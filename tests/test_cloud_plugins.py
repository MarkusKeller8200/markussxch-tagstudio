"""#318–#320: Cloud-Plugins OneDrive, Google Drive, Dropbox mit nachgebauten Diensten (kein Netz) – Auflisten, Hoch-,
Herunterladen, Löschen, Abgleich über cloudsync, Anmelde-Adresse, 429 ohne Wiederholung."""
import hashlib
import json
import os
import re
import time
import urllib.parse

from test_tagger_tools import Base

import cloudsync
import onlinematch

TOKEN = "AT-geheim"


class FakeGraph:
    def __init__(self):
        self.files, self.calls, self.n, self.sessions, self.status = {}, [], 0, {}, None

    def __call__(self, method, url, headers, data=None):
        u = urllib.parse.urlparse(url)
        self.calls.append((method, u.netloc, u.path, dict(headers or {})))
        if self.status:
            return self.status, {}, b'{"error":{"code":"tooManyRequests","message":"slow down"}}'
        if u.netloc == "up.example":
            buf = self.sessions[u.path]
            m = re.match(r"bytes (\d+)-(\d+)/(\d+)", headers["Content-Range"])
            buf["data"] += data
            if int(m.group(2)) + 1 == int(m.group(3)):
                return self._store(buf["path"], buf["data"], 201)
            return 202, {}, b'{"nextExpectedRanges":[]}'
        assert headers.get("Authorization") == f"Bearer {TOKEN}", headers
        p = urllib.parse.unquote(u.path)
        if p == "/v1.0/me/drive":
            return 200, {}, json.dumps({"driveType": "personal", "owner": {"user": {"displayName": "Markus"}},
                                        "quota": {"remaining": 5e9}}).encode()
        m = re.match(r"^/v1\.0/me/drive/root:/(.*?):/(children|content|createUploadSession)$", p)
        if m:
            path, what = m.group(1), m.group(2)
            if what == "children" and method == "GET":
                pre = path + "/"
                kids = {}
                for k in self.files:
                    if k.startswith(pre):
                        rest = k[len(pre):]
                        name = rest.split("/")[0]
                        kids[name] = "/" in rest
                if not kids:
                    return 404, {}, b'{"error":{"code":"itemNotFound"}}'
                vals = [{"name": n, "folder": {}} if isdir else {"name": n, "file": {}, "cTag": self.files[f"{pre}{n}"][0],
                                                                   "size": len(self.files[f"{pre}{n}"][1])} for n, isdir in kids.items()]
                return 200, {}, json.dumps({"value": vals}).encode()
            if what == "content" and method == "GET":
                return (200, {}, self.files[path][1]) if path in self.files else (404, {}, b"")
            if what == "content" and method == "PUT":
                return self._store(path, data, 201)
            if what == "createUploadSession":
                key = f"/sess/{len(self.sessions)}"
                self.sessions[key] = {"path": path, "data": b""}
                return 200, {}, json.dumps({"uploadUrl": f"https://up.example{key}"}).encode()
        m = re.match(r"^/v1\.0/me/drive/root:/(.*)$", p)
        if m and method == "DELETE":
            self.files.pop(m.group(1), None)
            return 204, {}, b""
        return 404, {}, b"{}"

    def _store(self, path, data, st):
        self.n += 1
        self.files[path] = (f"c{self.n}", data)
        return st, {}, json.dumps({"name": path.rsplit("/", 1)[-1], "cTag": f"c{self.n}", "file": {}}).encode()


