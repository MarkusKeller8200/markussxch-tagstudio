# Konzept: Ordner-Rollen – jeder Ordner genau einmal festgelegt

Status: **ENTWURF** (25.10.2026, Wunsch User 13:53) – noch nicht freigegeben. Ergänzt
[KONZEPT-SPEICHER.md](KONZEPT-SPEICHER.md) (Programmdaten bleiben dort beschrieben) und ersetzt dessen Abschnitte 4/5,
sobald umgesetzt.

## 1. Ausgangslage und Ziel

Heute speichert jedes Modul seine Ordner selbst. Die **Bibliothek** steht an bis zu fünf Stellen (Tagger-Standardordner
`default_tagger`, Workflow „Bibliothek“, Basisordner + `01_Library`, Snapshots, Hilfe › Scan-Ordner), der
**Download-Ordner** an drei (Workflow-Quelle, Beatport-Ziel, Käufe-Ziel `purch_dest`). Weichen die Einträge
voneinander ab, arbeiten Module mit verschiedenen Ordnern – so liest der Käufe-Abgleich heute zwei Bibliotheken.

Ziel:

- Jeder Ordner hat eine **Rolle** und wird **an einer Stelle** festgelegt (Einstellungen › Ordner).
- Standard ist das **Basisordner-Konzept**: Rollen ergeben sich aus Basisordner + Unterordner.
- **Jede Rolle lässt sich auf einen eigenen Ordner umstellen** – wer der Struktur nicht folgen will, muss nicht.
- **Mehrere Bibliotheken** sind möglich, jede einzeln aktiv/inaktiv.
- Neue Rolle **Export**.
- Ordner wechseln, neu wählen oder neu anlegen – mit der Frage, ob der bisherige Inhalt **verschoben, kopiert oder
  dort gelassen** wird.

## 2. Rollen

| Rolle | Standard unter dem Basisordner | Anzahl | Wer nutzt sie |
|---|---|---|---|
| **Eingang** | `00_New` | 1 | Vorbereiten (Eingang), Abholen, Käufe › Download (Standardziel) |
| **Bibliotheken** | `01_Library` | 1 … n | Tagger (Auswahl), Vorbereiten › Übernahme (Hauptbibliothek), Käufe-Abgleich, Playlist-Abgleich, Entdecken („schon vorhanden“), Hilfe › Scan, Snapshots |
| **Archiv** | `02_Archiv` | 1 | Aussortieren (Tagger, Vorbereiten), archivierte Playlists `_Playlists` |
| **Playlists** | `03_Playlists` | 1 | M3U8-Spiegel der Playlists |
| **Export** *(neu)* | `04_Export` | 1 | Startordner aller „Exportieren …“: Tagger-Liste, Playlists, DJ-Set, Merkliste (Entdecken), Journal, Einstellungen, Workflow, Cover |
| **Downloads** | `90_Download` | 1 (+ weitere Quellen im Workflow) | Quelle „Downloads“ im Workflow, Beatport-Download |
| **Arbeit** | `91_Work` | 1 | Stufen-Ordner der Workflow-Schritte |
| **Sicherung** | `99_Sicherung\Tags` | 1 | Tag-Sicherungen vor dem Speichern (wenn nicht im Snapshot-Speicher) |
| **Snapshots** | `99_Sicherung\Snapshots` | 1 | Snapshot-Speicher |

