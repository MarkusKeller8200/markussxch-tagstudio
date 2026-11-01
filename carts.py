"""MarKusSXCH TagStudio – Warenkorb (#420–#423): Titel sammeln, auf Käufe prüfen, als Einkaufsliste an den Shop senden.

Gespeichert im Datenordner des Profils (``~/TagStudio/Warenkorb/warenkorb.json``, atomar geschrieben):

    {"format": 1,
     "carts": {"c_…": {"id", "name", "store": "beatport", "created", "status": "open|bought", "closed",
                       "closed_by": "auto|hand", "auto": true, "archived", "checked", "pushed": {"beatport": {…}},
                       "items": [{"artist", "title", "mix", "isrc", "dur", "url", "note", "src", "added", "sid",
                                  "match": {"state", "score", "cands"}, "lib", "removed": {"why", "at"}}]}}}

*Gekauft* ergibt sich bei jeder Anzeige aus der Liste „Einkäufe“ (gleiche Beatport-ID, sonst Künstler + Titel + Mix,
``discover.mark_purchased``), *in Bibliothek* aus der letzten Prüfung. Ein offener Korb wird automatisch „gekauft“,
wenn alle Titel der Einkaufsliste gekauft sind (Entscheid W3); „Wieder öffnen“ schaltet das ab, bis neue Titel dazukommen.
Konzept: docs/KONZEPT-WARENKORB.md. Nur Standardbibliothek, ohne Netz – siehe ``session_carts.py``.
"""
from __future__ import annotations

import copy
import json
import os
import re
import secrets
import time

import discover
import playlists

FORMAT = 1
STORES = {"beatport": "Beatport"}
SOURCES = {"text": "Liste", "ideas": "Ideen", "manual": "von Hand", "url": "Link"}
STATUS = {"open": "offen", "bought": "gekauft", "lib": "in Bibliothek", "removed": "entfernt"}
REMOVED_WHY = {"hand": "von Hand", "bought": "bereits gekauft", "lib": "in Bibliothek"}
MATCH = ("sure", "unsure", "none")
BP_PREFIX = "TagStudio_CART_"
DEFAULT_NAME = "Warenkorb"
NAME_TEMPLATE = "Warenkorb_{y:04d}_{m:02d}_{d:02d}"      # #433: Vorlage für neue Körbe (unabhängig von der Sprache)
UNDO_MAX = 30
EXPORT_HEAD = ["Warenkorb", "Zustand", "Status", "Künstler", "Titel", "Mix", "Beatport-ID", "Link", "Quelle", "Notiz",
               "Gekauft am"]
_TEXT = ("artist", "title", "mix", "isrc", "note")


def _txt(v, n=300) -> str:
    return " ".join(str(v or "").split())[:n]


def _url(v) -> str:
    u = str(v or "").strip()
    return u if u.startswith("https://") and len(u) < 400 else ""


def clean_cand(c) -> dict | None:
    if not isinstance(c, dict) or not str(c.get("id") or "").strip():
        return None
    out = {"id": str(c["id"]).strip()[:30]}
    for k in ("artist", "title", "mix"):
        v = _txt(c.get(k))
        if v:
            out[k] = v
    if _url(c.get("url")):
        out["url"] = _url(c.get("url"))
    try:
        out["score"] = round(max(0.0, min(1.0, float(c.get("score") or 0))), 3)
    except (TypeError, ValueError):
        out["score"] = 0.0
    return out


