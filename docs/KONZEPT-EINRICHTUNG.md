# Konzept: Profile (zweite unabhängige Installation) und Einrichtungsassistent

Status: **Entwurf 2026-10-11** – zur Prüfung durch den User. Issues im Meilenstein „4.4.0 – Beatport-Download,
Profile, Einrichtungsassistent“ (Label `idee` – zur Prüfung), Reihenfolge und Umfang legt der User fest.

Issues: #163 zentrale Pfade · #164 Start mit Profil · #165 Profil-Verwaltung · #166 zweite Installation (optional) ·
#167 Assistent-Grundgerüst · #168 Assistent-Inhalte · #169 Menüpunkte ein-/ausblenden · #170 „Erste Schritte“ /
„Neu in dieser Version“.

## Ausgangslage

Wunsch des Users (2026-10-11): eine **frische, zweite Installation** neben der bestehenden betreiben, mit vollständig
getrennten Einstellungen – und neue Benutzer sollen von einem **Assistenten** durch die Einstellungen geführt werden,
statt von den vielen Funktionen erschlagen zu werden.

## Teil A – Zweite unabhängige Installation („Profile“)

### Heute: wo TagStudio Daten ablegt

| Was | Ort heute | Datei / Modul |
|---|---|---|
| Einstellungen | `~/.tagstudio.json` | `core.CONFIG` |
| Einzel-Instanz-Sperre | `~/.tagstudio.lock`, Windows-Mutex `MarKusSXCH-TagStudio` | `instance.py` |
| Caches (Listen, Wellenform, Cover, Tag-Scan) | `~/TagStudio/cache/…` | `listcache`, `waveform`, `thumbs`, `taghelp` |
| Sicherungen (Standard) | `~/TagStudio/Sicherungen` | `backup.py` |
| Snapshots | `~/TagStudio/Snapshots` | `snapshots.py` |
| Einstellungs-Sicherungen | `~/TagStudio/Einstellungen` | `appsettings.py` |
| Plugins (eigene), Plugin-Daten, Protokolle | `~/TagStudio/Plugins`, `Plugin-Daten`, `Logs` | `plugins.py`, `applog.py` |
| Hintergrund-Aufträge | `~/TagStudio/Auftraege.json` | `jobs.py` |
| Vorbereiten, Entdecken | `~/TagStudio/Vorbereiten`, `~/TagStudio/Entdecken` | `prepare.py`, `discover.py` |
| Beatport-Token | `Plugin-Daten/beatport/token.bin` (DPAPI) | Beatport-Plugin |
| Oberfläche (Browser-Speicher) | WebView2-Benutzerdaten des Programms | `tagstudio_web.py` |
| Installation | `{Programme}\TagStudio`, feste Inno-`AppId` | `packaging/windows.iss` |

Diese Pfade stehen an rund 15 Stellen im Code. Eine zweite Installation in einen anderen Programmordner würde deshalb
**dieselben** Einstellungen und Daten benutzen – und die Einzel-Instanz-Sperre verhindert, dass beide gleichzeitig
laufen.

### Varianten

| Variante | Idee | Vorteile | Nachteile |
|---|---|---|---|
| **A1 Profile** (empfohlen) | Ein Programm, mehrere getrennte Datenordner („Profile“). Start mit Profil über Verknüpfung (`--profil Test`) oder Profilwahl beim Start. | Ein Update für alle, keine zweite Installation nötig, beliebig viele Profile, sauber testbar | Verknüpfungen nötig |
| A2 Portable | Datei `profil.ini` neben dem Programm → alle Daten in einem Ordner daneben (z. B. auf USB-Stick) | Komplett in sich geschlossen, gut für „frische Installation zum Testen“ | Updates je Kopie, Installer-Weg passt nicht |
| A3 Zweiter Installer-Eintrag | Installer-Option „zusätzliche Installation“ mit eigener `AppId` und eigenem Ordner | Wirkt wie zwei Programme | Aufwendig (zwei Deinstallationen, zwei Updates), braucht trotzdem A1 für getrennte Daten |

**Vorschlag:** A1 als Grundlage, A2 als kleine Ergänzung (dieselbe Technik, nur anders ausgelöst). A3 nur, falls
wirklich zwei Programmversionen nebeneinander nötig sind (z. B. stabil + Beta).

### Umsetzung A1/A2

1. **Zentrale Pfade** (`paths.py`): eine Funktion `data_root()` liefert den Datenordner; alle Module holen ihre Pfade
   dort (Einstellungen, Caches, Sicherungen, Snapshots, Plugins, Logs, Vorbereiten, Entdecken, Aufträge, Sperre).
   Ohne Profil bleibt **alles wie heute** (`~/.tagstudio.json`, `~/TagStudio`) – bestehende Daten werden nicht verschoben.
2. **Profil bestimmen** (Reihenfolge): Startparameter `--profil NAME` → Umgebungsvariable `TAGSTUDIO_PROFIL` →
   `profil.ini` neben dem Programm (portable) → Standard.
   Profil-Daten: `~/TagStudio-Profile/<NAME>/` mit `einstellungen.json` und denselben Unterordnern wie heute.
