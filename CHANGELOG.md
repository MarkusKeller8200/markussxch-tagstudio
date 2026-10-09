# Changelog – MarKusSXCH TagStudio

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/) (MAJOR.MINOR.PATCH). Versionen bis 2.8 hießen „MP3 Tag Compare“.
Neue Einträge kommen laufend unter **Unveröffentlicht**; `python packaging/release.py X.Y.Z` macht daraus eine Version.

## [Unveröffentlicht]

## [3.0.1] – 2026-10-09
Fehlerbehebungen.

### Behoben
- **Plugins:** Ein fehlerhaftes `plugin.json` (z. B. `"api": "1.0"`, Liste statt Objekt, falsche Einträge bei
  `requires`/`install`/`external`) legte die ganze Plugin-Seite und die Plugin-Knöpfe im Tagger lahm. Jetzt erscheint
  nur dieses Plugin mit Fehlermeldung, alle anderen laufen weiter.
- **Rückgängig:** Brach ein Plugin mitten im Ändern ab, blieben seine Teiländerungen im nächsten Rückgängig-Schritt
  hängen (falsche Beschriftung, Rückgängig nahm mehr zurück als erwartet). Der Schritt wird jetzt immer abgeschlossen.
- **Plugin-Vorschau:** Gleich benannte Dateien aus verschiedenen Ordnern (z. B. zweimal `01 Intro.mp3`) wurden zu
  einer Gruppe zusammengelegt. Sie bleiben jetzt getrennt, mit Ordnername zur Unterscheidung.
- **Beatport:** Titel in nicht-lateinischer Schrift (Kyrillisch, Japanisch …) galten immer als „gleich“, falsche
  Treffer waren sogar vorab angehakt. Jetzt wird die Schrift beim Vergleich erhalten.
- **Beatport:** Ein `Retry-After` als Datum (statt Sekunden) brach den ganzen Abruf ab.
- **Vergleich/Sicherungs-Viewer:** Nach Emoji im Wert wurden die Markierungen um ein Zeichen verschoben angezeigt.
- **Update-Knopf:** Ein ausstehender Wechsel vom alten Zweig `web-ui` auf `main` wurde nicht angeboten, solange es
  keine neuen Änderungen gab.
- **Versionierung:** `release.py` sortierte Vorabversionen als Text (`beta.10` galt als älter als `beta.9`).
- **Installer-Bau:** GitHub-Actions auf aktuelle Versionen (Node 24) umgestellt – keine Deprecation-Warnungen mehr.

## [3.0.0] – 2026-10-09
Grosses Update: neue Oberfläche mit Tagger und Plugins (entwickelt im Zweig `web-ui`, jetzt in `main`).

### Neu
- **Neue Oberfläche** (`tagstudio_web.py`, Ordner `web/`): modernes Design mit Seitenleiste, Hell/Dunkel,
  Paarliste mit Status-Filtern und Suche, Vergleich mit zeichengenauen Markierungen, Pfeil-Knöpfen,
  Bearbeiten per Doppelklick, Kontextmenü, Cover-Vorschau, Rückgängig/Wiederholen, Speichern mit Sicherung.
  Läuft im eigenen App-Fenster (pywebview) oder – ohne pywebview – im Browser.
  Start: `start_web_windows.bat` / `start_web_mac.command`.
- Splitter für Seitenleiste (einklappbar), Paarliste und Tabellenspalten; Layout wird gemerkt.
- **Tagger** in der neuen Oberfläche: Dateiliste (sortier-/filterbar), Mehrfachbearbeitung, Cover, ID3-Version,
  Tags aus Dateiname, Umbenennen nach Tags, Spurnummern, weitere Felder; gemeinsames Dateiregister mit dem Vergleich.
- Tagger-Werkzeuge (alle mit Vorschau, rückgängig machbar): **Groß-/Kleinschreibung vereinheitlichen**,
  **Suchen & Ersetzen** über viele Dateien, **Cover aus Bild im Ordner** (folder.jpg …),
  **Liste als Excel/CSV exportieren**.
