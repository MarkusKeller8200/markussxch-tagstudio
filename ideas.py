"""MarKusSXCH TagStudio – Ideen (#186): Wunschlisten für Titel, die später gekauft werden sollen.

Wunschlisten sind Playlists der Art ``wish`` im Ordner „Ideen“ des Playlists-Speichers (Entscheid I2). Ihre Einträge
haben keine Datei, sondern eine Angabe ``ref`` (Künstler, Titel, Mix, Link) und Zusatzangaben ``idea``
(Status, Quelle, Store-ID, Vorhör- und Cover-Link, Label, Datum, Schlüssel in „Entdecken“), dazu ``note``.

Status: von Hand *Idee*, *Kaufen*, *Verworfen*; *Gekauft* ergibt sich aus der Liste „Einkäufe“ (gleiche Store-ID bzw.
Künstler + Titel + Mix), *In Bibliothek* aus einer verknüpften Datei (wie bei Playlists, #271).
Diese Datei enthält nur Logik ohne Oberfläche und ohne Netz – siehe ``session_ideas.py``.
"""
from __future__ import annotations

import os
import re

import discover
import playlists

FOLDER = "Ideen"
KIND = "wish"
DEFAULT_LIST = "Wunschliste"
MIGRATED_LIST = "Gemerkt (Entdecken)"
MIGRATED_FLAG = "ideas_from_discover"     # in index.json › migrated
BP_PREFIX = "TagStudio_WISH_"
STATUS = {"idea": "Idee", "buy": "Kaufen", "bought": "Gekauft", "lib": "In Bibliothek", "dropped": "Verworfen"}
SOURCES = {"deezer": "Deezer", "beatport": "Beatport", "spotify": "Spotify", "manual": "von Hand", "text": "Text",
           "discover": "Entdecken"}
EXPORT_HEAD = ["Wunschliste", "Status", "Künstler", "Titel", "Mix", "Label", "Datum", "Quelle", "Notiz", "Link", "Gekauft am"]


def is_wish(pl: dict) -> bool:
    return isinstance(pl, dict) and pl.get("kind") == KIND


def entry(artist="", title="", mix="", *, url="", isrc="", dur=0, note="", src="manual", **idea) -> dict | None:
    """Ein Eintrag einer Wunschliste (bereinigt) – None ohne Künstler und Titel."""
    ref = {"artist": artist, "title": title, "mix": mix, "isrc": isrc, "url": url, "dur": dur, "source": src}
    item = playlists.clean_item({"ref": ref, "note": note, "idea": {"status": "idea", "src": src, **idea}})
    if not item or not item.get("ref") or not (item["ref"].get("artist") or item["ref"].get("title")):
        return None
    return item


def from_discover(e: dict) -> dict | None:
    """Vorschlag aus „Entdecken“ → Eintrag. SonoVault-Vorschläge (#258, Entscheid I6): nur Künstler, Titel und Mix –
    wie ein Eintrag von Hand, ohne SonoVault-Felder, ohne Link und ohne Schlüssel."""
    if not isinstance(e, dict):
        return None
    if e.get("src") == "sonovault":
        return entry(e.get("artist", ""), e.get("title", ""), e.get("mix", ""), src="manual")
    src = e.get("src") if e.get("src") in ("deezer", "beatport", "spotify") else "discover"
    return entry(e.get("artist", ""), e.get("title", ""), e.get("mix", ""), url=e.get("url", ""), src=src,
                 store=src if src in ("deezer", "beatport", "spotify") else "", sid=str(e.get("id") or ""),
                 preview=e.get("preview", ""), cover=e.get("cover", ""), label=e.get("label", ""),
                 date=str(e.get("date") or "")[:10], release=e.get("release", ""), genre=e.get("genre", ""),
                 disc=e.get("key", ""))


def from_spotify(r: dict) -> dict | None:
    """#384 SP2: Titel aus Spotify („Läuft gerade“/„Zuletzt gehört“) → Eintrag mit Link, ISRC und Spotify-ID."""
    if not isinstance(r, dict):
        return None
    return entry(r.get("artist", ""), r.get("title", ""), r.get("mix", ""), url=r.get("url", ""), isrc=r.get("isrc", ""),
                 dur=r.get("dur") or 0, src="spotify", store="spotify", sid=str(r.get("id") or ""),
                 cover=r.get("cover", ""), release=r.get("release", ""), date=str(r.get("date") or "")[:10])


def spotify_uris(items: list) -> tuple[list[str], int]:
    """#384 SP5: Spotify-URIs der offenen Einträge (Idee/Kaufen) mit Spotify-ID → (URIs, Anzahl ohne ID)."""
    uris, without = [], 0
    for x in items or []:
        idea = x.get("idea") or {}
        if idea.get("status") not in ("idea", "buy", None):
            continue
        sid = str(idea.get("sid") or "") if idea.get("store") == "spotify" else ""
        if not sid:
            m = re.search(r"open\.spotify\.com/track/([A-Za-z0-9]{22})", str((x.get("ref") or {}).get("url") or ""))
            sid = m.group(1) if m else ""
        if sid and re.fullmatch(r"[A-Za-z0-9]{22}", sid):
            u = f"spotify:track:{sid}"
            if u not in uris:
                uris.append(u)
        else:
            without += 1
    return uris, without


