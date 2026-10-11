# Konzept: Vergleich

Stand: 2026-10-11 (4.4.0-beta.4) · Status: **umgesetzt** (Kernfunktion seit 1.x „MP3 Tag Compare“) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am Vergleich
> weitergearbeitet, ist es im selben Zug anzupassen (Funktionen, Umsetzung, Entscheide, Offen).

## 1. Ziel

Zwei Ordner, Dateien oder einen Snapshot und die echten Dateien Feld für Feld vergleichen (im Stil von Beyond
Compare) und Werte gezielt von einer Seite auf die andere übernehmen, z. B. nach einer Analyse durch ein anderes
Programm oder zwischen Original und bearbeiteter Kopie.

## 2. Funktionen

- **Laden:** Pfade links/rechts mit Verlauf und Standardordnern (⌂), Unterordner, Snapshot als Seite (📷,
  schreibgeschützt), „Paar neu einlesen“ (Shift+F5).
- **Zuordnung** (`PAIR_MODES`): Dateiname · Disc + Spurnummer · Titel · Reihenfolge · Audio-Inhalt (findet umbenannte
  und verschobene Titel).
- **Paarliste:** Status ≠ / ≈ (nur unwichtige Unterschiede) / = / ◧ ◨ (nur eine Seite), Suche in Namen und Werten,
  erweiterter Filter nach Feld/Bedingung/Seite, Herkunfts-Filter, Mehrfachauswahl, **Sammelkopie**.
- **Tabelle:** zeichengenaue Markierung der Unterschiede, Pfeile je Feld, Alles/Fehlende nach links/rechts, Bearbeiten
  per Doppelklick (Mehrfachwerte mit `¦`), Kontextmenü, Links, Cover mit Grossansicht und Bild-Aktionen, XML- und
  Binärfeld-Editor, Filter Alle/Unterschiede/Gleiche, unwichtige und leere Felder, + Feld, Felder einer Herkunft
  entfernen.
- **Unwichtige Felder** (`DEFAULT_TRIVIAL`, eigene Liste in den Einstellungen): Felder, die sich fast immer
  unterscheiden (TLEN, TSSE, GEOB …), werden als „≈“ gewertet und hinterlegt.
- **Player A/B:** L/R wechselt zwischen linker und rechter Datei an derselben Stelle.
- Vergleich und Tagger teilen dieselben Dateien, Undo und Speichern.

## 3. Umsetzung

- **Kern:** `compare.py` (`scan`, `pair_files`, `audio_key_of`, `diff`, `copy_tags`, `Rules`), `core.py`
  (`load_pairs`, Filter, Anzeige), `snapshots.py` (Snapshot als Quelle).
- **Session:** `start_load`, `reload_pair`, `pair_rows`, `filter_pairs`, `view`, `copy_keys`/`copy_all`/
  `copy_missing`, `set_value`, `remove`, `bulk_*`, `compare_origin_remove`, `cover_*`, `cmp_blob*`, `revert_pair`.
- **Oberfläche:** `web/app.js` (Paarliste, Tabelle), `web/xmleditor.js`.
- **Einstellungen:** `hist_left`, `hist_right`, `default_left`, `default_right`, `cmp_defaults` (Unterordner, Zuordnung,
  Anzeige, Unwichtige, Leere, Cover), `mode`, `recursive`, `filter`, `show_trivial`, `empty_set`, `show_covers`,
  `trivial`.

## 4. Entscheide

- Snapshot-Seiten sind schreibgeschützt; Werte gehen nur Richtung echte Dateien.
- Die klassische Oberfläche (tkinter) behält ihren Vergleich, wird aber nicht mehr erweitert (#106).

## 5. Offen / Ideen

- #107 Werkzeugleiste mit Symbolen wie in der klassischen Oberfläche (Meilenstein „Später“).

## 6. Tests

`tests/test_compare_backup.py`, `test_core_session.py`, `test_listcache.py` (Paar neu einlesen), `test_snapshots.py`
(Snapshot im Vergleich), `test_origins.py`, Oberflächen-Tests in `tests/test_browser_ui.py`.
