"""Übersicht aller ID3-Frames erzeugen (#98): docs/ID3-FELDER.md aus id3frames.SPEC.

    python tools/id3_frames_doc.py           # Datei schreiben
    python tools/id3_frames_doc.py --check   # nur prüfen, ob die Datei aktuell ist (Exit-Code 1 sonst)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import id3frames  # noqa: E402
from id3tags import FIELD_NAMES  # noqa: E402

OUT = os.path.join(ROOT, "docs", "ID3-FELDER.md")

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


def version(v: str) -> str:
    return {"34": "2.3 + 2.4", "3": "nur 2.3", "4": "nur 2.4", "x": "inoffiziell"}[v]


def render() -> str:
    rows = []
    for fid in sorted(id3frames.SPEC):
        v22, ver, label = id3frames.SPEC[fid]
        c = id3frames.capabilities(fid)
        rows.append(f"| `{fid}` | {v22 or '–'} | {version(ver)} | {label} | {c['show']} | {c['edit']} | "
                    f"{FIELD_NAMES.get(fid, '') or '–'} |")
    tail = "\n\n**Nur in ID3v2.2 (entfällt):** " + ", ".join(f"`{k}` {v}" for k, v in id3frames.V22_DROPPED.items()) + "\n"
    return HEAD + "\n".join(rows) + tail


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        try:
            with open(OUT, encoding="utf-8") as fh:
                same = fh.read() == text
        except OSError:
            same = False
        print("aktuell" if same else f"veraltet: python tools/id3_frames_doc.py ausführen ({OUT})")
        return 0 if same else 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"geschrieben: {OUT} ({len(id3frames.SPEC)} Frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
