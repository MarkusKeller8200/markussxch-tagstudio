# TagStudio – Produkt- und Architekturkonzept

**Arbeitsentwurf v0.1 · Stand: 14. Oktober 2026 · Grundlage für die weitere Entwicklung mit Claude und ChatGPT**  
**Status:** Konzept und Entscheidungsgrundlage – keine freigegebene Implementierungsspezifikation

> **Leitidee:** TagStudio ist eine intelligente, offene Schaltzentrale für DJ-Musikbibliotheken: Musik verwalten, Metadaten kontrollieren, Tracks analysieren, passende Titel und Übergänge finden, DJ-Sets planen und die Ergebnisse möglichst reibungsarm an bestehende DJ-Programme übergeben. TagStudio ist ausdrücklich **keine neue Live-DJ-Mixing-Software und keine vollwertige DAW**.

## Dokumentsteuerung

| Feld | Wert |
|---|---|
| Dokumenttyp | Produkt- und Architekturkonzept / Living Document |
| Ausgangsbasis | Öffentlicher TagStudio-Code, Version 4.4.0, plus Architekturgespräche |
| Zielplattformen | Windows und macOS |
| Verbindlichkeitsstufen | **BESCHLOSSEN** (Nutzervorgabe), **EMPFOHLEN** (Architekturvorschlag), **OFFEN** (noch zu entscheiden), **ZU PRÜFEN** (technische Machbarkeit) |
| Projektbezug | [TagStudio-Repository](https://github.com/MarkusKeller8200/markussxch-tagstudio) |
| Fortschreibung | Versionskontrollierte Markdown-Quelle; daraus ableitbare DOCX-Fassung, ADRs, GitHub-Issues und Testpläne |

## 1. Executive Summary

TagStudio soll seinen bisherigen Kern – Tagging, Vergleichen, Bibliotheksverwaltung, DJ-Set-Planung und sichere Änderungen – systematisch ausbauen. Der wesentliche neue Nutzen entsteht aus einer hochwertigen Audioanalyse, einem intelligenten Track- und Übergangs-Matching, einem dafür optimierten Vorschau-Player sowie aus der Interoperabilität mit bestehender Musiksoftware.

Der Player dient dem **Vorhören und Entscheiden**: Tempo und Tonart verändern, vorberechnete Stems kombinieren, Cues und Beatgrids nutzen, zwei Tracks an ausgewählten Stellen überlagern und die Eignung eines Übergangs bewerten. Keine Jogwheel-/Scratch-/Performance-Umgebung und keine Live-Set-Steuerung.

Die Kernanwendung bleibt zunächst **Python mit HTML/CSS/JavaScript in pywebview**. Für zeitkritische DSP- und VST3-Aufgaben wird eine **optionale native C++-Audio-Komponente** empfohlen; **JUCE** ist hierfür ein aussichtsreicher, aber noch zu validierender Kandidat. Eine komplette GUI-Neuentwicklung ist **nicht** vorgesehen. TypeScript und komponentenorientierte UI-Modernisierung können schrittweise folgen.

Stem-Separation erfolgt **offline und qualitätsorientiert**. Während der Wiedergabe werden ausschliesslich vorberechnete Spuren gemischt. Erweiterte VST3-Plugins (z. B. Wingman, Avenger, NEXUS) sollen in einem späteren **Audio Lab** möglich sein; ihre echte Host-Kompatibilität und die Lizenzbedingungen sind nachzuweisen.

Der Integrationsstrategie kommt hohe Bedeutung zu: **DJ.Studio** für die Offline-Mix-/Timeline-Arbeit, **Lexicon** und **Mixo** für Bibliothekskonvertierung, danach gemäss gewünschter Betrachtungsreihenfolge **Engine DJ, Serato, VirtualDJ, Traktor und rekordbox** für die DJ-Praxis. TagStudio soll diese Werkzeuge **ergänzen, nicht kopieren**.

## 2. Produktvision, Ziele und Abgrenzung

### 2.1 Ziele – BESCHLOSSEN

- Eine zentrale und möglichst vollständige Sicht auf Track-Metadaten, Tags, Herkunft, Änderungen, Cues, Beatgrids und musikalische Merkmale.
- Sicheres Bearbeiten, Vergleichen, Übernehmen und Zurücksetzen von Tags – bestehende Fremddaten werden nicht unbemerkt überschrieben.
- Musikalische Analyse mit reproduzierbaren Resultaten für BPM, Tonart/Camelot, Energie, Danceability, Stimmung, Songstruktur und Übergangspotenzial.
- Passende Tracks für ein geplantes DJ-Set vorschlagen; Bewertungen und subjektive Entscheidungen der Nutzerin oder des Nutzers bleiben massgeblich.
- Gezielt vorhören: Tempoanpassung, Key-Lock, Pitch, Stems, Cue-/Loop-Bereiche, A/B und Übergangssimulation.
- DJ-Set-Entwürfe inklusive Reihenfolge, Übergangsnotizen, markierten Stellen, Varianten und Exportpaketen verwalten.
- Daten und Sets möglichst verlustarm in vorhandene DJ-Anwendungen übergeben.

### 2.2 Nicht-Ziele – BESCHLOSSEN

- Kein Ersatz für Engine DJ, Serato, VirtualDJ, Traktor oder rekordbox im Live-Einsatz.
- Kein vollständiger Ersatz für DJ.Studio beim Offline-Mixing und kein DAW-Ersatz.
- Keine Live-Stem-Separation; keine Priorisierung minimaler Separationszeit zulasten der Qualität.
- Keine universelle Schreibberechtigung auf interne Drittanbieter-Datenbanken oder undokumentierte proprietäre Dateien.
- Keine automatische Veröffentlichung, Verbreitung oder Aufnahme lizenzrechtlich geschützter Streams.

### 2.3 Positionierung im Ökosystem

**TagStudio:** Datenqualität, Transparenz, Analyse, Entscheidung und Vorbereitung. **DJ.Studio:** detailreiche Offline-Mix- und Timeline-Arrangements. **Lexicon/Mixo:** Bibliothekskonvertierung und Synchronisation. **DJ-Programme:** Auftritt, Hardwareintegration und Live-Performance. Überschneidungen sind akzeptabel; der Schwerpunkt bleibt auf nahtlosen Übergaben.

## 3. Ausgangslage: bestehende TagStudio-Architektur

Der überprüfte öffentliche Stand der Anwendung weist Python 3.12+, eine aktuelle Web-GUI in `web/` und den Desktop-Container `pywebview` aus. `tagstudio_web.py` stellt die Session-API für das Frontend bereit; im Browsermodus steht ein lokaler HTTP-Endpunkt zur Verfügung. Die alte Tkinter-Oberfläche in `tagstudio.py` ist eingefroren. Die Installer werden unter anderem über PyInstaller für Windows und macOS erstellt. Der Quellcode ist unter GPL-3.0-or-later veröffentlicht. Quelle: [Repository](https://github.com/MarkusKeller8200/markussxch-tagstudio), [pyproject.toml](https://github.com/MarkusKeller8200/markussxch-tagstudio/blob/main/pyproject.toml), [tagstudio_web.py](https://github.com/MarkusKeller8200/markussxch-tagstudio/blob/main/tagstudio_web.py), [packaging/build.py](https://github.com/MarkusKeller8200/markussxch-tagstudio/blob/main/packaging/build.py).

Die Web-Oberfläche verwendet überwiegend **Vanilla JavaScript** ohne durchgehendes Komponentenframework. Der vorhandene Tagger und die Vergleichsliste sind bereits **virtualisiert**: Es werden nur sichtbare Zeilen und ein Puffer erzeugt. Das ist eine wichtige, ausdrücklich beizubehaltende Performance-Eigenschaft. Die Vorschau arbeitet bisher wesentlich mit HTML-Audioelementen und browserseitigen Timern/`playbackRate`. Sie ist funktional, eignet sich aber nicht ohne Weiteres als Grundlage für einen umfassenden VST3-Host.

**Konsequenz:** kein Big-Bang-Rewrite. Vorhandene Features, Sessions, Profile, Backups, Undo und Dateiformate müssen bei der Erweiterung stabil bleiben. Der neue Audio-Core wird durch definierte Schnittstellen angeschlossen und kann zunächst optional sein.

## 4. Priorisierte Nutzer-Workflows

### 4.1 Bibliothek vorbereiten

1. Dateien und bestehende DJ-Bibliotheken schreibgeschützt einlesen, Identitäten und Speicherorte abgleichen.
2. Tags, Schreibweisen, Mehrfachwerte und Quellen prüfen; Konflikte sichtbar machen.
3. Bei Bedarf Herkunft/Version pro Wert erfassen, Änderungen vor dem Schreiben anzeigen und sichern.
4. Audioanalyse im Hintergrund ausführen, Resultate versioniert zwischenspeichern.
5. Werte erst nach expliziter Freigabe in dafür geeignete Metadatenfelder übernehmen.

### 4.2 Passendes DJ-Set entwickeln

1. Ausgangstrack und gewünschte Energie-/Stimmungsdramaturgie wählen.
2. Kandidaten nach BPM, harmonischer Kompatibilität, Energie, Mood, Stil, Phrasing, Drops und Songstruktur vorschlagen.
3. Filter, Gewichtungen und Ausschlüsse anpassen; vorgeschlagene Übergänge begründen.
4. Kandidat und Ausgangstrack mit temporärem Tempo, Pitch und geeigneten Ausschnitten vorhören.
5. Optional vorberechnete Stems ein-/ausblenden; Cues und Übergangsvarianten bewerten.
6. Reihenfolge, Übergangsart, Cue-Marker, Notiz, Konfidenz und Nutzerbewertung im Set-Entwurf sichern.
7. Zielprogramm wählen, Exportvorschau und Kompatibilitätsbericht prüfen, anschliessend exportieren.

### 4.3 Kreative Experimente (optional)

Ein Vocal-/Instrumental-Ausschnitt kann an ein kompatibles VST3-Audio-Plugin übergeben werden. Ein Instrument kann über MIDI Noten erzeugen oder abspielen. Ideen werden als separate MIDI-/WAV-Artefakte und Presets mit dem Set verknüpft – **ohne Originaltracks zu verändern**.

## 5. Funktionsumfang und Roadmap-Prioritäten

| Bereich | Kernfunktion | Priorität | Status |
|---|---|---|---|
| Bestandsfunktionen | Tagger, Compare, Backup, Undo, Set-Planer erhalten | P0 | BESCHLOSSEN |
| Daten | Dateidentität, verlässliche Import-/Export-Basis, SQLite | P0 | EMPFOHLEN |
| Audioanalyse | BPM, Key, Loudness, Energieverlauf, Waveform | P0 | BESCHLOSSEN / EMPFOHLEN |
| DJ-Set | Matching, Reihenfolge, Übergangskommentare | P0 | BESCHLOSSEN |
| Interoperabilität | M3U8, CSV und geprüfte Zieladapter | P0 | BESCHLOSSEN |
| Preview | Tempo, Key-Lock, Pitch, A/B, Cues und Übergangsprobe | P1 | BESCHLOSSEN |
| Erweiterte Analyse | Drops, Phrasing, Struktur, Stimmung und Ähnlichkeit | P1 | BESCHLOSSEN, Reihenfolge offen |
| Offline-Stems | Qualitätsorientierte Trennung, Cache und Wiedergabe | P1 | BESCHLOSSEN |
| VST3-Audioeffekte | Optionaler nativer Plugin-Host | P2 | EMPFOHLEN |
| VST3-Instrumente | MIDI-Clip-Player, Avenger/NEXUS u. a. | P2 | BESCHLOSSENER WUNSCH, zu prüfen |
| Audio Lab | Wingman-Workflow, Presets, kreative Ideen | P2 | BESCHLOSSENER WUNSCH, zu prüfen |
| Weitere Formate | CLAP, erweiterte Synchronisation | P3 | EMPFOHLEN |

P0/P1/P2/P3 sind eine **Umsetzungsreihenfolge**, keine Produktversionszusagen.

## 6. Technische Zielarchitektur

```text
TagStudio GUI (HTML/CSS/JS; später optional TypeScript/Vue)
       |
       v
Application API / Session / Service-Layer  [Python]
       |                |                |
       |                |                +--> Integration Adapters
       |                |                     DJ.Studio / Lexicon / Mixo /
       |                |                     Engine / Serato / VirtualDJ /
       |                |                     Traktor / rekordbox
       |                v
       |          Analysis Workers [Python + native Libraries / ML]
       |                |
       v                v
Native Preview Host <-- SQLite / Artefakt-Cache / SetPlan Model
[C++ optional; JUCE als Kandidat]
       |
       +--> Decoder / Time-Stretch / Key-Lock / Stem-Balance
       +--> VST3 Host / MIDI (optionales Audio Lab)
       +--> Audio Device (CoreAudio / WASAPI / optional ASIO)
```

**Leitprinzipien:** Die Oberfläche enthält keine geschäftskritische Logik; Python steuert Analyse, Dateien, Tags und Set-Planung; native Komponenten erledigen nur zeitkritische Audioarbeit. Schnittstellen werden versioniert und testbar. Die Audiowiedergabe bleibt auf Wunsch mit einer einfachen Fallback-Implementierung verfügbar.

### 6.1 Prozess- und Modulgrenzen

- **GUI:** Darstellung, Benutzerinteraktionen, Filter, Waveforms und Bedienzustand.
- **Python Application Services:** Trackregister, Import, Tag-Transaktionen, Job-Queue, Matching, Export, Persistenz.
- **Analyse-Worker:** rechenintensive Prozesse abgekoppelt, limitiert nach CPU/GPU/RAM, absturzisolierbar.
- **Native Audio Host:** Deck-Vorschau, samplegenaue Audioverarbeitung, Plugins und MIDI, keine Metadatenautorität.
- **Integrationsadapter:** pro Drittprodukt importer/exporter mit Versionserkennung, Datenmapping, Validierung und lesbarem Bericht.

### 6.2 Kommunikationsvertrag

Befehle z. B. `load_preview`, `set_tempo`, `set_pitch`, `set_stem_levels`, `preview_transition`, `open_plugin`, `save_plugin_state`; Ereignisse z. B. `playback_state`, `position`, `underrun`, `plugin_error`. Metadaten-/Set-API unterstützt `track_id`, `file_revision`, `analysis_version`, `set_id`, `transition_id`. Für native Anbindung sind **pybind11/C ABI** oder ein **separater Hostprozess mit lokaler IPC** zu evaluieren. Audiobuffer werden **nicht** in kurzen Abständen durch Python oder HTTP geschoben.

## 7. Datenmodell, Tags und Revisionssicherheit

**EMPFOHLEN:** SQLite als lokale, migrierbare Katalog- und Statusdatenbank; Audiofiles bleiben in ihrem bestehenden Verzeichnis. Ein optionaler Vektorindex unterstützt ähnliche Tracks. Informationen werden nach Zuständigkeit getrennt.

| Entität | Wichtige Felder / Beziehungen |
|---|---|
| Track | stabile UUID; Titel/Artists; Release; Genre; externe IDs; Dateiverweise |
| FileAsset | Track-ID; Pfad/Volume-ID; Format; Grösse; mtime; Inhalts-/Audio-Hash; Revision |
| TagValue | Track/File; Feld; Wert; Quelle; Originalwert; Zeit; Konfliktstatus |
| AnalysisRun | Audio-Fingerprint; Algorithmus/Modell; Version; Parameter; Datum; Qualität; Status |
| AnalysisFeature | BPM, Key, Loudness, Danceability, Stimmung, Beats/Segmente, Konfidenz |
| StemAsset | Parent-Track; Stem-Typ; Dateipfad; Modell; Version; Offset; Sample-Rate; Status |
| Cue / Beatgrid | Track; Quelle; Position; Zeitbasis; Typ; Farb-/Namensattribute; Version |
| SetPlan | Name; Beschreibung; Zieltool; Sortier-/Matching-Regeln; Revision |
| SetEntry / Transition | Reihenfolge; Track; Ein-/Ausstieg; Tempo-/Pitch-Vorschau; Notizen; Rating |
| ExportJob / Mapping | Zieltool/-version; erzeugte Dateien; Feldverluste; Report; Prüfsumme |
| PluginSession | Pluginformat/ID; Version; State-Blob; MIDI-Clips; Artefakte; Zugriffsrechte |

**Schreibschutzprinzip:** Änderungen an Tags werden transaktional geplant, als Diff angezeigt, gesichert und rückgängig gemacht. Externe DJ-Programme können abweichende BPM/Beatgrids speichern; solche Werte werden **nicht stillschweigend zum einzigen Wahrheitswert**. Verschiedene Quellen und manuelle Korrekturen bleiben getrennt.

**ID3-Regel:** Energy/Danceability/Mood besitzen nicht für alle Anwendungsfälle ein universell interoperables Standard-Tag. Sie werden intern kanonisch gespeichert und nur über explizit konfigurierbare Mappings (z. B. ID3 `TXXX` oder kompatible Container-Tags) geschrieben. Bei FLAC/Vorbis, MP4/M4A und WAV müssen Formatgrenzen und Sidecars beachtet werden.

### 7.1 Dateiidentität und portable Pfade

Physische Pfade sind keine Trackidentität. Wir kombinieren UUID, robusten Audio-Fingerprint/Hash, Dateigrösse und zusätzliche Metadaten, um Verschieben, Duplikate und mehrere Versionen zu erkennen. Zielabhängige Pfadzuordnung (Windows-Laufwerk, macOS-Volume, USB-Datenträger) ist ein eigener Adapter. Ausgabepakete können relative Pfade und einen Manifestbericht enthalten.

## 8. Audioanalyse und Track-Matching

### 8.1 Analyse-Pipeline

1. Dateiprobe/Decoder (beispielsweise FFmpeg/PyAV), Format- und Metadatenprüfung.
2. Wiederverwendbare Audiosichten in unterschiedlichen Auflösungen; blockweises Dekodieren, keine unnötigen Vollkopien.
3. Basisanalyse: Länge, Wellenform, Lautheit, Peak/RMS, Dynamik, BPM/Beatgrid und Key.
4. DJ-Analyse: Abschnitte, Intro/Outro, Phrasen, Energy-Kurve, Drops/Breaks, Danceability und Mood.
5. Modellgestützte Analyse: Embeddings und Ähnlichkeit; bei Bedarf Vocals/Instrumente und Rhythmusmerkmale.
6. Ergebnis mit Herkunft, Parametern, Modellversion und Konfidenz speichern; manuelle Korrekturen getrennt verwalten.

**Bibliothekskandidaten (keine Festlegung):** FFmpeg/PyAV für Dekodierung, NumPy/SciPy/SoXR für numerische Verarbeitung, Librosa/Essentia für Features, ONNX Runtime für geeignete ML-Modelle sowie Chromaprint/geeignete Fingerprints für Identifikation. Lizenzstatus, Wartung, Windows/macOS-Builds und reproduzierbare Ergebnisse sind vor Integration zu prüfen – speziell Essentia und proprietäre FFmpeg-Build-Kombinationen.

### 8.2 Matching-Logik

Eine Kombination aus **harten Constraints** und **gewichteten Scores** ist sinnvoll: Tempo-/Key-Abstand (inklusive Half-/Double-Time und möglichem Key-Shift), Energieanstieg, Mood, Genre-Stil, Songstruktur/Phrase, Intro-/Outro-Kompatibilität und Embedding-Nähe. Gewichte sind pro Set/Genre anpassbar. Vorschläge erhalten Begründungen und Konfidenzen; die Hörprobe ist die finale Validierung.

**Beispielhafte Gewichtung – OFFEN:** Harmonie 20 %, Tempo 15 %, Phrasing/Struktur 20 %, Energie 15 %, Stimmung/Stil 15 %, Audio-Ähnlichkeit 10 %, Nutzerhistorie 5 %. Diese Zahlen sind **nur Startwerte** für Tests, keine validierte musikalische Bewertungsfunktion. Eine reine Camelot-Nachbarschaft oder identische BPM garantiert keinen guten Übergang.

### 8.3 Performance und Benchmarking

Messgrössen: Tracks/Minute je Analyseprofil, RAM/Track, CPU/GPU-Auslastung, Cache-Hit-Rate, Fehlerrate, Reproduzierbarkeit, Qualität gegen kuratierte Referenzen und Plattformdifferenzen. Bibliotheken mit **10'000, 50'000 und 100'000 Tracks** als Skalierungsszenarien simulieren. Hardwarebeschleunigung unter Apple Silicon und AMD/Windows nur nach realem Model-Benchmark zusagen; CPU-Fallback muss funktionieren.

## 9. Offline-Stems – Qualitätsstrategie

**BESCHLOSSEN:** Trennung erfolgt nicht live. Modelle können im Hintergrund laufen; Nutzerinnen und Nutzer wählen vorab Qualitätsprofile. Audio Lab und Preview verwenden nur fertig gespeicherte Stems.

- Qualitätsoptimierung vor Echtzeitgeschwindigkeit; hochqualitative Modelle anhand Vocals, Transienten, Phasing und Artefakten vergleichen.
- Originaldatei unverändert lassen; getrennte WAV/FLAC-Artefakte und Metadaten mit Modell-/Versionsinformation speichern.
- Samplegenaue Ausrichtung, Vorlauf/Offset, Gain und ggf. Sample-Rate dokumentieren; Original und Stems müssen synchron bleiben.
- Abbruch, Wiederaufnahme, GPU-Option und Job-Priorität unterstützen; keine unkontrollierten Massenseparationen.
- Bei Modellwechsel gezielte Neuberechnung; vorhandene Stems bis zur Freigabe behalten.
- Rechtliche Fragen bei Verbreitung/Export fremder Stems separat behandeln.

**ZU PRÜFEN:** Demucs-Nachfolger, MDX-/UVR-basierte Modelle, audio-separator und andere aktiv gepflegte Modelle; einheitliche Adapter-Schnittstelle statt harter Modellabhängigkeit.

## 10. Preview-Player und Übergangsvorschau

**BESCHLOSSEN:** Wiedergabe dient der Bewertung einer geplanten Set-Reihenfolge. Dafür werden höchstens zwei Tracks in einer Übergangsprobe benötigt – kein Live-DJ-Workspace.

| Funktion | Minimalanforderung |
|---|---|
| A/B und Überblendung | Schnelles Umschalten und definierte Überlagerung einer Outro-/Intro-Passage |
| BPM / Time-Stretch | Temporäre Ziel-BPM; Key-Lock separat schaltbar |
| Tonhöhe | Temporärer semitonbasierter Pitch-Shift ohne Veränderung der Originaldatei |
| Navigation | Beatgrid, Cue-, Drop- und Strukturmarker; reproduzierbarer Seek |
| Offline-Stems | Pro Stem Mute/Solo/Level; volle Wiedergabe aus vorbereitetem Cache |
| Set-Bezug | Übergangsvariante mit Cue-Paar, Tempo, Key-Shift, Note und Rating speichern |
| Audioqualität | Klickfreie Parameterwechsel, Gain-Schutz, Latenzausgleich soweit erforderlich |

**Konzeptioneller Signalweg:** Track A/B → Decoder/Resampler → Time-Stretch/Pitch → Stem-/Gain-Steuerung → Vorschau-Crossfade → optional FX → Limiter/Output. Dynamische Plugins sind nicht Voraussetzung für das Grundvorhören.

**Technische Empfehlung:** Zunächst Qualität, Latenz und Wartbarkeit von Web Audio/AudioWorklet + WebAssembly gegen einen schmalen nativen C++-Host vergleichen. Da das gewünschte VST3-Audio-Lab später native Prozesse benötigt, kann ein **optionaler JUCE-basierter Host** wirtschaftlich sinnvoll sein; das GUI bleibt unabhängig davon in pywebview.

## 11. Audio Lab und VST3-Plugins

Ein **optionaler** Kreativbereich ergänzt die Set-Planung. JUCE ist der bevorzugte Kandidat für einen separaten C++-Host mit Plugin-Erkennung, Parametern, MIDI, Transport, Presets und nativen Plugin-Editoren. Die Kompatibilität mit einem konkreten VST3 ist **nicht** durch die blosse Existenz eines VST3-SDK gewährleistet.

### 11.1 Anwendungsbeispiele

- **Mixed In Key Wingman 3:** Audio/Vocals einspielen, harmonische Ideen oder MIDI/WAV ableiten; Plugin verlangt geeignete Host-Transport-, Audio- und Editor-Funktionen. Kompatibilität mit einem eigenen Host ist **ZU PRÜFEN**.
- **Vengeance VPS Avenger 2:** MIDI-basierte Bass-/Lead-/Pad-Ideen zu ausgewählten Passagen vorhören.
- **reFX NEXUS:** Instrumentenideen und Preset-Varianten mit vorbereiteten Passagen testen.

Ein MIDI-Clip-Player, Taktsynchronisation, Plugin-State-Persistenz, Plugin-Latenzausgleich und ein separater nativer Plugin-Editor sind ausreichend. Eine vollständige DAW-Timeline, Recording- und Mischkonsole gehören ausdrücklich nicht zum Ziel.

### 11.2 Hosting-Architektur und Robustheit

- **Scanner** in isoliertem Prozess; Plugin-Versionen, Formate, Architekturen und ID erfassen.
- **Host** empfängt Audio- und MIDI-Daten über native Buffer; UI sendet Steuerbefehle.
- **Session** speichert Plugin-State, Host-Version, Routing, verwendete MIDI-/WAV-Entwürfe und Fehlermeldungen.
- **Sicherheit:** nicht vertrauenswürdige Plugins können abstürzen; separate Hostprozesse und Wiederanlaufstrategie prüfen.
- **Formatstrategie:** zuerst VST3; CLAP als spätere Option. Audio Units nur bei begründetem macOS-Bedarf.

**Lizenzhinweis:** JUCE 9 ist entweder nach entsprechender Open-Source-Lizenzstrategie oder mit geeigneter kommerzieller Lizenz zu nutzen; die AGPL-/GPL-Kompatibilität von Gesamtanwendung und Distribution wird juristisch/technisch geprüft. Das VST3-SDK selbst ist MIT-lizenziert; verwendete Drittanbieter-Plugins behalten eigene Lizenzen.

## 12. GUI-Strategie und Desktop-Distribution

**BESCHLOSSEN:** Keine vollständige GUI-Migration. Die bestehende Weboberfläche mit pywebview bleibt. Der aktuelle Vanilla-JavaScript-Ansatz ist funktional; bereits vorhandene Listenvirtualisierung ist eine Stärke.

**EMPFOHLEN:** Schrittweise TypeScript, Vite-basierter Build, klare Komponenten- und API-Grenzen; Vue 3 / Svelte 5 in einem **isolierten** neuen Audio-Lab-/Übergangsmodul vergleichen, nicht als pauschalen Ersatz des gesamten Frontends einführen. UI-Performance über Messungen (Scroll, Filter, 50'000 Tracks, Waveform) überprüfen.

**Distribution:** Windows x64 sowie macOS Apple Silicon zunächst priorisieren; Intel-Mac-Support als ausdrücklichen Buildentscheid klären. Python-App, optionale native Bibliotheken, Hostprozess, Signierung/Notarisierung, SDK-Lizenzen und automatische Updates in CI paketieren. Ein fehlender nativer Host darf Tagging und Bibliotheksverwaltung nicht verhindern.

## 13. Interoperabilität mit dem DJ-Ökosystem – strategischer Schwerpunkt

**BESCHLOSSEN:** Die Integration in vorhandene Werkzeuge ist ein **eigenständiges Produktmerkmal** und nicht nur ein Export-Button. Je weniger manueller Aufwand beim Wechsel zwischen Programmen entsteht, desto höher der Nutzen von TagStudio.

### 13.1 Rollen der externen Produkte

| Produkt | Rolle im Workflow | TagStudio-Integrationsziel |
|---|---|---|
| **DJ.Studio** | Bestehende Offline-Mixing-/Timeline-Lösung | Set-Reihenfolge, Trackauswahl und Planung exportieren; bearbeitete Resultate später zurückführen, soweit dokumentiert |
| **Lexicon DJ** | DJ-Bibliotheksverwaltung und Konvertierung | Tags/Metadaten/Cues möglichst verlustarm austauschen; als unterstützten Übergabekanal verwenden |
| **Mixo** | Bibliotheksverwaltung, Konvertierung und teils Cloud/Backup | Bibliotheks- und Playlist-Austausch über dokumentierte Wege nutzen |
| **Engine DJ** | DJ-Software/Hardwareökosystem – Nutzerpriorität 1 | Playlist-/Set-Übergabe und Analyse-/Cue-Abgleich, soweit sicher machbar |
| **Serato DJ** | DJ-Software – Nutzerpriorität 2 | Crates/Playlists, Trackmetadaten und kontrollierter Cue-Abgleich |
| **VirtualDJ** | DJ-Software – Nutzerpriorität 3 | Playlists, Trackmetadaten und optional weitergehende Sammlungsinformationen |
| **Traktor** | DJ-Software – Nutzerpriorität 4 | NML-/Playlist-Schnittstellen und nachvollziehbare Set-Reihenfolge |
| **rekordbox** | DJ-Software – Nutzerpriorität 5 | Rekordbox-XML-Bridge sowie Track-/Playlist-Mapping |

**Hinweis zur Reihenfolge:** Die Liste Engine DJ → Serato → VirtualDJ → Traktor → rekordbox bildet die vom Nutzer genannte Betrachtungs-/Wunschpriorität ab. **Technische Pilotierung** kann dennoch zuerst mit rekordbox-XML erfolgen, wenn sich dort ein dokumentierter und sicherer Datenaustausch früher nachweisen lässt.

### 13.2 Austauschformate und Integrationsstufen

| Stufe | Inhalt | Prinzip |
|---|---|---|
| **L1 – universell** | M3U8/M3U, CSV, TXT, Audiofiles, MIDI/WAV-Ideen | Sehr gut validierbar; Reihenfolge/Dateireferenzen übertragen, keine Garantie für Cues/Beatgrids |
| **L2 – dokumentierte Produktformate** | rekordbox XML, Traktor-NML und spezifizierte Zielimporte | Feld-/Versionsmapping, Roundtrip-Tests, nur ausgewiesene Funktionen zusagen |
| **L3 – produktabhängige Bibliotheksintegration** | Serato-Crates, Engine-Library, VirtualDJ-Daten/Playlists | zunächst schreibgeschützter Import und geprüfte Exportwege; niemals undokumentierte Live-Datenbanken verändern |
| **L4 – Sync/Bridge** | Wiederholte, bidirektionale Abgleiche mit Konfliktdialog | Nur bei validiertem Format-/API-Verhalten und sauberem Datenbesitz |

**Wesentliche Rechercheergebnisse (Stand 14.10.2026):** rekordbox stellt ein dokumentiertes XML-Playlist-/Bridge-Format bereit. Traktor dokumentiert den Playlist-Import/-Export und NML als Dateiformat. Serato DJ 4.0 verwendet laut Hersteller überwiegend `Subcrates` statt älterer `Crates`-Strukturen; frühere `database V2`-Annahmen sind für neue Versionen nicht ausreichend. VirtualDJ liest verschiedene fremde Sammlungen/Playlists, behandelt klassische M3U-Playlists aber anders als eigene native Playlists. Engine DJ unterstützt offiziell den Import einer Serato-Bibliothek. Daher sind generische Formatbehauptungen **pro Version in einem echten Test nachzuweisen**. [Quellen S04–S09]

### 13.3 Zieladapter – gewünschte Umsetzung

**Engine DJ (Priorität 1):** 1) sicheren Satz von Setlisten-/Dateiexporten definieren; 2) dokumentierten Import über Engine Desktop bzw. geprüfte Zwischenformate testen; 3) bei Bedarf Lexicon/Mixo als Brücke evaluieren. Hot Cues, Beatgrids oder Engine-Datenbanken erst nach explizitem Roundtrip-Test. Keine direkte Schreiboperation auf laufende Engine-Bibliotheken.

