"""Mix analysieren (#261, #387) – Titel der eigenen Bibliothek in DJ-Mixes erkennen, lokal.

Verfahren: eigener Audio-Fingerabdruck mit Abfrage in Tempo-Stufen (fp.py, docs/KONZEPT-MIXSCAN.md). Die Rechnung
läuft in worker.py im Python der Plugin-Umgebung (NumPy, SciPy, imageio-ffmpeg); dieses Modul sammelt die Dateien,
führt den Index nach (von Hand, nach „Vorbereiten“ und beim Start) und gibt das Ergebnis an TagStudio, das es im
Ergebnisfenster zeigt (mixresult.py, session_mixes.py). Alles bleibt auf dem eigenen Rechner – nichts wird hochgeladen.
"""
import json
import os
import shutil
import threading
import time

AUDIO_EXT = (".mp3", ".wav", ".flac", ".m4a", ".aac", ".aif", ".aiff", ".ogg", ".opus")
_LOCK = threading.RLock()          # Warteliste (neue/verschobene Titel) – Ereignisse kommen aus anderen Threads

ACTIONS = [
    {"id": "analyse", "label": "Mix analysieren …", "short": "Mix analysieren", "where": "page", "run_label": "Analysieren",
     "needs_selection": False, "background": "option", "job_name": "mix",
     "description": "Sucht die Titel deiner Bibliothek in einer Mix-Datei (DJ-Set, Radiosendung, eigener Mix) und zeigt "
                    "die Tracklist mit Zeit, Tempo und Sicherheit – speichern als Playlist, CUE-Datei oder Text.",
     "options": [
         {"key": "mix", "type": "file", "kind": "audio", "label": "Mix-Datei (MP3, WAV, FLAC, M4A …)"},
         {"key": "pitch", "type": "check", "label": "Auch ohne Keylock gespielte Titel suchen (Tempo und Tonhöhe "
                                                   "geändert, dauert etwa doppelt so lange)", "default": True},
         {"key": "tracklist", "type": "textarea",
          "label": "Bekannte Tracklist (optional, je Zeile „Künstler - Titel“, gern mit Zeitmarke) – zum Vergleich; "
                   "Lücken mit passender Zeitmarke füllt TagStudio daraus, fehlende Titel lassen sich als Ideen merken"},
         {"key": "background", "type": "check", "default": False,
          "label": "Im Hintergrund analysieren – weiterarbeiten; das Ergebnis lässt sich danach öffnen (Fussleiste "
                   "bzw. „Frühere Analysen …“)"},
         {"key": "hint", "type": "info",
          "label": "Nur eigene Dateien – TagStudio lädt nichts von YouTube, SoundCloud oder Mixcloud herunter. Erkannt "
                   "werden nur Titel, die im Index sind."}]},
    {"id": "analyse_folder", "label": "Ordner mit Mixen analysieren …", "short": "Ordner analysieren", "where": "page",
     "run_label": "In die Warteschlange", "needs_selection": False,
     "description": "Alle Mix-Dateien eines Ordners (z. B. alle Folgen einer Radiosendung) nacheinander analysieren – je "
                    "Datei ein Hintergrund-Auftrag; die Ergebnisse erscheinen einzeln auf der Seite „Mixe“.",
     "options": [
         {"key": "folder", "type": "folder", "label": "Ordner mit Mix-Dateien"},
         {"key": "subfolders", "type": "check", "label": "Auch Unterordner", "default": False},
         {"key": "skip_done", "type": "check", "label": "Schon analysierte Mixe auslassen", "default": True},
         {"key": "pitch", "type": "check", "label": "Auch ohne Keylock gespielte Titel suchen (dauert etwa doppelt so "
                                                   "lange)", "default": True},
         {"key": "hint", "type": "info", "label": "Ein laufender Auftrag lässt sich in der Fussleiste abbrechen – die "
                                                 "anderen laufen weiter."}]},
    {"id": "index", "label": "Bibliothek indexieren …", "short": "Indexieren", "where": "page",
     "run_label": "Im Hintergrund indexieren", "background": True, "needs_selection": False,
     "description": "Liest die Titel deiner Bibliotheken und legt ihren Fingerabdruck im Benutzerordner ab – als "
                    "Hintergrund-Auftrag, du kannst weiterarbeiten. Abbrechen jederzeit; beim nächsten Mal geht es dort "
                    "weiter. Danach wird der Index automatisch nachgeführt (siehe Optionen).",
     "options": [
         {"key": "folders", "type": "folders", "label": "Ordner (leer = alle Bibliotheken)"},
         {"key": "hint", "type": "info",
          "label": "Der Index enthält genau die Titel dieser Ordner; unveränderte Titel werden nicht neu gelesen, "
                   "verschwundene entfernt. An den Dateien wird nichts geändert."}]},
    {"id": "results", "label": "Frühere Analysen …", "where": "page", "run_label": "Öffnen", "needs_selection": False,
     "direct": True,
     "description": "Gespeicherte Ergebnisse wieder öffnen – ohne neue Analyse.", "options": []},
    {"id": "settings", "label": "Einstellungen …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Wann der Index automatisch nachgeführt wird – erst, nachdem du einmal „Bibliothek indexieren …“ "
                    "gestartet hast.",
     "options": [
         {"key": "auto_add", "type": "check", "label": "Neue Titel nach „Vorbereiten“ aufnehmen", "default": True},
         {"key": "auto_start", "type": "check", "label": "Beim Start im Hintergrund nachführen (neue, geänderte und "
                                                        "gelöschte Titel)", "default": True},
         {"key": "hint", "type": "info", "label": "Verschobene Titel werden immer nachgeführt, ohne sie neu zu lesen."}]},
    {"id": "selftest", "label": "Selbsttest mit eigenen Titeln …", "where": "page", "run_label": "Testen",
     "needs_selection": False,
     "description": "Baut aus zufällig gewählten indexierten Titeln einen Test-Mix (je 70 s, Tempo −6 … +6 %, mit und "
                    "ohne Keylock, überblendet) und prüft, ob die Analyse sie wiederfindet.",
     "options": [{"key": "count", "type": "number", "label": "Anzahl Titel im Test-Mix", "default": 8},
                 {"key": "hint", "type": "info",
                  "label": "Der Test-Mix liegt danach unter Plugin-Daten › mixscan › index › selbsttest.mp3 (wird beim "
                           "nächsten Selbsttest überschrieben)."}]},
    {"id": "index_add", "label": "Index nachführen", "where": "hidden", "run_label": "Nachführen", "background": True,
     "needs_selection": False, "options": []},
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


def _settings_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "einstellungen.json")


