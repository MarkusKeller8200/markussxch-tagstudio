"""Ordner-Rollen (#310, Konzept docs/KONZEPT-ORDNER.md): jeder Ordner wird genau einmal festgelegt.

Einstellung ``cfg["folders"]``::

    {"base": "D:\\TagStudio",
     "roles": {"inbox": {"mode": "base", "sub": "00_New"}, "export": {"mode": "custom", "path": "E:\\Exporte"},
               "snapshots": {"mode": "app"}, …},
     "libraries": [{"id": "main", "name": "Haupt", "mode": "base", "sub": "01_Library", "active": true,
                    "main": true, "snapshots": true}, …],
     "review": [...]}            # nur nach der Übernahme, solange der User noch nicht entschieden hat

Modus je Rolle: ``base`` = Basisordner + Unterordner (Name änderbar), ``custom`` = eigener Ordner,
``app`` = Programmdaten von TagStudio (nur Sicherung und Snapshots – so wie vor 4.10).

Module fragen nur noch :func:`role`, :func:`libraries` und :func:`main_library`. Die alten Einzel-Schlüssel
(``base_dir``, ``archive_dir``, ``playlist_dir``, ``backup_dir``, ``snap_dir``, ``default_tagger``) werden aus dem
Modell nachgeführt (:func:`legacy`) – so arbeiten noch nicht umgestellte Module mit denselben Ordnern, und ein
Downgrade findet seine Einstellungen.

Nur Standardbibliothek; keine Dateien werden hier verschoben oder gelöscht.
"""
from __future__ import annotations

import copy
import os
import re
import uuid

LIB_SUB = "01_Library"
# Rolle → Standard-Unterordner, Bezeichnung, Beschreibung, Programmdaten-Standard möglich
ROLES = [
    {"id": "inbox", "sub": "00_New", "label": "Eingang",
     "desc": "Neue Musik, unverändert – mit Unterordner je Quelle"},
    {"id": "archive", "sub": "02_Archiv", "label": "Archiv",
     "desc": "Aussortierte Titel (Tagger, Vorbereiten)"},
    {"id": "playlists", "sub": "03_Playlists", "label": "Playlists",
     "desc": "Alle Playlists als M3U8 für DJ-Programme"},
    {"id": "export", "sub": "04_Export", "label": "Export",
     "desc": "Startordner aller „Exportieren …“"},
    {"id": "downloads", "sub": "90_Download", "label": "Downloads",
     "desc": "Downloads aus Browser und Stores – mit Unterordner je Quelle"},
    {"id": "work", "sub": "91_Work", "label": "Arbeit",
     "desc": "Stufen-Ordner der Workflow-Schritte"},
    {"id": "backup", "sub": "99_Sicherung/Tags", "label": "Sicherung", "app": True,
     "desc": "Tag-Sicherungen vor dem Speichern (wenn nicht im Snapshot-Speicher)"},
    {"id": "snapshots", "sub": "99_Sicherung/Snapshots", "label": "Snapshots", "app": True,
     "desc": "Snapshot-Speicher"},
]
ROLE_IDS = [r["id"] for r in ROLES]
MODES = ("base", "custom", "app")


def _spec(rid: str) -> dict:
    for r in ROLES:
        if r["id"] == rid:
            return r
    raise ValueError(f"Unbekannte Ordner-Rolle: {rid}")


# ---------------------------------------------------------------------------- Pfade
def clean_path(p) -> str:
    s = str(p or "").strip().strip('"')
    return os.path.normpath(os.path.abspath(os.path.expanduser(s))) if s else ""


def clean_sub(name, default: str = "") -> str:
    """Unterordnername unter dem Basisordner: ohne verbotene Zeichen, ohne „..“, Trennzeichen erlaubt."""
    parts = []
    for part in re.split(r"[\\/]+", str(name or "")):
        part = re.sub(r'[<>:"|?*\x00-\x1f]', "", part).strip().rstrip(".")
        if part and part not in (".", ".."):
            parts.append(part)
    return "/".join(parts) or default


