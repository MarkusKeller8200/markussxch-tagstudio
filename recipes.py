"""MarKusSXCH TagStudio – Tag-Rezepte (#111): wiederverwendbare Aktionslisten wie in Mp3tag.

Ein Rezept ist {"id", "name", "actions": [...]}. Aktionen (alle mit Vorschau, angewendet mit Rückgängig):
  replace      {"find", "repl", "fields": "all"|[Schlüssel/Muster], "case": bool, "regex": bool, "word": bool}
  words        {"words": ["DJ", "feat.", …], "fields": …}   Schreibweise einzelner Wörter festlegen
  case         {"mode": "title"|"sentence"|"upper"|"lower", "fields": …}
  dedupe       {}                                           doppelte Werte/Felder mit gleichem Inhalt entfernen
  first_value  {"fields": [...]}                            nur den ersten Wert behalten (Mp3tag $meta(X,0))
  remove       {"fields": [Muster]}                         Felder entfernen (z. B. "COMM*")
  set          {"field", "value"}                           Feld setzen (leer = entfernen); %FELD% wird ersetzt
  trim         {"fields": …}                                Leerzeichen am Anfang/Ende und doppelte entfernen
  version      {"v2": 0|3|4, "v1": "keep"|"write"|"remove"} ID3-Version beim Speichern
Nur Standardbibliothek.
"""
from __future__ import annotations

import copy
import fnmatch
import re
import uuid

import tagger
from id3tags import MV, field_name

ACTION_TYPES = {
    "replace": "Ersetzen", "words": "Schreibweise von Wörtern", "case": "Gross-/Kleinschreibung",
    "dedupe": "Doppelte Felder/Werte entfernen", "first_value": "Nur ersten Wert behalten", "remove": "Felder entfernen",
    "set": "Feld setzen", "trim": "Leerzeichen bereinigen", "version": "ID3-Version beim Speichern",
}

# Vorlage nach dem Mp3tag-Schritt des Users (Workflow 02) – ohne persönliche Pfade
DEFAULT = [{
    "id": "beatport-download", "name": "Beatport-Download aufbereiten", "builtin": True,
    "actions": [
        {"type": "replace", "find": "%20", "repl": " ", "fields": "all"},
        {"type": "replace", "find": "_", "repl": " ", "fields": "all"},
        {"type": "trim", "fields": "all"},
        {"type": "words", "words": ["Dj", "Feat", "Mc", "Vs"], "fields": "all"},
        {"type": "dedupe"},
        {"type": "first_value", "fields": ["TXXX:FILETYPE"]},
        {"type": "remove", "fields": ["TXXX:COMMENT", "COMM*"]},
        {"type": "version", "v2": 4, "v1": "write"},
    ],
}]


def defaults() -> list:
    return copy.deepcopy(DEFAULT)


def clean(recipes) -> list:
    """Rezepte aus der Oberfläche prüfen (unbekannte Aktionen fallen weg)."""
    out = []
    for r in recipes or []:
        if not isinstance(r, dict):
            continue
        acts = [a for a in (r.get("actions") or []) if isinstance(a, dict) and a.get("type") in ACTION_TYPES]
        name = str(r.get("name") or "").strip()[:80] or "Rezept"
        out.append({"id": str(r.get("id") or uuid.uuid4().hex[:8])[:40], "name": name, "actions": acts,
                    **({"builtin": True} if r.get("builtin") else {})})
    return out


def describe(a: dict) -> str:
    """Kurztext einer Aktion für die Liste."""
    t = a.get("type")
    f = a.get("fields", "all")
    fs = "alle Textfelder" if f in ("all", None) else ", ".join(f)
    if t == "replace":
        return f"„{a.get('find', '')}“ → „{a.get('repl', '')}“ in {fs}"
    if t == "words":
        return f"Wörter so schreiben: {', '.join(a.get('words') or [])} ({fs})"
    if t == "case":
        return f"{tagger.CASE_MODES.get(a.get('mode'), a.get('mode'))} in {fs}"
    if t == "dedupe":
        return "Doppelte Werte und gleiche Doppel-Felder entfernen"
    if t == "first_value":
        return f"Nur den ersten Wert behalten: {fs}"
    if t == "remove":
        return f"Entfernen: {fs}"
    if t == "set":
        return f"{a.get('field', '')} = „{a.get('value', '')}“"
    if t == "trim":
        return f"Leerzeichen bereinigen in {fs}"
    if t == "version":
        v1 = {"write": "mit ID3v1", "remove": "ohne ID3v1"}.get(a.get("v1"), "ID3v1 wie vorhanden")
        return f"Speichern als {'ID3v2.' + str(a.get('v2')) if a.get('v2') in (3, 4) else 'bisherige ID3-Version'}, {v1}"
    return t or "?"


def _match(key: str, pats) -> bool:
    if pats in ("all", None):
        return True
    k = key.split("#")[0].lower()
    for p in pats:
        p = str(p).lower()
        if fnmatch.fnmatchcase(k, p) or k == p or (p.endswith(":") and k.startswith(p)) \
                or field_name(key).lower() == p:
            return True
    return False


def _keys(f, pats):
    return [k for k, _it in tagger._text_items(f, None) if _match(k, pats)]


