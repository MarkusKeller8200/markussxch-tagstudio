# Entwicklungsanweisungen für KI-Agenten

## Zentrale Projektgrundlage

Vor Architekturentscheidungen, neuen Modulen oder grösseren Codeänderungen unbedingt lesen:

- [`docs/KONZEPT-PRODUKT-ARCHITEKTUR.md`](docs/KONZEPT-PRODUKT-ARCHITEKTUR.md) – übergeordnetes Produkt- und Architekturkonzept v0.1
- [`docs/KONZEPT-MUSIKANALYSIEREN.md`](docs/KONZEPT-MUSIKANALYSIEREN.md) – bei Musik- und KI-Analyse, Ähnlichkeitssuche und DJ-Übergangsempfehlungen lesen (Technologien noch zu evaluieren)
- [`docs/KONZEPT_DJPLATTFORMEN.md`](docs/KONZEPT_DJPLATTFORMEN.md) – bei Plattformrecherche, Metadaten-APIs, Bezugsquellen und Downloadverwaltung lesen; Angaben und Berechtigungen vor Implementierung verifizieren
- [`docs/UEBERGABE.md`](docs/UEBERGABE.md) – bisherige Projektübergabe und Entwicklungsregeln
- [`docs/PROJEKTSTAND.md`](docs/PROJEKTSTAND.md) – tatsächlicher Implementierungsstand
- passende `docs/KONZEPT-*.md`-Datei für den zu bearbeitenden Funktionsbereich

## Verbindliche Leitplanken

- TagStudio bleibt eine Anwendung für Musikverwaltung, Tagging, Analyse und DJ-Set-Planung; keine vollwertige DJ-Mixing-Software oder DAW entwickeln.
- Bestehende Python-Logik und Web-GUI beibehalten; eine native Audio-Engine, JUCE, VST3 oder Vue sind keine bereits freigegebenen Implementierungsentscheide.
- Stem-Separation offline und qualitätsorientiert; kein Live-Separation-Zwang.
- DJ.Studio, Lexicon, Mixo, Engine DJ, Serato, VirtualDJ, Traktor und rekordbox bei relevanten Austauschfunktionen berücksichtigen.
- Drittanbieterbibliotheken und deren Datenbanken niemals ohne ausdrückliche Freigabe verändern. Erhaltene Metadaten, unbekannte Tags und Binärfelder schützen.
- Beschlossene Anforderungen, Empfehlungen, offene Entscheide und Prüfaufträge aus dem Konzept voneinander unterscheiden. Offene Entscheidungen nicht als beschlossen behandeln.
- Keine grossen Refactorings oder neuen Pflicht-Abhängigkeiten ohne Issue/ADR sowie Kompatibilitäts- und Lizenzprüfung.
- Bei betroffenen Änderungen Tests und die relevanten Dokumente nachführen.

## Pflege

`docs/KONZEPT-PRODUKT-ARCHITEKTUR.md` ist das übergreifende Living Document. Bestehende Detailkonzepte behalten ihre Bedeutung; bei Widersprüchen explizit entscheiden und dokumentieren statt stillschweigend überschreiben.