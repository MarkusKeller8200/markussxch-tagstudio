#!/usr/bin/env python3
"""
MarKusSXCH TagStudio – Web-Oberfläche.

Zeigt die Oberfläche aus dem Ordner web/ in einem eigenen App-Fenster (pywebview). Die Arbeit macht
derselbe Python-Kern wie bei der klassischen Oberfläche (session.py → core.py, id3tags.py …).

Ist pywebview nicht installiert (oder mit --browser), läuft die Oberfläche stattdessen im
Standard-Browser über einen lokalen Server (nur 127.0.0.1, mit Zugangsschlüssel).

    python tagstudio_web.py [links] [rechts] [--browser] [--port N] [--no-open]
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MIN_PYTHON = (3, 12)          # #135 – gleiche Version wie Installer und Stems-Umgebung
if sys.version_info < MIN_PYTHON:   # pragma: no cover – verständliche Meldung statt Folgefehlern
    sys.exit(f"TagStudio braucht Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} oder neuer (gefunden: {sys.version.split()[0]}).\n"
             "Neues Python: https://www.python.org/downloads/ – oder den Installer verwenden (bringt Python mit).")

from session import Session  # noqa: E402
import applog  # noqa: E402
import instance  # noqa: E402
import updater  # noqa: E402
from version import VERSION  # noqa: E402

APP = "MarKusSXCH TagStudio"
WEB = os.path.join(HERE, "web")


# Sitzungs-Methoden, die die Oberfläche direkt aufrufen darf
_STARTED = time.time()

_PASS = {
    "add_field_choices", "add_field", "bulk_keys", "bulk_apply", "cover_remove",
    "fixer_settings", "fixer_preview", "fixer_apply",
    "backups", "set_backup", "start_backup_check", "start_restore", "backup_diff", "delete_backup",
    "start_tag_load", "tagger_settings", "tag_state_save", "tag_rows", "tag_detail", "tag_set", "tag_set_rating", "player_mark", "tag_remove", "tag_add_field",
    "tag_cover", "tag_version", "tag_from_filename", "tag_rename", "tag_number", "tag_xml", "tag_blob", "tag_blob_set", "blob_pretty", "players", "set_players", "play_external", "wave_save", "settings_page", "set_trivial", "set_save_version", "set_player_pref", "player_defaults", "player_resume_save", "player_resume", "set_player_window", "bus_post", "bus_poll", "bus_peer", "bus_reset", "bus_sync", "media_cover", "settings_export_text", "settings_import_preview", "settings_import", "settings_reset", "tag_origins", "set_tag_origins", "tag_origin_remove", "jobs_status", "job_cancel", "jobs_cancel_all", "jobs_clear", "jobs_resume", "tag_attach_stems", "set_stems_flat", "set_feat_scale", "tag_stem_tags", "set_origin_std_badge", "set_origin_ver_badge", "set_origin_label", "cache_info", "cache_clear", "set_list_cache", "verify_status", "tag_cover_thumb", "reload_pair", "set_default_dir", "set_view_default", "cmp_defaults_apply", "start_cache_build", "compare_origin_remove", "save_conflicts", "save_merge_external", "snap_overview", "snap_list", "snap_add_library", "snap_remove_library", "snap_update_library", "snap_update", "snap_delete", "snap_prune", "snap_create", "snap_baseline_info", "snap_set_baseline", "snap_startup", "snap_set", "start_snap_journal", "snap_revert", "start_snap_move", "snap_detect", "snap_use", "snap_ignore", "snap_watch", "snap_watch_ack",
    "tag_case_modes", "tag_case", "tag_replace", "tag_folder_cover", "tag_key_notation", "tag_key_set", "tag_key_convert", "tag_feature_set", "tag_features_open",
    "dj_state", "dj_add", "dj_remove", "dj_clear", "dj_order", "dj_lock", "dj_set_opt", "dj_optimize", "dj_revert", "dj_tag_indices",
    "plugins_list", "plugin_enable", "plugin_actions", "plugin_form", "start_plugin_action", "start_plugin_install", "plugin_apply",
}


class Api:
    """Alle Funktionen, die die Oberfläche aufrufen darf (öffentliche Methoden)."""

    def __init__(self, start_paths=None, argv=None):
        self._s = Session()
        self._window = None
        self._start = start_paths or []
        self._argv = list(argv or [])   # für den Neustart nach einem Update
        self._server = None             # (srv, token) im Browser-Modus
        self._pwin = None               # abgedocktes Player-Fenster (#69, nur im App-Fenster)

    # ---------- Sitzung
    def settings(self):
        st = self._s.settings()
        st["start_paths"] = self._start
        st["native"] = self._window is not None
        return st

    def set_option(self, name, value):
        return self._s.set_option(name, value)

    def set_ui(self, name, value):
        return self._s.set_ui(name, value)

    def unsaved(self):
        return self._s.unsaved()

    def start_load(self, lp, rp, recursive=False, mode="filename", keep_current=False):
        return self._s.start_load(lp, rp, bool(recursive), mode, bool(keep_current))

    def start_save(self, force=False):
        return self._s.start_save(bool(force))

    def task_status(self):
        return self._s.task_status()

    def cancel_task(self):
        return self._s.cancel_task()

    def pair_rows(self):
        return self._s.pair_rows()

    def filter_pairs(self, query="", key=None, op="enthält", val="", side="links oder rechts"):
        return self._s.filter_pairs(query, key, op, val, side)

    def field_choices(self):
        return self._s.field_choices()

    def select(self, i):
        return self._s.select(None if i is None else int(i))

    def state(self):
        return self._s.state()

    # ---------- Ändern
    def copy_keys(self, keys, direction):
        return self._s.copy_keys(list(keys), direction)

    def copy_all(self, direction, delete_missing=None):
        return self._s.copy_all(direction, delete_missing)

    def copy_missing(self, direction):
        return self._s.copy_missing(direction)

    def remove(self, side, keys):
        return self._s.remove(side, list(keys))

    def set_value(self, side, key, text):
        return self._s.set_value(side, key, text)

    def revert_pair(self):
        return self._s.revert_pair()

    def get_xml(self, side, key):
        return self._s.get_xml(side, key)

    def xml_tool(self, action, text):
        return self._s.xml_tool(action, text)

    def discard_all(self):
        return self._s.discard_all()

    def undo(self):
        return self._s.do_undo()

    def redo(self):
        return self._s.do_redo()

    # ---------- Weitere Funktionen der Sitzung (Tag-Fixer, Sicherungen, Tagger, Felder, Sammelkopie, Bilder)
    def cover_replace(self, side, key, start=""):
        p = self.pick_file("image", start)
        return self._s.cover_set_file(side, key, p) if p else None

    def cover_export(self, side, key):
        name = self._s.cover_default_name(side, key)
        if not name:
            return {"ok": False, "error": "Kein Bild."}
        dest = self.save_dialog(name)
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.cover_export(side, key, dest)

    def tag_cover_file(self, idx, start=""):
        p = self.pick_file("image", start)
        return self._s.tag_cover(list(idx), p) if p else None

    def tag_export(self, idx, fmt="xlsx"):
        """Liste der Tagger-Dateien (Auswahl oder alle) als Excel/CSV speichern."""
        dest = self.save_dialog(self._s.tag_export_name(fmt))
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.tag_export_file(list(idx or []), fmt, dest)

    def dj_export(self, fmt, opts=None):
        """#4: DJ-Set als M3U8, Rekordbox-XML oder CSV speichern."""
        dest = self.save_dialog(self._s.dj_export_name(fmt))
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.dj_export_file(fmt, dest, opts or {})

    def backup_pick_folder(self):
        p = self.pick_path("", True, self._s._backup_folder())
        return self._s.set_backup(folder=p) if p else None

    def open_folder(self, path):
        if not path:
            return False
        os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
        return True

    # ---------- Wiedergabe
    def wave_missing(self):
        """#80: Titel ohne Wellenform – mit Adresse für den lokalen Medien-Server."""
        import media
        out = self._s.wave_missing()
        for x in out:
            x["url"] = media.SERVER.register(x["path"])
        return out

    def media_url(self, kind, ref):
        """Adresse für den Vorschau-Player (lokaler Server mit Range-Anfragen) plus Titelinfos."""
        import media
        info = self._s.media_info(kind, ref)
        info["url"] = media.SERVER.register(info["path"])
        info.update(self._s.media_extra(kind, ref))
        return info

    # ---------- abgedockter Player (#69)
    def player_window_open(self, two=False):
        """Eigenes Fenster für den Player. Im Browser-Modus öffnet die Oberfläche selbst ein Popup.
        two: Player B wird mit angezeigt (grössere Mindesthöhe)."""
        if self._window is None:
            return {"ok": False, "browser": True, **self._s.player_window_size(bool(two))}
        if self._pwin is not None:
            try:
                self._pwin.restore()
                self._pwin.show()
            except Exception:  # noqa: BLE001
                pass
            return {"ok": True}
        import webview
        g = self._s.player_window_size(bool(two))
        kw = {"width": g["w"], "height": g["h"]}
        if g.get("x") is not None and g.get("y") is not None:
            kw.update(x=g["x"], y=g["y"])
        try:
            w = webview.create_window(f"{APP} – Player", url=os.path.join(WEB, "player-window.html"), js_api=self,
                                      min_size=(760, 300), background_color="#121419", **kw)
        except Exception as ex:  # noqa: BLE001
            return {"ok": False, "error": f"Fenster konnte nicht geöffnet werden: {ex}"}
        self._pwin = w
        try:
            w.events.shown += lambda: titlebar_theme(w, getattr(self, "_dark", True))
        except Exception:  # noqa: BLE001
            pass

        def closed():
            self._pwin = None
            self._s.bus_post("pl_cmd", {"cmd": "dock"})
        try:
            w.events.closed += closed
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True}

    def player_window_close(self):
        w, self._pwin = self._pwin, None
        if w is not None:
            try:
                w.destroy()
            except Exception:  # noqa: BLE001
                pass
        return True

    # ---------- Hintergrund-Aufträge beim Beenden
    def jobs_on_close(self, win=None) -> bool:
        s = self._s
        if s._jobs is None or not s._jobs.status()["active"]:
            return True
        n = s._jobs.status()["active"]
        if win is not None and not win.create_confirmation_dialog(
                APP, f"{n} Hintergrund-Auftrag/-Aufträge (z. B. Stems) laufen noch.\n\nBeenden und abbrechen? "
                     "Die Warteschlange wird beim nächsten Start zum Fortsetzen angeboten."):
            return False
        s._jobs.shutdown(keep_queue=True)
        return True

    # ---------- Einstellungen exportieren/importieren (Dateidialoge)
    def settings_export(self):
        """Einstellungen in eine Datei schreiben (Speichern-Dialog)."""
        import time as _t
        dest = self.save_dialog(f"TagStudio-Einstellungen-{_t.strftime('%Y-%m-%d')}.json")
        if not dest:
            return {"ok": False, "cancelled": True}
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(self._s.settings_export_text())
        except OSError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "path": dest}

    def settings_import_pick(self):
        """Einstellungsdatei wählen → Inhalt (für Vorschau und Import)."""
        p = self.pick_file("json", "")
        if not p:
            return None
        if os.path.getsize(p) > 4_000_000:
            return {"error": "Datei ist zu groß für eine Einstellungsdatei."}
        with open(p, encoding="utf-8", errors="replace") as fh:
            return {"name": os.path.basename(p), "text": fh.read()}

    # ---------- System
    def pick_file(self, kind="image", start=""):
        """Datei wählen: kind = image | mp3."""
        start = start if start and os.path.isdir(start) else (os.path.dirname(start) if start else os.path.expanduser("~"))
        types = {"image": ("Bilder (*.jpg;*.jpeg;*.png;*.gif)", "Alle Dateien (*.*)"),
                 "mp3": ("MP3-Dateien (*.mp3;*.MP3)", "Alle Dateien (*.*)"),
                 "program": ("Programme (*.exe;*.app;*.bat;*.cmd)", "Alle Dateien (*.*)"),
                 "json": ("Einstellungen (*.json)", "Alle Dateien (*.*)")}[kind]
        if self._window is not None:
            import webview
            res = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=start, file_types=types)
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res) if res else ""
        return _tk_dialog("open", start, kind)

    def save_dialog(self, name):
        start = os.path.expanduser("~")
        if self._window is not None:
            import webview
            res = self._window.create_file_dialog(webview.SAVE_DIALOG, directory=start, save_filename=name)
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res) if res else ""
        p = _tk_dialog("save", start, name)
        if p:
            return p
        if sys.platform == "darwin":  # Browser-Modus auf dem Mac: kein Dialog möglich → Downloads
            return os.path.join(os.path.expanduser("~/Downloads"), name)
        return ""

    def pick_path(self, side, folder=True, start=""):
        """Ordner- bzw. Dateiauswahl des Betriebssystems. Liefert den Pfad oder ''."""
        start = start if start and os.path.isdir(start) else (os.path.dirname(start) if start else os.path.expanduser("~"))
        if self._window is not None:
            import webview
            kind = webview.FOLDER_DIALOG if folder else webview.OPEN_DIALOG
            types = () if folder else ("MP3-Dateien (*.mp3;*.MP3)", "Alle Dateien (*.*)")
            res = self._window.create_file_dialog(kind, directory=start, file_types=types)
            if not res:
                return ""
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res)
        return _tk_pick(folder, start)

    # ---------- Update
    def update_status(self, fetch=True):
        """Gibt es auf GitHub eine neue Version? Installierte App: über die GitHub-Releases (#89), Quellcode: über git."""
        ch = self._s.update_channel()
        if updater.frozen():
            st = updater.release_check(VERSION, ch) if fetch else {"ok": False, "error": None}
            st.update(kind="release", frozen=True, channel=ch, version=VERSION, behind=1 if st.get("newer") else 0)
        else:
            st = updater.status(bool(fetch), channel=ch)
            st.update(kind="git", version=VERSION)
        st["unsaved"] = self._s.unsaved()
        return st

    def release_notes(self):
        """#90: Versionshinweise der installierten Version (CHANGELOG) und – falls neuer – der neuesten auf GitHub."""
        ch = self._s.update_channel()
        out = {"version": VERSION, "beta": updater.is_beta(VERSION), "channel": ch, "releases_url": updater.RELEASES_URL,
               "current": updater.changelog_section(updater.local_changelog(), VERSION)}
        rc = updater.release_check(VERSION, ch)
        out.update(online=rc.get("ok", False), error=rc.get("error"), newer=rc.get("newer", False), note=rc.get("note"))
        lt = rc.get("latest")
        if lt:
            out["latest"] = {k: lt[k] for k in ("version", "beta", "url", "notes", "date")}
            out["current_url"] = f"{updater.RELEASES_URL}/tag/v{VERSION}"
        return out

    def set_titlebar(self, dark=True):
        """#103: Titelleiste(n) der App-Fenster an das Theme anpassen (nur Windows, sonst ohne Wirkung)."""
        self._dark = bool(dark)
        ok = titlebar_theme(self._window, self._dark)
        titlebar_theme(self._pwin, self._dark)
        return ok

    def set_update_channel(self, channel):
        return self._s.set_update_channel(channel)

    def apply_update(self):
        """Neue Version holen (git pull, nur Vorspulen). Danach restart() aufrufen."""
        if self._s.unsaved():
            return {"ok": False, "message": "Bitte zuerst speichern oder die Änderungen verwerfen."}
        if self._s.task.get("running"):
            return {"ok": False, "message": "Es läuft noch ein Vorgang."}
        return updater.pull(channel=self._s.update_channel())

    # ---------- Expert (#133): Einstellungsdatei, Protokolle, Diagnose
    _SECRET_KEYS = ("token", "password", "passwort", "secret", "api_key", "apikey")

    def _mask(self, v):
        if isinstance(v, dict):
            return {k: ("•••" if any(w in str(k).lower() for w in self._SECRET_KEYS) and v[k] else self._mask(v[k])) for k in v}
        if isinstance(v, list):
            return [self._mask(x) for x in v]
        return v

    def expert_info(self) -> dict:
        import platform
        import plugins as plg
        import appsettings
        try:
            import webview
            wv = getattr(webview, "__version__", "") or "installiert"
        except ImportError:
            wv = "nicht installiert"
        s = self._s
        cfg_path = appsettings.core.CONFIG
        paths = [["Einstellungsdatei", cfg_path], ["Sicherungen der Einstellungen", appsettings.BACKUP_DIR],
                 ["Protokolle", applog.log_dir()], ["Eigene Plugins", plg.user_dir()], ["Plugin-Daten", plg.data_root()],
                 ["Programmordner", HERE], ["Sperrdatei (eine Instanz)", instance.LOCKFILE]]
        try:
            pl = [f"{p['id']} {p.get('version', '')} ({'an' if p.get('enabled') else 'aus'}, {p.get('state', '')})"
                  for p in s.plugins_list()]
        except Exception as ex:  # noqa: BLE001
            pl = [f"(Fehler: {ex})"]
        try:
            jobs = s._jobs.status()["active"] if s._jobs is not None else 0
        except Exception:  # noqa: BLE001
            jobs = "?"
        facts = [["Version", VERSION], ["Python", f"{platform.python_version()} ({sys.executable})"],
                 ["Betriebssystem", f"{platform.platform()} · {platform.machine()}"],
                 ["Paket", "Installer (gepackt)" if getattr(sys, "frozen", False) else "Quellcode"],
                 ["Oberfläche", "App-Fenster" if self._window is not None else "Browser"], ["pywebview", wv],
                 ["Prozess", f"PID {os.getpid()} · läuft seit {time.strftime('%H:%M:%S', time.localtime(_STARTED))}"],
                 ["Einstellungsdatei", f"{os.path.getsize(cfg_path) // 1024 if os.path.isfile(cfg_path) else 0} KB"],
                 ["Laufende Aufträge", str(jobs)], ["Plugins", ", ".join(pl) or "keine"]]
        return {"facts": facts, "paths": paths}

    def expert_config(self) -> dict:
        """Einstellungsdatei (nur lesen); Werte unter Schlüsseln wie *token*/*password* werden ausgeblendet."""
        import appsettings
        p = appsettings.core.CONFIG
        try:
            with open(p, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as ex:
            return {"path": p, "text": "", "error": str(ex)}
        try:
            text = json.dumps(self._mask(json.loads(raw)), ensure_ascii=False, indent=2, sort_keys=True)
        except ValueError as ex:
            text, err = raw, f"Keine gültige JSON-Datei: {ex}"
            return {"path": p, "text": text, "error": err}
        return {"path": p, "text": text, "error": None}

    def expert_logs(self) -> list:
        d = applog.log_dir()
        out = []
        try:
            for n in os.listdir(d):
                fp = os.path.join(d, n)
                if os.path.isfile(fp):
                    st = os.stat(fp)
                    out.append({"name": n, "size": st.st_size, "mtime": st.st_mtime})
        except OSError:
            pass
        return sorted(out, key=lambda x: -x["mtime"])

    def expert_log(self, name) -> dict:
        d = applog.log_dir()
        fp = os.path.join(d, os.path.basename(str(name)))
        if not os.path.isfile(fp):
            raise ValueError("Protokoll nicht gefunden")
        return {"path": fp, "text": applog.tail(fp)}

    def client_log(self, level, msg):
        """Fehler aus der Oberfläche (JavaScript) ins App-Protokoll."""
        applog.write("WARN" if level != "error" else "ERROR", "Oberfläche: " + str(msg)[:2000])
        return True

    # ---------- Beenden, Fenster (#132, #134)
    def quit(self, stop_jobs=True):
        """Sauber beenden: Fenstergrösse speichern, Hintergrund-Aufträge anhalten (Warteschlange bleibt), Prozess beenden.
        Tagger-Zustand und Wiedergabe hat die Seite vorher gespeichert (appQuit)."""
        self._quitting = True
        applog.info("Beenden")
        geom = getattr(self, "_geom", None)
        if geom:
            try:
                self._s.set_window_geometry(geom)
            except Exception:  # noqa: BLE001
                pass
        s = self._s
        if stop_jobs and s._jobs is not None and s._jobs.status()["active"]:
            s._jobs.shutdown(keep_queue=True)

        def go():
            time.sleep(0.3)                    # Antwort noch an die Seite schicken
            if self._server is not None:
                try:
                    self._server[0].shutdown()
                except Exception:  # noqa: BLE001
                    pass
            os._exit(0)
        threading.Thread(target=go, daemon=False).start()
        return True

    def close_cancelled(self):
        """Seite hat das Beenden abgebrochen (z. B. ungespeicherte Änderungen behalten)."""
        self._close_req = 0.0
        return True

    def window_mode(self, what):
        """„fullscreen“ = Vollbild ein/aus, „window“ = zurück ins normale Fenster (aus Vollbild oder maximiert)."""
        w = self._window
        if w is None:
            return {"ok": False, "fullscreen": False}
        fs = bool(getattr(self, "_fs", False))
        try:
            if what == "fullscreen":
                w.toggle_fullscreen()
                fs = not fs
            elif what == "window":
                if fs:
                    w.toggle_fullscreen()
                    fs = False
                else:
                    w.restore()
            else:
                raise ValueError(f"Unbekannt: {what}")
        except AttributeError:
            return {"ok": False, "fullscreen": fs}
        self._fs = fs
        return {"ok": True, "fullscreen": fs}

    def restart(self):
        """Programm mit dem neuen Stand neu starten (gleiche Pfade, im Browser-Modus gleiche Adresse)."""
        l, r = self._s.left_root, self._s.right_root
        args = [a for a in self._argv if a.startswith("--") and a not in ("--port", "--no-open")]
        cmd = [sys.executable, *args] if getattr(sys, "frozen", False) \
            else [sys.executable, os.path.join(HERE, "tagstudio_web.py"), *args]
        if l or r:
            cmd += [l, r] if r else [l]
        env = dict(os.environ, TAGSTUDIO_RESTART="1")     # neue Instanz wartet, bis diese beendet ist
        if self._server is not None:
            srv, token = self._server
            cmd += ["--browser", "--no-open", "--port", str(srv.server_address[1])]
            env["TAGSTUDIO_TOKEN"] = token

        applog.info("Neustart")
        self._restarting = True                # Schliessen-Ereignis nicht mehr behandeln (keine Rückfragen, kein JS)
        geom = getattr(self, "_geom", None)
        if geom:
            try:
                self._s.set_window_geometry(geom)
            except Exception:  # noqa: BLE001
                pass

        def go():
            if self._server is not None:
                self._server[0].shutdown()
                self._server[0].server_close()
            kw = {"creationflags": 0x00000008 | 0x00000200} if sys.platform.startswith("win") else {"start_new_session": True}
            subprocess.Popen(cmd, cwd=HERE, env=env, close_fds=True, **kw)
            # Fenster nicht über destroy() schliessen: das löst das Schliessen-Ereignis aus und kann hängen bleiben,
            # sodass die alte Instanz offen bleibt. os._exit beendet Fenster und Prozess sofort.
            os._exit(0)
        t = threading.Timer(0.4, go)
        t.daemon = False  # sonst endet das Programm nach shutdown(), bevor der Neustart läuft
        t.start()
        return True

    def open_url(self, url):
        if url.lower().startswith("www."):
            url = "https://" + url
        if url.lower().startswith(("http://", "https://")):
            webbrowser.open(url)
        return True

    def reveal(self, path):
        """Datei im Explorer/Finder zeigen."""
        if not path or not os.path.exists(path):
            return False
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return True


def _passthrough(name):
    def method(self, *args):
        try:
            return getattr(self._s, name)(*args)
        except (ValueError, KeyError) as ex:           # Eingabe-/Bedienfehler: kurz protokollieren
            applog.warn(f"{name}: {ex}")
            raise
        except Exception as ex:  # noqa: BLE001
            applog.error(f"{name}: {ex}", ex)
            raise
    method.__name__ = name
    method.__doc__ = f"Weitergereicht an Session.{name}"
    return method


# echte Methoden (pywebview erkennt nur vorhandene Methoden, keine __getattr__-Tricks)
for _n in sorted(_PASS):
    setattr(Api, _n, _passthrough(_n))


def _tk_dialog(kind, start, extra=""):
    """Rückfall im Browser-Modus: open/save-Dialog über tkinter (nicht auf macOS)."""
    result = {"p": ""}

    def run():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            if kind == "save":
                ext = os.path.splitext(extra)[1]
                p = filedialog.asksaveasfilename(initialdir=start, initialfile=extra, defaultextension=ext, parent=root)
            else:
                ft = {"image": [("Bilder", "*.jpg *.jpeg *.png *.gif *.JPG *.JPEG *.PNG")],
                      "program": [("Programme", "*.exe *.bat *.cmd")],
                      "json": [("Einstellungen", "*.json")]}.get(extra, [("MP3-Dateien", "*.mp3 *.MP3")])
                p = filedialog.askopenfilename(initialdir=start, parent=root, filetypes=ft + [("Alle Dateien", "*")])
            root.destroy()
            result["p"] = os.path.normpath(p) if p else ""
        except Exception:  # noqa: BLE001
            result["p"] = ""
    if sys.platform == "darwin":
        return ""
    t = threading.Thread(target=run)
    t.start()
    t.join()
    return result["p"]


def _tk_pick(folder, start):
    """Rückfall für den Browser-Modus: Dialog über tkinter (falls vorhanden)."""
    result = {"p": ""}

    def run():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            if folder:
                p = filedialog.askdirectory(initialdir=start, title="Ordner wählen", parent=root)
            else:
                p = filedialog.askopenfilename(initialdir=start, title="MP3-Datei wählen", parent=root,
                                               filetypes=[("MP3-Dateien", "*.mp3 *.MP3"), ("Alle Dateien", "*")])
            root.destroy()
            result["p"] = os.path.normpath(p) if p else ""
        except Exception:  # noqa: BLE001
            result["p"] = ""
    if sys.platform == "darwin":  # Tk muss auf macOS im Hauptthread laufen – im Browser-Modus nicht möglich
        return ""
    t = threading.Thread(target=run)
    t.start()
    t.join()
    return result["p"]


# =========================================================================== Browser-Modus (lokaler Server)
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon", ".woff2": "font/woff2",
}


