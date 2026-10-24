"""MarKusSXCH TagStudio – Plugin-System.

Ein Plugin ist ein Ordner mit
    plugin.json   Beschreibung (id, name, version, api, description, requires, install, external)
    plugin.py     Python-Code: ACTIONS (Liste) oder actions(ctx) sowie run(action, ctx, files, options)

Gesucht wird im eingebauten Ordner `plugins/` neben dem Programm und im Benutzerordner
`~/TagStudio/Plugins`. Fehlende Python-Pakete werden erkannt (ohne Import) und lassen sich per pip
nachinstallieren. Plugins laufen als Hintergrundauftrag mit Fortschritt und Abbruch.

Plugins sind normaler Python-Code mit vollen Rechten – nur aus vertrauenswürdigen Quellen verwenden.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import os
import paths
import re
import shutil
import subprocess
import sys
import threading
import traceback

API_VERSION = 1
HERE = os.path.dirname(os.path.abspath(__file__))
BUILTIN_DIR = os.path.join(HERE, "plugins")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
# Kategorie je Plugin (plugin.json "category"), als Kennzeichen auf der Plugin-Karte
CATEGORIES = {"online": "Online-API", "local_api": "Lokale API", "import": "Übernahme aus Tags",
              "audio": "Audio-Verarbeitung", "other": "Sonstiges"}
OPTION_TYPES = {"select", "check", "text", "number", "folder", "folders", "info", "password", "textarea"}
SECRET_TYPES = {"password"}   # werden nie gespeichert


class Cancelled(Exception):
    """Abbruch durch den Benutzer."""


MANAGER = None          # #204: zuletzt angelegter Manager – damit Plugins andere Dienst-Plugins nutzen können


def user_dir() -> str:
    """Eigene Plugins (Programmcode) – gemeinsam für alle Profile."""
    return os.path.join(paths.base_dir(), "Plugins")


def data_root() -> str:
    """Plugin-Daten des Profils (Anmeldungen, Ergebnisse …)."""
    return paths.sub("Plugin-Daten")


def shared_root() -> str:
    """Gemeinsame, grosse Plugin-Daten (Umgebung, Modelle, FFmpeg) – für alle Profile gleich."""
    return paths.shared_plugin_data()


def log_dir() -> str:
    d = paths.sub("Logs")
    os.makedirs(d, exist_ok=True)
    return d


def write_log(name: str, text: str, append=True) -> str:
    """Protokoll nach ~/TagStudio/Logs/<name> schreiben. Liefert den Pfad (Fehler beim Schreiben werden ignoriert)."""
    import datetime
    path = os.path.join(log_dir(), name)
    try:
        with open(path, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(f"===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} =====\n{text.rstrip()}\n\n")
    except OSError:
        pass
    return path


def _env_python(env_dir: str) -> str:
    return os.path.join(env_dir, "Scripts", "python.exe") if os.name == "nt" else os.path.join(env_dir, "bin", "python")


# Meldungen, wenn das Basis-Python einer Umgebung fehlt (z. B. uv-Python verschoben/aufgeräumt) – #135
_BROKEN_ENV = ("failed to spawn python child process", "no python at", "did not find executable at",
               "unable to create process using")
BROKEN_ENV_MSG = ("Die Umgebung des Plugins ist beschädigt: das Python, auf das sie verweist, gibt es nicht mehr "
                  "(z. B. nach einem Update von uv oder Python). Bitte auf der Plugin-Seite „Neu installieren …“ "
                  "wählen – die Umgebung wird dann neu angelegt.")


def env_broken(lines) -> bool:
    text = "\n".join(lines).lower()
    return any(m in text for m in _BROKEN_ENV)


def env_runs(py: str) -> bool:
    """Startet das Python der Umgebung überhaupt? (Basis-Python vorhanden, Umgebung nicht beschädigt)"""
    if not py or not os.path.exists(py):
        return False
    try:
        rc, _tail = run_lines([py, "-c", "import sys"])
    except OSError:
        return False
    return rc == 0


# Von PyInstaller gesetzte Variablen, die ein fremdes Python (Plugin-Umgebung) stören würden
_FROZEN_VARS = {"TCL_LIBRARY", "TK_LIBRARY", "PYTHONHOME", "PYTHONPATH", "SSL_CERT_FILE"}


def _unfreeze_child_env():
    """In der installierten Windows-App erben Kindprozesse sonst deren DLL-Suchpfad (PyInstaller-Eigenheit)."""
    if getattr(sys, "frozen", False) and os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:  # noqa: BLE001
            pass


def run_lines(cmd, on_line=None, cancel=None, env=None, cwd=None, low_priority=False):
    """Startet einen Prozess, liefert jede Ausgabezeile an on_line. Rückgabe: (Exitcode, letzte Zeilen).
    low_priority: niedrige Priorität (Hintergrund-Aufträge), damit der Rechner bedienbar bleibt."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    extra = {}
    if low_priority:
        if os.name == "nt":
            flags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
        elif hasattr(os, "nice"):
            extra["preexec_fn"] = lambda: os.nice(10)
    _unfreeze_child_env()
    e = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k not in _FROZEN_VARS} \
        if getattr(sys, "frozen", False) else dict(os.environ)
    e.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    if env:
        e.update(env)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=flags, env=e, cwd=cwd, **extra)
    tail = []
    stop = threading.Event()

    def watch():   # Abbruch auch während der Prozess nichts ausgibt
        while not stop.wait(0.3):
            if cancel is not None and cancel.is_set():
                proc.terminate()
                return
    threading.Thread(target=watch, daemon=True).start()
    try:
        for line in proc.stdout:
            line = line.rstrip("\r\n")
            if not line:
                continue
            tail.append(line)
            del tail[:-400]
            if on_line:
                on_line(line)
    finally:
        rc = proc.wait()
        stop.set()
        proc.stdout.close()
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    return rc, tail


