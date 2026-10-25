# Konzept: DJ-Musikplattformen – Vergleich, API und Workflow

**Stand:** 15.10.2026 (zusammengeführt mit der Übersicht „Tag-Programme und Musik-Plattformen“ vom 12.10.2026)  
**Dokumenttyp:** Detailkonzept für TagStudio  
**Status:** Konzept / Evaluationsgrundlage; API-Zugänge, Downloadrechte, Verfügbarkeit und Preise vor Implementierung prüfen  
**Quellen:** `2026_10_13_Konzept_IDEE_DJ_Plattformen_Vergleich.pdf` (6 Seiten) sowie die recherchierte Übersicht mit Kosten (Abschnitt 2.1 und Anhang A; Export als [Word](Tag-Programme-und-Musik-Plattformen.docx) / [PDF](Tag-Programme-und-Musik-Plattformen.pdf))  
**Übergeordnetes Konzept:** [KONZEPT-PRODUKT-ARCHITEKTUR.md](KONZEPT-PRODUKT-ARCHITEKTUR.md)  
**Verwandte Konzepte:** [KONZEPT-VORBEREITEN.md](KONZEPT-VORBEREITEN.md), [KONZEPT-MUSIKANALYSIEREN.md](KONZEPT-MUSIKANALYSIEREN.md), [KONZEPT-PLUGINS.md](KONZEPT-PLUGINS.md)

> **Einordnung:** Dieses Dokument bildet den Inhalt des PDF vom Oktober 2026 strukturiert in Markdown ab. Die Anbieter- und API-Angaben sind Aussagen des Ausgangsdokuments und wurden für diese Übertragung **nicht erneut extern verifiziert**. Ein als verfügbar beschriebener Dienst bedeutet weder automatisch einen frei erhältlichen privaten API-Schlüssel noch eine Download-Erlaubnis. Plattformen, Partnerprogramme, Lizenzbedingungen und Schnittstellen können sich ändern.
>
> **Abgrenzung:** Hier geht es um **Musikshops, Streamingdienste, DJ-Pools und deren Schnittstellen**. Die Interoperabilität mit DJ-Software wie DJ.Studio, Lexicon, Mixo, Engine DJ, Serato, VirtualDJ, Traktor und rekordbox ist im [übergeordneten Produkt- und Architekturkonzept](KONZEPT-PRODUKT-ARCHITEKTUR.md) beschrieben. TagStudio soll vorhandene Werkzeuge ergänzen, nicht ersetzen.

## 1. Ziel und Leitfragen

Bei einer Integration von Musikplattformen sind laut Ausgangsdokument drei Fragen entscheidend:

1. **Musikkatalog und Metadaten:** Lassen sich Artist, Titel, Remix, Label, ISRC, BPM und weitere Informationen abrufen?
2. **Kauf und Datei-Download:** Können Tracks als MP3, FLAC, WAV oder AIFF gekauft und als lokale Dateien gespeichert werden?
3. **API-Integration:** Darf TagStudio Plattformen automatisiert durchsuchen, Metadaten übernehmen und rechtmässig verfügbare Downloads verwalten?

Es ist zwischen **öffentlich dokumentierter API**, **eingeschränktem bzw. Partnerzugang** und **gewöhnlichem Website-Kauf oder Website-Download** zu unterscheiden. Ein Download innerhalb eines Streaming-Abonnements ist **keine frei nutzbare Audiodatei**. Bei DJ-Pools gelten eigene Lizenzbedingungen.

## 2. Plattformvergleich

Die Angaben in dieser Tabelle stammen aus Abschnitt 1 des PDF (Seiten 1–2); sie stellen keine aktuelle Zusage des jeweiligen Anbieters dar.

