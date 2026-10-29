"""#280: Spotify- und SoundCloud-Plugin mit nachgebauten Diensten (kein Netz nötig) und die OAuth-Anmeldung (PKCE).
Antworten nach den dokumentierten Formaten (Spotify Web API Stand Februar 2026, SoundCloud API)."""
import base64
import hashlib
import json
import os
import threading
import time
import unittest
import urllib.parse
import urllib.request

from helpers import write_mp3, text
from test_tagger_tools import Base

import oauthkit
import onlinematch

SP_TRACK = {"id": "sp1", "type": "track", "name": "Kaltes Glas - Extended Mix", "duration_ms": 340000, "track_number": 3,
            "explicit": False,
            "disc_number": 1, "artists": [{"id": "ar1", "name": "Mara Lind"}], "external_ids": {"isrc": "cha012100002"},
            "external_urls": {"spotify": "https://open.spotify.com/track/sp1"},
            "album": {"id": "al1", "name": "Nachtfahrt EP", "release_date": "2021-05-14", "artists": [{"name": "Mara Lind"}],
                      "total_tracks": 4,
                      "images": [{"url": "https://i.scdn.co/image/abc"}]}}
SP2_TRACK = {"id": "sp2" + "x" * 19, "type": "track", "name": "Morgenrot", "duration_ms": 300000, "track_number": 1,
             "artists": [{"id": "ar2", "name": "Lio Berg"}], "external_ids": {"isrc": "CHA012100009"},
             "external_urls": {"spotify": "https://open.spotify.com/track/sp2xxxxxxxxxxxxxxxxxxx"},
             "uri": "spotify:track:sp2xxxxxxxxxxxxxxxxxxx",
             "album": {"id": "al2", "name": "Morgenrot", "release_date": "2026-10-20", "images": []}}
SP_ALBUM = {"id": "al1", "name": "Nachtfahrt EP", "release_date": "2021-05-14", "total_tracks": 2, "album_type": "ep",
            "artists": [{"id": "ar1", "name": "Mara Lind"}], "images": [{"url": "https://i.scdn.co/image/abc"}],
            "external_urls": {"spotify": "https://open.spotify.com/album/al1"},
            "tracks": {"items": [{"id": "sp1", "name": "Kaltes Glas - Extended Mix", "track_number": 1, "disc_number": 1,
                                  "duration_ms": 340000, "artists": [{"id": "ar1", "name": "Mara Lind"}]},
                                 {"id": "sp3", "name": "Nordlicht", "track_number": 2, "disc_number": 1,
                                  "duration_ms": 372000, "artists": [{"id": "ar1", "name": "Mara Lind"}]}], "next": None}}
import datetime as _dt                                                          # noqa: E402
_RECENT = (_dt.date.today() - _dt.timedelta(days=3)).isoformat()
SP_RELEASES = {"ar1": [{"id": "al9", "name": "Neue Single", "album_type": "single", "release_date": _RECENT,
                        "artists": [{"id": "ar1", "name": "Mara Lind"}], "images": [{"url": "https://i.scdn.co/image/n"}],
                        "external_urls": {"spotify": "https://open.spotify.com/album/al9"}},
                       {"id": "al0", "name": "Altes Album", "album_type": "album", "release_date": "2019-01-01",
                        "artists": [{"id": "ar1", "name": "Mara Lind"}], "images": [],
                        "external_urls": {"spotify": "https://open.spotify.com/album/al0"}}]}
SC_TRACK = {"id": 77, "title": "Nordlicht (Club Mix)", "duration": 372000, "genre": "Techno", "bpm": 128,
            "permalink_url": "https://soundcloud.com/maralind/nordlicht", "user": {"username": "maralind"},
            "publisher_metadata": {"artist": "Mara Lind", "isrc": "CHA012100001", "release_title": "Nachtfahrt EP"},
            "artwork_url": "https://i1.sndcdn.com/artworks-x-large.jpg", "created_at": "2021/05/14 10:00:00 +0000"}


