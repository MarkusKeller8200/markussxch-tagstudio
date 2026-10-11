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
| `online` | Online-Metadaten: MusicBrainz/AcoustID, Deezer, iTunes, Discogs, Last.fm |
| `mik` | Werte aus Mixed-In-Key-Stellen übernehmen (Tonart, BPM, Energie) |
| `beatunes` | beaTunes-Stimmungswerte als Audio-Merkmale |
| `lexicon` | Werte über die Lexicon Local API |
| `loudness` | LUFS, True Peak, Lautheitsbereich, Clipping; angeglichene Kopie |

## 4. Umsetzung

- **Kern:** `plugins.py` (`Manager`, `Plugin`, `Context`, `OPTION_TYPES`, `API_VERSION`, `uv_command`, `shared_root`),
  `jobs.py`, `onlinematch.py`, `importsync.py`, `serato.py`.
- **Session:** `plugins_list`, `plugin_enable`, `plugin_actions`, `plugin_form`, `start_plugin_action`,
  `start_plugin_install`, `plugin_apply`, `jobs*`.
- **Oberfläche:** `web/plugins.js` (Seite, Formulare, Ergebnisdialog), `web/jobs.js` (Aufträge in der Fusszeile).
- **Einstellungen:** `plugins_enabled`, `plugin_options`, `plugin_settings`; Daten unter `Plugin-Daten/<id>` (siehe
  [KONZEPT-SPEICHER.md](KONZEPT-SPEICHER.md)).

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

`tests/test_plugins.py`, `test_jobs.py`, `test_beatport.py`, `test_beatport_purchases.py`, `test_online.py`
(`test_online_live.py` nur im Workflow), `test_mik.py`, `test_importers.py`, `test_loudness.py`, `test_serato.py`;
Stems-Test im Workflow „Stems-Test“.
