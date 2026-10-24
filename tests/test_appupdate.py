"""#234: Update auf Knopfdruck – Installer laden, Prüfsumme, Windows-Skript (ohne Netz)."""
import hashlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import updater  # noqa: E402

DATA = b"MZ" + b"installer" * 50000
URL = updater.ASSET_HOST + "v4.8.0/TagStudio-4.8.0-Windows-Setup.exe"


class _Resp(io.BytesIO):
    headers = {"Content-Length": str(len(DATA))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class TestAppUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.asset = {"name": "TagStudio-4.8.0-Windows-Setup.exe", "url": URL, "size": len(DATA),
                      "digest": "sha256:" + hashlib.sha256(DATA).hexdigest()}

    def tearDown(self):
        self.tmp.cleanup()

    def dl(self, asset, **kw):
        return updater.download_asset(asset, self.tmp.name, opener=lambda req, timeout: _Resp(DATA), **kw)

    def test_download_checks_digest(self):
        seen = []
        p = self.dl(self.asset, progress=lambda d, t: seen.append((d, t)))
        with open(p, "rb") as fh:
            self.assertEqual(fh.read(), DATA)
        self.assertEqual(seen[-1], (len(DATA), len(DATA)))
        bad = dict(self.asset, digest="sha256:" + "0" * 64)
        os.remove(p)
        with self.assertRaisesRegex(ValueError, "Prüfsumme"):
            self.dl(bad)
        self.assertEqual(os.listdir(self.tmp.name), [])                     # nichts liegen geblieben

    def test_download_refuses_unsafe(self):
        with self.assertRaisesRegex(ValueError, "keine Prüfsumme"):
            self.dl(dict(self.asset, digest=""))
        with self.assertRaisesRegex(ValueError, "Download-Adresse"):
            self.dl(dict(self.asset, url="https://example.org/evil.exe"))
        with self.assertRaisesRegex(ValueError, "Download-Adresse"):
            self.dl(dict(self.asset, name=".."))
        with self.assertRaises(InterruptedError):
            self.dl(self.asset, cancelled=lambda: True)

    def test_platform_asset(self):
        rel = {"assets": [{"name": "TagStudio-4.8.0-macOS-Apple-Chip.dmg"}, {"name": "TagStudio-4.8.0-Windows-Setup.exe"}]}
        self.assertTrue(updater.platform_asset(rel, "win32")["name"].endswith(".exe"))
        self.assertTrue(updater.platform_asset(rel, "darwin", "arm64")["name"].endswith(".dmg"))
        self.assertIsNone(updater.platform_asset(rel, "linux"))
        with mock.patch.object(updater, "frozen", return_value=True):
            self.assertTrue(updater.auto_update_supported("win32"))
            self.assertTrue(updater.auto_update_supported("darwin"))             # #251
        with mock.patch.object(updater, "frozen", return_value=False):
            self.assertFalse(updater.auto_update_supported("win32"))             # Quellcode: git

    def test_windows_script(self):
        s = updater.windows_update_script(r"C:\Users\Jürg O'Neil\TagStudio\Updates\Setup.exe", 4242,
                                          r"C:\Users\Jürg\AppData\Local\Programs\TagStudio\TagStudio.exe",
                                          r"C:\Users\Jürg\TagStudio\Updates\update installer.log", False)
        self.assertIn("Get-Process -Id $p", s)
        self.assertIn("$p = 4242", s)
        self.assertIn("'C:\\Users\\Jürg O''Neil\\TagStudio\\Updates\\Setup.exe'", s)   # Hochkomma verdoppelt
        self.assertIn("'/VERYSILENT'", s)
        self.assertIn("'/CURRENTUSER'", s)
        self.assertIn("'/LOG=\"C:\\Users\\Jürg\\TagStudio\\Updates\\update installer.log\"'", s)
        self.assertIn("Start-Process -FilePath 'C:\\Users\\Jürg\\AppData\\Local\\Programs\\TagStudio\\TagStudio.exe'", s)
        self.assertIn("'/ALLUSERS'", updater.windows_update_script("a", 1, "b", "c", True))


if __name__ == "__main__":
    unittest.main()
