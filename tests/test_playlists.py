"""Playlists (#267): Speicher, Ordner, Rückgängig, Archiv, Playlist-Ordner (M3U8) und Änderungen von aussen."""
import csv
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import playlists  # noqa: E402
from playlists import Store  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_pl_")
        self.root = os.path.join(self.dir, "data", "Playlists")
        self.mirror = os.path.join(self.dir, "base", "03_Playlists")
        self.arch = os.path.join(self.dir, "base", "02_Archiv")
        self.lib = os.path.join(self.dir, "base", "01_Library")
        os.makedirs(self.lib)
        self.a, self.b, self.c = (os.path.join(self.lib, n) for n in ("a.mp3", "Bär ö.mp3", "c.mp3"))
        for p in (self.a, self.b, self.c):
            open(p, "wb").close()
        self.s = Store(self.root, self.mirror, self.arch)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def m3u(self, *rel):
        return os.path.join(self.mirror, *rel)

    def read(self, *rel):
        with open(self.m3u(*rel), encoding="utf-8") as fh:
            return fh.read()

    def reopen(self):
        return Store(self.root, self.mirror, self.arch)


class TestStore(Base):
    def test_create_items_and_mirror(self):
        pl = self.s.create("Freitag  Warm-up", "Sets / 2026", items=[{"path": self.a, "artist": "DJ", "title": "A", "dur": 300}, self.b])
        self.assertEqual((pl["name"], pl["folder"], len(pl["items"])), ("Freitag Warm-up", "Sets/2026", 2))
        text = self.read("Sets", "2026", "Freitag Warm-up.m3u8")
        self.assertIn("#EXTINF:300,DJ - A", text)
        self.assertIn(os.path.join("..", "..", "01_Library", "a.mp3"), text)            # relativ zur M3U8
        self.assertIn("Bär ö.mp3", text)
        s2 = self.reopen()                                                             # bleibt nach Neustart
        self.assertEqual([p["name"] for p in s2.active()], ["Freitag Warm-up"])
        self.assertEqual(s2.folders(), ["Sets", "Sets/2026"])
        parsed = playlists.parse_m3u(text, self.m3u("Sets", "2026"))
        self.assertEqual([os.path.normcase(e["path"]) for e in parsed], [os.path.normcase(self.a), os.path.normcase(self.b)])
        with self.assertRaises(ValueError):
            self.s.create("freitag warm-up", "Sets/2026")                              # Name im Ordner vergeben
        self.s.create("Freitag Warm-up", "")                                           # anderer Ordner: erlaubt

    def test_duplicates_ask_add_skip(self):
        pl = self.s.create("P", items=[self.a])
        r = self.s.add(pl["id"], [self.a, self.b], "ask")
        self.assertEqual((r["ask"], r["dupes"], r["new"], len(self.s.get(pl["id"])["items"])), (True, 1, 1, 1))
        self.assertEqual(self.s.add(pl["id"], [self.a, self.b], "skip")["added"], 1)
        self.assertEqual(self.s.add(pl["id"], [self.a], "add")["added"], 1)            # E5: Doppelte erlaubt
        self.assertEqual([os.path.basename(x["path"]) for x in self.s.get(pl["id"])["items"]], ["a.mp3", "Bär ö.mp3", "a.mp3"])
        self.assertEqual(self.s.recent()[0], pl["id"])

    def test_order_remove_undo_redo(self):
        pl = self.s.create("P", items=[self.a, self.b, self.c])
        pid = pl["id"]
        self.s.order(pid, [2, 0, 1])
        names = lambda: [os.path.basename(x["path"]) for x in self.s.get(pid)["items"]]  # noqa: E731
        self.assertEqual(names(), ["c.mp3", "a.mp3", "Bär ö.mp3"])
        self.assertEqual(self.s.remove(pid, [0]), 1)
        self.assertEqual(names(), ["a.mp3", "Bär ö.mp3"])
        self.assertEqual(self.s.undo(), "Titel entfernen")
        self.assertEqual(names(), ["c.mp3", "a.mp3", "Bär ö.mp3"])
        self.s.undo()
        self.assertEqual(names(), ["a.mp3", "Bär ö.mp3", "c.mp3"])
        self.s.redo()
        self.assertEqual(names(), ["c.mp3", "a.mp3", "Bär ö.mp3"])
        self.assertIn("c.mp3", self.read("P.m3u8").splitlines()[3])                   # Ordner folgt dem Rückgängig
        self.s.undo()
        self.s.undo()                                                                  # Anlegen rückgängig
        self.assertFalse(self.s.exists(pid))
        self.assertFalse(os.path.exists(self.m3u("P.m3u8")))
        with self.assertRaises(ValueError):
            self.s.undo()

    def test_rename_move_duplicate_merge_folders(self):
        p = self.s.create("Alt", "A", items=[self.a])
        q = self.s.create("Zwei", "A", items=[self.b])
        self.s.rename(p["id"], "Neu")
        self.assertTrue(os.path.isfile(self.m3u("A", "Neu.m3u8")))
        self.assertFalse(os.path.exists(self.m3u("A", "Alt.m3u8")))
        self.s.move(p["id"], "B")
        self.assertTrue(os.path.isfile(self.m3u("B", "Neu.m3u8")))
        d = self.s.duplicate(p["id"])
        self.assertEqual((d["name"], d["folder"]), ("Neu (Kopie)", "B"))
        self.assertEqual(self.s.duplicate(p["id"])["name"], "Neu (Kopie 2)")
        m = self.s.merge([p["id"], q["id"]], "Alle", "")
        self.assertEqual(len(m["items"]), 2)
        self.s.folder_create("Leer/Unter")
        self.assertIn("Leer/Unter", self.s.folders())
        self.s.folder_rename("B", "C/B")
        self.assertEqual(self.s.get(p["id"])["folder"], "C/B")
        self.assertTrue(os.path.isfile(self.m3u("C", "B", "Neu.m3u8")))
        with self.assertRaises(ValueError):
            self.s.folder_remove("C")                                                  # enthält Playlists
        self.s.folder_remove("Leer")
        self.assertNotIn("Leer", self.s.folders())
        with self.assertRaises(ValueError):
            self.s.folder_rename("C", "C/D")

    def test_safe_filenames(self):
        p = self.s.create('A/B: "x"?', items=[self.a])
        self.s.create("CON", items=[self.a])
        self.assertEqual(os.path.basename(self.s.mirror_path(p["id"])), "A_B_ _x__.m3u8")
        self.assertTrue(os.path.isfile(self.m3u("CON_.m3u8")))


