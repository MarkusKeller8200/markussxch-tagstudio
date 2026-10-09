/* MarKusSXCH TagStudio – Vorschau-Player (unten in der Aktionsleiste) und externe Player.
   Leertaste: markierten Titel abspielen/pausieren · Shift+←/→: ±10 s · Alt+Bild↑/↓: voriger/nächster Cue ·
   Strg/Cmd+P: im externen Player öffnen. Wellenform: einmal per Web Audio berechnet, im Cache (waveform.py);
   Cue-Marken aus Serato/Mixed In Key (cues.py).
   Im Tagger spielt der Player beim Wechsel der Markierung (↑/↓, Klick) automatisch weiter („Durchhören“).
   Im Vergleich schaltet A/B zwischen linker und rechter Datei um und behält die Position. */
"use strict";

const PLAYER = { audio: null, info: null, kind: null, ref: null, side: "L", loading: false, follow: true, startAt: "0",
  wave: true, waveBusy: null, loop: null, raf: 0 };
const WAVE_N = 800;               // Balken der Wellenform (im Cache gespeichert)
const WAVE_MAX_BYTES = 80e6;      // sehr lange Mixe nicht dekodieren (Speicher)

const ICON_PLAY = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4v16l13-8Z"/></svg>';
const ICON_PAUSE = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4h3v16H7zM14 4h3v16h-3z"/></svg>';

/** Player-Einstellung ändern und in den Einstellungen (~/.tagstudio.json, Gruppe „Player“) merken. */
let plVolTimer = null;
function plSetPref(k, v) {
  if (k === "start") { PLAYER.startAt = v; plStartSync(); }
  else if (k === "wave") { PLAYER.wave = !!v; if (PLAYER.wave && PLAYER.info && !PLAYER.info.wave) plWaveCompute(PLAYER.info); plRender(); }
  else if (k === "follow") PLAYER.follow = !!v;
  else if (k === "vol") { clearTimeout(plVolTimer); plVolTimer = setTimeout(() => call("set_player_pref", "vol", v).catch(() => {}), 400); return; }
  call("set_player_pref", k, v).catch(() => {});
}

/** Startpunkt-Umschalter (#36) */
function plStartSync() {
  $$("#plStart button").forEach((b) => { const on = b.dataset.v === PLAYER.startAt; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); });
}

function plStore(k, v) {
  try { if (v === undefined) return localStorage.getItem("ts_pl_" + k); localStorage.setItem("ts_pl_" + k, String(v)); } catch (e) { /* egal */ }
  return null;
}
const fmtTime = (s) => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60), r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
};

/** Was soll gespielt werden? → {kind, ref} oder null */
function plTarget() {
  if (S.module === "tagger" && typeof tgSelected === "function") {
    const sel = tgSelected();
    const i = sel.length ? (TG.sel.has(TG.anchor) ? TG.anchor : sel[0]) : null;
    return i === null || i === undefined ? null : { kind: "tag", ref: i };
  }
  if (S.module === "compare" && S.cur !== null && S.cur !== undefined) return { kind: "side", ref: PLAYER.side };
  return null;
}

async function plLoad(target, autoplay = true, keepTime = null) {
  if (!target) { toast(S.module === "tagger" ? "Erst einen Titel markieren." : "Erst ein Dateipaar wählen."); return; }
  PLAYER.loading = true;
  let info;
  try { info = await call("media_url", target.kind, target.ref); } catch (e) { PLAYER.loading = false; toast(String(e.message || e)); return; }
  PLAYER.info = info; PLAYER.kind = target.kind; PLAYER.ref = target.ref;
  const a = PLAYER.audio;
  plLoopSet(null);
  a.src = info.url;
  const dur = info.duration || 0;
  const firstCue = (info.cues || []).find((c) => c.pos > 0.05);
  const start = keepTime !== null ? keepTime : PLAYER.startAt === "30" ? dur * 0.3 : PLAYER.startAt === "60" ? Math.min(60, dur * 0.5)
    : PLAYER.startAt === "cue" ? (firstCue ? firstCue.pos : 0) : 0;
  const seek = () => { try { if (start > 0) a.currentTime = Math.min(start, (a.duration || dur) - 1); } catch (e) { /* egal */ } };
  a.addEventListener("loadedmetadata", seek, { once: true });
  plCues();
  plRender();
  if (PLAYER.wave && !info.wave) plWaveCompute(info);
  if (autoplay) {
    try { await a.play(); } catch (e) {
      // AbortError: schneller Titelwechsel – der neue Titel lädt bereits, kein Fehler
      if (e.name !== "AbortError") toast("Wiedergabe nicht möglich: " + (e.message || e));
    }
  }
  PLAYER.loading = false;
}

