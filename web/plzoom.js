/* MarKusSXCH TagStudio – Lupe im Player (#224).
   Vergrösserter Ausschnitt der Wellenform um die Abspielposition von Player A, in hoher Auflösung direkt aus dem Audio
   berechnet (nur im Speicher, nichts gespeichert). Serato-Raster (oben) und eigene Analyse (unten) werden getrennt
   eingezeichnet, damit Abweichungen sichtbar werden (#223). Klick springt, Mausrad bzw. −/+ zoomt. Nur lesen.
   Nutzt $/call/esc/fmtTime aus app.js, PLAYER/plSetPref aus player.js, gridOf/gridBeatAt/gridTimeOfBeat aus player2.js. */
"use strict";

const PL_ZOOM = { on: false, span: 4, key: "", rate: 0, data: null, seq: 0, raf: 0, busy: false, err: "" };
const PL_ZOOM_SPANS = [1, 2, 4, 8, 16, 32];        // sichtbarer Ausschnitt in Sekunden
const PL_ZOOM_RATE = 11025;                        // reicht für scharfe Schläge, hält den Speicher klein (~2,6 MB/min)

function plZoomToggle(on = !PL_ZOOM.on, save = true) {
  PL_ZOOM.on = !!on;
  if (save) plSetPref("zoom", PL_ZOOM.on);
  $("#plZoomBtn")?.setAttribute("aria-pressed", String(PL_ZOOM.on));
  $("#plZoomBtn")?.classList.toggle("on", PL_ZOOM.on);
  plZoomBuild();
  if (PL_ZOOM.on) { plZoomLoad(); plZoomLoop(); } else { cancelAnimationFrame(PL_ZOOM.raf); PL_ZOOM.data = null; PL_ZOOM.key = ""; }
}

function plZoomOnLoad() { if (PL_ZOOM.on) plZoomLoad(); }

