"""Warenkorb (#420–#423): Körbe, Liste einfügen, aus Ideen, Prüfung auf Käufe, Historik, Beatport zuordnen und senden."""
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

import carts
import ideas


def read(path, enc="utf-8"):
    with open(path, encoding=enc) as fh:
        return fh.read()


class TestLogic(unittest.TestCase):
    def test_text_and_clean(self):
        got, unknown = carts.from_text("01. [00:00] Mara Lind - Golden Hour (Extended Mix) [Nordwerk]\nID - ID\nnur Text\n"
                                       "w/ Kai Ost - Morgen")
        self.assertEqual(unknown, 1)
        self.assertEqual([(x["artist"], x["title"], x.get("mix", ""), x["src"]) for x in got],
                         [("Mara Lind", "Golden Hour", "Extended Mix", "text"), ("Kai Ost", "Morgen", "", "text")])
        bad = carts.clean_item({"artist": "A", "title": "B", "url": "http://unsicher", "sid": "abc", "src": "boom",
                                "match": {"state": "egal"}, "removed": {"why": "x"}})
        self.assertEqual(bad["src"], "manual")
        for k in ("url", "sid", "match", "removed"):
            self.assertNotIn(k, bad)
        self.assertIsNone(carts.clean_item({"note": "nur Notiz"}))

    def test_from_idea_and_dupes(self):
        e = ideas.entry("Mara Lind", "Golden Hour", "Extended Mix", url="https://www.beatport.com/track/golden-hour/42",
                        src="beatport", store="beatport", sid="42")
        x = carts.from_idea(e)
        self.assertEqual((x["sid"], x["src"], x["match"]["state"]), ("42", "ideas", "sure"))
        y = carts.from_idea(ideas.entry("B", "Zwei", url="https://www.beatport.com/track/zwei/7"))
        self.assertEqual(y["sid"], "7")                                                  # ID aus dem Beatport-Link
        a = carts.item("mara lind", "golden hour", "extended mix")
        items, added, dupes = carts.merge([x], [a, carts.item("Mara Lind", "Golden Hour", "Radio Edit"), None])
        self.assertEqual((len(items), added, dupes), (2, 1, 1))

    def test_status_purchased_shopping(self):
        items = [carts.item("A", "Eins", sid="1"), carts.item("B", "Zwei", "Extended Mix"), carts.item("C", "Drei"),
                 dict(carts.item("D", "Vier"), lib="/da.mp3"), dict(carts.item("E", "Fünf", sid="5"), removed={"why": "hand"})]
        bought = [{"store": "beatport", "id": 1, "artist": "x", "title": "y", "bought": "2026-10-20 10:00"},
                  {"store": "other", "artist": "B", "title": "Zwei", "mix": "Extended Mix"}]
        b = carts.purchased(items, bought)
        self.assertEqual(b, {0: "2026-10-20", 1: "ja"})
        ex = lambda p: p == "/da.mp3"                                                    # noqa: E731
        self.assertEqual([carts.status(x, b.get(k, ""), ex) for k, x in enumerate(items)],
                         ["bought", "bought", "open", "lib", "removed"])
        self.assertEqual(carts.shopping(items, b, ex), [2])
        items[2]["sid"] = "3"
        self.assertEqual(carts.bp_ids(items, b, ex), (["3"], 0))
        self.assertEqual(carts.bp_name("Club / Herbst 26"), "TagStudio_CART_Club_Herbst_26")

    def test_auto_close(self):
        c = {"status": "open", "items": [carts.item("A", "Eins"), dict(carts.item("B", "Zwei"), removed={"why": "hand"})]}
        self.assertFalse(carts.auto_close(c, {}))
        self.assertTrue(carts.auto_close(c, {0: "2026-10-20"}, now=100))
        self.assertEqual((c["status"], c["closed"], c["closed_by"]), ("bought", 100, "auto"))
        c2 = {"status": "open", "auto": False, "items": [carts.item("A", "Eins")]}
        self.assertFalse(carts.auto_close(c2, {0: "ja"}))                                # nach „Wieder öffnen“
        self.assertFalse(carts.auto_close({"status": "open", "items": []}, {}))           # leerer Korb bleibt offen

    def test_apply_match_and_pick(self):
        x = carts.item("A", "Eins")
        y = carts.apply_match(x, {"id": "9", "score": 0.91, "sure": True, "url": "https://www.beatport.com/track/eins/9"})
        self.assertEqual((y["sid"], y["match"]["state"], y["url"]), ("9", "sure", "https://www.beatport.com/track/eins/9"))
        u = carts.apply_match(x, {"id": "9", "score": 0.7, "sure": False,
                                  "cands": [{"id": "9", "artist": "A", "title": "Eins", "score": 0.7}, {"id": "", "score": 1}]})
        self.assertEqual((u.get("sid"), u["match"]["state"], len(u["match"]["cands"])), (None, "unsure", 1))
        self.assertEqual(carts.apply_match(x, None)["match"]["state"], "none")
        p = carts.pick(u, u["match"]["cands"][0])
        self.assertEqual((p["sid"], p["match"]["state"]), ("9", "sure"))
        self.assertEqual(carts.pick(u, None)["match"]["state"], "none")

    def test_store_undo_and_reload(self):
        d = tempfile.mkdtemp()
        try:
            st = carts.Store(d)
            c = st.create("Club")
            self.assertEqual(st.create("club")["name"], "club (2)")
            st.change("x", lambda cs: cs[c["id"]].update(name="Neu") or True)
            self.assertEqual(st.undo(), "x")
            self.assertEqual(st.get(c["id"])["name"], "Club")
            raw = json.loads(read(os.path.join(d, "warenkorb.json")))
            raw["carts"]["böse"] = {"name": "x"}                                          # ungültige ID fällt weg
            with open(os.path.join(d, "warenkorb.json"), "w", encoding="utf-8") as fh:
                json.dump(raw, fh)
            os.utime(os.path.join(d, "warenkorb.json"), (time.time() + 5, time.time() + 5))
            self.assertEqual(len(st.carts()), 2)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestSession(unittest.TestCase):
    def setUp(self):
        import core
        self.home = tempfile.mkdtemp()
        self._env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        os.environ["HOME"] = os.environ["USERPROFILE"] = self.home
        self._cfg = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = os.path.join(self.home, ".tagstudio.json")
        core.CONFIG_OLD = os.path.join(self.home, ".mp3tagcompare.json")
        from session import Session
        self.s = Session()

    def tearDown(self):
        import core
        core.CONFIG, core.CONFIG_OLD = self._cfg
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.home, ignore_errors=True)

    def wait(self):
        for _ in range(200):
            if self.s.task.get("done"):
                return self.s.task
            time.sleep(0.05)
        self.fail("Vorgang endet nicht")

    def test_text_remove_restore_undo(self):
        r = self.s.carts_add_text("", "Mara Lind - Eins\nID - ID\nMara Lind - Zwei\nMara Lind - Eins", name="Club")
        self.assertEqual((r["added"], r["dupes"], r["unknown"], r["name"]), (2, 1, 1, "Club"))
        cid = r["cid"]
        ov = self.s.carts_overview()
        self.assertEqual((ov["sel"], ov["open"]), (cid, 2))
        self.assertEqual(self.s.carts_count(), 2)
        ov = self.s.carts_remove(cid, [0])
        self.assertEqual([(x["status"], x["removed"]) for x in ov["items"]], [("removed", "hand"), ("open", "")])
        self.assertEqual(ov["open"], 1)
        ov = self.s.carts_restore(cid, [0])
        self.assertEqual(ov["open"], 2)
        ov = self.s.carts_note(cid, 1, "  fürs Warm-up ")
        self.assertEqual(ov["items"][1]["note"], "fürs Warm-up")
        r = self.s.carts_undo(cid)
        self.assertIn("Notiz", r["message"])
        self.assertEqual(r["items"][1]["note"], "")
        self.s.carts_add_manual(cid, {"artist": "Kai Ost", "title": "Morgen", "url": "https://www.beatport.com/track/morgen/88"})
        it = self.s.carts_overview(cid)["items"][2]
        self.assertEqual((it["sid"], it["match"]), ("88", "sure"))
        with self.assertRaises(ValueError):
            self.s.carts_add_text(cid, "nur Text")

    def test_bought_auto_close_history_reopen(self):
        cid = self.s.carts_add_text("", "Mara Lind - Eins\nKai Ost - Zwei", name="K")["cid"]
        self.s._purch().merge("beatport", "Beatport", [{"id": 1, "artist": "Mara Lind", "title": "Eins", "bought": "2026-10-25 12:00:00"}])
        ov = self.s.carts_overview(cid)
        self.assertEqual([x["status"] for x in ov["items"]], ["bought", "open"])
        self.assertEqual(ov["items"][0]["bought"], "2026-10-25")
        self.assertEqual(ov["carts"][0]["status"], "open")
        ov = self.s.carts_remove_bought(cid)                                             # #422
        self.assertEqual((ov["removed_n"], ov["items"][0]["removed"]), (1, "bought"))
        self.s._purch().merge("beatport", "Beatport", [{"id": 2, "artist": "Kai Ost", "title": "Zwei", "bought": "2026-10-26 12:00:00"}])
        c = self.s.carts_overview(cid)["carts"][0]
        self.assertEqual((c["status"], c["closed_by"]), ("bought", "auto"))              # W3 automatisch
        self.assertEqual(self.s.carts_count(), 0)
        with self.assertRaises(ValueError):
            self.s.carts_add_text(cid, "A - B")                                          # abgeschlossen
        c = self.s.carts_reopen(cid)["carts"][0]
        self.assertEqual(c["status"], "open")
        self.assertEqual(self.s.carts_overview(cid)["carts"][0]["status"], "open")       # schliesst nicht sofort wieder
        c = self.s.carts_close(cid)["carts"][0]
        self.assertEqual((c["status"], c["closed_by"]), ("bought", "hand"))
        ov = self.s.carts_archive(cid)
        self.assertEqual((ov["carts"][0]["archived"] > 0, ov["sel"]), (True, ""))
        ov = self.s.carts_archive(cid, False)
        self.assertEqual(ov["sel"], cid)

    def test_from_ideas_sets_buy(self):
        pid = self.s.ideas_list_create("W")["sel"]
        self.s.ideas_add_manual(pid, {"artist": "A", "title": "Eins", "url": "https://www.beatport.com/track/eins/5"})
        self.s.ideas_add_manual(pid, {"artist": "B", "title": "Zwei"})
        r = self.s.carts_from_ideas(pid, [0, 1], name="Aus Ideen")
        self.assertEqual((r["added"], r["name"]), (2, "Aus Ideen"))
        self.assertEqual([x["set"] for x in self.s.ideas_overview(pid)["items"]], ["buy", "buy"])
        items = self.s.carts_overview(r["cid"])["items"]
        self.assertEqual([(x["sid"], x["src"]) for x in items], [("5", "ideas"), ("", "ideas")])
        self.assertEqual(self.s.carts_from_ideas(pid, [0], cid=r["cid"])["dupes"], 1)

    def test_export(self):
        cid = self.s.carts_add_text("", "Mara Lind - Eins (Extended Mix)", name="Ex")["cid"]
        dest = os.path.join(self.home, "k.csv")
        out = self.s.carts_export_write("csv", dest, cid)
        self.assertEqual(out["count"], 1)
        text = read(dest, "utf-8-sig")
        self.assertIn("Extended Mix", text)
        self.assertIn("Beatport-ID", text)

    def test_beatport_match_and_send(self):
        cid = self.s.carts_add_text("", "Mara Lind - Eins\nKai Ost - Zwei\nLena Berg - Drei\nAlt - Gekauft", name="BP")["cid"]
        self.s._purch().merge("beatport", "Beatport", [{"id": 4, "artist": "Alt", "title": "Gekauft", "bought": "2026-10-01"}])
        calls = []

        def fake(plugin, fn, *args, **kw):
            calls.append((fn, args))
            if fn == "store_settings":
                return {"playlists_write": True, "buy_prefix": "TagStudio_BUY_"}
            if fn == "store_search":
                self.assertEqual([r["title"] for r in args[0]], ["Eins", "Zwei", "Drei"])   # gekaufte nicht gesucht
                return [{"id": "11", "score": 0.95, "sure": True, "url": "https://www.beatport.com/track/eins/11"},
                        {"id": "22", "score": 0.7, "sure": False, "cands": [{"id": "22", "artist": "Kai Ost", "title": "Zwei", "score": 0.7}]},
                        None]
            if fn == "store_playlist_put":
                return {"id": 99, "name": args[0], "url": "https://www.beatport.com/library/playlists/99", "added": len(args[1])}
            raise AssertionError(fn)
        with mock.patch.object(self.s.plugins, "call_playlist", side_effect=fake):
            self.s._carts().quiet(lambda cs: cs[cid]["items"][3].update(sid="4") or True)
            st = self.s.start_carts_bp_match(cid)
            self.assertNotIn("error", st)
            res = self.wait()["result"]
            self.assertEqual((res["sure"], res["unsure"], res["none"]), (1, 1, 1))
            items = self.s.carts_overview(cid)["items"]
            self.assertEqual([x["match"] for x in items[:3]], ["sure", "unsure", "none"])
            self.s.carts_pick(cid, 1, 0)                                                 # unsicher → gewählt
            pv = self.s.carts_bp_preview(cid)
            self.assertEqual((pv["name"], pv["count"], pv["without"], pv["bought"]), ("TagStudio_CART_BP", 2, 1, 1))
            st = self.s.start_carts_bp(cid)
            self.assertNotIn("error", st)
            res = self.wait()["result"]
        self.assertEqual(res["count"], 2)
        self.assertIn(("store_playlist_put", ("TagStudio_CART_BP", ["11", "22"], True)), calls)
        self.assertEqual(self.s.carts_overview(cid)["carts"][0]["pushed"]["id"], "99")

    def test_send_needs_setting(self):
        cid = self.s.carts_add_text("", "A - B", name="X")["cid"]
        with mock.patch.object(self.s.plugins, "call_playlist", return_value={"playlists_write": False}):
            r = self.s.start_carts_bp(cid)
        self.assertFalse(r["ok"])
        self.assertIn("ausgeschaltet", r["error"])


