"""#262/#264/#265/#266: FLAC, MP4/M4A, OGG/Opus – Felder lesen/schreiben über die gemeinsame Grundlage."""
import hashlib
import os
import shutil
import struct
import subprocess
import unittest

from test_tagger_tools import Base

import audioformats
import backup
import flactags
import mp4tags
import oggtags
from id3tags import MP3File, Item, Cover, MV

FF = shutil.which("ffmpeg") or ""
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
JPG = b"\xff\xd8\xff\xe0" + b"1" * 40


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# --------------------------------------------------------------------------- synthetische Dateien
def vc(entries, vendor=b"test"):
    out = struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", len(entries))
    for e in entries:
        b = e.encode("utf-8")
        out += struct.pack("<I", len(b)) + b
    return out


def flac_block(t, d, last=False):
    return bytes([(0x80 if last else 0) | t]) + len(d).to_bytes(3, "big") + d


def make_flac(path, entries=(), padding=64, audio=None):
    rate, ch, bps, total = 44100, 2, 16, 44100 * 2
    x = (rate << 44) | ((ch - 1) << 41) | ((bps - 1) << 36) | total
    si = b"\x10\x00\x10\x00" + b"\x00" * 6 + x.to_bytes(8, "big") + b"\x00" * 16
    audio = audio if audio is not None else bytes(range(256)) * 100
    blocks = [flac_block(0, si), flac_block(4, vc(list(entries)))]
    blocks.append(flac_block(1, b"\x00" * padding, True) if padding else b"")
    if not padding:
        blocks[-2] = flac_block(4, vc(list(entries)), True)
    with open(path, "wb") as f:
        f.write(b"fLaC" + b"".join(blocks) + b"\xff\xf8" + audio)


def box(t, p):
    return struct.pack(">I", 8 + len(p)) + t + p


def make_m4a(path, ilst_items=b"", moov_first=True, free_after=0, codec=b"mp4a"):
    audio = bytes(range(256)) * 200
    mvhd = box(b"mvhd", b"\x00" * 4 + b"\x00" * 8 + struct.pack(">II", 1000, 3000) + b"\x00" * 80)
    entry = box(codec, b"\x00" * 6 + b"\x00\x01" + b"\x00" * 8 + struct.pack(">HHHHI", 2, 16, 0, 0, 44100 << 16))
    stsd = box(b"stsd", b"\x00" * 4 + struct.pack(">I", 1) + entry)

    def build(off):
        stco = box(b"stco", b"\x00" * 4 + struct.pack(">III", 2, off, off + 1000))
        trak = box(b"trak", box(b"mdia", box(b"minf", box(b"stbl", stsd + stco))))
        udta = box(b"udta", box(b"meta", b"\x00" * 4 + box(b"hdlr", b"\x00" * 8 + b"mdirappl" + b"\x00" * 9)
                                + box(b"ilst", ilst_items))) if ilst_items is not None else b""
        return box(b"moov", mvhd + trak + udta)
    ftyp = box(b"ftyp", b"M4A \x00\x00\x00\x00M4A mp42isom")
    free = box(b"free", b"\x00" * (free_after - 8)) if free_after else b""
    if moov_first:
        moov = build(0)
        off = len(ftyp) + len(moov) + len(free) + 8
        moov = build(off)
        data = ftyp + moov + free + box(b"mdat", audio)
    else:
        off = len(ftyp) + 8
        data = ftyp + box(b"mdat", audio) + build(off)
    with open(path, "wb") as f:
        f.write(data)


def itext(atom, s):
    return box(atom, box(b"data", struct.pack(">I", 1) + b"\x00" * 4 + s.encode()))


def ifree(name, s, mean="com.apple.iTunes"):
    return box(b"----", box(b"mean", b"\x00" * 4 + mean.encode()) + box(b"name", b"\x00" * 4 + name.encode())
               + box(b"data", struct.pack(">I", 1) + b"\x00" * 4 + s.encode()))


def ogg_page(serial, seq, packets, granule=0, flags=0):
    segs, body = [], b""
    for p in packets:
        n = len(p)
        while n >= 255:
            segs.append(255)
            n -= 255
        segs.append(n)
        body += p
    h = b"OggS" + bytes([0, flags]) + struct.pack("<qIII", granule, serial, seq, 0) + bytes([len(segs)]) + bytes(segs)
    return h + body