class Fake:
    """Spotify- und SoundCloud-API; prüft den Token im Kopf."""

    def __init__(self):
        self.calls, self.token_ok = [], {"SP-OK", "SC-OK", "SP-NEW", "SC-NEW"}
        self.playing, self.sp_items, self.saved = None, {}, set()

    def __call__(self, url, headers=None):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        h = dict(headers or {})
        self.calls.append((u.netloc, u.path, q, h))
        js = lambda d, st=200: (st, {}, json.dumps(d).encode())        # noqa: E731
        auth = h.get("Authorization", "")
        if u.netloc in ("api.spotify.com", "api.soundcloud.com") and auth.split(" ")[-1] not in self.token_ok:
            return 401, {}, b"{}"
        p = u.path
        if u.netloc == "api.spotify.com":
            assert auth.startswith("Bearer ")
            if p == "/v1/me":
                return js({"id": "me", "display_name": "Markus"})
            if p == "/v1/me/playlists":
                if q.get("offset") == "1":
                    return js({"items": [{"id": "pl2", "name": "Fremd", "owner": {"id": "other"}}], "next": None})
                return js({"items": [{"id": "pl1", "name": "Freitag", "owner": {"id": "me"}}],
                           "next": "https://api.spotify.com/v1/me/playlists?offset=1&limit=50"})
            if p == "/v1/playlists/pl1":
                return js({"name": "Freitag"})
            if p == "/v1/playlists/pl1/items":
                return js({"items": [{"item": SP_TRACK}, {"item": {"type": "episode", "name": "Podcast"}}], "next": None})
            if p == "/v1/me/tracks":
                return js({"items": [{"track": SP_TRACK}], "next": None})
            if p == "/v1/me/following":
                return js({"artists": {"items": [{"name": "Mara Lind"}, {"name": "Neu Artist"}], "next": None}})
            if p == "/v1/search" and q.get("type") == "album":                  # #384 SP4
                return js({"albums": {"items": [SP_ALBUM] if "nachtfahrt" in q["q"].lower() else []}})
            if p == "/v1/search" and q.get("type") == "artist":                 # #384 SP1
                return js({"artists": {"items": [{"id": "ar1", "name": "Mara Lind"}] if "mara" in q["q"].lower() else []}})
            if p == "/v1/albums/al9/tracks":
                return js({"items": [{"id": "sp9", "name": "Neue Single - Club Mix", "artists": [{"id": "ar1", "name": "Mara Lind"}],
                                      "external_urls": {"spotify": "https://open.spotify.com/track/sp9"}}], "next": None})
            if p == "/v1/search":
                hit = "cha012100002" in q["q"].lower() or "kaltes" in q["q"].lower()
                assert int(q["limit"]) <= 10
                return js({"tracks": {"items": [SP_TRACK] if hit else []}})
            if p == "/v1/tracks/sp1":
                return js(SP_TRACK)
            if p == "/v1/artists/ar1":
                return js({"id": "ar1", "genres": ["deep house"]})
            if p == "/v1/me/player/currently-playing":                      # #384 SP2
                if getattr(self, "playing", None) is None:
                    return 204, {}, b""
                return js({"is_playing": True, "item": self.playing})
            if p == "/v1/me/player/recently-played":
                return js({"items": [{"track": SP_TRACK, "played_at": "2026-10-29T18:00:00Z"},
                                     {"track": SP_TRACK, "played_at": "2026-10-29T17:50:00Z"},
                                     {"track": SP2_TRACK, "played_at": "2026-10-29T17:40:00Z"}]})
            if p.startswith("/v1/playlists/wp1"):                              # SP5: eigene Wunschliste
                if p.endswith("/items"):
                    return js({"items": [{"item": {"uri": u}} for u in self.sp_items.get("wp1", [])], "next": None})
                return js({"id": "wp1", "name": "x", "owner": {"id": "me"}, "external_urls": {"spotify": "https://open.spotify.com/playlist/wp1"}})
            if p == "/v1/me/library/contains":                                 # SP6
                ids = q["uris"].split(",")
                return js([u in self.saved for u in ids])
            if p.startswith("/v1/artists/") and p.endswith("/albums"):         # SP1
                return js({"items": SP_RELEASES.get(p.split("/")[3], []), "next": None})
            if p == "/v1/me/albums":                                           # SP3
                return js({"items": [{"added_at": "2026-10-01T00:00:00Z", "album": SP_ALBUM}], "next": None})
            if p == "/v1/albums/al1":                                          # SP4
                return js(SP_ALBUM)
            if p == "/v1/albums/al1/tracks":
                return js({"items": SP_ALBUM["tracks"]["items"], "next": None})
        if u.netloc == "api.soundcloud.com":
            assert auth.startswith("OAuth ")
            if p == "/me":
                return js({"username": "markus"})
            if p == "/me/playlists":
                return js({"collection": [{"urn": "soundcloud:playlists:5", "title": "Warm up"}], "next_href": None})
            if p == "/playlists/soundcloud:playlists:5":
                return js({"title": "Warm up", "tracks": [SC_TRACK]})
            if p == "/me/likes/tracks":
                return js({"collection": [SC_TRACK], "next_href": None})
            if p == "/me/followings":
                return js({"collection": [{"username": "maralind"}], "next_href": None})
            if p == "/tracks":
                return js({"collection": [SC_TRACK] if "nordlicht" in q["q"].lower() else []})
        if u.netloc in ("i.scdn.co", "i1.sndcdn.com"):
            return 200, {}, b"\xff\xd8\xff\xe0" + b"0" * 64
        return 404, {}, b""


