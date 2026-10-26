"""Ideen (#186): Wunschlisten als Playlists, Übernahme aus Entdecken, Status bis Kauf/Bibliothek, Beatport-Name, Export."""
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

import discover
import ideas
import playlists


def read(path, enc="utf-8"):
    with open(path, encoding=enc) as fh:
        return fh.read()


def disc_item(key, artist, title, mix="", status="new", src=None, **kw):
    src = src or key.split(":")[0]
    return {"key": key, "src": src, "id": key.split(":")[1], "artist": artist, "title": title, "mix": mix, "status": status,
            "url": f"https://www.{src}.com/track/{key.split(':')[1]}", "preview": "https://p/x.mp3", "cover": "https://c/x.jpg",
            "label": "Nordwerk", "date": "2026-10-01", **kw}


class TestLogic(unittest.TestCase):
    def test_entry_and_clean(self):
        e = ideas.from_discover(disc_item("beatport:42", "Mara Lind", "Golden Hour", "Extended Mix"))
        self.assertEqual(e["ref"]["artist"], "Mara Lind")
        self.assertEqual((e["idea"]["store"], e["idea"]["sid"], e["idea"]["disc"]), ("beatport", "42", "beatport:42"))
        self.assertEqual(e["idea"]["status"], "idea")
        bad = playlists.clean_item({"ref": {"title": "x"}, "idea": {"status": "boom", "preview": "http://unsicher", "cover": "https://ok"}})
        self.assertEqual(bad["idea"]["status"], "idea")                         # unbekannter Status → Idee
        self.assertNotIn("preview", bad["idea"])                                # nur https-Verweise
        self.assertEqual(bad["idea"]["cover"], "https://ok")

    def test_sonovault_only_names(self):
        e = ideas.from_discover(disc_item("sonovault:9", "Mara Lind", "Nordlicht", src="sonovault", bpm=124))
        self.assertEqual(e["ref"], {"artist": "Mara Lind", "title": "Nordlicht", "source": "manual"})
        self.assertEqual(e["idea"], {"status": "idea", "src": "manual"})          # I6: keine SonoVault-Felder

    def test_merge_no_dupes(self):
        a = ideas.entry("Mara Lind", "Golden Hour", "Extended Mix")
        b = ideas.entry("mara lind", "golden hour", "extended mix")              # gleich → doppelt
        c = ideas.entry("Mara Lind", "Golden Hour", "Radio Edit")                # anderer Mix → neu
        items, added, dupes = ideas.merge([a], [b, c, None])
        self.assertEqual((len(items), added, dupes), (2, 1, 1))

    def test_text(self):
        got, unknown = ideas.from_text("01. Mara Lind - Golden Hour (Extended Mix)\nID - ID\nnur Text\n")
        self.assertEqual(unknown, 1)
        self.assertEqual([(x["ref"]["artist"], x["ref"]["title"], x["ref"].get("mix")) for x in got],
                         [("Mara Lind", "Golden Hour", "Extended Mix")])

    def test_status_and_purchased(self):
        items = [ideas.from_discover(disc_item("beatport:1", "A", "Eins")), ideas.entry("B", "Zwei", "Extended Mix"),
                 ideas.entry("C", "Drei"), dict(ideas.entry("D", "Vier"), path="/gibt/es/nicht.mp3")]
        items[2]["idea"]["status"] = "buy"
        bought = [{"store": "beatport", "id": 1, "artist": "x", "title": "y", "bought": "2026-10-20 10:00"},
                  {"store": "other", "artist": "B", "title": "Zwei", "mix": "Extended Mix", "bought": ""}]
        b = ideas.purchased(items, bought)
        self.assertEqual(b, {0: "2026-10-20", 1: "ja"})
        self.assertEqual([ideas.status(x, b.get(k, ""), exists=lambda p: p == "/gibt/es/nicht.mp3") for k, x in enumerate(items)],
                         ["bought", "bought", "buy", "lib"])

    def test_bp(self):
        self.assertEqual(ideas.bp_name("Warm-up Herbst 26"), "TagStudio_WISH_Warm-up_Herbst_26")
        items = [ideas.from_discover(disc_item("beatport:1", "A", "Eins")), ideas.from_discover(disc_item("deezer:2", "B", "Zwei")),
                 ideas.from_discover(disc_item("beatport:3", "C", "Drei"))]
        items[2]["idea"]["status"] = "dropped"
        self.assertEqual(ideas.bp_ids(items), (["1"], 1))

    def test_wish_not_mirrored(self):
        d = tempfile.mkdtemp()
        try:
            st = playlists.Store(os.path.join(d, "data"), os.path.join(d, "m"))
            st.create("Wunsch", "Ideen", "wish", [ideas.entry("A", "B")])
            st.create("Set", "", "manual", [])
            self.assertEqual(sorted(st.desired().values()), ["Set.m3u8"])
            self.assertFalse(os.path.exists(os.path.join(d, "m", "Ideen")))
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
        d = discover.load()
        for e in (disc_item("beatport:1", "Mara Lind", "Golden Hour", status="saved"), disc_item("deezer:2", "Nordwerk", "Morgen"),
                  disc_item("sonovault:3", "Sv", "Geheim", status="saved", src="sonovault", first=time.strftime("%Y-%m-%dT%H:%M:%S")), disc_item("deezer:4", "X", "Weg", status="hidden")):
            d["items"][e["key"]] = e
        discover.save(d)
        self.raw = read(discover.state_path())
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

    def test_migration_once_and_discover_unchanged(self):
        ov = self.s.ideas_overview()
        self.assertEqual([x["name"] for x in ov["lists"]], [ideas.MIGRATED_LIST])
        self.assertEqual(sorted(x["title"] for x in ov["items"]), ["Geheim", "Golden Hour"])
        self.assertEqual(read(discover.state_path()), self.raw)   # entdecken.json unverändert
        self.assertFalse(self.s._pls().undo_stack)                                       # kein Rückgängig-Schritt
        self.s.ideas_overview()
        self.assertEqual(len(self.s.ideas_overview()["lists"]), 1)                       # nur einmal
        pl = self.s._pls().get(ov["sel"])
        self.assertEqual(pl["folder"], "Ideen")
        self.assertEqual(pl["kind"], "wish")

    def test_from_disc_marks_and_clear_keeps(self):
        self.s.ideas_overview()
        r = self.s.ideas_from_disc(["deezer:2", "beatport:1"], name="Herbst")
        self.assertEqual((r["added"], r["dupes"], r["name"]), (2, 0, "Herbst"))
        r2 = self.s.ideas_from_disc(["deezer:2"], pid=r["pid"])
        self.assertEqual((r2["added"], r2["dupes"]), (0, 1))
        ov = self.s.disc_overview()
        flags = {e["key"]: (e["status"], e.get("idea", False)) for e in ov["items"]}
        self.assertEqual(flags["deezer:2"], ("saved", True))                              # in Entdecken gemerkt + „in Ideen“
        d = discover.load()
        d["items"]["deezer:2"]["status"] = "new"                                         # auch ungemerkt bleibt er …
        discover.save(d)
        self.s.disc_clear()
        self.assertIn("deezer:2", discover.load()["items"])                              # … beim Leeren erhalten
        self.assertNotIn("deezer:4", discover.load()["items"])
        self.assertEqual(self.s.cfg.get("ideas_last"), r["pid"])

    def test_set_note_move_remove_undo(self):
        pid = self.s.ideas_list_create("A")["sel"]
        self.s.ideas_add_text(pid, "Mara Lind - Eins\nMara Lind - Zwei\nMara Lind - Drei")
        ov = self.s.ideas_set(pid, [0, 2], status="buy")
        self.assertEqual([x["status"] for x in ov["items"]], ["buy", "idea", "buy"])
        self.assertEqual(next(x for x in ov["lists"] if x["id"] == pid)["counts"]["buy"], 2)
        ov = self.s.ideas_set(pid, [1], note="  fürs Warm-up ")
        self.assertEqual(ov["items"][1]["note"], "fürs Warm-up")
        b = self.s.ideas_list_create("B")["sel"]
        r = self.s.ideas_move(pid, [0], b)
        self.assertEqual(r["moved"], 1)
        self.assertEqual([x["title"] for x in self.s.ideas_overview(pid)["items"]], ["Zwei", "Drei"])
        self.assertEqual([x["title"] for x in self.s.ideas_overview(b)["items"]], ["Eins"])
        self.s.ideas_move(pid, [0], b, True)                                             # kopieren
        self.assertEqual(len(self.s.ideas_overview(pid)["items"]), 2)
        self.s.ideas_remove(pid, [0])
        self.assertEqual([x["title"] for x in self.s.ideas_overview(pid)["items"]], ["Drei"])
        r = self.s.ideas_undo(pid)
        self.assertIn("Ideen entfernen", r["message"])
        self.assertEqual(len(r["items"]), 2)
        with self.assertRaises(ValueError):
            self.s.ideas_set(pid, [0], status="gekauft")

    def test_manual_playlist_archive_export(self):
        pid = self.s.ideas_list_create("Liste")["sel"]
        with self.assertRaises(ValueError):
            self.s.ideas_add_manual(pid, {"artist": " "})
        self.s.ideas_add_manual(pid, {"artist": "A", "title": "B", "url": "https://x/1", "note": "n"})
        self.s.ideas_add_manual(pid, {"artist": "C", "title": "D"})
        self.s.ideas_set(pid, [1], status="dropped")
        r = self.s.ideas_to_playlist(pid)
        self.assertEqual(r["count"], 1)
        pl = self.s._pls().get(r["pid"])
        self.assertEqual((pl["kind"], pl["items"][0]["ref"]["url"], "idea" in pl["items"][0]), ("manual", "https://x/1", False))
        dest = os.path.join(self.home, "w.csv")
        out = self.s.ideas_export_write("csv", dest, pid)
        self.assertEqual(out["count"], 2)
        text = read(dest, "utf-8-sig")
        self.assertIn("Verworfen", text)
        self.assertIn("Notiz", text)
        other = self.s.ideas_list_create("Andere")["sel"]
        ov = self.s.ideas_list_archive(pid, move_to=other)
        self.assertNotIn(pid, [x["id"] for x in ov["lists"]])
        self.assertEqual(len(self.s.ideas_overview(other)["items"]), 2)
        self.assertTrue(self.s._pls().get(pid)["archived"])                              # archiviert, nicht gelöscht

    def test_beatport_push(self):
        self.s.ideas_overview()
        pid = self.s.ideas_from_disc(["beatport:1", "deezer:2"], name="Kauf")["pid"]
        calls = []

        def fake(plugin, fn, *args, **kw):
            calls.append((fn, args))
            if fn == "store_settings":
                return {"playlists_write": True, "buy_prefix": "TagStudio_BUY_"}
            if fn == "store_playlist_put":
                return {"id": 77, "name": args[0], "added": len(args[1]), "created": True}
            raise AssertionError(fn)
        with mock.patch.object(self.s.plugins, "call_playlist", side_effect=fake):
            pv = self.s.ideas_bp_preview(pid)
            self.assertEqual((pv["name"], pv["count"], pv["without"]), ("TagStudio_WISH_Kauf", 1, 1))
            st = self.s.start_ideas_bp(pid)
            self.assertNotIn("error", st)
            for _ in range(100):
                if self.s.task.get("done"):
                    break
                time.sleep(0.05)
        self.assertEqual(self.s.task["result"]["added"], 1)
        self.assertIn(("store_playlist_put", ("TagStudio_WISH_Kauf", ["1"], False)), calls)
        self.assertEqual(self.s._pls().get(pid)["pushed"]["beatport"]["id"], 77)

    def test_bought_from_purchases(self):
        self.s.ideas_overview()
        pid = self.s.ideas_from_disc(["beatport:1"], name="K")["pid"]
        self.s._purch().merge("beatport", "Beatport", [{"id": 1, "artist": "Mara Lind", "title": "Golden Hour", "bought": "2026-10-25 12:00:00"}])
        ov = self.s.ideas_overview(pid)
        self.assertEqual((ov["items"][0]["status"], ov["items"][0]["bought"]), ("bought", "2026-10-25"))


if __name__ == "__main__":
    unittest.main()