function plSame(t) { return t && PLAYER.info && t.kind === PLAYER.kind && t.ref === PLAYER.ref; }

async function plToggle() {
  const t = plTarget();
  if (!PLAYER.audio.src || (t && !plSame(t) && !(t.kind === "side" && PLAYER.kind === "side"))) return plLoad(t);
  if (t && t.kind === "side" && PLAYER.kind === "side" && PLAYER.info && PLAYER.info.ref !== PLAYER.side) return plLoad(t, true);
  if (PLAYER.audio.paused) { try { await PLAYER.audio.play(); } catch (e) { toast(String(e.message || e)); } } else PLAYER.audio.pause();
}

/** Markierung hat sich geändert (Tagger/Vergleich): beim Abspielen gleich weiter mit dem neuen Titel. */
function playerFollow() {
  if (!PLAYER.audio || PLAYER.audio.paused || !PLAYER.follow || PLAYER.loading) { plRender(); return; }
  const t = plTarget();
  if (t && !plSame(t)) plLoad(t, true);
}

async function plStep(dir) {
  if (S.module === "tagger" && TG.order.length) {
    const k = Math.max(0, Math.min(TG.order.length - 1, TG.order.indexOf(TG.anchor) + dir));
    const i = TG.order[k];
    const wasPlaying = !PLAYER.audio.paused;
    await tgSelect(i, {});          // beim Abspielen übernimmt playerFollow() den neuen Titel
    tgScrollTo(i);
    if (!wasPlaying) plLoad(plTarget(), true);
  } else if (S.module === "compare" && S.visible && S.visible.length) {
    const k = Math.max(0, Math.min(S.visible.length - 1, S.visible.indexOf(S.cur) + dir));
    const wasPlaying = !PLAYER.audio.paused;
    await selectPair(S.visible[k]);
    if (!wasPlaying) plLoad(plTarget(), true);
  }
}

function plSide(side) {
  PLAYER.side = side;
  if (PLAYER.kind === "side" && PLAYER.audio.src) plLoad({ kind: "side", ref: side }, !PLAYER.audio.paused, PLAYER.audio.currentTime);
  else plRender();
}

function plRender() {
  const a = PLAYER.audio;
  if (!a) return;
  const bar = $("#player");
  bar.classList.toggle("on", !!a.src);
  $("#plPlay").innerHTML = a.paused ? ICON_PLAY : ICON_PAUSE;
  $("#plPlay").title = a.paused ? "Abspielen (Leertaste)" : "Pause (Leertaste)";
  const i = PLAYER.info;
  $("#plTitle").textContent = i ? (i.title ? `${i.artist ? i.artist + " – " : ""}${i.title}` : i.name) : "Vorhören: Titel markieren, Leertaste";
  $("#plTitle").title = i ? i.path : "";
  // #46: Tonart und Tempo des laufenden Titels
  const bpm = i && i.bpm ? String(Math.round(parseFloat(String(i.bpm).replace(",", ".")) || 0) || i.bpm) : "";
  const meta = i ? `${i.key && typeof keyBadge === "function" ? keyBadge(i.key) : ""}${bpm ? `<span class="pl-bpm">${esc(bpm)} BPM</span>` : ""}` : "";
  if ($("#plMeta").dataset.v !== meta) { $("#plMeta").innerHTML = meta; $("#plMeta").dataset.v = meta; }
  $("#plVol").classList.toggle("muted", a.muted);
  $("#plVol").title = a.muted ? "Stumm (M)" : "Lautstärke (M: stumm)";
  const dur = a.duration || (i && i.duration) || 0;
  $("#plTime").textContent = i ? `${fmtTime(a.currentTime)} / ${fmtTime(dur)}` : "";
  const seek = $("#plSeek");
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(a.currentTime * 10)); }
  seek.disabled = !i;
  plDrawWave();
  $("#plAB").hidden = S.module !== "compare";
  const hasCues = !!(i && i.cues && i.cues.length);
  $("#plCuePrev").hidden = $("#plCueNext").hidden = !hasCues;      // Cue-Sprünge (#37)
  $$("#plAB button").forEach((b) => b.classList.toggle("on", b.dataset.side === PLAYER.side));
}

