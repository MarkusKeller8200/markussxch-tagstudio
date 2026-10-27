"""Mix analysieren (#261) – Titel der eigenen Bibliothek in DJ-Mixes erkennen, lokal (Prototyp, Entscheid M6).

Verfahren: eigener Audio-Fingerabdruck mit Abfrage in Tempo-Stufen (fp.py, docs/KONZEPT-MIXSCAN.md). Die Rechnung
läuft in worker.py im Python der Plugin-Umgebung (NumPy, SciPy, imageio-ffmpeg); dieses Modul sammelt die Dateien,
führt den Index nach und schreibt den Messbericht. Alles bleibt auf dem eigenen Rechner – nichts wird hochgeladen.
"""
import json
import os
import shutil
import time

AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".aif", ".aiff", ".ogg", ".opus")

ACTIONS = [
    {"id": "index", "label": "Bibliothek indexieren (Test) …", "where": "page", "run_label": "Indexieren",
     "needs_selection": False,
     "description": "Liest die Titel der gewählten Ordner und legt ihren Fingerabdruck im Benutzerordner ab. Für die "
                    "Messung genügen etwa 200 Titel – darunter die Titel deines Test-Mixes.",
     "options": [
         {"key": "folders", "type": "folders", "label": "Ordner (leer = alle Bibliotheken)"},
         {"key": "limit", "type": "number", "label": "Höchstens so viele Titel (0 = alle)", "default": 200},
         {"key": "hint", "type": "info",
          "label": "Der Index enthält genau die gewählten Titel; unveränderte Titel werden nicht neu gelesen. "
                   "Es wird nichts an den Dateien geändert."}]},
    {"id": "index_bg", "label": "Bibliothek im Hintergrund indexieren …", "where": "page", "run_label": "Im Hintergrund indexieren", "background": True,
     "needs_selection": False,
     "description": "Wie „Bibliothek indexieren“, aber als Hintergrund-Auftrag mit niedriger Priorität – du kannst "
                    "weiterarbeiten. Abbrechen jederzeit; beim nächsten Mal geht es dort weiter, wo es aufgehört hat.",
     "options": [
         {"key": "folders", "type": "folders", "label": "Ordner (leer = alle Bibliotheken)"},
         {"key": "limit", "type": "number", "label": "Höchstens so viele Titel (0 = alle)", "default": 0},
         {"key": "hint", "type": "info",
          "label": "Der Index enthält genau die gewählten Titel; unveränderte Titel werden nicht neu gelesen. "
                   "Es wird nichts an den Dateien geändert."}]},
    {"id": "analyse", "label": "Mix analysieren (Test) …", "where": "page", "run_label": "Analysieren",
     "needs_selection": False,
     "description": "Sucht die indexierten Titel in einer Mix-Datei und schreibt einen Messbericht (Startzeit, Titel, "
                    "Tempo, Sicherheit). Mit bekannter Tracklist wird die Trefferquote berechnet.",
     "options": [
         {"key": "mix", "type": "text", "label": "Mix-Datei (vollständiger Pfad; MP3, WAV, FLAC, M4A …)"},
         {"key": "tracklist", "type": "textarea",
          "label": "Bekannte Tracklist (optional, je Zeile „Künstler - Titel“) – für die Trefferquote"},
         {"key": "pitch", "type": "check", "label": "Auch ohne Keylock gespielte Titel suchen (Tempo und Tonhöhe "
                                                   "geändert, dauert etwa doppelt so lange)", "default": True},
         {"key": "hint", "type": "info",
          "label": "Nur eigene Dateien – TagStudio lädt nichts von YouTube, SoundCloud oder Mixcloud herunter."}]},
    {"id": "selftest", "label": "Selbsttest mit eigenen Titeln …", "where": "page", "run_label": "Testen",
     "needs_selection": False,
     "description": "Baut aus zufällig gewählten indexierten Titeln einen Test-Mix (je 70 s, Tempo −6 … +6 %, mit und "
                    "ohne Keylock, überblendet) und prüft, ob die Analyse sie wiederfindet – ganz ohne Tracklist.",
     "options": [{"key": "count", "type": "number", "label": "Anzahl Titel im Test-Mix", "default": 8},
                 {"key": "hint", "type": "info",
                  "label": "Der Test-Mix liegt danach unter Plugin-Daten › mixscan › index › selbsttest.mp3 (wird beim "
                           "nächsten Selbsttest überschrieben)."}]},
]


