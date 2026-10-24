"""Session-Teil „Playlists“ (#267–#269): Verwaltung, Titel aus Tagger und DJ-Set, Playlist-Ordner.

Der Speicher (``playlists.Store``) liegt im Datenordner des Profils; der Playlist-Ordner ist ``cfg["playlist_dir"]``,
sonst ``<Basisordner>/03_Playlists``. Archivierte M3U8 wandern in den Archiv-Ordner (``cfg["archive_dir"]``).
Titel werden über ihren Pfad mit dem Tagger verbunden; Angaben nicht geladener Titel liest die Seite direkt aus
der Datei (zwischengespeichert nach Grösse und Änderungszeit).
"""
from __future__ import annotations

import os

import core
import djlibs
import paths
import playlists
import ratings
import setplan
from id3tags import MV

PLAYLIST_DIR = "03_Playlists"
DJ_FOLDER = "DJ-Sets"
META_MAX = 5000                     # Grösse des Zwischenspeichers für Titelangaben


class PlaylistMixin:
    # ------------------------------------------------------------------ Speicher
    def _pl_dirs(self) -> tuple[str, str]:
        d = str(self.cfg.get("playlist_dir") or "")
        if not d and self.cfg.get("base_dir"):
            d = os.path.join(str(self.cfg["base_dir"]), PLAYLIST_DIR)
        return d, str(self.cfg.get("archive_dir") or "")

    def _pls(self) -> playlists.Store:
        mirror, arch = self._pl_dirs()
        st = getattr(self, "_plstore", None)
        if st is None:
            st = self._plstore = playlists.Store(paths.sub("Playlists"), mirror, arch)
            ids = st.migrate_djset(self._dj_saved() if hasattr(self, "_dj_saved") else {})       # #269: einmalig
            cur = self.cfg.get("djset_name") or ""
            if cur in ids and not self.cfg.get("djset_pl"):
                self.cfg["djset_pl"] = ids[cur]
                core.save_config({"djset_pl": ids[cur]})
        else:
            st.mirror, st.archive_dir = mirror, arch
        return st

    def set_playlist_dir(self, path) -> dict:
        p = os.path.abspath(os.path.expanduser(str(path).strip())) if str(path or "").strip() else ""
        self.cfg["playlist_dir"] = p
        core.save_config({"playlist_dir": p})
        with self.lock:
            st = self._pls()
            st.index["written"] = {}                       # neuer Ordner: alle Playlists neu schreiben
            st.save_index()
            st.sync()
        return self.folders_overview()

    # ------------------------------------------------------------------ Titelangaben
    @staticmethod
    def _pl_track(f) -> dict:
        t = setplan.track_from_file(f)
        try:
            rating = ratings.get_rating(f)
        except Exception:  # noqa: BLE001
            rating = 0
        return {"artist": f.text("TPE1").replace(MV, ", "), "title": f.text("TIT2"), "bpm": t.bpm, "key": t.key,
                "dur": round(t.duration or 0), "rating": rating}

    def _pl_info(self, item_paths) -> dict:
        """Pfad-Schlüssel → Angaben (aus dem Tagger, sonst aus der Datei, sonst „fehlt“/„im Archiv“)."""
        from id3tags import MP3File
        where = {playlists.nk(f.path): i for i, f in enumerate(self.tag_files)}
        cache = self.__dict__.setdefault("_pl_meta", {})
        out, gone = {}, []
        for p in item_paths:
            k = playlists.nk(p)
            if k in out:
                continue
            i = where.get(k)
            if i is not None and os.path.isfile(p):
                out[k] = {**self._pl_track(self.tag_files[i]), "i": i}
                continue
            try:
                stt = os.stat(p)
            except OSError:
                out[k] = {"missing": True}
                gone.append(k)
                continue
            sig = (stt.st_size, stt.st_mtime_ns)
            c = cache.get(k)
            if not c or c[0] != sig:
                try:
                    f = MP3File(p)
                    f.load()
                    c = (sig, self._pl_track(f))
                except Exception:  # noqa: BLE001
                    c = (sig, {})
                if len(cache) > META_MAX:
                    cache.clear()
                cache[k] = c
            out[k] = {**c[1], "i": None}
        if gone and self.cfg.get("archive_dir"):                     # aussortierte Titel: „im Archiv“ statt „fehlt“
            import archive
            moved = {playlists.nk(e["src"]): e["dst"] for e in archive.entries(self.cfg["archive_dir"], 100000)
                     if e["in_archive"] and not e["restored"]}
            for k in gone:
                if k in moved:
                    out[k]["archived"] = moved[k]
        return out

    def _pl_items_from_tag(self, idx) -> list:
        out = []
        for i in idx or []:
            if not isinstance(i, int) or not 0 <= i < len(self.tag_files) or i in self.tag_parent:
                continue
            f = self.tag_files[i]
            t = self._pl_track(f)
            try:
                size = os.path.getsize(f.path)
            except OSError:
                size = 0
            out.append({"path": f.path, "artist": t["artist"], "title": t["title"], "dur": t["dur"], "size": size})
        return out

    # ------------------------------------------------------------------ Abruf
    def pl_list(self) -> dict:
        """Kurzliste für Menüs und Auswahldialoge (nur aktive Playlists)."""
        with self.lock:
            st = self._pls()
            return {"playlists": [st.meta(p) for p in st.active()], "recent": st.recent(), "folders": st.folders()}

    def pl_state(self, sel="") -> dict:
        with self.lock:
            st = self._pls()
            act = st.active()
            sel = str(sel or "")
            if not st.exists(sel):
                rec = st.recent()
                sel = rec[0] if rec else (act[0]["id"] if act else "")
            out = {"folders": st.folders(), "playlists": [st.meta(p) for p in act],
                   "archived": [st.meta(p) for p in st.archived()], "recent": st.recent(), "sel": sel,
                   "mirror": st.mirror, "archive": st.archive_dir, "tagger": len(self.tag_files),
                   "can_undo": bool(st.undo_stack), "undo": st.undo_stack[-1]["label"] if st.undo_stack else "",
                   "can_redo": bool(st.redo_stack), "redo": st.redo_stack[-1]["label"] if st.redo_stack else "",
                   "pl": None}
            try:
                out["external"] = len(st.external_changes())
            except OSError:
                out["external"] = 0
            if sel:
                pl = st.get(sel)
                items = pl.get("items") or []
                info = self._pl_info([x["path"] for x in items if x.get("path")])
                count = {}
                for x in items:
                    if x.get("path"):
                        k = playlists.nk(x["path"])
                        count[k] = count.get(k, 0) + 1
                rows, dur, missing, loaded = [], 0, 0, 0
                refs = 0
                for n, x in enumerate(items):
                    k = playlists.nk(x["path"]) if x.get("path") else ""
                    inf = info.get(k, {"missing": True})
                    ref = x.get("ref") or {}
                    if not x.get("path"):
                        refs += 1                                # #271: nur Angabe, keine Datei
                    r = {"k": n, "path": x.get("path", ""), "name": os.path.basename(x.get("path", "")),
                         "dir": os.path.basename(os.path.dirname(x.get("path", ""))),
                         "artist": inf.get("artist") or x.get("artist", "") or ref.get("artist", ""),
                         "title": inf.get("title") or x.get("title", "") or (ref.get("title", "") + (f" ({ref['mix']})" if ref.get("mix") else "")),
                         "ref": not x.get("path"), "url": ref.get("url", ""), "bpm": inf.get("bpm"), "key": inf.get("key"),
                         "dur": inf.get("dur") or x.get("dur") or ref.get("dur") or 0,
                         "rating": inf.get("rating", 0), "i": inf.get("i"), "missing": bool(inf.get("missing")),
                         "in_archive": inf.get("archived", ""), "lock": bool(x.get("lock")), "dup": count.get(k, 0) > 1,
                         "added": x.get("added", 0)}
                    dur += r["dur"]
                    missing += r["missing"]
                    loaded += r["i"] is not None
                    rows.append(r)
                out["pl"] = {**st.meta(pl), "items": rows, "duration": dur, "missing": missing, "loaded": loaded,
                             "refs": refs, "djset": pl["id"] == self.cfg.get("djset_pl")}
            return out

    def pl_tag_indices(self, pid) -> dict:
        """Tagger-Indizes der Titel einer Playlist (Filter „In Playlist“, #268)."""
        with self.lock:
            st = self._pls()
            pl = st.get(pid)
            want = {playlists.nk(x["path"]) for x in pl.get("items") or [] if x.get("path")}
            idx = [i for i, f in enumerate(self.tag_files) if playlists.nk(f.path) in want]
            return {"id": pid, "name": pl["name"], "indices": idx, "count": len(want)}

    def pl_files(self, pid) -> dict:
        """Vorhandene Dateien einer Playlist in ihrer Reihenfolge (ohne Doppelte) – zum Öffnen im Tagger."""
        with self.lock:
            st = self._pls()
            pl = st.get(pid)
            st.touch(pid)
            seen, files, missing = set(), [], 0
            for x in pl.get("items") or []:
                p = x.get("path")
                if not p or playlists.nk(p) in seen:
                    continue
                seen.add(playlists.nk(p))
                if os.path.isfile(p):
                    files.append(p)
                else:
                    missing += 1
            return {"id": pid, "name": pl["name"], "files": files, "missing": missing}

    # ------------------------------------------------------------------ Ändern
    def _pl_after(self, sel, msg="") -> dict:
        st = self.pl_state(sel)
        if msg:
            st["message"] = msg
        return st

    def pl_create(self, name, folder="", idx=None) -> dict:
        """Neue Playlist, optional gleich mit Tagger-Titeln (idx)."""
        with self.lock:
            st = self._pls()
            items = self._pl_items_from_tag(idx) if idx else []
            pl = st.create(name, folder, "manual", items)
            st.touch(pl["id"])
        n = len(items)
        return self._pl_after(pl["id"], f"Playlist „{pl['name']}“ mit {n} Titel(n) angelegt." if n else f"Playlist „{pl['name']}“ angelegt.")

    def pl_rename(self, pid, name) -> dict:
        with self.lock:
            pl = self._pls().rename(pid, name)
            if self.cfg.get("djset_pl") == pid:
                self.cfg["djset_name"] = pl["name"]
                core.save_config({"djset_name": pl["name"]})
        return self._pl_after(pid)

    def pl_move(self, pid, folder) -> dict:
        with self.lock:
            self._pls().move(pid, folder)
        return self._pl_after(pid)

    def pl_meta(self, pid, color="", note="") -> dict:
        with self.lock:
            self._pls().update(pid, "Farbe und Notiz", color=str(color or "")[:16], note=str(note or "")[:2000])
        return self._pl_after(pid)

    def pl_duplicate(self, pid) -> dict:
        with self.lock:
            pl = self._pls().duplicate(pid)
        return self._pl_after(pl["id"], f"Kopie „{pl['name']}“ angelegt.")

    def pl_merge(self, ids, name, folder="") -> dict:
        ids = [i for i in ids or [] if isinstance(i, str)]
        if len(ids) < 2:
            raise ValueError("Bitte mindestens zwei Playlists wählen.")
        with self.lock:
            pl = self._pls().merge(ids, name, folder)
        return self._pl_after(pl["id"], f"Playlist „{pl['name']}“ aus {len(ids)} Playlists angelegt ({len(pl['items'])} Titel).")

    def _pl_add(self, pid, items, dupes) -> dict:
        st = self._pls()
        pl = st.get(pid)
        r = st.add(pid, items, dupes if dupes in ("ask", "add", "skip") else "ask")
        if r["ask"]:
            return {"ask": True, "dupes": r["dupes"], "new": r["new"], "name": pl["name"], "id": pid}
        msg = f"{r['added']} Titel zu „{pl['name']}“ hinzugefügt." if r["added"] else f"Keine neuen Titel für „{pl['name']}“."
        if r["dupes"] and dupes == "skip":
            msg = f"{r['added']} Titel zu „{pl['name']}“ hinzugefügt, {r['dupes']} schon enthaltene übersprungen."
        return {"ask": False, "added": r["added"], "id": pid, "name": pl["name"], "message": msg}

    def pl_add_tag(self, pid, idx, dupes="ask") -> dict:
        """Tagger-Titel anhängen (#268). Bei Doppelten und dupes="ask": nichts ändern, nur melden."""
        with self.lock:
            return self._pl_add(pid, self._pl_items_from_tag(idx), dupes)

    def pl_add_paths(self, pid, item_paths, dupes="ask") -> dict:
        with self.lock:
            return self._pl_add(pid, [p for p in item_paths or [] if isinstance(p, str) and p], dupes)

    def pl_remove(self, pid, indices) -> dict:
        with self.lock:
            n = self._pls().remove(pid, [i for i in indices or [] if isinstance(i, int)])
        return self._pl_after(pid, f"{n} Titel aus der Playlist entfernt (die Dateien bleiben)." if n else "")

    def pl_order(self, pid, perm) -> dict:
        with self.lock:
            self._pls().order(pid, perm)
        return self._pl_after(pid)

    def pl_undo(self, sel="") -> dict:
        with self.lock:
            label = self._pls().undo()
        return self._pl_after(sel, f"Rückgängig: {label}")

    def pl_redo(self, sel="") -> dict:
        with self.lock:
            label = self._pls().redo()
        return self._pl_after(sel, f"Wiederholt: {label}")

    # ------------------------------------------------------------------ Ordner
    def pl_folder_create(self, path) -> dict:
        with self.lock:
            f = self._pls().folder_create(path)
        return self._pl_after("", f"Ordner „{f}“ angelegt.")

    def pl_folder_rename(self, old, new) -> dict:
        with self.lock:
            f = self._pls().folder_rename(old, new)
        return self._pl_after("", f"Ordner umbenannt in „{f}“.")

    def pl_folder_remove(self, path) -> dict:
        with self.lock:
            self._pls().folder_remove(path)
        return self._pl_after("")

    def pl_folder_archive(self, path) -> dict:
        with self.lock:
            n = self._pls().archive_folder(path)
            self._pl_djset_check()
        return self._pl_after("", f"{n} Playlist(s) archiviert.")

    # ------------------------------------------------------------------ Archiv
    def _pl_djset_check(self):
        """Archivierte Playlist ist nicht mehr die Liste des DJ-Sets (das Set selbst bleibt)."""
        pid = self.cfg.get("djset_pl") or ""
        st = self._pls()
        if pid and (not st.exists(pid) or st.get(pid).get("archived")):
            self.cfg["djset_pl"] = self.cfg["djset_name"] = ""
            core.save_config({"djset_pl": "", "djset_name": ""})

    def pl_archive(self, pid) -> dict:
        with self.lock:
            pl = self._pls().archive(pid)
            self._pl_djset_check()
        return self._pl_after("", f"Playlist „{pl['name']}“ archiviert.")

    def pl_restore(self, pid) -> dict:
        with self.lock:
            pl = self._pls().restore(pid)
        return self._pl_after(pid, f"Playlist „{pl['name']}“ zurückgeholt.")

    def pl_delete(self, pid) -> dict:
        with self.lock:
            st = self._pls()
            name = st.get(pid)["name"]
            st.delete(pid)
        return self._pl_after("", f"Playlist „{name}“ endgültig gelöscht.")

    def _pl_archive_restored(self, moved):
        """Allgemeines „Zurückholen“ (Einstellungen › Aussortierte) hat eine Playlist-Datei zurückgeholt."""
        try:
            st = self._pls()
        except Exception:  # noqa: BLE001
            return
        back = {os.path.normcase(m["old"]) for m in moved or []}
        for p in st.archived():
            if p.get("archived_file") and os.path.normcase(p["archived_file"]) in back:
                q = dict(p)
                q.pop("archived", None)
                q.pop("archived_file", None)
                st.index["written"].pop(p["id"], None)
                try:
                    st._check_free(q["name"], q.get("folder", ""), skip=q["id"])
                except ValueError:
                    q["name"] = st.unique_name(q["name"], q.get("folder", ""))
                st._put(q)
        st.save_index()
        st.sync()

    # ------------------------------------------------------------------ Playlist-Ordner: Änderungen von aussen
    def pl_external(self) -> dict:
        with self.lock:
            st = self._pls()
            return {"mirror": st.mirror, "changes": st.external_changes()}

    def pl_external_apply(self, decisions) -> dict:
        """decisions: [{rel, action}] mit action take/keep/archive."""
        done, errors, sel = 0, [], ""
        with self.lock:
            st = self._pls()
            for d in decisions or []:
                if not isinstance(d, dict):
                    continue
                try:
                    r = st.apply_external(str(d.get("rel") or ""), str(d.get("action") or "keep"))
                    sel = r.get("id") or sel
                    done += 1
                except (ValueError, OSError) as ex:
                    errors.append(f"{d.get('rel')}: {ex}")
        out = self._pl_after(sel, f"{done} Änderung(en) erledigt, {len(errors)} Fehler." if errors else f"{done} Änderung(en) erledigt.")
        out["errors"] = errors
        return out

    def pl_reveal_path(self, pid) -> str:
        """Pfad der M3U8 im Playlist-Ordner (bzw. im Archiv) – zum Zeigen im Explorer/Finder."""
        with self.lock:
            st = self._pls()
            pl = st.get(pid)
            p = pl.get("archived_file", "") if pl.get("archived") else st.mirror_path(pid)
            return p if p and os.path.exists(p) else ""

    # ------------------------------------------------------------------ #270: Abspielen ohne Tagger
    def _pl_has_path(self, path) -> bool:
        """Liegt die Datei in einer aktiven Playlist? (Player darf sie dann direkt öffnen – kind „file“.)"""
        if not isinstance(path, str) or not path:
            return False
        k = playlists.nk(path)
        with self.lock:
            return any(playlists.nk(x["path"]) == k for p in self._pls().active() for x in p.get("items") or []
                       if x.get("path"))

    def pl_to_queue(self, pid) -> dict:
        """Im Tagger geladene Titel einer Playlist an die Warteschlange hängen (#270)."""
        with self.lock:
            pl = self._pls().get(pid)
            where = {playlists.nk(f.path): i for i, f in enumerate(self.tag_files)}
            idx = [where[playlists.nk(x["path"])] for x in pl.get("items") or []
                   if x.get("path") and playlists.nk(x["path"]) in where]
        if not idx:
            raise ValueError("Keiner der Titel ist im Tagger geladen – zuerst „Im Tagger öffnen“.")
        return self.pq_add(idx, False)

    # ------------------------------------------------------------------ #270: Vorbereiten › Übernahme
    @staticmethod
    def _pl_pattern(pattern, workflow="") -> str:
        import time
        t = time.localtime()
        out = str(pattern or "")
        for k, v in (("{Jahr}", f"{t.tm_year}"), ("{Monat}", f"{t.tm_mon:02d}"), ("{Tag}", f"{t.tm_mday:02d}"),
                     ("{Workflow}", workflow), ("{year}", f"{t.tm_year}"), ("{month}", f"{t.tm_mon:02d}"),
                     ("{day}", f"{t.tm_mday:02d}")):
            out = out.replace(k, v)
        return out.strip(" /")

    def _pl_prep_add(self, pattern, files, workflow="") -> str:
        """Übernommene Titel in eine Playlist legen (Name mit Platzhaltern, Ordner mit „/“); fehlt sie, wird sie
        angelegt. Schon enthaltene werden übersprungen. → Name der Playlist oder ""."""
        full = self._pl_pattern(pattern, workflow)
        if not full or not files:
            return ""
        folder, _, name = full.rpartition("/")
        with self.lock:
            st = self._pls()
            pl = st.find(name, folder) or st.create(name, folder, "manual")
            st.add(pl["id"], [{"path": p} for p in files], "skip")
            return st.get(pl["id"])["name"]

    # ------------------------------------------------------------------ #271: Bibliothek, Abgleich, Fehlende
    def _pl_lib_roots(self) -> list:
        roots = [self.cfg.get("default_tagger") or ""]
        try:
            roots.append(self._prep_get().get("library") or "")
        except Exception:  # noqa: BLE001
            pass
        if self.cfg.get("base_dir"):
            roots.append(os.path.join(str(self.cfg["base_dir"]), "01_Library"))
        out, seen = [], set()
        for r in roots:
            if r and os.path.isdir(r) and playlists.nk(r) not in seen:
                seen.add(playlists.nk(r))
                out.append(r)
        if not out and self.cfg.get("base_dir") and os.path.isdir(str(self.cfg["base_dir"])):
            out.append(str(self.cfg["base_dir"]))
        return out

    def _pl_index(self, files) -> list:
        out = []
        for f in files:
            try:
                dur = getattr(f, "duration", 0)
                dur = dur() if callable(dur) else dur
            except Exception:  # noqa: BLE001
                dur = 0
            out.append(playlists.lib_entry(f.path, f.text("TPE1").replace(MV, ", "), f.text("TIT2"), f.text("TSRC"),
                                           int(dur or 0)))
        return out

    def _pl_lib_index(self, cancel, progress, roots=None) -> list:
        """Bibliothek einlesen (mit Listen-Cache) – geladene Tagger-Titel zuerst, ohne doppelte."""
        index, seen = [], set()
        for f in list(self.tag_files):
            seen.add(playlists.nk(f.path))
            index += self._pl_index([f])
        for r in roots if roots is not None else self._pl_lib_roots():
            progress(("text", f"Bibliothek lesen: {r}"))
            files, _err = core.load_files(r, True, cancel, progress, registry=None, use_cache=self._list_cache_on())
            index += self._pl_index([f for f in files if playlists.nk(f.path) not in seen])
            seen |= {playlists.nk(f.path) for f in files}
        return index

    def start_pl_match(self, pid):
        """Einträge ohne Datei mit der Bibliothek abgleichen → rows [{k, label, status, path, candidates}]."""
        pl = self._pls().get(pid)
        todo = [(k, x) for k, x in enumerate(pl.get("items") or []) if not x.get("path") and x.get("ref")]
        if not todo:
            return {"ok": False, "error": "Diese Playlist hat keine Einträge ohne Datei."}
        roots = self._pl_lib_roots()
        if not roots and not self.tag_files:
            return {"ok": False, "error": "Keine Bibliothek festgelegt – Einstellungen › Speicherort und Ordner."}

        def job(cancel, progress):
            index = self._pl_lib_index(cancel, progress, roots)
            rows = []
            for k, x in todo:
                r = playlists.match_ref(x["ref"], index)
                ref = x["ref"]
                rows.append({"k": k, "label": " – ".join(v for v in (ref.get("artist"), ref.get("title")) if v)
                             + (f" ({ref['mix']})" if ref.get("mix") else ""), **r})
            return {"ok": True, "rows": rows, "roots": roots, "library": len(index),
                    "sure": sum(r["status"] == "sure" for r in rows), "unclear": sum(r["status"] == "unclear" for r in rows),
                    "missing": sum(r["status"] == "missing" for r in rows)}
        return self._run("pl_match", "Mit der Bibliothek abgleichen", job)

    def start_pl_find_missing(self, pid, folder=""):
        """Fehlende Dateien (verschoben, umbenannt) suchen: gleicher Dateiname in den Bibliotheksordnern bzw. im
        gewählten Ordner, gleiche Grösse bevorzugt → rows [{k, old, candidates, status}]."""
        pl = self._pls().get(pid)
        todo = [(k, x) for k, x in enumerate(pl.get("items") or []) if x.get("path") and not os.path.isfile(x["path"])]
        if not todo:
            return {"ok": False, "error": "In dieser Playlist fehlt keine Datei."}
        roots = [folder] if folder and os.path.isdir(folder) else self._pl_lib_roots()
        if not roots:
            return {"ok": False, "error": "Keine Bibliothek festgelegt – bitte einen Ordner wählen."}

        def job(cancel, progress):
            want = {}
            for k, x in todo:
                want.setdefault(os.path.basename(x["path"]).casefold(), []).append((k, x))
            found = {}
            n = 0
            for r in roots:
                for dp, dns, fns in os.walk(r):
                    if cancel.is_set():
                        break
                    dns[:] = [d for d in dns if not d.startswith(".")]
                    for fn in fns:
                        if fn.casefold() in want:
                            found.setdefault(fn.casefold(), []).append(os.path.join(dp, fn))
                    n += 1
                    if n % 200 == 0:
                        progress(("text", f"Suche … {dp}"))
            rows = []
            for name, lst in want.items():
                cands = found.get(name, [])
                for k, x in lst:
                    same = [c for c in cands if x.get("size") and os.path.getsize(c) == x["size"]]
                    pick = same[0] if len(same) == 1 else (cands[0] if len(cands) == 1 else "")
                    rows.append({"k": k, "old": x["path"], "candidates": cands[:12], "path": pick,
                                 "status": "sure" if pick else ("unclear" if cands else "missing")})
            rows.sort(key=lambda r: r["k"])
            return {"ok": True, "rows": rows, "roots": roots}
        return self._run("pl_find", "Fehlende Dateien suchen", job)

    def pl_relink(self, pid, picks) -> dict:
        """Gewählte Treffer übernehmen (Abgleich bzw. Fehlende suchen) – rückgängig machbar."""
        with self.lock:
            n = self._pls().relink(pid, [p for p in picks or [] if isinstance(p, dict)])
        return self._pl_after(pid, f"{n} Titel verknüpft." if n else "Nichts verknüpft.")

    def _pl_autolink(self, files) -> int:
        """Neu in die Bibliothek übernommene Titel mit Einträgen ohne Datei in allen Playlists verknüpfen (nur sichere
        Treffer)."""
        from id3tags import MP3File
        loaded = []
        for p in files or []:
            try:
                f = MP3File(p)
                f.load()
                loaded.append(f)
            except Exception:  # noqa: BLE001
                pass
        index = self._pl_index(loaded)
        if not index:
            return 0
        n = 0
        with self.lock:
            st = self._pls()
            for pl in st.active():
                picks = []
                for k, x in enumerate(pl.get("items") or []):
                    if not x.get("path") and x.get("ref"):
                        r = playlists.match_ref(x["ref"], index)
                        if r["status"] == "sure":
                            picks.append({"k": k, "path": r["path"]})
                if picks:
                    n += st.relink(pl["id"], picks, "Neue Titel verknüpfen")
        return n

    # ------------------------------------------------------------------ #271: Export, Einkaufsliste, Import
    def _pl_entries(self, pl) -> list:
        items = [x for x in pl.get("items") or [] if x.get("path")]
        info = self._pl_info([x["path"] for x in items])
        out = []
        for x in items:
            inf = info.get(playlists.nk(x["path"]), {})
            out.append({"path": x["path"], "artist": inf.get("artist") or x.get("artist", ""),
                        "title": inf.get("title") or x.get("title", ""), "album": "", "genre": "",
                        "key": inf.get("key") or "", "bpm": inf.get("bpm"), "duration": inf.get("dur") or x.get("dur") or 0,
                        "rating": inf.get("rating", 0)})
        return out

    def _pl_pick(self, ids=None, folder=None) -> list:
        st = self._pls()
        if folder is not None:
            f = playlists.clean_folder(folder)
            return [p for p in st.active() if not f or p.get("folder", "") == f or p.get("folder", "").startswith(f + "/")]
        return [st.get(i) for i in ids or [] if st.exists(i)]

    def pl_export_name(self, ids=None, fmt="m3u8", folder=None) -> str:
        pls = self._pl_pick(ids, folder)
        base = (folder.split("/")[-1] if folder else (pls[0]["name"] if len(pls) == 1 else "Playlists")) or "Playlists"
        return playlists.safe_part(base) + {"m3u8": ".m3u8", "xml": ".xml", "csv": ".csv"}.get(fmt, ".txt")

    def pl_export_file(self, fmt, dest, ids=None, folder=None, opts=None) -> dict:
        """Export: m3u8 (eine Playlist, absolute oder relative Pfade), xml (Rekordbox, mehrere mit Ordnerbaum),
        csv (eine Playlist, mit BPM, Tonart, Länge)."""
        from version import VERSION
        import tagger
        opts = opts or {}
        with self.lock:
            pls = self._pl_pick(ids, folder)
            if not pls:
                raise ValueError("Keine Playlist gewählt.")
            if fmt == "xml":
                base = playlists.clean_folder(folder) if folder else ""
                groups = []
                for p in pls:
                    f = p.get("folder", "")
                    if base and f.startswith(base):
                        f = (base.split("/")[-1] + f[len(base):]).strip("/")
                    elif not folder:
                        f = f if len(pls) > 1 else ""
                    groups.append({"folder": f, "name": p["name"], "entries": self._pl_entries(p)})
                text = playlists.rekordbox_tree(groups, VERSION, opts.get("notation") or "musical")
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(text)
                n = sum(len(g["entries"]) for g in groups)
                return {"ok": True, "path": dest, "message": f"{len(groups)} Playlist(s) mit {n} Titeln exportiert: {os.path.basename(dest)}"}
            pl = pls[0]
            entries = self._pl_entries(pl)
            if fmt == "m3u8":
                import setexport
                n = setexport.write("m3u8", dest, entries, relative=bool(opts.get("relative")), name=pl["name"])
            elif fmt == "csv":
                rows = [[k + 1, e["artist"], e["title"], e["bpm"] or "", e["key"] or "",
                         core.duration_text(e["duration"]) if e["duration"] else "", e["rating"] or "", e["path"]]
                        for k, e in enumerate(entries)]
                tagger.write_csv(dest, ["Nr", "Künstler", "Titel", "BPM", "Camelot", "Länge", "Bewertung", "Pfad"], rows)
                n = len(rows)
            else:
                raise ValueError(f"Unbekanntes Format: {fmt}")
            return {"ok": True, "path": dest, "message": f"{n} Titel exportiert: {os.path.basename(dest)}"}

    def pl_shopping_file(self, dest, ids=None, folder=None) -> dict:
        """Einkaufsliste: Einträge ohne Datei und fehlende Dateien aller gewählten Playlists als CSV."""
        import tagger
        with self.lock:
            rows = []
            for p in self._pl_pick(ids, folder):
                for x in p.get("items") or []:
                    ref = x.get("ref") or {}
                    if x.get("path") and os.path.isfile(x["path"]):
                        continue
                    rows.append([p["name"], ref.get("artist") or x.get("artist", ""), ref.get("title") or x.get("title", ""),
                                 ref.get("mix", ""), ref.get("isrc", ""), x.get("path", ""),
                                 "Datei fehlt" if x.get("path") else "nicht in der Bibliothek", ref.get("url", "")])
            if not rows:
                raise ValueError("Es fehlen keine Titel.")
            tagger.write_csv(dest, ["Playlist", "Künstler", "Titel", "Mix", "ISRC", "Pfad", "Status", "Link"], rows)
            return {"ok": True, "path": dest, "message": f"Einkaufsliste mit {len(rows)} Titel(n) gespeichert: {os.path.basename(dest)}"}

    def pl_import_file(self, path, folder="") -> dict:
        """M3U/M3U8, Rekordbox-XML oder CSV als Playlist(s) übernehmen (Ordner im Baum: folder)."""
        path = str(path or "")
        if not os.path.isfile(path):
            raise ValueError("Datei nicht gefunden.")
        ext = os.path.splitext(path)[1].lower()
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            text = fh.read()
        base = os.path.dirname(path)
        stem = os.path.splitext(os.path.basename(path))[0]
        folder = playlists.clean_folder(folder)
        if ext in (".m3u", ".m3u8"):
            groups = [{"folder": folder, "name": stem, "items": [
                {"path": e["path"], "dur": e["dur"], **playlists.Store._split_label(e["label"])} for e in playlists.parse_m3u(text, base)]}]
        elif ext == ".xml":
            try:
                tree = playlists.read_rekordbox_tree(text)
            except Exception as ex:  # noqa: BLE001
                raise ValueError(f"Kein gültiges Rekordbox-XML: {ex}") from ex
            groups = [{"folder": "/".join(x for x in (folder, g["folder"]) if x), "name": g["name"],
                       "items": [{"path": p} for p in g["paths"]]} for g in tree]
        elif ext in (".csv", ".txt"):
            groups = [{"folder": folder, "name": stem, "items": playlists.parse_csv(text, base)}]
        else:
            raise ValueError("Unbekanntes Format – M3U, M3U8, Rekordbox-XML oder CSV.")
        groups = [g for g in groups if g["items"]]
        if not groups:
            raise ValueError("Die Datei enthält keine Titel.")
        first, n, refs, gone = "", 0, 0, 0
        with self.lock:
            st = self._pls()
            for g in groups:
                pl = st.create(st.unique_name(g["name"], g["folder"]), g["folder"], "import", g["items"],
                               source={"plugin": "file", "id": path})
                first = first or pl["id"]
                n += len(pl["items"])
                refs += sum(1 for x in pl["items"] if not x.get("path"))
                gone += sum(1 for x in pl["items"] if x.get("path") and not os.path.isfile(x["path"]))
                st.touch(pl["id"])
        msg = f"{len(groups)} Playlist(s) mit {n} Titeln übernommen."
        if refs:
            msg += f" {refs} ohne Datei – „Mit Bibliothek abgleichen …“ sucht sie."
        if gone:
            msg += f" {gone} Datei(en) fehlen – „Fehlende suchen …“."
        return self._pl_after(first, msg)

    # ------------------------------------------------------------------ DJ-Programme (#278, nur lesen)
    def pl_dj_libraries(self, app) -> dict:
        """Gefundene Bibliotheken von Serato, Engine DJ bzw. VirtualDJ (Standardorte und externe Laufwerke)."""
        if app not in djlibs.APPS:
            raise ValueError("Unbekanntes Programm.")
        return {"app": app, "name": djlibs.APPS[app], "found": djlibs.find_libraries(app)}

    def start_pl_dj_scan(self, app, path):
        """Playlists einer Bibliothek auflisten → {lists: [{key, folder, name, count, missing}]}"""
        if app not in djlibs.APPS:
            return {"ok": False, "error": "Unbekanntes Programm."}

        def job(cancel, progress):
            progress(("text", f"{djlibs.APPS[app]}: Playlists lesen …"))
            try:
                lists = djlibs.read_library(app, path)
            except (ValueError, OSError) as ex:
                return {"ok": False, "error": str(ex)}
            except Exception as ex:  # noqa: BLE001 – kaputte Datenbank o. Ä.
                return {"ok": False, "error": f"{djlibs.APPS[app]}: Bibliothek nicht lesbar ({ex})."}
            st = self._pls()
            out = []
            for g in lists:
                miss = sum(1 for x in g["items"] if not os.path.isfile(x["path"]))
                out.append({"key": g["key"], "folder": g["folder"], "name": g["name"], "count": len(g["items"]),
                            "missing": miss, "known": bool(st.find_source("app:" + app, g["key"]))})
            return {"ok": True, "app": app, "name": djlibs.APPS[app], "path": djlibs.library_root(app, path), "lists": out}
        return self._run("pl_dj", f"{djlibs.APPS[app]}: Playlists lesen", job)

    def start_pl_dj_import(self, app, path, keys):
        """Gewählte Playlists in den Ordner „<Programm>/…“ übernehmen; schon übernommene werden aktualisiert."""
        keys = {str(k) for k in (keys or []) if isinstance(k, (str, int))}
        if app not in djlibs.APPS:
            return {"ok": False, "error": "Unbekanntes Programm."}
        if not keys:
            return {"ok": False, "error": "Bitte mindestens eine Playlist wählen."}
        name = djlibs.APPS[app]

        def job(cancel, progress):
            progress(("text", f"{name}: Playlists lesen …"))
            try:
                lists = [g for g in djlibs.read_library(app, path) if g["key"] in keys]
            except Exception as ex:  # noqa: BLE001
                return {"ok": False, "error": str(ex)}
            out, missing = [], 0
            for k, g in enumerate(lists):
                if cancel.is_set():
                    break
                progress(("progress", k, len(lists), g["name"]))
                folder = playlists.clean_folder("/".join(x for x in (name, g["folder"]) if x))
                items = [{kk: v for kk, v in x.items() if v} for x in g["items"]]
                src = {"plugin": "app:" + app, "id": g["key"]}
                with self.lock:
                    st = self._pls()
                    pl = st.find_source(src["plugin"], g["key"])
                    if pl is None:
                        pl = st.create(st.unique_name(g["name"], folder), folder, "import", items, source=src)
                    else:
                        pl = st.update(pl["id"], "Playlist aktualisieren", items=items, source=src)
                    st.touch(pl["id"])
                miss = sum(1 for x in items if not os.path.isfile(x["path"]))
                missing += miss
                out.append({"id": pl["id"], "name": pl["name"], "count": len(items), "missing": miss})
            return {"ok": True, "lists": out, "missing": missing}
        return self._run("pl_dj", f"{name}: Playlists übernehmen", job)

    # ------------------------------------------------------------------ Trackliste als Text (#279)
    def pl_import_text(self, text, name="", folder="", source="text") -> dict:
        """Kopierte Trackliste (1001Tracklists, MixID, Beatport …) als Playlist mit Einträgen ohne Datei."""
        source = str(source or "text")[:40]
        items, unknown = playlists.parse_tracklist(text, source)
        if not items:
            raise ValueError("Keine Titel erkannt – je Zeile „Künstler - Titel“.")
        folder = playlists.clean_folder(folder)
        with self.lock:
            st = self._pls()
            pl = st.create(st.unique_name(name or "Trackliste", folder), folder, "import", items)
            st.touch(pl["id"])
        msg = f"{len(items)} Einträge übernommen – „Mit Bibliothek abgleichen …“ sucht die Dateien."
        if unknown:
            msg += f" {unknown} unbekannte (ID) ausgelassen."
        return self._pl_after(pl["id"], msg)

    def start_pl_source_import(self, pid, ids):
        """Playlists aus einem Plugin (z. B. Lexicon) nur als Playlists übernehmen – ohne sie ins DJ-Set zu laden."""
        return self.start_dj_source_import(pid, ids, load=False)

