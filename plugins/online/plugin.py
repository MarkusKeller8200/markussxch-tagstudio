"""Online-Metadaten (4.1.0, #6–#8; seit 4.6 #204 als gemeinsame Suche über die Dienst-Plugins).

Die Dienste selbst sind eigene Plugins: MusicBrainz (+ AcoustID), Discogs, Deezer, iTunes und Last.fm. Dieses Plugin
fragt die eingeschalteten nacheinander ab und legt alle Änderungen als Vorschläge vor (Vorschau mit Häkchen,
Rückgängig). Standard ist „nur leere Felder füllen“. Je Feld ist nur der Wert der ersten Quelle (Reihenfolge
MusicBrainz → Discogs → SonoVault → Deezer → iTunes) vorausgewählt, weitere erscheinen als Alternative.
Ein Treffer kann „allowed_fields“ mitbringen (z. B. SonoVault: nur die laut Nutzungsbedingungen erlaubten Felder) und
„compare“ (BPM/Tonart nur zum Vergleich in der Notiz, nie als Vorschlag).

Schlüssel liegen verschlüsselt im jeweiligen Dienst-Plugin (Discogs, Last.fm, AcoustID – „Schlüssel …“ dort).
Nur Standardbibliothek.
"""
import os
import re

import onlinematch as om
import servicekit as sk
from onlinematch import HttpError, MAYBE, SURE

# Quelle (Optionsschlüssel wie bis 4.5, damit gemerkte Einstellungen gelten) → Dienst-Plugin, in Vorrang-Reihenfolge
SOURCES = [("mb", "musicbrainz", "MusicBrainz (frei)"), ("discogs", "discogs", "Discogs (eigener Token nötig)"),
           ("sonovault", "sonovault", "SonoVault (eigener Schlüssel nötig, Free: 1000 Anfragen im Monat)"),   # #254, SV4
           ("deezer", "deezer", "Deezer (frei)"), ("spotify", "spotify", "Spotify (eigene Spotify-App und Anmeldung nötig)"),
           ("itunes", "itunes", "iTunes (frei, langsam: ca. 20 Abfragen pro Minute)"),
           ("soundcloud", "soundcloud", "SoundCloud (eigene SoundCloud-App und Anmeldung nötig)")]
EXTRA = [("acoustid", "acoustid"), ("lastfm", "lastfm")]
SOURCE_NAME = {"mb": "MusicBrainz", "discogs": "Discogs", "sonovault": "SonoVault", "deezer": "Deezer", "itunes": "iTunes", "lastfm": "Last.fm",
               "spotify": "Spotify", "soundcloud": "SoundCloud",
               "acoustid": "AcoustID"}
DEFAULT_ON = {"mb": True, "deezer": True}


def _have(ctx, pid) -> bool:
    return ctx.service(pid) is not None


