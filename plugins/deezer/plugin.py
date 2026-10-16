"""Deezer (#204, aus „Online-Metadaten“ herausgelöst; auch Quelle für „Entdecken“). Öffentliche API ohne Anmeldung.
Nur Standardbibliothek."""
import urllib.parse

import onlinematch as om
import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "deezer", "name": "Deezer", "order": 30, "role": "metadata"}
API = "https://api.deezer.com"
INTERVALS = {"api.deezer.com": 0.15}

ACTIONS = [{"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
            "description": "Prüft, ob Deezer erreichbar ist.", "options": []}]


def client(ctx):
    return sk.client(ctx, INTERVALS)


def ok(d):
    return isinstance(d, dict) and not d.get("error")


def get_json(ctx, path, cl=None, **params):
    """Für „Entdecken“: GET {API}{path}?params → dict (Fehlerantworten von Deezer → {})."""
    cl = cl or client(ctx)
    d = cl.json(API + path + ("?" + urllib.parse.urlencode(params) if params else ""))
    return d if ok(d) else {}


def _cand(t) -> dict:
    title = t.get("title_short") or t.get("title", "")
    mix = (t.get("title_version") or "").strip(" ()[]")
    artists = [x.get("name", "") for x in t.get("contributors") or []] or [(t.get("artist") or {}).get("name", "")]
    alb = t.get("album") or {}
    return {"source": "deezer", "source_name": "Deezer", "id": str(t.get("id", "")), "title": title, "mix": mix,
            "artists": artists, "length": t.get("duration") or None, "isrc": (t.get("isrc") or "").upper(),
            "album": alb.get("title", ""), "album_id": alb.get("id"),
            "date": t.get("release_date") or alb.get("release_date") or "",
            "bpm": t.get("bpm") or 0, "cover": alb.get("cover_xl") or alb.get("cover_big") or "",
            "track": str(t.get("track_position") or ""), "disc": str(t.get("disk_number") or ""),
            "url": t.get("link") or ""}


def candidates(ctx, cl, info, opts=None) -> list:
    if info.get("isrc"):
        d = cl.json(f"{API}/track/isrc:{sk.q(info['isrc'])}")
        if ok(d) and d.get("id"):
            return [_cand(d)]
    if not info["title"]:
        return []
    q = f'track:"{info["title"]}"' + (f' artist:"{om.first_artist(info)}"' if info["artist"] else "")
    d = cl.json(f"{API}/search/track?q={sk.q(q)}&limit=10")
    out = [_cand(t) for t in (d.get("data") or [])] if ok(d) else []
    if not out:                    # erweiterte Suche liefert nichts → einfache Suche
        q = " ".join(x for x in (om.first_artist(info), info["title"]) if x)
        d = cl.json(f"{API}/search?q={sk.q(q)}&limit=10")
        out = [_cand(t) for t in (d.get("data") or [])] if ok(d) else []
    return out


def details(ctx, cl, c) -> dict:
    t = cl.json(f"{API}/track/{c['id']}") if c.get("id") else None
    if ok(t) and t.get("id"):
        c.update({k: v for k, v in _cand(t).items() if v})
    a = cl.json(f"{API}/album/{c['album_id']}") if c.get("album_id") else None
    if ok(a):
        c["label"] = a.get("label") or ""
        g = [x.get("name", "") for x in ((a.get("genres") or {}).get("data") or [])]
        c["genre"] = g[0] if g else ""
        c["date"] = c.get("date") or a.get("release_date") or ""
        c["album_artist"] = (a.get("artist") or {}).get("name", "")
    if c.get("id"):
        c["ids"] = {"TXXX:DEEZER_TRACK_ID": c["id"]}
    return c


def check(ctx, cl):
    cl.json(f"{API}/search/track?q=test&limit=1")
    return True, "in Ordnung"


def test_query(ctx, info):
    cl = client(ctx)
    cands = candidates(ctx, cl, info)
    ctx.log(("ISRC " + info["isrc"] + ", sonst " if info.get("isrc") else "") + f"Suche: {len(cands)} Titel")
    c, s = om.best(info, cands)
    if c and s >= om.MAYBE:
        details(ctx, cl, c)
        c["extra"] = " · ".join(x for x in (f"{int(round(float(c['bpm'])))} BPM" if c.get("bpm") else "",
                                            c.get("genre", "")) if x)
    return cands


def status(ctx):
    return "Ohne Schlüssel."


def run(action, ctx, files, opts):
    if action != "test":
        raise ValueError(f"Unbekannte Aktion: {action}")
    try:
        check(ctx, client(ctx))
        return {"message": "Deezer ist erreichbar."}
    except HttpError as ex:
        return {"message": f"Deezer nicht erreichbar: {ex}"}
