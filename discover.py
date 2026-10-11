"""MarKusSXCH TagStudio – Entdecken (#120): neue Titel von gefolgten Künstlern, Labels und Genres vorschlagen.

Quellen:
  deezer    öffentliche API ohne Anmeldung – neue Veröffentlichungen gefolgter Künstler und Labels, ähnliche
            Künstler, 30-s-Vorhören
  beatport  über die Anmeldung des Beatport-Plugins – neue Titel gefolgter Künstler/Labels und Genre-Charts
            (Top 100) mit Vorhör-Ausschnitt; Kauf nur über den Link, nie automatisch

Zustand in ~/TagStudio/Entdecken/entdecken.json:
  {"follow": {"artists": [...], "labels": [...], "genres": [{"id", "name"}]},
   "items": {Schlüssel: Eintrag}, "last": Zeitpunkt}
Eintrag: key, src, id, artist, title, mix, label, date, preview, url, cover, seed, status (new|saved|hidden|bought),
         owned (schon in der Bibliothek), first (zuerst gesehen).
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request

DEEZER = "https://api.deezer.com"
UA = "MarKusSXCH-TagStudio (+https://github.com/MarkusKeller8200/markussxch-tagstudio)"
STATUS = {"new": "neu", "saved": "gemerkt", "hidden": "ausgeblendet", "bought": "gekauft"}
MAX_ITEMS = 5000             # ältere ausgeblendete/neue Einträge fallen weg, gemerkte bleiben


# =========================================================================== Zustand
def state_path() -> str:
    return os.path.join(os.path.expanduser("~"), "TagStudio", "Entdecken", "entdecken.json")


def load() -> dict:
    try:
        with open(state_path(), encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    f = d.get("follow") if isinstance(d.get("follow"), dict) else {}
    d["follow"] = {"artists": _names(f.get("artists")), "labels": _names(f.get("labels")),
                   "genres": [g for g in f.get("genres") or [] if isinstance(g, dict) and g.get("id")],
                   "days": int(f.get("days") or 60), "sources": [s for s in f.get("sources") or ["deezer", "beatport"]
                                                                if s in ("deezer", "beatport")]}
    d["items"] = d.get("items") if isinstance(d.get("items"), dict) else {}
    return d


def save(d: dict):
    p = state_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    items = d.get("items") or {}
    if len(items) > MAX_ITEMS:
        keep = sorted(items.values(), key=lambda e: (e.get("status") == "saved", e.get("first", "")), reverse=True)
        d["items"] = {e["key"]: e for e in keep[:MAX_ITEMS]}
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _names(xs) -> list[str]:
    out, seen = [], set()
    for x in xs or []:
        x = str(x).strip()
        if x and norm(x) not in seen:
            seen.add(norm(x))
            out.append(x[:80])
    return out


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold().replace("&", " and ")
    return " ".join(re.sub(r"[\W_]+", " ", s).split())


def split_mix(title: str) -> tuple[str, str]:
    m = re.search(r"\s*[\(\[]([^\)\]]*(mix|edit|remix|version|dub|rework|bootleg|vip)[^\)\]]*)[\)\]]\s*$", title or "", re.I)
    return (title[:m.start()].strip(), m.group(1).strip()) if m else ((title or "").strip(), "")


def owned_index(files) -> set:
    """(Künstler, Titel) der Bibliothek normalisiert – für „schon vorhanden“."""
    out = set()
    for f in files:
        t, _mix = split_mix(f.text("TIT2"))
        for a in re.split(r"\s*(?:,|&|\bfeat\.?|\bft\.?|\bvs\.?|\x00| / )\s*", f.text("TPE1"), flags=re.I):
            if a.strip():
                out.add((norm(a), norm(t)))
    return out


def is_owned(e: dict, idx: set) -> bool:
    t = norm(e.get("title"))
    return any((norm(a), t) in idx for a in re.split(r"\s*(?:,|&)\s*", e.get("artist") or "") if a.strip())


def suggest_follow(files, n=30) -> dict:
    """Häufigste Künstler und Labels der Bibliothek als Vorschlag zum Folgen."""
    arts, labs = {}, {}
    for f in files:
        for a in re.split(r"\s*(?:,|&|\x00| / )\s*", f.text("TPE1")):
            a = a.strip()
            if a:
                arts[a] = arts.get(a, 0) + 1
        lab = f.text("TPUB").strip()
        if lab:
            labs[lab] = labs.get(lab, 0) + 1
    top = lambda d: [k for k, _v in sorted(d.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:n]]  # noqa: E731
    return {"artists": [{"name": k, "count": arts[k]} for k in top(arts)],
            "labels": [{"name": k, "count": labs[k]} for k in top(labs)]}


def merge(d: dict, found: list[dict], idx: set | None = None) -> int:
    """Neue Funde übernehmen (Status bleibt erhalten). → Anzahl neuer Einträge."""
    items = d["items"]
    new = 0
    for e in found:
        old = items.get(e["key"])
        if old:
            for k in ("preview", "url", "cover", "label", "date"):
                if e.get(k) and not old.get(k):
                    old[k] = e[k]
            if idx is not None:
                old["owned"] = is_owned(old, idx)
            continue
        e["status"] = "new"
        e["first"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        e["owned"] = is_owned(e, idx) if idx is not None else False
        items[e["key"]] = e
        new += 1
    return new


def _recent(date: str, days: int) -> bool:
    if not date:
        return True
    try:
        t = time.mktime(time.strptime(date[:10], "%Y-%m-%d"))
    except ValueError:
        return True
    return t >= time.time() - days * 86400


# =========================================================================== Deezer
def fetch_json(url: str, timeout=20):
    """GET → JSON (in Tests ersetzbar)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 – nur https-Adressen der Quellen
        return json.loads(r.read().decode("utf-8"))


