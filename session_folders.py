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
        m = self._folders()
        st = folders.status(m)
        roles = []
        for r in folders.ROLES:
            e = m["roles"][r["id"]]
            roles.append({"id": r["id"], "label": r["label"], "desc": r["desc"], "mode": e["mode"], "sub": e["sub"],
                          "default_sub": r["sub"], "app": bool(r.get("app")), **st["roles"][r["id"]]})
        libs = [{**x, **st["libraries"][x["id"]]} for x in m["libraries"]]
        return {"base": m["base"], "base_exists": bool(m["base"]) and os.path.isdir(m["base"]),
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
        """Download-Ordner einer Quelle (Käufe/Store-Downloads): Downloads\\<Quelle> – "" ohne Rolle „Downloads“."""
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