def make_server(api: Api, port: int = 0):
    """Lokaler HTTP-Server: liefert web/ aus und nimmt API-Aufrufe unter POST /api/<name> entgegen."""
    token = os.environ.pop("TAGSTUDIO_TOKEN", "") or secrets.token_urlsafe(24)  # Neustart: gleicher Schlüssel

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # ruhig bleiben
            pass

        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if path in ("", "/"):
                path = "/index.html"
            full = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
            if not full.startswith(WEB + os.sep) or not os.path.isfile(full):
                return self._send(404, b"not found", "text/plain")
            # Content-Type nur aus fester Liste (nie aus dem angefragten Pfad zusammengesetzt)
            ctype = STATIC_TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
            with open(full, "rb") as fh:
                self._send(200, fh.read(), ctype)

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            if not path.startswith("/api/") or self.headers.get("X-Token") != token:
                return self._send(403, b'{"error":"forbidden"}')
            name = path[5:]
            fn = getattr(api, name, None)
            if name.startswith("_") or not callable(fn):
                return self._send(404, b'{"error":"unknown"}')
            try:
                n = int(self.headers.get("Content-Length") or 0)
                args = json.loads(self.rfile.read(n) or b"[]")
                res = fn(*args)
                body = json.dumps({"ok": True, "result": res}, ensure_ascii=False).encode("utf-8")
                self._send(200, body)
            except Exception as ex:  # noqa: BLE001
                self._send(500, json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False).encode("utf-8"))

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    return srv, token