/** Audio des Titels einmal dekodieren und als Mono-Spur im Speicher halten */
async function plZoomLoad() {
  const i = PLAYER.info, key = i ? (i.wave_key || i.url) : "";
  if (!i || !i.url) { PL_ZOOM.data = null; PL_ZOOM.key = ""; plZoomDraw(); return; }
  if (key === PL_ZOOM.key && (PL_ZOOM.data || PL_ZOOM.busy)) return;
  const seq = ++PL_ZOOM.seq;
  PL_ZOOM.key = key; PL_ZOOM.data = null; PL_ZOOM.err = ""; PL_ZOOM.busy = true; plZoomDraw();
  try {
    const res = await fetch(i.url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const buf = await res.arrayBuffer();
    if (seq !== PL_ZOOM.seq) return;
    const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const audio = await new OAC(1, 1, PL_ZOOM_RATE).decodeAudioData(buf);
    if (seq !== PL_ZOOM.seq) return;
    const n = audio.length, mono = new Float32Array(n), ch = audio.numberOfChannels;
    for (let c = 0; c < ch; c++) { const d = audio.getChannelData(c); for (let k = 0; k < n; k++) mono[k] += d[k] / ch; }
    PL_ZOOM.data = mono; PL_ZOOM.rate = audio.sampleRate;
  } catch (e) {
    if (seq === PL_ZOOM.seq) PL_ZOOM.err = "Audio für die Lupe nicht lesbar (" + String(e.message || e) + ")";
  } finally {
    if (seq === PL_ZOOM.seq) { PL_ZOOM.busy = false; plZoomDraw(); }
  }
}

function plZoomPlace(box) {
  const pl = $("#player"), r = pl ? pl.getBoundingClientRect() : null;
  if (!r || !r.height) { box.style.top = ""; box.style.bottom = "72px"; return; }
  if (r.top > innerHeight / 2) { box.style.top = ""; box.style.bottom = `${Math.max(8, innerHeight - r.top + 8)}px`; }
  else { box.style.bottom = ""; box.style.top = `${r.bottom + 8}px`; }
}

function plZoomBuild() {
  let box = $("#plZoom");
  if (!PL_ZOOM.on || (typeof DET !== "undefined" && DET.on)) { if (box) box.hidden = true; return; }
  if (!box) {
    box = document.createElement("div");
    box.id = "plZoom"; box.className = "pl-zoom"; box.setAttribute("role", "dialog"); box.setAttribute("aria-label", "Lupe");
    box.innerHTML = `<div class="zm-head"><span class="zm-t">Lupe</span><span class="zm-leg" id="zmLeg"></span>
      <button class="zm-b" data-z="-1" title="Mehr zeigen (herauszoomen)" aria-label="Herauszoomen">−</button>
      <span class="zm-span" id="zmSpan"></span>
      <button class="zm-b" data-z="1" title="Weniger zeigen (hineinzoomen)" aria-label="Hineinzoomen">+</button>
      <button class="zm-x" title="Lupe schliessen" aria-label="Lupe schliessen">×</button></div>
      <canvas id="zmCanvas" title="Klick: hierhin springen · Mausrad: zoomen"></canvas><div class="zm-msg" id="zmMsg"></div>`;
    document.body.appendChild(box);
    box.addEventListener("click", (e) => {
      if (e.target.closest(".zm-x")) { plZoomToggle(false); return; }
      const b = e.target.closest("[data-z]");
      if (b) { plZoomStep(+b.dataset.z); return; }
      if (e.target.id === "zmCanvas") plZoomSeek(e);
    });
    box.addEventListener("wheel", (e) => { e.preventDefault(); plZoomStep(e.deltaY < 0 ? 1 : -1); }, { passive: false });
  }
  box.hidden = false;
  plZoomPlace(box);
  plZoomDraw();
}

function plZoomStep(dir) {
  const k = PL_ZOOM_SPANS.indexOf(PL_ZOOM.span), n = Math.max(0, Math.min(PL_ZOOM_SPANS.length - 1, (k < 0 ? 2 : k) - dir));
  PL_ZOOM.span = PL_ZOOM_SPANS[n];
  plZoomDraw();
}

function plZoomSeek(e) {
  const a = PLAYER.audio, cv = $("#zmCanvas");
  if (!a || !a.src || !cv) return;
  const r = cv.getBoundingClientRect(), t = (a.currentTime || 0) + ((e.clientX - r.left) / r.width - 0.5) * PL_ZOOM.span;
  a.currentTime = Math.max(0, Math.min((a.duration || 0) - 0.05, t));
  plZoomDraw();
}

/** eigene Analyse als einfaches Raster (konstantes Tempo) – aus dem Cache bzw. dem Tag */
function plZoomOwn(info) {
  const b = info && info.wave && info.wave.beat;
  if (b && b.bpm > 0) return { bpm: +b.bpm, first: +b.first || 0 };
  const g = info && info.grid;
  if (g && g.analysed && g.bpm > 0) return { bpm: +g.bpm, first: +g.first || 0 };
  return null;
}

function plZoomLoop() {
  cancelAnimationFrame(PL_ZOOM.raf);
  const tick = () => {
    if (!PL_ZOOM.on) return;
    if (PLAYER.audio && !PLAYER.audio.paused) plZoomDraw();
    PL_ZOOM.raf = requestAnimationFrame(tick);
  };
  PL_ZOOM.raf = requestAnimationFrame(tick);
}

function plZoomDraw() {
  const box = $("#plZoom"), cv = $("#zmCanvas");
  if (!PL_ZOOM.on || !box || box.hidden || !cv) return;
  const info = PLAYER.info, a = PLAYER.audio;
  $("#zmSpan").textContent = `${PL_ZOOM.span} s`;
  const msg = !info ? "Kein Titel in Player A." : PL_ZOOM.err ? PL_ZOOM.err : (!PL_ZOOM.data ? "Audio wird gelesen …" : "");
  $("#zmMsg").textContent = msg;
  const dpr = window.devicePixelRatio || 1, W = Math.max(1, Math.round(cv.clientWidth * dpr)), H = Math.max(1, Math.round(cv.clientHeight * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const g = cv.getContext("2d"), st = getComputedStyle(document.documentElement);
  const acc = st.getPropertyValue("--acc").trim() || "#7c5cff", fg = st.getPropertyValue("--fg").trim() || "#fff";
  const dim = st.getPropertyValue("--faint").trim() || "#888";
  g.clearRect(0, 0, W, H);
  const sg = gridOf(info), own = plZoomOwn(info), serato = !!(sg && sg.exact);
  $("#zmLeg").innerHTML = [
    sg ? `<span class="zl-s" title="Raster oben">${esc(serato ? "Serato" : sg.source || "Raster")} ${(+sg.bpm).toFixed(2)} BPM</span>` : "",
    own && serato ? `<span class="zl-o" title="Raster unten">Analyse ${own.bpm.toFixed(2)} BPM</span>` : "",
  ].join("");
  if (!info) return;
  const t = (a && a.currentTime) || 0, span = PL_ZOOM.span, t0 = t - span / 2, mid = H / 2;
  const x = (tt) => ((tt - t0) / span) * W;
  // Wellenform: Spitzenwert je Pixelspalte
  const d = PL_ZOOM.data;
  if (d) {
    const rate = PL_ZOOM.rate, per = (span * rate) / W;
    let top = 0.05;
    const col = new Float32Array(W);
    for (let px = 0; px < W; px++) {
      const s0 = Math.floor((t0 * rate) + px * per), s1 = Math.max(s0 + 1, Math.floor(t0 * rate + (px + 1) * per));
      let pk = 0;
      for (let s = Math.max(0, s0); s < s1 && s < d.length; s++) { const v = Math.abs(d[s]); if (v > pk) pk = v; }
      col[px] = pk; if (pk > top) top = pk;
    }
    g.fillStyle = dim; g.globalAlpha = 0.55;
    for (let px = 0; px < W; px++) { const h = Math.max(0.5, (col[px] / top) * (H * 0.46)); g.fillRect(px, mid - h, 1, h * 2); }
    g.globalAlpha = 1;
  }
  // Raster: Serato bzw. massgebendes Raster oben, eigene Analyse unten
  const lines = (beatOf, timeOf, y0, y1, color, alpha) => {
    const b0 = Math.ceil(beatOf(Math.max(0, t0))), b1 = Math.floor(beatOf(t0 + span));
    g.fillStyle = color;
    for (let b = b0; b <= b1 && b - b0 < 400; b++) {
      const xx = Math.round(x(timeOf(b)));
      const strong = ((b % 4) + 4) % 4 === 0;
      g.globalAlpha = strong ? alpha : alpha * 0.6;
      g.fillRect(xx, y0, Math.max(1, Math.round(dpr * (strong ? 2 : 1))), y1 - y0);
    }
    g.globalAlpha = 1;
  };
  if (sg) lines((tt) => gridBeatAt(sg, tt), (b) => gridTimeOfBeat(sg, b), 0, own && serato ? mid : H, acc, 0.95);
  if (own && serato) {
    const p = 60 / own.bpm;
    lines((tt) => (tt - own.first) / p, (b) => own.first + b * p, mid, H, "#F5A623", 0.95);
  }
  // Abspielposition
  g.fillStyle = fg; g.globalAlpha = 0.9;
  g.fillRect(Math.round(W / 2), 0, Math.max(1, Math.round(dpr)), H);
  g.globalAlpha = 1;
}

(function plZoomInit() {
  const btn = $("#plZoomBtn");
  if (btn) btn.addEventListener("click", () => plZoomToggle());
  const hook = () => {
    if (!PLAYER.audio || PLAYER.audio.__zm) return;
    PLAYER.audio.__zm = true;
    PLAYER.audio.addEventListener("seeked", () => { if (PL_ZOOM.on) plZoomDraw(); });
  };
  hook();
  setTimeout(hook, 500);
  addEventListener("resize", () => { const b = $("#plZoom"); if (b && !b.hidden) { plZoomPlace(b); plZoomDraw(); } });
})();
