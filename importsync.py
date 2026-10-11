"""MarKusSXCH TagStudio – Abgleich für Importer (#145, #146): Werte aus einer Quelle (beaTunes, Lexicon …) als
Audio-Merkmale vorschlagen und merken, welcher Wert zuletzt übernommen wurde.

Gemerkt wird in TXXX:TAGSTUDIO (JSON, wie das Like), z. B. {"sync": {"lexicon": {"DANCEABILITY": 70}}}.
Damit lässt sich beim nächsten Lauf unterscheiden:
  - Feld leer                                   → Vorschlag, angehakt
  - Datei = zuletzt übernommener Wert, Quelle neu → Vorschlag, angehakt („in <Quelle> geändert“)
  - Datei von Hand bzw. anders geändert          → Vorschlag, NICHT angehakt („fragen“)
  - Datei = Quelle                               → kein Vorschlag
Nur Standardbibliothek.
"""
from __future__ import annotations

import json

import features

TS_KEY = "TXXX:TAGSTUDIO"


def _key_ci(f, key):
    return next((k for k in f.items if k.upper() == key.upper()), None)


def _ts(f) -> dict:
    k = _key_ci(f, TS_KEY)
    if not k:
        return {}
    try:
        d = json.loads(f.text(k) or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def last(f, source: str) -> dict:
    """Zuletzt übernommene Werte {Merkmal: 0–100} dieser Quelle."""
    d = (_ts(f).get("sync") or {}).get(source) or {}
    return {k: v for k, v in d.items() if isinstance(v, int)} if isinstance(d, dict) else {}


def remember(f, source: str, name: str, value: int) -> bool:
    """Übernommenen Wert merken. → True bei Änderung."""
    d = _ts(f)
    sync = d.get("sync") if isinstance(d.get("sync"), dict) else {}
    src = sync.get(source) if isinstance(sync.get(source), dict) else {}
    if src.get(name) == value:
        return False
    src[name] = int(value)
    sync[source] = src
    d["sync"] = sync
    f.set_text(_key_ci(f, TS_KEY) or TS_KEY, json.dumps(d, ensure_ascii=False, separators=(",", ":")))
    return True


def feature_key(f, name: str) -> str:
    """Vorhandene Schreibweise (TXXX:Energy) weiterverwenden, sonst TXXX:ENERGY."""
    ks = features.find_keys(f, name)
    return ks[0] if ks else features.KEYS[name]


def propose(ctx, f, source: str, source_name: str, name: str, value: int, *, enabled=True, group=None, note="") -> str:
    """Merkmal vorschlagen. value 0–100. → "new" | "changed" | "conflict" | "same" """
    cur = features.number(features.get(f, name))
    prev = last(f, source).get(name)
    label = f"{dict((n, l) for n, l, _d in features.FEATURES)[name]} ({name})"
    sync = (source, name, int(value))
    if cur == value:
        ctx.remember_sync(f, sync)         # beim Übernehmen anderer Werte dieser Datei mitmerken
        return "same"
    if cur is None:
        state, checked, hint = "new", True, f"aus {source_name}"
    elif prev is not None and prev == cur:
        state, checked, hint = "changed", True, f"in {source_name} geändert ({prev} → {value})"
    elif prev is None:
        state, checked, hint = "conflict", False, f"Datei hat {cur}, {source_name} {value} – noch nie abgeglichen, bitte prüfen"
    else:
        state, checked, hint = "conflict", False, (f"Datei seit dem letzten Abgleich geändert ({prev} → {cur}), "
                                                   f"{source_name} {value} – bitte prüfen")
    if not enabled:
        checked, hint = False, hint + " · in den Optionen abgewählt"
    ctx.propose(f, feature_key(f, name), features.stored(value), label, note=note, checked=checked, group=group,
                hint=hint, sync=sync)
    return state