function plSeekBy(sec) {
  if (!PLAYER.audio.src) return;
  PLAYER.audio.currentTime = Math.max(0, Math.min((PLAYER.audio.duration || 0) - 0.5, PLAYER.audio.currentTime + sec));
  plRender();
}

// ---------------------------------------------------------------------- Wellenform & Cue-Marken
/** Wellenform einmal berechnen (Web Audio, niedrige Abtastrate spart Speicher) und im Cache ablegen. */
async function plWaveCompute(info) {
  if (!info.wave_key || PLAYER.waveBusy === info.wave_key) return;
  PLAYER.waveBusy = info.wave_key;
  try {
    const res = await fetch(info.url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    if (+(res.headers.get("Content-Length") || 0) > WAVE_MAX_BYTES) return;
    const buf = await res.arrayBuffer();
    const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    let audio = null;
    for (const rate of [8000, 22050, 44100]) {
      try { audio = await new OAC(1, 1, rate).decodeAudioData(buf.slice(0)); break; } catch (e) { audio = null; }
    }
    if (!audio) return;
    const ch = [...Array(audio.numberOfChannels).keys()].map((c) => audio.getChannelData(c));
    const len = ch[0].length, step = len / WAVE_N, peaks = [], rms = [];
    for (let b = 0; b < WAVE_N; b++) {
      const from = Math.floor(b * step), to = Math.max(from + 1, Math.floor((b + 1) * step));
      let pk = 0, sq = 0, n = 0;
      for (const d of ch) for (let k = from; k < to && k < len; k++) { const v = Math.abs(d[k]); if (v > pk) pk = v; sq += v * v; n++; }
      peaks.push(Math.min(255, Math.round(pk * 255)));
      rms.push(Math.min(255, Math.round(Math.sqrt(sq / Math.max(1, n)) * 255)));
    }
    const wave = { peaks, rms };
    call("wave_save", info.wave_key, peaks, rms).catch(() => {});
    if (PLAYER.info && PLAYER.info.wave_key === info.wave_key) { PLAYER.info.wave = wave; plRender(); }
  } catch (e) { /* ohne Wellenform weiter – Wiedergabe ist wichtiger */ }
  finally { if (PLAYER.waveBusy === info.wave_key) PLAYER.waveBusy = null; }
}

function plDrawWave() {
  const box = $("#plWave"), cv = $("#plCanvas");
  const w = PLAYER.wave && PLAYER.info && PLAYER.info.wave;
  box.classList.toggle("wave", !!w);
  if (!w) return;
  const dpr = window.devicePixelRatio || 1, W = Math.max(1, Math.round(cv.clientWidth * dpr)), H = Math.max(1, Math.round(cv.clientHeight * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const g = cv.getContext("2d"), st = getComputedStyle(document.documentElement);
  const acc = st.getPropertyValue("--acc").trim() || "#7c5cff", dim = st.getPropertyValue("--faint").trim() || "#888";
  const a = PLAYER.audio, dur = a.duration || PLAYER.info.duration || 0, played = dur ? a.currentTime / dur : 0;
  const n = w.peaks.length, top = Math.max(1, ...w.peaks), bw = W / n, mid = H / 2;
  g.clearRect(0, 0, W, H);
  for (let k = 0; k < n; k++) {
    const x = k * bw, ph = Math.max(1, (w.peaks[k] / top) * (H - 2) / 2), rh = Math.max(0.5, (w.rms[k] / top) * (H - 2) / 2);
    const on = k / n < played;
    g.globalAlpha = on ? 0.45 : 0.3; g.fillStyle = on ? acc : dim;
    g.fillRect(x, mid - ph, Math.max(1, bw - 0.4), ph * 2);
    g.globalAlpha = on ? 1 : 0.75;
    g.fillRect(x, mid - rh, Math.max(1, bw - 0.4), rh * 2);
  }
  g.globalAlpha = 1; g.fillStyle = acc;
  g.fillRect(Math.round(played * W), 0, Math.max(1, Math.round(dpr)), H);
}

function plCues() {
  const box = $("#plCues"), i = PLAYER.info, cues = (i && i.cues) || [];
  const dur = (PLAYER.audio && PLAYER.audio.duration) || (i && i.duration) || 0;
  box.innerHTML = dur ? cues.map((c, k) => {
    const left = Math.max(0, Math.min(100, (c.pos / dur) * 100));
    const w = c.kind === "loop" && c.end ? `--w:${Math.max(2, ((c.end - c.pos) / dur) * box.clientWidth)}px;` : "";
    const label = `${c.kind === "loop" ? "Loop" : "Cue"} ${c.index + 1}${c.name ? " · " + c.name : ""} · ${fmtTime(c.pos)}${c.kind === "loop" && c.end ? `–${fmtTime(c.end)} · Klick: Schleife an/aus` : ""} (${c.source})`;
    return `<button class="pl-cue${c.kind === "loop" ? " loop" : ""}${PLAYER.loop && PLAYER.loop.k === k ? " on" : ""}" data-k="${k}" style="left:${left}%;${c.color ? `--cue:${esc(c.color)};` : ""}${w}" title="${esc(label)}" aria-label="${esc(label)}"></button>`;
  }).join("") : "";
}

/** #47: Serato-Loop als Schleife abspielen (null = aus) */
function plLoopSet(c) {
  PLAYER.loop = c && c.end > c.pos ? { pos: c.pos, end: c.end, k: c.k } : null;
  cancelAnimationFrame(PLAYER.raf);
  $$("#plCues .pl-cue.loop").forEach((b) => b.classList.toggle("on", !!PLAYER.loop && +b.dataset.k === PLAYER.loop.k));
  if (!PLAYER.loop) return;
  const tick = () => {
    const L = PLAYER.loop, a = PLAYER.audio;
    if (!L) return;
    if (a.currentTime >= L.end || a.currentTime < L.pos - 0.5) a.currentTime = L.pos;
    PLAYER.raf = requestAnimationFrame(tick);
  };
  PLAYER.raf = requestAnimationFrame(tick);
}

/** #48: Zeit (und nahen Cue) beim Überfahren der Leiste zeigen */
function plHover(e) {
  const box = $("#plWave"), tip = $("#plHover"), i = PLAYER.info;
  const dur = (PLAYER.audio && PLAYER.audio.duration) || (i && i.duration) || 0;
  if (!i || !dur || e.type === "mouseleave") { tip.hidden = true; return; }
  const r = box.getBoundingClientRect(), f = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), t = f * dur;
  const near = (i.cues || []).find((c) => Math.abs(c.pos - t) / dur < 0.012);
  tip.textContent = fmtTime(t) + (near ? ` · ${near.kind === "loop" ? "Loop" : "Cue"} ${near.index + 1}${near.name ? " " + near.name : ""}` : "");
  tip.hidden = false;
  tip.style.left = Math.max(0, Math.min(r.width - tip.offsetWidth, f * r.width - tip.offsetWidth / 2)) + "px";
}

/** Zum nächsten/vorigen Cue springen (Shift+↑/↓ bzw. Alt+←/→ im Player). */
function plCueJump(dir) {
  const cues = (PLAYER.info && PLAYER.info.cues) || [], t = PLAYER.audio.currentTime;
  if (!cues.length || !PLAYER.audio.src) return false;
  const c = dir > 0 ? cues.find((x) => x.pos > t + 0.3) : [...cues].reverse().find((x) => x.pos < t - 1);
  PLAYER.audio.currentTime = c ? c.pos : dir > 0 ? t : 0;
  plRender();
  return true;
}

// ---------------------------------------------------------------------- Externe Player
function plRefs() {
  if (S.module === "tagger") { const sel = tgSelected(); return sel.length ? { kind: "tag", refs: sel } : null; }
  if (S.module === "compare" && S.cur !== null) return { kind: "side", refs: [PLAYER.side] };
  return null;
}

async function plExternal(index = null) {
  const r = plRefs();
  if (!r) { toast("Erst Titel markieren."); return; }
  const res = await call("play_external", r.kind, r.refs, index);
  if (!res.ok) await info("Player konnte nicht gestartet werden", res.error);
  else toast(`${res.count} Titel in ${res.player} geöffnet.`);
}

async function plMenu(btn) {
  const list = await call("players");
  const r = btn.getBoundingClientRect();
  showMenu(r.left, r.top - 8 - (list.length + 4) * 34, [
    ...list.map((p, k) => ({ label: `Öffnen mit ${p.name}` + (k === 0 ? "  (Strg/Cmd+P)" : ""), run: () => plExternal(k) })),
    { label: "Öffnen mit Standardprogramm" + (list.length ? "" : "  (Strg/Cmd+P)"), run: () => plExternal(null) },
    "-",
    { label: "Player einrichten …", run: () => plSetup() },
    { label: (PLAYER.wave ? "✓ " : "    ") + "Wellenform anzeigen", run: () => plSetPref("wave", !PLAYER.wave) },
  ]);
}

async function plSetup() {
  let list = await call("players");
  const row = (p, k) => `<div class="pl-row" data-k="${k}">
      <input class="pl-name" value="${esc(p.name || "")}" placeholder="Name, z. B. foobar2000" aria-label="Name">
      <div class="pl-cmd"><input class="pl-path" value="${esc(p.cmd || "")}" placeholder="Programm, z. B. C:\\Program Files\\foobar2000\\foobar2000.exe" spellcheck="false" aria-label="Programm">
        <button class="ghost sm" data-browse="${k}" title="Programm wählen">…</button></div>
      <input class="pl-args" value="${esc(p.args || "{files}")}" spellcheck="false" aria-label="Argumente" title="Platzhalter: {files} alle Dateien · {file} erste Datei · {folder} Ordner · {m3u} Playlist">
      <button class="x del" data-del="${k}" title="Entfernen">✕</button></div>`;
  const draw = (b) => {
    $("#plList", b).innerHTML = list.length
      ? `<div class="pl-row pl-head"><span>Name</span><span>Programm</span><span>Argumente</span><span></span></div>${list.map(row).join("")}`
      : '<div class="muted">Noch kein Player eingerichtet – ohne Eintrag öffnet TagStudio das Standardprogramm des Systems.</div>';
  };
  const read = (b) => $$(".pl-row[data-k]", b).map((r) => ({
    name: $(".pl-name", r).value, cmd: $(".pl-path", r).value, args: $(".pl-args", r).value }));
  const res = await modal({
    title: "Externe Player", wide: true,
    html: `<div class="hint" style="margin-bottom:10px">Markierte Titel mit einem anderen Programm öffnen (Knopf ⋯ im Player oder Strg/Cmd+P für den ersten Eintrag).
      Argumente: <code>{files}</code> alle Dateien · <code>{file}</code> erste Datei · <code>{folder}</code> Ordner · <code>{m3u}</code> temporäre Playlist.
      Beispiele: foobar2000 <code>/add {files}</code> · VLC <code>--playlist-enqueue {files}</code> · macOS: Programm als <code>/Applications/VLC.app</code>.</div>
      <div id="plList" class="pl-list"></div><button class="ghost sm" id="plAdd" style="width:auto">+ Player hinzufügen</button>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }],
    onMount: (b) => {
      draw(b);
      b.addEventListener("click", async (e) => {
        const t = e.target.closest("button"); if (!t) return;
        if (t.id === "plAdd") { list = read(b); list.push({ name: "", cmd: "", args: "{files}" }); draw(b); $$(".pl-name", b).pop()?.focus(); }
        else if (t.dataset.del !== undefined) { list = read(b); list.splice(+t.dataset.del, 1); draw(b); }
        else if (t.dataset.browse !== undefined) {
          const p = await call("pick_file", "program", "");
          if (p) { list = read(b); list[+t.dataset.browse].cmd = p; if (!list[+t.dataset.browse].name) list[+t.dataset.browse].name = p.split(/[\\/]/).pop().replace(/\.(exe|app|bat|cmd)$/i, ""); draw(b); }
          else if (!S.settings.native) toast("Im Browser-Modus bitte den Pfad eintragen.");
        }
      });
    },
    collect: (b) => read(b),
  });
  if (res === null) return;
  const saved = await call("set_players", res);
  toast(`${saved.length} Player gespeichert.`);
}

// ---------------------------------------------------------------------- Einrichten
function initPlayer() {
  const a = new Audio();
  a.preload = "metadata";
  PLAYER.audio = a;
  const pp = (S.settings && S.settings.player) || { vol: 0.8, start: "0", follow: true, wave: true, saved: true };
  if (!pp.saved) {          // bis 3.2.0-beta.1 im Browser-Speicher → einmalig in die Einstellungen übernehmen
    const v = parseFloat(plStore("vol")), st = plStore("start");
    if (isFinite(v)) { pp.vol = Math.max(0, Math.min(1, v)); call("set_player_pref", "vol", pp.vol).catch(() => {}); }
    if (st && ["0", "30", "60", "cue"].includes(st)) { pp.start = st; call("set_player_pref", "start", st).catch(() => {}); }
    if (plStore("wave") === "0") { pp.wave = false; call("set_player_pref", "wave", false).catch(() => {}); }
    if (plStore("follow") === "0") { pp.follow = false; call("set_player_pref", "follow", false).catch(() => {}); }
  }
  a.volume = pp.vol;
  PLAYER.startAt = pp.start;
  PLAYER.follow = pp.follow;
  PLAYER.wave = pp.wave;
  ["play", "pause", "ended", "loadedmetadata", "emptied"].forEach((ev) => a.addEventListener(ev, plRender));
  a.addEventListener("loadedmetadata", plCues);
  $("#plWave").insertAdjacentHTML("beforeend", '<div class="pl-hover" id="plHover" hidden></div>');
  $("#plWave").addEventListener("mousemove", plHover);
  $("#plWave").addEventListener("mouseleave", plHover);
  window.addEventListener("resize", () => { plCues(); plDrawWave(); });
  $("#plCues").addEventListener("click", (e) => {
    const b = e.target.closest(".pl-cue"); if (!b || !PLAYER.info) return;
    const c = PLAYER.info.cues[+b.dataset.k];
    if (c.kind === "loop" && c.end) {            // #47: Loop an/aus
      if (PLAYER.loop && PLAYER.loop.k === +b.dataset.k) { plLoopSet(null); toast("Schleife aus."); return; }
      plLoopSet({ pos: c.pos, end: c.end, k: +b.dataset.k });
      toast(`Schleife ${fmtTime(c.pos)}–${fmtTime(c.end)} – erneut klicken zum Beenden.`);
    }
    a.currentTime = c.pos;
    if (a.paused) a.play().catch(() => {});
    plRender();
  });
  a.addEventListener("timeupdate", () => { const s = $("#plSeek"); if (!s.matches(":active")) plRender(); });
  a.addEventListener("ended", () => { if (PLAYER.follow && S.module === "tagger") plStep(1); });
  a.addEventListener("error", () => { if (a.src) toast("Datei kann nicht abgespielt werden."); });

  $("#plPlay").addEventListener("click", () => plToggle());
  $("#plPrev").addEventListener("click", () => plStep(-1));
  $("#plNext").addEventListener("click", () => plStep(1));
  $("#plSeek").addEventListener("input", (e) => { a.currentTime = (+e.target.value) / 10; $("#plTime").textContent = `${fmtTime(a.currentTime)} / ${fmtTime(a.duration)}`; });
  $("#plVol").value = String(Math.round(a.volume * 100));
  $("#plVol").addEventListener("input", (e) => { a.volume = (+e.target.value) / 100; plSetPref("vol", a.volume); });
  plStartSync();
  $("#plStart").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) plSetPref("start", b.dataset.v); });
  $("#plCuePrev").addEventListener("click", () => plCueJump(-1));
  $("#plCueNext").addEventListener("click", () => plCueJump(1));
  $("#plAB").addEventListener("click", (e) => { const b = e.target.closest("[data-side]"); if (b) plSide(b.dataset.side); });
  $("#plMore").addEventListener("click", (e) => plMenu(e.currentTarget));

  document.addEventListener("keydown", (e) => {
    const inField = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") && document.activeElement?.type !== "range";
    if (inField || !$("#modal").hidden || !$("#dialog").hidden || !$("#xmlEd").hidden) return;
    if (S.module !== "tagger" && S.module !== "compare") return;
    if (e.key === " " && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); plToggle(); }
    else if (e.shiftKey && (e.key === "ArrowRight" || e.key === "ArrowLeft") && PLAYER.audio.src) { e.preventDefault(); plSeekBy(e.key === "ArrowRight" ? 10 : -10); }
    else if ((e.key === "m" || e.key === "M") && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); PLAYER.audio.muted = !PLAYER.audio.muted; plRender(); toast(PLAYER.audio.muted ? "Stumm (M)" : "Ton an"); }   // #49
    else if (e.altKey && (e.key === "PageDown" || e.key === "PageUp") && PLAYER.audio.src) { e.preventDefault(); plCueJump(e.key === "PageDown" ? 1 : -1); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") { e.preventDefault(); call("players").then((l) => plExternal(l.length ? 0 : null)); }
  });
  plRender();
}
