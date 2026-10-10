/* MarKusSXCH TagStudio – Player-Erweiterungen 3.4.0:
   #94 Überblenden zum nächsten Titel · #68 Player oben (einklappbar) · #67 Player B (zweiter Player, eigenes Ausgabegerät)
   #69 Abdocken (eigenes Fenster: zeigt und steuert den Player; die Wiedergabe bleibt in diesem Fenster und läuft weiter)
   Kontextmenü auf Titeln: in Player A/B laden. */
"use strict";

const PL2 = { layout: "bottom", collapsed: false, deck2: false, window: null, ready: false };
const DECKB = { audio: null, info: null, kind: null, ref: null, seq: 0, sink: "" };
const DET = { on: false, timer: 0, seq: 0, popup: null, t0: 0, waveKey: null, last: "", busy: false };

// ====================================================================== #94 Überblenden
/** Beim Abspielen prüfen, ob es Zeit zum Überblenden ist (aus dem timeupdate des aktiven Elements). */
function plXfadeCheck() {
  const a = PLAYER.audio, x = PLAYER.xfade;
  if (!x || PLAYER.fade || PLAYER.loading || a.paused || !a.src || PLAYER.repeat || PLAYER.loop || PLAYER.ab || !PLAYER.follow) return;
  if (S.module !== "tagger" || PLAYER.kind !== "tag" || !TG.order.length) return;
  const dur = a.duration;
  if (!isFinite(dur) || dur < x + 2) return;
  let at = dur - x;
  if (PLAYER.xfadeAfter > 0) at = Math.min(at, (PLAYER.playFrom || 0) + PLAYER.xfadeAfter);   // Durchhören: nach x Sekunden
  if (a.currentTime < at || a.currentTime > dur - 0.3) return;
  const k = TG.order.indexOf(TG.anchor);
  if (k < 0 || k >= TG.order.length - 1) return;
  plCrossfade(TG.order[k + 1]);
}

