# Konzept: Plugins

Stand: 2026-10-11 (4.4.0-beta.4) · Status: **umgesetzt** (Plugin-System seit 3.0, Plugin-API Version 1) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird an den Plugins oder am
> Plugin-System weitergearbeitet, ist es im selben Zug anzupassen. Die Entwickler-Anleitung steht in
> [PLUGINS.md](../PLUGINS.md) und ist ebenfalls nachzuführen.

## 1. Ziel

Funktionen mit grossen oder heiklen Abhängigkeiten (PyTorch, Online-Dienste, Logins) aus dem Kern heraushalten.
Der Kern bleibt reine Standardbibliothek; Plugins lassen sich ein-/ausschalten, eigene Plugins sind möglich.

## 2. Plugin-System

- **Fundorte:** eingebaut `plugins/`, eigene `~/TagStudio/Plugins` (ersetzen eingebaute mit gleicher id; gemeinsam für
  alle Profile).
- **Aufbau:** `plugin.json` (id, name, version, api, description, requires, install, external, notes, env, fields,
  background …) und `plugin.py` (`ACTIONS` oder `actions(ctx)`, `run(action, ctx, files, options)`, optional
  `status(ctx)`); geladen erst bei Bedarf, Fehler bleiben auf das Plugin beschränkt.
- **Context:** Fortschritt, Status, Abbruch, Protokoll (`Logs/<Plugin>.log`), `propose` (Vorschläge → Vorschau mit
  Häkchen → `plugin_apply` mit Undo), `edit_tags`, `data_dir` (je Profil), `shared_dir` (gemeinsam, grosse Daten).
- **Optionstypen:** select, check, text, number, folder, folders, info, password, textarea (mit `show_if`).
- **Umgebungen:** Plugins mit `env` bekommen eine eigene uv-Python-Umgebung (z. B. Stems mit Python 3.12).
- **Hintergrund:** Aktionen mit `"background": true` laufen als Auftrag (`jobs.py`, Warteschlange, Fortsetzen nach
  Neustart).
