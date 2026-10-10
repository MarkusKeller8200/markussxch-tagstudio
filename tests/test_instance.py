"""Nur eine Instanz (4.1.0): Sperre, Warten beim Neustart, zweiter Start endet mit Hinweis."""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import instance  # noqa: E402


class TestInstance(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="ts_inst_")
        self.path = os.path.join(self.dir, ".tagstudio.lock")

    def test_lock_and_release(self):
        a, b = instance.Instance(self.path), instance.Instance(self.path)
        self.assertTrue(a.acquire())
        self.assertFalse(b.acquire(0.3))
        a.release()
        self.assertTrue(b.acquire())
        b.release()

    def test_wait_for_old_instance(self):
        a, b = instance.Instance(self.path), instance.Instance(self.path)
        self.assertTrue(a.acquire())
        threading.Timer(0.5, a.release).start()
        t0 = time.monotonic()
        self.assertTrue(b.acquire(5.0))          # wie beim Neustart nach einem Update
        self.assertGreaterEqual(time.monotonic() - t0, 0.3)
        b.release()

    def test_second_start_exits(self):
        home = os.path.join(self.dir, "home")
        os.makedirs(home)
        env = dict(os.environ, HOME=home, USERPROFILE=home, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        env.pop("TAGSTUDIO_RESTART", None)
        first = subprocess.Popen([sys.executable, os.path.join(ROOT, "tagstudio_web.py"), "--browser", "--no-open", "--port", "0"],
                                 env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            line = ""
            for _ in range(50):                  # nur bis zur Adresszeile lesen (weitere Zeilen evtl. gepuffert)
                line = first.stdout.readline()
                if "http://" in line or not line:
                    break
            self.assertIn("http://", line)
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tagstudio_web.py"), "--browser", "--no-open", "--port", "0"],
                               env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(r.returncode, 0)
            self.assertIn("läuft bereits", r.stderr)
        finally:
            first.terminate()
            first.wait(10)


if __name__ == "__main__":
    unittest.main()