| Plattform | Kaufen | Datei-Download | Streaming | Schwerpunkt |
|---|---|---|---|---|
| Beatport | Ja | Ja | Ja | Electronic, House, Techno, Open Format |
| Traxsource | Ja | Ja | Nein | House, Deep House, Afro |
| Bandcamp | Ja | Ja | Eingeschränkt | Independent, Underground |
| Qobuz | Ja | Ja | Ja | Hi-Res, alle Genres |
| Volumo | Ja | Ja | Nein | Electronic, Underground |
| Mixupload | Teilweise | Teilweise | Ja | Remixe, DJ-Mixes |
| 7digital | Ja | Ja | Nein | Pop, Rock, Electronic |
| iTunes Store | Ja | Ja | Nein | Mainstream, alle Genres |
| Amazon Music | Regional (auch Schweiz, Hinweis User 25.10.2026) | Bei Kauf | Ja | Mainstream |
| SoundCloud | Nein | Bei Freigabe | Ja | Remixe, Bootlegs |
| Spotify | Nein | Kein freier Download | Ja | Alle Genres |
| TIDAL | Nein | Kein freier Download | Ja | Hi-Fi, Mainstream |
| Apple Music | Nein | Kein freier Download | Ja | Mainstream |
| Deezer | Nein | Kein freier Download | Ja | Alle Genres |
| DJcity | Pool-Abo | Ja | Vorschau | DJ-Edits |
| BPM Supreme | Pool-Abo | Ja | Vorschau | Remixe, DJ-Edits |
| ZIPDJ | Pool-Abo | Ja | Vorschau | Electronic, House |
| Beatsource | Ja | Ja | Ja | Open Format (Hip-Hop, Latin, Pop) |
| Juno Download | – | nur Re-Download | Nein | **seit 1. Juni 2026 geschlossen** |

### 2.1 Kosten und Kurzbeschreib (recherchiert am 12.10.2026)

Preise von Hersteller- oder Testseiten, in der Währung der Quelle; ändern sich oft und je nach Land. Plattformen aus der
Tabelle oben ohne Eintrag hier (Qobuz, Volumo, Mixupload, 7digital, DJcity, ZIPDJ) sind noch **nicht preisgeprüft**.