# =========================================================================== Kontext für Plugins
class Context:
    """Was ein Plugin während eines Laufs benutzen darf."""

    def __init__(self, plugin, session=None, cancel=None, progress=None, background=False):
        self.plugin = plugin
        self.background = bool(background)   # läuft als Hintergrund-Auftrag (eigene Dateikopien, kein Undo)
        self.id = plugin.id
        self._session = session
        self._cancel = cancel or threading.Event()
        self._progress = progress or (lambda m: None)
        self.log_lines: list[str] = []
        self.outputs: list[str] = []
        self.proposals: list[dict] = []
        self.same_syncs: dict[int, list] = {}   # Abgleich (#145/#146): schon gleiche Werte je Datei
        self.changed = False

    # ---- Ordner / Einstellungen
    @property
    def data_dir(self) -> str:
        """Eigener Ordner für Modelle, Caches usw. (wird angelegt)."""
        d = os.path.join(data_root(), self.id)
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def shared_dir(self) -> str:
        """Gemeinsamer Ordner für grosse Daten (Modelle, FFmpeg) – für alle Profile gleich (wird angelegt)."""
        d = os.path.join(shared_root(), self.id)
        os.makedirs(d, exist_ok=True)
        return d

    def setting(self, key, default=None):
        return self.plugin.settings.get(key, default)

    # ---- andere Dienst-Plugins (#204)
    def service(self, pid):
        """Modul eines eingeschalteten, bereiten Dienst-Plugins (z. B. „deezer“) – sonst None."""
        m = MANAGER
        if m is None:
            return None
        p = m.plugins.get(pid)
        if p is None or not p.enabled or p.state() != "ready":
            return None
        return p.load()

    def service_ctx(self, pid):
        """Context für ein anderes Dienst-Plugin (eigener Datenordner, Schlüssel …), mit gleichem Abbruch/Fortschritt."""
        m = MANAGER
        p = m.plugins.get(pid) if m is not None else None
        if p is None:
            return None
        c = Context(p, self._session, self._cancel, self._progress, self.background)
        c.log_lines = self.log_lines          # gemeinsames Protokoll
        return c

    # ---- eigene Python-Umgebung (plugin.json "env")
    @property
    def env_python(self) -> str:
        return self.plugin.env_python()

    @property
    def env_info(self) -> dict:
        return self.plugin.env_info()

    def run_env(self, args, on_line=None, env=None):
        """Python der Plugin-Umgebung mit args starten (z. B. [worker.py, job.json]).
        Ausgabezeilen gehen an on_line; Abbruch beendet den Prozess. Rückgabe: (Exitcode, letzte Zeilen)."""
        py = self.env_python
        if not py or not os.path.exists(py):
            raise RuntimeError("Die Umgebung des Plugins ist nicht installiert – bitte auf der Plugin-Seite installieren.")
        rc, tail = run_lines([py, *args], on_line, self._cancel, env=env, cwd=self.data_dir, low_priority=self.background)
        if rc != 0 and env_broken(tail):
            raise RuntimeError(BROKEN_ENV_MSG)
        return rc, tail

    # ---- Fortschritt / Abbruch / Protokoll
    def progress(self, i: int, total: int, text: str = "", frac: float = None):
        """i von total erledigt; frac (0–1) = Anteil des gerade laufenden Elements (für lange Einzelschritte)."""
        self.check_cancel()
        self._progress(("progress", i, total, text, frac))

    def status(self, text: str):
        self._progress(("text", text))

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check_cancel(self):
        if self._cancel.is_set():
            raise Cancelled()

    def log(self, msg: str):
        self.log_lines.append(str(msg))

    def output(self, path: str):
        """Erzeugte Datei/Ordner melden (wird im Ergebnis angezeigt)."""
        self.outputs.append(path)

    # ---- #238: Zustand der Oberfläche (nur lesend)
    def djset(self) -> dict:
        """Aktuelles DJ-Set: {"name", "paths"} (leer ohne Sitzung)."""
        s = self._session
        if s is None or not hasattr(s, "_dj"):
            return {"name": "", "paths": []}
        with s.lock:
            return {"name": s.cfg.get("djset_name") or "", "paths": [x["path"] for x in s._dj()["items"]]}

    # ---- Vorschläge (werden nach dem Lauf als Vorschau mit Häkchen gezeigt)
    def propose(self, f, key, new, label=None, note="", checked=True, kind="text", data=None, group=None, hint="",
                show_same=False, link="", link_label="", sync=None, old=None):
        """Änderung vorschlagen statt sie direkt auszuführen. kind="text" (key/new), "cover" (data=Bildbytes),
        "frame" (key = Frame-Schlüssel wie „SYLT“, data = Frame-Rumpf, new = Beschreibung für die Vorschau) oder
        "file" (key = Pfad einer Begleitdatei neben dem MP3, data = Inhalt; geschrieben beim Übernehmen, #183).
        note: Hinweis zur Datei (z. B. Treffer und Sicherheit), group: Überschrift je Datei,
        hint: Hinweis zu genau diesem Feld (z. B. „schon gefüllt“).
        show_same=True: auch einen unveränderten Wert als (nicht wählbare) Zeile „gleich“ zeigen.
        link/link_label: Adresse des Treffers auf der Plattform (nur https), z. B. zum Vergleichen der Version (#144).
        sync: (Quelle, Merkmal, Wert) – beim Übernehmen in TXXX:TAGSTUDIO merken (siehe importsync).
        #237: kind="rating" – Bewertung 0–5 Sterne (POPM, new = Anzahl Sterne).
        #239: kind="remote" – Änderung ausserhalb der Datei (z. B. in Lexicon): old = bisheriger Wert dort, data =
        beliebige Angaben für das Plugin; beim Übernehmen ruft TagStudio apply_remote(ctx, items) des Plugins auf."""
        same = False
        if kind == "remote":
            old = "" if old is None else str(old)
            same = str(new or "") == old
            if same and not show_same:
                return False
        elif kind == "rating":
            import ratings
            old = str(ratings.get_rating(f) or "")
            same = str(new or "") == old
            if same and not show_same:
                return False
        elif kind == "text":
            it = f.get(key)
            old = it.text if it is not None and it.kind not in ("picture", "raw") else ""
            if (new or "") == old:
                if not show_same:
                    return False
                same = True
        elif kind == "file":
            old = "vorhanden" if os.path.exists(key) else ""
            same = data is None
        else:
            old = "vorhanden" if f.get(key) is not None else ""
            same = data is None    # nur Info (z. B. Cover vorhanden, nicht geladen)
        self.proposals.append({"file": f, "key": key, "new": "" if new is None else str(new), "old": old,
                               "label": label or key, "note": note, "checked": bool(checked) and not same, "kind": kind,
                               "data": data, "group": group, "hint": hint, "same": same,
                               "link": link if str(link or "").startswith("https://") else "", "link_label": link_label or "",
                               "sync": tuple(sync) if sync else None})
        return True

    def remember_sync(self, f, sync):
        """Abgleich für einen schon gleichen Wert merken – wird gespeichert, wenn für diese Datei etwas übernommen wird."""
        self.same_syncs.setdefault(id(f), []).append(tuple(sync))

    # ---- Tags ändern (mit Rückgängig, noch nicht gespeichert)
    def edit_tags(self, files, fn, label=None):
        """fn(f) ändert die Tags einer Datei (f.set_text …). Läuft unter der Sitzungssperre mit Undo."""
        if self._session is None:
            for f in files:
                fn(f)
            self.changed = True
            return
        s = self._session
        with s.lock:
            s.undo.checkpoint(label or self.plugin.name, list(files))
            try:
                for f in files:
                    fn(f)
            finally:   # auch bei Fehler abschliessen, sonst landen Teiländerungen im nächsten Undo-Schritt
                s.undo.commit()
        self.changed = True


