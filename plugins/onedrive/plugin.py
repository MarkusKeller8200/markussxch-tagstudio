"""OneDrive (#318, Cloud Weg 2): Abgleich über Microsoft Graph – Kontoart wählbar (#405, Entscheid User 29.10.2026).

- **Geschäfts-/Schulkonto:** App-Anbindung über Microsoft Graph (eigene Entra-App im Verzeichnis der Organisation),
  Endpunkt ``organizations`` bzw. das eingetragene Verzeichnis (Tenant-ID/Domain bei Apps für ein Verzeichnis).
- **Privates OneDrive:** keine App, keine Anmeldung – nur der OneDrive-Ordner des Desktop-Clients; dorthin gehen der
  Spiegel der Bibliothek (#403) und die Sicherung der Programmdaten (#402). ``cloud_folder(ctx)`` liefert den Ordner.

Eigene App in Microsoft Entra (Client-ID, C4), Anmeldung mit OAuth 2 und PKCE (öffentlicher Client, ohne Secret),
Berechtigung „Files.ReadWrite“ (laut Microsoft ohne Zustimmung des Administrators – eine Organisation kann die
Zustimmung durch Benutzer aber sperren) plus „User.Read“ und „offline_access“. TagStudio schreibt nur unter dem
gewählten Ordner (Standard „TagStudio“). Dateien bis 4 MB in einem Schritt, grössere über eine Upload-Sitzung.
Nur Standardbibliothek.
"""
import json
import os
import re
import urllib.parse

import cloudkit as ck
import oauthkit
import onlinematch as om

NAME = "OneDrive"
API = "https://graph.microsoft.com/v1.0"
INTERVALS = {"graph.microsoft.com": 0.1}
SIMPLE_MAX = 4 * 1024 * 1024
CHUNK = 320 * 1024 * 10                     # Upload-Sitzung: Vielfaches von 320 KiB
AUTH_BASE = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/"
CFG = {"name": NAME, "authorize": AUTH_BASE.format(tenant="organizations") + "authorize",
       "token": AUTH_BASE.format(tenant="organizations") + "token",
       "scopes": ["Files.ReadWrite", "User.Read", "offline_access"], "header": "Bearer", "secret": False,
       "redirect": "http://localhost:8767/callback"}
CONSENT = ("Bei einem Geschäfts- oder Schulkonto kann die Organisation die Zustimmung durch Benutzer gesperrt haben – "
           "dann muss ein Administrator die App in Microsoft Entra freigeben („Administratorzustimmung erteilen“).")
PERSONAL_HINT = ("Das ist ein privates Microsoft-Konto – dafür unter „Kontoart …“ „Privates OneDrive“ wählen "
                 "(Spiegel und Sicherung über den OneDrive-Ordner, ohne App).")
KINDS = ("business", "private")
_TENANT = re.compile(r"^(organizations|[0-9a-fA-F-]{36}|[A-Za-z0-9.-]{3,253})$")

LOGIN_ACTIONS = ck.login_actions(
    NAME, "Eigene App in Microsoft Entra anlegen (Verzeichnis deiner Organisation)",
    "1. Auf entra.microsoft.com › App-Registrierungen › „Neue Registrierung“ (im Verzeichnis deiner Organisation – "
    "dazu braucht es dort die Berechtigung bzw. einen Administrator): Name z. B. „TagStudio“, unterstützte Kontotypen "
    "„Nur Konten in diesem Organisationsverzeichnis“ (dann unter „Kontoart …“ die Verzeichnis-ID eintragen) oder "
    "„Konten in einem beliebigen Organisationsverzeichnis“. 2. Plattform „Mobile Anwendungen und Desktopanwendungen“ "
    "hinzufügen, Umleitungs-URI genau http://localhost/callback (der Port spielt bei localhost keine Rolle). "
    "3. Unter „Authentifizierung“ „Öffentliche Clientflows zulassen“ auf Ja. 4. API-Berechtigungen › Microsoft Graph › "
    "delegiert: Files.ReadWrite, User.Read, offline_access. 5. Die Anwendungs-ID (Client-ID) hier einfügen – ein Secret "
    "ist nicht nötig.",
    [["Microsoft Entra: App-Registrierungen", "https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"],
     ["Anleitung: App registrieren", "https://learn.microsoft.com/entra/identity-platform/quickstart-register-app"],
     ["Berechtigung Files.ReadWrite", "https://learn.microsoft.com/graph/permissions-reference#filesreadwrite"]],
    CFG["redirect"], note=CONSENT)
