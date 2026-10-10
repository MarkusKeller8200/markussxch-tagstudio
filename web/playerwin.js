/* MarKusSXCH TagStudio – abgedockter Player (#69, #101). Zeigt Player A (und Player B, wenn eingeschaltet) des
   Hauptfensters in einem eigenen Fenster – mit Cover – und steuert sie. Die Wiedergabe bleibt im Hauptfenster; beim
   Ab- und Andocken läuft sie an derselben Stelle weiter. Verbindung über den Nachrichten-Kanal der Sitzung (bus_*). */
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
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtTime = (s) => { if (!isFinite(s) || s < 0) s = 0; return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`; };
const ICON_PLAY = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4v16l13-8Z"/></svg>';
const ICON_PAUSE = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4h3v16H7zM14 4h3v16h-3z"/></svg>';
const ICON_NOTE = '<svg class="i" viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>';

const PW = { seq: 0, st: {}, at: 0, closed: false, geomT: 0, geom: "", deck: {} };

function send(cmd, extra = {}) { return call("bus_post", "pl_cmd", { cmd, ...extra }).catch(() => {}); }

function deckHtml(d) {
  return `<section class="pw" data-deck="${d}" role="group" aria-label="Player ${d}">
    <button class="pl-tag" data-cmd="target" title="Player ${d} – Klick: Markierung, Leertaste und Tasten wirken auf Player ${d}">${d}</button>
    <div class="pw-cover" title=""></div>
    <div class="pw-main">
      <div class="pw-head">
        <div class="pw-title"><b class="pw-t">–</b><span class="pw-sub muted"></span></div>
        <div class="pw-meta"></div>
        <span class="pw-rate"></span>
      </div>
      <div class="pl-wave pw-wave"><canvas aria-hidden="true"></canvas><input type="range" class="pw-seek" min="0" max="1" value="0" step="1" aria-label="Position Player ${d}"><div class="pl-cues"></div></div>
      <div class="pw-bar">
        <button class="icon-btn" data-cmd="prev" title="Voriger Titel" aria-label="Voriger Titel"><svg class="i" viewBox="0 0 24 24"><path d="M6 5v14"/><path d="M19 5 9 12l10 7Z"/></svg></button>
        <button class="icon-btn pl-play" data-cmd="toggle" aria-label="Abspielen"></button>
        <button class="icon-btn" data-cmd="next" title="Nächster Titel" aria-label="Nächster Titel"><svg class="i" viewBox="0 0 24 24"><path d="M18 5v14"/><path d="M5 5l10 7-10 7Z"/></svg></button>
        ${d === "A" ? `<button class="icon-btn pl-tog pw-live" data-cmd="live" title="Live-Vorschau" aria-label="Live-Vorschau"><svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="2.5"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4"/><path d="M16.2 7.8a6 6 0 0 1 0 8.4"/><path d="M5 5a10 10 0 0 0 0 14"/><path d="M19 5a10 10 0 0 1 0 14"/></svg></button>` : '<span class="icon-btn pl-ph" aria-hidden="true"></span>'}
        <button class="icon-btn pl-tog pw-repeat" data-cmd="repeat" title="Titel wiederholen (R)" aria-label="Titel wiederholen"><svg class="i" viewBox="0 0 24 24"><path d="M17 2l3 3-3 3"/><path d="M4 11V9a4 4 0 0 1 4-4h12"/><path d="M7 22l-3-3 3-3"/><path d="M20 13v2a4 4 0 0 1-4 4H4"/></svg></button>
        <button class="icon-btn pl-tog pl-ab-btn pw-ab" data-cmd="ab" title="A–B-Schleife (L)" aria-label="A–B-Schleife">A–B</button>
        <div class="pw-time"><span class="pw-el">0:00</span><span class="pw-rem pl-remain">−0:00</span><span class="pw-len muted">0:00</span></div>
        <div class="grow"></div>
        <div class="seg sm pl-start pw-start" title="Startpunkt beim Abspielen"><button data-v="0">Start</button><button data-v="30">30 %</button><button data-v="60">1:00</button><button data-v="cue">Cue</button></div>
        <input type="range" class="pw-vol" min="0" max="100" value="80" title="Lautstärke (M: stumm)" aria-label="Lautstärke Player ${d}">
        ${d === "A" ? '<button class="icon-btn pw-dock" data-dock="1" title="Andocken: Player wieder ins Hauptfenster holen" aria-label="Andocken"><svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M14 10H9V5"/><path d="m9 10 7-7"/></svg></button>' : '<span class="icon-btn pl-ph" aria-hidden="true"></span>'}
      </div>
    </div>
  </section>`;
}

/** aktuelle Zeit zwischen zwei Zuständen weiterzählen (flüssige Anzeige) */
function nowT(s) {
  return s.paused || !s.on ? s.t || 0 : Math.min(s.dur || 0, (s.t || 0) + ((performance.now() - PW.at) / 1000) * (s.rate || 1));
}

function keyBadge(code) {
  if (!code) return "";
  const n = parseInt(code, 10), minor = code.endsWith("A"), h = (180 - (n - 1) * 30 + 720) % 360;
  const fg = h >= 35 && h <= 195 ? "#15181F" : "#FFFFFF";
  return `<span class="kb" style="--kc:hsl(${h} ${minor ? "58% 56%" : "62% 46%"});--kt:${fg}">${esc(code)}</span>`;
}

function bpmText(s) {
  const b = parseFloat(String(s.bpm || "").replace(",", "."));
  if (!b) return "";
  const r = s.rate || 1;
  if (Math.abs(r - 1) < 0.001) return `${Math.round(b)} BPM`;
  return `${(b * r).toFixed(1)} BPM <span class="muted">(${r > 1 ? "+" : ""}${((r - 1) * 100).toFixed(1)} %)</span>`;
}

function setHtml(el, h) { if (el.dataset.v !== h) { el.innerHTML = h; el.dataset.v = h; } }

function renderDeck(d) {
  const box = $(`.pw[data-deck="${d}"]`), s = PW.st[d] || {}, P = PW.deck[d] || (PW.deck[d] = {});
  if (!box) return;
  box.classList.toggle("on", !!s.on);
  box.classList.toggle("target", PW.st.two && PW.st.target === d);
  $(".pl-tag", box).classList.toggle("on", PW.st.two && PW.st.target === d);
  $(".pw-t", box).textContent = s.on ? (s.title ? `${s.artist ? s.artist + " – " : ""}${s.title}` : s.name) : (d === "A" ? "Kein Titel – im Hauptfenster markieren und Leertaste" : "Player B: Titel im Hauptfenster per Rechtsklick laden");
  $(".pw-sub", box).textContent = s.on ? `${s.name || ""}${s.stem ? " · " + s.stem : ""}` : "";
  $(".pw-t", box).title = s.path || "";
  const alt = s.key_alt ? [s.key_alt.musical, s.key_alt.openkey].filter(Boolean) : [];
  setHtml($(".pw-meta", box), s.on ? `${keyBadge(s.key)}${alt.length ? `<span class="pl-key-alt">${esc(alt.join(" · "))}</span>` : ""}${s.bpm ? `<span class="pl-bpm">${bpmText(s)}</span>` : ""}` : "");
  let rh = "";
  if (s.on && s.markable) {
    rh = '<span class="rate" role="group" aria-label="Bewertung">';
    for (let n = 1; n <= 5; n++) rh += `<button class="rs${n <= s.rating ? " on" : ""}" data-star="${n}" title="${n} Stern${n > 1 ? "e" : ""}">★</button>`;
    rh += `<button class="rl${s.like ? " on" : ""}" data-like="1" title="Like">♥</button></span>`;
  }
  setHtml($(".pw-rate", box), rh);
  $(".pl-play", box).innerHTML = s.paused || !s.on ? ICON_PLAY : ICON_PAUSE;
  const live = $(".pw-live", box); if (live) live.classList.toggle("on", !!s.live);
  $(".pw-repeat", box).classList.toggle("on", !!s.repeat);
  $(".pw-ab", box).classList.toggle("on", !!s.ab); $(".pw-ab", box).classList.toggle("half", s.ab === "half");
  $$(".pw-start button", box).forEach((b) => b.classList.toggle("on", b.dataset.v === s.start));
  const vol = $(".pw-vol", box);
  if (!vol.matches(":active")) vol.value = String(Math.round((s.vol ?? 0.8) * 100));
  vol.classList.toggle("muted", !!s.muted);
  // Cover (#101): bei neuem Titel nachladen
  const ck = s.on ? `${s.kind}|${s.ref}|${s.path}` : "";
  if (P.coverKey !== ck) {
    P.coverKey = ck;
    const cv = $(".pw-cover", box);
    cv.innerHTML = ICON_NOTE; cv.title = "kein Cover";
    if (ck) call("media_cover", s.kind, s.ref, 300).then((r) => {
      if (P.coverKey !== ck) return;
      if (r && r.src) { cv.innerHTML = `<img src="${r.src}" alt="Cover">`; cv.title = r.desc || ""; }
    }).catch(() => {});
  }
  cues(d, box, s);
  tick(d);
}

function cues(d, box, s) {
  const el = $(".pl-cues", box), dur = s.dur || 0, key = JSON.stringify([s.wkey, dur, s.cues, el.clientWidth]);
  if (el.dataset.v === key) return;
  el.dataset.v = key;
  el.innerHTML = dur && s.on ? (s.cues || []).map((c) => {
    const w = c.kind === "loop" && c.end ? `--w:${Math.max(2, ((c.end - c.pos) / dur) * el.clientWidth)}px;` : "";
    return `<button class="pl-cue${c.kind === "loop" ? " loop" : ""}" data-pos="${c.pos}" style="left:${(c.pos / dur) * 100}%;${c.color ? `--cue:${esc(c.color)};` : ""}${w}" title="${c.kind === "loop" ? "Loop" : "Cue"} ${c.index + 1}${c.name ? " · " + esc(c.name) : ""} · ${fmtTime(c.pos)}"></button>`;
  }).join("") : "";
}

/** Zeit, Suchleiste und Wellenform (flüssig, per requestAnimationFrame) */
function tick(d) {
  const box = $(`.pw[data-deck="${d}"]`), s = PW.st[d];
  if (!box || !s) return;
  const t = nowT(s), dur = s.dur || 0, rest = Math.max(0, dur - t);
  $(".pw-el", box).textContent = fmtTime(t);
  $(".pw-rem", box).textContent = "−" + fmtTime(Math.ceil(rest - 0.001));
  $(".pw-rem", box).classList.toggle("end", !!s.on && dur > 0 && rest <= 30);
  $(".pw-len", box).textContent = fmtTime(dur);
  const seek = $(".pw-seek", box);
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(t * 10)); }
  seek.disabled = !s.on;
  drawWave($(".pw-wave", box), $("canvas", box), s.on && (PW.deck[d] || {}).wave, dur ? t / dur : 0);
}

function drawWave(box, cv, w, played) {
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

function render() {
  const st = PW.st;
  document.documentElement.dataset.theme = st.theme || "dark";
  const want = st.two ? ["A", "B"] : ["A"], box = $("#pwDecks");
  if (box.dataset.decks !== want.join()) { box.innerHTML = want.map(deckHtml).join(""); box.dataset.decks = want.join(); }
  box.classList.toggle("two", !!st.two);
  want.forEach(renderDeck);
}

async function poll() {
  try {
    const r = await call("bus_poll", "pl_state", PW.seq);
    PW.seq = r.seq;
    for (const m of r.msgs) for (const d of ["A", "B"]) if (m && m[d] && m[d].wave !== undefined) (PW.deck[d] || (PW.deck[d] = {})).wave = m[d].wave;
    const last = r.msgs[r.msgs.length - 1];
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

const tgt = () => (PW.st.two && PW.st.target === "B" ? "B" : "A");

function init() {
  render();
  (function loop() { ["A", "B"].forEach(tick); requestAnimationFrame(loop); })();
  send("hello");
  poll();
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button"), sec = e.target.closest(".pw");
    if (!b || !sec) return;
    const deck = sec.dataset.deck, s = PW.st[deck] || {};
    if (b.dataset.dock) send("dock");
    else if (b.dataset.cmd) send(b.dataset.cmd, { deck });
    else if (b.dataset.star) send("rate", { deck, n: +b.dataset.star === s.rating ? 0 : +b.dataset.star });
    else if (b.dataset.like) send("like", { deck });
    else if (b.dataset.v && b.closest(".pw-start")) send("start", { deck, v: b.dataset.v });
    else if (b.dataset.pos) send("seek", { deck, t: +b.dataset.pos });
  });
  document.addEventListener("change", (e) => {
    const sec = e.target.closest(".pw");
    if (sec && e.target.classList.contains("pw-seek")) send("seek", { deck: sec.dataset.deck, t: (+e.target.value) / 10 });
  });
  let vt = 0;
  document.addEventListener("input", (e) => {
    const sec = e.target.closest(".pw");
    if (!sec || !e.target.classList.contains("pw-vol")) return;
    clearTimeout(vt); vt = setTimeout(() => send("vol", { deck: sec.dataset.deck, v: (+e.target.value) / 100 }), 60);
  });
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey) return;
    const k = e.key, deck = tgt(), s = PW.st[deck] || {};
    let c = null;
    if (k === " ") c = ["toggle"];
    else if (k === "ArrowDown" || k === "ArrowUp") c = [k === "ArrowDown" ? "down" : "up"];
    else if (e.shiftKey && (k === "ArrowRight" || k === "ArrowLeft")) c = ["seekby", { s: k === "ArrowRight" ? 10 : -10 }];
    else if (e.altKey && (k === "PageDown" || k === "PageUp")) c = ["cue", { dir: k === "PageDown" ? 1 : -1 }];
    else if (/^[0-5]$/.test(k)) c = ["rate", { n: +k === s.rating ? 0 : +k }];
    else if (k === "f" || k === "F") c = ["like"];
    else if (k === "r" || k === "R") c = ["repeat"];
    else if (k === "l" || k === "L") c = ["ab"];
    else if (k === "m" || k === "M") c = ["mute"];
    else if ((k === "b" || k === "B") && PW.st.two) c = ["target", { deck: deck === "A" ? "B" : "A" }];
    else if ((k === "s" || k === "S") && deck === "A") c = ["stem", { dir: e.shiftKey ? -1 : 1 }];
    if (!c) return;
    e.preventDefault();
    send(c[0], { deck, ...(c[1] || {}) });
  });
  window.addEventListener("resize", () => { $$(".pl-cues").forEach((x) => { x.dataset.v = ""; }); render(); });
  window.addEventListener("pagehide", () => {        // Fenster geschlossen → Hauptfenster dockt wieder an
    if (PW.closed) return;
    if (TOKEN) fetch("/api/bus_post", { method: "POST", keepalive: true, headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(["pl_cmd", { cmd: "dock" }]) }).catch(() => {});
    else send("dock");
  });
}

init();
