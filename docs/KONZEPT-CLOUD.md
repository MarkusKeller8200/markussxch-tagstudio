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

## 5. Offen (bei der Umsetzung prüfen)

- Genaue Endpunkte und Kontingente (Microsoft Graph, Google Drive API v3, Dropbox API v2) aus den offiziellen
  Dokumentationen nachtragen.
- OneDrive geschäftlich: braucht die App-Registrierung in Entra ID die Zustimmung des Administrators?
