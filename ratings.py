"""MarKusSXCH TagStudio – Bewertung (#96) und Like (#95).

Bewertung: 0–5 Sterne im ID3-Frame POPM (Popularimeter). Vorhandene POPM-Frames (z. B. von Windows Media Player,
MusicBee, Mp3tag) werden alle angepasst – der Wiedergabezähler bleibt erhalten. Fehlt ein POPM-Frame, wird einer
mit der verbreiteten Kennung „Windows Media Player 9 Series“ angelegt. Ein vorhandenes TXXX:FMPS_Rating (0–1,
z. B. von beaTunes/Clementine) wird mitgeführt. Werte-Zuordnung wie bei Windows: 1=1, 2=64, 3=128, 4=196, 5=255.

Like: als JSON in TXXX:TAGSTUDIO, z. B. {"like": true}. Weitere Schlüssel darin bleiben erhalten.
Nur Standardbibliothek.
"""
from __future__ import annotations

import json

from id3tags import Item

POPM_EMAIL = "Windows Media Player 9 Series"
STAR_BYTE = (0, 1, 64, 128, 196, 255)
TS_KEY = "TXXX:TAGSTUDIO"
FMPS_KEY = "TXXX:FMPS_Rating"


def stars_of_byte(r: int) -> int:
    return 0 if r == 0 else 1 if r < 64 else 2 if r < 128 else 3 if r < 196 else 4 if r < 255 else 5


def _popm_keys(f) -> list[str]:
    return [k for k in f.items if k.split(":", 1)[0] == "POPM"]


def _key_ci(f, key):
    return next((k for k in f.items if k.upper() == key.upper()), None)


def _split_popm(p: bytes):
    """→ (email, rating, rest) – rest = Zähler-Bytes."""
    if b"\x00" not in p:
        return "", 0, b""
    email, rest = p.split(b"\x00", 1)
    return email.decode("latin-1", "replace"), (rest[0] if rest else 0), rest[1:]


def get_rating(f) -> int:
    """0–5 Sterne. Bevorzugt die Windows-Kennung, sonst den ersten POPM-Frame mit Wert, sonst FMPS_Rating."""
    best = None
    for k in _popm_keys(f):
        it = f.get(k)
        if it is None or it.payload is None:
            continue
        email, r, _ = _split_popm(it.payload)
        if email == POPM_EMAIL:
            return stars_of_byte(r)
        if best is None and r:
            best = stars_of_byte(r)
    if best is not None:
        return best
    k = _key_ci(f, FMPS_KEY)
    if k:
        try:
            v = float(f.text(k).strip().replace(",", "."))
            return max(0, min(5, round(v * 5)))
        except ValueError:
            pass
    return 0


def set_rating(f, stars: int) -> bool:
    """Bewertung setzen (0 = keine). → True, wenn sich etwas geändert hat."""
    stars = int(stars)
    if not 0 <= stars <= 5:
        raise ValueError("Bewertung muss zwischen 0 und 5 Sternen liegen.")
    before = get_rating(f)
    byte = STAR_BYTE[stars]
    keys = _popm_keys(f)
    changed = False
    for k in keys:
        it = f.get(k)
        if it is None or it.payload is None:
            continue
        email, r, rest = _split_popm(it.payload)
        if r == byte:
            continue
        payload = email.encode("latin-1", "replace") + b"\x00" + bytes([byte]) + rest
        f.items[k] = Item("POPM", k, desc=email, payload=payload)
        changed = True
    if not keys and stars:
        k = f"POPM:{POPM_EMAIL}"
        f.items[k] = Item("POPM", k, desc=POPM_EMAIL, payload=POPM_EMAIL.encode("latin-1") + b"\x00" + bytes([byte]))
        changed = True
    fk = _key_ci(f, FMPS_KEY)
    if fk:
        val = f"{stars / 5:g}" if stars else "0"
        if f.text(fk).strip() != val:
            f.set_text(fk, val)
            changed = True
    return changed or before != get_rating(f)


def _ts_data(f) -> dict:
    k = _key_ci(f, TS_KEY)
    if not k:
        return {}
    try:
        d = json.loads(f.text(k) or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def get_like(f) -> bool:
    return bool(_ts_data(f).get("like"))


def set_like(f, on: bool) -> bool:
    """Like setzen/entfernen. → True, wenn sich etwas geändert hat."""
    if get_like(f) == bool(on):
        return False
    d = _ts_data(f)
    if on:
        d["like"] = True
    else:
        d.pop("like", None)
    k = _key_ci(f, TS_KEY) or TS_KEY
    if d:
        f.set_text(k, json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    else:
        f.set(k, None)
    return True
