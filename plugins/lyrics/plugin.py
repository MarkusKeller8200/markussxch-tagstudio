"""Liedtexte von LRCLIB (4.5.0, #183).

LRCLIB (https://lrclib.net) ist frei und braucht keinen Schlüssel. Abfrage zuerst genau (`/api/get` mit Künstler, Titel,
Album, Dauer), sonst über die Suche (`/api/search`); bewertet wie bei Online-Metadaten (Titel, Künstler, Mix, Länge).
Original-, Remix- und Live-Versionen werden nicht gleichgesetzt (`version_score`): Extended Mix, Radio Edit u. Ä.
gelten als Original; eine abweichende Fassung kostet 15 Punkte und ist höchstens „unsicher“ (nie vorausgewählt).

Speichern (Entscheid des Projektverantwortlichen, 16.10.2026):
- normaler Text → `USLT` (Liedtext, ungetaktet)
- synchronisierter Text → `SYLT` (Zeitstempel in Millisekunden, Textkodierung UTF-16 – lesbar in v2.3 und v2.4)
- zusätzlich eine `.lrc`-Datei neben dem MP3, NUR wenn sie in den Plugin-Einstellungen eingeschaltet ist
  (Plugins › Liedtexte › „Einstellungen …“, gespeichert in settings.json im Datenordner des Plugins)
- vorhandene Liedtexte bzw. eine vorhandene .lrc-Datei werden nie ohne Häkchen ersetzt (Vorschlag nicht vorausgewählt)

Alles als Vorschlag mit Vorschau; Tags werden erst beim Speichern geschrieben, die .lrc-Datei beim Übernehmen.
Nur Standardbibliothek.
"""
import json
import os
import re
import urllib.parse

import onlinematch as om
from onlinematch import HttpError, MAYBE, SURE

try:
    from version import VERSION
except Exception:  # noqa: BLE001
    VERSION = "4"

USER_AGENT = f"TagStudio/{VERSION} ( https://github.com/MarkusKeller8200/markussxch-tagstudio )"
API = "https://lrclib.net/api"
INTERVALS = {"lrclib.net": 0.5}                    # höflich: höchstens 2 Anfragen pro Sekunde, nacheinander

http_get = om.http_get                             # in Tests ersetzbar

ACTIONS = [
    {
        "id": "fetch", "label": "Liedtexte suchen (LRCLIB) …", "where": "tagger", "run_label": "Suchen",
        "description": "Sucht die Liedtexte der markierten Titel bei LRCLIB und schlägt sie zur Übernahme vor. "
                       "Vorhandene Liedtexte werden nur ersetzt, wenn du sie anhakst.",
        "options": [
            {"key": "what", "type": "select", "label": "Was übernehmen",
             "choices": [["both", "Text (USLT) und synchronisiert (SYLT)"], ["plain", "Nur Text (USLT)"],
                         ["synced", "Nur synchronisiert (SYLT)"]], "default": "both"},
            {"key": "id", "type": "check", "label": "LRCLIB-ID speichern (TXXX:LRCLIB_ID)", "default": True},
            {"type": "info", "label": ".lrc-Datei und Sprache: Plugins › Liedtexte › „Einstellungen …“. "
                                      "Liedtexte sind urheberrechtlich geschützt – nur für den eigenen Gebrauch, nicht weitergeben."},
        ],
    },
    {
        "id": "settings", "label": "Einstellungen …", "where": "page", "run_label": "Speichern", "needs_selection": False,
        "description": "Gilt für jede Liedtext-Suche.",
        "options": [
            {"key": "lrc", "type": "check", "label": "Zusätzlich .lrc-Datei neben dem MP3 schreiben (synchronisierter Text, "
                                                     "gleicher Name wie das MP3)", "default": False},
            {"key": "lang", "type": "text", "label": "Sprache für USLT/SYLT (ISO-639-2, z. B. eng, deu)", "default": "eng"},
        ],
    },
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft, ob LRCLIB erreichbar ist.", "options": []},
]


