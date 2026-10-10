"""MarKusSXCH TagStudio – die einzige Stelle mit der Versionsnummer.

Schema MAJOR.MINOR.PATCH (Semantic Versioning):
  PATCH  Fehlerbehebungen                     3.0.0 → 3.0.1
  MINOR  neue Funktionen                      3.0.1 → 3.1.0
  MAJOR  grosse Umbrüche / inkompatibel       3.1.0 → 4.0.0
  Vorabversionen mit Zusatz: 3.1.0-beta.1

Nicht von Hand ändern, sondern:  python packaging/release.py 3.1.0
Schlägt der Build fehl (kein Tag entstanden), nach der Korrektur eine Änderung an dieser Datei pushen –
der Workflow „Installer“ startet nur bei Änderungen hier bzw. unter packaging/.
"""
VERSION = "4.1.0-beta.1"
APP = "MarKusSXCH TagStudio"
