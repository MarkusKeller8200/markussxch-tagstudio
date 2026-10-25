"""#253–#255: SonoVault-Plugin mit nachgebautem Dienst (kein Netz nötig). Antworten wie in den offiziellen SDKs von
Rekordcloud (snake_case: title, artists, isrc, duration, bpm, key_alphanumeric, keys, genre, releases)."""
import json
import os
import time
import urllib.parse

from test_online import OnlineHarness

import onlinematch

SV_TRACK = {"id": 4711, "title": "Kaltes Glas (Original Mix)", "artists": [{"id": 1, "name": "Mara Lind", "primary": True}],
            "isrc": "CHA012100002", "duration": 340, "bpm": 122, "key_alphanumeric": "8A", "key_musical": "Am", "key_open": "1m",
            "keys": [{"key_alphanumeric": "8A", "source": "a"}, {"key_alphanumeric": "8A", "source": "b"}],
            "genre": ["House"], "subgenre": ["Deep House"],
            "releases": [{"title": "Nachtfahrt EP", "label": "Polar Records", "release_date": "2021-05-14", "catalog_number": "POL042"}]}
SV_N = dict(SV_TRACK, id=4712, title="Nordlicht", isrc="CHA012100001", key_alphanumeric="9A", bpm=None, keys=[])
LINKS = {"links": [{"source": "spotify", "external_id": "SPOT123", "url": "https://open.spotify.com/track/SPOT123"},
                   {"source": "beatport", "external_id": "BP987", "url": "https://www.beatport.com/track/x/BP987"}]}


class FakeSV:
    def __init__(self, inner):
        self.inner, self.calls, self.status = inner, [], None

    def __call__(self, url, headers=None):
        u = urllib.parse.urlparse(url)
        if u.netloc != "api.sonovault.now":
            return self.inner(url, headers)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        self.calls.append((u.path, q, dict(headers or {})))
        if self.status:
            return self.status, {}, b'{"error":"rate limit"}'
        if (headers or {}).get("x-api-key") != "svk_live_TEST":
            return 401, {}, b'{"error":"invalid key"}'
        hd = {"RateLimit-Limit": "20", "RateLimit-Remaining": "19"}
        js = lambda d: (200, hd, json.dumps(d).encode())        # noqa: E731
        if u.path == "/v1/tracks/isrc/CHA012100001":
            return js(SV_N)
        if u.path.startswith("/v1/tracks/isrc/"):
            return 404, hd, b'{"error":"not found"}'
        if u.path == "/v1/tracks/search":
            return js({"results": [SV_TRACK] if "kaltes" in q["title"].lower() else [], "next_cursor": None})
        if u.path == "/v1/tracks/links":
            return js(LINKS)
        if u.path == "/v1/genres":
            return js({"genres": [{"id": 1, "name": "House"}]})
        return 404, hd, b"{}"


class FakePost:
    def __init__(self):
        self.calls, self.no_credits = [], False

    def __call__(self, url, headers, data):
        body = json.loads(data.decode("utf-8"))
        self.calls.append((urllib.parse.urlparse(url).path, body))
        if headers.get("x-api-key") != "svk_live_TEST":
            return 401, {}, b'{"error":"invalid key"}'
        out = []
        for it in body["items"]:
            if self.no_credits:
                out.append({"status": "skipped_no_credits"})
            elif it == "CHA012100001":
                out.append({"status": "matched", "track": SV_N, "links": []})
            elif isinstance(it, dict) and "kaltes" in it["title"].lower():
                out.append({"status": "matched", "track": SV_TRACK, "links": []})
            else:
                out.append({"status": "not_found"})
        return 200, {}, json.dumps({"results": out, "partial": False}).encode()


