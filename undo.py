"""
undo.py – Rückgängig/Wiederholen über Schnappschüsse (unabhängig von der Oberfläche).
"""
from __future__ import annotations


class UndoStack:
    """Schnappschuss-basiertes Undo/Redo über beliebig viele Dateien (Tags + ID3-Version)."""

    def __init__(self, limit=200):
        self.limit = limit
        self.undo: list = []
        self.redo: list = []
        self.pending = None

    @staticmethod
    def _snap(f):
        return {k: v.clone() for k, v in f.items.items()}, f.version

    @staticmethod
    def _same(a, b):
        (ia, va), (ib, vb) = a, b
        return va == vb and ia.keys() == ib.keys() and all(ia[k] == ib[k] for k in ia)

    def checkpoint(self, label, files):
        """Vor einer Änderung aufrufen: merkt sich den Zustand der betroffenen Dateien."""
        if self.pending is None:
            self.pending = {"label": label, "before": {}, "files": {}}
        for f in files:
            if f is not None and id(f) not in self.pending["before"]:
                self.pending["before"][id(f)] = self._snap(f)
                self.pending["files"][id(f)] = f

    def commit(self):
        p, self.pending = self.pending, None
        if not p:
            return False
        after = {i: self._snap(f) for i, f in p["files"].items()}
        changed = [i for i in after if not self._same(p["before"][i], after[i])]
        if not changed:
            return False
        p["before"] = {i: p["before"][i] for i in changed}
        p["after"] = {i: after[i] for i in changed}
        p["files"] = {i: p["files"][i] for i in changed}
        self.undo.append(p)
        del self.undo[:-self.limit]
        self.redo.clear()
        return True

    @staticmethod
    def _apply(entry, which):
        for i, f in entry["files"].items():
            items, ver = entry[which][i]
            f.items = {k: v.clone() for k, v in items.items()}
            f.version = ver

    def do_undo(self):
        self.commit()
        if not self.undo:
            return None
        e = self.undo.pop()
        self._apply(e, "before")
        self.redo.append(e)
        return e

    def do_redo(self):
        if not self.redo:
            return None
        e = self.redo.pop()
        self._apply(e, "after")
        self.undo.append(e)
        return e

    def clear(self):
        self.undo.clear()
        self.redo.clear()
        self.pending = None
