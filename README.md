# MarKusSXCH TagStudio

Werkzeugkasten für MP3-Bibliotheken – **Tagger, Vergleich (im Stil von Beyond Compare), Tag-Fixer, Sicherungen**,
weitere Module (z. B. Datenbank) folgen. Für **Windows und macOS**.
Keine Zusatzpakete nötig, nur Python 3.9 oder neuer.

> Bis Version 2.8 hieß das Programm „MP3 Tag Compare“. Einstellungen und Sicherungen von damals werden automatisch übernommen.

**Aktuelle Version:** 2.9 · Änderungen siehe [CHANGELOG.md](CHANGELOG.md)

## Installation & Start

- **Windows:** Python von https://www.python.org/downloads/ installieren („Add python.exe to PATH“ anhaken),
  dann Doppelklick auf `start_windows.bat`.
- **macOS:** Python von https://www.python.org/downloads/ installieren (enthält tkinter),
  dann Doppelklick auf `start_mac.command` (beim ersten Mal: Rechtsklick → Öffnen).
  Homebrew-Python braucht zusätzlich `brew install python-tk`.
- Terminal: `python3 tagstudio.py [links] [rechts]` – Ordner oder Dateien.

## Neue Oberfläche (Version 3, in Arbeit)

Zusätzlich zur klassischen Oberfläche gibt es eine moderne Oberfläche – gleicher Kern, gleiche Einstellungen,
beide lassen sich abwechselnd verwenden.

- **Start:** Doppelklick auf `start_web_windows.bat` bzw. `start_web_mac.command`. Beim ersten Mal wird
  `pywebview` installiert (klein, Internet nötig). Danach öffnet sich ein eigenes App-Fenster.
  Ohne pywebview öffnet sich dieselbe Oberfläche im Browser (`python tagstudio_web.py --browser`).
- **Schon dabei:** Pfade mit Verlauf und Ordner-/Dateiauswahl, Zuordnung, Unterordner; Paarliste mit
  Status-Filtern (≠ ≈ = ◧), Suche in Dateinamen und Werten, erweiterter Filter nach Feld/Bedingung/Seite;
  Vergleich mit zeichengenauen Markierungen, Pfeil-Knöpfen pro Feld, Alles/Fehlende nach links/rechts,
  Mehrfachauswahl (Klick, Shift, Strg/Cmd), Bearbeiten per Doppelklick (Tab = nächstes Feld, Mehrfachwerte mit ¦),
  Kontextmenü (kopieren, bearbeiten, entfernen, Link öffnen, im Explorer/Finder zeigen), klickbare Links,
  Cover-Vorschau mit Großansicht, Filter Alle/Unterschiede/Gleiche, Unwichtige, leere Felder, Feldsuche,
  Rückgängig/Wiederholen, Speichern mit automatischer Sicherung, Hell/Dunkel.
- **XML-Editor:** Felder mit XML-Inhalt (z. B. Analysedaten in Benutzertexten) tragen das Kennzeichen **XML**.
  Klick darauf oder Doppelklick öffnet den Editor: **Baum** (Attribute und Texte direkt bearbeiten, auf-/zuklappen,
  suchen) und **Quelltext** (farbig, Zeilennummern). Laufende Prüfung mit Zeile/Spalte der Fehlerstelle (Klick springt
  hin), **Formatieren** (eingerückt) und **Kompakt** (eine Zeile). Binärfelder mit XML (GEOB/PRIV) nur ansehen.
  Strg/Cmd+Enter übernimmt, Esc schließt. Die klassische Oberfläche hat denselben Editor (Quelltext-Ansicht).
- **Update:** Unten in der Seitenleiste „Nach Update suchen“. TagStudio prüft beim Start selbst, ob es auf GitHub
  eine neue Version gibt (Punkt am Knopf). Ein Klick lädt sie (`git pull`, nur wenn der Programmordner keine
  eigenen Änderungen hat) und startet TagStudio neu – die gewählten Ordner werden wieder eingelesen.
  Voraussetzung: Der Programmordner ist ein Git-Klon und git ist installiert. Ungespeicherte Änderungen werden
  vorher abgefragt.
- **Splitter:** Seitenleiste, Paarliste und Tabellenspalten lassen sich mit der Maus ziehen (oder per Tastatur
  mit ←/→ auf dem Griff). Die Seitenleiste lässt sich einklappen (Knopf unten, Doppelklick auf den Splitter oder
  ganz schmal ziehen). In der Tabelle verschiebt der Griff zwischen den Wertespalten die Aufteilung links/rechts,
  der Griff rechts neben „Feld“ die Breite der Feldspalte. Doppelklick setzt jeweils zurück. Alles wird gemerkt.
