#!/bin/bash
# MarKusSXCH TagStudio – neue Oberfläche starten (installiert pywebview beim ersten Mal)
cd "$(dirname "$0")"
if ! python3 -c "import webview" 2>/dev/null; then
  echo "pywebview wird installiert (einmalig) …"
  python3 -m pip install --user pywebview || exec python3 tagstudio_web.py --browser "$@"
fi
exec python3 tagstudio_web.py "$@"
