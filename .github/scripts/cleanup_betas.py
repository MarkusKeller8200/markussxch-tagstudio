"""Beta-Releases aufräumen: entfernt Vorabversionen (vX.Y.Z-beta.N), sobald es die finale Version vX.Y.Z gibt –
oder eine höhere finale Version, die sie ersetzt (z. B. v4.1.1-beta.1 nach v4.2.0).

Nur die Release-Einträge samt Installern verschwinden von der Releases-Seite – die Git-Tags bleiben erhalten.
Läuft im Workflow „Installer“ nach jeder finalen Version und von Hand über den Workflow „Releases aufräumen“.
Aufruf: python .github/scripts/cleanup_betas.py [--dry-run]   (braucht gh mit GH_TOKEN)
"""
import json
import os
import subprocess
import sys


def _ver(tag: str) -> tuple:
    try:
        return tuple(int(x) for x in tag.lstrip("v").split("-", 1)[0].split("."))
    except ValueError:
        return ()


def main() -> int:
    dry = "--dry-run" in sys.argv
    repo = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY")
    out = subprocess.run(["gh", "api", "--paginate", f"repos/{repo}/releases?per_page=100",
                          "--jq", ".[] | [.id, .tag_name, .prerelease] | @json"],
                         check=True, capture_output=True, text=True).stdout
    rels = [json.loads(line) for line in out.splitlines() if line.strip()]
    finals = {tag for _id, tag, pre in rels if not pre and "-" not in tag}
    top = max((_ver(t) for t in finals if _ver(t)), default=())
    gone = []
    for rid, tag, pre in rels:
        if (pre or "-" in tag) and (tag.split("-", 1)[0] in finals or (_ver(tag) and _ver(tag) < top)):
            print(("würde entfernen: " if dry else "entferne: ") + tag)
            if not dry:   # nur der Release-Eintrag (REST), der Git-Tag bleibt
                subprocess.run(["gh", "api", "-X", "DELETE", f"repos/{repo}/releases/{rid}"], check=True)
            gone.append(tag)
    print(f"{len(gone)} Beta-Release(s) {'gefunden' if dry else 'entfernt'}, {len(finals)} finale Version(en) bleiben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
