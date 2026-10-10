# MarKusSXCH TagStudio

Werkzeugkasten für MP3-Bibliotheken von DJs: **Tagger, Vergleich** (im Stil von Beyond Compare), **Tag-Fixer,
Sicherungen, Camelot-Rad, Audio-Merkmale** und **Plugins** (z. B. Stems, Beatport). Für **Windows und macOS**.
Der Kern braucht keine Zusatzpakete, nur Python 3.9 oder neuer – oder gar nichts, mit dem Installer.

**Download:** [Releases](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases) ·
**Änderungen:** [CHANGELOG.md](CHANGELOG.md) · **Plugins:** [PLUGINS.md](PLUGINS.md) ·
**Fehler & Ideen:** [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues) ·
**Mitmachen:** [CONTRIBUTING.md](CONTRIBUTING.md) · **Sicherheit:** [SECURITY.md](SECURITY.md) ·
**Lizenz:** [GNU GPL v3](LICENSE)

> Bis Version 2.8 hieß das Programm „MP3 Tag Compare“. Einstellungen und Sicherungen von damals werden automatisch übernommen.

## Funktionen im Überblick

- **Tagger:** viele Dateien gemeinsam bearbeiten, Cover, Tags aus Dateiname, Umbenennen, Spurnummern,
  Groß-/Kleinschreibung, Suchen & Ersetzen, Export nach Excel/CSV.
- **Editoren für jedes Feld:** mehrzeiliger Feld-Editor, Mehrfachwerte als Einzelwerte, JSON als Baum,
  XML-Editor, Binärfeld-Editor für DJ-Daten (GEOB/PRIV), Farbwähler für Hex-Farben, anklickbare Links.
- **Tonart:** Camelot-Rad mit harmonisch passenden Tonarten; Schreibweise Camelot (`08A`), musikalisch (`Am`)
  oder Open Key (`1m`).
- **Audio-Merkmale:** Energy, Danceability, Happiness … als Felder mit Werten 0–100, als Spalten im Tagger,
  sortier- und filterbar (`energy>=70`); Dateien wahlweise in 0–10 (Lexicon).
- **DJ-Set:** Reihenfolge nach Tonart (Camelot), BPM und Energie optimieren, jeden Übergang bewerten, per Ziehen
  umsortieren und sperren, Weg durch das Camelot-Rad und Energiekurve; Export als M3U8, Rekordbox-XML und CSV.
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
  Beatport (Metadaten mit eigenem Login), eigene Plugins möglich.
- **Einstellungen** an einem Ort – mit Vorgaben für den Start –, exportieren/importieren (z. B. Windows ↔ Mac) und
  zurücksetzen; Updates wahlweise nur offizielle oder auch Beta-Versionen, Versionshinweise direkt in der App.

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

Seitenleiste mit **Tagger, Tag-Fixer, Vergleich, DJ-Set, Snapshots, Sicherungen, Plugins, Einstellungen**, unten
„Nach Update suchen“, Versionshinweise, Einklappen und Hell/Dunkel. Beim Start öffnet die zuletzt benutzte Seite
(beim ersten Start der Tagger). Der Tagger lädt beim Start den zuletzt geladenen Ordner und stellt Markierung,
Sortierung, Filter und Bildlauf wieder her (Einstellungen › Tagger › „Beim Start laden“: zuletzt geladen, Standardordner
oder nichts). Vergleich und Tagger arbeiten mit denselben Dateien – Änderungen sind in beiden sichtbar, werden
zusammen gespeichert (Strg/Cmd+S) und lassen sich gemeinsam rückgängig machen.
Das App-Fenster öffnet in der Grösse und Position vom letzten Mal (auch maximiert).

### Tagger

- **Schnell wieder da:** ein schon eingelesener Ordner erscheint sofort aus dem Listen-Cache; danach prüft TagStudio
  im Hintergrund jeden Titel über einen Hash seiner Tags und liest Geändertes neu (Stand in der Statuszeile).
