"""MarKusSXCH TagStudio – gemeinsame Werkzeuge der Cloud-Plugins (#318 OneDrive, #319 Google Drive, #320 Dropbox).

Anfragen mit dem OAuth-Token des Plugins (``oauthkit.App``), einmal erneuern bei 401, gemeinsame Drosselung je Host.
Bei Grenzen (HTTP 429, Kontingent) wird **nicht** wiederholt, sondern gemeldet (Konzept Cloud, Grundsätze). Abruf über
``onlinematch.http_request`` – in Tests an einer Stelle ersetzbar. Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import urllib.parse

import onlinematch as om
from onlinematch import HttpError
import servicekit as sk


def request(app, method: str, url: str, data: bytes | None = None, headers: dict | None = None, name: str = "",
            raw: bool = False, auth: bool = True):
    """Eine Anfrage → JSON (bzw. Bytes mit raw=True, None bei 404). Fehler als HttpError mit verständlichem Text."""
    host = urllib.parse.urlparse(url).netloc
    for attempt in (0, 1):
        h = {"User-Agent": sk.USER_AGENT, **(headers or {})}
        if auth:
            h.update(app.headers())
        cancel = getattr(app.ctx, "check_cancel", None)
        if callable(cancel):
            cancel()
        om.SHARED.wait(host)
        st, hd, body = om.http_request(method, url, h, data)
        if st == 401 and auth and attempt == 0 and app.refresh():
            continue
        break
    if st == 404:
        return None
    if st == 0 or st >= 400:
        raise HttpError(st, error_text(name or host, st, body, hd))
    if raw:
        return body
    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as ex:
        raise HttpError(-1, f"{name or host}: unerwartete Antwort") from ex


def error_text(name: str, st: int, body: bytes, headers: dict | None = None) -> str:
    msg = ""
    try:
        d = json.loads((body or b"{}").decode("utf-8"))
        e = d.get("error") if isinstance(d, dict) else None
        if isinstance(e, dict):
            msg = str(e.get("message") or e.get(".tag") or e.get("code") or "")
        elif e:
            msg = str(d.get("error_summary") or d.get("error_description") or e)
    except (UnicodeDecodeError, ValueError, AttributeError):
        pass
    base = {401: "nicht angemeldet bzw. Anmeldung abgelaufen – bitte neu anmelden",
            403: "kein Zugriff (Berechtigung, Kontingent oder Zustimmung des Administrators)",
            429: "zu viele Anfragen bzw. Kontingent erreicht – nicht wiederholt, später erneut abgleichen",
            507: "Speicherplatz im Dienst voll"}.get(st, f"HTTP {st}" if st else "keine Verbindung")
    return f"{name}: {base}" + (f" ({msg[:160]})" if msg else "")


def clean_path(path: str) -> str:
    """„TagStudio/Playlists/x.m3u8“ – ohne führenden Schrägstrich, ohne „..“."""
    parts = [p for p in str(path or "").replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"Ungültiger Pfad: {path}")
    return "/".join(parts)


# =========================================================================== Anmelden (gemeinsam für die Cloud-Plugins)
def login_actions(name: str, info_title: str, info_label: str, links: list, redirect: str, secret: bool = False,
                  note: str = "") -> list:
    """Aktionen „Anmelden …“, „Abmelden …“, „Verbindung testen“ eines Cloud-Plugins (eigene App je Dienst, C4)."""
    opts = [{"type": "info", "title": info_title, "label": info_label, "links": links}]
    if note:
        opts.append({"type": "info", "label": note})
    opts.append({"key": "client_id", "type": "password", "label": "Client-ID"})
    if secret:
        opts.append({"key": "client_secret", "type": "password", "label": "Client-Secret"})
    opts += [{"key": "redirect", "type": "text", "label": "Redirect URI (wie in deiner App eingetragen)", "default": redirect},
             {"key": "method", "type": "select", "label": "Methode",
              "choices": [["browser", "Im Browser anmelden (automatisch)"], ["paste", "Adresse einfügen (wenn automatisch nicht geht)"]],
              "default": "browser"},
             {"key": "url", "type": "text", "label": "Adresse aus der Adresszeile nach der Anmeldung", "show_if": {"method": "paste"}},
             {"type": "info", "show_if": {"method": "paste"},
              "label": "Zuerst ohne Adresse „Anmelden“ – der Browser öffnet die Anmeldung. Nach der Zustimmung zeigt der "
                       "Browser eine Fehlerseite mit der Rückleitungs-Adresse in der Adresszeile: diese Adresse kopieren, "
                       "hier einfügen und nochmals „Anmelden“."}]
    return [
        {"id": "login", "label": "Anmelden …", "where": "page", "run_label": "Anmelden", "needs_selection": False,
         "description": f"Zugangsdaten deiner eigenen {name}-App eintragen (leer = unverändert, verschlüsselt gespeichert) "
                        "und im Browser anmelden. TagStudio schreibt nur in seinen eigenen Ordner (Standard „TagStudio“).",
         "options": opts},
        {"id": "logout", "label": "Abmelden …", "where": "page", "run_label": "Abmelden", "needs_selection": False,
         "description": "Gespeicherte Anmeldung löschen.",
         "options": [{"key": "clear", "type": "check", "label": "Auch die Zugangsdaten der App löschen", "default": False}]},
        {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
         "description": f"Prüft Anmeldung und Zugriff bei {name} und zeigt Konto und Ordner „TagStudio“.", "options": []},
    ]


def ready(app, name: str):
    if not app.configured():
        return False, f"keine Client-ID (Plugin {name} › „Anmelden …“)"
    if not app.logged_in():
        return False, f"nicht angemeldet (Plugin {name} › „Anmelden …“)"
    return True, ""


def run_login(action, ctx, app, opts, name: str, account, consent_hint: str = ""):
    """Gemeinsamer Ablauf der Aktionen; account(ctx) → Text zum Konto (für „Testen“ und nach der Anmeldung)."""
    import oauthkit
    try:
        if action == "logout":
            app.logout()
            if opts.get("clear"):
                app.save_credentials({"clear": True})
            return {"message": "Abgemeldet."}
        if action == "login":
            app.save_credentials({k: opts.get(k) for k in ("client_id", "client_secret", "redirect")})
            if not app.configured():
                return {"message": f"Bitte die Zugangsdaten deiner {name}-App eintragen."}
            if opts.get("method") == "paste":
                if not (opts.get("url") or "").strip():
                    url = app.auth_url()
                    if not oauthkit.open_browser(url):
                        ctx.log(f"Diese Adresse im Browser öffnen: {url}")
                    return {"message": f"{name} ist im Browser geöffnet. Nach der Zustimmung die Adresse aus der "
                                       "Adresszeile kopieren, hier einfügen und nochmals „Anmelden“."}
                app.finish(opts["url"])
            else:
                app.login_browser()
            return {"message": f"Bei {name} angemeldet: {account(ctx)}."}
        if action == "test":
            ok, why = ready(app, name)
            if not ok:
                return {"message": f"{name}: {why}."}
            return {"message": f"{name}: in Ordnung – {account(ctx)}."}
    except (oauthkit.OAuthError, HttpError) as ex:
        txt = str(ex)
        if consent_hint and any(k in txt for k in ("AADSTS65001", "AADSTS90094", "consent", "admin")):
            txt += " " + consent_hint
        return {"message": f"{name}: {txt}"}
    raise ValueError(f"Unbekannte Aktion: {action}")
