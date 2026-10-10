/* MarKusSXCH TagStudio – Player-Erweiterungen 3.4.0:
   #94 Überblenden zum nächsten Titel · #68 Player oben (einklappbar) · #67 Player B (zweiter Player, eigenes Ausgabegerät)
   #69 Abdocken (eigenes Fenster: zeigt und steuert den Player; die Wiedergabe bleibt in diesem Fenster und läuft weiter)
   Kontextmenü auf Titeln: in Player A/B laden. */
"use strict";

const PL2 = { layout: "bottom", collapsed: false, deck2: false, window: null, ready: false };
const DECKB = { audio: null, info: null, kind: null, ref: null, seq: 0, sink: "", startAt: "0", repeat: false, ab: null, loop: null, raf: 0 };
const DET = { on: false, timer: 0, seq: 0, popup: null, t0: 0, waveKey: { A: null, B: null }, last: "", busy: false };

// ====================================================================== #94 Überblenden
/** Beim Abspielen prüfen, ob es Zeit zum Überblenden ist (aus dem timeupdate des aktiven Elements). */
function plXfadeCheck() {
  const a = PLAYER.audio, x = PLAYER.xfade;
  if (!x || PLAYER.fade || PLAYER.loading || a.paused || !a.src || PLAYER.repeat || PLAYER.loop || PLAYER.ab || !PLAYER.follow) return;
  if (PLAYER.kind !== "tag") return;
  const dj = S.module === "djset" && typeof djNextTag === "function";
  if (!dj && (S.module !== "tagger" || !TG.order.length)) return;
  const dur = a.duration;
  if (!isFinite(dur) || dur < x + 2) return;
  let at = dur - x;
  if (PLAYER.xfadeAfter > 0) at = Math.min(at, (PLAYER.playFrom || 0) + PLAYER.xfadeAfter);   // Durchhören: nach x Sekunden
  if (a.currentTime < at || a.currentTime > dur - 0.3) return;
  if (dj) { const n = djNextTag(); if (n !== null) plCrossfade(n); return; }     // #3: Set-Reihenfolge
  const k = TG.order.indexOf(TG.anchor);
  if (k < 0 || k >= TG.order.length - 1) return;
  plCrossfade(TG.order[k + 1]);
}

/** Zum Titel i überblenden: neues Element lädt und blendet ein, das alte gleichmässig aus (gleiche Leistung, sin/cos). */
/** BPM-Zahl aus dem Tag (z. B. „124“, „123,5“) oder 0 */
function bpmOf(info) { const b = parseFloat(String((info && info.bpm) || "").replace(",", ".")); return b > 30 && b < 400 ? b : 0; }

/** #102: Tempo-Faktor, damit der nächste Titel im Tempo des laufenden läuft (halbes/doppeltes Tempo erkannt). 1 = nicht angleichen. */
function plTempoRatio(bpmFrom, bpmTo) {
  if (!bpmFrom || !bpmTo) return 1;
  let r = bpmFrom / bpmTo;
  if (r > 1.5) r /= 2; else if (r < 0.75) r *= 2;
  return r >= 0.9 && r <= 1.1 ? r : 1;           // höchstens ±10 % (wie ein Pitch-Regler)
}

/** Tempo des aktiven Titels in sec Sekunden gleichmässig auf 1 (eigenes BPM) zurückführen */
function plTempoReturn(sec) {
  plTempoStop(false);
  const a = PLAYER.audio, r0 = a.playbackRate;
  if (Math.abs(r0 - 1) < 0.0005) return;
  if (!sec) { a.playbackRate = 1; plRender(); return; }
  const t0 = performance.now();
  PLAYER.tempo = { timer: setInterval(() => {
    if (PLAYER.audio !== a) return plTempoStop(false);
    const g = Math.min(1, (performance.now() - t0) / (sec * 1000));
    a.playbackRate = r0 + (1 - r0) * g;
    if (g >= 1) { plTempoStop(false); plRender(); }
  }, 100) };
}

function plTempoStop(reset = true) {
  if (PLAYER.tempo) { clearInterval(PLAYER.tempo.timer); PLAYER.tempo = null; }
  if (reset && PLAYER.audio) PLAYER.audio.playbackRate = 1;
}

async function plCrossfade(i) {
  const old = PLAYER.audio, nu = PLAYER.spare, D = PLAYER.xfade * 1000;
  const bpmFrom = bpmOf(PLAYER.info) * (old.playbackRate || 1);
  PLAYER.fade = { old, timer: 0 };
  PLAYER.spare = old;
  PLAYER.audio = nu;
  nu.muted = old.muted;
  nu.volume = 0;
  if (S.module === "djset" && typeof djSelectTag === "function") djSelectTag(i);   // #3
  else {
    await tgSelect(i, {});            // Player B / „Folgen“: nu ist noch leer → kein Laden über playerFollow
    TG.anchor = i;
    tgScrollTo(i);
  }
  await plLoad({ kind: "tag", ref: i }, true, null, PLAYER.xfadeStart === "start" ? null : PLAYER.xfadeStart, true);
  const f = PLAYER.fade;
  if (!f || f.old !== old) return;
  const ratio = PLAYER.xfadeSync ? plTempoRatio(bpmFrom, bpmOf(PLAYER.info)) : 1;
  if (ratio !== 1) { nu.preservesPitch = true; nu.playbackRate = ratio; }      // Tonhöhe bleibt
  f.ratio = ratio;
  const t0 = performance.now();
  f.timer = setInterval(() => {
    if (PLAYER.fade !== f) return clearInterval(f.timer);
    const g = Math.min(1, (performance.now() - t0) / D), v = PLAYER.vol;
    PLAYER.audio.volume = v * Math.sin((g * Math.PI) / 2);
    old.volume = v * Math.cos((g * Math.PI) / 2);
    if (g >= 1) { plFadeStop(); if (f.ratio !== 1) plTempoReturn(PLAYER.xfadeReturn); }
  }, 40);
}