| Plattform | Kurzbeschreib | Kosten |
|---|---|---|
| [Beatport](https://www.beatport.com) | Grösster Shop für elektronische Musik; TagStudio-Plugin für Metadaten, Käufe, Download | Kauf je Titel; Streaming [Essential 10,99 / Advanced 15,99 / Professional 29,99 USD pro Monat](https://thedjmixtape.com/beatport-streaming-review/) – erst ab Advanced in DJ-Programmen |
| [Beatsource](https://www.beatsource.com) | Schwester-Shop von Beatport für Open Format | Kauf je Titel; Streaming [Standard 12,99, Pro+ 34,99 USD/Monat](https://www.digitaldjtips.com/best-music-streaming-services/) |
| [Traxsource](https://www.traxsource.com/) | House, Soulful, Deep House, Techno | Kauf je Titel, meist 1,99 USD (teils 2,49); kein Abo |
| [Juno Download](https://www.digitaldjtips.com/juno-download-shuts-down-after-20-years/) | ehemaliger britischer Shop – **seit 1. Juni 2026 geschlossen** | – |
| [Bandcamp](https://bandcamp.com) | Künstler und Labels verkaufen direkt | Preis legt der Künstler fest, teils „Name your price“ |
| [BPM Supreme](https://bpmmusic.io/supreme) | Record Pool mit DJ-Edits (Open Format, Latin, Hip-Hop) | Abo; Preise nur nach Anmeldung sichtbar |
| [Spotify](https://www.spotify.com/ch-de/premium/) | Streaming; in Serato, rekordbox, djay | Free mit Werbung; Premium 15,95 CHF/Monat (Duo 21,95, Family 26,95, Student 8,95) |
| [Deezer](https://www.deezer.com) | Streaming; Quelle für „Online-Metadaten“ und „Entdecken“ | Premium ca. 11,99 USD/Monat; API kostenlos |
| [Apple Music](https://www.apple.com/apple-music/) | Streaming; in djay, Serato, rekordbox, Engine | ca. 10,99 USD/Monat |
| [Amazon Music](https://music.amazon.com) | Streaming; in Denon-/Numark-Geräten. Verkauft auch MP3-Downloads, laut User auch in der Schweiz (meist 256 kbps) | Unlimited ca. 10,99 USD/Monat (Prime); Kauf je Titel |
| [TIDAL](https://tidal.com) | Streaming in hoher Qualität mit DJ-Erweiterung | 10,99 + 9 USD DJ-Erweiterung = 19,99 USD/Monat |
| [SoundCloud](https://soundcloud.com) | Streaming und Künstlerplattform | Go 4,99 (ohne DJ-Nutzung), Go+ 10,99, DJ 19,99 USD/Monat |
| [MusicBrainz](https://musicbrainz.org) | Offene Musikdatenbank; Quelle für Picard und das TagStudio-Plugin | kostenlos |
| [AcoustID](https://acoustid.org/webservice) | Erkennung per Audio-Fingerabdruck | kostenlos für nichtkommerzielle Nutzung |
| [Discogs](https://www.discogs.com) | Datenbank und Marktplatz (Labels, Katalognummern) | Datenbank/API kostenlos (eigenes Token) |
| [Last.fm](https://www.last.fm/pro) | Statistik und Genre-Tags | Free; Pro 4,99 USD/Monat oder 49,99 USD/Jahr |

**Wichtig:** Bei einer Downloadfreigabe ist zusätzlich zu klären, ob eine Datei ausschliesslich über die offizielle Website oder auch über eine dokumentierte API bezogen werden darf.

## 3. API-Verfügbarkeit: Metadaten und Downloads

### 3.1 Vergleich der Schnittstellen

**Legende:** `Ja` = im PDF als unterstützt eingestuft; `Eingeschränkt / Partner` = nicht allgemein zugänglich; `Nein` = im PDF als nicht verfügbar eingestuft; `Unklar` = nicht ausreichend dokumentiert. Diese Klassifikation sagt noch nichts darüber aus, **welche individuellen Zugangsdaten** erhältlich sind oder welche API-Nutzungsrechte konkret gewährt werden.

| Plattform | API für Titelsuche / Metadaten | Download über API | Bewertung aus dem PDF |
|---|---|---|---|
| Beatport | Eingeschränkt / Partner | Nein | Sehr interessant für DJ-Metadaten |
| Traxsource | Unklar | Unklar | Manueller Kauf sinnvoll |
| Bandcamp | Eingeschränkt / Partner | Nein | Gut für lokale Musikdateien |
| Qobuz | Eingeschränkt / Partner | Eingeschränkt / Partner | Interessant bei Partnerzugang |
| Volumo | Unklar | Unklar | Weitere Abklärung nötig |
| Mixupload | Unklar | Unklar | Weitere Abklärung nötig |
| 7digital / MassiveMusic | Eingeschränkt / Partner | Eingeschränkt / Partner | Besonders interessant |
| iTunes Store | Ja | Nein | Gut für Katalogsuche |
| Amazon Music | Eingeschränkt / Partner | Nein | Eingeschränkt |
| SoundCloud | Ja | Eingeschränkt | Sehr interessant |
| Spotify | Ja | Nein | Gut für Metadaten |
| TIDAL | Eingeschränkt / Partner | Nein | Eingeschränkt |
| Apple Music | Eingeschränkt / Partner | Nein | Gut für Katalogdaten |
| Deezer | Ja | Nein | Gut für Metadaten |
| DJcity | Unklar | Unklar | Manueller Pool-Download |
| BPM Supreme | Unklar | Unklar | Manueller Pool-Download |
| ZIPDJ | Unklar | Unklar | Manueller Pool-Download |

Die Tabelle betrifft Integrationsmöglichkeiten **für Drittentwickler**. Interne, nicht veröffentlichte Schnittstellen einer Website begründen keinen allgemeinen API-Zugang und keine Erlaubnis für einen automatisierten Download.

### 3.2 Zentrale APIs im Detail

#### Beatport API v4

- Katalogsuche nach Tracks, Artists, Releases, Labels und Genres sowie DJ-relevanten Merkmalen wie BPM und Tonart.
- Die Dokumentation ist über das Partnerumfeld zugänglich; **produktiven Zugang und konkrete Berechtigungen klären**.
- Das PDF nennt keinen allgemein verfügbaren Kauf-/Download-Endpunkt.
- Quellen aus dem PDF: [Partnerportal](https://partnerportal.beatport.com/hc/en-us), [API-v4-Dokumentation](https://api.beatport.com/v4/docs/).

#### SoundCloud API

- Im Ausgangsdokument als offizielle REST-API mit OAuth 2.1 beschrieben.
- Suche und Trackinformationen; Angaben wie BPM und Tonart nur, soweit beim jeweiligen Track vorhanden.
- Vorhandene Zugangsdaten können eine Integration erleichtern, ersetzen aber keine Berechtigungs- und Nutzungsprüfung.
- **Kein allgemeiner Downloadzugang:** Streaming-Endpunkte dürfen nicht als Downloadersatz behandelt werden. Das PDF weist ausdrücklich auf Einschränkungen für das Herunterladen und Speichern über die öffentliche API hin.
- Empfehlung aus der Quelle: **API für Suche und Metadaten**, bei vom Künstler freigegebenen Downloads **Link zur offiziellen Trackseite**.
- Quelle aus dem PDF: [SoundCloud API-Dokumentation](https://developers.soundcloud.com/docs/).

#### 7digital / MassiveMusic API

- Professionelle Schnittstellen für Katalog, Metadaten und die lizenzierte Auslieferung von Audiodateien.
- Das PDF beschreibt Möglichkeiten, bereits gekaufte Tracks über entsprechend autorisierte Schnittstellen abzurufen.
- Zugang ist auf lizenzierte Integrationspartner ausgerichtet; **nicht automatisch für normale Shopkunden verfügbar**.
- Potenzial für eine spätere rechtmässige Downloadintegration bei entsprechendem Vertrag.
- Quelle aus dem PDF: [MassiveMusic API-Referenz](https://docs.massivemusic.com/reference/introduction).

#### Spotify Web API

- Track-, Album-, Artist- und ISRC-Daten; zudem Playlist-Funktionen.
- Geeignet für Trackidentifikation und Abgleich der bestehenden Musiksammlung.
- **Kein Audio-Download über die API**; Zugangsbedingungen und zulässige Datennutzung prüfen.
- Quelle aus dem PDF: [Spotify Web API](https://developer.spotify.com/documentation/web-api).

#### Bandcamp API

- Im PDF als auf Labels und Fulfillment-Partner ausgerichtete API beschrieben, insbesondere für Konto-, Verkaufs- und Bestelldaten.
- Keine allgemeine öffentliche Katalogsuch- oder Käuferdownload-API genannt.
- Lokal erworbene Dateien, beispielsweise FLAC, können anschliessend in TagStudio eingelesen und getaggt werden.
- Quelle aus dem PDF: [Bandcamp Developer](https://bandcamp.com/developer).

#### Qobuz API

- Im PDF als eingeschränkte Schnittstelle für Katalogdaten und Musikdienste beschrieben.
- Gültige, individuell zugewiesene Zugangsdaten erforderlich; automatisierte Kaufdownloads sind damit nicht allgemein freigegeben.
- Quelle aus dem PDF: [Qobuz API Terms of Use (PDF)](https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf).

#### Weitere im PDF bewertete Plattformen

- **iTunes Search API:** öffentliche, dokumentierte Suche und ID-basierte Abfragen; Shoplinks für den manuellen Kauf.
- **Apple Music API:** erweiterte Katalogsuche, im PDF als Zugang mit signierten Entwicklertokens beschrieben.
- **Deezer API:** ergänzende Katalogsuche und Metadaten.
- **Traxsource, Volumo, Mixupload und DJ-Pools:** Verfügbarkeit und Nutzungsrechte von Integrationsschnittstellen gemäss PDF unklar; vorerst Website- bzw. manuelle Abläufe vorsehen.

## 4. Empfohlener Workflow für TagStudio

Das Ausgangsdokument zeigt einen sechsstufigen Ablauf (Seiten 4–5):

```mermaid
flowchart TD
    A[1. Musik entdecken] --> B[2. Trackinformationen abrufen]
    B --> C[3. Musik kaufen oder legal herunterladen]
    C --> D[4. Audiodateien analysieren]
    D --> E[5. Metadaten in TagStudio bearbeiten]
    E --> F[6. Bibliothek und DJ-Export]
```

| Schritt | Funktion | Beispiele aus dem PDF |
|---|---|---|
| 1. Musik entdecken | Interessante Musik recherchieren | Spotify, SoundCloud, Beatport, Apple Music |
| 2. Trackinformationen abrufen | APIs abfragen, ISRC zuordnen, Remix-/Mix-Version erkennen, Bezugsquellen vergleichen | Mehrere Metadatenanbieter |
| 3. Musik kaufen oder legal herunterladen | Offizielle Kauf-/Downloadwege nutzen | Beatport, Traxsource, Bandcamp, Qobuz, 7digital |
| 4. Audiodateien analysieren | BPM, Tonart, Energy, Danceability, Drops, Ähnlichkeit ermitteln | Essentia als im PDF genannter Kandidat; siehe [Musikanalysekonzept](KONZEPT-MUSIKANALYSIEREN.md) |
| 5. Metadaten bearbeiten | Tags prüfen, korrigieren und ergänzen | ID3v2.4, Cover, Artist, Remix, ISRC, BPM, Tonart, benutzerdefinierte Tags |
| 6. Bibliothek und DJ-Export | Daten für bestehende DJ-Anwendungen bereitstellen | Lexicon → VirtualDJ, Traktor, Engine DJ |

Die Import- und Exportvorgänge müssen die bestehenden Schutzmechanismen von TagStudio beachten: **unbekannte Tags erhalten, Änderungen nachvollziehbar machen, Originaldateien nicht ungefragt überschreiben**. Die weiterführende DJ-Software-Interoperabilität wird im übergeordneten Konzept behandelt.

## 5. Konkrete API-Priorisierung

Dies ist ausdrücklich die **Vorschlagsreihenfolge des PDF** (Seite 5), nicht die Zusage einer bereits genehmigten Implementierung.

| Priorität | Schnittstelle | Geplante Funktion |
|---:|---|---|
| 1 | Apple iTunes Search API | Titelsuche, Versionen, Shoplinks ohne aufwendige Authentifizierung |
| 2 | SoundCloud API | Suche, Metadaten, Downloadfreigabe soweit erkennbar, Link zur Trackseite |
| 3 | Spotify Web API | Trackidentifikation, ISRC, Artist, Album |
| 4 | Beatport API | DJ-spezifische Metadaten, BPM, Tonart, Labels; Partnerzugang klären |
| 5 | Deezer API | Ergänzende Katalogsuche und Metadaten |
| 6 | 7digital / MassiveMusic | Partnerzugang für Kauf- und Downloadintegration prüfen |
| 7 | Apple Music API | Erweiterte Katalogsuche mit Entwicklerzugang |

**Abgrenzung:** Eine Suche über die API und eine Downloadfunktion sind unterschiedliche Berechtigungen. Ein vorhandener privater API-Schlüssel ist **kein Nachweis**, dass Dateien automatisiert heruntergeladen werden dürfen.

## 6. Geplante Funktionen für TagStudio

Die folgenden Funktionen übernimmt das Konzept aus Seite 6 des PDF und formuliert sie als Entwicklungsanforderungen:

| Funktion | Erwartetes Verhalten |
|---|---|
| Multi-Plattform-Suche | Artist und Titel einmal eingeben und Resultate mehrerer erlaubter APIs zusammenführen |
| Intelligentes Matching | ISRC, Artist, Titel, Mix-/Remix-Version und Laufzeit vergleichen, um beispielsweise Radio Edit und Extended Mix nicht zu verwechseln |
| Bezugsquellenvergleich | Offizielle Kauf- und Downloadlinks darstellen; Preise und Dateiformate nur anzeigen, wenn eine Quelle diese tatsächlich liefert |
| Downloadverwaltung | Ausschliesslich freigegebene oder gekaufte Dateien über vom Anbieter **ausdrücklich unterstützte** Wege übernehmen |
| Metadatenübernahme | Ausgewählte Trackinformationen als Vorschläge in TagStudio anzeigen und zur Bearbeitung anbieten |

**Architekturvorschlag aus dem PDF:** Die plattformübergreifende Metadatensuche zunächst als **eigenständiges Python-Modul** umsetzen. Kauf- und Downloadverwaltung davon **getrennt** als optionale Erweiterung entwickeln. So können geänderte Anbieter-APIs und Lizenzbedingungen ohne Eingriff in die Tagging-Kernfunktionen behandelt werden.

## 7. Technische und rechtliche Leitplanken

- **Keine unbelegten Schnittstellen:** Nur dokumentierte und für den konkreten Anwendungszweck freigegebene APIs verwenden; nicht aus einer internen Website-API auf öffentliche Nutzungsrechte schliessen.
- **Kein Stream-Ripping:** Streamingdaten nicht als Ersatz für einen autorisierten Musikdatei-Download speichern.
- **Berechtigungen unterscheiden:** Öffentliche API, Zugang mit eigenem Schlüssel und Partner-API gesondert dokumentieren.
- **Token schützen:** Authentifizierungsdaten nicht in Repository, Logdateien oder Exportpakete schreiben.
- **Versionsgenaues Matching:** ISRC allein ist kein hinreichender Nachweis für die richtige Mix-Version; weitere Merkmale mitprüfen.
- **Fremddaten schützen:** Übernahme neuer Metadaten nur kontrolliert, mit Vorschau und bestehender Backup-/Undo-Strategie.
- **Quellen belegen:** Herkunft, Aktualisierungszeitpunkt und Anbieter-ID der übernommenen Daten nachvollziehbar speichern, soweit zulässig.
- **Lizenzbedingungen prüfen:** Nutzungsrechte und kommerzielle/öffentliche Verteilbarkeit von Bibliotheken und APIs vor einer Implementierung klären.

Diese Leitplanken sind die aus dem PDF und dem übergeordneten TagStudio-Konzept abgeleitete technische Einordnung; sie stellen keine Rechtsberatung dar.

## 8. Offene Prüfaufträge

- [ ] Für alle vorgesehenen Schnittstellen aktuelle API-Dokumentation, Verfügbarkeit, Rate Limits und Terms of Use prüfen.
- [ ] Je Anbieter klären: **öffentlich ohne Schlüssel**, **privater Entwickler-/Nutzerschlüssel**, **Partnervertrag erforderlich** oder **kein zulässiger API-Zugang**.
- [ ] Beatport: vorhandene Plugin-Funktionalität gegen offizielle API-Berechtigungen und dokumentierte Endpunkte abgleichen.
- [ ] SoundCloud: Such-/Metadatenzugang sowie Grenzen der Downloadfreigabe verifizieren; Website-Verlinkung als Fallback testen.
- [ ] 7digital/MassiveMusic: Voraussetzungen und Kosten eines möglichen Partnervertrags prüfen.
- [ ] Format-, Preis- und Downloadinformationen ausschliesslich anzeigen, wenn verlässliche Angebotsdaten vorhanden sind.
- [ ] Abgleich von ISRC, Mix-Version und Dauer mit realen Dubletten-/Remix-Beispielen testen.
- [ ] Integrationsmodule und Datenfelder an bestehende TagStudio-Plugins und den Workflow «Vorbereiten» anschliessen, ohne vorhandene Funktionen doppelt aufzubauen.
- [ ] Export und Übergabe an die DJ-Programme mit den bestehenden Konzepten abstimmen.

## 9. Entscheidungsstand und nächste Schritte

| Gegenstand | Status | Nächster Schritt |
|---|---|---|
| TagStudio-Fokus auf Verwaltung, Tagging und DJ-Set-Vorbereitung | **BESCHLOSSEN** (übergeordnetes Konzept) | Bei allen Integrationen berücksichtigen |
| Plattformvergleich und priorisierte Schnittstellen | **KONZEPTVORSCHLAG** (PDF) | Zugang und Aktualität überprüfen |
| Python-Modul für Metadatensuche | **EMPFOHLEN** | Bestehende Module und Plugin-Struktur prüfen |
| Automatisierte Kauf-/Downloadintegration | **ZU PRÜFEN** | Partnerverträge, Nutzungsrechte, Endpunkte verifizieren |
| Direkte Schreibzugriffe auf fremde Bibliotheksdatenbanken | **NICHT ZIEL** | Sichere Austauschformate und autorisierte Schnittstellen bevorzugen |

**Empfohlene Reihenfolge:** Zuerst die vorhandenen Integrationen inventarisieren und die API-Zugänge validieren. Danach Multi-Plattform-Suche und Matching prototypisch ergänzen. Downloadverwaltung erst entwickeln, wenn ein zulässiger Downloadweg je Anbieter konkret nachgewiesen wurde.

## Anhang A: Tag-Programme, DJ-Software und Player (recherchiert am 12.10.2026)

Programme, die in TagStudio als Herkunft von Tags, Workflow-Schritt, Plugin-Quelle oder Vorbild vorkommen.

| Programm | Kurzbeschreib | Kosten |
|---|---|---|
| [Mp3tag](https://www.mp3tag.de/en/) | Tag-Editor für viele Dateien, Online-Abfragen, Umbenennen | Windows kostenlos (Spende); Mac [24,99 € im App Store](https://apps.apple.com/de/app/mp3tag/id1532597159?mt=12) |
| [MusicBrainz Picard](https://picard.musicbrainz.org/) | Erkennung per AcoustID, Tags nach MusicBrainz (Open Source, GPL) | kostenlos |
| [OneTagger](https://onetagger.github.io/) | DJ-Tagger mit Beatport, Traxsource, Discogs, Spotify u. a. | kostenlos (Spenden) |
| [AudioRanger](https://www.audioranger.com/) | Automatisches Erkennen und Taggen, Duplikate, Ordner ordnen | Gratisversion; Pro mit Lifetime-Lizenz (Preis erst im Kaufprozess) |
| [Mixed In Key 11](https://mixedinkey.com/) | Tonart- und Energie-Analyse, Cue-Punkte | ca. 58 USD / 60 EUR einmalig; Pro ca. 99 EUR ([Testbericht](https://vibesdj.io/learn/gear/mixed-in-key-11)) |
| [Platinum Notes 10](https://mixedinkey.com/platinum-notes) | Lautheit angleichen, Clipping beheben | 98 USD einmalig, Upgrade 49 USD ([Testbericht](https://vibesdj.io/learn/gear/platinum-notes-10)) |
| [beaTunes 5](https://www.beatunes.com/en/index.html) | BPM, Tonart, Stimmung; Tag-Prüfung | [34,95 € einmalig](https://www.beatunes.com/en/beatunes-buy.html), Upgrade 11,95 € |
| [Lexicon DJ](https://www.lexicondj.com/pricing) | Zentrale DJ-Bibliothek, Konvertierung zwischen DJ-Programmen | Free; Essential ab 10,49 USD/Monat oder 249 USD Lifetime; Ultimate ab 20,99 USD/Monat oder 499 USD Lifetime |
| [Mixo](https://mixo.dj/pricing) | DJ-Bibliothek synchron über Programme und Geräte | Free; Gold 7 USD/Monat |
| [rekordbox](https://rekordbox.com/en/plan/) | DJ-Software von AlphaTheta/Pioneer | Free; Core 12, Creative 18, Professional 36 USD/Monat (Jahresabo günstiger) |
| [Serato DJ](https://serato.com/dj/pro/buy) | DJ-Software; schreibt Cues, Loops, Beatgrid in die Tags | Lite kostenlos; Pro 9,99/Monat; Suite 14,99/Monat |
| [Traktor Pro 4](https://www.native-instruments.com/en/products/traktor/dj-software/traktor-pro-4/) | DJ-Software von Native Instruments | 149 USD einmalig |
| [VirtualDJ](https://virtualdj.com/products/virtualdj/price.html) | DJ-Software mit breiter Controller-Unterstützung, Stems, Video | Free (privat, ohne Controller); Home 4, Pro 19, Business 99 USD/Monat |
| [Engine DJ](https://enginedj.com/software/enginedj-desktop) | Bibliothek für Denon-DJ- und Numark-Geräte | kostenlos |
| [foobar2000](https://www.foobar2000.org/), [VLC](https://www.videolan.org/vlc/), [MusicBee](https://www.getmusicbee.com/) | Player (externe Player in TagStudio) | kostenlos |
| [Beyond Compare](https://www.scootersoftware.com/shop) | Vergleichsprogramm – Vorbild für den TagStudio-Vergleich | Standard 35 USD, Pro 70 USD einmalig |

---

*Redaktioneller Hinweis:* Abschnitt 2.1 und Anhang A stammen aus der am 12.10.2026 recherchierten Übersicht (Quellen dort verlinkt); die übrigen Tabellen, Beschreibungen, API-Prioritäten und der sechsstufige Workflow sind aus dem genannten PDF übertragen und für eine versionskontrollierte Projektdokumentation neu formatiert. Die zusätzliche Verknüpfung zu TagStudio-Konzepten, die Entscheidungsstatus und die Prüfaufträge dienen der späteren Umsetzung. Eine erneute Recherche zur faktischen Aktualität der Plattformangebote und Schnittstellen war **nicht** Teil dieser Übertragung.