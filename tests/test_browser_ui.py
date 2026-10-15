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
        if "wizard" not in self._testMethodName:          # #167: ohne Einrichtungsassistent (bestehende Installation)
            from version import VERSION
            with open(os.path.join(self.home, ".tagstudio.json"), "w", encoding="utf-8") as fh:
                json.dump({"setup_done": "test", "seen_version": VERSION, "first_steps": False}, fh)
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

    def cfg_until(self, test, timeout=4.0):
        """Konfiguration lesen, bis test(cfg) wahr ist (Speichern ist teils verzögert)."""
        t0 = time.time()
        while True:
            try:
                c = self.cfg()
                if test(c) or time.time() - t0 > timeout:
                    return c
            except (OSError, ValueError):
                if time.time() - t0 > timeout:
                    raise
            time.sleep(0.1)

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
        self.assertEqual(navs, ["prep", "tagger", "fixer", "compare", "djset", "snapshots", "backups", "plugins", "settings", "help", "db"])
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
        # #139: zwei einzelne Klicks (Zähler e.detail beginnt wieder bei 1, wie bei neu gezeichneten, ziehbaren Zeilen)
        pg.evaluate("PLAYER.audio.pause()")
        pg.click('.tg-row[data-i="2"] .nm')
        pg.click('.tg-row[data-i="2"] .nm', delay=10)
        self.assertTrue(self.until("PLAYER.ref === 2 && !PLAYER.audio.paused"))
        time.sleep(0.6)
        pg.click('.tg-row[data-i="0"] .nm')                          # Einzelklick: spielt nicht
        time.sleep(0.6)
        self.assertEqual(pg.evaluate("PLAYER.ref"), 2)
        pg.click("#plLive")
        pg.click(".tg-row >> nth=0")
        self.assertTrue(self.until("PLAYER.ref === 0 && !PLAYER.audio.paused"))
        pg.click("#plRate .rs[data-star='4']")
        self.assertTrue(self.until("PLAYER.info.rating === 4"))
        pg.keyboard.press("f")
        self.assertTrue(self.until("PLAYER.info.like === true"))
        self.assertIn("★★★★", pg.inner_text(".tg-row[data-i='0'] .rate-mini"))

    def test_player_manual_tempo_and_goto_tagger(self):
        """#174 Tempo von Hand (Klick auf BPM, Reset), #175 laufenden Titel im Tagger zeigen."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="1"] .nm')
        pg.keyboard.press(" ")
        self.assertTrue(self.until("PLAYER.ref === 1 && !PLAYER.audio.paused && !!document.querySelector('#plMeta .pl-bpm')"))
        orig = pg.evaluate("bpmOf(PLAYER.info)")
        self.assertGreater(orig, 0)
        pg.click("#plMeta .pl-bpm")
        pg.wait_for_selector("#tpBpm")
        pg.fill("#tpBpm", str(round(orig * 1.05, 1)))
        pg.click("#mBtns .primary")
        self.assertTrue(self.until(f"Math.abs(PLAYER.audio.playbackRate - {round(orig * 1.05, 1)} / {orig}) < 0.002"))
        pg.wait_for_selector("#plMeta .pl-bpm.manual")
        pg.click("#plMeta .pl-bpm")
        pg.fill("#tpBpm", "1")                                                       # ausserhalb → Dialog bleibt offen
        pg.click("#mBtns .primary")
        self.assertTrue(pg.locator("#modal").is_visible())
        pg.click("#mBtns button >> text=Reset")
        self.assertTrue(self.until("PLAYER.audio.playbackRate === 1 && !document.querySelector('#plMeta .pl-bpm.manual')"))
        # #175: woanders hin, Markierung ändern, Filter setzen → Knopf führt zurück und markiert den laufenden Titel
        pg.click('.tg-row[data-i="0"] .nm')
        pg.fill("#tgQuery", "zzz-nichts")
        pg.wait_for_function("TG.order.length === 0")
        pg.click('.nav[data-module="compare"]')
        pg.click("#plGoto")
        self.assertTrue(self.until("S.module === 'tagger' && TG.sel.size === 1 && TG.sel.has(1) && TG.order.includes(1)"))
        self.assertEqual(pg.evaluate("PLAYER.ref"), 1)
        self.assertTrue(pg.evaluate("!PLAYER.audio.paused"))

    def test_metronome_resyncs_after_seek(self):
        """#181: Metronom plant nach einem Klick in den Titel erst wieder, wenn die Medienuhr eingeschwungen ist."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="0"] .nm')
        pg.keyboard.press(" ")
        self.assertTrue(self.until("!PLAYER.audio.paused && PLAYER.audio.currentTime > 0.5"))
        # Raster vorgeben (die Testtöne haben kein Serato-Grid), dann Metronom einschalten
        pg.evaluate("PLAYER.info.grid = {bpm: 124, markers: [{pos: 0, bpm: 124}], source: 'Test'}; plMetroToggle('A')")
        self.assertTrue(self.until("PL_METRO.deck === 'A' && PL_METRO.next !== null", 4))
        est = "plClockEstimate(PL_METRO.clk, performance.now(), PLAYER.audio.playbackRate || 1)"
        self.assertTrue(self.until(f"Math.abs({est} - PLAYER.audio.currentTime) < 0.06", 3))
        pg.evaluate("PLAYER.audio.currentTime = Math.min(PLAYER.audio.duration - 5, PLAYER.audio.currentTime + 7.3)")
        # unmittelbar nach dem Sprung: keine Klicks aus der alten Position, Uhr neu eingeschwungen
        self.assertTrue(self.until("PL_METRO.next === null || PL_METRO.clk.samples.length < 4", 1))
        self.assertTrue(self.until(f"PL_METRO.next !== null && Math.abs({est} - PLAYER.audio.currentTime) < 0.06", 4))
        pg.evaluate("plMetroStop(); PLAYER.audio.pause()")

    def test_help_licenses(self):
        """#176: Hilfe › Lizenzen listet die Fremdkomponenten mit Lizenz und Quelle."""
        pg = self.pg
        pg.click('.nav[data-module="help"]')
        pg.click('#helpTabs [data-htab="licenses"]')
        pg.wait_for_selector("#helpDoc .help-lic")
        txt = pg.inner_text("#helpDoc")
        for s in ("Lizenzen und Quellen", "GPL-3.0-or-later", "pywebview", "BSD-3-Clause", "serato-tags", "Im Programm enthalten"):
            self.assertIn(s, txt)
        self.assertGreater(pg.locator("#helpDoc a[data-url]").count(), 20)

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

    def test_tagger_state_restore(self):
        """#127: Tagger-Zustand (Ordner, Sortierung, Filter, Markierung) nach einem Neustart der App wiederherstellen;
        DJ-Set-Titel sind danach sofort geladen, auch wenn die App auf der DJ-Set-Seite startet."""
        pg = self.pg
        self.load_tagger()
        pg.click('#tgHead [data-sort="TIT2"]')
        pg.click('#tgHead [data-sort="TIT2"]')                      # absteigend
        pg.fill("#tgQuery", "Ton")
        pg.click('.tg-row[data-i="1"] .nm')
        pg.click('.tg-row[data-i="2"] .nm', modifiers=["Control"])
        pg.evaluate("call('dj_add', null)")
        c = self.cfg_until(lambda c: len(c.get("tagger_state", {}).get("sel", [])) == 2)
        st = c["tagger_state"]
        self.assertEqual((st["sort"], st["query"], st["root"]), ({"col": "TIT2", "dir": -1}, "Ton", self.lib))
        pg.click('.nav[data-module="djset"]')
        time.sleep(0.5)
        # App neu starten (neuer Server, gleiches Benutzerverzeichnis); #137: ohne Fortschrittsfenster einlesen
        self.ctx.add_init_script("""document.addEventListener('DOMContentLoaded', () => {
            window.__prog = 0; const el = document.getElementById('progress');
            new MutationObserver(() => { if (!el.hidden) window.__prog++; }).observe(el, {attributes: true}); });""")
        pg = self.restart()
        self.assertTrue(self.until("TG.loaded && TG.rows.length === 3", 15))
        self.assertEqual(pg.evaluate("window.__prog"), 0, "Fortschrittsfenster beim Start")
        self.assertIn("im Tagger", pg.inner_text("#statusText"))
        self.assertEqual(pg.evaluate("S.module"), "djset")
        self.assertEqual(pg.evaluate("[TG.sort.col, TG.sort.dir, document.querySelector('#tgQuery').value]"), ["TIT2", -1, "Ton"])
        self.assertEqual(sorted(pg.evaluate("[...TG.sel].map(i => TG.rows[i].rel)")), sorted(st["sel"]))
        self.assertTrue(self.until("DJ.st && DJ.st.items.length === 3 && DJ.st.items.every(r => !r.missing)", 10))
        # Einstellung „nichts“: Tagger bleibt beim nächsten Start leer
        pg.evaluate("call('set_view_default', 'tagger', 'start', 'none')")
        pg = self.restart()
        time.sleep(1.5)
        self.assertFalse(pg.evaluate("TG.loaded"))

    def restart(self):
        """App neu starten: neuer Server, gleiches Benutzerverzeichnis. Wie beim Schliessen des App-Fensters wird
        vorher der ausstehende Zustand gespeichert (appFlushState)."""
        self.pg.evaluate("appFlushState()")
        self.server.terminate(); self.server.wait(10)
        self.pg.close()
        self.server, self.url = self.start_server()
        self.pg = self.page()
        return self.pg

    def test_player_resume(self):
        """#126: Titel und Position je Player beim Schliessen merken, beim Start in Pause dort laden."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("plSetPref('layout','top'); plSetPref('deck2', true)")
        time.sleep(0.3)
        pg.dblclick('.tg-row[data-i="1"] .nm')
        self.assertTrue(self.until("PLAYER.ref === 1 && !PLAYER.audio.paused"))
        pg.evaluate("PLAYER.audio.currentTime = 12; PLAYER.audio.pause()")
        pg.evaluate("dbLoad({kind: 'tag', ref: 2}, false, 20)")
        self.assertTrue(self.until("DECKB.ref === 2 && DECKB.audio.currentTime > 19"))
        pg.evaluate("plResumeSave(true)")
        c = self.cfg_until(lambda c: (c.get("player_resume", {}).get("B") or {}).get("pos", 0) >= 19)
        self.assertAlmostEqual(c["player_resume"]["A"]["pos"], 12, delta=1)
        pg = self.restart()
        ok = self.until("PLAYER.info && PLAYER.ref === 1 && PLAYER.audio.paused && Math.abs(PLAYER.audio.currentTime - 12) < 1", 15)
        self.assertTrue(ok, pg.evaluate("call('tagger_settings').then(ts => call('player_resume').then(r => JSON.stringify({ts: [ts.start, ts.state], r, loaded: TG.loaded, info: !!PLAYER.info, ref: PLAYER.ref, t: PLAYER.audio.currentTime, done: RESUME.done, mod: S.module})))"))
        self.assertTrue(self.until("DECKB.info && DECKB.ref === 2 && DECKB.audio.paused && Math.abs(DECKB.audio.currentTime - 20) < 1", 10))
        # Autoplay nach dem Neustart: A spielt, B (war in Pause) bleibt in Pause
        pg.evaluate("call('set_player_pref', 'resume_play', 'play')")
        pg = self.restart()
        self.assertTrue(self.until("PLAYER.ref === 1 && !PLAYER.audio.paused && PLAYER.audio.currentTime >= 11.5", 15))
        self.assertTrue(self.until("DECKB.ref === 2 && DECKB.audio.paused", 10))
        # ausgeschaltet → Player startet leer
        pg.evaluate("call('set_player_pref', 'resume', false)")
        pg = self.restart()
        self.assertTrue(self.until("TG.loaded", 15))
        time.sleep(1)
        self.assertFalse(pg.evaluate("!!PLAYER.info"))

    def test_drag_to_player(self):
        """#105: Titel aus Tagger und Vergleich auf Player A/B ziehen; Ziel wird hervorgehoben."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("plSetPref('layout','top'); plSetPref('deck2', true)")
        time.sleep(0.4)
        pg.drag_and_drop('.tg-row[data-i="2"] .nm', "#player")
        self.assertTrue(self.until("PLAYER.ref === 2 && !PLAYER.audio.paused"))
        self.assertEqual(pg.locator(".player.drop-on").count(), 0)
        self.assertFalse(pg.evaluate("document.body.classList.contains('pl-dragging')"))
        pg.drag_and_drop('.tg-row[data-i="1"] .nm', "#deckB")       # A läuft → B lädt in Pause
        self.assertTrue(self.until("DECKB.ref === 1 && DECKB.audio.paused && !PLAYER.audio.paused"))
        pg.evaluate("PLAYER.audio.pause()")
        self.assertTrue(self.until("PLAYER.audio.paused"))
        pg.drag_and_drop('.tg-row[data-i="0"] .nm', "#deckB")       # nichts läuft → spielt
        self.assertTrue(self.until("DECKB.ref === 0 && !DECKB.audio.paused"))
        pg.evaluate("DECKB.audio.pause()")
        # Hervorhebung während des Ziehens
        pg.evaluate("""() => { const dt = new DataTransfer(); dt.setData(PL_DND, '{"kind":"tag","ref":0}');
            document.querySelector('#player').dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
        self.assertEqual(pg.locator("#player.drop-on").count(), 1)
        pg.evaluate("document.dispatchEvent(new DragEvent('dragend'))")
        self.assertEqual(pg.locator(".player.drop-on").count(), 0)
        # Vergleich: Paar ziehen → links/rechts wählen
        lib2 = os.path.join(self.dir, "lib2")
        shutil.copytree(self.lib, lib2)
        pg.click('.nav[data-module="compare"]')
        pg.fill("#pathL", self.lib)
        pg.fill("#pathR", lib2)
        pg.evaluate("void compare(true)")
        ok = self.until("S.pairs.length === 3", 10)
        self.assertTrue(ok, pg.evaluate("JSON.stringify({n: S.pairs.length, dlg: !document.querySelector('#dialog').hidden && document.querySelector('#dialog').textContent.slice(0, 200), st: document.querySelector('#statusText') && document.querySelector('#statusText').textContent})"))
        pg.drag_and_drop('.pair[data-i="0"]', "#player")
        pg.click('#menu button:has-text("Rechts in Player A laden")')
        self.assertTrue(self.until("PLAYER.kind === 'side' && PLAYER.ref === 'R' && S.cur === 0 && !PLAYER.audio.paused"))

    def test_compare_blob_and_json(self):
        """#13: Binärfeld-Editor und JSON-Baum auch im Vergleich."""
        from helpers import geob, text, txxx, write_mp3
        pg = self.pg
        a, b = os.path.join(self.dir, "A"), os.path.join(self.dir, "B")
        os.makedirs(a); os.makedirs(b)
        js = '{"cues": [{"name": "Drop", "pos": 32.5}], "bpm": 124}'
        write_mp3(os.path.join(a, "x.mp3"), [text("TIT2", "X"), geob("Probe JSON", js.encode(), "application/json"),
                                            txxx("DATA", js)])
        write_mp3(os.path.join(b, "x.mp3"), [text("TIT2", "X")])
        pg.click('.nav[data-module="compare"]')
        pg.fill("#pathL", a)
        pg.fill("#pathR", b)
        pg.evaluate("void compare(true)")
        self.assertTrue(self.until("S.pairs.length === 1 && S.view && S.view.rows.length > 1", 10))
        pg.evaluate("void selectPair(0)")
        self.assertTrue(self.until("S.view.rows.some(r => r.key === 'GEOB:Probe JSON' && r.L && r.L.blob)"))
        pg.dblclick('.tr[data-key="GEOB:Probe JSON"] .v[data-side="L"]')
        pg.wait_for_selector("#modal #bfTree")
        self.assertIn("(links)", pg.inner_text("#mTitle"))
        pg.click('#modal [data-bmode="text"]')
        pg.fill("#bfText", js.replace("124", "126"))
        pg.click("#mBtns .primary")
        self.assertTrue(self.until("S.view.rows.find(r => r.key === 'GEOB:Probe JSON').L.mod"))
        # Rechtsklick bietet den Binärfeld-Editor an
        pg.click('.tr[data-key="GEOB:Probe JSON"] .v[data-side="L"]', button="right")
        self.assertTrue(pg.locator("#menu button", has_text="Binärfeld-Editor (links)").is_visible())
        pg.evaluate("hideMenu()")
        # JSON in einem Textfeld → Baum
        pg.dblclick('.tr[data-key="TXXX:DATA"] .v[data-side="L"]')
        pg.wait_for_selector("#modal #jeTree")
        pg.click('#modal [data-jmode="text"]')
        pg.fill("#jeText", js.replace("Drop", "Break"))
        pg.click("#mBtns .primary")
        self.assertTrue(self.until("S.view.rows.find(r => r.key === 'TXXX:DATA').L.text.includes('Break')"))

    def test_journal_export_rows(self):
        """#59: Journal berechnen, Export-Menü, Zeilen je Feld mit Filter."""
        pg = self.pg
        lid = pg.evaluate(f"call('snap_add_library', {json.dumps(self.lib)}).then(r => r.library.id)")
        pg.evaluate(f"call('snap_create', '{lid}', 'Vorher', false, false)")
        self.assertTrue(self.until(f"call('snap_list', '{lid}').then(r => r.snapshots.length === 1)"))
        from id3tags import MP3File
        f = MP3File(os.path.join(self.lib, "01 Ton 220.mp3"))
        f.set_text("TKEY", "8A")
        f.set_text("TIT2", "Neu")
        f.save()
        t = time.time() + 5
        os.utime(f.path, (t, t))
        pg.click('.nav[data-module="snapshots"]')
        pg.wait_for_selector("#snRun")
        pg.wait_for_function("SN.lid && SN.a")
        pg.click("#snRun")
        pg.wait_for_function("SN.j && SN.j.rows.length === 1")
        pg.click("#snExport")
        self.assertTrue(pg.locator("#menu button", has_text="Excel (.xlsx)").is_visible())
        pg.evaluate("hideMenu()")
        rows = pg.evaluate("snExportRows()")
        self.assertEqual(sorted(r[5] for r in rows), ["TIT2", "TKEY"])
        self.assertEqual(rows[0][0], "01 Ton 220.mp3")
        pg.select_option("#snFkey", "TKEY")
        rows = pg.evaluate("snExportRows()")
        self.assertEqual([(r[5], r[6], r[7]) for r in rows], [("TKEY", "", "8A")])

    def test_help_page(self):
        """#158: Hilfe – Kapitel aufklappen, Bibliothek scannen, Zähler filtert im Tagger, Handbuch als Markdown."""
        from id3tags import MP3File
        f = MP3File(os.path.join(self.lib, "01 Ton 220.mp3"))
        f.set_text("TXXX:MEINFELD", "1")
        f.save()
        pg = self.pg
        pg.evaluate(f"call('set_default_dir', 'tagger', {json.dumps(self.lib)})")
        pg.click('.nav[data-module="help"]')
        pg.wait_for_selector('#helpChapters tr.help-sub[data-ch="ident"]')
        self.assertIn("TIT2", pg.inner_text("#helpChapters"))
        self.assertTrue(pg.locator('#helpChapters details[data-ch="software"]').count())
        pg.click("#helpScan")
        pg.wait_for_selector('#helpChapters tr[data-ch="custom"] [data-filter="TXXX:MEINFELD"]:not([data-mode])')
        self.assertIn("3 Titel", pg.inner_text("#helpScanInfo"))
        pg.fill("#helpQ", "meinfeld")
        self.assertEqual(pg.locator("#helpChapters tr.help-grp").count(), 1)
        pg.fill("#helpQ", "")
        # Gruppen: zuklappen/aufklappen, nach Gruppe filtern, sortieren
        n_ident = pg.locator('#helpChapters tr.help-sub[data-ch="ident"]').count()
        self.assertGreater(n_ident, 3)
        pg.click('#helpChapters tr.help-grp[data-ch="ident"] .tw')
        self.assertEqual(pg.locator('#helpChapters tr.help-sub[data-ch="ident"]').count(), 0)
        pg.click('#helpChapters tr.help-grp[data-ch="ident"]')
        self.assertEqual(pg.locator('#helpChapters tr.help-sub[data-ch="ident"]').count(), n_ident)
        pg.click('#helpGroups [data-grp="custom"]')
        self.assertEqual(pg.locator("#helpChapters tr.help-grp").count(), 1)
        pg.click('#helpGroups [data-grp=""]')
        self.assertGreater(pg.locator("#helpChapters tr.help-grp").count(), 5)
        pg.click('#helpChapters th[data-sort="mit"]')
        first = pg.locator('#helpChapters tr.help-sub[data-ch="ident"] td:nth-child(2)').first.inner_text()
        self.assertIn("TIT2", first)                                             # alle 3 Titel haben TIT2
        miss = '#helpChapters tr[data-ch="custom"] [data-filter="TXXX:MEINFELD"][data-mode="miss"]'
        self.assertEqual(pg.inner_text(miss).strip(), "2")                      # Spalte „Ohne“
        pg.click(miss)
        pg.wait_for_function("S.module === 'tagger' && TG.fieldFilter && TG.fieldFilter.mode === 'miss' && TG.order.length === 2")
        pg.click("#tgFieldFilter [data-ffx]")
        pg.wait_for_function("TG.order.length === 3 && !TG.fieldFilter")
        pg.click('.nav[data-module="help"]')
        pg.click('#helpChapters tr[data-ch="custom"] [data-filter="TXXX:MEINFELD"]:not([data-mode])')
        pg.wait_for_function("S.module === 'tagger' && TG.fieldFilter && TG.order.length === 1")
        self.assertIn("MEINFELD", pg.inner_text("#tgFieldFilter"))
        pg.click('#tgFieldFilter [data-ffm="miss"]')
        pg.wait_for_function("TG.order.length === 2")
        pg.click("#tgFieldFilter [data-ffx]")
        pg.wait_for_function("TG.order.length === 3 && !TG.fieldFilter")
        # Handbuch
        pg.click('.nav[data-module="help"]')
        pg.click('#helpTabs [data-htab="readme"]')
        pg.wait_for_selector("#helpDoc h2")
        self.assertTrue(pg.locator("#helpDoc table").count() >= 0)
        pg.click('#helpTabs [data-htab="id3"]')
        pg.wait_for_selector("#helpDoc table.help-t")
        pg.click('#helpTabs [data-htab="keys"]')                                  # #159
        pg.wait_for_selector("#helpDoc table.help-keys kbd")
        self.assertIn("A–B-Schleife", pg.inner_text("#helpDoc"))

    def test_recipe_dialog(self):
        """#111: Tag-Rezepte – Vorlage, Aktion hinzufügen, Vorschau, Anwenden."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("call('tag_set', [0], 'TIT2', 'Ton_220%20Mix')")
        pg.click('.tg-row[data-i="0"] .nm')
        pg.click("#tgRecipe")
        pg.wait_for_selector("#rcActs .rc-act")
        self.assertIn("Beatport", pg.inner_text("#rcSel"))
        pg.wait_for_function("document.querySelector('#tdPrev table') !== null")
        self.assertIn("Ton 220 Mix", pg.inner_text("#tdPrev"))
        n = pg.locator("#rcActs .rc-act").count()
        pg.select_option("#rcType", "set")
        pg.click("#rcAdd")
        pg.fill("#raField", "TXXX:QUELLE")
        pg.fill("#raValue", "Rezept")
        pg.click('#rcEdit [data-rce="ok"]')
        self.assertTrue(self.until(f"document.querySelectorAll('#rcActs .rc-act').length === {n + 1}"))
        self.assertTrue(self.until("document.querySelector('#tdPrev').textContent.includes('Rezept')"))
        pg.click("#mBtns .primary")
        pg.wait_for_function("TG.detail && TG.detail.common.TIT2.value === 'Ton 220 Mix'")

    def test_prepare_page(self):
        """#109: Vorbereiten – Workflow, Rezept-Schritt ausführen, Zelle als erledigt markieren, Bearbeiten-Dialog."""
        pg = self.pg
        inbox = os.path.join(self.dir, "Neu", "_01_Original")
        lib = os.path.join(self.dir, "Bib")
        shutil.copytree(self.lib, inbox)
        os.makedirs(lib)
        pg.click('.nav[data-module="prep"]')
        pg.wait_for_function("PREP.d && PREP.d.workflow")
        w = pg.evaluate("PREP.d.workflow")
        w.update(inbox=inbox, library=lib)
        pg.evaluate(f"call('prep_workflow_save', {json.dumps(w)}).then(prepApply)")
        pg.wait_for_function("PREP.d.rows.length === 3")
        self.assertEqual(pg.locator("#prepTable td.pc.s-open").count(), 3)
        self.assertEqual(pg.locator("#prepPaths .path-dir").count(), 3)                 # #177: Ordner grün
        self.assertNotEqual(pg.evaluate("getComputedStyle(document.querySelector('#prepPaths .path-dir')).color"),
                            pg.evaluate("getComputedStyle(document.querySelector('#prepPaths')).color"))
        pg.click('#prepSteps [data-run="s02"]')
        pg.wait_for_function("PREP.d.counts.s02.done === 3")
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "Neu", "_02_MP3Tag", "01 Ton 220.mp3")))
        pg.click('#prepTable tr[data-name="01 Ton 220.mp3"] td.pc[data-step="1"]')
        pg.click("#menu button >> text=Als erledigt markieren")
        pg.wait_for_function("PREP.d.counts.s03.done === 1")
        self.assertEqual(pg.inner_text("#prepCount").strip(), "3")                # noch nicht übernommen
        pg.click("#prepEdit")
        pg.wait_for_selector("#pwSteps .rc-act")
        pg.click('#pwSteps .rc-act[data-k="1"] [data-ps="edit"]')
        pg.fill("#psLabel", "03 Lautheit")
        pg.click('#pwEdit [data-pse="ok"]')
        pg.click("#mBtns .primary")
        pg.wait_for_function("PREP.d.workflow.steps[1].label === '03 Lautheit'")
        # Quelle (#118): Download-Ordner hinzufügen, abholen
        dl = os.path.join(self.dir, "Downloads")
        os.makedirs(dl)
        shutil.copy(os.path.join(inbox, "01 Ton 220.mp3"), os.path.join(dl, "Neu gekauft.mp3"))
        self.assertTrue(pg.locator("#prepFetch").is_hidden())
        pg.click("#prepEdit")
        self.assertEqual(pg.locator('#modal [data-pick="pwInbox"]').count(), 1)    # #161 Dateibrowser
        self.assertEqual(pg.locator('#modal [data-pick="pwLib"]').count(), 1)
        pg.click("#pwSrcAdd")
        self.assertEqual(pg.locator('.prep-src-row').count(), 1)                 # Handler früherer Dialoge laufen nicht mit
        self.assertEqual(pg.locator('.prep-src-row [data-pick]').count(), 1)
        pg.fill('.prep-src-row [data-f="name"]', "Bandcamp")
        pg.fill('.prep-src-row [data-f="folder"]', dl)
        pg.click("#mBtns .primary")
        pg.wait_for_function("PREP.d.workflow.sources.length === 1")
        self.assertIn("(1)", pg.inner_text("#prepFetch"))
        pg.click("#prepFetch")
        pg.wait_for_function("PREP.d.rows.length === 4")
        self.assertIn("Bandcamp", pg.inner_text('#prepTable tr[data-name="Neu gekauft.mp3"] .nm'))

    def test_discover_tab(self):
        """#120: Entdecken – Liste, Merken, Filter, Folgen-Dialog."""
        pg = self.pg
        d = os.path.join(self.home, "TagStudio", "Entdecken")
        os.makedirs(d, exist_ok=True)
        items = {f"deezer:{i}": {"key": f"deezer:{i}", "src": "deezer", "id": str(i), "artist": "Mara Lind", "title": f"Titel {i}",
                                 "mix": "", "label": "Nordwerk", "date": "2026-10-0%d" % i, "preview": "", "url": "https://www.deezer.com/track/1",
                                 "status": "new", "owned": i == 3, "first": "2026-10-11T10:00:00"} for i in (1, 2, 3)}
        with open(os.path.join(d, "entdecken.json"), "w", encoding="utf-8") as fh:
            json.dump({"follow": {"artists": ["Mara Lind"]}, "items": items}, fh)
        pg.click('.nav[data-module="prep"]')
        pg.wait_for_function("PREP.d && PREP.d.workflow")
        pg.click('#prepTabs [data-ptab="disc"]')
        pg.wait_for_function("DISC.d && DISC.d.items.length === 3")
        self.assertTrue(pg.locator("#prepWfPane").is_hidden())
        self.assertEqual(pg.locator("#discList tbody tr").count(), 2)          # vorhandener ausgeblendet
        pg.uncheck("#discHideOwned")
        self.assertEqual(pg.locator("#discList tbody tr").count(), 3)
        pg.click('#discList tr[data-k="deezer:2"] [data-a="saved"]')
        pg.wait_for_function("DISC.d.counts.saved === 1")
        pg.click('#discFilter [data-f="saved"]')
        self.assertEqual(pg.locator("#discList tbody tr").count(), 1)
        self.assertEqual(pg.inner_text("#discCount").strip(), "2")
        pg.click("#discFollow")
        pg.fill("#dfLab", "Nordwerk\nDrumcode")
        pg.click("#mBtns .primary")
        pg.wait_for_function("DISC.d.follow.labels.length === 2")
        pg.click('#prepTabs [data-ptab="wf"]')
        self.assertTrue(pg.locator("#discPane").is_hidden())

    def test_profiles(self):
        """#164/#165: Profil anlegen in den Einstellungen, Profilwahl beim Start (gleiches Profil → kein Neustart)."""
        pg = self.pg
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stProfiles .prof-row")
        self.assertIn("Standard", pg.inner_text("#stProfiles"))
        pg.fill("#profNew", "Frisch")
        pg.click("#profAdd")
        pg.wait_for_function("document.querySelectorAll('#stProfiles .prof-row').length === 2")
        self.assertTrue(os.path.isdir(os.path.join(self.home, "TagStudio-Profile", "Frisch")))
        pg.uncheck("#profAsk")
        time.sleep(0.3)
        with open(os.path.join(self.home, "TagStudio", "profile.json"), encoding="utf-8") as fh:
            self.assertFalse(json.load(fh)["ask"])
        # Startauswahl: Dialog zeigt beide Profile, „Standard“ bleibt → kein Neustart
        pg.evaluate("() => { window.__pp = profilePick({name: 'Standard', list: ['Standard', 'Frisch']}); }")
        pg.wait_for_selector('#modal input[name="profPick"][value="Frisch"]')
        pg.click("#mBtns .primary")
        self.assertFalse(pg.evaluate("window.__pp"))

    def test_wizard_first_start(self):
        """#167–#170: frisches Profil → Assistent; Einstellungen übernehmen; Empfehlung; Erste Schritte."""
        pg = self.pg
        pg.wait_for_selector("#wizard .wiz-box")
        self.assertIn("Willkommen", pg.inner_text("#wizard"))
        pg.check('#wizard [data-w="goal"][value="prep"]')
        pg.click('#wizard [data-wiz="next"]')                       # Speicherort: Laufwerke, Basisordner, Art
        self.assertTrue(pg.locator("#wizard .wiz-drive").count() >= 1)
        base = os.path.join(self.dir, "Musik")
        pg.fill("#wBase", base)
        pg.check('#wizard input[name="wMode"][value="struct"]')
        pg.click('#wizard [data-wiz="next"]')                       # Ordnerstruktur (Namen änderbar)
        pg.fill('#wizard [data-wname="new"]', "00_Neu")
        pg.click('#wizard [data-wiz="next"]')                       # Sicherheit
        pg.click('#wizard [data-wiz="next"]')                       # Programme
        pg.check('#wizard [data-w="prog"][value="mik"]')
        pg.click('#wizard [data-wiz="next"]')                       # Online
        pg.click('#wizard [data-wiz="next"]')                       # Darstellung
        pg.click('#wizard .wiz-theme [data-v="light"]')
        pg.click('#wizard [data-wiz="next"]')                       # Fertig
        self.assertIn(base, pg.inner_text("#wizard"))
        pg.click('#wizard [data-wiz="next"]')                       # Einrichten
        pg.wait_for_function("document.querySelector('#wizard').hidden")
        cfg = self.cfg()
        self.assertEqual(cfg["base_dir"], base)
        self.assertEqual(cfg["default_tagger"], os.path.join(base, "01_Library"))
        self.assertTrue(os.path.isdir(os.path.join(base, "00_Neu")))
        self.assertTrue(os.path.isdir(os.path.join(base, "99_Sicherung", "Snapshots")))
        self.assertEqual(cfg["web_theme"], "light")
        self.assertIn("prep", cfg["nav_recommended"])
        self.assertTrue(cfg["setup_done"])
        names = [w["steps"] for w in cfg["prep_workflows"]][0]
        labels = " ".join(st["label"] for st in names)
        self.assertIn("Mixed In Key", labels)
        self.assertNotIn("beaTunes", labels)                        # nicht gewählt → aus dem Workflow entfernt
        self.assertTrue(pg.locator('.nav[data-module="prep"] .rec-dot').count())
        # Erste Schritte auf der Startseite, „Verstanden“ blendet aus (Hinweise nach dem Assistenten zuerst schliessen)
        pg.wait_for_selector("#firstSteps:not([hidden])")
        for _ in range(20):
            time.sleep(0.2)
            if pg.locator("#modal").is_visible():
                pg.click("#mBtns button >> nth=0")
        pg.click('#firstSteps [data-fs="ok"]')
        pg.wait_for_selector("#firstSteps", state="hidden")
        # Menüpunkt ausblenden in den Einstellungen (Hinweise, die nach dem Assistenten kommen, schliessen)
        for _ in range(20):
            time.sleep(0.2)
            if pg.locator("#modal").is_visible():
                pg.click("#mBtns button >> nth=0")
        pg.click('.nav[data-module="settings"]')
        pg.uncheck('[data-navshow="djset"]')
        pg.wait_for_function("document.querySelector('.nav[data-module=\"djset\"]').hidden")

    def test_archive_tagger(self):
        """#173: Aussortieren im Tagger – Vorschau, verschieben, Liste neu geladen, zurückholen."""
        pg = self.pg
        arch = os.path.join(self.dir, "Archiv")
        pg.evaluate(f"call('set_archive_dir', {json.dumps(arch)})")
        self.load_tagger()
        n = pg.evaluate("TG.order.length")
        pg.click('.tg-row[data-i="0"] .nm')
        pg.click("#tgArchive")
        pg.wait_for_selector("#modal .fx-table")
        pg.click("#mBtns .primary")
        pg.wait_for_function(f"TG.order.length === {n - 1}")
        self.assertEqual(len([f for _d, _s, fs in os.walk(arch) for f in fs if f.endswith(".mp3")]), 1)
        pg.click('.nav[data-module="settings"]')
        pg.click('[data-stbase="archlist"]')
        pg.wait_for_selector("#modal [data-arid]")
        pg.check("#modal [data-arid]")
        pg.click("#mBtns .primary")
        for _ in range(50):
            if not [f for _d, _s, fs in os.walk(arch) for f in fs if f.endswith(".mp3")]:
                break
            time.sleep(0.1)
        self.assertEqual([f for _d, _s, fs in os.walk(arch) for f in fs if f.endswith(".mp3")], [])

    def test_snapshot_baseline(self):
        """Neue Baseline: aus dem aktuellen Stand, ältere Snapshots löschen (angeheftete nur auf Wunsch)."""
        pg = self.pg
        lid = pg.evaluate(f"call('snap_add_library', {json.dumps(self.lib)}).then(r => r.library.id)")
        for label, pin in (("Alt", False), ("Wichtig", True)):
            pg.evaluate(f"call('snap_create', '{lid}', '{label}', false, {str(pin).lower()})")
            for _ in range(100):
                if pg.evaluate(f"call('snap_list', '{lid}').then(r => r.snapshots.length)") >= (1 if label == "Alt" else 2):
                    break
                time.sleep(0.1)
        pg.click('.nav[data-module="snapshots"]')
        pg.wait_for_selector("#snSnaps [data-base]")
        self.assertEqual(pg.locator("#snLibs .sn-lib .r.path-dir").count(), 1)          # #178: Verzeichnis grün
        self.assertEqual(pg.locator("#snInfo .path-dir").count(), 1)
        pg.click("#snBaseline")
        pg.wait_for_function("document.querySelector('#sbInfo') && /1 ältere/.test(document.querySelector('#sbInfo').textContent)")
        self.assertIn("1 angeheftete", pg.inner_text("#sbInfo"))
        pg.click("#mBtns .primary")
        for _ in range(100):
            snaps = pg.evaluate(f"call('snap_list', '{lid}').then(r => r.snapshots.map(s => [s.label, !!s.baseline]))")
            if any(b for _l, b in snaps):
                break
            time.sleep(0.1)
        self.assertEqual(sorted(snaps), [["Baseline", True], ["Wichtig", False]])
        pg.wait_for_selector("#snSnaps .sn-base")

    def test_online_plugin(self):
        """#6–#8: Plugin Online-Metadaten – Schlüssel speichern (nie in der Konfiguration), Formular im Tagger."""
        pg = self.pg
        pg.click('.nav[data-module="plugins"]')
        card = '.pl-card[data-pid="online"]'
        pg.wait_for_selector(card)
        if not pg.locator(card + " [data-enable]").is_checked():
            pg.click(card + " .switch")
            pg.wait_for_selector(card + ' [data-paction="keys"]')
        self.assertIn("Schlüssel: keine", pg.inner_text(card))
        pg.click(card + ' [data-paction="keys"]')
        pg.wait_for_selector("#modal .pl-link")
        self.assertEqual(pg.locator("#modal .pl-link").count(), 6)              # Anleitung mit Links (#8)
        self.assertIn("discogs.com/settings/developers", pg.get_attribute("#modal .pl-link >> nth=0", "data-url"))
        pg.fill('#modal [data-ok="discogs"]', "geheim-123")
        pg.click("#mBtns .primary")
        pg.wait_for_selector("#modal .pl-log, #modal p")
        self.assertTrue(self.until("document.querySelector('#modal').textContent.includes('Schlüssel: Discogs')"))
        pg.click("#mBtns button >> nth=0")
        pg.wait_for_function(f"document.querySelector('{card}').textContent.includes('Schlüssel: Discogs')")
        with open(os.path.join(self.home, ".tagstudio.json"), encoding="utf-8") as fh:
            self.assertNotIn("geheim-123", fh.read())
        # Formular im Tagger (ohne Netzabfrage abbrechen)
        self.load_tagger()
        pg.click(".tg-row >> nth=0")
        pg.click('#tgPlugins [data-plugin="online"][data-action="fetch"]')
        pg.wait_for_selector('#modal [data-ok="mb"]')
        self.assertTrue(pg.locator('#modal [data-ok="mb"]').is_checked())
        self.assertFalse(pg.locator('#modal [data-ok="lastfm"]').is_checked())
        self.assertEqual(pg.locator('#modal [data-ok="mode"]').input_value(), "empty")

    def test_restart_and_quit_buttons(self):
        """#134/#132: Symbole unten in der Seitenleiste – Neustart stellt den Zustand wieder her, Beenden speichert
        und beendet den Server; ein zweiter Start während die erste Instanz läuft, endet sofort (#131)."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="2"] .nm')
        self.assertEqual(pg.locator("#sideWin .icon-btn").count(), 4)
        pg.evaluate("window.__alt = 1")
        pg.click("#winRestart")
        pg.wait_for_function("/startet neu/.test(document.querySelector('#progTitle').textContent)")
        try:
            pg.wait_for_function("!window.__alt && typeof TG !== 'undefined' && TG.loaded && TG.rows.length === 3", timeout=30000)
        except Exception:                                          # #193: Zustand für die Fehlersuche ausgeben
            self.fail("Neustart nicht abgeschlossen: " + pg.evaluate(
                "JSON.stringify({url: location.href, alt: !!window.__alt, prog: (document.querySelector('#progTitle') || {}).textContent, tg: typeof TG !== 'undefined' && TG.loaded})"))
        self.assertEqual(pg.evaluate("tgSelected()"), [2])
        lock = os.path.join(self.home, ".tagstudio.lock")
        with open(lock, encoding="utf-8") as fh:
            pid = int(fh.read().strip() or 0)
        self.assertNotEqual(pid, self.server.pid)                  # neue Instanz läuft
        pg.click("#winQuit")
        pg.wait_for_function("/beendet/.test(document.querySelector('#progTitle').textContent)", timeout=15000)
        for _ in range(50):
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
        else:
            os.kill(pid, 9)
            self.fail("Server läuft nach „Beenden“ weiter")
        c = self.cfg()
        self.assertEqual(c["tagger_state"]["sel"], ["03 Ton 440.mp3"])

    def test_expert_settings(self):
        """#133: Einstellungen › Expert – Diagnose, Einstellungsdatei (maskiert, Suche), Protokolle."""
        pg = self.pg
        pg.evaluate("call('set_option', 'theme', 'dark')")
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stExpertRows #stXConfig")
        self.assertIn("Expert", pg.inner_text("#stToc"))
        self.assertIn("Version", pg.inner_text("#stExpertRows"))
        pg.click("#stXConfig")
        pg.wait_for_selector("#xText")
        self.assertIn('"web_theme": "dark"', pg.input_value("#xText"))
        pg.fill("#xFind", "theme")
        self.assertTrue(self.until("/Treffer/.test(document.querySelector('#xHits').textContent)"))
        pg.click("#mBtns .primary")
        pg.click('#stExpertRows [data-xlog="app.log"]')
        pg.wait_for_selector("#xText")
        self.assertIn("Start ", pg.input_value("#xText"))
        pg.click("#mBtns .primary")

    def test_release_notes_older(self):
        """#136: Versionshinweise zeigen ältere Versionen aufklappbar (aus dem mitgelieferten CHANGELOG)."""
        pg = self.pg
        pg.click("#notesBtn")
        pg.wait_for_selector(".rn-older details.rn-ver", timeout=30000)
        self.assertGreaterEqual(pg.locator(".rn-older details.rn-ver").count(), 10)
        first = pg.locator(".rn-older details.rn-ver >> nth=0")
        self.assertEqual(first.locator(".rn-body").inner_html(), "")
        first.locator("summary").click()
        self.assertTrue(self.until("document.querySelector('.rn-older .rn-body').textContent.length > 20"))
        pg.click("#mBtns .primary")

    def test_mik_plugin_form(self):
        """#147: Plugin „Mixed In Key übernehmen“ steht im Tagger bereit und öffnet sein Formular."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="0"] .nm')
        pg.click('#tgPlugins [data-plugin="mik"][data-action="import"]')
        pg.wait_for_selector('#modal [data-ok="key"]')
        self.assertTrue(pg.locator('#modal [data-ok="key"]').is_checked())
        self.assertFalse(pg.locator('#modal [data-ok="clean_title"]').is_checked())
        pg.click("#mBtns button >> nth=0")

    def test_preview_links(self):
        """#144: Vorschau von Plugins zeigt Links zum Treffer auf der Plattform (je Datei und je Feld)."""
        pg = self.pg
        pg.evaluate("""void pluginPreview({label: 'Online-Metadaten holen …'}, {proposals: [
            {id: 0, name: 'a.mp3', group: 'a.mp3', gkey: 'a', label: 'Album (MusicBrainz)', old: '', new: 'Y', note: 'MB',
             checked: true, kind: 'text', hint: '', same: false, link: 'https://musicbrainz.org/recording/x', link_label: 'MusicBrainz'},
            {id: 1, name: 'a.mp3', group: 'a.mp3', gkey: 'a', label: 'Album (Deezer)', old: '', new: 'Z', note: 'MB',
             checked: false, kind: 'text', hint: 'Alternative', same: false, link: 'https://www.deezer.com/track/1', link_label: 'Deezer'},
            {id: 2, name: 'a.mp3', group: 'a.mp3', gkey: 'a', label: 'Label', old: 'Alt', new: 'Neu', note: 'MB',
             checked: true, kind: 'text', hint: '', same: false, link: '', link_label: ''}],
            log: []})""")
        pg.wait_for_selector("#modal .pv-links")
        self.assertIn("MusicBrainz ↗", pg.inner_text("#modal .pv-links"))
        self.assertIn("Deezer ↗", pg.inner_text("#modal .pv-links"))
        self.assertEqual(pg.locator("#modal tr:not(.pv-file) .pl-link").count(), 2)
        pg.click('#modal [data-pv="empty"]')                                   # #142: nur fehlende Felder
        self.assertEqual(pg.evaluate("[...document.querySelectorAll('#modal [data-pvi]')].map(c => c.checked)"), [True, True, False])
        pg.click('#modal [data-pv="default"]')
        self.assertEqual(pg.evaluate("[...document.querySelectorAll('#modal [data-pvi]')].map(c => c.checked)"), [True, False, True])
        pg.click("#mBtns button >> nth=0")

    def test_tagger_field_names_sort_cover(self):
        """#140/#151 Feldnamen wie in Mp3tag mit Erklärung, #141 Weitere Felder nach Herkunft, #150 Cover-Knöpfe."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="0"] .nm')
        pg.evaluate("call('tag_add_field', [0], 'TXXX', 'CATALOGNUMBER', 'POL042', false).then(taggerApplyDetail)")
        pg.evaluate("call('tag_add_field', [0], 'TXXX', 'MYFIELD', 'x', false).then(taggerApplyDetail)")
        pg.evaluate("call('tag_add_field', [0], 'TSST', '', 'Teil 1', false).then(taggerApplyDetail)")
        pg.wait_for_selector('.tg-f[data-key="TXXX:CATALOGNUMBER"]')
        pg.wait_for_selector('.tg-f[data-key="TSST"]')
        k = pg.inner_text('.tg-f[data-key="TXXX:CATALOGNUMBER"] .k')
        self.assertIn("CATALOGNUMBER Benutzertext", " ".join(k.split()))      # Feldname vorne, Art dahinter
        lab = pg.locator('label[for="tgf-TIT2"]')
        self.assertIn("TITLE", lab.inner_text())
        # #192: native title wird in den App-Tooltip (data-tip-title) übernommen
        self.assertIn("Mix-Name", lab.get_attribute("data-tip-title") or lab.get_attribute("title") or "")
        # Sortierung nach Herkunft: Beatport (CATALOGNUMBER) vor Feldern ohne bekannte Herkunft (MYFIELD)
        pg.click("#tgMoreSort")
        self.assertIn("Herkunft", pg.inner_text("#tgMoreSort"))
        keys = pg.evaluate("[...document.querySelectorAll('.tg-f')].map(e => e.dataset.key)")
        self.assertLess(keys.index("TXXX:CATALOGNUMBER"), keys.index("TXXX:MYFIELD"))
        self.assertEqual(keys[0], "TSST")                                      # offizielle ID3v2.4-Felder zuerst
        self.assertEqual(self.cfg_until(lambda c: c.get("web_ui", {}).get("tg_more_sort") == "src").get("web_ui", {}).get("tg_more_sort"), "src")
        # Cover-Knöpfe untereinander
        ys = pg.evaluate("['#tgCoverSet', '#tgCoverDel', '#tgCoverWeb'].map(s => document.querySelector(s).getBoundingClientRect().top)")
        self.assertTrue(ys[0] < ys[1] < ys[2], ys)
        # #150: links Länge/Bewertung, rechts Bild-Info über den Knöpfen
        g = pg.evaluate("""(() => { const r = (s) => document.querySelector(s).getBoundingClientRect();
          return {len: r('.tg-cover-side .tg-lenrate').left, btn: r('#tgCoverSet').left, hint: r('.tg-cover-btns .hint').top, set: r('#tgCoverSet').top}; })()""")
        self.assertLess(g["len"], g["btn"], g)
        self.assertLess(g["hint"], g["set"], g)

    def test_mood_field(self):
        """#12: Stimmung als Chips mit Vorschlägen, Mehrfachauswahl (teilweise vorhanden → allen geben), Spalte."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="0"] .nm')
        pg.wait_for_selector("#tgMoodIn")
        self.assertTrue(self.until("TG.moodSuggest && TG.moodSuggest.some(s => s.value === 'Uplifting')"))
        pg.fill("#tgMoodIn", "Dark, Driving")
        pg.keyboard.press("Enter")
        pg.wait_for_function("TG.detail.mood.all.length === 2")
        self.assertEqual(pg.locator("#tgMood .mood-chip").count(), 2)
        pg.click('#tgMood [data-mood-del="Driving"]')
        pg.wait_for_function("TG.detail.mood.all.join() === 'Dark'")
        pg.click('.tg-row[data-i="1"] .nm', modifiers=["Shift"])
        pg.wait_for_function("TG.detail.count === 2")
        part = pg.locator('#tgMood [data-mood-add="Dark"]')
        self.assertIn("1/2", part.inner_text())
        part.click()
        pg.wait_for_function("TG.detail.mood.all.join() === 'Dark' && !TG.detail.mood.some.length")
        pg.keyboard.press("Backspace") if pg.evaluate("document.activeElement.id") == "tgMoodIn" else None
        pg.wait_for_function("TG.detail.mood.all.length === 0")
        # Spalte „Stimmung“ zeigt den Wert aus TMOO bzw. TXXX:MOOD
        pg.evaluate("call('tag_mood', [2], ['Hypnotic'], []).then(taggerApplyDetail)")
        pg.evaluate("tgSetCols([...tgCols(), 'fld:TMOO'], true)")
        self.assertTrue(self.until("TG.rows[2] && TG.rows[2].x && TG.rows[2].x.TMOO === 'Hypnotic'"))

    def test_tagger_columns_sort_view(self):
        """#152 Spalten anordnen, #154 weitere Spalten, #148 waagrecht blättern, #153 Sortierstufen, #155 Ansicht."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("call('tag_add_field', [0, 1, 2], 'TXXX', 'CATALOGNUMBER', 'POL042', false)")
        # Spalte „Länge“ über das Menü
        pg.click("#tgColsBtn")
        pg.locator("#menu .menu-chk", has_text="Länge").click()
        pg.keyboard.press("Escape")
        pg.wait_for_selector('#tgHead [data-col="len"]')
        self.assertIn("0:40", pg.inner_text('.tg-row[data-i="0"]'))
        # eigenes Feld als Spalte
        pg.evaluate("tgSetCols([...tgCols(), 'fld:TXXX:CATALOGNUMBER'], true)")
        self.assertTrue(self.until("document.querySelector('.tg-row[data-i=\"0\"]').textContent.includes('POL042')"))
        # Spalte per Ziehen vor „Datei“ setzen
        pg.drag_and_drop('#tgHead [data-col="TIT2"]', '#tgHead [data-col="name"]')
        self.assertEqual(pg.evaluate("tgCols()[0]"), "TIT2")
        c = self.cfg_until(lambda c: (c.get("web_ui", {}).get("tg_cols") or [""])[0] == "TIT2")
        self.assertIn("fld:TXXX:CATALOGNUMBER", c["web_ui"]["tg_cols"])
        # zwei Sortierstufen, zurücksetzen
        pg.click('#tgHead [data-sort="TPE1"]')
        pg.click('#tgHead [data-sort="TIT2"]', modifiers=["Shift"])
        self.assertEqual(pg.evaluate("TG.sorts.map(s => s.col)"), ["TPE1", "TIT2"])
        self.assertIn("2", pg.inner_text('#tgHead [data-sort="TIT2"] sup'))
        self.assertTrue(pg.locator("#tgSortReset").is_visible())
        pg.click("#tgSortReset")
        self.assertEqual(pg.evaluate("TG.sorts.map(s => s.col)"), ["name"])
        # optimale Breite → waagrecht blättern, Kopfzeile läuft mit
        pg.evaluate("tgSetFit('scroll')")
        self.assertTrue(pg.evaluate("document.querySelector('#tgTable').classList.contains('hscroll')"))
        self.assertTrue(pg.evaluate("(() => { const s = document.querySelector('#tgScroll'); return s.scrollWidth > s.clientWidth; })()"))
        pg.evaluate("document.querySelector('#tgScroll').scrollLeft = 120; document.querySelector('#tgScroll').dispatchEvent(new Event('scroll'))")
        self.assertIn("translateX(-120px)", pg.evaluate("document.querySelector('#tgHead').style.transform"))
        # bevorzugte Ansicht speichern und wieder laden
        pg.evaluate("tgViewSave()")
        v = self.cfg_until(lambda c: c.get("web_ui", {}).get("tg_view_default", {}).get("fit") == "scroll")["web_ui"]["tg_view_default"]
        self.assertEqual(v["cols"][0], "TIT2")
        pg.evaluate("tgSetCols(TG_DEFAULT_COLS.slice(), false); tgSetFit('fit')")
        pg.evaluate("tgViewApply()")
        self.assertTrue(self.until("tgCols()[0] === 'TIT2' && LAYOUT.tg_fit === 'scroll'"))
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stTgViewInfo")
        self.assertIn("Titel", pg.inner_text("#stTgViewInfo"))
        self.assertIn("optimale Breite", pg.inner_text("#stTgViewInfo"))

    def test_serato_readable(self):
        """#76: Serato-Felder als lesbare Kurzfassung bei „Weitere Felder“ und im Binärfeld-Editor."""
        sys.path.insert(0, HERE)
        from helpers import geob, text, write_mp3
        from test_serato import AUTOTAGS, OVERVIEW, grid
        write_mp3(os.path.join(self.lib, "04 Serato.mp3"), [text("TIT2", "Serato"), geob("Serato BeatGrid", grid([], 0.25, 126.0)),
                                                            geob("Serato Autotags", AUTOTAGS), geob("Serato Overview", OVERVIEW)], audio_frames=400)
        pg = self.pg
        pg.click('.nav[data-module="tagger"]')
        pg.fill("#tgPath", self.lib)
        pg.click("#tgLoad")
        pg.wait_for_function("TG.loaded && TG.rows.length === 4")
        i = pg.evaluate("TG.rows.find(r => r.name.startsWith('04')).i")
        pg.click(f'.tg-row[data-i="{i}"] .nm')
        pg.wait_for_selector('.tg-f[data-key="GEOB:Serato BeatGrid"]')
        self.assertIn("126.0 BPM", pg.inner_text('.tg-f[data-key="GEOB:Serato BeatGrid"] .v'))
        pg.click('.tg-f[data-key="GEOB:Serato Overview"] [data-tedit]')
        pg.wait_for_selector("#modal .bf-serato")
        self.assertEqual(pg.locator("#modal .bf-ov rect").count(), 240)
        pg.click("#mBtns button >> nth=0")

    def test_beatgrid_sync(self):
        """#76: Beatgrid-Rechnung, Rasterlinien, Player B synchron zu Player A (Tempo und Takt)."""
        pg = self.pg
        g = pg.evaluate("""(() => { const g = {bpm: 120, markers: [{pos: 0.5, bpm: 120}, {pos: 32.5, bpm: 128}]};
            return [gridBeatAt(g, 0.5), gridBeatAt(g, 32.5), gridTimeOfBeat(g, 64), gridTimeOfBeat(g, 72),
                    gridAlign({bpm: 120, markers: [{pos: 0, bpm: 120}]}, 10.1, 0.5), gridPhase({bpm: 120, markers: [{pos: 0, bpm: 120}]}, 10.25)]; })()""")
        self.assertAlmostEqual(g[0], 0)
        self.assertAlmostEqual(g[1], 64)
        self.assertAlmostEqual(g[2], 32.5)
        self.assertAlmostEqual(g[3], 32.5 + 8 * 60 / 128, places=3)
        self.assertAlmostEqual(g[4], 10.25, places=3)
        self.assertAlmostEqual(g[5], 0.5, places=3)
        self.load_tagger()
        pg.evaluate("plSetPref('layout','top'); plSetPref('deck2', true)")
        time.sleep(0.3)
        pg.evaluate("plLoad({kind: 'tag', ref: 0}, true)")                  # 124 BPM
        pg.evaluate("dbLoad({kind: 'tag', ref: 1}, false)")                 # 120 BPM
        self.assertTrue(self.until("PLAYER.info && PLAYER.info.grid && DECKB.info && DECKB.info.grid"))
        self.assertEqual(pg.evaluate("[PLAYER.info.grid.bpm, PLAYER.info.grid.exact, DECKB.info.grid.bpm]"), [124, False, 120])
        pg.click("#dbSync")
        self.assertTrue(self.until("Math.abs(DECKB.audio.playbackRate - 124 / 120) < 0.001"), pg.evaluate("JSON.stringify([DECKB.audio.playbackRate, PLAYER.info.grid, DECKB.info.grid, PLAYER.info.wave && PLAYER.info.wave.beat])"))
        self.assertTrue(pg.evaluate("document.querySelector('#dbSync').classList.contains('on')"))

    def test_player_phase_alignment_and_bar_navigation(self):
        """#181/#182: Beatgrid auch am Anfang phasentreu ausrichten; Taktwege bei variablem Tempo."""
        pg = self.pg
        result = pg.evaluate("""(() => {
          const g = {bpm: 120, markers: [{pos: 0.5, bpm: 120}, {pos: 32.5, bpm: 128}]};
          const s = {bpm: 120, markers: [{pos: 0.3, bpm: 120}]};
          const targetPhase = 0.75;
          const align = gridAlign(s, 0, targetPhase, 1);
          const phase = gridPhase(s, align);
          const t0 = 30.5;
          const t1 = gridTimeOfBeat(g, gridBeatAt(g, t0) + 4);
          return { align, phase, targetPhase, t0, t1, beatDelta: gridBeatAt(g, t1) - gridBeatAt(g, t0) };
        })()""")
        self.assertGreaterEqual(result["align"], 0)
        self.assertAlmostEqual(result["phase"], result["targetPhase"], delta=1e-6)
        self.assertAlmostEqual(result["beatDelta"], 4, delta=1e-6)
        self.assertGreater(result["t1"], result["t0"])

    def test_player_bar_and_cue_keyboard(self):
        """#182: Navigation auf A/B sowie unbekanntes BPM und Cue-Sortierung."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("plSetPref('layout','top'); plSetPref('deck2',true)")
        pg.evaluate("plLoad({kind:'tag',ref:0},false)")
        self.assertTrue(self.until("PLAYER.info && PLAYER.audio.readyState >= 1 && PLAYER.audio.duration > 1"))
        pg.evaluate("PLAYER.info.grid={bpm:120,markers:[{pos:0,bpm:120}]}; PLAYER.audio.currentTime=10")
        pg.keyboard.press("ArrowRight")
        self.assertAlmostEqual(pg.evaluate("PLAYER.audio.currentTime"), 12, delta=0.35)
        pg.keyboard.press("ArrowLeft")
        self.assertAlmostEqual(pg.evaluate("PLAYER.audio.currentTime"), 10, delta=0.35)
        pg.evaluate("""PLAYER.info.cues=[{pos:22,kind:'cue'},{pos:8,kind:'cue'},{pos:12,kind:'loop',end:14}]; PLAYER.audio.currentTime=10""")
        pg.keyboard.press("Shift+ArrowRight")
        self.assertAlmostEqual(pg.evaluate("PLAYER.audio.currentTime"), 22, delta=0.35)
        pg.keyboard.press("Shift+ArrowLeft")
        self.assertAlmostEqual(pg.evaluate("PLAYER.audio.currentTime"), 8, delta=0.35)
        pg.evaluate("dbLoad({kind:'tag',ref:1},false)")
        self.assertTrue(self.until("DECKB.info && DECKB.audio.readyState >= 1 && DECKB.audio.duration > 1"))
        pg.evaluate("DECKB.info.grid={bpm:120,markers:[{pos:0,bpm:120}]}; DECKB.audio.currentTime=10; dbTargetSet('B')")
        pg.keyboard.press("ArrowRight")
        self.assertAlmostEqual(pg.evaluate("DECKB.audio.currentTime"), 12, delta=0.35)
        pg.evaluate("DECKB.info.cues=[{pos:3,kind:'cue'},{pos:21,kind:'cue'}]; DECKB.audio.currentTime=10")
        pg.keyboard.press("Shift+ArrowRight")
        self.assertAlmostEqual(pg.evaluate("DECKB.audio.currentTime"), 21, delta=0.35)

    def test_beat_analysis(self):
        """#76: Schlag aus dem Audio – 124 BPM, erster Schlag bei 0,3 s – wird erkannt und als Beatgrid genutzt."""
        P = 60 / 124
        expr = f"0.9*sin(2*PI*55*t)*exp(-25*mod(t-0.3+{20 * P},{P}))"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=22050:d=40",
                        "-b:a", "128k", "-id3v2_version", "3", "-metadata", "title=Beat", "-metadata", "TBPM=124",
                        os.path.join(self.lib, "04 Beat.mp3")], check=True)
        pg = self.pg
        pg.click('.nav[data-module="tagger"]')
        pg.fill("#tgPath", self.lib)
        pg.click("#tgLoad")
        pg.wait_for_function("TG.loaded && TG.rows.length === 4")
        i = pg.evaluate("TG.rows.find(r => r.name.startsWith('04')).i")
        pg.evaluate(f"plLoad({{kind: 'tag', ref: {i}}}, false)")
        self.assertTrue(self.until("PLAYER.info && PLAYER.ref === " + str(i)))
        beat = pg.evaluate("plWaveCompute(PLAYER.info).then(w => w && w.beat)")
        self.assertIsNotNone(beat)
        self.assertAlmostEqual(beat["bpm"], 124, delta=0.3)
        ph = (beat["first"] - 0.3) % P
        self.assertLess(min(ph, P - ph), 0.02, beat)                      # Versatz auf ±20 ms genau
        self.assertEqual(pg.evaluate("PLAYER.info.grid.source"), "Analyse")
        # gespeichert: beim nächsten Laden kommt das Beatgrid aus dem Cache
        pg.evaluate(f"plLoad({{kind: 'tag', ref: {i}}}, false)")
        self.assertTrue(self.until("PLAYER.info && PLAYER.info.grid && PLAYER.info.grid.source === 'Analyse'"))

    def test_tagger_feature_columns(self):
        """#11: Spalten mit Audio-Merkmalen, Sortierung und Zahlenfilter im Suchfeld."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("call('tag_feature_set', [0], 'ENERGY', '80')")
        pg.evaluate("call('tag_feature_set', [1], 'ENERGY', '40')")
        pg.evaluate("taggerRefresh()")
        pg.click("#tgFeatCols")
        pg.locator("#menu button", has_text="Energy – ").click()
        pg.wait_for_selector('#tgHead [data-sort="f:ENERGY"]')
        # #149: Häkchen, Menü bleibt offen – zweites Merkmal an und wieder aus
        self.assertTrue(pg.locator("#menu").is_visible())
        self.assertEqual(pg.locator("#menu button", has_text="Energy – ").get_attribute("aria-checked"), "true")
        pg.locator("#menu .menu-chk >> nth=1").click()
        self.assertEqual(pg.evaluate("LAYOUT.tg_feat_cols.length"), 2)
        pg.locator("#menu .menu-chk >> nth=1").click()
        self.assertEqual(pg.evaluate("LAYOUT.tg_feat_cols"), ["ENERGY"])
        pg.keyboard.press("Escape")
        self.assertEqual(pg.locator("#tgInner .ft-c").count(), 2)
        self.assertEqual(self.cfg_until(lambda c: "tg_feat_cols" in c.get("web_ui", {}))["web_ui"]["tg_feat_cols"], ["ENERGY"])
        # Sortieren nach Energy: 40 vor 80, leere ans Ende
        pg.click('#tgHead [data-sort="f:ENERGY"]')
        self.assertEqual(pg.evaluate("TG.order.map(i => TG.rows[i].feat.ENERGY)"), [40, 80, None])
        # Filter
        for q, n in (("energy>=70", 1), ("Energie ≥ 30", 2), ("bpm:118-125", 2), ("dance<10", 0), ("Ton 220 energy>50", 1)):
            pg.fill("#tgQuery", q)
            self.assertTrue(self.until(f"TG.order.length === {n}"), q)
        pg.fill("#tgQuery", "")
        self.assertTrue(self.until("TG.order.length === 3"))
        # Skala 0–10: Anzeige bleibt 0–100, gespeichert wird ÷10
        pg.click('.nav[data-module="settings"]')
        pg.select_option("#stFeatScale", "10")
        self.assertEqual(self.cfg_until(lambda c: c.get("feat_scale") == 10).get("feat_scale"), 10)
        pg.select_option("#stFeatScale", "100")

    def test_queue_and_saved_lists(self):
        """#138: Warteschlange (Als Nächstes spielen, ⏭, Dialog) und gespeicherte DJ-Set-Listen."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="1"]', button="right")
        pg.click("#menu button >> text=Als Nächstes spielen")
        pg.wait_for_function("PQ.items.length === 1")
        pg.click('.tg-row[data-i="2"]', button="right")
        pg.click("#menu button >> text=Zur Warteschlange hinzufügen")
        pg.wait_for_function("PQ.items.length === 2 && PQ.items[1].i === 2")
        self.assertEqual(pg.inner_text("#plQueueN").strip(), "2")
        pg.evaluate("plLoad({kind: 'tag', ref: 0}, true)")
        self.assertTrue(self.until("PLAYER.ref === 0 && !PLAYER.audio.paused"))
        pg.click("#plNext")                                     # Warteschlange vor Tagger-Reihenfolge
        self.assertTrue(self.until("PLAYER.ref === 1 && PQ.items.length === 1 && PQ.items[0].i === 2"))
        self.assertEqual(self.cfg_until(lambda c: len(c.get("player_queue", [])) == 1)["player_queue"][0].endswith(".mp3"), True)
        pg.click("#plQueue")
        pg.wait_for_selector("#pqList .pq-row")
        self.assertEqual(pg.locator("#pqList .pq-row").count(), 1)
        pg.click("#mBtns button >> text=Als DJ-Set übernehmen")
        pg.wait_for_function("DJ.st && DJ.st.items.length === 1")
        pg.keyboard.press("Space")
        # DJ-Set als Liste speichern, neue Liste, wieder laden
        pg.click('.nav[data-module="djset"]')
        pg.wait_for_function("DJ.st && DJ.st.items.length === 1")
        pg.click("#djListBtn")
        pg.click("#menu button >> text=Speichern unter")
        pg.fill("#djNameIn", "Probe")
        pg.click("#mBtns .primary")
        pg.wait_for_function("DJ.st.name === 'Probe' && !DJ.st.dirty")
        self.assertIn("Probe", pg.inner_text("#djListName"))
        pg.click("#djAllTagger")
        pg.wait_for_function("DJ.st.items.length === 3 && DJ.st.dirty")
        pg.click("#djListBtn")
        pg.click("#menu button >> text=Neue, leere Liste")
        pg.wait_for_selector("#mBtns button >> text=Verwerfen")
        pg.click("#mBtns button >> text=Verwerfen")
        pg.wait_for_function("DJ.st.items.length === 0 && DJ.st.name === ''")
        pg.click("#djListBtn")
        pg.click("#menu button >> text=Probe (1)")
        pg.wait_for_function("DJ.st.items.length === 1 && DJ.st.name === 'Probe'")
        self.assertEqual(list(self.cfg_until(lambda c: "Probe" in c.get("djset_saved", {}))["djset_saved"]), ["Probe"])

    def test_djset_page(self):
        """#3 DJ-Set: aus dem Tagger übernehmen, optimieren, sperren, ziehen, Tasten, Wiedergabe, gemerkte Optionen."""
        pg = self.pg
        self.load_tagger()
        for i, (key, bpm) in enumerate((("10A", "124"), ("8A", "120"), ("9A", "122"))):
            pg.evaluate(f"call('tag_set', [{i}], 'TKEY', '{key}')")
            pg.evaluate(f"call('tag_set', [{i}], 'TBPM', '{bpm}')")
        # Kontextmenü im Tagger bietet „Zum DJ-Set hinzufügen“
        pg.click('.tg-row[data-i="0"]', button="right")
        self.assertTrue(pg.locator("#menu button", has_text="Zum DJ-Set hinzufügen").is_visible())
        pg.keyboard.press("Escape")
        pg.evaluate("hideMenu()")
        pg.click('.nav[data-module="djset"]')
        pg.click("#djAllTagger")
        pg.wait_for_function("DJ.st && DJ.st.items.length === 3")
        self.assertEqual(pg.inner_text("#djCount").strip(), "3")        # Anzahl in der Seitenleiste
        self.assertEqual(pg.locator("#djList .dj-row").count(), 3)
        self.assertEqual(pg.locator("#djList .dj-tr").count(), 2)
        before = pg.evaluate("DJ.st.score")
        pg.click("#djOpt")
        pg.wait_for_function("DJ.st.method === 'exact'")
        keys = pg.evaluate("DJ.st.items.map(r => r.key)")
        self.assertIn(keys, (["8A", "9A", "10A"], ["10A", "9A", "8A"]))
        self.assertGreaterEqual(pg.evaluate("DJ.st.score"), before)
        self.assertEqual(pg.locator("#djWheel .wk.on").count(), 3)
        self.assertEqual(pg.locator("#djCurve svg").count(), 1)
        # #192: nur TagStudio-Tooltips – keine title-Attribute und keine SVG-<title> (Browser-Tooltips) im Dokument
        self.assertEqual(pg.evaluate("document.querySelectorAll('[title], svg title').length"), 0)
        self.assertGreater(pg.locator("#djCurve circle[data-tip-title]").count(), 0)
        # Vorher/Nachher
        pg.click("#djRevert")
        pg.wait_for_function("DJ.st.items[0].key === '10A' && DJ.st.items[1].key === '8A'")
        pg.click("#djRevert")
        pg.wait_for_function(f"DJ.st.items[0].key === '{keys[0]}'")
        # Sperren per Knopf, dann Ziehen: erste Zeile ans Ende
        pg.click('#djList .dj-row[data-k="0"] [data-lock]')
        pg.wait_for_function("DJ.st.items[0].lock")
        self.assertEqual(pg.locator("#djList .dj-row.locked").count(), 1)
        first = pg.evaluate("DJ.st.items[0].path")
        box = pg.locator('#djList .dj-row[data-k="2"]').bounding_box()
        pg.drag_and_drop('#djList .dj-row[data-k="0"] .h', '#djList .dj-row[data-k="2"]',
                         target_position={"x": 40, "y": box["height"] - 4})
        pg.wait_for_function(f"DJ.st.items[2].path === {json.dumps(first)}")
        # Tasten: Zeile wählen, Alt+↑ verschiebt, G entsperrt, Enter spielt
        pg.click('#djList .dj-row[data-k="2"] .t')
        pg.keyboard.press("Alt+ArrowUp")
        pg.wait_for_function(f"DJ.st.items[1].path === {json.dumps(first)}")
        pg.keyboard.press("g")
        pg.wait_for_function("!DJ.st.items.some(r => r.lock)")
        pg.keyboard.press("Enter")
        self.assertTrue(self.until(f"PLAYER.kind === 'tag' && !PLAYER.audio.paused && PLAYER.info.path === {json.dumps(first)}"))
        pg.keyboard.press("Space")
        # Optionen werden gemerkt
        pg.click('#djProfile [data-prof="rise"]')
        pg.wait_for_function("DJ.st.opts.profile === 'rise' && DJ.st.energy_fit !== null")
        self.assertEqual(self.cfg()["djset_opts"]["profile"], "rise")
        self.assertEqual(len(self.cfg()["djset_items"]), 3)
        # Entfernen per Entf
        pg.click('#djList .dj-row[data-k="0"] .t')
        pg.keyboard.press("Delete")
        pg.wait_for_function("DJ.st.items.length === 2")
        # Neu laden: Set und Seite bleiben
        pg.reload()
        pg.wait_for_function("typeof S !== 'undefined' && S.settings")
        ok = self.until("S.module === 'djset' && DJ.st && DJ.st.items.length === 2")
        self.assertTrue(ok, pg.evaluate("JSON.stringify({m: S.module, n: DJ.st && DJ.st.items.length})"))
        # #4: Export-Menü und Spurnummern in Set-Reihenfolge
        pg.click("#djExport")
        self.assertEqual(pg.locator("#menu button").count(), 5)
        pg.click("#menu button >> text=Spurnummern")
        pg.wait_for_selector("#djNumPrev table")
        self.assertEqual(pg.locator("#djNumPrev tbody tr").count(), 2)
        pg.click("#mBtns .primary")
        order = pg.evaluate("DJ.st.items.map(r => r.i)")
        for _ in range(30):                             # Übernehmen läuft asynchron
            rows = pg.evaluate("call('tag_rows').then(t => t.rows.map(r => r.TRCK))")
            if [rows[order[0]], rows[order[1]]] == ["1/2", "2/2"]:
                break
            time.sleep(0.1)
        self.assertEqual([rows[order[0]], rows[order[1]]], ["1/2", "2/2"])


if __name__ == "__main__":
    unittest.main()
