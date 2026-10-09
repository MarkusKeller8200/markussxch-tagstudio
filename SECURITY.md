# Sicherheit / Security Policy

## Unterstützte Versionen / Supported versions

Sicherheitskorrekturen gibt es für die jeweils **neueste Version**. Ältere Versionen werden nicht nachgebessert –
bitte auf die aktuelle Version aktualisieren (Installer unter
[Releases](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases) oder Update-Knopf in der App).

Security fixes are provided for the **latest release** only.

| Version | Unterstützt / Supported |
| ------- | ----------------------- |
| 3.3.x   | :white_check_mark:      |
| < 3.3   | :x:                     |

## Sicherheitslücke melden / Reporting a vulnerability

Bitte **kein öffentliches Issue** für Sicherheitslücken anlegen.
Please do **not** open a public issue for security problems.

1. Auf GitHub im Repository **Security → Report a vulnerability** öffnen
   (privater Bericht, nur für den Betreuer sichtbar).
2. Beschreiben: betroffene Version und Betriebssystem, Schritte zum Nachstellen, mögliche Auswirkung;
   wenn vorhanden ein Beispiel (z. B. eine präparierte MP3-Datei oder ein Plugin).

Use **Security → Report a vulnerability** in this repository (private report).

### Was dich erwartet / What to expect

- Eingangsbestätigung innerhalb von **7 Tagen** (Freizeitprojekt).
- Einschätzung und – wenn bestätigt – Korrektur in der nächsten Version, je nach Schwere als Bugfix-Version
  (z. B. 3.1.1). Die Lücke wird im CHANGELOG und im Release beschrieben, wenn die Korrektur verfügbar ist;
  auf Wunsch mit Nennung des Meldenden.
- Wird die Meldung abgelehnt (z. B. kein Sicherheitsproblem oder ausserhalb des Projekts), gibt es eine Begründung.

Acknowledgement within 7 days; confirmed issues are fixed in the next release and disclosed in the changelog.

## Geltungsbereich / Scope

Im Geltungsbereich: der Code in diesem Repository (TagStudio, eingebaute Plugins, Installer und Workflows).

Nicht im Geltungsbereich:
- **Plugins von Dritten** – Plugins laufen mit den Rechten der App; installiere nur Plugins, denen du vertraust.
- Externe Dienste (z. B. Beatport-API) und von Plugins nachinstallierte Pakete (z. B. audio-separator, PyTorch).
- Warnungen von Windows SmartScreen bzw. macOS Gatekeeper wegen fehlender Signatur (bekannt, siehe README).

## Hinweise zum Umgang mit Daten / Data handling

- Zugangsdaten (z. B. Beatport) werden nicht gespeichert; Tokens liegen nur lokal im Benutzerordner,
  unter Windows mit DPAPI verschlüsselt.
- TagStudio sendet keine Daten an Dritte; Netzwerkzugriffe gibt es nur bei Update-Prüfung und Plugins.