- **Camelot-Rad** für die Tonart im Tagger: Tonart per Klick setzen, passende Tonarten hervorgehoben, Schreibweise
  Camelot/musikalisch/Open Key wählbar und für viele Dateien vereinheitlichen; Spalte „Tonart“ mit farbigen Codes.
- **Audio-Merkmale** im Tagger: zehn TXXX-Felder (Energy, Danceability, Happiness, Valence, Acousticness,
  Instrumentalness, Liveness, Speechiness, Brightness, Aggressiveness), 0–100, Schieberegler, Mehrfachauswahl,
  Export-Spalten.
- **Plugin-System** (`plugins.py`, Seite „Plugins“): Plugins aus `plugins/` und `~/TagStudio/Plugins`, Status,
  Ein/Aus, fehlende Pakete per pip installieren, Formulare aus den Optionen, Ausführung im Hintergrund mit
  Fortschritt/Abbruch, Tag-Änderungen mit Rückgängig. Anleitung: `PLUGINS.md`.
- Eingebautes Plugin **Stems**: Titel mit audio-separator (Demucs, BS-RoFormer, Mel-Band-RoFormer) in
  Einzelspuren trennen; FLAC/WAV/MP3 (MP3 mit Tags und Cover).
- Plugins können eine **eigene Python-Umgebung** verlangen (`env` in plugin.json): Installation per uv mit
  passender Python-Version, unabhängig vom Python von TagStudio. Stems nutzt das (Python 3.12, FFmpeg
  inklusive) – behebt die fehlgeschlagene Installation unter Python 3.14. Neue Variante AMD/Intel (DirectML).
- Eingebautes Plugin **Beatport (inoffiziell)**: Anmeldung mit eigenem Konto (Passwort nie gespeichert, Token
  mit DPAPI verschlüsselt), Abgleich über ID/ISRC/Suche mit Trefferbewertung, Vorschau mit Häkchen; schon gefüllte Felder werden
  ungehakt angezeigt statt still übersprungen, gleiche Werte gezählt, Protokoll je Titel.
- Plugin-System: Vorschläge mit Vorschau (`ctx.propose`), Aktionen auf der Plugin-Karte, Passwort-/Textfelder,
  bedingte Felder (`show_if`), Statustext je Plugin.
- Stems-Installation: `audioread` ergänzt und librosa auf 0.x festgelegt (audio-separator lud sonst nicht).
  Die Installation ergänzt fehlende, nicht deklarierte Module selbst und verwendet eine vorhandene Umgebung
  bei gleicher Variante weiter (kein erneuter PyTorch-Download).
- Protokolle in `~/TagStudio/Logs` (Installation, Plugin-Fehler mit Details); Knopf „Protokolle“.
- Neue Oberfläche jetzt mit **Tag-Fixer**, **Sicherungen** (prüfen, wiederherstellen, löschen, Einstellungen),
  **Sammelkopie** (Mehrfachauswahl in der Paarliste), **Feld hinzufügen** und **Bildern** (ersetzen, exportieren,
  entfernen, hinzufügen).
- **XML-Editor** für Felder mit XML-Inhalt (Baum- und Quelltextansicht, Prüfung mit Fehlerstelle, Formatieren/Kompakt);
  auch in der klassischen Oberfläche. XML in Binärfeldern (GEOB/PRIV) lässt sich ansehen.
- Knopf „Nach Update suchen“: prüft beim Start auf neue Versionen, lädt sie per Klick und startet neu.
- Gemeinsamer Kern `core.py` (Anzeige-Logik, Filter, Laden, Speichern) und `session.py`; beide Oberflächen
  nutzen dieselbe Logik und dieselben Einstellungen.
### Neu (Sicherungen)
- **Änderungs-Viewer** in den Sicherungen: Spalte „Geänderte Felder“ je Datei; Ansicht Feld für Feld
  „Vorher (Sicherung)“ ↔ „Jetzt“ mit Hervorhebung, Blättern durch geänderte Dateien, einzelne Datei wiederherstellen.

### Neu (Installer)
- **Installer** für Windows (`…-Windows-Setup.exe`, ohne Adminrechte) und macOS (`…-macOS-Apple-Chip.dmg`) –
  kein Python nötig. Gebaut von GitHub Actions bei jedem Versions-Tag, mit Selbsttest; erscheinen als GitHub-Release.

