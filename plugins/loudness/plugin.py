"""Lautheit messen (#119): EBU R128 mit FFmpeg, Werte als Felder vorschlagen; optional angeglichene Kopie.

FFmpeg wird gesucht: 1. Kopie des Stems-Plugins (Plugin-Daten/stems/ffmpeg), 2. imageio-ffmpeg, 3. PATH.
Messung: ffmpeg -af volumedetect,ebur128=peak=true → „I: -9.4 LUFS“, „LRA: 5.1 LU“, „Peak: -0.3 dBFS“;
Clipping: volumedetect zählt Samples auf Vollaussteuerung („histogram_0db“ von „n_samples“). Reparieren (adeclip)
wird bewusst nicht angeboten: bei MP3 erkennt es nach dem Dekodieren kaum etwas und ist sehr langsam.
Angleichen (nur auf Wunsch): zwei Durchgänge loudnorm, neu kodiert mit libmp3lame 320 kbit/s in einen eigenen Ordner;
die Tags werden byte-genau aus dem Original übernommen. Das Original wird nie verändert.
"""
import os
import re
import shutil
import subprocess

ACTIONS = [{
    "id": "measure", "label": "Lautheit messen …", "where": "tagger", "run_label": "Messen",
    "description": "Misst integrierte Lautheit (LUFS), True Peak und Lautheitsbereich und schlägt sie als Felder vor.",
    "options": [
        {"key": "lufs", "type": "check", "label": "TXXX:LUFS_I (integrierte Lautheit)", "default": True},
        {"key": "peak", "type": "check", "label": "TXXX:TRUE_PEAK (dBTP)", "default": True},
        {"key": "lra", "type": "check", "label": "TXXX:LOUDNESS_RANGE (LU)", "default": False},
        {"key": "clip", "type": "check", "label": "TXXX:CLIPPING (Anteil übersteuerter Samples in %, nur wenn vorhanden)", "default": False},
        {"key": "rg", "type": "check", "label": "ReplayGain (TXXX:REPLAYGAIN_TRACK_GAIN/PEAK, Referenz −18 LUFS)", "default": False},
        {"key": "normalize", "type": "check", "label": "Zusätzlich angeglichene Kopie erzeugen (neu kodiert, 320 kbit/s)", "default": False},
        {"key": "target", "type": "number", "label": "Ziel-Lautheit (LUFS) für die Kopie", "default": -10.5},
        {"key": "folder", "type": "text", "label": "Ordner für die Kopien (leer = Unterordner „Angeglichen“)", "default": ""},
        {"type": "info", "label": "Das Messen ändert keine Audiodaten. Angleichen kodiert neu (kleiner Qualitätsverlust) – "
                                  "deshalb nur als Kopie; Platinum Notes bleibt im Workflow der Standard."},
    ],
}]

RX = {"I": re.compile(r"^\s*I:\s*(-?[\d.]+|-inf)\s*LUFS", re.M), "LRA": re.compile(r"^\s*LRA:\s*([\d.]+)\s*LU", re.M),
      "Peak": re.compile(r"^\s*Peak:\s*(-?[\d.]+|-inf)\s*dBFS", re.M),
      "n": re.compile(r"n_samples:\s*(\d+)"), "clip": re.compile(r"histogram_0db:\s*(\d+)")}
CLIP_WARN = 0.01          # ab 0,01 % Samples auf Vollaussteuerung gilt ein Titel als übersteuert


def find_ffmpeg(ctx=None) -> str:
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
        import imageio_ffmpeg  # noqa: F401
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        pass
    p = shutil.which("ffmpeg")
    if p:
        return p
    raise RuntimeError("FFmpeg nicht gefunden – das Stems-Plugin installieren (bringt FFmpeg mit) oder FFmpeg in den "
                       "Suchpfad legen.")


def _run(cmd, cancel=None):
    flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags)
    return p.returncode, p.stderr


def parse(text: str) -> dict:
    """Werte aus der Zusammenfassung von ebur128 (letzte Vorkommen = Summary)."""
    out = {}
    for k, rx in RX.items():
        m = rx.findall(text)
        if m:
            v = m[-1]
            out[k] = None if v == "-inf" else float(v)
    if out.get("n"):
        out["clip_pct"] = 100.0 * (out.get("clip") or 0) / out["n"]
    return out


def measure(ff: str, path: str) -> dict:
    rc, err = _run([ff, "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0", "-af", "volumedetect,ebur128=peak=true",
                    "-f", "null", "-"])
    if rc != 0:
        raise RuntimeError((err.strip().splitlines() or ["FFmpeg-Fehler"])[-1])
    d = parse(err)
    if d.get("I") is None:
        raise RuntimeError("Keine Lautheit ermittelt (Stille oder kein Audio).")
    return d


