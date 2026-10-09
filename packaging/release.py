"""Neue Version vorbereiten: Versionsnummer setzen und den CHANGELOG umstellen.

    python packaging/release.py 3.1.0            # Version 3.1.0 (Abschnitt „Unveröffentlicht“ → [3.1.0] – Datum)
    python packaging/release.py 3.1.0-beta.1     # Vorabversion (CHANGELOG bleibt, Text kommt aus „Unveröffentlicht“)
    python packaging/release.py 3.1.0 --commit   # zusätzlich git commit + Tag v3.1.0 (danach: git push --follow-tags)
    python packaging/release.py --check          # nur prüfen, ob alles zusammenpasst

Danach den Tag v<Version> auf GitHub setzen (oder pushen) – GitHub baut dann die Installer und das Release.
"""
import datetime
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$")
UNRELEASED = "## [Unveröffentlicht]"


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def _write(name, text):
    with open(os.path.join(ROOT, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def current_version(root=ROOT) -> str:
    with open(os.path.join(root, "version.py"), encoding="utf-8") as fh:
        return re.search(r'^VERSION = "([^"]+)"', fh.read(), re.M).group(1)


def key(v):
    """Sortierschlüssel nach SemVer: 3.1.0-beta.2 < 3.1.0-beta.10 < 3.1.0-rc.1 < 3.1.0."""
    m = SEMVER.match(v or "")
    if not m:
        raise ValueError(f"„{v}“ ist keine gültige Version (MAJOR.MINOR.PATCH).")
    major, minor, patch, pre = int(m[1]), int(m[2]), int(m[3]), m[4]
    # Zahlen-Teile numerisch, Zahlen vor Text
    ids = tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre.lstrip("-").split(".")) if pre else ()
    return (major, minor, patch, 0 if pre else 1, ids)


def unreleased_text(changelog: str) -> str:
    i = changelog.find(UNRELEASED)
    if i < 0:
        return ""
    rest = changelog[i + len(UNRELEASED):]
    j = rest.find("\n## [")
    return (rest if j < 0 else rest[:j]).strip()


def section_text(changelog: str, ver: str) -> str:
    """Text eines Abschnitts (für die Release-Beschreibung); bei Vorabversionen „Unveröffentlicht“."""
    m = re.search(r"^## \[" + re.escape(ver) + r"\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog, re.S | re.M)
    if m:
        return m.group(1).strip()
    return unreleased_text(changelog)


def check(root=ROOT) -> list:
    """Probleme in der Versionierung (leer = alles in Ordnung)."""
    probs = []
    ver = current_version(root)
    if not SEMVER.match(ver):
        probs.append(f"version.py: „{ver}“ ist keine gültige Version (MAJOR.MINOR.PATCH).")
    with open(os.path.join(root, "pyproject.toml"), encoding="utf-8") as fh:
        m = re.search(r'^version = "([^"]+)"', fh.read(), re.M)
    if not m or m.group(1) != ver:
        probs.append(f"pyproject.toml hat Version {m.group(1) if m else '?'}, version.py {ver}.")
    with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as fh:
        log = fh.read()
    if UNRELEASED not in log:
        probs.append("CHANGELOG.md: Abschnitt „## [Unveröffentlicht]“ fehlt.")
    if "-" not in ver and f"## [{ver}]" not in log:
        probs.append(f"CHANGELOG.md: Abschnitt „## [{ver}]“ fehlt.")
    return probs


def release(new: str, today=None, root=ROOT) -> str:
    if not SEMVER.match(new):
        raise ValueError(f"„{new}“ ist keine gültige Version – Schema MAJOR.MINOR.PATCH, z. B. 3.1.0 oder 3.1.0-beta.1.")
    old = current_version(root)
    if key(new) <= key(old):
        raise ValueError(f"{new} ist nicht neuer als die aktuelle Version {old}.")
    pre = "-" in new
    log_path = os.path.join(root, "CHANGELOG.md")
    with open(log_path, encoding="utf-8") as fh:
        log = fh.read()
    if UNRELEASED not in log:
        raise ValueError("CHANGELOG.md hat keinen Abschnitt „## [Unveröffentlicht]“.")
    if not pre:
        if not unreleased_text(log):
            raise ValueError("Unter „Unveröffentlicht“ steht nichts – was ist neu in dieser Version?")
        date = (today or datetime.date.today()).isoformat()
        log = log.replace(UNRELEASED, f"{UNRELEASED}\n\n## [{new}] – {date}", 1)
        with open(log_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(log)
    for name, pat, rep in (("version.py", r'^VERSION = "[^"]+"', f'VERSION = "{new}"'),
                           ("pyproject.toml", r'^version = "[^"]+"', f'version = "{new}"')):
        p = os.path.join(root, name)
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        text, n = re.subn(pat, rep, text, count=1, flags=re.M)
        if not n:
            raise ValueError(f"Versionszeile in {name} nicht gefunden.")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    return old


def main(argv):
    if "--check" in argv:
        probs = check()
        print("\n".join(probs) if probs else f"Versionierung in Ordnung ({current_version()}).")
        return 1 if probs else 0
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    new = args[0].lstrip("v")
    try:
        old = release(new)
    except ValueError as ex:
        print(f"Fehler: {ex}")
        return 1
    print(f"Version {old} → {new}: version.py, pyproject.toml" + ("" if "-" in new else ", CHANGELOG.md") + " angepasst.")
    if "--commit" in argv:
        subprocess.run(["git", "add", "version.py", "pyproject.toml", "CHANGELOG.md"], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"Version {new}"], cwd=ROOT, check=True)
        subprocess.run(["git", "tag", "-a", f"v{new}", "-m", f"MarKusSXCH TagStudio {new}"], cwd=ROOT, check=True)
        print(f"Commit und Tag v{new} erstellt. Jetzt: git push --follow-tags")
    else:
        print(f"Nächste Schritte: committen und auf main pushen – der Workflow „Installer“ baut dann und legt "
              f"Tag v{new} und das Release selbst an.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
