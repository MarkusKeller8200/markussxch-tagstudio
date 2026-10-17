"""Session-Teil „Einrichtung“ (#167–#170): Einrichtungsassistent, empfohlene/ausgeblendete Menüpunkte,
„Erste Schritte“-Hinweise je Seite und „Neu in dieser Version“."""
from __future__ import annotations

import re

import core
from version import VERSION

MODULES = ["prep", "tagger", "fixer", "compare", "djset", "snapshots", "backups", "plugins", "settings", "help"]
ALWAYS = {"settings", "help"}          # lassen sich nicht ausblenden
# Schlüssel, an denen ein schon benutztes TagStudio erkennbar ist (dann kein Assistent beim Start)
USED_KEYS = ("hist_tagger", "default_tagger", "tagger_state", "hist_left", "web_ui", "theme", "web_theme", "backup_dir", "prep_workflows")
INTRODUCED = "4.3.0"                    # bestehende Benutzer sehen „Neu in dieser Version“ ab hier


class SetupMixin:
    def _setup_migrate(self):
        """Bestehende Installation ohne Assistent-Stand: nicht als Erststart behandeln."""
        c = self.cfg
        if c.get("setup_started"):                        # Assistent läuft schon (z. B. Neuladen nach Sprachwechsel)
            return
        # die Sprachwahl allein (web_ui.lang, auch beim ersten Start gesetzt) macht noch keine bestehende Installation
        used = any(k in c for k in USED_KEYS if k != "web_ui") or bool(set(c.get("web_ui") or {}) - {"lang"})
        if not c.get("setup_done") and used:
            self._setup_set(setup_done="bestehend", seen_version=c.get("seen_version") or INTRODUCED,
                            first_steps=c.get("first_steps", False))

    def setup_state(self) -> dict:
        self._setup_migrate()
        c = self.cfg
        first = not c.get("setup_done")
        if first and not c.get("setup_started"):           # Erststart merken: Werte, die der Assistent schon setzt
            self._setup_set(setup_started=True)           # (Sprache, Workflow), machen ihn nicht zur „bestehenden“
        return {"done": c.get("setup_done") or "", "first": first, "version": VERSION,
                "recommended": [m for m in c.get("nav_recommended") or [] if m in MODULES],
                "hidden": [m for m in c.get("nav_hidden") or [] if m in MODULES and m not in ALWAYS],
                "first_steps": c.get("first_steps", True) is not False,
                "first_steps_seen": [m for m in c.get("first_steps_seen") or [] if m in MODULES],
                "seen_version": c.get("seen_version") or "", "modules": MODULES}

    def _setup_set(self, **kv):
        self.cfg.update(kv)
        core.save_config(kv)

    def setup_finish(self, recommended=None, first_steps=True) -> dict:
        """Assistent abgeschlossen (oder übersprungen): Empfehlungen und „Erste Schritte“ merken."""
        rec = [m for m in recommended or [] if m in MODULES]
        self._setup_set(setup_done=VERSION, nav_recommended=rec, first_steps=bool(first_steps),
                        first_steps_seen=[], seen_version=VERSION, setup_started=False)
        return self.setup_state()

    def set_nav_hidden(self, hidden) -> dict:
        self._setup_set(nav_hidden=[m for m in hidden or [] if m in MODULES and m not in ALWAYS])
        return self.setup_state()

    def first_steps_seen(self, module) -> dict:
        seen = list(self.cfg.get("first_steps_seen") or [])
        if module in MODULES and module not in seen:
            seen.append(module)
            self._setup_set(first_steps_seen=seen)
        return self.setup_state()

    def first_steps_restart(self) -> dict:
        """„Erste Schritte“ neu starten: alle Hinweise wieder zeigen."""
        self._setup_set(first_steps=True, first_steps_seen=[])
        return self.setup_state()

    def set_first_steps(self, on) -> dict:
        self._setup_set(first_steps=bool(on))
        return self.setup_state()

    def whats_new(self) -> dict:
        """Neu seit der zuletzt gezeigten Version: Abschnitte aus dem CHANGELOG (nur nach einem Update)."""
        import updater
        self._setup_migrate()
        seen = self.cfg.get("seen_version") or ""
        if not self.cfg.get("setup_done") or seen == VERSION:
            return {"show": False}
        text = updater.local_changelog() or ""
        if not text:
            return {"show": False}
        cur = updater.parse_version(VERSION)
        old = updater.parse_version(seen) if seen else None
        parts = []
        if updater.is_beta(VERSION):
            sec = updater.changelog_section(text, VERSION)
            if sec:
                parts.append({"version": VERSION, "notes": sec})
        for v in updater.changelog_versions(text):
            pv = updater.parse_version(v["version"])
            if pv and pv <= cur and (old is None or pv > old):
                parts.append({"version": v["version"], "notes": v["notes"]})
        return {"show": bool(parts), "since": seen, "parts": parts[:4]}

    def whats_new_seen(self) -> dict:
        self._setup_set(seen_version=VERSION)
        return {"ok": True}


