"""Gemeinsame Bausteine für Online-Abgleiche (4.1.0): Titel normalisieren, Mix-Namen trennen, Kandidaten bewerten,
gedrosselte HTTP-Abfragen je Dienst. Nur Standardbibliothek.

Ein **Kandidat** ist ein dict mit (soweit bekannt):
    source, id, title, mix, artists (Liste), length (Sekunden), isrc, album, album_artist, label, catno, date,
    genre, bpm, cover, track, disc, ids ({TXXX-Schlüssel: Wert}), url
"""
from __future__ import annotations

import difflib
import email.utils
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from id3tags import MV

SURE, MAYBE = 0.80, 0.62     # Trefferschwellen wie beim Beatport-Plugin
TIMEOUT = 30

_MIX_RE = re.compile(r"\s*[\(\[]([^\)\]]*(mix|edit|remix|version|dub|rework|bootleg|vip|remaster(?:ed)?)[^\)\]]*)[\)\]]\s*$", re.I)
_FEAT_RE = re.compile(r"\s*[\(\[]?\b(feat\.?|ft\.?|featuring)\b.*$", re.I)


# =========================================================================== Text
def norm(s) -> str:
    """Für den Vergleich: Akzente weg, Kleinbuchstaben, nur Buchstaben/Ziffern; nicht-lateinische Schrift bleibt."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = s.replace("ß", "ss").replace("&", " and ")
    s = re.sub(r"[\W_]+", " ", s)
    return " ".join(s.split())


def strip_feat(s) -> str:
    return _FEAT_RE.sub("", s or "").strip()


def split_title(title) -> tuple[str, str]:
    """'Song (Extended Mix)' → ('Song', 'Extended Mix'); auch 'Song - Extended Mix' (Deezer/iTunes-Schreibweise)."""
    t = (title or "").strip()
    m = _MIX_RE.search(t)
    if m:
        return t[:m.start()].strip(), m.group(1).strip()
    m = re.match(r"^(.*?)\s+-\s+([^-]*(mix|edit|remix|version|dub|remaster(?:ed)?)[^-]*)$", t, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return t, ""


def file_info(f) -> dict:
    """Suchangaben aus einer MP3File: Titel ohne Mix, Mix, Künstler, ISRC, Dauer; ohne Titel aus dem Dateinamen."""
    title, artist = f.text("TIT2"), f.text("TPE1")
    if not title:
        base = os.path.splitext(os.path.basename(f.path))[0]
        base = re.sub(r"^\d+[\s._-]+", "", base)
        if " - " in base:
            a, t = base.split(" - ", 1)
            artist, title = artist or a, t
        else:
            title = base
    name, mix = split_title(title)
    return {"title": name, "mix": mix, "artist": artist.replace(MV, ", "), "isrc": f.text("TSRC").strip().upper(),
            "duration": float(getattr(f, "duration", 0) or 0), "album": f.text("TALB")}


def first_artist(info) -> str:
    return strip_feat(info["artist"]).split(",")[0].split(" & ")[0].strip()


# =========================================================================== Bewerten
def score(info: dict, c: dict) -> float:
    """0–1: wie gut passt Kandidat c zur Datei? ISRC-Treffer = 1."""
    if info.get("isrc") and (c.get("isrc") or "").upper() == info["isrc"]:
        return 1.0
    ctitle, cmix = c.get("title", ""), c.get("mix", "")
    if not cmix:
        ctitle, cmix = split_title(ctitle)
    a, b = norm(strip_feat(info["title"])), norm(strip_feat(ctitle))
    ts = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    fa = norm(strip_feat(info["artist"]))
    names = [x for x in (c.get("artists") or []) if x]
    cand = [norm(x) for x in names] + [norm(", ".join(names))]
    as_ = max([difflib.SequenceMatcher(None, fa, x).ratio() for x in cand if x] + [0.0]) if fa else 0.5
    if fa and any(x and (x in fa or fa in x) for x in cand[:-1]):
        as_ = max(as_, 0.9)
    parts = [(ts, 0.5), (as_, 0.3)]
    if info.get("duration") and c.get("length"):
        d = abs(info["duration"] - float(c["length"]))
        parts.append((1.0 if d <= 3 else 0.7 if d <= 8 else 0.3 if d <= 20 else 0.0, 0.2))
    s = sum(v * w for v, w in parts) / sum(w for _v, w in parts)
    if info.get("mix"):
        s += 0.05 if norm(info["mix"]) == norm(cmix) else -0.05
    if fa and as_ < 0.5:          # anderer Künstler: gleicher Titel reicht nicht
        s *= 0.6
    if ts < 0.6:                  # anderer Titel: Künstler allein reicht nicht
        s *= 0.6
    return max(0.0, min(1.0, s))


def best(info: dict, cands: list) -> tuple[dict | None, float]:
    scored = sorted(((score(info, c), i, c) for i, c in enumerate(cands)), key=lambda x: (-x[0], x[1]))
    return (scored[0][2], scored[0][0]) if scored else (None, 0.0)


def mmss(v) -> float | None:
    """'6:12' → 372.0"""
    m = re.match(r"^\s*(\d+):(\d{2})(?::(\d{2}))?\s*$", v or "")
    if not m:
        return None
    if m.group(3):
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return int(m.group(1)) * 60 + int(m.group(2))


# =========================================================================== HTTP
class HttpError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


def retry_after(v) -> float:
    try:
        return max(0.0, min(30.0, float(v)))
    except (TypeError, ValueError):
        pass
    try:
        return max(0.0, min(30.0, email.utils.parsedate_to_datetime(str(v)).timestamp() - time.time()))
    except (TypeError, ValueError, IndexError, OverflowError):
        return 5.0


def http_get(url: str, headers: dict | None = None) -> tuple[int, dict, bytes]:
    """Eine GET-Anfrage → (Status, Kopfzeilen, Inhalt). In Tests ersetzbar."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as ex:
        return ex.code, dict(ex.headers or {}), ex.read() if hasattr(ex, "read") else b""
    except (urllib.error.URLError, OSError) as ex:
        raise HttpError(0, f"Keine Verbindung: {getattr(ex, 'reason', ex)}") from ex


