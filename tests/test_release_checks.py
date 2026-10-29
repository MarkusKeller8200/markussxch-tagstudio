"""#406/#407: Prüfsummen-Datei und VirusTotal-Prüfung im Release-Workflow (ohne Netz, mit nachgebauter API)."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".github", "scripts"))

import release_checks as rc  # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeVT:
    def __init__(self, stats, pending=1):
        self.stats, self.pending, self.calls = stats, pending, []

    def __call__(self, req, timeout=0):
        self.calls.append((req.get_method(), req.full_url, dict(req.header_items())))
        u = req.full_url
        if u.endswith("/files/upload_url"):
            return _Resp(json.dumps({"data": "https://upload.example/big"}).encode())
        if req.get_method() == "POST":
            return _Resp(json.dumps({"data": {"id": "AID"}}).encode())
        if "/analyses/AID" in u:
            if self.pending:
                self.pending -= 1
                return _Resp(json.dumps({"data": {"attributes": {"status": "queued"}}}).encode())
            return _Resp(json.dumps({"data": {"attributes": {"status": "completed", "stats": self.stats}}}).encode())
        raise AssertionError(u)


class ReleaseChecksTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for n, b in (("TagStudio-4.14.0-Windows-Setup.exe", b"exe"), ("plugin-a-1.0.zip", b"zip")):
            with open(os.path.join(self.dir, n), "wb") as fh:
                fh.write(b)

    def test_sums(self):
        txt = rc.write_sums(self.dir)
        lines = txt.strip().split("\n")
        self.assertEqual([ln.split("  ")[1] for ln in lines], ["TagStudio-4.14.0-Windows-Setup.exe", "plugin-a-1.0.zip"])
        self.assertEqual(lines[0].split("  ")[0], hashlib.sha256(b"exe").hexdigest())
        self.assertTrue(os.path.isfile(os.path.join(self.dir, rc.SUMS)))
        self.assertNotIn(rc.SUMS, rc.write_sums(self.dir))                      # nicht sich selbst

    def test_scan_clean_and_flagged(self):
        f = os.path.join(self.dir, "TagStudio-4.14.0-Windows-Setup.exe")
        vt = FakeVT({"malicious": 0, "suspicious": 0, "undetected": 60, "harmless": 10})
        r = rc.scan(f, "KEY", opener=vt, sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(rc.flagged(r["stats"]), 0)
        self.assertEqual(vt.calls[0][2].get("X-apikey"), "KEY")
        self.assertIn("70/70 Scanner unauffällig", rc.report_md([r]))
        self.assertIn(r["sha256"], r["link"])
        bad = rc.scan(f, "KEY", opener=FakeVT({"malicious": 2, "undetected": 68}, 0), sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(rc.flagged(bad["stats"]), 2)

    def test_big_file_uses_upload_url(self):
        f = os.path.join(self.dir, "gross.exe")
        with open(f, "wb") as fh:
            fh.truncate(rc.SMALL + 1)
        vt = FakeVT({"undetected": 1}, 0)
        rc.scan(f, "KEY", opener=vt, sleep=lambda s: None, log=lambda m: None)
        self.assertEqual(vt.calls[1][1], "https://upload.example/big")

    def test_main_without_key(self):
        old = os.getcwd()
        os.chdir(self.dir)
        env = os.environ.pop("VIRUSTOTAL_API_KEY", None)
        try:
            self.assertEqual(rc.main(["virustotal", "TagStudio-4.14.0-Windows-Setup.exe"]), 0)
            self.assertEqual(open("virustotal.md", encoding="utf-8").read(), "")
        finally:
            os.chdir(old)
            if env is not None:
                os.environ["VIRUSTOTAL_API_KEY"] = env


if __name__ == "__main__":
    unittest.main()
