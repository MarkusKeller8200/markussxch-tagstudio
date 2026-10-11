"""
session.py – Zustand und Befehle einer Vergleichssitzung, unabhängig von der Oberfläche.

Die Web-Oberfläche ruft diese Methoden auf; alle Ergebnisse sind JSON-taugliche dict/list.
Lange Vorgänge (Einlesen, Speichern) laufen im Hintergrund – Fortschritt über task_status().
"""
from __future__ import annotations

import base64
import os
import sys
import threading

import time

import backup
import core
import features
import keys
import plugins
import ratings
import tagger
import xmltools
import blobs
from compare import (PAIR_MODES, Rules, DEFAULT_TRIVIAL, Cancelled, diff, copy_tags, all_keys, MULTI_FIELDS,
                     INPUT_SEPARATORS, plan_multi_fix)
from id3tags import key_label, sort_key, TEXT_LABELS, STANDARD_KEYS, MV, MV_SHOW, Cover, Item
from undo import UndoStack
from version import VERSION  # einzige Versionsquelle
from session_player import PlayerMixin
from core import size_text as fmt_bytes, duration_text as fmt_duration  # noqa: F401 (auch für session_snapshots)
from session_snapshots import SnapshotMixin
from session_djset import DjSetMixin

# Layout der Web-Oberfläche (Splitter, eingeklappte Seitenleiste): Schlüssel → erlaubter Typ
UI_KEYS = {"side_w": (int, float), "side_collapsed": bool, "pairs_w": (int, float),
           "col_name": (int, float), "col_ratio": (int, float), "tg_edit_w": (int, float),
           "tg_more_k": (int, float), "tg_col_name": (int, float), "tg_cover_col": bool,
           "module": str,                                    # #88: zuletzt benutzte Seite
           "tg_feat_cols": list}                             # #11: Spalten mit Audio-Merkmalen im Tagger


