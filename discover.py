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
         owned (schon in der Bibliothek), first (zuerst gesehen); purchased (Kaufdatum laut „Käufe“, nur angezeigt, #291).
follow.bp: von Beatport übernommene Künstler/Labels (Herkunft, #291).
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import paths
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
    return paths.sub("Entdecken", "entdecken.json")


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
                   "days": int(f.get("days") or 60), "auto": bool(f.get("auto")), "sources": [s for s in f.get("sources") or ["deezer", "beatport"]
                                                                if s in ("deezer", "beatport")],
                   "bp": _bp_origin(f.get("bp"))}
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


def _bp_origin(x) -> dict:
    """Von Beatport übernommene Namen (#291) – nur zur Anzeige der Herkunft."""
    x = x if isinstance(x, dict) else {}
    return {"artists": _names(x.get("artists")), "labels": _names(x.get("labels"))}


def follow_edit(d: dict, kind: str, name: str, add: bool = True) -> bool:
    """Einen Künstler bzw. ein Label folgen (add) oder entfernen (#291). → geändert?"""
    if kind not in ("artists", "labels"):
        raise ValueError("Unbekannte Art.")
    name = str(name or "").strip()[:80]
    if not name:
        return False
    lst = d["follow"][kind]
    have = [x for x in lst if norm(x) == norm(name)]
    if add:
        if have:
            return False
        lst.append(name)
        return True
    if not have:
        return False
    d["follow"][kind] = [x for x in lst if norm(x) != norm(name)]
    bp = d["follow"].get("bp") or {}
    if kind in bp:
        bp[kind] = [x for x in bp[kind] if norm(x) != norm(name)]
    return True


def clear(d: dict, keep=("saved", "bought")) -> int:
    """Vorschläge leeren (#291): alles außer gemerkten und gekauften entfernen. → Anzahl entfernt."""
    before = len(d["items"])
    d["items"] = {k: e for k, e in d["items"].items() if e.get("status") in keep}
    d.pop("auto_new", None)
    return before - len(d["items"])


def _artists(s) -> set:
    return {norm(a) for a in re.split(r"\s*(?:,|&|\bfeat\.?|\bft\.?|\bvs\.?| / )\s*", str(s or ""), flags=re.I) if a.strip()}


def _mix(s) -> str:
    m = norm(s)
    return "" if m in ("original mix", "original") else m


def mark_purchased(d: dict, bought) -> int:
    """Vorschläge mit der Liste „Käufe“ abgleichen (#291): gleiche Beatport-ID oder gleicher Künstler + Titel (+ Mix,
    wenn beide einen haben) → e["purchased"] = Kaufdatum (oder "ja"). bought: Einträge aus purchases.Store. → Anzahl."""
    ids, names = {}, {}
    for it in bought or []:
        if not isinstance(it, dict):
            continue
        when = (it.get("bought") or "")[:10] or "ja"
        if it.get("store") == "beatport" and it.get("id"):
            ids[f"beatport:{it['id']}"] = when
        t = norm(it.get("title"))
        for a in _artists(it.get("artist")):
            names.setdefault((a, t), []).append((_mix(it.get("mix")), when))
    n = 0
    for e in d["items"].values():
        when = ids.get(e["key"])
        if not when:
            t, mx = norm(e.get("title")), _mix(e.get("mix"))
            for a in _artists(e.get("artist")):
                hit = next((w for m, w in names.get((a, t), []) if not m or not mx or m == mx), None)
                if hit:
                    when = hit
                    break
        if when:
            e["purchased"] = when
            n += 1
        else:
            e.pop("purchased", None)
    return n


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


def mark_bought(tracks, d: dict | None = None) -> int:
    """Gekaufte Titel (Beatport-Käufe: id, name, artists) in der Liste als „gekauft“ markieren. → Anzahl."""
    own = d is None
    d = d or load()
    ids = {f"beatport:{t.get('id')}" for t in tracks if isinstance(t, dict) and t.get("id")}
    names = set()
    for t in tracks:
        if not isinstance(t, dict):
            continue
        title = norm(t.get("name"))
        for a in t.get("artists") or []:
            if isinstance(a, dict) and title:
                names.add((norm(a.get("name")), title))
    n = 0
    for e in d["items"].values():
        if e.get("status") == "bought":
            continue
        if e["key"] in ids or is_owned(e, names):
            e["status"] = "bought"
            n += 1
    if own and n:
        save(d)
    return n


EXPORT_HEAD = ["Status", "Künstler", "Titel", "Mix", "Label", "Release", "Datum", "BPM", "Tonart", "Genre", "Quelle", "Link"]


def export_rows(d: dict, status=("saved",)) -> list[list[str]]:
    rows = []
    for e in sorted(d["items"].values(), key=lambda e: (e.get("artist", "").lower(), e.get("title", "").lower())):
        if status and e.get("status") not in status:
            continue
        rows.append([STATUS.get(e.get("status"), ""), e.get("artist", ""), e.get("title", ""), e.get("mix", ""),
                     e.get("label", ""), e.get("release", ""), (e.get("date") or "")[:10], str(e.get("bpm") or ""),
                     e.get("key_name", ""), e.get("genre", ""), {"deezer": "Deezer", "beatport": "Beatport"}.get(e.get("src"), e.get("src", "")),
                     e.get("url", "")])
    return rows


def auto_due(d: dict, hours=20) -> bool:
    """Tägliche Suche fällig? (eingeschaltet, etwas gefolgt, letzte Suche älter als hours)"""
    f = d["follow"]
    if not f.get("auto") or not (f["artists"] or f["labels"] or f["genres"]):
        return False
    try:
        last = time.mktime(time.strptime(d.get("last", "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return True
    return time.time() - last >= hours * 3600


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


def _dz_album_tracks(aid, seed: str, dz=None) -> list[dict]:
    a = (dz or _dz)(f"/album/{aid}")
    if not isinstance(a, dict):
        return []
    out = []
    for t in ((a.get("tracks") or {}).get("data") or []):
        e = _dz_track(t, a, seed)
        if e:
            out.append(e)
    return out


def deezer_artist(name: str, days: int, log=None, dz=None) -> list[dict]:
    """dz: Abruf über das Plugin Deezer (#204); ohne – eigener Abruf (Tests)."""
    dz = dz or _dz
    res = dz("/search/artist", q=name, limit=5).get("data") or []
    hit = next((a for a in res if norm(a.get("name")) == norm(name)), None)
    if not hit:
        if log:
            log(f"Deezer: Künstler „{name}“ nicht gefunden")
        return []
    albums = dz(f"/artist/{hit['id']}/albums", limit=25).get("data") or []
    out = []
    for al in sorted(albums, key=lambda x: x.get("release_date") or "", reverse=True)[:8]:
        if _recent(al.get("release_date") or "", days):
            out += [e for e in _dz_album_tracks(al["id"], f"Künstler {name}", dz) if norm(name) in norm(e["artist"])]
    return out


def deezer_label(name: str, days: int, log=None, dz=None) -> list[dict]:
    dz = dz or _dz
    res = dz("/search", q=f'label:"{name}"', limit=50).get("data") or []
    albums = []
    for t in res:
        aid = (t.get("album") or {}).get("id")
        if aid and aid not in albums:
            albums.append(aid)
    out = []
    for aid in albums[:10]:
        tr = _dz_album_tracks(aid, f"Label {name}", dz)
        if tr and norm(tr[0].get("label")) == norm(name) and _recent(tr[0].get("date") or "", days):
            out += tr
    if not out and log:
        log(f"Deezer: keine neuen Titel für Label „{name}“")
    return out


def deezer_related(name: str, n=8, dz=None) -> list[str]:
    dz = dz or _dz
    res = dz("/search/artist", q=name, limit=5).get("data") or []
    hit = next((a for a in res if norm(a.get("name")) == norm(name)), None)
    if not hit:
        return []
    return [a.get("name", "") for a in (dz(f"/artist/{hit['id']}/related", limit=n).get("data") or []) if a.get("name")]


def related_artists(follow: list[str], dz=None, per=8, limit=30, cancel=None, progress=None) -> list[dict]:
    """Ähnliche Künstler zu den gefolgten (#291, Deezer) – ohne bereits gefolgte, häufigste zuerst.
    → [{"name", "count", "because": [gefolgte Künstler]}]"""
    have = {norm(a) for a in follow}
    agg: dict[str, dict] = {}
    for i, a in enumerate(follow[:40], 1):
        if cancel is not None and cancel.is_set():
            break
        if progress:
            progress(("progress", i, min(len(follow), 40), f"Deezer: ähnlich wie {a}"))
        try:
            rel = deezer_related(a, per, dz)
        except Exception:  # noqa: BLE001 – einzelner Künstler darf nicht stören
            continue
        for r in rel:
            k = norm(r)
            if not k or k in have:
                continue
            x = agg.setdefault(k, {"name": r, "count": 0, "because": []})
            x["count"] += 1
            x["because"].append(a)
    return sorted(agg.values(), key=lambda x: (-x["count"], x["name"].lower()))[:limit]


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


def beatport_feed(client, days: int, log=None) -> list[dict]:
    """„My Beatport“ (#291): neue Titel gefolgter Künstler/Labels – GET /my/beatport/tracks/ (nur lesen)."""
    out = []
    for page in (1, 2, 3):
        res = client.get("/my/beatport/tracks/", page=page, per_page=100)
        rows = [r.get("track") if isinstance(r.get("track"), dict) else r for r in _bp_list(res)]
        es = [e for e in (_bp_entry(t, "My Beatport") for t in rows) if e]
        out += [e for e in es if _recent(e["date"], days)]
        if len(rows) < 100 or (es and not _recent(es[-1]["date"], days)):
            break
    return out


def beatport_genre(client, gid, name: str) -> list[dict]:
    res = client.get(f"/catalog/genres/{gid}/top/100/")
    return [e for e in (_bp_entry(t, f"Top 100 {name}") for t in _bp_list(res)) if e]


def beatport_genres(client) -> list[dict]:
    res = client.get("/catalog/genres/", per_page=100)
    return [{"id": g["id"], "name": g.get("name", "")} for g in _bp_list(res) if g.get("id")]


# =========================================================================== Lauf
def run(d: dict, bp_client=None, log=None, progress=None, cancel=None, dz=_dz) -> list[dict]:
    """Alle Quellen für alle gefolgten Künstler/Labels/Genres abfragen. Fehler einzelner Abfragen landen im Log.
    dz: Deezer-Abruf (Plugin Deezer, #204); None = Deezer überspringen."""
    f = d["follow"]
    days = f.get("days") or 60
    jobs = []
    if "deezer" in f["sources"] and dz is not None:
        jobs += [("Deezer", a, lambda a=a: deezer_artist(a, days, log, dz)) for a in f["artists"]]
        jobs += [("Deezer", lab, lambda lab=lab: deezer_label(lab, days, log, dz)) for lab in f["labels"]]
    if "beatport" in f["sources"] and bp_client is not None:
        jobs += [("Beatport", a, lambda a=a: beatport_artist(bp_client, a, days, log)) for a in f["artists"]]
        jobs += [("Beatport", lab, lambda lab=lab: beatport_label(bp_client, lab, days, log)) for lab in f["labels"]]
        jobs += [("Beatport", g.get("name", ""), lambda g=g: beatport_genre(bp_client, g["id"], g.get("name", "")))
                 for g in f["genres"]]
        jobs.append(("Beatport", "My Beatport", lambda: beatport_feed(bp_client, days, log)))
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
