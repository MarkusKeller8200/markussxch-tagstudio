"""Session-Teil „Sicherung der Programmdaten“ (#402): ZIP in einen Ordner (z. B. OneDrive privat, #405), von Hand oder
automatisch (beim Beenden / täglich), Wiederherstellen mit Vorschau und vorheriger Sicherung; ältere Sicherungen nur
nach Rückfrage löschen."""
from __future__ import annotations

import os
import threading
import time

import appbackup
import core
import folders
import paths

CFG_KEY, LAST_KEY = "app_backup", "app_backup_last"


class AppBackupMixin:
    def _ab_cfg(self) -> dict:
        return appbackup.clean_cfg(self.cfg.get(CFG_KEY))

    def _ab_suggest(self) -> str:
        roots = [x["path"] for x in self._cloud_folders()] if callable(getattr(self, "_cloud_folders", None)) else []
        if not roots:
            import cloud
            roots = [r["path"] for r in cloud.detect() if r.get("provider") == "onedrive"]
        return os.path.join(roots[0], appbackup.DEFAULT_SUB) if roots else paths.sub("Sicherungen", "Programmdaten")

    def _ab_folder(self) -> str:
        return self._ab_cfg()["folder"] or ""

    def _ab_libs(self) -> list[dict]:
        roots, _sk = folders.scan_roots(self._folders())
        return roots

    def appbackup_overview(self) -> dict:
        c = self._ab_cfg()
        lst = appbackup.listing(c["folder"]) if c["folder"] else []
        return {"cfg": c, "suggest": self._ab_suggest(), "list": lst[:30], "count": len(lst),
                "surplus": len(lst[c["keep"]:]), "last": self.cfg.get(LAST_KEY) or {},
                "parts": [{"id": p[0], "label": p[1]} for p in appbackup.PARTS]}

    def appbackup_set(self, c) -> dict:
        c = appbackup.clean_cfg(c)
        if c["folder"]:
            c["folder"] = os.path.abspath(os.path.expanduser(c["folder"]))
        self.cfg[CFG_KEY] = c
        core.save_config({CFG_KEY: c})
        return self.appbackup_overview()

    def _appbackup_bytes(self) -> int:
        """Für die Platzschätzung des Spiegels (#403)."""
        c = self._ab_cfg()
        return appbackup.size_of(c["folder"], c["keep"]) if c["folder"] else 0

    # ------------------------------------------------------------------ Sichern
    def _ab_create(self, note: str = "") -> dict:
        from version import VERSION
        c = self._ab_cfg()
        if not c["folder"]:
            raise ValueError("Bitte zuerst den Ordner für die Sicherung angeben (z. B. im OneDrive-Ordner).")
        with self._ab_lock():
            r = appbackup.create(c["folder"], VERSION, self._ab_libs(), note)
        last = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "name": r["name"], "size": r["size"], "files": r["files"]}
        if not note:
            self.cfg[LAST_KEY] = last
            core.save_config({LAST_KEY: last})
        r["surplus"] = len(appbackup.surplus(c["folder"], c["keep"]))
        return r

    def start_appbackup(self):
        if not self._ab_cfg()["folder"]:
            return {"ok": False, "error": "Bitte zuerst den Ordner für die Sicherung angeben (z. B. im OneDrive-Ordner)."}

        def job(cancel, progress):
            progress(("text", "Programmdaten sichern …"))
            r = self._ab_create()
            from id3tags import fmt_bytes
            msg = f"Gesichert: {r['name']} ({r['files']} Dateien, {fmt_bytes(r['size'])})"
            if r["surplus"]:
                msg += f" – {r['surplus']} ältere Sicherung(en) über der Anzahl „behalten“ (löschen nur nach Rückfrage)"
            return {"message": msg + ".", "ab_surplus": r["surplus"], "log": []}
        return self._run("appbackup", "Programmdaten sichern", job)

    def appbackup_surplus(self) -> dict:
        c = self._ab_cfg()
        return {"folder": c["folder"], "keep": c["keep"], "files": appbackup.surplus(c["folder"], c["keep"]) if c["folder"] else []}

    def appbackup_delete(self, paths_) -> dict:
        """Nach Rückfrage: gewählte Sicherungen löschen (nur Dateien „TagStudio-Programmdaten_*.zip“ im Ordner)."""
        c = self._ab_cfg()
        return appbackup.delete(list(paths_ or []), c["folder"])

    # ------------------------------------------------------------------ automatisch
    def _ab_lock(self):
        lk = getattr(self, "_ab_lk", None)
        if lk is None:
            lk = self._ab_lk = threading.Lock()
        return lk

    def appbackup_exit(self) -> bool:
        """Beim Beenden (Einstellung „beim Beenden“) – Fehler stören das Beenden nie."""
        c = self._ab_cfg()
        if c["auto"] != "exit" or not c["folder"]:
            return False
        try:
            self._ab_create()
            return True
        except Exception:  # noqa: BLE001
            return False

    def appbackup_daily(self) -> bool:
        """Nach dem Start (Einstellung „täglich“): sichern, wenn die letzte Sicherung älter als 24 Stunden ist."""
        c = self._ab_cfg()
        if c["auto"] != "daily" or not c["folder"]:
            return False
        last = (self.cfg.get(LAST_KEY) or {}).get("at") or ""
        try:
            age = time.time() - time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S")) if last else 1e9
        except ValueError:
            age = 1e9
        if age < 24 * 3600:
            return False

        def work():
            try:
                self._ab_create()
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=work, name="appbackup-daily", daemon=True).start()
        return True

    # ------------------------------------------------------------------ Wiederherstellen
    def appbackup_preview(self, path) -> dict:
        p = appbackup.preview(str(path))
        p["libraries_here"] = [{"id": x["id"], "name": x["name"], "path": x["path"]} for x in self._ab_libs()]
        _rb, pairs = appbackup.path_mapper(p["libraries"], p["libraries_here"])
        p["remap"] = [{"from": a, "to": b} for a, b in pairs]
        return p

    def start_appbackup_restore(self, path, parts=None, groups=None):
        path = str(path or "")
        parts = [x for x in (parts or appbackup.PART_IDS) if x in appbackup.PART_IDS]
        if not parts:
            return {"ok": False, "error": "Nichts zum Wiederherstellen gewählt."}
        try:
            man, files = appbackup.read(path)
        except (OSError, ValueError) as ex:
            return {"ok": False, "error": str(ex)}

        def job(cancel, progress):
            progress(("text", "Jetzigen Stand sichern …"))
            before = ""
            try:
                before = self._ab_create("vor-Wiederherstellen")["name"] if self._ab_cfg()["folder"] else ""
            except Exception as ex:  # noqa: BLE001
                raise RuntimeError(f"Der jetzige Stand liess sich nicht sichern – nichts wiederhergestellt ({ex}).") from ex
            progress(("text", "Wiederherstellen …"))
            done = appbackup.restore_files(files, parts)
            n_set = 0
            if "settings" in parts and appbackup.settings_text(files):
                import appsettings
                r = appsettings.import_apply(appbackup.settings_text(files), list(groups or []))
                n_set = r.get("keys", 0) if r.get("ok") else 0
                self.cfg.update(core.load_config())
            self._plstore = None                                   # Speicher neu laden
            self._purchstore = None
            rb, pairs = appbackup.path_mapper(man.get("libraries") or [], self._ab_libs())
            moved = self._folders_relink(None, None, rb=rb) if pairs else {}
            labels = {p[0]: p[1] for p in appbackup.PARTS}
            parts_txt = ", ".join(f"{labels.get(k, k)}: {v}" for k, v in done.items() if v)
            msg = (f"Wiederhergestellt: {parts_txt or 'keine Dateien'}"
                   + (f", {n_set} Einstellung(en)" if n_set else "")
                   + (f"; Pfade auf diesen Rechner umgeschrieben ({sum(v for v in moved.values() if isinstance(v, int))})" if pairs else "")
                   + (f". Vorheriger Stand gesichert als {before}" if before else "") + ".")
            return {"message": msg, "log": [], "reload": True}
        return self._run("appbackup", "Programmdaten wiederherstellen", job)
