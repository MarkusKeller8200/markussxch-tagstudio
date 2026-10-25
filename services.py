"""MarKusSXCH TagStudio – Online-Dienste als Plugins (#204).

Ein Dienst-Plugin beschreibt sich in `plugin.json` unter "service":

    "service": {
      "name": "MusicBrainz", "kind": "online" | "local",
      "home": "https://musicbrainz.org", "docs": "https://musicbrainz.org/doc/MusicBrainz_API",
      "base": "https://musicbrainz.org/ws/2",
      "auth": "none" | "key" | "token" | "oauth" | "local", "auth_note": "…", "limits": "1 Anfrage/s", "terms": "https://…",
      "endpoints": [
        {"id": "recording-search", "method": "GET", "path": "/recording", "label": "Aufnahmen suchen",
         "status": "full" | "partial" | "none", "use": "Online-Metadaten: Suche", "note": "…",
         "params": [{"name": "query", "default": "…", "required": true, "label": "…", "in": "query" | "path"}],
         "test": true | false}
      ]
    }

Status: „full“ = vollständig genutzt, „partial“ = teilweise (nur ein Teil der Parameter/Felder), „none“ = nicht
implementiert (nur zur Übersicht). Der API-Tester ruft nur GET-Endpunkte auf, die nicht ausdrücklich mit
"test": false ausgeschlossen sind (z. B. Downloads). #350: Mit "write_test": true im Dienst sind auch POST, PUT, PATCH
und DELETE testbar – nur über api_request des Plugins, nur mit Bestätigung (`_confirm`), Body als JSON (`_body`).
Schlüssel setzt das Plugin über `auth(ctx)` ein; in URL und Antwort werden sie geschwärzt.

Optionale Funktionen im plugin.py eines Dienstes:
    auth(ctx) -> {"headers": {...}, "params": {...}}            Schlüssel/Token für den API-Tester
    api_request(ctx, endpoint, params) -> (status, headers, body, url)   eigener Abruf (z. B. OAuth mit Erneuerung)
    test_query(ctx, info) -> [Kandidat …]                           Testabfrage ohne Track
    score(info, kandidat) -> 0–1                                    eigene Bewertung (sonst onlinematch.score)
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse

STATUS = {"full": "vollständig", "partial": "teilweise", "none": "nicht implementiert"}
AUTH = {"none": "ohne Anmeldung", "key": "eigener Schlüssel", "token": "eigener Token", "oauth": "Anmeldung (OAuth)",
        "local": "lokales Programm"}
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
MAX_BODY = 300_000                     # Zeichen der Antwort im Tester
_ID = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,60}$")


def _url_ok(u, local=False) -> str:
    u = str(u or "").strip()
    if u.startswith("https://") or (local and u.startswith("http://")):
        return u
    return ""


QUERY_KEYS = ("artist", "title", "mix", "album", "isrc", "duration")


def clean(raw) -> dict | None:
    """Dienstbeschreibung aus plugin.json prüfen und bereinigen (fehlerhafte Einträge fallen weg)."""
    if not isinstance(raw, dict) or not raw.get("name"):
        return None
    kind = "local" if raw.get("kind") == "local" else "online"
    local = kind == "local"
    out = {"name": str(raw["name"])[:60], "kind": kind,
           "home": _url_ok(raw.get("home"), local), "docs": _url_ok(raw.get("docs"), local),
           "base": _url_ok(raw.get("base"), local), "terms": _url_ok(raw.get("terms")),
           "auth": raw.get("auth") if raw.get("auth") in AUTH else ("local" if local else "none"),
           "auth_note": str(raw.get("auth_note") or "")[:300], "limits": str(raw.get("limits") or "")[:200],
           "note": str(raw.get("note") or "")[:400], "endpoints": [], "write_test": bool(raw.get("write_test")),
           # #205: Beispiel für die Testabfrage, das beim Dienst tatsächlich einen Treffer liefert
           "example": {k: str(v)[:200] for k, v in (raw.get("example") or {}).items()
                       if k in QUERY_KEYS and isinstance(v, (str, int, float))} if isinstance(raw.get("example"), dict) else {}}
    seen = set()
    for e in raw.get("endpoints") or []:
        if not isinstance(e, dict):
            continue
        eid, method, path = str(e.get("id") or ""), str(e.get("method") or "GET").upper(), str(e.get("path") or "")
        if not _ID.match(eid) or eid in seen or method not in METHODS or not path.startswith("/"):
            continue
        seen.add(eid)
        params = []
        for p in e.get("params") or []:
            if isinstance(p, dict) and re.match(r"^[A-Za-z_][A-Za-z0-9_.\[\]-]{0,40}$", str(p.get("name") or "")):
                params.append({"name": p["name"], "label": str(p.get("label") or p["name"])[:80],
                               "default": "" if p.get("default") is None else str(p.get("default"))[:300],
                               "example": "" if p.get("example") is None else str(p.get("example"))[:300],
                               "required": bool(p.get("required")),
                               "in": "path" if "{" + p["name"] + "}" in path else "query"})
        for name in re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", path):      # Pfadparameter immer abfragen
            if not any(p["name"] == name for p in params):
                params.append({"name": name, "label": name, "default": "", "example": "", "required": True, "in": "path"})
        status = e.get("status") if e.get("status") in STATUS else "none"
        out["endpoints"].append({
            "id": eid, "method": method, "path": path, "label": str(e.get("label") or path)[:120],
            "status": status, "use": str(e.get("use") or "")[:200], "note": str(e.get("note") or "")[:300],
            "params": params,
            "write": method != "GET",
            "test": (method == "GET" or bool(raw.get("write_test"))) and e.get("test", True) is not False})
    return out


def counts(svc: dict) -> dict:
    c = {k: 0 for k in STATUS}
    for e in svc.get("endpoints", []):
        c[e["status"]] += 1
    return c


def summary(svc: dict, module=None) -> dict:
    """Kurzfassung für die Plugin-Karte."""
    return {"name": svc["name"], "kind": svc["kind"], "home": svc["home"], "docs": svc["docs"], "auth": svc["auth"],
            "auth_text": AUTH[svc["auth"]], "counts": counts(svc), "endpoints": len(svc["endpoints"]),
            "testable": any(e["test"] for e in svc["endpoints"]),
            "test_query": bool(module is not None and callable(getattr(module, "test_query", None)))}


# =========================================================================== Infos aus der Testabfrage
def _secs(v) -> float:
    """„6:12“ oder „372“ → Sekunden."""
    s = str(v or "").strip()
    m = re.match(r"^(\d+):(\d{1,2})$", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    try:
        return max(0.0, float(s.replace(",", ".")))
    except ValueError:
        return 0.0


def query_info(raw: dict) -> dict:
    """Eingaben der Testabfrage → info wie onlinematch.file_info (Titel ohne Mix, Mix, Künstler …)."""
    import onlinematch as om
    raw = raw if isinstance(raw, dict) else {}
    title, mix = om.split_title(str(raw.get("title") or "").strip())
    mix = str(raw.get("mix") or "").strip() or mix
    return {"title": title, "mix": mix, "artist": str(raw.get("artist") or "").strip(),
            "album": str(raw.get("album") or "").strip(), "isrc": str(raw.get("isrc") or "").strip().upper(),
            "duration": _secs(raw.get("duration"))}


def result_rows(module, info: dict, cands: list, limit=50) -> list:
    """Kandidaten bewerten und für die Anzeige aufbereiten (beste zuerst)."""
    import onlinematch as om
    score = None
    if module is not None:                      # test_score: eigene Bewertung für die Testabfrage (z. B. Rohdaten)
        score = getattr(module, "test_score", None) or getattr(module, "score", None)
    score = score if callable(score) else om.score
    rows = []
    for c in cands or []:
        if not isinstance(c, dict):
            continue
        try:
            s = float(score(info, c))
        except Exception:  # noqa: BLE001
            s = 0.0
        length = c.get("length")
        rows.append({"score": round(s * 100), "sure": s >= om.SURE, "maybe": s >= om.MAYBE,
                     "source": str(c.get("source_name") or c.get("source") or ""),
                     "artist": ", ".join(a for a in (c.get("artists") or []) if a) or str(c.get("artist") or ""),
                     "title": str(c.get("title") or ""), "mix": str(c.get("mix") or ""), "album": str(c.get("album") or ""),
                     "date": str(c.get("date") or "")[:10], "label": str(c.get("label") or ""), "isrc": str(c.get("isrc") or ""),
                     "length": f"{int(length) // 60}:{int(length) % 60:02d}" if isinstance(length, (int, float)) and length else "",
                     "id": str(c.get("id") or ""), "url": c.get("url") if str(c.get("url") or "").startswith("https://") else "",
                     "extra": str(c.get("extra") or "")[:200]})
    rows.sort(key=lambda r: -r["score"])
    return rows[:limit]


# =========================================================================== API-Tester
def build_url(svc: dict, ep: dict, params: dict, extra: dict | None = None) -> str:
    """Adresse aus base + path; {name} im Pfad wird ersetzt, übrige Werte als Query. Leere Werte entfallen."""
    path = ep["path"]
    query = []
    for p in ep["params"]:
        v = str((params or {}).get(p["name"], p["default"]) or "").strip()
        if p["in"] == "path":
            if not v:
                raise ValueError(f"Bitte „{p['label']}“ angeben.")
            path = path.replace("{" + p["name"] + "}", urllib.parse.quote(v, safe=":"))
        elif v:
            query.append((p["name"], v))
        elif p["required"]:
            raise ValueError(f"Bitte „{p['label']}“ angeben.")
    for k, v in (extra or {}).items():
        if v not in (None, ""):
            query.append((k, str(v)))
    base = svc["base"].rstrip("/")
    return base + path + ("?" + urllib.parse.urlencode(query) if query else "")


def redact(text: str, secrets) -> str:
    out = str(text or "")
    for s in secrets:
        s = str(s or "")
        if len(s) >= 4:
            out = out.replace(s, "•••").replace(urllib.parse.quote(s, safe=""), "•••")
    return out


def format_response(status: int, headers: dict, body: bytes, url: str, ms: float, secrets=()) -> dict:
    h = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    ctype = h.get("content-type", "")
    text, is_json = "", False
    if body:
        try:
            data = json.loads(body.decode("utf-8"))
            text, is_json = json.dumps(data, ensure_ascii=False, indent=2), True
        except (UnicodeDecodeError, ValueError):
            if "text" in ctype or "json" in ctype or "xml" in ctype or not ctype:
                text = body.decode("utf-8", "replace")
            else:
                text = f"(Binärdaten · {ctype or 'unbekannt'} · {len(body):,} Bytes)".replace(",", "'")
    cut = len(text) > MAX_BODY
    keep = ("content-type", "content-length", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining",
            "ratelimit-remaining", "x-discogs-ratelimit-remaining", "cache-control", "date")
    return {"status": status, "ok": 200 <= status < 300, "ms": round(ms), "bytes": len(body or b""),
            "url": redact(url, secrets), "json": is_json, "content_type": ctype,
            "headers": {k: redact(v, secrets) for k, v in h.items() if k in keep},
            "body": redact(text[:MAX_BODY], secrets) + ("\n… (gekürzt)" if cut else "")}


def api_call(plugin, ctx, eid: str, params: dict, user_agent: str) -> dict:
    """Einen Endpunkt eines Dienst-Plugins aufrufen (nur GET, nur testbare). Schlüssel werden geschwärzt."""
    import onlinematch as om
    svc = plugin.service
    if not svc:
        raise ValueError("Dieses Plugin beschreibt keinen Dienst.")
    ep = next((e for e in svc["endpoints"] if e["id"] == eid), None)
    if ep is None:
        raise ValueError(f"Endpunkt „{eid}“ nicht gefunden.")
    if not ep["test"]:
        raise ValueError("Dieser Endpunkt wird im Tester nicht aufgerufen (ändert Daten oder lädt Dateien).")
    mod = plugin.load()
    custom = getattr(mod, "api_request", None) if mod is not None else None
    if ep.get("write"):                                         # #350: schreibend nur bestätigt und über das Plugin
        if str((params or {}).get("_confirm") or "") != "yes":
            raise ValueError("Schreibende Anfrage nicht bestätigt – es wurde nichts gesendet.")
        if not callable(custom):
            raise ValueError("Dieses Plugin kann schreibende Anfragen nicht testen.")
        body = str((params or {}).get("_body") or "").strip()
        if body:
            try:
                json.loads(body)
            except ValueError as ex:
                raise ValueError(f"Body ist kein gültiges JSON: {ex}") from None
    auth = getattr(mod, "auth", None) if mod is not None else None
    a = auth(ctx) if callable(auth) else {}
    a = a if isinstance(a, dict) else {}
    secrets = [v for v in list((a.get("headers") or {}).values()) + list((a.get("params") or {}).values()) if v]
    for v in list((a.get("headers") or {}).values()):           # „Bearer xyz“, „Discogs token=xyz“: auch den Teil
        secrets += re.findall(r"[A-Za-z0-9._~+/=-]{12,}", str(v))
    t0 = time.monotonic()
    if callable(custom):
        status, headers, body, url = custom(ctx, ep, params or {})
        secrets += list(getattr(ctx, "secrets", []) or [])
    else:
        url = build_url(svc, ep, params or {}, a.get("params"))
        # #212: dieselbe Drosselung und Wiederholung wie die Suche (schnelles Senden → sonst HTTP 503)
        status, headers, body, retries = om.get_retry(
            url, {"User-Agent": user_agent, "Accept": "application/json", **(a.get("headers") or {})},
            cancel=getattr(ctx, "check_cancel", None), log=getattr(ctx, "log", None))
    res = format_response(status, headers, body, url, (time.monotonic() - t0) * 1000, secrets)
    res["retries"] = 0 if callable(custom) else retries
    return res


# =========================================================================== #297: Zugriff prüfen
ACCESS = {"ok": "Zugriff", "reach": "erreichbar", "denied": "kein Zugriff", "notfound": "nicht gefunden",
          "limit": "begrenzt", "error": "Fehler", "skip": "übersprungen"}
_COUNT_NAMES = ("num", "n", "count", "limit")


def _access_class(status: int) -> str:
    if 200 <= status < 300:
        return "ok"
    if status in (401, 403):
        return "denied"
    if status in (400, 405, 422):                  # Route erlaubt, aber Anfrage unvollständig (z. B. Pflichtparameter)
        return "reach"
    if status == 404:
        return "notfound"
    if status == 429:
        return "limit"
    return "error"


def _first_id(body: bytes):
    try:
        data = json.loads((body or b"").decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if isinstance(data, dict):
        data = data.get("results") if isinstance(data.get("results"), list) else data
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict) and x.get("id") is not None), None)
    return data.get("id") if isinstance(data, dict) and data.get("id") is not None else None


def _detail(body: bytes, secrets) -> str:
    try:
        data = json.loads((body or b"").decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    d = data.get("detail") or data.get("error_description") or data.get("error") or data.get("message") or ""
    return redact(str(d)[:200], secrets)


def access_check(plugin, ctx, user_agent: str) -> dict:
    """Mit der aktuellen Anmeldung jeden lesenden Endpunkt (GET) einmal aufrufen und einordnen: Zugriff, erreichbar
    (Anfrage unvollständig), kein Zugriff (401/403), nicht gefunden … Nur GET; Anmelde-Routen und Datei-Downloads
    werden ausgelassen. Pfad-IDs kommen aus der ersten Antwort der passenden Liste. → {"rows", "counts"}"""
    import onlinematch as om
    svc = plugin.service
    if not svc:
        raise ValueError("Dieses Plugin beschreibt keinen Dienst.")
    mod = plugin.load()
    custom = getattr(mod, "api_request", None) if mod is not None else None
    auth = getattr(mod, "auth", None) if mod is not None else None
    a = auth(ctx) if callable(auth) else {}
    a = a if isinstance(a, dict) else {}
    secrets = [v for v in list((a.get("headers") or {}).values()) + list((a.get("params") or {}).values()) if v]
    eps = [e for e in svc["endpoints"] if e["method"] == "GET" and not e["path"].startswith("/auth/")
           and not e["path"].rstrip("/").endswith("/download")]
    eps.sort(key=lambda e: (e["path"].count("{"), e["path"]))       # Listen zuerst (liefern die Beispiel-IDs)
    ids, rows = {}, []
    for i, e in enumerate(eps, 1):
        ctx.progress(i - 1, len(eps), e["path"])
        row = {"id": e["id"], "method": e["method"], "path": e["path"], "label": e["label"], "status": 0,
               "access": "skip", "detail": "", "ms": 0}
        params, ep = {}, dict(e)
        pp = [p for p in e["params"] if p["in"] == "path"]
        if pp:
            for p in pp:                    # je Platzhalter: ID aus der Liste davor, z. B. /my/playlists/ → {pk}
                base = e["path"][:e["path"].index("{" + p["name"] + "}")]
                if p["name"] in _COUNT_NAMES:
                    params[p["name"]] = "10"
                elif ids.get(base) is not None:
                    params[p["name"]] = str(ids[base])
            if len(params) < len(pp):
                row["detail"] = "keine Beispiel-ID aus der Liste"
                rows.append(row)
                continue
        for p in e["params"]:                                       # Pflichtwerte der Abfrage: Beispiel oder leer
            if p["in"] == "query" and p["required"] and p.get("example"):
                params[p["name"]] = p["example"]
        if not any(p["name"] == "per_page" for p in e["params"]):
            ep["params"] = e["params"] + [{"name": "per_page", "label": "per_page", "default": "1", "example": "",
                                           "required": False, "in": "query"}]
        t0 = time.monotonic()
        try:
            if callable(custom):
                status, _h, body, _url = custom(ctx, ep, params)
                secrets += list(getattr(ctx, "secrets", []) or [])
            else:
                url = build_url(svc, ep, params, a.get("params"))
                status, _h, body, _r = om.get_retry(
                    url, {"User-Agent": user_agent, "Accept": "application/json", **(a.get("headers") or {})},
                    cancel=getattr(ctx, "check_cancel", None), log=None)
        except ValueError as ex:                                    # fehlender Pflichtwert
            row["detail"] = str(ex)
            rows.append(row)
            continue
        except Exception as ex:  # noqa: BLE001 – ein Endpunkt darf die Prüfung nicht abbrechen
            if type(ex).__name__ == "Cancelled":
                raise
            row.update(access="error", detail=redact(str(ex)[:200], secrets))
            rows.append(row)
            continue
        row.update(status=int(status), access=_access_class(int(status)), ms=round((time.monotonic() - t0) * 1000))
        if row["access"] == "ok":
            fid = _first_id(body)
            if fid is not None:
                ids[e["path"]] = fid
        elif row["access"] != "ok":
            row["detail"] = _detail(body, secrets)
        rows.append(row)
    counts = {k: 0 for k in ACCESS}
    for r in rows:
        counts[r["access"]] += 1
    ctx.progress(len(eps), len(eps), "fertig")
    return {"rows": rows, "counts": counts, "labels": ACCESS}


# =========================================================================== Kern (kein Plugin)
CORE = [{
    "id": "core-github", "plugin": None, "name": "GitHub Releases (Updates)", "kind": "online",
    "home": "https://github.com/MarkusKeller8200/markussxch-tagstudio",
    "docs": "https://docs.github.com/rest/releases/releases", "auth": "none", "auth_text": AUTH["none"],
    "note": "Update-Prüfung und Download – bleibt im Kern, damit Updates auch ohne Plugins funktionieren.",
    "endpoints": [
        {"id": "releases", "method": "GET", "path": "/repos/{owner}/{repo}/releases", "label": "Versionen auflisten",
         "status": "full", "use": "Updates: neueste Version und Beta-Kanal", "note": "", "params": [], "test": False},
        {"id": "asset", "method": "GET", "path": "(Download-Adresse aus der Version)", "label": "Installer/Update herunterladen",
         "status": "full", "use": "Updates: Download", "note": "", "params": [], "test": False},
        {"id": "latest", "method": "GET", "path": "/repos/{owner}/{repo}/releases/latest", "label": "Neueste Version",
         "status": "none", "use": "", "note": "nicht nötig – die Liste enthält auch Betas", "params": [], "test": False},
    ]}]
