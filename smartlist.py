"""MarKusSXCH TagStudio – Smartlists (#272): Playlists, die sich über Regeln auf Tag-Feldern selbst füllen.

Eine Smartlist ist eine Playlist mit ``kind = "smart"`` und dem Feld ``rules``:

    {"base":  {"kind": "library" | "tagger" | "playlist", "pid": "pl_…"},   # Datenbasis (S1)
     "match": "all" | "any",                                               # alle bzw. eine Regel erfüllt (S2)
     "rules": [{"f": "bpm", "op": "between", "a": 124, "b": 128}, …],
     "sort":  "bpm", "desc": false, "limit": 50}                          # Sortierung, Höchstzahl (S5)

Aktualisiert wird beim Öffnen und auf Knopfdruck (S3), nie im Hintergrund; die Einträge werden dabei neu gesetzt
und die M3U8 im Playlist-Ordner neu geschrieben (S4). „Einfrieren“ macht eine normale Playlist daraus.
Entscheide S1–S5 vom 25.10.2026 (docs/KONZEPT-PLAYLISTS.md, Abschnitt 17). Nur Standardbibliothek.
"""
from __future__ import annotations

import datetime
import random
import re

import features
import keys
import moods
import ratings
import tsmeta
from id3tags import MV

# Feld → (Bezeichnung, Art)
FIELDS = {
    "text": ("Text (Künstler, Titel, Album, Kommentar)", "text"),
    "artist": ("Künstler", "text"),
    "title": ("Titel", "text"),
    "album": ("Album", "text"),
    "genre": ("Genre", "text"),
    "label": ("Label", "text"),
    "comment": ("Kommentar", "text"),
    "year": ("Jahr", "num"),
    "bpm": ("BPM", "num"),
    "key": ("Tonart", "key"),
    "rating": ("Bewertung", "num"),
    "like": ("Like", "bool"),
    "mood": ("Stimmung", "list"),
    "energy": ("Energie", "num"),
    "added": ("Aufgenommen", "date"),
    "edited": ("Bearbeitet", "date"),
    "origin": ("Herkunft", "origin"),
}
# Art → erlaubte Vergleiche
OPS = {
    "text": ("contains", "not_contains", "is", "empty", "not_empty"),
    "num": ("between", "gte", "lte", "eq", "empty", "not_empty"),
    "key": ("is", "fits", "empty", "not_empty"),
    "bool": ("yes", "no"),
    "list": ("contains", "not_contains", "empty", "not_empty"),
    "date": ("days", "after", "before", "empty", "not_empty"),
    "origin": ("has", "not_has"),
}
OP_LABELS = {"contains": "enthält", "not_contains": "enthält nicht", "is": "ist", "empty": "ist leer",
             "not_empty": "ist nicht leer", "between": "zwischen", "gte": "mindestens", "lte": "höchstens",
             "eq": "gleich", "fits": "passt zu", "yes": "ja", "no": "nein", "days": "in den letzten … Tagen",
             "after": "ab", "before": "vor", "has": "hat Felder von", "not_has": "hat keine Felder von"}
BASES = ("library", "tagger", "playlist")
SORTS = ("", "random", "artist", "title", "album", "genre", "year", "bpm", "key", "rating", "energy", "added",
         "edited", "path")
LIMIT_MAX = 10000
RULES_MAX = 30
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SPLIT = re.compile(r"\s*(?:\x00|;|/|,)\s*")


def default_rules() -> dict:
    """Vorgabe für eine neue Smartlist: Bibliothek, alle Regeln, 124–128 BPM, nach BPM sortiert."""
    return {"base": {"kind": "library", "pid": ""}, "match": "all",
            "rules": [{"f": "bpm", "op": "between", "a": 124, "b": 128}], "sort": "bpm", "desc": False, "limit": 0}


def _num(v):
    try:
        x = float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None
    return x if x == x else None                     # NaN aussortieren


