"""Discogs (#204, aus „Online-Metadaten“ herausgelöst). Eigener persönlicher Token (verschlüsselt gespeichert).
Nur Standardbibliothek."""
import re

import onlinematch as om
import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "discogs", "name": "Discogs", "order": 20, "role": "metadata"}
API = "https://api.discogs.com"
INTERVALS = {"api.discogs.com": 1.05}
KEYS = ("discogs",)

ACTIONS = [
    {"id": "keys", "label": "Schlüssel …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Persönlicher Discogs-Token. Leer lassen = unverändert. Wird verschlüsselt gespeichert und nie angezeigt.",
     "options": [
         {"type": "info", "title": "Discogs",
          "label": "Kostenlos, nur ein Discogs-Konto nötig. 1. Bei discogs.com anmelden. 2. Einstellungen › Entwickler "
                   "öffnen. 3. „Neuen Token generieren“ klicken. 4. Den Token kopieren und unten einfügen.",
          "links": [["Discogs: Entwickler-Einstellungen", "https://www.discogs.com/settings/developers"],
                    ["Konto anlegen", "https://accounts.discogs.com/register"]]},
         {"key": "discogs", "type": "password", "label": "Discogs: persönlicher Token"},
         {"key": "clear", "type": "check", "label": "Gespeicherten Token löschen", "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft Erreichbarkeit und Token.", "options": []},
]


def token(ctx) -> str:
    return sk.load_keys(ctx, KEYS).get("discogs", "")


def ready(ctx):
    return (True, "") if token(ctx) else (False, "kein Token gespeichert (Plugin Discogs › „Schlüssel …“)")


def headers(ctx) -> dict:
    t = token(ctx)
    return {"Authorization": f"Discogs token={t}"} if t else {}


def auth(ctx):
    return {"headers": headers(ctx)}


cover_headers = headers


def client(ctx):
    return sk.client(ctx, INTERVALS)


def _name(s):
    return re.sub(r"\s\(\d+\)$", "", (s or "").strip())      # „Artist (2)“ → „Artist“


def candidates(ctx, cl, info, opts=None) -> list:
    """Releases suchen und je Release den passenden Titel der Trackliste als Kandidat."""
    if not info["title"]:
        return []
    h = headers(ctx)
    q = f"{API}/database/search?type=release&per_page=5&track={sk.q(info['title'])}"
    if info["artist"]:
        q += f"&artist={sk.q(om.first_artist(info))}"
    d = cl.json(q, h) or {}
    out = []
    for res in (d.get("results") or [])[:3]:
        r = cl.json(f"{API}/releases/{res['id']}", h) or {}
        rel_artists = [_name(a.get("name")) for a in r.get("artists") or []]
        labels = r.get("labels") or [{}]
        imgs = r.get("images") or []
        img = next((i.get("uri") for i in imgs if i.get("type") == "primary"), imgs[0].get("uri") if imgs else "")
        for t in r.get("tracklist") or []:
            if t.get("type_", "track") != "track":
                continue
            title, mix = om.split_title(t.get("title", ""))
            catno = (labels[0].get("catno") or "").strip()
            out.append({"source": "discogs", "source_name": "Discogs", "id": str(r.get("id", "")), "title": title, "mix": mix,
                        "artists": [_name(a.get("name")) for a in t.get("artists") or []] or rel_artists,
                        "length": om.mmss(t.get("duration")), "album": r.get("title", ""),
                        "album_artist": ", ".join(rel_artists),
                        "label": _name(labels[0].get("name")), "catno": "" if catno.lower() == "none" else catno,
                        "date": r.get("released") or str(r.get("year") or ""),
                        "genre": ", ".join((r.get("styles") or r.get("genres") or [])[:2]), "cover": img,
                        "track": t.get("position", ""),
                        "ids": {"TXXX:DISCOGS_RELEASE_ID": str(r.get("id", ""))}, "url": r.get("uri", ""),
                        "extra": ", ".join((r.get("styles") or r.get("genres") or [])[:2])})
    return out


def details(ctx, cl, c) -> dict:
    return c                       # Release ist schon vollständig geladen


def check(ctx, cl):
    if not token(ctx):
        return False, "kein Token"
    d = cl.json(f"{API}/oauth/identity", headers(ctx)) or {}
    return bool(d.get("username")), "in Ordnung" if d.get("username") else "Token ungültig"


def test_query(ctx, info):
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Discogs: {why}.")
    cands = candidates(ctx, client(ctx), info)
    ctx.log(f"Suche Veröffentlichungen: {len({c['id'] for c in cands})} geladen, {len(cands)} Titel in den Tracklisten")
    return cands


def status(ctx):
    return "Token gespeichert" if token(ctx) else "kein Token – unter „Schlüssel …“ eintragen"


def run(action, ctx, files, opts):
    if action == "keys":
        sk.keys_action(ctx, opts, KEYS)
        return {"message": status(ctx)}
    if action == "test":
        try:
            ok, why = check(ctx, client(ctx))
            return {"message": f"Discogs: {why}"}
        except HttpError as ex:
            return {"message": f"Discogs nicht erreichbar: {ex}"}
    raise ValueError(f"Unbekannte Aktion: {action}")
