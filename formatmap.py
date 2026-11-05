"""Feld-Zuordnung ID3 ↔ MP4/M4A ↔ FLAC/OGG (Vorbis) ↔ AAC (#262, Grundlage für #264–#266).

TagStudio behält seine ID3-Schlüssel als gemeinsame Sprache; je Format steht hier, unter welchem Namen ein Feld liegt.
Übersicht in der Hilfe (docs/ID3-FELDER.md); die Lese-/Schreibschicht (`mapfile.VORBIS_MAP`, `mp4tags.MP4_TEXT/
MP4_FREE`) folgt derselben Zuordnung – `tests/test_formatmap.py` prüft, dass beide übereinstimmen. Namen nach der TagLib-Property-Zuordnung und den Konventionen von Mp3tag/Picard – **geplant, mit
Testdateien aus den DJ-Programmen zu bestätigen (#446)**.

Werte: (Stufe, Text) mit Stufe "y" = Standardfeld, "p" = nur als freies Feld bzw. per Konvention, "n" = gibt es
nicht, "?" = noch zu messen. Bei FLAC/OGG markiert ein * einen Unterschied zwischen FLAC und OGG (siehe VORBIS_DIFF).
Fehlt ein Frame, gilt "n" (Frames, die in den anderen Formaten kein Gegenstück haben).
"""
from __future__ import annotations

FREE = "----:com.apple.iTunes:"

MP4 = {
    "TIT2": ("y", "`©nam`"), "TPE1": ("y", "`©ART`"), "TALB": ("y", "`©alb`"), "TPE2": ("y", "`aART`"),
    "TCOM": ("y", "`©wrt`"), "TEXT": ("p", "`----:LYRICIST`"), "TPE3": ("p", "`----:CONDUCTOR`"),
    "TPE4": ("p", "`----:REMIXER`"), "TCON": ("y", "`©gen`"), "TDRC": ("y", "`©day`"), "TYER": ("y", "`©day`"),
    "TDOR": ("p", "`----:ORIGINALDATE`"), "TDRL": ("p", "`----:RELEASEDATE`"), "TRCK": ("y", "`trkn` (Nr. + Anzahl)"),
    "TPOS": ("y", "`disk`"), "TSST": ("p", "`----:DISCSUBTITLE`"), "TBPM": ("p", "`tmpo` (nur ganze Zahl)"),
    "TKEY": ("p", "`----:initialkey`"), "TSRC": ("p", "`----:ISRC`"), "TPUB": ("p", "`----:LABEL`"),
    "TCOP": ("y", "`cprt`"), "COMM": ("y", "`©cmt`"), "USLT": ("y", "`©lyr`"),
    "APIC": ("y", "`covr` (nur JPEG/PNG, ohne Bildart)"), "POPM": ("n", "noch nicht – Konvention wird gemessen (#453)"),
    "TIT1": ("y", "`©wrk`"), "GRP1": ("y", "`©grp`"), "TIT3": ("p", "`----:SUBTITLE`"), "TMOO": ("p", "`----:MOOD`"),
    "TMED": ("p", "`----:MEDIA`"), "TLAN": ("p", "`----:LANGUAGE`"), "TENC": ("y", "`©enc`"), "TSSE": ("y", "`©too`"),
    "TSOT": ("y", "`sonm`"), "TSOP": ("y", "`soar`"), "TSOA": ("y", "`soal`"), "TSO2": ("y", "`soaa`"),
    "TSOC": ("y", "`soco`"), "TCMP": ("y", "`cpil`"), "MVNM": ("y", "`©mvn`"), "MVIN": ("y", "`©mvi` + `©mvc`"),
    "TOPE": ("p", "freies Feld über TXXX"), "TOAL": ("p", "freies Feld über TXXX"), "TXXX": ("y", "`----:com.apple.iTunes:<NAME>`"),
    "UFID": ("n", "noch nicht"), "GEOB": ("p", "Serato: `----:com.serato.dj:…` bleibt unverändert erhalten"),
    "CHAP": ("n", "noch nicht (eigene Kapitel-Spur)"), "CTOC": ("n", "noch nicht (eigene Kapitel-Spur)"),
}