# =========================================================================== Index-Verwaltung
def _index_dir(ctx) -> str:
    d = os.path.join(ctx.data_dir, "index")
    os.makedirs(d, exist_ok=True)
    return d


def _manifest_path(ctx) -> str:
    return os.path.join(_index_dir(ctx), "titel.json")


def load_manifest(ctx) -> dict:
    try:
        with open(_manifest_path(ctx), encoding="utf-8") as fh:
            m = json.load(fh)
        if isinstance(m, dict) and isinstance(m.get("files"), dict):
            m.setdefault("next", 1 + max([int(v.get("nr", 0)) for v in m["files"].values()] or [0]))
            return m
    except (OSError, ValueError):
        pass
    return {"next": 1, "files": {}}


def save_manifest(ctx, m):
    p = _manifest_path(ctx)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(m, fh, ensure_ascii=False)
    os.replace(tmp, p)


def _roots(ctx, opts) -> list:
    roots = [x.strip() for x in str(opts.get("folders") or "").splitlines() if x.strip()]
    if not roots and ctx._session is not None and hasattr(ctx._session, "_lib_roots"):
        roots = [r["path"] for r in ctx._session._lib_roots()["roots"]]
    return [r for r in roots if os.path.isdir(r)]


def scan(roots, limit=0, cancel=None) -> list:
    """Audiodateien der Ordner (sortiert, ohne versteckte Ordner), höchstens limit."""
    out, seen = [], set()
    for r in roots:
        for dp, dns, fns in os.walk(r):
            if cancel and cancel():
                return out
            dns[:] = sorted(d for d in dns if not d.startswith("."))
            for fn in sorted(fns):
                if fn.lower().endswith(AUDIO_EXT) and not fn.startswith("."):
                    p = os.path.join(dp, fn)
                    k = os.path.normcase(os.path.abspath(p))
                    if k not in seen:
                        seen.add(k)
                        out.append(p)
                        if limit and len(out) >= limit:
                            return out
    return out


def plan(manifest: dict, paths: list) -> tuple[list, list]:
    """Was neu gelesen bzw. entfernt werden muss → ([(Nr., Pfad)], [Nr.]); manifest wird nachgeführt."""
    files = manifest["files"]
    want = {}
    for p in paths:
        try:
            st = os.stat(p)
        except OSError:
            continue
        want[p] = (st.st_size, int(st.st_mtime))
    drop = [v["nr"] for k, v in files.items() if k not in want]
    for k in [k for k in files if k not in want]:
        del files[k]
    todo = []
    for p, (size, mtime) in want.items():
        e = files.get(p)
        if e and e.get("size") == size and e.get("mtime") == mtime and e.get("keys"):
            continue
        nr = e["nr"] if e else manifest["next"]
        if not e:
            manifest["next"] += 1
        files[p] = {"nr": nr, "size": size, "mtime": mtime, "keys": 0}
        todo.append((nr, p))
    return todo, drop


# =========================================================================== Tracklist und Bericht
def track_name(path: str) -> tuple[str, str]:
    """(Künstler, Titel) aus den Tags (MP3), sonst aus dem Dateinamen „Künstler - Titel“."""
    if path.lower().endswith(".mp3"):
        try:
            from id3tags import MP3File
            f = MP3File(path)
            f.load()
            a, t = f.text("TPE1").replace("\x00", ", "), f.text("TIT2")
            if a or t:
                return a, t
        except Exception:  # noqa: BLE001 – dann Dateiname
            pass
    stem = os.path.splitext(os.path.basename(path))[0]
    if " - " in stem:
        a, t = stem.split(" - ", 1)
        return a.strip(), t.strip()
    return "", stem


def _mix(m: str) -> str:
    """Fassung für den Vergleich: Original und Extended gelten als gleich (Beatport: Extended = Original)."""
    return "" if m in ("", "extended", "extended club", "club") else m


def _key(artist, title):
    import playlists
    t, mix = playlists.split_title(title)
    return playlists.artist_keys(artist), t, _mix(mix)


