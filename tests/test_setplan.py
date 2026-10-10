"""Tests für die DJ-Set-Optimierung (setplan.py)."""
import itertools
import os
import random
import tempfile
import time
import unittest

from helpers import write_mp3, text, txxx

import setplan
from setplan import Options, Track
from id3tags import MP3File

KEYS = [f"{n}{m}" for n in range(1, 13) for m in "AB"]


def random_tracks(n, seed=1, missing=0.0):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        out.append(Track(
            id=i,
            key=None if rnd.random() < missing else rnd.choice(KEYS),
            bpm=None if rnd.random() < missing else round(rnd.uniform(118, 132), 1),
            energy=None if rnd.random() < 0.3 else rnd.randint(20, 95),
        ))
    return out


def brute(tracks, opts):
    m = setplan._Model(tracks, opts)
    best = min(itertools.permutations(range(len(tracks))), key=lambda o: m.cost(list(o)))
    return m.cost(list(best))


def cost_of(tracks, ids, opts):
    by = {t.id: t for t in tracks}
    m = setplan._Model(tracks, opts)
    pos = {t.id: i for i, t in enumerate(tracks)}
    return m.cost([pos[i] for i in ids])


class TestParts(unittest.TestCase):
    def test_key_kinds(self):
        k = setplan.key_kind
        self.assertEqual(k("8A", "8A")[0], "same")
        self.assertEqual(k("8A", "9A")[0], "adjacent")
        self.assertEqual(k("12A", "1A")[0], "adjacent")      # Rad schliesst sich
        self.assertEqual(k("8A", "8B")[0], "parallel")
        self.assertEqual(k("8A", "10A")[0], "boost")
        self.assertEqual(k("8A", "9B")[0], "boost")
        self.assertEqual(k("8A", "2B")[0], "jump")
        self.assertEqual(k(None, "2B")[0], "unknown")
        self.assertLess(k("8A", "11A")[1], k("8A", "2B")[1])  # weiter weg = teurer
        self.assertEqual(k("3A", "7B"), k("7B", "3A"))        # symmetrisch

    def test_bpm_half_double(self):
        pct, rel = setplan.bpm_step(128, 64)
        self.assertEqual((pct, rel), (0.0, "x2"))
        pct, rel = setplan.bpm_step(87, 174)
        self.assertEqual((round(pct, 1), rel), (0.0, "half"))
        pct, rel = setplan.bpm_step(120, 126)
        self.assertEqual((round(pct, 1), rel), (5.0, ""))
        self.assertEqual(setplan.bpm_step(None, 120), (None, ""))

    def test_bpm_symmetric(self):
        for a, b in ((60, 128), (120, 126), (87, 176), (124, 124)):
            self.assertAlmostEqual(setplan.bpm_step(a, b)[0], setplan.bpm_step(b, a)[0])

    def test_matrix_matches_transition(self):
        """Die schnelle Kostenmatrix muss genau transition()["cost"] entsprechen – in beide Richtungen."""
        tr = random_tracks(30, 9, missing=0.2)
        for prof in ("none", "wave"):
            o = Options(profile=prof, max_jump=4)
            m = setplan._Model(tr, o)
            for i in range(30):
                for j in range(30):
                    if i != j:
                        self.assertAlmostEqual(m.T[i][j], setplan.transition(tr[i], tr[j], o)["cost"], places=12)

    def test_energy_estimate(self):
        self.assertEqual(setplan.energy_of(Track(1, energy=55)), (55, False))
        e, est = setplan.energy_of(Track(1, bpm=140))
        self.assertTrue(est)
        self.assertEqual(e, 90)
        self.assertEqual(setplan.energy_of(Track(1, bpm=70))[0], setplan.energy_of(Track(1, bpm=140))[0])
        self.assertEqual(setplan.energy_of(Track(1)), (None, True))

    def test_transition_over_max(self):
        o = Options(max_jump=6)
        tr = setplan.transition(Track(1, "8A", 120), Track(2, "8A", 130), o)
        self.assertTrue(tr["bpm_over"])
        self.assertEqual(tr["score"], 0)
        tr = setplan.transition(Track(1, "8A", 124), Track(2, "9A", 126), o)
        self.assertFalse(tr["bpm_over"])
        self.assertGreater(tr["score"], 80)
        self.assertEqual(tr["key"], "adjacent")

    def test_curve(self):
        self.assertEqual(setplan.target_curve("rise", 3, 20, 80), [20, 50, 80])
        self.assertEqual(setplan.target_curve("fall", 2, 0, 100), [100, 0])
        w = setplan.target_curve("wave", 5, 0, 100)
        self.assertAlmostEqual(w[0], 0)
        self.assertAlmostEqual(w[1], 100)
        self.assertEqual(setplan.target_curve("none", 3, 0, 1), [None] * 3)

    def test_options_from_dict(self):
        o = Options.from_dict({"w_key": "0.7", "profile": "xyz", "locks": {"2": 5}, "max_jump": 0, "start": 3})
        self.assertEqual(o.w_key, 0.7)
        self.assertEqual(o.profile, "none")
        self.assertEqual(o.locks, {2: 5})
        self.assertEqual(o.max_jump, 0.5)
        self.assertEqual(o.start, 3)


