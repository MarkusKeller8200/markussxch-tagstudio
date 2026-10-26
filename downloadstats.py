"""MarKusSXCH TagStudio – Download-Statistik der Installationsdateien (#370).

GitHub zählt je Release-Datei nur die Gesamtzahl der Downloads (``download_count``), ohne Verlauf. Darum:

* ``fetch()`` holt alle Releases (öffentliche API, ohne Anmeldung) und ``summarize()`` fasst sie je Version zusammen:
  Windows-Setup, macOS-DMG, Plugin-ZIPs.
* Der Workflow „Download-Statistik“ ruft ``python downloadstats.py --update <Datei>`` täglich auf und speichert die
  Zählerstände je Tag im Zweig ``stats`` (``docs/download-stats.json``) – daraus berechnet ``history()`` die neuen
  Downloads je Tag. TagStudio liest die Datei über ``STATS_URL`` (fehlt sie, gibt es nur die Gesamtsummen).

Datei: {"format": 1, "days": {"2026-10-26": {"v4.12.0": [win, mac, plugins], …}, …}}

#371: Daneben ``summary.json`` (je Version) und ``badge.json`` (shields.io-Endpunkt) für die Statistik-Seite und das
Abzeichen. #372: ``download_block``/``apply_block`` setzen oben in die Versionshinweise einen Kasten mit direkten
Download-Links (``--release-notes``); ``strip_block`` entfernt ihn wieder (Anzeige in TagStudio).
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
                        "id": x.get("id"), "body": str(x.get("body") or ""),
                        "assets": [{"name": str(a.get("name") or ""), "kind": kind(a.get("name")),
                                    "count": int(a.get("download_count") or 0), "size": int(a.get("size") or 0),
                                    "url": str(a.get("browser_download_url") or "")} for a in x.get("assets") or []]})
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


def badge(summary: dict) -> dict:
    """#371: shields.io-Endpunkt (nur Installer)."""
    return {"schemaVersion": 1, "label": "Downloads", "message": f"{summary['total']['installers']:,}".replace(",", "'"),
            "color": "1D76DB", "cacheSeconds": 3600}


def write_site(folder: str, releases: list, data: dict) -> None:
    """#371: summary.json und badge.json neben download-stats.json schreiben (für Statistik-Seite und Abzeichen)."""
    s = summarize(releases)
    s["history"] = history(data)
    s["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    s["releases_url"] = RELEASES_URL
    for name, obj in (("summary.json", s), ("badge.json", badge(s))):
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.write("\n")


# =========================================================================== #372: Download-Kasten in den Versionshinweisen
BLOCK_START = "<!-- tagstudio-downloads:start -->"
BLOCK_END = "<!-- tagstudio-downloads:end -->"
_OLD_LINE = "**Download:** Windows →"


def _mb(n: int) -> str:
    return f"{n / 1048576:.0f} MB" if n >= 1048576 else f"{max(1, round(n / 1024))} KB"


def download_block(rel: dict) -> str:
    """Kasten mit direkten Links: Installer oben, Plugins zugeklappt. "" ohne Installer."""
    inst = [a for a in rel["assets"] if a["kind"] in ("win", "mac") and a.get("url")]
    if not inst:
        return ""
    label = {"win": "Windows", "mac": "macOS (Apple-Chip)"}
    lines = [BLOCK_START, "## ⬇ Download", "", "| | |", "|---|---|"]
    for a in sorted(inst, key=lambda a: a["kind"] != "win"):
        lines.append(f"| **{label[a['kind']]}** | [{a['name']}]({a['url']}) · {_mb(a.get('size') or 0)} |")
    plug = [a for a in rel["assets"] if a["kind"] == "plugin" and a.get("url")]
    if plug:
        lines += ["", f"<details><summary>Plugins ({len(plug)}) – TagStudio bietet sie unter „Plugins“ selbst an, "
                      "einzeln laden nur bei Bedarf</summary>", ""]
        lines += [f"- [{a['name']}]({a['url']})" for a in sorted(plug, key=lambda a: a["name"])]
        lines += ["", "</details>"]
    lines += ["", BLOCK_END]
    return "\n".join(lines)


def strip_block(body: str) -> str:
    """Kasten (und die alte Zeile „**Download:** …“) aus den Versionshinweisen entfernen."""
    s = str(body or "")
    while BLOCK_START in s and BLOCK_END in s:
        a, b = s.index(BLOCK_START), s.index(BLOCK_END) + len(BLOCK_END)
        s = s[:a] + s[b:]
    return s.lstrip("\r\n")


def apply_block(body: str, block: str) -> str:
    """Kasten oben einsetzen bzw. ersetzen; die alte allgemeine Zeile „**Download:** …“ fällt weg."""
    rest = strip_block(body)
    rest = "\n".join(l for l in rest.split("\n") if not l.startswith(_OLD_LINE)).lstrip("\r\n")
    return (block + "\n\n" + rest) if block else rest


def update_release_notes(releases: list, token: str, patch=None, log=print) -> int:
    """Alle Releases mit Installern prüfen und den Kasten setzen, wo er fehlt oder abweicht → Anzahl geändert."""
    def _patch(rid, body):
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/{rid}", method="PATCH",
                                     data=json.dumps({"body": body}).encode("utf-8"),
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": UA,
                                              "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
    patch = patch or _patch
    n = 0
    for r in releases:
        blk = download_block(r)
        if not blk or not r.get("id"):
            continue
        new = apply_block(r.get("body", ""), blk)
        if new.strip() != str(r.get("body") or "").strip():
            patch(r["id"], new)
            n += 1
            log(f"Download-Kasten gesetzt: {r['tag']}")
    return n


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
    """Workflow: python downloadstats.py --update docs/download-stats.json   (dazu summary.json, badge.json)
              python downloadstats.py --release-notes                     (Download-Kasten oben, braucht GITHUB_TOKEN)"""
    if len(argv) == 2 and argv[1] == "--release-notes":
        tok = os.environ.get("GITHUB_TOKEN", "")
        if not tok:
            print("GITHUB_TOKEN fehlt.")
            return 2
        n = update_release_notes(fetch(tok), tok)
        print(f"{n} Release(s) angepasst.")
        return 0
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
    write_site(os.path.dirname(os.path.abspath(path)), rel, data)
    s = summarize(rel)["total"]
    print(f"{len(rel)} Releases · Installer {s['installers']} (Windows {s['win']}, macOS {s['mac']}) · Plugins {s['plugins']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