def _join(base: str, sub: str) -> str:
    return os.path.normpath(os.path.join(base, *sub.split("/"))) if base and sub else ""


def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(p))) if p else ""


def same_dir(a: str, b: str) -> bool:
    """Gleicher Ordner – auch über einen anderen Weg (Laufwerksbuchstabe/Netzlaufwerk, Verknüpfung)."""
    if not a or not b:
        return False
    if _norm(a) == _norm(b):
        return True
    try:
        if _norm(os.path.realpath(a)) == _norm(os.path.realpath(b)):
            return True
        return os.path.isdir(a) and os.path.isdir(b) and os.path.samefile(a, b)
    except OSError:
        return False


def inside(child: str, parent: str) -> bool:
    """child liegt (echt) in parent."""
    if not child or not parent or same_dir(child, parent):
        return False
    c, p = _norm(child), _norm(parent)
    try:
        if os.path.commonpath([c, p]) == p:
            return True
        rc, rp = _norm(os.path.realpath(child)), _norm(os.path.realpath(parent))
        return rc != rp and os.path.commonpath([rc, rp]) == rp
    except ValueError:                                  # verschiedene Laufwerke
        return False


def reachable(p: str) -> bool:
    """Laufwerk / Freigabe / Volume vorhanden (der Ordner selbst darf fehlen)."""
    if not p:
        return False
    anchor = os.path.splitdrive(p)[0]
    if anchor:
        return os.path.isdir(anchor + os.sep)
    parts = os.path.normpath(p).split(os.sep)
    if len(parts) > 2 and parts[1] in ("Volumes", "media", "mnt"):        # macOS/Linux: externes Volume
        return os.path.isdir(os.sep.join(parts[:3]))
    return True


# ---------------------------------------------------------------------------- Modell
def empty() -> dict:
    return {"base": "", "roles": {r["id"]: {"mode": "base", "sub": r["sub"]} for r in ROLES}, "libraries": []}


def normalize(m) -> dict:
    """Fehlende Rollen ergänzen, unbekannte Werte bereinigen (alte/neue Versionen lesen dieselbe Einstellung)."""
    m = copy.deepcopy(m) if isinstance(m, dict) else {}
    out = {"base": clean_path(m.get("base")), "roles": {}, "libraries": []}
    roles = m.get("roles") if isinstance(m.get("roles"), dict) else {}
    for r in ROLES:
        e = roles.get(r["id"]) if isinstance(roles.get(r["id"]), dict) else {}
        mode = e.get("mode") if e.get("mode") in MODES else "base"
        if mode == "app" and not r.get("app"):
            mode = "base"
        x = {"mode": mode, "sub": clean_sub(e.get("sub"), r["sub"])}
        if mode == "custom":
            x["path"] = clean_path(e.get("path"))
        for k in ("sync",):                              # später (Cloud Weg 2) – unverändert mitführen
            if k in e:
                x[k] = e[k]
        out["roles"][r["id"]] = x
    seen = set()
    for e in m.get("libraries") or []:
        if not isinstance(e, dict):
            continue
        lid = re.sub(r"[^\w-]", "", str(e.get("id") or "")) or uuid.uuid4().hex[:8]
        if lid in seen:
            lid = uuid.uuid4().hex[:8]
        seen.add(lid)
        mode = "custom" if e.get("mode") == "custom" else "base"
        lib = {"id": lid, "name": str(e.get("name") or "").strip()[:60] or "Bibliothek", "mode": mode,
               "sub": clean_sub(e.get("sub"), LIB_SUB), "active": e.get("active", True) is not False,
               "main": bool(e.get("main")), "snapshots": bool(e.get("snapshots", e.get("main")))}
        if mode == "custom":
            lib["path"] = clean_path(e.get("path"))
        out["libraries"].append(lib)
    mains = [x for x in out["libraries"] if x["main"]]
    for x in mains[1:]:
        x["main"] = False
    if out["libraries"] and not mains:
        out["libraries"][0]["main"] = True
    if m.get("review"):
        out["review"] = list(m["review"])
    return out


