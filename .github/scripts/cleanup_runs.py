"""Alte Workflow-Durchläufe löschen (Actions-Verlauf aufräumen, Entscheid User 17.10.2026).

Löscht abgeschlossene Durchläufe, die älter als DAYS Tage sind (DAYS=0: alle); der neueste Durchlauf jedes Workflows
und laufende Durchläufe bleiben. Nur über die GitHub-API (gh). Nur Standardbibliothek.

    GH_REPO=owner/repo DAYS=30 python3 .github/scripts/cleanup_runs.py [--dry-run]
"""
import datetime
import json
import os
import subprocess
import sys


def gh(*args):
    r = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout) if r.stdout.strip() else None


def main() -> int:
    repo = os.environ["GH_REPO"]
    days = int(os.environ.get("DAYS") or "30")
    dry = "--dry-run" in sys.argv
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    runs, page = [], 1
    while True:
        d = gh(f"/repos/{repo}/actions/runs?per_page=100&page={page}")
        runs += d.get("workflow_runs") or []
        if len(d.get("workflow_runs") or []) < 100:
            break
        page += 1
    newest = {}
    for r in runs:                                   # neuester Durchlauf je Workflow bleibt
        w = r["workflow_id"]
        if w not in newest or r["created_at"] > newest[w]["created_at"]:
            newest[w] = r
    keep = {r["id"] for r in newest.values()}
    gone = 0
    for r in runs:
        when = datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        if r["id"] in keep or r["status"] != "completed" or (days and when > cutoff):
            continue
        if not dry:
            try:
                gh("-X", "DELETE", f"/repos/{repo}/actions/runs/{r['id']}")
            except RuntimeError as ex:
                print(f"nicht gelöscht {r['id']}: {ex}")
                continue
        gone += 1
    print(f"{'würde löschen' if dry else 'gelöscht'}: {gone} von {len(runs)} Durchläufen (behalten: neuester je Workflow, laufende, jünger als {days} Tage)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
