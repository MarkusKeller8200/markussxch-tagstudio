"""Prüfungen vor dem Veröffentlichen eines Releases (#406, #407) – läuft im Workflow „Installer“, Job „release“.

    python3 .github/scripts/release_checks.py sums assets            → assets/SHA256SUMS.txt (alle Dateien)
    python3 .github/scripts/release_checks.py virustotal assets/*.exe assets/*.dmg
        → schreibt virustotal.md (Zeilen für die Versionshinweise); Exit 1, wenn ein Scanner etwas meldet
          (dann wird das Release **nicht** erstellt). Ohne Secret VIRUSTOTAL_API_KEY: Hinweis, Exit 0.

VirusTotal-API v3 (öffentlicher Schlüssel: 4 Anfragen/Minute, nur nicht-kommerziell): Dateien bis 32 MB direkt,
grössere über eine Upload-Adresse (bis 650 MB); danach wird die Analyse alle 20 s abgefragt (höchstens 20 Minuten).
Hinweis: SmartScreen nutzt diese Prüfung laut Microsoft nicht – sie ist ein Vertrauenszeichen für die Nutzer.
Nur Standardbibliothek.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

SUMS = "SHA256SUMS.txt"
VT = "https://www.virustotal.com/api/v3"
SMALL = 32 * 1024 * 1024
POLL, MAX_WAIT = 20, 20 * 60


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sums(folder: str) -> str:
    """SHA256SUMS.txt im Format von ``sha256sum`` (Hash, zwei Leerzeichen, Dateiname), sortiert."""
    names = sorted(n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n)) and n != SUMS)
    text = "".join(f"{sha256(os.path.join(folder, n))}  {n}\n" for n in names)
    with open(os.path.join(folder, SUMS), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return text


# --------------------------------------------------------------------------- VirusTotal
def _req(method: str, url: str, key: str, data: bytes | None = None, ctype: str = "", opener=None) -> dict:
    h = {"x-apikey": key, "accept": "application/json"}
    if ctype:
        h["content-type"] = ctype
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    op = opener or urllib.request.urlopen
    try:
        with op(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as ex:
        body = ex.read().decode("utf-8", "replace") if hasattr(ex, "read") else ""
        raise RuntimeError(f"VirusTotal HTTP {ex.code}: {body[:200]}") from ex


def _multipart(path: str) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    with open(path, "rb") as fh:
        data = fh.read()
    head = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
    return head + data + f"\r\n--{b}--\r\n".encode("ascii"), f"multipart/form-data; boundary={b}"


def scan(path: str, key: str, opener=None, sleep=time.sleep, log=print) -> dict:
    """Datei hochladen und auf das Ergebnis warten → {"name", "sha256", "stats", "link"}."""
    body, ctype = _multipart(path)
    url = f"{VT}/files"
    if os.path.getsize(path) > SMALL:
        url = _req("GET", f"{VT}/files/upload_url", key, opener=opener).get("data") or ""
        if not url.startswith("https://"):
            raise RuntimeError("VirusTotal: keine Upload-Adresse erhalten")
    aid = (_req("POST", url, key, body, ctype, opener=opener).get("data") or {}).get("id")
    if not aid:
        raise RuntimeError("VirusTotal: keine Analyse-ID erhalten")
    waited = 0
    while True:
        a = _req("GET", f"{VT}/analyses/{aid}", key, opener=opener).get("data") or {}
        attr = a.get("attributes") or {}
        if attr.get("status") == "completed":
            sha = sha256(path)
            return {"name": os.path.basename(path), "sha256": sha, "stats": attr.get("stats") or {},
                    "link": f"https://www.virustotal.com/gui/file/{sha}"}
        if waited >= MAX_WAIT:
            raise RuntimeError(f"VirusTotal: Analyse von {os.path.basename(path)} nach {MAX_WAIT // 60} Minuten nicht fertig")
        log(f"VirusTotal: {os.path.basename(path)} – {attr.get('status') or 'warte'} …")
        sleep(POLL)
        waited += POLL


def flagged(stats: dict) -> int:
    return int(stats.get("malicious") or 0) + int(stats.get("suspicious") or 0)


def report_md(results: list[dict]) -> str:
    lines = []
    for r in results:
        st = r["stats"]
        total = sum(int(v or 0) for v in st.values())
        clean = total - flagged(st)
        lines.append(f"- **VirusTotal** `{r['name']}`: {clean}/{total} Scanner unauffällig – [Bericht]({r['link']})")
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "sums":
        print(write_sums(argv[1]), end="")
        return 0
    if argv and argv[0] == "virustotal":
        key = os.environ.get("VIRUSTOTAL_API_KEY", "").strip()
        files = [f for f in argv[1:] if os.path.isfile(f)]
        if not key:
            print("::notice title=VirusTotal::Kein Secret VIRUSTOTAL_API_KEY – Prüfung übersprungen")
            open("virustotal.md", "w", encoding="utf-8").close()
            return 0
        results, bad = [], []
        for f in files:
            r = scan(f, key)
            results.append(r)
            if flagged(r["stats"]):
                bad.append(r)
        with open("virustotal.md", "w", encoding="utf-8") as fh:
            fh.write(report_md(results))
        for r in bad:
            print(f"::error title=VirusTotal::{r['name']}: {flagged(r['stats'])} Scanner melden etwas – Release angehalten "
                  f"({r['link']})")
        return 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
