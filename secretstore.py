"""MarKusSXCH TagStudio – Zugangsdaten sicher ablegen (#287).

Eine Geheimnis-Datei (z. B. `token.bin`, `keys.bin` eines Plugins) wird je nach System so gespeichert:

- **Windows:** Inhalt mit DPAPI verschlüsselt (`DPAPI` + Daten), nur für den angemeldeten Benutzer lesbar.
- **macOS:** Inhalt im Schlüsselbund des Benutzers (Security.framework, Eintrag „Generisches Passwort“, Dienst
  `MarKusSXCH TagStudio`, Konto = Pfad der Datei – damit sind Profile und Plugins getrennt). In der Datei steht nur
  noch der Verweis `KEYCHAIN:1`. Eine ältere Klartext-Datei wird beim ersten Lesen übernommen und durch den Verweis
  ersetzt (die Datei wird nicht gelöscht, nur überschrieben).
- **Rückfall** (Linux, CI, Schlüsselbund gesperrt oder Zugriff verweigert): Klartext-Datei mit Rechten 0600 wie bis
  4.9.0. Der Grund steht in `last_note()` (ohne Inhalt) und kann im Plugin angezeigt bzw. protokolliert werden.

Geheimnisse erscheinen nie im Protokoll. Nur Standardbibliothek (ctypes).
"""
from __future__ import annotations

import os
import sys
import threading

SERVICE = "MarKusSXCH TagStudio"
MARK = b"KEYCHAIN:1"
_lock = threading.Lock()
_note = ""

# In Tests ersetzbar: Objekt mit get(account) -> bytes|None, set(account, data), delete(account).
backend = None


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_mac() -> bool:
    return sys.platform == "darwin"


def last_note() -> str:
    """Hinweis zum letzten Rückfall (z. B. „Schlüsselbund nicht verfügbar …“), sonst leer."""
    return _note


def _set_note(text: str):
    global _note
    _note = text


# ---------------------------------------------------------------- Windows: DPAPI
def dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("Windows-Verschlüsselung (DPAPI) fehlgeschlagen.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


# ---------------------------------------------------------------- macOS: Schlüsselbund
class KeychainError(OSError):
    def __init__(self, status: int, what: str):
        super().__init__(f"Schlüsselbund: {what} fehlgeschlagen (OSStatus {status})")
        self.status = status


class MacKeychain:
    """Generische Passwörter über SecItemAdd/SecItemUpdate/SecItemCopyMatching/SecItemDelete."""
    NOT_FOUND = -25300
    DUPLICATE = -25299

    def __init__(self):
        import ctypes
        from ctypes import c_void_p, c_long, c_int32, c_char_p, POINTER
        self.ct = ctypes
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        sec = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
        self.cf, self.sec = cf, sec
        cf.CFStringCreateWithCString.restype = c_void_p
        cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, ctypes.c_uint32]
        cf.CFDataCreate.restype = c_void_p
        cf.CFDataCreate.argtypes = [c_void_p, c_char_p, c_long]
        cf.CFDataGetLength.restype = c_long
        cf.CFDataGetLength.argtypes = [c_void_p]
        cf.CFDataGetBytePtr.restype = c_void_p
        cf.CFDataGetBytePtr.argtypes = [c_void_p]
        cf.CFDictionaryCreate.restype = c_void_p
        cf.CFDictionaryCreate.argtypes = [c_void_p, POINTER(c_void_p), POINTER(c_void_p), c_long, c_void_p, c_void_p]
        cf.CFRelease.restype = None
        cf.CFRelease.argtypes = [c_void_p]
        for fn in ("SecItemAdd", "SecItemCopyMatching"):
            getattr(sec, fn).restype = c_int32
            getattr(sec, fn).argtypes = [c_void_p, POINTER(c_void_p)]
        sec.SecItemUpdate.restype = c_int32
        sec.SecItemUpdate.argtypes = [c_void_p, c_void_p]
        sec.SecItemDelete.restype = c_int32
        sec.SecItemDelete.argtypes = [c_void_p]
        k = lambda lib, name: c_void_p.in_dll(lib, name).value  # noqa: E731
        self.kClass = k(sec, "kSecClass")
        self.kGeneric = k(sec, "kSecClassGenericPassword")
        self.kService = k(sec, "kSecAttrService")
        self.kAccount = k(sec, "kSecAttrAccount")
        self.kData = k(sec, "kSecValueData")
        self.kReturnData = k(sec, "kSecReturnData")
        self.kMatchLimit = k(sec, "kSecMatchLimit")
        self.kMatchOne = k(sec, "kSecMatchLimitOne")
        self.kTrue = k(cf, "kCFBooleanTrue")
        self.keyCB = ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryKeyCallBacks"))
        self.valCB = ctypes.addressof(ctypes.c_byte.in_dll(cf, "kCFTypeDictionaryValueCallBacks"))

    def _str(self, s: str):
        return self.cf.CFStringCreateWithCString(None, s.encode("utf-8"), 0x08000100)

    def _dict(self, pairs):
        ct = self.ct
        n = len(pairs)
        keys = (ct.c_void_p * n)(*[p[0] for p in pairs])
        vals = (ct.c_void_p * n)(*[p[1] for p in pairs])
        return self.cf.CFDictionaryCreate(None, keys, vals, n, self.keyCB, self.valCB)

    def _query(self, account: str, extra=()):
        svc, acc = self._str(SERVICE), self._str(account)
        d = self._dict([(self.kClass, self.kGeneric), (self.kService, svc), (self.kAccount, acc), *extra])
        self.cf.CFRelease(svc)
        self.cf.CFRelease(acc)
        return d

    def get(self, account: str) -> bytes | None:
        ct = self.ct
        q = self._query(account, [(self.kReturnData, self.kTrue), (self.kMatchLimit, self.kMatchOne)])
        out = ct.c_void_p()
        try:
            st = self.sec.SecItemCopyMatching(q, ct.byref(out))
        finally:
            self.cf.CFRelease(q)
        if st == self.NOT_FOUND:
            return None
        if st != 0 or not out.value:
            raise KeychainError(st, "Lesen")
        try:
            n = self.cf.CFDataGetLength(out.value)
            return ct.string_at(self.cf.CFDataGetBytePtr(out.value), n)
        finally:
            self.cf.CFRelease(out.value)

    def set(self, account: str, data: bytes):
        val = self.cf.CFDataCreate(None, data, len(data))
        try:
            add = self._query(account, [(self.kData, val)])
            try:
                st = self.sec.SecItemAdd(add, None)
            finally:
                self.cf.CFRelease(add)
            if st == self.DUPLICATE:
                q = self._query(account)
                upd = self._dict([(self.kData, val)])
                try:
                    st = self.sec.SecItemUpdate(q, upd)
                finally:
                    self.cf.CFRelease(q)
                    self.cf.CFRelease(upd)
            if st != 0:
                raise KeychainError(st, "Speichern")
        finally:
            self.cf.CFRelease(val)

    def delete(self, account: str):
        q = self._query(account)
        try:
            st = self.sec.SecItemDelete(q)
        finally:
            self.cf.CFRelease(q)
        if st not in (0, self.NOT_FOUND):
            raise KeychainError(st, "Löschen")