- **Tagger** (Seitenleiste): Ordner oder Datei einlesen, Liste mit Titel/Künstler/Album/Spur/Jahr/Genre (sortierbar
  per Klick auf die Spalte, filterbar). Eine oder mehrere Dateien markieren (Klick, Shift, Strg/Cmd, Strg/Cmd+A) und
  rechts gemeinsam bearbeiten – Felder mit „‹verschieden›“ bleiben unverändert, bis du etwas einträgst. Cover für die
  Auswahl setzen/entfernen, ID3-Version wählen, weitere Felder (einzelne Datei) bearbeiten/entfernen, XML-Editor.
  Werkzeuge mit Vorschau: **Tags aus Dateiname** (Muster z. B. `%track% - %artist% - %title%`, `%dummy%` überspringt),
  **Dateien umbenennen** (aus Tags, ungültige Zeichen → `_`, Kollisionen werden erkannt; sofort, nicht über
  „Speichern“), **Spurnummern** (in Listenreihenfolge, optional mit Gesamtzahl), **Groß-/Kleinschreibung**
  (Titel-Schreibweise, Satzanfang, GROSS, klein; Abkürzungen wie DJ/AC/DC bleiben, kleine Wörter wahlweise klein),
  **Suchen & Ersetzen** (über alle markierten Dateien, wählbare Felder, ganze Wörter, reguläre Ausdrücke),
  **Cover aus Ordner** (cover/folder/front/album.jpg|png im Ordner der Datei, sonst das größte Bild; wahlweise nur
  für Dateien ohne Cover) und **Liste exportieren** (Excel .xlsx oder CSV mit Semikolon, inkl. Camelot-Spalte).
  **Tonart mit Camelot-Rad:** Knopf neben dem Feld „Tonart“ öffnet das Rad (aussen Dur, innen Moll); Klick setzt die
  Tonart der markierten Dateien, die aktuelle und die harmonisch passenden Tonarten (±1, Paralleltonart) sind
  hervorgehoben. Geschrieben wird wahlweise als Camelot (8A), musikalisch (Am) oder Open Key (1m); erkannt werden
  auch Schreibweisen wie A minor, F♯m, a-Moll oder Es-Dur. „Schreibweise vereinheitlichen“ schreibt alle markierten
  Dateien um. In der Liste zeigt die Spalte „Tonart“ farbige Camelot-Codes (sortierbar); bei einer markierten Datei
  sind die passenden Titel umrandet. Vergleich und Tagger arbeiten mit
  denselben Dateien – Änderungen sind in beiden sichtbar und werden zusammen gespeichert.
- **Plugins** (Seitenleiste): Erweiterungen ein-/ausschalten, fehlende Python-Pakete per Knopf installieren;
  Aktionen erscheinen im Tagger unter „Plugins“. Eingebaut ist **Stems** (Titel in Gesang, Schlagzeug, Bass,
  Instrumental … trennen, mit audio-separator). Eigene Plugins in `~/TagStudio/Plugins` – Anleitung in
  [PLUGINS.md](PLUGINS.md).
- **Tag-Fixer** (Seitenleiste): Mehrfachwerte vereinheitlichen – Bereich (aktuelles Paar, eine Seite, markierte Paare,
  alle Dateien, Tagger-Auswahl), Felder, erkannte Trenner, Ausgabe (Trennzeichen oder ID3v2.4-Mehrfachwerte),
  laufende Vorschau.
- **Sicherungen** (Seitenleiste): alle Sicherungen, Dateien mit Status (wiederherstellbar/gleich/fehlt/Audio geändert),
  markierte oder alle wiederherstellen (vorher wird der aktuelle Stand selbst gesichert), Sicherung löschen,
  automatische Sicherung ein/aus, Ordner ändern/öffnen.
- **Sammelkopie:** In der Paarliste mehrere Paare mit Strg/Cmd- oder Shift-Klick markieren → „◀ Sammelkopie“ /
  „Sammelkopie ▶“ → Felder wählen.
- **Feld hinzufügen:** Knopf „+ Feld“ über der Tabelle oder Kontextmenü.
- **Bilder:** Rechtsklick auf ein Cover (oder die Bild-Zeile): anzeigen, ersetzen, exportieren, entfernen;
  Klick auf den leeren Cover-Platz fügt ein Cover hinzu. (Dateidialoge gibt es im App-Fenster; im Browser-Modus nur
  unter Windows/Linux.)
- **Tastatur:** Strg/Cmd+S speichern · Strg/Cmd+Z / Strg+Y rückgängig/wiederholen · Alt+← / Alt+→ Markierte
  kopieren · Strg/Cmd+A alle Felder markieren · F5 neu einlesen · ↑/↓ in Paarliste und Tabelle.

