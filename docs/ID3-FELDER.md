# ID3-Felder in TagStudio

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

**Spalten:** v2.2 = ID in ID3v2.2 · Version = 2.3, 2.4 oder inoffiziell · Anzeige = Text, Bild, lesbare Kurzfassung
oder Grösse + Prüfsumme · Bearbeiten = womit TagStudio das Feld ändern kann · Mp3tag = Feldname in Mp3tag.

| Frame | v2.2 | Version | Bezeichnung | Anzeige | Bearbeiten | Mp3tag |
|---|---|---|---|---|---|---|
| `AENC` | CRA | 2.3 + 2.4 | Audio-Verschlüsselung | lesbar | – | – |
| `APIC` | PIC | 2.3 + 2.4 | Bild / Cover | Bild | Cover-Werkzeuge | PICTURE |
| `ASPI` | – | nur 2.4 | Audio-Suchindex | lesbar | – | – |
| `CHAP` | – | 2.3 + 2.4 | Kapitel | lesbar | – | – |
| `COMM` | COM | 2.3 + 2.4 | Kommentar | Text | Text | COMMENT |
| `COMR` | – | 2.3 + 2.4 | Kommerziell | lesbar | – | – |
| `CTOC` | – | 2.3 + 2.4 | Inhaltsverzeichnis (Kapitel) | lesbar | – | – |
| `ENCR` | – | 2.3 + 2.4 | Verschlüsselungsmethode | lesbar | – | – |
| `EQU2` | – | nur 2.4 | Equalizer | lesbar | – | – |
| `EQUA` | EQU | nur 2.3 | Equalizer | lesbar | – | – |
| `ETCO` | ETC | 2.3 + 2.4 | Ereignis-Zeitpunkte | lesbar | – | – |
| `GEOB` | GEO | 2.3 + 2.4 | Eingebettete Daten | lesbar | Binärfeld-Editor | – |
| `GRID` | – | 2.3 + 2.4 | Gruppen-ID | lesbar | – | – |
| `GRP1` | GP1 | inoffiziell | Gruppierung (iTunes) | Text | Text | GROUPING |
| `IPLS` | IPL | nur 2.3 | Beteiligte Personen | Text | Text | – |
| `LINK` | LNK | 2.3 + 2.4 | Verknüpfung | lesbar | – | – |
| `MCDI` | MCI | 2.3 + 2.4 | CD-Inhaltsverzeichnis | lesbar | – | – |
| `MLLT` | MLL | 2.3 + 2.4 | MPEG-Lookup-Tabelle | lesbar | – | – |
| `MVIN` | MVI | inoffiziell | Satznummer (iTunes) | Text | Text | MOVEMENT |
| `MVNM` | MVN | inoffiziell | Satzname (iTunes) | Text | Text | MOVEMENTNAME |
| `OWNE` | – | 2.3 + 2.4 | Besitzer | lesbar | – | – |
| `PCNT` | CNT | 2.3 + 2.4 | Wiedergabezähler | lesbar | – | – |
| `PCST` | PCS | inoffiziell | Podcast-Kennzeichen (iTunes) | lesbar | – | – |
| `POPM` | POP | 2.3 + 2.4 | Bewertung | lesbar | Bewertung (Sterne) | RATING |
| `POSS` | – | 2.3 + 2.4 | Positions-Synchronisation | lesbar | – | – |
| `PRIV` | – | 2.3 + 2.4 | Private Daten | lesbar | Binärfeld-Editor | – |
| `RBUF` | BUF | 2.3 + 2.4 | Puffergrösse | lesbar | – | – |
| `RVA2` | – | nur 2.4 | Lautstärke-Anpassung | lesbar | – | – |
| `RVAD` | RVA | nur 2.3 | Lautstärke-Anpassung | lesbar | – | – |
| `RVRB` | REV | 2.3 + 2.4 | Hall | lesbar | – | – |
| `SEEK` | – | nur 2.4 | Suchmarke | lesbar | – | – |
| `SIGN` | – | nur 2.4 | Signatur | lesbar | – | – |
| `SYLT` | SLT | 2.3 + 2.4 | Synchronisierter Liedtext | lesbar | – | – |
| `SYTC` | STC | 2.3 + 2.4 | Tempo-Code | lesbar | – | – |
| `TALB` | TAL | 2.3 + 2.4 | Album | Text | Text | ALBUM |
| `TBPM` | TBP | 2.3 + 2.4 | Beats pro Minute | Text | Text | BPM |
| `TCAT` | TCT | inoffiziell | Podcast-Kategorie (iTunes) | Text | Text | – |
| `TCMP` | TCP | inoffiziell | Zusammenstellung (iTunes) | Text | Text | COMPILATION |
| `TCOM` | TCM | 2.3 + 2.4 | Komponist | Text | Text | COMPOSER |
| `TCON` | TCO | 2.3 + 2.4 | Genre | Text | Text | GENRE |
| `TCOP` | TCR | 2.3 + 2.4 | Copyright | Text | Text | COPYRIGHT |
| `TDAT` | TDA | nur 2.3 | Datum (TTMM) | Text | Text | – |
| `TDEN` | – | nur 2.4 | Kodierungsdatum | Text | Text | – |
| `TDES` | TDS | inoffiziell | Podcast-Beschreibung (iTunes) | Text | Text | – |
| `TDLY` | TDY | 2.3 + 2.4 | Verzögerung | Text | Text | – |
| `TDOR` | – | nur 2.4 | Originalveröffentlichungsdatum | Text | Text | ORIGYEAR |
| `TDRC` | – | nur 2.4 | Aufnahmedatum | Text | Text | YEAR |
| `TDRL` | – | nur 2.4 | Veröffentlichungsdatum | Text | Text | RELEASETIME |
| `TDTG` | – | nur 2.4 | Tagging-Datum | Text | Text | TAGGINGTIME |
| `TENC` | TEN | 2.3 + 2.4 | Kodiert von | Text | Text | ENCODEDBY |
| `TEXT` | TXT | 2.3 + 2.4 | Texter | Text | Text | LYRICIST |
| `TFLT` | TFT | 2.3 + 2.4 | Dateityp | Text | Text | FILETYPE |
| `TGID` | TID | inoffiziell | Podcast-ID (iTunes) | Text | Text | – |
| `TIME` | TIM | nur 2.3 | Uhrzeit (HHMM) | Text | Text | – |
| `TIPL` | – | nur 2.4 | Beteiligte Personen | Text | Text | INVOLVEDPEOPLE |
| `TIT1` | TT1 | 2.3 + 2.4 | Inhaltliche Gruppierung | Text | Text | CONTENTGROUP |
| `TIT2` | TT2 | 2.3 + 2.4 | Titel | Text | Text | TITLE |
| `TIT3` | TT3 | 2.3 + 2.4 | Untertitel | Text | Text | SUBTITLE |
| `TKEY` | TKE | 2.3 + 2.4 | Tonart | Text | Text | INITIALKEY |
| `TKWD` | TKW | inoffiziell | Podcast-Schlüsselwörter (iTunes) | Text | Text | – |
| `TLAN` | TLA | 2.3 + 2.4 | Sprache | Text | Text | LANGUAGE |
| `TLEN` | TLE | 2.3 + 2.4 | Länge (ms) | Text | Text | LENGTH |
| `TMCL` | – | nur 2.4 | Musiker | Text | Text | MUSICIANCREDITS |
| `TMED` | TMT | 2.3 + 2.4 | Medientyp | Text | Text | MEDIATYPE |
| `TMOO` | – | nur 2.4 | Stimmung | Text | Text | MOOD |
| `TOAL` | TOT | 2.3 + 2.4 | Originalalbum | Text | Text | ORIGALBUM |
| `TOFN` | TOF | 2.3 + 2.4 | Originaldateiname | Text | Text | ORIGFILENAME |
| `TOLY` | TOL | 2.3 + 2.4 | Originaltexter | Text | Text | ORIGLYRICIST |
| `TOPE` | TOA | 2.3 + 2.4 | Originalkünstler | Text | Text | ORIGARTIST |
| `TORY` | TOR | nur 2.3 | Originaljahr | Text | Text | – |
| `TOWN` | – | 2.3 + 2.4 | Eigentümer | Text | Text | FILEOWNER |
| `TPE1` | TP1 | 2.3 + 2.4 | Künstler | Text | Text | ARTIST |
| `TPE2` | TP2 | 2.3 + 2.4 | Album-Künstler | Text | Text | ALBUMARTIST |
| `TPE3` | TP3 | 2.3 + 2.4 | Dirigent | Text | Text | CONDUCTOR |
| `TPE4` | TP4 | 2.3 + 2.4 | Remix / Bearbeitung | Text | Text | MIXARTIST |
| `TPOS` | TPA | 2.3 + 2.4 | Disknummer | Text | Text | DISCNUMBER |
| `TPRO` | – | nur 2.4 | Produktionshinweis | Text | Text | PRODUCEDNOTICE |
| `TPUB` | TPB | 2.3 + 2.4 | Herausgeber / Label | Text | Text | PUBLISHER |
| `TRCK` | TRK | 2.3 + 2.4 | Spurnummer | Text | Text | TRACK |
| `TRDA` | TRD | nur 2.3 | Aufnahmedaten | Text | Text | – |
| `TRSN` | – | 2.3 + 2.4 | Internetradio-Name | Text | Text | – |
| `TRSO` | – | 2.3 + 2.4 | Internetradio-Eigentümer | Text | Text | – |
| `TSIZ` | TSI | nur 2.3 | Grösse (Bytes) | Text | Text | – |
| `TSO2` | TS2 | inoffiziell | Album-Künstler einsortieren als (iTunes) | Text | Text | ALBUMARTISTSORT |
| `TSOA` | TSA | nur 2.4 | Album einsortieren als | Text | Text | ALBUMSORT |
| `TSOC` | TSC | inoffiziell | Komponist einsortieren als (iTunes) | Text | Text | COMPOSERSORT |
| `TSOP` | TSP | nur 2.4 | Künstler einsortieren als | Text | Text | ARTISTSORT |
| `TSOT` | TST | nur 2.4 | Titel einsortieren als | Text | Text | TITLESORT |
| `TSRC` | TRC | 2.3 + 2.4 | ISRC | Text | Text | ISRC |
| `TSSE` | TSS | 2.3 + 2.4 | Kodierung Einstellungen | Text | Text | ENCODERSETTINGS |
| `TSST` | – | nur 2.4 | Disc-Untertitel | Text | Text | SETSUBTITLE |
| `TXXX` | TXX | 2.3 + 2.4 | Benutzertext | Text | Text | – |
| `TYER` | TYE | nur 2.3 | Jahr | Text | Text | – |
| `UFID` | UFI | 2.3 + 2.4 | Eindeutige Datei-ID | lesbar | – | UNIQUEFILEID |
| `USER` | – | 2.3 + 2.4 | Nutzungsbedingungen | lesbar | – | – |
| `USLT` | ULT | 2.3 + 2.4 | Liedtext | Text | Text | UNSYNCEDLYRICS |
| `WCOM` | WCM | 2.3 + 2.4 | Kauf-Internetseite | Text | Text | WWWCOMMERCIALINFO |
| `WCOP` | WCP | 2.3 + 2.4 | Copyright-Internetseite | Text | Text | WWWCOPYRIGHT |
| `WFED` | WFD | inoffiziell | Podcast-Feed (iTunes) | Text | Text | – |
| `WOAF` | WAF | 2.3 + 2.4 | Audiodatei Internetseite | Text | Text | WWWAUDIOFILE |
| `WOAR` | WAR | 2.3 + 2.4 | Künstler Internetseite | Text | Text | WWWARTIST |
| `WOAS` | WAS | 2.3 + 2.4 | Audioquelle Internetseite | Text | Text | WWWAUDIOSOURCE |
| `WORS` | – | 2.3 + 2.4 | Internetradio Internetseite | Text | Text | – |
| `WPAY` | – | 2.3 + 2.4 | Bezahlung Internetseite | Text | Text | WWWPAYMENT |
| `WPUB` | WPB | 2.3 + 2.4 | Herausgeber Internetseite | Text | Text | WWWPUBLISHER |
| `WXXX` | WXX | 2.3 + 2.4 | Benutzer-Link | Text | Text | – |
| `XSOA` | – | inoffiziell | Album einsortieren als (v2.3, iTunes) | Text | Text | – |
| `XSOP` | – | inoffiziell | Künstler einsortieren als (v2.3, iTunes) | Text | Text | – |
| `XSOT` | – | inoffiziell | Titel einsortieren als (v2.3, iTunes) | Text | Text | – |

**Nur in ID3v2.2 (entfällt):** `CRM` Verschlüsselte Meta-Daten (nur ID3v2.2)