**Serato (Priorität 2):** Crate-/Subcrate- und Playlist-Import für die jeweilige Major-Version prüfen; Track-Identitäten anhand Pfad + Fingerprint sichern. Ein Export darf keine existierenden Nutzer-Cues zerstören. Serato 4.x benötigt eigene Fixtures; ältere Formate nicht ungeprüft als Standard verwenden.

**VirtualDJ (Priorität 3):** Native Playlist- und Fremdbibliothekslesefunktionen unterscheiden; M3U-Übergaben am realen Produkt testen. Reiner Dateiexport ist nicht automatisch gleichbedeutend mit korrekter Playlist-Anzeige. Datenbank-/XML-Schreiben nur nach Freigabe eines stabilen Adapters.

**Traktor (Priorität 4):** Zunächst NML-Playlist-Import/-Export verwenden und Reihenfolge/Pfade prüfen. Tags, Hot Cues, Beatgrids und sonstige Traktor-spezifische Zustände erst über eine separat geprüfte Abbildung übernehmen.

**rekordbox (Priorität 5):** Dokumentiertes XML-Bridge-Format als frühes Referenzformat nutzen. Gültiges XML, Positions-/Pfadzuordnung, Importverhalten, erneuter Import und Einschränkungen im Zielprogramm in automatisierten Fixtures und manuellen Tests prüfen.

