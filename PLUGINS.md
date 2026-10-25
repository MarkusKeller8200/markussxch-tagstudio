# Plugins für MarKusSXCH TagStudio

*English: [PLUGINS.en.md](PLUGINS.en.md)*

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

### Plugins nachladen und aktualisieren

**Verfügbare Plugins …** (Plugin-Seite oben) lädt den Plugin-Katalog des neuesten Releases im gewählten Update-Kanal
(„nur offizielle Versionen“ bzw. „auch Beta-Versionen“) und listet alle Plugins – gruppiert nach Updates, neuen,
installierten und nicht verträglichen, mit Kategoriefilter. Karten mit neuerer Version zeigen **Update verfügbar → Aktualisieren**. TagStudio lädt nur aus den offiziellen
Releases dieses Projekts und prüft die Prüfsumme. Das geladene Plugin liegt danach im Ordner „Eigene Plugins“
(Abzeichen „nachgeladen“) und ersetzt die eingebaute Version; **Mehr … → Zurück auf eingebaute Version** entfernt es
wieder. Eigene Plugins werden dabei nie überschrieben.

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
  "min_app": "4.8.0",
  "category": "online",
  "api": 1,
  "description": "Was es tut – erscheint auf der Plugin-Seite.",
  "author": "Name",
  "requires": [{"module": "numpy", "label": "NumPy"}],
  "install": [{"id": "std", "label": "Installieren", "packages": ["numpy"], "hint": "optionaler Hinweis"}],
  "external": [{"cmd": "ffmpeg", "label": "FFmpeg", "hint": "So installierst du es …"}],
  "notes": "Zusätzlicher Hinweis bei fehlenden Paketen",
  "fields": ["TXXX:MEIN_PLUGIN_*"],
  "i18n": {"en": {"Mein Text": "My text"}}
}
```

- `min_app`: älteste TagStudio-Version, mit der das Plugin läuft. Der Plugin-Katalog bietet das Plugin nur dort an.
  Bei Änderungen an einem Plugin die `version` erhöhen, sonst erscheint kein Update.
- `links` (optional): `[{"label", "url", "desc"}]` – erscheinen unter „Mehr …“ auf der Plugin-Karte, z. B. Download
  einer Zusatz-App (nur `https://`, höchstens 8).
- `id`: Kleinbuchstaben, Ziffern, `-`, `_`.
- `category`: Kennzeichen auf der Plugin-Karte – `online` (Online-API), `local_api` (Lokale API), `import`
  (Übernahme aus Tags), `audio` (Audio-Verarbeitung) oder `other` (Sonstiges, Standard).