def settings(ctx) -> dict:
    out = {"auto_add": True, "auto_start": True}
    try:
        with open(_settings_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
        out.update({k: bool(d[k]) for k in out if k in d})
    except (OSError, ValueError, TypeError):
        pass
    return out


def _pending_path(ctx) -> str:
    return os.path.join(_index_dir(ctx), "warteliste.json")


def _pending(ctx, add=(), moves=()) -> dict:
    """Warteliste lesen und ergänzen: {"add": [Pfad], "moves": [[alt, neu]]}."""
    with _LOCK:
        try:
            with open(_pending_path(ctx), encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            d = {}
        d = {"add": list(d.get("add") or []), "moves": list(d.get("moves") or [])}
        if add or moves:
            d["add"] = list(dict.fromkeys(d["add"] + [p for p in add if str(p).lower().endswith(AUDIO_EXT)]))
            d["moves"] += [[m[0], m[1]] for m in moves]
            with open(_pending_path(ctx), "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False)
        return d


def _take_pending(ctx) -> dict:
    with _LOCK:
        d = _pending(ctx) if os.path.isfile(_pending_path(ctx)) else {"add": [], "moves": []}
        try:
            os.remove(_pending_path(ctx))
        except OSError:
            pass
        return d


def apply_moves(m: dict, moves) -> int:
    """Verschobene/umbenannte Titel im Index nachführen, ohne sie neu zu lesen (gleiche Nummer, gleiche Schlüssel)."""
    n = 0
    files = m["files"]
    for old, new in moves:
        e = files.pop(old, None)
        if e is None:
            continue
        files[new] = e
        try:
            st = os.stat(new)
            e["size"], e["mtime"] = st.st_size, int(st.st_mtime)
        except OSError:
            pass
        n += 1
    return n


def on_event(ctx, event, data):
    """Index nachführen (M5): neue Titel nach „Vorbereiten“, verschobene sofort umbenennen, beim Start alles prüfen –
    nur, wenn schon einmal indexiert wurde. Die Arbeit selbst läuft als Hintergrund-Auftrag."""
    m = load_manifest(ctx)
    if not m["files"]:
        return
    st = settings(ctx)
    if event == "files_moved":
        moves = [(d.get("old"), d.get("new")) for d in data or [] if isinstance(d, dict) and d.get("old") and d.get("new")]
        if any(o in m["files"] for o, _n in moves):
            _pending(ctx, moves=[(o, n) for o, n in moves if o in m["files"]])
            ctx.queue_job("index_add")
    elif event == "files_added" and st["auto_add"]:
        if _pending(ctx, add=[p for p in data or [] if isinstance(p, str)])["add"]:
            ctx.queue_job("index_add")
    elif event == "app_started" and st["auto_start"]:
        ctx.queue_job("index", {"folders": m.get("folders", "")})


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


def plan(manifest: dict, paths: list, prune=True) -> tuple[list, list]:
    """Was neu gelesen bzw. entfernt werden muss → ([(Nr., Pfad)], [Nr.]); manifest wird nachgeführt.
    prune=False: nur hinzufügen/aktualisieren (neue Titel nach „Vorbereiten“), nichts entfernen."""
    files = manifest["files"]
    want = {}
    for p in paths:
        try:
            st = os.stat(p)
        except OSError:
            continue
        want[p] = (st.st_size, int(st.st_mtime))
    drop = [v["nr"] for k, v in files.items() if k not in want] if prune else []
    for k in ([k for k in files if k not in want] if prune else []):
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


_MIX_WORDS = {"extended", "original", "mix", "remix", "edit", "version", "club", "rmx"}


def _mix(m: str) -> str:
    """Fassung für den Vergleich: ohne Füllwörter – „Tim Engelhardt Remix, Extended“ = „Tim Engelhardt Remix“,
    Original = Extended (Beatport); übrig bleibt der Remixer bzw. „dub“, „radio“, „instrumental“ …"""
    return " ".join(w for w in str(m or "").split() if w not in _MIX_WORDS)


def _artists(artist) -> set:
    """Künstler für den Vergleich, ohne Länderzusatz wie „(FR)“ (Messung 27.10.2026: „NTO (FR)“ ≠ „NTO“)."""
    import playlists
    import re
    return playlists.artist_keys(re.sub(r"\s*[\(\[][A-Za-z]{2,3}[\)\]]", "", str(artist or "")))


def _same_artist(a: set, b: set) -> bool:
    return not a or not b or bool(a & b) or any(x.startswith(y + " ") or y.startswith(x + " ") for x in a for y in b)


def _key(artist, title):
    import playlists
    t, mix = playlists.split_title(title)
    return _artists(artist), t, _mix(mix)


_TL_TIME = None


def tracklist_times(text: str) -> list:
    """Zeitmarken je Tracklist-Zeile (in Reihenfolge der erkannten Titel): „[04:56] …“, „04:56 …“, „1:02:10 …“ →
    Sekunden bzw. None. Zeilen ohne Titel (z. B. „00:00 Intro“) zählen nicht."""
    import re
    import playlists
    out = []
    for line in str(text or "").splitlines():
        items, _u = playlists.parse_tracklist(line, "text")
        if not items:
            continue
        line = playlists.MD_LINK.sub(r"\1", line)
        m = re.match(r"\s*\[?\s*(?:(\d{1,2}):)?(\d{1,3}):(\d{2})\s*\]?", line)      # „106:00“ (MixID)
        out.append(int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None)
    return out


def compare(expected_text: str, found: list) -> dict:
    """Bekannte Tracklist mit den erkannten Titeln vergleichen. found: [{artist, title}] →
    {expected, hit, miss, other, extra}. „other“: gleicher Titel, aber eine andere Fassung (z. B. Remix statt Extended
    Mix) – zählt nicht als erkannt (Messung 27.10.2026: „Space (Extended Mix)“ statt „Space (Paradoks Remix)“).
    Unsichere Abschnitte (conf < 0.6) zählen nur, wenn sie zu einem Tracklist-Titel passen („erkannt (unsicher)“,
    Messung 27.10.2026: „Evenfall“ mit 58 %); unpassende unsichere Abschnitte erscheinen nicht unter „extra“."""
    import playlists
    exp, _unknown = playlists.parse_tracklist(expected_text or "", "text")
    times = tracklist_times(expected_text)
    fk = [_key(x["artist"], x["title"]) for x in found]
    hit, miss, other, used, timing, unsure = [], [], [], set(), [], []
    sure = [x.get("conf", 1.0) >= 0.6 for x in found]
    for n, e in enumerate(exp):
        r = e["ref"]
        ea, et, em = _key(r.get("artist", ""), r.get("title", ""))
        cands = [i for i, (fa, ft, fm) in enumerate(fk) if i not in used and ft and (ft == et or ft in et or et in ft)
                 and _same_artist(ea, fa)]
        cands.sort(key=lambda i: (not sure[i], -found[i].get("conf", 1.0)))
        same = [i for i in cands if fk[i][2] == em]
        name = f"{r.get('artist', '')} - {r.get('title', '')}"
        if same:
            used.add(same[0])
            hit.append(name)
            if not sure[same[0]]:
                unsure.append(name)
            t = times[n] if n < len(times) else None
            f = found[same[0]]
            if t is not None and f.get("track_start") is not None:
                seen = f.get("start")
                timing.append({"name": name, "list": t, "calc": f["track_start"], "seen": seen,
                               "diff": round(f["track_start"] - t),
                               # Tracklist-Zeit zwischen Titelanfang (Einblenden) und „erkannt ab“ (Titel dominiert)?
                               "inside": seen is not None and f["track_start"] - 5 <= t <= seen + 10})
        elif cands:
            used.add(cands[0])
            other.append(f"{name} → {name_of(found[cands[0]]['artist'], found[cands[0]]['title'])}")
        else:
            miss.append(name)
    extra = [name_of(found[i]["artist"], found[i]["title"]) for i in range(len(found)) if i not in used and sure[i]]
    return {"expected": len(exp), "hit": hit, "miss": miss, "other": other, "extra": extra, "timing": timing,
            "unsure": unsure}


def merge_rows(rows: list, gap: float = 60.0) -> list:
    """Aufeinanderfolgende Abschnitte desselben Titels (gleicher Künstler und Titel, auch andere Fassung wie Dub Mix)
    mit höchstens gap Sekunden Abstand zusammenfassen – der Abschnitt mit den meisten Treffern gibt Datei und Fassung
    vor, die übrigen Fassungen stehen unter „auch“ (Messung 27.10.2026: „Hypnotic“ in sechs Stücken)."""
    out = []
    for r in sorted(rows, key=lambda x: x["start"]):
        a, t, _m = _key(r["artist"], r["title"])
        last = out[-1] if out else None
        if last and r["start"] - last["end"] <= gap and last["_t"] == t and _same_artist(a, last["_a"]):
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


def plugin_version() -> str:
    """Version aus plugin.json – steht in jedem Bericht, damit Messungen vergleichbar bleiben."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin.json"), encoding="utf-8") as fh:
            return str(json.load(fh).get("version") or "?")
    except (OSError, ValueError):
        return "?"


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
    L = [f"Mix analysieren – Bericht ({time.strftime('%Y-%m-%d %H:%M')}, Plugin {plugin_version()})", "",
         f"Mix: {mix}", f"Länge: {fmt_time(res['duration'])} · Analyse: {res['secs']} s",
         f"Index: {idx_info}", "", "Erkannte Titel:"]
    for r in rows:
        anf = f"  [Titelanfang ≈ {fmt_time(max(0.0, r['track_start']))}]" if r.get("track_start") is not None else ""
        L.append(f"  {fmt_time(r['start'])}–{fmt_time(r['end'])}{anf}  {name_of(r['artist'], r['title'])}  "
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
        un = cmp.get("unsure") or []
        L += ["", f"Abgleich mit der bekannten Tracklist: {len(cmp['hit'])} von {cmp['expected']} erkannt ({q} %)"
              + (f", davon {len(un)} unsicher." if un else ".")]
        if un:
            L += ["Erkannt (unsicher – passt zur Tracklist, aber wenig Treffer):"] + [f"  {x}" for x in un]
        if cmp.get("timing"):
            d = sorted(abs(x["diff"]) for x in cmp["timing"])
            ins = sum(1 for x in cmp["timing"] if x.get("inside"))
            L += [f"Zeiten (Titelanfang berechnet gegenüber Tracklist; Median der Abweichung {d[len(d) // 2]} s; "
                  f"Tracklist-Zeit im Übergang zwischen Titelanfang und „erkannt ab“: {ins} von {len(d)}):"]
            L += [f"  {x['name']}: Tracklist {fmt_time(x['list'])} · berechnet {fmt_time(max(0.0, x['calc']))} ({x['diff']:+d} s)"
                  f" · erkannt ab {fmt_time(x['seen'])}{' ✓' if x.get('inside') else ''}" for x in cmp["timing"]]
        if cmp.get("other"):
            L += ["Gleicher Titel, aber andere Fassung in der Bibliothek (zählt nicht als erkannt):"] + [f"  {x}" for x in cmp["other"]]
        if cmp["miss"]:
            L += ["Nicht erkannt (nicht im Index oder nicht gefunden):"] + [f"  {x}" for x in cmp["miss"]]
        if cmp["extra"]:
            L += ["Erkannt, aber nicht in der Tracklist (falsch oder fehlt dort):"] + [f"  {x}" for x in cmp["extra"]]
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


def _build(ctx, m, todo, drop) -> dict:
    """Titel lesen (todo), entfernte aus dem Index nehmen (drop) und den Index neu zusammensetzen."""
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
    m["stats"] = {"tracks": b.get("tracks", 0), "keys": b.get("keys", 0), "bytes": b.get("bytes", 0),
                  "secs": b.get("secs", 0), "at": time.strftime("%Y-%m-%d %H:%M")}
    save_manifest(ctx, m)
    return info


def run_index(ctx, opts) -> dict:
    roots = _roots(ctx, opts)
    if not roots:
        raise ValueError("Kein Ordner gewählt und keine Bibliothek festgelegt (Einstellungen › Speicherort und Ordner).")
    ctx.status("Suche Titel …")
    paths = scan(roots, 0, ctx.cancelled)
    ctx.check_cancel()                                   # halbe Liste nie zum Aufräumen verwenden
    pend = _take_pending(ctx)
    m = load_manifest(ctx)
    apply_moves(m, pend["moves"])
    m["folders"] = str(opts.get("folders") or "")
    todo, drop = plan(m, paths)
    if not todo and not drop and m.get("stats"):
        save_manifest(ctx, m)
        return {"message": f"Index aktuell: {len(m['files'])} Titel."}
    info = _build(ctx, m, todo, drop)
    b = info["built"]
    msg = (f"Index: {b.get('tracks', 0)} Titel ({len(todo)} neu gelesen, {len(drop)} entfernt), "
           f"{b.get('bytes', 0) / 1e6:.1f} MB, {b.get('secs', 0)} s.")
    if info["failed"]:
        msg += f" {info['failed']} Datei(en) mit Fehler – siehe Protokoll."
    ctx.log(msg)
    return {"message": msg}


def run_index_add(ctx, opts) -> dict:
    """Warteliste abarbeiten: neue Titel aufnehmen (nichts entfernen), verschobene umbenennen."""
    pend = _take_pending(ctx)
    m = load_manifest(ctx)
    if not m["files"]:
        return {"message": "Noch kein Index – nichts nachzuführen."}
    moved = apply_moves(m, pend["moves"])
    todo, _drop = plan(m, [p for p in pend["add"] if os.path.isfile(p)], prune=False)
    if not todo:
        save_manifest(ctx, m)
        return {"message": f"Index nachgeführt: {moved} verschoben." if moved else "Index aktuell."}
    try:
        info = _build(ctx, m, todo, [])
    except BaseException:
        _pending(ctx, add=[p for _nr, p in todo if not (m["files"].get(p) or {}).get("keys")])   # beim nächsten Mal
        raise
    msg = f"Index nachgeführt: {len(todo) - info['failed']} neu" + (f", {moved} verschoben" if moved else "") + "."
    ctx.log(msg)
    return {"message": msg}


def mix_files(folder: str, subfolders=False) -> list:
    """Audiodateien eines Ordners (sortiert), auf Wunsch mit Unterordnern."""
    out = []
    for dp, dns, fns in os.walk(folder):
        dns[:] = sorted(d for d in dns if not d.startswith(".")) if subfolders else []
        out += [os.path.join(dp, f) for f in sorted(fns) if f.lower().endswith(AUDIO_EXT) and not f.startswith(".")]
    return out


def run_analyse_folder(ctx, opts) -> dict:
    """#396: je Mix-Datei einen Hintergrund-Auftrag „Mix analysieren“ anlegen."""
    folder = str(opts.get("folder") or "").strip().strip('"')
    if not folder or not os.path.isdir(folder):
        raise ValueError("Bitte einen Ordner wählen.")
    if not load_manifest(ctx)["files"]:
        raise ValueError("Noch kein Index – zuerst „Bibliothek indexieren …“ (Plugins › Mix analysieren › Mehr …).")
    files = mix_files(folder, bool(opts.get("subfolders")))
    done = set()
    if opts.get("skip_done", True):
        try:
            import mixresult
            import paths
            done = {os.path.normcase(os.path.abspath(x["mix"])) for x in mixresult.listing(paths.sub("Mixe")) if x.get("mix")}
        except Exception as ex:  # noqa: BLE001
            ctx.log(f"Frühere Analysen nicht lesbar: {ex}")
    todo = [p for p in files if os.path.normcase(os.path.abspath(p)) not in done]
    if not todo:
        return {"message": f"Keine neuen Mix-Dateien in „{os.path.basename(folder)}“ ({len(files)} gefunden, alle schon analysiert)."
                if files else f"Keine Audiodateien in „{os.path.basename(folder)}“."}
    n = 0
    for p in todo:
        if ctx.queue_job("analyse", {"mix": p, "pitch": bool(opts.get("pitch", True)), "background": True},
                         os.path.basename(p), dedupe=False) is not None:
            n += 1
    skipped = len(files) - len(todo)
    return {"message": f"{n} Mix-Datei(en) in die Warteschlange gestellt" + (f", {skipped} schon analysiert" if skipped else "")
            + " – Fortschritt in der Fussleiste."}


def run_analyse(ctx, opts) -> dict:
    mix = str(opts.get("mix") or "").strip().strip('"')
    if not mix or not os.path.isfile(mix):
        raise ValueError("Bitte eine Mix-Datei wählen.")
    m = load_manifest(ctx)
    if not m["files"]:
        raise ValueError("Noch kein Index – zuerst „Bibliothek indexieren …“ (Plugins › Mix analysieren › Mehr …).")
    apply_moves(m, _pending(ctx)["moves"])              # verschoben, aber noch nicht nachgeführt: neuer Pfad
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
    cmp = compare(opts.get("tracklist") or "", rows) if str(opts.get("tracklist") or "").strip() else None
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
        json.dump({"plugin_version": plugin_version(), "mix": mix, "result": got, "rows": rows, "compare": cmp}, fh, ensure_ascii=False, indent=1)
    ctx.log(text)
    sure = sum(1 for r in rows if r["conf"] >= 0.6)
    msg = f"{sure} Titel erkannt ({len(rows) - sure} unsicher) in {fmt_time(got.get('duration', 0))} Mix, Analyse {got.get('secs', 0)} s."
    if cmp and cmp["expected"]:
        msg += f" Tracklist: {len(cmp['hit'])} von {cmp['expected']} erkannt ({round(100 * len(cmp['hit']) / cmp['expected'])} %)."
    keep = ("start", "end", "track_start", "path", "artist", "title", "tempo", "keylock", "conf", "also")
    return {"message": msg, "mix_result": {
        "mix": mix, "duration": got.get("duration", 0), "rows": [{k: r[k] for k in keep if k in r} for r in rows],
        "compare": cmp, "report": base + ".txt", "index": idx_info, "version": plugin_version(),
        "tracklist": str(opts.get("tracklist") or "")}}


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
        raise ValueError("Zu wenig indexierte Titel (mindestens 2 mit über 100 s) – zuerst „Bibliothek indexieren …“.")
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
    lines = [f"Mix analysieren – Selbsttest ({time.strftime('%Y-%m-%d %H:%M')}, Plugin {plugin_version()})", "",
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
        json.dump({"plugin_version": plugin_version(), "expected": exp, "result": got}, fh, ensure_ascii=False, indent=1)
    ctx.output(path)
    ctx.log(text)
    return {"message": f"Selbsttest: {ok} von {total} Titeln erkannt ({round(100 * ok / max(1, total))} %), {len(wrong)} falsch. "
                       f"Bericht: {os.path.basename(path)}"}


def run(action, ctx, files, opts):
    if action == "selftest":
        return run_selftest(ctx, opts)
    if action in ("index", "index_bg"):
        return run_index(ctx, opts)
    if action == "index_add":
        return run_index_add(ctx, opts)
    if action == "analyse":
        return run_analyse(ctx, opts)
    if action == "analyse_folder":
        return run_analyse_folder(ctx, opts)
    if action == "results":
        return {"message": "", "mix_list": True}
    if action == "settings":
        st = {k: bool(opts.get(k, True)) for k in ("auto_add", "auto_start")}
        with open(_settings_path(ctx), "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        return {"message": "Einstellungen gespeichert."}
    raise ValueError(f"Unbekannte Aktion: {action}")


def status(ctx):
    m = load_manifest(ctx)
    st = m.get("stats") or {}
    if not m["files"]:
        return "Noch kein Index – „Mehr …“ › „Bibliothek indexieren …“."
    return f"Index: {len(m['files'])} Titel, {st.get('bytes', 0) / 1e6:.1f} MB (Stand {st.get('at', '?')})."