### 13.4 DJ.Studio, Lexicon und Mixo intelligent einbeziehen

**DJ.Studio:** M3U/M3U8/TXT/CSV-Playlist-Exports sind dokumentiert; darüber kann eine geordnete Trackliste transportiert werden. Erweiterte DJ-Set-Exports sind je Zielprogramm verschieden und werden laufend erweitert. Die DJ.Studio-Hilfeseiten nennen für Engine DJ und Traktor teils zukünftige beziehungsweise generische Exportpfade; **Funktionsumfang/Version vor Implementierung live testen**. Keine unbestätigte öffentliche Projekt-API voraussetzen. Mögliche Richtung: `TagStudio SetPlan -> M3U8 -> DJ.Studio`; Rückweg zunächst über exportierte Playlists/Medien und dokumentierte Formate, **nicht** durch direktes Editieren interner DJ.Studio-Projekte.

**Lexicon:** Das Produkt dokumentiert Konvertierung zwischen rekordbox, Serato, Traktor, VirtualDJ, Engine DJ und djay Pro einschliesslich Trackinfos, Cues, Beatgrids und Playlists mit produktabhängigen Einschränkungen. Es ist ein **geeigneter ergänzender Austauschkanal**, kein von TagStudio zu ersetzender Konverter.

**Mixo:** Die Dokumentation nennt Import/Export mehrerer DJ-Bibliotheken und Formate, unter anderem Serato-Crates, Traktor-NML, rekordbox- und VirtualDJ-XML und Engine-Export. Einige Exportfunktionen können einen kostenpflichtigen Plan erfordern; dies ist **keine zugesagte kostenlose Integrationsmöglichkeit**.