# =========================================================================== Einstellungen
DEFAULTS = {"lrc": False, "lang": "eng"}


def _settings_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "settings.json")


def load_settings(ctx) -> dict:
    out = dict(DEFAULTS)
    try:
        with open(_settings_path(ctx), encoding="utf-8") as fh:
            d = json.load(fh)
        if isinstance(d, dict):
            out["lrc"] = bool(d.get("lrc", out["lrc"]))
            out["lang"] = clean_lang(d.get("lang"))
    except (OSError, ValueError):
        pass
    return out


def clean_lang(v) -> str:
    """ISO-639-2: drei Buchstaben, sonst „eng“."""
    v = str(v or "").strip().lower()
    return v if re.fullmatch(r"[a-z]{3}", v) else "eng"


def save_settings(ctx, opts) -> dict:
    d = {"lrc": bool(opts.get("lrc")), "lang": clean_lang(opts.get("lang"))}
    tmp = _settings_path(ctx) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    os.replace(tmp, _settings_path(ctx))
    return d


# =========================================================================== LRC und SYLT
_STAMP = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def parse_lrc(text: str) -> list[tuple[int, str]]:
    """LRC-Text → [(Millisekunden, Zeile)], nach Zeit sortiert. Mehrere Zeitstempel je Zeile erlaubt; Kopfzeilen wie
    [ar:…] und Zeilen ohne Zeitstempel werden übergangen. Hundertstel (2 Ziffern) und Tausendstel (3) werden erkannt."""
    out = []
    for line in str(text or "").splitlines():
        stamps, pos = [], 0
        while True:
            m = _STAMP.match(line, pos)
            if not m:
                break
            mm, ss, frac = int(m.group(1)), int(m.group(2)), m.group(3) or "0"
            ms = int(frac.ljust(3, "0")[:3]) if len(frac) != 2 else int(frac) * 10
            stamps.append((mm * 60 + ss) * 1000 + ms)
            pos = m.end()
        if stamps:
            txt = line[pos:].strip()
            out.extend((t, txt) for t in stamps)
    out.sort(key=lambda x: x[0])
    return out


def plain_from_lrc(text: str) -> str:
    """Normaler Text aus synchronisiertem (falls LRCLIB nur diesen liefert)."""
    return "\n".join(t for _ms, t in parse_lrc(text)).strip()


def _u16(s: str) -> bytes:
    return b"\xff\xfe" + s.encode("utf-16-le") + b"\x00\x00"


def sylt_payload(lines: list[tuple[int, str]], lang: str = "eng") -> bytes:
    """SYLT-Rumpf: Kodierung 1 (UTF-16 mit BOM), Sprache, Zeitformat 2 (ms), Inhalt 1 (Liedtext), leere Beschreibung,
    dann je Zeile Text + 4-Byte-Zeitstempel."""
    lang = (lang or "eng").lower()[:3].ljust(3, "x").encode("latin-1", "replace")
    body = b"\x01" + lang + b"\x02\x01" + _u16("")
    for ms, txt in lines:
        body += _u16(txt) + int(max(0, ms)).to_bytes(4, "big")
    return body


# =========================================================================== LRCLIB
def _client(ctx):
    return om.Client(USER_AGENT, INTERVALS, get=lambda url, h: http_get(url, h), cancel=ctx.check_cancel)


def _cand(d: dict) -> dict:
    title, mix = om.split_title(d.get("trackName") or "")
    return {"source": "lrclib", "id": d.get("id"), "title": title, "mix": mix,
            "artists": [a.strip() for a in re.split(r",|&| feat\.? | ft\.? ", d.get("artistName") or "") if a.strip()],
            "length": float(d.get("duration") or 0) or None, "album": d.get("albumName") or "",
            "plain": d.get("plainLyrics") or "", "synced": d.get("syncedLyrics") or "",
            "instrumental": bool(d.get("instrumental")),
            "label_text": f"{d.get('artistName') or ''} – {d.get('trackName') or ''}"}


