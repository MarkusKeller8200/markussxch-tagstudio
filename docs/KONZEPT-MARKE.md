# Konzept: Marke TagStudioSX

Status: **freigegeben** (2026-11-09) – Meilenstein „5.0.0 – TagStudioSX (Rebrand)“, Issues #461–#469.
Grundlage (eine Quelle, hier nicht kopiert): Repo [MarkusKeller8200/markussxch](https://github.com/MarkusKeller8200/markussxch),
Ordner `docs/brand/` – CI-Manual v1.0, Markenkonzept v1.0, Markenfortschreibung v1.1.

## Ziel

TagStudio heisst ab Version **5.0.0** **TagStudioSX** und tritt als Produkt der Dachmarke **MarKusSXCH** auf. Geändert wird
der **sichtbare** Auftritt. Technische Namen bleiben, damit Daten, Tags, Plugins und Updates ohne Umzug weiter funktionieren
(CI-Manual § 10: „nicht API-Namen, GitHub-Repositories, URLs, Datenmodelle oder Musikmetadaten“).

## Entscheide des Users (09.11.2026)

| | Entscheid |
|---|---|
| E1 | Programmdatei und App heissen `TagStudioSX.exe` / `TagStudioSX.app` |
| E2 | Download-Dateien `TagStudioSX-X.Y.Z-Windows-Setup.exe`, `TagStudioSX-X.Y.Z-macOS-….dmg` |
| E3 | Name überall **TagStudioSX**; Herkunft über die Signatur „Developed by MarKusSXCH“ (nicht mehr „MarKusSXCH TagStudio“) |
| E4 | Version **5.0.0 „Rebrand“** |
| E5 | Neues Signet (App-Symbol) – Vorschlag, nach Freigabe auch ins CI (Repo markussxch, per Pull Request) |
| E6 | Produktakzent Blau; Kontrast vorgängig geprüft (siehe unten) |
| E7 | Klassische tkinter-Oberfläche: nur Fenstertitel |

## Was sich ändert

- Wortmarke **TagStudioSX**: `T` violett · `ag` neutral · `S` orange · `tudio` neutral · `SX` blau; Schrift fett (600–700),
  keine Verläufe/Schatten. Eine zentrale Funktion `brandWordmark()` in `web/app.js`; `aria-label="TagStudioSX"`, die
  Segmente sind für Screenreader ausgeblendet.
- Farben als Tokens `--brand-violet/-orange/-blue/-neutral/-muted` (Werte CI-Manual § 2, hell und dunkel).
- Bedienelemente im Produktblau (`--acc`), Statusfarben bleiben.
- Alle sichtbaren Texte, Fenstertitel, Installer, DMG, Release-Titel, Doku, Webseite: TagStudioSX.
- Signatur „Developed by MarKusSXCH“ und Claim „Music Management & DJ Library“ in Hilfe › Über, Webseite, README.

## Was bleibt (technisch)

| Bereich | bleibt | Grund |
|---|---|---|
| Tags in Musikdateien | `TXXX:TAGSTUDIO_ADDED/EDITED/BEATGRID`, GEOB „TagStudio Overview“, FLAC-Vendor „TagStudio“ | Musikmetadaten; ältere Versionen und andere Programme finden sie sonst nicht |
| Datenordner | `~/TagStudio`, `~/.tagstudio.json`, Profile `TagStudio-Profile`, Musik-/Cloud-Ordner `TagStudio` | kein Umzug, keine Migration |
| Installation | Windows-AppId, Mutex `MarKusSXCH-TagStudio`, macOS-Bundle-ID `ch.markussxch.tagstudio`, Installationsordner bestehender Installationen | Update über die bestehende Installation, Schlüsselbund-Zugänge |
| Repo, Adressen | `markussxch-tagstudio`, GitHub-Pages-Adresse | Markenkonzept § 5 |
| Code | Modulnamen, Plugin-Schnittstelle, Umgebungsvariablen `TAGSTUDIO_*`, Kommentare | keine Bedeutung für Nutzer |

## Farben und Kontrast (E6)

Geprüft nach WCAG 2.1 (Text 4,5:1, Bedienelemente 3:1) gegen die App-Hintergründe:

| Farbe | Hintergründe der App | Schrift auf der Farbe | Verwendung |
|---|---|---|---|
| Blau hell `#007EBB` (CI) | 3,9–4,5:1 | Weiss 4,47:1 | **nur** Wortmarke/Markenfläche (grosse, fette Schrift ≥ 3:1) |
| Blau hell funktional `#00699E` | 5,2–6,0:1 | Weiss 5,98:1 | `--acc` hell: Knöpfe, Links, Fokus (CI § 4 „funktionale Abstufung“) |
| Blau dunkel `#32B8F2` (CI) | 6,8–8,4:1 | `#0E1430` 7,99:1 | `--acc` dunkel und Wortmarke |
| Orange `#FF8A00` | hell 2,0–2,4:1, dunkel 6,5–8,1:1 | – | nur Wortmarke/Signet, nie als einziger Hinweis |
| Violett `#7952B3` / `#B59AFF` | 4,9–5,7:1 / 6,6–8,2:1 | – | Wortmarke, ergänzender Akzent |

Das `S` der Wortmarke bleibt im hellen Modus offiziell orange (CI § 7); lesbar über Grösse und Gewicht, der Name steht
zusätzlich im `aria-label`.

## Updates von 4.x auf 5.0.0

- **Windows:** gleiche AppId → Update in den bisherigen Ordner. Der Installer entfernt `TagStudio.exe` und die alten
  Verknüpfungen „MarKusSXCH TagStudio“ und legt „TagStudioSX“ an. Der Updater von 4.16 startet nach dem Installieren die alte
  `TagStudio.exe` – die gibt es nicht mehr; deshalb startet der Installer bei diesem Übergang `TagStudioSX.exe` selbst.
- **macOS:** Der Updater von 4.16 erwartet `TagStudio.app` im DMG und bricht sonst ohne Schaden ab (alte App bleibt).
  5.0.0 einmalig von Hand installieren (DMG → Programme), danach `TagStudio.app` löschen. Ab 5.0.0 ersetzt der Updater
  `TagStudio.app` oder `TagStudioSX.app` durch `TagStudioSX.app`.
- Der Updater erkennt Installer nur an Endung und Prozessor – neue Dateinamen sind ohne Anpassung kompatibel.

## Signet (E5)

Vorschlag in #465 (drei Entwürfe). Nach Freigabe: `web/icon.png`/`icon.ico`/`.icns`, Favicon und Vorschaubild der Webseite,
Ablage als SVG; Aufnahme ins CI per Pull Request im Repo markussxch.