- **Liste:** Ordner oder Datei einlesen; optional mit **Cover-Spalte** (Knopf „Cover“); Spalten Datei, Titel, Künstler, Album, Spur, Jahr, Genre, Tonart –
  sortierbar per Klick, filterbar. Markieren mit Klick, Shift, Strg/Cmd, Strg/Cmd+A.
- **Bearbeiten:** rechts die Standardfelder der markierten Dateien. Bei mehreren Dateien zeigt „‹verschieden›“
  unterschiedliche Werte – sie bleiben unverändert, bis du etwas einträgst. Cover setzen/entfernen, ID3-Version
  (v2.3/v2.4) wählen. Steht eine Internetadresse im Feld (z. B. Kommentar), erscheint daneben ein Link-Knopf.
- **Werkzeuge** (alle mit Vorschau):
  - **Tags aus Dateiname** – Muster wie `%track% - %artist% - %title%`, `%dummy%` überspringt einen Teil.
  - **Dateien umbenennen** – aus Tags; ungültige Zeichen → `_`, Kollisionen werden erkannt (sofort, nicht über
    „Speichern“).
  - **Spurnummern** – in Listenreihenfolge, optional mit Gesamtzahl (3/12).
  - **Groß-/Kleinschreibung** – Titel-Schreibweise, Satzanfang, GROSS, klein; Abkürzungen wie DJ/AC/DC bleiben.
  - **Suchen & Ersetzen** – über alle markierten Dateien, wählbare Felder, ganze Wörter, reguläre Ausdrücke.
  - **Cover aus Ordner** – `cover/folder/front/album.jpg|png` im Ordner der Datei, sonst das größte Bild.
  - **Liste exportieren** – Excel (.xlsx) oder CSV mit Semikolon, inkl. Camelot- und Audio-Merkmal-Spalten.
  - **Feld hinzufügen**, **Tag-Fixer**, **Im Explorer/Finder zeigen**.

#### Weitere Felder und Editoren

Bei einer markierten Datei listet „Weitere Felder“ alle übrigen Tags. Der Teiler zwischen Feld und Wert lässt sich
ziehen (Doppelklick = Standard, Breite wird gemerkt). Links sind anklickbar, Hex-Farben (Felder mit „COLOR“ im
Namen, z. B. `#CC0000`, `0xFFCC0000`) erscheinen als Farbfeld. **Stift-Knopf** oder **Doppelklick** öffnet den
passenden Editor, ✕ entfernt das Feld.

- **Feld-Editor:** großes, mehrzeiliges Textfeld (Kommentare, Liedtexte), Zeichen-/Zeilenzähler, mit ‹ › bzw.
  Alt+↑/↓ zum vorigen/nächsten Feld blättern (speichert dabei), Strg/Cmd+Enter übernimmt.
  - **Einzelwerte:** Mehrfachwerte (getrennt durch NULL-Zeichen/ID3v2.4, Semikolon oder Komma) als Liste –
    Wert hinzufügen (auch Enter), entfernen, umsortieren; Trennung umstellbar, z. B. „House; Techno“ in echte
    ID3v2.4-Mehrfachwerte umwandeln.
  - **Farbwähler** bei Hex-Farben – die Schreibweise (Präfix, Groß-/Kleinschreibung, Alpha) bleibt erhalten.
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

Knopf neben dem Feld „Tonart“ öffnet das Rad (außen Dur, innen Moll). Klick setzt die Tonart der markierten
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
  entfernen, Link öffnen, im Explorer/Finder zeigen), klickbare Links, Cover-Vorschau mit Großansicht,
  Filter Alle/Unterschiede/Gleiche, Unwichtige, leere Felder, Feldsuche, **+ Feld**.
- **Bilder:** Rechtsklick auf ein Cover: anzeigen, ersetzen, exportieren, entfernen; Klick auf den leeren
  Cover-Platz fügt eines hinzu. (Dateidialoge im App-Fenster; im Browser-Modus nur unter Windows/Linux.)

### Vorschau-Player und externe Player