def candidates(cl, info: dict) -> list:
    """Genaue Abfrage (Dauer ±2 s auf LRCLIB-Seite), sonst Suche nach Titel und Künstler."""
    full_title = f"{info['title']} ({info['mix']})" if info.get("mix") else info["title"]
    artist = info["artist"]
    out = []
    if info.get("duration") and info.get("album"):          # /api/get verlangt Album und Dauer, sonst HTTP 400
        q = {"artist_name": artist, "track_name": full_title, "album_name": info["album"],
             "duration": int(round(info["duration"]))}
        try:
            d = cl.json(f"{API}/get?" + urllib.parse.urlencode(q))
        except HttpError as ex:
            if ex.status not in (400, 404):                  # nur „unpassende Anfrage“ → weiter mit der Suche
                raise
            d = None
        if isinstance(d, dict) and d.get("id"):
            out.append(_cand(d))
    if not out:
        q = {"track_name": info["title"], "artist_name": om.first_artist(info)}
        d = cl.json(f"{API}/search?" + urllib.parse.urlencode(q))
        if isinstance(d, list):
            out.extend(_cand(x) for x in d[:20] if isinstance(x, dict))
    return out


# =========================================================================== Versionen
# Gleicher Liedtext wie das Original: Extended Mix, Radio Edit usw. Abweichend: Remix, Live, Acoustic, Rework …
_ORIGINAL_LIKE = {"", "original", "original mix", "extended", "extended mix", "extended version", "radio edit",
                  "radio mix", "radio version", "edit", "main mix", "album version", "single version"}


def _mix_kind(mix: str) -> str:
    return "original" if om.norm(mix) in {om.norm(x) for x in _ORIGINAL_LIKE} else om.norm(mix)


def version_score(info: dict, c: dict) -> float:
    """Wie onlinematch.score, aber Original/Remix/Live nicht gleichsetzen: abweichende Fassung −0,15 und höchstens
    „unsicher“ (unter SURE) – sie wird gezeigt, aber nie vorausgewählt."""
    s = om.score(info, c)
    a, b = _mix_kind(info.get("mix") or ""), _mix_kind(c.get("mix") or "")
    if a != b:
        s = min(s - 0.15, SURE - 0.01)
    return max(0.0, min(1.0, s))


def best(info: dict, cands: list):
    scored = sorted(((version_score(info, c), i, c) for i, c in enumerate(cands)), key=lambda x: (-x[0], x[1]))
    return (scored[0][2], scored[0][0]) if scored else (None, 0.0)


# =========================================================================== Vorschläge
def _existing(f, prefix: str):
    """Erster vorhandener Schlüssel eines Frame-Typs (z. B. USLT:… / SYLT), sonst None."""
    return next((k for k in f.items if k == prefix or k.startswith(prefix + ":") or k.startswith(prefix + "#")), None)


def propose_file(ctx, f, c: dict, s: float, opts: dict, group: str) -> int:
    sure = s >= SURE
    note = f"LRCLIB: {c['label_text']} ({round(s * 100)} %)" + ("" if sure else " – unsicher, nicht vorausgewählt")
    what = opts.get("what") or "both"
    lang = clean_lang(opts.get("lang"))
    plain = c["plain"].strip() or plain_from_lrc(c["synced"])
    lines = parse_lrc(c["synced"])
    n = 0
    if what in ("both", "plain") and plain:
        key = _existing(f, "USLT")
        if key and f.text(key).strip() == plain:
            ctx.propose(f, key, plain, "Liedtext (USLT)", note=note, checked=False, group=group, hint="gleich", show_same=True)
        elif key:
            n += ctx.propose(f, key, plain, "Liedtext (USLT)", note=note, checked=False, group=group,
                             hint="Liedtext vorhanden – nur mit Häkchen ersetzen")
        else:
            n += ctx.propose(f, "USLT:", plain, "Liedtext (USLT)", note=note, checked=sure, group=group)
    if what in ("both", "synced") and lines:
        key = _existing(f, "SYLT") or "SYLT"
        has = f.get(key) is not None
        n += ctx.propose(f, key, f"{len(lines)} Zeilen mit Zeitstempel ({lang})", "Synchronisierter Liedtext (SYLT)",
                         note=note, checked=sure and not has, kind="frame", data=sylt_payload(lines, lang), group=group,
                         hint="synchronisierter Liedtext vorhanden – nur mit Häkchen ersetzen" if has else "")
    if opts.get("lrc") and c["synced"].strip():
        path = os.path.splitext(f.path)[0] + ".lrc"
        has = os.path.exists(path)
        n += ctx.propose(f, path, os.path.basename(path), "LRC-Datei", note=note, checked=sure and not has, kind="file",
                         data=c["synced"].strip().encode("utf-8") + b"\n", group=group,
                         hint=".lrc-Datei vorhanden – nur mit Häkchen ersetzen" if has else "wird beim Übernehmen geschrieben")
    if opts.get("id", True) and c.get("id") and n:
        ctx.propose(f, "TXXX:LRCLIB_ID", str(c["id"]), "LRCLIB-ID", note=note, checked=sure, group=group)
    return n


