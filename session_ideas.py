"""Session-Teil „Ideen“ (#186): Wunschlisten (Playlists der Art „wish“ im Ordner „Ideen“), Idee merken aus
„Entdecken“, Status bis Kauf und Bibliothek, Export, Wunschliste als Beatport-Playlist (nur auf Klick, I5).
Logik ohne Oberfläche in ideas.py; Speicher und Rückgängig wie bei den Playlists (playlists.Store)."""
from __future__ import annotations

import copy
import os

import core
import discover
import ideas


class IdeasMixin:
    # ------------------------------------------------------------------ Speicher
    def _ideas_lists(self, st) -> list:
        return [p for p in st.active() if ideas.is_wish(p)]

    def _ideas_migrate(self, st):
        """Einmalig (#186, 4.2): gemerkte Vorschläge aus „Entdecken“ in die Wunschliste „Gemerkt (Entdecken)“ kopieren.
        entdecken.json bleibt unverändert; das Kennzeichen in index.json verhindert eine zweite Übernahme."""
        if st.index["migrated"].get(ideas.MIGRATED_FLAG):
            return
        try:
            d = discover.load()
        except Exception:  # noqa: BLE001 – ohne lesbares Entdecken nichts übernehmen, beim nächsten Mal wieder versuchen
            return
        saved = sorted((e for e in d["items"].values() if e.get("status") == "saved"),
                       key=lambda e: (e.get("first") or "", e.get("key") or ""))
        new = [y for y in (ideas.from_discover(e) for e in saved) if y]
        if new:
            items, _a, _d = ideas.merge([], new)
            name = st.unique_name(ideas.MIGRATED_LIST, ideas.FOLDER)
            st.create(name, ideas.FOLDER, ideas.KIND, items)
            if st.undo_stack:
                st.undo_stack.pop()                       # Übernahme ist kein Rückgängig-Schritt
        st.index["migrated"][ideas.MIGRATED_FLAG] = len(new)
        st.save_index()

    def _ideas_get(self, st, pid) -> dict:
        pl = st.get(pid)
        if not ideas.is_wish(pl) or pl.get("archived"):
            raise ValueError("Wunschliste nicht gefunden.")
        return pl

    def _ideas_target(self, st, pid="", name="") -> dict:
        """Ziel-Wunschliste: gewählte, sonst neue mit Namen, sonst zuletzt benutzte bzw. „Wunschliste“."""
        if pid and st.exists(pid):
            return self._ideas_get(st, pid)
        if name:
            return st.create(st.unique_name(name, ideas.FOLDER), ideas.FOLDER, ideas.KIND, [])
        last = str(self.cfg.get("ideas_last") or "")
        if last and st.exists(last) and ideas.is_wish(st.get(last)) and not st.get(last).get("archived"):
            return st.get(last)
        lists = self._ideas_lists(st)
        if lists:
            return lists[0]
        return st.create(ideas.DEFAULT_LIST, ideas.FOLDER, ideas.KIND, [])

    def _ideas_remember(self, pid):
        if self.cfg.get("ideas_last") != pid:
            self.cfg["ideas_last"] = pid
            core.save_config({"ideas_last": pid})

    def _ideas_bought_by(self, lists) -> dict:
        bought = self._disc_bought() if hasattr(self, "_disc_bought") else []
        return {p["id"]: ideas.purchased(p.get("items") or [], bought) for p in lists}

    # ------------------------------------------------------------------ Abruf
    def ideas_overview(self, sel="") -> dict:
        with self.lock:
            st = self._pls()
            self._ideas_migrate(st)
            lists = [copy.deepcopy(p) for p in self._ideas_lists(st)]
        bought_by = self._ideas_bought_by(lists)
        sel = sel if any(p["id"] == sel for p in lists) else (str(self.cfg.get("ideas_last") or "") if any(
            p["id"] == self.cfg.get("ideas_last") for p in lists) else (lists[0]["id"] if lists else ""))
        out_lists, items, total_buy = [], [], 0
        for p in lists:
            b = bought_by.get(p["id"], {})
            counts = {k: 0 for k in ideas.STATUS}
            for k, x in enumerate(p.get("items") or []):
                st_ = ideas.status(x, b.get(k, ""))
                counts[st_] += 1
                if p["id"] == sel:
                    idea, ref = x.get("idea") or {}, x.get("ref") or {}
                    items.append({"k": k, "artist": ref.get("artist", ""), "title": ref.get("title", ""), "mix": ref.get("mix", ""),
                                  "url": ref.get("url", ""), "status": st_, "set": idea.get("status", "idea"),
                                  "note": x.get("note", ""), "bought": b.get(k, ""), "path": x.get("path", ""),
                                  "src": idea.get("src", ""), "store": idea.get("store", ""), "sid": idea.get("sid", ""),
                                  "preview": idea.get("preview", ""), "cover": idea.get("cover", ""), "label": idea.get("label", ""),
                                  "date": idea.get("date", ""), "release": idea.get("release", ""), "added": x.get("added", 0)})
            total_buy += counts["buy"]
            out_lists.append({"id": p["id"], "name": p["name"], "count": len(p.get("items") or []), "counts": counts,
                              "bp": ideas.bp_name(p["name"]), "pushed": (p.get("pushed") or {}).get("beatport"),
                              "sp_pushed": (p.get("pushed") or {}).get("spotify")})
        s = self.purch_bp_settings() if hasattr(self, "purch_bp_settings") else {"available": False}
        return {"lists": out_lists, "sel": sel, "items": items, "buy": total_buy, "status": ideas.STATUS,
                "sources": ideas.SOURCES, "beatport": {"available": bool(s.get("available")),
                                                       "write": bool(s.get("playlists_write"))},
                "spotify": self._ideas_sp(),
                "library": bool(self._pl_lib_roots()) if hasattr(self, "_pl_lib_roots") else False,
                "undo": bool(self._pls().undo_stack)}

    def ideas_count(self) -> int:
        """Zahl in der Seitenleiste: Einträge mit Status „Kaufen“ (noch nicht gekauft, nicht in der Bibliothek)."""
        try:
            return self.ideas_overview().get("buy", 0)
        except Exception:  # noqa: BLE001 – Zahl ist nur ein Hinweis
            return 0

    def _ideas_disc_keys(self) -> set:
        """Schlüssel der Vorschläge aus „Entdecken“, die in einer Wunschliste stehen (Kennzeichen „in Ideen“, I3)."""
        out = set()
        with self.lock:
            for p in self._ideas_lists(self._pls()):
                for x in p.get("items") or []:
                    k = (x.get("idea") or {}).get("disc")
                    if k:
                        out.add(k)
        return out

    # ------------------------------------------------------------------ Wunschlisten
    def ideas_list_create(self, name) -> dict:
        with self.lock:
            st = self._pls()
            pl = st.create(name, ideas.FOLDER, ideas.KIND, [])
        self._ideas_remember(pl["id"])
        return self.ideas_overview(pl["id"])

    def ideas_list_rename(self, pid, name) -> dict:
        with self.lock:
            st = self._pls()
            self._ideas_get(st, pid)
            st.rename(pid, name)
        return self.ideas_overview(pid)

    def ideas_list_archive(self, pid, move_to="") -> dict:
        """Wunschliste archivieren (wie Playlists: unter Playlists › Archiv zurückholbar). move_to: Einträge vorher in
        diese Wunschliste verschieben (ohne Doppelte)."""
        with self.lock:
            st = self._pls()
            pl = self._ideas_get(st, pid)
            if move_to and move_to != pid:
                dest = self._ideas_get(st, move_to)
                items, _a, _d = ideas.merge(list(dest.get("items") or []), copy.deepcopy(pl.get("items") or []))
                st.update(move_to, "Ideen verschieben", items=items)
            st.archive(pid)
        return self.ideas_overview(move_to or "")

    # ------------------------------------------------------------------ Einträge
    def _ideas_add(self, pid, name, new) -> dict:
        with self.lock:
            st = self._pls()
            pl = self._ideas_target(st, pid, name)
            items, added, dupes = ideas.merge(list(pl.get("items") or []), new)
            if added:
                st.update(pl["id"], "Ideen merken", items=items)
            st.touch(pl["id"])
        self._ideas_remember(pl["id"])
        return {"ok": True, "pid": pl["id"], "name": pl["name"], "added": added, "dupes": dupes}

    def ideas_from_disc(self, keys, pid="", name="") -> dict:
        """„Idee merken ▸“ in Entdecken: Vorschläge in eine Wunschliste kopieren; in Entdecken bleiben sie als
        „gemerkt“ sichtbar (Filter „Gemerkt“ noch eine Version, I3)."""
        with discover.LOCK:
            d = discover.load()
            picked = [d["items"][k] for k in keys or [] if k in d["items"]]
            for e in picked:
                if e.get("status") in ("new", "hidden"):
                    e["status"] = "saved"
            if picked:
                discover.save(d)
        if not picked:
            raise ValueError("Kein Vorschlag gewählt.")
        return self._ideas_add(pid, name, [ideas.from_discover(e) for e in picked])

    def ideas_add_manual(self, pid, data) -> dict:
        """Eintrag von Hand: {artist, title, mix, url, note}."""
        data = data if isinstance(data, dict) else {}
        e = ideas.entry(data.get("artist", ""), data.get("title", ""), data.get("mix", ""), url=data.get("url", ""),
                        note=data.get("note", ""), src="manual")
        if not e:
            raise ValueError("Bitte Künstler oder Titel eingeben.")
        return self._ideas_add(pid, "", [e])

    def ideas_add_text(self, pid, text) -> dict:
        """Liste aus Text (je Zeile „Künstler - Titel (Mix)“) in die Wunschliste übernehmen."""
        new, unknown = ideas.from_text(text)
        if not new:
            raise ValueError("Keine Titel erkannt – je Zeile „Künstler - Titel“.")
        r = self._ideas_add(pid, "", new)
        r["unknown"] = unknown
        return r

    def _ideas_change(self, pid, label, fn) -> dict:
        with self.lock:
            st = self._pls()
            pl = self._ideas_get(st, pid)
            items = copy.deepcopy(pl.get("items") or [])
            if fn(items):
                st.update(pid, label, items=items)
        return self.ideas_overview(pid)

    @staticmethod
    def _ideas_ks(ks, n) -> list:
        return sorted({k for k in ks or [] if isinstance(k, int) and 0 <= k < n})

    def ideas_set(self, pid, ks, status=None, note=None) -> dict:
        """Status (idea | buy | dropped) und/oder Notiz der gewählten Einträge setzen."""
        if status is not None and status not in ("idea", "buy", "dropped"):
            raise ValueError("Unbekannter Status.")

        def fn(items):
            ch = False
            for k in self._ideas_ks(ks, len(items)):
                x = items[k]
                if status is not None:
                    x.setdefault("idea", {})["status"] = status
                    ch = True
                if note is not None:
                    v = str(note).strip()[:1000]
                    if v:
                        x["note"] = v
                    else:
                        x.pop("note", None)
                    ch = True
            return ch
        return self._ideas_change(pid, "Idee ändern" if note is None else "Notiz", fn)

    def ideas_remove(self, pid, ks) -> dict:
        """Einträge aus der Wunschliste entfernen (die Oberfläche fragt vorher; Rückgängig möglich)."""
        def fn(items):
            drop = set(self._ideas_ks(ks, len(items)))
            items[:] = [x for k, x in enumerate(items) if k not in drop]
            return bool(drop)
        return self._ideas_change(pid, "Ideen entfernen", fn)

    def ideas_move(self, pid, ks, to, copy_only=False) -> dict:
        """Einträge in eine andere Wunschliste verschieben bzw. kopieren (ohne Doppelte)."""
        with self.lock:
            st = self._pls()
            src = self._ideas_get(st, pid)
            dest = self._ideas_get(st, to)
            if src["id"] == dest["id"]:
                raise ValueError("Bitte eine andere Wunschliste wählen.")
            items = list(src.get("items") or [])
            sel = self._ideas_ks(ks, len(items))
            merged, added, dupes = ideas.merge(list(dest.get("items") or []), [copy.deepcopy(items[k]) for k in sel])
            if added:
                st.update(dest["id"], "Ideen kopieren" if copy_only else "Ideen verschieben", items=merged)
            if not copy_only and sel:
                st.update(src["id"], "Ideen verschieben", items=[x for k, x in enumerate(items) if k not in set(sel)])
        r = self.ideas_overview(pid)
        r.update(moved=added, dupes=dupes)
        return r

    def ideas_undo(self, sel="") -> dict:
        with self.lock:
            label = self._pls().undo()
        r = self.ideas_overview(sel)
        r["message"] = f"Rückgängig: {label}"
        return r

    def ideas_preview(self, pid, k) -> str:
        """Vorhör-Link eines Eintrags; Deezer-Links laufen ab und werden über die Titel-ID frisch geholt."""
        with self.lock:
            pl = self._ideas_get(self._pls(), pid)
            items = pl.get("items") or []
            if not isinstance(k, int) or not 0 <= k < len(items):
                return ""
            idea = items[k].get("idea") or {}
        if idea.get("store") == "deezer" and idea.get("sid"):
            try:
                js = discover.fetch_json(f"https://api.deezer.com/track/{int(idea['sid'])}")
                if isinstance(js, dict) and str(js.get("preview") or "").startswith("https://"):
                    return js["preview"]
            except Exception:  # noqa: BLE001 – dann den gespeicherten Link versuchen
                pass
        return idea.get("preview", "")

    # ------------------------------------------------------------------ Weitergeben
    def ideas_to_playlist(self, pid, name="", folder="") -> dict:
        """„Als Playlist übernehmen“: normale Playlist mit den Einträgen (ohne verworfene); vorhandene Dateien sind
        verknüpft, die übrigen bleiben Einträge ohne Datei (Einkaufsliste)."""
        with self.lock:
            st = self._pls()
            pl = self._ideas_get(st, pid)
            items = ideas.to_playlist_items(copy.deepcopy(pl.get("items") or []))
            if not items:
                raise ValueError("Die Wunschliste hat keine offenen Einträge.")
            new = st.create(st.unique_name(name or pl["name"], folder), folder, "manual", items)
            st.touch(new["id"])
        return {"ok": True, "pid": new["id"], "name": new["name"], "count": len(items)}

    def start_ideas_match(self, pid):
        """Einträge ohne Datei mit der Bibliothek abgleichen und sichere Treffer verknüpfen (→ „In Bibliothek“)."""
        with self.lock:
            self._ideas_get(self._pls(), pid)
        if not self._pl_lib_roots() and not self.tag_files:
            return {"ok": False, "error": "Keine Bibliothek festgelegt (Einstellungen › Speicherort und Ordner)."}

        def job(cancel, progress):
            return {"ok": True, "linked": self._pl_auto_match([pid], cancel, progress)}
        return self._run("ideas", "Wunschliste mit der Bibliothek abgleichen", job)

    # ------------------------------------------------------------------ #384 Spotify (SP2, SP5)
    SP = "spotify"

    def _ideas_sp(self) -> dict:
        """Spotify-Plugin für Ideen: {"available", "why", "missing": [fehlende Berechtigungen]}."""
        import plugins as _pl
        try:
            p = self.plugins.get(self.SP)
        except KeyError:
            return {"available": False, "why": "Spotify-Plugin fehlt", "missing": []}
        if not p.enabled or p.state() != "ready":
            return {"available": False, "why": "Spotify-Plugin ist aus", "missing": []}
        mod = p.load()
        try:
            ctx = _pl.Context(p, self)
            ok, why = mod.ready(ctx)
            miss = mod.missing_scopes(ctx, mod.NEW_SCOPES) if ok and hasattr(mod, "missing_scopes") else []
        except Exception as ex:  # noqa: BLE001
            ok, why, miss = False, str(ex), []
        return {"available": bool(ok), "why": why, "missing": miss}

    def ideas_spotify_now(self) -> dict:
        """„Läuft gerade“ in Spotify → {"track": Eintrag | None, "playing"} (nur lesen)."""
        return self.plugins.call_playlist(self.SP, "now_playing", session=self) or {}

    def ideas_spotify_recent(self, n=50) -> dict:
        """„Zuletzt gehört“ in Spotify → {"tracks": [...]} – zum Auswählen in der Oberfläche."""
        return {"tracks": self.plugins.call_playlist(self.SP, "recently_played", int(n or 50), session=self) or []}

    def ideas_add_spotify(self, pid, tracks, name="") -> dict:
        """Gewählte Spotify-Titel als Ideen merken (Link, ISRC, Spotify-ID bleiben erhalten)."""
        new = [e for e in (ideas.from_spotify(t) for t in tracks or []) if e]
        if not new:
            raise ValueError("Kein Titel gewählt.")
        return self._ideas_add(pid, name, new)

    def ideas_sp_preview(self, pid) -> dict:
        """„Als Spotify-Playlist“ (SP5): Name, Titel mit Spotify-ID, ohne ID, schon angelegt?"""
        with self.lock:
            pl = self._ideas_get(self._pls(), pid)
            uris, without = ideas.spotify_uris(pl.get("items") or [])
            pushed = (pl.get("pushed") or {}).get("spotify") or {}
        sp = self._ideas_sp()
        return {"name": ideas.sp_name(pl["name"]), "count": len(uris), "without": without, "pushed": pushed, **sp}

    def start_ideas_sp(self, pid):
        """Wunschliste als private Spotify-Playlist anlegen bzw. fehlende Titel ergänzen – nur auf Klick (SP5)."""
        pv = self.ideas_sp_preview(pid)
        if not pv["available"]:
            return {"ok": False, "error": f"Spotify: {pv['why'] or 'nicht bereit'}."}
        if "playlist-modify-private" in pv["missing"]:
            return {"ok": False, "error": "Spotify: Berechtigung zum Anlegen von Playlists fehlt – bitte unter Plugins › "
                                          "Spotify einmal „Anmelden …“."}
        if not pv["count"]:
            return {"ok": False, "error": "Kein offener Eintrag mit Spotify-Link bzw. -ID (z. B. aus „Läuft gerade“ "
                                          "oder „Zuletzt gehört“)."}
        with self.lock:
            uris, _w = ideas.spotify_uris(self._ideas_get(self._pls(), pid).get("items") or [])

        def job(cancel, progress):
            r = self.plugins.call_playlist(self.SP, "wish_push", pv["name"], uris, (pv.get("pushed") or {}).get("id", ""),
                                           session=self, cancel=cancel, progress=progress) or {}
            with self.lock:
                st = self._pls()
                if st.exists(pid) and r.get("id"):
                    st.set_pushed(pid, "spotify", {"id": r["id"], "url": r.get("url", "")})
            return {"ok": True, **r, "without": pv["without"]}
        return self._run("ideas", f"Spotify: {pv['name']}", job)

    def ideas_bp_preview(self, pid) -> dict:
        """„Als Beatport-Playlist“: Name, Zahl der Titel mit Beatport-ID, ohne ID, Einstellung „Playlists schreiben“."""
        with self.lock:
            pl = self._ideas_get(self._pls(), pid)
            ids, without = ideas.bp_ids(pl.get("items") or [])
        s = self.purch_bp_settings()
        return {"name": ideas.bp_name(pl["name"]), "count": len(ids), "without": without,
                "available": bool(s.get("available")), "write": bool(s.get("playlists_write")), "why": s.get("why", "")}

    def start_ideas_bp(self, pid):
        """Wunschliste in Beatport als TagStudio_WISH_<Liste> anlegen bzw. ergänzen – nur auf Klick (I5)."""
        pv = self.ideas_bp_preview(pid)
        if not pv["available"]:
            return {"ok": False, "error": "Das Beatport-Plugin ist aus oder nicht angemeldet."}
        if not pv["write"]:
            return {"ok": False, "error": "Im Beatport-Plugin ist „Playlists in Beatport schreiben“ ausgeschaltet."}
        if not pv["count"]:
            return {"ok": False, "error": "Kein offener Eintrag mit Beatport-ID (nur Vorschläge von Beatport haben eine)."}
        with self.lock:
            ids, _w = ideas.bp_ids(self._ideas_get(self._pls(), pid).get("items") or [])

        def job(cancel, progress):
            r = self.plugins.call_playlist(self.BP, "store_playlist_put", pv["name"], ids, False,
                                           session=self, cancel=cancel, progress=progress)
            with self.lock:
                st = self._pls()
                if st.exists(pid) and r and r.get("id"):
                    st.set_pushed(pid, "beatport", {"id": r.get("id")})
            return {"ok": True, **(r or {}), "without": pv["without"]}
        return self._run("ideas", f"Beatport: {pv['name']}", job)

    def ideas_export_write(self, fmt, dest, pid="") -> dict:
        """Wunschliste (pid) bzw. alle Wunschlisten als Excel oder CSV."""
        import tagger
        with self.lock:
            st = self._pls()
            lists = [copy.deepcopy(self._ideas_get(st, pid))] if pid else [copy.deepcopy(p) for p in self._ideas_lists(st)]
        rows = ideas.export_rows(lists, self._ideas_bought_by(lists))
        (tagger.write_xlsx if fmt == "xlsx" else tagger.write_csv)(dest, ideas.EXPORT_HEAD, rows)
        return {"ok": True, "path": dest, "count": len(rows), "message": f"{len(rows)} Ideen exportiert: {os.path.basename(dest)}"}

    def ideas_export_name(self, fmt, pid="") -> str:
        import playlists
        name = "Ideen"
        if pid:
            with self.lock:
                st = self._pls()
                if st.exists(pid):
                    name = st.get(pid)["name"]
        return playlists.safe_part(name) + (".xlsx" if fmt == "xlsx" else ".csv")
