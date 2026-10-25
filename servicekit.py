"""MarKusSXCH TagStudio – gemeinsame Werkzeuge der Dienst-Plugins (#204).

- Client: JSON-Abfragen mit eigenem User-Agent, Drosselung je Host (`onlinematch.INTERVALS`), Wiederholung bei
  429/503 und Abbruch. Der eigentliche Abruf läuft über `onlinematch.http_get` – in Tests an einer Stelle ersetzbar.
- Schlüssel: im Datenordner des jeweiligen Dienst-Plugins über `secretstore` (Windows: DPAPI, macOS: Schlüsselbund,
  sonst Datei mit Rechten 0600, #287), nie protokolliert, nie im Einstellungs-Export. Bis 4.5 lagen alle Schlüssel gemeinsam im Ordner des Plugins
  „Online-Metadaten“; beim ersten Lesen zieht ein Dienst-Plugin seine Schlüssel von dort um (`load_keys(…, migrate=…)`).
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import urllib.parse

import onlinematch as om
import secretstore as ss

try:
    from version import VERSION
except Exception:  # noqa: BLE001
    VERSION = "4"

USER_AGENT = f"TagStudio/{VERSION} ( https://github.com/MarkusKeller8200/markussxch-tagstudio )"


def client(ctx, intervals: dict | None = None) -> om.Client:
    """Client für ein Dienst-Plugin. intervals ergänzt die gemeinsamen Abstände (Sekunden je Host)."""
    for host, sec in (intervals or {}).items():
        om.INTERVALS.setdefault(host, sec)
    cancel = getattr(ctx, "check_cancel", None)
    return om.Client(USER_AGENT, om.INTERVALS, get=lambda url, h: om.http_get(url, h), cancel=cancel, throttle=om.SHARED)


def q(s) -> str:
    return urllib.parse.quote(s or "", safe="")


# =========================================================================== Schlüssel sicher ablegen
def _read(path) -> dict:
    try:
        raw = ss.read(path)
        d = json.loads(raw.decode("utf-8")) if raw else {}
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _keys_path(ctx) -> str:
    return os.path.join(ctx.data_dir, "keys.bin")


def legacy_path(ctx) -> str:
    """Gemeinsame Schlüsseldatei bis 4.5 (Plugin „Online-Metadaten“)."""
    return os.path.join(os.path.dirname(ctx.data_dir.rstrip("/\\")), "online", "keys.bin")


def load_keys(ctx, migrate: tuple = ()) -> dict:
    """Schlüssel des Dienst-Plugins. migrate: Namen, die aus der alten gemeinsamen Datei übernommen werden, solange
    das Plugin noch keine eigene Datei hat (einmalig; die alte Datei bleibt unverändert)."""
    path = _keys_path(ctx)
    if os.path.exists(path) or not migrate:
        return _read(path)
    old = _read(legacy_path(ctx))
    keys = {k: old[k] for k in migrate if old.get(k)}
    if keys:
        save_keys(ctx, keys)
        ctx.log("Schlüssel aus „Online-Metadaten“ übernommen (verschlüsselt).")
    return keys


def save_keys(ctx, keys: dict):
    raw = json.dumps({k: v for k, v in keys.items() if v}).encode("utf-8")
    if ss.write(_keys_path(ctx), raw) == "file" and ss.last_note():
        ctx.log(ss.last_note())


def keys_action(ctx, opts: dict, names: tuple, extra_plain: tuple = ()) -> dict:
    """Gemeinsame Logik der Aktion „Schlüssel …“: leere Felder = unverändert, „clear“ löscht."""
    keys = load_keys(ctx, names + extra_plain)
    if opts.get("clear"):
        for n in names + extra_plain:
            keys.pop(n, None)
    else:
        for n in names:
            if (opts.get(n) or "").strip():
                keys[n] = opts[n].strip()
        for n in extra_plain:
            if n in opts:
                keys[n] = (opts.get(n) or "").strip()
    save_keys(ctx, keys)
    return keys
