"""Schreibt eine Datei als GitHub-Actions-Anmerkung (notice/warning/error), damit Ergebnisse ohne Log-Zugriff
lesbar sind:  python packaging/ci_note.py error "PyInstaller" build.log [Zeilen]"""
import sys

level, title, path = sys.argv[1], sys.argv[2], sys.argv[3]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 60
try:
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()[-n:]
except OSError as ex:
    lines = [f"(keine Datei: {ex})"]
text = "\n".join(lines)
text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
print(f"::{level} title={title}::{text}")
