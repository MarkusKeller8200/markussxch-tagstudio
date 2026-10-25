"""
plugin_store.py – Plugins einzeln nachladen und aktualisieren (#235).

Der Release-Workflow legt je Plugin ein ZIP und die Übersicht `plugins.json` als Release-Assets ab (`build`).
TagStudio liest den Katalog des neuesten Releases im gewählten Kanal (offiziell bzw. auch Beta – nie den
Entwicklungsstand), zeigt Updates und neue Plugins und installiert sie nach `~/TagStudio/Plugins`. Ein dort
installiertes Plugin überlagert das eingebaute gleicher ID (vorhandenes Verhalten des Plugin-Managers).

Sicherheit: nur Adressen aus den Releases dieses Repos (HTTPS), SHA-256 von GitHub („digest“) und aus dem Katalog
müssen übereinstimmen, ZIP-Inhalt wird vor dem Entpacken geprüft (keine Pfade ausserhalb, keine Links).
Eigene Plugins (ohne Markierungsdatei) werden nie überschrieben oder entfernt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import zipfile

import updater

CATALOG = "plugins.json"
MARKER = ".tagstudio-store.json"       # liegt im nachgeladenen Plugin-Ordner: Herkunft, Version, Prüfsumme
FORMAT = 1
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
_FILE_RE = re.compile(r"^plugin-[a-z0-9][a-z0-9_-]{0,40}-[0-9A-Za-z.]{1,20}\.zip$")
_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_SKIP_DIRS = {"__pycache__"}
_ZIP_TIME = (2020, 1, 1, 0, 0, 0)      # feste Zeit → gleiche Dateien ergeben das gleiche ZIP


# =========================================================================== Versionen
def version_key(v) -> tuple:
    """Plugin-Version „1.10“ → (1, 10); ohne Ziffern → ()."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v or "")))[:4]


def app_base(v: str):
    """App-Version ohne Beta-Anhang: „4.8.0-beta.2“ → (4, 8, 0)."""
    p = updater.parse_version(str(v or ""))
    return p[:3] if p else None


def app_ok(min_app: str, app_version: str) -> bool:
    """Passt das Plugin zur laufenden TagStudio-Version? Ohne Angabe: ja. Betas zählen wie ihre Version."""
    need, have = app_base(min_app), app_base(app_version)
    return need is None or have is None or have >= need


# =========================================================================== Katalog bauen (Release-Workflow)
def plugin_files(src: str) -> list[str]:
    """Dateien eines Plugin-Ordners (relativ, sortiert) ohne Caches und versteckte Dateien."""
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.startswith(".") or f.endswith((".pyc", ".pyo")):
                continue
            out.append(os.path.relpath(os.path.join(root, f), src).replace(os.sep, "/"))
    return out