/** Überblenden beenden (fertig oder abgebrochen durch einen anderen Titel): altes Element stoppen. */
function plFadeStop() {
  const f = PLAYER.fade;
  if (!f) return;
  clearInterval(f.timer);
  PLAYER.fade = null;
  f.old.pause();
  f.old.removeAttribute("src");
  f.old.load();
  f.old.volume = PLAYER.vol;
  PLAYER.audio.volume = PLAYER.vol;
  plRender();
}

// ====================================================================== #68 Player oben
/** Player B gibt es nur mit „Player oben“ – dort steht er unter Player A. */
function pl2B() { return PL2.deck2 && PL2.layout === "top"; }

function pl2Layout() {
  if (!PL2.ready) return;
  const top = PL2.layout === "top", b = pl2B();
  const p = $("#player"), box = $("#plTop"), db = $("#deckB");
  if (top && p.parentElement !== $("#plTopSlot")) $("#plTopSlot").appendChild(p);
  else if (!top && p.parentElement !== PL2.home) PL2.home.insertBefore(p, $("#undoBtn"));
  if (db.parentElement !== box) box.appendChild(db);           // B immer unter A
  box.hidden = !top || DET.on;                                 // abgedockt: A und B im eigenen Fenster (#101)
  box.classList.toggle("collapsed", top && PL2.collapsed);
  box.classList.toggle("two", b);
  const fold = $("#plTopFold"), lbl = PL2.collapsed ? "Player-Leiste ausklappen (Shift+P)" : "Player-Leiste einklappen (Shift+P)";
  fold.title = lbl; fold.setAttribute("aria-label", lbl); fold.setAttribute("aria-expanded", String(!PL2.collapsed));
  db.hidden = !b;
  if (!b) { if (DECKB.audio && !DECKB.audio.paused) DECKB.audio.pause(); PLAYER.target = "A"; }
  document.body.classList.toggle("pl-at-top", top);
  document.body.classList.toggle("pl-detached", DET.on);
  $("#plDockChip").hidden = !DET.on;
  const dt = $("#plDetach"), dl = DET.on ? "Player andocken" : "Player abdocken (eigenes Fenster)";
  dt.title = dl; dt.setAttribute("aria-label", dl);
  plTagSync();
  requestAnimationFrame(() => { plCues(); plDrawWave(); dbCues(); dbRender(); });
}

function plTopFold(on = !PL2.collapsed) {
  plSetPref("top_collapsed", !!on);
}

/** Beschriftung A/B ganz vorne: hervorgehoben = Ziel von Markierung, Leertaste, Doppelklick und Tasten */
function plTagSync() {
  const b = pl2B();
  [["#plTag", "A"], ["#dbTag", "B"]].forEach(([id, v]) => {
    const el = $(id), on = PLAYER.target === v;
    el.classList.toggle("on", on && b);
    el.setAttribute("aria-pressed", String(on));
  });
  $("#plTag").hidden = !b;
  $("#player").classList.toggle("target", b && PLAYER.target === "A");
  $("#deckB").classList.toggle("target", b && PLAYER.target === "B");
}

function dbTargetSet(v) {
  if (!pl2B()) v = "A";
  if (PLAYER.target === v) return;
  plSetPref("deck_target", v);
  toast(v === "B" ? "Markierung, Leertaste, Doppelklick und Tasten wirken jetzt auf Player B." : "Markierung, Leertaste, Doppelklick und Tasten wirken auf Player A.");
}

// ====================================================================== #67 Player B
const DB_START = () => DECKB.startAt || "0";

async function dbLoad(t, autoplay = true, keepTime = null) {
  if (!t) { toast(S.module === "tagger" ? "Erst einen Titel markieren." : "Erst ein Dateipaar wählen."); return; }
  if (PL2.layout !== "top") { toast("Player B gibt es nur mit „Player oben“ (Einstellungen → Player → Position)."); return; }
  if (!PL2.deck2) plSetPref("deck2", true);
  const seq = ++DECKB.seq;
  let info;
  try { info = await call("media_url", t.kind, t.ref); } catch (e) { toast(String(e.message || e)); return; }
  if (seq !== DECKB.seq) return;
  DECKB.info = info; DECKB.kind = t.kind; DECKB.ref = t.ref;
  if (keepTime === null) dbABClear(true);
  const a = DECKB.audio, dur = info.duration || 0, firstCue = (info.cues || []).find((c) => c.pos > 0.05), sm = DB_START();
  const start = keepTime !== null ? keepTime : sm === "30" ? dur * 0.3 : sm === "60" ? Math.min(60, dur * 0.5) : sm === "cue" ? (firstCue ? firstCue.pos : 0) : 0;
  a.src = info.url;
  a.addEventListener("loadedmetadata", () => { try { if (start > 0) a.currentTime = Math.min(start, (a.duration || dur) - 1); } catch (e) { /* egal */ } }, { once: true });
  if (PLAYER.wave && !info.wave) plWaveCompute(info);
  dbCues();
  dbRender();
  if (autoplay) { try { await a.play(); } catch (e) { if (e.name !== "AbortError") toast("Wiedergabe nicht möglich: " + (e.message || e)); } }
}

function dbSame(t) { return t && DECKB.info && t.kind === DECKB.kind && t.ref === DECKB.ref; }
function dbRefOf() { return DECKB.info ? { kind: DECKB.kind, ref: DECKB.kind === "side" ? DECKB.info.ref : DECKB.ref } : null; }

