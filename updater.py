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


def _git(args, cwd=HERE, timeout=60):
    kw = {}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW: kein Konsolenfenster aufblitzen lassen
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace", **kw)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def available(cwd=HERE) -> str | None:
    """None, wenn Updates möglich sind – sonst der Grund, warum nicht."""
    if shutil.which("git") is None:
        return "Git ist auf diesem Rechner nicht installiert."
    code, out, _ = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if code != 0 or out != "true":
        return "Der Programmordner ist kein Git-Repository."
    return None


def status(fetch: bool = True, cwd=HERE) -> dict:
    """Vergleicht den lokalen Stand mit GitHub.
    → {"ok", "error", "branch", "behind", "ahead", "commits": [Betreff…], "dirty": [Dateien…], "current"}"""
    err = available(cwd)
    if err:
        return {"ok": False, "error": err}
    code, branch, _ = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if code != 0 or branch == "HEAD":
        return {"ok": False, "error": "Kein Zweig ausgecheckt."}
    code, upstream, _ = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd)
    if code != 0:
        return {"ok": False, "error": f"Der Zweig „{branch}“ ist nicht mit GitHub verbunden.", "branch": branch}
    if fetch:
        remote = upstream.split("/", 1)[0]
        code, _, err = _git(["fetch", "--quiet", remote], cwd, timeout=90)
        if code != 0:
            return {"ok": False, "error": f"GitHub ist nicht erreichbar:\n{err}", "branch": branch}
    _, counts, _ = _git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], cwd)
    ahead, behind = (int(x) for x in (counts.split() + ["0", "0"])[:2])
    _, log, _ = _git(["log", "--format=%s", f"HEAD..{upstream}"], cwd)
    _, dirty, _ = _git(["status", "--porcelain", "--untracked-files=no"], cwd)
    _, cur, _ = _git(["log", "-1", "--format=%h · %cd", "--date=format:%d.%m.%Y %H:%M"], cwd)
    return {"ok": True, "error": None, "branch": branch, "upstream": upstream, "behind": behind, "ahead": ahead,
            "commits": [c for c in log.splitlines() if c][:30], "dirty": [d.split(maxsplit=1)[-1] for d in dirty.splitlines() if d.strip()],
            "current": cur}


def pull(cwd=HERE) -> dict:
    """Holt die neue Version (nur Vorspulen). → {"ok", "message"}"""
    st = status(fetch=True, cwd=cwd)
    if not st.get("ok"):
        return {"ok": False, "message": st.get("error")}
    if not st["behind"]:
        return {"ok": True, "message": "Bereits auf dem neuesten Stand.", "updated": False}
    if st["dirty"]:
        return {"ok": False, "message": "Im Programmordner gibt es lokale Änderungen – Update abgebrochen:\n"
                + "\n".join(st["dirty"][:10])}
    code, out, err = _git(["merge", "--ff-only", st["upstream"]], cwd, timeout=120)
    if code != 0:
        return {"ok": False, "message": f"Update nicht möglich:\n{err or out}"}
    return {"ok": True, "message": f"{st['behind']} Änderung(en) geladen.", "updated": True}