def clean_item(x) -> dict | None:
    """Eintrag eines Warenkorbs bereinigen – None ohne Künstler und Titel."""
    if not isinstance(x, dict):
        return None
    out = {k: _txt(x.get(k), 1000 if k == "note" else 300) for k in _TEXT if _txt(x.get(k))}
    if not (out.get("artist") or out.get("title")):
        return None
    if out.get("isrc"):
        out["isrc"] = out["isrc"].upper()
    if _url(x.get("url")):
        out["url"] = _url(x.get("url"))
    try:
        d = int(float(x.get("dur") or 0))
        if d > 0:
            out["dur"] = d
    except (TypeError, ValueError):
        pass
    out["src"] = x.get("src") if x.get("src") in SOURCES else "manual"
    out["added"] = int(x.get("added") or time.time())
    sid = str(x.get("sid") or "").strip()
    if re.fullmatch(r"\d{1,15}", sid):
        out["sid"] = sid
    m = x.get("match")
    if isinstance(m, dict) and m.get("state") in MATCH:
        mm = {"state": m["state"]}
        try:
            mm["score"] = round(float(m.get("score") or 0), 3)
        except (TypeError, ValueError):
            mm["score"] = 0.0
        cands = [c for c in (clean_cand(c) for c in (m.get("cands") or [])[:5]) if c]
        if cands:
            mm["cands"] = cands
        out["match"] = mm
    if isinstance(x.get("lib"), str) and x["lib"]:
        out["lib"] = x["lib"][:1000]
    r = x.get("removed")
    if isinstance(r, dict) and r.get("why") in REMOVED_WHY:
        out["removed"] = {"why": r["why"], "at": int(r.get("at") or time.time())}
    return out


def item(artist="", title="", mix="", *, url="", isrc="", dur=0, note="", src="manual", sid="") -> dict | None:
    return clean_item({"artist": artist, "title": title, "mix": mix, "url": url, "isrc": isrc, "dur": dur,
                       "note": note, "src": src, "sid": sid})


def from_text(text: str) -> tuple[list[dict], int]:
    """Kopierte Trackliste (1001Tracklists, MixID, Notizen) → (Einträge, unbekannte „ID – ID“)."""
    refs, unknown = playlists.parse_tracklist(text, "text")
    out = []
    for r in refs:
        ref = r.get("ref") or {}
        title, mix = discover.split_mix(ref.get("title", ""))
        e = item(ref.get("artist", ""), title, mix, url=ref.get("url", ""), src="text")
        if e and r.get("head"):
            e["head"] = True                                  # #436: vermutlich Titel des Mixes (nur für die Vorschau)
        out.append(e)
    return [x for x in out if x], unknown


URL_PLUGINS = {"beatport.com": "beatport", "open.spotify.com": "spotify", "soundcloud.com": "soundcloud"}


def url_plugin(url: str) -> str:
    """#424: zuständiges Plugin für einen Link (Beatport, Spotify, SoundCloud) – sonst ""."""
    import urllib.parse
    u = str(url or "").strip()
    if not u.startswith("https://"):
        return ""
    host = (urllib.parse.urlparse(u).hostname or "").lower()
    for dom, pid in URL_PLUGINS.items():
        if host == dom or host.endswith("." + dom):
            return pid
    return ""


def from_ref(r: dict, src="url") -> dict | None:
    """#424: Titel aus einem Plugin (url_tracks) → Eintrag; Beatport-ID nur aus „sid“ bzw. einem Beatport-Link."""
    if not isinstance(r, dict):
        return None
    sid = str(r.get("sid") or "") or bp_id_from_url(r.get("url", ""))
    e = item(r.get("artist", ""), r.get("title", ""), r.get("mix", ""), url=r.get("url", ""), isrc=r.get("isrc", ""),
             dur=r.get("dur") or 0, src=src, sid=sid)
    if e and e.get("sid"):
        e["match"] = {"state": "sure", "score": 1.0}
    return e


def bp_id_from_url(url: str) -> str:
    m = re.search(r"beatport\.com/track/[^/]+/(\d+)", str(url or ""))
    return m.group(1) if m else ""


