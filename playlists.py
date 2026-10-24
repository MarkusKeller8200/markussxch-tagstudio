"""MarKusSXCH TagStudio – Playlists (#267): Speicher, Ordner, Archiv und Playlist-Ordner (M3U8).

Massgebend ist der Speicher im Datenordner des Profils (``~/TagStudio/Playlists``):

    index.json          Ordner, zuletzt benutzt, geschriebene M3U8 (Pfad + SHA-256), ignorierte fremde Dateien
    pl_<id>.json        eine Datei je Playlist (atomar geschrieben)

Zusätzlich liegt jede aktive Playlist als M3U8 im **Playlist-Ordner** (Standard ``<Basisordner>/03_Playlists``),
Unterordner = Ordner im Baum, Pfade relativ zur M3U8. TagStudio schreibt dort nur eigene Dateien und überschreibt
nie eine Datei, die ein anderes Programm geändert hat (→ ``external_changes``).

Archivieren statt Löschen (wie bei den Titeln, #173): die Playlist bekommt ``archived``, ihre M3U8 wandert nach
``<Archiv>/_Playlists/…`` mit Vermerk in ``_aussortiert.csv`` (Bereich „Playlists“). Endgültig gelöscht wird nur
eine archivierte Playlist. Nur Standardbibliothek.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import re
import secrets
import shutil
import time
import urllib.parse

import archive
import setexport

FORMAT = 1
KINDS = ("manual", "djset", "smart", "import", "queue")
ITEM_KEYS = ("path", "size", "akey", "added", "lock", "note", "artist", "title", "dur", "ref")
MIRROR_EXT = ".m3u8"
ARCHIVE_SUB = "_Playlists"          # im Archiv-Ordner
MIRROR_ARCHIVE = "_Archiv"          # im Playlist-Ordner, wenn kein Archiv-Ordner festgelegt ist
AREA = "Playlists"
UNDO_MAX = 50
RECENT_MAX = 8
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


# =========================================================================== kleine Hilfen
def nk(p: str) -> str:
    """Vergleichsschlüssel eines Pfads (Gross-/Kleinschreibung unter Windows egal)."""
    return os.path.normcase(os.path.abspath(p))


def clean_name(name) -> str:
    n = " ".join(str(name or "").split())[:120]
    if not n:
        raise ValueError("Bitte einen Namen eingeben.")
    return n


def clean_folder(folder) -> str:
    """„Sets / 2026“ bzw. „Sets\\2026“ → „Sets/2026“ (ohne leere Teile, „.“ und „..“)."""
    parts = re.split(r"[/\\]+", str(folder or ""))
    out = [" ".join(p.split())[:80] for p in parts]
    return "/".join(p for p in out if p and p not in (".", ".."))


def safe_part(part: str) -> str:
    """Teil eines Dateinamens: verbotene Zeichen → _, keine reservierten Namen unter Windows."""
    s = _BAD.sub("_", part).strip(" .") or "_"
    return s + "_" if s.split(".")[0].upper() in _RESERVED else s


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _unique(path: str) -> str:
    stem, ext = os.path.splitext(path)
    k, cand = 1, path
    while os.path.exists(cand):
        k += 1
        cand = f"{stem} ({k}){ext}"
    return cand


def clean_item(x) -> dict | None:
    """Eintrag bereinigen. Ein Eintrag braucht einen Pfad oder (später, #271) eine Angabe „ref“ ohne Datei."""
    if isinstance(x, str):
        x = {"path": x}
    if not isinstance(x, dict):
        return None
    out = {k: x[k] for k in ITEM_KEYS if k in x and x[k] not in (None, "")}
    if not isinstance(out.get("path", ""), str) or not (out.get("path") or isinstance(out.get("ref"), dict)):
        return None
    if "lock" in out:
        out["lock"] = bool(out["lock"])
        if not out["lock"]:
            del out["lock"]
    return out


# =========================================================================== M3U / M3U8
def parse_m3u(text: str, base_dir: str) -> list[dict]:
    """M3U/M3U8 lesen → [{"path", "label", "dur"}]. Relative Pfade gelten ab base_dir; file://-Adressen und
    Windows-Pfade mit „\\“ (auch auf macOS geschrieben) werden verstanden."""
    out, label, dur = [], "", None
    for line in str(text or "").splitlines():
        s = line.strip().lstrip("﻿")
        if not s:
            continue
        if s.upper().startswith("#EXTINF:"):
            head, _, lab = s[8:].partition(",")
            try:
                dur = int(float(head.split()[0])) if head.split() else None
            except ValueError:
                dur = None
            label = lab.strip()
            continue
        if s.startswith("#"):
            continue
        p = s
        if p.lower().startswith("file://"):
            p = setexport.path_from_location(p) if p.lower().startswith("file://localhost") \
                else urllib.parse.unquote(re.sub(r"^file://", "", p, flags=re.I))
            if re.match(r"^/[A-Za-z]:/", p):
                p = p[1:]
        win_abs = bool(re.match(r"^[A-Za-z]:[\\/]", p)) or p.startswith("\\\\")
        if os.sep == "/" and not win_abs:
            p = p.replace("\\", "/")
        if not win_abs and not os.path.isabs(p):
            p = os.path.normpath(os.path.join(base_dir, p))
        out.append({"path": p, "label": label, "dur": dur if dur and dur > 0 else None})
        label, dur = "", None
    return out


def m3u_text(pl: dict, dest_dir: str) -> str:
    entries = [{"path": it["path"], "artist": it.get("artist", ""), "title": it.get("title", ""),
                "duration": it.get("dur") or 0} for it in pl.get("items") or [] if it.get("path")]
    return setexport.m3u8(entries, dest_dir, True, pl.get("name", ""))


# =========================================================================== Speicher
class Store:
    def __init__(self, root: str, mirror: str = "", archive_dir: str = ""):
        self.root = root
        self.mirror = mirror or ""
        self.archive_dir = archive_dir or ""
        self._pls: dict[str, dict] | None = None
        self._index: dict | None = None
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []

    # ------------------------------------------------------------------ Laden und Schreiben
    def _file(self, pid: str) -> str:
        return os.path.join(self.root, f"{pid}.json")

    @property
    def index(self) -> dict:
        if self._index is None:
            try:
                with open(os.path.join(self.root, "index.json"), encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                d = {}
            d = d if isinstance(d, dict) else {}
            d.setdefault("format", FORMAT)
            for k, typ in (("folders", list), ("recent", list), ("written", dict), ("ignored", list), ("migrated", dict)):
                if not isinstance(d.get(k), typ):
                    d[k] = typ()
            self._index = d
        return self._index

    def save_index(self):
        _write_json(os.path.join(self.root, "index.json"), self.index)

    def _all(self) -> dict[str, dict]:
        if self._pls is None:
            out = {}
            try:
                names = os.listdir(self.root)
            except OSError:
                names = []
            for n in names:
                if not (n.startswith("pl_") and n.endswith(".json")):
                    continue
                try:
                    with open(os.path.join(self.root, n), encoding="utf-8") as fh:
                        d = json.load(fh)
                except (OSError, ValueError):
                    continue
                if isinstance(d, dict) and d.get("id") == n[:-5]:
                    d["items"] = [y for y in (clean_item(x) for x in d.get("items") or []) if y]
                    out[d["id"]] = d
            self._pls = out
        return self._pls

    def _put(self, pl: dict):
        pl["modified"] = int(time.time())
        self._all()[pl["id"]] = pl
        _write_json(self._file(pl["id"]), pl)

    def _drop(self, pid: str):
        self._all().pop(pid, None)
        try:
            os.remove(self._file(pid))
        except OSError:
            pass

    # ------------------------------------------------------------------ Abfragen
    def get(self, pid) -> dict:
        pl = self._all().get(str(pid or ""))
        if pl is None:
            raise ValueError("Playlist nicht gefunden.")
        return pl

    def exists(self, pid) -> bool:
        return str(pid or "") in self._all()

    def active(self) -> list[dict]:
        return sorted((p for p in self._all().values() if not p.get("archived")),
                      key=lambda p: (p.get("folder", "").lower(), p["name"].lower(), p["id"]))

    def archived(self) -> list[dict]:
        return sorted((p for p in self._all().values() if p.get("archived")), key=lambda p: -int(p["archived"]))

    def find(self, name, folder=None) -> dict | None:
        """Aktive Playlist mit diesem Namen (und Ordner, wenn angegeben)."""
        n = " ".join(str(name or "").split()).lower()
        for p in self.active():
            if p["name"].lower() == n and (folder is None or p.get("folder", "") == clean_folder(folder)):
                return p
        return None

    def find_source(self, plugin, sid) -> dict | None:
        for p in self.active():
            src = p.get("source") or {}
            if src.get("plugin") == plugin and str(src.get("id")) == str(sid):
                return p
        return None

    def meta(self, pl: dict) -> dict:
        return {"id": pl["id"], "name": pl["name"], "folder": pl.get("folder", ""), "kind": pl.get("kind", "manual"),
                "count": len(pl.get("items") or []), "modified": pl.get("modified", 0), "created": pl.get("created", 0),
                "archived": pl.get("archived") or 0, "color": pl.get("color", ""), "note": pl.get("note", ""),
                "source": pl.get("source") or None, "file": self.mirror_path(pl["id"]) if not pl.get("archived") else pl.get("archived_file", "")}

    def folders(self) -> list[str]:
        """Alle Ordner: angelegte und die der aktiven Playlists (mit allen Elternordnern)."""
        out = set()
        for f in list(self.index["folders"]) + [p.get("folder", "") for p in self.active()]:
            parts = clean_folder(f).split("/") if f else []
            for k in range(1, len(parts) + 1):
                out.add("/".join(parts[:k]))
        return sorted(out, key=lambda s: [x.lower() for x in s.split("/")])

    def recent(self) -> list[str]:
        return [i for i in self.index["recent"] if self.exists(i) and not self.get(i).get("archived")][:RECENT_MAX]

    def touch(self, pid):
        r = [x for x in self.index["recent"] if x != pid]
        self.index["recent"] = [pid] + r[:RECENT_MAX * 2]
        self.save_index()

    # ------------------------------------------------------------------ Rückgängig
    def _snap(self, ids, label: str) -> dict:
        return {"label": label, "pls": {i: copy.deepcopy(self._all().get(i)) for i in ids},
                "folders": list(self.index["folders"])}

    def _record(self, rec: dict):
        self.undo_stack.append(rec)
        del self.undo_stack[:-UNDO_MAX]
        self.redo_stack.clear()

    def _swap(self, rec: dict) -> dict:
        back = self._snap(list(rec["pls"]), rec["label"])
        for pid, pl in rec["pls"].items():
            if pl is None:
                self._drop(pid)
            else:
                self._all()[pid] = copy.deepcopy(pl)
                _write_json(self._file(pid), pl)
        self.index["folders"] = list(rec["folders"])
        self.save_index()
        self.sync(list(rec["pls"]))
        return back

    def undo(self) -> str:
        if not self.undo_stack:
            raise ValueError("Nichts rückgängig zu machen.")
        rec = self.undo_stack.pop()
        self.redo_stack.append(self._swap(rec))
        return rec["label"]

    def redo(self) -> str:
        if not self.redo_stack:
            raise ValueError("Nichts zu wiederholen.")
        rec = self.redo_stack.pop()
        self.undo_stack.append(self._swap(rec))
        return rec["label"]

    def _change(self, ids, label, fn):
        """Änderung mit Rückgängig-Eintrag und nachgeführtem Playlist-Ordner."""
        rec = self._snap(ids, label)
        out = fn()
        self._record(rec)
        self.sync(ids)
        return out

    # ------------------------------------------------------------------ Ändern
    def _check_free(self, name, folder, skip=None):
        for p in self.active():
            if p["id"] != skip and p.get("folder", "") == folder and p["name"].lower() == name.lower():
                if folder:
                    raise ValueError(f"Eine Playlist „{name}“ gibt es im Ordner „{folder}“ schon.")
                raise ValueError(f"Eine Playlist „{name}“ gibt es schon.")

    def unique_name(self, name, folder, suffix="") -> str:
        name, folder = clean_name(name), clean_folder(folder)
        taken = {p["name"].lower() for p in self.active() if p.get("folder", "") == folder}
        if name.lower() not in taken and not suffix:
            return name
        k = 1
        while True:
            cand = f"{name} ({suffix}{'' if k == 1 else ' ' + str(k)})" if suffix else f"{name} ({k + 1})"
            if cand.lower() not in taken:
                return cand
            k += 1

    def create(self, name, folder="", kind="manual", items=None, **extra) -> dict:
        name, folder = clean_name(name), clean_folder(folder)
        self._check_free(name, folder)
        pid = "pl_" + secrets.token_hex(6)
        now = int(time.time())
        pl = {"format": FORMAT, "id": pid, "name": name, "folder": folder, "kind": kind if kind in KINDS else "manual",
              "created": now, "items": [y for y in (clean_item(x) for x in items or []) if y]}
        for k in ("color", "note", "source", "djset", "rules"):
            if extra.get(k):
                pl[k] = extra[k]
        self._change([pid], "Playlist anlegen", lambda: self._put(pl))
        return pl

    def update(self, pid, label="Playlist ändern", **fields) -> dict:
        pl = copy.deepcopy(self.get(pid))
        if pl.get("archived"):
            raise ValueError("Archivierte Playlists lassen sich nicht ändern – zuerst zurückholen.")
        if "name" in fields or "folder" in fields:
            name = clean_name(fields.get("name", pl["name"]))
            folder = clean_folder(fields.get("folder", pl.get("folder", "")))
            self._check_free(name, folder, skip=pid)
            pl["name"], pl["folder"] = name, folder
        if "items" in fields:
            pl["items"] = [y for y in (clean_item(x) for x in fields["items"] or []) if y]
        for k in ("color", "note", "kind", "source", "djset", "rules"):
            if k in fields:
                if fields[k] in (None, "", {}):
                    pl.pop(k, None)
                else:
                    pl[k] = fields[k]
        self._change([pid], label, lambda: self._put(pl))
        return pl

    def rename(self, pid, name) -> dict:
        return self.update(pid, "Umbenennen", name=name)

    def move(self, pid, folder) -> dict:
        return self.update(pid, "Verschieben", folder=folder)

    def duplicate(self, pid) -> dict:
        src = self.get(pid)
        name = self.unique_name(src["name"], src.get("folder", ""), "Kopie")
        extra = {k: copy.deepcopy(src[k]) for k in ("color", "note", "djset", "rules") if src.get(k)}
        return self.create(name, src.get("folder", ""), src.get("kind", "manual") if src.get("kind") != "queue" else "manual",
                           copy.deepcopy(src.get("items") or []), **extra)

    def merge(self, ids, name, folder="") -> dict:
        items = []
        for pid in ids:
            items += copy.deepcopy(self.get(pid).get("items") or [])
        return self.create(name, folder, "manual", items)

    def add(self, pid, items, dupes="ask") -> dict:
        """Einträge anhängen. dupes: "ask" (bei Doppelten nichts ändern, nur melden), "add", "skip"."""
        pl = self.get(pid)
        new = [y for y in (clean_item(x) for x in items or []) if y]
        have = {nk(x["path"]) for x in pl.get("items") or [] if x.get("path")}
        dup = 0
        seen = set(have)
        for x in new:
            if x.get("path") and nk(x["path"]) in seen:
                dup += 1
            if x.get("path"):
                seen.add(nk(x["path"]))
        if dup and dupes == "ask":
            return {"ask": True, "dupes": dup, "new": len(new) - dup, "added": 0}
        if dupes == "skip":
            keep, seen = [], set(have)
            for x in new:
                if x.get("path") and nk(x["path"]) in seen:
                    continue
                if x.get("path"):
                    seen.add(nk(x["path"]))
                keep.append(x)
            new = keep
        now = int(time.time())
        for x in new:
            x.setdefault("added", now)
        if new:
            self.update(pid, "Titel hinzufügen", items=list(pl.get("items") or []) + new)
        self.touch(pid)
        return {"ask": False, "dupes": dup, "added": len(new)}

    def remove(self, pid, indices) -> int:
        pl = self.get(pid)
        drop = {int(i) for i in indices or [] if isinstance(i, int)}
        items = [x for k, x in enumerate(pl.get("items") or []) if k not in drop]
        n = len(pl.get("items") or []) - len(items)
        if n:
            self.update(pid, "Titel entfernen", items=items)
        return n

    def order(self, pid, perm) -> dict:
        """Neue Reihenfolge als Liste der bisherigen Positionen (fehlende hängen hinten an)."""
        pl = self.get(pid)
        items = pl.get("items") or []
        seen, out = set(), []
        for i in perm or []:
            if isinstance(i, int) and 0 <= i < len(items) and i not in seen:
                out.append(items[i])
                seen.add(i)
        out += [x for k, x in enumerate(items) if k not in seen]
        return self.update(pid, "Reihenfolge", items=out)

    # ------------------------------------------------------------------ Ordner
    def folder_create(self, path) -> str:
        f = clean_folder(path)
        if not f:
            raise ValueError("Bitte einen Ordnernamen eingeben.")
        if f not in self.index["folders"]:
            rec = self._snap([], "Ordner anlegen")
            self.index["folders"].append(f)
            self.save_index()
            self._record(rec)
        return f

    def _under(self, folder, prefix) -> bool:
        return folder == prefix or folder.startswith(prefix + "/")

    def folder_rename(self, old, new) -> str:
        old, new = clean_folder(old), clean_folder(new)
        if not old or not new:
            raise ValueError("Bitte einen Ordnernamen eingeben.")
        if old == new:
            return new
        if self._under(new, old):
            raise ValueError("Ein Ordner lässt sich nicht in sich selbst verschieben.")
        pls = [p for p in self.active() if self._under(p.get("folder", ""), old)]
        for p in pls:
            nf = new + p.get("folder", "")[len(old):]
            self._check_free(p["name"], nf, skip=p["id"])
        rec = self._snap([p["id"] for p in pls], "Ordner umbenennen")
        for p in pls:
            q = copy.deepcopy(p)
            q["folder"] = new + p.get("folder", "")[len(old):]
            self._put(q)
        self.index["folders"] = sorted({(new + f[len(old):]) if self._under(f, old) else f for f in self.index["folders"]})
        self.save_index()
        self._record(rec)
        self.sync([p["id"] for p in pls])
        return new

    def folder_remove(self, path):
        """Leeren Ordner entfernen (Ordner mit Playlists: diese zuerst archivieren oder verschieben)."""
        f = clean_folder(path)
        if any(self._under(p.get("folder", ""), f) for p in self.active()):
            raise ValueError("Der Ordner enthält noch Playlists – zuerst archivieren oder verschieben.")
        rec = self._snap([], "Ordner entfernen")
        self.index["folders"] = [x for x in self.index["folders"] if not self._under(x, f)]
        self.save_index()
        self._record(rec)

    # ------------------------------------------------------------------ Archiv
    def _archive_root(self) -> str:
        if self.archive_dir:
            return os.path.join(self.archive_dir, ARCHIVE_SUB)
        return os.path.join(self.mirror, MIRROR_ARCHIVE) if self.mirror else ""

    def _log_dir(self) -> str:
        return self.archive_dir or (os.path.join(self.mirror, MIRROR_ARCHIVE) if self.mirror else "")

    def _log(self, src, dst):
        d = self._log_dir()
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        log = os.path.join(d, archive.LOG)
        new = not os.path.exists(log)
        with open(log, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
            w = csv.writer(fh, delimiter=";")
            if new:
                w.writerow(archive.HEAD)
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), src, dst, AREA, ""])

    def _log_restored(self, dst):
        log = os.path.join(self._log_dir() or "", archive.LOG)
        if not self._log_dir() or not os.path.isfile(log):
            return
        with open(log, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
        for r in reversed(rows[1:]):
            r += [""] * (5 - len(r))
            if os.path.normcase(r[2]) == os.path.normcase(dst) and not r[4]:
                r[4] = time.strftime("%Y-%m-%d %H:%M:%S")
                break
        with open(log, "w", encoding="utf-8-sig", newline="") as fh:
            csv.writer(fh, delimiter=";").writerows(rows)

    def archive(self, pid) -> dict:
        """Archivieren: Playlist bleibt erhalten (Archiv-Bereich), ihre M3U8 wandert ins Archiv."""
        pl = copy.deepcopy(self.get(pid))
        if pl.get("archived"):
            return pl
        pl["archived"] = int(time.time())
        info = self.index["written"].pop(pid, None)
        if info and self.mirror:
            src = os.path.join(self.mirror, *info["rel"].split("/"))
            root = self._archive_root()
            if os.path.isfile(src) and root:
                dst = _unique(os.path.join(root, *info["rel"].split("/")))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
                self._log(src, dst)
                pl["archived_file"] = dst
        self._put(pl)
        self.index["recent"] = [x for x in self.index["recent"] if x != pid]
        self.save_index()
        self.undo_stack = [r for r in self.undo_stack if pid not in r["pls"]]     # Archivieren ersetzt das Rückgängig
        self.redo_stack = [r for r in self.redo_stack if pid not in r["pls"]]
        return pl

    def archive_folder(self, path) -> int:
        f = clean_folder(path)
        pls = [p for p in self.active() if self._under(p.get("folder", ""), f)]
        for p in pls:
            self.archive(p["id"])
        self.index["folders"] = [x for x in self.index["folders"] if not self._under(x, f)]
        self.save_index()
        return len(pls)

    def restore(self, pid) -> dict:
        """Aus dem Archiv zurückholen (bei gleichem Namen im Ordner mit Zusatz „(2)“)."""
        pl = copy.deepcopy(self.get(pid))
        if not pl.get("archived"):
            return pl
        pl.pop("archived", None)
        try:
            self._check_free(pl["name"], pl.get("folder", ""), skip=pid)
        except ValueError:
            pl["name"] = self.unique_name(pl["name"], pl.get("folder", ""))
        old = pl.pop("archived_file", "")
        self._put(pl)
        if old and os.path.isfile(old) and self.mirror:
            rel = self.desired().get(pid)
            dst = os.path.join(self.mirror, *rel.split("/")) if rel else ""
            if dst and not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(old, dst)
                self._log_restored(old)
                self.index["written"][pid] = {"rel": rel, "sha": sha_file(dst)}
                self.save_index()
        self.sync([pid])
        return pl

    def delete(self, pid):
        """Endgültig löschen – nur archivierte Playlists (die Oberfläche fragt vorher)."""
        pl = self.get(pid)
        if not pl.get("archived"):
            raise ValueError("Nur archivierte Playlists lassen sich endgültig löschen.")
        f = pl.get("archived_file", "")
        if f and os.path.isfile(f):
            os.remove(f)
        self._drop(pid)
        self.index["written"].pop(pid, None)
        self.save_index()

    # ------------------------------------------------------------------ Playlist-Ordner (M3U8)
    def desired(self) -> dict[str, str]:
        """Aktive Playlist → relativer Pfad ihrer M3U8 im Playlist-Ordner (Trenner „/“, eindeutig)."""
        out, used = {}, set()
        for p in self.active():
            parts = [safe_part(x) for x in p.get("folder", "").split("/") if x]
            stem = safe_part(p["name"])
            rel = "/".join(parts + [stem + MIRROR_EXT])
            k = 1
            while rel.lower() in used:
                k += 1
                rel = "/".join(parts + [f"{stem} ({k}){MIRROR_EXT}"])
            used.add(rel.lower())
            out[p["id"]] = rel
        return out

    def mirror_path(self, pid) -> str:
        if not self.mirror:
            return ""
        rel = self.desired().get(pid)
        return os.path.join(self.mirror, *rel.split("/")) if rel else ""

    def sync(self, ids=None) -> dict:
        """M3U8 der genannten (None = aller) Playlists schreiben, umbenennen bzw. entfernen. Von anderen Programmen
        geänderte oder fremde Dateien bleiben unangetastet (→ external_changes)."""
        if not self.mirror:
            return {"written": 0, "conflicts": []}
        want = self.desired()
        ids = set(want) | set(self.index["written"]) if ids is None else set(ids)
        written = self.index["written"]
        n, conflicts = 0, []
        for pid in sorted(ids):
            rel, info = want.get(pid), written.get(pid)
            path = os.path.join(self.mirror, *rel.split("/")) if rel else ""
            if info and info["rel"] != rel:                          # umbenannt, verschoben, entfernt
                old = os.path.join(self.mirror, *info["rel"].split("/"))
                if os.path.isfile(old) and sha_file(old) != info["sha"]:
                    conflicts.append(info["rel"])                    # von aussen geändert: bleibt liegen (→ „neu“)
                    written.pop(pid, None)
                    info = None
                elif os.path.isfile(old):
                    if not rel:
                        os.remove(old)                               # eigene, unveränderte Datei einer entfernten Playlist
                        written.pop(pid, None)
                        continue
                    if os.path.exists(path):                         # Ziel belegt (fremde Datei)
                        conflicts.append(rel)
                        continue
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    os.replace(old, path)
                    info = written[pid] = {"rel": rel, "sha": info["sha"]}
                else:
                    written.pop(pid, None)
                    info = None
            if not rel:
                written.pop(pid, None)
                continue
            text = m3u_text(self.get(pid), os.path.dirname(path))
            sha = sha_text(text)
            if os.path.isfile(path):
                cur = sha_file(path)
                if cur == sha:
                    written[pid] = {"rel": rel, "sha": sha}
                    continue
                if not info or info.get("sha") != cur:               # fremd oder von aussen geändert
                    conflicts.append(rel)
                    continue
            _write_text(path, text)
            written[pid] = {"rel": rel, "sha": sha}
            n += 1
        self.save_index()
        return {"written": n, "conflicts": conflicts}

    def external_changes(self) -> list[dict]:
        """Änderungen im Playlist-Ordner durch andere Programme: geändert, entfernt, neu."""
        if not self.mirror or not os.path.isdir(self.mirror):
            return []
        out, known = [], set()
        for pid, info in self.index["written"].items():
            if not self.exists(pid):
                continue
            known.add(info["rel"].lower())
            path = os.path.join(self.mirror, *info["rel"].split("/"))
            if not os.path.isfile(path):
                out.append({"kind": "removed", "id": pid, "rel": info["rel"], "name": self.get(pid)["name"]})
            elif sha_file(path) != info["sha"]:
                out.append({"kind": "changed", "id": pid, "rel": info["rel"], "name": self.get(pid)["name"]})
        ignored = {x.lower() for x in self.index["ignored"]}
        for dp, dns, fns in os.walk(self.mirror):
            dns[:] = [d for d in dns if d != MIRROR_ARCHIVE and not d.startswith(".")]
            for fn in fns:
                if not fn.lower().endswith((".m3u8", ".m3u")):
                    continue
                rel = os.path.relpath(os.path.join(dp, fn), self.mirror).replace(os.sep, "/")
                if rel.lower() in known or rel.lower() in ignored:
                    continue
                out.append({"kind": "new", "id": "", "rel": rel, "name": os.path.splitext(fn)[0]})
        return sorted(out, key=lambda x: x["rel"].lower())

    def read_mirror(self, rel) -> list[dict]:
        path = os.path.join(self.mirror, *rel.split("/"))
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return parse_m3u(fh.read(), os.path.dirname(path))

    def apply_external(self, rel, action) -> dict:
        """Eine Änderung von aussen übernehmen ("take"), die TagStudio-Fassung behalten ("keep"; bei neuen Dateien:
        ignorieren) oder – bei entfernten Dateien – die Playlist archivieren ("archive")."""
        ch = next((c for c in self.external_changes() if c["rel"] == rel), None)
        if ch is None:
            raise ValueError("Diese Änderung gibt es nicht mehr.")
        path = os.path.join(self.mirror, *rel.split("/"))
        if ch["kind"] == "new":
            if action == "take":
                folder = "/".join(rel.split("/")[:-1])
                name = self.unique_name(os.path.splitext(rel.split("/")[-1])[0], folder)
                items = [{"path": e["path"], "dur": e["dur"], **self._split_label(e["label"])} for e in self.read_mirror(rel)]
                pl = self.create(name, folder, "import", items, source={"plugin": "file", "id": rel})
                if self.desired().get(pl["id"]) == rel:
                    self.index["written"][pl["id"]] = {"rel": rel, "sha": sha_file(path)}
                else:                                                   # z. B. .m3u → eigene .m3u8 daneben
                    self.index["ignored"].append(rel)
                self.save_index()
                self.sync([pl["id"]])
                return {"id": pl["id"]}
            self.index["ignored"].append(rel)
            self.save_index()
            return {"id": ""}
        pid = ch["id"]
        if ch["kind"] == "changed" and action == "take":
            old = {nk(x["path"]): x for x in self.get(pid).get("items") or [] if x.get("path")}
            items = []
            for e in self.read_mirror(rel):
                x = dict(old.get(nk(e["path"])) or {"path": e["path"], **self._split_label(e["label"])})
                x["path"] = e["path"]
                if e["dur"]:
                    x["dur"] = e["dur"]
                items.append(x)
            self.index["written"][pid]["sha"] = sha_file(path)
            self.save_index()
            self.update(pid, "Änderung übernehmen", items=items)
        elif ch["kind"] == "changed":                                   # TagStudio-Fassung behalten
            self.index["written"][pid]["sha"] = sha_file(path)
            self.save_index()
            self.sync([pid])
        elif action == "archive":                                       # Datei entfernt → Playlist archivieren
            self.index["written"].pop(pid, None)
            self.save_index()
            self.archive(pid)
        else:                                                           # Datei entfernt → neu schreiben
            self.index["written"].pop(pid, None)
            self.save_index()
            self.sync([pid])
        return {"id": pid}

    @staticmethod
    def _split_label(label) -> dict:
        a, sep, t = str(label or "").partition(" - ")
        return {"artist": a.strip(), "title": t.strip()} if sep else ({"title": label.strip()} if label else {})

    # ------------------------------------------------------------------ Übernahme (DJ-Set-Listen, #269)
    def migrate_djset(self, saved: dict, current: str = "", folder: str = "DJ-Sets") -> dict:
        """Gespeicherte DJ-Set-Listen (cfg „djset_saved“) einmalig übernehmen → {alter Name: id}."""
        if self.index["migrated"].get("djset"):
            return {}
        out = {}
        for name, v in sorted((saved or {}).items()):
            if not isinstance(v, dict):
                continue
            items = [{"path": x["path"], **({"lock": True} if x.get("lock") else {})}
                     for x in v.get("items") or [] if isinstance(x, dict) and isinstance(x.get("path"), str)]
            src, f, n, kind = v.get("source"), folder, name, "djset"
            if src and ": " in name:                                  # „Lexicon: Freitag“ → Ordner Lexicon
                f, n = name.split(": ", 1)
                kind = "import"
            try:
                n = self.unique_name(n, f)
                pl = self.create(n, f, kind, items, djset={"opts": v["opts"]} if isinstance(v.get("opts"), dict) else None,
                                 source={"plugin": src, "id": ""} if src else None)
            except ValueError:
                continue
            out[name] = pl["id"]
        self.index["migrated"]["djset"] = int(time.time())
        self.save_index()
        self.undo_stack.clear()
        return out