def status(ctx):
    st = load_settings(ctx)
    return f"LRCLIB: frei, ohne Schlüssel · .lrc-Datei: {'ja' if st['lrc'] else 'nein'} · Sprache: {st['lang']}"


def run(action, ctx, files, opts):
    if action == "settings":
        d = save_settings(ctx, opts)
        msg = f"Gespeichert: .lrc-Datei {'ja' if d['lrc'] else 'nein'}, Sprache {d['lang']}."
        ctx.log(msg)
        return {"message": msg}
    cl = _client(ctx)
    if action == "test":
        try:
            cl.json(f"{API}/search?" + urllib.parse.urlencode({"q": "test"}))
            msg = "LRCLIB ist erreichbar."
        except HttpError as ex:
            msg = f"LRCLIB: {ex}"
        ctx.log(msg)
        return {"message": msg}
    if action != "fetch":
        raise ValueError(f"Unbekannte Aktion: {action}")
    opts = {**opts, **load_settings(ctx)}             # .lrc und Sprache aus den Plugin-Einstellungen
    found = unsure = missing = instrumental = 0
    for i, f in enumerate(files):
        name = os.path.basename(f.path)
        ctx.progress(i, len(files), f"Suche {name}")
        info = om.file_info(f)
        if not info["title"]:
            ctx.log(f"{name}: kein Titel – übersprungen")
            missing += 1
            continue
        try:
            c, s = best(info, candidates(cl, info))
        except HttpError as ex:
            if ex.status in (0, 429):
                raise RuntimeError(str(ex)) from ex
            ctx.log(f"{name}: {ex}")
            missing += 1
            continue
        if not c or s < MAYBE:
            ctx.log(f"{name}: nicht gefunden" + (f" (bester Kandidat {c['label_text']}, {round(s * 100)} %)" if c else ""))
            missing += 1
            continue
        if c["instrumental"] or not (c["plain"].strip() or c["synced"].strip()):
            ctx.log(f"{name}: {c['label_text']} – instrumental bzw. ohne Text")
            instrumental += 1
            continue
        ctx.log(f"{name}: {c['label_text']} ({round(s * 100)} %)"
                + (" · synchronisiert" if c["synced"].strip() else " · nur Text"))
        propose_file(ctx, f, c, s, opts, name)
        found += s >= SURE
        unsure += s < SURE
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{found} gefunden" + (f", {unsure} unsicher (nicht vorausgewählt)" if unsure else "") + \
          (f", {instrumental} ohne Text (instrumental)" if instrumental else "") + \
          (f", {missing} nicht gefunden" if missing else "")
    if not ctx.proposals:
        return {"message": f"{msg}. Nichts zu übernehmen."}
    n = sum(1 for p in ctx.proposals if p["checked"])
    return {"message": f"{msg}. {sum(1 for p in ctx.proposals if not p['same'])} Vorschlag/Vorschläge, {n} vorausgewählt."}
