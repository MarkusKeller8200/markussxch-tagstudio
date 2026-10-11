"""Entdecken (#120): Deezer/Beatport mit nachgebauten Antworten, Merkliste, „schon vorhanden“, Vorschläge zum Folgen."""
import os
import time
import unittest
from unittest import mock

from helpers import write_mp3, text
from test_tagger_tools import Base

import discover

RECENT = time.strftime("%Y-%m-%d", time.localtime(time.time() - 5 * 86400))
OLD = "2001-01-01"

DZ = {
    "/search/artist?q=Mara+Lind&limit=5": {"data": [{"id": 7, "name": "Mara Lind"}]},
    "/search/artist?q=Niemand&limit=5": {"data": []},
    "/artist/7/albums?limit=25": {"data": [{"id": 70, "release_date": RECENT}, {"id": 71, "release_date": OLD}]},
    "/album/70": {"id": 70, "title": "Neu EP", "label": "Nordwerk", "release_date": RECENT, "cover_medium": "https://c/1.jpg",
                  "tracks": {"data": [
                      {"id": 701, "title": "Golden Hour (Extended Mix)", "preview": "https://p/701.mp3", "link": "https://www.deezer.com/track/701",
                       "artist": {"name": "Mara Lind"}},
                      {"id": 702, "title": "Morgenrot", "preview": "https://p/702.mp3", "artist": {"name": "Mara Lind"}},
                      {"id": 703, "title": "Fremd", "artist": {"name": "Jemand Anders"}}]}},
    "/album/71": {"id": 71, "title": "Alt", "release_date": OLD, "tracks": {"data": [{"id": 711, "title": "Alt", "artist": {"name": "Mara Lind"}}]}},
    '/search?q=label%3A%22Nordwerk%22&limit=50': {"data": [{"id": 701, "album": {"id": 70}}]},
}


def fake_fetch(url, timeout=20):
    path = url.replace(discover.DEEZER, "")
    if path not in DZ:
        return {"error": {"message": f"unbekannt {path}"}}
    return DZ[path]


class FakeBP:
    def __init__(self):
        self.calls = []

    def get(self, path, **params):
        self.calls.append((path, params))
        if path == "/catalog/search/":
            kind = params["type"]
            return {kind: [{"id": 5, "name": params["q"]}]}
        if path == "/catalog/tracks/":
            return [{"id": 900, "name": "Golden Hour", "mix_name": "Original Mix", "slug": "golden-hour",
                     "artists": [{"name": "Mara Lind"}], "publish_date": RECENT, "sample_url": "https://bp/900.mp3",
                     "release": {"name": "Neu", "label": {"name": "Nordwerk"}, "image": {"dynamic_uri": "https://i/{w}x{h}.jpg"}},
                     "bpm": 124, "key": {"name": "A Minor"}, "genre": {"name": "Techno"}},
                    {"id": 901, "name": "Uralt", "artists": [{"name": "Mara Lind"}], "publish_date": OLD}]
        if path == "/catalog/genres/":
            return {"results": [{"id": 6, "name": "Techno (Peak Time / Driving)"}]}
        if path.startswith("/catalog/genres/"):
            return {"results": [{"id": 950, "name": "Hit", "artists": [{"name": "X"}], "publish_date": OLD}]}
        return None


