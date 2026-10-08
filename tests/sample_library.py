"""Erzeugt eine kleine Beispiel-Bibliothek (zwei Ordner) für Tests und Bildschirmfotos.

    python tests/sample_library.py ZIELORDNER
"""
import os
import struct
import sys
import zlib

from helpers import write_mp3, text, txxx, comm, frame


def png_solid(rgb, w=240, h=240) -> bytes:
    """Echtes, einfarbiges PNG (nur Standardbibliothek)."""
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def apic(data):
    return frame("APIC", b"\x00image/png\x00\x03\x00" + data)


def xml_meta(bpm, key, rating, extra=""):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<analysis version="2">\n  <tempo bpm="%s" confidence="0.92"/>\n'
            '  <key camelot="%s" open="5m"/>\n  <rating stars="%s">Gut tanzbar &amp; melodisch</rating>\n'
            '  <segments>\n    <segment start="0.0" end="31.5" type="intro"/>\n'
            '    <segment start="31.5" end="96.2" type="verse"/>%s\n  </segments>\n</analysis>' % (bpm, key, rating, extra))


def geob_xml(desc, xml):
    return frame("GEOB", b"\x00application/xml\x00\x00" + desc.encode() + b"\x00" + xml.encode())


TRACKS = ["Nordlicht", "Kaltes Glas", "Golden Hour", "Tunnelblick", "Halbschlaf", "Neonregen",
          "Ausfahrt Süd", "Lichtjahre", "Spiegelbild", "Stille Post", "Funkloch", "Nachspann"]


def build(root):
    """Links: Bibliothek, rechts: Import mit typischen Abweichungen."""
    L, R = os.path.join(root, "Bibliothek"), os.path.join(root, "Import")
    os.makedirs(L, exist_ok=True)
    os.makedirs(R, exist_ok=True)
    violet, teal = png_solid((59, 47, 99)), png_solid((31, 79, 92))
    for i, t in enumerate(TRACKS, 1):
        name = f"{i:02d} {t}.mp3"
        base = [text("TALB", "Nachtfahrt"), text("TPE2", "Mara Lind"), text("TDRC", "2021"),
                text("TSSE", "LAME 3.100")]
        left = [text("TIT2", t), text("TPE1", "Mara Lind"), text("TRCK", str(i)), text("TCON", "Synthpop"),
                txxx("Acoustid Id", f"a41f-{i:04d}"), apic(violet),
                comm("", "Mehr unter https://example.org/nachtfahrt")] + base
        left.append(txxx("Analyse", xml_meta(118, "8A", 4)))
        left.append(geob_xml("Cue-Punkte", '<cues><cue pos="12.5" name="Drop"/><cue pos="64.0" name="Break"/></cues>'))
        right = list(left)
        if i == 3:
            right = [txxx("Analyse", xml_meta(120, "8A", 5, '\n    <segment start="96.2" end="140.0" type="chorus"/>')),
                     text("TIT2", t + " (Radio Edit)"), text("TPE1", "Mara Lind feat. Oskar Vey"),
                     text("TRCK", f"{i}/12"), text("TCON", "Synth-Pop"), text("TBPM", "118"),
                     txxx("Acoustid Id", f"c07e-{i:04d}"), apic(teal),
                     comm("", "Mehr unter https://example.org/nachtfahrt")] + base
        elif i in (4, 8, 12):
            right = [text("TIT2", t), text("TPE1", "Mara Lind"), text("TRCK", f"{i}/12"),
                     text("TCON", "Synth-Pop"), txxx("Acoustid Id", f"a41f-{i:04d}"), apic(violet)] + base
        elif i in (2, 10):
            right = [x for x in left if b"Acoustid" not in x[:40]] + [txxx("Acoustid Id", f"ffff-{i:04d}")]
        if i != 7:
            write_mp3(os.path.join(L, name), left, audio_seed=i)
        write_mp3(os.path.join(R, name), right, audio_seed=i)
    return L, R


if __name__ == "__main__":
    print("\n".join(build(sys.argv[1])))
