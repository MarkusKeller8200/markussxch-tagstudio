"""
thumbs.py – Vorschaubilder (PNG) aus Cover-Daten erzeugen, ohne Zusatzpakete.

Tk kann von Haus aus nur PNG/GIF anzeigen. Für JPEG wird – in dieser Reihenfolge – verwendet:
  1. Pillow (falls installiert)
  2. Windows: .NET System.Drawing über PowerShell (immer vorhanden)
  3. macOS:   sips (immer vorhanden)
  4. Linux:   ImageMagick (convert / magick) oder ffmpeg
Ergebnisse werden im Speicher und auf der Platte zwischengespeichert (~/TagStudio/cache).
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

CACHE_DIR = os.path.join(os.path.expanduser("~"), "TagStudio", "cache")
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

_PS = (
    "$ErrorActionPreference='Stop';Add-Type -AssemblyName System.Drawing;"
    "$s=[System.Drawing.Image]::FromFile($args[0]);"
    "$r=[Math]::Min({size}/$s.Width,{size}/$s.Height);if($r -gt 1){{$r=1}};"
    "$w=[Math]::Max(1,[int]($s.Width*$r));$h=[Math]::Max(1,[int]($s.Height*$r));"
    "$b=New-Object System.Drawing.Bitmap $w,$h;$g=[System.Drawing.Graphics]::FromImage($b);"
    "$g.InterpolationMode='HighQualityBicubic';$g.DrawImage($s,0,0,$w,$h);"
    "$b.Save($args[1],[System.Drawing.Imaging.ImageFormat]::Png);$g.Dispose();$b.Dispose();$s.Dispose()"
)


def backend() -> str:
    """Name des verfügbaren Verfahrens (für Anzeige/Diagnose)."""
    try:
        import PIL  # noqa: F401
        return "Pillow"
    except ImportError:
        pass
    if IS_WIN:
        return "Windows (.NET)"
    if IS_MAC and shutil.which("sips"):
        return "macOS (sips)"
    for tool in ("magick", "convert", "ffmpeg"):
        if shutil.which(tool):
            return tool
    return ""


def cache_path(data: bytes, size: int) -> str:
    return os.path.join(CACHE_DIR, f"{hashlib.md5(data).hexdigest()}_{size}.png")


def make_png(data: bytes, size: int) -> bytes | None:
    """Liefert PNG-Bytes, auf max. size×size verkleinert, oder None. Kann einige 100 ms dauern."""
    cp = cache_path(data, size)
    try:
        with open(cp, "rb") as fh:
            return fh.read()
    except OSError:
        pass
    png = _convert(data, size)
    if png:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cp, "wb") as fh:
                fh.write(png)
        except OSError:
            pass
    return png


def _convert(data: bytes, size: int) -> bytes | None:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.thumbnail((size, size))
        out = io.BytesIO()
        im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB").save(out, "PNG")
        return out.getvalue()
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        return None
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else (".gif" if data[:3] == b"GIF" else ".jpg")
    tmpdir = tempfile.mkdtemp(prefix="mp3thumb_")
    src, dst = os.path.join(tmpdir, "in" + ext), os.path.join(tmpdir, "out.png")
    try:
        with open(src, "wb") as fh:
            fh.write(data)
        if IS_WIN:
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                   "-Command", "& {" + _PS.format(size=size) + "}", src, dst]
            flags = 0x08000000  # CREATE_NO_WINDOW – kein aufblitzendes Konsolenfenster
            subprocess.run(cmd, capture_output=True, timeout=30, creationflags=flags)
        elif IS_MAC and shutil.which("sips"):
            subprocess.run(["sips", "-s", "format", "png", "-Z", str(size), src, "--out", dst],
                           capture_output=True, timeout=30)
        elif shutil.which("magick") or shutil.which("convert"):
            tool = shutil.which("magick") or shutil.which("convert")
            subprocess.run([tool, src + "[0]", "-thumbnail", f"{size}x{size}>", dst], capture_output=True, timeout=30)
        elif shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-vf",
                            f"scale='min({size},iw)':'min({size},ih)':force_original_aspect_ratio=decrease",
                            dst], capture_output=True, timeout=30)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            with open(dst, "rb") as fh:
                return fh.read()
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return None