function dbToggle() {
  const t = plTarget(), a = DECKB.audio;
  if (!a.src || (t && !dbSame(t) && a.paused)) return dbLoad(t);
  if (a.paused) a.play().catch((e) => toast(String(e.message || e))); else a.pause();
}

/** wie playerFollow, für Player B (wenn B das Ziel ist) */
function dbFollow(src) {
  const a = DECKB.audio;
  if (PLAYER.noFollow || src === "multi") { dbRender(); return; }
  const t = plTarget();
  if (src === "click" && PLAYER.live) { if (t && (!dbSame(t) || a.paused)) dbLoad(t); return; }
  if (src === "click" || a.paused || !PLAYER.follow) { dbRender(); return; }
  if (t && !dbSame(t)) dbLoad(t);
}

function dbPlayRow() { const t = plTarget(); if (t && !(dbSame(t) && !DECKB.audio.paused)) dbLoad(t); }

/** Voriger/nächster Titel in Player B. Ist B das Ziel, wandert die Markierung mit. */
async function dbStep(dir) {
  const a = DECKB.audio, playing = !a.paused || !a.src;
  if (S.module === "tagger" && TG.order.length) {
    const from = DECKB.kind === "tag" ? DECKB.ref : TG.anchor;
    const k = Math.max(0, Math.min(TG.order.length - 1, TG.order.indexOf(from) + dir));
    const i = TG.order[k];
    if (i === undefined) return;
    if (PLAYER.target === "B") { PLAYER.noFollow = true; try { await tgSelect(i, {}); } finally { PLAYER.noFollow = false; } TG.anchor = i; tgScrollTo(i); }
    return dbLoad({ kind: "tag", ref: i }, playing);
  }
  if (S.module === "compare" && S.visible && S.visible.length) {
    const k = Math.max(0, Math.min(S.visible.length - 1, S.visible.indexOf(S.cur) + dir));
    PLAYER.noFollow = true;
    try { await selectPair(S.visible[k]); } finally { PLAYER.noFollow = false; }
    return dbLoad({ kind: "side", ref: DECKB.kind === "side" ? DECKB.info.ref : "L" }, playing);
  }
}

function dbForget() {
  const a = DECKB.audio;
  if (!a) return;
  a.pause(); a.removeAttribute("src"); a.load();
  DECKB.info = null; DECKB.kind = null; DECKB.ref = null;
  dbABClear(true); dbCues(); dbRender();
}

function dbSide(side) {
  if (DECKB.kind !== "side" || !DECKB.audio.src) return dbLoad({ kind: "side", ref: side });
  dbLoad({ kind: "side", ref: side }, !DECKB.audio.paused, DECKB.audio.currentTime);
}

function dbSeekBy(sec) {
  const a = DECKB.audio;
  if (!a.src) return;
  a.currentTime = Math.max(0, Math.min((a.duration || 0) - 0.5, a.currentTime + sec));
  dbRender();
}

function dbCueJump(dir) {
  const cues = (DECKB.info && DECKB.info.cues) || [], a = DECKB.audio, t = a.currentTime;
  if (!cues.length || !a.src) return;
  const c = dir > 0 ? cues.find((x) => x.pos > t + 0.3) : [...cues].reverse().find((x) => x.pos < t - 1);
  a.currentTime = c ? c.pos : dir > 0 ? t : 0;
  dbRender();
}

/** Schleife (A–B oder Serato-Loop) für Player B */
function dbLoopSet(c) {
  DECKB.loop = c && c.end > c.pos ? c : null;
  cancelAnimationFrame(DECKB.raf);
  $$("#dbCues .pl-cue.loop").forEach((b) => b.classList.toggle("on", !!DECKB.loop && +b.dataset.k === DECKB.loop.k));
  if (!DECKB.loop) return;
  const tick = () => {
    const L = DECKB.loop, a = DECKB.audio;
    if (!L) return;
    if (a.currentTime >= L.end || a.currentTime < L.pos - 0.5) a.currentTime = L.pos;
    DECKB.raf = requestAnimationFrame(tick);
  };
  DECKB.raf = requestAnimationFrame(tick);
}

function dbABStep() {
  const a = DECKB.audio;
  if (!a.src) return;
  if (!DECKB.ab) { DECKB.ab = { a: a.currentTime }; toast(`Player B: A gesetzt bei ${fmtTime(a.currentTime)} – nochmals für B.`); }
  else if (DECKB.ab.b === undefined) {
    const t = a.currentTime;
    if (t <= DECKB.ab.a + 0.2) { toast("B muss nach A liegen."); return; }
    DECKB.ab.b = t;
    dbLoopSet({ pos: DECKB.ab.a, end: t, k: -1 });
    toast(`Player B: Schleife ${fmtTime(DECKB.ab.a)}–${fmtTime(t)}.`);
  } else { dbABClear(); toast("Player B: Schleife aufgehoben."); }
  dbCues(); dbRender();
}
function dbABClear(quiet) { DECKB.ab = null; if (DECKB.loop && DECKB.loop.k === -1) dbLoopSet(null); if (!quiet) { dbCues(); dbRender(); } }

