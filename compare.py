"""
compare.py – Ordner einlesen, Dateien zuordnen, Unterschiede ermitteln, Felder kopieren.
Unabhängig von der Oberfläche (testbar).
"""
from __future__ import annotations

import fnmatch
import re
import os

from id3tags import MP3File, sort_key, MV

PAIR_MODES = {
    "filename": "Dateiname",
    "track": "Disc + Spurnummer",
    "title": "Titel",
    "order": "Reihenfolge (alphabetisch)",
}

# Felder, die sich zwischen Dateien fast immer unterscheiden ("unwichtig", wie "Triv." in Beyond Compare)
DEFAULT_TRIVIAL = [
    "TLEN", "TSSE", "TENC", "TFLT", "TDTG", "TDEN", "COMM:iTunNORM", "COMM:iTunSMPB",
    "COMM:iTunPGAP", "COMM:ID3v1 Comment", "PRIV:*", "UFID:*", "TXXX:Acoustid*",
    "TXXX:1T_*", "TXXX:AnalysisDate", "TXXX:MusicBrainz*", "TXXX:replaygain*",
    # DJ-/Analyse-Daten (gehören zum einzelnen Track, unterscheiden sich praktisch immer)
    "GEOB:*", "ETCO", "PCNT", "TXXX:beaTunes*", "TXXX:*Algorithm", "TXXX:Segments", "TXXX:Similarities",
    "TXXX:fBPM*", "TXXX:time_reference", "TXXX:umid", "TXXX:originator_reference",
]


class Rules:
    def __init__(self, trivial=None):
        self.trivial = list(trivial if trivial is not None else DEFAULT_TRIVIAL)

    def is_trivial(self, key: str) -> bool:
        k = key.split("#")[0]
        return any(fnmatch.fnmatchcase(k.lower(), p.lower()) for p in self.trivial)


class Cancelled(Exception):
    """Einlesen wurde vom Benutzer abgebrochen."""


def scan(path: str, recursive: bool = False, cancel=None, on_found=None) -> list[str]:
    """Liefert alle MP3-Dateien. cancel: threading.Event (optional), on_found(n): Zwischenstand."""
    if os.path.isfile(path):
        return [path]
    result = []

    def check():
        if cancel is not None and cancel.is_set():
            raise Cancelled()

    def is_mp3(name):
        return name.lower().endswith(".mp3") and not name.startswith(".")

    if recursive:
        for root, dirs, files in os.walk(path):
            check()
            dirs[:] = sorted((d for d in dirs if not d.startswith(".")), key=str.lower)
            result += [os.path.join(root, f) for f in sorted(files, key=str.lower) if is_mp3(f)]
            if on_found:
                on_found(len(result))
    else:
        with os.scandir(path) as it:
            for n, entry in enumerate(sorted(it, key=lambda e: e.name.lower())):
                if n % 200 == 0:
                    check()
                if is_mp3(entry.name) and entry.is_file():
                    result.append(entry.path)
                    if on_found and len(result) % 50 == 0:
                        on_found(len(result))
        if on_found:
            on_found(len(result))
    return result


def _num(s: str):
    s = (s or "").split("/")[0].strip()
    return int(s) if s.isdigit() else None


def _key(f: MP3File, mode: str, root: str):
    if mode == "filename":
        rel = os.path.relpath(f.path, root) if os.path.isdir(root) else os.path.basename(f.path)
        return rel.replace("\\", "/").lower()
    if mode == "track":
        t = _num(f.text("TRCK"))
        return None if t is None else (_num(f.text("TPOS")) or 1, t)
    if mode == "title":
        return f.text("TIT2").strip().lower() or None
    return None