# =========================================================================== Speicherort und Ordnerkonzept (#171)
import os  # noqa: E402
import sys  # noqa: E402

STRUCTURE = [
    ("new", "00_New", "Neue Musik (Rohdaten, unverändert)"),
    ("library", "01_Library", "Endgültige Bibliothek"),
    ("archive", "02_Archiv", "Aussortierte Titel"),
    ("download", "90_Download", "Temporäre Downloads (Browser, Beatport, ZIP)"),
    ("work", "91_Work", "Arbeitsordner für TagStudio und andere Programme (Stufen-Ordner)"),
    ("backup", "99_Sicherung", "Sicherungen der Tags und Snapshots"),
]


def _drives() -> list[dict]:
    """Laufwerke mit Bezeichnung und freiem Platz (Windows); sonst Benutzerordner und /."""
    out = []
    if sys.platform.startswith("win"):
        import ctypes
        import string
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if not mask & (1 << i):
                continue
            root = f"{letter}:\\"
            kind = ctypes.windll.kernel32.GetDriveTypeW(root)      # 2 Wechsel, 3 fest, 4 Netz, 5 CD
            if kind not in (2, 3, 4):
                continue
            free, total = ctypes.c_ulonglong(0), ctypes.c_ulonglong(0)
            if not ctypes.windll.kernel32.GetDiskFreeSpaceExW(root, None, ctypes.byref(total), ctypes.byref(free)):
                continue
            name = ctypes.create_unicode_buffer(261)
            ctypes.windll.kernel32.GetVolumeInformationW(root, name, 261, None, None, None, None, 0)
            out.append({"root": root, "label": name.value, "free": free.value, "total": total.value,
                        "kind": {2: "Wechseldatenträger", 3: "Festplatte", 4: "Netzlaufwerk"}.get(kind, "")})
    else:
        import shutil
        for root in (os.path.expanduser("~"), "/"):
            try:
                u = shutil.disk_usage(root)
            except OSError:
                continue
            out.append({"root": root, "label": "Benutzerordner" if root != "/" else "System", "free": u.free,
                        "total": u.total, "kind": ""})
    return out


def suggest_base(drives) -> str:
    """Vorschlag: D:\\TagStudio (bzw. erstes weiteres festes Laufwerk), sonst Benutzerordner\\Music\\TagStudio
    (nicht ~\\TagStudio – dort liegen die Programmdaten)."""
    if sys.platform.startswith("win"):
        fixed = [d for d in drives if d["kind"] == "Festplatte" and not d["root"].upper().startswith("C:")]
        d = next((x for x in fixed if x["root"].upper().startswith("D:")), fixed[0] if fixed else None)
        if d:
            return os.path.join(d["root"], "TagStudio")
    return os.path.join(os.path.expanduser("~"), "Music", "TagStudio")


