"""Session-Teil „Spiegel der Bibliothek“ (#403): Einweg-Kopie der Musik in einen Cloud-Ordner (z. B. OneDrive privat,
#405) mit Platzschätzung, index.json, Playlists (M3U8 relativ) und überzähligen Dateien nur nach Rückfrage."""
from __future__ import annotations

import os
import threading
import time

import core
import folders
import mirror
from id3tags import fmt_bytes

LAST_KEY = "mirror_last"


class MirrorMixin:
    # ------------------------------------------------------------------ Einstellungen
    def _mirror_cfg(self) -> dict:
        return mirror.clean_cfg(self.cfg.get("mirror"))

    def _cloud_folders(self) -> list[dict]:
        """Ordner, die Plugins als Cloud-Ziel anbieten (OneDrive „Privat“: ``cloud_folder``) → [{id, name, path}]."""
        import plugins
        out = []
        for pid, p in self.plugins.plugins.items():
            try:
                mod = p.load() if p.enabled and p.state() == "ready" else None
                fn = getattr(mod, "cloud_folder", None) if mod is not None else None
                f = fn(plugins.Context(p, self)) if callable(fn) else ""
            except Exception:  # noqa: BLE001 – ein Plugin-Fehler blendet nur diesen Vorschlag aus
                f = ""
            if f:
                out.append({"id": pid, "name": p.name, "path": f})
        return out

    def _cloud_root(self) -> str:
        """Ordner aus einem Cloud-Plugin (OneDrive privat), sonst ein erkannter OneDrive-Ordner – oder leer."""
        roots = [x["path"] for x in self._cloud_folders()]
        if not roots:
            import cloud
            roots = [r["path"] for r in cloud.detect() if r.get("provider") == "onedrive"]
        return roots[0] if roots else ""

    def _mirror_suggest(self, layout: str = "path") -> str:
        """Vorschlag für das Ziel (#415): Aufbau „Pfad“ → der OneDrive-Ordner selbst (darin der Pfad der Bibliothek ohne
        Laufwerk, #413); Aufbau „Name“ → ``<OneDrive>/TagStudio-Spiegel``."""
        root = self._cloud_root()
        if not root:
            return ""
        return root if layout == "path" else os.path.join(root, mirror.DEFAULT_SUB)

    def _mirror_dests(self, c: dict, folder: str = "", layout: str = "") -> list[dict]:
        folder, layout = folder or c["folder"], layout or c["layout"]
        if not folder:
            return []
        return [{"name": r["name"], "path": r["path"], "dest": mirror.dest_of(r, os.path.abspath(folder), layout)}
                for r in self._mirror_libs(c)]

    def _mirror_libs(self, c: dict) -> list[dict]:
        roots, _skipped = folders.scan_roots(self._folders())
        want = set(c.get("libraries") or [])
        return [r for r in roots if not want or r["id"] in want]

    def mirror_overview(self) -> dict:
        c = self._mirror_cfg()
        roots, skipped = folders.scan_roots(self._folders())
        want = set(c["libraries"])
        libs = [{"id": r["id"], "name": r["name"], "path": r["path"], "on": not want or r["id"] in want} for r in roots]
        extra = getattr(self, "_mirror_extra", None) or []
        return {"cfg": c, "suggest": self._mirror_suggest(c["layout"]),
                "suggests": {k: self._mirror_suggest(k) for k in mirror.LAYOUTS},
                "dests": self._mirror_dests(c, c["folder"] or self._mirror_suggest(c["layout"])),
                "cloud_folders": self._cloud_folders(), "libraries": libs,
                "skipped": skipped, "last": self.cfg.get(LAST_KEY) or {}, "extra": len(extra),
                "windows": os.name == "nt"}

    def mirror_set(self, c) -> dict:
        c = mirror.clean_cfg(c)
        if c["folder"]:
            c["folder"] = os.path.abspath(os.path.expanduser(c["folder"]))
            for r in folders.scan_roots(self._folders())[0]:
                if mirror._inside(c["folder"], r["path"]) or mirror._inside(r["path"], c["folder"]):
                    raise ValueError(f"Der Spiegel darf nicht in der Bibliothek „{r['name']}“ liegen (und umgekehrt).")
        self.cfg["mirror"] = c
        core.save_config({"mirror": c})
        return self.mirror_overview()

    def mirror_cloud_folders(self, base, create: bool = False) -> dict:
        """#413 (OneDrive privat › „Spiegel-Ordner erstellen“): im Cloud-Ordner je gewählter Bibliothek denselben Pfad
        wie auf dem Rechner ohne Laufwerk; mit ``create`` anlegen und den Spiegel darauf einstellen (Aufbau „Pfad“).
        Nichts wird gelöscht; vorhandene Ordner werden weiterverwendet."""
        base = os.path.abspath(os.path.expanduser(str(base or "").strip() or self._cloud_root()))
        if not base or not os.path.isdir(base):
            raise ValueError(f"Cloud-Ordner nicht gefunden: {base}")
        c = dict(self._mirror_cfg(), folder=base, layout="path")
        libs = self._mirror_libs(c)
        if not libs:
            raise ValueError("Keine erreichbare Bibliothek zum Spiegeln.")
        dests = self._mirror_dests(c)
        for r, d in zip(libs, dests):
            if mirror._inside(base, r["path"]) or mirror._inside(r["path"], base):
                raise ValueError(f"Der Cloud-Ordner liegt in der Bibliothek „{r['name']}“ (oder umgekehrt).")
        for i, a in enumerate(dests):
            for b in dests[i + 1:]:
                if mirror._inside(a["dest"], b["dest"]) or mirror._inside(b["dest"], a["dest"]):
                    raise ValueError(f"Die Bibliotheken „{a['name']}“ und „{b['name']}“ liegen ineinander – bitte eine "
                                     "unter Einstellungen › Cloud › Spiegel abwählen.")
        made = 0
        if create:
            for d in dests:
                if not os.path.isdir(d["dest"]):
                    os.makedirs(d["dest"], exist_ok=True)
                    made += 1
            self.mirror_set(c)
        return {"folder": base, "dests": dests, "created": made, "saved": bool(create)}

    # ------------------------------------------------------------------ Schätzung und Lauf
    def _mirror_plan(self, c: dict | None = None) -> dict:
        c = c or self._mirror_cfg()
        if not c["folder"]:
            raise ValueError("Bitte zuerst den Ziel-Ordner für den Spiegel angeben (z. B. im OneDrive-Ordner).")
        libs = self._mirror_libs(c)
        if not libs:
            raise ValueError("Keine erreichbare Bibliothek zum Spiegeln gewählt.")
        pl = mirror.plan(libs, c["folder"], c["layout"])
        if pl["error"]:
            raise ValueError(pl["error"])
        return pl

    def mirror_estimate(self) -> dict:
        """Platzschätzung: Musik gesamt, schon im Spiegel, noch zu kopieren, Sicherungen der Programmdaten (#402),
        freier Platz auf dem Laufwerk. Abo/Speicher in der Cloud entscheidet der Benutzer."""
        c = self._mirror_cfg()
        pl = self._mirror_plan(c)
        other = 0
        if callable(getattr(self, "_appbackup_bytes", None)):
            try:
                other = int(self._appbackup_bytes() or 0)
            except Exception:  # noqa: BLE001 – Schätzung der Sicherungen ist eine Beigabe
                other = 0
        est = mirror.estimate(pl, other)
        est.update(free=mirror.free_space(c["folder"]), extra=len(pl["extra"]), extra_bytes=pl["extra_bytes"],
                   libs=[{k: r[k] for k in ("name", "files", "bytes", "copy", "copy_bytes", "same", "extra")} for r in pl["libs"]],
                   folder=c["folder"])
        return est

    def start_mirror(self):
        try:
            c = self._mirror_cfg()
            pl = self._mirror_plan(c)
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}

        def job(cancel, progress):
            log = []
            with self._mirror_lock():
                res = mirror.run(pl, cancel=cancel.is_set, log=log.append,
                                 progress=lambda i, n, p: progress(("progress", i, n, p)))
                if cancel.is_set():
                    return {"cancelled": True, "log": log}
                progress(("text", "index.json schreiben …"))
                meta = mirror.meta_dir(c["folder"], c["layout"])
                n_idx = mirror.write_index(c["folder"], pl, mirror.load_index(meta), meta)
                n_pl = 0
                if c["playlists"]:
                    try:
                        n_pl = mirror.write_playlists(meta, self._pls().active(), pl)
                    except Exception as ex:  # noqa: BLE001 – Playlists sind eine Beigabe
                        log.append(f"Playlists nicht geschrieben: {ex}")
                note = mirror.set_online_only(res["paths"]) if c["online_only"] else ""
            self._mirror_extra = list(pl["extra"])
            last = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "copied": res["copied"], "bytes": res["bytes"],
                    "files": pl["files"], "extra": len(pl["extra"]), "errors": len(res["errors"]), "playlists": n_pl}
            self.cfg[LAST_KEY] = last
            core.save_config({LAST_KEY: last})
            msg = (f"Spiegel nachgeführt: {res['copied']} Datei(en) kopiert ({fmt_bytes(res['bytes'])}), "
                   f"{pl['files'] - res['copied'] - len(res['errors'])} unverändert, {n_idx} im Index, {n_pl} Playlist(s)")
            if pl["extra"]:
                msg += f", {len(pl['extra'])} überzählige Datei(en) im Spiegel – löschen nur nach Rückfrage"
            if res["errors"]:
                msg += f", {len(res['errors'])} Fehler"
            return {"message": msg + "." + (f" {note}" if note else ""), "log": log + res["errors"][:50],
                    "mirror_extra": len(pl["extra"])}
        return self._run("mirror", "Spiegel nachführen", job)

    def mirror_extra(self) -> dict:
        """Überzählige Dateien (im Spiegel, nicht mehr in der Bibliothek) aus dem letzten Lauf."""
        c = self._mirror_cfg()
        ex = getattr(self, "_mirror_extra", None) or []
        return {"folder": c["folder"], "files": [{"path": p, "rel": os.path.relpath(p, c["folder"]).replace(os.sep, "/")}
                                                 for p in ex if os.path.exists(p)]}

    def mirror_delete_extra(self, paths) -> dict:
        """Nach Rückfrage in der Oberfläche: gewählte überzählige Dateien im Spiegel löschen (nur aus der Liste)."""
        c = self._mirror_cfg()
        allowed = {os.path.normcase(p) for p in (getattr(self, "_mirror_extra", None) or [])}
        pick = [p for p in (paths or []) if os.path.normcase(str(p)) in allowed]
        r = mirror.delete_extra(pick, c["folder"])
        gone = {os.path.normcase(p) for p in pick}
        self._mirror_extra = [p for p in (getattr(self, "_mirror_extra", None) or []) if os.path.normcase(p) not in gone]
        r["left"] = len(self._mirror_extra)
        last = dict(self.cfg.get(LAST_KEY) or {})
        if last:
            last["extra"] = r["left"]
            self.cfg[LAST_KEY] = last
            core.save_config({LAST_KEY: last})
        return r

    # ------------------------------------------------------------------ automatisch nachführen
    def _mirror_lock(self):
        lk = getattr(self, "_mirror_lk", None)
        if lk is None:
            lk = self._mirror_lk = threading.Lock()
        return lk

    def _mirror_touch(self, paths):
        """Nach dem Speichern bzw. nach „Vorbereiten › Übernehmen“: geänderte Titel im Hintergrund in den Spiegel kopieren
        (nur mit „automatisch nachführen“). Fehler stören die eigentliche Arbeit nie."""
        try:
            c = self._mirror_cfg()
            if not (c["auto"] and c["folder"] and paths):
                return
            libs = self._mirror_libs(c)
            pl = mirror.plan(libs, c["folder"], c["layout"]) if libs else None
        except Exception:  # noqa: BLE001
            return
        if not pl or pl["error"]:
            return
        want = {os.path.normcase(os.path.abspath(str(p))) for p in paths}
        pl["copy"] = [x for x in pl["copy"] if os.path.normcase(x[0]) in want]
        if not pl["copy"]:
            return

        def work():
            with self._mirror_lock():
                try:
                    res = mirror.run(pl)
                    if c["online_only"]:
                        mirror.set_online_only(res["paths"])
                except Exception:  # noqa: BLE001
                    pass
        threading.Thread(target=work, name="mirror-auto", daemon=True).start()
