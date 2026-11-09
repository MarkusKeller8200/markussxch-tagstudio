# ID3-Felder in TagStudioSX

Diese Übersicht wird aus `id3frames.py` erzeugt (`python tools/id3_frames_doc.py`) – bitte nicht von Hand ändern.
Issue #98.

**Grundsätze**

- **Lesen:** alle Frames aus ID3v2.2, v2.3 und v2.4. ID3v2.2 wird beim Laden nach v2.3 umgesetzt (3-Zeichen-IDs →
  4-Zeichen-IDs, auch in LINK); nur `CRM` (verschlüsselte Meta-Daten) hat kein Gegenstück und entfällt.
- **Schreiben:** unveränderte Frames werden **byte-genau** übernommen (auch unbekannte und eigene Frames anderer
  Programme). Beim Wechsel der ID3-Version werden Frames neu verpackt, der Inhalt bleibt.
- **v2.3 ↔ v2.4:** `TYER`/`TDAT` ↔ `TDRC`, `TORY` ↔ `TDOR`, `IPLS` ↔ `TIPL`; `TIME`, `TRDA`, `TSIZ` gibt es in v2.4
  nicht (entfallen beim Umwandeln nach v2.4). Mehrfachwerte: v2.4 null-getrennt, v2.3 mit „ / “ (Personenlisten bleiben
  Paare). Die Stimmung (#12) liegt in v2.4 in `TMOO`, in v2.3 in `TXXX:MOOD`. Andere v2.4-Textfelder (z. B. `TSOA`,
  `TDRL`) werden in v2.3-Dateien unverändert geschrieben – so machen es auch iTunes und viele DJ-Programme.
- **Binär-Frames nur einer Version** (`RVAD`/`EQUA` bzw. `RVA2`/`EQU2`, `ASPI`, `SEEK`, `SIGN`) bleiben beim Umwandeln
  erhalten, die meisten Programme ignorieren sie in der jeweils anderen Version.
- **Verschlüsselte oder komprimierte Frames** werden in derselben Version byte-genau behalten; beim Wechsel der
  ID3-Version können sie nicht neu verpackt werden und entfallen.