## Oberfläche

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

## Cover-Vorschau

Über der Tabelle zeigt jede Seite alle eingebetteten Bilder als Vorschau mit Größe (z. B. 1400×1400 · 245 KB).
Unterschiedliche Cover sind **rot umrandet**, in der Mitte steht = oder ≠. Klick auf ein Bild öffnet eine große
Ansicht (mit „Im Bildbetrachter öffnen“ und „Speichern unter“). **▣ Cover** blendet die Leiste aus/ein.
Technik: Tk kann kein JPEG – die Vorschau wird ohne Zusatzpakete erzeugt (Windows: eingebautes .NET über PowerShell,
macOS: `sips`, Linux: ImageMagick; falls Pillow installiert ist, wird es bevorzugt) und in
`~/TagStudio/cache` zwischengespeichert. Die erste Vorschau eines Covers dauert unter Windows evtl. ~1 s.

## Suchen & Filtern

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

## Einlesen großer Ordner

Beim Vergleichen werden zuerst alle MP3-Dateien gezählt, danach erscheint ein Fortschrittsbalken
mit Anzahl, Prozent, geschätzter Restzeit und aktuellem Dateinamen. **Abbrechen** (oder Esc) stoppt
sofort – die bisherige Ansicht bleibt dann unverändert. Bei schnellen Vorgängen erscheint der Dialog gar nicht erst.
Hinweis: Bei OneDrive-Ordnern mit „nur online“-Dateien lädt Windows diese beim Einlesen herunter.

## Leere Felder einblenden

Toolbar **☐ Leere Felder** → wählen: ID3v1, ID3v2.3, ID3v2.4 oder alle. Dann erscheinen alle Felder, die der
jeweilige Standard vorsieht (Text-, URL-, Kommentar-, Liedtext- und Cover-Felder), auch wenn sie unbeschrieben sind.
Doppelklick auf ein leeres Feld füllt es.

## Tag-Fixer: Mehrfachwerte

Toolbar **¦ Mehrfachwerte** vereinheitlicht Felder mit mehreren Werten (z. B. „Adriatique; Vincent Vossen / Yubik“):

- **Dateien:** aktuelles Paar (beide/links/rechts), markierte Paare oder alle geladenen Dateien.
- **Felder:** Künstler, Album-Künstler, Komponist, Texter, Genre, Sortierfelder … oder alle Textfelder.
- **Als Trenner erkennen:** Null (v2.4), `;`, ` / `, `\\` (Mp3tag) – optional `,`, `/`, `&`, `feat.`, ` x `.
- **Ausgabe:** Trennzeichen (Standard `, `) **oder ID3v2.4-Standard** (echte, null-getrennte Mehrfachwerte).
  Für Letzteres können v2.3-Dateien automatisch auf v2.4 umgestellt werden; sonst erhalten sie `; `.
- Doppelte Werte werden auf Wunsch entfernt. Eine **Vorschau** zeigt jede Änderung vorher/nachher.
- Beim Bearbeiten trennt `¦` einzelne Werte (wird als v2.4-Mehrfachwert gespeichert; in v2.3 als ` / `).
- Hinweis: Nicht alle Programme zeigen v2.4-Mehrfachwerte vollständig an (manche nur den ersten Wert).

## Bedienung

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

## Rückgängig / Wiederholen

Jede Änderung – Feld bearbeiten, ◀/▶, Auswahl/Alles/Fehlende kopieren, Sammelkopie, Tag-Fixer, Feld entfernen,
Bild ersetzen, Paar verwerfen – lässt sich mit **↶ Rückgängig** (Strg/Cmd+Z) zurücknehmen und mit
**↷ Wiederholen** (Strg+Y bzw. Strg/Cmd+Shift+Z) erneut ausführen. Bis zu 200 Schritte, über alle Dateien.
Auch nach dem Speichern kann man zurückgehen – die Datei gilt dann wieder als „geändert“ und kann erneut gespeichert werden.
Beim Laden neuer Ordner wird der Verlauf geleert. Während man in einem Feld tippt, gilt Strg+Z für das Eingabefeld.

## Automatische Sicherung & Wiederherstellen

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

## Fenster & Dialoge

Alle Dialoge (Sicherungen, Tag-Fixer, Sammelkopie, Feld hinzufügen, Cover-Ansicht, Bearbeiten) sowie Meldungen
und Datei-Dialoge öffnen sich **zentriert über dem Programmfenster** – also auf dem Bildschirm, auf dem das
Programm gerade liegt. Meldungen aus einem Dialog heraus erscheinen über diesem Dialog.

