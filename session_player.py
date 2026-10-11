"""MarKusSXCH TagStudio – Sitzung: Player-Einstellungen, Fenster-Nachrichten und Wiedergabe (#36–#69, #91–#102)."""
from __future__ import annotations

import base64
import os

import time

import core
import keys
import ratings
from id3tags import MV

# Layout der Web-Oberfläche (Splitter, eingeklappte Seitenleiste): Schlüssel → erlaubter Typ


class PlayerMixin:
    """Teil der Klasse Session (session.py) – nutzt deren Zustand (self.cfg, self.lock, …)."""

    PLAYER_PREFS = {"wave": (bool, True), "follow": (bool, True), "start": (str, "0"), "vol": ((int, float), 0.8),
                    "repeat": (bool, False), "live": (bool, False),
                    "xfade": (int, 0), "xfade_start": (str, "start"), "xfade_after": (int, 0),          # #94
                    "xfade_sync": (bool, True), "xfade_return": (int, 8),                                # #102
                    "layout": (str, "bottom"), "top_collapsed": (bool, False),                           # #68
                    "deck2": (bool, False), "deck_target": (str, "A"), "vol_b": ((int, float), 0.8),     # #67
                    "sink_b": (str, ""), "start_b": (str, "0"), "repeat_b": (bool, False),
                    "startmode": (str, "last"),                                                          # #93
                    "resume": (bool, True), "resume_play": (str, "pause"),                               # #126
                    "xfade_phase": (bool, True), "xfade_bars": (int, 0)}                                 # #76
    PLAYER_CHOICES = {"start": ("0", "30", "60", "cue"), "resume_play": ("pause", "play", "was"), "xfade_bars": (0, 4, 8, 16), "layout": ("bottom", "top"), "startmode": ("last", "default"),
                      "xfade_start": ("start", "0", "cue"), "deck_target": ("A", "B"),
                      "start_b": ("0", "30", "60", "cue")}
    PLAYER_RANGES = {"vol": (0.0, 1.0), "vol_b": (0.0, 1.0), "xfade": (0, 30), "xfade_after": (0, 600), "xfade_return": (0, 120)}

    def _player_clean(self, p) -> dict:
        p = p if isinstance(p, dict) else {}
        out = {}
        for k, (typ, default) in self.PLAYER_PREFS.items():
            v = p.get(k, default)
            out[k] = v if isinstance(v, typ) and (typ is bool) == isinstance(v, bool) else default
            if k in self.PLAYER_CHOICES and out[k] not in self.PLAYER_CHOICES[k]:
                out[k] = default
        for k, (lo, hi) in self.PLAYER_RANGES.items():
            out[k] = max(lo, min(hi, type(lo)(out[k])))
        return out

    def player_prefs(self, at_start=False) -> dict:
        """Aktuelle Player-Einstellungen; at_start: beim Programmstart – mit „startmode = default“ gelten die
        gespeicherten Standards (#93), sonst die zuletzt benutzten."""
        out = self._player_clean(self.cfg.get("player"))
        defaults = self.cfg.get("player_defaults")
        if at_start and out["startmode"] == "default" and isinstance(defaults, dict):
            mode = out["startmode"]
            out = self._player_clean(defaults)
            out["startmode"] = mode
        out["has_defaults"] = isinstance(defaults, dict)
        out["window"] = self.cfg.get("player_window") if isinstance(self.cfg.get("player_window"), dict) else None
        return out

    # ------------------------------------------------------------------ Wiedergabe fortsetzen (#126)
    def player_resume_save(self, state) -> bool:
        """Titel (Pfad) und Position je Player merken: {"A": {"path", "pos", "vol"} | None, "B": …}."""
        if not isinstance(state, dict):
            raise ValueError("Zustand erwartet")
        out = {}
        for deck in ("A", "B"):
            d = state.get(deck)
            if isinstance(d, dict) and isinstance(d.get("path"), str) and d["path"]:
                out[deck] = {"path": d["path"][:4096], "pos": max(0.0, round(float(d.get("pos") or 0), 1)),
                             "playing": bool(d.get("playing"))}
        if out == self.cfg.get("player_resume"):
            return False
        self.cfg["player_resume"] = out
        core.save_config({"player_resume": out})
        return True

    def player_resume(self) -> dict:
        """Gemerkter Stand je Player mit Tagger-Index, falls die Datei gerade im Tagger geladen ist."""
        st = self.cfg.get("player_resume") if isinstance(self.cfg.get("player_resume"), dict) else {}
        prefs = self._player_clean(self.cfg.get("player"))
        on = prefs.get("resume", True)
        with self.lock:
            where = {os.path.normcase(os.path.abspath(f.path)): i for i, f in enumerate(self.tag_files)}
        out = {"on": on, "play": prefs.get("resume_play", "pause")}
        for deck, d in st.items():
            if deck in ("A", "B") and isinstance(d, dict) and d.get("path"):
                p = d["path"]
                out[deck] = {"path": p, "pos": float(d.get("pos") or 0), "exists": os.path.isfile(p), "playing": bool(d.get("playing")),
                             "i": where.get(os.path.normcase(os.path.abspath(p)))}
        return out

    def set_player_pref(self, name, value):
        if name not in self.PLAYER_PREFS:
            raise ValueError(f"Unbekannte Player-Einstellung: {name}")
        typ = self.PLAYER_PREFS[name][0]
        if not isinstance(value, typ) or (typ is bool) != isinstance(value, bool):
            raise ValueError(f"Ungültiger Wert für {name}")
        if name in self.PLAYER_CHOICES and value not in self.PLAYER_CHOICES[name]:
            raise ValueError(f"{name}: {', '.join(self.PLAYER_CHOICES[name])}")
        p = dict(self.cfg.get("player") or {})
        if name in self.PLAYER_RANGES:
            lo, hi = self.PLAYER_RANGES[name]
            value = max(lo, min(hi, type(lo)(value)))
        p[name] = value
        self.cfg["player"] = p
        core.save_config({"player": p})
        return self.player_prefs()

    # ------------------------------------------------------------------ Nachrichten zwischen Fenstern (#69)
    def bus_post(self, chan, msg) -> int:
        """Nachricht an einen Kanal (z. B. „pl_cmd“: Befehle vom abgedockten Player, „pl_state“: Zustand für ihn)."""
        import collections
        with self._bus_lock():
            q = self._bus.setdefault(str(chan), {"seq": 0, "msgs": collections.deque(maxlen=200), "seen": 0.0})
            q["seq"] += 1
            q["msgs"].append((q["seq"], msg))
            return q["seq"]

    def bus_poll(self, chan, since=0) -> dict:
        """Neue Nachrichten seit `since`. `peer`: Sekunden seit die Gegenseite diesen Kanal zuletzt abgefragt hat
        (das Hauptfenster erkennt so ein geschlossenes Player-Fenster)."""
        import collections
        with self._bus_lock():
            q = self._bus.setdefault(str(chan), {"seq": 0, "msgs": collections.deque(maxlen=200), "seen": 0.0})
            q["seen"] = time.time()
            since = since if isinstance(since, int) else 0
            return {"seq": q["seq"], "msgs": [m for n, m in q["msgs"] if n > since]}

    def bus_sync(self, poll_chan, since=0, post_chan=None, msg=None, peer_chan=None) -> dict:
        """Ein Aufruf statt drei (Abfrage, optional senden, Gegenseite prüfen) – für den 5-mal-pro-Sekunde-Takt."""
        if post_chan is not None and msg is not None:
            self.bus_post(post_chan, msg)
        out = self.bus_poll(poll_chan, since)
        if peer_chan is not None:
            out["peer"] = self.bus_peer(peer_chan)
        return out

    def bus_peer(self, chan) -> float | None:
        with self._bus_lock():
            q = self._bus.get(str(chan))
            return round(time.time() - q["seen"], 2) if q and q["seen"] else None

    def bus_reset(self, chan) -> None:
        with self._bus_lock():
            self._bus.pop(str(chan), None)

    def _bus_lock(self):
        return self._buslock

    PLAYER_WIN_MIN = {False: (1000, 330), True: (1000, 600)}       # #69: (Breite, Höhe) ohne / mit Player B
    PLAYER_WIN_DEFAULT = {False: (1280, 380), True: (1280, 680)}

    def player_window_size(self, two=False) -> dict:
        """Grösse des abgedockten Players: gemerkte Grösse, aber nie kleiner als nötig (mit Player B höher)."""
        g = self.cfg.get("player_window") if isinstance(self.cfg.get("player_window"), dict) else {}
        mw, mh = self.PLAYER_WIN_MIN[bool(two)]
        dw, dh = self.PLAYER_WIN_DEFAULT[bool(two)]
        w, h = (g.get("w") or dw), (g.get("h") or dh)
        return {"w": max(mw, int(w)), "h": max(mh, int(h)), "x": g.get("x"), "y": g.get("y")}

    def set_player_window(self, geom) -> bool:
        """#69: Grösse und Position des abgedockten Player-Fensters merken."""
        if not isinstance(geom, dict):
            return False
        g = {k: int(geom[k]) for k in ("x", "y", "w", "h") if isinstance(geom.get(k), (int, float))}
        if len(g) != 4 or g["w"] < 200 or g["h"] < 80:
            return False
        self.cfg["player_window"] = g
        core.save_config({"player_window": g})
        return True

    def player_defaults(self, action) -> dict:
        """#93: „save“ = aktuelle Einstellungen als Standard beim Start, „reset“ = Standards löschen,
        „apply“ = Standards jetzt übernehmen."""
        if action == "save":
            d = self._player_clean(self.cfg.get("player"))
            d.pop("startmode", None)
            self.cfg["player_defaults"] = d
            core.save_config({"player_defaults": d})
        elif action == "reset":
            self.cfg["player_defaults"] = None
            core.save_config({"player_defaults": None})
        elif action == "apply":
            d = self.cfg.get("player_defaults")
            if isinstance(d, dict):
                p = {**self._player_clean(d), "startmode": self._player_clean(self.cfg.get("player"))["startmode"]}
                self.cfg["player"] = p
                core.save_config({"player": p})
        else:
            raise ValueError("save, reset oder apply")
        return {**self.player_prefs(), "defaults": self.cfg.get("player_defaults")}


    # ================================================================== Wiedergabe
    def media_info(self, kind, ref) -> dict:
        """Datei für den Player: kind „tag“ (ref = Index im Tagger), „side“ (ref = „L“/„R“ im Vergleich) oder
        „stem“ (ref = Pfad einer nicht als MP3 geladenen Spur). Mit `stems` (#66): Original und Spuren derselben
        Gruppe, damit der Player an derselben Stelle umschalten kann."""
        with self.lock:
            if kind == "tag" and isinstance(ref, int) and 0 <= ref < len(self.tag_files):
                f = self.tag_files[ref]
            elif kind == "side" and ref in ("L", "R"):
                f = self._file(ref)
            elif kind == "stem":
                parent, st = next(((p, s) for p, lst in self.tag_stems.items() for s in lst if s["path"] == ref),
                                  (None, None))
                if st is None:
                    raise ValueError("Diese Spur ist nicht (mehr) geladen.")
                out = {"path": st["path"], "name": os.path.basename(st["path"]), "title": "", "artist": "",
                       "duration": 0.0, "kind": kind, "ref": ref, "key": "", "bpm": "", "stem": st["name"]}
                pf = self.tag_files[parent] if parent is not None and parent < len(self.tag_files) else None
                if pf is not None:          # Spur ohne eigene Tags: Titel, Tonart, Tempo vom Original
                    out.update(title=pf.text("TIT2"), artist=pf.text("TPE1").replace(MV, ", "),
                               duration=float(getattr(pf, "duration", 0) or 0), **self._key_info(pf), bpm=pf.text("TBPM"))
                out["stems"] = self._stem_group(parent)
                return out
            else:
                f = None
            if f is None:
                raise ValueError("Keine Datei zum Abspielen gewählt.")
            title, artist = f.text("TIT2"), f.text("TPE1").replace(MV, ", ")
            out = {"path": f.path, "name": os.path.basename(f.path), "title": title, "artist": artist,
                   "duration": float(getattr(f, "duration", 0) or 0), "kind": kind, "ref": ref,
                   **self._key_info(f), "bpm": f.text("TBPM"), "stems": [],
                   "rating": ratings.get_rating(f), "like": ratings.get_like(f), "markable": not self._ro(f)}
            if kind == "tag":
                parent = self.tag_parent.get(ref, ref if ref in self.tag_stems else None)
                out["stems"] = self._stem_group(parent)
                if parent is not None and parent != ref:
                    out["stem"] = next((s["name"] for s in self.tag_stems.get(parent, []) if s["i"] == ref), "")
                    pf = self.tag_files[parent]
                    for k, fid in (("title", "TIT2"), ("bpm", "TBPM")):
                        out[k] = out[k] or pf.text(fid)
                    if not out["key"]:
                        out.update(self._key_info(pf))
            return out

    @staticmethod
    def _key_info(f) -> dict:
        """Tonart als Camelot-Code plus die anderen Schreibweisen (#63)."""
        code = keys.parse_key(f.text("TKEY"))
        return {"key": code, "key_alt": {"musical": keys.format_key(code, "musical"),
                                         "openkey": keys.format_key(code, "openkey")} if code else {}}

    def _stem_group(self, parent) -> list:
        """Original + Spuren als Player-Ziele [{label, kind, ref}] – leer ohne Stems."""
        if parent is None or not self.tag_stems.get(parent):
            return []
        out = [{"label": "Original", "kind": "tag", "ref": parent}]
        for s in self.tag_stems[parent]:
            out.append({"label": s["name"], "kind": "tag" if s["i"] is not None else "stem",
                        "ref": s["i"] if s["i"] is not None else s["path"]})
        return out

    def media_cover(self, kind, ref, size=240) -> dict:
        """#101: Cover des Titels im Player (verkleinert, aus dem Vorschau-Cache) als data-URL."""
        import thumbs
        with self.lock:
            if kind == "tag" and isinstance(ref, int) and 0 <= ref < len(self.tag_files):
                f = self.tag_files[ref]
            elif kind == "side" and ref in ("L", "R"):
                f = self._file(ref)
            else:
                f = None
            c = self._front_cover(f) if f is not None else None
        if c is None:
            return {"src": ""}
        size = max(48, min(600, int(size or 240)))
        png = thumbs.make_png(c.data, size)
        if png:
            return {"src": "data:image/png;base64," + base64.b64encode(png).decode("ascii"), "desc": c.describe()}
        if len(c.data) > 4_000_000:
            return {"src": ""}
        return {"src": f"data:{c.mime or 'image/jpeg'};base64,{base64.b64encode(c.data).decode('ascii')}", "desc": c.describe()}

    def media_extra(self, kind, ref) -> dict:
        """Cue-Punkte (Serato, Mixed In Key) und Wellenform aus dem Cache für den Player."""
        import cues
        import waveform
        if kind == "stem":                       # FLAC/WAV-Spur: keine Tags, Wellenform über den Dateiinhalt
            path = self.media_info(kind, ref)["path"]
            out = {"cues": [], "wave": None, "wave_key": ""}
            try:
                out["wave_key"] = waveform.audio_key(path)
                out["wave"] = waveform.load(out["wave_key"])
            except (OSError, ValueError):
                pass
            return out
        with self.lock:
            f = self.tag_files[ref] if kind == "tag" and isinstance(ref, int) and 0 <= ref < len(self.tag_files) \
                else self._file(ref) if kind == "side" and ref in ("L", "R") else None
            if f is None:
                raise ValueError("Keine Datei zum Abspielen gewählt.")
            out = {"cues": cues.read(f), "wave": None, "wave_key": ""}
            out["grid"] = self._beat_grid(f, out["cues"])                        # #76: Beatgrid für den Player
        try:
            out["wave_key"] = waveform.key_for(f)
            out["wave"] = waveform.load(out["wave_key"])
        except (OSError, ValueError):
            pass
        return out

    @staticmethod
    def _beat_grid(f, cue_list) -> dict | None:
        """#76: Beatgrid aus Serato (GEOB „Serato BeatGrid“), sonst geschätzt aus dem BPM-Tag mit dem ersten Cue
        als erstem Schlag. → {"bpm", "first", "markers", "source", "exact"} oder None."""
        import serato
        try:
            bg = serato.of_file(f).get("BeatGrid")
        except Exception:  # noqa: BLE001
            bg = None
        if bg and not bg.get("error") and bg.get("bpm") and bg.get("markers"):
            return {"bpm": bg["bpm"], "first": bg["first"], "source": "Serato", "exact": True,
                    "markers": [{"pos": m["pos"], "bpm": m["bpm"]} for m in bg["markers"]]}
        import tagger
        try:
            bpm = float(tagger.text_of(f, "TBPM").replace(",", ".") or 0)
        except ValueError:
            bpm = 0
        if not 40 <= bpm <= 300:
            return None
        first = next((c["pos"] for c in cue_list if c.get("kind") == "cue"), 0.0)
        period = 60 / bpm
        first = first % period if first else 0.0           # erster Schlag am Anfang, im Raster des ersten Cues
        return {"bpm": round(bpm, 3), "first": round(first, 4), "source": "BPM-Tag" + (" + Cue" if first else ""),
                "exact": False, "markers": [{"pos": round(first, 4), "bpm": round(bpm, 3)}]}

    def wave_save(self, key, peaks, rms) -> dict:
        """Von der Oberfläche berechnete Wellenform im Cache ablegen."""
        import waveform
        try:
            waveform.save(str(key), peaks, rms)
        except (OSError, ValueError) as ex:
            return {"ok": False, "error": str(ex)}
        return {"ok": True}

    def media_paths(self, kind, refs) -> list:
        return [self.media_info(kind, r)["path"] for r in (refs if isinstance(refs, list) else [refs])]

    def players(self) -> list:
        return list(self.cfg.get("players") or [])

    def set_players(self, lst) -> list:
        import players as pl
        cleaned = pl.clean(lst)
        self.cfg["players"] = cleaned
        core.save_config({"players": cleaned})
        return cleaned

    def play_external(self, kind, refs, index=None) -> dict:
        """Dateien im externen Player (index in der Player-Liste) bzw. im Standardprogramm öffnen."""
        import players as pl
        paths = self.media_paths(kind, refs)
        lst = self.players()
        player = lst[index] if isinstance(index, int) and 0 <= index < len(lst) else None
        try:
            pl.open_files(paths, player)
        except (OSError, ValueError) as ex:
            return {"ok": False, "error": str(ex) or type(ex).__name__}
        return {"ok": True, "count": len(paths), "player": player["name"] if player else "Standardprogramm"}