def actions(ctx):
    """Quellen nur für eingeschaltete, bereite Dienst-Plugins; die übrigen werden als Hinweis genannt."""
    opts = [{"type": "info", "label": "Quellen (Reihenfolge = Vorrang bei gleichen Feldern)"}]
    off = []
    for sid, pid, label in SOURCES:
        if _have(ctx, pid):
            opts.append({"key": sid, "type": "check", "label": label, "default": DEFAULT_ON.get(sid, False)})
            if sid == "mb" and _have(ctx, "acoustid"):
                opts.append({"key": "acoustid", "type": "check", "default": False, "show_if": {"mb": True},
                             "label": "… dazu AcoustID-Fingerabdruck für Titel ohne brauchbare Tags (Schlüssel + fpcalc im Plugin AcoustID)"})
            if sid == "itunes":
                opts.append({"key": "itunes_country", "type": "text", "label": "iTunes-Land (z. B. CH, DE, US)", "default": "CH",
                             "show_if": {"itunes": True}})
        else:
            off.append(SOURCE_NAME[sid])
    if _have(ctx, "lastfm"):
        opts.append({"key": "lastfm", "type": "check", "default": False,
                     "label": "Last.fm-Tags als Vorschlag (eigener Schlüssel im Plugin Last.fm, nie vorausgewählt)"})
    else:
        off.append("Last.fm")
    if off:
        opts.append({"type": "info", "label": f"Nicht verfügbar (Plugin ausgeschaltet): {', '.join(off)} – unter Plugins einschalten."})
    opts += [
        {"key": "mode", "type": "select", "label": "Vorhandene Werte",
         "choices": [["empty", "Nur leere Felder füllen (ergänzen)"], ["overwrite", "Überschreiben (Vorschau zeigt alt → neu)"]],
         "default": "empty"},
        {"key": "album", "type": "check", "label": "Album", "default": True},
        {"key": "date", "type": "select", "label": "Erscheinungsdatum",
         "choices": [["year", "Nur Jahr"], ["full", "Volles Datum (JJJJ-MM-TT)"], ["no", "Nicht übernehmen"]], "default": "year"},
        {"key": "label", "type": "check", "label": "Label (TPUB) und Katalognummer", "default": True},
        {"key": "isrc", "type": "check", "label": "ISRC", "default": True},
        {"key": "genre", "type": "check", "label": "Genre (Discogs: Stil, sonst Genre)", "default": True},
        {"key": "bpm", "type": "check", "label": "BPM (nur Deezer, wenn vorhanden)", "default": False},
        {"key": "track", "type": "check", "label": "Spur- und CD-Nummer", "default": False},
        {"key": "names", "type": "check", "label": "Titel und Künstler übernehmen", "default": False},
        {"key": "cover", "type": "select", "label": "Cover",
         "choices": [["missing", "Nur wenn keins vorhanden"], ["replace", "Ersetzen"], ["no", "Nicht übernehmen"]], "default": "missing"},
        {"key": "ids", "type": "check", "label": "IDs speichern (MusicBrainz, Deezer, iTunes, Discogs)", "default": True},
        {"key": "own", "type": "check", "default": False,
         "label": "Zusätzlich eigene Felder der Quelle mit Herkunft schreiben (SonoVault: TXXX:SONOVAULT_*, Spotify: TXXX:SPOTIFY_*)"},
    ]
    return [
        {"id": "fetch", "label": "Online-Metadaten holen …", "where": "tagger", "run_label": "Suchen",
         "description": "Sucht die markierten Titel bei den gewählten Diensten und schlägt Ergänzungen vor. Du bestätigst danach jede Änderung.",
         "options": opts},
        {"id": "test", "label": "Verbindungen testen", "where": "page", "run_label": "Testen", "needs_selection": False,
         "description": "Prüft alle eingeschalteten Dienste und ihre Schlüssel.", "options": []},
    ]


def _field_values(c, opts) -> list:
    """(Schlüssel, Wert, Beschriftung, gewünscht) für einen Treffer."""
    out = []
    names = bool(opts.get("names"))
    title = c.get("title", "")
    if c.get("mix"):
        title = f"{title} ({c['mix']})"
    out.append(("TIT2", title, "Titel", names))
    out.append(("TPE1", ", ".join(a for a in c.get("artists") or [] if a), "Künstler", names))
    out.append(("TALB", c.get("album", ""), "Album", opts.get("album")))
    date, dmode = c.get("date") or "", opts.get("date", "year")
    if dmode == "full" and re.match(r"\d{4}-\d{2}-\d{2}", date):
        out.append(("TDRC", date[:10], "Datum", True))
    elif date[:4].isdigit():
        out.append(("TDRC", date[:4], "Jahr", dmode != "no"))
    out.append(("TPUB", c.get("label", ""), "Label", opts.get("label")))
    out.append(("TXXX:CATALOGNUMBER", c.get("catno", ""), "Katalognummer", opts.get("label")))
    out.append(("TSRC", c.get("isrc", ""), "ISRC", opts.get("isrc")))
    out.append(("TCON", c.get("genre", ""), "Genre", opts.get("genre")))
    if c.get("bpm"):
        out.append(("TBPM", str(int(round(float(c["bpm"])))), "BPM", opts.get("bpm")))
    out.append(("TRCK", c.get("track", ""), "Spur", opts.get("track")))
    out.append(("TPOS", c.get("disc", ""), "CD", opts.get("track")))
    for k, v in (c.get("ids") or {}).items():
        out.append((k, v, k.split(":", 1)[1], opts.get("ids")))
    allowed = c.get("allowed_fields")
    if allowed is not None:                                  # #254: Nutzungsbedingungen der Quelle
        out = [x for x in out if x[0] in allowed]
    return out


