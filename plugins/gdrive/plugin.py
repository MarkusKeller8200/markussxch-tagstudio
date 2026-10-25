"""Google Drive (#319, Cloud Weg 2): Abgleich über die Drive API v3 (Entscheide C1–C4).

Eigene OAuth-App (Typ „Desktop-App“) in der Google Cloud Console mit Client-ID und Client-Secret (bei Desktop-Apps
kein echtes Geheimnis, wird trotzdem verschlüsselt gespeichert), Anmeldung mit PKCE, Bereich **drive.file**: TagStudio
sieht nur Dateien und Ordner, die es selbst angelegt hat – nichts anderes in deinem Drive. Drive kennt keine Pfade,
darum werden Ordner über Name und übergeordneten Ordner gesucht bzw. angelegt. Löschen = in den Papierkorb.
Nur Standardbibliothek.
"""
import json
import urllib.parse
import uuid

import cloudkit as ck
import oauthkit
import onlinematch as om

NAME = "Google Drive"
API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3"
FOLDER = "application/vnd.google-apps.folder"
INTERVALS = {"www.googleapis.com": 0.1}
CFG = {"name": NAME, "authorize": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
       "scopes": ["https://www.googleapis.com/auth/drive.file"], "header": "Bearer", "secret": True,
       "auth_params": {"access_type": "offline", "prompt": "consent"}, "redirect": "http://127.0.0.1:8768/callback"}

ACTIONS = ck.login_actions(
    NAME, "Eigene Desktop-App in der Google Cloud Console anlegen",
    "1. Auf console.cloud.google.com ein Projekt anlegen und die „Google Drive API“ aktivieren. 2. OAuth-Zustimmungsbildschirm "
    "einrichten (Typ „Extern“, dich selbst als Testnutzer eintragen), Bereich …/auth/drive.file. 3. Anmeldedaten › "
    "„OAuth-Client-ID erstellen“ › Anwendungstyp „Desktop-App“. 4. Client-ID und Client-Secret hier einfügen – die "
    "Rückleitung auf http://127.0.0.1 erlaubt Google bei Desktop-Apps ohne Eintrag. TagStudio sieht nur, was es selbst "
    "in Drive anlegt.",
    [["Google Cloud Console: Anmeldedaten", "https://console.cloud.google.com/apis/credentials"],
     ["Drive API aktivieren", "https://console.cloud.google.com/apis/library/drive.googleapis.com"],
     ["Anleitung: Desktop-App", "https://developers.google.com/identity/protocols/oauth2/native-app"]],
    CFG["redirect"], secret=True)

_IDS: dict = {}                          # Pfad → Datei-/Ordner-ID (je Sitzung)


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


def _req(ctx, method, url, data=None, headers=None, raw=False):
    return ck.request(app(ctx), method, url, data, headers, NAME, raw)


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


def account(ctx) -> str:
    d = _req(ctx, "GET", f"{API}/about?fields=user,storageQuota") or {}
    u = d.get("user") or {}
    q = d.get("storageQuota") or {}
    free = ""
    if q.get("limit") and q.get("usage"):
        free = f", frei {round((int(q['limit']) - int(q['usage'])) / 1e9, 1)} GB"
    return f"{u.get('displayName') or u.get('emailAddress') or '?'}{free}"


def status(ctx):
    ok, why = ready(ctx)
    return "angemeldet – Abgleich in Einstellungen › Speicherort und Ordner" if ok else why


def check(ctx, cl=None):
    ok, why = ready(ctx)
    return (True, account(ctx)) if ok else (False, why)


def _children(ctx, parent: str) -> list:
    out, token = [], ""
    while True:
        params = {"q": f"'{_q(parent)}' in parents and trashed = false", "pageSize": "1000",
                  "fields": "nextPageToken,files(id,name,mimeType,md5Checksum,version,size)", "spaces": "drive"}
        if token:
            params["pageToken"] = token
        d = _req(ctx, "GET", f"{API}/files?" + urllib.parse.urlencode(params)) or {}
        out += d.get("files") or []
        token = d.get("nextPageToken")
        if not token:
            return out


