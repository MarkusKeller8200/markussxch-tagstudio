"""
updater.py – neue Version von GitHub holen (git fetch / git pull im Programmordner).

Funktioniert, wenn der Programmordner ein Git-Repository ist und git installiert ist.
Es wird nur „vorgespult“ (--ff-only): lokale Änderungen werden nie überschrieben.
"""
from __future__ import annotations

import os
import re
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


_DEV: dict = {}


def dev_info(version: str, cwd=HERE) -> dict:
    """Developer Release (Entscheid 16.10.2026): Quellcode mit Änderungen nach dem Tag der laufenden Version
    (v<VERSION>), also eingecheckt, aber weder Beta noch Release. → {"dev", "commits", "sha", "base"}.
    Installierte App, kein Git oder kein passender Tag → nicht als Developer Release kennzeichnen, ausser der Tag der
    eigenen Version fehlt noch (Stand vor dem Release) – dann zählt die Nähe zum letzten Versions-Tag."""
    key = (version, str(cwd))
    if key in _DEV:
        return _DEV[key]
    out = {"dev": False, "commits": 0, "sha": "", "base": ""}
    if not frozen() and available(cwd) is None:
        code, desc, _ = _git(["describe", "--tags", "--long", "--match", "v[0-9]*"], cwd, timeout=10)
        m = re.match(r"^(v.+)-(\d+)-g([0-9a-f]+)$", desc) if code == 0 else None
        if m:
            base, n, sha = m.group(1), int(m.group(2)), m.group(3)
            out = {"dev": n > 0 or base != f"v{version}", "commits": n, "sha": sha, "base": base[1:]}
    out["planned"] = planned_version(version) if out["dev"] else version
    _DEV[key] = out
    return out


def planned_version(version: str) -> str:
    """#233: Version, auf die die Entwicklung zuläuft – für die Anzeige „Developer Release“.
    version_next.NEXT (wenn grösser als die aktuelle), sonst laufende Beta ohne Zusatz, sonst nächste Minor-Version."""
    try:
        import version_next
        nxt = str(getattr(version_next, "NEXT", "") or "").strip()
    except ImportError:
        nxt = ""
    cur = parse_version(version)
    if nxt and parse_version(nxt) and cur and parse_version(nxt) > cur:
        return nxt
    m = _re.match(r"^(\d+)\.(\d+)\.(\d+)(-.+)?$", version or "")
    if not m:
        return version
    a, b, c, pre = m.groups()
    return f"{a}.{b}.{c}" if pre else f"{a}.{int(b) + 1}.0"


def status(fetch: bool = True, cwd=HERE, channel: str = "dev") -> dict:
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
    if channel in ("stable", "beta"):            # #89/#233: nur veröffentlichte Versionen (Tags) – nie der Entwicklungsstand
        tag = final_tag_target(cwd, include_beta=channel == "beta")
        if tag and _git(["merge-base", "--is-ancestor", "HEAD", tag], cwd)[0] == 0:
            upstream, switch = tag, None
        else:
            upstream, switch = "HEAD", None
            note = ("Du bist auf einem neueren Stand als die letzte veröffentlichte Version. Die nächste Version wird "
                    "angeboten, sobald sie erscheint.")
    _, counts, _ = _git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], cwd)
    ahead, behind = (int(x) for x in (counts.split() + ["0", "0"])[:2])
    _, log, _ = _git(["log", "--format=%s", f"HEAD..{upstream}"], cwd)
    _, dirty, _ = _git(["status", "--porcelain", "--untracked-files=no"], cwd)
    _, cur, _ = _git(["log", "-1", "--format=%h · %cd", "--date=format:%d.%m.%Y %H:%M"], cwd)
    return {"ok": True, "error": None, "branch": branch, "upstream": upstream, "behind": behind, "ahead": ahead,
            "commits": [c for c in log.splitlines() if c][:30], "dirty": [d.split(maxsplit=1)[-1] for d in dirty.splitlines() if d.strip()],
            "current": cur, "switch": switch, "channel": channel, "note": note}


def pull(cwd=HERE, channel: str = "dev") -> dict:
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
CHANNELS = ("stable", "beta", "dev")    # dev = Entwicklungsstand (main), nur im Quellcode (#233)


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
                    "assets": [{"name": a.get("name"), "url": a.get("browser_download_url"), "size": a.get("size") or 0,
                                "digest": str(a.get("digest") or "")} for a in x.get("assets") or []]})
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