### Geändert
- Versionierung nach MAJOR.MINOR.PATCH mit einer einzigen Quelle (`version.py`), Abschnitt „Unveröffentlicht“ im
  CHANGELOG, `packaging/release.py`; Release-Workflow prüft Tag ↔ Version und veröffentlicht Beta-Tags als Vorabversion.
- Update-Knopf: wer noch auf dem Zweig `web-ui` steht, wird automatisch auf `main` umgestellt.
- Die klassische Oberfläche (`tagstudio.py`) nutzt den gemeinsamen Kern – Aussehen und Bedienung unverändert.
- Rückgängig/Wiederholen in `undo.py` ausgelagert.

## [2.9] – 2026-10-08
### Geändert
- Projekt umbenannt in **MarKusSXCH TagStudio** (Hauptdatei `tagstudio.py`, Einstellungen `~/.tagstudio.json`,
  Sicherungen `~/TagStudio/Sicherungen`, Cache `~/TagStudio/cache`).
- Einstellungen und Sicherungen der Vorgängerversion werden automatisch weiterverwendet.
### Neu
- Git-Repository, automatische Tests (`tests/`) und GitHub Actions für Windows, macOS und Linux.

## [2.8] – 2026-10-08
### Neu
- URLs in Tag-Werten sind klickbar und öffnen im Browser; Kontextmenü „Link öffnen“.
- Alle Dialoge, Meldungen und Dateidialoge öffnen sich zentriert über dem aktiven Programmfenster.

## [2.7] – 2026-10-08
### Neu
- Cover-Vorschau über der Tabelle, Unterschiede rot umrandet, große Ansicht per Klick.
- Suche und Filter in der Paarliste (Feld · Bedingung · Wert · Seite), „Felder suchen“ in der Tabelle.

## [2.6] – 2026-10-08
### Neu
- Rückgängig/Wiederholen (Strg/Cmd+Z, Strg+Y) über alle Änderungen.
- Automatische Sicherung der Tags vor jedem Speichern, Dialog „Sicherungen“ zum Wiederherstellen (byte-genau).
- Speichern im Hintergrund mit Fortschrittsbalken.

## [2.5] – 2026-10-08
### Behoben (Praxistest mit 1'493 Dateien)
- Unsichtbare BOM-Zeichen in Mehrfachwerten werden entfernt.
- Eingebettete DJ-Daten (GEOB: Serato, Mixed In Key, PlatinumNotes) werden nach Beschreibung zugeordnet und lesbar angezeigt.
- Beteiligte Personen (TIPL) als „Rolle: Name“.
### Geändert
- Analyse-/DJ-Daten (beaTunes, GEOB, ETCO …) gelten standardmäßig als „unwichtig“.

## [2.4] – 2026-10-08
### Neu
- Splitter zwischen links / Befehlsspalte / rechts und zwischen Name | Wert, automatisch optimale Breiten.
- Befehlsspalte mit ◀/▶ pro Zeile; „Alles“ und „Fehlende“ nach links/rechts übernehmen.

## [2.3] – 2026-10-08
### Neu
- Tag-Fixer für Mehrfachwerte (Trennzeichen oder ID3v2.4-Standard).
- Feine Trennlinien zwischen den Zeilen.
- Leere Standardfelder (ID3v1 / v2.3 / v2.4) einblenden.

## [2.2] – 2026-10-08
### Neu
- Tooltip mit der originalen Frame-ID beim Überfahren eines Feldnamens.

## [2.1] – 2026-10-08
### Neu
- Einlesen großer Ordner mit Zählung, Fortschrittsbalken und Abbrechen.

## [2.0] – 2026-10-08
### Neu
- Oberfläche im Stil von Beyond Compare (Dunkel/Hell), alle ID3-Frames, Zeichen-Diff, Inline-Bearbeitung,
  Kontextmenü, Sammelkopie, Datei-Infos (Dauer, Bitrate).

## [1.0] – 2026-10-04
### Neu
- Erste Version: zwei Ordner oder Dateien vergleichen, Standardfelder links ↔ rechts kopieren, eigene ID3-Bibliothek ohne Zusatzpakete.
