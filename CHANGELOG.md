# Changelog – MarKusSXCH TagStudio

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/) (MAJOR.MINOR.PATCH). Versionen bis 2.8 hießen „MP3 Tag Compare“.
Neue Einträge kommen laufend unter **Unveröffentlicht**; `python packaging/release.py X.Y.Z` macht daraus eine Version.

## [Unveröffentlicht]

### Neu

- **MixID-Tracklisten einfügen (#392):** von MixID kopierte Tracklisten mit Zeitmarken über 99 Minuten („106:00“)
  werden richtig gelesen (Playlists, Ideen, Mix analysieren 1.2) – bisher blieb die Zeit im Künstlernamen stehen.
  „Trackliste einfügen …“ zeigt für MixID und 1001Tracklists eine Anleitung mit Link.

- **SonoVault 1.2 (#380, #381, #383, #259):** eigene Felder `TXXX:SONOVAULT_*` mit Herkunft „SonoVault“ (nur
  erlaubte Werte + Abrufdatum, Option in Online-Metadaten, Release nachschlagen und Audio erkennen); „Release
  nachschlagen (SonoVault) …“ für ganze Alben/EPs; Tarif-Einstellung Free/Bezahlt – mit bezahltem Tarif die neuesten
  Titel je Label und Genre in „Entdecken“ und „Genre-Korrektur an SonoVault melden …“ mit „Meine Genre-Vorschläge …“.
  Audio-Erkennung holt schlanke Treffer über die ID nach. Online-Metadaten 2.3.
- **SonoVault-Integrationsfenster nachgeführt (#379, Plugin 1.1):** neue Endpunkte der Doku (Genre-Vorschläge,
  Radio-Überwachung, Webhooks) kostenpflichtig markiert und nie abgefragt; Notizen zu Erkennung (nur rohes Audio),
  Künstler/Label und Blättern mit Cursor. „Zugriff prüfen“ ruft bei allen Diensten keine Endpunkte mit `test: false`
  mehr auf.

- **Mix analysieren (#261, #387):** neues Plugin „Mix analysieren“ erkennt die Titel der eigenen Bibliothek in einer
  Mix-Datei (DJ-Set, Radiosendung, eigener Mix) – auch mit geändertem Tempo (±10 %, mit und ohne Keylock). Eigener
  Audio-Fingerabdruck, läuft vollständig lokal (Konzept `docs/KONZEPT-MIXSCAN.md`). Einmal „Bibliothek indexieren …“
  (Hintergrund-Auftrag), danach führt TagStudio den Index nach „Vorbereiten“ und beim Start selbst nach (abschaltbar).
  **Ergebnisfenster:** Zeit je Titel (Mitte des Übergangs, änderbar), Tempo, Sicherheit; Vorhören im Mix und im
  Titel; falsche Treffer verwerfen; Lücken als „ID – ID“. Speichern als **Playlist** im Ordner „Mixe“, **CUE-Datei**
  (neben dem Mix) oder **Text**; mit bekannter Tracklist fehlende Titel als **Ideen** merken. Aufruf auch über
  Playlists › Importieren ▾ „Aus Mix erkennen …“ und „Frühere Mix-Analysen …“. Kopierte YouTube-Tracklisten mit Links
  („[04:56](https://…)“) werden überall verstanden; Playlists: „feat. X (Remix)“ verlor beim Vergleich den
  Remix-Namen – behoben. Playlists zeigen die Notiz eines Eintrags hinter dem Titel.
  **Eigene Seite „Mixe“** in der Seitenleiste (#390): links alle Analysen, rechts die Tracklist; „Mix analysieren …“,
  „Bibliothek indexieren …“, „Optionen …“ und Stand des Plugins auf einen Blick.
  Plugin 1.1 (#389): Analyse wahlweise **im Hintergrund** – Fortschritt in der Fussleiste, danach „Ergebnis öffnen“.
  Plugin-Rahmen: Optionstyp `file`, Aktionen ohne Formular (`direct`) und versteckte Aktionen (`hidden`),
  `ctx.queue_job()`, Ereignis `app_started`, Seiten-Aktionen ohne Auswahl im Hintergrund, Hintergrund per Häkchen
  (`"background": "option"`, `job_name`).

- **Ideen – Wunschlisten (#186):** neue Seite „Ideen“ nach „Entdecken“. Titel, die du später kaufen willst, in
  Wunschlisten sammeln – mit ☆ „Idee merken ▸“ in Entdecken, von Hand oder als Liste aus Text; je Eintrag Notiz, Quelle
  mit Link und Vorhören. Status Idee → Kaufen → Gekauft (erkannt über „Einkäufe“) → In Bibliothek (verknüpfte Datei,
  „Mit Bibliothek abgleichen“); verschieben/kopieren, entfernen mit Rückfrage, Rückgängig, Export als Excel/CSV,
  „Als Playlist übernehmen“ und „Als Beatport-Playlist“ (`TagStudio_WISH_<Liste>`, nur auf Klick). Wunschlisten sind
  Playlists im Ordner „Ideen“; bisher in Entdecken gemerkte Titel werden einmal in „Gemerkt (Entdecken)“ kopiert.

- **Download-Verwaltung (#370):** Einstellungen › Expert › Entwicklung › „Downloads je Version …“ – wie oft die
  Installationsdateien je Version heruntergeladen wurden (Windows, macOS, Plugins, Summen, letzte 7/30 Tage); der neue
  Workflow „Download-Statistik“ speichert die Zählerstände täglich im Zweig `stats` für den Verlauf je Tag.
- **Download-Zahlen öffentlich (#371):** Abzeichen „Downloads“ im README und Statistik-Seite (GitHub Pages) mit Summen,
  Verlauf je Tag und Tabelle je Version.
- **Release-Seite: Download oben (#372):** In den Versionshinweisen steht ganz oben ein Kasten mit direkten Links für
  Windows und macOS (Plugins zugeklappt) – kein Scrollen mehr zu den Dateien.
- **Neue Startseite des Repositories (#373):** README mit Symbol, Abzeichen, Download-Knöpfen, Bildschirmfotos (hell und
  dunkel) und Funktions-Kacheln; die Bedienungsanleitung steht jetzt in `docs/HANDBUCH.md` bzw. `docs/HANDBUCH.en.md`
  (Hilfe in TagStudio zeigt sie wie bisher). Bilder erzeugt `tools/screenshots.py` mit Beispieltiteln.
- **Projekt-Webseite (#375):** https://markuskeller8200.github.io/markussxch-tagstudio/ mit Startseite (Download-Knöpfe
  direkt zur neuesten Datei, Bilder, Funktionen), Handbuch Deutsch/Englisch mit Inhaltsverzeichnis und Suche und der
  Download-Statistik; baut sich automatisch neu (`tools/website.py`, Workflow „Download-Statistik“).

## [4.12.0] – 2026-10-26

### Neu

- **Einkäufe: im Browser laden, verlinken, in die Bibliothek (#367, #368, #369)** – nicht ladbare Titel gibt „Fehlende
  herunterladen“ bei Beatport automatisch zum Download frei; Fenster mit Speicherort zum Kopieren und „Downloads bei
  Beatport öffnen“; im Browser geladene Dateien (auch ZIP) erkennt TagStudio selbst und verlinkt sie; „In Bibliothek
  verschieben …“ (nie überschreibend) mit „Im Tagger öffnen“.
- **Beatport: Sitzungs-Token wird zurückgezogen (#366, Plugin 2.11)** – beim Abmelden sowie beim Beenden/Neustarten von
  TagStudio (Revoke laut Beatport-Anleitung, Access- und Refresh-Token).
- **Beatport-API-Tester mit Sitzungs-Anmeldung (#365, Plugin 2.10)** – Zeile „Zugang“: gespeicherter Zugang oder Anmeldung
  wie die Webseite (Anmeldefeld im Tester, Token nur im Speicher); Protokoll nennt den Zugang.
- **Beatport-API-Tester: `/catalog/tracks/purchase-download/` (#364, Plugin 2.9)** – mit order_item_download_id, nach Rückfrage,
  ohne Weiterleitung.
- **Beatport-API-Tester: Download-Endpunkte (#363, Plugin 2.8)** – `/my/downloads/{id}/`, `/my/downloads/{id}/download/`,
  `/catalog/tracks/{id}/download/`; Weiterleitung nicht verfolgt (Ziel unter `location`), Dateien nur als Grösse, …/download/
  nach Rückfrage.
- **Einkäufe: „Erneut zum Download freigeben …“ (#362, Plugin 2.7)** – setzt bei Beatport den Download der markierten bzw.
  fehlenden Einkäufe zurück (reset-download, getestet: HTTP 204, Titel danach in der Download-Warteliste); nach Rückfrage,
  mit Link zu den Beatport-Downloads; auch im Rechtsklick-Menü.
- **Beatport-API-Tester: „Download eines Kaufs zurücksetzen“ (#361, Plugin 2.6)** – inoffizieller Endpunkt
  `/catalog/tracks/reset-download/` als GET und POST, ⚠ mit Rückfrage, nie in „Zugriff prüfen“.
- **Beatport-API-Tester: Werte-Editor und PATCH (#356, #357, Plugin 2.3):** unter dem Body „Mögliche Werte“ mit Feld,
  Typ, Pflicht und Beschreibung (aus der Plugin-Beschreibung oder per OPTIONS „Vom Dienst laden“), „Einfügen“ je Feld,
  „Alle Werte einfügen“, „Beispiel einfügen“, „Formatieren“, laufende JSON-Prüfung; PATCH-Endpunkte testbar (neu:
  Playlist umbenennen), Konto-Endpunkte deutlich gewarnt, Konto löschen/Anmeldung bleiben gesperrt.
- **Einkäufe: Linksklick auf unklaren Einkauf öffnet die Korrektur (#353)**, Rechtsklick wieder das Kontextmenü;
  Korrekturfenster ca. 50 % breiter (#354).
- **„Best Match“ nur noch als Symbol ⇔ (#355)**, neu auch im Tagger (links im Tabellenkopf: Spalte Datei so breit wie
  nötig, ohne waagrechten Bildlauf).
- **Plugins: neue Kategorie „Shop-API“ (#352):** ein Plugin kann mehreren Kategorien angehören (`plugin.json`
  `"categories"`); Beatport (Plugin 2.2) steht unter Online-API und Shop-API, Filter und Karte zeigen beide.
- **Beatport: API-Tester auch schreibend (#350, Plugin 2.1):** POST, PATCH und DELETE im Integrationsfenster testbar –
  nur nach Rückfrage; jeder Aufruf mit Kopfzeilen und Werten im Protokoll, Zugangsdaten geschwärzt.
- **Tabellen: „⇔ Best Match“ (#347):** verteilt die angezeigten Spalten nach Inhalt auf die Breite; fixe Spalten bleiben.
- **Einkäufe: Doppelklick spielt ab (#349);** „Markierte prüfen …“ (#345); Rechtsklick auf einen unklaren Einkauf öffnet
  direkt die Korrektur (#346).

- **Käufe: Playlists in Beatport (#334, #335, Beatport-Plugin 2.0):** „Download Tracks …“ legt Playlists mit den
  Titeln ohne Datei an (je 100), „Playlists je Kaufdatum …“ eine Playlist `TagStudio_BUY_JJJJ_MM_TT` je Kaufdatum;
  „Aufräumen …“ und „Schreibzugriff prüfen“. Nur mit eingeschalteter Plugin-Einstellung (Standard aus), nur auf Klick,
  nur Playlists `TagStudio_…`.

- **Käufe: Zuweisung „streng“ und Korrekturfenster (#338):** Mit „Streng“ muss auch der Mix passen (auch bei gleicher
  ISRC). „Unklare prüfen …“ zeigt je Grund die Kandidaten mit Tags, lässt bei anderem Mix Titel, Untertitel und
  Dateinamen anpassen und erneut prüfen, zeigt bei anderem Künstler die Ähnlichkeit; „Weiter ›“ zum nächsten Kauf.

- **Käufe: ZIP-Downloads automatisch entpacken (#336):** Neue ZIPs im Download-Ordner werden beim Öffnen der Seite
  und beim Abholen entpackt (nur Audio, nie überschreiben, unsichere Pfade abgelehnt); das ZIP kommt nach `_entpackt`.
  Schalter „ZIP entpacken“, Standard ein.

- **Tag-Fixer: Smart Fix mit Rezepten (#339):** Umschalter „Mehrfachwerte | Smart Fix“. Mitgeliefertes Rezept
  „Mehrfachwerte mit Komma“ (`&`/`;` → `, `, Doppelte weg, Künstler, Genre, Stimmung); Ziel-Trenner je Rezept wählbar
  (Standard `, `). Eigene Rezepte anlegen, kopieren, bearbeiten, löschen, exportieren und importieren.

- **Tag-Fixer: Ausnahmen je Feld (#342, #343):** Namen mit Trennzeichen wie „Above & Beyond“ bleiben beim Trennen
  zusammen – je Feld oder Gruppe (Künstler und Mitwirkende, Genre, Stimmung). Editor „Ausnahmen …“ mit Vorschlägen
  aus den geladenen Titeln (Suchtext, Anzahl, Häkchen, gesammelt übernehmen), bestehende Ausnahmen aus- oder markiert
  einblendbar, bearbeiten und entfernen. Teil des Einstellungs-Exports.

### Verbessert

- **Einkäufe: Playlists je Kaufdatum ungeteilt (#360, Plugin 2.5)** – eine Playlist pro Datum mit allen Titeln; die
  100er-Teilung gilt nur noch für „Download Tracks“.
- **Einstellungen ein- und ausklappbar (#351):** alle Kacheln standardmässig eingeklappt, „Alle ausklappen/einklappen“,
  Sprungmarken öffnen die Kachel, Zustand gemerkt.

- **„Käufe“ heisst jetzt „Einkäufe“ (#348)** – überall in der Oberfläche; Daten unverändert.

- **Entdecken als eigene Seite (#333):** zuoberst in der Seitenleiste mit der Zahl neuer Vorschläge; „Vorbereiten“
  ohne Umschalter `Workflow | Entdecken`. Daten und Einstellungen von Entdecken bleiben unverändert.

- **Tag-Fixer: Änderungen einzeln abwählen (#341):** Die Vorschau hat eine Häkchen-Spalte (Kopf = alle/keine,
  Umschalt-Klick für Bereiche); „Anwenden“ führt nur die angehakten Änderungen aus – eine Rückgängig-Stufe.

- **Spaltenbreite per Ziehen (#337, #340):** In den Tabellen von Käufe und Tag-Fixer lässt sich die Breite jeder
  Spalte am Rand des Kopfs ziehen – Doppelklick passt sie dem Inhalt an, ←/→ auf dem Griff verschiebt in Schritten.
  Die Breiten bleiben gespeichert; Rechtsklick auf die Kopfzeile › „Spaltenbreiten zurücksetzen“.

- **Tag-Fixer: Trennzeichen als Code (#344):** Die Trennzeichen stehen als Code neben ihrer Beschreibung –
  Leerzeichen sichtbar als `␣`, der Null-Trenner als `\0`; der gewählte Ausgabe-Trenner wird ebenso angezeigt.

- **Protokolle beim Beenden leeren (#332, Entwicklung):** Einstellungen › Expert – Schalter, Standard aus. Beim Beenden,
  Neustart und Update werden `app.log` und `app.log.1` geleert (nicht gelöscht), auf Wunsch auch die Plugin-Protokolle;
  die erste Zeile danach meldet „Protokoll beim letzten Beenden geleert (Entwicklermodus)“.

### Behoben

- **Einkäufe: Beatport-Playlists wurden fälschlich als „nicht erlaubt“ abgelehnt (#359, Plugin 2.4)** – die Vorprüfung per
  OPTIONS liefert bei Beatport keine verwertbare Antwort; jetzt entscheidet die echte Anfrage, Status und Antwort im Protokoll.
- **Einstellungen: Kacheln springen beim Auf-/Zuklappen nicht mehr in andere Spalten (#358)** – feste Spalte je
  Kachel, nur darunterliegende rücken nach.

## [4.11.0] – 2026-10-25

### Neu

- **Plugins OneDrive, Google Drive und Dropbox (#318–#320, je 1.0):** Gegenstellen für den Abgleich über die Dienste –
  eigene App je Dienst (Client-ID), Anmeldung mit PKCE, Token verschlüsselt; OneDrive privat und geschäftlich (Upload-
  Sitzung für grosse Dateien), Google Drive nur mit Zugriff auf eigene Dateien (`drive.file`), Dropbox mit App-Ordner.
  Grenzen werden gemeldet, nicht wiederholt; Löschen landet im Papierkorb des Dienstes.
- **Abgleich über die Dienste – Rahmen (#317, Cloud Weg 2):** Einstellungen › Cloud › „Abgleich über
  die Dienste“ – Rollen Playlists und Export sowie Programmdaten-Teile (Playlists-Speicher, Käufe, Entdecken,
  Einstellungen ohne Zugangsdaten) mit einem Ordner im Dienst abgleichen, in beiden Richtungen. Ändert sich eine Datei
  hier und dort, zeigt TagStudio beide Fassungen und fragt; gelöschte Dateien werden nur nach Rückfrage gelöscht.
- **SonoVault (#253–#255, Plugin 1.0):** Dienst-Plugin mit eigenem Schlüssel; zählt die Anfragen je Monat (Free:
  1000), zeigt den Rest auf der Kachel, warnt ab 90 % und fragt beim erreichten Kontingent nichts mehr ab; HTTP 429 wird
  nie wiederholt. Neue Quelle in „Online-Metadaten“ (2.2) nach MusicBrainz/Discogs – nur die laut Nutzungsbedingungen
  erlaubten Felder, BPM und Tonart nur als Vergleich in der Notiz. „Plattform-IDs anzeigen (SonoVault) …“ zeigt IDs
  bei Spotify, Beatport & Co. als Tabelle (nur Anzeige). Zwischenspeicher höchstens 30 Tage, nie exportiert.
- **SonoVault: Audio erkennen (#257, optional):** Titel ohne brauchbare Tags aus einem kurzen Ausschnitt (30–60 s,
  mono, ohne Tags) erkennen – mit Kostenvorschau (10 + 1 Kredit je MB, gekaufte Kredite nötig) und Datenschutz-Hinweis;
  Treffer als Vorschau.
- **SonoVault in Entdecken (#258):** neue Veröffentlichungen gefolgter Künstler und Labels als weitere Quelle (aus,
  bis gewählt) – nur bei „Suchen“, nie bei der täglichen Suche; Einträge ohne Link, nach 30 Tagen entfernt, nie
  exportiert.
- **SonoVault: Bibliothek abgleichen (#256):** markierte Titel in Blöcken zu 100 mit SonoVault vergleichen – zuerst
  Kostenvorschau, nie mehr Kredite als übrig, Abweichungen (ISRC, Label, Genre, Album, Jahr, Tonart) als Tabelle; nur
  Anzeige, übernommen wird pro Titel.
- **Wellenform im MP3 (#222, Entscheid W1):** Einstellungen › Sicherungen und Speichern › „Wellenform im MP3“
  (Standard aus) – beim Speichern kommt die eigene Wellenform als GEOB „TagStudio Overview“ (`wavetag.py`, rund
  1.6 KB) in die Datei; der Player liest sie, wenn der Cache leer ist, und legt sie wieder in den Cache. Serato-Felder
  werden nie verändert.

### Verbessert

- **Tagger-Spalten (#331):** passen bei „An Fenster anpassen“ nicht alle Spalten ins Fenster (z. B. alle Merkmale),
  wechselt die Liste selbst auf waagrechtes Blättern (und zurück, sobald es wieder passt); beim waagrechten Blättern
  bleibt die erste Spalte samt Kopf und Filterfeld links stehen.
- **Fenster verschieben und vergrössern (#330):** alle Dialoge lassen sich am Titel verschieben und an der Ecke unten
  rechts in der Grösse ändern (Inhalt wächst mit); Doppelklick auf den Titel setzt zurück, jeder neue Dialog öffnet in
  der Mitte. Rückfragen liegen immer vor dem offenen Fenster.
- **Protokolle leeren und Teile kopieren (#329):** Protokoll-Ansicht (Einstellungen › Expert) und Live-Fenster mit
  „Leeren …“ (nach Rückfrage, die Datei wird geleert, nicht gelöscht); „Kopieren“ nimmt nur die Markierung, ohne
  Markierung alles. Das Live-Fenster behält eine Markierung, auch wenn neue Zeilen kommen.
- **Protokolle live (#327):** Einstellungen › Expert › Protokolle „Live anzeigen …“ öffnet dasselbe Live-Fenster wie
  bei den Plugins – alle Protokolle im Log-Ordner zur Auswahl (Standard `app.log`), läuft mit, Filtern, Anhalten,
  Kopieren, Log-Ordner öffnen.
- **Einstellungen › Cloud (#324):** eigene Karte nach „Speicherort und Ordner“ mit den Sync-Ordnern der Desktop-
  Clients, „Nur-online-Dateien herunterladen“ und dem Abgleich über die Dienste; dessen Tabelle hat jetzt eine
  Kopfzeile (Bereich · Dienst · Richtung · Ordner im Dienst), ist nach Ordner-Rollen und Programmdaten gegliedert und
  füllt die ganze Kartenbreite wie die Ordner-Tabelle.
- **Plugin-Kategorie „Cloud-API“ (#323):** OneDrive, Google Drive und Dropbox (je 1.1) stehen auf der Seite Plugins
  und im Katalog unter einer eigenen Kategorie mit Wolken-Symbol statt unter „Online-API“.
- **Werkzeugleiste im Vergleich (#107):** gruppiert wie in der klassischen Oberfläche – Anzeige, Kopieren, Bearbeiten,
  Verlauf (neu: ↶/↷ direkt im Vergleich) –, je Gruppe farbige Symbole, Trenner und Tooltips; „Aa“ schaltet auf
  „nur Symbole“ um (wird gemerkt). Mit Symbol und Text zwei Zeilen – oben die Anzeige, darunter Kopieren, Bearbeiten
  und Verlauf; nur Symbole: alles in einer Zeile. **Im Tagger** dieselbe Leiste: Anzeige (Filter, Spalten, Cover, Merkmale,
  Stems), Zurücksetzen/Melden, Verlauf mit ↶/↷ direkt im Tagger und eigenem „Aa“.
- **Dateidialoge und Fenstertitel übersetzt (#304):** Dateitypen in den Öffnen- und Ordner-Dialogen („MP3-Dateien“,
  „Alle Dateien“ …), die Titel der Dialoge im Browser-Modus und die Fenstertitel von Player und Protokollen folgen
  der gewählten Sprache (Englisch, Zürichdeutsch) – auch direkt nach einem Sprachwechsel.

### Behoben

- **Vergleich blitzte beim Start kurz auf (#328):** die Vergleichsseite war beim Laden als einzige nicht ausgeblendet –
  jetzt erscheint direkt die zuletzt benutzte Seite.
- **Tagger lädt schneller, besonders von Netz- und USB-Laufwerken (#326):** Grösse und Änderungszeit jeder Datei kommen
  jetzt aus dem Durchsuchen des Ordners – Titel aus dem Zwischenspeicher werden nicht mehr einzeln abgefragt (unter
  Windows entfällt so ein Zugriff je Datei; gilt auch für Vergleich und Snapshots-Startprüfung). Die
  Snapshots-Startprüfung beginnt erst, wenn der Tagger geladen ist, statt gleichzeitig dieselben Dateien abzufragen.
  Das App-Protokoll zeigt den Startablauf mit Zeiten („Startablauf: … s nach dem Start“).
  **Letzte Liste sofort:** beim Start erscheint die zuletzt angezeigte Tagger-Liste direkt nach dem Seitenaufbau (nur
  ansehen, Hinweis „wird im Hintergrund geprüft …“); nach dem Einlesen ersetzt die echte Liste sie – Markierung und
  Sortierung bleiben, Änderungen meldet die Statuszeile („x neu, y entfernt, z geändert“). Der Cover-Fingerabdruck der
  Liste rechnet nicht mehr über das ganze Bild. **Cover sofort:** Vorschaubilder liegen zusätzlich unter dem
  Listen-Fingerabdruck im Cache und erscheinen schon in der Sofort-Liste; fehlt ein kleines Bild, verkleinert die
  Oberfläche das Cover einmal selbst (statt jedes Mal das ganze Cover zu laden). Beim schnellen Blättern werden Cover erst nach dem
  Anhalten gezeichnet (kein Ruckeln); beim Darüberfahren erscheint eine scharfe grosse Vorschau (440 px). Die Details des
  markierten Titels (meist der im Player) kommen in der Sofort-Liste gleich aus der Datei. Startdialoge (Snapshots, Ordner, Neuigkeiten) kommen nacheinander.
- **Neustart öffnete immer den Vergleich (#325):** nach „Neu starten“ oder einem Update startete die App im Vergleich
  und las ihn neu ein, ohne den Tagger zu laden – und blieb bei jedem weiteren Neustart dort. Jetzt öffnet sie die
  zuletzt benutzte Seite, liest den Tagger im Hintergrund ein und setzt den Player an derselben Stelle fort (gemäss
  Einstellung „Nach dem Neustart“); die Vergleichsordner kommen nur mit, wenn zuletzt der Vergleich offen war.

## [4.10.0] – 2026-10-25

### Neu

- **Ordner-Rollen – Grundlage (#310, Konzept `docs/KONZEPT-ORDNER.md`):** Einstellungen › Speicherort und Ordner zeigt
  jeden Ordner genau einmal als Rolle (Eingang, Bibliotheken, Archiv, Playlists, **Export** `04_Export`, Downloads,
  Arbeit, Sicherung, Snapshots) – je Rolle Modus „Basis“ (Basisordner + Unterordner, Name änderbar), „Eigener
  Ordner“ oder (Sicherung/Snapshots) „Programmdaten“. Mehrere Bibliotheken mit Name, aktiv/inaktiv und
  Hauptbibliothek; Hinweise „fehlt – anlegen?“, „nicht erreichbar“, Überschneidungen. Die bisherigen Einstellungen
  werden einmalig übernommen; verschiedene Bibliotheks-Einträge erscheinen in der Übersicht „Diese Ordner haben wir
  gefunden“. Ändern stellt nur die Einstellung um (Dateien bleiben); Workflows, die auf den bisherigen Ordner zeigten,
  folgen. Neues Modul `folders.py`, Seite `web/folders.js`.
- **Export-Ordner (#312):** Jeder Speichern-Dialog für Exporte (Tagger-Liste, Playlists, Einkaufsliste, DJ-Set,
  Merkliste, Snapshot-Journal, Einstellungen, Texte, Cover) öffnet im Export-Ordner (`04_Export` bzw. eigener
  Ordner); fehlt er, wird er angelegt. Neu: „Workflow exportieren …“ kann den Workflow auch als Datei speichern.
- **Mehrere Bibliotheken (#311):** Käufe-Abgleich, Playlist-Abgleich, Entdecken und Hilfe › Scan lesen die
  **aktiven** Bibliotheken aus Einstellungen › Ordner (jeder Ordner nur einmal, nicht erreichbare übersprungen und
  gemeldet) statt drei verschiedener Einstellungen – der Käufe-Abgleich liest keine Bibliothek mehr doppelt.
  „Verglichen mit“ zeigt die Namen. Tagger: Auswahl „Bibliothek ▾“ mit „Alle aktiven“. Snapshots je Bibliothek
  ein/aus. Vorbereiten übernimmt ohne eigenen Bibliotheksordner in die Hauptbibliothek.
- **Unterordner je Quelle und Ordner-Klappmenü (#314):** Einschalten eines Store-Plugins (Plugin-Feld `source`,
  Beatport-Plugin 1.9) legt `90_Download\<Quelle>` und `00_New\<Quelle>` an und trägt die Quelle im Workflow ein;
  Käufe-Downloads gehen in den Unterordner des Stores; „Struktur anlegen“ legt `_Manuell` an. Workflow-Felder
  Eingang/Arbeit/Bibliothek folgen leer den Rollen. Jede Ordnerauswahl öffnet ein Klappmenü (Bibliotheken, Rollen,
  zuletzt benutzt, Anderer/Neuer Ordner …, „als Rolle speichern“).
- **Cloud-Sync-Ordner (#315, Weg 1):** Neues Modul `cloud.py` erkennt die Sync-Ordner von OneDrive (privat und
  geschäftlich), Google Drive und Dropbox (Windows und macOS); Einstellungen › Ordner zeigt „☁ OneDrive“, Pfade
  werden zusätzlich relativ zum Sync-Ordner gespeichert. Nur-online-Dateien werden beim Einlesen übersprungen und
  gemeldet (Schalter zum Herunterladen), Konfliktkopien angezeigt; Hinweis bei Snapshots/Arbeit/Sicherung in der
  Cloud.
- **Ordner ändern mit Inhalt (#313):** „Ändern …“ (Rolle, Bibliothek, Basisordner) fragt Verschieben / Kopieren /
  Nicht übernehmen (Bibliothek: Standard „Nicht übernehmen“ mit Hinweis zu fremden DJ-Programmen), mit Vorschau
  (Dateien, Grösse, freier Platz, Konflikte). Nie überschreiben, über Laufwerke SHA-256-Prüfung vor dem Entfernen,
  abbrechbar ohne halbe Dateien, Journal `Ordnerwechsel.csv`; Verweise in Playlists, Käufen, Snapshots,
  Archiv-Vermerk, Vorbereiten, Verlauf und Warteschlange werden nachgeführt. Neues Modul `foldermove.py`.

## [4.9.1] – 2026-10-25

### Verbessert

- **Seitenleiste (#316):** „Käufe“ lässt sich ein-/ausblenden und steht standardmässig ganz oben; eigene Reihenfolge
  der Menüpunkte mit ↑/↓ in Einstellungen › Darstellung › Seitenleiste, „Standard-Reihenfolge“ setzt zurück.

### Sicherheit

- **Zugangsdaten unter macOS im Schlüsselbund (#287):** Schlüssel und Tokens der Dienst-Plugins (AcoustID, Discogs,
  Last.fm, Spotify, SoundCloud …) und Beatport-Token/App-Daten liegen unter macOS jetzt im Schlüsselbund statt als
  Datei; bestehende Dateien werden beim ersten Lesen übernommen. Windows wie bisher DPAPI. Neues Kernmodul
  `secretstore.py`, Dateien werden atomar und von Anfang an nur für den Benutzer lesbar geschrieben
  (Beatport-Plugin 1.8).

### Behoben

- **Oberfläche und lokaler Server (#305):** Tagger und Vergleich zeigen beim schnellen Blättern keine veralteten
  Werte mehr; Hinweise erscheinen nacheinander statt sich zu überschreiben; die Auftrags-Anzeige bleibt nach einem
  Abruffehler nicht stehen; der lokale Server nimmt nur Aufrufe an die eigene Adresse an (Schutz vor
  DNS-Rebinding), vergleicht den Schlüssel in konstanter Zeit und lehnt übergrosse Anfragen ab.
- **Kern (#306):** Archiv vergibt eindeutige Namen und vermerkt jeden Titel sofort; Umbenennen nur in
  Gross-/Kleinschreibung hinterlässt keine Hilfsdatei; Warteschlange atomar; kein Doppelstart von Vorgängen;
  keine `.part`-Reste bei abgebrochenen Updates, Plugin-Update legt bei Fehler die alte Version zurück;
  Protokoll schwärzt auch Authorization/Bearer/Cookie; Melden kürzt lange Texte sauber; Vorbereiten › Abholen
  erkennt gleichnamige Dateien gleicher Grösse auch am Inhalt.
- **Plugins (#302):** Stems (1.3) und Tonart (1.4) nutzen je Lauf einen eigenen Arbeitsordner (Hintergrund- und
  Vordergrund-Auftrag löschten sich gegenseitig die Daten); Lautheit (1.1) bricht FFmpeg beim Abbrechen sofort ab
  und überschreibt keine vorhandenen Kopien; Spotify/SoundCloud (1.1) laden bei leeren oder wiederholten Seiten
  nicht endlos und schicken den Token nur an den eigenen API-Host; Anmeldung mit Rückleitung über `localhost`
  klappt auch, wenn der Browser IPv6 nutzt.
- **Entdecken (#303):** Änderungen (merken, ausblenden, folgen) gehen nicht mehr verloren, wenn gleichzeitig die
  Hintergrundsuche speichert.
- **Schutz vor Datenverlust (#301):** Einstellungen werden nie mehr geleert, wenn die Datei beim Speichern gesperrt
  oder defekt ist (defekte Datei wird als Kopie gesichert); Aufräumen im Snapshot-Speicher lässt Daten laufender
  Snapshots/Sicherungen stehen; Wiederherstellen überschreibt keine Datei ohne Sicherheitskopie; MP3s mit
  beschädigter ID3-Grösse werden nicht gespeichert (sonst wären Audiodaten überschrieben worden).
- **Cover-Bildtyp (#300):** Ein präparierter Bildtyp im Cover einer MP3 konnte Script in die Oberfläche bringen.
  Bildtypen werden jetzt geprüft (nur `image/…`, sonst aus den Daten erkannt) und Bildadressen überall maskiert.
- **Vorbereiten (#298):** „Übernehmen“ ersetzt nie mehr eine vorhandene Datei in der Bibliothek (auch nicht mit
  „trotzdem“); Stufen-Ordner „.“/„..“ werden verworfen, „Stufen-Kopien aufräumen“ löscht nur in Stufen-Ordnern;
  externe Batch-Programme (.bat/.cmd) bekommen keine Dateinamen mit Sonderzeichen wie & oder %.
- **Beatport (#299):** Token wird nie an eine Weiterleitung mitgeschickt; die Anmeldung bleibt bei Serverfehlern
  während der Token-Erneuerung erhalten; ZIP-Inhalte und die Liste geladener Käufe werden vollständig bzw. atomar
  geschrieben.

## [4.9.0] – 2026-10-25

### Neu

- **Smartlists (#272):** Playlists, die sich über Regeln selbst füllen („+ Smartlist“, ⚡). Datenbasis Bibliothek,
  im Tagger geladene Titel oder eine andere Playlist; Regeln über Text, Genre, Label, Kommentar, Jahr, BPM, Tonart
  (auch „passt zu“), Bewertung, Like, Stimmung, Energie, Aufgenommen/Bearbeitet und Herkunft, „alle“ oder „mindestens
  eine“ erfüllt; Sortierung (auch Zufall) und Höchstzahl. Neu gebildet beim Öffnen (älter als 15 Minuten) und mit
  „↻ Aktualisieren“, M3U8 im Playlist-Ordner wird mitgeschrieben; „Einfrieren“ macht eine normale Playlist daraus.
- **Playlists an Lexicon senden (#273):** Playlists › Mehr ▾ › „An Lexicon senden …“ legt die Playlist in Lexicon an;
  erneutes Senden führt dieselbe Playlist nach (fehlende Titel an ihrer Stelle eingefügt, nichts entfernt – Titel, die
  nur in Lexicon stehen, werden gemeldet). Einträge ohne Datei und Titel, die Lexicon nicht kennt, werden ausgelassen
  und gemeldet. Nur mit eingeschaltetem Zurückschreiben im Lexicon-Plugin (2.2), Journal im Plugin. Neu im
  Plugin-Rahmen: `playlist_push(ctx, playlist, options)` und `push_ready(ctx)`.
- **Beatport: eigener API-Zugang (#286):** Anmelden mit der eigenen offiziellen Beatport-App (Client-ID und Secret,
  verschlüsselt gespeichert), Erneuern des Tokens über die App, Abmelden zieht das Token bei Beatport zurück
  (Beatport-Plugin 1.3).
- **Entdecken ← My Beatport (#288):** Beatport-Plugin › „Gefolgte Künstler und Labels in „Entdecken“ übernehmen …“
  ergänzt die auf Beatport gefolgten Künstler und Labels (nur lesen).
- **Beatport offiziell (#289):** Plugin heisst jetzt „Beatport“; Standard-Anmeldung ist der eigene API-Zugang, die
  bisherige Anmeldung bleibt als „inoffizieller Ausweichweg“. Das Integrationsfenster listet alle Endpunkte der
  offiziellen Beschreibung (catalog, my, curation) mit Status; genutzt werden nur dokumentierte Endpunkte, ausser
  beim Download gekaufter Dateien. Konto über `GET /my/account/`.
- **Zugriff prüfen (#297):** Integrationsfenster › „Zugriff prüfen“ ruft mit der aktuellen Anmeldung jeden lesenden
  Endpunkt einmal auf und zeigt, worauf du Zugriff hast (Zugriff, erreichbar, kein Zugriff …), mit Zugang und Scope;
  Ergebnis auch im Protokoll (Beatport-Plugin 1.7).
- **Beatport: Berechtigungen anzeigen (#296):** „Testen“ und „Anmelden“ zeigen den Scope des Tokens, das Protokoll
  nennt ihn bei jedem Download (Beatport-Plugin 1.6).
- **Beatport: Anmelden für den Download (#295):** lehnt Beatport den gespeicherten Zugang beim Herunterladen ab,
  fragt die Seite „Käufe“ nach einer Anmeldung nur für diese Sitzung (wie die Webseite, nichts gespeichert) und lädt
  gleich erneut; Anzeige der Sitzung mit „Abmelden“ (Beatport-Plugin 1.5).
- **Plugin-Protokolle (#293):** bei jedem Plugin unter „Mehr …“ „Log-Ordner öffnen“ und „Protokoll live anzeigen …“
  – eigenes Fenster, das das Protokoll jede Sekunde nachführt (Datei wählen, filtern, anhalten, kopieren); Zeilen
  laufender Vorgänge erscheinen sofort.
- **Beatport-Download wie die Webseite (#292):** „Fehlende herunterladen“ versucht zuerst den Weg der
  Beatport-Webseite (`purchase-download` mit der Kauf-ID aus `/my/downloads/`); Beatport-Plugin 1.4.
- **Entdecken verbessert (#291):** Bereich „Gefolgt“ mit allen gefolgten Künstlern, Labels und Genres (von Beatport
  übernommene mit „BP“) – direkt hinzufügen, mit × entfernen, „Von Beatport übernehmen“, „Ähnliche Künstler …“
  (Deezer); Rechtsklick auf einen Vorschlag „Künstler folgen“ / „Label folgen“; „Leeren …“ (gemerkte und gekaufte
  bleiben, wahlweise gleich neu suchen); Vorschläge, die unter „Käufe“ stehen, sind als „gekauft“ markiert; neue Titel
  aus „My Beatport“ als Vorschläge.
- **Käufe: Abgleich (#290):** dieselbe Datei unter zwei Pfaden zählt nur einmal (weniger „unklar“, auch bei
  Playlists), Spalte „Hinweis“ mit dem Grund, Zeile „Verglichen mit …“, „Zuordnen …“ von Hand.
- **Käufe (#285):** neue Seite „Käufe“ – gekaufte Titel aller Stores (vorerst Beatport) in einer Tabelle mit Titel,
  Interpret, Mix, Länge, Tonart, BPM, Katalognummer, Store, Kaufdatum und Link; „Aktualisieren“ holt neue Käufe und
  gleicht mit der Bibliothek ab (in Bibliothek, im Eingang, unklar, fehlt), „Fehlende herunterladen“ lädt in den
  Eingangsordner (`00_New`). Neu im Plugin-Rahmen: `store_purchases`, `store_download` (Beatport-Plugin 1.2).
- **Beatport-Playlists holen (#284):** Playlists › Importieren ▾ › „Aus Beatport …“ übernimmt die eigenen
  Beatport-Playlists als Playlists mit Einträgen ohne Datei (Link zu Beatport), gleicht sichere Treffer mit der
  Bibliothek ab und behält Verknüpfungen beim erneuten Holen. Nur lesen, über die Anmeldung im Beatport-Plugin (1.1).

## [4.8.0] – 2026-10-25

### Neu

- **Playlists (#267–#269):** neue Seite „Playlists“ zum Sammeln, Ordnen und Verwalten – Ordner beliebig tief,
  „Zuletzt benutzt“, Suche, Umbenennen, Duplizieren, Verschieben (auch per Ziehen), Farbe und Notiz,
  Zusammenführen, Rückgängig/Wiederholen. Jede Playlist liegt zusätzlich als **M3U8 im Playlist-Ordner**
  (`03_Playlists` im Basisordner, neu in der Ordnerstruktur und unter Einstellungen › Speicherort und Ordner) – zum
  Einlesen in Engine DJ, VirtualDJ und andere Programme; Änderungen anderer Programme dort werden gemeldet und nie
  ungefragt überschrieben. **Archivieren statt Löschen** wie bei den Titeln (`02_Archiv/_Playlists`, Vermerk in
  `_aussortiert.csv`, Zurückholen). Doppelte Titel sind erlaubt (mit Rückfrage).
- **Tagger ↔ Playlists (#268):** Rechtsklick bzw. Werkzeuge › „Playlist ▾“ → „Zur Playlist hinzufügen …“,
  **Strg+Shift+P** = zur zuletzt benutzten Playlist, „Playlist im Tagger öffnen …“ und Filter „Nur Titel aus einer
  Playlist zeigen“.
- **Playlists abspielen, Warteschlange, Vorbereiten (#270):** „▶ Abspielen“ – der Player folgt der Playlist auch auf
  anderen Seiten, Titel müssen nicht im Tagger geladen sein; Warteschlange „Als Playlist speichern …“ und Playlist
  „In die Warteschlange“; Player-Menü „Laufenden Titel zur Playlist hinzufügen …“; Vorbereiten › Übernahme „In
  Playlist aufnehmen“ (Platzhalter `{Jahr}`, `{Monat}`, `{Tag}`, `{Workflow}`).
- **Playlists importieren, exportieren, abgleichen (#271):** Import aus M3U/M3U8, Rekordbox-XML (mit Ordnerbaum),
  CSV (auch ohne Dateien: Künstler, Titel, Mix, ISRC) und Lexicon; Export als M3U8, Rekordbox-XML (auch ganze Ordner)
  und CSV; „Mit Bibliothek abgleichen …“ (Radio Edit ≠ Extended Mix), „Fehlende suchen …“ für verschobene Dateien,
  Einkaufsliste als CSV; neu übernommene Titel werden automatisch verknüpft.
- **Playlists aus Serato, Engine DJ und VirtualDJ (#278):** „Importieren ▾ › Aus Serato …“ (Crates mit
  Unter-Crates), „Aus Engine DJ …“ (Playlists mit Ordnern und Reihenfolge, Engine DJ 2 und neuer) und „Aus
  VirtualDJ …“ (virtuelle Ordner und Playlists); Lexicon wie bisher. Die Bibliotheken werden gesucht (auch auf
  externen Laufwerken) und **nur gelesen**; erneuter Import aktualisiert die Playlists im Ordner des Programms.
- **Tracklisten aus Online-Quellen (#279):** „Importieren ▾ › Trackliste einfügen …“ übernimmt kopierte Tracklisten
  von 1001Tracklists, MixID, Beatport u. a. als Einträge ohne Datei (Nummern, Zeitmarken, Labels und „ID - ID“
  fallen weg) – danach „Mit Bibliothek abgleichen …“; Spotify-Exporte (z. B. Exportify-CSV) über „Datei …“.
  TagStudio ruft dafür keine Webseiten ab.
- **Plugins Spotify und SoundCloud (#280, nur lesen):** mit deiner eigenen App beim Dienst (Spotify: Client-ID,
  Premium; SoundCloud: Client-ID und Secret, Artist Pro) und Anmeldung im Browser (OAuth mit PKCE, Token verschlüsselt,
  automatisch erneuert). Playlists, Lieblingssongs bzw. Likes und eigene Titel kommen über Playlists › Importieren ▾
  als Einträge ohne Datei mit Link („↗“), danach Abgleich und Einkaufsliste (mit Link); neue Quellen „Spotify“ und
  „SoundCloud“ in den Online-Metadaten (ISRC, Link als `TXXX:SPOTIFY_URL` bzw. `TXXX:SOUNDCLOUD_URL`); gefolgte
  Künstler lassen sich in „Entdecken“ übernehmen. Alle Lese-Endpunkte stehen mit Umsetzungsstand im API-Tester.
- **Abgleich mit der Bibliothek toleranter (#281):** Mix-Schreibweisen („Song - Extended Mix“, „(Extended)“,
  „Remastered“, Mix in TIT3), Ähnlichkeitssuche als Rückfall, je Eintrag der Grund und ein Vorschlag ★, Option „Anderer
  Mix gilt als gefunden“ (Extended bevorzugt) und Suche in einem gewählten Ordner.
- **Abgleich für viele Playlists, Verknüpfungen bleiben (#282):** Bibliotheken im Abgleich einzeln an- und abwählen,
  Vorschläge ★ vorgewählt, „Ordner mit Bibliothek abgleichen …“ bzw. „Alle Playlists …“; erneutes Holen einer Playlist
  behält die Verknüpfungen und verknüpft sichere Treffer gleich.
- **„Online suchen ›“ im Rechtsklick-Menü (#283):** im Tagger, in den Playlists und im DJ-Set – öffnet die Suche bei
  Beatport, Spotify, SoundCloud, Apple Music oder YouTube mit Künstler, Titel und Mix.
- **Zurück zur vorherigen Ansicht (#274):** Nach einem Sprung aus dem Inhalt (z. B. Playlist › „Im Tagger öffnen“)
  führt „← Zurück“ oben in der Seitenleiste an dieselbe Stelle zurück – mit Auswahl, Filter und Bildlauf; „→“
  vorwärts, Rechtsklick zeigt die letzten Stationen. Auch Alt+← / Alt+→ (ausser im Vergleich) und die Maustasten
  Zurück/Vorwärts. Klicks in der Seitenleiste zählen nicht.
- **Tagger: „↺ Filter“ (#275)** hebt Suche, Spalten-, Feld- und Playlist-Filter auf einmal auf; sind nur die Titel
  einer Playlist geladen, zeigt ein Hinweis das an und „Ganzen Ordner laden“ holt den vorher geladenen Ordner zurück.
- **Tagger: Stems mit einem Umschalt-Knopf (#276)** statt zwei Knöpfen zum Auf- und Zuklappen; „Stems“ und „Filter“
  sind wie „Cover“ blau hervorgehoben, solange sie eingeschaltet sind (#277).
- **DJ-Set ↔ Playlists (#269):** Das Set wird als Playlist gespeichert (Ordner „DJ-Sets“, mit Sperren und Optionen),
  jede Playlist lässt sich im DJ-Set öffnen; Playlists aus Lexicon landen im Ordner „Lexicon“. Die bisherigen
  gespeicherten Listen werden beim ersten Start einmalig übernommen.
- **Update auf Knopfdruck (#234, Windows; macOS #251):** Die installierte App lädt die neue Version direkt von GitHub, prüft die
  Prüfsumme, schliesst sich, installiert still und startet neu – Einstellungen und Daten bleiben erhalten. Nur
  veröffentlichte Versionen im gewählten Kanal. Unter macOS wird das DMG für den eigenen Prozessor geladen und die
  App ersetzt; die bisherige Version bleibt als Sicherung in `~/TagStudio/Updates/vorherige-Version`.
- **Plugins einzeln nachladen und aktualisieren (#235):** „Verfügbare Plugins …“ auf der Plugin-Seite listet alle
  Plugins aus dem neuesten Release im gewählten Kanal – Updates, neue und installierte, mit Kategoriefilter (#236); „Aktualisieren“ bzw. „Installieren“ lädt nur
  dieses Plugin (mit Prüfsumme) – ohne ganzes App-Update. „Mehr … → Zurück auf eingebaute Version“ macht es rückgängig.
  Jedes Release enthält dafür je Plugin ein ZIP und den Katalog `plugins.json`; `plugin.json` kennt neu `min_app`.
- **Lexicon ausgebaut (#237–#239):** „Lexicon übernehmen“ sucht gezielt (schneller bei grossen Bibliotheken) und
  übernimmt auf Wunsch auch Bewertung, Popularität, Farbe und Tags aller Kategorien; Beatgrid und Cue-Punkte werden
  mit der Datei verglichen. Neu „Aus Lexicon öffnen …“: markierte Titel oder eine Playlist in Tagger oder DJ-Set laden;
  Vorbereiten erkennt den Schritt „Lexicon“. Zurückschreiben (standardmässig aus, nur auf diesem Rechner): Pfade
  nachführen, neue Bibliothekstitel aufnehmen (Playlist, Analyse), Tags mit Vorschau übertragen, DJ-Set als Playlist,
  „Letzte Änderung rückgängig“. TagStudio löscht nie etwas in Lexicon. Werte aus Lexicon ohne offizielles
  MP3-Feld kommen in eigene Felder `TXXX:LEXICON_…` mit Herkunft „Lexicon“ (Energie, Tanzbarkeit, Fröhlichkeit,
  Popularität, Farbe, Tags, Stimmung bei ID3v2.3), so wie Lexicon sie liefert; die TagStudio-Felder bleiben
  unverändert (#240).
- **DJ-Set: Playlists aus Lexicon (#242):** „Aus Lexicon …“ holt alle Playlists (und die Warteschlange), zeigt sie mit
  Häkchen und Filter; gewählte werden als Listen „Lexicon: …“ gespeichert, die erste geladen. Dazu „Lexicon-Werte in
  TagStudio-Felder …“ (#241): Werte aus den Lexicon-Feldern auf Wunsch in ENERGY usw. und die Stimmung übernehmen.
- **Tonart mit OpenKeyScan (#217, #244, #245):** zwei neue Plugins mit gleicher Vorschau. „Tonart (OpenKeyScan)“
  erkennt die Tonart ohne Zusatz-App und offline mit dem quelloffenen OpenKeyScan-Modell (eigene Umgebung wie Stems;
  Modell von festem Stand, mit Prüfsumme), auch im Hintergrund vorab. „OpenKeyScan-App“ nutzt die lokale API der
  Desktop-App, startet sie bei Bedarf selbst und warnt, wenn die App selbst in Dateien schreibt (Auto-Tagging). Ergebnis in `TXXX:OPENKEYSCAN_KEY`
  (Herkunft „OpenKeyScan“) und auf Wunsch TKEY in deiner Schreibweise – mit Vergleich zu TKEY, Beatport und Mixed In
  Key (gleich, verwandt, abweichend). Plugins können neu Zusatzdateien mit Prüfsumme installieren (`env.files`).
- **API-Rekorder für Entwickler (#243):** `tools/api_recorder.py` zeichnet die Schnittstellen-Aufrufe einer Website
  auf (Playwright) und erzeugt einen Entwurf für ein Dienst-Plugin – ohne Zugangsdaten.
- **Eigene Übersetzungen einreichen (#232):** Hilfe › Melden › „Übersetzung einreichen“ (oder „Eigene Texte einreichen …“
  in den Spracheinstellungen) füllt die selbst angepassten Texte einer Sprache ins GitHub-Formular – nur Texte, die von
  der mitgelieferten Fassung abweichen. Nach Prüfung kommen sie in die mitgelieferten Übersetzungen.

### Geändert

- **Plugin-Karten lesbarer (#248):** Aktionen stehen einzeilig mit Kurznamen („Im Tagger: Übernehmen · Öffnen …“),
  zu lange Namen werden mit „…“ gekürzt (ganzer Name im Tooltip), mehr als vier als „+n“. Aktionen können dafür einen
  Kurznamen `short` angeben.
- **Protokoll direkt öffnen (#247):** Nennt eine Fehlermeldung ein Protokoll („Details im Protokoll: …“), öffnen
  „Protokoll öffnen“ bzw. „Ordner öffnen“ es direkt (nur Dateien im Log-Ordner von TagStudio).
- **Versionsanzeige und Update-Kanäle (#233):** Der Entwicklungsstand im Quellcode heisst „Developer Release“ und zeigt
  die geplante Version (z. B. 4.8.0 statt 4.7.0); Basis und Anzahl Änderungen stehen im Tooltip. „Nur offizielle“ und
  „auch Beta-Versionen“ bieten nur veröffentlichte Versionen an. Der neue Kanal „Entwicklung“ (jede Änderung auf
  `main`) ist nur im Quellcode wählbar; bisherige Quellcode-Einstellungen „auch Beta“ werden einmalig dorthin umgestellt.

### Behoben

- **Tonart (OpenKeyScan): Pfade mit Umlauten und Netzlaufwerken (#250):** Die Analyse meldet Pfade nur noch als
  ASCII-Zeichen zurück (übersteht jede Codepage); Umlaute, `\\NAS\…` und unterschiedliche Schrägstriche werden
  zuverlässig zugeordnet (mit Tests abgesichert).
- **Start bei langsamem Laden (#230):** Die Oberfläche startete manchmal, bevor alle ihre Teile geladen waren – dann
  fehlte z. B. der Einrichtungsassistent nach dem Sprachwechsel, oder Warteschlange und Aufträge blieben leer. Der
  Start wartet jetzt, bis alles geladen ist.

## [4.7.0] – 2026-10-17

### Neu

- **Mehrsprachig: Englisch und Zürichdeutsch (#157):** Einstellungen › Darstellung › Sprache (und der
  Einrichtungsassistent) wechseln mit Flaggen zwischen Deutsch (für Deutschland und die Schweiz gleich, Flagge diagonal
  geteilt), Englisch und Zürichdeutsch – zusätzlich als Auswahlliste unten in der Seitenleiste unter „Einklappen“. Übersetzt
  werden alle Seiten, Dialoge, Tooltips, Meldungen aus dem Python-Teil und die Texte der eingebauten Plugins; Tags in
  den MP3-Dateien bleiben unverändert. Die Option „Sprache des Betriebssystems verwenden“ ist beim allerersten Start
  aktiv; bestehende Installationen bleiben auf Deutsch. Im Englischen werden Tausender mit Komma getrennt (641,243).
- **Eigene Texte exportieren und importieren (#219):** Unter Sprache lassen sich alle Texte als CSV (für Excel) oder
  JSON exportieren, anpassen und wieder importieren. Der Import zeigt eine Vorschau und prüft unbekannte Texte,
  Platzhalter, HTML und Länge; eigene Texte liegen in `~/TagStudio/Sprachen/<sprache>.json`, überlagern die
  mitgelieferten und überstehen Updates. „Eigene Texte zurücksetzen“ entfernt sie. Plugins können in `plugin.json`
  eigene Übersetzungen mitbringen (`"i18n"`).
- **Englische Hilfe (#219):** Handbuch (`README.en.md`), Plugin-Anleitung (`PLUGINS.en.md`) und ID3-Felder
  (`docs/ID3-FELDER.en.md`) gibt es auf Englisch; die Hilfe zeigt sie, wenn Englisch gewählt ist.

- **Plugin-Seite neu geordnet:** Alle Kacheln gleich gross mit festem Aufbau – Titel mit Kategorie (Online-API, Lokale
  API, Übernahme aus Tags, Audio-Verarbeitung), Beschreibung, Aktionen im Tagger, API-Zeile, Hinweise (z. B. wie
  Schlüssel gespeichert werden) und unten immer dieselben vier Knöpfe mit Symbol „Testen“, „Schlüssel“/„Anmelden“,
  „Optionen“, „Mehr …“ (nicht vorhandene ausgegraut). Lange Beschreibungen klappen mit „mehr“ auf; Status steht über
  dem Schalter, die Kategorie unter dem Titel. Oben filtert eine Leiste nach Art (Alle, Online-API, Lokale API, Übernahme aus
  Tags, Audio-Verarbeitung – mit Anzahl); die Wahl wird gemerkt. „Plugin-Ordner öffnen“ bietet eigene und eingebaute Plugins
  (Programmordner) an; unter „Mehr …“ öffnet jede Karte ihren eigenen Ordner.
- **Melden mit drei Arten:** Hilfe › Melden unterscheidet „Fehler melden“, „Verbesserung vorschlagen“ und „Neue
  Funktion vorschlagen“; auf GitHub landet jede Art in ihrem Meilenstein (Fehler, Verbesserungen, Funktionen); Labels und Meilensteine auf GitHub sind deutsch.
- **Lexicon: Verbindung testen:** prüft, ob die Lexicon Local API unter der eingestellten Adresse antwortet. Fehlende Pakete: ein Knopf „Installieren …“
  mit den Varianten im Fenster.

### Geändert

- Sprachwahl als Auswahlliste mit Flaggen (Einstellungen, Assistent, Seitenleiste); erste Zeile „Betriebssystem“.
- Kennzeichen „eingebaut“ auf den Plugin-Karten wird nicht mehr abgeschnitten (kollidierte mit dem A/B-Kennzeichen des
  Players).
- Schreibweise vereinheitlicht: „ss“ statt „ß“ in der ganzen Oberfläche (der Filter versteht weiter „größer als“).
- Einstellungen › Player: die Zeile heisst „Wiederholung“ statt „Wiederholen“.

## [4.6.0] – 2026-10-17

### Neu

- **Lupe im Player (#224):** Neuer Knopf „Lupe“ in Player A zeigt einen vergrösserten, mitlaufenden Ausschnitt der
  Wellenform um die Abspielposition (1–32 s, −/+ oder Mausrad), in hoher Auflösung direkt aus dem Audio. Serato-Raster
  (oben) und eigene Analyse (unten, orange) werden getrennt eingezeichnet – so lässt sich prüfen, ob das Beatgrid auf
  den Schlägen liegt. Klick springt an die Stelle. Nichts wird gespeichert.
- **Serato-Raster mit eigener Analyse vergleichen (#223):** Liegt für einen Titel mit Serato-Raster auch eine eigene
  Analyse vor, zeigt die Spalte „Beatgrid“ „Serato ✓“ (stimmt überein) oder „Serato ≠ Analyse“ mit dem Unterschied im
  Tooltip (halbes/doppeltes Tempo, Tempo weicht ab, erster Schlag versetzt) – auch als Filter. Der Player zeigt denselben
  Hinweis neben „Serato-Grid“. Rechtsklick › „Beatgrid analysieren (auch Serato, zum Vergleich) …“ rechnet die Analyse
  auch für Serato-Titel. Serato-Daten werden nur gelesen, nie geändert. Korrektur: Nach einer Analyse wurde der Status
  teils gelesen, bevor das Ergebnis gespeichert war – die Spalte zeigte dann weiter nur „Serato“. Der Player rechnet die Analyse beim Laden jetzt auch
  für Serato-Titel (nur Cache) und zeigt den Vergleich so ohne Umweg über den Tagger.
- **Serato Tempo Map lesen (#223):** Neuere Serato-Versionen speichern das Raster nicht mehr in „Serato BeatGrid“,
  sondern in „Serato Tempo Map“. TagStudio liest jetzt auch dieses Format (Tempo und Anker, gleichbleibendes Tempo) –
  Spalte „Beatgrid“, Player-Raster und Vergleich funktionieren damit auch für diese Titel. Das Format ist nicht
  öffentlich dokumentiert und wurde aus Beispielen erschlossen; bei abweichendem Aufbau wird nur der Anfang gelesen.
- **Eigenes Raster auch bei Serato-Titeln speichern (#223):** „Beatgrid in Tag speichern …“ hat das Häkchen „Auch Titel
  mit Serato-Raster (nur zum Vergleich)“. Dann reist die eigene Analyse in `TXXX:TAGSTUDIO_BEATGRID` mit der Datei, und
  der Vergleich „Serato ✓ / ≠ Analyse“ bleibt auch ohne Cache erhalten. Serato-Daten bleiben unberührt und massgebend.
- **Beatgrid im MP3 speichern (#221):** Rechtsklick › „Beatgrid in Tag speichern …“ übernimmt das Raster der eigenen
  Analyse (BPM, erster Schlag, Sicherheit) in `TXXX:TAGSTUDIO_BEATGRID` – mit Vorschau und Rückgängig, geschrieben beim
  Speichern. Damit reist es mit der Datei; Player und Spalte „Beatgrid“ („Analyse (Tag)“) lesen es auch ohne Cache.
  Serato-Raster haben Vorrang und bleiben unberührt.
- **Serato-Wellenform im Player (#220):** Hat ein Titel noch keine eigene Wellenform, zeigt der Player sofort die
  Wellenform-Übersicht, die Serato im MP3 ablegt („Serato Overview“) – ohne die Datei zu dekodieren. Die eigene ersetzt
  sie, sobald sie berechnet ist. Serato-Daten werden nur gelesen.
- **Beatgrid-Status im Tagger (#191):** Neue Spalte „Beatgrid“ zeigt für die ganze Bibliothek, ob ein Titel ein
  Serato-Raster, eine eigene Analyse, nur einen BPM-Tag oder gar nichts hat – filter- und sortierbar, ermittelt aus Tags
  und Cache ohne die Dateien zu dekodieren. Rechtsklick › „Beatgrid analysieren …“ analysiert markierte Titel nach
  (wie im Player, abbrechbar); das Ergebnis liegt im Cache, die MP3s bleiben unverändert.
- **Liedtext im Player (#215):** Neuer Knopf im Player A öffnet den Liedtext. Synchronisierte Texte (SYLT im MP3 oder
  die `.lrc`-Datei daneben) laufen mit – die aktuelle Zeile ist hervorgehoben, ein Klick springt an die Stelle. Ohne
  Zeitstempel erscheint der normale Text. Bleibt eingeschaltet, bis man es schliesst.
- **„Developer Release“:** Läuft TagStudio aus dem Quellcode mit Änderungen nach der letzten Version (eingecheckt,
  aber weder Beta noch Release), steht neben der Versionsnummer „Developer Release“ (Tooltip: Anzahl Änderungen, Stand).

### Behoben

- **Tagger-Spalten bündig:** Nimmt die Bildlaufleiste der Liste Platz ein (Windows), waren Überschriften und
  Filterzeile gegenüber den Zeilen verschoben – je weiter rechts, desto mehr. Kopf und Filter rücken jetzt um ihre Breite ein.

## [4.5.0] – 2026-10-16

### Neu
- **Online-Dienste als Plugins (#204, Teil 1):** Dienst-Plugins zeigen auf ihrer Karte einen anklickbaren Link zur
  API-Dokumentation und „Integration …“: alle API-Endpunkte mit Stand (vollständig / teilweise / nicht implementiert),
  **Testabfrage ohne Track** (Künstler, Titel, Mix, Album, ISRC, Dauer – gleiche Suche und Bewertung wie im Tagger) und
  **API-Tester** (Endpunkt wählen, Parameter eintragen, Antwort mit Status, Dauer und JSON; Schlüssel werden eingesetzt,
  aber nie angezeigt; nur lesende Endpunkte). Plugins › „Integrationen …“ zeigt alle Dienste und Endpunkte auf einen
  Blick, inklusive der Update-Prüfung im Kern. Zuerst für LRCLIB, Beatport und Lexicon (27 Endpunkte laut offizieller
  OpenAPI-Beschreibung).
- **Eigene Plugins für MusicBrainz, AcoustID, Deezer, iTunes, Discogs und Last.fm (#204, Teil 2):** jedes mit
  API-Link, Endpunkt-Tabelle, Testabfrage und API-Tester. „Online-Metadaten“ ist jetzt die gemeinsame Suche über die
  eingeschalteten Dienst-Plugins – ausgeschaltete Dienste erscheinen im Dialog als Hinweis. Schlüssel (Discogs-Token,
  Last.fm, AcoustID + fpcalc) trägt man im jeweiligen Plugin ein; bereits gespeicherte werden beim ersten Start
  einmalig und verschlüsselt übernommen. Eine gemeinsame Drosselung je Dienst gilt für alle Plugins.
  „Entdecken“ fragt Deezer jetzt ebenfalls über das Plugin Deezer ab (Beatport schon bisher über sein Plugin); ist
  ein Plugin ausgeschaltet, wird die Quelle mit Hinweis im Protokoll übersprungen.
- **Integrationsfenster mit Beispielen, die ein Resultat liefern (#205):** Testabfrage und API-Tester sind je Dienst mit
  echten Werten vorbelegt (z. B. Daft Punk – One More Time mit passenden IDs); neu „Felder löschen“ und „Beispiel
  einsetzen“. Der wöchentliche Online-Test prüft, dass die Beispiele weiterhin Treffer bringen.
- **Lizenzen mit GitHub-Repositories (#206):** Hilfe › Lizenzen zeigt bei allen Komponenten von GitHub einen Link zum
  Repository und zum Entwickler, dazu Sterne und letzte Änderung (archivierte oder lange stille Projekte markiert).
  Eigene Häkchen „geprüft / gefolgt / bedankt“ und ein vorbereiteter Danke-Text („Danke …“, Englisch oder Deutsch, mit
  der Bitte um Rückmeldung, falls die Nutzung nicht erwünscht ist) zum Kopieren. Die Tabelle nutzt die ganze Breite. Neu in der
  Liste: python-build-standalone und die einzelnen GitHub Actions.
- **API-Tester mit Drosselung (#212):** Der Tester hält dieselben Abstände je Dienst ein wie die Suche und wiederholt
  bei „ausgelastet“ (HTTP 429/503) automatisch; die Antwort zeigt die Zahl der Wiederholungen.
- **IDs aus der Antwort übernehmen (#213):** IDs in der Antwort des API-Testers sind anklickbar; TagStudio schlägt die
  passenden Endpunkte vor (z. B. Beatport: Suche → Titel/Release/Künstler/Label) und füllt das ID-Feld.
- **Fehler melden und Funktionen vorschlagen (#187):** Hilfe › „Melden“ und „Melden …“ im Tagger. TagStudio füllt das
  GitHub-Formular vor (Bereich, Version, System), zeigt ähnliche Meldungen, schwärzt private Angaben (Benutzerordner,
  E-Mail-Adressen, Schlüssel) und öffnet es nach Vorschau und Zustimmung im Browser – abgeschickt wird mit dem eigenen
  GitHub-Konto, TagStudio speichert keine Zugangsdaten. Neue Meldungen erhalten das Label `triage` und werden erst nach
  Prüfung durch den Projektverantwortlichen umgesetzt.
- **Zeitraum-Filter für „Aufgenommen“ und „Bearbeitet“ (#214):** In der Filterzeile des Taggers z. B. `<30d` (letzte
  30 Tage), `>1y` (älter als ein Jahr), `heute`, `2026-10`, `2026-09-01..2026-10-16` oder `leer`; sortiert wird nach dem
  echten Zeitpunkt.
- **Filter je Spalte im Tagger (#202):** Filterzeile unter den Spaltenköpfen – je Spalte ein Suchfeld (mehrere Wörter,
  Reihenfolge egal), Zahlenspalten auch mit `>120`, `<=5` oder `120-128`; wirkt zusammen mit dem Suchfeld oben.
  **Esc** leert ein Feld, **×** alle, Knopf „Filter“ blendet die Zeile aus.
- **Plugin „Liedtexte“ (#183):** Tagger › Plugins › „Liedtexte suchen (LRCLIB) …“ – frei, ohne Schlüssel. Genaue
  Abfrage mit Künstler, Titel, Album und Dauer, sonst Suche; Original, Remix und Live werden nicht gleichgesetzt
  (andere Fassung höchstens „unsicher“). Vorschau mit Häkchen: normaler Text in `USLT`, synchronisierter in `SYLT`;
  vorhandene Liedtexte werden nur mit Häkchen ersetzt. Zusätzlich eine `.lrc`-Datei neben dem MP3, wenn unter
  Plugins › Liedtexte › „Einstellungen …“ eingeschaltet (dort auch die Sprache). Instrumentals werden erkannt.
- **In Bibliothek aufgenommen (#184):** die Übernahme aus „Vorbereiten“ schreibt den Zeitpunkt in
  `TXXX:TAGSTUDIO_ADDED` (ein vorhandener Wert bleibt). Für bestehende Titel: Tagger › „Aufnahmedatum nachtragen …“ mit
  Vorschau – Vorschlag aus dem frühesten Snapshot, der den Titel enthält (am Audio erkannt, auch nach Umbenennen), sonst
  ein Datum von Hand; nie das Dateidatum. Tagger-Spalte „Aufgenommen“, abschaltbar unter Einstellungen › Speichern.
- **Letzte Bearbeitung (#185):** beim Speichern geänderter Tags schreibt TagStudio den Zeitpunkt in
  `TXXX:TAGSTUDIO_EDITED` (ISO 8601 mit Zeitzone, z. B. `2026-10-16T01:55:00+02:00`) – nicht beim Anzeigen, Einlesen
  oder Speichern ohne Änderung; Rückgängig/Wiederherstellen zählt als Bearbeitung. Abschaltbar unter Einstellungen ›
  Speichern; im Tagger als Spalte „Bearbeitet“ wählbar, im Vergleich standardmässig „unwichtig“.

### Behoben
- **Liedtexte: Fehlersuche (#203):** War LRCLIB nicht erreichbar (z. B. HTTP 503), stand bisher nur „nicht gefunden“.
  Jetzt eigene Meldung „nicht abgefragt – LRCLIB war nicht erreichbar“; nach drei Ausfällen in Folge wird nicht weiter
  angefragt. Das Protokoll zeigt je Titel, wonach gesucht wurde (genau / Titel + Künstler / Freitext), wie viele Treffer
  kamen und den besten Kandidaten mit Prozent. Neue dritte Stufe: Freitextsuche „Künstler Titel“. LRCLIB kennt keine ISRC.
- **Änderungsjournal bei grossen Listen (#201):** Snapshots vergleichen lädt jetzt auch bei 1500 geänderten Titeln
  zügig: Tags werden im Speicher gelesen statt über je zwei Hilfsdateien (unter Windows bremste der Virenschutz jede
  davon). Fortschritt „x von y“ auch im Vergleichsschritt; **Abbrechen** greift sofort und zeigt „Wird abgebrochen …“.
  Gilt ebenso für Snapshot-Seiten im Vergleich.
- **„ohne bekannte Herkunft“ (#199):**

## [4.4.1] – 2026-10-16

Version 4.4.1 – Player-Stabilität: Übergänge im Takt (messen und nachführen), Beatgrid-Metronom, Takt- und Cue-Sprünge,
Tempo per Doppelklick/Mausrad, schneller Start des Players, Herkunfts-Auswahl mit Kennzeichen (Betas 4.4.1-beta.1 bis beta.6).

### Neu
- **Takt- und Cue-Sprünge (#182):** **←/→** springt im Player einen Takt (vier Schläge, mit Beatgrid oder BPM-Näherung),
  **Shift+←/→** zum vorigen/nächsten Cue; rückwärts wird der zuletzt angesprungene Cue ignoriert, bis vier Takte
  weitergespielt wurden. Gilt für Player A/B und das abgedockte Fenster; die Tagger-Liste behält ←/→ für die Stems.
  Die alte Belegung Alt+Bild↑/↓ und Shift+←/→ ±10 s entfällt.
- **Beatgrid-Metronom ♩ (#181):** zuschaltbar in Player A/B und im abgedockten Fenster, zum Hören, ob das Raster sitzt;
  Klicks nach WebAudio-Zeitbasis, nach Pause/Sprung/Tempoänderung neu ausgerichtet. Lautstärke 0–100 % (Standard 80 %)
  für A und B gemeinsam, kräftiger Rechteck-Klick. Während des Überblendens folgt es dem auslaufenden Titel und wechselt
  erst nach dem Ausblenden. Der Vierer-Akzent ist kein geprüfter Downbeat.
- **Beatgrid-Herkunft (#181):** neben dem Titel steht, woher das Raster kommt (`Serato-Grid`, `Audioanalyse`,
  `Nur BPM-Schätzung`, `Kein Beatgrid`); ohne Serato-Grid startet die eigene Analyse beim Vorhören automatisch.
- **Latenzkorrektur für Übergänge (#181):** Einstellungen › Player bzw. Player-Menü, −500 bis +500 ms, gespeichert;
  verschiebt die Beat-Phase des Folgetitels (positiv = später). Keine automatische Messung.
- **Übergänge im Takt halten (#181):** beim automatischen Überblenden in Player A misst TagStudio laufend den
  Beat-Versatz zwischen auslaufendem und neuem Titel und gleicht ihn mit einer kleinen Tempo-Korrektur des neuen Titels
  aus (höchstens ±4 %, ohne Sprung). Die beim Start gemessene Verzögerung wird gelernt und beim nächsten Übergang schon
  vorgehalten. Einstellungen › Player › „Im Takt halten“ (Standard an), gelernter Wert mit „Zurücksetzen“, „Messwerte …“
  zeigt die letzten Übergänge; jeder Übergang steht zusätzlich im App-Protokoll (Zeilen „Übergang“). Im Browser-Test setzte
  der Folgetitel ohne Nachführen rund 90 ms zu spät ein (Seek-Verzögerung) – das war die Ursache der Offbeat-Übergänge.

- **BPM-Anzeige im Player (#194):** Doppelklick setzt das Originaltempo, Mausrad über der Anzeige ändert das Tempo um
  ±0,1 BPM (mit Shift ±1 BPM, rastet am Original ein); Einzelklick öffnet wie bisher den Tempo-Dialog. Player A und B.
- **Herkunfts-Auswahl mit Kennzeichen (#198):** Tagger (Weitere Felder) und Vergleich: mehrere Herkünfte gleichzeitig
  wählbar; Knopf und Liste zeigen die farbigen Herkunfts-Kennzeichen mit Anzahl.
- **Dateiordner öffnen (#197):** im Kontextmenü von Tagger-Titeln, Vergleichsfeldern und Dateipaaren.
### Geändert
- **Übergänge (#181):** der neue Titel wird stumm geladen, die Phase direkt nach dem tatsächlichen Start angeglichen und
  erst dann eingeblendet; Beat-Ausrichtung am Titelanfang und Tempo-Rücksetzung verbessert.
- **Überblenddauer:** 0 (aus) bis 30 Sekunden in ganzen Sekunden (bisher Auswahl bis 12 s).
- **Tooltips (#192):** einheitlich im TagStudio-Design im Hauptfenster und im abgedockten Player, auch für Knöpfe mit
  wechselndem Text; keine Standard-Browser-Tooltips mehr.

### Behoben
- **Fortsetzen nach dem Neustart (#195):** der Player lädt den zuletzt gespielten Titel sofort über den Dateipfad –
  parallel zum Einlesen des Tagger-Ordners statt danach. Sobald der Tagger fertig ist, ist der Titel dort markiert und
  sichtbar (bisher blieb die Liste auf der alten Auswahl stehen).
- **Schneller Doppelklick zum Abspielen (#196):** wurde verschluckt, wenn die Liste zwischen Drücken und Loslassen des
  zweiten Klicks neu gezeichnet wurde (Titel-Details des ersten Klicks kamen gerade an). Der Doppelklick wird jetzt beim
  zweiten Drücken erkannt und spielt sofort; das Zeitfenster zählt ab dem Klick (600 ms).
- **„ohne bekannte Herkunft“ (#199):** filtert im Tagger jetzt; vorher sprang die Auswahl auf „Alle Herkünfte“ zurück.
- **Snapshots:** Die Snapshot-Liste brach mit „Snapshot nicht lesbar“ ab, wenn gleichzeitig ein Snapshot gelöscht wurde
  (z. B. bei „Neue Baseline“). Gelöschte werden jetzt übersprungen; beschädigte stoppen das Aufräumen weiterhin.
- **Neustart im Browser-Modus (#193):** die Seite lädt erst neu, wenn die neue Instanz antwortet – vorher konnte sie
  gelegentlich die alte, gerade beendete Instanz erwischen und leer bleiben.
- **Oberflächen-Tests (#193):** Feldnamen-Test an die neuen Tooltips angepasst.
- **Metronom nach Klick in den Titel (#181):** Das Metronom plant seine Klicks jetzt über eine geglättete Medienuhr. Nach
  einem Sprung (Klick in die Wellenform, Cue, Takt-Sprung) werden bereits geplante Klicks verworfen und erst wieder
  geklickt, wenn die Wiedergabe gleichmässig läuft – vorher lief es danach oft versetzt („async“).
- **Browser-Modus:** die Adresse wird sofort ausgegeben, auch wenn die Ausgabe umgeleitet ist (vorher erst gepuffert).
- **Nur noch TagStudio-Tooltips (#192):** auch die Punkte im Energieverlauf des DJ-Sets zeigen keinen Browser-Tooltip mehr;
  SVG-Titel werden wie `title` übernommen. Für Screenreader bleibt nur das unsichtbare `aria-label`.
- **Dokumentation (#193):** Tastaturübersicht im README, Stand-Angaben in Übergabe, Projektstand und AGENTS.md
  nachgeführt; Meilenstein-Workflow nutzt `actions/checkout@v7` wie alle anderen.

### Intern
- Oberflächen-Tests laufen zusätzlich bei jedem Push in GitHub Actions (Job „Oberflächen-Tests“, ca. 7 min).
- Regeln für KI-Agenten (`AGENTS.md`, `CLAUDE.md`): Releases nur nach ausdrücklicher Freigabe, App-Meldungen sind keine
  Entwicklungsaufträge, fremde Bibliotheken und Datenbanken werden nie verändert.
- Meilensteine über Eigentümer-Kommentare in #190 verwalten (`.github/workflows/milestone-admin.yml`).
- Neue Konzepte: Produkt- und Architekturkonzept v0.1, Musikanalyse, DJ-Plattformen; 1001Tracklists als Idee (#180).
- Tests: Node-basierte Logiktests für Beatphase, Tastatur und Metronom, Tooltip-Tests.

## [4.4.0] – 2026-10-12

### Neu
- Beatport: **„Fehlende Käufe herunterladen …“** (Plugins › Beatport) – lädt gekaufte Titel, die in deinen Ordnern
  noch fehlen, unverändert in einen Zielordner (z. B. den Eingangsordner von „Vorbereiten“), im gekauften Format;
  ZIP-Downloads werden entpackt, bereits geladene Titel nicht doppelt geholt. Beatport hat dafür keine offizielle
  Schnittstelle – der Weg wird vorsichtig ermittelt und protokolliert, Vorhör-Ausschnitte werden nie als Download
  genommen. Zuerst mit 1 Titel testen (#117).
- **Profile** – eine zweite, unabhängige TagStudio-Instanz mit eigenen Einstellungen und Daten (Sicherungen,
  Snapshots, Vorbereiten, Entdecken, Caches, Protokolle); Plugins, die Stems-Umgebung, Modelle und FFmpeg werden
  gemeinsam genutzt. Einstellungen › Profile: neues Profil (leer oder mit den aktuellen Einstellungen), wechseln,
  Verknüpfung auf dem Desktop; beim Start Profilwahl (abschaltbar). Profile laufen auch gleichzeitig; das Profil steht
  im Fenstertitel und unten in der Seitenleiste. Start auch mit `--profil NAME` (#163–#165).
- **Einrichtungsassistent** beim ersten Start (bzw. in einem neuen Profil): Ziele, Musikordner, Sicherungen und
  Snapshots, genutzte Programme (Plugins und Vorbereiten-Workflow passend), Online-Dienste, Darstellung. Gewählte
  Bereiche werden in der Seitenleiste mit ★ empfohlen. Jederzeit erneut über Hilfe oder Einstellungen › Darstellung
  (#167, #168).
- **Speicherort und Ordnerstruktur:** Basislaufwerk und Basisordner werden gespeichert – jede Ordnerauswahl beginnt
  dort. Im Assistenten nach der Laufwerkswahl entweder bestehende Ordner wählen oder die empfohlene Struktur anlegen
  (`00_New`, `01_Library`, `02_Archiv`, `90_Download`, `91_Work`, `99_Sicherung`; Namen änderbar). TagStudio stellt
  Bibliothek, Vorbereiten (Eingang, Arbeitsordner, Quelle Downloads), Sicherungen, Snapshot-Speicher und das
  Beatport-Download-Ziel darauf ein; vorhandene Ordner bleiben, nichts wird verschoben. Einstellungen › Speicherort und
  Ordner zeigt alle Arbeitsordner (#172).
- **Aussortieren** ins Archiv (z. B. `02_Archiv`): im Tagger („Aussortieren …“) und in „Vorbereiten“ (Zelle ›
  „Aussortieren“). Unterordner bleiben erhalten, ein Stems-Ordner wandert mit; in „Vorbereiten“ kommt das Original aus
  dem Eingang ins Archiv, Stufen-Kopien werden auf Wunsch gelöscht. Jede Bewegung steht im Vermerk
  `_aussortiert.csv`; Einstellungen › Speicherort und Ordner › „Aussortierte …“ holt Titel zurück (#173).
- **Speicherkonzept** – alle Ablageorte und die empfohlene Ordnerstruktur:
  [docs/KONZEPT-SPEICHER.md](docs/KONZEPT-SPEICHER.md).
- **Projektstand und Übergabe** im Repo: [docs/PROJEKTSTAND.md](docs/PROJEKTSTAND.md),
  [docs/UEBERGABE.md](docs/UEBERGABE.md), [docs/PROJEKTSTAND-ARCHIV.md](docs/PROJEKTSTAND-ARCHIV.md).
- **Übersicht Tag-Programme und Musik-Plattformen** mit Kurzbeschreib, Link und Kosten (Stand Oktober 2026):
  [Word](docs/Tag-Programme-und-Musik-Plattformen.docx), [PDF](docs/Tag-Programme-und-Musik-Plattformen.pdf).
- **Konzepte nachgetragen** für Tagger, Tag-Fixer, Vergleich, DJ-Set, Plugins, Einstellungen, Hilfe, Update, Player und
  App/Oberfläche (`docs/KONZEPT-*.md`) – werden bei jeder Weiterarbeit an der Funktion nachgeführt.
- **Seitenleiste:** Menüpunkte lassen sich ausblenden (Einstellungen › Darstellung) (#169).
- **„Erste Schritte“** – kurze Hinweise beim ersten Besuch jeder Seite (neu startbar über Hilfe) – und **„Neu in
  dieser Version“** nach einem Update (#170).
- **Player: Tempo von Hand** – Klick auf die BPM-Anzeige (Player A und B), neues Tempo eingeben (50–200 % des
  Originals, Tonhöhe nach Einstellung); **Reset** stellt das Original-Tempo wieder her. Gilt nur für den laufenden Titel,
  die Datei bleibt unverändert (#174).
- **Player: „Im Tagger zeigen“** – Knopf neben dem Titel wechselt zum Tagger und markiert den laufenden Titel (Filter
  wird bei Bedarf aufgehoben, Stems aufgeklappt); liegt der Titel nicht im geladenen Ordner, bietet TagStudio an, dessen
  Ordner zu laden (#175).
- **Hilfe › Lizenzen** – alle verwendeten Bibliotheken, Werkzeuge, Online-Dienste und Vorlagen mit Lizenz und Quelle
  (`docs/third-party.json`). Der neue Workflow „Fremdkomponenten prüfen“ vergleicht sie monatlich mit PyPI/GitHub und
  meldet neue Versionen oder geänderte Lizenzen als Issue (#176).

### Geändert
- **Vorbereiten:** Eingang, Arbeitsordner, Bibliothek und Stufen-Ordner in grüner Schrift (#177).
- **Snapshots:** überwachte Verzeichnisse und Speicherort in grüner Schrift (#178).

### Behoben
- Desktop-Verknüpfung eines Profils (macOS/Linux) nur noch für den eigenen Benutzer ausführbar (CodeQL, #171).

## [4.3.0] – 2026-10-11

### Neu
**Tracks vorbereiten** (neue Seite „Vorbereiten“, erster Menüpunkt – #109–#118, #160, #161)
- Neue Titel laufen vom **Eingangsordner** über frei zusammenstellbare **Schritte** in die **Bibliothek**; jede Stufe
  arbeitet auf einer Kopie, die Rohdaten bleiben unverändert. Workflow-Vorlage „DJ-Workflow (Beatport → Bibliothek)“,
  Export/Import ohne persönliche Pfade, „Wählen …“ (Dateibrowser) für alle Ordner und Programme.
- Schritt-Typen: **Tag-Rezept** (automatisch), **externes Programm** (Platinum Notes, Picard … öffnen, Abschluss an der
  Herkunft erkennen oder bestätigen), **Plugin** (z. B. Lautheit, Online-Metadaten – nur leere Felder füllen, alle
  vorausgewählten oder nur ausführen), **Pflichtfelder prüfen**, **Übernahme** mit Duplikatprüfung (Dateiname,
  Künstler + Titel, Audio) und Snapshot der Bibliothek, **nachgelagerte Programme** als Status (Mixed In Key,
  beaTunes, Lexicon erkannt; Engine DJ, Mixo von Hand).
- **Schutzregel „nur ergänzen“** je Schritt (Variante A/B/C, nur melden oder automatisch zurücksetzen, „Feld künftig
  erlauben“).
- **Quellen (Download-Ordner)** je Kaufplattform (Beatport, Bandcamp, Traxsource, Juno …): „Abholen“ kopiert neue MP3 –
  auch aus ZIP-Archiven – in den Eingang, ohne Doppelte; die Quelle steht in der Tabelle.
- Seitenleiste zeigt offene Titel im Eingang und neue Downloads (alle 2 Minuten aktualisiert); Stufen-Kopien
  übernommener Titel auf Wunsch löschen.

**Entdecken** (Reiter auf der Seite „Vorbereiten“ – #120, #162)
- Neue Titel von **gefolgten Künstlern, Labels und Genres** über **Deezer** (ohne Anmeldung) und **Beatport**
  (Anmeldung des Plugins, Genre-Charts Top 100, BPM/Tonart); „Aus der Bibliothek vorschlagen“ schlägt die häufigsten
  Künstler und Labels vor.
- Kompakte Liste mit **Vorhören**, Merken, gekauft, ausblenden, Cover-Vergrösserung beim Darüberfahren; Titel aus der
  Bibliothek werden als „vorhanden“ erkannt. Gekauft wird nie automatisch – „Öffnen“ führt zur Seite des Titels.
- Auf Wunsch **täglich beim Start automatisch suchen**, **Merkliste als Excel/CSV exportieren**; der Beatport-Abgleich
  markiert gekaufte Titel als „gekauft“.

**Tag-Rezepte, ID3** (#111, #112, #98, #13)
- **Tag-Rezepte** (Tagger › „Tag-Rezepte …“): Aktionslisten wie in Mp3tag – Ersetzen, Schreibweise von Wörtern,
  Gross-/Kleinschreibung, Leerzeichen bereinigen, doppelte Werte/Felder entfernen, nur ersten Wert behalten, Felder
  entfernen oder setzen (%FELD%), ID3-Version und ID3v1. Vorschau und Rückgängig; Vorlage „Beatport-Download aufbereiten“.
- **ID3v1 schreiben** (Einstellungen › Sicherungen und Speichern › „ID3v1 (Dateiende)“; auch als Rezept-Aktion).
- **Alle ID3-Frames**: Katalog aller Frames aus ID3v2.2, v2.3 und v2.4 (inkl. Kapitel und iTunes-Frames) in
  `docs/ID3-FELDER.md`; Binär-Frames lesbar (SYLT, ETCO, RVA2/RVAD, Equalizer, Kapitel, Zähler, OWNE/COMR, LINK …).
- **Vergleich:** Binärfeld-Editor (Serato-Ansicht, JSON-Baum, Hex) und JSON-Baum wie im Tagger.

**Hilfe** (neuer Menüpunkt – #158, #159)
- **Tag-Übersicht** als eine Tabelle mit aufklappbaren Gruppen (offizielle ID3v2.4-Frames nach Funktion,
  DJ-Analysewerte, Programm-Daten nach Herkunft, eigene Tags, weitere Frames), Gruppenfilter und Sortierung; Bedeutung,
  Mp3tag-Name, DJ-Relevanz, konfigurierte Herkunft und der Vergleich der DJ-Software.
- **Bibliothek scannen** zählt je Tag die Titel **mit** und **ohne** das Feld (Ergebnis im Cache); ein Klick öffnet
  den Tagger mit Filter „vorhanden“ bzw. „fehlt“ zum Vervollständigen.
- Handbuch, ID3-Felder, Plugin-Anleitung und **alle Tastenkombinationen** direkt in der App.

**Snapshots und Sicherungen** (#59)
- Änderungsjournal als **Excel oder CSV exportieren** (genau die sichtbaren Einträge).
- **Sicherungen im Snapshot-Speicher**: gleiche Tag-Bytes nur einmal abgelegt, spart viel Platz; ältere
  ZIP-Sicherungen bleiben lesbar und wiederherstellbar (abschaltbar).

**Plugins** (#117, #119)
- Neues Plugin **Lautheit messen**: LUFS, True Peak, Lautheitsbereich (EBU R128, FFmpeg), ReplayGain, Clipping-Zählung
  (TXXX:CLIPPING); optional eine angeglichene Kopie in eigenem Ordner – das Original bleibt unverändert.
- Beatport: **„Gekaufte Titel abgleichen“** – Käufe des Kontos mit deinen Ordnern vergleichen (Beatport-ID, ISRC,
  Künstler + Titel + Mix), Ergebnis als CSV; der automatische Download folgt in einer späteren Version.
- Neuer Optionstyp `folders` (mehrere Ordner mit Dateibrowser) für Plugins.

### Behoben
- Dialoge: Klick-Handler früherer Dialoge liefen weiter mit (z. B. legte „+ Quelle“ nach dem zweiten Öffnen zwei
  Zeilen an).
- ID3v2.2: alle Frames werden übernommen (bisher fehlten u. a. SLT, CNT, ETC, EQU, RVA, IPL, GEO, LNK, TOA, TOT …);
  LINK-Verweise erhalten die 4-Zeichen-ID (#98).
- ID3v2.3 `IPLS` (Beteiligte Personen) wird als `TIPL` gelesen und beim Umwandeln v2.3 ↔ v2.4 korrekt umgesetzt;
  leere Rollen bleiben erhalten (#98).

## [4.2.0] – 2026-10-11

### Neu
- Neues Plugin **Mixed In Key übernehmen**: liest Tonart, BPM und Energie, die Mixed In Key in Kommentar, Titel,
  Künstler, Gruppierung, Label oder TXXX:EnergyLevel geschrieben hat, und schlägt TKEY (in deiner Schreibweise),
  gerundetes BPM und das Merkmal ENERGY (1–10 → 10–100) vor; auf Wunsch werden die Präfixe wieder entfernt (#147).
- Werkzeug `tools/wavcheck.py` und Konzepte für **WAV-Unterstützung** und **Mehrsprachigkeit** (#156, #157).
- **Serato-Daten lesbar** (nur Ansicht): Markers2 (Cues, Loops, Farben, Namen, Track-Farbe, BPM-Sperre), Autotags
  (BPM, Auto-Gain, Gain), BeatGrid (Marker, BPM, erster Schlag), Overview (kleine Wellenform), Analyse-Version – als
  Kurzfassung bei „Weitere Felder“ und ausführlich im Binärfeld-Editor; kaputte Daten werden verständlich gemeldet (#76).
- **Beatgrid im Player** (aus Serato, sonst aus BPM und erstem Cue geschätzt): Rasterlinien in der Wellenform,
  Überblenden **im Takt** (nächster Titel in der Phase des laufenden) und wahlweise **auf Taktgrenze** (4/8/16 Schläge),
  **Sync**-Knopf in Player B (Tempo und Takt von Player A) (#76).
- Beatgrid ohne Serato: TagStudio **ermittelt den Schlag aus dem Audio** (Tempo fein um das BPM-Feld, Lage des
  ersten Schlags) zusammen mit der Wellenform und merkt ihn im Cache; vor dem Überblenden wird der neue Titel bei
  Bedarf zuerst analysiert. Neue Option **Tonhöhe beim Angleichen beibehalten** (aus = wie beim Plattenspieler) (#76).
- Vorschau der Plugins **Online-Metadaten** und **Beatport**: Links zum Treffer auf der Plattform (je Datei und je
  Feld), um z. B. eine andere Version eines Titels zu erkennen, bevor man übernimmt (#144).
- Tagger: Feldnamen wie in Mp3tag (z. B. TITLE, INITIALKEY, CATALOGNUMBER) bei den wichtigen Feldern am Ende und bei
  „Weitere Felder“; Benutzerfelder zeigen ihren Namen vorne. Beim Darüberfahren eine kurze Erklärung des Felds
  (#140, #151).
- Tagger: „Weitere Felder“ wahlweise nach Herkunft sortiert – offizielle ID3v2.4-Felder zuerst, dann TagStudio, dann
  die Herkünfte alphabetisch (#141).
- Tagger: Cover-Bereich aufgeteilt – links Länge und Bewertung, rechts Bild-Info und die Knöpfe untereinander, neu
  „Im Web suchen“ (Bildersuche mit Künstler und Album) (#150).
- Tagger: Auswahl der Merkmal-Spalten mit Häkchen; das Menü bleibt offen, mehrere Merkmale nacheinander (#149).
- Tagger-Liste: **Spalten ▾** – weitere Spalten (u. a. Album-Künstler, Kommentar, Länge, kbit/s, Bewertung, Label,
  Katalognummer, Remixer, ISRC) und **beliebige Felder** als Spalte (#154); Reihenfolge per Ziehen in der Kopfzeile
  (#152); „An Fenster anpassen“ oder „Optimale Breite“ mit waagrechtem Blättern, die Kopfzeile läuft mit (#148).
- Tagger-Liste: **Sortierung in bis zu drei Stufen** (Shift+Klick), Knopf „↺ Sortierung“ setzt auf den Standard
  zurück, „Aktuelle Sortierung als Standard“ (#153).
- **DJ-Set: mehrere gespeicherte Listen** – Knopf „Liste ▾“: neu, speichern, speichern unter, laden, umbenennen,
  entfernen; Hinweis bei nicht gespeicherten Änderungen; der Export heisst wie die Liste (#138).
- **Warteschlange im Player:** Rechtsklick auf Titel im Tagger oder DJ-Set › „Als Nächstes spielen“ / „Zur
  Warteschlange hinzufügen“. Hat Vorrang bei ⏭, Titelende und Überblenden; Knopf neben ⏭ öffnet die Liste
  (umsortieren, entfernen, leeren, als DJ-Set übernehmen) (#138).
- Neue Plugins **beaTunes übernehmen** (TXXX:MOOD_DANCEABILITY, MOOD_ACOUSTIC, MOOD_HAPPY, MOOD_AGGRESSIVE → Merkmale)
  und **Lexicon übernehmen** (Tanzbarkeit, Energie, Fröhlichkeit und Mood-Tags über die Lexicon Local API) – beide mit
  **Abgleich**: Wurde ein Wert in der Datei seit dem letzten Übernehmen geändert, ist der Vorschlag nicht angehakt (#145,
  #146).
- Tagger: **Stimmung (Mood)** als eigenes Feld mit mehreren Werten – Chips mit ×, Eingabe mit Vorschlägen (Werte im
  Ordner, eigene Liste unter Einstellungen › Tagger, Grundliste); bei Mehrfachauswahl werden teilweise vorhandene Werte
  gestrichelt gezeigt (Klick: allen geben). Gespeichert wie in Mp3tag: ID3v2.4 `TMOO`, ID3v2.3 `TXXX:MOOD`; Spalte
  „Stimmung“ und Lexicon-Mood-Tags nutzen dasselbe Feld (#12).
- Plugin-Vorschau: Knopf **„Nur fehlende“** wählt nur Felder, die in der Datei noch leer sind; „Vorschlag“ heisst
  jetzt „Vorauswahl“ (#142).
- **Bevorzugte Ansicht** (Spalten, Breite, Sortierung, Merkmale) speichern und wieder laden – im Spalten-Menü und
  unter Einstellungen › Tagger (#155).

### Geändert
- Beatport: neue Option „Nur noch nicht vorhandene Felder“ – ist Standard; vorhandene Felder werden dann weder
  geändert noch in der Vorschau gezeigt (#142).
- Herkunft: `TXXX:CATALOGNUMBER` wird Beatport zugeordnet (#143).
- **Schnellerer Start:** Der zuletzt geladene Tagger-Ordner wird beim Start im Hintergrund eingelesen – ohne
  Fortschrittsfenster, die App ist sofort bedienbar (Fortschritt in der Tagger-Liste und der Fusszeile). „Einlesen“ von
  Hand bricht das ab und lädt neu. Das App-Protokoll zeigt, wie lange Einlesen und Snapshot-Prüfung dauern (#137).
- **Listen-Cache schneller:** grosse Frames (Cover …) liegen jetzt in einer einzigen Packdatei statt in Tausenden
  Einzeldateien – unter Windows war das Öffnen dieser Dateien der Hauptteil der Wartezeit beim Einlesen aus dem
  Cache. Der alte Cache wird beim ersten Einlesen übernommen; das App-Protokoll zeigt die Zeiten je Schritt (#137).

### Behoben
- Doppelklick auf einen Titel (Tagger, Vergleich, DJ-Set) spielt ihn wieder zuverlässig ab; seit die Zeilen
  ziehbar sind, wurde der zweite Klick teils als neuer Einzelklick gezählt (#139).

## [4.1.0] – 2026-10-11

### Neu
- **Versionshinweise:** neuer Abschnitt „Weitere Versionen“ zeigt die Hinweise aller älteren Versionen direkt in
  der App (aufklappbar, auch ohne Internet) (#136).
- Einstellungen › **Expert**: Diagnose (Version, Python, System, Oberfläche, Plugins, Pfade) mit „Diagnose kopieren“,
  **Einstellungsdatei** ansehen und durchsuchen (Zugangsdaten ausgeblendet), **Protokolle** ansehen; neues
  App-Protokoll `~/TagStudio/Logs/app.log` mit Start/Ende, Fehlern und Warnungen, auch aus der Oberfläche (#133).
- Seitenleiste unten: Symbole für **Vollbild** (auch F11), **Fenstermodus**, **Neu starten** und **Beenden** (#134).
- Beim **Beenden** (auch über das X des Fensters) erscheint „Einstellungen werden gespeichert …“; ungespeicherte
  Änderungen und laufende Hintergrund-Aufträge werden vorher in der App abgefragt (#132).
- Neues Plugin **Online-Metadaten**: sucht für markierte Titel bei **MusicBrainz** (über ISRC oder Titel/Künstler,
  Cover aus dem Cover Art Archive), optional per **AcoustID-Fingerabdruck** (fpcalc), bei **Deezer**, **iTunes**
  (Land wählbar, Cover 1400 px), **Discogs** (eigener Token) und **Last.fm** (Tags, nie vorausgewählt). Treffer werden
  bewertet (ISRC, Titel ohne Mix, Künstler, Dauer); Album, Datum, Label/Katalognummer, ISRC, Genre, BPM, Spur-/CD-Nummer,
  Cover und Dienst-IDs erscheinen als **Vorschau mit Häkchen** – je Feld die erste Quelle vorausgewählt, andere Quellen als
  Alternative. Modus „nur leere Felder ergänzen“ (Standard) oder „überschreiben“. Abfragen werden je Dienst gedrosselt
  (MusicBrainz 1/s), 429/503 werden wiederholt. Schlüssel werden verschlüsselt im Plugin-Ordner abgelegt (Windows: DPAPI),
  nie protokolliert; „Schlüssel …“ erklärt Schritt für Schritt mit Links, wie man Discogs-Token, Last.fm- und
  AcoustID-Schlüssel erstellt und fpcalc bekommt; „Verbindungen testen“ prüft alle Dienste (#6, #7, #8).
- Tagger merkt sich seinen **Zustand** (Ordner, Unterordner, Markierung, Sortierung, Suchfeld/Filter, aufgeklappte
  Stems, Bildlauf) und stellt ihn beim Start wieder her – auf jeder Startseite, damit z. B. DJ-Set-Titel sofort
  geladen sind. Einstellungen › Tagger › „Beim Start laden“: zuletzt geladenen Ordner (Standard), Standardordner oder
  nichts (#127).
- Player: **Wiedergabe fortsetzen** – Titel und Position von Player A und B werden gemerkt und beim Start in Pause an
  derselben Stelle geladen; abschaltbar unter Einstellungen › Player › „Fortsetzen“. „Nach dem Neustart“: in Pause
  laden (Standard), sofort abspielen (Autoplay) oder abspielen, wenn er beim Schliessen lief (#126).
- App-Fenster merkt sich **Grösse, Position und „maximiert“** und öffnet beim nächsten Start wieder so; liegt die
  Position auf einem nicht mehr angeschlossenen Bildschirm, erscheint es mittig auf dem Hauptbildschirm (#125).

### Geändert
- Beta-Versionen werden nur noch für Windows gebaut und getestet; macOS-Installer und -Tests gibt es mit den finalen
  Versionen.
- **Python 3.12 oder neuer** nötig für die Quellcode-Variante (vorher 3.9; 3.9 und 3.10 bekommen keine Updates
  mehr). Der Installer bringt jetzt **Python 3.15** mit (vorher 3.12; Stems-Umgebung bleibt 3.12). Tests laufen mit 3.12 und 3.15 (Linux derzeit nicht
  vorgesehen); der Installer-Workflow kann von Hand mit einer anderen Python-Version bauen (Probe-Build) (#135).

### Behoben
- Plugins mit eigener Umgebung (Stems): fehlt das Python, auf das die Umgebung verweist (z. B. nach einem Update von
  uv oder Python), meldet TagStudio das verständlich statt „Code 1“, und „Neu installieren …“ legt die Umgebung neu an,
  statt die beschädigte weiterzuverwenden (#135).
- Update: die alte Instanz blieb offen und die neue startete ohne die gespeicherten Einstellungen. Es läuft jetzt nur
  noch **eine Instanz** (ein zweiter Start meldet „TagStudio läuft bereits“); der Installer erkennt ein offenes
  TagStudio und bittet, es zu schliessen; beim Neustart nach einem Update werden Zustände vorher gespeichert und die
  neue Instanz wartet, bis die alte beendet ist (#131).
- Einstellungen: gleichzeitige Speichervorgänge konnten sich gegenseitig Einträge überschreiben; die Datei wird jetzt
  gesperrt und atomar geschrieben. Beim Schliessen der App werden ausstehende Zustände sofort gespeichert.

## [4.0.0] – 2026-10-10

### Neu
- DJ-Set, Grundlage: neues Modul `setplan.py` bewertet und optimiert die Reihenfolge eines Sets nach
  **Tonart** (Camelot-Rad: gleich, ±1, Paralleltonart, Energie-Sprung), **BPM** (auch Halb-/Doppeltempo,
  maximaler Sprung einstellbar) und **Energie** (Feld ENERGY, sonst aus dem BPM geschätzt), wahlweise mit
  Energieverlauf steigend, fallend oder Welle. Bis 15 Titel exakt, darüber schnelle Näherung; Start, Ende und
  gesperrte Positionen bleiben fest; Titel ohne Tonart/BPM ans Ende oder neutral; Note 0–100 je Übergang und
  für das ganze Set, vorher/nachher (#2).
- Neue Seite **DJ-Set** in der Seitenleiste: Titel aus dem Tagger übernehmen (Markierte, ganzer Ordner oder per
  Rechtsklick „Zum DJ-Set hinzufügen“), Energieverlauf, Gewichtung von Tonart/BPM/Energie, maximaler BPM-Sprung;
  Liste mit Tonart-Plakette, BPM, Energie (mit Soll-Wert) und je Übergang Ampel, Art des Tonartwechsels,
  BPM-Unterschied und Note; Gesamtnote mit Vorher/Nachher-Umschalter. Titel per **Ziehen** umsortieren oder
  **sperren** 🔒 (dann „Rest optimieren“); Tasten ↑/↓, Alt+↑/↓ verschieben, G sperren, Entf entfernen, Enter bzw.
  Doppelklick spielt. Rechts der **Weg durch das Camelot-Rad** und die **Energie-/BPM-Kurve**. Der Player folgt
  der Set-Reihenfolge, auch beim Überblenden. Set und Optionen werden gemerkt (#3).
- DJ-Set **exportieren**: M3U8-Playlist mit absoluten oder relativen Pfaden, **Rekordbox-XML** (Playlist mit
  BPM, Tonart, Dauer; Pfade mit Umlauten und Leerzeichen korrekt kodiert) und CSV für Excel mit
  Übergangsbewertung; dazu **Spurnummern in Set-Reihenfolge** schreiben (mit Vorschau, rückgängig machbar) (#4).
- Tagger: **Spalten mit Audio-Merkmalen** (Energy, Danceability …) über „Merkmale ▾“ ein- und ausblenden, nach
  ihnen sortieren; das Suchfeld versteht **Zahlenfilter** wie `energy>=70`, `Energie ≥ 70`, `dance<40` oder
  `bpm:120-128`, auch kombiniert mit Text. Einstellungen › Tagger: Skala der Merkmale in den Dateien wählbar
  (0–100 oder 0–10 wie Lexicon); angezeigt wird immer 0–100, beim Lesen und Schreiben wird umgerechnet (#11).
- Player: Titel per **Ziehen** laden – eine Zeile aus Tagger oder DJ-Set auf Player A oder B ziehen; ein Paar aus
  dem Vergleich fragt beim Ablegen nach links oder rechts. Die Player sind beim Ziehen markiert, das Ziel unter der
  Maus hervorgehoben (#105).
- README: neue Abschnitte „DJ-Set“ sowie Spalten und Filter der Audio-Merkmale; Oberflächentests für DJ-Set,
  Exporte, Merkmal-Spalten und Ziehen auf die Player (#5).

- Seitenleiste zeigt die **Anzahl Titel im DJ-Set** (#123).
- Snapshots: **⚑ Neue Baseline** – den aktuellen Stand oder einen vorhandenen Snapshot als neuen Ausgangspunkt
  setzen und ältere Snapshots löschen (Vorschau mit Anzahl und freiem Platz; angeheftete nur auf Wunsch). Die
  Baseline wird beim Aufräumen nie gelöscht (#124).

### Geändert
- Ziehen auf Player A/B spielt nur, wenn gerade kein Player läuft – sonst wird der Titel in Pause geladen, z. B. um
  in Player B vorzubereiten, während A spielt (#105).

### Behoben
- DJ-Set: Optimieren grosser Sets deutlich schneller (1500 Titel ca. 4 s statt 20 s, Zeitlimit wird eingehalten);
  der BPM-Unterschied gilt jetzt in beide Richtungen gleich (Prozent bezogen auf den kleineren Wert); Hinweis
  „Optimiere …“ während der Berechnung. Rekordbox-XML ohne Kommentarfeld, damit ein Import eigene Kommentare
  nicht überschreibt (#122).

## [3.5.0] – 2026-10-10

### Neu
- Seitenleiste in neuer Reihenfolge: **Tagger, Tag-Fixer, Vergleich, Snapshots, Sicherungen, Plugins,
  Einstellungen**; beim Start öffnet die zuletzt benutzte Seite (beim ersten Start der Tagger) (#88).
- Einstellungen: Kacheln in der Reihenfolge des Menüs, oben **Sprungmarken**; allgemeine Kacheln (Darstellung,
  Cache, Updates) am Anfang bzw. Ende (#87).
- Einstellungen › Vergleich: **Vorgaben beim Start** für Unterordner, Zuordnen nach, Anzeige, Unwichtige, Leere
  Felder und Cover; weicht der Vergleich ab, setzt der Knopf ⌂ „Standard“ in der Werkzeugleiste ihn zurück (#85).
- Einstellungen › Tagger: Vorgaben beim Start für automatisches Einlesen des Standardordners, Unterordner,
  Sortierung, Cover-Spalte und Herkunfts-Filter (#86).
- Updates: wählbar **nur offizielle Versionen** oder **auch Beta-Versionen**; die installierte App zeigt eine neue
  Version mit Hinweisen und lädt den passenden Installer; Kennzeichen „Beta“ bei der Versionsnummer (#89).
- **Versionshinweise** unter „Nach Update suchen“: installierte und neueste Version, Link zu GitHub, verständlicher
  Hinweis ohne Verbindung (#90).
- App-Fenster mit **TagStudio-Symbol** (Fenster und Taskleiste, auch im Quellcode-Start) und Titelleiste passend
  zum hellen bzw. dunklen Design (Windows 10/11) (#103).
- Beta-Releases verschwinden nach der finalen Version automatisch von der Releases-Seite (Tags bleiben) (#106).

### Geändert
- Projekt aufgeräumt (#106): `session.py` in Teile aufgeteilt (`session_player.py`, `session_snapshots.py`),
  ungenutzter Code und Übernahme alter Player-Einstellungen (bis 3.2.0) entfernt, Oberflächen-Tests im Browser als
  feste Testsuite (`tests/test_browser_ui.py`), Testdateien auch einzeln startbar, README neu gegliedert, ältere
  CHANGELOG-Einträge zusammengefasst.
- Klassische Oberfläche (`tagstudio.py`) eingefroren auf Stand 3.0 (Hinweis im Fenstertitel);
  `start_windows.bat`/`start_mac.command` starten jetzt die neue Oberfläche, die klassische über
  `start_classic_windows.bat`/`start_classic_mac.command` (#106).

### Behoben
- Tagger: leere Werte stehen beim Sortieren immer am Ende (auch absteigend); Sortierung nach Spur ohne Disc-Nummer
  funktioniert wieder.

## [3.4.0] – 2026-10-10

### Neu
- Player: **Bewertung** 0–5 Sterne (Feld POPM, vorhandene Frames werden angepasst, Zähler bleibt; `TXXX:FMPS_Rating`
  wird mitgeführt) und **Like** (♥, `TXXX:TAGSTUDIO` als JSON) – im Player, Tasten 0–5 und F (#95, #96).
- Tagger: Sterne und ♥ neben der Länge, auch für mehrere markierte Titel; kleine Anzeige in der Liste (#97).
- Player: **Live-Vorschau** – ein Klick auf einen Titel spielt ihn sofort (#91); **Doppelklick** spielt einen
  Titel, ohne Live-Vorschau wechselt ein einfacher Klick den laufenden Titel nicht mehr (#92).
- Player: **Überblenden** zum nächsten Titel (2–12 s, gleichmässige Kurve), nächster Titel ab Startpunkt/Anfang/
  erstem Cue, wahlweise schon nach 15 s … 2 min; nicht bei Wiederholen/Schleife (#94).
- Player **oben** als eigene, einklappbare Leiste (Shift+P) mit grösserer Wellenform (#68).
- **Player B:** zweiter Player zum Vorhören mit eigener Lautstärke, Wellenform und Ausgabegerät; Rechtsklick
  „In Player B laden“, Ziel A/B umschaltbar (Taste B) (#67).
- Player **abdocken** in ein eigenes Fenster (z. B. zweiter Bildschirm); Wiedergabe läuft weiter, Grösse und
  Position werden gemerkt, Schliessen dockt wieder an (#69).
- Einstellungen → Player: alle Player-Optionen, **Standard speichern / zurücksetzen / löschen** und „Nach dem Start:
  zuletzt benutzte oder Standard-Einstellungen“ (#93).

- Abgedockter Player zeigt auch **Player B** (wenn eingeschaltet) und je Player das **Cover**; Beschriftung A/B
  wählt das Ziel, Tasten im Fenster wirken auf den gewählten Player (#101).
- Überblenden: **Tempo angleichen** – der nächste Titel läuft während des Überblendens im BPM des laufenden
  (Tonhöhe bleibt, höchstens ±10 %, halbes/doppeltes Tempo erkannt) und gleitet danach in einstellbarer Zeit auf sein
  eigenes BPM zurück; angeglichenes BPM im Player hervorgehoben (#102).

- Abgedockter Player: grösseres Fenster (Standard 1280×380, mit Player B 1280×680; nie kleiner als die
  Mindestgrösse, auch wenn eine kleinere Grösse gemerkt ist) und grössere Schrift, Knöpfe, Wellenform und Cover.

### Geändert
- Ein einfacher Klick auf einen anderen Titel wechselt den laufenden Titel nur noch mit Live-Vorschau (#92).
- Player B nur noch mit „Player oben“ und dort unter Player A; gleich aufgebaut wie A (⏮/⏭, Cue-Sprünge,
  Wiederholen, A–B-Schleife, Cue-Marken, Bewertung, Tonart/BPM, Laufzeit/Rest/Länge, eigener Startpunkt, L/R im
  Vergleich, Menü mit Ausgabegerät), Platzhalter wo eine Funktion nur A hat – alles bündig (#68).
- Statt „→ A / → B“: Klick auf die Beschriftung **A** bzw. **B** ganz vorne wählt, worauf Markierung, Leertaste,
  Doppelklick und Tasten wirken (Taste B schaltet weiterhin um) (#68).
- Eingeklappte Player-Leiste: je Player eine Zeile mit Beschriftung, ▶/⏸, Titel und Restlaufzeit (#68).
- Eigenes Symbol für das Player-Menü (Regler) mit „Alle Player-Einstellungen …“ (#68).

## [3.3.1] – 2026-10-10

### Neu
- Vergleich: **Filter nach Herkunft** – Auswahl „Alle Herkünfte“ in der Werkzeugleiste (mit Anzahl je Herkunft des
  aktuellen Paars) oder Klick auf ein Kennzeichen; erneuter Klick zeigt wieder alle. Der Filter bleibt beim Wechsel
  des Paars erhalten (#99).

### Geändert
- Herkunft: weitere Felder erkannt – `TXXX:AnalysisDate` als beaTunes; `TXXX:FILEOWNER`, `LABEL`, `LABEL_URL`,
  `RELEASE_TIME`, `TRACK_URL`, `WWWAUDIOFILE`, `BPM`, `COMMENT`, `FILETYPE`, `INITIAL_KEY`, `ISRC`,
  `ORGANIZATION` und `YEAR` als Beatport; `TXXX:FMPS_Rating`, `Liking` und `ValenceArousal` als beaTunes
  (`BPMAlgorithm`, `MoodAlgorithm`, `fBPM`, `fBPM2`, `MOOD_AROUSAL`, `MOOD_VALENCE` waren schon erkannt) (#100).

## [3.3.0] – 2026-10-10

### Neu
- **Snapshots & Änderungsjournal** (Seite „Snapshots“): Ordner überwachen und ihren Tag-Zustand festhalten – byte-genau,
  ohne Audio, platzsparend (jeder ID3-Frame wird nur einmal gespeichert; unveränderte Titel kosten fast nichts).
  Das **Journal** zeigt zwischen einem Snapshot und jetzt (oder zwei Snapshots), welche Titel andere Programme
  geändert haben – geändert, neu, entfernt, **umbenannt** (erkannt am Audio-Inhalt), **Audio geändert** (nur Hinweis)
  oder nur anders gespeichert – mit allen Feldern alt/neu und Herkunfts-Kennzeichen; Filter und Suche.
  **Zurücksetzen** einzelner Felder oder ganzer Titel (Rückgängig möglich, geschrieben wird mit „Speichern“) oder
  **byte-genau** inklusive Binärfeldern (vorher Sicherung). Snapshots benennen, anheften, löschen; Aufräumen nach
  Regel (20 automatische + je einer pro Woche der letzten 12 Wochen, einstellbar); **Speicherplatz** je Snapshot,
  je Ordner und gesamt (auch in der Seitenleiste). Speicher mit Format-Version (für spätere Änderungen) (#52, #53, #61).
- **Täglicher Snapshot** beim ersten Start des Tages und **Frage beim Start** („n Titel seit … geändert – Journal
  ansehen / Snapshot erstellen / Später“), beides abschaltbar; Einstellungen „Snapshots“ (#54).
- **Schutz beim Speichern:** Hat ein anderes Programm (Mp3tag, Mixed In Key, beaTunes …) eine Datei geändert,
  seit TagStudio sie eingelesen hat, wird nicht mehr stillschweigend überschrieben. TagStudio zeigt die fremden
  Änderungen und bietet „Übernehmen und speichern“ (eigene Änderungen bleiben), „Trotzdem überschreiben“ oder
  „Abbrechen“ – erkennt auch Programme, die die Änderungszeit erhalten (#55).
- Snapshot-Aufträge schreiben ein **Protokoll** (`Logs/snapshots.log`, Knopf „Protokoll“ bei den Aufträgen): Start,
  Ende, Dauer, Anzahl Titel (neu eingelesen / unverändert übernommen), nicht lesbare Dateien, Aufräumen und am Ende
  den **Speicherplatz** – dieser Snapshot, der Ordner und alle Snapshots zusammen (#62).
- Player: **Stems an derselben Stelle umschalten** – bei Titeln mit Stems wählt der Knopf neben dem Titel (oder
  **S** / Shift+S) zwischen Original und den Spuren; die Wiedergabe läuft an der gleichen Position weiter. Spuren
  ohne eigene Tags zeigen Titel, Tonart und Tempo des Originals (#66).
- Player: **Restlaufzeit**, in den letzten 30 Sekunden **rot blinkend** (ohne Blinken bei „Bewegung reduzieren“) (#65).
- **Snapshots im Vergleich:** links oder rechts einen Snapshot wählen (📷 neben dem Pfad) – schreibgeschützt,
  übernehmen nur in Richtung der echten Dateien; Snapshot ↔ Snapshot nur ansehen. Neue Zuordnung **„Audio-Inhalt“**
  findet umbenannte und verschobene Titel. Im Journal öffnet ⇄ den Titel direkt im Vergleich (#56).
- Journal: **„vermutlich geändert von …“** je Titel aus der Herkunft der geänderten Felder, Filter nach Programm und
  Feld und **„Sichtbare auswählen“** für Sammel-Rückgängig (z. B. alle Tonart-Änderungen von Mixed In Key) (#57).
- **Ordnerüberwachung während TagStudio läuft:** alle 5 Minuten (einstellbar, 0 = aus) nur Grösse/Änderungszeit;
  Hinweis „n Titel extern geändert“ in der Fußleiste öffnet das Journal; eigene Speicherungen zählen nicht (#58).
- **Snapshot-Speicher verschieben** (Einstellungen › Snapshots › „Ändern …“): kopieren, prüfen, dann alten entfernen;
  in einem nicht leeren Ordner als `.tagstudio-snapshots`. Ordner werden auch nach der Weitergabe (anderer Pfad,
  anderer Rechner) über ihren Pfad relativ zum Speicher gefunden. Ein Speicher im eingelesenen Ordner wird zur
  Übernahme angeboten (#60).
- **Herkunfts-Kennzeichen:** offizielle ID3-Felder zeigen die Version (v2.3/v2.4) zusammen mit der Herkunft;
  benutzerdefinierte Felder (TXXX, GEOB, PRIV …) ohne bekannte Herkunft heissen „unbekannt“ (#74). **Eigene
  Kennzeichen** (Text und Farbe) je Herkunft in den Einstellungen, einzeln oder alle auf Standard zurücksetzbar (#75).
- **Listen-Cache mit Hash je Titel:** Tagger und Vergleich zeigen einen schon einmal eingelesenen Ordner sofort aus
  dem Cache (Dateien mit gleicher Grösse und Änderungszeit werden gar nicht geöffnet) und prüfen danach im
  Hintergrund jeden Titel über den Hash seiner Tag-Bytes – auch Änderungen von Programmen, die die Änderungszeit
  erhalten. Stand in der Statuszeile („prüfe 340 / 1'500 …“, „3 Titel ausserhalb geändert – neu gelesen“).
  Einstellungen › Cache: an/aus, Grösse, leeren (#70).
- **Mehrere überwachte Ordner** eindeutig: Farbe, Name (gleiche Namen mit übergeordnetem Ordner), Pfad, Grösse,
  letzter Snapshot; Anzeigename und Ordner änderbar, täglicher Snapshot je Ordner abschaltbar (#77).
- **Hinweis beim Start**, solange kein Ordner überwacht wird – „Ordner wählen …“ / „Später“ / „Nicht mehr
  fragen“ (#78).
- Tagger: **Cover-Spalte** (ein-/ausblendbar, gleiche Zeilenhöhe, Hover zeigt das Cover gross) (#73).
- **Hover-Infos** im App-Design statt der Browser-Tooltips: Überschrift, Feld/Wert-Zeilen, Tonart in
  Camelot-Farbe, BPM und Abweichungen hervorgehoben, Herkunfts-Kennzeichen mit Erklärung (#72).
- Player: **Titel wiederholen** (🔁, Taste R) und **A–B-Schleife** (Knopf bzw. Taste L: A setzen, B setzen,
  aufheben; Esc hebt auf) mit Markierung auf der Wellenform; bleibt beim Umschalten Original/Stems und L/R (#79).
- Einstellungen › Cache: **„Erstellen“** je Cache – Listen-Cache neu von der Platte aufbauen, fehlende
  **Wellenformen** berechnen, **Cover-Vorschauen** erzeugen; jeweils für alle geladenen Titel (Tagger und Vergleich),
  mit Fortschritt und Abbrechen – wahlweise **im Hintergrund** (Listen und Cover als Hintergrund-Auftrag,
  Wellenformen mit Fortschritt in der Fußleiste) (#80).
- **Standardordner** (Einstellungen › Vergleich: links und rechts; › Tagger): stehen beim Start in den Pfadfeldern;
  weicht ein Feld ab (z. B. nach einem Snapshot-Vergleich), trägt ⌂ neben dem Feld den Standard wieder ein.
  Snapshot-Angaben landen nicht mehr im Pfad-Verlauf (#84).
- Vergleich: **unwichtige Unterschiede deutlich markiert** – eigene Farbe für Zeile und geänderte Zeichen,
  Kennzeichen „unwichtig“ neben der Feld-ID (#83).
- Vergleich: **„Paar neu“** (Shift+F5) liest nur die beiden Dateien des aktuellen Paars neu – die übrige Liste
  bleibt, bei ungespeicherten Änderungen wird gefragt (#82).

### Behoben
- Hintergrund-Aufträge, die sehr schnell fertig waren, meldeten ihr Ende nicht.
- Player: Nach dem Einlesen eines anderen Ordners im Tagger konnte die Leertaste noch den alten Titel abspielen.
- Fehlermeldungen aus Aktionen, die nicht abgefangen wurden, erscheinen jetzt als Hinweis statt still zu verschwinden.
- Journal: ⇄ öffnet im Vergleich nur noch den einen Titel statt den ganzen Ordner neu einzulesen (#56).
- Journal → Vergleich: rechts erscheint immer der aktuelle Stand (einzelne Dateien kommen nie aus dem
  Listen-Cache), der Filter steht direkt auf „Unterschiede“ und „Unwichtige“ ist eingeschaltet (#81).

### Geändert
- **Schneller einlesen:** jede Datei wird nur noch einmal gelesen (der Fingerabdruck für den Konfliktschutz entsteht
  aus den gelesenen Bytes), die Stems-Suche kostet ohne Stems-Ordner fast nichts – 1'500 Titel ohne Cache etwa
  doppelt so schnell (#70).
- Vergleich: Version und Herkunft stehen klein neben der Feld-ID – der Feldname hat die volle Breite (#74).
- Tagger: Cover in der Breite der Feldnamen, Infos und Länge bündig mit den Eingabefeldern (#71).
- Die Option „v2.3/v2.4-Kennzeichen auch bei Standardfeldern“ (#40) heisst jetzt „ID3-Version bei offiziellen
  Feldern zeigen“ und ist standardmässig **an** (#74).
- Player neu geordnet: Tonart (Camelot-Kennzeichen plus musikalische und Open-Key-Schreibweise), BPM, Laufzeit,
  Restlaufzeit und Länge stehen jetzt in einem eigenen Block zwischen Wellenform und Startpunkt – die Wellenform hat
  die ganze Breite (#63). Der Statustext in der Fußleiste wird bei Platzmangel gekürzt (voller Text als Tooltip).
- **↑/↓ wechseln den Titel, egal wo der Fokus ist** – auch aus Suchfeldern, Tag-Feldern (Eingabe wird übernommen)
  oder der Wellenform; ausgenommen mehrzeilige Felder, Auswahl- und Zahlenfelder, Pfadfelder mit Verlauf, offene
  Dialoge und die Feldtabelle im Vergleich. Ohne laufende Wiedergabe wird nur die Markierung bewegt (#64).
- Lizenz: **GNU GPL v3** (`LICENSE`, auch im Installer bzw. DMG). Neu: Verhaltenskodex (`CODE_OF_CONDUCT.md`),
  Anleitung zum Mitmachen (`CONTRIBUTING.md`), Issue-Vorlagen (Fehler melden, Funktion vorschlagen, Plugin-Idee)
  und Vorlage für Pull Requests.

## [3.2.0] – 2026-10-09

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
- **Änderungs-Viewer** in den Sicherungen: Spalte „Geänderte Felder“ je Datei; Ansicht Feld für Feld
  „Vorher (Sicherung)“ ↔ „Jetzt“ mit Hervorhebung, Blättern durch geänderte Dateien, einzelne Datei wiederherstellen.
- **Installer** für Windows (`…-Windows-Setup.exe`, ohne Adminrechte) und macOS (`…-macOS-Apple-Chip.dmg`) –
  kein Python nötig. Gebaut von GitHub Actions bei jedem Versions-Tag, mit Selbsttest; erscheinen als GitHub-Release.

### Geändert
- Versionierung nach MAJOR.MINOR.PATCH mit einer einzigen Quelle (`version.py`), Abschnitt „Unveröffentlicht“ im
  CHANGELOG, `packaging/release.py`; Release-Workflow prüft Tag ↔ Version und veröffentlicht Beta-Tags als Vorabversion.
- Update-Knopf: wer noch auf dem Zweig `web-ui` steht, wird automatisch auf `main` umgestellt.
- Die klassische Oberfläche (`tagstudio.py`) nutzt den gemeinsamen Kern – Aussehen und Bedienung unverändert.
- Rückgängig/Wiederholen in `undo.py` ausgelagert.

## [2.9] – 2026-10-08

### Neu
- Git-Repository, automatische Tests (`tests/`) und GitHub Actions für Windows, macOS und Linux.

### Geändert
- Projekt umbenannt in **MarKusSXCH TagStudio** (Hauptdatei `tagstudio.py`, Einstellungen `~/.tagstudio.json`,
  Sicherungen `~/TagStudio/Sicherungen`, Cache `~/TagStudio/cache`).
- Einstellungen und Sicherungen der Vorgängerversion werden automatisch weiterverwendet.

## Frühere Versionen als „MP3 Tag Compare“ (1.0 – 2.8, 2026-10-04 bis 2026-10-08)

Zusammengefasst – die klassische Oberfläche (tkinter) entstand in diesen Versionen:
- **1.0:** zwei Ordner oder Dateien vergleichen, Standardfelder links ↔ rechts kopieren, eigene ID3-Bibliothek ohne
  Zusatzpakete.
- **2.0 – 2.4:** Oberfläche im Stil von Beyond Compare (Dunkel/Hell) mit allen ID3-Frames, Zeichen-Diff,
  Inline-Bearbeitung, Kontextmenü und Sammelkopie; Einlesen grosser Ordner mit Fortschritt; Tooltip mit Frame-ID;
  Tag-Fixer für Mehrfachwerte; leere Standardfelder einblenden; Splitter und Befehlsspalte (◀/▶, „Alles“, „Fehlende“).
- **2.5:** Praxistest mit 1'493 Dateien – BOM in Mehrfachwerten entfernt, DJ-Daten (GEOB: Serato, Mixed In Key,
  PlatinumNotes) lesbar zugeordnet, TIPL als „Rolle: Name“; Analyse-/DJ-Daten gelten als „unwichtig“.
- **2.6 – 2.8:** Rückgängig/Wiederholen, automatische Sicherung vor jedem Speichern mit Wiederherstellen,
  Speichern im Hintergrund; Cover-Vorschau, Suche und Filter in der Paarliste; klickbare URLs, zentrierte Dialoge.
