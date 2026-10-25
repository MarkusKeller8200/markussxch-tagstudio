"""ZIP-Downloads entpacken (#336)."""
import os
import shutil
import tempfile
import time
import unittest
import zipfile

import helpers  # noqa: F401 – Programmordner im Suchpfad
import unzip


class TestUnzip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def zip(self, name, members, age=60):
        p = os.path.join(self.dir, name)
        with zipfile.ZipFile(p, "w") as z:
            for n, data in members.items():
                z.writestr(n, data)
        t = time.time() - age
        os.utime(p, (t, t))
        return p

    def test_unpack_twenty_and_move(self):
        self.zip("Beatport.zip", {f"Beatport/{i:02d} Titel.mp3": b"ID3" + bytes([i]) for i in range(20)}
                 | {"Beatport/cover.jpg": b"x", "Beatport/._01 Titel.mp3": b"mac"})
        r = unzip.unpack_folders([self.dir])
        self.assertEqual((r["files"], r["skipped"], r["errors"]), (20, 0, []))
        self.assertEqual(len([n for n in os.listdir(self.dir) if n.endswith(".mp3")]), 20)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "cover.jpg")))       # nur Audio
        self.assertTrue(os.path.isfile(os.path.join(self.dir, unzip.DONE_DIR, "Beatport.zip")))   # verschoben, nicht gelöscht
        self.assertEqual(unzip.unpack_folders([self.dir])["zips"], [])               # nichts mehr zu tun

    def test_no_overwrite_and_unique_move(self):
        with open(os.path.join(self.dir, "a.mp3"), "wb") as fh:
            fh.write(b"alt")
        os.makedirs(os.path.join(self.dir, unzip.DONE_DIR))
        with open(os.path.join(self.dir, unzip.DONE_DIR, "x.zip"), "wb") as fh:
            fh.write(b"alt")
        self.zip("x.zip", {"a.mp3": b"neu", "b.mp3": b"neu"})
        r = unzip.unpack_folders([self.dir])
        self.assertEqual((r["files"], r["skipped"]), (1, 1))
        with open(os.path.join(self.dir, "a.mp3"), "rb") as fh:
            self.assertEqual(fh.read(), b"alt")
        self.assertIn("gibt es schon", r["zips"][0]["skipped"][0])
        self.assertTrue(r["zips"][0]["moved"].endswith("x (2).zip"))

    def test_unsafe_running_and_bad(self):
        self.zip("slip.zip", {"../../boese.mp3": b"x", "gut.mp3": b"y"})
        self.zip("frisch.zip", {"c.mp3": b"z"}, age=0)                             # Download läuft noch
        with open(os.path.join(self.dir, "d.zip.crdownload"), "wb") as fh:
            fh.write(b"teil")
        with open(os.path.join(self.dir, "kaputt.zip"), "wb") as fh:
            fh.write(b"kein zip")
        t = time.time() - 60
        os.utime(os.path.join(self.dir, "kaputt.zip"), (t, t))
        r = unzip.unpack_folders([self.dir])
        names = {z["zip"]: z for z in r["zips"]}
        self.assertEqual(set(names), {"slip.zip", "kaputt.zip"})
        self.assertIn("unsicherer Pfad", names["slip.zip"]["error"])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "gut.mp3")))         # ganzes ZIP abgelehnt
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "slip.zip")))
        self.assertIn("nicht lesbar", names["kaputt.zip"]["error"])
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "frisch.zip")))
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "d.zip.crdownload")))
        self.assertTrue(unzip._unsafe("C:/x.mp3") and unzip._unsafe("/x.mp3") and not unzip._unsafe("a/b.mp3"))


class TestUnzipSession(unittest.TestCase):
    def setUp(self):
        import core
        self.home = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.home, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.home, ".mp3tagcompare.json")

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def test_setting_and_own_dest(self):
        from session import Session
        dl = os.path.join(self.home, "dl")
        os.makedirs(dl)
        s = Session()
        s.purch_set_dest(dl)
        p = os.path.join(dl, "k.zip")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("k.mp3", b"x")
        t = time.time() - 60
        os.utime(p, (t, t))
        self.assertTrue(s.purch_state()["unzip"])
        s.set_unzip_auto(False)                                                        # aus → nichts passiert
        self.assertTrue(s.purch_unzip()["off"])
        self.assertTrue(os.path.isfile(p))
        s.set_unzip_auto(True)
        self.assertEqual(s.purch_unzip()["files"], 1)
        self.assertTrue(os.path.isfile(os.path.join(dl, "k.mp3")))


if __name__ == "__main__":
    unittest.main()