def normalize(ff: str, path: str, dest: str, target: float, m: dict):
    """Zwei Durchgänge loudnorm (lineare Angleichung, True Peak −1 dBTP), Tags aus dem Original übernehmen."""
    import json
    rc, err = _run([ff, "-hide_banner", "-nostats", "-i", path, "-map", "0:a:0",
                    "-af", f"loudnorm=I={target}:TP=-1:LRA=20:print_format=json", "-f", "null", "-"])
    js = err[err.rfind("{"):err.rfind("}") + 1] if "{" in err else "{}"
    meas = json.loads(js) if js.strip() else {}
    af = (f"loudnorm=I={target}:TP=-1:LRA=20:linear=true:measured_I={meas.get('input_i', m['I'])}"
          f":measured_TP={meas.get('input_tp', m.get('Peak') or 0)}:measured_LRA={meas.get('input_lra', m.get('LRA') or 0)}"
          f":measured_thresh={meas.get('input_thresh', -70)}:offset={meas.get('target_offset', 0)}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".tmp.mp3"
    rc, err = _run([ff, "-hide_banner", "-nostats", "-y", "-i", path, "-map", "0:a:0", "-af", af, "-ar", "44100",
                    "-c:a", "libmp3lame", "-b:a", "320k", "-map_metadata", "-1", "-id3v2_version", "0", tmp])
    if rc != 0:
        raise RuntimeError((err.strip().splitlines() or ["FFmpeg-Fehler"])[-1])
    # Tags byte-genau aus dem Original vor das neue Audio setzen
    import backup
    lay = backup.read_layout(path)
    with open(path, "rb") as fh:
        tag = fh.read(lay["audio_start"])
    with open(tmp, "rb") as fh, open(dest, "wb") as out:
        out.write(tag)
        shutil.copyfileobj(fh, out)
    os.remove(tmp)


def run(action, ctx, files, opts):
    if action != "measure":
        raise ValueError(f"Unbekannte Aktion: {action}")
    ff = find_ffmpeg(ctx)
    ctx.log(f"FFmpeg: {ff}")
    done, copies, clipped, errors = 0, 0, 0, []
    for n, f in enumerate(files):
        ctx.check_cancel()
        name = os.path.basename(f.path)
        ctx.progress(n, len(files), name)
        try:
            m = measure(ff, f.path)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{name}: {ex}")
            continue
        done += 1
        note = f"{m['I']:.1f} LUFS · True Peak {m['Peak']:.1f} dBTP" if m.get("Peak") is not None else f"{m['I']:.1f} LUFS"
        cp = m.get("clip_pct")
        if cp is not None and cp >= CLIP_WARN:
            note += f" · übersteuert: {cp:.2f} % der Samples"
            clipped += 1
        if opts.get("clip") and cp is not None and cp >= CLIP_WARN:
            ctx.propose(f, "TXXX:CLIPPING", f"{cp:.2f}", "CLIPPING", note=note, group=name,
                        hint="Anteil der Samples auf Vollaussteuerung")
        if opts.get("lufs"):
            ctx.propose(f, "TXXX:LUFS_I", f"{m['I']:.1f}", "LUFS_I", note=note, group=name)
        if opts.get("peak") and m.get("Peak") is not None:
            ctx.propose(f, "TXXX:TRUE_PEAK", f"{m['Peak']:.1f}", "TRUE_PEAK", note=note, group=name)
        if opts.get("lra") and m.get("LRA") is not None:
            ctx.propose(f, "TXXX:LOUDNESS_RANGE", f"{m['LRA']:.1f}", "LOUDNESS_RANGE", note=note, group=name)
        if opts.get("rg"):
            ctx.propose(f, "TXXX:REPLAYGAIN_TRACK_GAIN", f"{-18.0 - m['I']:+.2f} dB", "ReplayGain Gain", note=note, group=name)
            if m.get("Peak") is not None:
                ctx.propose(f, "TXXX:REPLAYGAIN_TRACK_PEAK", f"{10 ** (m['Peak'] / 20):.6f}", "ReplayGain Peak", note=note, group=name)
        if opts.get("normalize"):
            folder = (opts.get("folder") or "").strip() or os.path.join(os.path.dirname(f.path), "Angeglichen")
            dest = os.path.join(folder, name)
            try:
                if os.path.abspath(dest) == os.path.abspath(f.path):
                    raise RuntimeError("Ziel wäre das Original – anderen Ordner wählen.")
                normalize(ff, f.path, dest, float(opts.get("target") or -10.5), m)
                ctx.output(dest)
                copies += 1
            except Exception as ex:  # noqa: BLE001
                errors.append(f"{name} (Angleichen): {ex}")
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{done} von {len(files)} Titel(n) gemessen" + (f", {clipped} übersteuert" if clipped else "") \
        + (f", {copies} angeglichene Kopie(n)" if copies else "")
    if errors:
        ctx.log("\n".join(errors))
        msg += f", {len(errors)} Fehler (siehe Protokoll)"
    return {"message": msg + "."}
