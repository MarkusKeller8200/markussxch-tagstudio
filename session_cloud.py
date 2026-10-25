"""Session-Teil „Abgleich über die Dienste“ (Cloud Weg 2, #317): Einstellungen, Abgleich-Auftrag, Konflikte, Löschen
nur nach Rückfrage. Die Dienste selbst sind Plugins mit der Fähigkeit „cloud_sync“ (#318 OneDrive, #319 Google Drive,
#320 Dropbox)."""
from __future__ import annotations

import uuid

import cloudsync
import core
import folders

SYNC_ROLES = ("playlists", "export")


class PluginProvider:
    """Ein Cloud-Plugin als Gegenstelle für cloudsync (list/get/put/delete über die Funktionen des Plugins)."""

    def __init__(self, plugin, session=None, cancel=None, progress=None):
        import plugins
        self.plugin = plugin
        self.mod = plugin.load()
        self.ctx = plugins.Context(plugin, session, cancel, progress)

    def list(self, folder: str) -> dict:
        return self.mod.cloud_list(self.ctx, folder)

    def get(self, path: str) -> bytes:
        return self.mod.cloud_get(self.ctx, path)

    def put(self, path: str, data: bytes):
        return self.mod.cloud_put(self.ctx, path, data)

    def delete(self, path: str):
        return self.mod.cloud_delete(self.ctx, path)


