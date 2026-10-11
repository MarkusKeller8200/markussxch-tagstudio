"""Session-Teil „Entdecken“ (#120): gefolgte Künstler/Labels/Genres, Suchlauf, Merkliste, Vorhören."""
from __future__ import annotations

import os

import core
import discover


class DiscoverMixin:
    def _disc_beatport(self, log=None):
        """Client des Beatport-Plugins, wenn eingeschaltet und angemeldet – sonst None."""
        try:
            import plugins
            p = self.plugins.get("beatport")
            if not p.enabled or p.state() != "ready":
                return None
            mod = p.load()
            ctx = plugins.Context(p, None)
            if mod is None or not mod.load_token(ctx):
                return None
            return mod.Client(ctx)
        except Exception as ex:  # noqa: BLE001
            if log:
                log(f"Beatport nicht verfügbar: {ex}")
            return None

    def _disc_library(self) -> str:
        try:
            lib = self._prep_get().get("library") or ""
        except Exception:  # noqa: BLE001
            lib = ""
        return lib if lib and os.path.isdir(lib) else ""

    def disc_overview(self) -> dict:
        d = discover.load()
        items = sorted(d["items"].values(), key=lambda e: (e.get("date") or "", e.get("first") or ""), reverse=True)
        counts = {k: 0 for k in discover.STATUS}
        for e in items:
            counts[e.get("status", "new")] = counts.get(e.get("status", "new"), 0) + 1
        bp = False
        try:
            p = self.plugins.get("beatport")
            bp = bool(p.enabled and p.state() == "ready")
        except KeyError:
            pass
        return {"follow": d["follow"], "items": items, "counts": counts, "status": discover.STATUS,
                "last": d.get("last", ""), "log": d.get("log", [])[-30:], "beatport": bp, "library": self._disc_library()}

    def disc_follow_save(self, follow) -> dict:
        d = discover.load()
        f = follow if isinstance(follow, dict) else {}
        d["follow"] = {"artists": discover._names(f.get("artists")), "labels": discover._names(f.get("labels")),
                       "genres": [{"id": g["id"], "name": str(g.get("name") or "")} for g in f.get("genres") or []
                                  if isinstance(g, dict) and g.get("id")],
                       "days": max(1, min(3650, int(f.get("days") or 60))), "auto": bool(f.get("auto")),
                       "sources": [s for s in f.get("sources") or [] if s in ("deezer", "beatport")]}
        discover.save(d)
        return self.disc_overview()

    def disc_set(self, keys, status) -> dict:
        if status not in discover.STATUS:
            raise ValueError("Unbekannter Status.")
        d = discover.load()
        for k in keys or []:
            if k in d["items"]:
                d["items"][k]["status"] = status
        discover.save(d)
        return self.disc_overview()

    def disc_genres(self) -> dict:
        c = self._disc_beatport()
        if c is None:
            return {"ok": False, "error": "Für Genres bei Beatport anmelden (Plugins › Beatport › „Anmelden …“)."}
        try:
            return {"ok": True, "genres": discover.beatport_genres(c)}
        except Exception as ex:  # noqa: BLE001
            return {"ok": False, "error": f"Beatport: {ex}"}

    def _disc_lib_files(self, cancel=None, progress=None):
        lib = self._disc_library()
        if not lib:
            return []
        if progress:
            progress(("text", "Lese die Bibliothek …"))
        files, _e = core.load_files(lib, True, cancel, None, None, self._list_cache_on())
        return files

    def disc_export_write(self, fmt, dest, which="saved") -> dict:
        """Merkliste (bzw. alle sichtbaren Einträge) als Excel oder CSV schreiben."""
        import tagger
        st = {"saved": ("saved",), "bought": ("bought",), "all": ("new", "saved", "bought")}.get(which, ("saved",))
        rows = discover.export_rows(discover.load(), st)
        (tagger.write_xlsx if fmt == "xlsx" else tagger.write_csv)(dest, discover.EXPORT_HEAD, rows)
        return {"ok": True, "path": dest, "count": len(rows), "message": f"{len(rows)} Titel exportiert: {os.path.basename(dest)}"}

    def disc_auto(self) -> dict:
        """Tägliche Suche beim Start (#162): läuft im Hintergrund (eigener Thread, kein Fortschrittsfenster)."""
        import threading
        d = discover.load()
        if not discover.auto_due(d) or getattr(self, "_disc_auto_running", False):
            return {"started": False}
        self._disc_auto_running = True

        def work():
            try:
                log = []
                f = d["follow"]
                bp = self._disc_beatport(log.append) if "beatport" in f["sources"] else None
                found = discover.run(d, bp, log.append)
                idx = None
                if self._disc_library():
                    try:
                        idx = discover.owned_index(self._disc_lib_files())
                    except Exception as ex:  # noqa: BLE001
                        log.append(f"Bibliothek: {ex}")
                cur = discover.load()
                new = discover.merge(cur, found, idx)
                cur["last"] = discover.time.strftime("%Y-%m-%dT%H:%M:%S")
                cur["log"] = log[-50:]
                cur["auto_new"] = new
                discover.save(cur)
            except Exception:  # noqa: BLE001 – Hintergrundsuche darf nie stören
                pass
            finally:
                self._disc_auto_running = False
        threading.Thread(target=work, daemon=True, name="disc-auto").start()
        return {"started": True}

    def disc_auto_status(self) -> dict:
        d = discover.load()
        return {"running": bool(getattr(self, "_disc_auto_running", False)), "auto_new": d.get("auto_new", 0), "count_new": sum(1 for e in d["items"].values() if e.get("status") == "new")}

    def start_disc_suggest(self):
        """Häufigste Künstler und Labels der Bibliothek als Vorschlag zum Folgen."""
        if not self._disc_library():
            return {"ok": False, "error": "Keine Bibliothek festgelegt (Vorbereiten › Workflow bearbeiten › Bibliothek)."}

        def job(cancel, progress):
            return discover.suggest_follow(self._disc_lib_files(cancel, progress))
        return self._run("disc", "Bibliothek auswerten", job)

    def start_disc_run(self):
        """Suchlauf über alle Quellen; neue Titel kommen als „neu“ in die Liste, vorhandene werden erkannt."""
        d0 = discover.load()
        f = d0["follow"]
        if not (f["artists"] or f["labels"] or f["genres"]):
            return {"ok": False, "error": "Noch nichts zum Folgen – Künstler, Labels oder Genres festlegen."}

        def job(cancel, progress):
            log = []
            bp = self._disc_beatport(log.append) if "beatport" in f["sources"] else None
            if "beatport" in f["sources"] and bp is None and not log:
                log.append("Beatport übersprungen: nicht angemeldet oder Plugin aus.")
            found = discover.run(d0, bp, log.append, progress, cancel)
            idx = discover.owned_index(self._disc_lib_files(cancel, progress)) if self._disc_library() else None
            d = discover.load()
            new = discover.merge(d, found, idx)
            d["last"] = discover.time.strftime("%Y-%m-%dT%H:%M:%S")
            d["log"] = log[-50:]
            discover.save(d)
            return {"new": new, "found": len(found), "log": log[-50:]}
        return self._run("disc", "Entdecken", job)
