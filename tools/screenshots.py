"""Bildschirmfotos der Oberfläche für Startseite, Webseite und Video (#373, #439).

    python tools/screenshots.py [HD-Ordner]
        → HD-Ordner (Standard: <Temp>/TagStudio-Screenshots): alle Motive hell und dunkel in 2560 × 1440,
          Ausschnitte (ausschnitte/), Titel- und Schlussbild fürs Video (video/) – nicht im Repository
        → docs/screenshots/<name>-light.png und -dark.png: die Motive der Startseite verkleinert auf 1600 × 900
        → docs/social-preview.png (Vorschaubild für GitHub, 1280 × 640)

Braucht Playwright (Chromium), ffmpeg und Pillow. Alles läuft mit einem frischen Benutzerordner und einer Beispiel-
Bibliothek mit erfundenen Titeln (keine privaten Daten, keine echten Künstler, keine Konten). Einkäufe, Treffer bei
Beatport und das Mix-Plugin werden nachgebildet; Cover sind erzeugte Farbverläufe.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "screenshots")
VIEW = {"width": 1600, "height": 900}          # Fenster wie bisher …
SCALE = 1.6                                     # … 1,6-fach gerendert → 2560 × 1440 (#439)
SITE = ("tagger", "discover", "ideas", "carts", "purchases", "prep", "compare", "djset", "mixes", "plugins")   # ins Repo
sys.path.insert(0, ROOT)

# Erfundene Titel: Künstler, Titel, Mix, BPM, Tonart (Camelot), Genre, Label, Jahr, Ton (Hz)
TRACKS = [
    ("Mara Lind", "Nordlicht", "Extended Mix", 124, "8A", "Melodic House", "Polarstern Records", 2026, 220),
    ("Ivo Berg", "Kaltes Glas", "Original Mix", 126, "9A", "Techno", "Graustufen", 2025, 247),
    ("Lea Sommer", "Wellenbrecher", "Club Mix", 122, "7A", "Deep House", "Küstenlicht", 2026, 262),
    ("Noah Feld", "Morgengrau", "Extended Mix", 124, "8B", "Progressive House", "Polarstern Records", 2024, 294),
    ("Elin Hart; Juna Weiss", "Sternstaub", "Dub", 120, "10A", "Organic House", "Waldklang", 2026, 330),
    ("Tim Kessler", "Hafenlichter", "Extended Mix", 128, "6A", "Tech House", "Nachtzug", 2025, 349),
    ("Mara Lind", "Eisblumen", "Radio Edit", 124, "8A", "Melodic House", "Polarstern Records", 2026, 392),
    ("Sami Roth", "Echolot", "Original Mix", 125, "11A", "Melodic Techno", "Tiefsee", 2026, 440),
    ("Juna Weiss", "Lichtung", "Extended Mix", 123, "5A", "Deep House", "Waldklang", 2023, 466),
    ("Ivo Berg", "Schwarzwasser", "Extended Mix", 127, "9B", "Techno", "Graustufen", 2026, 494),
    ("Nora Kluge feat. Leon Brand", "Abendrot", "Club Mix", 121, "4A", "Afro House", "Küstenlicht", 2025, 523),
    ("Leon Brand", "Funkenflug", "Original Mix", 126, "12A", "Tech House", "Nachtzug", 2026, 587),
]


def cover_files(folder: str) -> list:
    """Erzeugte Cover als JPEG-Dateien (für die Beispiel-MP3s) – gleiche Motive wie covers()."""
    import base64
    os.makedirs(folder, exist_ok=True)
    out = []
    for i, uri in enumerate(covers()):
        path = os.path.join(folder, f"cover{i}.jpg")
        if not os.path.isfile(path):
            from PIL import Image
            import io
            Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))).convert("RGB").resize((500, 500)).save(path, quality=90)
        out.append(path)
    return out


def make_library(folder: str, variant: bool = False, tracks=None) -> list:
    """variant: zweite Fassung mit ein paar abweichenden Tags (für den Vergleich); tracks: andere Titel (Eingang)."""
    os.makedirs(folder, exist_ok=True)
    out = []
    cov = cover_files(os.path.join(os.path.dirname(folder), "_cover"))
    for i, (artist, title, mix, bpm, key, genre, label, year, hz) in enumerate(tracks or TRACKS, 1):
        if variant and i in (2, 4, 7):
            bpm, key, genre = (bpm + 1, key, genre) if i == 2 else (bpm, "9B", genre) if i == 4 else (bpm, key, "House")
        path = os.path.join(folder, f"{artist} - {title} ({mix}).mp3")
        # pulsierender Ton → sichtbare Wellenform
        src = f"sine=frequency={hz}:duration=45,volume='0.35+0.3*gt(mod(t*{bpm}/60,1),0.5)':eval=frame"
        meta = {"title": f"{title} ({mix})", "artist": artist, "album": f"{title} EP", "genre": genre, "TBPM": str(bpm),
                "TKEY": key, "publisher": label, "date": str(year), "track": str(i)}
        args = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-i", cov[i % len(cov)],
                "-map", "0:a", "-map", "1:v", "-c:v", "copy", "-disposition:v", "attached_pic",
                "-metadata:s:v", "title=Album cover", "-metadata:s:v", "comment=Cover (front)",
                "-af", "volume=0.8", "-b:a", "128k", "-id3v2_version", "3"]
        for k, v in meta.items():
            args += ["-metadata", f"{k}={v}"]
        subprocess.run(args + [path], check=True)
        out.append(path)
    return out


def start_server(home: str):
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, "tagstudio_web.py"), "--browser", "--no-open", "--port", "0"],
                         env=dict(os.environ, HOME=home, USERPROFILE=home, PYTHONUNBUFFERED="1"),
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for _ in range(200):
        m = re.search(r"(http://\S+)", p.stdout.readline() or "")
        if m:
            return p, m.group(1)
    p.terminate()
    raise RuntimeError("Server startet nicht")


PURCHASES = """(() => { const orig = call;
  const row = (i, title, mix, artist, status, file, extra) => Object.assign({ k: "beatport:" + i, store: "beatport", id: String(i), title, mix, artist,
    dur: 380 + i * 7, key: ["8A", "9A", "7A", "8B", "10A", "6A"][i % 6], bpm: 120 + (i % 8), catalog: "PSR0" + (40 + i), label: "Polarstern Records",
    release: title + " EP", genre: "Melodic House", isrc: "", url: "https://www.beatport.com/", bought: "2026-10-" + String(26 - i).padStart(2, "0") + " 10:00:00",
    seen: 1, status, file, reason: "", preorder: false, downloaded: 0, await: false }, extra || {});
  const rows = [row(1, "Nordlicht", "Extended Mix", "Mara Lind", "library", "Nordlicht.mp3"), row(2, "Kaltes Glas", "Original Mix", "Ivo Berg", "inbox", "Kaltes Glas.mp3"),
    row(3, "Wellenbrecher", "Club Mix", "Lea Sommer", "unclear", "", { reason: "anderer Mix", cands: ["a", "b"] }), row(4, "Morgengrau", "Extended Mix", "Noah Feld", "library", "Morgengrau.mp3"),
    row(5, "Sternstaub", "Dub", "Elin Hart", "missing", "", { await: true }), row(6, "Hafenlichter", "Extended Mix", "Tim Kessler", "library", "Hafenlichter.mp3"),
    row(7, "Echolot", "Original Mix", "Sami Roth", "missing", ""), row(8, "Lichtung", "Extended Mix", "Juna Weiss", "library", "Lichtung.mp3")];
  window.call = (n, ...a) => {
    if (n === "purch_state") return Promise.resolve({ rows, stores: { beatport: { name: "Beatport" } }, sources: [{ id: "beatport", name: "Beatport", ready: true, why: "" }],
      count: { library: 4, inbox: 1, unclear: 1, missing: 2 }, dest: "D:/Musik/90_Download/Beatport", dest_from: "eigene Wahl", dest_ok: true,
      roots: ["D:/Musik/Bibliothek"], libs: [{ name: "Bibliothek", path: "D:/Musik/Bibliothek" }], libs_skipped: [], last: { roots: ["D:/Musik/Bibliothek"], files: 2480 },
      sessions: {}, unzip: true, strict: false });
    if (n === "purch_unzip") return Promise.resolve({ zips: [], files: 0, skipped: 0, errors: [] });
    if (n === "purch_dl_signature") return Promise.resolve({ waiting: 0, sig: "" });
    return orig(n, ...a); }; })()"""


# ---------------------------------------------------------------------------------------------- Beispieldaten (#439)
NEW_TRACKS = [("Ava Nordin", "Polarlicht", "Extended Mix", 124, "8A", "Melodic House", "Polarstern Records", 2026, 233),
              ("Kian Wolf", "Nachtfalter", "Original Mix", 126, "9A", "Melodic Techno", "Tiefsee", 2026, 277),
              ("Lina Brook", "Salzwiese", "Club Mix", 122, "7A", "Organic House", "Waldklang", 2026, 311),
              ("Ole Frost", "Glutwind", "Extended Mix", 125, "10B", "Progressive House", "Nachtzug", 2026, 370),
              ("Mira Stein feat. Jon Vale", "Fernweh", "Vocal Mix", 123, "8B", "Melodic House", "Küstenlicht", 2026, 415)]

# kopierte Trackliste wie von 1001Tracklists – erste Zeile = Titel des Mixes (#436)
TRACKLIST = """Mara Lind - Polarstern Radio 112 2026-10-30

