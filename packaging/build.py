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
    "services", "servicekit", "oauthkit", "feedback", "lyricsync", "gridstatus", "beattag",   # #204: Online-Dienste als Plugins
    "keyscan",                                                     # #244/#245: Tonart mit OpenKeyScan
    "secretstore",                                                 # #287: Zugangsdaten (DPAPI / Schlüsselbund)
    "tsmeta", "i18n",                                              # #157: Mehrsprachigkeit
    # eigene Module (werden teils erst bei Bedarf importiert)
    "session", "core", "keys", "features", "plugins", "updater", "xmltools", "tagger", "backup", "compare",
    "id3tags", "thumbs", "undo", "version", "blobs", "media", "cues", "waveform", "appsettings", "origins", "jobs", "stemsview", "snapshots", "players",
    "session_player", "session_snapshots", "ratings", "listcache", "setplan", "session_djset", "setexport", "onlinematch", "instance", "applog", "serato", "importsync", "moods", "id3frames", "taghelp", "session_help", "recipes", "prepare", "session_prepare", "discover", "session_discover", "paths", "session_setup", "archive", "plugin_store", "playlists", "session_playlists", "smartlist", "purchases", "session_purchases",
    "folders", "session_folders", "cloud", "foldermove",                # #310–#315: Ordner-Rollen (4.10.0)
    "wavetag", "cloudsync", "cloudkit", "session_cloud",               # #222, #317–#320: Wellenform im MP3, Cloud-Abgleich (4.11.0)
    "smartfix", "unzip",                                               # #339 Smart Fix, #336 ZIP entpacken (4.12.0)
    "downloadstats", "ideas", "session_ideas", "mixresult", "session_mixes", "djlibs",   # #370, #186, #387 (4.13.0)
    "mirror", "session_mirror", "appbackup", "session_appbackup",     # #403 Spiegel, #402 Sicherung (4.14.0)
    # Standardbibliothek für Plugins
    "http.cookiejar", "urllib.request", "urllib.parse", "urllib.error", "difflib", "unicodedata", "ctypes",
    "ctypes.wintypes", "uuid", "csv", "zipfile", "logging", "base64", "hashlib", "html", "html.parser",
    "xml.dom.minidom", "xml.etree.ElementTree", "sqlite3", "datetime", "statistics", "shlex", "tempfile",
    "email.utils", "subprocess", "shutil", "threading", "ipaddress",
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
            "--add-data", f"{os.path.join(ROOT, 'CHANGELOG.md')}{sep}.",          # Versionshinweise in der App (#90)
            "--add-data", f"{os.path.join(ROOT, 'README.md')}{sep}.",             # Hilfe (#158)
            "--add-data", f"{os.path.join(ROOT, 'PLUGINS.md')}{sep}.",
            "--add-data", f"{os.path.join(ROOT, 'README.en.md')}{sep}.",          # englische Hilfe (#219)
            "--add-data", f"{os.path.join(ROOT, 'PLUGINS.en.md')}{sep}.",
            "--add-data", f"{os.path.join(ROOT, 'docs', 'HANDBUCH.md')}{sep}docs",     # Handbuch der Hilfe (#373)
            "--add-data", f"{os.path.join(ROOT, 'docs', 'HANDBUCH.en.md')}{sep}docs",
            "--add-data", f"{os.path.join(ROOT, 'docs', 'ID3-FELDER.md')}{sep}docs",
            "--add-data", f"{os.path.join(ROOT, 'docs', 'ID3-FELDER.en.md')}{sep}docs",
            "--add-data", f"{os.path.join(ROOT, 'docs', 'third-party.json')}{sep}docs",   # Hilfe › Lizenzen (#176)
            "--add-binary", f"{uv_binary()}{sep}.",
            "--paths", ROOT]
    for h in HIDDEN:
        args += ["--hidden-import", h]
    sign_id = os.environ.get("TS_SIGN_ID", "").strip() if mac else ""    # #374: Developer ID aus dem Workflow
    ent = os.path.join(ROOT, "packaging", "entitlements.plist")
    if mac:
        args += ["--osx-bundle-identifier", BUNDLE_ID]
        if sign_id:                     # PyInstaller signiert alle eingebetteten Teile (Hardened Runtime)
            args += ["--codesign-identity", sign_id, "--osx-entitlements-file", ent]
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
        app = os.path.join(DIST, NAME + ".app")
        if sign_id:   # #374: nach dem Ändern die App selbst neu signieren (Teile sind schon signiert), für Notarisierung
            subprocess.run(["codesign", "--force", "--options", "runtime", "--timestamp", "--entitlements", ent,
                            "--sign", sign_id, app], check=True)
            subprocess.run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app], check=True)
        else:         # nach dem Ändern neu (ad hoc) signieren, sonst startet die App auf Apple-Chips nicht
            subprocess.run(["codesign", "--force", "--deep", "--sign", "-", app], check=True)

    env = os.environ.get("GITHUB_ENV")
    if env:
        with open(env, "a", encoding="utf-8") as fh:
            fh.write(f"TS_VERSION={ver}\n")
    print(f"Fertig: {APP_TITLE} {ver} → {DIST}")


if __name__ == "__main__":
    main()
