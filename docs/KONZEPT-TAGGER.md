# Konzept: Tagger

Stand: 2026-10-11 (4.4.0-beta.4) · Status: **umgesetzt** (seit 3.0, laufend erweitert) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am Tagger
> weitergearbeitet, ist es im selben Zug anzupassen (Funktionen, Umsetzung, Entscheide, Offen).

## 1. Ziel

Viele MP3-Dateien gemeinsam ansehen und bearbeiten – schnell bei grossen Bibliotheken, sicher (Vorschau, Rückgängig,
Sicherung vor dem Speichern) und mit Blick auf DJ-Daten (Tonart, BPM, Audio-Merkmale, Cues, Herkunft der Felder).

## 2. Funktionen

| Bereich | Inhalt |
|---|---|
| Liste | Ordner/Datei einlesen (mit Unterordnern), Spalten wählbar (Standardfelder, Merkmale, beliebiges Feld wie `TXXX:LABEL`), Reihenfolge per Ziehen, Sortierung in bis zu drei Stufen, Filter mit Text und Zahlenfiltern (`energy>=70`, `bpm:120-128`), Cover-Spalte, Stems als aufklappbare Spuren |
| Bearbeiten | Standardfelder der Markierung („‹verschieden›“ bleibt unverändert), Cover, ID3-Version, Bewertung/Like, Links, Audio-Merkmale (0–100, Skala 0–10 für Lexicon), Stimmung |
| Weitere Felder | alle übrigen Frames mit Herkunfts-Kennzeichen; Editoren: Feld-Editor (mehrzeilig, Einzelwerte), JSON-Baum (Expertenmodus), XML-Editor, Binärfeld-Editor (GEOB/PRIV), Farbwähler |
| Tonart | Camelot-Rad, Schreibweise Camelot `08A` / musikalisch / Open Key, „Schreibweise vereinheitlichen“ |
| Werkzeuge | Tags aus Dateiname, Umbenennen, Spurnummern, Gross-/Kleinschreibung, Suchen & Ersetzen, Cover aus Ordner, Export Excel/CSV, Feld hinzufügen, Felder nach Herkunft entfernen, Tag-Rezepte (#111), Aussortieren (#173) |
| Plugins | Aktionen der Plugins auf die Markierung, Vorschläge als Vorschau mit Häkchen |
| Start | zuletzt geladener Ordner, Standardordner oder nichts; Markierung, Sortierung, Filter und Bildlauf werden wiederhergestellt |

Alle Werkzeuge zeigen zuerst eine **Vorschau** und laufen über den gemeinsamen **Undo-Stapel**. Geschrieben wird erst mit
„Speichern“ (Strg/Cmd+S) – mit Sicherung und Konfliktschutz (fremde Änderungen seit dem Einlesen).

## 3. Umsetzung

- **Kern:** `tagger.py` (Felder, Muster, Umbenennen, Nummern, Schreibweise, Ersetzen, Cover, Export), `keys.py`,
  `features.py`, `moods.py`, `ratings.py`, `recipes.py`, `blobs.py`, `xmltools.py`, `origins.py`, `stemsview.py`,
  `archive.py`; Laden über `core.py` mit gemeinsamem Dateiregister (Tagger und Vergleich teilen die `MP3File`-Objekte)
  und Listen-Cache `listcache.py` (Hintergrund-Prüfung per Tag-Hash).
- **Session:** `tag_*`-Methoden in `session.py` (`start_tag_load`, `tag_rows`, `tag_detail`, `tag_set`, `tag_case`,
  `tag_replace`, `tag_recipe`, `tag_key_*`, `tag_feature_set`, `tag_export_file` …); Werkzeuge mit `apply=False` liefern
  die Vorschau, `_apply_plan` wendet mit Undo an.
- **Oberfläche:** `web/tagger.js`, `web/keywheel.js`, `web/features.js`, `web/jsontree.js`, `web/xmleditor.js`,
  `web/recipes.js`.
- **Einstellungen:** `default_tagger`, `hist_tagger`, `tagger_recursive`, `tagger_stems_flat`, `tagger_state`,
  `tg_defaults`, `tagger_patterns`, `key_notation`, `feat_scale`, `mood_list`, `recipes`, `list_cache`.

## 4. Entscheide

- Tagger **nur in der Web-Oberfläche** (klassische tkinter-Oberfläche eingefroren, #106).
- Camelot wird immer zweistellig geschrieben (`01A`); intern bleiben Codes wie `8A`.
- Änderungen an DJ-Daten (Serato, Mixed In Key) nur so weit, wie sie verlustfrei zurückgeschrieben werden können.

## 5. Offen / Ideen

- #111 Wortliste der Tag-Rezepte („Dj, Feat, Mc, Vs“) – Frage an den User offen.
- WAV-Unterstützung: [KONZEPT-WAV.md](KONZEPT-WAV.md) (#156).

## 6. Tests

`tests/test_tagger.py`, `test_tagger_tools.py`, `test_keys.py`, `test_features.py`, `test_moods.py`, `test_recipes.py`, `test_blobs.py`, `test_ratings.py`,
`test_listcache.py`, `test_archive.py` sowie Oberflächen-Tests in `tests/test_browser_ui.py`.
