# Konzept: Snapshots und Änderungsjournal

Stand: 2026-10-09 · Status: **Konzept**, noch nicht umgesetzt

## 1. Ziel

DJ-Bibliotheken werden nicht nur mit TagStudio bearbeitet. **Mp3tag, beaTunes, Mixed In Key, Platinum Notes,
Rekordbox, Serato** und andere schreiben ebenfalls in die Tags – oft im Hintergrund, in vielen Dateien gleichzeitig
und ohne Protokoll. TagStudio soll das sichtbar und umkehrbar machen:

1. **Snapshot:** den Tag-Zustand eines überwachten Ordners festhalten – schnell und platzsparend, ohne Audiodaten.
2. **Änderungsjournal:** später zeigen, welche Titel sich seit einem Snapshot verändert haben, welche Felder und
   vermutlich durch welches Programm.
3. **Rückgängig:** einzelne Felder, einzelne Titel oder ganze Gruppen auf den Snapshot-Stand zurücksetzen –
   mit Vorschau, Rückgängig und Sicherung wie überall in TagStudio.
4. **Vergleich:** einen Snapshot (oder zwei) auf der bestehenden Vergleichsseite gegen den Live-Stand legen und
   Werte gezielt übernehmen.

Typischer Ablauf: *Snapshot „Vor Mixed In Key“ → MIK analysiert 300 Titel → TagStudio zeigt 300 geänderte Titel,
davon 280 nur Tonart/Energie (erwünscht) und 20 mit überschriebenem Kommentar (unerwünscht) → die 20 Kommentare mit
einem Klick zurücksetzen.*

### Abgrenzung zu „Sicherungen“

| | Sicherungen (heute) | Snapshots (neu) |
|---|---|---|
| Auslöser | automatisch, bevor **TagStudio** speichert | von Hand, beim Start oder zeitgesteuert |
| Umfang | nur die gespeicherten Dateien | ein ganzer überwachter Ordner |
| Erkennt Änderungen durch | – | **alle** Programme |
| Zweck | eigenes Speichern rückgängig machen | fremde Änderungen finden und gezielt zurücknehmen |

Beide nutzen dieselbe Technik (exakte Tag-Bytes, Audio-Fingerabdruck, byte-genaues Zurückschreiben aus
`backup.py`). Langfristig können Sicherungen als „kleine Snapshots“ im selben Speicher landen (Phase 3).

## 2. Begriffe

- **Überwachter Ordner** (Bibliothek): ein Wurzelordner mit Unterordnern, z. B. `S:\_MP3\01_Library`. Mehrere möglich.
- **Snapshot:** Zustand aller MP3-Dateien eines überwachten Ordners zu einem Zeitpunkt.
- **Live:** der aktuelle Zustand auf der Platte.
- **Journal:** Unterschied zwischen zwei Zuständen (Snapshot ↔ Live oder Snapshot ↔ Snapshot).

## 3. Was ein Snapshot speichert

Pro Datei:

| Feld | Zweck |
|---|---|
| Pfad relativ zum überwachten Ordner | Zuordnung; funktioniert auch bei anderem Laufwerksbuchstaben oder Windows ↔ Mac |
| Grösse, Änderungszeit | schneller Vergleich ohne Lesen der Datei |
| **Audio-Schlüssel** (wie `waveform.audio_key`: Länge + Anfang + Ende des Audioteils) | erkennt **Umbenennen/Verschieben** (gleiches Audio, anderer Pfad) und **Audio-Änderungen** (z. B. Platinum Notes) |
| ID3v2-Tag **byte-genau** (Kopf, Frames in Reihenfolge, Padding) und ID3v1 | exakte Wiederherstellung |
| Dauer, ID3-Version | Anzeige, Plausibilität |

Audiodaten werden **nicht** gespeichert – Snapshots bleiben klein. Audio-Änderungen werden erkannt und gemeldet,
lassen sich aber nicht rückgängig machen (dafür wäre eine Audio-Sicherung nötig, siehe offene Fragen).

### Speicherformat (inhaltsadressiert, wie Git)

```
~/TagStudio/Snapshots/                     (Ordner änderbar, wie bei Sicherungen)
  objects/ab/abcdef….z                     einzelne Frames (zlib), Name = SHA-256 des Inhalts
  libs/<id>/library.json                   überwachter Ordner: Pfad, Name, Einstellungen
  libs/<id>/snaps/2026-10-09_1830_<id>.json.gz   Manifest eines Snapshots
```

