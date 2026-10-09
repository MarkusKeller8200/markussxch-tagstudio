"""MarKusSXCH TagStudio – Cue-Punkte aus den Tags lesen (für die Marken im Vorschau-Player).

Unterstützt:
  Serato        GEOB „Serato Markers2“ – Base64 mit Einträgen CUE (Position, Farbe, Name) und LOOP
  Mixed In Key  GEOB/TXXX „CuePoints“ – (Base64-)JSON {"cues": [{"name", "time"}, …]}
Ergebnis: Liste von {"pos": Sekunden, "end": Sekunden|None, "name", "color": "#RRGGBB"|"", "kind": "cue"|"loop",
"index", "source"}; nach Position sortiert, Doppelte (gleiche Stelle aus zwei Quellen) zusammengefasst.
Nur lesen – geschrieben wird nichts. Nur Standardbibliothek.
"""
from __future__ import annotations

import base64
import binascii
import json
import struct

MIK_NAMES = ("cuepoints", "cue points", "cuepoint")


def _b64(data: bytes) -> bytes | None:
    clean = b"".join(data.split())
    if len(clean) % 4 == 1:          # Serato-Eigenheit: ein überzähliges Zeichen am Ende
        clean = clean[:-1]
    try:
        return base64.b64decode(clean + b"=" * (-len(clean) % 4))
    except (binascii.Error, ValueError):
        return None


def _cstr(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("utf-8", "replace")


# --------------------------------------------------------------------------- Serato
def serato_markers2(data: bytes) -> list[dict]:
    """GEOB-Daten von „Serato Markers2“ (ohne GEOB-Kopf) → Cue-Liste."""
    if data[:2] != b"\x01\x01":
        return []
    raw = _b64(data[2:].split(b"\x00", 1)[0])
    if not raw or raw[:2] != b"\x01\x01":
        return []
    out, i = [], 2
    while i < len(raw):
        j = raw.find(b"\x00", i)
        if j <= i:
            break
        name = raw[i:j].decode("ascii", "replace")
        if j + 5 > len(raw):
            break
        n = struct.unpack(">I", raw[j + 1:j + 5])[0]
        body = raw[j + 5:j + 5 + n]
        i = j + 5 + n
        if name == "CUE" and len(body) >= 12:
            out.append({"kind": "cue", "index": body[1], "pos": struct.unpack(">I", body[2:6])[0] / 1000,
                        "end": None, "color": "#%02X%02X%02X" % tuple(body[7:10]), "name": _cstr(body[12:]),
                        "source": "Serato"})
        elif name == "LOOP" and len(body) >= 19:
            s, e = struct.unpack(">II", body[2:10])
            out.append({"kind": "loop", "index": body[1], "pos": s / 1000, "end": e / 1000,
                        "color": "#%02X%02X%02X" % tuple(body[15:18]), "name": _cstr(body[19:]),
                        "source": "Serato"})
    return out


# --------------------------------------------------------------------------- Mixed In Key
def _mik_json(obj, duration: float) -> list[dict]:
    cues = obj.get("cues") if isinstance(obj, dict) else obj
    if not isinstance(cues, list):
        return []
    vals = []
    for k, c in enumerate(cues):
        if not isinstance(c, dict):
            continue
        t = next((c[x] for x in ("time", "position", "pos", "start") if isinstance(c.get(x), (int, float))), None)
        if t is None or t < 0:
            continue
        vals.append((k, float(t), str(c.get("name") or c.get("label") or "")))
    if not vals:
        return []
    top = max(v[1] for v in vals)
    ms = top > duration + 1 if duration > 0 else top > 1000     # Millisekunden oder Sekunden?
    return [{"kind": "cue", "index": k, "pos": t / 1000 if ms else t, "end": None, "color": "",
             "name": name, "source": "Mixed In Key"} for k, t, name in vals]


def mik_cuepoints(data: bytes | str, duration: float = 0) -> list[dict]:
    """„CuePoints“ von Mixed In Key (JSON oder Base64-JSON) → Cue-Liste."""
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    data = data.strip(b"\x00 \r\n\t")
    for cand in (data, _b64(data)):
        if not cand:
            continue
        try:
            return _mik_json(json.loads(cand.decode("utf-8").strip("\x00")), duration)
        except (ValueError, UnicodeDecodeError):
            continue
    return []


# --------------------------------------------------------------------------- Datei
def read(f) -> list[dict]:
    """Alle Cue-Punkte einer geladenen MP3File."""
    import blobs
    duration = float(getattr(f, "duration", 0) or 0)
    found = []
    for it in f.items.values():
        try:
            if it.fid == "GEOB" and it.payload is not None:
                g = blobs.split(it)
                desc = (g.get("desc") or "").strip()
                if desc == "Serato Markers2":
                    found += serato_markers2(g["data"])
                elif desc.lower() in MIK_NAMES:
                    found += mik_cuepoints(g["data"], duration)
            elif it.fid == "TXXX" and (it.desc or "").strip().lower() in MIK_NAMES:
                found += mik_cuepoints(it.text, duration)
        except (ValueError, IndexError, struct.error):
            continue      # kaputte Daten einer Anwendung → einfach keine Marken
    found = [c for c in found if duration <= 0 or c["pos"] <= duration + 1]
    found.sort(key=lambda c: (c["pos"], c["source"] != "Serato"))
    out = []
    for c in found:          # gleiche Stelle aus zwei Quellen (MIK schreibt oft auch Serato-Cues) → einmal
        if out and c["kind"] == out[-1]["kind"] == "cue" and abs(c["pos"] - out[-1]["pos"]) < 0.05:
            if not out[-1]["name"]:
                out[-1]["name"] = c["name"]
            continue
        c["pos"] = round(c["pos"], 3)
        if c["end"] is not None:
            c["end"] = round(c["end"], 3)
        out.append(c)
    return out[:64]