class FoldersMixin:
    def base_dir(self) -> str:
        return str(self.cfg.get("base_dir") or "")

    def folders_overview(self) -> dict:
        """Speicherort und alle Arbeitsordner auf einen Blick (Einstellungen › Ordner, Assistent)."""
        drives = _drives()
        try:
            w = self._prep_get()
        except Exception:  # noqa: BLE001
            w = {}
        rows = [("Basisordner", self.base_dir()), ("Bibliothek (Tagger)", self.cfg.get("default_tagger") or ""),
                ("Eingang (Vorbereiten)", w.get("inbox", "")), ("Arbeitsordner (Vorbereiten)", w.get("work", "")),
                ("Bibliothek (Vorbereiten)", w.get("library", "")), ("Archiv", self.cfg.get("archive_dir") or ""),
                ("Sicherungen", self._backup_folder()), ("Snapshot-Speicher", self.snap_store.root)]
        rows += [(f"Quelle: {q['name']}", q["folder"]) for q in w.get("sources") or []]
        return {"base": self.base_dir(), "suggest": suggest_base(drives), "drives": drives,
                "archive": str(self.cfg.get("archive_dir") or ""),
                "home_base": os.path.join(os.path.expanduser("~"), "Music", "TagStudio"),
                "structure": [{"id": k, "name": n, "desc": d} for k, n, d in STRUCTURE],
                "rows": [{"label": lab, "path": p, "exists": bool(p) and os.path.isdir(p)} for lab, p in rows]}

    def set_base_dir(self, path, create=True) -> dict:
        p = os.path.abspath(os.path.expanduser(str(path or "").strip())) if str(path or "").strip() else ""
        if p and create:
            os.makedirs(p, exist_ok=True)
        self.cfg["base_dir"] = p
        core.save_config({"base_dir": p})
        return self.folders_overview()

    def setup_structure(self, base, names=None) -> dict:
        """Ordnerstruktur unter base anlegen (vorhandene bleiben, nichts wird verschoben) und alle Einstellungen
        darauf setzen: Tagger-Bibliothek, Vorbereiten (Eingang, Arbeitsordner, Bibliothek, Quelle), Archiv,
        Sicherungen, Snapshot-Speicher (nur wenn noch leer), Beatport-Download-Ziel."""
        names = names or {}
        raw = str(base or "").strip()
        base = os.path.abspath(os.path.expanduser(raw)) if raw else ""
        if not base or os.path.dirname(base) == base:
            raise ValueError("Bitte einen Basisordner wählen (nicht direkt das Laufwerk).")
        p = {}
        for k, n, _d in STRUCTURE:
            n = re.sub(r'[<>:"/\\|?*]', "", str(names.get(k) or n)).strip() or n
            p[k] = os.path.join(base, n)
        created = []
        for k in p:
            if not os.path.isdir(p[k]):
                os.makedirs(p[k])
                created.append(p[k])
        tags, snaps = os.path.join(p["backup"], "Tags"), os.path.join(p["backup"], "Snapshots")
        for d in (tags, snaps):
            os.makedirs(d, exist_ok=True)
        self.set_base_dir(base)
        self.set_default_dir("tagger", p["library"])
        self.cfg["archive_dir"] = p["archive"]
        core.save_config({"archive_dir": p["archive"]})
        self.set_backup(True, tags, None)
        if not os.path.isdir(self.snap_store.root) or not os.listdir(self.snap_store.root):
            self._snap_dir_set(snaps)
        w = self._prep_get()
        w.update(inbox=p["new"], work=p["work"], library=p["library"])
        if not any(os.path.normcase(q.get("folder", "")) == os.path.normcase(p["download"]) for q in w.get("sources") or []):
            w.setdefault("sources", []).append({"name": "Downloads", "folder": p["download"], "pattern": "", "sub": "", "zip": True})
        self.prep_workflow_save(w)
        po = self.cfg.setdefault("plugin_options", {}).setdefault("beatport", {}).setdefault("download", {})
        po["dest"] = p["download"]
        core.save_config({"plugin_options": self.cfg["plugin_options"]})
        return {"paths": p, "created": created, "overview": self.folders_overview()}


