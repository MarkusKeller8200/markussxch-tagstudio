# Konzept: Mehrsprachigkeit

Status: **Entwurf** (2026-10-11, ergänzt 2026-10-16: KI-Übersetzung, eigene Sprachdatei, Übersetzungen melden) – Issue #157.

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

**Nachmessung 2026-10-16 (nach 4.5.0):** grob **2 500–3 000 verschiedene Texte** – Oberfläche rund 1 300–1 500
(`web/*.js`, `index.html`), Python-Meldungen rund 1 000, Plugins rund 400 (`plugin.py`, `plugin.json` inkl.
Dienstbeschreibungen). Dazu die Feldbeschreibungen der Tag-Übersicht (`taghelp.py`) und rund 19 000 Wörter Doku
(README, PLUGINS.md, ID3-FELDER.md, CHANGELOG). 59 Stellen mit „ß“ sind zu vereinheitlichen. Bei rund 40 Zeichen je
Text sind das etwa 120 000 Zeichen – für eine KI-Übersetzung wenig, für die Durchsicht von Hand viel.

## Sprachen – Vorschlag

| Flagge | Sprache | Inhalt |
|---|---|---|
| 🇩🇪 | Deutsch | heutiger Text (Hochdeutsch), Schreibweise vereinheitlicht – **Ausgangssprache** |
| 🇨🇭 | Schweizerdeutsch (Mundart) | eigener Katalog in Mundart, z. B. „Spichere“, „Abbräche“, „Iilääse“ |
| 🇬🇧 | English | vollständige Übersetzung |

**Entscheid des Users (2026-10-11): Schweizerdeutsch = Mundart.** Mundart hat keine feste Rechtschreibung; der
Katalog folgt einer Schreibweise (Vorschlag: Zürichdeutsch nach Dieth, ohne Sonderzeichen ausser ä/ö/ü) und wird vom
User durchgesehen. Fehlt ein Mundart-Text, gilt Hochdeutsch.

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

## Übersetzen mit KI, eigene Sprachdatei, Übersetzungen melden (Ergänzung 2026-10-16)

**Zwei Ebenen von Sprachdateien:**
- *Mitgeliefert:* `web/i18n/<sprache>.json` (im Repository, geprüft) – Deutsch ist die Ausgangssprache.
- *Eigene:* `~/TagStudio/Sprachen/<sprache>.json` (je Benutzer, nicht im Profil-Export der Zugangsdaten). Eigene
  Einträge gehen vor; fehlt ein Eintrag, gilt der mitgelieferte, dann Deutsch. Ein Update von TagStudio überschreibt
  die eigene Datei nie. Neue Sprachen (z. B. Französisch) kann der Benutzer selbst anlegen.
- Je Eintrag: Text, Herkunft (`mitgeliefert` / `ki` / `manuell`), Stand des deutschen Originals (Prüfsumme) – ändert
  sich der deutsche Text, wird die Übersetzung als „veraltet“ markiert statt still weiterverwendet.

**Übersetzen mit KI** (eigene Aktion „Fehlende Texte übersetzen …“):
- Über Dienst-Plugins nach dem Muster von #204 – der Benutzer wählt den Dienst, Schlüssel liegen verschlüsselt im
  Plugin:
  | Dienst | Art | Stärken / Grenzen |
  |---|---|---|
  | DeepL API | online, eigener Schlüssel (Free bis 500 000 Zeichen/Monat) | sehr gut für EN/FR/IT …, keine Mundart |
  | OpenAI / Anthropic / andere LLM-API | online, eigener Schlüssel | auch Mundart, Glossar und Kontext im Prompt |
  | Ollama / LM Studio (lokales Modell) | lokal, kostenlos, nichts verlässt den PC | Qualität je Modell, langsamer |
  | Argos Translate | lokal, Open Source (MIT), Offline-Modelle | einfach, Qualität mittel, keine Mundart |
- **Kandidat lokales Modell: [Apertus](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)** (Swiss AI, ETH/EPFL/CSCS;
  Apache-2.0, offen trainiert, sehr viele Sprachen – laut Projekt auch Schweizerdeutsch und Rätoromanisch). 8B passt
  quantisiert (GGUF, Ollama/LM Studio) auf einen normalen PC; Zugang auf Hugging Face erst nach Zustimmung zur
  Nutzungsrichtlinie. TagStudio bindet es nicht direkt ein, sondern über die OpenAI-kompatible Schnittstelle von
  Ollama/LM Studio – das Modell ist dort frei wählbar. Vor dem Entscheid: Probeübersetzung von ~50 echten TagStudio-
  Texten DE→EN und DE→Mundart, verglichen mit DeepL und einem grossen Modell (Entscheid User offen, Hinweis 16.10.2026).
- Übersetzt werden nur fehlende oder veraltete Einträge, in Paketen (z. B. 50 Texte) mit **Kontext** (Seite, Knopf
  oder Tooltip) und **Glossar**: feste Begriffe (TagStudio, Tagger, Cue, BPM, Camelot …) und Feldnamen/ID3-Schlüssel
  bleiben unverändert, Platzhalter `{n}` werden geschützt und danach geprüft.