def run_browser(api: Api, port=0, open_browser=True):
    srv, token = make_server(api, port)
    api._server = (srv, token)
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html#token={quote(token)}"
    print(f"{APP} läuft im Browser: {url}\n(Fenster offen lassen; Beenden mit Strg+C)")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    api.jobs_on_close()        # laufende Aufträge abbrechen, Warteschlange für den nächsten Start vermerken
    return 0


# =========================================================================== App-Fenster (pywebview)
def _app_user_model_id():
    """#103 Windows: eigene App-Kennung, damit die Taskleiste das TagStudio-Symbol zeigt (nicht das von Python)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ch.markussxch.tagstudio")
        except Exception:  # noqa: BLE001
            pass


def titlebar_theme(win, dark: bool) -> bool:
    """#103 Windows 10/11: Titelleiste hell/dunkel wie das Theme der App (statt wie das System).
    Windows 11 zusätzlich in der Hintergrundfarbe der Seitenleiste."""
    if win is None or not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        hwnd = int(win.native.Handle.ToInt32())
        dwm = ctypes.windll.dwmapi
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):          # DWMWA_USE_IMMERSIVE_DARK_MODE (ab 20H1 = 20, davor 19)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4) == 0:
                break
        rgb = (0x0E, 0x10, 0x14) if dark else (0xEC, 0xEE, 0xF3)      # --side
        color = ctypes.c_int(rgb[0] | (rgb[1] << 8) | (rgb[2] << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), 4)  # DWMWA_CAPTION_COLOR (Windows 11)
        return True
    except Exception:  # noqa: BLE001 – anderes System / ältere pywebview
        return False


def run_window(api: Api):
    import webview
    _app_user_model_id()
    # #125: Grösse, Position und „maximiert“ vom letzten Mal (nur wenn sichtbar auf einem Bildschirm)
    try:
        screens = [(sc.x, sc.y, sc.width, sc.height) for sc in webview.screens]
    except Exception:  # noqa: BLE001 – ältere pywebview-Versionen
        screens = []
    kw = api._s.window_start(screens)
    geom = {"w": kw["width"], "h": kw["height"], "x": kw.get("x"), "y": kw.get("y"), "max": kw["maximized"]}
    common = dict(url=os.path.join(WEB, "index.html"), js_api=api, min_size=api._s.WIN_MIN, background_color="#121419")
    try:
        win = webview.create_window(APP, **common, **kw)
    except TypeError:                                                    # ältere pywebview: ohne x/y/maximized
        win = webview.create_window(APP, **common, width=kw["width"], height=kw["height"])
    api._window = win
    api._geom = geom

    def nums(a):                               # pywebview gibt evtl. zuerst das Fenster mit – nur Zahlen zählen
        return [v for v in a if isinstance(v, (int, float)) and not isinstance(v, bool)]

    def on_resized(*a):
        n = nums(a)
        if len(n) >= 2 and not geom["max"] and not getattr(api, "_fs", False):
            geom.update(w=n[0], h=n[1])

    def on_moved(*a):
        n = nums(a)
        if len(n) >= 2 and not geom["max"] and not getattr(api, "_fs", False):
            geom.update(x=n[0], y=n[1])

    def on_maximized(*_a):
        geom["max"] = True

    def on_restored(*_a):
        geom["max"] = False

    def flush_state():
        try:
            win.evaluate_js("appFlushState()")
        except Exception:  # noqa: BLE001
            pass

    def ask_page():
        try:
            win.evaluate_js("appQuit()")
        except Exception:  # noqa: BLE001
            api._close_req = 0.0

    def on_closing():
        if getattr(api, "_restarting", False) or getattr(api, "_quitting", False):
            return True
        # #132: Schliessen übernimmt die Seite (Hinweis „Einstellungen werden gespeichert“, Rückfragen, dann quit()).
        # Antwortet sie nicht, schliesst ein zweiter Klick auf X direkt (alter Weg unten).
        now = time.monotonic()
        if not getattr(api, "_close_req", 0.0) or now - api._close_req > 15:
            api._close_req = now
            threading.Thread(target=ask_page, daemon=True).start()
            return False
        # #126/#127: Tagger-Zustand und Wiedergabe noch speichern – in einem eigenen Faden mit Zeitlimit, denn
        # evaluate_js im Schliessen-Ereignis kann je nach System auf den Oberflächen-Faden warten und hängen.
        t = threading.Thread(target=flush_state, daemon=True)
        t.start()
        t.join(1.5)
        try:                                   # #125: Fenstergeometrie
            api._s.set_window_geometry(geom)
        except Exception:  # noqa: BLE001
            pass
        n = api.unsaved()
        if n and not win.create_confirmation_dialog(
                APP, f"{n} Datei(en) haben ungespeicherte Änderungen.\n\nTrotzdem beenden? (Änderungen gehen verloren)"):
            return False
        return api.jobs_on_close(win)
    try:
        win.events.closing += on_closing
        win.events.closed += api.player_window_close      # abgedockten Player mit schliessen (#69)
        for ev, fn in (("resized", on_resized), ("moved", on_moved), ("maximized", on_maximized), ("restored", on_restored)):
            event = getattr(win.events, ev, None)
            if event is not None:
                event += fn                               # pywebview: Event.__iadd__ hängt den Handler an
    except Exception:  # noqa: BLE001 – ältere pywebview-Versionen
        pass
    icon = os.path.join(WEB, "icon.ico" if sys.platform.startswith("win") else "icon.png")
    try:
        webview.start(icon=icon if os.path.isfile(icon) else None)     # #103: TagStudio-Symbol statt Python
    except TypeError:                                                    # ältere pywebview-Versionen
        webview.start()
    return 0


def selftest(out=None) -> int:
    """Prüft eine (gepackte) Installation: Oberfläche, Plugins, Fenster-Bibliothek, uv. Für die Installer-CI."""
    lines, ok = [], True

    def check(name, fn):
        nonlocal ok
        try:
            res = fn()
            lines.append(f"OK   {name}: {res}")
        except Exception as ex:  # noqa: BLE001
            ok = False
            lines.append(f"FAIL {name}: {type(ex).__name__}: {ex}")

    def web():
        assert os.path.isfile(os.path.join(WEB, "index.html")), WEB
        return WEB

    def plugin_list():
        import plugins as pl
        m = pl.Manager({})
        info = {p["id"]: p for p in m.list()}
        assert {"stems", "beatport"} <= set(info), sorted(info)
        assert info["beatport"]["state"] == "ready", info["beatport"]["error"]
        assert info["stems"]["state"] in ("ready", "missing"), info["stems"]["error"]
        return ", ".join(f"{k}={v['state']}" for k, v in sorted(info.items()))

    def uv():
        import plugins as pl
        return " ".join(pl.uv_command())

    def window():
        import webview  # noqa: F401
        return getattr(webview, "__version__", "ok")

    def session():
        from session import Session
        return Session().settings()["version"]

    check("Python", lambda: f"{sys.version.split()[0]} ({'gepackt' if getattr(sys, 'frozen', False) else 'Quellcode'})")
    check("Oberfläche", web)
    check("Sitzung", session)
    check("Plugins", plugin_list)
    check("uv", uv)
    check("pywebview", window)
    check("tkinter", lambda: __import__("tkinter").TkVersion)
    text = "\n".join(lines) + ("\nSELFTEST OK\n" if ok else "\nSELFTEST FEHLER\n")
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        i = argv.index("--selftest")
        return selftest(argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else None)
    browser = "--browser" in argv
    no_open = "--no-open" in argv
    port = 0
    if "--port" in argv:
        i = argv.index("--port")
        port = int(argv[i + 1])
        del argv[i:i + 2]
    paths = [a for a in argv if not a.startswith("--")][:2]
    applog.install_hooks()
    # nur eine Instanz: zwei gleichzeitige überschreiben sich die Einstellungen (z. B. nach einem Update)
    inst = instance.Instance()
    restart = os.environ.pop("TAGSTUDIO_RESTART", "") == "1"
    if not inst.acquire(wait=25.0 if restart else 2.0):
        applog.info(f"Zweiter Start abgelehnt (PID {os.getpid()}): TagStudio läuft bereits")
        instance.already_running_message("TagStudio läuft bereits.\n\nBitte das offene Fenster verwenden oder es zuerst "
                                         "schliessen. (Zwei gleichzeitige Instanzen würden sich die Einstellungen "
                                         "gegenseitig überschreiben.)", gui="--browser" not in argv)
        return 0
    applog.info(f"Start {VERSION} ({'Browser' if browser else 'Fenster'}, PID {os.getpid()})")
    api = Api(paths, argv)
    api._instance = inst
    if not browser:
        try:
            import webview  # noqa: F401
        except ImportError:
            print("pywebview ist nicht installiert – die Oberfläche öffnet sich im Browser.\n"
                  "Für ein eigenes Fenster: python -m pip install pywebview")
            browser = True
    if browser:
        return run_browser(api, port, not no_open)
    return run_window(api)


if __name__ == "__main__":
    sys.exit(main())
