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
        self.calls, self.no_credits, self.paid = [], False, True

    def __call__(self, url, headers, data):
        u = urllib.parse.urlparse(url)
        if u.path == "/v1/tracks/identify":
            self.calls.append((u.path, {"bytes": len(data), "type": headers.get("Content-Type")}))
            if self.paid is False:
                return 403, {}, b'{"error":"paid tier required"}'
            return 200, {}, json.dumps({"matches": [{"track": SV_TRACK, "confidence": 0.93}]}).encode()
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
        # #379: neue Endpunkte der Doku stehen in der Tabelle, sind kostenpflichtig markiert und werden nie aufgerufen
        before = len(self.sv.calls)
        eps = {e["id"]: e for e in p.service["endpoints"]}
        new = ["suggestions-list", "stream", "stream-update", "stream-delete", "stream-history", "streams-report", "streams-live",
               "webhooks-create", "webhooks", "webhook-update", "webhook-delete", "webhook-test", "webhook-deliveries"]
        for eid in new + ["streams", "suggestions", "tracks-identify", "tracks-browse", "releases-new"]:
            self.assertIn(eid, eps)
            self.assertFalse(eps[eid]["test"], eid)
            self.assertTrue(self.mod.paid(eid), eid)
            self.assertEqual(self.mod.api_request(ctx, eps[eid], {"id": "1"})[0], 403)
        self.assertEqual(len(self.sv.calls), before)
        self.assertIn("415", eps["tracks-identify"]["note"])
        self.assertIn("next_cursor", eps["artist-releases"]["note"])
        import services
        rows = services.access_check(p, ctx, "Test")["rows"]                  # „Zugriff prüfen“ lässt sie aus
        self.assertFalse({r["path"] for r in rows} & {eps[e]["path"] for e in new + ["streams", "tracks-browse", "releases-new"]})

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

    def test_identify_costs_and_proposals(self):
        """#257 (SV2): Audio-Erkennung – Kostenhinweis ohne Hochladen, nur Titel ohne Tags, Vorschläge nur erlaubte Felder."""
        from helpers import write_mp3
        self.keys()
        write_mp3(os.path.join(self.B, "t.mp3"), [], audio_seed=21)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}
        mod = self.s.plugins.get("sonovault").load()
        cut = []
        orig = mod.excerpt
        mod.excerpt = lambda ctx, path, secs, dur=0: cut.append((os.path.basename(path), secs)) or b"x" * 200_000
        self.addCleanup(setattr, mod, "excerpt", orig)
        sel = [idx["t.mp3"], idx["k.mp3"]]
        r = self.act("identify", sel, pid="sonovault", seconds="30", only_untagged=True, confirm=False)["result"]
        self.assertIn("1 von 2 Titel(n) zum Erkennen – geschätzt 11 Kredite", r["message"])
        self.assertEqual((cut, self.post.calls), ([], []))                          # nichts hochgeladen
        r = self.act("identify", sel, pid="sonovault", seconds="30", only_untagged=True, confirm=True)["result"]
        self.assertEqual(cut, [("t.mp3", 30)])
        self.assertEqual(self.post.calls[0][1]["type"], "application/octet-stream")
        by = {p["label"]: p for p in r["proposals"]}
        self.assertEqual(by["Titel (SonoVault)"]["new"], "Kaltes Glas (Original Mix)")
        self.assertTrue(by["Titel (SonoVault)"]["checked"])
        self.assertIn("93 %", by["Titel (SonoVault)"]["note"])
        self.assertFalse(any("BPM" in k or "Tonart" in k or "Katalog" in k for k in by))
        self.assertIn("11 von 1000 Anfragen", self.info()["status_text"])         # 10 + 1 je MB
        # ohne bezahlten Tarif: verständliche Meldung, nichts verrechnet
        self.post.paid = False
        st = self.act("identify", sel, pid="sonovault", seconds="30", only_untagged=True, confirm=True)
        self.assertIn("gekaufte Kredite", st["error"] or "")
        self.assertIn("11 von 1000 Anfragen", self.info()["status_text"])


