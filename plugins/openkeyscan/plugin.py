"""OpenKeyScan-App – Tonart über die lokale REST-API der Desktop-App (#244).

API (https://www.openkeyscan.com/api, Port 58721, ohne Anmeldung):
  GET /health · POST /analyze/single {"file"} → {"success", "file", "key"} · POST /analyze/add {"files": […]}
  GET /analyze/result?file=… · GET /analyze/results · DELETE /analyze/clear (nie benutzt)
Die Tonart kommt in der Schreibweise, die in der App eingestellt ist (Camelot, Open Key, musikalisch) – keyscan.code_of
erkennt alle. Antwortformate von /health und /analyze/results sind nicht dokumentiert → tolerant lesen.

Schutz: nur Adressen auf diesem Rechner, nie über einen Proxy; ändert sich eine Datei während der Analyse (Auto-Tagging
der App), steht das als Warnung im Ergebnis. Vorschläge, Vergleich und Zwischenspeicher: keyscan.py (wie #245).
"""
import ipaddress
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import keyscan

DEFAULT_URL = "http://localhost:58721"
SINGLE_MAX = 20          # bis so viele Titel einzeln (wartet je Titel), darüber Warteschlange
BATCH = 1000             # höchstens so viele Dateien je /analyze/add
POLL = 2.0               # Sekunden zwischen zwei Abfragen der Warteschlange
IDLE_TIMEOUT = 300       # so lange ohne neues Ergebnis → aufgeben
DONE = {"done", "success", "succeeded", "complete", "completed", "finished", "analyzed", "ok"}
FAILED = {"error", "errored", "failed", "failure"}

OPTIONS = [
    {"key": "tkey", "type": "check", "label": "Auch TKEY vorschlagen (in deiner Schreibweise)", "default": True},
    {"key": "force", "type": "check", "label": "Abweichende Tonart in TKEY ebenfalls ankreuzen", "default": False},
    {"key": "cache", "type": "check", "label": "Frühere Ergebnisse verwenden (unveränderte Dateien nicht neu analysieren)",
     "default": True},
    {"key": "hint", "type": "info",
     "label": "Die OpenKeyScan-App muss laufen. In der App „Auto-Tagging“ ausschalten – sonst schreibt sie selbst in die "
              "Dateien. TagStudio zeigt das Ergebnis nur als Vorschau."},
]

