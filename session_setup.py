"""Session-Teil „Einrichtung“ (#167–#170): Einrichtungsassistent, empfohlene/ausgeblendete Menüpunkte,
„Erste Schritte“-Hinweise je Seite und „Neu in dieser Version“."""
from __future__ import annotations

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
        if not c.get("setup_done") and any(k in c for k in USED_KEYS):
            self._setup_set(setup_done="bestehend", seen_version=c.get("seen_version") or INTRODUCED,
                            first_steps=c.get("first_steps", False))

    def setup_state(self) -> dict:
        self._setup_migrate()
        c = self.cfg
        first = not c.get("setup_done")
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
                        first_steps_seen=[], seen_version=VERSION)
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
