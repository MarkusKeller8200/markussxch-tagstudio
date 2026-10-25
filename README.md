# MarKusSXCH TagStudio

Werkzeugkasten für MP3-Bibliotheken von DJs: **Tagger, Vergleich** (im Stil von Beyond Compare), **Tag-Fixer,
Sicherungen, Camelot-Rad, Audio-Merkmale** und **Plugins** (z. B. Stems, Beatport). Für **Windows und macOS**.
Der Kern braucht keine Zusatzpakete, nur Python 3.12 oder neuer – oder gar nichts, mit dem Installer.

**Download:** [Releases](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases) ·
**Änderungen:** [CHANGELOG.md](CHANGELOG.md) · **Plugins:** [PLUGINS.md](PLUGINS.md) ·
**Fehler & Ideen:** [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues) ·
**Mitmachen:** [CONTRIBUTING.md](CONTRIBUTING.md) · **Sicherheit:** [SECURITY.md](SECURITY.md) ·
**Lizenz:** [GNU GPL v3](LICENSE) · **English:** [README.en.md](README.en.md)

> Bis Version 2.8 hiess das Programm „MP3 Tag Compare“. Einstellungen und Sicherungen von damals werden automatisch übernommen.

## Funktionen im Überblick

- **Tagger:** viele Dateien gemeinsam bearbeiten, Cover, Tags aus Dateiname, Umbenennen, Spurnummern,
  Gross-/Kleinschreibung, Suchen & Ersetzen, Export nach Excel/CSV.
- **Editoren für jedes Feld:** mehrzeiliger Feld-Editor, Mehrfachwerte als Einzelwerte, JSON als Baum,
  XML-Editor, Binärfeld-Editor für DJ-Daten (GEOB/PRIV), Farbwähler für Hex-Farben, anklickbare Links.
- **Tonart:** Camelot-Rad mit harmonisch passenden Tonarten; Schreibweise Camelot (`08A`), musikalisch (`Am`)
  oder Open Key (`1m`).
- **Audio-Merkmale:** Energy, Danceability, Happiness … als Felder mit Werten 0–100, als Spalten im Tagger,
  sortier- und filterbar (`energy>=70`); Dateien wahlweise in 0–10 (Lexicon).
- **DJ-Set:** Reihenfolge nach Tonart (Camelot), BPM und Energie optimieren, jeden Übergang bewerten, per Ziehen
  umsortieren und sperren, Weg durch das Camelot-Rad und Energiekurve; Export als M3U8, Rekordbox-XML und CSV.
- **Playlists:** Titel aus Tagger und DJ-Set in Playlists mit Ordnern sammeln; jede Playlist liegt zusätzlich als
  M3U8 im Playlist-Ordner (für Engine DJ, VirtualDJ & Co.); Archivieren statt Löschen.
- **Vergleich zweier Ordner/Dateien:** Feld für Feld mit zeichengenauen Markierungen, Werte per Pfeil übernehmen.
- **Tag-Fixer:** Mehrfachwerte (`;`, `/`, `feat.` …) vereinheitlichen oder in echte ID3v2.4-Mehrfachwerte umwandeln.
- **Sicherheit beim Speichern:** vor jedem Speichern automatische Sicherung der Tags, Änderungs-Viewer,
  byte-genaues Wiederherstellen; Rückgängig/Wiederholen über alle Dateien.
- **Vorschau-Player:** Titel vorhören mit Wellenform und Cue-Marken (Serato, Mixed In Key), Live-Vorschau,
  Überblenden mit Tempo-Angleichung, **Bewertung und Like**, zweiter Player zum Vorhören, abdockbar auf einen zweiten
  Bildschirm, A/B im Vergleich, externe Player (foobar2000, VLC …).
- **Snapshots & Änderungsjournal:** Tag-Zustand überwachter Ordner festhalten, Änderungen anderer Programme erkennen
  und einzeln zurücknehmen; Schutz vor dem Überschreiben fremder Änderungen.
- **Herkunft der Tags:** Kennzeichen, welche Anwendung ein Feld geschrieben hat; Felder einer Anwendung filtern
  oder entfernen.
- **Plugins:** Stems (Gesang, Schlagzeug, Bass … trennen – im Hintergrund, Spuren aufklappbar unter dem Titel) und
  Beatport (Metadaten mit eigenem Login, Käufe abgleichen und fehlende herunterladen), eigene Plugins möglich.
- **Einstellungen** an einem Ort – mit Vorgaben für den Start –, exportieren/importieren (z. B. Windows ↔ Mac) und
  zurücksetzen; Updates wahlweise nur offizielle oder auch Beta-Versionen, Versionshinweise direkt in der App.
- **Sprachen:** Deutsch, Englisch und Zürichdeutsch; eigene Texte exportieren, anpassen und wieder
  importieren (Einstellungen › Darstellung › Sprache).

## Programmstart

| | |
|---|---|
| Installiert | **TagStudio** im Startmenü bzw. unter Programme |
| Quellcode Windows | `start_windows.bat` (bzw. `start_web_windows.bat`) |
| Quellcode macOS | `start_mac.command` (bzw. `start_web_mac.command`) |
| Terminal | `python tagstudio_web.py [links] [rechts]` – mit `--browser` im Browser statt im eigenen Fenster |

