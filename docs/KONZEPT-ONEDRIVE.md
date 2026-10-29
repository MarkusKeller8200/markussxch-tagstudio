# Konzept: OneDrive als persönlicher Cloud-Speicher von TagStudio

> Stand 29.10.2026 (17:40) – Status **NICHT WEITER VERFOLGT** (Entscheid User 17:35: bei OD1 bleiben, keine
> TagStudio-App, kein Ausbau des API-Abgleichs; stattdessen Sicherung der Programmdaten in den Cloud-Ordner, #402).
> Bleibt als Referenz. #401 (Sicherheit) gilt unabhängig davon. Neuer Weg ab 17:58: Umschalter Kontoart (#405),
> siehe [KONZEPT-CLOUD.md](KONZEPT-CLOUD.md) §4c.
> Auftrag User 29.10.2026, 17:23. Issues: [#400](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/400)
> (einfache Anmeldung) · [#401](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/401) (Token bei
> Umleitungen, Sicherheit). Baut auf [KONZEPT-CLOUD.md](KONZEPT-CLOUD.md) (Weg 2, Entscheide C1–C4) und dem Plugin
> `onedrive` 1.x auf. Angaben zu Microsoft geprüft gegen Microsoft Learn am 29.10.2026 (Quellen in Abschnitt 13).

## 1. Ziel und Abgrenzung

**Anwendungsfall:** TagStudio nutzt das OneDrive des Users als **eigenen Cloud-Speicher** – für die Ordner-Rollen
Playlists und Export sowie die Programmdaten-Teile (Playlists-Speicher, Käufe, Entdecken, Einstellungen ohne
Zugangsdaten), damit zwei Rechner (Windows ↔ Mac) denselben Stand haben. Abgleich, Konflikte und Löschregeln bleiben
wie in KONZEPT-CLOUD §2–4a (`cloudsync.py`).

| | Beschlossen / Vorgabe | Quelle |
|---|---|---|
| Konten | **Nur private Microsoft-Konten** (outlook.com, hotmail.com, live.com …). Keine Geschäfts- und Schulkonten. | User 29.10.2026, 04:02 |
| Ablauf | „Anmelden …“ → Browser → Anmeldung bei Microsoft → Zustimmung „TagStudio vertrauen“ → zurück in TagStudio. | User 29.10.2026, 04:02 |
| Passwort | TagStudio sieht und speichert das Microsoft-Passwort **nie** (Anmeldung nur auf der Microsoft-Seite). | KONZEPT-CLOUD §4 |
| Musik | Nicht über die API – Musik bleibt beim Desktop-Client (Weg 1). | C2 |

**Nicht Ziel:** OneDrive als Dateibrowser für beliebige Ordner, Freigaben an andere, SharePoint, Geschäftskonten,
eingebettetes Anmeldefenster in TagStudio.

## 2. Ausgangslage (Plugin `onedrive` 1.x, Stand 4.13.0)

- Eigene App des Users in Microsoft Entra (Client-ID im Plugin, C4), Endpunkt `…/common/…` (privat **und**
  geschäftlich), Scopes `Files.ReadWrite User.Read offline_access` – Zugriff auf das **ganze** OneDrive.
- Rückleitung `http://localhost:8767/callback` (fester Port), PKCE (S256) und `state` in `oauthkit.App`.
- Dateien unter `/TagStudio/<Rolle>` im Stamm des OneDrive; Liste rekursiv über `…/children`, Revision = `cTag`.
- Hochladen ≤ 4 MB direkt (`PUT …:/content`), grösser über Upload-Sitzung (Teile à 3,2 MB, Vielfaches von 320 KiB).
- Token verschlüsselt (`servicekit.save_keys` → `secretstore`: DPAPI bzw. macOS-Schlüsselbund), Erneuerung vor
  Ablauf bzw. einmal bei 401, 429 wird nicht wiederholt (`cloudkit.request`).

**Lücken:** ohne eigene App keine Anmeldung (Hinweis „Zugangsdaten deiner App eintragen“); Zugriff breiter als nötig;
fester Port; Erneuerung nicht gegen gleichzeitige Aufträge gesperrt; jeder Abgleich listet alles neu; kein Schutz vor
Überschreiben zwischen Plan und Hochladen; **Token wird beim Herunterladen an den Download-Host mitgesendet (#401).**

## 3. Voraussetzung: die App „TagStudio“ bei Microsoft (einmalig, Entwickler)

Damit sich Nutzer ohne eigene App anmelden können, braucht es **eine** App-Registrierung „TagStudio“, deren
Client-ID im Plugin als Vorgabe steht. Die Client-ID eines öffentlichen Clients ist **kein Geheimnis** (sie steht in
jeder Anmeldeadresse); ein Secret gibt es nicht.

**Hürde (geklärt 29.10.2026):** Seit Juni 2024 müssen neue App-Registrierungen in einem Verzeichnis (Tenant) liegen; ein
reines Privatkonto kann keine App mehr anlegen. Wege laut Microsoft: Verzeichnis über eine Azure-Anmeldung (laut
Nutzerberichten mit Kreditkarte zur Identitätsprüfung; Entra-ID-Grundfunktionen kosten nichts) oder über das
M365 Developer Program. Das Verzeichnis gehört dem Entwickler; die **Nutzer** brauchen kein Verzeichnis. → **OD1**.

Einstellungen der Registrierung:

| Einstellung | Wert | Warum |
|---|---|---|
| Name | `TagStudio` | erscheint im Zustimmungsdialog **und** als Ordnername `Apps/TagStudio` |
| Unterstützte Kontotypen | **Nur persönliche Microsoft-Konten** (`signInAudience = PersonalMicrosoftAccount`) | Vorgabe User; Geschäftskonten werden von Microsoft abgewiesen |
| Plattform | „Mobile Anwendungen und Desktopanwendungen“ (öffentlicher Client) | kein Secret, PKCE |
| Umleitungs-URI | `http://localhost/callback` | bei `localhost` ignoriert Microsoft den Port → TagStudio darf einen freien Port wählen |
| Öffentliche Clientflows | Ja | Desktop-App ohne Secret |
| API-Berechtigungen (delegiert, Microsoft Graph) | `Files.ReadWrite.AppFolder`, `offline_access` (+ ggf. `User.Read`, OD3) | geringste Rechte, siehe §5 |
| Branding | Logo, Startseite (GitHub-Seite), Datenschutzerklärung, Nutzungsbedingungen | Vertrauen im Zustimmungsdialog; Herausgeber bleibt ohne Verifizierung „nicht überprüft“ (OD7) |
| Manifest | `requestedAccessTokenVersion = 2` (bei privaten Konten Pflicht) | |

## 4. Anmeldung (Authorization Code Flow mit PKCE)

```
TagStudio                          Browser                         login.microsoftonline.com/consumers
   │ 1. verifier, challenge, state     │                                      │
   │ 2. Loopback-Server 127.0.0.1+[::1]:<freier Port>                         │
   │ 3. öffnet Anmeldeadresse ────────▶│ ── GET /oauth2/v2.0/authorize ──────▶│
   │                                   │◀─ Anmeldung (Passwort/Passkey/2FA) ─│
   │                                   │◀─ Zustimmung „TagStudio vertrauen“ ─│
   │◀─ 4. GET /callback?code&state ────│                                      │
   │ 5. state prüfen, Seite „fertig“   │                                      │
   │ 6. POST /oauth2/v2.0/token (code, verifier, redirect_uri, client_id) ──▶│
   │◀──────────── access_token, refresh_token, expires_in, scope ────────────│
   │ 7. Konto prüfen (§4.3), Token verschlüsselt speichern                    │
```

### 4.1 Adressen und Parameter

- Autorisierung: `https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize`
- Token: `https://login.microsoftonline.com/consumers/oauth2/v2.0/token`
- `client_id` (Vorgabe TagStudio-App bzw. eigene App), `response_type=code`, `redirect_uri=http://localhost:<Port>/callback`,
  `scope=Files.ReadWrite.AppFolder offline_access`, `code_challenge_method=S256`, `code_challenge`, `state`
  (zufällig, 128 Bit), `prompt=select_account` (Konto wählbar, wenn im Browser schon ein anderes angemeldet ist).
- `consumers` statt `common`: Geschäfts- und Schulkonten kommen gar nicht erst zur Anmeldung.

### 4.2 Rückleitung

- **Freier Port** (Betriebssystem wählt, `bind(…, 0)`), damit „Port 8767 belegt“ entfällt. Zulässig, weil Microsoft
  bei `localhost` den Port nicht vergleicht. Der Server lauscht wie heute auf `127.0.0.1` **und** `[::1]` (Browser lösen
  `localhost` teils als IPv6 auf); registriert bleibt `localhost`, weil Microsoft `[::1]` als Adresse nicht unterstützt
  und `http://127.0.0.1` im Portal nur über das Manifest eintragbar ist.
- Nur der Pfad `/callback`, nur **eine** Antwort, danach Server schliessen; Wartezeit 3 Minuten, Abbruch möglich.
- `state` muss passen, sonst Abbruch (Schutz gegen untergeschobene Codes). Fehler wie `access_denied` (Zustimmung
  abgelehnt) als verständliche Meldung.
- Rückfall „Adresse einfügen“ bleibt (Firewall, Sicherheitssoftware).

### 4.3 Kontoprüfung nach der Anmeldung

`GET /me/drive?$select=id,driveType,owner,quota` (bzw. `/me/drive/special/approot`, falls `/me/drive` mit der
App-Ordner-Berechtigung nicht erlaubt ist – **ZU PRÜFEN** beim ersten echten Test):

- `driveType` muss `personal` sein, sonst Abmelden mit Hinweis „nur private Microsoft-Konten“.
- `drive.id` und Anzeigename merken (§6.1). Meldet sich später ein **anderes** Konto an, fragt TagStudio, ob der
  Abgleich-Zustand dieses Kontos verworfen werden soll (sonst würde „im Dienst gelöscht“ fälschlich gemeldet).

### 4.4 Eigene App (Erweitert)

Wer eine eigene Registrierung hat, trägt unter „Erweitert“ die Client-ID ein; sie hat Vorrang vor der Vorgabe. Gleiche
Einstellungen wie §3. Ohne Vorgabe-ID (OD1 nicht erfüllt) bleibt das der einzige Weg – dann mit besserem Hinweis
(Microsoft verlangt ein Verzeichnis) statt nur „Zugangsdaten eintragen“.

## 5. Berechtigungen (Scopes)

| Scope | Zweck | Entscheid |
|---|---|---|
| `Files.ReadWrite.AppFolder` | Lesen/Schreiben **nur** im App-Ordner `Apps/TagStudio` – gilt laut Microsoft nur für private Konten | **Vorschlag** (OD2) |
| `offline_access` | Erneuerungs-Token (sonst nach ~1 h neu anmelden) | nötig |
| `User.Read` | Anzeigename für „Angemeldet als …“ | nur falls `owner` im Drive nicht genügt (OD3) |
| ~~`Files.ReadWrite`~~ | ganzes OneDrive | nur noch für die eigene App mit altem Ordner `/TagStudio` (Übergang, OD4) |

Der App-Ordner wird beim ersten Zugriff angelegt, heisst nach dem App-Namen und kann vom User umbenannt oder
verschoben werden – TagStudio adressiert ihn immer über `special/approot`, nie über einen Pfad. Legt der User selbst
Dateien hinein, sieht TagStudio sie (die Grenze ist der Ordner, nicht die Datei); `cloudsync` beachtet weiterhin nur
die erlaubten Endungen je Teil.

## 6. Datenmodell

### 6.1 Zugang (Plugin-Schlüssel, verschlüsselt, `servicekit.save_keys`)

```json
{
  "mode": "tagstudio",                  // "tagstudio" = Vorgabe-App, "own" = eigene App
  "client_id": "",                      // nur bei mode "own"
  "token": {
    "access_token": "…", "refresh_token": "…",
    "expires_at": 1793300000.0,         // Sekunden (Unix), aus expires_in
    "scope": "Files.ReadWrite.AppFolder offline_access"
  },
  "account": {"drive_id": "…", "name": "Markus K.", "type": "personal", "since": "2026-10-29T17:40:00Z"},
  "pending": {"verifier": "…", "state": "…", "at": 1793299000.0}   // nur während der Anmeldung, max. 15 Min.
}
```

Die Vorgabe-Client-ID steht im Code (`plugins/onedrive/plugin.py`, `CFG["client_id"]`), nicht in den Schlüsseln.
Zugangsdaten gehen nie in den Einstellungs-Export, die Cloud, Protokolle oder Fehlermeldungen.

### 6.2 Ablage im OneDrive

```
Apps/TagStudio/                     ← special/approot
  Playlists/…                       ← Rolle „playlists“ (FolderPart)
  Export/…                          ← Rolle „export“
  Programmdaten/
    Playlists/…  Kaeufe/…  Entdecken/…  einstellungen.json
```

Im App-Ordner entfällt die bisherige Vorsilbe `TagStudio/`: `sync.remote` ist relativ zu `approot`
(Standard `<Rolle>` bzw. `Programmdaten/<Teil>`). Pfade werden wie heute mit `clean_path` geprüft (kein `..`, kein
führender `/`) und je Teil URL-kodiert.

### 6.3 Abgleich-Zustand (`~/TagStudio/Cloud/abgleich.json`, Erweiterung)

Je Ziel (`Teil|onedrive|Ordner`) und Datei wie heute `sha` + `rev`, neu dazu:

| Feld | Inhalt | Nutzen |
|---|---|---|
| `id` | driveItem-ID | stabile Zuordnung bei Umbenennen im Dienst |
| `etag` | eTag der letzten gemeinsamen Fassung | `If-Match` beim Hochladen (§7.3) |
| `_delta` (je Ziel) | letzter `@odata.deltaLink` | nur Änderungen abholen (§7.2) |
| `_drive` (je Ziel) | `drive_id` | anderes Konto erkennen (§4.3) |

`cTag` (Inhalt) bleibt die Revision für „dort geändert“; der `eTag` ändert sich auch bei Metadaten und dient nur
der Vorbedingung.

## 7. API (Microsoft Graph v1.0, `https://graph.microsoft.com/v1.0`)

### 7.1 Endpunkte

| Zweck | Anfrage | Hinweise |
|---|---|---|
| Konto/Kontingent | `GET /me/drive?$select=id,driveType,owner,quota` | §4.3; Kontingent in „Verbindung testen“ |
| App-Ordner | `GET /me/drive/special/approot` | legt den Ordner an; `approot` ist gross-/kleinschreibungsabhängig |
| Liste (erstmals) | `GET /me/drive/special/approot:/{ordner}:/children?$select=id,name,cTag,eTag,size,file,folder&$top=200` | rekursiv, `@odata.nextLink` |
| Änderungen | `GET /me/drive/special/approot/delta` bzw. gespeicherter `deltaLink` | §7.2, **ZU PRÜFEN** mit `AppFolder` |
| Herunterladen | `GET …/items/{id}?$select=id,cTag,@microsoft.graph.downloadUrl`, dann Download-Adresse **ohne** Token | Adresse nur Minuten gültig; §8.4 / #401 |
| Hochladen ≤ 4 MB | `PUT /me/drive/special/approot:/{pfad}:/content` (+ `If-Match`) | legt fehlende Ordner an |
| Hochladen > 4 MB | `POST /me/drive/special/approot:/{pfad}:/createUploadSession` mit `conflictBehavior` + `If-Match`, dann Teile `PUT {uploadUrl}` mit `Content-Range` | Teile Vielfaches von 320 KiB, je < 60 MiB (empfohlen 5–10 MiB); Upload-Adresse ohne Token |
| Löschen | `DELETE /me/drive/items/{id}` (+ `If-Match`) | nur nach Rückfrage (C3); landet im Papierkorb |

### 7.2 Änderungen mit `delta`

- Erster Abgleich: `delta` ohne Parameter, allen `nextLink` folgen, am Ende `deltaLink` speichern.
- Folgende Abgleiche: nur den `deltaLink` abrufen; Einträge mit `deleted` = „im Dienst gelöscht“ (nur melden, C3).
- `410 Gone` bzw. ungültiger Link → vollständige Liste wie beim ersten Mal.
- Rückfall: bleibt `delta` auf dem App-Ordner mit `Files.ReadWrite.AppFolder` verwehrt, weiter mit der rekursiven
  `children`-Liste (heutiges Verhalten); für die kleinen Programmdaten genügt das.

### 7.3 Schutz vor Überschreiben

Zwischen „planen“ und „hochladen“ kann der zweite Rechner dieselbe Datei ändern. Darum Hochladen und Löschen mit
`If-Match: <eTag aus dem Plan>`; `412 Precondition Failed` → Datei wird zum **Konflikt** (Dialog „bitte
entscheiden“, C3) statt still überschrieben. Neue Dateien mit `conflictBehavior=fail`; Antwort `409` → ebenfalls
Konflikt.

### 7.4 Grenzen und Fehler

| Status | Bedeutung | Verhalten |
|---|---|---|
| 401 | Token abgelaufen/ungültig | einmal erneuern (§9), sonst „bitte neu anmelden“ |
| 403 | keine Berechtigung (z. B. Scope fehlt) | Meldung, neu anmelden |
| 404 | Datei/Upload-Sitzung fehlt | Liste neu; Upload von vorn |
| 409 / 412 | Name belegt / eTag passt nicht | Konflikt-Dialog |
| 429 / 503 | Drosselung | `Retry-After` anzeigen, Abgleich anhalten (Grundsatz „nicht wiederholen“, OD6) |
| 507 | OneDrive voll | Meldung mit freiem Speicher |
| 5xx beim Teil-Upload | Störung | mit `nextExpectedRanges` fortsetzen, höchstens 3 Versuche mit wachsender Wartezeit |

Mindestabstand je Host bleibt (`INTERVALS`, 0,1 s); gleichzeitig höchstens **ein** Abgleich je Konto.

## 8. Sicherheit

### 8.1 Bedrohungen und Massnahmen

| Bedrohung | Massnahme |
|---|---|
| Passwort-Diebstahl durch TagStudio | Anmeldung nur im System-Browser auf `login.microsoftonline.com`; kein eingebettetes Fenster, kein Passwortfeld |
| Untergeschobener Code (CSRF / fremde Rückleitung) | `state` (128 Bit) und PKCE S256; Code ohne passenden Verifier wertlos |
| Abfangen des Codes durch anderes Programm | Loopback nur auf diesem Rechner, kurz offen, eine Antwort; PKCE |
| Zu viel Zugriff | `Files.ReadWrite.AppFolder` statt `Files.ReadWrite`; `consumers` statt `common` |
| Token im Klartext | DPAPI (Windows) / Schlüsselbund (macOS); Rückfall Datei 0600 nur mit Hinweis |
| Token in Protokoll/Fehlertext | `App.secrets()` schwärzen; Upload- und Download-Adressen gelten ebenfalls als Geheimnis (sie sind vorab beglaubigt) und werden nie protokolliert |
| Token an fremden Host (**#401**) | Umleitungen ohne `Authorization`/`Cookie` bei Hostwechsel; Download über `downloadUrl` ohne Token |
| Pfad-Ausbruch (`..`) | `clean_path`/`clean_rel` vor jeder Anfrage |
| Fremde Dateien im App-Ordner | nur erlaubte Endungen je Teil; Inhalte als Daten, nie ausführen; Grössengrenze `MAX_FILE` (50 MB) |
| Zugangsdaten in der Cloud | `SettingsPart` ohne Zugangsdaten (wie bisher); `secretstore`-Dateien nie abgleichen |
| Öffentliches Repo | Vorgabe-Client-ID darf öffentlich sein (kein Secret); keine Tokens, Konten, Testdaten des Users im Repo |

### 8.2 Abmelden und Widerrufen

- „Abmelden …“ löscht Token, `pending` und Kontoangaben lokal (Abgleich-Zustand auf Wunsch).
- Microsoft bietet für private Konten keinen Widerruf per API; TagStudio verlinkt die Seite „Apps und Dienste“
  im Microsoft-Konto, wo der User „TagStudio“ den Zugriff entzieht (genaue Adresse **ZU PRÜFEN**).
- Passwortänderung beim Microsoft-Konto widerruft Erneuerungs-Token aus Passwort-Anmeldungen → TagStudio fragt beim
  nächsten Abgleich nach neuer Anmeldung.

### 8.3 Datenschutz

TagStudio überträgt nur an Microsoft und nur die abgeglichenen Dateien. Kein eigener Server, keine Telemetrie. In
PLUGINS.md und im Handbuch: was abgeglichen wird, wo es liegt (`Apps/TagStudio`), wie man den Zugriff entzieht.

### 8.4 Umleitungen (#401)

`urllib` übernimmt bei 302 alle Kopfzeilen ausser Content-Length/-Type – heute also auch den Bearer-Token zum
Download-Host. Behebung im Kern (`onlinematch.http_request`/`http_get`): eigener Redirect-Handler, der bei Wechsel von
Schema oder Host `Authorization` und `Cookie` entfernt. Gilt für alle Dienst-Plugins.

## 9. Tokenverwaltung

- **Laufzeiten:** Zugriffs-Token laut `expires_in` (typisch ~1 h); Erneuerungs-Token bei Desktop-Apps standardmässig
  90 Tage, jede Erneuerung liefert einen **neuen** Erneuerungs-Token. Microsoft kann ihn jederzeit ungültig machen –
  TagStudio verlässt sich auf keine feste Dauer.
- **Erneuern:** 60 s vor `expires_at` bzw. einmal nach 401. Den neuen Erneuerungs-Token sofort speichern, den alten
  verwerfen (Microsoft widerruft alte nicht selbst).
- **Sperre:** Erneuerung pro Plugin mit Sperre (`threading.Lock`), nach der Sperre Token neu lesen – zwei
  gleichzeitige Aufträge (Abgleich + „Verbindung testen“) erneuern sonst doppelt und überschreiben sich.
- **`invalid_grant`** (abgelaufen, widerrufen, Passwort geändert): Token löschen, Status „Anmeldung abgelaufen – bitte
  neu anmelden“, Abgleich als „nicht angemeldet“ überspringen (kein Fehlerdialog bei jedem Start).
- **Scope-Wechsel** (z. B. Übergang `Files.ReadWrite` → `AppFolder`): gespeicherter `scope` ≠ benötigter → neue
  Anmeldung anstossen, alten Token verwerfen.
- **Mehrere Rechner:** jeder Rechner meldet sich selbst an; Token werden nie abgeglichen. Mehrere TagStudio-Profile
  haben getrennte Schlüssel (`secretstore`-Konto = Pfad der Datei).

## 10. Umsetzung (Vorschlag, nach den Entscheiden)

| Schritt | Inhalt | Dateien |
|---|---|---|
| 1 | #401 Umleitungen ohne Token (Kern, alle Plugins) | `onlinematch.py`, Tests |
| 2 | `oauthkit`: Vorgabe-Client-ID, freier Port, `prompt`, Sperre beim Erneuern, `invalid_grant`, Scope-Prüfung | `oauthkit.py`, `tests/test_oauthkit.py` |
| 3 | OneDrive 2.0: `consumers`, AppFolder, Kontoprüfung `personal`, `downloadUrl`, `If-Match`, `delta` mit Rückfall | `plugins/onedrive/plugin.py` (+ `plugin.json` 2.0) |
| 4 | `cloudsync`: Felder `id`/`etag`/`_delta`/`_drive`, Konflikt bei 409/412, Kontowechsel | `cloudsync.py`, `session_cloud.py` |
| 5 | Oberfläche: „Anmelden …“ ohne Felder, „Erweitert › Eigene App“, Konto + Speicher anzeigen, Zugriff entziehen (Link) | `cloudkit.py`, `web/cloudsync.js`, i18n de/en/gsw |
| 6 | Übergang bestehender Nutzer (OD4) | Plugin, Hinweis |
| 7 | Doku: PLUGINS.md/.en, HANDBUCH/.en, KONZEPT-CLOUD §4b, CHANGELOG; Tests: Unit (gemockte Graph-Antworten), Playwright (Anmelde-Dialog) | |

Echte Tests nur mit dem Konto des Users und der registrierten App (Client-ID trägt der User ein).

## 11. Offene Entscheide

| ID | Frage | Vorschlag |
|---|---|---|
| OD1 | Registrierst du die App „TagStudio“ in einem eigenen Verzeichnis (Azure-Anmeldung bzw. M365 Developer Program)? Ohne sie bleibt nur die eigene App. | Ja, wenn das Verzeichnis ohne Kosten geht; sonst OneDrive bei „eigene App“ belassen |
| OD2 | App-Ordner (`Apps/TagStudio`, `Files.ReadWrite.AppFolder`) statt `/TagStudio` mit Zugriff aufs ganze OneDrive? | App-Ordner |
| OD3 | `User.Read` für den Anzeigenamen? | Nein, nur falls `owner` fehlt |
| OD4 | Bestehende Daten in `/TagStudio`: (a) einmal herunterladen und in den App-Ordner hochladen, (b) Hinweis „bitte selbst verschieben“, (c) eigene App behält den alten Ordner | (a) über den lokalen Stand: Abgleich lädt alles neu hoch, alter Ordner bleibt unangetastet |
| OD5 | Eigene App weiterhin anbieten (Erweitert)? | Ja |
| OD6 | Bei 429 einmal `Retry-After` abwarten (≤ 30 s) statt sofort anhalten? | Ja, einmal – Abweichung vom Grundsatz „nicht wiederholen“ nur mit deinem Entscheid |
| OD7 | Herausgeber-Verifizierung bei Microsoft (braucht Partner-Programm-Konto)? Ohne erscheint „nicht überprüft“. | Nein, zuerst ohne |
| OD8 | Meilenstein: 4.14.0 oder später? | Später (Spotify zuerst); #401 sofort |

## 12. Testliste (für das Umsetzungs-Issue)

- [ ] Ohne eigene App: „Anmelden …“ öffnet den Browser, Anmeldung mit privatem Konto, Zustimmung, zurück in TagStudio
- [ ] Geschäfts-/Schulkonto wird abgewiesen (Meldung „nur private Microsoft-Konten“)
- [ ] Zustimmung abgelehnt → verständliche Meldung, nichts gespeichert
- [ ] Port frei gewählt; „Adresse einfügen“ funktioniert weiterhin
- [ ] Ordner `Apps/TagStudio` entsteht; nach Umbenennen im OneDrive läuft der Abgleich weiter
- [ ] Abgleich beide Richtungen; zweiter Rechner ändert dieselbe Datei → Konflikt-Dialog (412)
- [ ] Datei > 4 MB über Upload-Sitzung; Unterbruch → Fortsetzen
- [ ] Zweiter Abgleich holt nur Änderungen (delta) bzw. Rückfall auf Liste
- [ ] Token nach 1 h automatisch erneuert; zwei gleichzeitige Aufträge → nur eine Erneuerung
- [ ] Passwort geändert / Zugriff im Microsoft-Konto entzogen → „bitte neu anmelden“
- [ ] Anderes Konto angemeldet → Rückfrage zum Abgleich-Zustand
- [ ] Protokolle enthalten keine Token, Upload- oder Download-Adressen
- [ ] Eigene App (Erweitert) funktioniert weiterhin
- [ ] Texte de/en/gsw, Handbuch und PLUGINS.md

## 13. Quellen (Microsoft Learn, abgerufen 29.10.2026)

- App-Ordner: [Using an App Folder](https://learn.microsoft.com/onedrive/developer/rest-api/concepts/special-folders-appfolder),
  [App folder in OneDrive and SharePoint](https://learn.microsoft.com/graph/onedrive-sharepoint-appfolder),
  [Permissions for OneDrive API](https://learn.microsoft.com/onedrive/developer/rest-api/concepts/permissions_reference)
  („Files.ReadWrite.AppFolder … only valid for personal accounts“)
- Kontotypen: [signInAudience](https://learn.microsoft.com/entra/identity-platform/supported-accounts-validation),
  `consumers`: [Access tokens](https://learn.microsoft.com/entra/identity-platform/access-tokens#validate-tokens)
- Rückleitung: [Redirect URI restrictions](https://learn.microsoft.com/entra/identity-platform/reply-url) (Port bei
  localhost ignoriert, `[::1]` nicht unterstützt)
- Token: [Refresh tokens](https://learn.microsoft.com/entra/identity-platform/refresh-tokens)
- Dateien: [Download](https://learn.microsoft.com/graph/api/driveitem-get-content) (302, ohne Authorization),
  [createUploadSession](https://learn.microsoft.com/graph/api/driveitem-createuploadsession) (320 KiB, < 60 MiB,
  If-Match), [delta](https://learn.microsoft.com/graph/api/driveitem-delta)
- Registrierung nur noch in einem Verzeichnis (seit Juni 2024):
  [Microsoft Q&A](https://learn.microsoft.com/answers/questions/1663127/question-regarding-notification-about-being-requir)
