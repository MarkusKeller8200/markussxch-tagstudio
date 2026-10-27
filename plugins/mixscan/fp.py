"""Mix analysieren (#261) – Audio-Fingerabdruck, tempo- und tonhöhenrobust (Verfahren A, docs/KONZEPT-MIXSCAN.md).

Läuft in der Umgebung des Plugins (NumPy, SciPy; Dekodieren mit FFmpeg). Eigene Umsetzung nach dem bekannten
Landmark-Verfahren: markante Spitzen im Spektrogramm → Paare (f1, f2-f1, dt) als 32-Bit-Schlüssel mit Zeit. Der Index
bleibt einfach (Originaltempo); die **Abfrage** rechnet die Spitzen des Mixes in Tempo-Stufen um:
  - mit Keylock (nur Zeit gedehnt):        dt_titel = dt_mix · s,  f unverändert
  - ohne Keylock (Tempo und Tonhöhe):      dt_titel = dt_mix · s,  f_titel = f_mix / s
s = Tempo des Titels im Mix relativ zum Original (1,03 = 3 % schneller).
Treffer zählen je Block (5 s) nach (Titel, Stufe, zeitlicher Versatz); daraus entstehen Abschnitte mit Startzeit.
"""
from __future__ import annotations

import os
import subprocess

import numpy as np
from scipy.ndimage import maximum_filter

SR = 11025                 # Abtastrate für die Analyse (mono)
NFFT = 1024
HOP = 256                  # ≈ 23,2 ms je Rahmen
FPS = SR / HOP             # Rahmen je Sekunde
FMIN, FMAX = 5, 480        # Frequenz-Bins (≈ 54 Hz … 5,2 kHz)
PEAK_T, PEAK_F = 15, 15    # Umgebung für lokale Maxima (Rahmen, Bins)
PEAKS_PER_S = 18           # höchstens so viele Spitzen je Sekunde
FAN = 6                    # Partner je Anker
DT_MIN, DT_MAX = 2, 63     # Abstand zum Partner in Rahmen (6 Bit)
DF_MAX = 127               # |f2 - f1| in Bins (8 Bit)
BLOCK_S = 5.0              # Auswertung je Block
OFF_Q = 4                  # Versatz-Raster in Rahmen
OFF_TOL = 12               # erlaubte Versatz-Abweichung je Block Abstand (Tempo-Stufe ±0,5 %, Nachjustieren)
MAX_OCC = 400              # Schlüssel, die öfter vorkommen, sind wertlos (Stille, Klick)
GRID = tuple(round(1 + k / 100, 2) for k in range(-10, 11))      # 0,90 … 1,10