def _find(ctx, parent: str, name: str, folder: bool):
    q = f"'{_q(parent)}' in parents and name = '{_q(name)}' and trashed = false and mimeType " + ("=" if folder else "!=") + f" '{FOLDER}'"
    d = _req(ctx, "GET", f"{API}/files?" + urllib.parse.urlencode({"q": q, "fields": "files(id,md5Checksum,version)", "spaces": "drive"})) or {}
    f = d.get("files") or []
    return f[0]["id"] if f else None


def _folder(ctx, path: str, create: bool):
    path = ck.clean_path(path)
    if not path:
        return "root"
    if path in _IDS:
        return _IDS[path]
    parent = "root"
    acc = []
    for part in path.split("/"):
        acc.append(part)
        key = "/".join(acc)
        fid = _IDS.get(key) or _find(ctx, parent, part, True)
        if not fid:
            if not create:
                return None
            d = _req(ctx, "POST", f"{API}/files?fields=id", json.dumps({"name": part, "mimeType": FOLDER, "parents": [parent]}).encode(),
                     {"Content-Type": "application/json"}) or {}
            fid = d.get("id")
            if not fid:
                raise ck.HttpError(-1, f"{NAME}: Ordner „{part}“ konnte nicht angelegt werden")
        _IDS[key] = fid
        parent = fid
    return parent


def _file_id(ctx, path: str):
    path = ck.clean_path(path)
    if path in _IDS:
        return _IDS[path]
    folder, _, name = path.rpartition("/")
    parent = _folder(ctx, folder, False)
    fid = _find(ctx, parent, name, False) if parent else None
    if fid:
        _IDS[path] = fid
    return fid


# =========================================================================== Abgleich (cloud_sync)
def cloud_list(ctx, folder) -> dict:
    root = _folder(ctx, folder, False)
    out = {}
    if not root:
        return out
    base = ck.clean_path(folder)

    def walk(fid, rel):
        for f in _children(ctx, fid):
            name = f.get("name") or ""
            if not name:
                continue
            if f.get("mimeType") == FOLDER:
                _IDS[f"{base}/{rel}{name}"] = f["id"]
                walk(f["id"], f"{rel}{name}/")
            elif not f.get("mimeType", "").startswith("application/vnd.google-apps."):       # Google-Dokumente auslassen
                _IDS[f"{base}/{rel}{name}"] = f["id"]
                out[rel + name] = {"rev": f.get("md5Checksum") or f.get("version") or "", "size": int(f.get("size") or 0)}
    walk(root, "")
    return out


def cloud_get(ctx, path) -> bytes:
    fid = _file_id(ctx, path)
    data = _req(ctx, "GET", f"{API}/files/{fid}?alt=media", raw=True) if fid else None
    if data is None:
        raise ck.HttpError(404, f"{NAME}: Datei fehlt ({path})")
    return data


def cloud_put(ctx, path, data: bytes) -> str:
    path = ck.clean_path(path)
    fid = _file_id(ctx, path)
    if fid:
        d = _req(ctx, "PATCH", f"{UPLOAD}/files/{fid}?uploadType=media&fields=id,md5Checksum,version", data,
                 {"Content-Type": "application/octet-stream"}) or {}
    else:
        folder, _, name = path.rpartition("/")
        parent = _folder(ctx, folder, True)
        b = "ts" + uuid.uuid4().hex
        meta = json.dumps({"name": name, "parents": [parent]}).encode("utf-8")
        body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n").encode() + meta + \
            (f"\r\n--{b}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{b}--\r\n".encode()
        d = _req(ctx, "POST", f"{UPLOAD}/files?uploadType=multipart&fields=id,md5Checksum,version", body,
                 {"Content-Type": f"multipart/related; boundary={b}"}) or {}
        if d.get("id"):
            _IDS[path] = d["id"]
    return d.get("md5Checksum") or d.get("version") or ""


def cloud_delete(ctx, path):
    """In den Papierkorb von Google Drive – nur nach Rückfrage in der Oberfläche."""
    fid = _file_id(ctx, path)
    if fid:
        _req(ctx, "PATCH", f"{API}/files/{fid}?fields=id", json.dumps({"trashed": True}).encode(), {"Content-Type": "application/json"})
        _IDS.pop(ck.clean_path(path), None)


def run(action, ctx, files, opts):
    return ck.run_login(action, ctx, app(ctx), opts, NAME, account)