_mac = None


def _keychain():
    """Schlüsselbund-Zugang oder None (nicht macOS, Framework nicht ladbar)."""
    global _mac
    if backend is not None:
        return backend
    if not is_mac():
        return None
    if _mac is None:
        try:
            _mac = MacKeychain()
        except Exception as e:  # noqa: BLE001
            _set_note(f"Schlüsselbund nicht verfügbar ({type(e).__name__}) – Datei nur für dich lesbar (0600).")
            _mac = False
    return _mac or None


def account_for(path: str) -> str:
    return os.path.abspath(path)


# ---------------------------------------------------------------- Datei
def _write_file(path: str, raw: bytes):
    """Atomar schreiben; ausserhalb von Windows von Anfang an nur für den Benutzer lesbar."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        if not is_windows():
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write(path: str, data: bytes) -> str:
    """Geheimnis speichern. Rückgabe: „dpapi“, „keychain“ oder „file“ (Rückfall, Grund in last_note())."""
    with _lock:
        if is_windows() and backend is None:
            _write_file(path, b"DPAPI" + dpapi(data, True))
            return "dpapi"
        kc = _keychain()
        if kc is not None:
            try:
                kc.set(account_for(path), data)
                _write_file(path, MARK)
                _set_note("")
                return "keychain"
            except OSError as e:
                _set_note(f"{e} – Datei nur für dich lesbar (0600).")
        _write_file(path, data)
        return "file"


def read(path: str) -> bytes | None:
    """Geheimnis lesen (None = keins gespeichert oder nicht lesbar). Klartext unter macOS wird übernommen."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if raw.startswith(b"DPAPI"):
        return dpapi(raw[5:], False)
    if raw.strip() == MARK:
        kc = _keychain()
        if kc is None:
            return None
        try:
            return kc.get(account_for(path))
        except OSError as e:
            _set_note(str(e))
            return None
    if raw and _keychain() is not None and not is_windows():
        # Klartext aus einer früheren Version → einmalig in den Schlüsselbund übernehmen
        try:
            write(path, raw)
        except OSError:
            pass
    return raw


def delete(path: str) -> bool:
    """Geheimnis entfernen (Eintrag im Schlüsselbund und Datei). True, wenn etwas da war."""
    had = False
    try:
        with open(path, "rb") as fh:
            marked = fh.read().strip() == MARK
    except OSError:
        marked = False
    kc = _keychain()
    if kc is not None:
        try:
            if marked or kc.get(account_for(path)) is not None:
                kc.delete(account_for(path))
                had = True
        except OSError as e:
            _set_note(str(e))
    try:
        os.remove(path)
        had = True
    except OSError:
        pass
    return had