def make_ogg(path, entries, opus=False):
    if opus:
        ident = b"OpusHead" + bytes([1, 2]) + struct.pack("<HIh", 312, 44100, 0) + b"\x00"
        comm = b"OpusTags" + vc(entries)
        gran = 48000 * 3 + 312
    else:
        ident = b"\x01vorbis" + struct.pack("<IBIiii", 0, 2, 44100, 0, 128000, 0) + b"\xb8\x01"
        comm = b"\x03vorbis" + vc(entries) + b"\x01"
        gran = 44100 * 3
    with open(path, "wb") as f:
        f.write(ogg_page(7, 0, [ident], flags=2) + ogg_page(7, 1, [comm]) + ogg_page(7, 2, [b"x" * 500], gran, 4))


class TestDispatch(Base):
    def test_classes(self):
        p = os.path.join(self.dir, "a.flac")
        make_flac(p)
        self.assertIsInstance(MP3File(p), flactags.FlacFile)
        q = os.path.join(self.dir, "a.m4a")
        make_m4a(q)
        self.assertIsInstance(MP3File(q), mp4tags.Mp4File)
        r = os.path.join(self.dir, "a.ogg")
        make_ogg(r, ["TITLE=x"])
        self.assertIsInstance(MP3File(r), oggtags.OggFile)
        self.assertIs(type(MP3File(os.path.join(self.A, "1.mp3"))), MP3File)
        self.assertEqual(audioformats.exts_for(["flac", "ogg"]), (".flac", ".ogg", ".oga", ".opus"))
        self.assertEqual(audioformats.clean_ids(["ogg", "x", "wav"]), ["wav", "ogg"])

    def test_mp3_writer_refuses(self):
        p = os.path.join(self.dir, "b.flac")
        make_flac(p)
        h = sha(p)
        f = MP3File.__new__(MP3File)
        f.path = p
        f.load()
        f.set_text("TIT2", "nein")
        with self.assertRaises(ValueError):
            f.save()
        self.assertEqual(sha(p), h)

    def test_garbage_is_damaged_not_crash(self):
        for ext in (".flac", ".m4a", ".ogg"):
            p = os.path.join(self.dir, "kaputt" + ext)
            with open(p, "wb") as fh:
                fh.write(b"\x00" * 300)
            f = MP3File(p)
            self.assertTrue(f.tag_damaged, ext)
            f.set_text("TIT2", "x")
            with self.assertRaises(ValueError):
                f.save()


