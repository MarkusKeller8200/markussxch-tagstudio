"""Oberflächen-Tests im Browser (Playwright/Chromium) für die Web-Oberfläche.

Laufen nur auf Wunsch, weil sie Chromium, ffmpeg (für hörbare Test-Titel) und etwa zwei Minuten brauchen:

    TAGSTUDIO_UI_TESTS=1 python -m unittest discover -s tests -p "test_browser_ui.py" -v

Jeder Test startet TagStudio im Browser-Modus mit eigenem Benutzerordner (HOME) und eigener Bibliothek.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

WANT = os.environ.get("TAGSTUDIO_UI_TESTS") == "1"
try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
HAVE = WANT and sync_playwright is not None and shutil.which("ffmpeg") is not None


def make_library(folder, tones=(220, 330, 440), seconds=40, bpms=("124", "120", "")):
    """Drei hörbare Sinus-Titel (ffmpeg) mit Titel, Künstler und BPM."""
    os.makedirs(folder, exist_ok=True)
    for i, (f, bpm) in enumerate(zip(tones, bpms)):
        meta = ["-metadata", f"title=Ton {f}", "-metadata", "artist=Test"] + (["-metadata", f"TBPM={bpm}"] if bpm else [])
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={f}:duration={seconds}",
                        "-b:a", "128k", "-id3v2_version", "3", *meta, os.path.join(folder, f"0{i + 1} Ton {f}.mp3")], check=True)


@unittest.skipUnless(HAVE, "Oberflächen-Tests nur mit TAGSTUDIO_UI_TESTS=1, Playwright und ffmpeg")
class UiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="ts_ui_")
        cls.src = os.path.join(cls.base, "vorlage")
        make_library(cls.src)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="t_", dir=self.base)
        self.lib = os.path.join(self.dir, "lib")
        shutil.copytree(self.src, self.lib)
        self.home = os.path.join(self.dir, "home")
        os.makedirs(self.home)
        self.errors = []
        self.server, self.url = self.start_server()
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        self.ctx = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.pg = self.page()

    def tearDown(self):
        self.browser.close()
        self.pw.stop()
        self.server.terminate()
        self.server.wait(10)
        self.assertEqual(self.errors, [], "Fehler in der Seite")

    # ---------------------------------------------------------------- Hilfen
    def start_server(self):
        p = subprocess.Popen([sys.executable, os.path.join(ROOT, "tagstudio_web.py"), "--browser", "--no-open", "--port", "0"],
                             env=dict(os.environ, HOME=self.home, USERPROFILE=self.home),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for _ in range(200):
            m = re.search(r"(http://\S+)", p.stdout.readline() or "")
            if m:
                return p, m.group(1)
        p.terminate()
        raise RuntimeError("Server startet nicht")

    def page(self):
        pg = self.ctx.new_page()
        pg.set_default_timeout(8000)
        pg.on("pageerror", lambda e: self.errors.append(str(e)))
        pg.goto(self.url)
        pg.wait_for_function("typeof S !== 'undefined' && S.settings")
        for _ in range(30):                            # Hinweise beim Start (#78, Snapshots) schliessen
            time.sleep(0.1)
            if pg.locator("#modal").is_visible():
                pg.click("#mBtns button >> nth=0")
                time.sleep(0.3)
        return pg

    def cfg(self):
        with open(os.path.join(self.home, ".tagstudio.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def load_tagger(self):
        pg = self.pg
        pg.click('.nav[data-module="tagger"]')
        pg.fill("#tgPath", self.lib)
        pg.click("#tgLoad")
        pg.wait_for_function("TG.loaded && TG.rows.length === 3")

    def until(self, js, timeout=6.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.pg.evaluate(js):
                return True
            time.sleep(0.1)
        return False

    # ---------------------------------------------------------------- Tests
    def test_navigation_and_settings(self):
        """#88 Menü-Reihenfolge und Startseite, #87 Einstellungskacheln, #85/#86 Vorgaben, #89 Kanal."""
        pg = self.pg
        navs = pg.evaluate("[...document.querySelectorAll('.nav[data-module]')].map(b=>b.dataset.module)")
        self.assertEqual(navs, ["tagger", "fixer", "compare", "snapshots", "backups", "plugins", "settings", "db"])
        self.assertEqual(pg.evaluate("S.module"), "tagger")
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stUpdateCard")
        cards = pg.evaluate("[...document.querySelectorAll('#stGrid > .card')].filter(c=>!c.hidden).map(c=>c.id)")
        self.assertEqual(cards[:4], ["stLookCard", "stTaggerCard", "stFixerCard", "stCompareCard"])
        self.assertEqual(pg.locator("#stToc .chip").count(), len(cards))
        pg.select_option("#stVd_compare_filter", label="Unterschiede")
        pg.select_option("#stVd_tagger_sort", label="BPM ↓")
        pg.select_option("#stUpdCh", "beta")
        time.sleep(0.5)
        c = self.cfg()
        self.assertEqual((c["cmp_defaults"], c["tg_defaults"], c["update_channel"]),
                         ({"filter": "diff"}, {"sort_col": "TBPM", "sort_dir": -1}, "beta"))
        pg.click('.nav[data-module="compare"]')
        time.sleep(0.4)
        self.server.terminate()                        # Neustart: Vorgaben und letzte Seite gelten
        self.server.wait(10)
        self.server, self.url = self.start_server()
        pg2 = self.page()
        self.assertEqual((pg2.evaluate("S.module"), pg2.evaluate("S.opts.filter")), ("compare", "diff"))

    def test_player_live_doubleclick_rating(self):
        """#91 Live-Vorschau, #92 Doppelklick, #95/#96/#97 Bewertung und Like."""
        pg = self.pg
        self.load_tagger()
        pg.click(".tg-row >> nth=0")
        self.assertTrue(pg.evaluate("!PLAYER.audio.src || PLAYER.audio.paused"))
        pg.dblclick(".tg-row >> nth=1")
        self.assertTrue(self.until("PLAYER.ref === 1 && !PLAYER.audio.paused"))
        pg.click(".tg-row >> nth=2")
        time.sleep(0.5)
        self.assertEqual(pg.evaluate("PLAYER.ref"), 1)
        pg.click("#plLive")
        pg.click(".tg-row >> nth=0")
        self.assertTrue(self.until("PLAYER.ref === 0 && !PLAYER.audio.paused"))
        pg.click("#plRate .rs[data-star='4']")
        self.assertTrue(self.until("PLAYER.info.rating === 4"))
        pg.keyboard.press("f")
        self.assertTrue(self.until("PLAYER.info.like === true"))
        self.assertIn("★★★★", pg.inner_text(".tg-row[data-i='0'] .rate-mini"))

    def test_crossfade_with_tempo(self):
        """#94 Überblenden, #102 Tempo angleichen (124 → 120 BPM)."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("plSetPref('xfade', 2); plSetPref('xfade_return', 4)")
        pg.click(".tg-row >> nth=0")
        pg.keyboard.press(" ")
        self.assertTrue(self.until("!PLAYER.audio.paused && PLAYER.audio.duration > 0"))
        pg.evaluate("PLAYER.audio.currentTime = PLAYER.audio.duration - 3.2")
        self.assertTrue(self.until("!!PLAYER.fade && PLAYER.ref === 1"))
        self.assertTrue(self.until("Math.abs(PLAYER.audio.playbackRate - 124/120) < 0.002", 3))
        self.assertTrue(self.until("!PLAYER.fade && PLAYER.spare.paused", 4))
        self.assertTrue(self.until("PLAYER.audio.playbackRate === 1", 6))

    def test_player_b_and_detach(self):
        """#67/#68 Player B (nur oben, unter A, Ziel per Beschriftung), #69/#101 Abdocken mit B und Cover."""
        pg = self.pg
        self.load_tagger()
        self.assertFalse(pg.is_visible("#deckB"))
        pg.evaluate("plSetPref('layout','top'); plSetPref('deck2', true)")
        time.sleep(0.4)
        ra = pg.evaluate("document.querySelector('#player').getBoundingClientRect().toJSON()")
        rb = pg.evaluate("document.querySelector('#deckB').getBoundingClientRect().toJSON()")
        self.assertGreaterEqual(rb["top"], ra["bottom"])
        pg.click(".tg-row >> nth=1", button="right")
        pg.click('#menu button:has-text("In Player B laden")')
        self.assertTrue(self.until("DECKB.ref === 1 && !DECKB.audio.paused"))
        pg.click("#dbTag")
        self.assertEqual(pg.evaluate("PLAYER.target"), "B")
        with self.ctx.expect_page() as pi:
            pg.click("#plDetach")
        pop = pi.value
        pop.wait_for_selector('.pw[data-deck="B"]')
        self.assertEqual(pop.locator(".pw").count(), 2)
        pop.click('.pw[data-deck="B"] .pl-play')
        self.assertTrue(self.until("DECKB.audio.paused"))
        pop.close()
        self.assertTrue(self.until("!DET.on", 10))


if __name__ == "__main__":
    unittest.main()
