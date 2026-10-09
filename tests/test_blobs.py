"""Tests für den Binärfeld-Editor (blobs.py): Erkennen und byte-genaues Ändern von GEOB/PRIV."""
import base64
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import blobs  # noqa: E402
from id3tags import Item, MP3File  # noqa: E402
from helpers import frame, write_mp3  # noqa: E402


def geob(data, mime=b"application/octet-stream", fname=b"", desc=b"Daten"):
    return Item("GEOB", "GEOB:" + desc.decode(), desc=desc.decode(), payload=b"\x00" + mime + b"\x00" + fname + b"\x00" + desc + b"\x00" + data)


class TestBlobs(unittest.TestCase):
    def test_base64_json_mixed_in_key(self):
        js = json.dumps({"key": "8A", "energy": 6})
        it = geob(base64.b64encode(js.encode()).rstrip(b"="), mime=b"application/octet-stream", desc=b"CuePoints")
        v = blobs.view(it)
        self.assertEqual((v["kind"], v["inner"], v["text"], v["editable"]), ("base64", "json", js, True))
        new = blobs.update(it, text=js.replace("6", "7"))
        self.assertFalse(new.payload.endswith(b"="))                 # Polsterung wie im Original (keine)
        self.assertEqual(blobs.view(new)["text"], js.replace("6", "7"))
        self.assertTrue(new.payload.startswith(b"\x00application/octet-stream\x00\x00CuePoints\x00"))

    def test_text_keeps_trailing_nul(self):
        it = Item("PRIV", "PRIV:www.example.com", desc="www.example.com", payload=b"www.example.com\x00Hallo Welt\x00")
        v = blobs.view(it)
        self.assertEqual((v["kind"], v["text"], v["owner"]), ("text", "Hallo Welt", "www.example.com"))
        self.assertEqual(blobs.update(it, text="Neu").payload, b"www.example.com\x00Neu\x00")

    def test_binary_only_header(self):
        data = bytes(range(256))
        it = geob(data, desc=b"Serato Markers2")
        v = blobs.view(it)
        self.assertEqual((v["kind"], v["editable"]), ("binary", False))
        self.assertIn("00000000  00 01 02", v["hex"])
        with self.assertRaises(ValueError):
            blobs.update(it, text="x")
        new = blobs.update(it, mime="application/x-serato", filename="m.bin")
        s = blobs.split(new)
        self.assertEqual((s["mime"], s["filename"], s["desc"], s["data"]), ("application/x-serato", "m.bin", "Serato Markers2", data))
        self.assertIs(blobs.update(it, mime="application/octet-stream", filename=""), it)   # unverändert

    def test_xml_with_prefix(self):
        it = geob(b"\x02\x00<a><b/></a>\x00", desc=b"Analyse")
        v = blobs.view(it)
        self.assertEqual((v["kind"], v["text"]), ("xml", "<a><b/></a>"))
        self.assertTrue(blobs.update(it, text="<a/>").payload.endswith(b"\x02\x00<a/>\x00"))

    def test_session(self):
        import time
        import core
        from session import Session
        d = tempfile.mkdtemp(prefix="tagstudio_blobs_")
        old = (core.CONFIG, core.CONFIG_OLD)
        core.CONFIG = core.CONFIG_OLD = os.path.join(d, "cfg.json")
        try:
            path = os.path.join(d, "a.mp3")
            js = base64.b64encode(b'{"k":1}')
            write_mp3(path, [frame("GEOB", b"\x00application/octet-stream\x00\x00MIK\x00" + js)])
            s = Session()
            s.start_tag_load(d, False)
            while not s.task_status()["done"]:
                time.sleep(0.02)
            det = s.tag_detail([0])
            fld = next(x for x in det["fields"] if x["key"].startswith("GEOB"))
            self.assertTrue(fld["blob"])
            b = s.tag_blob(0, fld["key"])
            self.assertEqual((b["ok"], b["inner"], b["text"]), (True, "json", '{"k":1}'))
            self.assertEqual(s.blob_pretty('{"k":1}', "json")["text"], '{\n  "k": 1\n}')
            r = s.tag_blob_set(0, fld["key"], '{"k":2}', "application/json", None)
            self.assertIn("geändert", r["message"])
            self.assertEqual(s.tag_blob(0, fld["key"])["text"], '{"k":2}')
            self.assertEqual(s.tag_blob(0, fld["key"])["mime"], "application/json")
            s.do_undo()
            self.assertEqual(s.tag_blob(0, fld["key"])["text"], '{"k":1}')
        finally:
            core.CONFIG, core.CONFIG_OLD = old
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