class TestOptimize(unittest.TestCase):
    def test_exact_equals_brute_force(self):
        for seed in range(6):
            for profile in ("none", "rise", "wave"):
                tr = random_tracks(7, seed)
                o = Options(profile=profile)
                r = setplan.optimize(tr, o)
                self.assertEqual(r["method"], "exact")
                self.assertAlmostEqual(cost_of(tr, r["order"], o), brute(tr, o), places=9,
                                       msg=f"seed {seed} {profile}")

    def test_heuristic_close_to_optimum(self):
        worse = 0
        for seed in range(5):
            tr = random_tracks(8, seed + 10)
            o = Options(exact_max=0, time_limit=1)
            r = setplan.optimize(tr, o)
            self.assertEqual(r["method"], "heuristic")
            if cost_of(tr, r["order"], o) > brute(tr, o) * 1.05 + 1e-9:
                worse += 1
        self.assertLessEqual(worse, 1)

    def test_harmonic_chain_found(self):
        keys = ["5A", "6A", "7A", "8A", "9A", "10A"]
        tr = [Track(i, k, 124) for i, k in enumerate(keys)]
        random.Random(3).shuffle(tr)
        r = setplan.optimize(tr)
        got = [next(t.key for t in tr if t.id == i) for i in r["order"]]
        self.assertIn(got, (keys, keys[::-1]))
        self.assertGreaterEqual(r["after"]["score"], r["before"]["score"])
        self.assertTrue(all(t["key"] == "adjacent" for t in r["after"]["transitions"]))

    def test_start_end_and_locks(self):
        tr = random_tracks(9, 4)
        for exact_max in (13, 0):
            o = Options(start=5, end=2, locks={3: 7}, exact_max=exact_max, time_limit=0.5)
            r = setplan.optimize(tr, o)
            self.assertEqual(r["order"][0], 5)
            self.assertEqual(r["order"][-1], 2)
            self.assertEqual(r["order"][3], 7)
            self.assertEqual(sorted(r["order"]), list(range(9)))

    def test_locked_brute_force(self):
        tr = random_tracks(7, 8)
        o = Options(start=0, locks={4: 6})
        r = setplan.optimize(tr, o)
        m = setplan._Model(tr, o)
        best = min((p for p in itertools.permutations(range(7)) if p[0] == 0 and p[4] == 6),
                   key=lambda p: m.cost(list(p)))
        self.assertAlmostEqual(m.cost(r["order"]), m.cost(list(best)), places=9)

    def test_missing_end_and_neutral(self):
        tr = random_tracks(10, 2, missing=0.25)
        r = setplan.optimize(tr, Options(missing="end"))
        rest = r["rest"]
        self.assertTrue(rest)
        self.assertEqual(r["order"][-len(rest):], rest)
        r2 = setplan.optimize(tr, Options(missing="neutral"))
        self.assertEqual(r2["rest"], [])
        self.assertEqual(sorted(r2["order"]), list(range(10)))

    def test_trivial_sizes(self):
        self.assertEqual(setplan.optimize([])["order"], [])
        self.assertEqual(setplan.optimize([Track("a", "8A", 120)])["order"], ["a"])
        with self.assertRaises(ValueError):
            setplan.optimize([Track(1), Track(1)])

    def test_runtime_200(self):
        tr = random_tracks(200, 7)
        t0 = time.monotonic()
        r = setplan.optimize(tr, Options(time_limit=3, profile="rise"))
        dt = time.monotonic() - t0
        self.assertLess(dt, 6)
        self.assertEqual(sorted(r["order"]), list(range(200)))
        self.assertGreater(r["after"]["score"], r["before"]["score"])

    def test_exact_runtime(self):
        t0 = time.monotonic()
        r = setplan.optimize(random_tracks(setplan.EXACT_MAX, 1), Options(profile="wave"))
        self.assertEqual(r["method"], "exact")
        self.assertLess(time.monotonic() - t0, 15)


