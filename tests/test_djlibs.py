"""#278/#279: Playlists aus Serato, Engine DJ, VirtualDJ lesen (nur lesen) und kopierte Tracklisten übernehmen."""
import hashlib
import os
import shutil
import sqlite3
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import djlibs  # noqa: E402
import playlists  # noqa: E402


def rec(tag, body: bytes) -> bytes:
    return tag.encode("latin-1") + struct.pack(">I", len(body)) + body


def crate(paths) -> bytes:
    out = rec("vrsn", "1.0/Serato ScratchLive Crate".encode("utf-16-be"))
    for p in paths:
        out += rec("otrk", rec("ptrk", p.encode("utf-16-be")))
    return out


def digest(folder):
    h = hashlib.sha1()
    for dp, _dn, fn in sorted(os.walk(folder)):
        for f in sorted(fn):
            with open(os.path.join(dp, f), "rb") as fh:
                h.update(f.encode() + fh.read())
    return h.hexdigest()


def make_engine(root, music):
    """Engine-DJ-2-Datenbank: Ordner „Sets“ mit „Freitag“ (b, a – verkettete Reihenfolge) und „Leer“."""
    os.makedirs(os.path.join(root, "Database2"))
    con = sqlite3.connect(os.path.join(root, "Database2", "m.db"))
    con.executescript("""
      CREATE TABLE Track (id INTEGER PRIMARY KEY, path TEXT, filename TEXT, title TEXT, artist TEXT, length INTEGER);
      CREATE TABLE Playlist (id INTEGER PRIMARY KEY, title TEXT, parentListId INTEGER, isPersisted INTEGER, nextListId INTEGER);
      CREATE TABLE PlaylistEntity (id INTEGER PRIMARY KEY, listId INTEGER, trackId INTEGER, databaseUuid TEXT, nextEntityId INTEGER);
    """)
    rel = os.path.relpath(music, root).replace("\\", "/")
    con.execute("INSERT INTO Track VALUES (1, ?, 'a.mp3', 'A', 'DJ', 300)", (rel + "/a.mp3",))
    con.execute("INSERT INTO Track VALUES (2, ?, 'b.mp3', 'B', 'DJ', 200)", (rel + "/b.mp3",))
    con.execute("INSERT INTO Track VALUES (3, ?, 'x.mp3', 'X', 'DJ', 100)", (rel + "/x.mp3",))
    # Reihenfolge: „Zuerst“ (id 4) vor „Sets“ (id 1); in Sets: „Leer“ (3) nach „Freitag“ (2)
    con.execute("INSERT INTO Playlist VALUES (1, 'Sets', 0, 1, 0)")
    con.execute("INSERT INTO Playlist VALUES (4, 'Zuerst', 0, 1, 1)")
    con.execute("INSERT INTO Playlist VALUES (2, 'Freitag', 1, 1, 3)")
    con.execute("INSERT INTO Playlist VALUES (3, 'Leer', 1, 1, 0)")
    con.execute("INSERT INTO PlaylistEntity VALUES (10, 2, 1, 'u', 0)")       # a ist das letzte
    con.execute("INSERT INTO PlaylistEntity VALUES (11, 2, 2, 'u', 10)")      # b zuerst
    con.execute("INSERT INTO PlaylistEntity VALUES (12, 4, 3, 'u', 0)")
    con.commit()
    con.close()


