"""Profile und zentrale Pfade (#163–#165)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

import helpers  # noqa: F401 – Pfad zum Programm
import paths


class TestPaths(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE", "TAGSTUDIO_PROFIL", "TAGSTUDIO_NOASK")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        for k in ("TAGSTUDIO_PROFIL", "TAGSTUDIO_NOASK"):
            os.environ.pop(k, None)
        self._prof = paths.profile()
        paths.set_profile(None)

    def tearDown(self):
        paths._profile = self._prof
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_default_unchanged(self):
        self.assertEqual(paths.config_file(), os.path.join(self.dir, ".tagstudio.json"))
        self.assertEqual(paths.data_dir(), os.path.join(self.dir, "TagStudio"))
        self.assertEqual(paths.lock_file(), os.path.join(self.dir, ".tagstudio.lock"))
        self.assertEqual(paths.mutex_name(), "MarKusSXCH-TagStudio")
        self.assertEqual(paths.profile_label(), "Standard")

    def test_profile_paths(self):
        paths.set_profile("Test 2")
        d = os.path.join(self.dir, "TagStudio-Profile", "Test 2")
        self.assertEqual(paths.data_dir(), d)
        self.assertEqual(paths.config_file(), os.path.join(d, "einstellungen.json"))
        self.assertEqual(paths.sub("Logs"), os.path.join(d, "Logs"))
        self.assertTrue(paths.lock_file().startswith(d))
        self.assertEqual(paths.mutex_name(), "MarKusSXCH-TagStudio-Test_2")
        self.assertEqual(paths.shared_plugin_data(), os.path.join(self.dir, "TagStudio", "Plugin-Daten"))  # geteilt
        import plugins
        self.assertTrue(plugins.data_root().startswith(d))
        self.assertTrue(plugins.shared_root().startswith(os.path.join(self.dir, "TagStudio")))
        self.assertEqual(plugins.user_dir(), os.path.join(self.dir, "TagStudio", "Plugins"))

    def test_names_and_argv(self):
        for bad in ("../x", "a/b", "x" * 41, "?"):
            with self.assertRaises(ValueError):
                paths.clean_name(bad)
        self.assertIsNone(paths.clean_name("standard"))
        self.assertEqual(paths._from_argv(["--profil", "Neu"]), "Neu")
        self.assertEqual(paths._from_argv(["x", "--profil=Neu"]), "Neu")
        os.environ["TAGSTUDIO_PROFIL"] = "Env"
        paths.init([])
        self.assertEqual(paths.profile(), "Env")
        paths.init(["--profil", "Arg"])
        self.assertEqual(paths.profile(), "Arg")

    def test_create_list_registry_ask(self):
        argv = sys.argv
        sys.argv = ["tagstudio_web.py"]
        try:
            self.assertEqual(paths.list_profiles(), ["Standard"])
            self.assertFalse(paths.should_ask())                       # nur ein Profil
            with open(os.path.join(self.dir, ".tagstudio.json"), "w", encoding="utf-8") as fh:
                json.dump({"theme": "light", "setup_done": 1, "window": {"x": 1}}, fh)
            paths.create_profile("Frisch")
            paths.create_profile("Kopie", "Standard")
            with self.assertRaises(ValueError):
                paths.create_profile("Frisch")
            self.assertEqual(paths.list_profiles(), ["Standard", "Frisch", "Kopie"])
            self.assertFalse(os.path.exists(paths.config_file("Frisch")))   # leer
            with open(paths.config_file("Kopie"), encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"theme": "light"})          # ohne Assistent-/Fenster-Stand
            self.assertTrue(paths.should_ask())
            paths.save_registry({"ask": False, "last": "Kopie"})
            self.assertFalse(paths.should_ask())
            paths.save_registry({"ask": True})
            os.environ["TAGSTUDIO_NOASK"] = "1"                           # nach einem Neustart nicht nochmals fragen
            self.assertFalse(paths.should_ask())
        finally:
            sys.argv = argv

    def test_instance_per_profile(self):
        import instance
        a = instance.Instance(os.path.join(self.dir, "a.lock"))
        b = instance.Instance(os.path.join(self.dir, "b.lock"))
        self.assertTrue(a.acquire(wait=0))
        self.assertTrue(b.acquire(wait=0))                              # anderes Profil = andere Sperre
        a.release()
        b.release()


if __name__ == "__main__":
    unittest.main()