- Ergebnis zuerst als **Vorschau** (alt → neu, mit Häkchen wie bei den Plugins), dann in die eigene Sprachdatei;
  Herkunft `ki`. Kosten-/Zeichenschätzung vor dem Start.

**Von Hand anpassen** (Einstellungen › Sprache › „Übersetzungen bearbeiten“):
- Tabelle Schlüssel · Kontext · Deutsch · Übersetzung · Herkunft, Filter „fehlt / KI / veraltet / manuell“, Suche.
- Ändern direkt in der Tabelle oder in der laufenden Oberfläche (Übersetzungsmodus: Text anklicken → bearbeiten);
  gespeichert wird sofort in die eigene Sprachdatei, Herkunft `manuell`; Rückgängig je Eintrag.
- Prüfungen beim Speichern: Platzhalter vollständig, keine HTML-Tags, Länge für Knöpfe (Warnung).
- Export/Import (CSV/JSON) wie oben bleibt für Übersetzungen ausserhalb von TagStudio.

**Übersetzungen melden** (aufbauend auf #187 „Melden“):
- „Übersetzung einreichen …“ erzeugt eine Datei nur mit den eigenen Änderungen (Sprache, Schlüssel, Text, Herkunft,
  TagStudio-Version) und öffnet das GitHub-Formular „Übersetzung“ (neue Vorlage, Labels `translation` + `triage`).
  Grosse Dateien passen nicht in die Adresse – die Datei wird gespeichert und im Formular angehängt (Ziehen).
- Übernahme in die Distribution nur nach Prüfung durch den Projektverantwortlichen: Werkzeug
  `tools/i18n_merge.py` prüft Schlüssel, Platzhalter, HTML, Länge und zeigt den Unterschied; Einreichungen sind
  unvertrauenswürdig (kein Code, keine Anweisungen).
- Mitwirkende werden auf Wunsch in der Hilfe genannt (Lizenz der Beiträge wie das Projekt, Hinweis im Formular).

## Umsetzung in Phasen

1. **Grundlage:** Kataloge, `t()`, `data-i18n`, Sprachwahl mit Flaggen, Export/Import; Seitenleiste, Einstellungen
   und Dialoge umgestellt; Schreibweise der Ausgangssprache vereinheitlicht.
2. **Module umstellen:** Tagger, Vergleich, Player, DJ-Set, Snapshots, Sicherungen, Plugins – je Modul ein Issue,
   mit einem Test, der in jeder Sprache alle Seiten öffnet und auf fehlende Schlüssel prüft.
3. **Englisch** vollständig übersetzen (Vorschlag: zuerst maschinell aus den Katalogen, dann durchsehen).
4. **Python-Meldungen und Plugins**, README/Hilfe auf Englisch (Kurzfassung).

5. **KI-Übersetzung, eigene Sprachdatei, Bearbeiten, Melden** (siehe oben) – kann direkt nach Phase 1 kommen und
   hilft dann schon bei Phase 3.

**Aufwand (Schätzung 2026-10-16, gemessen an 4.5.0):**
| Phase | Inhalt | Umfang |
|---|---|---|
| 1 Grundlage | `t()`, `data-i18n`, Kataloge, Sprachwahl, Rückfall, `Intl`, Extraktions-Werkzeug + Test „keine neuen festen Texte“ | ca. 1 Release (kleiner als 4.5.0) |
| 2 Umstellung | rund 2 500–3 000 Texte in Schlüssel überführen, alle Module | 2–3 Releases, grösster Teil, mechanisch, Risiko kleiner Fehler in der Oberfläche |
| 5 KI + eigene Datei + Editor + Melden | Übersetzungs-Plugins (zuerst DeepL und ein lokales Modell), Vorschau, Editor, Übersetzungsmodus, Vorlage „Übersetzung“, `i18n_merge.py` | ca. 1 Release |
| 3 Englisch | KI-Übersetzung Minuten, **Durchsicht durch den User** mehrere Stunden | Durchsicht ist der Engpass |
| 4 Python/Plugins/Doku | Meldungen, Plugin-Texte, README/Hilfe englisch (Kurzfassung) | 1 Release |
| Mundart | nur mit LLM sinnvoll, vollständige Durchsicht durch den User | nach Englisch |

Insgesamt rund **4–6 Releases** in der Grösse von 4.4/4.5. Bis Phase 2 abgeschlossen ist, bleiben einzelne Texte
deutsch – das ist gewollt (Fallback). Empfehlung: Phase 1 + 5 zusammen beginnen (dann kann der User sofort selbst
übersetzen lassen und prüfen), Phase 2 modulweise.

## Offene Fragen an den User

- Welcher KI-Dienst zuerst (Vorschlag: DeepL für Englisch, lokales Modell über Ollama für Datenschutz/Mundart)?
- Sollen Übersetzer in der Hilfe namentlich genannt werden (nur auf Wunsch)?

- Welche Mundart bzw. Schreibweise (Zürich, Bern, Basel …)?
- ~~Soll die Sprache der Oberfläche auch die Tags beeinflussen?~~ **Entschieden 16.10.2026: nein** – übersetzt werden
  nur die Texte der Oberfläche, MP3-Tags bleiben, wie sie sind.
