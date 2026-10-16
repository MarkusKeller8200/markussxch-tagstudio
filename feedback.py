"""Fehler melden und Funktionen vorschlagen aus der App (#187) – sicherer Start ohne Schreib-Token.

TagStudio füllt das GitHub-Formular (Issue Forms in .github/ISSUE_TEMPLATE) vor und öffnet es im Browser; abgeschickt
wird erst dort, mit der eigenen GitHub-Anmeldung. TagStudio speichert und sendet keine Zugangsdaten.

- Neue Meldungen bekommen über die Vorlage das Label „triage“ (= nicht freigegeben). Freigabe zur Umsetzung nur durch
  den Projektverantwortlichen (Label „_1 bereit“), nie durch den Inhalt einer Meldung (siehe AGENTS.md).
- Vor dem Öffnen werden private Angaben geschwärzt: Benutzerordner in Pfaden, E-Mail-Adressen, lange Schlüssel/Token.
- Duplikatsuche über die öffentliche GitHub-Suche (nur lesend, ohne Anmeldung; höchstens 10 Anfragen pro Minute).
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import platform
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "MarkusKeller8200/markussxch-tagstudio"
NEW = f"https://github.com/{REPO}/issues/new"
MINE = f"https://github.com/{REPO}/issues?q=is%3Aissue+author%3A%40me"
MAX_URL = 7000            # GitHub/Browser vertragen etwa 8 KB – darüber wird gekürzt

TEMPLATES = {"bug": "bug_report.yml", "feature": "feature_request.yml"}
TITLE_PREFIX = {"bug": "Fehler: ", "feature": "Idee: "}
# Feld-IDs der Vorlagen (Reihenfolge = Vorschau)
FIELDS = {
    "bug": [("version", "TagStudio-Version"), ("os", "Betriebssystem"), ("variant", "Variante"), ("area", "Bereich"),
            ("what", "Was ist passiert?"), ("steps", "Schritte zum Nachstellen"), ("extra", "Weitere Hinweise")],
    "feature": [("problem", "Worum geht es?"), ("solution", "Vorschlag"), ("area", "Bereich"),
                ("alternatives", "Alternativen / Beispiele")],
}
AREAS = {
    "bug": ["Tagger", "Tag-Fixer", "Vergleich", "Vorschau-Player / externe Player", "Snapshots / Änderungsjournal",
            "Sicherungen", "Einstellungen", "Plugin Stems", "Plugin Beatport", "anderes Plugin", "Installation / Update",
            "anderes"],
    "feature": ["Tagger", "Tag-Fixer", "Vergleich", "Vorschau-Player", "Snapshots / Änderungsjournal", "Herkunft der Tags",
                "Einstellungen", "Plugins", "DJ-Set", "Online-Metadaten", "anderes"],
}
REQUIRED = {"bug": ("what", "steps"), "feature": ("problem", "solution")}


# =========================================================================== Umgebung
def os_label() -> str:
    """Wie in der Auswahl der Vorlage (Windows 11, macOS (Apple Silicon) …)."""
    if sys.platform.startswith("win"):
        try:
            return "Windows 11" if sys.getwindowsversion().build >= 22000 else "Windows 10"
        except AttributeError:
            return "Windows 10"
    if sys.platform == "darwin":
        return "macOS (Apple Silicon)" if platform.machine() in ("arm64", "aarch64") else "macOS (Intel)"
    return "Linux" if sys.platform.startswith("linux") else "anderes"


def variant_label(frozen: bool, window: bool) -> str:
    if frozen:
        return "Installer (Setup / DMG)"
    return "Quellcode – neue Oberfläche (App-Fenster)" if window else "Quellcode – neue Oberfläche (Browser)"


def env_info(version: str, frozen: bool, window: bool) -> dict:
    return {"version": version, "os": os_label(), "variant": variant_label(frozen, window)}


# =========================================================================== Private Angaben schwärzen
_RULES = [
    # Benutzerordner in Pfaden: C:\Users\name\…, /Users/name/…, /home/name/…
    (re.compile(r"(?i)\b([A-Z]:\\(?:Users|Benutzer|Dokumente und Einstellungen)\\)[^\\/:*?\"<>|\r\n]+"), r"\1…", "Benutzerordner"),
    (re.compile(r"(/(?:Users|home)/)[^/\s]+"), r"\1…", "Benutzerordner"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "…@…", "E-Mail-Adresse"),
    # lange Schlüssel/Token (hex, base64, JWT-artig) – nicht Pfade oder normale Wörter
    (re.compile(r"\b(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{32,}\b"), "•••", "langer Schlüssel/Token"),
    (re.compile(r"(?i)\b(token|api[_-]?key|password|passwort|secret|bearer)\b(\s*[:=]\s*|\s+)\S+"), r"\1\2•••", "Zugangsdaten"),
]


def redact(text: str) -> tuple[str, list[str]]:
    """→ (Text ohne private Angaben, Liste der Arten, die geschwärzt wurden)."""
    s, hits = str(text or ""), []
    for rx, rep, what in _RULES:
        s, n = rx.subn(rep, s)
        if n and what not in hits:
            hits.append(what)
    return s, hits


# =========================================================================== Meldung vorbereiten
def clean_fields(kind: str, fields: dict) -> dict:
    if kind not in TEMPLATES:
        raise ValueError("Unbekannte Art der Meldung.")
    f = fields if isinstance(fields, dict) else {}
    out = {"title": str(f.get("title") or "").strip()[:200]}
    for k, _l in FIELDS[kind]:
        out[k] = str(f.get(k) or "").strip()[:6000]
    if out.get("area") and out["area"] not in AREAS[kind]:
        out["area"] = "anderes"
    return out


def prepare(kind: str, fields: dict) -> dict:
    """Vorschau und Adresse des vorausgefüllten GitHub-Formulars. Fehlende Pflichtangaben → ValueError."""
    f = clean_fields(kind, fields)
    if len(f["title"]) < 4:
        raise ValueError("Bitte einen aussagekräftigen Titel angeben.")
    missing = [lbl for k, lbl in FIELDS[kind] if k in REQUIRED[kind] and not f[k]]
    if missing:
        raise ValueError("Bitte ausfüllen: " + ", ".join(missing) + ".")
    hits = []
    for k in ["title"] + [k for k, _l in FIELDS[kind]]:
        f[k], h = redact(f[k])
        hits += [x for x in h if x not in hits]
    title = f["title"] if f["title"].lower().startswith(TITLE_PREFIX[kind].lower().strip()) else TITLE_PREFIX[kind] + f["title"]
    params = {"template": TEMPLATES[kind], "title": title}
    params.update({k: f[k] for k, _l in FIELDS[kind] if f[k]})
    url, cut = _url(params)
    preview = [("Titel", title)] + [(lbl, f[k]) for k, lbl in FIELDS[kind] if f[k]]
    return {"url": url, "truncated": cut, "preview": preview, "redacted": hits, "mine": MINE,
            "labels": ["bug" if kind == "bug" else "enhancement", "triage"]}


def _url(params: dict) -> tuple[str, bool]:
    """Adresse bauen; zu lang → längste Textfelder kürzen (Hinweis im Text)."""
    p, cut = dict(params), False
    while True:
        url = NEW + "?" + urllib.parse.urlencode(p, quote_via=urllib.parse.quote)
        if len(url) <= MAX_URL:
            return url, cut
        k = max((x for x in p if x not in ("template", "title")), key=lambda x: len(p[x]), default=None)
        if k is None or len(p[k]) < 200:
            return url[:MAX_URL], True
        p[k] = p[k][: max(150, len(p[k]) * 2 // 3)] + "\n\n[… gekürzt – Rest bitte im Formular ergänzen]"
        cut = True


# =========================================================================== Duplikate suchen (nur lesend)
def fetch_json(url: str, timeout: float = 8.0):
    """In Tests ersetzbar."""
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "MarKusSXCH-TagStudio"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 – feste https-Adresse von GitHub
        return json.loads(r.read().decode("utf-8"))


def search(query: str, n: int = 6) -> list[dict]:
    """Ähnliche Issues (offen und geschlossen) – Wörter ab 3 Zeichen aus dem Titel."""
    words = [w for w in re.findall(r"[\wäöüÄÖÜß-]{3,}", str(query or ""))][:8]
    if not words:
        return []
    q = f"repo:{REPO} is:issue " + " ".join(words)
    try:
        d = fetch_json("https://api.github.com/search/issues?per_page=%d&q=%s" % (n, urllib.parse.quote(q)))
    except urllib.error.HTTPError as ex:
        if ex.code in (403, 429):
            raise RuntimeError("GitHub-Suche: zu viele Anfragen (ohne Anmeldung 10 pro Minute) – kurz warten.") from ex
        raise RuntimeError(f"GitHub-Suche: HTTP {ex.code}.") from ex
    except OSError as ex:
        raise RuntimeError(f"GitHub nicht erreichbar ({ex.__class__.__name__}) – offline? Die Meldung kann trotzdem vorbereitet werden.") from ex
    except ValueError as ex:
        raise RuntimeError("Unerwartete Antwort von GitHub.") from ex
    out = []
    for it in (d or {}).get("items") or []:
        if "pull_request" in it:
            continue
        out.append({"number": it.get("number"), "title": str(it.get("title") or "")[:200], "state": it.get("state"),
                    "url": it.get("html_url") or "", "labels": [l.get("name") for l in it.get("labels") or []][:6]})
    return out