### 13.5 Kanonisches Austauschmodell und Verlustbericht

TagStudio führt ein eigenes neutrales SetPlan-Modell und übersetzt daraus in Zieladapter. Beispiel einer **konzeptionellen**, nicht verbindlichen JSON-Struktur:

```json
{
  "schema_version": "1.0-draft",
  "set_id": "uuid",
  "entries": [{
    "track_id": "uuid", "order": 1,
    "file_ref": "portable-file-id",
    "cue_in_ms": 32000, "cue_out_ms": 198000,
    "preview_bpm": 124, "preview_key_shift": 0
  }],
  "target": {"application": "engine-dj", "version": "detected"},
  "export_manifest": {"warnings": [], "unmapped_fields": []}
}
```

Jeder Export erstellt einen **Preview-Diff und einen lesbaren Kompatibilitätsbericht**: Was wurde übertragen (Reihenfolge, Pfade, Tags, Cues, Beatgrid, Bewertungen)? Was ging verloren oder konnte nicht abgebildet werden? Welche Formate/Versionen wurden verwendet? Wurden Dateien kopiert oder referenziert? Ein wiederholter Import sollte bestehende Set-Entwürfe nicht ungefragt duplizieren.

### 13.6 Übertragungstests / Abnahmekriterien

- Testsatz aus mindestens 30 Tracks: MP3, FLAC, WAV/AIFF/M4A soweit unterstützt, Sonderzeichen, Multi-Artists, fehlende Tags, Netz-/USB-Pfade, Duplikate.
- Zwei Export-/Importzyklen pro Zieltool und OS, inklusive Reihenfolge und Auflösung aller Referenzen.
- Separate Tests für 1) Playlists, 2) Metadaten, 3) Cues/Loops, 4) Beatgrids; jede Kategorie unabhängig freigeben.
- Originalbibliotheken auf Dateiebene sichern; keine Schreibtests an produktiven Datenbanken.
- Stabile Identitätszuordnung, Meldung unauffindbarer Dateien, keine stillen Überschreibungen.
- Änderungen externer Major-Versionen aus Kompatibilitätsmatrix erkennen und Adapter bis zur Validierung gegebenenfalls nur lesend betreiben.