def _app_dir(rid: str) -> str:
    if rid == "snapshots":
        import snapshots
        return snapshots.default_dir()
    if rid == "backup":
        import backup
        return backup.default_dir()
    return ""


def resolve_role(m: dict, rid: str) -> str:
    e = m["roles"][rid]
    if e["mode"] == "custom":
        return e.get("path", "")
    if e["mode"] == "app":
        return _app_dir(rid)
    return _join(m["base"], e["sub"])


def resolve_lib(m: dict, lib: dict) -> str:
    return lib.get("path", "") if lib["mode"] == "custom" else _join(m["base"], lib["sub"])


def model(cfg: dict) -> dict:
    return normalize(cfg.get("folders"))


def role(cfg: dict, rid: str) -> str:
    """Pfad einer Rolle ("" = nicht festgelegt)."""
    _spec(rid)
    return resolve_role(model(cfg), rid)


def libraries(cfg: dict, active: bool | None = None) -> list[dict]:
    """Bibliotheken mit aufgelöstem Pfad; active=True nur die eingeschalteten."""
    m = model(cfg)
    out = []
    for lib in m["libraries"]:
        if active is not None and lib["active"] != active:
            continue
        out.append({**lib, "path": resolve_lib(m, lib)})
    return out


def main_library(cfg: dict) -> str:
    for lib in libraries(cfg):
        if lib["main"]:
            return lib["path"]
    return ""


# ---------------------------------------------------------------------------- Ändern (nur Einstellung)
def set_base(m: dict, path) -> dict:
    m = normalize(m)
    m["base"] = clean_path(path)
    return m


def set_role(m: dict, rid: str, mode: str, value="") -> dict:
    """mode base: value = Unterordnername; custom: value = Pfad; app: Programmdaten."""
    spec = _spec(rid)
    m = normalize(m)
    if mode not in MODES or (mode == "app" and not spec.get("app")):
        raise ValueError("Modus base, custom oder app erwartet")
    e = m["roles"][rid]
    e["mode"] = mode
    if mode == "base":
        e["sub"] = clean_sub(value, e.get("sub") or spec["sub"])
        e.pop("path", None)
    elif mode == "custom":
        p = clean_path(value)
        if not p:
            raise ValueError("Bitte einen Ordner wählen.")
        e["path"] = p
    else:
        e.pop("path", None)
    return m


def note_path(m: dict, rid: str, path) -> dict:
    """Ein Pfad wurde an anderer Stelle gesetzt (alte Einstellungsfelder): Rolle passend nachführen –
    Modus Basis, wenn er Basis + Unterordner entspricht, sonst eigener Ordner."""
    m = normalize(m)
    p = clean_path(path)
    spec = _spec(rid)
    e = m["roles"][rid]
    if not p:
        if spec.get("app"):
            m["roles"][rid] = {"mode": "app", "sub": e["sub"]}
        else:
            m["roles"][rid] = {"mode": "custom", "sub": e["sub"], "path": ""}
        return m
    if spec.get("app") and same_dir(p, _app_dir(rid)):
        m["roles"][rid] = {"mode": "app", "sub": e["sub"]}
    elif m["base"] and same_dir(p, _join(m["base"], e["sub"])):
        m["roles"][rid] = {"mode": "base", "sub": e["sub"]}
    elif m["base"] and same_dir(p, _join(m["base"], spec["sub"])):
        m["roles"][rid] = {"mode": "base", "sub": spec["sub"]}
    else:
        m["roles"][rid] = {"mode": "custom", "sub": e["sub"], "path": p}
    return m


