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
import re
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
import i18n  # noqa: E402
import instance  # noqa: E402
import updater  # noqa: E402
from version import VERSION  # noqa: E402

APP = "MarKusSXCH TagStudio"
WEB = os.path.join(HERE, "web")


# Sitzungs-Methoden, die die Oberfläche direkt aufrufen darf
_STARTED = time.time()
APP_LOGS = "@app"          # #327: Live-Fenster für alle Protokolle im Log-Ordner (Einstellungen › Expert)

_PASS = {
    "tag_locate",                                                   # #175
    "services_overview", "service_detail", "start_service_api", "start_service_fields", "service_session", "start_service_access", "start_service_test",   # #204
    "add_field_choices", "add_field", "bulk_keys", "bulk_apply", "cover_remove",
    "fixer_settings", "fixer_preview", "fixer_apply", "set_fixer_exceptions", "fixer_exception_candidates",
    "purch_unzip", "set_unzip_auto", "set_purch_strict", "purch_candidates", "purch_fix_file",
    "purch_bp_settings", "purch_bp_check", "purch_dl_playlist_preview", "start_purch_dl_playlist", "purch_reset_preview", "start_purch_reset", "purch_dl_signature", "purch_pickup", "purch_move_preview", "purch_move", "start_purch_dl_cleanup",
    "purch_buy_playlists_preview", "start_purch_buy_playlists", "smart_list", "smart_set_out", "smart_save", "smart_delete", "smart_select", "smart_import", "smart_preview", "smart_apply",
    "backups", "set_backup", "start_backup_check", "start_restore", "backup_diff", "delete_backup",
    "start_tag_load", "start_tag_load_files", "tagger_settings", "tag_state_save", "tag_rows", "tag_rows_preview", "tag_detail_file", "tag_cover_thumb_store", "tag_detail", "tag_set", "tag_set_rating", "player_mark", "tag_remove", "tag_add_field",
    "tag_cover", "tag_version", "tag_from_filename", "tag_rename", "tag_number", "tag_xml", "tag_blob", "tag_blob_set", "cmp_blob", "cmp_blob_set", "blob_pretty", "players", "set_players", "play_external", "wave_save", "settings_page", "set_trivial", "set_save_version", "set_save_v1", "set_stamp_edited", "set_wave_in_file", "cloud_sync_overview", "cloud_sync_set", "start_cloud_sync", "cloud_pending", "cloud_resolve", "cloud_gone", "set_stamp_added", "tag_added", "set_player_pref", "player_defaults", "player_resume_save", "player_resume", "set_player_window", "bus_post", "bus_poll", "bus_peer", "bus_reset", "bus_sync", "media_cover", "media_lyrics", "tag_grid_status", "tag_beatgrid", "i18n_catalog", "i18n_overlay_info", "i18n_export_text", "i18n_import_preview", "i18n_import_apply", "i18n_overlay_reset", "settings_export_text", "settings_import_preview", "settings_import", "settings_reset", "tag_origins", "set_tag_origins", "tag_origin_remove", "jobs_status", "job_cancel", "jobs_cancel_all", "jobs_clear", "jobs_resume", "tag_attach_stems", "set_stems_flat", "set_feat_scale", "tag_stem_tags", "set_origin_std_badge", "set_origin_ver_badge", "set_origin_label", "cache_info", "cache_clear", "set_list_cache", "verify_status", "tag_cover_thumb", "reload_pair", "set_default_dir", "set_view_default", "cmp_defaults_apply", "start_cache_build", "compare_origin_remove", "save_conflicts", "save_merge_external", "snap_overview", "snap_list", "snap_add_library", "snap_remove_library", "snap_update_library", "snap_update", "snap_delete", "snap_prune", "snap_create", "snap_baseline_info", "snap_set_baseline", "snap_startup", "snap_set", "start_snap_journal", "snap_revert", "start_snap_move", "snap_detect", "snap_use", "snap_ignore", "snap_watch", "snap_watch_ack",
    "tag_case_modes", "tag_case", "recipes", "recipes_save", "recipes_reset", "tag_recipe", "tag_replace", "tag_folder_cover", "tag_key_notation", "tag_key_set", "tag_key_convert", "tag_feature_set", "tag_features_open", "tag_mood", "tag_mood_suggest", "set_mood_list",
    "dj_state", "dj_add", "dj_add_paths", "dj_sources", "start_dj_source_list", "start_dj_source_import", "dj_remove", "dj_clear", "dj_order", "dj_lock", "dj_set_opt", "dj_optimize", "dj_revert", "dj_tag_indices",
    "dj_lists", "dj_save_as", "dj_load", "dj_new", "dj_list_delete", "dj_list_rename",
    "pq_state", "pq_add", "pq_set", "pq_take", "pq_to_djset",
    "pl_list", "pl_state", "pl_tag_indices", "pl_files", "pl_create", "pl_rename", "pl_move", "pl_meta", "pl_duplicate",
    "pl_merge", "pl_smart_info", "pl_smart_save", "start_pl_smart_refresh", "pl_smart_stale", "pl_smart_freeze", "pl_push_targets", "start_pl_push", "purch_state", "purch_set_dest", "purch_link", "start_purch_refresh", "start_purch_match", "start_purch_download", "purch_session_login", "purch_session_logout", "pl_add_tag", "pl_add_paths", "pl_remove", "pl_order", "pl_undo", "pl_redo", "pl_folder_create",
    "pl_folder_rename", "pl_folder_remove", "pl_folder_archive", "pl_archive", "pl_restore", "pl_delete", "pl_external",
    "pl_external_apply", "set_playlist_dir", "pl_to_queue", "start_pl_match", "start_pl_find_missing", "pl_relink", "pl_relink_many",
    "pl_import_file", "start_pl_source_import", "pl_dj_libraries", "start_pl_dj_scan", "start_pl_dj_import",
    "pl_import_text",
    "help_docs", "help_licenses", "help_lic_mark", "feedback_info", "feedback_search", "feedback_prepare", "feedback_translation", "help_tags", "start_tag_scan", "tag_field_filter",
    "setup_state", "setup_finish", "set_nav_hidden", "set_nav_order", "first_steps_seen", "first_steps_restart", "set_first_steps", "whats_new", "whats_new_seen", "folders_overview", "folders_get", "folders_set_base", "folders_set_role", "folders_lib_add", "folders_lib_update", "folders_lib_remove", "folders_create", "folders_review_apply", "folders_adopt", "folders_menu", "folders_recent_add", "folders_mkdir", "folders_cloud_online", "folders_change_preview", "start_folders_change", "folders_remove_empty", "set_base_dir", "setup_structure", "set_archive_dir", "tag_archive", "prep_archive", "archive_list", "archive_restore",
    "disc_overview", "disc_follow_save", "disc_follow_edit", "disc_clear", "start_disc_bp_follow", "start_disc_related", "disc_set", "disc_genres", "disc_auto", "disc_auto_status", "start_disc_suggest", "start_disc_run",
    "prep_overview", "prep_pending", "start_prep_fetch", "prep_workflow_save", "prep_workflow_new", "prep_workflow_delete", "prep_export", "prep_import", "start_prep_run", "prep_refresh", "prep_mark", "prep_revert", "prep_allow", "prep_cleanup",
    "plugins_list", "plugin_log_read", "plugin_enable", "plugin_actions", "plugin_form", "start_plugin_action", "start_plugin_install", "plugin_apply",
    "start_plugin_catalog", "start_plugin_store_install", "plugin_store_revert",
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
        st["profile"] = self.profile_info()
        return st

    # ---------- Profile (#164, #165)
    def profile_info(self):
        import paths
        reg = paths.load_registry()
        return {"name": paths.profile_label(), "default": paths.profile() is None, "list": paths.list_profiles(),
                "ask": paths.should_ask() and not getattr(self, "_profile_asked", False), "ask_setting": reg["ask"],
                "dir": paths.data_dir(), "config": paths.config_file()}

    def profile_choose(self, name, ask=True):
        """Startauswahl bzw. Wechsel: anderes Profil → Neustart mit --profil NAME. → {"restart": bool}"""
        import paths
        n = paths.clean_name(name)
        if n is not None and n not in paths.list_profiles():
            raise ValueError(f"Profil „{name}“ gibt es nicht.")
        reg = paths.load_registry()
        reg["ask"] = bool(ask)
        reg["last"] = n or paths.DEFAULT
        paths.save_registry(reg)
        self._profile_asked = True
        if n == paths.profile():
            return {"restart": False}
        self._argv = [a for i, a in enumerate(self._argv)
                      if a not in ("--profil", "--profile") and not (i and self._argv[i - 1] in ("--profil", "--profile"))
                      and not a.startswith(("--profil=", "--profile="))]
        if n:
            self._argv += [f"--profil={n}"]
        self.restart()
        return {"restart": True}

    def profile_set_ask(self, ask):
        import paths
        reg = paths.load_registry()
        reg["ask"] = bool(ask)
        paths.save_registry(reg)
        return self.profile_info()

    def profile_create(self, name, copy_settings=False):
        import paths
        n = paths.create_profile(name, paths.profile_label() if copy_settings else None)
        info = self.profile_info()
        info["created"] = n
        return info

    def profile_shortcut(self, name):
        """Verknüpfung „TagStudio (Profil)“ auf dem Desktop (Windows: .lnk über PowerShell, sonst Startskript)."""
        import paths
        n = paths.clean_name(name)
        label = f"TagStudio ({n or paths.DEFAULT})"
        desk = os.path.join(paths.home(), "Desktop")
        os.makedirs(desk, exist_ok=True)
        target = sys.executable if getattr(sys, "frozen", False) else sys.executable
        args = [] if getattr(sys, "frozen", False) else [os.path.join(HERE, "tagstudio_web.py")]
        if n:
            args.append(f"--profil={n}")
        if sys.platform.startswith("win"):
            lnk = os.path.join(desk, label + ".lnk")
            argstr = " ".join(f'"{a}"' for a in args).replace("'", "''")
            ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('" + lnk.replace("'", "''") + "');"
                  "$s.TargetPath='" + target.replace("'", "''") + "';$s.Arguments='" + argstr + "';"
                  "$s.WorkingDirectory='" + os.path.dirname(target).replace("'", "''") + "';"
                  "$s.IconLocation='" + target.replace("'", "''") + "';$s.Save()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, capture_output=True,
                           creationflags=0x08000000)
            return {"ok": True, "path": lnk}
        path = os.path.join(desk, label + (".command" if sys.platform == "darwin" else ".sh"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\n" + " ".join(f'"{a}"' for a in [target, *args]) + ' "$@"\n')
        os.chmod(path, 0o700)          # nur für den eigenen Benutzer ausführbar (#171)
        return {"ok": True, "path": path}

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

    def snap_journal_export(self, fmt, rows, name="Journal"):
        """#59: sichtbares Änderungsjournal als Excel/CSV speichern (rows: Zeilen ohne Kopf)."""
        dest = self.save_dialog(self._s.snap_journal_export_name(fmt, name))
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.snap_journal_write(fmt, dest, rows)

    def disc_export(self, fmt, which="saved"):
        """#162: Merkliste von „Entdecken“ als Excel/CSV speichern."""
        dest = self.save_dialog(f"Merkliste.{'xlsx' if fmt == 'xlsx' else 'csv'}")
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.disc_export_write(fmt, dest, which)

    def pl_export(self, fmt, ids=None, folder=None, opts=None):
        """#271: Playlist(s) als M3U8, Rekordbox-XML oder CSV speichern."""
        dest = self.save_dialog(self._s.pl_export_name(ids, fmt, folder))
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.pl_export_file(fmt, dest, ids, folder, opts or {})

    def pl_shopping(self, ids=None, folder=None):
        """#271: Einkaufsliste (Titel ohne Datei, fehlende Dateien) als CSV speichern."""
        dest = self.save_dialog("Einkaufsliste.csv")
        if not dest:
            return {"ok": False, "cancelled": True}
        return self._s.pl_shopping_file(dest, ids, folder)

    def prep_export_file(self, wid):
        """#312: Workflow als JSON-Datei speichern (Speichern-Dialog im Export-Ordner)."""
        w = self._s._prep_get(wid)
        safe = re.sub(r'[<>:"/\\|?*]', "", w.get("name") or "Workflow").strip() or "Workflow"
        dest = self.save_dialog(f"Workflow – {safe}.json")
        if not dest:
            return {"ok": False, "cancelled": True}
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(self._s.prep_export(wid))
        except OSError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "path": dest}

    def pl_import(self, folder=""):
        """#271: M3U/M3U8, Rekordbox-XML oder CSV wählen und als Playlist(s) übernehmen."""
        p = self.pick_file("playlist")
        if not p:
            return {"cancelled": True}
        return self._s.pl_import_file(p, folder)

    def pl_dj_pick(self, app):
        """#278: Bibliotheksordner von Serato (_Serato_), Engine DJ (Engine Library) bzw. VirtualDJ wählen."""
        p = self.pick_path("", True, os.path.expanduser("~"))
        return {"path": p} if p else {"cancelled": True}

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

    # ---------- Protokolle der Plugins (#293)
    def plugin_log_folder(self, pid):
        """Log-Ordner öffnen, das Protokoll des Plugins markiert (falls vorhanden)."""
        import plugins
        p = os.path.join(plugins.log_dir(), f"{self._s.plugins.get(str(pid)).id}.log")
        if os.path.isfile(p) and self.reveal(p):
            return True
        return self.open_folder(plugins.log_dir())

    def log_window_open(self, pid):
        """Live-Protokoll in einem eigenen Fenster (je Plugin eines; #327: APP_LOGS = alle App-Protokolle).
        Im Browser-Modus öffnet die Oberfläche ein Popup."""
        import json as _json
        pid = APP_LOGS if pid == APP_LOGS else self._s.plugins.get(str(pid)).id
        if self._window is None:
            return {"ok": False, "browser": True}
        wins = self.__dict__.setdefault("_logwins", {})
        w = wins.get(pid)
        if w is not None:
            try:
                w.restore()
                w.show()
                return {"ok": True}
            except Exception:  # noqa: BLE001 – Fenster inzwischen zu
                wins.pop(pid, None)
        import webview
        try:
            w = webview.create_window(self._log_title(pid), url=os.path.join(WEB, "log-window.html"),
                                      js_api=self, width=900, height=560, min_size=(420, 240), background_color="#121419")
        except Exception as ex:  # noqa: BLE001
            return {"ok": False, "error": f"Fenster konnte nicht geöffnet werden: {ex}"}
        wins[pid] = w
        try:
            w.events.shown += lambda: titlebar_theme(w, getattr(self, "_dark", True))
            w.events.loaded += lambda: w.evaluate_js(f"lwStart({_json.dumps(pid)})")
            w.events.closed += lambda: wins.pop(pid, None)
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True}

    def _log_title(self, pid) -> str:
        if pid == APP_LOGS:
            return f"{APP} – {i18n.tr('Protokolle')}"
        return f"{APP} – {i18n.tr('Protokoll')} {self._s.plugins.get(pid).name}"

    def log_windows_close(self):
        for w in list(self.__dict__.get("_logwins", {}).values()):
            try:
                w.destroy()
            except Exception:  # noqa: BLE001
                pass
        self.__dict__["_logwins"] = {}
        return True

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
            w = webview.create_window(f"{APP} – {i18n.tr('Player')}", url=os.path.join(WEB, "player-window.html"), js_api=self,
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

    def i18n_export(self, lang, fmt="csv"):
        """#219: Texte einer Sprache in eine Datei schreiben (Speichern-Dialog)."""
        r = self._s.i18n_export_text(lang, fmt)
        dest = self.save_dialog(r["name"])
        if not dest:
            return {"ok": False, "cancelled": True}
        try:
            with open(dest, "w", encoding="utf-8", newline="") as fh:
                fh.write(r["text"])
        except OSError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "path": dest}

    def i18n_import_pick(self):
        """#219: Textdatei (CSV/JSON) wählen → Inhalt."""
        p = self.pick_file("texts", "")
        if not p:
            return None
        if os.path.getsize(p) > 8_000_000:
            return {"error": "Datei ist zu gross."}
        with open(p, encoding="utf-8-sig", errors="replace") as fh:
            return {"name": os.path.basename(p), "text": fh.read()}

    def settings_import_pick(self):
        """Einstellungsdatei wählen → Inhalt (für Vorschau und Import)."""
        p = self.pick_file("json", "")
        if not p:
            return None
        if os.path.getsize(p) > 4_000_000:
            return {"error": "Datei ist zu gross für eine Einstellungsdatei."}
        with open(p, encoding="utf-8", errors="replace") as fh:
            return {"name": os.path.basename(p), "text": fh.read()}

    def smart_export(self, ids=None):
        """#339: eigene Smart-Fix-Rezepte in eine Datei schreiben (Speichern-Dialog)."""
        dest = self.save_dialog("TagStudio-SmartFix.json")
        if not dest:
            return {"ok": False, "cancelled": True}
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(self._s.smart_export_text(ids))
        except OSError as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "path": dest}

    def smart_import_pick(self):
        """#339: Smart-Fix-Datei wählen → Inhalt."""
        return self.settings_import_pick()

    # ---------- System
    def pick_file(self, kind="image", start=""):
        """Datei wählen: kind = image | mp3."""
        start = start if start and os.path.isdir(start) else (os.path.dirname(start) if start else os.path.expanduser("~"))
        types = {"image": ("Bilder (*.jpg;*.jpeg;*.png;*.gif)", "Alle Dateien (*.*)"),
                 "mp3": ("MP3-Dateien (*.mp3;*.MP3)", "Alle Dateien (*.*)"),
                 "program": ("Programme (*.exe;*.app;*.bat;*.cmd)", "Alle Dateien (*.*)"),
                 "json": ("Einstellungen (*.json)", "Alle Dateien (*.*)"),
                 "texts": ("Texte (*.csv;*.json)", "Alle Dateien (*.*)"),
                 "playlist": ("Playlists (*.m3u;*.m3u8;*.xml;*.csv;*.txt)", "Alle Dateien (*.*)")}[kind]
        if self._window is not None:
            import webview
            res = self._window.create_file_dialog(webview.OPEN_DIALOG, directory=start, file_types=i18n.file_types(types))
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res) if res else ""
        return _tk_dialog("open", start, kind)

    def save_dialog(self, name):
        """Speichern-Dialog für alle Exporte – startet im Export-Ordner (#312), sonst im Benutzerordner."""
        exp = self._s.export_dir()
        start = exp or os.path.expanduser("~")
        if self._window is not None:
            import webview
            res = self._window.create_file_dialog(webview.SAVE_DIALOG, directory=start, save_filename=name)
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res) if res else ""
        p = _tk_dialog("save", start, name)
        if p:
            return p
        if sys.platform == "darwin":  # Browser-Modus auf dem Mac: kein Dialog möglich → Export-Ordner bzw. Downloads
            return os.path.join(exp or os.path.expanduser("~/Downloads"), name)
        return ""

    def pick_path(self, side, folder=True, start="", kind="mp3"):
        """Ordner- bzw. Dateiauswahl des Betriebssystems. Liefert den Pfad oder ''.
        kind (nur Dateien): "mp3" oder "program" (Programme, z. B. für externe Schritte im Workflow).
        Ohne Startpfad beginnt die Auswahl im Basisordner (#171), sonst im Benutzerordner."""
        if not start and kind != "program":
            base = self._s.base_dir()
            start = base if base and os.path.isdir(base) else ""
        start = start if start and os.path.isdir(start) else (os.path.dirname(start) if start else os.path.expanduser("~"))
        if start and not os.path.isdir(start):
            start = os.path.expanduser("~")
        if self._window is not None:
            import webview
            dlg = webview.FOLDER_DIALOG if folder else webview.OPEN_DIALOG
            types = () if folder else (("Programme (*.exe;*.app;*.bat;*.cmd)", "Alle Dateien (*.*)") if kind == "program"
                                       else ("MP3-Dateien (*.mp3;*.MP3)", "Alle Dateien (*.*)"))
            res = self._window.create_file_dialog(dlg, directory=start, file_types=i18n.file_types(types))
            if not res:
                return ""
            return os.path.normpath(res[0] if isinstance(res, (list, tuple)) else res)
        return _tk_pick(folder, start, kind)

    # ---------- Update
    def update_status(self, fetch=True):
        """Gibt es auf GitHub eine neue Version? Installierte App: über die GitHub-Releases (#89), Quellcode: über git."""
        ch = self._s.update_channel()
        if updater.frozen():
            st = updater.release_check(VERSION, ch) if fetch else {"ok": False, "error": None}
            st.update(kind="release", frozen=True, channel=ch, version=VERSION, behind=1 if st.get("newer") else 0,
                      auto=updater.auto_update_supported())                       # #234: Update auf Knopfdruck
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
        out["older"] = updater.changelog_versions(updater.local_changelog(), VERSION)     # #136: ältere Versionen
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

    def window_titles(self):
        """#304: Fenstertitel nach einem Sprachwechsel neu setzen (Hauptfenster mit Profil, Player, Protokolle)."""
        out = {"main": _title(), "lang": i18n.current()}
        if self._pwin is not None:
            out["player"] = f"{APP} – {i18n.tr('Player')}"
        wins = [(self._window, out["main"])] + ([(self._pwin, out["player"])] if "player" in out else [])
        for pid, w in self.__dict__.get("_logwins", {}).items():
            try:
                wins.append((w, self._log_title(pid)))
            except Exception:  # noqa: BLE001 – Plugin inzwischen entfernt
                pass
        for w, t in wins:
            if w is None:
                continue
            try:
                w.set_title(t) if hasattr(w, "set_title") else setattr(w, "title", t)
            except Exception:  # noqa: BLE001 – Fenster inzwischen zu
                pass
        return out

    def set_update_channel(self, channel):
        return self._s.set_update_channel(channel)

    # ---------- #234: Update auf Knopfdruck (installierte App, zuerst Windows)
    def start_app_update(self):
        """Installer der neuesten Version im gewählten Kanal laden und prüfen (Hintergrund-Vorgang mit Fortschritt)."""
        if not updater.auto_update_supported():
            return {"ok": False, "error": "Update auf Knopfdruck gibt es nur in der installierten App (Windows, macOS)."}
        import paths
        ch = self._s.update_channel()
        dest = paths.sub("Updates")

        def job(cancel, progress):
            rc = updater.release_check(VERSION, ch)
            if not rc.get("ok"):
                raise RuntimeError(rc.get("error") or "GitHub ist nicht erreichbar.")
            if not rc.get("newer"):
                return {"ok": False, "message": f"Du hast bereits die neueste Version ({VERSION})."}
            lt = rc["latest"]
            asset = updater.platform_asset(lt)
            if not asset:
                raise RuntimeError(f"Im Release {lt['version']} gibt es keinen Installer für dieses System.")
            progress(("text", f"Lade {asset['name']} …"))

            def prog(done, total):
                mb = lambda n: round(n / 1048576)                       # noqa: E731
                if total:
                    progress(("progress", mb(done), max(1, mb(total)), f"{asset['name']} (MB)"))
            path = updater.download_asset(asset, dest, prog, cancel.is_set)
            applog.info(f"Update {VERSION} → {lt['version']}: {asset['name']} geladen und geprüft")
            return {"ok": True, "path": path, "version": lt["version"], "beta": lt.get("beta", False)}
        return self._s._run("update", "Update wird geladen", job)

    def app_update_install(self, path):
        """Geladenen Installer still ausführen: TagStudio beendet sich, installiert und startet neu (#234, macOS #251)."""
        if not updater.auto_update_supported():
            return {"ok": False, "message": "Nur in der installierten App (Windows, macOS)."}
        import paths
        dest = os.path.normcase(os.path.abspath(paths.sub("Updates")))
        p = os.path.abspath(str(path or ""))
        ext = ".dmg" if sys.platform == "darwin" else ".exe"
        if os.path.normcase(os.path.dirname(p)) != dest or not p.lower().endswith(ext) or not os.path.isfile(p):
            return {"ok": False, "message": "Installer nicht gefunden – bitte das Update nochmals starten."}
        try:
            log = (updater.launch_mac_update if sys.platform == "darwin" else updater.launch_windows_update)(p, os.path.dirname(p))
        except RuntimeError as ex:
            return {"ok": False, "message": str(ex)}
        applog.info(f"Update: Installer gestartet ({os.path.basename(p)}), Protokoll {log}")
        self.quit(stop_jobs=True)
        return {"ok": True, "log": log}

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
        c = s.cfg or {}
        dev = {"log_clear_exit": bool(c.get("log_clear_exit", False)), "log_clear_plugins": bool(c.get("log_clear_plugins", False))}
        return {"facts": facts, "paths": paths, "dev": dev}

    def set_log_clear_exit(self, on, plugins=False):
        """#332 (Entwicklung): Protokolle beim Beenden/Neustart leeren – Standard aus; Plugin-Protokolle nur auf Wunsch."""
        import core
        on, plugins = bool(on), bool(plugins)
        self._s.cfg.update(log_clear_exit=on, log_clear_plugins=plugins)
        core.save_config({"log_clear_exit": on, "log_clear_plugins": plugins})
        return {"log_clear_exit": on, "log_clear_plugins": plugins}

    def _exit_sessions(self, wait=6.0):
        """#366: Sitzungs-Anmeldungen (Beatport) beim Beenden zurückziehen – höchstens wait Sekunden, nur einmal."""
        if getattr(self, "_sess_done", False):
            return
        self._sess_done = True
        fn = getattr(self._s, "end_store_sessions", None)
        if not callable(fn):
            return
        t = threading.Thread(target=lambda: fn(), daemon=True)
        t.start()
        t.join(wait)

    def _exit_logs(self):
        """#332: beim Beenden, Neustart und Update die Protokolle leeren, wenn eingeschaltet (nur einmal je Prozess).
        #366: vorher die Sitzungs-Anmeldungen zurückziehen (damit es noch im Protokoll steht)."""
        try:
            self._exit_sessions()
        except Exception:  # noqa: BLE001
            pass
        if getattr(self, "_logs_done", False):
            return []
        self._logs_done = True
        c = getattr(self._s, "cfg", None) or {}
        if not c.get("log_clear_exit"):
            return []
        try:
            return applog.clear_on_exit(plugins=bool(c.get("log_clear_plugins")))
        except Exception:  # noqa: BLE001 – Beenden darf daran nie scheitern
            return []

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
        return [{k: f[k] for k in ("name", "size", "mtime")} for f in applog.files()]

    def expert_log_read(self, name="", offset=-1, seq=0):
        """#327: App-Protokolle fortlaufend lesen – gleiche Antwort wie plugin_log_read (Live-Fenster)."""
        r = applog.read_from(str(name or ""), int(offset))
        r.update(live=[], seq=int(seq or 0), plugin=APP_LOGS, title=i18n.tr("Protokolle"), dir=applog.log_dir())
        return r

    def expert_log_clear(self, name):
        """#329: Protokoll leeren (die Oberfläche fragt vorher nach) – App- und Plugin-Protokolle im Log-Ordner."""
        ok = applog.clear(str(name or ""))
        if ok and os.path.basename(str(name)) != applog.NAME:
            applog.info(f"Protokoll geleert: {os.path.basename(str(name))}")
        return ok

    def expert_log_folder(self):
        return self.open_folder(applog.log_dir())

    def expert_log(self, name) -> dict:
        d = applog.log_dir()
        fp = os.path.join(d, os.path.basename(str(name)))
        if not os.path.isfile(fp):
            raise ValueError("Protokoll nicht gefunden")
        return {"path": fp, "text": applog.tail(fp)}

    def player_log(self, entry):
        """#181: Messwerte eines automatischen Übergangs ins App-Protokoll (nur Dateinamen, keine Pfade)."""
        if not isinstance(entry, dict):
            return False
        applog.info("Übergang: " + json.dumps(entry, ensure_ascii=False)[:4000])
        return True

    def start_mark(self, label):
        """#326: Schritte des Programmstarts mit Zeit seit dem Start ins App-Protokoll (Wartezeit eingrenzen)."""
        n = self.__dict__.setdefault("_marks", 0)
        if n >= 20 or time.time() - _STARTED > 300:
            return False
        self._marks = n + 1
        applog.info(f"Startablauf: {str(label)[:160]} – {time.time() - _STARTED:.1f} s nach dem Start")
        return True

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
        for _ in range(40):                            # #326: Sofortbild der Tagger-Liste fertig schreiben lassen
            if not getattr(self._s, "_tag_prev_busy", False):
                break
            time.sleep(0.05)
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
            self._exit_logs()                  # #332
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

    def instance_id(self):
        """#193: Kennung dieser Instanz – der Browser lädt nach einem Neustart erst neu, wenn die NEUE Instanz antwortet."""
        return f"{os.getpid()}-{_STARTED:.3f}"

    def _restart_cmd(self):
        """Befehl und Umgebung für den Neustart. #325: die Vergleichsordner nur mitgeben, wenn zuletzt der Vergleich
        offen war – Startpfade öffnen immer den Vergleich und überspringen Tagger und Fortsetzen; sonst startet die
        App normal auf der zuletzt benutzten Seite und setzt den Player fort."""
        l, r = self._s.left_root, self._s.right_root
        skip = ("--port", "--no-open") + (("--browser",) if self._server is not None else ())   # kommen unten dazu
        args = list(dict.fromkeys(a for a in self._argv if a.startswith("--") and a not in skip))
        cmd = [sys.executable, *args] if getattr(sys, "frozen", False) \
            else [sys.executable, os.path.join(HERE, "tagstudio_web.py"), *args]
        if (l or r) and (self._s.ui or {}).get("module") == "compare":
            cmd += [l, r] if r else [l]
        env = dict(os.environ, TAGSTUDIO_RESTART="1", TAGSTUDIO_NOASK="1")   # wartet auf diese Instanz; keine Profilwahl
        if self._server is not None:
            srv, token = self._server
            cmd += ["--browser", "--no-open", "--port", str(srv.server_address[1])]
            env["TAGSTUDIO_TOKEN"] = token
        return cmd, env

    def restart(self):
        """Programm mit dem neuen Stand neu starten (im Browser-Modus gleiche Adresse)."""
        cmd, env = self._restart_cmd()

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
            self._exit_logs()                  # #332: vor dem Start der neuen Instanz
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

    def open_log(self, path, folder=False):
        """#247: Protokoll aus einer Fehlermeldung öffnen – nur *.log im Log-Ordner von TagStudio.
        folder=True: Ordner mit markierter Datei zeigen."""
        import plugins
        root = os.path.normcase(os.path.abspath(plugins.log_dir()))
        p = os.path.normcase(os.path.abspath(str(path or "")))
        if not p.endswith(".log") or os.path.dirname(p) != root or not os.path.isfile(p):
            return False
        if folder:
            return self.reveal(os.path.abspath(str(path)))
        if sys.platform.startswith("win"):
            os.startfile(os.path.abspath(str(path)))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", os.path.abspath(str(path))])
        return True

    def pl_reveal(self, pid):
        """#267: M3U8 einer Playlist im Explorer/Finder zeigen (Playlist-Ordner bzw. Archiv)."""
        return self.reveal(self._s.pl_reveal_path(pid))

    def reveal_tag(self, i):
        """#197: Dateiordner eines Tagger-Titels öffnen (Datei markiert)."""
        s = self._s
        with s.lock:
            f = s.tag_files[i] if isinstance(i, int) and 0 <= i < len(s.tag_files) else None
        return self.reveal(f.path) if f is not None else False

    def reveal_side(self, side):
        """#197: Dateiordner der linken/rechten Datei des aktuellen Vergleichspaars öffnen."""
        s = self._s
        with s.lock:
            f = s._file(side) if side in ("L", "R") else None
        return self.reveal(f.path) if f is not None else False


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
                      "json": [("Einstellungen", "*.json")],
                      "texts": [("Texte", "*.csv *.json")],
                      "playlist": [("Playlists", "*.m3u *.m3u8 *.xml *.csv *.txt")]}.get(extra, [("MP3-Dateien", "*.mp3 *.MP3")])
                ft = [(i18n.tr(n), pat) for n, pat in ft + [("Alle Dateien", "*")]]          # #304
                p = filedialog.askopenfilename(initialdir=start, parent=root, filetypes=ft,
                                               title=i18n.tr("Datei wählen"))
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