# =========================================================================== Plugin-Beschreibung
class Plugin:
    def __init__(self, path: str, builtin: bool):
        self.path = path
        self.builtin = builtin
        self.manifest: dict = {}
        self.module = None
        self.error = ""
        self.settings: dict = {}
        self.enabled = True
        self._load_manifest()

    @classmethod
    def broken(cls, path: str, builtin: bool, ex: Exception) -> "Plugin":
        pl = cls.__new__(cls)
        pl.path, pl.builtin, pl.manifest, pl.module = path, builtin, {}, None
        pl.settings, pl.enabled = {}, True
        pl.id = re.sub(r"[^a-z0-9_-]", "_", os.path.basename(path).lower())[:40] or "plugin"
        pl.error = f"Plugin nicht ladbar: {str(ex) or type(ex).__name__}"
        return pl

    # ---- Manifest
    def _load_manifest(self):
        mf = os.path.join(self.path, "plugin.json")
        try:
            with open(mf, encoding="utf-8") as fh:
                self.manifest = json.load(fh)
        except (OSError, ValueError) as ex:
            self.manifest = {}
            self.error = f"plugin.json nicht lesbar: {ex}"
        if not isinstance(self.manifest, dict):
            self.manifest = {}
            self.error = "plugin.json muss ein Objekt { … } sein."
        m = self.manifest
        # Listen-Einträge bereinigen, damit ein fehlerhaftes Manifest nicht die ganze Plugin-Liste lahmlegt
        req = m.get("requires", [])
        m["requires"] = [r for r in (req if isinstance(req, list) else [])
                         if (isinstance(r, str) and r) or (isinstance(r, dict) and isinstance(r.get("module"), str) and r["module"])]
        for k, need in (("install", None), ("external", "cmd")):
            v = m.get(k, [])
            m[k] = [e for e in (v if isinstance(v, list) else []) if isinstance(e, dict) and (need is None or e.get(need))]
        pid = str(m.get("id") or os.path.basename(self.path)).lower()
        self.id = pid if _ID_RE.match(pid) else re.sub(r"[^a-z0-9_-]", "_", pid)[:40] or "plugin"
        try:
            api = int(m.get("api", 1))
        except (TypeError, ValueError):
            api = None
            if not self.error:
                self.error = f"Ungültige Plugin-API-Angabe „{m.get('api')}“ (erwartet: Ganzzahl)."
        if not self.error and api > API_VERSION:
            self.error = f"Benötigt eine neuere TagStudio-Version (Plugin-API {m.get('api')})."

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.id)

    @property
    def service(self):
        """#204: bereinigte Dienstbeschreibung aus plugin.json („service“) oder None."""
        if not hasattr(self, "_service"):
            import services
            self._service = services.clean(self.manifest.get("service"))
        return self._service

    # ---- eigene Umgebung
    @property
    def env_spec(self):
        e = self.manifest.get("env")
        return e if isinstance(e, dict) else None

    @property
    def env_dir(self) -> str:
        return os.path.join(shared_root(), self.id, "env")

    def env_info(self) -> dict:
        """Inhalt der Markierungsdatei nach erfolgreicher Installation (oder {})."""
        try:
            with open(os.path.join(shared_root(), self.id, "env.json"), encoding="utf-8") as fh:
                d = json.load(fh)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def env_python(self) -> str:
        info = self.env_info()
        return info.get("python") or _env_python(self.env_dir)

    def env_files(self) -> list[dict]:
        """#245: Dateien, die beim Installieren geladen und geprüft werden (plugin.json "env": {"files": […]})."""
        return clean_env_files((self.env_spec or {}).get("files"))

    def env_file_path(self, rel: str) -> str:
        return os.path.join(shared_root(), self.id, *str(rel).split("/"))

    def missing(self) -> list[dict]:
        """Fehlende Python-Pakete (geprüft ohne Import)."""
        if self.env_spec:
            info = self.env_info()
            if not info or not os.path.exists(self.env_python()):
                return [{"module": "env", "label": f"Eigene Umgebung (Python {self.env_spec.get('python', '3')} + Pakete)"}]
            gone = [e for e in self.env_files() if not os.path.isfile(self.env_file_path(e["path"]))]
            if gone:                                       # #245: Modell o. Ä. fehlt (gelöscht, neue Version)
                return [{"module": "env", "label": "Daten: " + ", ".join(e["label"] for e in gone)}]
            return []
        out = []
        for r in self.manifest.get("requires", []):
            mod = r.get("module") if isinstance(r, dict) else str(r)
            try:
                found = importlib.util.find_spec(mod) is not None
            except (ImportError, ValueError):
                found = False
            if not found:
                out.append({"module": mod, "label": (r.get("label") if isinstance(r, dict) else None) or mod})
        return out

    def missing_external(self) -> list[dict]:
        out = []
        for e in self.manifest.get("external", []):
            if not shutil.which(e.get("cmd", "")):
                out.append({"label": e.get("label") or e.get("cmd"), "hint": e.get("hint", "")})
        return out

    def state(self) -> str:
        if self.error:
            return "error"
        if self.missing():
            return "missing"
        return "ready"

    # ---- Code laden
    def load(self):
        """Lädt plugin.py (erst bei Bedarf, damit fehlende Pakete den Start nicht stören)."""
        if self.module is not None or self.error:
            return self.module
        src = os.path.join(self.path, "plugin.py")
        if not os.path.isfile(src):
            self.error = "plugin.py fehlt."
            return None
        try:
            spec = importlib.util.spec_from_file_location(f"tagstudio_plugin_{self.id}", src)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not callable(getattr(mod, "run", None)):
                raise AttributeError("plugin.py hat keine Funktion run(action, ctx, files, options).")
            self.module = mod
        except Exception as ex:  # noqa: BLE001 – Plugin-Fehler dürfen das Programm nicht stoppen
            self.error = f"Fehler beim Laden: {ex}"
            self.trace = traceback.format_exc()
        return self.module

    def actions(self, ctx=None) -> list[dict]:
        mod = self.load()
        if mod is None:
            return []
        acts = getattr(mod, "ACTIONS", None)
        if callable(getattr(mod, "actions", None)):
            try:
                acts = mod.actions(ctx or Context(self))
            except Exception as ex:  # noqa: BLE001
                self.error = f"Fehler in actions(): {ex}"
                return []
        out = []
        for a in acts or []:
            if not isinstance(a, dict) or not a.get("id"):
                continue
            a = dict(a)
            a.setdefault("label", a["id"])
            a.setdefault("where", "tagger")
            a["options"] = [o for o in a.get("options", []) if isinstance(o, dict) and o.get("type") in OPTION_TYPES]
            out.append(a)
        return out

    def info(self) -> dict:
        m = self.manifest
        st = self.state()
        d = {"id": self.id, "name": self.name, "version": str(m.get("version", "")),
             "description": m.get("description", ""), "author": m.get("author", ""), "url": m.get("url", ""),
             "builtin": self.builtin, "path": self.path, "enabled": self.enabled, "state": st,
             "error": self.error, "missing": self.missing(), "external": self.missing_external(),
             "install": [{"id": v.get("id"), "label": v.get("label", v.get("id")), "packages": v.get("packages", []),
                          "hint": v.get("hint", "")} for v in m.get("install", []) if v.get("packages")],
             "notes": m.get("notes", ""), "env": bool(self.env_spec),
             "env_variant": self.env_info().get("label", "") if self.env_spec else ""}
        if not self.builtin:                               # #235: aus einem Release nachgeladen?
            import plugin_store
            mk = plugin_store.store_info(self.path)
            if mk:
                d["store"] = {"version": str(mk.get("version", "")), "tag": str(mk.get("tag", ""))}
            d["builtin_version"] = getattr(self, "builtin_version", None)
        d["min_app"] = str(m.get("min_app", ""))
        cat = m.get("category") if m.get("category") in CATEGORIES else ("online" if self.service else "other")
        d["category"], d["category_label"] = cat, CATEGORIES[cat]
        if self.service:                                   # #204: API-Link und Endpunkt-Zahlen
            import services
            d["service"] = services.summary(self.service, self.module if st == "ready" and self.enabled else None)
        if st == "ready" and self.enabled:
            d["actions"] = [{"id": a["id"], "label": a["label"], "where": a["where"],
                             "short": str(a.get("short") or "")[:40],          # #248: Kurzname für die Karte
                             "description": a.get("description", "")} for a in self.actions()]
            st_fn = getattr(self.module, "status", None)
            if callable(st_fn):
                try:
                    d["status_text"] = str(st_fn(Context(self)) or "")
                except Exception as ex:  # noqa: BLE001
                    d["status_text"] = f"Status nicht lesbar: {ex}"
            if self.error:  # actions() kann einen Fehler setzen
                d["state"], d["error"], d["actions"] = "error", self.error, []
        else:
            d["actions"] = []
        return d