def lib_add(m: dict, name: str, mode: str, value="", active=True) -> tuple[dict, dict]:
    m = normalize(m)
    lib = {"id": uuid.uuid4().hex[:8], "name": str(name or "").strip()[:60] or "Bibliothek",
           "mode": "custom" if mode == "custom" else "base", "sub": LIB_SUB, "active": bool(active),
           "main": not m["libraries"], "snapshots": not m["libraries"]}
    if lib["mode"] == "custom":
        lib["path"] = clean_path(value)
        if not lib["path"]:
            raise ValueError("Bitte einen Ordner wählen.")
    else:
        lib["sub"] = clean_sub(value, LIB_SUB)
    p = resolve_lib(m, lib)
    for x in m["libraries"]:
        if same_dir(resolve_lib(m, x), p):
            raise ValueError(f"Diesen Ordner gibt es schon als Bibliothek „{x['name']}“.")
    m["libraries"].append(lib)
    return normalize(m), lib


def lib_update(m: dict, lid: str, **kw) -> dict:
    m = normalize(m)
    lib = next((x for x in m["libraries"] if x["id"] == lid), None)
    if lib is None:
        raise ValueError("Bibliothek nicht gefunden.")
    if kw.get("name") is not None:
        lib["name"] = str(kw["name"]).strip()[:60] or lib["name"]
    if kw.get("mode") in ("base", "custom"):
        lib["mode"] = kw["mode"]
        if kw["mode"] == "custom":
            lib["path"] = clean_path(kw.get("value"))
            if not lib["path"]:
                raise ValueError("Bitte einen Ordner wählen.")
        else:
            lib["sub"] = clean_sub(kw.get("value"), lib.get("sub") or LIB_SUB)
            lib.pop("path", None)
    if kw.get("active") is not None:
        lib["active"] = bool(kw["active"])
    if kw.get("snapshots") is not None:
        lib["snapshots"] = bool(kw["snapshots"])
    if kw.get("main"):
        for x in m["libraries"]:
            x["main"] = x is lib
        lib["active"] = True
    if lib["main"] and not lib["active"]:
        raise ValueError("Die Hauptbibliothek ist immer aktiv – zuerst eine andere als Hauptbibliothek wählen.")
    return normalize(m)


def lib_remove(m: dict, lid: str) -> dict:
    """Nur den Eintrag entfernen – die Dateien bleiben unberührt."""
    m = normalize(m)
    m["libraries"] = [x for x in m["libraries"] if x["id"] != lid]
    return normalize(m)


# ---------------------------------------------------------------------------- Hinweise
def status(m: dict) -> dict:
    """Pfad, vorhanden, erreichbar und Hinweise je Rolle und Bibliothek."""
    libs = [(x, resolve_lib(m, x)) for x in m["libraries"]]
    out = {"roles": {}, "libraries": {}}

    def info(p):
        return {"path": p, "exists": bool(p) and os.path.isdir(p), "reachable": reachable(p)}

    for r in ROLES:
        p = resolve_role(m, r["id"])
        d = info(p)
        hints = []
        if not p:
            hints.append("nicht festgelegt" if m["roles"][r["id"]]["mode"] != "base" else "kein Basisordner")
        elif not d["reachable"]:
            hints.append("nicht erreichbar")
        elif not d["exists"]:
            hints.append("fehlt – anlegen?")
        for lib, lp in libs:
            if p and lp and (same_dir(p, lp) or inside(p, lp)):
                hints.append(f"liegt in Bibliothek „{lib['name']}“")
        d["hints"] = hints
        out["roles"][r["id"]] = d
    for lib, p in libs:
        d = info(p)
        hints = []
        if not p:
            hints.append("kein Basisordner" if lib["mode"] == "base" else "nicht festgelegt")
        elif not d["reachable"]:
            hints.append("nicht erreichbar")
        elif not d["exists"]:
            hints.append("fehlt – anlegen?")
        for other, op in libs:
            if other is lib or not p or not op:
                continue
            if same_dir(p, op):
                hints.append(f"gleicher Ordner wie „{other['name']}“")
            elif inside(p, op):
                hints.append(f"ist in „{other['name']}“ enthalten")
        d["hints"] = hints
        out["libraries"][lib["id"]] = d
    return out


# ---------------------------------------------------------------------------- Übernahme (einmalig)
def _base_or_custom(m: dict, rid: str, path: str):
    m["roles"][rid] = note_path(m, rid, path)["roles"][rid]


