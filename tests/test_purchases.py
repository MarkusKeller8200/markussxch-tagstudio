"""Käufe (#285, #290): Abgleich mit der Bibliothek – dieselbe Datei unter zwei Pfaden, Zuordnen von Hand."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import playlists  # noqa: E402
import purchases  # noqa: E402


class TestMatch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_pur_")
        self.a = os.path.join(self.dir, "S", "Lib", "Mara Lind - Nordlicht (Extended Mix).mp3")
        self.b = os.path.join(self.dir, "NAS", "Lib", "Mara Lind - Nordlicht (Extended Mix).mp3")   # gleiche Datei, 2. Pfad
        self.c = os.path.join(self.dir, "S", "Lib", "Mara Lind - Nordlicht (Radio Edit).mp3")
        for p in (self.a, self.b, self.c):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(b"x" * (100 if p != self.c else 50))
        self.st = purchases.Store(os.path.join(self.dir, "data"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def entry(self, path, title, size, isrc=""):
        return playlists.lib_entry(path, "Mara Lind", title, isrc, 300, "", size)

    def test_same_file_two_paths(self):
        ix = playlists.LibIndex([self.entry(self.a, "Nordlicht (Extended Mix)", 100, "CHA1"),
                                 self.entry(self.b, "Nordlicht (Extended Mix)", 100, "CHA1")])
        self.assertEqual((len(ix), len(ix.dupes)), (1, 1))
        self.st.merge("beatport", "Beatport", [
            {"id": 1, "title": "Nordlicht", "mix": "Extended Mix", "artist": "Mara Lind", "dur": 300, "isrc": "CHA1"},
            {"id": 2, "title": "Nordlicht", "mix": "Extended Mix", "artist": "Mara Lind", "dur": 300}])
        count = self.st.match(ix)
        self.assertEqual(count["library"], 2)                       # vorher: „unklar – mehrere Treffer“
        # verschiedene Dateien mit gleichem Namen bleiben getrennt (andere Grösse)
        ix = playlists.LibIndex([self.entry(self.a, "Nordlicht (Extended Mix)", 100),
                                 self.entry(self.b, "Nordlicht (Extended Mix)", 99)])
        self.assertEqual((len(ix), len(ix.dupes)), (2, 0))
        self.assertEqual(self.st.match(ix)["unclear"], 2)

    def test_link_by_hand(self):
        self.st.merge("beatport", "Beatport", [{"id": 7, "title": "Nordlicht", "mix": "Club Mix", "artist": "Mara Lind"}])
        ix = playlists.LibIndex([self.entry(self.c, "Nordlicht (Radio Edit)", 50)])
        self.st.match(ix)
        it = self.st.data["items"]["beatport:7"]
        self.assertEqual(it["status"], "unclear")
        self.assertTrue(it["reason"].startswith("anderer Mix"))
        self.assertEqual(it["cands"], [self.c])
        self.st.link("beatport:7", self.c)
        self.assertEqual(self.st.match(ix)["library"], 1)            # bleibt bei weiteren Abgleichen
        self.assertEqual(self.st.data["items"]["beatport:7"]["reason"], "von Hand zugeordnet")
        self.st.merge("beatport", "Beatport", [{"id": 7, "title": "Nordlicht", "mix": "Club Mix", "artist": "Mara Lind"}])
        self.assertTrue(self.st.data["items"]["beatport:7"]["linked"])   # auch nach Aktualisieren
        self.st.link("beatport:7", "")
        self.assertEqual(self.st.match(ix)["unclear"], 1)
        with self.assertRaises(ValueError):
            self.st.link("beatport:7", os.path.join(self.dir, "gibt-es-nicht.mp3"))


if __name__ == "__main__":
    unittest.main()