REL_SEARCH = {"results": [{"id": 9, "title": "Andere EP", "artist": {"id": 2, "name": "Jemand"}},
                          {"id": 8, "title": "Nachtfahrt EP", "artist": {"id": 1, "name": "Mara Lind"},
                           "label": {"id": 3, "name": "Polar Records"}, "release_date": "2021-05-14"}], "next_cursor": None}
REL = {"id": 8, "title": "Nachtfahrt EP", "artist": {"id": 1, "name": "Mara Lind"}, "label": {"id": 3, "name": "Polar Records"},
       "release_date": "2021-05-14", "catalog_no": "POL042", "editions": [], "edition": None,
       "tracks": [dict(SV_N, disc_number=1, track_number=1, releases=None),
                  dict(SV_TRACK, disc_number=1, track_number=2, releases=None)]}
BROWSE = {"results": [dict(SV_TRACK, id=901, title="Frisch (Extended Mix)", releases=[{"title": "Frisch", "label": {"name": "Polar Records"},
                                                                                      "release_date": "2026-10-25"}]),
                      dict(SV_TRACK, id=902, title="Alt", releases=[{"title": "Alt", "release_date": "2019-01-01"}])]}


class TestSonoVaultMore(TestSonoVault):
    """#380, #381, #383, #259 – Release nachschlagen, eigene Felder, Tarif, Browse in Entdecken, Genre-Korrektur."""

    def setUp(self):
        super().setUp()
        sv = self.sv

        def fake(url, headers=None):
            u = urllib.parse.urlparse(url)
            if u.netloc == "api.sonovault.now":
                q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
                js = (lambda d: (sv.calls.append((u.path, q, {})) or (200, {}, json.dumps(d).encode())))   # noqa: E731
                if u.path == "/v1/releases/search":
                    return js(REL_SEARCH)
                if u.path == "/v1/releases/8":
                    return js(REL)
                if u.path == "/v1/tracks/browse":
                    return js(BROWSE)
                if u.path == "/v1/labels/search":
                    return js({"results": [{"id": 3, "name": "Polar Records"}]})
                if u.path == "/v1/genres":
                    return js({"genres": [{"id": 12, "name": "House", "type": "main"},
                                          {"id": 47, "name": "Deep House", "type": "subgenre", "parent": "House"},
                                          {"id": 50, "name": "Techno", "type": "main"}]})
                if u.path == "/v1/suggestions":
                    return js({"results": [{"id": 5, "track_id": 4711, "field": "genre",
                                            "proposed_value": {"genre_id": 50, "genre_name": "Techno"},
                                            "current_value": {"genre": ["House"], "subgenre": ["Deep House"]},
                                            "status": "pending", "review_note": None, "created_at": "2026-10-28T10:00:00Z"}],
                               "next_cursor": None})
                if u.path == "/v1/tracks/4711":
                    return js(SV_TRACK)
            return sv(url, headers)
        onlinematch.http_get = fake
        post = self.post

        def fpost(url, headers, data):
            u = urllib.parse.urlparse(url)
            if u.path.endswith("/suggestions"):
                body = json.loads(data.decode("utf-8"))
                post.calls.append((u.path, body))
                if not post.paid:
                    return 403, {}, b'{"error":"paid plan required"}'
                return 201, {}, json.dumps({"id": 6, "track_id": 4711, "field": "genre", "status": "pending"}).encode()
            return post(url, headers, data)
        onlinematch.http_post = fpost

    def test_release_lookup(self):
        """#380: Release über Album + Künstler, Trackliste per ISRC bzw. Titel zugeordnet, nur erlaubte Felder,
        Katalog-/Titelnummer nur in der Notiz, 2 Anfragen je Release (danach Zwischenspeicher)."""
        self.keys()
        r = self.act("release", [self.idx["n.mp3"], self.idx["k.mp3"], self.idx["u.mp3"]], pid="sonovault",
                     title="Nachtfahrt EP", artist="Mara Lind", mode="empty", date="year", names=False, own=False)["result"]
        self.assertIn("1 von 1 Release(s) gefunden, 2 von 3 Titel(n) zugeordnet", r["message"])
        by = {(p["name"], p["label"]): p for p in r["proposals"]}
        self.assertEqual(by[("n.mp3", "Album (SonoVault)")]["new"], "Nachtfahrt EP")
        self.assertEqual(by[("k.mp3", "Label (SonoVault)")]["new"], "Polar Records")
        self.assertEqual(by[("k.mp3", "Jahr (SonoVault)")]["new"], "2021")
        self.assertEqual(by[("k.mp3", "ISRC (SonoVault)")]["new"], "CHA012100002")
        self.assertIn("Katalognummer POL042 (nur Anzeige)", by[("k.mp3", "Album (SonoVault)")]["note"])
        self.assertIn("Titel 2 / CD 1 (nur Anzeige)", by[("k.mp3", "Album (SonoVault)")]["note"])
        self.assertFalse(any("Katalog" in p["label"] or "Spur" in p["label"] or "SONOVAULT" in p["label"] for p in r["proposals"]))
        self.assertIn(["u.mp3", "Nachtfahrt EP", "nicht in der Trackliste"], r["table"]["rows"])
        self.assertEqual([c[0] for c in self.sv.calls], ["/v1/releases/search", "/v1/releases/8"])
        self.assertTrue(all("Polar" not in ln for ln in r["log"]))                       # keine Werte im Protokoll
        self.act("release", [self.idx["k.mp3"]], pid="sonovault", title="Nachtfahrt EP", artist="Mara Lind")
        self.assertEqual(len(self.sv.calls), 2)

    def test_own_fields(self):
        """#383: eigene Felder TXXX:SONOVAULT_* nur auf Wunsch, nur erlaubte Werte + Abrufdatum, Herkunft „SonoVault“."""
        import datetime
        import origins
        self.keys()
        res = self.fetch(["k.mp3"], mb=False, deezer=False, sonovault=True, own=True)
        own = {p["label"].split(" (")[0]: p for p in res["proposals"] if p["label"].startswith("SONOVAULT_")}
        self.assertEqual(set(own), {"SONOVAULT_TITLE", "SONOVAULT_ARTIST", "SONOVAULT_RELEASE", "SONOVAULT_LABEL",
                                    "SONOVAULT_GENRE", "SONOVAULT_RELEASE_DATE", "SONOVAULT_DURATION", "SONOVAULT_ISRC",
                                    "SONOVAULT_DATE"})
        self.assertEqual(own["SONOVAULT_DURATION"]["new"], "5:40")
        self.assertEqual(own["SONOVAULT_DATE"]["new"], datetime.date.today().isoformat())
        self.assertEqual(own["SONOVAULT_RELEASE_DATE"]["new"], "2021-05-14")
        self.assertFalse(any(k in own for k in ("SONOVAULT_BPM", "SONOVAULT_KEY", "SONOVAULT_ID", "SONOVAULT_CATALOGNUMBER")))
        res = self.fetch(["k.mp3"], mb=False, deezer=False, sonovault=True, own=False)
        self.assertFalse(any(p["label"].startswith("SONOVAULT_") for p in res["proposals"]))
        o = origins.Origins()
        self.assertEqual(o.catalog()[o.of("TXXX:SONOVAULT_LABEL")]["name"], "SonoVault")

    def test_tier_browse_in_discover(self):
        """#381: Tarif „Bezahlt“ – Starter-Kontingent, Entdecken holt zusätzlich die neuesten Titel je Label/Genre."""
        import discover
        self.keys()
        mod = self.mod
        import plugins
        ctx = plugins.Context(self.s.plugins.get("sonovault"))
        with self.assertRaises(ValueError):
            mod.browse(ctx, {"genre": "House"}, "x", 60)                   # Free: nie abgefragt
        self.act("keys", pid="sonovault", tier="paid")
        self.assertTrue(mod.is_paid(ctx))
        self.assertIn("50000", self.info()["status_text"])
        self.assertIn("Tarif bezahlt", self.info()["status_text"])
        with discover.LOCK:
            d = discover.load()
            d["follow"].update(artists=[], labels=["Polar Records"], genres=[{"id": 5, "name": "House"}], sources=["sonovault"])
            discover.save(d)
        self.assertTrue(self.s.disc_overview()["sonovault"]["paid"])
        self.s.start_disc_run()
        st = self.wait()
        self.assertIsNone(st["error"], st)
        items = discover.load()["items"]
        e = items.get("sonovault:trk:901")
        self.assertIsNotNone(e, list(items))
        self.assertEqual((e["title"], e["mix"], e["url"]), ("Frisch", "Extended Mix", ""))
        self.assertNotIn("sonovault:trk:902", items)                         # älter als „days“
        paths = [c[0] for c in self.sv.calls]
        self.assertIn("/v1/tracks/browse", paths)
        browse_q = [c[1] for c in self.sv.calls if c[0] == "/v1/tracks/browse"]
        self.assertIn({"labelId": "3"}, browse_q)
        self.assertIn({"genre": "House"}, browse_q)
        self.assertEqual(discover.export_rows(discover.load()), [])           # nie exportiert
        self.act("keys", pid="sonovault", tier="free")
        self.assertIn("1000 Anfragen", self.info()["status_text"])

    def test_genre_suggestion(self):
        """#259: Vorschau ohne Senden, dann genreId + note; nur mit bezahltem Tarif; Liste mit Status."""
        self.keys()
        f = self.s.tag_files[self.idx["k.mp3"]]
        f.set_text("TCON", "Techno")
        st = self.act("suggest", [self.idx["k.mp3"]], pid="sonovault", note="", confirm=False)
        self.assertIn("bezahlten Tarif", st["error"] or "")
        self.act("keys", pid="sonovault", tier="paid")
        r = self.act("suggest", [self.idx["k.mp3"], self.idx["u.mp3"]], pid="sonovault", note="", confirm=False)["result"]
        self.assertIn("1 von 2 Titel(n) könnten gemeldet werden – nichts gesendet", r["message"])
        self.assertIn(["k.mp3", "House, Deep House", "Techno", "Techno"], r["table"]["rows"])
        self.assertFalse([c for c in self.post.calls if c[0].endswith("/suggestions")])
        r = self.act("suggest", [self.idx["k.mp3"]], pid="sonovault", note="Klar Techno", confirm=True)["result"]
        sent = [c for c in self.post.calls if c[0].endswith("/suggestions")]
        self.assertEqual(sent, [("/v1/tracks/4711/suggestions", {"genreId": 50, "note": "Klar Techno"})])
        self.assertIn("1 Genre-Korrektur(en) gemeldet", r["message"])
        f.set_text("TCON", "Deep House")                                         # gleich → nichts zu melden
        r = self.act("suggest", [self.idx["k.mp3"]], pid="sonovault", confirm=False)["result"]
        self.assertIn(["k.mp3", "House, Deep House", "Deep House", "gleich"], r["table"]["rows"])
        r = self.act("suggestions", pid="sonovault")["result"]
        self.assertEqual(r["table"]["rows"][0][3:5], ["Techno", "pending"])

    def test_mix_gaps_online(self):
        """#393 „MixID light“: Erkennungsdienst im Rahmen, Kostenvorschau, Lauf, Zeilen „online“, Aufbewahrung, Ideen."""
        import mixresult
        self.keys()
        mix = os.path.join(self.B, "Mix.mp3")
        with open(mix, "wb") as fh:
            fh.write(b"\xff\xfb\x90\x00" * 50)
        rid = self.s._mix_store({"mix": mix, "duration": 900, "rows": [
            {"start": 400, "end": 500, "path": "", "artist": "A", "title": "Bekannt", "conf": 0.9}]})
        recs = self.s.plugins.recognizers(self.s)
        self.assertEqual([r["id"] for r in recs], ["sonovault"])
        self.assertEqual(recs[0]["retain_days"], 30)                         # Free: nur 30 Tage
        info = self.s.mix_gaps_info(rid)
        self.assertEqual([(g["start"], g["end"]) for g in info["gaps"]], [(0.0, 400.0), (500.0, 900.0)])
        p = self.s.mix_gaps_plan(rid, "sonovault", 30, 3)
        self.assertEqual((p["clips"], p["more"], p["each"], p["cost"]), (3, 3, 11, 33))   # je 3 Ausschnitte (400 s = 3 × 180 s)
        self.assertFalse(self.s.start_mix_gaps(rid, {"seconds": 30, "max": 3})["ok"])      # ohne Bestätigung
        self.assertEqual(self.post.calls, [])
        cut = []
        orig = self.mod.excerpt_at
        self.mod.excerpt_at = lambda ctx, path, start, secs: cut.append((start, secs)) or b"x" * 1000
        self.addCleanup(setattr, self.mod, "excerpt_at", orig)
        self.act("keys", pid="sonovault", tier="paid")
        self.assertTrue(self.s.start_mix_gaps(rid, {"seconds": 30, "max": 3, "confirm": True})["ok"])
        r = self.wait()["result"]
        self.assertEqual((r["found"], r["clips"], r["error"]), (2, 3, ""))   # zwei gleiche Treffer nebeneinander → eine Zeile
        self.assertEqual(len(cut), 3)
        d = self.s.mix_get(rid)
        on = [ln for ln in d["lines"] if not ln.get("gap") and ln["online"]]
        self.assertEqual([ln["title"] for ln in on], ["Kaltes Glas (Original Mix)", "Kaltes Glas (Original Mix)"])
        self.assertEqual(on[0]["online"], "SonoVault")
        self.assertEqual(d["online"], 2)
        self.assertIn("Mara Lind - Kaltes Glas (Original Mix)", d["text"])
        res = mixresult.load(self.s._mix_dir(), rid)
        again = mixresult.plan_clips(res, 30, 10)                           # geprüfte Stellen nicht nochmals
        self.assertTrue(again)
        self.assertFalse([c for c in again if any(c["start"] < b and a < c["end"] for a, b in res["probed"])])
        self.assertTrue(any(r.get("online") for r in res["rows"]))
        it = [x for x in mixresult.to_items(res) if x["title"].startswith("Kaltes")][0]
        self.assertEqual(it["ref"]["source"], "sonovault")
        self.assertIn("SonoVault", it["note"])
        r = self.s.mix_online_to_ideas(rid, "", "")
        self.assertEqual(r["added"], 1)
        # bezahlter Tarif: bleiben; Free und älter als 30 Tage: werden entfernt
        for row in res["rows"]:
            if row.get("online"):
                row["online"]["fetched"] = "2026-01-01"
        mixresult.save(self.s._mix_dir(), res)
        self.assertEqual(self.s.mix_get(rid)["online"], 2)
        self.act("keys", pid="sonovault", tier="free")
        self.assertEqual(self.s.mix_get(rid)["online"], 0)
        self.assertEqual([ln["title"] for ln in self.s.mix_get(rid)["lines"] if not ln.get("gap")], ["Bekannt"])


for _n in [n for n in dir(TestSonoVault) if n.startswith("test_")]:     # geerbte Tests nicht doppelt ausführen
    setattr(TestSonoVaultMore, _n, None)
