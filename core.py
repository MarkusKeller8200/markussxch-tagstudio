"""
core.py – gemeinsame Logik aller Oberflächen (tkinter, Web).

Alles, was nicht „zeichnen“ ist, gehört hierher: welche Zeilen angezeigt werden, welche Zeichen
sich unterscheiden, Status und Filter der Paarliste, Laden, Speichern mit Sicherung, Einstellungen.
Unabhängig von jeder Oberfläche und damit testbar.
"""
from __future__ import annotations

import difflib
import json
import os
import re

from id3tags import MP3File, key_label, sort_key, FIELDSETS, MV
from compare import scan, pair_files, diff, all_keys, Cancelled
import backup

CONFIG = os.path.join(os.path.expanduser("~"), ".tagstudio.json")
CONFIG_OLD = os.path.join(os.path.expanduser("~"), ".mp3tagcompare.json")  # Version ≤ 2.8 (MP3 Tag Compare)

URL_RE = re.compile(r"(?:https?://|www\.)[^\s|¦<>\"]+", re.I)
FILTER_OPS = ["enthält", "enthält nicht", "ist", "ist nicht", "beginnt mit", "fehlt / leer", "vorhanden",
              "größer als", "kleiner als", "Regex"]
FILTER_SIDES = ["links oder rechts", "links", "rechts", "beide Seiten"]
EMPTY_SETS = {"off": "Leere Felder", "v1": "Leere: v1", "v23": "Leere: v2.3", "v24": "Leere: v2.4", "all": "Leere: alle"}


# =========================================================================== Einstellungen
def config_path() -> str:
    """Aktuelle Einstellungsdatei; liest einmalig die der Vorgängerversion, falls die neue fehlt."""
    return CONFIG if os.path.exists(CONFIG) or not os.path.exists(CONFIG_OLD) else CONFIG_OLD