# =========================================================================== Audio
def decode(path: str, ffmpeg: str = "ffmpeg", start: float = 0.0, dur: float = 0.0) -> np.ndarray:
    """Datei → float32 mono SR (über FFmpeg, alle Formate)."""
    cmd = [ffmpeg, "-nostdin", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", path]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "replace").strip()[-300:] or f"FFmpeg-Fehler {r.returncode}")
    return np.frombuffer(r.stdout, dtype="<i2").astype(np.float32) / 32768.0


def spectrogram(y: np.ndarray) -> np.ndarray:
    """Log-Leistungsspektrum [Rahmen, Bins]."""
    if len(y) < NFFT:
        return np.zeros((0, NFFT // 2 + 1), dtype=np.float32)
    n = 1 + (len(y) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    win = np.hanning(NFFT).astype(np.float32)
    out = np.empty((n, NFFT // 2 + 1), dtype=np.float32)
    step = 4096                                   # in Stücken – Speicher bei langen Mixen begrenzen
    for a in range(0, n, step):
        fr = y[idx[a:a + step]] * win
        out[a:a + step] = np.log1p(np.abs(np.fft.rfft(fr, axis=1)) ** 2 * 1e3).astype(np.float32)
    return out


def peaks(S: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Markante Spitzen → (Rahmen, Bin), nach Zeit sortiert; je Sekunde höchstens PEAKS_PER_S."""
    if not len(S):
        return np.zeros(0, np.int32), np.zeros(0, np.int32)
    S = S[:, :FMAX]
    S = S - np.median(S, axis=0, keepdims=True)                   # gleichmässige Anteile (Rauschen, EQ) abziehen
    mx = maximum_filter(S, size=(PEAK_T, PEAK_F), mode="constant", cval=-np.inf)
    t, f = np.nonzero((S == mx) & (S > 0.5))
    keep = f >= FMIN
    t, f = t[keep], f[keep]
    v = S[t, f]
    sec = (t / FPS).astype(np.int64)                              # je Sekunde die stärksten behalten
    order = np.lexsort((-v, sec))
    t, f, sec = t[order], f[order], sec[order]
    first = np.r_[0, np.flatnonzero(np.diff(sec)) + 1]
    rank = np.arange(len(sec)) - np.repeat(first, np.diff(np.r_[first, len(sec)]))
    sel = rank < PEAKS_PER_S
    t, f = t[sel], f[sel]
    o = np.argsort(t, kind="stable")
    return t[o].astype(np.int32), f[o].astype(np.int32)


def pairs(t: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Anker mit den nächsten FAN Partnern → (t1, f1, f2, dt) als Gleitkomma-freie Ganzzahlen."""
    n = len(t)
    if n < 2:
        z = np.zeros(0, np.int32)
        return z, z, z, z
    A, B = [], []
    for k in range(1, FAN * 4):                    # Partner in zeitlicher Reihenfolge, gefiltert
        a = np.arange(n - k)
        b = a + k
        ok = (t[b] - t[a] >= DT_MIN) & (t[b] - t[a] <= DT_MAX) & (np.abs(f[b] - f[a]) <= DF_MAX)
        A.append(a[ok])
        B.append(b[ok])
    a = np.concatenate(A)
    b = np.concatenate(B)
    o = np.lexsort((t[b], a))                      # je Anker nach Partnerzeit, dann die ersten FAN
    a, b = a[o], b[o]
    first = np.r_[0, np.flatnonzero(np.diff(a)) + 1]
    rank = np.arange(len(a)) - np.repeat(first, np.diff(np.r_[first, len(a)]))
    sel = rank < FAN
    a, b = a[sel], b[sel]
    return t[a], f[a], f[b], t[b] - t[a]


def hashes(f1, f2, dt) -> np.ndarray:
    return ((f1.astype(np.uint32) & 511) << 15) | (((f2 - f1 + 128).astype(np.uint32) & 255) << 7) | (dt.astype(np.uint32) & 127)


def fingerprint(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Audio → (Schlüssel uint32, Zeit in Rahmen int32)."""
    t, f = peaks(spectrogram(y))
    t1, f1, f2, dt = pairs(t, f)
    return hashes(f1, f2, dt), t1.astype(np.int32)


# =========================================================================== Index
class Index:
    """Alle Schlüssel der Bibliothek, sortiert – Abfrage per np.searchsorted (schnell, ohne Datenbank)."""

    def __init__(self, H=None, T=None, I=None):
        self.H = np.zeros(0, np.uint32) if H is None else H
        self.T = np.zeros(0, np.int32) if T is None else T
        self.I = np.zeros(0, np.int32) if I is None else I

    @classmethod
    def build(cls, parts):
        """parts: [(Titel-Nr., Schlüssel, Zeiten)]"""
        parts = [p for p in parts if len(p[1])]
        if not parts:
            return cls()
        H = np.concatenate([p[1] for p in parts])
        T = np.concatenate([p[2] for p in parts])
        I = np.concatenate([np.full(len(p[1]), p[0], np.int32) for p in parts])
        o = np.argsort(H, kind="stable")
        return cls(H[o], T[o], I[o])

    def save(self, path):
        np.savez(path, H=self.H, T=self.T, I=self.I)

    @classmethod
    def load(cls, path):
        with np.load(path) as d:
            return cls(d["H"], d["T"], d["I"])

    def lookup(self, q: np.ndarray, qt: np.ndarray):
        """→ (Mix-Zeit, Titel, Titel-Zeit) aller Treffer; häufige Schlüssel (> MAX_OCC) zählen nicht."""
        lo = np.searchsorted(self.H, q, "left")
        hi = np.searchsorted(self.H, q, "right")
        n = hi - lo
        ok = (n > 0) & (n <= MAX_OCC)
        lo, n, qt = lo[ok], n[ok], qt[ok]
        if not len(n):
            z = np.zeros(0, np.int64)
            return z, z, z
        rep = np.repeat(np.arange(len(n)), n)
        pos = np.repeat(lo - np.r_[0, np.cumsum(n)[:-1]], n) + np.arange(n.sum())
        return qt[rep].astype(np.int64), self.I[pos].astype(np.int64), self.T[pos].astype(np.int64)


# =========================================================================== Abfrage
def _soft(x: np.ndarray) -> list[np.ndarray]:
    """Gerundete Werte; liegt der Wert nahe an x,5, zusätzlich der andere Nachbar (nur dort, sonst doppelt)."""
    r = np.rint(x).astype(np.int64)
    fr = x - np.floor(x)
    amb = np.abs(fr - 0.5) < 0.2
    alt = np.where(fr < 0.5, r + 1, r - 1)
    return [r, np.where(amb, alt, r)] if amb.any() else [r]


def query(index: Index, y: np.ndarray, grid=GRID, modes=("lock", "pitch"), progress=None, exclude=()) -> list[dict]:
    """Mix → Kandidaten je Block: [{block, cands: [(Treffer, Titel, s, Modus, Versatz)]}] (beste zuerst).
    exclude: Titel-Nummern, die nicht zählen (z. B. der Mix selbst, wenn er im indexierten Ordner liegt)."""
    excl = np.array(sorted({int(x) for x in exclude or ()}), dtype=np.int64)
    t, f = peaks(spectrogram(y))
    t1, f1, f2, dtm = pairs(t, f)
    blk = int(round(BLOCK_S * FPS))
    nblocks = int(t.max() // blk + 1) if len(t) else 0
    best: dict = {}
    variants = [(s, m) for m in modes for s in grid if not (m == "pitch" and s == 1.0)]
    for vi, (s, mode) in enumerate(variants):
        if progress:
            progress(vi, len(variants))
        if mode == "pitch":
            qs = [(_soft(dtm * s), _soft(f1 / s), _soft(f2 / s))]
        else:
            qs = [(_soft(dtm * s), [f1.astype(np.int64)], [f2.astype(np.int64)])]
        Q, QT = [], []
        for dts, g1s, g2s in qs:                    # Rundung an der Grenze: beide Nachbarn abfragen
            for dt in dts:
                for g1 in g1s:
                    for g2 in g2s:
                        ok = (dt >= DT_MIN) & (dt <= 127) & (g1 >= 0) & (g1 < 512) & (np.abs(g2 - g1) <= DF_MAX)
                        Q.append(hashes(g1[ok], g2[ok], dt[ok]))
                        QT.append(t1[ok])
        q, qt = np.concatenate(Q), np.concatenate(QT)
        # gleiche Abfrage (Zeit + Schlüssel) nur einmal
        uq = np.unique((qt.astype(np.int64) << 32) | q.astype(np.int64))
        mt, ti, tt = index.lookup((uq & 0xFFFFFFFF).astype(np.uint32), (uq >> 32).astype(np.int64))
        if len(excl) and len(ti):
            keep = ~np.isin(ti, excl)
            mt, ti, tt = mt[keep], ti[keep], tt[keep]
        if not len(mt):
            continue
        rel = tt - np.rint(mt * s).astype(np.int64)
        b = mt // blk
        for shift in (0, OFF_Q // 2):               # Versatz-Raster zweimal versetzt – Grenzfälle nicht teilen
            off = (rel + shift) // OFF_Q
            key = (b << 40) | ((ti & 0xFFFFF) << 20) | ((off + (1 << 19)) & 0xFFFFF)
            u, c = np.unique(key, return_counts=True)
            ub, ut, uo = u >> 40, (u >> 20) & 0xFFFFF, (u & 0xFFFFF) - (1 << 19)
            o = np.lexsort((-c, ut, ub))
            ub, ut, uo, c = ub[o], ut[o], uo[o], c[o]
            first = np.r_[0, np.flatnonzero((np.diff(ub) != 0) | (np.diff(ut) != 0)) + 1]
            grp = np.repeat(first, np.diff(np.r_[first, len(ub)]))
            rank = np.arange(len(ub)) - grp
            sel = np.flatnonzero((rank < 3) & (c >= 4))       # je (Block, Titel) die 3 besten Versätze:
            for kb, kt, ko, kc, kr in zip(ub[sel].tolist(), ut[sel].tolist(), uo[sel].tolist(), c[sel].tolist(),
                                          rank[sel].tolist()):   # Musik wiederholt sich (Loops, 4-Takt-Phrasen)
                cur = best.setdefault(kb, {})
                if kr == 0:
                    prev = cur.get(kt)
                    if prev is None or kc > prev[0]:
                        cur[kt] = [kc, kt, s, mode, ko * OFF_Q - shift, [ko * OFF_Q - shift]]
                elif cur.get(kt) and cur[kt][2] == s and cur[kt][3] == mode and kc * 2 >= cur[kt][0]:
                    cur[kt][5].append(ko * OFF_Q - shift)
    out = []
    for b in range(nblocks):
        cands = [tuple(x[:5]) + (x[5],) for x in sorted(best.get(b, {}).values(), key=lambda x: -x[0])[:5]]
        out.append({"block": b, "start": b * BLOCK_S, "cands": cands})
    return out


def segments(blocks: list[dict], min_score: int = 70, ratio: float = 1.4, win: int = 5) -> list[dict]:
    """Kandidaten je Block → Abschnitte {start, end, track, hits, tempo, keylock, conf, pos}.
    Je Titel werden die Treffer über win Blöcke (gleitend) summiert – so setzt sich ein Titel durch, der in jedem
    Block vorne mit dabei ist, gegen zufällige Einzeltreffer anderer. Ein Block gehört dem Titel mit der höchsten
    Summe, wenn sie min_score erreicht und ratio-mal über dem Zweiten liegt."""
    n = len(blocks)
    tids = sorted({c[1] for bl in blocks for c in bl["cands"]})
    if not n or not tids:
        return []
    col = {t: k for k, t in enumerate(tids)}
    M = np.zeros((n, len(tids)), np.float32)
    info = {}
    for bl in blocks:
        for hits, tid, sc, mode, off, *more in bl["cands"]:
            M[bl["block"], col[tid]] = hits
            info[(bl["block"], tid)] = (sc, mode, off, more[0] if more else [off])
    # gleitende Summe nur über Blöcke mit passendem Versatz: derselbe Titel an derselben Stelle (Zufallstreffer
    # anderer Titel springen im Versatz und summieren sich nicht)
    W = M.copy()
    h = win // 2
    for (bb, tid), (sc, mode, off, offs) in info.items():
        k = col[tid]
        for d in range(-h, h + 1):
            nb = bb + d
            if d == 0 or not 0 <= nb < n or (nb, tid) not in info:
                continue
            other = info[(nb, tid)][3]
            if any(abs(a - b) <= OFF_TOL * abs(d) for a in offs for b in other):
                W[bb, k] += M[nb, k]
    order = np.argsort(-W, axis=1)
    best, second = order[:, 0], order[:, 1] if W.shape[1] > 1 else order[:, 0]
    bv = W[np.arange(n), best]
    sv = W[np.arange(n), second] if W.shape[1] > 1 else np.zeros(n)
    own = M[np.arange(n), best] > 0                                   # Titel muss im Block selbst vorkommen
    ok = (bv >= min_score) & (bv >= ratio * sv) & own
    runs, cur = [], None
    for b in range(n):
        t = tids[best[b]] if ok[b] else None
        if cur and t == cur["track"] and b - cur["b1"] <= 2:
            cur["b1"] = b
            cur["bl"].append(b)
        elif t is not None:
            cur = {"track": t, "b0": b, "b1": b, "bl": [b]}
            runs.append(cur)
    merged = []                                       # gleicher Titel nach kurzer Unterbrechung (≤ 20 s): ein Abschnitt
    for r in runs:
        if merged and merged[-1]["track"] == r["track"] and r["b0"] - merged[-1]["b1"] <= 4:
            merged[-1]["b1"] = r["b1"]
            merged[-1]["bl"] += r["bl"]
        else:
            merged.append(r)
    out = []
    for r in merged:
        hits = np.array([M[b, col[r["track"]]] for b in r["bl"]])
        if len(r["bl"]) < 2 and hits.sum() < min_score:
            continue
        meta = [info[(b, r["track"])] for b in r["bl"] if (b, r["track"]) in info]
        sc = float(np.median([m[0] for m in meta]))
        modes = [m[1] for m in meta]
        mode = max(set(modes), key=modes.count)
        b0 = r["b0"]
        off0 = info[(b0, r["track"])][2]
        blk = BLOCK_S * FPS
        conf = float(min(0.99, (1 - np.exp(-hits.mean() / 25)) * min(1.0, 0.4 + len(hits) / 6)))
        if mode == "pitch" and len(hits) < 6:      # ohne Keylock doppelt so viele Versuche → kurze Treffer eher Zufall
            conf *= 0.75                            # (Messung 27.10.2026: drei kurze Fehltreffer am Ende des Mixes)
        out.append({"start": b0 * BLOCK_S, "end": (r["b1"] + 1) * BLOCK_S, "track": r["track"], "hits": int(hits.sum()),
                    "blocks": len(hits), "tempo": round((sc - 1) * 100, 1), "keylock": mode == "lock",
                    "conf": round(conf, 2), "pos": max(0.0, (off0 + b0 * blk * sc) / FPS)})
    return out


def fmt_time(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


def size_of(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
