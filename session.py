"""
session.py – Zustand und Befehle einer Vergleichssitzung, unabhängig von der Oberfläche.

Die Web-Oberfläche ruft diese Methoden auf; alle Ergebnisse sind JSON-taugliche dict/list.
Lange Vorgänge (Einlesen, Speichern) laufen im Hintergrund – Fortschritt über task_status().
"""
from __future__ import annotations

import base64
import os
import threading

import core
from compare import PAIR_MODES, Rules, DEFAULT_TRIVIAL, Cancelled, diff, copy_tags, all_keys
from id3tags import key_label
from undo import UndoStack

VERSION = "3.0"
# Layout der Web-Oberfläche (Splitter, eingeklappte Seitenleiste): Schlüssel → erlaubter Typ
UI_KEYS = {"side_w": (int, float), "side_collapsed": bool, "pairs_w": (int, float),
           "col_name": (int, float), "col_ratio": (int, float)}


class Session:
    def __init__(self):
        self.lock = threading.RLock()
        self.cfg = core.load_config()
        triv = list(self.cfg.get("trivial", DEFAULT_TRIVIAL))
        known = set(self.cfg.get("trivial_known", triv))
        triv += [p for p in DEFAULT_TRIVIAL if p not in known and p not in triv]
        self.rules = Rules(triv)
        self.pairs: list = []
        self.cur: int | None = None
        self.left_root = self.right_root = ""
        self.undo = UndoStack()
        self.opts = {
            "filter": self.cfg.get("filter", "all"),
            "show_trivial": self.cfg.get("show_trivial", True),
            "empty_set": self.cfg.get("empty_set", "off"),
            "show_covers": self.cfg.get("show_covers", True),
            "query": "",
            "theme": self.cfg.get("web_theme", self.cfg.get("theme", "dark")),
        }
        self.task = {"running": False}
        self._cancel = None
        ui = self.cfg.get("web_ui")
        self.ui = {k: v for k, v in (ui.items() if isinstance(ui, dict) else []) if k in UI_KEYS}

    # ================================================================== Einstellungen
    def settings(self) -> dict:
        c = self.cfg
        return {
            "version": VERSION,
            "hist_left": c.get("hist_left", []), "hist_right": c.get("hist_right", []),
            "mode": c.get("mode", "filename"), "modes": [[k, v] for k, v in PAIR_MODES.items()],
            "recursive": c.get("recursive", False), "options": dict(self.opts),
            "empty_sets": [[k, v] for k, v in core.EMPTY_SETS.items()],
            "filter_ops": core.FILTER_OPS, "filter_sides": core.FILTER_SIDES,
            "ui": dict(self.ui),
        }

    def set_ui(self, name: str, value):
        """Layout merken (Breiten der Splitter, eingeklappte Seitenleiste)."""
        if name not in UI_KEYS or not isinstance(value, UI_KEYS[name]) or isinstance(value, bool) != (UI_KEYS[name] is bool):
            raise ValueError(f"Ungültige Layout-Einstellung: {name}")
        self.ui[name] = value
        self.cfg["web_ui"] = dict(self.ui)
        core.save_config({"web_ui": dict(self.ui)})
        return True

    def set_option(self, name: str, value):
        if name not in self.opts:
            raise ValueError(f"Unbekannte Option: {name}")
        self.opts[name] = value
        key = {"theme": "web_theme"}.get(name, name)
        if name != "query":
            self.cfg[key] = value
            core.save_config({key: value})
        return self.state()

    # ================================================================== Hintergrund-Aufgaben
    def _run(self, kind, label, fn):
        if self.task.get("running"):
            return {"ok": False, "error": "Es läuft bereits ein Vorgang."}
        self._cancel = threading.Event()
        self.task = {"running": True, "kind": kind, "label": label, "i": 0, "total": 0, "text": label,
                     "done": False, "error": None, "result": None}

        def progress(m):
            t = self.task
            if m[0] == "count":
                t["text"] = f"{core.fmt_n(m[1])} MP3-Dateien gefunden …"
            elif m[0] == "total":
                t["total"] = m[1]
            elif m[0] == "progress":
                t["i"], t["total"] = m[1], m[2]
                t["text"] = os.path.basename(m[3])
            elif m[0] == "pairing":
                t["text"] = "Ordne Dateien zu …"

        def worker():
            try:
                res = fn(self._cancel, progress)
                self.task.update(result=res)
            except Cancelled:
                self.task.update(result={"cancelled": True})
            except Exception as ex:  # noqa: BLE001
                self.task.update(error=str(ex))
            finally:
                self.task.update(running=False, done=True)
        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True}

    def task_status(self) -> dict:
        return dict(self.task)

    def cancel_task(self):
        if self._cancel is not None:
            self._cancel.set()
        return {"ok": True}

    # ================================================================== Laden
    def unsaved(self) -> int:
        return len(core.modified_files(self.pairs))

    def start_load(self, lp: str, rp: str, recursive: bool, mode: str, keep_current: bool = False):
        lp, rp = (lp or "").strip(), (rp or "").strip()
        err = core.check_paths(lp, rp)
        if err:
            return {"ok": False, "error": err}
        if mode not in PAIR_MODES:
            mode = "filename"
        keep = self.cur if keep_current else None

        def job(cancel, progress):
            pairs, errors = core.load_pairs(lp, rp, recursive, mode, cancel, progress)
            with self.lock:
                self.undo.clear()
                self.pairs = pairs
                self.left_root, self.right_root = lp, rp
                self.cur = keep if keep is not None and keep < len(pairs) else (0 if pairs else None)
            self.cfg.update(hist_left=core.history(self.cfg, "hist_left", lp),
                            hist_right=core.history(self.cfg, "hist_right", rp), mode=mode, recursive=recursive)
            core.save_config({k: self.cfg[k] for k in ("hist_left", "hist_right", "mode", "recursive")})
            return {"pairs": len(pairs), "errors": errors}
        return self._run("load", "Dateien einlesen", job)

    # ================================================================== Paarliste
    def pair_rows(self) -> dict:
        """Alle Paare mit Status (für die Liste) plus Zähler."""
        with self.lock:
            rows, counts = [], {"diff": 0, "triv": 0, "same": 0, "single": 0}
            for i, (l, r) in enumerate(self.pairs):
                st = core.pair_status(l, r, self.rules)
                counts[st["tag"]] += 1
                rows.append({"i": i, "left": core.rel_name(l, self.left_root), "right": core.rel_name(r, self.right_root),
                             "symbol": st["symbol"], "tag": st["tag"], "info": st["info"], "modified": st["modified"]})
            return {"rows": rows, "counts": counts, "left_root": self.left_root, "right_root": self.right_root}

    def filter_pairs(self, query="", key=None, op="enthält", val="", side="links oder rechts") -> list[int]:
        """Indizes der Paare, die zum (erweiterten) Filter passen."""
        flt = core.make_pair_filter(query, key, op, val, side)
        with self.lock:
            return [i for i, p in enumerate(self.pairs) if flt is None or flt(p)]

    def field_choices(self) -> list:
        with self.lock:
            return [[k, v] for k, v in core.field_choices(self.pairs).items()]

    def select(self, i):
        with self.lock:
            self.cur = i if i is not None and 0 <= i < len(self.pairs) else None
            return self.state()

    # ================================================================== Ansicht
    def files(self):
        return self.pairs[self.cur] if self.cur is not None and self.cur < len(self.pairs) else (None, None)

    def _file(self, side):
        l, r = self.files()
        return l if side == "L" else r

    @staticmethod
    def _covers(f, other):
        out = []
        if f is None:
            return out
        for k in sorted(k for k in f.items if k.startswith("APIC")):
            it = f.get(k)
            if not it.cover or not it.cover.data:
                continue
            mime = it.cover.mime or "image/jpeg"
            data = it.cover.data if len(it.cover.data) <= 4_000_000 else b""
            out.append({"key": k, "label": key_label(k), "desc": it.cover.describe(),
                        "differs": other is not None and other.get(k) != it,
                        "src": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}" if data else ""})
        return out

    def _side_head(self, f, root, other):
        if f is None:
            return None
        return {"name": os.path.basename(f.path), "rel": core.rel_name(f, root), "path": f.path,
                "info": f.info(), "version": f.version, "modified": f.is_modified(),
                "covers": self._covers(f, other) if self.opts["show_covers"] else []}

    def view(self) -> dict:
        with self.lock:
            l, r = self.files()
            o = self.opts
            keys, states = core.visible_keys(l, r, self.rules, o["filter"], o["show_trivial"], o["empty_set"], o["query"])
            rows = []
            for k in keys:
                st = states[k]
                row = {"key": k, "label": key_label(k), "state": st}
                fids = []
                for side, f, other in (("L", l, r), ("R", r, l)):
                    it = f.get(k) if f else None
                    if it is not None:
                        for x in it.frame_ids(f.version):
                            if x not in fids:
                                fids.append(x)
                    text = core.disp(it) if it is not None else ""
                    spans = []
                    if it is not None and st in ("diff", "triv") and other is not None and other.get(k) is not None:
                        spans = core.diff_spans(text, core.disp(other.get(k)))
                    row[side] = {
                        "present": it is not None, "text": text, "spans": spans,
                        "links": [[a, b, u] for a, b, u in core.link_spans(text)],
                        "mod": bool(f is not None and f.field_modified(k)),
                        "editable": core.can_edit_text(f, k),
                        "multiline": bool(it is not None and ("\n" in it.text or k.startswith("USLT"))),
                        "edit": core.edit_text(it) if it is not None and it.kind != "picture" else "",
                    } if f is not None else None
                row["fid"] = " · ".join(fids) or k.split(":")[0].split("#")[0]
                rows.append(row)
            return {"index": self.cur, "both": l is not None and r is not None,
                    "left": self._side_head(l, self.left_root, r), "right": self._side_head(r, self.right_root, l),
                    "rows": rows, "counts": core.state_counts(states)}

    def meta(self) -> dict:
        return {"unsaved": self.unsaved(), "can_undo": bool(self.undo.undo), "can_redo": bool(self.undo.redo),
                "undo_label": self.undo.undo[-1]["label"] if self.undo.undo else "",
                "redo_label": self.undo.redo[-1]["label"] if self.undo.redo else ""}

    def pair_row(self, i):
        if i is None or not (0 <= i < len(self.pairs)):
            return None
        l, r = self.pairs[i]
        st = core.pair_status(l, r, self.rules)
        return {"i": i, "left": core.rel_name(l, self.left_root), "right": core.rel_name(r, self.right_root),
                "symbol": st["symbol"], "tag": st["tag"], "info": st["info"], "modified": st["modified"]}

    def state(self, message=None, tone="info") -> dict:
        with self.lock:
            return {"view": self.view(), "pair": self.pair_row(self.cur), "meta": self.meta(),
                    "options": dict(self.opts), "message": message, "tone": tone}

    # ================================================================== Ändern
    @staticmethod
    def _dir(direction):
        return "nach rechts" if direction == "lr" else "nach links"

    def _src_dst(self, direction):
        l, r = self.files()
        return (l, r) if direction == "lr" else (r, l)

    def _done(self, msg, tone="info"):
        self.undo.commit()
        return self.state(msg, tone)

    def copy_keys(self, keys, direction):
        with self.lock:
            src, dst = self._src_dst(direction)
            if not (src and dst):
                return self.state("Kopieren geht nur, wenn links und rechts eine Datei vorhanden ist.", "warn")
            self.undo.checkpoint(f"{len(keys)} Feld(er) {self._dir(direction)}", [dst])
            n = 0
            for k in keys:
                if dst.get(k) != src.get(k):
                    dst.set(k, src.get(k))
                    n += 1
            return self._done(f"{n} Feld(er) {self._dir(direction)} kopiert – noch nicht gespeichert.")

    def copy_all(self, direction, delete_missing=None):
        """Alle Unterschiede übernehmen. Gibt es Felder nur im Ziel und ist delete_missing None,
        kommt {"ask": {...}} zurück – die Oberfläche fragt und ruft erneut auf."""
        with self.lock:
            src, dst = self._src_dst(direction)
            if not (src and dst):
                return self.state()
            imp, triv = diff(src, dst, self.rules)
            keys = imp + (triv if self.opts["show_trivial"] else [])
            if not keys:
                return self.state("Keine Unterschiede zum Kopieren.", "ok")
            missing = [k for k in keys if src.get(k) is None]
            if missing and delete_missing is None:
                return {"ask": {"count": len(missing), "labels": [key_label(k) for k in missing[:12]],
                                "more": max(0, len(missing) - 12)}}
            self.undo.checkpoint(f"Alles {self._dir(direction)}", [dst])
            n = copy_tags(src, dst, keys, delete_missing=bool(delete_missing))
            return self._done(f"{n} Feld(er) {self._dir(direction)} übernommen – noch nicht gespeichert.")

    def copy_missing(self, direction):
        with self.lock:
            src, dst = self._src_dst(direction)
            if not (src and dst):
                return self.state()
            keys = [k for k in all_keys(src, dst) if src.get(k) is not None and dst.get(k) is None]
            if not self.opts["show_trivial"]:
                keys = [k for k in keys if not self.rules.is_trivial(k)]
            if not keys:
                return self.state(f"Keine fehlenden Felder {'rechts' if direction == 'lr' else 'links'}.", "ok")
            self.undo.checkpoint(f"Fehlende {self._dir(direction)}", [dst])
            for k in keys:
                dst.set(k, src.get(k))
            return self._done(f"{len(keys)} fehlende(s) Feld(er) {self._dir(direction)} übernommen – noch nicht gespeichert.")

    def remove(self, side, keys):
        with self.lock:
            f = self._file(side)
            keys = [k for k in keys if f is not None and f.get(k) is not None]
            if not keys:
                return self.state()
            self.undo.checkpoint(f"{len(keys)} Feld(er) entfernt", [f])
            for k in keys:
                f.set(k, None)
            return self._done(f"{len(keys)} Feld(er) entfernt – noch nicht gespeichert.")

    def set_value(self, side, key, text):
        with self.lock:
            f = self._file(side)
            if f is None or not core.can_edit_text(f, key):
                return self.state("Dieses Feld kann nicht als Text bearbeitet werden.", "warn")
            it = f.get(key)
            if core.normalize_value(text) == (it.text if it else ""):
                return self.state()
            self.undo.checkpoint(f"„{key_label(key)}“ bearbeitet", [f])
            core.apply_value(f, key, text)
            return self._done(None)

    def revert_pair(self):
        with self.lock:
            files = [f for f in self.files() if f]
            self.undo.checkpoint("Paar verworfen", files)
            for f in files:
                f.revert()
            return self._done("Änderungen an diesem Paar verworfen.")

    def do_undo(self):
        with self.lock:
            e = self.undo.do_undo()
            return self.state(f"Rückgängig: {e['label']}" if e else None)

    def do_redo(self):
        with self.lock:
            e = self.undo.do_redo()
            return self.state(f"Wiederholt: {e['label']}" if e else None)

    # ================================================================== Speichern
    def start_save(self):
        files = core.modified_files(self.pairs)
        if not files:
            return {"ok": False, "error": "Keine ungespeicherten Änderungen."}
        backup_on = self.cfg.get("backup_enabled", True)
        folder = self.cfg.get("backup_dir") or None

        def job(cancel, progress):
            with self.lock:
                return core.save_files(files, backup_on, folder, cancel, progress)
        return self._run("save", f"{len(files)} Datei(en) speichern", job)
