"""#157: Mehrsprachigkeit – Kataloge, Platzhalter, Abdeckung der Oberflächentexte."""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import i18n  # noqa: E402
import i18n_extract as ex  # noqa: E402

PH = re.compile(r"\{[nqx]\}")


class TestCatalog(unittest.TestCase):
    def files(self):
        return [f for f in i18n._files()]

    def test_format_and_placeholders(self):
        self.assertTrue(self.files())
        for f in self.files():
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            for k, v in d.items():
                where = f"{os.path.basename(f)}: {k!r}"
                self.assertIsInstance(v, list, where)
                self.assertEqual(len(v), len(i18n.COLUMNS), where)
                self.assertTrue(all(isinstance(x, str) and x.strip() for x in v), where)
                for lang, x in zip(i18n.COLUMNS, v):
                    self.assertEqual(sorted(PH.findall(k)), sorted(PH.findall(x)), f"{where} [{lang}] Platzhalter")
                    self.assertEqual(ex.skeleton(k), k, f"{where}: Schlüssel nicht in Laufzeitform")

    def test_no_duplicate_keys_across_files(self):
        seen = {}
        for f in self.files():
            with open(f, encoding="utf-8") as fh:
                for k in json.load(fh):
                    self.assertNotIn(k, seen, f"{k!r} in {os.path.basename(f)} und {seen.get(k)}")
                    seen[k] = os.path.basename(f)

    def test_session_api(self):
        from session import Session
        r = Session().i18n_catalog("en")
        self.assertEqual(r["lang"], "en")
        self.assertEqual(r["catalog"]["Einlesen"], "Load")
        self.assertEqual([x["code"] for x in r["langs"]], ["de-CH", "en", "gsw-u-sd-chzh"])
        self.assertEqual(Session().i18n_catalog("xx")["lang"], "de-CH")
        self.assertEqual(i18n.catalog("de-CH"), {})
        self.assertEqual(i18n.detect("en-US"), "en")
        self.assertEqual(i18n.detect("de-DE"), "de-CH")
        self.assertEqual(i18n.detect("gsw"), "gsw-u-sd-chzh")

    def test_extract(self):
        lit = ex.js_literals('const a = `<b>${n}</b> Datei(en) im Tagger\\nKlick: abbrechen`; x = /a"b/; y = "Titel";')
        self.assertIn("Titel", lit)
        self.assertEqual(list(ex.chunks(lit[0])), ["Datei(en) im Tagger", "Klick: abbrechen"])
        self.assertEqual(ex.skeleton("Tagger: 1'234 Dateien, „Neu“"), "Tagger: {n} Dateien, {q}")
        self.assertFalse(ex.is_ui("icon-btn pl-tog"))
        self.assertFalse(ex.is_ui("TXXX:TAGSTUDIO_EDITED"))
        self.assertTrue(ex.is_ui("nicht geprüft"))

    @unittest.skipUnless(os.environ.get("TAGSTUDIO_I18N_STRICT", "0") == "1", "Abdeckung abgeschaltet")
    def test_all_texts_translated(self):
        """Jeder Oberflächentext ist in allen mitgelieferten Sprachen vorhanden (neue Texte im selben Commit übersetzen)."""
        texts = ex.collect()
        for lang in i18n.COLUMNS:
            m = ex.missing(lang, texts)
            n = sum(len(v) for v in m.values())
            self.assertEqual(n, 0, f"{lang}: {n} Texte fehlen, z. B. {json.dumps(dict(list(m.items())[:3]), ensure_ascii=False)[:600]}"
                             " – python3 tools/i18n_extract.py --missing " + lang)


if __name__ == "__main__":
    unittest.main()
