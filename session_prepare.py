"""Session-Teil „Vorbereiten“ (#109–#116): Workflows verwalten, Schritte ausführen, Status, Schutzregel, Übernahme."""
from __future__ import annotations

import json
import os

import core
import prepare
import tsmeta


def plugins_write_log(name, text):
    import plugins
    return plugins.write_log(name, text)


class PrepareMixin:
    # ------------------------------------------------------------------ Workflows
    def _prep_workflows(self) -> list:
        ws = self.cfg.get("prep_workflows")
        out = []
        for w in ws if isinstance(ws, list) else []:
            try:
                out.append(prepare.clean_workflow(w))
            except ValueError:
                continue
        return out

    def _prep_save(self, ws):
        self.cfg["prep_workflows"] = ws
        core.save_config({"prep_workflows": ws})

    def _prep_get(self, wid=None) -> dict:
        ws = self._prep_workflows()
        if not ws:
            w = prepare.template()
            ws = [w]
            self._prep_save(ws)
        wid = wid or self.cfg.get("prep_current")
        return next((w for w in ws if w["id"] == wid), ws[0])

    def prep_workflow_save(self, w) -> dict:
        w = prepare.clean_workflow(w)
        ws = [x for x in self._prep_workflows() if x["id"] != w["id"]]
        ws.append(w)
        self._prep_save(ws)
        self.cfg["prep_current"] = w["id"]
        core.save_config({"prep_current": w["id"]})
        return self.prep_overview(w["id"])

    def prep_workflow_new(self, from_id=None) -> dict:
        base = self._prep_get(from_id) if from_id else prepare.template()
        w = json.loads(json.dumps(base))
        w["id"] = prepare.template()["id"]
        w["name"] = (base["name"] + " (Kopie)") if from_id else base["name"]
        return self.prep_workflow_save(w)

    def prep_workflow_delete(self, wid) -> dict:
        ws = [x for x in self._prep_workflows() if x["id"] != wid]
        self._prep_save(ws)
        self.cfg["prep_current"] = ws[0]["id"] if ws else ""
        core.save_config({"prep_current": self.cfg["prep_current"]})
        return self.prep_overview()

    def prep_export(self, wid) -> str:
        """Workflow als JSON zum Weitergeben – ohne persönliche Ordner und Programmpfade."""
        w = json.loads(json.dumps(self._prep_get(wid)))
        w["inbox"] = w["work"] = w["library"] = ""
        for q in w.get("sources") or []:
            q["folder"] = ""
        for s in w["steps"]:
            if "program" in s:
                s["program"] = ""
        return json.dumps({"tagstudio_workflow": 1, **w}, ensure_ascii=False, indent=2)

    def prep_import(self, text) -> dict:
        try:
            d = json.loads(text)
        except ValueError as ex:
            raise ValueError(f"Kein gültiges JSON: {ex}") from ex
        d.pop("tagstudio_workflow", None)
        d["id"] = prepare.template()["id"]
        return self.prep_workflow_save(d)

    def prep_pending(self) -> dict:
        """Für die Seitenleiste: Titel im Eingang, die noch nicht übernommen sind (alle Workflows, ohne Tags zu lesen)."""
        total, new, waiting = 0, 0, 0
        for w in self._prep_workflows():
            if not w.get("inbox"):
                continue
            st = prepare.load_state(w["id"])
            for q in w.get("sources") or []:
                waiting += len(prepare.source_candidates(q, st))
            imp = next((s["id"] for s in w["steps"] if s["type"] == "import"), None)
            for n in prepare.list_inbox(w):
                t = st["tracks"].get(n)
                if t is None:
                    new += 1
                if not imp or (((t or {}).get("steps") or {}).get(imp) or {}).get("state") not in ("done", "warn"):
                    total += 1
        return {"count": total, "new": new, "sources": waiting}

    # ------------------------------------------------------------------ Übersicht
    def prep_overview(self, wid=None) -> dict:
        w = self._prep_get(wid)
        st = prepare.load_state(w["id"])
        names = prepare.list_inbox(w)
        for n in st["tracks"]:
            if n not in names:
                names.append(n)
        rows = []
        counts = {s["id"]: {} for s in w["steps"]}
        for n in names:
            t = st["tracks"].get(n, {})
            cells = []
            for i, s in enumerate(w["steps"]):
                rec = (t.get("steps") or {}).get(s["id"]) or {}
                state = rec.get("state") or ("open" if prepare.step_ready(w, st, n, i) else "blocked")
                counts[s["id"]][state] = counts[s["id"]].get(state, 0) + 1
                cells.append({"state": state, "note": rec.get("note", ""), "at": rec.get("at", ""),
                              "viol": rec.get("viol") or []})
            path = prepare.track_path(w, st, n)
            rows.append({"name": n, "cells": cells, "path": path, "exists": os.path.isfile(path),
                         "source": t.get("source", ""), "origin_file": t.get("origin_file", ""),
                         "missing_inbox": not os.path.isfile(os.path.join(w["inbox"], n)) if w["inbox"] else True})
        waiting = {q["id"]: len(prepare.source_candidates(q, st)) for q in w.get("sources") or []}
        return {"workflow": w, "sources_new": waiting, "workflows": [{"id": x["id"], "name": x["name"]} for x in self._prep_workflows()],
                "rows": rows, "counts": counts, "types": prepare.STEP_TYPES, "states": prepare.STATES,
                "plugin_modes": prepare.PLUGIN_MODES,
                "work": prepare.work_dir(w), "origins": {k: v.get("name") for k, v in self.origin_catalog().items()}}

    # ------------------------------------------------------------------ Schritte
    def _prep_step(self, w, sid):
        i = next((k for k, s in enumerate(w["steps"]) if s["id"] == sid), None)
        if i is None:
            raise ValueError("Schritt nicht gefunden.")
        return i, w["steps"][i]

    def _prep_finish(self, w, s, rec, path, manual=False):
        """Schritt abschliessen: Schutzregel prüfen (#114), Zustand setzen."""
        before = rec.pop("before", None)
        rec["viol"] = []
        if before is not None and os.path.isfile(path):
            v = prepare.violations(w, s, before, prepare.tag_values(path))
            if v and w["protect"]["on_violation"] == "revert":
                n = prepare.revert_values(path, v)
                rec["note"] = f"{n} Feld(er) automatisch zurückgesetzt"
                v = [x for x in v if x.get("binary")]
            rec["viol"] = v
        rec["state"] = "warn" if rec["viol"] else "done"
        rec["at"] = prepare.now()
        if manual and not rec.get("note"):
            rec["note"] = "bestätigt"

    def start_prep_run(self, wid, sid, names=None, force=False):
        """Schritt für die gewählten (bzw. alle bereiten) Titel ausführen – Rezept, Übernahme, externes Programm."""
        w = self._prep_get(wid)
        i, s = self._prep_step(w, sid)
        if s["type"] == "check":
            return {"ok": False, "error": "Status-Schritte werden erkannt oder von Hand bestätigt."}
        st = prepare.load_state(w["id"])
        todo = [n for n in (names or prepare.list_inbox(w)) if prepare.step_ready(w, st, n, i)
                and ((st["tracks"].get(n, {}).get("steps") or {}).get(sid) or {}).get("state") in (None, "open", "error")
                or (force and n in (names or []))]
        if not todo:
            return {"ok": False, "error": "Keine Titel bereit für diesen Schritt (vorherige Schritte zuerst erledigen)."}
        for need, what in ((w["inbox"], "Eingangsordner"), (prepare.work_dir(w) if s.get("folder") else "x", "Arbeitsordner"),
                           (w["library"] if s["type"] == "import" else "x", "Bibliotheksordner")):
            if not need or (need != "x" and not os.path.isdir(need)):
                return {"ok": False, "error": f"{what} fehlt oder ist nicht erreichbar – Workflow bearbeiten."}

        def job(cancel, progress):
            import recipes
            done, errors, launched = 0, [], ""
            progress(("total", len(todo)))
            lib_files = None
            if s["type"] == "import" and s.get("dup", True):
                progress(("text", "Lese die Bibliothek (Duplikatprüfung) …"))
                lib_files, _e = core.load_files(w["library"], True, cancel, None, None, self._list_cache_on())
            recipe = None
            if s["type"] == "recipe":
                recipe = next((r for r in self.recipes()["recipes"] if r["id"] == s.get("recipe")), None)
                if recipe is None:
                    raise RuntimeError(f"Rezept „{s.get('recipe')}“ nicht gefunden (Tagger › Tag-Rezepte).")
            if s["type"] == "plugin":
                try:
                    self.plugins.action(s.get("plugin"), s.get("action"))
                except (KeyError, ValueError) as ex:
                    raise RuntimeError(f"Plugin-Schritt „{s['label']}“: {ex.args[0] if ex.args else ex} (Workflow bearbeiten bzw. Plugin-Seite).") from ex
            ext_files, ext_folder = [], ""
            plug = []        # (Name, Datei-Objekt, Zustand) für den Plugin-Lauf nach dem Kopieren
            for k, n in enumerate(todo, 1):
                if cancel.is_set():
                    break
                progress(("progress", k, len(todo), n))
                t = st["tracks"].setdefault(n, {"added": prepare.now(), "steps": {}})
                rec = t.setdefault("steps", {}).setdefault(sid, {})
                rec.update(note="", viol=[])
                src = prepare.track_path(w, st, n, upto=i)
                try:
                    if not os.path.isfile(src):
                        raise RuntimeError(f"Datei fehlt: {src}")
                    if s["type"] == "recipe":
                        from id3tags import MP3File
                        dst = os.path.join(prepare.work_dir(w), s["folder"], n)
                        prepare.copy_file(src, dst)
                        f = MP3File(dst)
                        p = recipes.plan([f], recipe)
                        recipes.apply(p)
                        if self.cfg.get("stamp_edited", True):
                            tsmeta.stamp_edited(f)          # #185
                        f.save()
                        rec.update(state="done", at=prepare.now(), file=dst,
                                   note=f"{sum(len(e['changes']) for e in p)} Änderung(en)")
                    elif s["type"] == "import":
                        dst = os.path.join(w["library"], n)
                        dups = prepare.duplicates(src, lib_files or [], dst) if s.get("dup", True) else []
                        if dups and not force:
                            rec.update(state="error", at=prepare.now(), note="; ".join(dups))
                            errors.append(f"{n}: {dups[0]}")
                            continue
                        prepare.copy_file(src, dst)
                        if self.cfg.get("stamp_added", True):             # #184: Zeitpunkt der Aufnahme, nie überschreiben
                            from id3tags import MP3File
                            fa = MP3File(dst)
                            if tsmeta.set_added(fa):
                                fa.save()
                        t["lib_baseline"] = prepare.tag_values(dst)
                        rec.update(state="done", at=prepare.now(), file=dst, note="übernommen" + (" (trotz Hinweis)" if dups else ""))
                    elif s["type"] == "verify":
                        miss = prepare.missing_fields(src, s.get("fields"))
                        if miss:
                            rec.update(state="error", at=prepare.now(), file=src, note="fehlt: " + ", ".join(miss))
                            errors.append(f"{n}: fehlt {', '.join(miss)}")
                            continue
                        rec.update(state="done", at=prepare.now(), file=src, note="vollständig")
                    elif s["type"] == "plugin":
                        from id3tags import MP3File
                        dst = os.path.join(prepare.work_dir(w), s["folder"], n)
                        prepare.copy_file(src, dst)
                        if s.get("protect"):
                            rec["before"] = prepare.tag_values(dst)
                        rec.update(state="waiting", at=prepare.now(), file=dst)
                        plug.append((n, MP3File(dst), rec))
                        continue
                    else:   # external
                        path = src
                        if s.get("copy") and s.get("folder"):
                            path = os.path.join(prepare.work_dir(w), s["folder"], n)
                            prepare.copy_file(src, path)
                        if s.get("protect"):
                            rec["before"] = prepare.tag_values(path)
                        rec.update(state="waiting", at=prepare.now(), file=path)
                        ext_files.append(path)
                        ext_folder = os.path.dirname(path)
                    done += 1
                except Exception as ex:  # noqa: BLE001
                    rec.update(state="error", at=prepare.now(), note=str(ex))
                    errors.append(f"{n}: {ex}")
            if plug and not cancel.is_set():
                done += self._prep_plugin(w, s, plug, errors, cancel, progress)
            for _n, _f, rec in plug:              # abgebrochen oder Fehler im Lauf → wieder offen
                if rec.get("state") == "waiting":
                    rec.pop("before", None)
                    rec.update(state="error", note=rec.get("note") or "abgebrochen")
            prepare.save_state(w["id"], st)
            if s["type"] == "external" and ext_files:
                if s.get("program"):
                    try:
                        launched = prepare.launch(s["program"], s.get("args", "{folder}"), ext_folder, ext_files)
                    except (ValueError, OSError) as ex:
                        errors.append(str(ex))
            snap = ""
            if s["type"] == "import" and done:
                lib = next((l for l in self.snap_store.libraries()
                            if os.path.normcase(os.path.abspath(l.get("root") or "")) == os.path.normcase(os.path.abspath(w["library"]))), None) \
                    if self._snap_store_ok() else None
                if lib:
                    self.snap_create(lib["id"], f"Nach Übernahme ({done} Titel)")
                    snap = lib["name"]
            return {"done": done, "errors": errors[:50], "launched": launched, "folder": ext_folder, "snapshot": snap,
                    "step": s["label"]}
        return self._run("prep", f"Vorbereiten: {s['label']}", job)

    def start_prep_fetch(self, wid, qids=None):
        """Quellen abholen (#118): neue Downloads (MP3, ZIP) in den Eingangsordner kopieren."""
        w = self._prep_get(wid)
        if not w["inbox"] or not os.path.isdir(w["inbox"]):
            return {"ok": False, "error": "Eingangsordner fehlt oder ist nicht erreichbar – Workflow bearbeiten."}
        qs = [q for q in w.get("sources") or [] if not qids or q["id"] in qids]
        if not qs:
            return {"ok": False, "error": "Keine Quellen festgelegt (Workflow bearbeiten › Quellen)."}

        def job(cancel, progress):
            st = prepare.load_state(w["id"])
            got, same, errors, per = [], 0, [], []
            for q in qs:
                if not os.path.isdir(q["folder"]):
                    errors.append(f"{q['name']}: Ordner nicht erreichbar ({q['folder']})")
                    continue
                progress(("text", f"Quelle {q['name']} …"))
                r = prepare.fetch_source(w, q, st, cancel, progress)
                got += r["got"]
                same += r["same"]
                errors += [f"{q['name']}: {e}" for e in r["errors"]]
                per.append(f"{q['name']}: {len(r['got'])}")
                prepare.save_state(w["id"], st)
            return {"got": got, "same": same, "errors": errors[:50], "per": per}
        return self._run("prep", "Quellen abholen", job)

    def _prep_plugin(self, w, s, plug, errors, cancel, progress) -> int:
        """Plugin-Aktion auf die Stufen-Kopien anwenden, Vorschläge je nach Modus übernehmen und speichern."""
        import importsync
        import tagger
        pid, aid = s["plugin"], s["action"]
        opts = self.cfg.get("plugin_options", {}).get(pid, {}).get(aid, {})
        files = [f for _n, f, _r in plug]
        progress(("text", f"{s['label']}: Plugin läuft …"))
        try:
            res = self.plugins.run(pid, aid, files, opts, None, cancel, progress)
        except Exception as ex:  # noqa: BLE001
            import traceback
            path = plugins_write_log(f"{pid}.log", traceback.format_exc())
            for _n, _f, rec in plug:
                rec.update(state="error", note=str(ex) or type(ex).__name__)
            errors.append(f"{s['label']}: {ex} (Protokoll: {path})")
            return 0
        if res.get("cancelled"):
            return 0
        if res.get("log"):
            plugins_write_log(f"{pid}.log", "\n".join(res["log"]))
        chosen = prepare.pick_proposals(res.get("proposals") or [], s.get("mode", "fill"))
        by_file: dict[int, list] = {}
        for p in chosen:
            by_file.setdefault(id(p["file"]), []).append(p)
        props_all: dict[int, int] = {}
        for p in res.get("proposals") or []:
            if not p.get("same"):
                props_all[id(p["file"])] = props_all.get(id(p["file"]), 0) + 1
        done = 0
        for n, f, rec in plug:
            mine = by_file.get(id(f), [])
            try:
                k = 0
                for p in mine:
                    if p["kind"] == "cover":
                        if p["data"]:
                            tagger.set_cover([f], p["data"])
                            k += 1
                    elif core.apply_value(f, p["key"], p["new"]):
                        k += 1
                    if p.get("sync"):
                        importsync.remember(f, *p["sync"])
                if mine:
                    for sync in mine[0].get("sync_same") or []:
                        importsync.remember(f, *sync)
                if self.cfg.get("stamp_edited", True):
                    tsmeta.stamp_edited(f)          # #185 (nur bei Änderungen)
                f.save()          # speichert nur bei Änderungen
                rest = props_all.get(id(f), 0) - len(mine)
                rec["note"] = f"{k} Feld(er) übernommen" + (f", {rest} Vorschlag/Vorschläge nicht übernommen" if rest > 0 else "")
                self._prep_finish(w, s, rec, rec["file"])
                done += 1
            except Exception as ex:  # noqa: BLE001
                rec.pop("before", None)
                rec.update(state="error", at=prepare.now(), note=str(ex))
                errors.append(f"{n}: {ex}")
        return done

    def _snap_store_ok(self) -> bool:
        try:
            return not self.snap_store.readonly
        except Exception:  # noqa: BLE001
            return False

    def prep_refresh(self, wid=None) -> dict:
        """Wartende externe Schritte und Status-Schritte erkennen (Herkunfts-Kennzeichen)."""
        w = self._prep_get(wid)
        st = prepare.load_state(w["id"])
        found = 0
        names = set(prepare.list_inbox(w)) | set(st["tracks"])
        for n in names:
            t = st["tracks"].setdefault(n, {"added": prepare.now(), "steps": {}})
            for i, s in enumerate(w["steps"]):
                rec = (t.get("steps") or {}).get(s["id"]) or {}
                if s["type"] == "external" and rec.get("state") == "waiting" and s.get("detect"):
                    if prepare.detect(rec.get("file", ""), s["detect"], self.origins.of):
                        self._prep_finish(w, s, rec, rec["file"])
                        rec["note"] = rec.get("note") or "erkannt"
                        found += 1
                elif s["type"] == "check" and rec.get("state") in (None, "open") and s.get("detect") \
                        and prepare.step_ready(w, st, n, i):
                    path = prepare.track_path(w, st, n)
                    if prepare.detect(path, s["detect"], self.origins.of):
                        rec = t["steps"].setdefault(s["id"], {})
                        if s.get("protect") and t.get("lib_baseline") is not None:
                            rec["before"] = t["lib_baseline"]
                        self._prep_finish(w, s, rec, path)
                        rec["note"] = rec.get("note") or "erkannt"
                        t["lib_baseline"] = prepare.tag_values(path)
                        found += 1
        prepare.save_state(w["id"], st)
        d = self.prep_overview(w["id"])
        d["message"] = f"{found} Schritt(e) erkannt." if found else ""
        return d

    def prep_mark(self, wid, sid, names, state="done") -> dict:
        """Von Hand: erledigt (mit Schutzregel), übersprungen oder wieder offen."""
        w = self._prep_get(wid)
        i, s = self._prep_step(w, sid)
        st = prepare.load_state(w["id"])
        for n in names or []:
            t = st["tracks"].setdefault(n, {"added": prepare.now(), "steps": {}})
            rec = t.setdefault("steps", {}).setdefault(sid, {})
            if state == "open":
                t["steps"].pop(sid, None)
            elif state == "skipped":
                rec.update(state="skipped", at=prepare.now(), note="übersprungen", viol=[])
                rec.pop("before", None)
            else:
                path = rec.get("file") or prepare.track_path(w, st, n)
                if s["type"] == "check" and s.get("protect") and t.get("lib_baseline") is not None:
                    rec["before"] = t["lib_baseline"]
                self._prep_finish(w, s, rec, path, manual=True)
                if s["type"] == "check" and os.path.isfile(path):
                    t["lib_baseline"] = prepare.tag_values(path)
        prepare.save_state(w["id"], st)
        return self.prep_overview(w["id"])

    def prep_revert(self, wid, sid, name) -> dict:
        """Gemeldete Verstösse gegen die Schutzregel zurücksetzen (Textfelder)."""
        w = self._prep_get(wid)
        _i, s = self._prep_step(w, sid)
        st = prepare.load_state(w["id"])
        t = st["tracks"].get(name) or {}
        rec = (t.get("steps") or {}).get(sid) or {}
        path = rec.get("file") or prepare.track_path(w, st, name)
        n = prepare.revert_values(path, rec.get("viol") or [])
        rec["viol"] = [x for x in rec.get("viol") or [] if x.get("binary")]
        rec["state"] = "warn" if rec["viol"] else "done"
        rec["note"] = f"{n} Feld(er) zurückgesetzt"
        prepare.save_state(w["id"], st)
        d = self.prep_overview(w["id"])
        d["message"] = f"{n} Feld(er) zurückgesetzt."
        return d

    def prep_allow(self, wid, sid, key) -> dict:
        """„Feld künftig erlauben“: Muster in die erlaubten Felder des Schritts übernehmen."""
        w = self._prep_get(wid)
        _i, s = self._prep_step(w, sid)
        if key not in s.setdefault("allow", []):
            s["allow"].append(key)
        return self.prep_workflow_save(w)

    def prep_cleanup(self, wid, names=None, apply=False) -> dict:
        """Stufen-Kopien übernommener Titel auflisten bzw. (nach Rückfrage in der Oberfläche) löschen."""
        w = self._prep_get(wid)
        st = prepare.load_state(w["id"])
        imp = [s for s in w["steps"] if s["type"] == "import"]
        files = []
        for n, t in st["tracks"].items():
            if names and n not in names:
                continue
            if not imp or ((t.get("steps") or {}).get(imp[0]["id"]) or {}).get("state") not in ("done", "warn"):
                continue
            for s in w["steps"]:
                if s.get("folder"):
                    p = os.path.join(prepare.work_dir(w), s["folder"], n)
                    if os.path.isfile(p):
                        files.append(p)
        if not apply:
            return {"files": files, "count": len(files)}
        gone = 0
        for p in files:
            try:
                os.remove(p)
                gone += 1
            except OSError:
                pass
        return {"removed": gone, "count": len(files)}