class _Work:
    """Arbeitskopie der Textwerte einer Datei, damit Aktionen aufeinander aufbauen."""

    def __init__(self, f):
        self.f = f
        self.vals = {k: it.text for k, it in tagger._text_items(f, None)}
        self.removed = set()
        self.version = None
        self.v1 = None

    def get(self, k):
        return self.vals.get(k, "")

    def put(self, k, v):
        if k in self.removed:
            self.removed.discard(k)
        self.vals[k] = v


def _apply_action(w: _Work, a: dict):
    t = a.get("type")
    pats = a.get("fields", "all")
    keys = [k for k in list(w.vals) if k not in w.removed and _match(k, pats)]
    if t == "replace":
        find = a.get("find") or ""
        if not find:
            return
        pat = find if a.get("regex") else re.escape(find)
        if a.get("word"):
            pat = rf"\b(?:{pat})\b"
        rx = re.compile(pat, 0 if a.get("case") else re.I)
        repl = a.get("repl", "")
        for k in keys:
            w.put(k, rx.sub(repl if a.get("regex") else repl.replace("\\", "\\\\"), w.get(k)))
    elif t == "words":
        for word in a.get("words") or []:
            word = str(word).strip()
            if not word:
                continue
            rx = re.compile(rf"(?<![\w]){re.escape(word.rstrip('.'))}(\.?)(?![\w])", re.I)
            keep_dot = word.endswith(".")
            for k in keys:
                w.put(k, rx.sub(lambda m: word.rstrip(".") + ("." if keep_dot else m.group(1)), w.get(k)))
    elif t == "case":
        for k in keys:
            w.put(k, tagger.change_case(w.get(k), a.get("mode", "title"), True, bool(a.get("small_words"))))
    elif t == "trim":
        for k in keys:
            w.put(k, MV.join(re.sub(r"\s{2,}", " ", v).strip() for v in w.get(k).split(MV)))
    elif t == "dedupe":
        for k in list(w.vals):
            if k in w.removed:
                continue
            cur = w.get(k)
            sep = MV if MV in cur or " / " not in cur else " / "     # ID3v2.3: Mehrfachwerte mit „ / “
            vals, seen = [], set()
            for v in cur.split(sep):
                if v.strip().lower() not in seen:
                    seen.add(v.strip().lower())
                    vals.append(v.strip() if sep != MV else v)
            if len(vals) < len(cur.split(sep)):
                w.put(k, sep.join(vals))
        for k in list(w.vals):                   # „TXXX:X#2“ mit gleichem Inhalt wie „TXXX:X“
            base = k.split("#")[0]
            if "#" in k and base in w.vals and base not in w.removed and w.get(k).strip() == w.get(base).strip():
                w.removed.add(k)
    elif t == "first_value":
        for k in keys:
            v = w.get(k)
            first = v.split(MV)[0]
            if " / " in first and k.split(":")[0] in ("TXXX",):
                first = first.split(" / ")[0]
            w.put(k, first.strip())
    elif t == "remove":
        for k in list(w.f.items):
            if _match(k, pats if pats not in ("all", None) else []):
                w.removed.add(k)
    elif t == "set":
        key = str(a.get("field") or "").strip()
        if not key:
            return
        val = re.sub(r"%([A-Za-z0-9:_ ]+)%", lambda m: w.get(m.group(1)) or w.get(m.group(1).upper()), str(a.get("value", "")))
        if val:
            w.put(key, val)
        else:
            w.removed.add(key)
    elif t == "version":
        if a.get("v2") in (3, 4):
            w.version = a["v2"]
        if a.get("v1") in ("write", "remove"):
            w.v1 = a["v1"]


def plan(files, recipe: dict) -> list[dict]:
    """→ je Datei {"file", "changes": [(key, alt, neu)], "version": int|None, "v1": str|None}"""
    out = []
    for f in files:
        w = _Work(f)
        for a in recipe.get("actions") or []:
            try:
                _apply_action(w, a)
            except re.error as ex:
                raise ValueError(f"Ungültiger regulärer Ausdruck in „{describe(a)}“: {ex}") from ex
        changes = []
        for k in sorted(set(w.vals) | w.removed):
            old = f.get(k).text if f.get(k) is not None and f.get(k).kind not in ("picture", "raw") else \
                ("(Binärfeld)" if f.get(k) is not None else "")
            if k in w.removed:
                if f.get(k) is not None:
                    changes.append((k, old, None))
                continue
            new = w.get(k)
            if new != old:
                changes.append((k, old, new))
        ver = w.version if w.version and w.version != f.version else None
        v1 = w.v1 if (w.v1 == "write" and not f.had_v1) or (w.v1 == "remove" and f.had_v1) else None
        if changes or ver or v1:
            out.append({"file": f, "changes": changes, "version": ver, "v1": v1, "v1_keep": w.v1})
    return out


def apply(p: list[dict]) -> int:
    """Plan anwenden (ohne Speichern). → Anzahl geänderter Dateien."""
    import core
    n = 0
    for e in p:
        f = e["file"]
        for k, _old, new in e["changes"]:
            if new is None:
                f.set(k, None)
            else:
                core.apply_value(f, k, new)
        if e["version"]:
            f.set_version(e["version"])
        if e.get("v1_keep"):
            f.v1_mode = e["v1_keep"]
        n += 1
    return n