def from_idea(x: dict) -> dict | None:
    """Eintrag einer Wunschliste (Ideen, #186) → Eintrag des Warenkorbs; Beatport-ID, Link, ISRC bleiben."""
    if not isinstance(x, dict):
        return None
    idea, ref = x.get("idea") or {}, x.get("ref") or {}
    sid = idea.get("sid", "") if idea.get("store") == "beatport" else bp_id_from_url(ref.get("url", ""))
    e = item(ref.get("artist", ""), ref.get("title", ""), ref.get("mix", ""), url=ref.get("url", ""),
             isrc=ref.get("isrc", ""), dur=ref.get("dur") or 0, note=x.get("note", ""), src="ideas", sid=sid)
    if e and e.get("sid"):
        e["match"] = {"state": "sure", "score": 1.0}
    return e


def keys(x: dict) -> set:
    """Schlüssel gegen Doppelte: Beatport-ID, Künstler + Titel + Mix."""
    out = set()
    if x.get("sid"):
        out.add("s:" + x["sid"])
    t = discover.norm(x.get("title"))
    if t:
        out.add("n:" + "|".join([discover.norm(x.get("artist")), t, discover._mix(x.get("mix"))]))
    return out


def merge(items: list, new: list) -> tuple[list, int, int]:
    """Neue Einträge anhängen, Doppelte auslassen (auch entfernte zählen – die stehen schon im Korb).
    → (Einträge, neu, doppelt)"""
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
    """Einträge mit „Einkäufe“ abgleichen → {Position: Kaufdatum oder "ja"} (wie Entdecken ↔ Käufe, #291)."""
    pseudo = {"items": {}}
    for k, x in enumerate(items):
        pseudo["items"][str(k)] = {"key": f"beatport:{x['sid']}" if x.get("sid") else f"#{k}",
                                   "artist": x.get("artist", ""), "title": x.get("title", ""), "mix": x.get("mix", "")}
    discover.mark_purchased(pseudo, bought)
    return {int(k): e["purchased"] for k, e in pseudo["items"].items() if e.get("purchased")}


def status(x: dict, bought_on: str = "", exists=os.path.isfile) -> str:
    """Wirksamer Status: entfernt > gekauft > in Bibliothek (Datei noch da) > offen."""
    if x.get("removed"):
        return "removed"
    if bought_on:
        return "bought"
    if x.get("lib") and exists(x["lib"]):
        return "lib"
    return "open"


def bp_name(cart_name: str) -> str:
    """Name der Beatport-Playlist zu einem Korb (Entscheid W2): TagStudio_CART_<Korb>."""
    s = re.sub(r"[^\w\-]+", "_", str(cart_name or "").strip(), flags=re.UNICODE).strip("_") or "Korb"
    return BP_PREFIX + s[:60]


def shopping(items: list, bought_by: dict, exists=os.path.isfile) -> list[int]:
    """Positionen der Einkaufsliste: offen (nicht entfernt, nicht gekauft, nicht in der Bibliothek)."""
    return [k for k, x in enumerate(items) if status(x, bought_by.get(k, ""), exists) == "open"]


def bp_ids(items: list, bought_by: dict, exists=os.path.isfile) -> tuple[list[str], int]:
    """Beatport-IDs der Einkaufsliste → (IDs ohne Doppelte, Anzahl ohne sichere Beatport-ID)."""
    ids, without = [], 0
    for k in shopping(items, bought_by, exists):
        sid = items[k].get("sid")
        if sid:
            ids.append(sid)
        else:
            without += 1
    return list(dict.fromkeys(ids)), without


def apply_match(x: dict, r: dict | None) -> dict:
    """Ergebnis der Beatport-Suche in einen Eintrag übernehmen. r: {"id", "score", "url", "cands"} oder None.
    sicher → Beatport-ID und Link übernehmen; unsicher → Kandidaten merken; sonst „nicht bei Beatport“."""
    y = copy.deepcopy(x)
    if not isinstance(r, dict):
        y["match"] = {"state": "none", "score": 0.0}
        return y
    cands = [c for c in (clean_cand(c) for c in r.get("cands") or []) if c]
    score = float(r.get("score") or 0)
    if r.get("id") and r.get("sure"):
        y["sid"] = str(r["id"])
        if _url(r.get("url")):
            y["url"] = _url(r.get("url"))
        y["match"] = {"state": "sure", "score": round(score, 3)}
    elif cands:
        y.pop("sid", None)
        y["match"] = {"state": "unsure", "score": round(score, 3), "cands": cands[:3]}
    else:
        y.pop("sid", None)
        y["match"] = {"state": "none", "score": round(score, 3)}
    return y