def pair_files(left, right, mode, left_root="", right_root=""):
    """Liste von (links|None, rechts|None)."""
    if len(left) <= 1 and len(right) <= 1 and (os.path.isfile(left_root) or os.path.isfile(right_root)):
        if left or right:
            return [(left[0] if left else None, right[0] if right else None)]
        return []
    if mode == "order":
        n = max(len(left), len(right))
        return [(left[i] if i < len(left) else None, right[i] if i < len(right) else None) for i in range(n)]
    by_key: dict = {}
    for r in right:
        by_key.setdefault(_key(r, mode, right_root), []).append(r)
    used, pairs = set(), []
    for l in left:
        k = _key(l, mode, left_root)
        cand = by_key.get(k) if k is not None else None
        if cand:
            r = cand.pop(0)
            used.add(id(r))
            pairs.append((l, r))
        else:
            pairs.append((l, None))
    pairs += [(None, r) for r in right if id(r) not in used]
    return pairs


def all_keys(a: MP3File | None, b: MP3File | None):
    ks = set(a.items if a else ()) | set(b.items if b else ())
    return sorted(ks, key=sort_key)


def diff(a, b, rules: Rules | None = None):
    """(wichtige, unwichtige) unterschiedliche Schlüssel."""
    if a is None or b is None:
        return [], []
    rules = rules or Rules()
    imp, triv = [], []
    for k in all_keys(a, b):
        if a.get(k) != b.get(k):
            (triv if rules.is_trivial(k) else imp).append(k)
    return imp, triv


def copy_tags(src: MP3File, dst: MP3File, keys, delete_missing: bool = False) -> int:
    """Kopiert Felder src → dst. Fehlt ein Feld in src, wird es in dst nur mit delete_missing gelöscht."""
    n = 0
    for k in keys:
        s = src.get(k)
        if s is None and not delete_missing:
            continue
        if dst.get(k) != s:
            dst.set(k, s)
            n += 1
    return n


# =========================================================================== Mehrfachwerte-Fixer
MULTI_FIELDS = ["TPE1", "TPE2", "TPE3", "TPE4", "TCOM", "TEXT", "TOLY", "TOPE", "TCON",
                "TSOP", "TSO2", "TSOC", "TMCL", "TIPL"]
INPUT_SEPARATORS = [  # (Anzeige, Zeichenkette, Standard aktiv)
    ("Null (ID3v2.4-Mehrfachwert)", MV, True),
    ("Semikolon  ;", ";", True),
    ("Schrägstrich mit Leerzeichen  ' / '", " / ", True),
    ("Doppel-Backslash  \\\\  (Mp3tag)", "\\\\", True),
    ("Komma  ,", ",", False),
    ("Schrägstrich ohne Leerzeichen  /  (Achtung: AC/DC)", "/", False),
    ("Kaufmanns-Und  &", "&", False),
    ("' feat. ' / ' ft. '", " feat. ", False),
    ("' x '", " x ", False),
]


def split_multi(text: str, seps) -> list[str]:
    parts = [text]
    for sep in seps:
        nxt = []
        for p in parts:
            if sep == " feat. ":
                nxt += re.split(r"\s+(?:feat\.?|ft\.?|featuring)\s+", p, flags=re.I)
            else:
                nxt += p.split(sep)
        parts = nxt
    return [p.strip() for p in parts if p.strip()]


def fix_multi(text: str, seps, out_sep: str, dedupe: bool = True) -> str:
    """Zerlegt text an den Eingangs-Trennern und verbindet mit out_sep (MV = v2.4-Standard)."""
    parts = split_multi(text, seps)
    if dedupe:
        seen, uniq = set(), []
        for p in parts:
            if p.lower() not in seen:
                seen.add(p.lower())
                uniq.append(p)
        parts = uniq
    return out_sep.join(parts)


def plan_multi_fix(files, keys, seps, out_sep, dedupe=True, all_text=False, upgrade=False):
    """Liefert Liste (datei, key, vorher, nachher). out_sep == MV: v2.4-Standard."""
    plan = []
    for f in files:
        use_sep = out_sep
        if out_sep == MV and f.version != 4 and not upgrade:
            use_sep = "; "  # v2.3 ohne Umstellung: kein Null-Trenner möglich
        for k, it in list(f.items.items()):
            if it.kind not in ("text", "txxx"):
                continue
            if not (all_text or k in keys):
                continue
            new = fix_multi(it.text, seps, use_sep, dedupe)
            if new != it.text:
                plan.append((f, k, it.text, new))
    return plan
