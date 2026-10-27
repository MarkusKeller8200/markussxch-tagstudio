"""Mix-analysieren-Worker (#261): läuft im Python der Plugin-Umgebung (NumPy, SciPy, imageio-ffmpeg).

Aufruf: python worker.py auftrag.json
Auftrag „index“:   {"task": "index", "dir": Indexordner, "files": [[Nr., Pfad], …], "drop": [Nr., …]}
Auftrag „analyse“: {"task": "analyse", "dir": Indexordner, "mix": Pfad, "pitch": true}
Meldungen an TagStudio als Zeilen „@@{json}“ (nur ASCII); alles andere ist Protokoll.

Index: je Titel eine Datei parts/<Nr>.npz (Schlüssel + Zeiten); daraus wird index.npz (sortiert) gebaut.
"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import fp  # noqa: E402


def emit(**kw):
    sys.stderr.flush()
    print("\n@@" + json.dumps(kw), flush=True)


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 – dann FFmpeg aus dem Suchpfad
        return "ffmpeg"


def do_index(job):
    d = job["dir"]
    parts = os.path.join(d, "parts")
    os.makedirs(parts, exist_ok=True)
    ff = ffmpeg_exe()
    for n in job.get("drop") or []:
        try:
            os.remove(os.path.join(parts, f"{int(n)}.npz"))
        except OSError:
            pass
    files = job.get("files") or []
    t0 = time.time()
    for i, (n, path) in enumerate(files):
        emit(event="start", i=i, n=len(files), path=path)
        try:
            y = fp.decode(path, ff)
            h, t = fp.fingerprint(y)
            np.savez(os.path.join(parts, f"{int(n)}.npz"), H=h, T=t)
            emit(event="done", i=i, nr=int(n), keys=int(len(h)), dur=round(len(y) / fp.SR, 1))
        except Exception as ex:  # noqa: BLE001 – einzelne Datei überspringen
            emit(event="fail", i=i, nr=int(n), path=path, msg=str(ex)[:300])
    emit(event="status", msg="Index zusammenführen …")
    built = []
    for name in os.listdir(parts):
        if name.endswith(".npz"):
            try:
                with np.load(os.path.join(parts, name)) as z:
                    built.append((int(name[:-4]), z["H"], z["T"]))
            except (OSError, ValueError):
                pass
    idx = fp.Index.build(built)
    idx.save(os.path.join(d, "index.npz"))
    emit(event="built", tracks=len(built), keys=int(len(idx.H)), bytes=fp.size_of(os.path.join(d, "index.npz")),
         secs=round(time.time() - t0, 1))


def do_analyse(job):
    d = job["dir"]
    path = os.path.join(d, "index.npz")
    if not os.path.isfile(path):
        emit(event="fatal", msg="Noch kein Index – zuerst „Bibliothek indexieren“.")
        return
    emit(event="status", msg="Index laden …")
    idx = fp.Index.load(path)
    emit(event="status", msg="Mix dekodieren …")
    t0 = time.time()
    y = fp.decode(job["mix"], ffmpeg_exe())
    if not len(y):
        emit(event="fatal", msg="Keine Audiodaten im Mix.")
        return
    modes = ("lock", "pitch") if job.get("pitch", True) else ("lock",)
    bl = fp.query(idx, y, modes=modes, progress=lambda i, n: emit(event="step", i=i, n=n), exclude=job.get("exclude") or ())
    segs = fp.segments(bl)
    emit(event="result", segments=segs, duration=round(len(y) / fp.SR, 1), secs=round(time.time() - t0, 1),
         blocks=[{"start": b["start"], "cands": [list(c) for c in b["cands"][:3]]} for b in bl])


SELF_SPEC = [(1.0, "lock"), (1.03, "lock"), (0.96, "lock"), (1.05, "lock"), (0.98, "pitch"), (1.06, "pitch"),
             (0.94, "lock"), (1.02, "pitch")]


def do_selftest(job):
    """Selbsttest mit echter Musik: aus indexierten Titeln einen Mix bauen (je 70 s aus der Mitte, Tempo ±6 % mit und
    ohne Keylock, 10 s überblendet, leises Rauschen), dann wie einen fremden Mix analysieren."""
    import subprocess
    d = job["dir"]
    ff = ffmpeg_exe()
    tracks = job["tracks"]
    args, flt, expected, t = [], "", [], 0.0
    for i, (nr, path, dur) in enumerate(tracks):
        fac, mode = SELF_SPEC[i % len(SELF_SPEC)]
        start = max(0.0, float(dur or 0) / 2 - 35)
        args += ["-ss", f"{start:.1f}", "-t", "70", "-i", path]
        f = f"atempo={fac}" if mode == "lock" else f"aresample=44100,asetrate=44100*{fac},aresample=44100"
        flt += f"[{i}:a]aformat=channel_layouts=stereo,aresample=44100,{f}[s{i}];"
        length = 70 / fac
        expected.append({"track": int(nr), "start": round(t, 1), "end": round(t + length, 1), "tempo": round((fac - 1) * 100, 1),
                         "keylock": mode == "lock"})
        t += length - 10
    cur = "s0"
    for k in range(1, len(tracks)):
        flt += f"[{cur}][s{k}]acrossfade=d=10[x{k}];"
        cur = f"x{k}"
    flt += f"anoisesrc=c=pink:a=0.02:r=44100:d=3600:seed=7,aformat=channel_layouts=stereo[n];[{cur}][n]amix=inputs=2:duration=first,volume=1.5[out]"
    out = os.path.join(d, "selbsttest.mp3")
    emit(event="status", msg="Test-Mix bauen …")
    r = subprocess.run([ff, "-nostdin", "-v", "error", "-y", *args, "-filter_complex", flt, "-map", "[out]", "-b:a", "192k", out],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if r.returncode != 0:
        emit(event="fatal", msg="Test-Mix: " + (r.stderr or b"").decode("utf-8", "replace")[-300:])
        return
    job = dict(job, mix=out)
    emit(event="expected", items=expected, mix=out)
    do_analyse(job)


def main():
    with open(sys.argv[1], encoding="utf-8") as fh:
        job = json.load(fh)
    try:
        {"index": do_index, "analyse": do_analyse, "selftest": do_selftest}[job["task"]](job)
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        emit(event="fatal", msg=str(ex)[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