def _dz(path, **params):
    url = DEEZER + path + ("?" + urllib.parse.urlencode(params) if params else "")
    d = fetch_json(url)
    if isinstance(d, dict) and d.get("error"):
        err = d["error"]
        raise RuntimeError(f"Deezer: {err.get('message') if isinstance(err, dict) else err}")
    _throttle()
    return d


def _throttle():
    time.sleep(0.12)            # Deezer erlaubt ca. 50 Anfragen / 5 s


def _dz_track(t: dict, album: dict, seed: str) -> dict | None:
    if not isinstance(t, dict) or not t.get("id"):
        return None
    title = t.get("title") or ""
    name, mix = split_mix(title)
    if not mix and t.get("title_version"):
        mix = str(t["title_version"]).strip("() ")
    artist = ", ".join(c.get("name", "") for c in (t.get("contributors") or []) if isinstance(c, dict)) \
        or (t.get("artist") or {}).get("name", "")
    return {"key": f"deezer:{t['id']}", "src": "deezer", "id": str(t["id"]), "artist": artist, "title": name, "mix": mix,
            "label": album.get("label") or "", "date": album.get("release_date") or "", "preview": t.get("preview") or "",
            "url": t.get("link") or f"https://www.deezer.com/track/{t['id']}", "release": album.get("title") or "",
            "cover": album.get("cover_medium") or "", "seed": seed}


def _dz_album_tracks(aid, seed: str) -> list[dict]:
    a = _dz(f"/album/{aid}")
    if not isinstance(a, dict):
        return []
    out = []
    for t in ((a.get("tracks") or {}).get("data") or []):
        e = _dz_track(t, a, seed)
        if e:
            out.append(e)
    return out


def deezer_artist(name: str, days: int, log=None) -> list[dict]:
    res = _dz("/search/artist", q=name, limit=5).get("data") or []
    hit = next((a for a in res if norm(a.get("name")) == norm(name)), None)
    if not hit:
        if log:
            log(f"Deezer: Künstler „{name}“ nicht gefunden")
        return []
    albums = _dz(f"/artist/{hit['id']}/albums", limit=25).get("data") or []
    out = []
    for al in sorted(albums, key=lambda x: x.get("release_date") or "", reverse=True)[:8]:
        if _recent(al.get("release_date") or "", days):
            out += [e for e in _dz_album_tracks(al["id"], f"Künstler {name}") if norm(name) in norm(e["artist"])]
    return out


def deezer_label(name: str, days: int, log=None) -> list[dict]:
    res = _dz("/search", q=f'label:"{name}"', limit=50).get("data") or []
    albums = []
    for t in res:
        aid = (t.get("album") or {}).get("id")
        if aid and aid not in albums:
            albums.append(aid)
    out = []
    for aid in albums[:10]:
        tr = _dz_album_tracks(aid, f"Label {name}")
        if tr and norm(tr[0].get("label")) == norm(name) and _recent(tr[0].get("date") or "", days):
            out += tr
    if not out and log:
        log(f"Deezer: keine neuen Titel für Label „{name}“")
    return out


def deezer_related(name: str, n=8) -> list[str]:
    res = _dz("/search/artist", q=name, limit=5).get("data") or []
    hit = next((a for a in res if norm(a.get("name")) == norm(name)), None)
    if not hit:
        return []
    return [a.get("name", "") for a in (_dz(f"/artist/{hit['id']}/related", limit=n).get("data") or []) if a.get("name")]