def compare(expected_text: str, found: list) -> dict:
    """Bekannte Tracklist mit den erkannten Titeln vergleichen. found: [{artist, title}] →
    {expected, hit, miss, other, extra}. „other“: gleicher Titel, aber eine andere Fassung (z. B. Remix statt Extended
    Mix) – zählt nicht als erkannt (Messung 27.10.2026: „Space (Extended Mix)“ statt „Space (Paradoks Remix)“)."""
    import playlists
    exp, _unknown = playlists.parse_tracklist(expected_text or "", "text")
    fk = [_key(x["artist"], x["title"]) for x in found]
    hit, miss, other, used = [], [], [], set()
    for e in exp:
        r = e["ref"]
        ea, et, em = _key(r.get("artist", ""), r.get("title", ""))
        cands = [i for i, (fa, ft, fm) in enumerate(fk) if i not in used and ft and (ft == et or ft in et or et in ft)
                 and (not ea or not fa or ea & fa)]
        same = [i for i in cands if fk[i][2] == em]
        name = f"{r.get('artist', '')} - {r.get('title', '')}"
        if same:
            used.add(same[0])
            hit.append(name)
        elif cands:
            used.add(cands[0])
            other.append(f"{name} → {name_of(found[cands[0]]['artist'], found[cands[0]]['title'])}")
        else:
            miss.append(name)
    extra = [name_of(found[i]["artist"], found[i]["title"]) for i in range(len(found)) if i not in used]
    return {"expected": len(exp), "hit": hit, "miss": miss, "other": other, "extra": extra}


def merge_rows(rows: list, gap: float = 60.0) -> list:
    """Aufeinanderfolgende Abschnitte desselben Titels (gleicher Künstler und Titel, auch andere Fassung wie Dub Mix)
    mit höchstens gap Sekunden Abstand zusammenfassen – der Abschnitt mit den meisten Treffern gibt Datei und Fassung
    vor, die übrigen Fassungen stehen unter „auch“ (Messung 27.10.2026: „Hypnotic“ in sechs Stücken)."""
    out = []
    for r in sorted(rows, key=lambda x: x["start"]):
        a, t, _m = _key(r["artist"], r["title"])
        last = out[-1] if out else None
        if last and r["start"] - last["end"] <= gap and last["_t"] == t and (not a or not last["_a"] or a & last["_a"]):
            best = r if r["hits"] > last["hits"] else last
            alts = set(last.get("also") or []) | {name_of(x["artist"], x["title"]) for x in (r, last) if x is not best}
            merged = {**best, "start": last["start"], "end": max(last["end"], r["end"]), "hits": last["hits"] + r["hits"],
                      "blocks": last.get("blocks", 0) + r.get("blocks", 0), "conf": max(last["conf"], r["conf"]),
                      "_a": last["_a"], "_t": t}
            alts.discard(name_of(best["artist"], best["title"]))
            if alts:
                merged["also"] = sorted(alts)
            out[-1] = merged
        else:
            out.append({**r, "_a": a, "_t": t})
    for r in out:
        r.pop("_a", None)
        r.pop("_t", None)
    return out


def name_of(artist, title) -> str:
    return f"{artist} - {title}" if artist else title


