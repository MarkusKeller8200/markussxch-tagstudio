"""Tests für das Plugin „Online-Metadaten“ (#6–#8) mit nachgebauten Diensten (kein Netz nötig).
Die Antworten folgen den dokumentierten Formaten von MusicBrainz, Cover Art Archive, Deezer, iTunes, Discogs, Last.fm."""
import json
import os
import time
import unittest
import urllib.parse

from helpers import write_mp3, text
from test_tagger_tools import Base

import onlinematch
import plugins

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64

MB_REC = {"id": "rec-1", "title": "Nordlicht", "length": 372000,
          "artist-credit": [{"name": "Mara Lind", "artist": {"id": "art-1", "name": "Mara Lind"}}],
          "isrcs": ["CHA012100001"],
          "releases": [{"id": "rel-bootleg", "title": "Bootleg", "status": "Bootleg", "date": "2019"},
                       {"id": "rel-1", "title": "Nachtfahrt EP", "status": "Official", "date": "2021-05-14",
                        "release-group": {"id": "rg-1"}}]}
MB_REL = {"id": "rel-1", "title": "Nachtfahrt EP", "date": "2021-05-14",
          "label-info": [{"catalog-number": "POL042", "label": {"name": "Polar Records"}}],
          "release-group": {"id": "rg-1"},
          "artist-credit": [{"name": "Mara Lind", "artist": {"id": "art-1", "name": "Mara Lind"}}],
          "cover-art-archive": {"front": True},
          "media": [{"position": 1, "track-count": 3,
                     "tracks": [{"id": "trk-9", "position": 2, "number": "2", "recording": {"id": "rec-1"}}]}]}
DZ_SEARCH = {"data": [{"id": 3001, "title": "Kaltes Glas (Original Mix)", "title_short": "Kaltes Glas",
                       "title_version": "(Original Mix)", "duration": 0, "artist": {"name": "Mara Lind"},
                       "album": {"id": 501, "title": "Nachtfahrt EP", "cover_xl": "https://e-cdns-images.dzcdn.net/x/1000x1000.jpg"}}],
             "total": 1}
DZ_TRACK = {"id": 3001, "title": "Kaltes Glas (Original Mix)", "title_short": "Kaltes Glas", "title_version": "(Original Mix)",
            "isrc": "CHA012100002", "duration": 0, "track_position": 3, "disk_number": 1, "release_date": "2021-05-14",
            "bpm": 120.2, "contributors": [{"name": "Mara Lind"}], "artist": {"name": "Mara Lind"},
            "album": {"id": 501, "title": "Nachtfahrt EP", "cover_xl": "https://e-cdns-images.dzcdn.net/x/1000x1000.jpg"}}
DZ_ALBUM = {"id": 501, "label": "Polar Records", "genres": {"data": [{"name": "Dance"}]}, "release_date": "2021-05-14",
            "artist": {"name": "Mara Lind"}}
IT = {"resultCount": 1, "results": [{"trackId": 77, "trackName": "Kaltes Glas", "artistName": "Mara Lind",
                                     "collectionName": "Nachtfahrt - EP", "releaseDate": "2021-05-14T07:00:00Z",
                                     "primaryGenreName": "Electronic", "trackTimeMillis": 0, "trackNumber": 3, "trackCount": 3,
                                     "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/x/100x100bb.jpg"}]}
DC_SEARCH = {"results": [{"id": 9001, "title": "Mara Lind - Nachtfahrt EP"}]}
DC_REL = {"id": 9001, "title": "Nachtfahrt EP", "year": 2021, "released": "2021-05-14", "uri": "https://www.discogs.com/release/9001",
          "artists": [{"name": "Mara Lind (2)"}], "labels": [{"name": "Polar Records", "catno": "POL042"}],
          "genres": ["Electronic"], "styles": ["Deep House", "Minimal"],
          "images": [{"type": "secondary", "uri": "https://i.discogs.com/b.jpg"}, {"type": "primary", "uri": "https://i.discogs.com/a.jpg"}],
          "tracklist": [{"type_": "heading", "title": "Seite A"},
                        {"type_": "track", "position": "A1", "title": "Nordlicht", "duration": "6:12"},
                        {"type_": "track", "position": "A2", "title": "Kaltes Glas", "duration": "5:40"}]}


