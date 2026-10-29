# Konzept: Cloud-Abgleich über die Dienste (Weg 2) – OneDrive, Google Drive, Dropbox

Status: **ENTSCHIEDEN** (Entscheide C1–C4 vom User 25.10.2026, 16:54) – Umsetzung in 4.11.0 (Meilenstein #27), Issues
#309 (Sammel-Issue) und #317–#320. Weg 1 (Sync-Ordner der Desktop-Clients, `cloud.py`) ist mit 4.10.0 umgesetzt, siehe
[KONZEPT-ORDNER.md](KONZEPT-ORDNER.md) Abschnitt 9.

## 1. Ziel

TagStudio gleicht ausgewählte Ordner-Rollen und Programmdaten **direkt über die API** der Dienste ab – ohne
Desktop-Client, z. B. auf einen zweiten Rechner (Windows ↔ Mac). Musik bleibt beim Desktop-Client (Weg 1).

## 2. Entscheide (User 25.10.2026, 16:54)

| ID | Frage | Entscheid |
|---|---|---|
| C1 | Welche Anbieter? | **Alle drei:** OneDrive (privat und geschäftlich), Google Drive, Dropbox – je ein Plugin. |
| C2 | Was wird abgeglichen? | Rollen **Playlists** und **Export**, dazu Programmdaten-Teile: Playlists-Speicher, Käufe, Entdecken, Einstellungen **ohne Zugangsdaten**. Musik nur über den Desktop-Client (Weg 1). |
| C3 | Richtung und Konflikte | **Beide Richtungen.** Bei gleichzeitiger Änderung auf zwei Rechnern **fragt TagStudio nach** (beide Fassungen zeigen) – nie still überschreiben. |
| C4 | Zugang | **Eigene App je Dienst** (Client-ID), die der User im Plugin einträgt – wie Spotify/SoundCloud (OAuth mit PKCE, `oauthkit.py`). TagStudio liefert keine Client-ID mit. |

## 3. Aufbau

- **Rahmen im Kern (#317):** Plugin-Fähigkeit `cloud_sync` (`list`, `get`, `put`, `delta` je Dienst), Feld `sync` je
  Rolle im Ordner-Modell (`{"provider", "remote", "mode": "both|up|down"}`, schon in `folders.normalize` vorgesehen),
  Abgleich-Auftrag mit Zustand je Datei (Hash/ETag der letzten gemeinsamen Fassung) → erkennt „nur hier geändert“,
  „nur dort geändert“, „beide geändert“ (Konflikt → Dialog). Schreiben immer atomar (`.part`). Löschen nie
  automatisch: entfernte Dateien werden gemeldet und erst nach Rückfrage gelöscht.
- **Plugins (#318 OneDrive, #319 Google Drive, #320 Dropbox):** OAuth über `oauthkit` (Rückleitung 127.0.0.1),
  Token verschlüsselt (`secretstore`/`servicekit.save_keys`), Integrationsfenster mit Endpunkt-Tabelle wie bei den
  Dienst-Plugins, Kontingente/429 melden. Ordner im Dienst standardmässig `/TagStudio/<Rolle>`.
- **Oberfläche:** Einstellungen › Ordner zeigt je Rolle „☁ Abgleich: OneDrive“ mit Knopf „Jetzt abgleichen“ und
  Stand (zuletzt, Anzahl, Konflikte); Programmdaten-Teile als eigene Zeilen.

## 4. Grundsätze

- Zugangsdaten nie abgleichen, nie protokollieren, nie exportieren (Einstellungen-Export ohne Zugangsdaten wie bisher).
- Snapshot-Speicher, Arbeit, Cache und Plugin-Umgebungen **nie** über die Dienste (wie Weg 1).
- Nur Dateien, die TagStudio selbst schreibt; fremde Dateien im Zielordner bleiben unberührt.
- Keine Kosten: nur die Gratis-API-Kontingente der Dienste; bei Grenzen melden statt wiederholen.

## 4a. Umsetzung Rahmen (#317, 25.10.2026)

- **`cloudsync.py`** (Kern, nur Standardbibliothek): Teile `FolderPart` (Ordner rekursiv, erlaubte Endungen –
  Playlists: m3u8/m3u/xml/csv/txt/json, Export: alle; ohne versteckte, `.part`/`.tmp` und Konfliktkopien der
  Desktop-Clients), `DiscoverPart` (SonoVault-Einträge nie hochladen, beim Herunterladen die hiesigen behalten),
  `SettingsPart` (eine Datei `einstellungen.json` aus `appsettings.shareable`, nur Gruppen ohne Pfade/Fenster:
  Design, Ansicht, Unwichtige, DJ-Set, Herkunft, Plugins, Updates; Übernahme über `appsettings.import_apply` mit
  Sicherung). `plan` ordnet je Datei zu: hochladen, herunterladen, prüfen (beide da, kein Zustand → Inhalt vergleichen),
  Konflikt, im Dienst bzw. hier gelöscht (nur melden). Modus `up`/`down` lässt die andere Richtung aus.
- **Zustand** `~/TagStudio/Cloud/abgleich.json`: je Ziel (`Teil|Dienst|Ordner`) und Datei SHA-256 + Revision, dazu
  `_last` (Zeitpunkt, ↑, ↓, Konflikte, offene Löschungen, Fehler). Herunterladen atomar (`.part` → ersetzen).
- **Einstellung:** Rollen über `folders` › `roles.<id>.sync` (`{"provider", "remote", "mode"}`), Programmdaten-Teile
  in `cloud_sync_app`. Standard-Ordner im Dienst `TagStudio/<Rolle>` bzw. `TagStudio/Programmdaten/<Teil>`.
- **Session** (`session_cloud.py`): `cloud_sync_overview`, `cloud_sync_set`, `start_cloud_sync` (Auftrag; Konflikte und
  Löschungen in eine Liste), `cloud_pending` (Vorschau beider Fassungen), `cloud_resolve` (hier / dort / beide –
  „beide“ legt die Fassung aus dem Dienst als „Name (Cloud).ext“ daneben), `cloud_gone` (löschen nach Rückfrage in
  der Oberfläche bzw. „nicht löschen“ = Stand vergessen, beim nächsten Abgleich wieder übertragen). Nach dem
  Herunterladen werden Playlists-/Käufe-Speicher und Einstellungen der Sitzung neu geladen.
- **Gegenstelle:** Plugins mit `cloud_list/get/put/delete` (siehe PLUGINS.md, Abschnitt „Cloud-Abgleich“).
- **Oberfläche** (`web/cloudsync.js`): Abschnitt „Abgleich über die Dienste“ in der Karte Einstellungen › Cloud (#324, eigene Karte mit Sync-Ordnern; Tabelle Bereich · Dienst · Richtung · Ordner im Dienst) –
  je Zeile Dienst (nur angemeldete wählbar), Richtung, Ordner im Dienst, Stand; „Jetzt abgleichen“; Dialog „Abgleich –
  bitte entscheiden“.
- **Grenzen:** Playlists-Speicher enthält absolute Pfade der Titel – zwischen Windows und Mac passen sie nur, wenn die
  Musik gleich liegt (Weg 1, relativ zum Sync-Ordner). Eine heruntergeladene M3U8 im Playlist-Ordner meldet der
  Playlists-Speicher wie jede fremde Änderung.

## 4b. Umsetzung Plugins (#318–#320, 25.10.2026)

Gemeinsam: `cloudkit.py` (Anfragen mit Token, einmal erneuern bei 401, **429 nie wiederholen**, verständliche Fehler,
Aktionen „Anmelden … / Abmelden … / Verbindung testen“), `oauthkit` mit `auth_params`, `onlinematch.http_request`
(PUT/PATCH/DELETE, in Tests ersetzbar).

| Dienst | Anmeldung | Endpunkte | Grenzen (offizielle Doku) |
|---|---|---|---|
| OneDrive (Plugin `onedrive`) | Entra-App, öffentlicher Client, PKCE, `http://localhost/callback` (Port egal), Scopes `Files.ReadWrite User.Read offline_access` | `GET /me/drive`, `…/root:/{pfad}:/children`, `…:/content` (GET/PUT ≤ 4 MB), `…:/createUploadSession`, `DELETE …/root:/{pfad}` | Drosselung mit 429/Retry-After; einfacher Upload laut Graph bis 250 MB (TagStudio: Sitzung ab 4 MB) |
| Google Drive (`gdrive`) | Desktop-App mit Client-ID + Secret, PKCE, `access_type=offline`, `prompt=consent`, Scope `drive.file` | `GET /about`, `GET /files?q=…`, `POST /files` (Ordner), `GET /files/{id}?alt=media`, `POST /upload/…?uploadType=multipart`, `PATCH /upload/…/{id}?uploadType=media`, `PATCH /files/{id}` (trashed) | 325 000 Einheiten/Minute/Benutzer, 1 000 000/Minute/Projekt; Liste 100, Download 200, Ändern 50 Einheiten; 403/429 |
| Dropbox (`dropbox`) | App-Key, PKCE, `token_access_type=offline`, Redirect `http://127.0.0.1:8769/callback` | `users/get_current_account`, `users/get_space_usage`, `files/list_folder` (+`/continue`), `files/download`, `files/upload` (overwrite), `files/delete_v2` | nicht veröffentlicht, 429 |

**OneDrive geschäftlich (offener Punkt aus Abschnitt 5):** `Files.ReadWrite` (delegiert) hat laut Microsoft Graph
„AdminConsentRequired: No“. Eine Organisation kann die Zustimmung durch Benutzer aber sperren – dann meldet die Anmeldung
das (AADSTS65001/90094) und TagStudio nennt den Weg über die Administratorzustimmung.

## 4c. Entscheid 29.10.2026 (17:58) – OneDrive nach Kontoart (#405, geplant für 4.14.0)

- Plugin `onedrive` bleibt (eigene App, API-Abgleich), neu mit **Umschalter Kontoart**:
  - **Geschäfts-/Schulkonto:** App-Anbindung über Microsoft Graph wie bisher, Endpunkt `organizations`.
  - **Privates OneDrive:** keine App, keine Anmeldung – nur der angegebene **OneDrive-Ordner** des Desktop-Clients:
    Spiegel der Bibliothek als Einweg-Kopie (#403) und Sicherung der Programmdaten (#402).
  - Vorausgewählt ist immer „Privat“ (Entscheid User 29.10.2026 20:13, #412, OneDrive 1.3).
- Abo und Speichergrösse entscheidet der Benutzer; TagStudio zeigt eine **Schätzung des benötigten Platzes**.
- Sicherheitsfehler #401 (Token bei Umleitungen) wird behoben. Einfache Anmeldung mit TagStudio-App (#400) und
  [KONZEPT-ONEDRIVE.md](KONZEPT-ONEDRIVE.md) nicht weiter verfolgt; Web-Player #404 bleibt Idee.

### Umsetzung Spiegel (#403, 29.10.2026)

- `mirror.py` (Kern, nur Standardbibliothek): `plan` (je Bibliothek `<Ziel>/<Name>/…`, Audio-Endungen, Vergleich
  Grösse + Änderungszeit ±2 s, überzählige Dateien), `run` (`.part` → `os.replace`, Zeit übernommen), `estimate`,
  `free_space`, `delete_extra` (nur Audio unterhalb des Ziels), `set_online_only` (Windows `attrib +u -p`; macOS nur
  Hinweis – **ZU PRÜFEN** beim User, ob OneDrive neue Dateien danach freigibt), `write_index` (`index.json`, Format 1,
  übernimmt unveränderte Einträge), `write_playlists` (`<Ziel>/Playlists/<Ordner>/<Name>.m3u8`, relative Pfade mit „/“).
- `session_mirror.py` (MirrorMixin): cfg `mirror` {folder, libraries [] = alle aktiven, auto, playlists, online_only},
  `mirror_last`; `mirror_overview/set/estimate`, `start_mirror` (Auftrag), `mirror_extra`, `mirror_delete_extra` (nur
  Pfade aus dem letzten Lauf), `_mirror_touch` (nach `start_save` und Vorbereiten-Übernahme, Hintergrund-Faden, nur mit
  „automatisch“). Vorschlag für das Ziel: `cloud_folder(ctx)` der Plugins (OneDrive privat) + `TagStudio-Spiegel`.
- Oberfläche `web/mirror.js` (Abschnitt `#stMirror` in Einstellungen › Cloud).

### Umsetzung Sicherung der Programmdaten (#402, 29.10.2026)

- `appbackup.py`: Teile settings (`appsettings.export_text`, ohne Zugangsdaten), playlists (`Playlists/*.json|.m3u8`),
  purchases (`Käufe`), discover (`cloudsync.DiscoverPart` – ohne SonoVault), prepare (`Vorbereiten`), mixes (`Mixe`).
  ZIP `TagStudio-Programmdaten_<Rechner>_<JJJJ-MM-TT_HHMMSS>[_Notiz][-n].zip` mit `manifest.json` (Format
  `tagstudio-appbackup` 1, Version, Rechner, Plattform, Profil, Bibliotheken, SHA-256 je Datei); `.part` → umbenennen.
  `read` prüft Format, Grösse (≤ 512 MB) und Prüfsummen; `preview` (ersetzt/neu/gleich/nur hier, Einstellungsgruppen über
  `appsettings.import_preview`), `path_mapper` (Bibliotheken gleicher ID bzw. gleichen Namens, Trennzeichen egal),
  `restore_files` (atomar, Dateien „nur hier“ bleiben), `surplus`/`delete` (nur eigene ZIPs im Ordner).
- `session_appbackup.py`: cfg `app_backup` {folder, auto off|exit|daily, keep}, `app_backup_last`; `start_appbackup`,
  `appbackup_surplus/delete`, `appbackup_preview`, `start_appbackup_restore` (zuerst Sicherung „vor-Wiederherstellen“,
  dann Dateien, Einstellungen, `_folders_relink(rb=…)`); `appbackup_exit` (Api `_exit_backup`, höchstens 30 s),
  `appbackup_daily` (aus `plugins_startup`). Vorschlag: Cloud-Ordner eines Plugins + `TagStudio/Sicherungen`.
- Oberfläche `web/appbackup.js` (Abschnitt `#stAppBackup` in Einstellungen › Cloud).

## 5. Offen (bei der Umsetzung prüfen)

- **OneDrive nur privat, einfache Anmeldung, App-Ordner:** Entwurf in [KONZEPT-ONEDRIVE.md](KONZEPT-ONEDRIVE.md)
  (29.10.2026, nicht weiter verfolgt – Entscheid User 17:35; stattdessen #402 Sicherung in den Cloud-Ordner;
  Sicherheitsfehler Token bei Umleitungen #401).

- Genaue Endpunkte und Kontingente (Microsoft Graph, Google Drive API v3, Dropbox API v2) aus den offiziellen
  Dokumentationen nachtragen.
- OneDrive geschäftlich: braucht die App-Registrierung in Entra ID die Zustimmung des Administrators?
