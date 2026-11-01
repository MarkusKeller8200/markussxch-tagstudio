# Konzept: Warenkorb – Titel sammeln, auf Käufe prüfen, an den Shop senden (#420–#425)

Stand: 2026-11-01 (4.15.0, Meilenstein #32) · Status: **IN ARBEIT** – Entscheide W1–W3 vom User (01.11.2026, 16:20).

## 1. Ziel

Wunsch des Users (01.11.2026, 16:12): ein Menüpunkt **„Warenkorb“** zwischen „Ideen“ und „Einkäufe“. Alles, was
gekauft werden soll, wird in Warenkörben zusammengefasst. Am Ende steht eine **Einkaufsliste**, die an den Shop geht –
zuerst **Beatport**, später iTunes und weitere. Bereits gekaufte Titel werden erkannt und aus der Einkaufsliste
genommen, damit nichts doppelt gekauft wird. Die Körbe bleiben mit ihrem Zustand **Offen** oder **Gekauft** in der
**Historik**.

**Nichtziele:** kein Bezahlen und kein Kauf durch TagStudio; kein Zugriff auf den Warenkorb der Shop-Webseite
(undokumentiert, siehe W2).

## 2. Ablauf

```
Ideen (Wunschlisten) ─┐
Liste einfügen ───────┼──► Warenkorb (offen) ──► „Bei Beatport suchen“ (Titel ohne Beatport-ID zuordnen)
URL einer Plattform ──┘          │
                                 ├──► „Auf Käufe prüfen“ (Einkäufe aktualisieren, Bibliothek) → „Gekaufte entfernen“
                                 ├──► „An Beatport senden …“ → Playlist TagStudio_CART_<Korb> (nur auf Klick)
                                 │        └─ auf beatport.com: „Alle in den Warenkorb“ → bezahlen
                                 ▼
                        Einkäufe-Abgleich erkennt die Käufe → Korb „Gekauft“ (Historik)
```

## 3. Entscheide

| Nr. | Frage | Entscheid (User 01.11.2026, 16:20) |
|---|---|---|
| W1 | Meilenstein | neuer Meilenstein **#32 „4.15.0 – Warenkorb“** |
| W2 | Übergabe an Beatport – die offizielle API v4 (117 Endpunkte, Stand 25.10.2026) hat **keinen** Warenkorb-Endpunkt | eigene **Beatport-Playlist `TagStudio_CART_<Korb>`** über die offizielle API (`/my/playlists/`, wie #334); auf beatport.com mit „Alle in den Warenkorb“ übernehmen. Nur auf Klick, nur mit der Plugin-Einstellung „Playlists in Beatport“ |
| W3 | Wann ist ein Korb „gekauft“? | **automatisch**, wenn alle Titel der Einkaufsliste über „Einkäufe“ als gekauft erkannt sind, **und von Hand** („Als gekauft abschliessen“) |

Reihenfolge der Quellen (User): zuerst die **einfache Liste** (z. B. kopierte Trackliste von 1001Tracklists), dann
aus den Ideen, danach per URL einer Streaming-Plattform (#424).

## 4. Seite „Warenkorb“ (#420)

- Seitenleiste zwischen „Ideen“ und „Einkäufe“, Zahl = offene Titel in offenen Körben (noch nicht gekauft).
- Links die Körbe in drei Gruppen: **Offen**, **Gekauft** (Historik, mit Datum) und **Archiv** (eingeklappt).
  „＋“ legt einen neuen Korb an; Rechtsklick: umbenennen, als gekauft abschliessen / wieder öffnen, archivieren /
  zurückholen, als Excel/CSV.
- Rechts die Titel: Künstler, Titel (Mix), Shop-Treffer (Beatport-ID mit Link, „unsicher“ zur Auswahl, „nicht bei
  Beatport“), Quelle, Status, Notiz. Filter: **Einkaufsliste** (offen), Gekauft, In Bibliothek, Entfernt, Alle.
- Kopfzeile: „+ Hinzufügen ▾“, „Bei Beatport suchen“, „Auf Käufe prüfen“, „Weitere ▾“, **„An Beatport senden …“**.

### Status eines Titels

| Status | Bedeutung | Quelle |
|---|---|---|
| offen | steht auf der Einkaufsliste | Standard |
| gekauft | steht unter „Einkäufe“ (gleiche Beatport-ID, sonst Künstler + Titel + Mix wie #291) | bei jeder Anzeige ermittelt |
| in Bibliothek | Datei vorhanden (letzte Prüfung) | „Auf Käufe prüfen“ |
| entfernt | aus der Einkaufsliste genommen – von Hand oder „bereits gekauft“ | gespeichert, bleibt sichtbar |

Entfernte Titel bleiben im Korb (Historik) und lassen sich zurückholen; Rückgängig für jede Änderung.

## 5. Titel hinzufügen (#421, #424)

1. **Liste einfügen:** je Zeile „Künstler – Titel (Mix)“ – Nummern, Zeitmarken, „w/“, Label in eckigen Klammern fallen
   weg, „ID – ID“ wird gezählt, aber nicht übernommen (`playlists.parse_tracklist`, wie Playlists und Ideen).
2. **Aus den Ideen:** markierte Einträge einer Wunschliste „In den Warenkorb ▸“ (Korb wählen oder neu). Beatport-ID,
   Link und ISRC werden übernommen; die Idee bekommt den Status „Kaufen“.
3. **Von Hand:** Künstler, Titel, Mix, Link.
4. **Per URL** (#424, später): Link einer Playlist bzw. eines Titels von Beatport, Spotify, SoundCloud über das Plugin
   lesen (nur lesend).

Doppelte (gleiche Beatport-ID bzw. Künstler + Titel + Mix) werden gemeldet und nicht doppelt aufgenommen.

## 6. Prüfung auf bereits gekaufte Titel (#422)

- **„Auf Käufe prüfen“** (Hintergrund-Vorgang): zuerst die Einkäufe der bereiten Stores aktualisieren (wie
  Einkäufe › „Aktualisieren“, nur neue Käufe), dann jeden Titel des Korbs mit „Einkäufe“ abgleichen und mit der
  Bibliothek (`playlists.match_ref`, sichere Treffer). Ergebnis: *gekauft* (Kaufdatum), *in Bibliothek*, *offen*.
- **„Gekaufte entfernen (n)“** setzt gekaufte und in der Bibliothek vorhandene Titel auf *entfernt – bereits
  gekauft* bzw. *entfernt – in Bibliothek*; vorher Rückfrage, Rückgängig möglich.
- Vor dem Senden an Beatport wird automatisch geprüft; gekaufte Titel werden nie gesendet.

## 7. Beatport (#423)

- **„Bei Beatport suchen“:** Titel ohne Beatport-ID werden über die Katalogsuche zugeordnet (Plugin-Funktion
  `store_search(ctx, refs)`, gleiche Bewertung wie die Online-Metadaten: ISRC, sonst Suche nach Künstler + Titel + Mix,
  Punktzahl `score`). Ab 0,80 sicher (übernommen), ab 0,62 unsicher (bis drei Kandidaten zur Auswahl), darunter
  „nicht bei Beatport“. Nur lesend.
- **„An Beatport senden …“:** Vorschau (Name `TagStudio_CART_<Korb>`, n Titel; ohne gekaufte, entfernte und Titel
  ohne Beatport-ID), dann `store_playlist_put(name, ids, replace=True)`: Playlist anlegen bzw. auf genau die
  Einkaufsliste bringen (Titel, die nicht mehr dazugehören, werden aus **dieser** Playlist genommen). Nur auf Klick, nur
  mit der Einstellung „Playlists in Beatport“; verändert nur Playlists mit dem Präfix `TagStudio_`. Danach
  „Playlist bei Beatport öffnen“; der Korb merkt sich Playlist, Zeitpunkt und Anzahl.
- Kauf und Bezahlung geschehen auf beatport.com. Danach erkennt „Einkäufe“ die Käufe, der Korb wird „gekauft“.

## 8. Datenmodell

**Eigener Speicher** `~/TagStudio/Warenkorb/warenkorb.json` (je Profil, atomar) statt Playlists wie bei den Ideen:
Ein Korb ist ein Einkaufsvorgang mit Zustand und Historik, keine Playlist – er soll weder unter „Playlists“ noch als
M3U8 erscheinen. Teil der Sicherung der Programmdaten (#402, Teil „Warenkorb“).

```json
{"format": 1,
 "carts": {"c_ab12cd34ef56": {
   "id": "c_ab12cd34ef56", "name": "Warenkorb 1. Nov.", "store": "beatport", "created": 1761990000,
   "status": "open | bought", "closed": 0, "closed_by": "auto | hand", "auto": true, "archived": 0, "checked": 0,
   "pushed": {"beatport": {"id": "123", "name": "TagStudio_CART_…", "url": "https://…", "at": 0, "count": 12}},
   "items": [{"artist", "title", "mix", "isrc", "dur", "url", "note", "src": "text | ideas | manual | url",
              "added": 0, "sid": "Beatport-ID", "match": {"state": "sure | unsure | none", "score": 0.0,
              "cands": [{"id", "artist", "title", "mix", "url", "score"}]},
              "lib": "Pfad (letzte Prüfung)", "removed": {"why": "hand | bought | lib", "at": 0}}]}}}
```

- *gekauft* wird bei jeder Anzeige aus `kaeufe.json` ermittelt (`discover.mark_purchased`); *in Bibliothek* stammt
  aus der letzten Prüfung.
- Automatisch „gekauft“ (W3): offener Korb mit mindestens einem Titel auf der Einkaufsliste, alle davon gekauft →
  `status = bought`, `closed`, `closed_by = auto`. „Wieder öffnen“ setzt `auto = false`, damit der Korb nicht sofort
  wieder schliesst; neue Titel setzen `auto` wieder.
- Logik in `carts.py` (nur Standardbibliothek, ohne Netz), Session-Teil `session_carts.py` (`CartsMixin`),
  Oberfläche `web/carts.js`.

## 9. Rechte und Nutzungsbedingungen

- Beatport-Konto: nur die eigene Playlist `TagStudio_CART_<Korb>`, nur auf Klick (wie #334/#335, I5).
- Keine Zugangsdaten im Korb; Links nur `https://`.
- Spotify (#424): nur lesen, Developer Terms beachten.

## 10. Tests

Unit (`tests/test_carts.py`): Liste einfügen, Doppelte, aus Ideen, Status gekauft/in Bibliothek/entfernt, automatisch
gekauft und Wieder öffnen, Rückgängig, Export, Beatport-Zuordnung mit Plugin-Attrappe, Senden ohne gekaufte.
Oberfläche (`test_browser_ui.test_carts_page`): Menüpunkt zwischen Ideen und Einkäufe, Korb anlegen, Liste einfügen,
Prüfung mit „Einkäufe“, Gekaufte entfernen mit Rückfrage, Historik, aus Ideen in den Warenkorb.

## 11. Phasen

1. **4.15.0:** #420 Seite und Historik, #421 Liste einfügen und aus Ideen, #422 Prüfung auf Käufe, #423 Beatport
   zuordnen und senden.
2. **4.15.0 (danach):** #424 Titel per URL einer Plattform.
3. **Später:** #425 weitere Shops (iTunes Store, Traxsource, Bandcamp, Beatsource, Amazon) – je Shop prüfen, ob es
   eine erlaubte Schnittstelle gibt, sonst Einkaufsliste mit Links.
