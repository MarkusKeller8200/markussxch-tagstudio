"""Stems – Titel in Einzelspuren trennen (audio-separator).

Benutzt die Python-Schnittstelle von audio-separator:
    Separator(output_dir, output_format, model_file_dir, output_single_stem).load_model(name).separate(path)
"""
import logging
import os
import re
import shutil

MODELS = [
    ["htdemucs_ft.yaml", "4 Spuren: Vocals, Drums, Bass, Other – Demucs ft (gute Qualität)"],
    ["htdemucs_6s.yaml", "6 Spuren: zusätzlich Guitar und Piano – Demucs 6s"],
    ["htdemucs.yaml", "4 Spuren, schneller – Demucs"],
    ["model_bs_roformer_ep_317_sdr_12.9755.ckpt", "2 Spuren: Vocals / Instrumental – BS-RoFormer (beste Gesangstrennung)"],
    ["model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt", "2 Spuren: Vocals / Instrumental – Mel-Band-RoFormer"],
]
STEMS = [["", "Alle Spuren"], ["Vocals", "Nur Vocals (Gesang)"], ["Instrumental", "Nur Instrumental (2-Spur-Modelle)"],
         ["Drums", "Nur Drums"], ["Bass", "Nur Bass"]]
FORMATS = [["FLAC", "FLAC (verlustfrei, kleiner als WAV)"], ["WAV", "WAV"], ["MP3", "MP3 (mit Tags und Cover)"]]

ACTIONS = [{
    "id": "separate",
    "label": "Stems erzeugen …",
    "where": "tagger",
    "run_label": "Stems erzeugen",
    "description": "Trennt die markierten Titel in Einzelspuren. Die Originale bleiben unverändert.",
    "options": [
        {"key": "model", "type": "select", "label": "Modell", "choices": MODELS, "default": "htdemucs_ft.yaml"},
        {"key": "stem", "type": "select", "label": "Spuren", "choices": STEMS, "default": ""},
        {"key": "format", "type": "select", "label": "Format", "choices": FORMATS, "default": "FLAC"},
        {"key": "dest", "type": "select", "label": "Ablage",
         "choices": [["beside", "Neben dem Titel, Unterordner „<Titel> – Stems“"],
                     ["folder", "In einem festen Ordner (unten), je Titel ein Unterordner"]], "default": "beside"},
        {"key": "folder", "type": "folder", "label": "Fester Ordner", "default": ""},
        {"key": "overwrite", "type": "check", "label": "Vorhandene Stems überschreiben", "default": False},
        {"key": "hint", "type": "info",
         "label": "Beim ersten Gebrauch wird das Modell heruntergeladen (einige hundert MB). Ohne Grafikkarte dauert ein Titel einige Minuten."},
    ],
}]

_STEM_RE = re.compile(r"_\(([^)]+)\)")


def _target_dir(f, opts):
    base = os.path.splitext(os.path.basename(f.path))[0]
    root = os.path.dirname(f.path)
    if opts.get("dest") == "folder" and opts.get("folder"):
        root = opts["folder"]
    return os.path.join(root, f"{base} – Stems"), base


def _stem_name(fname):
    m = _STEM_RE.search(os.path.basename(fname))
    return m.group(1) if m else os.path.splitext(os.path.basename(fname))[0]


def _tag_mp3(src, path, stem):
    """Tags und Cover der Quelle in eine MP3-Spur übernehmen; Titel bekommt „(Stem)“."""
    from id3tags import MP3File
    from compare import copy_tags
    dst = MP3File(path)
    copy_tags(src, dst, list(src.items))
    title = src.text("TIT2") or os.path.splitext(os.path.basename(src.path))[0]
    dst.set_text("TIT2", f"{title} ({stem})")
    dst.save()


def run(action, ctx, files, opts):
    if action != "separate":
        raise ValueError(f"Unbekannte Aktion: {action}")
    if opts.get("dest") == "folder" and not opts.get("folder"):
        raise ValueError("Bitte einen festen Ordner angeben oder „Neben dem Titel“ wählen.")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg wurde nicht gefunden. Windows: „winget install ffmpeg“, Mac: „brew install ffmpeg“ – danach TagStudio neu starten.")

    todo, skipped = [], 0
    for f in files:
        out, _base = _target_dir(f, opts)
        if os.path.isdir(out) and os.listdir(out) and not opts.get("overwrite"):
            skipped += 1
            ctx.log(f"Übersprungen (Stems vorhanden): {os.path.basename(f.path)}")
            continue
        todo.append(f)
    if not todo:
        return {"message": f"Nichts zu tun – für alle {skipped} Titel gibt es schon Stems."}

    ctx.status("Lade audio-separator …")
    from audio_separator.separator import Separator   # schwerer Import erst hier

    work = os.path.join(ctx.data_dir, "arbeit")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    sep = Separator(output_dir=work, output_format=opts.get("format", "FLAC"),
                    model_file_dir=os.path.join(ctx.data_dir, "modelle"),
                    output_single_stem=opts.get("stem") or None, log_level=logging.WARNING)
    ctx.status(f"Lade Modell {opts['model']} (beim ersten Mal mit Download) …")
    sep.load_model(model_filename=opts["model"])

    done, made = 0, 0
    for i, f in enumerate(todo):
        name = os.path.basename(f.path)
        ctx.progress(i, len(todo), f"Trenne {name}")
        try:
            outs = sep.separate(f.path) or []
        except Exception as ex:  # noqa: BLE001 – einzelne Datei darf den Lauf nicht abbrechen
            ctx.log(f"Fehler bei {name}: {ex}")
            continue
        dest, base = _target_dir(f, opts)
        os.makedirs(dest, exist_ok=True)
        for o in outs:
            src = o if os.path.isabs(o) else os.path.join(work, o)
            if not os.path.exists(src):
                continue
            stem = _stem_name(src)
            target = os.path.join(dest, f"{base} ({stem}){os.path.splitext(src)[1].lower()}")
            if os.path.exists(target):
                os.remove(target)
            shutil.move(src, target)
            made += 1
            if target.lower().endswith(".mp3"):
                try:
                    _tag_mp3(f, target, stem)
                except Exception as ex:  # noqa: BLE001
                    ctx.log(f"Tags für {os.path.basename(target)} nicht übernommen: {ex}")
        ctx.output(dest)
        ctx.log(f"{name}: {len(outs)} Spur(en) → {dest}")
        done += 1
    ctx.progress(len(todo), len(todo), "fertig")
    shutil.rmtree(work, ignore_errors=True)
    msg = f"Stems für {done} von {len(todo)} Titel(n) erzeugt ({made} Dateien)."
    if skipped:
        msg += f" {skipped} übersprungen (schon vorhanden)."
    return {"message": msg}
