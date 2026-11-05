"""#156/#263: WAV und AIFF – Tags im ID3-Chunk lesen und schreiben, getrennt vom MP3-Weg."""
import hashlib
import os
import struct
import time
import wave

from helpers import apic, geob, tag, text, txxx, write_mp3
from test_tagger_tools import Base

import backup
import chunktags
import compare
import core
from id3tags import MP3File, Item

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def make_wav(path, chunks_before=b"", chunks_after=b""):
    """WAV mit Python-`wave`, danach beliebige weitere Chunks vor bzw. hinter `data`."""
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(bytes(range(256)) * 690)          # 44160 Frames … genug Audio, ≈ 1 s
    with open(path, "rb") as f:
        raw = f.read()
    # Aufbau von wave: RIFF … WAVE fmt … data …
    fmt_end = 12 + 8 + struct.unpack("<I", raw[16:20])[0]
    body = raw[12:fmt_end] + chunks_before + raw[fmt_end:] + chunks_after
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body)


def riff_chunk(cid, data, le=True):
    return cid + struct.pack("<I" if le else ">I", len(data)) + data + (b"\x00" if len(data) & 1 else b"")


def info_list(**vals):
    body = b"INFO"
    for k, v in vals.items():
        d = v.encode() + b"\x00"
        body += riff_chunk(k.encode(), d)
    return riff_chunk(b"LIST", body)


def ext80(rate):
    """44100 als 80-Bit-Gleitkommazahl (AIFF COMM)."""
    import math
    e = int(math.floor(math.log2(rate)))
    mant = int(rate * 2 ** (63 - e))
    return struct.pack(">HQ", e + 16383, mant)


def make_aiff(path, extra=b"", form=b"AIFF", audio=None):
    audio = audio if audio is not None else bytes(range(256)) * 345
    frames = len(audio) // 4
    comm = struct.pack(">HIH", 2, frames, 16) + ext80(44100)
    if form == b"AIFC":
        comm += b"NONE" + b"\x0enot compressed\x00"
    ssnd = struct.pack(">II", 0, 0) + audio
    body = form + riff_chunk(b"COMM", comm, False) + riff_chunk(b"SSND", ssnd, False) + extra
    with open(path, "wb") as f:
        f.write(b"FORM" + struct.pack(">I", len(body)) + body)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def chunk_bytes(path, cid):
    lay = chunktags.read_layout(path)
    out = []
    with open(path, "rb") as f:
        for c in lay["chunks"]:
            if c["id"] == cid:
                f.seek(c["start"])
                out.append(f.read(c["end"] - c["start"]))
    return out