/** Cue-Marken (und A–B-Bereich) über der Leiste von Player B */
function dbCues() {
  const box = $("#dbCues"), i = DECKB.info, a = DECKB.audio;
  if (!box) return;
  const dur = (a && a.duration) || (i && i.duration) || 0;
  let h = i && dur ? (i.cues || []).map((c, k) => {
    const left = (c.pos / dur) * 100;
    const w = c.kind === "loop" && c.end ? `--w:${Math.max(2, ((c.end - c.pos) / dur) * box.clientWidth)}px;` : "";
    const label = `${c.kind === "loop" ? "Loop" : "Cue"} ${c.index + 1}${c.name ? " · " + c.name : ""} · ${fmtTime(c.pos)}${c.kind === "loop" && c.end ? `–${fmtTime(c.end)} · Klick: Schleife an/aus` : ""}`;
    return `<button class="pl-cue${c.kind === "loop" ? " loop" : ""}${DECKB.loop && DECKB.loop.k === k ? " on" : ""}" data-k="${k}" style="left:${left}%;${c.color ? `--cue:${esc(c.color)};` : ""}${w}" title="${esc(label)}" aria-label="${esc(label)}"></button>`;
  }).join("") : "";
  const ab = DECKB.ab;
  if (ab && dur) h += `<button class="pl-abmark${ab.b === undefined ? " open" : ""}" data-abclear="1" style="left:${(ab.a / dur) * 100}%;width:${Math.max(0.4, ab.b !== undefined ? ((ab.b - ab.a) / dur) * 100 : 0)}%" title="A–B-Schleife · Klick: aufheben"></button>`;
  box.innerHTML = h;
}

function dbRender() {
  const a = DECKB.audio;
  if (!a || !PL2.ready) return;
  const i = DECKB.info, box = $("#deckB");
  box.classList.toggle("on", !!a.src);
  box.classList.toggle("playing", !a.paused);
  const tgt = PLAYER.target === "B";
  $("#dbPlay").innerHTML = a.paused ? ICON_PLAY : ICON_PAUSE;
  $("#dbPlay").title = a.paused ? `Player B abspielen${tgt ? " (Leertaste)" : ""}` : `Player B anhalten${tgt ? " (Leertaste)" : ""}`;
  const title = i ? (i.title ? `${i.artist ? i.artist + " – " : ""}${i.title}` : i.name) : "Player B: Rechtsklick auf einen Titel → „In Player B laden“ oder Beschriftung B anklicken";
  if ($("#dbTitle").textContent !== title) $("#dbTitle").textContent = title;
  $("#dbTitle").title = i ? i.path : "";
  const rh = i && i.markable !== false && i.rating !== undefined ? rateHtml(i.rating, i.like, { keys: tgt }) : "";
  if ($("#dbRate").dataset.v !== rh) { $("#dbRate").innerHTML = rh; $("#dbRate").dataset.v = rh; }
  const bpm = i && i.bpm ? String(Math.round(parseFloat(String(i.bpm).replace(",", ".")) || 0) || i.bpm) : "";
  const alt = i && i.key_alt ? [i.key_alt.musical, i.key_alt.openkey].filter(Boolean) : [];
  const meta = i ? `${i.key && typeof keyBadge === "function" ? keyBadge(i.key) : ""}${alt.length ? `<span class="pl-key-alt" title="Musikalisch · Open Key">${esc(alt.join(" · "))}</span>` : ""}${bpm ? `<span class="pl-bpm">${esc(bpm)} BPM</span>` : ""}` : "";
  if ($("#dbMeta").dataset.v !== meta) { $("#dbMeta").innerHTML = meta; $("#dbMeta").dataset.v = meta; }
  const dur = a.duration || (i && i.duration) || 0, t = i ? a.currentTime : 0;
  $("#dbElapsed").textContent = fmtTime(t);
  $("#dbRemain").textContent = "−" + fmtTime(Math.ceil(Math.max(0, dur - t) - 0.001));
  $("#dbRemain").classList.toggle("end", !!i && dur > 0 && dur - t <= 30);
  $("#dbLen").textContent = fmtTime(dur);
  const seek = $("#dbSeek");
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(t * 10)); }
  seek.disabled = !i;
  const hasCues = !!(i && i.cues && i.cues.length);
  $("#dbCuePrev").hidden = $("#dbCueNext").hidden = !hasCues;
  $("#dbRepeat").classList.toggle("on", !!DECKB.repeat); $("#dbRepeat").setAttribute("aria-pressed", String(!!DECKB.repeat));
  $("#dbAB2").classList.toggle("on", !!DECKB.ab); $("#dbAB2").classList.toggle("half", !!DECKB.ab && DECKB.ab.b === undefined);
  $("#dbAB").hidden = S.module !== "compare";
  $$("#dbAB button").forEach((b) => b.classList.toggle("on", DECKB.kind === "side" && i && b.dataset.side === i.ref));
  $$("#dbStart button").forEach((b) => { const on = b.dataset.v === DB_START(); b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); });
  $("#dbVol").classList.toggle("muted", a.muted);
  plTagSync();
  drawWaveInto($("#dbWave"), $("#dbCanvas"), PLAYER.wave && i && i.wave, dur ? t / dur : 0);
}

