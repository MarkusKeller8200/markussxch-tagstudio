"""#117 Machbarkeit: gekaufte Beatport-Titel lesen und mit lokalen Ordnern abgleichen (ohne Netz, Client simuliert)."""
import importlib.util
import os

from helpers import write_mp3, text, txxx
from test_tagger_tools import Base

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_plugin():
    spec = importlib.util.spec_from_file_location("bp_plugin", os.path.join(ROOT, "plugins", "beatport", "plugin.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeClient:
    def __init__(self, pages):
        self.pages = pages

    def get(self, path, **params):
        if path != "/my/downloads/":
            return None
        return self.pages.get(params.get("page"), [])


class Ctx:
    def __init__(self, d):
        self.data_dir = d
        self.logs, self.outputs = [], []

    def log(self, m):
        self.logs.append(m)

    def status(self, m):
        pass

    def output(self, p):
        self.outputs.append(p)


class TestPurchases(Base):
    def test_compare(self):
        bp = load_plugin()
        write_mp3(os.path.join(self.B, "a.mp3"), [text("TIT2", "Nordlicht (Extended Mix)"), text("TPE1", "Mara Lind")], audio_seed=91)
        write_mp3(os.path.join(self.B, "b.mp3"), [text("TIT2", "X"), txxx("BEATPORT_TRACK_ID", "222")], audio_seed=92)
        items = [{"track": {"id": 111, "name": "Nordlicht", "mix_name": "Extended Mix", "artists": [{"name": "Mara Lind"}]}},
                 {"track": {"id": 222, "name": "Andere", "mix_name": "", "artists": [{"name": "Kai"}]}},
                 {"track": {"id": 333, "name": "Fehlt", "mix_name": "Original Mix", "artists": [{"name": "Niemand"}]}}]
        path, got = bp.purchases(FakeClient({1: items}), 100, None)
        self.assertEqual((path, [t["id"] for t in got]), ("/my/downloads/", [111, 222, 333]))
        bp.Client = lambda ctx: FakeClient({1: items})
        ctx = Ctx(self.dir)
        r = bp.run_purchases(ctx, {"folders": self.B, "max": 100})
        self.assertIn("3 gekaufte Titel", r["message"])
        self.assertIn("2 vorhanden, 1 fehlen", r["message"])
        with open(ctx.outputs[0], encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
        self.assertTrue(lines[3].startswith("333;Niemand;Fehlt;Original Mix"))
        self.assertTrue(lines[3].split(";")[6] == "fehlt")


if __name__ == "__main__":
    import unittest
    unittest.main()