def _tk_pick(folder, start, kind="mp3"):
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
                p = filedialog.askdirectory(initialdir=start, title=i18n.tr("Ordner wählen"), parent=root)
            else:
                ft = [("Programme", "*.exe *.app *.bat *.cmd"), ("Alle Dateien", "*")] if kind == "program" \
                    else [("MP3-Dateien", "*.mp3 *.MP3"), ("Alle Dateien", "*")]
                ft = [(i18n.tr(n), pat) for n, pat in ft]                                     # #304
                p = filedialog.askopenfilename(initialdir=start, parent=root, filetypes=ft,
                                               title=i18n.tr("Programm wählen" if kind == "program" else "MP3-Datei wählen"))
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
MAX_REQUEST = 64 << 20        # grösste API-Anfrage (64 MB)
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

        def _host_ok(self) -> bool:
            """Nur Aufrufe an die eigene Adresse (Schutz vor DNS-Rebinding fremder Webseiten)."""
            host = (self.headers.get("Host") or "").strip().lower()
            port = self.server.server_address[1]
            return host in (f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}")

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return self._send(403, b"forbidden", "text/plain")
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
            if not path.startswith("/api/") or not self._host_ok() \
                    or not secrets.compare_digest(self.headers.get("X-Token") or "", token):
                return self._send(403, b'{"error":"forbidden"}')
            name = path[5:]
            fn = getattr(api, name, None)
            if name.startswith("_") or not callable(fn):
                return self._send(404, b'{"error":"unknown"}')
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n < 0 or n > MAX_REQUEST:
                    return self._send(413, b'{"error":"too large"}')
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
    print(f"{APP} läuft im Browser: {url}\n(Fenster offen lassen; Beenden mit Strg+C)", flush=True)   # auch über eine Pipe sofort sichtbar
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    api.jobs_on_close()        # laufende Aufträge abbrechen, Warteschlange für den nächsten Start vermerken
    api._exit_logs()           # #332
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
        win = webview.create_window(_title(), **common, **kw)
    except TypeError:                                                    # ältere pywebview: ohne x/y/maximized
        win = webview.create_window(_title(), **common, width=kw["width"], height=kw["height"])
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
        win.events.closed += api.log_windows_close        # Live-Protokolle mit schliessen (#293)
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
    api._exit_logs()                                                     # #332: Fenster ohne quit() geschlossen
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


def _title() -> str:
    import paths
    return APP + (f" · {paths.profile()}" if paths.profile() else "")


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
