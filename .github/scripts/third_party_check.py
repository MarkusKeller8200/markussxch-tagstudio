"""Fremdkomponenten auf Änderungen prüfen (#176) – läuft monatlich im Workflow „Fremdkomponenten prüfen“.

    python .github/scripts/third_party_check.py                 # prüfen, Bericht ausgeben, Issue anlegen/aktualisieren
    python .github/scripts/third_party_check.py --dry-run       # nur Bericht, kein Issue
    python .github/scripts/third_party_check.py --apply neu.json  # geprüfte Stände in docs/third-party.json übernehmen

Für jeden Eintrag mit „check“ in docs/third-party.json wird der aktuelle Stand geholt:
- pypi:   neueste Version und Lizenzangabe (PyPI-JSON-API)
- github: neueste Release-Version (sonst letzter Push) und erkannte Lizenz (GitHub-API)
und mit „checked“ verglichen. Für Einträge mit „repo“ (GitHub) kommen zusätzlich Vertrauenssignale dazu (#206): Sterne,
letzter Push, archiviert, Diskussionen – gespeichert als „repo_info“, angezeigt in Hilfe › Lizenzen. Abweichungen (neue Version, Lizenzwechsel, noch nie geprüft) kommen als ein Issue
„Fremdkomponenten: Änderungen prüfen“ (Marker im Text, wird aktualisiert statt doppelt angelegt). Im Issue steht ein
JSON-Block mit den neuen Ständen; nach der Durchsicht mit --apply übernehmen und committen.
Nur Standardbibliothek.
"""
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "docs", "third-party.json")
API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
MARK = "<!-- third-party-check -->"
TITLE = "Fremdkomponenten: Änderungen prüfen"