# =========================================================================== Verwaltung
class Manager:
    def __init__(self, cfg: dict, dirs=None):
        global MANAGER
        self.cfg = cfg
        self.dirs = dirs or [(BUILTIN_DIR, True), (user_dir(), False)]
        self.plugins: dict[str, Plugin] = {}
        self.scan()
        MANAGER = self

    def scan(self):
        importlib.invalidate_caches()
        found: dict[str, Plugin] = {}
        enabled = self.cfg.get("plugins_enabled", {})
        settings = self.cfg.get("plugin_settings", {})
        for base, builtin in self.dirs:
            if not os.path.isdir(base):
                continue
            for name in sorted(os.listdir(base)):
                p = os.path.join(base, name)
                if name.startswith((".", "_")) or not os.path.isfile(os.path.join(p, "plugin.json")):
                    continue
                try:
                    pl = Plugin(p, builtin)
                except Exception as ex:  # noqa: BLE001 – ein defektes Plugin darf die Liste nicht blockieren
                    pl = Plugin.broken(p, builtin, ex)
                if pl.id in found:   # Benutzer-Plugin mit gleicher id ersetzt das eingebaute
                    if builtin:
                        continue
                    if found[pl.id].builtin:                     # #235: für „Zurück auf eingebaute Version“
                        pl.builtin_version = str(found[pl.id].manifest.get("version", ""))
                pl.enabled = bool(enabled.get(pl.id, True))
                pl.settings = dict(settings.get(pl.id, {}))
                found[pl.id] = pl
        self.plugins = found
        return self.list()

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.plugins.values(), key=lambda p: (not p.builtin, p.name.lower())):
            try:
                out.append(p.info())
            except Exception as ex:  # noqa: BLE001
                p.error = f"Plugin-Beschreibung fehlerhaft: {str(ex) or type(ex).__name__}"
                out.append({"id": p.id, "name": p.name, "version": "", "description": "", "author": "", "url": "",
                            "builtin": p.builtin, "path": p.path, "enabled": p.enabled, "state": "error",
                            "error": p.error, "missing": [], "external": [], "install": [], "notes": "",
                            "env": False, "env_variant": ""})
        return out

    # ---- #204: Dienste
    def services(self) -> list[dict]:
        """Alle Dienst-Plugins mit Endpunkten (für die Gesamtübersicht) plus die Kern-Dienste."""
        import services
        out = []
        for p in sorted(self.plugins.values(), key=lambda p: p.name.lower()):
            svc = p.service
            if not svc:
                continue
            ready = p.enabled and p.state() == "ready"
            out.append({"id": p.id, "plugin": p.id, "plugin_name": p.name, "enabled": p.enabled, "ready": ready,
                        **{k: svc[k] for k in ("name", "kind", "home", "docs", "auth", "note", "limits", "auth_note")},
                        "auth_text": services.AUTH[svc["auth"]], "counts": services.counts(svc),
                        "endpoints": svc["endpoints"],
                        "test_query": bool(ready and callable(getattr(p.load(), "test_query", None)))})
        for c in services.CORE:
            out.append({**c, "plugin_name": "Kern", "enabled": True, "ready": True,
                        "counts": services.counts(c), "test_query": False, "limits": "", "auth_note": ""})
        return out

    def service_plugin(self, pid) -> Plugin:
        p = self.get(pid)
        if not p.service:
            raise ValueError(f"„{p.name}“ ist kein Dienst-Plugin.")
        if not p.enabled:
            raise ValueError(f"Plugin „{p.name}“ ist ausgeschaltet – zuerst einschalten.")
        if p.state() != "ready" or p.load() is None:
            raise ValueError(f"Plugin „{p.name}“ ist nicht bereit: {p.error or 'Pakete fehlen'}.")
        return p

    def api_call(self, pid, eid, params, session=None, cancel=None, progress=None) -> dict:
        import services
        from version import VERSION
        p = self.service_plugin(pid)
        ctx = Context(p, session, cancel, progress)
        ua = f"TagStudio/{VERSION} ( https://github.com/MarkusKeller8200/markussxch-tagstudio )"
        res = services.api_call(p, ctx, eid, params or {}, ua)
        res["log"] = ctx.log_lines
        return res

    def test_query(self, pid, raw, session=None, cancel=None, progress=None) -> dict:
        """Testabfrage ohne Track: gleiche Suche und Bewertung wie mit einem Titel, ohne Tags zu ändern."""
        import services
        p = self.service_plugin(pid)
        mod = p.load()
        fn = getattr(mod, "test_query", None)
        if not callable(fn):
            raise ValueError(f"„{p.name}“ bietet keine Testabfrage.")
        info = services.query_info(raw)
        if not (info["title"] or info["artist"] or info["isrc"]):
            raise ValueError("Bitte mindestens Titel, Künstler oder ISRC angeben.")
        ctx = Context(p, session, cancel, progress)
        try:
            cands = fn(ctx, info) or []
        except Cancelled:
            return {"cancelled": True, "rows": [], "log": ctx.log_lines, "info": info}
        rows = services.result_rows(mod, info, cands)
        return {"rows": rows, "log": ctx.log_lines, "info": info, "count": len(cands)}

    # ---- #238/#239: Ereignisse und Erkennung für Plugins
    def _ready_with(self, fn_name):
        for p in self.plugins.values():
            if p.enabled and p.state() == "ready":
                mod = p.load()
                fn = getattr(mod, fn_name, None)
                if callable(fn):
                    yield p, fn

    def emit(self, event: str, data, session=None, wait=False):
        """Ereignis an Plugins mit on_event(ctx, event, data) melden – im Hintergrund, Fehler nur ins Protokoll.
        Ereignisse: "files_moved" [{"old", "new"}], "files_added" [Pfad]. wait=True (Tests): auf das Ende warten."""
        if not data:
            return []
        threads = []
        for p, fn in list(self._ready_with("on_event")):
            def work(p=p, fn=fn):
                ctx = Context(p, session)
                try:
                    fn(ctx, event, data)
                except Exception:  # noqa: BLE001 – ein Plugin darf die Arbeit nie stören
                    ctx.log(f"Fehler bei „{event}“:\n{traceback.format_exc()}")
                if ctx.log_lines:
                    write_log(f"{p.id}.log", f"Ereignis {event}\n" + "\n".join(ctx.log_lines))
            t = threading.Thread(target=work, daemon=True, name=f"plugin-{p.id}-{event}")
            t.start()
            threads.append(t)
        if wait:
            for t in threads:
                t.join(30)
        return [p.id for p, _fn in self._ready_with("on_event")]

    def detect(self, sid: str, paths, session=None) -> set:
        """Vorbereiten (#238): Plugin mit id sid und detect_files(ctx, paths) → Menge erkannter Pfade."""
        p = self.plugins.get(sid)
        if p is None or not p.enabled or p.state() != "ready" or not paths:
            return set()
        fn = getattr(p.load(), "detect_files", None)
        if not callable(fn):
            return set()
        ctx = Context(p, session)
        try:
            return {x for x in (fn(ctx, list(paths)) or []) if isinstance(x, str)}
        except Exception as ex:  # noqa: BLE001
            write_log(f"{p.id}.log", f"Erkennung fehlgeschlagen: {ex}")
            return set()

    # ---- #242: Playlists anderer Programme fürs DJ-Set (playlists(ctx), playlist_files(ctx, id))
    PLAYLIST_FNS = ("playlists", "playlist_files")

    def playlist_sources(self) -> list[dict]:
        """Bereite, eingeschaltete Plugins mit playlists(ctx) – z. B. Lexicon."""
        return [{"id": p.id, "name": p.name} for p, _fn in self._ready_with("playlists")]

    def call_playlist(self, pid, fn_name, *args, session=None, cancel=None, progress=None):
        if fn_name not in self.PLAYLIST_FNS:
            raise ValueError("Unbekannte Funktion.")
        p = self.get(pid)
        if not p.enabled or p.state() != "ready":
            raise ValueError(f"Plugin „{p.name}“ ist nicht bereit.")
        fn = getattr(p.load(), fn_name, None)
        if not callable(fn):
            raise ValueError(f"„{p.name}“ bietet keine Playlists.")
        return fn(Context(p, session, cancel, progress), *args)

    def apply_remote(self, pid, items, session=None) -> dict:
        """#239: übernommene Vorschläge kind="remote" an das Plugin (apply_remote(ctx, items))."""
        p = self.get(pid)
        fn = getattr(p.load(), "apply_remote", None)
        if not callable(fn):
            raise ValueError(f"„{p.name}“ kann keine Änderungen übernehmen.")
        ctx = Context(p, session)
        res = fn(ctx, items) or {}
        res["log"] = ctx.log_lines + list(res.get("log", []))
        if res["log"]:
            res["logfile"] = write_log(f"{p.id}.log", "\n".join(res["log"]))
        return res

    def get(self, pid) -> Plugin:
        p = self.plugins.get(pid)
        if p is None:
            raise KeyError(f"Plugin „{pid}“ nicht gefunden.")
        return p

    def set_enabled(self, pid, on: bool):
        p = self.get(pid)
        p.enabled = bool(on)
        self.cfg.setdefault("plugins_enabled", {})[pid] = p.enabled
        return {"plugins_enabled": self.cfg["plugins_enabled"]}

    def actions(self, where="tagger") -> list[dict]:
        out = []
        for p in self.plugins.values():
            if not p.enabled or p.state() != "ready":
                continue
            for a in p.actions():
                if a["where"] == where:
                    out.append({"plugin": p.id, "plugin_name": p.name, "id": a["id"], "label": a["label"],
                                "description": a.get("description", "")})
        return out

    def action(self, pid, aid) -> tuple[Plugin, dict]:
        p = self.get(pid)
        if not p.enabled:
            raise ValueError(f"Plugin „{p.name}“ ist ausgeschaltet.")
        if p.state() != "ready":
            raise ValueError(f"Plugin „{p.name}“ ist nicht bereit: {p.error or 'Pakete fehlen'}.")
        for a in p.actions():
            if a["id"] == aid:
                return p, a
        raise KeyError(f"Aktion „{aid}“ nicht gefunden.")

    def form(self, pid, aid) -> dict:
        """Optionen einer Aktion mit den zuletzt benutzten Werten."""
        p, a = self.action(pid, aid)
        last = self.cfg.get("plugin_options", {}).get(pid, {}).get(aid, {})
        opts = []
        for o in a["options"]:
            o = dict(o)
            if o["type"] in SECRET_TYPES or o.get("secret"):
                o["value"] = ""
            elif o.get("key") in last:
                o["value"] = last[o["key"]]
            else:
                o["value"] = o.get("default", False if o["type"] == "check" else "")
            opts.append(o)
        return {"plugin": pid, "plugin_name": p.name, "id": aid, "label": a["label"],
                "description": a.get("description", ""), "options": opts, "run_label": a.get("run_label", "Ausführen"),
                "needs_selection": a.get("needs_selection", True),
                "background": bool(a.get("background", (p.manifest or {}).get("background", False)))}

    def clean_options(self, action: dict, values: dict) -> dict:
        out = {}
        values = values or {}
        for o in action["options"]:
            k, t = o.get("key"), o["type"]
            if not k or t == "info":
                continue
            v = values.get(k, o.get("default"))
            if t == "check":
                v = bool(v)
            elif t == "number":
                try:
                    v = float(v)
                    v = int(v) if v.is_integer() else v
                except (TypeError, ValueError):
                    v = o.get("default", 0)
            elif t == "select":
                allowed = [c[0] if isinstance(c, (list, tuple)) else c for c in o.get("choices", [])]
                if v not in allowed:
                    v = o.get("default", allowed[0] if allowed else "")
            else:
                v = "" if v is None else str(v)
            out[k] = v
        return out

    def remember(self, pid, aid, opts):
        try:
            _p, a = self.action(pid, aid)
            secret = {o.get("key") for o in a["options"] if o["type"] in SECRET_TYPES or o.get("secret")}
        except (KeyError, ValueError):
            secret = set()
        opts = {k: v for k, v in opts.items() if k not in secret}
        self.cfg.setdefault("plugin_options", {}).setdefault(pid, {})[aid] = opts
        return {"plugin_options": self.cfg["plugin_options"]}

    def is_background(self, pid, aid) -> bool:
        """Aktion als Hintergrund-Auftrag? („background“: true in der Aktion oder in plugin.json)"""
        p, a = self.action(pid, aid)
        return bool(a.get("background", (p.manifest or {}).get("background", False)))

    def run(self, pid, aid, files, values, session=None, cancel=None, progress=None, background=False) -> dict:
        p, a = self.action(pid, aid)
        opts = self.clean_options(a, values)
        ctx = Context(p, session, cancel, progress, background)
        try:
            res = p.module.run(aid, ctx, list(files), opts) or {}
        except Cancelled:
            return {"cancelled": True, "log": ctx.log_lines, "outputs": ctx.outputs, "changed": ctx.changed,
                    "proposals": []}
        if not isinstance(res, dict):
            res = {"message": str(res)}
        res.setdefault("message", f"{a['label']}: fertig.")
        res["log"] = ctx.log_lines + list(res.get("log", []))
        res["outputs"] = ctx.outputs + [o for o in res.get("outputs", []) if o not in ctx.outputs]
        res["changed"] = bool(res.get("changed") or ctx.changed)
        for prop in ctx.proposals:
            prop["sync_same"] = ctx.same_syncs.get(id(prop["file"]), [])
        res["proposals"] = ctx.proposals
        return res