Nicht als Rolle (bleiben wie heute): Startpfade links/rechts im Vergleich (Komfort, darf auf eine Rolle zeigen),
`<Titel> – Stems\` neben dem Original, `Angeglichen\` des Plugins Lautheit, `.tagstudio-snapshots\` im Bibliotheksordner,
Programmdaten `~\TagStudio` (siehe KONZEPT-SPEICHER).

## 3. Basisordner oder eigener Ordner – je Rolle

Jede Rolle hat einen von zwei Modi:

- **Basis** (Standard): Pfad = Basisordner + Unterordnername (Name änderbar, z. B. `01_Library` → `Musik`). Wird der
  Basisordner gewechselt, folgen alle Rollen im Modus „Basis“ (mit der Frage aus Abschnitt 5).
- **Eigener Ordner**: frei gewählter Pfad, auch auf einem anderen Laufwerk oder Netzlaufwerk. Folgt dem Basisordner
  nicht. Zurück auf „Basis“ ist jederzeit möglich.

Ohne Basisordner (wer die Struktur gar nicht will): alle Rollen „Eigener Ordner“; leere Rollen sind erlaubt –
die Funktion fragt dann beim ersten Gebrauch nach dem Ordner und bietet an, ihn als Rolle zu speichern.

## 4. Mehrere Bibliotheken

Jede Bibliothek hat: **Name** (z. B. „Haupt“, „Vinyl-Rips“, „Extern SSD“), **Pfad** (Basis oder eigener Ordner),
**aktiv** (Häkchen), **Hauptbibliothek** (genau eine), **Snapshots** (überwachen ja/nein).

- **Aktiv** = wird in Abgleichen berücksichtigt (Käufe, Playlists, Entdecken, Hilfe › Scan). Inaktive bleiben
  eingetragen, z. B. ein externes Laufwerk, das nicht immer angeschlossen ist. Nicht erreichbare aktive Bibliotheken
  werden übersprungen und gemeldet („Extern SSD nicht erreichbar“).
- **Hauptbibliothek** = Ziel von Vorbereiten › Übernehmen und Startordner des Tagger.
- **Überschneidung** wird erkannt und angezeigt: eine Bibliothek liegt in einer anderen („ist in ‚Haupt‘ enthalten“)
  oder zeigt auf denselben Ordner über einen anderen Weg (Laufwerksbuchstabe/Netzlaufwerk, gleiche Dateien). Solche
  Doppel werden beim Einlesen nur einmal gelesen.
- **Tagger:** Auswahlliste „Bibliothek ▾“ neben dem Pfad; „Alle aktiven“ lädt alle zusammen.
- **„Verglichen mit“** (Käufe, Playlist-Abgleich) zeigt die Namen der aktiven Bibliotheken; ein Klick öffnet die
  Ordner-Einstellungen.

## 5. Ordner ändern – wechseln, neu wählen, neu anlegen

Jede Rolle hat in Einstellungen › Ordner den Knopf **„Ändern …“** mit drei Wegen:

1. **Zu einem vorhandenen Ordner wechseln** – nur die Einstellung ändert sich, Dateien bleiben, wo sie sind.
2. **Neuen Ordner wählen** (vorhanden, leer oder nicht).
3. **Neuen Ordner anlegen** (Name eingeben, Elternordner wählen).

Bei 2 und 3 – und bei 1, wenn der bisherige Ordner Inhalt hat – kommt die Frage, was mit dem **bisherigen Inhalt**
geschieht:

| Wahl | Was passiert |
|---|---|
| **Verschieben** | Inhalt wandert in den neuen Ordner; auf demselben Laufwerk sofort (Umbenennen), sonst Kopieren → Prüfen (Grösse, bei Musik Prüfsumme) → Original erst danach entfernen. Der alte, leere Ordner bleibt stehen (Löschen nur auf Rückfrage). |
| **Kopieren** | Inhalt wird kopiert, das Original bleibt unverändert. Die Rolle zeigt danach auf den neuen Ordner. |
| **Nicht übernehmen** | Nur die Einstellung ändert sich; der neue Ordner startet leer bzw. mit seinem eigenen Inhalt. |

Regeln dabei:

- **Vorschau vor dem Start:** Anzahl Dateien, Grösse, freier Platz am Ziel, Konflikte (gleiche Namen am Ziel).
  Konflikte: „Ziel behalten“ (Standard), „mit (2) daneben ablegen“ – **nie still überschreiben**.
- Läuft als Hintergrund-Auftrag mit Fortschritt, abbrechbar; ein Abbruch hinterlässt keine halben Dateien
  (`.part` + Umbenennen). Journal `Ordnerwechsel.csv` im Export-Ordner bzw. in den Programmdaten.
- **TagStudio-Verweise nachführen** (bei Verschieben automatisch, bei Kopieren auf Wunsch): Playlists (Einträge mit
  Pfad), Käufe (zugeordnete Dateien), Vorbereiten (Status, Stufen), Snapshots (Bibliotheks-Wurzel), Tagger-Verlauf,
  Warteschlange. M3U8 im Playlist-Ordner werden neu geschrieben.
- **Bibliothek verschieben – deutliche Warnung:** Engine DJ, Lexicon, Rekordbox, Serato, VirtualDJ merken sich Pfade
  und verlieren die Verweise. TagStudio ändert **keine fremden Datenbanken** (Projektregel) – der Hinweis nennt, was
  dort zu tun ist (z. B. „Relocate“/„Fehlende Dateien suchen“). Standard-Antwort bei der Bibliothek ist darum
  „Nicht übernehmen“, bei den anderen Rollen „Verschieben“.
- **Snapshots:** Der Speicher wird als Ganzes verschoben/kopiert (nicht teilweise); geöffnete Snapshots werden vorher
  geschlossen.
- **Archiv:** `_aussortiert.csv` wird mit verschoben und die Pfade darin nachgeführt, damit „Zurückholen“ weiter geht.
- **Basisordner wechseln:** dieselbe Frage einmal für alle Rollen im Modus „Basis“ (Liste mit Häkchen je Rolle,
  Bibliotheken standardmässig nicht verschieben).

Dieselbe Auswahl erscheint überall, wo heute ein Ordner gewählt wird (Tagger, Workflow, Käufe, Playlists …), als
Klappmenü: **Rollen** (z. B. „Bibliothek: Haupt“, „Eingang“, „Export“) · **Zuletzt benutzt** · **Anderer Ordner …** ·
**Neuer Ordner …** – und bei einer Rolle zusätzlich „Als neuen Ordner für ‚Eingang‘ speichern“.

## 6. Datenmodell

```json
"folders": {
  "base": "D:\\TagStudio",
  "roles": {
    "inbox":     {"mode": "base", "name": "00_New"},
    "archive":   {"mode": "base", "name": "02_Archiv"},
    "playlists": {"mode": "base", "name": "03_Playlists"},
    "export":    {"mode": "custom", "path": "E:\\Exporte"},
    "downloads": {"mode": "base", "name": "90_Download"},
    "work":      {"mode": "base", "name": "91_Work"},
    "backup":    {"mode": "base", "name": "99_Sicherung\\Tags"},
    "snapshots": {"mode": "base", "name": "99_Sicherung\\Snapshots"}
  },
  "libraries": [
    {"id": "main", "name": "Haupt", "mode": "base", "name_sub": "01_Library", "active": true, "main": true, "snapshots": true},
    {"id": "ssd1", "name": "Extern SSD", "mode": "custom", "path": "F:\\Musik", "active": false, "main": false, "snapshots": false}
  ]
}
```

- Ein Modul ruft nur noch `folders.role("inbox")`, `folders.libraries(active=True)`, `folders.main_library()` –
  kein eigener Pfad mehr. Workflows speichern statt eines Pfads den Verweis `@inbox` / `@library:main`; ein eigener
  Pfad je Workflow bleibt möglich (z. B. zweiter Workflow mit anderem Eingang).
- Neues Modul `folders.py` (Auflösen, Überschneidungen, Verschieben/Kopieren als Auftrag), Session-Mixin
  `session_folders.py`, Seite Einstellungen › Ordner (`web/folders.js`).

## 7. Übernahme der heutigen Einstellungen (einmalig)

- `base_dir` → `folders.base`; `archive_dir`, `playlist_dir`, `backup_dir`, `snap_dir`/`backup_store` → Rollen
  (Modus „Basis“, wenn der Pfad = Basis + Standardname, sonst „Eigener Ordner“).
- Bibliotheken aus `default_tagger`, Workflow-Bibliothek(en), Basis + `01_Library`, Snapshot-Bibliotheken,
  `help_scan_root` – **gleiche Ordner zusammengefasst** (auch über Laufwerksbuchstabe/Netzlaufwerk erkannt).
- Eingang, Arbeit, Downloads aus dem aktuellen Workflow; `purch_dest` → Eingang (wenn gleich) oder eigener Ordner.
- **Abweichungen werden nicht still entschieden:** Gibt es mehrere verschiedene Bibliotheken, zeigt TagStudio beim
  ersten Start eine Übersicht „Diese Ordner haben wir gefunden“ – je Ordner: als Bibliothek behalten (aktiv/inaktiv),
  Hauptbibliothek wählen, verwerfen.
- Alte Schlüssel bleiben bis zur nächsten Hauptversion lesbar (Rückweg bei einem Downgrade).

## 8. Oberfläche (Einstellungen › Ordner)

```
Basisordner   D:\TagStudio                                   [Ändern …]  [Struktur anlegen …]

