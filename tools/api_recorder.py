#!/usr/bin/env python3
"""API-Rekorder (#243) – Entwicklerwerkzeug, nicht Teil der App.

Öffnet eine Website in Chromium (Playwright). Du klickst dich durch; das Werkzeug liest die JSON-Aufrufe der Seite an
ihre Schnittstelle passiv mit und schreibt nach dem Schliessen des Browsers:

  recording.json  – Aufrufe: Methode, Pfad, Parameter, Status, Antwortfelder, gekürzte Beispielwerte
  service.json    – Entwurf des Abschnitts "service" für plugin.json (Endpunkte mit Platzhaltern wie /tracks/{id})

Aufruf:
  python tools/api_recorder.py https://example.org [--host api.example.org] [--out ORDNER] [--profile ORDNER]

Schutz: Cookies, Authorization- und ähnliche Kopfzeilen werden nie gespeichert, Werte mit Schlüsseln wie token,
password, secret, session, email werden geschwärzt, ebenso lange Zeichenketten, die wie Schlüssel aussehen. Es
werden keine eigenen Anfragen geschickt. Nur für Schnittstellen verwenden, die du nutzen darfst – Nutzungsbedingungen
der Website beachten. Ausgabe standardmässig unter ~/TagStudio/API-Aufnahmen/<host>/ (nicht im Repo).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse

SECRET_KEY = re.compile(r"(token|auth|password|passwd|secret|session|cookie|csrf|xsrf|signature|sig|apikey|api_key|"
                        r"key_id|email|e-mail|phone|bearer)", re.I)
DROP_HEADERS = {"cookie", "set-cookie", "authorization", "proxy-authorization", "x-api-key", "x-auth-token",
                "x-csrf-token", "x-xsrf-token"}
KEEP_HEADERS = {"accept", "content-type", "x-requested-with"}
LONG_SECRET = re.compile(r"^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_\-.=+/]{32,}$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ID_SEGMENT = re.compile(r"^(\d+|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{16,}|"
                        r"[A-Za-z0-9_-]{20,})$", re.I)
MAX_STR = 120


# =========================================================================== Schwärzen
def redact_value(key: str, value):
    """Einzelwert schwärzen, wenn Schlüssel oder Inhalt nach Zugangsdaten bzw. persönlichen Angaben aussehen."""
    if isinstance(value, str):
        if SECRET_KEY.search(key or "") or LONG_SECRET.match(value) or EMAIL.search(value):
            return "•••"
        return value if len(value) <= MAX_STR else value[:MAX_STR] + "…"
    if isinstance(value, (int, float, bool)) or value is None:
        return "•••" if SECRET_KEY.search(key or "") and value is not None else value
    return value


def redact(obj, key: str = "", depth: int = 0, max_items: int = 3):
    """JSON-Daten schwärzen und kürzen (Listen auf wenige Beispiele, Tiefe begrenzt)."""
    if depth > 8:
        return "…"
    if isinstance(obj, dict):
        return {k: ("•••" if SECRET_KEY.search(k) else redact(v, k, depth + 1, max_items)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v, key, depth + 1, max_items) for v in obj[:max_items]]
    return redact_value(key, obj)


def safe_headers(headers: dict) -> dict:
    """Nur unkritische Kopfzeilen behalten – Cookies und Anmeldung nie."""
    return {k.lower(): v for k, v in (headers or {}).items()
            if k.lower() in KEEP_HEADERS and k.lower() not in DROP_HEADERS}


def safe_query(query: str) -> dict:
    out = {}
    for k, v in urllib.parse.parse_qsl(query or "", keep_blank_values=True):
        out[k] = "•••" if SECRET_KEY.search(k) else redact_value(k, v)
    return out


# =========================================================================== Struktur
def template_path(path: str) -> tuple[str, list[str]]:
    """/tracks/12345/cues → ("/tracks/{id}/cues", ["id"]) – Kennungen werden zu Platzhaltern."""
    parts, names = [], []
    for seg in (path or "/").split("/"):
        if seg and ID_SEGMENT.match(seg):
            prev = parts[-1] if parts else ""
            name = re.sub(r"[^a-z0-9_]", "", (prev[:-1] if prev.endswith("s") else prev).lower()) + "_id" if prev else "id"
            name = name if name != "_id" else "id"
            while name in names:
                name += "2"
            names.append(name)
            parts.append("{" + name + "}")
        else:
            parts.append(seg)
    return "/".join(parts) or "/", names


def fields(obj, prefix: str = "", depth: int = 0, out=None) -> list[str]:
    """Feldpfade einer JSON-Antwort (z. B. data.tracks[].title)."""
    out = [] if out is None else out
    if depth > 6 or len(out) > 200:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                fields(v, p, depth + 1, out)
            elif p not in out:
                out.append(p)
    elif isinstance(obj, list) and obj:
        fields(obj[0], prefix + "[]", depth + 1, out)
    return out


def endpoint_id(method: str, tpath: str, used: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", tpath.replace("{", "").replace("}", "").lower()).strip("-") or "root"
    eid = (base if method == "GET" else f"{method.lower()}-{base}")[:40].strip("-")
    n, out = 2, eid
    while out in used:
        out = f"{eid[:36]}-{n}"
        n += 1
    used.add(out)
    return out


def build_service(calls: list, name: str, home: str) -> dict:
    """Aufzeichnung → Entwurf des Abschnitts "service" (gemeinsame Basisadresse, je Methode + Pfadmuster ein Endpunkt)."""
    if not calls:
        return {"name": name, "kind": "online", "home": home, "base": "", "auth": "none", "endpoints": []}
    origins = {}
    for c in calls:
        u = urllib.parse.urlsplit(c["url"])
        origins[f"{u.scheme}://{u.netloc}"] = origins.get(f"{u.scheme}://{u.netloc}", 0) + 1
    base = max(origins, key=origins.get)
    groups = {}
    for c in calls:
        u = urllib.parse.urlsplit(c["url"])
        if f"{u.scheme}://{u.netloc}" != base:
            continue
        tpath, _names = template_path(u.path)
        g = groups.setdefault((c["method"], tpath), {"params": {}, "fields": [], "status": set(), "n": 0})
        g["n"] += 1
        g["status"].add(c["status"])
        for k, v in (c.get("query") or {}).items():
            g["params"].setdefault(k, v)
        for f in c.get("fields") or []:
            if f not in g["fields"]:
                g["fields"].append(f)
    used, eps = set(), []
    for (method, tpath), g in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        note = ("Antwortfelder: " + ", ".join(g["fields"][:25]) + (" …" if len(g["fields"]) > 25 else "")) if g["fields"] else ""
        eps.append({"id": endpoint_id(method, tpath, used), "method": method, "path": tpath,
                    "label": f"{method} {tpath}", "status": "none", "note": note[:300],
                    "params": [{"name": k, "default": "" if v == "•••" else str(v)} for k, v in g["params"].items()
                               if re.match(r"^[A-Za-z_][A-Za-z0-9_.\[\]-]{0,40}$", k)],
                    "seen": g["n"]})
    return {"name": name, "kind": "online", "home": home, "base": base, "auth": "none",
            "note": f"Entwurf aus dem API-Rekorder ({time.strftime('%Y-%m-%d')}) – Nutzungsbedingungen prüfen, "
                    "Endpunkte im API-Tester bestätigen, dann Status setzen.",
            "endpoints": eps}


def record_response(method: str, url: str, status: int, req_headers: dict, post_data, body_text: str) -> dict | None:
    """Einen mitgelesenen Aufruf aufbereiten (nur JSON-Antworten). → Eintrag oder None"""
    try:
        data = json.loads(body_text)
    except (TypeError, ValueError):
        return None
    u = urllib.parse.urlsplit(url)
    body = None
    if post_data:
        try:
            body = redact(json.loads(post_data))
        except (TypeError, ValueError):
            body = "(kein JSON)"
    return {"method": method.upper(), "url": f"{u.scheme}://{u.netloc}{u.path}", "path": u.path,
            "query": safe_query(u.query), "status": status, "headers": safe_headers(req_headers), "body": body,
            "fields": fields(data), "example": redact(data)}


# =========================================================================== Aufnahme (Playwright)
def main(argv=None):
    ap = argparse.ArgumentParser(description="Schnittstellen einer Website mitlesen und als Plugin-Entwurf ausgeben.")
    ap.add_argument("url")
    ap.add_argument("--host", action="append", default=[], help="nur Aufrufe an diese(n) Host(s) aufzeichnen")
    ap.add_argument("--out", help="Ausgabeordner (Standard: ~/TagStudio/API-Aufnahmen/<host>)")
    ap.add_argument("--name", help="Name des Dienstes im Entwurf")
    ap.add_argument("--headless", action="store_true", help="ohne sichtbares Fenster (zusammen mit --seconds)")
    ap.add_argument("--seconds", type=float, default=0, help="nach so vielen Sekunden selbst beenden")
    a = ap.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright fehlt: pip install playwright (Chromium: python -m playwright install chromium)")
        return 2
    host = urllib.parse.urlsplit(a.url).netloc
    out = a.out or os.path.join(os.path.expanduser("~"), "TagStudio", "API-Aufnahmen", re.sub(r"[^\w.-]", "_", host))
    os.makedirs(out, exist_ok=True)
    print("Hinweis: Nur Schnittstellen aufzeichnen, die du nutzen darfst – Nutzungsbedingungen der Website beachten.")
    print("Browser öffnet sich. Klicke dich durch die Seite; zum Beenden den Browser schliessen.")
    calls = []

    def on_response(resp):
        try:
            req = resp.request
            if req.resource_type not in ("xhr", "fetch"):
                return
            if a.host and urllib.parse.urlsplit(req.url).netloc not in a.host:
                return
            if "json" not in (resp.headers.get("content-type") or ""):
                return
            e = record_response(req.method, req.url, resp.status, req.headers, req.post_data, resp.text())
            if e:
                calls.append(e)
                print(f"  {e['method']} {e['path']} → {e['status']}")
        except Exception as ex:  # noqa: BLE001 – eine Antwort darf die Aufnahme nicht abbrechen
            print(f"  (übersprungen: {ex})")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(a.headless))
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("response", on_response)
        page.goto(a.url)
        try:
            if a.seconds:
                page.wait_for_timeout(a.seconds * 1000)
            else:
                page.wait_for_event("close", timeout=0)
        except Exception:  # noqa: BLE001 – Browser geschlossen
            pass
        try:
            browser.close()
        except Exception:  # noqa: BLE001
            pass
    with open(os.path.join(out, "recording.json"), "w", encoding="utf-8") as fh:
        json.dump(calls, fh, ensure_ascii=False, indent=1)
    svc = build_service(calls, a.name or host, f"https://{host}")
    with open(os.path.join(out, "service.json"), "w", encoding="utf-8") as fh:
        json.dump(svc, fh, ensure_ascii=False, indent=2)
    print(f"{len(calls)} Aufrufe, {len(svc['endpoints'])} Endpunkte → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
