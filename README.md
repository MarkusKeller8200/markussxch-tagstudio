# MarKusSXCH TagStudio

Werkzeugkasten für MP3-Bibliotheken von DJs: **Tagger, Vergleich** (im Stil von Beyond Compare), **Tag-Fixer,
Sicherungen, Camelot-Rad, Audio-Merkmale** und **Plugins** (z. B. Stems, Beatport). Für **Windows und macOS**.
Der Kern braucht keine Zusatzpakete, nur Python 3.9 oder neuer – oder gar nichts, mit dem Installer.

**Download:** [Releases](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases) ·
**Änderungen:** [CHANGELOG.md](CHANGELOG.md) · **Plugins:** [PLUGINS.md](PLUGINS.md) ·
**Fehler & Ideen:** [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues) ·
**Sicherheit:** [SECURITY.md](SECURITY.md)

> Bis Version 2.8 hieß das Programm „MP3 Tag Compare“. Einstellungen und Sicherungen von damals werden automatisch übernommen.

## Funktionen im Überblick

- **Tagger:** viele Dateien gemeinsam bearbeiten, Cover, Tags aus Dateiname, Umbenennen, Spurnummern,
  Groß-/Kleinschreibung, Suchen & Ersetzen, Export nach Excel/CSV.
- **Editoren für jedes Feld:** mehrzeiliger Feld-Editor, Mehrfachwerte als Einzelwerte, JSON als Baum,
  XML-Editor, Binärfeld-Editor für DJ-Daten (GEOB/PRIV), Farbwähler für Hex-Farben, anklickbare Links.
- **Tonart:** Camelot-Rad mit harmonisch passenden Tonarten; Schreibweise Camelot (`08A`), musikalisch (`Am`)
  oder Open Key (`1m`).
- **Audio-Merkmale:** Energy, Danceability, Happiness … als Felder mit Werten 0–100.
- **Vergleich zweier Ordner/Dateien:** Feld für Feld mit zeichengenauen Markierungen, Werte per Pfeil übernehmen.
- **Tag-Fixer:** Mehrfachwerte (`;`, `/`, `feat.` …) vereinheitlichen oder in echte ID3v2.4-Mehrfachwerte umwandeln.
- **Sicherheit beim Speichern:** vor jedem Speichern automatische Sicherung der Tags, Änderungs-Viewer,
  byte-genaues Wiederherstellen; Rückgängig/Wiederholen über alle Dateien.
- **Vorschau-Player:** Titel vorhören mit Wellenform und Cue-Marken (Serato, Mixed In Key), A/B im Vergleich,
  externe Player (foobar2000, VLC …).
- **Herkunft der Tags:** Kennzeichen, welche Anwendung ein Feld geschrieben hat; Felder einer Anwendung filtern
  oder entfernen.
- **Plugins:** Stems (Gesang, Schlagzeug, Bass … trennen – im Hintergrund, Spuren aufklappbar unter dem Titel) und
  Beatport (Metadaten mit eigenem Login), eigene Plugins möglich.
- **Einstellungen** an einem Ort, exportieren/importieren (z. B. Windows ↔ Mac) und zurücksetzen.

## Zwei Oberflächen, ein Kern

| | Neue Oberfläche (empfohlen) | Klassische Oberfläche |
|---|---|---|
| Start Windows | `start_web_windows.bat` | `start_windows.bat` |
| Start macOS | `start_web_mac.command` | `start_mac.command` |
| Terminal | `python tagstudio_web.py [links] [rechts]` | `python3 tagstudio.py [links] [rechts]` |
| Technik | HTML/CSS/JS im eigenen App-Fenster (pywebview), sonst im Browser | tkinter |
| Umfang | Vergleich, **Tagger** mit allen Editoren, Tag-Fixer, Sicherungen, **Plugins**, Update-Knopf | Vergleich, Tag-Fixer, Sicherungen, XML-Editor |
| Installer | ja | nein (nur Quellcode) |

Beide nutzen denselben Kern und dieselben Einstellungen (`~/.tagstudio.json`) und lassen sich abwechselnd verwenden.

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

