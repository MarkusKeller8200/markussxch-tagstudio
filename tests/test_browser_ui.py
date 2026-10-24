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
                             env=dict(os.environ, HOME=self.home, USERPROFILE=self.home, PYTHONUNBUFFERED="1"),
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for _ in range(200):
            m = re.search(r"(http://\S+)", p.stdout.readline() or "")
            if m:
                return p, m.group(1)
        p.terminate()
        raise RuntimeError("Server startet nicht")

    def page(self, init=None):
        pg = self.ctx.new_page()
        if init:
            pg.add_init_script(init)
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
        """Warten, bis js wahr ist. Ein abgelehnter Aufruf (z. B. Snapshot wird gerade geschrieben) zählt als „noch
        nicht“ – erst nach Ablauf der Zeit wird der letzte Fehler gemeldet."""
        t0, err = time.time(), None
        while time.time() - t0 < timeout:
            try:
                if self.pg.evaluate(js):
                    return True
                err = None
            except Exception as ex:  # noqa: BLE001 – Playwright meldet abgelehnte Promises als Error
                if "Target" in type(ex).__name__ or "closed" in str(ex):
                    raise
                err = ex
            time.sleep(0.1)
        if err is not None:
            raise err
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
        dv = pg.evaluate("S.settings.dev || {}")                        # #233: Developer Release zeigt die geplante Version
        if dv.get("dev"):
            self.assertIn(f"Version {dv['planned']}", pg.inner_text("#ver"))
            self.assertIn("Developer Release", pg.inner_text("#ver"))
        # #233: Quellcode – drei Kanäle, „Entwicklung“ nur hier
        self.assertEqual(pg.evaluate("[...document.querySelectorAll('#stUpdCh option')].map((o) => o.value)"), ["stable", "beta", "dev"])
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

    def test_player_bpm_doubleclick_and_wheel(self):
        """#194: Mausrad über BPM ändert das Tempo (±0,1, Shift ±1), Doppelklick setzt das Originaltempo."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="1"] .nm')
        pg.keyboard.press(" ")
        self.assertTrue(self.until("PLAYER.ref === 1 && !PLAYER.audio.paused && !!document.querySelector('#plMeta .pl-bpm')"))
        orig = pg.evaluate("bpmOf(PLAYER.info)")
        pg.hover("#plMeta .pl-bpm")
        for _ in range(3):
            pg.mouse.wheel(0, -100)                                   # 3 Rasten nach oben = +0,3 BPM
        self.assertTrue(self.until(f"Math.abs(PLAYER.audio.playbackRate * {orig} - {orig + 0.3}) < 0.02"),
                        pg.evaluate("PLAYER.audio.playbackRate"))
        pg.keyboard.down("Shift"); pg.mouse.wheel(0, 100); pg.keyboard.up("Shift")   # −1 BPM
        self.assertTrue(self.until(f"Math.abs(PLAYER.audio.playbackRate * {orig} - {orig - 0.7}) < 0.02"))
        pg.wait_for_selector("#plMeta .pl-bpm.manual")
        pg.dblclick("#plMeta .pl-bpm")
        self.assertTrue(self.until("PLAYER.audio.playbackRate === 1 && !document.querySelector('#plMeta .pl-bpm.manual')"))
        time.sleep(0.5)
        self.assertFalse(pg.locator("#modal").is_visible())          # Doppelklick öffnet keinen Dialog
        pg.click("#plMeta .pl-bpm")                                   # Einzelklick: Dialog (kurz verzögert)
        pg.wait_for_selector("#tpBpm")
        pg.click("#mBtns button >> text=Abbrechen")
        # Mausrad zurück auf das Original rastet ein
        pg.hover("#plMeta .pl-bpm")
        pg.mouse.wheel(0, -100); pg.mouse.wheel(0, 100)
        self.assertTrue(self.until("PLAYER.audio.playbackRate === 1 && !PLAYER.tempoManual"))
        pg.evaluate("PLAYER.audio.pause()")

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
        self.assertTrue(pg.evaluate("document.querySelector('#helpDoc').classList.contains('wide')"))   # #206: ganze Breite
        lefts = pg.evaluate("[...document.querySelectorAll('#helpDoc .help-lic')].map(t => [...t.querySelectorAll('th')].map(th => Math.round(th.getBoundingClientRect().left)).join(','))")
        self.assertEqual(len(set(lefts)), 1, lefts)                          # Spalten aller Tabellen untereinander
        txt = pg.inner_text("#helpDoc")
        for s in ("Lizenzen und Quellen", "GPL-3.0-or-later", "pywebview", "BSD-3-Clause", "serato-tags", "Im Programm enthalten"):
            self.assertIn(s, txt)
        self.assertGreater(pg.locator("#helpDoc a[data-url]").count(), 20)
        # #206: GitHub-Repository, Entwickler, eigene Durchsicht, Danke-Text
        self.assertTrue(pg.locator('#helpDoc .lic-gh a[data-url="https://github.com/r0x0r/pywebview"]').count())
        self.assertTrue(pg.locator('#helpDoc .lic-gh a[data-url="https://github.com/r0x0r"]').count())
        pg.check('#helpDoc [data-licmark="pywebview"][data-key="checked"]')
        self.assertTrue(self.cfg_until(lambda c: "checked" in (c.get("lic_review") or {}).get("pywebview", {})))
        pg.wait_for_function("document.querySelector('#helpDoc').textContent.includes('geprüft 1')")      # nach Neuaufbau
        self.assertTrue(pg.locator('#helpDoc [data-licmark="pywebview"][data-key="checked"]').is_checked())
        pg.click('#helpDoc [data-licthanks="pywebview"]')
        pg.wait_for_selector("#licThanksTxt")
        txt = pg.input_value("#licThanksTxt")                             # Englisch zuerst (internationale Projekte)
        self.assertIn("TagStudio", txt)
        self.assertIn("pywebview", txt)
        self.assertIn("removed from this project", txt)
        pg.check('#modal input[name="licLang"][value="de"]')
        de = pg.input_value("#licThanksTxt")
        self.assertIn("aus diesem Projekt entfernt", de)
        self.assertIn("bitte ich dich", de)                                  # r0x0r ist eine Person → Du-Form
        self.assertNotIn(" Ihr", de)
        pg.click("#mBtns button >> nth=0")
        self.assertEqual(self.errors, [])

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

    def restart_with_init(self, script):
        """Wie restart(), aber script läuft vor den Seitenskripten (z. B. um Antworten zu verzögern)."""
        self.pg.evaluate("appFlushState()")
        self.server.terminate(); self.server.wait(10)
        self.pg.close()
        self.server, self.url = self.start_server()
        self.pg = self.page(init=script)
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

    def test_resume_selects_row_and_doubleclick(self):
        """#195: nach dem Neustart steht der Tagger auf dem fortgesetzten Titel; #196: Doppelklick spielt danach."""
        pg = self.pg
        self.load_tagger()
        pg.dblclick('.tg-row[data-i="2"] .nm')
        self.assertTrue(self.until("PLAYER.ref === 2 && !PLAYER.audio.paused"))
        pg.evaluate("PLAYER.audio.currentTime = 8; PLAYER.audio.pause()")
        pg.click('.tg-row[data-i="0"] .nm')                      # Tagger steht woanders als der Player
        time.sleep(0.4)
        pg.evaluate("plResumeSave(true)")
        self.cfg_until(lambda c: (c.get("player_resume", {}).get("A") or {}).get("pos", 0) >= 7)
        pg = self.restart()
        self.assertTrue(self.until("PLAYER.ref === 2 && PLAYER.kind === 'tag' && RESUME.done", 15),
                        pg.evaluate("JSON.stringify({kind: PLAYER.kind, ref: PLAYER.ref, loaded: TG.loaded})"))
        sel = pg.evaluate("[...TG.sel]")
        self.assertTrue(self.until("TG.sel.size === 1 && TG.sel.has(2) && TG.anchor === 2", 4), sel)
        self.assertTrue(pg.evaluate("PLAYER.audio.paused"))           # Auswahl darf nicht abspielen
        # #196: schneller Doppelklick – Liste wird zwischen zweitem Drücken und Loslassen neu gezeichnet
        box = pg.locator('.tg-row[data-i="1"] .nm').bounding_box()
        pg.mouse.move(box["x"] + 20, box["y"] + 5)
        pg.mouse.down(); pg.mouse.up()
        pg.mouse.down(click_count=2)
        pg.evaluate("tgApplyOrder()")
        pg.mouse.up(click_count=2)
        ok = self.until("PLAYER.ref === 1 && !PLAYER.audio.paused", 5)
        self.assertTrue(ok, pg.evaluate("JSON.stringify({ref: PLAYER.ref, paused: PLAYER.audio.paused, target: PLAYER.target, sel: [...TG.sel], mod: S.module, live: PLAYER.live, follow: PLAYER.follow})"))
        pg.evaluate("PLAYER.audio.pause()")

    def test_resume_player_before_tagger(self):
        """#195: Nach dem Neustart lädt der Player sofort über den Pfad, auch während der Tagger noch einliest;
        danach wird auf die Tagger-Zeile umgestellt."""
        pg = self.pg
        self.load_tagger()
        pg.dblclick('.tg-row[data-i="1"] .nm')
        self.assertTrue(self.until("PLAYER.ref === 1 && !PLAYER.audio.paused"))
        pg.evaluate("PLAYER.audio.currentTime = 6; PLAYER.audio.pause(); plResumeSave(true)")
        self.cfg_until(lambda c: (c.get("player_resume", {}).get("A") or {}).get("pos", 0) >= 5)
        # Tagger-Einlesen beim nächsten Start künstlich aufhalten: tag_rows antwortet erst nach 9 s
        pg = self.restart_with_init("""(() => { const wait = () => { if (typeof call !== 'function') return setTimeout(wait, 5);
            const orig = call; window.call = async (n, ...a) => {
              if (n === 'tag_rows' || n === 'start_tag_load') await new Promise(r => setTimeout(r, 9000));
              return orig(n, ...a); }; }; wait(); })()""")
        self.assertTrue(self.until("PLAYER.kind === 'file' && !!PLAYER.info && Math.abs(PLAYER.audio.currentTime - 6) < 1", 3),
                        pg.evaluate("JSON.stringify({kind: PLAYER.kind, loaded: TG.loaded})"))
        self.assertFalse(pg.evaluate("TG.loaded"))                    # Tagger liest noch ein
        self.assertTrue(self.until("TG.loaded && PLAYER.kind === 'tag' && PLAYER.ref === 1 && TG.sel.has(1)", 20))

    def test_tagger_origin_multiselect(self):
        """#198 Herkunfts-Auswahl mit Kennzeichen und Mehrfachauswahl, #199 „ohne bekannte Herkunft“ filtert,
        #197 Kontextmenü „Dateiordner öffnen“."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="0"] .nm')
        pg.wait_for_function("TG.detail && TG.detail.fields")
        for fid, desc, val in (("TXXX", "Meter", "4/4"), ("TXXX", "Eigenes Feld", "x"), ("TXXX", "Noch eins", "y")):
            pg.evaluate(f"call('tag_add_field', [0], '{fid}', '{desc}', '{val}').then(taggerApplyDetail)")
        self.assertTrue(self.until("TG.srcCounts && TG.srcCounts.unknown === 2 && TG.srcCounts.beatunes >= 1"),
                        pg.evaluate("JSON.stringify(TG.srcCounts)"))
        # Felder ganz ohne Herkunft (src leer) – so erscheint „ohne bekannte Herkunft (n)“ in der Auswahl
        pg.evaluate("TG.detail.fields.filter((f) => f.src === 'unknown').forEach((f) => { f.src = ''; }); renderTgEditor()")
        self.assertTrue(self.until("TG.srcCounts['-'] === 2"), pg.evaluate("JSON.stringify(TG.srcCounts)"))
        total = pg.evaluate("TG.detail.fields.length")
        # #199: nur „ohne bekannte Herkunft“
        pg.click("#tgSrcF")
        pg.click("#menu .menu-chk >> text=ohne bekannte Herkunft")
        self.assertTrue(self.until("TG.srcSel.size === 1 && TG.srcSel.has('-') && document.querySelectorAll('.tg-more .tg-f').length === 2"),
                        pg.evaluate("[...TG.srcSel].join() + ' ' + document.querySelectorAll('.tg-more .tg-f').length"))
        self.assertTrue(pg.locator("#menu").is_visible())                       # Menü bleibt offen
        # #198: zweite Herkunft dazu (beaTunes über TXXX:Meter) – Kennzeichen im Menü und im Knopf
        self.assertGreater(pg.locator("#menu .menu-chk .src-b").count(), 1)
        n_bt = pg.evaluate("TG.srcCounts['beatunes'] || 0")
        self.assertGreater(n_bt, 0)
        pg.click("#menu .menu-chk >> text=beaTunes")
        self.assertTrue(self.until(f"TG.srcSel.size === 2 && document.querySelectorAll('.tg-more .tg-f').length === {2 + n_bt}"))
        self.assertEqual(pg.locator("#tgSrcF .src-b").count(), 2)
        pg.keyboard.press("Escape")
        pg.click("#tgSrcF")
        pg.click("#menu button >> text=Alle Herkünfte zeigen")
        self.assertTrue(self.until(f"TG.srcSel.size === 0 && document.querySelectorAll('.tg-more .tg-f').length === {total}"))
        # #197: Kontextmenü im Tagger hat „Dateiordner öffnen“
        pg.click('.tg-row[data-i="1"] .nm', button="right")
        pg.wait_for_selector("#menu button >> text=Dateiordner öffnen")
        pg.keyboard.press("Escape")
        self.assertTrue(pg.evaluate("call('reveal_tag', 99)") is False)
        self.assertEqual(self.errors, [])

    def test_tagger_timestamps(self):
        """#185 Letzte Bearbeitung beim Speichern, #184 Aufnahmedatum nachtragen (Dialog), Spalten und Einstellungen."""
        pg = self.pg
        self.load_tagger()
        pg.click('.tg-row[data-i="0"] .nm')
        pg.wait_for_function("TG.detail && TG.detail.common")
        # #184: nachtragen – kein Snapshot vorhanden, also Datum von Hand
        pg.click("#tgAdded")
        pg.wait_for_selector("#adDate")
        pg.fill("#adDate", "2026-03-04")
        self.assertTrue(self.until("/1 Titel bekommen/.test(document.querySelector('#tdSum').textContent)"),
                        pg.inner_text("#tdSum"))
        self.assertIn("von Hand", pg.inner_text("#tdPrev"))
        pg.click("#mBtns .primary")
        self.assertTrue(self.until("TG.detail.fields.some(f => f.key === 'TXXX:TAGSTUDIO_ADDED')"))
        # speichern → #185 „Letzte Bearbeitung“
        pg.evaluate("void call('start_save')")
        for _ in range(60):
            if pg.evaluate("call('tag_detail', [0]).then(d => d.fields.some(f => f.key === 'TXXX:TAGSTUDIO_EDITED'))"):
                break
            time.sleep(0.1)
        d = pg.evaluate("call('tag_detail', [0]).then(d => d.fields.filter(f => f.key.startsWith('TXXX:TAGSTUDIO_')).map(f => [f.key, f.label || '']))")
        keys = [k for k, _l in d]
        self.assertIn("TXXX:TAGSTUDIO_EDITED", keys, d)
        self.assertIn("TXXX:TAGSTUDIO_ADDED", keys, d)
        # Spalten „Aufgenommen“ und „Bearbeitet“ zeigen ein kurzes Datum
        self.assertTrue(pg.evaluate("tsTime('2026-03-04T00:00:00+01:00') === '04.03.2026 00:00'"))
        # Einstellungen: beide Schalter vorhanden und an
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stStampEdited")
        self.assertTrue(pg.is_checked("#stStampEdited"))
        self.assertTrue(pg.is_checked("#stStampAdded"))
        pg.click("#stStampAdded")
        c = self.cfg_until(lambda c: c.get("stamp_added") is False)
        self.assertFalse(c.get("stamp_added"))
        self.assertEqual(self.errors, [])

    def test_tagger_column_filter(self):
        """#202: Filter je Spalte (Text, mehrere Spalten, BPM-Bereich), Esc leert, Tasten bewerten nicht, Ausblenden."""
        pg = self.pg
        self.load_tagger()
        pg.wait_for_selector('#tgHeadF input[data-cf="TIT2"]')
        n = lambda: pg.evaluate("TG.view.length")                       # noqa: E731
        pg.fill('#tgHeadF input[data-cf="TIT2"]', "330")
        self.assertTrue(self.until("TG.view.length === 1 && TG.rows[TG.view[0].i].TIT2 === 'Ton 330'"))
        self.assertIn("1 von 3", pg.inner_text("#tgCount"))
        pg.fill('#tgHeadF input[data-cf="TIT2"]', "ton")                # alle drei
        pg.fill('#tgHeadF input[data-cf="TPE1"]', "test")
        self.assertTrue(self.until("TG.view.length === 3"))
        # Ziffern im Feld setzen keine Bewertung, Leertaste spielt nicht
        pg.click('#tgHeadF input[data-cf="TPE1"]')
        pg.keyboard.type(" 5")
        self.assertTrue(self.until("TG.view.length === 0"))               # „test 5“: kein Treffer
        self.assertEqual(pg.evaluate("TG.rows.every(r => !r.rating)"), True)
        self.assertTrue(pg.evaluate("!PLAYER.audio.src || PLAYER.audio.paused"))
        pg.keyboard.press("Escape")                                       # leert dieses Feld
        self.assertEqual(pg.input_value('#tgHeadF input[data-cf="TPE1"]'), "")
        self.assertTrue(self.until("TG.view.length === 3"))
        # Zahlen: BPM-Bereich und Vergleich (BPM 124 und 120, dritter ohne)
        pg.fill('#tgHeadF input[data-cf="TBPM"]', "121-130")
        self.assertTrue(self.until("TG.view.length === 1 && TG.rows[TG.view[0].i].TBPM === '124'"))
        pg.fill('#tgHeadF input[data-cf="TBPM"]', "<=122")
        self.assertTrue(self.until("TG.view.length === 1 && TG.rows[TG.view[0].i].TBPM === '120'"))
        # zusammen mit dem Suchfeld oben
        pg.fill("#tgQuery", "440")
        self.assertTrue(self.until("TG.view.length === 0"))
        pg.fill("#tgQuery", "")
        # × leert alle Filter
        pg.click("#tgColFilterClear")
        self.assertTrue(self.until("TG.view.length === 3 && !tgColFilterActive()"))
        # Ausblenden merken
        pg.click("#tgColFilterBtn")
        self.assertTrue(pg.locator("#tgHeadF").is_hidden())
        c = self.cfg_until(lambda c: (c.get("ui") or {}).get("tg_colfilter") is False)
        self.assertFalse((c.get("ui") or {}).get("tg_colfilter"))
        pg.click("#tgColFilterBtn")
        self.assertTrue(pg.locator("#tgHeadF").is_visible())
        self.assertEqual(self.errors, [])

    def test_tagger_date_filter(self):
        """#214: Spalte „Aufgenommen“ – Zeitraum-Filter (<30d, >1y, Monat, Bereich, leer) und Sortierung nach Zeitpunkt."""
        pg = self.pg
        self.load_tagger()
        col = "fld:TXXX:TAGSTUDIO_ADDED"
        pg.evaluate(f"""(async () => {{
          await tgSetCols([...tgCols().filter((c) => c !== "{col}"), "{col}"], true);   // lädt die Zeilen neu
          const d = (days) => new Date(Date.now() - days * 864e5).toISOString();
          const vals = [d(3), d(400), ""];
          TG.rows.forEach((r, i) => {{ r.x = r.x || {{}}; r.x["TXXX:TAGSTUDIO_ADDED"] = vals[i]; }});
        }})()""")
        sel = f'#tgHeadF input[data-cf="{col}"]'
        pg.wait_for_selector(sel)
        self.assertIn("30d", pg.get_attribute(sel, "placeholder"))
        ix = "TG.view.map(v => v.i).join(',')"
        pg.fill(sel, "<30d")
        self.assertTrue(self.until(f"{ix} === '0'"))
        pg.fill(sel, ">1y")
        self.assertTrue(self.until(f"{ix} === '1'"))
        pg.fill(sel, "leer")
        self.assertTrue(self.until(f"{ix} === '2'"))
        y = pg.evaluate("new Date(Date.now() - 3 * 864e5).toISOString().slice(0, 7)")
        pg.fill(sel, y)
        self.assertTrue(self.until(f"{ix} === '0'"))
        pg.fill(sel, "2000-01-01..2099-12-31")
        self.assertTrue(self.until("TG.view.length === 2"))
        pg.fill(sel, "")
        pg.evaluate(f"tgSetSorts([{{col: '{col}', dir: -1}}]); tgApplyOrder()")   # neueste zuerst, leer am Ende
        self.assertTrue(self.until(f"{ix} === '0,1,2'"))
        self.assertEqual(self.errors, [])

    def test_app_update_button(self):
        """#234: installierte App unter Windows – „Jetzt aktualisieren“ lädt, prüft und installiert (Aufrufe simuliert)."""
        pg = self.pg
        self.calm()
        pg.evaluate("""(() => { const orig = call; window.__calls = [];
          const rel = { version: "9.9.0", beta: false, date: "2026-12-01", url: "https://github.com/x", notes: "Neu",
            assets: [{ name: "TagStudio-9.9.0-Windows-Setup.exe", url: "https://github.com/x.exe" }, { name: "TagStudio-9.9.0-macOS-Apple-Chip.dmg", url: "u" }] };
          window.call = (n, ...a) => { window.__calls.push(n);
            if (n === "update_status") return Promise.resolve({ ok: true, kind: "release", frozen: true, newer: true, channel: "stable", version: "4.7.0", auto: true, latest: rel, behind: 1 });
            if (n === "start_app_update") return Promise.resolve({ ok: true });
            if (n === "task_status") return Promise.resolve({ done: true, running: false, result: { ok: true, path: "C:/x/TagStudio-9.9.0-Windows-Setup.exe", version: "9.9.0" } });
            if (n === "app_update_install") { window.__inst = a[0]; return Promise.resolve({ ok: true }); }
            return orig(n, ...a); }; })()""")
        pg.evaluate("Object.defineProperty(navigator, 'platform', { get: () => 'Win32' })")
        pg.click("#updateBtn")
        pg.wait_for_selector('#mBtns button:has-text("Jetzt aktualisieren")')
        self.assertIn("schliesst TagStudio", pg.inner_text("#mBody"))
        pg.click('#mBtns button:has-text("Jetzt aktualisieren")')
        self.assertTrue(self.until("window.__inst === 'C:/x/TagStudio-9.9.0-Windows-Setup.exe'"))
        calls = pg.evaluate("window.__calls")
        self.assertLess(calls.index("start_app_update"), calls.index("app_update_install"))
        self.assertIn("wird installiert", pg.inner_text("#progTitle"))

    def test_plugin_store(self):
        """#235/#236: Verfügbare Plugins – Katalog, Hinweis auf der Karte, neues Plugin installieren, zurück auf eingebaute Version."""
        pg = self.pg
        self.calm()
        pg.click('.nav[data-module="plugins"]')
        pg.wait_for_selector('.pl-card[data-pid="lexicon"] .pl-btns')
        pg.evaluate("""(() => { const orig = call; window.__calls = []; window.__res = null;
          const row = (id, state, extra) => ({ id, name: id, version: "9.0", installed: "", min_app: "4.8.0", description: "Text " + id,
            category: "other", env: false, requires: false, file: `plugin-${id}-9.0.zip`, sha256: "a".repeat(64), state, ...extra });
          const cat = { ok: true, release: { tag: "v4.8.1", version: "4.8.1", beta: false, url: "u" }, channel: "stable", version: "4.8.0",
            rows: [row("lexicon", "update", { installed: "1.0", builtin: true }), row("neu", "new"), row("zukunft", "too_new", { min_app: "9.9.0" }),
                   row("mik", "current", { installed: "9.0", builtin: true })] };
          window.call = (n, ...a) => { window.__calls.push([n, ...a]);
            if (n === "start_plugin_catalog") { window.__res = cat; return Promise.resolve({ ok: true }); }
            if (n === "start_plugin_store_install") { window.__res = { ok: true, id: a[0], name: a[0], version: "9.0", state: "ready" }; return Promise.resolve({ ok: true }); }
            if (n === "task_status") return Promise.resolve({ done: true, running: false, result: window.__res });
            if (n === "plugin_store_revert") return orig("plugins_list").then((r) => ({ ok: true, ...r }));
            if (n === "plugins_list") return orig(n, ...a).then((r) => { if (window.__stored) { const p = r.plugins.find((x) => x.id === "lexicon");
              Object.assign(p, { builtin: false, store: { version: "9.0", tag: "v4.8.1" }, builtin_version: "1.0", version: "9.0" }); } return r; });
            return orig(n, ...a); }; })()""")
        pg.click("#plStore")
        pg.wait_for_selector("#mBody .st-row")
        rows = pg.evaluate("[...document.querySelectorAll('#mBody .st-row')].map((r) => [r.querySelector('b').textContent, r.querySelector('button').textContent, r.querySelector('button').disabled])")
        self.assertEqual(rows, [["lexicon", "Aktualisieren", False], ["neu", "Installieren", False], ["mik", "Aktuell", True],
                                ["zukunft", "Nicht verträglich", True]])
        heads = pg.evaluate("[...document.querySelectorAll('#mBody .st-group h4')].map((h) => h.firstChild.textContent.trim())")
        self.assertEqual(heads, ["Updates", "Neu – noch nicht installiert", "Installiert", "Nicht verträglich"])   # #236
        self.assertIn("4 Plugins · 1 Update(s) · 1 neu", pg.inner_text("#mBody"))
        self.assertIn("Sonstiges", pg.inner_text('#mBody [data-strow="neu"]'))
        self.assertEqual(pg.locator("#mBody [data-stcat]").count(), 2)        # Alle + Sonstiges
        pg.click('#mBody [data-stcat="other"]')
        self.assertEqual(pg.locator("#mBody .st-row").count(), 4)
        pg.click('#mBody [data-stcat=""]')
        self.assertIn("TagStudio 9.9.0", pg.inner_text("#mBody"))
        self.assertIn("Update verfügbar", pg.inner_text('.pl-card[data-pid="lexicon"] .pl-box.upd'))
        pg.click('#mBody [data-stinst="neu"]')
        self.assertTrue(self.until("window.__calls.some((c) => c[0] === 'start_plugin_store_install' && c[1] === 'neu')"))
        self.assertTrue(self.until("document.querySelector('#toast') && /neu 9.0 installiert/.test(document.querySelector('#toast').textContent)"))
        # Update direkt auf der Karte
        pg.evaluate("window.__stored = true")
        pg.click('.pl-card[data-pid="lexicon"] [data-plupd]')
        self.assertTrue(self.until("window.__calls.some((c) => c[0] === 'start_plugin_store_install' && c[1] === 'lexicon')"))
        pg.wait_for_selector('.pl-card[data-pid="lexicon"] .plg-tag.store')
        self.assertEqual(pg.locator('.pl-card[data-pid="lexicon"] .pl-box.upd').count(), 0)    # kein Update mehr angezeigt
        # Zurück auf eingebaute Version – mit Rückfrage
        pg.click('.pl-card[data-pid="lexicon"] [data-plmore]')
        pg.click('#mBody button:has-text("Zurück auf eingebaute Version 1.0")')
        pg.wait_for_selector('#dlgBtns button:has-text("Zurücksetzen")')
        self.assertIn("gelöscht", pg.inner_text("#dlgText"))
        pg.evaluate("window.__stored = false")
        pg.click('#dlgBtns button:has-text("Zurücksetzen")')
        self.assertTrue(self.until("window.__calls.some((c) => c[0] === 'plugin_store_revert' && c[1] === 'lexicon')"))
        pg.wait_for_selector('.pl-card[data-pid="lexicon"] .plg-tag:not(.cat):has-text("eingebaut")')

    def test_lexicon_open_and_remote(self):
        """#238/#239: Ergebnis „öffnen“ lädt die Dateien und legt sie als DJ-Set an; Vorschau zeigt Änderungen in Lexicon."""
        pg = self.pg
        self.calm()
        a, b = os.path.join(self.lib, "03 Ton 440.mp3"), os.path.join(self.lib, "01 Ton 220.mp3")
        pg.evaluate("""([a, b]) => { const orig = call; window.__fake = null; window.__applied = null;
          window.call = (n, ...args) => {
            if (n === "start_plugin_action" && args[1] === "open") { window.__fake = { message: "„Freitag“: 2 Titel.", log: [], outputs: [],
                open: { target: "djset", files: [a, b], label: "Freitag" } }; return Promise.resolve({ ok: true }); }
            if (n === "start_plugin_action" && args[1] === "send") { window.__fake = { message: "1 Wert weicht ab.", log: [], outputs: [],
                proposals_token: "t1", proposals: [{ id: 0, name: "x.mp3", group: "x.mp3", gkey: "x", folder: "", label: "Lexicon: Genre",
                  old: "Techno", new: "House", note: "geändert wird in Lexicon", checked: true, kind: "remote", hint: "wird in Lexicon geändert", same: false }] };
              return Promise.resolve({ ok: true }); }
            if (n === "task_status" && window.__fake) { const r = window.__fake; window.__fake = null; return Promise.resolve({ done: true, running: false, result: r }); }
            if (n === "plugin_apply") { window.__applied = args; return Promise.resolve({ ok: true, message: "1 Titel in Lexicon geändert. 1 Fehler.", errors: ["Titel 2: Track does not exist"] }); }
            return orig(n, ...args); }; }""", [a, b])
        pg.evaluate("() => { pluginRun('lexicon', 'open'); }")
        pg.wait_for_selector('#mBtns button:has-text("Öffnen")')
        self.assertIn("Lexicon", pg.inner_text("#mBody"))
        pg.click('#mBtns button:has-text("Öffnen")')
        pg.wait_for_selector("#moduleDjset:not([hidden])")
        self.assertTrue(self.until("DJ.st && DJ.st.items.length === 2"))
        self.assertEqual(pg.evaluate("DJ.st.items.map((r) => r.path)"), [a, b])          # Reihenfolge der Playlist
        self.assertTrue(self.until("TG.rows && TG.rows.length === 2"))                    # Tagger hat genau diese Dateien
        # Vorschau mit Änderung in Lexicon (nicht in der Datei)
        pg.evaluate("() => { pluginRun('lexicon', 'send'); }")
        pg.wait_for_selector('#mBtns button:has-text("Vergleichen")')
        pg.click('#mBtns button:has-text("Vergleichen")')
        pg.wait_for_selector(".pl-prev")
        txt = pg.inner_text(".pl-prev")
        self.assertIn("Lexicon: Genre", txt)
        self.assertIn("Techno", txt)
        self.assertIn("wird in Lexicon geändert", txt)
        pg.click('#mBtns button.primary')
        self.assertTrue(self.until("window.__applied && window.__applied[0] === 't1'"))
        pg.wait_for_selector("#dlgText:has-text('Track does not exist')")

    def test_openkeyscan_preview(self):
        """#244/#245: Plugin-Karten beider Wege; Tonart über die (nachgestellte) OpenKeyScan-App als Vorschau."""
        import fake_openkeyscan
        pg = self.pg
        self.calm()
        state = fake_openkeyscan.State()
        state.default = "1m"                                   # jede Datei: a-Moll (08A) in Open-Key-Schreibweise
        srv, url = fake_openkeyscan.start(state)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        pg.click('.nav[data-module="plugins"]')
        pg.wait_for_selector('.pl-card[data-pid="keyscan"]')
        card = pg.inner_text('.pl-card[data-pid="keyscan"]')
        self.assertIn("Tonart (OpenKeyScan)", card)
        self.assertIn("Eigene Umgebung (Python 3.12 + Pakete)", card)
        self.assertIn("OpenKeyScan Local API", pg.inner_text('.pl-card[data-pid="openkeyscan"]'))
        pg.evaluate("(u) => call('start_plugin_action', 'openkeyscan', 'settings', [], { url: u })", url)
        self.assertTrue(self.until("call('task_status').then((s) => s.done)"))
        self.load_tagger()
        pg.evaluate("() => { TG.sel = new Set(TG.order); pluginRun('openkeyscan', 'scan'); }")
        pg.wait_for_selector('#mBtns button:has-text("Tonart erkennen")')
        self.assertIn("Auto-Tagging", pg.inner_text("#mBody"))
        pg.click('#mBtns button:has-text("Tonart erkennen")')
        pg.wait_for_selector(".pl-prev")
        txt = pg.inner_text(".pl-prev")
        self.assertIn("Tonart (OpenKeyScan)", txt)
        self.assertIn("08A", txt)
        self.assertEqual(len([c for c in state.calls if c[1] == "/analyze/single"]), 3)

    def test_error_dialog_opens_log(self):
        """#247: Meldung mit Protokoll-Pfad → „Protokoll öffnen“ und „Ordner öffnen“; ohne Pfad nur OK."""
        pg = self.pg
        self.calm()
        pg.evaluate("""() => { const orig = call; window.__log = [];
          window.call = (n, ...a) => { if (n === "open_log") { window.__log.push(a); return Promise.resolve(true); } return orig(n, ...a); }; }""")
        pg.evaluate("() => { info('Fehler', 'Keine Verbindung.\\n\\nDetails im Protokoll: C:\\\\Users\\\\m\\\\TagStudio\\\\Logs\\\\openkeyscan.log'); }")
        pg.wait_for_selector("#dialog:not([hidden]) [data-dlglog]")
        self.assertEqual(pg.locator("#dlgBtns button").all_inner_texts(), ["Protokoll öffnen", "Ordner öffnen", "OK"])
        pg.click('[data-dlglog="file"]')
        pg.click('[data-dlglog="folder"]')
        self.assertTrue(self.until("window.__log.length === 2"))
        self.assertEqual(pg.evaluate("window.__log"), [["C:\\Users\\m\\TagStudio\\Logs\\openkeyscan.log", False],
                                                     ["C:\\Users\\m\\TagStudio\\Logs\\openkeyscan.log", True]])
        self.assertFalse(pg.locator("#dialog").is_hidden())                     # Dialog bleibt offen
        pg.click("#dlgBtns button.primary")
        pg.evaluate("() => { info('Hinweis', 'Alles gut.'); }")
        pg.wait_for_selector("#dialog:not([hidden])")
        self.assertEqual(pg.locator("#dlgBtns button").all_inner_texts(), ["OK"])
        pg.click("#dlgBtns button.primary")

    def test_dj_lexicon_playlists(self):
        """#242: DJ-Set › „Aus Lexicon …“ – alle Playlists holen, mit Häkchen wählen, als Listen laden."""
        pg = self.pg
        self.calm()
        a, b = os.path.join(self.lib, "02 Ton 330.mp3"), os.path.join(self.lib, "01 Ton 220.mp3")
        pg.evaluate("""([a, b]) => { const orig = call; window.__fake = null; window.__imp = null;
          window.call = (n, ...args) => {
            if (n === "dj_sources") return Promise.resolve({ sources: [{ id: "lexicon", name: "Lexicon" }] });
            if (n === "start_dj_source_list") { window.__fake = { ok: true, playlists: [
                { id: "queue", name: "Warteschlange in Lexicon (läuft gerade + nächste)", depth: 0, type: "queue", path: [] },
                { id: 11, name: "Sets", depth: 0, type: "1", path: ["Sets"] }, { id: 12, name: "Freitag", depth: 1, type: "2", path: ["Sets", "Freitag"] },
                { id: 13, name: "Samstag", depth: 1, type: "3", path: ["Sets", "Samstag"] }] }; return Promise.resolve({ ok: true }); }
            if (n === "start_dj_source_import") { window.__imp = args[1];
              return orig("dj_add_paths", [a, b], true, "Freitag").then(() => { window.__fake = { ok: true, lists: [{ name: "Lexicon: Freitag" }, { name: "Lexicon: Samstag" }],
                first: "Lexicon: Freitag", files: [a, b], missing: 1 }; return { ok: true }; }); }
            if (n === "task_status" && window.__fake) { const r = window.__fake; window.__fake = null; return Promise.resolve({ done: true, running: false, result: r }); }
            return orig(n, ...args); }; }""", [a, b])
        pg.click('.nav[data-module="djset"]')
        pg.wait_for_selector("#djSource:not([hidden])")
        self.assertEqual(pg.inner_text("#djSource"), "Aus Lexicon …")
        pg.click("#djSource")
        pg.wait_for_selector("#mBody .djs-row")
        self.assertEqual(pg.locator("#mBody .djs-row").count(), 4)
        self.assertTrue(pg.locator("#mBtns .primary").is_disabled())                    # nichts gewählt
        pg.fill("#djsFind", "sets / f")                                                 # Filter über den Pfad
        self.assertEqual(pg.locator("#mBody .djs-row:not([hidden])").count(), 1)
        pg.fill("#djsFind", "")
        pg.check('[data-djsi="2"]')
        pg.check('[data-djsi="3"]')
        self.assertEqual(pg.inner_text("#mBtns .primary"), "Laden (2)")
        pg.click("#mBtns .primary")
        self.assertTrue(self.until("window.__imp && window.__imp.join(',') === '12,13'"))
        self.assertTrue(self.until("DJ.st && DJ.st.items.length === 2 && !DJ.st.items.some((r) => r.missing)"))
        self.assertEqual(pg.evaluate("DJ.st.items.map((r) => r.path)"), [a, b])
        self.assertTrue(self.until("document.querySelector('#toast') && /2 Liste\\(n\\) gespeichert/.test(document.querySelector('#toast').textContent)"))

    def test_feedback_translation(self):
        """#232: eigene Übersetzungen einreichen – Texte eingefüllt, Sprache wählbar, Vorschau, zu viele Texte → Kopieren."""
        pg = self.pg
        self.calm()
        pg.evaluate("""(() => { const orig = call; window.__opened = null; window.__langs = [];
          window.call = (n, ...a) => {
            if (n === "feedback_translation") { window.__langs.push(a[0]); const many = a[0] === "gsw-u-sd-chzh";
              const texts = many ? Object.fromEntries([...Array(900)].map((_, i) => [`Text ${i}`, `Täxt ${i}`])) : { "Speichern": "Store" };
              return Promise.resolve({ texts, count: Object.keys(texts).length, language: a[0] === "en" ? "Englisch" : "Zürichdeutsch", json: JSON.stringify(texts, null, 1) }); }
            if (n === "open_url") { window.__opened = a[0]; return Promise.resolve({}); }
            return orig(n, ...a); }; })()""")
        pg.evaluate("() => { fbOpen('translation', 'en'); }")
        pg.wait_for_selector("#fb-texts")
        self.assertTrue(self.until("document.querySelector('#fb-texts').value.includes('Store')"))
        self.assertEqual(pg.input_value("#fbTitle"), "Englisch – 1 eigene Texte")
        self.assertEqual(pg.locator("#fbArea").count(), 0)                    # kein Bereich bei Übersetzungen
        self.assertIn("1 eigene Texte", pg.inner_text("#fbBody"))
        pg.click("#fbPreview")
        pg.wait_for_selector("#fbConsent")
        self.assertIn("Übersetzung: Englisch", pg.inner_text("#fbBody"))
        self.assertIn("funktion", pg.inner_text("#fbBody"))
        self.assertEqual(pg.locator("#fbCopy").count(), 0)
        pg.check("#fbConsent")
        pg.click("#fbGo")
        self.assertTrue(self.until("window.__opened && window.__opened.includes('template=translation.yml')"))
        url = pg.evaluate("window.__opened")
        self.assertIn("language=Englisch", url)
        # andere Sprache mit sehr vielen Texten: Titel folgt, Kopieren-Knopf erscheint
        pg.click("#fbBack")
        pg.select_option("#fbLang", "Zürichdeutsch")
        self.assertTrue(self.until("document.querySelector('#fbTitle').value === 'Zürichdeutsch – 900 eigene Texte'"))
        pg.click("#fbPreview")
        pg.wait_for_selector("#fbCopy")

    def test_feedback_report(self):
        """#187: Melden aus dem Tagger – Bereich vorgewählt, Duplikate, Pflichtfelder, Vorschau geschwärzt, Zustimmung."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("""(() => { const orig = call; window.__opened = null;
          window.call = (n, ...a) => n === "feedback_search"
            ? Promise.resolve({ ok: true, items: [{ number: 187, title: "Melden aus der App", state: "open", url: "https://github.com/x/187" }] })
            : n === "open_url" ? (window.__opened = a[0], Promise.resolve({})) : orig(n, ...a); })()""")
        pg.click("#tgReport")
        pg.wait_for_selector("#fbTitle")
        self.assertEqual(pg.input_value("#fbArea"), "Tagger")
        pg.fill("#fbTitle", "Speichern bricht ab")
        pg.click("#fbSearch")
        pg.wait_for_selector("#fbDup a[data-url]")
        self.assertIn("#187", pg.inner_text("#fbDup"))
        pg.click("#fbPreview")                                              # Pflichtfelder fehlen
        self.assertTrue(self.until("document.querySelector('#toast') && /ausfüllen/.test(document.querySelector('#toast').textContent)"))
        pg.fill("#fb-what", r"Fehler bei C:\Users\Markus\Music\a.mp3")
        pg.fill("#fb-steps", "1. speichern")
        pg.click("#fbPreview")
        pg.wait_for_selector("#fbConsent")
        txt = pg.inner_text("#fbBody")
        self.assertIn("Geschwärzt: Benutzerordner", txt)
        self.assertNotIn("Markus", pg.inner_text("#fbBody .fb-prev"))
        self.assertIn("triage", txt)
        self.assertTrue(pg.locator("#fbGo").is_disabled())                 # erst nach Zustimmung
        pg.check("#fbConsent")
        pg.click("#fbGo")
        url = pg.evaluate("window.__opened")
        self.assertTrue(url.startswith("https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/new?template=bug_report.yml"), url)
        self.assertIn("area=Tagger", url)
        self.assertIn("wartet auf Prüfung", pg.inner_text("#fbBody"))
        pg.click("#mBtns button")
        # Hilfe › Melden
        pg.click('.nav[data-module="help"]')
        pg.click('#helpTabs [data-htab="report"]')
        pg.click('#helpDoc [data-fbopen="feature"]')
        pg.wait_for_selector('[data-fbkind="feature"][aria-checked="true"]')
        self.assertTrue(pg.locator("#fb-solution").count())
        pg.click("#mBtns button")
        # vier Arten: Verbesserung mit eigenem Formular und Meilenstein (Entscheid 17.10.2026), Übersetzung (#232)
        self.assertEqual(pg.locator('#helpDoc [data-fbopen]').count(), 4)
        pg.click('#helpDoc [data-fbopen="improvement"]')
        pg.wait_for_selector('[data-fbkind="improvement"][aria-checked="true"]')
        self.assertTrue(pg.locator("#fb-current").count())
        self.assertIn("Verbesserungen", pg.inner_text("#fbBody .fb-ms"))
        pg.click('[data-fbkind="bug"]')
        self.assertIn("Fehler", pg.inner_text("#fbBody .fb-ms"))
        pg.click("#mBtns button")
        self.assertEqual(self.errors, [])

    def test_player_lyrics(self):
        """#215: Liedtext im Player – synchronisiert mit hervorgehobener Zeile, Klick springt, gemerkt; normaler Text."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("""(() => { const orig = call; window.__lyCalls = 0;
          window.call = (n, ...a) => n === "media_lyrics"
            ? (window.__lyCalls++, Promise.resolve(a[1] === 0 ? { source: "SYLT", synced: [[500, "Erste Zeile"], [1500, "Zweite Zeile"], [3000, ""]], plain: "" }
                                                         : { source: "USLT", synced: [], plain: "Nur Text ohne Zeit" }))
            : orig(n, ...a); })()""")
        pg.evaluate("plLoad({kind: 'tag', ref: 0}, false)")
        self.assertTrue(self.until("PLAYER.info && PLAYER.audio.src"))
        pg.click("#plLyricsBtn")
        pg.wait_for_selector("#plLyrics .ly-l")
        self.assertEqual(pg.locator("#plLyrics .ly-l").count(), 3)
        self.assertIn("SYLT", pg.inner_text("#plLyrics .ly-src"))
        pg.evaluate("PLAYER.audio.currentTime = 1.6; plLyricsRender()")
        self.assertTrue(self.until("document.querySelector('#plLyrics .ly-l.on')?.textContent === 'Zweite Zeile'"))
        pg.click('#plLyrics .ly-l[data-k="0"]')                              # Klick springt
        self.assertTrue(self.until("Math.abs(PLAYER.audio.currentTime - 0.5) < 0.3"))
        c = self.cfg_until(lambda c: (c.get("player") or {}).get("lyrics") is True)
        self.assertTrue((c.get("player") or {}).get("lyrics"))
        # anderer Titel: normaler Text mit Hinweis
        pg.evaluate("plLoad({kind: 'tag', ref: 1}, false)")
        pg.wait_for_selector("#plLyrics .ly-plain")
        self.assertIn("ohne Zeit", pg.inner_text("#plLyrics .ly-plain"))
        self.assertIn("Nicht synchronisiert", pg.inner_text("#plLyrics"))
        pg.click("#plLyrics .ly-x")                                          # schliessen
        self.assertTrue(pg.locator("#plLyrics").is_hidden())
        self.assertEqual(pg.get_attribute("#plLyricsBtn", "aria-pressed"), "false")
        self.assertEqual(self.errors, [])

    def calm(self):
        """Hinweise beim Start (Snapshots …) schliessen – sie erscheinen verzögert und fangen sonst Klicks ab."""
        pg = self.pg
        for _ in range(15):
            time.sleep(0.15)
            if pg.locator("#modal").is_visible() and not pg.locator("#modal .i18n-imp").count():
                pg.click("#mBtns button >> nth=0")

    def lang_pick(self, drop, code):
        """Sprache über die Auswahlliste mit Flaggen wählen (Einstellungen #stLang, Seitenleiste #sideLang, Assistent)."""
        self.pg.click(f"{drop} .lang-cur")
        self.pg.click(f'{drop} .lang-menu [data-lang="{code}"]')

    def test_i18n_language(self):
        """#157: Sprache wählen – Oberfläche auf Englisch/Zürichdeutsch, Platzhalter, Tooltips, gemerkt; zurück auf Deutsch."""
        pg = self.pg
        self.assertEqual(pg.evaluate("I18N.lang"), "de-CH")                          # bestehende Installation: Deutsch
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stLang")
        self.assertEqual(pg.locator("#stLang .lang-menu [data-lang]").count(), 4)           # Betriebssystem + 3 Sprachen
        self.assertTrue(pg.locator("#stLang .lang-menu").is_hidden())
        self.lang_pick("#stLang", "en")
        self.assertTrue(self.until("I18N.lang === 'en' && document.documentElement.lang === 'en'"))
        c = self.cfg_until(lambda c: (c.get("web_ui") or {}).get("lang") == "en")
        self.assertEqual(c["web_ui"]["lang"], "en")
        self.assertIn("Settings", pg.inner_text(".nav[data-module=settings]"))
        self.assertEqual(pg.evaluate("tr('Einlesen')"), "Load")
        self.assertEqual(pg.evaluate("tr('Sortierung auf den Standard zurücksetzen (#153)')"), "Reset sorting to default (#153)")
        self.assertEqual(pg.evaluate("tr('Die Hinweise „Erste Schritte“ wieder auf jeder Seite zeigen')"),
                         "Show the “First steps” hints on every page again")           # {q} mitübersetzt
        self.assertEqual(pg.evaluate("tr('Unbekannter Text bleibt')"), "Unbekannter Text bleibt")
        # neu eingefügte Elemente und Tooltips werden übersetzt, Daten mit translate=no nicht
        pg.evaluate("""document.body.insertAdjacentHTML('beforeend', '<div id="i18nT"><button title="Ordner wählen">Abbrechen</button><span translate="no">Abbrechen</span></div>')""")
        self.assertTrue(self.until("document.querySelector('#i18nT button').textContent === 'Cancel'"))
        self.assertEqual(pg.evaluate("document.querySelector('#i18nT button').dataset.tipTitle || document.querySelector('#i18nT button').title"), "Choose folder")
        self.assertEqual(pg.inner_text("#i18nT span"), "Abbrechen")
        # nach Neustart wieder Englisch, ohne deutsches Aufblitzen
        pg.reload()
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'en'")
        self.assertFalse(pg.evaluate("document.documentElement.classList.contains('i18n-wait')"))
        self.calm()
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stLang")
        self.lang_pick("#stLang", "gsw-u-sd-chzh")
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'gsw-u-sd-chzh'")
        self.assertEqual(pg.evaluate("tr('Einlesen')"), "Iiläse")
        self.calm()
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stLang")
        self.lang_pick("#stLang", "de-CH")
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'de-CH'")
        self.assertIn("Einstellungen", pg.inner_text(".nav[data-module=settings]"))
        self.assertEqual(self.errors, [])

    def test_i18n_side_and_system(self):
        """Sprachwahl als Auswahlliste mit Flaggen (Seitenleiste unter „Einklappen“, Einstellungen), Deutsch mit
        geteilter Flagge, Eintrag „Sprache des Betriebssystems“."""
        pg = self.pg
        self.calm()
        side = "#sideLang"
        self.assertIn("Deutsch", pg.inner_text(f"{side} .lang-cur"))
        self.assertTrue(pg.locator(f'{side} .lang-cur svg.flag[viewBox="0 0 30 20"]').count())   # DE/CH diagonal
        self.assertTrue(pg.evaluate("document.querySelector('#collapseBtn').compareDocumentPosition(document.querySelector('#sideLang')) & 4"))
        pg.click(f"{side} .lang-cur")
        items = pg.evaluate("[...document.querySelectorAll('#sideLang .lang-menu [data-lang]')].map((b) => [b.dataset.lang, b.textContent.trim(), !!b.querySelector('svg')])")
        self.assertEqual([i[0] for i in items], ["auto", "de-CH", "en", "gsw-u-sd-chzh"])
        self.assertTrue(all(i[2] for i in items))                               # jede Zeile mit Flagge bzw. Symbol
        self.assertIn("Betriebssystem", items[0][1])
        pg.click(f'{side} .lang-menu [data-lang="en"]')
        self.assertTrue(self.until("I18N.lang === 'en'"))
        self.assertTrue(pg.locator(f"{side} .lang-menu").is_hidden())
        self.assertEqual(self.cfg_until(lambda c: (c.get("web_ui") or {}).get("lang") == "en")["web_ui"]["lang"], "en")
        self.assertIn("Settings", pg.inner_text(".nav[data-module=settings]"))
        # Einstellungen: dieselbe Auswahlliste, Beschriftung auf Höhe der Liste
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stLang .lang-cur")
        top = pg.evaluate("""(() => { const l = [...document.querySelectorAll('#stLookCard .st-top')].pop().getBoundingClientRect(),
          d = document.querySelector('#stLang .lang-cur').getBoundingClientRect(); return Math.abs((l.top + l.height / 2) - (d.top + d.height / 2)); })()""")
        self.assertLess(top, 4)
        self.lang_pick("#stLang", "auto")
        c = self.cfg_until(lambda c: (c.get("web_ui") or {}).get("lang") == "auto")
        self.assertEqual(c["web_ui"]["lang"], "auto")
        self.assertEqual(pg.evaluate("I18N.lang"), pg.evaluate("i18nSysLang()"))
        self.assertTrue(self.until("document.querySelector('#sideLang .lang-menu [data-lang=auto]').classList.contains('on')"))
        # feste Sprache wählen nimmt „Betriebssystem“ zurück
        self.lang_pick("#stLang", "gsw-u-sd-chzh")
        pg.wait_for_function("I18N.lang === 'gsw-u-sd-chzh'")
        self.assertTrue(self.until("document.querySelector('#sideLang .lang-menu [data-lang=\"gsw-u-sd-chzh\"]').classList.contains('on')"))
        # eingeklappte Seitenleiste: Flagge bleibt, Liste öffnet sich
        pg.click("#collapseBtn")
        self.assertTrue(pg.locator(f"{side} .lang-flag").is_visible())
        pg.click(f"{side} .lang-cur")
        self.assertTrue(pg.locator(f"{side} .lang-menu").is_visible())
        pg.keyboard.press("Escape")
        self.assertTrue(pg.locator(f"{side} .lang-menu").is_hidden())
        pg.click("#collapseBtn")
        self.assertEqual(self.errors, [])

    def test_i18n_own_texts(self):
        """#219: Texte exportieren (CSV) und eigene Texte importieren – Vorschau, Überlagerung, Zurücksetzen."""
        pg = self.pg

        calm = self.calm
        pg.evaluate("call('set_ui', 'lang', 'en')")
        pg.reload()
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'en'")
        calm()
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stLangTools")
        self.assertTrue(self.until("/No own texts/.test(document.querySelector('#stLangInfo').textContent)"))
        with pg.expect_download() as dl:
            pg.click('[data-i18n-x="csv"]')
        self.assertEqual(dl.value.suggested_filename, "TagStudio-Texte-en.csv")
        src = os.path.join(self.dir, "eigene.json")
        with open(src, "w", encoding="utf-8") as fh:
            json.dump({"texts": {"Einlesen": "Read in", "Gibt es nicht": "x"}}, fh)
        with pg.expect_file_chooser() as fc:
            pg.click("[data-i18n-imp]")
        fc.value.set_files(src)
        pg.wait_for_selector("#modal .i18n-imp")
        self.assertIn("1 text(s) will be taken over", pg.inner_text("#modal"))
        self.assertIn("1 rejected", pg.inner_text("#modal"))
        pg.click("#mBtns .primary")
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'en' && tr('Einlesen') === 'Read in'", timeout=15000)
        calm()
        pg.click('.nav[data-module="settings"]')
        self.assertTrue(self.until("/Own texts for English: 1/.test(document.querySelector('#stLangInfo')?.textContent || '')"))
        pg.click("[data-i18n-reset]")
        pg.click("#mBtns .primary")
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'en' && tr('Einlesen') === 'Load'", timeout=15000)
        self.assertEqual(self.errors, [])

    def test_i18n_pages_english(self):
        """#157: alle Seiten auf Englisch – keine deutschen Reste in der sichtbaren Oberfläche (ausser Daten)."""
        pg = self.pg
        pg.evaluate("localStorage.setItem('ts_i18n_miss', '1'); call('set_ui', 'lang', 'en')")   # Fehlliste der Übersetzung
        pg.reload()
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'en'")
        self.load_tagger()
        pg.click(".tg-row >> nth=0")
        scan = """(() => {
          const de = /[äöüÄÖÜ]|\b(der|die|das|und|nicht|keine?|mit|für|von|oder|wird|werden|noch|bitte|Datei|Dateien|Ordner|Titel|Einstellungen|Speichern|Abbrechen|Feld|Felder|Hinweis)\b/;
          const out = new Set();
          const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          for (let n = w.nextNode(); n; n = w.nextNode()) {
            const p = n.parentElement; if (!p || p.closest('[translate="no"],script,style,textarea,code,pre,[hidden]')) continue;
            if (!p.offsetParent && getComputedStyle(p).position !== 'fixed') continue;
            const t = n.nodeValue.trim(); if (t && de.test(t)) out.add(t.slice(0, 120));
          }
          for (const el of document.querySelectorAll('[data-tip-title],[placeholder],[aria-label]')) {
            if (el.closest('[translate="no"]')) continue;
            for (const a of ['data-tip-title', 'placeholder', 'aria-label']) { const t = el.getAttribute(a); if (t && de.test(t)) out.add('@' + a + ': ' + t.slice(0, 120)); }
          }
          return [...out]; })()"""
        shots = os.environ.get("TAGSTUDIO_I18N_SHOTS")              # Bildschirmfotos zur Sichtprüfung
        if shots:
            pg.screenshot(path=os.path.join(shots, "en_tagger.png"))
        left = set(pg.evaluate(scan))
        for mod in ("compare", "djset", "snapshots", "backups", "plugins", "settings", "prepare", "help"):
            loc = pg.locator(f'.nav[data-module="{mod}"]')
            if pg.locator("#modal").is_visible():
                pg.click("#mBtns button >> nth=0")
                time.sleep(0.3)
            if loc.count() and loc.is_visible():
                loc.click()
                time.sleep(0.6)
                if shots:
                    pg.screenshot(path=os.path.join(shots, f"en_{mod}.png"))
                left |= set(pg.evaluate(scan))
        # Texte, die die Übersetzung gesehen, aber nicht gefunden hat – deutsche davon (Daten wie Pfade ausgenommen)
        miss = pg.evaluate("""[...I18N.miss].filter((t) => !/^[\\/]|\\.mp3$|^https?:/.test(t)
          && /[äöüÄÖÜ]|\\b(der|die|das|und|nicht|ohne|mit|für|von|oder|holen|suchen|Daten|wählen|leer|alle|keine?|nur|wird)\\b/.test(t))""")
        left |= {"miss: " + t[:120] for t in miss}
        if os.environ.get("TAGSTUDIO_I18N_REPORT"):
            print("\nI18N-REST", json.dumps(sorted(left), ensure_ascii=False, indent=0))
        self.assertLessEqual(len(left), int(os.environ.get("TAGSTUDIO_I18N_MAXREST", "3")), sorted(left)[:60])
        self.assertEqual(self.errors, [])

    def test_i18n_help_docs(self):
        """#219: Hilfe auf Englisch zeigt die englischen Dokumente, ganz und unübersetzt (translate="no")."""
        pg = self.pg
        pg.evaluate("call('set_ui', 'lang', 'en')")
        pg.reload()
        pg.wait_for_function("typeof S !== 'undefined' && S.settings && I18N.lang === 'en'")
        self.calm()
        pg.click('.nav[data-module="help"]')
        pg.click('#helpTabs [data-htab="readme"]')
        pg.wait_for_function("document.querySelector('#helpDoc').innerText.includes('Features at a glance')")
        self.assertEqual(pg.get_attribute("#helpDoc", "translate"), "no")
        pg.click('#helpTabs [data-htab="plugins"]')
        pg.wait_for_function("document.querySelector('#helpDoc').innerText.includes('Where do plugins live?')")
        pg.click('#helpTabs [data-htab="keys"]')
        self.assertIsNone(pg.get_attribute("#helpDoc", "translate"))           # eigene Seiten werden übersetzt
        self.assertEqual(self.errors, [])

    def test_player_zoom(self):
        """#224: Lupe – hochaufgelöster Ausschnitt um die Position, Serato oben/Analyse unten, Zoom, Klick springt, gemerkt."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("plLoad({kind: 'tag', ref: 0}, false)")
        self.assertTrue(self.until("PLAYER.info && PLAYER.audio.src"))
        pg.click("#plZoomBtn")
        pg.wait_for_selector("#plZoom canvas")
        self.assertTrue(self.until("PL_ZOOM.data && PL_ZOOM.data.length > 1000", 20))   # Audio dekodiert
        self.assertEqual(pg.inner_text("#zmSpan"), "4 s")
        pg.click('#plZoom [data-z="1"]')
        self.assertEqual(pg.inner_text("#zmSpan"), "2 s")
        pg.dispatch_event("#zmCanvas", "wheel", {"deltaY": 100})
        self.assertEqual(pg.inner_text("#zmSpan"), "4 s")
        # Serato-Raster und eigene Analyse → beide in der Legende
        pg.evaluate("""PLAYER.info.grid = {bpm: 120, first: 0.1, source: 'Serato', exact: true, markers: [{pos: 0.1, bpm: 120}]};
                       PLAYER.info.wave = {peaks: [], rms: [], beat: {bpm: 120.5, first: 0.12}}; plZoomDraw()""")
        leg = pg.inner_text("#zmLeg")
        self.assertIn("Serato 120.00 BPM", leg)
        self.assertIn("Analyse 120.50 BPM", leg)
        pg.evaluate("PLAYER.audio.currentTime = 2; plZoomDraw()")
        box = pg.locator("#zmCanvas").bounding_box()
        pg.mouse.click(box["x"] + box["width"] * 0.75, box["y"] + box["height"] / 2)   # +1 s bei 4 s Ausschnitt
        self.assertTrue(self.until("Math.abs(PLAYER.audio.currentTime - 3) < 0.3"))
        c = self.cfg_until(lambda c: (c.get("player") or {}).get("zoom") is True)
        self.assertTrue((c.get("player") or {}).get("zoom"))
        pg.click("#plZoom .zm-x")
        self.assertTrue(pg.locator("#plZoom").is_hidden())
        self.assertEqual(self.errors, [])

    def test_tagger_columns_aligned(self):
        """Kopf, Filterzeile und Liste bleiben bündig – auch mit senkrechter Bildlaufleiste in der Liste."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("tgSetCols([...tgCols().filter((c) => c !== 'grid'), 'grid'], true)")
        pg.add_style_tag(content="#tgScroll{border-right:17px solid transparent}")   # wirkt wie eine Windows-Bildlaufleiste (headless: überlagert)
        pg.set_viewport_size({"width": 2400, "height": 300})                       # wenig Höhe → Bildlaufleiste
        self.assertTrue(self.until("(() => { const s = document.querySelector('#tgScroll'); return s.scrollHeight > s.clientHeight; })()"))
        self.until("""(() => { const h = [...document.querySelectorAll('#tgHead > *')].pop(), r = [...document.querySelector('.tg-row').children].pop();
          return Math.abs(h.getBoundingClientRect().left - r.getBoundingClientRect().left) <= 1.5; })()""")   # Beobachter läuft verzögert
        d = pg.evaluate("""(() => {
          const head = [...document.querySelectorAll('#tgHead > *')], filt = [...document.querySelectorAll('#tgHeadF > *')];
          const row = [...document.querySelector('.tg-row').children];
          const L = (e) => e.getBoundingClientRect().left;
          return { sb: document.querySelector('#tgScroll').offsetWidth - document.querySelector('#tgScroll').clientWidth,
                   head: L(head[head.length - 1]), filt: L(filt[filt.length - 1]), row: L(row[row.length - 1]) }; })()""")
        self.assertGreater(d["sb"], 0, d)
        self.assertLessEqual(abs(d["head"] - d["row"]), 1.5, d)
        self.assertLessEqual(abs(d["filt"] - d["row"]), 1.5, d)
        self.assertEqual(self.errors, [])

    def test_tagger_grid_status(self):
        """#191: Spalte „Beatgrid“ – Status im Hintergrund, Filter, Analyse über das Kontextmenü (nur Cache)."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("tgSetCols([...tgCols().filter((c) => c !== 'grid'), 'grid'], true)")
        self.assertTrue(self.until("TG.rows.every((r) => r.grid)", 10))                  # Status nachgeholt
        codes = pg.evaluate("TG.rows.map((r) => r.grid)")
        self.assertTrue(all(c in ("bpm", "none", "analyse", "nobeat", "serato", "serato_ok", "serato_diff", "tag") for c in codes), codes)
        self.assertTrue(pg.locator("#tgInner .tg-grid").count() >= 3)
        sel = '#tgHeadF select[data-cf="grid"]'                                         # Auswahl mit den Zuständen
        pg.wait_for_selector(sel)
        label = pg.evaluate("tgGridText(TG.rows[0])")
        n = pg.evaluate(f"TG.rows.filter((r) => tgGridText(r) === {json.dumps(label)}).length")
        self.assertIn(f"{label} ({n})", pg.inner_text(sel))
        pg.select_option(sel, label)
        self.assertTrue(self.until(f"TG.view.length === {n} && TG.view.every((v) => tgGridText(TG.rows[v.i]) === {json.dumps(label)})"))
        pg.select_option(sel, "")
        self.assertTrue(self.until("TG.view.length === TG.rows.length"))
        # Analyse über das Kontextmenü (dieselbe wie im Player, Ergebnis nur im Cache)
        pg.click(".tg-row >> nth=0", button="right")
        pg.click('.menu button:has-text("Beatgrid analysieren")')
        self.assertTrue(self.until("!TGG.run && /Beatgrid-Analyse/.test(document.querySelector('#toast')?.textContent || '')", 30))
        self.assertIn(pg.evaluate("TG.rows[TG.view[0].i].grid"), ("analyse", "nobeat", "bpm"))
        self.assertFalse(pg.evaluate("TG.rows.some((r) => r.modified)"))                 # nichts am MP3 geändert
        self.assertEqual(self.errors, [])

    def test_serato_compare(self):
        """#223: Serato-Raster gegen eigene Analyse – Spalte mit Hinweis, Filterauswahl, Player-Status, Menüeintrag."""
        pg = self.pg
        self.load_tagger()
        r = pg.evaluate("""[plGridCompare({bpm: 126, first: 0.25}, {bpm: 63, first: 0.25}),
                            plGridCompare({bpm: 126, first: 0.25}, {bpm: 126, first: 0.25 + 60 / 126})]""")
        self.assertEqual([x["ok"] for x in r], [False, True])
        self.assertIn("doppeltes Tempo in Serato", r[0]["note"])
        st = pg.evaluate("""[plGridStatus({grid: {source: 'Serato', exact: true, bpm: 126, markers: [{pos: 0.25, bpm: 126}], check: {ok: false, note: 'Tempo weicht ab'}}}),
                             plGridStatus({grid: {source: 'Serato', exact: true, bpm: 126, markers: [{pos: 0.25, bpm: 126}]}})]""")
        self.assertEqual((st[0]["label"], st[1]["label"]), ("Serato ≠ Analyse", "Serato-Grid"))
        self.assertIn("Tempo weicht ab", st[0]["hint"])
        pg.evaluate("tgSetCols([...tgCols().filter((c) => c !== 'grid'), 'grid'], true)")
        self.assertTrue(self.until("TG.rows.every((r) => r.grid)", 10))
        pg.evaluate("""TG.rows[TG.view[0].i].grid = 'serato_diff'; TG.rows[TG.view[0].i].grid_note = 'Serato 126,0 BPM, Analyse 63,0 BPM';
                       drawTgList(); tgGridFilterRefresh()""")
        cell = pg.locator(".tg-row >> nth=0").locator(".tg-grid")
        self.assertEqual(cell.inner_text(), "Serato ≠ Analyse")
        self.assertIn("Analyse 63,0 BPM", cell.evaluate("(e) => e.outerHTML"))   # Hinweis im Tooltip
        self.assertIn("Serato ≠ Analyse (1)", pg.inner_text('#tgHeadF select[data-cf="grid"]'))
        pg.click(".tg-row >> nth=0", button="right")
        self.assertEqual(pg.locator('.menu button:has-text("auch Serato, zum Vergleich")').count(), 1)
        pg.keyboard.press("Escape")
        self.assertEqual(self.errors, [])

    def test_beatgrid_to_tag(self):
        """#221: Raster der eigenen Analyse ins MP3 übernehmen – Vorschau, Übernehmen (geändert, nicht gespeichert), Status."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("""(async () => { const i = TG.view[0].i; const info = await call('media_url', 'tag', i);
          await call('wave_save', info.wave_key, Array(100).fill(9), Array(100).fill(9), { bpm: 123.4, first: 0.25, conf: 0.8 }); })()""")
        pg.evaluate("tgSetCols([...tgCols().filter((c) => c !== 'grid'), 'grid'], true)")
        pg.click(".tg-row >> nth=0")
        pg.click(".tg-row >> nth=0", button="right")
        pg.click('.menu button:has-text("Beatgrid in Tag speichern")')
        pg.wait_for_selector("#modal table")
        self.assertIn("bpm=123.400; first=0.2500", pg.inner_text("#modal table"))
        self.assertIn("nur zum Vergleich", pg.inner_text("#modal"))                  # #223: Option für Serato-Titel
        pg.check("#btSerato")
        self.assertTrue(self.until("document.querySelector('#modal table')?.textContent.includes('bpm=123.400')"))
        pg.click("#mBtns .primary")
        self.assertTrue(self.until("TG.rows[TG.view[0].i].grid === 'tag' && TG.rows[TG.view[0].i].modified"))
        self.assertIn("Analyse (Tag)", pg.inner_text(".tg-row >> nth=0"))
        self.assertEqual(self.errors, [])

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

    def test_compare_origin_multiselect(self):
        """#198 Herkunfts-Auswahl im Vergleich (Mehrfachauswahl, Kennzeichen-Klick), #197 Dateiordner im Kontextmenü."""
        from helpers import text, txxx, write_mp3
        pg = self.pg
        a, b = os.path.join(self.dir, "A"), os.path.join(self.dir, "B")
        os.makedirs(a); os.makedirs(b)
        tags = [text("TIT2", "X"), txxx("Meter", "4/4"), txxx("Eigenes", "1"), txxx("CATALOGNUMBER", "C1")]
        write_mp3(os.path.join(a, "x.mp3"), tags)
        write_mp3(os.path.join(b, "x.mp3"), [text("TIT2", "Y")])
        pg.click('.nav[data-module="compare"]')
        pg.fill("#pathL", a)
        pg.fill("#pathR", b)
        pg.evaluate("void compare(true)")
        self.assertTrue(self.until("S.pairs.length === 1 && S.view && S.view.rows.length > 2", 10))
        counts = pg.evaluate("S.srcCounts")
        keys = [k for k in counts if k not in ("id3v3", "id3v4")][:2]
        self.assertEqual(len(keys), 2, counts)
        pg.click("#cmpSrc")
        for k in keys:
            pg.click(f'#menu .menu-chk:has(.src-b[data-sid="{k}"])')
        want = pg.evaluate(f"S.view.rows.filter(r => cmpSrcOf(r).some(k => {keys!r}.includes(k))).length")
        self.assertTrue(self.until(f"S.srcSel.size === 2 && document.querySelectorAll('#tbody .tr').length === {want}"))
        self.assertEqual(pg.locator("#cmpSrc .src-b").count(), 2)
        pg.keyboard.press("Escape"); pg.evaluate("hideMenu()")
        # Klick auf ein Kennzeichen in der Liste: nur diese Herkunft, nochmals: alle
        pg.click(f'#tbody .f-id .src-b[data-sid="{keys[0]}"] >> nth=0')
        self.assertTrue(self.until(f"S.srcSel.size === 1 && S.srcSel.has('{keys[0]}')"))
        pg.click(f'#tbody .f-id .src-b[data-sid="{keys[0]}"] >> nth=0')
        self.assertTrue(self.until("S.srcSel.size === 0"))
        # #197
        pg.click('.tr[data-key="TIT2"] .v[data-side="L"]', button="right")
        self.assertTrue(pg.locator("#menu button", has_text="Dateiordner öffnen").is_visible())
        pg.evaluate("hideMenu()")
        pg.evaluate("""document.querySelector('.pair[data-i="0"]').dispatchEvent(new MouseEvent('contextmenu',
            {bubbles: true, cancelable: true, clientX: 50, clientY: 50}))""")
        pg.wait_for_selector("#menu button >> text=Dateiordner öffnen (links)")
        self.assertTrue(pg.locator("#menu button", has_text="Dateiordner öffnen (links)").is_visible())
        pg.evaluate("hideMenu()")
        self.assertEqual(self.errors, [])

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
        self.assertIn(pg.evaluate("I18N.lang"), (pg.evaluate("i18nSysLang()"),))     # erster Start: Betriebssystem-Sprache
        self.assertTrue(pg.locator('#wizard .lang-menu [data-lang="auto"].on').count())
        self.assertEqual(self.cfg_until(lambda c: (c.get("web_ui") or {}).get("lang") == "auto")["web_ui"]["lang"], "auto")
        if pg.evaluate("I18N.lang") != "de-CH":                     # Rest des Tests auf Deutsch
            with pg.expect_navigation():                             # zurück auf Deutsch lädt die Seite neu
                self.lang_pick("#wizard", "de-CH")
            pg.wait_for_selector("#wizard .wiz-box")                  # #230: init startet erst nach allen Skripten
            self.assertFalse(pg.locator('#wizard .lang-menu [data-lang="auto"].on').count())
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
            self.until(f"call('snap_list', '{lid}').then(r => r.snapshots.length >= {1 if label == 'Alt' else 2})", 10)
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
            if sorted(snaps) == [["Baseline", True], ["Wichtig", False]]:   # Baseline da und ältere gelöscht
                break
            time.sleep(0.1)
        self.assertEqual(sorted(snaps), [["Baseline", True], ["Wichtig", False]])
        pg.wait_for_selector("#snSnaps .sn-base")

    def test_plugin_cards(self):
        """Plugin-Karten: gleich gross, Kategorie, Abschnitte, feste Funktionsknöpfe (ausgegraut, wenn nicht vorhanden),
        „Weitere Funktionen …“ mit den übrigen Funktionen."""
        pg = self.pg
        self.calm()
        pg.click('.nav[data-module="plugins"]')
        pg.wait_for_selector('.pl-card[data-pid="beatport"] .pl-btns')
        hs = pg.evaluate("[...document.querySelectorAll('.pl-card')].map((c) => Math.round(c.getBoundingClientRect().height))")
        self.assertGreater(len(hs), 5)
        self.assertEqual(len(set(hs)), 1, hs)                                   # alle Kacheln gleich gross
        cat = lambda pid: pg.inner_text(f'.pl-card[data-pid="{pid}"] .plg-tag.cat')
        self.assertEqual(cat("beatport"), "Online-API")
        self.assertEqual(cat("lexicon"), "Lokale API")
        self.assertEqual(cat("mik"), "Übernahme aus Tags")
        self.assertEqual(cat("loudness"), "Audio-Verarbeitung")
        order = pg.evaluate("""[...document.querySelector('.pl-card[data-pid="acoustid"]').children].map((e) => e.className.split(' ')[0])""")
        self.assertEqual(order, ["pl-head", "pl-desc", "pl-acts", "pl-svc", "pl-hints", "pl-btns"])
        btns = lambda pid: pg.evaluate(f"""[...document.querySelectorAll('.pl-card[data-pid="{pid}"] .pl-btns button')].map((b) => [b.textContent.trim(), b.disabled])""")
        self.assertEqual(btns("acoustid"), [["Testen", False], ["Schlüssel", False], ["Optionen", True], ["Mehr …", False]])
        self.assertEqual(btns("mik"), [["Testen", True], ["Schlüssel", True], ["Optionen", True], ["Mehr …", False]])   # Mehr: Ordner öffnen
        self.assertEqual(btns("beatport")[1], ["Anmelden", False])
        # Zeilen bündig: Aktionen, API und Hinweise beginnen in jeder Karte an derselben Stelle (relativ zur Karte)
        rel = pg.evaluate("""[...document.querySelectorAll('.pl-card')].map((c) => { const t = c.getBoundingClientRect().top;
          return ['.pl-desc', '.pl-acts', '.pl-svc', '.pl-hints', '.pl-btns'].map((q) => Math.round(c.querySelector(q).getBoundingClientRect().top - t)); })""")
        self.assertEqual(len({tuple(r) for r in rel}), 1, rel)
        # Status über dem Schalter, Kategorie unter dem Titel
        self.assertTrue(pg.evaluate("""(() => { const c = document.querySelector('.pl-card[data-pid="acoustid"]');
          const st = c.querySelector('.pl-st').getBoundingClientRect(), sw = c.querySelector('.switch').getBoundingClientRect(),
                h = c.querySelector('h3').getBoundingClientRect(), cat = c.querySelector('.plg-tag.cat').getBoundingClientRect();
          return st.bottom <= sw.top + 1 && cat.top >= h.bottom - 1; })()"""))
        # Symbol je Kategorie, so hoch wie Titel + Kategorie
        g = pg.evaluate("""(() => { const c = document.querySelector('.pl-card[data-pid="acoustid"]'); const r = (q) => c.querySelector(q).getBoundingClientRect();
          return [r('.pl-ico').top - r('h3').top, r('.pl-ico').bottom - r('.pl-cat').bottom]; })()""")
        self.assertTrue(all(abs(x) <= 2 for x in g), g)
        self.assertTrue(pg.locator('.pl-card[data-pid="loudness"] .pl-ico.cat-audio').count())
        # lange Beschreibung: „mehr“ klappt sie über der Karte auf, die Karte selbst bleibt gleich hoch
        card = '.pl-card[data-pid="beatport"]'
        self.assertTrue(pg.locator(card + " [data-dmore]").is_visible())
        h0 = pg.evaluate(f"document.querySelector('{card}').getBoundingClientRect().height")
        pg.click(card + " [data-dmore]")
        self.assertIn("weniger", pg.inner_text(card + " .pl-desc"))
        self.assertIn("Metadaten deiner eigenen Titel", pg.inner_text(card + " .pl-desc"))
        self.assertEqual(h0, pg.evaluate(f"document.querySelector('{card}').getBoundingClientRect().height"))
        pg.click(card + " [data-dmore]")
        self.assertFalse(pg.locator(card + " .pl-desc.open").count())
        self.assertIn("verschlüsselt", pg.inner_text('.pl-card[data-pid="acoustid"] .pl-hints'))
        # Plugin-Ordner öffnen: Menü mit eigenen und eingebauten Plugins
        pg.click("#plOpen")
        menu = pg.inner_text("#menu")
        self.assertIn("Eigene Plugins", menu)
        self.assertIn("Eingebaute Plugins", menu)
        pg.keyboard.press("Escape")
        pg.mouse.click(5, 5)
        # Weitere Funktionen: Beatport hat Abmelden, Käufe abgleichen, Download und Integration
        pg.click('.pl-card[data-pid="beatport"] [data-plmore]')
        pg.wait_for_selector("#mBody .pl-more")
        more = pg.inner_text("#mBody .pl-more")
        for t in ("Abmelden", "Integration", "herunterladen"):
            self.assertIn(t, more)
        pg.click('#mBody [data-more]:has-text("Integration")')
        pg.wait_for_selector("#svcBody, #modal .svc-tab, #modal table")
        self.assertIn("Beatport", pg.inner_text("#mTitle"))
        pg.keyboard.press("Escape")
        # fehlende Pakete: ein Knopf, Varianten im Fenster
        if pg.locator('.pl-card[data-pid="stems"] [data-plinstall]').count():
            pg.click('.pl-card[data-pid="stems"] [data-plinstall]')
            pg.wait_for_selector("#mBody .pl-more [data-more]")
            self.assertGreaterEqual(pg.locator("#mBody .pl-more [data-more]").count(), 2)
            pg.keyboard.press("Escape")
        # Filter nach Art: Audio-Verarbeitung → nur Tonart (OpenKeyScan), Lautheit und Stems; gemerkt; „Alle“ zeigt wieder alles
        n_all = pg.locator(".pl-card").count()
        pg.click('#plFilter [data-plcat="audio"]')
        self.assertEqual(sorted(pg.evaluate("[...document.querySelectorAll('.pl-card')].map((c) => c.dataset.pid)")), ["keyscan", "loudness", "stems"])
        self.assertIn("3", pg.inner_text('#plFilter [data-plcat="audio"]'))
        pg.click('.nav[data-module="settings"]'); pg.click('.nav[data-module="plugins"]')
        pg.wait_for_selector('#plFilter [data-plcat="audio"].on')
        self.assertEqual(pg.locator(".pl-card").count(), 3)
        pg.click('#plFilter [data-plcat=""]')
        self.assertEqual(pg.locator(".pl-card").count(), n_all)
        # eingebaut: eine Zeile, auch übersetzt
        h = pg.evaluate("""(() => { const t = document.querySelector('.pl-card[data-pid="beatunes"] .plg-tag'); return [t.getClientRects().length, getComputedStyle(t).whiteSpace]; })()""")
        self.assertEqual(h, [1, "nowrap"])
        self.assertEqual(self.errors, [])

    def test_lyrics_plugin(self):
        """#183: Plugin Liedtexte – Einstellungen (.lrc, Sprache) auf der Plugin-Seite, Formular im Tagger,
        mehrzeilige Werte in der Vorschau. Die LRCLIB-Abfrage selbst prüft tests/test_lyrics.py (ohne Netz)."""
        pg = self.pg
        pg.click('.nav[data-module="plugins"]')
        card = '.pl-card[data-pid="lyrics"]'
        pg.wait_for_selector(card)
        if not pg.locator(card + " [data-enable]").is_checked():
            pg.click(card + " .switch")
            pg.wait_for_selector(card + ' [data-paction="settings"]')
        self.assertIn(".lrc-Datei: nein", pg.inner_text(card))
        pg.click(card + ' [data-paction="settings"]')
        pg.wait_for_selector('#modal [data-ok="lrc"]')
        self.assertFalse(pg.locator('#modal [data-ok="lrc"]').is_checked())
        pg.check('#modal [data-ok="lrc"]')
        pg.fill('#modal [data-ok="lang"]', "deu")
        pg.click("#mBtns .primary")
        self.assertTrue(self.until("document.querySelector('#modal').textContent.includes('.lrc-Datei ja')"))
        pg.click("#mBtns button >> nth=0")
        pg.wait_for_function(f"document.querySelector('{card}').textContent.includes('.lrc-Datei: ja · Sprache: deu')")
        # Formular im Tagger: Auswahl USLT/SYLT, Hinweis auf die Einstellungen (ohne Netzabfrage abbrechen)
        self.load_tagger()
        pg.click(".tg-row >> nth=0")
        pg.click('#tgPlugins [data-plugin="lyrics"][data-action="fetch"]')
        pg.wait_for_selector('#modal [data-ok="what"]')
        self.assertEqual(pg.locator('#modal [data-ok="what"]').input_value(), "both")
        self.assertIn("Einstellungen", pg.inner_text("#modal"))
        self.assertEqual(pg.locator('#modal [data-ok="lrc"]').count(), 0)        # .lrc nur in den Einstellungen
        pg.click("#mBtns button >> text=Abbrechen")
        # Vorschau: mehrzeiliger Liedtext mit Umbrüchen, begrenzte Höhe
        pg.evaluate("""void pluginPreview({label: 'Liedtexte suchen (LRCLIB) …'}, {message: 'Test', proposals: [
            {id: 0, name: 'a.mp3', group: 'a.mp3', gkey: 'a', folder: '', label: 'Liedtext (USLT)', old: '',
             new: ['Zeile 1', 'Zeile 2', 'Zeile 3'].join(String.fromCharCode(10)), note: '', checked: true, kind: 'text', hint: '', same: false}]})""")
        pg.wait_for_selector("#modal .pv-val")
        style = pg.evaluate("getComputedStyle(document.querySelector('#modal td.new .pv-val')).whiteSpace")
        self.assertEqual(style, "pre-line")
        self.assertGreater(pg.evaluate("document.querySelector('#modal td.new .pv-val').getClientRects().length && "
                                       "document.querySelector('#modal td.new .pv-val').offsetHeight"), 30)
        pg.click("#mBtns button >> text=Abbrechen")
        self.assertEqual(self.errors, [])

    def test_service_integration(self):
        """#204: Dienst-Plugins – API-Link auf der Karte, Integrationsfenster (Endpunkte, Testabfrage, API-Tester),
        Gesamtübersicht. Lexicon gegen einen lokalen Nachbau, damit kein Internet nötig ist."""
        import http.server
        import threading
        from test_services import FakeLexicon
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeLexicon)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            pg = self.pg
            path = os.path.join(self.home, ".tagstudio.json")
            pg.evaluate("appFlushState()")
            with open(path, encoding="utf-8") as fh:
                cfg = json.load(fh)
            cfg.setdefault("plugin_options", {})["lexicon"] = {"import": {"url": f"http://127.0.0.1:{srv.server_address[1]}"}}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh)
            pg = self.restart()
            pg.click('.nav[data-module="plugins"]')
            card = '.pl-card[data-pid="lexicon"]'
            pg.wait_for_selector(card)
            if not pg.locator(card + " [data-enable]").is_checked():
                pg.click(card + " .switch")
                pg.wait_for_selector(card + " [data-svcopen]")
            link = pg.locator(card + " .pl-svc .pl-link[data-url]")
            self.assertIn("lexicondj.com/docs/developers/api", link.get_attribute("data-url"))
            self.assertIn("27 Endpunkte", pg.inner_text(card + " .pl-svc"))
            # Integrationsfenster: Endpunkte mit Status, Filter
            pg.click(card + " [data-svcopen]")
            pg.wait_for_selector("#svcBody .svc-table")
            self.assertIn("Integration – Lexicon Local API", pg.inner_text("#mTitle"))
            self.assertEqual(pg.locator("#svcBody tbody tr").count(), 27)
            pg.click('#svcBody [data-svcf="partial"]')
            self.assertEqual(pg.locator("#svcBody tbody tr").count(), 6)          # #237–#239: Stand der Endpunkte
            # Testabfrage ohne Track
            pg.click('[data-svctab="tq"]')
            pg.fill('[data-tq="artist"]', "mara")
            pg.fill('[data-tq="title"]', "nordlicht")
            pg.click("#svcTqRun")
            pg.wait_for_selector("#svcTqOut table")
            self.assertIn("Nordlicht", pg.inner_text("#svcTqOut table"))
            self.assertIn("Energie 70", pg.inner_text("#svcTqOut table"))
            # API-Tester: über „Testen“ in der Endpunkt-Tabelle
            pg.click('[data-svctab="ep"]')
            pg.click('#svcBody [data-svctest="tracks"]')
            pg.wait_for_selector('#svcApi [data-ap="limit"]')
            pg.fill('#svcApi [data-ap="limit"]', "1")
            pg.click("#svcApiRun")
            pg.wait_for_selector("#svcApiOut .svc-http")
            self.assertEqual(pg.inner_text("#svcApiOut .svc-http"), "HTTP 200")
            self.assertIn('"Nordlicht"', pg.inner_text("#svcApiBody"))
            self.assertNotIn("Kaltes Glas", pg.inner_text("#svcApiBody"))       # limit=1
            # #213: ID in der Antwort anklicken → passenden Endpunkt füllen
            pg.click('#svcApiBody a.svc-id[data-idk="id"]')
            pg.wait_for_selector('#svcIdBar [data-idto="track"]')
            pg.click('#svcIdBar [data-idto="track"]')
            pg.wait_for_selector('#svcApi [data-ap="id"]')
            self.assertEqual(pg.input_value("#svcApiEp"), "track")
            self.assertEqual(pg.input_value('#svcApi [data-ap="id"]'), "1")
            pg.click("#mBtns .primary")
            # Gesamtübersicht: alle Dienste inkl. Kern
            pg.click("#plServices")
            pg.wait_for_selector("#svcOvBody")
            txt = pg.inner_text("#svcOvBody")
            for name in ("LRCLIB", "Lexicon Local API", "Beatport API v4", "GitHub Releases (Updates)"):
                self.assertIn(name, txt)
            pg.click('[data-ovf="full"]')
            self.assertEqual(pg.locator("#svcOvBody .svc-st.svc-none").count()
                             - pg.locator("#svcOvBody .svc-grp .svc-st.svc-none").count(), 0)
            pg.click('#svcOvBody [data-svcopen="lyrics"]')
            pg.wait_for_function("document.querySelector('#mTitle').textContent.includes('LRCLIB')")
            # #205: Beispielwerte vorbelegt, „Felder löschen“, „Beispiel einsetzen“
            pg.click('[data-svctab="tq"]')
            self.assertEqual(pg.input_value('[data-tq="artist"]'), "Daft Punk")
            self.assertEqual(pg.input_value('[data-tq="title"]'), "One More Time")
            pg.click("#svcTqClear")
            self.assertEqual([pg.input_value(f'[data-tq="{k}"]') for k in ("artist", "title", "duration")], ["", "", ""])
            pg.click("#svcTqEx")
            self.assertEqual(pg.input_value('[data-tq="title"]'), "One More Time")
            pg.click('[data-svctab="api"]')
            pg.select_option("#svcApiEp", "get")
            self.assertEqual(pg.input_value('#svcApi [data-ap="artist_name"]'), "Daft Punk")
            pg.click("#svcApiClear")
            self.assertEqual(pg.input_value('#svcApi [data-ap="artist_name"]'), "")
            pg.click("#svcApiEx")
            self.assertEqual(pg.input_value('#svcApi [data-ap="track_name"]'), "One More Time")
            pg.click("#mBtns .primary")
            self.assertEqual(self.errors, [])
        finally:
            srv.shutdown()

    def test_online_plugin(self):
        """#6–#8, #204: Schlüssel im Dienst-Plugin Discogs speichern (nie in der Konfiguration), Formular im Tagger."""
        pg = self.pg
        pg.click('.nav[data-module="plugins"]')
        for pid in ("online", "discogs"):
            c = f'.pl-card[data-pid="{pid}"]'
            pg.wait_for_selector(c)
            if not pg.locator(c + " [data-enable]").is_checked():
                pg.click(c + " .switch")
        card = '.pl-card[data-pid="discogs"]'
        pg.wait_for_selector(card + ' [data-paction="keys"]')
        self.assertIn("kein Token", pg.inner_text(card))
        self.assertIn("Endpunkte", pg.inner_text(card + " .pl-svc"))            # #204: Dienstbeschreibung (Integration über die Zahl)
        pg.click(card + ' [data-paction="keys"]')
        pg.wait_for_selector("#modal .pl-link")
        self.assertIn("discogs.com/settings/developers", pg.get_attribute("#modal .pl-link >> nth=0", "data-url"))
        pg.fill('#modal [data-ok="discogs"]', "geheim-123")
        pg.click("#mBtns .primary")
        pg.wait_for_selector("#modal .pl-log, #modal p")
        self.assertTrue(self.until("document.querySelector('#modal').textContent.includes('Token gespeichert')"))
        pg.click("#mBtns button >> nth=0")
        pg.wait_for_function(f"document.querySelector('{card}').textContent.includes('Token gespeichert')")
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

    def test_crossfade_phase_lock_and_log(self):
        """#181: Übergang in Player A wird gemessen, im Takt nachgeführt und protokolliert."""
        pg = self.pg
        self.load_tagger()
        pg.evaluate("plSetPref('xfade', 4); plSetPref('xfade_return', 0); plSetPref('xfade_phase', true);"
                    "plSetPref('xfade_lock', true); plSetPref('xfade_seek_ms', 0); PLAYER.xfadeLog = []")
        pg.click(".tg-row >> nth=0")
        pg.keyboard.press(" ")
        self.assertTrue(self.until("!PLAYER.audio.paused && PLAYER.audio.duration > 0"))
        self.assertTrue(self.until("!!gridOf(PLAYER.info)", 6))
        pg.evaluate("PLAYER.audio.currentTime = PLAYER.audio.duration - 6")
        self.assertTrue(self.until("!!PLAYER.fade && PLAYER.ref === 1", 6))
        self.assertTrue(self.until("!PLAYER.fade && (PLAYER.xfadeLog || []).length === 1", 10))
        e = pg.evaluate("PLAYER.xfadeLog[0]")
        print("\n  Übergang:", {k: e[k] for k in ("start_err_ms", "settled_after_ms", "end_err_ms", "max_nudge_pct",
                                               "learned_pre_ms") if k in e}, flush=True)
        self.assertEqual(e["reason"], "fertig")
        self.assertTrue(e["lock"])
        self.assertIsNotNone(e["start_err_ms"], e)
        self.assertLessEqual(abs(e["end_err_ms"]), 20, e)
        self.assertGreaterEqual(len(e["trace"]), 3, e)
        # Tempo-Korrektur zurückgenommen, gelernter Vorhalt gespeichert
        self.assertTrue(self.until("Math.abs(PLAYER.audio.playbackRate - 1) < 0.0005", 3))
        want = e.get("learned_pre_ms", 0)
        c = self.cfg_until(lambda c: c.get("player", {}).get("xfade_seek_ms", 0) == want)
        self.assertEqual(c.get("player", {}).get("xfade_seek_ms", 0), want)
        # Messwerte-Dialog in den Einstellungen
        pg.evaluate("PLAYER.audio.pause()")
        pg.click('.nav[data-module="settings"]')
        pg.wait_for_selector("#stPlXfLock")
        self.assertTrue(pg.is_checked("#stPlXfLock"))
        self.assertIn(f"gelernt: {want} ms", pg.inner_text("#stPlXfSeek"))
        pg.click("#stPlXfLog")
        pg.wait_for_selector("#mBody .help-t")
        self.assertIn(e["to"], pg.inner_text("#mBody"))
        pg.keyboard.press("Escape")
        pg.click("#stPlXfSeekReset")
        c = self.cfg_until(lambda c: c.get("player", {}).get("xfade_seek_ms", 0) == 0)
        self.assertEqual(c["player"]["xfade_seek_ms"], 0)

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
        for _ in range(3):         # CI ist langsamer: die Liste kann nach „Vorher/Nachher“ gerade neu gezeichnet werden
            pg.click('#djList .dj-row[data-k="0"] [data-lock]')
            if self.until("DJ.st.items[0].lock", 3):
                break
        self.assertTrue(pg.evaluate("DJ.st.items[0].lock"))
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