class TestBeatportSearch(unittest.TestCase):
    """#423: Plugin-Funktion store_search – ISRC zuerst, sonst Suche; sicher/unsicher/kein Treffer, nur lesend."""

    def test_store_search(self):
        from test_beatport_purchases import load_plugin, Ctx
        bp = load_plugin()
        tracks = {"gold": [{"id": 11, "name": "Golden Hour", "mix_name": "Extended Mix", "artists": [{"name": "Mara Lind"}],
                            "slug": "golden-hour", "release": {"label": {"name": "x"}}}],
                  "nord": [{"id": 21, "name": "Nord", "mix_name": "Original Mix", "artists": [{"name": "Kai"}],
                            "release": {"label": {"name": "x"}}},
                           {"id": 22, "name": "Nordwind", "mix_name": "Original Mix", "artists": [{"name": "Mara Lind"}],
                            "release": {"label": {"name": "x"}}}]}
        seen = []

        class FakeClient:
            def __init__(self, ctx):
                pass

            def search_tracks(self, q, n=8):
                seen.append(("q", q))
                return tracks["gold"] if "Golden" in q else tracks["nord"] if "Nord" in q else []

            def by_isrc(self, isrc):
                seen.append(("isrc", isrc))
                return []

        class C(Ctx):
            def progress(self, i, total, text="", frac=None):
                pass
        bp.Client = FakeClient
        res = bp.store_search(C(tempfile.mkdtemp()), [
            {"artist": "Mara Lind", "title": "Golden Hour", "mix": "Extended Mix", "isrc": "deaa1"},
            {"artist": "Kai Ost", "title": "Nordwind"},
            {"artist": "Niemand", "title": "Gibt es nicht"}])
        self.assertEqual((res[0]["id"], res[0]["sure"]), ("11", True))
        self.assertEqual(res[0]["url"], "https://www.beatport.com/track/golden-hour/11")
        self.assertFalse(res[1]["sure"])                                                 # nur ähnlich → unsicher
        self.assertTrue(res[1]["cands"])
        self.assertIsNone(res[2])
        self.assertEqual(seen[0], ("isrc", "DEAA1"))                                     # ISRC zuerst


if __name__ == "__main__":
    unittest.main()
