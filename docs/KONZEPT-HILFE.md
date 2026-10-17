# Konzept: Hilfe

Stand: 2026-10-11 (4.4.0) · Status: **umgesetzt in 4.3.0** (#158, #159) · nachträglich erstellt

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
- **Melden (#187):** Reiter „Melden“ und Knopf „Melden …“ im Tagger (Bereich Tagger vorgewählt) öffnen `fbOpen`
  (`web/feedback.js`, Modul `feedback.py`). Sicherer Start ohne Schreib-Token: TagStudio baut die Adresse des
  GitHub-Formulars (`issues/new?template=bug_report.yml|improvement.yml|feature_request.yml|translation.yml&title=…&<Feld-ID>=…`, Feld-IDs wie in
  `.github/ISSUE_TEMPLATE`) und öffnet sie nach Vorschau und ausdrücklicher Zustimmung im Browser; abgeschickt wird dort
  mit der eigenen GitHub-Anmeldung. Vorher werden Benutzerordner in Pfaden, E-Mail-Adressen und lange Schlüssel/Token
  geschwärzt; Version/System nur mit Häkchen; keine Protokolle, Dateien oder Liedtexte. Duplikatsuche über die
  öffentliche GitHub-Suche (nur lesend, ohne Anmeldung, 10/min; Fehler offline/Rate-Limit verständlich). Die Vorlagen
  setzen `fehler`/`verbesserung`/`funktion` + **`triage`** (nicht freigegeben); Freigabe nur durch den Owner (`_1 bereit`, AGENTS.md).
  Grenzen des sicheren Starts: Den Link des neuen Issues kennt TagStudio nicht (Absenden im Browser) – angeboten wird
  „Meine Meldungen“ (`author:@me`). Eine integrierte Meldemaske mit OAuth bleibt eine spätere Option.
- **Übersetzung einreichen (#232):** vierte Art im Melden-Dialog und Knopf „Eigene Texte einreichen …“ in den
  Spracheinstellungen. `feedback.own_texts(lang)` liefert nur eigene Texte, die von der mitgelieferten Fassung abweichen
  (JSON), Vorlage `translation.yml` (Felder `language`, `texts`, `note`), Labels `funktion` + `triage`, Meilenstein
  „Funktionen“. Zu viele Texte für die Adresse → im Formular ein Teil, „Alle Texte kopieren“ für den Rest. Übernahme in
  `web/i18n/*.json` erst nach Prüfung durch den Projektverantwortlichen.
- **GitHub-Repositories (#206):** Feld `repo` (owner/name) bei allen Komponenten von GitHub; der Workflow holt dazu
  `repo_info` (Sterne, letzter Push, archiviert, Diskussionen, Organisation) und meldet archivierte, über zwei Jahre
  stille, umbenannte oder nicht abrufbare Projekte im Issue (JSON-Schlüssel `_repo_info`, mit `--apply` übernehmen).
  Anzeige: Spalte „GitHub“ mit Link zum Repository und zum Entwickler-Profil, „Danke …“ (vorbereiteter Text, kopieren
  und als Diskussion bzw. Issue öffnen – TagStudio sendet nichts selbst) und eigene Häkchen „geprüft / gefolgt /
  bedankt“ (cfg `lic_review`, nur lokal, `help_lic_mark`).
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

## 5.1 Geplante Erweiterung: Rückmeldungen aus TagStudio (TODO)

**Noch nicht umgesetzt; offene Idee [#187](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/187), keine Implementierungsfreigabe.**

- Aus **HILFE** und direkt aus **TAGGER** «Fehler melden» und «Funktion vorschlagen» anbieten.
- Vor dem Versand eine Vorschau mit ausdrücklich bestätigter **Veröffentlichung als GitHub-Issue** zeigen; sensible Pfade, Logs, Musikdateien und Zugangsdaten nicht automatisch mitsenden.
- Anbindung über offizielle GitHub Issue Forms mit vorausgefüllten Angaben oder eine sicher authentifizierte Integration evaluieren. Keine Repository-Schreibtokens im ausgelieferten Client ablegen.
- Neu angelegte Meldungen bleiben **ungeprüft und nicht für Entwicklung freigegeben**. Nur eine ausdrückliche Bestätigung durch den Projektverantwortlichen darf sie in den bestehenden Freigabeprozess (z. B. manuelles Label `_1 bereit`) übernehmen. Das gilt ebenso für Claude, ChatGPT und Automationen.
- Bei der Umsetzung Rechteprüfung, Schutz gegen Spam/Missbrauch, Duplikate und UI-/Integrationstests vorsehen.

**Quelle:** Nutzeranforderung 14.10.2026; Issue #187.

## 6. Tests

`tests/test_taghelp.py`, `tests/test_id3frames.py`, `tests/test_third_party.py`, Oberflächen-Tests in `tests/test_browser_ui.py` (Hilfe).
