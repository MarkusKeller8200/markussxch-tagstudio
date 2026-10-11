"""MarKusSXCH TagStudio – Sitzung: Snapshots, Journal, Überwachung, Speicherort (#52–#61)."""
from __future__ import annotations

import os
import time


import core
from core import size_text as fmt_bytes, duration_text as fmt_duration
import plugins

# Layout der Web-Oberfläche (Splitter, eingeklappte Seitenleiste): Schlüssel → erlaubter Typ


class SnapshotMixin:
    """Teil der Klasse Session (session.py) – nutzt deren Zustand (self.cfg, self.lock, …)."""

    # ================================================================== Snapshots (#52–#54, #61)
    SNAP_DEFAULTS = {"snap_daily": True, "snap_ask": True, "snap_keep": 20, "snap_weeks": 12, "snap_thorough": False,
                     "snap_watch": 5, "snap_hint": True}

    def _snap_cfg(self, k):
        v = self.cfg.get(k, self.SNAP_DEFAULTS.get(k))
        return v

    @property
    def snap_store(self):
        import snapshots
        d = self.cfg.get("snap_dir") or snapshots.default_dir()
        if getattr(self, "_snap_store", None) is None or self._snap_store.root != os.path.abspath(d):
            self._snap_store = snapshots.Store(d)
        return self._snap_store

    def snap_overview(self) -> dict:
        import snapshots
        st = self.snap_store
        sizes = st.sizes() if os.path.isdir(st.root) else {"total": 0, "libs": {}, "snaps": {}}
        libs = []
        all_libs = st.libraries()
        labels = self._lib_labels(all_libs)
        for lib in all_libs:
            snaps = st.snapshots(lib["id"])
            libs.append({"id": lib["id"], "name": lib["name"], "label": labels[lib["id"]],
                         "hue": int(lib["id"][:6], 16) % 360, "auto": lib.get("auto", True),
                         "root": lib["root"], "exists": os.path.isdir(lib["root"]),
                         "count": len(snaps), "bytes": sizes["libs"].get(lib["id"], 0),
                         "last": ({"created": snaps[0]["created"], "label": snaps[0]["label"],
                                   "age": snapshots.fmt_age(snaps[0]["created"])} if snaps else None)})
        return {"dir": st.root, "readonly": st.readonly, "total": sizes["total"], "libs": libs,
                "default": os.path.normcase(st.root) == os.path.normcase(os.path.abspath(snapshots.default_dir())),
                "settings": {k: self._snap_cfg(k) for k in self.SNAP_DEFAULTS}}

    def snap_list(self, lid) -> dict:
        st = self.snap_store
        sizes = st.sizes()
        out = []
        for s in st.snapshots(lid):
            s["bytes"] = sizes["snaps"].get(f"{lid}/{s['id']}", 0)
            out.append(s)
        return {"library": st.library(lid), "snapshots": out, "bytes": sizes["libs"].get(lid, 0), "total": sizes["total"]}

    def snap_add_library(self, path, name=None) -> dict:
        import snapshots
        try:
            lib = self.snap_store.add_library(str(path), name)
        except snapshots.StoreError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "library": lib}

    @staticmethod
    def _lib_labels(libs) -> dict:
        """#77: Anzeigenamen – gleichnamige Ordner bekommen den übergeordneten Ordner dazu."""
        names = [l["name"].lower() for l in libs]
        out = {}
        for l in libs:
            parent = os.path.basename(os.path.dirname(l["root"].rstrip("\\/"))) or l["root"][:3]
            out[l["id"]] = f"{l['name']} ({parent})" if names.count(l["name"].lower()) > 1 else l["name"]
        return out

    def snap_update_library(self, lid, name=None, root=None, auto=None) -> dict:
        """#77: Anzeigename, Ordner und „täglicher Snapshot“ je überwachtem Ordner."""
        import snapshots
        if root is not None:
            root = os.path.abspath(str(root))
            if not os.path.isdir(root):
                return {"ok": False, "error": f"Ordner nicht gefunden: {root}"}
        if name is not None:
            name = str(name).strip()[:80] or None
        try:
            self.snap_store.update_library(str(lid), name=name, root=root, auto=None if auto is None else bool(auto))
        except (OSError, snapshots.StoreError) as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, **self.snap_overview()}

    def snap_remove_library(self, lid) -> dict:
        self.snap_store.remove_library(str(lid))
        return self.snap_overview()

    def snap_update(self, lid, sid, label=None, pinned=None) -> dict:
        return self.snap_store.update_snapshot(str(lid), str(sid), label, pinned)

    def snap_delete(self, lid, sid) -> dict:
        freed = self.snap_store.delete_snapshot(str(lid), str(sid))
        return {"freed": freed, **self.snap_list(lid)}

    def snap_prune(self, lid=None) -> dict:
        st = self.snap_store
        before = st.sizes()["total"] if os.path.isdir(st.root) else 0
        gone = []
        for lib in st.libraries():
            if lid in (None, "", lib["id"]):
                gone += st.prune(lib["id"], int(self._snap_cfg("snap_keep")), int(self._snap_cfg("snap_weeks")))
        after = st.sizes()["total"] if os.path.isdir(st.root) else 0
        return {"removed": len(gone), "freed": max(0, before - after)}

    def snap_baseline_info(self, lid, sid=None, include_pinned=False) -> dict:
        """Vorschau für „Neue Baseline“: wie viele ältere Snapshots gelöscht würden (sid=None: alle bisherigen)."""
        st = self.snap_store
        snaps = st.snapshots(str(lid))
        if sid:
            older = st.older_than(str(lid), str(sid), include_pinned)
            pinned = [x for x in st.older_than(str(lid), str(sid), True) if x.get("pinned")]
        else:
            older = [x for x in snaps if include_pinned or not x.get("pinned")]
            pinned = [x for x in snaps if x.get("pinned")]
        sizes = st.sizes()
        return {"older": len(older), "pinned": len(pinned), "total": len(snaps),
                "bytes": sum(sizes["snaps"].get(f"{lid}/{x['id']}", 0) for x in older),
                "current": next((x["id"] for x in snaps if x.get("baseline")), None)}

    def snap_set_baseline(self, lid, sid, delete_older=True, include_pinned=False) -> dict:
        """Vorhandenen Snapshot als neue Baseline; ältere auf Wunsch löschen."""
        res = self.snap_store.set_baseline(str(lid), str(sid), bool(delete_older), bool(include_pinned))
        msg = "Neue Baseline gesetzt"
        if res["removed"]:
            msg += f" · {res['removed']} ältere(r) Snapshot(s) gelöscht, {fmt_bytes(res['freed'])} frei"
        return {**res, "message": msg, **self.snap_list(lid)}

    def snap_create(self, lid, label="", auto=False, pinned=False, baseline=None) -> dict:
        """Snapshot als Hintergrund-Auftrag (Fortschritt in der Fussleiste).
        baseline = {"delete_older": bool, "include_pinned": bool}: danach als neue Baseline setzen."""
        lib = self.snap_store.library(str(lid))
        if self.snap_store.readonly:
            return {"ok": False, "error": "Der Snapshot-Speicher stammt aus einer neueren TagStudio-Version (nur lesen)."}
        opts = {"lid": lib["id"], "label": str(label or ""), "auto": bool(auto), "pinned": bool(pinned),
                "thorough": bool(self._snap_cfg("snap_thorough"))}
        if isinstance(baseline, dict):
            opts["baseline"] = {"delete_older": bool(baseline.get("delete_older", True)),
                                "include_pinned": bool(baseline.get("include_pinned"))}
        job = self.jobs.add("tagstudio:snapshot", "create", f"Snapshot: {lib['name']}", [lib["root"]], opts,
                            names=[lib["name"]])
        return {"ok": True, "background": True, "job": job["id"], "waiting": 1}

    def _snap_job(self, job, cancel, progress):
        """Snapshot im Hintergrund (#53) mit Protokoll in Logs/snapshots.log (#62): Start, Ende, Dauer, Platz."""
        import datetime
        import time
        import snapshots
        o = job["opts"]
        st = self.snap_store
        try:
            lib = st.library(o["lid"])
            name, root = lib["name"], lib["root"]
        except Exception:  # noqa: BLE001
            name, root = o.get("lid", "?"), "?"
        t0, start = time.monotonic(), datetime.datetime.now()
        lines = [f"Snapshot „{o.get('label') or ('Automatisch' if o.get('auto') else 'Snapshot')}“ – {name}",
                 f"Ordner:   {root}",
                 f"Start:    {start:%Y-%m-%d %H:%M:%S}" + (" (gründlich)" if o.get("thorough") else "")]

        def finish(status):
            end = datetime.datetime.now()
            lines.append(f"Ende:     {end:%Y-%m-%d %H:%M:%S} – {status}")
            lines.append(f"Dauer:    {fmt_duration(time.monotonic() - t0)}")
            return plugins.write_log("snapshots.log", "\n".join(lines))

        try:
            res = snapshots.create(st, o["lid"], o["label"], o["auto"], o["pinned"], o["thorough"], cancel, progress)
        except Exception as ex:
            from compare import Cancelled
            path = finish("abgebrochen" if isinstance(ex, Cancelled) else f"Fehler: {ex}")
            if isinstance(ex, Cancelled):
                raise
            raise RuntimeError(f"{ex}\n\nDetails im Protokoll: {path}") from ex
        lines.append(f"Titel:    {res['count']} (neu eingelesen {res.get('read', 0)}, unverändert übernommen "
                     f"{res.get('reused', 0)})")
        based = None
        if o.get("baseline"):                                   # „Neue Baseline“ aus dem aktuellen Stand
            based = st.set_baseline(o["lid"], res["id"], o["baseline"]["delete_older"], o["baseline"]["include_pinned"])
            lines.append(f"Baseline: neu gesetzt, {based['removed']} ältere(r) Snapshot(s) gelöscht, "
                         f"{fmt_bytes(based['freed'])} freigegeben")
        pruned, freed = [], 0
        if o["auto"]:
            before = st.sizes()["total"]
            pruned = st.prune(o["lid"], int(self._snap_cfg("snap_keep")), int(self._snap_cfg("snap_weeks")))
            if pruned:
                freed = max(0, before - st.sizes()["total"])
        sz = st.sizes()
        own = sz.get("snaps", {}).get(f"{o['lid']}/{res['id']}", 0)
        if res["errors"]:
            lines.append(f"Nicht lesbar: {len(res['errors'])}")
            lines += ["  " + e for e in res["errors"][:200]]
        if pruned:
            lines.append(f"Aufgeräumt: {len(pruned)} alte(r) Snapshot(s), {fmt_bytes(freed)} freigegeben")
        lines.append(f"Speicherplatz: dieser Snapshot {fmt_bytes(own)} · Bibliothek "
                     f"{fmt_bytes(sz.get('libs', {}).get(o['lid'], 0))} · alle Snapshots {fmt_bytes(sz.get('total', 0))}")
        logfile = finish("fertig")
        msg = f"Snapshot „{res['label']}“: {res['count']} Titel"
        if res["errors"]:
            msg += f", {len(res['errors'])} nicht lesbar"
        if pruned:
            msg += f" · {len(pruned)} alte(r) Snapshot(s) aufgeräumt"
        if based:
            msg += f" · neue Baseline ({based['removed']} ältere gelöscht, {fmt_bytes(based['freed'])} frei)"
        msg += f" · {fmt_duration(time.monotonic() - t0)} · gesamt {fmt_bytes(sz.get('total', 0))}"
        return {"message": msg, "outputs": [], "log": lines, "logfile": logfile}

    def snap_startup(self) -> dict:
        """Beim Start (#54): je überwachtem Ordner schnelle Prüfung seit dem letzten Snapshot + fällig für heute?"""
        import datetime
        import snapshots
        st = self.snap_store
        today = datetime.date.today().isoformat()
        out = []
        t0 = time.time()
        libs = st.libraries() if os.path.isdir(st.root) else []
        labels = self._lib_labels(libs)
        for lib in libs:
            lib = {**lib, "name": labels[lib["id"]]}
            if not os.path.isdir(lib["root"]):
                out.append({"id": lib["id"], "name": lib["name"], "missing": True})
                continue
            last = st.latest(lib["id"])
            q = snapshots.quick_changes(lib["root"], last)
            out.append({"id": lib["id"], "name": lib["name"], "missing": False, **q,
                        "last": last and {"id": last["id"], "created": last["created"], "label": last["label"],
                                          "age": snapshots.fmt_age(last["created"])},
                        "due": lib.get("auto", True) and (not last or not any(s["created"][:10] == today and s.get("auto")
                                                                           for s in st.snapshots(lib["id"])))})
        if libs:
            try:                                       # #137: Dauer fürs App-Protokoll
                import applog
                applog.info(f"Snapshots-Startprüfung: {len(libs)} Ordner, {sum(x.get('total', 0) for x in out)} Datei(en), "
                            f"{time.time() - t0:.1f} s")
            except Exception:  # noqa: BLE001
                pass
        return {"libs": out, "ask": bool(self._snap_cfg("snap_ask")), "daily": bool(self._snap_cfg("snap_daily")),
                "hint": bool(self._snap_cfg("snap_hint"))}

    def snap_set(self, name, value) -> dict:
        if name not in self.SNAP_DEFAULTS:
            raise ValueError("Unbekannte Snapshot-Einstellung")
        d = self.SNAP_DEFAULTS[name]
        if isinstance(d, bool):
            value = bool(value)
        else:
            value = max(0, min(500, int(value)))
        self.cfg[name] = value
        core.save_config({name: value})
        return self.snap_overview()["settings"]

    # ------------------------------------------------------------------ Überwachung zur Laufzeit (#58)
    def snap_watch(self) -> dict:
        """Sparsame Abfrage: je überwachtem Ordner ein Listing + Grösse/Änderungszeit. Verglichen wird mit der
        vorigen Abfrage; Dateien, die TagStudio selbst gespeichert hat (Register, Tag-Bytes wie gespeichert),
        zählen nicht. Funde sammeln sich, bis sie mit snap_watch_ack quittiert werden."""
        import snapshots
        base = self.__dict__.setdefault("_watch_base", {})
        ext = self.__dict__.setdefault("_watch_ext", {})
        out = []
        st = self.snap_store
        libs = st.libraries() if os.path.isdir(st.root) else []
        for lib in libs:
            root = lib["root"]
            if not os.path.isdir(root):
                continue
            cur = {}
            for p in snapshots.list_mp3(root):
                try:
                    stt = os.stat(p)
                except OSError:
                    continue
                cur[snapshots.rel(root, p)] = (stt.st_size, stt.st_mtime_ns, p)
            prev = base.get(lib["id"])
            found = ext.setdefault(lib["id"], set())
            if prev is not None:
                for r, (size, mt, p) in cur.items():
                    old = prev.get(r)
                    if old is not None and old[:2] == (size, mt):
                        continue
                    f = self.reg.get(os.path.normcase(os.path.abspath(p)))
                    if old is not None and f is not None and not f.external_change():
                        continue                      # von TagStudio gespeichert
                    found.add(r)
                found.update(r for r in prev if r not in cur)
            base[lib["id"]] = cur
            if found:
                out.append({"id": lib["id"], "name": lib["name"], "count": len(found), "files": sorted(found)[:20]})
        return {"libs": out, "total": sum(x["count"] for x in out), "interval": int(self._snap_cfg("snap_watch") or 0)}

    def snap_watch_ack(self, lid=None) -> dict:
        ext = self.__dict__.setdefault("_watch_ext", {})
        for k in ([str(lid)] if lid else list(ext)):
            ext.pop(k, None)
        return {"ok": True}

    # ------------------------------------------------------------------ Speicherort (#60)
    def _snap_dir_set(self, root):
        import snapshots
        root = os.path.abspath(root)
        val = "" if os.path.normcase(root) == os.path.normcase(os.path.abspath(snapshots.default_dir())) else root
        self.cfg["snap_dir"] = val
        core.save_config({"snap_dir": val})
        self._snap_store = None

    def start_snap_move(self, dest):
        """Ganzen Snapshot-Speicher verschieben (kopieren, prüfen, alten entfernen) – mit Fortschritt."""
        import snapshots
        if self._jobs is not None and any(j["plugin"] == "tagstudio:snapshot" and j["status"] in ("queued", "running")
                                          for j in self.jobs.status()["jobs"]):
            return {"ok": False, "error": "Es läuft noch ein Snapshot-Auftrag – bitte warten."}
        dest = str(dest or snapshots.default_dir())
        src = self.snap_store.root

        def job(cancel, progress):
            res = snapshots.move_store(src, dest, cancel, progress)
            self._snap_dir_set(res["root"])
            return {**res, "message": f"Snapshot-Speicher verschoben nach {res['root']} "
                                      f"({res['files']} Dateien, {fmt_bytes(res['bytes'])})."}
        return self._run("snap_move", "Snapshot-Speicher verschieben", job)

    def snap_detect(self, path) -> dict | None:
        """Liegt in/über `path` ein anderer Snapshot-Speicher (z. B. mit dem MP3-Ordner weitergegeben)?"""
        import snapshots
        try:
            found = snapshots.find_store(str(path))
        except OSError:
            return None
        if not found:
            return None
        n = lambda p: os.path.normcase(os.path.abspath(p))
        if n(found) == n(self.snap_store.root) or n(found) in {n(p) for p in self.cfg.get("snap_ignored", [])}:
            return None
        try:
            return snapshots.summary(found)
        except snapshots.StoreError as ex:
            return {"root": found, "error": str(ex), "libs": []}

    def snap_use(self, root) -> dict:
        """Vorhandenen Speicher übernehmen (ohne Kopieren)."""
        import snapshots
        if not snapshots.is_store(str(root)):
            return {"ok": False, "error": "Dort liegt kein Snapshot-Speicher."}
        self._snap_dir_set(str(root))
        return {"ok": True, **self.snap_overview()}

    def snap_ignore(self, root) -> dict:
        lst = [p for p in self.cfg.get("snap_ignored", []) if p != root] + [str(root)]
        self.cfg["snap_ignored"] = lst[-50:]
        core.save_config({"snap_ignored": self.cfg["snap_ignored"]})
        return {"ok": True}

    # ------------------------------------------------------------------ Journal
    _GUESS_SKIP = {"tagstudio", "encoder", "id3v3", "id3v4", "unknown"}

    def _snap_guess(self, rows) -> dict:
        """#57: je Titel das vermutliche Programm aus der Herkunft der geänderten Felder (häufigste bekannte
        Herkunft; TKEY, BPM & Co. sagen allein nichts). → {sid: {"name", "rows", "fields"}}, "" = unbekannt."""
        cat = self.origin_catalog()
        progs: dict = {}
        for r in rows:
            n: dict = {}
            for fld in r["fields"]:
                sid = fld.get("src")
                if sid and sid not in self._GUESS_SKIP:
                    n[sid] = n.get(sid, 0) + 1
            g = max(n, key=lambda k: (n[k], k)) if n else ""
            if not r["fields"] and r["status"] not in ("changed", "rewrite"):
                g = None                      # neu/entfernt/umbenannt ohne Feldänderung: keine Vermutung
            r["guess"] = g
            if g is None:
                continue
            p = progs.setdefault(g, {"name": cat.get(g, {}).get("name", g) if g else "unbekannt", "rows": 0, "fields": 0})
            p["rows"] += 1
            p["fields"] += len(r["fields"])
        return progs

    def start_snap_journal(self, lid, a_sid, b_sid="live"):
        """Journal A → B (B = „live“ oder ein Snapshot) berechnen – mit Fortschritt."""
        import snapshots
        st = self.snap_store

        def job(cancel, progress):
            lib = st.library(str(lid))
            a = st.manifest(lib["id"], str(a_sid))
            if b_sid == "live":
                if not os.path.isdir(lib["root"]):
                    raise RuntimeError(f"Ordner nicht erreichbar: {lib['root']}")
                src_b = snapshots.MemStore(st)
                b_files, errors = snapshots.scan(lib["root"], src_b, a, False, cancel, progress)
                b_meta = {"id": "live", "label": "Jetzt", "created": ""}
            else:
                bm = st.manifest(lib["id"], str(b_sid))
                src_b, b_files, errors = st, bm["files"], []
                b_meta = {k: bm.get(k) for k in ("id", "label", "created")}
            progress(("text", "Vergleiche …"))
            j = snapshots.journal(a, b_files, st, src_b)
            for r in j["rows"]:
                for fld in r["fields"]:
                    fld["src"] = self._src(fld["key"], None)
            j["programs"] = self._snap_guess(j["rows"])
            self._jctx = {"lid": lib["id"], "root": lib["root"], "a": a, "A": {e["p"]: e for e in a["files"]},
                          "B": {e["p"]: e for e in b_files}}
            return {"rows": j["rows"], "counts": j["counts"], "programs": j["programs"], "errors": errors[:50], "root": lib["root"],
                    "a": {k: a.get(k) for k in ("id", "label", "created")}, "b": b_meta}
        return self._run("journal", "Änderungsjournal berechnen", job)

    def snap_revert(self, items, mode="undo", force_audio=False) -> dict:
        """Snapshot-Stand (A) auf die Live-Dateien zurück: items = [{"p", "p_old", "keys": [..]|None}].
        mode „undo“: Werte in die Dateien übernehmen (Rückgängig, Speichern nötig); „bytes“: Tag-Bytes exakt
        zurückschreiben (vorher Sicherung)."""
        import backup
        import snapshots
        ctx = getattr(self, "_jctx", None)
        if not ctx:
            return {"ok": False, "error": "Bitte zuerst das Journal berechnen."}
        st, done, errors = self.snap_store, 0, []
        plan = []
        for it in items or []:
            p, q = str(it.get("p") or ""), str(it.get("p_old") or it.get("p") or "")
            ea = ctx["A"].get(q)
            live = os.path.normpath(os.path.join(ctx["root"], p))
            if ea is None or not os.path.isfile(live) or not os.path.abspath(live).startswith(os.path.abspath(ctx["root"])):
                errors.append(f"{p}: nicht im Snapshot oder nicht mehr vorhanden")
                continue
            plan.append((p, live, ea, it.get("keys")))
        if mode == "bytes":
            bw = backup.BackupWriter(self._backup_folder(), label=f"Vor Snapshot-Wiederherstellung ({len(plan)} Datei(en))") \
                if plan else None
            for p, live, ea, _keys in plan:
                info = snapshots.read_tags(live)
                if snapshots.audio_key(live, info) != ea["audio"] and not force_audio:
                    errors.append(f"{p}: Audio hat sich geändert – übersprungen")
                    continue
                k = os.path.normcase(os.path.abspath(live))
                f = self.reg.get(k)
                if f is not None and f.is_modified():
                    errors.append(f"{p}: hat ungespeicherte Änderungen in TagStudio – übersprungen")
                    continue
                try:
                    bw.add(live)
                    tag, v1 = st.tag_bytes(ea)
                    backup._write_tags(live, tag, v1)
                    if f is not None:
                        f.load()
                    done += 1
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"{p}: {ex}")
            if bw:
                try:
                    bw.close()
                except Exception:  # noqa: BLE001
                    pass
            return {"ok": True, "done": done, "errors": errors, "saved": True,
                    "message": f"{done} Datei(en) byte-genau auf den Snapshot-Stand zurückgeschrieben."}
        with self.lock:
            files = []
            for p, live, ea, keys in plan:
                k = os.path.normcase(os.path.abspath(live))
                f = self.reg.get(k) or core._open(live, self.reg)
                old = snapshots._mp3(*st.tag_bytes(ea))
                ks = list(keys) if keys else sorted(set(old.items) | set(f.items))
                files.append((f, old, ks, not keys))
            if not files:
                return {"ok": False, "error": "; ".join(errors) or "Nichts zurückzusetzen."}
            self.undo.checkpoint(f"Snapshot-Stand für {len(files)} Datei(en)", [f for f, *_ in files])
            n = 0
            for f, old, ks, whole in files:
                for k in ks:
                    if k.startswith("APIC") and k not in old.items and k not in f.items:
                        continue
                    if f.items.get(k) != old.items.get(k):
                        f.set(k, old.items.get(k).clone() if old.items.get(k) is not None else None)
                        n += 1
                if whole and old.version in (3, 4) and f.version != old.version:
                    f.set_version(old.version)
                done += 1
            self.undo.commit()
        return {"ok": True, "done": done, "fields": n, "errors": errors, "saved": False, "unsaved": self.unsaved(),
                "message": f"{n} Feld(er) in {done} Datei(en) auf den Snapshot-Stand gesetzt – noch nicht gespeichert."}
