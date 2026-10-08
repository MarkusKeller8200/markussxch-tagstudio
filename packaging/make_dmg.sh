#!/bin/bash
# MarKusSXCH TagStudio – macOS-Disk-Image bauen (nach python packaging/build.py)
#   bash packaging/make_dmg.sh 3.0
set -euo pipefail
VER="${1:-${TS_VERSION:-0.0}}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/TagStudio.app"
STAGE="$ROOT/build/dmg"
ARCH="$(uname -m)"
[ "$ARCH" = "arm64" ] && LABEL="Apple-Chip" || LABEL="Intel"
OUT="$ROOT/dist/TagStudio-$VER-macOS-$LABEL.dmg"

rm -rf "$STAGE" "$OUT"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Programme"
cp "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT/PLUGINS.md" "$STAGE/" 2>/dev/null || true
cat > "$STAGE/Zuerst lesen.txt" <<EOF
MarKusSXCH TagStudio $VER

Installieren: „TagStudio“ auf „Programme“ ziehen.

Erster Start: Die App ist nicht von Apple beglaubigt (kein kostenpflichtiges Entwicklerkonto).
macOS blockiert sie deshalb beim ersten Öffnen.
  1. TagStudio im Programme-Ordner doppelklicken → Meldung schliessen.
  2. Systemeinstellungen → Datenschutz & Sicherheit → ganz unten bei „TagStudio“ auf „Trotzdem öffnen“.
  3. Nochmals öffnen und bestätigen. Danach startet die App normal.
Alternativ im Terminal: xattr -dr com.apple.quarantine /Applications/TagStudio.app

Einstellungen, Sicherungen und Plugins liegen im Benutzerordner (~/.tagstudio.json, ~/TagStudio)
und bleiben bei einem Update erhalten.
EOF
hdiutil create -volname "TagStudio $VER" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "Fertig: $OUT"
