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

import formatmap  # noqa: E402
import id3frames  # noqa: E402
import i18n  # noqa: E402
from id3tags import FIELD_NAMES  # noqa: E402

OUT = os.path.join(ROOT, "docs", "ID3-FELDER.md")
OUT_EN = os.path.join(ROOT, "docs", "ID3-FELDER.en.md")
_NUM = re.compile(r"(?<![\w{])[-+]?\d+(?:['’.,]\d+)*(?![\w}])")

HEAD = """# ID3-Felder in TagStudioSX

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

**Dateiformate (#156, #263, 4.16.0)**

| Format | Tags von TagStudioSX | Zusätzlich gelesen | Hinweise |
|---|---|---|---|
| MP3 | ID3v2.3/v2.4 am Dateianfang | ID3v1 am Dateiende (wird auf Wunsch mitgeschrieben) | – |
| WAV | ID3v2 im Chunk `id3 ` (bzw. `ID3 `) – **alle Frames wie bei MP3** | RIFF `LIST/INFO`, wenn kein ID3-Chunk da ist (nur lesen) | Einstellung „WAV und AIFF“; RF64 (über 4 GB) nur lesen; kein ID3v1 |
| AIFF / AIFC | ID3v2 im Chunk `ID3 ` – **alle Frames wie bei MP3** | `NAME`, `AUTH`, `(c) `, `ANNO`, wenn kein ID3-Chunk da ist (nur lesen) | Einstellung „WAV und AIFF“; kein ID3v1 |
| MP4 / M4A (AAC, ALAC) | iTunes-Atome `ilst` (fest: `©nam`, `©ART` …), freie Felder `----:com.apple.iTunes:NAME` | – | Test (#265, Einstellung „Weitere Formate“); AAC und ALAC haben dieselben Atome, MP4 (Video) ebenso; Audio bleibt byte-gleich, Offsets werden nachgeführt |
| AAC (.aac, roh) | **kein eigenes Tag-System** | ID3v2 davor bzw. ID3v1 am Ende (nur lesen) | **nur lesen** (#455, Einstellung „Weitere Formate“); für Tags als M4A speichern – Umwandeln › M4A – AAC packt ohne Neukodierung um |
| FLAC / OGG Vorbis | Vorbis-Kommentare (`NAME=Wert`, frei wählbar); Cover in FLAC als `PICTURE`-Block, in OGG als `METADATA_BLOCK_PICTURE` | – | FLAC: Test (#264); **OGG/Opus nur lesen** (#266); Mehrfachwerte über mehrere gleiche Felder; Platzpuffer (PADDING) wird genutzt |

Beim Speichern von WAV/AIFF ersetzt TagStudioSX nur den ID3-Chunk; INFO bzw. NAME/AUTH bleiben unverändert. Ob die
DJ-Programme ein Feld in WAV/AIFF auch lesen, ist je Programm verschieden (Messreihe #446).

**Spalten:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 oder inoffiziell · MP3 / WAV / AIFF = schreibbar (✔); dahinter
das entsprechende Feld in ID3v1 bzw. im INFO-/AIFF-Textchunk (nur lesen) · MP4 / M4A, AAC, FLAC / OGG = Name des Felds
im jeweiligen Format (so liest und schreibt TagStudioSX es; Namen mit Testdateien zu bestätigen, #453): ✔ = Standardfeld,
◐ = nur als freies Feld bzw. per Konvention, ✖ = gibt es nicht, * = Unterschied zwischen FLAC und OGG (unter der Tabelle)
· Anzeige = Text, Bild, lesbare Kurzfassung oder Grösse + Prüfsumme · Bearbeiten = womit TagStudioSX das Feld ändern kann
· Mp3tag = Feldname in Mp3tag.

| Frame | v2.2 | Version | Bezeichnung | MP3 | WAV | AIFF | MP4 / M4A (AAC, ALAC) | AAC | FLAC / OGG | Anzeige | Bearbeiten | Mp3tag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""


HEAD_EN = """# ID3 fields in TagStudioSX

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