class FakeOnline:
    def __init__(self):
        self.calls = []
        self.fail503 = 0

    def __call__(self, url, headers=None):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        self.calls.append((u.netloc, u.path, q, dict(headers or {})))
        js = lambda d, st=200: (st, {}, json.dumps(d).encode())        # noqa: E731
        h, p = u.netloc, u.path
        if h == "musicbrainz.org":
            if self.fail503:
                self.fail503 -= 1
                return 503, {"Retry-After": "0"}, b""
            if p == "/ws/2/isrc/CHA012100001":
                return js({"isrc": "CHA012100001", "recordings": [MB_REC]})
            if p.startswith("/ws/2/isrc/"):
                return 404, {}, b""
            if p == "/ws/2/recording":
                return js({"recordings": [MB_REC] if "nordlicht" in q["query"].lower() else []})
            if p == "/ws/2/release/rel-1":
                return js(MB_REL)
        if h == "coverartarchive.org" or h.endswith(".dzcdn.net") or h.endswith(".mzstatic.com") or h == "i.discogs.com":
            return 200, {}, JPEG
        if h == "api.deezer.com":
            if p.startswith("/track/isrc:"):
                return js({"error": {"type": "DataException", "message": "no data", "code": 800}})
            if p == "/search/track":
                return js(DZ_SEARCH if "kaltes" in q["q"].lower() else {"data": [], "total": 0})
            if p == "/track/3001":
                return js(DZ_TRACK)
            if p == "/album/501":
                return js(DZ_ALBUM)
        if h == "itunes.apple.com" and p == "/search":
            return js(IT if "kaltes" in q["term"].lower() else {"resultCount": 0, "results": []})
        if h == "api.discogs.com":
            if headers.get("Authorization") != "Discogs token=DTOK":
                return 401, {}, b"{}"
            if p == "/database/search":
                return js(DC_SEARCH if "nordlicht" in q.get("track", "").lower() else {"results": []})
            if p == "/releases/9001":
                return js(DC_REL)
            if p == "/oauth/identity":
                return js({"username": "marku"})
        if h == "api.acoustid.org" and p == "/v2/lookup":
            if q.get("client") != "AKEY":
                return js({"status": "error", "error": {"code": 4, "message": "invalid API key"}})
            assert q.get("fingerprint") == "AQADtEmUaEkS" and q.get("duration") == "372"
            return js({"status": "ok", "results": [{"id": "fp-1", "score": 0.95, "recordings": [{"id": "rec-1"}]}]})
        if h == "musicbrainz.org" and p == "/ws/2/recording/rec-1":
            return js(MB_REC)
        if h == "ws.audioscrobbler.com":
            if q.get("api_key") != "LKEY":
                return js({"error": 10, "message": "Invalid API key"})
            if q.get("method") == "track.gettoptags":
                return js({"toptags": {"tag": [{"name": "deep house", "count": 100}, {"name": "melodic", "count": 40},
                                               {"name": "seen live", "count": 2}]}})
            return js({"tag": {"name": "house"}})
        return 404, {}, b"{}"


