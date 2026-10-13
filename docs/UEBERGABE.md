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

## Geplante Iterationen 4.4.1 und 4.5.0 (Entscheid 2026-10-14)

**Planung freigegeben, Implementierung noch nicht abgeschlossen.** Details und Abnahmekriterien: [Releaseplanung 4.4.1 (#188)](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/188), [Releaseplanung 4.5.0 (#189)](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/189).

- **4.4.1 – Player-Stabilität zuerst:** [#181 Offbeat-Übergänge korrigieren](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/181) und [#182 Takt-/Cue-Sprünge](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/182); beide explizit mit `_1 bereit` für die Entwicklung freigegeben. Tests und Vorschauqualität haben Vorrang; kein ungefragter JUCE-/GUI-Umbau.
- **4.5.0 – Tagger & Metadaten danach:** [#184 Bibliotheksaufnahme](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/184), [#185 Letzte Bearbeitung](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/185), [#183 LRCLIB-Lyrics](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/183). Diese Issues sind **weiterhin `idee`** und noch nicht zur Umsetzung freigegeben.
- **Später / Konzeptphase:** [#186 Neues Modul IDEE](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/186), [#187 GitHub-Meldeformular mit Eigentümerfreigabe](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/187), [#180 1001Tracklists](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/180) und die grössere Analyse-/Audio-Architektur.
- **Meilensteinpflege (am 14.10.2026 geprüft):** Das Release [v4.4.0](https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/tag/v4.4.0) ist veröffentlicht; der GitHub-Meilenstein [#10](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/10) ist **geschlossen** (17 von 17 Issues erledigt). Die neu angelegten Meilensteine [#14 – 4.4.1 Player-Stabilität](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/14) enthalten #181, #182 und Planungs-Issue #188; [#15 – 4.5.0 Tagger & Metadaten](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/15) enthalten #183–#185 und Planungs-Issue #189. Alle übrigen neun offenen Ideen sind [#4 – Idee (Später)](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestone/4) zugeordnet. **Kein offenes Issue ohne Meilenstein** (16 von 16). Aktuell kein weiteres ungeplantes BugFixes-Issue.

## Offen (Stand 4.4.0 final)

- **NEUE KONZEPTIDEE #180 (14.10.2026):** 1001Tracklists-basierter Tracklist-Import, Discovery und datenbasierte DJ-Set-Analyse – **noch nicht implementiert**. Siehe `docs/KONZEPT-DJSET.md` (Abschnitt 5.1) und `docs/KONZEPT-MUSIKANALYSIEREN.md` (Abschnitt 12); Label `idee`, Meilenstein „Später“. Keine Scraping-/API-Implementierung ohne vorangehende Rechteprüfung.


- 4.4.0 ist final (2026-10-12), Meilenstein #10 geschlossen; alle Issues getestet und geschlossen.
- Nächste Iterationen: #14 «4.4.1» und #15 «4.5.0» wie oben; «Idee (Später)» (#4): #9, #14, #107, #108, #156, #157, #180, #186 und #187.
- Monatlich: Issue „Fremdkomponenten: Änderungen prüfen“ durchsehen, Stände mit
  `python .github/scripts/third_party_check.py --apply datei.json` übernehmen.
- Neue Fremdkomponenten immer in `docs/third-party.json` eintragen.