# =========================================================================== Pakete installieren
def pip_install(packages, cancel=None, progress=None) -> dict:
    """pip install … mit dem laufenden Python. Ausgabe zeilenweise als Fortschrittstext."""
    if not packages:
        return {"ok": False, "error": "Keine Pakete angegeben."}
    if getattr(sys, "frozen", False):
        return {"ok": False, "error": "In der gepackten App lassen sich keine Pakete nachinstallieren."}
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *packages]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", creationflags=flags)
    except OSError as ex:
        return {"ok": False, "error": f"pip konnte nicht gestartet werden: {ex}"}
    lines = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            lines.append(line)
            if progress:
                progress(("text", line[:160]))
        if cancel is not None and cancel.is_set():
            proc.terminate()
            proc.wait()
            raise Cancelled()
    rc = proc.wait()
    importlib.invalidate_caches()
    return {"ok": rc == 0, "code": rc, "log": lines[-60:], "command": " ".join(cmd[2:]),
            "error": "" if rc == 0 else "pip meldet einen Fehler – Details im Protokoll."}


def uv_command(install=False, progress=None, cancel=None):
    """Aufruf für uv: in der installierten App die mitgelieferte uv-Datei, sonst uv aus dem Python-Paket
    bzw. aus dem Suchpfad. Mit install=True wird uv bei Bedarf per pip nachinstalliert (nur Quellcode-Version)."""
    exe = "uv.exe" if os.name == "nt" else "uv"
    if getattr(sys, "frozen", False):
        for base in (getattr(sys, "_MEIPASS", ""), os.path.dirname(sys.executable)):
            cand = os.path.join(base, exe)
            if base and os.path.isfile(cand):
                return [cand]
    if importlib.util.find_spec("uv") is not None and not getattr(sys, "frozen", False):
        return [sys.executable, "-m", "uv"]
    found = shutil.which("uv")
    if found:
        return [found]
    if install and not getattr(sys, "frozen", False):
        rc, tail = run_lines([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "uv"],
                             (lambda ln: progress(("text", ln[:160]))) if progress else None, cancel)
        importlib.invalidate_caches()
        if rc == 0:
            return [sys.executable, "-m", "uv"]
        raise RuntimeError("uv konnte nicht installiert werden:\n" + "\n".join(tail[-10:]))
    raise RuntimeError("uv wurde nicht gefunden – in der installierten App sollte es mitgeliefert sein.")


