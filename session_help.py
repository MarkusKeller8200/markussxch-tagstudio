"""Session-Teil „Hilfe“ (#158): Handbuch (README), ID3-Felder, Tag-Übersicht mit Herkunft und Bibliotheks-Scan."""
from __future__ import annotations

import os
import sys
import time

import taghelp

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = {"readme": ("Handbuch", "README.md"), "id3": ("ID3-Felder", os.path.join("docs", "ID3-FELDER.md")),
        "plugins": ("Plugins", "PLUGINS.md")}


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
    def help_docs(self) -> dict:
        return {k: {"title": t, "text": _read_doc(rel)} for k, (t, rel) in DOCS.items()}

    # ------------------------------------------------------------------ Tag-Übersicht
    def _help_roots(self) -> list[dict]:
        """Ordner, die gescannt werden können: Standardordner des Taggers, geladener Ordner, Snapshot-Bibliotheken."""
        out, seen = [], set()

        def add(p, label):
            if p and os.path.isdir(p) and os.path.normcase(os.path.abspath(p)) not in seen:
                seen.add(os.path.normcase(os.path.abspath(p)))
                out.append({"path": os.path.abspath(p), "label": label, "cached": bool(taghelp.cached(p))})
        add(self.cfg.get("default_tagger"), "Standardordner Tagger")
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