[00:00] Mara Lind - Nordlicht (Extended Mix) [POLARSTERN RECORDS]
[04:12] Ava Nordin - Polarlicht (Extended Mix) [POLARSTERN RECORDS]
[08:40] Kian Wolf - Nachtfalter [TIEFSEE]
[13:05] Lina Brook - Salzwiese (Club Mix) [WALDKLANG]
Polarstern Discovery:
[17:30] Ole Frost - Glutwind (Extended Mix) [NACHTZUG]
[21:48] Mira Stein feat. Jon Vale - Fernweh (Vocal Mix) [KÜSTENLICHT]
[26:15] ID - ID
[30:02] Sami Roth - Echolot [TIEFSEE]
w/ Juna Weiss - Lichtung (Extended Mix) [WALDKLANG]
[34:40] Nora Kluge - Abendrot (Club Mix) [KÜSTENLICHT]"""

PALETTES = [("#ff7a59", "#7a3fd1"), ("#1d76db", "#5eead4"), ("#f59e0b", "#ef4444"), ("#10b981", "#2563eb"),
            ("#ec4899", "#8b5cf6"), ("#22d3ee", "#0f766e"), ("#a3e635", "#15803d"), ("#fb7185", "#f97316"),
            ("#6366f1", "#0ea5e9"), ("#eab308", "#0d9488")]


def covers(n=10) -> list:
    """Erzeugte Cover (Farbverlauf mit Kreisen) als data:-Adressen – keine fremden Bilder."""
    import base64
    import io
    from PIL import Image, ImageDraw
    out = []
    for i in range(n):
        a, b = PALETTES[i % len(PALETTES)]
        ca, cb = [tuple(int(c[k:k + 2], 16) for k in (1, 3, 5)) for c in (a, b)]
        img = Image.new("RGB", (240, 240))
        px = img.load()
        for y in range(240):
            for x in range(240):
                t = (x + y) / 478
                px[x, y] = tuple(int(ca[j] * (1 - t) + cb[j] * t) for j in range(3))
        d = ImageDraw.Draw(img, "RGBA")
        for k in range(3):
            r = 40 + 30 * k + 7 * i % 25
            cx, cy = 60 + 50 * ((i + k) % 3), 70 + 45 * ((i * 2 + k) % 3)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 120), width=3)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        out.append("data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii"))
    return out


def seed(home: str, lib: str, mixfile: str):
    """Läuft in einem eigenen Prozess mit HOME=home: Entdecken, Einkäufe, Warenkorb und ein Mix-Ergebnis."""
    import carts
    import discover
    import mixresult
    import paths
    import purchases
    cv = covers()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    d = discover.load()
    d["follow"]["artists"] = ["Mara Lind", "Ivo Berg", "Sami Roth", "Ava Nordin", "Kian Wolf"]
    d["follow"]["labels"] = ["Polarstern Records", "Tiefsee"]
    rows = NEW_TRACKS + [TRACKS[i] for i in (0, 7, 9, 1)]
    for i, (artist, title, mix, _bpm, _key, genre, label, _year, _hz) in enumerate(rows):
        key = f"beatport:{9100 + i}"
        d["items"][key] = {"key": key, "src": "beatport" if i % 3 else "deezer", "id": str(9100 + i), "artist": artist,
                           "title": title, "mix": mix, "label": label, "genre": genre, "date": f"2026-10-{30 - i * 2:02d}",
                           "preview": "", "url": f"https://www.beatport.com/track/{title.lower()}/{9100 + i}",
                           "cover": cv[i % len(cv)], "status": "saved" if i in (1, 3) else "new", "first": now,
                           "owned": i >= len(NEW_TRACKS)}
    discover.save(d)
    st = purchases.Store(paths.sub("Käufe"))
    st.merge("beatport", "Beatport", [{"id": 7001, "artist": "Sami Roth", "title": "Echolot", "mix": "Original Mix",
                                       "bought": "2026-10-28 20:15:00", "label": "Tiefsee"},
                                      {"id": 7002, "artist": "Mara Lind", "title": "Nordlicht", "mix": "Extended Mix",
                                       "bought": "2026-10-12 18:00:00", "label": "Polarstern Records"}])
    cs = carts.Store(paths.sub("Warenkorb"))
    url = lambda t, i: f"https://www.beatport.com/track/{t.lower()}/{i}"           # noqa: E731
    sure = lambda i, t: {"sid": str(i), "url": url(t, i), "match": {"state": "sure", "score": 0.94}}   # noqa: E731
    items = [
        dict(carts.item("Ava Nordin", "Polarlicht", "Extended Mix", src="text"), via="1001Tracklists", **sure(9100, "Polarlicht")),
        dict(carts.item("Kian Wolf", "Nachtfalter", "Original Mix", src="text"), via="1001Tracklists", **sure(9101, "Nachtfalter")),
        dict(carts.item("Lina Brook", "Salzwiese", "Club Mix", src="text"), via="1001Tracklists",
             match={"state": "unsure", "score": 0.7, "cands": [{"id": "9102", "artist": "Lina Brook", "title": "Salzwiese",
                    "mix": "Original Mix", "score": 0.72}, {"id": "9180", "artist": "Lina Brooks", "title": "Salzwiesen", "score": 0.64}]}),
        dict(carts.item("Ole Frost", "Glutwind", "Extended Mix", src="text"), via="1001Tracklists", **sure(9103, "Glutwind")),
        dict(carts.item("Mira Stein feat. Jon Vale", "Fernweh", "Vocal Mix", src="text"), via="1001Tracklists", **sure(9104, "Fernweh")),
        dict(carts.item("Sami Roth", "Echolot", "Original Mix", src="text"), via="1001Tracklists", **sure(7001, "Echolot"),
             removed={"why": "bought", "at": int(time.time())}),
        dict(carts.item("Nora Kluge", "Abendrot", "Club Mix", src="ideas"), via="Sommer-Set 2026", **sure(9110, "Abendrot")),
        dict(carts.item("Tom Reiser", "Weite", "Extended Mix", src="url"), via="Spotify", match={"state": "none", "score": 0.0}),
    ]
    items = [carts.clean_item(x) for x in items]
    old = [carts.clean_item(dict(carts.item(a, t, m, src="text"), via="MixID", **sure(8000 + k, t)))
           for k, (a, t, m) in enumerate([("Ivo Berg", "Kaltes Glas", "Original Mix"), ("Lea Sommer", "Wellenbrecher", "Club Mix"),
                                          ("Noah Feld", "Morgengrau", "Extended Mix")])]
    t0 = int(time.time())
    cs.data["carts"] = {
        "c_00000000a001": {"id": "c_00000000a001", "name": "Warenkorb_2026_11_02", "store": "beatport", "created": t0,
                           "status": "open", "auto": True, "items": items, "checked": t0},
        "c_00000000a002": {"id": "c_00000000a002", "name": "Warenkorb_2026_10_24", "store": "beatport", "created": t0 - 9 * 86400,
                           "status": "bought", "closed": t0 - 7 * 86400, "closed_by": "auto", "auto": True, "items": old,
                           "pushed": {"beatport": {"id": "1", "name": "TagStudio_CART_Warenkorb_2026_10_24", "url": "",
                                                   "at": t0 - 8 * 86400, "count": 3}}}}
    cs.save()
    files = sorted(os.listdir(lib))
    pick = [f for f in files if f.endswith(".mp3")][:7]
    rows, pos = [], 0.0
    for k, f in enumerate(pick):
        artist, rest = f[:-4].split(" - ", 1)
        if k == 4:
            pos += 120                                                    # Lücke → „ID – ID“
        dur = 300 + 23 * k
        rows.append({"start": pos, "end": pos + dur, "tempo": [0.8, 0.0, -1.2, 1.6, 0.4, -0.8, 2.0][k], "conf": [0.93, 0.88, 0.71, 0.95, 0.52, 0.9, 0.84][k],
                     "path": os.path.join(lib, f), "artist": artist, "title": rest, "keylock": True})
        pos += dur - 15
    res = mixresult.new(mixfile, pos + 60, rows)
    res["name"] = "Club Night 12 – Live-Set"
    mixresult.save(paths.sub("Mixe"), res)


IDEAS_OV = """((cv) => { const orig = call;
  window.call = (n, ...a) => n !== "ideas_overview" ? orig(n, ...a) : orig(n, ...a).then((d) => {
    (d.items || []).forEach((e, i) => { e.cover = cv[i % cv.length]; e.label = e.label || ["Polarstern Records", "Tiefsee", "Waldklang", "Nachtzug"][i % 4];
      e.date = e.date || "2026-10-" + String(28 - i * 3).padStart(2, "0"); });
    return d; }); })"""

MIX_OV = """(() => { const orig = call;
  window.call = (n, ...a) => n === "mix_list" ? orig(n, ...a).then((d) => Object.assign(d, { ready: true,
    plugin: { found: true, enabled: true, state: "ready", version: "1.3", status: "bereit" } })) : orig(n, ...a); })()"""


def _dismiss(pg, rounds=10):
    for _ in range(rounds):
        time.sleep(0.15)
        if pg.locator("#modal").is_visible():
            pg.click("#mBtns button >> nth=0")
        if pg.locator("#dialog").is_visible():
            pg.click("#dlgBtns button >> nth=0")


def _go(pg, module, wait=0.9):
    pg.click(f'.nav[data-module="{module}"]')
    time.sleep(wait)


def _crop(pg, sel, name, theme, hd):
    loc = pg.locator(sel).first
    if loc.count() and loc.is_visible():
        os.makedirs(os.path.join(hd, "ausschnitte"), exist_ok=True)
        loc.screenshot(path=os.path.join(hd, "ausschnitte", f"{name}-{theme}.png"))


def prepare_data(pg, music, lib):
    """Einmal (im ersten Durchgang): Ordner-Rollen, Playlists, Ideen, Cloud-Einstellungen – über die echte Sitzung."""
    pg.evaluate(f"call('folders_set_base', {json.dumps(music)}, true)")
    pg.evaluate("call('folders_create')")
    _go(pg, "tagger")
    pg.fill("#tgPath", lib)
    pg.click("#tgLoad")
    pg.wait_for_function("TG.loaded && TG.rows.length > 10")
    for name, folder, idx in (("Warm-up", "Sets", [2, 4, 8, 10]), ("Peak Time", "Sets", [1, 5, 7, 9, 11]),
                              ("Sonntagabend", "", [3, 6, 12]), ("Neu im Oktober", "Archiv", [0, 1, 2, 3, 4, 5])):
        pg.evaluate(f"call('pl_create', {json.dumps(name)}, {json.dumps(folder)}, {json.dumps(idx)})")
    pid = pg.evaluate("call('ideas_list_create', 'Sommer-Set 2026').then((d) => d.sel)")
    for i, (a, t, m) in enumerate([("Ava Nordin", "Polarlicht", "Extended Mix"), ("Kian Wolf", "Nachtfalter", "Original Mix"),
                                   ("Nora Kluge", "Abendrot", "Club Mix"), ("Ole Frost", "Glutwind", "Extended Mix"),
                                   ("Lina Brook", "Salzwiese", "Club Mix"), ("Sami Roth", "Echolot", "Original Mix")]):
        pg.evaluate(f"call('ideas_add_manual', {json.dumps(pid)}, {json.dumps({'artist': a, 'title': t, 'mix': m, 'url': f'https://www.beatport.com/track/{t.lower()}/{9200 + i}', 'note': 'fürs Warm-up' if i == 1 else ''})})")
    pg.evaluate(f"call('ideas_set', {json.dumps(pid)}, [0, 2, 3], 'buy')")
    pg.evaluate("call('ideas_list_create', 'Afro House')")
    od = os.path.join(os.path.dirname(music), "OneDrive", "TagStudio")
    for sub in ("Spiegel", "Sicherung"):
        os.makedirs(os.path.join(od, sub), exist_ok=True)
    pg.evaluate(f"call('mirror_set', {json.dumps({'folder': os.path.join(od, 'Spiegel'), 'libraries': [], 'auto': True, 'playlists': True, 'online_only': True})})")
    pg.evaluate(f"call('appbackup_set', {json.dumps({'folder': os.path.join(od, 'Sicherung'), 'auto': 'daily', 'keep': 10})})")


def _open(pg, url, theme, cv):
    pg.goto(url)
    pg.wait_for_function("typeof S !== 'undefined' && S.settings")
    pg.evaluate(f"S.opts.theme = '{theme}'; applyTheme(); call('set_option', 'theme', '{theme}')")
    pg.add_style_tag(content="#ver{visibility:hidden}")      # Entwicklungsstand nicht im Bild
    _dismiss(pg, 12)
    pg.evaluate(f"{IDEAS_OV}({json.dumps(cv)})")
    pg.evaluate(MIX_OV)


def scenes(pg, url, theme, lib, lib2, hd, cv):
    pg.evaluate(f"{IDEAS_OV}({json.dumps(cv)})")
    pg.evaluate(MIX_OV)
    # Entdecken
    _go(pg, "discover")
    pg.wait_for_function("typeof DISC !== 'undefined' && DISC.d && DISC.d.items.length > 5")
    pg.evaluate("(() => { const b = document.querySelector('#discFilter [data-f=\"all\"]'); if (b) b.click(); })()")
    time.sleep(0.8)
    shot(pg, "discover", theme, hd)
    # Ideen
    _go(pg, "ideas")
    pg.wait_for_function("IDEA.d && IDEA.d.lists.length >= 2")
    pg.evaluate("ideasShow(IDEA.d.lists.find((l) => l.name.startsWith('Sommer')).id)")
    pg.wait_for_function("IDEA.d.items.length >= 6")
    time.sleep(0.6)
    shot(pg, "ideas", theme, hd)
    # Warenkorb: Einkaufsliste (alle), Assistent, Vorschau „Liste einfügen“
    _go(pg, "carts")
    pg.evaluate("cartsShow('c_00000000a001')")
    pg.wait_for_function("CART.d && CART.d.items.length >= 8")
    pg.click('#cartFilter [data-f="all"]')
    time.sleep(0.6)
    shot(pg, "carts", theme, hd)
    pg.evaluate("cartsWizard(); 0")
    pg.wait_for_selector("#modal:not([hidden]) .cart-wz-steps")
    time.sleep(0.5)
    shot(pg, "carts-wizard", theme, hd)
    _crop(pg, ".modal-dlg", "assistent", theme, hd)
    pg.keyboard.press("Escape")
    time.sleep(0.4)
    pg.evaluate(f"tracklistPickDialog({json.dumps(TRACKLIST)}, 'Liste einfügen – Vorschau'); 0")
    pg.wait_for_selector("#modal:not([hidden]) .cart-pv")
    time.sleep(0.5)
    shot(pg, "carts-paste", theme, hd)
    _crop(pg, ".modal-dlg", "vorschau-trackliste", theme, hd)
    pg.keyboard.press("Escape")
    time.sleep(0.3)
    # Vorbereiten
    _go(pg, "prep", 1.6)
    _dismiss(pg, 4)
    shot(pg, "prep", theme, hd)
    # Tagger mit Auswahl, Editor und Player
    _go(pg, "tagger")
    pg.fill("#tgPath", lib)
    pg.click("#tgLoad")
    pg.wait_for_function("TG.loaded && TG.rows.length > 10")
    time.sleep(0.6)
    pg.click(".tg-row >> nth=1")
    time.sleep(1.4)
    shot(pg, "tagger", theme, hd)
    # Tag-Fixer
    _go(pg, "tagger", 1.2)
    pg.wait_for_function("TG.loaded && TG.rows.length > 10")
    pg.evaluate("setModule('fixer', { scope: 'tag_all', side: true })")
    time.sleep(1.8)
    shot(pg, "fixer", theme, hd)
    # Vergleich
    _go(pg, "compare")
    pg.fill("#pathL", lib)
    pg.fill("#pathR", lib2)
    pg.click("#compareBtn")
    pg.wait_for_selector("#cmp:not([hidden])")
    time.sleep(0.8)
    pg.click(".pair[data-i=\"1\"]")
    time.sleep(0.8)
    shot(pg, "compare", theme, hd)
    # DJ-Set
    _go(pg, "djset", 0.6)
    if theme == "light":                                       # Set bleibt gespeichert
        pg.click('.nav[data-module="tagger"]')
        time.sleep(0.4)
        pg.click('.nav[data-module="djset"]')
        time.sleep(0.4)
        pg.click("#djAllTagger")
        time.sleep(1.5)
        pg.click("#djOpt")
    time.sleep(2.0)
    _dismiss(pg)
    shot(pg, "djset", theme, hd)
    _crop(pg, "#djWheel", "camelot-rad", theme, hd)
    # Mixe
    _go(pg, "mixes", 1.2)
    pg.evaluate("(() => { const b = document.querySelector('#mxList [data-id], #mxList button.idea-l'); if (b) b.click(); })()")
    time.sleep(1.2)
    shot(pg, "mixes", theme, hd)
    # Playlists
    _go(pg, "playlists", 1.0)
    pg.locator(".pls-pl", has_text="Peak Time").last.click()
    time.sleep(1.0)
    shot(pg, "playlists", theme, hd)
    # Einkäufe (nachgebildet)
    pg.evaluate(PURCHASES)
    _go(pg, "purchases")
    pg.wait_for_selector("#purTable tbody tr")
    time.sleep(0.6)
    shot(pg, "purchases", theme, hd)
    # Einstellungen › Cloud (Spiegel, Sicherung)
    _go(pg, "settings", 1.0)
    pg.evaluate("""stFoldSet(['stCloudCard'], true); $$('#stGrid > .card').forEach((c) => { if (c.id !== 'stCloudCard') c.hidden = true; });
      stMasonry(); $('#stGrid').style.columns = '1'; $('#stGrid').style.maxWidth = '1180px';
      document.getElementById('stCloudCard').scrollIntoView({ block: 'start' })""")       # nur die Kachel „Cloud“
    time.sleep(1.0)
    shot(pg, "cloud", theme, hd)
    pg.evaluate("$$('#stGrid > .card').forEach((c) => { c.hidden = false; }); $('#stGrid').style.columns = $('#stGrid').style.maxWidth = ''; stMasonry()")
    # Plugins
    _go(pg, "plugins")
    pg.wait_for_selector(".pl-card")
    time.sleep(0.6)
    shot(pg, "plugins", theme, hd)
    # zuletzt: Player mit Wellenform als Ausschnitt – breiteres Fenster, damit nichts überlappt (#444)
    pg.set_viewport_size({"width": 2200, "height": VIEW["height"]})
    _go(pg, "tagger", 1.0)
    pg.dblclick(".tg-row >> nth=1")
    time.sleep(2.5)
    pg.evaluate("PLAYER.audio && PLAYER.audio.pause()")
    time.sleep(0.6)
    pg.mouse.move(2, 2)
    _crop(pg, "#player", "player-wellenform", theme, hd)
    pg.set_viewport_size(VIEW)


def main() -> int:
    from playwright.sync_api import sync_playwright
    hd = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "TagStudio-Screenshots")
    shutil.rmtree(hd, ignore_errors=True)
    os.makedirs(hd)
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(tempfile.gettempdir(), "TagStudio-Demo")          # kurzer, lesbarer Pfad in den Bildern
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    try:
        music = os.path.join(base, "Musik")
        lib = os.path.join(music, "01_Library")
        make_library(lib)
        lib2 = os.path.join(music, "Vergleich")
        make_library(lib2, variant=True)
        inbox = os.path.join(music, "00_New")
        make_library(inbox, tracks=NEW_TRACKS)
        mixfile = os.path.join(music, "Mixe", "Club Night 12 – Live-Set.mp3")
        os.makedirs(os.path.dirname(mixfile), exist_ok=True)
        open(mixfile, "wb").close()
        home = os.path.join(base, "home")
        os.makedirs(home)
        from version import VERSION
        with open(os.path.join(home, ".tagstudio.json"), "w", encoding="utf-8") as fh:
            json.dump({"setup_done": "screenshots", "seen_version": VERSION, "first_steps": False, "snap_hint": False,
                       "update_notify": False, "player": {"resume": False}}, fh)       # Player nach dem Neuladen leer
        subprocess.run([sys.executable, os.path.abspath(__file__), "--seed", home, lib, mixfile], check=True,
                       env=dict(os.environ, HOME=home, USERPROFILE=home))
        cv = covers()
        server, url = start_server(home)
        try:
            with sync_playwright() as pw:
                br = pw.chromium.launch()
                for theme in ("light", "dark"):
                    ctx = br.new_context(viewport=VIEW, device_scale_factor=SCALE, color_scheme=theme, locale="de-CH")
                    pg = ctx.new_page()
                    pg.set_default_timeout(20000)
                    pg.goto(url)
                    pg.wait_for_function("typeof S !== 'undefined' && S.settings")
                    pg.evaluate(f"S.opts.theme = '{theme}'; applyTheme(); call('set_option', 'theme', '{theme}')")
                    pg.add_style_tag(content="#ver{visibility:hidden}")      # Entwicklungsstand nicht im Bild
                    _dismiss(pg, 20)
                    if theme == "light":
                        prepare_data(pg, music, lib)
                    scenes(pg, url, theme, lib, lib2, hd, cv)
                    ctx.close()
                site_copies(hd)
                social_preview(br)
                video_cards(br, hd)
                br.close()
        finally:
            server.terminate()
            server.wait(10)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print("Bilder in", hd, "und", OUT)
    return 0


def site_copies(hd):
    """Motive der Startseite verkleinert (1600 × 900) nach docs/screenshots – die 2560er bleiben ausserhalb des Repos."""
    from PIL import Image
    for name in SITE:
        for theme in ("light", "dark"):
            src = os.path.join(hd, f"{name}-{theme}.png")
            if os.path.isfile(src):
                im = Image.open(src).convert("RGB")
                im = im.resize((VIEW["width"], VIEW["height"]), Image.LANCZOS)
                im.quantize(256, method=Image.Quantize.MEDIANCUT).save(os.path.join(OUT, f"{name}-{theme}.png"), optimize=True)   # ⅓ der Grösse
                print("  ", f"docs/screenshots/{name}-{theme}.png")


def video_cards(br, hd):
    """#441: Titelbild für YouTube (1280 × 720) und Schlussbild (2560 × 1440)."""
    import base64
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode("ascii")      # noqa: E731
    icon = b64(os.path.join(ROOT, "web", "icon.png"))
    img = lambda n: b64(os.path.join(hd, n)) if os.path.isfile(os.path.join(hd, n)) else ""     # noqa: E731
    css = """html,body{width:100%;height:100%}body{margin:0;overflow:hidden;background:radial-gradient(circle at 18% 22%,#22324a,#0f1216 62%);
      font-family:Inter,system-ui,sans-serif;color:#e8ecf1}"""
    os.makedirs(os.path.join(hd, "video"), exist_ok=True)
    title = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
      .t{{position:absolute;left:64px;top:118px;width:520px}} .t img{{width:84px;height:84px;border-radius:20px}}
      h1{{font-size:62px;line-height:1.02;margin:22px 0 14px;letter-spacing:-.02em}}
      p{{font-size:27px;line-height:1.35;color:#a9b4c2;margin:0}}
      .k{{margin-top:24px;display:flex;flex-wrap:wrap;gap:9px;font-size:18px;color:#cdd6e1}} .k span{{border:1px solid #33404f;border-radius:99px;padding:5px 13px}}
      .s1{{position:absolute;left:600px;top:60px;width:860px;border-radius:14px;box-shadow:0 30px 80px rgba(0,0,0,.6);border:1px solid #2c3542}}
      .s2{{position:absolute;left:760px;top:390px;width:560px;border-radius:12px;box-shadow:0 24px 60px rgba(0,0,0,.65);border:1px solid #2c3542}}
      </style></head><body><div class="t"><img src="data:image/png;base64,{icon}"><h1>Vom Fund bis ins DJ-Set</h1>
      <p>MarKusSXCH TagStudio – kostenlos für Windows &amp; macOS</p>
      <div class="k"><span>Entdecken</span><span>Warenkorb</span><span>Tagger</span><span>DJ-Set</span></div></div>
      <img class="s1" src="data:image/png;base64,{img('tagger-dark.png')}"><img class="s2" src="data:image/png;base64,{img('carts-dark.png')}">
      </body></html>"""
    end = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}
      .c{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}}
      .c img{{width:150px;height:150px;border-radius:34px}} h1{{font-size:88px;margin:34px 0 10px;letter-spacing:-.02em}}
      p{{font-size:38px;color:#a9b4c2;margin:0 0 40px}} .b{{font-size:34px;padding:18px 40px;border-radius:22px;background:#1d76db;color:#fff;font-weight:600}}
      .u{{margin-top:34px;font-size:30px;color:#8fa0b4}}</style></head><body><div class="c">
      <img src="data:image/png;base64,{icon}"><h1>MarKusSXCH TagStudio</h1><p>Kostenlos und quelloffen · Windows &amp; macOS</p>
      <div class="b">Jetzt herunterladen</div><div class="u">markuskeller8200.github.io/markussxch-tagstudio</div></div></body></html>"""
    for html, (w, h), name in ((title, (1280, 720), "titelbild-youtube.png"), (end, (1280, 720), "schlussbild.png")):
        pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=1 if name.startswith("titel") else 2)
        pg.set_content(html)
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(hd, "video", name))
        pg.close()
        print("  ", os.path.join("video", name))


def social_preview(br) -> None:
    """Vorschaubild für soziale Netze (GitHub › Settings › Social preview): Symbol, Name, Satz, Ausschnitt Tagger."""
    import base64
    b64 = lambda p: base64.b64encode(open(p, "rb").read()).decode("ascii")      # noqa: E731
    icon, shotimg = b64(os.path.join(ROOT, "web", "icon.png")), b64(os.path.join(OUT, "tagger-dark.png"))
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      body{{margin:0;width:1280px;height:640px;overflow:hidden;background:radial-gradient(circle at 20% 20%,#22324a,#0f1216 60%);
        font-family:Inter,system-ui,sans-serif;color:#e8ecf1}}
      .t{{position:absolute;left:72px;top:150px;width:520px}}
      .t img{{width:88px;height:88px;border-radius:20px}}
      h1{{font-size:56px;line-height:1.05;margin:26px 0 14px;letter-spacing:-.02em}}
      p{{font-size:24px;line-height:1.4;color:#a9b4c2;margin:0}}
      .k{{margin-top:26px;display:flex;gap:10px;font-size:17px;color:#cdd6e1}}
      .k span{{border:1px solid #33404f;border-radius:99px;padding:5px 13px}}
      .s{{position:absolute;left:640px;top:70px;width:900px;border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,.6);
        border:1px solid #2c3542}}</style></head><body>
      <div class="t"><img src="data:image/png;base64,{icon}"><h1>MarKusSXCH<br>TagStudio</h1>
        <p>Der Werkzeugkasten für die MP3-Bibliothek von DJs</p>
        <div class="k"><span>Warenkorb</span><span>Tagger</span><span>Vergleich</span><span>DJ-Set</span></div></div>
      <img class="s" src="data:image/png;base64,{shotimg}"></body></html>"""
    pg = br.new_page(viewport={"width": 1280, "height": 640})
    pg.set_content(html)
    pg.wait_for_timeout(300)
    path = os.path.join(ROOT, "docs", "social-preview.png")
    pg.screenshot(path=path)
    pg.close()
    print("  ", os.path.relpath(path, ROOT))



def shot(pg, name: str, theme: str, hd: str) -> None:
    pg.mouse.move(2, 2)
    path = os.path.join(hd, f"{name}-{theme}.png")
    pg.screenshot(path=path)
    print("  ", f"{name}-{theme}.png")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--seed":
        seed(*sys.argv[2:5])
        sys.exit(0)
    sys.exit(main())
