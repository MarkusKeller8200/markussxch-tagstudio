"""GitHub Actions: owner-only, issue-comment milestone administration.

Accepted commands on the dedicated administrative GitHub issue:
  /milestone list
  /milestone create VERSION – Title
  /milestone close NUMBER
  /milestone reopen NUMBER

Never interpolate issue/comment text into shell commands. Use only GitHub's
short-lived GITHUB_TOKEN with issues:write; never require a personal token.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


EXPECTED_REPO = "MarkusKeller8200/markussxch-tagstudio"
COMMAND_PATTERN = re.compile(r"^/milestone (list|create|close|reopen)(?: (.+))?$")


def api(method: str, endpoint: str, data: dict | None = None) -> object:
    token = os.environ["GH_TOKEN"]
    url = "https://api.github.com" + endpoint
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": "TagStudio-milestone-admin",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc


def parse_command(raw: str) -> tuple[str, str | None]:
    if len(raw) > 180 or "\n" in raw or "\r" in raw:
        raise ValueError("One single-line command (max. 180 characters) is required.")
    match = COMMAND_PATTERN.fullmatch(raw.strip())
    if not match:
        raise ValueError("Commands: /milestone list | create TITLE | close NUMBER | reopen NUMBER")
    operation, argument = match.groups()
    if operation == "list" and argument is not None:
        raise ValueError("Usage: /milestone list")
    if operation == "create":
        if not argument or not 3 <= len(argument) <= 120:
            raise ValueError("Usage: /milestone create TITLE (3–120 characters)")
        return operation, argument
    if operation in ("close", "reopen"):
        if not argument or not re.fullmatch(r"[1-9][0-9]{0,7}", argument):
            raise ValueError("Usage: /milestone close NUMBER or /milestone reopen NUMBER")
        return operation, argument
    return operation, None


def execute(operation: str, argument: str | None, repo: str) -> str:
    base = f"/repos/{repo}/milestones"
    if operation == "list":
        found = []
        page = 1
        while True:
            data = api("GET", f"{base}?state=all&per_page=100&page={page}")
            if not isinstance(data, list):
                raise RuntimeError("Unexpected GitHub milestones response.")
            found.extend(data)
            if len(data) < 100:
                break
            page += 1
            if page > 10:
                raise RuntimeError("Too many milestones to list safely.")
        lines = [
            f"- [#{m['number']} – {m['title']}]({m['html_url']}) · {m['state']} · {m['open_issues']} open"
            for m in sorted(found, key=lambda m: m["number"], reverse=True)
        ]
        return "**Current milestones:**\n" + ("\n".join(lines) if lines else "(none)")
    if operation == "create":
        title = str(argument)
        existing = api("GET", f"{base}?state=all&per_page=100")
        for item in existing:
            if item["title"].casefold() == title.casefold():
                return f"Already exists: [#{item['number']} – {item['title']}]({item['html_url']})."
        created = api("POST", base, {"title": title})
        return f"Created [#{created['number']} – {created['title']}]({created['html_url']})."
    number = int(str(argument))
    milestone = api("GET", f"{base}/{number}")
    target = "closed" if operation == "close" else "open"
    if milestone["state"] == target:
        return f"Already {target}: [#{number} – {milestone['title']}]({milestone['html_url']})."
    updated = api("PATCH", f"{base}/{number}", {"state": target})
    return f"Set to **{target}**: [#{number} – {updated['title']}]({updated['html_url']})."


def main() -> int:
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fp:
        event = json.load(fp)
    issue = event.get("issue") or {}
    comment = event.get("comment") or {}
    repository = event.get("repository") or {}
    owner = repository.get("owner") or {}
    repo = repository.get("full_name") or ""
    issue_number = int(os.environ["ADMIN_ISSUE_NUMBER"])
    # IMPORTANT: repeat the workflow-level permission checks before doing anything.
    if (
        event.get("action") != "created"
        or repo != EXPECTED_REPO
        or os.environ.get("GITHUB_REPOSITORY") != EXPECTED_REPO
        or owner.get("login") != comment.get("user", {}).get("login")
        or issue.get("number") != issue_number
        or "pull_request" in issue
    ):
        print("Not an authorized administrative command; no action taken.")
        return 0
    body = str(comment.get("body") or "")
    if not body.startswith("/milestone "):
        return 0
    print("Processing approved command on administrative issue.")
    try:
        operation, argument = parse_command(body)
        result = execute(operation, argument, repo)
        message = "✅ **Milestone administration:** " + result
    except (ValueError, RuntimeError, KeyError) as exc:
        message = "⚠️ **Milestone administration failed:** " + str(exc)
        print(message, file=sys.stderr)
    api("POST", f"/repos/{repo}/issues/{issue_number}/comments", {"body": message})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
