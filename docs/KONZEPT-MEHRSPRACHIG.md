# Konzept: Mehrsprachigkeit

Status: **umgesetzt im Developer Release für 4.7.0** (17.10.2026, #157 und #219) – Abweichungen vom Entwurf siehe
„Umsetzung (Stand 17.10.2026)“; diese hat Claude während der autonomen Arbeit entschieden, der User prüft sie beim
Testen. Entwurf 2026-10-11; ergänzt 16./17.10.2026: Sprachcodes, Probeübersetzung, Entscheid „Claude übersetzt mit“,
Überlagerung in den Benutzereinstellungen.

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
| 🇨🇭 | Hochdeutsch (Schweiz, `de-CH`) | heutiger Text, Schreibweise vereinheitlicht – **Ausgangssprache** |
| 🇩🇪 | Deutsch (`de-DE`) | optional, mit „ß“ |
| 🇨🇭 | Schweizerdeutsch (Mundart) | eigener Katalog in Mundart, z. B. „Spichere“, „Abbräche“, „Iilääse“ |
| 🇬🇧 | English | vollständige Übersetzung |

**Sprachcodes (BCP 47, Entscheid 16.10.2026: Zürichdeutsch):**
| Code | Sprache | Rolle |
|---|---|---|
| `de-CH` | Schweizer Hochdeutsch (mit „ss“) | **Ausgangssprache** – so ist TagStudio heute geschrieben |
| `de-DE` | Deutsch (Deutschland, mit „ß“) | optional, weitgehend automatisch aus `de-CH` (ss → ß nach Wörterliste) |
| `gsw-u-sd-chzh` | Zürichdeutsch (Mundart) | `gsw` = Schweizerdeutsch, `sd-chzh` = Kanton Zürich |
| `en` | Englisch | erste Übersetzung |

Damit sind mehrere Mundarten nebeneinander möglich (z. B. `gsw-u-sd-chbe` Berndeutsch, `gsw-u-sd-chbs` Baseldeutsch);
fehlt ein Mundart-Text, gilt `gsw`, dann `de-CH`. Zahlen/Daten über `Intl` mit `de-CH` (1'234).

**Entscheid des Users (2026-10-11): Schweizerdeutsch = Mundart.** Mundart hat keine feste Rechtschreibung; der
Katalog folgt einer Schreibweise (Vorschlag: Zürichdeutsch nach Dieth, ohne Sonderzeichen ausser ä/ö/ü) und wird vom
User durchgesehen. Fehlt ein Mundart-Text, gilt Hochdeutsch.

## Umsetzung (Stand 17.10.2026)

Umgesetzt wurde eine **Übersetzungsschicht über dem DOM** statt Schlüsseln im Code (`t("tagger.load")`). Grund: rund
4 000 Texte in Vorlagen-Strings, Python-Meldungen und Plugins hätten einen Umbau jeder Zeile verlangt (Phase 2 mit
2–3 Releases und hohem Fehlerrisiko); die Schicht erreicht dasselbe ohne Eingriff in die Module.

- **Schlüssel = deutscher Ausgangstext** (`de-CH`). Kataloge je Bereich in `web/i18n/<bereich>.json`:
  `{"Deutscher Text": ["English", "Züritüütsch"]}` (Spalten nach `i18n.COLUMNS`). Für `de-CH` gibt es keine Datei.
  `web/i18n/ignore.json` listet Marken, Feldnamen und Code-Texte, die nie übersetzt werden.
- **Laufzeitform:** Zahlen werden zu `{n}`, Text in Anführungszeichen zu `{q}` (Inhalt wird mitübersetzt, Englisch
  mit “…”), im Code eingesetzte Teile zu `{x}` (rekursiv übersetzt). So deckt „{n} Datei(en) im Tagger“ jede Zahl ab.
- **`web/i18n.js`:** MutationObserver über Textknoten und die Attribute `title`, `data-tip-title`, `placeholder`,
  `aria-label`, `alt` (plus Knopf-`value`); Rückfälle: ganzer Text → zeilenweise → „Präfix: Rest“ → führendes „· “ →
  Teile zwischen „ · “ → Spaltenkopf mit Sortierzeichen → Aktionsname ohne „ …“. `translate="no"` schützt Daten
  (Dateinamen, Tag-Werte, Hilfe-Dokumente). `alert/confirm/prompt` werden übersetzt. `html.i18n-wait` verdeckt die
  Seite, bis die Sprache geladen ist (kein Aufblitzen).
- **Sprache:** UI-Schlüssel `lang` in der Einstellungsdatei: Sprachcode oder `auto` = „Sprache des Betriebssystems
  verwenden“ (beim allerersten Start gesetzt; bestehende Installationen ohne Wahl bleiben `de-CH`). Auswahl mit
  SVG-Flaggen unter Einstellungen › Darstellung, im Einrichtungsassistenten und als Auswahlliste unten in der
  Seitenleiste unter „Einklappen“ (eingeklappt nur die Flagge). Wechsel zurück auf Deutsch lädt die Seite neu.
- **Deutsch (Entscheid User 17.10.2026):** eine Sprache „Deutsch“ für Deutschland und die Schweiz (Code `de-CH`,
  Schreibweise mit „ss“), Flagge Deutschland/Schweiz diagonal geteilt. Systemsprache `de-*` → Deutsch. Ein eigenes
  `de-DE` ist damit nicht vorgesehen.
- **Python und Plugins:** Meldungen bleiben deutsch im Code und werden in der Oberfläche übersetzt. Plugins können in
  `plugin.json` `"i18n": {"en": {"Deutsch": "English"}}` mitbringen; die eingebauten stehen im Katalog.
- **Prüfung:** `tools/i18n_extract.py` sammelt Texte aus JS, HTML, Python (inkl. `label=`, Frame-Tabellen) und Plugins;
  `tests/test_i18n.py` verlangt, dass jeder Text in `en` und `gsw-u-sd-chzh` übersetzt ist. Der Oberflächentest
  `test_i18n_pages_english` öffnet alle Seiten auf Englisch und meldet deutsche Reste (sichtbar oder in der
  Fehlliste `I18N.miss`).
- **Eigene Texte (#219):** Einstellungen › Darstellung › Sprache: Export CSV (Excel, `;`, BOM) oder JSON mit Spalten
  `de-CH`, `en`, `gsw-u-sd-chzh`, `eigene:<sprache>`; Import mit Vorschau prüft unbekannte Texte, Platzhalter, HTML,
  Länge (Warnung) und unveränderte Texte; gespeichert in `~/TagStudio/Sprachen/<sprache>.json` (je Profil),
  überlagert Katalog und Plugin-Texte, „Eigene Texte zurücksetzen“ entfernt die Datei. Auch `de-CH` lässt sich so
  anpassen.
- **Dokumente:** `README.en.md`, `PLUGINS.en.md`, `docs/ID3-FELDER.en.md` (aus dem Katalog erzeugt); die Hilfe zeigt
  auf Englisch diese Fassungen, sonst die deutschen. Zürichdeutsch nutzt die deutschen Dokumente.
- **Schreibweise:** „ß“ in der Oberfläche durch „ss“ ersetzt (Filter versteht weiter „größer als“).
- **Nicht umgesetzt / offen:** Zahlen und Daten über `Intl` (nur Tausendertrenner im Englischen angepasst),
  englische Fassung der Konzept- und Projektdokumente (bleiben deutsch).

## Technik (Entwurf 2026-10-11, ersetzt durch „Umsetzung“)

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

## Übersetzung (Entscheid 17.10.2026)

**Ergebnis der Probe (16./17.10.2026):** 50 echte TagStudio-Texte, übersetzt von Apertus v1.5-70B (über Hugging Face)
und von Claude, bewertet vom User. Apertus: Englisch brauchbar mit Fehlern („Stufen“ → „Levels“, Sinnfehler bei
„nach links“), Mundart in keiner Variante (Zürich, Zürich mit Wortliste, Bern, Basel, allgemein) brauchbar, Platzhalter
teils verdoppelt. **Claude-Übersetzung am besten** (Englisch und Zürichdeutsch). Ergebnisse als Kommentare in #157
(Probe-Workflow nach dem Entscheid entfernt).

**Entscheid:**
- **Keine KI-Anbindung in TagStudio.** Die mitgelieferten Sprachen (`de-CH`, `en`, `gsw-u-sd-chzh`) übersetzt Claude
  direkt bei der Entwicklung: Jeder neue oder geänderte Text kommt im selben Commit in allen Sprachdateien an; der User
  prüft beim Testen. Ein Test stellt sicher, dass kein Schlüssel in einer mitgelieferten Sprache fehlt.
- **Bestehende Texte** (~3 000–3 500) werden beim Umbau (Phase 2) Modul für Modul gleich mitübersetzt.
- **Eigene Anpassungen (letzter Schritt):** Export/Import der Texte (CSV/JSON) für manuelle Anpassungen. Importierte
  Texte werden in den **Einstellungen des Benutzers** gespeichert (eigene Datei je Profil, z. B.
  `<Einstellungen>/Sprachen/<sprache>.json`) und **überlagern** die mitgelieferten Texte nur für diesen Benutzer;
  Updates überschreiben sie nie. Fehlt ein Eintrag, gilt der mitgelieferte, dann `de-CH`. „Zurücksetzen“ entfernt die
  eigenen Anpassungen. Import prüft Schlüssel, Platzhalter `{n}`, HTML und Länge (Warnung).
- **Einreichen (#232):** „Eigene Texte einreichen …“ bzw. Hilfe › Melden › „Übersetzung einreichen“ füllt die vom
  mitgelieferten Text abweichenden eigenen Texte (JSON) ins GitHub-Formular `translation.yml`; Übernahme nach Prüfung
  durch den Owner (siehe [KONZEPT-HILFE.md](KONZEPT-HILFE.md)).

**Tokenbedarf (Schätzung 17.10.2026, aus der Probe ~70 Tokens je Text):** Oberfläche + Meldungen + Plugins
~200 000–250 000 Tokens je Sprache, Doku (nur Englisch sinnvoll) ~60 000–80 000; Englisch + Zürichdeutsch zusammen
~0,5–0,7 Mio. Tokens. Danach je Release nur neue Texte (~5 000–15 000). Der eigentliche Aufwand ist der Umbau
(Texte aus dem Code in Sprachdateien), nicht das Übersetzen.

## Umsetzung in Phasen

1. **Grundlage:** Kataloge, `t()`, `data-i18n`, Sprachwahl mit Flaggen, Export/Import; Seitenleiste, Einstellungen
   und Dialoge umgestellt; Schreibweise der Ausgangssprache vereinheitlicht.
2. **Module umstellen:** Tagger, Vergleich, Player, DJ-Set, Snapshots, Sicherungen, Plugins – je Modul ein Issue,
   mit einem Test, der in jeder Sprache alle Seiten öffnet und auf fehlende Schlüssel prüft.
3. **Englisch** vollständig übersetzen (Vorschlag: zuerst maschinell aus den Katalogen, dann durchsehen).
4. **Python-Meldungen und Plugins**, README/Hilfe auf Englisch (Kurzfassung).

5. **Export/Import mit Überlagerung in den Benutzereinstellungen** (siehe oben) – letzter Schritt.

**Aufwand (Schätzung 2026-10-16, gemessen an 4.5.0):**
| Phase | Inhalt | Umfang |
|---|---|---|
| 1 Grundlage | `t()`, `data-i18n`, Kataloge, Sprachwahl, Rückfall, `Intl`, Extraktions-Werkzeug + Test „keine neuen festen Texte“ | ca. 1 Release (kleiner als 4.5.0) |
| 2 Umstellung | rund 2 500–3 000 Texte in Schlüssel überführen, alle Module | 2–3 Releases, grösster Teil, mechanisch, Risiko kleiner Fehler in der Oberfläche |
| 5 Export/Import + Überlagerung | eigene Anpassungen je Benutzer, Prüfung beim Import | klein |
| 3 Englisch + Zürichdeutsch | übersetzt Claude im Umbau gleich mit; User prüft beim Testen | ~0,5–0,7 Mio. Tokens |
| 4 Python/Plugins/Doku | Meldungen, Plugin-Texte, README/Hilfe englisch (Kurzfassung) | 1 Release |

Insgesamt rund **4–6 Releases** in der Grösse von 4.4/4.5. Bis Phase 2 abgeschlossen ist, bleiben einzelne Texte
deutsch – das ist gewollt (Fallback). Vorgehen (Entscheid 17.10.2026): Phase 1, dann Phase 2 modulweise mit Englisch und Zürichdeutsch im selben Zug,
zuletzt Phase 5.

## Offene Fragen an den User

- ~~Welcher KI-Dienst?~~ **Entschieden 17.10.2026: keiner** – Claude übersetzt bei der Entwicklung.
- Sollen Übersetzer in der Hilfe namentlich genannt werden (nur auf Wunsch)?

- ~~Welche Mundart?~~ **Entschieden 16.10.2026: Zürichdeutsch** (`gsw-u-sd-chzh`).
- ~~Soll die Sprache der Oberfläche auch die Tags beeinflussen?~~ **Entschieden 16.10.2026: nein** – übersetzt werden
  nur die Texte der Oberfläche, MP3-Tags bleiben, wie sie sind.
