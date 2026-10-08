"""Tests für die Versionierung (version.py, packaging/release.py) – prüfen auch das echte Repository."""
import datetime
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "packaging"))
import release  # noqa: E402
import version  # noqa: E402


class TestRepository(unittest.TestCase):
    def test_repo_consistent(self):
        self.assertEqual(release.check(), [], "Versionierung im Repository passt nicht zusammen")

    def test_version_used_everywhere(self):
        import session
        self.assertEqual(session.VERSION, version.VERSION)
        self.assertRegex(version.VERSION, release.SEMVER)


class TestRelease(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_rel_")
        for n in ("version.py", "pyproject.toml"):
            shutil.copy(os.path.join(ROOT, n), self.dir)
        with open(os.path.join(self.dir, "CHANGELOG.md"), "w", encoding="utf-8") as fh:
            fh.write("# Changelog\n\n## [Unveröffentlicht]\n### Neu\n- Etwas Neues\n\n"
                     f"## [{version.VERSION}] – 2026-10-09\n- Alt\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def read(self, n):
        with open(os.path.join(self.dir, n), encoding="utf-8") as fh:
            return fh.read()

    def test_release_and_beta(self):
        nxt = "9.1.0"
        old = release.release(nxt + "-beta.1", root=self.dir)
        self.assertEqual(old, version.VERSION)
        self.assertEqual(release.current_version(self.dir), nxt + "-beta.1")
        self.assertIn("## [Unveröffentlicht]\n### Neu", self.read("CHANGELOG.md"))   # Beta: CHANGELOG bleibt
        self.assertEqual(release.section_text(self.read("CHANGELOG.md"), nxt + "-beta.1"), "### Neu\n- Etwas Neues")
        release.release(nxt, today=datetime.date(2026, 11, 1), root=self.dir)
        log = self.read("CHANGELOG.md")
        self.assertIn(f"## [Unveröffentlicht]\n\n## [{nxt}] – 2026-11-01\n### Neu\n- Etwas Neues", log)
        self.assertEqual(release.section_text(log, nxt), "### Neu\n- Etwas Neues")
        self.assertIn(f'version = "{nxt}"', self.read("pyproject.toml"))
        self.assertEqual(release.check(self.dir), [])
        with self.assertRaises(ValueError):          # Unveröffentlicht ist jetzt leer
            release.release("9.1.1", root=self.dir)

    def test_rules(self):
        with self.assertRaises(ValueError):
            release.release("3.1", root=self.dir)          # kein MAJOR.MINOR.PATCH
        with self.assertRaises(ValueError):
            release.release(version.VERSION, root=self.dir)  # nicht neuer
        self.assertLess(release.key("3.1.0-beta.1"), release.key("3.1.0"))
        self.assertLess(release.key("3.1.0"), release.key("3.10.0"))
        self.assertTrue(release.SEMVER.match("4.0.0-rc.2"))


if __name__ == "__main__":
    unittest.main()