class FakeGoogle:
    FOLDER = "application/vnd.google-apps.folder"

    def __init__(self):
        self.items, self.calls, self.n = {}, [], 0

    def _new(self, name, parent, mime, data=b""):
        self.n += 1
        fid = f"id{self.n}"
        self.items[fid] = {"id": fid, "name": name, "parent": parent, "mimeType": mime, "data": data, "trashed": False,
                           "md5Checksum": hashlib.md5(data).hexdigest() if mime != self.FOLDER else None, "version": str(self.n)}
        return self.items[fid]

    def _pub(self, it):
        d = {k: it[k] for k in ("id", "name", "mimeType", "version")}
        if it["mimeType"] != self.FOLDER:
            d.update(md5Checksum=it["md5Checksum"], size=str(len(it["data"])))
        return d

    def __call__(self, method, url, headers, data=None):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        self.calls.append((method, u.path, q))
        assert headers.get("Authorization") == f"Bearer {TOKEN}"
        if u.path == "/drive/v3/about":
            return 200, {}, json.dumps({"user": {"displayName": "Markus"}}).encode()
        if u.path == "/drive/v3/files" and method == "GET":
            m = re.match(r"'(.+?)' in parents and (?:name = '(.+?)' and )?trashed = false(?: and mimeType (=|!=) '(.+)')?", q["q"])
            parent, name, op, mime = m.groups()
            res = [i for i in self.items.values() if i["parent"] == parent and not i["trashed"] and (name is None or i["name"] == name)
                   and (op is None or (i["mimeType"] == mime) == (op == "="))]
            return 200, {}, json.dumps({"files": [self._pub(i) for i in res]}).encode()
        if u.path == "/drive/v3/files" and method == "POST":
            b = json.loads(data)
            return 200, {}, json.dumps({"id": self._new(b["name"], b["parents"][0], b["mimeType"])["id"]}).encode()
        m = re.match(r"^/drive/v3/files/(\w+)$", u.path)
        if m and method == "GET" and q.get("alt") == "media":
            return 200, {}, self.items[m.group(1)]["data"]
        if m and method == "PATCH":
            self.items[m.group(1)].update(json.loads(data))
            return 200, {}, b"{}"
        if u.path == "/upload/drive/v3/files" and method == "POST":
            b = headers["Content-Type"].split("boundary=")[1]
            parts = data.split(f"--{b}".encode())
            meta = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n"))
            content = parts[2].split(b"\r\n\r\n", 1)[1][:-2]
            it = self._new(meta["name"], meta["parents"][0], "application/octet-stream", content)
            return 200, {}, json.dumps(self._pub(it)).encode()
        m = re.match(r"^/upload/drive/v3/files/(\w+)$", u.path)
        if m and method == "PATCH":
            it = self.items[m.group(1)]
            self.n += 1
            it.update(data=data, md5Checksum=hashlib.md5(data).hexdigest(), version=str(self.n))
            return 200, {}, json.dumps(self._pub(it)).encode()
        return 404, {}, b"{}"


class FakeDropbox:
    def __init__(self):
        self.files, self.calls, self.n = {}, [], 0

    def __call__(self, method, url, headers, data=None):
        u = urllib.parse.urlparse(url)
        self.calls.append((method, u.netloc, u.path, dict(headers or {})))
        assert headers.get("Authorization") == f"Bearer {TOKEN}"
        js = lambda d, st=200: (st, {}, json.dumps(d).encode())          # noqa: E731
        if u.path == "/2/users/get_current_account":
            return js({"name": {"display_name": "Markus"}})
        if u.path == "/2/users/get_space_usage":
            return js({"used": 1e9, "allocation": {"allocated": 2e9}})
        if u.path == "/2/files/list_folder":
            base = json.loads(data)["path"].lower()
            ents = [{".tag": "file", "path_lower": k, "path_display": v[0], "rev": v[1], "size": len(v[2])}
                    for k, v in self.files.items() if k.startswith(base + "/")]
            return js({"entries": ents, "has_more": False, "cursor": "c"}) if ents else js({"error_summary": "path/not_found/"}, 409)
        if u.path == "/2/files/upload":
            arg = json.loads(headers["Dropbox-API-Arg"])
            self.n += 1
            self.files[arg["path"].lower()] = (arg["path"], f"r{self.n}", data)
            return js({"rev": f"r{self.n}"})
        if u.path == "/2/files/download":
            arg = json.loads(headers["Dropbox-API-Arg"])
            f = self.files.get(arg["path"].lower())
            return (200, {}, f[2]) if f else js({"error_summary": "path/not_found/"}, 409)
        if u.path == "/2/files/delete_v2":
            self.files.pop(json.loads(data)["path"].lower(), None)
            return js({})
        return 404, {}, b"{}"


