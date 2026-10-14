/* #181: Beatgrid-Diagnose. Vierer-Akzent = Rasterzählung, kein geprüfter Downbeat. */
"use strict";
const PL_METRO = {deck:null, ctx:null, timer:null, nodes:new Set(), generation:0,
  audio:null, info:null, next:null, media:null, clock:null, rate:1};

function plMetroBeat(grid, time, rate, beat) {
  if (!grid || !Number.isFinite(time) || !(rate > 0)) return null;
  const pos = gridTimeOfBeat(grid, beat);
  return Number.isFinite(pos) ? {beat, delay:(pos-time)/rate, accent:beat % 4 === 0} : null;
}
function plMetroClear() {
  for (const osc of PL_METRO.nodes) try { osc.stop(); } catch (_) { /* bereits gestoppt */ }
  PL_METRO.nodes.clear();
  PL_METRO.next = null; PL_METRO.media = null; PL_METRO.clock = null;
}
function plMetroUi(deck) {
  const b = document.getElementById(deck === "B" ? "dbMetro" : "plMetro");
  if (!b) return;
  const info = deck === "B" ? DECKB.info : PLAYER.info, g = gridOf(info);
  const active = PL_METRO.deck === deck;
  b.disabled = !g; b.classList.toggle("on", active);
  b.setAttribute("aria-pressed", String(active));
  b.title = `Beatgrid-Metronom Player ${deck}: ${g ? (g.source + " · " + g.bpm + " BPM") : "kein Beatgrid"} – Vierer-Akzent ist kein geprüfter Downbeat`;
}
function plMetroStop() {
  const m = PL_METRO;
  m.generation++;
  clearInterval(m.timer); m.timer = null;
  plMetroClear();
  const ctx = m.ctx; m.ctx = null; m.deck = null; m.audio = null; m.info = null;
  if (ctx) ctx.close().catch(() => {});
  plMetroUi("A"); plMetroUi("B");
}
function plMetroClick(when, accent) {
  const ctx = PL_METRO.ctx, o = ctx.createOscillator(), gain = ctx.createGain();
  o.type = "sine";
  o.frequency.setValueAtTime(accent ? 1320 : 880, when);
  gain.gain.setValueAtTime(0.0001, when);
  gain.gain.exponentialRampToValueAtTime(accent ? 0.12 : 0.07, when + 0.003);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.045);
  o.connect(gain); gain.connect(ctx.destination);
  PL_METRO.nodes.add(o);
  o.onended = () => { PL_METRO.nodes.delete(o); o.disconnect(); gain.disconnect(); };
  o.start(when); o.stop(when + 0.05);
}
function plMetroTick() {
  const m = PL_METRO;
  if (!m.ctx || !m.deck) return;
  const a = m.deck === "B" ? DECKB.audio : PLAYER.audio;
  const info = m.deck === "B" ? DECKB.info : PLAYER.info, g = gridOf(info);
  if (!a || !a.src || !g) { plMetroStop(); return; }
  if (a !== m.audio || info !== m.info) {
    plMetroClear(); m.audio = a; m.info = info; plMetroUi(m.deck);
  }
  if (a.paused || a.seeking || a.readyState < 2) { plMetroClear(); return; }
  const t = a.currentTime, now = performance.now(), rate = a.playbackRate || 1;
  if (m.clock !== null && Math.abs(t - (m.media + (now - m.clock) * m.rate / 1000)) > 0.25) plMetroClear();
  const beat = gridBeatAt(g, t);
  if (!Number.isFinite(beat)) { plMetroStop(); return; }
  let next = m.next === null ? Math.ceil(beat + 0.0001) : m.next;
  if (next < beat - 0.02) { plMetroClear(); next = Math.ceil(beat + 0.0001); }
  for (let i = 0; i < 3; i++) {
    const tick = plMetroBeat(g, t, rate, next);
    if (!tick || tick.delay > 0.12) break;
    if (tick.delay >= -0.025) plMetroClick(m.ctx.currentTime + Math.max(0.004, tick.delay), tick.accent);
    next++;
  }
  m.next = next; m.media = t; m.clock = now; m.rate = rate;
}
async function plMetroToggle(deck = "A") {
  if (PL_METRO.deck === deck) { plMetroStop(); return; }
  const info = deck === "B" ? DECKB.info : PLAYER.info, g = gridOf(info);
  if (!g) { toast("Kein Beatgrid vorhanden – Metronom nicht verfügbar."); return; }
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) { toast("Web Audio ist für das Metronom nicht verfügbar."); return; }
  plMetroStop();
  const gen = PL_METRO.generation, ctx = new Ctx();
  try {
    await ctx.resume();
    if (gen !== PL_METRO.generation) { await ctx.close(); return; }
    if (deck === "B" && DECKB.sink && typeof ctx.setSinkId === "function") {
      try { await ctx.setSinkId(DECKB.sink); }
      catch (_) { toast("Metronom spielt über das Standard-Ausgabegerät."); }
    }
    if (gen !== PL_METRO.generation) { await ctx.close(); return; }
    PL_METRO.ctx = ctx; PL_METRO.deck = deck;
    PL_METRO.timer = setInterval(plMetroTick, 25);
    plMetroUi("A"); plMetroUi("B"); plMetroTick();
    toast(`Beatgrid-Metronom ${deck}: ${g.source || "Raster"}, ${g.bpm} BPM (Vierer-Akzent nicht verifiziert).`);
  } catch (e) { ctx.close().catch(() => {}); toast("Metronom nicht verfügbar: " + (e.message || e)); }
}
if (typeof window.addEventListener === "function") window.addEventListener("beforeunload", plMetroStop);
