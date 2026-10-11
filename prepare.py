"""MarKusSXCH TagStudio – Tracks vorbereiten (#109–#116): Eingangsordner → Stufen → Bibliothek.

Ein **Workflow** ist eine Liste von Schritten (Typen siehe STEP_TYPES). Jeder Titel aus dem Eingangsordner läuft der
Reihe nach durch; Stufen-Schritte arbeiten auf einer **Kopie** im eigenen Stufen-Ordner (Rohdaten bleiben unverändert).
Der Zustand je Titel liegt in ~/TagStudio/Vorbereiten/<Workflow-ID>.json.

Schritte:
  recipe    Tag-Rezept (#111) auf eine Kopie im Stufen-Ordner anwenden und speichern – automatisch
  external  Programm öffnen (Platinum Notes, Picard …); Abschluss über Herkunfts-Kennzeichen erkennen oder bestätigen;
            optional mit Schutzregel „nur ergänzen“ (#114)
  import    in die Bibliothek kopieren mit Duplikatprüfung (#115)
  check     nachgelagertes Programm als Status (Mixed In Key, beaTunes, Engine DJ, Lexicon, Mixo – #116)
  verify    Pflichtfelder prüfen (z. B. vor der Übernahme: Tonart, BPM, Cover) – automatisch, ändert nichts
  plugin    Plugin-Aktion (Lautheit, Online-Metadaten …) auf eine Kopie im Stufen-Ordner; Vorschläge werden je nach
            Modus übernommen (nur leere Felder füllen · alle vorgeschlagenen · nur messen) und gespeichert
Nur Standardbibliothek. Gelöscht wird nur auf ausdrücklichen Wunsch (Stufen-Kopien nach der Übernahme).
"""
from __future__ import annotations

import copy
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

STEP_TYPES = {"recipe": "Tag-Rezept", "external": "Externes Programm", "import": "Übernahme in die Bibliothek",
              "check": "Nachgelagertes Programm (Status)", "plugin": "Plugin",
              "verify": "Pflichtfelder prüfen"}
VERIFY_DEFAULT = ["TIT2", "TPE1", "TKEY", "TBPM", "APIC*"]
PLUGIN_MODES = {"fill": "nur leere Felder füllen", "checked": "alle vorausgewählten Vorschläge übernehmen",
                "none": "nichts übernehmen (nur ausführen, z. B. messen oder Kopie erzeugen)"}
STATES = {"open": "offen", "waiting": "wartet", "done": "erledigt", "warn": "erledigt mit Warnung", "error": "Fehler",
          "skipped": "übersprungen"}

PROTECT_DEFAULT = {
    "variant": "C",                          # A alle Felder · B nur Liste · C alle ausser freie Felder
    "fields": ["TIT2", "TPE1", "TALB", "TPE4", "TPUB", "TXXX:CATALOGNUMBER", "TCON", "TDRC", "TSRC", "APIC*"],
    "free": ["TLEN", "TSSE", "TENC", "GEOB:Serato*", "GEOB:CuePoints", "GEOB:Energy", "GEOB:Key", "PRIV:*",
             "TXXX:TAGSTUDIO", "TXXX:EnergyLevel"],
    "on_violation": "report",                # report = nur melden · revert = automatisch zurücksetzen
}

