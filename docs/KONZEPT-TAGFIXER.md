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
- **Spaltenbreite (#340, 4.12.0):** Vorschau-Tabelle mit Griffen wie bei den Käufen (`colResize(…, "fixer")`),
  gemerkt, bleibt bei jeder neuen Vorschau.
- **Ausnahmen je Feld (#342, 4.12.0):** cfg `fixer_exceptions` = `{Ziel: [Namen]}`; Ziel ist eine Gruppe aus
  `compare.EXCEPTION_GROUPS` (`@artists` Künstler und Mitwirkende, `@genre` TCON, `@mood` TMOO/TXXX:MOOD) oder ein
  einzelnes Feld. `exceptions_for(feld)` = eigene + Gruppe. `split_multi(…, exceptions)` ersetzt Treffer (Wortgrenzen,
  Leerzeichen beliebig, gross/klein egal, längste zuerst) vor dem Trennen durch Platzhalter und setzt sie danach
  unverändert wieder ein – „Above & Beyond“ bleibt auch in „Above & Beyond; Zoë Johnston“ zusammen. Gilt für
  `plan_multi_fix` und künftig Smart Fix (#339). Einstellungsgruppe „history“ (Export/Import). Keine mitgelieferte
  Grundliste – die Namen kommen aus der eigenen Sammlung.
- **Editor für Ausnahmen (#343, 4.12.0):** Knopf „Ausnahmen … (n)“ unter den Trennern, `web/fixerexc.js`. Feld/Gruppe,
  Suchtexte (Standard `&` plus die aktiven Trenner, mehrere mit Leerzeichen), Vorschläge aus allen geladenen Titeln
  (Vergleich + Tagger) über `Session.fixer_exception_candidates`: Feldwert an den übrigen aktiven Trennern zerlegt
  (ohne die, die einen Suchtext enthalten), Teile mit Suchtext, Anzahl Titel. Häkchen + „Angehakte übernehmen (n)“,
  rechts die Liste (bearbeiten, ✕ entfernen, von Hand hinzufügen). Bestehende Ausnahmen in den Vorschlägen
  ausgeblendet; „Bestehende Ausnahmen anzeigen“ bzw. Auge je Eintrag blendet sie ein, Zeile markiert mit „Ausnahme“.
  Gespeichert erst mit „Speichern“ (`set_fixer_exceptions`, bereinigt).
- **Auswahl in der Vorschau (#341, 4.12.0):** Häkchen-Spalte (Standard an), Kopf alle/keine (halb bei Teilauswahl),
  Umschalt-Klick für Bereiche, Zähler „x von y Änderung(en) werden ausgeführt“. Jede Zeile hat die Kennung
  `Session._fixer_id` (Pfad, Feld, neuer Wert); `fixer_apply` erhält die **abgewählten** Kennungen (`skip`) – Zeilen
  jenseits der ersten 3000 angezeigten werden also ausgeführt. Eine Rückgängig-Stufe für das Ausgeführte.
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

- Mögliche Ausbauten: eigene Trennzeichen eingeben; abgewählte Vorschau-Zeilen direkt als Ausnahme übernehmen (#341).

## 6. Tests

`tests/test_compare_backup.py`, `tests/test_tagger.py` (Fixer über die Tagger-Auswahl), `tests/test_recipes.py`.