## Einstellungen

Werden in `~/.tagstudio.json` gespeichert (Design, Fenstergröße, Pfad-Verlauf, Filter).
Unter `"trivial"` steht die Liste der unwichtigen Felder (Platzhalter `*` erlaubt), z. B.
`"TLEN"`, `"TXXX:Acoustid*"`, `"COMM:iTunNORM"` – frei anpassbar.

## Technisches

**Praxistest (Version 2.5):** 1'493 Dateien einer echten DJ-Bibliothek (ID3v2.4, Beatport/beaTunes/Mixed In Key/Serato)
wurden eingelesen sowie auf Kopien neu geschrieben, zwischen v2.4 und v2.3 umgewandelt und einzeln geändert –
ohne Lesefehler, ohne Datenverlust, Audio jeweils byte-identisch.

- **DJ-Daten** (eingebettete GEOB-Objekte wie *Serato Markers2*, Mixed-In-Key *Key/Energy/CuePoints*, *PlatinumNotes*)
  werden nach ihrer Beschreibung zugeordnet, lesbar angezeigt und unverändert erhalten. Sie gelten standardmäßig als
  „unwichtig“, da Cue-Punkte/Beatgrids zu genau einem Track gehören.

- Liest ID3v2.2/2.3/2.4 und ID3v1, schreibt in der vorhandenen Version (v2.3 bei Dateien ohne Tag).
- Unveränderte Felder werden byte-genau zurückgeschrieben, Audiodaten nie angefasst.
  Wächst der Tag, wird über eine temporäre Datei geschrieben und erst danach ersetzt.
- Beim Kopieren zwischen v2.3 und v2.4 werden Felder korrekt umgewandelt (z. B. Datum TDRC ↔ TYER/TDAT).
- Tipp: Vor dem ersten Einsatz an einer Kopie der Musik ausprobieren.

## Dateien

- `tagstudio.py` – klassische Oberfläche (tkinter), Programmstart
- `tagstudio_web.py` + `web/` – neue Oberfläche (HTML/CSS/JS im App-Fenster über pywebview, sonst im Browser)
- `core.py` – gemeinsame Logik beider Oberflächen: Anzeige, Zeichen-Diff, Filter, Laden, Speichern, Einstellungen
- `session.py` – Zustand und Befehle einer Sitzung für die neue Oberfläche
- `undo.py` – Rückgängig/Wiederholen
- `xmltools.py` – XML in Feldern erkennen, prüfen, formatieren/kompakt schreiben
- `tagger.py` – Tagger-Logik: gemeinsame Felder, Tags aus Dateiname, Umbenennen, Spurnummern, Cover,
  Groß-/Kleinschreibung, Suchen & Ersetzen, Cover aus Ordner, Export (CSV/Excel ohne Zusatzpakete)
- `keys.py` – Tonarten: erkennen, umschreiben (Camelot, musikalisch, Open Key), passende Tonarten
- `plugins.py` + `plugins/` – Plugin-System (siehe [PLUGINS.md](PLUGINS.md)); eingebaut: `plugins/stems`
- `updater.py` – neue Version von GitHub holen (git fetch/pull, nur Vorspulen)
- `compare.py` – Zuordnung, Vergleich, Kopieren, Regeln für unwichtige Felder
- `id3tags.py` – ID3 lesen/schreiben, MPEG-Infos (ohne externe Bibliotheken)
- `backup.py` – Sicherung und Wiederherstellung der Tags
- `thumbs.py` – Cover-Vorschaubilder ohne Zusatzpakete


## Entwicklung

- **Tests:** `python -m unittest discover -s tests -v` – prüfen ID3-Lesen/-Schreiben (v2.3/v2.4, Mehrfachwerte,
  BOM, GEOB, Datumsumwandlung), Vergleich, Tag-Fixer und Sicherung/Wiederherstellung mit synthetischen MP3-Dateien.
  Keine Zusatzpakete nötig.
- **Automatische Prüfung (GitHub Actions):** Bei jedem Push laufen die Tests auf Windows, macOS und Linux
  (`.github/workflows/tests.yml`).
- **Versionen:** Jede Version bekommt einen Git-Tag (`v2.9` …) und einen Eintrag in `CHANGELOG.md`.
- **Arbeitsweise:** Neue Funktionen in einem eigenen Branch entwickeln, per Pull Request nach `main` übernehmen.

## Ausblick

- Umstieg der Oberfläche auf Qt (PySide6)
- Paketierung als eigenständige Anwendung (`.exe` / `.app`)
- Datenbank-Modul für die Musikbibliothek
