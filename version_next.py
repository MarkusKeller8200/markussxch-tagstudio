"""Geplante nächste Version (#233) – nur für die Anzeige des Developer Release im Quellcode.

Leer = automatisch: Version der laufenden Beta ohne Zusatz (4.8.0-beta.1 → 4.8.0), sonst die nächste Minor-Version
(4.7.0 → 4.8.0). Steht ein anderes Release an (z. B. ein Patch 4.7.1), hier eintragen. `packaging/release.py` setzt den
Wert beim Erstellen einer Version wieder auf leer. Bewusst nicht in version.py: Änderungen dort starten den Installer.
"""
NEXT = ""
