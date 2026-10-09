"""Stems-Worker: läuft im Python der Plugin-Umgebung (nicht in TagStudio).

Aufruf: python worker.py auftrag.json
Meldungen an TagStudio als Zeilen „@@{json}“; alles andere ist Protokoll.
"""
import json
import logging
import os
import shutil
import sys
import traceback


def emit(**kw):
    print("@@" + json.dumps(kw, ensure_ascii=False), flush=True)


def hook_tqdm():
    """Fortschrittsbalken (tqdm) von audio-separator/Demucs als Ereignisse „tick“ melden.
    tqdm schreibt sonst nur „\r45%|███“ ohne Zeilenende – das kommt bei TagStudio nicht als Fortschritt an."""
    try:
        import time
        import tqdm.std as tq
    except Exception:  # noqa: BLE001
        return
    orig_update, orig_close = tq.tqdm.update, tq.tqdm.close
    last = {"t": 0.0}

    def tick(bar, force=False):
        total = getattr(bar, "total", None)
        if not total:
            return
        now = time.monotonic()
        if not force and now - last["t"] < 0.4:
            return
        last["t"] = now
        emit(event="tick", n=float(bar.n), total=float(total), unit=str(getattr(bar, "unit", "") or ""),
             desc=str(getattr(bar, "desc", "") or ""))

    def update(self, n=1):
        r = orig_update(self, n)
        try:
            tick(self)
        except Exception:  # noqa: BLE001
            pass
        return r

    def close(self):
        try:
            if not getattr(self, "disable", False):
                tick(self, force=True)
        except Exception:  # noqa: BLE001
            pass
        return orig_close(self)

    tq.tqdm.update, tq.tqdm.close = update, close


def ensure_ffmpeg(data_dir):
    """FFmpeg aus imageio-ffmpeg bereitstellen, falls keins im Suchpfad liegt."""
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        d = os.path.join(data_dir, "ffmpeg")
        os.makedirs(d, exist_ok=True)
        target = os.path.join(d, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if not os.path.exists(target):
            shutil.copy2(exe, target)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    except Exception as ex:  # noqa: BLE001
        emit(event="warn", msg=f"FFmpeg nicht verfügbar: {ex}")


def main(job_path):
    with open(job_path, encoding="utf-8") as fh:
        job = json.load(fh)
    ensure_ffmpeg(job["data_dir"])
    hook_tqdm()
    emit(event="status", msg="Lade audio-separator …")
    from audio_separator.separator import Separator

    kw = dict(output_dir=job["work"], output_format=job["format"], model_file_dir=job["model_dir"],
              output_single_stem=job.get("stem") or None, log_level=logging.WARNING)
    if job.get("directml"):
        kw["use_directml"] = True
    sep = Separator(**kw)
    emit(event="status", msg=f"Lade Modell {job['model']} (beim ersten Mal mit Download) …")
    sep.load_model(model_filename=job["model"])
    emit(event="loaded")
    for i, path in enumerate(job["files"]):
        emit(event="start", i=i, path=path)
        try:
            outs = sep.separate(path) or []
            outs = [o if os.path.isabs(o) else os.path.join(job["work"], o) for o in outs]
            emit(event="done", i=i, path=path, outputs=outs)
        except Exception as ex:  # noqa: BLE001 – nächste Datei versuchen
            traceback.print_exc()
            emit(event="fail", i=i, path=path, msg=f"{type(ex).__name__}: {ex}")
    emit(event="end")


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        emit(event="fatal", msg=f"{type(ex).__name__}: {ex}")
        sys.exit(2)
