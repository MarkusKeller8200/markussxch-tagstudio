"""Session-Teil „Mix analysieren“ (#387): Ergebnisse des Plugins `mixscan` ansehen, bearbeiten, vorhören und als
Playlist (Ordner „Mixe“), CUE-Datei oder Text ausgeben; fehlende Titel einer bekannten Tracklist als Ideen merken.
Logik ohne Oberfläche in mixresult.py; die Analyse selbst läuft im Plugin."""
from __future__ import annotations

import os

import mixresult
import paths

PLUGIN = "mixscan"


class MixesMixin:
    def _mix_dir(self) -> str:
        return paths.sub("Mixe")

    def _mix_store(self, res: dict) -> str:
        """Neues Ergebnis eines Plugin-Laufs ablegen → Kennung."""
        r = mixresult.new(res.get("mix", ""), res.get("duration", 0), res.get("rows") or [], compare=res.get("compare"),
                          report=res.get("report", ""), index=res.get("index", ""), plugin=PLUGIN, version=res.get("version", ""))
        mixresult.save(self._mix_dir(), r)
        return r["id"]

    def _mix_ready(self) -> bool:
        try:
            p = self.plugins.get(PLUGIN)
        except KeyError:
            return False
        return bool(p.enabled and p.state() == "ready")

    # ------------------------------------------------------------------ Abruf
    def mix_list(self) -> dict:
        """Gespeicherte Analysen und Stand des Plugins (für die Seite „Mixe“, #390)."""
        info = {"found": False}
        try:
            p = self.plugins.get(PLUGIN)
            d = p.info()
            info = {"found": True, "enabled": bool(d.get("enabled")), "state": d.get("state", ""),
                    "version": d.get("version", ""), "status": d.get("status_text", "")}
        except KeyError:
            pass
        return {"items": mixresult.listing(self._mix_dir()), "ready": self._mix_ready(), "plugin": info}

    def _mix_retain(self) -> dict:
        """#393: Aufbewahrung der Online-Treffer je Erkennungsdienst (Tage oder None = behalten)."""
        try:
            return {r["id"]: r.get("retain_days") for r in self.plugins.recognizers(self) if "retain_days" in r}
        except Exception:  # noqa: BLE001
            return {}

    def mix_get(self, rid) -> dict:
        res = mixresult.load(self._mix_dir(), rid)
        if any(r.get("online") for r in res["rows"]) and mixresult.purge_online(res, self._mix_retain()):
            mixresult.save(self._mix_dir(), res)
        lines = []
        for e in mixresult.with_gaps(res):
            if e.get("gap"):
                lines.append({"gap": True, "start": e["start"], "end": e["end"]})
                continue
            r = e["row"]
            lines.append({"n": e["n"], "at": mixresult.mark(r), "start": r["start"], "end": r["end"],
                          "track_start": r.get("track_start"), "artist": r["artist"], "title": r["title"], "path": r["path"],
                          "exists": bool(r["path"]) and os.path.isfile(r["path"]), "tempo": r["tempo"],
                          "keylock": r["keylock"], "conf": r["conf"], "sure": r["conf"] >= mixresult.SURE,
                          "also": r.get("also") or [], "edited": r.get("at") is not None,
                          "online": (r.get("online") or {}).get("name", "")})
        dropped = [{"n": n, "artist": r["artist"], "title": r["title"], "start": r["start"], "online": bool(r.get("online"))}
                   for n, r in enumerate(res["rows"]) if r.get("drop")]
        pl = res.get("playlist") or ""
        with self.lock:
            st = self._pls()
            if pl and (not st.exists(pl) or st.get(pl).get("archived")):
                pl = ""
        cmp = res.get("compare")
        return {"id": res["id"], "name": res.get("name", ""), "mix": res.get("mix", ""), "created": res.get("created", ""),
                "duration": res.get("duration", 0), "mix_exists": os.path.isfile(res.get("mix", "")),
                "lines": lines, "dropped": dropped, "report": res.get("report", "") if os.path.isfile(res.get("report", "")) else "",
                "index": res.get("index", ""), "version": res.get("version", ""), "playlist": pl,
                "compare": cmp, "missing": (cmp or {}).get("miss") or [], "text": mixresult.to_text(res),
                "gaps": len(mixresult.gaps(res)),
                "online": sum(1 for _n, r in mixresult.kept(res) if r.get("online"))}

    # ------------------------------------------------------------------ Bearbeiten
    def _mix_change(self, rid, fn) -> dict:
        d = self._mix_dir()
        res = mixresult.load(d, rid)
        fn(res)
        mixresult.save(d, res)
        return self.mix_get(rid)

    def _mix_row(self, res, n) -> dict:
        try:
            return res["rows"][int(n)]
        except (TypeError, ValueError, IndexError) as ex:
            raise ValueError("Diese Zeile gibt es nicht.") from ex

    def mix_drop(self, rid, n, drop=True) -> dict:
        """Treffer verwerfen bzw. zurückholen."""
        def fn(res):
            r = self._mix_row(res, n)
            if drop:
                r["drop"] = True
            else:
                r.pop("drop", None)
        return self._mix_change(rid, fn)

    def mix_set_time(self, rid, n, text) -> dict:
        """Zeit in der Tracklist von Hand setzen („12:30“); leer = wieder berechnen."""
        def fn(res):
            r = self._mix_row(res, n)
            if not str(text or "").strip():
                r.pop("at", None)
                return
            t = mixresult.parse_time(text)
            if t is None:
                raise ValueError("Zeit bitte als „mm:ss“ oder „h:mm:ss“.")
            if res.get("duration") and t > res["duration"]:
                raise ValueError("Die Zeit liegt nach dem Ende des Mixes.")
            r["at"] = t
        return self._mix_change(rid, fn)

    def mix_rename(self, rid, name) -> dict:
        name = str(name or "").strip()[:200]
        if not name:
            raise ValueError("Bitte einen Namen eingeben.")
        return self._mix_change(rid, lambda res: res.__setitem__("name", name))

    def mix_delete(self, rid) -> dict:
        """Ergebnis löschen (nur die Analyse – Mix, Titel und gespeicherte Playlist bleiben)."""
        mixresult.remove(self._mix_dir(), rid)
        return self.mix_list()

    # ------------------------------------------------------------------ Vorhören
    def mix_audio(self, rid, n=None) -> dict:
        """Adresse zum Vorhören: der Mix (n = None) oder der erkannte Titel n – nur Dateien dieses Ergebnisses."""
        import media
        res = mixresult.load(self._mix_dir(), rid)
        if n is None or n == "":
            path = res.get("mix", "")
        else:
            path = self._mix_row(res, n)["path"]
        if not path or not os.path.isfile(path):
            raise ValueError("Die Datei gibt es nicht mehr.")
        return {"url": media.SERVER.register(path), "path": path}

    # ------------------------------------------------------------------ Ausgeben
    def mix_to_playlist(self, rid, name="") -> dict:
        """Als Playlist im Ordner „Mixe“ speichern; erneut gespeichert wird dieselbe Playlist nachgeführt."""
        d = self._mix_dir()
        res = mixresult.load(d, rid)
        items = mixresult.to_items(res)
        if not items:
            raise ValueError("Keine Titel zum Speichern – alle Treffer verworfen.")
        with self.lock:
            st = self._pls()
            pid = res.get("playlist") or ""
            if pid and st.exists(pid) and not st.get(pid).get("archived"):
                pl = st.update(pid, "Mix nachführen", items=items)
                msg = f"Playlist „{pl['name']}“ nachgeführt ({len(items)} Titel)."
            else:
                pl = st.create(st.unique_name(name or res.get("name") or "Mix", mixresult.FOLDER), mixresult.FOLDER, "import",
                               items, source="mixscan", note=f"Erkannt aus {os.path.basename(res.get('mix', ''))}"[:500])
                msg = f"Playlist „{pl['name']}“ im Ordner „{mixresult.FOLDER}“ angelegt ({len(items)} Titel)."
            st.touch(pl["id"])
        res["playlist"] = pl["id"]
        mixresult.save(d, res)
        return {"ok": True, "playlist": pl["id"], "message": msg}

    def mix_export_name(self, rid, fmt) -> str:
        res = mixresult.load(self._mix_dir(), rid)
        stem = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in (res.get("name") or "Mix")).strip(" .") or "Mix"
        return stem + (".cue" if fmt == "cue" else ".txt")

    def mix_cue_beside(self, rid) -> str:
        """Vorschlag für die CUE-Datei: neben dem Mix (gleicher Name, Endung .cue)."""
        res = mixresult.load(self._mix_dir(), rid)
        return os.path.splitext(res.get("mix", ""))[0] + ".cue" if res.get("mix") else ""

    def mix_export_write(self, rid, fmt, dest, overwrite=False) -> dict:
        res = mixresult.load(self._mix_dir(), rid)
        dest = str(dest or "")
        if not dest:
            return {"ok": False, "cancelled": True}
        if fmt not in ("cue", "txt"):
            raise ValueError("Unbekanntes Format.")
        if os.path.exists(dest) and not overwrite:
            return {"ok": False, "exists": True, "path": dest}
        text = mixresult.to_cue(res, dest) if fmt == "cue" else mixresult.to_text(res)
        with open(dest, "w", encoding="utf-8-sig" if fmt == "cue" else "utf-8", newline="\r\n" if fmt == "cue" else None) as fh:
            fh.write(text)
        return {"ok": True, "path": dest, "message": f"{'CUE-Datei' if fmt == 'cue' else 'Tracklist'} gespeichert: {os.path.basename(dest)}"}

    def mix_missing_to_ideas(self, rid, pid="", name="") -> dict:
        """Titel der bekannten Tracklist, die nicht in der Bibliothek sind, als Ideen merken (#186)."""
        res = mixresult.load(self._mix_dir(), rid)
        text = mixresult.missing_text(res)
        if not text.strip():
            raise ValueError("Keine fehlenden Titel – alle Titel der Tracklist wurden gefunden.")
        import ideas
        new, _unknown = ideas.from_text(text)
        if not new:
            raise ValueError("Keine Titel erkannt.")
        return self._ideas_add(pid, name, new)

    # ------------------------------------------------------------------ #393 „MixID light“: Lücken online erkennen
    def mix_gaps_info(self, rid) -> dict:
        """Lücken des Ergebnisses und die Erkennungsdienste (Plugins mit identify_clip) mit Kosten und Kontingent."""
        res = mixresult.load(self._mix_dir(), rid)
        recs = self.plugins.recognizers(self)
        return {"gaps": [{"start": a, "end": b} for a, b in mixresult.gaps(res)], "recognizers": recs,
                "mix_exists": os.path.isfile(res.get("mix", ""))}

    def mix_gaps_plan(self, rid, pid="", seconds=30, max_clips=10, only=None) -> dict:
        """Kostenvorschau: Zahl der Ausschnitte und Kosten (nichts wird hochgeladen)."""
        res = mixresult.load(self._mix_dir(), rid)
        rec = self._mix_recognizer(pid)
        clips = mixresult.plan_clips(res, seconds, max_clips, only)
        all_clips = mixresult.plan_clips(res, seconds, 10_000, only)
        each = int((rec.get("cost") or {}).get(str(int(seconds)), 0) or 0)
        return {"clips": len(clips), "more": max(0, len(all_clips) - len(clips)), "each": each, "cost": each * len(clips),
                "unit": rec.get("unit", ""), "rest": rec.get("rest"), "quota": rec.get("quota", ""),
                "gaps": len({c["gap"] for c in clips}), "name": rec.get("name", "")}

    def _mix_recognizer(self, pid="") -> dict:
        recs = [r for r in self.plugins.recognizers(self) if not pid or r["id"] == pid]
        if not recs:
            raise ValueError("Kein Erkennungsdienst eingeschaltet – das Plugin SonoVault einschalten und den Schlüssel "
                             "eintragen (Audio-Erkennung braucht einen bezahlten Tarif bzw. Kredite).")
        rec = recs[0]
        if not rec.get("ready"):
            raise ValueError(f"{rec['name']}: {rec.get('why') or 'nicht bereit'}.")
        return rec

    def start_mix_gaps(self, rid, opts=None):
        """Ausschnitte der Lücken an den Erkennungsdienst senden und Treffer als Zeilen „online“ übernehmen."""
        o = opts or {}
        if not o.get("confirm"):
            return {"ok": False, "error": "Kosten und Hochladen zuerst bestätigen."}
        d = self._mix_dir()
        res = mixresult.load(d, rid)
        if not os.path.isfile(res.get("mix", "")):
            return {"ok": False, "error": "Die Mix-Datei gibt es nicht mehr am gespeicherten Ort."}
        try:
            rec = self._mix_recognizer(o.get("pid") or "")
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}
        secs = int(o.get("seconds") or rec.get("default") or 30)
        clips = mixresult.plan_clips(res, secs, int(o.get("max") or 10), o.get("only"))
        if not clips:
            return {"ok": False, "error": "Keine Lücke zum Erkennen (alle Stellen schon geprüft)."}
        mix = res["mix"]

        def job(cancel, progress):
            found, error = [], ""
            for i, c in enumerate(clips):
                if cancel.is_set():
                    break
                progress(("progress", i, len(clips), f"{mixresult.fmt_time(c['start'])} – {rec['name']}"))
                try:
                    hits = self.plugins.recognize(rec["id"], mix, c["start"], secs, session=self, cancel=cancel)
                except Exception as ex:  # noqa: BLE001
                    if getattr(ex, "status", None) in (0, 401, 402, 403, 429) or isinstance(ex, (ValueError, RuntimeError)):
                        error = str(ex)
                        break
                    continue                              # nur diese Stelle (nicht als geprüft merken)
                found.append((c, hits[0] if hits else None))
            progress(("progress", len(clips), len(clips), "fertig"))
            cur = mixresult.load(d, rid)                  # frisch laden (Änderungen während des Laufs)
            added = mixresult.add_online(cur, found, rec["id"], rec["name"])
            mixresult.save(d, cur)
            return {"ok": True, "found": added, "clips": len(found), "planned": len(clips), "error": error,
                    "name": rec["name"], "mix_open": rid}
        return self._run("mixes", f"Mix-Lücken erkennen ({rec['name']})", job)

    def mix_online_to_ideas(self, rid, pid="", name="") -> dict:
        """Online erkannte Titel als Ideen merken (#393, nur auf Klick)."""
        text = mixresult.online_text(mixresult.load(self._mix_dir(), rid))
        if not text.strip():
            raise ValueError("Keine online erkannten Titel.")
        import ideas
        new, _unknown = ideas.from_text(text)
        if not new:
            raise ValueError("Keine Titel erkannt.")
        return self._ideas_add(pid, name, new)
