"""Ordner wechseln mit Inhalt (#313, docs/KONZEPT-ORDNER.md Abschnitt 5): verschieben oder kopieren.

Regeln (Entscheide O4/O6):
- **Nie überschreiben:** Liegt am Ziel schon eine Datei gleichen Namens, bleibt sie („Ziel behalten“, Standard – das
  Original bleibt dann am alten Ort) oder die neue kommt als „Name (2).ext“ daneben („beide behalten“).
- **Derselbe Datenträger:** Verschieben = Umbenennen (sofort, keine Kopie).
- **Über Datenträger:** kopieren in „<Ziel>.part“ (SHA-256 beim Lesen), Kopie erneut lesen und vergleichen, erst dann
  umbenennen und – beim Verschieben – das Original entfernen. Ein Abbruch hinterlässt keine halben Dateien.
- Ordner werden nie gelöscht; der alte (leere) Ordner bleibt stehen (Löschen nur auf Rückfrage: :func:`remove_empty`).

Nur Standardbibliothek.
"""
from __future__ import annotations

import csv
import hashlib
import os
import shutil
import time

CHUNK = 1024 * 1024
PART = ".part"


class Cancelled(Exception):
    pass


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _inside(child: str, parent: str) -> bool:
    c, p = _norm(child), _norm(parent)
    try:
        return c != p and os.path.commonpath([c, p]) == p
    except ValueError:
        return False


def _existing_parent(p: str) -> str:
    p = os.path.abspath(p)
    while p and not os.path.exists(p):
        q = os.path.dirname(p)
        if q == p:
            return ""
        p = q
    return p


def same_volume(a: str, b: str) -> bool:
    """Liegen a und b auf demselben Datenträger (Umbenennen möglich)?"""
    pa, pb = _existing_parent(a), _existing_parent(b)
    if not pa or not pb:
        return False
    try:
        return os.stat(pa).st_dev == os.stat(pb).st_dev
    except OSError:
        return False


def free_space(p: str) -> int:
    q = _existing_parent(p)
    try:
        return shutil.disk_usage(q).free if q else 0
    except OSError:
        return 0


def _files(src: str) -> list[tuple[str, str, int]]:
    """Alle Dateien unter src → [(rel, abs, size)] (ohne eigene .part-Reste)."""
    out = []
    for root, dirs, files in os.walk(src):
        dirs.sort(key=str.lower)
        for n in sorted(files, key=str.lower):
            if n.endswith(PART):
                continue
            p = os.path.join(root, n)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            out.append((os.path.relpath(p, src), p, size))
    return out


def _free_name(path: str, taken: set) -> str:
    stem, ext = os.path.splitext(path)
    n = 2
    while True:
        cand = f"{stem} ({n}){ext}"
        if not os.path.exists(cand) and _norm(cand) not in taken:
            return cand
        n += 1


def plan(src: str, dst: str) -> dict:
    """Vorschau: Anzahl, Grösse, freier Platz am Ziel, Konflikte (gleicher Name am Ziel)."""
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    out = {"src": src, "dst": dst, "files": 0, "bytes": 0, "free": free_space(dst), "same_volume": same_volume(src, dst),
           "conflicts": [], "error": ""}
    if not os.path.isdir(src):
        return out                                           # nichts zu übernehmen
    if _norm(src) == _norm(dst):
        out["error"] = "Neuer und bisheriger Ordner sind gleich."
        return out
    if _inside(dst, src):
        out["error"] = "Der neue Ordner liegt im bisherigen – bitte einen Ordner daneben wählen."
        return out
    files = _files(src)
    out["files"] = len(files)
    out["bytes"] = sum(s for _r, _p, s in files)
    out["conflicts"] = [r for r, _p, _s in files if os.path.exists(os.path.join(dst, r))]
    return out


def _sha_copy(src: str, part: str, cancel) -> str:
    h = hashlib.sha256()
    with open(src, "rb") as fi, open(part, "wb") as fo:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            b = fi.read(CHUNK)
            if not b:
                break
            h.update(b)
            fo.write(b)
        fo.flush()
        os.fsync(fo.fileno())
    return h.hexdigest()


