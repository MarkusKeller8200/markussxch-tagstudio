# Speicherkonzept – wo TagStudio was ablegt

Stand: **4.4.0-beta.4** (2026-10-11). Dieses Dokument wird bei Gelegenheit nachgeführt, wenn sich Ablageorte ändern.
`~` steht für den Benutzerordner (Windows: `C:\Users\<Name>`).

Es gibt zwei Arten von Ordnern:

- **Programmdaten** (Abschnitte 1–3): legt TagStudio selbst an und verwaltet sie – Einstellungen, Caches, Protokolle,
  Zustände. Liegen im Benutzerordner, je Profil getrennt.
- **Arbeitsordner** (Abschnitte 4–5): deine Musik und die Ordner, in denen gearbeitet wird. TagStudio legt dort nichts
  Eigenes ab, ausser es wird verlangt (Stufen-Kopien, Stems, angeglichene Kopien, Sicherungen und Snapshots, wenn sie
  dorthin gelegt werden).

## 1. Programmdaten des Standardprofils – `~\TagStudio`

| Ordner / Datei | Wofür |
|---|---|
| `~\.tagstudio.json` | Alle Einstellungen (liegt direkt im Benutzerordner) |
| `~\.tagstudio.lock` | Sperrdatei „nur eine Instanz je Profil“ – wird beim Beenden frei |
| `Einstellungen\` | Automatische Sicherungen der Einstellungsdatei vor Import oder Zurücksetzen |
| `Sicherungen\` | Standardort der Tag-Sicherungen, solange kein eigener Ordner gewählt ist |
| `Snapshots\` | Standardort des Snapshot-Speichers, solange kein eigener Ort gewählt ist |
| `cache\` | Cover-Vorschaubilder – darf gelöscht werden |
| `cache\lists\` | Listen-Cache für schnelles Einlesen grosser Ordner |
| `cache\wave\` | Wellenformen und Beatgrid für den Player |
| `cache\tagscan\` | Ergebnisse von „Bibliothek scannen“ (Hilfe › Tag-Übersicht) |
| `Logs\` | Protokolle: `app.log` und je ein Protokoll pro Plugin |
| `Plugins\` | Eigene Plugins (Programmcode) – **für alle Profile gemeinsam** |
| `Plugin-Daten\<Plugin>\` | Daten der Plugins (Abschnitt 2) |
| `Vorbereiten\<Workflow>.json` | Status je Titel in den Workflow-Schritten, abgeholte Downloads |
| `Entdecken\entdecken.json` | Gefolgte Künstler/Labels/Genres, Vorschläge, Merkliste |
| `Käufe\kaeufe.json` (#285) | Gekaufte Titel aller Stores mit Status (Bibliothek, Eingang, unklar, fehlt) |
| `Playlists\` (#267) | Playlist-Speicher: `index.json` + eine Datei je Playlist (massgebend, Spiegel in `03_Playlists`) |
| `Auftraege.json` | Warteschlange der Hintergrund-Aufträge (z. B. Stems) |
| `profile.json` | Profilwahl beim Start (fragen ja/nein, zuletzt benutzt) |

## 2. Plugin-Daten – `~\TagStudio\Plugin-Daten`

| Ordner / Datei | Wofür | Gilt für |
|---|---|---|
| `stems\env\` | Eigene Python-Umgebung des Stems-Plugins (gross) | alle Profile |
| `stems\modelle\` | KI-Modelle zur Trennung (gross) | alle Profile |
| `stems\ffmpeg\` | FFmpeg (nutzt auch das Plugin Lautheit) | alle Profile |
| `stems\arbeit\` | Temporärer Arbeitsordner während einer Trennung | je Profil |
| `beatport\token.bin` | Beatport-Anmeldung, verschlüsselt (nur das eigene Windows-Konto kann sie lesen) | je Profil |
| `beatport\client_id.txt` | Technische Kennung für die Anmeldung | je Profil |
| `beatport\gekaufte-titel.csv` | Ergebnis von „Gekaufte Titel abgleichen“ | je Profil |
| `beatport\geladen.json` | Bereits heruntergeladene Käufe (keine Doppelten) | je Profil |
| `online\keys.bin` | Schlüssel der Online-Dienste, verschlüsselt | je Profil |

## 3. Weitere Profile – `~\TagStudio-Profile\<Name>\`

Jedes weitere Profil hat einen eigenen Ordner mit denselben Unterordnern wie Abschnitt 1; die Einstellungen stehen
dort in `einstellungen.json`, die Sperrdatei ist `.tagstudio.lock`. Gemeinsam bleiben nur `~\TagStudio\Plugins\` sowie
Stems-Umgebung, Modelle und FFmpeg aus `~\TagStudio\Plugin-Daten\stems\`. Siehe [KONZEPT-EINRICHTUNG.md](KONZEPT-EINRICHTUNG.md).

## 4. Arbeitsordner – empfohlene Struktur unter dem Basisordner

Der **Basisordner** wird gespeichert (Einstellungen › Speicherort und Ordner bzw. Einrichtungsassistent); jede
Ordnerauswahl in TagStudio beginnt dort. Vorschlag: `D:\TagStudio` (erstes weiteres festes Laufwerk), nur mit C:
`~\Music\TagStudio` – bewusst **nicht** `~\TagStudio`, dort liegen die Programmdaten.

Die empfohlene Struktur (Namen im Assistenten änderbar; vorhandene Ordner bleiben, nichts wird verschoben):

| Ordner | Wofür | In TagStudio eingestellt als |
|---|---|---|
| `00_New` | Neue Musik, Rohdaten – bleiben unverändert | Eingangsordner „Vorbereiten“ |
| `01_Library` | Endgültige Bibliothek | Tagger-Standardordner, Bibliothek im Workflow (Ziel der Übernahme), mit Snapshots überwacht |
| `02_Archiv` | Aussortierte Titel – Unterordner bleiben erhalten; Vermerk `_aussortiert.csv` (Datum, Von, Nach) zum Zurückholen | Archiv (Aktion „Aussortieren“ im Tagger und in „Vorbereiten“, #173) |
| `03_Playlists` (#267) | Alle Playlists als M3U8 (relative Pfade), Unterordner = Ordner im Playlist-Baum; archivierte Playlists in `02_Archiv/_Playlists` | Playlist-Ordner ([KONZEPT-PLAYLISTS.md](KONZEPT-PLAYLISTS.md)) |
| `90_Download` | Temporäre Downloads (Browser, Beatport, ZIP) | Quelle „Downloads“ im Workflow („Abholen“ kopiert nach `00_New`), Ziel des Beatport-Downloads |
| `91_Work` | Arbeitsordner für TagStudio und andere Programme | Arbeitsordner im Workflow; darin die Stufen-Ordner `_02_MP3Tag`, `_03_PlatinumNotes` … |
| `99_Sicherung\Tags` | Tag-Sicherungen vor jedem Speichern | Sicherungs-Ordner |
| `99_Sicherung\Snapshots` | Snapshot-Speicher (Tag-Stände, Journal, auch die Sicherungen) | Snapshot-Speicher (nur umgestellt, wenn der bisherige leer ist) |

Weg eines neuen Titels: `90_Download` → „Abholen“ → `00_New` → Stufen in `91_Work` → „Übernahme“ → `01_Library`
(oder „Aussortieren“ → `02_Archiv`).

Hinweise:
- **Alles auf einem Laufwerk** – Verschieben zwischen den Ordnern geht dann sofort und braucht keinen zusätzlichen Platz.
- **`99_Sicherung` ist kein Backup der Musik.** TagStudio sichert nur Tags (wenige MB). Die Musik zusätzlich auf ein
  anderes Laufwerk oder in die Cloud sichern.
- **`01_Library` früh festlegen** – Engine DJ, Lexicon, Rekordbox und Serato merken sich die Pfade; verschobene
  Bibliotheken verlieren dort die Verweise.

## 5. Weitere Arbeitsordner (frei gewählt oder automatisch)

| Ordner | Wo eingestellt | Wofür |
|---|---|---|
| Standard links / rechts | Einstellungen › Vergleich | Startpfade im Vergleich |
| Weitere Quellen (Download-Ordner) | Vorbereiten › Workflow › Quellen | z. B. Bandcamp, Traxsource – „Abholen“ holt neue MP3, Downloads bleiben unverändert |
| `<Titel> – Stems\` | automatisch neben dem Original | Ergebnisse des Stems-Plugins |
| `Angeglichen\` (oder eigener Ordner) | Plugin Lautheit | Angeglichene Kopien, Original bleibt |
| `.tagstudio-snapshots\` | Snapshots (Option) | Snapshot-Speicher direkt in einem Bibliotheksordner – reist mit dem Ordner mit |

## 6. Programm und Altlasten

- **Installation:** `C:\Program Files\TagStudio` bzw. Benutzer-Programmordner – nur das Programm, keine Daten.
  Aus dem Quellcode gestartet: der Ordner des Git-Klons.
- **Von früher (≤ 2.8 „MP3 Tag Compare“):** `~\.mp3tagcompare.json` und `~\MP3TagCompare\Sicherungen` werden nur
  gelesen, wenn es die neuen Dateien noch nicht gibt.

In der App: Einstellungen › Speicherort und Ordner (Arbeitsordner), Einstellungen › Profile (Profil-Ordner),
Einstellungen › Expert (Programmdaten).