def final_tag_target(cwd=HERE, include_beta: bool = False) -> str | None:
    """Git-Modus: neueste veröffentlichte Version (Tag vX.Y.Z; mit include_beta auch vX.Y.Z-beta.N) auf GitHub."""
    code, out, _ = _git(["tag", "-l", "v*"], cwd)
    tags = [t for t in out.splitlines() if parse_version(t) and (include_beta or not is_beta(t))] if code == 0 else []
    return max(tags, key=parse_version, default=None)


# =========================================================================== #234: Update auf Knopfdruck (installierte App)
ASSET_HOST = "https://github.com/MarkusKeller8200/markussxch-tagstudio/releases/download/"


def mac_arch_label(machine: str | None = None) -> str:
    """Teil des DMG-Namens je Prozessor (packaging/make_dmg.sh): „Apple-Chip“ (arm64) oder „Intel“."""
    import platform as _pf
    m = (machine or _pf.machine() or "").lower()
    return "Apple-Chip" if m in ("arm64", "aarch64") else "Intel"


def platform_asset(release: dict, platform: str | None = None, machine: str | None = None):
    """Installer des Releases für dieses System: Windows .exe, macOS .dmg passend zum Prozessor (Apple-Chip/Intel;
    ältere Releases ohne Kennzeichen: erstes .dmg). → Asset-Dict oder None."""
    plat = platform or sys.platform
    assets = release.get("assets") or []
    if plat.startswith("win"):
        return next((a for a in assets if _re.search(r"\.exe$", a.get("name") or "", _re.I)), None)
    if plat != "darwin":
        return None
    dmgs = [a for a in assets if _re.search(r"\.dmg$", a.get("name") or "", _re.I)]
    label = mac_arch_label(machine)
    exact = [a for a in dmgs if label.lower() in (a.get("name") or "").lower()]
    if exact:
        return exact[0]
    tagged = [a for a in dmgs if _re.search(r"apple-chip|intel", a.get("name") or "", _re.I)]
    return None if tagged else (dmgs[0] if dmgs else None)    # nur andere Architektur vorhanden → keins


def mac_bundle(exe: str | None = None) -> str:
    """Pfad der laufenden TagStudio.app (aus …/TagStudio.app/Contents/MacOS/TagStudio) oder ""."""
    p = os.path.abspath(exe or sys.executable)
    for _ in range(4):
        p = os.path.dirname(p)
        if p.endswith(".app"):
            return p
    return ""


def auto_update_supported(platform: str | None = None) -> bool:
    """Update auf Knopfdruck in der installierten App: Windows (#234) und macOS (#251)."""
    plat = platform or sys.platform
    return frozen() and (plat.startswith("win") or plat == "darwin")


def download_asset(asset: dict, dest_dir: str, progress=None, cancelled=None, opener=None) -> str:
    """Installer laden und die SHA-256-Prüfsumme von GitHub („digest“) prüfen. → Pfad der Datei.
    Nur Adressen aus den Releases dieses Repos; ohne Prüfsumme oder bei Abweichung: ValueError (nichts installieren)."""
    import hashlib
    import urllib.request
    url, name = str(asset.get("url") or ""), os.path.basename(str(asset.get("name") or ""))
    if not url.startswith(ASSET_HOST) or not name or name in (".", ".."):
        raise ValueError("Unerwartete Download-Adresse – Update abgebrochen.")
    want = str(asset.get("digest") or "")
    if not want.lower().startswith("sha256:"):
        raise ValueError("GitHub liefert für diese Datei keine Prüfsumme – bitte den Installer von Hand laden.")
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, name)
    part = path + ".part"
    h, done, total = hashlib.sha256(), 0, int(asset.get("size") or 0)
    req = urllib.request.Request(url, headers={"User-Agent": "MarKusSXCH-TagStudio"})
    op = opener or urllib.request.urlopen
    with op(req, timeout=30) as r, open(part, "wb") as fh:
        total = total or int(r.headers.get("Content-Length") or 0)
        while True:
            if cancelled and cancelled():
                raise InterruptedError("Abgebrochen.")
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    got = "sha256:" + h.hexdigest()
    if got.lower() != want.lower():
        os.remove(part)
        raise ValueError("Prüfsumme stimmt nicht – die Datei ist unvollständig oder verändert. Nichts installiert.")
    os.replace(part, path)
    return path


