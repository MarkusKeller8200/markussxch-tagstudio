# Konzept: Modul IDEE – Ideen sammeln, Wunschlisten pflegen, später kaufen (#186)

Stand: 2026-10-26 (4.12.0, Meilenstein #28) · Status: **KONZEPT – Entscheide I1–I6 freigegeben (27.10.2026)**, noch nicht umgesetzt.

> Was es heute schon gibt (umgesetzt) und was geplant ist, ist in jedem Abschnitt getrennt markiert. Nichts aus diesem
> Konzept ist implementiert, bevor der User die Entscheide in Abschnitt 8 freigegeben hat (Issue #186, Phase 2).

## 1. Ziel

Neue Titel, die beim Stöbern auffallen (Entdecken, Beatport, Spotify, ein Tipp eines Freundes), sollen nicht mehr in
„Vorbereiten“ landen, sondern in einem eigenen Bereich **IDEE**: dort werden sie in **Wunschlisten** gesammelt,
vorgehört, mit Notizen versehen und später gekauft. Gekaufte Titel gehen über **Käufe** und **Vorbereiten** in die
Bibliothek; die Idee erkennt das selbst und wird erledigt.

**Entscheid User (25.10.2026, 23:06):** „Idee merken“ kommt ins Modul IDEE – dort Playlists (Wunschlisten) pflegen,
um die Titel später zu kaufen.

**Nichtziele:** kein automatischer Kauf, kein Mixen, keine Datenmigration ohne Rückfall (die Daten von Entdecken bleiben
unverändert erhalten).

## 2. Ausgangslage (umgesetzt)

- **Entdecken** (#120, #162, #258, #291) ist heute ein Reiter in „Vorbereiten“ (`web/discover.js`, `discover.py`,
  `session_discover.py`, Zustand `~/TagStudio/Entdecken/entdecken.json`). Einträge haben den Status
  `new | saved | hidden | bought`; „gemerkt“ (`saved`) ist die heutige Merkliste, Export als Excel/CSV.
- **Playlists** (#267–#284) kennen **Einträge ohne Datei** (Künstler, Titel, Mix, ISRC, Länge, Link), verknüpfen sie
  automatisch, sobald der Titel in der Bibliothek ist, und exportieren eine **Einkaufsliste**. KONZEPT-PLAYLISTS
  Abschnitt 16 sieht „Neuerscheinungen als Merkliste-Playlist“ ausdrücklich vor.
- **Käufe** (#285, #290, #334–#338) gleicht gekaufte Titel mit der Bibliothek ab und kann Beatport-Playlists anlegen.
- **#333** trennt Entdecken von Vorbereiten (eigene Seite, an erster Stelle).

## 3. Nutzer-Workflow (geplant)

```
Entdecken / Beatport / Spotify / von Hand
        │  „Idee merken ▸ Wunschliste“
        ▼
IDEE: Wunschlisten ── vorhören, Notiz, Bewertung, Status „Idee → Kaufen“
        │  „Kaufen“ (Link zum Store) bzw. „Als Beatport-Playlist“ (#334-Schnittstelle)
        ▼
Käufe: gekauft erkannt (Store-ID bzw. Künstler + Titel + Mix) → Idee „gekauft“
        │  Download / ZIP (#336) → Eingang
        ▼
Vorbereiten → Bibliothek: Eintrag mit Datei verknüpft → Idee „in Bibliothek“ (erledigt)
        │
        ▼
DJ-Set / Playlists: Wunschliste lässt sich als Playlist weiterverwenden
```

## 4. Bausteine (geplant)

### 4.1 Seite „Ideen“ (Seitenleiste)

- Links die **Wunschlisten** (Name, Anzahl offen/gekauft), „Neue Wunschliste …“, umbenennen, löschen (nach Rückfrage,
  Einträge zuerst verschieben oder mitlöschen).
- Rechts die Einträge der gewählten Liste: Cover, Künstler, Titel, Mix, Label, Datum, Quelle, Status, Notiz, Link,
  Vorhören (wie Entdecken), sortier- und filterbar (Status, Quelle, Suche); Spaltenbreite wie #337/#340.
- Aktionen: Status setzen (*Idee*, *Kaufen*, *Verworfen*), Notiz, in andere Liste verschieben/kopieren, beim Store
  öffnen, „Online suchen ›“ (#283), Export (Excel/CSV, Einkaufsliste), „Als Beatport-Playlist“ (siehe I5).
- Seitenleisten-Zahl: Einträge mit Status *Kaufen*.

### 4.2 Übernahme aus Entdecken

- In Entdecken wird „Merken“ zu **„Idee merken ▸“** mit Auswahl der Wunschliste (zuletzt benutzte vorgewählt).
- Der Eintrag bleibt in Entdecken sichtbar und bekommt das Kennzeichen „in Ideen“; er fällt beim „Leeren“ nicht weg.
- **Einmalige Übernahme** (Migration): beim ersten Öffnen der Seite „Ideen“ werden alle gemerkten Einträge
  (`saved`) aus Entdecken in die Wunschliste „Gemerkt (Entdecken)“ kopiert. `entdecken.json` wird **nicht** verändert;
  ein Kennzeichen in den Ideen verhindert doppelte Übernahme. Rückfall: Entdecken funktioniert unverändert weiter.

### 4.3 Status und automatische Erkennung

| Status | Bedeutung | Wechsel |
|---|---|---|
| Idee | gemerkt | Standard |
| Kaufen | zum Kauf vorgemerkt | von Hand |
| Gekauft | in „Käufe“ gefunden | automatisch beim Käufe-Abgleich (Store-ID, sonst `playlists.match_ref` streng) |
| In Bibliothek | Datei vorhanden, verknüpft | automatisch wie bei Playlists (Einträge ohne Datei werden verknüpft) |
| Verworfen | nicht mehr interessant | von Hand; ausgeblendet, nicht gelöscht |

### 4.4 Übergabe an Käufe, Vorbereiten, DJ-Set

- **Käufe:** Wunschliste *Kaufen* ↔ Käufe-Abgleich; „Als Beatport-Playlist“ nutzt `store_playlist_put` (#334) mit
  `TagStudio_WISH_<Liste>` – so lassen sich alle Titel einer Liste in Beatport mit einem Klick in den Warenkorb legen
  (nur mit eingeschalteter Plugin-Einstellung, nur auf Klick).
- **Vorbereiten:** keine Ideen-Navigation mehr (#333 entfernt den Reiter); neue Dateien werden nach der Übernahme in
  die Bibliothek mit offenen Ideen verknüpft (gleicher Mechanismus wie Playlists #271).
- **DJ-Set / Playlists:** „Als Playlist übernehmen“ legt eine normale Playlist an (Einträge ohne Datei bleiben
  Einkaufsliste, vorhandene sind verknüpft).

## 5. Datenmodell (Vorschlag, siehe I2)

**Variante B (empfohlen): Wunschlisten sind Playlists.** Ein eigener Ordner „Ideen“ im Playlists-Speicher
(`playlists.py`); jede Wunschliste ist eine Playlist mit Einträgen ohne Datei (`ref`: Künstler, Titel, Mix, ISRC,
Länge, Link, Quelle, Store-ID) und zusätzlichen Feldern je Eintrag: `idea: {status, note, src, preview, cover, label,
date, added, disc_key}`. Vorteile: Verknüpfen mit der Bibliothek, Einkaufsliste, Export/Import, Senden an Lexicon und
Archiv gibt es schon; die Seite „Ideen“ ist eine eigene, schlanke Sicht darauf.

Variante A: eigener Speicher `~/TagStudio/Ideen/ideen.json` (Listen + Einträge). Einfacher getrennt, aber alles oben
Genannte müsste nachgebaut werden.

Je Profil, atomar gespeichert, Teil der Programmdaten für den Cloud-Abgleich (#317, Bereich „Playlists“ bei B).

## 6. Rechte, Datenschutz, Nutzungsbedingungen

- Vorhör-Links und Cover nur als Verweis (keine Kopie der Audiodaten).
- SonoVault-Einträge: höchstens 30 Tage, nie exportiert (#258) – sie lassen sich **nicht** als Idee merken, oder nur
  ohne SonoVault-Felder (siehe I6).
- Beatport-Konto wird nur bei „Als Beatport-Playlist“ und nur auf Klick verändert.

## 7. Tests (geplant)

Unit: Übernahme aus Entdecken (keine Doppelten, `entdecken.json` unverändert), Status-Erkennung über Käufe und
Bibliothek, Verschieben/Kopieren, Export. Oberfläche: Seite „Ideen“, „Idee merken ▸“ aus Entdecken, Zahl in der
Seitenleiste, Übersetzungen.

## 8. Entscheide (freigegeben vom User am 27.10.2026, 00:35)

| Nr. | Frage | Entscheid |
|---|---|---|
| I1 | Wandert ganz Entdecken ins Modul IDEE oder bleibt Entdecken eine eigene Quellen-Seite? | **Entdecken bleibt eigene Seite** (#333, zuoberst) als Quelle; nur das Merken wandert nach IDEE |
| I2 | Datenmodell | **Variante B** – Wunschlisten als Playlists im Ordner „Ideen“ |
| I3 | Was passiert mit dem Filter „Gemerkt“ in Entdecken? | bleibt vorerst als Ansicht, Einträge zeigen „in Ideen“; nach einer Version entfernen |
| I4 | Name des Menüpunkts | „Ideen“ (Seitenleiste nach „Entdecken“) |
| I5 | Wunschliste als Beatport-Playlist (`TagStudio_WISH_<Liste>`) | ja, in Phase 2b, **nur auf Klick** je Liste (nur Titel mit Beatport-ID, kein automatischer Abgleich), gleiche Einstellung wie #334 |
| I6 | SonoVault-Vorschläge als Idee merken | nur Künstler/Titel/Mix ohne SonoVault-Felder, wie ein Eintrag von Hand |

Zusätzlich bestätigt: je Eintrag **Notiz**, **Status** (automatisch aus dem Käufe-Abgleich), **Quelle/Link** und
**Vorhören** direkt in „Ideen“ (wie in 4.1 beschrieben).

## 9. Phasen

1. **Konzept** (dieses Dokument) – Entscheide I1–I6 freigegeben (27.10.2026).
2. **Phase 2a:** Seite „Ideen“, Wunschlisten, „Idee merken ▸“ aus Entdecken, Übernahme der gemerkten Einträge,
   Status Idee/Kaufen/Verworfen, Erkennung gekauft/in Bibliothek, Export.
3. **Phase 2b:** „Als Beatport-Playlist“, „Als Playlist übernehmen“, Einträge von Hand bzw. aus Text einfügen.
