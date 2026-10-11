"""Tests für id3tags.py – Lesen, Schreiben, Umwandeln von ID3-Tags."""
import base64
import os
import shutil
import tempfile
import unittest

from helpers import (write_mp3, text, txxx, comm, geob, apic, frame, id3v1, png, audio_of)
from id3tags import MP3File, MV, key_label


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_test_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def p(self, name="t.mp3"):
        return os.path.join(self.dir, name)


class TestRead(Base):
    def test_v24_text_fields(self):
        write_mp3(self.p(), [text("TIT2", "Never Alone (Extended Mix)"), text("TPE1", "Adriatique"),
                             text("TBPM", "126"), text("TKEY", "04A")])
        f = MP3File(self.p())
        self.assertEqual(f.tag_desc, "ID3v2.4")
        self.assertEqual(f.text("TIT2"), "Never Alone (Extended Mix)")
        self.assertEqual(f.text("TBPM"), "126")
        self.assertEqual(key_label("TKEY"), "Tonart")

    def test_v23_utf16_umlauts(self):
        write_mp3(self.p(), [text("TPE1", "Björk", 3), text("TIT2", "日本 Song", 3)], ver=3)
        f = MP3File(self.p())
        self.assertEqual(f.text("TPE1"), "Björk")
        self.assertEqual(f.text("TIT2"), "日本 Song")

    def test_multivalue_null_separated_with_bom(self):
        # Wie in der echten Bibliothek: vor jedem Einzelwert ein BOM-Zeichen
        val = "CamelPhat\x00﻿Kotiēr\x00﻿Yellowitz"
        write_mp3(self.p(), [frame("TSOP", b"\x03" + val.encode("utf-8"))])
        f = MP3File(self.p())
        self.assertEqual(f.text("TSOP"), "CamelPhat" + MV + "Kotiēr" + MV + "Yellowitz")
        self.assertNotIn("﻿", f.text("TSOP"))
        self.assertEqual(f.get("TSOP").display(), "CamelPhat ¦ Kotiēr ¦ Yellowitz")

    def test_v23_date_combined(self):
        write_mp3(self.p(), [text("TYER", "2025", 3), text("TDAT", "2507", 3)], ver=3)
        self.assertEqual(MP3File(self.p()).text("TDRC"), "2025-07-25")

    def test_geob_keyed_by_description(self):
        mik = base64.b64encode(b'{"key":"10A","source":"mixedinkey"}')
        write_mp3(self.p(), [geob("Serato Markers2", b"\x01\x01AAAA"),
                             geob("Key", mik, "application/json"),
                             geob("Energy", base64.b64encode(b'{"energyLevel":7}'), "application/json")])
        f = MP3File(self.p())
        self.assertIn("GEOB:Serato Markers2", f.items)
        self.assertIn("GEOB:Key", f.items)
        self.assertNotIn("GEOB#2", f.items)
        self.assertEqual(f.get("GEOB:Key").display(), '{"key":"10A","source":"mixedinkey"}')

    def test_txxx_comm_and_picture(self):
        write_mp3(self.p(), [txxx("Acoustid Id", "7b6e"), comm("", "04A - 126 - 7"), comm("iTunNORM", "0000"),
                             apic(png(1400, 1400), 3)])
        f = MP3File(self.p())
        self.assertEqual(f.text("TXXX:Acoustid Id"), "7b6e")
        self.assertEqual(f.text("COMM:"), "04A - 126 - 7")
        self.assertIn("COMM:iTunNORM", f.items)
        self.assertEqual(f.get("APIC:3").cover.dimensions(), (1400, 1400))

    def test_tipl_pairs_display(self):
        write_mp3(self.p(), [frame("TIPL", b"\x03" + "publisher\x00Kobalt\x00producer\x00X".encode())])
        self.assertEqual(MP3File(self.p()).get("TIPL").display(), "publisher: Kobalt; producer: X")

    def test_v1_only_and_no_tag(self):
        write_mp3(self.p("v1.mp3"), None, v1=id3v1("Titel V1", "Artist", year="1999", track=3, genre=17))
        f = MP3File(self.p("v1.mp3"))
        self.assertEqual(f.tag_desc, "ID3v1")
        self.assertEqual((f.text("TIT2"), f.text("TRCK"), f.text("TCON")), ("Titel V1", "3", "Rock"))
        write_mp3(self.p("none.mp3"), None)
        self.assertEqual(MP3File(self.p("none.mp3")).items, {})

    def test_mpeg_info(self):
        write_mp3(self.p(), [text("TIT2", "x")], audio_frames=100)
        f = MP3File(self.p())
        self.assertEqual((f.bitrate, f.samplerate, f.channels), (128, 44100, "Joint Stereo"))
        self.assertAlmostEqual(f.duration, 100 * 417 * 8 / 128000, places=2)


