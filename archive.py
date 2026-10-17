"""MarKusSXCH TagStudio – Aussortieren ins Archiv (#173).

Titel werden in den Archiv-Ordner (Standard: `02_Archiv`) **verschoben** – mit ihren Unterordnern relativ zum
Herkunftsordner (Bibliothek bzw. Eingang), damit die Ordnung erhalten bleibt. Ein Stems-Ordner neben dem Titel
(„<Titel> – Stems“) wandert mit. Jede Bewegung steht im Vermerk `_aussortiert.csv` im Archiv (Datum, Von, Nach,
Bereich); daraus lässt sich ein Titel zurückholen. Gelöscht wird nichts.
Nur Standardbibliothek.
"""
from __future__ import annotations

import csv
import os
import shutil
import time

LOG = "_aussortiert.csv"
HEAD = ["Datum", "Von", "Nach", "Bereich", "Zurückgeholt"]


def _rel(path: str, root: str | None) -> str:
    if root:
        try:
            rel = os.path.relpath(path, root)
            if not rel.startswith(".."):
                return rel
        except ValueError:          # anderes Laufwerk
            pass
    return os.path.basename(path)


def _inside(path: str, folder: str) -> bool:
    a, b = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
    return a.startswith(b.rstrip("\\/") + os.sep)


def _unique(path: str) -> str:
    stem, ext = os.path.splitext(path)
    k, cand = 1, path
    while os.path.exists(cand):
        k += 1
        cand = f"{stem} ({k}){ext}"
    return cand


def stems_dir(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    d = os.path.join(os.path.dirname(path), f"{base} – Stems")
    return d if os.path.isdir(d) else ""


def plan(paths, root, archive_dir) -> list[dict]:
    """→ [{"src", "dst", "stems_src", "stems_dst", "problem"}]"""
    out = []
    for p in paths:
        p = os.path.abspath(p)
        prob = ""
        if not os.path.isfile(p):
            prob = "Datei fehlt"
        elif _inside(p, archive_dir):
            prob = "liegt schon im Archiv"
        dst = _unique(os.path.join(archive_dir, _rel(p, root)))
        sd = stems_dir(p) if not prob else ""
        out.append({"src": p, "dst": dst, "stems_src": sd,
                    "stems_dst": _unique(os.path.join(os.path.dirname(dst), os.path.basename(sd))) if sd else "",
                    "problem": prob})
    return out


def move(pl, archive_dir, area="Tagger") -> dict:
    """Plan ausführen; Vermerk schreiben. → {"moved": [...], "errors": [...]}"""
    moved, errors = [], []
    rows = []
    for e in pl:
        if e["problem"]:
            continue
        try:
            os.makedirs(os.path.dirname(e["dst"]), exist_ok=True)
            shutil.move(e["src"], e["dst"])
            if e["stems_src"]:
                shutil.move(e["stems_src"], e["stems_dst"])
            moved.append(e)
            rows.append([time.strftime("%Y-%m-%d %H:%M:%S"), e["src"], e["dst"], area, ""])
            if e["stems_src"]:
                rows.append([time.strftime("%Y-%m-%d %H:%M:%S"), e["stems_src"], e["stems_dst"], area + " (Stems)", ""])
        except OSError as ex:
            errors.append(f"{os.path.basename(e['src'])}: {ex}")
    if rows:
        log = os.path.join(archive_dir, LOG)
        new = not os.path.exists(log)
        with open(log, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            if new:
                w.writerow(HEAD)
            w.writerows(rows)
    return {"moved": moved, "errors": errors}


def entries(archive_dir, limit=500) -> list[dict]:
    """Vermerke (neueste zuerst) mit Zustand: im Archiv vorhanden, zurückholbar."""
    log = os.path.join(archive_dir or "", LOG)
    if not archive_dir or not os.path.isfile(log):
        return []
    with open(log, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=";"))[1:]
    out = []
    for i, r in enumerate(rows):
        r = (r + [""] * 5)[:5]
        out.append({"id": i, "at": r[0], "src": r[1], "dst": r[2], "area": r[3], "restored": r[4],
                    "in_archive": os.path.exists(r[2]), "src_free": not os.path.exists(r[1])})
    return list(reversed(out))[:limit]


def restore(archive_dir, ids) -> dict:
    """Ausgewählte Vermerke zurückholen (nur wenn der alte Platz frei ist)."""
    log = os.path.join(archive_dir, LOG)
    with open(log, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    done, errors, moved = [], [], []
    for i in ids:
        if not isinstance(i, int) or not 0 <= i < len(rows) - 1:
            continue
        r = (rows[i + 1] + [""] * 5)[:5]
        if r[4]:
            continue
        if not os.path.exists(r[2]):
            errors.append(f"{os.path.basename(r[2])}: nicht mehr im Archiv")
            continue
        if os.path.exists(r[1]):
            errors.append(f"{os.path.basename(r[1])}: am alten Platz liegt schon etwas")
            continue
        try:
            os.makedirs(os.path.dirname(r[1]), exist_ok=True)
            shutil.move(r[2], r[1])
            r[4] = time.strftime("%Y-%m-%d %H:%M:%S")
            rows[i + 1] = r
            done.append(r[1])
            moved.append({"old": r[2], "new": r[1]})
        except OSError as ex:
            errors.append(f"{os.path.basename(r[2])}: {ex}")
    if done:
        tmp = log + ".tmp"
        with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            csv.writer(fh, delimiter=";").writerows(rows)
        os.replace(tmp, log)
    return {"restored": done, "errors": errors, "moved": moved}