TEMPLATE = {
    "id": "", "name": "DJ-Workflow (Beatport → Bibliothek)", "inbox": "", "work": "", "library": "",
    "protect": PROTECT_DEFAULT,
    "steps": [
        {"id": "s02", "type": "recipe", "label": "02 Mp3tag-Aktionen", "recipe": "beatport-download", "folder": "_02_MP3Tag"},
        {"id": "s03", "type": "external", "label": "03 Platinum Notes", "folder": "_03_PlatinumNotes", "copy": True,
         "program": "", "args": "{folder}", "detect": "platinum", "protect": False, "allow": []},
        {"id": "s04", "type": "external", "label": "04 MusicBrainz Picard", "folder": "", "program": "", "args": "{files}",
         "detect": "musicbrainz", "protect": True, "allow": []},
        {"id": "s05", "type": "external", "label": "05 AudioRanger", "folder": "", "program": "", "args": "{folder}",
         "detect": "", "protect": True, "allow": []},
        {"id": "s06", "type": "external", "label": "06 OneTagger", "folder": "", "program": "", "args": "{folder}",
         "detect": "", "protect": True, "allow": []},
        {"id": "s07", "type": "import", "label": "Übernahme in die Bibliothek", "dup": True},
        {"id": "s08", "type": "check", "label": "07 Mixed In Key", "detect": "mik", "protect": True,
         "allow": ["TKEY", "TBPM", "TXXX:EnergyLevel", "TXXX:ENERGY", "COMM*", "GEOB:*"]},
        {"id": "s09", "type": "check", "label": "08 beaTunes", "detect": "beatunes", "protect": True,
         "allow": ["TBPM", "TXXX:*"]},
        {"id": "s10", "type": "check", "label": "09 Engine DJ", "detect": ""},
        {"id": "s11", "type": "check", "label": "10 Lexicon", "detect": "lexicon"},
        {"id": "s12", "type": "check", "label": "11 Mixo", "detect": ""},
    ],
}


def template() -> dict:
    w = copy.deepcopy(TEMPLATE)
    w["id"] = uuid.uuid4().hex[:10]
    return w


def clean_workflow(w: dict) -> dict:
    """Workflow aus der Oberfläche bzw. einem Import prüfen."""
    if not isinstance(w, dict):
        raise ValueError("Ungültiger Workflow.")
    out = {"id": re.sub(r"[^0-9a-zA-Z_-]", "", str(w.get("id") or "")) or uuid.uuid4().hex[:10],
           "name": str(w.get("name") or "Workflow").strip()[:80],
           "inbox": str(w.get("inbox") or "").strip(), "work": str(w.get("work") or "").strip(),
           "library": str(w.get("library") or "").strip()}
    p = w.get("protect") if isinstance(w.get("protect"), dict) else {}
    out["protect"] = {"variant": p.get("variant") if p.get("variant") in ("A", "B", "C") else "C",
                      "fields": [str(x) for x in p.get("fields", PROTECT_DEFAULT["fields"]) if str(x).strip()],
                      "free": [str(x) for x in p.get("free", PROTECT_DEFAULT["free"]) if str(x).strip()],
                      "on_violation": "revert" if p.get("on_violation") == "revert" else "report"}
    steps, seen = [], set()
    for s in w.get("steps") or []:
        if not isinstance(s, dict) or s.get("type") not in STEP_TYPES:
            continue
        sid = re.sub(r"[^0-9a-zA-Z_-]", "", str(s.get("id") or "")) or uuid.uuid4().hex[:6]
        while sid in seen:
            sid += "x"
        seen.add(sid)
        st = {"id": sid, "type": s["type"], "label": str(s.get("label") or STEP_TYPES[s["type"]]).strip()[:80]}
        folder = re.sub(r'[<>:"/\\|?*]', "", str(s.get("folder") or "")).strip()
        if s["type"] == "recipe":
            st.update(recipe=str(s.get("recipe") or ""), folder=folder or f"_{sid}")
        elif s["type"] == "external":
            st.update(folder=folder, copy=bool(s.get("copy")) and bool(folder), program=str(s.get("program") or "").strip(),
                      args=str(s.get("args") if s.get("args") is not None else "{folder}"),
                      detect=str(s.get("detect") or ""), protect=bool(s.get("protect")),
                      allow=[str(x) for x in s.get("allow") or [] if str(x).strip()])
        elif s["type"] == "import":
            st.update(dup=s.get("dup", True) is not False)
        elif s["type"] == "check":
            st.update(detect=str(s.get("detect") or ""), protect=bool(s.get("protect")),
                      allow=[str(x) for x in s.get("allow") or [] if str(x).strip()])
        elif s["type"] == "verify":
            fl = [str(x).strip() for x in (s.get("fields") if s.get("fields") is not None else VERIFY_DEFAULT) if str(x).strip()]
            st.update(fields=fl)
        elif s["type"] == "plugin":
            st.update(plugin=str(s.get("plugin") or ""), action=str(s.get("action") or ""), folder=folder or f"_{sid}",
                      mode=s.get("mode") if s.get("mode") in PLUGIN_MODES else "fill", protect=bool(s.get("protect")),
                      allow=[str(x) for x in s.get("allow") or [] if str(x).strip()])
        steps.append(st)
    out["steps"] = steps
    return out