# Modulname → pip-Paket, wo sie sich unterscheiden (für das Nachinstallieren fehlender Module)
MODULE_PACKAGES = {"yaml": "pyyaml", "sklearn": "scikit-learn", "cv2": "opencv-python", "PIL": "pillow",
                   "soundfile": "soundfile", "samplerate": "samplerate", "ml_collections": "ml-collections"}


# #245: Herkunft erlaubter Zusatzdateien (Modelle, Programmteile) – nur feste Stände auf GitHub, immer mit Prüfsumme
FILE_HOSTS = ("https://raw.githubusercontent.com/", "https://github.com/", "https://media.githubusercontent.com/")
_REL_RE = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+){0,4}$")


def clean_env_files(entries) -> list[dict]:
    """plugin.json "env.files" prüfen: [{"url", "path", "sha256", "label"}] – Adresse auf GitHub (https), relativer
    Pfad ohne „..“, SHA-256 mit 64 Hex-Zeichen. Ungültige Einträge werden weggelassen."""
    out = []
    for e in entries if isinstance(entries, list) else []:
        if not isinstance(e, dict):
            continue
        url, rel, sha = str(e.get("url") or ""), str(e.get("path") or ""), str(e.get("sha256") or "").lower()
        if (not url.startswith(FILE_HOSTS) or not _REL_RE.match(rel) or ".." in rel.split("/")
                or rel.split("/")[0] in ("env", "env.json") or not re.fullmatch(r"[0-9a-f]{64}", sha)):
            continue
        out.append({"url": url, "path": rel, "sha256": sha, "label": str(e.get("label") or os.path.basename(rel))[:80],
                    "size": int(e.get("size") or 0)})
    return out


