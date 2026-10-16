# Konzept: Update und Versionen

Stand: 2026-10-11 (4.4.0-beta.4) · Status: **umgesetzt** (Update-Knopf seit 2.x, Kanäle und Versionshinweise seit 3.5.0) · nachträglich erstellt

> **Pflege:** Dieses Dokument wurde nachträglich aus Code und Handbuch zusammengestellt. Wird am Update, an der
> Versionierung oder am Release-Ablauf weitergearbeitet, ist es im selben Zug anzupassen.

## 1. Ziel

Neue Versionen sollen den User ohne Umwege erreichen – in der installierten App wie in der Quellcode-Variante –, mit
Wahl zwischen offiziellen und Beta-Versionen und mit verständlichen Versionshinweisen. Einstellungen und Daten
bleiben bei jedem Update erhalten.

## 2. Funktionen

- **„Nach Update suchen“** unten in der Seitenleiste; Prüfung beim Start (Punkt am Knopf).
- **Kanal** (Einstellungen › Updates, `update_channel`): `stable` = nur offizielle Versionen, `beta` = auch Betas.
- **Installierte App:** fragt die GitHub-Releases ab, zeigt die neue Version mit Hinweisen und lädt den passenden
  Installer herunter; installiert wird darüber (Einstellungen bleiben).
- **Quellcode (Git-Klon):** `git fetch` + `pull --ff-only` (nur Vorspulen, nur ohne eigene Änderungen); bei `stable`
  bis zum neuesten Versions-Tag. Vorher Abfrage ungespeicherter Änderungen und laufender Aufträge, danach Neustart.
  Alte Zweige werden umgestellt (`MOVED = {"web-ui": "main"}`).
- **Versionshinweise:** installierte Version (aus dem mitgelieferten CHANGELOG), neueste auf GitHub, „Weitere
  Versionen“ zum Aufklappen, Link zu GitHub.
- **„Neu in dieser Version“** nach einem Update (#170, siehe [KONZEPT-EINRICHTUNG.md](KONZEPT-EINRICHTUNG.md)).

## 3. Versionierung und Release

- SemVer `MAJOR.MINOR.PATCH`, Betas `X.Y.Z-beta.N`; einzige Quelle `version.py`.
- CHANGELOG: jede Änderung sofort unter „Unveröffentlicht“; `packaging/release.py X.Y.Z[-beta.N]` setzt die Version
  (final: verschiebt „Unveröffentlicht“ in den Versionsabschnitt).
- Push auf `main` → Workflow „Installer“ baut (Betas nur Windows, finale Versionen zusätzlich macOS), testet, legt Tag
  und Release an (Beta = Pre-Release). Nach einer finalen Version entfernt `cleanup_betas.py` die Beta-Releases
  (Tags bleiben). Finale Versionen nur auf ausdrücklichen Wunsch des Users.

**Developer Release (Entscheid 16.10.2026):** Läuft TagStudio aus dem Quellcode (Git) und liegen nach dem Tag der
laufenden Version `v<VERSION>` weitere Commits – oder fehlt dieser Tag noch –, zeigt die Seitenleiste „Version X ·
Developer Release“ (Tooltip: Anzahl Änderungen, Stand, Basisversion). `updater.dev_info()` per `git describe --tags
--long --match v[0-9]*`, einmal je Start zwischengespeichert. Die installierte App ist nie ein Developer Release.
Betas sind nicht nötig, wenn alles auf `main` getestet ist (4.5.0 erschien direkt final).

## 4. Umsetzung

- **Kern:** `updater.py` (`status`, `pull`, `fetch_releases`, `release_check`, `parse_version`, `is_beta`,
  `changelog_section`, `changelog_versions`, `final_tag_target`, `frozen`), `version.py`.
- **Api** (`tagstudio_web.py`): `update_status`, `apply_update`, `release_notes`, `restart`.
- **Oberfläche:** `web/app.js` (Update-Dialog, Versionshinweise mit `mdLite`).
- **Paketierung:** `packaging/release.py`, `packaging/build.py`, `packaging/windows.iss`, `make_dmg.sh`,
  `.github/workflows/installer.yml`, `.github/scripts/cleanup_betas.py`.

## 5. Entscheide

- Installer bleibt kanalgebunden an GitHub-Releases; kein stilles Selbst-Update.
- Klassische Oberfläche und Zweig `web-ui` sind abgeschlossen; Updates laufen nur über `main`.

## 6. Offen / Ideen

- #14 Installer signieren (Windows, macOS) – offen gelassen, lohnt sich derzeit nicht.

## 7. Tests

`tests/test_updater.py`, `tests/test_version.py` (Konsistenz von `version.py`, `pyproject.toml`, CHANGELOG).
