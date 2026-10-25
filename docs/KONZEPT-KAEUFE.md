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
  `my` noch `catalog`; `audio-files` ist für Labels). Der Download nutzt weiter die undokumentierten Wege (#117) –
  Entscheid des Users offen, ob stattdessen die Download-Seite von Beatport geöffnet wird.
- **Beatport-Plugin 1.2**: nutzt die bestehende inoffizielle Abfrage der Käufe (`/my/downloads/` u. a., #117) und den
  Download (`resolve_download`, `fetch_file`, merkt geladene in `geladen.json`). Kaufdatum aus bekannten Feldnamen
  (`purchase_date`, `order_date`, `created` …, auch aus der Bestellung um den Titel); fehlt es, stehen die Feldnamen im
  Protokoll. Die Aktionen „Gekaufte Titel abgleichen …“ und „Fehlende Käufe herunterladen …“ bleiben bestehen.

## 4. Später

- Weitere Stores als Plugins: iTunes Store, Amazon, Traxsource, Bandcamp, Beatsource – soweit es eine erlaubte
  Schnittstelle oder einen Export (z. B. Kaufhistorie als CSV) gibt; Prüfung in `KONZEPT-DJPLATTFORMEN.md`.
- Import einer Kaufliste aus Datei (CSV) für Stores ohne Schnittstelle.