## Neue Oberfläche

Seitenleiste mit **Vergleich, Tagger, Tag-Fixer, Sicherungen, Plugins**, unten Update-Knopf, Einklappen und
Hell/Dunkel. Vergleich und Tagger arbeiten mit denselben Dateien – Änderungen sind in beiden sichtbar, werden
zusammen gespeichert (Strg/Cmd+S) und lassen sich gemeinsam rückgängig machen.

### Tagger

- **Liste:** Ordner oder Datei einlesen; Spalten Datei, Titel, Künstler, Album, Spur, Jahr, Genre, Tonart –
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
  Erklärung; Benutzerfelder ohne bekannte Anwendung tragen **v2.3/v2.4**. Auch im Vergleich – dort entfernt der Knopf
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

Unten in der Fußleiste – in Tagger und Vergleich:
- **Abspielen** des markierten Titels (Leertaste oder ▶), ⏮/⏭ springt zum vorherigen/nächsten Titel, der Player
  folgt der Auswahl und spielt am Titelende den nächsten. **Shift+←/→** spult 10 s, Klick in die Leiste springt.
- **Startpunkt** per Umschalter: Start, 30 %, 1:00 oder erster Cue – praktisch zum schnellen Durchhören. Lautstärke
  wird gemerkt. Bei Titeln mit Cue-Punkten springen zwei Knöpfe zum vorigen/nächsten Cue.
- **Wellenform:** wird beim ersten Abspielen einmal berechnet und im Cache abgelegt (`~/TagStudio/cache/wave`,
  bleibt beim Bearbeiten der Tags und Umbenennen gültig); im Menü ⋯ bzw. in den Einstellungen abschaltbar.
- **Cue-Marken** aus Serato (Cues und Loops mit Farbe und Name) und Mixed In Key über der Leiste: Klick springt
  hin, **Alt+Bild↑/↓** zum vorigen/nächsten Cue.
- **A/B im Vergleich:** L/R wechselt zwischen linker und rechter Datei **an derselben Stelle**.
- **Externe Player** (⋯ bzw. **Strg/Cmd+P**): markierte Titel in foobar2000, VLC, Rekordbox, Music … öffnen; ohne
  Einrichtung im Standardprogramm des Systems. Unter „Externe Player…“ beliebig viele Programme mit Argumenten
  (`{files}` alle Dateien, `{file}` erste, `{folder}` Ordner, `{m3u}` temporäre Playlist).
- Die Wiedergabe läuft über einen lokalen Mini-Server (nur 127.0.0.1, nur freigegebene Dateien, zufälliges Token).

### Tag-Fixer

Mehrfachwerte vereinheitlichen – Bereich (aktuelles Paar, eine Seite, markierte Paare, alle Dateien,
Tagger-Auswahl), Felder, erkannte Trenner, Ausgabe (Trennzeichen oder ID3v2.4-Mehrfachwerte), laufende Vorschau.

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
- **Eigene Plugins** in `~/TagStudio/Plugins` – Anleitung in [PLUGINS.md](PLUGINS.md).

### Update, Layout, Tastatur

- **Update:** „Nach Update suchen“ unten in der Seitenleiste; TagStudio prüft beim Start selbst (Punkt am Knopf).
  In der Quellcode-Variante lädt ein Klick die neue Version (`git pull`, nur ohne eigene Änderungen im
  Programmordner) und startet neu; ungespeicherte Änderungen werden vorher abgefragt. Wer noch auf dem früheren
  Zweig `web-ui` steht, wird automatisch auf `main` umgestellt. In der installierten App öffnet der Knopf die
  Releases-Seite.
- **Splitter:** Seitenleiste, Paarliste, Tabellenspalten, Bearbeitungsbereich und Feldnamen-Spalte lassen sich
  ziehen (oder mit ←/→ auf dem Griff); Doppelklick setzt zurück, alles wird gemerkt. Die Seitenleiste lässt sich
  einklappen.