ACTIONS = LOGIN_ACTIONS                      # für ältere Aufrufer; die Liste je Kontoart liefert actions(ctx)


# =========================================================================== Kontoart (#405)
def _settings_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "einstellungen.json")


def suggest_folder() -> str:
    """Ordner des OneDrive-Desktop-Clients für private Konten (cloud.detect), sonst leer."""
    try:
        import cloud
        for r in cloud.detect():
            if r.get("provider") == "onedrive":
                return r["path"]
    except Exception:  # noqa: BLE001 – Erkennung ist nur ein Vorschlag
        pass
    return ""


def clean_tenant(v) -> str:
    v = str(v or "").strip() or "organizations"
    if v.lower() in ("common", "consumers") or not _TENANT.match(v):
        raise ValueError("Verzeichnis: „organizations“, eine Verzeichnis-ID (GUID) oder eine Domain (z. B. firma.ch).")
    return v


def load_settings(ctx) -> dict:
    """{"account": "business"|"private", "folder", "tenant"} – ohne gespeicherte Wahl immer „private“ (#412);
    eine gespeicherte App/Anmeldung bleibt erhalten und gilt wieder, sobald „Geschäftlich“ gewählt ist."""
    d = {}
    try:
        with open(_settings_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    kind = d.get("account")
    if kind not in KINDS:
        kind = "private"
    try:
        tenant = clean_tenant(d.get("tenant"))
    except ValueError:
        tenant = "organizations"
    return {"account": kind, "folder": str(d.get("folder") or ""), "tenant": tenant}


def save_settings(ctx, opts: dict) -> dict:
    cur = load_settings(ctx)
    kind = opts.get("account") if opts.get("account") in KINDS else cur["account"]
    folder = str(opts.get("folder") if opts.get("folder") is not None else cur["folder"]).strip()
    tenant = clean_tenant(opts.get("tenant") if opts.get("tenant") is not None else cur["tenant"])
    if kind == "private":
        if not folder:
            folder = suggest_folder()
        if not folder:
            raise ValueError("Bitte den OneDrive-Ordner angeben (der Ordner, den die OneDrive-App auf diesem Rechner "
                             "synchronisiert).")
        folder = os.path.abspath(os.path.expanduser(folder))
        if not os.path.isdir(folder):
            raise ValueError(f"Ordner nicht gefunden: {folder}")
    d = {"account": kind, "folder": folder, "tenant": tenant}
    os.makedirs(ctx.data_dir, exist_ok=True)
    tmp = _settings_path(ctx) + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _settings_path(ctx))
    return d


def is_private(ctx) -> bool:
    return load_settings(ctx)["account"] == "private"


def cloud_folder(ctx) -> str:
    """Kontoart „Privat“: der OneDrive-Ordner (vorhanden), sonst leer – Ziel für Spiegel und Sicherung."""
    st = load_settings(ctx)
    return st["folder"] if st["account"] == "private" and st["folder"] and os.path.isdir(st["folder"]) else ""


def _kind_action(ctx) -> dict:
    st = load_settings(ctx)
    return {"id": "settings", "label": "Kontoart …", "where": "page", "run_label": "Übernehmen", "needs_selection": False,
            "description": "Geschäfts-/Schulkonto: Abgleich über Microsoft Graph mit eigener App. Privates OneDrive: "
                           "keine App und keine Anmeldung – TagStudio nutzt nur den OneDrive-Ordner auf diesem Rechner "
                           "(Spiegel der Bibliothek und Sicherung der Programmdaten, Einstellungen › Cloud).",
            "options": [
                {"key": "account", "type": "select", "label": "Kontoart", "default": st["account"],
                 "choices": [["business", "Geschäfts- oder Schulkonto (App-Anbindung)"],
                             ["private", "Privates OneDrive (OneDrive-Ordner)"]]},
                {"key": "folder", "type": "folder", "label": "OneDrive-Ordner", "default": st["folder"] or suggest_folder(),
                 "show_if": {"account": "private"}},
                {"type": "info", "show_if": {"account": "private"},
                 "label": "Abo und Speichergrösse bestimmst du selbst – vor dem Spiegeln zeigt TagStudio, wie viel Platz "
                          "nötig ist. Den freien Platz in OneDrive kennt TagStudio ohne Anmeldung nicht."},
                {"key": "tenant", "type": "text", "label": "Verzeichnis (leer = „organizations“; Verzeichnis-ID oder Domain "
                                                          "bei einer App nur für deine Organisation)",
                 "default": "" if st["tenant"] == "organizations" else st["tenant"], "show_if": {"account": "business"}},
            ]}


