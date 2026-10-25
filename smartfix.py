"""Smart Fix (#339): Rezepte für den Tag-Fixer – mitgelieferte (nicht änderbar, nur kopierbar) und eigene.

Ein Rezept beschreibt einen Mehrfachwerte-Fix mit festen Feldern, Eingangs-Trennern und Ziel-Trenner. Es nutzt
dieselbe Logik wie der Mehrfachwerte-Fixer (`compare.plan_multi_fix`) samt Ausnahmen je Feld (#342), damit Namen wie
„Above & Beyond“ zusammenbleiben. Weitere Rezept-Arten können später über `type` dazukommen.

Rezept: {id, name, desc, type: "multi", fields: [Feld oder Gruppe], seps: [Trenner], out: ", " | "; " | " / " | "v24",
         dedupe: bool}
"""
from __future__ import annotations

import datetime
import json
import re

from compare import EXCEPTION_GROUPS, INPUT_SEPARATORS, MULTI_FIELDS, plan_multi_fix
from id3tags import MV

FORMAT = "tagstudio-smartfix"
OUTPUTS = [  # (Wert, Beschreibung)
    (", ", "Komma"),
    ("; ", "Semikolon"),
    (" / ", "Schrägstrich mit Leerzeichen"),
    ("v24", "ID3v2.4-Mehrfachwert (v2.3-Dateien: „ / “)"),
]
_SEPS = {s for _, s, _ in INPUT_SEPARATORS}
_FIELDS = set(MULTI_FIELDS) | {"TMOO", "TXXX:MOOD"} | set(EXCEPTION_GROUPS)

BUILTIN = [
    {"id": "multi_comma", "name": "Mehrfachwerte mit Komma", "type": "multi", "builtin": True,
     "desc": "Werte, die mit „&“ oder „;“ getrennt sind, mit „, “ verbinden und Doppelte entfernen – Künstler und Mitwirkende, Genre, Stimmung. Ausnahmen je Feld bleiben zusammen.",  # noqa: E501
     "fields": ["@artists", "@genre", "@mood"], "seps": [";", "&"], "out": ", ", "dedupe": True},
]


def builtins() -> list[dict]:
    return [dict(r) for r in BUILTIN]


def builtin_ids() -> set[str]:
    return {r["id"] for r in BUILTIN}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:40]
    return s or "rezept"


def clean(r, taken=()) -> dict | None:
    """Eigenes Rezept bereinigen (nur bekannte Felder, Trenner, Ausgaben); None = unbrauchbar."""
    if not isinstance(r, dict):
        return None
    name = " ".join(str(r.get("name") or "").split())[:80]
    fields = [f for f in dict.fromkeys(r.get("fields") or []) if f in _FIELDS]
    seps = [s for s in dict.fromkeys(r.get("seps") or []) if s in _SEPS]
    if not name or not fields or not seps:
        return None
    out = r.get("out") if r.get("out") in {o for o, _ in OUTPUTS} else ", "
    rid = str(r.get("id") or "")
    if not re.fullmatch(r"u_[a-z0-9_]{1,48}", rid) or rid in taken:
        base, n = "u_" + _slug(name), 2
        rid = base
        while rid in taken:
            rid, n = f"{base}_{n}", n + 1
    return {"id": rid, "name": name, "desc": " ".join(str(r.get("desc") or "").split())[:400], "type": "multi",
            "fields": fields, "seps": seps, "out": out, "dedupe": r.get("dedupe", True) is not False}


def expand_fields(fields) -> list[str]:
    """Felder und Gruppen → Liste der Feldschlüssel (Gruppen aufgelöst)."""
    out = []
    for f in fields:
        out += EXCEPTION_GROUPS[f][1] if f in EXCEPTION_GROUPS else [f]
    return list(dict.fromkeys(out))


def plan(files, recipe: dict, exceptions=None, out=None) -> list:
    """Änderungen eines Rezepts (wie plan_multi_fix). out überschreibt den Ziel-Trenner des Rezepts."""
    out = out or recipe.get("out") or ", "
    keys = expand_fields(recipe.get("fields") or [])
    if out == "v24":
        return plan_multi_fix(files, keys, recipe["seps"], MV, recipe.get("dedupe", True), False, False, exceptions,
                              v23_sep=" / ")
    return plan_multi_fix(files, keys, recipe["seps"], out, recipe.get("dedupe", True), False, False, exceptions)


def export_text(recipes: list[dict]) -> str:
    return json.dumps({"format": FORMAT, "version": 1, "exported": datetime.datetime.now().isoformat(timespec="seconds"),
                       "recipes": [{k: r[k] for k in ("name", "desc", "type", "fields", "seps", "out", "dedupe")}
                                   for r in recipes]}, ensure_ascii=False, indent=2)


def import_text(text: str, taken=()) -> list[dict]:
    """Rezepte aus einer Export-Datei – je Rezept eine neue Kennung; unbrauchbare werden übersprungen."""
    try:
        data = json.loads(text)
    except ValueError as ex:
        raise ValueError(f"Keine gültige JSON-Datei: {ex}") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("Das ist keine Smart-Fix-Datei von TagStudio.")
    out, ids = [], set(taken)
    for r in data.get("recipes") or []:
        c = clean(dict(r, id=""), ids) if isinstance(r, dict) else None
        if c:
            ids.add(c["id"])
            out.append(c)
    return out
