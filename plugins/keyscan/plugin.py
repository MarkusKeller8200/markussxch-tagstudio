"""Tonart (OpenKeyScan) – Tonart-Erkennung ohne Zusatz-App (#245).

Die Analyse läuft in worker.py im Python der eigenen Plugin-Umgebung (PyTorch, librosa, PyAV). Netz und Modell
lädt die Installation von einem festen, geprüften Stand des OpenKeyScan-Repositorys (plugin.json "env.files").
Vorschläge, Vergleich und Zwischenspeicher teilt sich das Plugin mit „openkeyscan“ (#244) über keyscan.py.
"""
import json
import os
import shutil

import keyscan

OPTIONS = [
    {"key": "tkey", "type": "check", "label": "Auch TKEY vorschlagen (in deiner Schreibweise)", "default": True},
    {"key": "force", "type": "check", "label": "Abweichende Tonart in TKEY ebenfalls ankreuzen", "default": False},
    {"key": "cache", "type": "check", "label": "Frühere Ergebnisse verwenden (unveränderte Dateien nicht neu analysieren)",
     "default": True},
    {"key": "hint", "type": "info",
     "label": "Ergebnis kommt als Vorschau: OPENKEYSCAN_KEY (Camelot) und auf Wunsch TKEY. TKEY ist nur angekreuzt, "
              "wenn es leer ist – vorhandene Tonarten werden verglichen (gleich, verwandt, abweichend)."},
]

ACTIONS = [
    {"id": "scan", "label": "Tonart erkennen (OpenKeyScan) …", "short": "Tonart erkennen", "where": "tagger",
     "run_label": "Tonart erkennen",
     "description": "Analysiert die markierten Titel und zeigt die erkannte Tonart als Vorschau mit Vergleich.",
     "options": OPTIONS},
    {"id": "prefetch", "label": "Tonart im Hintergrund analysieren …", "short": "Im Hintergrund", "where": "tagger",
     "run_label": "Analysieren",
     "background": True,
     "description": "Analysiert die markierten Titel im Hintergrund und merkt sich nur das Ergebnis – es wird nichts "
                    "geschrieben. Danach zeigt „Tonart erkennen“ die Vorschau sofort.",
     "options": [{"key": "hint", "type": "info",
                  "label": "Ideal für grosse Mengen: weiterarbeiten, später „Tonart erkennen (OpenKeyScan)“ wählen."}]},
]


def cache(ctx) -> keyscan.Cache:
    return keyscan.Cache(os.path.join(ctx.shared_dir, "ergebnisse.json"))


def analyse(ctx, files, store) -> dict:
    """Dateien ohne gültiges Ergebnis analysieren. → {Pfad: Ergebnis} (nur neue); Fehler im Protokoll."""
    eng = os.path.join(ctx.shared_dir, "engine")
    model = os.path.join(eng, "openkeyscan3.pt")
    if not (os.path.isfile(model) and os.path.isfile(os.path.join(eng, "model.py"))):
        raise RuntimeError("Das Tonart-Modell fehlt – bitte auf der Plugin-Seite „Neu installieren …“ wählen.")
    work = os.path.join(ctx.data_dir, "arbeit")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    job = {"files": [f.path for f in files], "engine": eng, "model": model,
           "device": "auto"}
    job_path = os.path.join(work, "auftrag.json")
    with open(job_path, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False)
    state = {"fatal": "", "failed": 0, "new": {}}
    n = len(files)

    def on_line(line):
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
        elif kind == "loaded":
            ctx.status(f"Modell geladen ({ev.get('device', '')}) – starte Analyse …")
        elif kind == "start":
            ctx.progress(ev["i"], n, "Analysiere " + os.path.basename(ev["path"]))
        elif kind == "done":
            code = keyscan.code_of(ev.get("camelot"))
            if code:
                store.put(ev["path"], code, ev.get("conf"), "keyscan")
                state["new"][ev["path"]] = store.get(ev["path"])
            ctx.progress(ev["i"] + 1, n, "Fertig: " + os.path.basename(ev["path"]))
        elif kind == "fail":
            state["failed"] += 1
            ctx.log(f"Fehler bei {os.path.basename(ev.get('path', ''))}: {ev.get('msg', '')}")
        elif kind == "fatal":
            state["fatal"] = ev.get("msg", "")

    ctx.status("Starte Tonart-Umgebung …")
    try:
        rc, tail = ctx.run_env([os.path.join(os.path.dirname(__file__), "worker.py"), job_path], on_line)
    finally:
        store.save()                         # auch bei Abbruch: Bisheriges behalten
        shutil.rmtree(work, ignore_errors=True)
    if rc != 0 or state["fatal"]:
        details = "\n".join(l for l in tail if "@@{" not in l)[-3000:]
        ctx.log(details)
        raise RuntimeError(f"Tonart-Erkennung fehlgeschlagen: {state['fatal'] or f'Code {rc}'}\n\n{details[-800:]}")
    if state["failed"]:
        ctx.log(f"{state['failed']} Titel mit Fehler.")
    return state["new"]


def run(action, ctx, files, opts):
    if action not in ("scan", "prefetch"):
        raise ValueError(f"Unbekannte Aktion: {action}")
    store = cache(ctx)
    reuse = action == "prefetch" or opts.get("cache", True)
    todo = [f for f in files if not (reuse and store.get(f.path))]
    if todo:
        analyse(ctx, todo, store)
    if action == "prefetch":
        done = sum(1 for f in files if store.get(f.path))
        return {"message": f"Tonart für {done} von {len(files)} Titel(n) bereit – „Tonart erkennen (OpenKeyScan)“ "
                           f"zeigt die Vorschau ({len(files) - len(todo)} schon bekannt)."}
    stats, missing = {}, 0
    for f in files:
        e = store.get(f.path)
        if not e:
            missing += 1
            continue
        rel = keyscan.propose(ctx, f, e["camelot"], e.get("conf"), want_tkey=bool(opts.get("tkey", True)),
                              force_tkey=bool(opts.get("force")))
        stats[rel] = stats.get(rel, 0) + 1
    msg = f"Tonart für {len(files) - missing} von {len(files)} Titel(n) erkannt"
    s = keyscan.summary(stats)
    msg += f" – Vergleich mit TKEY: {s}." if s else "."
    if missing:
        msg += f" {missing} ohne Ergebnis – siehe Protokoll."
    return {"message": msg}


def status(ctx):
    n = len(cache(ctx).data)
    return f"{n} Ergebnis(se) zwischengespeichert." if n else ""