## 14. Externe Musikquellen und Discovery – Abgrenzung

Frühere Ideen wie Beatport/SoundCloud, 1001Tracklists und Shazam-/Fingerprint-Dienste können künftig die Discovery und Metadatenanreicherung unterstützen. Dieser Bereich ist **nicht Teil der Kern-Interoperabilität mit DJ-Programmen**. APIs, Nutzungsbedingungen, öffentliche/Partner-Zugänge und Downloadrechte sind je Anbieter gesondert zu bewerten. Ein Stream- oder Downloadrecht darf nicht aus der technischen Möglichkeit abgeleitet werden.

## 15. Lizenzierung, Sicherheit und Betrieb

- **GPL-3.0-or-later TagStudio:** Abhängigkeiten und Verteilungsmodell müssen kompatibel geprüft werden.
- **JUCE 9:** konkrete Lizenzwahl, AGPL-/kommerzielle Kombination sowie Projektverteilung vor verbindlicher Auswahl juristisch prüfen.
- **VST3-SDK:** MIT-Lizenz des SDKs; Namen/Markenregeln und Plugins separat beachten. **CLAP:** MIT-lizenzierte Spezifikation/Referenzcode prüfen.
- **Plugins Dritter:** keine Lizenzumgehung; nur lokal installierte, berechtigte Instanzen. Plugin-Scan isolieren; vertrauenswürdige und unbekannte Plugins unterscheiden.
- **Dateischutz:** Tag-Backups, Undo, Snapshot und atomare Schreiboperationen beibehalten; Eingriffe in fremde Bibliotheken standardmässig deaktivieren.
- **Privacy/Netzwerk:** lokale Verarbeitung als Standard; externe Requests, API-Credentials und Uploads sichtbar zustimmungsbedürftig.
- **CI/Release:** Windows/macOS-Builds, Bibliothekslizenzen, signierte Artefakte (wo möglich), SBOM, reproduzierbare Dependency-Locks und Regressionstests.