class TestWrite(Base):
    def test_unchanged_save_is_noop(self):
        write_mp3(self.p(), [text("TIT2", "A"), txxx("X", "1")])
        before = _read(self.p())
        MP3File(self.p()).save()
        self.assertEqual(_read(self.p()), before)

    def test_small_edit_in_place_keeps_other_frames(self):
        audio = write_mp3(self.p(), [text("TIT2", "A"), geob("Serato Markers2", b"\x01\x02\x03"), text("TKEY", "8A")])
        f = MP3File(self.p())
        raw_before = {k: list(it.orig) for k, it in f.items.items()}
        size = os.path.getsize(self.p())
        f.set_text("TKEY", "9A")
        f.save()
        g = MP3File(self.p())
        self.assertEqual(g.text("TKEY"), "9A")
        self.assertEqual(os.path.getsize(self.p()), size)  # passte ins Padding
        for k in ("TIT2", "GEOB:Serato Markers2"):
            self.assertEqual(g.get(k).orig, raw_before[k])
        self.assertEqual(audio_of(self.p()), audio)

    def test_growing_tag_rewrites_file_audio_identical(self):
        audio = write_mp3(self.p(), [text("TIT2", "A")], padding=0, v1=id3v1("A"))
        f = MP3File(self.p())
        f.set_text("TIT2", "B" * 5000)
        f.set_text("TXXX:Neu", "Wert äöü 日本")
        f.save()
        g = MP3File(self.p())
        self.assertEqual(len(g.text("TIT2")), 5000)
        self.assertEqual(g.text("TXXX:Neu"), "Wert äöü 日本")
        self.assertEqual(audio_of(self.p()), audio)
        self.assertTrue(g.had_v1)  # ID3v1 bleibt erhalten und wird aktualisiert
        with open(self.p(), "rb") as fh:
            fh.seek(-125, os.SEEK_END)
            self.assertEqual(fh.read(1), b"B")

    def test_add_tag_to_file_without_tag(self):
        audio = write_mp3(self.p(), None)
        f = MP3File(self.p())
        f.set_text("TIT2", "Neu")
        f.save()
        self.assertEqual(MP3File(self.p()).text("TIT2"), "Neu")
        self.assertEqual(audio_of(self.p()), audio)

    def test_convert_v24_to_v23(self):
        write_mp3(self.p(), [text("TDRC", "2025-07-25"), frame("TPE1", b"\x03A\x00B"), text("TKEY", "4B")])
        f = MP3File(self.p())
        f.set_version(3)
        f.save()
        g = MP3File(self.p())
        self.assertEqual(g.tag_desc, "ID3v2.3")
        self.assertEqual(g.text("TDRC"), "2025-07-25")  # als TYER + TDAT geschrieben
        self.assertEqual(g.get("TDRC").frame_ids(3), ["TYER", "TDAT"])
        self.assertEqual(g.text("TPE1"), "A / B")  # v2.3 kennt keine Null-Trennung
        self.assertEqual(g.text("TKEY"), "4B")

    def test_convert_v23_to_v24_multivalue(self):
        write_mp3(self.p(), [text("TPE1", "A", 3), text("TYER", "2020", 3)], ver=3)
        f = MP3File(self.p())
        f.set_version(4)
        f.set_text("TPE1", "A" + MV + "B")
        f.save()
        g = MP3File(self.p())
        self.assertEqual(g.tag_desc, "ID3v2.4")
        self.assertEqual(g.text("TPE1"), "A" + MV + "B")
        self.assertEqual(g.text("TDRC"), "2020")

    def test_remove_and_revert(self):
        write_mp3(self.p(), [text("TIT2", "A"), text("TKEY", "8A")])
        f = MP3File(self.p())
        f.set("TKEY", None)
        self.assertTrue(f.is_modified())
        f.revert()
        self.assertFalse(f.is_modified())
        f.set("TKEY", None)
        f.save()
        self.assertNotIn("TKEY", MP3File(self.p()).items)

    def test_copy_item_between_files(self):
        write_mp3(self.p("a.mp3"), [text("TIT2", "A"), apic(png(500, 500), 3)])
        write_mp3(self.p("b.mp3"), [text("TIT2", "B")], ver=3)
        a, b = MP3File(self.p("a.mp3")), MP3File(self.p("b.mp3"))
        b.set("APIC:3", a.get("APIC:3"))
        b.set("TIT2", a.get("TIT2"))
        b.save()
        c = MP3File(self.p("b.mp3"))
        self.assertEqual(c.get("APIC:3"), a.get("APIC:3"))
        self.assertEqual(c.text("TIT2"), "A")



class TestFieldNames(unittest.TestCase):
    def test_names_and_help(self):
        """#140/#151: Feldnamen wie in Mp3tag und Erklärungen."""
        from id3tags import field_name, field_help
        self.assertEqual(field_name("TXXX:CatalogNumber"), "CATALOGNUMBER")
        self.assertEqual(field_name("TIT2"), "TITLE")
        self.assertEqual(field_name("TKEY"), "INITIALKEY")
        self.assertEqual(field_name("COMM:eng:"), "COMMENT")
        self.assertEqual(field_name("GEOB:Serato Markers2"), "Serato Markers2")
        self.assertEqual(field_name("ZZZZ"), "ZZZZ")
        self.assertIn("Tonart", field_help("TKEY"))
        self.assertEqual(field_help("ZZZZ"), "")

if __name__ == "__main__":
    unittest.main()
