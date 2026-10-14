# Konzept: Player (Vorschau-Player und externe Player)

Stand: 2026-10-11 (4.4.0) · Status: **umgesetzt** (3.2.0, ausgebaut 3.4.0, 4.1.0, 4.2.0) · nachträglich erstellt

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
| Überblenden | 2–12 s, gleiche Leistung, früh überblenden zum Durchhören, Tempo angleichen (±10 %, Rückkehr einstellbar), im Takt / auf Taktgrenze, Tonhöhe beibehalten |
| Player B | zweiter, gleich aufgebauter Player (nur mit „Player oben“), eigenes Ausgabegerät, Sync zu A, Ziel A/B per Klick/Taste B, Titel per Ziehen laden |
| Layout | unten in der Fusszeile oder oben mit voller Breite (einklappbar, Shift+P), abdocken in ein eigenes Fenster (zweiter Bildschirm) |
| Fortsetzen | zuletzt gehörter Titel (A und B) an derselben Stelle; nach Neustart Pause, Autoplay oder wie beim Schliessen |
| Warteschlange | „Als Nächstes spielen“ / „Zur Warteschlange“ (#138), Vorrang vor Tagger-/Set-Reihenfolge |
| Externe Player | foobar2000, VLC, Rekordbox … mit Platzhaltern `{files}` `{file}` `{folder}` `{m3u}`, Strg/Cmd+P |

## 3. Umsetzung

- **Kern:** `media.py` (lokaler Range-Server nur auf 127.0.0.1, nur freigegebene Dateien, Token, max. 300 Dateien),
  `waveform.py` (Cache `cache/wave`), `cues.py`, `serato.py` (Beatgrid), `ratings.py`, `players.py`.
- **Session:** `session_player.py` (`PlayerMixin`: `player_prefs`, `set_player_pref`, `player_defaults`,
  `player_resume*`, `media_info`, `media_cover`, `media_extra`, `wave_save`, Bus `bus_*` für das abgedockte Fenster,
  `player_window_size`, `players`, `play_external`); `tag_set_rating`, `player_mark`, `tag_locate` (#175) in `session.py`.
- **Tempo von Hand:** `plTempoDialog`/`plTempoSet` in `web/player2.js` (setzt `playbackRate`, Kennzeichen `tempoManual`).
- **Oberfläche:** `web/player.js` (Player A, Wellenform, Analyse), `web/player2.js` (Überblenden, Player oben,
  Player B, Abdocken), `web/player-window.html` + `web/playerwin.js` (Fernanzeige), `web/queue.js`.
- **Einstellungen:** `player` (Werte aus `PLAYER_PREFS` mit Bereichen), `player_defaults`, `player_window`,
  `player_resume`, `players`.

## 4. Entscheide

- Beim Abdocken läuft die Wiedergabe weiter im Hauptfenster; das Fenster ist eine Fernanzeige (Session-Bus).
- Player B nur mit Layout „oben“.
- Beatgrid-Reihenfolge: Serato → eigene Audio-Analyse (Cache) → Schätzung aus BPM-Feld. **Nur das Serato-Raster wird aus einem Track-Tag eingelesen.** `beatAnalyse()` im Browser schätzt aus dem Kick-/Bass-Onset-Signal BPM und Offset; es ist noch keine vollständige Variable-Tempo-/Downbeat-Analyse. Ein BPM-Tag allein ist kein Beatgrid.
- **Kennzeichnung #181:** In Player A/B sowie im abgedockten Fenster wird die Rasterquelle beim Track markiert: `Serato-Grid`, `Audioanalyse`, `Nur BPM-Schätzung` oder `Kein Beatgrid`/`Beatgrid-Analyse läuft`. Bei nicht vorhandenem Serato-Grid wird die Analyse beim Laden zum Vorhören gestartet; Ergebnisse liegen im bestehenden Wellenformcache. Die Anzeige sagt nichts über eine musikalische Verifikation aus.
- **Latenzkorrektur #181 (Testfunktion, noch nicht beta-released):** Unter Einstellungen → Player sowie im ⋯-Menü von Player A kann eine signierte `xfade_latency_ms`-Korrektur zwischen −500 und +500 ms gesetzt werden (Standard 0). Positive Werte lassen den Folgetrack relativ zum aktuellen Beat **später**, negative **früher** hören. Dies erfolgt als Phasenoffset in der Mediaposition, umgerechnet nach PlaybackRate, bevor die Fade-Lautstärke geöffnet wird. Wenn die Position negativ wäre, wird um ganze Beats bzw. Takte vorwärts versetzt, um die Rasterphase zu erhalten. Nur wenn „Im Takt“ aktiv ist und beide Tracks gültige Beatgrids mit kompatiblem Tempo haben. Der Wert wird dauerhaft in den Player-Einstellungen gespeichert und gilt für **alle automatischen Übergänge**, nicht für manuelles Player-B-Sync. Das ist keine automatische Messung der Audio-Latenz; die Korrektur kann von Setup, Track, Tempo, Codec oder Decoder abhängen. Ein konstanter Erfolgswert über viele Übergänge wäre ein Hinweis auf einen systematischen Offset. Die Ausgabe muss noch praktisch geprüft werden.
- **Metronom #181 (nächste Beta erst nach Freigabe):** Trotz Erhöhung auf 0.20/0.30 in beta.3 war das Sinus-Metronom hörbar zu leise. Neu: durchsetzungsfähigerer kurzer Rechteck-Klick (1.6/2.1 kHz, 70 ms mit Envelope), **Metronom-Lautstärke 0–100 %** (Standard 80 %, Maximum intern unter Vollaussteuerung). Ein gemeinsamer Regler für A und B unter Einstellungen → Player sowie Dialog im Player-A/B-Menü; die Lautstärke lässt sich bei aktivem Metronom vorhören und wird separat in den Player-Einstellungen gespeichert. 0 % ist stumm. Die Track-Lautstärke und die Beatgrid-Positionen bleiben unverändert; bei Kopfhörern vorsichtig erhöhen. Der Klicktest klang subjektiv on beat, Crossfade bleibt offbeat: als Nächstes Player-/Seek-/Decoder-Latenz und Takt-/Phrasenphase prüfen.
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
