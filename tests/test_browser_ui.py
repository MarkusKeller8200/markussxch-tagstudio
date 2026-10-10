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
        self.assertEqual(navs, ["tagger", "fixer", "compare", "djset", "snapshots", "backups", "plugins", "settings", "db"])
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
