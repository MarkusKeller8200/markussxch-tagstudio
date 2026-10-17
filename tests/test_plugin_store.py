"""#235: Plugins einzeln nachladen und aktualisieren – Katalog bauen, vergleichen, installieren (ohne Netz)."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "packaging"))
import plugin_store as ps  # noqa: E402
import updater  # noqa: E402


class _Resp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _plugin(base, pid, version="1.0", **extra):
    d = os.path.join(base, pid)
    os.makedirs(os.path.join(d, "__pycache__"), exist_ok=True)
    with open(os.path.join(d, "plugin.json"), "w", encoding="utf-8") as fh:
        json.dump({"id": pid, "name": pid.title(), "version": version, "api": 1, **extra}, fh)
    with open(os.path.join(d, "plugin.py"), "w", encoding="utf-8") as fh:
        fh.write(f"ACTIONS = []\nVERSION = {version!r}\n\ndef run(action, ctx, files, options):\n    return {{'message': 'ok'}}\n")
    with open(os.path.join(d, "__pycache__", "plugin.cpython-312.pyc"), "wb") as fh:
        fh.write(b"cache")
    return d


class TestPluginStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.src, self.out, self.dest, self.cache = (os.path.join(t, x) for x in ("src", "out", "dest", "cache"))
        _plugin(self.src, "alpha", "1.2", min_app="4.8.0", category="online")
        _plugin(self.src, "beta", "2.0", env={"python": "3.12"})
        _plugin(self.src, "gamma", "1.0", min_app="9.0.0")
        self.cat = ps.build(self.src, self.out, "4.8.0-beta.1")
        self.files = {}
        for n in os.listdir(self.out):
            with open(os.path.join(self.out, n), "rb") as fh:
                self.files[n] = fh.read()
        tag = "v4.8.0"
        self.assets = [{"name": n, "url": updater.ASSET_HOST + f"{tag}/{n}", "size": len(b),
                        "digest": "sha256:" + hashlib.sha256(b).hexdigest()} for n, b in self.files.items()]

    def tearDown(self):
        self.tmp.cleanup()

    def opener(self, req, timeout):
        return _Resp(self.files[req.full_url.rsplit("/", 1)[1]])

    def entry(self, pid):
        return next(e for e in ps.clean_catalog(self.cat) if e["id"] == pid)

    def install(self, pid, **kw):
        return ps.install(self.entry(pid), kw.pop("assets", self.assets), self.dest, self.cache, "v4.8.0",
                          opener=kw.pop("opener", self.opener), **kw)

    # ---- Katalog bauen
    def test_build(self):
        ids = [e["id"] for e in self.cat["plugins"]]
        self.assertEqual(ids, ["alpha", "beta", "gamma"])
        a = self.cat["plugins"][0]
        self.assertEqual((a["file"], a["min_app"], a["category"]), ("plugin-alpha-1.2.zip", "4.8.0", "online"))
        self.assertEqual(self.cat["plugins"][1]["min_app"], "4.8.0")          # ohne Angabe: Version des Releases
        self.assertTrue(self.cat["plugins"][1]["env"])
        with zipfile.ZipFile(os.path.join(self.out, "plugin-alpha-1.2.zip")) as z:
            self.assertEqual(sorted(z.namelist()), ["alpha/plugin.json", "alpha/plugin.py"])   # ohne Cache
        self.assertEqual(a["sha256"], hashlib.sha256(self.files["plugin-alpha-1.2.zip"]).hexdigest())
        cat2 = ps.build(self.src, os.path.join(self.tmp.name, "out2"), "4.8.0-beta.1")      # reproduzierbar
        self.assertEqual(cat2["plugins"][0]["sha256"], a["sha256"])
        with open(os.path.join(self.out, ps.CATALOG), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), self.cat)

    def test_clean_catalog_skips_bad(self):
        data = {"format": 1, "plugins": [{"id": "../x", "file": "plugin-x-1.zip", "sha256": "0" * 64},
                                          {"id": "ok", "file": "evil.exe", "sha256": "0" * 64},
                                          {"id": "ok", "file": "plugin-ok-1.0.zip", "sha256": "xyz"},
                                          {"id": "ok", "file": "plugin-ok-1.0.zip", "sha256": "a" * 64}]}
        self.assertEqual([e["id"] for e in ps.clean_catalog(data)], ["ok"])
        with self.assertRaisesRegex(ValueError, "Format"):
            ps.clean_catalog({"format": 99, "plugins": []})

    # ---- Versionen und Kanal
    def test_versions(self):
        self.assertGreater(ps.version_key("1.10"), ps.version_key("1.9"))
        self.assertTrue(ps.app_ok("4.8.0", "4.8.0-beta.1"))
        self.assertTrue(ps.app_ok("", "4.7.0"))
        self.assertFalse(ps.app_ok("4.9.0", "4.8.5"))

    def test_catalog_release_per_channel(self):
        cat = [{"name": ps.CATALOG}]
        rels = [{"tag": "v4.8.0", "beta": False, "assets": cat}, {"tag": "v4.9.0-beta.1", "beta": True, "assets": cat},
                {"tag": "v4.9.0-beta.2", "beta": True, "assets": []}, {"tag": "v4.7.0", "beta": False, "assets": []}]
        self.assertEqual(ps.catalog_release(rels, "stable")["tag"], "v4.8.0")
        self.assertEqual(ps.catalog_release(rels, "beta")["tag"], "v4.9.0-beta.1")
        self.assertIsNone(ps.catalog_release(rels[3:], "stable"))
        with self.assertRaisesRegex(ValueError, "veröffentlichten"):
            ps.fetch_catalog("dev", self.cache, releases=rels)

    def test_fetch_catalog(self):
        rel = {"tag": "v4.8.0", "version": "4.8.0", "beta": False, "url": "u", "assets": self.assets}
        res = ps.fetch_catalog("stable", self.cache, releases=[rel], opener=self.opener)
        self.assertEqual(res["release"]["tag"], "v4.8.0")
        self.assertEqual(len(res["plugins"]), 3)

    def test_compare(self):
        inst = [{"id": "alpha", "version": "1.0", "builtin": True},
                {"id": "beta", "version": "2.0", "builtin": True},
                {"id": "gamma", "version": "0.1", "builtin": False}]           # eigenes Plugin
        rows = {r["id"]: r["state"] for r in ps.compare(inst, ps.clean_catalog(self.cat), "4.8.0")}
        self.assertEqual(rows, {"alpha": "update", "beta": "current", "gamma": "own"})
        rows = {r["id"]: r["state"] for r in ps.compare([], ps.clean_catalog(self.cat), "4.8.0")}
        self.assertEqual(rows, {"alpha": "new", "beta": "new", "gamma": "too_new"})

    # ---- Installieren, aktualisieren, entfernen
    def test_install_update_remove(self):
        path = self.install("alpha")
        self.assertEqual(path, os.path.join(self.dest, "alpha"))
        mk = ps.store_info(path)
        self.assertEqual((mk["version"], mk["tag"]), ("1.2", "v4.8.0"))
        self.assertEqual(sorted(os.listdir(self.dest)), ["alpha"])          # keine Reste (.install-/.old-)
        self.assertEqual(os.listdir(self.cache), [])                         # ZIP wieder weg
        self.install("alpha")                                                # erneut: ersetzt die nachgeladene
        self.assertEqual(sorted(os.listdir(self.dest)), ["alpha"])
        ps.remove("alpha", self.dest)
        self.assertFalse(os.path.exists(path))

    def test_own_plugin_untouched(self):
        own = _plugin(self.dest, "alpha", "0.5")
        with self.assertRaisesRegex(ValueError, "eigenes Plugin"):
            self.install("alpha")
        with self.assertRaisesRegex(ValueError, "Nur nachgeladene"):
            ps.remove("alpha", self.dest)
        self.assertTrue(os.path.isfile(os.path.join(own, "plugin.py")))
        with self.assertRaisesRegex(ValueError, "Ungültige"):
            ps.remove("../dest", self.dest)

    def test_checksum_mismatch(self):
        bad = [dict(a, digest="sha256:" + "0" * 64) if a["name"].startswith("plugin-alpha") else a for a in self.assets]
        with self.assertRaisesRegex(ValueError, "stimmen nicht überein"):
            self.install("alpha", assets=bad)
        evil = dict(self.files, **{"plugin-alpha-1.2.zip": b"PK manipuliert"})
        with self.assertRaisesRegex(ValueError, "Prüfsumme"):
            self.install("alpha", opener=lambda req, timeout: _Resp(evil[req.full_url.rsplit("/", 1)[1]]))
        self.assertFalse(os.path.exists(os.path.join(self.dest, "alpha")))

    def test_rejects_unsafe_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("alpha/plugin.json", json.dumps({"id": "alpha"}))
            z.writestr("alpha/../../boese.py", "x")
        data = buf.getvalue()
        e = dict(self.entry("alpha"), sha256=hashlib.sha256(data).hexdigest())
        assets = [{"name": e["file"], "url": updater.ASSET_HOST + "v4.8.0/" + e["file"], "size": len(data),
                   "digest": "sha256:" + e["sha256"]}]
        with self.assertRaisesRegex(ValueError, "Unerwarteter Inhalt"):
            ps.install(e, assets, self.dest, self.cache, opener=lambda req, timeout: _Resp(data))
        self.assertEqual([n for n in os.listdir(self.dest) if not n.startswith(".")], [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "boese.py")))

    def test_rejects_other_plugin(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("alpha/plugin.json", json.dumps({"id": "andere"}))
        data = buf.getvalue()
        e = dict(self.entry("alpha"), sha256=hashlib.sha256(data).hexdigest())
        assets = [{"name": e["file"], "url": updater.ASSET_HOST + "v4.8.0/" + e["file"], "size": len(data),
                   "digest": "sha256:" + e["sha256"]}]
        with self.assertRaisesRegex(ValueError, "anderes Plugin"):
            ps.install(e, assets, self.dest, self.cache, opener=lambda req, timeout: _Resp(data))
        self.assertEqual(os.listdir(self.dest), [])

    # ---- Plugin-Manager: Herkunft und eingebaute Version
    def test_manager_info(self):
        import plugins
        self.install("alpha")
        m = plugins.Manager({}, dirs=[(self.src, True), (self.dest, False)])
        info = {p["id"]: p for p in m.list()}
        self.assertFalse(info["alpha"]["builtin"])
        self.assertEqual(info["alpha"]["store"], {"version": "1.2", "tag": "v4.8.0"})
        self.assertEqual(info["alpha"]["builtin_version"], "1.2")
        self.assertNotIn("store", info["beta"])

    def test_builtin_plugins_declare_min_app(self):
        for name in os.listdir(os.path.join(ROOT, "plugins")):
            mf = os.path.join(ROOT, "plugins", name, "plugin.json")
            if os.path.isfile(mf):
                with open(mf, encoding="utf-8") as fh:
                    self.assertRegex(json.load(fh).get("min_app", ""), r"^\d+\.\d+\.\d+$", name)

    def test_release_plugin_bumps_skips_old_tags(self):
        import release
        self.assertEqual(release.plugin_bumps(ref="v4.7.0"), [])


if __name__ == "__main__":
    unittest.main()
