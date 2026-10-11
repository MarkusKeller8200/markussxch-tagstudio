"""Serato-Daten in GEOB-Feldern lesbar machen (#76, nur lesen).

Formate (öffentlich dokumentiert u. a. im Projekt „serato-tags“):
  Serato Analysis   Versionsnummer (2 Bytes, z. B. 2.1)
  Serato Autotags   01 01 + drei Texte mit Nullbyte: BPM, Auto-Gain, Gain (dB)
  Serato BeatGrid   01 00 + Anzahl Marker (uint32); je Marker Position (float32, s) und Beats bis zum nächsten
                    (uint32), der letzte stattdessen das BPM (float32); dann ein Füllbyte
  Serato Markers2   01 01 + Base64 von (01 01 + Einträgen NAME\\0 Länge Inhalt): CUE, LOOP, COLOR, BPMLOCK, FLIP
  Serato Overview   01 05 + Blöcke à 16 Bytes (Wellenform-Übersicht, meist 240)
Ergebnis von decode(): {"name", "summary", "rows": [[Bezeichnung, Wert]], …} oder {"error": …} bei kaputten Daten.
Nur Standardbibliothek.
"""
from __future__ import annotations

import struct

import cues

KNOWN = ("Serato Analysis", "Serato Autotags", "Serato BeatGrid", "Serato Markers2", "Serato Overview",
         "Serato Markers_")


def _mmss(sec: float) -> str:
    sec = max(0.0, float(sec))
    m, s = divmod(sec, 60)
    return f"{int(m)}:{s:06.3f}"


# --------------------------------------------------------------------------- einzelne Formate
def analysis(data: bytes) -> dict:
    if len(data) < 2:
        raise ValueError("zu kurz")
    v = f"{data[0]}.{data[1]}"
    return {"name": "Analyse", "version": v, "summary": f"Serato-Analyse Version {v}", "rows": [["Version", v]]}


def autotags(data: bytes) -> dict:
    if data[:2] != b"\x01\x01":
        raise ValueError("unbekannter Kopf")
    parts = data[2:].split(b"\x00")
    vals = [p.decode("ascii", "replace").strip() for p in parts[:3]]
    if len(vals) < 3:
        raise ValueError("unvollständig")
    bpm, autogain, gain = vals
    return {"name": "Autotags", "bpm": _num(bpm), "autogain": _num(autogain), "gain": _num(gain),
            "summary": f"BPM {bpm} · Auto-Gain {autogain} dB · Gain {gain} dB",
            "rows": [["BPM", bpm], ["Auto-Gain", f"{autogain} dB"], ["Gain", f"{gain} dB"]]}


def _num(s):
    try:
        return float(s)
    except ValueError:
        return None


def beatgrid(data: bytes) -> dict:
    """→ {"markers": [{"pos", "beats"|None, "bpm"|None}], "bpm", "first"} (BPM und erster Schlag für den Player)."""
    if data[:2] != b"\x01\x00" or len(data) < 6:
        raise ValueError("unbekannter Kopf")
    n = struct.unpack(">I", data[2:6])[0]
    if n == 0:
        return {"name": "BeatGrid", "markers": [], "bpm": None, "first": None, "summary": "kein Beatgrid", "rows": []}
    if n > 10000 or len(data) < 6 + n * 8:
        raise ValueError("Länge passt nicht")
    markers = []
    for k in range(n):
        o = 6 + k * 8
        pos = struct.unpack(">f", data[o:o + 4])[0]
        if k < n - 1:
            markers.append({"pos": round(pos, 4), "beats": struct.unpack(">I", data[o + 4:o + 8])[0], "bpm": None})
        else:
            markers.append({"pos": round(pos, 4), "beats": None, "bpm": round(struct.unpack(">f", data[o + 4:o + 8])[0], 3)})
    # BPM zwischen Markern aus Abstand und Beats; das Tempo des Titels = letzter Marker bzw. erster Abschnitt
    for a, b in zip(markers, markers[1:]):
        if a["beats"]:
            a["bpm"] = round(60 * a["beats"] / (b["pos"] - a["pos"]), 3) if b["pos"] > a["pos"] else None
    bpm = markers[-1]["bpm"] if len(markers) == 1 else markers[0]["bpm"]
    rows = [[f"Marker {k + 1}", f"{_mmss(m['pos'])} · {m['bpm'] or '?'} BPM" + (f" · {m['beats']} Beats" if m["beats"] else "")]
            for k, m in enumerate(markers)]
    return {"name": "BeatGrid", "markers": markers, "bpm": bpm, "first": markers[0]["pos"],
            "summary": f"Beatgrid: {len(markers)} Marker, {bpm} BPM, erster Schlag {_mmss(markers[0]['pos'])}",
            "rows": rows}


