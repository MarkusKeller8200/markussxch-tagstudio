"""Ergebnisse von „Mix analysieren“ (#261, #387): erkannte Titel eines Mixes speichern, bearbeiten und ausgeben.

Das Plugin `mixscan` liefert die erkannten Abschnitte; hier werden sie als Ergebnis im Programmdaten-Ordner „Mixe“
abgelegt (eine JSON-Datei je Analyse) und als Tracklist-Text, CUE-Datei oder Playlist-Einträge ausgegeben. Reine
Logik ohne Oberfläche – die Sitzung (`session_mixes.py`) ruft sie auf.
"""
import json
import os
import re
import secrets
import time

FORMAT = 1
FOLDER = "Mixe"          # Playlist-Ordner für gespeicherte Mixe
SURE = 0.6               # ab hier „sicher“
GAP = 60.0               # Lücken ab einer Minute erscheinen als „ID – ID“
_ID = re.compile(r"^mx_[0-9a-f]{12}$")
_ROW_KEYS = ("start", "end", "track_start", "path", "artist", "title", "tempo", "keylock", "conf", "also", "at", "drop")


def fmt_time(sec) -> str:
    sec = max(0, int(round(float(sec or 0))))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def parse_time(text) -> float | None:
    """„12:30“, „1:02:10“ oder Sekunden → Sekunden; None, wenn unlesbar."""
    s = str(text or "").strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", s)
    if not m:
        return None
    return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def mark(row: dict) -> float:
    """Zeit in der Tracklist: Mitte des Übergangs zwischen Titelanfang (Einblenden) und „erkannt ab“ (Titel dominiert).
    Messung 7 (#261): Tracklisten nennen meist einen Zeitpunkt im Übergang – die Mitte lag im Median 17 s daneben,
    der Titelanfang 48 s. Von Hand geänderte Zeit („at“) gilt immer."""
    if row.get("at") is not None:
        return float(row["at"])
    ts = row.get("track_start")
    if ts is None:
        return float(row.get("start") or 0)
    return max(0.0, (float(ts) + float(row.get("start") or 0)) / 2)


def clean_row(r) -> dict | None:
    if not isinstance(r, dict):
        return None
    out = {}
    try:
        out["start"] = max(0.0, float(r.get("start") or 0))
        out["end"] = max(out["start"], float(r.get("end") or out["start"]))
        out["tempo"] = round(float(r.get("tempo") or 0), 1)
        out["conf"] = min(1.0, max(0.0, float(r.get("conf") or 0)))
        if r.get("track_start") is not None:
            out["track_start"] = float(r["track_start"])
        if r.get("at") is not None:
            out["at"] = max(0.0, float(r["at"]))
    except (TypeError, ValueError):
        return None
    out["path"] = str(r.get("path") or "")
    out["artist"] = str(r.get("artist") or "")[:300]
    out["title"] = str(r.get("title") or "")[:300]
    out["keylock"] = bool(r.get("keylock", True))
    if isinstance(r.get("also"), list):
        out["also"] = [str(x)[:300] for x in r["also"][:8]]
    if r.get("drop"):
        out["drop"] = True
    return out


def new(mix: str, duration: float, rows: list, *, compare=None, report="", index="", plugin="", version="") -> dict:
    """Neues Ergebnis (noch nicht gespeichert)."""
    rs = sorted((x for x in (clean_row(r) for r in rows or []) if x), key=lambda x: x["start"])
    res = {"format": FORMAT, "id": "mx_" + secrets.token_hex(6), "mix": str(mix),
           "name": os.path.splitext(os.path.basename(str(mix)))[0][:200],
           "created": time.strftime("%Y-%m-%d %H:%M"), "duration": float(duration or 0), "rows": rs,
           "report": str(report or ""), "index": str(index or ""), "plugin": str(plugin or ""), "version": str(version or "")}
    if isinstance(compare, dict):
        res["compare"] = {k: [str(x) for x in compare.get(k) or []][:500] for k in ("hit", "miss", "other", "unsure")}
        res["compare"]["expected"] = int(compare.get("expected") or 0)
    return res


def kept(res) -> list:
    """Nicht verworfene Zeilen mit Nummer, nach Tracklist-Zeit."""
    rows = [(n, r) for n, r in enumerate(res.get("rows") or []) if not r.get("drop")]
    return sorted(rows, key=lambda x: mark(x[1]))


def with_gaps(res) -> list:
    """Zeilen für die Anzeige: [{"n", "row"} | {"gap": True, "start", "end"}] – Lücken ≥ GAP zwischen den Titeln."""
    out, pos = [], 0.0
    for n, r in kept(res):
        if r["start"] - pos >= GAP:
            out.append({"gap": True, "start": pos, "end": r["start"]})
        out.append({"n": n, "row": r})
        pos = max(pos, r["end"])
    if res.get("duration") and res["duration"] - pos >= GAP:
        out.append({"gap": True, "start": pos, "end": res["duration"]})
    return out


def name_of(r) -> str:
    return f"{r['artist']} - {r['title']}" if r.get("artist") else (r.get("title") or "?")


