"""Stems – Titel in Einzelspuren trennen (audio-separator).

Die Trennung läuft in worker.py im Python der eigenen Plugin-Umgebung (siehe plugin.json "env"),
damit TagStudio selbst keine schweren Pakete (PyTorch …) braucht und jede Python-Version nutzen kann.
"""
import json
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
    "background": True,      # Warteschlange: Dialog schliesst sofort, Weiterarbeiten möglich
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

# Wie viele Fortschrittsbalken ein Titel durchläuft (Demucs: Modelle × 2 Verschiebungen) – nur für die Anzeige
PASSES = {"htdemucs_ft.yaml": 8, "htdemucs.yaml": 2, "htdemucs_6s.yaml": 2}

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


def _place(f, src, opts, ctx):
    """Eine erzeugte Spur an ihren Platz verschieben (und bei MP3 taggen). Liefert Zielordner."""
    dest, base = _target_dir(f, opts)
    os.makedirs(dest, exist_ok=True)
    stem = _stem_name(src)
    target = os.path.join(dest, f"{base} ({stem}){os.path.splitext(src)[1].lower()}")
    if os.path.exists(target):
        os.remove(target)
    shutil.move(src, target)
    if target.lower().endswith(".mp3"):
        try:
            _tag_mp3(f, target, stem)
        except Exception as ex:  # noqa: BLE001
            ctx.log(f"Tags für {os.path.basename(target)} nicht übernommen: {ex}")
    return dest


def run(action, ctx, files, opts):
    if action != "separate":
        raise ValueError(f"Unbekannte Aktion: {action}")
    if opts.get("dest") == "folder" and not opts.get("folder"):
        raise ValueError("Bitte einen festen Ordner angeben oder „Neben dem Titel“ wählen.")

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

    work = os.path.join(ctx.data_dir, "arbeit")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    job = {"files": [f.path for f in todo], "work": work, "format": opts.get("format", "FLAC"),
           "model": opts.get("model", "htdemucs_ft.yaml"), "stem": opts.get("stem") or "",
           "model_dir": os.path.join(ctx.data_dir, "modelle"), "data_dir": ctx.data_dir,
           "directml": ctx.env_info.get("variant") == "dml"}
    job_path = os.path.join(work, "auftrag.json")
    with open(job_path, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False)

    state = {"done": 0, "made": 0, "fatal": "", "failed": 0, "i": None, "seg": 0, "last": 0.0, "frac": 0.0}
    passes = PASSES.get(job["model"], 1)

    def on_tick(ev):
        """Fortschritt innerhalb eines Titels (Demucs rechnet mehrere Durchgänge, jeder mit eigenem Balken)."""
        f = ev["n"] / ev["total"] if ev.get("total") else 0.0
        unit = ev.get("unit", "")
        if state["i"] is None:            # vor dem ersten Titel: Modell-Download
            if unit.lower().endswith("b"):
                n, total = ev.get("n", 0), ev.get("total", 0)
                if total >= 1e5 and n <= total:          # Grösse bekannt → Prozent
                    ctx.status(f"Lade Modell herunter … {round(100 * n / total)} % von {total / 1e6:.0f} MB")
                else:                                     # Grösse unbekannt/falsch (z. B. Weiterleitung) → nur Menge
                    ctx.status(f"Lade Modell herunter … {n / 1e6:.1f} MB")
            return
        if f + 0.3 < state["last"]:       # neuer Balken → nächster Durchgang
            state["seg"] += 1
        state["last"] = f
        expect = max(passes, state["seg"] + 1)
        frac = min(0.99, max(state["frac"], (state["seg"] + f) / expect))
        state["frac"] = frac
        name = os.path.basename(todo[state["i"]].path)
        ctx.progress(state["i"], len(todo), f"Trenne {name} · {round(100 * frac)} %", frac)

    def on_line(line):
        # tqdm schreibt „\r 42%|███…“ ohne Zeilenende auf denselben Kanal – das Ereignis kann daher hinter so einem
        # Balken in derselben Zeile stehen. Deshalb nach „@@{“ suchen statt nur am Zeilenanfang.
        k = line.find("@@{")
        if k < 0:
            return
        try:
            ev = json.loads(line[k + 2:])
        except ValueError:
            return
        kind = ev.get("event")
        if kind == "status":
            ctx.status(ev.get("msg", ""))
        elif kind == "warn":
            ctx.log("Hinweis: " + ev.get("msg", ""))
        elif kind == "tick":
            on_tick(ev)
        elif kind == "loaded":
            ctx.status("Modell geladen – starte Trennung …")
        elif kind == "start":
            state.update(i=ev["i"], seg=0, last=0.0, frac=0.0)
            ctx.progress(ev["i"], len(todo), "Trenne " + os.path.basename(ev["path"]), 0.0)
        elif kind == "done":
            ctx.progress(ev["i"] + 1, len(todo), "Fertig: " + os.path.basename(ev["path"]))
            f = todo[ev["i"]]
            dest = None
            for src in ev.get("outputs", []):
                if os.path.exists(src):
                    dest = _place(f, src, opts, ctx)
                    state["made"] += 1
            if dest:
                ctx.output(dest)
                state["done"] += 1
            ctx.log(f"{os.path.basename(f.path)}: {len(ev.get('outputs', []))} Spur(en)" + (f" → {dest}" if dest else ""))
        elif kind == "fail":
            state["failed"] += 1
            ctx.log(f"Fehler bei {os.path.basename(ev.get('path', ''))}: {ev.get('msg', '')}")
        elif kind == "fatal":
            state["fatal"] = ev.get("msg", "")

    ctx.status("Starte Stems-Umgebung …")
    rc, tail = ctx.run_env([os.path.join(os.path.dirname(__file__), "worker.py"), job_path], on_line)
    shutil.rmtree(work, ignore_errors=True)
    if rc != 0 or state["fatal"]:
        details = "\n".join(l for l in tail if "@@{" not in l)[-3000:]
        ctx.log(details)
        raise RuntimeError(f"Stems fehlgeschlagen: {state['fatal'] or f'Code {rc}'}\n\n{details[-800:]}")
    ctx.progress(len(todo), len(todo), "fertig")
    msg = f"Stems für {state['done']} von {len(todo)} Titel(n) erzeugt ({state['made']} Dateien)."
    if state["failed"]:
        msg += f" {state['failed']} mit Fehler – siehe Protokoll."
    if skipped:
        msg += f" {skipped} übersprungen (schon vorhanden)."
    return {"message": msg}
