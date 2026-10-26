"""#370: Download-Statistik – Zusammenfassung je Version, Tagesstände, neue Downloads je Tag (ohne Netz)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import downloadstats as ds  # noqa: E402


def rel(tag, win, mac, plug=0, beta=False, draft=False):
    return {"tag_name": tag, "published_at": "2026-10-26T01:00:00Z", "prerelease": beta, "draft": draft,
            "html_url": f"https://github.com/x/releases/tag/{tag}",
            "assets": [{"name": f"TagStudio-{tag[1:]}-Windows-Setup.exe", "download_count": win},
                       {"name": f"TagStudio-{tag[1:]}-macOS-Apple-Chip.dmg", "download_count": mac},
                       {"name": "plugin-beatport-2.11.zip", "download_count": plug},
                       {"name": "plugins.json", "download_count": 99}]}


class TestDownloadStats(unittest.TestCase):
    def test_kind(self):
        self.assertEqual([ds.kind(n) for n in ("A-Setup.exe", "A.dmg", "plugin-x-1.0.zip", "plugins.json", "x.zip")],
                         ["win", "mac", "plugin", "other", "other"])

    def test_fetch_and_summarize(self):
        pages = {1: [rel("v4.12.0", 3, 1, 5), rel("v4.12.0-beta.1", 2, 0, beta=True), rel("v9", 7, 7, draft=True)]}
        seen = []

        def get(url):
            seen.append(url)
            return pages.get(int(url.rsplit("=", 1)[1]), [])
        r = ds.fetch(get=get)
        self.assertEqual([x["tag"] for x in r], ["v4.12.0", "v4.12.0-beta.1"])                 # Entwürfe nie
        self.assertEqual(len(seen), 1)                                                          # < 100 → keine 2. Seite
        s = ds.summarize(r)
        self.assertEqual(s["total"], {"win": 5, "mac": 1, "plugins": 5, "installers": 6})
        self.assertEqual((s["rows"][0]["total"], s["rows"][1]["beta"]), (4, True))
        self.assertEqual([f["name"] for f in s["rows"][0]["files"]], ["TagStudio-4.12.0-Windows-Setup.exe", "TagStudio-4.12.0-macOS-Apple-Chip.dmg"])

    def test_update_and_history(self):
        r1 = ds.fetch(get=lambda u: [rel("v4.12.0", 3, 1)] if u.endswith("=1") else [])
        d = ds.update(None, r1, "2026-10-26")
        d = ds.update(d, ds.fetch(get=lambda u: [rel("v4.12.0", 8, 2), rel("v4.13.0", 1, 0)] if u.endswith("=1") else []), "2026-10-27")
        d = ds.update(d, ds.fetch(get=lambda u: [rel("v4.12.0", 9, 2), rel("v4.13.0", 1, 0)] if u.endswith("=1") else []), "2026-10-27")  # gleicher Tag: ersetzt
        self.assertEqual(sorted(d["days"]), ["2026-10-26", "2026-10-27"])
        h = ds.history(d, "2026-10-28")
        self.assertEqual(h["days"], [{"day": "2026-10-27", "win": 7, "mac": 1, "total": 8}])
        self.assertEqual((h["last7"], h["last30"], h["since"]), (8, 8, "2026-10-26"))
        self.assertEqual(ds.history(d, "2026-12-31")["last7"], 0)
        self.assertEqual(ds.history(None), {"days": [], "last7": 0, "last30": 0, "since": ""})

    def test_main_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "docs", "download-stats.json")
            with mock.patch.object(ds, "fetch", return_value=ds.fetch(get=lambda u: [rel("v4.12.0", 1, 1)] if u.endswith("=1") else [])):
                self.assertEqual(ds.main(["x", "--update", path]), 0)
            data = json.load(open(path, encoding="utf-8"))
            self.assertEqual(list(data["days"].values())[0], {"v4.12.0": [1, 1, 0]})
            self.assertEqual(ds.main(["x"]), 2)

    def test_report_offline_history(self):
        with mock.patch.object(ds, "fetch", return_value=[]), mock.patch.object(ds, "load_stats", return_value=None):
            r = ds.report()
        self.assertEqual((r["rows"], r["history"]["days"]), ([], []))
        self.assertIsNone(ds.load_stats(get=lambda u: (_ for _ in ()).throw(OSError("offline"))))


if __name__ == "__main__":
    unittest.main()


class TestSiteAndNotes(unittest.TestCase):
    """#371 summary.json/badge.json, #372 Download-Kasten oben in den Versionshinweisen."""

    def rels(self):
        r = rel("v4.12.0", 3, 1, 5)
        r["id"] = 7
        r["body"] = "**Download:** Windows → `TagStudio-…-Windows-Setup.exe` · macOS\n\nDie Installer sind nicht signiert.\n\n### Neu\n- x"
        for a, (url, size) in zip(r["assets"], [("https://x/w.exe", 50 * 1048576), ("https://x/m.dmg", 60 * 1048576),
                                                 ("https://x/p.zip", 2048), ("https://x/plugins.json", 10)]):
            a["browser_download_url"], a["size"] = url, size
        return ds.fetch(get=lambda u: [r, rel("v0.1.0-alt", 0, 0)] if u.endswith("=1") else [])

    def test_site_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.rels()
            ds.write_site(tmp, r, ds.update(None, r, "2026-10-26"))
            s = json.load(open(os.path.join(tmp, "summary.json"), encoding="utf-8"))
            b = json.load(open(os.path.join(tmp, "badge.json"), encoding="utf-8"))
        self.assertEqual(s["total"]["installers"], 4)
        self.assertIn("updated", s)
        self.assertEqual((b["schemaVersion"], b["label"], b["message"]), (1, "Downloads", "4"))

    def test_block(self):
        r = self.rels()
        blk = ds.download_block(r[0])
        self.assertTrue(blk.startswith(ds.BLOCK_START) and blk.endswith(ds.BLOCK_END))
        self.assertLess(blk.index("Windows"), blk.index("macOS"))                       # Windows zuerst
        self.assertIn("[TagStudio-4.12.0-Windows-Setup.exe](https://x/w.exe) · 50 MB", blk)
        self.assertIn("<details><summary>Plugins (1)", blk)
        self.assertNotIn("plugins.json", blk)
        self.assertEqual(ds.download_block(r[1]), "")                                   # ohne Download-Adressen kein Kasten
        body = ds.apply_block(r[0]["body"], blk)
        self.assertTrue(body.startswith(ds.BLOCK_START))
        self.assertNotIn("**Download:** Windows →", body)                                 # alte Zeile weg
        self.assertIn("### Neu", body)
        self.assertEqual(ds.apply_block(body, blk), body)                                 # zweimal = gleich
        self.assertEqual(ds.strip_block(body).split("\n")[0], "Die Installer sind nicht signiert.")
        calls = []
        n = ds.update_release_notes(r, "T", patch=lambda rid, b: calls.append((rid, b)), log=lambda *_: None)
        self.assertEqual((n, calls[0][0]), (1, 7))                                        # nur Releases mit Installer-Link
        r[0]["body"] = calls[0][1]
        self.assertEqual(ds.update_release_notes(r, "T", patch=lambda *a: calls.append(a), log=lambda *_: None), 0)

    def test_updater_strips_block(self):
        import updater
        self.assertEqual(updater._strip_dl(ds.BLOCK_START + "\nx\n" + ds.BLOCK_END + "\n\n### Neu"), "### Neu")