# =========================================================================== Beatport (über den Client des Plugins)
def _bp_entry(t: dict, seed: str) -> dict | None:
    if not isinstance(t, dict) or not t.get("id"):
        return None
    rel = t.get("release") or {}
    img = rel.get("image") or {}
    cover = img.get("dynamic_uri", "").replace("{w}", "250").replace("{h}", "250") if "{w}" in (img.get("dynamic_uri") or "") \
        else img.get("uri") or ""
    slug = t.get("slug") or re.sub(r"[^a-z0-9]+", "-", (t.get("name") or "").lower()).strip("-") or "track"
    return {"key": f"beatport:{t['id']}", "src": "beatport", "id": str(t["id"]),
            "artist": ", ".join(a.get("name", "") for a in t.get("artists") or [] if isinstance(a, dict)),
            "title": t.get("name") or "", "mix": t.get("mix_name") or "", "label": (rel.get("label") or {}).get("name", ""),
            "date": t.get("publish_date") or t.get("new_release_date") or "", "preview": t.get("sample_url") or "",
            "url": f"https://www.beatport.com/track/{slug}/{t['id']}", "release": rel.get("name") or "", "cover": cover,
            "seed": seed, "bpm": t.get("bpm") or "", "key_name": (t.get("key") or {}).get("name", "") if isinstance(t.get("key"), dict) else "",
            "genre": (t.get("genre") or {}).get("name", "") if isinstance(t.get("genre"), dict) else ""}


def _bp_list(res) -> list:
    if isinstance(res, dict):
        res = res.get("results") or res.get("tracks") or []
    return [t for t in res or [] if isinstance(t, dict)]


def _bp_find(client, kind: str, name: str):
    res = client.get("/catalog/search/", q=name, type=kind, per_page=5)
    lst = res.get(kind) if isinstance(res, dict) else res
    return next((x for x in lst or [] if isinstance(x, dict) and norm(x.get("name")) == norm(name)), None)


def beatport_artist(client, name: str, days: int, log=None) -> list[dict]:
    a = _bp_find(client, "artists", name)
    if not a:
        if log:
            log(f"Beatport: Künstler „{name}“ nicht gefunden")
        return []
    res = client.get("/catalog/tracks/", artist_id=a["id"], order_by="-publish_date", per_page=30)
    return [e for e in (_bp_entry(t, f"Künstler {name}") for t in _bp_list(res)) if e and _recent(e["date"], days)]


def beatport_label(client, name: str, days: int, log=None) -> list[dict]:
    lab = _bp_find(client, "labels", name)
    if not lab:
        if log:
            log(f"Beatport: Label „{name}“ nicht gefunden")
        return []
    res = client.get("/catalog/tracks/", label_id=lab["id"], order_by="-publish_date", per_page=50)
    return [e for e in (_bp_entry(t, f"Label {name}") for t in _bp_list(res)) if e and _recent(e["date"], days)]


def beatport_genre(client, gid, name: str) -> list[dict]:
    res = client.get(f"/catalog/genres/{gid}/top/100/")
    return [e for e in (_bp_entry(t, f"Top 100 {name}") for t in _bp_list(res)) if e]


def beatport_genres(client) -> list[dict]:
    res = client.get("/catalog/genres/", per_page=100)
    return [{"id": g["id"], "name": g.get("name", "")} for g in _bp_list(res) if g.get("id")]


# =========================================================================== Lauf
def run(d: dict, bp_client=None, log=None, progress=None, cancel=None) -> list[dict]:
    """Alle Quellen für alle gefolgten Künstler/Labels/Genres abfragen. Fehler einzelner Abfragen landen im Log."""
    f = d["follow"]
    days = f.get("days") or 60
    jobs = []
    if "deezer" in f["sources"]:
        jobs += [("Deezer", a, lambda a=a: deezer_artist(a, days, log)) for a in f["artists"]]
        jobs += [("Deezer", lab, lambda lab=lab: deezer_label(lab, days, log)) for lab in f["labels"]]
    if "beatport" in f["sources"] and bp_client is not None:
        jobs += [("Beatport", a, lambda a=a: beatport_artist(bp_client, a, days, log)) for a in f["artists"]]
        jobs += [("Beatport", lab, lambda lab=lab: beatport_label(bp_client, lab, days, log)) for lab in f["labels"]]
        jobs += [("Beatport", g.get("name", ""), lambda g=g: beatport_genre(bp_client, g["id"], g.get("name", "")))
                 for g in f["genres"]]
    found = []
    for i, (src, what, fn) in enumerate(jobs, 1):
        if cancel is not None and cancel.is_set():
            break
        if progress:
            progress(("progress", i, len(jobs), f"{src}: {what}"))
        try:
            found += fn()
        except Exception as ex:  # noqa: BLE001 – eine Quelle darf den Lauf nicht abbrechen
            if log:
                log(f"{src} „{what}“: {ex}")
    return found