def pick(x: dict, cand: dict | None) -> dict:
    """Kandidat von Hand wählen (cand None = „nicht bei Beatport“)."""
    y = copy.deepcopy(x)
    c = clean_cand(cand) if cand else None
    if c:
        y["sid"] = c["id"]
        if c.get("url"):
            y["url"] = c["url"]
        y["match"] = {"state": "sure", "score": c.get("score", 0.0), "hand": True}
    else:
        y.pop("sid", None)
        y["match"] = {"state": "none", "score": 0.0, "hand": True}
    return clean_item(y) or y


def auto_close(cart: dict, bought_by: dict, now=None, exists=os.path.isfile) -> bool:
    """Entscheid W3: offener Korb, alle Titel ausser entfernten gekauft → „gekauft“. → geändert?"""
    if cart.get("status") != "open" or cart.get("archived") or not cart.get("auto", True):
        return False
    active = [k for k, x in enumerate(cart.get("items") or []) if not x.get("removed")]
    if not active or any(status(cart["items"][k], bought_by.get(k, ""), exists) != "bought" for k in active):
        return False
    cart.update(status="bought", closed=int(now or time.time()), closed_by="auto")
    return True


def export_rows(carts: list, bought_by: dict) -> list[list[str]]:
    rows = []
    for c in carts:
        b = bought_by.get(c["id"], {})
        for k, x in enumerate(c.get("items") or []):
            st = status(x, b.get(k, ""))
            label = STATUS.get(st, st)
            if st == "removed":
                label += f" ({REMOVED_WHY.get((x.get('removed') or {}).get('why'), '')})"
            rows.append([c["name"], "gekauft" if c.get("status") == "bought" else "offen", label, x.get("artist", ""),
                         x.get("title", ""), x.get("mix", ""), x.get("sid", ""), x.get("url", ""),
                         SOURCES.get(x.get("src", ""), x.get("src", "")), x.get("note", ""), b.get(k, "")])
    return rows