def fmt_time(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def near_misses(blocks, found, by_nr, n=10) -> list:
    """Indexierte Titel, die nicht erkannt wurden, mit ihrem stärksten Block (Treffer) und der Zahl der Blöcke, in denen
    sie unter den drei Besten waren – zeigt, ob ein Titel knapp unter der Schwelle lag (Messung #261)."""
    best, cnt = {}, {}
    for b in blocks:
        for c in b.get("cands") or []:
            tid, hits = c[1], c[0]
            if tid in found:
                continue
            cnt[tid] = cnt.get(tid, 0) + 1
            if hits > best.get(tid, (0, 0))[0]:
                best[tid] = (hits, b.get("start", 0))
    out = []
    for tid in sorted(best, key=lambda t: -best[t][0])[:n]:
        a, t = track_name(by_nr.get(tid, "")) if by_nr.get(tid) else ("", "?")
        out.append({"track": tid, "name": name_of(a, t), "hits": best[tid][0], "at": best[tid][1], "blocks": cnt[tid]})
    return out


def report_text(mix, res, rows, cmp, idx_info, near=None, self_excluded=False) -> str:
    L = [f"Mix analysieren – Messbericht ({time.strftime('%Y-%m-%d %H:%M')})", "",
         f"Mix: {mix}", f"Länge: {fmt_time(res['duration'])} · Analyse: {res['secs']} s",
         f"Index: {idx_info}", "", "Erkannte Titel:"]
    for r in rows:
        L.append(f"  {fmt_time(r['start'])}–{fmt_time(r['end'])}  {name_of(r['artist'], r['title'])}  "
                 f"(Tempo {r['tempo']:+.1f} %{'' if r['keylock'] else ', ohne Keylock'}, Sicherheit {round(r['conf'] * 100)} %"
                 f"{', unsicher' if r['conf'] < 0.6 else ''})"
                 + (f" – auch: {', '.join(r['also'])}" if r.get("also") else ""))
    if not rows:
        L.append("  – keine –")
    if self_excluded:
        L += ["", "Hinweis: Der Mix liegt selbst im indexierten Ordner und wurde nicht mitgezählt."]
    if near:
        L += ["", "Nicht erkannte Titel mit den meisten Treffern (zum Vergleich: echte Treffer liegen meist über 40 je 5 s):"]
        L += [f"  {x['name']}: höchstens {x['hits']} Treffer (bei {fmt_time(x['at'])}), {x['blocks']}× unter den Besten"
              for x in near]
    if cmp and cmp["expected"]:
        q = round(100 * len(cmp["hit"]) / cmp["expected"])
        L += ["", f"Abgleich mit der bekannten Tracklist: {len(cmp['hit'])} von {cmp['expected']} erkannt ({q} %)."]
        if cmp.get("other"):
            L += ["Gleicher Titel, aber andere Fassung in der Bibliothek (zählt nicht als erkannt):"] + [f"  {x}" for x in cmp["other"]]
        if cmp["miss"]:
            L += ["Nicht erkannt (nicht im Index oder nicht gefunden):"] + [f"  {x}" for x in cmp["miss"]]
        if cmp["extra"]:
            L += ["Erkannt, aber nicht in der Tracklist (falsch oder fehlt dort):"] + [f"  {x}" for x in cmp["extra"]]
    L += ["", "Bitte diesen Bericht im Issue #261 anhängen bzw. die Zahlen eintragen."]
    return "\n".join(L) + "\n"


# =========================================================================== Worker
def _work(ctx, job, on_event) -> None:
    import tempfile
    work = tempfile.mkdtemp(prefix="arbeit-", dir=ctx.data_dir)
    job_path = os.path.join(work, "auftrag.json")
    with open(job_path, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False)
    state = {"fatal": ""}

    def on_line(line):
        k = line.find("@@{")
        if k < 0:
            return
        try:
            ev = json.loads(line[k + 2:])
        except ValueError:
            return
        if ev.get("event") == "fatal":
            state["fatal"] = ev.get("msg", "")
        elif ev.get("event") == "status":
            ctx.status(ev.get("msg", ""))
        else:
            on_event(ev)
    try:
        rc, tail = ctx.run_env([os.path.join(os.path.dirname(os.path.abspath(__file__)), "worker.py"), job_path], on_line)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if rc != 0 or state["fatal"]:
        details = "\n".join(x for x in tail if "@@{" not in x)[-3000:]
        if details:
            ctx.log(details)
        raise RuntimeError(state["fatal"] or f"Analyse fehlgeschlagen (Code {rc}) – Details im Protokoll.")


def run_index(ctx, opts) -> dict:
    roots = _roots(ctx, opts)
    if not roots:
        raise ValueError("Kein Ordner gewählt und keine Bibliothek festgelegt (Einstellungen › Speicherort und Ordner).")
    try:
        limit = max(0, int(float(opts.get("limit") or 0)))
    except (TypeError, ValueError):
        limit = 0
    ctx.status("Suche Titel …")
    paths = scan(roots, limit, ctx.cancelled)
    m = load_manifest(ctx)
    todo, drop = plan(m, paths)
    by_nr = {v["nr"]: k for k, v in m["files"].items()}
    info = {"failed": 0, "built": {}}

    def on_event(ev):
        kind = ev.get("event")
        if kind == "start":
            ctx.progress(ev["i"], ev["n"], "Lese " + os.path.basename(ev.get("path", "")))
        elif kind == "done":
            p = by_nr.get(ev["nr"])
            if p in m["files"]:
                m["files"][p].update(keys=ev["keys"], dur=ev["dur"])
            info["n"] = info.get("n", 0) + 1
            if info["n"] % 25 == 0:                  # Zwischenstand sichern: nach Abbruch oder Absturz geht es weiter
                save_manifest(ctx, {**m, "files": {k: v for k, v in m["files"].items() if v.get("keys")}})
        elif kind == "fail":
            info["failed"] += 1
            ctx.log(f"Fehler bei {os.path.basename(ev.get('path', ''))}: {ev.get('msg', '')}")
        elif kind == "built":
            info["built"] = ev
    try:
        _work(ctx, {"task": "index", "dir": _index_dir(ctx), "files": todo, "drop": drop}, on_event)
    finally:
        m["files"] = {k: v for k, v in m["files"].items() if v.get("keys")}
        save_manifest(ctx, m)
    b = info["built"]
    mb = b.get("bytes", 0) / 1e6
    per1000 = mb / max(1, b.get("tracks", 1)) * 1000
    m["stats"] = {"tracks": b.get("tracks", 0), "keys": b.get("keys", 0), "bytes": b.get("bytes", 0),
                  "secs": b.get("secs", 0), "at": time.strftime("%Y-%m-%d %H:%M")}
    save_manifest(ctx, m)
    msg = (f"Index: {b.get('tracks', 0)} Titel ({len(todo)} neu gelesen, {len(drop)} entfernt), {mb:.1f} MB "
           f"(≈ {per1000:.0f} MB je 1000 Titel), {b.get('secs', 0)} s.")
    if info["failed"]:
        msg += f" {info['failed']} Datei(en) mit Fehler – siehe Protokoll."
    ctx.log(msg)
    return {"message": msg}


def run_analyse(ctx, opts) -> dict:
    mix = str(opts.get("mix") or "").strip().strip('"')
    if not mix or not os.path.isfile(mix):
        raise ValueError("Bitte den vollständigen Pfad einer Mix-Datei angeben.")
    m = load_manifest(ctx)
    if not m["files"]:
        raise ValueError("Noch kein Index – zuerst „Bibliothek indexieren (Test)“.")
    by_nr = {v["nr"]: k for k, v in m["files"].items()}
    key = os.path.normcase(os.path.abspath(mix))
    exclude = [v["nr"] for k, v in m["files"].items() if os.path.normcase(os.path.abspath(k)) == key]
    if exclude:                         # Mix liegt im indexierten Ordner: würde sich selbst finden (Messung 27.10.2026)
        ctx.log("Der Mix ist selbst im Index – er wird bei der Analyse nicht mitgezählt.")
    got = {}

    def on_event(ev):
        if ev.get("event") == "step":
            ctx.progress(ev["i"], ev["n"], "Vergleiche Tempo-Stufen …")
        elif ev.get("event") == "result":
            got.update(ev)
    _work(ctx, {"task": "analyse", "dir": _index_dir(ctx), "mix": mix, "pitch": bool(opts.get("pitch", True)),
                "exclude": exclude}, on_event)
    rows = []
    for s in got.get("segments") or []:
        p = by_nr.get(s["track"], "")
        a, t = track_name(p) if p else ("", "?")
        rows.append({**s, "path": p, "artist": a, "title": t})
    rows = merge_rows(rows)
    cmp = compare(opts.get("tracklist") or "", [r for r in rows if r["conf"] >= 0.6]) if str(opts.get("tracklist") or "").strip() else None
    st = m.get("stats") or {}
    idx_info = f"{len(m['files'])} Titel, {st.get('bytes', 0) / 1e6:.1f} MB"
    near = near_misses(got.get("blocks") or [], {r["track"] for r in rows}, by_nr)
    text = report_text(mix, got, rows, cmp, idx_info, near, bool(exclude))
    out_dir = os.path.join(ctx.data_dir, "berichte")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, time.strftime("%Y-%m-%d_%H%M%S_") + os.path.splitext(os.path.basename(mix))[0][:60])
    with open(base + ".txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(base + ".json", "w", encoding="utf-8") as fh:
        json.dump({"mix": mix, "result": got, "rows": rows, "compare": cmp}, fh, ensure_ascii=False, indent=1)
    ctx.output(base + ".txt")
    ctx.log(text)
    sure = sum(1 for r in rows if r["conf"] >= 0.6)
    msg = f"{sure} Titel erkannt ({len(rows) - sure} unsicher) in {fmt_time(got.get('duration', 0))} Mix, Analyse {got.get('secs', 0)} s."
    if cmp and cmp["expected"]:
        msg += f" Tracklist: {len(cmp['hit'])} von {cmp['expected']} erkannt ({round(100 * len(cmp['hit']) / cmp['expected'])} %)."
    msg += " Bericht: " + os.path.basename(base) + ".txt"
    return {"message": msg}


def run_selftest(ctx, opts) -> dict:
    import random
    m = load_manifest(ctx)
    pool = [(v["nr"], k, v.get("dur") or 0) for k, v in m["files"].items()
            if (v.get("dur") or 0) >= 100 and os.path.isfile(k)]
    try:
        n = max(2, min(16, int(float(opts.get("count") or 8))))
    except (TypeError, ValueError):
        n = 8
    if len(pool) < 2:
        raise ValueError("Zu wenig indexierte Titel (mindestens 2 mit über 100 s) – zuerst „Bibliothek indexieren (Test)“.")
    pick = random.sample(pool, min(n, len(pool)))
    by_nr = {v["nr"]: k for k, v in m["files"].items()}
    got, exp = {}, {}

    def on_event(ev):
        if ev.get("event") == "step":
            ctx.progress(ev["i"], ev["n"], "Vergleiche Tempo-Stufen …")
        elif ev.get("event") == "expected":
            exp.update(ev)
        elif ev.get("event") == "result":
            got.update(ev)
    _work(ctx, {"task": "selftest", "dir": _index_dir(ctx), "tracks": pick, "pitch": True}, on_event)
    found = {s["track"]: s for s in got.get("segments") or [] if s["conf"] >= 0.6}
    lines = [f"Mix analysieren – Selbsttest ({time.strftime('%Y-%m-%d %H:%M')})", "",
             f"Index: {len(m['files'])} Titel · Test-Mix {fmt_time(got.get('duration', 0))} · Analyse {got.get('secs', 0)} s", ""]
    ok = 0
    for e in exp.get("items") or []:
        a, t = track_name(by_nr.get(e["track"], ""))
        s = found.get(e["track"])
        if s:
            ok += 1
        lines.append(f"  {'✓' if s else '✗'} {fmt_time(e['start'])}  {name_of(a, t)}  (Tempo {e['tempo']:+.1f} %"
                     f"{'' if e['keylock'] else ', ohne Keylock'})"
                     + (f" → erkannt {fmt_time(s['start'])}, {s['tempo']:+.1f} %, Sicherheit {round(s['conf'] * 100)} %" if s else ""))
    wrong = [s for s in got.get("segments") or [] if s["conf"] >= 0.6 and s["track"] not in {e["track"] for e in exp.get("items") or []}]
    for s in wrong:
        a, t = track_name(by_nr.get(s["track"], ""))
        lines.append(f"  ! {fmt_time(s['start'])}  {name_of(a, t)} – falsch erkannt (Sicherheit {round(s['conf'] * 100)} %)")
    total = len(exp.get("items") or [])
    lines += ["", f"Ergebnis: {ok} von {total} erkannt ({round(100 * ok / max(1, total))} %), {len(wrong)} falsch."]
    text = "\n".join(lines) + "\n"
    out_dir = os.path.join(ctx.data_dir, "berichte")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, time.strftime("%Y-%m-%d_%H%M%S_selbsttest.txt"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(path[:-4] + ".json", "w", encoding="utf-8") as fh:
        json.dump({"expected": exp, "result": got}, fh, ensure_ascii=False, indent=1)
    ctx.output(path)
    ctx.log(text)
    return {"message": f"Selbsttest: {ok} von {total} Titeln erkannt ({round(100 * ok / max(1, total))} %), {len(wrong)} falsch. "
                       f"Bericht: {os.path.basename(path)}"}


def run(action, ctx, files, opts):
    if action == "selftest":
        return run_selftest(ctx, opts)
    if action in ("index", "index_bg"):
        return run_index(ctx, opts)
    if action == "analyse":
        return run_analyse(ctx, opts)
    raise ValueError(f"Unbekannte Aktion: {action}")


def status(ctx):
    m = load_manifest(ctx)
    st = m.get("stats") or {}
    if not m["files"]:
        return "Noch kein Index."
    return f"Index: {len(m['files'])} Titel, {st.get('bytes', 0) / 1e6:.1f} MB (Stand {st.get('at', '?')})."