class CloudSyncMixin:
    # ------------------------------------------------------------------ Dienste
    def _cloud_plugins(self) -> dict:
        """Eingeschaltete Plugins mit Cloud-Abgleich: {id: Plugin}."""
        out = {}
        for pid, p in self.plugins.plugins.items():
            try:
                if p.enabled and p.state() == "ready" and p.load() is not None and callable(getattr(p.load(), "cloud_list", None)):
                    out[pid] = p
            except Exception:  # noqa: BLE001 – ein defektes Plugin blendet nur sich selbst aus
                continue
        return out

    def _cloud_provider(self, pid: str, cancel=None, progress=None):
        p = self._cloud_plugins().get(pid)
        if p is None:
            raise ValueError(f"Cloud-Plugin „{pid}“ ist aus oder nicht bereit.")
        return PluginProvider(p, self, cancel, progress)

    def _cloud_provider_info(self) -> list:
        out = []
        for pid, p in sorted(self._cloud_plugins().items(), key=lambda x: x[1].name.lower()):
            mod = p.load()
            import plugins
            try:
                ok, why = mod.ready(plugins.Context(p, self)) if callable(getattr(mod, "ready", None)) else (True, "")
            except Exception as ex:  # noqa: BLE001
                ok, why = False, str(ex)
            out.append({"id": pid, "name": p.name, "ready": bool(ok), "why": why})
        return out

    # ------------------------------------------------------------------ Ziele
    def _cloud_targets(self) -> list:
        """[(Teil, Einstellung)] aller eingeschalteten Abgleiche."""
        out = []
        m = self._folders()
        for rid in SYNC_ROLES:
            s = cloudsync.clean_sync((m["roles"].get(rid) or {}).get("sync"))
            path = folders.resolve_role(m, rid)
            if s and path:
                out.append((cloudsync.FolderPart(rid, folders._spec(rid)["label"], path, exts=cloudsync.ROLE_EXTS.get(rid)), s))
        app = self.cfg.get("cloud_sync_app") if isinstance(self.cfg.get("cloud_sync_app"), dict) else {}
        for pid, _label in cloudsync.APP_PARTS:
            s = cloudsync.clean_sync(app.get(pid))
            if s:
                out.append((self._cloud_app_part(pid), s))
        return out

    def _cloud_app_part(self, pid: str):
        part = cloudsync.app_part(pid)
        session = self

        def after():
            if pid == "pl_store":
                session._plstore = None                     # Speicher neu laden
            elif pid == "purchases":
                session._purchstore = None
            elif pid == "settings":
                session.cfg.update(core.load_config())
        part.after = after
        return part

    def _cloud_part(self, part_id: str):
        for part, s in self._cloud_targets():
            if part.id == part_id:
                return part, s
        raise ValueError("Dieser Abgleich ist nicht (mehr) eingerichtet.")

    def cloud_sync_overview(self) -> dict:
        m = self._folders()
        app = self.cfg.get("cloud_sync_app") if isinstance(self.cfg.get("cloud_sync_app"), dict) else {}
        rows = []
        for rid in SYNC_ROLES:
            s = cloudsync.clean_sync((m["roles"].get(rid) or {}).get("sync"))
            rows.append({"kind": "role", "id": rid, "label": folders._spec(rid)["label"], "path": folders.resolve_role(m, rid),
                         "sync": s, "default_remote": cloudsync.REMOTE_DEFAULT[rid], "last": cloudsync.last(rid, s) if s else {}})
        for pid, label in cloudsync.APP_PARTS:
            s = cloudsync.clean_sync(app.get(pid))
            rows.append({"kind": "app", "id": pid, "label": label, "path": "", "sync": s,
                         "default_remote": cloudsync.REMOTE_DEFAULT[pid], "last": cloudsync.last(pid, s) if s else {}})
        pend = getattr(self, "_cloud_pending", None) or {"conflicts": [], "gone": []}
        return {"providers": self._cloud_provider_info(), "rows": rows,
                "conflicts": len(pend["conflicts"]), "gone": len(pend["gone"])}

    def cloud_sync_set(self, kind, rid, sync) -> dict:
        """Abgleich einer Rolle bzw. eines Programmdaten-Teils einstellen (sync=None: aus)."""
        if isinstance(sync, dict) and sync.get("provider") and not sync.get("remote"):
            sync = dict(sync, remote=cloudsync.REMOTE_DEFAULT.get(str(rid), "TagStudio"))     # Standard: /TagStudio/<Rolle>
        s = cloudsync.clean_sync(sync) if sync else None
        if s and s["provider"] not in self._cloud_plugins():
            raise ValueError("Dieses Cloud-Plugin ist aus oder nicht bereit.")
        if kind == "role":
            if rid not in SYNC_ROLES:
                raise ValueError("Nur Playlists und Export lassen sich über die Dienste abgleichen.")
            m = self._folders()
            r = dict(m["roles"][rid])
            if s:
                r["sync"] = s
            else:
                r.pop("sync", None)
            m["roles"][rid] = r
            self._folders_save(m, follow=False)
        elif kind == "app":
            if rid not in dict(cloudsync.APP_PARTS):
                raise ValueError("Unbekannter Teil der Programmdaten.")
            app = dict(self.cfg.get("cloud_sync_app") or {})
            if s:
                app[rid] = s
            else:
                app.pop(rid, None)
            self.cfg["cloud_sync_app"] = app
            core.save_config({"cloud_sync_app": app})
        else:
            raise ValueError("role oder app erwartet")
        return self.cloud_sync_overview()

    # ------------------------------------------------------------------ Abgleich
    def start_cloud_sync(self, only=None):
        """Alle (bzw. only: Liste von Teil-IDs) eingerichteten Abgleiche ausführen. Konflikte und gelöschte Dateien
        kommen in eine Liste zum Nachfragen – es wird nie still überschrieben oder gelöscht."""
        targets = [(p, s) for p, s in self._cloud_targets() if not only or p.id in set(only)]
        if not targets:
            return {"ok": False, "error": "Kein Abgleich eingerichtet – unter Einstellungen › Speicherort und Ordner › "
                                          "„Abgleich über die Dienste“ einen Dienst wählen."}

        def job(cancel, progress):
            def check():
                if cancel is not None and cancel.is_set():
                    raise RuntimeError("Abgebrochen.")
            pend = {"conflicts": [], "gone": []}
            rows, log = [], []
            for i, (part, s) in enumerate(targets):
                progress(("progress", i, len(targets), part.label))
                try:
                    res = cloudsync.run(part, self._cloud_provider(s["provider"], cancel), s, log=log.append, cancel=check)
                except Exception as ex:  # noqa: BLE001 – ein Ziel darf die anderen nicht aufhalten
                    rows.append({"part": part.id, "label": part.label, "error": str(ex)})
                    continue
                for c in res["conflicts"]:
                    pend["conflicts"].append({"id": uuid.uuid4().hex[:12], "part": part.id, "label": part.label, "rel": c["rel"],
                                              "local": c["local"], "remote": c["remote"], "rev": c["rev"]})
                for rel in res["gone_remote"]:
                    pend["gone"].append({"id": uuid.uuid4().hex[:12], "part": part.id, "label": part.label, "rel": rel, "where": "local",
                                         "why": "im Dienst gelöscht"})
                for rel in res["gone_local"]:
                    pend["gone"].append({"id": uuid.uuid4().hex[:12], "part": part.id, "label": part.label, "rel": rel, "where": "remote",
                                         "why": "hier gelöscht"})
                rows.append({"part": part.id, "label": part.label, "up": res["up"], "down": res["down"],
                             "conflicts": len(res["conflicts"]), "gone": len(res["gone_remote"]) + len(res["gone_local"]),
                             "errors": res["errors"][:20]})
            progress(("progress", len(targets), len(targets), "fertig"))
            self._cloud_pending = pend
            up, down = sum(r.get("up", 0) for r in rows), sum(r.get("down", 0) for r in rows)
            return {"rows": rows, "log": log, "conflicts": len(pend["conflicts"]), "gone": len(pend["gone"]),
                    "message": f"{up} Datei(en) hochgeladen, {down} heruntergeladen"
                               + (f", {len(pend['conflicts'])} Konflikt(e) – bitte entscheiden" if pend["conflicts"] else "")
                               + (f", {len(pend['gone'])} gelöschte Datei(en) – nur nach Rückfrage" if pend["gone"] else "") + "."}
        return self._run("cloud", "Abgleich über die Dienste", job)

    def cloud_pending(self) -> dict:
        """Offene Konflikte (mit Vorschau beider Fassungen) und gelöschte Dateien."""
        pend = getattr(self, "_cloud_pending", None) or {"conflicts": [], "gone": []}
        return {"conflicts": [{"id": c["id"], "label": c["label"], "rel": c["rel"], "part": c["part"],
                               "local": cloudsync.preview(c["local"]), "remote": cloudsync.preview(c["remote"]),
                               "local_size": len(c["local"]), "remote_size": len(c["remote"])} for c in pend["conflicts"]],
                "gone": [{k: g[k] for k in ("id", "label", "rel", "part", "where", "why")} for g in pend["gone"]]}

    def cloud_resolve(self, cid, choice) -> dict:
        pend = getattr(self, "_cloud_pending", None) or {"conflicts": [], "gone": []}
        c = next((x for x in pend["conflicts"] if x["id"] == cid), None)
        if c is None:
            raise ValueError("Dieser Konflikt ist schon erledigt.")
        part, s = self._cloud_part(c["part"])
        cloudsync.resolve(part, self._cloud_provider(s["provider"]), s, c["rel"], str(choice), c["remote"], c["rev"])
        pend["conflicts"].remove(c)
        return self.cloud_pending()

    def cloud_gone(self, gid, action) -> dict:
        """Gelöschte Datei: action = delete (nach Rückfrage in der Oberfläche auch auf der anderen Seite löschen)
        oder keep (nicht löschen – beim nächsten Abgleich wieder übertragen)."""
        pend = getattr(self, "_cloud_pending", None) or {"conflicts": [], "gone": []}
        g = next((x for x in pend["gone"] if x["id"] == gid), None)
        if g is None:
            raise ValueError("Schon erledigt.")
        part, s = self._cloud_part(g["part"])
        if action == "delete":
            cloudsync.delete(part, self._cloud_provider(s["provider"]), s, g["rel"], g["where"])
        elif action == "keep":
            cloudsync.forget(part.id, s, g["rel"])
        else:
            raise ValueError("delete oder keep erwartet")
        pend["gone"].remove(g)
        return self.cloud_pending()
