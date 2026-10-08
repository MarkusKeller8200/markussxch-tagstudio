#!/bin/bash
# MarKusSXCH TagStudio starten
cd "$(dirname "$0")"
exec python3 tagstudio.py "$@"
