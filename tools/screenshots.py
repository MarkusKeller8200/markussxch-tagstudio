"""Bildschirmfotos der Oberfläche für die Startseite des Repositories (#373).

    python tools/screenshots.py            # → docs/screenshots/<name>-light.png und <name>-dark.png
                                           #   und docs/social-preview.png (Vorschaubild für GitHub, 1280×640)

Braucht Playwright (Chromium) und ffmpeg. Alles läuft mit einem frischen Benutzerordner und einer Beispiel-
Bibliothek mit erfundenen Titeln (keine privaten Daten, keine echten Künstler). Einkäufe werden nachgebildet
(kein Store-Zugang nötig).
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
sys.path.insert(0, ROOT)

# Erfundene Titel: Künstler, Titel, Mix, BPM, Tonart (Camelot), Genre, Label, Jahr, Ton (Hz)
TRACKS = [
    ("Mara Lind", "Nordlicht", "Extended Mix", 124, "8A", "Melodic House", "Polarstern Records", 2026, 220),
    ("Ivo Berg", "Kaltes Glas", "Original Mix", 126, "9A", "Techno", "Graustufen", 2025, 247),
    ("Lea Sommer", "Wellenbrecher", "Club Mix", 122, "7A", "Deep House", "Küstenlicht", 2026, 262),
    ("Noah Feld", "Morgengrau", "Extended Mix", 124, "8B", "Progressive House", "Polarstern Records", 2024, 294),
    ("Elin Hart", "Sternstaub", "Dub", 120, "10A", "Organic House", "Waldklang", 2026, 330),
    ("Tim Kessler", "Hafenlichter", "Extended Mix", 128, "6A", "Tech House", "Nachtzug", 2025, 349),
    ("Mara Lind", "Eisblumen", "Radio Edit", 124, "8A", "Melodic House", "Polarstern Records", 2026, 392),
    ("Sami Roth", "Echolot", "Original Mix", 125, "11A", "Melodic Techno", "Tiefsee", 2026, 440),
    ("Juna Weiss", "Lichtung", "Extended Mix", 123, "5A", "Deep House", "Waldklang", 2023, 466),
    ("Ivo Berg", "Schwarzwasser", "Extended Mix", 127, "9B", "Techno", "Graustufen", 2026, 494),
    ("Nora Kluge", "Abendrot", "Club Mix", 121, "4A", "Afro House", "Küstenlicht", 2025, 523),
    ("Leon Brand", "Funkenflug", "Original Mix", 126, "12A", "Tech House", "Nachtzug", 2026, 587),
]


def make_library(folder: str, variant: bool = False) -> list:
    """variant: zweite Fassung mit ein paar abweichenden Tags (für den Vergleich)."""
    os.makedirs(folder, exist_ok=True)
    out = []
    for i, (artist, title, mix, bpm, key, genre, label, year, hz) in enumerate(TRACKS, 1):
        if variant and i in (2, 4, 7):
            bpm, key, genre = (bpm + 1, key, genre) if i == 2 else (bpm, "9B", genre) if i == 4 else (bpm, key, "House")
        path = os.path.join(folder, f"{artist} - {title} ({mix}).mp3")
        # pulsierender Ton → sichtbare Wellenform
        src = f"sine=frequency={hz}:duration=45,volume='0.35+0.3*gt(mod(t*{bpm}/60,1),0.5)':eval=frame"
        meta = {"title": f"{title} ({mix})", "artist": artist, "album": f"{title} EP", "genre": genre, "TBPM": str(bpm),
                "TKEY": key, "publisher": label, "date": str(year), "track": str(i)}
        args = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-af", "volume=0.8", "-b:a", "128k",
                "-id3v2_version", "3"]
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


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    base = os.path.join(tempfile.gettempdir(), "TagStudio-Demo")          # kurzer, lesbarer Pfad in den Bildern
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    try:
        lib = os.path.join(base, "Musik", "Bibliothek")
        make_library(lib)
        lib2 = os.path.join(base, "Musik", "Eingang")
        make_library(lib2, variant=True)
        home = os.path.join(base, "home")
        os.makedirs(home)
        from version import VERSION
        with open(os.path.join(home, ".tagstudio.json"), "w", encoding="utf-8") as fh:
            json.dump({"setup_done": "screenshots", "seen_version": VERSION, "first_steps": False, "snap_hint": False}, fh)
        server, url = start_server(home)
        try:
            with sync_playwright() as pw:
                br = pw.chromium.launch()
                for theme in ("light", "dark"):
                    ctx = br.new_context(viewport={"width": 1600, "height": 900}, color_scheme=theme)
                    pg = ctx.new_page()
                    pg.set_default_timeout(15000)
                    pg.goto(url)
                    pg.wait_for_function("typeof S !== 'undefined' && S.settings")
                    pg.evaluate(f"S.opts.theme = '{theme}'; applyTheme(); call('set_option', 'theme', '{theme}')")
                    pg.add_style_tag(content="#ver{visibility:hidden}")      # Entwicklungsstand nicht im Bild
                    for _ in range(20):
                        time.sleep(0.15)
                        if pg.locator("#modal").is_visible():
                            pg.click("#mBtns button >> nth=0")
                    # Tagger mit Auswahl und Editor
                    pg.click('.nav[data-module="tagger"]')
                    pg.fill("#tgPath", lib)
                    pg.click("#tgLoad")
                    pg.wait_for_function(f"TG.loaded && TG.rows.length === {len(TRACKS)}")
                    time.sleep(0.6)
                    pg.click(".tg-row >> nth=1")
                    time.sleep(1.2)
                    shot(pg, "tagger", theme)
                    # Vergleich: Eingang gegen Bibliothek (drei Titel mit abweichenden Tags)
                    pg.click('.nav[data-module="compare"]')
                    pg.fill("#pathL", lib)
                    pg.fill("#pathR", lib2)
                    pg.click("#compareBtn")
                    try:
                        pg.wait_for_selector("#cmp:not([hidden])")
                    except Exception:
                        pg.screenshot(path=os.path.join(OUT, "_fehler.png"))
                        raise
                    time.sleep(0.8)
                    pg.click(".pair[data-i=\"1\"]")                       # Paar mit Unterschied (BPM)
                    time.sleep(0.8)
                    shot(pg, "compare", theme)
                    # DJ-Set mit den geladenen Titeln
                    pg.click('.nav[data-module="djset"]')
                    time.sleep(0.6)
                    if theme == "light":                                       # Set bleibt gespeichert
                        pg.click("#djAllTagger")
                        time.sleep(1.5)
                        pg.click("#djOpt")
                    time.sleep(2.0)
                    for _ in range(10):
                        time.sleep(0.2)
                        if pg.locator("#modal").is_visible():
                            pg.click("#mBtns button >> nth=0")
                    shot(pg, "djset", theme)
                    # Einkäufe (nachgebildet)
                    pg.evaluate(PURCHASES)
                    pg.click('.nav[data-module="purchases"]')
                    pg.wait_for_selector("#purTable tbody tr")
                    time.sleep(0.6)
                    shot(pg, "purchases", theme)
                    # Plugins
                    pg.click('.nav[data-module="plugins"]')
                    pg.wait_for_selector(".pl-card")
                    time.sleep(0.6)
                    shot(pg, "plugins", theme)
                    ctx.close()
                social_preview(br)
                br.close()
        finally:
            server.terminate()
            server.wait(10)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print("Bilder in", OUT)
    return 0


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
        <div class="k"><span>Tagger</span><span>Vergleich</span><span>Einkäufe</span><span>DJ-Set</span></div></div>
      <img class="s" src="data:image/png;base64,{shotimg}"></body></html>"""
    pg = br.new_page(viewport={"width": 1280, "height": 640})
    pg.set_content(html)
    pg.wait_for_timeout(300)
    path = os.path.join(ROOT, "docs", "social-preview.png")
    pg.screenshot(path=path)
    pg.close()
    print("  ", os.path.relpath(path, ROOT))


def shot(pg, name: str, theme: str) -> None:
    pg.mouse.move(2, 2)
    path = os.path.join(OUT, f"{name}-{theme}.png")
    pg.screenshot(path=path)
    print("  ", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    sys.exit(main())