Unten in der Fußleiste (oder oben, siehe unten) – in Tagger und Vergleich:
- **Abspielen** des markierten Titels (Leertaste, ▶ oder **Doppelklick** auf die Zeile), ⏮/⏭ springt zum
  vorherigen/nächsten Titel; beim Abspielen folgt der Player ↑/↓ und spielt am Titelende den nächsten.
  **Live-Vorschau** (Knopf mit den Funkwellen): ein einfacher Klick auf einen Titel spielt ihn sofort; ohne
  Live-Vorschau wechselt ein Klick den laufenden Titel nicht. **↑/↓** wechseln den Titel, egal wo der Fokus gerade ist
  (außer in mehrzeiligen, Auswahl- und Zahlenfeldern). **Shift+←/→** spult 10 s, Klick in die Leiste springt.
- **Startpunkt** per Umschalter: Start, 30 %, 1:00 oder erster Cue – praktisch zum schnellen Durchhören. Lautstärke
  wird gemerkt. Bei Titeln mit Cue-Punkten springen zwei Knöpfe zum vorigen/nächsten Cue.
- **Wellenform:** wird beim ersten Abspielen einmal berechnet und im Cache abgelegt (`~/TagStudio/cache/wave`,
  bleibt beim Bearbeiten der Tags und Umbenennen gültig); im Menü ⋯ bzw. in den Einstellungen abschaltbar.
- **Cue-Marken** aus Serato (Cues und Loops mit Farbe und Name) und Mixed In Key über der Leiste: Klick springt
  hin, **Alt+Bild↑/↓** zum vorigen/nächsten Cue. Ein Klick auf eine **Loop-Marke** spielt den Loop als Schleife
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
  Titel überblenden, 2–12 s; der nächste Titel startet ab Startpunkt, Anfang oder erstem Cue; wahlweise schon nach
  15 s … 2 Minuten (zum schnellen Durchhören). Nicht bei „Titel wiederholen“ oder einer Schleife.
  **Tempo angleichen** (Standard an): der nächste Titel läuft während des Überblendens im BPM des laufenden
  (Tonhöhe bleibt, höchstens ±10 %, halbes/doppeltes Tempo wird erkannt; ohne BPM-Feld kein Angleichen) und gleitet
  danach in der eingestellten Zeit (sofort … 1 Minute) auf sein eigenes BPM zurück. Nur das Tempo wird angeglichen,
  die Beats werden nicht übereinandergelegt (dafür fehlt ein Beatgrid).
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
  Änderungszeit; „n Titel extern geändert“ in der Fußleiste öffnet das Journal. Eigene Speicherungen zählen nicht.
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
abweichende Zeichen hervorgehoben; mit ‹ › blättern und einzelne Dateien direkt wiederherstellen. Außerdem
markierte oder alle wiederherstellen (vorher wird der aktuelle Stand selbst gesichert), Sicherung löschen,
automatische Sicherung ein/aus, Ordner ändern/öffnen.

### Plugins

Seite „Plugins“: Erweiterungen ein-/ausschalten, fehlende Pakete per Knopf installieren; Aktionen erscheinen im
Tagger unter „Plugins“. Vorschläge von Plugins (z. B. Beatport) erscheinen erst als **Vorschau mit Häkchen**.

- **Stems:** trennt Titel in Gesang, Schlagzeug, Bass, Instrumental … (audio-separator, eigene Python-Umgebung,
  Varianten CPU/DirectML/NVIDIA). Läuft **im Hintergrund**: der Dialog schliesst sofort, unten in der Fußleiste
  steht der Fortschritt („Stems: 2 von 7 · 45 %“), ein Klick zeigt alle Aufträge (Abbrechen, Ordner, Protokoll).
  Weitere Aufträge werden hinten angestellt, beim Beenden wird nachgefragt und die Warteschlange beim nächsten
  Start zum Fortsetzen angeboten. Im Tagger hängen die Spuren **aufklappbar unter dem Original** (▸, →/←,
  „Stems ▾/▸“ für alle): MP3-Spuren bearbeiten, FLAC/WAV anhören; „Stems: Tags vom Original …“ überträgt die Tags.
