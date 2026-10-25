"""Tests für die Ablage von Zugangsdaten (#287): DPAPI / Schlüsselbund / Rückfall-Datei."""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secretstore as ss  # noqa: E402

REAL = os.environ.get("TAGSTUDIO_REAL_SECRETS") == "1"


class FakeKeychain:
    def __init__(self, fail=False):
        self.items, self.fail = {}, fail

    def get(self, account):
        if self.fail:
            raise ss.KeychainError(-25293, "Lesen")
        return self.items.get(account)

    def set(self, account, data):
        if self.fail:
            raise ss.KeychainError(-25293, "Speichern")
        self.items[account] = bytes(data)

    def delete(self, account):
        self.items.pop(account, None)


class Ctx:
    def __init__(self, d):
        self.data_dir = d
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)


class FakeBackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kc = FakeKeychain()
        ss.backend = self.kc
        self.path = os.path.join(self.tmp.name, "token.bin")

    def tearDown(self):
        ss.backend = None
        self.tmp.cleanup()

    def test_write_read_delete_keychain(self):
        self.assertEqual(ss.write(self.path, b'{"a": 1}'), "keychain")
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), ss.MARK)           # kein Geheimnis in der Datei
        self.assertEqual(ss.read(self.path), b'{"a": 1}')
        self.assertTrue(ss.delete(self.path))
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.kc.items, {})
        self.assertIsNone(ss.read(self.path))

    def test_plaintext_is_migrated(self):
        with open(self.path, "wb") as fh:
            fh.write(b'{"secret": "x"}')
        self.assertEqual(ss.read(self.path), b'{"secret": "x"}')
        with open(self.path, "rb") as fh:
            self.assertEqual(fh.read(), ss.MARK)
        self.assertEqual(self.kc.items[ss.account_for(self.path)], b'{"secret": "x"}')

    def test_fallback_when_keychain_fails(self):
        ss.backend = FakeKeychain(fail=True)
        self.assertEqual(ss.write(self.path, b"geheim"), "file")
        self.assertIn("Schlüsselbund", ss.last_note())
        self.assertNotIn("geheim", ss.last_note())
        self.assertEqual(ss.read(self.path), b"geheim")
        if not sys.platform.startswith("win"):
            self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_accounts_separate_per_path(self):
        p2 = os.path.join(self.tmp.name, "other", "token.bin")
        ss.write(self.path, b"eins")
        ss.write(p2, b"zwei")
        self.assertEqual(ss.read(self.path), b"eins")
        self.assertEqual(ss.read(p2), b"zwei")
        self.assertFalse(os.path.exists(self.path + ".tmp"))

    def test_servicekit_uses_store(self):
        import servicekit
        ctx = Ctx(self.tmp.name)
        servicekit.save_keys(ctx, {"discogs": "DTOK", "leer": ""})
        with open(os.path.join(self.tmp.name, "keys.bin"), "rb") as fh:
            self.assertNotIn(b"DTOK", fh.read())
        self.assertEqual(servicekit.load_keys(ctx), {"discogs": "DTOK"})

    def test_beatport_token_and_app(self):
        import importlib.util
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = importlib.util.spec_from_file_location("bp_secret", os.path.join(here, "plugins", "beatport", "plugin.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ctx = Ctx(self.tmp.name)
        mod.save_app(ctx, "CID", "SECRET")
        mod.save_token(ctx, {"access_token": "AT", "refresh_token": "RT"})
        for name in ("app.bin", "token.bin"):
            with open(os.path.join(self.tmp.name, name), "rb") as fh:
                data = fh.read()
            self.assertNotIn(b"SECRET", data)
            self.assertNotIn(b"AT", data.replace(ss.MARK, b""))
        self.assertEqual(mod.load_app(ctx)["client_secret"], "SECRET")
        self.assertEqual(mod.load_token(ctx)["access_token"], "AT")
        self.assertTrue(mod.delete_token(ctx))
        self.assertIsNone(mod.load_token(ctx))
        self.assertTrue(mod.delete_app(ctx))
        self.assertEqual(self.kc.items, {})


@unittest.skipUnless(REAL, "nur im Workflow „Zugangsdaten-Test“ (echter Schlüsselbund / DPAPI)")
class RealStoreTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "keys.bin")
            data = json.dumps({"k": "wert-äöü"}).encode("utf-8")
            mode = ss.write(path, data)
            self.assertEqual(mode, "dpapi" if sys.platform.startswith("win") else
                             "keychain" if sys.platform == "darwin" else "file", ss.last_note())
            if mode != "file":
                with open(path, "rb") as fh:
                    self.assertNotIn(b"wert", fh.read())
            self.assertEqual(ss.read(path), data)
            ss.write(path, b"neu")                          # Aktualisieren eines bestehenden Eintrags
            self.assertEqual(ss.read(path), b"neu")
            self.assertTrue(ss.delete(path))
            self.assertIsNone(ss.read(path))

    @unittest.skipUnless(sys.platform == "darwin", "nur macOS")
    def test_migrate_plaintext(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "token.bin")
            with open(path, "wb") as fh:
                fh.write(b'{"access_token": "alt"}')
            self.assertEqual(ss.read(path), b'{"access_token": "alt"}')
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), ss.MARK)
            self.assertEqual(ss.read(path), b'{"access_token": "alt"}')
            ss.delete(path)


if __name__ == "__main__":
    unittest.main()
