"""ZIP-Downloads entpacken (#336): Beatport & Co. liefern gekaufte Titel als ZIP. Neue ZIP-Dateien in einem
Download-Ordner werden entpackt – nur Audiodateien, flach in denselben Ordner, nie überschreiben – und das ZIP danach
in den Unterordner `_entpackt` verschoben (nie gelöscht).

Sicherheit: Einträge mit absolutem Pfad oder „..“ lehnen das ganze ZIP ab (Zip-Slip), Grössenlimit je Eintrag und
gesamt, unvollständige Downloads (`.crdownload`, `.part`, gerade noch geschriebene ZIPs) bleiben unberührt.
"""
from __future__ import annotations

import os
import shutil
import time
import zipfile

AUDIO_EXT = (".mp3", ".wav", ".aif", ".aiff", ".flac", ".m4a", ".ogg")
DONE_DIR = "_entpackt"
MAX_MEMBER = 2 << 30          # 2 GB je Audiodatei
MAX_TOTAL = 20 << 30          # 20 GB je ZIP
SETTLE = 5.0                  # so lange muss ein ZIP unverändert sein (Download fertig)


def _unsafe(name: str) -> bool:
    n = name.replace("\\", "/")
    return n.startswith("/") or (len(n) > 1 and n[1] == ":") or ".." in n.split("/")


def _unique(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    k = 2
    while os.path.exists(f"{base} ({k}){ext}"):
        k += 1
    return f"{base} ({k}){ext}"


def pending(folder: str, now: float | None = None) -> list[str]:
    """ZIP-Dateien direkt im Ordner, deren Download fertig ist (nicht in den letzten SETTLE Sekunden geändert)."""
    if not folder or not os.path.isdir(folder):
        return []
    now = time.time() if now is None else now
    out = []
    for n in sorted(os.listdir(folder), key=str.lower):
        p = os.path.join(folder, n)
        if n.startswith(".") or not n.lower().endswith(".zip") or not os.path.isfile(p):
            continue
        try:
            if now - os.path.getmtime(p) < SETTLE:
                continue
        except OSError:
            continue
        out.append(p)
    return out


def unpack(zpath: str) -> dict:
    """Ein ZIP entpacken. → {zip, files: [Pfade], skipped: [Texte], error: "" | Grund, moved: Pfad}"""
    folder = os.path.dirname(zpath)
    res = {"zip": os.path.basename(zpath), "files": [], "skipped": [], "error": "", "moved": ""}
    try:
        with zipfile.ZipFile(zpath) as z:
            infos = z.infolist()
            bad = [zi.filename for zi in infos if _unsafe(zi.filename)]
            if bad:
                res["error"] = f"abgelehnt – unsicherer Pfad im ZIP ({bad[0]})"
                return res
            audio = [zi for zi in infos if not zi.is_dir() and os.path.basename(zi.filename).lower().endswith(AUDIO_EXT)
                     and not os.path.basename(zi.filename).startswith((".", "._"))]
            if sum(zi.file_size for zi in audio) > MAX_TOTAL or any(zi.file_size > MAX_MEMBER for zi in audio):
                res["error"] = "abgelehnt – zu gross"
                return res
            if not audio:
                res["error"] = "keine Audiodateien im ZIP"
                return res
            for zi in audio:
                name = os.path.basename(zi.filename.replace("\\", "/"))
                dest = os.path.join(folder, name)
                if os.path.exists(dest):
                    res["skipped"].append(f"{name}: gibt es schon – nicht überschrieben")
                    continue
                tmp = dest + ".part"
                with z.open(zi) as src, open(tmp, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
                os.replace(tmp, dest)
                res["files"].append(dest)
    except (OSError, zipfile.BadZipFile, RuntimeError) as ex:
        res["error"] = f"nicht lesbar ({ex})"
        return res
    done = os.path.join(folder, DONE_DIR)
    try:
        os.makedirs(done, exist_ok=True)
        res["moved"] = _unique(os.path.join(done, os.path.basename(zpath)))
        os.replace(zpath, res["moved"])
    except OSError as ex:
        res["error"] = f"entpackt, aber nicht verschoben ({ex})"
        res["moved"] = ""
    return res


def unpack_folders(folders) -> dict:
    """Alle fertigen ZIPs in den Ordnern entpacken. → {zips: [Ergebnis je ZIP], files: n, skipped: n, errors: [Texte]}"""
    out = {"zips": [], "files": 0, "skipped": 0, "errors": []}
    for f in dict.fromkeys(x for x in folders if x):
        for zp in pending(f):
            r = unpack(zp)
            out["zips"].append(r)
            out["files"] += len(r["files"])
            out["skipped"] += len(r["skipped"])
            if r["error"]:
                out["errors"].append(f"{r['zip']}: {r['error']}")
    return out