class TestMatch(unittest.TestCase):
    def test_split_and_score(self):
        self.assertEqual(onlinematch.split_title("Song (Extended Mix)"), ("Song", "Extended Mix"))
        self.assertEqual(onlinematch.split_title("Song - Extended Mix"), ("Song", "Extended Mix"))
        self.assertEqual(onlinematch.split_title("Rock - Paper"), ("Rock - Paper", ""))
        self.assertEqual(onlinematch.mmss("6:12"), 372)
        info = {"title": "Nordlicht", "mix": "", "artist": "Mara Lind", "isrc": "", "duration": 372}
        good = {"title": "Nordlicht", "artists": ["Mara Lind"], "length": 371}
        other = {"title": "Nordlicht", "artists": ["Ganz Anderer"], "length": 200}
        self.assertGreaterEqual(onlinematch.score(info, good), onlinematch.SURE)
        self.assertLess(onlinematch.score(info, other), onlinematch.MAYBE)
        self.assertEqual(onlinematch.best(info, [other, good])[0], good)
        self.assertEqual(onlinematch.score(dict(info, isrc="X1"), {"isrc": "x1", "title": "?"}), 1.0)

    def test_client_retry_and_throttle(self):
        fake = FakeOnline()
        fake.fail503 = 1
        cl = onlinematch.Client("UA", {"musicbrainz.org": 0.05}, get=fake)
        t0 = time.monotonic()
        d = cl.json("https://musicbrainz.org/ws/2/release/rel-1?fmt=json")
        self.assertEqual(d["id"], "rel-1")                      # 503 einmal → wiederholt
        cl.json("https://musicbrainz.org/ws/2/release/rel-1?fmt=json")
        self.assertGreaterEqual(time.monotonic() - t0, 0.08)     # Mindestabstand (Windows-Uhr ±16 ms)
        self.assertEqual(fake.calls[0][3]["User-Agent"], "UA")
        self.assertIsNone(cl.json("https://musicbrainz.org/ws/2/isrc/NOPE"))     # 404 → None