def _get(url, gh=False):
    h = {"User-Agent": "tagstudio-third-party-check", "Accept": "application/json"}
    if gh:
        h["Accept"] = "application/vnd.github+json"
        if TOKEN:
            h["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def _pypi_license(info) -> str:
    lic = (info.get("license_expression") or "").strip()
    if lic:
        return lic
    raw = (info.get("license") or "").strip()
    if raw and len(raw) <= 60 and "\n" not in raw:
        return raw
    cls = [c.split("::")[-1].strip() for c in info.get("classifiers") or [] if c.startswith("License ::")]
    return ", ".join(cls) or ("siehe Projekt" if raw else "")


def current(check) -> dict:
    """Aktueller Stand einer Komponente: {"version", "license"} (Fehler → {"error"})."""
    try:
        if check["type"] == "pypi":
            info = _get(f"https://pypi.org/pypi/{check['package']}/json")["info"]
            return {"version": info.get("version") or "", "license": _pypi_license(info)}
        if check["type"] == "github":
            repo = _get(f"{API}/repos/{check['repo']}", gh=True)
            lic = ((repo.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", "eigene")
            try:
                ver = _get(f"{API}/repos/{check['repo']}/releases/latest", gh=True).get("tag_name") or ""
            except urllib.error.HTTPError:
                ver = ""
            if not ver:
                ver = "Stand " + (repo.get("pushed_at") or "")[:10]
            return {"version": ver, "license": lic}
    except Exception as ex:  # noqa: BLE001 – ein Fehler betrifft nur diesen Eintrag
        return {"error": f"{type(ex).__name__}: {ex}"}
    return {"error": f"unbekannte Prüfart {check.get('type')}"}


def repo_info(repo, today="") -> dict:
    """#206: Vertrauenssignale eines GitHub-Repositorys."""
    j = _get(f"{API}/repos/{repo}", gh=True)
    return {"stars": j.get("stargazers_count") or 0, "archived": bool(j.get("archived")),
            "pushed": (j.get("pushed_at") or "")[:10], "discussions": bool(j.get("has_discussions")),
            "owner_type": (j.get("owner") or {}).get("type") or "", "full_name": j.get("full_name") or repo,
            "license": ((j.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", "eigene"),
            "date": today or datetime.date.today().isoformat()}


def collect_repo_info(items, fetch=repo_info, today="") -> dict:
    """{id: repo_info} für alle Einträge mit „repo“; Fehler → {"error"}."""
    out = {}
    for it in items:
        if it.get("repo"):
            try:
                out[it["id"]] = fetch(it["repo"], today)
            except Exception as ex:  # noqa: BLE001
                out[it["id"]] = {"error": f"{type(ex).__name__}: {ex}"}
    return out


def repo_warnings(items, infos, today) -> list:
    """Hinweise zur Vertrauenswürdigkeit: archiviert, seit über 2 Jahren still, umbenannt, nicht erreichbar."""
    out = []
    t = datetime.date.fromisoformat(today)
    for it in items:
        inf = infos.get(it["id"])
        if not inf:
            continue
        if inf.get("error"):
            out.append((it, "Repository nicht abrufbar: " + inf["error"]))
            continue
        if inf.get("archived"):
            out.append((it, "archiviert (wird nicht mehr gepflegt)"))
        if inf.get("pushed"):
            try:
                if (t - datetime.date.fromisoformat(inf["pushed"])).days > 730:
                    out.append((it, f"seit {inf['pushed']} keine Änderungen"))
            except ValueError:
                pass
        if inf.get("full_name") and inf["full_name"].lower() != it["repo"].lower():
            out.append((it, f"umbenannt/verschoben nach {inf['full_name']}"))
    return out


def compare(items, fetch=current) -> list:
    """→ [{"id", "name", "old", "new", "what"}] für alle Einträge mit Änderungen oder Fehlern."""
    out = []
    for it in items:
        chk = it.get("check")
        if not chk:
            continue
        new = fetch(chk)
        old = it.get("checked") or {}
        what = []
        if new.get("error"):
            what.append("Fehler beim Abruf: " + new["error"])
        else:
            if not old:
                what.append("noch nie geprüft")
            else:
                if old.get("version") != new.get("version"):
                    what.append(f"Version {old.get('version') or '–'} → {new.get('version') or '–'}")
                if (old.get("license") or "") != (new.get("license") or ""):
                    what.append(f"Lizenzangabe „{old.get('license') or '–'}“ → „{new.get('license') or '–'}“")
        if what:
            out.append({"id": it["id"], "name": it["name"], "old": old, "new": new, "what": what,
                        "license": it.get("license", ""), "url": it.get("url", "")})
    return out


def report(changes, today, infos=None, warnings=()) -> str:
    lines = [MARK, f"Monatliche Prüfung der Fremdkomponenten vom {today} (Liste: `docs/third-party.json`, Anzeige: Hilfe › Lizenzen).", ""]
    if warnings:
        lines += ["**Repositories – bitte ansehen (#206):**", ""] + \
                 [f"- [{it['name']}](https://github.com/{it['repo']}): {w}" for it, w in warnings] + [""]
    good = {k: v for k, v in (infos or {}).items() if not v.get("error")}
    if not changes:
        lines.append("Keine Änderungen.")
        if good:
            lines += ["", "<details><summary>Vertrauenssignale der Repositories (JSON, mit --apply übernehmen)</summary>", "",
                      "```json", json.dumps({"_repo_info": good}, ensure_ascii=False, indent=1), "```", "</details>"]
        return "\n".join(lines)
    lines += ["Bitte prüfen: Passt die Lizenz weiterhin (auch für die Weitergabe im Installer)? Gibt es "
              "sicherheitsrelevante Änderungen? Muss die Anzeige in der Hilfe angepasst werden?", "",
              "| Komponente | Änderung | Lizenz laut Liste |", "|---|---|---|"]
    for c in changes:
        lines.append(f"| [{c['name']}]({c['url']}) | {'; '.join(c['what'])} | {c['license']} |")
    upd = {c["id"]: {"version": c["new"].get("version", ""), "license": c["new"].get("license", ""), "date": today}
           for c in changes if not c["new"].get("error")}
    if good:
        upd["_repo_info"] = good
    lines += ["", "- [ ] Änderungen geprüft, Lizenzangaben in `docs/third-party.json` bei Bedarf angepasst",
              "- [ ] Neue Stände übernommen: JSON unten speichern und "
              "`python .github/scripts/third_party_check.py --apply datei.json` ausführen, committen", "",
              "<details><summary>Neue Stände (JSON)</summary>", "", "```json", json.dumps(upd, ensure_ascii=False, indent=1),
              "```", "</details>"]
    return "\n".join(lines)


def apply(path_new, data_path=DATA) -> int:
    with open(path_new, encoding="utf-8") as fh:
        upd = json.load(fh)
    with open(data_path, encoding="utf-8") as fh:
        text = fh.read()
    data = json.loads(text)
    n = 0
    infos = upd.pop("_repo_info", {}) or {}
    for it in data["items"]:
        if it["id"] in upd:
            it["checked"] = upd[it["id"]]
            n += 1
        if it["id"] in infos and not infos[it["id"]].get("error"):
            it["repo_info"] = infos[it["id"]]
            n += 1
    with open(data_path, "w", encoding="utf-8") as fh:
        fh.write(dump(data))
    return n


def dump(data) -> str:
    """Eine Zeile je Eintrag (gut lesbare Diffs)."""
    head = {k: v for k, v in data.items() if k != "items"}
    body = ",\n".join("    " + json.dumps(it, ensure_ascii=False) for it in data["items"])
    lines = json.dumps(head, ensure_ascii=False, indent=2).rstrip("}").rstrip()
    return f'{lines},\n  "items": [\n{body}\n  ]\n}}\n'


def gh(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "tagstudio-third-party-check"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            return json.loads(data) if data else None
    except urllib.error.HTTPError as ex:
        print(f"::warning::GitHub-API {method} {path}: {ex.code} {ex.read()[:300]!r}")
        return None


def publish(text, changed: bool):
    issues = gh("GET", f"/repos/{REPO}/issues?state=open&labels=documentation&per_page=100") or []
    cur = next((i for i in issues if MARK in (i.get("body") or "")), None)
    if cur:
        gh("PATCH", f"/repos/{REPO}/issues/{cur['number']}", {"body": text})
        if changed:
            gh("POST", f"/repos/{REPO}/issues/{cur['number']}/comments", {"body": "Neue Prüfung – Liste oben aktualisiert."})
        print(f"Issue #{cur['number']} aktualisiert.")
    elif changed:
        r = gh("POST", f"/repos/{REPO}/issues", {"title": TITLE, "body": text, "labels": ["documentation"]})
        print(f"Issue #{r and r.get('number')} angelegt.")


def main(argv):
    if argv[:1] == ["--apply"] and len(argv) > 1:
        print(f"{apply(argv[1])} Einträge übernommen.")
        return 0
    with open(DATA, encoding="utf-8") as fh:
        data = json.load(fh)
    today = datetime.date.today().isoformat()
    changes = compare(data["items"])
    infos = collect_repo_info(data["items"], today=today) if TOKEN else {}
    warns = repo_warnings(data["items"], infos, today)
    # schon bekannte Hinweise (aus den gespeicherten repo_info) lösen kein neues Issue aus
    known = {(it["id"], w) for it, w in repo_warnings(data["items"], {i["id"]: i["repo_info"] for i in data["items"]
                                                                       if i.get("repo_info")}, today)}
    new_warns = [(it, w) for it, w in warns if (it["id"], w) not in known]
    text = report(changes, today, infos, warns)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(re.sub(re.escape(MARK), "", text) + "\n")
    if "--dry-run" not in argv and REPO and TOKEN:
        publish(text, bool(changes or new_warns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