class TestReaders(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_djl_")
        self.music = os.path.join(self.dir, "Music")
        os.makedirs(self.music)
        for n in ("a.mp3", "b.mp3"):
            with open(os.path.join(self.music, n), "wb") as fh:
                fh.write(b"ID3")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_serato(self):
        root = os.path.join(self.dir, "_Serato_")
        os.makedirs(os.path.join(root, "Subcrates"))
        drive = os.path.splitdrive(self.music)[0]
        rel = os.path.relpath(self.music, drive + os.sep).replace("\\", "/")         # relativ zum Laufwerk
        with open(os.path.join(root, "Subcrates", "House%%Deep.crate"), "wb") as fh:
            fh.write(crate([rel + "/b.mp3", rel + "/a.mp3"]))
        with open(os.path.join(root, "Subcrates", "House.crate"), "wb") as fh:
            fh.write(crate([rel + "/a.mp3"]))
        before = digest(root)
        lists = djlibs.read_library("serato", self.dir)                 # Elternordner reicht
        self.assertEqual([(g["folder"], g["name"]) for g in lists], [("", "House"), ("House", "Deep")])
        self.assertEqual([os.path.basename(x["path"]) for x in lists[1]["items"]], ["b.mp3", "a.mp3"])
        self.assertTrue(all(os.path.isfile(x["path"]) for x in lists[1]["items"]))
        self.assertEqual(digest(root), before)                           # nur gelesen
        self.assertEqual(djlibs.find_libraries("serato", home=self.dir, volumes=[]), [])
        os.makedirs(os.path.join(self.dir, "home", "Music"))
        shutil.move(root, os.path.join(self.dir, "home", "Music", "_Serato_"))
        self.assertEqual(len(djlibs.find_libraries("serato", home=os.path.join(self.dir, "home"), volumes=[])), 1)

    def test_serato_base(self):
        self.assertEqual(djlibs.serato_base("/Volumes/USB/_Serato_"), "/Volumes/USB")
        self.assertEqual(djlibs.serato_base("/Users/x/Music/_Serato_"), "/")

    def test_engine(self):
        root = os.path.join(self.dir, "Engine Library")
        make_engine(root, self.music)
        before = digest(root)
        lists = djlibs.read_library("engine", os.path.join(root, "Database2", "m.db"))   # Datei reicht auch
        self.assertEqual([g["key"] for g in lists], ["Zuerst", "Sets/Freitag", "Sets/Leer"])
        fr = lists[1]
        self.assertEqual((fr["folder"], fr["name"]), ("Sets", "Freitag"))
        self.assertEqual([(os.path.basename(x["path"]), x["title"], x["dur"]) for x in fr["items"]], [("b.mp3", "B", 200), ("a.mp3", "A", 300)])
        self.assertTrue(os.path.isfile(fr["items"][0]["path"]))
        self.assertEqual(lists[2]["items"], [])
        self.assertEqual(digest(root), before)

    def test_engine_too_old(self):
        root = os.path.join(self.dir, "Engine Library")
        os.makedirs(os.path.join(root, "Database2"))
        sqlite3.connect(os.path.join(root, "Database2", "m.db")).execute("CREATE TABLE List (id INTEGER)").connection.commit()
        with self.assertRaises(ValueError):
            djlibs.read_library("engine", root)

    def test_vdj(self):
        root = os.path.join(self.dir, "VirtualDJ")
        os.makedirs(os.path.join(root, "Folders", "Sets"))
        os.makedirs(os.path.join(root, "Playlists"))
        a, b = os.path.join(self.music, "a.mp3"), os.path.join(self.music, "b.mp3")
        with open(os.path.join(root, "Folders", "Sets", "Freitag.vdjfolder"), "w", encoding="utf-8") as fh:
            fh.write(f'<?xml version="1.0"?><VirtualFolder><song path="{b}" artist="DJ" title="B" songlength="200.5" idx="0"/>'
                     f'<song path="{a}" idx="1"/></VirtualFolder>')
        with open(os.path.join(root, "Folders", "Neu.vdjfolder"), "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0"?><FilterFolder><filter>Year &gt; 2020</filter></FilterFolder>')
        with open(os.path.join(root, "Playlists", "Warm up.m3u"), "w", encoding="utf-8") as fh:
            fh.write(f"#EXTVDJ:<artist>DJ &amp; Co</artist><title>A</title><songlength>300</songlength>\n{a}\n")
        lists = djlibs.read_library("vdj", root)
        self.assertEqual([(g["folder"], g["name"]) for g in lists], [("Sets", "Freitag"), ("Playlists", "Warm up")])
        self.assertEqual([(x["title"], x["dur"]) for x in lists[0]["items"]], [("B", 200), ("", 0)])
        self.assertEqual((lists[1]["items"][0]["artist"], lists[1]["items"][0]["path"]), ("DJ & Co", a))

    def test_no_library(self):
        with self.assertRaises(ValueError):
            djlibs.read_library("serato", self.music)


class TestTracklist(unittest.TestCase):
    def test_parse(self):
        items, unknown = playlists.parse_tracklist(
            "01. [00:00] Artist A - Song One (Extended Mix) [LABEL]\nw/ Artist B ft. C - Song Two\n02 ID - ID\n"
            "Überschrift\n[1:02:03] DJ X – Tune (Remix)\n", "1001tracklists")
        self.assertEqual([(x["ref"]["artist"], x["ref"]["title"]) for x in items],
                         [("Artist A", "Song One (Extended Mix)"), ("Artist B ft. C", "Song Two"), ("DJ X", "Tune (Remix)")])
        self.assertEqual((unknown, items[0]["ref"]["source"]), (1, "1001tracklists"))

    def test_spotify_csv(self):
        items = playlists.parse_csv("Track URI,Track Name,Artist Name(s),Duration (ms),ISRC\n"
                                    "spotify:track:1,Song (Extended Mix),Art,215000,GB-123\n")
        self.assertEqual(items[0]["ref"], {"artist": "Art", "title": "Song (Extended Mix)", "mix": "", "isrc": "GB-123",
                                           "dur": 215, "source": "csv"})


class TestSessionImport(unittest.TestCase):
    def setUp(self):
        import core
        from helpers import text, write_mp3
        self.dir = tempfile.mkdtemp(prefix="ts_djs_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.music = os.path.join(self.dir, "Music")
        os.makedirs(self.music)
        for n, name in enumerate(("a", "b")):
            write_mp3(os.path.join(self.music, f"{name}.mp3"), [text("TIT2", name.upper()), text("TPE1", "DJ")], audio_seed=n + 1)

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    @staticmethod
    def wait(s, r):
        if r.get("ok") is False:
            return r
        while not s.task_status()["done"]:
            time.sleep(0.02)
        return s.task_status()["result"]

    def test_engine_import_update(self):
        from session import Session
        root = os.path.join(self.dir, "Music", "Engine Library")
        make_engine(root, self.music)
        s = Session()
        self.assertEqual(s.pl_dj_libraries("engine")["found"], [root])          # Standardort ~/Music
        scan = self.wait(s, s.start_pl_dj_scan("engine", root))
        fr = next(x for x in scan["lists"] if x["key"] == "Sets/Freitag")
        self.assertEqual((fr["count"], fr["missing"], fr["known"]), (2, 0, False))
        self.assertEqual(next(x for x in scan["lists"] if x["key"] == "Zuerst")["missing"], 1)
        r = self.wait(s, s.start_pl_dj_import("engine", root, ["Sets/Freitag", "Zuerst"]))
        self.assertEqual((len(r["lists"]), r["missing"]), (2, 1))
        self.assertEqual([x["name"] for x in r["lists"]], ["Zuerst", "Freitag"])            # Reihenfolge wie in Engine
        fid = r["lists"][1]["id"]
        cur = next(p for p in s.pl_state(fid)["playlists"] if p["id"] == fid)
        self.assertEqual((cur["folder"], cur["name"]), ("Engine DJ/Sets", "Freitag"))
        # erneut übernehmen → dieselbe Playlist wird aktualisiert, nicht doppelt
        n = len(s.pl_list()["playlists"])
        r2 = self.wait(s, s.start_pl_dj_import("engine", root, ["Sets/Freitag"]))
        self.assertEqual(r2["lists"][0]["id"], fid)
        self.assertEqual(len(s.pl_list()["playlists"]), n)
        self.assertTrue(next(x for x in self.wait(s, s.start_pl_dj_scan("engine", root))["lists"] if x["key"] == "Sets/Freitag")["known"])
        self.assertEqual(self.wait(s, s.start_pl_dj_scan("serato", self.music))["ok"], False)

    def test_text_import(self):
        from session import Session
        s = Session()
        st = s.pl_import_text("1. DJ - A\n2. ID - ID\n3. DJ - B (Extended Mix)", "Mix vom Freitag", "1001Tracklists", "1001tracklists")
        pl = next(p for p in st["playlists"] if p["id"] == st["sel"])
        self.assertEqual((pl["folder"], pl["name"], pl["count"]), ("1001Tracklists", "Mix vom Freitag", 2))
        self.assertIn("1 unbekannte", st["message"])
        with self.assertRaises(ValueError):
            s.pl_import_text("nur Text")


if __name__ == "__main__":
    unittest.main()
