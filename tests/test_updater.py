"""Tests für updater.py mit echten (temporären) Git-Repositories."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater  # noqa: E402

HAVE_GIT = shutil.which("git") is not None


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="T",
                            GIT_COMMITTER_EMAIL="t@t"))


@unittest.skipUnless(HAVE_GIT, "git nicht installiert")
class TestUpdater(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_upd_")
        self.origin = os.path.join(self.dir, "origin.git")
        self.app = os.path.join(self.dir, "app")
        self.dev = os.path.join(self.dir, "dev")
        git(self.dir, "init", "-q", "--bare", "-b", "main", self.origin)
        git(self.dir, "clone", "-q", self.origin, self.dev)
        with open(os.path.join(self.dev, "a.txt"), "w") as fh:
            fh.write("1\n")
        git(self.dev, "add", "a.txt")
        git(self.dev, "commit", "-q", "-m", "Erster Stand")
        git(self.dev, "push", "-q", "origin", "HEAD:main")
        git(self.dir, "clone", "-q", self.origin, self.app)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _new_commit(self, msg, content):
        with open(os.path.join(self.dev, "a.txt"), "w") as fh:
            fh.write(content)
        git(self.dev, "commit", "-qam", msg)
        git(self.dev, "push", "-q", "origin", "HEAD:main")

    def test_status_and_pull(self):
        st = updater.status(True, self.app)
        self.assertTrue(st["ok"], st)
        self.assertEqual((st["branch"], st["behind"]), ("main", 0))
        self._new_commit("Neue Funktion", "2\n")
        st = updater.status(True, self.app)
        self.assertEqual(st["behind"], 1)
        self.assertEqual(st["commits"], ["Neue Funktion"])
        res = updater.pull(self.app)
        self.assertTrue(res["ok"] and res["updated"], res)
        with open(os.path.join(self.app, "a.txt")) as fh:
            self.assertEqual(fh.read(), "2\n")
        self.assertEqual(updater.pull(self.app)["updated"], False)

    def test_moved_branch_switches_to_main(self):
        # App steht auf „web-ui“; der Zweig wird nach main übernommen → Update wechselt auf main
        git(self.dev, "switch", "-q", "-c", "web-ui")
        with open(os.path.join(self.dev, "b.txt"), "w") as fh:
            fh.write("neu\n")
        git(self.dev, "add", "b.txt")
        git(self.dev, "commit", "-q", "-m", "Neue Oberfläche")
        git(self.dev, "push", "-q", "origin", "HEAD:web-ui")
        git(self.app, "fetch", "-q", "origin")
        git(self.app, "switch", "-q", "-c", "web-ui", "--track", "origin/web-ui")
        git(self.app, "branch", "-q", "-D", "main")            # wie auf dem PC: kein lokaler main
        st = updater.status(True, self.app)
        self.assertEqual((st["branch"], st["switch"]), ("web-ui", None))   # main enthält web-ui noch nicht
        git(self.dev, "switch", "-q", "main")
        git(self.dev, "merge", "-q", "--no-ff", "-m", "Merge web-ui", "web-ui")
        git(self.dev, "push", "-q", "origin", "main")
        st = updater.status(True, self.app)
        self.assertEqual(st["switch"], "main")
        self.assertEqual(st["upstream"], "origin/main")
        self.assertEqual(st["behind"], 1)
        res = updater.pull(self.app)
        self.assertTrue(res["ok"] and res["updated"], res)
        self.assertIn("Hauptzweig", res["message"])
        st = updater.status(True, self.app)
        self.assertEqual((st["branch"], st["behind"], st["switch"]), ("main", 0, None))
        self.assertTrue(os.path.exists(os.path.join(self.app, "b.txt")))

    def test_moved_branch_deleted_on_github(self):
        git(self.dev, "push", "-q", "origin", "HEAD:web-ui")
        git(self.app, "fetch", "-q", "origin")
        git(self.app, "switch", "-q", "-c", "web-ui", "--track", "origin/web-ui")
        self._new_commit("Weiter auf main", "4\n")
        git(self.dev, "push", "-q", "origin", "--delete", "web-ui")
        git(self.app, "fetch", "-q", "--prune", "origin")          # origin/web-ui verschwindet
        st = updater.status(True, self.app)
        self.assertTrue(st["ok"], st)
        self.assertEqual((st["switch"], st["behind"]), ("main", 1))
        self.assertTrue(updater.pull(self.app)["ok"])
        self.assertEqual(updater.status(False, self.app)["branch"], "main")

    def test_local_changes_block_update(self):
        self._new_commit("Noch was", "3\n")
        with open(os.path.join(self.app, "a.txt"), "w") as fh:
            fh.write("lokal geändert\n")
        res = updater.pull(self.app)
        self.assertFalse(res["ok"])
        self.assertIn("a.txt", res["message"])

    def test_stable_channel_stops_at_final_tag(self):
        """#89: Kanal „stable“ lädt nur bis zur neuesten offiziellen Version (Tag), „beta“ bis zum Zweig."""
        self._new_commit("3.5.0", "2\n")
        git(self.dev, "tag", "v3.5.0")
        git(self.dev, "push", "-q", "origin", "v3.5.0")
        self._new_commit("Beta", "3\n")
        git(self.dev, "tag", "v3.6.0-beta.1")
        git(self.dev, "push", "-q", "origin", "v3.6.0-beta.1")
        st = updater.status(True, self.app, channel="stable")
        self.assertEqual((st["behind"], st["upstream"]), (1, "v3.5.0"))
        self.assertTrue(updater.pull(self.app, channel="stable")["updated"])
        with open(os.path.join(self.app, "a.txt")) as fh:
            self.assertEqual(fh.read(), "2\n")
        self.assertEqual(updater.status(True, self.app, channel="beta")["behind"], 1)
        updater.pull(self.app, channel="beta")
        st = updater.status(True, self.app, channel="stable")       # Beta weiter als offiziell → Hinweis
        self.assertEqual(st["behind"], 0)
        self.assertIn("Beta", st["note"])

    def test_not_a_repo(self):
        st = updater.status(False, self.dir)
        self.assertFalse(st["ok"])


