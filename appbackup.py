"""MarKusSXCH TagStudio – Sicherung der Programmdaten in einen Ordner, z. B. den OneDrive-Ordner (#402).

Eine ZIP-Datei je Sicherung ``TagStudio-Programmdaten_<Rechner>_<JJJJ-MM-TT_HHMM>.zip`` mit ``manifest.json``
(Version, Rechner, Zeit, Bibliotheken, SHA-256 je Datei). Erst als ``.part`` geschrieben, dann umbenannt – der
Cloud-Client lädt nie eine halbe Datei hoch.

Enthalten: Einstellungen ohne Zugangsdaten, Playlists-Speicher (mit Ideen/Wunschlisten), Einkäufe, Entdecken (ohne
SonoVault-Einträge – Nutzungsbedingungen), Vorbereiten, Mixe. **Nie:** Zugangsdaten/Token (Schlüsselablage der
Plugins), Caches, Snapshots, Plugin-Umgebungen, Protokolle, Musik.

Wiederherstellen: Vorschau (was ersetzt wird), vorher automatische Sicherung des jetzigen Stands, dann Übernahme; Pfade
auf Musikdateien werden über die Bibliotheken (gleiche ID) auf diesen Rechner umgeschrieben. Dateien, die es nur hier
gibt, bleiben erhalten. Nur Standardbibliothek.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import time
import zipfile

import paths

FORMAT = "tagstudio-appbackup"
PREFIX = "TagStudio-Programmdaten_"
KEEP_DEFAULT = 10
MAX_ZIP = 512 * 1024 * 1024                 # Schutz beim Öffnen fremder Dateien
MODES = ("off", "exit", "daily")
DEFAULT_SUB = os.path.join("TagStudio", "Sicherungen")

# Teile: (ID, Bezeichnung, Unterordner im Datenordner, erlaubte Endungen)
PARTS = [("settings", "Einstellungen (ohne Zugangsdaten)", None, None),
         ("playlists", "Playlists, Ideen und Wunschlisten", "Playlists", (".json", ".m3u8")),
         ("purchases", "Einkäufe", "Käufe", (".json", ".csv")),
         ("discover", "Entdecken (ohne SonoVault)", "Entdecken", (".json",)),
         ("prepare", "Vorbereiten (Workflows, Stand)", "Vorbereiten", (".json",)),
         ("mixes", "Mixe (Analysen)", "Mixe", (".json", ".cue", ".txt", ".m3u8"))]
PART_IDS = tuple(p[0] for p in PARTS)
SETTINGS_NAME = "einstellungen.json"


def clean_cfg(c) -> dict:
    c = c if isinstance(c, dict) else {}
    try:
        keep = max(1, min(100, int(c.get("keep", KEEP_DEFAULT))))
    except (TypeError, ValueError):
        keep = KEEP_DEFAULT
    return {"folder": str(c.get("folder") or "").strip(), "auto": c.get("auto") if c.get("auto") in MODES else "off",
            "keep": keep}


def host() -> str:
    n = re.sub(r"[^\w-]+", "-", platform.node() or "Rechner").strip("-")
    return n[:40] or "Rechner"


def _part(pid: str):
    import cloudsync
    for p_id, label, sub, exts in PARTS:
        if p_id != pid or sub is None:
            continue
        if pid == "discover":
            return cloudsync.DiscoverPart(paths.sub(sub))
        return cloudsync.FolderPart(pid, label, paths.sub(sub), exts=exts)
    return None


def collect(version: str) -> dict:
    """{"<teil>/<rel>": bytes} – alles, was in eine Sicherung gehört (ohne Zugangsdaten)."""
    import appsettings
    out = {f"settings/{SETTINGS_NAME}": appsettings.export_text(version).encode("utf-8")}
    for pid in PART_IDS:
        part = _part(pid)
        if part is None:
            continue
        for rel, data in part.files().items():
            out[f"{pid}/{rel}"] = data
    return out


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def create(folder: str, version: str, libraries: list[dict] | None = None, note: str = "") -> dict:
    """Sicherung anlegen → {"path", "size", "files", "name"}."""
    if not folder:
        raise ValueError("Kein Ordner für die Sicherung angegeben.")
    os.makedirs(folder, exist_ok=True)
    files = collect(version)
    stamp = time.strftime("%Y-%m-%d_%H%M%S")
    name = f"{PREFIX}{host()}_{stamp}{('_' + re.sub(r'[^\w-]+', '-', note)) if note else ''}.zip"
    dest = os.path.join(folder, name)
    k = 1
    while os.path.exists(dest):                       # zwei Sicherungen in derselben Sekunde
        k += 1
        dest = os.path.join(folder, name[:-4] + f"-{k}.zip")
    name = os.path.basename(dest)
    manifest = {"format": FORMAT, "format_version": 1, "app_version": version, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "host": host(), "platform": sys.platform, "profile": paths.profile_label(), "note": note,
                "libraries": [{"id": x.get("id"), "name": x.get("name"), "path": x.get("path")} for x in libraries or []],
                "files": {k: {"sha256": _sha(v), "size": len(v)} for k, v in sorted(files.items())}}
    tmp = dest + ".part"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
            for k, v in sorted(files.items()):
                z.writestr(k, v)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return {"path": dest, "name": name, "size": os.path.getsize(dest), "files": len(files)}


def listing(folder: str) -> list[dict]:
    """Sicherungen im Ordner (neueste zuerst) – liest nur Namen und Grösse; „nur online“ wird nicht geöffnet."""
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for n in names:
        if not (n.startswith(PREFIX) and n.lower().endswith(".zip")):
            continue
        p = os.path.join(folder, n)
        try:
            st = os.stat(p)
        except OSError:
            continue
        m = re.match(re.escape(PREFIX) + r"(.+?)_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})(\d{2})?", n)
        try:
            import cloud
            online = cloud.online_only(p, st)
        except Exception:  # noqa: BLE001
            online = False
        out.append({"path": p, "name": n, "size": st.st_size, "mtime": st.st_mtime, "online_only": bool(online),
                    "host": m.group(1) if m else "", "date": f"{m.group(2)} {m.group(3)}:{m.group(4)}" if m else ""})
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out


def surplus(folder: str, keep: int) -> list[dict]:
    """Sicherungen über der Anzahl „behalten“ (älteste) – gelöscht wird nur nach Rückfrage."""
    return listing(folder)[keep:]


def delete(paths_: list[str], folder: str) -> dict:
    ok, errors = 0, []
    root = os.path.normcase(os.path.abspath(folder))
    for p in paths_:
        ap = os.path.abspath(p)
        if os.path.normcase(os.path.dirname(ap)) != root or not os.path.basename(ap).startswith(PREFIX) \
                or not ap.lower().endswith(".zip"):
            errors.append(f"{p}: keine Sicherung in diesem Ordner")
            continue
        try:
            os.remove(ap)
            ok += 1
        except FileNotFoundError:
            ok += 1
        except OSError as ex:
            errors.append(f"{p}: {ex}")
    return {"deleted": ok, "errors": errors}


def read(path: str) -> tuple[dict, dict]:
    """→ (manifest, {name: bytes}); prüft Format, Grösse und Prüfsummen."""
    if os.path.getsize(path) > MAX_ZIP:
        raise ValueError("Datei ist zu gross für eine Sicherung der Programmdaten.")
    with zipfile.ZipFile(path) as z:
        try:
            man = json.loads(z.read("manifest.json").decode("utf-8"))
        except (KeyError, ValueError) as ex:
            raise ValueError("Das ist keine TagStudio-Sicherung der Programmdaten.") from ex
        if not isinstance(man, dict) or man.get("format") != FORMAT:
            raise ValueError("Das ist keine TagStudio-Sicherung der Programmdaten.")
        files = {}
        for name, info in (man.get("files") or {}).items():
            pid, _, rel = name.partition("/")
            if pid not in PART_IDS or not rel or ".." in rel.split("/") or rel.startswith("/"):
                continue
            data = z.read(name)
            if _sha(data) != (info or {}).get("sha256"):
                raise ValueError(f"Prüfsumme stimmt nicht: {name} – Sicherung beschädigt?")
            files[name] = data
    return man, files


def current_files() -> dict:
    """Heutiger Stand im selben Format wie collect (ohne Einstellungen) – für die Vorschau."""
    out = {}
    for pid in PART_IDS:
        part = _part(pid)
        if part is None:
            continue
        for rel, data in part.files().items():
            out[f"{pid}/{rel}"] = data
    return out


def preview(path: str) -> dict:
    import appsettings
    man, files = read(path)
    cur = current_files()
    parts = []
    for pid, label, _sub, _e in PARTS:
        names = [n for n in files if n.startswith(pid + "/")]
        if pid == "settings":
            st = appsettings.import_preview(files[f"settings/{SETTINGS_NAME}"].decode("utf-8")) if names else None
            parts.append({"id": pid, "label": label, "files": len(names), "settings": st})
            continue
        mine = [n for n in cur if n.startswith(pid + "/")]
        changed = sum(1 for n in names if n in cur and cur[n] != files[n])
        new = sum(1 for n in names if n not in cur)
        only_here = sum(1 for n in mine if n not in files)
        parts.append({"id": pid, "label": label, "files": len(names), "changed": changed, "new": new,
                      "same": len(names) - changed - new, "only_here": only_here})
    return {"manifest": {k: man.get(k) for k in ("app_version", "created", "host", "platform", "profile", "note")},
            "libraries": man.get("libraries") or [], "foreign": man.get("host") != host() or man.get("platform") != sys.platform,
            "parts": parts}


def path_mapper(src_libs: list[dict], dst_libs: list[dict]):
    """Pfade der Bibliotheken des anderen Rechners (gleiche ID, sonst gleicher Name) auf diesen Rechner umschreiben –
    unabhängig vom Trennzeichen (Windows ↔ macOS)."""
    pairs = []
    by_id = {x.get("id"): x for x in dst_libs}
    by_name = {str(x.get("name") or "").lower(): x for x in dst_libs}
    for s in src_libs or []:
        d = by_id.get(s.get("id")) or by_name.get(str(s.get("name") or "").lower())
        if d and s.get("path") and d.get("path"):
            old = str(s["path"]).replace("\\", "/").rstrip("/")
            if old.replace("/", os.sep) != str(d["path"]).rstrip(os.sep):
                pairs.append((old, d["path"]))
    pairs.sort(key=lambda x: -len(x[0]))

    def rb(p):
        if not isinstance(p, str) or not p:
            return p
        q = p.replace("\\", "/")
        for old, new in pairs:
            if q.lower() == old.lower() or q.lower().startswith(old.lower() + "/"):
                rest = q[len(old):].lstrip("/")
                return os.path.join(new, *rest.split("/")) if rest else new
        return p
    return rb, pairs


def restore_files(files: dict, parts: list[str]) -> dict:
    """Dateien der gewählten Teile (ohne Einstellungen) zurückschreiben (atomar). → Anzahl je Teil"""
    out = {}
    for pid in parts:
        if pid == "settings":
            continue
        part = _part(pid)
        if part is None:
            continue
        n = 0
        for name, data in files.items():
            if name.startswith(pid + "/"):
                part.write(name[len(pid) + 1:], data)
                n += 1
        out[pid] = n
    return out


def settings_text(files: dict) -> str:
    b = files.get(f"settings/{SETTINGS_NAME}")
    return b.decode("utf-8") if b else ""


def size_of(folder: str, keep: int) -> int:
    """Platz der Sicherungen (für die Schätzung beim Spiegel): vorhandene, sonst eine geschätzte × keep."""
    lst = listing(folder) if folder else []
    if lst:
        avg = sum(x["size"] for x in lst) / len(lst)
        return int(avg * keep)
    try:
        est = sum(len(v) for v in collect("0").values()) // 3          # ZIP verdichtet JSON etwa um den Faktor 3
    except Exception:  # noqa: BLE001
        est = 0
    return int(est * keep)

