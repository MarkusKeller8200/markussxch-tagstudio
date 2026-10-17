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

**Columns:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 or unofficial · Display = text, image, readable summary or
size + checksum · Edit = what TagStudio can change the field with · Mp3tag = field name in Mp3tag.

| Frame | v2.2 | Version | Name | Display | Edit | Mp3tag |
|---|---|---|---|---|---|---|
| `AENC` | CRA | 2.3 + 2.4 | Audio encryption | readable | – | – |
| `APIC` | PIC | 2.3 + 2.4 | Image / cover | Image | Cover tools | PICTURE |
| `ASPI` | – | 2.4 only | Audio seek index | readable | – | – |
| `CHAP` | – | 2.3 + 2.4 | Chapter | readable | – | – |
| `COMM` | COM | 2.3 + 2.4 | Comment | Text | Text | COMMENT |
| `COMR` | – | 2.3 + 2.4 | Commercial | readable | – | – |
| `CTOC` | – | 2.3 + 2.4 | Table of contents (chapters) | readable | – | – |
| `ENCR` | – | 2.3 + 2.4 | Encryption method | readable | – | – |
| `EQU2` | – | 2.4 only | Equalizer | readable | – | – |
| `EQUA` | EQU | 2.3 only | Equalizer | readable | – | – |
| `ETCO` | ETC | 2.3 + 2.4 | Event timing | readable | – | – |
| `GEOB` | GEO | 2.3 + 2.4 | Embedded data | readable | Binary field editor | – |
| `GRID` | – | 2.3 + 2.4 | Group ID | readable | – | – |
| `GRP1` | GP1 | unofficial | Grouping (iTunes) | Text | Text | GROUPING |
| `IPLS` | IPL | 2.3 only | Involved people | Text | Text | – |
| `LINK` | LNK | 2.3 + 2.4 | Shortcut | readable | – | – |
| `MCDI` | MCI | 2.3 + 2.4 | CD table of contents | readable | – | – |
| `MLLT` | MLL | 2.3 + 2.4 | MPEG-Lookup-Tabelle | readable | – | – |
| `MVIN` | MVI | unofficial | Movement number (iTunes) | Text | Text | MOVEMENT |
| `MVNM` | MVN | unofficial | Movement name (iTunes) | Text | Text | MOVEMENTNAME |
| `OWNE` | – | 2.3 + 2.4 | Owner | readable | – | – |
| `PCNT` | CNT | 2.3 + 2.4 | Play counter | readable | – | – |
| `PCST` | PCS | unofficial | Podcast flag (iTunes) | readable | – | – |
| `POPM` | POP | 2.3 + 2.4 | Rating | readable | Rating (stars) | RATING |
| `POSS` | – | 2.3 + 2.4 | Position synchronisation | readable | – | – |
| `PRIV` | – | 2.3 + 2.4 | Private data | readable | Binary field editor | – |
| `RBUF` | BUF | 2.3 + 2.4 | Buffer size | readable | – | – |
| `RVA2` | – | 2.4 only | Volume adjustment | readable | – | – |
| `RVAD` | RVA | 2.3 only | Volume adjustment | readable | – | – |
| `RVRB` | REV | 2.3 + 2.4 | Hall | readable | – | – |
| `SEEK` | – | 2.4 only | Seek frame | readable | – | – |
| `SIGN` | – | 2.4 only | Signature | readable | – | – |
| `SYLT` | SLT | 2.3 + 2.4 | Synchronized lyrics | readable | – | – |
| `SYTC` | STC | 2.3 + 2.4 | Tempo code | readable | – | – |
| `TALB` | TAL | 2.3 + 2.4 | Album | Text | Text | ALBUM |
| `TBPM` | TBP | 2.3 + 2.4 | Beats per minute | Text | Text | BPM |
| `TCAT` | TCT | unofficial | Podcast category (iTunes) | Text | Text | – |
| `TCMP` | TCP | unofficial | Compilation (iTunes) | Text | Text | COMPILATION |
| `TCOM` | TCM | 2.3 + 2.4 | Composer | Text | Text | COMPOSER |
| `TCON` | TCO | 2.3 + 2.4 | Genre | Text | Text | GENRE |
| `TCOP` | TCR | 2.3 + 2.4 | Copyright | Text | Text | COPYRIGHT |
| `TDAT` | TDA | 2.3 only | Date (DDMM) | Text | Text | – |
| `TDEN` | – | 2.4 only | Encoding date | Text | Text | – |
| `TDES` | TDS | unofficial | Podcast description (iTunes) | Text | Text | – |
| `TDLY` | TDY | 2.3 + 2.4 | Delay | Text | Text | – |
| `TDOR` | – | 2.4 only | Original release date | Text | Text | ORIGYEAR |
| `TDRC` | – | 2.4 only | Recording date | Text | Text | YEAR |
| `TDRL` | – | 2.4 only | Release date | Text | Text | RELEASETIME |
| `TDTG` | – | 2.4 only | Tagging date | Text | Text | TAGGINGTIME |
| `TENC` | TEN | 2.3 + 2.4 | Encoded by | Text | Text | ENCODEDBY |
| `TEXT` | TXT | 2.3 + 2.4 | Lyricist | Text | Text | LYRICIST |
| `TFLT` | TFT | 2.3 + 2.4 | File type | Text | Text | FILETYPE |
| `TGID` | TID | unofficial | Podcast ID (iTunes) | Text | Text | – |
| `TIME` | TIM | 2.3 only | Time (HHMM) | Text | Text | – |
| `TIPL` | – | 2.4 only | Involved people | Text | Text | INVOLVEDPEOPLE |
| `TIT1` | TT1 | 2.3 + 2.4 | Content group | Text | Text | CONTENTGROUP |
| `TIT2` | TT2 | 2.3 + 2.4 | Title | Text | Text | TITLE |
| `TIT3` | TT3 | 2.3 + 2.4 | Subtitle | Text | Text | SUBTITLE |
| `TKEY` | TKE | 2.3 + 2.4 | Key | Text | Text | INITIALKEY |
| `TKWD` | TKW | unofficial | Podcast keywords (iTunes) | Text | Text | – |
| `TLAN` | TLA | 2.3 + 2.4 | Language | Text | Text | LANGUAGE |
| `TLEN` | TLE | 2.3 + 2.4 | Length (ms) | Text | Text | LENGTH |
| `TMCL` | – | 2.4 only | Musicians | Text | Text | MUSICIANCREDITS |
| `TMED` | TMT | 2.3 + 2.4 | Media type | Text | Text | MEDIATYPE |
| `TMOO` | – | 2.4 only | Mood | Text | Text | MOOD |
| `TOAL` | TOT | 2.3 + 2.4 | Original album | Text | Text | ORIGALBUM |
| `TOFN` | TOF | 2.3 + 2.4 | Original file name | Text | Text | ORIGFILENAME |
| `TOLY` | TOL | 2.3 + 2.4 | Original lyricist | Text | Text | ORIGLYRICIST |
| `TOPE` | TOA | 2.3 + 2.4 | Original artist | Text | Text | ORIGARTIST |
| `TORY` | TOR | 2.3 only | Original year | Text | Text | – |
| `TOWN` | – | 2.3 + 2.4 | Owner | Text | Text | FILEOWNER |
| `TPE1` | TP1 | 2.3 + 2.4 | Artist | Text | Text | ARTIST |
| `TPE2` | TP2 | 2.3 + 2.4 | Album artist | Text | Text | ALBUMARTIST |
| `TPE3` | TP3 | 2.3 + 2.4 | Conductor | Text | Text | CONDUCTOR |
| `TPE4` | TP4 | 2.3 + 2.4 | Remix / modification | Text | Text | MIXARTIST |
| `TPOS` | TPA | 2.3 + 2.4 | Disc number | Text | Text | DISCNUMBER |
| `TPRO` | – | 2.4 only | Production notice | Text | Text | PRODUCEDNOTICE |
| `TPUB` | TPB | 2.3 + 2.4 | Publisher / label | Text | Text | PUBLISHER |
| `TRCK` | TRK | 2.3 + 2.4 | Track number | Text | Text | TRACK |
| `TRDA` | TRD | 2.3 only | Recording dates | Text | Text | – |
| `TRSN` | – | 2.3 + 2.4 | Internet radio name | Text | Text | – |
| `TRSO` | – | 2.3 + 2.4 | Internet radio owner | Text | Text | – |
| `TSIZ` | TSI | 2.3 only | Size (bytes) | Text | Text | – |
| `TSO2` | TS2 | unofficial | Album artist sort order (iTunes) | Text | Text | ALBUMARTISTSORT |
| `TSOA` | TSA | 2.4 only | Album sort order | Text | Text | ALBUMSORT |
| `TSOC` | TSC | unofficial | Composer sort order (iTunes) | Text | Text | COMPOSERSORT |
| `TSOP` | TSP | 2.4 only | Artist sort order | Text | Text | ARTISTSORT |
| `TSOT` | TST | 2.4 only | Title sort order | Text | Text | TITLESORT |
| `TSRC` | TRC | 2.3 + 2.4 | ISRC | Text | Text | ISRC |
| `TSSE` | TSS | 2.3 + 2.4 | Encoding settings | Text | Text | ENCODERSETTINGS |
| `TSST` | – | 2.4 only | Disc subtitle | Text | Text | SETSUBTITLE |
| `TXXX` | TXX | 2.3 + 2.4 | User text | Text | Text | – |
| `TYER` | TYE | 2.3 only | Year | Text | Text | – |
| `UFID` | UFI | 2.3 + 2.4 | Unique file ID | readable | – | UNIQUEFILEID |
| `USER` | – | 2.3 + 2.4 | Terms of use | readable | – | – |
| `USLT` | ULT | 2.3 + 2.4 | Lyrics | Text | Text | UNSYNCEDLYRICS |
| `WCOM` | WCM | 2.3 + 2.4 | Purchase website | Text | Text | WWWCOMMERCIALINFO |
| `WCOP` | WCP | 2.3 + 2.4 | Copyright website | Text | Text | WWWCOPYRIGHT |
| `WFED` | WFD | unofficial | Podcast feed (iTunes) | Text | Text | – |
| `WOAF` | WAF | 2.3 + 2.4 | Audio file web page | Text | Text | WWWAUDIOFILE |
| `WOAR` | WAR | 2.3 + 2.4 | Artist web page | Text | Text | WWWARTIST |
| `WOAS` | WAS | 2.3 + 2.4 | Audio source web page | Text | Text | WWWAUDIOSOURCE |
| `WORS` | – | 2.3 + 2.4 | Internet radio web page | Text | Text | – |
| `WPAY` | – | 2.3 + 2.4 | Payment web page | Text | Text | WWWPAYMENT |
| `WPUB` | WPB | 2.3 + 2.4 | Publisher web page | Text | Text | WWWPUBLISHER |
| `WXXX` | WXX | 2.3 + 2.4 | User link | Text | Text | – |
| `XSOA` | – | unofficial | Album sort order (v2.3, iTunes) | Text | Text | – |
| `XSOP` | – | unofficial | Artist sort order (v2.3, iTunes) | Text | Text | – |
| `XSOT` | – | unofficial | Title sort order (v2.3, iTunes) | Text | Text | – |

**Only in ID3v2.2 (dropped):** `CRM` Encrypted meta data (ID3v2.2 only)