@mock.patch.object(discover, "fetch_json", fake_fetch)
@mock.patch.object(discover, "_throttle", lambda: None)
class TestDiscover(Base):
    def test_deezer_artist_and_label(self):
        e = discover.deezer_artist("Mara Lind", 60)
        self.assertEqual([x["id"] for x in e], ["701", "702"])            # nur neue, nur dieser Künstler
        self.assertEqual((e[0]["title"], e[0]["mix"], e[0]["label"]), ("Golden Hour", "Extended Mix", "Nordwerk"))
        self.assertEqual(e[0]["preview"], "https://p/701.mp3")
        lab = discover.deezer_label("Nordwerk", 60)
        self.assertEqual(len(lab), 3)
        log = []
        self.assertEqual(discover.deezer_artist("Niemand", 60, log.append), [])
        self.assertIn("Deezer", log[0])

    def test_beatport(self):
        bp = FakeBP()
        e = discover.beatport_artist(bp, "Mara Lind", 60)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["url"], "https://www.beatport.com/track/golden-hour/900")
        self.assertEqual(e[0]["cover"], "https://i/250x250.jpg")
        self.assertEqual((e[0]["bpm"], e[0]["key_name"], e[0]["genre"]), (124, "A Minor", "Techno"))
        self.assertEqual(discover.beatport_genres(bp), [{"id": 6, "name": "Techno (Peak Time / Driving)"}])
        self.assertEqual(len(discover.beatport_genre(bp, 6, "Techno")), 1)          # Charts ohne Datumsfilter

    def test_run_merge_owned(self):
        d = discover.load()
        d["follow"].update(artists=["Mara Lind"], labels=[], genres=[{"id": 6, "name": "Techno"}], sources=["deezer", "beatport"])
        found = discover.run(d, FakeBP())
        self.assertEqual(sorted(x["key"] for x in found), ["beatport:900", "beatport:950", "deezer:701", "deezer:702"])
        lib = os.path.join(self.dir, "Lib")
        os.makedirs(lib)
        write_mp3(os.path.join(lib, "g.mp3"), [text("TIT2", "Golden Hour (Original Mix)"), text("TPE1", "Mara Lind")])
        from id3tags import MP3File
        idx = discover.owned_index([MP3File(os.path.join(lib, "g.mp3"))])
        self.assertEqual(discover.merge(d, found, idx), 4)
        self.assertTrue(d["items"]["deezer:701"]["owned"])
        self.assertFalse(d["items"]["deezer:702"]["owned"])
        d["items"]["deezer:702"]["status"] = "saved"
        self.assertEqual(discover.merge(d, found, idx), 0)                    # Status bleibt
        self.assertEqual(d["items"]["deezer:702"]["status"], "saved")
        discover.save(d)
        self.assertEqual(len(discover.load()["items"]), 4)

    def test_session(self):
        from session import Session
        s = Session()
        self.assertFalse(s.start_disc_run()["ok"])                          # nichts zum Folgen
        ov = s.disc_follow_save({"artists": ["Mara Lind", "mara lind", ""], "labels": ["Nordwerk"], "days": 30,
                                 "sources": ["deezer", "spotify"]})
        self.assertEqual(ov["follow"]["artists"], ["Mara Lind"])
        self.assertEqual(ov["follow"]["sources"], ["deezer"])
        self.assertTrue(s.start_disc_run()["ok"])
        for _ in range(500):
            st = s.task_status()
            if st.get("done"):
                break
            time.sleep(0.02)
        self.assertIsNone(st["error"], st)
        self.assertTrue(st.get("done"), st)
        self.assertEqual(st["result"]["new"], 3, st)        # 701, 702 (Künstler) + 703 (Label); doppelte nur einmal
        ov = s.disc_set(["deezer:702"], "saved")
        self.assertEqual(ov["counts"]["saved"], 1)
        with self.assertRaises(ValueError):
            s.disc_set(["deezer:702"], "egal")

    def test_suggest(self):
        lib = os.path.join(self.dir, "Lib2")
        os.makedirs(lib)
        for i, (a, lab) in enumerate([("Mara Lind", "Nordwerk"), ("Mara Lind & Kai Ost", "Nordwerk"), ("Kai Ost", "")]):
            write_mp3(os.path.join(lib, f"{i}.mp3"), [text("TIT2", f"T{i}"), text("TPE1", a)] + ([text("TPUB", lab)] if lab else []))
        from id3tags import MP3File
        r = discover.suggest_follow([MP3File(os.path.join(lib, f"{i}.mp3")) for i in range(3)])
        self.assertEqual([x["name"] for x in r["artists"]], ["Kai Ost", "Mara Lind"])
        self.assertEqual(r["labels"], [{"name": "Nordwerk", "count": 2}])


if __name__ == "__main__":
    unittest.main()
