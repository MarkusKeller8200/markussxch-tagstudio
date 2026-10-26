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

    def test_nav_order_and_purchases(self):
        """#316: Käufe schaltbar und zuerst; eigene Reihenfolge, neue Module an ihrem Standardplatz, zurücksetzen."""
        s = self.session({"setup_done": "x"})
        st = s.setup_state()
        self.assertEqual(st["order"][:3], ["discover", "ideas", "purchases"])  # #333: Entdecken zuoberst, #186 Ideen
        self.assertNotIn("settings", st["order"])
        self.assertEqual(s.set_nav_hidden(["purchases"])["hidden"], ["purchases"])
        order = list(st["order"])
        order.remove("tagger")
        order.insert(0, "tagger")
        st = s.set_nav_order(order)
        self.assertEqual(st["order"][:4], ["tagger", "discover", "ideas", "purchases"])
        s.cfg["nav_order"] = ["tagger", "prep"]                  # ältere Liste ohne neue Module
        o = s.setup_state()["order"]
        self.assertEqual(o[:3], ["discover", "ideas", "purchases"])             # neue Module an ihrem Standardplatz
        self.assertLess(o.index("tagger"), o.index("prep"))
        self.assertEqual(sorted(o), sorted(m for m in st["modules"] if m not in ("settings", "help")))
        self.assertEqual(s.set_nav_order([])["order"][0], "discover")
        self.assertEqual(s.cfg.get("nav_order"), [])

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

    def test_first_start_survives_language_and_reload(self):
        """Sprachwahl („auto“) und Werte des Assistenten machen den Erststart nicht zur bestehenden Installation."""
        s = self.session({"web_ui": {"lang": "auto"}})
        self.assertTrue(s.setup_state()["first"])
        s.cfg.update({"web_ui": {"lang": "de-CH"}, "prep_workflows": [{"id": "x"}]})   # Assistent hat schon Werte gesetzt
        self.assertTrue(s.setup_state()["first"])                 # z. B. Neuladen nach Sprachwechsel
        self.assertFalse(s.setup_finish([], True)["first"])
        self.assertFalse(s.cfg["setup_started"])

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

    def test_structure(self):
        import os
        s = self.session({})
        base = os.path.join(self.dir, "Musik")
        os.makedirs(os.path.join(base, "01_Library"))                  # vorhandener Ordner bleibt
        r = s.setup_structure(base, {"new": "00_Neu"})
        self.assertTrue(all(os.path.isdir(p) for p in r["paths"].values()))
        self.assertEqual(os.path.basename(r["paths"]["new"]), "00_Neu")
        self.assertEqual(len(r["created"]), 7)                           # inkl. 04_Export (#310)
        self.assertEqual(s.cfg["base_dir"], base)
        self.assertEqual(s.cfg["playlist_dir"], r["paths"]["playlists"])             # #267
        self.assertEqual(os.path.basename(r["paths"]["playlists"]), "03_Playlists")
        self.assertEqual(s.cfg["default_tagger"], r["paths"]["library"])
        self.assertEqual(s.cfg["archive_dir"], r["paths"]["archive"])
        self.assertEqual(s.snap_store.root, os.path.join(r["paths"]["backup"], "Snapshots"))
        w = s._prep_get()
        self.assertEqual((w["inbox"], w["work"], w["library"]), (r["paths"]["new"], r["paths"]["work"], r["paths"]["library"]))
        self.assertEqual(w["_raw"], {"inbox": "", "work": "", "library": ""})        # #314: folgt den Rollen
        n = len(w["sources"])
        srcs = {q["name"]: q for q in w["sources"]}
        self.assertEqual(srcs["Manuell"]["folder"], os.path.join(r["paths"]["download"], "_Manuell"))   # O5
        self.assertEqual(srcs["Manuell"]["sub"], "_Manuell")
        self.assertTrue(os.path.isdir(os.path.join(r["paths"]["new"], "_Manuell")))
        if "Beatport" in srcs:                                          # eingeschaltetes Store-Plugin
            self.assertEqual(s.cfg["plugin_options"]["beatport"]["download"]["dest"],
                             os.path.join(r["paths"]["download"], "Beatport"))
        s.setup_structure(base)                                         # nochmals: keine doppelte Quelle
        self.assertEqual(len(s._prep_get()["sources"]), n)
        ov = s.folders_overview()
        self.assertTrue(all(x["exists"] for x in ov["rows"] if x["path"]))
        with self.assertRaises(ValueError):
            s.setup_structure("")


if __name__ == "__main__":
    unittest.main()
