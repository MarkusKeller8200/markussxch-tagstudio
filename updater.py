"""
updater.py – neue Version von GitHub holen (git fetch / git pull im Programmordner).

Funktioniert, wenn der Programmordner ein Git-Repository ist und git installiert ist.
Es wird nur „vorgespult“ (--ff-only): lokale Änderungen werden nie überschrieben.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Abgeschlossene Entwicklungszweige → Zweig, auf dem es weitergeht. Ein Update wechselt dorthin,
# sobald der neue Zweig den alten vollständig enthält (also nur Vorspulen, nichts geht verloren).
MOVED = {"web-ui": "main"}
RELEASES_URL = "https://github.com/MarkusKeller8200/markussxch-tagstudio/releases"


def frozen() -> bool:
    """Läuft TagStudio als installierte App (PyInstaller) statt aus dem Quellcode?"""
    return bool(getattr(sys, "frozen", False))


def _git(args, cwd=HERE, timeout=60):
    kw = {}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW: kein Konsolenfenster aufblitzen lassen
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace", **kw)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def available(cwd=HERE) -> str | None:
    """None, wenn Updates möglich sind – sonst der Grund, warum nicht."""
    if frozen():
        return ("Die installierte App wird mit dem neuen Installer aktualisiert: neue Version unter "
                "„Releases“ auf GitHub herunterladen und installieren (Einstellungen bleiben erhalten).")
    if shutil.which("git") is None:
        return "Git ist auf diesem Rechner nicht installiert."
    code, out, _ = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if code != 0 or out != "true":
        return "Der Programmordner ist kein Git-Repository."
    return None


def status(fetch: bool = True, cwd=HERE, channel: str = "beta") -> dict:
    """Vergleicht den lokalen Stand mit GitHub.
    → {"ok", "error", "branch", "behind", "ahead", "commits": [Betreff…], "dirty": [Dateien…], "current"}"""
    err = available(cwd)
    if err:
        return {"ok": False, "error": err, "frozen": frozen(), "releases_url": RELEASES_URL}
    code, branch, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if code != 0 or branch == "HEAD":
        return {"ok": False, "error": "Kein Zweig ausgecheckt."}
    code, upstream, _ = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd)
    if code != 0:
        if branch not in MOVED:
            return {"ok": False, "error": f"Der Zweig „{branch}“ ist nicht mit GitHub verbunden.", "branch": branch}
        upstream = f"origin/{MOVED[branch]}"      # alter Zweig auf GitHub gelöscht → trotzdem umstellen
    remote = upstream.split("/", 1)[0]
    if fetch:
        code, _, err = _git(["fetch", "--quiet", "--tags", remote], cwd, timeout=90)
        if code != 0:
            return {"ok": False, "error": f"GitHub ist nicht erreichbar:\n{err}", "branch": branch}
    switch = None
    target = MOVED.get(branch)
    if target:
        ref = f"{remote}/{target}"
        if _git(["rev-parse", "--verify", "--quiet", ref], cwd)[0] == 0 \
                and _git(["merge-base", "--is-ancestor", "HEAD", ref], cwd)[0] == 0:
            upstream, switch = ref, target
    note = None
    if channel == "stable":                      # #89: nur offizielle Versionen → bis zum neuesten Versions-Tag
        tag = final_tag_target(cwd)
        if tag and _git(["merge-base", "--is-ancestor", "HEAD", tag], cwd)[0] == 0:
            upstream, switch = tag, None
        else:
            upstream, switch = "HEAD", None
            note = "Du bist auf einem neueren Stand als die letzte offizielle Version (Beta). Die nächste offizielle Version wird angeboten, sobald sie erscheint."
    _, counts, _ = _git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], cwd)
    ahead, behind = (int(x) for x in (counts.split() + ["0", "0"])[:2])
    _, log, _ = _git(["log", "--format=%s", f"HEAD..{upstream}"], cwd)
    _, dirty, _ = _git(["status", "--porcelain", "--untracked-files=no"], cwd)
    _, cur, _ = _git(["log", "-1", "--format=%h · %cd", "--date=format:%d.%m.%Y %H:%M"], cwd)
    return {"ok": True, "error": None, "branch": branch, "upstream": upstream, "behind": behind, "ahead": ahead,
            "commits": [c for c in log.splitlines() if c][:30], "dirty": [d.split(maxsplit=1)[-1] for d in dirty.splitlines() if d.strip()],
            "current": cur, "switch": switch, "channel": channel, "note": note}


def pull(cwd=HERE, channel: str = "beta") -> dict:
    """Holt die neue Version (nur Vorspulen). → {"ok", "message"}"""
    st = status(fetch=True, cwd=cwd, channel=channel)
    if not st.get("ok"):
        return {"ok": False, "message": st.get("error")}
    if not st["behind"] and not st.get("switch"):
        return {"ok": True, "message": "Bereits auf dem neuesten Stand.", "updated": False}
    if st["dirty"]:
        return {"ok": False, "message": "Im Programmordner gibt es lokale Änderungen – Update abgebrochen:\n"
                + "\n".join(st["dirty"][:10])}
    note = ""
    if st.get("switch"):
        target = st["switch"]
        if _git(["rev-parse", "--verify", "--quiet", f"refs/heads/{target}"], cwd)[0] == 0:
            code, out, err = _git(["switch", target], cwd)
        else:
            code, out, err = _git(["switch", "-c", target, "--track", st["upstream"]], cwd)
        if code != 0:
            return {"ok": False, "message": f"Wechsel auf „{target}“ nicht möglich:\n{err or out}"}
        note = f" Weiter geht es jetzt auf dem Hauptzweig „{target}“."
    code, out, err = _git(["merge", "--ff-only", st["upstream"]], cwd, timeout=120)
    if code != 0:
        return {"ok": False, "message": f"Update nicht möglich:\n{err or out}"}
    return {"ok": True, "message": f"{st['behind']} Änderung(en) geladen.{note}", "updated": True}


# =========================================================================== Versionen und Kanal (#89, #90)
import json as _json
import re as _re

API_RELEASES = "https://api.github.com/repos/MarkusKeller8200/markussxch-tagstudio/releases?per_page=30"
CHANNELS = ("stable", "beta")


def parse_version(v: str):
    """„v3.5.0-beta.2“ → (3, 5, 0, 0, 2); finale Versionen sortieren nach ihren Betas: „3.5.0“ → (3, 5, 0, 1, 0)."""
    m = _re.match(r"^v?(\d+)\.(\d+)\.(\d+)(?:-[A-Za-z]+\.?(\d+))?$", (v or "").strip())
    if not m:
        return None
    a, b, c, n = m.groups()
    return (int(a), int(b), int(c), 0 if n is not None else 1, int(n or 0))


def is_beta(v: str) -> bool:
    return "-" in (v or "")


def fetch_releases(timeout: float = 8.0) -> list:
    """Releases von GitHub (öffentliche API, ohne Anmeldung). Wirft OSError/ValueError, wenn offline."""
    import urllib.request
    req = urllib.request.Request(API_RELEASES, headers={"Accept": "application/vnd.github+json",
                                                        "User-Agent": "MarKusSXCH-TagStudio"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = _json.loads(r.read().decode("utf-8"))
    out = []
    for x in data if isinstance(data, list) else []:
        tag = str(x.get("tag_name") or "")
        if parse_version(tag) is None or x.get("draft"):
            continue
        out.append({"tag": tag, "version": tag.lstrip("v"), "beta": bool(x.get("prerelease")) or is_beta(tag),
                    "url": x.get("html_url") or RELEASES_URL, "notes": str(x.get("body") or ""),
                    "date": str(x.get("published_at") or "")[:10],
                    "assets": [{"name": a.get("name"), "url": a.get("browser_download_url")} for a in x.get("assets") or []]})
    return out


def newest(releases: list, channel: str):
    """Neueste Version für den Kanal: „stable“ nur offizielle, „beta“ auch Vorabversionen."""
    cand = [r for r in releases if channel == "beta" or not r["beta"]]
    return max(cand, key=lambda r: parse_version(r["tag"]), default=None)


def release_check(current: str, channel: str, releases: list | None = None) -> dict:
    """Gibt es eine neuere Version im gewählten Kanal? → {"ok", "newer", "latest", "error"}"""
    try:
        rels = fetch_releases() if releases is None else releases
    except (OSError, ValueError) as ex:
        return {"ok": False, "offline": True, "error": f"GitHub ist nicht erreichbar ({ex.__class__.__name__}).",
                "releases_url": RELEASES_URL}
    top = newest(rels, channel)
    cur = parse_version(current)
    newer = bool(top and cur and parse_version(top["tag"]) > cur)
    note = None
    if channel == "stable" and is_beta(current) and not newer:
        note = "Du verwendest eine Beta-Version. Die nächste offizielle Version wird angeboten, sobald sie erscheint."
    return {"ok": True, "newer": newer, "latest": top, "note": note, "releases_url": RELEASES_URL}


def changelog_section(text: str, ver: str) -> str:
    """Abschnitt einer Version aus dem CHANGELOG; Vorabversionen → „Unveröffentlicht“."""
    if is_beta(ver):
        m = _re.search(r"^## \[Unveröffentlicht\][^\n]*\n(.*?)(?=^## \[|\Z)", text, _re.S | _re.M)
    else:
        m = _re.search(r"^## \[" + _re.escape(ver) + r"\][^\n]*\n(.*?)(?=^## \[|\Z)", text, _re.S | _re.M)
    return m.group(1).strip() if m else ""


def changelog_versions(text: str, skip: str = "") -> list:
    """Alle veröffentlichten Versionen aus dem CHANGELOG (neueste zuerst): [{version, date, notes}].
    „Unveröffentlicht“ und die Version `skip` (die installierte) werden ausgelassen."""
    out = []
    for m in _re.finditer(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, _re.S | _re.M):
        head, body = m.group(1).strip(), m.group(2).strip()
        b = _re.match(r"\[([^\]]+)\](.*)$", head)
        ver, rest = (b.group(1).strip(), b.group(2)) if b else (head, "")   # z. B. „Frühere Versionen als …“
        if ver.lower().startswith("unver") or ver == skip:
            continue
        d = _re.search(r"\d{4}-\d{2}-\d{2}", rest)
        out.append({"version": ver, "date": d.group(0) if d else "", "notes": body})
    return out


def local_changelog() -> str:
    for base in (HERE, getattr(sys, "_MEIPASS", HERE)):
        p = os.path.join(base, "CHANGELOG.md")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                return fh.read()
    return ""


def final_tag_target(cwd=HERE) -> str | None:
    """Git-Modus, Kanal „stable“: neueste offizielle Version (Tag vX.Y.Z) auf GitHub."""
    code, out, _ = _git(["tag", "-l", "v*"], cwd)
    tags = [t for t in out.splitlines() if parse_version(t) and not is_beta(t)] if code == 0 else []
    return max(tags, key=parse_version, default=None)