## 16. Risiken, Abhängigkeiten und Gegenmassnahmen

| Risiko | Wirkung | Gegenmassnahme |
|---|---|---|
| Drittanbieter ändern Dateiformate / Library-Versionen | Set-Export oder Import fällt aus | Versionierte Adapter, Compatibility Suite, konservativer read-only-Fallback |
| Proprietäre Cue-/Beatgrid-Daten | Informationsverlust | Feldmatrix, Roundtrip-Tests, sichtbarer Verlustbericht |
| VST3-Host instabil / Plugin inkompatibel | Absturz, unbrauchbare Sitzung | separater Host, Scanner, Whitelist/Blacklist, sichere Wiederaufnahme |
| JUCE-/Modell-/Codec-Lizenzen | Distribution blockiert | License Gate vor Architekturfixierung und Release |
| Analysequalität variiert stark | Falsche Trackvorschläge | Ground-Truth-Tracks, mehrere Algorithmen, Confidence, menschliches Vorhören |
| CPU/GPU/RAM-Spitzen | Langsames GUI oder Preview-Dropouts | Worker-Prioritäten, Caching, Benchmarking, Preview vor Hintergrundjobs |
| Migrationsfehler an bestehenden Tags | Datenverlust | Backup, reversible Migration, Diff, Tests über echte Dateien |
| Scope Creep Richtung DAW/DJ-App | Hohe Komplexität, Fokusverlust | explizite Nicht-Ziele und P0/P1/P2-Gates |

