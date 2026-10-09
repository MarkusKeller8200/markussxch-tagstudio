"""MarKusSXCH TagStudio – erzeugte Stems einem Original zuordnen (Tagger: aufklappbare Spuren, #31).

Das Stems-Plugin legt die Spuren in einen Ordner „<Titel> – Stems“ neben dem Titel (oder in einem festen Ordner)
mit Dateinamen „<Titel> (Vocals).flac“ usw. Dieses Modul findet diese Spuren zu einer Originaldatei und erkennt
umgekehrt, ob eine Datei selbst eine solche Spur ist. Nur Standardbibliothek.
"""
from __future__ import annotations

import os
import re

SUFFIX = " – Stems"
EXTS = (".mp3", ".flac", ".wav")
ORDER = ["Vocals", "Instrumental", "Drums", "Bass", "Other", "Guitar", "Piano"]


def _order(name: str) -> tuple:
    return (ORDER.index(name) if name in ORDER else len(ORDER), name.lower())


def folders_for(path: str, roots=()) -> list[str]:
    """Mögliche Stems-Ordner einer Originaldatei."""
    base = os.path.splitext(os.path.basename(path))[0]
    out = [os.path.join(os.path.dirname(path), base + SUFFIX)]
    out += [os.path.join(r, base + SUFFIX) for r in roots if r]
    seen, res = set(), []
    for d in out:
        k = os.path.normcase(os.path.abspath(d))
        if k not in seen:
            seen.add(k)
            res.append(d)
    return res


def find(path: str, roots=()) -> list[dict]:
    """Spuren zu einer Originaldatei → [{"name", "path", "ext", "size"}] (Vocals, Drums, Bass, Other …)."""
    base = os.path.splitext(os.path.basename(path))[0]
    rx = re.compile(r"^" + re.escape(base) + r" \(([^()]+)\)(\.[A-Za-z0-9]+)$")
    out, seen = [], set()
    for d in folders_for(path, roots):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            m = rx.match(n)
            if not m or m.group(2).lower() not in EXTS:
                continue
            p = os.path.join(d, n)
            if not os.path.isfile(p):
                continue
            key = (m.group(1).lower(), m.group(2).lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({"name": m.group(1), "path": p, "ext": m.group(2)[1:].upper(), "size": os.path.getsize(p)})
    out.sort(key=lambda s: (_order(s["name"]), s["ext"]))
    return out


def is_stem(path: str) -> bool:
    """Liegt die Datei in einem „… – Stems“-Ordner und heisst „<Titel> (Spur).ext“?"""
    d = os.path.basename(os.path.dirname(path))
    if not d.endswith(SUFFIX):
        return False
    base = d[:-len(SUFFIX)]
    return bool(re.match(r"^" + re.escape(base) + r" \([^()]+\)\.[A-Za-z0-9]+$", os.path.basename(path)))
