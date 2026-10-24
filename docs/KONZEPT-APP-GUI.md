# Konzept: App und Oberfläche (GUI)

Stand: 2026-10-15 (4.4.1-beta.6) · Status: **umgesetzt** (Web-Oberfläche seit 3.0, laufend erweitert) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am App-Rahmen
> (Fenster, Seitenleiste, Dialoge, Design, Start/Beenden, Protokoll) weitergearbeitet, ist es im selben Zug anzupassen.

## 1. Ziel

Ein ruhiges, schnelles App-Fenster für Windows und macOS, das alle Module unter einer Seitenleiste vereint, sich
Grösse, Layout und Zustand merkt und Fehler nachvollziehbar protokolliert – ohne Framework und ohne Build-Schritt.

## 2. Aufbau

- **Fenster:** `pywebview` (WebView2 unter Windows); ohne pywebview Browser-Modus über lokalen Server
  (`--browser`). Fenstersymbol, Titelleiste im Hell/Dunkel-Design (Windows DWM), Titel mit Profilname.
- **Seitenleiste** (Reihenfolge): Vorbereiten · Tagger · Tag-Fixer · Vergleich · DJ-Set · Snapshots · Sicherungen ·
  Plugins · Einstellungen · Hilfe · Datenbank (geplant, „bald“). Unten: Nach Update suchen, Versionshinweise,
  Einklappen, Hell/Dunkel, Vollbild/Fenster, Neu starten, Beenden. Menüpunkte ein-/ausblendbar, ★ = empfohlen (#169).
  Zahlen/Kennzeichen je Modul (z. B. neue Titel in Vorbereiten, Titel im DJ-Set, Snapshot-Speicher).
- **Start:** zuletzt benutzte Seite; Fenster in Grösse/Position vom letzten Mal (auch maximiert); Profilwahl, wenn
  mehrere Profile; beim ersten Start der Einrichtungsassistent, danach „Erste Schritte“ und „Neu in dieser Version“
  (siehe [KONZEPT-EINRICHTUNG.md](KONZEPT-EINRICHTUNG.md)).
- **Gemeinsame Bausteine:** `modal()` (Dialoge; frischer Inhalt je Dialog, wartet bei offenem Assistenten), `toast()`,
  Tooltips (`initTips`, farbige Hover-Infos), Fortschritts-Overlay, Aufträge-Chip in der Fusszeile, Statuszeile,
  Splitter (ziehen, ←/→, Doppelklick = Standard, gemerkt), Dateibrowser `pick_path` (startet im Basisordner).
- **Tooltips** (#192): nur eine sichtbare Art – `web/tooltips.js` übernimmt `title` und SVG-`<title>` in `data-tip-title` und zeigt alle Hinweise im App-Design, auch im abgedockten Player. Tests prüfen `data-tip-title`, nicht `title`.
- **Neustart im Browser-Modus** (#193): `appRestartNow` merkt sich `instance_id` (PID + Startzeit) und lädt die Seite erst neu, wenn eine andere Instanz antwortet.
- **Ordner und Pfade** werden einheitlich grün dargestellt (Klasse `.path-dir`, Farbe `--ok`; #177, #178).
- **Speichern und Undo:** global für Tagger und Vergleich (Strg/Cmd+S, Strg/Cmd+Z/Y), Konfliktschutz.
- **Beenden:** „Einstellungen werden gespeichert …“, Abfrage ungespeicherter Änderungen und laufender Aufträge;
  **nur eine Instanz** je Profil (Sperrdatei + Windows-Mutex).
- **Protokoll:** `Logs/app.log` (Start, Ende, Fehler, JS-Fehler über `client_log`; ab 1 MB `app.log.1`), Geheimnisse
  werden herausgefiltert; einsehbar unter Einstellungen › Expert.

## 3. Umsetzung

- **Python:** `tagstudio_web.py` (Api, `_PASS`-Weiterleitungen an die Session, Fenster, Dialoge, `restart`, `quit`,
  `window_mode`, `set_titlebar`, `expert_*`, Profile), `session.py` + Mixins (`session_*.py`), `instance.py`,
  `applog.py`, `paths.py`.
- **Web:** `web/index.html`, `web/app.css`, `web/app.js` (Grundgerüst, Vergleich, Update), `web/modules.js`
  (Modulwechsel, `modal`), je Modul eine eigene Datei (`tagger.js`, `prepare.js`, `djset.js`, `snapshots.js`,
  `settings.js`, `help.js`, `setup.js`, `profiles.js` …). HTML/CSS/JS ohne Framework, Systemschriften.
- **Einstellungen:** `web_theme`, `web_ui` (Splitter, Seitenleiste), `window`, `nav_hidden`, `nav_recommended`,
  `ui`-Schlüssel je Modul.

### 3.1 Zurück/Vorwärts zwischen Ansichten (#274, Entscheid User 24.10.2026)

- `web/nav.js`: Verlauf (höchstens 30 Stationen, nur laufende Sitzung). `setModule` merkt vor jedem **Sprung aus dem
  Inhalt** die bisherige Stelle (`navPush`); Klicks in der Seitenleiste (`{side: true}`), der Start und der Abschluss
  des Assistenten zählen nicht.
- Gemerkt je Seite (`navCapture`): Playlists (gewählte Playlist, Auswahl, Bildlauf), Tagger (Ordner, markierte Titel
  über den relativen Pfad, Suche, Playlist-Filter, Bildlauf – nur wiederhergestellt, wenn derselbe Ordner geladen ist),
  DJ-Set (markierter Titel), Vergleich (Paar), Hilfe (Reiter). Zurück macht **keine Aktion rückgängig** und lädt keinen
  Tagger-Ordner neu.
- Bedienung: Knopf „← Zurück“ oben in der Seitenleiste (Ziel als zweite Zeile und im Tooltip), „→“ nach einem
  Zurück, Rechtsklick = Liste der Stationen; Alt+←/→ überall ausser im Vergleich (dort Felder kopieren); Maustasten
  Zurück/Vorwärts (Taste 4/5, Browser-Navigation unterdrückt).
- Abweichung vom ersten Vorschlag: Knopf in der Seitenleiste statt im Seitenkopf, weil die Seiten keinen gemeinsamen
  Kopf haben; die Seitenleiste ist überall an derselben Stelle.

## 4. Entscheide

- Web-Oberfläche statt Qt (PySide6 brachte optisch keinen Vorteil); die klassische tkinter-Oberfläche ist
  eingefroren (#106).
- Gemeinsame Logik im Python-Kern mit Tests; die Oberfläche ruft nur Session-Methoden auf.
- Nicht gewählte Module werden im Assistenten nur als „empfohlen“ markiert, nicht ausgeblendet.

## 5. Offen / Ideen

- Mehrsprachigkeit: [KONZEPT-MEHRSPRACHIG.md](KONZEPT-MEHRSPRACHIG.md) (#157).
- Modul „Datenbank“ (Platzhalter in der Seitenleiste).
- #107 Werkzeugleiste mit Symbolen im Vergleich.

## 6. Tests

`tests/test_core_session.py`, `test_instance.py`, `test_paths.py`, `test_setup.py`, `test_gui_smoke.py` (klassische
Oberfläche, nur CI), Oberflächen-Tests in `tests/test_browser_ui.py`.
