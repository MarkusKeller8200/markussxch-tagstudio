"""MarKusSXCH TagStudio – die einzige Stelle mit der Versionsnummer.

Schema MAJOR.MINOR.PATCH (Semantic Versioning):
  PATCH  Fehlerbehebungen                     3.0.0 → 3.0.1
  MINOR  neue Funktionen                      3.0.1 → 3.1.0
  MAJOR  grosse Umbrüche / inkompatibel       3.1.0 → 4.0.0
  Vorabversionen mit Zusatz: 3.1.0-beta.1

Nicht von Hand ändern, sondern:  python packaging/release.py 3.1.0
"""
VERSION = "3.2.0-beta.2"
APP = "MarKusSXCH TagStudio"
