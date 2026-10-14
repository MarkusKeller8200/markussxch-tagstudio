/* #181: Beatgrid-Diagnose. Vierer-Akzent = Rasterzählung, kein geprüfter Downbeat. */
"use strict";
const PL_METRO = {deck:null, ctx:null, timer:null, nodes:new Set(), generation:0,
  audio:null, info:null, next:null, media:null, clock:null, rate:1, volume:80};

/** #181: gemeinsamer Metronompegel (0–100 %), unabhängig von der Track-Lautstärke. */
function plMetroVolume(value) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.max(0, Math.min(100, Math.round(n))) : 80;
}
function plMetroPeak(accent, volume = PL_METRO.volume) {
  return (accent ? 0.78 : 0.68) * plMetroVolume(volume) / 100;
}
function plMetroSetVolume(value) {
  PL_METRO.volume = plMetroVolume(value);
  plMetroUi("A"); plMetroUi("B");
  return PL_METRO.volume;
}

function plMetroBeat(grid, time, rate, beat) {
  if (!grid || !Number.isFinite(time) || !(rate > 0)) return null;
  const pos = gridTimeOfBeat(grid, beat);
  return Number.isFinite(pos) ? {beat, delay:(pos-time)/rate, accent:beat % 4 === 0} : null;
}
/** Quelle der Klicks: beim Crossfade bis zu dessen Ende alter Track,
 * obwohl PLAYER.audio/info schon während der Ladephase auf den neuen zeigen.
 * Player B bleibt eine separate, unabhängige Metronom-Quelle.
 */
function plMetroSource(deck) {
  if (deck === "B") return { audio: DECKB.audio, info: DECKB.info };
  const fading = PLAYER.fade;
  return fading && fading.old
    ? { audio: fading.old, info: fading.oldInfo }
    : { audio: PLAYER.audio, info: PLAYER.info };
}

function plMetroClear() {
  for (const osc of PL_METRO.nodes) try { osc.stop(); } catch (_) { /* bereits gestoppt */ }
  PL_METRO.nodes.clear();
  PL_METRO.next = null; PL_METRO.media = null; PL_METRO.clock = null;
}
function plMetroUi(deck) {
  const b = document.getElementById(deck === "B" ? "dbMetro" : "plMetro");
  if (!b) return;
  const { info } = plMetroSource(deck), g = gridOf(info);
  const active = PL_METRO.deck === deck;
  // Eingeschaltet auch ohne Grid bedienbar halten (Analyse/Trackwechsel).
  b.disabled = !g && !active;
  b.classList.toggle("on", active);
  b.setAttribute("aria-pressed", String(active));
  const fadeHint = deck === "A" && PLAYER.fade && PLAYER.fade.old
    ? " · Überblendung: Raster des auslaufenden Tracks" : "";
  b.title = `Beatgrid-Metronom Player ${deck}: ${g ? (g.source + " · " + g.bpm + " BPM") : "Beatgrid noch nicht verfügbar"}${fadeHint} · Lautstärke ${PL_METRO.volume}% (im Player-Menü einstellbar). Vierer-Akzent ist kein geprüfter Downbeat.`;
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
  const ctx = PL_METRO.ctx, peak = plMetroPeak(accent);
  if (!ctx || !peak) return;                        // 0 % = wirklich stumm
  const o = ctx.createOscillator(), gain = ctx.createGain();
  // Rechteck mit Obertönen statt kurzem Sinuston: in lauter Musik klarer hörbar.
  // Max. Amplitude unter 1; bei Kopfhörern zunächst mit kleiner Lautstärke beginnen.
  o.type = "square";
  o.frequency.setValueAtTime(accent ? 2100 : 1600, when);
  gain.gain.setValueAtTime(0.0001, when);
  gain.gain.exponentialRampToValueAtTime(peak, when + 0.002);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.065);
  o.connect(gain); gain.connect(ctx.destination);
  PL_METRO.nodes.add(o);
  o.onended = () => { PL_METRO.nodes.delete(o); o.disconnect(); gain.disconnect(); };
  o.start(when); o.stop(when + 0.07);
}
function plMetroTick() {
  const m = PL_METRO;
  if (!m.ctx || !m.deck) return;
  const { audio: a, info } = plMetroSource(m.deck), g = gridOf(info);
  // Kein Raster beim neuen Track: weiter EINgeschaltet bleiben und auf
  // Analyse warten, ohne noch Klicks des vorherigen Titels auszugeben.
  if (!a || !a.src || !g) {
    plMetroClear();
    m.audio = a || null; m.info = info || null;
    plMetroUi(m.deck);
    return;
  }
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
/** Pegel sofort probehören und erst bei Übernehmen dauerhaft speichern. */
async function plMetroVolumeDialog() {
  const before = PL_METRO.volume;
  const result = await modal({
    title: "Metronom-Lautstärke",
    html: `<label class="field">Lautstärke: <strong id="plMetroVolText">${before} %</strong>
      <input id="plMetroVolRange" type="range" min="0" max="100" step="5"
        value="${before}" style="width:100%" aria-label="Metronom-Lautstärke in Prozent">
    </label>
    <p class="muted sm">Wirkt sofort während das Metronom läuft – gemeinsam für Player A und B.
      0 % ist stumm, 100 % der höchste Pegel. Bitte bei Kopfhörern leise beginnen.
      Dieser Regler beeinflusst die Track-Lautstärke nicht.</p>`,
    buttons: [{label: "Abbrechen", value: null}, {label: "Speichern", value: "save", primary: true}],
    onMount: (body) => {
      const input = $("#plMetroVolRange", body);
      input.addEventListener("input", () => {
        const value = plMetroSetVolume(+input.value);
        $("#plMetroVolText", body).textContent = value + " %";
      });
    },
    collect: (body, action) => action === "save"
      ? {volume: +$("#plMetroVolRange", body).value} : null,
  });
  if (!result) { plMetroSetVolume(before); return; }
  plSetPref("metro_volume", result.volume);
  toast(`Metronom-Lautstärke ${result.volume}% gespeichert.`);
}

async function plMetroToggle(deck = "A") {
  if (PL_METRO.deck === deck) { plMetroStop(); return; }
  const { info } = plMetroSource(deck), g = gridOf(info);
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