class ArchiveMixin:
    """Aussortieren ins Archiv (#173) – im Tagger und in „Vorbereiten“, mit Vermerk und Zurückholen."""

    def _archive_dir(self) -> str:
        d = str(self.cfg.get("archive_dir") or "")
        if not d:
            raise ValueError("Kein Archiv-Ordner festgelegt – Einstellungen › Speicherort und Ordner.")
        os.makedirs(d, exist_ok=True)
        return d

    def set_archive_dir(self, path) -> dict:
        p = os.path.abspath(os.path.expanduser(str(path).strip())) if str(path or "").strip() else ""
        self.cfg["archive_dir"] = p
        core.save_config({"archive_dir": p})
        return self.folders_overview()

    def tag_archive(self, idx, apply=False) -> dict:
        """Markierte Titel des Taggers ins Archiv verschieben (Unterordner relativ zum geladenen Ordner bleiben)."""
        import archive
        d = self._archive_dir()
        with self.lock:
            files = self._tsel(idx)
            dirty = {os.path.abspath(f.path) for f in files if f.is_modified()}
            pl = archive.plan([f.path for f in files], getattr(self, "tag_root", None), d)
            for e in pl:
                if not e["problem"] and e["src"] in dirty:
                    e["problem"] = "ungespeicherte Änderungen – zuerst speichern"
            rows = [{"src": e["src"], "dst": e["dst"], "stems": bool(e["stems_src"]), "problem": e["problem"]} for e in pl]
            if not apply:
                return {"rows": rows, "archive": d, "ok": sum(1 for e in pl if not e["problem"])}
            res = archive.move(pl, d, "Tagger")
        return {"moved": len(res["moved"]), "errors": res["errors"], "archive": d,
                "message": f"{len(res['moved'])} Titel ins Archiv verschoben." + (f" {len(res['errors'])} Fehler." if res["errors"] else "")}

    def prep_archive(self, wid, names, apply=False, drop_copies=True) -> dict:
        """Titel aus dem Eingang von „Vorbereiten“ aussortieren: Original ins Archiv, Stufen-Kopien entfernen (nach Rückfrage
        in der Oberfläche), Titel aus dem Workflow-Status nehmen."""
        import archive
        import prepare
        d = self._archive_dir()
        w = self._prep_get(wid)
        st = prepare.load_state(w["id"])
        srcs = [os.path.join(w["inbox"], n) for n in names or []]
        pl = archive.plan(srcs, w["inbox"], d)
        copies = {}
        for n in names or []:
            for s in w["steps"]:
                if s.get("folder"):
                    p = os.path.join(prepare.work_dir(w), s["folder"], n)
                    if os.path.isfile(p):
                        copies.setdefault(n, []).append(p)
        rows = [{"src": e["src"], "dst": e["dst"], "problem": e["problem"]} for e in pl]
        if not apply:
            return {"rows": rows, "copies": [c for v in copies.values() for c in v], "archive": d,
                    "ok": sum(1 for e in pl if not e["problem"])}
        res = archive.move(pl, d, "Vorbereiten")
        moved = {os.path.normcase(e["src"]) for e in res["moved"]}
        removed = 0
        for n in names or []:
            if os.path.normcase(os.path.abspath(os.path.join(w["inbox"], n))) not in moved:
                continue
            st["tracks"].pop(n, None)
            if drop_copies:
                for c in copies.get(n, []):
                    try:
                        os.remove(c)
                        removed += 1
                    except OSError:
                        pass
        prepare.save_state(w["id"], st)
        d2 = self.prep_overview(w["id"])
        d2["message"] = f"{len(res['moved'])} Titel aussortiert" + (f", {removed} Stufen-Kopie(n) entfernt" if removed else "") + "."
        d2["errors"] = res["errors"]
        return d2

    def archive_list(self) -> dict:
        import archive
        d = str(self.cfg.get("archive_dir") or "")
        return {"archive": d, "entries": archive.entries(d) if d else []}

    def archive_restore(self, ids) -> dict:
        import archive
        res = archive.restore(self._archive_dir(), [int(i) for i in ids or []])
        out = self.archive_list()
        out.update(restored=len(res["restored"]), errors=res["errors"],
                   message=f"{len(res['restored'])} Titel zurückgeholt." + (f" {len(res['errors'])} Hinweis(e)." if res["errors"] else ""))
        return out
