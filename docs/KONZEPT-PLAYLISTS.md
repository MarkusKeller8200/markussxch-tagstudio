# Konzept: Playlists

> Stand 24.10.2026 – Entwurf auf Wunsch des Users. Status **Idee**: keine Umsetzung ohne Freigabe (`_1 bereit`).
> Issues: #267 (Grundlage) · #268 (Tagger) · #269 (DJ-Set) · #270 (Player, Warteschlange, Vorbereiten) ·
> #271 (Import/Export, Ordner-Spiegel) · #272 (Smartlists) · #273 (Austausch mit DJ-Programmen und Plugins)

## 1. Ziel

Titel aus dem **Tagger** und aus dem **DJ-Set** sollen in **Playlists** abgelegt werden können. Die Playlists werden an
einer Stelle **verwaltet** (anlegen, ordnen, umbenennen, prüfen, exportieren) und lassen sich überall wieder öffnen:
im Tagger zum Bearbeiten, im DJ-Set zum Optimieren, im Player zum Abspielen.

Eine Playlist ist eine **Liste von Verweisen auf Dateien**. TagStudio ändert dabei die MP3-Dateien nicht. Ausnahme ist
eine ausdrückliche Aktion wie „Spurnummern schreiben“. Fremde Bibliotheken (Engine DJ, Serato, Rekordbox, Lexicon …)
werden nie direkt verändert. Der Austausch läuft über Dateien (M3U8, XML) oder über freigegebene Plugin-Wege.

## 2. Ausgangslage (Stand 4.8.0-beta.2)

Es gibt bereits mehrere Teile, aber keine gemeinsame Verwaltung:

