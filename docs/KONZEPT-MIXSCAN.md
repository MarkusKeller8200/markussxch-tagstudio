# Konzept: Mix analysieren – Titel in DJ-Mixes erkennen (#261) und MixID (#218)

Stand: 2026-10-27 (Meilenstein #30 „4.13.0“) · Status: **Entscheide freigegeben (27.10.2026, 03:45)** – Phase 2 (Prototyp) umgesetzt, Messung beim User offen.

> Was es schon gibt und was geplant ist, ist je Abschnitt markiert. Umgesetzt wird erst nach Freigabe der Entscheide in
> Abschnitt 8. Grundsatz aus #260 (Entscheid User 24.10.2026): **nur lokale Ausführung**, kein eigener Server.

## 1. Ziel

Aus einer **eigenen Mix-Datei** (Aufnahme eines DJ-Sets, eigener Mix, Radiosendung) eine **Tracklist mit Startzeiten**
gewinnen: welche Titel der eigenen Bibliothek laufen wann, mit welcher Tempo-Abweichung und wie sicher. Ergebnis als
Playlist (verknüpfte Dateien), CUE-Datei, Text (Format wie 1001Tracklists) oder Wunschliste (#186) für Lücken.

**Nichtziele:** keine Erkennung fremder Titel über einen Online-Dienst ohne ausdrückliche Wahl (siehe M3), kein
Herunterladen von YouTube/SoundCloud/Mixcloud, kein Mixen, kein eigener Server.

## 2. Ausgangslage (umgesetzt)

- **AcoustID/Chromaprint** (Plugin `acoustid`) erkennt ganze Titel ohne Tempoänderung – für Mixe ungeeignet.
- **SonoVault Identify** (#257, Plugin `sonovault`) erkennt einen Ausschnitt online, kostenpflichtig, lädt Audio hoch.
- **Analyse-Plugins mit eigener Umgebung** (Stems, Tonart/OpenKeyScan): `plugin.json › env` + `worker.py`, Installation
  über die Plugin-Seite – das neue Plugin folgt diesem Muster; am Installer (`packaging/`) ändert sich nichts.
- **Playlists** kennen Einträge ohne Datei, Import aus Text (#279) und Einkaufsliste; **Ideen** (#186) Wunschlisten.
- **MixID** (#218): keine öffentliche API bekannt (geprüft 16.10. und 27.10.2026); Anfrage an Rekordcloud als Entwurf im
  Issue, **noch nicht gesendet**.

## 3. Verfahren (Audio-Fingerabdruck)

Shazam-artig: im Spektrogramm die markanten Spitzen (Frequenz, Zeit) finden, Paare/Gruppen davon zu Schlüsseln
(„Hashes“) verdichten und im Index ablegen; ein Ausschnitt des Mixes wird gleich zerlegt und gegen den Index gezählt.
Ein Treffer = viele Schlüssel desselben Titels mit gleichem zeitlichen Versatz.

**Problem im Mix:** DJs ändern das Tempo (typisch ±0–8 %), meist **mit Keylock** (Tonhöhe bleibt, nur die Zeit wird
gedehnt), seltener ohne (Tempo und Tonhöhe ändern sich gemeinsam, wie bei Vinyl). Dazu Übergänge (zwei Titel
gleichzeitig), EQ, Effekte. Klassische Landmark-Verfahren (audfprint, dejavu) verkraften nur ~±5 %.

| Kandidat | Robust gegen Tempo/Tonhöhe | Lizenz | Bewertung |
|---|---|---|---|
| **A – eigene Umsetzung, Index einfach, Abfrage gerastert** | ja, durch Abfrage in Stufen (z. B. −10 … +10 % in 1-%-Schritten; mit Keylock nur die Zeitachse, ohne zusätzlich die Frequenz skaliert) | eigener Code (GPL wie TagStudio) | **empfohlen**: kleiner Index, Python/NumPy, volle Kontrolle; Abfrage kostet je Stufe Zeit |
| B – eigene Umsetzung „Quad“ (Sonnleitner & Widmer 2016) | ja, Schlüssel sind von Haus aus skalierungsfest | eigener Code nach Veröffentlichung | Ausweichweg, falls A im Prototyp nicht reicht; aufwändiger |
| C – Panako (Joren Six) als getrenntes Werkzeug | ja, dafür gebaut | **AGPL-3.0**, Java 11 + LMDB | nur als vom Benutzer separat installiertes Programm; schwere Abhängigkeit |
| audfprint / dejavu | nein (≈±5 %) | MIT | zu wenig tempo-robust |
| qfp (Python, Quad) | ja | Lizenz unklar, seit 2022 unverändert, Python < 3.11 | nicht verwenden |

**Patente:** Das Shazam-Patent zur tempo-/tonhöhenfesten Zuordnung (US 7 627 477) ist laut Google Patents abgelaufen
(voraussichtlich 31.03.2025). Das ist keine Rechtsberatung; vor einer Veröffentlichung nochmals prüfen (ZU PRÜFEN).

## 4. Bausteine (geplant)

### 4.1 Plugin „Mix analysieren“ (`plugins/mixscan`, Kategorie Audio)

- Eigene Umgebung wie Tonart: `numpy`, `scipy`, `av` (Dekodieren aller FFmpeg-Formate). Kein PyTorch, klein (~100 MB).
- `worker.py` rechnet in der Umgebung (Index aufbauen, Mix abfragen); `plugin.py` stellt Aktionen und Fortschritt bereit.

### 4.2 Index der eigenen Bibliothek

- SQLite im Benutzerordner (`~/TagStudio/Mixscan/index.db`, je Profil), Tabellen Titel (Pfad, Grösse, Änderungszeit,
  Dauer) und Schlüssel (Hash → Titel, Zeit). Nur Verweise auf die Dateien, keine Audiokopien.
- Quelle: alle aktiven Bibliotheken (`folders.libraries()`); nur neue/geänderte Dateien werden nachgeführt,
  verschwundene entfernt.
- Aufbau im Hintergrund (abbrechbar, fortsetzbar). Grobe Erwartung je 10 000 Titel: einige hundert MB, einige Stunden
  beim ersten Mal (im Prototyp messen, M6).

### 4.3 Mix analysieren

- Eingabe: lokale Datei (MP3, WAV, FLAC, M4A/AAC, AIFF, OGG – alles, was FFmpeg liest). Kein Herunterladen aus dem Netz.
- Fenster von 10–15 s alle 5 s, je Fenster Abfrage in Tempo-Stufen; Treffer über die Zeit glätten → Abschnitte
  „Titel X von 12:30 bis 16:10, +3,2 %, Sicherheit 94 %“; zu kurze oder schwache Treffer → „unbekannt“.
- Übergänge: zwei Titel dürfen sich überlappen (Ein- und Ausblenden).

### 4.4 Ergebnis (Seite bzw. Dialog „Mix analysieren“)

- Liste mit Startzeit, Titel (verknüpft), Tempo-Abweichung, Sicherheit; Vorhören an der Stelle im Mix und im Titel;
  Treffer korrigieren (anderen Titel wählen) oder verwerfen; Lücken mit Notiz („ID – ID“).
- Speichern als **Playlist** (Ordner „Mixe“, Startzeit als Notiz je Eintrag), **CUE-Datei** neben dem Mix,
  **Text** (`[00:00] Künstler - Titel`), Lücken optional als Einträge einer **Wunschliste** (#186).
- Ergebnisse je Mix im Benutzerordner (`~/TagStudio/Mixscan/mixe/<id>.json`), erneut öffnen ohne neue Analyse.

### 4.5 Unbekannte Abschnitte (optional, siehe M3)

- Nur auf Klick je Abschnitt: kurzer Ausschnitt an **SonoVault Identify** (#257, kostenpflichtig, lädt Audio hoch, mit
  dem bestehenden Kosten- und Datenschutzhinweis). Standard: aus.

## 5. MixID (#218)

- Ohne offizielle API keine Integration (kein Scraping, keine undokumentierten Endpunkte).
- Nächster Schritt liegt beim User: Anfrage aus #218 an Rekordcloud senden (oder nicht). Bis zur Antwort bleibt #218
  vorgemerkt und gehört **nicht** in ein Release.
- Mit API wären möglich: Tracklist eines veröffentlichten Sets importieren (wie #180), „gespielt in N Sets“,
  Vorschläge aus Sets gefolgter DJs in „Entdecken“.

## 6. Rechte, Datenschutz, Nutzungsbedingungen

- Alles läuft lokal; Index und Ergebnisse bleiben im Benutzerordner; keine Daten an Dritte (ausser M3 auf Klick).
- Nur eigene Dateien bzw. Aufnahmen, die man verwenden darf; keine Download-Funktion für Streaming-Plattformen.
- Drittkomponenten (NumPy BSD, SciPy BSD, PyAV BSD/FFmpeg LGPL) in `docs/third-party.json`.

## 7. Tests (geplant)

Unit: Schlüssel bilden, Index nachführen (neu/geändert/gelöscht), Abfrage mit synthetisch gedehnten Ausschnitten
(±8 % mit und ohne Tonhöhe), Glättung zu Abschnitten, Export CUE/Text/Playlist. Oberfläche: Dialog/Seite, Index-Status,
Ergebnis speichern. Prototyp-Messung mit echter Musik beim User (M6).

## 8. Entscheide (User 27.10.2026, 03:45)

| Nr. | Frage | Entscheid |
|---|---|---|
| M1 | Verfahren | **A** – eigene Umsetzung, Abfrage in Tempo-Stufen; B (Quad) nur, falls der Prototyp nicht reicht |
| M2 | Welche Titel werden erkannt? | nur Titel der **eigenen Bibliothek** (alle aktiven Bibliotheken) |
| M3 | Unbekannte Abschnitte | vorerst „unbekannt“ lassen; SonoVault Identify je Abschnitt auf Klick als Option später |
| M4 | Eingabe | Vorschlag: nur **lokale Dateien** – in der Rückfrage nicht angekreuzt, **noch zu bestätigen**; der Prototyp liest nur lokale Dateien |
| M5 | Index aufbauen | von Hand starten, danach automatisch für neue Titel (nach „Vorbereiten“ und beim Start im Hintergrund) |
| M6 | Prototyp zuerst | ja: Messwerkzeug, das du mit ~200 Titeln und einem eigenen Mix mit bekannter Tracklist laufen lässt; weiter erst bei ≥ 80 % erkannten Titeln |
| M7 | Ergebnis und Ort | Plugin-Aktion „Mix analysieren …“ (Playlists und Plugin-Seite) mit Ergebnisfenster; speichern als Playlist (Ordner „Mixe“), CUE, Text |
| M8 | MixID (#218) | Anfrage an Rekordcloud senden (durch den User); #218 bis zur Antwort aus 4.13.0 genommen (Sammlung „Funktionen“) |

## 9. Phasen

1. **Konzept** (dieses Dokument) – M1–M3, M5–M8 freigegeben; M4 zu bestätigen.
2. **Prototyp** (M6): Plugin mit Index + Analyse ohne Oberfläche, Messbericht (Trefferquote, Speicher, Zeit).
3. **Plugin** mit Ergebnisfenster, Export, automatischem Nachführen.
4. Optional: SonoVault für Lücken (M3), MixID (M8, nur mit API).

## 10. Prototyp (umgesetzt, 4.13.0)

- Plugin `plugins/mixscan` 0.1: `fp.py` (Verfahren A), `worker.py` (Umgebung), `plugin.py` (Aktionen
  „Bibliothek indexieren (Test) …“ und „Mix analysieren (Test) …“, Messbericht in `Plugin-Daten/mixscan/berichte`).
- Parameter: 11 025 Hz mono, FFT 1024 / Sprung 256 (23 ms), ≤ 18 Spitzen je Sekunde, 6 Partner je Anker, Schlüssel
  `f1 | f2−f1 | dt` (32 Bit). Abfrage in 21 Tempo-Stufen (0,90–1,10) mit Keylock und 20 ohne; Werte nahe an der
  Rundungsgrenze fragen beide Nachbarn ab. Auswertung je 5-s-Block; Glättung über 5 Blöcke nur bei passendem Versatz
  (je Block die 3 besten Versätze – Musik wiederholt sich); Schwelle 70 Treffer, Abstand 1,4 zum Zweiten;
  Abschnitte desselben Titels mit ≤ 20 s Unterbrechung zusammengefasst; Sicherheit < 60 % = „unsicher“.
- **Synthetische Messung** (40 erzeugte Titel, Mix 3:18 min, 6 Titel, Tempo −6 … +8 %, 2 ohne Keylock, Rauschen und EQ,
  MP3): 6/6 erkannt, Tempo auf ±1 % genau; Mix aus 4 unbekannten Titeln: nichts mit ≥ 60 % gemeldet. Abfrage ≈ 1 s je
  Minute Mix. Index ≈ 100 Schlüssel/s ≈ 1,2 MB je Minute Audio (≈ 440 MB je 1000 Titel à 6 min) – im echten Test messen;
  falls zu gross: Dichte senken oder Index stückweise (Speicherabbild) laden.
- Startzeiten auf 5 s genau (Blockraster); im Übergang zählt noch der alte Titel. Verfeinerung in Phase 3.
- Test: `tests/test_mixscan.py`, Workflow „Mix-Analyse-Test“ (Windows, macOS; synthetische Titel, keine echte Musik).

### 10.1 Messungen mit echter Musik (User, 27.10.2026)

| Nr. | Plugin | Mix / Index | Ergebnis | Folge |
|---|---|---|---|---|
| 1 | 0.1 | Purified 531, Mix im indexierten Ordner | Mix erkennt sich selbst | 0.2: Mix-Datei wird ausgeschlossen |
| 2–3 | 0.2 | 531 / 530 (YouTube), wenige Titel | Titel nicht im Index → nichts erkannt | 0.3: „knapp verpasst“-Liste, Selbsttest |
| 4 | 0.4 | 531, 1610 Titel (≈ 658 MB) | Titel zerstückelt, andere Fassung als Treffer, kurze Fehltreffer ohne Keylock | 0.5: Zusammenfassen, Fassungsvergleich, Abschlag |
| 5 | 0.5 | 520 | „NTO (FR)“, „Remix, Extended“ nicht zugeordnet | 0.6 Abgleich toleranter; 0.7 Version im Bericht |
| 6 | 0.8 | 520 | Titelanfang 23–64 s vor Tracklist-Zeit (Median 48 s, DJ-Intro 16/32 Takte); Evenfall (+2,5 %) fehlt | 0.9: Konsistenz über den Titelanfang; „feat.“-Fehler behoben |
| 7 | 0.9 | 520 | 10/13 sicher, Evenfall mit 58 % gefunden, aber als „nicht erkannt“ gezählt; Zeiten 10/10 im Übergang | 0.10: unsichere Abschnitte zählen, wenn sie zur Tracklist passen („erkannt (unsicher)“) – 11/13 |

Die zwei übrigen Titel („More Than I Should Know“, „DJ Paulus – Mirage“) liegen nach dem Bericht nicht im Index.
