# Changelog – MarKusSXCH TagStudio

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/) (MAJOR.MINOR.PATCH). Versionen bis 2.8 hießen „MP3 Tag Compare“.
Neue Einträge kommen laufend unter **Unveröffentlicht**; `python packaging/release.py X.Y.Z` macht daraus eine Version.

## [Unveröffentlicht]

### Neu
- Player: **Tonart und BPM** des laufenden Titels neben dem Titel (#46); **Serato-Loops** per Klick auf die Marke als
  Schleife abspielen, erneuter Klick beendet sie (#47); **Zeit und Cue** beim Überfahren der Leiste (#48); Taste
  **M** schaltet stumm (#49).
- Herkunft: **Klick auf ein Kennzeichen** bei „Weitere Felder“ zeigt nur Felder dieser Herkunft, erneuter Klick alle (#50).
- **Vergleich: Felder nach Herkunft entfernen** – Knopf „Herkunft“: z. B. Serato-Daten nur rechts, im aktuellen,
  in markierten oder allen Paaren; Vorschau und Rückgängig (#45).
- Tagger: **Breite der Spalte „Datei“** per Griff im Spaltenkopf einstellbar (Doppelklick = automatisch), wird gemerkt (#41).
- Einstellungen: **Cache verwalten** – Anzahl und Grösse der Wellenformen und Cover-Vorschauen, je „Leeren“ und
  „Ordner“ (#42).
- **Länge** des Titels gross neben dem Cover im Tagger, bei mehreren markierten Titeln die Gesamtlänge (#34).
- **Tempo (BPM)** als sortierbare Spalte im Tagger; im Vergleich als Spalte in der Paarliste (abweichende Werte
  „124≠126“ hervorgehoben) und als Kennzeichen im Dateikopf (#35).
- Player: **Startpunkt als Umschalter** (Start · 30 % · 1:00 · Cue) statt Auswahlliste (#36) und **Cue-Sprung-Knöpfe**
  (voriger/nächster Cue, nur bei Titeln mit Cues) (#37).
- Herkunft der Tags: Felder ohne bekannte Anwendung tragen das Kennzeichen **v2.3/v2.4** (ID3-Version der Datei) (#38).
  Neue Herkünfte **Spotify** und **Discogs**; `GEOB:Energy`/`GEOB:Key` → Mixed In Key, `GEOB:PlatinumNotes` → Platinum
  Notes, `TXXX:Meter` und `TXXX:MOOD_*` → beaTunes (#39).
- **Stems als Spuren im Tagger:** erzeugte Stems (Ordner „<Titel> – Stems“ bzw. fester Stems-Ordner) erscheinen
  nicht mehr als eigene Titel, sondern **aufklappbar unter dem Original** (▸ / Kennzeichen „4 Stems“, →/← auf-
  und zuklappen, „Stems ▾/▸“ für alle). MP3-Spuren sind normal bearbeitbar, FLAC/WAV-Spuren lassen sich anhören
  und im Explorer/Finder zeigen. Sortieren und Filtern beziehen sich auf die Originale. **„Stems: Tags vom
  Original …“** überträgt die Tags auf die MP3-Spuren (ohne DJ-Analysedaten, Titel mit „(Vocals)“ usw.). Nach
  „Stems erzeugen“ erscheinen neue Spuren direkt aufgeklappt, ohne neu einzulesen. Einstellung „Stems als eigene
  Titel anzeigen“ für das bisherige Verhalten.
- **Stems im Hintergrund:** „Stems erzeugen …“ legt einen Auftrag an und schliesst sofort – Tagger, Vergleich und
  Speichern bleiben benutzbar. Warteschlange (immer ein Auftrag gleichzeitig, Worker mit niedriger Priorität),
  Anzeige unten in der Fußleiste („Stems: 2 von 7 · 45 %“), Liste mit Abbrechen, Ordner öffnen und Protokoll,
  Meldung bei Fertigstellung. Beim Beenden wird nachgefragt; offene Aufträge werden beim nächsten Start zum
  Fortsetzen angeboten. Allgemein für Plugins: `"background": true` in der Aktion oder in `plugin.json`.
- **Herkunft der Tags:** kleines Kennzeichen bei „Weitere Felder“ und im Vergleich, welche Anwendung ein Feld
  geschrieben hat (MusicBrainz, Serato, Mixed In Key, Beatport, Traktor, Rekordbox, beaTunes, Lexicon, Platinum
  Notes, iTunes, Windows Media Player, Amazon, ReplayGain, Kodierer, TagStudio-Plugins), Tooltip mit Erklärung.
  Im Tagger nach Herkunft filtern und **„Felder nach Herkunft entfernen …“** (Vorschau, Rückgängig). In den
  Einstellungen eigene Zuordnungen (Muster → Anwendung) und „als unwichtig“ je Herkunft. Plugins geben ihre
  Felder in `plugin.json` unter `fields` an (Beatport: `TXXX:BEATPORT_TRACK_ID`).
- **Einstellungen** als eigene Seite: Design, Tonart-Schreibweise, ID3-Version beim Speichern (beibehalten/immer
  v2.3/immer v2.4), Sicherung und Ordner, Player (Startpunkt, Wellenform, Durchhören, externe Player), Liste der
  unwichtigen Felder zum Bearbeiten (mit „Standard“), Plugins. **Exportieren/Importieren** als Datei ohne
  Zugangsdaten (Import mit Auswahl der Bereiche; Pfade eines anderen Systems nicht vorgewählt) und **Zurücksetzen**
  einzelner Bereiche oder aller Einstellungen – die alte Datei wird vorher nach `~/TagStudio/Einstellungen` gesichert.
  Player-Einstellungen liegen jetzt in `~/.tagstudio.json` statt im Browser-Speicher (werden übernommen).
- **Wellenform** im Vorschau-Player: einmal beim ersten Abspielen berechnet und im Cache abgelegt
  (`~/TagStudio/cache/wave`, bleibt beim Bearbeiten der Tags und Umbenennen gültig); im Menü ⋯ abschaltbar.
- **Cue-Marken** aus Serato (Markers2: Cues, Loops, Farben, Namen) und Mixed In Key (CuePoints) über der Leiste;
  Klick springt hin, Alt+Bild↑/↓ zum vorigen/nächsten Cue, Startpunkt „ab 1. Cue“.
- **Vorschau-Player** in der Fußleiste (Tagger und Vergleich): Leertaste spielt/pausiert, ⏮/⏭ und Folgen der
  Auswahl, am Titelende weiter zum nächsten Titel, Shift+←/→ spult 10 s, Startpunkt Anfang/30 %/1:00, Lautstärke
  wird gemerkt. Im Vergleich wechselt **A/B** zwischen linker und rechter Datei an derselben Stelle. Die Dateien
  liefert ein lokaler Mini-Server (nur 127.0.0.1, nur freigegebene Dateien, Token, Spulen per Range).
- **Externe Player:** markierte Titel mit Strg/Cmd+P oder über ⋯ in einem eigenen Player öffnen (foobar2000, VLC,
  Rekordbox, Music …) oder im Standardprogramm des Systems. Einrichtung unter „Externe Player…“ mit Platzhaltern
  `{files}`, `{file}`, `{folder}`, `{m3u}`; unter macOS auch .app-Programme.

### Geändert
- Herkunft: Standardfelder (Titel, Künstler, BPM …) zeigen das v2.3/v2.4-Kennzeichen nicht mehr – nur noch Benutzer-
  und Binärfelder ohne bekannte Anwendung. Einstellung „auch bei Standardfeldern“ unter Herkunft der Tags (#40).
- Stems-Zuordnung beim Einlesen liest jeden Ordner nur noch einmal – deutlich schneller bei grossen Bibliotheken und
  Netzlaufwerken (#43).
- Vorschau-Player: Der lokale Audio-Server gibt nur noch die 300 zuletzt genutzten Dateien frei (#44).
- Auswahlknöpfe (Radio) in Dialogen bleiben bei wenig Platz klein und umbrechen sauber.
- Milestones neu geordnet: 3.2.0 Wiedergabe & Herkunft, 3.3.0 DJ-Set, 3.4.0 Online-Metadaten.

### Behoben
- Klick auf L/R im Player bzw. auf den Design-Umschalter der Einstellungen setzte nebenbei den Filter des Vergleichs
  zurück (alle Segment-Schalter lösten den Filter-Befehl aus).
- Hintergrund-Aufträge (seit 3.2.0-beta.2): Beim Beenden konnte der gerade abgebrochene Auftrag den Vermerk der
  offenen Warteschlange überschreiben – dann fehlte das Angebot zum Fortsetzen. Gefunden durch einen sporadisch
  fehlschlagenden Test in GitHub Actions.
- CodeQL #33: Der Einstellungs-Export galt fälschlich als Klartext-Speicherung von Geheimnissen (Filter umbenannt;
  Zugangsdaten wurden schon vorher nicht exportiert).

## [3.1.1] – 2026-10-09

### Behoben
- **Stems:** MP3-Ausgabe scheiterte mit „Encoder not found“, wenn im PATH bereits ein abgespecktes „ffmpeg“ eines
  anderen Programms lag (ohne MP3-Encoder). Stems verwendet jetzt immer das eigene, vollständige FFmpeg aus
  imageio-ffmpeg. Der Stems-Test prüft das mit einem absichtlich defekten ffmpeg im PATH.
- **Stems:** Der Fortschritt innerhalb eines Titels kam trotz 3.1.0 nicht an – die Fortschrittsmeldungen standen in
  derselben Zeile hinter dem Balken von tqdm und wurden übersehen. Jetzt werden sie überall in der Zeile erkannt.
  Gefunden mit dem neuen Stems-Test.
- **Stems:** Beim Modell-Download stand teils „799 % von 0 MB“ (Server meldet falsche Grösse) – jetzt Prozent nur bei
  plausibler Grösse, sonst die geladene Menge in MB. Gefunden mit dem neuen Stems-Test.
- **Sicherheit (CodeQL):** Der eingebaute Webserver (Browser-Modus) setzt den Content-Type nur noch aus einer festen
  Liste statt aus dem angefragten Pfad (HTTP-Header-Injection ausgeschlossen). Test-Workflow mit minimalen Rechten
  (`contents: read`).

### Geändert
- Release-Workflow: Titel neuer Releases lautet „TagStudio X.Y.Z“ (wie die bisherigen Releases).
- GitHub: Workflow „Stems-Test“ – echter Ende-zu-Ende-Test des Stems-Plugins auf Windows und macOS (Installation
  wie in der App, Trennung eines synthetischen Testtitels, Prüfung von Fortschritt, Spuren und Tags).
- GitHub: Code-Scanning mit CodeQL (Python, JavaScript, Workflows; bei jedem Push, Pull Request und wöchentlich);
  Funde werden automatisch als Issues (bug, security, codeql) im nächsten Patch-Milestone angelegt und nach der
  Behebung geschlossen.
- README überarbeitet: Funktionsüberblick, Tagger mit allen Editoren (Feld-Editor, Einzelwerte, JSON-Baum,
  XML, Binärfelder, Farben), Plugins, Datenablage, GitHub-Abläufe (CodeQL-Issues, Dependabot, automatisches
  Release), Fehler melden, Ausblick mit Milestones.
- `SECURITY.md`: unterstützte Versionen und privates Melden von Sicherheitslücken; `release.py` zieht die Tabelle bei neuen MINOR/MAJOR-Versionen automatisch nach.
- Release-Workflow: Eine neue Versionsnummer auf `main` (nach `release.py X.Y.Z`) wird automatisch veröffentlicht –
  der Workflow baut, testet und legt Tag `vX.Y.Z` und das Release selbst an. Von Hand gesetzte Tags gehen weiterhin.
- Dependabot hält die GitHub-Actions im Workflow aktuell (monatlich, als ein gemeinsamer Pull Request).

## [3.1.0] – 2026-10-09

### Neu
- **Tagger – Weitere Felder:** Spaltenteiler zwischen Feldname und Wert (ziehen, Doppelklick = Standard, Breite wird
  gemerkt) und ein **Feld-Editor** (Stift-Knopf oder Doppelklick): grosses mehrzeiliges Textfeld, Zeichen-/Zeilenzähler,
  Blättern zum vorigen/nächsten Feld (‹ › oder Alt+↑/↓, speichert dabei), „Feld entfernen“, Strg/⌘+Enter übernimmt.
  Mehrzeilige Felder (Kommentare, Liedtexte) sind jetzt bearbeitbar und werden in der Liste mehrzeilig angezeigt.
- **Tagger – Links:** URLs werden wie im Vergleich als Links dargestellt und öffnen per Klick im Browser
  (Weitere Felder; bei Standardfeldern wie Kommentar erscheint ein Link-Knopf neben dem Eingabefeld).
- **Feld-Editor – Einzelwerte:** Mehrfachwerte, getrennt durch NULL-Zeichen (ID3v2.4), Semikolon oder Komma, werden
  als einzelne Werte bearbeitet: Wert hinzufügen (auch Enter), entfernen, umsortieren; Umschalten auf „Text“ und
  Wahl der Trennung (z. B. „House; Techno“ in echte ID3v2.4-Mehrfachwerte umwandeln). Doppelklick auf ein solches
  Feld öffnet direkt die Einzelwerte.
- **XML in Binärfeldern bearbeiten:** GEOB-, PRIV- und andere Binärfelder, in denen ein XML-Abschnitt steckt
  (UTF-8 oder UTF-16, auch mitten zwischen anderen Bytes), lassen sich jetzt im XML-Editor bearbeiten statt nur
  ansehen – im Vergleich, im Tagger und in der klassischen Oberfläche. Ersetzt wird nur der XML-Abschnitt in seiner
  ursprünglichen Kodierung; Frame-Kopf (MIME, Dateiname, Beschreibung, Besitzer) und alle Bytes davor/danach bleiben
  byte-genau erhalten. Der Editor zeigt Feldtyp, Kodierung und Grösse des XML-Teils an.
- **Binärfeld-Editor (GEOB, PRIV):** Bei „Weitere Felder“ haben jetzt auch Binärfelder einen Stift-Knopf
  (bzw. Doppelklick). Der Editor zeigt den Kopf (Beschreibung, MIME-Typ und Dateiname änderbar bzw. Besitzer) und
  den Inhalt: lesbarer Text und Base64-kodierter Text/JSON (z. B. Mixed In Key) sind direkt bearbeitbar
  (JSON formatieren, beim Übernehmen wieder Base64-kodiert), XML öffnet den XML-Editor, unbekannte Binärdaten
  erscheinen als Hex-Ansicht. Geändert wird nur, was bearbeitet wurde; mit Rückgängig.
- **JSON-Baum:** JSON (im Binärfeld-Editor, z. B. Mixed In Key, und in Textfeldern im Feld-Editor) wird wie im
  XML-Editor als aufklappbarer Baum mit Schlüssel/Wert-Paaren angezeigt. Bearbeitbar sind nur die Werte – Text,
  Zahlen (mit Prüfung, ungültige rot), Ja/Nein als Häkchen; Schlüssel und Aufbau bleiben fest. Beim Übernehmen
  werden nur die geänderten Werte im Originaltext ersetzt, Format, Einrückung und Escapes bleiben exakt erhalten.
  Die Textansicht steht weiterhin zur Verfügung.
- **JSON-Expertenmodus** (Häkchen im Baum, wird gemerkt): Einträge hinzufügen – bei Listen „+ Element (Kopie des
  letzten)“, z. B. ein neuer Cue-Punkt mit gleichem Aufbau, oder ein leeres Element eines Typs; bei Objekten neuer
  Schlüssel mit Typ (Text, Zahl, Ja/Nein, Objekt, Liste, null) –, Einträge duplizieren (⧉) und entfernen (✕).
  Neue Einträge übernehmen Einrückung und Trennzeichen der Nachbarn.
- **Farben:** Felder mit „COLOR“/„Farbe“ im Namen (z. B. TXXX:COLOR) und JSON-Werte unter „color“ werden, wenn sie
  ein Hex-Wert sind (#RGB, #RRGGBB, 0xAARRGGBB, RRGGBB …), als Farbfeld angezeigt und lassen sich per Farbwähler
  ändern; die Schreibweise (Präfix, Gross-/Kleinschreibung, Alpha-Anteil) bleibt erhalten.

### Behoben
- **Stems:** Der Fortschrittsbalken blieb während der Trennung eines Titels auf 0 stehen (er sprang erst nach dem
  ganzen Titel weiter – bei einem einzelnen Titel also nie). Jetzt zeigt er den Fortschritt innerhalb des Titels in
  Prozent (alle Demucs-Durchgänge), beim ersten Gebrauch auch den Modell-Download in Prozent und MB.
- Plugin-API: `ctx.progress(i, total, text, frac)` – `frac` (0–1) = Anteil des gerade laufenden Elements.

### Geändert
- **Beatport:** Die Vorschau zeigt jetzt **alle Felder, die Beatport liefert** – auch solche, die schon gleich sind
  (grau mit „=“, nicht wählbar), in den Optionen abgewählte (ungehakt, bei Bedarf anhakbar) und ein verfügbares Cover
  (als Info). Angehakt wird weiterhin nur, was nach den Optionen übernommen werden soll.
- **Tonart in Camelot** wird immer zweistellig mit führender Null geschrieben (`01A` statt `1A`, `08B` …) – gilt für
  Tagger, Camelot-Rad, Beatport und „Schreibweise umstellen“ (wandelt vorhandene `1A` in `01A` um). Erkannt wird
  beides wie bisher.
- Plugin-API: `ctx.propose(…, show_same=True)` für unveränderte Werte; Cover-Vorschläge ohne Daten sind Info-Zeilen.

## [3.0.1] – 2026-10-09
Fehlerbehebungen.

### Behoben
- **Plugins:** Ein fehlerhaftes `plugin.json` (z. B. `"api": "1.0"`, Liste statt Objekt, falsche Einträge bei
  `requires`/`install`/`external`) legte die ganze Plugin-Seite und die Plugin-Knöpfe im Tagger lahm. Jetzt erscheint
  nur dieses Plugin mit Fehlermeldung, alle anderen laufen weiter.
- **Rückgängig:** Brach ein Plugin mitten im Ändern ab, blieben seine Teiländerungen im nächsten Rückgängig-Schritt
  hängen (falsche Beschriftung, Rückgängig nahm mehr zurück als erwartet). Der Schritt wird jetzt immer abgeschlossen.
- **Plugin-Vorschau:** Gleich benannte Dateien aus verschiedenen Ordnern (z. B. zweimal `01 Intro.mp3`) wurden zu
  einer Gruppe zusammengelegt. Sie bleiben jetzt getrennt, mit Ordnername zur Unterscheidung.
- **Beatport:** Titel in nicht-lateinischer Schrift (Kyrillisch, Japanisch …) galten immer als „gleich“, falsche
  Treffer waren sogar vorab angehakt. Jetzt wird die Schrift beim Vergleich erhalten.
- **Beatport:** Ein `Retry-After` als Datum (statt Sekunden) brach den ganzen Abruf ab.
- **Vergleich/Sicherungs-Viewer:** Nach Emoji im Wert wurden die Markierungen um ein Zeichen verschoben angezeigt.
- **Update-Knopf:** Ein ausstehender Wechsel vom alten Zweig `web-ui` auf `main` wurde nicht angeboten, solange es
  keine neuen Änderungen gab.
- **Versionierung:** `release.py` sortierte Vorabversionen als Text (`beta.10` galt als älter als `beta.9`).
- **Installer-Bau:** GitHub-Actions auf aktuelle Versionen (Node 24) umgestellt – keine Deprecation-Warnungen mehr.

## [3.0.0] – 2026-10-09
Grosses Update: neue Oberfläche mit Tagger und Plugins (entwickelt im Zweig `web-ui`, jetzt in `main`).

### Neu
- **Neue Oberfläche** (`tagstudio_web.py`, Ordner `web/`): modernes Design mit Seitenleiste, Hell/Dunkel,
  Paarliste mit Status-Filtern und Suche, Vergleich mit zeichengenauen Markierungen, Pfeil-Knöpfen,
  Bearbeiten per Doppelklick, Kontextmenü, Cover-Vorschau, Rückgängig/Wiederholen, Speichern mit Sicherung.
  Läuft im eigenen App-Fenster (pywebview) oder – ohne pywebview – im Browser.
  Start: `start_web_windows.bat` / `start_web_mac.command`.
- Splitter für Seitenleiste (einklappbar), Paarliste und Tabellenspalten; Layout wird gemerkt.
- **Tagger** in der neuen Oberfläche: Dateiliste (sortier-/filterbar), Mehrfachbearbeitung, Cover, ID3-Version,
  Tags aus Dateiname, Umbenennen nach Tags, Spurnummern, weitere Felder; gemeinsames Dateiregister mit dem Vergleich.
- Tagger-Werkzeuge (alle mit Vorschau, rückgängig machbar): **Groß-/Kleinschreibung vereinheitlichen**,
  **Suchen & Ersetzen** über viele Dateien, **Cover aus Bild im Ordner** (folder.jpg …),
  **Liste als Excel/CSV exportieren**.
- **Camelot-Rad** für die Tonart im Tagger: Tonart per Klick setzen, passende Tonarten hervorgehoben, Schreibweise
  Camelot/musikalisch/Open Key wählbar und für viele Dateien vereinheitlichen; Spalte „Tonart“ mit farbigen Codes.
- **Audio-Merkmale** im Tagger: zehn TXXX-Felder (Energy, Danceability, Happiness, Valence, Acousticness,
  Instrumentalness, Liveness, Speechiness, Brightness, Aggressiveness), 0–100, Schieberegler, Mehrfachauswahl,
  Export-Spalten.
- **Plugin-System** (`plugins.py`, Seite „Plugins“): Plugins aus `plugins/` und `~/TagStudio/Plugins`, Status,
  Ein/Aus, fehlende Pakete per pip installieren, Formulare aus den Optionen, Ausführung im Hintergrund mit
  Fortschritt/Abbruch, Tag-Änderungen mit Rückgängig. Anleitung: `PLUGINS.md`.
- Eingebautes Plugin **Stems**: Titel mit audio-separator (Demucs, BS-RoFormer, Mel-Band-RoFormer) in
  Einzelspuren trennen; FLAC/WAV/MP3 (MP3 mit Tags und Cover).
- Plugins können eine **eigene Python-Umgebung** verlangen (`env` in plugin.json): Installation per uv mit
  passender Python-Version, unabhängig vom Python von TagStudio. Stems nutzt das (Python 3.12, FFmpeg
  inklusive) – behebt die fehlgeschlagene Installation unter Python 3.14. Neue Variante AMD/Intel (DirectML).
- Eingebautes Plugin **Beatport (inoffiziell)**: Anmeldung mit eigenem Konto (Passwort nie gespeichert, Token
  mit DPAPI verschlüsselt), Abgleich über ID/ISRC/Suche mit Trefferbewertung, Vorschau mit Häkchen; schon gefüllte Felder werden
  ungehakt angezeigt statt still übersprungen, gleiche Werte gezählt, Protokoll je Titel.
- Plugin-System: Vorschläge mit Vorschau (`ctx.propose`), Aktionen auf der Plugin-Karte, Passwort-/Textfelder,
  bedingte Felder (`show_if`), Statustext je Plugin.
- Stems-Installation: `audioread` ergänzt und librosa auf 0.x festgelegt (audio-separator lud sonst nicht).
  Die Installation ergänzt fehlende, nicht deklarierte Module selbst und verwendet eine vorhandene Umgebung
  bei gleicher Variante weiter (kein erneuter PyTorch-Download).
- Protokolle in `~/TagStudio/Logs` (Installation, Plugin-Fehler mit Details); Knopf „Protokolle“.
- Neue Oberfläche jetzt mit **Tag-Fixer**, **Sicherungen** (prüfen, wiederherstellen, löschen, Einstellungen),
  **Sammelkopie** (Mehrfachauswahl in der Paarliste), **Feld hinzufügen** und **Bildern** (ersetzen, exportieren,
  entfernen, hinzufügen).
- **XML-Editor** für Felder mit XML-Inhalt (Baum- und Quelltextansicht, Prüfung mit Fehlerstelle, Formatieren/Kompakt);
  auch in der klassischen Oberfläche. XML in Binärfeldern (GEOB/PRIV) lässt sich ansehen.
- Knopf „Nach Update suchen“: prüft beim Start auf neue Versionen, lädt sie per Klick und startet neu.
- Gemeinsamer Kern `core.py` (Anzeige-Logik, Filter, Laden, Speichern) und `session.py`; beide Oberflächen
  nutzen dieselbe Logik und dieselben Einstellungen.
### Neu (Sicherungen)
- **Änderungs-Viewer** in den Sicherungen: Spalte „Geänderte Felder“ je Datei; Ansicht Feld für Feld
  „Vorher (Sicherung)“ ↔ „Jetzt“ mit Hervorhebung, Blättern durch geänderte Dateien, einzelne Datei wiederherstellen.

### Neu (Installer)
- **Installer** für Windows (`…-Windows-Setup.exe`, ohne Adminrechte) und macOS (`…-macOS-Apple-Chip.dmg`) –
  kein Python nötig. Gebaut von GitHub Actions bei jedem Versions-Tag, mit Selbsttest; erscheinen als GitHub-Release.

### Geändert
- Versionierung nach MAJOR.MINOR.PATCH mit einer einzigen Quelle (`version.py`), Abschnitt „Unveröffentlicht“ im
  CHANGELOG, `packaging/release.py`; Release-Workflow prüft Tag ↔ Version und veröffentlicht Beta-Tags als Vorabversion.
- Update-Knopf: wer noch auf dem Zweig `web-ui` steht, wird automatisch auf `main` umgestellt.
- Die klassische Oberfläche (`tagstudio.py`) nutzt den gemeinsamen Kern – Aussehen und Bedienung unverändert.
- Rückgängig/Wiederholen in `undo.py` ausgelagert.

## [2.9] – 2026-10-08
### Geändert
- Projekt umbenannt in **MarKusSXCH TagStudio** (Hauptdatei `tagstudio.py`, Einstellungen `~/.tagstudio.json`,
  Sicherungen `~/TagStudio/Sicherungen`, Cache `~/TagStudio/cache`).
- Einstellungen und Sicherungen der Vorgängerversion werden automatisch weiterverwendet.
### Neu
- Git-Repository, automatische Tests (`tests/`) und GitHub Actions für Windows, macOS und Linux.

## [2.8] – 2026-10-08
### Neu
- URLs in Tag-Werten sind klickbar und öffnen im Browser; Kontextmenü „Link öffnen“.
- Alle Dialoge, Meldungen und Dateidialoge öffnen sich zentriert über dem aktiven Programmfenster.

## [2.7] – 2026-10-08
### Neu
- Cover-Vorschau über der Tabelle, Unterschiede rot umrandet, große Ansicht per Klick.
- Suche und Filter in der Paarliste (Feld · Bedingung · Wert · Seite), „Felder suchen“ in der Tabelle.

## [2.6] – 2026-10-08
### Neu
- Rückgängig/Wiederholen (Strg/Cmd+Z, Strg+Y) über alle Änderungen.
- Automatische Sicherung der Tags vor jedem Speichern, Dialog „Sicherungen“ zum Wiederherstellen (byte-genau).
- Speichern im Hintergrund mit Fortschrittsbalken.

## [2.5] – 2026-10-08
### Behoben (Praxistest mit 1'493 Dateien)
- Unsichtbare BOM-Zeichen in Mehrfachwerten werden entfernt.
- Eingebettete DJ-Daten (GEOB: Serato, Mixed In Key, PlatinumNotes) werden nach Beschreibung zugeordnet und lesbar angezeigt.
- Beteiligte Personen (TIPL) als „Rolle: Name“.
### Geändert
- Analyse-/DJ-Daten (beaTunes, GEOB, ETCO …) gelten standardmäßig als „unwichtig“.

## [2.4] – 2026-10-08
### Neu
- Splitter zwischen links / Befehlsspalte / rechts und zwischen Name | Wert, automatisch optimale Breiten.
- Befehlsspalte mit ◀/▶ pro Zeile; „Alles“ und „Fehlende“ nach links/rechts übernehmen.

## [2.3] – 2026-10-08
### Neu
- Tag-Fixer für Mehrfachwerte (Trennzeichen oder ID3v2.4-Standard).
- Feine Trennlinien zwischen den Zeilen.
- Leere Standardfelder (ID3v1 / v2.3 / v2.4) einblenden.

## [2.2] – 2026-10-08
### Neu
- Tooltip mit der originalen Frame-ID beim Überfahren eines Feldnamens.

## [2.1] – 2026-10-08
### Neu
- Einlesen großer Ordner mit Zählung, Fortschrittsbalken und Abbrechen.

## [2.0] – 2026-10-08
### Neu
- Oberfläche im Stil von Beyond Compare (Dunkel/Hell), alle ID3-Frames, Zeichen-Diff, Inline-Bearbeitung,
  Kontextmenü, Sammelkopie, Datei-Infos (Dauer, Bitrate).

## [1.0] – 2026-10-04
### Neu
- Erste Version: zwei Ordner oder Dateien vergleichen, Standardfelder links ↔ rechts kopieren, eigene ID3-Bibliothek ohne Zusatzpakete.