def actions(ctx):
    test = {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
            "description": "Prüft die Einstellung: Ordner (privat) bzw. Anmeldung und Zugriff (geschäftlich).",
            "options": []}
    if is_private(ctx):
        return [_kind_action(ctx), test]
    return [_kind_action(ctx)] + LOGIN_ACTIONS


def app(ctx) -> oauthkit.App:
    for h, s in INTERVALS.items():
        om.INTERVALS.setdefault(h, s)
    tenant = load_settings(ctx)["tenant"]
    cfg = dict(CFG, authorize=AUTH_BASE.format(tenant=tenant) + "authorize", token=AUTH_BASE.format(tenant=tenant) + "token")
    return oauthkit.App(ctx, cfg)


def ready(ctx):
    if is_private(ctx):
        f = cloud_folder(ctx)
        return (False, f"privates OneDrive – kein Abgleich über die API; Spiegel und Sicherung in {f}" if f else
                "privates OneDrive – OneDrive-Ordner fehlt (Plugin OneDrive › „Kontoart …“)")
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
    hint = f" – {PERSONAL_HINT}" if d.get("driveType") == "personal" else ""
    return f"{who} ({kind}{free}){hint}"


def status(ctx):
    if is_private(ctx):
        f = cloud_folder(ctx)
        return f"privat – OneDrive-Ordner {f}" if f else "privat – OneDrive-Ordner fehlt („Kontoart …“)"
    ok, why = ready(ctx)
    return "geschäftlich, angemeldet – Abgleich in Einstellungen › Cloud" if ok else why


def check(ctx, cl=None):
    if is_private(ctx):
        f = cloud_folder(ctx)
        return (True, f"privates OneDrive, Ordner {f}") if f else (False, "OneDrive-Ordner fehlt („Kontoart …“)")
    ok, why = ready(ctx)
    return (True, account(ctx)) if ok else (False, why)


def _api_only(ctx):
    if is_private(ctx):
        raise ck.HttpError(-1, f"{NAME}: privates OneDrive – kein Abgleich über die API (Kontoart „Geschäftlich“ wählen).")


# =========================================================================== Abgleich (cloud_sync)
def cloud_list(ctx, folder) -> dict:
    """Alle Dateien unter folder (rekursiv) → {rel: {"rev", "size"}}; fehlt der Ordner → {}."""
    _api_only(ctx)
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
    _api_only(ctx)
    data = _req(ctx, "GET", f"{API}/me/drive/root:/{_p(path)}:/content", raw=True)
    if data is None:
        raise ck.HttpError(404, f"{NAME}: Datei fehlt ({path})")
    return data


def cloud_put(ctx, path, data: bytes) -> str:
    """Hochladen (legt fehlende Ordner an, ersetzt). → neue Revision (cTag)."""
    _api_only(ctx)
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
    _api_only(ctx)
    _req(ctx, "DELETE", f"{API}/me/drive/root:/{_p(path)}")


def run(action, ctx, files, opts):
    if action == "settings":
        try:
            d = save_settings(ctx, opts)
        except ValueError as ex:
            return {"message": f"{NAME}: {ex}"}
        if d["account"] == "private":
            return {"message": f"{NAME}: privates OneDrive – Ordner {d['folder']}. Spiegel und Sicherung unter "
                               "Einstellungen › Cloud einrichten; eine gespeicherte App-Anmeldung bleibt erhalten, wird "
                               "aber nicht benutzt."}
        return {"message": f"{NAME}: Geschäfts-/Schulkonto (Verzeichnis {d['tenant']}) – jetzt „Anmelden …“."}
    if action == "test" and is_private(ctx):
        ok, why = check(ctx)
        return {"message": f"{NAME}: {'in Ordnung – ' if ok else ''}{why}."}
    if is_private(ctx) and action in ("login", "logout"):
        if action == "logout":
            return ck.run_login(action, ctx, app(ctx), opts, NAME, account, CONSENT)
        return {"message": f"{NAME}: privates OneDrive braucht keine Anmeldung – zum Anmelden mit einem Geschäftskonto "
                           "unter „Kontoart …“ umstellen."}
    r = ck.run_login(action, ctx, app(ctx), opts, NAME, account, CONSENT)
    msg = str(r.get("message") or "")
    if any(k in msg for k in ("AADSTS50020", "AADSTS50194", "personal account", "persönlichen Konto")):
        r["message"] = msg + " " + PERSONAL_HINT
    return r
