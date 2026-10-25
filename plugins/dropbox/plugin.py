"""Dropbox (#320, Cloud Weg 2): Abgleich über die Dropbox API v2 (Entscheide C1–C4).

Eigene App in der Dropbox App Console (App-Key = Client-ID, empfohlen Zugriff „App folder“ – dann sieht TagStudio nur
„Apps/<App-Name>“), Anmeldung mit PKCE und Offline-Token (wird erneuert). Pfade beginnen bei der Wurzel der App bzw.
der Dropbox, Standard „TagStudio/…“. Nur Standardbibliothek.
"""
import json

import cloudkit as ck
import oauthkit
import onlinematch as om
from onlinematch import HttpError

NAME = "Dropbox"
API = "https://api.dropboxapi.com/2"
CONTENT = "https://content.dropboxapi.com/2"
INTERVALS = {"api.dropboxapi.com": 0.1, "content.dropboxapi.com": 0.1}
CFG = {"name": NAME, "authorize": "https://www.dropbox.com/oauth2/authorize", "token": "https://api.dropboxapi.com/oauth2/token",
       "scopes": ["account_info.read", "files.metadata.read", "files.content.read", "files.content.write"],
       "header": "Bearer", "secret": False, "auth_params": {"token_access_type": "offline"},
       "redirect": "http://127.0.0.1:8769/callback"}

ACTIONS = ck.login_actions(
    NAME, "Eigene App in der Dropbox App Console anlegen",
    "1. Auf dropbox.com/developers/apps „Create app“: „Scoped access“, Zugriff „App folder“ (empfohlen – TagStudio sieht "
    "dann nur seinen Ordner unter Apps), Name z. B. „TagStudio-DeinName“. 2. Unter „Permissions“ anhaken: "
    "account_info.read, files.metadata.read, files.content.read, files.content.write – „Submit“. 3. Unter „Settings“ bei "
    "„Redirect URIs“ genau http://127.0.0.1:8769/callback eintragen. 4. Den „App key“ hier als Client-ID einfügen – ein "
    "Secret ist nicht nötig (PKCE).",
    [["Dropbox App Console", "https://www.dropbox.com/developers/apps"],
     ["Anleitung: OAuth", "https://developers.dropbox.com/oauth-guide"]],
    CFG["redirect"])


def app(ctx) -> oauthkit.App:
    for h, s in INTERVALS.items():
        om.INTERVALS.setdefault(h, s)
    return oauthkit.App(ctx, CFG)


def ready(ctx):
    return ck.ready(app(ctx), NAME)


def auth(ctx):
    try:
        return {"headers": app(ctx).headers()}
    except oauthkit.OAuthError:
        return {}


def _rpc(ctx, path: str, body):
    return ck.request(app(ctx), "POST", API + path, json.dumps(body).encode("utf-8") if body is not None else b"null",
                      {"Content-Type": "application/json"}, NAME)


def _dp(path: str) -> str:
    p = ck.clean_path(path)
    return "/" + p if p else ""


def account(ctx) -> str:
    a = _rpc(ctx, "/users/get_current_account", None) or {}
    name = (a.get("name") or {}).get("display_name") or a.get("email") or "?"
    try:
        s = _rpc(ctx, "/users/get_space_usage", None) or {}
        alloc = (s.get("allocation") or {}).get("allocated") or 0
        free = f", frei {round((alloc - (s.get('used') or 0)) / 1e9, 1)} GB" if alloc else ""
    except HttpError:
        free = ""
    return f"{name}{free}"


def status(ctx):
    ok, why = ready(ctx)
    return "angemeldet – Abgleich in Einstellungen › Speicherort und Ordner" if ok else why


def check(ctx, cl=None):
    ok, why = ready(ctx)
    return (True, account(ctx)) if ok else (False, why)


# =========================================================================== Abgleich (cloud_sync)
def cloud_list(ctx, folder) -> dict:
    base = _dp(folder)
    try:
        d = _rpc(ctx, "/files/list_folder", {"path": base, "recursive": True, "include_deleted": False})
    except HttpError as ex:
        if ex.status == 409:                       # path/not_found: Ordner gibt es noch nicht
            return {}
        raise
    out = {}
    pre = base.lower() + "/"
    while d:
        for e in d.get("entries") or []:
            if e.get(".tag") != "file":
                continue
            low = e.get("path_lower") or ""
            if not low.startswith(pre):
                continue
            disp = e.get("path_display") or low
            out[disp[len(pre):]] = {"rev": e.get("rev") or e.get("content_hash") or "", "size": e.get("size", 0)}
        if not d.get("has_more"):
            break
        d = _rpc(ctx, "/files/list_folder/continue", {"cursor": d.get("cursor")})
    return out


def cloud_get(ctx, path) -> bytes:
    data = ck.request(app(ctx), "POST", CONTENT + "/files/download", b"",
                      {"Dropbox-API-Arg": json.dumps({"path": _dp(path)}), "Content-Type": "text/plain; charset=dropbox-cors-hack"}, NAME, raw=True)
    if data is None:
        raise HttpError(404, f"{NAME}: Datei fehlt ({path})")
    return data


def cloud_put(ctx, path, data: bytes) -> str:
    arg = {"path": _dp(path), "mode": "overwrite", "autorename": False, "mute": True}
    d = ck.request(app(ctx), "POST", CONTENT + "/files/upload", data,
                   {"Dropbox-API-Arg": json.dumps(arg), "Content-Type": "application/octet-stream"}, NAME) or {}
    return d.get("rev") or d.get("content_hash") or ""


def cloud_delete(ctx, path):
    """Löschen (Dropbox bewahrt gelöschte Dateien eine Zeit lang auf) – nur nach Rückfrage in der Oberfläche."""
    _rpc(ctx, "/files/delete_v2", {"path": _dp(path)})


def run(action, ctx, files, opts):
    return ck.run_login(action, ctx, app(ctx), opts, NAME, account)