- Jeder ID3-Frame wird **einmal** gespeichert, egal in wie vielen Dateien oder Snapshots er vorkommt. Gleiche
  Cover eines Albums, unveränderte Felder und unveränderte Dateien kosten in weiteren Snapshots fast nichts.
- Ein Manifest listet je Datei nur Verweise: `{"p": "Artist/Titel.mp3", "size", "mtime", "audio", "dur",
  "tag": {"hdr": "<10 Byte>", "frames": ["<sha>", …], "pad": 1024, "ver": 3}, "v1": "<sha>|null"}`.
- Schätzung für 1'500 Titel: erster Snapshot ≈ Textfelder 3 MB + einmalige Cover; jeder weitere Snapshot
  ≈ 0,3–1 MB plus nur die tatsächlich geänderten Frames.
- **Aufräumen:** automatische Snapshots werden nach Regel ausgedünnt (z. B. die letzten 20 behalten, dazu je einen
  pro Woche/Monat); **angeheftete** Snapshots (eigene Bezeichnung, z. B. „Vor Platinum Notes“) bleiben immer.
  Danach werden nicht mehr benutzte Objekte entfernt.

### Schnell erstellen

- **Inkrementell:** stimmen Grösse und Änderungszeit mit dem letzten Snapshot überein, wird der Eintrag ohne
  Lesen übernommen. Nur geänderte Dateien werden gelesen (Tag-Bereich + 2 × 64 KB für den Audio-Schlüssel).