**Dateiformate (#156, #263, 4.16.0)**

| Format | Tags von TagStudioSX | Zusätzlich gelesen | Hinweise |
|---|---|---|---|
| MP3 | ID3v2.3/v2.4 am Dateianfang | ID3v1 am Dateiende (wird auf Wunsch mitgeschrieben) | – |
| WAV | ID3v2 im Chunk `id3 ` (bzw. `ID3 `) – **alle Frames wie bei MP3** | RIFF `LIST/INFO`, wenn kein ID3-Chunk da ist (nur lesen) | Einstellung „WAV und AIFF“; RF64 (über 4 GB) nur lesen; kein ID3v1 |
| AIFF / AIFC | ID3v2 im Chunk `ID3 ` – **alle Frames wie bei MP3** | `NAME`, `AUTH`, `(c) `, `ANNO`, wenn kein ID3-Chunk da ist (nur lesen) | Einstellung „WAV und AIFF“; kein ID3v1 |
| MP4 / M4A (AAC, ALAC) | iTunes-Atome `ilst` (fest: `©nam`, `©ART` …), freie Felder `----:com.apple.iTunes:NAME` | – | Test (#265, Einstellung „Weitere Formate“); AAC und ALAC haben dieselben Atome, MP4 (Video) ebenso; Audio bleibt byte-gleich, Offsets werden nachgeführt |
| AAC (.aac, roh) | **kein eigenes Tag-System** | ID3v2 davor bzw. ID3v1 am Ende (nur lesen) | **nur lesen** (#455, Einstellung „Weitere Formate“); für Tags als M4A speichern – Umwandeln › M4A – AAC packt ohne Neukodierung um |
| FLAC / OGG Vorbis | Vorbis-Kommentare (`NAME=Wert`, frei wählbar); Cover in FLAC als `PICTURE`-Block, in OGG als `METADATA_BLOCK_PICTURE` | – | FLAC: Test (#264); **OGG/Opus nur lesen** (#266); Mehrfachwerte über mehrere gleiche Felder; Platzpuffer (PADDING) wird genutzt |

Beim Speichern von WAV/AIFF ersetzt TagStudioSX nur den ID3-Chunk; INFO bzw. NAME/AUTH bleiben unverändert. Ob die
DJ-Programme ein Feld in WAV/AIFF auch lesen, ist je Programm verschieden (Messreihe #446).

**Spalten:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 oder inoffiziell · MP3 / WAV / AIFF = schreibbar (✔); dahinter
das entsprechende Feld in ID3v1 bzw. im INFO-/AIFF-Textchunk (nur lesen) · MP4 / M4A, AAC, FLAC / OGG = Name des Felds
im jeweiligen Format (so liest und schreibt TagStudioSX es; Namen mit Testdateien zu bestätigen, #453): ✔ = Standardfeld,
◐ = nur als freies Feld bzw. per Konvention, ✖ = gibt es nicht, * = Unterschied zwischen FLAC und OGG (unter der Tabelle)
· Anzeige = Text, Bild, lesbare Kurzfassung oder Grösse + Prüfsumme · Bearbeiten = womit TagStudioSX das Feld ändern kann
· Mp3tag = Feldname in Mp3tag.

| Frame | v2.2 | Version | Bezeichnung | MP3 | WAV | AIFF | MP4 / M4A (AAC, ALAC) | AAC | FLAC / OGG | Anzeige | Bearbeiten | Mp3tag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `AENC` | CRA | 2.3 + 2.4 | Audio-Verschlüsselung | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `APIC` | PIC | 2.3 + 2.4 | Bild / Cover | ✔ | ✔ | ✔ | ✔ `covr` (nur JPEG/PNG, ohne Bildart) | ◐ ID3v2 davor, nur lesen | ✔ `PICTURE`-Block (mit Bildart) * | Bild | Cover-Werkzeuge | PICTURE |
| `ASPI` | – | nur 2.4 | Audio-Suchindex | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `CHAP` | – | 2.3 + 2.4 | Kapitel | ✔ | ✔ | ✔ | ✖ noch nicht (eigene Kapitel-Spur) | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `COMM` | COM | 2.3 + 2.4 | Kommentar | ✔ · ID3v1 | ✔ · INFO `ICMT` | ✔ · `ANNO` | ✔ `©cmt` | ◐ ID3v2 davor, nur lesen | ✔ `COMMENT` (manche: `DESCRIPTION`) | Text | Text | COMMENT |
| `COMR` | – | 2.3 + 2.4 | Kommerziell | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `CTOC` | – | 2.3 + 2.4 | Inhaltsverzeichnis (Kapitel) | ✔ | ✔ | ✔ | ✖ noch nicht (eigene Kapitel-Spur) | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `ENCR` | – | 2.3 + 2.4 | Verschlüsselungsmethode | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `EQU2` | – | nur 2.4 | Equalizer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `EQUA` | EQU | nur 2.3 | Equalizer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `ETCO` | ETC | 2.3 + 2.4 | Ereignis-Zeitpunkte | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `GEOB` | GEO | 2.3 + 2.4 | Eingebettete Daten | ✔ | ✔ | ✔ | ◐ Serato: `----:com.serato.dj:…` bleibt unverändert erhalten | ◐ ID3v2 davor, nur lesen | ◐ Serato: `SERATO_…` (Base64) bleibt unverändert erhalten * | lesbar | Binärfeld-Editor | – |
| `GRID` | – | 2.3 + 2.4 | Gruppen-ID | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `GRP1` | GP1 | inoffiziell | Gruppierung (iTunes) | ✔ | ✔ | ✔ | ✔ `©grp` | ◐ ID3v2 davor, nur lesen | ✔ `GROUPING` | Text | Text | GROUPING |
| `IPLS` | IPL | nur 2.3 | Beteiligte Personen | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `LINK` | LNK | 2.3 + 2.4 | Verknüpfung | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `MCDI` | MCI | 2.3 + 2.4 | CD-Inhaltsverzeichnis | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `MLLT` | MLL | 2.3 + 2.4 | MPEG-Lookup-Tabelle | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `MVIN` | MVI | inoffiziell | Satznummer (iTunes) | ✔ | ✔ | ✔ | ✔ `©mvi` + `©mvc` | ◐ ID3v2 davor, nur lesen | ✔ `MOVEMENTNUMBER` | Text | Text | MOVEMENT |
| `MVNM` | MVN | inoffiziell | Satzname (iTunes) | ✔ | ✔ | ✔ | ✔ `©mvn` | ◐ ID3v2 davor, nur lesen | ✔ `MOVEMENTNAME` | Text | Text | MOVEMENTNAME |
| `OWNE` | – | 2.3 + 2.4 | Besitzer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `PCNT` | CNT | 2.3 + 2.4 | Wiedergabezähler | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `PCST` | PCS | inoffiziell | Podcast-Kennzeichen (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `POPM` | POP | 2.3 + 2.4 | Bewertung | ✔ | ✔ | ✔ | ✖ noch nicht – Konvention wird gemessen (#453) | ◐ ID3v2 davor, nur lesen | ✖ noch nicht – `RATING`/`FMPS_RATING` wird gemessen (#453) | lesbar | Bewertung (Sterne) | RATING |
| `POSS` | – | 2.3 + 2.4 | Positions-Synchronisation | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `PRIV` | – | 2.3 + 2.4 | Private Daten | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | Binärfeld-Editor | – |
| `RBUF` | BUF | 2.3 + 2.4 | Puffergrösse | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `RVA2` | – | nur 2.4 | Lautstärke-Anpassung | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `RVAD` | RVA | nur 2.3 | Lautstärke-Anpassung | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `RVRB` | REV | 2.3 + 2.4 | Hall | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `SEEK` | – | nur 2.4 | Suchmarke | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `SIGN` | – | nur 2.4 | Signatur | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `SYLT` | SLT | 2.3 + 2.4 | Synchronisierter Liedtext | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ noch nicht | lesbar | – | – |
| `SYTC` | STC | 2.3 + 2.4 | Tempo-Code | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `TALB` | TAL | 2.3 + 2.4 | Album | ✔ · ID3v1 | ✔ · INFO `IPRD` | ✔ | ✔ `©alb` | ◐ ID3v2 davor, nur lesen | ✔ `ALBUM` | Text | Text | ALBUM |
| `TBPM` | TBP | 2.3 + 2.4 | Beats pro Minute | ✔ | ✔ | ✔ | ◐ `tmpo` (nur ganze Zahl) | ◐ ID3v2 davor, nur lesen | ✔ `BPM` | Text | Text | BPM |
| `TCAT` | TCT | inoffiziell | Podcast-Kategorie (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TCMP` | TCP | inoffiziell | Zusammenstellung (iTunes) | ✔ | ✔ | ✔ | ✔ `cpil` | ◐ ID3v2 davor, nur lesen | ✔ `COMPILATION` | Text | Text | COMPILATION |
| `TCOM` | TCM | 2.3 + 2.4 | Komponist | ✔ | ✔ | ✔ | ✔ `©wrt` | ◐ ID3v2 davor, nur lesen | ✔ `COMPOSER` | Text | Text | COMPOSER |
| `TCON` | TCO | 2.3 + 2.4 | Genre | ✔ · ID3v1 | ✔ · INFO `IGNR` | ✔ | ✔ `©gen` | ◐ ID3v2 davor, nur lesen | ✔ `GENRE` | Text | Text | GENRE |
| `TCOP` | TCR | 2.3 + 2.4 | Copyright | ✔ | ✔ · INFO `ICOP` | ✔ · `(c)` | ✔ `cprt` | ◐ ID3v2 davor, nur lesen | ✔ `COPYRIGHT` | Text | Text | COPYRIGHT |
| `TDAT` | TDA | nur 2.3 | Datum (TTMM) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TDEN` | – | nur 2.4 | Kodierungsdatum | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TDES` | TDS | inoffiziell | Podcast-Beschreibung (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TDLY` | TDY | 2.3 + 2.4 | Verzögerung | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TDOR` | – | nur 2.4 | Originalveröffentlichungsdatum | ✔ | ✔ | ✔ | ◐ `----:ORIGINALDATE` | ◐ ID3v2 davor, nur lesen | ✔ `ORIGINALDATE` | Text | Text | ORIGYEAR |
| `TDRC` | – | nur 2.4 | Aufnahmedatum | ✔ · ID3v1 | ✔ · INFO `ICRD` | ✔ | ✔ `©day` | ◐ ID3v2 davor, nur lesen | ✔ `DATE` | Text | Text | YEAR |
| `TDRL` | – | nur 2.4 | Veröffentlichungsdatum | ✔ | ✔ | ✔ | ◐ `----:RELEASEDATE` | ◐ ID3v2 davor, nur lesen | ✔ `RELEASEDATE` | Text | Text | RELEASETIME |
| `TDTG` | – | nur 2.4 | Tagging-Datum | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | TAGGINGTIME |
| `TENC` | TEN | 2.3 + 2.4 | Kodiert von | ✔ | ✔ | ✔ | ✔ `©enc` | ◐ ID3v2 davor, nur lesen | ✔ `ENCODEDBY` | Text | Text | ENCODEDBY |
| `TEXT` | TXT | 2.3 + 2.4 | Texter | ✔ | ✔ | ✔ | ◐ `----:LYRICIST` | ◐ ID3v2 davor, nur lesen | ✔ `LYRICIST` | Text | Text | LYRICIST |
| `TFLT` | TFT | 2.3 + 2.4 | Dateityp | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | FILETYPE |
| `TGID` | TID | inoffiziell | Podcast-ID (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TIME` | TIM | nur 2.3 | Uhrzeit (HHMM) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TIPL` | – | nur 2.4 | Beteiligte Personen | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | INVOLVEDPEOPLE |
| `TIT1` | TT1 | 2.3 + 2.4 | Inhaltliche Gruppierung | ✔ | ✔ | ✔ | ✔ `©wrk` | ◐ ID3v2 davor, nur lesen | ✔ `WORK` | Text | Text | CONTENTGROUP |
| `TIT2` | TT2 | 2.3 + 2.4 | Titel | ✔ · ID3v1 | ✔ · INFO `INAM` | ✔ · `NAME` | ✔ `©nam` | ◐ ID3v2 davor, nur lesen | ✔ `TITLE` | Text | Text | TITLE |
| `TIT3` | TT3 | 2.3 + 2.4 | Untertitel | ✔ | ✔ | ✔ | ◐ `----:SUBTITLE` | ◐ ID3v2 davor, nur lesen | ✔ `SUBTITLE` | Text | Text | SUBTITLE |
| `TKEY` | TKE | 2.3 + 2.4 | Tonart | ✔ | ✔ | ✔ | ◐ `----:initialkey` | ◐ ID3v2 davor, nur lesen | ◐ `INITIALKEY` (manche: `KEY`) | Text | Text | INITIALKEY |
| `TKWD` | TKW | inoffiziell | Podcast-Schlüsselwörter (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TLAN` | TLA | 2.3 + 2.4 | Sprache | ✔ | ✔ | ✔ | ◐ `----:LANGUAGE` | ◐ ID3v2 davor, nur lesen | ✔ `LANGUAGE` | Text | Text | LANGUAGE |
| `TLEN` | TLE | 2.3 + 2.4 | Länge (ms) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | LENGTH |
| `TMCL` | – | nur 2.4 | Musiker | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | MUSICIANCREDITS |
| `TMED` | TMT | 2.3 + 2.4 | Medientyp | ✔ | ✔ | ✔ | ◐ `----:MEDIA` | ◐ ID3v2 davor, nur lesen | ✔ `MEDIA` | Text | Text | MEDIATYPE |
| `TMOO` | – | nur 2.4 | Stimmung | ✔ | ✔ | ✔ | ◐ `----:MOOD` | ◐ ID3v2 davor, nur lesen | ✔ `MOOD` | Text | Text | MOOD |
| `TOAL` | TOT | 2.3 + 2.4 | Originalalbum | ✔ | ✔ | ✔ | ◐ freies Feld über TXXX | ◐ ID3v2 davor, nur lesen | ✔ `ORIGINALALBUM` | Text | Text | ORIGALBUM |
| `TOFN` | TOF | 2.3 + 2.4 | Originaldateiname | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | ORIGFILENAME |
| `TOLY` | TOL | 2.3 + 2.4 | Originaltexter | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | ORIGLYRICIST |
| `TOPE` | TOA | 2.3 + 2.4 | Originalkünstler | ✔ | ✔ | ✔ | ◐ freies Feld über TXXX | ◐ ID3v2 davor, nur lesen | ✔ `ORIGINALARTIST` | Text | Text | ORIGARTIST |
| `TORY` | TOR | nur 2.3 | Originaljahr | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TOWN` | – | 2.3 + 2.4 | Eigentümer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | FILEOWNER |
| `TPE1` | TP1 | 2.3 + 2.4 | Künstler | ✔ · ID3v1 | ✔ · INFO `IART` | ✔ · `AUTH` | ✔ `©ART` | ◐ ID3v2 davor, nur lesen | ✔ `ARTIST` | Text | Text | ARTIST |
| `TPE2` | TP2 | 2.3 + 2.4 | Album-Künstler | ✔ | ✔ | ✔ | ✔ `aART` | ◐ ID3v2 davor, nur lesen | ✔ `ALBUMARTIST` | Text | Text | ALBUMARTIST |
| `TPE3` | TP3 | 2.3 + 2.4 | Dirigent | ✔ | ✔ | ✔ | ◐ `----:CONDUCTOR` | ◐ ID3v2 davor, nur lesen | ✔ `CONDUCTOR` | Text | Text | CONDUCTOR |
| `TPE4` | TP4 | 2.3 + 2.4 | Remix / Bearbeitung | ✔ | ✔ | ✔ | ◐ `----:REMIXER` | ◐ ID3v2 davor, nur lesen | ✔ `REMIXER` | Text | Text | MIXARTIST |
| `TPOS` | TPA | 2.3 + 2.4 | Disknummer | ✔ | ✔ | ✔ | ✔ `disk` | ◐ ID3v2 davor, nur lesen | ✔ `DISCNUMBER` (+ `DISCTOTAL`) | Text | Text | DISCNUMBER |
| `TPRO` | – | nur 2.4 | Produktionshinweis | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | PRODUCEDNOTICE |
| `TPUB` | TPB | 2.3 + 2.4 | Herausgeber / Label | ✔ | ✔ | ✔ | ◐ `----:LABEL` | ◐ ID3v2 davor, nur lesen | ◐ `LABEL` (auch `ORGANIZATION`, `PUBLISHER`) | Text | Text | PUBLISHER |
| `TRCK` | TRK | 2.3 + 2.4 | Spurnummer | ✔ · ID3v1 | ✔ · INFO `ITRK`, `IPRT` | ✔ | ✔ `trkn` (Nr. + Anzahl) | ◐ ID3v2 davor, nur lesen | ✔ `TRACKNUMBER` (+ `TRACKTOTAL`) | Text | Text | TRACK |
| `TRDA` | TRD | nur 2.3 | Aufnahmedaten | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TRSN` | – | 2.3 + 2.4 | Internetradio-Name | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TRSO` | – | 2.3 + 2.4 | Internetradio-Eigentümer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TSIZ` | TSI | nur 2.3 | Grösse (Bytes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `TSO2` | TS2 | inoffiziell | Album-Künstler einsortieren als (iTunes) | ✔ | ✔ | ✔ | ✔ `soaa` | ◐ ID3v2 davor, nur lesen | ✔ `ALBUMARTISTSORT` | Text | Text | ALBUMARTISTSORT |
| `TSOA` | TSA | nur 2.4 | Album einsortieren als | ✔ | ✔ | ✔ | ✔ `soal` | ◐ ID3v2 davor, nur lesen | ✔ `ALBUMSORT` | Text | Text | ALBUMSORT |
| `TSOC` | TSC | inoffiziell | Komponist einsortieren als (iTunes) | ✔ | ✔ | ✔ | ✔ `soco` | ◐ ID3v2 davor, nur lesen | ✔ `COMPOSERSORT` | Text | Text | COMPOSERSORT |
| `TSOP` | TSP | nur 2.4 | Künstler einsortieren als | ✔ | ✔ | ✔ | ✔ `soar` | ◐ ID3v2 davor, nur lesen | ✔ `ARTISTSORT` | Text | Text | ARTISTSORT |
| `TSOT` | TST | nur 2.4 | Titel einsortieren als | ✔ | ✔ | ✔ | ✔ `sonm` | ◐ ID3v2 davor, nur lesen | ✔ `TITLESORT` | Text | Text | TITLESORT |
| `TSRC` | TRC | 2.3 + 2.4 | ISRC | ✔ | ✔ | ✔ | ◐ `----:ISRC` | ◐ ID3v2 davor, nur lesen | ✔ `ISRC` | Text | Text | ISRC |
| `TSSE` | TSS | 2.3 + 2.4 | Kodierung Einstellungen | ✔ | ✔ · INFO `ISFT` | ✔ | ✔ `©too` | ◐ ID3v2 davor, nur lesen | ◐ `ENCODING` (Mp3tag: `ENCODERSETTINGS`) | Text | Text | ENCODERSETTINGS |
| `TSST` | – | nur 2.4 | Disc-Untertitel | ✔ | ✔ | ✔ | ◐ `----:DISCSUBTITLE` | ◐ ID3v2 davor, nur lesen | ✔ `DISCSUBTITLE` | Text | Text | SETSUBTITLE |
| `TXXX` | TXX | 2.3 + 2.4 | Benutzertext | ✔ | ✔ | ✔ | ✔ `----:com.apple.iTunes:<NAME>` | ◐ ID3v2 davor, nur lesen | ✔ `<NAME>` | Text | Text | – |
| `TYER` | TYE | nur 2.3 | Jahr | ✔ · ID3v1 | ✔ · INFO `ICRD` | ✔ | ✔ `©day` | ◐ ID3v2 davor, nur lesen | ✔ `DATE` | Text | Text | – |
| `UFID` | UFI | 2.3 + 2.4 | Eindeutige Datei-ID | ✔ | ✔ | ✔ | ✖ noch nicht | ◐ ID3v2 davor, nur lesen | ✖ noch nicht | lesbar | – | UNIQUEFILEID |
| `USER` | – | 2.3 + 2.4 | Nutzungsbedingungen | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | lesbar | – | – |
| `USLT` | ULT | 2.3 + 2.4 | Liedtext | ✔ | ✔ | ✔ | ✔ `©lyr` | ◐ ID3v2 davor, nur lesen | ✔ `LYRICS` | Text | Text | UNSYNCEDLYRICS |
| `WCOM` | WCM | 2.3 + 2.4 | Kauf-Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWCOMMERCIALINFO |
| `WCOP` | WCP | 2.3 + 2.4 | Copyright-Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWCOPYRIGHT |
| `WFED` | WFD | inoffiziell | Podcast-Feed (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `WOAF` | WAF | 2.3 + 2.4 | Audiodatei Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWAUDIOFILE |
| `WOAR` | WAR | 2.3 + 2.4 | Künstler Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWARTIST |
| `WOAS` | WAS | 2.3 + 2.4 | Audioquelle Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWAUDIOSOURCE |
| `WORS` | – | 2.3 + 2.4 | Internetradio Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `WPAY` | – | 2.3 + 2.4 | Bezahlung Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWPAYMENT |
| `WPUB` | WPB | 2.3 + 2.4 | Herausgeber Internetseite | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | WWWPUBLISHER |
| `WXXX` | WXX | 2.3 + 2.4 | Benutzer-Link | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `XSOA` | – | inoffiziell | Album einsortieren als (v2.3, iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `XSOP` | – | inoffiziell | Künstler einsortieren als (v2.3, iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |
| `XSOT` | – | inoffiziell | Titel einsortieren als (v2.3, iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 davor, nur lesen | ✖ | Text | Text | – |

**Unterschiede FLAC ↔ OGG** (in der Tabelle mit * markiert):

- `APIC`: OGG: Cover als Base64-Feld `METADATA_BLOCK_PICTURE`
- `GEOB`: OGG: ob Serato hier Daten ablegt, ist noch zu messen

**Nur in ID3v2.2 (entfällt):** `CRM` Verschlüsselte Meta-Daten (nur ID3v2.2)
