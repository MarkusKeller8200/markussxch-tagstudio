"""Mehrsprachigkeit (#157): Sprachen und Kataloge der Oberfläche.

Ausgangssprache ist Schweizer Hochdeutsch (``de-CH``) – so steht der Text im Code. Die Kataloge liegen je Modul in
``web/i18n/<modul>.json``: deutscher Text (Schlüssel) → ``[Englisch, Zürichdeutsch]`` (Reihenfolge wie ``COLUMNS``) –
so steht jeder Text mit allen Übersetzungen beisammen. Platzhalter: ``{n}`` Zahl, ``{q}`` Text in
Anführungszeichen, ``{x}`` beliebiger eingesetzter Text (wird seinerseits übersetzt). Übersetzt wird in der Oberfläche
(``web/i18n.js``); MP3-Tags werden nie übersetzt. Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import threading

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DIR = os.path.join(WEB, "i18n")
SOURCE = "de-CH"
# (Code nach BCP 47, Name in der eigenen Sprache, Flagge, Name auf Deutsch)
LANGS = [
    ("de-CH", "Deutsch", "🇩🇪🇨🇭", "Deutsch"),           # für Deutschland und die Schweiz gleich (Entscheid 17.10.2026)
    ("en", "English", "🇬🇧", "Englisch"),
    ("gsw-u-sd-chzh", "Züritüütsch", "🦁", "Zürichdeutsch"),
]
CODES = tuple(c for c, *_ in LANGS)
AUTO = "auto"                                # gespeicherte Wahl „Sprache des Betriebssystems“
COLUMNS = ("en", "gsw-u-sd-chzh")            # Spalten in den Katalogdateien
_lock = threading.Lock()
_cache: dict[str, tuple[tuple, dict]] = {}


def _files() -> list[str]:
    try:
        return sorted(os.path.join(DIR, f) for f in os.listdir(DIR) if f.endswith(".json") and not f.startswith("_")
                      and f != "ignore.json")
    except OSError:
        return []


def shipped(lang: str) -> dict[str, str]:
    """Mitgelieferter Katalog einer Sprache (alle Dateien zusammengeführt, zwischengespeichert je Änderungszeit)."""
    if lang not in COLUMNS:
        return {}
    files, col = _files(), COLUMNS.index(lang)
    stamp = tuple((f, os.path.getmtime(f)) for f in files)
    with _lock:
        hit = _cache.get(lang)
        if hit and hit[0] == stamp:
            return hit[1]
    out: dict[str, str] = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        for k, v in d.items():
            if isinstance(k, str) and isinstance(v, list) and len(v) > col and isinstance(v[col], str) and v[col]:
                out[k] = v[col]
    with _lock:
        _cache[lang] = (stamp, out)
    return out


def source_keys() -> list[str]:
    """Alle Texte der Ausgangssprache, die mitgeliefert übersetzt sind (Reihenfolge wie in den Dateien)."""
    keys: dict[str, None] = {}
    for f in _files():
        try:
            with open(f, encoding="utf-8") as fh:
                keys.update(dict.fromkeys(json.load(fh)))
        except (OSError, ValueError):
            continue
    return list(keys)


# ---------------------------------------------------------------- Plugins anderer Anbieter (#219)
def plugin_texts(lang: str) -> dict[str, str]:
    """Übersetzungen aus plugin.json "i18n": {"en": {"Deutscher Text": "English"}} – mitgelieferte und eigene Plugins."""
    out: dict[str, str] = {}
    try:
        import plugins as pl
        dirs = [pl.BUILTIN_DIR, pl.user_dir()]
    except Exception:  # noqa: BLE001
        return out
    for base in dirs:
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for n in names:
            p = os.path.join(base, n, "plugin.json")
            try:
                with open(p, encoding="utf-8") as fh:
                    d = (json.load(fh).get("i18n") or {}).get(lang) or {}
            except (OSError, ValueError, AttributeError):
                continue
            if isinstance(d, dict):
                out.update({k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, str) and v.strip()})
    return out


# ---------------------------------------------------------------- eigene Anpassungen je Benutzer/Profil (#219)
def overlay_dir() -> str:
    import paths
    return paths.sub("Sprachen")


def _overlay_file(lang: str) -> str:
    if lang not in CODES:
        raise ValueError(f"Unbekannte Sprache: {lang}")
    return os.path.join(overlay_dir(), f"{lang}.json")


def overlay(lang: str) -> dict[str, str]:
    """Eigene Texte des Benutzers – überlagern die mitgelieferten, Updates überschreiben sie nie."""
    try:
        with open(_overlay_file(lang), encoding="utf-8") as fh:
            d = json.load(fh).get("texts") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return {k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, str) and v.strip()}


def catalog(lang: str) -> dict[str, str]:
    """Wirksamer Katalog: mitgeliefert → Plugin-Übersetzungen → eigene Anpassungen (Vorrang in dieser Reihenfolge)."""
    if lang not in CODES:
        return {}
    out = dict(shipped(lang)) if lang != SOURCE else {}
    out.update(plugin_texts(lang))
    out.update(overlay(lang))
    return out


import re as _re  # noqa: E402

_PH = _re.compile(r"\{[nqx]\}")
_HTML = _re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>")


def _ph(s: str) -> list[str]:
    return sorted(_PH.findall(s))


def export_rows(lang: str) -> list[dict]:
    """Alle Texte mit mitgelieferten Übersetzungen und den eigenen Texten der gewählten Sprache."""
    cols = {c: shipped(c) for c in COLUMNS}
    own = overlay(lang)
    return [{"key": k, **{c: cols[c].get(k, "") for c in COLUMNS}, "own": own.get(k, "")} for k in source_keys()]


def export_text(lang: str, fmt: str = "csv") -> str:
    rows = export_rows(lang)
    if fmt == "json":
        return json.dumps({"tagstudio_texts": 1, "lang": lang,
                           "texts": {r["key"]: r["own"] or (r[lang] if lang in COLUMNS else r["key"]) for r in rows}},
                          ensure_ascii=False, indent=1)
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(["de-CH", *COLUMNS, f"eigene:{lang}"])
    for r in rows:
        w.writerow([r["key"], *(r[c] for c in COLUMNS), r["own"]])
    return "\ufeff" + buf.getvalue()                 # BOM: Excel erkennt UTF-8


def _parse(lang: str, text: str) -> dict[str, str]:
    """CSV (Spalte „eigene:<lang>“, sonst die Sprachspalte) oder JSON {"texts": {…}} bzw. {Text: Übersetzung}."""
    t = (text or "").lstrip("\ufeff").strip()
    if not t:
        raise ValueError("Die Datei ist leer.")
    if t[0] in "{[":
        d = json.loads(t)
        d = d.get("texts", d) if isinstance(d, dict) else {}
        if not isinstance(d, dict):
            raise ValueError("JSON: erwartet wird ein Objekt mit Texten.")
        return {str(k): str(v) for k, v in d.items() if isinstance(v, (str, int, float))}
    import csv
    import io
    rd = list(csv.reader(io.StringIO(t), delimiter=";" if t.split("\n", 1)[0].count(";") >= t.split("\n", 1)[0].count(",") else ","))
    if not rd:
        return {}
    head = [h.strip().lower() for h in rd[0]]
    if "de-ch" not in head:
        raise ValueError("CSV: Spalte „de-CH“ fehlt (Datei aus „Texte exportieren“ verwenden).")
    ki = head.index("de-ch")
    oi = head.index(f"eigene:{lang}".lower()) if f"eigene:{lang}".lower() in head else -1
    li = head.index(lang.lower()) if lang.lower() in head else -1
    out = {}
    for row in rd[1:]:
        if len(row) <= ki or not row[ki].strip():
            continue
        own = row[oi].strip() if 0 <= oi < len(row) else ""
        val = own or (row[li].strip() if 0 <= li < len(row) else "")
        if val:
            out[row[ki]] = val
    return out


def import_preview(lang: str, text: str) -> dict:
    """Prüft eine Datei: unbekannte Texte, Platzhalter {n}/{q}/{x}, HTML, Länge. → {rows, ok, errors, warnings, unchanged}"""
    if lang not in CODES:
        raise ValueError(f"Unbekannte Sprache: {lang}")
    data = _parse(lang, text)
    known = set(source_keys())
    base = shipped(lang) if lang != SOURCE else {}
    cur = catalog(lang)
    rows, ok = [], {}
    n_err = n_warn = n_same = 0
    for k, v in data.items():
        v = v.strip()
        status, note = "ok", ""
        if k not in known:
            status, note = "error", "unbekannter Text"
        elif _ph(k) != _ph(v):
            status, note = "error", "Platzhalter {n}/{q}/{x} stimmen nicht überein"
        elif _HTML.search(v):
            status, note = "error", "HTML ist nicht erlaubt"
        elif v == cur.get(k, k if lang == SOURCE else None):
            status, note = "same", "unverändert"
        elif len(v) > max(40, int(len(k) * 2.5)):
            status, note = "warn", "deutlich länger als das Original – passt evtl. nicht auf Knöpfe"
        if status == "error":
            n_err += 1
        elif status == "same":
            n_same += 1
            continue
        else:
            n_warn += status == "warn"
            ok[k] = v
        rows.append({"key": k, "old": cur.get(k, base.get(k, "")), "new": v, "status": status, "note": note})
    return {"rows": rows[:3000], "count": len(ok), "errors": n_err, "warnings": n_warn, "unchanged": n_same, "texts": ok}


def import_apply(lang: str, text: str) -> dict:
    pv = import_preview(lang, text)
    cur = overlay(lang)
    cur.update(pv["texts"])
    os.makedirs(overlay_dir(), exist_ok=True)
    tmp = _overlay_file(lang) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"tagstudio_texts": 1, "lang": lang, "texts": cur}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _overlay_file(lang))
    return {"count": pv["count"], "total": len(cur)}


def overlay_reset(lang: str) -> int:
    """Eigene Anpassungen einer Sprache entfernen (die Datei wird gelöscht – nach Rückfrage in der Oberfläche)."""
    n = len(overlay(lang))
    try:
        os.remove(_overlay_file(lang))
    except FileNotFoundError:
        pass
    return n


def detect(accept: str | None) -> str:
    """Sprache aus der System-/Browsersprache (erster Start): en… → en, gsw… → Zürichdeutsch, sonst de-CH."""
    a = (accept or "").strip().lower()
    if a.startswith("gsw"):
        return "gsw-u-sd-chzh"
    if a.startswith("de") or not a:
        return SOURCE
    return "en"


def langs() -> list[dict]:
    return [{"code": c, "name": n, "flag": f, "de": d} for c, n, f, d in LANGS]
