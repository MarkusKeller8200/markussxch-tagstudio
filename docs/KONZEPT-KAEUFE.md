# Konzept: Käufe – gekaufte Titel aller Stores (#285)

> Wunsch des Users 25.10.2026 (02:26): eigenes Modul / Menüeintrag für gekaufte Titel, gesammelt nach Verkaufsstelle
> (Store) – vorerst nur Beatport. Tabelle mit Titel, Interpret, Mix, Länge, Tonart, BPM, Link zur Plattform,
> Katalognummer, Store und – wenn möglich – Kaufdatum. Aktualisieren gleicht neue Käufe ab, Abgleich mit der
> Bibliothek, fehlende Titel in den Eingangsordner (`00_New`) laden.

## 1. Seite „Käufe“

- Seitenleiste nach „Playlists“, Zahl = fehlende Titel.
- Tabelle (sortierbar per Klick auf die Spalte, fehlende Werte immer unten): Status, Titel, Interpret, Mix, Länge,
  Tonart (Camelot-Badge), BPM, Katalognummer, Store, Kaufdatum (sonst grau „zuerst gesehen“), Link ↗.
- Filter: Suche (Titel, Interpret, Mix, Katalognr., Label, Release, ISRC), Store, Status (alle, in Bibliothek, im
  Eingang, unklar, fehlt) mit Zählern.
- Auswahl mit Häkchen; „Fehlende herunterladen (n)“ bzw. „Markierte herunterladen (n)“; Rechtsklick: beim Store öffnen,
  Dateiordner, „Online suchen ›“, Herunterladen.
- „↻ Aktualisieren“ = Stores abfragen + abgleichen; „Abgleichen“ = nur Bibliothek neu prüfen.
- Ziel für Downloads: eigene Wahl („Ordner …“, cfg `purch_dest`), sonst Eingang von „Vorbereiten“, sonst
  `<Basisordner>/00_New` (wird angelegt, wenn der Basisordner existiert).

## 2. Status

| Status | Bedeutung |
|---|---|
| in Bibliothek | sicherer Treffer in der Bibliothek (gleiche ISRC bzw. Künstler + Titel + Mix, wie `playlists.match_ref`) |
| im Eingang | Treffer bzw. heruntergeladene Datei im Eingangsordner |
| unklar | ähnlicher Treffer (anderer Mix, ähnlicher Titel …) – Grund als Tooltip |
| fehlt | kein Treffer – herunterladen |

Vorbestellungen werden angezeigt, aber nie heruntergeladen.

### Abgleich: doppelte Bibliothek, Hinweis, Zuordnen (#290)

- Dieselbe Datei unter einem zweiten Pfad (gleicher Dateiname + gleiche Grösse, `playlists.LibIndex.dupes`) zählt
  nur einmal – sonst wäre jeder Titel „unklar – mehrere Treffer“, wenn Tagger-Standardordner, Bibliothek aus
  „Vorbereiten“ und `01_Library` dieselbe Sammlung über verschiedene Pfade zeigen. Wirkt auch beim Playlist-Abgleich.
- Zeile „Verglichen mit …“ (Ordner, Dateien, zusammengefasste Doppelte mit Beispielen im Tooltip), Spalte „Hinweis“.
- „Zuordnen …“ (`Store.link`, Feld `linked`): bleibt bei Abgleich und Aktualisieren, „Zuordnung aufheben“.

## 3. Technik

- **`purchases.py`**: Speicher `~/TagStudio/Käufe/kaeufe.json` (je Profil, atomar), `clean_item`, `Store.merge`
  (neue Käufe zuführen; bekannte behalten zuerst gesehen, Status, Datei, Download, Kaufdatum), `Store.match`
  (Abgleich mit `playlists.LibIndex` der Bibliothek plus Eingangsordner), `Store.set_file`.
- **`session_purchases.py`** (`PurchasesMixin`): `purch_state`, `purch_set_dest`, `start_purch_refresh`,
  `start_purch_match`, `start_purch_download` (Hintergrund-Vorgänge). Bibliothek = `_pl_lib_roots()` (Tagger-Standard,
  Bibliothek aus „Vorbereiten“, `01_Library`) mit Listen-Cache, geladene Tagger-Titel zuerst.
- **Plugin-Rahmen**: `store_purchases(ctx)` → `{"name", "items": [{id, title, mix, artist, dur, key, bpm, catalog,
  isrc, label, release, genre, url, bought, preorder, dl}]}` und `store_download(ctx, items, dest)` →
  `{"files": {id: [Pfade]}, "failed": [Text]}`; optional `ready(ctx)`. `Manager.store_sources()`.
- **Offizielle Doku (User 25.10.2026):** Käufe = `GET /v4/my/downloads/` (kein `/my/library/`), Filter u. a.
  `purchase_date` (Bereich `JJJJ-MM-TT:`), `received_status`, `isrc`, `catalog_number`; Unterpunkte nur `encode-status`
  und `facets`. TagStudio holt deshalb nach dem ersten Mal nur Käufe ab dem letzten Kaufdatum minus 3 Tage
  (`store_purchases(ctx, since)`), alle 30 Tage oder mit „Alle neu holen“ die ganze Liste (`stores[…].full_at`).
