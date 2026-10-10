/* MarKusSXCH TagStudio – abgedockter Player (#69). Zeigt den Player des Hauptfensters in einem eigenen Fenster
   (z. B. auf einem zweiten Bildschirm) und steuert ihn. Die Wiedergabe bleibt im Hauptfenster – beim Ab- und
   Andocken läuft sie an derselben Stelle weiter. Verbindung über den Nachrichten-Kanal der Sitzung (bus_*). */
"use strict";

const TOKEN = new URLSearchParams(location.hash.slice(1)).get("token") || "";
const pywebviewReady = new Promise((resolve) => {
  if (TOKEN) return resolve(false);
  if (window.pywebview && window.pywebview.api) return resolve(true);
  window.addEventListener("pywebviewready", () => resolve(true));
});
async function call(name, ...args) {
  if (await pywebviewReady) return window.pywebview.api[name](...args);
  const res = await fetch("/api/" + name, { method: "POST", headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(args) });
  const j = await res.json();
  if (!j.ok) throw new Error(j.error || "Fehler");
  return j.result;
}
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtTime = (s) => { if (!isFinite(s) || s < 0) s = 0; return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; };
const ICON_PLAY = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4v16l13-8Z"/></svg>';
const ICON_PAUSE = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4h3v16H7zM14 4h3v16h-3z"/></svg>';

const PW = { seq: 0, st: {}, wave: null, at: 0, lastPoll: 0, closed: false, geomT: 0, geom: "" };

function send(cmd, extra = {}) { return call("bus_post", "pl_cmd", { cmd, ...extra }).catch(() => {}); }

/** aktuelle Zeit zwischen zwei Zuständen weiterzählen (flüssige Anzeige) */
function nowT() {
  const s = PW.st;
  return s.paused || !s.on ? s.t || 0 : Math.min(s.dur || 0, (s.t || 0) + (performance.now() - PW.at) / 1000);
}

function keyBadge(code) {
  if (!code) return "";
  const n = parseInt(code, 10), minor = code.endsWith("A"), h = (180 - (n - 1) * 30 + 720) % 360;
  const fg = h >= 35 && h <= 195 ? "#15181F" : "#FFFFFF";
  return `<span class="kb" style="--kc:hsl(${h} ${minor ? "58% 56%" : "62% 46%"});--kt:${fg}">${esc(code)}</span>`;
}

function render() {
  const s = PW.st;
  document.documentElement.dataset.theme = s.theme || "dark";
  $("#pw").classList.toggle("on", !!s.on);
  $("#pwTitle").textContent = s.on ? (s.title ? `${s.artist ? s.artist + " – " : ""}${s.title}` : s.name) : "Kein Titel – im Hauptfenster markieren und Leertaste";
  $("#pwSub").textContent = s.on ? `${s.name || ""}${s.stem ? " · " + s.stem : ""}` : "";
  $("#pwTitle").title = s.path || "";
  const alt = s.key_alt ? [s.key_alt.musical, s.key_alt.openkey].filter(Boolean) : [];
  const bpm = s.bpm ? String(Math.round(parseFloat(String(s.bpm).replace(",", ".")) || 0) || s.bpm) : "";
  const meta = s.on ? `${keyBadge(s.key)}${alt.length ? `<span class="pl-key-alt">${esc(alt.join(" · "))}</span>` : ""}${bpm ? `<span class="pl-bpm">${esc(bpm)} BPM</span>` : ""}` : "";
  if ($("#pwMeta").dataset.v !== meta) { $("#pwMeta").innerHTML = meta; $("#pwMeta").dataset.v = meta; }
  let rh = "";
  if (s.on && s.markable) {
    rh = '<span class="rate" role="group" aria-label="Bewertung">';
    for (let n = 1; n <= 5; n++) rh += `<button class="rs${n <= s.rating ? " on" : ""}" data-star="${n}" title="${n} Stern${n > 1 ? "e" : ""} (${n})">★</button>`;
    rh += `<button class="rl${s.like ? " on" : ""}" data-like="1" title="Like (F)">♥</button></span>`;
  }
  if ($("#pwRate").dataset.v !== rh) { $("#pwRate").innerHTML = rh; $("#pwRate").dataset.v = rh; }
  $("#pwPlay").innerHTML = s.paused || !s.on ? ICON_PLAY : ICON_PAUSE;
  $("#pwLive").classList.toggle("on", !!s.live);
  $("#pwRepeat").classList.toggle("on", !!s.repeat);
  $("#pwAB").classList.toggle("on", !!s.ab); $("#pwAB").classList.toggle("half", s.ab === "half");
  $$("#pwStart button").forEach((b) => b.classList.toggle("on", b.dataset.v === s.start));
  if (!$("#pwVol").matches(":active")) $("#pwVol").value = String(Math.round((s.vol ?? 0.8) * 100));
  $("#pwVol").classList.toggle("muted", !!s.muted);
  cues();
  tick();
}