def compare_note(f, c) -> str:
    """#254: BPM/Tonart einer Quelle nur als Vergleich mit den Werten der Datei (wie OpenKeyScan)."""
    cmp = c.get("compare") or {}
    if not cmp:
        return ""
    import keys
    import keyscan
    parts = []
    code = keys.parse_key(str(cmp.get("key") or "")) if cmp.get("key") else None
    if code:
        txt = f"Tonart {keys.format_key(code, 'camelot')}" + (f" ({cmp['sources']} Quellen)" if (cmp.get("sources") or 0) > 1 else "")
        known = dict(keyscan.known_keys(f))
        if known.get("TKEY"):
            txt += f" – TKEY {keyscan.REL_TEXT[keyscan.relation(code, known['TKEY'])]}"
        parts.append(txt)
    try:
        bpm = float(cmp.get("bpm") or 0)
    except (TypeError, ValueError):
        bpm = 0
    if bpm:
        txt = f"{bpm:g} BPM"
        try:
            cur = float(f.text("TBPM").replace(",", ".") or 0)
        except ValueError:
            cur = 0
        if cur:
            txt += " – TBPM " + ("gleich" if abs(cur - bpm) < 0.6 else f"{cur:g} (abweichend)")
        parts.append(txt)
    return f" · Vergleich {cmp.get('source', '')}: " + ", ".join(parts) if parts else ""


def _same(key, old, new):
    o, n = (old or "").strip(), (new or "").strip()
    if o.lower() == n.lower():
        return True
    if key == "TDRC":
        return len(n) == 4 and o[:4] == n
    if key in ("TPE1", "TIT2", "TALB", "TPUB"):
        return om.norm(o) == om.norm(n)
    if key in ("TRCK", "TPOS"):
        return o.split("/")[0].lstrip("0") == n.split("/")[0].lstrip("0") and ("/" not in n or o == n)
    return False


def propose_file(ctx, cl, f, hits, opts, group, stats, auth=None):
    """hits: [(Quelle, Kandidat, Treffer-Score)] in Vorrang-Reihenfolge. Je Feld nur der erste Wert vorausgewählt."""
    empty_only = opts.get("mode", "empty") == "empty"
    taken = set()
    for src, c, s in hits:
        sure = s >= SURE
        note = f"{SOURCE_NAME[src]}: {', '.join(c.get('artists') or [])} – {c.get('title', '')}" + \
               (f" ({c['mix']})" if c.get("mix") else "") + f" · {round(s * 100)} %" + ("" if sure else " · unsicher") + \
            compare_note(f, c)
        lk = {"link": c.get("url") or "", "link_label": SOURCE_NAME[src]}      # #144: Treffer auf der Plattform
        for key, val, label, wanted in _field_values(c, opts):
            val = (val or "").strip()
            if not val:
                continue
            cur = f.text(key).strip()
            lab = f"{label} ({SOURCE_NAME[src]})"
            if cur == val:
                if key not in taken:
                    stats["same"] += 1
                    ctx.propose(f, key, val, lab, note=note, checked=False, group=group, **lk, hint="gleich", show_same=True)
                taken.add(key)
                continue
            first = key not in taken
            taken.add(key)
            if not first:
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, **lk, hint="Alternative – bei Bedarf anhaken")
            elif not wanted:
                stats["off"] += 1
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, **lk, hint="in den Optionen abgewählt")
            elif cur and _same(key, cur, val):
                stats["same"] += 1
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, **lk, hint="gleicher Wert, andere Schreibweise")
            elif cur and empty_only:
                stats["filled"] += 1
                ctx.propose(f, key, val, lab, note=note, checked=False, group=group, **lk, hint="schon gefüllt – nur ergänzen")
            else:
                ctx.propose(f, key, val, lab, note=note, checked=sure, group=group, **lk)
    # #383: eigene Felder einer Quelle (z. B. TXXX:SONOVAULT_*) – Kopie mit Herkunft, nur mit Option „own“
    if opts.get("own"):
        for src, c, s in hits:
            own = [tuple(x) + (False,) * (4 - len(x)) for x in c.get("own_fields") or []]
            for key, val, label, stamp in own:
                if stamp and all(f.text(k).strip() == v for k, v, _l, st in own if not st):
                    continue                         # nur der Stempel (z. B. Abrufdatum) wäre neu
                if f.text(key).strip() == val:
                    continue
                ctx.propose(f, key, val, f"{label} ({SOURCE_NAME[src]})", note=f"{SOURCE_NAME[src]}: eigenes Feld",
                            checked=s >= SURE, group=group,
                            hint=c.get("own_hint") or f"eigenes Feld mit Herkunft „{SOURCE_NAME[src]}“")   # #385
    # Cover: aus der ersten Quelle, die eins hat
    cov = opts.get("cover", "missing")
    has = f.get("APIC:3") is not None
    for src, c, s in hits:
        url = c.get("cover")
        if not url:
            continue
        if cov == "no" or (cov == "missing" and has):
            ctx.propose(f, "APIC:3", f"Cover von {SOURCE_NAME[src]} verfügbar", "Cover", checked=False, kind="cover",
                        data=None, group=group, hint="Datei hat schon ein Cover – Option Cover → „Ersetzen“ lädt es" if has
                        else "Option Cover → „Nur wenn keins vorhanden“ lädt es")
            break
        try:
            data = cl.raw(url, (auth or {}).get(src))
        except HttpError as ex:
            ctx.log(f"Cover ({SOURCE_NAME[src]}): {ex}")
            continue
        if data[:3] in (b"\xff\xd8\xff", b"\x89PN"):
            ctx.propose(f, "APIC:3", f"Cover von {SOURCE_NAME[src]}", "Cover", checked=s >= SURE and not has, kind="cover",
                        data=data, group=group, hint="ersetzt vorhandenes Cover" if has else "")
            break