- **Tastatur:** Strg/Cmd+S speichern · Strg/Cmd+Z / Strg+Y rückgängig/wiederholen · Alt+← / Alt+→ Markierte
  kopieren · Strg/Cmd+A alles markieren · Leertaste abspielen · Shift+←/→ ±10 s · Alt+Bild↑/↓ Cue · Strg/Cmd+P externer Player · →/← Stems auf-/zuklappen · F5 neu einlesen · ↑/↓ in Listen · Esc schließt Dialoge.

## Klassische Oberfläche

Die folgenden Abschnitte beschreiben die klassische Oberfläche (`tagstudio.py`). Vergleich, Filter, Tag-Fixer,
Sicherungen und Tastenkürzel funktionieren in der neuen Oberfläche sinngemäss gleich.

### Aufbau

- **Oben:** Werkzeugleiste. Darunter links und rechts der Pfad (Ordner oder Datei, mit Verlauf)
  sowie Datei-Infos: Datum, Größe, ID3-Version, Dauer, Bitrate, Abtastrate.
- **Dateipaare** (nur bei Ordnern): Status pro Paar – ≠ Unterschiede, ≈ nur unwichtige, = gleich, ◧/◨ nur eine Seite.
- **Vergleich:** Alle ID3-Felder als Tabelle „Name | Wert“, links und rechts synchron scrollend.
  Dazwischen die **Befehlsspalte**: ◀ übernimmt den rechten Wert nach links, ▶ den linken nach rechts
  (linke/rechte Hälfte der Spalte anklicken). Pfeile erscheinen nur, wo es etwas zu übernehmen gibt.
- **Splitter:** Die Breiten von links / Befehlsspalte / rechts sowie die Grenze Name | Wert lassen sich ziehen
  (Name | Wert im Spaltenkopf oder direkt an der Linie in der Tabelle). Standardmäßig wird alles **automatisch
  optimal** nach Inhalt gesetzt – längster Feldname bzw. Länge der Werte je Seite.
  **Doppelklick** auf einen Splitter stellt die optimale Breite wieder her.

| Farbe | Bedeutung |
|---|---|
| Rot hinterlegt, rote Zeichen | Unterschied (die abweichenden Zeichen sind rot) |
| Braun/orange | unwichtiger Unterschied (Länge, Encoder, Fingerprints …) |
| Violett | Feld gibt es nur auf dieser Seite |
| ● blau | geändert, noch nicht gespeichert |
| *kursiv, grau* | vorgesehenes, aber leeres Feld (Option „Leere Felder“) |

Die Zeilen sind durch feine Linien getrennt. Mehrfachwerte (ID3v2.4) werden als `A ¦ B ¦ C` angezeigt.

### Cover-Vorschau

Über der Tabelle zeigt jede Seite alle eingebetteten Bilder als Vorschau mit Größe (z. B. 1400×1400 · 245 KB).
Unterschiedliche Cover sind **rot umrandet**, in der Mitte steht = oder ≠. Klick auf ein Bild öffnet eine große
Ansicht (mit „Im Bildbetrachter öffnen“ und „Speichern unter“). **▣ Cover** blendet die Leiste aus/ein.
Technik: Tk kann kein JPEG – die Vorschau wird ohne Zusatzpakete erzeugt (Windows: eingebautes .NET über PowerShell,
macOS: `sips`, Linux: ImageMagick; falls Pillow installiert ist, wird es bevorzugt) und in
`~/TagStudio/cache` zwischengespeichert. Die erste Vorschau eines Covers dauert unter Windows evtl. ~1 s.

### Suchen & Filtern

**Dateipaare** – Zeile unter der Überschrift:
- **Suchen:** sucht in Dateinamen und allen Tag-Werten beider Seiten.
- **Filter:** Feld (jedes vorkommende Feld, „Dateiname“ oder „Beliebiges Feld“) · Bedingung · Wert · Seite.
  Bedingungen: *enthält, enthält nicht, ist, ist nicht, beginnt mit, fehlt / leer, vorhanden, größer als,
  kleiner als, Regex*. Seite: *links oder rechts, links, rechts, beide Seiten*.