- Seiten-Aktionen mit den IDs `test`, `keys` bzw. `login` und `settings` erscheinen als feste Knöpfe „Testen“,
  „Schlüssel“/„Anmelden“ und „Optionen“; alle übrigen unter „Mehr …“. Dort stehen bei jedem Plugin zusätzlich
  „Log-Ordner öffnen“ und „Protokoll live anzeigen …“ (#293): `ctx.log(...)` erscheint im Live-Fenster sofort,
  in `Logs/<id>.log` wie bisher am Ende des Vorgangs.
- `requires`: Python-Module, die vorhanden sein müssen. Fehlen sie, steht das Plugin auf „Pakete fehlen“
  und bietet die `install`-Varianten als Knöpfe an (`pip install …` mit dem Python von TagStudio).
- `external`: Programme, die im Suchpfad liegen sollten (nur Hinweis, blockiert nicht).
- `background`: `true` → Aktionen laufen als **Hintergrund-Auftrag** in einer Warteschlange (wie Stems): Der Dialog
  schliesst sofort, man kann weiterarbeiten. Das Plugin bekommt eigene, frisch von der Platte gelesene Dateien
  (`ctx.background` ist `True`), Prozesse über `ctx.run_env` laufen mit niedriger Priorität. Für lange Aktionen,
  die neue Dateien erzeugen – Tag-Änderungen und Vorschläge gehören in Vordergrund-Aktionen. Auch je Aktion
  möglich (`"background": true` im ACTIONS-Eintrag).
- `fields`: Felder, die das Plugin schreibt (Muster mit `*`). TagStudio zeigt bei diesen Feldern die Herkunft
  „TagStudio · Plugin-Name“ an (Tagger, Vergleich), damit eigene Felder erkennbar bleiben.
- `i18n`: Übersetzungen der Plugin-Texte je Sprache (`en`, `gsw-u-sd-chzh`): deutscher Text → Übersetzung. Die
  Oberfläche nutzt sie, wenn diese Sprache gewählt ist; Texte ohne Übersetzung bleiben deutsch.

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

**Zusatzdateien (`env.files`, #245):** Modelle oder Programmteile, die nicht als Python-Paket kommen, lädt die
Installation nach den Paketen – nur von GitHub (`https://raw.githubusercontent.com/…`, fester Commit) und immer mit
SHA-256-Prüfsumme. Stimmt die Prüfsumme nicht, wird nichts abgelegt. Fehlt eine Datei später, zeigt die Karte
„Daten: …“ und „Neu installieren …“ holt sie (die Umgebung bleibt).

```json
"env": {"python": "3.12", "check": ["torch"],
        "files": [{"label": "Modell (18 MB)", "path": "engine/modell.pt", "size": 18830452,
                   "url": "https://raw.githubusercontent.com/<owner>/<repo>/<commit>/modell.pt",
                   "sha256": "<64 Hex-Zeichen>"}]}
```

Die Dateien liegen unter `ctx.shared_dir/<path>` (z. B. `~/TagStudio/Plugin-Daten/<id>/engine/modell.pt`).

### plugin.py

```python
ACTIONS = [{
    "id": "mark",
    "label": "Markieren …",          # Knopf im Tagger
    "where": "tagger",
    "description": "Tooltip / Text im Dialog",
    "run_label": "Ausführen",        # Text des Startknopfs
    "short": "Kurzname",             # optional: kürzerer Name für die Plugin-Karte (#248)
    "options": [                     # daraus entsteht das Formular automatisch
        {"key": "text",  "type": "text",   "label": "Text", "default": "hallo"},
        {"key": "loud",  "type": "check",  "label": "Gross schreiben"},
        {"key": "n",     "type": "number", "label": "Zahl", "default": 2},
        {"key": "mode",  "type": "select", "label": "Modus", "choices": [["a", "Variante A"], ["b", "B"]], "default": "a"},
        {"key": "ziel",  "type": "folder", "label": "Ordner"},
        {"type": "info", "label": "Nur ein Hinweistext."},
        {"type": "info", "title": "Anleitung", "label": "Hinweis mit Links (nur https://, öffnen im Browser).",
         "links": [["Beispiel-Seite", "https://example.org"]]},
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
- Optionstypen zusätzlich `password` (wird nie gespeichert), `textarea`, `folders` (mehrere Ordner, je Zeile einer, mit Auswahl-Knopf „+ Ordner …“); `"secret": true` verhindert das Merken
  bei jedem Typ. `"show_if": {"method": "login"}` zeigt ein Feld nur, wenn ein anderes Feld diesen Wert hat.
- Eine Funktion `status(ctx)` im Plugin liefert einen Statustext für die Karte (z. B. „Angemeldet als …“).

Statt `ACTIONS` geht auch eine Funktion `actions(ctx)`, die die Liste liefert (z. B. für dynamische Auswahl).
Die zuletzt benutzten Werte merkt sich TagStudio pro Aktion.

### Der Kontext `ctx`

| | |
|---|---|
| `ctx.progress(i, total, text, frac=None)` | Fortschrittsbalken; prüft dabei auf Abbruch. `frac` (0–1) = Anteil des gerade laufenden Elements, damit der Balken auch bei langen Einzelschritten weiterläuft |
| `ctx.status(text)` | Statuszeile im Fortschrittsfenster |
| `ctx.cancelled()` / `ctx.check_cancel()` | Abbruch abfragen / bei Abbruch beenden |
| `ctx.log(text)` | Zeile ins Protokoll (wird nach dem Lauf angezeigt) |
| `ctx.output(pfad)` | erzeugte Datei/Ordner melden („Im Explorer zeigen“) |
| `ctx.edit_tags(files, fn, label)` | Tags ändern – mit Rückgängig, gespeichert wird wie gewohnt mit „Speichern“ |
| `ctx.propose(f, key, neu, label, note=, checked=)` | Änderung **vorschlagen**: nach dem Lauf erscheint eine Vorschau mit Häkchen, übernommen wird erst nach Bestätigung (mit Rückgängig). `kind="cover", data=Bytes` für Cover (ohne `data` = reine Info-Zeile). `hint=` Hinweis zum Feld, `show_same=True` zeigt auch unveränderte Werte (grau, nicht wählbar) |
| `importsync.propose(ctx, f, quelle, name, merkmal, wert)` | Audio-Merkmal (0–100) aus einer anderen Quelle **mit Abgleich** vorschlagen: leeres Feld oder seit dem letzten Übernehmen unveränderte Datei → angehakt, sonst nicht angehakt („fragen“). Der übernommene Wert wird in `TXXX:TAGSTUDIO` gemerkt. Beispiele: Plugins *beaTunes* und *Lexicon* |
| `ctx.propose(…, kind="rating")` | Bewertung 0–5 Sterne vorschlagen (`neu` = Anzahl Sterne, POPM) |
| `ctx.propose(…, kind="remote", old=…, data=…)` | Änderung **ausserhalb der Datei** vorschlagen (z. B. in Lexicon): `old` = bisheriger Wert dort, `data` = Angaben fürs Plugin. Nach Bestätigung ruft TagStudio `apply_remote(ctx, items)` des Plugins auf (Rückgabe `{"message", "errors"}`) |
| `ctx.djset()` | aktuelles DJ-Set: `{"name", "paths"}` (nur lesen) |
| `ctx.data_dir` | eigener Datenordner des Plugins im aktuellen Profil (Anmeldungen, Ergebnisse) |
| `ctx.shared_dir` | gemeinsamer Ordner für grosse Daten (Modelle, Programme) – für alle Profile gleich |
| `ctx.run_env(args, on_line)` | Python der eigenen Umgebung starten (nur mit `env`) |

Protokolle (Installation, Fehler mit Details) liegen in `~/TagStudio/Logs` – Knopf „Protokolle“ auf der Plugin-Seite.

`files` sind die geladenen `MP3File`-Objekte (`f.path`, `f.text("TIT2")`, `f.set_text(key, wert)`, `f.items`).
Tags nur über `ctx.edit_tags` ändern – dann funktionieren Rückgängig, Anzeige und Speichern.

Rückgabe von `run`: ein Dict mit `message` (Pflicht), optional `log` (Liste) und `outputs` (Liste).
Mit `"open": {"target": "tagger" | "djset" | "djadd", "files": [Pfade], "label": "…"}` lädt TagStudio die Dateien in den
Tagger und auf Wunsch als neues DJ-Set bzw. zusätzlich ins DJ-Set (Reihenfolge bleibt). Ausnahmen werden als
Fehlermeldung angezeigt.

Weitere Funktionen, die ein Plugin anbieten kann (alle optional):

- `on_event(ctx, event, data)` – TagStudio meldet `"files_moved"` (`[{"old", "new"}]`: umbenannt, archiviert,
  zurückgeholt) und `"files_added"` (`[Pfad]`: neu in die Bibliothek übernommen, Vorbereiten). Läuft im Hintergrund,
  Fehler landen nur im Protokoll.
- `detect_files(ctx, paths)` – Vorbereiten: Status-Schritt mit „Erkennung“ = Plugin-ID erkennt diese Dateien als
  erledigt (Beispiel: Lexicon – Datei ist in Lexicon).
- `apply_remote(ctx, items)` – siehe `kind="remote"` oben.
- `playlists(ctx)` → `[{id, name, path, depth, type}]` und `playlist_files(ctx, id)` → `{name, files, missing}` –
  das DJ-Set bietet dann „Aus <Plugin> …“: Playlists auswählen und als Listen laden (Beispiel: Lexicon).
- `store_purchases(ctx)` → `{"name", "items": [{id, title, mix, artist, dur, key, bpm, catalog, isrc, label, release,
  genre, url, bought, preorder, dl}]}` und `store_download(ctx, items, dest)` → `{"files": {id: [Pfade]}, "failed"}` –
  Seite „Käufe“ (#285): gekaufte Titel eines Stores sammeln und fehlende herunterladen (Beispiel: Beatport).
- `playlist_push(ctx, playlist, options)` – Seite Playlists › Mehr ▾ › „An <Plugin> senden …“ (#273). `playlist` =
  `{"name", "folder", "items": [{"path", "artist", "title"}], "remote"}` (`remote` = die ID, die das Plugin beim
  letzten Senden zurückgegeben hat, sonst `None`). Rückgabe `{"ok", "id", "message", "missing": [Pfade], …}`; TagStudio
  merkt sich `id` je Playlist, erneutes Senden soll dieselbe Playlist nachführen. Optional `push_ready(ctx)` →
  `(bereit, Hinweis)`, z. B. wenn das Schreiben im Plugin ausgeschaltet ist. Regeln: nie etwas löschen, Einträge ohne
  Datei auslassen und melden, Änderungen ins eigene Journal (Beispiel: Lexicon – legt an bzw. fügt fehlende Titel an
  ihrer Stelle ein, entfernt nichts).

## Werkzeug: API-Rekorder (für Entwickler)

`python tools/api_recorder.py https://… [--host api.…]` öffnet die Seite in Chromium (Playwright), liest beim
Durchklicken die JSON-Aufrufe der Seite mit und schreibt nach dem Schliessen `recording.json` und `service.json` –
einen Entwurf des Abschnitts `"service"` mit Endpunkten wie `/tracks/{track_id}`, Parametern und Antwortfeldern
(Ordner `~/TagStudio/API-Aufnahmen/<host>`). Cookies, Anmeldung, Tokens, Passwörter und E-Mail-Adressen werden nie
gespeichert. Nur für Schnittstellen verwenden, die du nutzen darfst.

## Eingebaut: Tonart (OpenKeyScan) und OpenKeyScan-App

Zwei Wege zur Tonart-Erkennung mit [OpenKeyScan](https://www.openkeyscan.com) (Rekordcloud) – gleiches Ergebnis,
gleiche Vorschau (#217):

- **Tonart (OpenKeyScan)** (`keyscan`, #245) – ohne Zusatz-App, offline. Eigene Umgebung mit Python 3.12, PyTorch,
  librosa und PyAV (Variante **Prozessor** oder **NVIDIA**, ca. 1 GB). Netz und Modell der quelloffenen Engine
  ([openkeyscan-analyzer](https://github.com/rekordcloud/openkeyscan-analyzer), MIT; Modell trainiert mit den
  GiantSteps-Datensätzen, CC BY-SA 4.0) lädt die Installation von einem festen Commit und prüft sie mit SHA-256.
  Aktionen: **Tonart erkennen (OpenKeyScan) …** (Vorschau) und **Tonart im Hintergrund analysieren …** (merkt sich nur
  das Ergebnis, schreibt nichts – danach ist die Vorschau sofort da).
- **OpenKeyScan-App** (`openkeyscan`, #244) – über die lokale API der Desktop-App (`http://localhost:58721`, Windows
  und macOS). Bis 20 Titel einzeln (`/analyze/single`), darüber über die Warteschlange (`/analyze/add`,
  `/analyze/results`). Nur Adressen auf diesem Rechner, nie über einen Proxy; `/analyze/clear` wird nie aufgerufen.
  **In der App „Auto-Tagging“ ausschalten** – sonst schreibt sie selbst in die Dateien. Ändert sich eine Datei während
  der Analyse, warnt TagStudio. Antwortet der Server nicht, startet TagStudio die App selbst (Option „App bei Bedarf
  selbst starten“, Programm wird gesucht oder unter Optionen eingetragen) und wartet bis 30 s; läuft die App ohne
  Server, sagt die Meldung das. Unter **Mehr …** stehen Download-Links für Windows und Mac.
- Beim Plugin „Tonart (OpenKeyScan)“ prüft **Testen** die Umgebung (Modell laden, Gerät melden); unter **Optionen**
  lässt sich „Immer Prozessor“ wählen.

Vorschau (beide): `TXXX:OPENKEYSCAN_KEY` (Camelot, z. B. `09A`, Herkunft „OpenKeyScan“) und auf Wunsch `TKEY` in der
eingestellten Schreibweise. TKEY ist nur angekreuzt, wenn es leer ist (Option „Abweichende … ebenfalls ankreuzen“).
Die Notiz vergleicht mit TKEY, Beatport (`TXXX:INITIAL_KEY`) und dem Mixed-In-Key-Kommentar: gleich, verwandt
(±1 auf dem Rad oder Paralleltonart) oder abweichend; dazu die Sicherheit des Modells (nur `keyscan`). Ergebnisse
werden je Datei (Grösse + Änderungszeit) zwischengespeichert. Als Schritt in **Vorbereiten** einsetzbar (Schritt-Typ
„Plugin“, Modus „nur leere Felder füllen“).

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

## Eingebaut: Beatport

Holt BPM, Tonart (in deiner Schreibweise), Genre/Subgenre, Label, Katalognummer, Datum, ISRC, Remixer, Cover
und optional Titel/Künstler/Album von Beatport, dazu Beatport-Playlists und die Seite „Käufe“. Nutzt die
**offizielle Beatport-API v4** – alle Endpunkte mit Status stehen unter Plugins › Beatport › „Integration …“.
Inoffiziell sind nur noch der Ausweichweg bei der Anmeldung und der Download gekaufter Dateien (Beatport bietet ihn
offiziell nicht an). Der Download nutzt zuerst denselben Weg wie die Beatport-Webseite
(`/catalog/tracks/purchase-download/?order_item_download_id=…`, #292, Plugin 1.4); jeder Download zählt bei Beatport
als Download-Versuch wie auf der Webseite.

1. Seite **Plugins** → Beatport → **Anmelden …**
   - *Eigener API-Zugang* (Standard, empfohlen): Client-ID, Client-Secret, Benutzername, Passwort – siehe unten.
   - *Benutzername und Passwort* (inoffizieller Ausweichweg, wie das beets-Plugin „beatport4“ über die Kennung der
     Doku-Seite): Das Passwort wird nur für die Anmeldung benutzt und **nie gespeichert**.
   - *Token aus dem Browser*: auf api.beatport.com/v4/docs anmelden, Entwicklertools (F12) → Netzwerk →
     Anfrage „token“ → Antwort (JSON) kopieren und einfügen.
   Gespeichert wird nur der Token, unter Windows mit DPAPI verschlüsselt (nur dein Benutzerkonto kann ihn lesen).
   Abgelaufene Tokens werden automatisch erneuert.
2. Im Tagger Titel markieren → **Plugins → Beatport-Daten holen …** → Felder wählen, „Nur leere Felder füllen“
   oder „Überschreiben“.
3. **Vorschau:** je Datei der gefundene Beatport-Titel mit Sicherheit in %, darunter jedes Feld alt → neu.
   Unsichere Treffer sind nicht vorausgewählt. Bei „Nur leere Felder füllen“ erscheinen schon gefüllte Felder
   mit anderem Wert trotzdem – aber **nicht angehakt** („schon gefüllt“). Es erscheinen **alle Felder, die
   Beatport liefert**: gleiche Werte grau mit „=“ (nicht wählbar), gleicher Wert in anderer Schreibweise
   (z. B. Tonart Am = 08A, BPM 124.0 = 124) und in den Optionen abgewählte Felder ungehakt, ein verfügbares Cover
   als Info-Zeile. Im Protokoll steht je Titel, welche
   Felder Beatport geliefert hat. „Übernehmen“ ändert die Tags (rückgängig machbar), geschrieben
   wird wie immer erst mit „Speichern“.

Treffer: zuerst über eine gespeicherte Beatport-ID (`TXXX:BEATPORT_TRACK_ID`), dann ISRC, sonst Suche nach
Künstler + Titel + Mix-Name; bewertet werden Titel, Künstler, Länge und Mix-Name. Höchstens ~3 Anfragen pro Sekunde.

**Eigener API-Zugang (#286):** Wer bei Beatport eine eigene API-App hat, wählt unter „Anmelden …“ die Methode
„Eigener API-Zugang“ und trägt Client-ID, Client-Secret, Benutzername und Passwort ein (Password Grant laut offizieller
Doku). Client-ID und Secret werden verschlüsselt im Plugin gespeichert (leer lassen = gespeicherte verwenden), das
Passwort nie. Das Token wird mit Client-ID und Secret erneuert; „Abmelden“ zieht es bei Beatport zurück.

**Gefolgte Künstler und Labels (#288):** „Gefolgte Künstler und Labels in „Entdecken“ übernehmen …“ liest, wem du
auf Beatport folgst („My Beatport“, `/my/beatport/artists/` und `/labels/`), und ergänzt die Listen in „Entdecken“.
Vorhandene bleiben, bei Beatport wird nichts geändert. Dasselbe geht direkt in „Entdecken“ › Gefolgt › „Von Beatport
übernehmen“ (#291); dort sind solche Einträge mit „BP“ markiert. Mit Quelle Beatport holt „Suchen“ zusätzlich die
neuen Titel aus „My Beatport“ (`/my/beatport/tracks/`).

**Käufe (#285):** Die Seite „Käufe“ nutzt `store_purchases(ctx)` (alle Käufe mit Titel, Mix, Tonart, BPM,
Katalognummer, Link, Kaufdatum) und `store_download(ctx, items, dest)` (fehlende in den Eingangsordner laden).

**Playlists (#284, nur lesen):** Nach dem Anmelden bietet Playlists › Importieren ▾ **„Aus Beatport …“**: deine
eigenen Beatport-Playlists wählen, sie kommen als Playlists mit Einträgen ohne Datei (Künstler, Titel, Mix, ISRC,
Länge, Link zu Beatport) in den Ordner „Beatport“; sichere Treffer in der Bibliothek werden gleich verknüpft, der Rest
lässt sich abgleichen oder als Einkaufsliste exportieren. Erneut holen aktualisiert die Playlist und behält
Verknüpfungen. Auch hier inoffiziell (`/my/playlists/`): Liefert Beatport nichts, stehen die Feldnamen der Antwort im
Protokoll (Plugins › Beatport).

## Eingebaut: Spotify und SoundCloud

Lesen deine Playlists und Titel-Daten bei Spotify bzw. SoundCloud – **nur lesen**, in deinem Konto wird nichts
geändert. Beide brauchen eine **eigene App** beim Dienst; TagStudio liefert keine gemeinsamen Zugangsdaten mit.

- **Spotify:** auf [developer.spotify.com](https://developer.spotify.com/dashboard) mit deinem Konto anmelden
  (Spotify Premium nötig), „Create app“, als Redirect URI genau `http://127.0.0.1:8765/callback` eintragen, „Web API“
  wählen. Die Client-ID unter Plugins › Spotify › **Anmelden …** einfügen (ein Secret ist nicht nötig, Anmeldung mit
  PKCE). Entwicklungsmodus: höchstens 5 Nutzer je App. Seit Februar 2026 liefert Spotify Titel nur für eigene bzw.
  gemeinsame Playlists, die Suche höchstens 10 Treffer je Abfrage und beim Album kein Label mehr.
- **SoundCloud:** App in „SoundCloud for Developers“ registrieren (Selbstregistrierung mit Artist Pro), Redirect URI
  `http://127.0.0.1:8766/callback`. Client-ID **und** Client-Secret unter Plugins › SoundCloud › **Anmelden …**
  einfügen (OAuth 2.1 mit PKCE).
- **Anmelden …** öffnet die Anmeldeseite im Browser; TagStudio nimmt die Rückleitung auf `127.0.0.1` kurz selbst an.
  Geht das nicht (Port belegt), „Adresse einfügen“ wählen: nach der Zustimmung die Adresse aus der Adresszeile
  einfügen. Zugangsdaten und Token liegen verschlüsselt im Datenordner des Plugins und werden automatisch erneuert;
  „Abmelden …“ löscht die Anmeldung (wahlweise auch die Zugangsdaten).
- **Playlists › Importieren ▾ › „Aus Spotify …“ / „Aus SoundCloud …“** (erscheint nach der Anmeldung): Lieblingssongs
  bzw. Likes, eigene Titel (SoundCloud) und deine Playlists als Playlists mit **Einträgen ohne Datei** (Künstler,
  Titel, Mix, ISRC, Dauer, Link) im Ordner „Spotify“ bzw. „SoundCloud“ – danach „Mit Bibliothek abgleichen …“ und
  „Einkaufsliste exportieren …“ (mit Link). „↗“ in der Liste öffnet den Titel beim Dienst.
- **Online-Metadaten:** Quellen „Spotify“ und „SoundCloud“ (aus, bis du sie anhakst) – Album, Datum, ISRC, Genre,
  Cover und als Felder `TXXX:SPOTIFY_TRACK_ID`/`TXXX:SPOTIFY_URL` bzw. `TXXX:SOUNDCLOUD_TRACK_ID`/`TXXX:SOUNDCLOUD_URL`.
- **„Gefolgte Künstler in „Entdecken“ übernehmen …“:** ergänzt die Künstler (Spotify, wahlweise auch deine Top 20)
  bzw. Konten (SoundCloud), denen du folgst, unter Entdecken › Gefolgte Künstler.
- Die Kachel zeigt unter „Endpunkte“ alle Lese-Endpunkte mit Umsetzungsstand; der API-Tester ruft sie mit deiner
  Anmeldung auf (Token geschwärzt).

## Eingebaut: Lexicon

Verbindet TagStudio mit [Lexicon DJ](https://www.lexicondj.com) über dessen Local API (in Lexicon: Settings ›
Integrations › Local API einschalten; Standard `http://localhost:48624`).

- **Lexicon übernehmen …** (Tagger): Werte ohne offizielles MP3-Feld kommen in **eigene Felder mit Herkunft
  „Lexicon“**, unverändert wie in Lexicon (1–10): `TXXX:LEXICON_DANCEABILITY`, `…_ENERGY`, `…_HAPPINESS`,
  `…_POPULARITY`, `…_COLOR`, `…_TAGS` (übrige Tag-Kategorien, wahlweise auch Grouping oder Kommentar) und
  `TXXX:LEXICON_MOOD` (in ID3v2.4 offiziell `TMOO`). Bewertung in `POPM`. Die TagStudio-Felder (ENERGY usw.) bleiben
  unverändert. Zuordnung gezielt über den Pfad, sonst über
  Künstler + Titel. Beatgrid und Cue-Punkte aus Lexicon werden mit der Datei verglichen (Hinweis in der Vorschau).
- **Aus Lexicon öffnen …** (Tagger, ohne Auswahl): die in Lexicon markierten Titel, die markierte Playlist oder eine
  Playlist über ihren Namen (`Sets/Freitag`) in den Tagger laden oder als DJ-Set übernehmen. Ordner und Smartlists
  gehen auch.
- **Lexicon-Werte in TagStudio-Felder …** (Tagger): übernimmt die Werte aus den `LEXICON_`-Feldern der Dateien in
  ENERGY, DANCEABILITY, HAPPINESS (×10) und die Stimmung – mit Vorschau und Abgleich, ohne Verbindung zu Lexicon.
  Beim Übernehmen aus Lexicon geht das auch gleich mit („Zusätzlich in die TagStudio-Felder übernehmen“).
- **DJ-Set › Aus Lexicon …:** alle Playlists (und die Warteschlange) holen, mit Häkchen wählen; jede wird als Liste
  „Lexicon: …“ gespeichert, die erste geladen.
- **Vorbereiten:** Der Status-Schritt „Lexicon“ erkennt Titel, die in Lexicon vorhanden sind.
- **Zurückschreiben** (Plugins › Lexicon › Optionen, standardmässig aus):
  - Pfade nachführen, wenn TagStudio Dateien umbenennt, archiviert oder zurückholt.
  - Neu in die Bibliothek übernommene Titel aufnehmen, in eine Playlist legen (Standard „TagStudio Neu“) und von
    Lexicon analysieren lassen.
  - **Nach Lexicon übertragen …** (Tagger): Titel, Künstler, Album, Genre, BPM, Tonart, Bewertung, Energie usw. und
    Stimmung als Mood-Tags – mit Vorschau, geändert wird nur in Lexicon.
  - **DJ-Set als Lexicon-Playlist …** (Mehr …).
  - **Letzte Änderung in Lexicon rückgängig …** stellt Werte und Pfade wieder her.

  Die Lexicon-API hat keine Anmeldung: TagStudio schreibt nur an Lexicon auf diesem Rechner (localhost) und löscht nie
  etwas. Jede Änderung steht im Journal (`Plugin-Daten/lexicon/journal.json`).
