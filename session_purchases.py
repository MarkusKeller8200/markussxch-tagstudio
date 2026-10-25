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
        """Eingangsordner für Downloads → (Pfad, Herkunft)."""
        own = str(self.cfg.get("purch_dest") or "")
        if own:
            return own, "eigene Wahl"
        try:
            inbox = self._prep_get().get("inbox") or ""
        except Exception:  # noqa: BLE001
            inbox = ""
        if inbox:
            return inbox, "Eingang von „Vorbereiten“"
        if self.cfg.get("base_dir"):
            return os.path.join(str(self.cfg["base_dir"]), NEW_DIR), "Basisordner"
        return "", ""

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
                "downloaded": it.get("downloaded") or 0}

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
                "dest": dest, "dest_from": why, "dest_ok": bool(dest) and os.path.isdir(dest),
                "roots": self._pl_lib_roots(), "sessions": self._purch_sessions()}

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
        d = {"roots": roots, "files": len(index), "dupes": len(dupes),
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
                count = self._purch().match(index, dest)
            return {"ok": True, "new": new, "count": count, "errors": errors, "library": len(index),
                    "diag": self._purch_diag(index, dest)}
        return self._run("purch", "Käufe aktualisieren", job)

    def start_purch_match(self):
        """Nur neu abgleichen (z. B. nach dem Übernehmen in die Bibliothek)."""
        def job(cancel, progress):
            index, dest = self._purch_index(cancel, progress)
            with self.lock:
                count = self._purch().match(index, dest)
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
        dest, _why = self._purch_dest()
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
                try:
                    r = self.plugins.call_playlist(store, "store_download", its, dest, session=self, cancel=cancel,
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