class TestFlac(Base):
    def test_read_mapping(self):
        p = os.path.join(self.dir, "r.flac")
        make_flac(p, ["TITLE=Titel", "ARTIST=A1", "ARTIST=A2", "TRACKNUMBER=3", "TRACKTOTAL=12", "INITIALKEY=8A",
                      "ORGANIZATION=Label X", "ENERGY=7", "SERATO_MARKERS_V2=QUJD", "COMMENT=hallo"])
        f = MP3File(p)
        self.assertEqual(f.text("TIT2"), "Titel")
        self.assertEqual(f.text("TPE1"), "A1" + MV + "A2")
        self.assertEqual(f.text("TRCK"), "3/12")
        self.assertEqual((f.text("TKEY"), f.text("TPUB"), f.text("TXXX:ENERGY"), f.text("COMM:")),
                         ("8A", "Label X", "7", "hallo"))
        self.assertNotIn("TXXX:SERATO_MARKERS_V2", f.items)        # Serato verborgen, aber erhalten
        self.assertEqual((f.samplerate, f.bits, f.channels), (44100, 16, "Stereo"))
        self.assertAlmostEqual(f.duration, 2.0)
        self.assertIn("FLAC", f.info())

    def test_write_in_place_keeps_names_order_and_hidden(self):
        p = os.path.join(self.dir, "w.flac")
        make_flac(p, ["ORGANIZATION=Alt", "TITLE=T", "SERATO_MARKERS_V2=QUJD", "TRACKNUMBER=1"], padding=2000)
        audio = flactags.audio_hash(p, flactags.read_layout(p)["audio_start"])
        size = os.path.getsize(p)
        f = MP3File(p)
        f.set_text("TIT2", "Neu")
        f.set_text("TPUB", "Neues Label")
        f.set_text("TXXX:ENERGY", "9")
        f.set("APIC:3", Item.new_cover(Cover(PNG, "image/png")))
        f.set_text("TRCK", "2/10")
        f.save()
        self.assertEqual(os.path.getsize(p), size)                           # Platzpuffer genutzt
        lay = flactags.read_layout(p)
        self.assertEqual(flactags.audio_hash(p, lay["audio_start"]), audio)
        vcb = next(b for b in lay["blocks"] if b["type"] == 4)
        names = [n for n, _v in __import__("mapfile").parse_vorbis_comment(vcb["data"])[1]]
        self.assertEqual(names, ["ORGANIZATION", "TITLE", "SERATO_MARKERS_V2", "TRACKNUMBER", "TRACKTOTAL", "ENERGY"])
        g = MP3File(p)
        self.assertEqual((g.text("TIT2"), g.text("TPUB"), g.text("TRCK"), g.text("TXXX:ENERGY")),
                         ("Neu", "Neues Label", "2/10", "9"))
        self.assertEqual(g.items["APIC:3"].cover.data, PNG)

    def test_write_grow_rewrites_file(self):
        p = os.path.join(self.dir, "g.flac")
        make_flac(p, ["TITLE=x"], padding=0)
        audio = flactags.audio_hash(p, flactags.read_layout(p)["audio_start"])
        f = MP3File(p)
        f.set("APIC:3", Item.new_cover(Cover(JPG * 100, "image/jpeg")))
        f.set_text("TIT2", "länger")
        f.save()
        lay = flactags.read_layout(p)
        self.assertEqual(flactags.audio_hash(p, lay["audio_start"]), audio)
        self.assertEqual(lay["blocks"][-1]["type"], 1)                       # neues PADDING
        self.assertEqual(MP3File(p).text("TIT2"), "länger")
        self.assertEqual([n for n in os.listdir(self.dir) if n.startswith(".tagstudio_flac_")], [])

    def test_unwritable_fields_reported(self):
        p = os.path.join(self.dir, "s.flac")
        make_flac(p, ["TITLE=x"])
        f = MP3File(p)
        it = Item("POPM", "POPM:x", payload=b"x\x00\xff")
        it.kind = "raw"
        f.items["POPM:x"] = it
        f.set_text("TIT2", "y")
        f.save()
        self.assertIn("POPM:x", f.save_skipped)
        self.assertNotIn("POPM:x", MP3File(p).items)

    def test_backup_restore(self):
        p = os.path.join(self.dir, "b.flac")
        make_flac(p, ["TITLE=Vorher"])
        bw = backup.BackupWriter(os.path.join(self.dir, "bk"), "T")
        bw.add(p)
        zp = bw.close()
        f = MP3File(p)
        f.set_text("TIT2", "Nachher")
        f.save()
        e = backup._manifest(zp)["files"][0]
        self.assertEqual(e["container"], "flac")
        self.assertEqual(backup.read_backup_tags(zp, e).text("TIT2"), "Vorher")
        self.assertEqual(backup.check_entry(e)[0], "ok")
        res = backup.restore(zp, safety_folder=os.path.join(self.dir, "bk2"))
        self.assertEqual(res[0][1], "restored", res)
        self.assertEqual(MP3File(p).text("TIT2"), "Vorher")


