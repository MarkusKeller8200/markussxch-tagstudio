<p align="center">
  <img src="web/icon.png" width="96" height="96" alt="">
</p>

<h1 align="center">MarKusSXCH TagStudio</h1>

<p align="center">
  <b>The toolbox for DJs' MP3 libraries</b><br>
  Tag, compare, clean up, match purchases and plan sets – for Windows and macOS.
</p>

<p align="center">
  <a href="https://markuskeller8200.github.io/markussxch-tagstudio/"><img alt="Downloads" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FMarkusKeller8200%2Fmarkussxch-tagstudio%2Fstats%2Fdocs%2Fbadge.json"></a>
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest"><img alt="Latest version" src="https://img.shields.io/github/v/release/MarkusKeller8200/markussxch-tagstudio?label=Version"></a>
  <img alt="Windows and macOS" src="https://img.shields.io/badge/Windows%20%7C%20macOS-555">
  <a href="LICENSE"><img alt="Licence GPL-3.0" src="https://img.shields.io/badge/Licence-GPL--3.0-555"></a>
</p>

<p align="center">
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest"><img alt="Download for Windows" src="https://img.shields.io/badge/Download-Windows-1D76DB?style=for-the-badge&logo=windows11&logoColor=white"></a>
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest"><img alt="Download for macOS" src="https://img.shields.io/badge/Download-macOS%20(Apple%20silicon)-1D76DB?style=for-the-badge&logo=apple&logoColor=white"></a>
  <a href="docs/HANDBUCH.en.md"><img alt="Manual" src="https://img.shields.io/badge/Manual-read-6E7781?style=for-the-badge&logo=readthedocs&logoColor=white"></a>
</p>

<p align="center">
  <a href="docs/HANDBUCH.en.md">Manual</a> ·
  <a href="CHANGELOG.md">Changes</a> ·
  <a href="PLUGINS.en.md">Plugins</a> ·
  <a href="https://markuskeller8200.github.io/markussxch-tagstudio/">Website</a> ·
  <a href="https://markuskeller8200.github.io/markussxch-tagstudio/statistik.html">Download statistics</a> ·
  <a href="https://github.com/MarkusKeller8200/markussxch-tagstudio/issues">Bugs &amp; ideas</a> ·
  <a href="README.md">Deutsch</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/tagger-dark.png">
  <img alt="Tagger: edit many files at once, key, BPM and genre at a glance" src="docs/screenshots/tagger-light.png">
</picture>

<sub>The pictures show the German interface; TagStudio also speaks English and Swiss German.</sub>

## What TagStudio does

| | | |
|---|---|---|
| 🏷️ **Tagger**<br>Edit many files at once, covers, tags from the file name, renaming, search & replace, export to Excel/CSV. | ⚖️ **Comparison**<br>Two folders or files field by field – marked character by character, copy values with an arrow. | 🧹 **Tag fixer**<br>Unify multiple values (`;` `/` `feat.` …), Smart Fix recipes, exceptions per field. |
| 🛒 **Purchases**<br>Match bought tracks (Beatport) with the library, download missing ones, create playlists in Beatport. | 🎛️ **DJ set**<br>Optimise the order by key (Camelot), BPM and energy – export as M3U8, Rekordbox XML, CSV. | 📂 **Playlists**<br>Collect tracks, sort them into folders, as M3U8 for Engine DJ, VirtualDJ & co. |
| 🎧 **Preview player**<br>Waveform, cue points (Serato, Mixed In Key), crossfading with tempo matching, ratings. | 🛡️ **Safe saving**<br>Backup before every save, undo across all files, snapshots and change journal. | 🧩 **Plugins**<br>Stems, Analyse mix (recognise tracks in DJ mixes), Beatport, Discogs, MusicBrainz, Lexicon, cloud sync (OneDrive, Google Drive, Dropbox) … |

Plus: Camelot wheel and key notations, audio features (energy, danceability …) as columns, origin of tags,
“Discover” new releases with wish lists (“Ideas”), settings in one place, German, English and Swiss German.
Everything in detail in the **[manual](docs/HANDBUCH.en.md)**.

## Pictures

<table>
  <tr>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/compare-dark.png"><img alt="Comparing two folders" src="docs/screenshots/compare-light.png"></picture><br><b>Comparison</b> – differences per field, copy with an arrow</td>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/djset-dark.png"><img alt="DJ set with Camelot wheel and energy curve" src="docs/screenshots/djset-light.png"></picture><br><b>DJ set</b> – path through the Camelot wheel, energy and BPM</td>
  </tr>
  <tr>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/purchases-dark.png"><img alt="Purchases with matching" src="docs/screenshots/purchases-light.png"></picture><br><b>Purchases</b> – bought, in inbox, in library, missing</td>
    <td width="50%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/plugins-dark.png"><img alt="Plugins by category" src="docs/screenshots/plugins-light.png"></picture><br><b>Plugins</b> – by category, updatable one by one</td>
  </tr>
</table>

<sub>Pictures with made-up example tracks, created with <code>tools/screenshots.py</code>.</sub>

## Installation

**With the installer (recommended, no Python needed):** on
[Latest version](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/latest) download the file for your
system from the “Download” box at the top.

- **Windows:** run `TagStudio-<version>-Windows-Setup.exe` – no administrator rights needed. The installer is not
  signed: at “Windows protected your PC” choose **More info → Run anyway**.
- **macOS (Apple silicon):** open `TagStudio-<version>-macOS-Apple-Chip.dmg`, drag **TagStudio** to **Applications** –
  signed and notarised by Apple (from 4.13.0).

**From source:** Python 3.12 or newer, then
`git clone https://github.com/MarkusKeller8200/markussxch-tagstudio.git` and `start_windows.bat` or
`start_mac.command`. Details, updates and all options: [Manual › Installation](docs/HANDBUCH.en.md#installation).

> Up to version 2.8 the program was called “MP3 Tag Compare”. Settings and backups from that time are taken over
> automatically.

## Contributing and contact

- **Report bugs, suggest ideas:** [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues) – or
  directly in TagStudio via “Report …”.
- **Contributing:** [CONTRIBUTING.md](CONTRIBUTING.md) · **Code of conduct:** [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- **Security:** [SECURITY.md](SECURITY.md) · **Third-party components:** in TagStudio under Help › Licences
- **Licence:** [GNU GPL v3](LICENSE) – free to use, changes stay open.
