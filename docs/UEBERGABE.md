# Übergabe an einen neuen Chat

Stand: **2026-10-11, 4.4.0-beta.4**. Kurzfassung für den Einstieg in einer neuen Claude-Sitzung. Details:
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

## Regeln des Users

- **Löschen** (Dateien, Branches, Tags, Labels) nur nach Rückfrage.
- **Keine Zugangsdaten anfassen:** Passwörter, Tokens, Schlüssel gibt der User selbst ein; nie speichern (ausser
  verschlüsselt im Plugin), nie protokollieren oder exportieren. Nichts Privates ins öffentliche Repo.
- **Keine Extra-Kredits verbrauchen.**

## Offen (Stand 4.4.0-beta.4)

- Wartet auf Tests des Users (`_3 Beta-Test`): #117 Beatport-Download (gegen die echte API noch ungetestet, Download-
  Endpunkt wird geprobt), #163–#165 Profile, #167–#170 Einrichtungsassistent, Seitenleiste, Erste Schritte,
  #172 Basisordner und Ordnerstruktur, #173 Aussortieren.
- #171 CodeQL-Fund (Dateirechte, `tagstudio_web.py:150`) – noch zu beheben.
- Offene Frage an den User: #111 Wortliste („Dj, Feat, Mc, Vs“).
- Nach den Tests: 4.4.0 final (nur auf Wunsch), danach Meilenstein „Später“ (#9, #14, #107, #108, #156 WAV, #157
  Mehrsprachigkeit).
