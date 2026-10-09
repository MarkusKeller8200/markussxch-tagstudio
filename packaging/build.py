"""Baut die eigenständige App mit PyInstaller (Windows: Ordner mit TagStudio.exe, macOS: TagStudio.app).

    python -m pip install pyinstaller pywebview pillow uv
    python packaging/build.py

Ergebnis in dist/. Danach baut packaging/windows.iss (Inno Setup) den Windows-Installer bzw.
packaging/make_dmg.sh das macOS-Disk-Image. In GitHub Actions: .github/workflows/installer.yml.
"""
import os
import plistlib
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "packaging")
DIST = os.path.join(ROOT, "dist")
BUILD = os.path.join(ROOT, "build")
NAME = "TagStudio"
APP_TITLE = "MarKusSXCH TagStudio"
BUNDLE_ID = "ch.markussxch.tagstudio"

# Module, die nur von Plugins (zur Laufzeit geladene .py-Dateien) gebraucht werden – PyInstaller sieht sie sonst nicht
HIDDEN = [
    # eigene Module (werden teils erst bei Bedarf importiert)
    "session", "core", "keys", "features", "plugins", "updater", "xmltools", "tagger", "backup", "compare",
    "id3tags", "thumbs", "undo", "version", "blobs", "media", "cues", "waveform", "appsettings", "origins", "jobs", "stemsview", "snapshots", "players",
    # Standardbibliothek für Plugins
    "http.cookiejar", "urllib.request", "urllib.parse", "urllib.error", "difflib", "unicodedata", "ctypes",
    "ctypes.wintypes", "uuid", "csv", "zipfile", "logging", "base64", "hashlib", "html", "html.parser",
    "xml.dom.minidom", "xml.etree.ElementTree", "sqlite3", "datetime", "statistics", "shlex", "tempfile",
    # Dialoge
    "tkinter", "tkinter.filedialog", "tkinter.messagebox",
]


def version() -> str:
    with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as fh:
        return re.search(r'^VERSION = "([^"]+)"', fh.read(), re.M).group(1)


def uv_binary() -> str:
    try:
        import uv
        return uv.find_uv_bin()
    except Exception:  # noqa: BLE001
        found = shutil.which("uv")
        if not found:
            sys.exit("uv nicht gefunden – bitte „python -m pip install uv“ ausführen.")
        return found


def stage_plugins() -> str:
    """Plugins ohne Caches für das Bündel bereitstellen."""
    dst = os.path.join(BUILD, "staging", "plugins")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "plugins"), dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def main():
    ver = version()
    sep = os.pathsep
    mac = sys.platform == "darwin"
    win = sys.platform.startswith("win")
    shutil.rmtree(os.path.join(DIST, NAME), ignore_errors=True)
    shutil.rmtree(os.path.join(DIST, NAME + ".app"), ignore_errors=True)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME,
            "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyinstaller"), "--specpath", BUILD,
            "--icon", os.path.join(PKG, "icon.ico" if win else "icon.png"),
            "--add-data", f"{os.path.join(ROOT, 'web')}{sep}web",
            "--add-data", f"{stage_plugins()}{sep}plugins",
            "--add-binary", f"{uv_binary()}{sep}.",
            "--paths", ROOT]
    for h in HIDDEN:
        args += ["--hidden-import", h]
    if mac:
        args += ["--osx-bundle-identifier", BUNDLE_ID]
    args.append(os.path.join(ROOT, "tagstudio_web.py"))
    print(" ".join(args), flush=True)
    subprocess.run(args, check=True, cwd=ROOT)

    if mac:   # Versionsnummer und Anzeigename ins Info.plist
        plist = os.path.join(DIST, NAME + ".app", "Contents", "Info.plist")
        with open(plist, "rb") as fh:
            info = plistlib.load(fh)
        info.update(CFBundleShortVersionString=ver, CFBundleVersion=ver, CFBundleDisplayName=APP_TITLE,
                    CFBundleName=NAME, NSHighResolutionCapable=True, LSMinimumSystemVersion="11.0",
                    NSHumanReadableCopyright="Markus Keller")
        with open(plist, "wb") as fh:
            plistlib.dump(info, fh)
        # nach dem Ändern neu (ad hoc) signieren, sonst startet die App auf Apple-Chips nicht
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", os.path.join(DIST, NAME + ".app")], check=True)

    env = os.environ.get("GITHUB_ENV")
    if env:
        with open(env, "a", encoding="utf-8") as fh:
            fh.write(f"TS_VERSION={ver}\n")
    print(f"Fertig: {APP_TITLE} {ver} → {DIST}")


if __name__ == "__main__":
    main()
