"""Session-Teil „Käufe“ (#285): gekaufte Titel aller Stores sammeln, mit der Bibliothek abgleichen, fehlende laden.

Stores sind Plugins mit ``store_purchases(ctx)`` und ``store_download(ctx, items, dest)`` (zuerst Beatport). Der
Speicher (``purchases.Store``) liegt im Datenordner des Profils. Ziel für Downloads ist der Eingangsordner: eigene
Wahl (cfg ``purch_dest``), sonst der Eingang von „Vorbereiten“, sonst ``<Basisordner>/00_New``.
"""
from __future__ import annotations

import os

import core
import keys
import paths
import playlists
import purchases

NEW_DIR = "00_New"
FULL_EVERY = 30 * 86400             # ganze Kaufliste spätestens nach 30 Tagen wieder einmal holen
OVERLAP_DAYS = 3                    # neue Käufe ab dem letzten Kaufdatum minus 3 Tage


class PurchasesMixin:
    def _purch(self) -> purchases.Store:
        st = getattr(self, "_purchstore", None)
        if st is None:
            st = self._purchstore = purchases.Store(paths.sub("Käufe"))
        return st

    def _purch_dest(self) -> tuple[str, str]:
        """Ziel für Downloads → (Pfad, Herkunft). #314: ohne eigene Wahl der Ordner „Downloads“ (je Store ein
        Unterordner, siehe _purch_dest_for), sonst wie bisher Eingang bzw. <Basisordner>/00_New."""
        own = str(self.cfg.get("purch_dest") or "")
        if own:
            return own, "eigene Wahl"
        import folders
        dl = folders.resolve_role(self._folders(), "downloads")
        if dl:
            return dl, "Downloads (Unterordner je Store)"
        try:
            inbox = self._prep_get().get("inbox") or ""
        except Exception:  # noqa: BLE001
            inbox = ""
        if inbox:
            return inbox, "Eingang von „Vorbereiten“"
        if self.cfg.get("base_dir"):
            return os.path.join(str(self.cfg["base_dir"]), NEW_DIR), "Basisordner"
        return "", ""

    def _purch_dest_for(self, store, dest, why) -> str:
        """Ziel eines Stores: bei der Rolle „Downloads“ deren Unterordner der Quelle (z. B. 90_Download\\Beatport)."""
        if why.startswith("Downloads"):
            return self._source_dir(store) or dest
        return dest

    # ---- #338: Zuweisung „streng“ und Korrekturfenster
    def _purch_strict(self) -> bool:
        return bool(self.cfg.get("purch_strict", False))

    def set_purch_strict(self, on) -> dict:
        """Abgleich „streng“ ein/aus (Mix muss passen, auch bei gleicher ISRC) – danach neu abgleichen."""
        self.cfg["purch_strict"] = bool(on)
        core.save_config({"purch_strict": bool(on)})
        return {"strict": bool(on)}

    @staticmethod
    def _file_info(path, ref_artist="") -> dict:
        """Angaben einer Kandidaten-Datei für das Korrekturfenster (Tags, Länge, Mix wie beim Abgleich)."""
        from id3tags import MP3File
        d = {"path": path, "name": os.path.basename(path), "dir": os.path.dirname(path), "artist": "", "title": "",
             "subtitle": "", "mix": "", "dur": 0, "bpm": "", "key": "", "isrc": "", "ok": os.path.isfile(path)}
        if not d["ok"]:
            return d
        try:
            f = MP3File(path)
            d.update(artist=f.text("TPE1"), title=f.text("TIT2"), subtitle=f.text("TIT3"), bpm=f.text("TBPM"),
                     key=keys.parse_key(f.text("TKEY")) or f.text("TKEY"), isrc=f.text("TSRC"),
                     dur=int(round(getattr(f, "duration", 0) or 0)))
        except Exception as ex:  # noqa: BLE001 – unlesbare Datei trotzdem zeigen
            d["error"] = str(ex)
        e = playlists.lib_entry(path, d["artist"], d["title"], subtitle=d["subtitle"])
        d["mix"] = e["mix"]
        d["artist_sim"] = round(playlists.artist_similarity(ref_artist, d["artist"]) * 100) if ref_artist else 0
        return d

    def purch_candidates(self, key) -> dict:
        """#338: Korrekturfenster – Kauf, Art der Unklarheit und Kandidaten mit ihren Tags."""
        with self.lock:
            it = dict(self._purch().data["items"].get(str(key)) or {})
        if not it:
            raise ValueError("Kauf nicht gefunden.")
        row = self._purch_row(str(key), it)
        _base, mix = playlists.split_title(it.get("title"), it.get("mix", ""))
        paths = list(it.get("cands") or []) or ([it["file"]] if it.get("file") else [])
        return {"row": row, "kind": it.get("kind") or ("missing" if row["status"] == "missing" else ""),
                "mix_key": mix, "strict": self._purch_strict(),
                "cands": [self._file_info(p, it.get("artist", "")) for p in paths[:12]]}

    def purch_fix_file(self, key, path, title, subtitle, filename="") -> dict:
        """#338: Tags einer Kandidaten-Datei anpassen (Titel, Untertitel), auf Wunsch umbenennen (nie überschreiben),
        mit Sicherung wie beim Speichern; danach diesen Kauf erneut gegen die Datei prüfen und bei Erfolg zuordnen.
        → {ok, path, sure, reason, state}"""
        from id3tags import MP3File
        path = str(path or "")
        if not os.path.isfile(path):
            raise ValueError("Datei nicht gefunden.")
        f = MP3File(path)
        changed = False
        for k, v in (("TIT2", title), ("TIT3", subtitle)):
            v = " ".join(str(v or "").split())
            if v != f.text(k):
                f.set_text(k, v) if v else f.set(k, None)
                changed = True
        if changed:
            r = core.save_files([f], self.cfg.get("backup_enabled", True) is not False, self.cfg.get("backup_dir") or None,
                                store=self._backup_store(), stamp=self.cfg.get("stamp_edited", True))
            if r.get("errors"):
                return {"ok": False, "error": "; ".join(r["errors"]), "path": path}
        new = path
        filename = os.path.basename(str(filename or "").strip())
        if filename and filename != os.path.basename(path):
            if not filename.lower().endswith(".mp3"):
                filename += ".mp3"
            new = os.path.join(os.path.dirname(path), filename)
            if os.path.exists(new):
                return {"ok": False, "error": f"„{filename}“ gibt es schon – nicht umbenannt.", "path": path}
            os.rename(path, new)
        with self.lock:
            it = self._purch().data["items"].get(str(key))
            if it is None:
                raise ValueError("Kauf nicht gefunden.")
            ref = {k: it.get(k, "") for k in ("artist", "title", "mix", "isrc")}
            ref["dur"] = it.get("dur") or 0
            info = self._file_info(new)
            e = playlists.lib_entry(new, info["artist"], info["title"], info["isrc"], info["dur"], info["subtitle"])
            m = playlists.match_ref(ref, [e], strict=self._purch_strict())
            if m["status"] == "sure":
                dest, _why = self._purch_dest()
                self._purch().link(str(key), new, dest)
        return {"ok": True, "path": new, "sure": m["status"] == "sure", "reason": m.get("reason", ""),
                "state": self.purch_state()}

    # ---- #334/#335: Playlists in Beatport (Download Tracks je 100, eine Playlist je Kaufdatum)
    BP = "beatport"
    DL_PREFIX = "TagStudio_DOWNLOAD_"

    def purch_bp_settings(self, update=None) -> dict:
        """Einstellungen des Beatport-Plugins für die Playlist-Knöpfe → {available, playlists_write, buy_prefix}."""
        try:
            s = self.plugins.call_playlist(self.BP, "store_settings", update, session=self) or {}
        except Exception as ex:  # noqa: BLE001 – Plugin aus, alt oder nicht bereit
            return {"available": False, "playlists_write": False, "buy_prefix": "TagStudio_BUY_", "why": str(ex)}
        return {"available": True, **s}

    def purch_bp_check(self) -> dict:
        """„Schreibzugriff prüfen“ (OPTIONS, ändert nichts)."""
        return self.plugins.call_playlist(self.BP, "store_playlist_check", session=self)

    def _bp_open_items(self, keys_=None) -> list:
        """Beatport-Käufe ohne lokale Datei (fehlt/unklar, keine Vorbestellung) bzw. die markierten."""
        with self.lock:
            items = self._purch().data["items"]
            sel = [items[k] for k in (keys_ or []) if k in items]
            if not keys_:
                sel = [it for it in items.values() if it.get("status") in ("missing", "unclear")]
            return [it for it in sel if it.get("store") == self.BP and not it.get("preorder") and it.get("id")]

    def purch_dl_playlist_preview(self, keys_=None) -> dict:
        import datetime
        items = self._bp_open_items(keys_)
        day = datetime.date.today().isoformat()
        chunks = [{"name": f"{self.DL_PREFIX}{day}_{n + 1}", "count": len(items[k:k + 100])}
                  for n, k in enumerate(range(0, len(items), 100))]
        return {"count": len(items), "chunks": chunks, **self.purch_bp_settings()}

    def start_purch_dl_playlist(self, keys_=None):
        """„Download Tracks“: Titel ohne lokale Datei in TagStudio_DOWNLOAD_<Datum>_<n> (je 100) eintragen; eine schon
        vorhandene Playlist gleichen Namens wird ersetzt, überzählige vom selben Tag geleert – nichts häuft sich an."""
        pv = self.purch_dl_playlist_preview(keys_)
        if not pv["count"]:
            return {"ok": False, "error": "Keine Beatport-Käufe ohne Datei."}
        ids = [str(it["id"]) for it in self._bp_open_items(keys_)]

        def job(cancel, progress):
            out, notes = [], []
            for n, ch in enumerate(pv["chunks"]):
                progress(("text", f"Beatport: {ch['name']} …"))
                r = self.plugins.call_playlist(self.BP, "store_playlist_put", ch["name"], ids[n * 100:(n + 1) * 100], True,
                                               session=self, cancel=cancel, progress=progress)
                out.append(r)
                if r.get("note"):
                    notes.append(r["note"])
            day_prefix = pv["chunks"][0]["name"].rsplit("_", 1)[0] + "_"
            names = {c["name"] for c in pv["chunks"]}
            for p in self.plugins.call_playlist(self.BP, "store_playlist_list", day_prefix, session=self) or []:
                if p["name"] not in names:                     # vom selben Tag übrig (früher mehr Titel) → leeren
                    r = self.plugins.call_playlist(self.BP, "store_playlist_put", p["name"], [], True, session=self)
                    if r.get("note"):
                        notes.append(r["note"])
            return {"ok": True, "playlists": out, "notes": notes, "count": len(ids)}
        return self._run("purch", "Download-Playlists in Beatport", job)

    def start_purch_dl_cleanup(self):
        """„Aufräumen“: alle TagStudio_DOWNLOAD_…-Playlists in Beatport löschen (die Oberfläche fragt vorher)."""
        def job(cancel, progress):
            progress(("text", "Beatport: Download-Playlists löschen …"))
            r = self.plugins.call_playlist(self.BP, "store_playlist_delete", self.DL_PREFIX, session=self)
            return {"ok": True, **r}
        return self._run("purch", "Download-Playlists aufräumen", job)

    def purch_buy_playlists_preview(self, prefix=None, since="", until="") -> dict:
        """Playlists je Kaufdatum: Datum, Name, Anzahl (Beatport-Käufe mit Kaufdatum, ohne Vorbestellungen)."""
        s = self.purch_bp_settings()
        prefix = prefix or s.get("buy_prefix") or "TagStudio_BUY_"
        days: dict = {}
        with self.lock:
            for it in self._purch().data["items"].values():
                d = str(it.get("bought") or "")[:10]
                if it.get("store") != self.BP or it.get("preorder") or not it.get("id") or not d:
                    continue
                if (since and d < since) or (until and d > until):
                    continue
                days.setdefault(d, []).append(str(it["id"]))
        rows = []
        for d in sorted(days, reverse=True):
            ids = list(dict.fromkeys(days[d]))
            base = prefix + d.replace("-", "_")
            for n, k in enumerate(range(0, len(ids), 100)):
                rows.append({"date": d, "name": base if n == 0 else f"{base}_{n + 1}", "ids": ids[k:k + 100],
                             "count": len(ids[k:k + 100])})
        return {"rows": rows, "prefix": prefix, **{k: v for k, v in s.items() if k != "buy_prefix"}}

    def start_purch_buy_playlists(self, prefix=None, since="", until=""):
        """Je Kaufdatum eine Playlist PREFIX_JJJJ_MM_TT – vorhandene werden nur ergänzt, keine Doppelten."""
        if prefix:
            self.purch_bp_settings({"buy_prefix": str(prefix)})
        pv = self.purch_buy_playlists_preview(None, since, until)
        if not pv["rows"]:
            return {"ok": False, "error": "Keine Beatport-Käufe mit Kaufdatum im gewählten Zeitraum."}

        def job(cancel, progress):
            out = []
            for i, r in enumerate(pv["rows"]):
                if cancel.is_set():
                    break
                progress(("progress", i, len(pv["rows"]), r["name"]))
                out.append(self.plugins.call_playlist(self.BP, "store_playlist_put", r["name"], r["ids"], False,
                                                      session=self, cancel=cancel, progress=progress))
            return {"ok": True, "playlists": out, "added": sum(x.get("added", 0) for x in out),
                    "created": sum(1 for x in out if x.get("created"))}
        return self._run("purch", "Playlists je Kaufdatum in Beatport", job)

    # ---- #336: ZIP-Downloads automatisch entpacken
    def _unzip_on(self) -> bool:
        return self.cfg.get("unzip_auto", True) is not False

    def set_unzip_auto(self, on) -> bool:
        self.cfg["unzip_auto"] = bool(on)
        core.save_config({"unzip_auto": bool(on)})
        return bool(on)

    def _purch_dl_folders(self) -> list:
        """Download-Ordner der Käufe: eigenes Ziel bzw. je Store der Unterordner der Rolle „Downloads“ plus _Manuell."""
        dest, why = self._purch_dest()
        if not why.startswith("Downloads"):
            return [dest] if dest else []
        out = [self._source_dir(s["id"]) for s in self.plugins.store_sources()]
        out.append(self._source_dir(""))                     # unbekannte Quelle → Downloads\\_Manuell
        return [p for p in dict.fromkeys(out) if p and os.path.isdir(p)]

    def _unzip(self, folders_) -> dict:
        import applog
        import unzip
        if not self._unzip_on():
            return {"zips": [], "files": 0, "skipped": 0, "errors": [], "off": True}
        r = unzip.unpack_folders(folders_)
        for z in r["zips"]:
            applog.info(f"ZIP entpackt: {z['zip']} – {len(z['files'])} Datei(en), {len(z['skipped'])} übersprungen"
                        + (f", {z['error']}" if z["error"] else ""))
        return r

    def purch_unzip(self) -> dict:
        """#336: beim Öffnen der Seite „Käufe“ neue ZIPs in den Download-Ordnern entpacken."""
        return self._unzip(self._purch_dl_folders())

    def purch_set_dest(self, path) -> dict:
        p = os.path.abspath(os.path.expanduser(str(path).strip())) if str(path or "").strip() else ""
        self.cfg["purch_dest"] = p
        core.save_config({"purch_dest": p})
        return self.purch_state()

    @staticmethod
    def _purch_row(k, it) -> dict:
        code = keys.parse_key(it.get("key") or "")
        return {"k": k, "store": it["store"], "id": it["id"], "title": it.get("title", ""), "mix": it.get("mix", ""),
                "artist": it.get("artist", ""), "dur": it.get("dur") or 0, "key": code or "", "bpm": it.get("bpm"),
                "catalog": it.get("catalog", ""), "label": it.get("label", ""), "release": it.get("release", ""),
                "genre": it.get("genre", ""), "isrc": it.get("isrc", ""), "url": it.get("url", ""),
                "bought": it.get("bought", ""), "seen": it.get("first_seen") or 0, "status": it.get("status", "missing"),
                "file": it.get("file", ""), "reason": it.get("reason", ""), "preorder": bool(it.get("preorder")),
                "cands": list(it.get("cands") or []), "linked": bool(it.get("linked")), "received": bool(it.get("received")),
                "downloaded": it.get("downloaded") or 0, "kind": it.get("kind", "")}

    def purch_state(self) -> dict:
        with self.lock:
            st = self._purch()
            rows = [self._purch_row(k, it) for k, it in st.data["items"].items()]
            stores = dict(st.data["stores"])
        rows.sort(key=lambda r: (r["bought"] or "", r["seen"]), reverse=True)
        count = {s: 0 for s in purchases.STATUSES}
        for r in rows:
            count[r["status"]] = count.get(r["status"], 0) + 1
        dest, why = self._purch_dest()
        return {"rows": rows, "stores": stores, "sources": self.plugins.store_sources(), "count": count,
                "last": dict(getattr(self, "_purch_last", {}) or {}),
                "dest": dest, "dest_from": why, "dest_ok": bool(dest) and os.path.isdir(dest), "unzip": self._unzip_on(),
                "strict": self._purch_strict(),
                "roots": self._pl_lib_roots(), **self._lib_info(), "sessions": self._purch_sessions()}

    def _purch_index(self, cancel, progress):
        """Bibliothek (wie bei den Playlists) plus Eingangsordner."""
        dest, _why = self._purch_dest()
        roots = self._pl_lib_roots()
        if dest and os.path.isdir(dest) and playlists.nk(dest) not in {playlists.nk(r) for r in roots}:
            roots = roots + [dest]
        return playlists.LibIndex(self._pl_lib_index(cancel, progress, roots)), dest

    def _purch_since(self, store, full=False) -> str:
        """Ab welchem Tag holen? "" = alles (erstes Mal, Wunsch oder letzte volle Abfrage älter als FULL_EVERY)."""
        import datetime
        import time
        st = self._purch()
        meta = st.data["stores"].get(store) or {}
        if full or time.time() - int(meta.get("full_at") or 0) > FULL_EVERY:
            return ""
        dates = [it.get("bought", "")[:10] for it in st.data["items"].values() if it.get("store") == store and it.get("bought")]
        if not dates:
            return ""
        d = datetime.date.fromisoformat(max(dates)) - datetime.timedelta(days=OVERLAP_DAYS)
        return d.isoformat()

    def _purch_diag(self, index, dest) -> dict:
        """Was wurde verglichen? Ordner, Anzahl Dateien, zusammengefasste Doppelte (gleiche Datei unter 2. Pfad)."""
        roots = self._pl_lib_roots()
        if dest and os.path.isdir(dest) and playlists.nk(dest) not in {playlists.nk(r) for r in roots}:
            roots = roots + [dest]
        dupes = getattr(index, "dupes", [])
        d = {"roots": roots, **self._lib_info(), "files": len(index), "dupes": len(dupes),
             "examples": [{"path": a, "same": b} for a, b in dupes[:5]]}
        self._purch_last = d
        return d

    def purch_link(self, key, path="") -> dict:
        """Unklaren (oder anderen) Kauf von Hand einer Datei zuordnen; path "" hebt die Zuordnung auf (#290)."""
        dest, _why = self._purch_dest()
        with self.lock:
            self._purch().link(str(key), str(path or ""), dest)
        return self.purch_state()

    def start_purch_refresh(self, stores=None, full=False):
        """Käufe der Stores holen (None = alle bereiten), zusammenführen, mit der Bibliothek abgleichen. Nach dem
        ersten Mal nur neue Käufe (Filter Kaufdatum), alle FULL_EVERY Tage bzw. mit full=True die ganze Liste."""
        src = [s for s in self.plugins.store_sources() if stores is None or s["id"] in stores]
        if not src:
            return {"ok": False, "error": "Kein Store eingerichtet – zuerst im Plugin „Beatport“ anmelden."}

        def job(cancel, progress):
            new, errors = 0, []
            for s in src:
                if not s["ready"]:
                    errors.append(f"{s['name']}: {s['why']}")
                    continue
                progress(("text", f"{s['name']}: gekaufte Titel lesen …"))
                with self.lock:
                    since = self._purch_since(s["id"], bool(full))
                try:
                    r = self.plugins.call_playlist(s["id"], "store_purchases", since, session=self, cancel=cancel,
                                                   progress=progress) or {}
                except core.Cancelled:
                    raise
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"{s['name']}: {ex}")
                    continue
                with self.lock:
                    m = self._purch().merge(s["id"], r.get("name") or s["name"], r.get("items") or [],
                                            full=not r.get("since"))
                new += m["new"]
            progress(("text", "Mit der Bibliothek abgleichen …"))
            index, dest = self._purch_index(cancel, progress)
            with self.lock:
                count = self._purch().match(index, dest, self._purch_strict())
            return {"ok": True, "new": new, "count": count, "errors": errors, "library": len(index),
                    "diag": self._purch_diag(index, dest)}
        return self._run("purch", "Käufe aktualisieren", job)

    def start_purch_match(self):
        """Nur neu abgleichen (z. B. nach dem Übernehmen in die Bibliothek)."""
        def job(cancel, progress):
            index, dest = self._purch_index(cancel, progress)
            with self.lock:
                count = self._purch().match(index, dest, self._purch_strict())
            return {"ok": True, "new": 0, "count": count, "errors": [], "library": len(index),
                    "diag": self._purch_diag(index, dest)}
        return self._run("purch", "Käufe abgleichen", job)

    def purch_session_login(self, store, username, password) -> dict:
        """#295: Anmeldung nur für diese Sitzung (Download wie die Webseite). Passwort wird nicht gespeichert."""
        r = self.plugins.call_playlist(str(store), "store_login", username, password, session=self) or {}
        return {"ok": bool(r.get("ok")), "username": r.get("username", ""), "sessions": self._purch_sessions()}

    def purch_session_logout(self, store) -> dict:
        self.plugins.call_playlist(str(store), "store_logout", session=self)
        return {"ok": True, "sessions": self._purch_sessions()}

    def _purch_sessions(self) -> dict:
        out = {}
        for s in self.plugins.store_sources():
            try:
                out[s["id"]] = self.plugins.call_playlist(s["id"], "store_session", session=self) or {}
            except Exception:  # noqa: BLE001 – Store ohne Sitzungs-Anmeldung
                pass
        return out

    def start_purch_download(self, keys_=None):
        """Gewählte (bzw. alle fehlenden) Käufe in den Eingangsordner laden. keys_: ["store:id", …]."""
        dest, why = self._purch_dest()
        if not dest:
            return {"ok": False, "error": "Kein Eingangsordner – Basisordner einstellen oder unter „Käufe“ einen Ordner wählen."}
        if not os.path.isdir(dest):
            if os.path.isdir(os.path.dirname(os.path.normpath(dest))):
                os.makedirs(dest, exist_ok=True)                # 00_New im Basisordner anlegen
            else:
                return {"ok": False, "error": f"Eingangsordner nicht gefunden: {dest}"}
        with self.lock:
            items = self._purch().data["items"]
            todo = [dict(items[k], key=k) for k in (keys_ if keys_ else list(items))
                    if k in items and (keys_ or items[k].get("status") == "missing") and not items[k].get("preorder")]
        if not todo:
            return {"ok": False, "error": "Nichts herunterzuladen – alle gekauften Titel sind schon vorhanden."}
        by_store: dict[str, list] = {}
        for it in todo:
            by_store.setdefault(it["store"], []).append(it)

        def job(cancel, progress):
            got, failed, manual, need = 0, [], [], []
            for store, its in by_store.items():
                to = self._purch_dest_for(store, dest, why)
                try:
                    os.makedirs(to, exist_ok=True)
                    r = self.plugins.call_playlist(store, "store_download", its, to, session=self, cancel=cancel,
                                                   progress=progress) or {}
                except core.Cancelled:
                    raise
                except Exception as ex:  # noqa: BLE001
                    failed.append(f"{store}: {ex}")
                    continue
                with self.lock:
                    st = self._purch()
                    for sid, files in (r.get("files") or {}).items():
                        if files:
                            st.set_file(purchases.key_of(store, sid), files[0], downloaded=True)
                            got += 1
                    st.save()
                failed += r.get("failed") or []
                if r.get("need_login"):                     # #295: Sitzungs-Anmeldung wie die Webseite anbieten
                    with self.lock:
                        nm = (self._purch().data["stores"].get(store) or {}).get("name") or self.plugins.get(store).name
                    need.append({"store": store, "name": nm, "keys": [it["key"] for it in its]})
                    continue
                if r.get("manual"):                         # Store lässt den Download nicht zu → selbst laden
                    with self.lock:
                        name = (self._purch().data["stores"].get(store) or {}).get("name") or self.plugins.get(store).name
                    manual.append({"store": store, "name": name, "url": r["manual"]})
            return {"ok": True, "downloaded": got, "failed": failed, "dest": dest, "manual": manual, "need_login": need}
        return self._run("purch_dl", "Käufe herunterladen", job)