Die erste, klassische Oberfläche (tkinter) ist seit Version 3.0 eingefroren – siehe
[Klassische Oberfläche](#klassische-oberfläche-eingefroren) am Ende.

## Installation

### Mit Installer (empfohlen, kein Python nötig)

Unter [Releases](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases) die neueste Version laden:

- **Windows:** `TagStudio-<Version>-Windows-Setup.exe` ausführen. Installiert ohne Administratorrechte nach
  `%LOCALAPPDATA%\Programs\TagStudio`, mit Startmenü-Eintrag, optionalem Desktop-Symbol und Deinstallation über
  „Apps & Features“. Der Installer ist nicht signiert – erscheint „Der Computer wurde durch Windows geschützt“:
  **Weitere Informationen → Trotzdem ausführen**.
- **macOS (Apple-Chip):** `TagStudio-<Version>-macOS-Apple-Chip.dmg` öffnen, **TagStudio** auf **Programme** ziehen.
  Die App ist nicht von Apple beglaubigt: beim ersten Start Meldung schliessen, dann **Systemeinstellungen →
  Datenschutz & Sicherheit → „Trotzdem öffnen“** (Details in „Zuerst lesen.txt“ im Disk-Image).

Die installierte App enthält die neue Oberfläche samt Plugins (Stems richtet seine eigene Umgebung beim ersten
Installieren selbst ein). **Updates:** Der Knopf „Nach Update suchen“ öffnet die Releases-Seite; neue Version laden
und darüber installieren – Einstellungen, Sicherungen und Plugin-Daten liegen im Benutzerordner und bleiben erhalten.

### Aus dem Quellcode (für Entwicklung und Update-Knopf)

1. **Python** von https://www.python.org/downloads/ installieren – Windows: „Add python.exe to PATH“ anhaken;
   macOS: das Installationspaket enthält tkinter (Homebrew-Python braucht zusätzlich `brew install python-tk`).
2. **Programm holen** – am besten als Git-Klon, dann funktioniert der Update-Knopf:
   `git clone https://github.com/MarkusKeller8200/markussxch-tagstudio.git`
   (alternativ ZIP von GitHub herunterladen und entpacken).
3. **Starten** per Doppelklick (siehe Tabelle; macOS beim ersten Mal: Rechtsklick → Öffnen).
   Die neue Oberfläche installiert beim ersten Start `pywebview` (klein, Internet nötig) und öffnet ein eigenes
   App-Fenster. Ohne pywebview öffnet sie sich im Browser (`python tagstudio_web.py --browser`).

## Bedienung

Seitenleiste mit **Käufe, Vorbereiten, Tagger, Tag-Fixer, Vergleich, DJ-Set, Playlists, Snapshots, Sicherungen, Plugins,
Einstellungen** (Einstellungen › Darstellung › Seitenleiste: Menüpunkte ein-/ausblenden und mit ↑/↓ eigene Reihenfolge), unten
„Nach Update suchen“, Versionshinweise, Einklappen und Hell/Dunkel. **Zurück:** Nach einem Sprung aus dem Inhalt
(z. B. Playlist › „Im Tagger öffnen“) erscheint oben in der Seitenleiste „← Zurück“ mit dem Ziel – es führt an
dieselbe Stelle zurück (Auswahl, Filter, Bildlauf); ebenso Alt+← / Alt+→ (ausser im Vergleich) und die Maustasten
Zurück/Vorwärts, Rechtsklick zeigt die letzten Stationen. Klicks in der Seitenleiste zählen nicht. Beim Start öffnet die zuletzt benutzte Seite
(beim ersten Start der Tagger). Der Tagger lädt beim Start den zuletzt geladenen Ordner im Hintergrund (die App ist
sofort bedienbar) und stellt Markierung,
Sortierung, Filter und Bildlauf wieder her (Einstellungen › Tagger › „Beim Start laden“: zuletzt geladen, Standardordner
oder nichts). Vergleich und Tagger arbeiten mit denselben Dateien – Änderungen sind in beiden sichtbar, werden
zusammen gespeichert (Strg/Cmd+S) und lassen sich gemeinsam rückgängig machen.
Das App-Fenster öffnet in der Grösse und Position vom letzten Mal (auch maximiert).

### Tagger

- **Schnell wieder da:** ein schon eingelesener Ordner erscheint sofort aus dem Listen-Cache; danach prüft TagStudio
  im Hintergrund jeden Titel über einen Hash seiner Tags und liest Geändertes neu (Stand in der Statuszeile).
- **Liste:** Ordner oder Datei einlesen; optional mit **Cover-Spalte** (Knopf „Cover“); Spalten Datei, Titel, Künstler, Album, Spur, Jahr, Genre, Tonart –
  sortierbar per Klick, filterbar. Markieren mit Klick, Shift, Strg/Cmd, Strg/Cmd+A.
- **Spalten ▾:** weitere Spalten (Album-Künstler, Disk, Komponist, Kommentar, Länge, kbit/s, Bewertung, ID3-Version,
  Label, Katalognummer, Remixer, ISRC … oder **beliebiges Feld** wie `TXXX:LABEL`), Reihenfolge per **Ziehen in der
  Kopfzeile**, „An Fenster anpassen“ oder „Optimale Breite“ mit waagrechtem Blättern. **Sortieren** in bis zu drei
  Stufen (Shift+Klick auf weitere Spalten), „↺ Sortierung“ setzt auf den Standard zurück; „Aktuelle Sortierung als
  Standard“ und **„Ansicht als bevorzugt speichern“** (auch unter Einstellungen › Tagger).
- **Bearbeiten:** rechts die Standardfelder der markierten Dateien. Bei mehreren Dateien zeigt „‹verschieden›“
  unterschiedliche Werte – sie bleiben unverändert, bis du etwas einträgst. Cover setzen/entfernen, ID3-Version
  (v2.3/v2.4) wählen. Steht eine Internetadresse im Feld (z. B. Kommentar), erscheint daneben ein Link-Knopf.
- **Werkzeuge** (alle mit Vorschau):
  - **Tags aus Dateiname** – Muster wie `%track% - %artist% - %title%`, `%dummy%` überspringt einen Teil.
  - **Dateien umbenennen** – aus Tags; ungültige Zeichen → `_`, Kollisionen werden erkannt (sofort, nicht über
    „Speichern“).
  - **Spurnummern** – in Listenreihenfolge, optional mit Gesamtzahl (3/12).
  - **Gross-/Kleinschreibung** – Titel-Schreibweise, Satzanfang, GROSS, klein; Abkürzungen wie DJ/AC/DC bleiben.
  - **Suchen & Ersetzen** – über alle markierten Dateien, wählbare Felder, ganze Wörter, reguläre Ausdrücke.
  - **Cover aus Ordner** – `cover/folder/front/album.jpg|png` im Ordner der Datei, sonst das grösste Bild.
  - **Liste exportieren** – Excel (.xlsx) oder CSV mit Semikolon, inkl. Camelot- und Audio-Merkmal-Spalten.
  - **Feld hinzufügen**, **Tag-Fixer**, **Im Explorer/Finder zeigen**.

#### Weitere Felder und Editoren

Bei einer markierten Datei listet „Weitere Felder“ alle übrigen Tags. Der Teiler zwischen Feld und Wert lässt sich
ziehen (Doppelklick = Standard, Breite wird gemerkt). Links sind anklickbar, Hex-Farben (Felder mit „COLOR“ im
Namen, z. B. `#CC0000`, `0xFFCC0000`) erscheinen als Farbfeld. **Stift-Knopf** oder **Doppelklick** öffnet den
passenden Editor, ✕ entfernt das Feld.

- **Feld-Editor:** grosses, mehrzeiliges Textfeld (Kommentare, Liedtexte), Zeichen-/Zeilenzähler, mit ‹ › bzw.
  Alt+↑/↓ zum vorigen/nächsten Feld blättern (speichert dabei), Strg/Cmd+Enter übernimmt.
  - **Einzelwerte:** Mehrfachwerte (getrennt durch NULL-Zeichen/ID3v2.4, Semikolon oder Komma) als Liste –
    Wert hinzufügen (auch Enter), entfernen, umsortieren; Trennung umstellbar, z. B. „House; Techno“ in echte
    ID3v2.4-Mehrfachwerte umwandeln.
  - **Farbwähler** bei Hex-Farben – die Schreibweise (Präfix, Gross-/Kleinschreibung, Alpha) bleibt erhalten.
- **JSON-Baum** (für JSON in Textfeldern und DJ-Daten, z. B. Mixed In Key): Schlüssel/Wert-Paare wie im XML-Editor,
  aufklappbar. Bearbeitet werden nur die Werte – Text, Zahlen (mit Prüfung), Ja/Nein als Häkchen; nur die
  geänderten Werte werden im Originaltext ersetzt, Format und Einrückung bleiben exakt.
  **Expertenmodus** (Häkchen, wird gemerkt): Einträge hinzufügen – bei Listen z. B. einen neuen Cue-Punkt als Kopie
  des letzten, bei Objekten neue Schlüssel mit Typ –, duplizieren (⧉) und entfernen (✕).
- **XML-Editor** (Kennzeichen **XML**, auch im Vergleich): **Baum** (Attribute und Texte direkt bearbeiten,
  auf-/zuklappen, suchen) und **Quelltext** (farbig, Zeilennummern), laufende Prüfung mit Fehlerstelle,
  **Formatieren** und **Kompakt**. Auch XML in Binärfeldern ist bearbeitbar – ersetzt wird nur der XML-Abschnitt.
- **Binärfeld-Editor** (GEOB/PRIV, z. B. Serato, Mixed In Key): Kopf (Beschreibung, MIME-Typ und Dateiname bzw.
  Besitzer) und Inhalt – lesbarer Text und Base64-kodierter Text/JSON direkt bearbeitbar (beim Übernehmen wieder
  gleich kodiert), XML im XML-Editor, sonst Hex-Ansicht. Geändert wird nur, was bearbeitet wurde.

- **Herkunft:** vor dem Feldnamen ein kleines Kennzeichen, welche Anwendung das Feld geschrieben hat (z. B.
  **Serato**, **MIK**, **MB** für MusicBrainz, **Beatport**, **Spotify**, **Discogs**, **Traktor**, **iTunes**), Tooltip mit
  Erklärung. Offizielle ID3-Felder (Titel, Künstler, BPM, Cover …) zeigen zusätzlich ihre **ID3-Version** (v2.3/v2.4,
  abschaltbar); benutzerdefinierte Felder (TXXX, GEOB, PRIV …) ohne bekannte Anwendung heissen **„unbekannt“**.
  Text und Farbe jedes Kennzeichens lassen sich in den Einstellungen anpassen und wieder zurücksetzen. Auch im Vergleich – dort entfernt der Knopf
  **„Herkunft“** die Felder einer Anwendung links, rechts oder auf beiden Seiten. Im Tagger über „Alle Herkünfte“
  filtern; „Alle entfernen …“ bzw. **„Felder nach Herkunft …“** entfernt alle Felder einer Anwendung aus den
  markierten Dateien (Vorschau, Rückgängig).

> Programme wie Serato oder Mixed In Key erwarten in ihren Feldern ihr eigenes Format. Änderungen an DJ-Daten
> (z. B. neue Cue-Punkte) zuerst an einer Testdatei ausprobieren.

#### Tonart und Camelot-Rad

Knopf neben dem Feld „Tonart“ öffnet das Rad (aussen Dur, innen Moll). Klick setzt die Tonart der markierten
Dateien; die aktuelle und die harmonisch passenden Tonarten (±1, Paralleltonart) sind hervorgehoben. Geschrieben
wird wahlweise als **Camelot** (immer zweistellig: `08A`, `01B`), **musikalisch** (`Am`) oder **Open Key** (`1m`);
erkannt werden auch Schreibweisen wie `8A`, `A minor`, `F♯m`, `a-Moll` oder `Es-Dur`. „Schreibweise
vereinheitlichen“ schreibt alle markierten Dateien um. Die Spalte „Tonart“ zeigt farbige Camelot-Codes
(sortierbar); bei einer markierten Datei sind die passenden Titel umrandet.

#### Audio-Merkmale

Aufklappbarer Bereich im Tagger: Energy, Danceability, Happiness, Valence, Acousticness, Instrumentalness,
Liveness, Speechiness, Brightness, Aggressiveness als `TXXX:ENERGY` … mit Werten 0–100 – per Schieberegler oder
Zahl (0.78 → 78), für eine oder mehrere Dateien. Andere Schreibweisen (`TXXX:Energy`) werden erkannt und beim
Ändern vereinheitlicht.

**Spalten und Filter:** Über „Merkmale ▾“ in der Liste lassen sich Merkmale als Spalten einblenden (mit kleinem
Balken) und per Klick auf den Spaltenkopf sortieren. Das Suchfeld versteht neben Text auch Zahlenfilter, mehrere mit
Leerzeichen getrennt und mit Text kombinierbar:

| Eingabe | findet |
|---|---|
| `energy>=70`, `Energie ≥ 70` | Energy ab 70 |
| `dance<40`, `tanz<40` | Danceability unter 40 |
| `energy:60-80` | Energy von 60 bis 80 |
| `bpm:120-128`, `tempo=124` | BPM-Bereich bzw. genau 124 |
| `house energy>50` | Text „house“ und Energy über 50 |

Namen dürfen abgekürzt (`ener`, `dance`) oder deutsch sein (Energie, Tanz, Stimmung, Akustik, Sprache …).
**Skala:** Unter Einstellungen › Tagger lässt sich einstellen, dass die Werte in den Dateien 0–10 sind (z. B. aus
Lexicon). Angezeigt und eingegeben wird dann weiterhin 0–100; beim Lesen wird ×10, beim Schreiben ÷10 gerechnet.

### Vorbereiten und Entdecken

**Workflow:** Neue Titel laufen vom **Eingangsordner** über frei zusammenstellbare Schritte in die **Bibliothek** – jede
Stufe arbeitet auf einer Kopie, die Rohdaten bleiben unverändert. Schritt-Typen: Tag-Rezept, externes Programm
(Abschluss an der Herkunft erkennen oder bestätigen), Plugin (z. B. Lautheit, Online-Metadaten – „nur leere Felder
füllen“), Pflichtfelder prüfen, Übernahme mit Duplikatprüfung und nachgelagerte Programme als Status. Die Schutzregel
„nur ergänzen“ meldet (oder setzt zurück), wenn ein Programm bestehende Tags ändert. **Quellen** sind Download-Ordner
der Kaufplattformen; „Abholen“ kopiert neue MP3 (auch aus ZIP) in den Eingang.

**Entdecken:** Unter „Folgen …“ Künstler, Labels und Beatport-Genres festlegen (oder aus der Bibliothek vorschlagen
lassen); „Suchen“ holt neue Veröffentlichungen von Deezer und Beatport. In der Liste vorhören (▶), merken (☆), als
gekauft markieren (✓) oder ausblenden (✕); „Öffnen“ führt zur Seite des Titels. Gekauft wird nie automatisch.
Der Bereich **Gefolgt** zeigt alle gefolgten Künstler, Labels und Genres (von Beatport übernommene mit „BP“):
Namen direkt hinzufügen, mit × entfernen, „Von Beatport übernehmen“ und „Ähnliche Künstler …“ (Deezer). Rechtsklick
auf einen Vorschlag: „Künstler folgen“ / „Label folgen“. **Leeren …** entfernt neue und ausgeblendete Vorschläge
(gemerkte und gekaufte bleiben), auf Wunsch mit neuer Suche. Titel, die unter **Käufe** stehen, sind mit „gekauft“
markiert und erscheinen im Filter „Gekauft“.

### DJ-Set

Ordnet Titel so, dass die Übergänge passen. Seite **DJ-Set** in der Seitenleiste (daneben die Anzahl Titel im Set).

1. **Titel holen:** im Tagger einen Ordner einlesen, dann „+ Markierte aus dem Tagger“ oder „+ Ganzer
   Tagger-Ordner“ – oder im Tagger Titel markieren und per Rechtsklick „Zum DJ-Set hinzufügen“.
2. **Einstellen:** Energieverlauf (egal, steigend, fallend, Welle), Gewichtung von Tonart, BPM und Energie,
   maximaler BPM-Sprung in Prozent, Titel ohne Tonart/BPM ans Ende oder neutral mitplanen.
3. **Optimieren:** bis 15 Titel wird die beste Reihenfolge exakt berechnet, darüber eine sehr gute Näherung
   (meist unter 2 % vom Optimum, bei 200 Titeln wenige Sekunden). „⇄ Vorher/Nachher“ wechselt zwischen alter und
   neuer Reihenfolge.

**Bewertung:** Zwischen zwei Titeln steht der Übergang mit Ampel, Art des Tonartwechsels (gleich, ±1 auf dem Rad,
Paralleltonart, Energie-Sprung +2/diagonal, Sprung), BPM-Unterschied (Halb-/Doppeltempo wird erkannt, ×2 bzw. ½) und
einer Note 0–100. Übergänge über dem maximalen BPM-Sprung bekommen 0. Die Gesamtnote ist der Durchschnitt der
Übergänge, mit Energieverlauf zu 20 % die Nähe zur Soll-Kurve. Fehlt das Feld ENERGY, wird die Energie grob aus dem
BPM geschätzt (gestreifter Balken).

**Von Hand anpassen:** Zeilen mit der Maus ziehen; 🔒 **sperrt** einen Titel auf seiner Position – „Rest optimieren“
ordnet dann nur die übrigen. Tasten: ↑/↓ wählen, Alt+↑/↓ verschieben, G sperren, Entf entfernen, Enter oder
Doppelklick spielt. Der Player folgt der Set-Reihenfolge (⏮/⏭, „Folgen“, Überblenden), so lassen sich Übergänge
vorhören. Zeilen lassen sich auch auf Player A oder B ziehen.

**Rechts:** der Weg des Sets durch das Camelot-Rad (Start eingekreist) und der Verlauf von Energie, Soll-Kurve und
BPM.

**Exportieren ▾:** M3U8-Playlist mit absoluten oder relativen Pfaden, Rekordbox-XML (in Rekordbox unter
*Einstellungen › Erweitert › rekordbox xml* die Datei einbinden, dann erscheint die Playlist im Bereich „rekordbox
xml“ und lässt sich importieren), CSV für Excel mit Übergangsbewertung, sowie **Spurnummern in
Set-Reihenfolge** schreiben (Vorschau, rückgängig machbar, gespeichert wird wie gewohnt).

Das Set und die Optionen merkt sich TagStudio; Titel aus einem anderen Ordner bleiben im Set, erscheinen aber grau,
bis ihr Ordner wieder im Tagger geladen ist.

**Playlist ▾** (oben): das Set als Playlist speichern (neue kommen in den Ordner „DJ-Sets“, mit Sperren und
Optionen) oder eine beliebige Playlist ins Set laden. Doppelte Titel einer Playlist fallen dabei weg – im Set kommt
jeder Titel einmal vor.

### Playlists

Titel sammeln, ordnen und für DJ-Programme bereitstellen. Seite **Playlists** in der Seitenleiste.

- **Titel hinzufügen:** im Tagger Titel markieren, Rechtsklick (oder Werkzeuge › „Playlist ▾“) → „Zur Playlist
  hinzufügen …“ – bestehende wählen oder eine neue mit Ordner anlegen. **Strg+Shift+P** legt die markierten Titel in
  die zuletzt benutzte Playlist. Im DJ-Set geht dasselbe per Rechtsklick auf einen Titel. **„Online suchen ›“** im
  Rechtsklick-Menü (Tagger, Playlists, DJ-Set) öffnet die Suche bei Beatport, Spotify, SoundCloud, Apple Music oder
  YouTube mit Künstler und Titel – auch für Einträge ohne Datei. Ist ein Titel schon
  enthalten, fragt TagStudio nach: überspringen oder trotzdem hinzufügen (Doppelte sind erlaubt).
- **Verwalten:** links der Baum mit Ordnern (beliebig tief), „Zuletzt benutzt“ und Suche; Playlists auf einen Ordner
  ziehen verschiebt sie. Rechtsklick: Umbenennen (F2), Duplizieren, Verschieben, Farbe und Notiz, mit anderen
  zusammenführen, Archivieren. Rechts die Titel mit BPM, Tonart, Länge und Bewertung – Ziehen bzw. Alt+↑/↓
  sortiert um, Entf entfernt (nur aus der Playlist, nie die Datei), Doppelklick spielt, Titel auf eine andere
  Playlist im Baum ziehen kopiert sie dorthin. Strg+Z / Strg+Y machen jede Änderung rückgängig.
- **Öffnen:** „Im Tagger öffnen“ lädt nur die Titel der Playlist in den Tagger (Hinweis „Nur Playlist geladen“ mit
  „Ganzen Ordner laden“), „Im DJ-Set öffnen“ ins Set. Im Tagger zeigt „Playlist ▾ → Nur Titel aus einer Playlist
  zeigen …“ nur deren Titel (Filter-Chip, ✕ hebt ihn auf). **„↺ Filter“** über der Liste hebt alle Filter auf
  (Suche, Spalten, Feld, Playlist) und lädt bei Bedarf den ganzen Ordner wieder.
- **Playlist-Ordner:** jede Playlist liegt zusätzlich als M3U8 (relative Pfade) in `03_Playlists` im Basisordner,
  Unterordner wie im Baum – zum Einlesen in Engine DJ, VirtualDJ und andere Programme. Einstellen unter
  Einstellungen › Speicherort und Ordner. Ändert ein anderes Programm dort eine Datei oder legt eine neue an,
  meldet die Seite das („Änderungen im Ordner …“) – übernehmen, behalten oder ignorieren; TagStudio überschreibt
  nichts ungefragt.
- **Smartlists (⚡):** „+ Smartlist“ legt eine Playlist an, die sich über Regeln selbst füllt – z. B. „BPM 124–128 und
  ★ ≥ 4“. Datenbasis: die Bibliothek (Tagger-Standardordner, Bibliothek aus „Vorbereiten“ bzw. `01_Library`, mit
  Listen-Cache), die im Tagger geladenen Titel (auch ungespeicherte Änderungen) oder eine andere Playlist. Regeln über
  Text, Künstler, Titel, Album, Genre, Label, Kommentar, Jahr, BPM, Tonart (auch „passt zu 8A“), Bewertung, Like,
  Stimmung, Energie, Aufgenommen/Bearbeitet (Zeitraum oder letzte n Tage) und Herkunft; „alle“ oder „mindestens eine“
  erfüllt; Sortierung (auch Zufall) und Höchstzahl. Neu gebildet wird beim Öffnen (wenn älter als 15 Minuten) und mit
  „↻ Aktualisieren“, nie im Hintergrund; die M3U8 im Playlist-Ordner wird dabei mitgeschrieben. Von Hand lässt sich
  eine Smartlist nicht ändern – „Mehr ▾ → Einfrieren“ macht eine normale Playlist daraus (Strg+Z macht es rückgängig).
- **Archiv statt Löschen:** „Archivieren“ legt die Playlist ins Archiv (unten im Baum), ihre M3U8 wandert nach
  `02_Archiv/_Playlists` (Vermerk in `_aussortiert.csv`). „Zurückholen“ stellt sie wieder her; endgültig löschen geht
  nur im Archiv. Aussortierte Titel bleiben in ihren Playlists stehen und sind als „im Archiv“ markiert.
- **Abspielen:** „▶ Abspielen“ startet ab dem markierten Titel – der Player folgt der Playlist dann auch auf anderen
  Seiten (⏭/⏮, Titelende; „▶ läuft“ im Kopf). Titel müssen dafür nicht im Tagger geladen sein. „Mehr ▾ → In die
  Warteschlange“ hängt die im Tagger geladenen Titel an; in der Warteschlange speichert „Als Playlist speichern …“ sie
  als Playlist, im Player-Menü legt „Laufenden Titel zur Playlist hinzufügen …“ den gerade gespielten Titel ab.
- **Importieren ▾:** M3U/M3U8, Rekordbox-XML (mit Ordnerbaum) oder CSV übernehmen – auch Listen ohne Dateien (Spalten
  Künstler, Titel, Mix, ISRC, Dauer) und Spotify-Exporte (z. B. Exportify-CSV). **„Aus Serato …“, „Aus Engine
  DJ …“, „Aus VirtualDJ …“** und „Aus Lexicon …“ holen die Playlists dieser Programme (Crates, Playlists mit Ordnern,
  virtuelle Ordner) – die Bibliothek wird am üblichen Ort und auf externen Laufwerken gesucht und **nur gelesen**;
  erneut holen aktualisiert sie. **„Trackliste einfügen …“** übernimmt eine kopierte Trackliste von 1001Tracklists,
  MixID, Beatport u. a. (je Zeile „Künstler - Titel“) als Einträge ohne Datei; TagStudio ruft dafür keine Webseite ab.
- **Mehr ▾:** exportieren als M3U8 (absolute oder relative Pfade), Rekordbox-XML oder CSV (ganze Ordner als
  Rekordbox-XML mit Ordnerbaum per Rechtsklick auf den Ordner). **„Mit Bibliothek abgleichen …“** sucht zu Einträgen
  ohne Datei den passenden Titel (gleiche ISRC bzw. Künstler + Titel + Mix = gefunden; „Song - Extended Mix“ und
  „Song (Extended)“ gelten gleich, „Original Mix“ und „Remastered“ wie ohne Angabe). Anderer Mix wie Radio Edit statt
  Extended Mix oder nur ähnlicher Titel = unklar mit Grund und Vorschlag ★; „Anderer Mix gilt als gefunden“ wählt ihn
  direkt (Extended bevorzugt). Gesucht wird in den angehakten Bibliotheken und auf Wunsch
  in einem weiteren Ordner („Anderer Ordner …“); Vorschläge ★ sind vorgewählt. Per Rechtsklick auf einen Ordner bzw.
  „Mehr ▾ › Alle Playlists mit Bibliothek abgleichen …“ geht das für viele Playlists auf einmal. Wird eine Playlist
  erneut geholt (Spotify, SoundCloud, Lexicon …), bleiben Verknüpfungen erhalten, sichere Treffer werden gleich
  verknüpft. **„Fehlende suchen …“** findet verschobene Dateien über den Dateinamen
  (gleiche Grösse bevorzugt). **„Einkaufsliste exportieren …“** speichert alles, was fehlt, als CSV.
- **Vorbereiten:** Im Schritt „Übernahme in die Bibliothek“ legt „In Playlist aufnehmen“ (z. B. `Neu/{Jahr}-{Monat}`)
  die übernommenen Titel in eine Playlist; neue Titel werden ausserdem automatisch mit passenden Einträgen ohne Datei
  verknüpft.
- Die bisherigen gespeicherten DJ-Set-Listen werden beim ersten Start einmalig als Playlists übernommen.

### Käufe

Gekaufte Titel aller Stores an einem Ort – vorerst **Beatport** (Anmeldung im Plugin Beatport). Seite **Käufe** in der
Seitenleiste: Tabelle mit Titel, Interpret, Mix, Länge, Tonart, BPM, Katalognummer, Store, Kaufdatum (sofern der Store
es liefert, sonst „zuerst gesehen“) und Link zum Store. **„↻ Aktualisieren“** holt neue Käufe und gleicht alles mit
der Bibliothek ab: *in Bibliothek*, *im Eingang*, *unklar* oder *fehlt*. **„Fehlende herunterladen“** (bzw. die
markierten) lädt die Dateien unverändert in den Eingangsordner (`00_New` bzw. Eingang von „Vorbereiten“, unter
„Ordner …“ änderbar) – von dort geht es wie gewohnt weiter. Vorbestellungen werden nicht geladen. Beatport bietet
das Herunterladen offiziell nicht an. Lehnt Beatport den gespeicherten Zugang dafür ab, erscheint ein Fenster
**„Anmelden für den Download“**: Anmeldung wie auf der Webseite, gültig nur solange TagStudio läuft (Passwort und
Token werden nicht gespeichert), danach lädt TagStudio die Titel gleich erneut; „● Beatport: Sitzung …“ zeigt die
Anmeldung, „Abmelden“ beendet sie. Klappt es auch so nicht, zeigt TagStudio, wie du die Titel auf der Download-Seite
von Beatport selbst lädst und mit „Abholen“ übernimmst.

### Tag-Fixer

Mehrfachwerte vereinheitlichen – Bereich (aktuelles Paar, eine Seite, markierte Paare, alle Dateien,
Tagger-Auswahl), Felder, erkannte Trenner, Ausgabe (Trennzeichen oder ID3v2.4-Mehrfachwerte), laufende Vorschau.

### Vergleich

Zwei Ordner oder Dateien nebeneinander: Pfade mit Verlauf, Zuordnung nach Dateiname, Disc + Spurnummer, Titel
oder Reihenfolge, Unterordner.
- **Paarliste** mit Status (≠ Unterschiede, ≈ nur unwichtige, = gleich, ◧/◨ nur eine Seite), Suche in Dateinamen
  und Werten, erweiterter Filter nach Feld/Bedingung/Seite, Mehrfachauswahl und **Sammelkopie**.
- **Tabelle** mit zeichengenauen Markierungen, Pfeil-Knöpfen pro Feld, Alles/Fehlende nach links/rechts,
  Bearbeiten per Doppelklick (Tab = nächstes Feld, Mehrfachwerte mit `¦`), Kontextmenü (kopieren, bearbeiten,
  entfernen, Link öffnen, im Explorer/Finder zeigen), klickbare Links, Cover-Vorschau mit Grossansicht,
  Filter Alle/Unterschiede/Gleiche, Unwichtige, leere Felder, Feldsuche, **+ Feld**.
- **Bilder:** Rechtsklick auf ein Cover: anzeigen, ersetzen, exportieren, entfernen; Klick auf den leeren
  Cover-Platz fügt eines hinzu. (Dateidialoge im App-Fenster; im Browser-Modus nur unter Windows/Linux.)

### Vorschau-Player und externe Player

Unten in der Fussleiste (oder oben, siehe unten) – in Tagger und Vergleich:
- **Abspielen** des markierten Titels (Leertaste, ▶ oder **Doppelklick** auf die Zeile), ⏮/⏭ springt zum
  vorherigen/nächsten Titel; beim Abspielen folgt der Player ↑/↓ und spielt am Titelende den nächsten.
  **Live-Vorschau** (Knopf mit den Funkwellen): ein einfacher Klick auf einen Titel spielt ihn sofort; ohne
  Live-Vorschau wechselt ein Klick den laufenden Titel nicht. **↑/↓** wechseln den Titel, egal wo der Fokus gerade ist
  (ausser in mehrzeiligen, Auswahl- und Zahlenfeldern). **←/→** springt taktweise (vier Schläge, mit Beatgrid oder BPM-Näherung), **Shift+←/→** zum vorherigen/nächsten Cue; Klick in die Leiste springt.
- **Tempo von Hand:** Klick auf die BPM-Anzeige → neues Tempo eingeben (50–200 %), **Reset** = Original-Tempo; gilt
  nur für den laufenden Titel, an der Datei ändert sich nichts. Der Knopf neben dem Titel (**Im Tagger zeigen**)
  wechselt zum Tagger und markiert den laufenden Titel.
- **Startpunkt** per Umschalter: Start, 30 %, 1:00 oder erster Cue – praktisch zum schnellen Durchhören. Lautstärke
  wird gemerkt. Bei Titeln mit Cue-Punkten springen zwei Knöpfe zum vorigen/nächsten Cue.
- **Wellenform:** wird beim ersten Abspielen einmal berechnet und im Cache abgelegt (`~/TagStudio/cache/wave`,
  bleibt beim Bearbeiten der Tags und Umbenennen gültig); im Menü ⋯ bzw. in den Einstellungen abschaltbar.
- **Cue-Marken** aus Serato (Cues und Loops mit Farbe und Name) und Mixed In Key über der Leiste: Klick springt
  hin, **Shift+←/→** zum vorigen/nächsten Cue (Rücksprung ignoriert Cues innerhalb der letzten vier Takte). Ein Klick auf eine **Loop-Marke** spielt den Loop als Schleife
  (erneuter Klick beendet sie); beim Überfahren der Leiste stehen Zeit und Cue-Name.
- Zwischen Wellenform und Startpunkt: **Tonart** (Camelot-Kennzeichen plus musikalisch und Open Key), **BPM**,
  Laufzeit, **Restlaufzeit** (blinkt in den letzten 30 Sekunden rot) und Länge. Taste **M** schaltet stumm.
- **Stems:** Bei Titeln mit Stems wählt der Knopf neben dem Titel (oder **S** / Shift+S) zwischen Original und den
  Spuren – die Wiedergabe läuft **an derselben Stelle** weiter.
- **Titel wiederholen** (🔁 bzw. **R**) und **A–B-Schleife** (Knopf „A–B“ bzw. **L**: A setzen, B setzen,
  aufheben; **Esc** hebt auf).
- **A/B im Vergleich:** L/R wechselt zwischen linker und rechter Datei **an derselben Stelle**.
- **Bewertung und Like:** Sterne und ♥ neben dem Titel im Player, Tasten **0–5** (gleicher Stern nochmals: löschen)
  und **F**. Die Bewertung steht im Feld **POPM** (wie Windows Media Player, MusicBee, Mp3tag; vorhandene POPM-Frames
  werden angepasst, der Wiedergabezähler bleibt) und – falls vorhanden – in `TXXX:FMPS_Rating`; das Like steht als
  `{"like":true}` in `TXXX:TAGSTUDIO`. Im Tagger stehen die Sterne neben der Länge (auch für mehrere markierte Titel)
  und klein in der Liste. Änderungen lassen sich rückgängig machen und werden mit „Speichern“ geschrieben.
- **Überblenden** (Einstellungen → Player oder ⋯): am Titelende gleichmässig (gleiche Leistung) in den nächsten
  Titel überblenden, **1–30 s in 1-Sekunden-Schritten** (0 = aus); der nächste Titel startet ab Startpunkt, Anfang oder erstem Cue; wahlweise schon nach
  15 s … 2 Minuten (zum schnellen Durchhören). Nicht bei „Titel wiederholen“ oder einer Schleife.
  **Tempo angleichen** (Standard an): der nächste Titel läuft während des Überblendens im BPM des laufenden
  (Tonhöhe bleibt, höchstens ±10 %, halbes/doppeltes Tempo wird erkannt; ohne BPM-Feld kein Angleichen) und gleitet
  danach in der eingestellten Zeit (sofort … 1 Minute) auf sein eigenes BPM zurück.
  **Latenz-/Phasenkorrektur (Testfunktion):** Einstellungen → Player → „Folgetrack-Korrektur (ms)“ oder
  ⋯ → „Latenzkorrektur“: −500 bis +500 ms, 0 = aus. **Plus** verschiebt die Beats des folgenden
  Titels später, **Minus** früher. Die Einstellung wird gespeichert und bei allen automatischen Übergängen
  mit aktivem „Im Takt“ und kompatiblen Beatgrids angewendet. Dies ist ein Phasenversatz, kein
  tatsächliches Pausieren des Folgetracks und kein Beweis für eine konstante Decoder-Latenz.
  **Im Takt** (Standard an): bei brauchbarem Beatgrid wird die Phase beim tatsächlichen Start des neuen
  (anfangs stummen) Titels an den laufenden Titel angepasst. „Überblenden auf Taktgrenze“ plant zunächst
  den nächsten Takt (4), 8 Schläge oder die nächste Phrase (16); Lade- und Decoderverzögerungen
  können den tatsächlichen Beginn jedoch verschieben. Ohne verlässliches Beatgrid ist nur Tempo-Sync möglich.
- **Beatgrid:** aus Serato (`GEOB:Serato BeatGrid`), sonst aus dem Audio ermittelt (mit der Wellenform, im Cache
  gemerkt), notfalls geschätzt aus dem BPM-Feld mit dem ersten Cue als Schlag. „Tonhöhe beibehalten“ (Einstellungen ›
  Player) lässt sich ausschalten – dann ändert sich die Tonhöhe mit dem Tempo wie beim Plattenspieler.
  Die Wellenform zeigt Rasterlinien (Takt/Phrase kräftiger, geschätzte blasser). **Sync** in Player B bringt ihn ins
  Tempo und – mit Beatgrid – in den Takt von Player A.
  **Metronom bei Übergängen:** Ist das Metronom für A aktiviert, bleibt es beim
  automatischen Crossfade bis zum vollständigen Ausblenden mit dem Beatgrid des alten
  Titels verbunden; anschliessend wechselt es automatisch auf das neue Raster. Es
  bleibt auch aktiv, wenn das neue Raster erst durch die Audioanalyse verfügbar wird.
  Player B bleibt unabhängig.
  **Metronom-Lautstärke (ab nächster Beta):** Einstellungen → Player → Metronom-Lautstärke (0–100 %,
  Standard 80 %) oder über das Player-Menü für A/B. Der Klick ist obertonreicher und besser hörbar;
  Änderungen wirken während des Abspielens sofort. Gemeinsam für beide Player, unabhängig von der
  Track-Lautstärke. Bei Kopfhörern am besten niedrig beginnen; noch kein neues Beta-Release freigegeben.
- **Player oben** (Einstellungen → Player → Position oder Regler-Menü): eigene Leiste über der Seite mit voller Breite
  und grösserer Wellenform; Knopf ˄ bzw. **Shift+P** klappt sie ein (je Player eine Zeile mit ▶/⏸, Titel und
  Restlaufzeit).
- **Fortsetzen:** Beim Start lädt der Player den zuletzt gehörten Titel (A und B) in Pause an derselben Stelle,
  sofern er im geladenen Tagger-Ordner liegt; abschaltbar in Einstellungen › Player. „Nach dem Neustart“ wählt
  Pause, Autoplay oder „abspielen, wenn er beim Schliessen lief“.
- **Player B** (nur mit Player oben, Regler-Menü oder Einstellungen): zweiter, unabhängiger Player unter Player A zum
  Vorhören – gleich aufgebaut (⏮/⏭, Cues, Wiederholen, A–B, Bewertung, eigener Startpunkt und Lautstärke, L/R im
  Vergleich) und mit eigenem **Ausgabegerät** im Menü (wenn das System es erlaubt), z. B. Kopfhörer. Rechtsklick auf
  einen Titel → „In Player B laden“ – oder den Titel (aus Tagger, DJ-Set oder ein Paar aus dem Vergleich) einfach auf
  Player A oder B **ziehen**. Läuft gerade ein Player, wird der gezogene Titel in Pause geladen. Ein Klick auf die Beschriftung **A** bzw. **B** ganz vorne (oder Taste **B**)
  legt fest, worauf Markierung, Leertaste, Doppelklick und Tasten wirken.
- **Abdocken** (Knopf ⧉): der Player – mit Cover und, wenn eingeschaltet, auch Player B – erscheint in einem
  eigenen Fenster, z. B. auf dem zweiten Bildschirm; die
  Wiedergabe läuft an derselben Stelle weiter, Markierung, ↑/↓ und Leertaste im Hauptfenster steuern ihn weiter.
  Grösse und Position werden gemerkt; Schliessen des Fensters (oder „Andocken“) holt ihn zurück.
- **Standard-Einstellungen** (Einstellungen → Player): „Aktuelle als Standard speichern“, „Auf Standard
  zurücksetzen“ und „Nach dem Start: zuletzt benutzte / immer die Standard-Einstellungen“.
- **Externe Player** (⋯ bzw. **Strg/Cmd+P**): markierte Titel in foobar2000, VLC, Rekordbox, Music … öffnen; ohne
  Einrichtung im Standardprogramm des Systems. Unter „Externe Player…“ beliebig viele Programme mit Argumenten
  (`{files}` alle Dateien, `{file}` erste, `{folder}` Ordner, `{m3u}` temporäre Playlist).
- Die Wiedergabe läuft über einen lokalen Mini-Server (nur 127.0.0.1, nur freigegebene Dateien, zufälliges Token).

### Snapshots & Änderungsjournal

Für Bibliotheken, die auch andere Programme bearbeiten (Mp3tag, beaTunes, Mixed In Key, Platinum Notes, Rekordbox …):
- **Ordner überwachen** und **Snapshots** erstellen – der Tag-Zustand aller Titel wird byte-genau festgehalten,
  ohne Audio. Jeder Frame wird nur einmal gespeichert; weitere Snapshots kosten nur, was sich geändert hat.
  Snapshots lassen sich benennen („Vor Mixed In Key“), anheften (werden nie aufgeräumt) und löschen.
- **Journal:** Snapshot ↔ jetzt (oder zwei Snapshots) – geänderte, neue, entfernte, umbenannte Titel und Titel mit
  geändertem Audio; je Titel alle Felder alt/neu mit Herkunfts-Kennzeichen und dem **vermutlichen Programm**
  (z. B. Mixed In Key bei Tonart + Energy). Filter nach Status, Programm und Feld, Suche nach Titel, Feld oder Wert;
  „Sichtbare auswählen“ wählt z. B. alle Tonart-Änderungen von Mixed In Key zum Zurücksetzen aus. ⇄ öffnet den Titel
  im Vergleich.
- **Zurücksetzen:** einzelne Felder oder ganze Titel ankreuzen → „Auswahl zurücksetzen“ (Rückgängig möglich, wird
  mit „Speichern“ geschrieben) oder „Byte-genau zurückschreiben“ (exakt der Snapshot-Stand inkl. Serato-/Cue-Daten,
  vorher Sicherung; Titel mit geändertem Audio werden übersprungen).
- **Mehrere Ordner** mit Farbe, eindeutigem Namen und Pfad; Anzeigename und Ordner änderbar, täglicher Snapshot je
  Ordner abschaltbar. Solange kein Ordner überwacht wird, weist TagStudio beim Start darauf hin.
- **Automatik:** einmal täglich ein Snapshot je Ordner, beim Start die Frage mit der Zahl geänderter Titel (beides
  abschaltbar). Aufräumen: 20 automatische + je einer pro Woche der letzten 12 Wochen (einstellbar).
- **Speicherplatz** je Snapshot, je Ordner und gesamt; die Summe steht auch in der Seitenleiste.
- **⚑ Neue Baseline:** den aktuellen Stand (neuer Snapshot) oder einen vorhandenen Snapshot als neuen Ausgangspunkt
  setzen und dabei ältere Snapshots löschen; angeheftete nur, wenn ausdrücklich gewählt. Die Baseline ist
  gekennzeichnet und wird beim Aufräumen nie gelöscht.
- **Überwachung während TagStudio läuft:** alle 5 Minuten (einstellbar) ein sparsamer Blick auf Grösse und
  Änderungszeit; „n Titel extern geändert“ in der Fussleiste öffnet das Journal. Eigene Speicherungen zählen nicht.
- **Im Vergleich:** links oder rechts einen **Snapshot** wählen (📷 neben dem Pfad) – schreibgeschützt, Werte gehen nur
  in Richtung der echten Dateien. Zuordnung **„Audio-Inhalt“** findet auch umbenannte und verschobene Titel.
- **Speicherort ändern:** Der ganze Speicher wird kopiert, geprüft und erst dann am alten Ort entfernt – z. B. in den
  MP3-Ordner (`.tagstudio-snapshots`), um ihn samt Historie weiterzugeben. Wird ein Ordner mit einem solchen Speicher
  eingelesen, bietet TagStudio an, ihn zu verwenden.
- **Protokoll** je Snapshot-Auftrag in `Logs/snapshots.log`: Start, Ende, Dauer, Titel, Fehler und Speicherplatz.
- Unabhängig davon schützt TagStudio beim **Speichern** vor dem Überschreiben fremder Änderungen: es zeigt, was ein
  anderes Programm seit dem Einlesen geändert hat, und übernimmt es auf Wunsch zusammen mit den eigenen Änderungen.

Konzept: [docs/KONZEPT-SNAPSHOTS.md](docs/KONZEPT-SNAPSHOTS.md).

### Sicherungen

Alle Sicherungen mit Dateien, Status (wiederherstellbar/gleich/fehlt/Audio geändert) und **geänderten Feldern**.
Klick öffnet den **Änderungs-Viewer**: jedes Feld „Vorher (Sicherung)“ und „Jetzt“, geändert/neu/entfernt markiert,
abweichende Zeichen hervorgehoben; mit ‹ › blättern und einzelne Dateien direkt wiederherstellen. Ausserdem
markierte oder alle wiederherstellen (vorher wird der aktuelle Stand selbst gesichert), Sicherung löschen,
automatische Sicherung ein/aus, Ordner ändern/öffnen.

### Plugins

Seite „Plugins“: Erweiterungen ein-/ausschalten, fehlende Pakete per Knopf installieren; Aktionen erscheinen im
Tagger unter „Plugins“. Vorschläge von Plugins (z. B. Beatport) erscheinen erst als **Vorschau mit Häkchen**.

- **Stems:** trennt Titel in Gesang, Schlagzeug, Bass, Instrumental … (audio-separator, eigene Python-Umgebung,
  Varianten CPU/DirectML/NVIDIA). Läuft **im Hintergrund**: der Dialog schliesst sofort, unten in der Fussleiste
  steht der Fortschritt („Stems: 2 von 7 · 45 %“), ein Klick zeigt alle Aufträge (Abbrechen, Ordner, Protokoll).
  Weitere Aufträge werden hinten angestellt, beim Beenden wird nachgefragt und die Warteschlange beim nächsten
  Start zum Fortsetzen angeboten. Im Tagger hängen die Spuren **aufklappbar unter dem Original** (▸, →/←,
  Umschalt-Knopf „Stems“ für alle): MP3-Spuren bearbeiten, FLAC/WAV anhören; „Stems: Tags vom Original …“ überträgt die Tags.
- **Beatport:** BPM, Tonart, Genre, Label, Katalognummer, ISRC, Remixer, Cover u. a. über die offizielle
  Beatport-API mit deinem eigenen API-Zugang (Ausweichweg: dein Beatport-Login; Passwort wird nie gespeichert). Die Vorschau zeigt **alle gelieferten Felder** – gleiche
  grau, abgewählte und schon gefüllte ungehakt. Eigene **Beatport-Playlists** holt Playlists › Importieren ▾ › „Aus
  Beatport …“ (Einträge ohne Datei mit Link, nur lesen).
- **Online-Metadaten:** Album, Datum, Label, Katalognummer, ISRC, Genre, Cover u. a. von MusicBrainz (auch per
  AcoustID-Fingerabdruck), Deezer, Spotify, iTunes, SoundCloud, Discogs und Last.fm. Standard: nur leere Felder ergänzen; je Feld ist die
  erste Quelle vorausgewählt, andere erscheinen als Alternative. Discogs-Token, Last.fm- und AcoustID-Schlüssel unter
  Plugins › Online-Metadaten › „Schlüssel …“ (verschlüsselt gespeichert); „Verbindungen testen“ prüft die Dienste.
- **Spotify und SoundCloud (nur lesen, eigene App beim Dienst):** Playlists, Lieblingssongs bzw. Likes als Playlists
  mit Einträgen ohne Datei (Playlists › Importieren ▾), Titel-Daten mit Link für die Online-Metadaten und gefolgte
  Künstler für „Entdecken“. Einrichtung in [PLUGINS.md](PLUGINS.md).
- **Mixed In Key übernehmen:** Tonart, BPM und Energie aus den Stellen, an die Mixed In Key sie geschrieben hat
  (Kommentar „10A - Energy 7“, Titel- oder Künstler-Präfix, Gruppierung, Label, TXXX:EnergyLevel) in TKEY, TBPM und
  ENERGY übernehmen; Präfixe auf Wunsch entfernen.
- **beaTunes übernehmen:** MOOD_DANCEABILITY, MOOD_ACOUSTIC, MOOD_HAPPY, MOOD_AGGRESSIVE (von beaTunes in die Dateien
  geschrieben) als Audio-Merkmale. **Lexicon übernehmen:** Tanzbarkeit, Energie, Fröhlichkeit, auf Wunsch Bewertung,
  Popularität, Farbe und Custom Tags über die Lexicon Local API (Zuordnung über Pfad bzw. Künstler + Titel). Beide mit
  **Abgleich**: Wurde ein Wert in der Datei seit dem letzten Übernehmen geändert, ist der Vorschlag nicht angehakt –
  TagStudio fragt. Lexicon zusätzlich: markierte Titel und Playlists öffnen, auf Wunsch Pfade nachführen, neue Titel
  aufnehmen, Tags zurückschreiben und **Playlists senden** (Playlists › Mehr ▾ › „An Lexicon senden …“: legt die
  Playlist in Lexicon an, erneutes Senden fügt fehlende Titel an ihrer Stelle ein und entfernt nichts; nur mit
  eingeschaltetem Zurückschreiben, siehe [PLUGINS.md](PLUGINS.md)).
- **Lautheit messen:** LUFS, True Peak, Lautheitsbereich (EBU R128, FFmpeg) als Felder, optional angeglichene Kopie.
- **Protokolle:** Bei jedem Plugin unter **Mehr …** „Log-Ordner öffnen“ und „Protokoll live anzeigen …“ – ein eigenes
  Fenster, das das Protokoll laufend nachführt; Zeilen eines laufenden Vorgangs erscheinen sofort („läuft“).
- **Eigene Plugins** in `~/TagStudio/Plugins` – Anleitung in [PLUGINS.md](PLUGINS.md).

### Update, Layout, Tastatur

- **Update:** „Nach Update suchen“ unten in der Seitenleiste; TagStudio prüft beim Start selbst (Punkt am Knopf).
  Unter Einstellungen › Updates: **nur offizielle Versionen** oder **auch Beta-Versionen**. Die installierte App
  zeigt die neue Version mit ihren Hinweisen; unter Windows lädt **„Jetzt aktualisieren“** den Installer, prüft ihn,
  installiert still und startet TagStudio neu (macOS: Installer herunterladen). In der Quellcode-Variante
  lädt ein Klick die neue Version (`git`, nur Vorspulen, nur ohne eigene Änderungen im Programmordner; bis zur
  neuesten offiziellen bzw. Beta-Version) und startet neu; ungespeicherte Änderungen werden vorher abgefragt. Nur im
  Quellcode gibt es zusätzlich den Kanal **Entwicklung** (jede Änderung auf `main`, angezeigt als „Developer Release“
  mit der geplanten Versionsnummer).
- **Fenster und Programm:** ganz unten in der Seitenleiste Vollbild (auch F11), Fenstermodus (zurück aus Vollbild
  bzw. maximiert), Neu starten und Beenden. Beim Beenden – auch über das X des Fensters – erscheint kurz
  „Einstellungen werden gespeichert …“; ungespeicherte Änderungen und laufende Aufträge werden vorher abgefragt.
  Es läuft immer nur **eine Instanz**; ein zweiter Start meldet „TagStudio läuft bereits“.
- **Versionshinweise:** unter dem Update-Knopf – was in der installierten Version neu ist und, falls vorhanden,
  in der neuesten; darunter „Weitere Versionen“ mit allen älteren Versionen zum Aufklappen; mit Link zu GitHub.
- **Splitter:** Seitenleiste, Paarliste, Tabellenspalten, Bearbeitungsbereich und Feldnamen-Spalte lassen sich
  ziehen (oder mit ←/→ auf dem Griff); Doppelklick setzt zurück, alles wird gemerkt. Die Seitenleiste lässt sich
  einklappen.
- **Tastatur** (vollständige Liste: Hilfe › Tastatur): Strg/Cmd+S speichern · Strg/Cmd+Z / Strg+Y rückgängig/wiederholen · Alt+← / Alt+→ Markierte
  kopieren · Strg/Cmd+A alles markieren · Leertaste abspielen · Doppelklick abspielen · 0–5 Bewertung · F Like · B Player A/B · Shift+P Player-Leiste ein/aus · ↑/↓ Titel wechseln (überall) · S Stem-Spur · R wiederholen · L A–B-Schleife · ←/→ einen Takt (Player) · Shift+←/→ voriger/nächster Cue · Shift+F5 Paar neu einlesen · Strg/Cmd+P externer Player · →/← Stems auf-/zuklappen (Tagger-Liste) · F5 neu einlesen · ↑/↓ in Listen · Esc schliesst Dialoge.

## Einstellungen und Datenablage

**Speicherort und Ordner (Ordner-Rollen, ab 4.10):** Unter Einstellungen › Speicherort und Ordner wird jeder Ordner
**genau einmal** festgelegt – als **Rolle**: Eingang · Bibliotheken · Archiv · Playlists · **Export** · Downloads ·
Arbeit · Sicherung · Snapshots. Standard ist der **Basisordner** (z. B. `D:\TagStudio`, jede Ordnerauswahl beginnt
dort) mit der Struktur `00_New` (neue Musik, Unterordner je Quelle) · `01_Library` (Bibliothek) · `02_Archiv`
(aussortiert) · `03_Playlists` (M3U8) · `04_Export` (Startordner aller Exporte: jeder Speichern-Dialog – Tagger-Liste, Playlists, DJ-Set, Merkliste, Journal, Einstellungen, Workflow, Cover – öffnet dort; fehlt der Ordner, wird er angelegt) · `90_Download` (Downloads,
Unterordner je Quelle) · `91_Work` (Stufen-Ordner) · `99_Sicherung` (`Tags`, `Snapshots`). Jede Rolle lässt sich mit
„Ändern …“ auf einen **eigenen Ordner** umstellen (auch anderes Laufwerk) und wieder zurück auf „Basis“; Sicherung
und Snapshots können wie bisher in den Programmdaten bleiben. Es gibt **mehrere Bibliotheken** (je mit Name,
aktiv/inaktiv, genau eine **Hauptbibliothek**); Überschneidungen (eine Bibliothek in einer anderen, derselbe Ordner
über einen anderen Weg) werden angezeigt und beim Einlesen nur einmal gelesen. **Aktive** Bibliotheken nutzen
Käufe-Abgleich, Playlist-Abgleich, Entdecken („schon vorhanden“) und Hilfe › Scan; „Verglichen mit“ zeigt ihre Namen
(Klick → Einstellungen), nicht erreichbare werden übersprungen und genannt. Der Tagger zeigt ab zwei aktiven
Bibliotheken die Auswahl **„Bibliothek ▾“** mit **„Alle aktiven“** (lädt alle zusammen); Vorbereiten übernimmt ohne
eigenen Bibliotheksordner in die Hauptbibliothek. Der Schalter **Snapshots** je Bibliothek schaltet den täglichen
Snapshot ein bzw. aus (vorhandene Snapshots bleiben). Jede Ordnerauswahl (Tagger, Vergleich, Workflow, Käufe, Standardordner)
öffnet ein **Klappmenü** mit Bibliotheken, Rollen, zuletzt benutzten Ordnern, „Anderer Ordner …“ und „Neuer Ordner …“.
**Unterordner je Quelle:** Wird ein Store-Plugin (z. B. Beatport) eingeschaltet, entstehen `90_Download\Beatport`
und `00_New\Beatport`, der Workflow bekommt die Quelle „Beatport“ (Abholen: Download-Unterordner → Eingangs-
Unterordner), Käufe-Downloads landen in `90_Download\Beatport`; manuelle Downloads gehören nach
`90_Download\_Manuell`. Workflow-Felder Eingang, Arbeit und Bibliothek dürfen leer bleiben – dann folgen sie den
Rollen (Eingang, Arbeit, Hauptbibliothek). **Cloud (OneDrive, Google Drive, Dropbox):** Rollen und Bibliotheken dürfen in einem
Ordner liegen, den der Desktop-Client synchronisiert – TagStudio erkennt ihn („☁ OneDrive“), speichert den Pfad
zusätzlich relativ zum Sync-Ordner (gilt auch auf einem zweiten Rechner), überspringt beim Einlesen **Nur-online-
Dateien** („Dateien bei Bedarf“, nichts lädt unbemerkt herunter – auf Wunsch einschaltbar) und meldet
**Konfliktkopien** des Clients. Snapshots, Arbeit und Sicherung im Sync-Ordner bekommen einen Hinweis (nicht
empfohlen). „Ändern …“ (auch beim Basisordner) zeigt, was im bisherigen Ordner liegt (Dateien,
Grösse, freier Platz, gleiche Namen am Ziel) und fragt **Verschieben / Kopieren / Nicht übernehmen** – bei
Bibliotheken ist „Nicht übernehmen“ vorgewählt, mit Hinweis, dass Engine DJ, Lexicon, Rekordbox, Serato und
VirtualDJ ihre Pfade danach selbst suchen müssen (TagStudio ändert keine fremden Datenbanken). Nie wird etwas
überschrieben („Ziel behalten“ oder „Name (2)“); auf demselben Laufwerk wird umbenannt, über Laufwerke kopiert, per
SHA-256 geprüft und erst dann das Original entfernt. Der Auftrag ist abbrechbar ohne halbe Dateien; Verweise in
Playlists (M3U8 neu), Käufen, Snapshots, `_aussortiert.csv`, Vorbereiten, Verlauf und Warteschlange werden
nachgeführt; Protokoll `Ordnerwechsel.csv` im Export-Ordner; ein leer gewordener alter Ordner wird nur auf
Rückfrage gelöscht. „Struktur anlegen …“ legt fehlende Ordner an. Beim ersten Start nach dem Update werden die bisherigen Einstellungen
übernommen; war die Bibliothek an verschiedenen Stellen verschieden eingetragen, zeigt TagStudio die Übersicht
**„Diese Ordner haben wir gefunden“** zur Entscheidung (nichts wird still verworfen). Konzept:
[docs/KONZEPT-ORDNER.md](docs/KONZEPT-ORDNER.md). TagStudio sichert nur Tags – die Musik selbst zusätzlich auf ein
anderes Laufwerk sichern. Alle Ablageorte im Überblick: [docs/KONZEPT-SPEICHER.md](docs/KONZEPT-SPEICHER.md).

**Profile:** Unter Einstellungen › Profile lässt sich ein weiteres Profil anlegen – eine unabhängige TagStudio-Instanz
mit eigenen Einstellungen und Daten (unter `~/TagStudio-Profile/<Name>/`). Ein leeres Profil startet wie eine frische
Installation mit dem **Einrichtungsassistenten**. Plugins, die Stems-Umgebung und Modelle werden mitbenutzt. Gestartet
wird über die Profilwahl beim Start, eine Desktop-Verknüpfung oder `--profil Name`; das Standardprofil benutzt wie
bisher `~/.tagstudio.json` und `~/TagStudio`.

Die Seite **Einstellungen** fasst alles zusammen – Kacheln in der Reihenfolge des Menüs, oben Sprungmarken:
Darstellung · **Tagger** (Standardordner, Stems; *beim Start:* automatisch einlesen, Unterordner, Sortierung,
Cover-Spalte, Herkunfts-Filter) · Tag-Fixer · **Vergleich** (Standardordner; *beim Start:* Unterordner, Zuordnen nach,
Anzeige, Unwichtige, Leere Felder, Cover – weicht der Vergleich davon ab, setzt ⌂ „Standard“ ihn zurück) ·
Snapshots · Sicherungen und Speichern (ID3-Version, Sicherung) · Player · Plugins · Herkunft der Tags · unwichtige
Felder · Cache · Updates · **Expert** (Diagnose mit Version, System und Pfaden zum Kopieren, Einstellungsdatei und
Protokolle ansehen und durchsuchen – Zugangsdaten ausgeblendet). Jede Vorgabe „beim Start“ kann auch „wie zuletzt benutzt“ bleiben. **Exportieren**
speichert alles als Datei (ohne Zugangsdaten), **Importieren** übernimmt gewählte Bereiche – Pfade eines anderen
Systems sind nicht vorgewählt –, **Zurücksetzen** geht für einzelne Bereiche oder alles. Vor Import und
Zurücksetzen wird die alte Datei nach `~/TagStudio/Einstellungen` gesichert.

**Sprache:** Einstellungen › Darstellung › Sprache oder die Auswahlliste unten in der Seitenleiste (unter „Einklappen“)
wechselt zwischen Deutsch, Englisch und Zürichdeutsch; „Sprache des Betriebssystems verwenden“ folgt der Sprache von
Windows bzw. macOS und ist beim allerersten Start aktiv. Tags in den MP3-Dateien werden nie übersetzt. „Texte
exportieren“ speichert alle Texte als CSV oder JSON für eigene Übersetzungen oder Korrekturen; „Texte importieren …“
prüft die Datei (unbekannte Texte, Platzhalter, HTML) und legt sie als eigene Texte in
`~/TagStudio/Sprachen/<sprache>.json` ab; „Eigene Texte zurücksetzen“ entfernt sie wieder. Die Hilfe zeigt auf Englisch
die englischen Fassungen von Handbuch, ID3-Feldern und Plugin-Anleitung. Auch die Dateidialoge (Dateitypen, Titel)
und die Fenstertitel von Player und Protokollen folgen der gewählten Sprache.

Gespeichert wird in `~/.tagstudio.json`. Weitere Ordner unter `~/TagStudio`:

| Ordner | Inhalt |
|---|---|
| `Sicherungen` | automatische Sicherungen der Tags (ZIP je Speichervorgang, Ordner änderbar) |
| `cache` | Cover-Vorschaubilder, Wellenformen (`wave`) |
| `Einstellungen` | Sicherungen der Einstellungsdatei vor Import/Zurücksetzen |
| `Plugins` | eigene Plugins |
| `Plugin-Daten` | z. B. Stems-Umgebung und Modelle, Beatport-Token (unter Windows verschlüsselt) |
| `Logs` | App-Protokoll `app.log` (Start, Ende, Fehler, Warnungen; ab 1 MB `app.log.1`), Protokolle von Plugins und Installationen |
| `Sprachen` | eigene Texte je Sprache |
| `Auftraege.json` | offene Hintergrund-Aufträge (zum Fortsetzen nach einem Neustart) |
| `Snapshots` | Snapshots überwachter Ordner (Speicherort einstellbar) |

Daneben liegt `~/.tagstudio.lock`: solange TagStudio läuft, gesperrt (nur eine Instanz).

Die unwichtigen Felder (`"trivial"`, Platzhalter `*`) und eigene Herkunfts-Zuordnungen (`"tag_origins"`) lassen sich
in den Einstellungen bearbeiten.

## Technisches

**Praxistest (Version 2.5):** 1'493 Dateien einer echten DJ-Bibliothek (ID3v2.4, Beatport/beaTunes/Mixed In Key/Serato)
wurden eingelesen sowie auf Kopien neu geschrieben, zwischen v2.4 und v2.3 umgewandelt und einzeln geändert –
ohne Lesefehler, ohne Datenverlust, Audio jeweils byte-identisch.

- Liest ID3v2.2/2.3/2.4 und ID3v1, schreibt in der vorhandenen Version (v2.3 bei Dateien ohne Tag).
- Unveränderte Felder werden byte-genau zurückgeschrieben, Audiodaten nie angefasst.
  Wächst der Tag, wird über eine temporäre Datei geschrieben und erst danach ersetzt.
- Beim Kopieren zwischen v2.3 und v2.4 werden Felder korrekt umgewandelt (z. B. Datum TDRC ↔ TYER/TDAT);
  ID3v2.4-Mehrfachwerte werden in v2.3 mit „ / “ verbunden.
- **DJ-Daten** (GEOB-Objekte wie *Serato Markers2*, Mixed-In-Key *Key/Energy/CuePoints*, *PlatinumNotes*) werden
  nach ihrer Beschreibung zugeordnet, lesbar angezeigt und unverändert erhalten, solange man sie nicht bewusst
  bearbeitet. Im Vergleich gelten sie standardmässig als „unwichtig“, da Cue-Punkte/Beatgrids zu genau einem Track
  gehören.
- Tipp: Vor dem ersten Einsatz an einer Kopie der Musik ausprobieren.

## Dateien

- `tagstudio_web.py` + `web/` – die App (HTML/CSS/JS im App-Fenster über pywebview, sonst im Browser);
  `web/xmleditor.js` XML-Editor, `web/jsontree.js` JSON-Baum, `web/tagger.js` Tagger und Editoren,
  `web/keywheel.js` Camelot-Rad, `web/features.js` Audio-Merkmale, `web/plugins.js` Plugin-Seite,
  `web/player.js` Vorschau-Player, `web/player2.js` Überblenden, Player oben, Player B, Abdocken,
  `web/player-window.html` + `web/playerwin.js` abgedocktes Player-Fenster, `web/settings.js` Einstellungen, `web/jobs.js` Hintergrund-Aufträge,
  `web/djset.js` Seite „DJ-Set“, `web/playlists.js` Seite „Playlists“
- `core.py` – gemeinsame Logik: Anzeige, Zeichen-Diff, Filter, Laden, Speichern, Einstellungen
- `session.py` – Zustand und Befehle einer Sitzung; Teile in `session_player.py` (Player, Fenster-Nachrichten,
  Wiedergabe), `session_snapshots.py` (Snapshots, Journal), `session_djset.py` (DJ-Set) und `session_playlists.py`
  (Playlists)
- `id3tags.py` – ID3 lesen/schreiben, MPEG-Infos (ohne externe Bibliotheken)
- `compare.py` – Zuordnung, Vergleich, Kopieren, Regeln für unwichtige Felder
- `tagger.py` – Tagger-Logik: gemeinsame Felder, Tags aus Dateiname, Umbenennen, Spurnummern, Cover,
  Gross-/Kleinschreibung, Suchen & Ersetzen, Cover aus Ordner, Export (CSV/Excel ohne Zusatzpakete)
- `keys.py` – Tonarten: erkennen, umschreiben (Camelot, musikalisch, Open Key), passende Tonarten
- `features.py` – Audio-Merkmale (TXXX, 0–100; Dateien wahlweise 0–10)
- `setplan.py` – DJ-Set: Übergänge bewerten, Reihenfolge optimieren (Held-Karp bzw. Greedy + 2-opt);
  `setexport.py` – Exporte M3U8, Rekordbox-XML, CSV
- `playlists.py` – Playlists: Speicher, Ordner, Rückgängig, Archiv, Playlist-Ordner (M3U8), Änderungen von aussen
- `xmltools.py` – XML in Feldern und Binärfeldern erkennen, prüfen, formatieren, ersetzen
- `blobs.py` – Binärfelder (GEOB/PRIV): Inhalt erkennen (XML, Text, Base64, binär) und byte-genau ändern
- `backup.py` – Sicherung und Wiederherstellung der Tags, Vergleich Sicherung ↔ Datei (Änderungs-Viewer)
- `undo.py` – Rückgängig/Wiederholen
- `media.py` – lokaler Audio-Server für den Player (Range-Anfragen, Token); `players.py` – externe Player
- `ratings.py` – Bewertung (POPM, FMPS_Rating) und Like (TXXX:TAGSTUDIO)
- `prepare.py`, `session_prepare.py`, `web/prepare.js` – Tracks vorbereiten (Workflow, Schritte, Schutzregel, Übernahme)
- `recipes.py`, `web/recipes.js` – Tag-Rezepte (Aktionslisten wie in Mp3tag)
- `taghelp.py`, `session_help.py` – Hilfe: Tag-Übersicht, Bibliotheks-Scan mit Zählern (Cache), Feld-Filter
- `i18n.py`, `web/i18n.js`, `web/i18n/` – Mehrsprachigkeit: Kataloge (Schlüssel = deutscher Text), Übersetzung der
  Oberfläche, eigene Texte; `tools/i18n_extract.py` prüft, ob alle Texte übersetzt sind
- `id3frames.py` – Katalog aller ID3-Frames, lesbare Binär-Frames; Übersicht [docs/ID3-FELDER.md](docs/ID3-FELDER.md)
- `moods.py` – Stimmung (TMOO bzw. TXXX:MOOD) mit Mehrfachwerten und Vorschlägen
- `importsync.py` – Abgleich für Importer (beaTunes, Lexicon): zuletzt übernommene Werte in TXXX:TAGSTUDIO
- `cues.py` – Cue-Punkte aus Serato/Mixed In Key lesen; `waveform.py` – Wellenform-Cache
- `origins.py` – Herkunft der Tags (Kennungsliste); `appsettings.py` – Einstellungen exportieren/importieren/zurücksetzen
- `jobs.py` – Warteschlange für Hintergrund-Aufträge; `stemsview.py` – Stems einem Original zuordnen
- `snapshots.py` – Snapshots (Frame-Speicher, Scan, Journal, Aufräumen); `web/snapshots.js` – Seite „Snapshots“
- `thumbs.py` – Cover-Vorschaubilder ohne Zusatzpakete
- `plugins.py` + `plugins/` – Plugin-System (siehe [PLUGINS.md](PLUGINS.md)); eingebaut: `plugins/stems`,
  `plugins/beatport`
- `updater.py` – Updates: GitHub-Releases (installierte App, Kanal offiziell/Beta) bzw. git (Quellcode, nur
  Vorspulen); Versionshinweise aus dem CHANGELOG
- `tagstudio.py` – klassische Oberfläche (tkinter, eingefroren auf Stand 3.0)
- `version.py` – Versionsnummer (einzige Stelle)
- `packaging/` – Installer: `build.py` (PyInstaller), `windows.iss` (Inno Setup), `make_dmg.sh` (macOS), Icon;
  `release.py` (neue Version vorbereiten)
- `.github/` – Workflows (Tests, Installer/Release, Releases aufräumen, CodeQL), Dependabot, Skripte für CodeQL-Issues
  und das Aufräumen alter Beta-Releases

## Entwicklung

- **Projektstand und Übergabe:** [docs/PROJEKTSTAND.md](docs/PROJEKTSTAND.md) (aktueller Stand, Arbeitsweise),
  [docs/UEBERGABE.md](docs/UEBERGABE.md) (Einstieg für eine neue Sitzung),
  [docs/PROJEKTSTAND-ARCHIV.md](docs/PROJEKTSTAND-ARCHIV.md) (Verlauf bis 3.5.0).
- **Konzepte:** je Bereich ein Dokument `docs/KONZEPT-*.md` (Tagger, Tag-Fixer, Vergleich, DJ-Set, Player, Plugins,
  Einstellungen, Hilfe, Update, App/Oberfläche, Vorbereiten, Snapshots, Einrichtung, Speicher …) – Übersicht in
  [docs/UEBERGABE.md](docs/UEBERGABE.md).
- **Präsentation zur Version 4.4** (Projektgeschichte und Highlights): [docs/TagStudio-Praesentation-4.4.pptx](docs/TagStudio-Praesentation-4.4.pptx).
- **Lizenzen und Fremdkomponenten:** [docs/third-party.json](docs/third-party.json) (Anzeige unter Hilfe › Lizenzen);
  der Workflow „Fremdkomponenten prüfen“ meldet monatlich neue Versionen und geänderte Lizenzen als Issue. Neue
  Bibliotheken, Plugin-Pakete oder übernommene Vorlagen dort eintragen.
- **Tests:** `python -m unittest discover -s tests -v` – ID3-Lesen/-Schreiben (v2.3/v2.4, Mehrfachwerte, BOM,
  GEOB, Datumsumwandlung), Vergleich, Tag-Fixer, Sicherung/Wiederherstellung, Sitzung der neuen Oberfläche,
  Tagger-Werkzeuge, Tonarten, Audio-Merkmale, XML und Binärfelder, Versionierung, Updater und Plugins (Stems und
  Beatport mit nachgebauter Gegenseite) – mit synthetischen MP3-Dateien, ohne Zusatzpakete und ohne Netz.
  Einzelne Datei: `python -m unittest tests.test_player`.
- **Oberflächen-Tests** im Browser (Playwright/Chromium, ffmpeg): `TAGSTUDIO_UI_TESTS=1 python -m unittest
  discover -s tests -p "test_browser_ui.py" -v` – Menü und Einstellungen, Player (Live-Vorschau, Doppelklick,
  Bewertung, Überblenden mit Tempo, Player B, Abdocken). Ohne die Variable werden sie übersprungen.
- **GitHub Actions:**
  - `tests.yml` – bei jedem Push die Tests mit Python 3.12 und 3.15 auf Windows, bei finalen Versionen zusätzlich macOS (Linux derzeit nicht vorgesehen), dazu ein Smoke-Test
    der klassischen Oberfläche.
  - `installer.yml` – baut und testet die Installer (Selbsttest der gebauten und der installierten App) und
    veröffentlicht bei neuer Versionsnummer das Release (siehe unten).
  - `codeql.yml` – Code-Scanning (Python, JavaScript, Workflows). Neue Funde werden automatisch als Issue mit den
    Labels `fehler`, `sicherheit`, `codeql` im nächsten Patch-Milestone angelegt und nach der Behebung geschlossen.
  - **Dependabot** hält die verwendeten Actions aktuell (monatlicher Pull Request).
- **Planung:** offene Punkte als [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues), geplante
  Versionen als [Milestones](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestones). Commits mit
  „Fixes #n“ schliessen das Issue automatisch.

## Versionen & Releases

**Schema MAJOR.MINOR.PATCH** ([Semantic Versioning](https://semver.org/lang/de/)), einzige Quelle: `version.py`.

| Teil | Wann erhöhen | Beispiel |
|---|---|---|
| PATCH | nur Fehlerbehebungen | 3.1.0 → 3.1.1 |
| MINOR | neue Funktionen (der Normalfall) | 3.1.1 → 3.2.0 |
| MAJOR | grosse Umbrüche, z. B. inkompatible Einstellungen/Datenbank | 3.4.2 → 4.0.0 |
| Vorabversion | zum Testen vor einer Version | 3.2.0-beta.1 |

**Ablauf**

1. **Laufend:** Jede Änderung kommt sofort in `CHANGELOG.md` unter **„Unveröffentlicht“**.
2. **Version festlegen**, wenn ein zusammenhängendes Paket fertig und getestet ist:
   `python packaging/release.py 3.2.0` – setzt `version.py`, `pyproject.toml` und die unterstützte Version in
   `SECURITY.md` und macht aus „Unveröffentlicht“ den Abschnitt „[3.2.0] – Datum“. Danach committen und auf `main`
   pushen.
3. **Automatisch veröffentlichen** – sobald die neue Versionsnummer auf `main` landet, baut GitHub Actions die
   Installer für Windows und macOS, testet sie und legt **selbst Tag `v3.2.0` und das Release „TagStudio 3.2.0“**
   mit dem Text aus dem CHANGELOG an. Ein von Hand gesetzter Tag (*Releases → Draft a new release*, Titel
   „TagStudio X.Y.Z“, Beschreibung leer) funktioniert weiterhin; der Workflow prüft dann, dass Tag und
   `version.py` übereinstimmen. Tags mit Zusatz (`v3.2.0-beta.1`) werden als **Vorabversion** veröffentlicht.
   Betas werden **nur für Windows** gebaut und getestet (macOS nur bei finalen Versionen oder beim Start von Hand mit „Auch
   macOS bauen“).
4. **Dringender Fehler:** sofort eine PATCH-Version auf demselben Weg.

`python packaging/release.py --check` prüft, ob Versionsnummer, `pyproject.toml`, `SECURITY.md` und CHANGELOG
zusammenpassen (läuft auch in den Tests).

**Kanäle:** In den Einstellungen wählbar – **nur offizielle Versionen** oder **auch Beta-Versionen**. Beta-Releases
einer Version werden automatisch von der Releases-Seite entfernt, sobald die finale Version erscheint (ihre Git-Tags
bleiben). Ein Git-Klon mit dem Kanal „Entwicklung“ folgt `main` und bekommt jede Änderung sofort.

**Zweige:** `main` ist immer lauffähig (die CI prüft jeden Commit). Grössere Vorhaben entstehen in kurzlebigen
Zweigen (`feature/…`) und werden nach `main` übernommen, wenn sie fertig sind.

## Fehler melden, Ideen, Sicherheit

- **Fehler und Wünsche:** als [Issue](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/new/choose) –
  die Vorlagen „Fehler melden“, „Funktion vorschlagen“ und „Plugin-Idee“ fragen Version, Betriebssystem, Schritte
  und Protokoll (`~/TagStudio/Logs`) gleich mit ab. Oder direkt in der App unter Hilfe › Melden.
- **Übersetzungen verbessern:** Einstellungen › Darstellung › Sprache → Texte exportieren, bearbeiten, importieren;
  dann „Eigene Texte einreichen …“ (oder Hilfe › Melden › „Übersetzung einreichen“) – die geänderten Texte werden ins
  GitHub-Formular eingefüllt und nach Prüfung mitgeliefert.
- **Mitmachen:** Entwicklungsumgebung, Richtlinien und Ablauf für Pull Requests in [CONTRIBUTING.md](CONTRIBUTING.md);
  es gilt der [Verhaltenskodex](CODE_OF_CONDUCT.md).
- **Sicherheitslücken** bitte nicht öffentlich, sondern privat melden – siehe [SECURITY.md](SECURITY.md).

## Ausblick

Zuletzt erschienen: **4.3.0 – Tracks vorbereiten, Entdecken, Hilfe** (Seite „Vorbereiten“ mit Workflow vom
Eingangsordner bis in die Bibliothek, Quellen, Schutzregel; Entdecken mit Vorhören und Merkliste; Tag-Rezepte;
ID3v1 schreiben; alle ID3-Frames; Hilfe mit Tag-Übersicht, Bibliotheks-Scan und Tastenkombinationen; Sicherungen im
Snapshot-Speicher; Plugin Lautheit). Davor **4.2.0 – Player, Tagger-Komfort, Importer & Playlist** und
**4.1.0 – Online-Metadaten & App**.

Geplant (Details in den [Milestones](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestones)):

- **WAV-Unterstützung** (Konzept, [docs/KONZEPT-WAV.md](docs/KONZEPT-WAV.md)) mit Testroutine `tools/wavcheck.py`
  (Aufbau, LIST/INFO, ID3-Chunk; Schreibtest an einer Kopie).
- **Mehrsprachigkeit** ([docs/KONZEPT-MEHRSPRACHIG.md](docs/KONZEPT-MEHRSPRACHIG.md)): Englisch und Zürichdeutsch
  sind im Developer Release für 4.7.0 umgesetzt; offen sind Deutsch (Deutschland) und Einreichen eigener Texte.
- **Profile und Einrichtungsassistent** ([docs/KONZEPT-EINRICHTUNG.md](docs/KONZEPT-EINRICHTUNG.md)): zweite,
  unabhängige TagStudio-Instanz mit getrennten Einstellungen; geführte Einrichtung für neue Benutzer.
- **Später:** Beatgrid und Beatmatching im Player, Symbol-Werkzeugleiste im Vergleich, Plugin-Ideen (Liedtexte,
  Duplikate, Qualitätsprüfung, Import aus Rekordbox/Traktor/Serato), Analyse-Modelle, signierte
  Installer, Datenbank-Modul für die Bibliothek.

Verworfen: Umstieg auf Qt (PySide6) – bringt gegenüber der neuen Oberfläche keinen Vorteil; Intel-Mac-Build (kein
Bedarf).

## Klassische Oberfläche (eingefroren)

Die erste Oberfläche von TagStudio (`tagstudio.py`, tkinter) ist auf dem **Stand von Version 3.0 eingefroren** und
wird nicht mehr weiterentwickelt. Sie kann vergleichen, kopieren, Felder bearbeiten, Mehrfachwerte vereinheitlichen
(Tag-Fixer), sichern und wiederherstellen und hat eine Symbol-Werkzeugleiste. Alles, was seither dazukam (Tagger,
Snapshots, Player, Plugins …), gibt es nur in der neuen Oberfläche. Start: `start_classic_windows.bat`,
`start_classic_mac.command` oder `python3 tagstudio.py [links] [rechts]`. Sie nutzt dieselben Einstellungen; ein
Rauchtest in der CI stellt sicher, dass sie weiterhin startet.

## Lizenz

© 2026 Markus Keller. MarKusSXCH TagStudio ist freie Software: Du kannst sie unter den Bedingungen der
[GNU General Public License, Version 3](LICENSE) oder (nach deiner Wahl) jeder späteren Version weitergeben und/oder
verändern. Das Programm wird in der Hoffnung verbreitet, dass es nützlich ist, aber **ohne jede Gewährleistung** –
Details in der Lizenz. Mitgelieferte bzw. nachinstallierte Fremdkomponenten (z. B. pywebview, FFmpeg,
audio-separator) stehen unter ihren eigenen Lizenzen.