class Throttle:
    """Mindestabstand je Dienst (z. B. MusicBrainz 1/s) – thread-sicher."""

    def __init__(self, intervals: dict):
        self.intervals = dict(intervals)
        self.last: dict = {}
        self.lock = threading.Lock()

    def wait(self, host: str):
        gap = next((v for k, v in self.intervals.items() if host == k or host.endswith("." + k)), 0.0)
        with self.lock:
            now = time.monotonic()
            t = self.last.get(host, 0.0) + gap
            if t > now:
                time.sleep(t - now)
            self.last[host] = time.monotonic()


class Client:
    """JSON-Abfragen mit Drosselung, Wiederholung bei 429/503 und verständlichen Fehlern."""

    def __init__(self, user_agent: str, intervals: dict, get=None, cancel=None):
        self.ua, self.th = user_agent, Throttle(intervals)
        self.get_fn = get or http_get
        self.cancel = cancel or (lambda: None)

    def raw(self, url: str, headers: dict | None = None, tries: int = 3) -> bytes:
        host = urllib.parse.urlparse(url).netloc
        h = {"User-Agent": self.ua, "Accept": "application/json", **(headers or {})}
        for n in range(tries):
            self.cancel()
            self.th.wait(host)
            st, hd, data = self.get_fn(url, h)
            if st in (429, 503) and n < tries - 1:
                time.sleep(retry_after({k.lower(): v for k, v in (hd or {}).items()}.get("retry-after", 2)))
                continue
            if st == 404:
                return b""
            if st >= 400:
                raise HttpError(st, f"{host}: HTTP {st}")
            return data
        raise HttpError(429, f"{host}: zu viele Anfragen – später nochmals versuchen")

    def json(self, url: str, headers: dict | None = None):
        data = self.raw(url, headers)
        if not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as ex:
            raise HttpError(-1, f"{urllib.parse.urlparse(url).netloc}: unerwartete Antwort") from ex
