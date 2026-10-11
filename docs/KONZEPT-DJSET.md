# Konzept: DJ-Set

Stand: 2026-10-11 (4.4.0-beta.4) · Status: **umgesetzt in 4.0.0**, erweitert in 4.2.0 (Listen, Warteschlange) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am DJ-Set
> weitergearbeitet, ist es im selben Zug anzupassen (Funktionen, Umsetzung, Entscheide, Offen).

## 1. Ziel

Titel so ordnen, dass die Übergänge harmonisch (Camelot), im Tempo (BPM) und im Energieverlauf passen – automatisch
optimiert, von Hand anpassbar und als Playlist für DJ-Programme exportierbar. Eigene Python-Umsetzung der Idee von
„harmonic-flow“ (dessen Code ohne Lizenz ist und nicht übernommen wurde).

## 2. Funktionen

- **Titel holen:** markierte Titel oder ganzer Ordner aus dem Tagger, Rechtsklick „Zum DJ-Set hinzufügen“.
- **Optionen:** Energieverlauf (egal, steigend, fallend, Welle), Gewichtung Tonart/BPM/Energie, maximaler BPM-Sprung
  in Prozent, Titel ohne Tonart/BPM ans Ende oder neutral.
- **Optimieren:** bis 15 Titel exakt (Held-Karp), darüber Greedy + Verbesserung (2-opt/Tausch) mit Zeitlimit;
  „⇄ Vorher/Nachher“, „Rest optimieren“ mit gesperrten Titeln (🔒).
- **Bewertung je Übergang:** Ampel, Art des Tonartwechsels (gleich, ±1, parallel, Energie-Sprung, Sprung), BPM-Abstand
  mit Halb-/Doppeltempo, Note 0–100; Gesamtnote mit 20 % Nähe zur Soll-Kurve; fehlende Energie aus BPM geschätzt.
- **Ansicht:** Weg durch das Camelot-Rad, Kurven für Energie, Soll und BPM.
- **Bedienung:** Ziehen, Tasten (↑/↓, Alt+↑/↓, G, Entf, Enter), Player folgt der Set-Reihenfolge, Ziehen auf Player A/B.
- **Listen:** Sets speichern, laden, umbenennen, löschen. Die **Warteschlange** des Players (`pq_*`) lässt sich
  ins Set übernehmen.
- **Export:** M3U8 (absolute/relative Pfade), Rekordbox-XML, CSV mit Übergangsbewertung, Spurnummern in
  Set-Reihenfolge schreiben (Vorschau, Undo).

## 3. Umsetzung

- **Kern:** `setplan.py` (`Track`, `Options`, `key_kind`, `bpm_step`, `transition`, `evaluate`, `optimize`,
  `EXACT_MAX = 15`, `PROFILES`), `setexport.py` (`m3u8`, `rekordbox_xml`, `read_rekordbox`, `csv_rows`, `write`).
- **Session:** `session_djset.py` (`DjSetMixin`: `dj_*`, `pq_*`, `dj_export_file`).
- **Oberfläche:** `web/djset.js`, `web/queue.js`.
- **Einstellungen:** `djset_items`, `djset_opts`, `djset_saved`.

## 4. Entscheide

- Exakte Optimierung nur bis 15 Titel (Laufzeit); darüber Näherung, meist < 2 % vom Optimum.
- Titel aus nicht geladenen Ordnern bleiben im Set (grau), bis ihr Ordner wieder geladen ist.

## 5. Offen / Ideen

- Keine offenen Issues. Mögliche Ausbauten: weitere Exportformate (Serato-Crate, Engine DJ), Energie aus
  Audio-Analyse (#9).

## 6. Tests

`tests/test_setplan.py`, `tests/test_setexport.py`, Oberflächen-Tests in `tests/test_browser_ui.py`.
