# Konzept: Weitere Dateiformate (WAV, AIFF, FLAC, M4A, OGG)

> Stand 24.10.2026 – Auftrag des Users: Konzept für die bei DJs gängigen Formate. **Nur Konzept**, Umsetzung nach Freigabe.
> Issues: #262 (Grundlage) · #156 (WAV, Detailkonzept [KONZEPT-WAV.md](KONZEPT-WAV.md)) · #263 (AIFF) · #264 (FLAC) ·
> #265 (M4A) · #266 (OGG/Opus)

## 1. Ausgangslage

TagStudio ist um **ID3 in MP3** gebaut: `id3tags.MP3File`, Feldschlüssel wie `TXXX:ENERGY`, `GEOB:Serato Markers2`,
`APIC`, `POPM`. Tagger, Vergleich, Snapshots, Sicherungen, Listen-Cache, Herkunft (`origins.py`) und alle Plugins
nutzen diese Schlüssel. WAV-Dateien erscheinen heute nur als Stem-Spuren zum Anhören.

**Vorgabe des Users (für WAV, gilt sinngemäss für alle):** Die Tags müssen in **Engine DJ, Serato, Rekordbox und
VirtualDJ** lesbar sein.

## 2. Formate im Überblick

| Format | Tag-System | Verbreitung bei DJs | Aufwand | Stufe | Issue |
|---|---|---|---|---|---|
| WAV | `id3 `-Chunk (ID3v2) + RIFF `LIST/INFO` | hoch (Beatport-WAV, Promos) | mittel | 1 | #156 |
| AIFF/AIFC | `ID3 `-Chunk (ID3v2), Big-Endian-Container | hoch (Rekordbox-/Mac-Nutzer) | klein, sobald WAV steht | 1 | #263 |
| FLAC | Vorbis-Kommentare + `PICTURE`-Block | mittel | mittel | 2 | #264 |
| M4A (AAC/ALAC) | MP4-Atome `ilst`, freie Felder `----:com.apple.iTunes:…` | mittel (Apple Music, ältere Käufe) | gross | 3 | #265 |
| OGG Vorbis/Opus | Vorbis-Kommentare, Cover Base64 | gering | klein–mittel | 4 (evtl. nur Lesen) | #266 |

Was die DJ-Programme je Format tatsächlich lesen/schreiben, wird wie bei WAV **gemessen statt angenommen**: je Format
Testdateien aus Rekordbox, Serato, Engine DJ, VirtualDJ, Lexicon und Mp3tag mit einem Prüfwerkzeug (Vorbild
`tools/wavcheck.py`) auswerten und die Tabelle hier nachtragen.

## 3. Grundlage: Zwischenschicht (#262)

1. **Eine Schnittstelle für alle Dateien:** lesen, Felder (`items`), Text lesen/setzen, Cover, Bewertung, Audio-Länge,
   speichern, Prüfsumme der Audiodaten. `MP3File` wird eine Umsetzung davon; je Format eine weitere Klasse.
2. **TagStudio-Feldschlüssel bleiben die gemeinsame Sprache** (ID3-Namen). Je Format eine Übersetzungstabelle:

   | TagStudio | FLAC/OGG (Vorbis) | M4A (MP4) |
   |---|---|---|
   | `TIT2` Titel | `TITLE` | `©nam` |
   | `TPE1` Künstler | `ARTIST` | `©ART` |
   | `TALB` Album | `ALBUM` | `©alb` |
   | `TBPM` BPM | `BPM` | `tmpo` (ganzzahlig) bzw. `----:…:BPM` |
   | `TKEY` Tonart | `INITIALKEY` | `----:com.apple.iTunes:initialkey` |
   | `TSRC` ISRC | `ISRC` | `----:com.apple.iTunes:ISRC` |
   | `TPUB` Label | `LABEL` bzw. `ORGANIZATION` | `----:com.apple.iTunes:LABEL` |
   | `TXXX:<NAME>` | `<NAME>` | `----:com.apple.iTunes:<NAME>` |
   | `APIC` Cover | `PICTURE`-Block | `covr` |
   | `POPM` Bewertung | `RATING` (Konvention je Programm) | `----:…:RATING` |
   | `GEOB:Serato …` | `SERATO_…` (Base64) | `----:com.serato.dj:…` |

   Die genauen Namen je Programm (z. B. `INITIALKEY` vs. `KEY`) werden mit den Testdateien festgelegt. Felder ohne
   Entsprechung werden angezeigt, aber nicht geschrieben (Hinweis in der Vorschau).
3. **Überall umstellen:** Einlesen (Dateiendungen), Listen-Cache, Snapshots/Sicherungen (Format im Journal), Vergleich
   (nur gleiche Felder vergleichbar), Herkunft (Muster auch für Vorbis/MP4-Namen), Player/Wellenform (FFmpeg/Browser
   können alle Formate abspielen – AIFF/ALAC im Browser prüfen), Plugins (jedes Plugin nennt, welche Formate es kann).
4. **Einstellung:** welche Formate in Tagger und Bibliothek aufgenommen werden (Standard: alle lesbaren).

## 4. Grundsätze

- **Audiodaten nie verändern:** jedes Schreiben atomar über eine temporäre Datei, danach Prüfsumme der Audiodaten
  vergleichen; Sicherung wie bei MP3.
- **Erst lesen, dann schreiben:** je Format zuerst nur Lesen freigeben, Schreiben erst nach dem Test mit den
  DJ-Programmen.
- **Serato-Daten** (Cues, Beatgrid, Wellenform) je Format in deren Ablage (`serato.py` erweitern) – nie verlieren.
- **Keine neuen Pflicht-Abhängigkeiten:** wie heute möglichst nur Standardbibliothek; falls nötig (M4A), eine
  Bibliothek mit verträglicher Lizenz (z. B. mutagen, GPL-2.0 → Lizenzfrage vorher klären) – Entscheid offen.

## 5. Reihenfolge (Vorschlag)

1. **Stufe 1:** #262 Zwischenschicht + #156 WAV + #263 AIFF (beide ID3 → wenig Neues).
2. **Stufe 2:** #264 FLAC.
3. **Stufe 3:** #265 M4A.
4. **Stufe 4:** #266 OGG/Opus, eventuell nur Lesen.

## 6. Offen

- Sollen diese Formate in die Bibliothek (nicht nur Stems/Vorbereiten)? (Frage aus KONZEPT-WAV)
- Testdateien je Format aus den DJ-Programmen (vom User) → Tabelle in Abschnitt 2 nachtragen.
- Eigene Umsetzung je Format oder Bibliothek (Lizenz, z. B. mutagen GPL-2.0).
- Formatwandlung (z. B. WAV → AIFF/FLAC) ist **nicht** Teil dieses Konzepts.
