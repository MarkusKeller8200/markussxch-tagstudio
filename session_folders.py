"""Session-Teil „Ordner-Rollen“ (#310, docs/KONZEPT-ORDNER.md): Einstellungen › Ordner.

Das Modell liegt in ``cfg["folders"]`` (siehe :mod:`folders`). Beim ersten Zugriff werden die heutigen Einzel-
Einstellungen übernommen; gibt es mehrere verschiedene Bibliotheks-Ordner, bleibt eine Übersicht zur Entscheidung
offen (``folders_review``). Nach jeder Änderung werden die alten Schlüssel nachgeführt – nur die, deren Wert sich durch
die Änderung tatsächlich verschiebt – und Workflows, die auf den bisherigen Ordner zeigten, folgen.
Hier wird nur die Einstellung geändert; Dateien bleiben, wo sie sind (Verschieben/Kopieren: #313)."""
from __future__ import annotations

import os

import core
import folders


class FolderRolesMixin:
    """Teil der Klasse Session – nutzt self.cfg, self._prep_workflows, self.snap_store, self._snap_dir_set."""

    # ------------------------------------------------------------------ Modell lesen / speichern
    def _folders(self) -> dict:
        if not isinstance(self.cfg.get("folders"), dict):
            m = self._folders_migrate()
            self.cfg["folders"] = m
            core.save_config({"folders": m})
        return folders.normalize(self.cfg["folders"])

    def _folders_migrate(self) -> dict:
        try:
            snap_libs = self.snap_store.libraries() if os.path.isdir(self.snap_store.root) else []
        except Exception:  # noqa: BLE001 – unlesbarer Speicher: ohne Snapshot-Bibliotheken übernehmen
            snap_libs = []
        bp = ((self.cfg.get("plugin_options") or {}).get("beatport") or {}).get("download") or {}
        return folders.migrate(self.cfg, self.cfg.get("prep_workflows") or [], self.cfg.get("prep_current"),
                               snap_libs, str(bp.get("dest") or ""))

    def _folders_save(self, new: dict, follow: bool = True) -> dict:
        """Modell speichern, alte Schlüssel und verweisende Einstellungen nachführen (nur geänderte Werte)."""
        old = self._folders()
        new = folders.normalize(new)
        self.cfg["folders"] = new
        upd = {"folders": new}
        if follow:
            lo, ln = folders.legacy(old), folders.legacy(new)
            for k, v in ln.items():
                if k == "snap_dir" or lo.get(k) == v:
                    continue
                self.cfg[k] = v
                upd[k] = v
            core.save_config(upd)
            snap = folders.resolve_role(new, "snapshots")
            if lo.get("snap_dir") != ln.get("snap_dir") and snap:
                self._snap_dir_set(snap, note=False)
            self._folders_follow(old, new)
            if folders.resolve_role(old, "playlists") != folders.resolve_role(new, "playlists"):
                try:
                    self._pl_dir_changed()
                except Exception as ex:  # noqa: BLE001 – Playlists werden beim nächsten Speichern geschrieben
                    core._log_warn(f"Playlists nicht neu geschrieben: {ex}")
        else:
            core.save_config(upd)
        return new

    def _folders_follow(self, old: dict, new: dict):
        """Workflows und Download-Ziel, die auf den bisherigen Ordner zeigten, auf den neuen setzen."""
        def main(m):
            return next((folders.resolve_lib(m, x) for x in m["libraries"] if x["main"]), "")

        moves = {"inbox": (folders.resolve_role(old, "inbox"), folders.resolve_role(new, "inbox")),
                 "work": (folders.resolve_role(old, "work"), folders.resolve_role(new, "work")),
                 "library": (main(old), main(new))}
        dl = (folders.resolve_role(old, "downloads"), folders.resolve_role(new, "downloads"))

        def rebase(p, a, b):
            if not p or not a or not b or folders.same_dir(a, b):
                return p
            if folders.same_dir(p, a):
                return b
            if folders.inside(p, a):
                return os.path.join(b, os.path.relpath(os.path.normpath(p), os.path.normpath(a)))
            return p

        ws = self.cfg.get("prep_workflows")
        changed = False
        for w in ws if isinstance(ws, list) else []:
            if not isinstance(w, dict):
                continue
            for k, (a, b) in moves.items():
                p = str(w.get(k) or "")
                q = b if p and folders.same_dir(p, a) and b and not folders.same_dir(a, b) else p
                if q != p:
                    w[k], changed = q, True
            for src in w.get("sources") or []:
                if isinstance(src, dict):
                    q = rebase(str(src.get("folder") or ""), *dl)
                    if q != src.get("folder"):
                        src["folder"], changed = q, True
        upd = {}
        if changed:
            upd["prep_workflows"] = ws
        po = ((self.cfg.get("plugin_options") or {}).get("beatport") or {}).get("download")
        if isinstance(po, dict) and po.get("dest"):
            q = rebase(str(po["dest"]), *dl)
            if q != po["dest"]:
                po["dest"] = q
                upd["plugin_options"] = self.cfg["plugin_options"]
        if upd:
            core.save_config(upd)

    def _folders_note(self, rid: str, path):
        """Ein altes Einstellungsfeld wurde direkt gesetzt (z. B. Snapshots › Speicher verschieben) – Rolle anpassen,
        ohne die alten Schlüssel erneut zu schreiben."""
        if not isinstance(self.cfg.get("folders"), dict):
            return
        m = folders.note_path(self._folders(), rid, path)
        self.cfg["folders"] = m
        core.save_config({"folders": m})

    # ------------------------------------------------------------------ Oberfläche
    def folders_get(self) -> dict:
        import cloud
        cloud.detect(refresh=True)                                     # #315: Seite zeigt den aktuellen Stand
        m = self._folders()
        st = folders.status(m)
        roles = []
        for r in folders.ROLES:
            e = m["roles"][r["id"]]
            roles.append({"id": r["id"], "label": r["label"], "desc": r["desc"], "mode": e["mode"], "sub": e["sub"],
                          "default_sub": r["sub"], "app": bool(r.get("app")), **st["roles"][r["id"]]})
        libs = [{**x, **st["libraries"][x["id"]]} for x in m["libraries"]]
        import cloud
        base = folders._base(m)
        loc = cloud.locate(base) if base else None
        return {"base": base, "base_exists": bool(base) and os.path.isdir(base), "base_cloud": loc["label"] if loc else "",
                "cloud": {"roots": cloud.detect(), "load_online": bool(self.cfg.get("cloud_load_online"))},
                "roles": roles, "libraries": libs, "review": m.get("review") or [],
                "structure": folders.structure(m)}

    def folders_set_base(self, path, create=False) -> dict:
        p = folders.clean_path(path)
        if p and os.path.dirname(p) == p:
            raise ValueError("Bitte einen Ordner wählen (nicht direkt das Laufwerk).")
        if p and create:
            os.makedirs(p, exist_ok=True)
        self._folders_save(folders.set_base(self._folders(), p))
        return self.folders_get()

    def folders_set_role(self, rid, mode, value="") -> dict:
        self._folders_save(folders.set_role(self._folders(), str(rid), str(mode), value))
        return self.folders_get()

    def folders_lib_add(self, name, mode, value="", active=True) -> dict:
        m, lib = folders.lib_add(self._folders(), name, str(mode), value, active)
        self._folders_save(m)
        out = self.folders_get()
        if lib["snapshots"]:
            out["snap_note"] = self._folders_snap_sync(lib["id"])
        return out

    def folders_lib_update(self, lid, changes=None) -> dict:
        c = changes if isinstance(changes, dict) else {}
        m = folders.lib_update(self._folders(), str(lid), name=c.get("name"), mode=c.get("mode"),
                               value=c.get("value"), active=c.get("active"), main=c.get("main"),
                               snapshots=c.get("snapshots"))
        self._folders_save(m)
        note = self._folders_snap_sync(str(lid)) if c.get("snapshots") is not None else ""
        out = self.folders_get()
        if note:
            out["snap_note"] = note
        return out

    # ------------------------------------------------------------------ Snapshots je Bibliothek (O3, #311)
    def _snap_lib_for(self, path):
        """Überwachter Ordner im Snapshot-Speicher, der zu path gehört (oder None)."""
        try:
            for d in self.snap_store.libraries():
                if folders.same_dir(d.get("root", ""), path):
                    return d
        except Exception:  # noqa: BLE001 – Speicher nicht lesbar
            return None
        return None

    def _folders_snap_sync(self, lid: str) -> str:
        """Schalter „Snapshots“ einer Bibliothek in den Snapshot-Speicher übertragen: an = überwachen und täglicher
        Snapshot, aus = kein täglicher Snapshot mehr (vorhandene Snapshots bleiben). → Hinweis für die Oberfläche."""
        import snapshots
        lib = next((x for x in folders.libraries(self.cfg) if x["id"] == lid), None)
        if lib is None or not lib["path"]:
            return ""
        d = self._snap_lib_for(lib["path"])
        try:
            if lib["snapshots"]:
                if d is None:
                    if not os.path.isdir(lib["path"]):
                        return "Ordner fehlt – Snapshots starten, sobald er da ist."
                    d = self.snap_store.add_library(lib["path"], lib["name"])
                self.snap_store.update_library(d["id"], auto=True)
                return "Snapshots eingeschaltet."
            if d is not None:
                self.snap_store.update_library(d["id"], auto=False)
                return "Keine täglichen Snapshots mehr – vorhandene bleiben unter Snapshots."
        except (OSError, snapshots.StoreError) as ex:
            return f"Snapshots: {ex}"
        return ""

    def _folders_main_from_tagger(self, path):
        """Tagger-Standardordner gesetzt (Tagger-Einstellungen, Assistent): Hauptbibliothek ist der Startordner des
        Taggers. Ist der Ordner schon eine Bibliothek, wird sie Hauptbibliothek; sonst kommt er als neue Bibliothek
        dazu (die bisherigen bleiben eingetragen)."""
        m = self._folders()
        lib = next((x for x in m["libraries"] if folders.same_dir(folders.resolve_lib(m, x), path)), None)
        if lib is not None and lib["main"]:
            return
        if lib is None:
            m, lib = folders.lib_add(m, "Haupt" if not m["libraries"] else
                                     (os.path.basename(os.path.normpath(path)) or "Bibliothek"), "custom", path)
        self._folders_save(folders.lib_update(m, lib["id"], main=True))

    # ------------------------------------------------------------------ Ordner ändern mit Inhalt (#313)
    LIB_WARNING = ("Engine DJ, Lexicon, Rekordbox, Serato und VirtualDJ merken sich die Pfade der Titel. Nach dem "
                   "Verschieben dort „Fehlende Dateien suchen“ bzw. „Relocate“ verwenden – TagStudio ändert keine "
                   "fremden Datenbanken.")

    def _change_plan(self, kind, oid, setting) -> tuple[dict, list[dict]]:
        """Neues Modell und betroffene Ordner (alt → neu) für Rolle, Bibliothek oder Basisordner."""
        cur = self._folders()
        st = setting if isinstance(setting, dict) else {}
        items = []
        if kind == "role":
            new = folders.set_role(cur, str(oid), str(st.get("mode") or ""), st.get("value") or "")
            spec = folders._spec(str(oid))
            items.append({"key": "role:" + oid, "role": oid, "label": spec["label"],
                          "old": folders.resolve_role(cur, oid), "new": folders.resolve_role(new, oid)})
        elif kind == "lib":
            new = folders.lib_update(cur, str(oid), name=st.get("name"), mode=st.get("mode"), value=st.get("value"))
            a = next(x for x in cur["libraries"] if x["id"] == oid)
            b = next(x for x in new["libraries"] if x["id"] == oid)
            items.append({"key": "lib:" + oid, "role": "library", "label": f"Bibliothek {b['name']}",
                          "old": folders.resolve_lib(cur, a), "new": folders.resolve_lib(new, b)})
        elif kind == "base":
            new = folders.set_base(cur, st.get("value") or "")
            for r in folders.ROLES:
                if cur["roles"][r["id"]]["mode"] == "base":
                    items.append({"key": "role:" + r["id"], "role": r["id"], "label": r["label"],
                                  "old": folders.resolve_role(cur, r["id"]), "new": folders.resolve_role(new, r["id"])})
            for a in cur["libraries"]:
                if a["mode"] == "base":
                    b = next((x for x in new["libraries"] if x["id"] == a["id"]), a)
                    items.append({"key": "lib:" + a["id"], "role": "library", "label": f"Bibliothek {a['name']}",
                                  "old": folders.resolve_lib(cur, a), "new": folders.resolve_lib(new, b)})
        else:
            raise ValueError("role, lib oder base erwartet")
        items = [x for x in items if x["old"] and x["new"] and not folders.same_dir(x["old"], x["new"])]
        return new, items

    def folders_change_preview(self, kind, oid=None, setting=None) -> dict:
        """Vorschau für „Ändern …“: je betroffenem Ordner Inhalt, Grösse, freier Platz, Konflikte, Standard-Wahl
        (Bibliothek: nicht übernehmen, O4; sonst verschieben)."""
        import foldermove
        _new, items = self._change_plan(kind, oid, setting)
        out = []
        for x in items:
            p = foldermove.plan(x["old"], x["new"])
            if x["role"] == "snapshots" and p["files"] and os.path.isdir(x["new"]) and os.listdir(x["new"]):
                p["error"] = "Snapshots ziehen nur in einen leeren Ordner um (der Speicher wird als Ganzes verschoben)."
            lib = x["role"] == "library"
            out.append({**x, "files": p["files"], "bytes": p["bytes"], "free": p["free"], "same_volume": p["same_volume"],
                        "conflicts": len(p["conflicts"]), "conflict_examples": p["conflicts"][:10], "error": p["error"],
                        "default": "none" if lib or not p["files"] else "move",
                        "warning": self.LIB_WARNING if lib and p["files"] else ""})
        return {"items": out}

    def start_folders_change(self, kind, oid=None, setting=None, choices=None, conflict="keep", relink_copy=False):
        """Ordner ändern: je Ordner verschieben / kopieren / nicht übernehmen (choices: key → move|copy|none), dann
        die Einstellung umstellen und TagStudio-Verweise nachführen. Abbruch: Einstellung bleibt unverändert."""
        import foldermove
        new, items = self._change_plan(kind, oid, setting)
        ch = choices if isinstance(choices, dict) else {}
        conflict = "both" if conflict == "both" else "keep"
        todo = []
        for x in items:
            tr = ch.get(x["key"], "none")
            if tr not in ("move", "copy", "none"):
                tr = "none"
            if tr != "none":
                p = foldermove.plan(x["old"], x["new"])
                if p["error"]:
                    return {"ok": False, "error": f"{x['label']}: {p['error']}"}
                if x["role"] == "snapshots" and p["files"] and os.path.isdir(x["new"]) and os.listdir(x["new"]):
                    return {"ok": False, "error": "Snapshots ziehen nur in einen leeren Ordner um."}
            todo.append((x, tr))
        if any(x["role"] == "snapshots" and tr != "none" for x, tr in todo) and self._jobs is not None and any(
                j["plugin"] == "tagstudio:snapshot" and j["status"] in ("queued", "running") for j in self.jobs.status()["jobs"]):
            return {"ok": False, "error": "Es läuft noch ein Snapshot-Auftrag – bitte warten."}
        jpath = os.path.join(self.export_dir() or __import__("paths").base_dir(), "Ordnerwechsel.csv")

        def job(cancel, progress):
            done = []
            for x, tr in todo:
                if tr == "none":
                    continue
                progress(("text", f"{x['label']}: {'verschieben' if tr == 'move' else 'kopieren'} …"))
                if x["role"] == "snapshots":
                    self._snap_store = None                          # Speicher schliessen
                    if tr == "move":
                        import snapshots
                        with snapshots.writing():
                            res = foldermove.run(x["old"], x["new"], tr, conflict, cancel, progress)
                    else:
                        res = foldermove.run(x["old"], x["new"], tr, conflict, cancel, progress)
                else:
                    res = foldermove.run(x["old"], x["new"], tr, conflict, cancel, progress)
                try:
                    foldermove.journal(jpath, x["label"], res, tr)
                except OSError:
                    pass
                done.append((x, tr, res))
                if res["cancelled"]:
                    break
            cancelled = any(r["cancelled"] for _x, _t, r in done)
            rows = [{"label": x["label"], "old": x["old"], "new": x["new"], "transfer": tr,
                     "files": len(r["moved"]) + r["copied"], "bytes": r["bytes"], "kept": len(r["kept"]),
                     "renamed": len(r["renamed"]), "errors": r["errors"][:50], "cancelled": r["cancelled"]}
                    for x, tr, r in done]
            if cancelled:
                return {"ok": False, "cancelled_move": True, "rows": rows, "journal": jpath,
                        "message": "Abgebrochen – bereits verschobene Dateien liegen vollständig im neuen Ordner, alle "
                                   "anderen unverändert am alten. Die Einstellung wurde nicht geändert."}
            self._folders_save(new)
            relinked = {}
            for x, tr, r in done:
                if tr == "move" or (tr == "copy" and relink_copy):
                    relinked[x["label"]] = self._folders_relink(x["old"], x["new"])
            if any(x["role"] == "snapshots" for x, _t, _r in done):
                try:
                    self.snap_store.refresh_rel()
                except Exception:  # noqa: BLE001
                    pass
            old_dirs = [x["old"] for x, tr, r in done if tr == "move" and os.path.isdir(x["old"])
                        and not any(f for _d, _s, fs in os.walk(x["old"]) for f in fs)]
            tagger = ""
            root = getattr(self, "tag_root", "")
            for x, tr, _r in done:
                if tr == "move" and root and (folders.same_dir(root, x["old"]) or folders.inside(root, x["old"])):
                    tagger = foldermove.rebase(root, x["old"], x["new"])
            return {"ok": True, "rows": rows, "relinked": relinked, "empty_old": old_dirs, "journal": jpath,
                    "tagger_root": tagger,
                    "message": "Ordner geändert." + (f" {sum(r['files'] for r in rows)} Datei(en) übernommen." if rows else "")}
        return self._run("folders_change", "Ordner ändern", job)

    def folders_remove_empty(self, path) -> dict:
        """Nach dem Verschieben: alten, leeren Ordner entfernen – nur auf Rückfrage in der Oberfläche; enthält er noch
        eine Datei, wird nichts gelöscht."""
        import foldermove
        p = folders.clean_path(path)
        if not p or not os.path.isdir(p):
            return {"ok": False, "error": "Ordner nicht gefunden."}
        if any(f for _d, _s, fs in os.walk(p) for f in fs):
            return {"ok": False, "error": "Der Ordner enthält noch Dateien – nichts gelöscht."}
        n = foldermove.remove_empty(p)
        return {"ok": True, "removed": n}

    def _folders_relink(self, old, new) -> dict:
        """TagStudio-Verweise von old auf new umschreiben (nie fremde Datenbanken). → Anzahl je Bereich."""
        import foldermove
        rb = lambda p: foldermove.rebase(p, old, new) if isinstance(p, str) else p  # noqa: E731
        out = {}
        with self.lock:                                                     # Playlists (+ M3U8 neu schreiben)
            try:
                st = self._pls()
                out["playlists"] = st.rebase_paths(rb)
                if out["playlists"]:
                    st.index["written"] = {}
                    st.save_index()
                    st.sync()
            except Exception as ex:  # noqa: BLE001
                out["playlists_error"] = str(ex)
        try:                                                                # Einkäufe
            ps = self._purch()
            n = 0
            for it in ps.data["items"].values():
                for k in ("file",):
                    if isinstance(it.get(k), str) and rb(it[k]) != it[k]:
                        it[k] = rb(it[k])
                        n += 1
                if isinstance(it.get("cands"), list):
                    it["cands"] = [rb(c) for c in it["cands"]]
            if n:
                ps.save()
            out["purchases"] = n
        except Exception as ex:  # noqa: BLE001
            out["purchases_error"] = str(ex)
        try:                                                                # Snapshots: überwachte Ordner
            n = 0
            for d in self.snap_store.libraries():
                r = d.get("root", "")
                if rb(r) != r:
                    self.snap_store.update_library(d["id"], root=rb(r))
                    n += 1
            out["snapshots"] = n
        except Exception as ex:  # noqa: BLE001
            out["snapshots_error"] = str(ex)
        try:                                                                # Archiv-Vermerk
            import archive
            arch = folders.role(self.cfg, "archive")
            out["archive"] = archive.rebase_log(arch, rb) if arch else 0
        except Exception as ex:  # noqa: BLE001
            out["archive_error"] = str(ex)
        upd = {}                                                            # Einstellungen mit Pfaden
        for k in ("hist_tagger", "hist_left", "hist_right", "folder_recent", "player_queue"):
            v = self.cfg.get(k)
            if isinstance(v, list) and any(rb(x) != x for x in v):
                upd[k] = [rb(x) for x in v]
        for k in ("default_left", "default_right", "default_tagger", "help_scan_root", "purch_dest"):
            v = self.cfg.get(k)
            if isinstance(v, str) and rb(v) != v:
                upd[k] = rb(v)
        tsx = self.cfg.get("tagger_state")
        if isinstance(tsx, dict) and isinstance(tsx.get("root"), str) and rb(tsx["root"]) != tsx["root"]:
            upd["tagger_state"] = {**tsx, "root": rb(tsx["root"])}
        pr = self.cfg.get("player_resume")
        if isinstance(pr, dict):
            pr2 = {s: ({**v, "path": rb(v.get("path"))} if isinstance(v, dict) else v) for s, v in pr.items()}
            if pr2 != pr:
                upd["player_resume"] = pr2
        ws = self.cfg.get("prep_workflows")
        if isinstance(ws, list):
            ch = False
            for w in ws:
                if not isinstance(w, dict):
                    continue
                for k in ("inbox", "work", "library"):
                    if isinstance(w.get(k), str) and not w[k].startswith("@") and rb(w[k]) != w[k]:
                        w[k], ch = rb(w[k]), True
                for q in w.get("sources") or []:
                    if isinstance(q, dict) and rb(q.get("folder")) != q.get("folder"):
                        q["folder"], ch = rb(q["folder"]), True
            if ch:
                upd["prep_workflows"] = ws
        po = self.cfg.get("plugin_options")
        if isinstance(po, dict):
            ch = False
            for opts in po.values():
                dl = opts.get("download") if isinstance(opts, dict) else None
                if isinstance(dl, dict) and isinstance(dl.get("dest"), str) and rb(dl["dest"]) != dl["dest"]:
                    dl["dest"], ch = rb(dl["dest"]), True
            if ch:
                upd["plugin_options"] = po
        if upd:
            self.cfg.update(upd)
            core.save_config(upd)
        out["settings"] = len(upd)
        return out

    # ------------------------------------------------------------------ Cloud-Sync-Ordner (#315)
    @staticmethod
    def _cloud_result(stats_list) -> dict:
        """Aus den Einlese-Statistiken: übersprungene Nur-online-Dateien und Konfliktkopien für die Oberfläche."""
        online, conflicts, prov = [], [], ""
        for st in stats_list:
            c = (st or {}).get("cloud") or {}
            online += c.get("online") or []
            conflicts += c.get("conflicts") or []
            prov = prov or c.get("provider") or ""
        return {"cloud": {"provider": prov, "online": len(online), "online_examples": online[:20],
                          "conflicts": conflicts[:200]}} if (online or conflicts) else {}

    def folders_cloud_online(self, on) -> dict:
        """Einstellung „Nur-online-Dateien beim Einlesen herunterladen“."""
        import cloud
        self.cfg["cloud_load_online"] = cloud.LOAD_ONLINE = bool(on)
        core.save_config({"cloud_load_online": bool(on)})
        return self.folders_get()

    # ------------------------------------------------------------------ Ordner-Klappmenü (#314)
    def folders_menu(self) -> dict:
        """Einträge des Klappmenüs bei jeder Ordnerauswahl: Rollen, Bibliotheken, zuletzt benutzt."""
        m = self._folders()
        roles = [{"id": r["id"], "label": r["label"], "path": folders.resolve_role(m, r["id"])} for r in folders.ROLES
                 if r["id"] not in ("backup", "snapshots")]
        libs = [{"id": x["id"], "label": x["name"], "path": folders.resolve_lib(m, x), "main": x["main"]}
                for x in m["libraries"]]
        recent = [p for p in self.cfg.get("folder_recent") or [] if isinstance(p, str) and os.path.isdir(p)]
        return {"roles": [r for r in roles if r["path"]], "libraries": [x for x in libs if x["path"]],
                "recent": recent[:8], "base": m["base"]}

    def folders_recent_add(self, path) -> bool:
        p = folders.clean_path(path)
        if not p or not os.path.isdir(p):
            return False
        self.cfg["folder_recent"] = core.history(self.cfg, "folder_recent", p, 12)
        core.save_config({"folder_recent": self.cfg["folder_recent"]})
        return True

    def folders_mkdir(self, parent, name) -> dict:
        """„Neuer Ordner …“: Ordner name in parent anlegen (vorhandener wird benutzt). → {"path"}"""
        par = folders.clean_path(parent)
        sub = folders.clean_sub(name)
        if not par or not os.path.isdir(par):
            raise ValueError("Elternordner nicht gefunden.")
        if not sub:
            raise ValueError("Bitte einen Namen eingeben.")
        p = os.path.normpath(os.path.join(par, *sub.split("/")))
        os.makedirs(p, exist_ok=True)
        self.folders_recent_add(p)
        return {"path": p}

    # ------------------------------------------------------------------ Unterordner je Quelle (O5, #314)
    MANUAL = "_Manuell"

    def _folders_source_setup(self, name: str, label: str = "", pid: str = "") -> dict:
        """Downloads\\<Quelle> und Eingang\\<Quelle> anlegen (nur wenn nicht vorhanden) und im aktuellen Workflow die
        Quelle eintragen (Download-Unterordner → Eingangs-Unterordner). Nichts wird gelöscht oder verschoben."""
        name = folders.clean_sub(name).replace("/", "")
        if not name:
            return {"created": [], "source": False}
        m = self._folders()
        dl, ib = folders.resolve_role(m, "downloads"), folders.resolve_role(m, "inbox")
        made = []
        for root in (dl, ib):
            p = os.path.join(root, name) if root else ""
            if p and not os.path.isdir(p) and folders.reachable(p):
                try:
                    os.makedirs(p, exist_ok=True)
                    made.append(p)
                except OSError:
                    pass
        added = False
        if dl:
            folder = os.path.join(dl, name)
            self._prep_get()                                   # legt bei Bedarf den Standard-Workflow an
            ws = self._prep_workflows()
            if ws:
                cur = next((w for w in ws if w["id"] == self.cfg.get("prep_current")), ws[0])
                if not any(folders.same_dir(q.get("folder", ""), folder) for q in cur.get("sources") or []):
                    cur.setdefault("sources", []).append({"name": label or name.lstrip("_"), "folder": folder, "pattern": "",
                                                          "sub": name, "zip": True})
                    self._prep_save(ws)
                    added = True
        if dl and pid:                         # Download-Aktion des Plugins: Ziel bisher Downloads selbst → Unterordner
            try:
                has_dl = any(a.get("id") == "download" for a in self.plugins.get(pid).actions())
            except Exception:  # noqa: BLE001
                has_dl = False
            po = self.cfg.setdefault("plugin_options", {}).setdefault(pid, {}).setdefault("download", {}) if has_dl else None
            if isinstance(po, dict) and (not po.get("dest") or folders.same_dir(po["dest"], dl)):
                po["dest"] = os.path.join(dl, name)
                core.save_config({"plugin_options": self.cfg["plugin_options"]})
        return {"created": made, "source": added}

    def _source_dir(self, store: str) -> str:
        """Download-Ordner einer Quelle (Einkäufe/Store-Downloads): Downloads\\<Quelle> – "" ohne Rolle „Downloads“."""
        dl = folders.resolve_role(self._folders(), "downloads")
        if not dl:
            return ""
        try:
            src = self.plugins.get(store).source
        except Exception:  # noqa: BLE001 – unbekanntes Plugin
            src = ""
        return os.path.join(dl, src or self.MANUAL)

    # ------------------------------------------------------------------ Bibliotheken zum Einlesen (#311)
    def _lib_roots(self) -> dict:
        """Aktive, erreichbare Bibliotheken – jeder Ordner nur einmal. → {"roots": [{id, name, path}], "skipped": [...]}"""
        roots, skipped = folders.scan_roots(self._folders())
        return {"roots": roots, "skipped": skipped}

    def folders_lib_remove(self, lid) -> dict:
        """Nur den Eintrag entfernen – die Dateien bleiben (Rückfrage in der Oberfläche)."""
        m = self._folders()
        if any(x["id"] == lid and x["main"] for x in m["libraries"]) and len(m["libraries"]) > 1:
            raise ValueError("Zuerst eine andere Bibliothek als Hauptbibliothek wählen.")
        self._folders_save(folders.lib_remove(m, str(lid)))
        return self.folders_get()

    def folders_create(self, ids=None) -> dict:
        """Fehlende Ordner anlegen (Rollen-IDs bzw. „lib:<id>“; ohne ids: alle aus dem Basisordner)."""
        m = self._folders()
        st = folders.status(m)
        want = set(ids or [])
        made, errors = [], []
        targets = [(r["id"], st["roles"][r["id"]]) for r in folders.ROLES]
        targets += [("lib:" + x["id"], st["libraries"][x["id"]]) for x in m["libraries"]]
        for key, d in targets:
            if want and key not in want:
                continue
            if not want and not (m["base"] and folders.inside(d["path"], m["base"])):
                continue
            if d["path"] and not d["exists"] and d["reachable"]:
                try:
                    os.makedirs(d["path"], exist_ok=True)
                    made.append(d["path"])
                except OSError as ex:
                    errors.append(f"{d['path']}: {ex}")
        out = self.folders_get()
        out.update(created=made, errors=errors)
        return out

    def folders_review_apply(self, decision=None) -> dict:
        """Entscheid zur Übersicht „Diese Ordner haben wir gefunden“."""
        self._folders_save(folders.review_apply(self._folders(), decision if isinstance(decision, dict) else {}))
        return self.folders_get()

    def export_dir(self) -> str:
        """Startordner aller „Exportieren …“ (#312): Rolle „Export“, fehlt er, wird er angelegt (wenn das Laufwerk
        erreichbar ist). "" = keine Rolle festgelegt bzw. nicht anlegbar → Aufrufer nimmt den Benutzerordner."""
        p = folders.resolve_role(self._folders(), "export")
        if p and not os.path.isdir(p) and folders.reachable(p):
            try:
                os.makedirs(p, exist_ok=True)
            except OSError:
                return ""
        return p if p and os.path.isdir(p) else ""

    def folders_adopt(self) -> dict:
        """Nach dem Einrichtungsassistenten („bestehende Ordner wählen“): Rollen aus den gesetzten Einzel-Ordnern
        neu übernehmen."""
        m = self._folders_migrate()
        self.cfg["folders"] = m
        core.save_config({"folders": m})
        return self.folders_get()
