"""Liedtexte für den Player (#215): synchronisiert aus SYLT oder der .lrc-Datei neben dem MP3, sonst normaler Text
(USLT). Nur lesen – geschrieben werden Liedtexte ausschliesslich über das Plugin „Liedtexte“ (#183).
Nur Standardbibliothek.
"""
from __future__ import annotations

import os
import re

from id3frames import _int, _term, _txt

LRC_MAX = 512 * 1024                      # .lrc-Dateien sind klein – grössere nicht lesen
_STAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def parse_lrc(text: str) -> list[tuple[int, str]]:
    """LRC-Text → [(Millisekunden, Zeile)], nach Zeit sortiert (gleiche Regeln wie im Plugin „Liedtexte“)."""
    out = []
    for line in str(text or "").splitlines():
        stamps, pos = [], 0
        while True:
            m = _STAMP.match(line, pos)
            if not m:
                break
            mm, ss, frac = int(m.group(1)), int(m.group(2)), m.group(3) or "0"
            ms = int(frac.ljust(3, "0")[:3]) if len(frac) != 2 else int(frac) * 10
            stamps.append((mm * 60 + ss) * 1000 + ms)
            pos = m.end()
        if stamps:
            txt = line[pos:].strip()
            out.extend((t, txt) for t in stamps)
    out.sort(key=lambda x: x[0])
    return out


def parse_sylt(payload: bytes) -> tuple[list[tuple[int, str]], str]:
    """SYLT-Rumpf → ([(ms, Zeile)], Sprache). Nur Zeitformat 2 (Millisekunden); MPEG-Frames (1) → leere Liste."""
    if not payload or len(payload) < 7:
        return [], ""
    enc, lang, fmt = payload[0], payload[1:4].decode("latin-1", "replace"), payload[4]
    if fmt != 2:
        return [], lang
    _desc, rest = _term(payload[6:], enc)
    lines = []
    while rest:
        t, rest = _term(rest, enc)
        if len(rest) < 4:
            break
        stamp, rest = _int(rest[:4]), rest[4:]
        lines.append((stamp, _txt(t, enc).replace("\r", "").strip("\n")))
    lines.sort(key=lambda x: x[0])
    return lines, lang


def _first(f, prefix: str):
    return next((f.get(k) for k in f.keys() if k == prefix or k.startswith(prefix + ":") or k.startswith(prefix + "#")), None)


def _read_lrc(path: str) -> str:
    lrc = os.path.splitext(path)[0] + ".lrc"
    try:
        if not os.path.isfile(lrc) or os.path.getsize(lrc) > LRC_MAX:
            return ""
        with open(lrc, "rb") as fh:
            raw = fh.read()
    except OSError:
        return ""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""


def for_file(f, path: str | None = None) -> dict:
    """→ {"source": "SYLT" | ".lrc" | "USLT" | "", "synced": [[ms, Zeile], …], "plain": Text, "lang": …}"""
    out = {"source": "", "synced": [], "plain": "", "lang": ""}
    it = _first(f, "SYLT")
    if it is not None and getattr(it, "payload", None):
        lines, lang = parse_sylt(it.payload)
        if lines:
            out.update(source="SYLT", synced=[[ms, t] for ms, t in lines], lang=lang)
    if not out["synced"] and path:
        lines = parse_lrc(_read_lrc(path))
        if lines:
            out.update(source=".lrc", synced=[[ms, t] for ms, t in lines])
    u = _first(f, "USLT")
    if u is not None and (u.text or "").strip():
        out["plain"] = u.text.strip()
        out["lang"] = out["lang"] or (u.lang or "")
        if not out["source"]:
            out["source"] = "USLT"
    elif out["synced"]:
        out["plain"] = "\n".join(t for _ms, t in out["synced"]).strip()
    return out