class TestArchive(Base):
    def test_archive_restore_delete(self):
        p = self.s.create("Set", "Sets", items=[self.a])
        self.s.archive(p["id"])
        self.assertEqual([x["id"] for x in self.s.archived()], [p["id"]])
        self.assertFalse(self.s.active())
        self.assertFalse(os.path.exists(self.m3u("Sets", "Set.m3u8")))
        dst = os.path.join(self.arch, "_Playlists", "Sets", "Set.m3u8")
        self.assertTrue(os.path.isfile(dst))
        with open(os.path.join(self.arch, "_aussortiert.csv"), encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        self.assertEqual(rows[1][2:4], [dst, "Playlists"])
        with self.assertRaises(ValueError):
            self.s.update(p["id"], name="x")                                           # archiviert: nicht änderbar
        with self.assertRaises(ValueError):
            self.s.delete(self.s.create("Aktiv")["id"])                                # nur archivierte löschen
        self.s.create("Set", "Sets")                                                   # Name wieder frei
        self.s.restore(p["id"])
        self.assertEqual(self.s.get(p["id"])["name"], "Set (2)")
        self.assertTrue(os.path.isfile(self.m3u("Sets", "Set (2).m3u8")))
        self.assertFalse(os.path.exists(dst))
        with open(os.path.join(self.arch, "_aussortiert.csv"), encoding="utf-8-sig") as fh:
            self.assertTrue(list(csv.reader(fh, delimiter=";"))[1][4])                 # als zurückgeholt vermerkt
        self.s.archive(p["id"])
        self.s.delete(p["id"])
        self.assertFalse(self.s.exists(p["id"]))
        self.assertFalse(os.listdir(os.path.join(self.arch, "_Playlists", "Sets")))

    def test_archive_folder_and_no_archive_dir(self):
        s = Store(self.root, self.mirror, "")
        s.create("Eins", "X/Y", items=[self.a])
        s.create("Zwei", "X", items=[self.a])
        self.assertEqual(s.archive_folder("X"), 2)
        self.assertNotIn("X", s.folders())
        self.assertTrue(os.path.isfile(os.path.join(self.mirror, "_Archiv", "X", "Y", "Eins.m3u8")))
        self.assertEqual(s.external_changes(), [])                                     # _Archiv zählt nicht

    def test_without_mirror(self):
        s = Store(self.root, "", "")
        p = s.create("Ohne", items=[self.a])
        self.assertEqual(s.mirror_path(p["id"]), "")
        s.archive(p["id"])
        s.restore(p["id"])
        self.assertEqual(s.external_changes(), [])


class TestExternal(Base):
    def test_changed_removed_new(self):
        p = self.s.create("Set", items=[{"path": self.a, "lock": True, "title": "A"}, self.b])
        path = self.m3u("Set.m3u8")
        with open(path, "w", encoding="utf-8") as fh:                                  # anderes Programm ändert
            fh.write("#EXTM3U\n#EXTINF:200,X - C\n../01_Library/c.mp3\n../01_Library/a.mp3\n")
        ch = self.s.external_changes()
        self.assertEqual([(c["kind"], c["id"]) for c in ch], [("changed", p["id"])])
        self.s.update(p["id"], note="Notiz")                                           # TagStudio überschreibt nicht
        self.assertIn("c.mp3", self.read("Set.m3u8"))
        self.s.apply_external("Set.m3u8", "take")
        items = self.s.get(p["id"])["items"]
        self.assertEqual([os.path.basename(x["path"]) for x in items], ["c.mp3", "a.mp3"])
        self.assertTrue(items[1]["lock"])                                              # Sperre bleibt erhalten
        self.assertEqual((items[0]["artist"], items[0]["dur"]), ("X", 200))
        self.assertEqual(self.s.external_changes(), [])
        # TagStudio-Fassung behalten
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("../01_Library/b.mp3\n")
        self.s.apply_external("Set.m3u8", "keep")
        self.assertNotIn("b.mp3", self.read("Set.m3u8"))
        # entfernt → neu schreiben bzw. archivieren
        os.remove(path)
        self.assertEqual(self.s.external_changes()[0]["kind"], "removed")
        self.s.apply_external("Set.m3u8", "keep")
        self.assertTrue(os.path.isfile(path))
        os.remove(path)
        self.s.apply_external("Set.m3u8", "archive")
        self.assertTrue(self.s.get(p["id"])["archived"])
        # neue fremde Datei: übernehmen bzw. ignorieren
        os.makedirs(self.m3u("Fremd"))
        with open(self.m3u("Fremd", "Gast.m3u"), "w", encoding="utf-8") as fh:
            fh.write("..\\..\\01_Library\\c.mp3\n")                                      # Windows-Trenner
        with open(self.m3u("Weg.m3u8"), "w", encoding="utf-8") as fh:
            fh.write("#EXTM3U\n")
        self.assertEqual([(c["kind"], c["rel"]) for c in self.s.external_changes()], [("new", "Fremd/Gast.m3u"), ("new", "Weg.m3u8")])
        r = self.s.apply_external("Fremd/Gast.m3u", "take")
        g = self.s.get(r["id"])
        self.assertEqual((g["name"], g["folder"], g["kind"]), ("Gast", "Fremd", "import"))
        self.assertEqual(os.path.normcase(g["items"][0]["path"]), os.path.normcase(self.c))
        self.s.apply_external("Weg.m3u8", "keep")
        self.assertEqual(self.s.external_changes(), [])
        self.assertTrue(os.path.isfile(self.m3u("Weg.m3u8")))                          # fremde Datei bleibt

    def test_foreign_file_not_overwritten(self):
        os.makedirs(self.mirror)
        with open(self.m3u("Set.m3u8"), "w", encoding="utf-8") as fh:
            fh.write("fremd\n")
        self.s.create("Set", items=[self.a])
        self.assertEqual(self.read("Set.m3u8"), "fremd\n")

    def test_parse_m3u_forms(self):
        text = ("\ufeff#EXTM3U\n#EXTINF:-1,Nur Titel\nfile:///C:/Musik/a%20b.mp3\n"
                "file://localhost/Users/x/c.mp3\nC:\\Musik\\d.mp3\n\n# Kommentar\nsub/e.mp3\n")
        r = playlists.parse_m3u(text, "/base")
        self.assertEqual(r[0]["path"], "C:/Musik/a b.mp3")
        self.assertEqual((r[0]["label"], r[0]["dur"]), ("Nur Titel", None))
        self.assertEqual(r[1]["path"], "/Users/x/c.mp3")
        self.assertEqual(r[2]["path"], "C:\\Musik\\d.mp3")
        self.assertEqual(os.path.normpath(r[3]["path"]), os.path.normpath(os.path.join("/base", "sub", "e.mp3")))


class TestMigrate(Base):
    def test_djset_lists(self):
        saved = {"Warm up": {"items": [{"path": self.a, "lock": True}, {"path": self.b}], "opts": {"w_key": 0.9}},
                 "Lexicon: Freitag": {"items": [{"path": self.c}], "source": "lexicon"}, "kaputt": 3}
        ids = self.s.migrate_djset(saved)
        self.assertEqual(sorted(ids), ["Lexicon: Freitag", "Warm up"])
        w = self.s.get(ids["Warm up"])
        self.assertEqual((w["folder"], w["kind"], w["djset"]["opts"]["w_key"], w["items"][0]["lock"]), ("DJ-Sets", "djset", 0.9, True))
        f = self.s.get(ids["Lexicon: Freitag"])
        self.assertEqual((f["name"], f["folder"], f["kind"]), ("Freitag", "Lexicon", "import"))
        self.assertEqual(self.s.migrate_djset(saved), {})                              # nur einmal
        self.assertFalse(self.s.undo_stack)


class TestMatchImport(Base):
    """#271: Abgleich ohne Datei, CSV/Rekordbox-Import, Rekordbox-Export mit Ordnern, Neu-Verknüpfen."""

    def test_match_ref(self):
        idx = [playlists.lib_entry("/l/a.mp3", "Daft Punk feat. X", "One More Time (Extended Mix)", "FR-AB1", 320),
               playlists.lib_entry("/l/b.mp3", "Daft Punk", "One More Time", "", 240),
               playlists.lib_entry("/l/c.mp3", "Other", "Song", "", 200)]
        m = playlists.match_ref
        self.assertEqual(m({"isrc": "fr-ab1"}, idx)["path"], "/l/a.mp3")
        self.assertEqual(m({"artist": "Daft Punk", "title": "One More Time", "mix": "Extended Mix"}, idx)["path"], "/l/a.mp3")
        self.assertEqual(m({"artist": "Daft Punk", "title": "One More Time (Original Mix)"}, idx)["path"], "/l/b.mp3")
        r = m({"artist": "Daft Punk", "title": "One More Time (Radio Edit)"}, idx)
        self.assertEqual((r["status"], sorted(r["candidates"])), ("unclear", ["/l/a.mp3", "/l/b.mp3"]))     # anderer Mix
        self.assertEqual(m({"artist": "Nobody", "title": "Nothing"}, idx)["status"], "missing")
        self.assertEqual(m({"artist": "Other", "title": "Song", "dur": 420}, idx)["status"], "unclear")     # Dauer passt nicht

    def test_match_tolerant(self):
        """#281: Mix-Schreibweisen, anderer Mix als gefunden, ähnliche Titel, Grund je Zeile."""
        e = playlists.lib_entry
        self.assertEqual(playlists.split_title("Song - Extended Mix"), ("song", "extended"))
        self.assertEqual(playlists.split_title("Song (Extended Version)"), ("song", "extended"))
        self.assertEqual(playlists.split_title("Song - Remastered 2011"), ("song", ""))
        self.assertEqual(playlists.split_title("Song (Original Mix)"), ("song", ""))
        self.assertEqual(playlists.split_title("Song (Kölsch Remix)"), ("song", "kolsch remix"))
        self.assertEqual(playlists.split_title("Long - Way - Home"), ("long way home", ""))     # Strich ohne Mix-Wort
        self.assertEqual(e("/l/t.mp3", "A", "Song", subtitle="Extended Mix")["mix"], "extended")  # Mix in TIT3
        idx = playlists.LibIndex([e("/l/ext.mp3", "Mara Lind", "Kaltes Glas - Extended Mix", "", 400),
                                  e("/l/dub.mp3", "Mara Lind", "Kaltes Glas (Dub)", "", 380),
                                  e("/l/n.mp3", "Mara Lind & Co", "Nordlicht and Stars", "", 300)])
        m = playlists.match_ref
        r = m({"artist": "Mara Lind", "title": "Kaltes Glas", "mix": "Extended"}, idx)
        self.assertEqual((r["status"], r["path"], r["reason"]), ("sure", "/l/ext.mp3", "Titel, Künstler und Mix"))
        r = m({"artist": "Mara Lind", "title": "Kaltes Glas - Radio Edit", "dur": 210}, idx)
        self.assertEqual((r["status"], r["path"], r["reason"]), ("unclear", "/l/ext.mp3", "anderer Mix: extended"))   # Vorschlag
        r = m({"artist": "Mara Lind", "title": "Kaltes Glas - Radio Edit"}, idx, any_mix=True)
        self.assertEqual((r["status"], r["path"]), ("sure", "/l/ext.mp3"))                       # Extended bevorzugt
        r = m({"artist": "Mara Lind", "title": "Nordlicht & Stars"}, idx)                        # ähnlich, nicht gleich
        self.assertEqual((r["status"], r["path"]), ("unclear", "/l/n.mp3"))
        self.assertTrue(r["reason"].startswith("Titel ähnlich"))
        r = m({"artist": "Jemand", "title": "Kaltes Glas"}, idx)
        self.assertEqual((r["status"], r["path"], r["reason"]), ("unclear", "", "anderer Künstler"))
        self.assertEqual(m({"artist": "Mara Lind", "title": "Ganz anders"}, idx)["status"], "missing")

    def test_parse_csv(self):
        items = playlists.parse_csv("Künstler;Titel;Mix;ISRC;Dauer\nA;Song;Extended Mix;X1;5:20\nB;Zwei;;;\n")
        self.assertEqual(items[0]["ref"], {"artist": "A", "title": "Song", "mix": "Extended Mix", "isrc": "X1", "dur": 320, "source": "csv"})
        items = playlists.parse_csv("Path,Artist\nsub/x.mp3,A\n", "/base")
        self.assertEqual(os.path.normpath(items[0]["path"]), os.path.normpath("/base/sub/x.mp3"))
        items = playlists.parse_csv("A - Song\nC:\\M\\b.mp3\n")
        self.assertEqual((items[0]["ref"]["artist"], items[1]["path"]), ("A", "C:\\M\\b.mp3"))
        p = self.s.create("Refs", items=[{"ref": {"artist": "A", "title": "Song"}}, {"ref": {}}, {"path": self.a}])
        self.assertEqual(len(p["items"]), 2)                                            # leere Angabe fällt weg
        self.assertNotIn("A - Song", self.read("Refs.m3u8"))                            # ohne Datei nicht in der M3U8
        self.assertEqual(self.s.relink(p["id"], [{"k": 0, "path": self.b}, {"k": 9, "path": "x"}]), 1)
        it = self.s.get(p["id"])["items"][0]
        self.assertEqual((it["path"], it["ref"]["title"]), (self.b, "Song"))

    def test_rekordbox_tree_roundtrip(self):
        e = lambda p: {"path": p, "title": "T", "artist": "A", "duration": 60, "bpm": 124, "key": "8A"}  # noqa: E731
        xml = playlists.rekordbox_tree([{"folder": "Sets/2026", "name": "Freitag", "entries": [e(self.a), e(self.b)]},
                                        {"folder": "", "name": "Neu", "entries": [e(self.a)]}], "4.8.0")
        self.assertEqual(xml.count("<TRACK TrackID"), 2)                                 # Sammlung ohne Doppelte
        tree = playlists.read_rekordbox_tree(xml)
        self.assertEqual([(g["folder"], g["name"], len(g["paths"])) for g in tree], [("Sets/2026", "Freitag", 2), ("", "Neu", 1)])
        self.assertEqual(os.path.normcase(tree[0]["paths"][1]), os.path.normcase(self.b))


class TestSession(unittest.TestCase):
    """Playlists in der Sitzung: Tagger-Titel, Doppelte, DJ-Set (#268, #269), Übernahme alter Listen, Archiv."""

    def setUp(self):
        import core
        from helpers import text, write_mp3
        self.dir = tempfile.mkdtemp(prefix="ts_pls_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.base = os.path.join(self.dir, "Musik")
        self.lib = os.path.join(self.base, "01_Library")
        os.makedirs(self.lib)
        for n, (name, key, bpm) in enumerate([("a", "8A", "124"), ("b", "9A", "125"), ("c", "", "")]):
            fr = [text("TIT2", name.upper()), text("TPE1", "DJ")] + ([text("TKEY", key), text("TBPM", bpm)] if key else [])
            write_mp3(os.path.join(self.lib, f"{name}.mp3"), fr, audio_seed=n + 1)

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def session(self, cfg=None, load=True):
        import json
        import time
        if cfg:
            with open(os.path.join(self.dir, "cfg.json"), "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
        from session import Session
        s = Session()
        if load:
            s.start_tag_load(self.lib, False)
            while not s.task_status()["done"]:
                time.sleep(0.02)
        return s

    def idx(self, s, name):
        return next(i for i, f in enumerate(s.tag_files) if os.path.basename(f.path) == name)

    def test_tagger_and_page(self):
        s = self.session({"base_dir": self.base, "archive_dir": os.path.join(self.base, "02_Archiv")})
        a, b = self.idx(s, "a.mp3"), self.idx(s, "b.mp3")
        st = s.pl_create("Freitag", "Sets", [a])
        pid = st["sel"]
        self.assertIn("1 Titel", st["message"])
        mirror = os.path.join(self.base, "03_Playlists", "Sets", "Freitag.m3u8")      # Standard: Basisordner
        self.assertTrue(os.path.isfile(mirror))
        with open(mirror, encoding="utf-8") as fh:
            self.assertIn("#EXTINF:", fh.read())
        r = s.pl_add_tag(pid, [a, b])
        self.assertEqual((r["ask"], r["dupes"], r["new"]), (True, 1, 1))
        self.assertEqual(s.pl_add_tag(pid, [a, b], "add")["added"], 2)
        st = s.pl_state(pid)
        rows = st["pl"]["items"]
        self.assertEqual([r["title"] for r in rows], ["A", "A", "B"])
        self.assertEqual((rows[0]["key"], rows[0]["bpm"], rows[0]["dup"], rows[2]["dup"]), ("8A", 124.0, True, False))
        self.assertEqual((st["pl"]["loaded"], st["pl"]["missing"]), (3, 0))
        self.assertEqual(s.pl_tag_indices(pid)["indices"], sorted([a, b]))
        self.assertEqual([os.path.basename(p) for p in s.pl_files(pid)["files"]], ["a.mp3", "b.mp3"])
        # nicht geladene Titel: Angaben aus der Datei
        s2 = self.session(load=False)
        rows = s2.pl_state(pid)["pl"]["items"]
        self.assertEqual(([r["title"] for r in rows], rows[0]["i"]), (["A", "A", "B"], None))
        # aussortierter Titel bleibt stehen, „im Archiv“
        s.tag_archive([b], True)
        row = s.pl_state(pid)["pl"]["items"][2]
        self.assertTrue(row["missing"])
        self.assertTrue(row["in_archive"].endswith("b.mp3"))
        # Playlist archivieren und über Einstellungen › Aussortierte zurückholen
        s.pl_archive(pid)
        self.assertFalse(os.path.exists(mirror))
        ent = [e for e in s.archive_list()["entries"] if e["area"] == "Playlists"]
        s.archive_restore([ent[0]["id"]])
        self.assertFalse(s._pls().get(pid).get("archived"))
        self.assertTrue(os.path.isfile(mirror))

    def test_djset_uses_playlists(self):
        p = lambda n: os.path.join(self.lib, n)  # noqa: E731
        old = {"djset_saved": {"Warm up": {"items": [{"path": p("a.mp3"), "lock": True}], "opts": {"w_key": 0.7}}},
               "djset_name": "Warm up"}
        s = self.session(old)
        st = s.dj_state()
        self.assertEqual((st["name"], st["lists"][0]["folder"]), ("Warm up", "DJ-Sets"))        # übernommen
        pid = st["pl"]
        s.pl_add_paths(pid, [p("a.mp3"), p("b.mp3")], "add")                                      # Doppelter Titel
        st = s.dj_load(pid)
        self.assertEqual(([os.path.basename(r["path"]) for r in st["items"]], st["dupes"]), (["a.mp3", "b.mp3"], 1))
        self.assertTrue(st["items"][0]["lock"])
        self.assertEqual(st["opts"]["w_key"], 0.7)
        self.assertIn("doppelte", st["message"])
        s.dj_lock(p("b.mp3"), True)
        st = s.dj_save_as("Warm up")                                                              # aktuelle: überschreibt
        self.assertTrue(st["ok"])
        self.assertEqual(len(s._pls().get(pid)["items"]), 2)
        self.assertTrue(s._pls().get(pid)["items"][1]["lock"])
        s.dj_new()
        s.dj_add()
        self.assertTrue(s.dj_save_as("warm up")["exists"])
        self.assertEqual(s.dj_save_as("Peak")["name"], "Peak")
        st = s.pl_rename(s.dj_state()["pl"], "Peak Time")
        self.assertEqual(s.dj_state()["name"], "Peak Time")                                       # folgt der Playlist
        s.pl_archive(s.dj_state()["pl"])
        st = s.dj_state()
        self.assertEqual((st["name"], st["pl"], len(st["items"])), ("", "", 3))                  # Set bleibt
        self.assertEqual(s.dj_export_name("csv")[:7], "DJ-Set ")

    def test_playlist_dir_setting_and_external(self):
        s = self.session({"base_dir": self.base})
        st = s.pl_create("Eins", "", [self.idx(s, "a.mp3")])
        own = os.path.join(self.dir, "Eigene")
        s.set_playlist_dir(own)
        self.assertTrue(os.path.isfile(os.path.join(own, "Eins.m3u8")))                         # neu geschrieben
        self.assertEqual(s.folders_overview()["playlists"], own)
        with open(os.path.join(own, "Neu.m3u8"), "w", encoding="utf-8") as fh:
            fh.write(os.path.join(self.lib, "c.mp3") + "\n")
        ch = s.pl_external()["changes"]
        self.assertEqual([(c["kind"], c["rel"]) for c in ch], [("new", "Neu.m3u8")])
        self.assertEqual(s.pl_state(st["sel"])["external"], 1)
        r = s.pl_external_apply([{"rel": "Neu.m3u8", "action": "take"}])
        self.assertEqual((r["pl"]["name"], r["pl"]["items"][0]["title"], r["external"]), ("Neu", "C", 0))
        r = s.pl_undo(r["sel"])
        self.assertIn("Rückgängig", r["message"])
        self.assertFalse(any(p["name"] == "Neu" for p in r["playlists"]))


    def test_import_export_match_missing(self):
        import time
        s = self.session({"base_dir": self.base, "default_tagger": self.lib})
        def wait():
            while not s.task_status()["done"]:
                time.sleep(0.02)
            return s.task_status()["result"]
        out = os.path.join(self.dir, "out")
        os.makedirs(out)
        # M3U8-Import (relativer Pfad, Umlaut im Namen), dann Export als M3U8, CSV und Rekordbox-XML
        m = os.path.join(out, "Gäste.m3u8")
        with open(m, "w", encoding="utf-8") as fh:
            fh.write("#EXTM3U\n#EXTINF:30,DJ - A\n../Musik/01_Library/a.mp3\n")
        st = s.pl_import_file(m, "Import")
        pid = st["sel"]
        self.assertEqual((st["pl"]["name"], st["pl"]["folder"], st["pl"]["items"][0]["title"]), ("Gäste", "Import", "A"))
        s.pl_export_file("m3u8", os.path.join(out, "x.m3u8"), [pid], None, {"relative": True})
        with open(os.path.join(out, "x.m3u8"), encoding="utf-8") as fh:
            self.assertIn(os.path.join("..", "Musik", "01_Library", "a.mp3"), fh.read())
        s.pl_export_file("csv", os.path.join(out, "x.csv"), [pid])
        with open(os.path.join(out, "x.csv"), encoding="utf-8-sig") as fh:
            self.assertIn("8A", fh.read())
        s.pl_create("Zwei", "Import/Sub", [self.idx(s, "b.mp3")])
        r = s.pl_export_file("xml", os.path.join(out, "x.xml"), None, "Import")
        self.assertIn("2 Playlist(s)", r["message"])
        st = s.pl_import_file(os.path.join(out, "x.xml"), "Zurück")
        self.assertIn("Zurück/Import/Sub", st["folders"])
        # CSV ohne Dateien → Abgleich mit der Bibliothek, Einkaufsliste
        c = os.path.join(out, "Liste.csv")
        with open(c, "w", encoding="utf-8") as fh:
            fh.write("Artist;Title\nDJ;A\nDJ;Fehlt\n")
        st = s.pl_import_file(c)
        cid = st["sel"]
        self.assertEqual((st["pl"]["refs"], st["pl"]["items"][0]["ref"]), (2, True))
        self.assertTrue(s.start_pl_match(cid)["ok"])
        res = wait()
        self.assertEqual((res["sure"], res["missing"]), (1, 1))
        s.pl_relink(cid, [{"k": r["k"], "path": r["path"]} for r in res["rows"] if r["path"]])
        self.assertEqual(s.pl_state(cid)["pl"]["refs"], 1)
        # #281: anderer Ordner, „anderer Mix gilt als gefunden“ wird gemerkt
        self.assertTrue(s.start_pl_match(cid, os.path.join(self.lib, "fehlt"))["ok"] is False)
        self.assertTrue(s.start_pl_match(cid, self.lib, True)["ok"])
        res = wait()
        self.assertEqual((res["roots"], res["any_mix"]), ([self.lib], True))
        self.assertTrue(s.pl_state(cid)["match"]["any_mix"])
        r = s.pl_shopping_file(os.path.join(out, "e.csv"), [cid])
        self.assertIn("1 Titel", r["message"])
        # Fehlende suchen: Datei verschoben
        mid = s.pl_create("Verschoben", "", [self.idx(s, "c.mp3")])["sel"]
        os.makedirs(os.path.join(self.lib, "neu"))
        os.replace(os.path.join(self.lib, "c.mp3"), os.path.join(self.lib, "neu", "c.mp3"))
        self.assertTrue(s.start_pl_find_missing(mid)["ok"])
        res = wait()
        self.assertEqual((res["rows"][0]["status"], os.path.basename(os.path.dirname(res["rows"][0]["path"]))), ("sure", "neu"))
        s.pl_relink(mid, [{"k": 0, "path": res["rows"][0]["path"]}])
        self.assertFalse(s.pl_state(mid)["pl"]["missing"])

    def test_play_queue_prepare(self):
        s = self.session({"base_dir": self.base})
        a = os.path.join(self.lib, "a.mp3")
        pid = s.pl_create("P", "", [self.idx(s, "a.mp3")])["sel"]
        s2 = self.session(load=False)                                       # Tagger leer: Datei direkt (kind „file“)
        self.assertEqual(s2.media_info("file", a)["title"], "A")
        with self.assertRaises(ValueError):
            s2.media_info("file", os.path.join(self.lib, "b.mp3"))          # nicht in einer Playlist
        self.assertEqual(len(s.pl_to_queue(pid)["items"]), 1)
        with self.assertRaises(ValueError):
            s2.pl_to_queue(pid)                                              # nichts im Tagger geladen
        name = s._pl_prep_add("Neu/{Jahr}-{Monat}", [a, os.path.join(self.lib, "b.mp3")], "W")
        pl = s._pls().find(name, "Neu")
        self.assertEqual((len(pl["items"]), name[:2]), (2, "20"))
        s._pl_prep_add("Neu/{Jahr}-{Monat}", [a])                            # schon drin: übersprungen
        self.assertEqual(len(s._pls().get(pl["id"])["items"]), 2)
        ref = s._pls().create("Wunsch", items=[{"ref": {"artist": "DJ", "title": "B"}}])
        self.assertEqual(s._pl_autolink([os.path.join(self.lib, "b.mp3")]), 1)
        self.assertTrue(s._pls().get(ref["id"])["items"][0]["path"].endswith("b.mp3"))


if __name__ == "__main__":
    unittest.main()
