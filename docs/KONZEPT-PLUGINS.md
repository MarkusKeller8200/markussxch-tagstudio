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

## 3. Eingebaute Plugins

| Plugin | Zweck |
|---|---|
| `stems` | Spuren trennen (audio-separator, CPU/DirectML/NVIDIA), im Hintergrund, Spuren unter dem Original |
| `beatport` | Metadaten mit eigenem Login (Token verschlüsselt), Käufe abgleichen, fehlende Käufe herunterladen (#117) |
| `online` | Online-Metadaten: gemeinsame Suche über die eingeschalteten Dienst-Plugins (Vorschau, Vorrang, Alternativen) |
| `musicbrainz`, `acoustid`, `deezer`, `itunes`, `discogs`, `lastfm` | Dienst-Plugins (#204): je ein Online-Dienst mit Kandidatensuche, Details, Verbindungstest, Testabfrage; Schlüssel (Discogs, Last.fm, AcoustID + fpcalc) verschlüsselt im eigenen Datenordner |
| `mik` | Werte aus Mixed-In-Key-Stellen übernehmen (Tonart, BPM, Energie) |
| `beatunes` | beaTunes-Stimmungswerte als Audio-Merkmale |
| `lexicon` | Werte über die Lexicon Local API |
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
- Karte: anklickbarer Link zur API-Doku, „Integration …“ (Endpunkt-Tabelle, Testabfrage ohne Track, API-Tester).
  Plugins › „Integrationen …“: alle Dienste inkl. Update-Prüfung im Kern (`services.CORE`).
- Hooks im Plugin: `test_query(ctx, info)` → Kandidaten, Bewertung über `test_score`/`score`/`onlinematch.score`;
  `api_request(ctx, ep, params)` für eigene Anmeldung (Beatport-OAuth, Lexicon-Adresse), sonst `auth(ctx)` →
  Header/Parameter. Schlüssel werden eingesetzt, in URL und Antwort aber als „•••“ angezeigt.
- Gemeinsam: `servicekit.py` (Client mit `onlinematch.INTERVALS` und gemeinsamer Drosselung `onlinematch.SHARED`,
  Schlüsselablage je Plugin mit DPAPI, einmalige Übernahme aus `Plugin-Daten/online/keys.bin`).
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

`tests/test_plugins.py`, `test_services.py`, `test_jobs.py`, `test_beatport.py`, `test_beatport_purchases.py`, `test_online.py`
(`test_online_live.py` nur im Workflow), `test_mik.py`, `test_importers.py`, `test_loudness.py`, `test_serato.py`;
Stems-Test im Workflow „Stems-Test“.
