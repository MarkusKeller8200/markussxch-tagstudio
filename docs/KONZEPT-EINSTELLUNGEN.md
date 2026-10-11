# Konzept: Einstellungen

Stand: 2026-10-11 (4.4.0-beta.4) · Status: **umgesetzt** (Seite seit 3.2.0, laufend erweitert) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird an den Einstellungen
> weitergearbeitet – auch wenn eine Funktion neue Einstellungen bekommt –, ist es im selben Zug anzupassen
> (Kacheln, Gruppen, Entscheide, Offen).

## 1. Ziel

Alle Einstellungen an einem Ort, verständlich gruppiert, mit Vorgaben für den Start („wie zuletzt benutzt“ oder fest),
übertragbar zwischen Rechnern (Windows ↔ Mac) und sicher zurücksetzbar.

## 2. Funktionen

- **Kacheln** mit Sprungmarken (`#stToc`): Darstellung (inkl. Seitenleiste ein-/ausblenden) · Tagger · Tag-Fixer ·
  Vergleich · Snapshots · Sicherungen und Speichern (ID3-Version, Sicherung) · Player · Plugins · Herkunft der Tags ·
  Unwichtige Felder · Cache · Updates · Speicherort und Ordner (Basisordner, Struktur, Archiv) · Profile · **Expert**
  (Diagnose, Einstellungsdatei und Protokolle ansehen, Zugangsdaten ausgeblendet). Vorbereiten und DJ-Set haben ihre
  Einstellungen auf der eigenen Seite.
- **Vorgaben beim Start** für Tagger und Vergleich (`tg_defaults`, `cmp_defaults`), ⌂ setzt auf den Standard zurück.
- **Exportieren** (ohne Zugangsdaten), **Importieren** gruppenweise mit Vorschau (Pfade eines anderen Systems nicht
  vorgewählt), **Zurücksetzen** je Gruppe oder alles; vorher Sicherung nach `Einstellungen\` (max. 20).
- **Einrichtungsassistent** und „Erste Schritte“ erneut starten (siehe [KONZEPT-EINRICHTUNG.md](KONZEPT-EINRICHTUNG.md)).

## 3. Gruppen (Export/Import/Zurücksetzen)

`appsettings.GROUPS`: design · layout · setup · view · history · trivial · saving · update · player · snapshots ·
djset · origin · plugins. Maschinenabhängig (beim Import von einem anderen System nicht vorgewählt): history, saving,
player, snapshots. Schlüssel mit `token|passw|secret|cookie|session|credential|api_key|auth` werden nie exportiert.

## 4. Umsetzung

- **Kern:** `appsettings.py` (Gruppen, Export/Import/Reset, Sicherungen), `core.py` (`save_config` mit Sperre),
  `paths.py` (Ort der Einstellungsdatei je Profil).
- **Session:** `settings`, `settings_page`, `set_option`, `set_ui`, `settings_export_text`, `settings_import_preview`,
  `settings_import`, `settings_reset`, dazu die `set_*`-Methoden der einzelnen Bereiche; `_load_cfg` liest nach
  Import/Reset neu ein (Oberfläche lädt neu).
- **Oberfläche:** `web/settings.js`, `web/setup.js` (Speicherort, Archiv), `web/profiles.js`.
- **Ablage:** `~/.tagstudio.json` bzw. `einstellungen.json` im Profil (siehe [KONZEPT-SPEICHER.md](KONZEPT-SPEICHER.md)).

## 5. Entscheide

- Eine Datei für alle Einstellungen; Browser-Speicher nur für Kleinigkeiten (z. B. JSON-Expertenmodus).
- Neue Einstellungen werden einer Gruppe in `appsettings.GROUPS` zugeordnet (sonst fehlen sie in Export/Import).

## 6. Offen / Ideen

- Mehrsprachigkeit der Oberfläche: [KONZEPT-MEHRSPRACHIG.md](KONZEPT-MEHRSPRACHIG.md) (#157).

## 7. Tests

`tests/test_settings_page.py`, `test_setup.py`, `test_paths.py`, Oberflächen-Tests in `tests/test_browser_ui.py`.
