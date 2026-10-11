# Konzept: Hilfe

Stand: 2026-10-11 (4.4.0-beta.6) · Status: **umgesetzt in 4.3.0** (#158, #159) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird an der Hilfe
> weitergearbeitet – auch neue Tastenkürzel oder Felder –, ist es im selben Zug anzupassen.

## 1. Ziel

Hilfe direkt in der App: verstehen, was die vielen ID3-Felder bedeuten und woher sie kommen, welche Felder in der
eigenen Bibliothek vorkommen, und das Handbuch, die Plugin-Anleitung und alle Tastenkürzel griffbereit haben.

## 2. Funktionen

| Reiter | Inhalt |
|---|---|
| Tag-Übersicht | alle Felder als **eine Tabelle** mit Bedeutung, Herkunft und DJ-Relevanz; Filter-Chips nach Gruppe (Kapitel, Programme, eigene Tags), Sortierung; nach einem **Scan** der Bibliothek die Spalten **Mit** und **Ohne** (Anzahl Titel mit bzw. ohne das Feld) – ein Klick öffnet die Titel im Tagger |
| Handbuch | README als formatierte Seite, Links zu ID3-Felder und Plugins innerhalb der Hilfe |
| ID3-Felder | docs/ID3-FELDER.md (alle Frames) |
| Plugins | PLUGINS.md (Anleitung für eigene Plugins) |
| Tastatur | alle Tastenkürzel nach Bereichen (`HELP_KEYS`) |
| Lizenzen | alle Fremdkomponenten (Bibliotheken, Werkzeuge, Dienste, Vorlagen) mit Lizenz, Quelle und Prüfstand, gruppiert (#176) |

Dazu die Knöpfe **Einrichtungsassistent** und **Erste Schritte** (erneut starten).

## 3. Umsetzung

- **Kern:** `taghelp.py` (`CHAPTERS`, `ANALYSIS`, `SOFTWARE`, `DJ_RELEVANT`, `MEANING`, `overview`, `scan`, `cached`,
  Cache `cache/tagscan`), `id3frames.py` (Frame-Katalog), `origins.py` (Herkunft).
- **Lizenzen (#176):** Liste `docs/third-party.json` (Gruppen, je Eintrag Verwendung, Lizenz, Quelle, Prüfart pypi/github,
  `checked`); `help_licenses` liest sie, `helpLicensesHtml` zeigt sie. Workflow „Fremdkomponenten prüfen“
  (`.github/workflows/third-party.yml`, `.github/scripts/third_party_check.py`) vergleicht monatlich mit PyPI/GitHub und
  führt ein Issue mit den Änderungen; nach der Durchsicht `--apply` und committen.
- **Session:** `session_help.py` (`help_docs` mit `DOCS` = README, `docs/ID3-FELDER.md`, `PLUGINS.md`; `help_licenses`; `help_tags`,
  `start_tag_scan`, `tag_field_filter`).
- **Oberfläche:** `web/help.js` (`helpTab`, Tabelle, `helpGroups`, `HELP.sort`, `helpMissing`, `HELP_KEYS`).
- Die Dokumente werden im Installer mitgeliefert (`--add-data`).

## 4. Entscheide

- Tag-Übersicht als Tabelle mit Gruppenfilter statt Abschnitten (Wunsch User, 4.3.0).
- Spalte „Ohne“ zeigt, welchen Titeln ein Feld fehlt (Wunsch User, 4.3.0).
- Vor der Freigabe an andere: Lizenzseite mit allen Fremdkomponenten, fremde Bestandteile werden periodisch auf
  Änderungen geprüft (Wunsch User, 4.4.0).
- Die Hilfe steht in der Seitenleiste nach den Einstellungen (vor „Datenbank“).

## 5. Offen / Ideen

- Neue Tastenkürzel müssen in `HELP_KEYS` und im README-Abschnitt „Tastatur“ ergänzt werden.
- **Neue Fremdkomponenten** (Bibliothek, Plugin-Paket, übernommene Vorlage, Online-Dienst) immer in `docs/third-party.json`
  eintragen – ein Test prüft die Pakete des Stems-Plugins.

## 6. Tests

`tests/test_taghelp.py`, `tests/test_id3frames.py`, `tests/test_third_party.py`, Oberflächen-Tests in `tests/test_browser_ui.py` (Hilfe).