/** Wellenform in eine Leiste zeichnen (wie plDrawWave, für Player B) */
function drawWaveInto(box, cv, w, played) {
  box.classList.toggle("wave", !!w);
  if (!w || !cv.clientWidth) return;
  const dpr = window.devicePixelRatio || 1, W = Math.max(1, Math.round(cv.clientWidth * dpr)), H = Math.max(1, Math.round(cv.clientHeight * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const g = cv.getContext("2d"), st = getComputedStyle(document.documentElement);
  const acc = st.getPropertyValue("--acc").trim() || "#7c5cff", dim = st.getPropertyValue("--faint").trim() || "#888";
  const n = w.peaks.length, top = Math.max(1, ...w.peaks), bw = W / n, mid = H / 2;
  g.clearRect(0, 0, W, H);
  for (let k = 0; k < n; k++) {
    const x = k * bw, ph = Math.max(1, (w.peaks[k] / top) * (H - 2) / 2), rh = Math.max(0.5, (w.rms[k] / top) * (H - 2) / 2), on = k / n < played;
    g.globalAlpha = on ? 0.45 : 0.3; g.fillStyle = on ? acc : dim;
    g.fillRect(x, mid - ph, Math.max(1, bw - 0.4), ph * 2);
    g.globalAlpha = on ? 1 : 0.75;
    g.fillRect(x, mid - rh, Math.max(1, bw - 0.4), rh * 2);
  }
  g.globalAlpha = 1; g.fillStyle = acc;
  g.fillRect(Math.round(played * W), 0, Math.max(1, Math.round(dpr)), H);
}

/** Ausgabegeräte (nur wenn der Browser setSinkId kann) → [{id, label}] oder null */
async function dbSinkList() {
  if (typeof DECKB.audio.setSinkId !== "function" || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return null;
  try {
    return (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audiooutput" && d.deviceId !== "default")
      .map((d, k) => ({ id: d.deviceId, label: d.label || `Ausgabegerät ${k + 1}` }));
  } catch (e) { return []; }
}

async function dbSinkSet(id, quiet = false) {
  try { await DECKB.audio.setSinkId(id); DECKB.sink = id; if (!quiet) { plSetPref("sink_b", id); toast("Ausgabegerät für Player B gesetzt."); } }
  catch (x) { if (!quiet) toast("Ausgabegerät nicht verfügbar: " + (x.message || x)); }
}

/** Menü von Player B (gleicher Platz wie das Menü von A) */
async function dbMenu(btn) {
  const sinks = await dbSinkList(), r = btn.getBoundingClientRect();
  const items = [];
  if (sinks === null) items.push({ label: "    Ausgabegerät: wird hier nicht unterstützt", run: () => {} });
  else {
    items.push({ label: (DECKB.sink ? "    " : "✓ ") + "Ausgabe: Standard des Systems", run: () => dbSinkSet("") });
    sinks.forEach((s) => items.push({ label: (DECKB.sink === s.id ? "✓ " : "    ") + "Ausgabe: " + s.label, run: () => dbSinkSet(s.id) }));
  }
  items.push("-", { label: "Player B ausblenden", run: () => plSetPref("deck2", false) });
  showMenu(r.left - 200, r.bottom + 6, items);
}

// ====================================================================== #69 Abdocken
async function plDetach() {
  if (DET.on) return plDock();
  await call("bus_reset", "pl_cmd"); await call("bus_reset", "pl_state");
  let r;
  try { r = await call("player_window_open", pl2B()); } catch (e) { r = { ok: false, error: String(e.message || e) }; }
  if (!r.ok && r.browser) {
    const pos = r.x !== null && r.x !== undefined ? `left=${r.x},top=${r.y},` : "";
    const f = `${pos}width=${r.w || 1280},height=${r.h || 380}`;
    DET.popup = window.open("player-window.html#token=" + encodeURIComponent(TOKEN), "tsPlayer", f + ",resizable=yes");
    if (!DET.popup) { toast("Das Player-Fenster wurde vom Browser blockiert – bitte Popups für diese Seite erlauben."); return; }
  } else if (!r.ok) { toast(r.error || "Player-Fenster konnte nicht geöffnet werden."); return; }
  DET.on = true; DET.t0 = Date.now(); DET.seq = 0; DET.waveKey = { A: null, B: null }; DET.last = "";
  pl2Layout();
  clearInterval(DET.timer);
  DET.timer = setInterval(detTick, 200);
  toast("Player abgedockt – Markierung, Leertaste und ↑/↓ steuern ihn weiterhin.");
}

function plDock() {
  if (!DET.on) return;
  DET.on = false;
  clearInterval(DET.timer);
  call("bus_post", "pl_state", { closed: true }).catch(() => {});
  if (DET.popup && !DET.popup.closed) DET.popup.close();
  DET.popup = null;
  call("player_window_close").catch(() => {});
  pl2Layout();
  plRender();
}

/** Zustand eines Players für das Fenster (Wellenform nur bei neuem Titel) */
function detDeck(d, a, i, x) {
  const st = { on: !!(a.src && i), paused: a.paused, t: Math.round(a.currentTime * 10) / 10, dur: a.duration || (i && i.duration) || 0,
    vol: x.vol, muted: a.muted, repeat: x.repeat, start: x.start, ab: x.ab ? (x.ab.b === undefined ? "half" : "on") : "",
    rate: Math.round((a.playbackRate || 1) * 1000) / 1000, live: x.live };
  if (i) {
    Object.assign(st, { title: i.title || "", artist: i.artist || "", name: i.name, path: i.path, key: i.key || "", key_alt: i.key_alt || {},
      bpm: i.bpm || "", rating: i.rating, like: i.like, markable: i.markable !== false && i.rating !== undefined,
      kind: x.kind, ref: x.kind === "side" ? i.ref : x.ref,
      cues: (i.cues || []).map((c) => ({ pos: c.pos, end: c.end, kind: c.kind, index: c.index, name: c.name, color: c.color })),
      wkey: i.wave_key || i.path, stem: x.stem || "" });
    const wk = (i.wave_key || i.path) + (i.wave ? ":w" : "");
    if (DET.waveKey[d] !== wk) { DET.waveKey[d] = wk; st.wave = (PLAYER.wave && i.wave) || null; }
  }
  return st;
}

function detState() {
  const i = PLAYER.info, b = pl2B();
  const st = { theme: document.documentElement.dataset.theme || "dark", module: S.module, target: b ? PLAYER.target : "A", two: b,
    A: detDeck("A", PLAYER.audio, i, { vol: PLAYER.vol, repeat: PLAYER.repeat, start: PLAYER.startAt, ab: PLAYER.ab, live: PLAYER.live,
      kind: PLAYER.kind, ref: PLAYER.ref, stem: i ? ((i.stems || []).find((g) => plSame(g)) || {}).label : "" }) };
  if (b) st.B = detDeck("B", DECKB.audio, DECKB.info, { vol: DECKB.audio.volume, repeat: DECKB.repeat, start: DB_START(), ab: DECKB.ab,
    kind: DECKB.kind, ref: DECKB.ref });
  else DET.waveKey.B = null;
  return st;
}

async function detTick() {
  if (DET.busy || !DET.on) return;
  DET.busy = true;
  try {
    const st = detState(), j = JSON.stringify(st, (k, v) => (k === "wave" ? (v ? 1 : 0) : v));
    const send = j !== DET.last || (st.A && st.A.wave !== undefined) || (st.B && st.B.wave !== undefined);
    if (send) DET.last = j;
    const r = await call("bus_sync", "pl_cmd", DET.seq, send ? "pl_state" : null, send ? st : null, "pl_state");
    DET.seq = r.seq;
    for (const m of r.msgs) await detCmd(m);
    if (!DET.on) return;
    const gone = (DET.popup && DET.popup.closed) || (Date.now() - DET.t0 > 10000 && (r.peer === null || r.peer > 5));
    if (gone) plDock();
  } catch (e) { /* nächster Takt */ } finally { DET.busy = false; }
}

/** Befehle aus dem Player-Fenster ausführen (deck „A“ oder „B“) */
async function detCmd(m) {
  if (m.cmd === "hello") { DET.waveKey = { A: null, B: null }; DET.last = ""; return; }
  if (m.cmd === "dock") return plDock();
  if (m.cmd === "target") return dbTargetSet(m.deck === "B" ? "B" : "A");
  if (m.cmd === "up" || m.cmd === "down") return plStep(m.cmd === "down" ? 1 : -1, false);
  if (m.deck === "B") return detCmdB(m);
  const a = PLAYER.audio, r = PLAYER.info ? { kind: PLAYER.kind, ref: PLAYER.kind === "side" ? PLAYER.info.ref : PLAYER.ref } : null;
  switch (m.cmd) {
    case "toggle":                        // Knopf im Fenster: den geladenen Titel anhalten/fortsetzen
      if (a.src && PLAYER.info) { if (a.paused) a.play().catch(() => {}); else a.pause(); } else await plToggle();
      break;
    case "prev": await plStep(-1); break;
    case "next": await plStep(1); break;
    case "seek": if (a.src && isFinite(m.t)) { a.currentTime = Math.max(0, m.t); plRender(); } break;
    case "seekby": plSeekBy(+m.s || 0); break;
    case "vol": PLAYER.vol = Math.max(0, Math.min(1, +m.v)); if (!PLAYER.fade) a.volume = PLAYER.vol; $("#plVol").value = String(Math.round(PLAYER.vol * 100)); plSetPref("vol", PLAYER.vol); break;
    case "mute": a.muted = !a.muted; plRender(); break;
    case "rate": if (r) await plMarkTarget(r, +m.n, null); break;
    case "like": if (r) await plMarkTarget(r, null, "toggle"); break;
    case "repeat": $("#plRepeat").click(); break;
    case "ab": plABStep(); break;
    case "live": plLiveSet(!PLAYER.live); break;
    case "cue": plCueJump(m.dir > 0 ? 1 : -1); break;
    case "start": if (["0", "30", "60", "cue"].includes(m.v)) plSetPref("start", m.v); break;
    case "stem": plStemCycle(m.dir || 1); break;
    default: break;
  }
}

async function detCmdB(m) {
  const a = DECKB.audio, r = dbRefOf();
  switch (m.cmd) {
    case "toggle": if (!a.src) await dbLoad(plTarget()); else if (a.paused) a.play().catch(() => {}); else a.pause(); break;
    case "prev": await dbStep(-1); break;
    case "next": await dbStep(1); break;
    case "seek": if (a.src && isFinite(m.t)) { a.currentTime = Math.max(0, m.t); dbRender(); } break;
    case "seekby": dbSeekBy(+m.s || 0); break;
    case "vol": { const v = Math.max(0, Math.min(1, +m.v)); $("#dbVol").value = String(Math.round(v * 100)); plSetPref("vol_b", v); break; }
    case "mute": a.muted = !a.muted; dbRender(); break;
    case "rate": if (r) await plMarkTarget(r, +m.n, null); break;
    case "like": if (r) await plMarkTarget(r, null, "toggle"); break;
    case "repeat": $("#dbRepeat").click(); break;
    case "ab": dbABStep(); break;
    case "cue": dbCueJump(m.dir > 0 ? 1 : -1); break;
    case "start": if (["0", "30", "60", "cue"].includes(m.v)) plSetPref("start_b", m.v); break;
    default: break;
  }
}

// ====================================================================== Kontextmenü: in Player A/B laden
function plRowMenu(e, t, label) {
  e.preventDefault();
  const items = [{ label: `${label} in Player A abspielen`, run: () => plLoad(t, true) }];
  if (PL2.layout === "top") items.push({ label: `${label} in Player B laden`, run: () => dbLoad(t, true) });
  items.push("-", { label: "Mit externem Player öffnen", run: () => call("players").then((l) => plExternal(l.length ? 0 : null)) });
  if (t.kind === "tag" && typeof djAddFromTagger === "function" && S.module === "tagger") {
    const n = typeof tgSelected === "function" ? tgSelected().length : 1;
    items.push("-", { label: `Zum DJ-Set hinzufügen${n > 1 ? ` (${n})` : ""}`, run: () => djAddFromTagger(false) });
  }
  showMenu(e.clientX, e.clientY, items);
}

// ====================================================================== Einstellungen, Tasten, Start
function pl2Apply(pp) {
  PL2.layout = pp.layout || "bottom";
  PL2.collapsed = !!pp.top_collapsed;
  PL2.deck2 = !!pp.deck2;
  PLAYER.target = pp.deck2 && pp.layout === "top" && pp.deck_target === "B" ? "B" : "A";
  PL2.window = pp.window || PL2.window;
  DECKB.startAt = pp.start_b || "0";
  DECKB.repeat = !!pp.repeat_b;
  if (DECKB.audio) { DECKB.audio.volume = pp.vol_b ?? 0.8; $("#dbVol").value = String(Math.round(DECKB.audio.volume * 100)); }
  DECKB.sink = pp.sink_b || "";
  if (!PL2.ready) return;
  pl2Layout();
  if (DECKB.sink) dbSinkSet(DECKB.sink, true);
}

function pl2Pref(k, v) {
  if (k === "layout") PL2.layout = v;
  else if (k === "top_collapsed") PL2.collapsed = !!v;
  else if (k === "deck2") { PL2.deck2 = !!v; if (!v) { DECKB.audio.pause(); PLAYER.target = "A"; } }
  else if (k === "deck_target") PLAYER.target = v === "B" && pl2B() ? "B" : "A";
  else if (k === "sink_b") DECKB.sink = v;
  else if (k === "start_b") DECKB.startAt = v;
  else if (k === "repeat_b") DECKB.repeat = !!v;
  else if (k === "vol_b") { DECKB.audio.volume = v; return; }
  pl2Layout();
  plRender();
  dbRender();
}

function pl2Key(e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "P" && e.shiftKey && PL2.layout === "top") { e.preventDefault(); plTopFold(); }
  else if ((e.key === "b" || e.key === "B") && !e.shiftKey && pl2B()) { e.preventDefault(); dbTargetSet(PLAYER.target === "B" ? "A" : "B"); }
}

/** Tasten, die bei Ziel B auf Player B wirken (Leertaste, 0–5 und F laufen über plToggle/plMark). → true = erledigt */
function dbKey(e) {
  if (PLAYER.target !== "B" || !pl2B()) return false;
  const a = DECKB.audio, plain = !e.ctrlKey && !e.metaKey && !e.altKey, k = e.key;
  if (e.shiftKey && (k === "ArrowRight" || k === "ArrowLeft") && a.src) dbSeekBy(k === "ArrowRight" ? 10 : -10);
  else if (plain && (k === "l" || k === "L") && a.src) dbABStep();
  else if (plain && (k === "r" || k === "R")) $("#dbRepeat").click();
  else if (k === "Escape" && DECKB.ab) dbABClear();
  else if (plain && (k === "m" || k === "M")) { a.muted = !a.muted; dbRender(); toast(a.muted ? "Player B stumm (M)" : "Player B: Ton an"); }
  else if (e.altKey && (k === "PageDown" || k === "PageUp") && a.src) dbCueJump(k === "PageDown" ? 1 : -1);
  else return false;
  e.preventDefault();
  return true;
}

function initPlayer2(pp) {
  const b = new Audio();
  b.preload = "metadata";
  DECKB.audio = b;
  ["play", "pause", "emptied", "timeupdate"].forEach((ev) => b.addEventListener(ev, dbRender));
  b.addEventListener("loadedmetadata", () => { dbCues(); dbRender(); });
  b.addEventListener("ended", () => {
    if (DECKB.repeat) { b.currentTime = 0; b.play().catch(() => {}); return; }
    if (PLAYER.follow && PLAYER.target === "B") dbStep(1);
    dbRender();
  });
  b.addEventListener("error", () => { if (b.src) toast("Player B: Datei kann nicht abgespielt werden."); });
  PL2.home = $("#player").parentElement;
  PL2.ready = true;
  pl2Apply(pp);
  $("#plTopFold").addEventListener("click", () => plTopFold());
  $("#plDetach").addEventListener("click", plDetach);
  $("#plDockChip").addEventListener("click", plDock);
  $("#plTag").addEventListener("click", () => dbTargetSet("A"));
  $("#dbTag").addEventListener("click", () => dbTargetSet("B"));
  $("#dbPlay").addEventListener("click", () => { if (!b.src) dbLoad(plTarget()); else if (b.paused) b.play().catch(() => {}); else b.pause(); });
  $("#dbPrev").addEventListener("click", () => dbStep(-1));
  $("#dbNext").addEventListener("click", () => dbStep(1));
  $("#dbCuePrev").addEventListener("click", () => dbCueJump(-1));
  $("#dbCueNext").addEventListener("click", () => dbCueJump(1));
  $("#dbRepeat").addEventListener("click", () => { plSetPref("repeat_b", !DECKB.repeat); toast(DECKB.repeat ? "Player B wiederholt den Titel." : "Player B: nicht mehr wiederholen."); });
  $("#dbAB2").addEventListener("click", dbABStep);
  $("#dbAB").addEventListener("click", (e) => { const t = e.target.closest("[data-side]"); if (t) dbSide(t.dataset.side); });
  $("#dbStart").addEventListener("click", (e) => { const t = e.target.closest("[data-v]"); if (t) plSetPref("start_b", t.dataset.v); });
  $("#dbMore").addEventListener("click", (e) => dbMenu(e.currentTarget));
  $("#dbSeek").addEventListener("input", (e) => { b.currentTime = (+e.target.value) / 10; dbRender(); });
  $("#dbVol").addEventListener("input", (e) => plSetPref("vol_b", (+e.target.value) / 100));
  $("#dbRate").addEventListener("click", (e) => {
    const t = e.target.closest("button"), r = dbRefOf(); if (!t || !r) return;
    if (t.dataset.star) plMarkTarget(r, +t.dataset.star, null); else if (t.dataset.like) plMarkTarget(r, null, "toggle");
  });
  $("#dbCues").addEventListener("click", (e) => {
    if (e.target.closest("[data-abclear]")) { dbABClear(); toast("Player B: Schleife aufgehoben."); return; }
    const t = e.target.closest(".pl-cue"); if (!t || !DECKB.info) return;
    const c = DECKB.info.cues[+t.dataset.k];
    if (c.kind === "loop" && c.end) {
      if (DECKB.loop && DECKB.loop.k === +t.dataset.k) { dbLoopSet(null); return; }
      dbLoopSet({ pos: c.pos, end: c.end, k: +t.dataset.k });
    }
    b.currentTime = c.pos;
    if (b.paused) b.play().catch(() => {});
    dbRender();
  });
  window.addEventListener("resize", () => { dbCues(); dbRender(); });
  window.addEventListener("beforeunload", () => { if (DET.popup && !DET.popup.closed) DET.popup.close(); });
  // Rechtsklick auf Titel (Tagger) und Dateipaare (Vergleich)
  $("#tgInner").addEventListener("contextmenu", async (e) => {
    const r = e.target.closest(".tg-row[data-i]"); if (!r) return;
    const i = +r.dataset.i;
    e.preventDefault();
    if (!TG.sel.has(i)) { PLAYER.noFollow = true; try { await tgSelect(i, {}); } finally { PLAYER.noFollow = false; } }
    plRowMenu(e, { kind: "tag", ref: i }, "Titel");
  });
  $("#pairsInner").addEventListener("contextmenu", async (e) => {
    const r = e.target.closest(".pair[data-i]"); if (!r) return;
    e.preventDefault();
    if (S.cur !== +r.dataset.i) { PLAYER.noFollow = true; try { await selectPair(+r.dataset.i); } finally { PLAYER.noFollow = false; } }
    const items = [
      { label: "Links in Player A abspielen", run: () => plLoad({ kind: "side", ref: "L" }) },
      { label: "Rechts in Player A abspielen", run: () => plLoad({ kind: "side", ref: "R" }) },
    ];
    if (PL2.layout === "top") items.push("-",
      { label: "Links in Player B laden", run: () => dbLoad({ kind: "side", ref: "L" }) },
      { label: "Rechts in Player B laden", run: () => dbLoad({ kind: "side", ref: "R" }) });
    showMenu(e.clientX, e.clientY, items);
  });
  pl2DragInit();
}

// ====================================================================== #105 Titel per Ziehen laden
const PL_DND = "application/x-tagstudio-track";
/** Ziehen beginnt (Tagger, Vergleich, DJ-Set): Ziel im Player merken. t = {kind:"tag", ref} oder {kind:"pair", ref} */
function plDragStart(e, t) {
  try { e.dataTransfer.setData(PL_DND, JSON.stringify(t)); } catch (err) { return; }
  e.dataTransfer.effectAllowed = e.dataTransfer.effectAllowed === "move" ? "copyMove" : "copy";
  document.body.classList.add("pl-dragging");
}

function pl2DragInit() {
  $("#tgInner").addEventListener("dragstart", (e) => {
    const r = e.target.closest(".tg-row[data-i]"); if (!r) return;
    plDragStart(e, { kind: "tag", ref: +r.dataset.i });
  });
  $("#pairsInner").addEventListener("dragstart", (e) => {
    const r = e.target.closest(".pair[data-i]"); if (!r) return;
    plDragStart(e, { kind: "pair", ref: +r.dataset.i });
  });
  document.addEventListener("dragend", () => {
    document.body.classList.remove("pl-dragging");
    $$(".player.drop-on").forEach((x) => x.classList.remove("drop-on"));
  });
  for (const [id, deck] of [["#player", "A"], ["#deckB", "B"]]) {
    const el = $(id);
    el.addEventListener("dragover", (e) => {
      if (!e.dataTransfer.types.includes(PL_DND)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
      el.classList.add("drop-on");
    });
    el.addEventListener("dragleave", (e) => { if (!el.contains(e.relatedTarget)) el.classList.remove("drop-on"); });
    el.addEventListener("drop", (e) => {
      if (!e.dataTransfer.types.includes(PL_DND)) return;
      e.preventDefault();
      el.classList.remove("drop-on");
      document.body.classList.remove("pl-dragging");
      let t;
      try { t = JSON.parse(e.dataTransfer.getData(PL_DND)); } catch (err) { return; }
      plDropLoad(t, deck, e.clientX, e.clientY);
    });
  }
}

async function plDropLoad(t, deck, x, y) {
  const load = (target) => (deck === "B" ? dbLoad(target, true) : plLoad(target, true));
  if (t.kind === "tag") return load({ kind: "tag", ref: t.ref });
  if (t.kind !== "pair") return;
  if (S.cur !== t.ref) { PLAYER.noFollow = true; try { await selectPair(t.ref); } finally { PLAYER.noFollow = false; } }
  showMenu(x, y, [
    { label: `Links in Player ${deck} laden`, run: () => load({ kind: "side", ref: "L" }) },
    { label: `Rechts in Player ${deck} laden`, run: () => load({ kind: "side", ref: "R" }) },
  ]);
}
