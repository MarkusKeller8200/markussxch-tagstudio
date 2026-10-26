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