class TestReleases(unittest.TestCase):
    """#89/#90: Versionen vergleichen, Kanal, Versionshinweise – ohne Netz."""
    RELS = [{"tag": "v3.5.0-beta.1", "beta": True}, {"tag": "v3.4.0", "beta": False},
            {"tag": "v3.5.0-beta.2", "beta": True}, {"tag": "v3.3.1", "beta": False}]

    def test_versions(self):
        pv = updater.parse_version
        self.assertLess(pv("3.5.0-beta.2"), pv("3.5.0"))
        self.assertLess(pv("v3.5.0-beta.2"), pv("3.5.0-beta.10"))
        self.assertLess(pv("3.4.0"), pv("3.5.0-beta.1"))
        self.assertIsNone(pv("web-ui"))
        self.assertEqual(updater.newest(self.RELS, "stable")["tag"], "v3.4.0")
        self.assertEqual(updater.newest(self.RELS, "beta")["tag"], "v3.5.0-beta.2")

    def test_release_check(self):
        rc = updater.release_check("3.4.0", "stable", self.RELS)
        self.assertFalse(rc["newer"])
        rc = updater.release_check("3.4.0", "beta", self.RELS)
        self.assertTrue(rc["newer"] and rc["latest"]["tag"] == "v3.5.0-beta.2")
        rc = updater.release_check("3.5.0-beta.2", "stable", self.RELS)    # Beta → offiziell: Hinweis
        self.assertFalse(rc["newer"])
        self.assertIn("Beta", rc["note"])
        rc = updater.release_check("3.5.0-beta.2", "stable", self.RELS + [{"tag": "v3.5.0", "beta": False}])
        self.assertTrue(rc["newer"])

    def test_changelog_section(self):
        log = "# C\n\n## [Unveröffentlicht]\n\n- neu\n\n## [3.4.0] – 2026\n\n### Neu\n- Player\n\n## [3.3.1]\n- x\n"
        self.assertEqual(updater.changelog_section(log, "3.4.0"), "### Neu\n- Player")
        self.assertEqual(updater.changelog_section(log, "3.5.0-beta.1"), "- neu")
        self.assertEqual(updater.changelog_section(log, "9.9.9"), "")
        self.assertIn("## [", updater.local_changelog())

    def test_changelog_versions(self):
        """#136: ältere Versionen für die Versionshinweise in der App."""
        log = ("# C\n\n## [Unveröffentlicht]\n- neu\n\n## [3.4.0] – 2026-10-10\n### Neu\n- Player\n\n"
               "## [3.3.1]\n- x\n\n## Frühere Versionen (1.0 – 2.8)\n- alt\n")
        v = updater.changelog_versions(log, "3.4.0")
        self.assertEqual([x["version"] for x in v], ["3.3.1", "Frühere Versionen (1.0 – 2.8)"])
        self.assertEqual(updater.changelog_versions(log)[0], {"version": "3.4.0", "date": "2026-10-10", "notes": "### Neu\n- Player"})
        self.assertEqual(v[1]["notes"], "- alt")


if __name__ == "__main__":
    unittest.main()