class Session(SnapshotMixin, PlayerMixin, DjSetMixin):
    def __init__(self):
        self.lock = threading.RLock()
        self._bus, self._buslock = {}, threading.Lock()       # Nachrichten zwischen Fenstern (#69)
        self._load_cfg()
        self.pairs: list = []
        self.reg: dict = {}          # gemeinsames Dateiregister (Vergleich + Tagger): Pfad → MP3File
        self.tag_files: list = []    # Tagger
        self.tag_stems: dict = {}    # Index Original → [Spuren] (#31)
        self.tag_parent: dict = {}   # Index Spur (MP3) → Index Original
        self.tag_root = ""
        self.cur: int | None = None
        self.left_root = self.right_root = ""
        self.undo = UndoStack()
        self.task = {"running": False}
        self._cancel = None
        self._plugins = None   # wird beim ersten Zugriff gesucht
        self._origins = None
        self._jobs = None      # Hintergrund-Aufträge (jobs.py), beim ersten Zugriff
        self._pending = None   # Vorschläge eines Plugins, warten auf Bestätigung

    def _load_cfg(self):
        """Einstellungen (neu) einlesen – beim Start und nach Import/Zurücksetzen."""
        self.cfg = core.load_config()
        self._djstate = None                                   # DJ-Set neu aus cfg (#3)
        features.set_scale(self.cfg.get("feat_scale", 100))   # #11: Skala der Audio-Merkmale in den Dateien
        triv = list(self.cfg.get("trivial", DEFAULT_TRIVIAL))
        known = set(self.cfg.get("trivial_known", triv))
        triv += [p for p in DEFAULT_TRIVIAL if p not in known and p not in triv]
        self.rules = Rules(triv)
        self.opts = {
            "filter": self.cfg.get("filter", "all"),
            "show_trivial": self.cfg.get("show_trivial", True),
            "empty_set": self.cfg.get("empty_set", "off"),
            "show_covers": self.cfg.get("show_covers", True),
            "query": getattr(self, "opts", {}).get("query", ""),
            "theme": self.cfg.get("web_theme", self.cfg.get("theme", "dark")),
        }
        ui = self.cfg.get("web_ui")
        self.ui = {k: v for k, v in (ui.items() if isinstance(ui, dict) else []) if k in UI_KEYS}
        # #85/#86: Vorgaben beim Start (fehlende = wie zuletzt benutzt)
        cd = self.view_defaults()["compare"]
        for k in ("filter", "show_trivial", "empty_set", "show_covers"):
            if k in cd:
                self.opts[k] = cd[k]
        td = self.view_defaults()["tagger"]
        if "stems_flat" in td:
            self.cfg["tagger_stems_flat"] = td["stems_flat"]
        if "cover_col" in td:
            self.ui["tg_cover_col"] = td["cover_col"]
        if getattr(self, "_plugins", None) is not None:
            self._plugins = None
        self._origins = None

    # ================================================================== Einstellungen
    def settings(self) -> dict:
        c = self.cfg
        return {
            "version": VERSION,
            "hist_left": c.get("hist_left", []), "hist_right": c.get("hist_right", []),
            "mode": self.view_defaults()["compare"].get("mode", c.get("mode", "filename")), "modes": [[k, v] for k, v in PAIR_MODES.items()],
            "recursive": self.view_defaults()["compare"].get("recursive", c.get("recursive", False)),
            "options": dict(self.opts), "view_defaults": self.view_defaults(),
            "empty_sets": [[k, v] for k, v in core.EMPTY_SETS.items()],
            "filter_ops": core.FILTER_OPS, "filter_sides": core.FILTER_SIDES,
            "ui": dict(self.ui), "player": self.player_prefs(at_start=True), "origins": self.origin_catalog(),
            "defaults": self.default_dirs(),
        }

    # ------------------------------------------------------------------ Standardordner (#84)
    DEFAULT_DIRS = ("default_left", "default_right", "default_tagger")

    def default_dirs(self) -> dict:
        return {k[8:]: str(self.cfg.get(k) or "") for k in self.DEFAULT_DIRS}

    def set_default_dir(self, which, path) -> dict:
        """which: left | right | tagger; leerer Pfad = kein Standardordner."""
        key = "default_" + str(which)
        if key not in self.DEFAULT_DIRS:
            raise ValueError("left, right oder tagger erwartet")
        path = (path or "").strip()
        if path and not os.path.exists(path):
            return {"ok": False, "error": f"Ordner nicht gefunden: {path}"}
        self.cfg[key] = path
        core.save_config({key: path})
        return {"ok": True, "defaults": self.default_dirs()}

    # ------------------------------------------------------------------ Vorgaben beim Start (#85, #86)
    TG_SORT_COLS = ("name", "TIT2", "TPE1", "TALB", "TRCK", "TDRC", "TCON", "TBPM", "camelot")

    def _view_default_spec(self):
        return {
            "compare": {"recursive": (bool,), "mode": tuple(PAIR_MODES), "filter": ("all", "diff", "same"),
                        "show_trivial": (bool,), "empty_set": tuple(core.EMPTY_SETS), "show_covers": (bool,)},
            "tagger": {"recursive": (bool,), "sort_col": self.TG_SORT_COLS, "sort_dir": (1, -1), "cover_col": (bool,),
                       "stems_flat": (bool,), "src_filter": (str,), "autoload": (bool,),
                       "start": ("last", "default", "none")},                        # #127
        }

    def _view_default_ok(self, choices, v) -> bool:
        if choices == (bool,):
            return isinstance(v, bool)
        if choices == (str,):
            return isinstance(v, str) and len(v) <= 64
        return not isinstance(v, bool) and v in choices

    def view_defaults(self) -> dict:
        """Gespeicherte Vorgaben je Bereich; nur gesetzte Schlüssel (fehlend = wie zuletzt benutzt)."""
        out = {}
        for area, spec in self._view_default_spec().items():
            d = self.cfg.get(f"{'cmp' if area == 'compare' else 'tg'}_defaults")
            d = d if isinstance(d, dict) else {}
            out[area] = {k: v for k, v in d.items() if k in spec and self._view_default_ok(spec[k], v)}
        return out

    def set_view_default(self, area, key, value) -> dict:
        """Eine Vorgabe setzen; value None = keine Vorgabe (wie zuletzt benutzt)."""
        spec = self._view_default_spec().get(area)
        if spec is None or key not in spec:
            raise ValueError(f"Unbekannte Vorgabe: {area}/{key}")
        if value is not None and not self._view_default_ok(spec[key], value):
            raise ValueError(f"Ungültiger Wert für {key}")
        cfg_key = f"{'cmp' if area == 'compare' else 'tg'}_defaults"
        d = dict(self.view_defaults()[area])
        if value is None:
            d.pop(key, None)
        else:
            d[key] = value
        self.cfg[cfg_key] = d
        core.save_config({cfg_key: d})
        return self.view_defaults()

    def cmp_defaults_apply(self) -> dict:
        """#85: Vergleich jetzt auf die Vorgaben zurücksetzen (Filter, Unwichtige, Leere, Cover, Zuordnung, Unterordner)."""
        d = self.view_defaults()["compare"]
        with self.lock:
            for k in ("filter", "show_trivial", "empty_set", "show_covers"):
                if k in d:
                    self.opts[k] = d[k]
                    self.cfg[k] = d[k]
            save = {k: self.cfg[k] for k in ("filter", "show_trivial", "empty_set", "show_covers") if k in d}
            for k in ("mode", "recursive"):
                if k in d:
                    self.cfg[k] = d[k]
                    save[k] = d[k]
            if save:
                core.save_config(save)
            st = self.state("Vergleich auf die Vorgaben zurückgesetzt." if d else "Keine Vorgaben gespeichert (Einstellungen › Vergleich).")
            st["mode"] = self.cfg.get("mode", "filename")
            st["recursive"] = bool(self.cfg.get("recursive", False))
            return st

    # ------------------------------------------------------------------ Update-Kanal (#89)
    def update_channel(self) -> str:
        ch = self.cfg.get("update_channel")
        if ch in ("stable", "beta"):
            return ch
        return "beta" if "-" in VERSION else "stable"

    def set_update_channel(self, channel) -> str:
        if channel not in ("stable", "beta"):
            raise ValueError("stable oder beta erwartet")
        self.cfg["update_channel"] = channel
        core.save_config({"update_channel": channel})
        return channel

    def set_ui(self, name: str, value):
        """Layout merken (Breiten der Splitter, eingeklappte Seitenleiste)."""
        if name not in UI_KEYS or not isinstance(value, UI_KEYS[name]) or isinstance(value, bool) != (UI_KEYS[name] is bool):
            raise ValueError(f"Ungültige Layout-Einstellung: {name}")
        if name == "tg_feat_cols":
            value = [x for x in dict.fromkeys(value) if x in features.NAMES]
        self.ui[name] = value
        self.cfg["web_ui"] = dict(self.ui)
        core.save_config({"web_ui": dict(self.ui)})
        return True

    def set_option(self, name: str, value):
        if name not in self.opts:
            raise ValueError(f"Unbekannte Option: {name}")
        self.opts[name] = value
        key = {"theme": "web_theme"}.get(name, name)
        if name != "query":
            self.cfg[key] = value
            core.save_config({key: value})
        return self.state()

    # ================================================================== Herkunft der Tags (#22)
    @property
    def origins(self):
        import origins
        if self._origins is None:
            pf = []
            try:
                for pl in self.plugins.plugins.values():
                    for pat in (getattr(pl, "manifest", None) or {}).get("fields") or []:
                        if isinstance(pat, str) and pat.strip():
                            pf.append((pat.strip(), pl.name))
            except Exception:  # noqa: BLE001 – Herkunft ist nur Anzeige
                pf = []
            self._origins = origins.Origins(self.cfg.get("tag_origins"), pf)
        return self._origins

    _CUSTOM_FIDS = ("TXXX", "WXXX", "GEOB", "PRIV", "UFID")
    SRC_SHORT = {"mik": "MIK", "itunes": "iTunes", "wmp": "WMP", "platinum": "PN", "replaygain": "ReplayGain",
                 "musicbrainz": "MB"}

    @classmethod
    def _official(cls, key) -> bool:
        """Offizielles ID3-Feld (Titel, Künstler, BPM, Cover …) – nicht TXXX, GEOB, PRIV & Co. (#74)."""
        fid, _sep, desc = key.split("#")[0].partition(":")
        if fid in cls._CUSTOM_FIDS:
            return False
        return not (fid in ("COMM", "USLT") and desc)

    def _src(self, key, f):
        """Herkunft eines Felds (#22, #74): bekannte Anwendung; benutzerdefinierte Felder ohne bekannte Herkunft
        → „unknown“; offizielle Felder ohne bekannte Herkunft → None (dort steht nur die ID3-Version, _ver)."""
        sid = self.origins.of(key)
        if sid is None and not self._official(key):
            sid = "unknown"
        return sid

    def _ver(self, key, f):
        """ID3-Version (v2.3/v2.4) als Kennzeichen bei offiziellen Feldern (#74, abschaltbar)."""
        if f is None or not self._official(key) or not self.cfg.get("origin_ver_badge", True):
            return None
        return "id3v4" if f.version == 4 else "id3v3"

    def set_origin_ver_badge(self, on) -> bool:
        self.cfg["origin_ver_badge"] = bool(on)
        core.save_config({"origin_ver_badge": bool(on)})
        return bool(on)

    def set_origin_std_badge(self, on) -> bool:          # alter Name (bis 3.3.0-beta.2)
        return self.set_origin_ver_badge(on)

    def origin_catalog(self) -> dict:
        o = self.origins
        cat = o.catalog()
        cat["id3v3"] = {"name": "v2.3", "desc": "offizielles Feld im ID3v2.3-Tag der Datei", "kind": "id3"}
        cat["id3v4"] = {"name": "v2.4", "desc": "offizielles Feld im ID3v2.4-Tag der Datei", "kind": "id3"}
        cat["unknown"] = {"name": "unbekannt", "desc": "benutzerdefiniertes Feld – Herkunft nicht ermittelbar", "kind": "unknown"}
        labels = self.cfg.get("origin_labels") or {}
        for sid, v in cat.items():
            v["patterns"] = o.patterns(sid)
            name = v["name"]
            v["short_default"] = self.SRC_SHORT.get(sid) or ("TagStudio" if v["kind"] == "plugin"
                                                              else name if len(name) <= 12 else name[:11] + "…")
            own = labels.get(sid) or {}
            v["short"] = own.get("short") or v["short_default"]
            v["hue"] = own.get("hue")
            v["custom_label"] = bool(own)
        return cat

    def set_origin_label(self, sid, short=None, hue=None) -> dict:
        """#75: eigenes Kennzeichen (Text, Farbton 0–359) je Herkunft; sid=None + leer = alle zurücksetzen."""
        labels = dict(self.cfg.get("origin_labels") or {})
        if sid is None:
            labels = {}
        else:
            sid = str(sid)[:80]
            short = (str(short).strip()[:16] if short is not None else "")
            try:
                hue = None if hue in (None, "") else int(hue) % 360
            except (TypeError, ValueError):
                hue = None
            if not short and hue is None:
                labels.pop(sid, None)
            else:
                labels[sid] = {k: v for k, v in (("short", short), ("hue", hue)) if v not in ("", None)}
        self.cfg["origin_labels"] = labels
        core.save_config({"origin_labels": labels})
        return self.tag_origins()

    def tag_origins(self) -> dict:
        return {"custom": list(self.cfg.get("tag_origins") or []), "catalog": self.origin_catalog(),
                "ver_badge": bool(self.cfg.get("origin_ver_badge", True))}

    def set_tag_origins(self, rules) -> dict:
        import origins
        cleaned = origins.clean_custom(rules)
        self.cfg["tag_origins"] = cleaned
        core.save_config({"tag_origins": cleaned})
        self._origins = None
        return self.tag_origins()

    def tag_origin_remove(self, idx, source, apply=False):
        """Alle Felder einer Quelle aus den gewählten Dateien entfernen (Vorschau, dann mit Rückgängig)."""
        with self.lock:
            files = self._tsel(idx)
            plan = [(f, k) for f in files for k in sorted(f.items, key=sort_key)
                    if not k.startswith("APIC") and self._src(k, f) == source]
            if not apply:
                keys = sorted({k for _f, k in plan}, key=sort_key)
                return {"count": len(plan), "files": len({id(f) for f, _k in plan}),
                        "keys": [[k, key_label(k), sum(1 for _f, x in plan if x == k)] for k in keys]}
            name = self.origin_catalog().get(source, {}).get("name", source)
            self.undo.checkpoint(f"Felder von {name} entfernt", list({id(f): f for f, _k in plan}.values()))
            for f, k in plan:
                f.set(k, None)
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"{len(plan)} Feld(er) von {name} entfernt – noch nicht gespeichert."
            return d

    # ================================================================== Cache (#42)
    @staticmethod
    def _cache_dirs():
        import re
        import thumbs
        import waveform
        return {"covers": (thumbs.CACHE_DIR, re.compile(r"^[0-9a-f]{32}_\d+\.png$"), False),
                "wave": (waveform.DIR, re.compile(r"^[0-9a-f]{32}\.json$"), True)}

    def cache_info(self) -> dict:
        import listcache
        n, size = listcache.cache_size()
        out = {"lists": {"dir": listcache.DIR, "count": n, "bytes": size, "on": self._list_cache_on()}}
        for name, (d, rx, deep) in self._cache_dirs().items():
            n = size = 0
            for root, _dirs, files in (os.walk(d) if deep else [(d, [], os.listdir(d) if os.path.isdir(d) else [])]):
                for fn in files:
                    if rx.match(fn):
                        try:
                            size += os.path.getsize(os.path.join(root, fn))
                            n += 1
                        except OSError:
                            pass
            out[name] = {"dir": d, "count": n, "bytes": size}
        return out

    def cache_clear(self, name) -> dict:
        """Nur Dateien, die zum jeweiligen Cache gehören (Namensmuster), werden gelöscht."""
        if name == "lists":
            import listcache
            import shutil
            n, _size = listcache.cache_size()
            shutil.rmtree(listcache.DIR, ignore_errors=True)
            info = self.cache_info()
            info["removed"] = n
            return info
        if name not in self._cache_dirs():
            raise ValueError("Unbekannter Cache")
        d, rx, deep = self._cache_dirs()[name]
        gone = 0
        for root, _dirs, files in (os.walk(d) if deep else [(d, [], os.listdir(d) if os.path.isdir(d) else [])]):
            for fn in files:
                if rx.match(fn):
                    try:
                        os.remove(os.path.join(root, fn))
                        gone += 1
                    except OSError:
                        pass
        info = self.cache_info()
        info["removed"] = gone
        return info

    # ------------------------------------------------------------------ Cache (neu) erstellen (#80)
    def _loaded_files(self) -> list:
        """Alle geladenen echten Dateien (Tagger + Vergleich), ohne Snapshot-Seiten, ohne Doppelte."""
        seen, out = set(), []
        with self.lock:
            for f in list(self.tag_files) + [g for p in self.pairs for g in p]:
                if f is None or self._ro(f):
                    continue
                k = os.path.normcase(os.path.abspath(f.path))
                if k not in seen:
                    seen.add(k)
                    out.append(f)
        return out

    def start_cache_build(self, name, background=False):
        """Listen-Cache bzw. Cover-Vorschauen für alle geladenen Titel neu aufbauen – mit Fortschritt oder als
        Hintergrund-Auftrag (#80)."""
        if name not in ("lists", "covers"):
            raise ValueError("Unbekannter Cache")
        files = self._loaded_files()
        if not files:
            return {"ok": False, "error": "Erst einen Ordner im Tagger oder Vergleich einlesen – erstellt wird für die geladenen Titel."}
        paths = [f.path for f in files]
        roots = sorted({r for r in (self.tag_root, self.left_root, self.right_root) if r and os.path.isdir(r)})
        label = "Listen-Cache erstellen" if name == "lists" else "Cover-Vorschauen erstellen"
        if background:
            job = self.jobs.add("tagstudio:cache", name, f"{label} ({len(paths)} Titel)", paths, {"roots": roots})
            return {"ok": True, "job": job["id"]}
        return self._run("cache_build", label, lambda cancel, progress: self._cache_work(name, paths, roots, cancel, progress))

    def _cache_work(self, name, paths, roots, cancel, progress) -> dict:
        """Eigentliche Arbeit – unabhängig von geladenen Objekten, damit ein Auftrag auch nach einem Neustart läuft."""
        from id3tags import MP3File
        progress(("total", len(paths)))
        if name == "lists":
            import listcache
            done = 0
            for root in roots:
                base = os.path.normcase(os.path.abspath(root)) + os.sep
                mine = [p for p in paths if os.path.normcase(os.path.abspath(p)).startswith(base)]
                if not mine:
                    continue
                c = listcache.ListCache(root)
                c.entries = {}                               # neu: alles von der Platte
                for p in mine:
                    if cancel.is_set():
                        raise Cancelled()
                    try:
                        st = os.stat(p)
                        g = MP3File.__new__(MP3File)
                        g.path = p
                        g.load(keep_raw=True)
                        c.store(p, st, g)
                    except OSError:
                        pass
                    done += 1
                    if done % 10 == 0 or done == len(paths):
                        progress(("progress", done, len(paths), p))
                c.dirty = True
                c.save(prune=False)
            _n, size = listcache.cache_size()
            return {"message": f"Listen-Cache neu erstellt: {done} Titel in {len(roots)} Ordner(n) · {fmt_bytes(size)}."}
        import thumbs
        uniq, ok = {}, 0
        for i, p in enumerate(paths, 1):
            if cancel.is_set():
                raise Cancelled()
            f = self.reg.get(os.path.normcase(os.path.abspath(p)))
            try:
                f = f or MP3File(p)
            except OSError:
                continue
            c = self._front_cover(f)
            if c is not None:
                h = self._cover_hash(f)
                if h not in uniq:
                    uniq[h] = True
                    ok += bool(thumbs.make_png(c.data, self.THUMB))
            if i % 10 == 0 or i == len(paths):
                progress(("progress", i, len(paths), p))
        if uniq and not ok and not thumbs.backend():
            return {"message": "Keine Vorschaubilder erzeugt – auf diesem System fehlt ein Bildwerkzeug (Pillow, ImageMagick …).",
                    "tone": "warn"}
        bad = len(uniq) - ok
        return {"message": f"Cover-Vorschauen erstellt: {ok} von {len(uniq)} verschiedenen Cover(n)"
                           + (f" – {bad} liessen sich nicht umwandeln." if bad else "."), "tone": "warn" if bad else "ok"}

    THUMB = 96

    def wave_missing(self) -> list:
        """Titel ohne Wellenform im Cache → [{path, key}] (berechnet wird in der Oberfläche, #80)."""
        import waveform
        out, seen = [], set()
        for f in self._loaded_files():
            try:
                k = waveform.key_for(f)
            except (OSError, ValueError):
                continue
            if k not in seen and not os.path.exists(waveform._file(k)):     # gleiches Audio nur einmal
                seen.add(k)
                out.append({"path": f.path, "key": k, "name": os.path.basename(f.path)})
        return out

    # ================================================================== Einstellungsseite (#21)
    def settings_page(self) -> dict:
        import appsettings
        c = self.cfg
        return {"file": appsettings.overview(), "trivial": list(self.rules.trivial), "trivial_default": list(DEFAULT_TRIVIAL),
                "save_version": c.get("save_version", 0), "key_notation": c.get("key_notation", "camelot"),
                "notations": [[k, v] for k, v in keys.NOTATIONS.items()], "theme": self.opts["theme"],
                "backup_enabled": c.get("backup_enabled", True), "backup_dir": self._backup_folder(),
                "player": self.player_prefs(), "players": len(c.get("players") or []),
                "stems_flat": bool(c.get("tagger_stems_flat")),
                "feat_scale": features.SCALE, "feat_scales": [[k, v] for k, v in features.SCALES.items()],
                "update_channel": self.update_channel(), "version": VERSION,
                "view_defaults": self.view_defaults(), "modes": [[k, v] for k, v in PAIR_MODES.items()],
                "empty_sets": [[k, v] for k, v in core.EMPTY_SETS.items()],
                "tg_sort_cols": [["name", "Datei"], ["TIT2", "Titel"], ["TPE1", "Künstler"], ["TALB", "Album"], ["TRCK", "Spur"],
                                 ["TDRC", "Jahr"], ["TCON", "Genre"], ["TBPM", "BPM"], ["camelot", "Tonart"]],
                "groups": [[g, label] for g, label, _k in appsettings.GROUPS]}

    def set_trivial(self, patterns) -> list:
        """Liste der unwichtigen Felder (Muster wie „TXXX:MusicBrainz*“) setzen."""
        if not isinstance(patterns, list):
            raise ValueError("Liste erwartet")
        out = []
        for p in patterns:
            p = str(p).strip()
            if p and len(p) <= 200 and p not in out:
                out.append(p)
        with self.lock:
            self.rules = Rules(out[:500])
            self.cfg["trivial"], self.cfg["trivial_known"] = list(self.rules.trivial), list(DEFAULT_TRIVIAL)
            core.save_config({"trivial": self.cfg["trivial"], "trivial_known": self.cfg["trivial_known"]})
        return list(self.rules.trivial)

    def set_save_version(self, ver):
        """ID3-Version beim Speichern: 0 = beibehalten, 3 = v2.3, 4 = v2.4."""
        if ver not in (0, 3, 4):
            raise ValueError("0, 3 oder 4 erwartet")
        self.cfg["save_version"] = ver
        core.save_config({"save_version": ver})
        return ver

    def settings_export_text(self) -> str:
        import appsettings
        return appsettings.export_text(VERSION)

    def settings_import_preview(self, text) -> dict:
        import appsettings
        try:
            return {"ok": True, **appsettings.import_preview(str(text))}
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}

    def settings_import(self, text, groups) -> dict:
        import appsettings
        try:
            res = appsettings.import_apply(str(text), list(groups or []))
        except (OSError, ValueError) as ex:
            return {"ok": False, "error": str(ex)}
        with self.lock:
            self._load_cfg()
        return res

    def settings_reset(self, groups) -> dict:
        import appsettings
        if groups != "all" and not isinstance(groups, list):
            raise ValueError("Liste oder „all“ erwartet")
        try:
            res = appsettings.reset(groups)
        except OSError as ex:
            return {"ok": False, "error": str(ex)}
        with self.lock:
            self._load_cfg()
        return res

    # ================================================================== Hintergrund-Aufgaben
    def _run(self, kind, label, fn):
        if self.task.get("running"):
            return {"ok": False, "error": "Es läuft bereits ein Vorgang."}
        self._cancel = threading.Event()
        self.task = {"running": True, "kind": kind, "label": label, "i": 0, "total": 0, "text": label,
                     "done": False, "error": None, "result": None}

        def progress(m):
            t = self.task
            if m[0] == "count":
                t["text"] = f"{core.fmt_n(m[1])} MP3-Dateien gefunden …"
            elif m[0] == "total":
                t["total"] = m[1]
            elif m[0] == "progress":
                t["i"], t["total"] = m[1], m[2]
                t["text"] = os.path.basename(m[3])
                t["frac"] = max(0.0, min(1.0, float(m[4]))) if len(m) > 4 and m[4] is not None else 0.0
            elif m[0] == "pairing":
                t["text"] = "Ordne Dateien zu …"
            elif m[0] == "text":
                t["text"] = m[1]

        def worker():
            try:
                res = fn(self._cancel, progress)
                self.task.update(result=res)
            except (Cancelled, plugins.Cancelled):
                self.task.update(result={"cancelled": True})
            except Exception as ex:  # noqa: BLE001
                self.task.update(error=str(ex) or type(ex).__name__)
            finally:
                self.task.update(running=False, done=True)
        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True}

    def task_status(self) -> dict:
        return dict(self.task)

    def cancel_task(self):
        if self._cancel is not None:
            self._cancel.set()
        return {"ok": True}

    # ================================================================== Laden
    def modified(self) -> list:
        """Alle geänderten Dateien – aus Vergleich und Tagger."""
        return [f for f in self.reg.values() if f.is_modified()]

    def unsaved(self) -> int:
        return len(self.modified())

    def start_load(self, lp: str, rp: str, recursive: bool, mode: str, keep_current: bool = False):
        lp, rp = (lp or "").strip(), (rp or "").strip()
        err = core.check_paths(lp, rp)
        if err:
            return {"ok": False, "error": err}
        if mode not in PAIR_MODES:
            mode = "filename"
        keep = self.cur if keep_current else None

        def snap_loader(spec, cancel, progress):      # #56: Snapshot als Quelle (schreibgeschützt)
            import snapshots
            return snapshots.load_snapshot(self.snap_store, spec, cancel, progress)

        def root_of(p):
            import snapshots
            ids = snapshots.parse_spec(p)
            if not ids:
                return p
            root = self.snap_store.library(ids[0])["root"]
            return os.path.join(root, *ids[2].split("/")) if ids[2] else root      # ein Titel: Datei als Wurzel

        def job(cancel, progress):
            stats = {}
            pairs, errors = core.load_pairs(lp, rp, recursive, mode, cancel, progress, self.reg, snap_loader,
                                            self._list_cache_on(), stats)
            with self.lock:
                self.undo.clear()
                self.pairs = pairs
                self.left_root, self.right_root = root_of(lp), root_of(rp)
                self.left_spec, self.right_spec = lp, rp
                self.cur = keep if keep is not None and keep < len(pairs) else (0 if pairs else None)
            hist = lambda key, p: self.cfg.get(key, []) if p.startswith("snapshot:") else core.history(self.cfg, key, p)
            self.cfg.update(hist_left=hist("hist_left", lp), hist_right=hist("hist_right", rp), mode=mode,
                            recursive=recursive)                       # Snapshot-Angaben nicht in den Verlauf (#84)
            core.save_config({k: self.cfg[k] for k in ("hist_left", "hist_right", "mode", "recursive")})
            return {"pairs": len(pairs), "errors": errors, **self._verify_start(stats, "compare")}
        return self._run("load", "Dateien einlesen", job)

    def reload_pair(self, force=False) -> dict:
        """#82: nur die beiden Dateien des aktuellen Paars neu von der Platte lesen (nicht die ganze Liste).
        Ungespeicherte Änderungen: ohne force kommt {"ask": {...}} zurück."""
        import listcache
        with self.lock:
            files = [(f, root) for f, root in zip(self.files(), (self.left_root, self.right_root))
                     if f is not None and not self._ro(f)]
            if not files:
                return self.state("Kein Paar gewählt.", "warn")
            mod = [os.path.basename(f.path) for f, _r in files if f.is_modified()]
            if mod and not force:
                return {"ask": {"files": mod}}
            changed, errors = 0, []
            for f, root in files:
                before = f.disk_sig
                try:
                    st = os.stat(f.path)
                    f.load(keep_raw=True)
                    changed += f.disk_sig != before
                    if self._list_cache_on() and root and os.path.isdir(root):
                        c = listcache.ListCache(root)
                        c.store(f.path, st, f)
                        c.save(prune=False)
                    f.__dict__.pop("_raw", None)
                except OSError as ex:
                    errors.append(f"{os.path.basename(f.path)}: {ex}")
            self.undo.forget([f for f, _r in files])
            msg = (f"Paar neu eingelesen – {changed} Datei(en) hatten sich geändert." if changed
                   else "Paar neu eingelesen – unverändert.") if not errors else "Neu einlesen fehlgeschlagen: " + "; ".join(errors)
            return self.state(msg, "warn" if errors or changed else "ok")

    # ================================================================== Paarliste
    def pair_rows(self) -> dict:
        """Alle Paare mit Status (für die Liste) plus Zähler."""
        with self.lock:
            rows, counts = [], {"diff": 0, "triv": 0, "same": 0, "single": 0}
            for i, (l, r) in enumerate(self.pairs):
                st = core.pair_status(l, r, self.rules)
                counts[st["tag"]] += 1
                rows.append({"i": i, "left": core.rel_name(l, self.left_root), "right": core.rel_name(r, self.right_root),
                             "symbol": st["symbol"], "tag": st["tag"], "info": st["info"], "modified": st["modified"],
                             "bpm": self._pair_bpm(l, r)})
            return {"rows": rows, "counts": counts, "left_root": self.left_root, "right_root": self.right_root}

    def filter_pairs(self, query="", key=None, op="enthält", val="", side="links oder rechts") -> list[int]:
        """Indizes der Paare, die zum (erweiterten) Filter passen."""
        flt = core.make_pair_filter(query, key, op, val, side)
        with self.lock:
            return [i for i, p in enumerate(self.pairs) if flt is None or flt(p)]

    def field_choices(self) -> list:
        with self.lock:
            return [[k, v] for k, v in core.field_choices(self.pairs).items()]

    def select(self, i):
        with self.lock:
            self.cur = i if i is not None and 0 <= i < len(self.pairs) else None
            return self.state()

    # ================================================================== Ansicht
    def files(self):
        return self.pairs[self.cur] if self.cur is not None and self.cur < len(self.pairs) else (None, None)

    def _file(self, side):
        l, r = self.files()
        return l if side == "L" else r

    @staticmethod
    def _covers(f, other):
        out = []
        if f is None:
            return out
        for k in sorted(k for k in f.items if k.startswith("APIC")):
            it = f.get(k)
            if not it.cover or not it.cover.data:
                continue
            mime = it.cover.mime or "image/jpeg"
            data = it.cover.data if len(it.cover.data) <= 4_000_000 else b""
            out.append({"key": k, "label": key_label(k), "desc": it.cover.describe(),
                        "differs": other is not None and other.get(k) != it,
                        "src": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}" if data else ""})
        return out

    def _side_head(self, f, root, other):
        if f is None:
            return None
        return {"name": os.path.basename(f.path), "rel": core.rel_name(f, root), "path": f.path,
                "readonly": bool(getattr(f, "readonly", False)), "snapshot": getattr(f, "snap_label", ""),
                "info": f.info(), "version": f.version, "modified": f.is_modified(),
                "bpm": self._bpm(f), "bpm_differs": other is not None and self._bpm(other) != self._bpm(f),
                "covers": self._covers(f, other) if self.opts["show_covers"] else []}

    def view(self) -> dict:
        with self.lock:
            l, r = self.files()
            o = self.opts
            keys, states = core.visible_keys(l, r, self.rules, o["filter"], o["show_trivial"], o["empty_set"], o["query"])
            rows = []
            for k in keys:
                st = states[k]
                row = {"key": k, "label": key_label(k), "state": st, "src": self._src(k, l if l is not None else r),
                       "ver": self._ver(k, l if l is not None else r), "trivial": self.rules.is_trivial(k)}
                fids = []
                for side, f, other in (("L", l, r), ("R", r, l)):
                    it = f.get(k) if f else None
                    if it is not None:
                        for x in it.frame_ids(f.version):
                            if x not in fids:
                                fids.append(x)
                    text = core.disp(it) if it is not None else ""
                    spans = []
                    if it is not None and st in ("diff", "triv") and other is not None and other.get(k) is not None:
                        spans = core.diff_spans(text, core.disp(other.get(k)))
                    xml = xmltools.xml_of_item(it)
                    row[side] = {
                        "present": it is not None, "text": text, "spans": spans,
                        "xml": None if xml is None else ("edit" if xml[1] else "view"),
                        "links": [[a, b, u] for a, b, u in core.link_spans(text)],
                        "mod": bool(f is not None and f.field_modified(k)),
                        "editable": core.can_edit_text(f, k),
                        "multiline": bool(it is not None and ("\n" in it.text or k.startswith("USLT"))),
                        "edit": core.edit_text(it) if it is not None and it.kind != "picture" and xml is None else "",
                    } if f is not None else None
                row["fid"] = " · ".join(fids) or k.split(":")[0].split("#")[0]
                rows.append(row)
            return {"index": self.cur, "both": l is not None and r is not None,
                    "left": self._side_head(l, self.left_root, r), "right": self._side_head(r, self.right_root, l),
                    "rows": rows, "counts": core.state_counts(states)}

    def meta(self) -> dict:
        return {"unsaved": self.unsaved(), "can_undo": bool(self.undo.undo), "can_redo": bool(self.undo.redo),
                "undo_label": self.undo.undo[-1]["label"] if self.undo.undo else "",
                "redo_label": self.undo.redo[-1]["label"] if self.undo.redo else ""}

    def pair_row(self, i):
        if i is None or not (0 <= i < len(self.pairs)):
            return None
        l, r = self.pairs[i]
        st = core.pair_status(l, r, self.rules)
        return {"i": i, "left": core.rel_name(l, self.left_root), "right": core.rel_name(r, self.right_root),
                "symbol": st["symbol"], "tag": st["tag"], "info": st["info"], "modified": st["modified"],
                "bpm": self._pair_bpm(l, r)}

    @staticmethod
    def _bpm(f) -> str:
        return (f.text("TBPM") or "").strip() if f is not None else ""

    def _pair_bpm(self, l, r) -> list:
        """Tempo links/rechts für die Spalte in der Paarliste."""
        return [self._bpm(l), self._bpm(r)]

    def state(self, message=None, tone="info") -> dict:
        with self.lock:
            return {"view": self.view(), "pair": self.pair_row(self.cur), "meta": self.meta(),
                    "options": dict(self.opts), "message": message, "tone": tone}

    # ================================================================== XML
    def get_xml(self, side, key):
        """XML-Inhalt eines Feldes für den XML-Editor."""
        with self.lock:
            f = self._file(side)
            it = f.get(key) if f else None
            x = xmltools.xml_of_item(it)
            if x is None:
                return {"ok": False, "error": "Dieses Feld enthält kein XML."}
            return {"ok": True, "text": x[0], "editable": x[1], "label": key_label(key),
                    "file": os.path.basename(f.path), "side": side, "key": key, "blob": xmltools.blob_info(it)}

    @staticmethod
    def xml_tool(action, text):
        """check | format | compact"""
        if action == "check":
            return xmltools.check(text)
        return xmltools.format_xml(text, compact=(action == "compact"))

    # ================================================================== Ändern
    @staticmethod
    def _dir(direction):
        return "nach rechts" if direction == "lr" else "nach links"

    def _src_dst(self, direction):
        l, r = self.files()
        return (l, r) if direction == "lr" else (r, l)

    _RO = "Die Snapshot-Seite ist schreibgeschützt – übernehmen geht nur in Richtung der echten Dateien."

    @staticmethod
    def _ro(f) -> bool:
        return bool(getattr(f, "readonly", False))

    def _done(self, msg, tone="info"):
        self.undo.commit()
        return self.state(msg, tone)

    def copy_keys(self, keys, direction):
        with self.lock:
            src, dst = self._src_dst(direction)
            if not (src and dst):
                return self.state("Kopieren geht nur, wenn links und rechts eine Datei vorhanden ist.", "warn")
            if self._ro(dst):
                return self.state(self._RO, "warn")
            self.undo.checkpoint(f"{len(keys)} Feld(er) {self._dir(direction)}", [dst])
            n = 0
            for k in keys:
                if dst.get(k) != src.get(k):
                    dst.set(k, src.get(k))
                    n += 1
            return self._done(f"{n} Feld(er) {self._dir(direction)} kopiert – noch nicht gespeichert.")

    def copy_all(self, direction, delete_missing=None):
        """Alle Unterschiede übernehmen. Gibt es Felder nur im Ziel und ist delete_missing None,
        kommt {"ask": {...}} zurück – die Oberfläche fragt und ruft erneut auf."""
        with self.lock:
            src, dst = self._src_dst(direction)
            if not (src and dst):
                return self.state()
            if self._ro(dst):
                return self.state(self._RO, "warn")
            imp, triv = diff(src, dst, self.rules)
            keys = imp + (triv if self.opts["show_trivial"] else [])
            if not keys:
                return self.state("Keine Unterschiede zum Kopieren.", "ok")
            missing = [k for k in keys if src.get(k) is None]
            if missing and delete_missing is None:
                return {"ask": {"count": len(missing), "labels": [key_label(k) for k in missing[:12]],
                                "more": max(0, len(missing) - 12)}}
            self.undo.checkpoint(f"Alles {self._dir(direction)}", [dst])
            n = copy_tags(src, dst, keys, delete_missing=bool(delete_missing))
            return self._done(f"{n} Feld(er) {self._dir(direction)} übernommen – noch nicht gespeichert.")

    def copy_missing(self, direction):
        with self.lock:
            src, dst = self._src_dst(direction)
            if not (src and dst):
                return self.state()
            if self._ro(dst):
                return self.state(self._RO, "warn")
            keys = [k for k in all_keys(src, dst) if src.get(k) is not None and dst.get(k) is None]
            if not self.opts["show_trivial"]:
                keys = [k for k in keys if not self.rules.is_trivial(k)]
            if not keys:
                return self.state(f"Keine fehlenden Felder {'rechts' if direction == 'lr' else 'links'}.", "ok")
            self.undo.checkpoint(f"Fehlende {self._dir(direction)}", [dst])
            for k in keys:
                dst.set(k, src.get(k))
            return self._done(f"{len(keys)} fehlende(s) Feld(er) {self._dir(direction)} übernommen – noch nicht gespeichert.")

    def remove(self, side, keys):
        with self.lock:
            f = self._file(side)
            if self._ro(f):
                return self.state(self._RO, "warn")
            keys = [k for k in keys if f is not None and f.get(k) is not None]
            if not keys:
                return self.state()
            self.undo.checkpoint(f"{len(keys)} Feld(er) entfernt", [f])
            for k in keys:
                f.set(k, None)
            return self._done(f"{len(keys)} Feld(er) entfernt – noch nicht gespeichert.")

    def set_value(self, side, key, text):
        with self.lock:
            f = self._file(side)
            if f is None or not core.can_edit_text(f, key):
                return self.state("Dieses Feld kann nicht als Text bearbeitet werden.", "warn")
            it = f.get(key)
            if core.normalize_value(text) == (it.text if it else ""):
                return self.state()
            self.undo.checkpoint(f"„{key_label(key)}“ bearbeitet", [f])
            core.apply_value(f, key, text)
            return self._done(None)

    def revert_pair(self):
        with self.lock:
            files = [f for f in self.files() if f and not self._ro(f)]
            self.undo.checkpoint("Paar verworfen", files)
            for f in files:
                f.revert()
            return self._done("Änderungen an diesem Paar verworfen.")

    def discard_all(self):
        """Alle ungespeicherten Änderungen verwerfen (z. B. vor einem Update)."""
        with self.lock:
            for f in self.modified():
                f.revert()
            self.undo.clear()
            return self.state("Alle ungespeicherten Änderungen verworfen.")

    def do_undo(self):
        with self.lock:
            e = self.undo.do_undo()
            return self.state(f"Rückgängig: {e['label']}" if e else None)

    def do_redo(self):
        with self.lock:
            e = self.undo.do_redo()
            return self.state(f"Wiederholt: {e['label']}" if e else None)

    # ================================================================== Speichern
    def save_conflicts(self) -> dict:
        """Ungespeicherte Dateien, die inzwischen von einem anderen Programm geändert wurden (#55),
        mit den extern geänderten Feldern."""
        import snapshots
        from id3tags import MP3File
        out = []
        with self.lock:
            for f in self.modified():
                if not f.external_change():
                    continue
                try:
                    disk = MP3File(f.path)
                    rows = snapshots.diff_items(f._orig, disk.items)
                except OSError as ex:
                    rows = [{"key": "", "label": f"nicht lesbar: {ex}", "state": "changed", "old": "", "new": ""}]
                mine = set(f.modified_keys())
                for r in rows:
                    r["mine"] = r["key"] in mine
                out.append({"path": f.path, "name": os.path.basename(f.path), "fields": rows,
                            "clash": sorted(mine & {r["key"] for r in rows})})
        return {"conflicts": out}

    def save_merge_external(self, paths=None) -> dict:
        """Externe Änderungen übernehmen, eigene (ungespeicherte) Änderungen behalten: Datei neu einlesen und die
        selbst geänderten Felder wieder darüberlegen. Bei Feldern, die beide geändert haben, gewinnt TagStudio."""
        n = 0
        with self.lock:
            want = {os.path.normcase(os.path.abspath(p)) for p in (paths or [])}
            for f in self.modified():
                if want and os.path.normcase(os.path.abspath(f.path)) not in want:
                    continue
                if not f.external_change():
                    continue
                mine = {k: f.items.get(k) for k in f.modified_keys()}
                ver = f.version if f.version != f._orig_version else None
                f.load()
                for k, it in mine.items():
                    f.set(k, it)
                if ver:
                    f.set_version(ver)
                n += 1
        st = self.state(f"{n} Datei(en) neu eingelesen – externe Änderungen übernommen, eigene Änderungen behalten.")
        st["pairs_changed"] = True
        return st

    def start_save(self, force=False):
        files = self.modified()
        if not force and any(f.external_change() for f in files):
            return {"ok": False, "conflict": True,
                    "error": "Dateien wurden inzwischen von einem anderen Programm geändert."}
        if not files:
            return {"ok": False, "error": "Keine ungespeicherten Änderungen."}
        backup_on = self.cfg.get("backup_enabled", True)
        folder = self.cfg.get("backup_dir") or None
        ver = self.cfg.get("save_version", 0)
        if ver in (3, 4):                 # Einstellung „ID3-Version beim Speichern“
            for f in files:
                f.set_version(ver)

        def job(cancel, progress):
            with self.lock:
                return core.save_files(files, backup_on, folder, cancel, progress, force=bool(force))
        return self._run("save", f"{len(files)} Datei(en) speichern", job)

    # ================================================================== Feld hinzufügen
    @staticmethod
    def add_field_choices() -> list:
        """[[Anzeigename, Frame-ID, braucht Beschreibung]]"""
        out = [[v, k, False] for k, v in sorted(TEXT_LABELS.items(), key=lambda x: x[1])
               if k not in ("TYER", "TIME", "TRDA", "TSIZ")]
        return [["Benutzertext (TXXX)", "TXXX", True], ["Kommentar (COMM)", "COMM", True],
                ["Benutzer-URL (WXXX)", "WXXX", True], ["Liedtext (USLT)", "USLT", True]] + out

    def _add_to(self, files, fid, desc, value, replace):
        key = f"{fid}:{(desc or '').strip()}" if fid in ("TXXX", "COMM", "WXXX", "USLT") else fid
        if not core.normalize_value(value or "").strip():
            return None, {"ok": False, "error": "Bitte einen Wert eingeben."}
        exists = [f for f in files if f.get(key) is not None]
        if exists and not replace:
            return None, {"ask": {"label": key_label(key), "count": len(exists)}}
        self.undo.checkpoint(f"„{key_label(key)}“ hinzugefügt", files)
        for f in files:
            core.apply_value(f, key, value)
        return key, None

    def add_field(self, side, fid, desc, value, replace=False):
        with self.lock:
            f = self._file(side)
            if f is None:
                return {"ok": False, "error": "Auf dieser Seite ist keine Datei."}
            if self._ro(f):
                return {"ok": False, "error": self._RO}
            key, err = self._add_to([f], fid, desc, value, replace)
            if err:
                return err
            st = self._done(f"„{key_label(key)}“ hinzugefügt – noch nicht gespeichert.")
            st["added"] = key
            return st

    # ================================================================== Sammelkopie
    def bulk_keys(self, idx, direction) -> dict:
        with self.lock:
            idx = [i for i in idx if 0 <= i < len(self.pairs) and all(self.pairs[i])]
            keys = set()
            for i in idx:
                keys |= set(self.pairs[i][0 if direction == "lr" else 1].items)
            return {"pairs": len(idx), "keys": [{"key": k, "label": key_label(k), "trivial": self.rules.is_trivial(k),
                                                 "standard": k in STANDARD_KEYS} for k in sorted(keys, key=sort_key)]}

    def bulk_apply(self, idx, direction, keys, delete_missing=False):
        with self.lock:
            idx = [i for i in idx if 0 <= i < len(self.pairs) and all(self.pairs[i])
                   and not self._ro(self.pairs[i][1 if direction == "lr" else 0])]
            if not idx or not keys:
                return self.state(self._RO if self.pairs and any(self._ro(p[1 if direction == "lr" else 0]) for p in self.pairs)
                                  else "Nichts zu übernehmen.", "warn")
            self.undo.checkpoint(f"Sammelkopie {len(idx)} Paar(e)", [self.pairs[i][1 if direction == "lr" else 0] for i in idx])
            n = 0
            for i in idx:
                l, r = self.pairs[i]
                src, dst = (l, r) if direction == "lr" else (r, l)
                n += copy_tags(src, dst, keys, delete_missing=bool(delete_missing))
            st = self._done(f"{n} Feld(er) in {len(idx)} Paar(en) übernommen – noch nicht gespeichert.")
            st["pairs_changed"] = True
            return st

    def compare_origin_remove(self, source, side="both", scope="cur", idx=None, apply=False):
        """Felder einer Herkunft im Vergleich entfernen (#45): side L/R/both, scope cur/sel/all."""
        if side not in ("L", "R", "both") or scope not in ("cur", "sel", "all"):
            raise ValueError("Ungültige Seite oder Auswahl")
        with self.lock:
            if scope == "cur":
                pidx = [self.cur] if self.cur is not None else []
            elif scope == "sel":
                pidx = [i for i in (idx or []) if isinstance(i, int) and 0 <= i < len(self.pairs)]
            else:
                pidx = list(range(len(self.pairs)))
            files = []
            for i in pidx:
                l, r = self.pairs[i]
                for s_, f in (("L", l), ("R", r)):
                    if f is not None and not self._ro(f) and side in (s_, "both") and all(f is not g for g in files):
                        files.append(f)
            plan = [(f, k) for f in files for k in sorted(f.items, key=sort_key)
                    if not k.startswith("APIC") and self._src(k, f) == source]
            if not apply:
                keys = sorted({k for _f, k in plan}, key=sort_key)
                return {"count": len(plan), "files": len({id(f) for f, _k in plan}), "pairs": len(pidx),
                        "keys": [[k, key_label(k), sum(1 for _f, x in plan if x == k)] for k in keys]}
            if not plan:
                return self.state("Keine Felder dieser Herkunft.", "warn")
            name = self.origin_catalog().get(source, {}).get("name", source)
            self.undo.checkpoint(f"Felder von {name} entfernt", list({id(f): f for f, _k in plan}.values()))
            for f, k in plan:
                f.set(k, None)
            st = self._done(f"{len(plan)} Feld(er) von {name} entfernt – noch nicht gespeichert.")
            st["pairs_changed"] = True
            return st

    # ================================================================== Bilder (Vergleich)
    @staticmethod
    def _read_image(path):
        with open(path, "rb") as fh:
            data = fh.read()
        if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or data[:6] in (b"GIF87a", b"GIF89a")):
            raise ValueError("Kein JPEG-, PNG- oder GIF-Bild.")
        return data

    def cover_set_file(self, side, key, path):
        with self.lock:
            f = self._file(side)
            if f is None or not path:
                return self.state()
            if self._ro(f):
                return self.state(self._RO, "warn")
            try:
                data = self._read_image(path)
            except (OSError, ValueError) as ex:
                return self.state(f"Bild nicht geladen: {ex}", "warn")
            try:
                ptype = int(key.split(":")[1].split("#")[0])
            except (IndexError, ValueError):
                ptype, key = 3, "APIC:3"
            self.undo.checkpoint("Bild ersetzt" if f.get(key) else "Bild hinzugefügt", [f])
            f.set(key, Item.new_cover(Cover(data, ptype=ptype)))
            return self._done("Bild übernommen – noch nicht gespeichert.")

    def cover_remove(self, side, key):
        return self.remove(side, [key])

    def cover_export(self, side, key, dest):
        with self.lock:
            f = self._file(side)
            it = f.get(key) if f else None
            if not it or not it.cover or not dest:
                return {"ok": False, "error": "Kein Bild."}
            with open(dest, "wb") as fh:
                fh.write(it.cover.data)
            return {"ok": True, "path": dest}

    def cover_default_name(self, side, key):
        f = self._file(side)
        it = f.get(key) if f else None
        if not it or not it.cover:
            return ""
        return os.path.splitext(os.path.basename(f.path))[0] + it.cover.ext

    # ================================================================== Tag-Fixer
    def fixer_settings(self) -> dict:
        fc = self.cfg.get("fixer", {})
        return {"fields": [[k, key_label(k)] for k in MULTI_FIELDS],
                "separators": [[label, sep, active] for label, sep, active in INPUT_SEPARATORS],
                "saved": {"fields": fc.get("fields", MULTI_FIELDS), "all_text": fc.get("all_text", False),
                          "seps": fc.get("seps", [s for _, s, a in INPUT_SEPARATORS if a]),
                          "mode": fc.get("mode", "sep"), "sep": fc.get("sep", ", "),
                          "upgrade": fc.get("upgrade", True), "dedupe": fc.get("dedupe", True)},
                "counts": {"pair": sum(1 for f in self.files() if f), "all": sum(1 for p in self.pairs for f in p if f),
                           "tag_all": len(self.tag_files)}}

    def _fixer_files(self, o):
        sc = o.get("scope", "pair")
        if sc in ("pair", "L", "R"):
            l, r = self.files()
            return [f for f, s in ((l, "L"), (r, "R")) if f and (sc == "pair" or sc == s)]
        if sc in ("sel", "all"):
            idx = (o.get("pairs") or []) if sc == "sel" else range(len(self.pairs))
            return [f for i in idx if 0 <= i < len(self.pairs) for f in self.pairs[i] if f]
        if sc in ("tag_sel", "tag_all"):
            idx = (o.get("tag_idx") or []) if sc == "tag_sel" else range(len(self.tag_files))
            return [self.tag_files[i] for i in idx if 0 <= i < len(self.tag_files)]
        return []

    def _fixer_plan(self, o):
        out = MV if o.get("mode") == "v24" else (o.get("sep") or ", ")
        return plan_multi_fix([f for f in self._fixer_files(o) if not self._ro(f)], o.get("fields", []), o.get("seps", []), out,
                              bool(o.get("dedupe", True)), bool(o.get("all_text")), bool(o.get("upgrade", True)))

    def fixer_preview(self, o) -> dict:
        with self.lock:
            plan = self._fixer_plan(o)
            rows = [{"file": os.path.basename(f.path), "key": k, "label": key_label(k),
                     "old": old.replace(MV, MV_SHOW), "new": new.replace(MV, MV_SHOW)} for f, k, old, new in plan[:3000]]
            return {"rows": rows, "count": len(plan), "files": len({id(f) for f, *_ in plan}),
                    "scope_files": len(self._fixer_files(o))}

    def fixer_apply(self, o):
        with self.lock:
            plan = self._fixer_plan(o)
            if not plan:
                return self.state("Tag-Fixer: nichts zu ändern.", "ok")
            to_v24 = o.get("mode") == "v24" and o.get("upgrade", True)
            self.undo.checkpoint(f"Tag-Fixer ({len(plan)} Felder)", [f for f, *_ in plan])
            for f, k, _old, new in plan:
                if to_v24 and f.version != 4:
                    f.set_version(4)
                f.set_text(k, new)
            keep = {k: o.get(k) for k in ("fields", "all_text", "seps", "mode", "sep", "upgrade", "dedupe")}
            self.cfg["fixer"] = keep
            core.save_config({"fixer": keep})
            st = self._done(f"Tag-Fixer: {len(plan)} Feld(er) angepasst – noch nicht gespeichert.")
            st["pairs_changed"] = True
            return st

    # ================================================================== Sicherungen
    def _backup_folder(self):
        return self.cfg.get("backup_dir") or backup.default_dir()

    def backups(self) -> dict:
        folder = self._backup_folder()
        items = backup.list_backups(folder)
        return {"enabled": self.cfg.get("backup_enabled", True), "folder": folder,
                "total": sum(b["bytes"] for b in items),
                "list": [{"path": b["path"], "name": b["name"], "label": b["label"], "count": b["count"],
                          "bytes": b["bytes"], "broken": bool(b.get("broken")),
                          "created": time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(b["created"]))} for b in items]}

    def set_backup(self, enabled=None, folder=None):
        if enabled is not None:
            self.cfg["backup_enabled"] = bool(enabled)
            core.save_config({"backup_enabled": bool(enabled)})
        if folder:
            self.cfg["backup_dir"] = os.path.normpath(folder)
            core.save_config({"backup_dir": self.cfg["backup_dir"]})
        return self.backups()

    def _backup_entry(self, path):
        folder = os.path.normcase(os.path.abspath(self._backup_folder()))
        p = os.path.normcase(os.path.abspath(path))
        if os.path.dirname(p) != folder or not p.endswith(".zip"):
            raise ValueError("Diese Sicherung liegt nicht im Sicherungsordner.")
        for b in backup.list_backups(self._backup_folder()):
            if os.path.normcase(os.path.abspath(b["path"])) == p:
                return b
        raise ValueError("Sicherung nicht gefunden.")

    def start_backup_check(self, path):
        try:
            b = self._backup_entry(path)
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}

        def job(cancel, progress):
            progress(("total", len(b["files"])))
            out = []
            for i, e in enumerate(b["files"], 1):
                if cancel.is_set():
                    raise Cancelled()
                code, txt = backup.check_entry(e)
                changes, fields = None, []
                if code in ("ok", "audio"):
                    try:
                        rows = backup.diff_entry(b["path"], e)["rows"]
                        changes, fields = len(rows), [r["label"] for r in rows]
                    except Exception:  # noqa: BLE001 – Übersicht darf nicht an einer Datei scheitern
                        changes = None
                elif code == "same":
                    changes = 0
                out.append({"changes": changes, "fields": fields[:8], "more": max(0, len(fields) - 8),
                            "id": e["id"], "name": e.get("name") or os.path.basename(e["path"]),
                            "dir": os.path.dirname(e["path"]), "code": code, "text": txt,
                            "loaded_modified": bool(self.reg.get(os.path.normcase(os.path.abspath(e["path"])))
                                                    and self.reg[os.path.normcase(os.path.abspath(e["path"]))].is_modified())})
                progress(("progress", i, len(b["files"]), e["path"]))
            return {"files": out, "name": b["name"]}
        return self._run("check", "Sicherung prüfen", job)

    def backup_diff(self, path, entry_id):
        """Feld-Vergleich Sicherung ↔ heutige Datei für den Änderungs-Viewer."""
        b = self._backup_entry(path)
        e = next((x for x in b["files"] if x.get("id") == entry_id), None)
        if e is None:
            raise ValueError("Datei nicht in dieser Sicherung.")
        d = backup.diff_entry(b["path"], e)
        for r in d["rows"]:
            r["spans_old"] = core.diff_spans(r["old"], r["new"]) if r["state"] == "changed" else []
            r["spans_new"] = core.diff_spans(r["new"], r["old"]) if r["state"] == "changed" else []
        reg = self.reg.get(os.path.normcase(os.path.abspath(e["path"])))
        d.update(name=e.get("name") or os.path.basename(e["path"]), path=e["path"], id=entry_id,
                 created=time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(b["created"])),
                 label=b.get("label", ""), unsaved=bool(reg and reg.is_modified()))
        return d

    def start_restore(self, path, ids=None, force_audio=False):
        try:
            b = self._backup_entry(path)
        except ValueError as ex:
            return {"ok": False, "error": str(ex)}

        def job(cancel, progress):
            res = backup.restore(b["path"], ids, self._backup_folder(), bool(force_audio),
                                 on_progress=lambda i, n, p: progress(("progress", i, n, p)), cancel=cancel)
            ok = {os.path.normcase(os.path.abspath(p)) for p, code, _ in res if code == "restored"}
            with self.lock:
                for k in ok:
                    if k in self.reg:
                        self.reg[k].load()
                if ok:
                    self.undo.clear()
            return {"restored": len(ok), "skipped": [{"name": os.path.basename(p), "text": t}
                                                     for p, code, t in res if code != "restored"]}
        return self._run("restore", "Wiederherstellen", job)

    def delete_backup(self, path):
        try:
            b = self._backup_entry(path)
            os.remove(b["path"])
        except (ValueError, OSError) as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True, "backups": self.backups()}

    # ================================================================== Tagger
    def start_tag_load(self, path, recursive=False):
        path = (path or "").strip()
        if not path or not os.path.exists(path):
            return {"ok": False, "error": "Bitte einen vorhandenen Ordner oder eine MP3-Datei wählen."}

        def job(cancel, progress):
            stats = {}
            t0 = time.time()
            files, errors = core.load_files(path, bool(recursive), cancel, progress, self.reg, self._list_cache_on(), stats)
            try:                                       # #137: Dauer fürs App-Protokoll (Wartezeit beim Start eingrenzen)
                import applog
                applog.info(f"Tagger eingelesen: {len(files)} Datei(en), {len(stats.get('cached') or [])} aus dem Cache, "
                            f"{time.time() - t0:.1f} s – {path}")
            except Exception:  # noqa: BLE001
                pass
            with self.lock:
                self.tag_files = files
                self.tag_root = path if os.path.isdir(path) else os.path.dirname(path)
                with_stems = self._attach_stems()
                n_orig = len(self.tag_files) - len(self.tag_parent)
            self.cfg["hist_tagger"] = core.history(self.cfg, "hist_tagger", path)
            core.save_config({"hist_tagger": self.cfg["hist_tagger"], "tagger_recursive": bool(recursive)})
            return {"files": n_orig, "stems": len(with_stems), "errors": errors, **self._verify_start(stats, "tagger")}
        return self._run("tagload", "Dateien einlesen", job)

    # ------------------------------------------------------------------ Listen-Cache und Prüfung (#70)
    def _list_cache_on(self) -> bool:
        return bool(getattr(self, "cfg", {}).get("list_cache", True))

    def set_list_cache(self, on) -> bool:
        self.cfg["list_cache"] = bool(on)
        core.save_config({"list_cache": bool(on)})
        return bool(on)

    def _verify_start(self, stats, kind) -> dict:
        """Aus dem Cache geladene Dateien im Hintergrund über den Hash ihrer Tag-Bytes prüfen."""
        import listcache
        files = list(stats.get("cached") or [])
        caches = stats.get("caches") or []
        self._verify_gen = getattr(self, "_verify_gen", 0) + 1
        gen = self._verify_gen
        self.verify = {"running": bool(files), "kind": kind, "i": 0, "total": len(files), "changed": [],
                       "removed": [], "seq": gen, "cached": len(files)}
        if not files:
            return {"cached": 0}

        def by_root(path):
            k = os.path.normcase(os.path.abspath(path))
            return next((c for c in caches if k.startswith(os.path.normcase(c.base) + os.sep) or k == os.path.normcase(c.root)), None)

        def worker():
            v = self.verify
            touched = set()
            for f in files:
                if getattr(self, "_verify_gen", 0) != gen:
                    return                                  # neu eingelesen – alte Prüfung verwerfen
                try:
                    sig, _size, _mt = listcache.tag_sig(f.path)
                    if sig != f.disk_sig:
                        with self.lock:
                            if not f.is_modified():         # eigene ungespeicherte Änderungen nie überschreiben
                                st = os.stat(f.path)
                                f.load(keep_raw=True)
                                c = by_root(f.path)
                                if c is not None:
                                    c.store(f.path, st, f)
                                    touched.add(id(c))
                        v["changed"].append(f.path)
                except OSError:
                    v["removed"].append(f.path)
                v["i"] += 1
            for c in caches:
                if id(c) in touched:
                    c.save(prune=False)
            v["running"] = False

        threading.Thread(target=worker, daemon=True).start()
        return {"cached": len(files)}

    def verify_status(self) -> dict:
        v = dict(getattr(self, "verify", None) or {"running": False, "total": 0, "i": 0, "changed": [], "removed": [], "seq": 0})
        v["changed"] = [os.path.basename(p) for p in v.get("changed", [])][:50]
        v["n_changed"] = len(getattr(self, "verify", {}).get("changed", [])) if getattr(self, "verify", None) else 0
        v["removed"] = [os.path.basename(p) for p in v.get("removed", [])][:50]
        return v

    # ------------------------------------------------------------------ Fenster (#125)
    WIN_DEFAULT = (1440, 920)
    WIN_MIN = (1000, 640)

    def window_start(self, screens=None) -> dict:
        """Startgrösse des Hauptfensters aus der gemerkten Geometrie (cfg „window“).
        screens = [(x, y, breite, höhe), …]: liegt das Fenster nicht sichtbar auf einem Bildschirm, wird nur die
        Position verworfen (Fenster mittig); zu grosse Fenster werden auf den grössten Bildschirm verkleinert."""
        g = self.cfg.get("window") if isinstance(self.cfg.get("window"), dict) else {}
        num = lambda v: int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        w, h = num(g.get("w")) or self.WIN_DEFAULT[0], num(g.get("h")) or self.WIN_DEFAULT[1]
        w, h = max(self.WIN_MIN[0], w), max(self.WIN_MIN[1], h)
        x, y = num(g.get("x")), num(g.get("y"))
        scr = [tuple(int(v) for v in sc) for sc in (screens or []) if len(sc) == 4]
        if scr:
            mw, mh = max(sc[2] for sc in scr), max(sc[3] for sc in scr)
            w, h = min(w, max(self.WIN_MIN[0], mw)), min(h, max(self.WIN_MIN[1], mh))
            if x is not None and y is not None:
                # sichtbar = Titelleiste (obere 40 px, mind. 100 px breit) liegt auf einem Bildschirm
                ok = any(sx - w + 100 <= x <= sx + sw - 100 and sy <= y <= sy + sh - 40 for sx, sy, sw, sh in scr)
                if not ok:
                    x = y = None
        out = {"width": w, "height": h, "maximized": bool(g.get("max"))}
        if x is not None and y is not None:
            out.update(x=x, y=y)
        return out

    def set_window_geometry(self, g) -> dict:
        """Geometrie beim Schliessen merken: {"w", "h", "x", "y", "max"}."""
        if not isinstance(g, dict):
            raise ValueError("Geometrie erwartet")
        num = lambda v: int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
        out = {"w": num(g.get("w")), "h": num(g.get("h")), "x": num(g.get("x")), "y": num(g.get("y")),
               "max": bool(g.get("max"))}
        out = {k: v for k, v in out.items() if v is not None}
        if out.get("w", 0) < 200 or out.get("h", 0) < 200:          # unbrauchbar (z. B. minimiert)
            out.pop("w", None), out.pop("h", None)
            old = self.cfg.get("window") if isinstance(self.cfg.get("window"), dict) else {}
            out = {**{k: old[k] for k in ("w", "h") if k in old}, **out}
        self.cfg["window"] = out
        core.save_config({"window": out})
        return out

    def tagger_start(self) -> str:
        """#127: Was beim Start in den Tagger kommt – „last“ (zuletzt geladen samt Zustand), „default“
        (Standardordner) oder „none“. Ältere Einstellung „autoload“ wird übernommen."""
        td = self.view_defaults()["tagger"]
        if "start" in td:
            return td["start"]
        if "autoload" in td:
            return "default" if td["autoload"] else "none"
        return "last"

    def tag_state(self) -> dict:
        st = self.cfg.get("tagger_state")
        return st if isinstance(st, dict) else {}

    def tag_state_save(self, state) -> bool:
        """#127: Zustand des Taggers merken (Ordner, Markierung, Sortierung, Filter, Bildlauf, aufgeklappte Stems).
        Pfade relativ zum Ordner; nur geprüfte Werte."""
        if not isinstance(state, dict):
            raise ValueError("Zustand erwartet")
        rels = lambda v: [x for x in v if isinstance(x, str) and len(x) < 1024][:5000] if isinstance(v, list) else []
        sort = state.get("sort") if isinstance(state.get("sort"), dict) else {}
        col = sort.get("col") if isinstance(sort.get("col"), str) and len(sort.get("col")) <= 40 else "name"
        out = {"root": str(state.get("root") or "")[:2048], "recursive": bool(state.get("recursive")),
               "sel": rels(state.get("sel")), "anchor": str(state.get("anchor") or "")[:1024],
               "sort": {"col": col, "dir": -1 if sort.get("dir") == -1 else 1},
               "query": str(state.get("query") or "")[:200], "open": rels(state.get("open")),
               "scroll": max(0, int(state.get("scroll") or 0))}
        if out == self.cfg.get("tagger_state"):
            return False
        self.cfg["tagger_state"] = out
        core.save_config({"tagger_state": out})
        return True

    def tagger_settings(self):
        td = self.view_defaults()["tagger"]
        return {"hist": self.cfg.get("hist_tagger", []), "recursive": td.get("recursive", self.cfg.get("tagger_recursive", False)),
                "defaults": td, "start": self.tagger_start(),
                "state": {**self.tag_state(), "exists": bool(self.tag_state().get("root")) and os.path.exists(self.tag_state()["root"])},
                "default": str(self.cfg.get("default_tagger") or ""),
                "fields": [[k, label, ph] for k, label, ph in tagger.FIELDS],
                "features": [[n, label, desc] for n, label, desc in features.FEATURES],
                "features_open": self.cfg.get("features_open", True),
                "keys": {"wheel": keys.wheel(), "notations": [[k, v] for k, v in keys.NOTATIONS.items()],
                         "notation": self.cfg.get("key_notation", "camelot")},
                "patterns": self.cfg.get("tagger_patterns", {"from": "%track% - %artist% - %title%",
                                                             "rename": "%track% - %artist% - %title%"})}

    # ------------------------------------------------------------------ Stems als Spuren (#31)
    def _stem_roots(self):
        o = ((self.cfg.get("plugin_options") or {}).get("stems") or {}).get("separate") or {}
        return [o["folder"]] if isinstance(o.get("folder"), str) and o.get("folder") else []

    def _attach_stems(self) -> list:
        """Spuren zu den geladenen Titeln suchen; MP3-Spuren werden mitgeladen (bearbeitbar).
        → Indizes der Originale, die (neue) Spuren haben."""
        import stemsview
        self.tag_stems, self.tag_parent = {}, {}
        if self.cfg.get("tagger_stems_flat"):
            return []
        roots = self._stem_roots()
        lister = stemsview.make_lister()
        where = {os.path.normcase(os.path.abspath(f.path)): i for i, f in enumerate(self.tag_files)}
        changed = []
        for i in range(len(self.tag_files)):
            f = self.tag_files[i]
            if stemsview.is_stem(f.path):
                continue
            found = stemsview.find(f.path, roots, lister)
            if not found:
                continue
            for st in found:
                st["i"] = None
                if st["ext"] == "MP3":
                    k = os.path.normcase(os.path.abspath(st["path"]))
                    j = where.get(k)
                    if j is None:
                        try:
                            g = self.reg.get(k) or core._open(st["path"], self.reg)
                        except Exception:  # noqa: BLE001 – defekte Spur nur nicht bearbeitbar
                            continue
                        self.tag_files.append(g)
                        j = where[k] = len(self.tag_files) - 1
                    st["i"] = j
                    self.tag_parent[j] = i
            self.tag_stems[i] = found
            changed.append(i)
        return changed

    def tag_attach_stems(self) -> dict:
        """Nach „Stems erzeugen“: neue Spuren ohne neues Einlesen anhängen."""
        with self.lock:
            before = {i: len(v) for i, v in self.tag_stems.items()}
            changed = self._attach_stems()
            new = [i for i in changed if len(self.tag_stems.get(i, [])) != before.get(i, 0)]
            return {"rows": [self._tag_row(i, f) for i, f in enumerate(self.tag_files)], "new": new}

    def set_feat_scale(self, scale) -> dict:
        """#11: Skala der Audio-Merkmale in den Dateien (100 oder 10); Anzeige bleibt 0–100."""
        v = features.set_scale(int(scale))
        self.cfg["feat_scale"] = v
        core.save_config({"feat_scale": v})
        return {"scale": v}

    def set_stems_flat(self, flat) -> dict:
        self.cfg["tagger_stems_flat"] = bool(flat)
        core.save_config({"tagger_stems_flat": bool(flat)})
        with self.lock:
            self._attach_stems()
        return {"flat": bool(flat)}

    def tag_stem_tags(self, idx, apply=False):
        """Tags der Originale auf ihre MP3-Spuren übertragen (Titel mit „(Spur)“) – Vorschau bzw. mit Rückgängig."""
        from compare import copy_tags
        with self.lock:
            parents = []
            for i in idx or []:
                p = self.tag_parent.get(i, i)
                if p in self.tag_stems and p not in parents:
                    parents.append(p)
            pairs = [(self.tag_files[p], self.tag_files[st["i"]], st["name"]) for p in parents
                     for st in self.tag_stems[p] if st["i"] is not None]
            if not apply:
                return {"originals": len(parents), "stems": len(pairs)}
            self.undo.checkpoint("Tags vom Original auf Stems übertragen", [d for _s, d, _n in pairs])
            n = 0
            for src, dst, name in pairs:
                keys = [k for k in src.items if not k.startswith(("GEOB", "PRIV"))]   # DJ-Analysen gehören zum Original
                n += copy_tags(src, dst, keys)
                title = (src.text("TIT2") or os.path.splitext(os.path.basename(src.path))[0]) + f" ({name})"
                if dst.text("TIT2") != title:
                    dst.set_text("TIT2", title)
                    n += 1
            self.undo.commit()
            d = self.tag_detail(idx)
            d["rows"] = [self._tag_row(i, f) for i, f in enumerate(self.tag_files)]
            d["message"] = f"Tags auf {len(pairs)} Spur(en) übertragen ({n} Feld(er)) – noch nicht gespeichert."
            return d

    def _tag_row(self, i, f):
        row = self._tag_row_base(i, f)
        if i in self.tag_parent:
            p = self.tag_parent[i]
            row["parent"] = p
            row["stem"] = next((s["name"] for s in self.tag_stems.get(p, []) if s["i"] == i), "")
        if i in self.tag_stems:
            row["stems"] = [{k: s[k] for k in ("name", "ext", "size", "i", "path")} for s in self.tag_stems[i]]
        return row

    def _tag_row_base(self, i, f):
        return {"i": i, "name": os.path.basename(f.path), "rel": core.rel_name(f, self.tag_root),
                "modified": f.is_modified(), "cover": f.get("APIC:3") is not None, "ch": self._cover_hash(f),
                "version": f.version,
                **{key: tagger.text_of(f, key) for key, _l, _p in tagger.FIELDS},
                "camelot": keys.parse_key(tagger.text_of(f, "TKEY")), "feat": features.values(f),
                "rating": ratings.get_rating(f), "like": ratings.get_like(f)}

    @staticmethod
    def _front_cover(f):
        it = f.get("APIC:3") or next((f.get(k) for k in f.items if k.startswith("APIC")), None)
        return it.cover if it is not None and it.cover and it.cover.data else None

    def _cover_hash(self, f) -> str:
        """#73: kurzer Hash des Covers (am Cover-Objekt gemerkt) – gleiche Cover eines Albums nur einmal laden."""
        import hashlib
        c = self._front_cover(f)
        if c is None:
            return ""
        h = getattr(c, "_h", None)
        if h is None or getattr(c, "_hlen", -1) != len(c.data):
            h = hashlib.md5(c.data).hexdigest()[:16]
            c._h, c._hlen = h, len(c.data)
        return h

    def tag_cover_thumb(self, h) -> dict:
        """Cover zu einem Hash aus tag_rows (für die Cover-Spalte, #73)."""
        with self.lock:
            for f in self.tag_files:
                if self._cover_hash(f) == h:
                    import thumbs
                    c = self._front_cover(f)
                    try:                                    # kleines Vorschaubild aus dem Cache (#80), sonst das Cover
                        with open(thumbs.cache_path(c.data, self.THUMB), "rb") as fh:
                            return {"ok": True, "src": "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii"),
                                    "desc": c.describe()}
                    except OSError:
                        pass
                    return {"ok": True, "src": f"data:{c.mime or 'image/jpeg'};base64,{base64.b64encode(c.data).decode('ascii')}",
                            "desc": c.describe()}
        return {"ok": False}

    def tag_rows(self) -> dict:
        with self.lock:
            return {"root": self.tag_root, "rows": [self._tag_row(i, f) for i, f in enumerate(self.tag_files)],
                    "stems_flat": bool(self.cfg.get("tagger_stems_flat"))}

    def _tsel(self, idx):
        return [self.tag_files[i] for i in idx if isinstance(i, int) and 0 <= i < len(self.tag_files)]

    def tag_detail(self, idx) -> dict:
        with self.lock:
            files = self._tsel(idx)
            out = {"count": len(files), "meta": self.meta(), "rows": [self._tag_row(i, self.tag_files[i])
                                                                   for i in idx if 0 <= i < len(self.tag_files)]}
            if not files:
                return out
            out["common"] = tagger.common_values(files)
            kv = out["common"].get("TKEY", {})
            kv["camelot"] = keys.parse_key(kv.get("value")) if not kv.get("mixed") else None
            cs = tagger.cover_summary(files)
            if cs.get("data") is not None:
                cs["src"] = f"data:{cs['mime']};base64,{base64.b64encode(cs.pop('data')).decode('ascii')}" \
                    if len(cs["data"]) <= 4_000_000 else ""
            out["cover"] = cs
            out["features"] = features.common(files)
            rs, ls = {ratings.get_rating(f) for f in files}, {ratings.get_like(f) for f in files}
            out["rating"] = {"value": next(iter(rs)) if len(rs) == 1 else None, "mixed": len(rs) > 1,
                             "like": next(iter(ls)) if len(ls) == 1 else None}
            durs = [float(getattr(f, "duration", 0) or 0) for f in files]
            out["length"] = {"total": round(sum(durs), 1), "count": len(files),
                             "same": len({round(d) for d in durs}) == 1}
            vers = {f.version for f in files}
            out["version"] = vers.pop() if len(vers) == 1 else None
            if len(files) == 1:
                f = files[0]
                out["file"] = {"name": os.path.basename(f.path), "path": f.path, "info": f.info()}
                std = {k for k, _l, _p in tagger.FIELDS}
                feat = {f"TXXX:{n}".upper() for n in features.NAMES}
                fields = []
                for k in sorted(f.items, key=sort_key):
                    if k in std or k.upper() in feat:
                        continue
                    it = f.get(k)
                    xml = xmltools.xml_of_item(it)
                    fields.append({"key": k, "label": key_label(k), "text": core.disp(it), "src": self._src(k, f), "ver": self._ver(k, f),
                                   "editable": core.can_edit_text(f, k) and xml is None,
                                   "multiline": "\n" in (it.text or "") or k.startswith(("COMM", "USLT")),
                                   "blob": blobs.is_blob(it),
                                   "xml": None if xml is None else ("edit" if xml[1] else "view"),
                                   "mod": f.field_modified(k), "edit": core.edit_text(it) if it.kind != "picture" and xml is None else ""})
                out["fields"] = fields
            return out

    def tag_set(self, idx, key, value):
        with self.lock:
            files = self._tsel(idx)
            if not files:
                return self.tag_detail(idx)
            self.undo.checkpoint(f"„{key_label(key)}“ in {len(files)} Datei(en)", files)
            n = tagger.set_field(files, key, value)
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"„{key_label(key)}“ in {n} Datei(en) geändert – noch nicht gespeichert." if n else None
            return d

    def tag_set_rating(self, idx, stars=None, like=None):
        """#96/#97: Bewertung (0–5) und/oder Like (#95) für die gewählten Dateien – mit Rückgängig."""
        with self.lock:
            files = [f for f in self._tsel(idx) if not self._ro(f)]
            if not files:
                return self.tag_detail(idx)
            n = self._mark(files, stars, like)
            d = self.tag_detail(idx)
            d["message"] = self._mark_msg(n, stars, like)
            return d

    def _mark(self, files, stars, like) -> int:
        what = "Bewertung" if stars is not None else "Like"
        self.undo.checkpoint(f"{what} in {len(files)} Datei(en)", files)
        n = 0
        for f in files:
            ch = ratings.set_rating(f, stars) if stars is not None else False
            if like is not None:
                ch = ratings.set_like(f, bool(like)) or ch
            n += bool(ch)
        self.undo.commit()
        return n

    @staticmethod
    def _mark_msg(n, stars, like):
        if not n:
            return None
        if stars is not None:
            what = f"Bewertung {'★' * int(stars)}{'☆' * (5 - int(stars))}" if stars else "Bewertung entfernt"
        else:
            what = "♥ Like gesetzt" if like else "Like entfernt"
        return f"{what} – {n} Datei(en), noch nicht gespeichert."

    def player_mark(self, kind, ref, stars=None, like=None) -> dict:
        """#95/#96: Bewertung/Like für den Titel im Player (Tagger-Zeile oder Vergleichsseite)."""
        with self.lock:
            if kind == "tag" and isinstance(ref, int) and 0 <= ref < len(self.tag_files):
                f = self.tag_files[ref]
            elif kind == "side" and ref in ("L", "R"):
                f = self._file(ref)
            else:
                return {"ok": False, "error": "Dieser Titel kann nicht bewertet werden (keine MP3 geladen)."}
            if f is None or self._ro(f):
                return {"ok": False, "error": "Diese Datei kann nicht geändert werden."}
            if like == "toggle":
                like = not ratings.get_like(f)
            n = self._mark([f], stars, like)
            out = {"ok": True, "rating": ratings.get_rating(f), "like": ratings.get_like(f),
                   "changed": bool(n), "message": self._mark_msg(n, stars, like), "meta": self.meta()}
            if kind == "tag":
                out["row"] = self._tag_row(ref, f)
            return out

    def tag_remove(self, idx, keys):
        with self.lock:
            files = self._tsel(idx)
            self.undo.checkpoint(f"{len(keys)} Feld(er) entfernt", files)
            for f in files:
                for k in keys:
                    f.set(k, None)
            self.undo.commit()
            return self.tag_detail(idx)

    def tag_add_field(self, idx, fid, desc, value, replace=False):
        with self.lock:
            files = self._tsel(idx)
            if not files:
                return {"ok": False, "error": "Keine Datei gewählt."}
            key, err = self._add_to(files, fid, desc, value, replace)
            if err:
                return err
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"„{key_label(key)}“ hinzugefügt – noch nicht gespeichert."
            return d

    def tag_cover(self, idx, path=None, remove=False):
        with self.lock:
            files = self._tsel(idx)
            data = None
            if not remove:
                try:
                    data = self._read_image(path)
                except (OSError, ValueError, TypeError) as ex:
                    d = self.tag_detail(idx)
                    d["message"] = f"Bild nicht geladen: {ex}"
                    return d
            self.undo.checkpoint("Cover entfernt" if remove else "Cover gesetzt", files)
            n = tagger.set_cover(files, data)
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"Cover in {n} Datei(en) {'entfernt' if remove else 'gesetzt'} – noch nicht gespeichert."
            return d

    def tag_version(self, idx, ver):
        with self.lock:
            files = self._tsel(idx)
            self.undo.checkpoint(f"ID3v2.{ver}", files)
            for f in files:
                f.set_version(int(ver))
            self.undo.commit()
            return self.tag_detail(idx)

    def _save_pattern(self, which, pattern):
        pats = dict(self.cfg.get("tagger_patterns", {}))
        pats[which] = pattern
        self.cfg["tagger_patterns"] = pats
        core.save_config({"tagger_patterns": pats})

    def tag_from_filename(self, idx, pattern, apply=False):
        with self.lock:
            files = self._tsel(idx)
            plan = tagger.plan_from_filename(files, pattern)
            rows = [{"name": os.path.basename(p["file"].path), "match": p["match"],
                     "changes": [[key_label(k), o, n] for k, o, n in p["changes"]]} for p in plan]
            if not apply:
                return {"rows": rows, "matched": sum(1 for p in plan if p["match"]),
                        "changes": sum(len(p["changes"]) for p in plan)}
            self._save_pattern("from", pattern)
            todo = [p for p in plan if p["changes"]]
            self.undo.checkpoint("Tags aus Dateinamen", [p["file"] for p in todo])
            for p in todo:
                for k, _o, n in p["changes"]:
                    core.apply_value(p["file"], k, n)
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"Tags aus {len(todo)} Dateinamen übernommen – noch nicht gespeichert."
            return d

    def tag_rename(self, idx, pattern, apply=False):
        with self.lock:
            files = self._tsel(idx)
            plan = tagger.plan_rename(files, pattern)
            rows = [{"old": p["old"], "new": p["new"], "problem": p["problem"]} for p in plan]
            if not apply:
                return {"rows": rows, "ok": sum(1 for p in plan if not p["problem"] and p["new"] != p["old"]),
                        "problems": sum(1 for p in plan if p["problem"])}
            self._save_pattern("rename", pattern)
            old_keys = {id(p["file"]): os.path.normcase(os.path.abspath(p["file"].path)) for p in plan}
            res = tagger.do_rename(plan)
            for p in plan:  # Register auf neue Pfade umstellen
                f = p["file"]
                old = old_keys[id(f)]
                new = os.path.normcase(os.path.abspath(f.path))
                if old != new and self.reg.get(old) is f:
                    del self.reg[old]
                    self.reg[new] = f
            d = self.tag_detail(idx)
            ok = [r for r in res if r["ok"]]
            bad = [r for r in res if not r["ok"]]
            d["message"] = f"{len(ok)} Datei(en) umbenannt." + (f" {len(bad)} Fehler." if bad else "")
            d["errors"] = [f"{r['old']}: {r['error']}" for r in bad]
            d["renamed"] = True
            return d

    def tag_number(self, idx, with_total=True, apply=False):
        with self.lock:
            files = self._tsel(idx)
            plan = tagger.plan_numbering(files, bool(with_total))
            if not apply:
                return {"rows": [{"name": os.path.basename(f.path), "old": o, "new": n} for f, o, n in plan]}
            self.undo.checkpoint("Spurnummern vergeben", [f for f, *_ in plan])
            for f, _o, n in plan:
                f.set_text("TRCK", n)
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"Spurnummern in {len(plan)} Datei(en) gesetzt – noch nicht gespeichert."
            return d

    def tag_xml(self, i, key):
        """XML-Inhalt eines Feldes einer Tagger-Datei (für den XML-Editor)."""
        with self.lock:
            if not (0 <= i < len(self.tag_files)):
                return {"ok": False, "error": "Keine Datei."}
            f = self.tag_files[i]
            it = f.get(key)
            x = xmltools.xml_of_item(it)
            if x is None:
                return {"ok": False, "error": "Dieses Feld enthält kein XML."}
            return {"ok": True, "text": x[0], "editable": x[1], "label": key_label(key),
                    "file": os.path.basename(f.path), "key": key, "blob": xmltools.blob_info(it)}

    def tag_blob(self, i, key):
        """Binärfeld (GEOB/PRIV) einer Tagger-Datei für den Binärfeld-Editor."""
        with self.lock:
            if not (0 <= i < len(self.tag_files)):
                return {"ok": False, "error": "Keine Datei."}
            f = self.tag_files[i]
            it = f.get(key)
            if not blobs.is_blob(it):
                return {"ok": False, "error": "Kein Binärfeld."}
            d = blobs.view(it)
            d.update(ok=True, key=key, label=key_label(key), file=os.path.basename(f.path))
            return d

    def tag_blob_set(self, i, key, text=None, mime=None, filename=None):
        """Binärfeld ändern (Inhalt als Text und/oder GEOB-Kopf). Mit Rückgängig, noch nicht gespeichert."""
        with self.lock:
            if not (0 <= i < len(self.tag_files)):
                return self.tag_detail([i])
            f = self.tag_files[i]
            it = f.get(key)
            if not blobs.is_blob(it):
                raise ValueError("Kein Binärfeld.")
            new = blobs.update(it, text, mime, filename)
            if new is not it:
                self.undo.checkpoint(f"„{key_label(key)}“ bearbeitet", [f])
                f.set(key, new)
                self.undo.commit()
            d = self.tag_detail([i])
            d["message"] = None if new is it else f"„{key_label(key)}“ geändert – noch nicht gespeichert."
            return d

    @staticmethod
    def blob_pretty(text, inner):
        try:
            return {"ok": True, "text": blobs.pretty(text, inner)}
        except ValueError as ex:
            return {"ok": False, "error": f"Kein gültiges JSON: {ex}"}

    # ================================================================== Tagger: weitere Werkzeuge
    def _plan_rows(self, plan, limit=2000):
        return [{"name": os.path.basename(f.path), "label": key_label(k), "old": o.replace(MV, MV_SHOW),
                 "new": n.replace(MV, MV_SHOW)} for f, k, o, n in plan[:limit]]

    def _apply_plan(self, idx, plan, label, msg):
        self.undo.checkpoint(label, list({id(f): f for f, *_ in plan}.values()))
        for f, k, _o, n in plan:
            f.set_text(k, n)
        self.undo.commit()
        d = self.tag_detail(idx)
        d["message"] = msg
        return d

    def tag_case_modes(self):
        return [[k, v] for k, v in tagger.CASE_MODES.items()]

    def tag_case(self, idx, keys, mode, keep_upper=True, small_words=False, apply=False):
        with self.lock:
            files = self._tsel(idx)
            plan = tagger.plan_case(files, keys or None, mode, bool(keep_upper), bool(small_words))
            if not apply:
                return {"rows": self._plan_rows(plan), "count": len(plan), "files": len({id(f) for f, *_ in plan})}
            return self._apply_plan(idx, plan, "Schreibweise geändert",
                                    f"Schreibweise in {len(plan)} Feld(ern) geändert – noch nicht gespeichert.")

    def tag_replace(self, idx, keys, find, repl, case=False, regex=False, word=False, apply=False):
        with self.lock:
            files = self._tsel(idx)
            try:
                plan = tagger.plan_replace(files, keys or None, find, repl, bool(case), bool(regex), bool(word))
            except ValueError as ex:
                return {"error": str(ex), "rows": [], "count": 0, "files": 0}
            if not apply:
                return {"rows": self._plan_rows(plan), "count": len(plan), "files": len({id(f) for f, *_ in plan})}
            return self._apply_plan(idx, plan, "Suchen & Ersetzen",
                                    f"{len(plan)} Feld(er) ersetzt – noch nicht gespeichert.")

    def tag_folder_cover(self, idx, only_missing=True, apply=False):
        with self.lock:
            files = self._tsel(idx)
            plan = tagger.plan_folder_cover(files, bool(only_missing))
            if not apply:
                return {"rows": [{"name": os.path.basename(p["file"].path),
                                  "image": os.path.basename(p["image"]) if p["image"] else "",
                                  "action": p["action"], "reason": p["reason"]} for p in plan],
                        "count": sum(1 for p in plan if p["action"] == "set")}
            todo = [p for p in plan if p["action"] == "set"]
            self.undo.checkpoint("Cover aus Ordner", [p["file"] for p in todo])
            cache, errors = {}, []
            for p in todo:
                try:
                    data = cache.get(p["image"]) or self._read_image(p["image"])
                    cache[p["image"]] = data
                    tagger.set_cover([p["file"]], data)
                except (OSError, ValueError) as ex:
                    errors.append(f"{os.path.basename(p['image'])}: {ex}")
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"Cover in {len(todo) - len(errors)} Datei(en) aus dem Ordner übernommen – noch nicht gespeichert."
            d["errors"] = errors
            return d

    # ------------------------------------------------------------------ Plugins
    @property
    def plugins(self) -> plugins.Manager:
        if self._plugins is None:
            self._plugins = plugins.Manager(self.cfg)
        return self._plugins

    def plugins_list(self, rescan=False):
        if rescan:
            self._origins = None
        lst = self.plugins.scan() if rescan else self.plugins.list()
        return {"plugins": lst, "user_dir": plugins.user_dir(), "log_dir": plugins.log_dir(),
                "frozen": bool(getattr(sys, "frozen", False))}

    def plugin_enable(self, pid, on):
        core.save_config(self.plugins.set_enabled(pid, on))
        return self.plugins_list()

    def plugin_actions(self, where="tagger"):
        return self.plugins.actions(where)

    def plugin_form(self, pid, aid):
        return self.plugins.form(pid, aid)

    def start_plugin_action(self, pid, aid, idx, values):
        try:
            p, a = self.plugins.action(pid, aid)
        except (KeyError, ValueError) as ex:
            return {"ok": False, "error": str(ex)}
        files = self._tsel(idx or [])
        if a.get("needs_selection", True) and not files:
            return {"ok": False, "error": "Bitte zuerst im Tagger Dateien markieren."}
        opts = self.plugins.clean_options(a, values)
        core.save_config(self.plugins.remember(pid, aid, opts))
        if self.plugins.is_background(pid, aid) and files:
            job = self.jobs.add(pid, aid, f"{p.name}: {a.get('run_label') or a['label']}", [f.path for f in files], opts)
            waiting = sum(1 for j in self.jobs.status()["jobs"] if j["status"] == "waiting")
            return {"ok": True, "background": True, "job": job["id"], "waiting": waiting}

        def job(cancel, progress):
            try:
                res = self.plugins.run(pid, aid, files, opts, self, cancel, progress)
            except Exception as ex:
                import traceback
                path = plugins.write_log(f"{pid}.log", traceback.format_exc())
                msg = str(ex) or type(ex).__name__
                raise RuntimeError(f"{msg}\n\nDetails im Protokoll: {path}") from ex
            if res.get("log"):
                res["logfile"] = plugins.write_log(f"{pid}.log", "\n".join(res["log"]))
            props = res.pop("proposals", [])
            if props:
                import uuid
                token = uuid.uuid4().hex
                self._pending = {"token": token, "plugin": pid, "items": props}
                res["proposals_token"] = token
                res["proposals"] = [{"id": n, "name": os.path.basename(p["file"].path), "group": p["group"] or os.path.basename(p["file"].path),
                                     "gkey": f'{p["file"].path}|{p["group"] or ""}',
                                     "folder": os.path.basename(os.path.dirname(p["file"].path)),
                                     "label": p["label"], "old": p["old"].replace(MV, MV_SHOW), "new": p["new"].replace(MV, MV_SHOW),
                                     "note": p["note"], "checked": p["checked"], "kind": p["kind"], "hint": p.get("hint", ""),
                                     "same": bool(p.get("same")), "link": p.get("link", ""), "link_label": p.get("link_label", "")}
                                    for n, p in enumerate(props)]
            res["unsaved"] = self.unsaved()
            return res
        return self._run("plugin", a["label"], job)

    # ================================================================== Hintergrund-Aufträge (#29)
    @property
    def jobs(self):
        import jobs
        if self._jobs is None:
            self._jobs = jobs.JobManager(self._job_runner)
        return self._jobs

    def _job_runner(self, job, cancel, progress):
        """Führt einen Auftrag aus – mit eigenen, frisch von der Platte gelesenen Dateien (die Oberfläche
        bearbeitet derweil ihre eigenen Objekte weiter; ungespeicherte Änderungen fliessen nicht ein)."""
        if job["plugin"] == "tagstudio:cache":            # eingebauter Auftrag: Cache erstellen (#80)
            res = self._cache_work(job["action"], job["paths"], job["opts"].get("roots", []), cancel, progress)
            return {"message": res["message"], "outputs": [], "log": []}
        if job["plugin"] == "tagstudio:snapshot":         # eingebauter Auftrag: Snapshot erstellen
            return self._snap_job(job, cancel, progress)
        from id3tags import MP3File
        files = []
        for p in job["paths"]:
            if os.path.isfile(p):
                try:
                    files.append(MP3File(p))
                except Exception as ex:  # noqa: BLE001
                    progress(("text", f"{os.path.basename(p)}: {ex}"))
        if not files:
            raise RuntimeError("Keine der Dateien ist mehr vorhanden.")
        try:
            res = self.plugins.run(job["plugin"], job["action"], files, job["opts"], None, cancel, progress, background=True)
        except Exception as ex:
            import traceback
            path = plugins.write_log(f"{job['plugin']}.log", traceback.format_exc())
            raise RuntimeError(f"{str(ex) or type(ex).__name__}\n\nDetails im Protokoll: {path}") from ex
        if res.get("proposals"):
            res["log"] = list(res.get("log") or []) + ["Hinweis: Vorschläge sind nur im Vordergrund möglich und wurden verworfen."]
        if res.get("log"):
            res["logfile"] = plugins.write_log(f"{job['plugin']}.log", "\n".join(res["log"]))
        return res

    def jobs_status(self) -> dict:
        return self.jobs.status()

    def job_cancel(self, jid) -> dict:
        self.jobs.cancel(str(jid))
        return self.jobs.status()

    def jobs_cancel_all(self) -> dict:
        self.jobs.cancel_all()
        return self.jobs.status()

    def jobs_clear(self) -> dict:
        self.jobs.clear_finished()
        return self.jobs.status()

    def jobs_resume(self, accept) -> dict:
        n = self.jobs.resume(bool(accept))
        st = self.jobs.status()
        st["resumed"] = n
        return st

    def plugin_apply(self, token, ids):
        """Ausgewählte Vorschläge eines Plugin-Laufs übernehmen (mit Rückgängig, noch nicht gespeichert)."""
        pend = self._pending
        if not pend or pend["token"] != token:
            return {"ok": False, "error": "Die Vorschläge sind nicht mehr aktuell – bitte das Plugin erneut ausführen."}
        chosen = [pend["items"][i] for i in ids if isinstance(i, int) and 0 <= i < len(pend["items"])
                  and not pend["items"][i].get("same")]
        self._pending = None
        if not chosen:
            return {"ok": True, "count": 0, "message": "Nichts übernommen."}
        with self.lock:
            files = list({id(p["file"]): p["file"] for p in chosen}.values())
            name = self.plugins.get(pend["plugin"]).name if pend["plugin"] in self.plugins.plugins else pend["plugin"]
            self.undo.checkpoint(f"{name}: {len(chosen)} Änderung(en)", files)
            n = 0
            try:
                for p in chosen:
                    if p["kind"] == "cover":
                        if p["data"]:
                            tagger.set_cover([p["file"]], p["data"])
                            n += 1
                    elif core.apply_value(p["file"], p["key"], p["new"]):
                        n += 1
            finally:   # auch bei Fehler abschliessen, sonst landen Teiländerungen im nächsten Undo-Schritt
                self.undo.commit()
        return {"ok": True, "count": n, "files": len(files), "unsaved": self.unsaved(),
                "message": f"{n} Änderung(en) in {len(files)} Datei(en) übernommen – noch nicht gespeichert."}

    def start_plugin_install(self, pid, variant=None):
        try:
            p = self.plugins.get(pid)
        except KeyError as ex:
            return {"ok": False, "error": str(ex)}
        vs = [v for v in p.manifest.get("install", []) if v.get("packages")]
        v = next((x for x in vs if x.get("id") == variant), vs[0] if vs else None)
        if v is None:
            return {"ok": False, "error": "Für dieses Plugin ist keine Installation hinterlegt."}

        def job(cancel, progress):
            if p.env_spec:
                res = plugins.env_install(p, v, cancel, progress)
            else:
                progress(("text", "pip install " + " ".join(v["packages"])))
                res = plugins.pip_install(v["packages"], cancel, progress)
                if not res.get("ok"):
                    res["logfile"] = plugins.write_log(f"{pid}-installation.log", "\n".join(res.get("log", [])))
            self.plugins.scan()
            res["state"] = self.plugins.get(pid).state()
            return res
        return self._run("install", f"{p.name}: Pakete installieren", job)

    # ------------------------------------------------------------------ Audio-Merkmale
    def tag_feature_set(self, idx, name, value):
        if name not in features.KEYS:
            raise ValueError(f"Unbekanntes Merkmal: {name}")
        try:
            features.normalize(value)
        except ValueError as ex:
            d = self.tag_detail(idx)
            d["error"] = str(ex)
            return d
        with self.lock:
            files = self._tsel(idx)
            if not files:
                return self.tag_detail(idx)
            label = dict((n, l) for n, l, _d in features.FEATURES)[name]
            self.undo.checkpoint(f"„{label}“ in {len(files)} Datei(en)", files)
            n = sum(1 for f in files if features.set_value(f, name, value))
            self.undo.commit()
            d = self.tag_detail(idx)
            d["message"] = f"„{label}“ in {n} Datei(en) geändert – noch nicht gespeichert." if n else None
            return d

    def tag_features_open(self, on):
        self.cfg["features_open"] = bool(on)
        core.save_config({"features_open": bool(on)})
        return bool(on)

    # ------------------------------------------------------------------ Tonart / Camelot
    def tag_key_notation(self, notation):
        if notation not in keys.NOTATIONS:
            raise ValueError(f"Unbekannte Schreibweise: {notation}")
        self.cfg["key_notation"] = notation
        core.save_config({"key_notation": notation})
        return notation

    def tag_key_set(self, idx, code):
        """Tonart per Camelot-Code setzen (in der gewählten Schreibweise); leer = entfernen."""
        if code and not keys.parse_key(code):
            raise ValueError(f"Unbekannte Tonart: {code}")
        val = keys.format_key(keys.parse_key(code), self.cfg.get("key_notation", "camelot")) if code else ""
        return self.tag_set(idx, "TKEY", val)

    def tag_key_convert(self, idx, notation, apply=False):
        with self.lock:
            files = self._tsel(idx)
            plan, unknown = keys.plan_notation(files, notation, tagger.text_of)
            if not apply:
                return {"rows": self._plan_rows(plan), "count": len(plan), "files": len(plan),
                        "unknown": [{"name": os.path.basename(f.path), "value": v} for f, v in unknown[:200]],
                        "unknown_count": len(unknown)}
            return self._apply_plan(idx, plan, "Tonart umschreiben",
                                    f"Tonart in {len(plan)} Datei(en) umgeschrieben – noch nicht gespeichert.")

    def tag_export_name(self, fmt):
        base = os.path.basename(os.path.normpath(self.tag_root)) or "TagStudio"
        return f"{base}.{'xlsx' if fmt == 'xlsx' else 'csv'}"

    def tag_export_file(self, idx, fmt, dest):
        with self.lock:
            files = self._tsel(idx) if idx else list(self.tag_files)
            head, rows = tagger.export_table(files, self.tag_root)
            (tagger.write_xlsx if fmt == "xlsx" else tagger.write_csv)(dest, head, rows)
            return {"ok": True, "path": dest, "count": len(rows)}
