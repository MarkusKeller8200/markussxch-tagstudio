"""Online-Metadaten (4.1.0, #6–#8): MusicBrainz (+ AcoustID), Deezer, iTunes, Discogs, Last.fm.

Alle Änderungen werden als Vorschläge zurückgegeben (Vorschau mit Häkchen, Rückgängig). Standard ist „nur leere
Felder füllen“ – passend zur Regel „spätere Programme ergänzen nur“. Je Feld ist nur der Wert der ersten Quelle
(Reihenfolge MusicBrainz → Discogs → Deezer → iTunes) vorausgewählt, weitere erscheinen als Alternative.

Schlüssel (Discogs-Token, Last.fm-, AcoustID-Schlüssel) liegen verschlüsselt in den Plugin-Daten (Windows: DPAPI),
werden nie protokolliert und nie in den Einstellungs-Export übernommen. Nur Standardbibliothek.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse

import onlinematch as om
from onlinematch import HttpError, MAYBE, SURE

try:
    from version import VERSION
except Exception:  # noqa: BLE001
    VERSION = "4"

USER_AGENT = f"TagStudio/{VERSION} ( https://github.com/MarkusKeller8200/markussxch-tagstudio )"
INTERVALS = {"musicbrainz.org": 1.05,          # MusicBrainz: im Mittel 1 Anfrage/s
             "coverartarchive.org": 0.25, "api.acoustid.org": 0.34,
             "api.deezer.com": 0.15,           # vorsichtig (Grenze nicht verlässlich dokumentiert)
             "itunes.apple.com": 3.1,          # iTunes Search: ca. 20 Anfragen/min
             "api.discogs.com": 1.05,          # Discogs mit Token: 60/min
             "ws.audioscrobbler.com": 0.25}
MB = "https://musicbrainz.org/ws/2"
SOURCES = [("mb", "MusicBrainz"), ("discogs", "Discogs"), ("deezer", "Deezer"), ("itunes", "iTunes")]
SOURCE_NAME = dict(SOURCES) | {"lastfm": "Last.fm", "acoustid": "AcoustID"}

# Gemeinsame Funktion: in Tests ersetzbar
http_get = om.http_get

ACTIONS = [
    {
        "id": "fetch", "label": "Online-Metadaten holen …", "where": "tagger", "run_label": "Suchen",
        "description": "Sucht die markierten Titel bei den gewählten Diensten und schlägt Ergänzungen vor. Du bestätigst danach jede Änderung.",
        "options": [
            {"type": "info", "label": "Quellen (Reihenfolge = Vorrang bei gleichen Feldern)"},
            {"key": "mb", "type": "check", "label": "MusicBrainz (frei)", "default": True},
            {"key": "acoustid", "type": "check", "label": "… dazu AcoustID-Fingerabdruck für Titel ohne brauchbare Tags (Schlüssel + fpcalc nötig)",
             "default": False, "show_if": {"mb": True}},
            {"key": "discogs", "type": "check", "label": "Discogs (eigener Token nötig)", "default": False},
            {"key": "deezer", "type": "check", "label": "Deezer (frei)", "default": True},
            {"key": "itunes", "type": "check", "label": "iTunes (frei, langsam: ca. 20 Abfragen pro Minute)", "default": False},
            {"key": "itunes_country", "type": "text", "label": "iTunes-Land (z. B. CH, DE, US)", "default": "CH",
             "show_if": {"itunes": True}},
            {"key": "lastfm", "type": "check", "label": "Last.fm-Tags als Vorschlag (eigener Schlüssel nötig, nie vorausgewählt)", "default": False},
            {"key": "mode", "type": "select", "label": "Vorhandene Werte",
             "choices": [["empty", "Nur leere Felder füllen (ergänzen)"], ["overwrite", "Überschreiben (Vorschau zeigt alt → neu)"]],
             "default": "empty"},
            {"key": "album", "type": "check", "label": "Album", "default": True},
            {"key": "date", "type": "select", "label": "Erscheinungsdatum",
             "choices": [["year", "Nur Jahr"], ["full", "Volles Datum (JJJJ-MM-TT)"], ["no", "Nicht übernehmen"]], "default": "year"},
            {"key": "label", "type": "check", "label": "Label (TPUB) und Katalognummer", "default": True},
            {"key": "isrc", "type": "check", "label": "ISRC", "default": True},
            {"key": "genre", "type": "check", "label": "Genre (Discogs: Stil, sonst Genre)", "default": True},
            {"key": "bpm", "type": "check", "label": "BPM (nur Deezer, wenn vorhanden)", "default": False},
            {"key": "track", "type": "check", "label": "Spur- und CD-Nummer", "default": False},
            {"key": "names", "type": "check", "label": "Titel und Künstler übernehmen", "default": False},
            {"key": "cover", "type": "select", "label": "Cover",
             "choices": [["missing", "Nur wenn keins vorhanden"], ["replace", "Ersetzen"], ["no", "Nicht übernehmen"]], "default": "missing"},
            {"key": "ids", "type": "check", "label": "IDs speichern (MusicBrainz, Deezer, iTunes, Discogs)", "default": True},
        ],
    },
    {
        "id": "keys", "label": "Schlüssel …", "where": "page", "run_label": "Speichern", "needs_selection": False,
        "description": "Eigene Schlüssel für Discogs, Last.fm und AcoustID. Leer lassen = unverändert. Die Schlüssel werden verschlüsselt gespeichert und nie angezeigt.",
        "options": [
            {"key": "discogs", "type": "password", "label": "Discogs: persönlicher Token (discogs.com → Einstellungen → Entwickler)"},
            {"key": "lastfm", "type": "password", "label": "Last.fm: API-Schlüssel (last.fm/api/account/create)"},
            {"key": "acoustid", "type": "password", "label": "AcoustID: Anwendungs-Schlüssel (acoustid.org/new-application)"},
            {"key": "fpcalc", "type": "text", "label": "Pfad zu fpcalc (leer = im Suchpfad suchen)"},
            {"key": "clear", "type": "select", "label": "Löschen",
             "choices": [["", "nichts löschen"], ["discogs", "Discogs-Token löschen"], ["lastfm", "Last.fm-Schlüssel löschen"],
                         ["acoustid", "AcoustID-Schlüssel löschen"], ["all", "alle löschen"]], "default": ""},
        ],
    },
    {"id": "test", "label": "Verbindungen testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft, ob die Dienste erreichbar und die Schlüssel gültig sind.", "options": []},
]


# =========================================================================== Schlüssel sicher ablegen
def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("Windows-Verschlüsselung (DPAPI) fehlgeschlagen.")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _keys_path(ctx):
    return os.path.join(ctx.data_dir, "keys.bin")


def load_keys(ctx) -> dict:
    try:
        with open(_keys_path(ctx), "rb") as fh:
            raw = fh.read()
        if raw.startswith(b"DPAPI"):
            raw = _dpapi(raw[5:], False)
        d = json.loads(raw.decode("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_keys(ctx, keys: dict):
    raw = json.dumps({k: v for k, v in keys.items() if v}).encode("utf-8")
    if sys.platform.startswith("win"):
        raw = b"DPAPI" + _dpapi(raw, True)
    path = _keys_path(ctx)
    with open(path, "wb") as fh:
        fh.write(raw)
    if not sys.platform.startswith("win"):
        os.chmod(path, 0o600)


def _client(ctx):
    return om.Client(USER_AGENT, INTERVALS, get=lambda url, h: http_get(url, h), cancel=ctx.check_cancel)


def _q(s):
    return urllib.parse.quote(s or "", safe="")


def _lucene(s):
    """Für MusicBrainz-Suchanfragen: Sonderzeichen entschärfen."""
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", s or "")


# =========================================================================== MusicBrainz (+ AcoustID)
def _mb_artists(credit) -> list:
    return [c.get("name") or (c.get("artist") or {}).get("name", "") for c in (credit or []) if isinstance(c, dict)]


_MB_SECONDARY = {"compilation", "dj-mix", "live", "soundtrack", "mixtape/street", "remix"}


def _mb_rel_rank(r) -> tuple:
    """Original-Veröffentlichung zuerst: offiziell, keine Kompilation/DJ-Mix/Live, Album/Single/EP, frühestes Datum."""
    rg = r.get("release-group") or {}
    sec = {x.lower() for x in rg.get("secondary-types") or []}
    prim = (rg.get("primary-type") or "").lower()
    return (r.get("status", "Official") != "Official", bool(sec & _MB_SECONDARY),
            prim not in ("album", "single", "ep", ""), r.get("date") or "9999")


def _mb_cand(rec) -> dict:
    rels = sorted(rec.get("releases") or [], key=_mb_rel_rank)
    rel = rels[0] if rels else {}
    return {"rank": _mb_rel_rank(rel)[:3] if rel else (True, True, True), "source": "mb", "id": rec.get("id", ""), "title": rec.get("title", ""), "artists": _mb_artists(rec.get("artist-credit")),
            "length": (rec.get("length") or 0) / 1000 or None, "isrc": ((rec.get("isrcs") or [""])[0] or "").upper(),
            "album": rel.get("title", ""), "date": rel.get("date", ""), "release_id": rel.get("id", ""),
            "rg_id": (rel.get("release-group") or {}).get("id", ""),
            "url": f"https://musicbrainz.org/recording/{rec.get('id', '')}"}


def mb_candidates(cl, info) -> list:
    if info["isrc"]:
        d = cl.json(f"{MB}/isrc/{_q(info['isrc'])}?inc=artists+releases+isrcs&fmt=json") or {}
        recs = d.get("recordings") or []
        if recs:
            out = [_mb_cand(r) for r in recs]
            for c in out:
                c["isrc"] = c["isrc"] or info["isrc"]
            return out
    q = f'recording:"{_lucene(info["title"])}"'
    if info["artist"]:
        q += f' AND artist:"{_lucene(om.first_artist(info))}"'
    d = cl.json(f"{MB}/recording?query={_q(q)}&limit=25&fmt=json") or {}
    out = [_mb_cand(r) for r in d.get("recordings") or []]
    # bei gleicher Bewertung gewinnt der frühere Kandidat → Aufnahmen mit Original-Veröffentlichung nach vorn
    return sorted(out, key=lambda c: c["rank"])


def mb_details(cl, c) -> dict:
    """Release nachladen: Label, Katalognummer, Datum, Spur/CD, IDs, Cover (Cover Art Archive)."""
    if not c.get("release_id"):
        return c
    r = cl.json(f"{MB}/release/{c['release_id']}?inc=labels+recordings+release-groups+artist-credits&fmt=json") or {}
    li = (r.get("label-info") or [{}])[0] or {}
    c["label"] = ((li.get("label") or {}).get("name") or "")
    c["catno"] = li.get("catalog-number") or ""
    c["date"] = r.get("date") or c.get("date", "")
    c["album"] = r.get("title") or c.get("album", "")
    c["album_artist"] = ", ".join(_mb_artists(r.get("artist-credit")))
    ids = {"TXXX:MusicBrainz Album Id": r.get("id", ""),
           "TXXX:MusicBrainz Release Group Id": (r.get("release-group") or {}).get("id", "") or c.get("rg_id", ""),
           "TXXX:MusicBrainz Album Artist Id": "/".join((a.get("artist") or {}).get("id", "") for a in r.get("artist-credit") or [])}
    for medium in r.get("media") or []:
        for t in medium.get("tracks") or []:
            if (t.get("recording") or {}).get("id") == c["id"]:
                ids["TXXX:MusicBrainz Release Track Id"] = t.get("id", "")
                c["track"] = f"{t.get('position') or t.get('number')}/{medium.get('track-count') or len(medium.get('tracks') or [])}"
                c["disc"] = f"{medium.get('position', 1)}/{len(r.get('media') or [])}"
    c["ids"] = {k: v for k, v in ids.items() if v}
    if (r.get("cover-art-archive") or {}).get("front"):
        c["cover"] = f"https://coverartarchive.org/release/{r['id']}/front-1200"
    return c


def fpcalc_path(keys) -> str:
    p = (keys.get("fpcalc") or "").strip()
    if p and os.path.isfile(p):
        return p
    return shutil.which("fpcalc") or shutil.which("fpcalc.exe") or ""


def acoustid_candidates(cl, ctx, f, keys) -> list:
    """Fingerabdruck mit fpcalc, Abfrage bei AcoustID → MusicBrainz-Aufnahmen."""
    exe = fpcalc_path(keys)
    if not exe or not keys.get("acoustid"):
        return []
    try:
        r = subprocess.run([exe, "-json", f.path], capture_output=True, text=True, timeout=120)
        fp = json.loads(r.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as ex:
        ctx.log(f"fpcalc: {ex}")
        return []
    if not fp.get("fingerprint"):
        return []
    url = (f"https://api.acoustid.org/v2/lookup?client={_q(keys['acoustid'])}&meta=recordings&format=json"
           f"&duration={int(fp.get('duration') or 0)}&fingerprint={_q(fp['fingerprint'])}")
    d = cl.json(url) or {}
    if d.get("status") != "ok":
        ctx.log(f"AcoustID: {(d.get('error') or {}).get('message', 'Fehler')}")
        return []
    out = []
    for res in sorted(d.get("results") or [], key=lambda x: -(x.get("score") or 0))[:3]:
        for rec in res.get("recordings") or []:
            if rec.get("id"):
                full = cl.json(f"{MB}/recording/{rec['id']}?inc=artists+releases+isrcs&fmt=json")
                if full:
                    c = _mb_cand(full)
                    c["fp_score"] = res.get("score") or 0
                    out.append(c)
    return out


# =========================================================================== Deezer
def _dz_cand(t) -> dict:
    title = t.get("title_short") or t.get("title", "")
    mix = (t.get("title_version") or "").strip(" ()[]")
    artists = [x.get("name", "") for x in t.get("contributors") or []] or [(t.get("artist") or {}).get("name", "")]
    alb = t.get("album") or {}
    return {"source": "deezer", "id": str(t.get("id", "")), "title": title, "mix": mix, "artists": artists,
            "length": t.get("duration") or None, "isrc": (t.get("isrc") or "").upper(), "album": alb.get("title", ""),
            "album_id": alb.get("id"), "date": t.get("release_date") or alb.get("release_date") or "",
            "bpm": t.get("bpm") or 0, "cover": alb.get("cover_xl") or alb.get("cover_big") or "",
            "track": str(t.get("track_position") or ""), "disc": str(t.get("disk_number") or ""),
            "url": t.get("link") or ""}


def _dz_ok(d):
    return isinstance(d, dict) and not d.get("error")


def deezer_candidates(cl, info) -> list:
    if info["isrc"]:
        d = cl.json(f"https://api.deezer.com/track/isrc:{_q(info['isrc'])}")
        if _dz_ok(d) and d.get("id"):
            return [_dz_cand(d)]
    q = f'track:"{info["title"]}"' + (f' artist:"{om.first_artist(info)}"' if info["artist"] else "")
    d = cl.json(f"https://api.deezer.com/search/track?q={_q(q)}&limit=10")
    out = [_dz_cand(t) for t in (d.get("data") or [])] if _dz_ok(d) else []
    if not out:                    # erweiterte Suche liefert nichts → einfache Suche
        q = " ".join(x for x in (om.first_artist(info), info["title"]) if x)
        d = cl.json(f"https://api.deezer.com/search?q={_q(q)}&limit=10")
        out = [_dz_cand(t) for t in (d.get("data") or [])] if _dz_ok(d) else []
    return out


def deezer_details(cl, c) -> dict:
    t = cl.json(f"https://api.deezer.com/track/{c['id']}") if c.get("id") else None
    if _dz_ok(t) and t.get("id"):
        c.update({k: v for k, v in _dz_cand(t).items() if v})
    a = cl.json(f"https://api.deezer.com/album/{c['album_id']}") if c.get("album_id") else None
    if _dz_ok(a):
        c["label"] = a.get("label") or ""
        g = [x.get("name", "") for x in ((a.get("genres") or {}).get("data") or [])]
        c["genre"] = g[0] if g else ""
        c["date"] = c.get("date") or a.get("release_date") or ""
        c["album_artist"] = (a.get("artist") or {}).get("name", "")
    if c.get("id"):
        c["ids"] = {"TXXX:DEEZER_TRACK_ID": c["id"]}
    return c


# =========================================================================== iTunes
def itunes_candidates(cl, info, country="CH") -> list:
    term = " ".join(x for x in (om.first_artist(info), info["title"]) if x)
    country = re.sub(r"[^A-Za-z]", "", country or "CH")[:2].upper() or "CH"
    d = cl.json(f"https://itunes.apple.com/search?term={_q(term)}&media=music&entity=song&limit=10&country={country}") or {}
    out = []
    for r in d.get("results") or []:
        title, mix = om.split_title(r.get("trackName", ""))
        cover = (r.get("artworkUrl100") or "").replace("100x100bb", "1400x1400bb")
        tn, tc, dn, dc = r.get("trackNumber"), r.get("trackCount"), r.get("discNumber"), r.get("discCount")
        out.append({"source": "itunes", "id": str(r.get("trackId", "")), "title": title, "mix": mix,
                    "artists": [r.get("artistName", "")], "length": (r.get("trackTimeMillis") or 0) / 1000 or None,
                    "album": r.get("collectionName", ""), "date": (r.get("releaseDate") or "")[:10],
                    "genre": r.get("primaryGenreName", ""), "cover": cover,
                    "track": f"{tn}/{tc}" if tn and tc else str(tn or ""), "disc": f"{dn}/{dc}" if dn and dc else str(dn or ""),
                    "ids": {"TXXX:ITUNES_TRACK_ID": str(r.get("trackId", ""))} if r.get("trackId") else {},
                    "url": r.get("trackViewUrl", "")})
    return out


# =========================================================================== Discogs
def _dc_name(s):
    return re.sub(r"\s\(\d+\)$", "", (s or "").strip())      # „Artist (2)“ → „Artist“


def discogs_candidates(cl, info, token) -> list:
    """Releases suchen und je Release den passenden Titel der Trackliste als Kandidat."""
    h = {"Authorization": f"Discogs token={token}"}
    q = f"https://api.discogs.com/database/search?type=release&per_page=5&track={_q(info['title'])}"
    if info["artist"]:
        q += f"&artist={_q(om.first_artist(info))}"
    d = cl.json(q, h) or {}
    out = []
    for res in (d.get("results") or [])[:3]:
        r = cl.json(f"https://api.discogs.com/releases/{res['id']}", h) or {}
        rel_artists = [_dc_name(a.get("name")) for a in r.get("artists") or []]
        labels = r.get("labels") or [{}]
        imgs = r.get("images") or []
        img = next((i.get("uri") for i in imgs if i.get("type") == "primary"), imgs[0].get("uri") if imgs else "")
        for t in r.get("tracklist") or []:
            if t.get("type_", "track") != "track":
                continue
            title, mix = om.split_title(t.get("title", ""))
            out.append({"source": "discogs", "id": str(r.get("id", "")), "title": title, "mix": mix,
                        "artists": [_dc_name(a.get("name")) for a in t.get("artists") or []] or rel_artists,
                        "length": om.mmss(t.get("duration")), "album": r.get("title", ""),
                        "album_artist": ", ".join(rel_artists),
                        "label": _dc_name(labels[0].get("name")),
                        "catno": "" if (labels[0].get("catno") or "").strip().lower() == "none" else (labels[0].get("catno") or "").strip(),
                        "date": r.get("released") or str(r.get("year") or ""),
                        "genre": ", ".join((r.get("styles") or r.get("genres") or [])[:2]), "cover": img,
                        "track": t.get("position", ""),
                        "ids": {"TXXX:DISCOGS_RELEASE_ID": str(r.get("id", ""))}, "url": r.get("uri", "")})
    return out


# =========================================================================== Last.fm
def lastfm_tags(cl, info, key) -> list:
    url = ("https://ws.audioscrobbler.com/2.0/?method=track.gettoptags&autocorrect=1&format=json"
           f"&artist={_q(om.first_artist(info))}&track={_q(info['title'])}&api_key={_q(key)}")
    d = cl.json(url) or {}
    if d.get("error"):
        return []
    tags = (d.get("toptags") or {}).get("tag") or []
    tags = tags if isinstance(tags, list) else [tags]
    return [t.get("name", "") for t in tags if t.get("name") and int(t.get("count") or 0) >= 10][:5]


# =========================================================================== Vorschläge
def _field_values(c, opts) -> list:
    """(Schlüssel, Wert, Beschriftung, gewünscht) für einen Treffer."""
    out = []
    names = bool(opts.get("names"))
    title = c.get("title", "")
    if c.get("mix"):
        title = f"{title} ({c['mix']})"
    out.append(("TIT2", title, "Titel", names))
    out.append(("TPE1", ", ".join(a for a in c.get("artists") or [] if a), "Künstler", names))
    out.append(("TALB", c.get("album", ""), "Album", opts.get("album")))
    date, dmode = c.get("date") or "", opts.get("date", "year")
    if dmode == "full" and re.match(r"\d{4}-\d{2}-\d{2}", date):
        out.append(("TDRC", date[:10], "Datum", True))
    elif date[:4].isdigit():
        out.append(("TDRC", date[:4], "Jahr", dmode != "no"))
    out.append(("TPUB", c.get("label", ""), "Label", opts.get("label")))
    out.append(("TXXX:CATALOGNUMBER", c.get("catno", ""), "Katalognummer", opts.get("label")))
    out.append(("TSRC", c.get("isrc", ""), "ISRC", opts.get("isrc")))
    out.append(("TCON", c.get("genre", ""), "Genre", opts.get("genre")))
    if c.get("bpm"):
        out.append(("TBPM", str(int(round(float(c["bpm"])))), "BPM", opts.get("bpm")))
    out.append(("TRCK", c.get("track", ""), "Spur", opts.get("track")))
    out.append(("TPOS", c.get("disc", ""), "CD", opts.get("track")))
    for k, v in (c.get("ids") or {}).items():
        out.append((k, v, k.split(":", 1)[1], opts.get("ids")))
    return out


def _same(key, old, new):
    o, n = (old or "").strip(), (new or "").strip()
    if o.lower() == n.lower():
        return True
    if key == "TDRC":
        return len(n) == 4 and o[:4] == n
    if key in ("TPE1", "TIT2", "TALB", "TPUB"):
        return om.norm(o) == om.norm(n)
    if key in ("TRCK", "TPOS"):
        return o.split("/")[0].lstrip("0") == n.split("/")[0].lstrip("0") and ("/" not in n or o == n)
    return False


def propose_file(ctx, cl, f, hits, opts, group, stats, auth=None):
    """hits: [(Quelle, Kandidat, Treffer-Score)] in Vorrang-Reihenfolge. Je Feld nur der erste Wert vorausgewählt."""
    empty_only = opts.get("mode", "empty") == "empty"
    taken = set()
    for src, c, s in hits:
        sure = s >= SURE
        note = f"{SOURCE_NAME[src]}: {', '.join(c.get('artists') or [])} – {c.get('title', '')}" + \
               (f" ({c['mix']})" if c.get("mix") else "") + f" · {round(s * 100)} %" + ("" if sure else " · unsicher")
        for key, val, label, wanted in _field_values(c, opts):
            val = (val or "").strip()
            if not val:
                continue
            cur = f.text(key).strip()
            lab = f"{label} ({SOURCE_NAME[src]})"
            if cur == val:
                if key not in taken:
                    stats["same"] += 1
                    ctx.propose(f, key, val, lab, note=note, checked=False, group=group, hint="gleich", show_same=True)
                taken.add(key)
                continue
            first = key not in taken
            taken.add(key)
            if not first:
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, hint="Alternative – bei Bedarf anhaken")
            elif not wanted:
                stats["off"] += 1
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, hint="in den Optionen abgewählt")
            elif cur and _same(key, cur, val):
                stats["same"] += 1
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, hint="gleicher Wert, andere Schreibweise")
            elif cur and empty_only:
                stats["filled"] += 1
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, hint="schon gefüllt – nur ergänzen")
            else:
                ctx.propose(f, key, val, lab, note=note, checked=sure, group=group)
    # Cover: aus der ersten Quelle, die eins hat
    cov = opts.get("cover", "missing")
    has = f.get("APIC:3") is not None
    for src, c, s in hits:
        url = c.get("cover")
        if not url:
            continue
        if cov == "no" or (cov == "missing" and has):
            ctx.propose(f, "APIC:3", f"Cover von {SOURCE_NAME[src]} verfügbar", "Cover", checked=False, kind="cover",
                        data=None, group=group, hint="Datei hat schon ein Cover – Option Cover → „Ersetzen“ lädt es" if has
                        else "Option Cover → „Nur wenn keins vorhanden“ lädt es")
            break
        try:
            data = cl.raw(url, (auth or {}).get(src))
        except HttpError as ex:
            ctx.log(f"Cover ({SOURCE_NAME[src]}): {ex}")
            continue
        if data[:3] in (b"\xff\xd8\xff", b"\x89PN"):
            ctx.propose(f, "APIC:3", f"Cover von {SOURCE_NAME[src]}", "Cover", checked=s >= SURE and not has, kind="cover",
                        data=data, group=group, hint="ersetzt vorhandenes Cover" if has else "")
            break


# =========================================================================== Aktionen
def status(ctx):
    k = load_keys(ctx)
    have = [n for n, lab in (("discogs", "Discogs"), ("lastfm", "Last.fm"), ("acoustid", "AcoustID")) if k.get(n)]
    fp = "fpcalc gefunden" if fpcalc_path(k) else "fpcalc nicht gefunden"
    return ("Schlüssel: " + (", ".join(SOURCE_NAME[n] for n in have) if have else "keine") +
            f" · {fp} · MusicBrainz, Deezer, iTunes ohne Schlüssel.")


def run(action, ctx, files, opts):
    if action == "keys":
        keys = load_keys(ctx)
        clear = opts.get("clear") or ""
        for n in ("discogs", "lastfm", "acoustid"):
            if clear in (n, "all"):
                keys.pop(n, None)
            elif (opts.get(n) or "").strip():
                keys[n] = opts[n].strip()
        if "fpcalc" in opts:
            keys["fpcalc"] = (opts.get("fpcalc") or "").strip()
        save_keys(ctx, keys)
        return {"message": status(ctx)}
    if action == "test":
        cl, keys, lines = _client(ctx), load_keys(ctx), []
        checks = [("MusicBrainz", f"{MB}/recording?query=recording:test&limit=1&fmt=json", None),
                  ("Deezer", "https://api.deezer.com/search/track?q=test&limit=1", None),
                  ("iTunes", "https://itunes.apple.com/search?term=test&entity=song&limit=1", None)]
        if keys.get("discogs"):
            checks.append(("Discogs", "https://api.discogs.com/oauth/identity", {"Authorization": f"Discogs token={keys['discogs']}"}))
        if keys.get("lastfm"):
            checks.append(("Last.fm", f"https://ws.audioscrobbler.com/2.0/?method=tag.getinfo&tag=house&format=json&api_key={_q(keys['lastfm'])}", None))
        ok = 0
        for name, url, h in checks:
            try:
                d = cl.json(url, h)
                bad = isinstance(d, dict) and d.get("error") and name == "Last.fm"
                lines.append(f"{name}: {'Schlüssel ungültig' if bad else 'in Ordnung'}")
                ok += not bad
            except HttpError as ex:
                lines.append(f"{name}: {ex}")
        for ln in lines:
            ctx.log(ln)
        return {"message": f"{ok} von {len(checks)} Diensten erreichbar. " + " · ".join(lines)}
    if action != "fetch":
        raise ValueError(f"Unbekannte Aktion: {action}")

    keys = load_keys(ctx)
    cl = _client(ctx)
    srcs = [s for s, _n in SOURCES if opts.get(s)]
    if opts.get("discogs") and not keys.get("discogs"):
        ctx.log("Discogs übersprungen: kein Token gespeichert (Aktion „Schlüssel …“).")
        srcs.remove("discogs")
    use_lastfm = bool(opts.get("lastfm") and keys.get("lastfm"))
    if opts.get("lastfm") and not keys.get("lastfm"):
        ctx.log("Last.fm übersprungen: kein Schlüssel gespeichert.")
    use_fp = bool(opts.get("mb") and opts.get("acoustid"))
    if use_fp and not (keys.get("acoustid") and fpcalc_path(keys)):
        ctx.log("AcoustID übersprungen: " + ("kein Schlüssel" if not keys.get("acoustid") else "fpcalc nicht gefunden") + ".")
        use_fp = False
    if not srcs and not use_lastfm:
        raise ValueError("Keine Quelle gewählt (oder für die gewählten fehlt der Schlüssel).")
    found = unsure = missing = 0
    stats = {"same": 0, "filled": 0, "off": 0}
    for i, f in enumerate(files):
        name = os.path.basename(f.path)
        ctx.progress(i, len(files), f"Suche {name}")
        info = om.file_info(f)
        hits = []
        for src in srcs:
            try:
                if src == "mb":
                    cands = mb_candidates(cl, info) if info["title"] else []
                    c, s = om.best(info, cands)
                    if use_fp and (not c or s < MAYBE):
                        fpc = acoustid_candidates(cl, ctx, f, keys)
                        if fpc:
                            fc = max(fpc, key=lambda x: x.get("fp_score", 0))
                            c, s = fc, max(om.score(info, fc), min(1.0, fc.get("fp_score", 0)))
                    if c and s >= MAYBE:
                        c = mb_details(cl, c)
                elif src == "deezer":
                    c, s = om.best(info, deezer_candidates(cl, info)) if info["title"] else (None, 0)
                    if c and s >= MAYBE:
                        c = deezer_details(cl, c)
                        s = max(s, om.score(info, c))
                elif src == "itunes":
                    c, s = om.best(info, itunes_candidates(cl, info, opts.get("itunes_country", "CH"))) if info["title"] else (None, 0)
                else:
                    c, s = om.best(info, discogs_candidates(cl, info, keys["discogs"])) if info["title"] else (None, 0)
            except HttpError as ex:
                if ex.status in (0, 429):
                    raise RuntimeError(str(ex)) from ex
                ctx.log(f"{name} · {SOURCE_NAME[src]}: {ex}")
                continue
            if c and s >= MAYBE:
                hits.append((src, c, s))
                ctx.log(f"{name} · {SOURCE_NAME[src]}: {', '.join(c.get('artists') or [])} – {c.get('title', '')} ({round(s * 100)} %)")
            else:
                ctx.log(f"{name} · {SOURCE_NAME[src]}: nicht gefunden" + (f" (bester Kandidat {round(s * 100)} %)" if c else ""))
        if use_lastfm and info["title"]:
            try:
                tags = lastfm_tags(cl, info, keys["lastfm"])
            except HttpError as ex:
                tags = []
                ctx.log(f"{name} · Last.fm: {ex}")
            if tags:
                ctx.propose(f, "TXXX:LASTFM_TAGS", "; ".join(tags), "Last.fm-Tags", note="Last.fm: Vorschlag", checked=False,
                            group=name, hint="Vorschlag – nie vorausgewählt")
                ctx.propose(f, "TCON", tags[0], "Genre (Last.fm)", note="Last.fm: Vorschlag", checked=False,
                            group=name, hint="Vorschlag aus den Last.fm-Tags")
        if hits:
            best_s = max(s for _src, _c, s in hits)
            found += best_s >= SURE
            unsure += best_s < SURE
            propose_file(ctx, cl, f, hits, opts, name, stats,
                         auth={"discogs": {"Authorization": f"Discogs token={keys['discogs']}"}} if keys.get("discogs") else None)
        else:
            missing += 1
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{found} sicher gefunden" + (f", {unsure} unsicher (nicht vorausgewählt)" if unsure else "") + \
          (f", {missing} nicht gefunden" if missing else "")
    if not ctx.proposals:
        return {"message": f"{msg}. Keine Felder zum Ergänzen."}
    n = sum(1 for p in ctx.proposals if p["checked"])
    m = sum(1 for p in ctx.proposals if not p["same"])
    extra = ""
    if stats["same"]:
        extra += f" {stats['same']} Feld(er) stimmen bereits (grau)."
    if stats["filled"]:
        extra += f" {stats['filled']} gefüllte Feld(er) mit anderem Wert gelistet, nicht angehakt (nur ergänzen)."
    return {"message": f"{msg}. {m} mögliche Änderung(en), {n} vorausgewählt." + extra}