- **OpenAPI-Beschreibung gelesen (25.10.2026, 117 Endpunkte, `/v4/swagger-ui/json/`):** Ein Kauf ist
  `TrackDownloadList` mit `purchase_date` (date-time), `order_item_download_id`, `received_status`, `pre_order`,
  `audio_format`, `release` (nur Name), Titelangaben, **ohne** ISRC, Katalognummer, Label → TagStudio ergänzt sie
  gesammelt über `/v4/catalog/tracks/?id=1,2,…` (je 100). **Kein Download-Endpunkt** in der offiziellen API (weder
  `my` noch `catalog`; `audio-files` ist für Labels). **Entscheid User 25.10.2026 (03:42):** Variante 1 – der
  Download versucht weiter die undokumentierten Wege (#117); findet er keine Adresse, meldet die Seite „Selbst
  herunterladen“ (Variante 2) mit Knopf zur Download-Seite `https://www.beatport.com/library/downloads`: dort in den
  Download-Ordner laden, in „Vorbereiten“ „Abholen“, hier „Abgleichen“ (`store_download` → `manual`).
- **#292 (Plugin 1.4):** Hinweis User 25.10.2026 04:18 (Entwicklerwerkzeuge auf beatport.com): die Webseite lädt über
  `GET /v4/catalog/tracks/purchase-download/?order_item_download_id=<id>` mit Bearer-Token und erhält eine signierte
  Datei-Adresse. Dieser Weg steht jetzt zuerst in `download_candidates`; `order_item_download_id` liefert das offizielle
  `/my/downloads/`. Offen: ob das Token des eigenen API-Zugangs dafür zugelassen ist (Beta-Test). Jeder Abruf zählt als
  Download-Versuch (`order_item_download_try_count`).
- **#295 (Plugin 1.5), Wunsch User 11:05:** Das Protokoll zeigte `purchase-download: HTTP 403` mit dem Token des
  eigenen API-Zugangs. Darum Sitzungs-Anmeldung nur für den Download: `store_download` meldet `need_login`, wenn
  `purchase-download` 401/403 liefert (oder niemand angemeldet ist); die Seite zeigt „Anmelden für den Download“,
  `store_login` nutzt den Ablauf der Webseite (`/auth/login/` → `/auth/o/authorize/` → Code → Token, wie `login()`),
  hält den Token in `_SESSION` (nur Speicher, `SessionClient` erneuert ohne zu speichern) und die Seite lädt sofort
  erneut. Passwort wird nie gespeichert, `token.bin`/`app.bin` bleiben unverändert. Ob Beatport mit diesem Token
  lädt, zeigt der Beta-Test; sonst bleibt Variante 2.
- **Beatport-Plugin 1.2**: nutzt die bestehende inoffizielle Abfrage der Käufe (`/my/downloads/` u. a., #117) und den
  Download (`resolve_download`, `fetch_file`, merkt geladene in `geladen.json`). Kaufdatum aus bekannten Feldnamen
  (`purchase_date`, `order_date`, `created` …, auch aus der Bestellung um den Titel); fehlt es, stehen die Feldnamen im
  Protokoll. Die Aktionen „Gekaufte Titel abgleichen …“ und „Fehlende Käufe herunterladen …“ bleiben bestehen.

## 3a. Entdecken ↔ Käufe (#291)

- Beim Anzeigen von „Entdecken“ werden alle Vorschläge mit `kaeufe.json` abgeglichen (`discover.mark_purchased`):
  gleiche Beatport-ID (`beatport:<id>`) oder gleicher Künstler (einer reicht) + Titel; haben beide einen Mix, muss er
  gleich sein („Original Mix“ = ohne Mix). Treffer bekommen `purchased` (Kaufdatum) – nur angezeigt, nicht gespeichert,
  damit spätere Käufe sofort und ohne neue Suche markiert sind. Filter „Gekauft“ = Status gekauft oder `purchased`.
- Der Käufe-Speicher lädt neu, wenn `kaeufe.json` von aussen geändert wurde (Änderungszeit).
- „Gefolgt“: `follow.bp` merkt, welche Künstler/Labels von Beatport übernommen wurden (Anzeige „BP“); Entfernen in
  TagStudio ändert bei Beatport nichts (`POST /my/beatport/` und `delete` werden nie benutzt).
- „Leeren …“ (`discover.clear`) behält gemerkte und gekaufte Einträge. „Ähnliche Künstler“ über Deezer
  (`/artist/{id}/related`), „My Beatport“-Feed über `/my/beatport/tracks/` (Antwort ohne festes Schema: Einträge
  direkt oder in `track`).

## 4. Später

- Weitere Stores als Plugins: iTunes Store, Amazon, Traxsource, Bandcamp, Beatsource – soweit es eine erlaubte
  Schnittstelle oder einen Export (z. B. Kaufhistorie als CSV) gibt; Prüfung in `KONZEPT-DJPLATTFORMEN.md`.
- Import einer Kaufliste aus Datei (CSV) für Stores ohne Schnittstelle.