VORBIS = {
    "TIT2": ("y", "`TITLE`"), "TPE1": ("y", "`ARTIST`"), "TALB": ("y", "`ALBUM`"), "TPE2": ("y", "`ALBUMARTIST`"),
    "TCOM": ("y", "`COMPOSER`"), "TEXT": ("y", "`LYRICIST`"), "TPE3": ("y", "`CONDUCTOR`"), "TPE4": ("y", "`REMIXER`"),
    "TCON": ("y", "`GENRE`"), "TDRC": ("y", "`DATE`"), "TYER": ("y", "`DATE`"), "TDOR": ("y", "`ORIGINALDATE`"),
    "TDRL": ("y", "`RELEASEDATE`"), "TRCK": ("y", "`TRACKNUMBER` (+ `TRACKTOTAL`)"),
    "TPOS": ("y", "`DISCNUMBER` (+ `DISCTOTAL`)"), "TSST": ("y", "`DISCSUBTITLE`"), "TBPM": ("y", "`BPM`"),
    "TKEY": ("p", "`INITIALKEY` (manche: `KEY`)"), "TSRC": ("y", "`ISRC`"),
    "TPUB": ("p", "`LABEL` (auch `ORGANIZATION`, `PUBLISHER`)"), "TCOP": ("y", "`COPYRIGHT`"),
    "COMM": ("y", "`COMMENT` (manche: `DESCRIPTION`)"), "USLT": ("y", "`LYRICS`"), "SYLT": ("n", "noch nicht"),
    "APIC": ("y", "`PICTURE`-Block (mit Bildart) *"), "POPM": ("n", "noch nicht – `RATING`/`FMPS_RATING` wird gemessen (#453)"),
    "TIT1": ("y", "`WORK`"), "GRP1": ("y", "`GROUPING`"), "TIT3": ("y", "`SUBTITLE`"), "TMOO": ("y", "`MOOD`"),
    "TMED": ("y", "`MEDIA`"), "TLAN": ("y", "`LANGUAGE`"), "TENC": ("y", "`ENCODEDBY`"),
    "TSSE": ("p", "`ENCODING` (Mp3tag: `ENCODERSETTINGS`)"), "TSOT": ("y", "`TITLESORT`"), "TSOP": ("y", "`ARTISTSORT`"),
    "TSOA": ("y", "`ALBUMSORT`"), "TSO2": ("y", "`ALBUMARTISTSORT`"), "TSOC": ("y", "`COMPOSERSORT`"),
    "TCMP": ("y", "`COMPILATION`"), "MVNM": ("y", "`MOVEMENTNAME`"), "MVIN": ("y", "`MOVEMENTNUMBER`"),
    "TOPE": ("y", "`ORIGINALARTIST`"), "TOAL": ("y", "`ORIGINALALBUM`"), "TXXX": ("y", "`<NAME>`"),
    "UFID": ("n", "noch nicht"),
    "GEOB": ("p", "Serato: `SERATO_…` (Base64) bleibt unverändert erhalten *"),
}

# Unterschiede FLAC ↔ OGG Vorbis (in der Tabelle mit * markiert)
VORBIS_DIFF = {
    "APIC": "OGG: Cover als Base64-Feld `METADATA_BLOCK_PICTURE`",
    "GEOB": "OGG: ob Serato hier Daten ablegt, ist noch zu messen",
}

# Rohes AAC (.aac, ADTS) hat kein eigenes Tag-System: höchstens ein vorangestelltes ID3v2 (nicht standardisiert)
AAC = ("p", "ID3v2 davor, nur lesen")

MARK = {"y": "✔", "p": "◐", "n": "✖", "?": "?"}


def cell(table: dict, fid: str) -> str:
    """Zelle für die Übersicht: Zeichen + Name, z. B. „✔ `©nam`“; ohne Eintrag „✖“."""
    lvl, txt = table.get(fid, ("n", ""))
    return f"{MARK[lvl]} {txt}".strip()