- **Nachladen und Aktualisieren (#235):** siehe Abschnitt „Plugins aus den Releases“ unten.

## 3. Eingebaute Plugins

| Plugin | Zweck |
|---|---|
| `stems` | Spuren trennen (audio-separator, CPU/DirectML/NVIDIA), im Hintergrund, Spuren unter dem Original |
| `beatport` | Metadaten mit eigenem Login (Token verschlüsselt), Käufe abgleichen, fehlende Käufe herunterladen (#117) |
| `online` | Online-Metadaten: gemeinsame Suche über die eingeschalteten Dienst-Plugins (Vorschau, Vorrang, Alternativen) |
| `musicbrainz`, `acoustid`, `deezer`, `itunes`, `discogs`, `lastfm` | Dienst-Plugins (#204): je ein Online-Dienst mit Kandidatensuche, Details, Verbindungstest, Testabfrage; Schlüssel (Discogs, Last.fm, AcoustID + fpcalc) verschlüsselt im eigenen Datenordner |
| `mik` | Werte aus Mixed-In-Key-Stellen übernehmen (Tonart, BPM, Energie) |
| `beatunes` | beaTunes-Stimmungswerte als Audio-Merkmale |
| `lexicon` | Lexicon Local API: übernehmen, öffnen, zurückschreiben (#146, #237–#239) |
| `loudness` | LUFS, True Peak, Lautheitsbereich, Clipping; angeglichene Kopie |
| `lyrics` | Liedtexte von LRCLIB (#183): `USLT`, `SYLT`, optional `.lrc` neben dem MP3 |

## 4. Umsetzung

- **Kern:** `plugins.py` (`Manager`, `Plugin`, `Context`, `OPTION_TYPES`, `API_VERSION`, `uv_command`, `shared_root`),
  `jobs.py`, `onlinematch.py`, `importsync.py`, `serato.py`.
- **Session:** `plugins_list`, `plugin_enable`, `plugin_actions`, `plugin_form`, `start_plugin_action`,
  `start_plugin_install`, `plugin_apply`, `jobs*`.
- **Oberfläche:** `web/plugins.js` (Seite, Formulare, Ergebnisdialog), `web/jobs.js` (Aufträge in der Fusszeile).
- **Einstellungen:** `plugins_enabled`, `plugin_options`, `plugin_settings`; Daten unter `Plugin-Daten/<id>` (siehe
  [KONZEPT-SPEICHER.md](KONZEPT-SPEICHER.md)).

### Liedtexte (`plugins/lyrics`, #183, Entscheide 16.10.2026)

- LRCLIB ohne Schlüssel; User-Agent mit Projektadresse, höchstens 2 Anfragen/s, nacheinander; 429/503 mit
  `Retry-After` über `onlinematch.Client`.
- Abfrage in drei Stufen, jede nur ohne Ergebnis der vorigen (#203): `/api/get` (Künstler, Titel mit und ohne Mix,
  Album, Dauer) nur mit Album und Dauer, 400/404 → weiter; `/api/search` mit Titel + erstem Künstler; Freitext
  `q = "Künstler Titel"`. LRCLIB kennt keine ISRC. Jede Stufe steht mit Trefferzahl im Protokoll, bei „nicht
  gefunden“ zusätzlich der beste Kandidat mit Prozent.
- Ausfälle (keine Verbindung, 429, 5xx nach den Wiederholungen von `onlinematch.Client`) zählen als „nicht abgefragt“,
  nicht als „nicht gefunden“; nach drei Ausfällen in Folge wird der Rest nicht mehr angefragt. Bewertung `version_score` = `onlinematch.score`, abweichende Fassung (Remix, Live,
  Acoustic …; Extended Mix/Radio Edit gelten als Original) −0,15 und höchstens „unsicher“.
- Vorschläge (Vorschau mit Häkchen): normaler Text → `USLT:` (Text aus LRC abgeleitet, falls nur dieser vorliegt),
  synchronisiert → `SYLT` (Rohframe: UTF-16 mit BOM, Zeitformat ms, Inhalt Liedtext), `TXXX:LRCLIB_ID`. Vorhandener
  Liedtext/SYLT/.lrc: nie vorausgewählt, Hinweis „nur mit Häkchen ersetzen“. Instrumental: kein Vorschlag.
- `.lrc`-Datei nur, wenn in Plugins › Liedtexte › „Einstellungen …“ eingeschaltet (`settings.json` im Datenordner,
  zusammen mit der Sprache ISO-639-2). Geschrieben beim Übernehmen (nicht beim Speichern), nur neben dem eigenen MP3
  mit gleichem Namen (`Session._sidecar_ok`). Neue Vorschlagsarten in `Context.propose`: `frame` und `file`.
- Liedtexte sind geschützt: nur eigener Gebrauch, nie ins Repository; Tests nutzen erfundene Texte und einen
  nachgebauten Dienst (`tests/test_lyrics.py`).

### Online-Dienste als Plugins (#204, Meilenstein 4.6.0)

- Jeder Online-Dienst (auch lokal über HTTP wie Lexicon) ist ein eigenes Plugin mit Abschnitt `"service"` in
  `plugin.json`: name, kind (online/local), home, docs, base, auth (none/key/token/oauth/local), auth_note, limits,
  terms, note und `endpoints` (id, method, path, label, status full/partial/none, use, note, params, test).
  `services.clean` prüft das (nur http(s)-Links, eindeutige IDs, ändernde Methoden nie im Tester).
- Karte: anklickbarer Link zur API-Doku; die Zahl der Endpunkte öffnet „Integration …“ (Endpunkt-Tabelle, Testabfrage
  ohne Track, API-Tester), ebenso „Weitere Funktionen …“.

### Plugin-Karte (Entscheid User 17.10.2026)

Über den Karten filtert eine Leiste nach Kategorie (Alle + je Kategorie mit Symbol und Anzahl, im Browser gemerkt).
Alle Karten gleich gross (Raster mit gleich hohen Zeilen), Aufbau von oben:
1. Titel, Version, „eingebaut“/„eigenes“; darunter die **Kategorie** (`plugin.json` `"category"`: `online` Online-API,
   `local_api` Lokale API, `import` Übernahme aus Tags, `audio` Audio-Verarbeitung, sonst `other` Sonstiges;
   ohne Angabe: Online-API bei Dienst-Plugins, sonst Sonstiges); rechts der Status über dem Schalter (Kopf springt nicht).
2. Beschreibung mit fester Höhe (4 Zeilen); passt sie nicht, klappt „mehr“ sie über der Karte auf – so liegen
   Aktionen, API-Zeile und Hinweise in allen Karten auf derselben Höhe.
3. Aktionen (erscheinen im Tagger).
4. API-Zeile (Link zur Doku · Anmeldung · Endpunkte) bzw. „API: keine – arbeitet lokal“.
5. Hinweise: Status des Plugins, wie Schlüssel/Token gespeichert werden, Umgebung, Warnungen (fehlende Pakete mit
   einem Knopf „Installieren …“ – Varianten und Hinweise im Fenster).
6. Vier gleich breite Funktionsknöpfe in einer Zeile, mit Symbol und kurzer Beschriftung (voller Name im Tooltip):
   **Testen** (Aktion `test`), **Schlüssel** bzw. **Anmelden** (`keys`/`login`), **Optionen** (`settings`),
   **Mehr …** (übrige Seiten-Aktionen, Integration, Neu installieren). Was fehlt, bleibt ausgegraut sichtbar.
  Plugins › „Integrationen …“: alle Dienste inkl. Update-Prüfung im Kern (`services.CORE`).
- Hooks im Plugin: `test_query(ctx, info)` → Kandidaten, Bewertung über `test_score`/`score`/`onlinematch.score`;
  `api_request(ctx, ep, params)` für eigene Anmeldung (Beatport-OAuth, Lexicon-Adresse), sonst `auth(ctx)` →
  Header/Parameter. Schlüssel werden eingesetzt, in URL und Antwort aber als „•••“ angezeigt.
- Gemeinsam: `servicekit.py` (Client mit `onlinematch.INTERVALS` und gemeinsamer Drosselung `onlinematch.SHARED`,
  Schlüsselablage je Plugin mit DPAPI, einmalige Übernahme aus `Plugin-Daten/online/keys.bin`).
- **OAuth mit PKCE** (#280, `oauthkit.py`): für Dienste mit eigener App des Users (Spotify, SoundCloud). Anmeldeseite
  im Browser, Rückleitung auf `http://127.0.0.1:<Port>/callback` nimmt ein kurzzeitiger lokaler Server an; sonst
  „Adresse einfügen“. Client-ID/Secret und Token in der Schlüsselablage des Plugins, Erneuerung vor Ablauf bzw. nach
  HTTP 401. Plugins mit `playlists(ctx)` dürfen in `playlist_files` statt Dateien `items` mit Einträgen ohne Datei
  (`ref`) liefern; Playlist-Quellen mit `ready(ctx)` erscheinen erst, wenn das Plugin bereit (angemeldet) ist.
- Nutzer der Dienste: `online` (Quellen-Häkchen nur für eingeschaltete Dienst-Plugins, sonst Hinweis; Optionsschlüssel
  wie bis 4.5), Entdecken (Deezer über `plugins/deezer`, Beatport über `plugins/beatport`; ausgeschaltet → Hinweis im
  Protokoll). Andere Plugins erreichen Dienste über `ctx.service(pid)` / `ctx.service_ctx(pid)`.
- Beispielwerte (#205): `service.example` (Testabfrage) und je Parameter `example` – echte Werte, die beim Dienst ein
  Resultat liefern (Daft Punk – One More Time, ISRC GBDUW0000053, passende IDs); `default` nur für feste Vorgaben wie
  `fmt=json`. Im Fenster „Felder löschen“ (feste Vorgaben bleiben) und „Beispiel einsetzen“. Der Online-Test
  (`TestExamples` in `tests/test_online_live.py`) prüft wöchentlich, dass alle Beispiele der frei nutzbaren Dienste
  ein Resultat liefern. Ausnahmen: Beatport (IDs nur angemeldet ermittelbar), Lexicon (eigene Bibliothek).
- API-Tester: generischer Abruf über `onlinematch.get_retry` (gemeinsame Drosselung `SHARED`, Wiederholung bei 429/503,
  Anzahl in `retries`, #212). IDs in der Antwort (Schlüssel `id`, `mbid`, `…_id`, `isrc`, `upc`, `discid`) sind
  anklickbar; vorgeschlagen werden Endpunkte mit passendem ID-Feld, sortiert nach dem umgebenden Objektnamen (#213).
- Die Update-Prüfung (GitHub Releases) bleibt im Kern.

### Plugins aus den Releases (#235, Entscheid User 17.10.2026)

Ziel: ein einzelnes Plugin aktualisieren (z. B. wenn ein Dienst seine Schnittstelle ändert) oder neue Plugins
installieren – ohne ganzes App-Release.

- **Katalog:** Der Release-Workflow (`installer.yml`, Job `release`) ruft `plugin_store.build` auf und legt je Plugin
  `plugin-<id>-<version>.zip` (Inhalt `<id>/…`, ohne Caches, reproduzierbar) und `plugins.json` (Format 1: id, name,
  version, category, description, `min_app`, env, requires, file, sha256, size) als Release-Assets ab.
- **Mindestversion:** `plugin.json` → `"min_app": "4.8.0"` (älteste TagStudio-Version, mit der das Plugin läuft; Betas
  zählen wie ihre Version). Ohne Angabe gilt die Version des Releases. Alle eingebauten Plugins tragen sie.
- **Plugin-Version erhöhen**, wenn sich ein Plugin ändert – sonst bietet der Katalog die Änderung nicht als Update an.
  `packaging/release.py --check` weist darauf hin (ab dem ersten Katalog-Release 4.8.0).
- **Kanal:** neuestes Release im gewählten Update-Kanal mit `plugins.json` („nur offizielle“ bzw. „auch Beta“), nie
  Entwicklungsstand; im Quellcode mit Kanal „Entwicklung“ kommen Plugins mit git.
- **Oberfläche:** Kopfzeile „Verfügbare Plugins …“ lädt den Katalog (Auftrag mit Fortschritt) und listet alle Plugins
  gruppiert (Updates, neu, installiert, nicht verträglich, eigenes) mit Kategoriefilter (#236); Karten mit neuerer Version zeigen „Update verfügbar“ mit „Aktualisieren“. Nachgeladene
  Plugins tragen das Abzeichen „nachgeladen“; unter „Mehr …“ „Zurück auf eingebaute Version“ bzw. „Nachgeladenes
  Plugin entfernen“ – mit Rückfrage.
- **Installation:** nach `~/TagStudio/Plugins/<id>` mit Markierung `.tagstudio-store.json` (Version, Prüfsumme, Tag);
  überlagert das eingebaute Plugin gleicher ID. Eigene Plugins (ohne Markierung) werden nie überschrieben oder
  entfernt. Einstellungen und Anmeldungen (`Plugin-Daten`) bleiben beim Aktualisieren und Zurücksetzen erhalten.
- **Sicherheit:** nur Adressen aus den Releases dieses Repos (HTTPS), SHA-256 aus dem Katalog muss mit dem
  GitHub-`digest` übereinstimmen und wird beim Laden geprüft (`updater.download_asset`), ZIP-Inhalt wird vor dem
  Entpacken geprüft (nur `<id>/…`, keine `..`, keine Links), `plugin.json` muss die erwartete ID haben; Austausch über
  Umbenennen (alte Version erst danach gelöscht).
- **Grenzen:** Die installierte App kann keine Python-Pakete nachinstallieren → Plugins mit `requires` werden mit Hinweis
  angezeigt; Plugins mit eigener Umgebung (`env`, wie Stems) funktionieren.
- **Umsetzung:** `plugin_store.py`; Session `start_plugin_catalog`, `start_plugin_store_install`, `plugin_store_revert`;
  `Plugin.info()` liefert `store`, `builtin_version`, `min_app`; `web/plugins.js` (`pluginStore*`, `plStoreBox`).

### Lexicon-Ausbau (#237–#239, Entscheid User 17.10.2026: alle drei in 4.8.0)

Grundlage: offizielle OpenAPI-Beschreibung der Lexicon Local API 1.0.0 (27 Endpunkte). Client
`plugins/lexicon/lexapi.py` (Abfrage-Kodierung wie in der Beschreibung, Fehlercode 2 → kurz warten und wiederholen,
nie über einen Proxy, `is_local`).

- **#237 Übernehmen:** bis 150 Dateien gezielt `/search/tracks` mit `filter[location]` (sonst einmal die Bibliothek mit
  `fields`), neu Bewertung (`kind="rating"`), Popularität, Farbe, Tags aller Kategorien; Beatgrid (`tempomarkers`) über
  `gridstatus.compare(…, "Lexicon", "Serato"|"Analyse")` und Cue-Punkte nur als Hinweis; Status Incoming/analysiert.
- **#238 Öffnen:** markierte Titel (`/tracks/selected`), markierte Playlist bzw. Name/Pfad (Baum aus `/playlists`,
  Inhalt `/playlist` – Ordner und Smartlists liefert Lexicon mit) → Ergebnis `open` → `start_tag_load_files` bzw.
  `dj_add_paths`. Vorbereiten: `detect_files` für Status-Schritte (Rahmen `Manager.detect`).
- **#239 Zurückschreiben:** Hauptschalter + Unterschalter in den Einstellungen (Standard aus), nur an localhost.
  Rahmen `Manager.emit` mit `on_event` (`files_moved` aus Umbenennen/Archiv/Zurückholen, `files_added` aus
  Vorbereiten › Übernahme), Vorschau `kind="remote"` → `apply_remote`. Pfade (`PATCH /track/location`), neue Titel
  (`POST /tracks`, Playlist, `AudioAnalyzer_Analyze`), Tags (`PATCH /track`), Mood-Tags (`POST /tag`), DJ-Set als
  Playlist. Journal `Plugin-Daten/lexicon/journal.json`; „Rückgängig“ setzt Werte und Pfade zurück. **Nie** löschen
  (keine DELETE-Endpunkte), keine Oberflächen-/Player-Steuerung über `/control`.
- **#240 Felder (Entscheid User 17.10.2026):** Alles aus Lexicon ohne offizielles MP3-Feld kommt in eigene Felder
  `TXXX:LEXICON_*` (DANCEABILITY, ENERGY, HAPPINESS, POPULARITY, COLOR, TAGS, MOOD bei ID3v2.3), Werte wie in Lexicon
  (1–10). Herkunft „Lexicon“ über die vorhandene Regel `TXXX:Lexicon*` (kein `fields` in plugin.json). Offizielle
  Felder: POPM, TMOO (v2.4), TIT1/COMM auf Wunsch. Die TagStudio-Felder (ENERGY usw.) fasst „Lexicon übernehmen“
  nicht an – optionale Übernahme in eigene Felder folgt als eigene Funktion.
- **#241 In TagStudio-Felder:** Aktion „Lexicon-Werte in TagStudio-Felder …“ (offline aus `TXXX:LEXICON_*`, ×10,
  `importsync`-Abgleich, Stimmung) bzw. Option `to_ts` bei „Lexicon übernehmen“.
- **#242 DJ-Set:** Rahmen `Manager.playlist_sources/call_playlist` (Plugin-Funktionen `playlists`, `playlist_files`),
  Session `dj_sources`, `start_dj_source_list`, `start_dj_source_import` (Listen „<Quelle>: <Name>“, erste geladen);
  Pseudo-Playlist „Warteschlange“ aus `/playing` + `/queue` (#238 Punkt 4).
- **#273 Senden:** Plugin-Funktion `playlist_push(ctx, playlist, options)` und optional `push_ready(ctx)`;
  `Manager.push_targets()`, Session `start_pl_push` (Ziel-ID je Playlist in `pushed`). Lexicon 2.2: anlegen bzw.
  fehlende Titel einfügen, nie löschen. Details `docs/KONZEPT-PLAYLISTS.md` Abschnitt 19.

### API-Rekorder (#243, Entscheid User 17.10.2026)

Entwicklerwerkzeug `tools/api_recorder.py` (Playwright, nicht in der App): liest beim Durchklicken einer Website die
JSON-Aufrufe passiv mit (keine eigenen Anfragen), schwärzt Zugangsdaten und persönliche Angaben, erzeugt
`recording.json` und einen `"service"`-Entwurf (Pfadmuster, Parameter, Antwortfelder), der direkt in `services.clean`
passt. Einsatz nur für erlaubte Schnittstellen; für MixID zuerst Anfrage (#218).

### Tonart mit OpenKeyScan (#217, #244, #245, Entscheid User 24.10.2026: wie vorgeschlagen, B vor A)

Zwei Plugins, ein gemeinsamer Kern `keyscan.py` (Zwischenspeicher je Datei mit Grösse + Änderungszeit, Vergleich mit
TKEY / `TXXX:INITIAL_KEY` / MIK-Kommentar, Vorschläge). Ergebnis nie direkt: `TXXX:OPENKEYSCAN_KEY` (Camelot `09A`,
Herkunft „OpenKeyScan“, Builtin-Regel `TXXX:OPENKEYSCAN*`) und optional `TKEY` in der eingestellten Schreibweise –
nur angehakt, wenn TKEY leer ist.

- **`keyscan` (#245):** eigene uv-Umgebung (Python 3.12, `torch`, `librosa<1.0`, `av`), Varianten CPU (Index
  `whl/cpu`) und NVIDIA (`whl/cu128`). Neu im Rahmen: **`env.files`** – Zusatzdateien nur von GitHub, fester Commit,
  SHA-256 Pflicht (`plugins.clean_env_files`, `fetch_file`); fehlt eine, ist das Plugin „missing“ („Daten: …“).
  `model.py` und `openkeyscan3.pt` von `rekordcloud/openkeyscan-analyzer@d5cac64` (nicht im Repo, nicht im Release).
  `worker.py` rechnet wie die Engine (PyAV/librosa → CQT 105 Bänder, 24/Oktave, fmin 65, hop 8820 → KeyNet, Klasse
  0–11 = 1A–12A, 12–23 = 1B–12B) und meldet zusätzlich die Softmax-Sicherheit. Aktionen `scan` (Vordergrund,
  Vorschau) und `prefetch` (Hintergrund, nur Zwischenspeicher – Hintergrund-Aufträge können keine Vorschläge zeigen).
  Echter Test in GitHub Actions: `packaging/ci_keyscan_test.py`, Workflow „Tonart-Test“ (synthetische Titel).
- **`openkeyscan` (#244):** Dienst-Plugin (`kind: local`, Port 58721), nur localhost, ohne Proxy. ≤ 20 Titel
  `/analyze/single`, sonst `/analyze/add` (≤ 1000 je Aufruf) und Abfragen von `/analyze/results` (alle 2 s, Abbruch
  nach 5 min ohne Fortschritt; leer → `/analyze/result?file=`). Antwortformate tolerant gelesen (nicht dokumentiert).
  `/analyze/clear` nie. Auto-Tagging der App wird über geänderte Änderungszeiten erkannt und gemeldet.

- **Protokolle (#293):** „Mehr …“ jedes Plugins: „Log-Ordner öffnen“ (`plugin_log_folder`, markiert `<id>.log`) und
  „Protokoll live anzeigen …“ (`web/log-window.html`, `web/logwin.js`; in der App `log_window_open` = eigenes
  pywebview-Fenster je Plugin, im Browser Popup mit Token). Das Fenster liest jede Sekunde `plugin_log_read(pid, name,
  offset, seq)` → nur neue Bytes (Datei kleiner → von vorne, erstes Mal die letzten 200 KB) plus Live-Zeilen:
  `Context.log` legt jede Zeile zusätzlich in einen Ringpuffer je Plugin (`plugins.live_push`, 2000 Zeilen,
  Nummer + Zeit). Angezeigt werden Live-Zeilen, die jünger sind als die letzte Änderung von `<id>.log` – sobald der
  Vorgang am Ende in die Datei schreibt, ersetzt die Datei sie. Nur Dateien `<id>.log` / `<id>-*.log` im Log-Ordner.

## 5. Entscheide

- Zugangsdaten nie im Klartext: Passwörter werden nicht gespeichert, Tokens/Schlüssel nur verschlüsselt, nie
  protokolliert oder exportiert.
- Inoffizieller Beatport-Zugriff mit eigenem Login ist akzeptiert.
- Profile teilen Plugin-Programme und grosse Daten (Stems-Umgebung, Modelle, FFmpeg), nicht aber Einstellungen und
  Anmeldungen.

## 6. Offen / Ideen

- #117 Beatport-Download: Download-Endpunkt gegen die echte API noch ungetestet.
- #9 Audio-Analyse-Plugin (librosa, Essentia/ONNX), #108 Sammlung weiterer Plugin-Ideen.

## 7. Tests

`tests/test_plugins.py`, `test_plugin_store.py` (#235), `test_lexicon.py` + `fake_lexicon.py` (#237–#239), `test_services.py`, `test_jobs.py`, `test_beatport.py`, `test_beatport_purchases.py`, `test_online.py`
(`test_online_live.py` nur im Workflow), `test_mik.py`, `test_importers.py`, `test_loudness.py`, `test_serato.py`;
Stems-Test im Workflow „Stems-Test“.