class Store:
    """Warenkörbe eines Profils mit Rückgängig (im Speicher, wie bei den Playlists)."""

    def __init__(self, root: str):
        self.root = root
        self.path = os.path.join(root, "warenkorb.json")
        self._data: dict | None = None
        self._mtime = None
        self.undo_stack: list[tuple[str, dict]] = []

    def _stamp(self):
        try:
            return os.path.getmtime(self.path)
        except OSError:
            return None

    @property
    def data(self) -> dict:
        if self._data is not None and self._stamp() != self._mtime:     # von aussen geändert (Wiederherstellen, Test)
            self._data = None
            self.undo_stack.clear()
        if self._data is None:
            self._mtime = self._stamp()
            try:
                with open(self.path, encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                d = {}
            d = d if isinstance(d, dict) else {}
            carts = {}
            for cid, c in (d.get("carts") or {}).items() if isinstance(d.get("carts"), dict) else []:
                cc = self._clean_cart(cid, c)
                if cc:
                    carts[cc["id"]] = cc
            self._data = {"format": FORMAT, "carts": carts}
        return self._data

    @staticmethod
    def _clean_cart(cid, c) -> dict | None:
        if not isinstance(c, dict) or not re.fullmatch(r"c_[0-9a-f]{6,32}", str(cid)):
            return None
        out = {"id": str(cid), "name": _txt(c.get("name"), 120) or DEFAULT_NAME,
               "store": c.get("store") if c.get("store") in STORES else "beatport",
               "created": int(c.get("created") or 0), "status": "bought" if c.get("status") == "bought" else "open",
               "auto": c.get("auto", True) is not False,
               "items": [y for y in (clean_item(x) for x in c.get("items") or []) if y]}
        for k in ("closed", "archived", "checked"):
            try:
                v = int(c.get(k) or 0)
            except (TypeError, ValueError):
                v = 0
            if v:
                out[k] = v
        if out["status"] == "bought":
            out["closed_by"] = "hand" if c.get("closed_by") == "hand" else "auto"
        if isinstance(c.get("pushed"), dict):
            out["pushed"] = {k: v for k, v in c["pushed"].items() if k in STORES and isinstance(v, dict)}
        return out

    def save(self):
        os.makedirs(self.root, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)
        self._mtime = self._stamp()

    # ------------------------------------------------------------------ Abfragen
    def carts(self, archived=None) -> list[dict]:
        """Körbe: offene zuerst (neueste oben), dann gekaufte (zuletzt abgeschlossen oben)."""
        cs = [c for c in self.data["carts"].values() if archived is None or bool(c.get("archived")) == archived]
        return sorted(cs, key=lambda c: (c["status"] == "bought", -(c.get("closed") or 0) if c["status"] == "bought"
                                         else -c.get("created", 0), c["name"].lower()))

    def get(self, cid) -> dict:
        c = self.data["carts"].get(str(cid or ""))
        if c is None:
            raise ValueError("Warenkorb nicht gefunden.")
        return c

    def exists(self, cid) -> bool:
        return str(cid or "") in self.data["carts"]

    def next_name(self, day=None) -> str:
        """#433: Vorschlag für einen neuen Korb – Warenkorb_JJJJ_MM_TT, am selben Tag _2, _3 … (auch gegen archivierte)."""
        t = time.localtime(day if day is not None else time.time())
        base = NAME_TEMPLATE.format(y=t.tm_year, m=t.tm_mon, d=t.tm_mday)
        taken = {c["name"].lower() for c in self.data["carts"].values()}
        if base.lower() not in taken:
            return base
        k = 2
        while f"{base}_{k}".lower() in taken:
            k += 1
        return f"{base}_{k}"

    def unique_name(self, name) -> str:
        name = _txt(name, 120) or DEFAULT_NAME
        taken = {c["name"].lower() for c in self.data["carts"].values() if not c.get("archived")}
        if name.lower() not in taken:
            return name
        k = 2
        while f"{name} ({k})".lower() in taken:
            k += 1
        return f"{name} ({k})"

    # ------------------------------------------------------------------ Ändern (mit Rückgängig)
    def change(self, label: str, fn) -> bool:
        """fn(carts) ändert das Wörterbuch der Körbe und gibt True zurück, wenn etwas geändert wurde."""
        before = copy.deepcopy(self.data["carts"])
        if not fn(self.data["carts"]):
            return False
        self.undo_stack.append((label, before))
        del self.undo_stack[:-UNDO_MAX]
        self.save()
        return True

    def quiet(self, fn) -> bool:
        """Änderung ohne Rückgängig-Eintrag (automatisch gekauft, Ergebnis einer Prüfung, gesendet)."""
        if fn(self.data["carts"]):
            self.save()
            return True
        return False

    def undo(self) -> str:
        if not self.undo_stack:
            raise ValueError("Nichts rückgängig zu machen.")
        label, carts = self.undo_stack.pop()
        self.data["carts"] = carts
        self.save()
        return label

    def create(self, name="", store="beatport", items=None) -> dict:
        cid = "c_" + secrets.token_hex(6)
        c = {"id": cid, "name": self.unique_name(name) if _txt(name) else self.next_name(), "store": store if store in STORES else "beatport",
             "created": int(time.time()), "status": "open", "auto": True,
             "items": [y for y in (clean_item(x) for x in items or []) if y]}

        def fn(carts):
            carts[cid] = c
            return True
        self.change("Warenkorb anlegen", fn)
        return c
