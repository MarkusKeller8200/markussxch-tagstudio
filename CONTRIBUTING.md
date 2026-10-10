# Mitmachen bei MarKusSXCH TagStudio

Danke für dein Interesse! Fehlerberichte, Ideen, Plugins und Pull Requests sind willkommen. Bitte halte dich an den
[Verhaltenskodex](CODE_OF_CONDUCT.md).

## Fehler melden und Ideen vorschlagen

- **Fehler:** [Issue „Fehler melden“](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/new/choose) –
  mit TagStudio-Version (unten in der Seitenleiste), Betriebssystem, Schritten zum Nachstellen und, falls
  vorhanden, dem Protokoll aus `~/TagStudio/Logs`. Bitte keine urheberrechtlich geschützten MP3s anhängen –
  ein Bildschirmfoto oder die betroffenen Feldnamen genügen meist.
- **Ideen:** Issue „Funktion vorschlagen“ bzw. „Plugin-Idee“. Vorher kurz in den
  [Issues](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues) und
  [Milestones](https://github.com/MarkusKeller8200/markussxch-tagstudio/milestones) schauen, ob es schon geplant ist.
- **Sicherheitslücken** nie öffentlich, sondern privat melden – siehe [SECURITY.md](SECURITY.md).

## Entwicklungsumgebung

```bash
git clone https://github.com/MarkusKeller8200/markussxch-tagstudio.git
cd markussxch-tagstudio
python tagstudio_web.py            # neue Oberfläche (App-Fenster mit pywebview, sonst Browser)
python tagstudio.py                # klassische Oberfläche (tkinter, eingefroren – keine Änderungen mehr)
python -m unittest discover -s tests -v
```

- **Python 3.9 oder neuer.** Der Kern nutzt **nur die Standardbibliothek** – bitte keine neuen Pflicht-Abhängigkeiten.
  Optionale Pakete (pywebview, Pillow) dürfen nur Komfort bringen; ohne sie muss alles weiter funktionieren.
- Schwere Pakete (z. B. PyTorch für Stems) gehören in ein **Plugin** mit eigener Umgebung – siehe [PLUGINS.md](PLUGINS.md).
- Die Oberfläche (`web/`) ist reines HTML/CSS/JavaScript ohne Build-Schritt und ohne Bibliotheken aus dem Netz.

## Richtlinien für Code

- **Sprache:** Oberfläche, Meldungen, Kommentare und Dokumentation auf **Deutsch** (Schweizer Schreibweise ist ok).
  Bezeichner im Code englisch.
- **Byte-genau:** TagStudio ändert nur, was der Benutzer ändert. Unbekannte Frames, Binärfelder und die
  Audiodaten bleiben unverändert – bitte mit einem Test absichern.
- **Rückgängig:** Jede Änderung an Tags läuft über die Undo-Funktion der Sitzung (`undo.checkpoint` … `commit`)
  und wird erst mit „Speichern“ geschrieben; vorher entsteht automatisch eine Sicherung.
- **Tests:** Neue Funktionen und Fehlerbehebungen bekommen Tests in `tests/` (mit synthetischen MP3-Dateien aus
  `tests/helpers.py`, ohne Netz). Alle Tests müssen auf Windows, macOS und Linux laufen.
- **Sicherheit:** Der lokale Server bindet nur an `127.0.0.1` und prüft ein Sitzungs-Token; Pfade aus der
  Oberfläche werden geprüft. CodeQL läuft bei jedem Push – Funde werden automatisch als Issue angelegt.
- **Stil:** an den bestehenden Code anlehnen (PEP 8, Zeilen bis ca. 120 Zeichen, kurze Docstrings auf Deutsch).

## Commits und Pull Requests

1. Für größere Änderungen zuerst ein Issue eröffnen und die Idee kurz abstimmen.
2. Eigenen Zweig anlegen (`feature/…` oder `fix/…`), kleine, thematisch saubere Commits.
3. Commit-Nachricht auf Deutsch: erste Zeile kurz und aussagekräftig, darunter das Warum. Mit `Fixes #n` bzw.
   `Refs #n` auf Issues verweisen.
4. **CHANGELOG.md:** Eintrag unter „Unveröffentlicht“ (Neu / Geändert / Behoben).
5. README bzw. PLUGINS.md nachziehen, wenn sich Bedienung oder Schnittstellen ändern.
6. Pull Request gegen `main` öffnen und die Checkliste der Vorlage ausfüllen. Die Tests in GitHub Actions müssen
   grün sein.

Versionsnummern und Releases setzt der Projektverantwortliche (`packaging/release.py`, siehe README unter
„Versionen & Releases“) – bitte `version.py` in Pull Requests nicht ändern.

## Plugins

Eigene Plugins brauchen keinen Pull Request: Ordner mit `plugin.json` und `plugin.py` nach `~/TagStudio/Plugins`
legen – Anleitung in [PLUGINS.md](PLUGINS.md). Wer ein Plugin allgemein nützlich findet, kann es gern als
Plugin-Idee vorschlagen.

## Lizenz

Mit einem Beitrag erklärst du dich einverstanden, dass er unter der Lizenz des Projekts
([GNU GPL v3](LICENSE)) veröffentlicht wird.
