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
cp "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT/PLUGINS.md" "$ROOT/LICENSE" "$STAGE/" 2>/dev/null || true
if [ -n "${TS_SIGN_ID:-}" ]; then        # #374: signiert und von Apple beglaubigt
cat > "$STAGE/Zuerst lesen.txt" <<EOF
MarKusSXCH TagStudio $VER

Installieren: „TagStudio“ auf „Programme“ ziehen und starten.
Die App ist signiert und von Apple beglaubigt (notarisiert).

Einstellungen, Sicherungen und Plugins liegen im Benutzerordner (~/.tagstudio.json, ~/TagStudio)
und bleiben bei einem Update erhalten.
EOF
else
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
fi
hdiutil create -volname "TagStudio $VER" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
if [ -n "${TS_SIGN_ID:-}" ]; then        # #374: Disk-Image signieren, beglaubigen lassen, Ticket anheften
  codesign --force --timestamp --sign "$TS_SIGN_ID" "$OUT"
  if [ -n "${TS_NOTARY_KEY:-}" ]; then
    mkdir -p "$ROOT/build"
    auth=(--key "$TS_NOTARY_KEY" --key-id "$TS_NOTARY_KEY_ID" --issuer "$TS_NOTARY_ISSUER")
    # einreichen ohne zu warten → ID sichtbar (die erste Beglaubigung eines neuen Kontos kann Stunden dauern)
    xcrun notarytool submit "$OUT" "${auth[@]}" --no-wait --output-format json > "$ROOT/build/notary.json"
    id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id",""))' "$ROOT/build/notary.json")"
    [ -n "$id" ] || { cat "$ROOT/build/notary.json"; echo "::error title=Notarisierung::Einreichen fehlgeschlagen"; exit 1; }
    echo "::notice title=Notarisierung eingereicht::ID $id"
    set +e
    xcrun notarytool wait "$id" "${auth[@]}" --timeout "${TS_NOTARY_WAIT:-120m}" --output-format json > "$ROOT/build/notary-wait.json"
    set -e
    status="$(python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("status",""))
except Exception: print("")' "$ROOT/build/notary-wait.json")"
    if [ "$status" != "Accepted" ]; then
      xcrun notarytool info "$id" "${auth[@]}" || true
      [ "$status" = "Invalid" ] && xcrun notarytool log "$id" "${auth[@]}" || true
      echo "::error title=Notarisierung ${status:-noch nicht fertig}::ID $id – Status „${status:-In Progress}“. Bei „In Progress“: Apple prüft noch (beim ersten Mal oft Stunden), später erneut bauen."
      exit 1
    fi
    xcrun stapler staple "$OUT"
    xcrun stapler validate "$OUT"
  fi
fi
echo "Fertig: $OUT"