## 17. Umsetzungsphasen und Abnahmekriterien

| Phase | Ergebnisse | Exit-Kriterium |
|---|---|---|
| **0 – Bestandsaufnahme** | Code-/Datenmodell-Audit, Feature-Inventar, Baseline-Benchmarks, Lizenzmatrix | Bestehende Tests grün; Architektur-ADRs dokumentiert |
| **1 – Daten & Austausch** | Track-IDs, Import-/Exportmodell, SetPlan, M3U8/CSV, XML-/NML-Pilot | 30-Track-Fixtures, kein Datenverlust, geprüfte Exportberichte |
| **2 – Analyse & Matching** | Worker, Cache, Grundmerkmale, Ranking mit Begründungen | Vergleich gegen kuratierte Tracks; nachvollziehbare Laufzeiten |
| **3 – Preview** | BPM/Key-Lock/Pitch, A/B, Cue-/Übergangsprobe | stabile Wiedergabe unter Windows/macOS; Übergangssitzung speicherbar |
| **4 – Offline-Stems** | Modelladapter, Qualitätsprofil, Stem-Assets und Vorschau | Artefakte synchron, Originaldatei unverändert, Wiederaufnahme funktioniert |
| **5 – Audio Lab Pilot** | JUCE/VST3-Prototyp, MIDI, ein Effekt, ein Instrument, Wingman-Test | Host-Kompatibilität und Lizenzstrategie nachgewiesen |
| **6 – Tiefe Interoperabilität** | Engine/Serato/VirtualDJ/Traktor/rekordbox-Adapter | Jeder Adapter hat dokumentierte Feldmatrix, Tests und Warnungen |

**Meilenstein-Politik:** Ein Phase-Gate entscheidet anhand von Tests und Nutzerwert, ob die nächste Funktion integriert oder verschoben wird. Ein Fehlschlag bei JUCE/VST3 blockiert nicht die Kernentwicklung der Bibliothek.

## 18. Offene Entscheidungen – noch nicht vom Nutzer beantwortet

Die acht zuletzt gestellten Architekturfragen wurden noch **nicht** final beantwortet. Folgende Voreinstellungen sind **Empfehlungen**, ausdrücklich **keine Nutzerbeschlüsse**:

| ID | Offene Entscheidung | Empfohlene Ausgangsposition |
|---|---|---|
| D01 | Audio-Engine intern oder eigenständig? | Eigenes, versioniertes Modul mit klarer API; zunächst im gemeinsamen Repo möglich |
| D02 | Weitere Audioformate vollständig taggen? | MP3 bewahren, FLAC/WAV/AIFF/M4A stufenweise nachziehen |
| D03 | Dimensionierung | 50'000 Tracks als Ziel, 100'000 als Stresstest |
| D04 | Analysenumfang der ersten Lieferung | BPM/Key/Loudness/Energy zuerst; Drops/Struktur/Mood/Ähnlichkeit danach |
| D05 | Speicherort der Analyseergebnisse | Zuerst interne Datenbank, nur explizit in Tags übernehmen |
| D06 | VST3-Zeitpunkt | Effekte zuerst; Instrumente/Wingman erst nach Host-Pilot |
| D07 | Kostenpflichtige SDKs | Nach Einzelprüfung erlaubt; Lizenzkosten und GPL-Kompatibilität bewerten |
| D08 | Umbaugrad | Gezieltes Refactoring bei Bedarf; kein flächendeckender Rewrite |

