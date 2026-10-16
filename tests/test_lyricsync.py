"""#215: Liedtext für den Player – SYLT, .lrc neben dem MP3, USLT (nur lesen)."""
import os
import time

from helpers import frame, text, write_mp3
from test_tagger_tools import Base

import lyricsync


def u16(s):
    return b"\xff\xfe" + s.encode("utf-16-le") + b"\x00\x00"


def sylt(lines, fmt=2):
    body = b"\x01eng" + bytes([fmt, 1]) + u16("")
    for ms, t in lines:
        body += u16(t) + ms.to_bytes(4, "big")
    return body


def uslt(txt):
    return b"\x03eng" + b"\x00" + txt.encode("utf-8")


class TestLyricSync(Base):
    def test_parsers(self):
        self.assertEqual(lyricsync.parse_lrc("[ar:x]\n[00:01.50]Eins\n[00:00.20][00:03.00]Zwei\nohne"),
                         [(200, "Zwei"), (1500, "Eins"), (3000, "Zwei")])
        lines, lang = lyricsync.parse_sylt(sylt([(2000, "B"), (500, "A")]))
        self.assertEqual((lines, lang), ([(500, "A"), (2000, "B")], "eng"))
        self.assertEqual(lyricsync.parse_sylt(sylt([(10, "x")], fmt=1))[0], [])        # MPEG-Frames: nicht unterstützt
        self.assertEqual(lyricsync.parse_sylt(b"\x01"), ([], ""))

    def wait(self, s):
        for _ in range(500):
            st = s.task_status()
            if st.get("done"):
                return st
            time.sleep(0.02)

    def test_session_sources(self):
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "Mit SYLT"), frame("SYLT", sylt([(1000, "Hallo"), (2500, "Welt")])),
                                                  frame("USLT", uslt("Hallo\nWelt"))], audio_seed=1)
        write_mp3(os.path.join(self.B, "b.mp3"), [text("TIT2", "Mit LRC")], audio_seed=2)
        with open(os.path.join(self.B, "b.lrc"), "w", encoding="utf-8") as fh:
            fh.write("[00:00.50]Erste\n[00:01.00]Zweite\n")
        write_mp3(os.path.join(self.B, "c.mp3"), [text("TIT2", "Nur Text"), frame("USLT", uslt("Nur so"))], audio_seed=3)
        write_mp3(os.path.join(self.B, "d.mp3"), [text("TIT2", "Ohne")], audio_seed=4)
        from session import Session
        s = Session()
        s.start_tag_load(self.B, False)
        self.wait(s)
        idx = {os.path.basename(f.path): i for i, f in enumerate(s.tag_files)}
        a = s.media_lyrics("tag", idx["a.mp3"])
        self.assertEqual((a["source"], a["synced"]), ("SYLT", [[1000, "Hallo"], [2500, "Welt"]]))
        self.assertEqual(a["plain"], "Hallo\nWelt")
        b = s.media_lyrics("tag", idx["b.mp3"])
        self.assertEqual((b["source"], b["synced"][1]), (".lrc", [1000, "Zweite"]))
        self.assertEqual(b["plain"], "Erste\nZweite")
        c = s.media_lyrics("tag", idx["c.mp3"])
        self.assertEqual((c["source"], c["synced"], c["plain"]), ("USLT", [], "Nur so"))
        d = s.media_lyrics("tag", idx["d.mp3"])
        self.assertEqual((d["source"], d["plain"]), ("", ""))
        with self.assertRaises(ValueError):
            s.media_lyrics("tag", 99)
        self.assertFalse(s.tag_files[idx["a.mp3"]].is_modified())                 # nur lesen
