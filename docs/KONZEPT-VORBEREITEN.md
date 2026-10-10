# Konzept: Tracks vorbereiten

Status: **Entwurf** (2026-10-10) – Übersicht #121, Teil-Issues #109–#120 (Label `vorbereiten`, Meilenstein „Tracks vorbereiten (Konzept)“).

## Ziel

Neue Titel kommen in einen **Eingangsordner** und durchlaufen einen festgelegten **Workflow** bis in die
**Bibliothek**. TagStudio führt die Schritte, die es selbst kann, automatisch aus, übergibt die übrigen an externe
Programme, erkennt, wann ein Schritt erledigt ist, und schützt bereits gepflegte Tags. Der Workflow ist frei
zusammenstellbar, damit ihn auch andere mit ihren Programmen nutzen können; der Workflow des Users wird als
Vorlage mitgeliefert.

## Der Workflow des Users (Ausgangslage)

| Nr. | Schritt | Heute | In TagStudio |
|---|---|---|---|
| 01 | Kauf/Download Beatport → `_01_Original` (Rohdaten, unverändert) | manuell | Eingangsordner überwachen; später Download gekaufter Titel (Machbarkeit offen) |
| 02 | Mp3tag-Aktionen → `_02_MP3Tag` | Mp3tag | **intern als Tag-Rezept** (siehe unten), automatisch |
| 03 | Platinum Notes (−10,5 LUFS, Clipping) → `_03_PlatinumNotes` | Platinum Notes | externer Schritt; Erkennung über das Platinum-Notes-Kennzeichen im Tag. Optional eigene Lautheit (ffmpeg) |
| 04 | MusicBrainz Picard | Picard | externer Schritt **oder** intern über 4.1.0 Online-Metadaten im Modus „nur ergänzen“ |
| 05 | AudioRanger | AudioRanger | externer Schritt |
| 06 | OneTagger | OneTagger | externer Schritt (Kommandozeile prüfen) |
| — | Kopieren nach `S:\_MP3\01_Library` | manuell | **Übernahme** mit Duplikatprüfung und Snapshot |
| 07 | Mixed In Key (Key, BPM, Beatgrid, Cues, Energie) | MIK | externer Schritt; Erkennung über MIK-Felder |
| 08 | beaTunes | beaTunes | externer Schritt; Erkennung über beaTunes-Felder |
| 09 | Engine DJ (Bibliothek, Stems, Playlisten) | Engine DJ | Checkliste |
| 10 | Lexicon (verteilt an VirtualDJ, Traktor, Serato, Rekordbox) | Lexicon | Checkliste |
| 11 | Mixo (Playlisten unterwegs) | Mixo | Checkliste |

**Regel des Users:** Ab Schritt 04 dürfen Programme bestehende Tags nicht mehr verändern, nur ergänzen.

## Bausteine

### 1. Seite „Vorbereiten“
- Eingangsordner (überwacht), Stufen-Ordner (`_01_Original`, `_02_MP3Tag`, …) und Zielordner (Bibliothek) je Workflow.
- Ansicht je Titel: in welcher Stufe, was ist erledigt, was wartet, Warnungen (z. B. überschriebene Felder).
- Neue Dateien im Eingang werden gemeldet (gleiche Abfrage-Überwachung wie bei Snapshots, kein Dienst im Hintergrund).
- **Rohdaten bleiben unverändert:** jede Stufe arbeitet auf einer Kopie im nächsten Stufen-Ordner.

### 2. Workflow-Vorlagen
- Ein Workflow ist eine geordnete Liste von Schritten; jeder Schritt hat einen Typ:
  - **Rezept** (TagStudio-Aktionen, automatisch),
  - **Plugin** (z. B. Online-Metadaten, Download, Lautheit),
  - **Extern** (Programm mit Ordner/Dateien öffnen, Abschluss erkennen oder bestätigen),
  - **Kopieren/Verschieben** (in Stufe oder Bibliothek),
  - **Prüfen** (Schutzregel, Pflichtfelder, Duplikate),
  - **Checkliste** (nur Status, z. B. Engine DJ, Lexicon).
- Speicherung als JSON; Export/Import zum Weitergeben. Mitgeliefert: Vorlage „DJ-Workflow (Beatport → Bibliothek)“
  nach dem Muster des Users, ohne seine persönlichen Pfade.

### 3. Tag-Rezepte (ersetzt Schritt 02)
Wiederverwendbare Aktionslisten wie in Mp3tag, mit Vorschau und Rückgängig, auch ausserhalb des Workflows im Tagger
nutzbar. Benötigte Aktionen für das Rezept des Users:
- Ersetzen in allen Feldern: `%20` → Leerzeichen, `_` → Leerzeichen.
- Schreibweise festlegen für Wörter: `Dj`, `Feat`, `Mc`, `Vs` (Liste frei).
- **Doppelte Felder entfernen**, wenn der Inhalt gleich ist.
- **Feld formatieren** (`FILETYPE` = erster Wert, Entsprechung zu Mp3tag `$meta(FILETYPE,0)`).
- **Felder entfernen** (`COMMENT`, `COMM`).
- Speichern als **ID3v2.4 und ID3v1** – TagStudio liest ID3v1 heute nur, **Schreiben fehlt noch**.