class TestOnlinePlugin(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind"), text("TSRC", "CHA012100001"),
                                                  text("TCON", "Synthpop")], audio_seed=11)
        write_mp3(os.path.join(self.B, "k.mp3"), [text("TIT2", "Kaltes Glas"), text("TPE1", "Mara Lind"),
                                                  text("TALB", "Eigenes Album")], audio_seed=12)
        write_mp3(os.path.join(self.B, "u.mp3"), [text("TIT2", "Gibt es nicht"), text("TPE1", "Niemand")], audio_seed=13)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.fake = FakeOnline()
        p = self.s.plugins.get("online")
        self.assertIsNotNone(p, "Plugin fehlt")
        mod = p.load()
        self.assertIsNotNone(mod, p.error)
        self.mod, self._orig = mod, mod.http_get
        mod.http_get = self.fake
        self._iv = dict(mod.INTERVALS)
        for k in mod.INTERVALS:
            mod.INTERVALS[k] = 0
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def tearDown(self):
        self.mod.http_get = self._orig
        self.mod.INTERVALS.update(self._iv)
        super().tearDown()

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def act(self, aid, idx=None, **opts):
        r = self.s.start_plugin_action("online", aid, idx or [], opts)
        self.assertTrue(r["ok"], r)
        return self.wait()

    def fetch(self, files, **opts):
        base = dict(mb=True, acoustid=False, discogs=False, deezer=True, itunes=False, itunes_country="CH", lastfm=False,
                    mode="empty", album=True, date="year", label=True, isrc=True, genre=True, bpm=False, track=False,
                    names=False, cover="missing", ids=True)
        base.update(opts)
        st = self.act("fetch", [self.idx[n] for n in files], **base)
        self.assertIsNone(st["error"], st)
        return st["result"]

    def test_musicbrainz_and_deezer(self):
        res = self.fetch(["n.mp3", "k.mp3", "u.mp3"], bpm=True)
        self.assertIn("2 sicher gefunden", res["message"])
        self.assertIn("1 nicht gefunden", res["message"])
        by = {(r["name"], r["label"]): r for r in res["proposals"]}
        # MusicBrainz über ISRC: offizielle Veröffentlichung statt Bootleg, Details aus dem Release
        self.assertEqual(by[("n.mp3", "Album (MusicBrainz)")]["new"], "Nachtfahrt EP")
        self.assertTrue(by[("n.mp3", "Album (MusicBrainz)")]["checked"])
        self.assertEqual(by[("n.mp3", "Jahr (MusicBrainz)")]["new"], "2021")
        self.assertEqual(by[("n.mp3", "Label (MusicBrainz)")]["new"], "Polar Records")
        self.assertEqual(by[("n.mp3", "Katalognummer (MusicBrainz)")]["new"], "POL042")
        self.assertEqual(by[("n.mp3", "MusicBrainz Release Track Id (MusicBrainz)")]["new"], "trk-9")
        self.assertEqual(by[("n.mp3", "MusicBrainz Album Id (MusicBrainz)")]["new"], "rel-1")
        self.assertEqual(by[("n.mp3", "Cover")]["kind"], "cover")
        self.assertIn("MusicBrainz", by[("n.mp3", "Cover")]["new"])
        # Deezer für k.mp3: Album schon gefüllt → nur gelistet (ergänzen), BPM gerundet, Label aus dem Album
        alb = by[("k.mp3", "Album (Deezer)")]
        self.assertFalse(alb["checked"])
        self.assertIn("ergänzen", alb["hint"])
        self.assertEqual(by[("k.mp3", "BPM (Deezer)")]["new"], "120")
        self.assertEqual(by[("k.mp3", "Label (Deezer)")]["new"], "Polar Records")
        self.assertEqual(by[("k.mp3", "ISRC (Deezer)")]["new"], "CHA012100002")
        self.assertEqual(by[("k.mp3", "DEEZER_TRACK_ID (Deezer)")]["new"], "3001")
        self.assertNotIn(("n.mp3", "Genre (MusicBrainz)"), by)               # vorhandenes Genre bleibt unberührt
        # MusicBrainz-Anfragen mit eigenem User-Agent
        ua = [c[3].get("User-Agent", "") for c in self.fake.calls if c[0] == "musicbrainz.org"]
        self.assertTrue(ua and all(u.startswith("TagStudio/") for u in ua))
        # übernehmen
        pick = [r["id"] for r in res["proposals"] if r["checked"]]
        self.assertTrue(self.s.plugin_apply(res["proposals_token"], pick)["ok"])
        f = self.s.tag_files[self.idx["n.mp3"]]
        self.assertEqual((f.text("TALB"), f.text("TPUB"), f.text("TCON")), ("Nachtfahrt EP", "Polar Records", "Synthpop"))
        self.assertEqual(self.s.tag_files[self.idx["k.mp3"]].text("TALB"), "Eigenes Album")

    def test_priority_and_alternatives(self):
        # Nordlicht: MusicBrainz und Discogs liefern Label – nur MusicBrainz (Vorrang) vorausgewählt
        self.act("keys", discogs="DTOK", lastfm="LKEY", acoustid="", fpcalc="", clear="")
        res = self.fetch(["n.mp3"], discogs=True, deezer=False, lastfm=True, genre=True)
        by = {(r["label"]): r for r in res["proposals"]}
        self.assertTrue(by["Label (MusicBrainz)"]["checked"])
        alt = by["Label (Discogs)"]
        self.assertFalse(alt["checked"])
        self.assertIn("Alternative", alt["hint"])
        self.assertEqual(by["DISCOGS_RELEASE_ID (Discogs)"]["new"], "9001")
        # Genre: vorhanden (Synthpop) → Discogs-Stil nur gelistet; Künstlername ohne „(2)“
        self.assertEqual(by["Genre (Discogs)"]["new"], "Deep House, Minimal")
        self.assertIn("Mara Lind –", by["Genre (Discogs)"]["note"])
        self.assertNotIn("(2)", by["Genre (Discogs)"]["note"])
        # Last.fm: Vorschläge, nie vorausgewählt, Tags mit wenig Stimmen weggelassen
        lt = by["Last.fm-Tags"]
        self.assertEqual((lt["new"], lt["checked"]), ("deep house; melodic", False))
        # Discogs-Token nie im Protokoll, in Vorschlägen oder Einstellungen
        blob = json.dumps(res) + json.dumps(self.s.cfg)
        self.assertNotIn("DTOK", blob)
        self.assertNotIn("LKEY", blob)

    def test_keys_status_test_and_missing(self):
        info = {p["id"]: p for p in self.s.plugins_list()["plugins"]}["online"]
        self.assertEqual(info["state"], "ready")
        self.assertIn("Schlüssel: keine", info["status_text"])
        # Discogs/Last.fm ohne Schlüssel: übersprungen mit Hinweis, kein Fehler
        res = self.fetch(["k.mp3"], mb=False, deezer=False, itunes=True, discogs=True, lastfm=True, cover="replace",
                         itunes_country="de")
        self.assertTrue(any("Discogs übersprungen" in l for l in res["log"]))
        by = {r["label"]: r for r in res["proposals"]}
        self.assertEqual(by["Genre (iTunes)"]["new"], "Electronic")
        self.assertEqual(by["ITUNES_TRACK_ID (iTunes)"]["new"], "77")
        it = [c for c in self.fake.calls if c[0] == "itunes.apple.com"][0]
        self.assertEqual(it[2]["country"], "DE")
        cov = [c for c in self.fake.calls if c[0].endswith(".mzstatic.com")][0]
        self.assertIn("1400x1400bb", cov[1])
        # keine Quelle → verständlicher Fehler
        st = self.act("fetch", [0], mb=False, deezer=False, itunes=False, discogs=False, lastfm=False)
        self.assertIn("Keine Quelle", st["error"])
        # Schlüssel speichern, Status, Test, Löschen
        self.act("keys", discogs="DTOK", lastfm="", acoustid="", fpcalc="", clear="")
        info = {p["id"]: p for p in self.s.plugins_list()["plugins"]}["online"]
        self.assertIn("Discogs", info["status_text"])
        with open(os.path.join(plugins.data_root(), "online", "keys.bin"), "rb") as fh:
            raw = fh.read()
        if os.name == "nt":
            self.assertNotIn(b"DTOK", raw)                       # Windows: DPAPI-verschlüsselt
        msg = self.act("test")["result"]["message"]
        self.assertIn("4 von 4", msg)
        self.act("keys", discogs="", lastfm="", acoustid="", fpcalc="", clear="all")
        self.assertIn("Schlüssel: keine", {p["id"]: p for p in self.s.plugins_list()["plugins"]}["online"]["status_text"])


    @unittest.skipIf(os.name == "nt", "nachgebautes fpcalc als Shell-Skript")
    def test_acoustid_for_untagged(self):
        import sys
        fp = os.path.join(self.dir, "fpcalc")
        with open(fp, "w") as fh:
            fh.write(f"#!{sys.executable}\nimport json; print(json.dumps({{'duration': 372.4, 'fingerprint': 'AQADtEmUaEkS'}}))\n")
        os.chmod(fp, 0o700)
        self.act("keys", discogs="", lastfm="", acoustid="AKEY", fpcalc=fp, clear="")
        self.assertIn("fpcalc gefunden", {p["id"]: p for p in self.s.plugins_list()["plugins"]}["online"]["status_text"])
        res = self.fetch(["u.mp3"], deezer=False, acoustid=True, names=True)
        by = {r["label"]: r for r in res["proposals"]}
        self.assertEqual(by["Titel (MusicBrainz)"]["new"], "Nordlicht")       # über den Fingerabdruck gefunden
        self.assertEqual(by["Album (MusicBrainz)"]["new"], "Nachtfahrt EP")
        self.assertTrue(by["Album (MusicBrainz)"]["checked"])
        self.assertNotIn("AKEY", json.dumps(res))
        # ohne fpcalc: verständlich übersprungen
        self.act("keys", discogs="", lastfm="", acoustid="AKEY", fpcalc="/gibt/es/nicht", clear="")
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = ""
        try:
            res = self.fetch(["u.mp3"], deezer=False, acoustid=True)
        finally:
            os.environ["PATH"] = old
        self.assertTrue(any("fpcalc nicht gefunden" in l for l in res["log"]))


if __name__ == "__main__":
    unittest.main()
