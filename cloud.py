"""Cloud-Sync-Ordner erkennen (#315, docs/KONZEPT-ORDNER.md Abschnitt 9, Weg 1).

TagStudio arbeitet nur mit dem Ordner, den der Desktop-Client (OneDrive, Google Drive, Dropbox) synchronisiert –
kein Zugriff auf die Dienste selbst. Erkannt werden:

- **Sync-Ordner** je Anbieter (Windows und macOS) → Anzeige „☁ OneDrive“ und Pfade relativ zum Sync-Ordner
  (gelten auf einem zweiten Rechner mit anderem Benutzernamen/Laufwerk),
- **Nur-online-Dateien** („Dateien bei Bedarf“): beim Einlesen übersprungen, damit nichts unbemerkt herunterlädt,
- **Konfliktkopien** der Clients („… (Konfliktkopie …)“, „conflicted copy“, „-<RECHNER>“ bei OneDrive).

Nur Standardbibliothek; liest nie Dateiinhalte (os.stat lädt keine Nur-online-Datei herunter).
"""
from __future__ import annotations

import json
import os
import re
import string
import sys
import time

PROVIDERS = {"onedrive": "OneDrive", "onedrive_business": "OneDrive (Geschäftlich)", "gdrive": "Google Drive",
             "dropbox": "Dropbox"}
# Rollen, die nicht in einen Sync-Ordner gehören (viele kleine Dateien, Sperren, Konfliktgefahr)
NOT_IN_CLOUD = ("snapshots", "work", "backup")

# Windows: Datei-Attribute (os.stat().st_file_attributes)
_FILE_ATTRIBUTE_OFFLINE = 0x1000
_FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
# macOS: st_flags SF_DATALESS (Datei ohne lokalen Inhalt)
_SF_DATALESS = 0x40000000

LOAD_ONLINE = False              # Einstellung „Nur-online-Dateien beim Einlesen herunterladen“ (setzt die Sitzung)

_CACHE: dict = {"t": 0.0, "roots": []}
_TTL = 60.0


def _home() -> str:
    return os.path.expanduser("~")


def _dropbox_info() -> list[str]:
    """Pfade aus info.json des Dropbox-Clients (privat und geschäftlich)."""
    cands = []
    for env in ("APPDATA", "LOCALAPPDATA"):
        if os.environ.get(env):
            cands.append(os.path.join(os.environ[env], "Dropbox", "info.json"))
    cands.append(os.path.join(_home(), ".dropbox", "info.json"))
    out = []
    for p in cands:
        try:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for k in ("personal", "business"):
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, dict) and isinstance(v.get("path"), str):
                out.append(v["path"])
    return out


