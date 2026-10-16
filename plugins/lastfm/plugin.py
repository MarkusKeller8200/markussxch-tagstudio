"""Last.fm (#204, aus „Online-Metadaten“ herausgelöst): Tags als Vorschlag. Eigener API-Schlüssel (verschlüsselt).
Nur Standardbibliothek."""
import onlinematch as om
import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "lastfm", "name": "Last.fm", "order": 50, "role": "tags"}
API = "https://ws.audioscrobbler.com/2.0/"
INTERVALS = {"ws.audioscrobbler.com": 0.25}
KEYS = ("lastfm",)

ACTIONS = [
    {"id": "keys", "label": "Schlüssel …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Eigener Last.fm-API-Schlüssel. Leer lassen = unverändert. Wird verschlüsselt gespeichert und nie angezeigt.",
     "options": [
         {"type": "info", "title": "Last.fm",
          "label": "Kostenlos mit Last.fm-Konto. 1. Anmelden. 2. „API-Konto erstellen“ öffnen. 3. Kontakt-E-Mail, "
                   "Anwendungsname (z. B. TagStudio) und kurze Beschreibung eintragen, Callback-URL und Homepage leer "
                   "lassen, absenden. 4. Den „API key“ kopieren (nicht das „Shared secret“) und unten einfügen.",
          "links": [["Last.fm: API-Konto erstellen", "https://www.last.fm/api/account/create"],
                    ["Meine API-Konten", "https://www.last.fm/api/accounts"]]},
         {"key": "lastfm", "type": "password", "label": "Last.fm: API-Schlüssel"},
         {"key": "clear", "type": "check", "label": "Gespeicherten Schlüssel löschen", "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft Erreichbarkeit und Schlüssel.", "options": []},
]


def key(ctx) -> str:
    return sk.load_keys(ctx, KEYS).get("lastfm", "")


def ready(ctx):
    return (True, "") if key(ctx) else (False, "kein Schlüssel gespeichert (Plugin Last.fm › „Schlüssel …“)")


def auth(ctx):
    k = key(ctx)
    return {"params": {"api_key": k}} if k else {}


def client(ctx):
    return sk.client(ctx, INTERVALS)


def tags(ctx, cl, info) -> list:
    if not info["title"]:
        return []
    url = (f"{API}?method=track.gettoptags&autocorrect=1&format=json"
           f"&artist={sk.q(om.first_artist(info))}&track={sk.q(info['title'])}&api_key={sk.q(key(ctx))}")
    d = cl.json(url) or {}
    if d.get("error"):
        return []
    tt = (d.get("toptags") or {}).get("tag") or []
    tt = tt if isinstance(tt, list) else [tt]
    return [t.get("name", "") for t in tt if t.get("name") and int(t.get("count") or 0) >= 10][:5]


def check(ctx, cl):
    if not key(ctx):
        return False, "kein Schlüssel"
    d = cl.json(f"{API}?method=tag.getinfo&tag=house&format=json&api_key={sk.q(key(ctx))}") or {}
    return (False, "Schlüssel ungültig") if isinstance(d, dict) and d.get("error") else (True, "in Ordnung")


def test_query(ctx, info):
    """Titel-Informationen und die Tags, die „Online-Metadaten“ vorschlagen würde."""
    ok, why = ready(ctx)
    if not ok:
        raise ValueError(f"Last.fm: {why}.")
    cl = client(ctx)
    t = tags(ctx, cl, info)
    ctx.log(f"Tags (mind. 10 Stimmen): {', '.join(t) or 'keine'}")
    d = cl.json(f"{API}?method=track.getinfo&autocorrect=1&format=json&artist={sk.q(om.first_artist(info))}"
                f"&track={sk.q(info['title'])}&api_key={sk.q(key(ctx))}") or {}
    tr = d.get("track") if isinstance(d, dict) else None
    if not isinstance(tr, dict):
        ctx.log("Titel bei Last.fm nicht gefunden" + (f": {d.get('message')}" if isinstance(d, dict) and d.get("message") else ""))
        return []
    return [{"source_name": "Last.fm", "title": tr.get("name") or "", "artists": [(tr.get("artist") or {}).get("name") or ""],
             "album": (tr.get("album") or {}).get("title") or "", "length": (int(tr.get("duration") or 0) / 1000) or None,
             "id": tr.get("mbid") or "", "url": tr.get("url") or "",
             "extra": ("Tags: " + ", ".join(t) if t else "keine Tags mit genug Stimmen") + f" · {tr.get('listeners', '?')} Hörer"}]


def status(ctx):
    return "Schlüssel gespeichert" if key(ctx) else "kein Schlüssel – unter „Schlüssel …“ eintragen"


def run(action, ctx, files, opts):
    if action == "keys":
        sk.keys_action(ctx, opts, KEYS)
        return {"message": status(ctx)}
    if action == "test":
        try:
            ok, why = check(ctx, client(ctx))
            return {"message": f"Last.fm: {why}"}
        except HttpError as ex:
            return {"message": f"Last.fm nicht erreichbar: {ex}"}
    raise ValueError(f"Unbekannte Aktion: {action}")