class TestCloudPlugins(Base):
    def setUp(self):
        super().setUp()
        from session import Session
        self.s = Session()
        self._orig = onlinematch.http_request
        self.addCleanup(setattr, onlinematch, "http_request", self._orig)
        self._iv = dict(onlinematch.INTERVALS)
        self.addCleanup(onlinematch.INTERVALS.update, self._iv)

    def login(self, pid):
        import plugins
        p = self.s.plugins.get(pid)
        mod = p.load()
        self.assertIsNotNone(mod, p.error)
        ctx = plugins.Context(p)
        a = mod.app(ctx)
        a.save_credentials({"client_id": "CID", "client_secret": "SEC"})
        a._save(token=json.dumps({"access_token": TOKEN, "refresh_token": "RT", "expires_at": time.time() + 3600}))
        for h in mod.INTERVALS:
            onlinematch.INTERVALS[h] = 0
        return mod, ctx, p

    def roundtrip(self, pid, fake):
        onlinematch.http_request = fake
        mod, ctx, p = self.login(pid)
        self.assertTrue(mod.ready(ctx)[0])
        self.assertIn("Markus", mod.run("test", ctx, [], {})["message"])
        self.assertEqual(mod.cloud_list(ctx, "TagStudio/Playlists"), {})            # Ordner fehlt noch
        rev = mod.cloud_put(ctx, "TagStudio/Playlists/DJ-Sets/Set ä.m3u8", b"#EXTM3U\n")
        self.assertTrue(rev)
        mod.cloud_put(ctx, "TagStudio/Playlists/B.m3u8", b"b")
        lst = mod.cloud_list(ctx, "TagStudio/Playlists")
        self.assertEqual(sorted(lst), ["B.m3u8", "DJ-Sets/Set ä.m3u8"])
        self.assertEqual(mod.cloud_get(ctx, "TagStudio/Playlists/DJ-Sets/Set ä.m3u8"), b"#EXTM3U\n")
        rev2 = mod.cloud_put(ctx, "TagStudio/Playlists/B.m3u8", b"b2")                 # ersetzen
        self.assertNotEqual(mod.cloud_list(ctx, "TagStudio/Playlists")["B.m3u8"]["rev"], lst["B.m3u8"]["rev"])
        self.assertTrue(rev2)
        mod.cloud_delete(ctx, "TagStudio/Playlists/B.m3u8")
        self.assertEqual(sorted(mod.cloud_list(ctx, "TagStudio/Playlists")), ["DJ-Sets/Set ä.m3u8"])
        # Abgleich über den Kern (PluginProvider)
        from session_cloud import PluginProvider
        prov = PluginProvider(p, self.s)
        root = os.path.join(self.dir, "pl")
        os.makedirs(root)
        part = cloudsync.FolderPart("playlists", "Playlists", root, exts=(".m3u8",))
        sync = {"provider": pid, "remote": "TagStudio/Playlists", "mode": "both"}
        r = cloudsync.run(part, prov, sync)
        self.assertEqual(r["down"], 1)
        with open(os.path.join(root, "DJ-Sets", "Set ä.m3u8"), "rb") as fh:
            self.assertEqual(fh.read(), b"#EXTM3U\n")
        with open(os.path.join(root, "Neu.m3u8"), "wb") as fh:
            fh.write(b"neu")
        self.assertEqual(cloudsync.run(part, prov, sync)["up"], 1)
        self.assertEqual(mod.cloud_get(ctx, "TagStudio/Playlists/Neu.m3u8"), b"neu")
        return mod, ctx

    def test_onedrive(self):
        g = FakeGraph()
        mod, ctx = self.roundtrip("onedrive", g)
        # grosse Datei: Upload-Sitzung, Teile ohne Token
        big = os.urandom(mod.SIMPLE_MAX + 10)
        mod.cloud_put(ctx, "TagStudio/Export/gross.bin", big)
        self.assertEqual(g.files["TagStudio/Export/gross.bin"][1], big)
        self.assertTrue(all("Authorization" not in c[3] for c in g.calls if c[1] == "up.example"))
        # Anmelde-Adresse: PKCE, Bereiche, localhost
        url = mod.app(ctx).auth_url()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(q["code_challenge_method"], ["S256"])
        self.assertIn("Files.ReadWrite", q["scope"][0])
        self.assertIn("offline_access", q["scope"][0])
        # 429: gemeldet, nicht wiederholt
        g.status, n = 429, len(g.calls)
        with self.assertRaises(onlinematch.HttpError) as cm:
            mod.cloud_list(ctx, "TagStudio/Playlists")
        self.assertIn("nicht wiederholt", str(cm.exception))
        self.assertEqual(len(g.calls), n + 1)

    def test_gdrive(self):
        fg = FakeGoogle()
        mod, ctx = self.roundtrip("gdrive", fg)
        mod._IDS.clear()
        self.assertEqual(sorted(mod.cloud_list(ctx, "TagStudio/Playlists")), ["DJ-Sets/Set ä.m3u8", "Neu.m3u8"])
        self.assertTrue(fg.items[[k for k, v in fg.items.items() if v["name"] == "B.m3u8"][0]]["trashed"])   # Papierkorb
        url = mod.app(ctx).auth_url()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual((q["access_type"], q["prompt"]), (["offline"], ["consent"]))
        self.assertEqual(q["scope"], ["https://www.googleapis.com/auth/drive.file"])
        mod._IDS.clear()

    def test_dropbox(self):
        fd = FakeDropbox()
        mod, ctx = self.roundtrip("dropbox", fd)
        arg = [c for c in fd.calls if c[2] == "/2/files/upload"][0][3]["Dropbox-API-Arg"]
        self.assertTrue(arg.isascii())                                             # Umlaute im Kopf als \\u…
        self.assertEqual(json.loads(arg)["mode"], "overwrite")
        url = mod.app(ctx).auth_url()
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(q["token_access_type"], ["offline"])

    def test_session_lists_cloud_plugins(self):
        onlinematch.http_request = FakeDropbox()
        ids = [p["id"] for p in self.s.cloud_sync_overview()["providers"]]
        self.assertEqual(sorted(ids), ["dropbox", "gdrive", "onedrive"])
        self.assertFalse(any(p["ready"] for p in self.s.cloud_sync_overview()["providers"]))
        with self.assertRaises(ValueError):
            self.s.cloud_sync_set("role", "playlists", {"provider": "unbekannt"})
        self.login("dropbox")
        prov = {p["id"]: p for p in self.s.cloud_sync_overview()["providers"]}
        self.assertTrue(prov["dropbox"]["ready"])
        ov = self.s.cloud_sync_set("app", "purchases", {"provider": "dropbox"})
        row = [r for r in ov["rows"] if r["id"] == "purchases"][0]
        self.assertEqual(row["sync"]["remote"], "TagStudio/Programmdaten/Käufe")