- Beispiele: *Tonart · fehlt / leer* → alle Tracks ohne Tonart; *Genre · enthält · techno*;
  *Beats pro Minute · größer als · 125*; *Benutzertext (EnergyLevel) · ist · 7*.
- Die Kopfzeile zeigt „x von y Paaren“. **Alle markieren** markiert nur die gefilterten Paare – praktisch für
  Sammelkopie oder den Tag-Fixer auf genau diese Auswahl. **✕ Zurücksetzen** hebt alles auf.

**Felder suchen** (oben rechts) blendet in der Vergleichstabelle nur Felder ein, deren Name, Frame-ID oder Wert
den Suchtext enthält – z. B. „bpm“, „serato“, „TXXX“, „mixedinkey“.

### Einlesen großer Ordner

Beim Vergleichen werden zuerst alle MP3-Dateien gezählt, danach erscheint ein Fortschrittsbalken
mit Anzahl, Prozent, geschätzter Restzeit und aktuellem Dateinamen. **Abbrechen** (oder Esc) stoppt
sofort – die bisherige Ansicht bleibt dann unverändert. Bei schnellen Vorgängen erscheint der Dialog gar nicht erst.
Hinweis: Bei OneDrive-Ordnern mit „nur online“-Dateien lädt Windows diese beim Einlesen herunter.

### Leere Felder einblenden

Toolbar **☐ Leere Felder** → wählen: ID3v1, ID3v2.3, ID3v2.4 oder alle. Dann erscheinen alle Felder, die der
jeweilige Standard vorsieht (Text-, URL-, Kommentar-, Liedtext- und Cover-Felder), auch wenn sie unbeschrieben sind.
Doppelklick auf ein leeres Feld füllt es.

### Tag-Fixer: Mehrfachwerte

Toolbar **¦ Mehrfachwerte** vereinheitlicht Felder mit mehreren Werten (z. B. „Adriatique; Vincent Vossen / Yubik“):

- **Dateien:** aktuelles Paar (beide/links/rechts), markierte Paare oder alle geladenen Dateien.
- **Felder:** Künstler, Album-Künstler, Komponist, Texter, Genre, Sortierfelder … oder alle Textfelder.
- **Als Trenner erkennen:** Null (v2.4), `;`, ` / `, `\\` (Mp3tag) – optional `,`, `/`, `&`, `feat.`, ` x `.
- **Ausgabe:** Trennzeichen (Standard `, `) **oder ID3v2.4-Standard** (echte, null-getrennte Mehrfachwerte).
  Für Letzteres können v2.3-Dateien automatisch auf v2.4 umgestellt werden; sonst erhalten sie `; `.
- Doppelte Werte werden auf Wunsch entfernt. Eine **Vorschau** zeigt jede Änderung vorher/nachher.
- Beim Bearbeiten trennt `¦` einzelne Werte (wird als v2.4-Mehrfachwert gespeichert; in v2.3 als ` / `).
- Hinweis: Nicht alle Programme zeigen v2.4-Mehrfachwerte vollständig an (manche nur den ersten Wert).

### Bedienung