ACTIONS = [
    {"id": "scan", "label": "Tonart mit der OpenKeyScan-App …", "where": "tagger", "run_label": "Tonart erkennen",
     "description": "Schickt die markierten Titel an die OpenKeyScan-App und zeigt die erkannte Tonart als Vorschau.",
     "options": OPTIONS},
    {"id": "settings", "label": "Einstellungen …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Adresse der OpenKeyScan-API (Standard: dieser Rechner, Port 58721).",
     "options": [{"key": "url", "type": "text", "label": "Adresse der OpenKeyScan-API", "default": DEFAULT_URL},
                 {"type": "info", "title": "Sicherheit",
                  "label": "Die API hat keine Anmeldung. TagStudio spricht sie nur auf diesem Rechner an (localhost).",
                  "links": [["OpenKeyScan: API", "https://www.openkeyscan.com/api"]]}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft, ob die OpenKeyScan-App unter der eingestellten Adresse antwortet.", "options": []},
]


class OKSError(RuntimeError):
    pass


# =========================================================================== Verbindung
def is_local(base: str) -> bool:
    host = (urllib.parse.urlparse(base or "").hostname or "").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Client:
    def __init__(self, base=DEFAULT_URL, timeout=30, opener=None):
        self.base = (base or DEFAULT_URL).strip().rstrip("/")
        if not self.base.startswith(("http://", "https://")) or not is_local(self.base):
            raise OKSError(f"TagStudio spricht OpenKeyScan nur auf diesem Rechner an (localhost) – nicht {self.base}.")
        self.timeout = timeout
        self._open = opener or urllib.request.build_opener(urllib.request.ProxyHandler({})).open   # nie über Proxy

    def request(self, method, path, body=None, query=None, timeout=None):
        url = self.base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Accept": "application/json", "Content-Type": "application/json"})
        try:
            with self._open(req, timeout=timeout or self.timeout) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as ex:
            raw = ex.read().decode("utf-8", "replace") if ex.fp else ""
            try:
                msg = json.loads(raw).get("error") or json.loads(raw).get("message") or raw
            except (ValueError, AttributeError):
                msg = raw
            raise OKSError(f"OpenKeyScan meldet Fehler {ex.code}{': ' + str(msg)[:200] if msg else ''} ({method} {path})") from ex
        except (urllib.error.URLError, OSError) as ex:
            raise OKSError(f"Keine Verbindung zur OpenKeyScan-App unter {self.base} – läuft die App? "
                           f"({getattr(ex, 'reason', ex)})") from ex
        try:
            return json.loads(raw) if raw.strip() else {}
        except ValueError:
            return {"text": raw.strip()}

    def health(self):
        return self.request("GET", "/health", timeout=5)

    def single(self, path, timeout=180):
        return self.request("POST", "/analyze/single", {"file": path}, timeout=timeout)

    def add(self, paths):
        return self.request("POST", "/analyze/add", {"files": list(paths)})

    def result(self, path):
        return self.request("GET", "/analyze/result", query={"file": path})

    def results(self):
        return self.request("GET", "/analyze/results")


# =========================================================================== Antworten lesen
def _norm(p) -> str:
    return os.path.normcase(os.path.normpath(str(p or ""))).replace("\\", "/")


def entries(data) -> list[dict]:
    """/analyze/results in eine Liste von Einträgen (Liste direkt oder in results/files/items/data)."""
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    if isinstance(data, dict):
        for k in ("results", "files", "items", "data", "tracks"):
            if k in data:
                return entries(data[k])
        if any(isinstance(v, dict) for v in data.values()):          # {Pfad: {…}}
            return [{"file": k, **v} for k, v in data.items() if isinstance(v, dict)]
    return []


def entry_path(e: dict) -> str:
    for k in ("file", "path", "filePath", "filepath", "location", "filename"):
        if e.get(k):
            return str(e[k])
    return ""


def entry_status(e: dict) -> str:
    """→ "done", "error" oder "pending"."""
    st = str(e.get("status") or e.get("state") or "").lower()
    if st in FAILED or e.get("error") or e.get("success") is False:
        return "error"
    if st in DONE or e.get("success") is True or (not st and entry_key(e)):
        return "done"
    return "pending"


def entry_key(e: dict):
    """Erkannte Tonart (nicht die schon vorhandene „current key“) → Camelot-Code oder None."""
    for k in ("analyzedKey", "analyzed_key", "detectedKey", "detected_key", "newKey", "result", "camelot", "key"):
        if k in e and e[k]:
            c = keyscan.code_of(e[k])
            if c:
                return c
    return None


# =========================================================================== Einstellungen
def _settings_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "settings.json")


def load_settings(ctx) -> dict:
    try:
        with open(_settings_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
        return {"url": str(d.get("url") or "")}
    except (OSError, ValueError, AttributeError):
        return {"url": ""}


def client(ctx, timeout=30) -> Client:
    return Client(load_settings(ctx)["url"] or DEFAULT_URL, timeout)


def test_connection(ctx):
    c = client(ctx)
    d = c.health()
    extra = ""
    if isinstance(d, dict):
        bits = [f"{k}: {d[k]}" for k in ("status", "version", "app", "message") if d.get(k) not in (None, "")]
        extra = f" ({', '.join(bits)})" if bits else ""
    return {"message": f"OpenKeyScan antwortet unter {c.base}{extra}."}


# =========================================================================== Analyse
def _stamps(files):
    out = {}
    for f in files:
        try:
            out[f.path] = os.stat(f.path).st_mtime
        except OSError:
            out[f.path] = None
    return out


def analyse(ctx, files, store) -> dict:
    """Dateien von der App analysieren lassen. → {"done": n, "failed": [Name], "changed": [Name]}"""
    c = client(ctx)
    ctx.status("Verbinde mit der OpenKeyScan-App …")
    c.health()
    before = _stamps(files)
    out = {"done": 0, "failed": [], "changed": []}
    n = len(files)
    if n <= SINGLE_MAX:
        for i, f in enumerate(files):
            name = os.path.basename(f.path)
            ctx.progress(i, n, "Analysiere " + name)
            try:
                d = c.single(f.path)
            except OKSError as ex:
                out["failed"].append(name)
                ctx.log(f"{name}: {ex}")
                continue
            code = keyscan.code_of(d) if not (isinstance(d, dict) and d.get("success") is False) else None
            if code:
                store.put(f.path, code, None, "openkeyscan", str(d.get("key") or "") if isinstance(d, dict) else "")
                out["done"] += 1
            else:
                out["failed"].append(name)
                ctx.log(f"{name}: keine Tonart erhalten ({json.dumps(d, ensure_ascii=False)[:200]})")
        ctx.progress(n, n, "fertig")
    else:
        for k in range(0, n, BATCH):
            ctx.status(f"Übergebe Titel {k + 1}–{min(n, k + BATCH)} an OpenKeyScan …")
            c.add([f.path for f in files[k:k + BATCH]])
        _collect(ctx, c, files, store, out)
    after = _stamps(files)
    changed = [p for p, t in after.items() if before.get(p) is not None and t != before[p]]
    for p in changed:            # Ergebnis gilt trotzdem – an den neuen Dateistand binden
        store.restamp(p)
    store.save()
    out["changed"] = [os.path.basename(p) for p in changed]
    if out["changed"]:
        ctx.log("Während der Analyse geändert (Auto-Tagging der App?): " + ", ".join(out["changed"][:50]))
    return out


def _collect(ctx, c, files, store, out):
    """Ergebnisse der Warteschlange abholen, bis alle fertig/fehlerhaft sind oder lange nichts mehr passiert."""
    want = {_norm(f.path): f for f in files}
    left = dict(want)
    last_change = time.monotonic()
    while left:
        ctx.check_cancel()
        try:
            rows = entries(c.results())
        except OKSError as ex:
            ctx.log(f"/analyze/results: {ex}")
            rows = []
        got = 0
        seen = {_norm(entry_path(e)): e for e in rows if entry_path(e)}
        if not rows:           # Liste leer/unbekannt → einzeln nachfragen
            seen = {}
            for p, f in list(left.items())[:50]:
                try:
                    e = c.result(f.path)
                except OKSError:
                    continue
                if isinstance(e, dict):
                    seen[p] = {**e, "file": f.path}
        for p, e in seen.items():
            f = left.get(p)
            if f is None:
                continue
            st = entry_status(e)
            if st == "done" and entry_key(e):
                store.put(f.path, entry_key(e), None, "openkeyscan")
                out["done"] += 1
            elif st == "error":
                out["failed"].append(os.path.basename(f.path))
                ctx.log(f"{os.path.basename(f.path)}: {e.get('error') or 'Fehler in OpenKeyScan'}")
            else:
                continue
            del left[p]
            got += 1
        done = len(want) - len(left)
        ctx.progress(done, len(want), f"OpenKeyScan: {done} von {len(want)} analysiert")
        if got:
            last_change = time.monotonic()
        elif time.monotonic() - last_change > IDLE_TIMEOUT:
            for f in left.values():
                out["failed"].append(os.path.basename(f.path))
            ctx.log(f"{len(left)} Titel ohne Ergebnis nach {IDLE_TIMEOUT // 60} Minuten ohne Fortschritt.")
            break
        if left:
            time.sleep(POLL)


def run_scan(ctx, files, opts):
    store = keyscan.Cache(os.path.join(ctx.data_dir, "ergebnisse.json"))
    todo = [f for f in files if not (opts.get("cache", True) and store.get(f.path))]
    res = analyse(ctx, todo, store) if todo else {"done": 0, "failed": [], "changed": []}
    stats, missing = {}, 0
    for f in files:
        e = store.get(f.path)
        if not e:
            missing += 1
            continue
        rel = keyscan.propose(ctx, f, e["camelot"], None, want_tkey=bool(opts.get("tkey", True)),
                              force_tkey=bool(opts.get("force")))
        stats[rel] = stats.get(rel, 0) + 1
    msg = f"Tonart für {len(files) - missing} von {len(files)} Titel(n) erkannt"
    s = keyscan.summary(stats)
    msg += f" – Vergleich mit TKEY: {s}." if s else "."
    if missing:
        msg += f" {missing} ohne Ergebnis – siehe Protokoll."
    if res["changed"]:
        msg += (f" Achtung: {len(res['changed'])} Datei(en) wurden während der Analyse verändert – vermutlich ist in "
                "der OpenKeyScan-App „Auto-Tagging“ eingeschaltet. Die Dateien neu laden, bevor du speicherst.")
    return {"message": msg}


def status(ctx):
    url = load_settings(ctx)["url"] or DEFAULT_URL
    return f"Adresse: {url}"


def run(action, ctx, files, opts):
    if action == "test":
        return test_connection(ctx)
    if action == "settings":
        url = str(opts.get("url") or "").strip().rstrip("/")
        if url and not is_local(url):
            raise OKSError("Nur Adressen auf diesem Rechner (localhost, 127.0.0.1) sind erlaubt.")
        with open(_settings_path(ctx), "w", encoding="utf-8") as fh:
            json.dump({"url": url}, fh)
        return {"message": f"Gespeichert. Adresse: {url or DEFAULT_URL}"}
    if action == "scan":
        return run_scan(ctx, files, opts)
    raise ValueError(f"Unbekannte Aktion: {action}")