class TestMp4(Base):
    def items(self):
        return (itext(b"\xa9nam", "Titel") + itext(b"\xa9ART", "Künstler")
                + box(b"trkn", box(b"data", b"\x00" * 8 + struct.pack(">HHHH", 0, 3, 12, 0)))
                + box(b"tmpo", box(b"data", struct.pack(">I", 21) + b"\x00" * 4 + struct.pack(">H", 124)))
                + ifree("initialkey", "8A") + ifree("ENERGY", "7") + ifree("markersv2", "QUJD", "com.serato.dj")
                + box(b"covr", box(b"data", struct.pack(">I", 13) + b"\x00" * 4 + JPG)))

    def test_read(self):
        p = os.path.join(self.dir, "r.m4a")
        make_m4a(p, self.items())
        f = MP3File(p)
        self.assertEqual((f.text("TIT2"), f.text("TPE1"), f.text("TRCK"), f.text("TBPM"), f.text("TKEY"),
                          f.text("TXXX:ENERGY")), ("Titel", "Künstler", "3/12", "124", "8A", "7"))
        self.assertEqual(f.items["APIC:3"].cover.data, JPG)
        self.assertEqual((f.codec, f.samplerate, f.channels), ("AAC", 44100, "Stereo"))
        self.assertAlmostEqual(f.duration, 3.0)
        self.assertEqual(f.format_name(), "M4A (AAC)")
        make_m4a(p, b"", codec=b"alac")
        self.assertEqual(MP3File(p).format_name(), "M4A (ALAC)")

    def _roundtrip(self, **kw):
        p = os.path.join(self.dir, "w.m4a")
        make_m4a(p, self.items(), **kw)
        audio = mp4tags._mdat_hash(p)
        f = MP3File(p)
        f.set_text("TIT2", "Ein viel längerer neuer Titel, damit sich moov vergrössert")
        f.set_text("TPUB", "Label")
        f.set_text("TBPM", "126")
        f.set_text("TPOS", "1/2")
        f.set("APIC:3", Item.new_cover(Cover(PNG, "image/png")))
        f.save()
        self.assertEqual(mp4tags._mdat_hash(p), audio)
        g = MP3File(p)
        self.assertEqual((g.text("TIT2")[:8], g.text("TPUB"), g.text("TBPM"), g.text("TPOS"), g.text("TKEY")),
                         ("Ein viel", "Label", "126", "1/2", "8A"))
        self.assertEqual(g.items["APIC:3"].cover.data, PNG)
        # Serato-Feld (fremdes mean) byte-genau erhalten
        moov = g._moov
        self.assertIn(b"com.serato.dj", moov)
        # Offsets zeigen weiter auf den Anfang von mdat
        top = mp4tags.top_atoms(p)
        md = next(a for a in top if a[0] == b"mdat")
        self.assertEqual(mp4tags._offsets(p)[0], md[1] + md[2])
        # kleiner werden (Titel kürzen)
        g.set_text("TIT2", "k")
        g.save()
        self.assertEqual(mp4tags._mdat_hash(p), audio)
        md = next(a for a in mp4tags.top_atoms(p) if a[0] == b"mdat")
        self.assertEqual(mp4tags._offsets(p)[0], md[1] + md[2])
        self.assertEqual(MP3File(p).text("TIT2"), "k")
        return p

    def test_write_moov_first_shifts_offsets(self):
        self._roundtrip()

    def test_write_moov_first_with_free(self):
        p = self._roundtrip(free_after=4000)
        self.assertIn(b"free", [a[0] for a in mp4tags.top_atoms(p)])

    def test_write_moov_last(self):
        self._roundtrip(moov_first=False)

    def test_create_ilst_when_missing(self):
        p = os.path.join(self.dir, "n.m4a")
        make_m4a(p, None)
        f = MP3File(p)
        self.assertEqual(f.items, {})
        f.set_text("TIT2", "Neu")
        f.set_text("TXXX:ENERGY", "5")
        f.save()
        g = MP3File(p)
        self.assertEqual((g.text("TIT2"), g.text("TXXX:ENERGY")), ("Neu", "5"))

    def test_backup_restore(self):
        p = os.path.join(self.dir, "b.m4a")
        make_m4a(p, itext(b"\xa9nam", "Vorher"))
        bw = backup.BackupWriter(os.path.join(self.dir, "bk"), "T")
        bw.add(p)
        zp = bw.close()
        f = MP3File(p)
        f.set_text("TIT2", "Nachher")
        f.save()
        e = backup._manifest(zp)["files"][0]
        self.assertEqual(backup.read_backup_tags(zp, e).text("TIT2"), "Vorher")
        res = backup.restore(zp, safety_folder=os.path.join(self.dir, "bk2"))
        self.assertEqual(res[0][1], "restored", res)
        self.assertEqual(MP3File(p).text("TIT2"), "Vorher")


class TestOgg(Base):
    def test_vorbis_and_opus_read_only(self):
        import base64
        pic = __import__("mapfile").build_picture(Cover(PNG, "image/png", 3))
        for opus in (False, True):
            p = os.path.join(self.dir, "o.opus" if opus else "o.ogg")
            make_ogg(p, ["TITLE=Ogg Titel", "ARTIST=X", "BPM=125",
                         "METADATA_BLOCK_PICTURE=" + base64.b64encode(pic).decode()], opus)
            f = MP3File(p)
            self.assertEqual((f.text("TIT2"), f.text("TBPM")), ("Ogg Titel", "125"))
            self.assertEqual(f.items["APIC:3"].cover.data, PNG)
            self.assertAlmostEqual(f.duration, 3.0, places=2)
            self.assertEqual(f.format_name(), "Opus" if opus else "OGG Vorbis")
            self.assertTrue(f.read_only)
            h = sha(p)
            f.set_text("TIT2", "x")
            with self.assertRaises(ValueError):
                f.save()
            self.assertEqual(sha(p), h)