| Aktion | So geht’s |
|---|---|
| Felder markieren | Klick, Shift-Klick (Bereich), Strg/Cmd-Klick (einzeln), ↑/↓ |
| Markierte kopieren | Toolbar **Auswahl →** / **← Auswahl**, Strg/Cmd + → / ←, oder Rechtsklick |
| Alles kopieren | **Alles →** / **← Alles** bzw. „Alle ⇉“ / „⇇ Alle“ im Kopf der Befehlsspalte (fragt, ob nur im Ziel vorhandene Felder entfernt werden sollen) |
| Fehlende ergänzen | **Fehlende →** / **← Fehlende** bzw. „Fehl. ▷“ / „◁ Fehl.“ – übernimmt nur Felder, die im Ziel fehlen; vorhandene Werte bleiben unangetastet |
| Einzelnes Feld | ◀ / ▶ in der Befehlsspalte |
| Bearbeiten | Doppelklick oder Enter auf einem Wert; Tab springt zum nächsten Feld; Esc bricht ab |
| Feld leeren | Wert löschen und Enter – das Feld wird entfernt |
| Neues Feld | **+ Feld** (z. B. Benutzertext/TXXX mit Beschreibung) |
| Original-Tag anzeigen | Maus über den Feldnamen halten → Frame-ID (z. B. `TPE1`, `TXXX`, bei v2.3-Datum `TYER + TDAT`), Beschreibung, Sprache, Bildtyp, ID3-Version |
| Links öffnen | URLs in Werten (Internetseiten-Felder, Benutzertexte, Kommentare …) sind blau unterstrichen – **ein Klick** öffnet sie im Browser; mehrere Links in einem Feld einzeln. Auch per Rechtsklick → „Link öffnen“ |
| Bilder | Rechtsklick auf „Bild (…)“: anzeigen, speichern unter, ersetzen |
| Sammelkopie | Paare in der Liste markieren → **Markierte … →** → Felder auswählen |
| Filter | **Alle / Unterschiede / Gleiche**, **Unwichtige** ein-/ausblenden |
| Speichern | **Speichern** oder Strg/Cmd + S (erst dann wird in die Dateien geschrieben; vorher automatische Sicherung) |
| Rückgängig / Wiederholen | **↶** / **↷** bzw. Strg/Cmd+Z, Strg+Y |
| Sicherungen | **⟲ Sicherungen** – Tags früherer Stände wiederherstellen |
| Design | **◐ Design** schaltet zwischen Dunkel und Hell |

### Rückgängig / Wiederholen

Jede Änderung – Feld bearbeiten, ◀/▶, Auswahl/Alles/Fehlende kopieren, Sammelkopie, Tag-Fixer, Feld entfernen,
Bild ersetzen, Paar verwerfen – lässt sich mit **↶ Rückgängig** (Strg/Cmd+Z) zurücknehmen und mit
**↷ Wiederholen** (Strg+Y bzw. Strg/Cmd+Shift+Z) erneut ausführen. Bis zu 200 Schritte, über alle Dateien.
Auch nach dem Speichern kann man zurückgehen – die Datei gilt dann wieder als „geändert“ und kann erneut gespeichert werden.
Beim Laden neuer Ordner wird der Verlauf geleert. Während man in einem Feld tippt, gilt Strg+Z für das Eingabefeld.

### Automatische Sicherung & Wiederherstellen

- Vor jedem Speichern werden die **bisherigen Tags** aller betroffenen Dateien gesichert – nur die Tag-Bytes
  (inkl. Cover, DJ-Daten, ID3v1), nicht die Musik. Pro Speichervorgang entsteht ein ZIP in
  `~/TagStudio/Sicherungen` (Ordner änderbar).
- Speichern läuft mit **Fortschrittsbalken**; *Abbrechen* stoppt nach der aktuellen Datei.
- Schlägt die Sicherung einer Datei fehl, wird diese Datei **nicht** gespeichert.
- **⟲ Sicherungen** zeigt alle Sicherungen mit Status je Datei (wiederherstellbar / bereits gleich / Datei fehlt /
  Audio verändert) und stellt markierte oder alle Dateien **byte-genau** wieder her. Vor dem Wiederherstellen wird
  der aktuelle Stand selbst gesichert – auch das ist also umkehrbar.
