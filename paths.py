"""MarKusSXCH TagStudio – zentrale Datenpfade und Profile (#163, #164).

Ohne Profil („Standard“) bleibt alles wie bisher: Einstellungen in ~/.tagstudio.json, Daten in ~/TagStudio.
Mit Profil NAME: alles unter ~/TagStudio-Profile/NAME/ (Einstellungen in einstellungen.json), eigene Instanz-Sperre.
Gemeinsam für alle Profile: eigene Plugins (Programmcode) und grosse Plugin-Daten wie die Stems-Umgebung, Modelle
und FFmpeg (Entscheid User 2026-10-11) – Einstellungen, Anmeldungen und Protokolle der Plugins liegen je Profil.

Profil bestimmen (Reihenfolge): Startparameter --profil NAME → Umgebungsvariable TAGSTUDIO_PROFIL → Datei
profil.ini neben dem Programm (portable) → Standard. Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import re
import sys

DEFAULT = "Standard"
_NAME_RE = re.compile(r"^[\w][\w .\-]{0,39}$", re.UNICODE)
_profile: str | None = None


def clean_name(name) -> str | None:
    """Gültiger Profilname oder None (= Standard). Wirft ValueError bei ungültigen Zeichen."""
    n = str(name or "").strip()
    if not n or n.lower() == DEFAULT.lower():
        return None
    if not _NAME_RE.match(n) or n in (".", ".."):
        raise ValueError("Profilname: Buchstaben, Ziffern, Leerzeichen, Punkt, Binde- und Unterstrich (max. 40 Zeichen).")
    return n


def _from_argv(argv) -> str:
    for i, a in enumerate(argv):
        if a in ("--profil", "--profile") and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(("--profil=", "--profile=")):
            return a.split("=", 1)[1]
    return ""


def _from_ini() -> str:
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    p = os.path.join(base, "profil.ini")
    try:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                k, _, v = line.partition("=")
                if k.strip().lower() in ("profil", "profile") and v.strip():
                    return v.strip()
    except OSError:
        pass
    return ""


def init(argv=None):
    """Profil aus Startparameter/Umgebung/profil.ini bestimmen (beim Import automatisch)."""
    global _profile
    raw = _from_argv(sys.argv[1:] if argv is None else argv) or os.environ.get("TAGSTUDIO_PROFIL", "") or _from_ini()
    try:
        _profile = clean_name(raw)
    except ValueError:
        _profile = None


def profile() -> str | None:
    return _profile


def profile_label() -> str:
    return _profile or DEFAULT


def set_profile(name):
    """Nur für Tests und den Programmstart – Module mit festen Pfaden lesen ihn beim Import."""
    global _profile
    _profile = clean_name(name)


def home() -> str:
    return os.path.expanduser("~")


def base_dir() -> str:
    """Datenordner des Standardprofils (auch Ablage für Gemeinsames)."""
    return os.path.join(home(), "TagStudio")


def profiles_dir() -> str:
    return os.path.join(home(), "TagStudio-Profile")


def data_dir(name: str | None = "") -> str:
    """Datenordner des aktuellen (oder angegebenen) Profils."""
    p = _profile if name == "" else clean_name(name)
    return os.path.join(profiles_dir(), p) if p else base_dir()


def sub(*parts) -> str:
    return os.path.join(data_dir(), *parts)


def config_file(name: str | None = "") -> str:
    p = _profile if name == "" else clean_name(name)
    return os.path.join(data_dir(p or None), "einstellungen.json") if p else os.path.join(home(), ".tagstudio.json")


def lock_file() -> str:
    return os.path.join(data_dir(), ".tagstudio.lock") if _profile else os.path.join(home(), ".tagstudio.lock")


def mutex_name() -> str:
    return "MarKusSXCH-TagStudio" + (f"-{re.sub(r'[^0-9A-Za-z_-]', '_', _profile)}" if _profile else "")


def shared_plugin_data() -> str:
    """Gemeinsame, grosse Plugin-Daten (Stems-Umgebung, Modelle, FFmpeg) – für alle Profile gleich."""
    return os.path.join(base_dir(), "Plugin-Daten")


# =========================================================================== Profil-Liste und Startauswahl
def registry_file() -> str:
    return os.path.join(base_dir(), "profile.json")


def load_registry() -> dict:
    try:
        with open(registry_file(), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        d = {}
    return {"ask": d.get("ask", True) is not False, "last": str(d.get("last") or "")}


def save_registry(reg: dict):
    os.makedirs(base_dir(), exist_ok=True)
    tmp = registry_file() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"ask": bool(reg.get("ask", True)), "last": str(reg.get("last") or "")}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, registry_file())


def list_profiles() -> list[str]:
    """Alle Profile (Standard zuerst)."""
    out = [DEFAULT]
    try:
        names = sorted(n for n in os.listdir(profiles_dir()) if os.path.isdir(os.path.join(profiles_dir(), n)))
    except OSError:
        names = []
    for n in names:
        try:
            if clean_name(n):
                out.append(n)
        except ValueError:
            continue
    return out


def create_profile(name, copy_settings_from: str | None = None) -> str:
    """Neues, leeres Profil anlegen (optional mit den Einstellungen eines anderen Profils)."""
    n = clean_name(name)
    if not n:
        raise ValueError("Bitte einen Namen für das neue Profil angeben.")
    d = data_dir(n)
    if os.path.exists(d):
        raise ValueError(f"Profil „{n}“ gibt es schon.")
    os.makedirs(d)
    if copy_settings_from is not None:
        src = config_file(copy_settings_from)
        if os.path.isfile(src):
            with open(src, encoding="utf-8") as fh:
                cfg = json.load(fh)
            for k in ("setup_done", "setup_started", "window", "ui"):          # neues Profil startet frisch (Assistent, Fenster)
                cfg.pop(k, None)
            with open(config_file(n), "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, ensure_ascii=False, indent=1)
    return n


def should_ask() -> bool:
    """Profilwahl beim Start zeigen? Nur ohne ausdrückliches Profil, wenn es mehrere gibt und sie nicht abgeschaltet ist."""
    if _from_argv(sys.argv[1:]) or os.environ.get("TAGSTUDIO_PROFIL") or os.environ.get("TAGSTUDIO_NOASK") or _from_ini():
        return False
    return len(list_profiles()) > 1 and load_registry()["ask"]


init()
