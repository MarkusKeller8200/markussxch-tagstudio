# Changelog – MarKusSXCH TagStudio

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/). Versionen bis 2.8 hießen „MP3 Tag Compare“.

## [3.0] – in Arbeit (Zweig `web-ui`)
### Neu
- **Neue Oberfläche** (`tagstudio_web.py`, Ordner `web/`): modernes Design mit Seitenleiste, Hell/Dunkel,
  Paarliste mit Status-Filtern und Suche, Vergleich mit zeichengenauen Markierungen, Pfeil-Knöpfen,
  Bearbeiten per Doppelklick, Kontextmenü, Cover-Vorschau, Rückgängig/Wiederholen, Speichern mit Sicherung.
  Läuft im eigenen App-Fenster (pywebview) oder – ohne pywebview – im Browser.
  Start: `start_web_windows.bat` / `start_web_mac.command`.
- Splitter für Seitenleiste (einklappbar), Paarliste und Tabellenspalten; Layout wird gemerkt.
- **XML-Editor** für Felder mit XML-Inhalt (Baum- und Quelltextansicht, Prüfung mit Fehlerstelle, Formatieren/Kompakt);
  auch in der klassischen Oberfläche. XML in Binärfeldern (GEOB/PRIV) lässt sich ansehen.
- Knopf „Nach Update suchen“: prüft beim Start auf neue Versionen, lädt sie per Klick und startet neu.
- Gemeinsamer Kern `core.py` (Anzeige-Logik, Filter, Laden, Speichern) und `session.py`; beide Oberflächen
  nutzen dieselbe Logik und dieselben Einstellungen.
### Geändert
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
