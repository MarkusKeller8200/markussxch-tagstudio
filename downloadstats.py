"""MarKusSXCH TagStudio – Download-Statistik der Installationsdateien (#370).

GitHub zählt je Release-Datei nur die Gesamtzahl der Downloads (``download_count``), ohne Verlauf. Darum:

* ``fetch()`` holt alle Releases (öffentliche API, ohne Anmeldung) und ``summarize()`` fasst sie je Version zusammen:
  Windows-Setup, macOS-DMG, Plugin-ZIPs.
* Der Workflow „Download-Statistik“ ruft ``python downloadstats.py --update <Datei>`` täglich auf und speichert die
  Zählerstände je Tag im Zweig ``stats`` (``docs/download-stats.json``) – daraus berechnet ``history()`` die neuen
  Downloads je Tag. TagStudio liest die Datei über ``STATS_URL`` (fehlt sie, gibt es nur die Gesamtsummen).

Datei: {"format": 1, "days": {"2026-10-26": {"v4.12.0": [win, mac, plugins], …}, …}}
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import urllib.request

REPO = "MarkusKeller8200/markussxch-tagstudio"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={{page}}"
STATS_URL = f"https://raw.githubusercontent.com/{REPO}/stats/docs/download-stats.json"
RELEASES_URL = f"https://github.com/{REPO}/releases"
UA = "MarKusSXCH-TagStudio"
KEEP_DAYS = 800


def kind(name: str) -> str:
    """Art einer Release-Datei: win | mac | plugin | other."""
    n = str(name or "").lower()
    if n.endswith(".exe") or n.endswith(".msi"):
        return "win"
    if n.endswith(".dmg") or n.endswith(".pkg"):
        return "mac"
    if n.startswith("plugin-") and n.endswith(".zip"):
        return "plugin"
    return "other"


def _get(url: str, token: str = "", timeout: float = 10.0):
    h = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if token:
        h["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch(token: str = "", timeout: float = 10.0, get=None) -> list:
    """Alle Releases (auch Vorabversionen, keine Entwürfe) → [{tag, date, beta, url, assets: [{name, kind, count}]}]"""
    get = get or (lambda u: _get(u, token, timeout))
    out = []
    for page in range(1, 11):
        data = get(API.format(page=page))
        if not isinstance(data, list) or not data:
            break
        for x in data:
            if x.get("draft"):
                continue
            out.append({"tag": str(x.get("tag_name") or ""), "date": str(x.get("published_at") or "")[:10],
                        "beta": bool(x.get("prerelease")), "url": str(x.get("html_url") or RELEASES_URL),
                        "assets": [{"name": str(a.get("name") or ""), "kind": kind(a.get("name")),
                                    "count": int(a.get("download_count") or 0)} for a in x.get("assets") or []]})
        if len(data) < 100:
            break
    return out


def counts(rel: dict) -> list:
    """[Windows, macOS, Plugins] einer Version."""
    c = {"win": 0, "mac": 0, "plugin": 0}
    for a in rel.get("assets") or []:
        if a["kind"] in c:
            c[a["kind"]] += a["count"]
    return [c["win"], c["mac"], c["plugin"]]


def summarize(releases: list) -> dict:
    """Je Version und gesamt → {rows: [{tag, date, beta, url, win, mac, plugins, total, files}], total: {…}}"""
    rows, tot = [], {"win": 0, "mac": 0, "plugins": 0, "installers": 0}
    for r in releases:
        w, m, p = counts(r)
        rows.append({"tag": r["tag"], "date": r["date"], "beta": r["beta"], "url": r["url"], "win": w, "mac": m,
                     "plugins": p, "total": w + m,
                     "files": [{"name": a["name"], "count": a["count"]} for a in r["assets"] if a["kind"] in ("win", "mac")]})
        tot["win"] += w
        tot["mac"] += m
        tot["plugins"] += p
    tot["installers"] = tot["win"] + tot["mac"]
    return {"rows": rows, "total": tot}


def snapshot(releases: list) -> dict:
    return {r["tag"]: counts(r) for r in releases if r["tag"]}


def update(data: dict | None, releases: list, day: str | None = None) -> dict:
    """Zählerstand des Tages eintragen (ein Eintrag je Tag, späterer Lauf ersetzt ihn); alte Tage kürzen."""
    data = data if isinstance(data, dict) and isinstance(data.get("days"), dict) else {"format": 1, "days": {}}
    day = day or datetime.date.today().isoformat()
    data["days"][day] = snapshot(releases)
    for d in sorted(data["days"])[:-KEEP_DAYS]:
        del data["days"][d]
    data["format"] = 1
    return data


def history(data: dict | None, today: str | None = None) -> dict:
    """Neue Installer-Downloads je Tag aus den Zählerständen → {days: [{day, win, mac, total}], last7, last30, since}"""
    days = sorted(((data or {}).get("days") or {}).items())
    out, prev = [], None
    for day, snap in days:
        tot = [sum((v or [0, 0, 0])[i] for v in snap.values()) for i in range(2)]
        if prev is not None:
            dw, dm = max(0, tot[0] - prev[0]), max(0, tot[1] - prev[1])
            out.append({"day": day, "win": dw, "mac": dm, "total": dw + dm})
        prev = tot
    today = datetime.date.fromisoformat(today) if today else datetime.date.today()
    def last(n):
        start = (today - datetime.timedelta(days=n)).isoformat()
        return sum(x["total"] for x in out if x["day"] > start)
    return {"days": out[-60:], "last7": last(7), "last30": last(30), "since": days[0][0] if days else ""}


def load_stats(timeout: float = 8.0, get=None):
    """Verlauf aus dem Zweig „stats“ – None, wenn es ihn (noch) nicht gibt."""
    try:
        return (get or (lambda u: _get(u, "", timeout)))(STATS_URL)
    except (OSError, ValueError):
        return None


def report(timeout: float = 10.0) -> dict:
    """Für die Oberfläche: Zusammenfassung + Verlauf. Wirft OSError, wenn GitHub nicht erreichbar ist."""
    s = summarize(fetch(timeout=timeout))
    h = history(load_stats(timeout))
    return {**s, "history": h, "releases_url": RELEASES_URL}


def main(argv) -> int:
    """Workflow: python downloadstats.py --update docs/download-stats.json"""
    if len(argv) != 3 or argv[1] != "--update":
        print(main.__doc__)
        return 2
    path = argv[2]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        data = None
    rel = fetch(os.environ.get("GITHUB_TOKEN", ""))
    data = update(data, rel)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    s = summarize(rel)["total"]
    print(f"{len(rel)} Releases · Installer {s['installers']} (Windows {s['win']}, macOS {s['mac']}) · Plugins {s['plugins']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
