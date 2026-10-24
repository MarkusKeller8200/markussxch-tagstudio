# Konzept: SonoVault-Integration

> Stand 24.10.2026 – Entwurf auf Wunsch des Users. Status **Idee**: keine Umsetzung ohne Freigabe (`_1 bereit`).
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

## 6. Offen / vor der Umsetzung klären

- ~~Nutzungsbedingungen~~, ~~Datenschutz~~ → geprüft, siehe Abschnitt 3. Offen: Seite „Data Sources & Attribution“ (nicht
  erreichbar), Verlinken auf Plattformen.
- Tarif des Users (Free reicht für Einzelabfragen, nicht für einen Bibliotheksabgleich).
- Anfrage an Rekordcloud zusammen mit MixID (#218): offizieller Zugang, Kontingent für TagStudio-Nutzer.
- Doppelte Quellen: Verhältnis zu MusicBrainz/Discogs/Beatport bei gleichen Feldern (Vorrang in „Online-Metadaten“).
