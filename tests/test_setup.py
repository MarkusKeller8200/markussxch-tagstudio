"""Einrichtung (#167–#170): Erststart, bestehende Installation, Empfehlungen, Erste Schritte, Neu in dieser Version."""
import unittest
from unittest import mock

from test_tagger_tools import Base


class TestSetup(Base):
    def session(self, cfg):
        from session import Session
        s = Session()
        s.cfg.clear()
        s.cfg.update(cfg)
        return s

    def test_first_and_finish(self):
        s = self.session({})
        st = s.setup_state()
        self.assertTrue(st["first"])
        st = s.setup_finish(["prep", "tagger", "unbekannt"], True)
        self.assertFalse(st["first"])
        self.assertEqual(st["recommended"], ["prep", "tagger"])
        self.assertTrue(st["first_steps"])
        st = s.first_steps_seen("tagger")
        self.assertEqual(st["first_steps_seen"], ["tagger"])
        st = s.first_steps_restart()
        self.assertEqual(st["first_steps_seen"], [])
        st = s.set_nav_hidden(["djset", "settings", "x"])
        self.assertEqual(st["hidden"], ["djset"])                 # Einstellungen/Hilfe nie ausblendbar

    def test_existing_install_no_wizard(self):
        s = self.session({"hist_tagger": ["/x"], "web_theme": "dark"})
        st = s.setup_state()
        self.assertFalse(st["first"])
        self.assertFalse(st["first_steps"])                       # bestehende Benutzer: keine Hinweise aufdrängen
        self.assertEqual(s.cfg["seen_version"], "4.3.0")

    def test_whats_new(self):
        import session_setup
        s = self.session({"setup_done": "x", "seen_version": "4.2.0"})
        text = "## [Unveröffentlicht]\n\n### Neu\n- A\n\n## [4.3.0] – 2026-10-11\n\n### Neu\n- B\n\n## [4.2.0] – 2026-10-01\n\n- C\n"
        with mock.patch("updater.local_changelog", return_value=text), mock.patch.object(session_setup, "VERSION", "4.4.0-beta.2"):
            r = s.whats_new()
            self.assertTrue(r["show"])
            self.assertEqual([p["version"] for p in r["parts"]], ["4.4.0-beta.2", "4.3.0"])
            s.whats_new_seen()
            self.assertFalse(s.whats_new()["show"])


if __name__ == "__main__":
    unittest.main()
