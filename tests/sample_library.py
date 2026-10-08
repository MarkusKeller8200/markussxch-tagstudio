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
        right = list(left)
        if i == 3:
            right = [text("TIT2", t + " (Radio Edit)"), text("TPE1", "Mara Lind feat. Oskar Vey"),
                     text("TRCK", f"{i}/12"), text("TCON", "Synth-Pop"), text("TBPM", "118"),
                     txxx("Acoustid Id", f"c07e-{i:04d}"), apic(teal),
                     comm("", "Mehr unter https://example.org/nachtfahrt")] + base
        elif i in (4, 8, 12):
            right = [text("TIT2", t), text("TPE1", "Mara Lind"), text("TRCK", f"{i}/12"),
                     text("TCON", "Synth-Pop"), txxx("Acoustid Id", f"a41f-{i:04d}"), apic(violet)] + base
        elif i in (2, 10):
            right = [x for x in left if not x.startswith(b"TXXX")] + [txxx("Acoustid Id", f"ffff-{i:04d}")]
        if i != 7:
            write_mp3(os.path.join(L, name), left, audio_seed=i)
        write_mp3(os.path.join(R, name), right, audio_seed=i)
    return L, R


if __name__ == "__main__":
    print("\n".join(build(sys.argv[1])))
