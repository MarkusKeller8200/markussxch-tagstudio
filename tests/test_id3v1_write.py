"""#112: ID3v1 zusätzlich schreiben bzw. entfernen; Audio bleibt unverändert."""
import os
import shutil
import tempfile
import unittest

from helpers import write_mp3, text, comm, audio_of

from id3tags import MP3File


class TestV1(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_v1_")
        self.p = os.path.join(self.dir, "a.mp3")
        self.audio = write_mp3(self.p, [text("TIT2", "Nordlicht (Extended Mix) mit sehr langem Titel"), text("TPE1", "Mara Lind"),
                                        text("TALB", "Nacht"), text("TDRC", "2024-05-01"), text("TRCK", "3/12"),
                                        text("TCON", "House"), comm("", "Hallo")])

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_write_and_remove(self):
        f = MP3File(self.p)
        self.assertFalse(f.had_v1)
        f.v1_mode = "write"
        self.assertTrue(f.is_modified())
        f.save()
        g = MP3File(self.p)
        self.assertTrue(g.had_v1)
        with open(self.p, "rb") as fh:
            fh.seek(-128, os.SEEK_END)
            v1 = fh.read()
        self.assertEqual(v1[:3], b"TAG")
        self.assertEqual(v1[3:33].rstrip(b"\x00"), "Nordlicht (Extended Mix) mit s".encode("latin-1"))
        self.assertEqual(v1[93:97], b"2024")
        self.assertEqual((v1[126], v1[127]), (3, 35))                  # Spur 3, Genre House
        self.assertEqual(g.text("TIT2"), "Nordlicht (Extended Mix) mit sehr langem Titel")   # v2 hat Vorrang
        size = os.path.getsize(self.p)
        g.set_text("TPE1", "Kai Ost")
        g.save()
        self.assertEqual(os.path.getsize(self.p), size)                 # v1 aktualisiert, nicht angehängt
        with open(self.p, "rb") as fh:
            fh.seek(-128, os.SEEK_END)
            self.assertEqual(fh.read()[33:40], b"Kai Ost")
        h = MP3File(self.p)
        h.v1_mode = "remove"
        h.save()
        self.assertFalse(MP3File(self.p).had_v1)
        self.assertEqual(os.path.getsize(self.p), size - 128)
        self.assertEqual(audio_of(self.p), self.audio)


if __name__ == "__main__":
    unittest.main()