@unittest.skipUnless(FF, "FFmpeg fehlt")
class TestRealFiles(Base):
    """Mit FFmpeg erzeugte Dateien: nach dem Schreiben dekodiert FFmpeg sie noch fehlerfrei und gleich lang."""

    def gen(self, name, args):
        p = os.path.join(self.dir, name)
        subprocess.run([FF, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                        "-ac", "2", "-metadata", "title=FF Titel", "-metadata", "artist=FF"] + args + [p], check=True)
        return p

    def pcm(self, p):
        r = subprocess.run([FF, "-loglevel", "error", "-i", p, "-f", "s16le", "-"], capture_output=True, check=True)
        return hashlib.sha256(r.stdout).hexdigest()

    def test_flac_m4a_roundtrip_decodes_identically(self):
        files = [self.gen("f.flac", ["-c:a", "flac"]), self.gen("a.m4a", ["-c:a", "aac"]),
                 self.gen("l.m4a", ["-c:a", "alac"]), self.gen("s.m4a", ["-c:a", "aac", "-movflags", "+faststart"])]
        for p in files:
            before = self.pcm(p)
            f = MP3File(p)
            self.assertEqual(f.text("TIT2"), "FF Titel", p)
            f.set_text("TIT2", "Neuer Titel " + "x" * 300)
            f.set_text("TKEY", "11B")
            f.set("APIC:3", Item.new_cover(Cover(JPG * 500, "image/jpeg")))
            f.save()
            self.assertEqual(self.pcm(p), before, p)
            g = MP3File(p)
            self.assertEqual((g.text("TIT2")[:11], g.text("TKEY")), ("Neuer Titel", "11B"), p)
        self.assertEqual(MP3File(files[2]).codec, "ALAC")

    def test_ogg_reads(self):
        for name, codec in (("v.ogg", "libvorbis"), ("o.opus", "libopus")):
            try:
                p = self.gen(name, ["-c:a", codec])
            except subprocess.CalledProcessError:
                continue
            f = MP3File(p)
            self.assertEqual(f.text("TIT2"), "FF Titel", name)
            self.assertAlmostEqual(f.duration, 2.0, delta=0.1)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(FF, "FFmpeg fehlt")
class TestPlayer(Base):
    """#454: FLAC/M4A/OGG im Player; ALAC über eine WAV-Fassung im Cache."""

    def gen(self, name, codec):
        p = os.path.join(self.dir, name)
        subprocess.run([FF, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=duration=1", "-ac", "2",
                        "-c:a", codec, p], check=True)
        return p

    def test_alac_served_as_wav_and_aac_direct(self):
        import media
        from unittest import mock
        srv = media.MediaServer()
        self.addCleanup(srv.stop)
        with mock.patch.object(media, "_play_dir", lambda: os.path.join(self.dir, "play")):
            alac, aac = self.gen("l.m4a", "alac"), self.gen("a.m4a", "aac")
            self.assertTrue(media.is_alac(alac))
            self.assertFalse(media.is_alac(aac))
            u1 = srv.register(alac)
            self.assertTrue(u1.endswith(".wav"))
            self.assertTrue(srv.register(aac).endswith(".m4a"))
            cached = os.listdir(os.path.join(self.dir, "play"))
            self.assertEqual(len(cached), 1)
            srv.register(alac)                                                 # zweites Mal: aus dem Cache
            self.assertEqual(os.listdir(os.path.join(self.dir, "play")), cached)
            import wave
            with wave.open(os.path.join(self.dir, "play", cached[0])) as w:
                self.assertAlmostEqual(w.getnframes() / w.getframerate(), 1.0, delta=0.05)

    def test_wave_key_ignores_tag_changes(self):
        import waveform
        for name, codec in (("w.flac", "flac"), ("w.m4a", "aac")):
            p = self.gen(name, codec)
            k = waveform.key_for(MP3File(p))
            f = MP3File(p)
            f.set_text("TIT2", "anders " + "x" * 5000)
            f.save()
            self.assertEqual(waveform.key_for(MP3File(p)), k, name)
