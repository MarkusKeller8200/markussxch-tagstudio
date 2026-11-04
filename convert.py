"""Konverter MP3 ↔ WAV und MP3 ↔ AIFF mit Tags (#451, Release 4.16.0 „Audioformate“).

Umgewandelt wird mit FFmpeg (wie bei Lautheit/Stems: FFmpeg aus dem Stems-Plugin, `imageio_ffmpeg` oder Suchpfad).
Das Original wird nie verändert; die neue Datei entsteht als temporäre Datei im Zielordner, bekommt die Tags des
Originals (ID3 → ID3-Chunk und zurück, inkl. Cover, Bewertung, eigene Felder, Serato-Daten) und wird erst dann unter
ihren Namen gelegt. Bestehende Dateien werden nie überschrieben.

Hinweise für die Oberfläche: MP3 → WAV/AIFF verbessert die Qualität nicht; WAV/AIFF → MP3 ist verlustbehaftet
(Bitrate wählbar, Standard 320 kbit/s CBR). Serato-Cues und -Beatgrid werden übernommen, können sich beim MP3 aber um
den Encoder-Versatz (wenige Millisekunden) verschieben – in Serato prüfen.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

TARGETS = {"wav": ".wav", "aiff": ".aiff", "mp3": ".mp3"}
SOURCES = (".mp3", ".wav", ".aif", ".aiff", ".aifc")
BITRATES = (128, 192, 256, 320)
DEFAULT_BITRATE = 320
RUN_TIMEOUT = 1800


class Cancelled(Exception):
    pass


def find_ffmpeg() -> str:
    """FFmpeg suchen; "" wenn keines da ist."""
    cands = []
    try:
        import plugins
        cands.append(os.path.join(plugins.shared_root(), "stems", "ffmpeg", "ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    except Exception:  # noqa: BLE001
        pass
    for c in cands:
        if os.path.isfile(c):
            return c
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pass
    return shutil.which("ffmpeg") or ""


def kind_of(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return "mp3" if ext == ".mp3" else "wav" if ext == ".wav" else "aiff" if ext in (".aif", ".aiff", ".aifc") else ""


def target_path(src: str, target: str, folder: str | None) -> str:
    base = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(folder or os.path.dirname(os.path.abspath(src)), base + TARGETS[target])


def plan(paths, target: str, folder: str | None, dirty=()) -> list[dict]:
    """Je Datei {"src", "dst", "problem"} – problem "" = wird umgewandelt. folder None = neben dem Original."""
    if target not in TARGETS:
        raise ValueError("Ziel muss wav, aiff oder mp3 sein")
    dirty = {os.path.normcase(os.path.abspath(p)) for p in dirty}
    rows, seen = [], set()
    for p in paths:
        src = os.path.abspath(p)
        dst = target_path(src, target, folder)
        k = os.path.normcase(dst)
        problem = ""
        if not kind_of(src):
            problem = "Format wird nicht umgewandelt"
        elif kind_of(src) == target:
            problem = "ist schon in diesem Format"
        elif not os.path.isfile(src):
            problem = "Datei fehlt"
        elif os.path.normcase(src) in dirty:
            problem = "ungespeicherte Änderungen – zuerst speichern"
        elif os.path.exists(dst):
            problem = "Ziel gibt es schon – wird nicht überschrieben"
        elif k in seen:
            problem = "gleicher Zielname wie eine andere Datei"
        seen.add(k)
        rows.append({"src": src, "dst": dst, "problem": problem})
    return rows


def _bits(f) -> int:
    b = int(getattr(f, "bits", 0) or 0)
    return b if b in (16, 24, 32) else 16


def ffmpeg_cmd(ff: str, src: str, out: str, target: str, bitrate: int, bits: int, rate: int) -> list[str]:
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", src, "-map", "0:a:0", "-vn",
           "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact"]
    if rate:
        cmd += ["-ar", str(rate)]
    if target == "mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", f"{bitrate}k", "-id3v2_version", "0", "-write_id3v1", "0", "-f", "mp3"]
    elif target == "wav":
        cmd += ["-c:a", f"pcm_s{bits}le", "-f", "wav"]
    else:
        cmd += ["-c:a", f"pcm_s{bits}be", "-f", "aiff"]
    return cmd + [out]


def _run(cmd, cancel=None):
    import time
    flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
    with tempfile.TemporaryFile() as log:                  # Fehlertext in eine Datei – kein volles Rohr
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=log, creationflags=flags)
        t0 = time.time()
        while p.poll() is None:
            if (cancel is not None and cancel.is_set()) or time.time() - t0 > RUN_TIMEOUT:
                p.kill()
                p.wait()
                raise Cancelled() if cancel is not None and cancel.is_set() else RuntimeError("FFmpeg: Zeitlimit")
            time.sleep(0.1)
        log.seek(0)
        err = log.read()[-4000:].decode("utf-8", "replace").strip()
    if p.returncode != 0:
        raise RuntimeError("FFmpeg: " + (err.splitlines()[-1] if err else f"Fehler {p.returncode}"))


def convert_one(src, dst: str, target: str, bitrate: int = DEFAULT_BITRATE, ff: str = "", cancel=None) -> str:
    """Eine Datei umwandeln und die Tags übernehmen. src = Pfad oder geladene Datei (MP3File/ChunkFile)."""
    from compare import copy_tags
    from id3tags import MP3File
    f = src if hasattr(src, "items") else MP3File(src)
    ff = ff or find_ffmpeg()
    if not ff:
        raise RuntimeError("FFmpeg nicht gefunden – das Stems-Plugin installieren (bringt FFmpeg mit) oder FFmpeg in "
                           "den Suchpfad legen.")
    if bitrate not in BITRATES:
        raise ValueError("Bitrate nicht erlaubt")
    if os.path.exists(dst):
        raise FileExistsError(dst)
    folder = os.path.dirname(dst)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tagstudio_conv_", suffix=TARGETS[target], dir=folder)
    os.close(fd)
    try:
        rate = int(getattr(f, "samplerate", 0) or 0)
        _run(ffmpeg_cmd(ff, f.path, tmp, target, bitrate, _bits(f), rate if rate in (32000, 44100, 48000, 88200, 96000) else 0),
             cancel)
        g = MP3File(tmp) if target == "mp3" else _chunk(tmp)
        copy_tags(f, g, list(f.items))
        g.set_version(f.version if f.version in (3, 4) else 3)
        g.save()
        if os.path.exists(dst):
            raise FileExistsError(dst)
        os.replace(tmp, dst)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return dst


def _chunk(path):
    import chunktags
    g = chunktags.ChunkFile.__new__(chunktags.ChunkFile)
    g.path = path
    g.load()
    return g


def has_serato(f) -> bool:
    return any(k.startswith("GEOB:Serato") for k in getattr(f, "items", {}))