def zip_name(pid: str, version: str) -> str:
    ver = re.sub(r"[^0-9A-Za-z.]", "", str(version or "")) or "0"
    return f"plugin-{pid}-{ver}.zip"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(plugins_dir: str, out_dir: str, app_version: str) -> dict:
    """Je Plugin ein ZIP (`<id>/…`) und den Katalog `plugins.json` nach `out_dir` schreiben. → Katalog"""
    os.makedirs(out_dir, exist_ok=True)
    entries = []
    for name in sorted(os.listdir(plugins_dir)):
        src = os.path.join(plugins_dir, name)
        mf = os.path.join(src, "plugin.json")
        if name.startswith((".", "_")) or not os.path.isfile(mf):
            continue
        with open(mf, encoding="utf-8") as fh:
            m = json.load(fh)
        pid = str(m.get("id") or name).lower()
        if not _ID_RE.match(pid):
            raise ValueError(f"Ungültige Plugin-ID „{pid}“ in {mf}")
        ver = str(m.get("version") or "0")
        fname = zip_name(pid, ver)
        dst = os.path.join(out_dir, fname)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for rel in plugin_files(src):
                zi = zipfile.ZipInfo(f"{pid}/{rel}", _ZIP_TIME)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                with open(os.path.join(src, rel), "rb") as fh:
                    z.writestr(zi, fh.read())
        env = isinstance(m.get("env"), dict)
        entries.append({"id": pid, "name": str(m.get("name") or pid), "version": ver,
                        "category": str(m.get("category") or "other"), "description": str(m.get("description") or ""),
                        "categories": [str(c) for c in (m.get("categories") or []) if isinstance(c, str)][:6],
                        "min_app": str(m.get("min_app") or ".".join(map(str, app_base(app_version) or ()))),
                        "api": m.get("api", 1), "env": env, "requires": bool(m.get("requires")) and not env,
                        "file": fname, "sha256": _sha256(dst), "size": os.path.getsize(dst)})
    cat = {"format": FORMAT, "app": app_version, "plugins": entries}
    with open(os.path.join(out_dir, CATALOG), "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False, indent=1)
    return cat


# =========================================================================== Katalog lesen
def clean_catalog(data) -> list[dict]:
    """Nur gültige Einträge übernehmen (fremde oder kaputte Angaben werden übersprungen)."""
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("plugins"), list):
        raise ValueError("Der Plugin-Katalog hat ein unbekanntes Format – bitte TagStudio aktualisieren.")
    out = []
    for e in data["plugins"]:
        if not isinstance(e, dict):
            continue
        pid, fn, sha = str(e.get("id") or ""), str(e.get("file") or ""), str(e.get("sha256") or "").lower()
        if not _ID_RE.match(pid) or not _FILE_RE.match(fn) or not _HEX_RE.match(sha):
            continue
        out.append({"id": pid, "name": str(e.get("name") or pid)[:80], "version": str(e.get("version") or "")[:20],
                    "category": str(e.get("category") or "other"), "description": str(e.get("description") or "")[:1500],
                    "categories": [str(c)[:20] for c in (e.get("categories") or []) if isinstance(c, str)][:6],
                    "min_app": str(e.get("min_app") or "")[:20], "env": bool(e.get("env")),
                    "requires": bool(e.get("requires")), "file": fn, "sha256": sha, "size": int(e.get("size") or 0)})
    return out


def catalog_release(releases: list, channel: str):
    """Neuestes Release im Kanal mit Plugin-Katalog („stable“ nur offizielle, „beta“ auch Vorabversionen)."""
    cand = [r for r in releases if (channel == "beta" or not r["beta"])
            and any(a.get("name") == CATALOG for a in r.get("assets", []))]
    return max(cand, key=lambda r: updater.parse_version(r["tag"]), default=None)


def _asset(release: dict, name: str):
    return next((a for a in release.get("assets", []) if a.get("name") == name), None)


def fetch_catalog(channel: str, cache_dir: str, releases=None, opener=None) -> dict:
    """Katalog laden und prüfen. → {"release": {...}, "plugins": [...]} oder {"release": None} ohne Katalog."""
    if channel not in ("stable", "beta"):
        raise ValueError("Plugins werden nur aus veröffentlichten Versionen geladen (Kanal „offiziell“ oder „Beta“).")
    rels = updater.fetch_releases() if releases is None else releases
    rel = catalog_release(rels, channel)
    if rel is None:
        return {"release": None, "plugins": []}
    path = updater.download_asset(_asset(rel, CATALOG), cache_dir, opener=opener)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {"release": {k: rel[k] for k in ("tag", "version", "beta", "url")}, "assets": rel.get("assets", []),
            "plugins": clean_catalog(data)}