class TestSession(unittest.TestCase):
    """DJ-Set in der Sitzung (#3): hinzufügen, optimieren, sperren, Reihenfolge, gemerkt in der Konfiguration."""

    def setUp(self):
        import core
        self.dir = tempfile.mkdtemp(prefix="tagstudio_dj_")
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.dir
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(self.dir, "cfg.json")
        self.lib = os.path.join(self.dir, "lib")
        os.makedirs(self.lib)
        spec = [("a", "10A", "124"), ("b", "8A", "124"), ("c", "9A", "125"), ("d", "11A", "126"), ("e", "", "")]
        for n, (name, key, bpm) in enumerate(spec):
            fr = [text("TIT2", name.upper())]
            if key:
                fr += [text("TKEY", key), text("TBPM", bpm)]
            write_mp3(os.path.join(self.lib, f"{name}.mp3"), fr, audio_seed=n + 1)

    def tearDown(self):
        import core
        import shutil
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def session(self):
        from session import Session
        s = Session()
        s.start_tag_load(self.lib, False)
        while not s.task_status()["done"]:
            time.sleep(0.02)
        return s

    def names(self, st):
        return [r["name"] for r in st["items"]]

    def test_flow(self):
        s = self.session()
        st = s.dj_add()
        self.assertEqual(len(st["items"]), 5)
        self.assertIn("5 Titel", st["message"])
        self.assertIn("schon im Set", s.dj_add([0])["message"])
        # Ordnung a b c d e → optimiert 8A 9A 10A 11A (oder umgekehrt), Titel ohne Tonart ans Ende
        st = s.dj_optimize()
        got = self.names(st)
        self.assertEqual(got[-1], "e.mp3")
        self.assertIn(got[:4], (["b.mp3", "c.mp3", "a.mp3", "d.mp3"], ["d.mp3", "a.mp3", "c.mp3", "b.mp3"]))
        self.assertEqual(st["method"], "exact")
        self.assertGreaterEqual(st["score"], st["before"])
        self.assertTrue(st["can_revert"])
        tr = st["items"][0]["to_next"]
        self.assertEqual(tr["key"], "adjacent")
        self.assertIsNone(st["items"][-1]["to_next"])
        # Vorher/Nachher
        back = s.dj_revert()
        self.assertEqual(self.names(back), ["a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3"])
        self.assertEqual(self.names(s.dj_revert()), got)
        # Sperren: a an Position 0 festhalten
        s.dj_order([os.path.join(self.lib, "a.mp3")])
        s.dj_lock(os.path.join(self.lib, "a.mp3"), True)
        st = s.dj_optimize()
        self.assertEqual(self.names(st)[0], "a.mp3")
        self.assertTrue(st["items"][0]["lock"])
        # Optionen und Entfernen
        st = s.dj_set_opt("profile", "rise")
        self.assertEqual(st["opts"]["profile"], "rise")
        self.assertIsNotNone(st["energy_fit"])
        self.assertEqual(s.dj_set_opt("max_jump", 99)["opts"]["max_jump"], 30)
        with self.assertRaises(ValueError):
            s.dj_set_opt("nix", 1)
        st = s.dj_remove([os.path.join(self.lib, "e.mp3")])
        self.assertEqual(len(st["items"]), 4)
        self.assertEqual(len(s.dj_tag_indices()), 4)

    def test_tagger_state(self):
        """#127: Zustand speichern (bereinigt) und Startvorgabe."""
        s = self.session()
        self.assertEqual(s.tagger_start(), "last")
        self.assertTrue(s.tag_state_save({"root": self.lib, "recursive": 1, "sel": ["a.mp3", 5, "b.mp3"],
                                          "sort": {"col": "TIT2", "dir": -1}, "query": "x" * 500, "scroll": -3,
                                          "open": None, "anchor": "a.mp3"}))
        st = s.tag_state()
        self.assertEqual((st["sel"], st["recursive"], st["sort"], len(st["query"]), st["scroll"], st["open"]),
                         (["a.mp3", "b.mp3"], True, {"col": "TIT2", "dir": -1}, 200, 0, []))
        self.assertFalse(s.tag_state_save(dict(st)))          # unverändert → nicht neu schreiben
        from session import Session
        s2 = Session()
        ts = s2.tagger_settings()
        self.assertEqual((ts["start"], ts["state"]["root"], ts["state"]["exists"]), ("last", self.lib, True))
        s2.set_view_default("tagger", "autoload", True)        # alte Einstellung wird übernommen
        self.assertEqual(s2.tagger_start(), "default")
        s2.set_view_default("tagger", "start", "none")
        self.assertEqual(s2.tagger_start(), "none")
        with self.assertRaises(ValueError):
            s2.set_view_default("tagger", "start", "irgendwo")
        with self.assertRaises(ValueError):
            s2.tag_state_save("kaputt")

    def test_window_geometry(self):
        """#125: Fenstergeometrie merken, prüfen und beim Start anwenden."""
        from session import Session
        s = Session()
        self.assertEqual(s.window_start([]), {"width": 1440, "height": 920, "maximized": False})
        s.set_window_geometry({"w": 1600, "h": 1000, "x": 100, "y": 50, "max": False})
        two = [(0, 0, 1920, 1080), (1920, 0, 2560, 1440)]
        self.assertEqual(Session().window_start(two), {"width": 1600, "height": 1000, "maximized": False, "x": 100, "y": 50})
        # auf dem zweiten Bildschirm, der jetzt fehlt → Position verwerfen, Grösse bleibt
        s.set_window_geometry({"w": 1600, "h": 1000, "x": 2500, "y": 100})
        self.assertNotIn("x", Session().window_start([(0, 0, 1920, 1080)]))
        self.assertEqual(Session().window_start(two)["x"], 2500)
        # zu gross für den einzigen Bildschirm → verkleinern, nie unter die Mindestgrösse
        s.set_window_geometry({"w": 3000, "h": 2000, "x": 0, "y": 0, "max": True})
        st = Session().window_start([(0, 0, 1366, 768)])
        self.assertEqual((st["width"], st["height"], st["maximized"]), (1366, 768, True))
        self.assertEqual(Session().window_start([(0, 0, 800, 600)])["width"], 1000)
        # minimiert/unbrauchbar → alte Grösse behalten
        s.set_window_geometry({"w": 160, "h": 28, "x": -32000, "y": -32000})
        st = Session().window_start([(0, 0, 3840, 2160)])
        self.assertEqual((st["width"], st["height"]), (3000, 2000))
        self.assertNotIn("x", st)
        with self.assertRaises(ValueError):
            s.set_window_geometry("1600x1000")

    def test_persist_and_missing(self):
        s = self.session()
        s.dj_add()
        s.dj_lock(os.path.join(self.lib, "b.mp3"), True)
        s.dj_set_opt("w_key", 0.9)
        from session import Session
        s2 = Session()                    # Tagger leer: Titel bleiben im Set, aber „nicht geladen“
        st = s2.dj_state()
        self.assertEqual(len(st["items"]), 5)
        self.assertTrue(all(r["missing"] for r in st["items"]))
        self.assertTrue(st["items"][1]["lock"])
        self.assertEqual(st["opts"]["w_key"], 0.9)
        with self.assertRaises(ValueError):
            s2.dj_optimize()
        s2.start_tag_load(self.lib, False)
        while not s2.task_status()["done"]:
            time.sleep(0.02)
        self.assertFalse(any(r["missing"] for r in s2.dj_state()["items"]))
        self.assertEqual(len(s2.dj_clear(missing_only=True)["items"]), 5)
        self.assertEqual(s2.dj_clear()["items"], [])


class TestFromFile(unittest.TestCase):
    def test_track_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.mp3")
            write_mp3(p, [text("TIT2", "Song"), text("TPE1", "DJ"), text("TKEY", "Am"),
                          text("TBPM", "124,5"), txxx("ENERGY", "0.7")])
            f = MP3File(p)
            f.load()
            t = setplan.track_from_file(f, tid=1)
            self.assertEqual((t.key, t.bpm, t.energy, t.title), ("8A", 124.5, 70, "DJ – Song"))
            self.assertGreater(t.duration, 0)


if __name__ == "__main__":
    unittest.main()
