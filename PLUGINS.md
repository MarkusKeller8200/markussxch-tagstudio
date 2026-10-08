# Plugins für MarKusSXCH TagStudio

Plugins erweitern die neue Oberfläche um eigene Funktionen. Ihre Aktionen erscheinen im **Tagger** unter
„Plugins“ und arbeiten mit den dort markierten Dateien. Verwaltet werden sie auf der Seite **Plugins**
(Seitenleiste): Status, Ein/Aus, fehlende Pakete per Knopf installieren.

> Plugins sind normaler Python-Code mit allen Rechten. Nur Plugins aus vertrauenswürdigen Quellen verwenden.

## Wo liegen Plugins?

| Ordner | Inhalt |
|---|---|
| `plugins/` im Programmordner | eingebaute Plugins (z. B. **Stems**) |
| `~/TagStudio/Plugins/` (Windows: `C:\Users\<Name>\TagStudio\Plugins`) | eigene Plugins – „Plugin-Ordner öffnen“ |
| `~/TagStudio/Plugin-Daten/<id>/` | Daten eines Plugins (Modelle, Caches) |

Ein eigenes Plugin mit derselben `id` wie ein eingebautes ersetzt dieses. Nach dem Hineinkopieren auf der
Plugin-Seite **Neu einlesen** klicken.

## Aufbau

```
Plugins/
  mein-plugin/
    plugin.json
    plugin.py
```

### plugin.json

```json
{
  "id": "mein-plugin",
  "name": "Mein Plugin",
  "version": "1.0",
  "api": 1,
  "description": "Was es tut – erscheint auf der Plugin-Seite.",
  "author": "Name",
  "requires": [{"module": "numpy", "label": "NumPy"}],
  "install": [{"id": "std", "label": "Installieren", "packages": ["numpy"], "hint": "optionaler Hinweis"}],
  "external": [{"cmd": "ffmpeg", "label": "FFmpeg", "hint": "So installierst du es …"}],
  "notes": "Zusätzlicher Hinweis bei fehlenden Paketen"
}
```

- `id`: Kleinbuchstaben, Ziffern, `-`, `_`.
- `requires`: Python-Module, die vorhanden sein müssen. Fehlen sie, steht das Plugin auf „Pakete fehlen“
  und bietet die `install`-Varianten als Knöpfe an (`pip install …` mit dem Python von TagStudio).
- `external`: Programme, die im Suchpfad liegen sollten (nur Hinweis, blockiert nicht).

### Eigene Python-Umgebung (`env`) – für schwere Pakete

```json
"env": {"python": "3.12", "check": ["mein_paket"]},
"install": [{"id": "cpu", "label": "Installieren", "packages": ["mein-paket"],
             "extra_index": ["https://…"]}]
```

