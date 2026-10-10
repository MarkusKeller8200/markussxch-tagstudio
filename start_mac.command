#!/bin/bash
# MarKusSXCH TagStudio starten (neue Oberfläche).
# Die klassische Oberfläche (eingefroren, Stand 3.0): start_classic_mac.command
exec "$(dirname "$0")/start_web_mac.command" "$@"
