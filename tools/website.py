"""Projekt-Webseite für GitHub Pages bauen (#375).

    python tools/website.py OUT            # z. B. stats/docs (Zweig „stats“, Pages-Ordner /docs)

Erzeugt aus dem Repo:
  index.html       Startseite (Download-Knöpfe direkt zur neuesten Datei, Bilder hell/dunkel, Kacheln, Zahlen)
  handbuch.html    Handbuch Deutsch (docs/HANDBUCH.md) mit Inhaltsverzeichnis und Suche
  manual.html      Handbuch Englisch (docs/HANDBUCH.en.md)
  statistik.html   Download-Statistik (.github/stats/index.html, liest summary.json)
  img/             Symbol, Bildschirmfotos, Vorschaubild
Braucht das Paket „markdown“ (pip install markdown). Keine externen Skripte, keine Cookies.
"""
from __future__ import annotations

import html
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "MarkusKeller8200/markussxch-tagstudio"
GH = f"https://github.com/{REPO}"
SITE = "https://markuskeller8200.github.io/markussxch-tagstudio/"

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--muted:#5f6b7a;--line:#e2e6ea;--acc:#1d76db;--acc2:#7a3fd1;--code:#eef1f5;--hl:#fff2a8}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--card:#171b21;--fg:#e8ecf1;--muted:#97a3b3;--line:#262c35;--acc:#5eaaff;--acc2:#c9a2ff;--code:#1f252d;--hl:#5a4a00}}
*{box-sizing:border-box}html{scroll-padding-top:72px}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
header.top .in{max-width:1180px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
header.top .brand{display:flex;align-items:center;gap:10px;font-weight:700;color:var(--fg)}
header.top .brand img{width:30px;height:30px;border-radius:8px}
header.top nav{display:flex;gap:16px;flex-wrap:wrap;margin-left:auto;font-size:15px}
header.top nav a{color:var(--muted)}header.top nav a.on,header.top nav a:hover{color:var(--fg);text-decoration:none}
main{max-width:1180px;margin:0 auto;padding:28px 16px 56px}
.btn{display:inline-flex;align-items:center;gap:8px;background:var(--acc);color:#fff;padding:11px 18px;border-radius:12px;font-weight:600}
.btn:hover{text-decoration:none;opacity:.92}.btn.alt{background:transparent;color:var(--fg);border:1px solid var(--line)}
@media (prefers-color-scheme:dark){.btn{color:#0f1216}.btn.alt{color:var(--fg)}}
.muted{color:var(--muted)}.sm{font-size:14px}
footer{max-width:1180px;margin:0 auto;padding:24px 16px 40px;color:var(--muted);font-size:14px;border-top:1px solid var(--line)}
/* Startseite */
.hero{text-align:center;padding:36px 0 18px}.hero img.logo{width:88px;height:88px;border-radius:22px}
.hero h1{font-size:clamp(30px,5vw,46px);line-height:1.1;margin:18px 0 10px;letter-spacing:-.02em}
.hero p.lead{font-size:clamp(17px,2.4vw,21px);color:var(--muted);max-width:720px;margin:0 auto}
.dl{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin:24px 0 8px}
.ver{color:var(--muted);font-size:14px}
.shot{margin:28px auto 8px;max-width:1100px}.shot img{width:100%;border-radius:14px;border:1px solid var(--line);box-shadow:0 18px 50px rgba(0,0,0,.18)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:34px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.tile b{display:block;font-size:17px;margin-bottom:4px}.tile span{color:var(--muted);font-size:15px}
.pics{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
.pics figure{margin:0}.pics img{width:100%;border-radius:12px;border:1px solid var(--line)}
.pics figcaption{color:var(--muted);font-size:14px;margin-top:6px}
.nums{display:flex;gap:28px;justify-content:center;flex-wrap:wrap;margin:10px 0 0}.nums div{text-align:center}
.nums b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.nums span{color:var(--muted);font-size:13px}
h2.sec{font-size:24px;margin:44px 0 14px}
/* Handbuch */
.doc{display:grid;grid-template-columns:270px minmax(0,1fr);gap:28px;align-items:start}
.toc{position:sticky;top:76px;max-height:calc(100vh - 96px);overflow:auto;font-size:14px;padding-right:6px}
.toc input{width:100%;padding:9px 11px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--fg);font:inherit;margin-bottom:10px}
.toc ul{list-style:none;margin:0;padding:0}.toc li{margin:2px 0}.toc li li{padding-left:14px}
.toc a{color:var(--muted);display:block;padding:2px 6px;border-radius:6px}.toc a:hover{color:var(--fg);background:var(--card);text-decoration:none}
.toc .hit{color:var(--muted);font-size:13px;margin:0 0 8px}
article{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:8px 30px 30px;min-width:0}
article h1{font-size:30px;margin:22px 0 8px}article h2{font-size:23px;margin:34px 0 10px;padding-top:10px;border-top:1px solid var(--line)}
article h3{font-size:19px;margin:26px 0 8px}article h4{font-size:16px;margin:20px 0 6px}
article code{background:var(--code);padding:1px 5px;border-radius:5px;font-size:.9em}
article pre{background:var(--code);padding:12px 14px;border-radius:10px;overflow:auto}article pre code{background:none;padding:0}
article table{border-collapse:collapse;display:block;overflow-x:auto;margin:12px 0}
article th,article td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
article blockquote{margin:12px 0;padding:6px 14px;border-left:4px solid var(--acc);color:var(--muted)}
article img{max-width:100%}
article section.hide{display:none}
article{overflow-wrap:anywhere}.doc>*{min-width:0}article pre{white-space:pre-wrap}
.tile code{overflow-wrap:anywhere}mark{background:var(--hl);color:inherit;border-radius:3px}
.toc-btn{display:none}
@media (max-width:860px){.doc{grid-template-columns:1fr}.toc{position:static;max-height:none}.toc ul{display:none}.toc.open ul{display:block}
  .toc-btn{display:inline-block;margin-bottom:8px}article{padding:4px 16px 20px}}
"""


def page(title: str, body: str, active: str, desc: str, lang: str = "de", extra_head: str = "") -> str:
    nav = [("index.html", "Start" if lang == "de" else "Start"), ("handbuch.html" if lang == "de" else "manual.html",
           "Handbuch" if lang == "de" else "Manual"), ("statistik.html", "Statistik" if lang == "de" else "Statistics"),
           (f"{GH}/releases/latest", "Download"), (GH, "GitHub")]
    on = ' class="on"'
    links = "".join(f'<a href="{h}"{on if h == active else ""}>{t}</a>' for h, t in nav)
    other = ('<a href="manual.html" hreflang="en">EN</a>' if lang == "de" else '<a href="handbuch.html" hreflang="de">DE</a>')
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="{SITE}img/social-preview.png"><meta property="og:type" content="website">
<meta name="twitter:card" content="summary_large_image"><link rel="icon" href="img/icon.png">
<style>{CSS}</style>{extra_head}</head><body>
<header class="top"><div class="in"><a class="brand" href="index.html"><img src="img/icon.png" alt="">MarKusSXCH TagStudio</a>
<nav>{links}{other}</nav></div></header>
{body}
<footer>MarKusSXCH TagStudio · <a href="{GH}">GitHub</a> · <a href="{GH}/blob/main/LICENSE">GNU GPL v3</a> ·
<a href="{GH}/issues">Fehler &amp; Ideen</a> · Diese Seite setzt keine Cookies und lädt nichts von fremden Servern.</footer>
</body></html>
"""


TILES = [("🏷️ Tagger", "Viele Dateien gemeinsam bearbeiten, Cover, Tags aus dem Dateinamen, Umbenennen, Export nach Excel/CSV."),
         ("⚖️ Vergleich", "Zwei Ordner oder Dateien Feld für Feld – zeichengenau markiert, Werte per Pfeil übernehmen."),
         ("🧹 Tag-Fixer", "Mehrfachwerte (; / feat. …) vereinheitlichen, Smart-Fix-Rezepte, Ausnahmen je Feld."),
         ("🛒 Einkäufe", "Beatport-Käufe mit der Bibliothek abgleichen, fehlende laden, Playlists in Beatport anlegen."),
         ("🎛️ DJ-Set", "Reihenfolge nach Tonart (Camelot), BPM und Energie – Export als M3U8, Rekordbox-XML, CSV."),
         ("📂 Playlists", "Titel sammeln und ordnen, als M3U8 für Engine DJ, VirtualDJ & Co."),
         ("🎧 Vorschau-Player", "Wellenform, Cue-Marken (Serato, Mixed In Key), Überblenden mit Tempo-Angleichung."),
         ("🛡️ Sicher speichern", "Sicherung vor jedem Speichern, Rückgängig über alle Dateien, Snapshots."),
         ("🧩 Plugins", "Stems, Beatport, Discogs, MusicBrainz, Lexicon, Cloud-Abgleich (OneDrive, Google Drive, Dropbox).")]
PICS = [("compare", "Vergleich – Unterschiede je Feld, per Pfeil übernehmen"),
        ("djset", "DJ-Set – Weg durch das Camelot-Rad, Energie und BPM"),
        ("purchases", "Einkäufe – gekauft, im Eingang, in der Bibliothek, fehlt"),
        ("plugins", "Plugins – nach Kategorie, einzeln aktualisierbar")]


def pic(name: str, alt: str) -> str:
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="img/{name}-dark.png">'
            f'<img src="img/{name}-light.png" alt="{html.escape(alt)}" loading="lazy"></picture>')


def landing() -> str:
    tiles = "".join(f'<div class="tile"><b>{html.escape(t)}</b><span>{html.escape(d)}</span></div>' for t, d in TILES)
    pics = "".join(f"<figure>{pic(n, c)}<figcaption>{html.escape(c)}</figcaption></figure>" for n, c in PICS)
    body = f"""<main>
<section class="hero"><img class="logo" src="img/icon.png" alt="">
<h1>MarKusSXCH TagStudio</h1>
<p class="lead">Der Werkzeugkasten für die MP3-Bibliothek von DJs: taggen, vergleichen, aufräumen, Einkäufe abgleichen und
Sets planen – für Windows und macOS. Kostenlos und quelloffen.</p>
<div class="dl"><a class="btn" id="dlWin" href="{GH}/releases/latest">⬇ Download für Windows</a>
<a class="btn" id="dlMac" href="{GH}/releases/latest">⬇ Download für macOS (Apple-Chip)</a>
<a class="btn alt" href="handbuch.html">Handbuch lesen</a></div>
<div class="ver" id="ver">Neueste Version auf GitHub</div>
<div class="nums" id="nums"></div></section>
<div class="shot">{pic("tagger", "Tagger: viele Dateien gemeinsam bearbeiten")}</div>
<h2 class="sec">Was TagStudio kann</h2><div class="grid">{tiles}</div>
<h2 class="sec">Bilder</h2><div class="pics">{pics}</div>
<p class="muted sm">Bilder mit erfundenen Beispieltiteln.</p>
<h2 class="sec">Installation</h2>
<div class="grid"><div class="tile"><b>Windows</b><span>Setup herunterladen und ausführen – ohne Administratorrechte.
Der Installer ist nicht signiert: bei „Der Computer wurde durch Windows geschützt“ <i>Weitere Informationen → Trotzdem
ausführen</i>.</span></div>
<div class="tile"><b>macOS (Apple-Chip)</b><span>Disk-Image öffnen, TagStudio auf „Programme“ ziehen und starten. Hinweise
zum ersten Start stehen in „Zuerst lesen.txt“ im Disk-Image.</span></div>
<div class="tile"><b>Aus dem Quellcode</b><span>Python 3.12 oder neuer, <code>git clone {GH}.git</code>, dann
<code>start_windows.bat</code> bzw. <code>start_mac.command</code>. Details im <a href="handbuch.html#installation">Handbuch</a>.</span></div></div>
</main>
<script>
(async () => {{
  const n = (x) => Number(x || 0).toLocaleString("de-CH");
  try {{
    const s = await (await fetch("summary.json", {{ cache: "no-store" }})).json();
    const rel = (s.rows || []).find((r) => !r.beta);
    if (rel) {{
      const v = rel.tag.replace(/^v/, ""), base = "{GH}/releases/download/" + rel.tag + "/";
      document.getElementById("dlWin").href = base + "TagStudio-" + v + "-Windows-Setup.exe";
      document.getElementById("dlMac").href = base + "TagStudio-" + v + "-macOS-Apple-Chip.dmg";
      document.getElementById("ver").innerHTML = 'Version <b>' + v + '</b> vom ' + rel.date + ' · <a href="' + rel.url + '">Versionshinweise</a>';
    }}
    const t = s.total || {{}}, h = s.history || {{}};
    document.getElementById("nums").innerHTML = '<div><b>' + n(t.installers) + '</b><span>Downloads gesamt</span></div>'
      + (h.days && h.days.length ? '<div><b>' + n(h.last30) + '</b><span>letzte 30 Tage</span></div>' : '')
      + '<div><b><a href="statistik.html">›</a></b><span><a href="statistik.html">Statistik</a></span></div>';
  }} catch (e) {{ /* Knöpfe führen dann zur Release-Seite */ }}
}})();
</script>"""
    return page("MarKusSXCH TagStudio – MP3-Werkzeugkasten für DJs", body, "index.html",
                "Kostenloser Werkzeugkasten für die MP3-Bibliothek von DJs: Tagger, Vergleich, Tag-Fixer, Einkäufe (Beatport), DJ-Set, Playlists – Windows & macOS.")


def _link(url: str, lang: str) -> str:
    """Links im Handbuch auf die Webseite bzw. GitHub umbiegen."""
    if re.match(r"^(https?:|mailto:|#)", url):
        return url
    path, _, frag = url.partition("#")
    frag = ("#" + frag) if frag else ""
    name = os.path.basename(path)
    if name == "HANDBUCH.md":
        return "handbuch.html" + frag
    if name == "HANDBUCH.en.md":
        return "manual.html" + frag
    if name in ("README.md", "README.en.md"):
        return "index.html"
    rel = os.path.normpath(os.path.join("docs", path)).replace(os.sep, "/")
    if rel.startswith("../"):
        rel = rel[3:]
    return f"{GH}/blob/main/{rel}{frag}"


def manual(md_path: str, lang: str) -> str:
    import markdown
    from markdown.extensions.toc import slugify_unicode
    text = open(md_path, encoding="utf-8").read()
    text = re.sub(r"\]\(([^)\s]+)\)", lambda m: "](" + _link(m.group(1), lang) + ")", text)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"slugify": slugify_unicode, "toc_depth": "2-3"}})
    body = md.convert(text)
    # Abschnitte je H2 für die Suche
    parts = re.split(r"(?=<h2 )", body)
    body = parts[0] + "".join(f'<section data-s="{i}">{p}</section>' for i, p in enumerate(parts[1:], 1))
    def toc_list(items):
        return "<ul>" + "".join(f'<li><a href="#{t["id"]}">{t["name"]}</a>{toc_list(t["children"]) if t.get("children") else ""}</li>'
                                for t in items) + "</ul>"
    tokens = md.toc_tokens
    flat = [t for top in tokens for t in (top.get("children") or [top])] if tokens and len(tokens) == 1 else tokens
    de = lang == "de"
    toc = (f'<aside class="toc" id="toc"><button class="btn alt toc-btn" onclick="this.parentNode.classList.toggle(\'open\')">'
           f'{"Inhalt" if de else "Contents"}</button><input id="q" type="search" placeholder="{"Im Handbuch suchen …" if de else "Search the manual …"}" '
           f'aria-label="{"Suche" if de else "Search"}"><p class="hit" id="hit"></p>{toc_list(flat)}</aside>')
    script = """<script>
(() => {
  const q = document.getElementById("q"), hit = document.getElementById("hit"), secs = [...document.querySelectorAll("article section")];
  const clean = () => document.querySelectorAll("article mark").forEach((m) => m.replaceWith(document.createTextNode(m.textContent)));
  const mark = (el, w) => { const it = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); const hits = []; let t;
    while ((t = it.nextNode())) { const i = t.data.toLowerCase().indexOf(w); if (i >= 0 && !t.parentNode.closest("mark")) hits.push([t, i]); }
    hits.slice(0, 200).forEach(([t, i]) => { const r = document.createRange(); r.setStart(t, i); r.setEnd(t, i + w.length);
      const m = document.createElement("mark"); r.surroundContents(m); }); };
  let tm = 0;
  q.addEventListener("input", () => { clearTimeout(tm); tm = setTimeout(() => {
    clean(); const w = q.value.trim().toLowerCase(); let n = 0;
    secs.forEach((s) => { const ok = !w || s.textContent.toLowerCase().includes(w); s.classList.toggle("hide", !ok); if (ok && w) { n++; mark(s, w); } });
    hit.textContent = w ? (n ? n + " ABSCHNITTE" : "KEINE") : "";
    if (w && n) { const f = document.querySelector("article section:not(.hide)"); if (f) f.scrollIntoView({ block: "start" }); }
  }, 180); });
})();
</script>""".replace("ABSCHNITTE", "Abschnitt(e) mit Treffern" if de else "section(s) with matches").replace("KEINE", "Keine Treffer" if de else "No matches")
    title = "TagStudio – Handbuch" if de else "TagStudio – Manual"
    return page(title, f'<main><div class="doc">{toc}<article>{body}</article></div></main>{script}',
                "handbuch.html" if de else "manual.html",
                "Handbuch zu MarKusSXCH TagStudio: alle Funktionen, Einstellungen und Tastenkürzel." if de else
                "Manual for MarKusSXCH TagStudio: all features, settings and shortcuts.", lang)


def stats_page() -> str:
    s = open(os.path.join(ROOT, ".github", "stats", "index.html"), encoding="utf-8").read()
    nav = ('<header class="top" style="position:sticky;top:0;z-index:5;border-bottom:1px solid var(--line);background:var(--bg)">'
           '<div style="max-width:960px;margin:0 auto;padding:10px 16px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">'
           '<a href="index.html" style="display:flex;align-items:center;gap:8px;font-weight:700;color:var(--fg)">'
           '<img src="img/icon.png" alt="" style="width:26px;height:26px;border-radius:7px">MarKusSXCH TagStudio</a>'
           '<span style="margin-left:auto;display:flex;gap:16px"><a href="index.html">Start</a><a href="handbuch.html">Handbuch</a></span>'
           '</div></header>')
    s = s.replace("<head>", '<head>\n<link rel="icon" href="img/icon.png">', 1)
    return s.replace("<body>\n<main>", "<body>\n" + nav + "\n<main>", 1)


def build(out: str) -> list:
    os.makedirs(os.path.join(out, "img"), exist_ok=True)
    shutil.copy(os.path.join(ROOT, "web", "icon.png"), os.path.join(out, "img", "icon.png"))
    shots = os.path.join(ROOT, "docs", "screenshots")
    for f in sorted(os.listdir(shots)) if os.path.isdir(shots) else []:
        if f.endswith(".png") and not f.startswith("_"):
            shutil.copy(os.path.join(shots, f), os.path.join(out, "img", f))
    sp = os.path.join(ROOT, "docs", "social-preview.png")
    if os.path.isfile(sp):
        shutil.copy(sp, os.path.join(out, "img", "social-preview.png"))
    files = {"index.html": landing(), "statistik.html": stats_page(),
             "handbuch.html": manual(os.path.join(ROOT, "docs", "HANDBUCH.md"), "de"),
             "manual.html": manual(os.path.join(ROOT, "docs", "HANDBUCH.en.md"), "en")}
    for name, text in files.items():
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    open(os.path.join(out, ".nojekyll"), "a").close()
    return sorted(files)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    print("Seiten:", ", ".join(build(sys.argv[1])))
