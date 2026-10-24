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
            "disc_number": 1, "artists": [{"id": "ar1", "name": "Mara Lind"}], "external_ids": {"isrc": "cha012100002"},
            "external_urls": {"spotify": "https://open.spotify.com/track/sp1"},
            "album": {"id": "al1", "name": "Nachtfahrt EP", "release_date": "2021-05-14", "artists": [{"name": "Mara Lind"}],
                      "images": [{"url": "https://i.scdn.co/image/abc"}]}}
SC_TRACK = {"id": 77, "title": "Nordlicht (Club Mix)", "duration": 372000, "genre": "Techno", "bpm": 128,
            "permalink_url": "https://soundcloud.com/maralind/nordlicht", "user": {"username": "maralind"},
            "publisher_metadata": {"artist": "Mara Lind", "isrc": "CHA012100001", "release_title": "Nachtfahrt EP"},
            "artwork_url": "https://i1.sndcdn.com/artworks-x-large.jpg", "created_at": "2021/05/14 10:00:00 +0000"}


class Fake:
    """Spotify- und SoundCloud-API; prüft den Token im Kopf."""

    def __init__(self):
        self.calls, self.token_ok = [], {"SP-OK", "SC-OK", "SP-NEW", "SC-NEW"}

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
            if p == "/v1/search":
                hit = "cha012100002" in q["q"].lower() or "kaltes" in q["q"].lower()
                assert int(q["limit"]) <= 10
                return js({"tracks": {"items": [SP_TRACK] if hit else []}})
            if p == "/v1/tracks/sp1":
                return js(SP_TRACK)
            if p == "/v1/artists/ar1":
                return js({"id": "ar1", "genres": ["deep house"]})
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
        self._orig = (onlinematch.http_get, oauthkit.http_post, oauthkit.open_browser)
        onlinematch.http_get, oauthkit.http_post = self.fake, self.post
        self.opened = []
        oauthkit.open_browser = lambda url: self.opened.append(url) or True
        self._iv = dict(onlinematch.INTERVALS)
        for k in onlinematch.INTERVALS:
            onlinematch.INTERVALS[k] = 0
        self.idx = {os.path.basename(f.path): i for i, f in enumerate(self.s.tag_files)}

    def tearDown(self):
        onlinematch.http_get, oauthkit.http_post, oauthkit.open_browser = self._orig
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
        self.assertEqual([p["id"] for p in lists], ["liked", "pl1"])
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
        # Online-Metadaten: ISRC-Suche, Link und ID als Vorschlag
        res = self.act("online", "fetch", [self.idx["k.mp3"]], mb=False, discogs=False, deezer=False, itunes=False,
                       spotify=True, soundcloud=False, lastfm=False, acoustid=False, mode="empty", album=True, date="full",
                       label=True, isrc=True, genre=True, bpm=False, track=False, names=False, cover="no", ids=True)
        by = {r["label"]: r["new"] for r in res["proposals"]}
        self.assertEqual(by["Album (Spotify)"], "Nachtfahrt EP")
        self.assertEqual(by["SPOTIFY_URL (Spotify)"], "https://open.spotify.com/track/sp1")
        self.assertEqual(by["Genre (Spotify)"], "Deep House")
        self.assertTrue(any(c[2].get("q") == "isrc:CHA012100002" for c in self.fake.calls))
        # abgelaufener Token wird erneuert
        self.fake.token_ok.discard("SP-OK")
        self.assertIn("in Ordnung", self.act("spotify", "test")["message"])
        self.assertEqual(self.post.calls[-1][1]["grant_type"], "refresh_token")
        # gefolgte Künstler → Entdecken
        self.assertIn("2 Künstler gelesen", self.act("spotify", "follow")["message"])
        self.assertIn("Neu Artist", self.s.disc_overview()["follow"]["artists"])
        self.act("spotify", "logout", clear=False)
        self.assertNotIn("spotify", [x["id"] for x in self.s.dj_sources()["sources"]])

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
