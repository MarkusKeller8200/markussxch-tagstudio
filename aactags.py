"""Rohes AAC (.aac, ADTS) – **nur lesen** (#455, Entscheid User 05.11.2026).

ADTS hat kein eigenes Tag-System. Manche Programme setzen ein ID3v2 davor (wie bei MP3) oder hängen ein ID3v1 an;
das liest TagStudio mit dem MP3-Leser. Geschrieben wird in .aac nie – für Tags die Datei als M4A speichern
(Konverter „M4A – AAC“: ohne Neukodierung, nur in den MP4-Container umgepackt).
"""
from __future__ import annotations

from id3tags import MP3File

EXTS = (".aac", ".adts")
RATES = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350]
SCAN_MAX = 64 << 20                      # höchstens 64 MB nach Frames durchsuchen


class AacFile(MP3File):
    FORMAT = "AAC"

    def load(self, cached=None, keep_raw=False):  # noqa: ARG002
        super().load()
        self.container = "aac"
        self.codec = "AAC"
        self.read_only = True
        self.save_skipped = []
        self.bits = 0
        self._adts()
        self.tag_desc = (self.tag_desc + " (nur lesen)") if self.had_v2 or self.had_v1 else "kein Tag (nur lesen)"

    def _adts(self):
        self.bitrate = self.samplerate = 0
        self.duration = 0.0
        self.channels = ""
        self.vbr = False
        end = self.size - (128 if self.had_v1 else 0)
        with open(self.path, "rb") as f:
            f.seek(self.audio_start)
            data = f.read(min(SCAN_MAX, max(0, end - self.audio_start)))
        p, frames, rate, ch = 0, 0, 0, 0
        while p + 7 <= len(data):
            if data[p] != 0xFF or (data[p + 1] & 0xF6) != 0xF0:
                if frames:
                    break
                p += 1
                continue
            sri = (data[p + 2] >> 2) & 0x0F
            ch = ((data[p + 2] & 1) << 2) | (data[p + 3] >> 6)
            ln = ((data[p + 3] & 3) << 11) | (data[p + 4] << 3) | (data[p + 5] >> 5)
            if sri >= len(RATES) or ln < 7:
                p += 1
                continue
            rate = RATES[sri]
            frames += 1
            p += ln
        if rate and frames:
            self.samplerate = rate
            self.channels = {1: "Mono", 2: "Stereo"}.get(ch, f"{ch} Kanäle")
            self.duration = frames * 1024 / rate
            self.bitrate = round(p * 8 / self.duration / 1000) if self.duration else 0

    def format_name(self) -> str:
        return "AAC"

    def v1_pending(self) -> bool:
        return False

    def save(self):
        if not self.is_modified():
            return
        raise ValueError("AAC (.aac) wird nur gelesen – für Tags die Datei als M4A speichern (Umwandeln › M4A – AAC, "
                         "ohne Neukodierung).")
