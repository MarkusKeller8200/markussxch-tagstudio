# Konzept: Mehrsprachigkeit

Status: **Entwurf** (2026-10-11) – Issue #157.

## Ziel

- Sprachauswahl mit Flaggen, zuerst **Englisch**, **Schweizerdeutsch** und **Deutsch**.
- Alle Beschriftungen exportieren und wieder importieren, damit übersetzt werden kann (auch von Dritten).
- Englische Übersetzung erstellen.

## Ausgangslage (gemessen 2026-10-11)

- Alle Texte stehen heute direkt im Code: rund **1 200 Texte** in der Oberfläche (`web/*.js`, `index.html`; am
  meisten in `settings.js`, `index.html`, `tagger.js`) und rund **580 Meldungen** im Python-Teil (Fehler, Hinweise,
  Plugin-Formulare).
- Die Schreibweise ist gemischt: überwiegend Schweizer Hochdeutsch mit „ss“ (Grösse, schliessen), aber vereinzelt
  „ß“ (17 Stellen, z. B. „Groß-/Kleinschreibung“).
- Plugins (Beatport, Online-Metadaten, Stems) bringen eigene Texte in `plugin.py`/`plugin.json` mit.

## Sprachen – Vorschlag

| Flagge | Sprache | Inhalt |
|---|---|---|
| 🇨🇭 | Deutsch (Schweiz) | heutiger Text, einheitlich mit „ss“ – **Ausgangssprache** |
| 🇩🇪 | Deutsch (Deutschland) | automatisch aus der Schweizer Fassung (ss → ß nach Wortliste) plus wenige eigene Begriffe |
| 🇬🇧 | English | vollständige Übersetzung |

**Offene Frage:** Ist mit „Schweizerdeutsch“ wirklich Mundart gemeint (z. B. „Spichere“, „Abbräche“) oder
Schweizer Hochdeutsch? Mundart ist möglich (eigener Katalog), aber für eine Oberfläche unüblich; der Vorschlag
oben geht von Schweizer Hochdeutsch aus.

## Technik

- **Kataloge:** je Sprache eine JSON-Datei `web/i18n/<sprache>.json` mit Schlüssel → Text, z. B.
  `"tagger.load": "Einlesen"`. Platzhalter in geschweiften Klammern: `"{n} Datei(en) im Tagger"`.
- **Oberfläche:** Funktion `t("tagger.load", {n})`; statische Texte in `index.html` über `data-i18n="…"`
  (Text) bzw. `data-i18n-title="…"` (Tooltip). Fehlt ein Text, gilt die Ausgangssprache, dann der Schlüssel – nie
  eine leere Beschriftung.
- **Python:** gleiche Kataloge für Meldungen (`i18n.t()` in `session.py`, `core.py` …); Fehlertexte, die in die
  Oberfläche gehen, bekommen Schlüssel.
- **Plugins:** `plugin.json` erhält optional `"i18n": {"en": {...}}`; ohne Übersetzung erscheint der deutsche Text.
- **Sprachwahl:** Einstellungen › Darstellung › Sprache (Flaggen-Knöpfe) und beim ersten Start nach der
  Systemsprache; gespeichert in der Einstellungsdatei; Wechsel ohne Neustart (Seite neu zeichnen).
- **Zahlen und Daten:** `Intl` mit der gewählten Sprache (1'234 in der Schweiz, 1.234 in Deutschland, 1,234 Englisch).
- **Feldnamen** (TITLE, INITIALKEY …) und ID3-Schlüssel bleiben unübersetzt.

## Export / Import für die Übersetzung

- Export als **CSV** (UTF-8, für Excel) und **JSON**: Spalten `Schlüssel`, `Kontext` (Seite/Datei), `de-CH`,
  `de-DE`, `en`, … – leere Zellen = noch nicht übersetzt.
- Import prüft: unbekannte Schlüssel, fehlende bzw. zusätzliche Platzhalter (`{n}`), zu lange Texte für Knöpfe
  (Warnung), zeigt eine Vorschau und übernimmt nur gültige Zeilen.
- Werkzeug `tools/i18n_extract.py` sammelt neue, noch nicht verschlüsselte Texte aus dem Code (für die Umstellung
  und danach als Prüfung in den Tests: keine neuen festen Texte).

## Umsetzung in Phasen

1. **Grundlage:** Kataloge, `t()`, `data-i18n`, Sprachwahl mit Flaggen, Export/Import; Seitenleiste, Einstellungen
   und Dialoge umgestellt; Schreibweise der Ausgangssprache vereinheitlicht.
2. **Module umstellen:** Tagger, Vergleich, Player, DJ-Set, Snapshots, Sicherungen, Plugins – je Modul ein Issue,
   mit einem Test, der in jeder Sprache alle Seiten öffnet und auf fehlende Schlüssel prüft.
3. **Englisch** vollständig übersetzen (Vorschlag: zuerst maschinell aus den Katalogen, dann durchsehen).
4. **Python-Meldungen und Plugins**, README/Hilfe auf Englisch (Kurzfassung).

Aufwand grob: Phase 1 ein Release, Phase 2 verteilt auf zwei bis drei Releases (rund 1 800 Texte), Phase 3/4
danach. Bis Phase 2 abgeschlossen ist, bleiben einzelne Texte deutsch – das ist gewollt (Fallback).

## Offene Fragen an den User

- Mundart oder Schweizer Hochdeutsch (siehe oben)?
- Soll die Sprache der Oberfläche auch die Sprache der geschriebenen Tags beeinflussen (z. B. Genre-Namen)?
  Vorschlag: nein – Tags bleiben, wie sie sind.
