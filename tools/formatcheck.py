"""Prüfwerkzeug für die Messreihe (#446 WAV/AIFF, #453 FLAC/M4A/OGG): zeigt, wie eine Datei aufgebaut ist und welche
Tag-Felder darin stehen – unter welchem Namen das DJ-Programm sie geschrieben hat und wie TagStudioSX sie liest.

    python tools/formatcheck.py DATEI [...]               # nur lesen, Bericht als Text
    python tools/formatcheck.py DATEI --json bericht.json  # Bericht zusätzlich als JSON (für das Issue)
    python tools/formatcheck.py DATEI --roundtrip          # zusätzlich Schreibtest an einer KOPIE

Der Schreibtest kopiert die Datei in einen temporären Ordner, schreibt `TXXX:TAGSTUDIO_FORMATCHECK=ok`, liest neu und
prüft, dass das Feld da ist und die Audiodaten byte-gleich sind. Das Original wird nie verändert. Im Bericht stehen
keine Audiodaten; Bilder und Binärfelder nur mit Grösse und Prüfsumme.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import audioformats  # noqa: E402
from id3tags import MP3File  # noqa: E402

MAX_VALUE = 200


def _short(v) -> str:
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} Bytes, md5 {hashlib.md5(v).hexdigest()[:8]}>"
    v = str(v)
    if len(v) > MAX_VALUE:
        return v[:MAX_VALUE] + f"… ({len(v)} Zeichen)"
    return v


def layout(path: str) -> list:
    """Bausteine der Datei (Chunks, Blöcke, Atome) – Typ und Grösse."""
    k = audioformats.kind_of(path)
    if k in ("wav", "aiff"):
        import chunktags
        return [[c["id"].decode("latin-1"), c["size"]] for c in chunktags.read_layout(path)["chunks"]]
    if k == "flac":
        import flactags
        names = {0: "STREAMINFO", 1: "PADDING", 2: "APPLICATION", 3: "SEEKTABLE", 4: "VORBIS_COMMENT", 5: "CUESHEET",
                 6: "PICTURE"}
        lay = flactags.read_layout(path)
        return ([["ID3v2 davor", lay["prefix"]]] if lay["prefix"] else []) + \
            [[names.get(b["type"], str(b["type"])), b["len"]] for b in lay["blocks"]]
    if k == "m4a":
        import mp4tags
        return [[t.decode("latin-1"), e - s] for t, s, _h, e in mp4tags.top_atoms(path)]
    if k == "ogg":
        return [["OGG-Seiten", os.path.getsize(path)]]
    return [["MP3", os.path.getsize(path)]]


def native_fields(f) -> list:
    """Felder so, wie sie im Format stehen (Name, Wert)."""
    nat = getattr(f, "_native", None)
    if nat is None:                                                   # MP3/WAV/AIFF: ID3-Frames
        return [[k, _short(it.display())] for k, it in f.items.items()]
    out = []
    for e in nat:
        if isinstance(e, dict):                                       # MP4-Atom
            name = e["atom"].decode("latin-1")
            if e["atom"] == b"----":
                name = f"----:{e['mean']}:{e['name']}"
            vals = [_short(v if k != 1 else v.decode("utf-8", "replace")) for k, v in e["values"]]
            out.append([name, " | ".join(vals)])
        else:
            out.append([e[0], _short(e[1])])
    return out


def report(path: str) -> dict:
    f = MP3File(path)
    shown = {k: _short(it.display()) for k, it in f.items.items()}
    nat = native_fields(f)
    known = set()
    for k in f.items:
        known.add(k.split("#")[0])
    serato = [n for n, _v in nat if "serato" in n.lower()]
    return {"file": os.path.basename(path), "format": audioformats.label(f), "info": f.info(),
            "damaged": bool(f.tag_damaged), "read_only": bool(getattr(f, "read_only", False)),
            "codec": getattr(f, "codec", ""), "samplerate": f.samplerate, "bits": getattr(f, "bits", 0),
            "duration": round(float(f.duration or 0), 3), "layout": layout(path), "native": nat,
            "tagstudio": shown, "serato_fields": serato}


def roundtrip(path: str) -> dict:
    d = tempfile.mkdtemp(prefix="ts_formatcheck_")
    try:
        cp = os.path.join(d, os.path.basename(path))
        shutil.copy2(path, cp)
        before = audio_digest(cp)
        f = MP3File(cp)
        if getattr(f, "read_only", False):
            return {"ok": None, "note": "Format wird nur gelesen – kein Schreibtest"}
        f.set_text("TXXX:TAGSTUDIO_FORMATCHECK", "ok")
        f.save()
        g = MP3File(cp)
        res = {"field": g.text("TXXX:TAGSTUDIO_FORMATCHECK") == "ok", "audio_same": audio_digest(cp) == before,
               "skipped": list(getattr(f, "save_skipped", []) or [])}
        res["ok"] = res["field"] and res["audio_same"]
        return res
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "error": str(ex)}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def audio_digest(path: str) -> str:
    k = audioformats.kind_of(path)
    if k in ("wav", "aiff"):
        import chunktags
        return chunktags.audio_hash(path)
    if k == "flac":
        import flactags
        return flactags.audio_hash(path, flactags.read_layout(path)["audio_start"])
    if k == "m4a":
        import mp4tags
        return mp4tags._mdat_hash(path)
    import backup
    lay = backup.read_layout(path)
    return lay["audio_md5"]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rt = "--roundtrip" in argv
    js = None
    if "--json" in argv:
        i = argv.index("--json")
        js = argv[i + 1] if i + 1 < len(argv) else "formatcheck.json"
        del argv[i:i + 2]
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        print(__doc__)
        return 2
    out, bad = [], 0
    for p in files:
        r = report(p)
        if rt:
            r["roundtrip"] = roundtrip(p)
            bad += r["roundtrip"].get("ok") is False
        out.append(r)
        print(f"== {r['file']} · {r['format']} · {r['info']}")
        print("   Aufbau: " + ", ".join(f"{n} ({s})" for n, s in r["layout"]))
        print("   Felder im Format:")
        for n, v in r["native"]:
            print(f"     {n} = {v}")
        print("   So liest TagStudioSX:")
        for k, v in r["tagstudio"].items():
            print(f"     {k} = {v}")
        if r["serato_fields"]:
            print("   Serato: " + ", ".join(r["serato_fields"]))
        if rt:
            print(f"   Schreibtest: {r['roundtrip']}")
    if js:
        with open(js, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print(f"Bericht: {js}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
