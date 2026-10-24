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
| Online-Metadaten | ISRC, ISWC, Label, Genre, Release, Katalognummer, BPM/Tonart als Vorschlag | `tracks/search`, `tracks/isrc/:isrc`, `tracks/:id`, `tracks/iswc` | Free | #254 |
| Plattform-IDs | IDs/Links aller Plattformen, „Auf Plattform öffnen“ | `tracks/links` | Free | #255 |
| Bibliothek abgleichen | bis 100 Titel je Anfrage, Hintergrund, Kostenvorschau | `POST tracks/resolve` | Free (Kontingent beachten) | #256 |
| Audio-Erkennung | Titel ohne Tags erkennen (nach AcoustID) | `POST tracks/identify` | bezahlt | #257 |
| Entdecken | Neuerscheinungen gefolgter Labels/Künstler | `labels/:id/releases`, `artists/:id/releases`, `releases/new`, `tracks/browse` | teils bezahlt | #258 |
| Später | Genre-Korrektur melden, Radio-Monitoring | `tracks/:id/suggestions`, `streams` | bezahlt | #259 |

## 3. Grundsätze (wie bei den anderen Diensten)

- **Nur Vorschläge:** Alles kommt in die Vorschau mit Häkchen; nichts wird ungefragt geschrieben. Vorhandene Werte nur
  mit Bestätigung überschreiben, Abgleich über `importsync` (wie Lexicon/beaTunes).
- **Eigene Kennung:** `TXXX:SONOVAULT_ID`, Herkunft „SonoVault“ (Builtin-Regel `TXXX:SONOVAULT*`). Offizielle Felder
  (TSRC, TPUB, TCON, TBPM, TKEY …) bleiben offizielle Felder.
- **Tonart/BPM:** nur leere Felder vorausgewählt; Notiz vergleicht mit vorhandener Tonart (wie OpenKeyScan, `keyscan.py`:
  gleich/verwandt/abweichend) – SonoVault liefert Tonarten mehrerer Quellen (`keys`).
- **Kosten:** Kontingent aus `RateLimit-*` auf der Karte; Bulk-Abgleich und Audio-Erkennung zeigen die Kredite vorher und
  starten nur nach Bestätigung; 429 nie wiederholen, sondern melden.
- **Zugangsdaten:** Schlüssel verschlüsselt im Plugin (`servicekit.save_keys`), nie anzeigen, protokollieren oder exportieren.
- **Datenschutz:** Audio-Erkennung lädt Audio hoch → nur Ausschnitt (30–60 s, mono 16 kHz), nur auf Wunsch.
- **Drosselung:** gemeinsame Drosselung `onlinematch` (Free: 20/min).

## 4. Reihenfolge (Vorschlag)

1. #253 Grundlage + #254 Online-Metadaten + #255 Plattform-IDs – zusammen ein Paket, mit dem Free-Tarif nutzbar.
2. #256 Bibliothek abgleichen – sobald klar ist, wie viel Kontingent nötig ist.
3. #258 Entdecken – passt zum Modul Entdecken (Deezer/Beatport).
4. #257 Audio-Erkennung – nur mit bezahltem Tarif sinnvoll.
5. #259 – nur bei Bedarf.

## 5. Offen / vor der Umsetzung klären

- Nutzungsbedingungen: Speichern der Werte in Tags und lokales Zwischenspeichern erlaubt? (Pricing-Seite nennt keine
  Regeln, die Terms selbst sind noch zu lesen.)
- Tarif des Users (Free reicht für Einzelabfragen, nicht für einen Bibliotheksabgleich).
- Anfrage an Rekordcloud zusammen mit MixID (#218): offizieller Zugang, Kontingent für TagStudio-Nutzer.
- Doppelte Quellen: Verhältnis zu MusicBrainz/Discogs/Beatport bei gleichen Feldern (Vorrang in „Online-Metadaten“).