def _local_letters() -> list[str]:
    """Windows: vorhandene, nicht-Netz-Laufwerke ab D: (getrennte Netzlaufwerke würden das Prüfen aufhalten)."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        mask = k32.GetLogicalDrives()
    except (AttributeError, OSError):
        return []
    out = []
    for i, letter in enumerate(string.ascii_uppercase):
        if i >= 3 and mask & (1 << i) and k32.GetDriveTypeW(f"{letter}:\\") in (2, 3):   # Wechseldatenträger, fest
            out.append(letter)
    return out


def detect(refresh: bool = False) -> list[dict]:
    """Sync-Ordner auf diesem Rechner → [{"provider", "label", "path"}] (vorhandene Ordner, ohne Doppel)."""
    if not refresh and time.time() - _CACHE["t"] < _TTL:
        return list(_CACHE["roots"])
    found: list[tuple[str, str]] = []
    env = os.environ
    for var, prov in (("OneDriveConsumer", "onedrive"), ("OneDriveCommercial", "onedrive_business"),
                      ("OneDrive", "onedrive")):
        if env.get(var):
            found.append((prov, env[var]))
    cs = os.path.join(_home(), "Library", "CloudStorage")                    # macOS (File Provider)
    try:
        for n in sorted(os.listdir(cs)):
            low = n.lower()
            if low.startswith("onedrive-"):
                prov = "onedrive" if "persönlich" in low or "personal" in low else "onedrive_business"
                found.append((prov, os.path.join(cs, n)))
            elif low.startswith("googledrive-"):
                p = os.path.join(cs, n)
                for sub in ("My Drive", "Meine Ablage"):
                    found.append(("gdrive", os.path.join(p, sub)))
            elif low.startswith("dropbox"):
                found.append(("dropbox", os.path.join(cs, n)))
    except OSError:
        pass
    if sys.platform.startswith("win"):                                       # Google Drive: eigenes Laufwerk
        for letter in _local_letters():
            for sub in ("My Drive", "Meine Ablage"):
                p = f"{letter}:\\{sub}"
                if os.path.isdir(p):
                    found.append(("gdrive", p))
    for p in (os.path.join(_home(), "Google Drive"), os.path.join(_home(), "OneDrive")):
        found.append(("gdrive" if "Google" in p else "onedrive", p))
    found += [("dropbox", p) for p in _dropbox_info()]
    out, seen = [], set()
    for prov, p in found:
        p = os.path.normpath(p)
        k = os.path.normcase(p)
        if k in seen or not os.path.isdir(p):
            continue
        seen.add(k)
        out.append({"provider": prov, "label": PROVIDERS[prov], "path": p})
    _CACHE.update(t=time.time(), roots=out)
    return list(out)


def _inside_or_same(child: str, root: str) -> bool:
    c, r = os.path.normcase(os.path.abspath(child)), os.path.normcase(os.path.abspath(root))
    try:
        return os.path.commonpath([c, r]) == r
    except ValueError:
        return False


def locate(path: str, roots=None) -> dict | None:
    """In welchem Sync-Ordner liegt path? → {"provider", "label", "root", "rel"} oder None."""
    if not path:
        return None
    best = None
    for r in roots if roots is not None else detect():
        if _inside_or_same(path, r["path"]) and (best is None or len(r["path"]) > len(best["path"])):
            best = r
    if best is None:
        return None
    rel = os.path.relpath(os.path.abspath(path), best["path"]).replace(os.sep, "/")
    return {"provider": best["provider"], "label": best["label"], "root": best["path"], "rel": "" if rel == "." else rel}


def rebuild(tag: dict, roots=None) -> str:
    """Pfad aus {"provider", "rel"} auf diesem Rechner (für Einstellungen von einem zweiten Rechner) – "" = fehlt."""
    if not isinstance(tag, dict) or tag.get("provider") not in PROVIDERS:
        return ""
    for r in roots if roots is not None else detect():
        if r["provider"] == tag["provider"]:
            rel = str(tag.get("rel") or "")
            p = os.path.normpath(os.path.join(r["path"], *[x for x in rel.split("/") if x and x != ".."]))
            if os.path.isdir(p):
                return p
    return ""


def online_only(path: str, st=None) -> bool:
    """Datei nur in der Cloud (noch nicht lokal)? Liest keine Daten – Öffnen würde sie herunterladen."""
    try:
        st = st or os.stat(path)
    except OSError:
        return False
    attrs = getattr(st, "st_file_attributes", 0) or 0
    if attrs & (_FILE_ATTRIBUTE_OFFLINE | _FILE_ATTRIBUTE_RECALL_ON_OPEN | _FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS):
        return True
    flags = getattr(st, "st_flags", 0) or 0
    return bool(flags & _SF_DATALESS)


_CONFLICT = [
    re.compile(r"\((?:[^()]*\s)?(?:conflicted copy|Konfliktkopie|copie en conflit|copia in conflitto)[^()]*\)", re.I),  # Dropbox
    re.compile(r"\s\((?:Konflikt|conflict)[^()]*\)", re.I),                          # Google Drive / allgemein
]


def is_conflict(name: str, provider: str = "") -> bool:
    """Konfliktkopie eines Sync-Clients am Dateinamen erkennen."""
    stem = os.path.splitext(os.path.basename(name))[0]
    if any(rx.search(stem) for rx in _CONFLICT):
        return True
    if provider.startswith("onedrive"):                                         # „Titel-DESKTOP-AB12CD.mp3“
        comp = os.environ.get("COMPUTERNAME") or ""
        if comp and stem.upper().endswith("-" + comp.upper()):
            return True
        return bool(re.search(r"-(?:DESKTOP|LAPTOP)-[A-Z0-9]{5,}$", stem, re.I))
    return False


def filter_paths(paths: list[str], root: str) -> tuple[list[str], dict]:
    """Beim Einlesen: Nur-online-Dateien weglassen (ausser LOAD_ONLINE), Konfliktkopien merken.
    → (paths, {"provider", "online": [...], "conflicts": [...]}); ausserhalb eines Sync-Ordners unverändert."""
    loc = locate(root)
    info = {"provider": loc["label"] if loc else "", "online": [], "conflicts": []}
    if loc is None:
        return paths, info
    keep = []
    for p in paths:
        if is_conflict(p, loc["provider"]):
            info["conflicts"].append(p)
        if not LOAD_ONLINE and online_only(p):
            info["online"].append(p)
            continue
        keep.append(p)
    return keep, info
