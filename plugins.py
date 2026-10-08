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
OPTION_TYPES = {"select", "check", "text", "number", "folder", "info", "password", "textarea"}
SECRET_TYPES = {"password"}   # werden nie gespeichert


class Cancelled(Exception):
    """Abbruch durch den Benutzer."""


def user_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "TagStudio", "Plugins")


def data_root() -> str:
    return os.path.join(os.path.expanduser("~"), "TagStudio", "Plugin-Daten")


def log_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), "TagStudio", "Logs")
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


def run_lines(cmd, on_line=None, cancel=None, env=None, cwd=None):
    """Startet einen Prozess, liefert jede Ausgabezeile an on_line. Rückgabe: (Exitcode, letzte Zeilen)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    e = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    if env:
        e.update(env)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", creationflags=flags, env=e, cwd=cwd)
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

    def __init__(self, plugin, session=None, cancel=None, progress=None):
        self.plugin = plugin
        self.id = plugin.id
        self._session = session
        self._cancel = cancel or threading.Event()
        self._progress = progress or (lambda m: None)
        self.log_lines: list[str] = []
        self.outputs: list[str] = []
        self.proposals: list[dict] = []
        self.changed = False

    # ---- Ordner / Einstellungen
    @property
    def data_dir(self) -> str:
        """Eigener Ordner für Modelle, Caches usw. (wird angelegt)."""
        d = os.path.join(data_root(), self.id)
        os.makedirs(d, exist_ok=True)
        return d

    def setting(self, key, default=None):
        return self.plugin.settings.get(key, default)

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
        return run_lines([py, *args], on_line, self._cancel, env=env, cwd=self.data_dir)

    # ---- Fortschritt / Abbruch / Protokoll
    def progress(self, i: int, total: int, text: str = ""):
        self.check_cancel()
        self._progress(("progress", i, total, text))

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

    # ---- Vorschläge (werden nach dem Lauf als Vorschau mit Häkchen gezeigt)
    def propose(self, f, key, new, label=None, note="", checked=True, kind="text", data=None, group=None, hint=""):
        """Änderung vorschlagen statt sie direkt auszuführen. kind="text" (key/new) oder "cover" (data=Bytes).
        note: Hinweis zur Datei (z. B. Treffer und Sicherheit), group: Überschrift je Datei,
        hint: Hinweis zu genau diesem Feld (z. B. „schon gefüllt“)."""
        if kind == "text":
            it = f.get(key)
            old = it.text if it is not None and it.kind not in ("picture", "raw") else ""
            if (new or "") == old:
                return False
        else:
            old = "vorhanden" if f.get(key) is not None else ""
        self.proposals.append({"file": f, "key": key, "new": "" if new is None else str(new), "old": old,
                               "label": label or key, "note": note, "checked": bool(checked), "kind": kind,
                               "data": data, "group": group, "hint": hint})
        return True

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
            for f in files:
                fn(f)
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

    # ---- Manifest
    def _load_manifest(self):
        mf = os.path.join(self.path, "plugin.json")
        try:
            with open(mf, encoding="utf-8") as fh:
                self.manifest = json.load(fh)
        except (OSError, ValueError) as ex:
            self.manifest = {}
            self.error = f"plugin.json nicht lesbar: {ex}"
        pid = str(self.manifest.get("id") or os.path.basename(self.path)).lower()
        self.id = pid if _ID_RE.match(pid) else re.sub(r"[^a-z0-9_-]", "_", pid)[:40] or "plugin"
        if not self.error and int(self.manifest.get("api", 1)) > API_VERSION:
            self.error = f"Benötigt eine neuere TagStudio-Version (Plugin-API {self.manifest.get('api')})."

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.id)

    # ---- eigene Umgebung
    @property
    def env_spec(self):
        e = self.manifest.get("env")
        return e if isinstance(e, dict) else None

    @property
    def env_dir(self) -> str:
        return os.path.join(data_root(), self.id, "env")

    def env_info(self) -> dict:
        """Inhalt der Markierungsdatei nach erfolgreicher Installation (oder {})."""
        try:
            with open(os.path.join(data_root(), self.id, "env.json"), encoding="utf-8") as fh:
                d = json.load(fh)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def env_python(self) -> str:
        info = self.env_info()
        return info.get("python") or _env_python(self.env_dir)

    def missing(self) -> list[dict]:
        """Fehlende Python-Pakete (geprüft ohne Import)."""
        if self.env_spec:
            info = self.env_info()
            if not info or not os.path.exists(self.env_python()):
                return [{"module": "env", "label": f"Eigene Umgebung (Python {self.env_spec.get('python', '3')} + Pakete)"}]
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
        if st == "ready" and self.enabled:
            d["actions"] = [{"id": a["id"], "label": a["label"], "where": a["where"],
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
        self.cfg = cfg
        self.dirs = dirs or [(BUILTIN_DIR, True), (user_dir(), False)]
        self.plugins: dict[str, Plugin] = {}
        self.scan()

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
                pl = Plugin(p, builtin)
                if pl.id in found:   # Benutzer-Plugin mit gleicher id ersetzt das eingebaute
                    if builtin:
                        continue
                pl.enabled = bool(enabled.get(pl.id, True))
                pl.settings = dict(settings.get(pl.id, {}))
                found[pl.id] = pl
        self.plugins = found
        return self.list()

    def list(self) -> list[dict]:
        return [p.info() for p in sorted(self.plugins.values(), key=lambda p: (not p.builtin, p.name.lower()))]

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
                "needs_selection": a.get("needs_selection", True)}

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

    def run(self, pid, aid, files, values, session=None, cancel=None, progress=None) -> dict:
        p, a = self.action(pid, aid)
        opts = self.clean_options(a, values)
        ctx = Context(p, session, cancel, progress)
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

    base = os.path.join(data_root(), plugin.id)
    os.makedirs(base, exist_ok=True)
    if importlib.util.find_spec("uv") is None:
        if getattr(sys, "frozen", False):
            return {"ok": False, "error": "uv fehlt – in der gepackten App noch nicht unterstützt."}
        r = step("Installiere uv (Umgebungs-Verwaltung) …",
                 [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "uv"])
        if r:
            return r
        importlib.invalidate_caches()
    uv = [sys.executable, "-m", "uv"]
    marker = os.path.join(base, "env.json")
    if os.path.exists(marker):
        os.remove(marker)
    env_dir = plugin.env_dir
    if os.path.isdir(env_dir):
        say("Entferne alte Umgebung …")
        shutil.rmtree(env_dir, ignore_errors=True)
    pyver = str(plugin.env_spec.get("python", "3.12"))
    r = step(f"Lege Umgebung mit Python {pyver} an (lädt Python bei Bedarf) …",
             uv + ["venv", "--python", pyver, env_dir], cwd=base)
    if r:
        return r
    py = _env_python(env_dir)
    cmd = uv + ["pip", "install", "--python", py]
    for idx in variant.get("extra_index", []):
        cmd += ["--extra-index-url", idx]
    if variant.get("extra_index"):
        cmd += ["--index-strategy", "unsafe-best-match"]
    r = step("Installiere Pakete (das dauert) …", cmd + list(variant.get("packages", [])), cwd=base)
    if r:
        return r
    for mod in plugin.env_spec.get("check", []):
        r = step(f"Prüfe {mod} …", [py, "-c", f"import {mod}"], cwd=base)
        if r:
            return r
    info = {"python": py, "variant": variant.get("id"), "label": variant.get("label", ""),
            "packages": variant.get("packages", []), "python_version": pyver}
    with open(marker, "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    path = write_log(f"{plugin.id}-installation.log", "\n".join(log + ["OK"]))
    return {"ok": True, "log": log[-40:], "logfile": path}
