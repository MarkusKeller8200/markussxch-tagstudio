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
                    "tagger": len(self.tag_files), "duration": sum(r["duration"] for r in items if not r["missing"]),
                    "name": self.cfg.get("djset_name") or "", "lists": self.dj_lists(), "dirty": self._dj_dirty()}

    def _dj_dirty(self) -> bool:
        """Weicht das aktuelle Set von der gleichnamigen gespeicherten Liste ab?"""
        name = self.cfg.get("djset_name") or ""
        v = self._dj_saved().get(name) if name else None
        if v is None:
            return bool(self._dj()["items"])
        a = [(x["path"], bool(x["lock"])) for x in self._dj()["items"]]
        b = [(x.get("path"), bool(x.get("lock"))) for x in v.get("items") or [] if isinstance(x, dict)]
        return a != b

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

    # ------------------------------------------------------------------ #242: Playlists aus Plugins (z. B. Lexicon)
    def dj_sources(self) -> dict:
        return {"sources": self.plugins.playlist_sources()}

    def start_dj_source_list(self, pid):
        """Alle Playlists eines Plugins holen (zur Auswahl mit Häkchen)."""
        def job(cancel, progress):
            progress(("text", "Playlists werden geholt …"))
            return {"ok": True, "playlists": self.plugins.call_playlist(pid, "playlists", session=self, cancel=cancel,
                                                                        progress=progress)}
        return self._run("dj_source", "Playlists holen", job)

    def start_dj_source_import(self, pid, ids, prefix=""):
        """Gewählte Playlists als gespeicherte Listen „<Quelle>: <Name>“ ablegen (gleichnamige werden ersetzt);
        die erste wird geladen. → {lists, first, files (der ersten), missing}"""
        ids = [i for i in (ids or []) if isinstance(i, (str, int))]
        if not ids:
            return {"ok": False, "error": "Bitte mindestens eine Playlist wählen."}
        src = self.plugins.get(pid).name

        def job(cancel, progress):
            out, missing = [], 0
            for k, i in enumerate(ids):
                if cancel.is_set():
                    break
                progress(("progress", k, len(ids), str(i)))
                r = self.plugins.call_playlist(pid, "playlist_files", i, session=self, cancel=cancel, progress=progress)
                name = " ".join(f"{prefix or src}: {r['name']}".split())[:80]
                with self.lock:
                    saved = self._dj_saved()
                    saved[name] = {"items": [{"path": p} for p in r["files"]], "opts": self._dj_opts(),
                                   "saved": int(time.time()), "source": pid}
                    self._dj_saved_write(saved)
                missing += r.get("missing", 0)
                out.append({"name": name, "count": len(r["files"]), "missing": r.get("missing", 0), "files": r["files"]})
            first = out[0] if out else None
            if first:
                self.dj_load(first["name"])
            return {"ok": True, "lists": [{k: v for k, v in x.items() if k != "files"} for x in out],
                    "first": first["name"] if first else "", "files": first["files"] if first else [], "missing": missing}
        return self._run("dj_source", "Playlists laden", job)

    def dj_add_paths(self, paths, new=False, name="") -> dict:
        """#238: Titel über ihre Pfade hinzufügen (Reihenfolge bleibt), z. B. aus einer Lexicon-Playlist.
        new=True: zuerst ein neues, leeres Set (das bisherige lässt sich mit „Rückgängig“ zurückholen)."""
        with self.lock:
            d = self._dj()
            if new:
                d["prev"] = [dict(x) for x in d["items"]]
                d["items"], d["before"] = [], None
                self.cfg["djset_name"] = ""
                core.save_config({"djset_name": ""})
            have = {_nk(x["path"]) for x in d["items"]}
            added = 0
            for p in paths or []:
                if not isinstance(p, str) or not p or _nk(p) in have:
                    continue
                have.add(_nk(p))
                d["items"].append({"path": p, "lock": False})
                added += 1
            if added and not new:
                d["prev"] = None
                d["before"] = None
            self._dj_save()
            st = self.dj_state()
            st["message"] = (f"{added} Titel" + (f" aus „{name}“" if name else "") + " ins DJ-Set übernommen.") if added \
                else "Keine neuen Titel (schon im Set)."
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

    # ------------------------------------------------------------------ Gespeicherte Listen (#138)
    def _dj_saved(self) -> dict:
        raw = self.cfg.get("djset_saved")
        return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, dict)} if isinstance(raw, dict) else {}

    def _dj_saved_write(self, saved: dict):
        self.cfg["djset_saved"] = saved
        core.save_config({"djset_saved": saved})

    def dj_lists(self) -> list:
        """Gespeicherte Listen: [{name, count, saved, current}] nach Name."""
        cur = self.cfg.get("djset_name") or ""
        return [{"name": n, "count": len(v.get("items") or []), "saved": v.get("saved", 0), "current": n == cur}
                for n, v in sorted(self._dj_saved().items(), key=lambda kv: kv[0].lower())]

    def dj_save_as(self, name, overwrite=False) -> dict:
        """Aktuelles Set (Titel, Sperren, Optionen) unter einem Namen speichern."""
        name = " ".join(str(name or "").split())[:80]
        if not name:
            raise ValueError("Bitte einen Namen für die Liste eingeben.")
        with self.lock:
            saved = self._dj_saved()
            if name in saved and not overwrite and name != (self.cfg.get("djset_name") or ""):
                return {"ok": False, "exists": True, "error": f"Eine Liste „{name}“ gibt es schon."}
            items = [{"path": x["path"], **({"lock": True} if x["lock"] else {})} for x in self._dj()["items"]]
            saved[name] = {"items": items, "opts": self._dj_opts(), "saved": int(time.time())}
            self._dj_saved_write(saved)
            self.cfg["djset_name"] = name
            core.save_config({"djset_name": name})
            st = self.dj_state()
            st["ok"] = True
            st["message"] = f"Liste „{name}“ gespeichert ({len(items)} Titel)."
            return st

    def dj_load(self, name) -> dict:
        """Gespeicherte Liste laden (ersetzt das aktuelle Set; „Rückgängig“ holt das vorige zurück)."""
        with self.lock:
            v = self._dj_saved().get(name)
            if v is None:
                raise ValueError(f"Liste „{name}“ nicht gefunden.")
            d = self._dj()
            d["prev"] = [dict(x) for x in d["items"]]
            d["items"] = [{"path": x["path"], "lock": bool(x.get("lock"))} for x in v.get("items") or []
                          if isinstance(x, dict) and isinstance(x.get("path"), str)]
            d["before"] = None
            if isinstance(v.get("opts"), dict):
                self.cfg["djset_opts"] = v["opts"]
                self.cfg["djset_opts"] = self._dj_opts()
                core.save_config({"djset_opts": self.cfg["djset_opts"]})
            self.cfg["djset_name"] = name
            core.save_config({"djset_name": name})
            self._dj_save()
            st = self.dj_state()
            st["message"] = f"Liste „{name}“ geladen ({len(d['items'])} Titel)."
            return st

    def dj_new(self) -> dict:
        """Neues, leeres Set (das bisherige bleibt als gespeicherte Liste erhalten, falls gespeichert)."""
        with self.lock:
            d = self._dj()
            d["prev"] = [dict(x) for x in d["items"]]
            d["items"], d["before"] = [], None
            self.cfg["djset_name"] = ""
            core.save_config({"djset_name": ""})
            self._dj_save()
            return self.dj_state()

    def dj_list_delete(self, name) -> dict:
        """Gespeicherte Liste entfernen (das aktuelle Set bleibt unverändert). Die Oberfläche fragt vorher."""
        with self.lock:
            saved = self._dj_saved()
            if saved.pop(name, None) is None:
                raise ValueError(f"Liste „{name}“ nicht gefunden.")
            self._dj_saved_write(saved)
            if self.cfg.get("djset_name") == name:
                self.cfg["djset_name"] = ""
                core.save_config({"djset_name": ""})
            st = self.dj_state()
            st["message"] = f"Liste „{name}“ entfernt."
            return st

    def dj_list_rename(self, name, new) -> dict:
        new = " ".join(str(new or "").split())[:80]
        with self.lock:
            saved = self._dj_saved()
            if name not in saved:
                raise ValueError(f"Liste „{name}“ nicht gefunden.")
            if not new or (new in saved and new != name):
                raise ValueError("Bitte einen neuen, noch nicht vergebenen Namen eingeben.")
            saved = {(new if k == name else k): v for k, v in saved.items()}
            self._dj_saved_write(saved)
            if self.cfg.get("djset_name") == name:
                self.cfg["djset_name"] = new
                core.save_config({"djset_name": new})
            return self.dj_state()

    # ------------------------------------------------------------------ Warteschlange des Players (#138)
    def _pq(self) -> list:
        q = self.cfg.get("player_queue")
        return [p for p in q if isinstance(p, str)] if isinstance(q, list) else []

    def _pq_write(self, q):
        self.cfg["player_queue"] = q
        core.save_config({"player_queue": q})

    def pq_state(self) -> dict:
        """Warteschlange: [{path, i (Tagger-Index oder None), name, title, artist}]"""
        with self.lock:
            where = self._dj_index()
            items = []
            for p in self._pq():
                i = where.get(_nk(p))
                f = self.tag_files[i] if i is not None else None
                items.append({"path": p, "i": i, "name": os.path.basename(p),
                              "title": f.text("TIT2") if f else "", "artist": f.text("TPE1").replace(MV, ", ") if f else ""})
            return {"items": items}

    def pq_add(self, idx, front=False) -> dict:
        """Tagger-Titel anhängen bzw. (front) als Nächstes einreihen; schon vorhandene werden verschoben."""
        with self.lock:
            paths = [self.tag_files[i].path for i in (idx or []) if isinstance(i, int) and 0 <= i < len(self.tag_files)
                     and i not in self.tag_parent]
            keys = {_nk(p) for p in paths}
            rest = [p for p in self._pq() if _nk(p) not in keys]
            self._pq_write(paths + rest if front else rest + paths)
        st = self.pq_state()
        n = len(paths)
        st["message"] = (f"{n} Titel als Nächstes eingereiht." if front else f"{n} Titel zur Warteschlange hinzugefügt.") if n else "Keine Titel gewählt."
        return st

    def pq_set(self, paths) -> dict:
        """Neue Reihenfolge bzw. Titel entfernen (nur bekannte Pfade)."""
        with self.lock:
            have = {_nk(p): p for p in self._pq()}
            out, seen = [], set()
            for p in paths or []:
                k = _nk(p) if isinstance(p, str) else None
                if k in have and k not in seen:
                    out.append(have[k])
                    seen.add(k)
            self._pq_write(out)
        return self.pq_state()

    def pq_take(self, i) -> dict:
        """Titel i wird gespielt → aus der Warteschlange nehmen."""
        with self.lock:
            if not isinstance(i, int) or not 0 <= i < len(self.tag_files):
                return self.pq_state()
            k = _nk(self.tag_files[i].path)
            q = self._pq()
            if any(_nk(p) == k for p in q):
                self._pq_write([p for p in q if _nk(p) != k])
        return self.pq_state()

    def pq_to_djset(self) -> dict:
        """Warteschlange als neues DJ-Set übernehmen (bisheriges Set über „Vorher/Nachher“ zurückholbar)."""
        with self.lock:
            d = self._dj()
            d["prev"] = [dict(x) for x in d["items"]]
            d["items"] = [{"path": p, "lock": False} for p in self._pq()]
            d["before"] = None
            self.cfg["djset_name"] = ""
            core.save_config({"djset_name": ""})
            self._dj_save()
            st = self.dj_state()
            st["message"] = f"{len(d['items'])} Titel als DJ-Set übernommen."
            return st

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
        name = "".join(c for c in (self.cfg.get("djset_name") or "") if c not in '<>:"/\\|?*').strip()
        return f"{name}.{ext}" if name else f"DJ-Set {time.strftime('%Y-%m-%d')}.{ext}"

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

