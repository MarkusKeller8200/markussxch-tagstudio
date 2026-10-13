# Übergabe an einen neuen Chat

Stand: **2026-10-12, 4.4.0 final**. Kurzfassung für den Einstieg in einer neuen Claude-Sitzung. Details:
[PROJEKTSTAND.md](PROJEKTSTAND.md) (aktuell), [PROJEKTSTAND-ARCHIV.md](PROJEKTSTAND-ARCHIV.md) (Verlauf bis 3.5.0, mit der
ersten Übergabe vom 2026-10-10), Konzepte in `docs/KONZEPT-*.md`. Bei jeder Übergabe nachführen.

## Einstieg

1. Sprache mit dem User: **Deutsch**.
2. Repo `MarkusKeller8200/markussxch-tagstudio` (öffentlich) per `add_repo` (Zugriff „push“) holen und nach
   `/home/claude/markussxch-tagstudio` klonen. Gearbeitet und gepusht wird nur auf `main`.
3. Diese Datei und `docs/PROJEKTSTAND.md` lesen, dann offene Issues ansehen:
   `gh api "repos/MarkusKeller8200/markussxch-tagstudio/issues?state=open&per_page=100"`.
4. Der User testet unter Windows, meist aus dem Quellcode (`S:\_Claude\markussxch-tagstudio`, Update-Knopf) oder mit
   dem Installer. Protokolle liegen bei ihm unter `~\TagStudio\Logs` (über die Desktop-App-Brücke lesbar, falls verbunden).

## Arbeitsweise (kurz)

- Je Issue: Code, Unit-Tests, Oberflächen-Test (Playwright). Commits auf Deutsch mit „Refs #n“ und den Trailern
  `Co-Authored-By` / `Claude-Session`.
- Tests: `python3 -m unittest discover -s tests -q` und
  `TAGSTUDIO_UI_TESTS=1 python3 -m unittest discover -s tests -p "test_browser_ui.py"`.
- Release: `python3 packaging/release.py X.Y.Z-beta.N`, committen „Version …“, pushen – der Workflow „Installer“ legt Tag
  und Release an. **Finale Version nur auf ausdrücklichen Wunsch.** Änderungen sofort im CHANGELOG unter „Unveröffentlicht“.
- Labels: `_1 bereit` (User) → `_2 in Arbeit` → `_3 Beta-Test` (mit Kommentar „Zum Testen in X abhaken:“ und
  Checkboxen) → nach „getestet ok“ schliessen und Label entfernen. `idee` = noch nicht eingeplant.
- Neue Python-Module in `packaging/build.py` unter `HIDDEN`; Session-Methoden in `_PASS` (`tagstudio_web.py`).
- Projekt-Doku doppelt führen: Claude-Projekt (`claude/…`) und `docs/` im Repo.

## Konzepte je Bereich

Jede Funktion hat ein Konzept in `docs/`. **Wird an einer Funktion weitergearbeitet, das zugehörige Konzept im selben
Zug nachführen.**

| Bereich | Konzept |
|---|---|
| Übergreifendes Produkt- und Architekturkonzept | [KONZEPT-PRODUKT-ARCHITEKTUR.md](KONZEPT-PRODUKT-ARCHITEKTUR.md) |
| Musikanalyse und MusicAnalyzer (geplant) | [KONZEPT-MUSIKANALYSIEREN.md](KONZEPT-MUSIKANALYSIEREN.md) |
| DJ-Musikplattformen, API und Kauf-/Download-Workflow (geplant) | [KONZEPT_DJPLATTFORMEN.md](KONZEPT_DJPLATTFORMEN.md) |
| Vorbereiten, Entdecken | [KONZEPT-VORBEREITEN.md](KONZEPT-VORBEREITEN.md) |
| Tagger | [KONZEPT-TAGGER.md](KONZEPT-TAGGER.md) |
| Tag-Fixer | [KONZEPT-TAGFIXER.md](KONZEPT-TAGFIXER.md) |
| Vergleich | [KONZEPT-VERGLEICH.md](KONZEPT-VERGLEICH.md) |
| DJ-Set | [KONZEPT-DJSET.md](KONZEPT-DJSET.md) |
| Snapshots | [KONZEPT-SNAPSHOTS.md](KONZEPT-SNAPSHOTS.md) |
| Player | [KONZEPT-PLAYER.md](KONZEPT-PLAYER.md) |
| Plugins | [KONZEPT-PLUGINS.md](KONZEPT-PLUGINS.md) |
| Einstellungen | [KONZEPT-EINSTELLUNGEN.md](KONZEPT-EINSTELLUNGEN.md) |
| Profile, Einrichtungsassistent | [KONZEPT-EINRICHTUNG.md](KONZEPT-EINRICHTUNG.md) |
| Speicherorte, Ordnerstruktur | [KONZEPT-SPEICHER.md](KONZEPT-SPEICHER.md) |
| Hilfe | [KONZEPT-HILFE.md](KONZEPT-HILFE.md) |
| Update, Versionen, Release | [KONZEPT-UPDATE.md](KONZEPT-UPDATE.md) |
| App und Oberfläche | [KONZEPT-APP-GUI.md](KONZEPT-APP-GUI.md) |
| WAV (geplant) | [KONZEPT-WAV.md](KONZEPT-WAV.md) |
| Mehrsprachigkeit (geplant) | [KONZEPT-MEHRSPRACHIG.md](KONZEPT-MEHRSPRACHIG.md) |
| ID3-Felder (Nachschlagen) | [ID3-FELDER.md](ID3-FELDER.md) |
| Programme und Plattformen (Kosten, Stand 10/2026) | [Word](Tag-Programme-und-Musik-Plattformen.docx), [PDF](Tag-Programme-und-Musik-Plattformen.pdf) – Original als Claude-Doc |

## Regeln des Users

- **Löschen** (Dateien, Branches, Tags, Labels) nur nach Rückfrage.
- **Keine Zugangsdaten anfassen:** Passwörter, Tokens, Schlüssel gibt der User selbst ein; nie speichern (ausser
  verschlüsselt im Plugin), nie protokollieren oder exportieren. Nichts Privates ins öffentliche Repo.
- **Keine Extra-Kredits verbrauchen.**

## Offen (Stand 4.4.0 final)

- **NEUE KONZEPTIDEE #180 (14.10.2026):** 1001Tracklists-basierter Tracklist-Import, Discovery und datenbasierte DJ-Set-Analyse – **noch nicht implementiert**. Siehe `docs/KONZEPT-DJSET.md` (Abschnitt 5.1) und `docs/KONZEPT-MUSIKANALYSIEREN.md` (Abschnitt 12); Label `idee`, Meilenstein „Später“. Keine Scraping-/API-Implementierung ohne vorangehende Rechteprüfung.


- 4.4.0 ist final (2026-10-12), Meilenstein #10 geschlossen; alle Issues getestet und geschlossen.
- Nächster Meilenstein noch nicht geplant – „Später“: #9, #14, #107, #108, #156 WAV, #157 Mehrsprachigkeit.
- Monatlich: Issue „Fremdkomponenten: Änderungen prüfen“ durchsehen, Stände mit
  `python .github/scripts/third_party_check.py --apply datei.json` übernehmen.
- Neue Fremdkomponenten immer in `docs/third-party.json` eintragen.
