"""#98: alle ID3-Frames – Katalog, lesbare Kurzfassungen, v2.2-Zuordnung, verlustfreies Durchreichen, v2.3 ↔ v2.4."""
import os
import shutil
import struct
import tempfile
import unittest

from helpers import frame, text, write_mp3, syncsafe, mpeg_audio

import id3frames
from id3tags import MP3File, MV

# Beispiel-Nutzdaten je Binär-Frame (wie in der Spezifikation aufgebaut)
SAMPLES = {
    "PCNT": (b"\x00\x00\x00\x2a", "42 Wiedergabe(n)"),
    "SYLT": (b"\x00eng\x02\x01Vers\x00" + b"Hallo\x00" + struct.pack(">I", 1500) + b"Welt\x00" + struct.pack(">I", 3000),
             "Liedtext (eng, Vers): 2 Zeile(n)"),
    "ETCO": (b"\x02" + b"\x03" + struct.pack(">I", 1000) + b"\x07" + struct.pack(">I", 61000), "Beginn Refrain @ 1:01.0"),
    "MLLT": (struct.pack(">H", 1) + b"\x00\x01\xa0" + b"\x00\x00\x1a" + b"\x08\x08", "alle 1 MPEG-Frames"),
    "SYTC": (b"\x02\x7d\x00\x00\x00\x00", "Tempo-Code, Zeit in ms"),
    "RVA2": (b"track\x00" + b"\x01" + struct.pack(">h", -3 * 512) + b"\x00", "track: Master -3.00 dB"),
    "RVAD": (b"\x03\x10" + b"\x00" * 8, "Lautstärke-Anpassung (ID3v2.3), 16 Bit"),
    "EQU2": (b"\x01bass\x00" + struct.pack(">Hh", 200, 512) + struct.pack(">Hh", 400, -512), "bass: 2 Punkt(e), linear"),
    "EQUA": (b"\x10" + b"\x80\x64\x01\x00" * 3, "Equalizer (ID3v2.3), 16 Bit je Wert, 3 Punkt(e)"),
    "RVRB": (struct.pack(">HH", 120, 130) + b"\x00" * 8, "Hall links 120 ms, rechts 130 ms"),
    "USER": (b"\x00deuNur privat", "deu: Nur privat"),
    "OWNE": (b"\x00EUR1.29\x0020261011Beatport", "Preis EUR1.29 · gekauft 2026-10-11 · Verkäufer Beatport"),
    "COMR": (b"\x00EUR1.29\x0020271231https://shop.example\x00\x01Shop\x00Single\x00", "gültig bis 2027-12-31 · Verkäufer Shop"),
    "ENCR": (b"mailto:x@example.org\x00\x80", "Methode 0x80"),
    "GRID": (b"mailto:x@example.org\x00\x81", "Gruppe 0x81"),
    "SIGN": (b"\x81" + b"\x01" * 20, "Signatur Gruppe 0x81, 20 Bytes"),
    "LINK": (b"WOARhttps://example.org/a.mp3\x00", "Verweis auf WOAR: https://example.org/a.mp3"),
    "POSS": (b"\x02\x00\x00\x30\x39", "Position 12345 ms"),
    "SEEK": (struct.pack(">I", 4096), "nächstes Tag nach 4096 Bytes"),
    "ASPI": (struct.pack(">IIHB", 0, 900000, 100, 8) + b"\x00" * 100, "Suchindex: 100 Punkte"),
    "RBUF": (b"\x00\x10\x00\x01", "Puffer 4096 Bytes, eingebettete Info"),
    "AENC": (b"owner\x00\x00\x10\x00\x20", "owner · Vorschau ab Frame 16, 32 Frames"),
    "MCDI": (b"\x00" * 28, "2 Spur(en)"),
    "CHAP": (b"ch1\x00" + struct.pack(">IIII", 0, 83000, 0xFFFFFFFF, 0xFFFFFFFF) + frame("TIT2", b"\x03Intro", 4),
             "ch1: 0:00.0–1:23.0 „Intro“"),
    "PCST": (b"\x00\x00\x00\x00", "Podcast"),
    "CTOC": (b"toc\x00\x03\x02ch1\x00ch2\x00", "toc: 2 Eintrag/Einträge · oberste Ebene"),
}