### 4. Externe Programme
- Programm je Schritt hinterlegen (Pfad, Argumente mit Platzhaltern für Ordner/Dateien).
- Abschluss erkennen: Dateien im Ausgabe-Ordner, geänderte Tags, **Herkunfts-Kennzeichen** (Platinum Notes,
  Mixed In Key, beaTunes sind in `origins.py` schon bekannt) – sonst manuell bestätigen.
- Platinum Notes, Picard und AudioRanger haben nach heutigem Stand keine dokumentierte Kommandozeile; sie werden
  geöffnet, der User arbeitet dort, TagStudio erkennt das Ergebnis. Für OneTagger ist eine Kommandozeile zu prüfen.

### 5. Schutzregel „nur ergänzen“
- Vor einem geschützten Schritt hält TagStudio den Tag-Stand fest (Snapshot-Technik), danach Vergleich:
  neue Felder = ok, geänderte oder entfernte Felder = Warnung mit Liste.
- Auf Wunsch die alten Werte feldweise zurückschreiben (wie im Änderungsjournal).

### 6. Übernahme in die Bibliothek
- Kopieren in den Zielordner (Namensschema wählbar), Prüfung auf Duplikate (gleicher Titel/Künstler/Mix oder
  gleicher Audio-Inhalt), Konflikte melden statt überschreiben.
- Danach Snapshot der Bibliothek, damit spätere Änderungen anderer Programme im Journal erscheinen.

### 7. Download gekaufter Titel (Beatport, später weitere)
- Abgleich „gekauft“ ↔ „schon vorhanden“ und Download der fehlenden in den Eingangsordner.
- Beatport hat keine öffentliche Download-Schnittstelle; das Beatport-Plugin nutzt heute den inoffiziellen Login.
  Zuerst klären: Gibt es für eigene Käufe einen stabilen Weg? Was sagen die Nutzungsbedingungen?
- **Zugangsdaten:** wie bisher nur ein verschlüsseltes Token; das Passwort wird nie gespeichert.

### 8. Entdecken (neue Titel vorschlagen, mit Vorhören)
Machbarkeit je Dienst (Stand 2026-10):
- **Beatport:** Charts, Neuheiten je Genre/Label/Künstler und Vorhör-Ausschnitte über die bestehende Anmeldung –
  realistischste Quelle, Kauf über Link.
- **Spotify:** seit Ende 2024 für neue Apps u. a. Empfehlungen, ähnliche Künstler, Audio-Merkmale und
  Vorschau-Links in Sammelabfragen gesperrt
  ([Spotify, 27.11.2024](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api)) – nur noch
  eigene Daten (z. B. gefolgte Künstler, eigene Playlisten) als Ausgangspunkt.
- **Apple Music:** API mit kostenpflichtigem Entwicklerkonto; zu prüfen.
- **Amazon Music:** keine allgemein zugängliche API bekannt.
- **SoundCloud:** API-Zugang eingeschränkt; zu prüfen.
- Ergänzend frei nutzbar: Deezer (Vorhören 30 s), MusicBrainz (neue Veröffentlichungen bekannter Künstler).
- Ergebnis: Vorschlagsliste mit Vorhören, Merkliste, Link zum Kauf; nichts wird automatisch gekauft.

## Phasen

1. **Grundgerüst (lokal):** Seite, Vorlagen, Tag-Rezepte, ID3v1 schreiben, externe Schritte, Schutzregel,
   Übernahme, Checkliste nachgelagerter Programme.
2. **Online:** Download gekaufter Titel (nach Machbarkeit), weitere Kaufplattformen, optional eigene Lautheit.
3. **Entdecken:** Beatport-Neuheiten mit Vorhören und Merkliste, weitere Quellen.

## Entscheide des Users (2026-10-10)
1. **Stufen-Ordner** (`_02_MP3Tag`, `_03_PlatinumNotes`): nach der Übernahme **optional löschen** (Auswahl, mit Rückfrage).
2. **Platinum Notes:** TagStudio kopiert nach `_03_PlatinumNotes`, Platinum Notes ersetzt die Dateien dort – **ja**.
3. **Picard, AudioRanger, OneTagger:** **vorerst weiter extern**; wenn TagStudio (4.1.0 Online-Metadaten, nur ergänzend)
   den Funktionsumfang komplett abdeckt, eventuell nicht mehr.
4. **Schutzregel – welche Felder:** in Klärung (Erläuterung und Vorschlag in #121).
5. **Beatport-Download:** inoffizieller Zugriff ist **akzeptiert**, falls es keinen offiziellen Weg gibt.