def load_config() -> dict:
    try:
        with open(config_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def save_config(updates: dict) -> None:
    """Schreibt nur die übergebenen Schlüssel – Einstellungen anderer Oberflächen bleiben erhalten."""
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except Exception:  # noqa: BLE001
        cfg = {}
    cfg.update(updates)
    try:
        with open(CONFIG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


def history(cfg: dict, name: str, value: str, n: int = 12) -> list[str]:
    h = [value] + [x for x in cfg.get(name, []) if x != value]
    return [x for x in h if x][:n]


# =========================================================================== Anzeige einzelner Werte
def disp(it) -> str:
    """Einzeilige Anzeige eines Feldwerts."""
    s = it.display().replace("\r", "").replace("\n", " ⏎ ")
    return s if len(s) <= 800 else s[:800] + " …"


def diff_spans(a: str, b: str) -> list[tuple[int, int]]:
    """Zeichenbereiche in a, die sich von b unterscheiden (ganz a, wenn praktisch alles anders ist)."""
    if not a:
        return []
    if len(a) + len(b) > 1600:
        return [(0, len(a))]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.ratio() < 0.3:
        return [(0, len(a))]
    return [(i1, i2) for op, i1, i2, _j1, _j2 in sm.get_opcodes() if op != "equal" and i2 > i1]


def link_spans(s: str) -> list[tuple[int, int, str]]:
    """URLs im Text: (start, ende, url)."""
    out = []
    for m in URL_RE.finditer(s):
        url = m.group(0).rstrip(".,;)")
        out.append((m.start(), m.start() + len(url), url))
    return out


def edit_text(it) -> str:
    """Text zum Bearbeiten (Mehrfachwerte mit sichtbarem Trenner)."""
    from id3tags import MV_SHOW
    return it.text.replace(MV, MV_SHOW) if it is not None else ""


def normalize_value(val: str) -> str:
    """Sichtbarer Trenner ¦ → ID3v2.4-Mehrfachwert."""
    return re.sub(r"\s*¦\s*", MV, val).strip(MV)


def apply_value(f, key: str, val: str) -> bool:
    """Setzt einen bearbeiteten Wert; leerer Wert entfernt das Feld. Liefert True bei Änderung."""
    it = f.get(key)
    if it is not None and it.kind == "raw":     # Binärfeld mit XML: nur den XML-Abschnitt ersetzen
        import xmltools
        if not val.strip():
            f.set(key, None)
            return True
        new = xmltools.replace_blob_xml(it, val)
        if new is None or new == it:
            return False
        f.set(key, new)
        return True
    val = normalize_value(val)
    if val == (it.text if it else ""):
        return False
    if val.strip() == "":
        f.set(key, None)
    else:
        f.set_text(key, val)
    return True


def can_edit_text(f, key: str) -> bool:
    """Lässt sich das Feld als Text bearbeiten (bzw. neu anlegen)?"""
    from id3tags import TEXT_LABELS
    if f is None or key.startswith("APIC") or getattr(f, "readonly", False):
        return False
    it = f.get(key)
    if it is None:
        return key.split(":")[0] in TEXT_LABELS or key.startswith(("TXXX", "COMM", "WXXX", "USLT", "T", "W"))
    if it.kind == "raw":   # Binärfeld: nur wenn es einen bearbeitbaren XML-Abschnitt enthält
        import xmltools
        hit = xmltools.blob_xml(it)
        return bool(hit and hit["editable"])
    return it.editable


# =========================================================================== Vergleichszeilen
def row_state(k, l, r, rules) -> str:
    """same | diff | triv | only | empty"""
    li, ri = l.get(k) if l else None, r.get(k) if r else None
    if li is None and ri is None:
        return "empty"
    if l is None or r is None:
        return "same"
    if li is None or ri is None:
        return "only"
    if li == ri:
        return "same"
    return "triv" if rules.is_trivial(k) else "diff"


def field_match(k, q, l, r) -> bool:
    """Feldsuche: Name, Schlüssel oder Wert enthält q (klein geschrieben)."""
    if q in key_label(k).lower() or q in k.lower():
        return True
    for f in (l, r):
        it = f.get(k) if f else None
        if it is not None and q in it.display().lower():
            return True
    return False


def visible_keys(l, r, rules, flt="all", show_trivial=True, empty_set="off", query=""):
    """Anzuzeigende Schlüssel und Zustand aller Schlüssel: (rows, states)."""
    keys = all_keys(l, r)
    if empty_set != "off" and (l or r):
        keys = sorted(set(keys) | set(FIELDSETS[empty_set]), key=sort_key)
    q = (query or "").strip().lower()
    rows, states = [], {}
    for k in keys:
        st = row_state(k, l, r, rules)
        states[k] = st
        if flt == "diff" and (st == "same" or (st == "triv" and not show_trivial)):
            continue
        if flt in ("diff", "same") and st == "empty":
            continue
        if flt == "same" and st != "same":
            continue
        if flt == "all" and st == "triv" and not show_trivial:
            continue
        if q and not field_match(k, q, l, r):
            continue
        rows.append(k)
    return rows, states


def state_counts(states: dict) -> dict:
    st = list(states.values())
    return {"diff": st.count("diff"), "triv": st.count("triv"), "only": st.count("only"), "same": st.count("same")}


# =========================================================================== Paarliste
def rel_name(f, root) -> str:
    if f is None:
        return ""
    return os.path.relpath(f.path, root) if root and os.path.isdir(root) else os.path.basename(f.path)


def pair_status(l, r, rules) -> dict:
    """Status eines Paars: symbol (≠ ≈ = ◧ ◨), tag (diff/triv/same/single), info, n_imp, n_triv, modified."""
    mod = bool((l and l.is_modified()) or (r and r.is_modified()))
    if l is None or r is None:
        return {"symbol": "◨" if l is None else "◧", "tag": "single", "info": "nur rechts" if l is None else "nur links",
                "n_imp": 0, "n_triv": 0, "modified": mod}
    imp, triv = diff(l, r, rules)
    if imp:
        info = f"{len(imp)} Unterschied{'e' if len(imp) > 1 else ''}" + (f"  (+{len(triv)} unwichtig)" if triv else "")
        sym, tag = "≠", "diff"
    elif triv:
        info, sym, tag = f"{len(triv)} unwichtig", "≈", "triv"
    else:
        info, sym, tag = "gleich", "=", "same"
    return {"symbol": sym, "tag": tag, "info": info, "n_imp": len(imp), "n_triv": len(triv), "modified": mod}


def file_values(f) -> list[str]:
    return [os.path.basename(f.path)] + [it.display() for it in f.items.values()]


def field_choices(pairs) -> dict:
    """Auswahl für den Feld-Filter: Anzeigename → Schlüssel."""
    keys = set(FIELDSETS["all"])
    for p in pairs:
        for f in p:
            if f:
                keys |= set(f.items)
    ch = {"— kein Filter —": None, "Dateiname": "__file__", "Beliebiges Feld": "__any__"}
    for k in sorted(keys, key=sort_key):
        lbl = key_label(k)
        if lbl in ch:
            lbl = f"{lbl}  [{k}]"
        ch[lbl] = k
    return ch


def _num(x):
    m = re.search(r"-?\d+(?:[.,]\d+)?", x or "")
    return float(m.group(0).replace(",", ".")) if m else None


def make_pair_filter(query="", key=None, op="enthält", val="", side="links oder rechts"):
    """Prüffunktion für ein Paar (l, r) – oder None, wenn kein Filter aktiv ist."""
    q = (query or "").strip().lower()
    val = (val or "").strip()
    needs_val = op not in ("fehlt / leer", "vorhanden")
    cond = None
    if key and (val or not needs_val):
        vl = val.lower()
        rx = None
        if op == "Regex":
            try:
                rx = re.compile(val, re.I)
            except re.error:
                rx = None

        def test(f):
            if f is None:
                return False
            if key == "__file__":
                vals = [os.path.basename(f.path)]
            elif key == "__any__":
                vals = file_values(f)
            else:
                it = f.get(key)
                vals = [it.display()] if it is not None and it.display().strip() else []
            low = [v.lower() for v in vals]
            if op == "fehlt / leer":
                return not low
            if op == "vorhanden":
                return bool(low)
            if op == "enthält":
                return any(vl in v for v in low)
            if op == "enthält nicht":
                return not any(vl in v for v in low)
            if op == "ist":
                return any(v.strip() == vl for v in low)
            if op == "ist nicht":
                return not any(v.strip() == vl for v in low)
            if op == "beginnt mit":
                return any(v.startswith(vl) for v in low)
            if op in ("größer als", "kleiner als"):
                ref = _num(val)
                nums = [n for n in (_num(v) for v in vals) if n is not None]
                if ref is None or not nums:
                    return False
                return any(n > ref for n in nums) if op == "größer als" else any(n < ref for n in nums)
            if op == "Regex":
                return rx is not None and any(rx.search(v) for v in vals)
            return True
        cond = test
    if not q and cond is None:
        return None

    def pair_ok(pair):
        l, r = pair
        if q and not any(q in v.lower() for f in (l, r) if f for v in file_values(f)):
            return False
        if cond is None:
            return True
        if side == "links":
            return cond(l)
        if side == "rechts":
            return cond(r)
        if side == "beide Seiten":
            return cond(l) and cond(r)
        return cond(l) or cond(r)
    return pair_ok


def modified_files(pairs) -> list:
    seen, out = set(), []
    for pair in pairs:
        for f in pair:
            if f and f.is_modified() and id(f) not in seen:
                seen.add(id(f))
                out.append(f)
    return out


# =========================================================================== Laden
def check_paths(lp: str, rp: str) -> str | None:
    """Fehlermeldung oder None."""
    if not lp and not rp:
        return "Bitte links und/oder rechts einen Ordner oder eine Datei wählen."
    for p, n in ((lp, "Links"), (rp, "Rechts")):
        if p and p.startswith("snapshot:"):        # #56: Snapshot als Quelle
            continue
        if p and not os.path.exists(p):
            return f"{n}: Der Pfad existiert nicht.\n\n{p}"
    if lp and rp and os.path.abspath(lp) == os.path.abspath(rp):
        return "Links und rechts ist derselbe Pfad."
    return None


def _open(path, registry):
    """MP3File öffnen – mit Register werden bereits geladene Objekte wiederverwendet (und frisch gelesen),
    damit Vergleich und Tagger dieselben Objekte nutzen."""
    if registry is None:
        return MP3File(path)
    k = os.path.normcase(os.path.abspath(path))
    f = registry.get(k)
    if f is not None:
        f.load()
        return f
    f = MP3File(path)
    registry[k] = f
    return f


def _load_list(paths, cache, registry, cancel, progress, offset=0, total=None, cached=None):
    """Dateien laden – mit Listen-Cache (#70) ohne die Dateien zu öffnen, wo Grösse/Änderungszeit stimmen."""
    import listcache
    files, errors = [], []
    total = total or len(paths)
    for i, p in enumerate(paths, 1):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        try:
            if cache is None:
                files.append(_open(p, registry))
            else:
                f, hit = listcache.open_file(p, cache, registry)
                files.append(f)
                if hit and cached is not None:
                    cached.append(f)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{os.path.basename(p)}: {ex}")
        if i % 10 == 0 or i == len(paths):
            progress(("progress", offset + i, total, p))
    if cache is not None:
        cache.save()
    return files, errors


def load_files(path, recursive, cancel=None, progress=None, registry=None, use_cache=False, stats=None):
    """Ordner/Datei für den Tagger einlesen → (files, errors). progress wie bei load_pairs.
    use_cache: Listen-Cache (#70); stats (dict) erhält "cached" (aus dem Cache geladene Dateien) und "caches"."""
    import listcache
    progress = progress or (lambda m: None)
    paths = scan(path, recursive, cancel, lambda n: progress(("count", n)))
    progress(("total", len(paths)))
    cache = listcache.ListCache(path) if use_cache and paths else None
    cached = []
    files, errors = _load_list(paths, cache, registry, cancel, progress, cached=cached)
    if stats is not None:
        stats.update(cached=cached, caches=[cache] if cache else [])
    return files, errors


def load_pairs(lp, rp, recursive, mode, cancel=None, progress=None, registry=None, snap_loader=None, use_cache=False,
               stats=None):
    """Ordner/Dateien einlesen und zuordnen → (pairs, errors).
    progress(msg): ("count", n) beim Zählen, ("total", n), ("progress", i, total, pfad).
    Wirft Cancelled, wenn cancel (threading.Event) gesetzt wird.
    registry (dict, optional): gemeinsames Dateiregister, siehe _open()."""
    progress = progress or (lambda m: None)
    found = [0, 0]

    def counter(side):
        def cb(n):
            found[side] = n
            progress(("count", found[0] + found[1]))
        return cb
    snap = {0: None, 1: None}          # #56: Seite aus einem Snapshot (schreibgeschützt)
    roots = [lp, rp]
    for side, p in ((0, lp), (1, rp)):
        if p and p.startswith("snapshot:"):
            if snap_loader is None:
                raise ValueError("Snapshots sind hier nicht verfügbar.")
            snap[side], roots[side], _label = snap_loader(p, cancel, progress)
    lpaths = scan(lp, recursive, cancel, counter(0)) if lp and snap[0] is None else []
    rpaths = scan(rp, recursive, cancel, counter(1)) if rp and snap[1] is None else []
    total = len(lpaths) + len(rpaths)
    progress(("total", total))
    import listcache
    errors, loaded, cached, caches = [], ([], []), [], []
    for side, paths, root in ((0, lpaths, lp), (1, rpaths, rp)):
        cache = listcache.ListCache(root) if use_cache and paths else None
        if cache is not None:
            caches.append(cache)
        fs, errs = _load_list(paths, cache, registry, cancel, progress, offset=len(lpaths) if side else 0,
                              total=total, cached=cached)
        loaded[side].extend(fs)
        errors += errs
    if stats is not None:
        stats.update(cached=cached, caches=caches)
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    for side in (0, 1):
        if snap[side] is not None:
            loaded[side].extend(snap[side])
    progress(("pairing",))
    return pair_files(loaded[0], loaded[1], mode, roots[0], roots[1]), errors


# =========================================================================== Speichern
class BackupUnavailable(Exception):
    """Sicherungsordner nicht verfügbar – es wurde nichts gespeichert."""


def save_files(files, backup_on=True, folder=None, cancel=None, progress=None, force=False) -> dict:
    """Speichert Dateien; vorher werden die bisherigen Tags gesichert (eine ZIP pro Vorgang).
    Schlägt die Sicherung einer Datei fehl, wird diese Datei nicht gespeichert.
    → {"saved": n, "errors": [...], "backup": pfad|None, "cancelled": bool}"""
    progress = progress or (lambda m: None)
    folder = folder or backup.default_dir()
    errors, saved, bpath, bw = [], 0, None, None
    if backup_on:
        try:
            bw = backup.BackupWriter(folder, label=f"Vor dem Speichern ({len(files)} Datei(en))")
        except OSError as ex:
            raise BackupUnavailable(f"Der Sicherungsordner ist nicht verfügbar:\n{folder}\n\n{ex}\n\n"
                                    "Es wurde nichts gespeichert.") from ex
    progress(("total", len(files)))
    for i, f in enumerate(files, 1):
        if cancel is not None and cancel.is_set():
            break
        name = os.path.basename(f.path)
        if not force and f.external_change():      # #55: nie stillschweigend fremde Änderungen überschreiben
            errors.append(f"{name}: wurde von einem anderen Programm geändert – NICHT gespeichert")
            progress(("progress", i, len(files), f.path))
            continue
        try:
            if bw:
                bw.add(f.path)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{name}: Sicherung fehlgeschlagen – NICHT gespeichert ({ex})")
            progress(("progress", i, len(files), f.path))
            continue
        try:
            f.save()
            saved += 1
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{name}: {ex}")
        progress(("progress", i, len(files), f.path))
    if bw:
        try:
            bpath = bw.close()
        except Exception as ex:  # noqa: BLE001
            errors.append(f"Sicherung konnte nicht abgeschlossen werden: {ex}")
    return {"saved": saved, "errors": errors, "backup": bpath,
            "cancelled": bool(cancel is not None and cancel.is_set())}


def fmt_n(n) -> str:
    return f"{n:,}".replace(",", "'")
