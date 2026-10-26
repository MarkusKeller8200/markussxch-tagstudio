"""Session-Teil „Hilfe“ (#158): Handbuch (README), ID3-Felder, Tag-Übersicht mit Herkunft und Bibliotheks-Scan."""
from __future__ import annotations

import os
import sys
import time

import taghelp

HERE = os.path.dirname(os.path.abspath(__file__))
# #373: das Handbuch liegt in docs/HANDBUCH.md (README ist nur noch die Startseite); ältere Pakete haben es im README
DOCS = {"readme": ("Handbuch", os.path.join("docs", "HANDBUCH.md")), "id3": ("ID3-Felder", os.path.join("docs", "ID3-FELDER.md")),
        "plugins": ("Plugins", "PLUGINS.md")}
LICENSES = os.path.join("docs", "third-party.json")                                # #176


def _read_doc(rel: str) -> str:
    for base in (HERE, getattr(sys, "_MEIPASS", HERE)):
        p = os.path.join(base, rel)
        try:
            with open(p, encoding="utf-8") as fh:
                return fh.read()
        except OSError:
            continue
    return ""


class HelpMixin:
    # ------------------------------------------------------------------ Dokumente
    def help_docs(self, lang: str = "") -> dict:
        """Handbuch, ID3-Felder, Plugins – auf Englisch die .en.md-Fassung, sonst (auch Zürichdeutsch) Deutsch (#219)."""
        out = {}
        for k, (t, rel) in DOCS.items():
            text, doc_lang = "", "de"
            if lang == "en":
                base, ext = os.path.splitext(rel)
                text = _read_doc(base + ".en" + ext)
                doc_lang = "en" if text else "de"
            text = text or _read_doc(rel)
            if not text and k == "readme":                                       # Paket ohne docs/HANDBUCH.md
                old = "README.en.md" if lang == "en" else "README.md"
                text, doc_lang = _read_doc(old) or _read_doc("README.md"), ("en" if lang == "en" and _read_doc(old) else "de")
            out[k] = {"title": t, "text": text, "lang": doc_lang}
        return out

    def help_licenses(self) -> dict:
        """#176: verwendete Bibliotheken, Werkzeuge, Dienste und Vorlagen mit Lizenz und Quelle (docs/third-party.json)."""
        import json
        text = _read_doc(LICENSES)
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {}
        groups = data.get("groups") or {}
        items = [it for it in data.get("items") or [] if isinstance(it, dict) and it.get("name")]
        order = list(groups)
        items.sort(key=lambda it: (order.index(it.get("group")) if it.get("group") in order else len(order),
                                   it.get("group") != "app", str(it.get("name")).lower()))
        review = (getattr(self, "cfg", None) or {}).get("lic_review") or {}
        return {"groups": groups, "items": items, "found": bool(items),
                "review": review if isinstance(review, dict) else {}}

    # ------------------------------------------------------------------ #187 Fehler melden / Funktion vorschlagen
    def feedback_info(self, window: bool = False) -> dict:
        """Version, Betriebssystem, Variante für das Formular; Bereiche je Art."""
        import sys
        import feedback
        from version import VERSION
        return {"env": feedback.env_info(VERSION, bool(getattr(sys, "frozen", False)), bool(window)),
                "areas": feedback.AREAS, "fields": feedback.FIELDS, "required": feedback.REQUIRED,
                "mine": feedback.MINE, "milestones": feedback.MILESTONE, "languages": feedback.TRANSLATION_LANGS}

    def feedback_translation(self, lang: str) -> dict:
        """#232: eigene Texte einer Sprache (nur von der mitgelieferten Fassung abweichende) zum Einreichen."""
        import feedback
        return feedback.own_texts(str(lang))

    def feedback_search(self, query: str) -> dict:
        """Ähnliche vorhandene Issues (öffentliche Suche, nur lesend)."""
        import feedback
        try:
            return {"ok": True, "items": feedback.search(query)}
        except RuntimeError as ex:
            return {"ok": False, "items": [], "error": str(ex)}

    def feedback_prepare(self, kind: str, fields: dict) -> dict:
        """Vorschau (geschwärzt) und Adresse des vorausgefüllten GitHub-Formulars – gesendet wird erst im Browser."""
        import feedback
        return feedback.prepare(kind, fields)

    REVIEW_KEYS = ("checked", "followed", "thanked")

    def help_lic_mark(self, cid: str, key: str, on: bool) -> dict:
        """#206: eigene Durchsicht je Komponente merken – geprüft, Entwickler gefolgt, bedankt (nur lokal)."""
        import core
        if key not in self.REVIEW_KEYS or not isinstance(cid, str) or not cid:
            raise ValueError("Unbekannte Markierung.")
        rv = dict(self.cfg.get("lic_review") or {})
        cur = {k: v for k, v in (rv.get(cid) or {}).items() if k in self.REVIEW_KEYS and v}
        if on:
            cur[key] = __import__("time").strftime("%Y-%m-%d")
        else:
            cur.pop(key, None)
        if cur:
            rv[cid] = cur
        else:
            rv.pop(cid, None)
        self.cfg["lic_review"] = rv
        core.save_config({"lic_review": rv})
        return {"ok": True, "review": rv}

    # ------------------------------------------------------------------ Tag-Übersicht
    def _help_roots(self) -> list[dict]:
        """Ordner, die gescannt werden können: aktive Bibliotheken (#311), geladener Ordner, Snapshot-Bibliotheken."""
        out, seen = [], set()

        def add(p, label):
            if p and os.path.isdir(p) and os.path.normcase(os.path.abspath(p)) not in seen:
                seen.add(os.path.normcase(os.path.abspath(p)))
                out.append({"path": os.path.abspath(p), "label": label, "cached": bool(taghelp.cached(p))})
        for r in self._lib_roots()["roots"]:                                 # #311: Einstellungen › Ordner
            add(r["path"], f"Bibliothek {r['name']}")
        add(getattr(self, "tag_root", ""), "im Tagger geladen")
        try:
            for lib in self.snap_store.libraries():
                add(lib.get("root"), f"Snapshot-Bibliothek {lib.get('name') or ''}".strip())
        except Exception:  # noqa: BLE001 – Speicher nicht lesbar: dann eben ohne
            pass
        return out

    def help_tags(self, root=None) -> dict:
        roots = self._help_roots()
        root = root or self.cfg.get("help_scan_root") or (roots[0]["path"] if roots else "")
        res = taghelp.cached(root) if root else None
        custom = [(r["pattern"], r["source"]) for r in (self.cfg.get("tag_origins") or [])]
        import origins
        o = self.origins
        d = taghelp.overview(lambda k: o.of(k) or ("unknown" if taghelp.is_custom(k) else None),
                             self.origin_catalog(), origins.BUILTIN, res, custom)
        d.update(roots=roots, root=root)
        return d

    def start_tag_scan(self, root):
        """Bibliothek einlesen (mit Listen-Cache) und zählen, welche Felder wie oft vorkommen."""
        import core
        root = (root or "").strip()
        if not root or not os.path.isdir(root):
            return {"ok": False, "error": "Bitte einen vorhandenen Ordner wählen."}

        def job(cancel, progress):
            t0 = time.time()
            stats = {}
            files, errors = core.load_files(root, True, cancel, progress, None, self._list_cache_on(), stats)
            for c in stats.get("caches") or []:
                try:
                    c.save()
                except Exception:  # noqa: BLE001
                    pass
            progress(("text", "Zähle Felder …"))
            r = taghelp.scan(files, root)
            self.cfg["help_scan_root"] = root
            import core as _core
            _core.save_config({"help_scan_root": root})
            return {"files": r["count"], "keys": len(r["families"]), "errors": len(errors),
                    "seconds": round(time.time() - t0, 1), "root": root}
        return self._run("tagscan", "Bibliothek scannen", job)

    def tag_field_filter(self, key) -> dict:
        """Indizes der im Tagger geladenen Titel, die das Feld (bzw. Muster) haben → Filter in der Liste."""
        with self.lock:
            hit = [i for i, f in enumerate(self.tag_files)
                   if taghelp.matches(sorted({taghelp._family(k) for k in f.items}), str(key or ""))]
            return {"key": key, "label": key, "has": hit, "count": len(self.tag_files)}
