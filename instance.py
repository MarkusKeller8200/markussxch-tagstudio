"""Nur eine laufende TagStudio-Instanz je Benutzer (4.1.0).

Zwei gleichzeitige Instanzen überschreiben sich gegenseitig die Einstellungen (z. B. wenn der Installer eine neue
Version startet, während die alte noch offen ist). Deshalb:

- **Sperrdatei** `~/.tagstudio.lock` mit Betriebssystem-Sperre (Windows: msvcrt, sonst fcntl) – wird beim Beenden
  oder Absturz des Prozesses automatisch frei.
- **Windows:** zusätzlich ein benannter Mutex `MUTEX`; der Installer (Inno Setup, `AppMutex`) erkennt daran eine
  laufende TagStudio-Instanz und bittet, sie zu schliessen, bevor er Dateien ersetzt.
"""
from __future__ import annotations

import os
import sys
import time

MUTEX = "MarKusSXCH-TagStudio"
LOCKFILE = os.path.join(os.path.expanduser("~"), ".tagstudio.lock")


class Instance:
    def __init__(self, path: str | None = None):
        self.path = path or LOCKFILE
        self.fh = None
        self.mutex = None

    def _try(self) -> bool:
        try:
            fh = open(self.path, "a+")
        except OSError:
            return True                       # ohne Sperrdatei lieber starten als blockieren
        try:
            if sys.platform.startswith("win"):
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self.fh = fh
        try:
            fh.seek(0)
            fh.truncate()
            fh.write(str(os.getpid()))
            fh.flush()
        except OSError:
            pass
        return True

    def acquire(self, wait: float = 0.0) -> bool:
        """Sperre holen; bis `wait` Sekunden warten (z. B. während die alte Instanz bei einem Neustart endet)."""
        end = time.monotonic() + max(0.0, wait)
        while True:
            if self._try():
                self._mutex()
                return True
            if time.monotonic() >= end:
                return False
            time.sleep(0.2)

    def _mutex(self):
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            self.mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX)
        except Exception:  # noqa: BLE001
            self.mutex = None

    def release(self):
        if self.fh is not None:
            try:
                if sys.platform.startswith("win"):
                    import msvcrt
                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            self.fh.close()
            self.fh = None
        if self.mutex:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.mutex)
            except Exception:  # noqa: BLE001
                pass
            self.mutex = None


def already_running_message(text: str):
    """Hinweis ohne Oberfläche: Windows-Meldungsfenster, sonst Konsole."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, "MarKusSXCH TagStudio", 0x40 | 0x40000)
            return
        except Exception:  # noqa: BLE001
            pass
    print(text, file=sys.stderr)