class FakeWrite:
    """Schreibende Spotify-Aufrufe (#384 SP5/SP6) über onlinematch.http_request."""

    def __init__(self, fake):
        self.fake, self.calls, self.status = fake, [], None

    def __call__(self, method, url, headers, data=None):
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        body = json.loads(data) if data else None
        self.calls.append((method, u.path, q, body, dict(headers or {})))
        if self.status:
            return self.status, {}, b'{"error":{"status":403,"message":"Forbidden"}}'
        assert (headers or {}).get("Authorization", "").startswith("Bearer SP-")
        if method == "POST" and u.path == "/v1/me/playlists":
            assert body["public"] is False                                     # immer privat
            self.fake.sp_items["wp1"] = []
            return 201, {}, json.dumps({"id": "wp1", "external_urls": {"spotify": "https://open.spotify.com/playlist/wp1"}}).encode()
        if method == "POST" and u.path == "/v1/playlists/wp1/items":
            self.fake.sp_items.setdefault("wp1", []).extend(body["uris"])
            return 201, {}, b'{"snapshot_id":"s"}'
        if method == "PUT" and u.path == "/v1/me/library":
            self.fake.saved.update(q["uris"].split(","))
            return 200, {}, b""
        return 404, {}, b""


class FakePost:
    def __init__(self):
        self.calls = []

    def __call__(self, url, data, headers=None):
        self.calls.append((url, dict(data)))
        if data["grant_type"] == "authorization_code":
            if data["code"] != "CODE1":
                return 400, {"error": "invalid_grant"}
            pre = "SP" if "spotify" in url else "SC"
            return 200, {"access_token": f"{pre}-OK", "refresh_token": f"{pre}-R1", "expires_in": 3600}
        if data["grant_type"] == "refresh_token":
            pre = "SP" if "spotify" in url else "SC"
            return 200, {"access_token": f"{pre}-NEW", "refresh_token": f"{pre}-R2", "expires_in": 3600}
        return 400, {}


class TestPkce(unittest.TestCase):
    def test_challenge_and_redirect(self):
        v, c = oauthkit.pkce()
        self.assertGreaterEqual(len(v), 43)
        self.assertEqual(c, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode())
        self.assertEqual(oauthkit.parse_redirect("http://127.0.0.1:8765/callback?code=AB&state=S", "S"), "AB")
        with self.assertRaises(oauthkit.OAuthError):
            oauthkit.parse_redirect("http://127.0.0.1:8765/callback?code=AB&state=X", "S")     # fremde Anmeldung
        with self.assertRaises(oauthkit.OAuthError):
            oauthkit.parse_redirect("http://127.0.0.1:8765/callback?error=access_denied&state=S", "S")

    def test_loopback_localhost(self):
        """4.9.1: Rückleitung über localhost – Server nimmt 127.0.0.1 (und [::1], falls vorhanden) an."""
        port = 18767
        res = {}
        t = threading.Thread(target=lambda: res.setdefault("url", oauthkit.wait_for_redirect(port, "/cb", timeout=10,
                                                                                               host="localhost")))
        t.start()
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/cb?code=L&state=S", timeout=2) as r:
                    r.read()
                break
            except OSError:
                time.sleep(0.1)
        t.join(5)
        self.assertTrue(res["url"].startswith("http://localhost:"), res)
        self.assertEqual(oauthkit.parse_redirect(res["url"], "S"), "L")

    def test_loopback_server(self):
        port = 18765
        res = {}
        t = threading.Thread(target=lambda: res.setdefault("url", oauthkit.wait_for_redirect(port, "/callback", timeout=10)))
        t.start()
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=Z&state=S", timeout=2) as r:
                    self.assertIn("Anmeldung abgeschlossen", r.read().decode())
                break
            except OSError:
                time.sleep(0.1)
        t.join(5)
        self.assertEqual(oauthkit.parse_redirect(res["url"], "S"), "Z")


