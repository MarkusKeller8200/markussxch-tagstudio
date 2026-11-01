"""Session-Teil „Warenkorb“ (#420–#423): Körbe mit Einkaufsliste, Titel aus Text und Ideen, Prüfung auf bereits
gekaufte Titel, Zuordnung und Übergabe an Beatport als Playlist TagStudio_CART_<Korb> (nur auf Klick, Entscheid W2),
Historik Offen/Gekauft (W3). Logik ohne Oberfläche und ohne Netz in carts.py; Konzept docs/KONZEPT-WARENKORB.md."""
from __future__ import annotations

import copy
import os

import carts
import core
import paths
import playlists


class CartsMixin:
    BP = "beatport"

    # ------------------------------------------------------------------ Speicher
    def _carts(self) -> carts.Store:
        st = getattr(self, "_cartstore", None)
        if st is None:
            st = self._cartstore = carts.Store(paths.sub("Warenkorb"))
        return st

    def _carts_bought(self) -> list:
        try:
            with self.lock:
                return list(self._purch().data["items"].values())
        except Exception:  # noqa: BLE001 – ohne Einkäufe wird nichts als gekauft markiert
            return []

    def _carts_get(self, cid) -> dict:
        c = self._carts().get(cid)
        if c.get("archived"):
            raise ValueError("Der Warenkorb ist archiviert – zuerst zurückholen.")
        return c

    def _carts_open(self, cid) -> dict:
        c = self._carts_get(cid)
        if c["status"] != "open":
            raise ValueError("Der Warenkorb ist abgeschlossen – zuerst „Wieder öffnen“.")
        return c

    def _carts_remember(self, cid):
        if self.cfg.get("carts_last") != cid:
            self.cfg["carts_last"] = cid
            core.save_config({"carts_last": cid})

    def _carts_target(self, cid="", name="") -> dict:
        """Ziel-Korb: gewählter (offen), sonst neuer mit Namen, sonst zuletzt benutzter offener bzw. neuer „Warenkorb“."""
        st = self._carts()
        if cid and st.exists(cid):
            return self._carts_open(cid)
        if name:
            return st.create(name)
        last = str(self.cfg.get("carts_last") or "")
        if last and st.exists(last) and st.get(last)["status"] == "open" and not st.get(last).get("archived"):
            return st.get(last)
        opened = [c for c in st.carts(archived=False) if c["status"] == "open"]
        return opened[0] if opened else st.create("")                  # #433: Warenkorb_JJJJ_MM_TT

    # ------------------------------------------------------------------ Abruf
    def carts_overview(self, sel="", archived=False) -> dict:
        bought = self._carts_bought()
        with self.lock:
            st = self._carts()
            bought_by = {c["id"]: carts.purchased(c["items"], bought) for c in st.carts()}

            def close(cs):                                    # W3: automatisch „gekauft“
                return any([carts.auto_close(c, bought_by.get(c["id"], {})) for c in cs.values()])
            st.quiet(close)
            lst = [copy.deepcopy(c) for c in st.carts()]
            undo = bool(st.undo_stack)
        ids = {c["id"] for c in lst if archived or not c.get("archived")}
        last = str(self.cfg.get("carts_last") or "")
        sel = sel if sel in ids else (last if last in ids else next((c["id"] for c in lst if c["id"] in ids), ""))
        out, items, total = [], [], 0
        for c in lst:
            b = bought_by.get(c["id"], {})
            counts = {k: 0 for k in carts.STATUS}
            no_id = unsure = 0
            for k, x in enumerate(c["items"]):
                s = carts.status(x, b.get(k, ""))
                counts[s] += 1
                if s == "open":
                    if not x.get("sid"):
                        no_id += 1
                    if (x.get("match") or {}).get("state") == "unsure":
                        unsure += 1
                if c["id"] == sel:
                    m = x.get("match") or {}
                    items.append({"k": k, "artist": x.get("artist", ""), "title": x.get("title", ""), "mix": x.get("mix", ""),
                                  "url": x.get("url", ""), "sid": x.get("sid", ""), "src": x.get("src", ""),
                                  "via": x.get("via", ""), "source": carts.source_label(x),
                                  "note": x.get("note", ""), "status": s, "bought": b.get(k, ""), "lib": x.get("lib", ""),
                                  "removed": (x.get("removed") or {}).get("why", ""), "match": m.get("state", ""),
                                  "score": m.get("score", 0), "cands": m.get("cands") or [], "hand": bool(m.get("hand")),
                                  "added": x.get("added", 0)})
            if c["status"] == "open" and not c.get("archived"):
                total += counts["open"]
            out.append({"id": c["id"], "name": c["name"], "status": c["status"], "store": c["store"],
                        "store_name": carts.STORES.get(c["store"], c["store"]), "created": c.get("created", 0),
                        "closed": c.get("closed", 0), "closed_by": c.get("closed_by", ""), "archived": c.get("archived", 0),
                        "checked": c.get("checked", 0), "count": len(c["items"]), "counts": counts, "no_id": no_id,
                        "unsure": unsure, "bp": carts.bp_name(c["name"]), "pushed": (c.get("pushed") or {}).get("beatport")})
        s = self.purch_bp_settings() if hasattr(self, "purch_bp_settings") else {"available": False}
        with self.lock:
            new_name = self._carts().next_name()
        return {"carts": out, "sel": sel, "items": items, "open": total, "undo": undo, "archived": bool(archived),
                "new_name": new_name, "library": bool(self._pl_lib_roots()) if hasattr(self, "_pl_lib_roots") else False,
                "n_archived": sum(1 for c in lst if c.get("archived")), "status": carts.STATUS,
                "sources": carts.SOURCES, "removed_why": carts.REMOVED_WHY,
                "beatport": {"available": bool(s.get("available")), "write": bool(s.get("playlists_write"))}}

    def carts_count(self) -> int:
        """Zahl in der Seitenleiste: Titel auf den Einkaufslisten offener Körbe."""
        try:
            return self.carts_overview().get("open", 0)
        except Exception:  # noqa: BLE001 – Zahl ist nur ein Hinweis
            return 0

    # ------------------------------------------------------------------ Körbe
    def carts_create(self, name) -> dict:
        with self.lock:
            c = self._carts().create(name or "")
        self._carts_remember(c["id"])
        return self.carts_overview(c["id"])

    def _carts_edit(self, cid, label, fn, sel=None, archived=False) -> dict:
        """fn(Korb) → geändert? Mit Rückgängig."""
        with self.lock:
            st = self._carts()
            st.get(cid)
            st.change(label, lambda cs: fn(cs[cid]))
        return self.carts_overview(cid if sel is None else sel, archived)

    def carts_rename(self, cid, name) -> dict:
        name = carts._txt(name, 120)
        if not name:
            raise ValueError("Bitte einen Namen eingeben.")

        def fn(c):
            if c["name"] == name:
                return False
            c["name"] = self._carts().unique_name(name)
            return True
        return self._carts_edit(cid, "Warenkorb umbenennen", fn)

    def carts_close(self, cid) -> dict:
        """„Als gekauft abschliessen“ (W3, von Hand)."""
        import time

        def fn(c):
            if c["status"] == "bought":
                return False
            c.update(status="bought", closed=int(time.time()), closed_by="hand")
            return True
        return self._carts_edit(cid, "Warenkorb abschliessen", fn)

    def carts_reopen(self, cid) -> dict:
        """„Wieder öffnen“: der Korb schliesst nicht sofort wieder automatisch (auto aus, bis neue Titel kommen)."""
        def fn(c):
            if c["status"] == "open":
                return False
            c.update(status="open", auto=False)
            c.pop("closed", None)
            c.pop("closed_by", None)
            return True
        return self._carts_edit(cid, "Warenkorb wieder öffnen", fn)

    def carts_archive(self, cid, on=True) -> dict:
        import time

        def fn(c):
            if bool(c.get("archived")) == bool(on):
                return False
            if on:
                c["archived"] = int(time.time())
            else:
                c.pop("archived", None)
                c["name"] = self._carts().unique_name(c["name"]) if any(
                    o["name"].lower() == c["name"].lower() and not o.get("archived") and o["id"] != c["id"]
                    for o in self._carts().carts()) else c["name"]
            return True
        return self._carts_edit(cid, "Warenkorb archivieren" if on else "Warenkorb zurückholen", fn,
                                sel="" if on else cid, archived=not on)

    # ------------------------------------------------------------------ Titel
    def _carts_add(self, cid, name, new) -> dict:
        with self.lock:
            st = self._carts()
            c = self._carts_target(cid, name)
            target = c["id"]
            res = {}

            def fn(cs):
                items, added, dupes = carts.merge(cs[target]["items"], new)
                res.update(added=added, dupes=dupes)
                if added:
                    cs[target]["items"] = items
                    cs[target]["auto"] = True
                return bool(added)
            st.change("Titel in den Warenkorb", fn)
            nm = st.get(target)["name"]
        self._carts_remember(target)
        return {"ok": True, "cid": target, "name": nm, **res}

    @staticmethod
    def tracklist_preview(text) -> dict:
        """#436: Vorschau einer eingefügten Trackliste (Warenkorb, Ideen, Playlists) – gleiche Reihenfolge wie beim
        Übernehmen; „head“ = vermutlich Titel des Mixes, in der Vorschau ausmarkiert."""
        new, unknown = carts.from_text(text)
        return {"items": [{"i": i, "artist": x.get("artist", ""), "title": x.get("title", ""), "mix": x.get("mix", ""),
                           "head": bool(x.get("head"))} for i, x in enumerate(new)],
                "unknown": unknown, "heads": sum(1 for x in new if x.get("head"))}

    TEXT_VIA = {"1001tracklists": "1001Tracklists", "mixid": "MixID"}      # #438: gewählte Quelle beim Einfügen

    def carts_add_text(self, cid, text, name="", skip=None, via="") -> dict:
        """#421: Liste aus Text (z. B. 1001Tracklists) – je Zeile „Künstler - Titel (Mix)“. skip (#436): Positionen der
        Vorschau, die nicht übernommen werden (None = erkannte Titelzeilen des Mixes auslassen)."""
        new, unknown = carts.from_text(text)
        new = playlists.pick_tracklist(new, skip)
        if not new:
            raise ValueError("Keine Titel erkannt – je Zeile „Künstler - Titel“.")
        v = self.TEXT_VIA.get(str(via or ""), "")
        if v:
            for x in new:
                x["via"] = v
        r = self._carts_add(cid, name, new)
        r["unknown"] = unknown
        return r

    def start_carts_url(self, url):
        """#424: Titel eines Links (Beatport, Spotify, SoundCloud) über das Plugin lesen – nur lesend, Ergebnis zur Vorschau."""
        url = str(url or "").strip()
        pid = carts.url_plugin(url)
        if not pid:
            return {"ok": False, "error": "Unbekannter Link – unterstützt werden Beatport, Spotify und SoundCloud "
                                          "(https://…)."}
        try:
            p = self.plugins.get(pid)
        except KeyError:
            return {"ok": False, "error": f"Das Plugin „{pid}“ fehlt."}
        if not p.enabled or p.state() != "ready":
            return {"ok": False, "error": f"Das Plugin „{p.name}“ ist aus – unter Plugins einschalten und anmelden."}

        def job(cancel, progress):
            progress(("text", f"{p.name}: Titel lesen …"))
            r = self.plugins.call_playlist(pid, "url_tracks", url, session=self, cancel=cancel, progress=progress) or {}
            items = [e for e in (carts.from_ref(x) for x in r.get("items") or []) if e]
            return {"ok": True, "plugin": p.name, "name": str(r.get("name") or "")[:200],
                    "items": [{"artist": e.get("artist", ""), "title": e.get("title", ""), "mix": e.get("mix", ""),
                               "isrc": e.get("isrc", ""), "dur": e.get("dur", 0), "url": e.get("url", ""),
                               "sid": e.get("sid", "")} for e in items]}
        return self._run("carts", "Warenkorb: Titel aus dem Link lesen", job)

    def carts_add_refs(self, cid, refs, name="", via="") -> dict:
        """#424: gewählte Titel aus der Link-Vorschau übernehmen; via (#438) = Dienst (Beatport, Spotify, SoundCloud)."""
        new = [e for e in (carts.from_ref(r) for r in refs or []) if e]
        v = carts._txt(via, 60)
        if v:
            for x in new:
                x["via"] = v
        if not new:
            raise ValueError("Keine Titel gewählt.")
        return self._carts_add(cid, name, new)

    def carts_add_manual(self, cid, data) -> dict:
        data = data if isinstance(data, dict) else {}
        url = str(data.get("url") or "").strip()
        e = carts.item(data.get("artist", ""), data.get("title", ""), data.get("mix", ""), url=url,
                       note=data.get("note", ""), src="manual", sid=carts.bp_id_from_url(url))
        if not e:
            raise ValueError("Bitte Künstler oder Titel eingeben.")
        if e.get("sid"):
            e["match"] = {"state": "sure", "score": 1.0}
        return self._carts_add(cid, "", [e])

    def carts_from_ideas(self, pid, ks, cid="", name="") -> dict:
        """#421: markierte Einträge einer Wunschliste in den Warenkorb; die Idee bekommt den Status „Kaufen“."""
        import ideas
        with self.lock:
            pls = self._pls()
            pl = self._ideas_get(pls, pid)
            items = copy.deepcopy(pl.get("items") or [])
            sel = self._ideas_ks(ks, len(items))
        new = [e for e in (carts.from_idea(items[k]) for k in sel) if e]
        if not new:
            raise ValueError("Keine Einträge gewählt.")
        for x in new:
            x["via"] = carts._txt(pl.get("name"), 120)                 # #438: Name der Wunschliste
        r = self._carts_add(cid, name, new)
        with self.lock:
            pls = self._pls()
            if pls.exists(pid):
                cur = copy.deepcopy(pls.get(pid).get("items") or [])
                ch = False
                for k in sel:
                    if k < len(cur) and (cur[k].get("idea") or {}).get("status", "idea") == "idea":
                        cur[k].setdefault("idea", {})["status"] = "buy"
                        ch = True
                if ch:
                    pls.update(pid, "Ideen in den Warenkorb", items=cur)
        r["ideas"] = ideas.FOLDER
        return r

    @staticmethod
    def _carts_ks(ks, n) -> list:
        return sorted({k for k in ks or [] if isinstance(k, int) and 0 <= k < n})

    def _carts_items(self, cid, label, fn) -> dict:
        """fn(items) ändert die Einträge des Korbs → geändert?"""
        with self.lock:
            self._carts_open(cid)
        return self._carts_edit(cid, label, lambda c: fn(c["items"]))

    def carts_remove(self, cid, ks) -> dict:
        """Titel von Hand aus der Einkaufsliste nehmen – sie bleiben als „entfernt“ im Korb (Rückfrage in der Oberfläche)."""
        import time

        def fn(items):
            n = 0
            for k in self._carts_ks(ks, len(items)):
                if not items[k].get("removed"):
                    items[k]["removed"] = {"why": "hand", "at": int(time.time())}
                    n += 1
            return bool(n)
        return self._carts_items(cid, "Aus der Einkaufsliste nehmen", fn)

    def carts_restore(self, cid, ks) -> dict:
        def fn(items):
            n = 0
            for k in self._carts_ks(ks, len(items)):
                if items[k].pop("removed", None):
                    n += 1
            return bool(n)
        return self._carts_items(cid, "Zurück auf die Einkaufsliste", fn)

    def carts_remove_bought(self, cid, ks=None) -> dict:
        """#422: gekaufte und in der Bibliothek vorhandene Titel aus der Einkaufsliste nehmen (Rückfrage in der Oberfläche).
        ks (#435): nur diese Positionen (aus der Vorschau); None = alle gekauften bzw. vorhandenen."""
        import time
        bought = self._carts_bought()
        with self.lock:
            b = carts.purchased(self._carts_open(cid)["items"], bought)
        res = {"n": 0}

        def fn(items):
            only = None if ks is None else set(self._carts_ks(ks, len(items)))
            for k, x in enumerate(items):
                s = carts.status(x, b.get(k, ""))
                if s in ("bought", "lib") and (only is None or k in only):
                    x["removed"] = {"why": s, "at": int(time.time())}
                    res["n"] += 1
            return bool(res["n"])
        r = self._carts_items(cid, "Gekaufte entfernen", fn)
        r["removed_n"] = res["n"]
        return r

    def carts_note(self, cid, k, note) -> dict:
        def fn(items):
            if not isinstance(k, int) or not 0 <= k < len(items):
                return False
            v = str(note or "").strip()[:1000]
            if v == items[k].get("note", ""):
                return False
            if v:
                items[k]["note"] = v
            else:
                items[k].pop("note", None)
            return True
        with self.lock:
            self._carts_get(cid)
        return self._carts_edit(cid, "Notiz", lambda c: fn(c["items"]))

    def carts_pick(self, cid, k, cand=-1) -> dict:
        """#423: unsicheren Beatport-Treffer wählen (cand = Nummer des Kandidaten) bzw. „nicht bei Beatport“ (-1)."""
        def fn(items):
            if not isinstance(k, int) or not 0 <= k < len(items):
                return False
            cs = (items[k].get("match") or {}).get("cands") or []
            c = cs[cand] if isinstance(cand, int) and 0 <= cand < len(cs) else None
            items[k] = carts.pick(items[k], c)
            return True
        return self._carts_items(cid, "Beatport-Treffer wählen", fn)

    def carts_pick_many(self, cid, picks) -> dict:
        """#435: mehrere unsichere Beatport-Treffer auf einmal wählen – picks {Position: Kandidat (-1 = keiner)}."""
        picks = {int(k): v for k, v in (picks or {}).items() if str(k).lstrip("-").isdigit()}

        def fn(items):
            n = 0
            for k, cand in picks.items():
                if 0 <= k < len(items) and (items[k].get("match") or {}).get("state") == "unsure":
                    cs = items[k]["match"].get("cands") or []
                    c = cs[cand] if isinstance(cand, int) and 0 <= cand < len(cs) else None
                    items[k] = carts.pick(items[k], c)
                    n += 1
            return bool(n)
        return self._carts_items(cid, "Beatport-Treffer wählen", fn)

    def carts_undo(self, sel="") -> dict:
        with self.lock:
            label = self._carts().undo()
        r = self.carts_overview(sel)
        r["message"] = f"Rückgängig: {label}"
        return r

    # ------------------------------------------------------------------ #422 Prüfung auf Käufe
    def _carts_check(self, cid, cancel, progress, library=True) -> dict:
        """Einkäufe der bereiten Stores aktualisieren, dann Korb mit „Einkäufe“ und der Bibliothek abgleichen."""
        import time
        src = [s for s in self.plugins.store_sources()]
        errors = []
        if src:
            _new, errors = self._purch_fetch(src, False, cancel, progress)
        else:
            errors.append("Kein Store eingerichtet – geprüft wird nur gegen die gespeicherten Einkäufe.")
        bought = self._carts_bought()
        with self.lock:
            items = copy.deepcopy(self._carts().get(cid)["items"])
        b = carts.purchased(items, bought)
        libs = {}
        roots_ok = bool(self._pl_lib_roots()) if hasattr(self, "_pl_lib_roots") else False
        if library and roots_ok:
            progress(("text", "Mit der Bibliothek abgleichen …"))
            index, _dest = self._purch_index(cancel, progress)
            for k, x in enumerate(items):
                if x.get("removed") or b.get(k):
                    continue
                r = playlists.match_ref({f: x.get(f, "") for f in ("artist", "title", "mix", "isrc")} | {"dur": x.get("dur") or 0},
                                        index, strict=self._purch_strict())
                libs[k] = r.get("path", "") if r.get("status") == "sure" else ""

        def fn(cs):
            c = cs.get(cid)
            if not c:
                return False
            for k, path in libs.items():
                if k < len(c["items"]):
                    if path:
                        c["items"][k]["lib"] = path
                    else:
                        c["items"][k].pop("lib", None)
            c["checked"] = int(time.time())
            return True
        with self.lock:
            self._carts().quiet(fn)
        n_lib = sum(1 for p in libs.values() if p)
        return {"bought": len(b), "lib": n_lib, "library": roots_ok, "errors": errors}

    def start_carts_check(self, cid):
        with self.lock:
            self._carts_get(cid)

        def job(cancel, progress):
            r = self._carts_check(cid, cancel, progress)
            return {"ok": True, **r}
        return self._run("carts", "Warenkorb auf Käufe prüfen", job)

    # ------------------------------------------------------------------ #423 Beatport
    def start_carts_bp_match(self, cid, again=False):
        """Titel ohne Beatport-ID über die Beatport-Katalogsuche zuordnen (nur lesend). again: auch unsichere und
        „nicht bei Beatport“ neu suchen (von Hand gewählte bleiben)."""
        with self.lock:
            c = self._carts_open(cid)
            todo = [k for k, x in enumerate(c["items"]) if not x.get("removed") and not x.get("sid")
                    and (again or not x.get("match")) and not (x.get("match") or {}).get("hand")]
            refs = [{f: c["items"][k].get(f, "") for f in ("artist", "title", "mix", "isrc")} | {"dur": c["items"][k].get("dur") or 0}
                    for k in todo]
        if not todo:
            return {"ok": False, "error": "Alle Titel der Einkaufsliste sind schon zugeordnet (bzw. als „nicht bei Beatport“ "
                                          "markiert – über „Weitere ▾“ neu suchen)."}
        s = self.purch_bp_settings()
        if not s.get("available"):
            return {"ok": False, "error": "Das Beatport-Plugin ist aus oder nicht angemeldet (Plugins › Beatport)."}

        def job(cancel, progress):
            res = self.plugins.call_playlist(self.BP, "store_search", refs, session=self, cancel=cancel,
                                             progress=progress) or []
            n = {"sure": 0, "unsure": 0, "none": 0}

            def fn(cs):
                cc = cs.get(cid)
                if not cc:
                    return False
                for k, r in zip(todo, res):
                    if k < len(cc["items"]) and not cc["items"][k].get("sid"):
                        cc["items"][k] = carts.apply_match(cc["items"][k], r)
                        n[cc["items"][k]["match"]["state"]] += 1
                return True
            with self.lock:
                self._carts().change("Bei Beatport suchen", fn)
            return {"ok": True, "searched": len(todo), **n}
        return self._run("carts", "Warenkorb: bei Beatport suchen", job)

    def carts_bp_preview(self, cid) -> dict:
        """„An Beatport senden“: Name, Titel mit Beatport-ID, ohne ID, gekaufte (werden nie gesendet), Einstellung."""
        bought = self._carts_bought()
        with self.lock:
            c = self._carts_open(cid)
            b = carts.purchased(c["items"], bought)
            ids, without = carts.bp_ids(c["items"], b)
            n_bought = sum(1 for k, x in enumerate(c["items"]) if carts.status(x, b.get(k, "")) in ("bought", "lib"))
            pushed = (c.get("pushed") or {}).get("beatport") or {}
            name = carts.bp_name(c["name"])
        s = self.purch_bp_settings()
        return {"name": name, "count": len(ids), "without": without, "bought": n_bought, "pushed": pushed,
                "available": bool(s.get("available")), "write": bool(s.get("playlists_write")), "why": s.get("why", "")}

    def start_carts_bp(self, cid):
        """Einkaufsliste als Beatport-Playlist TagStudio_CART_<Korb> – nur auf Klick (W2). Vorher automatisch auf Käufe
        prüfen; gekaufte Titel werden nie gesendet. Die Playlist enthält danach genau die Einkaufsliste."""
        pv = self.carts_bp_preview(cid)
        if not pv["available"]:
            return {"ok": False, "error": "Das Beatport-Plugin ist aus oder nicht angemeldet (Plugins › Beatport)."}
        if not pv["write"]:
            return {"ok": False, "error": "Im Beatport-Plugin ist „Playlists in Beatport schreiben“ ausgeschaltet "
                                          "(Plugins › Beatport › „Einstellungen …“)."}

        def job(cancel, progress):
            import time
            chk = self._carts_check(cid, cancel, progress, library=False)
            bought = self._carts_bought()
            with self.lock:
                c = self._carts_open(cid)
                b = carts.purchased(c["items"], bought)
                ids, without = carts.bp_ids(c["items"], b)
                name = carts.bp_name(c["name"])
            if not ids:
                raise ValueError("Auf der Einkaufsliste steht kein Titel mit Beatport-ID – zuerst „Bei Beatport suchen“.")
            progress(("text", f"Beatport: {name} …"))
            r = self.plugins.call_playlist(self.BP, "store_playlist_put", name, ids, True,
                                           session=self, cancel=cancel, progress=progress) or {}

            def fn(cs):
                cc = cs.get(cid)
                if not cc or not r.get("id"):
                    return False
                cc.setdefault("pushed", {})["beatport"] = {"id": str(r["id"]), "name": name, "url": r.get("url", ""),
                                                           "at": int(time.time()), "count": len(ids)}
                return True
            with self.lock:
                self._carts().quiet(fn)
            return {"ok": True, **r, "count": len(ids), "without": without, "bought": chk.get("bought", 0),
                    "errors": chk.get("errors", [])}
        return self._run("carts", f"Beatport: {pv['name']}", job)

    # ------------------------------------------------------------------ Export
    def carts_export_write(self, fmt, dest, cid="") -> dict:
        import tagger
        bought = self._carts_bought()
        with self.lock:
            st = self._carts()
            lst = [copy.deepcopy(st.get(cid))] if cid else [copy.deepcopy(c) for c in st.carts(archived=False)]
        rows = carts.export_rows(lst, {c["id"]: carts.purchased(c["items"], bought) for c in lst})
        (tagger.write_xlsx if fmt == "xlsx" else tagger.write_csv)(dest, carts.EXPORT_HEAD, rows)
        return {"ok": True, "path": dest, "count": len(rows), "message": f"{len(rows)} Titel exportiert: {os.path.basename(dest)}"}

    def carts_export_name(self, fmt, cid="") -> str:
        name = "Warenkorb"
        if cid:
            with self.lock:
                st = self._carts()
                if st.exists(cid):
                    name = st.get(cid)["name"]
        return playlists.safe_part(name) + (".xlsx" if fmt == "xlsx" else ".csv")
