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
| Werkzeuge | Tags aus Dateiname, Umbenennen, Spurnummern, Gross-/Kleinschreibung, Suchen & Ersetzen, Cover aus Ordner, Export Excel/CSV, Feld hinzufügen, Felder nach Herkunft entfernen, Tag-Rezepte (#111), Aussortieren (#173), Playlist ▾: zur Playlist hinzufügen (Strg+Shift+P = zuletzt benutzte), Playlist öffnen, Filter „Nur Titel aus einer Playlist“ (#268, [KONZEPT-PLAYLISTS.md](KONZEPT-PLAYLISTS.md)) |
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
- Tag-Rezept „Beatport-Download aufbereiten“: Wortliste `Dj, Feat, Mc, Vs` ist so gewollt (Entscheid User 2026-10-12, #111).
- Camelot wird immer zweistellig geschrieben (`01A`); intern bleiben Codes wie `8A`.
- Änderungen an DJ-Daten (Serato, Mixed In Key) nur so weit, wie sie verlustfrei zurückgeschrieben werden können.

## 5. Offen / Ideen

- WAV-Unterstützung: [KONZEPT-WAV.md](KONZEPT-WAV.md) (#156).

## 5b. Filter je Spalte (#202)

Filterzeile `#tgHeadF` unter den Spaltenköpfen, gleiches Raster wie Kopf und Zeilen (`--tg-grid`), scrollt waagrecht mit.
Je sichtbare Spalte ein Feld (`TG.colQ[spalte]`), auch für Merkmal-Spalten. Text: alle Wörter müssen vorkommen
(Reihenfolge egal, ohne Gross/klein). Zahlenspalten (BPM, Länge in s, kbit/s, Bewertung, Spur, ID3, Merkmale):
`>`, `>=`, `<`, `<=`, `=` und Bereich `a-b`; Länge auch als `m:ss`. Verknüpft mit UND und mit dem Suchfeld oben.
Tasten im Feld gehen nicht an die Liste (keine Bewertung/Wiedergabe), Strg/Cmd-Kürzel schon; Esc leert, Enter/↓ zur
Liste. Ein-/ausblenden über „Filter“ (`LAYOUT.tg_colfilter`, gemerkt); Filterwerte selbst werden nicht gespeichert.

Datumsspalten „Aufgenommen“ / „Bearbeitet“ (#214, `tgDateTest`): `<30d` bzw. `30d` = jünger als, `>1y` = älter als
(Einheiten h, d/t, w, m, y/j), `heute`, `gestern`, `2026`, `2026-10`, `2026-10-16`, Bereich `2026-09-01..2026-10-16`,
`leer`/`-` = ohne Wert, `*` = mit Wert. Sortiert wird nach dem Zeitpunkt (Zeitzonen beachtet), leere Werte am Ende.

## 5c. Beatgrid-Status (#191)

Spalte „Beatgrid“ (Spalten ▾): `serato` (GEOB „Serato BeatGrid“, übernommen – nicht automatisch musikalisch geprüft),
`analyse` (eigene Audioanalyse im Wellenform-Cache: BPM + erster Schlag, konstantes Tempo), `bpm` (nur TBPM – Schätzung,
**kein** Raster), `nobeat` (analysiert, kein Schlag gefunden), `none`; „–“ = noch nicht geprüft. Modul `gridstatus.py`,
`Session.tag_grid_status(indices, fresh)` liest nur Tags und Cache (kein Dekodieren), Ergebnis je Pfad+mtime
zwischengespeichert und in `tag_rows` als `grid` mitgeliefert. Ist die Spalte sichtbar, holt `web/gridscan.js` fehlende
Werte im Hintergrund in Paketen à 150 (Chip in der Fusszeile, Klick bricht ab). Kontextmenü „Beatgrid analysieren …“
(markierte Titel ohne Serato/Analyse): dieselbe Analyse wie im Player (`plWaveCompute`), fortlaufend, abbrechbar,
Ergebnis nur im Cache – nie im MP3. Filter: in der Filterzeile eine Auswahl mit den vorkommenden Zuständen und ihrer
Anzahl (z. B. „nur BPM (12)“), Sortierung nach Güte.
**Raster im MP3 (#221):** `TXXX:TAGSTUDIO_BEATGRID` (Modul `beattag.py`), Wert z. B. `bpm=124.998; first=0.1234;
conf=0.87; src=analyse; date=2026-10-17` – nur das Raster, nicht die Wellenform. Kontextmenü „Beatgrid in Tag speichern …“
(`Session.tag_beatgrid`, Vorschau → Übernehmen mit Rückgängig, gespeichert wie üblich); übersprungen werden Titel mit
Serato-Raster (Vorrang) und ohne Analyse, vorhandene Werte nur mit „ersetzen“. Lesen: Status `tag` („Analyse (Tag)“) vor
`analyse`; Player-Raster aus dem Tag (`from_tag`, Kennzeichnung „Audioanalyse (Tag)“), auch ohne Cache. Kein Verstoss
gegen die Schutzregel in „Vorbereiten“. Idee: Wellenform als GEOB „TagStudio Overview“ (#222, später).
**Vergleich Serato ↔ eigene Analyse (#223):** Hat ein Serato-Titel auch eine eigene Analyse (Tag oder Cache), vergleicht
`gridstatus.compare` (Python) bzw. `plGridCompare` (JS, gleiche Regeln): Tempoverhältnis 2 bzw. ½ → „halbes/doppeltes
Tempo in Serato“, Tempo-Abweichung > 0,1 % → „Tempo weicht ab“, sonst Abstand des ersten Schlags modulo Schlaglänge
> 20 ms → „erster Schlag N ms versetzt“; bei mehreren Serato-Markern nur der Anfang (Hinweis „Tempowechsel“). Codes
`serato_ok` („Serato ✓“) und `serato_diff` („Serato ≠ Analyse“), Hinweis als `grid_note` in den Zeilen bzw. `notes` von
`tag_grid_status` (Tooltip). Player: `media_extra` liefert `grid.check = {ok, note, from}`, Anzeige „Serato-Grid ✓“ /
„Serato ≠ Analyse“. Kontextmenü „Beatgrid analysieren (auch Serato, zum Vergleich) …“. Die eigene Analyse kennt nur
konstantes Tempo und keinen Taktanfang – eine Abweichung ist ein Hinweis zum Nachschauen, kein Fehlerbefund. Serato-Daten
werden nie geschrieben; „Beatgrid in Tag speichern“ überspringt Serato-Titel weiterhin.
**Serato Tempo Map (#223):** Neuere Serato-Versionen schreiben GEOB „Serato Tempo Map“ statt „Serato BeatGrid“.
`serato.tempomap` (aus Beispielen erschlossen, Big-Endian): Byte 0 = 0x02, Byte 2–3 uint16 Ankerzahl, Byte 4–11 double
Anker in Sekunden, Byte 24–31 double BPM, Byte 32–39 double Notenwert (0,25). Ergebnis wie ein BeatGrid mit einem Marker
(`first` = Anker modulo Schlaglänge, `tempo_map`, `anchor`, `partial` bei anderer Länge als 49 Bytes oder mehreren
Ankern). Ein klassisches „Serato BeatGrid“ hat Vorrang. Unklar: Bedeutung von Byte 12–23 und 40–48, Aufbau bei
Tempowechseln – weitere Beispiele nötig.
**Eigenes Raster bei Serato-Titeln (#223):** `tag_beatgrid(idx, overwrite, apply, serato=False)` – mit `serato=True`
(Häkchen „Auch Titel mit Serato-Raster (nur zum Vergleich)“) wird `TXXX:TAGSTUDIO_BEATGRID` auch bei Serato-Titeln
geschrieben. Für Player und Status bleibt Serato massgebend; das Tag-Raster ist dann die „eigene Analyse“ für den
Vergleich (`own_beat`: Tag vor Cache, `grid.check.from = "tag"`, `grid.check.own` für die Lupe). Der Player rechnet bei
solchen Titeln beim Laden keine Analyse mehr.
Offen: Qualität von `beatAnalyse()` (Taktanfang, Tempowechsel) und Vergleich Serato ↔ eigene Analyse – siehe
KONZEPT-MUSIKANALYSIEREN.

## 5a. TagStudio-Zeitstempel (#184, #185 – 4.5.0, Entscheide vom 16.10.2026)

Modul `tsmeta.py`. Eigene TXXX-Felder (in Mp3tag, Lexicon usw. sichtbar), Wert ISO 8601 mit Zeitzone, sekundengenau
(`2026-10-16T01:55:00+02:00`); im Tagger als Spalten „Aufgenommen“ / „Bearbeitet“ (Anzeige `16.10.2026 01:55`).

| Feld | Bedeutung | Gesetzt | Nie |
|---|---|---|---|
| `TXXX:TAGSTUDIO_EDITED` „Letzte Bearbeitung“ | letztes erfolgreiches Speichern **geänderter** Tags durch TagStudio | `core.save_files` (vor `f.save()`) und Speicherstellen in „Vorbereiten“; Rückgängig + Speichern = neue Zeit; cfg `stamp_edited` | Anzeigen, Einlesen, Vorhören, Speichern ohne Änderung |
| `TXXX:TAGSTUDIO_ADDED` „In Bibliothek aufgenommen“ | erste Übernahme in die Bibliothek | Übernahme-Schritt in „Vorbereiten“ (`session_prepare`, cfg `stamp_added`); Nachtragen von Hand | automatisch überschreiben; Dateidatum (mtime/ctime) |

**Nachtragen** (Tagger › „Aufnahmedatum nachtragen …“, `Session.tag_added(idx, mode, value, overwrite, apply)`):
Vorschlag aus dem frühesten Snapshot, der den Titel enthält (`snapshots.first_seen`: Audio-Schlüssel, sonst relativer
Pfad – überlebt Umbenennen/Verschieben), sonst Ersatzdatum von Hand; Modus „date“ setzt ein Datum für alle. Vorschau mit
Quelle je Titel, Übernehmen mit Rückgängig, geschrieben wird beim normalen Speichern. Vorhandene Werte nur mit
„überschreiben“.

`TXXX:TAGSTUDIO_EDITED` steht in den Standard-„unwichtigen Feldern“ (Vergleich, Journal), damit es nicht nach jedem
Speichern als Unterschied auffällt.

## 6. Tests

`tests/test_tagger.py`, `test_tagger_tools.py`, `test_keys.py`, `test_features.py`, `test_moods.py`, `test_recipes.py`, `test_blobs.py`, `test_ratings.py`,
`test_listcache.py`, `test_archive.py`, `test_tsmeta.py` sowie Oberflächen-Tests in `tests/test_browser_ui.py`.

## Ergänzungen 24.10.2026 (#275, #276)

- **„↺ Filter“** (`tgResetFilters`) neben „↺ Sortierung“, sichtbar bei aktiver Suche, Spaltenfilter, Feld-Filter
  (Hilfe) oder Playlist-Filter: hebt alle auf.
- **Nur Titel einer Playlist geladen** (`start_tag_load_files` mit Bezeichnung, `TG.list`): Hinweis-Chip `#tgListChip`
  mit „Ganzen Ordner laden“ (lädt den vorher geladenen Ordner, sonst den gemeinsamen Ordner); „↺ Filter“ lädt dann
  ebenfalls den Ordner.
- **Stems:** ein Umschalt-Knopf `#tgStemToggle` (aufgeklappt → alle zu, sonst alle auf, `aria-pressed`).