class TestSonoVault(OnlineHarness):
    def setUp(self):
        super().setUp()
        self.sv = FakeSV(self.fake)
        onlinematch.http_get = self.sv
        self.post = FakePost()
        self._post_orig = onlinematch.http_post
        onlinematch.http_post = self.post
        self.addCleanup(setattr, onlinematch, "http_post", self._post_orig)
        onlinematch.INTERVALS["api.sonovault.now"] = 0
        self.mod = self.s.plugins.get("sonovault").load()
        self.assertIsNotNone(self.mod, self.s.plugins.get("sonovault").error)

    def info(self):
        return {p["id"]: p for p in self.s.plugins_list()["plugins"]}["sonovault"]

    def keys(self):
        self.act("keys", pid="sonovault", sonovault="svk_live_TEST")

    def test_without_key_skipped(self):
        res = self.fetch(["k.mp3"], mb=True, deezer=False, sonovault=True)
        self.assertTrue(any("SonoVault übersprungen" in ln for ln in res["log"]), res["log"])
        self.assertEqual(self.sv.calls, [])
        self.assertIn("kein Schlüssel", self.info()["status_text"])

    def test_fetch_only_allowed_fields_and_compare(self):
        self.keys()
        self.assertIn("0 von 1000 Anfragen", self.info()["status_text"])
        res = self.fetch(["n.mp3", "k.mp3"], mb=False, deezer=False, sonovault=True, names=True)
        props = [r for r in res["proposals"] if r["name"] == "k.mp3"]
        labels = {r["label"].split(" (")[0] for r in props}                       # nur erlaubte Felder (§7)
        self.assertTrue(labels <= {"Titel", "Künstler", "Album", "Jahr", "Datum", "Label", "ISRC", "Genre"}, labels)
        by = {r["label"]: r for r in props}
        self.assertEqual(by["Label (SonoVault)"]["new"], "Polar Records")
        self.assertEqual(by["Album (SonoVault)"]["new"], "Nachtfahrt EP")
        self.assertEqual(by["ISRC (SonoVault)"]["new"], "CHA012100002")
        self.assertEqual(by["Genre (SonoVault)"]["new"], "House, Deep House")
        self.assertNotIn("Katalognummer (SonoVault)", by)                         # Nutzungsbedingungen §7
        self.assertIn("Vergleich SonoVault: Tonart 08A (2 Quellen)", by["Label (SonoVault)"]["note"])
        self.assertIn("122 BPM", by["Label (SonoVault)"]["note"])
        n = {r["label"]: r for r in res["proposals"] if r["name"] == "n.mp3"}
        self.assertIn("Album (SonoVault)", n)                                     # über die ISRC gefunden
        self.assertEqual([c[0] for c in self.sv.calls], ["/v1/tracks/isrc/CHA012100001", "/v1/tracks/search"])
        self.assertTrue(all("Polar" not in ln and "Nachtfahrt" not in ln for ln in res["log"]))   # keine Werte im Protokoll
        self.assertIn("2 von 1000 Anfragen", self.info()["status_text"])
        # zweiter Lauf: aus dem Zwischenspeicher, kein neuer Abruf
        self.fetch(["n.mp3", "k.mp3"], mb=False, deezer=False, sonovault=True)
        self.assertEqual(len(self.sv.calls), 2)
        self.assertIn("2 von 1000 Anfragen", self.info()["status_text"])

    def test_cache_expires_after_30_days(self):
        self.keys()
        self.fetch(["k.mp3"], mb=False, deezer=False, sonovault=True)
        ctx = self.s.plugins.get("sonovault")
        import plugins
        root = os.path.join(plugins.data_root(), "sonovault", "cache")
        files = [os.path.join(r, n) for r, _d, ns in os.walk(root) for n in ns]
        self.assertTrue(files)
        for p in files:
            with open(p, encoding="utf-8") as fh:
                d = json.load(fh)
            d["t"] = time.time() - 31 * 86400
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(d, fh)
        self.fetch(["k.mp3"], mb=False, deezer=False, sonovault=True)
        self.assertEqual(len(self.sv.calls), 2)                                    # abgelaufen → neu geholt
        self.assertIsNotNone(ctx)
        r = self.act("cache", pid="sonovault", confirm=True)["result"]
        self.assertIn("gelöscht", r["message"])

    def test_429_not_retried_and_limit(self):
        self.keys()
        self.sv.status = 429
        st = self.act("fetch", [self.idx["k.mp3"]], mb=False, deezer=False, sonovault=True, mode="empty", names=False)
        self.assertIn("nicht wiederholt", st["error"] or "")
        self.assertEqual(len(self.sv.calls), 1)
        # Kontingent aufgebraucht → kein Abruf mehr
        self.sv.status = None
        self.act("keys", pid="sonovault", limit="1")
        st = self.act("fetch", [self.idx["k.mp3"]], mb=False, deezer=False, sonovault=True)
        self.assertIn("Monatskontingent aufgebraucht", st["error"] or "")
        self.assertEqual(len(self.sv.calls), 1)
        self.assertIn("aufgebraucht", self.info()["status_text"])

    def test_links_only_displayed(self):
        self.keys()
        r = self.act("links", [self.idx["k.mp3"], self.idx["n.mp3"]], pid="sonovault")["result"]
        rows = r["table"]["rows"]
        self.assertIn(["n.mp3", "Spotify", "SPOT123"], rows)
        self.assertIn(["n.mp3", "Beatport", "BP987"], rows)
        self.assertEqual(r.get("proposals", []), [])                                       # nie in die Dateien
        self.assertTrue(all("SPOT123" not in ln for ln in r["log"]))
        f = self.s.tag_files[self.idx["n.mp3"]]
        self.assertFalse(f.is_modified())

    def test_tester_skips_paid_endpoints(self):
        self.keys()
        p = self.s.plugins.get("sonovault")
        import plugins
        ctx = plugins.Context(p)
        ep = next(e for e in p.service["endpoints"] if e["id"] == "tracks-browse")
        st, _h, body, _u = self.mod.api_request(ctx, ep, {})
        self.assertEqual(st, 403)
        self.assertEqual(self.sv.calls, [])
        ok, why = self.mod.check(ctx)
        self.assertTrue(ok)
        self.assertIn("1 von 1000", why)

    def test_resolve_compare_only(self):
        """#256: Bibliothek abgleichen – Kostenvorschau ohne Abruf, dann Blöcke, nur Anzeige, Zwischenspeicher kostet nichts."""
        self.keys()
        idx = [self.idx[n] for n in ("n.mp3", "k.mp3", "u.mp3")]
        r = self.act("resolve", idx, pid="sonovault", max="500", confirm=False)["result"]
        self.assertIn("3 brauchen eine Anfrage", r["message"])
        self.assertIn("Kosten jetzt: 3 Kredite", r["message"])
        self.assertEqual(self.post.calls, [])
        r = self.act("resolve", idx, pid="sonovault", max="500", confirm=True)["result"]
        self.assertEqual([c[1]["input_type"] for c in self.post.calls], ["isrc", "track_name"])
        rows = r["table"]["rows"]
        self.assertIn(["k.mp3", "Album", "Eigenes Album", "Nachtfahrt EP"], rows)
        self.assertIn(["u.mp3", "–", "–", "nicht gefunden"], rows)
        self.assertIn("3 von 1000 Anfragen", self.info()["status_text"])
        self.assertEqual(r.get("proposals", []), [])
        self.assertFalse(any(self.s.tag_files[i].is_modified() for i in idx))
        # nochmals: alles aus dem Zwischenspeicher, keine Kosten
        r = self.act("resolve", idx, pid="sonovault", max="500", confirm=True)["result"]
        self.assertEqual(len(self.post.calls), 2)
        self.assertIn("3 aus dem Zwischenspeicher", r["message"])
        self.assertIn("3 von 1000 Anfragen", self.info()["status_text"])

    def test_resolve_respects_quota(self):
        self.keys()
        self.act("keys", pid="sonovault", limit="2")
        idx = [self.idx[n] for n in ("n.mp3", "k.mp3", "u.mp3")]
        r = self.act("resolve", idx, pid="sonovault", max="500", confirm=True)["result"]
        self.assertIn("1 noch offen", r["message"])                                 # nur 2 Kredite übrig
        self.assertEqual(sum(len(c[1]["items"]) for c in self.post.calls), 2)
        self.assertIn("aufgebraucht", self.info()["status_text"])

    def test_discover_releases(self):
        """#258: Entdecken – neue Veröffentlichungen gefolgter Künstler/Labels, ohne Link, nie exportiert, nach 30 Tagen weg,
        nicht bei der täglichen Suche."""
        import discover
        self.keys()
        rel = {"results": [{"id": 77, "title": "Polarlicht EP", "artist": "Mara Lind", "label": {"name": "Polar Records"},
                            "release_date": "2026-10-20"}], "next_cursor": None}
        inner = self.sv.inner

        def fake(url, headers=None):
            u = urllib.parse.urlparse(url)
            if u.netloc == "api.sonovault.now" and u.path == "/v1/artists/search":
                self.sv.calls.append((u.path, {}, {}))
                return 200, {}, json.dumps({"results": [{"id": 5, "name": "Mara Lind"}]}).encode()
            if u.netloc == "api.sonovault.now" and u.path == "/v1/artists/5/releases":
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                self.assertIn("from", q)
                self.sv.calls.append((u.path, q, {}))
                return 200, {}, json.dumps(rel).encode()
            return self.sv(url, headers)
        onlinematch.http_get = fake
        with discover.LOCK:
            d = discover.load()
            d["follow"].update(artists=["Mara Lind"], labels=[], sources=["sonovault"])
            discover.save(d)
        r = self.s.disc_overview()
        self.assertTrue(r["sonovault"]["ready"])
        self.assertTrue(self.s.start_disc_run()["ok"])
        st = self.wait()
        self.assertIsNone(st["error"], st)
        items = discover.load()["items"]
        e = items["sonovault:rel:77"]
        self.assertEqual((e["src"], e["title"], e["label"], e["url"]), ("sonovault", "Polarlicht EP", "Polar Records", ""))
        self.assertEqual(len(self.sv.calls), 2)
        # nochmals: Suche und Liste aus dem Zwischenspeicher
        self.s.start_disc_run()
        self.wait()
        self.assertEqual(len(self.sv.calls), 2)
        # nie im Export, auch gemerkt
        with discover.LOCK:
            d = discover.load()
            d["items"]["sonovault:rel:77"]["status"] = "saved"
            discover.save(d)
        self.assertEqual(discover.export_rows(discover.load()), [])
        # nach 30 Tagen entfernt
        with discover.LOCK:
            d = discover.load()
            d["items"]["sonovault:rel:77"]["first"] = "2020-01-01T00:00:00"
            discover.save(d)
        self.assertNotIn("sonovault:rel:77", discover.load()["items"])
        # tägliche Suche: SonoVault nie
        n = len(self.sv.calls)
        found = discover.run(discover.load(), None, None, dz=None)
        self.assertEqual((found, len(self.sv.calls)), ([], n))
