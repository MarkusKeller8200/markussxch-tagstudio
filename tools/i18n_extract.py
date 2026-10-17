"""Mehrsprachigkeit (#157): Oberflächentexte aus dem Code sammeln und gegen die Sprachkataloge prüfen.

Die Ausgangssprache ist Schweizer Hochdeutsch (de-CH) und steht direkt im Code. Die Kataloge
``web/i18n/<modul>.json`` ordnen den deutschen Text (Schlüssel) den Übersetzungen ``[en, gsw-u-sd-chzh]`` zu. Zahlen werden zur Laufzeit zu
``{n}``, Text in „…“ bzw. "…" zu ``{q}``; im Code eingesetzte Ausdrücke (``${…}``, ``{…}``) erscheinen hier als ``{x}``.

  python3 tools/i18n_extract.py                 # Übersicht: Anzahl Texte, fehlende je Sprache
  python3 tools/i18n_extract.py --missing en    # fehlende Texte einer Sprache (JSON, nach Datei gruppiert)
  python3 tools/i18n_extract.py --all           # alle gefundenen Texte (JSON, nach Datei gruppiert)

Nur Standardbibliothek. Wird von tests/test_i18n.py verwendet (keine fehlenden Texte in den mitgelieferten Sprachen).
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
I18N = os.path.join(WEB, "i18n")
LANGS = ("en", "gsw-u-sd-chzh")
# Python-Module, deren Texte in der Oberfläche erscheinen (Meldungen, Auswahllisten, Dialoge)
PY_SKIP = {"version.py", "tagstudio.py", "applog.py", "instance.py", "paths.py"}

_TAG = re.compile(r"<[^<>]*>")
_ENT = re.compile(r"&(nbsp|amp|lt|gt|quot|#\d+|#x[0-9a-f]+);", re.I)
_NUM = re.compile(r"(?<![\w{])[-+]?\d+(?:['’.,]\d+)*(?![\w}])")
_QUOTE = re.compile(r"„[^„“”\n]*[“”]|\"[^\"\n]*\"|«[^«»\n]*»")
_PH = re.compile(r"\{(?:n|q|x)\}")
_WORD = re.compile(r"[A-Za-zÄÖÜäöüéèàß]{2,}")
_SVG = re.compile(r"^[MLHVCSQTAZmlhvcsqtaz0-9 .,\-]+$")
_CODEISH = re.compile(r"[{};$\\]|=>|\(\)|^[.#\[:@/]|^[\w.]+\([^)]*\)$|^\w+[.:]\w+$|https?://|^\S+\.(?:js|css|py|json|html|mp3|png)$")


def skeleton(text: str) -> str:
    """Laufzeitform: Zahlen → {n}, „…“/"…" → {q}; Leerraum vereinheitlicht."""
    s = _QUOTE.sub("{q}", text)
    s = _NUM.sub("{n}", s)
    return re.sub(r"\s+", " ", s).strip()


def norm(text: str) -> str:
    """Vergleichsform für die Abdeckung: alle Platzhalter gleich."""
    return _PH.sub("{}", skeleton(text))


def is_ui(s: str) -> bool:
    s = s.strip()
    if len(s) < 2 or not _WORD.search(s):
        return False
    if _SVG.match(s) or _CODEISH.search(_PH.sub("", s)):
        return False
    letters = re.sub(r"\{[nqx]\}", "", s)
    if not re.search(r"[A-Za-zÄÖÜäöü]", letters):
        return False
    if re.fullmatch(r"[a-z0-9_\-\s:,.*+>~=|!?'\"]+", letters) and ("-" in letters or "_" in letters or " " not in letters.strip()):
        return False                                          # Klassen, Schlüssel, Bezeichner
    if re.fullmatch(r"[A-Z0-9_:\-#/. ]+", letters):
        return False                                          # FELDNAMEN, Frame-IDs
    if re.fullmatch(r"[a-z]+[A-Z]\w*", letters.strip()):
        return False                                          # camelCase
    if re.fullmatch(r"(?:[a-z]+(?:-[a-z]+)*)(?:\s+[a-z]+(?:-[a-z]+)*)+", letters.strip()) and not re.search(r"[äöü]", letters):
        return False                                          # "icon-btn pl-tog", "click keydown"
    return True


def chunks(text: str):
    """Literal → einzelne Texte (HTML-Tags und Zeilen trennen)."""
    text = _ENT.sub(lambda m: {"nbsp": " ", "amp": "&", "lt": "<", "gt": ">", "quot": '"'}.get(m.group(1).lower(), " "), text)
    for part in _TAG.split(text):
        for line in part.replace("\n", " ").split("\x01"):
            line = re.sub(r"\s+", " ", line).strip()
            line = line.strip("·•|–—:,;").strip() if re.fullmatch(r"[·•|–—:,;\s]+.*|.*[·•|–—:,;\s]+", line) and len(line) < 3 else line
            if line and not re.fullmatch(r"(\{x\}|\s|[·•|–—:,;()/+×…%-])*", line) and is_ui(line):
                yield line


# ---------------------------------------------------------------- JavaScript
_REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_WORDS = ("return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else")


def js_literals(src: str):
    """String- und Template-Literale (Inhalt, ${…} → {x}); verschachtelte Templates werden ebenfalls geliefert."""
    i, n, out, last = 0, len(src), [], ""
    while i < n:
        c = src[i]
        if c == "/" and src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/":
            prev = src[:i].rstrip()
            word = re.search(r"(\w+)$", prev)
            if not prev or prev[-1] in _REGEX_BEFORE or (word and word.group(1) in _REGEX_WORDS):
                j, cls = i + 1, False
                while j < n and src[j] != "\n":
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == "[":
                        cls = True
                    elif src[j] == "]":
                        cls = False
                    elif src[j] == "/" and not cls:
                        break
                    j += 1
                i = j + 1
                continue
        if c in "'\"":
            j, buf = i + 1, []
            while j < n and src[j] != c:
                if src[j] == "\\" and j + 1 < n:
                    buf.append({"n": "\x01", "t": " "}.get(src[j + 1], src[j + 1]))
                    j += 2
                    continue
                if src[j] == "\n":
                    break
                buf.append(src[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
            continue
        if c == "`":
            text, i = _template(src, i + 1, out)
            out.append(text)
            continue
        last = c
        i += 1
    return out


def _template(src: str, i: int, out: list):
    buf, n = [], len(src)
    while i < n:
        c = src[i]
        if c == "\\" and i + 1 < n:
            buf.append({"n": "\x01"}.get(src[i + 1], src[i + 1]))
            i += 2
            continue
        if c == "`":
            return "".join(buf), i + 1
        if c == "$" and src.startswith("${", i):
            depth, j = 1, i + 2
            start = j
            while j < n and depth:
                ch = src[j]
                if ch == "`":
                    inner, j = _template(src, j + 1, out)
                    out.append(inner)
                    continue
                if ch in "'\"":
                    k = j + 1
                    while k < n and src[k] != ch:
                        k += 2 if src[k] == "\\" else 1
                    out.append(src[j + 1:k])
                    j = k + 1
                    continue
                depth += ch == "{"
                depth -= ch == "}"
                j += 1
            expr = src[start:j - 1]
            buf.append("{x}" if not re.fullmatch(r'\s*"[^"]*"\s*', expr) else expr.strip()[1:-1])
            i = j
            continue
        buf.append(c)
        i += 1
    return "".join(buf), i


def html_texts(src: str):
    src = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<!--.*?-->", " ", src, flags=re.S)
    out = [m.group(1) for m in re.finditer(r'\s(?:title|placeholder|aria-label|alt|data-tip-title)="([^"]*)"', src)]
    out += [t for t in re.split(r"<[^<>]*>", src)]
    return out


# ---------------------------------------------------------------- Python
def py_literals(src: str):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out, inner = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                    inner.add(id(v))
                else:
                    parts.append("{x}")
            out.append("".join(parts))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in inner:
            out.append(node.value)
    # Docstrings ausnehmen
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docs.add(d)
    return [s for s in out if s not in docs and not s.startswith("\n")]


def _py_ui(s: str) -> bool:
    """Python: nur Texte mit deutschem Inhalt (Meldungen), keine Bezeichner, Pfade, Formate."""
    if not re.search(r"[äöüÄÖÜ]|\b(der|die|das|und|nicht|kein|keine|mit|für|von|im|zum|zur|bitte|wird|werden|ist|sind|Datei|Dateien|Titel|Ordner|bereits|noch|nur|oder|aus|auf|alle|neu|Fehler)\b", s):
        return False
    return True


def collect(include_py=True, plugins=False) -> dict[str, list[str]]:
    """{Datei: [Texte]} – Reihenfolge wie im Code, je Datei ohne Doppelte."""
    res: dict[str, list[str]] = {}

    def add(fname, texts):
        seen = res.setdefault(fname, [])
        for t in texts:
            for c in chunks(t):
                if c not in seen:
                    seen.append(c)

    for fn in sorted(os.listdir(WEB)):
        p = os.path.join(WEB, fn)
        if fn.endswith(".js"):
            add(fn, js_literals(open(p, encoding="utf-8").read()))
        elif fn.endswith(".html"):
            add(fn, html_texts(open(p, encoding="utf-8").read()))
    if include_py:
        for fn in sorted(os.listdir(ROOT)):
            if fn.endswith(".py") and fn not in PY_SKIP:
                texts = [t.replace("\n", "\x01") for t in py_literals(open(os.path.join(ROOT, fn), encoding="utf-8").read()) if _py_ui(t)]
                add(fn, texts)
    if plugins:
        pdir = os.path.join(ROOT, "plugins")
        for name in sorted(os.listdir(pdir)) if os.path.isdir(pdir) else []:
            d = os.path.join(pdir, name)
            for fn in ("plugin.py", "plugin.json"):
                p = os.path.join(d, fn)
                if not os.path.isfile(p):
                    continue
                if fn.endswith(".py"):
                    texts = [t for t in py_literals(open(p, encoding="utf-8").read()) if _py_ui(t)]
                else:
                    texts = []

                    def walk(o):
                        if isinstance(o, str):
                            texts.append(o)
                        elif isinstance(o, dict):
                            for k, v in o.items():
                                if k not in ("id", "url", "api", "version", "entry", "key", "type", "i18n"):
                                    walk(v)
                        elif isinstance(o, list):
                            for v in o:
                                walk(v)
                    try:
                        walk(json.load(open(p, encoding="utf-8")))
                    except ValueError:
                        pass
                    texts = [t for t in texts if _py_ui(t) or re.search(r"[A-Z][a-zäöü]+ [a-zäöü]", t)]
                add(f"plugins/{name}/{fn}", texts)
    ignore = load_ignore()
    return {k: [t for t in v if norm(t) not in ignore] for k, v in res.items() if v}


def load_ignore() -> set[str]:
    p = os.path.join(I18N, "ignore.json")
    try:
        return {norm(x) for x in json.load(open(p, encoding="utf-8"))}
    except (OSError, ValueError):
        return set()


def load_catalog(lang: str) -> dict[str, str]:
    sys.path.insert(0, ROOT)
    import i18n
    return i18n.catalog(lang)


def missing(lang: str, texts: dict[str, list[str]]) -> dict[str, list[str]]:
    have = {norm(k) for k in load_catalog(lang)}
    out = {}
    for f, lst in texts.items():
        m = [t for t in lst if norm(t) not in have]
        if m:
            out[f] = m
    return out


def main(argv):
    plugins = "--plugins" in argv
    texts = collect(plugins=plugins)
    if "--all" in argv:
        print(json.dumps({f: [skeleton(t) for t in v] for f, v in texts.items()}, ensure_ascii=False, indent=1))
        return 0
    if "--missing" in argv:
        lang = argv[argv.index("--missing") + 1]
        print(json.dumps({f: [skeleton(t) for t in v] for f, v in missing(lang, texts).items()},
                         ensure_ascii=False, indent=1))
        return 0
    total = len({norm(t) for v in texts.values() for t in v})
    print(f"{total} verschiedene Texte in {len(texts)} Dateien")
    for lang in LANGS:
        m = missing(lang, texts)
        print(f"  {lang}: {len({norm(t) for v in m.values() for t in v})} fehlen")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
