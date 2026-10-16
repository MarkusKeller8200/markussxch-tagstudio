"""AcoustID (#204, aus „Online-Metadaten“ herausgelöst): Fingerabdruck einer Datei mit fpcalc (Chromaprint), Abfrage bei
AcoustID, Aufnahme über das Plugin MusicBrainz. Eigener Anwendungs-Schlüssel (verschlüsselt). Nur Standardbibliothek."""
import json
import os
import shutil
import subprocess

import servicekit as sk
from onlinematch import HttpError

SOURCE = {"id": "acoustid", "name": "AcoustID", "order": 11, "role": "fingerprint"}
API = "https://api.acoustid.org/v2"
INTERVALS = {"api.acoustid.org": 0.34}
KEYS = ("acoustid",)
PLAIN = ("fpcalc",)

ACTIONS = [
    {"id": "keys", "label": "Schlüssel …", "where": "page", "run_label": "Speichern", "needs_selection": False,
     "description": "Anwendungs-Schlüssel für AcoustID und Pfad zu fpcalc. Leer lassen = unverändert. Der Schlüssel wird verschlüsselt gespeichert und nie angezeigt.",
     "options": [
         {"type": "info", "title": "AcoustID",
          "label": "Nur für den Fingerabdruck (Titel ohne brauchbare Tags). 1. Bei acoustid.org anmelden. "
                   "2. „Register a new application“: Name TagStudio, Version, Website (z. B. die GitHub-Seite). "
                   "3. Den „API key“ der Anwendung kopieren und unten einfügen. 4. Zusätzlich das Programm fpcalc "
                   "(Chromaprint) herunterladen, entpacken und den Pfad zu fpcalc(.exe) unten eintragen.",
          "links": [["AcoustID: Anwendung registrieren", "https://acoustid.org/new-application"],
                    ["fpcalc (Chromaprint) herunterladen", "https://acoustid.org/chromaprint"]]},
         {"key": "acoustid", "type": "password", "label": "AcoustID: Anwendungs-Schlüssel"},
         {"key": "fpcalc", "type": "text", "label": "Pfad zu fpcalc (leer = im Suchpfad suchen)"},
         {"key": "clear", "type": "check", "label": "Gespeicherten Schlüssel und Pfad löschen", "default": False}]},
    {"id": "test", "label": "Verbindung testen", "where": "page", "run_label": "Testen", "needs_selection": False,
     "description": "Prüft Schlüssel und fpcalc.", "options": []},
]


def keys(ctx) -> dict:
    return sk.load_keys(ctx, KEYS + PLAIN)


def fpcalc_path(k) -> str:
    p = (k.get("fpcalc") or "").strip()
    if p and os.path.isfile(p):
        return p
    return shutil.which("fpcalc") or shutil.which("fpcalc.exe") or ""


def ready(ctx):
    k = keys(ctx)
    if not k.get("acoustid"):
        return False, "kein Schlüssel"
    if not fpcalc_path(k):
        return False, "fpcalc nicht gefunden"
    return True, ""


def auth(ctx):
    k = keys(ctx).get("acoustid")
    return {"params": {"client": k}} if k else {}


def fp_candidates(ctx, cl, f, mb) -> list:
    """Fingerabdruck mit fpcalc, Abfrage bei AcoustID → MusicBrainz-Aufnahmen (über das Plugin MusicBrainz)."""
    k = keys(ctx)
    exe = fpcalc_path(k)
    if not exe or not k.get("acoustid") or mb is None:
        return []
    try:
        r = subprocess.run([exe, "-json", f.path], capture_output=True, text=True, timeout=120)
        fp = json.loads(r.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError) as ex:
        ctx.log(f"fpcalc: {ex}")
        return []
    if not fp.get("fingerprint"):
        return []
    url = (f"{API}/lookup?client={sk.q(k['acoustid'])}&meta=recordings&format=json"
           f"&duration={int(fp.get('duration') or 0)}&fingerprint={sk.q(fp['fingerprint'])}")
    d = cl.json(url) or {}
    if d.get("status") != "ok":
        ctx.log(f"AcoustID: {(d.get('error') or {}).get('message', 'Fehler')}")
        return []
    out = []
    for res in sorted(d.get("results") or [], key=lambda x: -(x.get("score") or 0))[:3]:
        for rec in res.get("recordings") or []:
            if rec.get("id"):
                c = mb.recording(cl, rec["id"])
                if c:
                    c["fp_score"] = res.get("score") or 0
                    out.append(c)
    return out


def status(ctx):
    k = keys(ctx)
    return ("Schlüssel gespeichert" if k.get("acoustid") else "kein Schlüssel") + \
        (" · fpcalc gefunden" if fpcalc_path(k) else " · fpcalc nicht gefunden")


def run(action, ctx, files, opts):
    if action == "keys":
        sk.keys_action(ctx, opts, KEYS, PLAIN)
        return {"message": status(ctx)}
    if action == "test":
        ok, why = ready(ctx)
        if not keys(ctx).get("acoustid"):
            return {"message": "AcoustID: " + why}
        try:
            d = sk.client(ctx, INTERVALS).json(f"{API}/lookup?client={sk.q(keys(ctx)['acoustid'])}&trackid=00000000-0000-0000-0000-000000000000&format=json") or {}
            bad = d.get("status") != "ok" and (d.get("error") or {}).get("code") == 4
            return {"message": "AcoustID: " + ("Schlüssel ungültig" if bad else "in Ordnung") + ("" if ok else f" · {why}")}
        except HttpError as ex:
            return {"message": f"AcoustID nicht erreichbar: {ex}"}
    raise ValueError(f"Unbekannte Aktion: {action}")
