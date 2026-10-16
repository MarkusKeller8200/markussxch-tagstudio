"""Entscheid 16.10.2026: „Developer Release“ – Quellcode mit Commits nach dem Tag der laufenden Version."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater  # noqa: E402


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


@unittest.skipIf(not updater.shutil.which("git"), "git fehlt")
class TestDevRelease(unittest.TestCase):
    def setUp(self):
        updater._DEV.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        git(self.d, "init", "-q")
        for n in ("a", "b"):
            with open(os.path.join(self.d, n), "w") as fh:
                fh.write(n)
            git(self.d, "add", n)
            git(self.d, "commit", "-qm", n)
            if n == "a":
                git(self.d, "tag", "v4.5.0")

    def tearDown(self):
        self.tmp.cleanup()
        updater._DEV.clear()

    def test_dev_after_tag(self):
        r = updater.dev_info("4.5.0", self.d)
        self.assertEqual((r["dev"], r["commits"], r["base"]), (True, 1, "4.5.0"))

    def test_release_exactly_on_tag(self):
        git(self.d, "tag", "v4.5.1")
        self.assertFalse(updater.dev_info("4.5.1", self.d)["dev"])

    def test_version_without_tag_yet(self):
        self.assertTrue(updater.dev_info("4.6.0", self.d)["dev"])          # Version gesetzt, Tag folgt erst

    def test_installed_app_never_dev(self):
        with mock.patch.object(updater, "frozen", lambda: True):
            self.assertFalse(updater.dev_info("4.5.0", self.d)["dev"])


if __name__ == "__main__":
    unittest.main()