- **Beatport (inoffiziell):** BPM, Tonart, Genre, Label, Katalognummer, ISRC, Remixer, Cover u. a. mit deinem
  eigenen Beatport-Login (Passwort wird nie gespeichert). Die Vorschau zeigt **alle gelieferten Felder** – gleiche
  grau, abgewählte und schon gefüllte ungehakt.
- **Online-Metadaten:** Album, Datum, Label, Katalognummer, ISRC, Genre, Cover u. a. von MusicBrainz (auch per
  AcoustID-Fingerabdruck), Deezer, iTunes, Discogs und Last.fm. Standard: nur leere Felder ergänzen; je Feld ist die
  erste Quelle vorausgewählt, andere erscheinen als Alternative. Discogs-Token, Last.fm- und AcoustID-Schlüssel unter
  Plugins › Online-Metadaten › „Schlüssel …“ (verschlüsselt gespeichert); „Verbindungen testen“ prüft die Dienste.
- **Eigene Plugins** in `~/TagStudio/Plugins` – Anleitung in [PLUGINS.md](PLUGINS.md).

### Update, Layout, Tastatur

- **Update:** „Nach Update suchen“ unten in der Seitenleiste; TagStudio prüft beim Start selbst (Punkt am Knopf).
  Unter Einstellungen › Updates: **nur offizielle Versionen** oder **auch Beta-Versionen**. Die installierte App
  zeigt die neue Version mit ihren Hinweisen und lädt den passenden Installer herunter. In der Quellcode-Variante
  lädt ein Klick die neue Version (`git`, nur Vorspulen, nur ohne eigene Änderungen im Programmordner; bei „nur
  offizielle“ bis zum neuesten Versions-Tag) und startet neu; ungespeicherte Änderungen werden vorher abgefragt.
- **Fenster und Programm:** ganz unten in der Seitenleiste Vollbild (auch F11), Fenstermodus (zurück aus Vollbild
  bzw. maximiert), Neu starten und Beenden. Beim Beenden – auch über das X des Fensters – erscheint kurz
  „Einstellungen werden gespeichert …“; ungespeicherte Änderungen und laufende Aufträge werden vorher abgefragt.
  Es läuft immer nur **eine Instanz**; ein zweiter Start meldet „TagStudio läuft bereits“.
- **Versionshinweise:** unter dem Update-Knopf – was in der installierten Version neu ist und, falls vorhanden,
  in der neuesten; mit Link zu GitHub.
- **Splitter:** Seitenleiste, Paarliste, Tabellenspalten, Bearbeitungsbereich und Feldnamen-Spalte lassen sich
  ziehen (oder mit ←/→ auf dem Griff); Doppelklick setzt zurück, alles wird gemerkt. Die Seitenleiste lässt sich
  einklappen.
- **Tastatur:** Strg/Cmd+S speichern · Strg/Cmd+Z / Strg+Y rückgängig/wiederholen · Alt+← / Alt+→ Markierte
  kopieren · Strg/Cmd+A alles markieren · Leertaste abspielen · Doppelklick abspielen · 0–5 Bewertung · F Like · B Player A/B · Shift+P Player-Leiste ein/aus · ↑/↓ Titel wechseln (überall) · S Stem-Spur · R wiederholen · L A–B-Schleife · Shift+←/→ ±10 s · Shift+F5 Paar neu einlesen · Alt+Bild↑/↓ Cue · Strg/Cmd+P externer Player · →/← Stems auf-/zuklappen · F5 neu einlesen · ↑/↓ in Listen · Esc schließt Dialoge.

## Einstellungen und Datenablage

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

Gespeichert wird in `~/.tagstudio.json`. Weitere Ordner unter `~/TagStudio`:

| Ordner | Inhalt |
|---|---|
| `Sicherungen` | automatische Sicherungen der Tags (ZIP je Speichervorgang, Ordner änderbar) |
| `cache` | Cover-Vorschaubilder, Wellenformen (`wave`) |
| `Einstellungen` | Sicherungen der Einstellungsdatei vor Import/Zurücksetzen |
| `Plugins` | eigene Plugins |
| `Plugin-Daten` | z. B. Stems-Umgebung und Modelle, Beatport-Token (unter Windows verschlüsselt) |
| `Logs` | App-Protokoll `app.log` (Start, Ende, Fehler, Warnungen; ab 1 MB `app.log.1`), Protokolle von Plugins und Installationen |
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
  bearbeitet. Im Vergleich gelten sie standardmäßig als „unwichtig“, da Cue-Punkte/Beatgrids zu genau einem Track
  gehören.
