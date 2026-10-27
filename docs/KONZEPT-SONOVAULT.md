# Konzept: SonoVault-Integration

> Stand 25.10.2026 – Status **ENTSCHIEDEN** (SV1–SV4, Abschnitt 6), Umsetzung in 4.11.0 (Meilenstein #27), freigegeben
> vom User am 25.10.2026, 16:59 (`_1 bereit`).
> Issues: #253 (Grundlage) · #254 (Online-Metadaten) · #255 (Plattform-IDs) · #256 (Bibliothek abgleichen) ·
> #257 (Audio-Erkennung) · #258 (Entdecken) · #259 (später: Genre-Korrektur, Radio-Monitoring)

## 1. Was ist SonoVault?

[SonoVault](https://sonovault.now/docs) ist eine Musik-Metadaten-API (nach eigener Angabe über 93 Millionen Titel) mit
ISRC, ISWC, Künstler, Label, Genre/Subgenre, Release, Katalognummer, BPM, Tonart (drei Schreibweisen, mehrere
Quellen je Titel) und Plattform-IDs (Spotify, Apple Music, Beatport, Tidal, Discogs, MusicBrainz, YouTube). Dazu
Audio-Erkennung und Radio-/Stream-Monitoring. Die offiziellen SDKs liegen in der GitHub-Organisation
**rekordcloud** – derselbe Anbieter wie Lexicon, OpenKeyScan und MixID (#218). Eine Anfrage kann alle vier abdecken.

**Technik:** REST/JSON, Basis `https://api.sonovault.now`, Schlüssel im Header `x-api-key` (`svk_live_…`; Test-Schlüssel
`svk_test_…` liefert Musterdaten), E-Mail-Bestätigung nötig. OpenAPI: `https://sonovault.now/openapi.json`.

**Kosten (Seite „Pricing“, Beta-Angebot −50 %):**

| Tarif | Preis/Monat | Abfragen/Monat | pro Minute | Zusätzlich |
|---|---|---|---|---|
| Free | 0 € | 1 000 | 20 | Suche, ISRC, Plattform-Links, BPM/Tonart |
| Starter | 29 € (Beta 14.50 €) | 50 000 | 60 | Browse, Neuerscheinungen |
| Growth | 99 € (Beta 49.50 €) | 500 000 | 300 | |
| Scale | 249 € (Beta 124.50 €) | 5 000 000 | 1 000 | |

Fast alles kostet 1 Kredit; Bulk-Resolve 1 Kredit je Zeile; Audio-Erkennung 10 + 1 je MB (nur bezahlt); Stream-
Monitoring 29 € je Stream/Monat. Über dem Kontingent: 429, **keine automatischen Mehrkosten**. Energie, Tanzbarkeit und
Popularität sind laut Doku **nicht** Teil der öffentlichen API.

## 2. Nutzen für TagStudio

| Bereich | Nutzen | Endpunkte | Tarif | Issue |
|---|---|---|---|---|
| Grundlage | Dienst-Plugin mit Schlüssel, Integrationsfenster, Kontingent | `/v1/genres` (Test), alle | Free | #253 |
| Online-Metadaten | Titel, Künstler, Release, Label, Genre, Datum, Dauer, ISRC als Vorschlag; BPM/Tonart/ISWC nur als Vergleich | `tracks/search`, `tracks/isrc/:isrc`, `tracks/:id`, `tracks/iswc` | Free | #254 |
| Plattform-IDs | IDs nur anzeigen (nicht in Tags), „Auf Plattform öffnen“ (zu klären) | `tracks/links` | Free | #255 |
| Bibliothek abgleichen | nur Abgleich/Anzeige in Blöcken zu 100, kein Massen-Schreiben | `POST tracks/resolve` | Free (Kontingent beachten) | #256 |
| Audio-Erkennung | Titel ohne Tags erkennen (nach AcoustID) | `POST tracks/identify` | bezahlt | #257 |
| Entdecken | Neuerscheinungen gefolgter Labels/Künstler | `labels/:id/releases`, `artists/:id/releases`, `releases/new`, `tracks/browse` | teils bezahlt | #258 |
| Später | Genre-Korrektur melden, Radio-Monitoring | `tracks/:id/suggestions`, `streams` | bezahlt | #259 |

## 3. Nutzungsbedingungen (geprüft 24.10.2026, Terms „Last updated: October 19, 2026“)

[Terms](https://sonovault.now/terms), niederländisches Recht. Was das für TagStudio heisst:

| Regel | Folge für TagStudio |
|---|---|
| **Tags schreiben (§7):** nur „title, artist, release title, label, genre, release date, duration, and ISRC“, je Aufruf durch/für den Benutzer, für Dateien in seiner eigenen Bibliothek, nicht als „bulk data delivery“. Plattform-IDs ausdrücklich nicht. | Vorschläge zum Übernehmen **nur** für TIT2, TPE1, TALB, TPUB, TCON, Datum, TLEN, TSRC. **BPM, Tonart, ISWC, Katalognummer, Plattform-IDs und eine eigene `SONOVAULT_ID` dürfen nicht in die Datei** – nur anzeigen/vergleichen. |
| **Zwischenspeicher (§7):** nur flüchtig für eigene Anfragen, spätestens alle 30 Tage erneuern; Free-Tarif: nur dieser Zwischenspeicher. Bezahlte Tarife: Aufbewahren solange das Abo läuft (danach innert 30 Tagen löschen). | Cache im Plugin-Datenordner mit Ablaufdatum 30 Tage, nie exportieren, nicht in Snapshots/Sicherungen. Bei Abo-Ende: Cache leeren (mit Rückfrage). |
| **Kein Weitergeben (§4):** nichts weiterverkaufen, veröffentlichen, „in whole or in any part, however small“; keine konkurrierende Datenbank. | Keine Exporte der SonoVault-Daten (CSV, Listen, Melden …); Werte nur in der Vorschau. |
| **Schlüssel persönlich (§2, §9).** | Jeder Benutzer trägt seinen eigenen Schlüssel ein; TagStudio liefert keinen mit. |
| **Plattform-IDs (§8):** SonoVault gibt keine Rechte, Plattformen zu verlinken/einzubetten; nur mit eigener Beziehung zur Plattform. | „Auf Plattform öffnen“ vor der Umsetzung mit Rekordcloud klären. |
| **Audio hochladen (§5):** nur eigene bzw. berechtigte Aufnahmen; Aufbewahrung in der Datenschutzerklärung (noch zu lesen). | Audio-Erkennung nur für eigene Dateien, Hinweis im Dialog. |
| **Quellenangabe (§4, §8):** Hinweise nicht entfernen; Quellen gemäss „Data Sources & Attribution“. | Vorschau zeigt „Quelle: SonoVault“; Attribution-Seite vor der Umsetzung lesen. |
| **KI (§6):** Daten nicht zum Trainieren/Auswerten von KI. | Betrifft TagStudio nicht (keine KI-Anbindung). |

**Datenschutzerklärung** ([Privacy](https://sonovault.now/privacy), Stand 2.10.2026): Verantwortlich Rekordcloud B.V.
(Niederlande), Server bei Hetzner in der EU, Zahlung über Stripe, Google Analytics nur auf der Website.
- **Anfragen:** protokolliert werden Zeit, Endpunkt, **Parameter** (also Künstler, Titel, ISRC deiner Titel), Status und
  gelieferte Datensätze – **ohne festes Ablaufdatum**; IP-Adressen werden nach 90 Tagen entfernt. → Hinweis in den
  Plugin-Einstellungen: SonoVault sieht, welche Titel abgefragt werden.
- **Hochgeladenes Audio (Erkennung):** wird mit abgeleiteten Daten (Fingerabdrücke, Treffer, Logs) aufbewahrt, „for as
  long as reasonably necessary“ – keine feste Frist, Löschung nicht geregelt, Training nicht erwähnt. → #257 nur mit
  deutlichem Hinweis, nur kurzer Ausschnitt, nie automatisch; zuerst AcoustID (lädt kein Audio hoch, nur Fingerabdruck).
- **Rechte (DSGVO):** Auskunft, Berichtigung, Löschung, Export, Widerspruch innert 30 Tagen; Kontoschliessung löscht
  Personendaten innert 30 Tagen. Kontakt support@sonovault.now, Aufsicht: Autoriteit Persoonsgegevens.
- Seite „Data Sources & Attribution“ war nicht erreichbar → Quellenangabe vor der Umsetzung bei Rekordcloud erfragen.

**Folgen für die Issues:** #254 schreibt nur die erlaubten Felder, BPM/Tonart/ISWC nur als Vergleich in der Notiz.
#255 schreibt keine IDs in Tags. #256 (Bibliothek in Blöcken) ist als Massen-Schreiben nicht erlaubt → nur als
Abgleich/Anzeige (welche Titel stimmen nicht) oder gar nicht. #257 nur eigene Dateien.

## 4. Grundsätze (wie bei den anderen Diensten)

- **Nur Vorschläge:** Alles kommt in die Vorschau mit Häkchen; nichts wird ungefragt geschrieben. Vorhandene Werte nur
  mit Bestätigung überschreiben, Abgleich über `importsync` (wie Lexicon/beaTunes).
- **Nur erlaubte Felder schreiben:** siehe Abschnitt 3 – keine eigene Kennung in der Datei; die Zuordnung Datei ↔ SonoVault
  liegt höchstens im Zwischenspeicher (30 Tage).
- **Tonart/BPM:** nie schreiben; die Notiz vergleicht mit vorhandener Tonart (wie OpenKeyScan, `keyscan.py`:
  gleich/verwandt/abweichend) – SonoVault liefert Tonarten mehrerer Quellen (`keys`).
- **Kosten:** Kontingent aus `RateLimit-*` auf der Karte; Bulk-Abgleich und Audio-Erkennung zeigen die Kredite vorher und
  starten nur nach Bestätigung; 429 nie wiederholen, sondern melden.
- **Zugangsdaten:** Schlüssel verschlüsselt im Plugin (`servicekit.save_keys`), nie anzeigen, protokollieren oder exportieren.
- **Datenschutz:** Audio-Erkennung lädt Audio hoch → nur Ausschnitt (30–60 s, mono 16 kHz), nur auf Wunsch.
- **Drosselung:** gemeinsame Drosselung `onlinematch` (Free: 20/min).

## 5. Reihenfolge (Vorschlag)

1. #253 Grundlage + #254 Online-Metadaten + #255 Plattform-IDs – zusammen ein Paket, mit dem Free-Tarif nutzbar.
2. #256 Bibliothek abgleichen – nur als Abgleich/Anzeige (Massen-Schreiben nicht erlaubt), Kontingent beachten.
3. #258 Entdecken – passt zum Modul Entdecken (Deezer/Beatport).
4. #257 Audio-Erkennung – nur mit bezahltem Tarif sinnvoll.
5. #259 – nur bei Bedarf.

## 6. Entscheide (User 25.10.2026, 16:54) – Umsetzung in 4.11.0 (Meilenstein #27, #253–#258)

| ID | Frage | Entscheid |
|---|---|---|
| SV1 | Tarif | **Free.** TagStudio verwaltet die Anfragen: Zähler je Monat (aus `RateLimit-*` und eigenem Zähler), Rest auf der Plugin-Karte, Warnung vor dem Überschreiten, Bulk-Abgleich (#256) nur innerhalb des Kontingents bzw. in Etappen über mehrere Monate. |
| SV2 | Audio-Erkennung (#257) | **Optional**, mit Hinweis, dass dafür Kredits gekauft werden müssen und was es kostet (10 + 1 je MB) – auch im Free-Tarif anbieten. |
| SV3 | „Auf Plattform öffnen“ (#255) | IDs nur anzeigen; Verlinken erst nach Rückfrage bei Rekordcloud. |
| SV4 | Vorrang in „Online-Metadaten“ | Nach Beatport und MusicBrainz, vor Deezer und iTunes. |

## 6b. Umsetzung #253–#255 (25.10.2026)

- **Plugin `plugins/sonovault`** (1.0, `min_app` 4.11.0): Schlüssel verschlüsselt (`servicekit`), Integrationsfenster mit
  22 Endpunkten (3 vollständig, 1 teilweise), eigener Abruf `api_request` – kostenpflichtige Endpunkte (Identify,
  Browse, Neuerscheinungen, Streams) ruft der Tester nicht auf.
- **Anfragen-Verwaltung (SV1):** `quota.json` im Datenordner (Monat, verbraucht, Kontingent – Standard 1000, unter
  „Schlüssel …“ änderbar, Kopfzeilen `RateLimit-*`/`*credit*` zur Info). Jede gesendete Anfrage zählt, Antworten aus dem
  Zwischenspeicher nicht. Ab 90 % Warnung im Protokoll, bei erreichtem Kontingent kein Abruf mehr (HTTP 429 lokal).
  Eigene Drosselung 3.05 s (20/min), **429 nie wiederholt** (nicht über `onlinematch.Client`).
- **Zwischenspeicher:** je URL (ohne Schlüssel) im Datenordner `cache/`, höchstens 30 Tage, abgelaufene werden beim
  Lesen bzw. vor „Plattform-IDs“ entfernt; Aktion „Zwischenspeicher leeren“ mit Häkchen.
- **Online-Metadaten (#254, SV4):** Quelle `sonovault` nach MusicBrainz und Discogs, vor Deezer/iTunes (Online-Metadaten
  2.2). Treffer tragen `allowed_fields` (TIT2, TPE1, TALB, TPUB, TCON, TDRC, TSRC, TLEN) – alles andere filtert
  `_field_values`; `compare` (BPM, Tonart, Anzahl Quellen) erscheint nur in der Notiz (`compare_note`, Tonart-Vergleich
  wie OpenKeyScan). Keine IDs, keine Katalognummer, kein Cover. Im Protokoll (Datei) stehen keine SonoVault-Werte.
- **Plattform-IDs (#255, SV3):** Tagger-Aktion „Plattform-IDs anzeigen (SonoVault) …“ → Ergebnis-Tabelle
  (`res["table"]`, neu im Kern: `pluginResultTable`), nicht im Protokoll, nie in Tags, keine Links.
- **Bibliothek abgleichen (#256):** Tagger-Aktion „Mit SonoVault abgleichen (Bibliothek) …“ – `resolve_plan` (braucht
  Anfrage / im Zwischenspeicher / ohne Künstler+Titel), ohne Häkchen nur Kostenvorschau; `resolve_run` schickt
  höchstens min(Eingabe, Rest des Kontingents) Zeilen in Blöcken zu 100 (`input_type` `isrc` bzw. `track_name`),
  gezählt werden die gesendeten Zeilen ausser `skipped_no_credits`. Ergebnis je Titel 30 Tage im Zwischenspeicher
  (auch „nicht gefunden“); Anzeige der Abweichungen (ISRC, Label, Genre, Album, Jahr, Tonart) als Tabelle – nie
  Massen-Schreiben (§7). POST über `onlinematch.http_post` (neu).
- **Entdecken (#258):** `discover.run(…, sv=…)` mit `discover_releases(ctx, kind, name, days)` aus dem Plugin – Suche
  nach dem Namen (genaue Übereinstimmung, 30 Tage zwischengespeichert), dann `…/{id}/releases?from=…&limit=50`
  (20 Stunden). Quelle `sonovault` in `follow.sources`, standardmässig aus, nur mit Schlüssel wählbar. **Nie bei der
  täglichen Suche** (`disc_auto` übergibt kein `sv`), damit keine Kredite unbemerkt verbraucht werden; bei 401/429 lässt
  der Lauf die übrigen SonoVault-Abfragen aus. Einträge `sonovault:rel:<id>` ohne Link; `discover.purge_sonovault`
  entfernt sie nach 30 Tagen (auch gemerkte), `export_rows` lässt sie aus. `/v1/releases/new` und `/v1/tracks/browse`
  (bezahlt) nicht umgesetzt.
- **Audio-Erkennung (#257, SV2):** Tagger-Aktion „Audio erkennen (SonoVault, kostenpflichtig) …“ – auch im Free-Tarif
  angeboten, mit Hinweis auf gekaufte Kredite und Kosten (10 + 1 je MB, Schätzung je Länge im Auswahlfeld) sowie
  Datenschutz (Aufbewahrung ohne Frist). Standard: nur Titel ohne brauchbaren Titel/Künstler; ohne Häkchen nur
  Kostenvorschau. `excerpt`: FFmpeg, Mitte des Titels, 30/45/60 s, mono 16 kHz, 48 kbit/s, **ohne Tags**
  (`-map_metadata -1`); `identify` reserviert die Kosten, zählt bei Ablehnung (402/403/429) nichts. Treffer
  (`matches`/`results` mit `track` und `confidence`, tolerant gelesen) → Vorschläge nur erlaubter Felder.
- **Antwortformat:** Feldnamen nach den offiziellen SDKs von Rekordcloud (`sonovault-python`, `sonovault-mcp`);
  Release-Felder (Album, Label, `release_date`) werden tolerant gelesen – beim ersten echten Test im API-Tester prüfen.
  Laut SDK liefert die öffentliche API BPM und Tonart (`bpm`, `key_alphanumeric`, `keys`), aber keine Energie.

## 6a. Offen / vor der Umsetzung klären

- ~~Nutzungsbedingungen~~, ~~Datenschutz~~ → geprüft, siehe Abschnitt 3. Offen: Seite „Data Sources & Attribution“ (nicht
  erreichbar), Verlinken auf Plattformen.
- Tarif des Users (Free reicht für Einzelabfragen, nicht für einen Bibliotheksabgleich).
- Anfrage an Rekordcloud zusammen mit MixID (#218): offizieller Zugang, Kontingent für TagStudio-Nutzer.
- Doppelte Quellen: Verhältnis zu MusicBrainz/Discogs/Beatport bei gleichen Feldern (Vorrang in „Online-Metadaten“).

## 6c. Durchsicht 27.10.2026 – was noch offen ist

Doku und Website mit der Umsetzung verglichen (Terms unverändert „Last updated: October 19, 2026“):
- **Integrationsfenster veraltet** (fehlen: `GET /v1/suggestions`, Streams-Unterendpunkte, Webhooks; geänderte Antworten
  bei identify und artists/labels) → **#379**.
- **Releases** (`/v1/releases/search`, `/v1/releases/{id}`, Free) bisher ungenutzt → Idee **#380**.
- **Neuerscheinungs-Feed und Browse** (bezahlt) nicht umgesetzt (SV1 Free) → Idee **#381**, nur bei bezahltem Tarif.
- **Fragen an Rekordcloud** (Verlinken SV3, Quellenangabe – Seite „Data Sources“ gibt es nicht, BPM/Tonart in Tags,
  Kontingent) → **#382**, gemeinsam mit der MixID-Anfrage (#218).
- **Genre-Korrektur, Radio-Überwachung** → weiter Idee **#259** (neue Endpunkte dort vermerkt).
- Nicht relevant für TagStudio: Bulk Lookup im Dashboard, MCP-Server, Royalty-Seiten.
- Neu laut Terms §11: Daten nach einer Takedown-/Korrektur-Meldung innert 7 Tagen löschen – betrifft TagStudio nur über
  den Zwischenspeicher (höchstens 30 Tage, „Zwischenspeicher leeren“ vorhanden).

## 6d. Eigene Felder `TXXX:SONOVAULT_*` (#383, Entscheid User 27.10.2026, 08:41)

- Muster freigegeben: `TXXX:SONOVAULT_TITLE`, `_ARTIST`, `_RELEASE`, `_LABEL`, `_GENRE`, `_RELEASE_DATE`, `_DURATION`,
  `_ISRC` und `TXXX:SONOVAULT_DATE` (Abrufdatum) – Herkunft „SonoVault“ über `plugin.json › fields` (`TXXX:SONOVAULT*`).
- Nur diese Felder (Terms §7). `_BPM`, `_KEY`, `_ISWC`, `_CATALOGNUMBER` erst nach Zusage von Rekordcloud (#382);
  Plattform-IDs und eine SonoVault-ID nie.
- Schreiben nur über die Vorschau mit Häkchen, je Titel, eigene Dateien; zusätzlich zu den normalen Vorschlägen.

## 7. Eigener Katalog statt Dienst (#260, Entscheid User 24.10.2026)

Ein eigener Dienst wie SonoVault wird **nicht** gebaut (alle drei Punkte vom User am 24.10.2026, 11:14 bestätigt). Geplant ist **nur lokale Ausführung**: ein Katalog in TagStudio
(SQLite im Benutzerordner) aus freien Quellen (MusicBrainz-Kerndaten, Discogs-Dumps, Wikidata – CC0) für die eigene
Bibliothek und gefolgte Labels/Künstler, ergänzt um eigene Analysen (Tonart #245, später #9). Kein Server, keine
SonoVault-Daten als Grundlage (Terms §4). SonoVault bleibt optionale Zusatzquelle.


**Weitere Entscheide (User 24.10.2026, 11:16) – nur Konzept, noch keine Umsetzung:**
- **Felder:** möglichst alle Felder, die TagStudio heute schon in die Tags schreibt (Titel, Künstler, Album/Release,
  Label, Katalognummer, ISRC, Genre/Stil, Datum, Dauer, Plattform-IDs und -Links aus MusicBrainz/Discogs, BPM, Tonart,
  Energie und weitere Analysewerte aus eigener Analyse) – jeweils mit Quelle und Abrufdatum im Katalog.
- **Aktualisierung:** jederzeit **von Hand** („Katalog aktualisieren“), dazu ein **Zeitplan**, den der Benutzer selbst
  festlegt (z. B. aus, täglich, wöchentlich, monatlich, beim Start); läuft als Hintergrund-Auftrag mit Fortschritt
  und Abbrechen, schreibt nie ungefragt in Dateien.