- Option **„Gründlich“**: alle Dateien lesen (falls ein Programm die Änderungszeit zurücksetzt).
- Läuft als **Hintergrund-Auftrag** (`jobs.py`) mit Fortschritt in der Fussleiste – die Oberfläche bleibt frei.
- Ordner werden je einmal gelistet (wie bei der Stems-Suche, #43) – wichtig auf Netzlaufwerken.

## 4. Änderungen erkennen (Journal)

Vergleich zweier Zustände, Zuordnung zuerst über den Pfad, dann über den Audio-Schlüssel:

| Status | Bedeutung |
|---|---|
| **Tags geändert** | gleiche Datei, mindestens ein Feld anders |
| **Neu** | Datei nur im neueren Zustand (z. B. von Platinum Notes erzeugte Kopie) |
| **Entfernt** | Datei nur im älteren Zustand |
| **Umbenannt/verschoben** | gleicher Audio-Schlüssel, anderer Pfad (z. B. Mp3tag „Dateien umbenennen“) – Tags werden trotzdem verglichen |
| **Audio geändert** | Audio-Schlüssel anders (z. B. Platinum Notes, Neu-Kodierung) – nur Hinweis |
| **Nur Umschreibung** | Bytes anders, Werte gleich (z. B. v2.3 → v2.4, andere Kodierung, Padding) – standardmässig ausgeblendet |

Je geänderter Datei die **Felder** mit alt/neu (zeichengenaue Markierung wie im Vergleich und im Änderungs-Viewer der
Sicherungen) und dem Kennzeichen **Herkunft der Tags** (`origins.py`). Daraus eine **Vermutung, welches Programm
geändert hat**: ändern sich `TKEY`, `TXXX:EnergyLevel`, `GEOB:CuePoints`, steht „vermutlich Mixed In Key“; bei
`TXXX:Segments`/`TXXX:fBPM` „vermutlich beaTunes“. Unbekannte Felder zählen als „unbekannt“.

Vergleich auf **Werte**, nicht auf Bytes – sonst würde jede v2.3/v2.4-Umschreibung alles als geändert markieren.

## 5. Oberfläche

### 5.1 Seite „Snapshots“ (neu in der Seitenleiste)

```
┌ Bibliotheken ────────────┐ ┌ Journal: „Vor MIK“ (Mo 18:30) ↔ Jetzt ──────────────────────────────────┐
│ ▸ 01_Library  (1'493)    │ │ 312 geändert · 2 neu · 1 umbenannt · 1 Audio · [Filter: Programm ▾ Feld ▾]│
│   ● Jetzt                │ │ ☐ Titel                      Felder            vermutlich        Aktion    │
│   ○ Vor MIK   📌 Mo 18:30│ │ ☐ Nordlicht – Mara Lind      TKEY, Energy, +2  Mixed In Key      ↺  ⇄      │
│   ○ Start     Mo 08:02   │ │ ☐ Golden Hour – …            COMM (überschr.)  unbekannt         ↺  ⇄      │
│   ○ Start     So 09:15   │ │   ▾ COMM   „Gute Bridge ab 2:10“  →  „“            [↺ Feld zurück]       │
│ [+ Snapshot] [Ordner …]  │ │ …                                                                        │
└──────────────────────────┘ │ [Markierte Felder zurück] [Ganze Titel auf Snapshot-Stand] [Im Vergleich] │
                             └───────────────────────────────────────────────────────────────────────────┘
```

- Links die überwachten Ordner mit ihren Snapshots (Zeit, Bezeichnung, 📌 angeheftet). Zwei Snapshots wählen
  (oder einen und „Jetzt“) → rechts das Journal.
- **Filter** nach Status, Programm (Herkunft) und Feld, Suche nach Titel. Beispiel: „nur Mixed In Key, nur `TKEY`“.
- **Rückgängig:** je Feld (↺ in der Detailzeile), je Titel (↺ in der Zeile) oder für alle markierten Titel bzw.
  alle gefilterten Felder („alle Kommentar-Änderungen zurück“).
- **⇄** öffnet das Paar auf der Vergleichsseite.

### 5.2 Rückgängig – sicher wie Speichern

- Standard: Die Werte werden in die geladenen Dateien übernommen (wie eine Bearbeitung im Tagger) → **Rückgängig
  möglich**, gespeichert wird erst mit **Speichern** – vorher entsteht wie immer eine Sicherung.
- Für ganze Titel zusätzlich **„byte-genau zurückschreiben“** (exakte Tag-Bytes des Snapshots, wie das
  Wiederherstellen einer Sicherung) – inklusive Binärfeldern (Serato, Cue-Punkte) genau so, wie sie waren.
  Vorher wird der aktuelle Zustand gesichert; ist das Audio inzwischen anders, wird gewarnt.

### 5.3 Vergleichsseite mit Snapshots

- Links/rechts statt Ordner wahlweise **Snapshot** wählen (Auswahl „Ordner · Snapshot“ neben dem Pfad).
  Kombinationen: *Snapshot ↔ Live* (Standard), *Snapshot ↔ Snapshot* (nur ansehen).
- Snapshot-Seiten sind **schreibgeschützt**: Pfeile, „Alles“, „Fehlende“ und die Sammelkopie arbeiten nur in
  Richtung Live.
- Neue Zuordnung **„Audio-Inhalt“** (Audio-Schlüssel) – findet umbenannte und verschobene Titel.
- Technik: Snapshot-Einträge werden wie bei den Sicherungen als schreibgeschützte `MP3File` aus den Tag-Bytes
  geladen – die ganze Vergleichsansicht (Markierungen, Herkunft, Editoren, Player für die Live-Seite) funktioniert
  ohne Sonderwege.

### 5.4 Beim Start

- Ist mindestens ein Ordner überwacht und die Option an, prüft TagStudio im Hintergrund schnell (nur Grösse und
  Änderungszeit), was sich seit dem letzten Snapshot getan hat, und fragt dann:

  > **01_Library:** 37 Titel wurden seit dem letzten Snapshot (Mo 18:30) ausserhalb von TagStudio geändert.
  > [Journal ansehen] [Neuen Snapshot erstellen] [Später]   ☐ Nicht mehr fragen

  Ohne Änderungen nur ein dezenter Hinweis bzw. still ein neuer Snapshot (einstellbar).
- **Einstellungen** (Bereich „Snapshots“): überwachte Ordner, Frage beim Start ein/aus, automatischer Snapshot
  („bei jedem Start“, „höchstens einmal täglich“, „nie“), Aufbewahrung, Speicherort, „Gründlich“.

### 5.5 Während TagStudio läuft (Ordnerüberwachung)

- Die Standardbibliothek von Python hat keine Dateisystem-Ereignisse; überwacht wird darum **sparsam per
  Abfrage** (alle 5 Minuten, einstellbar): nur Grösse/Änderungszeit, je Ordner ein Listing.
- Fund → Hinweis in der Fussleiste („12 Titel extern geändert“), Klick öffnet das Journal *letzter Snapshot ↔ Jetzt*.
- **Konfliktschutz beim Speichern (wichtig, auch ohne Snapshots):** Hat ein anderes Programm eine Datei geändert,
  seit TagStudio sie eingelesen hat, darf Speichern diese Änderung nicht stillschweigend überschreiben. Vor dem
  Speichern werden Grösse/Änderungszeit geprüft; bei Abweichung: „Datei wurde extern geändert – Unterschiede
  ansehen / trotzdem speichern / neu einlesen“.

## 6. Technischer Aufbau

| Baustein | Inhalt |
|---|---|
| `snapshots.py` (neu, nur Standardbibliothek) | Bibliotheken verwalten, Scan (inkrementell), Objekt-Speicher, Manifest lesen/schreiben, Journal (Diff Zustand ↔ Zustand), Aufräumen |
| `backup.py` | `read_layout`, Audio-Fingerabdruck, `_write_tags` (byte-genaues Zurückschreiben) werden gemeinsam genutzt |
| `session.py` | Aufrufe für die Oberfläche; Rückgängig über `undo.checkpoint`; Snapshot als Quelle im Vergleich |
| `jobs.py` | Snapshot erstellen und Journal berechnen als Hintergrund-Auftrag |
| `origins.py` | Herkunft je Feld → Vermutung „welches Programm“ |
| `web/snapshots.js` + Seite | Bibliotheken, Snapshot-Liste, Journal, Filter, Rückgängig |
| `appsettings.py` | neue Gruppe „Snapshots“ (Export/Import/Zurücksetzen) |

Leistungsziel: Prüfen ohne Änderungen bei 1'500 Titeln < 2 s lokal; erster Snapshot < 1 min auf dem Netzlaufwerk;
Journal für 300 geänderte Titel < 3 s.

Tests: synthetische Bibliothek, „fremdes Programm“ simulieren (Tags direkt ändern, umbenennen, Audio ändern,
v2.3 → v2.4 umschreiben), Journal-Status prüfen, Feld- und Byte-Rückgängig, Aufräumen ohne Datenverlust.

## 7. Umsetzung in Schritten

**Phase 1 – Grundfunktion**
1. `snapshots.py`: Objekt-Speicher, Manifest, inkrementeller Scan, Journal, Aufräumen (mit Tests).
2. Seite „Snapshots“: Ordner überwachen, Snapshot von Hand (mit Bezeichnung/Anheften), Journal Snapshot ↔ Jetzt,
   Filter, Feld- und Titel-Rückgängig (über Undo), byte-genaues Zurückschreiben.
3. Start-Frage mit Option „nicht mehr fragen“; Einstellungen „Snapshots“.
4. **Konfliktschutz beim Speichern** (externe Änderung seit dem Einlesen).

**Phase 2 – Vergleich und Komfort**
5. Snapshot als Quelle auf der Vergleichsseite, schreibgeschützt; Zuordnung nach Audio-Inhalt; Snapshot ↔ Snapshot.
6. „Vermutlich geändert von …“ (Herkunft) mit Filter und Sammel-Rückgängig je Programm.
7. Überwachung während der Laufzeit (Abfrage) mit Hinweis in der Fussleiste.

**Phase 3 – Ausbau**
8. Journal exportieren (CSV/Excel).
9. Sicherungen im selben Objekt-Speicher (spart Platz, einheitlicher Änderungs-Viewer).
10. Optional: Audio-Sicherung einzelner Titel vor Programmen wie Platinum Notes.

## 8. Offene Fragen

1. **Speicherort:** lokal (`~/TagStudio/Snapshots`) oder neben der Bibliothek (z. B. `S:\_MP3\.tagstudio`), damit
   mehrere Rechner dieselben Snapshots sehen?
2. **Automatik:** bei jedem Start fragen, höchstens einmal täglich, oder still automatisch?
3. **Aufbewahrung:** wie viele automatische Snapshots behalten (Vorschlag: 20 + je einer pro Woche der letzten 3
   Monate)?
4. **Audio-Änderungen** (Platinum Notes): nur melden, oder Audio-Sicherung einzelner Titel anbieten (braucht viel
   Platz)?
5. **Reihenfolge in der Planung:** vor oder nach „3.3.0 – DJ-Set“?