Mit `env` installiert TagStudio die Pakete **nicht** in sein eigenes Python, sondern legt mit
[uv](https://docs.astral.sh/uv/) eine eigene Umgebung an (`~/TagStudio/Plugin-Daten/<id>/env`). Die gewünschte
Python-Version lädt uv bei Bedarf selbst herunter – so funktionieren Pakete wie PyTorch auch dann, wenn TagStudio
mit einer neueren Python-Version läuft, für die es sie noch nicht gibt. `check` sind Module, deren Import nach der
Installation geprüft wird. Code, der diese Pakete braucht, läuft als eigener Prozess:

```python
rc, tail = ctx.run_env([os.path.join(os.path.dirname(__file__), "worker.py"), "auftrag.json"], on_line)
```

`on_line` bekommt jede Ausgabezeile (z. B. JSON-Fortschrittsmeldungen), Abbrechen beendet den Prozess.
`ctx.env_info` enthält die installierte Variante. Vorlage: `plugins/stems/` (plugin.py + worker.py).

### plugin.py

```python
ACTIONS = [{
    "id": "mark",
    "label": "Markieren …",          # Knopf im Tagger
    "where": "tagger",
    "description": "Tooltip / Text im Dialog",
    "run_label": "Ausführen",        # Text des Startknopfs
    "options": [                     # daraus entsteht das Formular automatisch
        {"key": "text",  "type": "text",   "label": "Text", "default": "hallo"},
        {"key": "loud",  "type": "check",  "label": "Groß schreiben"},
        {"key": "n",     "type": "number", "label": "Zahl", "default": 2},
        {"key": "mode",  "type": "select", "label": "Modus", "choices": [["a", "Variante A"], ["b", "B"]], "default": "a"},
        {"key": "ziel",  "type": "folder", "label": "Ordner"},
        {"type": "info", "label": "Nur ein Hinweistext."},
    ],
}]

def run(action, ctx, files, options):
    for i, f in enumerate(files):
        ctx.progress(i, len(files), f.path)      # Fortschritt; löst bei Abbruch Cancelled aus
    ctx.edit_tags(files, lambda f: f.set_text("TXXX:Notiz", options["text"]), "Notiz setzen")
    ctx.log("alles gut")
    return {"message": f"{len(files)} Datei(en) bearbeitet."}
```

Weitere Angaben je Aktion:

- `"where": "page"` – Knopf auf der Plugin-Karte statt im Tagger (z. B. Anmelden); dann meist `"needs_selection": false`.
- Optionstypen zusätzlich `password` (wird nie gespeichert), `textarea`; `"secret": true` verhindert das Merken
  bei jedem Typ. `"show_if": {"method": "login"}` zeigt ein Feld nur, wenn ein anderes Feld diesen Wert hat.
- Eine Funktion `status(ctx)` im Plugin liefert einen Statustext für die Karte (z. B. „Angemeldet als …“).

Statt `ACTIONS` geht auch eine Funktion `actions(ctx)`, die die Liste liefert (z. B. für dynamische Auswahl).
Die zuletzt benutzten Werte merkt sich TagStudio pro Aktion.

### Der Kontext `ctx`

| | |
|---|---|
| `ctx.progress(i, total, text)` | Fortschrittsbalken; prüft dabei auf Abbruch |
| `ctx.status(text)` | Statuszeile im Fortschrittsfenster |
| `ctx.cancelled()` / `ctx.check_cancel()` | Abbruch abfragen / bei Abbruch beenden |
| `ctx.log(text)` | Zeile ins Protokoll (wird nach dem Lauf angezeigt) |
| `ctx.output(pfad)` | erzeugte Datei/Ordner melden („Im Explorer zeigen“) |
| `ctx.edit_tags(files, fn, label)` | Tags ändern – mit Rückgängig, gespeichert wird wie gewohnt mit „Speichern“ |
| `ctx.propose(f, key, neu, label, note=, checked=)` | Änderung **vorschlagen**: nach dem Lauf erscheint eine Vorschau mit Häkchen, übernommen wird erst nach Bestätigung (mit Rückgängig). `kind="cover", data=Bytes` für Cover |
| `ctx.data_dir` | eigener Datenordner des Plugins |
| `ctx.run_env(args, on_line)` | Python der eigenen Umgebung starten (nur mit `env`) |

Protokolle (Installation, Fehler mit Details) liegen in `~/TagStudio/Logs` – Knopf „Protokolle“ auf der Plugin-Seite.

`files` sind die geladenen `MP3File`-Objekte (`f.path`, `f.text("TIT2")`, `f.set_text(key, wert)`, `f.items`).
Tags nur über `ctx.edit_tags` ändern – dann funktionieren Rückgängig, Anzeige und Speichern.

Rückgabe von `run`: ein Dict mit `message` (Pflicht), optional `log` (Liste) und `outputs` (Liste).
Ausnahmen werden als Fehlermeldung angezeigt.

## Eingebaut: Stems

Trennt Titel in Einzelspuren mit [audio-separator](https://github.com/nomadkaraoke/python-audio-separator)
(Demucs, BS-RoFormer, Mel-Band-RoFormer). Läuft in einer eigenen Umgebung mit Python 3.12 – unabhängig davon,
mit welcher Python-Version TagStudio läuft. FFmpeg wird mitinstalliert.

1. Seite **Plugins** → bei „Stems“ eine Variante installieren:
   **Prozessor** (läuft überall), **AMD/Intel-Grafik (DirectML)** (Windows, experimentell) oder
   **NVIDIA-Grafikkarte**. Download zusammen 1–4 GB. Später lässt sich die Variante unter
   „Neu installieren / andere Variante …“ wechseln.
2. Im Tagger Titel markieren → **Plugins → Stems erzeugen …** → Modell, Spuren, Format, Ablage wählen.

Ergebnis: Ordner `<Titel> – Stems` neben dem Titel (oder im gewählten Ordner) mit `<Titel> (Vocals).flac` usw.
Bei MP3 werden Tags und Cover übernommen, der Titel bekommt den Zusatz „(Vocals)“. Die Modelle landen in
`~/TagStudio/Plugin-Daten/stems/modelle` und werden nur einmal geladen.

## Eingebaut: Beatport (inoffiziell)

Holt BPM, Tonart (in deiner Schreibweise), Genre/Subgenre, Label, Katalognummer, Datum, ISRC, Remixer, Cover
und optional Titel/Künstler/Album von Beatport. Nutzt die Beatport-API v4 mit **deinem eigenen Beatport-Konto**
– derselbe Weg wie das beets-Plugin „beatport4“. Inoffiziell: Beatport kann den Zugang jederzeit ändern.

1. Seite **Plugins** → Beatport → **Anmelden …**
   - *Benutzername und Passwort*: Das Passwort wird nur für die Anmeldung benutzt und **nie gespeichert**.
   - *Token aus dem Browser*: auf api.beatport.com/v4/docs anmelden, Entwicklertools (F12) → Netzwerk →
     Anfrage „token“ → Antwort (JSON) kopieren und einfügen.
   Gespeichert wird nur der Token, unter Windows mit DPAPI verschlüsselt (nur dein Benutzerkonto kann ihn lesen).
   Abgelaufene Tokens werden automatisch erneuert.
2. Im Tagger Titel markieren → **Plugins → Beatport-Daten holen …** → Felder wählen, „Nur leere Felder füllen“
   oder „Überschreiben“.
3. **Vorschau:** je Datei der gefundene Beatport-Titel mit Sicherheit in %, darunter jedes Feld alt → neu.
   Unsichere Treffer sind nicht vorausgewählt. Bei „Nur leere Felder füllen“ erscheinen schon gefüllte Felder
   mit anderem Wert trotzdem – aber **nicht angehakt** („schon gefüllt“); gleiche Werte (auch in anderer
   Schreibweise, z. B. Tonart Am = 8A, BPM 124.0 = 124) werden nur gezählt. Im Protokoll steht je Titel, welche
   Felder Beatport geliefert hat. „Übernehmen“ ändert die Tags (rückgängig machbar), geschrieben
   wird wie immer erst mit „Speichern“.

Treffer: zuerst über eine gespeicherte Beatport-ID (`TXXX:BEATPORT_TRACK_ID`), dann ISRC, sonst Suche nach
Künstler + Titel + Mix-Name; bewertet werden Titel, Künstler, Länge und Mix-Name. Höchstens ~3 Anfragen pro Sekunde.
