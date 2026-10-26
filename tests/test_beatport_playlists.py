"""#334/#335: Playlists in Beatport anlegen und befüllen – gegen eine nachgebaute Beatport-API (ohne Netz).
Geprüft: Einstellung aus → nichts, Schreibprüfung per OPTIONS, nur TagStudio_-Playlists, je 100 Titel, ersetzen
statt anhäufen, ergänzen ohne Doppelte, löschen nur mit Präfix."""
import json
import os
import shutil
import tempfile
import time
import unittest

from test_beatport_purchases import load_plugin, Ctx


class FakeBeatport:
    """Sehr kleine Django-REST-artige API: /my/playlists/ und /my/playlists/{id}/tracks/…"""

    def __init__(self, allow_create=True):
        self.pl = {1: {"id": 1, "name": "Meine Liste", "tracks": [5]}}
        self.next = 100
        self.allow_create = allow_create
        self.calls = []

    def page(self, rows, params):
        p, n = int(params.get("page", 1)), int(params.get("per_page", 100))
        return rows[(p - 1) * n:p * n]

    def get(self, path, **params):
        if path == "/my/playlists/":
            return self.page([{"id": k, "name": v["name"], "track_count": len(v["tracks"])} for k, v in self.pl.items()], params)
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[3] == "tracks":
            pl = self.pl.get(int(parts[2]))
            if pl is None:
                return None
            rows = [{"id": 1000 * pl["id"] + i, "track": {"id": t, "name": f"T{t}"}} for i, t in enumerate(pl["tracks"])]
            return self.page(rows, params)
        return None

    def request(self, method, url, headers=None, data=None, **_kw):
        path = url.split("/v4", 1)[1]
        self.calls.append((method, path, data))
        parts = path.strip("/").split("/")
        if method == "OPTIONS":
            if path == "/my/playlists/":
                acts = {"POST": {"name": {"type": "string"}}} if self.allow_create else {}
                return 200, {"Allow": "GET, POST, OPTIONS" if self.allow_create else "GET, OPTIONS"}, json.dumps({"actions": acts}).encode()
            if path.endswith("/tracks/bulk/"):
                return 200, {"Allow": "POST, OPTIONS"}, json.dumps({"actions": {"POST": {"track_ids": {"type": "list"}}}}).encode()
            return 200, {"Allow": "GET, PATCH, DELETE, OPTIONS"}, b"{}"
        if method == "POST" and path == "/my/playlists/":
            if not self.allow_create:
                return 403, {}, b'{"detail": "You do not have permission"}'
            self.next += 1
            self.pl[self.next] = {"id": self.next, "name": data["name"], "tracks": []}
            return 201, {}, json.dumps({"id": self.next, "name": data["name"]}).encode()
        if method == "POST" and path.endswith("/tracks/bulk/"):
            pl = self.pl[int(parts[2])]
            assert len(data["track_ids"]) <= 100
            pl["tracks"] += [t for t in data["track_ids"] if t not in pl["tracks"]]
            return 201, {}, b"{}"
        if method == "DELETE" and len(parts) == 5:                       # Titel entfernen
            pl = self.pl[int(parts[2])]
            entry = int(parts[4])
            pl["tracks"] = [t for i, t in enumerate(pl["tracks"]) if 1000 * pl["id"] + i != entry]
            return 204, {}, b""
        if method == "DELETE" and len(parts) == 3:
            self.pl.pop(int(parts[2]), None)
            return 204, {}, b""
        return 404, {}, b""


class FakeClient:
    def __init__(self, api):
        self.api = api
        self.tok = {"access_token": "x", "expires_at": time.time() + 3600}

    def get(self, path, **params):
        return self.api.get(path, **params)