def windows_update_script(installer: str, pid: int, exe: str, log: str, all_users: bool) -> str:
    """PowerShell: wartet, bis TagStudio beendet ist, installiert still und startet TagStudio neu.
    PowerShell statt Batch, weil Pfade mit Umlauten (Benutzername) sonst an der Codepage scheitern."""
    q = lambda s: "'" + str(s).replace("'", "''") + "'"   # noqa: E731 – PowerShell-Zeichenkette
    mode = "/ALLUSERS" if all_users else "/CURRENTUSER"
    args = ", ".join(q(x) for x in ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/SP-", mode,
                                    f'/LOG="{log}"'))
    return "\n".join([
        "# TagStudio - Update auf Knopfdruck (#234)",
        f"$p = {int(pid)}",
        "while (Get-Process -Id $p -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 500 }",
        f"$r = Start-Process -FilePath {q(installer)} -ArgumentList {args} -Wait -PassThru",
        f"Start-Process -FilePath {q(exe)}",
        "exit $r.ExitCode",
    ])


def mac_update_script(dmg: str, pid: int, bundle: str, log: str, backup: str) -> str:
    """bash: wartet, bis TagStudio beendet ist, hängt das DMG ein, ersetzt die App (die alte bleibt als Sicherung, bei
    einem Fehler wird sie zurückgelegt), entfernt die Quarantäne-Markierung und startet TagStudio neu (#251)."""
    q = lambda s: "'" + str(s).replace("'", "'\\''") + "'"      # noqa: E731 – bash-Zeichenkette
    return "\n".join([
        "#!/bin/bash",
        "# TagStudio - Update auf Knopfdruck (macOS, #251)",
        f"DMG={q(dmg)}; APP={q(bundle)}; BAK={q(backup)}; LOG={q(log)}; PID={int(pid)}",
        'exec >>"$LOG" 2>&1',
        'echo "== $(date) Update aus $DMG"',
        'for i in $(seq 1 240); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done',
        'MNT="$(mktemp -d "${TMPDIR:-/tmp}/tagstudio-update.XXXXXX")"',
        'fail() { echo "FEHLER: $1"; [ -d "$BAK/TagStudio.app" ] && [ ! -d "$APP" ] && mv "$BAK/TagStudio.app" "$APP"; '
        'hdiutil detach "$MNT" -quiet 2>/dev/null; open "$APP"; exit 1; }',
        'hdiutil attach "$DMG" -nobrowse -readonly -noautoopen -mountpoint "$MNT" || fail "DMG nicht einhängbar"',
        'NEW="$MNT/TagStudio.app"',
        '[ -d "$NEW" ] || fail "TagStudio.app fehlt im DMG"',
        'mkdir -p "$BAK" && rm -rf "$BAK/TagStudio.app"',
        'mv "$APP" "$BAK/TagStudio.app" || fail "alte Version nicht verschiebbar (Schreibrechte?)"',
        'ditto "$NEW" "$APP" || { rm -rf "$APP"; fail "Kopieren fehlgeschlagen"; }',
        'hdiutil detach "$MNT" -quiet || true',
        'xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true',
        'echo "OK – starte $APP"',
        'open "$APP"',
    ]) + "\n"


def launch_mac_update(dmg: str, data_dir: str, bundle: str | None = None) -> str:
    """Skript unabhängig vom laufenden Prozess starten. → Pfad des Protokolls."""
    import subprocess
    bundle = bundle or mac_bundle()
    if not bundle:
        raise RuntimeError("Die laufende TagStudio.app wurde nicht gefunden.")
    if not os.access(os.path.dirname(bundle), os.W_OK):
        raise RuntimeError(f"Keine Schreibrechte für {os.path.dirname(bundle)} – bitte das DMG von Hand installieren.")
    log = os.path.join(data_dir, "update-installer.log")
    script = os.path.join(data_dir, "update.sh")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(mac_update_script(dmg, os.getpid(), bundle, log, os.path.join(data_dir, "vorherige-Version")))
    os.chmod(script, 0o700)
    env = dict(os.environ, PATH="/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", ""))
    subprocess.Popen(["/bin/bash", script], cwd=data_dir, close_fds=True, start_new_session=True, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return log


def launch_windows_update(installer: str, data_dir: str) -> str:
    """Skript unabhängig vom laufenden Prozess starten (verborgen). → Pfad des Installer-Protokolls."""
    import base64
    import subprocess
    exe = sys.executable
    local = os.environ.get("LOCALAPPDATA", "")
    all_users = not (local and os.path.normcase(os.path.abspath(exe)).startswith(os.path.normcase(os.path.abspath(local))))
    log = os.path.join(data_dir, "update-installer.log")
    script = windows_update_script(installer, os.getpid(), exe, log, all_users)
    with open(os.path.join(data_dir, "update.ps1"), "w", encoding="utf-8") as fh:     # nur zur Nachvollziehbarkeit
        fh.write(script)
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    flags = 0x00000008 | 0x00000200 | 0x08000000      # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                      "-EncodedCommand", enc], cwd=data_dir, close_fds=True, creationflags=flags)
    return log
