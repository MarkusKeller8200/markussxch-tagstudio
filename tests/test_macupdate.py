"""#251: Update auf Knopfdruck unter macOS – DMG je Prozessor, Skript mit nachgestellten Mac-Werkzeugen."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import updater  # noqa: E402


class TestMacUpdate(unittest.TestCase):
    def test_supported_and_dmg_per_processor(self):
        with mock.patch.object(updater, "frozen", return_value=True):
            self.assertTrue(updater.auto_update_supported("darwin"))
            self.assertFalse(updater.auto_update_supported("linux"))
        rel = {"assets": [{"name": "TagStudio-4.8.0-macOS-Intel.dmg"}, {"name": "TagStudio-4.8.0-macOS-Apple-Chip.dmg"},
                          {"name": "TagStudio-4.8.0-Windows-Setup.exe"}]}
        self.assertEqual(updater.platform_asset(rel, "darwin", "arm64")["name"], "TagStudio-4.8.0-macOS-Apple-Chip.dmg")
        self.assertEqual(updater.platform_asset(rel, "darwin", "x86_64")["name"], "TagStudio-4.8.0-macOS-Intel.dmg")
        only_arm = {"assets": [{"name": "TagStudio-4.8.0-macOS-Apple-Chip.dmg"}]}
        self.assertIsNone(updater.platform_asset(only_arm, "darwin", "x86_64"))      # nie die falsche Architektur
        old = {"assets": [{"name": "TagStudio-4.0.0.dmg"}]}
        self.assertEqual(updater.platform_asset(old, "darwin", "x86_64")["name"], "TagStudio-4.0.0.dmg")

    def test_bundle_path(self):
        self.assertEqual(updater.mac_bundle("/Applications/TagStudio.app/Contents/MacOS/TagStudio"),
                         os.path.abspath("/Applications/TagStudio.app"))          # unter Windows mit Laufwerk
        self.assertEqual(updater.mac_bundle("/usr/bin/python3"), "")

    @unittest.skipIf(os.name == "nt" or not shutil.which("bash"), "braucht bash")
    def test_script_with_stub_tools(self):
        """Skript mit nachgestellten hdiutil/ditto/xattr/open: neue App ersetzt die alte, Sicherung bleibt; Pfade mit
        Umlaut, Leerzeichen und Hochkomma; bei kaputtem DMG bleibt die installierte App unverändert."""
        d = tempfile.mkdtemp(prefix="ts_mac_")
        self.addCleanup(shutil.rmtree, d, True)
        app = os.path.join(d, "Pro gramme", "TagStudio.app")
        os.makedirs(os.path.join(app, "Contents"))
        with open(os.path.join(app, "Contents", "version"), "w") as fh:
            fh.write("alt")
        content = os.path.join(d, "dmg-inhalt")
        os.makedirs(os.path.join(content, "TagStudio.app", "Contents"))
        with open(os.path.join(content, "TagStudio.app", "Contents", "version"), "w") as fh:
            fh.write("neu")
        upd = os.path.join(d, "Jürg O'Neil", "Updates")
        os.makedirs(upd)
        dmg = os.path.join(upd, "TagStudio-4.8.0-macOS-Apple-Chip.dmg")
        open(dmg, "w").close()
        stubs = os.path.join(d, "bin")
        os.makedirs(stubs)
        hdiutil = ('if [ "$1" = attach ]; then [ -s "$2" ] && exit 1; mnt="${@: -1}"; cp -R "CONTENT/." "$mnt/"; fi\n'
                   'exit 0').replace("CONTENT", content)
        tools = {"hdiutil": hdiutil, "ditto": 'cp -R "$1" "$2"', "xattr": "exit 0",
                 "open": 'echo "$1" >> "OPENED"'.replace("OPENED", os.path.join(d, "opened"))}
        for name, body in tools.items():
            with open(os.path.join(stubs, name), "w") as fh:
                fh.write("#!/bin/bash\n" + body + "\n")
            os.chmod(os.path.join(stubs, name), 0o700)
        log, bak = os.path.join(upd, "update-installer.log"), os.path.join(upd, "vorherige-Version")
        script = os.path.join(upd, "update.sh")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(updater.mac_update_script(dmg, 999999, app, log, bak))
        env = dict(os.environ, PATH=stubs + os.pathsep + os.environ["PATH"])
        r = subprocess.run(["bash", script], env=env, timeout=60)
        self.assertEqual(r.returncode, 0, open(log, encoding="utf-8").read())
        self.assertEqual(open(os.path.join(app, "Contents", "version")).read(), "neu")
        self.assertEqual(open(os.path.join(bak, "TagStudio.app", "Contents", "version")).read(), "alt")
        self.assertIn("OK", open(log, encoding="utf-8").read())
        self.assertEqual(open(os.path.join(d, "opened")).read().strip(), app)
        with open(dmg, "w") as fh:                                   # kaputtes DMG: Einhängen scheitert
            fh.write("kaputt")
        r = subprocess.run(["bash", script], env=env, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(open(os.path.join(app, "Contents", "version")).read(), "neu")
        self.assertIn("FEHLER: DMG nicht einhängbar", open(log, encoding="utf-8").read())

    def test_no_write_access(self):
        with mock.patch.object(updater.os, "access", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Schreibrechte"):
                updater.launch_mac_update("/x.dmg", tempfile.gettempdir(), "/Applications/TagStudio.app")


if __name__ == "__main__":
    unittest.main()