def clean(rules) -> dict:
    """Regeln prüfen und vereinheitlichen. Ungültige Einzelregeln fallen weg; ValueError bei unbrauchbarem Aufbau."""
    if not isinstance(rules, dict):
        raise ValueError("Ungültige Regeln.")
    base = rules.get("base") if isinstance(rules.get("base"), dict) else {}
    kind = base.get("kind") if base.get("kind") in BASES else "library"
    pid = str(base.get("pid") or "") if kind == "playlist" else ""
    if kind == "playlist" and not pid:
        raise ValueError("Bitte die Playlist wählen, aus der die Smartlist ihre Titel nimmt.")
    out = {"base": {"kind": kind, "pid": pid}, "match": "any" if rules.get("match") == "any" else "all", "rules": []}
    for r in (rules.get("rules") or [])[:RULES_MAX]:
        if not isinstance(r, dict) or r.get("f") not in FIELDS:
            continue
        typ = FIELDS[r["f"]][1]
        op = r.get("op") if r.get("op") in OPS[typ] else OPS[typ][0]
        x = {"f": r["f"], "op": op}
        a, b = r.get("a"), r.get("b")
        if op in ("empty", "not_empty", "yes", "no"):
            pass
        elif typ in ("text", "list", "origin"):
            s = " ".join(str(a or "").split())
            if not s:
                continue
            x["a"] = s[:200]
        elif typ == "num":
            na, nb = _num(a), _num(b)
            if op == "between":
                if na is None and nb is None:
                    continue
                if na is not None and nb is not None and na > nb:
                    na, nb = nb, na
                x["a"], x["b"] = na, nb
            else:
                if na is None:
                    continue
                x["a"] = na
        elif typ == "key":
            codes = [keys.parse_key(p) for p in (a if isinstance(a, list) else _SPLIT.split(str(a or "")))]
            codes = list(dict.fromkeys(c for c in codes if c))
            if not codes:
                continue
            x["a"] = codes if op == "is" else codes[:1]
        elif typ == "date":
            if op == "days":
                n = _num(a)
                if n is None or n <= 0:
                    continue
                x["a"] = int(n)
            else:
                s = str(a or "").strip()
                if not _DATE.match(s):
                    continue
                try:
                    datetime.date.fromisoformat(s)
                except ValueError:
                    continue
                x["a"] = s
        out["rules"].append(x)
    out["sort"] = rules.get("sort") if rules.get("sort") in SORTS else ""
    out["desc"] = bool(rules.get("desc"))
    lim = _num(rules.get("limit"))
    out["limit"] = max(0, min(LIMIT_MAX, int(lim))) if lim is not None else 0
    return out


# ---------------------------------------------------------------- Werte aus einer Datei
def _text(f, key) -> str:
    it = f.get(key) if hasattr(f, "get") else None
    return it.text.strip() if it is not None and getattr(it, "kind", "") not in ("picture", "raw") else ""


def _comment(f) -> str:
    out = []
    for k in getattr(f, "items", {}):
        if k.split(":")[0].split("#")[0] == "COMM":
            t = _text(f, k)
            if t:
                out.append(t)
    return " ".join(out)


def _ts(text) -> float | None:
    d = tsmeta.parse(text) if text else None
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.astimezone()
    return d.timestamp()


def values(f, origin_of=None) -> dict:
    """Alle Regel-Felder einer geladenen MP3File. origin_of(key) → Herkunfts-ID oder None (für „Herkunft“)."""
    v = {"artist": _text(f, "TPE1").replace(MV, ", "), "title": _text(f, "TIT2"), "album": _text(f, "TALB"),
         "genre": _text(f, "TCON").replace(MV, "; "), "label": _text(f, "TPUB"), "comment": _comment(f)}
    y = re.match(r"\s*(\d{4})", _text(f, "TDRC") or _text(f, "TYER"))
    v["year"] = float(y.group(1)) if y else None
    v["bpm"] = _num(_text(f, "TBPM")) or None
    v["key"] = keys.parse_key(_text(f, "TKEY"))
    try:
        v["rating"] = float(ratings.get_rating(f))
    except Exception:  # noqa: BLE001
        v["rating"] = 0.0
    try:
        v["like"] = bool(ratings.get_like(f))
    except Exception:  # noqa: BLE001
        v["like"] = False
    try:
        v["mood"] = moods.values(f)
    except Exception:  # noqa: BLE001
        v["mood"] = []
    e = features.number(features.get(f, "ENERGY"))
    v["energy"] = float(e) if e is not None else None
    v["added"] = _ts(_text(f, tsmeta.ADDED))
    v["edited"] = _ts(_text(f, tsmeta.EDITED))
    v["origin"] = sorted({s for s in (origin_of(k) for k in getattr(f, "items", {})) if s}) if origin_of else []
    v["path"] = getattr(f, "path", "")
    return v


