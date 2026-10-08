"""Tests für updater.py mit echten (temporären) Git-Repositories."""
import os
import shutil
import subprocess
import tempfile
import unittest

import updater

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

    def test_local_changes_block_update(self):
        self._new_commit("Noch was", "3\n")
        with open(os.path.join(self.app, "a.txt"), "w") as fh:
            fh.write("lokal geändert\n")
        res = updater.pull(self.app)
        self.assertFalse(res["ok"])
        self.assertIn("a.txt", res["message"])

    def test_not_a_repo(self):
        st = updater.status(False, self.dir)
        self.assertFalse(st["ok"])


if __name__ == "__main__":
    unittest.main()
