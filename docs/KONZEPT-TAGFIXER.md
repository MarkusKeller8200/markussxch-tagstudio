# Konzept: Tag-Fixer

Stand: 2026-10-25 (4.12.0, #344) · Status: **umgesetzt** (seit 2.x, in der Web-Oberfläche seit 3.0) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am Tag-Fixer
> weitergearbeitet, ist es im selben Zug anzupassen (Funktionen, Umsetzung, Entscheide, Offen).

## 1. Ziel

Mehrfachwerte (mehrere Künstler, Genres …) stehen je nach Programm unterschiedlich in den Tags: `A; B`, `A / B`,
`A \\ B` (Mp3tag), `A feat. B` oder als echter ID3v2.4-Mehrfachwert (NULL-getrennt). Der Tag-Fixer vereinheitlicht das
über viele Dateien – mit laufender Vorschau und Rückgängig.

## 2. Funktionen

- **Bereich:** aktuelles Paar, eine Seite, markierte Paare, alle Dateien (Vergleich) oder die Tagger-Auswahl.
- **Felder:** Standard die Mehrfach-Felder `TPE1 TPE2 TPE3 TPE4 TCOM TEXT TOLY TOPE TCON TSOP TSO2 TSOC TMCL TIPL`,
  optional alle Textfelder.
- **Erkannte Trenner** (je an/aus): NULL (v2.4), `;`, ` / `, `\\` (Mp3tag) – Standard an; `,`, `/` (Achtung AC/DC),
  `&`, ` feat. `/` ft. `, ` x ` – Standard aus.
- **Ausgabe:** ein Trennzeichen nach Wahl oder echte ID3v2.4-Mehrfachwerte (dann wird beim Speichern v2.4 geschrieben);
  doppelte Werte entfernen.
- **Trennzeichen als Code (#344, 4.12.0):** Zeichen getrennt von der Beschreibung als `code` (`translate="no"`),
  Leerzeichen als `␣`, Null-Trenner als `\0`, Beschreibung als Tooltip; `feat.` zeigt auch `ft.`/`featuring`. Der
  Ausgabe-Trenner hat eine laufende Code-Vorschau. Gemeinsame Hilfe `sepCode()` (`web/app.js`) – auch für den
  Ausnahmen-Editor (#343) und Smart Fix (#339).
- **Vorschau** je Datei und Feld (alt → neu), anwenden mit Undo; geschrieben wird mit „Speichern“.

## 3. Umsetzung

- **Kern:** `compare.py` – `MULTI_FIELDS`, `INPUT_SEPARATORS` (Beschreibung ohne Zeichen), `sep_code`/`sep_codes`, `split_multi`, `fix_multi`, `plan_multi_fix`.
- **Session:** `fixer_settings`, `fixer_preview`, `fixer_apply` in `session.py`.
- **Oberfläche:** Seite „Tag-Fixer“ (`web/modules.js`), aufrufbar auch aus Tagger und Vergleich.
- **Einstellungen:** `fixer` (gewählte Trenner, Felder, Ausgabe).

## 4. Entscheide

- `/` ohne Leerzeichen und `,` sind standardmässig aus, weil sie in Namen vorkommen (AC/DC, „Earth, Wind & Fire“).
- Ähnliche Aufgaben (Wortschreibweise, nur ersten Wert behalten, Duplikate) gibt es zusätzlich als Aktionen der
  Tag-Rezepte (`recipes.py`, #111).

## 5. Offen / Ideen

- Keine offenen Issues. Mögliche Ausbauten: eigene Trennzeichen eingeben, Ausnahmeliste für Namen mit Trennern.

## 6. Tests

`tests/test_compare_backup.py`, `tests/test_tagger.py` (Fixer über die Tagger-Auswahl), `tests/test_recipes.py`.