def _sha(path: str, cancel) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run(src: str, dst: str, mode: str = "move", conflict: str = "keep", cancel=None, progress=None) -> dict:
    """Inhalt von src nach dst verschieben (mode "move") bzw. kopieren ("copy"). conflict: "keep" | "both".
    → {"moved": [{"old", "new"}], "copied", "kept": [rel], "renamed": [rel], "errors": [...], "bytes", "cancelled"}"""
    if mode not in ("move", "copy"):
        raise ValueError("move oder copy erwartet")
    progress = progress or (lambda m: None)
    p = plan(src, dst)
    if p["error"]:
        raise ValueError(p["error"])
    res = {"moved": [], "copied": 0, "kept": [], "renamed": [], "errors": [], "bytes": 0, "cancelled": False,
           "src": p["src"], "dst": p["dst"], "mode": mode}
    if not os.path.isdir(p["src"]):
        os.makedirs(p["dst"], exist_ok=True)
        return res
    files = _files(p["src"])
    same = p["same_volume"]
    os.makedirs(p["dst"], exist_ok=True)
    taken: set = set()
    progress(("total", len(files)))
    try:
        for i, (rel, path, size) in enumerate(files):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            progress(("progress", i, len(files), rel))
            target = os.path.join(p["dst"], rel)
            if os.path.exists(target) or _norm(target) in taken:
                if conflict != "both":
                    res["kept"].append(rel)
                    continue
                target = _free_name(target, taken)
                res["renamed"].append(rel)
            taken.add(_norm(target))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            try:
                if mode == "move" and same:
                    os.rename(path, target)                      # derselbe Datenträger: umbenennen
                else:
                    part = target + PART
                    try:
                        digest = _sha_copy(path, part, cancel)
                        shutil.copystat(path, part)
                        if os.path.getsize(part) != size or (not same and _sha(part, cancel) != digest):
                            raise OSError("Prüfsumme der Kopie stimmt nicht – Original bleibt")
                        if os.path.exists(target):              # inzwischen entstanden: nie überschreiben
                            raise OSError("Ziel ist inzwischen vorhanden – nichts überschrieben")
                        os.replace(part, target)
                    except BaseException:
                        try:
                            os.remove(part)
                        except OSError:
                            pass
                        raise
                    if mode == "move":
                        os.remove(path)
                if mode == "move":
                    res["moved"].append({"old": path, "new": target})
                else:
                    res["copied"] += 1
                res["bytes"] += size
            except Cancelled:
                raise
            except OSError as ex:
                res["errors"].append(f"{rel}: {ex}")
    except Cancelled:
        res["cancelled"] = True
    return res


def remove_empty(root: str, keep_root: bool = False) -> int:
    """Leere Ordner unter root entfernen (nur auf ausdrücklichen Wunsch; Dateien werden nie gelöscht). → Anzahl."""
    n = 0
    for d, _dirs, _files in sorted(os.walk(root), key=lambda x: -len(x[0])):
        if keep_root and _norm(d) == _norm(root):
            continue
        try:
            if not os.listdir(d):
                os.rmdir(d)
                n += 1
        except OSError:
            pass
    return n


def rebase(path: str, old: str, new: str) -> str:
    """Pfad unter old auf new umschreiben (sonst unverändert)."""
    if not path or not old or not new:
        return path
    if _norm(path) == _norm(old):
        return os.path.normpath(new)
    if _inside(path, old):
        return os.path.normpath(os.path.join(new, os.path.relpath(os.path.abspath(path), os.path.abspath(old))))
    return path


def journal(path: str, role: str, res: dict, transfer: str):
    """Zeile(n) in Ordnerwechsel.csv anhängen (Zeit;Rolle;Aktion;Von;Nach;Dateien;Bytes;Behalten;Fehler)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        if new:
            w.writerow(["Zeit", "Rolle", "Aktion", "Von", "Nach", "Dateien", "Bytes", "Behalten (Konflikt)", "Fehler",
                        "Abgebrochen"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), role, transfer, res.get("src", ""), res.get("dst", ""),
                    len(res.get("moved") or []) + int(res.get("copied") or 0), res.get("bytes", 0),
                    len(res.get("kept") or []), " | ".join(res.get("errors") or [])[:2000],
                    "ja" if res.get("cancelled") else ""])