- Es wird **nie automatisch gelöscht**. Alte Sicherungen löscht man im Dialog einzeln (mit Rückfrage).
- Größe: Bibliotheken mit umfangreichen Analysedaten (z. B. beaTunes) haben große Tags – im Test etwa 0,8 MB
  pro Datei als ZIP. Eine Änderung an der ganzen Bibliothek (1'500 Dateien) erzeugt also eine Sicherung von gut 1 GB.

### Fenster & Dialoge

Alle Dialoge (Sicherungen, Tag-Fixer, Sammelkopie, Feld hinzufügen, Cover-Ansicht, Bearbeiten) sowie Meldungen
und Datei-Dialoge öffnen sich **zentriert über dem Programmfenster** – also auf dem Bildschirm, auf dem das
Programm gerade liegt. Meldungen aus einem Dialog heraus erscheinen über diesem Dialog.

## Einstellungen und Datenablage

Die Seite **Einstellungen** fasst alles zusammen: Design, Tonart-Schreibweise, Stems-Anzeige im Tagger, ID3-Version
beim Speichern (beibehalten / immer v2.3 / immer v2.4), Sicherung, Player, Herkunft der Tags (eigene Zuordnungen),
unwichtige Felder (Liste bearbeiten, Standard wiederherstellen, ganze Herkunft „als unwichtig“), Cache (Wellenformen,
Cover-Vorschauen: Grösse anzeigen, leeren). **Exportieren**
speichert alles als Datei (ohne Zugangsdaten), **Importieren** übernimmt gewählte Bereiche – Pfade eines anderen
Systems sind nicht vorgewählt –, **Zurücksetzen** geht für einzelne Bereiche oder alles. Vor Import und
Zurücksetzen wird die alte Datei nach `~/TagStudio/Einstellungen` gesichert.

Gespeichert wird in `~/.tagstudio.json` (beide Oberflächen). Weitere Ordner unter `~/TagStudio`:

| Ordner | Inhalt |
|---|---|
| `Sicherungen` | automatische Sicherungen der Tags (ZIP je Speichervorgang, Ordner änderbar) |
| `cache` | Cover-Vorschaubilder, Wellenformen (`wave`) |
| `Einstellungen` | Sicherungen der Einstellungsdatei vor Import/Zurücksetzen |
| `Plugins` | eigene Plugins |
| `Plugin-Daten` | z. B. Stems-Umgebung und Modelle, Beatport-Token (unter Windows verschlüsselt) |
| `Logs` | Protokolle von Plugins und Installationen |
| `Auftraege.json` | offene Hintergrund-Aufträge (zum Fortsetzen nach einem Neustart) |

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

- `tagstudio.py` – klassische Oberfläche (tkinter), Programmstart
- `tagstudio_web.py` + `web/` – neue Oberfläche (HTML/CSS/JS im App-Fenster über pywebview, sonst im Browser);
  `web/xmleditor.js` XML-Editor, `web/jsontree.js` JSON-Baum, `web/tagger.js` Tagger und Editoren,
  `web/keywheel.js` Camelot-Rad, `web/features.js` Audio-Merkmale, `web/plugins.js` Plugin-Seite,
  `web/player.js` Vorschau-Player, `web/settings.js` Einstellungen, `web/jobs.js` Hintergrund-Aufträge
- `core.py` – gemeinsame Logik beider Oberflächen: Anzeige, Zeichen-Diff, Filter, Laden, Speichern, Einstellungen
- `session.py` – Zustand und Befehle einer Sitzung für die neue Oberfläche
- `id3tags.py` – ID3 lesen/schreiben, MPEG-Infos (ohne externe Bibliotheken)
- `compare.py` – Zuordnung, Vergleich, Kopieren, Regeln für unwichtige Felder
- `tagger.py` – Tagger-Logik: gemeinsame Felder, Tags aus Dateiname, Umbenennen, Spurnummern, Cover,
  Groß-/Kleinschreibung, Suchen & Ersetzen, Cover aus Ordner, Export (CSV/Excel ohne Zusatzpakete)
- `keys.py` – Tonarten: erkennen, umschreiben (Camelot, musikalisch, Open Key), passende Tonarten
- `features.py` – Audio-Merkmale (TXXX, 0–100)
- `xmltools.py` – XML in Feldern und Binärfeldern erkennen, prüfen, formatieren, ersetzen
- `blobs.py` – Binärfelder (GEOB/PRIV): Inhalt erkennen (XML, Text, Base64, binär) und byte-genau ändern
- `backup.py` – Sicherung und Wiederherstellung der Tags, Vergleich Sicherung ↔ Datei (Änderungs-Viewer)
- `undo.py` – Rückgängig/Wiederholen
- `media.py` – lokaler Audio-Server für den Player (Range-Anfragen, Token); `players.py` – externe Player
- `cues.py` – Cue-Punkte aus Serato/Mixed In Key lesen; `waveform.py` – Wellenform-Cache
- `origins.py` – Herkunft der Tags (Kennungsliste); `appsettings.py` – Einstellungen exportieren/importieren/zurücksetzen
- `jobs.py` – Warteschlange für Hintergrund-Aufträge; `stemsview.py` – Stems einem Original zuordnen
- `thumbs.py` – Cover-Vorschaubilder ohne Zusatzpakete
- `plugins.py` + `plugins/` – Plugin-System (siehe [PLUGINS.md](PLUGINS.md)); eingebaut: `plugins/stems`,
  `plugins/beatport`
- `updater.py` – neue Version von GitHub holen (git fetch/pull, nur Vorspulen)
- `version.py` – Versionsnummer (einzige Stelle)
- `packaging/` – Installer: `build.py` (PyInstaller), `windows.iss` (Inno Setup), `make_dmg.sh` (macOS), Icon;
  `release.py` (neue Version vorbereiten)
- `.github/` – Workflows (Tests, Installer/Release, CodeQL), Dependabot, Skript für CodeQL-Issues

## Entwicklung

- **Tests:** `python -m unittest discover -s tests -v` – ID3-Lesen/-Schreiben (v2.3/v2.4, Mehrfachwerte, BOM,
  GEOB, Datumsumwandlung), Vergleich, Tag-Fixer, Sicherung/Wiederherstellung, Sitzung der neuen Oberfläche,
  Tagger-Werkzeuge, Tonarten, Audio-Merkmale, XML und Binärfelder, Versionierung, Updater und Plugins (Stems und
  Beatport mit nachgebauter Gegenseite) – mit synthetischen MP3-Dateien, ohne Zusatzpakete und ohne Netz.
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

**Zwei Kanäle:** **Installer (Releases)** – stabile Versionen für den Alltag. **Git-Klon mit Update-Knopf** – folgt
`main` und bekommt jede Änderung sofort (Testkanal).

**Zweige:** `main` ist immer lauffähig (die CI prüft jeden Commit). Größere Vorhaben entstehen in kurzlebigen
Zweigen (`feature/…`) und werden nach `main` übernommen, wenn sie fertig sind.

## Fehler melden, Ideen, Sicherheit

- **Fehler und Wünsche:** als [Issue](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/new) – mit
  Version, Betriebssystem, Schritten zum Nachstellen und, falls vorhanden, dem Protokoll aus `~/TagStudio/Logs`.
- **Sicherheitslücken** bitte nicht öffentlich, sondern privat melden – siehe [SECURITY.md](SECURITY.md).

## Ausblick

Geplant (Details in den [Milestones](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestones)):

- **3.2.0 – Wiedergabe & Herkunft** (als Beta verfügbar): Vorschau-Player mit Wellenform und Cue-Marken, externe
  Player, Herkunft der Tags, Einstellungsseite mit Export/Import, Stems im Hintergrund und als Spuren im Tagger.
- **3.3.0 – DJ-Set:** Reihenfolge eines Sets nach Tonart (Camelot), BPM und Energie optimieren, Bewertung jedes
  Übergangs, Exporte als M3U8, Rekordbox-XML und CSV.
- **3.4.0 – Online-Metadaten:** MusicBrainz/AcoustID, Deezer, iTunes, Discogs, Last.fm.
- **Plugin-Ideen:** Liedtexte (LRCLIB), Lautheit/ReplayGain, Duplikate finden, Qualitätsprüfung (falsche
  320 kbit/s), Import aus Rekordbox/Traktor/Serato, Bibliothek nach Tags ordnen.
- **Später:** Analyse mit librosa bzw. Essentia-Modellen, Filter und Spalten nach Audio-Merkmalen, Mood-Feld,
  Binärfeld-/JSON-Editor auch im Vergleich, signierte Installer, Intel-Mac, Datenbank-Modul für die Bibliothek.

Verworfen: Umstieg auf Qt (PySide6) – bringt gegenüber der neuen Oberfläche keinen Vorteil.