# =========================================================================== Vergleich mit den installierten Plugins
def store_info(path: str) -> dict:
    """Markierung eines nachgeladenen Plugins (oder {} für eingebaute und eigene)."""
    try:
        with open(os.path.join(path, MARKER), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def compare(installed: list[dict], catalog: list[dict], app_version: str) -> list[dict]:
    """Je Katalog-Eintrag der Zustand: update · new · current · too_new · own (eigenes Plugin, wird nicht angetastet)."""
    by_id = {p["id"]: p for p in installed}
    out = []
    for e in catalog:
        p = by_id.get(e["id"])
        row = {**e, "installed": p["version"] if p else "", "builtin": bool(p and p.get("builtin")),
               "store": bool(p and p.get("store"))}
        if p and not p.get("builtin") and not p.get("store"):
            row["state"] = "own"
        elif not app_ok(e["min_app"], app_version):
            row["state"] = "too_new"
        elif p is None:
            row["state"] = "new"
        elif version_key(e["version"]) > version_key(p["version"]):
            row["state"] = "update"
        else:
            row["state"] = "current"
        out.append(row)
    return out


# =========================================================================== Installieren und entfernen
def _safe_members(z: zipfile.ZipFile, pid: str) -> list[zipfile.ZipInfo]:
    out = []
    for zi in z.infolist():
        n = zi.filename
        parts = n.split("/")
        if (n.startswith(("/", "\\")) or "\\" in n or ":" in n or ".." in parts or parts[0] != pid
                or (zi.external_attr >> 16) & 0o170000 == 0o120000):          # Link
            raise ValueError(f"Unerwarteter Inhalt im Plugin-Archiv: {n}")
        if not n.endswith("/"):
            out.append(zi)
    if not any(zi.filename == f"{pid}/plugin.json" for zi in out):
        raise ValueError("Im Plugin-Archiv fehlt plugin.json.")
    return out


def install(entry: dict, assets: list, dest_root: str, cache_dir: str, tag: str = "",
            progress=None, cancelled=None, opener=None) -> str:
    """Plugin aus dem Release laden, prüfen und nach `dest_root/<id>` legen. → Zielordner"""
    pid = entry["id"]
    target = os.path.join(dest_root, pid)
    if os.path.isdir(target) and not store_info(target):
        raise ValueError(f"Im Plugin-Ordner liegt ein eigenes Plugin „{pid}“ – es wird nicht überschrieben.")
    asset = next((a for a in assets if a.get("name") == entry["file"]), None)
    if asset is None:
        raise ValueError(f"Das Release enthält die Datei {entry['file']} nicht.")
    if str(asset.get("digest") or "").lower() != "sha256:" + entry["sha256"]:
        raise ValueError("Prüfsumme im Katalog und auf GitHub stimmen nicht überein – nichts installiert.")
    zpath = updater.download_asset(asset, cache_dir, progress, cancelled, opener)
    os.makedirs(dest_root, exist_ok=True)
    tmp = os.path.join(dest_root, f".install-{pid}")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        with zipfile.ZipFile(zpath) as z:
            members = _safe_members(z, pid)
            for zi in members:
                rel = zi.filename.split("/", 1)[1]
                out = os.path.join(tmp, *rel.split("/"))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(zi) as src, open(out, "wb") as fh:
                    shutil.copyfileobj(src, fh)
        with open(os.path.join(tmp, "plugin.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        if str(m.get("id") or "").lower() != pid:
            raise ValueError("Das Plugin-Archiv enthält ein anderes Plugin als angegeben.")
        with open(os.path.join(tmp, MARKER), "w", encoding="utf-8") as fh:
            json.dump({"id": pid, "version": entry["version"], "sha256": entry["sha256"], "tag": tag,
                       "installed": time.strftime("%Y-%m-%d %H:%M")}, fh, ensure_ascii=False, indent=1)
        old = None
        if os.path.isdir(target):
            old = os.path.join(dest_root, f".old-{pid}-{int(time.time())}")
            os.replace(target, old)
        try:
            os.replace(tmp, target)
        except OSError:
            if old:
                os.replace(old, target)                    # bisherige Version zurücklegen statt ohne Plugin
            raise
        if old:
            shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            os.remove(zpath)
        except OSError:
            pass
    return target


def remove(pid: str, dest_root: str) -> str:
    """Nachgeladenes Plugin entfernen (danach gilt wieder die eingebaute Version). Eigene Plugins: ValueError."""
    if not _ID_RE.match(str(pid or "")):
        raise ValueError("Ungültige Plugin-ID.")
    target = os.path.join(dest_root, pid)
    if not os.path.isdir(target) or not store_info(target):
        raise ValueError("Nur nachgeladene Plugins können hier entfernt werden.")
    shutil.rmtree(target)
    return target
