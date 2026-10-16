# MarKusSXCH TagStudio – Projektstand

> Stand 2026-10-17: **4.5.0 final** veröffentlicht (Windows + macOS, ohne Beta; Meilenstein #15 geschlossen, 21 Issues: #183–#185, #187, #189, #200–#214, #216). Meilenstein #17 „4.6.0“ in Arbeit: #215, #191, #220, #221, #223, #224 im Beta-Test. Zuvor: **4.4.1 final** (veröffentlicht 16.10.2026, Windows + macOS; Meilenstein #14 geschlossen). Inhalt: Übergänge im Takt messen/nachführen (#181, `web/xfadesync.js`), Beatgrid-Metronom, Takt-/Cue-Sprünge (#182), Tooltips (#192), BPM per Doppelklick/Mausrad (#194), Player startet vor dem Tagger (#195), schneller Doppelklick (#196), Dateiordner im Kontextmenü (#197), Herkunfts-Auswahl mit Kennzeichen (#198/#199). **In Arbeit: 4.5.0 – Tagger & Metadaten** (Meilenstein #15, freigegeben 16.10.): #185 Letzte Bearbeitung (`TXXX:TAGSTUDIO_EDITED`, `tsmeta.py`), #184 In Bibliothek aufgenommen (`TXXX:TAGSTUDIO_ADDED`, Nachtragen aus Snapshots), #183 Liedtexte (`plugins/lyrics`, LRCLIB, USLT + SYLT, `.lrc` per Plugin-Einstellung) – alle drei auf main im Beta-Test. Entscheide siehe Issue-Kommentare vom 16.10. **Ausserdem 4.6.0 (Meilenstein #17): #204 Online-Dienste als Plugins** – je Dienst ein Plugin (MusicBrainz, AcoustID, Deezer, iTunes, Discogs, Last.fm, LRCLIB, Beatport, Lexicon) mit API-Link, „Integration …“ (Endpunkt-Tabelle vollständig/teilweise/nicht, Testabfrage ohne Track, API-Tester nur lesend), Plugins › „Integrationen …“ (inkl. Update-Prüfung im Kern); „Online-Metadaten“ ist die gemeinsame Suche über die eingeschalteten Dienst-Plugins, Entdecken nutzt das Plugin Deezer; Schlüssel je Plugin verschlüsselt (einmalige Übernahme aus `online/keys.bin`). Auf main, bereit zum Beta-Test. Details `docs/KONZEPT-PLUGINS.md`.

## Aktueller Stand (nach 4.1.0)

- **4.1.0 ist abgeschlossen:** Release v4.1.0 (Windows + macOS, Python 3.15 im Installer), Beta-Releases automatisch entfernt, Meilenstein #3 geschlossen (15 Issues: #6, #7, #8, #125–#136 inkl. CodeQL #128–#130).
- **User startet TagStudio normalerweise aus `S:\_Claude\markussxch-tagstudio` (Quellcode, sein Python 3.14)**; installiert war nur der 3.15-Probe-Build. Er testet **ausschliesslich auf Windows**.
- **CI-Entscheide 2026-10-11:** Linux nicht mehr getestet (Wiedereinschalten in `tests.yml`); **Betas: Tests und Installer nur Windows**, finale Versionen zusätzlich macOS (Installer-Workflow: Eingabe „Auch macOS bauen“ für Ausnahmen). Erst die nächste Beta zeigt, ob das Release ohne macOS-Datei sauber angelegt wird.
- **Auftrag des Users 2026-10-11 03:18:** Ideen als Issues erfassen (#138–#157, Meilenstein „Später“, Label `idee`), neuen Meilenstein planen (#76 muss dabei sein) und selbständig umsetzen – ohne Rückfragen, keine Extra-Kredits. User schaut ab Sonntag 09:00.
- **4.2.0 ist final** (Entscheid User 12:54: „alles in 4.2.0“): Meilenstein #11 umbenannt in „4.2.0 – Player, Tagger-Komfort, Importer & Playlist“, enthält jetzt auch #12, #138, #145, #146; Meilenstein #12 (4.3.0) leer und geschlossen. Alle Issues getestet und geschlossen.
  - #76 Serato lesbar + Beatgrid (Serato, sonst Audio-Analyse `beatAnalyse`, gespeichert im Wellenform-Cache), Überblenden im Takt/auf Taktgrenze, Sync B, Option `xfade_pitch`.
  - #137 Start im Hintergrund + Listen-Cache als Pack (`listcache._Pack`), gemessen 15.9 s → 3.0 s.
  - #139–#155 Tagger/Player-Komfort (Doppelklick, Feldnamen, Herkunft-Sortierung offizielle Felder zuerst, Spalten, Sortierstufen, Ansicht, Cover-Bereich links Länge/Bewertung rechts Info+Knöpfe, Vorschau „Nur fehlende“/„Vorauswahl“).
  - #147 MIK-Plugin, #145 beaTunes-Plugin, #146 Lexicon-Plugin (Local API `/v1/tracks` limit ≤ 1000, `/v1/tags`; Werte 0–10, 0 = nicht analysiert), gemeinsamer Abgleich `importsync.py` (TXXX:TAGSTUDIO `sync`).
  - #138 DJ-Set-Listen (cfg `djset_saved`, `djset_name`) + Warteschlange (cfg `player_queue`, `web/queue.js`).
  - #12 Stimmung `moods.py` (v2.4 TMOO, v2.3 TXXX:MOOD), Chips im Tagger, eigene Liste cfg `mood_list`.
- **Meilenstein #13 „4.3.0 – Hilfe, ID3, Snapshots, Tracks vorbereiten (Phase 1)“** (Auftrag User 13:06 + 13:23/13:25, „alles in diese Beta“), alle `_3 Beta-Test`, Testlisten in den Issues:
  - #13 Binärfeld-Editor/JSON-Baum im Vergleich (`cmp_blob/cmp_blob_set`, `blobEditor(src,key)`, `jsonEditDialog`).
  - #98 `id3frames.py` (SPEC aller Frames, `describe()` für Binär-Frames, V22_TO_V23, IPLS↔TIPL), `tools/id3_frames_doc.py` → `docs/ID3-FELDER.md` (Test prüft Aktualität).
  - #59 Journal-Export (Excel/CSV, `snap_journal_write`), Sicherungen im Snapshot-Speicher (`backup.StoreBackupWriter`, `make_writer`, Manifeste `<store>/backups/*.json`, `snapshots.PINNED`, cfg `backup_store`, Standard an).
  - #158 Hilfe-Seite (`taghelp.py`, `session_help.py`, `web/help.js`): Kapitel nach dem PDF des Users „DJ Software vergleichen“ (ID3v2.4 nach Funktion 1–10, 11 DJ-Analysewerte, DJ-Software-Vergleich, Programm-Daten aus Herkunft, CUSTOM-Tags aus Scan), Scan-Cache `~/TagStudio/cache/tagscan/<hash>.json`, Zähler → Tagger-Feld-Filter (`tag_field_filter`, Chip „vorhanden/fehlt“), Handbuch/ID3/Plugins als Markdown.
  - #112 ID3v1 schreiben (`MP3File.v1_mode`, cfg `save_v1`). #111 Tag-Rezepte (`recipes.py`, `web/recipes.js`, cfg `recipes`, Vorlage „Beatport-Download aufbereiten“ – Wortliste Dj/Feat/Mc/Vs vom User bestätigt 2026-10-12).
  - #109/#110/#113–#116 Vorbereiten (`prepare.py`, `session_prepare.py`, `web/prepare.js`): cfg `prep_workflows`/`prep_current`, Zustand `~/TagStudio/Vorbereiten/<wid>.json`, Schritte recipe/external/import/check + (beta.4) **plugin** (Plugin-Aktion auf Stufen-Kopie, `prepare.PLUGIN_MODES` fill/checked/none, Optionen aus cfg `plugin_options`, `_prep_plugin`) und **verify** (Pflichtfelder, `VERIFY_DEFAULT`, `missing_fields`), Seitenleisten-Zahl per `prep_pending` alle 2 min, Schutzregel A/B/C, Erkennung über Herkunft, Duplikatprüfung, Snapshot nach Übernahme, Stufen-Kopien löschen nach Rückfrage.
  - #119 Plugin `plugins/loudness` (EBU R128 via FFmpeg aus Stems-Daten/imageio/PATH; Felder LUFS_I/TRUE_PEAK/LOUDNESS_RANGE, ReplayGain; angeglichene Kopie loudnorm 2-pass, 320k, Tags byte-genau).
  - #118 Quellen (beta.5): Workflow-Feld `sources` [{id,name,folder,pattern,sub,zip}], `prepare.source_candidates/fetch_source` (MP3 + ZIP-Mitglieder, Schlüssel Pfad|Grösse|mtime in Zustand `fetched`, Track `source`/`origin_file`), `start_prep_fetch`, Knopf „Abholen“, Seitenleiste „↓n“. #119 ergänzt um Clipping (volumedetect `histogram_0db`/`n_samples`, ab 0,01 %, Option TXXX:CLIPPING; adeclip bewusst nicht).
  - #120 Entdecken (beta.6): `discover.py` (Deezer öffentlich: search/artist, artist/albums, album, search label:"…"; Beatport über Plugin-Client: catalog/search artists|labels, catalog/tracks?artist_id|label_id&order_by=-publish_date, catalog/genres/{id}/top/100/), `session_discover.py` (DiscoverMixin), `web/discover.js`, Reiter im Vorbereiten-Kopf (`#prepTabs`), Zustand `~/TagStudio/Entdecken/entdecken.json`. Nur mit Mocks getestet (keine Netzverbindung zu Deezer/Beatport).
  - Meilenstein #13 umbenannt in „… (Phase 1–3)“, #118 und #120 dorthin verschoben.
  - #117 Spike: Beatport-Aktion „purchases“ (probiert `/my/downloads/`, `/my/library/tracks/`, `/my/library/`, loggt Feldnamen, CSV vorhanden/fehlt) – Download erst nach Testergebnis des Users.
  - Offen aus Vorbereiten: #118 weitere Plattformen, #120 Entdecken, #121 Übersicht (Kommentar mit Stand).
  - Offene Rückfrage an den User: Wortliste im Rezept „Dj, Feat, Mc, Vs“ (aus Konzept) wirklich so?
- **Konzepte (#156, #157):** `docs/KONZEPT-WAV.md` + `tools/wavcheck.py`; `docs/KONZEPT-MEHRSPRACHIG.md`. Entscheide des Users: Schweizerdeutsch = **Mundart**; WAV-Tags müssen in **Engine DJ, Serato, Rekordbox, VirtualDJ** lesbar sein. Noch Konzept (Meilenstein „Später“).
- **Nächste Schritte:** Testergebnisse 4.3.0-beta.4 auswerten (Testlisten beta.4 in #109/#110 als Zusatz-Kommentar); danach Phase 2 Vorbereiten oder #156 WAV Schritt 1; Tracks vorbereiten (Meilenstein #10, #109–#121) wartet auf `_1 bereit`.
- **Erster Schritt im neuen Chat:** dieses Dokument lesen, Repo per `add_repo` anhängen und flach klonen, offene Issues per `gh api` holen, mit dem User den nächsten Umfang klären.
- **Lokal beim User (offen von 3.5.0):** `~/MP3TagCompare` (nur `cache`) kann weg; im lokalen Klon `git fetch --prune`.

## Was in 4.1.0 steckt

- **#6–#8 Plugin „Online-Metadaten“** (`plugins/online`, Modul `onlinematch.py`): MusicBrainz (ISRC oder Lucene-Suche, Release-Wahl offiziell/keine Kompilation/Album-Single-EP/frühestes, CAA-Cover, MB-IDs), AcoustID (fpcalc), Deezer (erweiterte Suche, Ersatz einfache Suche), iTunes (Land, 1400 px), Discogs (Token), Last.fm (Tags, nie vorausgewählt). Vorschau je Feld, erste Quelle vorausgewählt, andere „Alternative“. Drosselung je Dienst, 429/503-Wiederholung. Schlüssel in `ctx.data_dir/keys.bin` (DPAPI unter Windows). Formular „Schlüssel …“ mit Anleitung und Links (Plugin-Optionen `info` können jetzt `title` und `links` haben). Workflow **Online-Test** (`tests/test_online_live.py`, wöchentlich + bei Änderungen) prüft echte Antworten; Felder stehen als Anmerkungen.
- **#125 Fenster:** Grösse/Position/maximiert (`window_start`, `set_window_geometry`), unsichtbare Position → mittig.
- **#126 Wiedergabe fortsetzen:** cfg `player_resume` {A/B: path, pos, playing}; Einstellung „Nach dem Neustart“ `resume_play` = pause/play/was.
- **#127 Tagger-Zustand:** cfg `tagger_state`, Start „zuletzt/Standard/nichts“.
- **#131 Nur eine Instanz** (`instance.py`): Sperrdatei `~/.tagstudio.lock` (msvcrt/fcntl) + Windows-Mutex `MarKusSXCH-TagStudio`; Inno `AppMutex`; zweiter Start → Hinweis (MessageBox nur im App-Modus), Neustart setzt `TAGSTUDIO_RESTART=1` (neue Instanz wartet bis 25 s). `restart()` beendet per `os._exit` ohne `destroy()`.
- **#132 Beenden mit Hinweis:** Fenster-X → `on_closing` gibt False zurück und ruft im Faden `appQuit()` auf (Rückfragen in der App, „Einstellungen werden gespeichert …“, `appFlushState`, `quit()`); zweites X innerhalb 15 s schliesst auf dem alten Weg. `close_cancelled()` setzt zurück.
- **#133 Einstellungen › Expert:** `applog.py` (`~/TagStudio/Logs/app.log`, 1 MB → `.1`, Hooks, Aufruffehler ohne Argumente, JS-Fehler über `client_log`), Api `expert_info/expert_config` (Token/Passwort maskiert)/`expert_logs`/`expert_log`, Betrachter mit Suche.
- **#134 Seitenleiste unten:** Vollbild (F11), Fenstermodus, Neustart, Beenden (`window_mode`, `appWindow`, `appRestart`, `appQuit`).
- **#135 Python:** Mindestversion 3.12 (`MIN_PYTHON` in `tagstudio_web.py`), Tests 3.12 + 3.15 auf allen drei Systemen, Installer-Workflow mit Eingabe `python` (Probe-Build, nur Artifacts). Probe-Build 3.15.0 vom User getestet → **Installer ab beta.3 mit Python 3.15**. Tk-Test der klassischen Oberfläche stürzt auf macOS/3.15 ab (übersprungen). Plugin-Umgebung: fehlendes Basis-Python (uv-Trampolin) wird erkannt (`plugins.env_broken/env_runs`), „Neu installieren“ legt dann neu an.
- **#136 Versionshinweise:** `updater.changelog_versions`, `release_notes()['older']`, Abschnitt „Weitere Versionen“ (aufklappbar, Inhalt beim Öffnen).
- **Behoben:** `save_config` mit Lock + atomarem Schreiben.

## Lehren

- Installer startet nur bei Änderungen an `version.py`/`packaging/`; ein Start von Hand (workflow_dispatch) legt **kein** Release an. Nach gescheitertem Build `version.py` anfassen.
- Tests mit Unterprozessen: `PYTHONUNBUFFERED=1` setzen, sonst hängt `readline()` in der CI (lokal ist die Variable gesetzt). Keine Meldungsfenster in Tests/Browser-Modus.
- `evaluate_js` nie synchron im `closing`-Ereignis (kann hängen) – im Faden mit Zeitlimit.
- Windows-Uhr ±16 ms: Zeitprüfungen in Tests grosszügig.
- Live-APIs (MusicBrainz, Deezer, iTunes) sind aus der Sitzung nicht erreichbar → über den Workflow Online-Test prüfen.

## Arbeitsweise (mit User vereinbart)

**Repo und Arbeitsorte**
- Repo `MarkusKeller8200/markussxch-tagstudio` (**öffentlich** – keine privaten Daten, Zugangsdaten oder MP3 ins Repo). Gearbeitet wird nur auf `main`, gepusht nur auf `origin main`.
- Cloud-Klon: `/home/claude/markussxch-tagstudio` (in neuer Sitzung per `add_repo` + flachem Klon neu anlegen).
- Lokaler Klon des Users: `S:\_Claude\markussxch-tagstudio`, erreichbar über die Desktop-App-Brücke, falls verbunden.

**Pro Issue**
- Code, Unit-Tests und ein Browser-Test mit Playwright.
- Commits auf Deutsch mit „Refs #n“ bzw. „Fixes #n“ und dem Trailer `Co-Authored-By` / `Claude-Session`.
- Rückmeldungen des Users während der Beta: neue Punkte als eigenes Issue (Meilenstein der laufenden Version), Erweiterungen bestehender Issues dort ergänzen.

**Tests**
- Unit: `python3 -m unittest discover -s tests -q` (ca. 324 Tests, einige übersprungen). Mindestversion Python 3.12; CI 3.12 + 3.15 auf Windows und macOS.
- Oberfläche: `TAGSTUDIO_UI_TESTS=1 python3 -m unittest discover -s tests -p "test_browser_ui.py"` (ca. 33 Tests, ca. 220 s; `setUp` schreibt `.tagstudio.json` mit `setup_done`, ausser Tests mit „wizard“ im Namen). Hilfen `until(js)`, `cfg_until(test)`, `restart()`.
- Testserver: `tagstudio_web.py --browser --no-open --port 0` mit eigenem HOME. Das Start-Hinweis-Modal zuerst schliessen.
- Pfad-Tests plattformneutral schreiben.

**Release**
1. `python3 packaging/release.py X.Y.Z-beta.N` (final: `X.Y.Z`; verschiebt „Unveröffentlicht“ im CHANGELOG).
2. Committen und pushen; Workflow „Installer“ legt Tag und Release an (Beta = Pre-Release).
3. Bei finaler Version entfernt `cleanup_betas.py` die Beta-Releases (Tags bleiben).
- CI prüfen (Fehlertexte als Anmerkungen der Check-Runs, Logs nicht lesbar).
- Finale Version nur auf ausdrücklichen Wunsch des Users.
- Neue Python-Module in `packaging/build.py` unter `HIDDEN` eintragen.

**Test-Ablauf mit dem User**
- Nach dem Beta-Release je Issue ein Kommentar mit der Testliste.
- User meldet „getestet ok“ → Issue schliessen, Status-Label entfernen.

**Labels und Meilensteine**
- `_1 bereit` (setzt der User) → `_2 in Arbeit` → `_3 Beta-Test` → schliessen und Label entfernen.
- `idee` = noch nicht eingeplant (Meilenstein „Später“). `enhancement` = Funktion/Verbesserung, `bug` = Fehler.
- Plugin-Ideen in #108.

**GitHub-Zugriff**
- Nur per REST (`gh api repos/...`). Gesperrt: GraphQL, Projekte, Repo-Einstellungen, Releases schreiben, Zweige/Tags löschen.

**Sicherheit**
- Löschen (Dateien, Branches, Tags, Labels) nur nach Rückfrage.
- Keine Zugangsdaten anfassen: Passwörter, Tokens und Schlüssel gibt der User selbst ein; nie speichern (ausser verschlüsselt im Plugin), nie protokollieren oder exportieren.

**Projekt-Doku**
- Dieses Dokument nach jedem Release aktualisieren; Altes ins Archiv.
- Ablage doppelt: Claude-Projekt (`claude/projektstand.md`, `claude/projektstand-archiv.md`, `claude/speicherkonzept.md`) **und** Repo (`docs/PROJEKTSTAND.md`, `docs/PROJEKTSTAND-ARCHIV.md`, `docs/KONZEPT-SPEICHER.md`). Beide Fassungen gleich halten.
- Übergabe an einen neuen Chat: `docs/UEBERGABE.md` nachführen (Einstieg, Arbeitsweise kurz, offene Punkte).
- Jede Funktion hat ein Konzept `docs/KONZEPT-*.md` (Übersicht in `docs/UEBERGABE.md`). Wird an einer Funktion weitergearbeitet, das Konzept im selben Zug nachführen (Entscheid User 2026-10-11).

## Entscheide

- **Klassische tkinter-Oberfläche** eingefroren (#106).
- **Abgelehnt/aufgeschoben:** #15 macOS Intel; #14 Installer signieren offen.
- **Zusammengelegt:** #10 in #9; #104 in #76.
- **Update-Kanal** (cfg `update_channel`): `stable` / `beta`.
- **DJ-Set exakt nur bis 15 Titel.**
- **App-Erweiterungen #125–#127** in 4.1.0 (nicht im Datenbank-Modul).
- **Tracks vorbereiten:** Entscheide 1–5 vom 2026-10-10 im Konzept (Stufen-Ordner optional löschen, Kopie nach `_03_PlatinumNotes`, Picard/AudioRanger/OneTagger vorerst extern, Schutzregel konfigurierbar mit Vorgabe C + „nur melden“, inoffizieller Beatport-Zugriff akzeptiert).

## Architektur (Kurzüberblick)

**Kern (Python, nur stdlib)**
- `core.py` (Laden, Speichern, `save_config` mit Lock), `id3tags.py`, `compare.py`, `tagger.py`, `keys.py`, `ratings.py`, `features.py`.
- `setplan.py`, `setexport.py`, `origins.py`, `cues.py`, `waveform.py`, `media.py`, `thumbs.py`.
- `snapshots.py`, `backup.py`, `undo.py`, `listcache.py`, `jobs.py`.
- `plugins.py` + `plugins/` (stems, beatport, online, mik, beatunes, lexicon), `onlinematch.py`, `importsync.py`, `serato.py`, `updater.py`, `appsettings.py`, `version.py`.
- Neu 4.1.0: `instance.py` (eine Instanz), `applog.py` (App-Protokoll).

**Session (`session.py`)**
- `class Session(SnapshotMixin, PlayerMixin, DjSetMixin)`; Mixins in `session_player.py`, `session_snapshots.py`, `session_djset.py`.

**Oberfläche**
- `tagstudio_web.py`: Api (pywebview/Browser), `_PASS`-Weiterleitungen (mit Fehlerprotokoll), direkte Methoden u. a. `restart`, `quit`, `window_mode`, `expert_*`, `client_log`.
- `web/`: `index.html`, `app.js` (appQuit/appRestart/appWindow/appFlushState), `app.css`, `modules.js`, `settings.js` (Expert-Kachel), `tagger.js`, `snapshots.js`, `djset.js`, `plugins.js`, `keywheel.js`, `xmleditor.js`, `jsontree.js`, `features.js`, `jobs.js`, `player.js`, `player2.js`, `player-window.html`, `playerwin.js`.
- Menü: Vorbereiten · Tagger · Tag-Fixer · Vergleich · DJ-Set · Snapshots · Sicherungen · Plugins · Einstellungen · Datenbank; unten Update, Versionshinweise, Einklappen, Design, Fenster-Symbole.

**Paketierung**
- `packaging/build.py`, `windows.iss` (mit `AppMutex`), `make_dmg.sh`, `release.py`.
- Workflows: Tests (Betas Windows, final + macOS), CodeQL, Installer (Eingaben `python`, Standard 3.15, und `macos`; Betas nur Windows), Online-Test, Stems-Test, Releases aufräumen.

**Konfiguration**
- `~/.tagstudio.json` (neu: `tagger_state`, `player_resume`, `window`, `player.resume_play`), `~/.tagstudio.lock`.
- `~/TagStudio`: Sicherungen, cache, Plugins, Plugin-Daten, Logs (`app.log`).

## GitHub-Meilensteinverwaltung

Meilensteine können über den **gesicherten [Administrationskanal #190](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/190)** verwaltet werden. Das Issue ist bewusst **geschlossen**, aber für Eigentümer-Kommentare nutzbar. Der Workflow `.github/workflows/milestone-admin.yml` akzeptiert ausschliesslich einzeilige Kommentare vom Repository-Eigentümer auf #190, beispielsweise `/milestone list`, `/milestone create 4.6.0 – Titel`, `/milestone close 14` oder `/milestone reopen 14`. GitHub Actions verwendet dafür den Repository-Token mit `issues: write`. Ergebnisse im Issue-Thread überprüfen. Keine anderen Issues als Steuerkanal verwenden. Siehe [technische Anleitung](../.github/scripts/MILESTONE-ADMIN.md).

## Roadmap (Entscheid 17.10.2026)

- **4.6.0 – Beatgrid & Lyric Sync** (#17): #215 Liedtext im Player (`lyricsync.py`, `web/pllyrics.js`), #191 Beatgrid-Status im Tagger (`gridstatus.py`, `web/gridscan.js`), #220 Serato-Wellenform im Player (`serato.overview_wave`), #221 Beatgrid im MP3 (`beattag.py`, `TXXX:TAGSTUDIO_BEATGRID`), #223 Vergleich Serato ↔ eigene Analyse (`gridstatus.compare`, `plGridCompare`, Codes `serato_ok`/`serato_diff`; liest auch das neuere GEOB „Serato Tempo Map“ – Format aus einem Beispiel erschlossen, `serato.tempomap`), #224 Lupe im Player (`web/plzoom.js`) – alle auf `main`, `_3 Beta-Test` (17.10.2026). #222 Wellenform als GEOB = Idee (später).
- **4.7.0 – Mehrsprachigkeit** (#18): #157 Grundlage, Sprachwahl, alle Module in `de-CH`, `en`, `gsw-u-sd-chzh`; Claude übersetzt bei der Entwicklung mit (keine KI-Anbindung in TagStudio).
- **4.8.0 – Mehrsprachigkeit: Plugins, Doku, eigene Anpassungen** (#19): #219 inkl. Export/Import mit Überlagerung in den Benutzereinstellungen.

## Arbeitsregeln vom 16.10.2026

- **Meilensteine ohne Planungs-Issue (Entscheid 16.10.2026):** Beim Anlegen eines Meilensteins kein eigenes Issue mit
  der Meilenstein-Beschreibung (wie früher #188/#189) – die einzelnen Issues im Meilenstein genügen.
- **Developer Release (Entscheid 16.10.2026):** Eingecheckter Stand ohne Beta/Release zeigt neben der Version das
  Kennzeichen „Developer Release“ (`updater.dev_info`: Commits nach dem Tag `v<VERSION>`; installierte App nie).

## Release-Freigabe (Entscheid 14.10.2026)

**Beta- und finale Builds/Releases ausschliesslich nach ausdrücklicher neuer Rückfrage und Bestätigung des Projektverantwortlichen starten.** Code-Commits und reguläre automatisierte Tests/CodeQL sind davon nicht betroffen; bis zur Freigabe weder `version.py` noch einen Release-Tag oder den Installer-Workflow verändern/auslösen. Hintergrund: `version.py`-Änderungen auf `main` lösen über GitHub Actions automatisch einen Installer- und Pre-Release-Build aus. Der aktuell veröffentlichte Stand ist **v4.5.0** (final, freigegeben am 16.10.2026); spätere Änderungen liegen bis zur nächsten Freigabe ausschliesslich auf `main`. Auch wenn ein Issue für Entwicklung oder Beta-Test freigegeben ist, bedeutet dies **keine Release-Freigabe**.

## Geplante Iterationen 4.4.1 und 4.5.0 (Entscheid 2026-10-14)

**Planung freigegeben, Implementierung noch nicht abgeschlossen.** Details und Abnahmekriterien: [Releaseplanung 4.4.1 (#188)](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/188), [Releaseplanung 4.5.0 (#189)](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/189).

- **4.4.1 – Player-Stabilität:** [#182 Takt-/Cue-Sprünge](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/182) vom User am 14.10.2026 als korrekt bestätigt, Issue **geschlossen**. [#181 Offbeat-Übergänge](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/181) weiterhin **offen**; auf `main` existiert eine noch nicht veröffentlichte manuelle Latenz-/Phasenkorrektur (−500 bis +500 ms, Default 0; Einstellung für alle automatischen Übergänge), Code- und CI-Tests erfolgreich. Neues Beta nur auf ausdrückliche Freigabe. Kein ungefragter JUCE-/GUI-Umbau.
- **4.5.0 – Tagger & Metadaten danach:** [#184 Bibliotheksaufnahme](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/184), [#185 Letzte Bearbeitung](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/185), [#183 LRCLIB-Lyrics](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/183). Diese Issues sind **weiterhin `idee`** und noch nicht zur Umsetzung freigegeben.
- **Später / Konzeptphase:** [#186 Neues Modul IDEE](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/186), [#187 GitHub-Meldeformular mit Eigentümerfreigabe](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/187), [#180 1001Tracklists](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/180) und die grössere Analyse-/Audio-Architektur.
- **Meilensteinpflege (am 14.10.2026 geprüft):** Das Release [v4.4.0](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/tag/v4.4.0) ist veröffentlicht; der GitHub-Meilenstein [#10](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/10) ist **geschlossen** (17 von 17 Issues erledigt). Die neu angelegten Meilensteine [#14 – 4.4.1 Player-Stabilität](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/14) enthalten #181, #182 und Planungs-Issue #188; [#15 – 4.5.0 Tagger & Metadaten](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/15) enthalten #183–#185 und Planungs-Issue #189. Alle übrigen neun offenen Ideen sind [#4 – Idee (Später)](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/4) zugeordnet. **Kein offenes Issue ohne Meilenstein** (Stand 14.10.2026). Am 15.10.2026 kam #193 (BugFixes) in #14 dazu.

## Offene Meilensteine und Issues

- **#10 „4.4.0 – …“:** abgeschlossen mit 4.4.0 final (2026-10-12).
- **#14 „4.4.1 – Player-Stabilität“:** #181 (offen, Praxistest), #188 (Planung), #192 und #193 in `_3 Beta-Test` (beta.6).
- **#15 „4.5.0“ (geschlossen, v4.5.0 veröffentlicht):** #183–#185, #201–#204 geschlossen (16.10.); #205 Beispielwerte im Integrationsfenster, #206 Lizenzen mit GitHub-Repositories, #212 API-Tester-Drosselung, #213 IDs übernehmen, #214 Zeitraum-Filter in `_3 Beta-Test`; #207–#211 (CodeQL) geschlossen; #200 Durchsicht vorbereitet; #189 Planung offen bis zum Release.
- **#17 „4.6.0 – Beatgrid & Lyric Sync“:** #215, #191, #220, #221, #223, #224 (#204 nach 4.5.0 verschoben).
- **#4 „Idee (Später)“:** #9, #14, #107, #108, #156 (WAV), #157 (Mehrsprachigkeit), #180 (1001Tracklists), #186 (Modul IDEE), #187 (Feedback-Freigabe).
- **#180 „1001Tracklists: Set-Import, Library-Abgleich und DJ-Intelligence“:** `idee`, Meilenstein „Später“; **ausschliesslich geplant, noch nicht implementiert**. Anforderungen in `docs/KONZEPT-DJSET.md` (Import/Discovery) und `docs/KONZEPT-MUSIKANALYSIEREN.md` (Set-Intelligence/Score) aufgenommen. Vor Automatisierung Datenzugang und Nutzungsrechte klären.

## Versionen (Kurz)

- **4.5.0 – Tagger & Metadaten & Plugin-Management:** TagStudio-Zeitstempel (Aufgenommen/Bearbeitet mit Zeitraum-Filter), Liedtexte (LRCLIB), Filter je Spalte, Online-Dienste als Plugins mit Integrationsfenster/API-Tester, Lizenzen mit GitHub-Repositories, Melden aus der App.
- **4.4.0 – Beatport-Download, Profile, Einrichtungsassistent:** Profile, Assistent, Basisordner/Ordnerstruktur, Aussortieren, Lizenzen-Seite, Tempo von Hand, Im Tagger zeigen.
- **4.3.0 – Tracks vorbereiten, Entdecken, Hilfe.**
- **4.2.0 – Player, Tagger-Komfort, Importer & Playlist:** Beatgrid/Serato, schneller Start, Tagger-Spalten und Sortierung, Plugins MIK/beaTunes/Lexicon mit Abgleich, DJ-Set-Listen, Warteschlange, Stimmung.
- **4.1.0 – Online-Metadaten & App:** Plugin Online-Metadaten, Fenstergrösse, Wiedergabe fortsetzen/Autoplay, Tagger-Zustand, eine Instanz, Beenden mit Hinweis, Expert-Einstellungen, Fenster-Symbole.
- **4.0.0 – DJ-Set:** Set-Optimierung, Seite DJ-Set, Exporte, Merkmal-Spalten/-Filter, Ziehen auf Player, Snapshot-Baseline.
- **3.5.0 – App allgemein & Aufräumen**, **3.4.0 – Wiedergabe & Bewertung**, ältere: Archiv und CHANGELOG.md.
