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
- **Oberfläche** (`web/cloudsync.js`): Abschnitt „Abgleich über die Dienste“ in Einstellungen › Speicherort und Ordner –
  je Zeile Dienst (nur angemeldete wählbar), Richtung, Ordner im Dienst, Stand; „Jetzt abgleichen“; Dialog „Abgleich –
  bitte entscheiden“.
- **Grenzen:** Playlists-Speicher enthält absolute Pfade der Titel – zwischen Windows und Mac passen sie nur, wenn die
  Musik gleich liegt (Weg 1, relativ zum Sync-Ordner). Eine heruntergeladene M3U8 im Playlist-Ordner meldet der
  Playlists-Speicher wie jede fremde Änderung.

## 5. Offen (bei der Umsetzung prüfen)

- Genaue Endpunkte und Kontingente (Microsoft Graph, Google Drive API v3, Dropbox API v2) aus den offiziellen
  Dokumentationen nachtragen.
- OneDrive geschäftlich: braucht die App-Registrierung in Entra ID die Zustimmung des Administrators?
