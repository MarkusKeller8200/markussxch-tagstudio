"""MarKusSXCH TagStudio – Einstellungen sichern, übertragen und zurücksetzen.

Alle Einstellungen beider Oberflächen liegen in ~/.tagstudio.json. Dieses Modul teilt die Schlüssel in Gruppen
ein, exportiert sie als Datei (ohne Geheimnisse), liest einen Export wieder ein und setzt Gruppen zurück.
Vor jedem Import/Zurücksetzen wird die bisherige Datei nach ~/TagStudio/Einstellungen gesichert.
Nur Standardbibliothek.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

import core

GROUPS = [
    ("design", "Design und Tonart-Schreibweise", ("web_theme", "theme", "key_notation")),
    ("layout", "Layout (Splitter, Seitenleiste, Fenster)", ("web_ui", "geometry", "features_open")),
    ("view", "Ansicht und Filter", ("filter", "show_trivial", "empty_set", "show_covers", "mode", "recursive",
                                    "tagger_recursive", "tagger_stems_flat")),
    ("history", "Pfad-Verlauf, Muster und Tag-Fixer", ("hist_left", "hist_right", "hist_tagger", "tagger_patterns",
                                                        "fixer")),
    ("trivial", "Unwichtige Felder", ("trivial", "trivial_known")),
    ("saving", "Speichern und Sicherungen", ("backup_enabled", "backup_dir", "save_version")),
    ("player", "Player (Vorschau und externe)", ("player", "players")),
    ("origin", "Herkunft der Tags (eigene Zuordnungen)", ("tag_origins", "origin_std_badge")),
    ("plugins", "Plugins (an/aus, Optionen)", ("plugins_enabled", "plugin_options", "plugin_settings")),
]
GROUP_IDS = [g[0] for g in GROUPS]
# Pfade passen meist nicht auf einen anderen Rechner → beim Import von einem anderen System nicht vorgewählt
MACHINE_GROUPS = ("history", "saving", "player")
HIDDEN_KEYS = re.compile(r"token|passw|secret|cookie|session|credential|api[_-]?key|auth", re.I)
FORMAT = "tagstudio-settings"
BACKUP_DIR = os.path.join(os.path.expanduser("~"), "TagStudio", "Einstellungen")
KEEP_BACKUPS = 20


def group_of(key: str) -> str:
    for gid, _label, keys in GROUPS:
        if key in keys:
            return gid
    return "other"


def shareable(obj):
    """Schlüssel, die nach Zugangsdaten aussehen, entfernen (rekursiv)."""
    if isinstance(obj, dict):
        return {k: shareable(v) for k, v in obj.items() if not HIDDEN_KEYS.search(str(k))}
    if isinstance(obj, list):
        return [shareable(v) for v in obj]
    return obj


def read_file() -> dict:
    return core.load_config()


def write_file(cfg: dict) -> None:
    os.makedirs(os.path.dirname(core.CONFIG) or ".", exist_ok=True)
    tmp = core.CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, core.CONFIG)


def backup_current(reason: str) -> str | None:
    """Bisherige Einstellungsdatei sichern → Pfad der Kopie (oder None, wenn es keine gibt)."""
    cfg = read_file()
    if not cfg:
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"tagstudio-{stamp}-{reason}.json")
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(BACKUP_DIR, f"tagstudio-{stamp}-{reason}-{n}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    old = sorted((f for f in os.listdir(BACKUP_DIR) if f.startswith("tagstudio-") and f.endswith(".json")),
                 reverse=True)
    for f in old[KEEP_BACKUPS:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
        except OSError:
            pass
    return path


# --------------------------------------------------------------------------- Export / Import
def export_data(version: str) -> dict:
    return {"format": FORMAT, "format_version": 1, "app_version": version, "platform": sys.platform,
            "exported": datetime.datetime.now().isoformat(timespec="seconds"),
            "settings": shareable(read_file())}


def export_text(version: str) -> str:
    return json.dumps(export_data(version), indent=2, ensure_ascii=False)


def _load_export(text: str) -> dict:
    if len(text) > 4_000_000:
        raise ValueError("Datei ist zu groß für eine Einstellungsdatei.")
    try:
        data = json.loads(text)
    except ValueError as ex:
        raise ValueError(f"Datei kann nicht gelesen werden: {ex}") from ex
    if isinstance(data, dict) and data.get("format") == FORMAT and isinstance(data.get("settings"), dict):
        return data
    if isinstance(data, dict) and any(k in data for g in GROUPS for k in g[2]):   # rohe .tagstudio.json
        return {"format": FORMAT, "platform": "", "app_version": "", "exported": "", "settings": data}
    raise ValueError("Das ist keine TagStudio-Einstellungsdatei.")


def import_preview(text: str) -> dict:
    data = _load_export(text)
    cur, new = read_file(), shareable(data["settings"])
    foreign = bool(data.get("platform")) and data["platform"] != sys.platform
    groups = []
    for gid, label, keys in GROUPS + [("other", "Weitere", ())]:
        ks = [k for k in new if group_of(k) == gid]
        if not ks:
            continue
        changed = [k for k in ks if cur.get(k) != new[k]]
        groups.append({"id": gid, "label": label, "keys": ks, "changed": len(changed),
                       "default": bool(changed) and not (foreign and gid in MACHINE_GROUPS)})
    return {"platform": data.get("platform", ""), "app_version": data.get("app_version", ""),
            "exported": data.get("exported", ""), "foreign": foreign, "groups": groups}


def import_apply(text: str, groups: list) -> dict:
    data = _load_export(text)
    new = shareable(data["settings"])
    take = [k for k in new if group_of(k) in set(groups or [])]
    if not take:
        return {"ok": False, "error": "Keine Gruppe gewählt."}
    saved = backup_current("vor-import")
    cfg = read_file()
    for k in take:
        cfg[k] = new[k]
    write_file(cfg)
    return {"ok": True, "keys": len(take), "backup": saved}


# --------------------------------------------------------------------------- Zurücksetzen
def reset(groups) -> dict:
    """groups: Liste von Gruppen-IDs oder „all“."""
    saved = backup_current("vor-zuruecksetzen")
    if groups == "all":
        write_file({})
        return {"ok": True, "keys": -1, "backup": saved}
    keys = {k for gid, _l, ks in GROUPS if gid in set(groups or []) for k in ks}
    cfg = read_file()
    gone = [k for k in list(cfg) if k in keys]
    for k in gone:
        del cfg[k]
    write_file(cfg)
    return {"ok": True, "keys": len(gone), "backup": saved}


def overview() -> dict:
    cfg = read_file()
    return {"path": core.CONFIG, "exists": os.path.exists(core.CONFIG), "backup_dir": BACKUP_DIR,
            "groups": [{"id": g, "label": label, "set": [k for k in keys if k in cfg]} for g, label, keys in GROUPS]}
