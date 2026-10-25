"""OneDrive (#318, Cloud Weg 2): Abgleich über Microsoft Graph – privat und geschäftlich (Entscheide C1–C4).

Eigene App in Microsoft Entra (Client-ID, C4), Anmeldung mit OAuth 2 und PKCE (öffentlicher Client, ohne Secret),
Berechtigung „Files.ReadWrite“ (laut Microsoft ohne Zustimmung des Administrators – eine Organisation kann die
Zustimmung durch Benutzer aber sperren) plus „User.Read“ und „offline_access“. TagStudio schreibt nur unter dem
gewählten Ordner (Standard „TagStudio“). Dateien bis 4 MB in einem Schritt, grössere über eine Upload-Sitzung.
Nur Standardbibliothek.
"""
import urllib.parse

import cloudkit as ck
import oauthkit
import onlinematch as om

NAME = "OneDrive"
API = "https://graph.microsoft.com/v1.0"
INTERVALS = {"graph.microsoft.com": 0.1}
SIMPLE_MAX = 4 * 1024 * 1024
CHUNK = 320 * 1024 * 10                     # Upload-Sitzung: Vielfaches von 320 KiB
CFG = {"name": NAME, "authorize": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
       "token": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
       "scopes": ["Files.ReadWrite", "User.Read", "offline_access"], "header": "Bearer", "secret": False,
       "redirect": "http://localhost:8767/callback"}
CONSENT = ("Bei einem Geschäfts- oder Schulkonto kann die Organisation die Zustimmung durch Benutzer gesperrt haben – "
           "dann muss ein Administrator die App in Microsoft Entra freigeben („Administratorzustimmung erteilen“).")

ACTIONS = ck.login_actions(
    NAME, "Eigene App in Microsoft Entra anlegen",
    "1. Auf entra.microsoft.com (bzw. portal.azure.com) › App-Registrierungen › „Neue Registrierung“: Name z. B. "
    "„TagStudio“, unterstützte Kontotypen „Konten in einem beliebigen Organisationsverzeichnis und persönliche "
    "Microsoft-Konten“. 2. Plattform „Mobile Anwendungen und Desktopanwendungen“ hinzufügen, Umleitungs-URI genau "
    "http://localhost/callback (der Port spielt bei localhost keine Rolle). 3. Unter „Authentifizierung“ „Öffentliche "
    "Clientflows zulassen“ auf Ja. 4. API-Berechtigungen › Microsoft Graph › delegiert: Files.ReadWrite, User.Read, "
    "offline_access. 5. Die Anwendungs-ID (Client-ID) hier einfügen – ein Secret ist nicht nötig.",
    [["Microsoft Entra: App-Registrierungen", "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"],
     ["Anleitung: App registrieren", "https://learn.microsoft.com/entra/identity-platform/quickstart-register-app"],
     ["Berechtigung Files.ReadWrite", "https://learn.microsoft.com/graph/permissions-reference#filesreadwrite"]],
    CFG["redirect"], note=CONSENT)


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


def _p(path: str) -> str:
    return urllib.parse.quote(ck.clean_path(path), safe="/")


def _req(ctx, method, url, data=None, headers=None, raw=False):
    return ck.request(app(ctx), method, url, data, headers, NAME, raw)


def account(ctx) -> str:
    d = _req(ctx, "GET", f"{API}/me/drive?$select=driveType,owner,quota") or {}
    who = ((d.get("owner") or {}).get("user") or {}).get("displayName") or "?"
    kind = {"personal": "privat", "business": "geschäftlich", "documentLibrary": "SharePoint"}.get(d.get("driveType"), d.get("driveType", "?"))
    q = d.get("quota") or {}
    free = f", frei {round((q.get('remaining') or 0) / 1e9, 1)} GB" if q.get("remaining") is not None else ""
    return f"{who} ({kind}{free})"


def status(ctx):
    ok, why = ready(ctx)
    return "angemeldet – Abgleich in Einstellungen › Speicherort und Ordner" if ok else why


def check(ctx, cl=None):
    ok, why = ready(ctx)
    return (True, account(ctx)) if ok else (False, why)


# =========================================================================== Abgleich (cloud_sync)
def cloud_list(ctx, folder) -> dict:
    """Alle Dateien unter folder (rekursiv) → {rel: {"rev", "size"}}; fehlt der Ordner → {}."""
    out = {}

    def walk(path, rel):
        url = f"{API}/me/drive/root:/{_p(path)}:/children?$select=name,cTag,eTag,size,file,folder&$top=200"
        while url:
            d = _req(ctx, "GET", url)
            if d is None:
                return
            for it in d.get("value") or []:
                name = it.get("name") or ""
                if not name:
                    continue
                if "folder" in it:
                    walk(f"{path}/{name}", f"{rel}{name}/")
                elif "file" in it:
                    out[rel + name] = {"rev": it.get("cTag") or it.get("eTag") or "", "size": it.get("size", 0)}
            url = d.get("@odata.nextLink")
    walk(folder, "")
    return out


def cloud_get(ctx, path) -> bytes:
    data = _req(ctx, "GET", f"{API}/me/drive/root:/{_p(path)}:/content", raw=True)
    if data is None:
        raise ck.HttpError(404, f"{NAME}: Datei fehlt ({path})")
    return data


def cloud_put(ctx, path, data: bytes) -> str:
    """Hochladen (legt fehlende Ordner an, ersetzt). → neue Revision (cTag)."""
    if len(data) <= SIMPLE_MAX:
        it = _req(ctx, "PUT", f"{API}/me/drive/root:/{_p(path)}:/content", data, {"Content-Type": "application/octet-stream"}) or {}
        return it.get("cTag") or it.get("eTag") or ""
    import json
    s = _req(ctx, "POST", f"{API}/me/drive/root:/{_p(path)}:/createUploadSession",
             json.dumps({"item": {"@microsoft.graph.conflictBehavior": "replace"}}).encode(), {"Content-Type": "application/json"}) or {}
    up = s.get("uploadUrl")
    if not up:
        raise ck.HttpError(-1, f"{NAME}: keine Upload-Sitzung erhalten")
    it = {}
    for start in range(0, len(data), CHUNK):
        part = data[start:start + CHUNK]
        st, _h, body = om.http_request("PUT", up, {"Content-Range": f"bytes {start}-{start + len(part) - 1}/{len(data)}",
                                                    "Content-Length": str(len(part))}, part)   # ohne Token (Adresse genügt)
        if st >= 400 or st == 0:
            raise ck.HttpError(st, ck.error_text(NAME, st, body))
        if st in (200, 201) and body:
            it = json.loads(body.decode("utf-8"))
    return it.get("cTag") or it.get("eTag") or ""


def cloud_delete(ctx, path):
    """Löschen (OneDrive legt die Datei in den Papierkorb) – nur nach Rückfrage in der Oberfläche."""
    _req(ctx, "DELETE", f"{API}/me/drive/root:/{_p(path)}")


def run(action, ctx, files, opts):
    return ck.run_login(action, ctx, app(ctx), opts, NAME, account, CONSENT)