| Vorhanden | Wo | Grenze |
|---|---|---|
| Gespeicherte DJ-Set-Listen (Titel, Sperren 🔒, Optionen) | `session_djset.py` `dj_save_as/dj_load/…`, cfg `djset_saved`, `djset_name` | nur auf der Seite DJ-Set; liegen in `~/.tagstudio.json` (wächst mit jeder Liste); keine Ordner, keine Suche |
| Warteschlange des Players | cfg `player_queue`, `pq_*`, `web/queue.js` | flüchtig gedacht, nur „ins Set übernehmen“ |
| Exporte M3U8, Rekordbox-XML, CSV | `setexport.py`, `dj_export_file` | nur für das aktuelle DJ-Set |
| Rekordbox-XML lesen | `setexport.read_rekordbox` | nicht in der Oberfläche als Playlist-Import |
| Playlists aus Lexicon holen (#242) und DJ-Set als Lexicon-Playlist anlegen (#239) | `Manager.playlist_sources/call_playlist`, Plugin `lexicon` | landen als DJ-Set-Liste „Lexicon: …“ |
| Temporäre M3U8 für externe Player | `players.write_m3u` | nur intern |

## 3. Vorschlag in Kürze

1. **Neues Modul „Playlists“** im Menü (zwischen DJ-Set und Snapshots) mit Baum (Ordner, Playlists), Titelliste und
   Werkzeugen. Das ist die **Verwaltung**.
2. **Ein gemeinsamer Playlist-Speicher** für alle Bereiche. Die heutigen DJ-Set-Listen werden einmalig übernommen. Das
   DJ-Set bleibt der **Optimierer** und arbeitet auf einer Playlist („DJ-Set = Playlist mit Set-Optionen“).
3. **„Zur Playlist hinzufügen ›“** überall, wo Titel markiert werden: Tagger, DJ-Set, Player, Warteschlange, Vorbereiten.
4. **Export und Import** über offene Formate (M3U8, Rekordbox-XML, CSV), optional ein **Spiegel-Ordner**, in dem alle
   Playlists automatisch als M3U8 liegen, damit DJ-Programme sie einlesen können.
5. Später **Smartlists** (Regeln über Tag-Felder) und der Austausch mit DJ-Programmen über Plugins.

## 4. Datenmodell

```json
{
  "format": 1,
  "id": "pl_7f3c…",                 // fest, ändert sich beim Umbenennen nicht
  "name": "Freitag Warm-up",
  "folder": "Sets/2026",            // Ordnerpfad im Baum ("" = oberste Ebene)
  "kind": "manual",                 // manual | djset | smart | import | queue
  "color": "#4a90d9", "note": "",   // optional
  "created": 1761300000, "modified": 1761303600,
  "source": {"plugin": "lexicon", "id": "123", "path": "Sets/Freitag"},   // nur bei Importen
  "djset": {"opts": {…}},           // nur kind=djset: Set-Optionen (heute djset_opts)
  "rules": {…},                     // nur kind=smart (Abschnitt 9)
  "items": [
    {"path": "S:/_MP3/01_Library/…/Titel.mp3", "size": 9876543, "akey": "…", "added": 1761300000,
     "lock": true, "note": ""}
  ]
}
```

- **Titel-Identität:** In erster Linie der **Pfad**. Dazu kommen Grösse und, wenn vorhanden, der **Audio-Schlüssel**
  (`akey`), wie ihn Snapshots und Wellenform-Cache bereits verwenden. Damit lassen sich verschobene Titel
  wiederfinden (Abschnitt 7, „Fehlende suchen“).
- **Doppelte Titel:** In einer Playlist erlaubt, beim Hinzufügen gibt es aber einen Hinweis und die Wahl „trotzdem“
  oder „überspringen“. In einer DJ-Set-Playlist gibt es keine Doppelten, wie heute.
- **Keine Tag-Werte in der Playlist.** Titel, BPM, Tonart usw. kommen beim Anzeigen aus dem Tagger bzw. aus dem
  Listen-Cache. Damit bleibt die Playlist klein und nie veraltet.

## 5. Speicher

Vorschlag (Entscheid E3):

```
~/TagStudio/Playlists/            (je Profil, wie Vorbereiten/Entdecken)
  index.json                      Ordner, Reihenfolge, zuletzt benutzt, Spiegel-Einstellungen
  pl_7f3c….json                   eine Datei je Playlist (atomar schreiben, wie save_config)
  papierkorb/                     gelöschte Playlists 30 Tage (Wiederherstellen)
```

- Eine Datei je Playlist bedeutet kleine Schreibvorgänge und keine Konflikte bei langen Listen. Die Einstellungsdatei
  bleibt schlank.
- **Sicherung:** Die Playlists kommen in die Einstellungs-Sicherung (Export/Import, Gruppe „playlists“) und optional
  in den Snapshot-Speicher.
- **Übernahme:** Beim ersten Start mit dem Modul werden `djset_saved` → `kind: djset` (Name, Titel, Sperren, Optionen)
  und `player_queue` → `kind: queue` (eine feste Playlist „Warteschlange“) übernommen. Die alten Einträge bleiben
  eine Version lang lesbar und werden danach nicht mehr geschrieben.
- Neues Modul `playlists.py` (Kern, nur stdlib) und `session_playlists.py` (Mixin), Oberfläche `web/playlists.js`.
  Modul in `packaging/build.py` unter `HIDDEN`, Methoden in `_PASS`.

## 6. Verwaltung (Seite „Playlists“)

```
┌ Playlists ──────────────────┬─ Freitag Warm-up · 24 Titel · 1:52 h · 2 fehlen ──────────────────────┐
│ 🔍 Suchen                   │ [▶ Abspielen] [Im Tagger öffnen] [Im DJ-Set öffnen] [Export ▾] [⋯]    │
│ ★ Zuletzt benutzt           │ #  Titel / Künstler         BPM  Tonart  Länge  ★   Ordner             │
│ ▾ 📁 Sets                   │ 1  Opening – A. Artist      122  8A      6:12   ★★★ 01_Library/House   │
│    ▾ 📁 2026                │ 2  …                                                                   │
│       🎛 Freitag Warm-up    │ ⚠ 7  (fehlt) Track.mp3 — „Fehlende suchen …“                           │
│ 📋 Neu 2026-10              │                                                                        │
│ ⚡ Smart: 124–128 BPM, ★≥4  │                                                                        │
│ ⏭ Warteschlange             │                                                                        │
│ [+ Playlist] [+ Ordner]     │                                                                        │
└─────────────────────────────┴────────────────────────────────────────────────────────────────────────┘
```

**Baum:** Ordner beliebig tief, Ziehen zum Umsortieren und Verschieben. Symbole je Art: 📋 normal, 🎛 DJ-Set,
⚡ Smart, ⇣ Import, ⏭ Warteschlange. „Zuletzt benutzt“ oben (fünf Einträge).

**Aktionen je Playlist:** Neu, Umbenennen (F2), Duplizieren, In Ordner verschieben, Farbe/Notiz, Zusammenführen
(mehrere → neue), **Löschen** mit Rückfrage und Papierkorb, Rückgängig/Wiederholen für alle Änderungen.

**Titelliste:** Spalten wie im Tagger (wählbar), Sortieren, Ziehen zum Umordnen, Entf entfernt (nur aus der Playlist,
nie die Datei), Doppelklick spielt, Kontextmenü „Im Tagger zeigen“, „Im Ordner zeigen“, „Zu anderer Playlist ›“.

**Kopfzeile:** Anzahl, Gesamtdauer, fehlende Titel, Verteilung BPM/Tonart als kleine Leiste.

**Prüfen:** „Fehlende suchen …“ sucht verschobene Titel über Grösse + Audio-Schlüssel im Basisordner bzw. in
gewählten Ordnern und zeigt eine Vorschau „alt → neu“. Gesucht wird nur in Ordnern, die der Benutzer freigibt.

## 7. Anbindung der Bereiche

| Bereich | Neu |
|---|---|
| **Tagger** | Kontextmenü und Werkzeugleiste „Zur Playlist hinzufügen ›“ (zuletzt benutzte, „Neue Playlist aus Auswahl …“); Taste **Strg+Shift+P** (zuletzt benutzte Playlist); „Playlist öffnen …“ lädt die Titel wie Lexicon-Öffnen (`start_tag_load_files`); Spalte/Filter „In Playlist“ |
| **DJ-Set** | Liste „Speichern/Laden“ wird zu „Als Playlist speichern“/„Playlist öffnen“; jede Playlist lässt sich im DJ-Set öffnen (wird dabei `kind: djset` mit Optionen, das Original bleibt auf Wunsch unverändert); markierte Set-Titel „Zur Playlist ›“ |
| **Player / Warteschlange** | „Playlist abspielen“ (Player folgt der Playlist-Reihenfolge wie heute dem Set), Warteschlange = feste Playlist, „Warteschlange als Playlist speichern“, Titel im Player „Zur Playlist ›“ |
| **Vorbereiten** | neuer Workflow-Schritt „In Playlist aufnehmen“ (z. B. „Neu {Jahr}-{Monat}“) bei der Übernahme in die Bibliothek |
| **Snapshots** | Pfad-Änderungen aus dem Journal („umbenannt“) können Playlists nachführen (Vorschau) |
| **Plugins** | gemeinsamer Rahmen statt „Lexicon: …“-DJ-Set-Listen (Abschnitt 10) |

## 8. Import und Export, Spiegel-Ordner

**Export** (je Playlist, mehrere oder ein ganzer Ordner): M3U8 (absolute oder relative Pfade, `#EXTINF` mit Dauer,
Künstler – Titel), Rekordbox-XML (mehrere Playlists mit Ordnerbaum in **einer** Datei), CSV/Excel (wie Tagger-Export).
Vorhanden in `setexport.py`, wird auf Playlists verallgemeinert.

**Import:** M3U/M3U8 (auch relative Pfade, Windows-/Mac-Pfade, Umlaute), Rekordbox-XML (`read_rekordbox`, Ordner →
Playlist-Ordner), CSV mit Pfadspalte. Titel, die nicht gefunden werden, bleiben als „fehlt“ in der Playlist.

**Spiegel-Ordner (optional):** Alle oder gewählte Playlists werden bei jeder Änderung als M3U8 in einen Ordner
geschrieben, z. B. `01_Library/_Playlists/Sets/2026/Freitag Warm-up.m3u8` mit relativen Pfaden. Vorteile: Die
Playlists reisen mit der Bibliothek, und DJ-Programme können den Ordner einlesen. TagStudio schreibt dort nur eigene
`.m3u8`-Dateien und löscht nur Dateien, die es selbst angelegt hat (Liste im `index.json`), nach Rückfrage.

## 9. Smartlists (später)

Regeln über die Felder, die der Tagger-Filter schon kennt: Genre, BPM-Bereich, Tonart (auch „passend zu 8A“),
Bewertung, Like, Stimmung, Energie, Aufgenommen/Bearbeitet (Zeitraum), Herkunft, Kommentar enthält … Verknüpfung
„alle“/„eine“, Sortierung, Höchstzahl. Datenbasis (Entscheid E4): der Listen-Cache bzw. der Bibliotheks-Scan
(`cache/tagscan`) des Basisordners. Damit wird nichts neu eingelesen, die Liste ist aber nur so aktuell wie der letzte
Scan. „Jetzt aktualisieren“ startet einen Hintergrund-Auftrag. Eine Smartlist lässt sich in eine normale Playlist
„einfrieren“.

## 10. Austausch mit DJ-Programmen und Plugins (später)

Rahmen im Plugin-Manager (verallgemeinert aus #242/#239):

- `playlists(ctx)` → Baum der Playlists einer Quelle (gibt es), `playlist_files(ctx, id)` (gibt es)
- **neu** `playlist_push(ctx, playlist, options)` → Playlist im Zielprogramm anlegen oder aktualisieren (nur wenn das
  Plugin das anbietet und das Schreiben eingeschaltet ist, wie bei Lexicon). Nie löschen, Journal + Rückgängig.
- Seite Playlists: „Importieren aus ›“ und „Senden an ›“ mit den bereiten Plugins.

Reihenfolge nach Nutzerpriorität (Architekturkonzept): **Engine DJ** (über Lexicon oder M3U8-Import, nie direkt in
die Engine-Datenbank), **Serato** (Crates, erst nach Test mit Serato 4.x), **VirtualDJ** (M3U8, am Produkt testen),
**Traktor** (NML), **Rekordbox** (XML, vorhanden). Jedes Format wird in einem echten Test mit dem Programm des Users
bestätigt, bevor es als „unterstützt“ gilt.

## 11. Offene Entscheide (für den User)

| Nr. | Frage | Vorschlag |
|---|---|---|
| E1 | Eigenes Menü-Modul „Playlists“ oder nur ein Bereich im DJ-Set? | **eigenes Modul**; DJ-Set bleibt der Optimierer |
| E2 | Die heutigen DJ-Set-Listen in die Playlists übernehmen (ein gemeinsamer Speicher)? | **ja**, einmalig und automatisch |
| E3 | Speicherort: Programmdaten je Profil oder im Basisordner (reist mit der Musik)? | **Programmdaten** + optionaler M3U8-Spiegel im Basisordner |
| E4 | Smartlists: Datenbasis Bibliotheks-Scan (schnell, nicht immer aktuell) oder nur geladener Tagger-Ordner? | **Bibliotheks-Scan** mit „Jetzt aktualisieren“ |
| E5 | Doppelte Titel in einer Playlist? | **erlaubt mit Hinweis**, im DJ-Set nicht |
| E6 | Zugehörigkeit zusätzlich in die Tags schreiben (z. B. `TXXX:TAGSTUDIO_PLAYLISTS`)? | **nein** (Dateien bleiben unverändert, Tag-Änderung bei jeder Listenänderung wäre störend) |
| E7 | Welches DJ-Programm zuerst? | M3U8-Spiegel (für alle) → Engine DJ über Lexicon → Serato |
| E8 | Gelöschte Playlists: Papierkorb 30 Tage oder sofort weg (nach Rückfrage)? | **Papierkorb** |

## 12. Umsetzung in Schritten

| Phase | Inhalt | Issue | Grösse |
|---|---|---|---|
| 1 | Kern `playlists.py`, Speicher, Übernahme DJ-Set-Listen/Warteschlange, Seite „Playlists“ mit Baum, Liste, Aktionen, Undo, Papierkorb | #267 | gross |
| 1 | Tagger: „Zur Playlist ›“, „Playlist öffnen“, Filter „In Playlist“ | #268 | mittel |
| 1 | DJ-Set auf Playlists umstellen | #269 | mittel |
| 2 | Player, Warteschlange, Vorbereiten-Schritt | #270 | mittel |
| 2 | Import/Export M3U8, Rekordbox-XML, CSV; Spiegel-Ordner; „Fehlende suchen“ | #271 | mittel |
| 3 | Smartlists | #272 | mittel |
| 3 | `playlist_push`, Lexicon umstellen, weitere DJ-Programme nach Test | #273 | gross |

Phase 1 reicht für den Kernwunsch: Titel aus Tagger und DJ-Set in Playlists ablegen und verwalten. Vorschlag: Phase 1
und 2 als Meilenstein **4.9.0 – Playlists**.

## 13. Tests

- Unit: `tests/test_playlists.py` (Datenmodell, atomares Schreiben, Übernahme aus `djset_saved`, Doppelte, Papierkorb,
  M3U8 rund herum mit Umlauten und relativen Pfaden, Rekordbox-XML mit Ordnern, „Fehlende suchen“ mit verschobener
  Datei), Plattform-neutrale Pfade (Windows-Laufwerke).
- Oberfläche (Playwright): Playlist anlegen, aus dem Tagger hinzufügen, im DJ-Set öffnen, umordnen, löschen und
  wiederherstellen, Export-Dialog, englische Oberfläche ohne deutsche Reste.
- Mehrsprachigkeit: alle Texte in `web/i18n/playlists.json` (Deutsch, Englisch, Zürichdeutsch).