def migrate(cfg: dict, workflows=None, current=None, snap_libs=None, beatport_dest="") -> dict:
    """Heutige Einstellungen ins Rollen-Modell übernehmen. Bibliotheks-Kandidaten werden zusammengefasst (gleicher
    Ordner, auch über anderen Weg); sind es mehrere verschiedene, steht die Liste in ``review`` – nichts wird still
    verworfen. Rückgabe: normalisiertes Modell."""
    m = empty()
    m["base"] = clean_path(cfg.get("base_dir"))
    wfs = [w for w in workflows or [] if isinstance(w, dict)]
    cur = next((w for w in wfs if w.get("id") == current), wfs[0] if wfs else {})

    # Rollen
    if cfg.get("archive_dir") or not m["base"]:
        _base_or_custom(m, "archive", cfg.get("archive_dir") or "")
    if cfg.get("playlist_dir"):
        _base_or_custom(m, "playlists", cfg["playlist_dir"])
    elif not m["base"]:
        m["roles"]["playlists"] = {"mode": "custom", "sub": _spec("playlists")["sub"], "path": ""}
    if not m["base"]:
        m["roles"]["export"] = {"mode": "custom", "sub": _spec("export")["sub"], "path": ""}
    _base_or_custom(m, "backup", cfg.get("backup_dir") or "")
    _base_or_custom(m, "snapshots", cfg.get("snap_dir") or "")
    dl = beatport_dest or next((q.get("folder") for q in cur.get("sources") or [] if q.get("folder")), "")
    for rid, p in (("inbox", cur.get("inbox") or ""), ("work", cur.get("work") or ""), ("downloads", dl)):
        std = _join(m["base"], _spec(rid)["sub"])
        if rid in ("inbox", "downloads") and p and inside(p, std):   # Unterordner je Quelle (O5)
            continue
        if p or not m["base"]:                           # leer + Basisordner: Standard „Basis“ bleibt
            _base_or_custom(m, rid, p)

    # Bibliotheks-Kandidaten
    cands: list[dict] = []

    def add(p, why):
        p = clean_path(p)
        if not p:
            return
        for c in cands:
            if same_dir(c["path"], p):
                if why not in c["found"]:
                    c["found"].append(why)
                return
        cands.append({"path": p, "found": [why]})

    add(cfg.get("default_tagger"), "Tagger-Standardordner")
    for w in wfs:
        add(w.get("library"), f"Workflow „{w.get('name') or 'Vorbereiten'}“")
    if m["base"] and os.path.isdir(_join(m["base"], LIB_SUB)):
        add(_join(m["base"], LIB_SUB), "Basisordner + 01_Library")
    for lib in snap_libs or []:
        add(lib.get("root"), "Snapshots")
    add(cfg.get("help_scan_root"), "Hilfe › Scan")

    for i, c in enumerate(cands):
        lib = {"id": "main" if i == 0 else uuid.uuid4().hex[:8],
               "name": "Haupt" if i == 0 else (os.path.basename(c["path"].rstrip("\\/")) or c["path"]),
               "active": True, "main": i == 0,
               "snapshots": any(f == "Snapshots" for f in c["found"]) or i == 0}
        if m["base"] and same_dir(c["path"], _join(m["base"], LIB_SUB)):
            lib.update(mode="base", sub=LIB_SUB)
        else:
            lib.update(mode="custom", sub=LIB_SUB, path=c["path"])
        m["libraries"].append(lib)
        c["id"] = lib["id"]
    if not cands and m["base"]:
        m["libraries"].append({"id": "main", "name": "Haupt", "mode": "base", "sub": LIB_SUB, "active": True,
                               "main": True, "snapshots": True})
    if len(cands) > 1:
        m["review"] = cands
    return normalize(m)


