# ID3 fields in TagStudio

*English version – [Deutsch](ID3-FELDER.md).* This overview is generated from `id3frames.py`
(`python tools/id3_frames_doc.py`) – please do not edit it by hand. Issue #98.

**Principles**

- **Reading:** all frames from ID3v2.2, v2.3 and v2.4. ID3v2.2 is converted to v2.3 when loading (3-character IDs →
  4-character IDs, in LINK too); only `CRM` (encrypted meta data) has no counterpart and is dropped.
- **Writing:** unchanged frames are taken over **byte-exactly** (unknown frames and other programs' own frames too).
  When the ID3 version changes, frames are repacked, the content stays.
- **v2.3 ↔ v2.4:** `TYER`/`TDAT` ↔ `TDRC`, `TORY` ↔ `TDOR`, `IPLS` ↔ `TIPL`; `TIME`, `TRDA`, `TSIZ` do not exist in
  v2.4 (dropped when converting to v2.4). Multiple values: v2.4 null-separated, v2.3 with “ / ” (people lists stay
  pairs). The mood (#12) is stored in `TMOO` in v2.4 and in `TXXX:MOOD` in v2.3. Other v2.4 text fields (e.g. `TSOA`,
  `TDRL`) are written unchanged into v2.3 files – iTunes and many DJ programs do the same.
- **Binary frames of only one version** (`RVAD`/`EQUA` or `RVA2`/`EQU2`, `ASPI`, `SEEK`, `SIGN`) are kept when
  converting; most programs ignore them in the other version.
- **Encrypted or compressed frames** are kept byte-exactly in the same version; when the ID3 version changes they
  cannot be repacked and are dropped.

**File formats (#156, #263, 4.16.0)**

| Format | Tags written by TagStudio | Also read | Notes |
|---|---|---|---|
| MP3 | ID3v2.3/v2.4 at the start of the file | ID3v1 at the end (written too on request) | – |
| WAV | ID3v2 in the `id3 ` (or `ID3 `) chunk – **all frames as with MP3** | RIFF `LIST/INFO` if there is no ID3 chunk (read only) | setting “WAV and AIFF”; RF64 (over 4 GB) read only; no ID3v1 |
| AIFF / AIFC | ID3v2 in the `ID3 ` chunk – **all frames as with MP3** | `NAME`, `AUTH`, `(c) `, `ANNO` if there is no ID3 chunk (read only) | setting “WAV and AIFF”; no ID3v1 |
| MP4 / M4A (AAC, ALAC) | iTunes atoms `ilst` (fixed: `©nam`, `©ART` …), free fields `----:com.apple.iTunes:NAME` | – | test (#265, setting “More formats”); AAC and ALAC use the same atoms, so does MP4 (video); audio stays byte-identical, offsets are updated |
| AAC (.aac, raw) | **no tag system of its own** | – | some programs put an ID3v2 in front or append APEv2, rarely read – better use M4A |
| FLAC / OGG Vorbis | Vorbis comments (`NAME=value`, free names); cover in FLAC as `PICTURE` block, in OGG as `METADATA_BLOCK_PICTURE` | – | FLAC: test (#264); **OGG/Opus read only** (#266); multiple values via repeated fields; padding is used |

When saving WAV/AIFF, TagStudio only replaces the ID3 chunk; INFO or NAME/AUTH stay unchanged. Whether DJ programs
also read a field in WAV/AIFF differs per program (test series #446).

**Columns:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 or unofficial · MP3 / WAV / AIFF = writable (✔); after it the
matching field in ID3v1 or in the INFO/AIFF text chunk (read only) · MP4 / M4A, AAC, FLAC / OGG = name of the field in
that format (how TagStudio reads and writes it; names to be confirmed with test files, #453): ✔ = standard field,
◐ = only as a free field or by convention, ✖ = does not exist, * = difference between FLAC and OGG (below the table)
· Display = text, image, readable summary or size + checksum · Edit = what TagStudio can change the field with
· Mp3tag = field name in Mp3tag.

| Frame | v2.2 | Version | Name | MP3 | WAV | AIFF | MP4 / M4A (AAC, ALAC) | AAC | FLAC / OGG | Display | Edit | Mp3tag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `AENC` | CRA | 2.3 + 2.4 | Audio encryption | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `APIC` | PIC | 2.3 + 2.4 | Image / cover | ✔ | ✔ | ✔ | ✔ `covr` (JPEG/PNG only, no picture type) | ◐ ID3v2 | ✔ `PICTURE` block (with picture type) * | Image | Cover tools | PICTURE |
| `ASPI` | – | 2.4 only | Audio seek index | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `CHAP` | – | 2.3 + 2.4 | Chapter | ✔ | ✔ | ✔ | ✖ not yet (separate chapter track) | ◐ ID3v2 | ✖ | readable | – | – |
| `COMM` | COM | 2.3 + 2.4 | Comment | ✔ · ID3v1 | ✔ · INFO `ICMT` | ✔ · `ANNO` | ✔ `©cmt` | ◐ ID3v2 | ✔ `COMMENT` (some: `DESCRIPTION`) | Text | Text | COMMENT |
| `COMR` | – | 2.3 + 2.4 | Commercial | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `CTOC` | – | 2.3 + 2.4 | Table of contents (chapters) | ✔ | ✔ | ✔ | ✖ not yet (separate chapter track) | ◐ ID3v2 | ✖ | readable | – | – |
| `ENCR` | – | 2.3 + 2.4 | Encryption method | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `EQU2` | – | 2.4 only | Equalizer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `EQUA` | EQU | 2.3 only | Equalizer | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `ETCO` | ETC | 2.3 + 2.4 | Event timing | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `GEOB` | GEO | 2.3 + 2.4 | Embedded data | ✔ | ✔ | ✔ | ◐ Serato: `----:com.serato.dj:…` is kept unchanged | ◐ ID3v2 | ◐ Serato: `SERATO_…` (Base64) is kept unchanged * | readable | Binary field editor | – |
| `GRID` | – | 2.3 + 2.4 | Group ID | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `GRP1` | GP1 | unofficial | Grouping (iTunes) | ✔ | ✔ | ✔ | ✔ `©grp` | ◐ ID3v2 | ✔ `GROUPING` | Text | Text | GROUPING |
| `IPLS` | IPL | 2.3 only | Involved people | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `LINK` | LNK | 2.3 + 2.4 | Shortcut | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `MCDI` | MCI | 2.3 + 2.4 | CD table of contents | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `MLLT` | MLL | 2.3 + 2.4 | MPEG-Lookup-Tabelle | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `MVIN` | MVI | unofficial | Movement number (iTunes) | ✔ | ✔ | ✔ | ✔ `©mvi` + `©mvc` | ◐ ID3v2 | ✔ `MOVEMENTNUMBER` | Text | Text | MOVEMENT |
| `MVNM` | MVN | unofficial | Movement name (iTunes) | ✔ | ✔ | ✔ | ✔ `©mvn` | ◐ ID3v2 | ✔ `MOVEMENTNAME` | Text | Text | MOVEMENTNAME |
| `OWNE` | – | 2.3 + 2.4 | Owner | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `PCNT` | CNT | 2.3 + 2.4 | Play counter | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `PCST` | PCS | unofficial | Podcast flag (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `POPM` | POP | 2.3 + 2.4 | Rating | ✔ | ✔ | ✔ | ✖ not yet – convention being measured (#453) | ◐ ID3v2 | ✖ not yet – `RATING`/`FMPS_RATING` being measured (#453) | readable | Rating (stars) | RATING |
| `POSS` | – | 2.3 + 2.4 | Position synchronisation | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `PRIV` | – | 2.3 + 2.4 | Private data | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | Binary field editor | – |
| `RBUF` | BUF | 2.3 + 2.4 | Buffer size | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `RVA2` | – | 2.4 only | Volume adjustment | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `RVAD` | RVA | 2.3 only | Volume adjustment | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `RVRB` | REV | 2.3 + 2.4 | Hall | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `SEEK` | – | 2.4 only | Seek frame | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `SIGN` | – | 2.4 only | Signature | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `SYLT` | SLT | 2.3 + 2.4 | Synchronized lyrics | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ not yet | readable | – | – |
| `SYTC` | STC | 2.3 + 2.4 | Tempo code | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `TALB` | TAL | 2.3 + 2.4 | Album | ✔ · ID3v1 | ✔ · INFO `IPRD` | ✔ | ✔ `©alb` | ◐ ID3v2 | ✔ `ALBUM` | Text | Text | ALBUM |
| `TBPM` | TBP | 2.3 + 2.4 | Beats per minute | ✔ | ✔ | ✔ | ◐ `tmpo` (whole number only) | ◐ ID3v2 | ✔ `BPM` | Text | Text | BPM |
| `TCAT` | TCT | unofficial | Podcast category (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TCMP` | TCP | unofficial | Compilation (iTunes) | ✔ | ✔ | ✔ | ✔ `cpil` | ◐ ID3v2 | ✔ `COMPILATION` | Text | Text | COMPILATION |
| `TCOM` | TCM | 2.3 + 2.4 | Composer | ✔ | ✔ | ✔ | ✔ `©wrt` | ◐ ID3v2 | ✔ `COMPOSER` | Text | Text | COMPOSER |
| `TCON` | TCO | 2.3 + 2.4 | Genre | ✔ · ID3v1 | ✔ · INFO `IGNR` | ✔ | ✔ `©gen` | ◐ ID3v2 | ✔ `GENRE` | Text | Text | GENRE |
| `TCOP` | TCR | 2.3 + 2.4 | Copyright | ✔ | ✔ · INFO `ICOP` | ✔ · `(c)` | ✔ `cprt` | ◐ ID3v2 | ✔ `COPYRIGHT` | Text | Text | COPYRIGHT |
| `TDAT` | TDA | 2.3 only | Date (DDMM) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TDEN` | – | 2.4 only | Encoding date | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TDES` | TDS | unofficial | Podcast description (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TDLY` | TDY | 2.3 + 2.4 | Delay | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TDOR` | – | 2.4 only | Original release date | ✔ | ✔ | ✔ | ◐ `----:ORIGINALDATE` | ◐ ID3v2 | ✔ `ORIGINALDATE` | Text | Text | ORIGYEAR |
| `TDRC` | – | 2.4 only | Recording date | ✔ · ID3v1 | ✔ · INFO `ICRD` | ✔ | ✔ `©day` | ◐ ID3v2 | ✔ `DATE` | Text | Text | YEAR |
| `TDRL` | – | 2.4 only | Release date | ✔ | ✔ | ✔ | ◐ `----:RELEASEDATE` | ◐ ID3v2 | ✔ `RELEASEDATE` | Text | Text | RELEASETIME |
| `TDTG` | – | 2.4 only | Tagging date | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | TAGGINGTIME |
| `TENC` | TEN | 2.3 + 2.4 | Encoded by | ✔ | ✔ | ✔ | ✔ `©enc` | ◐ ID3v2 | ✔ `ENCODEDBY` | Text | Text | ENCODEDBY |
| `TEXT` | TXT | 2.3 + 2.4 | Lyricist | ✔ | ✔ | ✔ | ◐ `----:LYRICIST` | ◐ ID3v2 | ✔ `LYRICIST` | Text | Text | LYRICIST |
| `TFLT` | TFT | 2.3 + 2.4 | File type | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | FILETYPE |
| `TGID` | TID | unofficial | Podcast ID (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TIME` | TIM | 2.3 only | Time (HHMM) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TIPL` | – | 2.4 only | Involved people | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | INVOLVEDPEOPLE |
| `TIT1` | TT1 | 2.3 + 2.4 | Content group | ✔ | ✔ | ✔ | ✔ `©wrk` | ◐ ID3v2 | ✔ `WORK` | Text | Text | CONTENTGROUP |
| `TIT2` | TT2 | 2.3 + 2.4 | Title | ✔ · ID3v1 | ✔ · INFO `INAM` | ✔ · `NAME` | ✔ `©nam` | ◐ ID3v2 | ✔ `TITLE` | Text | Text | TITLE |
| `TIT3` | TT3 | 2.3 + 2.4 | Subtitle | ✔ | ✔ | ✔ | ◐ `----:SUBTITLE` | ◐ ID3v2 | ✔ `SUBTITLE` | Text | Text | SUBTITLE |
| `TKEY` | TKE | 2.3 + 2.4 | Key | ✔ | ✔ | ✔ | ◐ `----:initialkey` | ◐ ID3v2 | ◐ `INITIALKEY` (some: `KEY`) | Text | Text | INITIALKEY |
| `TKWD` | TKW | unofficial | Podcast keywords (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TLAN` | TLA | 2.3 + 2.4 | Language | ✔ | ✔ | ✔ | ◐ `----:LANGUAGE` | ◐ ID3v2 | ✔ `LANGUAGE` | Text | Text | LANGUAGE |
| `TLEN` | TLE | 2.3 + 2.4 | Length (ms) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | LENGTH |
| `TMCL` | – | 2.4 only | Musicians | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | MUSICIANCREDITS |
| `TMED` | TMT | 2.3 + 2.4 | Media type | ✔ | ✔ | ✔ | ◐ `----:MEDIA` | ◐ ID3v2 | ✔ `MEDIA` | Text | Text | MEDIATYPE |
| `TMOO` | – | 2.4 only | Mood | ✔ | ✔ | ✔ | ◐ `----:MOOD` | ◐ ID3v2 | ✔ `MOOD` | Text | Text | MOOD |
| `TOAL` | TOT | 2.3 + 2.4 | Original album | ✔ | ✔ | ✔ | ◐ free field via TXXX | ◐ ID3v2 | ✔ `ORIGINALALBUM` | Text | Text | ORIGALBUM |
| `TOFN` | TOF | 2.3 + 2.4 | Original file name | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | ORIGFILENAME |
| `TOLY` | TOL | 2.3 + 2.4 | Original lyricist | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | ORIGLYRICIST |
| `TOPE` | TOA | 2.3 + 2.4 | Original artist | ✔ | ✔ | ✔ | ◐ free field via TXXX | ◐ ID3v2 | ✔ `ORIGINALARTIST` | Text | Text | ORIGARTIST |
| `TORY` | TOR | 2.3 only | Original year | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TOWN` | – | 2.3 + 2.4 | Owner | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | FILEOWNER |
| `TPE1` | TP1 | 2.3 + 2.4 | Artist | ✔ · ID3v1 | ✔ · INFO `IART` | ✔ · `AUTH` | ✔ `©ART` | ◐ ID3v2 | ✔ `ARTIST` | Text | Text | ARTIST |
| `TPE2` | TP2 | 2.3 + 2.4 | Album artist | ✔ | ✔ | ✔ | ✔ `aART` | ◐ ID3v2 | ✔ `ALBUMARTIST` | Text | Text | ALBUMARTIST |
| `TPE3` | TP3 | 2.3 + 2.4 | Conductor | ✔ | ✔ | ✔ | ◐ `----:CONDUCTOR` | ◐ ID3v2 | ✔ `CONDUCTOR` | Text | Text | CONDUCTOR |
| `TPE4` | TP4 | 2.3 + 2.4 | Remix / modification | ✔ | ✔ | ✔ | ◐ `----:REMIXER` | ◐ ID3v2 | ✔ `REMIXER` | Text | Text | MIXARTIST |
| `TPOS` | TPA | 2.3 + 2.4 | Disc number | ✔ | ✔ | ✔ | ✔ `disk` | ◐ ID3v2 | ✔ `DISCNUMBER` (+ `DISCTOTAL`) | Text | Text | DISCNUMBER |
| `TPRO` | – | 2.4 only | Production notice | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | PRODUCEDNOTICE |
| `TPUB` | TPB | 2.3 + 2.4 | Publisher / label | ✔ | ✔ | ✔ | ◐ `----:LABEL` | ◐ ID3v2 | ◐ `LABEL` (also `ORGANIZATION`, `PUBLISHER`) | Text | Text | PUBLISHER |
| `TRCK` | TRK | 2.3 + 2.4 | Track number | ✔ · ID3v1 | ✔ · INFO `ITRK`, `IPRT` | ✔ | ✔ `trkn` (no. + total) | ◐ ID3v2 | ✔ `TRACKNUMBER` (+ `TRACKTOTAL`) | Text | Text | TRACK |
| `TRDA` | TRD | 2.3 only | Recording dates | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TRSN` | – | 2.3 + 2.4 | Internet radio name | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TRSO` | – | 2.3 + 2.4 | Internet radio owner | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TSIZ` | TSI | 2.3 only | Size (bytes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `TSO2` | TS2 | unofficial | Album artist sort order (iTunes) | ✔ | ✔ | ✔ | ✔ `soaa` | ◐ ID3v2 | ✔ `ALBUMARTISTSORT` | Text | Text | ALBUMARTISTSORT |
| `TSOA` | TSA | 2.4 only | Album sort order | ✔ | ✔ | ✔ | ✔ `soal` | ◐ ID3v2 | ✔ `ALBUMSORT` | Text | Text | ALBUMSORT |
| `TSOC` | TSC | unofficial | Composer sort order (iTunes) | ✔ | ✔ | ✔ | ✔ `soco` | ◐ ID3v2 | ✔ `COMPOSERSORT` | Text | Text | COMPOSERSORT |
| `TSOP` | TSP | 2.4 only | Artist sort order | ✔ | ✔ | ✔ | ✔ `soar` | ◐ ID3v2 | ✔ `ARTISTSORT` | Text | Text | ARTISTSORT |
| `TSOT` | TST | 2.4 only | Title sort order | ✔ | ✔ | ✔ | ✔ `sonm` | ◐ ID3v2 | ✔ `TITLESORT` | Text | Text | TITLESORT |
| `TSRC` | TRC | 2.3 + 2.4 | ISRC | ✔ | ✔ | ✔ | ◐ `----:ISRC` | ◐ ID3v2 | ✔ `ISRC` | Text | Text | ISRC |
| `TSSE` | TSS | 2.3 + 2.4 | Encoding settings | ✔ | ✔ · INFO `ISFT` | ✔ | ✔ `©too` | ◐ ID3v2 | ◐ `ENCODING` (Mp3tag: `ENCODERSETTINGS`) | Text | Text | ENCODERSETTINGS |
| `TSST` | – | 2.4 only | Disc subtitle | ✔ | ✔ | ✔ | ◐ `----:DISCSUBTITLE` | ◐ ID3v2 | ✔ `DISCSUBTITLE` | Text | Text | SETSUBTITLE |
| `TXXX` | TXX | 2.3 + 2.4 | User text | ✔ | ✔ | ✔ | ✔ `----:com.apple.iTunes:<NAME>` | ◐ ID3v2 | ✔ `<NAME>` | Text | Text | – |
| `TYER` | TYE | 2.3 only | Year | ✔ · ID3v1 | ✔ · INFO `ICRD` | ✔ | ✔ `©day` | ◐ ID3v2 | ✔ `DATE` | Text | Text | – |
| `UFID` | UFI | 2.3 + 2.4 | Unique file ID | ✔ | ✔ | ✔ | ✖ not yet | ◐ ID3v2 | ✖ not yet | readable | – | UNIQUEFILEID |
| `USER` | – | 2.3 + 2.4 | Terms of use | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | readable | – | – |
| `USLT` | ULT | 2.3 + 2.4 | Lyrics | ✔ | ✔ | ✔ | ✔ `©lyr` | ◐ ID3v2 | ✔ `LYRICS` | Text | Text | UNSYNCEDLYRICS |
| `WCOM` | WCM | 2.3 + 2.4 | Purchase website | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWCOMMERCIALINFO |
| `WCOP` | WCP | 2.3 + 2.4 | Copyright website | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWCOPYRIGHT |
| `WFED` | WFD | unofficial | Podcast feed (iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `WOAF` | WAF | 2.3 + 2.4 | Audio file web page | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWAUDIOFILE |
| `WOAR` | WAR | 2.3 + 2.4 | Artist web page | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWARTIST |
| `WOAS` | WAS | 2.3 + 2.4 | Audio source web page | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWAUDIOSOURCE |
| `WORS` | – | 2.3 + 2.4 | Internet radio web page | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `WPAY` | – | 2.3 + 2.4 | Payment web page | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWPAYMENT |
| `WPUB` | WPB | 2.3 + 2.4 | Publisher web page | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | WWWPUBLISHER |
| `WXXX` | WXX | 2.3 + 2.4 | User link | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `XSOA` | – | unofficial | Album sort order (v2.3, iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `XSOP` | – | unofficial | Artist sort order (v2.3, iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |
| `XSOT` | – | unofficial | Title sort order (v2.3, iTunes) | ✔ | ✔ | ✔ | ✖ | ◐ ID3v2 | ✖ | Text | Text | – |

**Differences FLAC ↔ OGG** (marked with * in the table):

- `APIC`: OGG: cover as Base64 field `METADATA_BLOCK_PICTURE`
- `GEOB`: OGG: whether Serato stores data here is still to be measured

**Only in ID3v2.2 (dropped):** `CRM` Encrypted meta data (ID3v2.2 only)
