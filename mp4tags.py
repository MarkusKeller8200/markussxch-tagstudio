"""MP4 / M4A (AAC, ALAC): iTunes-Atome lesen und schreiben (#265).

Tags stehen in `moov/udta/meta/ilst`: feste Atome (`©nam`, `trkn`, `covr` …) und freie Felder
`----` (mean `com.apple.iTunes`, name `NAME`). Unbekannte Atome und freie Felder anderer Programme (z. B. Serato
`com.serato.dj`) werden byte-genau übernommen.

Schreiben: `ilst` wird neu gebaut und `moov` mit den neuen Grössen neu zusammengesetzt. Liegt `moov` **vor** den
Audiodaten (`mdat`), verschieben sich diese – dann wird ein direkt folgendes `free`-Atom verkleinert/vergrössert oder,
wenn das nicht reicht, werden die Chunk-Offsets aller Spuren (`stco`/`co64`) korrigiert. Immer über eine temporäre
Datei; vor dem Ersetzen wird geprüft, dass `mdat` byte-gleich ist und die Offsets auf dieselben Audiodaten zeigen.
Nur lesen: fragmentierte Dateien (`moof`) und DRM-geschützte (`drms`).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile

from id3tags import Item, Cover, MV, GENRES
from mapfile import FormatError, MappedFile, channels_text

EXTS = (".m4a", ".mp4", ".m4b")
CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"udta", b"edts", b"dinf"}
ITUNES = "com.apple.iTunes"

# TagStudioSX-Schlüssel → festes Atom (Text, UTF-8)
MP4_TEXT = {
    "TIT2": b"\xa9nam", "TPE1": b"\xa9ART", "TALB": b"\xa9alb", "TPE2": b"aART", "TCOM": b"\xa9wrt",
    "TCON": b"\xa9gen", "TDRC": b"\xa9day", "TCOP": b"cprt", "COMM:": b"\xa9cmt", "USLT:": b"\xa9lyr",
    "TIT1": b"\xa9wrk", "GRP1": b"\xa9grp", "TENC": b"\xa9enc", "TSSE": b"\xa9too", "TSOT": b"sonm",
    "TSOP": b"soar", "TSOA": b"soal", "TSO2": b"soaa", "TSOC": b"soco", "MVNM": b"\xa9mvn",
}
# TagStudioSX-Schlüssel → freies Feld ----:com.apple.iTunes:NAME
MP4_FREE = {"TEXT": "LYRICIST", "TPE3": "CONDUCTOR", "TPE4": "REMIXER", "TDOR": "ORIGINALDATE",
            "TDRL": "RELEASEDATE", "TSST": "DISCSUBTITLE", "TKEY": "initialkey", "TSRC": "ISRC", "TPUB": "LABEL",
            "TIT3": "SUBTITLE", "TMOO": "MOOD", "TMED": "MEDIA", "TLAN": "LANGUAGE"}
_TEXT_READ = {v: k for k, v in MP4_TEXT.items()}
_FREE_READ = {v.upper(): k for k, v in MP4_FREE.items()}


# --------------------------------------------------------------------------- Atome
def atoms(data: bytes, start: int = 0, end: int | None = None):
    """Atome in data[start:end] → [(Typ, Anfang, Kopflänge, Ende)]."""
    end = len(data) if end is None else end
    out, p = [], start
    while p + 8 <= end:
        size, typ = struct.unpack_from(">I4s", data, p)
        hl = 8
        if size == 1:
            if p + 16 > end:
                raise FormatError("Atom abgeschnitten")
            size, hl = struct.unpack_from(">Q", data, p + 8)[0], 16
        elif size == 0:
            size = end - p
        if size < hl or p + size > end:
            raise FormatError(f"Atom {typ!r} ungültig")
        out.append((typ, p, hl, p + size))
        p += size
    return out


def top_atoms(path: str):
    """Oberste Ebene ohne mdat einzulesen → [(Typ, Anfang, Kopflänge, Ende)]."""
    size = os.path.getsize(path)
    out, p = [], 0
    with open(path, "rb") as f:
        while p + 8 <= size:
            f.seek(p)
            h = f.read(16)
            sz, typ = struct.unpack_from(">I4s", h, 0)
            hl = 8
            if sz == 1:
                sz, hl = struct.unpack_from(">Q", h, 8)[0], 16
            elif sz == 0:
                sz = size - p
            if sz < hl or p + sz > size:
                raise FormatError(f"Atom {typ!r} ungültig")
            out.append((typ, p, hl, p + sz))
            p += sz
    if not any(t == b"moov" for t, *_ in out):
        raise FormatError("kein moov-Atom")
    return out


def _box(typ: bytes, payload: bytes) -> bytes:
    n = 8 + len(payload)
    if n > 0xFFFFFFFF:
        raise FormatError("Atom zu gross")
    return struct.pack(">I", n) + typ + payload


def _meta_children_start(data: bytes, a) -> int:
    """`meta` ist meist eine FullBox (4 Byte Version/Flags), bei QuickTime aber nicht."""
    typ, s, hl, e = a
    p = s + hl
    if e - p >= 8 and data[p + 4:p + 8] in (b"hdlr", b"ilst", b"free", b"keys"):
        return p
    return p + 4


def find(data: bytes, path: list[bytes], start=0, end=None):
    """Atom auf dem Pfad (z. B. [b'udta', b'meta', b'ilst']) innerhalb data[start:end] oder None."""
    lvl = atoms(data, start, end)
    for a in lvl:
        if a[0] == path[0]:
            if len(path) == 1:
                return a
            cs = _meta_children_start(data, a) if a[0] == b"meta" else a[1] + a[2]
            return find(data, path[1:], cs, a[3])
    return None


def _all(data: bytes, typ: bytes, start=0, end=None, out=None):
    """Alle Atome eines Typs unterhalb von Containern (für stco/co64, stsd …)."""
    out = [] if out is None else out
    for a in atoms(data, start, end):
        if a[0] == typ:
            out.append(a)
        if a[0] in CONTAINERS:
            _all(data, typ, a[1] + a[2], a[3], out)
    return out


# --------------------------------------------------------------------------- ilst ↔ Einträge
def parse_ilst(data: bytes, a) -> list[dict]:
    """Einträge der ilst: {"atom", "mean", "name", "values": [(Typ, Wert-Bytes)], "raw"}."""
    out = []
    for typ, s, hl, e in atoms(data, a[1] + a[2], a[3]):
        ent = {"atom": typ, "mean": "", "name": "", "values": [], "raw": data[s:e]}
        for ct, cs, chl, ce in atoms(data, s + hl, e):
            body = data[cs + chl:ce]
            if ct == b"mean":
                ent["mean"] = body[4:].decode("utf-8", "replace")
            elif ct == b"name":
                ent["name"] = body[4:].decode("utf-8", "replace")
            elif ct == b"data" and len(body) >= 8:
                ent["values"].append((int.from_bytes(body[1:4], "big"), body[8:]))
        out.append(ent)
    return out


def _data(kind: int, value: bytes) -> bytes:
    return _box(b"data", struct.pack(">I", kind & 0xFFFFFF) + b"\x00\x00\x00\x00" + value)


def _free_atom(name: str, values: list[str]) -> bytes:
    body = (_box(b"mean", b"\x00\x00\x00\x00" + ITUNES.encode()) + _box(b"name", b"\x00\x00\x00\x00" + name.encode())
            + b"".join(_data(1, v.encode("utf-8")) for v in values))
    return _box(b"----", body)


def _int_pair(atom: bytes, text: str) -> bytes:
    n, _, t = text.partition("/")
    n, t = int(n.strip() or 0), int(t.strip() or 0)
    body = struct.pack(">HHHH", 0, n, t, 0) if atom == b"trkn" else struct.pack(">HHH", 0, n, t)
    return _box(atom, _data(0, body))


class Mp4File(MappedFile):
    FORMAT = "M4A"

    def format_name(self) -> str:
        return f"M4A ({self.codec})" if getattr(self, "codec", "") in ("AAC", "ALAC") else "MP4"

    def _parse(self) -> bytes:
        self.container = "m4a"
        top = top_atoms(self.path)
        self._top = top
        mv = next(a for a in top if a[0] == b"moov")
        with open(self.path, "rb") as f:
            f.seek(mv[1])
            moov = f.read(mv[3] - mv[1])
        self._moov = moov
        if any(t == b"moof" for t, *_ in top):
            self.read_only = True
        hl = mv[2]
        # Dauer (mvhd), Codec und Abtastrate (stsd)
        mvhd = find(moov, [b"mvhd"], hl)
        if mvhd:
            b = moov[mvhd[1] + mvhd[2]:mvhd[3]]
            if b[0] == 1:
                ts, dur = struct.unpack_from(">IQ", b, 20)
            else:
                ts, dur = struct.unpack_from(">II", b, 12)
            if ts:
                self.duration = dur / ts
        for sd in _all(moov, b"stsd", hl):
            b = moov[sd[1] + sd[2]:sd[3]]
            if len(b) >= 16 + 28:
                fmt = b[12:16]
                if fmt in (b"mp4a", b"alac", b"drms"):
                    e = b[16:]
                    ch, bits = struct.unpack_from(">HH", e, 16)
                    rate = struct.unpack_from(">I", e, 24)[0] >> 16
                    self.codec = {b"mp4a": "AAC", b"alac": "ALAC", b"drms": "AAC (DRM)"}[fmt]
                    self.channels, self.samplerate = channels_text(ch), rate
                    self.bits = bits if fmt == b"alac" else 0
                    if fmt == b"drms":
                        self.read_only = True
                    break
        mdat = sum(a[3] - a[1] for a in top if a[0] == b"mdat")
        if self.duration:
            self.bitrate = round(mdat * 8 / self.duration / 1000)
        ilst = find(moov, [b"udta", b"meta", b"ilst"], hl)
        self._native = parse_ilst(moov, ilst) if ilst else []
        raw = moov[ilst[1]:ilst[3]] if ilst else b""
        self.tag_desc = "iTunes-Atome" if ilst else "kein Tag"
        if self.read_only:
            self.tag_desc += " (nur lesen)"
        self._raw = raw
        return raw

    def _to_items(self):
        for ent in self._native:
            key, vals = self._ent_key(ent), ent["values"]
            if key is None or not vals:
                continue
            a = ent["atom"]
            self._srcname.setdefault(key, ent)
            if a == b"covr":
                for kind, v in vals:
                    mime = "image/png" if kind == 14 or v[:4] == b"\x89PNG" else "image/jpeg"
                    it = Item.new_cover(Cover(v, mime, 3))
                    key, n = "APIC:3", 2
                    while key in self.items:
                        key, n = f"APIC:3#{n}", n + 1
                    it.key = key
                    self.items[key] = it
                continue
            if a in (b"trkn", b"disk"):
                v = vals[0][1]
                if len(v) >= 6:
                    n, t = struct.unpack_from(">HH", v, 2)
                    text = f"{n}/{t}" if t else str(n) if n else ""
                else:
                    text = ""
            elif a == b"tmpo":
                v = vals[0][1]
                text = str(int.from_bytes(v[:2], "big")) if len(v) >= 2 else ""
            elif a == b"cpil":
                text = "1" if vals[0][1][:1] == b"\x01" else "0"
            elif a == b"gnre":
                v = vals[0][1]
                g = int.from_bytes(v[:2], "big") - 1 if len(v) >= 2 else -1
                text = GENRES[g] if 0 <= g < len(GENRES) else ""
            elif a == b"\xa9mvi":
                v = vals[0][1]
                text = str(int.from_bytes(v, "big")) if v else ""
            else:
                text = MV.join(v.decode("utf-8", "replace") for k, v in vals if k == 1 and v)
            if text.strip() and key not in self.items:
                self.items[key] = Item.new_text(key, text)

    @staticmethod
    def _ent_key(ent):
        a = ent["atom"]
        if a == b"covr":
            return "APIC:3"
        if a == b"trkn":
            return "TRCK"
        if a == b"disk":
            return "TPOS"
        if a == b"tmpo":
            return "TBPM"
        if a == b"cpil":
            return "TCMP"
        if a == b"gnre":
            return "TCON"
        if a == b"\xa9mvi":
            return "MVIN"
        if a in _TEXT_READ:
            return _TEXT_READ[a]
        if a == b"----" and ent["mean"] == ITUNES and ent["name"]:
            return _FREE_READ.get(ent["name"].upper()) or f"TXXX:{ent['name']}"
        return None                                              # unbekannt: byte-genau übernehmen

    def _item_atom(self, key: str, it) -> bytes | None:
        base = key.split("#")[0]
        src = self._srcname.get(base)
        if base == "TRCK":
            return _int_pair(b"trkn", it.text)
        if base == "TPOS":
            return _int_pair(b"disk", it.text)
        if base == "TBPM":
            try:
                v = int(round(float(it.text.replace(",", ".").split(MV)[0])))
            except ValueError:
                return None
            return _box(b"tmpo", _data(21, struct.pack(">H", max(0, min(v, 65535)))))
        if base == "TCMP":
            return _box(b"cpil", _data(21, b"\x01" if it.text.strip() in ("1", "true") else b"\x00"))
        if base == "MVIN":
            try:
                return _box(b"\xa9mvi", _data(21, struct.pack(">H", int(it.text.split("/")[0]))))
            except ValueError:
                return None
        vals = [it.text] if base in ("COMM:", "USLT:") else [v for v in it.text.split(MV) if v.strip()]
        if base in MP4_TEXT:
            atom = MP4_TEXT[base]
            if base == "TCON" and src and src["atom"] == b"gnre":
                atom = b"\xa9gen"
            return _box(atom, b"".join(_data(1, v.encode("utf-8")) for v in vals))
        if base in MP4_FREE:
            return _free_atom(src["name"] if src else MP4_FREE[base], vals)
        if it.fid == "TXXX" and it.desc:
            return _free_atom(it.desc, vals)
        return None

    def _build_ilst(self) -> bytes:
        skipped, wanted = [], {}
        for key, it in self.items.items():
            if it.kind == "picture":
                continue
            if it.kind == "raw" or it.fid in ("COMM", "USLT") and it.desc:
                skipped.append(key)
                continue
            if key.split("#")[0] == "TXXX:MOOD" and "TMOO" in self.items:
                continue
            b = self._item_atom(key, it)
            if b is None:
                skipped.append(key)
                continue
            if key.split("#")[0] == "TBPM" and "." in it.text.replace(",", "."):
                skipped.append("TBPM (nur ganze Zahl)")
            wanted[key.split("#")[0]] = b
        covers = [it.cover for it in self.items.values() if it.kind == "picture" and it.cover is not None]
        cov = b""
        if covers:
            parts = [_data(14 if c.mime == "image/png" else 13, c.data) for c in covers if c.mime in ("image/png", "image/jpeg")]
            skipped += [f"APIC ({c.mime})" for c in covers if c.mime not in ("image/png", "image/jpeg")]
            cov = _box(b"covr", b"".join(parts)) if parts else b""
        out, done = [], set()
        for ent in self._native:
            key = self._ent_key(ent)
            if key is None:
                out.append(ent["raw"])
                continue
            if key in done:
                continue
            done.add(key)
            if key == "APIC:3":
                if cov:
                    out.append(cov)
                    cov = b""
                continue
            if key in wanted:
                out.append(wanted.pop(key))
        out += list(wanted.values())
        if cov:
            out.append(cov)
        self.save_skipped = skipped
        return _box(b"ilst", b"".join(out))

    def _write(self):
        top = top_atoms(self.path)
        if [(t, s, e) for t, s, _h, e in top] != [(t, s, e) for t, s, _h, e in self._top]:
            raise FormatError("Datei wurde inzwischen verändert – bitte neu einlesen.")
        mv = next(a for a in top if a[0] == b"moov")
        moov = self._moov
        new_moov = _replace_ilst(moov, mv[2], self._build_ilst())
        delta = len(new_moov) - len(moov)
        idx = top.index(mv)
        after = [a for a in top[idx + 1:]]
        shift = any(a[0] == b"mdat" for a in after)
        pieces = []                                              # (Quelle, Anfang, Ende) bzw. Bytes
        free_fix = None
        if shift and delta and after and after[0][0] in (b"free", b"skip"):
            fsize = after[0][3] - after[0][1]
            if fsize - delta >= 8:
                free_fix = fsize - delta
            elif fsize - delta == 0:
                free_fix = 0
        if shift and delta and free_fix is None and delta < 0 and -delta >= 8:
            free_fix = -1                                        # neues free-Atom für die gewonnene Lücke
        if shift and delta and free_fix is None:
            new_moov = _shift_offsets(new_moov, mv[2], delta)
        folder = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(prefix=".tagstudio_mp4_", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "wb") as out, open(self.path, "rb") as src:
                for a in top:
                    if a is mv:
                        out.write(new_moov)
                        if free_fix == -1:
                            out.write(_box(b"free", b"\x00" * (-delta - 8)))
                        continue
                    if free_fix is not None and free_fix >= 0 and after and a is after[0]:
                        if free_fix:
                            out.write(_box(a[0], b"\x00" * (free_fix - 8)))
                        continue
                    src.seek(a[1])
                    left = a[3] - a[1]
                    while left:
                        b = src.read(min(left, 1 << 20))
                        if not b:
                            break
                        out.write(b)
                        left -= len(b)
            _verify(self.path, tmp)
            shutil.copymode(self.path, tmp)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise


def _rebuild(data: bytes, a, new_children: bytes) -> bytes:
    typ, s, hl, e = a
    head = data[s + 8:s + hl] if hl == 16 else b""
    pre = b""
    if typ == b"meta":
        cs = _meta_children_start(data, a)
        pre = data[s + hl:cs]
    payload = pre + new_children
    if hl == 16:
        return struct.pack(">I", 1) + typ + struct.pack(">Q", 16 + len(payload)) + payload
    return _box(typ, payload)


def _replace_child(data: bytes, a, path: list[bytes], new: bytes) -> bytes:
    """Container a neu zusammensetzen; path führt zum zu ersetzenden Kind (anlegen, wenn es fehlt)."""
    cs = _meta_children_start(data, a) if a[0] == b"meta" else a[1] + a[2]
    kids = atoms(data, cs, a[3])
    out, found = [], False
    for k in kids:
        if k[0] == path[0] and not found:
            found = True
            out.append(new if len(path) == 1 else _replace_child(data, k, path[1:], new))
        else:
            out.append(data[k[1]:k[3]])
    if not found:
        out.append(_create(path, new))
    return _rebuild(data, a, b"".join(out))


def _create(path, new):
    """Fehlende Container auf dem Pfad anlegen (udta → meta mit hdlr → ilst); path[-1] ist das neue Atom selbst."""
    if len(path) == 1:
        return new
    inner = _create(path[1:], new)
    if path[0] == b"meta":
        hdlr = _box(b"hdlr", b"\x00" * 8 + b"mdirappl" + b"\x00" * 9)
        return _box(b"meta", b"\x00\x00\x00\x00" + hdlr + inner)
    return _box(path[0], inner)


def _replace_ilst(moov: bytes, hl: int, ilst: bytes) -> bytes:
    root = (b"moov", 0, hl, len(moov))
    return _replace_child(moov, root, [b"udta", b"meta", b"ilst"], ilst)


def _shift_offsets(moov: bytes, hl: int, delta: int) -> bytes:
    """Alle stco/co64-Einträge um delta verschieben (Audio rutscht nach hinten/vorne)."""
    buf = bytearray(moov)
    for typ in (b"stco", b"co64"):
        for a in _all(moov, typ, hl):
            p = a[1] + a[2] + 4
            n = struct.unpack_from(">I", buf, p)[0]
            p += 4
            for i in range(n):
                if typ == b"stco":
                    v = struct.unpack_from(">I", buf, p + 4 * i)[0] + delta
                    if not 0 <= v <= 0xFFFFFFFF:
                        raise FormatError("Offsets passen nicht mehr in 32 Bit – nicht gespeichert")
                    struct.pack_into(">I", buf, p + 4 * i, v)
                else:
                    struct.pack_into(">Q", buf, p + 8 * i, struct.unpack_from(">Q", buf, p + 8 * i)[0] + delta)
    return bytes(buf)


def _offsets(path: str) -> list[int]:
    top = top_atoms(path)
    mv = next(a for a in top if a[0] == b"moov")
    with open(path, "rb") as f:
        f.seek(mv[1])
        moov = f.read(mv[3] - mv[1])
    out = []
    for typ, w in ((b"stco", 4), (b"co64", 8)):
        for a in _all(moov, typ, mv[2]):
            p = a[1] + a[2] + 4
            n = struct.unpack_from(">I", moov, p)[0]
            vals = [struct.unpack_from(">I" if w == 4 else ">Q", moov, p + 4 + w * i)[0] for i in range(n)]
            out += vals[:1] + vals[-1:] if vals else []
    return out


def _mdat_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for t, s, hl, e in top_atoms(path):
            if t == b"mdat":
                f.seek(s + hl)
                left = e - s - hl
                while left:
                    b = f.read(min(left, 1 << 20))
                    if not b:
                        break
                    h.update(b)
                    left -= len(b)
    return h.hexdigest()


def _verify(old: str, new: str):
    if _mdat_hash(old) != _mdat_hash(new):
        raise FormatError("Prüfung fehlgeschlagen: Audiodaten wären verändert worden – nicht gespeichert.")
    a, b = _offsets(old), _offsets(new)
    if len(a) != len(b):
        raise FormatError("Prüfung fehlgeschlagen: Spuren passen nicht – nicht gespeichert.")
    with open(old, "rb") as fo, open(new, "rb") as fn:
        for x, y in zip(a, b):
            fo.seek(x)
            fn.seek(y)
            if fo.read(32) != fn.read(32):
                raise FormatError("Prüfung fehlgeschlagen: Offsets zeigen nicht auf dieselben Audiodaten – nicht gespeichert.")


def tag_bytes(path: str) -> bytes:
    f = Mp4File.__new__(Mp4File)
    f.path = path
    f.load()
    return getattr(f, "_raw", b"")


def write_tag_bytes(path: str, tag: bytes) -> None:
    """Gesicherte ilst (b"" = keine) zurückschreiben."""
    f = Mp4File.__new__(Mp4File)
    f.path = path
    f.load()
    if f.read_only:
        raise FormatError("nur lesen")
    f._native = parse_ilst(tag, (b"ilst", 0, 8, len(tag))) if tag else []
    f.items, f._srcname = {}, {}
    f._to_items()
    f._write()
