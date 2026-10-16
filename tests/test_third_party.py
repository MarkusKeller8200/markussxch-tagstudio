"""#176: Liste der Fremdkomponenten (docs/third-party.json), Hilfe › Lizenzen und die monatliche Prüfung."""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "third-party.json")


def checker():
    spec = importlib.util.spec_from_file_location("third_party_check", os.path.join(ROOT, ".github", "scripts", "third_party_check.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestThirdParty(unittest.TestCase):
    def setUp(self):
        with open(DATA, encoding="utf-8") as fh:
            self.data = json.load(fh)

    def test_list_complete(self):
        ids, groups = set(), set(self.data["groups"])
        for it in self.data["items"]:
            for k in ("id", "group", "name", "use", "license", "url"):
                self.assertTrue(it.get(k), f"{it.get('id')}: {k} fehlt")
            self.assertNotIn(it["id"], ids)
            ids.add(it["id"])
            self.assertIn(it["group"], groups)
            self.assertTrue(it["url"].startswith("https://"), it["id"])
            if "check" in it:
                c = it["check"]
                self.assertIn(c["type"], ("pypi", "github"))
                self.assertTrue(c.get("package") if c["type"] == "pypi" else c.get("repo"), it["id"])
        # was im Installer steckt bzw. von Plugins installiert wird, muss in der Liste stehen
        for need in ("pywebview", "pillow", "uv", "pyinstaller", "python", "audio-separator", "librosa", "audioread",
                     "imageio-ffmpeg", "ffmpeg", "serato-tags", "beets-beatport4", "harmonic-flow"):
            self.assertIn(need, ids)
        with open(os.path.join(ROOT, "plugins", "stems", "plugin.json"), encoding="utf-8") as fh:
            stems = json.load(fh)
        pkgs = {p.split("[")[0].split("<")[0].split(">")[0] for v in stems.get("install", []) for p in v.get("packages", [])}
        known = {it["check"]["package"] for it in self.data["items"] if it.get("check", {}).get("type") == "pypi"}
        self.assertEqual(pkgs - known, set(), "Pakete des Stems-Plugins fehlen in docs/third-party.json")

    def test_dump_roundtrip(self):
        m = checker()
        self.assertEqual(json.loads(m.dump(self.data)), self.data)
        with open(DATA, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), m.dump(self.data), "Format mit third_party_check.dump() schreiben")

    def test_compare_report_apply(self):
        m = checker()
        items = [{"id": "a", "name": "A", "license": "MIT", "url": "https://x", "check": {"type": "pypi", "package": "a"},
                  "checked": {"version": "1.0", "license": "MIT", "date": "2026-01-01"}},
                 {"id": "b", "name": "B", "license": "MIT", "url": "https://y", "check": {"type": "pypi", "package": "b"},
                  "checked": {"version": "2.0", "license": "MIT", "date": "2026-01-01"}},
                 {"id": "c", "name": "C", "license": "BSD", "url": "https://z", "check": {"type": "github", "repo": "o/c"}},
                 {"id": "d", "name": "D", "license": "x", "url": "https://w"}]
        cur = {"a": {"version": "1.0", "license": "MIT"}, "b": {"version": "2.1", "license": "Apache-2.0"},
               "o/c": {"error": "HTTPError"}}
        ch = m.compare(items, fetch=lambda c: cur[c.get("package") or c.get("repo")])
        self.assertEqual([c["id"] for c in ch], ["b", "c"])
        self.assertIn("Version 2.0 → 2.1", ch[0]["what"])
        self.assertTrue(any("Lizenzangabe" in w for w in ch[0]["what"]))
        text = m.report(ch, "2026-11-01")
        self.assertIn(m.MARK, text)
        upd = json.loads(text.split("```json")[1].split("```")[0])
        self.assertEqual(upd, {"b": {"version": "2.1", "license": "Apache-2.0", "date": "2026-11-01"}})
        self.assertIn("Keine Änderungen", m.report([], "2026-11-01"))
        with tempfile.TemporaryDirectory() as d:
            data_p, new_p = os.path.join(d, "tp.json"), os.path.join(d, "neu.json")
            with open(data_p, "w", encoding="utf-8") as fh:
                fh.write(m.dump({"format": 1, "groups": {}, "items": items}))
            with open(new_p, "w", encoding="utf-8") as fh:
                json.dump(upd, fh)
            self.assertEqual(m.apply(new_p, data_p), 1)
            with open(data_p, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["items"][1]["checked"]["version"], "2.1")

    def test_repo_info_report_apply(self):
        """#206: GitHub-Repositories mit Vertrauenssignalen."""
        m = checker()
        for it in self.data["items"]:
            if it.get("repo"):
                self.assertRegex(it["repo"], r"^[\w.-]+/[\w.-]+$", it["id"])
        import urllib.parse
        gh = {it["id"] for it in self.data["items"] if urllib.parse.urlparse(it["url"]).hostname == "github.com"}  # CodeQL #208
        self.assertEqual({i for i in gh if not any(x["id"] == i and x.get("repo") for x in self.data["items"])}, set(),
                         "GitHub-Komponenten ohne „repo“")
        items = [{"id": "a", "name": "A", "repo": "o/a"}, {"id": "b", "name": "B", "repo": "o/b"},
                 {"id": "c", "name": "C", "repo": "o/c"}, {"id": "d", "name": "D"}]
        info = {"o/a": {"stars": 5, "archived": False, "pushed": "2026-10-01", "full_name": "o/a"},
                "o/b": {"stars": 1, "archived": True, "pushed": "2020-01-01", "full_name": "o/b"}}

        def fetch(repo, today):
            if repo not in info:
                raise OSError("404")
            return info[repo]
        infos = m.collect_repo_info(items, fetch, "2026-11-01")
        self.assertEqual(sorted(infos), ["a", "b", "c"])
        w = m.repo_warnings(items, infos, "2026-11-01")
        self.assertEqual([(it["id"], x.split(" ")[0]) for it, x in w], [("b", "archiviert"), ("b", "seit"), ("c", "Repository")])
        text = m.report([], "2026-11-01", infos, w)
        self.assertIn("Keine Änderungen", text)
        self.assertIn("archiviert", text)
        upd = json.loads(text.split("```json")[1].split("```")[0])
        self.assertEqual(sorted(upd["_repo_info"]), ["a", "b"])
        with tempfile.TemporaryDirectory() as d:
            data_p, new_p = os.path.join(d, "tp.json"), os.path.join(d, "neu.json")
            with open(data_p, "w", encoding="utf-8") as fh:
                fh.write(m.dump({"format": 1, "groups": {}, "items": items}))
            with open(new_p, "w", encoding="utf-8") as fh:
                json.dump(upd, fh)
            self.assertEqual(m.apply(new_p, data_p), 2)
            with open(data_p, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["items"][0]["repo_info"]["stars"], 5)

    def test_help_licenses(self):
        from session_help import HelpMixin
        d = HelpMixin().help_licenses()                  # liest nur die mitgelieferte Liste, keine Einstellungen
        self.assertTrue(d["found"])
        self.assertEqual(d["items"][0]["id"], "tagstudio")
        self.assertIn("bundled", d["groups"])


if __name__ == "__main__":
    unittest.main()
