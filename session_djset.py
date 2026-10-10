"""Session-Teil „DJ-Set“ (#3): Titel aus dem Tagger sammeln, Reihenfolge bewerten und optimieren.

Das Set merkt sich die Dateipfade (cfg „djset_items“) und löst sie bei jedem Abruf gegen die aktuell im
Tagger geladenen Dateien auf – so bleiben Wiedergabe (Player kind „tag“) und Bearbeitung beim Tagger.
Nicht geladene Titel bleiben im Set, werden aber grau angezeigt und nicht mit optimiert.
"""
from __future__ import annotations

import os

import time

import core
from id3tags import MV
import setexport
import setplan

# Optionen der Seite → Typ und Grenzen
DJ_OPTS = {"w_key": (float, 0, 1, 0.5), "w_bpm": (float, 0, 1, 0.3), "w_energy": (float, 0, 1, 0.2),
           "max_jump": (float, 1, 30, 8.0), "profile": (str, None, None, "none"), "missing": (str, None, None, "end")}


def _nk(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


class DjSetMixin:
    # ------------------------------------------------------------------ Zustand
    def _dj(self) -> dict:
        d = getattr(self, "_djstate", None)
        if d is None:
            items = self.cfg.get("djset_items")
            items = [x for x in items if isinstance(x, dict) and isinstance(x.get("path"), str)] if isinstance(items, list) else []
            d = self._djstate = {"items": [{"path": x["path"], "lock": bool(x.get("lock"))} for x in items],
                                 "prev": None, "before": None, "method": "", "ms": 0}
        return d

    def _dj_opts(self) -> dict:
        raw = self.cfg.get("djset_opts") if isinstance(self.cfg.get("djset_opts"), dict) else {}
        out = {}
        for k, (typ, lo, hi, dflt) in DJ_OPTS.items():
            v = raw.get(k, dflt)
            try:
                v = typ(v)
            except (TypeError, ValueError):
                v = dflt
            if typ is float:
                v = max(lo, min(hi, v))
            out[k] = v
        if out["profile"] not in setplan.PROFILES:
            out["profile"] = "none"
        if out["missing"] not in ("end", "neutral"):
            out["missing"] = "end"
        return out

    def _dj_save(self):
        items = [{"path": x["path"], **({"lock": True} if x["lock"] else {})} for x in self._dj()["items"]]
        self.cfg["djset_items"] = items
        core.save_config({"djset_items": items})

    def _dj_index(self) -> dict:
        return {_nk(f.path): i for i, f in enumerate(self.tag_files)}

    def _dj_tracks(self):
        """[(Item, Tagger-Index oder None, Track)] in Set-Reihenfolge."""
        where = self._dj_index()
        out = []
        for it in self._dj()["items"]:
            i = where.get(_nk(it["path"]))
            if i is None:
                t = setplan.Track(id=it["path"], title=os.path.basename(it["path"]))
            else:
                t = setplan.track_from_file(self.tag_files[i], tid=it["path"])
            out.append((it, i, t))
        return out

    def _dj_options(self, rows) -> setplan.Options:
        o = setplan.Options.from_dict(self._dj_opts())
        o.locks = {p: it["path"] for p, (it, i, _t) in enumerate(rows) if it["lock"] and i is not None}
        return o

    # ------------------------------------------------------------------ Abruf
    def dj_state(self) -> dict:
        with self.lock:
            d = self._dj()
            rows = self._dj_tracks()
            opts = self._dj_opts()
            live = [t for (_it, i, t) in rows if i is not None]
            ev = setplan.evaluate(live, self._dj_options(rows)) if live else {"score": None, "transitions": [], "energy_fit": None, "curve": None}
            trs = iter(ev["transitions"])
            items, n_live = [], 0
            for it, i, t in rows:
                e, est = setplan.energy_of(t)
                row = {"path": it["path"], "i": i, "lock": it["lock"], "missing": i is None,
                       "name": os.path.basename(it["path"]), "title": t.title, "key": t.key,
                       "bpm": t.bpm, "energy": e, "energy_est": est, "duration": t.duration or 0}
                if i is not None:
                    row["pos"] = n_live
                    row["to_next"] = next(trs, None) if n_live < len(live) - 1 else None
                    if ev["curve"]:
                        row["target"] = round(ev["curve"][n_live])
                    n_live += 1
                items.append(row)
            return {"items": items, "opts": opts, "score": ev["score"], "energy_fit": ev["energy_fit"],
                    "before": d["before"], "method": d["method"], "ms": d["ms"], "can_revert": d["prev"] is not None,
                    "profiles": setplan.PROFILES, "key_kinds": setplan.KEY_KINDS, "exact_max": setplan.EXACT_MAX,
                    "tagger": len(self.tag_files), "duration": sum(r["duration"] for r in items if not r["missing"])}

    # ------------------------------------------------------------------ Ändern
    def dj_add(self, idx=None) -> dict:
        """Titel aus dem Tagger hinzufügen (idx = Liste der Indizes, None = alle). Doppelte und Spuren übersprungen."""
        with self.lock:
            d = self._dj()
            have = {_nk(x["path"]) for x in d["items"]}
            src = range(len(self.tag_files)) if idx is None else idx
            added = 0
            for i in src:
                if not isinstance(i, int) or not 0 <= i < len(self.tag_files) or i in self.tag_parent:
                    continue
                p = self.tag_files[i].path
                if _nk(p) in have:
                    continue
                have.add(_nk(p))
                d["items"].append({"path": p, "lock": False})
                added += 1
            if added:
                d["prev"] = None
                d["before"] = None
                self._dj_save()
            st = self.dj_state()
            st["message"] = f"{added} Titel hinzugefügt." if added else "Keine neuen Titel (schon im Set)."
            return st

    def dj_remove(self, paths) -> dict:
        with self.lock:
            d = self._dj()
            drop = {_nk(p) for p in (paths or [])}
            d["items"] = [x for x in d["items"] if _nk(x["path"]) not in drop]
            d["prev"] = d["before"] = None
            self._dj_save()
            return self.dj_state()

    def dj_clear(self, missing_only=False) -> dict:
        with self.lock:
            d = self._dj()
            if missing_only:
                where = self._dj_index()
                d["items"] = [x for x in d["items"] if _nk(x["path"]) in where]
            else:
                d["items"] = []
            d["prev"] = d["before"] = None
            self._dj_save()
            return self.dj_state()

    def dj_order(self, paths) -> dict:
        """Neue Reihenfolge (z. B. nach Ziehen). Unbekannte Pfade werden ignoriert, fehlende hinten angehängt."""
        with self.lock:
            d = self._dj()
            by = {_nk(x["path"]): x for x in d["items"]}
            new, seen = [], set()
            for p in paths or []:
                k = _nk(p)
                if k in by and k not in seen:
                    new.append(by[k])
                    seen.add(k)
            new += [x for x in d["items"] if _nk(x["path"]) not in seen]
            d["items"] = new
            self._dj_save()
            return self.dj_state()

    def dj_lock(self, path, on=True) -> dict:
        with self.lock:
            for x in self._dj()["items"]:
                if _nk(x["path"]) == _nk(path):
                    x["lock"] = bool(on)
            self._dj_save()
            return self.dj_state()

    def dj_set_opt(self, key, value) -> dict:
        if key not in DJ_OPTS:
            raise ValueError(f"Unbekannte Option: {key}")
        with self.lock:
            o = {**self._dj_opts(), key: value}
            self.cfg["djset_opts"] = o
            self.cfg["djset_opts"] = self._dj_opts()          # bereinigt
            core.save_config({"djset_opts": self.cfg["djset_opts"]})
            return self.dj_state()

    def dj_optimize(self) -> dict:
        """Reihenfolge der geladenen Titel optimieren; gesperrte bleiben auf ihrer Position, nicht geladene hinten."""
        with self.lock:
            d = self._dj()
            rows = self._dj_tracks()
            live = [(it, t) for (it, i, t) in rows if i is not None]
            gone = [it for (it, i, _t) in rows if i is None]
            if len(live) < 2:
                raise ValueError("Für ein Set mindestens zwei Titel aus dem geladenen Tagger-Ordner hinzufügen.")
            opts = self._dj_options([(it, 0, t) for it, t in live])
            res = setplan.optimize([t for _it, t in live], opts)
            by = {it["path"]: it for it, _t in live}
            d["prev"] = [dict(x) for x in d["items"]]
            d["items"] = [by[p] for p in res["order"]] + gone
            d["before"] = res["before"]["score"]
            d["method"], d["ms"] = res["method"], res["ms"]
            self._dj_save()
            st = self.dj_state()
            rest = len(res["rest"])
            st["message"] = (f"Optimiert ({'exakt' if res['method'] == 'exact' else 'Näherung'}, {res['ms']} ms): "
                             f"Note {res['before']['score']} → {st['score']}"
                             + (f" · {rest} Titel ohne Tonart/BPM ans Ende" if rest else ""))
            return st

    def dj_revert(self) -> dict:
        """Reihenfolge vor der letzten Optimierung wiederherstellen (und zurück)."""
        with self.lock:
            d = self._dj()
            if d["prev"] is None:
                raise ValueError("Keine frühere Reihenfolge vorhanden.")
            d["prev"], d["items"] = [dict(x) for x in d["items"]], d["prev"]
            self._dj_save()
            return self.dj_state()

    def dj_tag_indices(self) -> list:
        """Tagger-Indizes der Set-Titel in Set-Reihenfolge (für Markieren im Tagger, Exporte)."""
        with self.lock:
            return [i for (_it, i, _t) in self._dj_tracks() if i is not None]

    # ------------------------------------------------------------------ Exporte (#4)
    def _dj_entries(self) -> list:
        st = self.dj_state()
        out = []
        for r in st["items"]:
            e = {"path": r["path"], "title": "", "artist": "", "album": "", "genre": "", "key": r["key"],
                 "bpm": r["bpm"], "energy": None if r["energy_est"] else r["energy"], "duration": r["duration"],
                 "to_next": r.get("to_next")}
            if r["i"] is not None:
                f = self.tag_files[r["i"]]
                e.update(title=f.text("TIT2"), artist=f.text("TPE1").replace(MV, ", "),
                         album=f.text("TALB"), genre=f.text("TCON").replace(MV, ", "))
            out.append(e)
        return out

    def dj_export_name(self, fmt) -> str:
        ext = {"m3u8": "m3u8", "xml": "xml", "csv": "csv"}.get(fmt, "txt")
        return f"DJ-Set {time.strftime('%Y-%m-%d')}.{ext}"

    def dj_export_file(self, fmt, dest, opts=None) -> dict:
        from version import VERSION
        opts = opts or {}
        with self.lock:
            entries = self._dj_entries()
            if not entries:
                raise ValueError("Das Set ist leer.")
            name = os.path.splitext(os.path.basename(dest))[0]
            n = setexport.write(fmt, dest, entries, relative=bool(opts.get("relative")), name=name,
                                version=VERSION, notation=opts.get("notation") or "musical", kinds=setplan.KEY_KINDS)
            return {"ok": True, "path": dest, "count": n, "message": f"{n} Titel exportiert: {os.path.basename(dest)}"}