# =========================================================================== Aktionen
def _services(ctx):
    """[(Quelle, Plugin-ID, Modul, Context)] der eingeschalteten Dienste in Vorrang-Reihenfolge."""
    out = []
    for sid, pid in [(a, b) for a, b, _l in SOURCES] + EXTRA:
        mod = ctx.service(pid)
        if mod is not None:
            out.append((sid, pid, mod, ctx.service_ctx(pid)))
    return out


def status(ctx):
    on, keyless = [], []
    for sid, _pid, mod, sctx in _services(ctx):
        on.append(SOURCE_NAME[sid])
        ready = getattr(mod, "ready", None)
        if callable(ready) and not ready(sctx)[0]:
            keyless.append(SOURCE_NAME[sid])
    return ("Quellen: " + (", ".join(on) if on else "keine – Dienst-Plugins einschalten")) + \
        (f" · ohne Schlüssel/fpcalc: {', '.join(keyless)}" if keyless else "")


def run(action, ctx, files, opts):
    cl = sk.client(ctx)
    if action == "test":
        lines, ok = [], 0
        svcs = [x for x in _services(ctx) if callable(getattr(x[2], "check", None))]
        for sid, _pid, mod, sctx in svcs:
            try:
                good, why = mod.check(sctx, cl)
            except HttpError as ex:
                good, why = False, str(ex)
            lines.append(f"{SOURCE_NAME[sid]}: {why}")
            ok += bool(good)
        for ln in lines:
            ctx.log(ln)
        return {"message": f"{ok} von {len(svcs)} Diensten in Ordnung. " + " · ".join(lines)}
    if action != "fetch":
        raise ValueError(f"Unbekannte Aktion: {action}")

    svc = {sid: (mod, sctx) for sid, _pid, mod, sctx in _services(ctx)}
    srcs = []
    for sid, _pid, _l in SOURCES:
        if not opts.get(sid):
            continue
        if sid not in svc:
            ctx.log(f"{SOURCE_NAME[sid]} übersprungen: Plugin ausgeschaltet.")
            continue
        mod, sctx = svc[sid]
        ready = getattr(mod, "ready", None)
        ok, why = ready(sctx) if callable(ready) else (True, "")
        if not ok:
            ctx.log(f"{SOURCE_NAME[sid]} übersprungen: {why}.")
            continue
        srcs.append(sid)
    use_lastfm = bool(opts.get("lastfm") and "lastfm" in svc and svc["lastfm"][0].ready(svc["lastfm"][1])[0])
    if opts.get("lastfm") and not use_lastfm:
        ctx.log("Last.fm übersprungen: " + ("Plugin ausgeschaltet." if "lastfm" not in svc else "kein Schlüssel gespeichert."))
    use_fp = bool(opts.get("mb") and opts.get("acoustid") and "mb" in srcs)
    if use_fp:
        if "acoustid" not in svc:
            ctx.log("AcoustID übersprungen: Plugin ausgeschaltet.")
            use_fp = False
        else:
            ok, why = svc["acoustid"][0].ready(svc["acoustid"][1])
            if not ok:
                ctx.log(f"AcoustID übersprungen: {why}.")
                use_fp = False
    if not srcs and not use_lastfm:
        raise ValueError("Keine Quelle gewählt (oder für die gewählten fehlt der Schlüssel bzw. das Plugin ist ausgeschaltet).")
    found = unsure = missing = 0
    stats = {"same": 0, "filled": 0, "off": 0}
    for i, f in enumerate(files):
        name = os.path.basename(f.path)
        ctx.progress(i, len(files), f"Suche {name}")
        info = om.file_info(f)
        hits = []
        for src in srcs:
            mod, sctx = svc[src]
            try:
                cands = mod.candidates(sctx, cl, info, opts) if info["title"] else []
                c, s = om.best(info, cands)
                if src == "mb" and use_fp and (not c or s < MAYBE):
                    fpc = svc["acoustid"][0].fp_candidates(svc["acoustid"][1], cl, f, mod)
                    if fpc:
                        fc = max(fpc, key=lambda x: x.get("fp_score", 0))
                        c, s = fc, max(om.score(info, fc), min(1.0, fc.get("fp_score", 0)))
                if c and s >= MAYBE:
                    c = mod.details(sctx, cl, c)
                    if src == "deezer":
                        s = max(s, om.score(info, c))
            except HttpError as ex:
                if ex.status in (0, 429):
                    raise RuntimeError(str(ex)) from ex
                ctx.log(f"{name} · {SOURCE_NAME[src]}: {ex}")
                continue
            if c and s >= MAYBE:
                hits.append((src, c, s))
                if c.get("allowed_fields") is not None:       # #254: keine Werte dieser Quelle ins Protokoll (Datei)
                    ctx.log(f"{name} · {SOURCE_NAME[src]}: gefunden ({round(s * 100)} %)")
                else:
                    ctx.log(f"{name} · {SOURCE_NAME[src]}: {', '.join(c.get('artists') or [])} – {c.get('title', '')} ({round(s * 100)} %)")
            else:
                ctx.log(f"{name} · {SOURCE_NAME[src]}: nicht gefunden" + (f" (bester Kandidat {round(s * 100)} %)" if c else ""))
        if use_lastfm and info["title"]:
            try:
                tags = svc["lastfm"][0].tags(svc["lastfm"][1], cl, info)
            except HttpError as ex:
                tags = []
                ctx.log(f"{name} · Last.fm: {ex}")
            if tags:
                ctx.propose(f, "TXXX:LASTFM_TAGS", "; ".join(tags), "Last.fm-Tags", note="Last.fm: Vorschlag", checked=False,
                            group=name, hint="Vorschlag – nie vorausgewählt")
                ctx.propose(f, "TCON", tags[0], "Genre (Last.fm)", note="Last.fm: Vorschlag", checked=False,
                            group=name, hint="Vorschlag aus den Last.fm-Tags")
        if hits:
            best_s = max(s for _src, _c, s in hits)
            found += best_s >= SURE
            unsure += best_s < SURE
            auth = {sid: mod.cover_headers(sctx) for sid, (mod, sctx) in svc.items() if callable(getattr(mod, "cover_headers", None))}
            propose_file(ctx, cl, f, hits, opts, name, stats, auth=auth)
        else:
            missing += 1
    ctx.progress(len(files), len(files), "fertig")
    msg = f"{found} sicher gefunden" + (f", {unsure} unsicher (nicht vorausgewählt)" if unsure else "") + \
          (f", {missing} nicht gefunden" if missing else "")
    if not ctx.proposals:
        return {"message": f"{msg}. Keine Felder zum Ergänzen."}
    n = sum(1 for p in ctx.proposals if p["checked"])
    m = sum(1 for p in ctx.proposals if not p["same"])
    extra = ""
    if stats["same"]:
        extra += f" {stats['same']} Feld(er) stimmen bereits (grau)."
    if stats["filled"]:
        extra += f" {stats['filled']} gefüllte Feld(er) mit anderem Wert gelistet, nicht angehakt (nur ergänzen)."
    return {"message": f"{msg}. {m} mögliche Änderung(en), {n} vorausgewählt." + extra}