def to_text(res, gaps=True) -> str:
    """Tracklist wie bei 1001Tracklists: „[12:30] Künstler - Titel“, Lücken als „ID - ID“."""
    lines = []
    for e in with_gaps(res):
        if e.get("gap"):
            if gaps:
                lines.append(f"[{fmt_time(e['start'])}] ID - ID")
        else:
            lines.append(f"[{fmt_time(mark(e['row']))}] {name_of(e['row'])}")
    return "\n".join(lines) + ("\n" if lines else "")


def _cue_str(s) -> str:
    return '"' + str(s).replace('"', "'").replace("\n", " ") + '"'


def to_cue(res, dest="") -> str:
    """CUE-Datei für den Mix (Player, Aufnahme-Software, DJ-Programme). Liegt die CUE nicht neben dem Mix, steht der
    volle Pfad unter FILE."""
    mix = res.get("mix") or ""
    same = dest and os.path.normcase(os.path.dirname(os.path.abspath(dest))) == os.path.normcase(os.path.dirname(os.path.abspath(mix)))
    ftype = "WAVE" if os.path.splitext(mix)[1].lower() in (".wav", ".aif", ".aiff", ".flac") else "MP3"
    L = ["REM COMMENT " + _cue_str("TagStudio – Mix analysieren"), "TITLE " + _cue_str(res.get("name") or ""),
         f"FILE {_cue_str(os.path.basename(mix) if same or not dest else mix)} {ftype}"]
    k = 0
    for e in with_gaps(res):
        k += 1
        t = e["start"] if e.get("gap") else mark(e["row"])
        if k == 1:
            t = 0.0                                  # CUE: der erste Titel beginnt bei 0
        frames = int(round(t * 75))
        idx = f"{frames // 75 // 60:02d}:{frames // 75 % 60:02d}:{frames % 75:02d}"
        L.append(f"  TRACK {k:02d} AUDIO")
        if e.get("gap"):
            L += ["    TITLE " + _cue_str("ID"), "    PERFORMER " + _cue_str("ID")]
        else:
            L += ["    TITLE " + _cue_str(e["row"]["title"]), "    PERFORMER " + _cue_str(e["row"]["artist"])]
        L.append(f"    INDEX 01 {idx}")
    return "\n".join(L) + "\n"


def note_of(r) -> str:
    """Notiz je Playlist-Eintrag – sprachneutral, weil sie als Daten gespeichert wird: „12:30 · +2.0 % · 94 %“."""
    return f"{fmt_time(mark(r))} · {r['tempo']:+.1f} % · {round(r['conf'] * 100)} %"


def to_items(res) -> list:
    """Playlist-Einträge in der Reihenfolge des Mixes – Startzeit, Tempo und Sicherheit als Notiz."""
    out = []
    for _n, r in kept(res):
        it = {"artist": r["artist"], "title": r["title"], "note": note_of(r)}
        if r["path"]:
            it["path"] = r["path"]
            try:
                it["size"] = os.path.getsize(r["path"])
            except OSError:
                pass
        else:
            it["ref"] = {"artist": r["artist"], "title": r["title"], "source": "mixscan"}
        out.append(it)
    return out


def missing_text(res) -> str:
    """Titel der bekannten Tracklist, die nicht im Index sind (zum Merken als Ideen)."""
    return "\n".join((res.get("compare") or {}).get("miss") or [])


# =========================================================================== Ablage
def _path(d, rid) -> str:
    if not _ID.match(str(rid or "")):
        raise ValueError("Unbekanntes Mix-Ergebnis.")
    return os.path.join(d, rid + ".json")


def save(d, res) -> dict:
    os.makedirs(d, exist_ok=True)
    p = _path(d, res["id"])
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return res


def load(d, rid) -> dict:
    try:
        with open(_path(d, rid), encoding="utf-8") as fh:
            res = json.load(fh)
    except (OSError, ValueError) as ex:
        raise ValueError("Dieses Mix-Ergebnis gibt es nicht mehr.") from ex
    if not isinstance(res, dict) or res.get("id") != rid:
        raise ValueError("Dieses Mix-Ergebnis ist beschädigt.")
    res["rows"] = [x for x in (clean_row(r) for r in res.get("rows") or []) if x]
    return res


def listing(d) -> list:
    out = []
    try:
        names = sorted(os.listdir(d), reverse=True)
    except OSError:
        return out
    for fn in names:
        if not fn.endswith(".json") or not _ID.match(fn[:-5]):
            continue
        try:
            res = load(d, fn[:-5])
        except ValueError:
            continue
        rows = [r for _n, r in kept(res)]
        out.append({"id": res["id"], "name": res.get("name", ""), "mix": res.get("mix", ""), "created": res.get("created", ""),
                    "duration": res.get("duration", 0), "count": len(rows),
                    "sure": sum(1 for r in rows if r["conf"] >= SURE), "exists": os.path.isfile(res.get("mix", ""))})
    out.sort(key=lambda x: x["created"], reverse=True)
    return out


def remove(d, rid):
    p = _path(d, rid)
    if os.path.isfile(p):
        os.remove(p)