class TestBeatportPlaylists(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.bp = load_plugin()
        self.api = FakeBeatport()
        self.bp.request = self.api.request
        self.bp.Client = lambda ctx: FakeClient(self.api)
        self.bp.ready = lambda ctx: (True, "")
        self.bp.scope_text = lambda tok: "Scope: test"
        self.ctx = Ctx(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_settings_and_guard(self):
        self.assertEqual(self.bp.store_settings(self.ctx), {"playlists_write": False, "buy_prefix": "TagStudio_BUY_"})
        with self.assertRaises(ValueError):                                       # Standard aus → nichts geschrieben
            self.bp.store_playlist_put(self.ctx, "TagStudio_DOWNLOAD_x_1", [1, 2])
        self.assertFalse([c for c in self.api.calls if c[0] in ("POST", "DELETE")])
        s = self.bp.store_settings(self.ctx, {"playlists_write": True, "buy_prefix": "Meine Käufe"})
        self.assertEqual(s["buy_prefix"], "TagStudio_Meine_Käufe")                  # nur eigene Playlists
        with self.assertRaises(ValueError):
            self.bp.store_playlist_put(self.ctx, "Meine Liste", [1])                 # fremde Playlist nie
        with self.assertRaises(ValueError):
            self.bp.store_playlist_delete(self.ctx, "Mein")

    def test_check_put_replace_delete(self):
        self.bp.store_settings(self.ctx, {"playlists_write": True})
        chk = self.bp.store_playlist_check(self.ctx)
        self.assertTrue(chk["ok"] and chk["create"] and chk["add"] and chk["remove"] and chk["delete"])
        self.assertIn("Playlist anlegen: ja", chk["text"])
        self.assertFalse([c for c in self.api.calls if c[0] not in ("OPTIONS",)])   # Prüfung ändert nichts
        ids = [str(i) for i in range(1, 231)]
        names = []
        for n, k in enumerate(range(0, 230, 100)):                                # 230 Titel → 100/100/30
            r = self.bp.store_playlist_put(self.ctx, f"TagStudio_DOWNLOAD_2026-10-26_{n + 1}", ids[k:k + 100], True)
            names.append(r["name"])
            self.assertTrue(r["created"])
        sizes = [len(v["tracks"]) for v in self.api.pl.values() if v["name"].startswith("TagStudio_")]
        self.assertEqual(sizes, [100, 100, 30])
        r = self.bp.store_playlist_put(self.ctx, names[2], ids[200:205], True)       # erneut: ersetzt, keine neue
        self.assertEqual((r["created"], r["added"], r["removed"], r["total"]), (False, 0, 25, 5))
        self.assertEqual(len([v for v in self.api.pl.values() if v["name"] == names[2]]), 1)
        r = self.bp.store_playlist_put(self.ctx, "TagStudio_BUY_2026_10_20", ["7", "8"], False)
        r = self.bp.store_playlist_put(self.ctx, "TagStudio_BUY_2026_10_20", ["8", "9"], False)   # nur ergänzen
        self.assertEqual((r["added"], r["removed"], r["total"]), (1, 0, 3))
        d = self.bp.store_playlist_delete(self.ctx, "TagStudio_DOWNLOAD_")
        self.assertEqual(sorted(d["deleted"]), names)
        self.assertEqual(sorted(v["name"] for v in self.api.pl.values()), ["Meine Liste", "TagStudio_BUY_2026_10_20"])

    def test_options_without_answer(self):
        """#334: OPTIONS ohne Angabe (wie bei echtem Beatport) blockiert nicht – die echte Anfrage entscheidet."""
        real = self.api.request

        def req(method, url, **kw):
            if method == "OPTIONS":
                self.api.calls.append((method, url, None))
                return 403, {}, b'{"detail": "Method not allowed"}'
            return real(method, url, **kw)
        self.bp.request = req
        self.bp.store_settings(self.ctx, {"playlists_write": True})
        chk = self.bp.store_playlist_check(self.ctx)
        self.assertTrue(chk["create"] and not chk["known"])
        self.assertIn("versucht es beim Anlegen direkt", chk["text"])
        r = self.bp.store_playlist_put(self.ctx, "TagStudio_DOWNLOAD_x_1", ["1", "2"], True)
        self.assertTrue(r["created"])
        self.assertEqual(r["added"], 2)
        self.assertIn("OPTIONS /my/playlists/: HTTP 403", "\n".join(self.ctx.logs))

    def test_no_create_permission(self):
        self.api.allow_create = False
        self.bp.store_settings(self.ctx, {"playlists_write": True})
        self.assertFalse(self.bp.store_playlist_check(self.ctx)["ok"])
        with self.assertRaises(ValueError) as cm:
            self.bp.store_playlist_put(self.ctx, "TagStudio_DOWNLOAD_x_1", ["1"])
        self.assertIn("nicht", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class TestApiTesterWrite(unittest.TestCase):
    """#350: API-Tester schreibend – nur bestätigt, alles ins Protokoll (Kopfzeilen, Body), Token geschwärzt."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.bp = load_plugin()
        self.api = FakeBeatport()
        self.bp.request = self.api.request
        self.bp.Client = lambda ctx: FakeClient(self.api)
        self.ctx = Ctx(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_services_guard_and_log(self):
        import services
        raw = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "plugins", "beatport", "plugin.json"), encoding="utf-8"))["service"]
        svc = services.clean(raw)
        ep = next(e for e in svc["endpoints"] if e["method"] == "POST" and e["path"] == "/my/playlists/")
        self.assertTrue(ep["test"] and ep["write"])
        self.assertFalse(services.clean(dict(raw, write_test=False))["endpoints"][[e["id"] for e in svc["endpoints"]].index(ep["id"])]["test"])

        class P:                                       # nachgebautes Plugin für services.api_call
            service = svc

            def load(_s):
                return self.bp
        with self.assertRaises(ValueError):            # ohne Bestätigung nichts senden
            services.api_call(P(), self.ctx, ep["id"], {"_body": '{"name": "TagStudio_T"}'}, "UA")
        self.assertFalse([c for c in self.api.calls if c[0] == "POST"])
        with self.assertRaises(ValueError):
            services.api_call(P(), self.ctx, ep["id"], {"_body": "{kaputt", "_confirm": "yes"}, "UA")
        r = services.api_call(P(), self.ctx, ep["id"], {"_body": '{"name": "TagStudio_T"}', "_confirm": "yes"}, "UA")
        self.assertEqual(r["status"], 201)
        self.assertEqual(self.api.calls[-1][:3], ("POST", "/my/playlists/", {"name": "TagStudio_T"}))
        log = "\n".join(self.ctx.logs)
        self.assertIn("POST https://api.beatport.com/v4/my/playlists/", log)
        self.assertIn("Authorization: Bearer •••", log)
        self.assertIn('Anfrage-Body: {"name": "TagStudio_T"}', log)
        self.assertIn("Antwort: HTTP 201", log)
        self.assertNotIn("Bearer x", log)
        de = next(e for e in svc["endpoints"] if e["method"] == "DELETE" and e["path"] == "/my/playlists/{id}/")
        services.api_call(P(), self.ctx, de["id"], {"id": "1", "_confirm": "yes"}, "UA")
        self.assertNotIn(1, self.api.pl)

    def test_fields_editor_and_patch(self):
        """#356: Felder per OPTIONS (ändert nichts, ohne Bestätigung), Rückfall auf plugin.json; #357: PATCH testbar."""
        import services
        raw = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "plugins", "beatport", "plugin.json"), encoding="utf-8"))["service"]
        svc = services.clean(raw)

        class P:
            service = svc

            def load(_s):
                return self.bp
        r = services.api_fields(P(), self.ctx, "my-playlists-create", {})
        self.assertEqual((r["source"], [f["name"] for f in r["fields"]]), ("service", ["name"]))
        self.assertEqual(json.loads(r["template"]), {"name": ""})
        self.assertIn("POST", r["allow"])
        self.assertEqual([c[0] for c in self.api.calls], ["OPTIONS"])                 # nur OPTIONS, nichts geschrieben
        self.assertIn("OPTIONS https://api.beatport.com/v4/my/playlists/", "\n".join(self.ctx.logs))
        r = services.api_fields(P(), self.ctx, "my-playlists-update", {})             # Pfad-ID fehlt → plugin.json
        self.assertEqual(r["source"], "plugin")
        self.assertIn("id", r["note"])
        self.assertEqual(json.loads(r["example"]), {"name": "TagStudio_Test_neu"})
        with self.assertRaises(ValueError):
            services.api_fields(P(), self.ctx, "my-playlists-delete", {"id": "1"})    # DELETE hat keinen Body
        eps = {e["id"]: e for e in svc["endpoints"]}
        patch = [e for e in svc["endpoints"] if e["method"] == "PATCH"]
        self.assertTrue(patch and all(e["test"] and e["write"] for e in patch))
        self.assertTrue(eps["my-account-myaccount"]["danger"])
        for eid in ("my-beatport-delete", "my-genres-id", "auth-token", "auth-login", "auth-revoke"):
            self.assertFalse(eps[eid]["test"], eid)                                     # bleiben gesperrt
        r = services.api_call(P(), self.ctx, "my-playlists-update", {"id": "1", "_body": '{"name": "TagStudio_X"}', "_confirm": "yes"}, "UA")
        self.assertEqual(self.api.calls[-1][:2], ("PATCH", "/my/playlists/1/"))

    def test_clean_fields(self):
        import services
        fs = services.clean_fields({"name": {"type": "string", "required": True, "max_length": 255, "help_text": "h"},
                                    "kind": {"type": "choice", "choices": [{"value": "a", "display_name": "A"}]},
                                    "ids": {"type": "list", "child": {"type": "integer"}},
                                    "id": {"type": "integer", "read_only": True}, "bad name": {"type": "x"}})
        self.assertEqual([f["name"] for f in fs], ["name", "kind", "ids", "id"])
        self.assertEqual(services.body_template(fs), {"name": "", "kind": "a", "ids": [0]})

    def test_large_buy_playlist(self):
        """#360: Playlist je Kaufdatum mit mehr als 100 Titeln – eine Playlist, API-Pakete je 100."""
        self.bp.ready = lambda ctx: (True, "")
        self.bp.store_settings(self.ctx, {"playlists_write": True})
        ids = [str(i) for i in range(1, 251)]
        r = self.bp.store_playlist_put(self.ctx, "TagStudio_BUY_2026_10_21", ids, False)
        self.assertEqual((r["created"], r["added"], r["total"]), (True, 250, 250))
        self.assertEqual([len(v["tracks"]) for v in self.api.pl.values() if v["name"] == "TagStudio_BUY_2026_10_21"], [250])
        self.assertEqual(len([c for c in self.api.calls if c[0] == "POST" and c[1].endswith("/tracks/bulk/")]), 3)

    def test_reset_download_endpoint(self):
        """#361: reset-download im API-Tester – GET, aber ändernd: nur mit Bestätigung, nie in „Zugriff prüfen“."""
        import services
        raw = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                          "plugins", "beatport", "plugin.json"), encoding="utf-8"))["service"]
        svc = services.clean(raw)
        eps = {e["id"]: e for e in svc["endpoints"]}
        ep = eps["track-reset-download"]
        self.assertEqual((ep["method"], ep["test"], ep["danger"]), ("GET", True, True))
        self.assertEqual(ep["params"][0]["example"], "605271245")
        self.assertTrue(eps["track-reset-download-post"]["write"])

        class P:
            service = svc

            def load(_s):
                return self.bp
        with self.assertRaises(ValueError):
            services.api_call(P(), self.ctx, "track-reset-download", {"order_item_download_id": "605271245"}, "UA")
        self.assertFalse(self.api.calls)                                                # ohne Bestätigung nichts gesendet
        services.api_call(P(), self.ctx, "track-reset-download", {"order_item_download_id": "605271245", "_confirm": "yes"}, "UA")
        self.assertEqual(self.api.calls[-1][:2], ("GET", "/catalog/tracks/reset-download/?order_item_download_id=605271245"))
        src = open(services.__file__, encoding="utf-8").read()
        self.assertIn('not e.get("danger")', src)                                       # „Zugriff prüfen“ lässt es aus
