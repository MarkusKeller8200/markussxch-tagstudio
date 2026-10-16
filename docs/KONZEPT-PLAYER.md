# Konzept: Player (Vorschau-Player und externe Player)

Stand: 2026-10-15 (4.4.1-beta.6) · Status: **umgesetzt** (3.2.0, ausgebaut 3.4.0, 4.1.0, 4.2.0) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am Player
> weitergearbeitet, ist es im selben Zug anzupassen (Funktionen, Umsetzung, Entscheide, Offen).

## 1. Ziel

Titel direkt in TagStudio vorhören – schnell durch viele Titel, mit DJ-Informationen (Wellenform, Cues, Beatgrid,
Tonart, BPM), Bewertung beim Hören und Übergängen wie im DJ-Programm. Externe Player für alles Weitere.

## 2. Funktionen

| Bereich | Inhalt |
|---|---|
| Wiedergabe | Leertaste/▶/Doppelklick, ⏮/⏭, folgt ↑/↓ und spielt am Ende den nächsten, Live-Vorschau (Klick spielt), Startpunkt (Start, 30 %, 1:00, erster Cue), ←/→ vier Beats, Shift+←/→ Cue-Sprünge, stumm (M) |
| Anzeige | Wellenform (einmal berechnet, Cache), Cue- und Loop-Marken (Serato, Mixed In Key), Beatgrid-Raster, Tonart in drei Schreibweisen, BPM, Lauf-/Restzeit (rot blinkend in den letzten 30 s) |
| Tempo | Klick auf BPM → Tempo von Hand (50–200 %, Tonhöhe nach Einstellung), Reset = Original; nur für den laufenden Titel (#174) |
| Tagger | Knopf „Im Tagger zeigen“ neben dem Titel: wechselt zum Tagger, markiert den laufenden Titel, hebt Filter auf, lädt bei Bedarf dessen Ordner (#175) |
| Steuerung | Taktweise springen (←/→), nächster/voriger Cue (Shift+←/→, rückwärts mit 4-Takt-Toleranz), Loop als Schleife, Titel wiederholen (R), A–B-Schleife (L), Stem-Spur wechseln (S) an derselben Stelle, A/B im Vergleich (L/R) |
| Bewertung | Sterne 0–5 (POPM, `TXXX:FMPS_Rating`) und Like (`TXXX:TAGSTUDIO`), mit Undo |
| Überblenden | 0 = aus, 1–30 s in 1-s-Schritten, gleiche Leistung, früh überblenden zum Durchhören, Tempo angleichen (±10 %, Rückkehr einstellbar), im Takt / auf Taktgrenze, Tonhöhe beibehalten |
| Player B | zweiter, gleich aufgebauter Player (nur mit „Player oben“), eigenes Ausgabegerät, Sync zu A, Ziel A/B per Klick/Taste B, Titel per Ziehen laden |
| Layout | unten in der Fusszeile oder oben mit voller Breite (einklappbar, Shift+P), abdocken in ein eigenes Fenster (zweiter Bildschirm) |
| Fortsetzen | zuletzt gehörter Titel (A und B) an derselben Stelle; nach Neustart Pause, Autoplay oder wie beim Schliessen |
| Warteschlange | „Als Nächstes spielen“ / „Zur Warteschlange“ (#138), Vorrang vor Tagger-/Set-Reihenfolge |
| Externe Player | foobar2000, VLC, Rekordbox … mit Platzhaltern `{files}` `{file}` `{folder}` `{m3u}`, Strg/Cmd+P |
| Liedtext (#215) | Knopf im Player A bzw. Menü: Fenster mit synchronisiertem Liedtext (SYLT im MP3, sonst `.lrc` daneben) – aktuelle Zeile hervorgehoben und mittig mitlaufend, Klick springt dorthin; sonst normaler Text (USLT) mit Hinweis. Stems zeigen den Text des Originals. Nur lesen (`lyricsync.py`, `media_lyrics`, `web/pllyrics.js`), Einstellung `lyrics` |

## 3. Umsetzung

- **Kern:** `media.py` (lokaler Range-Server nur auf 127.0.0.1, nur freigegebene Dateien, Token, max. 300 Dateien),
  `waveform.py` (Cache `cache/wave`), `cues.py`, `serato.py` (Beatgrid), `ratings.py`, `players.py`.
- **Session:** `session_player.py` (`PlayerMixin`: `player_prefs`, `set_player_pref`, `player_defaults`,
  `player_resume*`, `media_info`, `media_cover`, `media_extra`, `wave_save`, Bus `bus_*` für das abgedockte Fenster,
  `player_window_size`, `players`, `play_external`); `tag_set_rating`, `player_mark`, `tag_locate` (#175) in `session.py`.
- **Tempo von Hand:** `plTempoDialog`/`plTempoSet` in `web/player2.js` (setzt `playbackRate`, Kennzeichen `tempoManual`).
- **Oberfläche:** `web/player.js` (Player A, Wellenform, Analyse), `web/xfadesync.js` (Übergänge messen/nachführen, #181), `web/player2.js` (Überblenden, Player oben,
  Player B, Abdocken), `web/player-window.html` + `web/playerwin.js` (Fernanzeige), `web/queue.js`.
- **Einstellungen:** `player` (Werte aus `PLAYER_PREFS` mit Bereichen), `player_defaults`, `player_window`,
  `player_resume`, `players`.

## 4. Entscheide

- Beim Abdocken läuft die Wiedergabe weiter im Hauptfenster; das Fenster ist eine Fernanzeige (Session-Bus).
- Player B nur mit Layout „oben“.
- Beatgrid-Reihenfolge: Serato → eigene Audio-Analyse (Cache) → Schätzung aus BPM-Feld. **Nur das Serato-Raster wird aus einem Track-Tag eingelesen.** `beatAnalyse()` im Browser schätzt aus dem Kick-/Bass-Onset-Signal BPM und Offset; es ist noch keine vollständige Variable-Tempo-/Downbeat-Analyse. Ein BPM-Tag allein ist kein Beatgrid.
- **Kennzeichnung #181:** In Player A/B sowie im abgedockten Fenster wird die Rasterquelle beim Track markiert: `Serato-Grid`, `Audioanalyse`, `Nur BPM-Schätzung` oder `Kein Beatgrid`/`Beatgrid-Analyse läuft`. Bei nicht vorhandenem Serato-Grid wird die Analyse beim Laden zum Vorhören gestartet; Ergebnisse liegen im bestehenden Wellenformcache. Die Anzeige sagt nichts über eine musikalische Verifikation aus.
- **Latenzkorrektur #181 (Testfunktion, seit 4.4.1-beta.4):** Unter Einstellungen → Player sowie im ⋯-Menü von Player A kann eine signierte `xfade_latency_ms`-Korrektur zwischen −500 und +500 ms gesetzt werden (Standard 0). Positive Werte lassen den Folgetrack relativ zum aktuellen Beat **später**, negative **früher** hören. Dies erfolgt als Phasenoffset in der Mediaposition, umgerechnet nach PlaybackRate, bevor die Fade-Lautstärke geöffnet wird. Wenn die Position negativ wäre, wird um ganze Beats bzw. Takte vorwärts versetzt, um die Rasterphase zu erhalten. Nur wenn „Im Takt“ aktiv ist und beide Tracks gültige Beatgrids mit kompatiblem Tempo haben. Der Wert wird dauerhaft in den Player-Einstellungen gespeichert und gilt für **alle automatischen Übergänge**, nicht für manuelles Player-B-Sync. Das ist keine automatische Messung der Audio-Latenz; die Korrektur kann von Setup, Track, Tempo, Codec oder Decoder abhängen. Ein konstanter Erfolgswert über viele Übergänge wäre ein Hinweis auf einen systematischen Offset. Die Ausgabe muss noch praktisch geprüft werden.
- **Tooltips #192 (seit 4.4.1-beta.4):** Das gemeinsame Design aus `web/tooltips.js` läuft im Hauptfenster **und** im abgedockten Player. `title`-Attribute werden beim Initialisieren sowie bei später hinzugefügten/aktualisierten Elementen in `data-tip-title` überführt, sodass native Browser-Tooltips nicht mehr mit dem app-eigenen Design konkurrieren. Dynamische Texte (Metronom, Play/Pause, Cue, Vor-/Zurückspringen, Cover, Beatgrid-Status) bleiben aktuell; Fokus per Tastatur wird berücksichtigt. Schutz gegen doppelte Initialisierung und Regressionstests.
- **Überblenddauer und Metronom #181 (seit 4.4.1-beta.5):** Einstellungen → Player erlaubt 0 (aus) bis 30 Sekunden Überblendzeit in ganzen Sekunden. Das Backend konnte bereits 30 Sekunden; bisher war die UI-Auswahl auf 12 Sekunden begrenzt. Beim Crossfade wird die Info des alten Tracks im Fade-Zustand aufbewahrt; Metronom A folgt diesem Raster bis zum tatsächlichen Abschluss des Ausblendens. Erst nach `plFadeStop()` wird die Metronom-Zeitbasis auf den neuen Titel umgestellt; bereits geplante alte Klicks werden gelöscht. Scheitert der Wechsel, bleibt es beim alten Track; fehlt das neue Beatgrid, bleibt es eingeschaltet und wartet ohne Klicks auf ein neues Raster. Player B bleibt unabhängig. Noch durch Hörtest zu bestätigen.
- **Metronom #181 (seit 4.4.1-beta.4):** Trotz Erhöhung auf 0.20/0.30 in beta.3 war das Sinus-Metronom hörbar zu leise. Neu: durchsetzungsfähigerer kurzer Rechteck-Klick (1.6/2.1 kHz, 70 ms mit Envelope), **Metronom-Lautstärke 0–100 %** (Standard 80 %, Maximum intern unter Vollaussteuerung). Ein gemeinsamer Regler für A und B unter Einstellungen → Player sowie Dialog im Player-A/B-Menü; die Lautstärke lässt sich bei aktivem Metronom vorhören und wird separat in den Player-Einstellungen gespeichert. 0 % ist stumm. Die Track-Lautstärke und die Beatgrid-Positionen bleiben unverändert; bei Kopfhörern vorsichtig erhöhen. Der Klicktest klang subjektiv on beat, Crossfade bleibt offbeat: als Nächstes Player-/Seek-/Decoder-Latenz und Takt-/Phrasenphase prüfen.
- **Metronom-Uhr #181 (nach beta.6):** Klicks werden nicht mehr direkt aus `audio.currentTime` geplant, sondern aus einer
  geglätteten Medienuhr (`plClockSample`/`plClockEstimate` in `web/metronome.js`): Proben der letzten 800 ms, Steigung =
  PlaybackRate. Abweichung > 40 ms (Seek, Stillstand beim Anlaufen) → Uhr zurücksetzen und geplante Klicks verwerfen;
  geklickt wird erst wieder nach ≥ 4 Proben über ≥ 150 ms mit Restfehler < 25 ms. Grund: nach einem Klick in den Titel
  steht `currentTime` kurz still bzw. springt; die früheren Klicks lagen dann versetzt.
- **BPM-Anzeige #194:** Einzelklick öffnet den Tempo-Dialog (#174) erst nach 320 ms, damit ein Doppelklick ihn ersetzen
  kann; Doppelklick (bzw. Entf/Rückschritt/0 bei Fokus) = Originaltempo (`plTempoOriginal`). Mausrad = ±0,1 BPM, mit
  Shift ±1 BPM (`plTempoNudge`), begrenzt auf 50–200 %, rastet bei < 0,05 BPM Abstand auf dem Original ein. Player A
  und B; das abgedockte Fenster zeigt die Anzeige nur.
- **Fortsetzen #195:** Beim Start laufen Tagger-Einlesen und `plResume` gleichzeitig (der Player hat Vorrang).
  Ist der Titel noch nicht im Tagger, lädt der Player ihn über die Art `file` (ref = Pfad; `Session._resume_file`
  erlaubt nur Pfade aus `player_resume`, liest die Datei ohne sie ins Register zu legen). Nach dem Einlesen stellt
  `plResumeAdopt` A und B per `tag_locate` auf `tag`/Index um und markiert den Titel A im Tagger (`plResumeSelect`:
  Auswahl, Scrollen, Details, ohne den Player umzuschalten; Filter bleiben). Bewerten aus dem Player geht erst danach.
- **Doppelklick #196:** im Tagger beim zweiten `mousedown` erkannt (nicht `click`): Kommen die Details des ersten Klicks
  zwischen Drücken und Loslassen an, zeichnet die Liste neu und der Browser verwirft den `click`. Abspielen sofort,
  ohne auf `tag_detail` zu warten. `isDoubleClick` misst ab `e.timeStamp`, Fenster 600 ms.
- **Übergänge im Takt halten #181 (nach beta.6, `web/xfadesync.js`):** Ursache der Offbeat-Übergänge: Die Phase wird
  einmal berechnet und per Seek gesetzt; während der Seek-/Decoder-Anlaufzeit läuft der alte Titel weiter, der neue liegt
  danach um diese Zeit zurück (Browser-Test: ≈ 90 ms). Ein zweiter Seek hätte dieselbe Verzögerung. Lösung wie am
  Jogwheel:
  1. Messen: Beide Medienuhren mit der geglätteten Uhr (oben) zum selben Zeitpunkt schätzen, Beat-Versatz
     `plXsyncError` in ms (Wanduhr, + = Folgetitel zu früh, gewickelt auf ±½ Schlag). Beide Elemente spielen über
     dieselbe Ausgabe, ihre `currentTime` sind vergleichbar.
  2. Nachführen: `plXsyncNudge` – Tempo-Korrektur des Folgetitels, Fehler/1 s, Totband 4 ms, höchstens ±4 %; nach jeder
     Änderung die Uhr des Folgetitels neu einschwingen. Am Ende des Überblendens wird die Korrektur zurückgenommen.
  3. Lernen: Der erste eingeschwungene Versatz geht zu 70 % in `xfade_seek_ms` (±500 ms) ein und wird beim nächsten Seek
     vorgehalten (`plXfadeCalibratedTime(…, latency − pre)`). Nur bei abgeschlossenem Übergang mit Nachführen.
  4. Protokoll: je Übergang Dateinamen, BPM, Rasterquellen, Taktgrenze, Korrektur/Vorhalt, Versatz Start/Ende, maximale
     Korrektur, Verlauf alle 0,5 s → `Api.player_log` → `app.log` („Übergang: {…}“); die letzten 20 auch im Dialog
     Einstellungen › Player › „Messwerte …“.
  Einstellung `xfade_lock` (Standard an) schaltet 2 und 3 ab; gemessen und protokolliert wird trotzdem. Die
  Folgetrack-Korrektur `xfade_latency_ms` bleibt als Zielversatz. Gilt nur für Player A mit „Im Takt“ und zwei Rastern.
  Offen: Hörtest; bei grossem Startversatz klingt die Korrektur (bis 4 %) während des Einblendens evtl. leicht – der
  gelernte Vorhalt soll das ab dem zweiten Übergang verringern. Weitere Stufen (gemeinsame Web-Audio-Uhr,
  sample-genauer Start über `AudioBufferSourceNode`) erst, wenn die Messwerte das verlangen.
- Tempo von Hand wird nicht gespeichert und gilt nur für den Titel; ein neuer Titel startet im eigenen Tempo (#174).

## 5. Offen / Ideen

- **4.4.1 – #181 (Offbeat):** Crossfade-Kalibrierung implementiert, aber noch nicht hörgetestet; keine Beta ohne ausdrückliche Freigabe. **#182 (Takt-/Cue-Tasten)** wurde im Praxistest als korrekt bestätigt.
- **#181, Metronom-Diagnose für den nächsten Beta-Test:** Serato-`GEOB:Serato BeatGrid` wird bislang als `exact: true` eingelesen, ist aber nicht musikalisch verifiziert. Per ♩ lässt sich das benutzte Raster für A/B oder abgedocktes Fenster hörbar machen (Web Audio, Tempo- und Marker-Anpassung, pausiert beim Anhalten/Spulen). Der betonte Beat im Vierer-Raster ist **keine erkannte Downbeat-Position**. Konstante Abweichung deutet auf Grid-Offset, zunehmende Abweichung auf BPM-/Temposchwankung oder Wiedergabe-Timing. Ein Metronom ist kein samplegenauer Audiotest.
- **#181:** Das neue Audio-Element während Lade- und Analysephase stumm halten, erst nach erfolgreichem `play()` im aktuellen Takt des alten Players ausrichten und dann einblenden. Negative Zielzeiten nicht pauschal auf 0 kappen; Tempo des neuen Audio-Elements jedes Mal explizit setzen. Dies verbessert die Synchronisation, ersetzt aber keinen samplegenauen DJ-Audio-Mixer.
- **#182:** Ein Sprung entspricht vier Beats mit optional variablem Grid; ohne Grid nur BPM-Näherung, ohne BPM kein Sprung. Shift+←/→ springt zu Cue-Punkten (ohne Loops); Listennavigation im Tagger behält Vorrang. Gilt für A, B und das abgedockte Fenster.
- Weitere Ideen: Stems einzeln stummschalten, Beatgrid von weiteren Programmen lesen.

## 6. Tests

`tests/test_player.py`, `test_cues_wave.py`, `test_serato.py`, `test_ratings.py`, `test_stemsview.py`,
Oberflächen-Tests in `tests/test_browser_ui.py`.
