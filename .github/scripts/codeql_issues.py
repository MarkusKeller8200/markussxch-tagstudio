"""CodeQL-Funde als GitHub-Issues führen (läuft im Workflow „CodeQL“ nach der Analyse).

    python .github/scripts/codeql_issues.py <sarif-ordner> <sprache>

- Neuer Fund → Issue „CodeQL: <Regel> – <Datei>:<Zeile>“ mit Labels bug, security, codeql und dem nächsten
  offenen Patch-Milestone (z. B. „3.1.1“).
- Fund nicht mehr vorhanden (nur bei Push auf main) → Issue wird mit Hinweis geschlossen.
- Wiedererkennung über einen unsichtbaren Marker im Issue-Text (Regel + Datei + Zeilen-Fingerabdruck), damit ein
  Fund auch bei verschobenen Zeilen nicht doppelt angelegt wird.
Nur Standardbibliothek; nutzt die GitHub-REST-API mit GITHUB_TOKEN.
"""
import glob
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
SHA = os.environ.get("GITHUB_SHA", "")
SERVER = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
MARK = re.compile(r"<!-- codeql:(\S+) lang:(\S+) -->")


def gh(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tagstudio-codeql"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            return json.loads(data) if data else None
    except urllib.error.HTTPError as ex:
        print(f"::warning::GitHub-API {method} {path}: {ex.code} {ex.read()[:300]!r}")
        return None


def results(sarif_dir):
    """Alle Funde aus den SARIF-Dateien: dict fp → Infos."""
    out = {}
    for path in glob.glob(os.path.join(sarif_dir, "*.sarif")):
        with open(path, encoding="utf-8") as fh:
            sarif = json.load(fh)
        for run in sarif.get("runs", []):
            rules = {r.get("id"): r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
            for res in run.get("results", []):
                if res.get("suppressions"):
                    continue
                rid = res.get("ruleId", "?")
                rule = rules.get(rid, {})
                loc = (res.get("locations") or [{}])[0].get("physicalLocation", {})
                file = loc.get("artifactLocation", {}).get("uri", "?")
                line = loc.get("region", {}).get("startLine", 0)
                lhash = (res.get("partialFingerprints") or {}).get("primaryLocationLineHash", f"{line}")
                fp = hashlib.sha1(f"{rid}|{file}|{lhash}".encode()).hexdigest()[:16]
                props = rule.get("properties", {})
                out[fp] = {
                    "rule": rid, "file": file, "line": line,
                    "name": (rule.get("shortDescription") or {}).get("text") or rid,
                    "help": (rule.get("fullDescription") or {}).get("text", ""),
                    "msg": (res.get("message") or {}).get("text", ""),
                    "severity": props.get("security-severity") or res.get("level") or props.get("problem.severity", ""),
                    "tags": [t for t in props.get("tags", []) if t.startswith("external/cwe")],
                }
    return out


def patch_milestone():
    """Nummer des nächsten offenen Patch-Milestones („X.Y.Z“) oder None."""
    ms = gh("GET", f"/repos/{REPO}/milestones?state=open&per_page=100") or []
    cand = [m for m in ms if re.fullmatch(r"\d+\.\d+\.\d+", m.get("title", ""))]
    cand.sort(key=lambda m: tuple(int(x) for x in m["title"].split(".")))
    return cand[0]["number"] if cand else None


def open_issues():
    found, page = {}, 1
    while True:
        batch = gh("GET", f"/repos/{REPO}/issues?state=open&labels=codeql&per_page=100&page={page}") or []
        for it in batch:
            m = MARK.search(it.get("body") or "")
            if m:
                found[m.group(1)] = (it["number"], m.group(2))
        if len(batch) < 100:
            return found
        page += 1


def main(sarif_dir, lang):
    if not REPO or not TOKEN:
        print("::warning::GITHUB_REPOSITORY/GH_TOKEN fehlt – keine Issues")
        return 0
    res = results(sarif_dir)
    have = open_issues()
    ms = patch_milestone()
    made = 0
    for fp, r in res.items():
        if fp in have:
            continue
        link = f"{SERVER}/{REPO}/blob/{SHA}/{r['file']}#L{r['line']}" if SHA else r["file"]
        body = (f"**CodeQL-Fund** ({lang}) – automatisch angelegt.\n\n"
                f"- Regel: `{r['rule']}` – {r['name']}\n"
                f"- Stelle: [{r['file']}:{r['line']}]({link})\n"
                + (f"- Schweregrad: {r['severity']}\n" if r["severity"] else "")
                + (f"- {', '.join(r['tags'])}\n" if r["tags"] else "")
                + f"\n> {r['msg']}\n\n"
                + (f"{r['help']}\n\n" if r["help"] else "")
                + "Wird automatisch geschlossen, sobald der Fund nach einem Push auf `main` nicht mehr auftaucht.\n"
                + f"Details: Security → Code scanning.\n\n<!-- codeql:{fp} lang:{lang} -->")
        data = {"title": f"CodeQL: {r['name']} – {r['file']}:{r['line']}"[:240], "body": body,
                "labels": ["bug", "security", "codeql"]}
        if ms:
            data["milestone"] = ms
        it = gh("POST", f"/repos/{REPO}/issues", data)
        if it:
            made += 1
            print(f"::notice title=CodeQL-Issue::#{it['number']} {data['title']}")
    closed = 0
    if os.environ.get("GITHUB_REF") == "refs/heads/main" and os.environ.get("GITHUB_EVENT_NAME") in ("push", "schedule", "workflow_dispatch"):
        for fp, (num, l) in have.items():
            if l == lang and fp not in res:
                gh("POST", f"/repos/{REPO}/issues/{num}/comments",
                   {"body": f"Der Fund taucht in der Analyse von {SHA[:7]} nicht mehr auf – erledigt."})
                gh("PATCH", f"/repos/{REPO}/issues/{num}", {"state": "closed", "state_reason": "completed"})
                closed += 1
    print(f"{lang}: {len(res)} Fund(e), {made} neue(s) Issue(s), {closed} geschlossen")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