**File formats (#156, #263, 4.16.0)**

| Format | Tags written by TagStudioSX | Also read | Notes |
|---|---|---|---|
| MP3 | ID3v2.3/v2.4 at the start of the file | ID3v1 at the end (written too on request) | – |
| WAV | ID3v2 in the `id3 ` (or `ID3 `) chunk – **all frames as with MP3** | RIFF `LIST/INFO` if there is no ID3 chunk (read only) | setting “WAV and AIFF”; RF64 (over 4 GB) read only; no ID3v1 |
| AIFF / AIFC | ID3v2 in the `ID3 ` chunk – **all frames as with MP3** | `NAME`, `AUTH`, `(c) `, `ANNO` if there is no ID3 chunk (read only) | setting “WAV and AIFF”; no ID3v1 |
| MP4 / M4A (AAC, ALAC) | iTunes atoms `ilst` (fixed: `©nam`, `©ART` …), free fields `----:com.apple.iTunes:NAME` | – | test (#265, setting “More formats”); AAC and ALAC use the same atoms, so does MP4 (video); audio stays byte-identical, offsets are updated |
| AAC (.aac, raw) | **no tag system of its own** | ID3v2 in front or ID3v1 at the end (read only) | **read only** (#455, setting “More formats”); for tags save as M4A – Convert › M4A – AAC repacks without re-encoding |
| FLAC / OGG Vorbis | Vorbis comments (`NAME=value`, free names); cover in FLAC as `PICTURE` block, in OGG as `METADATA_BLOCK_PICTURE` | – | FLAC: test (#264); **OGG/Opus read only** (#266); multiple values via repeated fields; padding is used |

When saving WAV/AIFF, TagStudioSX only replaces the ID3 chunk; INFO or NAME/AUTH stay unchanged. Whether DJ programs
also read a field in WAV/AIFF differs per program (test series #446).

**Columns:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 or unofficial · MP3 / WAV / AIFF = writable (✔); after it the
matching field in ID3v1 or in the INFO/AIFF text chunk (read only) · MP4 / M4A, AAC, FLAC / OGG = name of the field in
that format (how TagStudioSX reads and writes it; names to be confirmed with test files, #453): ✔ = standard field,
◐ = only as a free field or by convention, ✖ = does not exist, * = difference between FLAC and OGG (below the table)
· Display = text, image, readable summary or size + checksum · Edit = what TagStudioSX can change the field with
· Mp3tag = field name in Mp3tag.

| Frame | v2.2 | Version | Name | MP3 | WAV | AIFF | MP4 / M4A (AAC, ALAC) | AAC | FLAC / OGG | Display | Edit | Mp3tag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""


def version(v: str, lang: str = "de") -> str:
    if lang == "en":
        return {"34": "2.3 + 2.4", "3": "2.3 only", "4": "2.4 only", "x": "unofficial"}[v]
    return {"34": "2.3 + 2.4", "3": "nur 2.3", "4": "nur 2.4", "x": "inoffiziell"}[v]


V1 = {"TIT2": "v1", "TPE1": "v1", "TALB": "v1", "TYER": "v1", "TDRC": "v1", "COMM": "v1", "TRCK": "v1", "TCON": "v1"}


def _side(table: dict) -> dict:
    """chunktags-Zuordnung (Chunk-ID → Feldschlüssel) umgedreht: Frame → „INFO-ID, …“."""
    out: dict = {}
    for cid, key in table.items():
        fid = key.split(":")[0]
        out.setdefault(fid, []).append(f"`{cid.decode('latin-1').strip()}`")
    if "TDRC" in out:
        out.setdefault("TYER", out["TDRC"])
    return {k: ", ".join(v) for k, v in out.items()}


def _fm(t, table: dict, fid: str) -> str:
    """MP4-/AAC-/Vorbis-Zelle; der Hinweistext wird übersetzt (Code in `…` bleibt)."""
    lvl, txt = table.get(fid, ("n", ""))
    return f"{formatmap.MARK[lvl]} {t(txt) if txt else ''}".strip()


def formats(fid: str) -> tuple[str, str, str]:
    """#156/#263: Spalten MP3, WAV, AIFF – alle Frames schreibbar (ID3v2 bzw. ID3-Chunk), dazu Lese-Gegenstück."""
    import chunktags
    wav, aif = _side(chunktags.INFO_MAP), _side(chunktags.AIFF_TEXT)
    mp3 = "✔ · ID3v1" if fid in V1 else "✔"
    return mp3, "✔ · INFO " + wav[fid] if fid in wav else "✔", "✔ · " + aif[fid] if fid in aif else "✔"


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
        m, w, a = formats(fid)
        x = [_fm(t, formatmap.MP4, fid), _fm(t, {fid: formatmap.AAC}, fid), _fm(t, formatmap.VORBIS, fid)]
        rows.append(f"| `{fid}` | {v22 or '–'} | {version(ver, lang)} | {t(label)} | {m} | {w} | {a} | {' | '.join(x)} | "
                    f"{t(c['show'])} | {t(c['edit'])} | {FIELD_NAMES.get(fid, '') or '–'} |")
    star = "\n".join(f"- `{k}`: {t(v)}" for k, v in formatmap.VORBIS_DIFF.items())
    if lang == "en":
        tail = "\n\n**Differences FLAC ↔ OGG** (marked with * in the table):\n\n" + star + "\n\n**Only in ID3v2.2 (dropped):** " + ", ".join(f"`{k}` {t(v)}" for k, v in id3frames.V22_DROPPED.items()) + "\n"
        return HEAD_EN + "\n".join(rows) + tail
    tail = "\n\n**Unterschiede FLAC ↔ OGG** (in der Tabelle mit * markiert):\n\n" + star + "\n\n**Nur in ID3v2.2 (entfällt):** " + ", ".join(f"`{k}` {v}" for k, v in id3frames.V22_DROPPED.items()) + "\n"
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