/** Zum Titel i überblenden: neues Element lädt und blendet ein, das alte gleichmässig aus (gleiche Leistung, sin/cos). */
async function plCrossfade(i) {
  const old = PLAYER.audio, nu = PLAYER.spare, D = PLAYER.xfade * 1000;
  PLAYER.fade = { old, timer: 0 };
  PLAYER.spare = old;
  PLAYER.audio = nu;
  nu.muted = old.muted;
  nu.volume = 0;
  await tgSelect(i, {});            // Player B / „Folgen“: nu ist noch leer → kein Laden über playerFollow
  TG.anchor = i;
  tgScrollTo(i);
  await plLoad({ kind: "tag", ref: i }, true, null, PLAYER.xfadeStart === "start" ? null : PLAYER.xfadeStart, true);
  const f = PLAYER.fade;
  if (!f || f.old !== old) return;
  const t0 = performance.now();
  f.timer = setInterval(() => {
    if (PLAYER.fade !== f) return clearInterval(f.timer);
    const g = Math.min(1, (performance.now() - t0) / D), v = PLAYER.vol;
    PLAYER.audio.volume = v * Math.sin((g * Math.PI) / 2);
    old.volume = v * Math.cos((g * Math.PI) / 2);
    if (g >= 1) plFadeStop();
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
function pl2Layout() {
  if (!PL2.ready) return;
  const top = PL2.layout === "top" && !DET.on;
  const p = $("#player"), box = $("#plTop"), db = $("#deckB");
  if (top && p.parentElement !== $("#plTopSlot")) $("#plTopSlot").appendChild(p);
  else if (!top && p.parentElement !== PL2.home) PL2.home.insertBefore(p, $("#undoBtn"));
  box.hidden = !top;
  box.classList.toggle("collapsed", top && PL2.collapsed);
  const fold = $("#plTopFold"), lbl = PL2.collapsed ? "Player-Leiste ausklappen (Shift+P)" : "Player-Leiste einklappen (Shift+P)";
  fold.title = lbl; fold.setAttribute("aria-label", lbl); fold.setAttribute("aria-expanded", String(!PL2.collapsed));
  if (top) { if (db.parentElement !== box) box.appendChild(db); }
  else if (db.nextElementSibling !== $("footer.actions")) $(".main").insertBefore(db, $("footer.actions"));
  db.hidden = !PL2.deck2;
  document.body.classList.toggle("pl-at-top", top);
  document.body.classList.toggle("pl-detached", DET.on);
  $("#plDockChip").hidden = !DET.on;
  const dt = $("#plDetach"), dl = DET.on ? "Player andocken" : "Player abdocken (eigenes Fenster)";
  dt.title = dl; dt.setAttribute("aria-label", dl);
  requestAnimationFrame(() => { plCues(); plDrawWave(); dbRender(); });
}

function plTopFold(on = !PL2.collapsed) {
  plSetPref("top_collapsed", !!on);
}

// ====================================================================== #67 Player B
async function dbLoad(t, autoplay = true) {
  if (!t) { toast(S.module === "tagger" ? "Erst einen Titel markieren." : "Erst ein Dateipaar wählen."); return; }
  if (!PL2.deck2) plSetPref("deck2", true);
  const seq = ++DECKB.seq;
  let info;
  try { info = await call("media_url", t.kind, t.ref); } catch (e) { toast(String(e.message || e)); return; }
  if (seq !== DECKB.seq) return;
  DECKB.info = info; DECKB.kind = t.kind; DECKB.ref = t.ref;
  const a = DECKB.audio, dur = info.duration || 0, firstCue = (info.cues || []).find((c) => c.pos > 0.05);
  const sm = PLAYER.startAt;
  const start = sm === "30" ? dur * 0.3 : sm === "60" ? Math.min(60, dur * 0.5) : sm === "cue" ? (firstCue ? firstCue.pos : 0) : 0;
  a.src = info.url;
  a.addEventListener("loadedmetadata", () => { try { if (start > 0) a.currentTime = Math.min(start, (a.duration || dur) - 1); } catch (e) { /* egal */ } }, { once: true });
  if (PLAYER.wave && !info.wave) plWaveCompute(info);
  dbRender();
  if (autoplay) { try { await a.play(); } catch (e) { if (e.name !== "AbortError") toast("Wiedergabe nicht möglich: " + (e.message || e)); } }
}

function dbSame(t) { return t && DECKB.info && t.kind === DECKB.kind && t.ref === DECKB.ref; }

function dbToggle() {
  const t = plTarget(), a = DECKB.audio;
  if (!a.src || (t && !dbSame(t) && a.paused)) return dbLoad(t);
  if (a.paused) a.play().catch((e) => toast(String(e.message || e))); else a.pause();
}

/** wie playerFollow, für Player B (wenn die Markierung auf B wirkt) */
function dbFollow(src) {
  const a = DECKB.audio;
  if (src === "multi") { dbRender(); return; }
  const t = plTarget();
  if (src === "click" && PLAYER.live) { if (t && (!dbSame(t) || a.paused)) dbLoad(t); return; }
  if (src === "click" || a.paused || !PLAYER.follow) { dbRender(); return; }
  if (t && !dbSame(t)) dbLoad(t);
}

function dbPlayRow() { const t = plTarget(); if (t && !(dbSame(t) && !DECKB.audio.paused)) dbLoad(t); }

function dbForget() {
  const a = DECKB.audio;
  if (!a) return;
  a.pause(); a.removeAttribute("src"); a.load();
  DECKB.info = null; DECKB.kind = null; DECKB.ref = null;
  dbRender();
}

function dbRender() {
  const a = DECKB.audio;
  if (!a || !PL2.ready) return;
  const i = DECKB.info, box = $("#deckB");
  box.classList.toggle("on", !!a.src);
  box.classList.toggle("playing", !a.paused);
  box.classList.toggle("target", PLAYER.target === "B");
  $("#dbPlay").innerHTML = a.paused ? ICON_PLAY : ICON_PAUSE;
  $("#dbPlay").title = a.paused ? `Player B abspielen${PLAYER.target === "B" ? " (Leertaste)" : ""}` : "Player B anhalten";
  const title = i ? (i.title ? `${i.artist ? i.artist + " – " : ""}${i.title}` : i.name) : "Player B: Titel per Rechtsklick → „In Player B laden“ oder Ziel → B";
  if ($("#dbTitle").textContent !== title) $("#dbTitle").textContent = title;
  $("#dbTitle").title = i ? i.path : "";
  const dur = a.duration || (i && i.duration) || 0, t = i ? a.currentTime : 0;
  $("#dbElapsed").textContent = fmtTime(t);
  $("#dbRemain").textContent = "−" + fmtTime(Math.ceil(Math.max(0, dur - t) - 0.001));
  $("#dbRemain").classList.toggle("end", !!i && dur > 0 && dur - t <= 30);
  const seek = $("#dbSeek");
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(t * 10)); }
  seek.disabled = !i;
  $$("#dbTarget button").forEach((b) => { const on = b.dataset.v === PLAYER.target; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); });
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

/** Ausgabegeräte für Player B (nur wenn der Browser setSinkId kann) */
async function dbSinks() {
  const sel = $("#dbSink");
  if (typeof DECKB.audio.setSinkId !== "function" || !navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) { sel.hidden = true; return; }
  let devs = [];
  try { devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audiooutput" && d.deviceId !== "default"); } catch (e) { devs = []; }
  sel.innerHTML = `<option value="">Ausgabe: Standard</option>` + devs.map((d, k) => `<option value="${esc(d.deviceId)}">${esc(d.label || `Ausgabegerät ${k + 1}`)}</option>`).join("");
  sel.value = devs.some((d) => d.deviceId === DECKB.sink) ? DECKB.sink : "";
  sel.hidden = !devs.length;
  if (sel.value) DECKB.audio.setSinkId(sel.value).catch(() => {});
}

function dbTargetSet(v) {
  plSetPref("deck_target", v);
  toast(v === "B" ? "Markierung, Leertaste und Doppelklick wirken jetzt auf Player B." : "Markierung, Leertaste und Doppelklick wirken auf Player A.");
}

// ====================================================================== #69 Abdocken
async function plDetach() {
  if (DET.on) return plDock();
  await call("bus_reset", "pl_cmd"); await call("bus_reset", "pl_state");
  let r;
  try { r = await call("player_window_open"); } catch (e) { r = { ok: false, error: String(e.message || e) }; }
  if (!r.ok && r.browser) {
    const g = PL2.window, f = g ? `left=${g.x},top=${g.y},width=${g.w},height=${g.h}` : "width=1100,height=230";
    DET.popup = window.open("player-window.html#token=" + encodeURIComponent(TOKEN), "tsPlayer", f + ",resizable=yes");
    if (!DET.popup) { toast("Das Player-Fenster wurde vom Browser blockiert – bitte Popups für diese Seite erlauben."); return; }
  } else if (!r.ok) { toast(r.error || "Player-Fenster konnte nicht geöffnet werden."); return; }
  DET.on = true; DET.t0 = Date.now(); DET.seq = 0; DET.waveKey = null; DET.last = "";
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

/** Zustand für das Player-Fenster (Wellenform nur bei neuem Titel) */
function detState() {
  const a = PLAYER.audio, i = PLAYER.info;
  const st = { on: !!(a.src && i), paused: a.paused, t: Math.round(a.currentTime * 10) / 10, dur: a.duration || (i && i.duration) || 0,
    vol: PLAYER.vol, muted: a.muted, repeat: PLAYER.repeat, live: PLAYER.live, start: PLAYER.startAt,
    ab: PLAYER.ab ? (PLAYER.ab.b === undefined ? "half" : "on") : "", theme: document.documentElement.dataset.theme || "dark",
    module: S.module, fade: !!PLAYER.fade };
  if (i) {
    Object.assign(st, { title: i.title || "", artist: i.artist || "", name: i.name, path: i.path, key: i.key || "", key_alt: i.key_alt || {},
      bpm: i.bpm || "", rating: i.rating, like: i.like, markable: i.markable !== false && i.rating !== undefined,
      cues: (i.cues || []).map((c) => ({ pos: c.pos, end: c.end, kind: c.kind, index: c.index, name: c.name, color: c.color })),
      wkey: i.wave_key || i.path, stem: ((i.stems || []).find((g) => plSame(g)) || {}).label || "" });
    const wk = (i.wave_key || i.path) + (i.wave ? ":w" : "");
    if (DET.waveKey !== wk) { DET.waveKey = wk; st.wave = (PLAYER.wave && i.wave) || null; }
  }
  return st;
}

async function detTick() {
  if (DET.busy || !DET.on) return;
  DET.busy = true;
  try {
    const st = detState(), j = JSON.stringify({ ...st, wave: st.wave ? 1 : 0 });
    const send = j !== DET.last || st.wave !== undefined;
    if (send) DET.last = j;
    const r = await call("bus_sync", "pl_cmd", DET.seq, send ? "pl_state" : null, send ? st : null, "pl_state");
    DET.seq = r.seq;
    for (const m of r.msgs) await detCmd(m);
    if (!DET.on) return;
    const gone = (DET.popup && DET.popup.closed) || (Date.now() - DET.t0 > 10000 && (r.peer === null || r.peer > 5));
    if (gone) plDock();
  } catch (e) { /* nächster Takt */ } finally { DET.busy = false; }
}

/** Befehle aus dem Player-Fenster ausführen */
async function detCmd(m) {
  const a = PLAYER.audio;
  switch (m.cmd) {
    case "hello": DET.waveKey = null; DET.last = ""; break;
    case "dock": plDock(); break;
    case "toggle":                        // Knopf/Leertaste im Fenster: den geladenen Titel anhalten/fortsetzen
      if (a.src && PLAYER.info) { if (a.paused) a.play().catch(() => {}); else a.pause(); } else await plToggle();
      break;
    case "prev": await plStep(-1); break;
    case "next": await plStep(1); break;
    case "up": case "down": await plStep(m.cmd === "down" ? 1 : -1, false); break;
    case "seek": if (a.src && isFinite(m.t)) { a.currentTime = Math.max(0, m.t); plRender(); } break;
    case "seekby": plSeekBy(+m.s || 0); break;
    case "vol": PLAYER.vol = Math.max(0, Math.min(1, +m.v)); if (!PLAYER.fade) a.volume = PLAYER.vol; $("#plVol").value = String(Math.round(PLAYER.vol * 100)); plSetPref("vol", PLAYER.vol); break;
    case "mute": a.muted = !a.muted; plRender(); break;
    case "rate": if (PLAYER.info) await plMarkTarget({ kind: PLAYER.kind, ref: PLAYER.kind === "side" ? PLAYER.info.ref : PLAYER.ref }, +m.n, null); break;
    case "like": if (PLAYER.info) await plMarkTarget({ kind: PLAYER.kind, ref: PLAYER.kind === "side" ? PLAYER.info.ref : PLAYER.ref }, null, "toggle"); break;
    case "repeat": $("#plRepeat").click(); break;
    case "ab": plABStep(); break;
    case "live": plLiveSet(!PLAYER.live); break;
    case "cue": plCueJump(m.dir > 0 ? 1 : -1); break;
    case "start": if (["0", "30", "60", "cue"].includes(m.v)) plSetPref("start", m.v); break;
    case "stem": plStemCycle(m.dir || 1); break;
    default: break;
  }
}

// ====================================================================== Kontextmenü: in Player A/B laden
function plRowMenu(e, t, label) {
  e.preventDefault();
  showMenu(e.clientX, e.clientY, [
    { label: `${label} in Player A abspielen`, run: () => plLoad(t, true) },
    { label: `${label} in Player B laden`, run: () => dbLoad(t, true) },
    "-",
    { label: "Mit externem Player öffnen", run: () => call("players").then((l) => plExternal(l.length ? 0 : null)) },
  ]);
}

// ====================================================================== Einstellungen, Tasten, Start
function pl2Apply(pp) {
  PL2.layout = pp.layout || "bottom";
  PL2.collapsed = !!pp.top_collapsed;
  PL2.deck2 = !!pp.deck2;
  PLAYER.target = pp.deck2 && pp.deck_target === "B" ? "B" : "A";
  PL2.window = pp.window || PL2.window;
  if (DECKB.audio) { DECKB.audio.volume = pp.vol_b ?? 0.8; $("#dbVol").value = String(Math.round(DECKB.audio.volume * 100)); }
  DECKB.sink = pp.sink_b || "";
  if (!PL2.ready) return;
  pl2Layout();
  if (PL2.deck2) dbSinks();
}

function pl2Pref(k, v) {
  if (k === "layout") PL2.layout = v;
  else if (k === "top_collapsed") PL2.collapsed = !!v;
  else if (k === "deck2") { PL2.deck2 = !!v; if (!v) { DECKB.audio.pause(); PLAYER.target = "A"; } else dbSinks(); }
  else if (k === "deck_target") PLAYER.target = v === "B" && PL2.deck2 ? "B" : "A";
  else if (k === "sink_b") DECKB.sink = v;
  else if (k === "vol_b") { DECKB.audio.volume = v; return; }
  pl2Layout();
  plRender();
}

function pl2Key(e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "P" && e.shiftKey && PL2.layout === "top" && !DET.on) { e.preventDefault(); plTopFold(); }
  else if ((e.key === "b" || e.key === "B") && !e.shiftKey && PL2.deck2) { e.preventDefault(); dbTargetSet(PLAYER.target === "B" ? "A" : "B"); }
}

function initPlayer2(pp) {
  const b = new Audio();
  b.preload = "metadata";
  DECKB.audio = b;
  ["play", "pause", "ended", "loadedmetadata", "emptied", "timeupdate"].forEach((ev) => b.addEventListener(ev, dbRender));
  b.addEventListener("error", () => { if (b.src) toast("Player B: Datei kann nicht abgespielt werden."); });
  PL2.home = $("#player").parentElement;
  PL2.ready = true;
  pl2Apply(pp);
  $("#plTopFold").addEventListener("click", () => plTopFold());
  $("#plDetach").addEventListener("click", plDetach);
  $("#plDockChip").addEventListener("click", plDock);
  $("#dbPlay").addEventListener("click", () => { if (!DECKB.audio.src) dbLoad(plTarget()); else dbToggle(); });
  $("#dbClose").addEventListener("click", () => plSetPref("deck2", false));
  $("#dbTarget").addEventListener("click", (e) => { const t = e.target.closest("[data-v]"); if (t) dbTargetSet(t.dataset.v); });
  $("#dbSeek").addEventListener("input", (e) => { b.currentTime = (+e.target.value) / 10; dbRender(); });
  $("#dbVol").addEventListener("input", (e) => plSetPref("vol_b", (+e.target.value) / 100));
  $("#dbSink").addEventListener("change", (e) => {
    const v = e.target.value;
    b.setSinkId(v).then(() => { plSetPref("sink_b", v); toast("Ausgabegerät für Player B gesetzt."); }).catch((x) => toast("Ausgabegerät nicht verfügbar: " + (x.message || x)));
  });
  window.addEventListener("resize", dbRender);
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
    showMenu(e.clientX, e.clientY, [
      { label: "Links in Player A abspielen", run: () => plLoad({ kind: "side", ref: "L" }) },
      { label: "Rechts in Player A abspielen", run: () => plLoad({ kind: "side", ref: "R" }) },
      "-",
      { label: "Links in Player B laden", run: () => dbLoad({ kind: "side", ref: "L" }) },
      { label: "Rechts in Player B laden", run: () => dbLoad({ kind: "side", ref: "R" }) },
    ]);
  });
}