function cues() {
  const s = PW.st, dur = s.dur || 0, key = JSON.stringify([s.wkey, dur, s.cues]);
  if ($("#pwCues").dataset.v === key) return;
  $("#pwCues").dataset.v = key;
  $("#pwCues").innerHTML = dur && s.on ? (s.cues || []).map((c) => {
    const w = c.kind === "loop" && c.end ? `--w:${Math.max(2, ((c.end - c.pos) / dur) * $("#pwCues").clientWidth)}px;` : "";
    return `<button class="pl-cue${c.kind === "loop" ? " loop" : ""}" data-pos="${c.pos}" style="left:${(c.pos / dur) * 100}%;${c.color ? `--cue:${esc(c.color)};` : ""}${w}" title="${c.kind === "loop" ? "Loop" : "Cue"} ${c.index + 1}${c.name ? " · " + esc(c.name) : ""} · ${fmtTime(c.pos)}"></button>`;
  }).join("") : "";
}

/** Zeit, Suchleiste und Wellenform (flüssig, per requestAnimationFrame) */
function tick() {
  const s = PW.st, t = nowT(), dur = s.dur || 0, rest = Math.max(0, dur - t);
  $("#pwElapsed").textContent = fmtTime(t);
  $("#pwRemain").textContent = "−" + fmtTime(Math.ceil(rest - 0.001));
  $("#pwRemain").classList.toggle("end", !!s.on && dur > 0 && rest <= 30);
  $("#pwLen").textContent = fmtTime(dur);
  const seek = $("#pwSeek");
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(t * 10)); }
  seek.disabled = !s.on;
  drawWave(dur ? t / dur : 0);
}

function drawWave(played) {
  const w = PW.st.on && PW.wave, box = $("#pwWave"), cv = $("#pwCanvas");
  box.classList.toggle("wave", !!w);
  if (!w || !cv.clientWidth) return;
  const dpr = window.devicePixelRatio || 1, W = Math.round(cv.clientWidth * dpr), H = Math.round(cv.clientHeight * dpr);
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

async function poll() {
  try {
    const r = await call("bus_poll", "pl_state", PW.seq);
    PW.seq = r.seq;
    const last = r.msgs[r.msgs.length - 1];
    for (const m of r.msgs) if (m && m.wave !== undefined) PW.wave = m.wave;
    if (last && last.closed) { PW.closed = true; window.close(); return; }
    if (last) { PW.st = last; PW.at = performance.now(); render(); }
  } catch (e) { /* Hauptfenster beschäftigt – nächster Versuch */ }
  saveGeom();
  setTimeout(poll, 200);
}

/** Fenstergrösse und -position merken (#69) */
function saveGeom() {
  const g = { x: window.screenX, y: window.screenY, w: window.outerWidth, h: window.outerHeight };
  const k = JSON.stringify(g);
  if (k === PW.geom || !g.w) return;
  PW.geom = k;
  clearTimeout(PW.geomT);
  PW.geomT = setTimeout(() => call("set_player_window", g).catch(() => {}), 800);
}

function init() {
  render();
  (function loop() { tick(); requestAnimationFrame(loop); })();
  send("hello");
  poll();
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.id === "pwDock") { send("dock"); return; }
    if (b.dataset.cmd) send(b.dataset.cmd);
    else if (b.dataset.star) send("rate", { n: +b.dataset.star === PW.st.rating ? 0 : +b.dataset.star });
    else if (b.dataset.like) send("like");
    else if (b.dataset.v && b.closest("#pwStart")) send("start", { v: b.dataset.v });
    else if (b.dataset.pos) send("seek", { t: +b.dataset.pos });
  });
  $("#pwSeek").addEventListener("change", (e) => send("seek", { t: (+e.target.value) / 10 }));
  let vt = 0;
  $("#pwVol").addEventListener("input", (e) => { clearTimeout(vt); vt = setTimeout(() => send("vol", { v: (+e.target.value) / 100 }), 60); });
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey) return;
    const k = e.key;
    let c = null;
    if (k === " ") c = ["toggle"];
    else if (k === "ArrowDown" || k === "ArrowUp") c = [k === "ArrowDown" ? "down" : "up"];
    else if (e.shiftKey && (k === "ArrowRight" || k === "ArrowLeft")) c = ["seekby", { s: k === "ArrowRight" ? 10 : -10 }];
    else if (e.altKey && (k === "PageDown" || k === "PageUp")) c = ["cue", { dir: k === "PageDown" ? 1 : -1 }];
    else if (/^[0-5]$/.test(k)) c = ["rate", { n: +k === PW.st.rating ? 0 : +k }];
    else if (k === "f" || k === "F") c = ["like"];
    else if (k === "r" || k === "R") c = ["repeat"];
    else if (k === "l" || k === "L") c = ["ab"];
    else if (k === "m" || k === "M") c = ["mute"];
    else if (k === "s" || k === "S") c = ["stem", { dir: e.shiftKey ? -1 : 1 }];
    if (!c) return;
    e.preventDefault();
    send(...c);
  });
  window.addEventListener("resize", () => { $("#pwCues").dataset.v = ""; render(); });
  window.addEventListener("pagehide", () => {        // Fenster geschlossen → Hauptfenster dockt wieder an
    if (PW.closed) return;
    if (TOKEN) fetch("/api/bus_post", { method: "POST", keepalive: true, headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(["pl_cmd", { cmd: "dock" }]) }).catch(() => {});
    else send("dock");
  });
}

init();
