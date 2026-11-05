"""Session-Teil „Umwandeln“ (#451): markierte Titel des Taggers MP3 ↔ WAV/AIFF mit Tags in eine neue Datei."""
from __future__ import annotations

import os

import convert
import core


class ConvertMixin:
    def _conv_opts(self, target=None, dest=None, bitrate=None) -> dict:
        c = self.cfg.get("convert") if isinstance(self.cfg.get("convert"), dict) else {}
        target = target if target in convert.TARGETS else c.get("target") if c.get("target") in convert.TARGETS else "wav"
        dest = dest if dest in ("export", "beside") else c.get("dest") if c.get("dest") in ("export", "beside") else "export"
        try:
            bitrate = int(bitrate if bitrate is not None else c.get("bitrate", convert.DEFAULT_BITRATE))
        except (TypeError, ValueError):
            bitrate = convert.DEFAULT_BITRATE
        if bitrate not in convert.BITRATES:
            raise ValueError("Bitrate nicht erlaubt")
        return {"target": target, "dest": dest, "bitrate": bitrate}

    def _conv_plan(self, idx, o):
        exp = self.export_dir()
        folder = (exp or os.path.expanduser("~")) if o["dest"] == "export" else None
        with self.lock:
            files = self._tsel(idx)
            dirty = [f.path for f in files if f.is_modified()]
            rows = convert.plan([f.path for f in files], o["target"], folder, dirty)
        return files, rows, exp

    def convert_preview(self, idx, target=None, dest=None, bitrate=None) -> dict:
        """Vorschau: Ziele je Titel, Probleme, Hinweise (FFmpeg, Serato)."""
        o = self._conv_opts(target, dest, bitrate)
        files, rows, exp = self._conv_plan(idx, o)
        for f, r in zip(files, rows):                                     # #456: Felder, die es im Ziel nicht gibt
            r["lost"] = convert.lost_keys(f, o["target"]) if not r["problem"] else []
        return {**o, "rows": rows, "ok": sum(1 for r in rows if not r["problem"]), "export": exp,
                "ffmpeg": bool(convert.find_ffmpeg()), "serato": any(convert.has_serato(f) for f in files),
                "lossy_src": any(convert.is_lossy_source(f) for f in files),
                "bitrates": list(convert.BITRATES), "kinds": sorted({convert.kind_of(f.path) for f in files} - {""})}

    def start_convert(self, idx, target, dest, bitrate) -> dict:
        o = self._conv_opts(target, dest, bitrate)
        files, rows, _exp = self._conv_plan(idx, o)
        self.cfg["convert"] = o
        core.save_config({"convert": o})
        todo = [(f, r) for f, r in zip(files, rows) if not r["problem"]]
        if not todo:
            return {"ok": False, "error": "Nichts umzuwandeln – siehe Vorschau."}
        ff = convert.find_ffmpeg()
        if not ff:
            return {"ok": False, "error": "FFmpeg nicht gefunden – das Stems-Plugin installieren (bringt FFmpeg mit) "
                                          "oder FFmpeg in den Suchpfad legen."}

        def job(cancel, progress):
            done, errors = [], []
            progress(("total", len(todo)))
            for n, (f, r) in enumerate(todo, 1):
                if cancel.is_set():
                    break
                progress(("progress", n - 1, len(todo), r["src"]))
                try:
                    notes = []
                    done.append(convert.convert_one(f, r["dst"], o["target"], o["bitrate"], ff, cancel, notes))
                    if notes:
                        errors.append(f"{os.path.basename(r['dst'])}: nicht übernommen (gibt es im Format nicht): "
                                      + ", ".join(notes))
                except convert.Cancelled:
                    break
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"{os.path.basename(r['src'])}: {ex}")
            progress(("progress", len(todo), len(todo), todo[-1][1]["src"]))
            msg = f"{len(done)} Titel umgewandelt ({o['target'].upper()})." + (f" {len(errors)} Hinweis(e)." if errors else "")
            return {"done": done, "errors": errors, "message": msg,
                    "folder": os.path.dirname(done[0]) if done else ""}
        return self._run("convert", "Umwandeln", job)