class TestCatalog(unittest.TestCase):
    def test_spec_complete(self):
        v23 = ("AENC APIC COMM COMR ENCR EQUA ETCO GEOB GRID IPLS LINK MCDI MLLT OWNE PRIV PCNT POPM POSS RBUF RVAD RVRB "
               "SYLT SYTC TALB TBPM TCOM TCON TCOP TDAT TDLY TENC TEXT TFLT TIME TIT1 TIT2 TIT3 TKEY TLAN TLEN TMED TOAL "
               "TOFN TOLY TOPE TORY TOWN TPE1 TPE2 TPE3 TPE4 TPOS TPUB TRCK TRDA TRSN TRSO TSIZ TSRC TSSE TYER TXXX UFID "
               "USER USLT WCOM WCOP WOAF WOAR WOAS WORS WPAY WPUB WXXX").split()
        v24_new = "ASPI EQU2 RVA2 SEEK SIGN TDEN TDOR TDRC TDRL TDTG TIPL TMCL TMOO TPRO TSOA TSOP TSOT TSST".split()
        for f in v23:
            self.assertIn("3", id3frames.SPEC[f][1], f)
        for f in v24_new:
            self.assertEqual(id3frames.SPEC[f][1], "4", f)
        self.assertEqual(id3frames.V23_ONLY, sorted("EQUA IPLS RVAD TDAT TIME TORY TRDA TSIZ TYER".split()))
        # jeder Binär-Frame hat eine lesbare Kurzfassung
        from id3tags import _kind_of
        raw = [f for f in id3frames.SPEC if _kind_of(f) == "raw" and f not in ("GEOB", "PRIV", "UFID", "POPM", "IPLS")]
        self.assertEqual(sorted(set(raw) - set(SAMPLES)), [])

    def test_v22_mapping(self):
        m = id3frames.V22_TO_V23
        for a, b in (("TT2", "TIT2"), ("TOA", "TOPE"), ("TOT", "TOAL"), ("SLT", "SYLT"), ("CNT", "PCNT"),
                     ("IPL", "IPLS"), ("RVA", "RVAD"), ("GEO", "GEOB"), ("LNK", "LINK"), ("CRA", "AENC")):
            self.assertEqual(m[a], b)
        self.assertEqual(len(set(m.values())), len(m))

    def test_describe(self):
        for fid, (payload, want) in SAMPLES.items():
            got = id3frames.describe(fid, payload)
            self.assertIsNotNone(got, fid)
            self.assertIn(want, got, fid)
        self.assertIsNone(id3frames.describe("SYLT", b"\x00"))         # kaputt → keine Kurzfassung, kein Fehler
        self.assertIsNone(id3frames.describe("XXXX", b"abc"))

    def test_capabilities(self):
        self.assertEqual(id3frames.capabilities("TIT2")["edit"], "Text")
        self.assertEqual(id3frames.capabilities("GEOB")["edit"], "Binärfeld-Editor")
        self.assertEqual(id3frames.capabilities("SYLT")["show"], "lesbar")
        self.assertEqual(id3frames.capabilities("IPLS")["edit"], "Text")


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_frames_")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_all_frames_lossless(self):
        """Datei mit jedem Binär-Frame: Anzeige lesbar, Speichern nach Textänderung lässt alle Frames byte-gleich."""
        for ver in (3, 4):
            frames = [text("TIT2", "Alle", ver)] + [frame(f, p, ver) for f, (p, _w) in SAMPLES.items()
                                                    if not (ver == 3 and f in id3frames.V24_ONLY)
                                                    and not (ver == 4 and f in id3frames.V23_ONLY)]
            p = self.path(f"alle{ver}.mp3")
            write_mp3(p, frames, ver=ver)
            f = MP3File(p)
            for fid, (_pl, want) in SAMPLES.items():
                it = f.get(fid)
                if it is not None:
                    self.assertIn(want, it.display(), fid)
            f.set_text("TIT2", "Geändert")
            f.save()
            g = MP3File(p)
            self.assertEqual(g.text("TIT2"), "Geändert")
            for fid in SAMPLES:
                if f.get(fid) is not None:
                    self.assertEqual(g.get(fid).payload, f.get(fid).payload, f"v2.{ver} {fid}")

    def test_ipls_tipl(self):
        """v2.3 IPLS wird als TIPL gelesen und bleibt IPLS; Umwandlung v2.3 → v2.4 → v2.3."""
        body = b"\x00" + b"\x00".join([b"Produzent", b"Mara Lind", b"Mix", b"Kai Ost"]) + b"\x00"
        p = self.path("ipls.mp3")
        write_mp3(p, [text("TIT2", "P", 3), frame("IPLS", body, 3)], ver=3)
        f = MP3File(p)
        self.assertEqual(f.text("TIPL"), MV.join(["Produzent", "Mara Lind", "Mix", "Kai Ost"]))
        self.assertIn("Produzent: Mara Lind", f.get("TIPL").display())
        self.assertEqual(f.get("TIPL").frame_ids(3), ["IPLS"])
        f.set_version(4)
        f.save()
        g = MP3File(p)
        self.assertEqual((g.version, g.text("TIPL")), (4, f.text("TIPL")))
        self.assertEqual(g.get("TIPL").frame_ids(4), ["TIPL"])
        g.set_version(3)
        g.save()
        h = MP3File(p)
        self.assertEqual(h.get("TIPL").frame_ids(3), ["IPLS"])
        self.assertEqual(h.text("TIPL"), f.text("TIPL"))

    def test_v22_file(self):
        """ID3v2.2-Datei: alle bekannten Frames werden nach v2.3 übernommen (auch SLT, CNT, LNK mit 3-Zeichen-ID)."""
        def f22(fid, payload):
            return fid.encode() + len(payload).to_bytes(3, "big") + payload
        frames = [f22("TT2", b"\x00Alt"), f22("TOA", b"\x00Original"), f22("CNT", b"\x00\x00\x00\x07"),
                  f22("SLT", SAMPLES["SYLT"][0]), f22("LNK", b"WARhttps://example.org\x00"), f22("CRM", b"x\x00y")]
        body = b"".join(frames) + b"\x00" * 64
        p = self.path("v22.mp3")
        with open(p, "wb") as fh:
            fh.write(b"ID3\x02\x00\x00" + syncsafe(len(body)) + body + mpeg_audio(20))
        f = MP3File(p)
        self.assertEqual(f.version, 3)
        self.assertEqual((f.text("TIT2"), f.text("TOPE")), ("Alt", "Original"))
        self.assertIn("7 Wiedergabe(n)", f.get("PCNT").display())
        self.assertIn("2 Zeile(n)", f.get("SYLT").display())
        self.assertIn("Verweis auf WOAR", f.get("LINK").display())
        self.assertIsNone(f.get("CRM"))


class TestDoc(unittest.TestCase):
    def test_doc_current(self):
        """docs/ID3-FELDER.md passt zum Katalog (sonst: python tools/id3_frames_doc.py)."""
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location("id3_frames_doc", os.path.join(root, "tools", "id3_frames_doc.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with open(mod.OUT, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), mod.render())


if __name__ == "__main__":
    unittest.main()