**Zusätzliche Freigaben:** D09 rechtliche Lizenzstrategie JUCE/Codec/Stem-Modelle; D10 Zielversionen und Betriebssysteme der DJ-Programme; D11 Positionierung des SetPlan-Austauschs gegenüber DJ.Studio; D12 tatsächliche Qualitätskriterien der Offline-Stems; D13 Audioformat-/Tag-Mapping pro Container; D14 erlaubte Export-/Sync-Automatisierung je Zieltool.

## 19. Konkrete Arbeitsaufträge für Claude und ChatGPT

1. **Ist-Analyse:** Repository-Module, Aufrufhierarchien, bestehende Tests, Datenpfade und aktuelle Import-/Exportfunktionen katalogisieren. Keine Änderung am Code ohne Issue/ADR.
2. **ADR-001:** Python-Core + optionale native Audio-Engine gegenüber Vollmigration/Browser-only vergleichen (Kriterien: API, Lizenz, Packaging, Stabilität).
3. **ADR-002:** kanonisches Track/SetPlan-Modell definieren; Migration mit Rückwärtskompatibilität und Backup.
4. **ADR-003:** Integrationsebenen L1–L4, Feldmatrix und readonly/overwrite-Sicherungen spezifizieren.
5. **Proof of Concept A:** Austauschpakete M3U8/CSV und rekordbox XML + Traktor NML an 30-Track-Fixture testen.
6. **Proof of Concept B:** Native Preview (Tempo/Key-Lock/A-B) gegen browserbasierte Lösung vergleichen.
7. **Proof of Concept C:** JUCE Host mit VST3-Effekt, Instrument sowie anschliessend Wingman, Avenger und NEXUS testen.
8. **Benchmark-Protokoll:** Datensatz, Modellversion, Hardware, Laufzeiten, Fehler, Qualität und Lizenznotizen festschreiben.
9. **Issue-Backlog:** Epics für Datenkern, Analyse, Matching, Preview, Stems, Interoperabilität, Audio Lab, GUI-Refactoring, Packaging anlegen; jedes Issue mit Akzeptanztests.
10. **Änderungsdisziplin:** Pro Merge Request Ziel, Annahmen, betroffene Schnittstellen, Tests, Migration und Rollback vermerken.

## 20. Technische Quellen und zu prüfende Referenzen

Die folgenden Quellen dienen als **Referenzstand am 14.10.2026**; Implementierungsdetails hängen von installierten Versionen und den aktuell gültigen Herstellerbedingungen ab.

- **S01** TagStudio Repository: https://github.com/MarkusKeller8200/markussxch-tagstudio
- **S02** TagStudio Python-Build und Oberfläche: https://github.com/MarkusKeller8200/markussxch-tagstudio/blob/main/tagstudio_web.py
- **S03** DJ.Studio – DJ-Set-Export und Grenzen: https://help.dj.studio/en/articles/16833153-export-dj-set-to-your-live-dj-software
- **S04** DJ.Studio – Formate, Workflow und Beatgrid-Einschränkungen: https://help.dj.studio/en/articles/8106079-exporting-mixes
- **S05** Lexicon – Cross-DJ-Konvertierung: https://www.lexicondj.com/manual/convert-library
- **S06** Mixo – Exportmatrix: https://www.mixo.dj/guides/dj-software-export-guide
- **S07** Engine DJ – offizieller Serato-Import: https://support.enginedj.com/support/solutions/articles/69000847452
- **S08** Serato – aktueller `_Serato_`-Ordner, Legacy und Subcrates: https://support.serato.com/hc/en-us/articles/204022904-What-is-in-the-Serato-folder
- **S09** VirtualDJ – Playlist- und Bibliothekseinbindung: https://virtualdj.com/manuals/virtualdj/interface/database/playlists.html
- **S10** Traktor Pro – Playlist-Import/-Export: https://docs.native-instruments.com/ni-tech-manuals/traktor-pro-manual/en/working-with-playlists
- **S11** rekordbox – dokumentierte XML-Schnittstelle: https://rekordbox.com/en/support/developer/
- **S12** JUCE 9 Lizenztext und Bedingungen: https://juce.com/legal/juce-9-licence/
- **S13** JUCE AudioPluginHost-Referenz: https://github.com/juce-framework/JUCE/tree/master/extras/AudioPluginHost
- **S14** Steinberg VST3-SDK / MIT-Lizenz: https://github.com/steinbergmedia/vst3sdk
- **S15** CLAP-Spezifikation: https://github.com/free-audio/clap
- **S16** Mixed In Key Wingman 3 – Funktionsumfang/Hosts: https://mixedinkey.com/Wingman/
- **S17** Wingman Release Notes und Instrument-Hosting: https://mixedinkey.com/release-notes/wingman/
- **S18** Mixo – Tarif-/Funktionsunterschiede: https://www.mixo.dj/guides/features

## 21. Glossar

| Begriff | Bedeutung |
|---|---|
| Beatgrid | Zeitlich verankerte Beat-/Taktpositionen eines Tracks |
| Camelot | Harmonische Tonartnotation für DJ-Workflows |
| Cue / Hot Cue | Markierte Position, die zum Vorhören oder im DJ-System aufgerufen wird |
| DSP | Digital Signal Processing; digitale Audioverarbeitung |
| Embedding | Merkmalsvektor zur Ähnlichkeitsbewertung |
| Key-Lock | Tempo verändern bei möglichst beibehaltener Tonhöhe/Tonart |
| NML | Traktor-eigenes XML-basiertes Collection-/Playlist-Dateiformat |
| Preview | Nichtdestruktives Vorhören zur musikalischen Entscheidungsfindung |
| SetPlan | Kanonisches, programmunabhängiges Modell eines geplanten DJ-Sets |
| Stem | Separierte Instrumenten-/Vocal-Spur eines Tracks |
| VST3 | Plugin-Schnittstelle für Audioeffekte und virtuelle Instrumente |