- Tipp: Vor dem ersten Einsatz an einer Kopie der Musik ausprobieren.

## Dateien

- `tagstudio_web.py` + `web/` – die App (HTML/CSS/JS im App-Fenster über pywebview, sonst im Browser);
  `web/xmleditor.js` XML-Editor, `web/jsontree.js` JSON-Baum, `web/tagger.js` Tagger und Editoren,
  `web/keywheel.js` Camelot-Rad, `web/features.js` Audio-Merkmale, `web/plugins.js` Plugin-Seite,
  `web/player.js` Vorschau-Player, `web/player2.js` Überblenden, Player oben, Player B, Abdocken,
  `web/player-window.html` + `web/playerwin.js` abgedocktes Player-Fenster, `web/settings.js` Einstellungen, `web/jobs.js` Hintergrund-Aufträge,
  `web/djset.js` Seite „DJ-Set“
- `core.py` – gemeinsame Logik: Anzeige, Zeichen-Diff, Filter, Laden, Speichern, Einstellungen
- `session.py` – Zustand und Befehle einer Sitzung; Teile in `session_player.py` (Player, Fenster-Nachrichten,
  Wiedergabe), `session_snapshots.py` (Snapshots, Journal) und `session_djset.py` (DJ-Set)
- `id3tags.py` – ID3 lesen/schreiben, MPEG-Infos (ohne externe Bibliotheken)
- `compare.py` – Zuordnung, Vergleich, Kopieren, Regeln für unwichtige Felder
- `tagger.py` – Tagger-Logik: gemeinsame Felder, Tags aus Dateiname, Umbenennen, Spurnummern, Cover,
  Groß-/Kleinschreibung, Suchen & Ersetzen, Cover aus Ordner, Export (CSV/Excel ohne Zusatzpakete)
- `keys.py` – Tonarten: erkennen, umschreiben (Camelot, musikalisch, Open Key), passende Tonarten
- `features.py` – Audio-Merkmale (TXXX, 0–100; Dateien wahlweise 0–10)
- `setplan.py` – DJ-Set: Übergänge bewerten, Reihenfolge optimieren (Held-Karp bzw. Greedy + 2-opt);
  `setexport.py` – Exporte M3U8, Rekordbox-XML, CSV
- `xmltools.py` – XML in Feldern und Binärfeldern erkennen, prüfen, formatieren, ersetzen
- `blobs.py` – Binärfelder (GEOB/PRIV): Inhalt erkennen (XML, Text, Base64, binär) und byte-genau ändern
- `backup.py` – Sicherung und Wiederherstellung der Tags, Vergleich Sicherung ↔ Datei (Änderungs-Viewer)
- `undo.py` – Rückgängig/Wiederholen
- `media.py` – lokaler Audio-Server für den Player (Range-Anfragen, Token); `players.py` – externe Player
- `ratings.py` – Bewertung (POPM, FMPS_Rating) und Like (TXXX:TAGSTUDIO)
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

- **Tests:** `python -m unittest discover -s tests -v` – ID3-Lesen/-Schreiben (v2.3/v2.4, Mehrfachwerte, BOM,
  GEOB, Datumsumwandlung), Vergleich, Tag-Fixer, Sicherung/Wiederherstellung, Sitzung der neuen Oberfläche,
  Tagger-Werkzeuge, Tonarten, Audio-Merkmale, XML und Binärfelder, Versionierung, Updater und Plugins (Stems und
  Beatport mit nachgebauter Gegenseite) – mit synthetischen MP3-Dateien, ohne Zusatzpakete und ohne Netz.
  Einzelne Datei: `python -m unittest tests.test_player`.
