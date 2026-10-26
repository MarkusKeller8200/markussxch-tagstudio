<p align="center">
  <img src="web/icon.png" width="96" height="96" alt="">
</p>

<h1 align="center">MarKusSXCH TagStudio</h1>

<p align="center">
  <b>Der Werkzeugkasten für die MP3-Bibliothek von DJs</b><br>
  Taggen, vergleichen, aufräumen, Einkäufe abgleichen und Sets planen – für Windows und macOS.
</p>

<p align="center">
  <a href="https://markuskeller8200.github.io/markussxch-tagstudio/"><img alt="Downloads" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FMarkusKeller8200%2Fmarkussxch-tagstudio%2Fstats%2Fdocs%2Fbadge.json"></a>
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest"><img alt="Neueste Version" src="https://img.shields.io/github/v/release/MarkusKeller8200/markussxch-tagstudio?label=Version"></a>
  <img alt="Windows und macOS" src="https://img.shields.io/badge/Windows%20%7C%20macOS-555">
  <a href="LICENSE"><img alt="Lizenz GPL-3.0" src="https://img.shields.io/badge/Lizenz-GPL--3.0-555"></a>
</p>

<p align="center">
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest"><img alt="Download für Windows" src="https://img.shields.io/badge/Download-Windows-1D76DB?style=for-the-badge&logo=windows11&logoColor=white"></a>
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest"><img alt="Download für macOS" src="https://img.shields.io/badge/Download-macOS%20(Apple--Chip)-1D76DB?style=for-the-badge&logo=apple&logoColor=white"></a>
  <a href="docs/HANDBUCH.md"><img alt="Handbuch" src="https://img.shields.io/badge/Handbuch-lesen-6E7781?style=for-the-badge&logo=readthedocs&logoColor=white"></a>
</p>

<p align="center">
  <a href="docs/HANDBUCH.md">Handbuch</a> ·
  <a href="CHANGELOG.md">Änderungen</a> ·
  <a href="PLUGINS.md">Plugins</a> ·
  <a href="https://markuskeller8200.github.io/markussxch-tagstudio/">Webseite</a> ·
  <a href="https://markuskeller8200.github.io/markussxch-tagstudio/statistik.html">Download-Statistik</a> ·
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/issues">Fehler &amp; Ideen</a> ·
  <a href="README.en.md">English</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/tagger-dark.png">
  <img alt="Tagger: viele Dateien gemeinsam bearbeiten, Tonart, BPM, Genre auf einen Blick" src="docs/screenshots/tagger-light.png">
</picture>

## Was TagStudio kann

| | | |
|---|---|---|
| 🏷️ **Tagger**<br>Viele Dateien gemeinsam bearbeiten, Cover, Tags aus dem Dateinamen, Umbenennen, Suchen & Ersetzen, Export nach Excel/CSV. | ⚖️ **Vergleich**<br>Zwei Ordner oder Dateien Feld für Feld – zeichengenau markiert, Werte per Pfeil übernehmen. | 🧹 **Tag-Fixer**<br>Mehrfachwerte (`;` `/` `feat.` …) vereinheitlichen, Smart-Fix-Rezepte, Ausnahmen je Feld. |
| 🛒 **Einkäufe**<br>Gekaufte Titel (Beatport) mit der Bibliothek abgleichen, fehlende laden, Playlists in Beatport anlegen. | 🎛️ **DJ-Set**<br>Reihenfolge nach Tonart (Camelot), BPM und Energie optimieren – Export als M3U8, Rekordbox-XML, CSV. | 📂 **Playlists**<br>Titel sammeln, in Ordnern ordnen, als M3U8 für Engine DJ, VirtualDJ & Co. |
| 🎧 **Vorschau-Player**<br>Wellenform, Cue-Marken (Serato, Mixed In Key), Überblenden mit Tempo-Angleichung, Bewertung. | 🛡️ **Sicher speichern**<br>Sicherung vor jedem Speichern, Rückgängig über alle Dateien, Snapshots und Änderungsjournal. | 🧩 **Plugins**<br>Stems, Beatport, Discogs, MusicBrainz, Lexicon, Cloud-Abgleich (OneDrive, Google Drive, Dropbox) … |

Dazu: Camelot-Rad und Tonart-Schreibweisen, Audio-Merkmale (Energy, Danceability …) als Spalten, Herkunft der Tags,
„Entdecken“ neuer Veröffentlichungen, Einstellungen an einem Ort, Deutsch, Englisch und Zürichdeutsch.
Alles im Detail im **[Handbuch](docs/HANDBUCH.md)**.

## Bilder

<table>
  <tr>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/compare-dark.png"><img alt="Vergleich zweier Ordner" src="docs/screenshots/compare-light.png"></picture><br><b>Vergleich</b> – Unterschiede je Feld, per Pfeil übernehmen</td>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/djset-dark.png"><img alt="DJ-Set mit Camelot-Rad und Energiekurve" src="docs/screenshots/djset-light.png"></picture><br><b>DJ-Set</b> – Weg durch das Camelot-Rad, Energie und BPM</td>
  </tr>
  <tr>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/purchases-dark.png"><img alt="Einkäufe mit Abgleich" src="docs/screenshots/purchases-light.png"></picture><br><b>Einkäufe</b> – gekauft, im Eingang, in der Bibliothek, fehlt</td>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/plugins-dark.png"><img alt="Plugins nach Kategorie" src="docs/screenshots/plugins-light.png"></picture><br><b>Plugins</b> – nach Kategorie, einzeln aktualisierbar</td>
  </tr>
</table>

<sub>Bilder mit erfundenen Beispieltiteln, erstellt mit <code>tools/screenshots.py</code>.</sub>

## Installation

**Mit Installer (empfohlen, kein Python nötig):** unter
[Neueste Version](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest) ganz oben im Kasten
„Download“ die Datei für dein System laden.

- **Windows:** `TagStudio-<Version>-Windows-Setup.exe` ausführen – ohne Administratorrechte. Der Installer ist nicht
  signiert: bei „Der Computer wurde durch Windows geschützt“ **Weitere Informationen → Trotzdem ausführen**.
- **macOS (Apple-Chip):** `TagStudio-<Version>-macOS-Apple-Chip.dmg` öffnen, **TagStudio** auf **Programme** ziehen;
  beim ersten Start **Systemeinstellungen → Datenschutz & Sicherheit → „Trotzdem öffnen“**.

**Aus dem Quellcode:** Python 3.12 oder neuer, dann
`git clone https://github.com/MarkusKeller8200/markussxch-tagstudio.git` und `start_windows.bat` bzw.
`start_mac.command`. Details, Updates und alle Optionen: [Handbuch › Installation](docs/HANDBUCH.md#installation).

> Bis Version 2.8 hiess das Programm „MP3 Tag Compare“. Einstellungen und Sicherungen von damals werden automatisch übernommen.

## Mitmachen und Kontakt

- **Fehler melden, Ideen vorschlagen:** [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues) –
  oder direkt in TagStudio über „Melden …“.
- **Mitmachen:** [CONTRIBUTING.md](CONTRIBUTING.md) · **Verhaltenskodex:** [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Sicherheit:** [SECURITY.md](SECURITY.md) · **Fremdkomponenten:** in TagStudio unter Hilfe › Lizenzen
- **Lizenz:** [GNU GPL v3](LICENSE) – frei nutzbar, Änderungen bleiben offen.