3. **Getrennt laufen:** Sperre und Windows-Mutex je Profil (`MarKusSXCH-TagStudio-<NAME>`), eigener WebView2-Speicher,
   Fenstertitel und Seitenleiste zeigen das Profil („TagStudio · Test“). Der Installer prüft weiterhin nur das
   Standardprofil (bzw. alle Mutexe mit Präfix).
4. **Verwaltung** (Einstellungen › Profile): neues Profil anlegen (leer oder mit Einstellungen aus dem aktuellen),
   Verknüpfung auf Desktop/Startmenü erstellen, Profil-Ordner öffnen, Einstellungen aus einem anderen Profil übernehmen
   (nutzt den bestehenden Export/Import aus `appsettings.py`), Profil löschen nur nach Rückfrage.
5. **Sicherheit:** Snapshots, Sicherungen und Vorbereiten-Ordner zeigen auf Musikordner – zwei Profile dürfen dieselbe
   Bibliothek benutzen; Hinweis, wenn zwei Profile in denselben Sicherungs-/Snapshot-Speicher schreiben würden.
6. **Tests:** Profil-Start in einem Test-HOME; keine Datei ausserhalb des Profilordners wird geschrieben.

**Für den konkreten Wunsch („frische Installation“)** reicht danach: Einstellungen › Profile › „Neues Profil (leer)“ →
Verknüpfung „TagStudio (Neu)“ starten → TagStudio startet wie beim allerersten Mal, inklusive Assistent (Teil B).

## Teil B – Einrichtungsassistent

### Ziel

Neue Benutzer erhalten beim ersten Start eine geführte Einrichtung in wenigen, verständlichen Schritten. Jeder
Schritt erklärt **wofür** eine Funktion gut ist, schlägt eine sinnvolle Einstellung vor und lässt sich überspringen.
Alles ist später unter Einstellungen änderbar; der Assistent lässt sich jederzeit erneut starten (Hilfe ›
„Einrichtungsassistent“).

### Schritte (Vorschlag)

| # | Schritt | Fragt / stellt ein | Bezug |
|---|---|---|---|
| 1 | Willkommen | Was willst du vor allem tun? (Tags bearbeiten · neue Tracks vorbereiten · Ordner vergleichen · DJ-Sets planen) → empfiehlt, welche Menüpunkte sichtbar sind | Seitenleiste |
| 2 | Deine Musik | Bibliotheksordner (Tagger-Standardordner), optional Eingangsordner für „Vorbereiten“ | Tagger, Vorbereiten |
| 3 | Sicherheit | Sicherungen vor dem Speichern (Ordner, im Snapshot-Speicher), Snapshot der Bibliothek anlegen | Sicherungen, Snapshots |
| 4 | Deine Programme | Welche DJ-/Analyse-Programme nutzt du? (Mixed In Key, beaTunes, Lexicon, Engine DJ, Serato, Rekordbox, Platinum Notes, Picard …) → Herkunft, passende Plugins einschalten, Vorbereiten-Workflow aus der Vorlage zusammenstellen | Herkunft, Plugins, Vorbereiten |
| 5 | Online-Dienste (optional) | Online-Metadaten, Beatport-Anmeldung, Stems-Plugin installieren – mit Hinweis auf Kosten/Zugangsdaten | Plugins |
| 6 | Darstellung | Hell/Dunkel, Player-Position, Kurzwahl der Tastatur | Einstellungen |
| 7 | Fertig | Zusammenfassung, „Erste Schritte“-Hinweise einschalten, Link zu Hilfe › Tastatur und Handbuch | Hilfe |

### Bausteine

- **Erststart-Erkennung:** keine Einstellungsdatei bzw. `setup_done` fehlt → Assistent; bestehende Benutzer sehen ihn
  nicht automatisch (nur über die Hilfe).
- **Eigene Assistenten-Ansicht** (Vollbild-Overlay mit Fortschritt „Schritt 2 von 7“, Zurück/Weiter/Überspringen) – nicht
  im bestehenden Einzel-Dialog, damit Dateibrowser und Rückfragen darin funktionieren.
- **Menüpunkte ein-/ausblenden** (Einstellungen › Darstellung › Seitenleiste): wenig genutzte Module verstecken; der
  Assistent setzt eine Empfehlung, alles bleibt jederzeit einblendbar.
- **„Erste Schritte“-Hinweise** je Seite: kleine, abschaltbare Karte oben („So funktioniert der Tagger in 3 Schritten“),
  verschwindet nach dem ersten Benutzen.
- **„Neu in dieser Version“:** nach einem Update kurze Hinweise nur zu neuen Funktionen (aus dem CHANGELOG), damit
  Neuerungen auffallen, ohne dass der Assistent nochmals ganz durchlaufen werden muss.

### Offene Fragen an den User

1. Profile nur über Verknüpfungen starten (A1) oder zusätzlich eine **Profilwahl beim Start** anzeigen?
2. Brauchst du wirklich eine **zweite Installation** (A3, z. B. stabile Version + Beta parallel) oder reicht ein zweites
   Profil derselben Installation?
3. Soll ein neues Profil die **Plugins** (z. B. Stems mit grossen Modellen) mitbenutzen oder komplett leer starten?
4. Assistent: sollen nicht gewählte Module **ausgeblendet** werden oder nur „empfohlen“ markiert?
5. „Erste Schritte“-Hinweise und „Neu in dieser Version“: gewünscht oder zu viel?