class TestOneDriveKind(Base):
    """#405: Umschalter Kontoart – geschäftlich (App, organizations) bzw. privat (OneDrive-Ordner)."""

    def setUp(self):
        super().setUp()
        from session import Session
        import plugins
        self.s = Session()
        self.p = self.s.plugins.get("onedrive")
        self.mod = self.p.load()
        self.assertIsNotNone(self.mod, self.p.error)
        self.ctx = plugins.Context(self.p)
        self.od = os.path.join(self.dir, "OneDrive")
        os.makedirs(self.od)
        self._orig = onlinematch.http_request
        self.addCleanup(setattr, onlinematch, "http_request", self._orig)

    def ids(self):
        return [a["id"] for a in self.p.actions(self.ctx)]

    def test_default_private_without_app(self):
        self.assertEqual(self.mod.load_settings(self.ctx)["account"], "private")
        self.assertEqual(self.ids(), ["settings", "test"])
        ok, why = self.mod.ready(self.ctx)
        self.assertFalse(ok)
        self.assertIn("OneDrive-Ordner fehlt", why)

    def test_default_business_with_existing_app(self):
        self.mod.app(self.ctx).save_credentials({"client_id": "CID"})
        self.assertEqual(self.mod.load_settings(self.ctx)["account"], "business")
        self.assertEqual(self.ids(), ["settings", "login", "logout", "test"])

    def test_private_folder(self):
        r = self.mod.run("settings", self.ctx, [], {"account": "private", "folder": self.od})
        self.assertIn("privates OneDrive", r["message"])
        self.assertEqual(self.mod.cloud_folder(self.ctx), os.path.abspath(self.od))
        self.assertIn("in Ordnung", self.mod.run("test", self.ctx, [], {})["message"])
        self.assertIn("keine Anmeldung", self.mod.run("login", self.ctx, [], {})["message"])
        with self.assertRaises(onlinematch.HttpError):
            self.mod.cloud_list(self.ctx, "TagStudio")                     # privat: kein API-Abgleich
        prov = {p["id"]: p for p in self.s.cloud_sync_overview()["providers"]}
        self.assertFalse(prov["onedrive"]["ready"])
        # fehlender Ordner → Meldung, Einstellung bleibt
        r = self.mod.run("settings", self.ctx, [], {"account": "private", "folder": os.path.join(self.dir, "fehlt")})
        self.assertIn("nicht gefunden", r["message"])
        self.assertEqual(self.mod.cloud_folder(self.ctx), os.path.abspath(self.od))

    def test_switch_keeps_settings(self):
        self.mod.app(self.ctx).save_credentials({"client_id": "CID"})
        self.mod.run("settings", self.ctx, [], {"account": "private", "folder": self.od})
        self.assertEqual(self.mod.app(self.ctx).client_id, "CID")          # App-Daten bleiben
        self.mod.run("settings", self.ctx, [], {"account": "business", "tenant": ""})
        st = self.mod.load_settings(self.ctx)
        self.assertEqual((st["account"], st["folder"], st["tenant"]), ("business", os.path.abspath(self.od), "organizations"))
        self.assertEqual(self.mod.cloud_folder(self.ctx), "")

    def test_business_endpoint_and_tenant(self):
        self.mod.run("settings", self.ctx, [], {"account": "business", "tenant": ""})
        a = self.mod.app(self.ctx)
        a.save_credentials({"client_id": "CID"})
        self.assertTrue(a.auth_url().startswith("https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize?"))
        self.mod.run("settings", self.ctx, [], {"account": "business", "tenant": "firma.ch"})
        self.assertIn("/firma.ch/oauth2/v2.0/token", self.mod.app(self.ctx).cfg["token"])
        for bad in ("common", "consumers", "a b"):
            self.assertIn("Verzeichnis", self.mod.run("settings", self.ctx, [], {"account": "business", "tenant": bad})["message"])

    def test_business_personal_drive_hint(self):
        g = FakeGraph()
        onlinematch.http_request = g
        a = self.mod.app(self.ctx)
        a.save_credentials({"client_id": "CID"})
        a._save(token=json.dumps({"access_token": TOKEN, "refresh_token": "RT", "expires_at": time.time() + 3600}))
        self.assertIn("Privates OneDrive", self.mod.run("test", self.ctx, [], {})["message"])   # Fake: driveType personal
