"""iTunes Search API (#204, aus „Online-Metadaten“ herausgelöst). Ohne Anmeldung, etwa 20 Abfragen/min.
Nur Standardbibliothek."""
import re

import onlinematch as om
import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "itunes", "name": "iTunes", "order": 40, "role": "metadata"}
API = "https://itunes.apple.com"
INTERVALS = {"itunes.apple.com": 3.1}

ACTIONS = [{"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
            "description": "Prüft, ob iTunes erreichbar ist.", "options": []}]


def client(ctx):
    return sk.client(ctx, INTERVALS)


def candidates(ctx, cl, info, opts=None) -> list:
    if not info["title"]:
        return []
    term = " ".join(x for x in (om.first_artist(info), info["title"]) if x)
    country = re.sub(r"[^A-Za-z]", "", (opts or {}).get("itunes_country") or "CH")[:2].upper() or "CH"
    d = cl.json(f"{API}/search?term={sk.q(term)}&media=music&entity=song&limit=10&country={country}") or {}
    out = []
    for r in d.get("results") or []:
        title, mix = om.split_title(r.get("trackName", ""))
        cover = (r.get("artworkUrl100") or "").replace("100x100bb", "1400x1400bb")
        tn, tc, dn, dc = r.get("trackNumber"), r.get("trackCount"), r.get("discNumber"), r.get("discCount")
        out.append({"source": "itunes", "source_name": "iTunes", "id": str(r.get("trackId", "")), "title": title, "mix": mix,
                    "artists": [r.get("artistName", "")], "length": (r.get("trackTimeMillis") or 0) / 1000 or None,
                    "album": r.get("collectionName", ""), "date": (r.get("releaseDate") or "")[:10],
                    "genre": r.get("primaryGenreName", ""), "cover": cover,
                    "track": f"{tn}/{tc}" if tn and tc else str(tn or ""), "disc": f"{dn}/{dc}" if dn and dc else str(dn or ""),
                    "ids": {"TXXX:ITUNES_TRACK_ID": str(r.get("trackId", ""))} if r.get("trackId") else {},
                    "url": r.get("trackViewUrl", ""), "extra": r.get("primaryGenreName", "")})
    return out


def details(ctx, cl, c) -> dict:
    return c                       # die Suche liefert schon alles


def check(ctx, cl):
    cl.json(f"{API}/search?term=test&entity=song&limit=1")
    return True, "in Ordnung"


def test_query(ctx, info):
    cands = candidates(ctx, client(ctx), info, {"itunes_country": "CH"})
    ctx.log(f"Suche (Land CH): {len(cands)} Titel")
    return cands


def status(ctx):
    return "Ohne Schlüssel · etwa 20 Abfragen pro Minute."


def run(action, ctx, files, opts):
    if action != "test":
        raise ValueError(f"Unbekannte Aktion: {action}")
    try:
        check(ctx, client(ctx))
        return {"message": "iTunes ist erreichbar."}
    except HttpError as ex:
        return {"message": f"iTunes nicht erreichbar: {ex}"}
