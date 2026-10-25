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

    def _disc_deezer(self, log=None):
        """#204: Deezer-Abruf über das Plugin Deezer (gemeinsame Drosselung) – None, wenn das Plugin aus ist."""
        try:
            import plugins
            p = self.plugins.plugins.get("deezer")
            mod = p.load() if p is not None and p.enabled and p.state() == "ready" else None
            if mod is None:
                if log:
                    log("Deezer übersprungen: Plugin „Deezer“ ist ausgeschaltet.")
                return None
            cl = mod.client(plugins.Context(p, None))

            def get(path, **params):
                d = cl.json(mod.API + path + ("?" + discover.urllib.parse.urlencode(params) if params else "")) or {}
                if isinstance(d, dict) and d.get("error"):
                    err = d["error"]
                    raise RuntimeError(f"Deezer: {err.get('message') if isinstance(err, dict) else err}")
                return d
            return get
        except Exception as ex:  # noqa: BLE001
            if log:
                log(f"Deezer nicht verfügbar: {ex}")
            return None

    def _disc_library(self) -> str:
        try:
            lib = self._prep_get().get("library") or ""
        except Exception:  # noqa: BLE001
            lib = ""
        return lib if lib and os.path.isdir(lib) else ""

    def _disc_bought(self) -> list:
        """Einträge der Liste „Käufe“ (#285) für die Markierung „gekauft“ (#291)."""
        try:
            with self.lock:
                return list(self._purch().data["items"].values())
        except Exception:  # noqa: BLE001 – ohne Käufe einfach nichts markieren
            return []

    def disc_overview(self) -> dict:
        d = discover.load()
        purchased = discover.mark_purchased(d, self._disc_bought())
        items = sorted(d["items"].values(), key=lambda e: (e.get("date") or "", e.get("first") or ""), reverse=True)
        counts = {k: 0 for k in discover.STATUS}
        for e in items:
            st = e.get("status", "new")
            counts[st] = counts.get(st, 0) + 1
            if e.get("purchased") and st not in ("bought", "hidden"):
                counts["bought"] += 1
        bp = False
        try:
            p = self.plugins.get("beatport")
            bp = bool(p.enabled and p.state() == "ready")
        except KeyError:
            pass
        return {"follow": d["follow"], "items": items, "counts": counts, "status": discover.STATUS,
                "last": d.get("last", ""), "log": d.get("log", [])[-30:], "beatport": bp, "library": self._disc_library(),
                "purchased": purchased}

    def disc_follow_edit(self, kind, name, add=True) -> dict:
        """Künstler/Label direkt in „Entdecken“ folgen bzw. entfernen (#291)."""
        with discover.LOCK:
            d = discover.load()
            if discover.follow_edit(d, str(kind), str(name or ""), bool(add)):
                discover.save(d)
        return self.disc_overview()

    def disc_clear(self) -> dict:
        """Neue und ausgeblendete Vorschläge entfernen, gemerkte und gekaufte bleiben (#291)."""
        with discover.LOCK:
            d = discover.load()
            n = discover.clear(d)
            discover.save(d)
        r = self.disc_overview()
        r["removed"] = n
        return r

    def _disc_bp_plugin(self):
        import plugins
        p = self.plugins.get("beatport")
        if not p.enabled or p.state() != "ready":
            return None, None
        mod = p.load()
        return mod, plugins.Context(p, None)

    def start_disc_bp_follow(self):
        """Auf Beatport gefolgte Künstler und Labels holen und übernehmen (#291, nur lesen)."""
        try:
            mod, ctx = self._disc_bp_plugin()
        except KeyError:
            mod = ctx = None
        if mod is None:
            return {"ok": False, "error": "Plugin „Beatport“ ist aus oder nicht bereit."}
        ok, why = mod.ready(ctx)
        if not ok:
            return {"ok": False, "error": f"Beatport: {why}."}

        def job(cancel, progress):
            progress(("text", "Beatport: gefolgte Künstler lesen …"))
            arts = mod.followed(ctx, "artists")
            progress(("text", "Beatport: gefolgte Labels lesen …"))
            labs = mod.followed(ctx, "labels")
            with discover.LOCK:
                d = discover.load()
                f = d["follow"]
                na, nl = len(f["artists"]), len(f["labels"])
                f["artists"] = discover._names(f["artists"] + arts)
                f["labels"] = discover._names(f["labels"] + labs)
                f["bp"] = {"artists": discover._names(f["bp"]["artists"] + arts), "labels": discover._names(f["bp"]["labels"] + labs)}
                discover.save(d)
            return {"artists": len(arts), "labels": len(labs), "new_artists": len(f["artists"]) - na,
                    "new_labels": len(f["labels"]) - nl}
        return self._run("disc", "Beatport: Gefolgte übernehmen", job)

    def start_disc_related(self):
        """Ähnliche Künstler zu den gefolgten (Deezer, #291)."""
        d = discover.load()
        if not d["follow"]["artists"]:
            return {"ok": False, "error": "Noch keinem Künstler gefolgt."}
        log = []
        dz = self._disc_deezer(log.append)
        if dz is None:
            return {"ok": False, "error": "Für ähnliche Künstler das Plugin „Deezer“ einschalten."}

        def job(cancel, progress):
            return {"artists": discover.related_artists(d["follow"]["artists"], dz, cancel=cancel, progress=progress)}
        return self._run("disc", "Ähnliche Künstler suchen", job)

    def disc_follow_save(self, follow) -> dict:
        with discover.LOCK:
            d = discover.load()
            f = follow if isinstance(follow, dict) else {}
            bp = d["follow"].get("bp") or {"artists": [], "labels": []}
            d["follow"] = {"artists": discover._names(f.get("artists")), "labels": discover._names(f.get("labels")),
                           "genres": [{"id": g["id"], "name": str(g.get("name") or "")} for g in f.get("genres") or []
                                      if isinstance(g, dict) and g.get("id")],
                           "days": max(1, min(3650, int(f.get("days") or 60))), "auto": bool(f.get("auto")),
                           "sources": [s for s in f.get("sources") or [] if s in ("deezer", "beatport")]}
            keep = lambda kind: [x for x in bp.get(kind, []) if discover.norm(x) in {discover.norm(y) for y in d["follow"][kind]}]  # noqa: E731
            d["follow"]["bp"] = {"artists": keep("artists"), "labels": keep("labels")}
            discover.save(d)
        return self.disc_overview()

    def disc_set(self, keys, status) -> dict:
        if status not in discover.STATUS:
            raise ValueError("Unbekannter Status.")
        with discover.LOCK:
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
        with discover.LOCK:                             # prüfen und setzen in einem Schritt
            d = discover.load()
            if not discover.auto_due(d) or getattr(self, "_disc_auto_running", False):
                return {"started": False}
            self._disc_auto_running = True

        def work():
            try:
                log = []
                f = d["follow"]
                bp = self._disc_beatport(log.append) if "beatport" in f["sources"] else None
                dz = self._disc_deezer(log.append) if "deezer" in f["sources"] else None
                found = discover.run(d, bp, log.append, dz=dz)
                idx = None
                if self._disc_library():
                    try:
                        idx = discover.owned_index(self._disc_lib_files())
                    except Exception as ex:  # noqa: BLE001
                        log.append(f"Bibliothek: {ex}")
                with discover.LOCK:
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
            dz = self._disc_deezer(log.append) if "deezer" in f["sources"] else None
            found = discover.run(d0, bp, log.append, progress, cancel, dz=dz)
            idx = discover.owned_index(self._disc_lib_files(cancel, progress)) if self._disc_library() else None
            with discover.LOCK:
                d = discover.load()
                new = discover.merge(d, found, idx)
                d["last"] = discover.time.strftime("%Y-%m-%dT%H:%M:%S")
                d["log"] = log[-50:]
                discover.save(d)
            return {"new": new, "found": len(found), "log": log[-50:]}
        return self._run("disc", "Entdecken", job)