- **Oberflächen-Tests** im Browser (Playwright/Chromium, ffmpeg): `TAGSTUDIO_UI_TESTS=1 python -m unittest
  discover -s tests -p "test_browser_ui.py" -v` – Menü und Einstellungen, Player (Live-Vorschau, Doppelklick,
  Bewertung, Überblenden mit Tempo, Player B, Abdocken). Ohne die Variable werden sie übersprungen.
- **GitHub Actions:**
  - `tests.yml` – bei jedem Push die Tests auf Windows, macOS und Linux (Python 3.9–3.13), dazu ein Smoke-Test
    der klassischen Oberfläche.
  - `installer.yml` – baut und testet die Installer (Selbsttest der gebauten und der installierten App) und
    veröffentlicht bei neuer Versionsnummer das Release (siehe unten).
  - `codeql.yml` – Code-Scanning (Python, JavaScript, Workflows). Neue Funde werden automatisch als Issue mit den
    Labels `bug`, `security`, `codeql` im nächsten Patch-Milestone angelegt und nach der Behebung geschlossen.
  - **Dependabot** hält die verwendeten Actions aktuell (monatlicher Pull Request).
- **Planung:** offene Punkte als [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues), geplante
  Versionen als [Milestones](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestones). Commits mit
  „Fixes #n“ schließen das Issue automatisch.

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
4. **Dringender Fehler:** sofort eine PATCH-Version auf demselben Weg.

`python packaging/release.py --check` prüft, ob Versionsnummer, `pyproject.toml`, `SECURITY.md` und CHANGELOG
zusammenpassen (läuft auch in den Tests).

**Kanäle:** In den Einstellungen wählbar – **nur offizielle Versionen** oder **auch Beta-Versionen**. Beta-Releases
einer Version werden automatisch von der Releases-Seite entfernt, sobald die finale Version erscheint (ihre Git-Tags
bleiben). Ein Git-Klon mit „auch Beta“ folgt `main` und bekommt jede Änderung sofort.

**Zweige:** `main` ist immer lauffähig (die CI prüft jeden Commit). Größere Vorhaben entstehen in kurzlebigen
Zweigen (`feature/…`) und werden nach `main` übernommen, wenn sie fertig sind.

## Fehler melden, Ideen, Sicherheit

- **Fehler und Wünsche:** als [Issue](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/new/choose) –
  die Vorlagen „Fehler melden“, „Funktion vorschlagen“ und „Plugin-Idee“ fragen Version, Betriebssystem, Schritte
  und Protokoll (`~/TagStudio/Logs`) gleich mit ab.
- **Mitmachen:** Entwicklungsumgebung, Richtlinien und Ablauf für Pull Requests in [CONTRIBUTING.md](CONTRIBUTING.md);
  es gilt der [Verhaltenskodex](CODE_OF_CONDUCT.md).
- **Sicherheitslücken** bitte nicht öffentlich, sondern privat melden – siehe [SECURITY.md](SECURITY.md).

## Ausblick

Zuletzt erschienen: **4.0.0 – DJ-Set** (Set-Optimierung und -Bewertung, Seite DJ-Set, Exporte M3U8/Rekordbox/CSV,
Merkmal-Spalten und -Filter, Ziehen auf die Player, Snapshot-Baseline). Davor **3.5.0 – App allgemein & Aufräumen**.

Geplant (Details in den [Milestones](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestones)):

- **4.1.0 – Online-Metadaten & App-Zustand** (in Beta): Plugin Online-Metadaten, Fenstergrösse, Wiedergabe
  fortsetzen, Tagger-Zustand.
- **Tracks vorbereiten** (Konzept, [docs/KONZEPT-VORBEREITEN.md](docs/KONZEPT-VORBEREITEN.md)): Workflow vom
  Eingangsordner über Tag-Rezepte und externe Programme bis in die Bibliothek, Schutz bestehender Tags, später
  Download gekaufter Titel und Vorschläge mit Vorhören.
- **Später:** Beatgrid und Beatmatching im Player, Symbol-Werkzeugleiste im Vergleich, Plugin-Ideen (Liedtexte,
  Lautheit, Duplikate, Qualitätsprüfung, Import aus Rekordbox/Traktor/Serato), Analyse-Modelle, signierte
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