def markers2(data: bytes) -> dict:
    """Cues und Loops (wie cues.serato_markers2) plus Track-Farbe und BPM-Sperre."""
    if data[:2] != b"\x01\x01":
        raise ValueError("unbekannter Kopf")
    raw = cues._b64(data[2:].split(b"\x00", 1)[0])
    if not raw or raw[:2] != b"\x01\x01":
        raise ValueError("Base64-Inhalt nicht lesbar")
    color, lock, entries, i = None, None, [], 2
    while i < len(raw):
        j = raw.find(b"\x00", i)
        if j <= i or j + 5 > len(raw):
            break
        name = raw[i:j].decode("ascii", "replace")
        n = struct.unpack(">I", raw[j + 1:j + 5])[0]
        body = raw[j + 5:j + 5 + n]
        i = j + 5 + n
        if name == "COLOR" and len(body) >= 4:
            color = "#%02X%02X%02X" % tuple(body[1:4])
        elif name == "BPMLOCK" and len(body) >= 1:
            lock = bool(body[0])
        elif name in ("CUE", "LOOP", "FLIP"):
            entries.append(name)
    cl = cues.serato_markers2(data)
    rows = []
    if color:
        rows.append(["Track-Farbe", color])
    if lock is not None:
        rows.append(["BPM gesperrt", "ja" if lock else "nein"])
    for c in cl:
        what = f"Cue {c['index'] + 1}" if c["kind"] == "cue" else f"Loop {c['index'] + 1}"
        span = _mmss(c["pos"]) + (f" – {_mmss(c['end'])}" if c.get("end") is not None else "")
        rows.append([what, f"{span} · {c['color']}" + (f" · „{c['name']}“" if c["name"] else "")])
    n_cue = sum(1 for c in cl if c["kind"] == "cue")
    n_loop = sum(1 for c in cl if c["kind"] == "loop")
    flips = entries.count("FLIP")
    summ = f"{n_cue} Cue(s), {n_loop} Loop(s)" + (f", {flips} Flip(s)" if flips else "") + \
           (f" · Farbe {color}" if color else "") + (" · BPM gesperrt" if lock else "")
    return {"name": "Markers2", "cues": cl, "color": color, "bpm_lock": lock, "summary": summ, "rows": rows}


def overview(data: bytes) -> dict:
    """→ {"bars": [0–1 je Block]} – Höhe je Block aus den 16 Werten (für eine kleine Vorschau)."""
    if data[:2] != b"\x01\x05":
        raise ValueError("unbekannter Kopf")
    body = data[2:]
    blocks = [body[k:k + 16] for k in range(0, len(body) - 15, 16)]
    if not blocks:
        raise ValueError("keine Daten")
    top = max(max(b) for b in blocks) or 1
    bars = [round(max(b) / top, 3) for b in blocks]
    return {"name": "Overview", "bars": bars, "summary": f"Wellenform-Übersicht ({len(bars)} Blöcke)",
            "rows": [["Blöcke", str(len(bars))]]}


DECODERS = {"Serato Analysis": analysis, "Serato Autotags": autotags, "Serato BeatGrid": beatgrid,
            "Serato Markers2": markers2, "Serato Overview": overview}


def decode(desc: str, data: bytes) -> dict | None:
    """Serato-GEOB lesbar machen; None, wenn kein bekanntes Serato-Feld; {"error"} bei kaputten Daten."""
    desc = (desc or "").strip()
    fn = DECODERS.get(desc)
    if fn is None:
        if desc == "Serato Markers_":
            return {"name": "Markers (alt)", "summary": "älteres Serato-Format (Markers_) – nur als Rohdaten",
                    "rows": [], "old": True}
        return None
    try:
        out = fn(data)
    except (ValueError, IndexError, struct.error) as ex:
        return {"name": desc.replace("Serato ", ""), "error": f"Serato-Daten nicht lesbar ({ex}) – Rohdaten unten",
                "summary": "nicht lesbar", "rows": []}
    out["source"] = "Serato"
    return out


def of_file(f) -> dict:
    """Alle Serato-Daten einer Datei: {"BeatGrid": {...}, "Autotags": {...}, …}."""
    import blobs
    out = {}
    for it in f.items.values():
        if it.fid == "GEOB" and it.payload is not None and (it.desc or "").startswith("Serato"):
            try:
                g = blobs.split(it)
            except (ValueError, IndexError):
                continue
            d = decode(g.get("desc") or it.desc, g["data"])
            if d is not None:
                out[d["name"]] = d
    return out
