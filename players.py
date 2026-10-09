"""MarKusSXCH TagStudio – Titel in einem externen Player öffnen (foobar2000, VLC, Rekordbox, Music …).

Player werden in den Einstellungen als Liste gespeichert: {"name", "cmd", "args"}.
- cmd:  Programm (Pfad zur .exe, unter macOS auch eine .app)
- args: Argumente mit Platzhaltern – {files} alle Dateien (je ein Argument), {file} erste Datei,
        {folder} Ordner der ersten Datei, {m3u} temporäre Playlist (M3U8) mit allen Dateien.
        Standard: „{files}“.
Ohne Player-Angabe wird das Standardprogramm des Systems benutzt. Programme werden immer direkt (ohne Shell)
gestartet. Nur Standardbibliothek.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile

PLACEHOLDERS = ("{files}", "{file}", "{folder}", "{m3u}")


def clean(players) -> list[dict]:
    """Eingaben aus der Oberfläche prüfen und vereinheitlichen."""
    out = []
    for p in players or []:
        if not isinstance(p, dict):
            continue
        name, cmd = str(p.get("name") or "").strip(), str(p.get("cmd") or "").strip().strip('"')
        args = str(p.get("args") if p.get("args") is not None else "{files}").strip()
        if not cmd:
            continue
        base = re.split(r"[\\/]", cmd.rstrip("/\\"))[-1]
        out.append({"name": name or os.path.splitext(base)[0], "cmd": cmd,
                    "args": args or "{files}"})
    return out[:20]


def write_m3u(files, folder=None) -> str:
    fd, path = tempfile.mkstemp(prefix="TagStudio-", suffix=".m3u8", dir=folder)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#EXTM3U\n")
        for f in files:
            fh.write(os.path.abspath(f) + "\n")
    return path


def split_args(args: str) -> list[str]:
    try:
        parts = shlex.split(args, posix=os.name != "nt")
    except ValueError:
        parts = args.split()
    return [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p for p in parts]


def build_command(player: dict, files: list[str], m3u_factory=write_m3u) -> list[str]:
    """Befehlszeile (Liste) für einen Player. Dateien, die mit „-“ beginnen, werden als Pfad übergeben."""
    files = [os.path.abspath(f) for f in files]
    cmd = player["cmd"]
    if sys.platform == "darwin" and cmd.lower().rstrip("/").endswith(".app"):
        return ["open", "-a", cmd, *files]          # macOS-Programm: Dateien über „open -a“
    out = [cmd]
    m3u = None
    for a in split_args(player.get("args") or "{files}"):
        if a == "{files}":
            out.extend(files)
            continue
        if "{m3u}" in a and m3u is None:
            m3u = m3u_factory(files)
        out.append(a.replace("{file}", files[0] if files else "")
                    .replace("{folder}", os.path.dirname(files[0]) if files else "")
                    .replace("{m3u}", m3u or ""))
    return out


def open_files(files: list[str], player: dict | None = None):
    """Dateien öffnen – mit dem angegebenen Player oder dem Standardprogramm."""
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise ValueError("Keine Datei zum Abspielen.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if player is None else 0
    if player:
        cmd = build_command(player, files)
        if not (os.path.isfile(cmd[0]) or os.path.isdir(cmd[0]) or cmd[0] in ("open",) or _which(cmd[0])):
            raise ValueError(f"Programm nicht gefunden: {cmd[0]}")
        subprocess.Popen(cmd, close_fds=True)
        return cmd
    target = files[0] if len(files) == 1 else write_m3u(files)
    if sys.platform.startswith("win"):
        os.startfile(target)  # noqa: S606 – Standardprogramm des Systems
        return ["startfile", target]
    cmd = ["open" if sys.platform == "darwin" else "xdg-open", target]
    subprocess.Popen(cmd, close_fds=True, creationflags=flags)
    return cmd


def _which(name):
    import shutil
    return shutil.which(name)