Rolle          Ordner                                Modus          
Eingang        D:\TagStudio\00_New                   Basis          [Ändern …] [Öffnen]
Bibliotheken   ☑ Haupt (Hauptbibliothek)  D:\TagStudio\01_Library   Basis    [Ändern …] [Öffnen]
               ☐ Extern SSD               F:\Musik  ⚠ nicht erreichbar  Eigener [Ändern …] [Entfernen]
               [+ Bibliothek hinzufügen …]
Archiv         D:\TagStudio\02_Archiv                Basis          [Ändern …] [Öffnen]
Playlists      D:\TagStudio\03_Playlists             Basis          …
Export         E:\Exporte                            Eigener Ordner …
Downloads      D:\TagStudio\90_Download              Basis          …
Arbeit         D:\TagStudio\91_Work                  Basis          …
Sicherung      D:\TagStudio\99_Sicherung\Tags        Basis          …
Snapshots      D:\TagStudio\99_Sicherung\Snapshots   Basis          …
```

Hinweise neben der Zeile: „fehlt – anlegen?“, „nicht erreichbar“, „überschneidet sich mit …“, „liegt nicht auf
demselben Laufwerk wie die Bibliothek (Verschieben dauert länger)“. Der Einrichtungsassistent nutzt dieselbe Seite.

## 9. Umsetzung in Schritten (Vorschlag)

1. `folders.py` + Datenmodell + Übernahme (Abschnitt 7) + Seite Einstellungen › Ordner (nur Anzeigen/Wechseln).
2. Module umstellen: Käufe, Playlist-Abgleich, Entdecken, Hilfe-Scan auf `libraries(active=True)`; Tagger-Auswahl;
   Vorbereiten-Workflow mit Verweisen; Export-Rolle als Startordner aller Exporte.
3. „Ändern …“ mit Verschieben/Kopieren/Nicht übernehmen, Vorschau, Konflikte, Auftrag, Verweise nachführen.
4. Ordner-Klappmenü in allen Auswahlfeldern.

Zeitpunkt: eigener Meilenstein (Vorschlag **4.10.0 – Ordner**), nicht in 4.9.1.

## 10. Offene Entscheide

- **O1** Name der neuen Rolle und Standardordner: „Export“ / `04_Export` – passt das?
- **O2** Tagger „Alle aktiven Bibliotheken“ laden – gewünscht, oder immer nur eine?
- **O3** Snapshots je Bibliothek ein- und ausschaltbar (wie heute je Ordner) – oder alle aktiven automatisch?
- **O4** Bibliothek ändern: Standard „Nicht übernehmen“ (Schutz der DJ-Programme) – einverstanden?
- **O5** Mehrere Eingänge (z. B. je Store) als Rolle – oder bleiben weitere Quellen im Workflow?
- **O6** Verschieben über Laufwerke: Prüfsumme für alle Dateien (sicher, langsamer) oder nur Grösse?
