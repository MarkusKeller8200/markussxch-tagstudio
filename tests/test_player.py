"""Tests für den Vorschau-Player (media.py: Range-Server) und externe Player (players.py)."""
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import media  # noqa: E402
import players  # noqa: E402


class TestMedia(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tagstudio_media_")
        self.path = os.path.join(self.dir, "Täst Song.mp3")
        self.data = bytes(range(256)) * 400
        with open(self.path, "wb") as fh:
            fh.write(self.data)
        self.srv = media.MediaServer()

    def tearDown(self):
        self.srv.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def get(self, url, rng=None):
        req = urllib.request.Request(url, headers={"Range": rng} if rng else {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()

    def test_registry_limit(self):
        old = media.MAX_FILES
        media.MAX_FILES = 3
        try:
            paths = []
            for n in range(5):
                p = os.path.join(self.dir, f"{n}.mp3")
                with open(p, "wb") as fh:
                    fh.write(b"x" * 10)
                paths.append(p)
            urls = [self.srv.register(p) for p in paths]
            self.srv.register(paths[2])                      # zuletzt genutzt → bleibt
            self.srv.register(os.path.join(self.dir, "Täst Song.mp3"))
            live = [u for u in urls if self.srv.lookup("/" + u.split("/", 3)[3]) is not None]
            self.assertEqual(len(self.srv.files), 3)
            self.assertEqual(live, [urls[2], urls[4]])
        finally:
            media.MAX_FILES = old

    def test_full_and_range(self):
        url = self.srv.register(self.path)
        self.assertTrue(url.startswith("http://127.0.0.1:") and url.endswith(".mp3"))
        st, h, body = self.get(url)
        self.assertEqual((st, h["Content-Type"], body), (200, "audio/mpeg", self.data))
        self.assertEqual(h["Accept-Ranges"], "bytes")
        st, h, body = self.get(url, "bytes=100-199")
        self.assertEqual((st, body, h["Content-Range"]), (206, self.data[100:200], f"bytes 100-199/{len(self.data)}"))
        st, h, body = self.get(url, "bytes=-50")
        self.assertEqual(body, self.data[-50:])
        st, h, body = self.get(url, "bytes=1000-")
        self.assertEqual(body, self.data[1000:])
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get(url, f"bytes={len(self.data) + 5}-")
        self.assertEqual(cm.exception.code, 416)

    def test_only_registered_and_token(self):
        url = self.srv.register(self.path)
        for bad in (url.replace(self.srv.token, "falsch"), url.rsplit("/", 1)[0] + "/0123456789abcdef0123.mp3",
                    url.rsplit("/m/", 1)[0] + "/m/" + self.srv.token + "/../../etc/passwd"):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.get(bad)
            self.assertEqual(cm.exception.code, 404, bad)
        with self.assertRaises(ValueError):
            self.srv.register(os.path.join(self.dir, "bild.jpg"))


class TestPlayers(unittest.TestCase):
    def test_clean(self):
        out = players.clean([{"name": "", "cmd": '"C:\\Programme\\foobar2000\\foobar2000.exe"', "args": ""},
                             {"name": "leer", "cmd": ""}, "unsinn"])
        self.assertEqual(out, [{"name": "foobar2000", "cmd": "C:\\Programme\\foobar2000\\foobar2000.exe", "args": "{files}"}])

    def test_build_command(self):
        files = [os.path.abspath("a b.mp3"), os.path.abspath("-c.mp3")]
        p = {"name": "VLC", "cmd": "/usr/bin/vlc", "args": "--playlist-enqueue {files}"}
        self.assertEqual(players.build_command(p, files), ["/usr/bin/vlc", "--playlist-enqueue", *files])
        p = {"name": "X", "cmd": "/opt/x", "args": "-f {file} -d {folder} -l {m3u}"}
        cmd = players.build_command(p, files, m3u_factory=lambda fs: "/tmp/liste.m3u8")
        self.assertEqual(cmd, ["/opt/x", "-f", files[0], "-d", os.path.dirname(files[0]), "-l", "/tmp/liste.m3u8"])

    def test_m3u(self):
        d = tempfile.mkdtemp()
        try:
            p = players.write_m3u(["/x/ä.mp3", "/y/b.mp3"], folder=d)
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(fh.read().splitlines()[0], "#EXTM3U")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestSessionMedia(unittest.TestCase):
    def test_media_info_and_players(self):
        import time
        import core
        from session import Session
        from helpers import write_mp3, text
        d = tempfile.mkdtemp(prefix="tagstudio_pl_")
        old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        try:
            write_mp3(os.path.join(d, "a.mp3"), [text("TIT2", "Nordlicht"), text("TPE1", "Mara Lind"), text("TKEY", "Am")])
            s = Session()
            s.start_tag_load(d, False)
            while not s.task_status()["done"]:
                time.sleep(0.02)
            i = s.media_info("tag", 0)
            self.assertEqual((i["title"], i["artist"], i["key"]), ("Nordlicht", "Mara Lind", "8A"))
            with self.assertRaises(ValueError):
                s.media_info("tag", 5)
            with self.assertRaises(ValueError):
                s.media_info("side", "L")       # kein Vergleich geladen
            saved = s.set_players([{"name": "Test", "cmd": "/gibt/es/nicht", "args": "{files}"}])
            self.assertEqual(Session().players(), saved)
            r = s.play_external("tag", [0], 0)
            self.assertFalse(r["ok"])
            self.assertIn("nicht gefunden", r["error"])
        finally:
            core.CONFIG, core.CONFIG_OLD = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
