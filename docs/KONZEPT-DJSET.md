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

- Weitere mögliche Ausbauten: weitere Exportformate (Serato-Crate, Engine DJ), Energie aus
  Audio-Analyse (#9).

### 5.1 Geplante Erweiterung: 1001Tracklists als Set-Datenquelle

**Status: TODO / geplant – NICHT implementiert.** Siehe [GitHub-Issue #180](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/180) (Label `idee`, Meilenstein «Später»).
**Quelle:** `2026_10_13_Konzept_DJSET_1001-Tracklist_abgleichen(1).pdf`, insbesondere Seiten 1, 3 und 4–5.
**Abgrenzung:** 1001Tracklists dient der Track-Discovery und Set-Planung, nicht dem Musikdownload oder Live-Mixing. Die datenbasierte Kompatibilitätsbewertung ist im [Musikanalyse-Konzept, Abschnitt 12](KONZEPT-MUSIKANALYSIEREN.md#12-geplant-set-intelligence-aus-externen-dj-tracklisten) dokumentiert.

**Geplante Funktionen:**

| Funktion | Nutzen | Priorität laut Ausgangskonzept |
|---|---|---|
| Tracklisten importieren | Bekannte DJ-Sets als externe Planungsgrundlage übernehmen | Hoch |
| Track Discovery | Neue Titel aus Sets bekannter DJs entdecken | Hoch |
| Library Matching | Eigene Tracks als vorhanden/fehlend/ungeklärt erkennen | Hoch |
| Track-Reihenfolge | Vorgänger-/Nachfolger-Beziehungen aus Sets zugänglich machen | Hoch |
| Track-Kombinationen | Häufig gemeinsam gespielte Titel für die Set-Planung nutzen | Hoch |
| Einkaufsliste / Bezugsquellen | Fehlende Tracks zur Recherche und für Shoplinks vormerken | Hoch |
| DJ-Support | Kennzeichnen, welche DJs einen Track spielen | Mittel |
| Trends / Beliebtheit | Veränderungen der Set-Verwendung untersuchen | Mittel |
| Set-Verlauf | BPM, Camelot/Tonart und Energy im Set visualisieren, sofern Daten vorliegen | Mittel |
| Unbekannte Tracks | Nicht identifizierte IDs zur manuellen Klärung sammeln | Mittel |

**Vorgeschlagener, noch zu spezifizierender Workflow:**

1. **Phase 1 – Manueller Import und Bibliotheksabgleich (TODO):** Eine vom Nutzer bereitgestellte bzw. exportierte Trackliste erfassen; ein URL-basierter Import ist nur vorzusehen, wenn ein zulässiger Abrufweg geklärt ist. DJ, Set, Veranstaltung, Trackposition, allfällige Zeitmarken und Quellenverweis erhalten.
2. **Normalisierung (TODO):** Artist, Titel, Mix-/Remix-Version, ISRC (falls verfügbar) und Laufzeit normalisieren. Unsichere Zuordnungen sichtbar machen und manuelle Bestätigung anbieten, damit Radio Edit und Extended Mix nicht fälschlich zusammenfallen.
3. **Library Matching (TODO):** Importierte Trackeinträge mit vorhandenen Dateien vergleichen; «vorhanden», «fehlt» und «unklar» unterscheiden. Nicht automatisch Tags oder fremde DJ-Bibliotheken ändern.
4. **Discovery und Einkaufslisten (TODO):** Fehlende Titel als Such-/Einkaufskandidaten vormerken; legale Bezugsquellen nur über erlaubte Schnittstellen bzw. offizielle Shoplinks ermitteln. Siehe [Konzept DJ-Plattformen](KONZEPT-DJPLATTFORMEN.md).
5. **Phase 2 – Datenbasierte Übergangsvorschläge (TODO):** Set-Reihenfolgen, Set-Verläufe und DJ-Support zusammen mit Ergebnissen der Musikanalyse als **erklärbare Vorschläge** im DJ-Set-Planer darstellen.
6. **Phase 3 – Wiederkehrende Discovery (optional / TODO):** Neue Sets ausgewählter DJs und Trends nur bei belegtem erlaubtem automatischem Zugang prüfen.

**Schnittstelle:** Ein separat austauschbarer Tracklist-Provider liefert normalisierte Set- und Trackreferenzen an den bestehenden DJ-Set-Planer; der Player bleibt ein nichtdestruktives Vorhörwerkzeug. Der im PDF vorgeschlagene Verzeichnisbaum `dj_intelligence/` ist **eine Architekturidee**, kein bestehender Code.

**Vorbedingungen:** Das Ausgangsdokument nennt **keine allgemein dokumentierte öffentliche Entwickler-API** für 1001Tracklists. Manuelle Importe sind als erste Machbarkeitsstufe vorgesehen; Partnerschaften und im PDF erwähnte Drittanbieter-/Scraping-Lösungen (z. B. CrateDigger, 1001-tracklists-api, Parse API) müssen auf Funktion, Aktualität, Vertrags- und Nutzungsrechte geprüft werden. Technische Abrufbarkeit allein bedeutet keine Erlaubnis.

**Umsetzung:** Ausdrücklich **nicht vorhanden**. Die Details zu Speicherformat, Rechteprüfung, UI und Akzeptanztests sind offen und werden vor Programmierung über #180 konkretisiert.

## 6. Tests

`tests/test_setplan.py`, `tests/test_setexport.py`, Oberflächen-Tests in `tests/test_browser_ui.py`.

## Playlists aus Plugins (#242, Entscheid User 17.10.2026)

„Aus Lexicon …“ in der Kopfzeile (nur wenn ein bereites Plugin `playlists(ctx)` anbietet): alle Playlists holen und
mit Häkchen (eingerückt nach Ordnern, Filter über den Pfad) wählen. Jede gewählte Playlist wird als gespeicherte Liste
„<Quelle>: <Name>“ abgelegt (gleichnamige werden aktualisiert, Reihenfolge wie in der Quelle), die erste geladen und
ihre Titel in den Tagger eingelesen. Titel, die nicht auf diesem Rechner sind, werden gezählt und gemeldet.
Lexicon liefert zusätzlich die Pseudo-Playlist „Warteschlange“ (läuft gerade + nächste).
