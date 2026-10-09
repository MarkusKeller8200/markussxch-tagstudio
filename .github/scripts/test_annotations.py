"""Fehlgeschlagene Tests aus der unittest-Ausgabe als GitHub-Anmerkungen ausgeben (lesbar ohne Log-Zugriff).

    python .github/scripts/test_annotations.py test-output.txt
"""
import re
import sys


def main(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        print("::error::Keine Testausgabe gefunden")
        return 0
    blocks = re.split(r"^={50,}$", text, flags=re.M)
    n = 0
    for b in blocks:
        b = b.strip("\n")
        m = re.match(r"(FAIL|ERROR): (\S+) \(([^)]+)\)", b)
        if not m:
            continue
        body = b.split("-" * 70, 1)[-1].strip()
        body = body.split("\n" + "-" * 70)[0]
        msg = (body[-3000:]).replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title={m.group(1)} {m.group(3)}.{m.group(2)}::{msg}")
        n += 1
    if not n:
        tail = text[-2500:].replace("%", "%25").replace("\n", "%0A")
        print(f"::error title=Testausgabe (Ende)::{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "test-output.txt"))
