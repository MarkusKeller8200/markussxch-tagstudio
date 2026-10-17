"""Übersicht aller ID3-Frames erzeugen (#98): docs/ID3-FELDER.md aus id3frames.SPEC, dazu die englische
Fassung docs/ID3-FELDER.en.md (#219) – Bezeichnungen aus dem Sprachkatalog web/i18n.

    python tools/id3_frames_doc.py           # Dateien schreiben
    python tools/id3_frames_doc.py --check   # nur prüfen, ob die Dateien aktuell sind (Exit-Code 1 sonst)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import id3frames  # noqa: E402
import i18n  # noqa: E402
from id3tags import FIELD_NAMES  # noqa: E402

OUT = os.path.join(ROOT, "docs", "ID3-FELDER.md")
OUT_EN = os.path.join(ROOT, "docs", "ID3-FELDER.en.md")
_NUM = re.compile(r"(?<![\w{])[-+]?\d+(?:['’.,]\d+)*(?![\w}])")

HEAD = """# ID3-Felder in TagStudio

Diese Übersicht wird aus `id3frames.py` erzeugt (`python tools/id3_frames_doc.py`) – bitte nicht von Hand ändern.
Issue #98.

**Grundsätze**

- **Lesen:** alle Frames aus ID3v2.2, v2.3 und v2.4. ID3v2.2 wird beim Laden nach v2.3 umgesetzt (3-Zeichen-IDs →
  4-Zeichen-IDs, auch in LINK); nur `CRM` (verschlüsselte Meta-Daten) hat kein Gegenstück und entfällt.
- **Schreiben:** unveränderte Frames werden **byte-genau** übernommen (auch unbekannte und eigene Frames anderer
  Programme). Beim Wechsel der ID3-Version werden Frames neu verpackt, der Inhalt bleibt.
- **v2.3 ↔ v2.4:** `TYER`/`TDAT` ↔ `TDRC`, `TORY` ↔ `TDOR`, `IPLS` ↔ `TIPL`; `TIME`, `TRDA`, `TSIZ` gibt es in v2.4
  nicht (entfallen beim Umwandeln nach v2.4). Mehrfachwerte: v2.4 null-getrennt, v2.3 mit „ / “ (Personenlisten bleiben
  Paare). Die Stimmung (#12) liegt in v2.4 in `TMOO`, in v2.3 in `TXXX:MOOD`. Andere v2.4-Textfelder (z. B. `TSOA`,
  `TDRL`) werden in v2.3-Dateien unverändert geschrieben – so machen es auch iTunes und viele DJ-Programme.
- **Binär-Frames nur einer Version** (`RVAD`/`EQUA` bzw. `RVA2`/`EQU2`, `ASPI`, `SEEK`, `SIGN`) bleiben beim Umwandeln
  erhalten, die meisten Programme ignorieren sie in der jeweils anderen Version.
- **Verschlüsselte oder komprimierte Frames** werden in derselben Version byte-genau behalten; beim Wechsel der
  ID3-Version können sie nicht neu verpackt werden und entfallen.

**Spalten:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 oder inoffiziell · Anzeige = Text, Bild, lesbare Kurzfassung
oder Grösse + Prüfsumme · Bearbeiten = womit TagStudio das Feld ändern kann · Mp3tag = Feldname in Mp3tag.

| Frame | v2.2 | Version | Bezeichnung | Anzeige | Bearbeiten | Mp3tag |
|---|---|---|---|---|---|---|
"""


HEAD_EN = """# ID3 fields in TagStudio

*English version – [Deutsch](ID3-FELDER.md).* This overview is generated from `id3frames.py`
(`python tools/id3_frames_doc.py`) – please do not edit it by hand. Issue #98.

**Principles**

- **Reading:** all frames from ID3v2.2, v2.3 and v2.4. ID3v2.2 is converted to v2.3 when loading (3-character IDs →
  4-character IDs, in LINK too); only `CRM` (encrypted meta data) has no counterpart and is dropped.
- **Writing:** unchanged frames are taken over **byte-exactly** (unknown frames and other programs' own frames too).
  When the ID3 version changes, frames are repacked, the content stays.
- **v2.3 ↔ v2.4:** `TYER`/`TDAT` ↔ `TDRC`, `TORY` ↔ `TDOR`, `IPLS` ↔ `TIPL`; `TIME`, `TRDA`, `TSIZ` do not exist in
  v2.4 (dropped when converting to v2.4). Multiple values: v2.4 null-separated, v2.3 with “ / ” (people lists stay
  pairs). The mood (#12) is stored in `TMOO` in v2.4 and in `TXXX:MOOD` in v2.3. Other v2.4 text fields (e.g. `TSOA`,
  `TDRL`) are written unchanged into v2.3 files – iTunes and many DJ programs do the same.
- **Binary frames of only one version** (`RVAD`/`EQUA` or `RVA2`/`EQU2`, `ASPI`, `SEEK`, `SIGN`) are kept when
  converting; most programs ignore them in the other version.
- **Encrypted or compressed frames** are kept byte-exactly in the same version; when the ID3 version changes they
  cannot be repacked and are dropped.

**Columns:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 or unofficial · Display = text, image, readable summary or
size + checksum · Edit = what TagStudio can change the field with · Mp3tag = field name in Mp3tag.

| Frame | v2.2 | Version | Name | Display | Edit | Mp3tag |
|---|---|---|---|---|---|---|
"""


def version(v: str, lang: str = "de") -> str:
    if lang == "en":
        return {"34": "2.3 + 2.4", "3": "2.3 only", "4": "2.4 only", "x": "unofficial"}[v]
    return {"34": "2.3 + 2.4", "3": "nur 2.3", "4": "nur 2.4", "x": "inoffiziell"}[v]


def render(lang: str = "de") -> str:
    cat = i18n.shipped(lang) if lang != "de" else {}

    def t(s):
        if s in cat:
            return cat[s]
        nums = iter(_NUM.findall(s))                 # Laufzeitform: Zahlen als {n} (z. B. „(v2.3, iTunes)“)
        v = cat.get(_NUM.sub("{n}", s))
        return re.sub(r"\{n\}", lambda m: next(nums, m.group(0)), v) if v else s
    rows = []
    for fid in sorted(id3frames.SPEC):
        v22, ver, label = id3frames.SPEC[fid]
        c = id3frames.capabilities(fid)
        rows.append(f"| `{fid}` | {v22 or '–'} | {version(ver, lang)} | {t(label)} | {t(c['show'])} | {t(c['edit'])} | "
                    f"{FIELD_NAMES.get(fid, '') or '–'} |")
    if lang == "en":
        tail = "\n\n**Only in ID3v2.2 (dropped):** " + ", ".join(f"`{k}` {t(v)}" for k, v in id3frames.V22_DROPPED.items()) + "\n"
        return HEAD_EN + "\n".join(rows) + tail
    tail = "\n\n**Nur in ID3v2.2 (entfällt):** " + ", ".join(f"`{k}` {v}" for k, v in id3frames.V22_DROPPED.items()) + "\n"
    return HEAD + "\n".join(rows) + tail


def main() -> int:
    outs = [(OUT, render("de")), (OUT_EN, render("en"))]
    if "--check" in sys.argv:
        ok = True
        for path, text in outs:
            try:
                with open(path, encoding="utf-8") as fh:
                    same = fh.read() == text
            except OSError:
                same = False
            ok = ok and same
            print("aktuell" if same else f"veraltet: python tools/id3_frames_doc.py ausführen ({path})")
        return 0 if ok else 1
    for path, text in outs:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"geschrieben: {path} ({len(id3frames.SPEC)} Frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
