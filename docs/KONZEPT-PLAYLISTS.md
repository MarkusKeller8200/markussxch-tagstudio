# Konzept: Playlists

> Stand 24.10.2026 – Entscheide E1–E8 des Users (13:03, Abschnitt 11). **Phase 1 umgesetzt** (#267–#269, Auftrag
> User 13:08, kommt in **4.8.0-beta.3**, Abschnitt 14). Phase 2 (#270, #271) im Meilenstein **4.9.0 – Playlists**,
> Phase 3 (#272, #273) Idee.
> Issues: #267 (Grundlage) · #268 (Tagger) · #269 (DJ-Set) · #270 (Player, Warteschlange, Vorbereiten) ·
> #271 (Import/Export, Quellen, Playlist-Ordner) · #272 (Smartlists) · #273 (Austausch mit DJ-Programmen und Plugins)

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
4. **Eigener Playlist-Ordner** in der Ordnerstruktur (`03_Playlists`, wie `01_Library` für die MP3): Dort liegen alle
   Playlists immer als M3U8, gespiegelt aus dem Playlist-Speicher (E3).
5. **Quellen:** Playlists entstehen aus Tagger, DJ-Set, Dateien, Lexicon und später MixID oder 1001Tracklists. Alle
   laufen über einen gemeinsamen Quellen-Rahmen (Abschnitt 7a, E4).
6. **Archiv statt Löschen**, wie bei den Tracks (Aussortieren nach `02_Archiv`, E8).
7. **Export und Import** über offene Formate (M3U8, Rekordbox-XML, CSV), später **Smartlists** und der Austausch mit
   DJ-Programmen über Plugins.

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
- **Doppelte Titel (E5):** In einer Playlist **erlaubt**. Beim Hinzufügen erscheint ein Hinweis mit der Wahl
  „trotzdem“ oder „überspringen“. Im DJ-Set-Optimierer bleibt jeder Titel einmal, weil sich sonst keine Reihenfolge
  berechnen lässt. Beim Öffnen im DJ-Set werden Doppelte gemeldet.
- **Keine Tag-Werte in der Playlist.** Titel, BPM, Tonart usw. kommen beim Anzeigen aus dem Tagger bzw. aus dem
  Listen-Cache. Damit bleibt die Playlist klein und nie veraltet.

## 5. Speicher

Entscheid E3: **Programmdaten + eigener Playlist-Ordner.**

```
~/TagStudio/Playlists/            Playlist-Speicher (je Profil, wie Vorbereiten/Entdecken) – massgebend
  index.json                      Ordner, Reihenfolge, zuletzt benutzt, Liste der geschriebenen M3U8
  pl_7f3c….json                   eine Datei je Playlist (atomar schreiben, wie save_config)

<Basisordner>/03_Playlists/       Playlist-Ordner (neu in der Ordnerstruktur, Name änderbar)
  Sets/2026/Freitag Warm-up.m3u8  jede Playlist als M3U8, Unterordner = Ordner im Baum
  Neu 2026-10.m3u8

<Basisordner>/02_Archiv/_Playlists/   archivierte Playlists (Abschnitt 6a)
```

- Der **Speicher** enthält alles (Sperren, Set-Optionen, Regeln, Notizen). Der **Playlist-Ordner** enthält dieselben
  Playlists als M3U8 mit **relativen Pfaden** zur Musik, ist für Menschen und DJ-Programme lesbar und reist mit der
  Bibliothek mit. Er wird bei jeder Änderung nachgeführt.
- **Änderungen von aussen:** Wird eine M3U8 im Playlist-Ordner von einem anderen Programm geändert oder neu angelegt,
  meldet TagStudio das beim nächsten Öffnen der Seite („3 Playlists im Ordner geändert – übernehmen?“, Vorschau).
  Es überschreibt nichts stillschweigend.
- Der Einrichtungsassistent und Einstellungen › Speicherort und Ordner bekommen den Eintrag `playlists`
  („03_Playlists – Playlists als M3U8“) in `session_setup.STRUCTURE`. Ohne Basisordner gibt es keinen Spiegel, nur den
  Speicher.

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
(mehrere → neue), **Archivieren** (statt Löschen, Abschnitt 6a), Rückgängig/Wiederholen für alle Änderungen.

**Titelliste:** Spalten wie im Tagger (wählbar), Sortieren, Ziehen zum Umordnen, Entf entfernt (nur aus der Playlist,
nie die Datei), Doppelklick spielt, Kontextmenü „Im Tagger zeigen“, „Im Ordner zeigen“, „Zu anderer Playlist ›“.

**Kopfzeile:** Anzahl, Gesamtdauer, fehlende Titel, Verteilung BPM/Tonart als kleine Leiste.

**Prüfen:** „Fehlende suchen …“ sucht verschobene Titel über Grösse + Audio-Schlüssel im Basisordner bzw. in
gewählten Ordnern und zeigt eine Vorschau „alt → neu“. Gesucht wird nur in Ordnern, die der Benutzer freigibt.

### 6a. Archiv (E8, wie bei den Tracks)

Wie „Aussortieren“ bei Titeln (`archive.py`, #173): Eine Playlist wird nicht gelöscht, sondern **archiviert**.

- Im Speicher bekommt sie den Vermerk `archived` (Datum) und erscheint im Baum unter **🗄 Archiv** (eingeklappt,
  durchsuchbar, Inhalt ansehen und abspielen möglich, nicht bearbeitbar).
- Ihre M3U8 wandert aus `03_Playlists` nach `02_Archiv/_Playlists/` (Unterordner bleiben erhalten).
- Jede Bewegung steht im Vermerk `_aussortiert.csv` im Archiv (Datum, Von, Nach, Bereich „Playlists“), derselbe
  Vermerk wie bei den Titeln. Daraus lässt sich die Playlist **zurückholen**.
- Ganze Ordner lassen sich archivieren. Endgültiges Löschen gibt es nur im Archiv, einzeln, mit Rückfrage.
- Wird ein **Titel** aussortiert, bleibt er in den Playlists stehen und wird als „im Archiv“ markiert (nicht „fehlt“).
  „Zurückholen“ des Titels stellt den alten Pfad wieder her.

## 7. Anbindung der Bereiche

| Bereich | Neu |
|---|---|
| **Tagger** | Kontextmenü und Werkzeugleiste „Zur Playlist hinzufügen ›“ (zuletzt benutzte, „Neue Playlist aus Auswahl …“); Taste **Strg+Shift+P** (zuletzt benutzte Playlist); „Playlist öffnen …“ lädt die Titel wie Lexicon-Öffnen (`start_tag_load_files`); Spalte/Filter „In Playlist“ |
| **DJ-Set** | Liste „Speichern/Laden“ wird zu „Als Playlist speichern“/„Playlist öffnen“; jede Playlist lässt sich im DJ-Set öffnen (wird dabei `kind: djset` mit Optionen, das Original bleibt auf Wunsch unverändert); markierte Set-Titel „Zur Playlist ›“ |
| **Player / Warteschlange** | „Playlist abspielen“ (Player folgt der Playlist-Reihenfolge wie heute dem Set), Warteschlange = feste Playlist, „Warteschlange als Playlist speichern“, Titel im Player „Zur Playlist ›“ |
| **Vorbereiten** | neuer Workflow-Schritt „In Playlist aufnehmen“ (z. B. „Neu {Jahr}-{Monat}“) bei der Übernahme in die Bibliothek |
| **Snapshots** | Pfad-Änderungen aus dem Journal („umbenannt“) können Playlists nachführen (Vorschau) |
| **Plugins** | gemeinsamer Rahmen statt „Lexicon: …“-DJ-Set-Listen (Abschnitt 10) |

### 7a. Quellen (E4)

Playlists können aus verschiedenen Quellen entstehen. Alle laufen über **einen Rahmen**: Eine Quelle liefert eine
Liste von Einträgen (Pfad, oder Künstler/Titel/Mix/ISRC/Dauer, wenn es keine Datei gibt), daraus wird eine Playlist.
Einträge ohne Datei werden über den **Bibliotheks-Abgleich** zugeordnet (vorhanden / fehlt / unklar, mit Vorschau und
Bestätigung, Radio Edit ≠ Extended Mix).

| Quelle | Weg | Phase |
|---|---|---|
| Tagger | markierte oder gefilterte Titel, ganzer Ordner | 1 |
| DJ-Set | aktuelles Set, markierte Set-Titel | 1 |
| Warteschlange | „als Playlist speichern“ | 2 |
| Datei | M3U/M3U8, Rekordbox-XML, CSV, Playlist-Ordner `03_Playlists` | 2 |
| Lexicon | Plugin `playlists`/`playlist_files` (#242) | 2 (Umstellung) |
| Smartlist | Regeln über Tag-Felder (Abschnitt 9) | 3 |
| Serato, Engine DJ, VirtualDJ (#278) | Bibliothek des Programms nur lesen (Crates, Datenbank-Kopie, Ordner/Playlists) | 4.8.0 |
| Trackliste einfügen (#279) | kopierter Text von 1001Tracklists, MixID, Beatport … → Einträge ohne Datei → Abgleich | 4.8.0 |
| Spotify-Export (#279) | CSV von Exportify, TuneMyMusic u. a. (Titel, Künstler, ISRC, Dauer) über „Datei …“ | 4.8.0 |
| Spotify, SoundCloud (#280) | Plugins mit eigener App des Users: Playlists, Lieblingssongs/Likes → Einträge ohne Datei mit Link | 4.8.0 |
| MixID (#218), 1001Tracklists (#180), Beatport-Playlists | direkter Abruf; Rechte bzw. Zugang vorher klären (Anfrage an 1001Tracklists vom User) | später |
| SonoVault (#258), Entdecken | Neuerscheinungen als „Merkliste“-Playlist (fehlende Titel = Einkaufsliste) | später |

**Fehlende Titel** aus externen Quellen bleiben als Einträge ohne Datei in der Playlist (grau, mit Künstler/Titel).
Sie lassen sich als Einkaufsliste exportieren (CSV) und werden später automatisch verknüpft, wenn der Titel in die
Bibliothek kommt (Abgleich bei der Übernahme in „Vorbereiten“). Datenmodell dafür: Eintrag mit `ref`
(`{"artist", "title", "mix", "isrc", "duration", "source"}`) statt oder zusätzlich zu `path`.

## 8. Import und Export, Playlist-Ordner

**Export** (je Playlist, mehrere oder ein ganzer Ordner): M3U8 (absolute oder relative Pfade, `#EXTINF` mit Dauer,
Künstler – Titel), Rekordbox-XML (mehrere Playlists mit Ordnerbaum in **einer** Datei), CSV/Excel (wie Tagger-Export).
Vorhanden in `setexport.py`, wird auf Playlists verallgemeinert.

**Import:** M3U/M3U8 (auch relative Pfade, Windows-/Mac-Pfade, Umlaute), Rekordbox-XML (`read_rekordbox`, Ordner →
Playlist-Ordner), CSV mit Pfadspalte. Titel, die nicht gefunden werden, bleiben als „fehlt“ in der Playlist.

**Playlist-Ordner `03_Playlists`** (Abschnitt 5): immer eingeschaltet, sobald ein Basisordner gewählt ist. TagStudio
schreibt dort nur eigene `.m3u8`-Dateien. Umbenennen und Verschieben im Baum benennen bzw. verschieben die Datei mit.
Archivieren verschiebt sie nach `02_Archiv/_Playlists`. Fremde Dateien im Ordner werden nie gelöscht.

## 9. Smartlists (umgesetzt in #272, siehe Abschnitt 18)

Regeln über die Felder, die der Tagger-Filter schon kennt: Genre, BPM-Bereich, Tonart (auch „passend zu 8A“),
Bewertung, Like, Stimmung, Energie, Aufgenommen/Bearbeitet (Zeitraum), Herkunft, Kommentar enthält … Verknüpfung
„alle“/„eine“, Sortierung, Höchstzahl. **Datenbasis wählbar** (E4): Bibliothek (Listen-Cache bzw. Bibliotheks-Scan
`cache/tagscan` des Basisordners, „Jetzt aktualisieren“ als Hintergrund-Auftrag), der geladene Tagger-Ordner, eine
andere Playlist oder eine Quelle aus Abschnitt 7a (z. B. Lexicon). Eine Smartlist lässt sich in eine normale Playlist
„einfrieren“.

## 10. Austausch mit DJ-Programmen und Plugins (Senden an Lexicon umgesetzt in #273, siehe Abschnitt 19)

Rahmen im Plugin-Manager (verallgemeinert aus #242/#239):

- `playlists(ctx)` → Baum der Playlists einer Quelle (gibt es), `playlist_files(ctx, id)` (gibt es)
- **neu** `playlist_push(ctx, playlist, options)` → Playlist im Zielprogramm anlegen oder aktualisieren (nur wenn das
  Plugin das anbietet und das Schreiben eingeschaltet ist, wie bei Lexicon). Nie löschen, Journal + Rückgängig.
- Seite Playlists: „Importieren aus ›“ und „Senden an ›“ mit den bereiten Plugins.

Reihenfolge nach Nutzerpriorität (Architekturkonzept): **Engine DJ** (über Lexicon oder M3U8-Import, nie direkt in
die Engine-Datenbank schreiben – **lesen** einer Kopie seit #278), **Serato** (Crates, erst nach Test mit Serato 4.x), **VirtualDJ** (M3U8, am Produkt testen),
**Traktor** (NML), **Rekordbox** (XML, vorhanden). Jedes Format wird in einem echten Test mit dem Programm des Users
bestätigt, bevor es als „unterstützt“ gilt.

## 11. Entscheide (User 24.10.2026, 13:03)

| Nr. | Frage | Entscheid |
|---|---|---|
| E1 | Eigenes Modul oder Bereich im DJ-Set? | **Eigenes Modul** „Playlists“; DJ-Set bleibt der Optimierer |
| E2 | DJ-Set-Listen übernehmen? | **Ja**, einmalig und automatisch |
| E3 | Speicherort? | **Programmdaten** (massgebend) **plus eigener Ordner** `03_Playlists` in der Ordnerstruktur, alle Playlists als M3U8 (Abschnitt 5) |
| E4 | Datenbasis / Quellen? | **Verschiedene Quellen** über einen Rahmen: Lexicon, Datei, Tagger, DJ-Set, später MixID, 1001Tracklists u. a. (Abschnitt 7a); Smartlists mit wählbarer Datenbasis |
| E5 | Doppelte Titel? | **Erlaubt** (mit Hinweis); nur der DJ-Set-Optimierer braucht jeden Titel einmal |
| E6 | Zugehörigkeit in Tags schreiben? | **Nein** |
| E7 | Welches DJ-Programm zuerst? | Wie vorgeschlagen: Playlist-Ordner (M3U8) → Engine DJ über Lexicon → Serato |
| E8 | Löschen? | **Archiv wie bei den Tracks** (Abschnitt 6a) |

## 12. Umsetzung in Schritten

| Phase | Inhalt | Issue | Grösse |
|---|---|---|---|
| 1 | Kern `playlists.py`, Speicher, Übernahme DJ-Set-Listen/Warteschlange, Seite „Playlists“ mit Baum, Liste, Aktionen, Undo, Archiv | #267 | gross |
| 1 | Tagger: „Zur Playlist ›“, „Playlist öffnen“, Filter „In Playlist“ | #268 | mittel |
| 1 | DJ-Set auf Playlists umstellen | #269 | mittel |
| 2 | Player, Warteschlange, Vorbereiten-Schritt | #270 | mittel |
| 2 | Import/Export M3U8, Rekordbox-XML, CSV; Playlist-Ordner `03_Playlists`; Quellen-Rahmen mit Bibliotheks-Abgleich; „Fehlende suchen“ | #271 | gross |
| 3 | Smartlists | #272 | mittel |
| 3 | `playlist_push`, Lexicon umstellen, weitere DJ-Programme nach Test | #273 | gross |

Phase 1 reicht für den Kernwunsch: Titel aus Tagger und DJ-Set in Playlists ablegen und verwalten. Phase 1 und 2
bilden den Meilenstein **4.9.0 – Playlists**. Offen: Soll der Playlist-Ordner schon in Phase 1 kommen (er ist klein
und macht die Playlists sofort für DJ-Programme nutzbar)? Vorschlag: ja, als Teil von #267.

## 13. Tests

- Unit: `tests/test_playlists.py` (Datenmodell, atomares Schreiben, Übernahme aus `djset_saved`, Doppelte, Archiv und Zurückholen, Playlist-Ordner (Umbenennen, Verschieben, Änderung von aussen), Einträge ohne Datei,
  M3U8 rund herum mit Umlauten und relativen Pfaden, Rekordbox-XML mit Ordnern, „Fehlende suchen“ mit verschobener
  Datei), Plattform-neutrale Pfade (Windows-Laufwerke).
- Oberfläche (Playwright): Playlist anlegen, aus dem Tagger hinzufügen, im DJ-Set öffnen, umordnen, archivieren und
  zurückholen, Export-Dialog, englische Oberfläche ohne deutsche Reste.
- Mehrsprachigkeit: alle Texte in `web/i18n/playlists.json` (Deutsch, Englisch, Zürichdeutsch).

## 14. Umsetzung Phase 1 (#267–#269, 24.10.2026)

**Kern `playlists.py`** (nur Standardbibliothek), Klasse `Store(root, mirror, archive_dir)`:

- Speicher `~/TagStudio/Playlists/` (je Profil): `index.json` (`folders`, `recent`, `written` = je Playlist
  relativer Pfad + SHA-256 der zuletzt geschriebenen M3U8, `ignored` = fremde Dateien, `migrated`) und
  `pl_<id>.json`. Einträge: `path`, `size`, `added`, `lock`, `note` und – nur für die `#EXTINF`-Zeile der M3U8 –
  `artist`, `title`, `dur` (beim Hinzufügen aus dem Tagger gefüllt; angezeigt werden die aktuellen Tag-Werte).
  `ref` für Einträge ohne Datei ist vorgesehen (#271).
- Namen sind je Ordner eindeutig (Gross-/Kleinschreibung egal); `unique_name` für Kopien („Name (Kopie)“).
- Rückgängig/Wiederholen im Speicher (`_change` merkt die betroffenen Playlists und Ordner, höchstens 50 Schritte);
  Archivieren ist kein Rückgängig-Schritt (dafür „Zurückholen“).
- **Playlist-Ordner** `sync(ids)`: schreibt M3U8 mit relativen Pfaden (`setexport.m3u8`), benennt beim Umbenennen
  oder Verschieben die eigene Datei mit um, entfernt sie, wenn die Playlist wegfällt – aber nur, wenn die Datei noch
  unverändert ist (SHA-256 wie geschrieben). Fremde oder von aussen geänderte Dateien bleiben stehen
  (`external_changes`: `changed`, `removed`, `new`; `apply_external(rel, take|keep|archive)`; `.m3u` wird als
  Playlist übernommen und daneben eine eigene `.m3u8` geschrieben). Dateinamen: verbotene Zeichen → `_`, reservierte
  Windows-Namen mit `_`, Kollisionen mit „(2)“. Unterordner `_Archiv` und versteckte Ordner werden nicht gelesen.
- **Archiv** wie `archive.py`: M3U8 nach `<Archiv>/_Playlists/<Ordner>/…` (ohne Archiv-Ordner:
  `<Playlist-Ordner>/_Archiv`), Zeile in `_aussortiert.csv` mit Bereich „Playlists“; `restore` holt sie zurück
  (bei belegtem Namen mit „(2)“) und vermerkt „zurückgeholt“. `delete` nur für archivierte Playlists.
- `parse_m3u`: `#EXTINF` (Dauer, „Künstler - Titel“), relative Pfade, `file://`-Adressen, Windows-Pfade auch auf
  macOS/Linux.
- `migrate_djset`: übernimmt `djset_saved` einmalig (Ordner „DJ-Sets“, Art `djset`, Sperren, Optionen; „Lexicon: X“
  → Ordner „Lexicon“, Art `import`). `djset_saved` bleibt in der Einstellungsdatei stehen (eine Version lang lesbar),
  wird aber nicht mehr geschrieben.

**Sitzung `session_playlists.py`** (`PlaylistMixin`): Playlist-Ordner = cfg `playlist_dir`, sonst
`<base_dir>/03_Playlists`; `pl_state(sel)` liefert Baum, Archiv, Zuletzt benutzt, Rückgängig-Stand, Zahl der
Änderungen von aussen und die Titel der gewählten Playlist mit Angaben aus dem Tagger bzw. – für nicht geladene –
direkt aus der Datei (zwischengespeichert nach Grösse/Änderungszeit); fehlende Titel, die im Archiv-Vermerk stehen,
sind „im Archiv“. Weitere Befehle: `pl_list`, `pl_create`, `pl_add_tag`/`pl_add_paths` (`dupes` ask/add/skip),
`pl_remove`, `pl_order`, `pl_rename`, `pl_move`, `pl_meta`, `pl_duplicate`, `pl_merge`, `pl_folder_*`,
`pl_archive`, `pl_restore`, `pl_delete`, `pl_undo`/`pl_redo`, `pl_tag_indices`, `pl_files`, `pl_external*`,
`set_playlist_dir`; Api `pl_reveal`. „Zurückholen“ unter Einstellungen › Aussortierte holt auch Playlists zurück.

**DJ-Set (#269):** `session_djset.py` speichert und lädt über den Playlist-Speicher (cfg `djset_pl` = id der
bearbeiteten Playlist, `djset_name` bleibt für Plugins nachgeführt). `dj_save_as` legt neue Playlists im Ordner
„DJ-Sets“ an (`djset.opts` = Set-Optionen), `dj_load(id|Name)` lässt Doppelte weg und meldet sie, `dj_list_delete`
archiviert. „Aus Lexicon …“ legt Playlists im Ordner „Lexicon“ an bzw. aktualisiert sie über `source`.

**Oberfläche:** `web/playlists.js` (Seite, Baum mit Ziehen, Titelliste mit Mehrfachauswahl, Tasten ↑/↓, Alt+↑/↓,
Entf, Enter, F2, Strg+Z/Y, Strg+A; Auswahldialog `plsPick`; `plsAddDialog`, `plsQuickAdd`, `plsMenuItems`),
Tagger-Menü „Playlist ▾“ und Filter-Chip `#tgPlFilter` (`tgSetPlFilter`), Player folgt der Playlist-Reihenfolge
auf der Seite (`plsTarget/plsStep/plsNextTag/plsSelectTag`), Einstellungen › Speicherort und Ordner „Playlist-Ordner“,
Ordnerstruktur `03_Playlists` (`session_setup.STRUCTURE`), Menüpunkt `playlists` (ausblendbar), Erste Schritte.
Übersetzungen in `web/i18n/playlists.json`.

Phase 2 siehe Abschnitt 15.

**Tests:** `tests/test_playlists.py` (Speicher, Rückgängig, Ordner, Archiv, Playlist-Ordner, Änderungen von aussen,
Übernahme, Sitzung mit Tagger/DJ-Set/Archiv/Einstellung), Oberflächentest `test_playlists_page`; angepasst
`test_queue_and_saved_lists`, `test_dj_lexicon_playlists`, `tests/test_lexicon.py`, `tests/test_setup.py`.

## 15. Umsetzung Phase 2 (#270, #271 – vom User am 24.10.2026 in 4.8.0 übernommen)

**#270 Player, Warteschlange, Vorbereiten**
- **„▶ Abspielen“** (`plsPlayStart`): merkt die Reihenfolge der Playlist (`PLS.play`); solange ein Titel daraus läuft,
  folgt der Player ihr auf jeder Seite (`plsPlayActive` in `plStep`, Titelende, Überblenden nur mit im Tagger geladenen
  Titeln). Nicht geladene Titel spielt der Player direkt über die Art **„file“** – `session_player._resume_file` erlaubt
  dafür Pfade aus `player_resume` **oder aus einer aktiven Playlist** (`_pl_has_path`), weiterhin kein beliebiger
  Dateizugriff.
- **Warteschlange:** bleibt eine eigene, flüchtige Liste (Entscheid bei der Umsetzung: kein Umbau zu einer festen
  Playlist, weil sie sich beim Spielen laufend leert). Dazu „Als Playlist speichern …“ im Warteschlangen-Dialog und
  „Mehr ▾ → In die Warteschlange“ (`pl_to_queue`, nur im Tagger geladene Titel).
- **Player-Menü:** „Laufenden Titel zur Playlist hinzufügen …“.
- **Vorbereiten:** Schritt „Übernahme“ hat das Feld `playlist` (Name mit Platzhaltern `{Jahr}`, `{Monat}`, `{Tag}`,
  `{Workflow}`, Ordner mit „/“) → `_pl_prep_add` legt die Playlist bei Bedarf an und überspringt Doppelte.

**#271 Quellen, Import/Export, Fehlende**
- Einträge **ohne Datei** (`ref`: `artist`, `title`, `mix`, `isrc`, `dur`, `source`) – in der Liste „ohne Datei“,
  nicht in der M3U8.
- **Abgleich** (`playlists.match_ref`, `start_pl_match`): Bibliothek = Tagger-Standardordner, Bibliothek des Workflows,
  `<Basisordner>/01_Library` (mit Listen-Cache), dazu die im Tagger geladenen Titel. Gleiche ISRC oder gleicher
  Künstler + Titel + Mix (ohne Akzente/Satzzeichen, „feat.“ und „Original Mix“ zählen nicht) = gefunden; anderer Mix
  oder mehrere Treffer = unklar; Dauer > 20 s daneben = unklar. Auswahl im Dialog, `pl_relink` (rückgängig machbar).
- **Toleranter Abgleich (#281):** `mix_key` (Extended Mix = Extended = Extended Version; Original Mix, Remastered =
  ohne Angabe; Remixe behalten den Namen), Mix auch nach „ - “ und aus TIT3; `LibIndex` (Nachschlagen über ISRC, Titel,
  Künstler); Rückfall Ähnlichkeit ≥ 88 % bei passendem Künstler; je Zeile `reason` und ein Vorschlag `path` für
  unklare (★, vorgewählt nur mit „Vorschläge vorwählen“). Option „Anderer Mix gilt als gefunden“ (`cfg
  pl_match_any_mix`, Rangfolge `MIX_RANK`: Extended, ohne Angabe, Club …). Vorab-Dialog mit den gesuchten Ordnern und
  „Anderer Ordner …“ (`start_pl_match(pid, folder, any_mix)`).
- **#282:** `start_pl_match(target, folder, any_mix, roots)` – `target` Playlist-ID oder `{"folder": …}` ("" = alle),
  `roots` = angehakte Bibliotheken; Zeilen mit `pid`, Übernahme mit `pl_relink_many`. Vorschläge ★ standardmässig
  vorgewählt. Erneutes Holen aus einer Quelle (`start_dj_source_import`): `playlists.keep_links` (Link, ISRC bzw.
  Künstler + Titel + Mix, Sperre/Notiz bleiben), danach `_pl_auto_match` (nur sichere Treffer).
- **Automatisch verknüpfen** (`_pl_autolink`): nach der Übernahme in „Vorbereiten“ werden sichere Treffer in allen
  Playlists eingetragen.
- **Fehlende suchen** (`start_pl_find_missing`): gleicher Dateiname in den Bibliotheksordnern oder einem gewählten
  Ordner, gleiche Grösse eindeutig = vorgewählt.
- **Import** (`pl_import_file`, Api `pl_import` mit Dateidialog): M3U/M3U8 (`parse_m3u`), Rekordbox-XML mit Ordnerbaum
  (`read_rekordbox_tree`), CSV (`parse_csv`: `;`, `,` oder Tab; Spalten Pfad/Künstler/Titel/Mix/ISRC/Dauer, sonst
  „Künstler - Titel“ je Zeile); Plugins über `start_pl_source_import` (wie „Aus Lexicon …“, ohne ins DJ-Set zu laden).
- **Export** (`pl_export_file`, Api `pl_export`): M3U8 absolut/relativ, CSV, Rekordbox-XML für eine Playlist oder einen
  ganzen Ordner mit Ordnerbaum (`rekordbox_tree`, Sammlung ohne Doppelte). **Einkaufsliste** (`pl_shopping_file`).

**Tests:** `tests/test_playlists.py` (`TestMatchImport`, Sitzung Import/Export/Abgleich/Fehlende, Abspielen ohne Tagger,
Warteschlange, Vorbereiten, automatisches Verknüpfen), Oberflächentest `test_playlists_play_import`.

## 16. Import aus DJ-Programmen und Online-Quellen (#278, #279 – vom User am 24.10.2026 in 4.8.0 übernommen)

**#278 Serato, Engine DJ, VirtualDJ, Lexicon** – `djlibs.py`, **nur lesen**, die Bibliotheken der Programme bleiben
unverändert (Test vergleicht Prüfsummen vor und nach dem Lesen).
- **Serato:** `_Serato_/Subcrates/*.crate` (Datensätze `otrk` › `ptrk`, UTF-16BE); „%%“ im Dateinamen = Unter-Crate.
  Pfade sind relativ zum Laufwerk, auf dem `_Serato_` liegt (`serato_base`: `~/Music/_Serato_` → Systemlaufwerk,
  `/Volumes/USB/_Serato_` bzw. `E:\_Serato_` → dieses Laufwerk). Smart-Crates werden (noch) nicht gelesen.
- **Engine DJ 2.x–4.x:** `Engine Library/Database2/m.db` wird samt `-wal` in einen Arbeitsordner kopiert und dort
  gelesen; Reihenfolge über `nextListId` bzw. `nextEntityId`, Ordner über `parentListId`, Pfade relativ zu „Engine
  Library“. Ältere Datenbanken (Engine Prime 1.x) melden „zu alt“.
- **VirtualDJ:** `Folders/**/*.vdjfolder` (feste virtuelle Ordner, Filter-Ordner übersprungen) und
  `Playlists/*.m3u` mit `#EXTVDJ`-Angaben (Künstler, Titel, Länge).
- **Lexicon:** wie bisher über das Plugin (`start_pl_source_import`).
- Standardorte (`find_libraries`): Musik-Ordner bzw. Dokumente des Benutzers, `Library/Application Support`,
  `%LOCALAPPDATA%`, externe Laufwerke; sonst Ordner wählen (Api `pl_dj_pick`).
- Ablauf: `start_pl_dj_scan` (Liste mit Anzahl, fehlenden Dateien, „schon übernommen“) → Auswahl →
  `start_pl_dj_import` legt Playlists im Ordner `<Programm>/<Ordner im Programm>` an; Quelle
  `{"plugin": "app:<serato|engine|vdj>", "id": "<Pfad im Programm>"}` → erneuter Import aktualisiert dieselbe Playlist.
- Noch mit den echten Programmen des Users zu bestätigen (Abschnitt 10): Serato 4.x, Engine DJ 4.x, VirtualDJ 2025.

**#279 Online-Quellen, Schritt 1 (ohne Zugangsdaten, ohne Abruf fremder Seiten)**
- **„Trackliste einfügen …“** (`playlists.parse_tracklist`, `pl_import_text`): je Zeile „Künstler - Titel (Mix)“;
  Nummern, Zeitmarken, „w/“ und ein Label in eckigen Klammern am Ende fallen weg, „ID - ID“ wird gezählt und
  ausgelassen. Ergebnis: Einträge ohne Datei im Ordner der gewählten Quelle (1001Tracklists, MixID, Beatport,
  Spotify, sonst „Tracklisten“) → „Mit Bibliothek abgleichen …“.
- **Spotify-Exporte** als CSV über „Datei …“: Spalten „Track Name“, „Artist Name(s)“, „ISRC“, „Duration (ms)“.
- **Schritt 2:** Spotify und SoundCloud als Plugins (#280, unten); Beatport-Playlists offen; 1001Tracklists nur mit
  Erlaubnis (#180 – Anfrage um API-Zugang vom User vorbereitet); MixID über #218.

**#280 Spotify und SoundCloud** (Entscheid User 24.10.2026: Premium und eigene Spotify-App vorhanden, SoundCloud
Artist Pro vorhanden, möglichst alle Lese-Endpunkte, in 4.8.0). `plugins/spotify`, `plugins/soundcloud`, Anmeldung
über `oauthkit.py` (PKCE). `playlist_files` liefert `items` mit `ref` (Künstler, Titel, Mix, ISRC, Dauer, `source`,
`url`); `start_dj_source_import` übernimmt sie unverändert. `ref.url` (nur `https://`) erscheint als „↗“ in der Liste
und als Spalte „Link“ in der Einkaufsliste. Tests: `tests/test_spotify_soundcloud.py`, UI `test_spotify_soundcloud_plugins`.

**Tests:** `tests/test_djlibs.py` (Serato, Engine, VirtualDJ, unverändert nach dem Lesen, Tracklisten, Spotify-CSV,
Sitzung mit erneutem Import), Oberflächentest `test_playlists_dj_and_text_import`.

## 17. Phase 3 – offene Entscheide für 4.9.0 (Vorbereitung 25.10.2026)

Meilenstein #24 „4.9.0 – Playlists Phase 3“: #272 Smartlists, #273 Senden an DJ-Programme, #284 Beatport-Playlists.
**Entscheid User 25.10.2026, 01:16:** #222 (Wellenform im MP3) und #107 (Werkzeugleiste im Vergleich) **nicht** in
4.9.0 (zurück in die Sammlungen Funktionen bzw. Verbesserungen); alle übrigen Vorschläge **so umsetzen** – die Spalte
„Vorschlag“ gilt damit als beschlossen (W1 bleibt offen, bis #222 eingeplant wird).

| Nr. | Frage | Vorschlag |
|---|---|---|
| S1 | Datenbasis der Smartlists | Bibliothek (Listen-Cache bzw. Scan der Bibliotheksordner) – wahlweise geladener Tagger-Ordner oder eine andere Playlist |
| S2 | Regeln | Felder wie der Tagger-Filter: Genre, BPM-Bereich, Tonart (auch „passt zu 8A“), Bewertung, Like, Stimmung, Energie, Aufgenommen/Bearbeitet (Zeitraum), Herkunft, Kommentar; „alle“/„eine“ Regel erfüllt |
| S3 | Aktualisierung | beim Öffnen und auf Knopfdruck; kein Dauerlauf im Hintergrund |
| S4 | M3U8 im Playlist-Ordner | ja, beim Aktualisieren neu geschrieben; „Einfrieren“ macht eine normale Playlist daraus |
| S5 | Sortierung, Höchstzahl | wählbar (z. B. BPM aufsteigend, höchstens 50) |
| P1 | Zielprogramm für „Senden an“ zuerst | Lexicon (Local API, Plugin vorhanden; Schreiben dort schon mit Einschalter) |
| P2 | Verhalten beim Senden | Playlist im Zielprogramm anlegen bzw. ersetzen, nie löschen; Journal und Rückgängig; Einträge ohne Datei werden ausgelassen und gemeldet |
| P3 | Serato/Engine/VirtualDJ direkt schreiben | vorerst nein (nur lesen); Austausch über M3U8 im Playlist-Ordner – fremde DJ-Datenbanken nur nach ausdrücklicher Freigabe |
| B1 | Beatport-Listen (#284) | eigene Playlists; Charts von Künstlern/Labels optional |
| W1 | Wellenform im MP3 (#222) | nur auf Wunsch (Einstellung, Standard aus), eigenes GEOB „TagStudio Overview“, nie Serato-Felder überschreiben |


## 18. Umsetzung Smartlists (#272, 25.10.2026)

- **Modul `smartlist.py`** (nur Standardbibliothek): `FIELDS` (Feld → Bezeichnung, Art), `OPS` je Art (Text:
  enthält/enthält nicht/ist/leer/nicht leer; Zahl: zwischen/mindestens/höchstens/gleich; Tonart: ist (Liste)/passt zu
  (`keys.compatible`); Ja/Nein; Liste (Stimmung); Datum: letzte n Tage/ab/vor; Herkunft: hat (keine) Felder von),
  `clean()` prüft und vereinheitlicht die Regeln (ungültige Einzelregeln fallen weg), `values(f, origin_of)` liest alle
  Regel-Felder einer `MP3File`, `apply()` filtert, sortiert (fehlende Werte ans Ende, „Zufall“) und kürzt.
- **Speicher:** Playlist `kind = "smart"` mit `rules` und `refreshed`; `Store.smart_fill()` setzt die Einträge
  (Rückgängig nur bei echter Änderung, sonst nur Zeitpunkt), `Store.freeze()` → `kind = "manual"`. `add`/`remove`/
  `order` sind für Smartlists gesperrt (`Store._hand`). `duplicate` übernimmt die Regeln.
- **Sitzung** (`session_playlists.py`): `pl_smart_info` (Felder, Vergleiche, Sortierungen, Herkünfte, Playlists,
  Bibliotheksordner), `pl_smart_save`, `start_pl_smart_refresh` (Hintergrund-Vorgang mit Fortschritt),
  `pl_smart_stale` (älter als 15 Minuten), `pl_smart_freeze`. Datenbasis „Bibliothek“ = `_pl_lib_roots()` mit
  Listen-Cache, geladene Tagger-Titel gehen vor (ungespeicherte Änderungen zählen); keine Smartlist als Datenbasis
  einer Smartlist. Herkunft über `Session._src` (wie die Kennzeichen im Tagger).
- **Oberfläche:** „+ Smartlist“, Baum-/Ordnermenü „Neue Smartlist …“, Kopf mit Regel-Zusammenfassung, „↻ Aktualisieren“,
  „Regeln …“, Mehr ▾ › „Einfrieren …“; Regel-Dialog mit Datenbasis, alle/eine, Regelzeilen (Feld, Vergleich, Wert),
  Sortierung, absteigend, Höchstzahl. Beim Öffnen wird neu gebildet, wenn älter als 15 Minuten (je Sitzung nur ein
  automatischer Versuch). Smartlists erscheinen nicht als Ziel in „Zur Playlist hinzufügen …“.
- **Nicht umgesetzt:** Quelle aus Abschnitt 7a (z. B. Lexicon) als Datenbasis – geht über Import + „Aus Playlist“.
- **Tests:** `tests/test_smartlist.py`, Oberflächentest `test_playlists_smartlist`.

## 19. Umsetzung Senden an DJ-Programme (#273, 25.10.2026)

- **Rahmen** (`plugins.py`): Plugin-Funktion `playlist_push(ctx, playlist, options)` (über `Manager.call_playlist`,
  Protokoll in `<plugin>.log`), optional `push_ready(ctx)` → `(bereit, Hinweis)`; `Manager.push_targets()` liefert die
  eingeschalteten, bereiten Plugins mit `playlist_push`.
- **Sitzung:** `pl_push_targets`, `start_pl_push(pid, plugin, opts)` (Hintergrund-Vorgang). Übergeben werden Name,
  Ordner, Einträge (Pfad, Künstler, Titel) und `remote` = die beim letzten Senden zurückgegebene ID; die neue ID steht
  danach in der Playlist unter `pushed[plugin] = {id, at}` (`Store.set_pushed`, ohne Rückgängig-Eintrag), der Kopf zeigt
  „gesendet an … <Datum>“.
- **Lexicon** (Plugin 2.2, Entscheide P1/P2): nur mit Hauptschalter „Zurückschreiben“ und nur an localhost
  (`writer`). Zuordnung Datei → Lexicon-Titel nur über den Pfad (`Matcher`, ohne Künstler+Titel). Erstes Senden bzw.
  Ziel in Lexicon nicht mehr vorhanden oder keine normale Playlist: neue Playlist (oberste Ebene, `POST /playlist`) +
  `PATCH /playlist-tracks`. Erneutes Senden: `plan_inserts(have, want)` fügt fehlende Titel an ihrer Stelle ein
  (`PATCH /playlist-tracks` mit `index`); Titel, die nur in Lexicon stehen, bleiben und werden gemeldet;
  abweichende Reihenfolge wird nicht korrigiert, doppelte Titel kommen nur einmal hinein. **Nie** `DELETE` – auch nicht
  zum Ersetzen (die Local API bietet laut OpenAPI kein Ersetzen des Inhalts; `PATCH /playlist` nicht genutzt).
  Journal im Plugin (`playlist` bzw. `playlist_tracks`); „Letzte Änderung rückgängig …“ lässt angelegte Playlists und
  eingefügte Titel wie bisher stehen (TagStudio löscht nichts in Lexicon).
- **P3:** Serato, Engine DJ und VirtualDJ werden nicht beschrieben – Austausch über die M3U8 im Playlist-Ordner.
- **Tests:** `tests/test_lexicon.py` (`TestPushPlaylist`, nachgebaute API mit `index`), Oberflächentest
  `test_playlists_send_lexicon`.

## 20. Umsetzung Beatport-Playlists (#284, 25.10.2026)

- **Entscheid B1:** eigene Beatport-Playlists; Charts von Künstlern/Labels optional – **noch nicht umgesetzt** (Pfade der
  inoffiziellen API nicht belegt).
- **Beatport-Plugin 1.1:** `ready(ctx)` (angemeldet?), `playlists(ctx)` und `playlist_files(ctx, id)` über die
  inoffizielle API v4 (`/my/playlists/`, `/my/playlists/{id}/`, `/my/playlists/{id}/tracks/`, Seiten mit
  `page`/`per_page`, Einträge mit `position` und `track`). Die Pfade sind nicht offiziell dokumentiert und konnten aus
  der Sitzung nicht geprüft werden – wie bei den Käufen (#117) stehen die Feldnamen der ersten Antwort im Protokoll
  (`Logs/beatport.log`), der echte Test läuft beim User. Titel → Eintrag ohne Datei (`track_ref`: Künstler, Titel,
  Mix, ISRC, Länge, Link).
- Der Rahmen erledigt den Rest wie bei Spotify/SoundCloud (#280): „Importieren ▾ › Aus Beatport …“, Ordner „Beatport“,
  sichere Treffer gleich verknüpfen (#282), erneutes Holen behält Verknüpfungen. Nur lesen.
- `Manager.call_playlist` schreibt jetzt bei allen Playlist-Funktionen das Protokoll des Plugins.
- **Tests:** `tests/test_beatport.py` (`test_playlists_import`, nachgebaute API), Oberflächentest
  `test_playlists_import_beatport`.
