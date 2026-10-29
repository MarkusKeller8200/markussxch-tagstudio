"""Entdecken (#120): Deezer/Beatport mit nachgebauten Antworten, Merkliste, „schon vorhanden“, Vorschläge zum Folgen."""
import os
import time
import unittest
from unittest import mock

from helpers import write_mp3, text
from test_tagger_tools import Base

import discover
import json
import onlinematch

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


def fake_http(url, headers=None):
    """#204: Abruf des Plugins Deezer (über onlinematch)."""
    d = fake_fetch(url)
    return 200, {}, json.dumps(d).encode()


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
@mock.patch.object(onlinematch, "http_get", fake_http)
@mock.patch.dict(onlinematch.INTERVALS, {"api.deezer.com": 0})
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
                                 "sources": ["deezer", "napster"]})
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
        # #204: Deezer läuft über das Plugin – ausgeschaltet → übersprungen mit Hinweis
        s.plugin_enable("deezer", False)
        self.assertTrue(s.start_disc_run()["ok"])
        for _ in range(500):
            st = s.task_status()
            if st.get("done"):
                break
            time.sleep(0.02)
        self.assertEqual(st["result"]["found"], 0, st)
        self.assertTrue(any("Plugin „Deezer“ ist ausgeschaltet" in ln for ln in st["result"]["log"]), st)

    def test_auto_export_bought(self):
        """#162: tägliche Suche im Hintergrund, Merkliste exportieren, Beatport-Käufe als gekauft."""
        from session import Session
        s = Session()
        self.assertFalse(s.disc_auto()["started"])                          # aus
        s.disc_follow_save({"artists": ["Mara Lind"], "sources": ["deezer"], "auto": True})
        self.assertTrue(discover.load()["follow"]["auto"])
        self.assertTrue(s.disc_auto()["started"])
        for _ in range(500):
            if not s.disc_auto_status()["running"]:
                break
            time.sleep(0.02)
        st = s.disc_auto_status()
        self.assertEqual((st["auto_new"], st["count_new"]), (2, 2))
        self.assertFalse(s.disc_auto()["started"])                          # heute schon gesucht
        s.disc_set(["deezer:702"], "saved")
        dest = os.path.join(self.dir, "Merkliste.csv")
        r = s.disc_export_write("csv", dest, "saved")
        self.assertEqual(r["count"], 1)
        with open(dest, encoding="utf-8-sig") as fh:
            txt = fh.read()
        self.assertIn("Morgenrot", txt)
        self.assertNotIn("Golden Hour", txt)
        n = discover.mark_bought([{"id": 1, "name": "Golden Hour", "artists": [{"name": "Mara Lind"}]}])
        self.assertEqual(n, 1)
        self.assertEqual(discover.load()["items"]["deezer:701"]["status"], "bought")
        self.assertEqual(discover.mark_bought([{"id": 1, "name": "Golden Hour", "artists": [{"name": "Mara Lind"}]}]), 0)

    def test_suggest(self):
        lib = os.path.join(self.dir, "Lib2")
        os.makedirs(lib)
        for i, (a, lab) in enumerate([("Mara Lind", "Nordwerk"), ("Mara Lind & Kai Ost", "Nordwerk"), ("Kai Ost", "")]):
            write_mp3(os.path.join(lib, f"{i}.mp3"), [text("TIT2", f"T{i}"), text("TPE1", a)] + ([text("TPUB", lab)] if lab else []))
        from id3tags import MP3File
        r = discover.suggest_follow([MP3File(os.path.join(lib, f"{i}.mp3")) for i in range(3)])
        self.assertEqual([x["name"] for x in r["artists"]], ["Kai Ost", "Mara Lind"])
        self.assertEqual(r["labels"], [{"name": "Nordwerk", "count": 2}])

    def test_follow_clear_purchased(self):
        """#291: direkt folgen/entfernen, leeren, gekaufte markieren, ähnliche, My Beatport."""
        d = discover.load()
        self.assertTrue(discover.follow_edit(d, "artists", "Mara Lind"))
        self.assertFalse(discover.follow_edit(d, "artists", "mara lind"))           # keine Doppelten
        self.assertTrue(discover.follow_edit(d, "labels", "Nordwerk"))
        d["follow"]["bp"]["labels"] = ["Nordwerk"]
        self.assertTrue(discover.follow_edit(d, "labels", "NORDWERK", add=False))
        self.assertEqual((d["follow"]["labels"], d["follow"]["bp"]["labels"]), ([], []))
        with self.assertRaises(ValueError):
            discover.follow_edit(d, "genres", "x")
        for k, st, mix in [("beatport:900", "new", "Original Mix"), ("deezer:1", "saved", ""), ("deezer:2", "hidden", ""),
                           ("deezer:3", "bought", ""), ("deezer:4", "new", "Club Mix")]:
            d["items"][k] = {"key": k, "artist": "Mara Lind, Kai Ost", "title": "Golden Hour" if k != "deezer:1" else "Morgenrot",
                             "mix": mix, "status": st}
        bought = [{"store": "beatport", "id": "900", "title": "Anders", "artist": "X", "bought": "2026-10-01T10:00:00"},
                  {"store": "beatport", "id": "5", "title": "Golden Hour", "mix": "Extended Mix", "artist": "Kai Ost", "bought": "2026-09-01"}]
        self.assertEqual(discover.mark_purchased(d, bought), 3)          # 900 per ID; deezer:2/3 ohne Mix; Club Mix ≠ Extended
        self.assertEqual(d["items"]["beatport:900"]["purchased"], "2026-10-01")
        self.assertNotIn("purchased", d["items"]["deezer:4"])
        self.assertEqual(discover.mark_purchased(d, []), 0)
        self.assertNotIn("purchased", d["items"]["beatport:900"])
        self.assertEqual(discover.clear(d), 3)                           # new, hidden, new
        self.assertEqual(sorted(d["items"]), ["deezer:1", "deezer:3"])
        # ähnliche Künstler über Deezer, ohne gefolgte
        dz = lambda path, **p: {"/search/artist": {"data": [{"id": 7, "name": p.get("q")}]},  # noqa: E731
                                "/artist/7/related": {"data": [{"name": "Kai Ost"}, {"name": "Mara Lind"}]}}[path]
        r = discover.related_artists(["Mara Lind", "Uli Berg"], dz)
        self.assertEqual(r, [{"name": "Kai Ost", "count": 2, "because": ["Mara Lind", "Uli Berg"]}])
        # My Beatport: Einträge mit oder ohne Hülle „track“
        bp = FakeBP()
        bp.get = lambda path, **p: {"results": [{"track": {"id": 1, "name": "A", "publish_date": RECENT}},
                                                {"id": 2, "name": "B", "publish_date": OLD}]}
        self.assertEqual([e["key"] for e in discover.beatport_feed(bp, 60)], ["beatport:1"])

    def test_session_follow_edit_clear(self):
        from session import Session
        s = Session()
        ov = s.disc_follow_edit("artists", "Mara Lind", True)
        self.assertEqual(ov["follow"]["artists"], ["Mara Lind"])
        d = discover.load()
        d["follow"]["bp"]["artists"] = ["Mara Lind"]
        d["items"]["beatport:9"] = {"key": "beatport:9", "artist": "Mara Lind", "title": "T", "status": "new"}
        d["items"]["deezer:8"] = {"key": "deezer:8", "artist": "Mara Lind", "title": "U", "status": "saved"}
        discover.save(d)
        s._purch().merge("beatport", "Beatport", [{"id": 9, "title": "T", "artist": "Mara Lind"}])
        ov = s.disc_overview()
        self.assertEqual(ov["purchased"], 1)
        self.assertEqual(ov["counts"]["bought"], 1)
        self.assertTrue(next(e for e in ov["items"] if e["key"] == "beatport:9")["purchased"])
        ov = s.disc_follow_save(dict(ov["follow"], artists=["Mara Lind", "Kai Ost"]))
        self.assertEqual(ov["follow"]["bp"]["artists"], ["Mara Lind"])     # Herkunft bleibt beim Speichern
        ov = s.disc_clear()
        self.assertEqual((ov["removed"], [e["key"] for e in ov["items"]]), (1, ["deezer:8"]))
        self.assertFalse(s.start_disc_bp_follow()["ok"])                   # Beatport nicht angemeldet
        ov = s.disc_follow_edit("artists", "mara lind", False)
        self.assertEqual((ov["follow"]["artists"], ov["follow"]["bp"]["artists"]), (["Kai Ost"], []))


if __name__ == "__main__":
    unittest.main()
