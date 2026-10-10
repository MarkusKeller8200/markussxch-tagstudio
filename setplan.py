"""DJ-Set: Reihenfolge optimieren und bewerten (nur Standardbibliothek).

Eigene Umsetzung. Kosten je Übergang aus Tonart (Camelot-Rad), BPM-Sprung
(auch Halb-/Doppeltempo) und Energie; dazu optional ein Energieverlauf über
das ganze Set (steigend, fallend, Welle).

Kleine Sets werden exakt gelöst (Held-Karp, dynamische Programmierung über
Teilmengen), grössere mit Greedy-Starts und lokaler Verbesserung
(2-opt, Verschieben, Tauschen). Feste Positionen („sperren“, Start/Ende)
gelten in beiden Verfahren.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import keys

# Exakt bis zu dieser Anzahl freier Titel (Laufzeit wächst mit 2^n · n²; 15 ≈ 1 s,
# 20 wäre in reinem Python zu langsam). Darüber Heuristik (gemessen ≤ 2 % über dem Optimum).
EXACT_MAX = 15
PROFILES = {"none": "egal", "rise": "steigend", "fall": "fallend", "wave": "Welle"}
KEY_KINDS = {
    "same": "gleiche Tonart",
    "adjacent": "±1 auf dem Rad",
    "parallel": "Paralleltonart",
    "boost": "Energie-Sprung (+2 / diagonal)",
    "jump": "Sprung",
    "unknown": "Tonart fehlt",
}
_KEY_COST = {"same": 0.0, "adjacent": 0.1, "parallel": 0.15, "boost": 0.45, "unknown": 0.5}
PENALTY = 3.0          # Zusatzkosten, wenn der BPM-Sprung über dem Maximum liegt


@dataclass
class Track:
    id: object
    key: str | None = None          # Camelot-Code wie „8A“
    bpm: float | None = None
    energy: int | None = None       # 0–100
    title: str = ""
    duration: float | None = None


@dataclass
class Options:
    w_key: float = 0.5
    w_bpm: float = 0.3
    w_energy: float = 0.2
    profile: str = "none"           # none | rise | fall | wave
    max_jump: float = 8.0           # Prozent
    missing: str = "end"            # end | neutral
    start: object = None            # Track-ID oder None
    end: object = None
    locks: dict = field(default_factory=dict)   # Position → Track-ID
    exact_max: int = EXACT_MAX
    time_limit: float = 3.0         # Sekunden für die Heuristik

    @classmethod
    def from_dict(cls, d: dict | None) -> "Options":
        o = cls()
        for k, v in (d or {}).items():
            if k == "locks":
                o.locks = {int(p): t for p, t in (v or {}).items()}
            elif hasattr(o, k) and v is not None:
                setattr(o, k, type(getattr(o, k))(v) if isinstance(getattr(o, k), (int, float, str)) else v)
        if o.profile not in PROFILES:
            o.profile = "none"
        o.max_jump = max(0.5, o.max_jump)
        return o


# ---------------------------------------------------------------- Einzelwerte

def key_kind(a: str | None, b: str | None) -> tuple[str, float]:
    """Art des Tonart-Übergangs und Kosten 0–1."""
    if not a or not b:
        return "unknown", _KEY_COST["unknown"]
    na, ma = keys.split(a)
    nb, mb = keys.split(b)
    d = min((na - nb) % 12, (nb - na) % 12)       # 0–6 auf dem Rad
    if ma == mb:
        if d == 0:
            return "same", 0.0
        if d == 1:
            return "adjacent", _KEY_COST["adjacent"]
        if d == 2:
            return "boost", _KEY_COST["boost"]
    else:
        if d == 0:
            return "parallel", _KEY_COST["parallel"]
        if d == 1:
            return "boost", _KEY_COST["boost"]
    # weiter weg: 0.65 (Abstand 2 mit Wechsel / 3) … 1.0 (Abstand 6)
    return "jump", min(1.0, 0.5 + 0.083 * (d + (0 if ma == mb else 1)))


def bpm_step(a: float | None, b: float | None) -> tuple[float | None, str]:
    """Prozentualer BPM-Unterschied unter Berücksichtigung von Halb-/Doppeltempo.
    Bezogen auf den kleineren der beiden verglichenen Werte – damit gilt a→b gleich wie b→a."""
    if not a or not b or a <= 0 or b <= 0:
        return None, ""
    best, rel = None, ""
    for factor, name in ((1.0, ""), (2.0, "x2"), (0.5, "half")):
        bb = b * factor
        p = abs(bb - a) / min(a, bb) * 100
        if best is None or p + 1e-9 < best:
            best, rel = p, name
    return best, rel


def energy_of(t: Track) -> tuple[int | None, bool]:
    """Energie 0–100; fehlt sie, grobe Schätzung aus dem BPM (90 → 20, 140 → 90)."""
    if t.energy is not None:
        return int(t.energy), False
    if t.bpm and t.bpm > 0:
        b = t.bpm
        while b < 80:
            b *= 2
        while b > 180:
            b /= 2
        return int(round(max(0, min(100, 20 + (b - 90) * 1.4)))), True
    return None, True


def target_curve(profile: str, n: int, lo: float, hi: float) -> list[float | None]:
    """Soll-Energie je Position."""
    if profile == "none" or n <= 0:
        return [None] * n
    out = []
    for p in range(n):
        x = p / (n - 1) if n > 1 else 0.0
        if profile == "rise":
            y = x
        elif profile == "fall":
            y = 1 - x
        else:  # wave: zwei Wellen, Start und Ende ruhig
            y = 0.5 - 0.5 * math.cos(4 * math.pi * x)
        out.append(lo + (hi - lo) * y)
    return out


def transition(a: Track, b: Track, opts: Options) -> dict:
    """Bewertung eines Übergangs a → b (Kosten symmetrisch)."""
    kk, kc = key_kind(a.key, b.key)
    pct, rel = bpm_step(a.bpm, b.bpm)
    if pct is None:
        bc, over = 0.5, False
    else:
        bc, over = min(1.0, pct / opts.max_jump), pct > opts.max_jump
    ea, _ = energy_of(a)
    eb, _ = energy_of(b)
    ec = abs(ea - eb) / 100 if ea is not None and eb is not None else 0.25
    wsum = (opts.w_key + opts.w_bpm + opts.w_energy) or 1.0
    cost = (opts.w_key * kc + opts.w_bpm * bc + opts.w_energy * ec) / wsum
    score = 0 if over else int(round(100 * (1 - cost)))
    return {
        "key": kk, "bpm_pct": None if pct is None else round(pct, 1), "bpm_rel": rel,
        "bpm_over": over, "energy_delta": None if ea is None or eb is None else eb - ea,
        "cost": cost + (PENALTY if over else 0.0), "score": score,
    }


# ---------------------------------------------------------------- Bewertung

_KEY_TAB: dict = {}


def _key_cost(a, b) -> float:
    """Tonart-Kosten aus einer Tabelle (24×24 Codes + fehlend) – schnell bei grossen Sets."""
    k = (a, b)
    c = _KEY_TAB.get(k)
    if c is None:
        c = _KEY_TAB[k] = key_kind(a, b)[1]
    return c


def _curve_for(tracks: list[Track], opts: Options):
    """Soll-Kurve über die Energie-Spanne des Sets; dazu die Energie je Titel."""
    en = [energy_of(t)[0] for t in tracks]
    known = [e for e in en if e is not None]
    lo, hi = (min(known), max(known)) if known else (0, 100)
    if hi - lo < 20:                       # flache Sets: Kurve trotzdem sichtbar
        mid = (hi + lo) / 2
        lo, hi = max(0, mid - 10), min(100, mid + 10)
    return target_curve(opts.profile, len(tracks), lo, hi), en


class _Model:
    """Vorberechnete Kostenmatrix und Positionskosten für eine Titelmenge.
    Die Paarkosten sind dieselben wie in transition()["cost"], nur ohne Zwischen-Dicts berechnet."""

    def __init__(self, tracks: list[Track], opts: Options):
        self.tracks, self.opts, n = tracks, opts, len(tracks)
        self.n = n
        self.curve, en = _curve_for(tracks, opts)
        wsum = (opts.w_key + opts.w_bpm + opts.w_energy) or 1.0
        wk, wb, we, mj = opts.w_key / wsum, opts.w_bpm / wsum, opts.w_energy / wsum, opts.max_jump
        ks = [t.key or None for t in tracks]
        bs = [t.bpm if t.bpm and t.bpm > 0 else None for t in tracks]
        T = self.T = [[0.0] * n for _ in range(n)]
        for i in range(n):
            ki, bi, ei, Ti = ks[i], bs[i], en[i], T[i]
            for j in range(i + 1, n):
                c = wk * _key_cost(ki, ks[j])
                bj = bs[j]
                if bi and bj:
                    pct = min(abs(bj - bi) / min(bi, bj), abs(bj * 2.0 - bi) / min(bi, bj * 2.0),
                              abs(bj * 0.5 - bi) / min(bi, bj * 0.5)) * 100
                    c += wb * (pct / mj if pct < mj else 1.0) + (PENALTY if pct > mj else 0.0)
                else:
                    c += wb * 0.5
                ej = en[j]
                c += we * (abs(ei - ej) / 100 if ei is not None and ej is not None else 0.25)
                Ti[j] = c
                T[j][i] = c
        self.P = [[0.0] * n for _ in range(n)]          # P[track][position]
        if opts.profile != "none":
            curve = self.curve
            for i, e in enumerate(en):
                Pi = self.P[i]
                if e is None:
                    for p in range(n):
                        Pi[p] = we * 0.25
                else:
                    for p in range(n):
                        Pi[p] = we * abs(e - curve[p]) / 100

    def cost(self, order: list[int]) -> float:
        c = sum(self.P[t][p] for p, t in enumerate(order))
        return c + sum(self.T[a][b] for a, b in zip(order, order[1:]))


def evaluate(tracks: list[Track], opts: Options | None = None) -> dict:
    """Bewertung einer Reihenfolge: je Übergang und gesamt (0–100)."""
    opts = opts or Options()
    trs = [transition(a, b, opts) for a, b in zip(tracks, tracks[1:])]
    mean = sum(t["score"] for t in trs) / len(trs) if trs else 100.0
    fit, curve = None, None
    if opts.profile != "none" and tracks:
        curve, en = _curve_for(tracks, opts)
        dev = [abs(e - curve[p]) for p, e in enumerate(en) if e is not None]
        fit = int(round(100 - sum(dev) / len(dev))) if dev else None
    score = mean if fit is None else 0.8 * mean + 0.2 * fit
    return {"score": int(round(score)), "transitions": trs, "energy_fit": fit, "curve": curve}


# ---------------------------------------------------------------- Optimierung

def _held_karp(m: _Model, free: list[int], fixed: dict[int, int]) -> list[int]:
    """Exakt: dp[(Maske, letzter)] über Positionen 0…n-1, feste Positionen erzwungen."""
    n = m.n
    idx = {t: b for b, t in enumerate(free)}
    INF = float("inf")
    # Zustand nach Position p: (Maske der freien, letzter Titel) → (Kosten, Vorgänger-Schlüssel)
    layer: dict = {}
    if 0 in fixed:
        t = fixed[0]
        layer[(0, t)] = (m.P[t][0], None)
    else:
        for t in free:
            layer[(1 << idx[t], t)] = (m.P[t][0], None)
    history = [layer]
    for p in range(1, n):
        nxt: dict = {}
        cands = [fixed[p]] if p in fixed else free
        for (mask, last), (c, _) in layer.items():
            for t in cands:
                if p not in fixed:
                    bit = 1 << idx[t]
                    if mask & bit:
                        continue
                    nm = mask | bit
                else:
                    nm = mask
                nc = c + m.T[last][t] + m.P[t][p]
                key = (nm, t)
                old = nxt.get(key)
                if old is None or nc < old[0]:
                    nxt[key] = (nc, (mask, last))
        layer = nxt
        history.append(layer)
    best = min(layer.items(), key=lambda kv: kv[1][0]) if layer else None
    if best is None:
        return []
    order, key = [], best[0]
    for p in range(n - 1, -1, -1):
        order.append(key[1])
        key = history[p][key][1]
    order.reverse()
    return order


def _greedy(m: _Model, free: list[int], fixed: dict[int, int], first: int | None) -> list[int]:
    left = set(free)
    order: list[int] = []
    for p in range(m.n):
        if p in fixed:
            order.append(fixed[p])
            continue
        if not order and first is not None:
            pick = first
        else:
            prev = order[-1] if order else None
            nxt_fixed = fixed.get(p + 1)
            pick = min(left, key=lambda t: (m.T[prev][t] if prev is not None else 0) + m.P[t][p]
                       + (m.T[t][nxt_fixed] if nxt_fixed is not None else 0))
        left.discard(pick)
        order.append(pick)
    return order


def _improve(m: _Model, order: list[int], movable: list[bool], deadline: float) -> list[int]:
    """Lokale Verbesserung bis kein Schritt mehr hilft oder die Zeit abläuft."""
    n, T, P = m.n, m.T, m.P
    cur = m.cost(order)
    improved = True
    while improved and time.monotonic() < deadline:
        improved = False
        # 2-opt: Abschnitt i..j umdrehen (Übergänge innen bleiben gleich, da symmetrisch)
        for i in range(n - 1):
            if not movable[i]:
                continue
            for j in range(i + 1, n):
                if not movable[j]:
                    break
                d = 0.0
                if i > 0:
                    d += T[order[i - 1]][order[j]] - T[order[i - 1]][order[i]]
                if j < n - 1:
                    d += T[order[i]][order[j + 1]] - T[order[j]][order[j + 1]]
                for k in range(i, j + 1):
                    d += P[order[i + j - k]][k] - P[order[k]][k]
                if d < -1e-9:
                    order[i:j + 1] = order[i:j + 1][::-1]
                    cur += d
                    improved = True
            if time.monotonic() >= deadline:
                break
        # Tauschen zweier beweglicher Positionen
        pos = [p for p in range(n) if movable[p]]
        for a in range(len(pos)):
            for b in range(a + 1, len(pos)):
                i, j = pos[a], pos[b]
                new = order[:]
                new[i], new[j] = new[j], new[i]
                c = m.cost(new) if j - i < 2 else _swap_cost(m, order, cur, i, j)
                if c < cur - 1e-9:
                    order, cur, improved = new, c, True
            if time.monotonic() >= deadline:
                break
    return order


def _swap_cost(m: _Model, order: list[int], cur: float, i: int, j: int) -> float:
    """Kosten nach Tausch nicht benachbarter Positionen i < j (nur betroffene Teile)."""
    T, P, n = m.T, m.P, m.n
    a, b = order[i], order[j]

    def around(p, t):
        c = P[t][p]
        if p > 0:
            c += T[order[p - 1] if p - 1 not in (i, j) else (b if p - 1 == i else a)][t]
        if p < n - 1:
            c += T[t][order[p + 1] if p + 1 not in (i, j) else (b if p + 1 == i else a)]
        return c

    old = P[a][i] + P[b][j]
    if i > 0:
        old += T[order[i - 1]][a]
    old += T[a][order[i + 1]]
    old += T[order[j - 1]][b]
    if j < n - 1:
        old += T[b][order[j + 1]]
    new = around(i, b) + around(j, a)
    return cur - old + new


def optimize(tracks: list[Track], opts: Options | None = None) -> dict:
    """Beste Reihenfolge suchen. Ergebnis: order (IDs), before/after, method, rest."""
    opts = opts or Options()
    t0 = time.monotonic()
    ids = [t.id for t in tracks]
    if len(set(ids)) != len(ids):
        raise ValueError("Titel-IDs sind nicht eindeutig.")
    plan, rest = list(tracks), []
    if opts.missing == "end":
        plan = [t for t in tracks if t.key and t.bpm]
        rest = [t for t in tracks if not (t.key and t.bpm)]
    n = len(plan)
    pos_of = {t.id: i for i, t in enumerate(plan)}
    fixed: dict[int, int] = {}
    for p, tid in sorted(opts.locks.items()):
        if tid in pos_of and 0 <= p < n:
            fixed[p] = pos_of[tid]
    if opts.start in pos_of and 0 not in fixed:
        fixed[0] = pos_of[opts.start]
    if opts.end in pos_of and n - 1 not in fixed and pos_of[opts.end] not in fixed.values():
        fixed[n - 1] = pos_of[opts.end]
    # doppelt gesperrte Titel nur einmal
    seen, clean = set(), {}
    for p, t in sorted(fixed.items()):
        if t not in seen:
            seen.add(t)
            clean[p] = t
    fixed = clean
    free = [i for i in range(n) if i not in fixed.values()]

    before = evaluate(tracks, opts)
    if n == 0:
        return {"order": ids, "before": before, "after": before, "method": "none",
                "rest": [t.id for t in rest], "ms": 0}
    m = _Model(plan, opts)
    if len(free) <= opts.exact_max:
        best, method = _held_karp(m, free, fixed), "exact"
    else:
        method = "heuristic"
        deadline = t0 + max(0.2, opts.time_limit)
        movable = [p not in fixed for p in range(n)]
        starts: list[int | None] = [None] if 0 in fixed else free[:]
        # Startreihenfolge: vielversprechende zuerst, damit auch bei knapper Zeit etwas Gutes da ist
        starts = sorted(starts, key=lambda t: m.P[t][0] if t is not None else 0)
        best, bc = None, float("inf")
        for k, s in enumerate(starts):
            if k and time.monotonic() >= deadline:
                break
            o = _improve(m, _greedy(m, free, fixed, s), movable, deadline)
            c = m.cost(o)
            if c < bc:
                best, bc = o, c
        original = list(range(n))
        if all(original[p] == t for p, t in fixed.items()):
            o = _improve(m, original, movable, deadline + 0.5)
            if m.cost(o) < bc:
                best = o
    ordered = [plan[i] for i in best] + rest
    return {
        "order": [t.id for t in ordered],
        "before": before,
        "after": evaluate(ordered, opts),
        "method": method,
        "rest": [t.id for t in rest],
        "ms": int((time.monotonic() - t0) * 1000),
    }


# ---------------------------------------------------------------- aus Dateien

def track_from_file(f, tid=None) -> Track:
    """Track aus einer geladenen MP3File (TKEY, TBPM, TXXX:ENERGY, Länge)."""
    import features

    def text(k):
        it = f.get(k) if hasattr(f, "get") else None
        return it.text.strip() if it is not None and getattr(it, "kind", "") not in ("picture", "raw") else ""

    bpm = None
    try:
        bpm = float(text("TBPM").replace(",", ".")) or None
    except ValueError:
        pass
    title = text("TIT2")
    artist = text("TPE1")
    dur = getattr(f, "duration", None)
    return Track(
        id=tid if tid is not None else getattr(f, "path", id(f)),
        key=keys.parse_key(text("TKEY")),
        bpm=bpm,
        energy=features.number(features.get(f, "ENERGY")),
        title=f"{artist} – {title}" if artist and title else title or artist,
        duration=dur() if callable(dur) else dur,
    )