def file_sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_file(entry: dict, dest: str, cancel=None, say=None, opener=None):
    """Eine Zusatzdatei laden und gegen die Prüfsumme prüfen; schon vorhandene, korrekte Dateien bleiben.
    Bei Abweichung wird nichts abgelegt (ValueError)."""
    import hashlib
    import urllib.request
    if os.path.isfile(dest) and file_sha256(dest) == entry["sha256"]:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    h, done = hashlib.sha256(), 0
    req = urllib.request.Request(entry["url"], headers={"User-Agent": "MarKusSXCH-TagStudio"})
    op = opener or urllib.request.urlopen
    try:
        with op(req, timeout=60) as r, open(part, "wb") as fh:
            total = int(r.headers.get("Content-Length") or 0) or entry.get("size") or 0
            while True:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if say:
                    say(f"Lade {entry['label']} … " + (f"{round(100 * done / total)} %" if total else f"{done / 1e6:.1f} MB"))
        if h.hexdigest() != entry["sha256"]:
            raise ValueError(f"Prüfsumme von {entry['label']} stimmt nicht – Datei unvollständig oder verändert. "
                             "Nichts übernommen.")
        os.replace(part, dest)
    finally:
        if os.path.exists(part):
            os.remove(part)
    return True


def env_install(plugin, variant: dict, cancel=None, progress=None) -> dict:
    """Eigene Umgebung für ein Plugin anlegen: uv (bei Bedarf per pip) → uv venv mit passender Python-Version
    (lädt sie selbst herunter) → uv pip install Pakete → Import prüfen → Markierung env.json schreiben."""
    say = (lambda t: progress(("text", t[:160]))) if progress else (lambda t: None)
    log = [f"Plugin: {plugin.id}  Variante: {variant.get('id')}  Pakete: {' '.join(variant.get('packages', []))}"]

    def step(title, cmd, cwd=None):
        say(title)
        log.append(f"$ {' '.join(cmd)}")
        rc, tail = run_lines(cmd, lambda ln: say(ln), cancel, cwd=cwd)
        log.extend(tail)
        if rc != 0:
            path = write_log(f"{plugin.id}-installation.log", "\n".join(log))
            return {"ok": False, "error": f"{title} fehlgeschlagen (Code {rc}).", "log": log[-40:], "logfile": path}
        return None

    base = os.path.join(shared_root(), plugin.id)
    os.makedirs(base, exist_ok=True)
    try:
        say("Suche uv (Umgebungs-Verwaltung) …")
        uv = uv_command(install=True, progress=progress, cancel=cancel)
    except RuntimeError as ex:
        path = write_log(f"{plugin.id}-installation.log", "\n".join(log + [str(ex)]))
        return {"ok": False, "error": str(ex), "log": log[-40:], "logfile": path}
    log.append("uv: " + " ".join(uv))
    marker = os.path.join(base, "env.json")
    attempt = os.path.join(base, "env-versuch.json")   # Variante des letzten (auch gescheiterten) Versuchs
    try:
        with open(attempt, encoding="utf-8") as fh:
            last_variant = json.load(fh).get("variant")
    except (OSError, ValueError):
        last_variant = None
    if os.path.exists(marker):
        os.remove(marker)
    env_dir = plugin.env_dir
    py = _env_python(env_dir)
    pyver = str(plugin.env_spec.get("python", "3.12"))
    reuse = os.path.exists(py) and last_variant == variant.get("id")
    if reuse and not env_runs(py):             # #135: Basis-Python fehlt → nicht weiterverwenden
        say("Vorhandene Umgebung ist beschädigt – wird neu angelegt …")
        log.append("Vorhandene Umgebung startet nicht (Basis-Python fehlt) – wird neu angelegt.")
        reuse = False
    if reuse:
        say("Vorhandene Umgebung wird weiterverwendet …")
        log.append("Vorhandene Umgebung wird weiterverwendet (gleiche Variante).")
    else:
        if os.path.isdir(env_dir):
            say("Entferne alte Umgebung …")
            shutil.rmtree(env_dir, ignore_errors=True)
        r = step(f"Lege Umgebung mit Python {pyver} an (lädt Python bei Bedarf) …",
                 uv + ["venv", "--python", pyver, env_dir], cwd=base)
        if r:
            return r
    with open(attempt, "w", encoding="utf-8") as fh:
        json.dump({"variant": variant.get("id")}, fh)
    cmd = uv + ["pip", "install", "--python", py]
    for idx in variant.get("extra_index", []):
        cmd += ["--extra-index-url", idx]
    if variant.get("extra_index"):
        cmd += ["--index-strategy", "unsafe-best-match"]
    r = step("Installiere Pakete (das dauert) …", cmd + list(variant.get("packages", [])), cwd=base)
    if r:
        return r
    for mod in plugin.env_spec.get("check", []):
        for _attempt in range(4):         # fehlende, nicht deklarierte Abhängigkeiten selbst nachinstallieren
            say(f"Prüfe {mod} …")
            log.append(f"$ {py} -c import {mod}")
            rc, tail = run_lines([py, "-c", f"import {mod}"], lambda ln: say(ln), cancel, cwd=base)
            log.extend(tail)
            if rc == 0:
                break
            m = re.search(r"No module named '([A-Za-z0-9_]+)", "\n".join(tail))
            if not m:
                path = write_log(f"{plugin.id}-installation.log", "\n".join(log))
                return {"ok": False, "error": f"Prüfe {mod} fehlgeschlagen (Code {rc}).", "log": log[-40:], "logfile": path}
            missing = m.group(1)
            pkg = MODULE_PACKAGES.get(missing, missing.replace("_", "-"))
            r = step(f"Ergänze fehlendes Paket {pkg} …", uv + ["pip", "install", "--python", py, pkg], cwd=base)
            if r:
                return r
        else:
            path = write_log(f"{plugin.id}-installation.log", "\n".join(log))
            return {"ok": False, "error": f"{mod} lässt sich auch nach Nachinstallieren nicht laden.",
                    "log": log[-40:], "logfile": path}
    for entry in plugin.env_files():          # #245: Modelle/Programmteile von festem Stand, mit Prüfsumme
        log.append(f"Datei: {entry['url']} → {entry['path']}")
        try:
            got = fetch_file(entry, plugin.env_file_path(entry["path"]), cancel, say)
            log.append("  geladen und geprüft" if got else "  schon vorhanden (Prüfsumme stimmt)")
        except Cancelled:
            raise
        except Exception as ex:  # noqa: BLE001 – Netzwerk, Prüfsumme
            log.append(f"  Fehler: {ex}")
            path = write_log(f"{plugin.id}-installation.log", "\n".join(log))
            return {"ok": False, "error": f"{entry['label']} konnte nicht geladen werden: {ex}", "log": log[-40:],
                    "logfile": path}
    info = {"python": py, "variant": variant.get("id"), "label": variant.get("label", ""),
            "packages": variant.get("packages", []), "python_version": pyver}
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    path = write_log(f"{plugin.id}-installation.log", "\n".join(log + ["OK"]))
    return {"ok": True, "log": log[-40:], "logfile": path}