class TestPlugins(Base):
    def setUp(self):
        super().setUp()
        write_mp3(os.path.join(self.B, "k.mp3"), [text("TIT2", "Kaltes Glas (Extended Mix)"), text("TPE1", "Mara Lind"),
                                                  text("TSRC", "CHA012100002")], audio_seed=12)
        write_mp3(os.path.join(self.B, "n.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind")], audio_seed=11)
        from session import Session
        self.s = Session()
        self.s.start_tag_load(self.B, False)
        self.wait()
        self.fake, self.post = Fake(), FakePost()
        self._orig = (onlinematch.http_get, oauthkit.http_post, oauthkit.open_browser, onlinematch.http_request)
        onlinematch.http_get, oauthkit.http_post = self.fake, self.post
        self.write = FakeWrite(self.fake)
        onlinematch.http_request = self.write
        self.opened = []
        oauthkit.open_browser = lambda url: self.opened.append(url) or True
        self._iv = dict(onlinematch.INTERVALS)
        for k in onlinematch.INTERVALS:
            onlinematch.INTERVALS[k] = 0
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def tearDown(self):
        onlinematch.http_get, oauthkit.http_post, oauthkit.open_browser, onlinematch.http_request = self._orig
        onlinematch.INTERVALS.update(self._iv)
        super().tearDown()

    def wait(self):
        for _ in range(500):
            st = self.s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)
        self.fail("hängt")

    def act(self, pid, aid, idx=None, **opts):
        r = self.s.start_plugin_action(pid, aid, idx or [], opts)
        self.assertTrue(r["ok"], r)
        st = self.wait()
        self.assertIsNone(st["error"], st)
        return st["result"]

    def login(self, pid, **keys):
        self.assertIn("Client-ID", self.act(pid, "login", method="browser")["message"])          # ohne Zugang: Hinweis
        r = self.act(pid, "login", method="paste", url="", **keys)         # Schritt 1: Zugang speichern, Browser öffnen
        self.assertIn("Adresse", r["message"])
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.opened[-1]).query).items()}
        self.assertEqual((q["code_challenge_method"], q["client_id"]), ("S256", keys["client_id"]))
        r = self.act(pid, "login", method="paste", url=f"{q['redirect_uri']}?code=CODE1&state={q['state']}")
        self.assertIn("angemeldet als", r["message"])
        return q

    def test_pages_stop_and_host(self):
        """4.9.1: leere Seiten bzw. wiederholte next-Links beenden das Laden; fremder Host bekommt keinen Token."""
        class C:
            def check_cancel(self):
                pass
        for pid, nxt_key, box in (("spotify", "next", "items"), ("soundcloud", "next_href", "collection")):
            mod = self.s.plugins.get(pid).load()
            calls = []
            api = mod.API

            def fake_get(ctx, path, cl=None, **params):
                calls.append(path)
                if len(calls) > 50:
                    raise AssertionError("endlos")
                return {box: [] if calls[1:] else [{"id": 1}], nxt_key: api + "/next?x=1"}
            orig = mod.get
            mod.get = fake_get
            try:
                self.assertEqual(len(mod.pages(C(), "/me", cl=object())), 1)
                self.assertLessEqual(len(calls), 3, calls)
            finally:
                mod.get = orig
            with self.assertRaises(RuntimeError):
                mod.get(C(), "https://evil.example/steal", cl=object())

    def test_spotify(self):
        q = self.login("spotify", client_id="CID", redirect="http://127.0.0.1:8765/callback")
        self.assertIn("playlist-read-private", q["scope"])
        self.assertNotIn("client_secret", self.post.calls[-1][1])                    # PKCE ohne Secret
        # Schlüssel verschlüsselt bzw. nicht lesbar im Datenordner – nie im Klartext in der Konfiguration
        with open(os.path.join(self.dir, "cfg.json"), encoding="utf-8") as fh:
            self.assertNotIn("SP-OK", fh.read()) if os.path.exists(fh.name) else None
        # Playlists: Lieblingssongs + eigene (fremde fallen weg)
        self.assertEqual([x["name"] for x in self.s.dj_sources()["sources"] if x["id"] == "spotify"], ["Spotify"])
        st = self.s.start_dj_source_list("spotify")
        lists = self.wait()["result"]["playlists"]
        self.assertEqual([p["id"] for p in lists], ["liked", "pl1", "album:al1"])               # #384 SP3: + Alben
        self.s.start_pl_source_import("spotify", ["pl1"])
        r = self.wait()["result"]
        self.assertEqual(r["lists"][0]["count"], 1)                                  # Podcast fällt weg
        pl = self.s._pls().get(r["lists"][0]["id"])
        ref = pl["items"][0]["ref"]
        self.assertEqual(self.s.pl_state(pl["id"])["pl"]["items"][0]["url"], "https://open.spotify.com/track/sp1")
        self.assertEqual((ref["artist"], ref["title"], ref["mix"], ref["isrc"], ref["dur"]),
                         ("Mara Lind", "Kaltes Glas", "Extended Mix", "CHA012100002", 340))
        self.assertEqual(ref["url"], "https://open.spotify.com/track/sp1")
        self.assertEqual(pl["folder"], "Spotify")
        # #282: sicherer Treffer (ISRC) gleich verknüpft; erneutes Holen behält die Verknüpfung
        self.assertEqual((r["linked"], pl["items"][0].get("path")), (1, os.path.join(self.B, "k.mp3")))
        self.s.pl_relink(pl["id"], [{"k": 0, "path": os.path.join(self.B, "n.mp3")}])      # von Hand umgehängt
        self.s.start_pl_source_import("spotify", ["pl1"])
        r2 = self.wait()["result"]
        self.assertEqual((r2["kept"], r2["linked"]), (1, 0))
        self.assertEqual(self.s._pls().get(pl["id"])["items"][0]["path"], os.path.join(self.B, "n.mp3"))
        # Online-Metadaten: ISRC-Suche, Link und ID als Vorschlag
        res = self.act("online", "fetch", [self.idx["k.mp3"]], mb=False, discogs=False, deezer=False, itunes=False,
                       spotify=True, soundcloud=False, lastfm=False, acoustid=False, mode="empty", album=True, date="full",
                       label=True, isrc=True, genre=True, bpm=False, track=False, names=False, cover="no", ids=True)
        by = {r["label"]: r["new"] for r in res["proposals"]}
        self.assertEqual(by["Album (Spotify)"], "Nachtfahrt EP")
        self.assertEqual(by["SPOTIFY_URL (Spotify)"], "https://open.spotify.com/track/sp1")
        self.assertEqual(by["Genre (Spotify)"], "Deep House")
        self.assertTrue(any(c[2].get("q") == "isrc:CHA012100002" for c in self.fake.calls))
        # #385: eigene Felder TXXX:SPOTIFY_* nur mit Option „own“, mit Hinweis auf die Developer Terms
        self.assertFalse(any(r["label"].startswith("SPOTIFY_ALBUM") for r in res["proposals"]))
        res = self.act("online", "fetch", [self.idx["k.mp3"]], mb=False, discogs=False, deezer=False, itunes=False,
                       spotify=True, soundcloud=False, lastfm=False, acoustid=False, mode="empty", album=True, date="full",
                       label=True, isrc=True, genre=True, bpm=False, track=False, names=False, cover="no", ids=True, own=True)
        own = {"TXXX:" + r["label"].split(" (")[0]: r for r in res["proposals"] if r["label"].startswith("SPOTIFY_")}
        self.assertEqual(own["TXXX:SPOTIFY_ALBUM_ID"]["new"], "al1")
        self.assertEqual(own["TXXX:SPOTIFY_ARTIST_ID"]["new"], "ar1")
        self.assertEqual(own["TXXX:SPOTIFY_TITLE"]["new"], "Kaltes Glas (Extended Mix)")
        self.assertEqual(own["TXXX:SPOTIFY_TRACK"]["new"], "3/4")
        self.assertEqual(own["TXXX:SPOTIFY_DURATION"]["new"], "5:40")
        self.assertEqual(own["TXXX:SPOTIFY_EXPLICIT"]["new"], "0")
        self.assertEqual(own["TXXX:SPOTIFY_GENRE"]["new"], "Deep House")
        self.assertIn("TXXX:SPOTIFY_DATE", own)
        self.assertIn("Developer Terms", own["TXXX:SPOTIFY_ALBUM"]["hint"])
        # abgelaufener Token wird erneuert
        self.fake.token_ok.discard("SP-OK")
        self.assertIn("in Ordnung", self.act("spotify", "test")["message"])
        self.assertEqual(self.post.calls[-1][1]["grant_type"], "refresh_token")
        # gefolgte Künstler → Entdecken
        self.assertIn("2 Künstler gelesen", self.act("spotify", "follow")["message"])
        self.assertIn("Neu Artist", self.s.disc_overview()["follow"]["artists"])
        self.act("spotify", "logout", clear=False)
        self.assertNotIn("spotify", [x["id"] for x in self.s.dj_sources()["sources"]])

    def test_spotify_ideas_now_recent_push(self):
        """#384 SP2 + SP5: Läuft gerade / Zuletzt gehört → Ideen; Wunschliste als private Spotify-Playlist (nur ergänzen)."""
        self.login("spotify", client_id="CID", redirect="http://127.0.0.1:8765/callback")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.opened[-1]).query)
        for sc in ("user-read-currently-playing", "playlist-modify-private", "user-library-modify"):
            self.assertIn(sc, q["scope"][0])                                   # alle neuen Berechtigungen auf einmal
        ov = self.s.ideas_overview()
        self.assertTrue(ov["spotify"]["available"])
        self.assertIsNone(self.s.ideas_spotify_now()["track"])                # 204: nichts läuft
        self.fake.playing = SP2_TRACK
        now = self.s.ideas_spotify_now()["track"]
        self.assertEqual((now["artist"], now["title"], now["isrc"]), ("Lio Berg", "Morgenrot", "CHA012100009"))
        rec = self.s.ideas_spotify_recent(50)["tracks"]
        self.assertEqual([t["title"] for t in rec], ["Kaltes Glas", "Morgenrot"])   # ohne Doppel, neueste zuerst
        r = self.s.ideas_add_spotify("", [now, rec[0]], "")
        self.assertEqual(r["added"], 2)
        items = self.s.ideas_overview(r["pid"])["items"]
        self.assertEqual({i["src"] for i in items}, {"spotify"})
        self.assertTrue(all(i["url"].startswith("https://open.spotify.com/track/") for i in items))
        self.assertEqual(self.s.ideas_add_spotify(r["pid"], [now], "")["added"], 0)   # schon vorhanden
        # SP5: Vorschau, Anlegen (privat), zweites Mal nur ergänzen
        pv = self.s.ideas_sp_preview(r["pid"])
        self.assertEqual((pv["count"], pv["without"]), (1, 1))                # sp1 hat keine gültige 22-Zeichen-ID
        self.assertTrue(pv["name"].startswith("TagStudio_WISH_"))
        st = self.s.start_ideas_sp(r["pid"])
        self.assertTrue(st["ok"], st)
        res = self.wait()["result"]
        self.assertTrue(res["created"])
        self.assertEqual(self.fake.sp_items["wp1"], ["spotify:track:sp2xxxxxxxxxxxxxxxxxxx"])
        self.s.start_ideas_sp(r["pid"])
        res2 = self.wait()["result"]
        self.assertEqual((res2["created"], res2["added"], res2["existing"]), (False, 0, 1))
        self.assertFalse(any(c[0] == "DELETE" for c in self.write.calls))      # nie etwas entfernen
        # 403 (Entwicklungsmodus): verständliche Meldung
        self.write.status = 403
        self.s._pls().set_pushed(r["pid"], "spotify", {"id": ""})
        self.s.start_ideas_sp(r["pid"])
        st3 = self.wait()
        self.assertIn("403", str(st3.get("error") or st3.get("result")))
        # alte Anmeldung ohne neue Berechtigungen → Hinweis „neu anmelden“
        import plugins
        p = self.s.plugins.get("spotify")
        mod = p.load()
        a = mod.app(plugins.Context(p))
        a._save(token=json.dumps({**a.token, "scope": "playlist-read-private user-read-recently-played"}))
        self.assertIn("user-read-currently-playing", self.s.ideas_overview()["spotify"]["missing"])
        with self.assertRaises(Exception):
            self.s.ideas_spotify_now()

    def test_spotify_library(self):
        """#384 SP6: „In deiner Spotify-Bibliothek“ prüfen (nur lesen) und markierte auf Klick speichern."""
        self.login("spotify", client_id="CID", redirect="http://127.0.0.1:8765/callback")
        self.fake.playing = SP2_TRACK
        now = self.s.ideas_spotify_now()["track"]
        rec = self.s.ideas_spotify_recent(50)["tracks"]
        r = self.s.ideas_add_spotify("", [now, rec[0]], "")
        pid = r["pid"]
        lib = self.s.ideas_sp_library(pid)
        self.assertEqual(list(lib["state"].values()), [False])                 # ein Eintrag mit gültiger ID
        self.assertEqual(lib["without"], 1)
        k = next(iter(lib["state"]))
        self.assertEqual(self.write.calls, [])                                   # Prüfen schreibt nichts
        bad = self.s.start_ideas_sp_save(pid, [1 - k])                          # nur Eintrag ohne ID markiert
        self.assertFalse(bad["ok"])
        st = self.s.start_ideas_sp_save(pid, [0, 1])
        self.assertTrue(st["ok"], st)
        res = self.wait()["result"]
        self.assertEqual(res["saved"], 1)
        self.assertEqual(self.fake.saved, {"spotify:track:sp2xxxxxxxxxxxxxxxxxxx"})
        self.assertEqual([c[0] for c in self.write.calls], ["PUT"])
        self.assertEqual(self.s.ideas_sp_library(pid)["state"], {k: True})

    def test_spotify_discover(self):
        """#384 SP1: Entdecken mit Quelle Spotify – neue Singles/Alben gefolgter Künstler, alte bleiben weg."""
        self.login("spotify", client_id="CID", redirect="http://127.0.0.1:8765/callback")
        import discover
        d = discover.load()
        d["follow"]["artists"] = ["Mara Lind", "Unbekannt"]
        d["follow"]["sources"] = ["spotify"]
        discover.save(d)
        self.assertTrue(self.s.disc_overview()["spotify"])
        st = self.s.start_disc_run()
        self.assertTrue(st["ok"], st)
        r = self.wait()["result"]
        self.assertEqual(r["new"], 1, r)
        e = discover.load()["items"]["spotify:sp9"]
        self.assertEqual((e["artist"], e["title"], e["mix"], e["release"], e["src"]),
                         ("Mara Lind", "Neue Single", "Club Mix", "Neue Single", "spotify"))
        self.assertFalse(any(k.startswith("spotify:") and "al0" in k for k in discover.load()["items"]))
        n_search = sum(1 for c in self.fake.calls if c[1] == "/v1/search" and c[2].get("type") == "artist")
        self.s.start_disc_run()
        self.wait()
        self.assertEqual(sum(1 for c in self.fake.calls if c[1] == "/v1/search" and c[2].get("type") == "artist"), n_search)
        # Idee merken übernimmt die Spotify-ID (für „Als Spotify-Playlist“)
        res = self.s.ideas_from_disc(["spotify:sp9"], "", "Neu")
        it = self.s.ideas_overview(res["pid"])["items"][0]
        self.assertEqual((it["store"], it["sid"]), ("spotify", "sp9"))

    def test_spotify_saved_albums(self):
        """#384 SP3: gespeicherte Alben erscheinen beim Import als eigene Playlists mit allen Titeln."""
        self.login("spotify", client_id="CID", redirect="http://127.0.0.1:8765/callback")
        self.s.start_dj_source_list("spotify")
        lists = self.wait()["result"]["playlists"]
        alb = [p for p in lists if p["id"] == "album:al1"]
        self.assertEqual(len(alb), 1)
        self.assertEqual(alb[0]["name"], "Album: Nachtfahrt EP – Mara Lind")
        self.s.start_pl_source_import("spotify", ["album:al1"])
        r = self.wait()["result"]
        pl = self.s._pls().get(r["lists"][0]["id"])
        self.assertEqual([i["ref"]["title"] for i in pl["items"]], ["Kaltes Glas", "Nordlicht"])
        self.assertEqual(pl["name"], "Nachtfahrt EP – Mara Lind")

    def test_spotify_album_lookup(self):
        """#384 SP4: „Album nachschlagen (Spotify)“ – ganzes Album mit wenigen Anfragen, Titelnummern, kein Label."""
        self.login("spotify", client_id="CID", redirect="http://127.0.0.1:8765/callback")
        n0 = len(self.fake.calls)
        res = self.act("spotify", "album", [self.idx["k.mp3"], self.idx["n.mp3"]], title="Nachtfahrt EP", artist="Mara Lind",
                       mode="empty", date="full", cover="missing", names=False, ids=True, own=False)
        self.assertIn("1 von 1 Album", res["message"])
        self.assertIn("2 von 2 Titel", res["message"])
        by = {(r["name"], r["label"]): r["new"] for r in res["proposals"]}
        self.assertEqual(by[("k.mp3", "Titelnummer (Spotify)")], "1/2")
        self.assertEqual(by[("n.mp3", "Titelnummer (Spotify)")], "2/2")
        self.assertEqual(by[("k.mp3", "Album (Spotify)")], "Nachtfahrt EP")
        self.assertEqual(by[("k.mp3", "Datum (Spotify)")], "2021-05-14")
        self.assertEqual(by[("k.mp3", "Genre (Spotify)")], "Deep House")
        self.assertEqual(by[("n.mp3", "SPOTIFY_TRACK_ID (Spotify)")], "sp3")
        self.assertFalse(any(r["label"].startswith("Label") for r in res["proposals"]))
        self.assertTrue(any(r.get("kind") == "cover" for r in res["proposals"]))
        api = [c for c in self.fake.calls[n0:] if c[0] == "api.spotify.com"]
        self.assertLessEqual(len(api), 4, api)                                 # Suche, Album, Künstler (+ Cover extern)
        res2 = self.act("spotify", "album", [self.idx["n.mp3"]], title="Gibt es nicht", artist="", mode="empty",
                        date="year", cover="no", names=False, ids=True, own=False)
        self.assertIn("0 von 1", res2["message"])

    def test_soundcloud(self):
        self.login("soundcloud", client_id="SCID", client_secret="SECRET", redirect="http://127.0.0.1:8766/callback")
        self.assertEqual(self.post.calls[-1][1]["client_secret"], "SECRET")          # SoundCloud verlangt das Secret
        self.s.start_dj_source_list("soundcloud")
        lists = self.wait()["result"]["playlists"]
        self.assertEqual([p["id"] for p in lists], ["likes", "uploads", "soundcloud:playlists:5"])
        self.s.start_pl_source_import("soundcloud", ["soundcloud:playlists:5", "likes"])
        r = self.wait()["result"]
        pl = self.s._pls().get(r["lists"][0]["id"])
        ref = pl["items"][0]["ref"]
        self.assertEqual((ref["artist"], ref["title"], ref["mix"], ref["isrc"], ref["url"]),
                         ("Mara Lind", "Nordlicht", "Club Mix", "CHA012100001", "https://soundcloud.com/maralind/nordlicht"))
        res = self.act("online", "fetch", [self.idx["n.mp3"]], mb=False, discogs=False, deezer=False, itunes=False,
                       spotify=False, soundcloud=True, lastfm=False, acoustid=False, mode="empty", album=True, date="full",
                       label=True, isrc=True, genre=True, bpm=True, track=False, names=False, cover="no", ids=True)
        by = {r["label"]: r["new"] for r in res["proposals"]}
        self.assertEqual(by["SOUNDCLOUD_URL (SoundCloud)"], "https://soundcloud.com/maralind/nordlicht")
        self.assertEqual(by["Genre (SoundCloud)"], "Techno")
        self.assertIn("1 Konten gelesen", self.act("soundcloud", "follow")["message"])
        self.assertIn("127.0.0.1", self.act("soundcloud", "login", method="paste", url="", redirect="https://example.com/cb")["message"])   # nur lokal


if __name__ == "__main__":
    unittest.main()
