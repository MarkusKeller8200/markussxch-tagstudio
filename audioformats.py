"""Welche Dateiformate TagStudio kennt und welche Klasse sie liest/schreibt (#262).

MP3 bleibt der Standardweg (`id3tags.MP3File`). Für die anderen Formate liefert `MP3File(pfad)` über `open_class`
die passende Unterklasse – so funktionieren alle Stellen, die `MP3File(pfad)` aufrufen, ohne Änderung, und nie wird
ein ID3-Kopf vor eine fremde Datei geschrieben. In Tagger und Vergleich erscheinen die Formate nur, wenn sie in der
Einstellung „Formate in Tagger und Vergleich“ (`tag_formats`) gewählt sind.
"""
from __future__ import annotations

import hashlib
import os

# Format-ID → (Endungen, Anzeige, Modul, Klasse, schreibbar)
FORMATS = {
    "wav": ((".wav",), "WAV", "chunktags", "ChunkFile", True),
    "aiff": ((".aif", ".aiff", ".aifc"), "AIFF", "chunktags", "ChunkFile", True),
    "flac": ((".flac",), "FLAC", "flactags", "FlacFile", True),
    "m4a": ((".m4a", ".mp4", ".m4b"), "MP4 / M4A (AAC, ALAC)", "mp4tags", "Mp4File", True),
    "ogg": ((".ogg", ".oga", ".opus"), "OGG Vorbis / Opus (nur lesen)", "oggtags", "OggFile", False),
    "aac": ((".aac", ".adts"), "AAC roh (.aac, nur lesen)", "aactags", "AacFile", False),               # #455
}
ORDER = ["wav", "aiff", "flac", "m4a", "ogg", "aac"]
OTHER_EXTS = tuple(e for f in FORMATS.values() for e in f[0])
FP_BYTES = 256 * 1024


def kind_of(path) -> str:
    """Format-ID nach der Endung ("" = MP3 oder unbekannt)."""
    p = str(path or "").lower()
    for k, (exts, *_r) in FORMATS.items():
        if p.endswith(exts):
            return k
    return ""


def is_other(path) -> bool:
    return bool(kind_of(path))


def open_class(path):
    """Klasse für eine Nicht-MP3-Datei oder None."""
    k = kind_of(path)
    if not k:
        return None
    import importlib
    _e, _l, mod, cls, _w = FORMATS[k]
    return getattr(importlib.import_module(mod), cls)


def exts_for(ids) -> tuple:
    out = []
    for i in ids or []:
        if i in FORMATS:
            out += FORMATS[i][0]
    return tuple(out)


def clean_ids(ids) -> list[str]:
    return [i for i in ORDER if i in set(ids or [])]


def label(f) -> str:
    """Kurzname für die Spalte „Format“ im Tagger."""
    k = kind_of(getattr(f, "path", ""))
    if not k:
        return "MP3"
    if hasattr(f, "format_name"):
        return f.format_name()
    return {"wav": "WAV", "aiff": "AIFF"}.get(k, k.upper())


# --------------------------------------------------------------------------- Sicherungen (backup.py)
def tag_bytes(path: str) -> bytes:
    k = kind_of(path)
    if k in ("wav", "aiff"):
        import chunktags
        return chunktags.read_tag_bytes(path)
    if k == "flac":
        import flactags
        return flactags.tag_bytes(path)
    if k == "m4a":
        import mp4tags
        return mp4tags.tag_bytes(path)
    f = open_class(path).__new__(open_class(path))
    f.path = path
    f.load()
    return getattr(f, "_raw", b"")


def write_tag_bytes(path: str, tag: bytes) -> None:
    k = kind_of(path)
    if k in ("wav", "aiff"):
        import chunktags
        return chunktags.write_tag_bytes(path, tag)
    if k == "flac":
        import flactags
        return flactags.write_tag_bytes(path, tag)
    if k == "m4a":
        import mp4tags
        return mp4tags.write_tag_bytes(path, tag)
    raise ValueError("Dieses Format wird nur gelesen – nicht wiederhergestellt.")


def audio_fingerprint(path: str) -> tuple[int, str]:
    """(Länge, MD5 der ersten 256 KB) der Audiodaten – erkennt beim Wiederherstellen eine andere Datei."""
    k = kind_of(path)
    start, end = 0, os.path.getsize(path)
    if k in ("wav", "aiff"):
        import chunktags
        c = chunktags._audio_chunk(chunktags.read_layout(path))
        if c is not None:
            start, end = c["data_start"], min(c["data_start"] + c["size"], c["end"])
    elif k == "flac":
        import flactags
        start = flactags.read_layout(path)["audio_start"]
    elif k == "m4a":
        import mp4tags
        md = [a for a in mp4tags.top_atoms(path) if a[0] == b"mdat"]
        if md:
            start, end = md[0][1] + md[0][2], md[0][3]
    with open(path, "rb") as f:
        f.seek(start)
        fp = hashlib.md5(f.read(min(FP_BYTES, max(0, end - start)))).hexdigest()
    return max(0, end - start), fp


def from_tag_bytes(kind: str, tag: bytes):
    """Gesicherte Tag-Bytes (FLAC-Blöcke bzw. ilst) als Objekt mit `items`/`tag_desc` – für „Änderungen ansehen“."""
    if kind == "flac":
        import flactags
        from mapfile import parse_picture, parse_vorbis_comment
        f = flactags.FlacFile.__new__(flactags.FlacFile)
        blocks, p = [], 0
        while p + 4 <= len(tag):
            t, ln = tag[p] & 0x7F, int.from_bytes(tag[p + 1:p + 4], "big")
            blocks.append((t, tag[p + 4:p + 4 + ln]))
            p += 4 + ln
        vc = next((d for t, d in blocks if t == flactags.VORBIS_COMMENT), None)
        f._native = parse_vorbis_comment(vc)[1] if vc is not None else []
        f._covers = [parse_picture(d) for t, d in blocks if t == flactags.PICTURE]
    elif kind == "m4a":
        import mp4tags
        f = mp4tags.Mp4File.__new__(mp4tags.Mp4File)
        f._native = mp4tags.parse_ilst(tag, (b"ilst", 0, 8, len(tag))) if tag else []
    else:
        return None
    f.items, f._srcname, f.version = {}, {}, 4
    f._to_items()
    f.tag_desc = FORMATS[kind][1]
    return f


def audio_range(path: str) -> tuple[int, int] | None:
    """(Anfang, Ende) der Audiodaten – für den Wellenform-Schlüssel, der beim Taggen gleich bleiben soll (#448/#454)."""
    k = kind_of(path)
    try:
        if k in ("wav", "aiff"):
            import chunktags
            c = chunktags._audio_chunk(chunktags.read_layout(path))
            return (c["data_start"], min(c["data_start"] + c["size"], c["end"])) if c else None
        if k == "flac":
            import flactags
            return flactags.read_layout(path)["audio_start"], os.path.getsize(path)
        if k == "m4a":
            import mp4tags
            md = [a for a in mp4tags.top_atoms(path) if a[0] == b"mdat"]
            return (md[0][1] + md[0][2], md[0][3]) if md else None
    except (ValueError, OSError):
        return None
    return None
