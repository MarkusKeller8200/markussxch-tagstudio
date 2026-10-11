#!/usr/bin/env python3
"""WAV-Prüfung für das Konzept WAV-Unterstützung (#156).

Liest den RIFF-Aufbau einer WAV-Datei und zeigt, welche Tag-Bereiche vorhanden sind:
  LIST/INFO   RIFF-eigene Textfelder (INAM Titel, IART Künstler, IPRD Album, ICRD Datum, IGNR Genre, ICMT Kommentar …)
  id3 / ID3   ID3v2-Tag als eigener Chunk (so schreiben es u. a. Mp3tag und viele DJ-Programme)
  bext        Broadcast-Wave-Erweiterung (Beschreibung, Urheber, Datum)
  cue / LIST adtl   Cue-Punkte mit Namen
  acid        Tempo und Grundton (ACIDized WAV)
Mit --roundtrip wird eine KOPIE in einem temporären Ordner angelegt, ein ID3-Chunk mit einem Testfeld geschrieben,
wieder gelesen und geprüft, dass die Audiodaten unverändert sind. Die Originaldatei wird nie verändert.

    python tools/wavcheck.py DATEI.wav [...] [--roundtrip]

Nur Standardbibliothek. Teile davon (read_chunks, read_id3, write_id3) sind der Prototyp für die spätere
WAV-Unterstützung in TagStudio.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import struct
import sys
import tempfile
import wave

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

INFO_NAMES = {"INAM": "Titel", "IART": "Künstler", "IPRD": "Album", "ICRD": "Datum", "IGNR": "Genre",
              "ICMT": "Kommentar", "ITRK": "Spur", "IPRT": "Spur", "ISFT": "Software", "ICOP": "Copyright",
              "IENG": "Techniker", "ISRC": "Quelle", "IKEY": "Schlüsselwörter", "ISBJ": "Thema", "ILNG": "Sprache"}
ID3_IDS = (b"id3 ", b"ID3 ", b"ID32")


# --------------------------------------------------------------------------- RIFF lesen
def read_chunks(path: str) -> dict:
    """→ {"ok", "riff_size", "file_size", "chunks": [{"id", "offset", "size"}], "problems": [...]}"""
    out = {"ok": False, "chunks": [], "problems": [], "file_size": os.path.getsize(path)}
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or head[:4] not in (b"RIFF", b"RF64") or head[8:12] != b"WAVE":
            out["problems"].append("keine RIFF/WAVE-Datei")
            return out
        out["riff_size"] = struct.unpack("<I", head[4:8])[0]
        pos = 12
        while pos + 8 <= out["file_size"]:
            f.seek(pos)
            ch = f.read(8)
            cid, size = ch[:4], struct.unpack("<I", ch[4:8])[0]
            out["chunks"].append({"id": cid.decode("latin-1"), "offset": pos, "size": size})
            pos += 8 + size + (size & 1)                 # Chunks sind auf gerade Länge aufgefüllt
        if pos != out["file_size"]:
            out["problems"].append(f"Chunk-Ende ({pos}) passt nicht zur Dateigrösse ({out['file_size']})")
        if head[:4] == b"RIFF" and out["riff_size"] + 8 != out["file_size"]:
            out["problems"].append(f"RIFF-Grösse {out['riff_size']} + 8 ≠ Dateigrösse {out['file_size']}")
    out["ok"] = not out["problems"]
    return out


def chunk_data(path: str, c: dict) -> bytes:
    with open(path, "rb") as f:
        f.seek(c["offset"] + 8)
        return f.read(c["size"])


def read_info(data: bytes) -> dict:
    """LIST-Chunk vom Typ INFO → {Feld-ID: Text}"""
    if data[:4] != b"INFO":
        return {}
    out, i = {}, 4
    while i + 8 <= len(data):
        cid, size = data[i:i + 4].decode("latin-1"), struct.unpack("<I", data[i + 4:i + 8])[0]
        raw = data[i + 8:i + 8 + size].split(b"\x00", 1)[0]
        try:
            out[cid] = raw.decode("utf-8")
        except UnicodeDecodeError:
            out[cid] = raw.decode("latin-1")
        i += 8 + size + (size & 1)
    return out


def read_id3(data: bytes, path: str = ""):
    """ID3-Chunk mit dem TagStudio-Parser lesen → MP3File-ähnliches Objekt (items, version) oder None."""
    from id3tags import MP3File, _syncsafe
    if len(data) < 10 or data[:3] != b"ID3" or data[3] not in (2, 3, 4):
        return None
    size = _syncsafe(data[6:10])
    f = MP3File.__new__(MP3File)
    f.path = path
    f.load(cached={"head": data[:10], "body": data[10:10 + size], "v1": b"", "mpeg": {}, "size": len(data), "mtime": 0})
    return f


def audio_hash(path: str) -> str:
    """Hash der Audiodaten (data-Chunk) – bleibt beim Schreiben von Tags gleich."""
    info = read_chunks(path)
    c = next((c for c in info["chunks"] if c["id"] == "data"), None)
    if c is None:
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        f.seek(c["offset"] + 8)
        left = c["size"]
        while left:
            b = f.read(min(1 << 20, left))
            if not b:
                break
            h.update(b)
            left -= len(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- Prototyp: ID3-Chunk schreiben
def write_id3(path: str, tag: bytes, chunk_id: bytes = b"id3 ") -> None:
    """ID3-Chunk ersetzen bzw. anhängen (alle übrigen Chunks bleiben byte-genau), RIFF-Grösse anpassen.
    Schreibt über eine temporäre Datei im selben Ordner und ersetzt dann atomar."""
    info = read_chunks(path)
    if "keine RIFF/WAVE-Datei" in info["problems"]:
        raise ValueError("keine WAV-Datei")
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".wavtag_", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "wb") as out, open(path, "rb") as src:
            src.seek(0)
            head = src.read(12)
            out.write(head)
            for c in info["chunks"]:
                if c["id"].encode("latin-1") in ID3_IDS:
                    continue
                src.seek(c["offset"])
                left = 8 + c["size"] + (c["size"] & 1)
                while left:
                    b = src.read(min(1 << 20, left))
                    if not b:
                        break
                    out.write(b)
                    left -= len(b)
            out.write(chunk_id + struct.pack("<I", len(tag)) + tag + (b"\x00" if len(tag) & 1 else b""))
            end = out.tell()
            out.seek(4)
            out.write(struct.pack("<I", end - 8))
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def build_id3(frames: dict, version: int = 3) -> bytes:
    """Einfaches ID3v2-Tag aus Textfeldern {"TIT2": "…", "TXXX:NAME": "…"} (mit TagStudio-Items)."""
    from id3tags import MP3File, _to_syncsafe
    f = MP3File.__new__(MP3File)
    f.path = ""
    f.load(cached={"head": b"", "body": b"", "v1": b"", "mpeg": {}, "size": 0, "mtime": 0})
    f.version = version
    for k, v in frames.items():
        f.set_text(k, v)
    body = b"".join(b for it in f.items.values() for b in it.to_frames(version))
    return b"ID3" + bytes([version, 0, 0]) + _to_syncsafe(len(body)) + body


# --------------------------------------------------------------------------- Bericht
def report(path: str) -> dict:
    info = read_chunks(path)
    rep = {"path": path, "ok": info["ok"], "problems": list(info["problems"]),
           "chunks": [f"{c['id']} ({c['size']} B)" for c in info["chunks"]], "info": {}, "id3": None,
           "bext": False, "cue": 0, "acid": None, "format": ""}
    for c in info["chunks"]:
        cid = c["id"]
        if cid == "LIST":
            rep["info"].update(read_info(chunk_data(path, c)))
        elif cid.encode("latin-1") in ID3_IDS:
            f = read_id3(chunk_data(path, c), path)
            rep["id3"] = None if f is None else {"version": f"2.{f.version}", "chunk": cid,
                                                  "fields": {k: f.text(k) for k in list(f.items)[:60]}}
            if f is None:
                rep["problems"].append(f"Chunk „{cid}“ enthält kein lesbares ID3-Tag")
        elif cid == "bext":
            rep["bext"] = True
        elif cid == "cue ":
            d = chunk_data(path, c)
            rep["cue"] = struct.unpack("<I", d[:4])[0] if len(d) >= 4 else 0
        elif cid == "acid":
            d = chunk_data(path, c)
            if len(d) >= 24:
                rep["acid"] = {"root": struct.unpack("<H", d[4:6])[0], "tempo": round(struct.unpack("<f", d[20:24])[0], 2)}
        elif cid == "fmt ":
            d = chunk_data(path, c)
            if len(d) >= 16:
                fmt, ch, sr, _br, _ba, bits = struct.unpack("<HHIIHH", d[:16])
                rep["format"] = f"{'PCM' if fmt == 1 else 'Float' if fmt == 3 else 'Extensible' if fmt == 0xFFFE else fmt} {bits} Bit, {ch} Kanal/Kanäle, {sr} Hz"
    return rep


def roundtrip(path: str) -> dict:
    """Kopie anlegen, ID3-Chunk schreiben (bestehende Felder + Testfeld), lesen, Audio vergleichen."""
    tmpdir = tempfile.mkdtemp(prefix="wavcheck_")
    try:
        cp = os.path.join(tmpdir, os.path.basename(path))
        shutil.copy2(path, cp)
        before = audio_hash(cp)
        old = report(cp)
        fields = dict((old["id3"] or {}).get("fields", {})) if old["id3"] else {}
        fields = {k: v for k, v in fields.items() if k[:4].isalnum() and k[0] in "TW" and v}
        fields["TXXX:TAGSTUDIO_WAVCHECK"] = "ok"
        write_id3(cp, build_id3(fields))
        new = report(cp)
        res = {"audio_same": audio_hash(cp) == before, "riff_ok": new["ok"],
               "field_ok": bool(new["id3"]) and new["id3"]["fields"].get("TXXX:TAGSTUDIO_WAVCHECK") == "ok",
               "info_kept": new["info"] == old["info"], "problems": new["problems"]}
        try:
            with wave.open(cp, "rb") as w:              # Standardbibliothek kann die Datei noch lesen?
                res["wave_ok"] = w.getnframes() > 0
        except (wave.Error, EOFError) as ex:
            res["wave_ok"] = None if "unknown format" in str(ex) else False
        res["ok"] = res["audio_same"] and res["riff_ok"] and res["field_ok"] and res["info_kept"]
        return res
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rt = "--roundtrip" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    bad = 0
    for p in paths:
        r = report(p)
        print(f"== {p}")
        print(f"   Format: {r['format'] or '?'} · Chunks: {', '.join(r['chunks'])}")
        print("   RIFF-Aufbau: " + ("in Ordnung" if r["ok"] else "; ".join(r["problems"])))
        print("   LIST/INFO: " + (", ".join(f"{INFO_NAMES.get(k, k)}={v}" for k, v in r["info"].items()) or "–"))
        print("   ID3-Chunk: " + (f"ID3v{r['id3']['version']} im Chunk „{r['id3']['chunk']}“, {len(r['id3']['fields'])} Feld(er)" if r["id3"] else "–"))
        print(f"   bext: {'ja' if r['bext'] else '–'} · Cue-Punkte: {r['cue'] or '–'} · acid: {r['acid'] or '–'}")
        if rt:
            t = roundtrip(p)
            print("   Schreibtest (Kopie): " + ("OK" if t["ok"] else f"FEHLER {t}"))
            bad += not t["ok"]
        bad += not r["ok"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