def review_apply(m: dict, items) -> dict:
    """Entscheid zur Übersicht „Diese Ordner haben wir gefunden“: items = [{"id", "keep", "active"}], main = id."""
    m = normalize(m)
    items = items or {}
    rows = {str(x.get("id")): x for x in items.get("items") or [] if isinstance(x, dict)}
    keep = []
    for lib in m["libraries"]:
        d = rows.get(lib["id"])
        if d is not None and not d.get("keep", True):
            continue
        if d is not None and d.get("active") is not None:
            lib["active"] = bool(d["active"])
        keep.append(lib)
    if not keep:
        raise ValueError("Mindestens eine Bibliothek behalten.")
    main = str(items.get("main") or "")
    if main and any(x["id"] == main for x in keep):
        for x in keep:
            x["main"] = x["id"] == main
    m["libraries"] = keep
    m.pop("review", None)
    m = normalize(m)
    for x in m["libraries"]:
        if x["main"]:
            x["active"] = True
    return m


# ---------------------------------------------------------------------------- Alte Schlüssel
def legacy(m: dict) -> dict:
    """Werte der alten Einzel-Einstellungen aus dem Modell (für noch nicht umgestellte Module und Downgrade)."""
    m = normalize(m)
    out = {"base_dir": m["base"], "archive_dir": resolve_role(m, "archive")}
    out["playlist_dir"] = resolve_role(m, "playlists")
    out["backup_dir"] = "" if m["roles"]["backup"]["mode"] == "app" else resolve_role(m, "backup")
    out["snap_dir"] = "" if m["roles"]["snapshots"]["mode"] == "app" else resolve_role(m, "snapshots")
    main = next((resolve_lib(m, x) for x in m["libraries"] if x["main"]), "")
    if main:
        out["default_tagger"] = main
    return out


def structure(m: dict) -> list[dict]:
    """Ordner, die „Struktur anlegen …“ unter dem Basisordner anlegt (Rollen im Modus Basis + Bibliotheken)."""
    out = []
    for r in ROLES:
        e = m["roles"][r["id"]]
        if e["mode"] == "base":
            out.append({"id": r["id"], "label": r["label"], "sub": e["sub"]})
    for lib in m["libraries"]:
        if lib["mode"] == "base":
            out.append({"id": "lib:" + lib["id"], "label": lib["name"], "sub": lib["sub"]})
    return out


_STRUCT_KEYS = {"new": "inbox", "archive": "archive", "playlists": "playlists", "export": "export",
                "download": "downloads", "work": "work"}


def structure_model(m: dict, base: str, paths: dict, keep_snapshots: bool = False) -> dict:
    """„Struktur anlegen“ bzw. Assistent: alle Rollen auf „Basis“ unter base (Namen aus paths: id → Pfad wie in
    session_setup.STRUCTURE), Bibliothek als Hauptbibliothek. keep_snapshots: Snapshot-Rolle unverändert lassen
    (der bisherige Speicher enthält schon Snapshots)."""
    m = set_base(m, base)

    def sub(p):
        return clean_sub(os.path.relpath(p, m["base"]).replace(os.sep, "/"))

    for k, rid in _STRUCT_KEYS.items():
        if paths.get(k):
            m["roles"][rid] = {"mode": "base", "sub": sub(paths[k])}
    if paths.get("backup"):
        b = sub(paths["backup"])
        m["roles"]["backup"] = {"mode": "base", "sub": b + "/Tags"}
        if not keep_snapshots:
            m["roles"]["snapshots"] = {"mode": "base", "sub": b + "/Snapshots"}
    if paths.get("library"):
        s = sub(paths["library"])
        lib = next((x for x in m["libraries"] if same_dir(resolve_lib(m, x), paths["library"])), None)
        if lib is None:
            lib = {"id": "main" if not any(x["id"] == "main" for x in m["libraries"]) else uuid.uuid4().hex[:8],
                   "name": "Haupt" if not m["libraries"] else "Bibliothek", "active": True, "snapshots": True}
            m["libraries"].append(lib)
        lib.update(mode="base", sub=s, active=True)
        lib.pop("path", None)
        for x in m["libraries"]:
            x["main"] = x is lib
    return normalize(m)
