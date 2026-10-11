# Konzept: WAV-Unterstützung

Status: **Entwurf** (2026-10-11) – Issue #156. Testroutine: `tools/wavcheck.py`, Tests `tests/test_wavcheck.py`.

## Ziel

WAV-Dateien im Tagger wie MP3 lesen und bearbeiten (Titel, Künstler, BPM, Tonart, Cover …), ohne die Audiodaten
anzufassen, und so, dass DJ-Programme die Tags wiederfinden. Heute zeigt TagStudio WAV nur als Stem-Spur zum Anhören.

## Welche Tags gibt es in WAV?

WAV ist ein RIFF-Container: eine Folge von Chunks (`fmt `, `data`, …). Tags stehen in eigenen Chunks:

| Chunk | Inhalt | Bewertung |
|---|---|---|
| `id3 ` (auch `ID3 `) | ein vollständiges ID3v2-Tag (wie bei MP3) | **Hauptweg**: alle Felder, die TagStudio schon kann (TXXX, Cover, POPM, GEOB/Serato …). So schreiben es Mp3tag und viele DJ-Programme. |
| `LIST` Typ `INFO` | wenige Textfelder: INAM Titel, IART Künstler, IPRD Album, ICRD Datum, IGNR Genre, ICMT Kommentar, ITRK Spur | **mitpflegen** für Windows-Explorer und ältere Programme; keine BPM/Tonart/Cover |
| `bext` | Broadcast-Wave: Beschreibung, Urheber, Datum, Zeitcode | nur anzeigen |
| `cue ` + `LIST adtl` | Cue-Punkte mit Namen | später: als Cues im Player anzeigen |
| `acid` | Tempo, Grundton (ACIDized WAV) | anzeigen; BPM-Quelle, falls kein ID3-BPM |
| `iXML`, `_PMX` (XMP) | Metadaten aus Studio-Programmen | nur anzeigen |

Wichtig:
- Chunks haben eine gerade Länge (ein Füllbyte bei ungerader Länge); die RIFF-Grösse im Kopf muss nach jeder
  Änderung stimmen.
- **RF64** (WAV über 4 GB) hat statt der 32-Bit-Grössen einen `ds64`-Chunk – im ersten Schritt nur lesen, nicht
  schreiben.
- Felder **beide** pflegen (ID3 und INFO) – bei Abweichung gilt ID3, INFO wird beim Speichern angeglichen.

## Unterstützung in DJ-Programmen (zu prüfen)

Was die Programme bei WAV tatsächlich lesen und schreiben, ist je Version verschieden und nicht verlässlich
dokumentiert. Deshalb **messen statt annehmen**: mit `tools/wavcheck.py` je eine WAV-Datei prüfen, die von
Rekordbox, Serato, Traktor, Engine DJ, Lexicon und Mp3tag getaggt wurde (welcher Chunk, welche ID3-Version, welche
Felder). Ergebnis hier als Tabelle nachtragen, bevor das Schreiben gebaut wird.

## Testroutine

```
python tools/wavcheck.py DATEI.wav [...]            # Aufbau, INFO, ID3-Chunk, bext, Cues, acid – nur lesen
python tools/wavcheck.py DATEI.wav --roundtrip      # zusätzlich Schreibtest an einer KOPIE
```

Der Schreibtest kopiert die Datei in einen temporären Ordner, schreibt einen ID3-Chunk mit allen vorhandenen
Textfeldern plus `TXXX:TAGSTUDIO_WAVCHECK=ok`, liest neu und prüft: RIFF-Aufbau stimmt, Feld ist da, INFO
unverändert, **Audiodaten byte-gleich** (SHA-256 des `data`-Chunks), Python-`wave` kann die Datei noch öffnen.
Das Original wird nie verändert. Die automatischen Tests (`tests/test_wavcheck.py`) machen dasselbe mit
erzeugten WAV-Dateien und prüfen auch eine kaputte RIFF-Grösse.

Vorschlag für den Test durch den User: einige WAV-Dateien aus der Bibliothek bzw. Stems mit `--roundtrip` prüfen
und die Kopie in den DJ-Programmen öffnen (Felder sichtbar? Cues/Beatgrid erhalten?).

## Umsetzung in Schritten

1. **Lesen:** `MP3File` um einen WAV-Zweig erweitern (Chunk-Liste, ID3-Chunk über den bestehenden Parser, INFO als
   Ersatz, Dauer aus `fmt `/`data`). Tagger, Vergleich, Snapshots und Listen-Cache bekommen WAV-Dateien.
2. **Schreiben:** ID3-Chunk ersetzen bzw. anhängen (Prototyp `write_id3` aus `wavcheck.py`: alle anderen Chunks
   byte-genau übernehmen, über temporäre Datei atomar ersetzen), INFO-Felder angleichen, Sicherung wie bei MP3.
3. **Player/Stems:** WAV-Stems erhalten Tags (heute nur MP3-Stems).
4. **Nicht im ersten Schritt:** RF64 schreiben, AIFF/FLAC (eigene Formate), Cue-Chunk schreiben.

## Offene Fragen an den User

- Welche Programme sollen die WAV-Tags sicher lesen (Reihenfolge der Prüfung)?
- Sollen WAV-Dateien in der Bibliothek liegen (nicht nur Stems)?