def sp_name(list_name: str) -> str:
    """Name der Spotify-Playlist zu einer Wunschliste – gleich wie bei Beatport (TagStudio_WISH_<Liste>)."""
    return bp_name(list_name)


def from_text(text: str) -> tuple[list[dict], int]:
    """Kopierte Liste „Künstler - Titel (Mix)“ je Zeile → Einträge (wie die Trackliste bei Playlists, #279)."""
    refs, unknown = playlists.parse_tracklist(text, "text")
    out = []
    for r in refs:
        ref = r.get("ref") or {}
        title, mix = discover.split_mix(ref.get("title", ""))
        e = entry(ref.get("artist", ""), title, mix, url=ref.get("url", ""), src="text")
        if e:
            out.append(e)
    return out, unknown


def keys(item: dict) -> set:
    """Schlüssel gegen Doppelte: Schlüssel in Entdecken, Store-ID, Künstler + Titel + Mix."""
    idea, ref = item.get("idea") or {}, item.get("ref") or {}
    out = set()
    if idea.get("disc"):
        out.add("d:" + idea["disc"])
    if idea.get("store") and idea.get("sid"):
        out.add(f"s:{idea['store']}:{idea['sid']}")
    t = discover.norm(ref.get("title") or item.get("title"))
    if t:
        out.add("n:" + "|".join([discover.norm(ref.get("artist") or item.get("artist")), t, discover._mix(ref.get("mix"))]))
    return out


def merge(items: list, new: list) -> tuple[list, int, int]:
    """Neue Einträge anhängen, Doppelte (in der Liste oder untereinander) auslassen. → (Einträge, neu, doppelt)."""
    seen = set()
    for x in items:
        seen |= keys(x)
    out, added, dupes = list(items), 0, 0
    for x in new:
        if not x:
            continue
        k = keys(x)
        if k & seen:
            dupes += 1
            continue
        seen |= k
        out.append(x)
        added += 1
    return out, added, dupes


def purchased(items: list, bought) -> dict:
    """Einträge mit der Liste „Einkäufe“ abgleichen (gleiche Store-ID, sonst Künstler + Titel + Mix, wie #291).
    → {Position: Kaufdatum oder "ja"}."""
    pseudo = {"items": {}}
    for k, x in enumerate(items):
        idea, ref = x.get("idea") or {}, x.get("ref") or {}
        key = f"{idea['store']}:{idea['sid']}" if idea.get("store") and idea.get("sid") else f"#{k}"
        pseudo["items"][str(k)] = {"key": key, "artist": ref.get("artist", ""), "title": ref.get("title", ""),
                                   "mix": ref.get("mix", "")}
    discover.mark_purchased(pseudo, bought)
    return {int(k): e["purchased"] for k, e in pseudo["items"].items() if e.get("purchased")}


def status(item: dict, bought_on: str = "", exists=os.path.isfile) -> str:
    """Wirksamer Status: In Bibliothek (Datei verknüpft) > Gekauft (in „Einkäufe“) > von Hand gesetzt."""
    if item.get("path") and exists(item["path"]):
        return "lib"
    if bought_on:
        return "bought"
    st = (item.get("idea") or {}).get("status")
    return st if st in playlists.IDEA_STATUS else "idea"


def bp_name(list_name: str) -> str:
    """Name der Beatport-Playlist zu einer Wunschliste (Entscheid I5): TagStudio_WISH_<Liste>."""
    s = re.sub(r"[^\w\-]+", "_", str(list_name or "").strip(), flags=re.UNICODE).strip("_") or "Liste"
    return BP_PREFIX + s[:60]


def bp_ids(items: list) -> tuple[list[str], int]:
    """Beatport-IDs der offenen Einträge (nicht verworfen, nicht schon in der Bibliothek). → (IDs, ohne ID)."""
    ids, without = [], 0
    for x in items:
        idea = x.get("idea") or {}
        if idea.get("status") == "dropped" or x.get("path"):
            continue
        if idea.get("store") == "beatport" and idea.get("sid"):
            ids.append(idea["sid"])
        else:
            without += 1
    return list(dict.fromkeys(ids)), without


def to_playlist_items(items: list) -> list:
    """Einträge für eine normale Playlist (#186 Phase 2b): ohne verworfene, ohne Ideen-Angaben."""
    out = []
    for x in items:
        if (x.get("idea") or {}).get("status") == "dropped":
            continue
        y = {k: v for k, v in x.items() if k != "idea"}
        out.append(y)
    return out


def export_rows(lists: list, bought_by: dict) -> list[list[str]]:
    """lists: Wunschlisten; bought_by: {Playlist-ID: {Position: Datum}} → Zeilen für Excel/CSV."""
    rows = []
    for pl in lists:
        b = bought_by.get(pl["id"], {})
        for k, x in enumerate(pl.get("items") or []):
            idea, ref = x.get("idea") or {}, x.get("ref") or {}
            st = status(x, b.get(k, ""))
            rows.append([pl["name"], STATUS.get(st, st), ref.get("artist", ""), ref.get("title", ""), ref.get("mix", ""),
                         idea.get("label", ""), idea.get("date", ""), SOURCES.get(idea.get("src", ""), idea.get("src", "")),
                         x.get("note", ""), ref.get("url", ""), b.get(k, "") if b.get(k, "") != "ja" else "ja"])
    return rows
