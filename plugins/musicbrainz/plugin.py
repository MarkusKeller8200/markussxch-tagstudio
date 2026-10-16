"""MusicBrainz (#204, aus „Online-Metadaten“ herausgelöst): Aufnahmen über ISRC oder Titel/Künstler, Details aus der
Veröffentlichung, Cover aus dem Cover Art Archive. Ohne Schlüssel, höchstens etwa 1 Anfrage/s. Nur Standardbibliothek."""
import re

import onlinematch as om
import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "mb", "name": "MusicBrainz", "order": 10, "role": "metadata"}
MB = "https://musicbrainz.org/ws/2"
INTERVALS = {"musicbrainz.org": 1.05, "coverartarchive.org": 0.25}

ACTIONS = [{"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
            "description": "Prüft, ob MusicBrainz erreichbar ist.", "options": []}]


def _lucene(s):
    """Für MusicBrainz-Suchanfragen: Sonderzeichen entschärfen."""
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", s or "")


def _artists(credit) -> list:
    return [c.get("name") or (c.get("artist") or {}).get("name", "") for c in (credit or []) if isinstance(c, dict)]


_SECONDARY = {"compilation", "dj-mix", "live", "soundtrack", "mixtape/street", "remix"}


def _rel_rank(r) -> tuple:
    """Original-Veröffentlichung zuerst: offiziell, keine Kompilation/DJ-Mix/Live, Album/Single/EP, frühestes Datum."""
    rg = r.get("release-group") or {}
    sec = {x.lower() for x in rg.get("secondary-types") or []}
    prim = (rg.get("primary-type") or "").lower()
    return (r.get("status", "Official") != "Official", bool(sec & _SECONDARY),
            prim not in ("album", "single", "ep", ""), r.get("date") or "9999")


def cand(rec) -> dict:
    rels = sorted(rec.get("releases") or [], key=_rel_rank)
    rel = rels[0] if rels else {}
    return {"rank": _rel_rank(rel)[:3] if rel else (True, True, True), "source": "mb", "source_name": "MusicBrainz",
            "id": rec.get("id", ""), "title": rec.get("title", ""), "artists": _artists(rec.get("artist-credit")),
            "length": (rec.get("length") or 0) / 1000 or None, "isrc": ((rec.get("isrcs") or [""])[0] or "").upper(),
            "album": rel.get("title", ""), "date": rel.get("date", ""), "release_id": rel.get("id", ""),
            "rg_id": (rel.get("release-group") or {}).get("id", ""),
            "url": f"https://musicbrainz.org/recording/{rec.get('id', '')}"}


def candidates(ctx, cl, info, opts=None) -> list:
    if not info["title"] and not info.get("isrc"):
        return []
    if info.get("isrc"):
        d = cl.json(f"{MB}/isrc/{sk.q(info['isrc'])}?inc=artists+releases+isrcs&fmt=json") or {}
        recs = d.get("recordings") or []
        if recs:
            out = [cand(r) for r in recs]
            for c in out:
                c["isrc"] = c["isrc"] or info["isrc"]
            return out
    if not info["title"]:
        return []
    q = f'recording:"{_lucene(info["title"])}"'
    if info["artist"]:
        q += f' AND artist:"{_lucene(om.first_artist(info))}"'
    d = cl.json(f"{MB}/recording?query={sk.q(q)}&limit=25&fmt=json") or {}
    out = [cand(r) for r in d.get("recordings") or []]
    # bei gleicher Bewertung gewinnt der frühere Kandidat → Aufnahmen mit Original-Veröffentlichung nach vorn
    return sorted(out, key=lambda c: c["rank"])


def recording(cl, mbid) -> dict | None:
    full = cl.json(f"{MB}/recording/{mbid}?inc=artists+releases+isrcs&fmt=json")
    return cand(full) if full else None


def details(ctx, cl, c) -> dict:
    """Release nachladen: Label, Katalognummer, Datum, Spur/CD, IDs, Cover (Cover Art Archive)."""
    if not c.get("release_id"):
        return c
    r = cl.json(f"{MB}/release/{c['release_id']}?inc=labels+recordings+release-groups+artist-credits&fmt=json") or {}
    li = (r.get("label-info") or [{}])[0] or {}
    c["label"] = ((li.get("label") or {}).get("name") or "")
    c["catno"] = li.get("catalog-number") or ""
    c["date"] = r.get("date") or c.get("date", "")
    c["album"] = r.get("title") or c.get("album", "")
    c["album_artist"] = ", ".join(_artists(r.get("artist-credit")))
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


def check(ctx, cl):
    cl.json(f"{MB}/recording?query=recording:test&limit=1&fmt=json")
    return True, "in Ordnung"


def client(ctx):
    return sk.client(ctx, INTERVALS)


def test_query(ctx, info):
    """Testabfrage ohne Track: gleiche Suche wie in „Online-Metadaten“; der beste Treffer mit Details."""
    cl = client(ctx)
    cands = candidates(ctx, cl, info)
    ctx.log(("ISRC " + info["isrc"] + ", sonst " if info.get("isrc") else "") + f"Suche Titel + Künstler: {len(cands)} Aufnahmen")
    c, s = om.best(info, cands)
    if c and s >= om.MAYBE:
        details(ctx, cl, c)
        c["extra"] = " · ".join(x for x in (c.get("catno", ""), f"{len(c.get('ids') or {})} IDs" if c.get("ids") else "",
                                            "Cover vorhanden" if c.get("cover") else "") if x)
    return cands


def status(ctx):
    return "Ohne Schlüssel · höchstens etwa 1 Anfrage/s."


def run(action, ctx, files, opts):
    if action != "test":
        raise ValueError(f"Unbekannte Aktion: {action}")
    try:
        check(ctx, client(ctx))
        return {"message": "MusicBrainz ist erreichbar."}
    except HttpError as ex:
        return {"message": f"MusicBrainz nicht erreichbar: {ex}"}