# ---------------------------------------------------------------- Prüfen
def _fold(s) -> str:
    return str(s or "").casefold()


def _day_start(s: str) -> float:
    d = datetime.date.fromisoformat(s)
    return datetime.datetime(d.year, d.month, d.day).astimezone().timestamp()


def test(rule: dict, v: dict, now: float | None = None) -> bool:
    f, op, a = rule["f"], rule["op"], rule.get("a")
    typ = FIELDS[f][1]
    if f == "text":
        val = " ".join(v.get(k) or "" for k in ("artist", "title", "album", "comment", "genre"))
    else:
        val = v.get(f)
    if op == "empty":
        return val in (None, "", [], 0.0) if f == "rating" else val in (None, "", [])
    if op == "not_empty":
        return not test({**rule, "op": "empty"}, v, now)
    if typ == "text":
        s, q = _fold(val), _fold(a)
        if op == "contains":
            return q in s
        if op == "not_contains":
            return q not in s
        parts = [p for p in _SPLIT.split(s) if p] if f == "genre" else [s]
        return q in parts or s == q                    # „ist“: ganzer Wert oder ein Teil eines Mehrfach-Genres
    if typ == "num":
        if val is None:
            return False
        if op == "between":
            lo, hi = rule.get("a"), rule.get("b")
            return (lo is None or val >= lo) and (hi is None or val <= hi)
        if op == "gte":
            return val >= a
        if op == "lte":
            return val <= a
        return abs(val - a) < 1e-6
    if typ == "key":
        if not val:
            return False
        if op == "fits":
            return val in keys.compatible(a[0])
        return val in a
    if typ == "bool":
        return bool(val) == (op == "yes")
    if typ == "list":
        q = _fold(a)
        hit = any(_fold(x) == q for x in val or [])
        return hit if op == "contains" else not hit
    if typ == "date":
        if val is None:
            return False
        if op == "days":
            return val >= (now if now is not None else datetime.datetime.now().timestamp()) - a * 86400
        if op == "after":
            return val >= _day_start(a)
        return val < _day_start(a)
    if typ == "origin":
        hit = _fold(a) in {_fold(x) for x in val or []}
        return hit if op == "has" else not hit
    return False


def matches(rules: dict, v: dict, now: float | None = None) -> bool:
    rs = rules.get("rules") or []
    if not rs:
        return True                                    # ohne Regeln: alle Titel der Datenbasis
    res = (test(r, v, now) for r in rs)
    return any(res) if rules.get("match") == "any" else all(res)


def _sort_key(field):
    def k(v):
        x = v.get(field)
        if field == "key":
            return (x is None, keys.sort_value(x))
        if isinstance(x, str):
            return (not x, x.casefold())
        return (x is None, x if x is not None else 0)
    return k


def apply(entries, rules: dict, now: float | None = None, rng=None) -> list[dict]:
    """entries: Werte je Titel (aus values()) → die passenden in der gewünschten Reihenfolge, höchstens limit."""
    hits = [v for v in entries if matches(rules, v, now)]
    sort = rules.get("sort") or ""
    if sort == "random":
        (rng or random).shuffle(hits)
    elif sort:
        none = [v for v in hits if v.get(sort) in (None, "")]
        some = [v for v in hits if v.get(sort) not in (None, "")]
        some.sort(key=_sort_key(sort), reverse=bool(rules.get("desc")))
        hits = some + none                             # fehlende Werte immer ans Ende
    lim = int(rules.get("limit") or 0)
    return hits[:lim] if lim else hits
