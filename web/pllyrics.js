/* MarKusSXCH TagStudio – Liedtext im Player (#215).
   Zeigt den Liedtext des Titels in Player A: synchronisiert (SYLT im MP3 oder .lrc daneben) mit hervorgehobener,
   mitlaufender Zeile – Klick auf eine Zeile springt dorthin; sonst den normalen Text (USLT). Nur lesen.
   Nutzt call/esc/toast aus app.js und PLAYER/plSetPref aus player.js. */
"use strict";

const PL_LY = { on: false, data: null, key: "", idx: -2, seq: 0 };

function plLyricsTarget() { return PLAYER.info ? `${PLAYER.kind}|${PLAYER.ref}` : ""; }

/** Ein-/ausschalten (gemerkt in den Player-Einstellungen) */
function plLyricsToggle(on = !PL_LY.on, save = true) {
  PL_LY.on = !!on;
  if (save) plSetPref("lyrics", PL_LY.on);
  $("#plLyricsBtn")?.setAttribute("aria-pressed", String(PL_LY.on));
  $("#plLyricsBtn")?.classList.toggle("on", PL_LY.on);
  plLyricsRender(true);
  if (PL_LY.on) plLyricsLoad();
}

/** nach jedem Titelwechsel in Player A (aus plLoad) */
function plLyricsOnLoad() { if (PL_LY.on) plLyricsLoad(); }

async function plLyricsLoad() {
  const key = plLyricsTarget();
  if (!key) { PL_LY.data = null; PL_LY.key = ""; plLyricsRender(true); return; }
  if (key === PL_LY.key && PL_LY.data) { plLyricsRender(true); return; }
  const seq = ++PL_LY.seq;
  PL_LY.key = key; PL_LY.data = null; plLyricsRender(true);
  let d;
  try { d = await call("media_lyrics", PLAYER.kind, PLAYER.ref); } catch (e) { d = { source: "", synced: [], plain: "", error: String(e.message || e) }; }
  if (seq !== PL_LY.seq) return;                                 // inzwischen anderer Titel
  PL_LY.data = d; PL_LY.idx = -2;
  plLyricsRender(true);
}

/** aktuelle Zeile: letzte mit Zeit ≤ Position (Binärsuche) */
function plLyricsIndex(lines, ms) {
  let lo = 0, hi = lines.length - 1, r = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (lines[m][0] <= ms) { r = m; lo = m + 1; } else hi = m - 1; }
  return r;
}

function plLyricsPlace(box) {
  const pl = $("#player"), r = pl ? pl.getBoundingClientRect() : null;
  if (!r || !r.height) { box.style.top = ""; box.style.bottom = "72px"; return; }
  if (r.top > innerHeight / 2) { box.style.top = ""; box.style.bottom = `${Math.max(8, innerHeight - r.top + 8)}px`; }
  else { box.style.bottom = ""; box.style.top = `${r.bottom + 8}px`; }
}

/** Fenster aufbauen (full) bzw. nur die aktuelle Zeile nachführen */
function plLyricsRender(full = false) {
  let box = $("#plLyrics");
  if (!PL_LY.on || (typeof DET !== "undefined" && DET.on)) { if (box) box.hidden = true; return; }
  if (!box) {
    box = document.createElement("div");
    box.id = "plLyrics"; box.className = "pl-lyrics"; box.setAttribute("role", "dialog"); box.setAttribute("aria-label", "Liedtext");
    document.body.appendChild(box);
    box.addEventListener("click", (e) => {
      if (e.target.closest(".ly-x")) { plLyricsToggle(false); return; }
      const ln = e.target.closest("[data-ms]");
      if (ln && PLAYER.audio && PLAYER.audio.src) { PLAYER.audio.currentTime = (+ln.dataset.ms) / 1000; plLyricsRender(); }
    });
  }
  box.hidden = false;
  if (full) {
    plLyricsPlace(box);
    const d = PL_LY.data, i = PLAYER.info;
    const title = i ? (i.title || i.name || "") : "";
    const head = `<div class="ly-head"><span class="ly-t" title="${esc(title)}">${esc(title || "Liedtext")}</span>
      ${d && d.source ? `<span class="ly-src" title="Quelle des Liedtexts">${esc(d.source === ".lrc" ? ".lrc-Datei" : d.source)}</span>` : ""}
      <button class="ly-x" title="Liedtext schliessen" aria-label="Liedtext schliessen">×</button></div>`;
    let body;
    if (!i) body = '<div class="ly-empty">Kein Titel in Player A.</div>';
    else if (!d) body = '<div class="ly-empty">Lade …</div>';
    else if (d.error) body = `<div class="ly-empty">${esc(d.error)}</div>`;
    else if (d.synced && d.synced.length) {
      body = `<div class="ly-lines">${d.synced.map(([ms, t], k) => `<div class="ly-l${t ? "" : " gap"}" data-k="${k}" data-ms="${ms}" title="${fmtTime(ms / 1000)} – Klick: hierhin springen">${t ? esc(t) : "♪"}</div>`).join("")}</div>`;
    } else if (d.plain) body = `<div class="ly-plain">${esc(d.plain)}</div><div class="ly-note">Nicht synchronisiert – mit dem Plugin „Liedtexte“ lässt sich ein Text mit Zeitstempeln holen.</div>`;
    else body = '<div class="ly-empty">Kein Liedtext gespeichert. Tagger › Plugins › „Liedtexte holen …“ (LRCLIB).</div>';
    box.innerHTML = head + body;
    PL_LY.idx = -2;
  }
  const d = PL_LY.data;
  if (!d || !d.synced || !d.synced.length || !PLAYER.audio) return;
  const k = plLyricsIndex(d.synced, (PLAYER.audio.currentTime || 0) * 1000 + 150);   // 150 ms früher: liest sich natürlicher
  if (k === PL_LY.idx) return;
  PL_LY.idx = k;
  box.querySelector(".ly-l.on")?.classList.remove("on");
  const el = k >= 0 ? box.querySelector(`.ly-l[data-k="${k}"]`) : null;
  if (el) {
    el.classList.add("on");
    const list = box.querySelector(".ly-lines");
    if (list && !list.matches(":hover")) list.scrollTo({ top: el.offsetTop - list.clientHeight / 2 + el.clientHeight / 2, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }
}

(function plLyricsInit() {
  const btn = $("#plLyricsBtn");
  if (btn) btn.addEventListener("click", () => plLyricsToggle());
  const hook = () => {
    if (!PLAYER.audio || PLAYER.audio.__ly) return;
    PLAYER.audio.__ly = true;
    PLAYER.audio.addEventListener("timeupdate", () => { if (PL_LY.on) plLyricsRender(); });
    PLAYER.audio.addEventListener("seeked", () => { if (PL_LY.on) plLyricsRender(); });
  };
  hook();
  setTimeout(hook, 500);
  addEventListener("resize", () => { const b = $("#plLyrics"); if (b && !b.hidden) plLyricsPlace(b); });
})();