# =========================================================================== Zustand
def state_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "TagStudio", "Vorbereiten")


def state_path(wid: str) -> str:
    return os.path.join(state_dir(), f"{wid}.json")


def load_state(wid: str) -> dict:
    try:
        with open(state_path(wid), encoding="utf-8") as fh:
            d = json.load(fh)
            if isinstance(d, dict) and isinstance(d.get("tracks"), dict):
                return d
    except (OSError, ValueError):
        pass
    return {"tracks": {}}


def save_state(wid: str, st: dict):
    os.makedirs(state_dir(), exist_ok=True)
    tmp = state_path(wid) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, state_path(wid))


def work_dir(w: dict) -> str:
    if w.get("work"):
        return w["work"]
    return os.path.dirname(os.path.normpath(w["inbox"])) if w.get("inbox") else ""


def list_inbox(w: dict) -> list[str]:
    """MP3 im Eingangsordner (relativ, mit Unterordnern)."""
    root = w.get("inbox")
    if not root or not os.path.isdir(root):
        return []
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for n in files:
            if n.lower().endswith(".mp3") and not n.startswith("."):
                out.append(os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/"))
    return sorted(out, key=str.lower)


def track_path(w: dict, st: dict, name: str, upto: int | None = None) -> str:
    """Aktueller Ort eines Titels: Bibliothek nach der Übernahme, sonst die letzte erledigte Stufe mit Ordner,
    sonst der Eingangsordner. upto: nur Schritte vor diesem Index berücksichtigen."""
    t = st["tracks"].get(name, {})
    steps = w["steps"] if upto is None else w["steps"][:upto]
    path = os.path.join(w["inbox"], name)
    for s in steps:
        rec = (t.get("steps") or {}).get(s["id"]) or {}
        if rec.get("state") not in ("done", "warn", "waiting"):
            continue
        if s["type"] == "import" and rec.get("file"):
            path = rec["file"]
        elif s.get("folder"):
            path = os.path.join(work_dir(w), s["folder"], name)
    return path


def step_ready(w: dict, st: dict, name: str, i: int) -> bool:
    """Alle früheren Schritte (ausser Status-Schritten) erledigt oder übersprungen?"""
    t = st["tracks"].get(name, {})
    for s in w["steps"][:i]:
        if s["type"] == "check":
            continue
        if ((t.get("steps") or {}).get(s["id"]) or {}).get("state") not in ("done", "warn", "skipped"):
            return False
    return True


# =========================================================================== Schutzregel
def _match(key: str, pats) -> bool:
    k = key.split("#")[0].lower()
    return any(fnmatch.fnmatchcase(k, str(p).lower()) or k == str(p).lower() for p in pats or [])


def tag_values(path: str) -> dict:
    """{Schlüssel: Text bzw. Prüfsumme} für den Vergleich vor/nach einem Schritt."""
    import hashlib
    from id3tags import MP3File
    f = MP3File(path)
    out = {}
    for k, it in f.items.items():
        if it.kind in ("picture", "raw"):
            data = it.cover.data if it.kind == "picture" and it.cover else (it.payload or b"")
            out[k] = "#" + hashlib.md5(data).hexdigest()
        else:
            out[k] = it.text
    return out


def violations(w: dict, step: dict, before: dict, after: dict) -> list[dict]:
    """Geänderte oder entfernte Felder, die der Schritt nicht ändern durfte. Neue Felder sind immer erlaubt."""
    p = w["protect"]
    allow = list(step.get("allow") or [])
    out = []
    for k, old in before.items():
        new = after.get(k)
        if new == old:
            continue
        if p["variant"] == "B" and not _match(k, p["fields"]):
            continue
        if p["variant"] == "C" and _match(k, p["free"]):
            continue
        if _match(k, allow):
            continue
        out.append({"key": k, "old": old if not str(old).startswith("#") else "(Binärdaten)",
                    "new": "" if new is None else (new if not str(new).startswith("#") else "(Binärdaten geändert)"),
                    "state": "removed" if new is None else "changed", "binary": str(old).startswith("#")})
    return out


def revert_values(path: str, rows: list[dict]) -> int:
    """Geänderte Textfelder auf den Stand vor dem Schritt zurücksetzen (Binärfelder nicht)."""
    from id3tags import MP3File
    f = MP3File(path)
    n = 0
    for r in rows:
        if r.get("binary"):
            continue
        f.set_text(r["key"], r["old"])
        n += 1
    if n:
        f.save()
    return n


def missing_fields(path: str, pats) -> list[str]:
    """Pflichtfelder (Muster wie „APIC*“, „TXXX:ENERGY“), die fehlen oder leer sind."""
    from id3tags import MP3File
    f = MP3File(path)
    have = [k for k, it in f.items.items() if it.kind in ("picture", "raw") or (it.text or "").strip()]
    return [p for p in pats or [] if not any(_match(k, [p]) for k in have)]


# =========================================================================== Plugin-Schritt
def pick_proposals(props: list[dict], mode: str) -> list[dict]:
    """Welche Plugin-Vorschläge ein Plugin-Schritt übernimmt.
    fill: nur Felder, die bisher leer sind (Cover nur, wenn keins da ist) · checked: alle vorausgewählten · none: keine."""
    if mode == "none":
        return []
    out = []
    for p in props:
        if p.get("same"):
            continue
        if mode == "fill" and (p.get("old") or "").strip():
            continue
        if mode == "fill" and p.get("kind") == "cover" and not p.get("data"):
            continue
        if mode == "checked" and not p.get("checked"):
            continue
        out.append(p)
    return out


# =========================================================================== Programme
def launch(program: str, args: str, folder: str, files: list[str]) -> str:
    """Externes Programm starten. Platzhalter: {folder} (Ordner), {files} (alle Dateien). → Befehl als Text."""
    if not program:
        raise ValueError("Für diesen Schritt ist kein Programm hinterlegt (Workflow bearbeiten).")
    if not os.path.exists(program):
        raise ValueError(f"Programm nicht gefunden: {program}")
    parts = []
    for tok in (args or "").split():
        if tok == "{folder}":
            parts.append(folder)
        elif tok == "{files}":
            parts.extend(files)
        else:
            parts.append(tok.replace("{folder}", folder))
    if sys.platform == "darwin" and program.endswith(".app"):
        cmd = ["open", "-a", program] + (["--args"] + parts if parts else [])
    else:
        cmd = [program] + parts
    subprocess.Popen(cmd, close_fds=True)
    return " ".join(cmd[:3]) + (" …" if len(cmd) > 3 else "")


def detect(path: str, sid: str, origin_of) -> bool:
    """Hat ein Programm (Herkunft sid) die Datei bearbeitet?"""
    if not sid or not os.path.isfile(path):
        return False
    from id3tags import MP3File
    try:
        f = MP3File(path)
    except Exception:  # noqa: BLE001
        return False
    return any(origin_of(k) == sid for k in f.items)


# =========================================================================== Übernahme
def _norm(s: str) -> str:
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def duplicates(src: str, lib_files, dest: str) -> list[str]:
    """Mögliche Doppel in der Bibliothek: gleicher Dateiname, gleiches Audio oder gleicher Künstler + Titel."""
    from id3tags import MP3File
    import backup
    out = []
    if os.path.exists(dest):
        out.append(f"Datei existiert bereits: {os.path.basename(dest)}")
    try:
        f = MP3File(src)
        key = (_norm(f.text("TPE1")), _norm(f.text("TIT2")))
        lay = backup.read_layout(src)
    except Exception:  # noqa: BLE001
        return out
    for g in lib_files:
        if os.path.normcase(g.path) == os.path.normcase(dest):
            continue
        if key[1] and (_norm(g.text("TPE1")), _norm(g.text("TIT2"))) == key:
            same = ""
            try:
                gl = backup.read_layout(g.path)
                same = " – gleiches Audio" if gl["audio_md5"] == lay["audio_md5"] and gl["audio_len"] == lay["audio_len"] else ""
            except OSError:
                pass
            out.append(f"gleicher Künstler und Titel: {os.path.basename(g.path)}{same}")
            if len(out) >= 5:
                break
    return out


def copy_file(src: str, dst: str):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".tstmp"
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