class TestChunkTags(Base):
    def wav(self, name="t.wav", **kw):
        p = os.path.join(self.dir, name)
        make_wav(p, **kw)
        return p

    def aiff(self, name="t.aiff", **kw):
        p = os.path.join(self.dir, name)
        make_aiff(p, **kw)
        return p

    # ------------------------------------------------------------------ Weiche und Lesen
    def test_dispatch_only_for_wav_aiff(self):
        mp3 = os.path.join(self.A, "1.mp3")
        self.assertIs(type(MP3File(mp3)), MP3File)                      # MP3 unverändert
        for p in (self.wav(), self.aiff(), self.aiff("t.aif"), self.aiff("T.AIFC", form=b"AIFC")):
            self.assertIsInstance(MP3File(p), chunktags.ChunkFile, p)
        self.assertIs(type(MP3File.__new__(MP3File)), MP3File)          # Listen-Cache-Weg bleibt MP3File

    def test_wav_audio_info_and_empty_tag(self):
        f = MP3File(self.wav())
        self.assertEqual((f.samplerate, f.bits, f.channels), (44100, 16, "Stereo"))
        self.assertAlmostEqual(f.duration, 44160 / 44100, places=3)
        self.assertEqual(f.items, {})
        self.assertIn("WAV", f.info())
        self.assertFalse(f.is_modified())

    def test_aiff_audio_info(self):
        f = MP3File(self.aiff())
        self.assertEqual((f.samplerate, f.bits, f.channels, f.container), (44100, 16, "Stereo", "aiff"))
        self.assertAlmostEqual(f.duration, (256 * 345 // 4) / 44100, places=3)

    def test_read_existing_id3_chunk(self):
        t = tag([text("TIT2", "Chunk Titel"), text("TBPM", "124"), txxx("ENERGY", "7"), apic(PNG)])
        p = self.wav(chunks_after=riff_chunk(b"id3 ", t))
        f = MP3File(p)
        self.assertEqual(f.text("TIT2"), "Chunk Titel")
        self.assertEqual(f.text("TBPM"), "124")
        self.assertEqual(f.text("TXXX:ENERGY"), "7")
        self.assertIn("APIC:3", f.items)
        self.assertIn("ID3v2.4", f.tag_desc)
        a = self.aiff(extra=riff_chunk(b"ID3 ", t, False))
        self.assertEqual(MP3File(a).text("TIT2"), "Chunk Titel")

    def test_info_and_aiff_text_without_id3(self):
        p = self.wav(chunks_before=info_list(INAM="Info Titel", IART="Info Künstler", IGNR="House"))
        f = MP3File(p)
        self.assertEqual((f.text("TIT2"), f.text("TPE1"), f.text("TCON")), ("Info Titel", "Info Künstler", "House"))
        self.assertEqual(f.tag_desc, "RIFF INFO")
        self.assertFalse(f.is_modified())
        a = self.aiff(extra=riff_chunk(b"NAME", b"Aiff Name", False) + riff_chunk(b"AUTH", b"Autor", False))
        g = MP3File(a)
        self.assertEqual((g.text("TIT2"), g.text("TPE1")), ("Aiff Name", "Autor"))

    # ------------------------------------------------------------------ Schreiben
    def _roundtrip(self, p, cid):
        audio = chunktags.audio_hash(p)
        others = {c: chunk_bytes(p, c) for c in (b"fmt ", b"LIST", b"cue ", b"COMM", b"NAME", b"junk")}
        f = MP3File(p)
        f.set_text("TIT2", "Neuer Titel")
        f.set_text("TKEY", "8A")
        f.set_text("TXXX:ENERGY", "8")
        f.set(f"GEOB:Serato Markers2", None)
        from id3tags import Cover
        f.set("APIC:3", Item.new_cover(Cover(PNG, "image/png")))
        f.save()
        self.assertEqual(chunktags.audio_hash(p), audio)                 # Audio byte-gleich
        for c, v in others.items():
            self.assertEqual(chunk_bytes(p, c), v, c)                     # übrige Chunks byte-gleich
        g = MP3File(p)
        self.assertEqual((g.text("TIT2"), g.text("TKEY"), g.text("TXXX:ENERGY")), ("Neuer Titel", "8A", "8"))
        self.assertEqual(g.items["APIC:3"].cover.data, PNG)
        self.assertEqual(len(chunk_bytes(p, cid)), 1)
        lay = chunktags.read_layout(p)
        self.assertEqual(lay["body_end"], lay["size"])                     # Containergrösse stimmt
        # zweites Speichern ersetzt den Chunk (kein zweiter Chunk)
        g.set_text("TIT2", "Noch einer, länger als vorher – damit sich die Grösse ändert")
        g.save()
        self.assertEqual(len(chunk_bytes(p, cid)), 1)
        self.assertEqual(MP3File(p).text("TIT2"), "Noch einer, länger als vorher – damit sich die Grösse ändert")
        self.assertEqual(chunktags.audio_hash(p), audio)
        return g

    def test_wav_write_roundtrip_keeps_everything_else(self):
        p = self.wav(chunks_before=info_list(INAM="Info"),
                     chunks_after=riff_chunk(b"cue ", b"\x01\x02\x03") + riff_chunk(b"junk", b"x" * 7))
        self._roundtrip(p, b"id3 ")
        with wave.open(p, "rb") as w:                                     # Standard-Leser kann die Datei noch öffnen
            self.assertEqual(w.getnframes(), 44160)
        self.assertEqual(MP3File(p).text("TIT2")[:9], "Noch eine")         # ID3 hat Vorrang vor INFO

    def test_aiff_and_aifc_write_roundtrip(self):
        self._roundtrip(self.aiff(extra=riff_chunk(b"NAME", b"Alt", False)), b"ID3 ")
        self._roundtrip(self.aiff("c.aifc", form=b"AIFC"), b"ID3 ")

    def test_existing_chunk_name_kept(self):
        t = tag([text("TIT2", "x")])
        p = self.wav(chunks_after=riff_chunk(b"ID3 ", t))                 # Grossschreibung wie manche Programme
        f = MP3File(p)
        f.set_text("TIT2", "y")
        f.save()
        self.assertEqual(len(chunk_bytes(p, b"ID3 ")), 1)
        self.assertEqual(chunk_bytes(p, b"id3 "), [])

    def test_serato_geob_survives(self):
        markers = b"\x01\x01" + bytes(range(255))
        p = self.wav(chunks_after=riff_chunk(b"id3 ", tag([text("TIT2", "a"), geob("Serato Markers2", markers)])))
        f = MP3File(p)
        before = f.items["GEOB:Serato Markers2"].clone()
        f.set_text("TIT2", "b")
        f.save()
        self.assertEqual(MP3File(p).items["GEOB:Serato Markers2"], before)

    def test_remove_all_fields_removes_chunk(self):
        p = self.wav(chunks_after=riff_chunk(b"id3 ", tag([text("TIT2", "weg")])))
        audio = chunktags.audio_hash(p)
        f = MP3File(p)
        f.set("TIT2", None)
        f.save()
        self.assertEqual(chunk_bytes(p, b"id3 "), [])
        self.assertEqual(chunktags.audio_hash(p), audio)

    def test_unmodified_save_does_not_touch_file(self):
        p = self.wav()
        h = sha(p)
        MP3File(p).save()
        self.assertEqual(sha(p), h)

    def test_refuses_rf64_truncated_and_foreign(self):
        p = self.wav()
        with open(p, "r+b") as fh:                                         # als RF64 markieren
            fh.write(b"RF64")
        f = MP3File(p)
        self.assertTrue(f.rf64)
        f.set_text("TIT2", "x")
        h = sha(p)
        with self.assertRaises(ValueError):
            f.save()
        self.assertEqual(sha(p), h)
        q = self.wav("kurz.wav")
        with open(q, "r+b") as fh:
            fh.truncate(os.path.getsize(q) - 100)                         # data-Chunk abgeschnitten
        g = MP3File(q)
        g.set_text("TIT2", "x")
        h = sha(q)
        with self.assertRaises(ValueError):
            g.save()
        self.assertEqual(sha(q), h)
        r = os.path.join(self.dir, "kein.wav")
        with open(r, "wb") as fh:
            fh.write(b"\x00" * 100)
        k = MP3File(r)
        self.assertTrue(k.tag_damaged)
        k.set_text("TIT2", "x")
        with self.assertRaises(ValueError):
            k.save()

    def test_mp3_writer_refuses_wav(self):
        p = self.wav()
        h = sha(p)
        f = MP3File.__new__(MP3File)                                       # MP3-Weg an einer WAV-Datei
        f.path = p
        f.load()
        f.set_text("TIT2", "darf nicht")
        with self.assertRaises(ValueError):
            f.save()
        self.assertEqual(sha(p), h)

    def test_external_change(self):
        p = self.wav()
        f = MP3File(p)
        self.assertFalse(f.external_change())
        g = MP3File(p)
        g.set_text("TIT2", "fremd")
        g.save()
        self.assertTrue(f.external_change())

    def test_odd_tag_length_padded(self):
        p = self.wav()
        f = MP3File(p)
        f.set_text("TIT2", "abc")                                          # ungerade Länge erzwingen
        while True:
            body = b"".join(b for it in f.items.values() for b in it.to_frames(f.version))
            if (10 + len(body)) & 1:
                break
            f.set_text("TIT2", f.text("TIT2") + "x")
        f.save()
        lay = chunktags.read_layout(p)
        self.assertEqual(lay["body_end"], lay["size"])
        self.assertEqual(MP3File(p).text("TIT2"), f.text("TIT2"))

    # ------------------------------------------------------------------ Einbindung
    def test_scan_only_with_exts(self):
        self.wav("x.wav")
        d = self.dir
        mp3 = os.path.join(d, "m.mp3")
        write_mp3(mp3, [text("TIT2", "m")])
        self.assertEqual([os.path.basename(p) for p in compare.scan(d)], ["m.mp3"])          # Standard: nur MP3
        got = sorted(os.path.basename(p) for p in compare.scan(d, exts=compare.MP3_EXTS + compare.CHUNK_EXTS))
        self.assertEqual(got, ["m.mp3", "x.wav"])

    def test_session_setting_default_off_and_tagger(self):
        import shutil
        shutil.copy(self.wav("w.wav"), os.path.join(self.B, "w.wav"))
        make_aiff(os.path.join(self.B, "a.aiff"))
        from session import Session
        s = Session()
        self.assertFalse(s.settings_page()["chunk_formats"])
        self.assertEqual(s._tag_exts(), compare.MP3_EXTS)
        files, _e = core.load_files(self.B, True, exts=s._tag_exts())
        self.assertEqual(sorted(os.path.basename(f.path) for f in files), ["3.mp3"])
        s.set_chunk_formats(True)
        with self.assertRaises(ValueError):
            s.set_chunk_formats("ja")
        self.assertTrue(core.load_config().get("chunk_formats"))
        self.assertEqual(core.load_config().get("tag_formats"), ["wav", "aiff"])
        self.assertEqual(s.set_tag_formats(["flac", "wav"]), ["wav", "flac"])
        with self.assertRaises(ValueError):
            s.set_tag_formats(["mp5"])
        s.set_tag_formats(["wav", "aiff"])
        files, _e = core.load_files(self.B, True, exts=s._tag_exts(), use_cache=True)
        self.assertEqual(sorted(os.path.basename(f.path) for f in files), ["3.mp3", "a.aiff", "w.wav"])
        # über den Tagger speichern (mit Sicherung)
        s.start_tag_load(self.B, False)
        for _ in range(500):
            if s.task_status().get("done"):
                break
            time.sleep(0.02)
        names = [os.path.basename(f.path) for f in s.tag_files]
        i = names.index("w.wav")
        s.tag_set([i], "TIT2", "Aus dem Tagger")
        s.start_save()
        for _ in range(500):
            if s.task_status().get("done"):
                break
            time.sleep(0.02)
        self.assertEqual(MP3File(os.path.join(self.B, "w.wav")).text("TIT2"), "Aus dem Tagger")

    def test_backup_and_restore(self):
        p = self.wav(chunks_after=riff_chunk(b"id3 ", tag([text("TIT2", "Vorher")])))
        audio = chunktags.audio_hash(p)
        bw = backup.BackupWriter(os.path.join(self.dir, "bk"), "Test")
        bw.add(p)
        zp = bw.close()
        f = MP3File(p)
        f.set_text("TIT2", "Nachher")
        f.save()
        man = backup._manifest(zp)
        e = man["files"][0]
        self.assertEqual(e["container"], "wav")
        self.assertEqual(backup.check_entry(e)[0], "ok")
        self.assertEqual(backup.read_backup_tags(zp, e).text("TIT2"), "Vorher")
        d = backup.diff_entry(zp, e)
        self.assertEqual([r["key"] for r in d["rows"]], ["TIT2"])
        res = backup.restore(zp, safety_folder=os.path.join(self.dir, "bk2"))
        self.assertEqual(res[0][1], "restored", res)
        self.assertEqual(MP3File(p).text("TIT2"), "Vorher")
        self.assertEqual(chunktags.audio_hash(p), audio)
        self.assertEqual(backup.check_entry(e)[0], "same")

    def test_mp3_backup_layout_unchanged(self):
        lay = backup.read_layout(os.path.join(self.A, "1.mp3"))
        self.assertNotIn("container", lay)
