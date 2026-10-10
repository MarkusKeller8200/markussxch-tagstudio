/* MarKusSXCH TagStudio – Web-Oberfläche. Ohne Bibliotheken; alle Arbeit erledigt der Python-Kern. */
"use strict";

// ====================================================================== Verbindung zum Python-Kern
const TOKEN = new URLSearchParams(location.hash.slice(1)).get("token") || "";
// Mit Zugangsschlüssel in der Adresse: Browser-Modus (lokaler Server); sonst App-Fenster (pywebview).
const pywebviewReady = new Promise((resolve) => {
  if (TOKEN) return resolve(false);
  if (window.pywebview && window.pywebview.api) return resolve(true);
  window.addEventListener("pywebviewready", () => resolve(true));
});

async function call(name, ...args) {
  if (await pywebviewReady) return window.pywebview.api[name](...args);
  const res = await fetch("/api/" + name, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(args),
  });
  const j = await res.json();
  if (!j.ok) throw new Error(j.error || "Fehler");
  return j.result;
}

// ====================================================================== Hilfsfunktionen
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtN = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "'");
const IS_MAC = /Mac/.test(navigator.platform);
const ICON = {
  left: '<svg class="i" viewBox="0 0 24 24"><path d="M19 12H5"/><path d="m11 18-6-6 6-6"/></svg>',
  right: '<svg class="i" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>',
  note: '<svg class="i" viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  edit: '<svg class="i" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
  trash: '<svg class="i" viewBox="0 0 24 24"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="m19 6-1 14H6L5 6"/></svg>',
  copy: '<svg class="i" viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  link: '<svg class="i" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>',
  folder: '<svg class="i" viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>',
  image: '<svg class="i" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>',
};

const S = {
  settings: null, opts: {}, pairs: [], counts: {}, visible: [], cur: null,
  chip: "all", advKeys: null, view: null, meta: {}, sel: new Set(), anchor: null, module: "compare",
  pairSel: new Set(), pairAnchor: null,
};

// ====================================================================== Meldungen & Dialoge
let toastTimer = null;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 3200);
}

function status(msg, tone = "info") {
  if (!msg) return;
  $("#statusText").textContent = msg;
  $("#statusText").title = msg;            // in der Fußleiste ggf. gekürzt (Platz für den Player)
  $("#pendingDot").className = "dot " + ({ ok: "ok", warn: "warn" }[tone] || (S.meta.unsaved ? "pending" : ""));
}

function dialog({ title, text = "", buttons, area = null }) {
  return new Promise((resolve) => {
    const ov = $("#dialog");
    $("#dlgTitle").textContent = title;
    $("#dlgText").textContent = text;
    const ta = $("#dlgArea");
    ta.hidden = area === null;
    if (area !== null) ta.value = area;
    const box = $("#dlgBtns");
    box.innerHTML = "";
    const finish = (v) => { ov.hidden = true; document.removeEventListener("keydown", onKey, true); resolve(v); };
    buttons.forEach((b) => {
      const el = document.createElement("button");
      el.className = b.primary ? "primary" : "ghost";
      el.textContent = b.label;
      el.addEventListener("click", () => finish(area !== null && b.value === true ? ta.value : b.value));
      box.appendChild(el);
    });
    const onKey = (e) => {
      if (e.key === "Escape") { e.preventDefault(); finish(null); }
      if (e.key === "Enter" && area === null) { e.preventDefault(); const p = buttons.find((b) => b.primary); finish(p ? p.value : null); }
    };
    document.addEventListener("keydown", onKey, true);
    ov.hidden = false;
    (area !== null ? ta : box.querySelector(".primary") || box.lastChild).focus();
  });
}

const info = (title, text) => dialog({ title, text, buttons: [{ label: "OK", value: true, primary: true }] });

// ====================================================================== Hintergrund-Aufgaben
async function runTask(startPromise, title) {
  const r = await startPromise;
  if (!r.ok) { await info("Hinweis", r.error); return null; }
  const ov = $("#progress");
  $("#progTitle").textContent = title;
  $("#progText").textContent = "";
  const bar = $("#progBar");
  bar.classList.add("indet");
  bar.style.width = "";
  const showTimer = setTimeout(() => (ov.hidden = false), 250);
  $("#progCancel").onclick = () => call("cancel_task");
  for (;;) {
    const t = await call("task_status");
    if (t.total) {
      bar.classList.remove("indet");
      const frac = t.frac || 0;   // Anteil des laufenden Elements (z. B. Stems eines Titels)
      bar.style.width = Math.min(100, Math.round((100 * (t.i + frac)) / t.total)) + "%";
      $("#progText").textContent = frac
        ? `${fmtN(Math.min(t.i + 1, t.total))} von ${fmtN(t.total)} · ${t.text || ""}`
        : `${fmtN(t.i)} von ${fmtN(t.total)} · ${t.text || ""}`;
    } else {
      $("#progText").textContent = t.text || "";
    }
    if (t.done) {
      clearTimeout(showTimer);
      ov.hidden = true;
      if (t.error) { await info("Fehler", t.error); return null; }
      return t.result;
    }
    await new Promise((res) => setTimeout(res, 120));
  }
}


// ====================================================================== Splitter & Layout
const LAYOUT = { side_w: 224, side_collapsed: false, pairs_w: 330, col_name: 190, col_ratio: 0.5, tg_edit_w: 430, tg_more_k: 130, tg_col_name: 0, tg_cover_col: false };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
let uiSaveTimers = {};
function saveUi(key) {
  clearTimeout(uiSaveTimers[key]);
  uiSaveTimers[key] = setTimeout(() => call("set_ui", key, LAYOUT[key]).catch(() => {}), 300);
}

function applyLayout() {
  const root = document.documentElement.style, side = $(".side"), table = $("#table");
  root.setProperty("--side-w", LAYOUT.side_w + "px");
  root.setProperty("--pairs-w", LAYOUT.pairs_w + "px");
  root.setProperty("--tg-edit-w", LAYOUT.tg_edit_w + "px");
  root.setProperty("--tg-more-k", LAYOUT.tg_more_k + "px");
  root.setProperty("--tg-name", LAYOUT.tg_col_name > 0 ? LAYOUT.tg_col_name + "px" : "minmax(130px,1.5fr)");   // #41
  side.classList.toggle("collapsed", !!LAYOUT.side_collapsed);
  const cb = $("#collapseBtn");
  const lbl = LAYOUT.side_collapsed ? "Seitenleiste ausklappen" : "Seitenleiste einklappen";
  cb.title = lbl; cb.setAttribute("aria-label", lbl); cb.setAttribute("aria-expanded", String(!LAYOUT.side_collapsed));
  cb.querySelector(".nt").textContent = "Einklappen";
  table.style.setProperty("--col-name", LAYOUT.col_name + "px");
  table.style.setProperty("--col-l", LAYOUT.col_ratio.toFixed(4) + "fr");
  table.style.setProperty("--col-r", (1 - LAYOUT.col_ratio).toFixed(4) + "fr");
}

/** Ziehen mit Maus/Stift/Finger: onMove(dx) mit Abstand zum Startpunkt, onEnd() danach. */
function draggable(handle, { onStart, onMove, onEnd, onDouble, onKey }) {
  handle.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const x0 = e.clientX, state = onStart ? onStart() : null;
    handle.setPointerCapture(e.pointerId);
    handle.classList.add("drag");
    document.body.classList.add("resizing");
    const move = (ev) => onMove(ev.clientX - x0, state);
    const up = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
      handle.classList.remove("drag");
      document.body.classList.remove("resizing");
      if (onEnd) onEnd(state);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  });
  if (onDouble) handle.addEventListener("dblclick", (e) => { e.preventDefault(); onDouble(); });
  if (onKey) handle.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 40 : 10;
    if (e.key === "ArrowLeft") { e.preventDefault(); onKey(-step); }
    if (e.key === "ArrowRight") { e.preventDefault(); onKey(step); }
    if (e.key === "Enter" && onDouble) { e.preventDefault(); onDouble(); }
  });
}

function toggleSide(force) {
  LAYOUT.side_collapsed = force === undefined ? !LAYOUT.side_collapsed : force;
  applyLayout();
  saveUi("side_collapsed");
}

function bindLayout() {
  // Seitenleiste: ziehen; sehr schmal gezogen = einklappen; Doppelklick = ein-/ausklappen
  draggable($("#sideSplit"), {
    onStart: () => ({ w: LAYOUT.side_collapsed ? 68 : LAYOUT.side_w }),
    onMove: (dx, st) => {
      const w = st.w + dx;
      if (w < 130) { if (!LAYOUT.side_collapsed) { LAYOUT.side_collapsed = true; applyLayout(); } return; }
      LAYOUT.side_collapsed = false;
      LAYOUT.side_w = clamp(w, 180, 340);
      applyLayout();
    },
    onEnd: () => { saveUi("side_w"); saveUi("side_collapsed"); },
    onDouble: () => toggleSide(),
    onKey: (d) => { if (LAYOUT.side_collapsed) { if (d > 0) toggleSide(false); return; }
      LAYOUT.side_w = clamp(LAYOUT.side_w + d, 180, 340); applyLayout(); saveUi("side_w"); },
  });
  $("#collapseBtn").addEventListener("click", () => toggleSide());

  // Paarliste
  draggable($("#pairSplit"), {
    onStart: () => ({ w: $("#pairsPane").getBoundingClientRect().width }),
    onMove: (dx, st) => { LAYOUT.pairs_w = clamp(Math.round(st.w + dx), 220, Math.max(240, innerWidth * 0.55)); applyLayout(); drawPairWindow(); },
    onEnd: () => saveUi("pairs_w"),
    onDouble: () => { LAYOUT.pairs_w = 330; applyLayout(); drawPairWindow(); saveUi("pairs_w"); },
    onKey: (d) => { LAYOUT.pairs_w = clamp(LAYOUT.pairs_w + d, 220, innerWidth * 0.55); applyLayout(); saveUi("pairs_w"); },
  });

  // Tabelle: Breite der Feldspalte
  draggable($("#gripName"), {
    onStart: () => ({ w: LAYOUT.col_name }),
    onMove: (dx, st) => { LAYOUT.col_name = clamp(Math.round(st.w + dx), 110, 420); applyLayout(); },
    onEnd: () => saveUi("col_name"),
    onDouble: () => { LAYOUT.col_name = 190; applyLayout(); saveUi("col_name"); },
    onKey: (d) => { LAYOUT.col_name = clamp(LAYOUT.col_name + d, 110, 420); applyLayout(); saveUi("col_name"); },
  });
  // Tabelle: Aufteilung links/rechts (mittlere Spalte verschieben)
  const valuesWidth = () => {
    const t = $("#table").getBoundingClientRect().width;
    return Math.max(200, t - LAYOUT.col_name - 92 - 32);
  };
  draggable($("#gripMid"), {
    onStart: () => ({ r: LAYOUT.col_ratio, w: valuesWidth() }),
    onMove: (dx, st) => { LAYOUT.col_ratio = clamp(st.r + dx / st.w, 0.2, 0.8); applyLayout(); },
    onEnd: () => saveUi("col_ratio"),
    onDouble: () => { LAYOUT.col_ratio = 0.5; applyLayout(); saveUi("col_ratio"); },
    onKey: (d) => { LAYOUT.col_ratio = clamp(LAYOUT.col_ratio + d / valuesWidth(), 0.2, 0.8); applyLayout(); saveUi("col_ratio"); },
  });
}

// ====================================================================== Update von GitHub
let updateInfo = null;
function showUpdateBadge(st) {
  updateInfo = st;
  const has = !!(st && st.ok && (st.behind || st.switch));
  $("#updateDot").hidden = !has;
  $("#updateBtn").classList.toggle("has-update", has);
  $("#updateLbl").textContent = has ? (st.behind ? `Update verfügbar (${st.behind})` : "Update verfügbar") : "Nach Update suchen";
  $("#updateBtn").title = has ? `Neue Version auf GitHub (${st.branch}): ${st.behind} Änderung(en)` : "Nach neuer Version suchen";
}

async function checkUpdateQuietly() {
  try { showUpdateBadge(await call("update_status", true)); } catch (e) { /* offline – egal */ }
}

async function runUpdate() {
  $("#updateLbl").textContent = "Suche …";
  let st;
  try { st = await call("update_status", true); } catch (e) { st = { ok: false, error: String(e.message || e) }; }
  showUpdateBadge(st);
  if (!st.ok && st.frozen) {
    const go = await dialog({ title: "Update", text: st.error,
      buttons: [{ label: "Schliessen", value: null }, { label: "Releases auf GitHub öffnen", value: true, primary: true }] });
    if (go) call("open_url", st.releases_url);
    return;
  }
  if (!st.ok) { await info("Update nicht möglich", st.error); return; }
  if (!st.behind && !st.switch) { toast(`Du hast die neueste Version (${st.branch}, ${st.current}).`); return; }
  const list = (st.commits || []).map((c) => "• " + c).join("\n");
  const head = st.switch && !st.behind
    ? `Der Zweig „${st.branch}“ wurde nach „${st.switch}“ verschoben – TagStudio wechselt auf „${st.switch}“ (gleicher Stand).`
    : `Zweig „${st.switch || st.branch}“: ${st.behind} Änderung(en)\n\n${list}`;
  const go = await dialog({
    title: "Neue Version verfügbar",
    text: `${head}\n\nJetzt laden? TagStudio startet danach neu – die gewählten Ordner werden wieder eingelesen.`,
    buttons: [{ label: "Später", value: null }, { label: "Laden und neu starten", value: true, primary: true }],
  });
  if (!go) return;
  if ((S.meta.unsaved || st.unsaved) && !(await confirmDiscard())) return;
  if (await call("unsaved")) applyState(await call("discard_all"));  // „Verwerfen“ gewählt
  const res = await call("apply_update");
  if (!res.ok) { await info("Update nicht möglich", res.message); return; }
  const ov = $("#progress");
  $("#progTitle").textContent = "Neue Version geladen – TagStudio startet neu …";
  $("#progText").textContent = res.message;
  $("#progBar").classList.add("indet");
  $("#progCancel").hidden = true;
  ov.hidden = false;
  S.meta.unsaved = 0;
  await call("restart");
  if (!S.settings.native) {
    // Browser-Modus: der neue Server übernimmt Adresse und Schlüssel → Seite neu laden, sobald er antwortet
    for (let k = 0; k < 60; k++) {
      await new Promise((r) => setTimeout(r, 500));
      try { const r = await fetch("index.html", { cache: "no-store" }); if (r.ok && k > 1) { location.reload(); return; } } catch (e) { /* noch nicht da */ }
    }
    $("#progTitle").textContent = "Bitte TagStudio neu starten.";
  }
}

// ====================================================================== Herkunft der Tags (#22)
function srcInfo(sid) { return sid && S.settings && S.settings.origins ? S.settings.origins[sid] : null; }
function srcHue(sid) { let h = 0; for (const c of String(sid)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
/** Kleines Kennzeichen „von welcher Anwendung“ vor dem Feldnamen. */
function srcBadge(sid) {
  const o = srcInfo(sid);
  if (!o) return "";
  const short = o.short || (o.kind === "plugin" ? "TagStudio" : o.name.length > 12 ? o.name.slice(0, 11) + "…" : o.name);
  const own = o.hue !== null && o.hue !== undefined;         // #75: eigene Farbe
  const cls = own ? "" : o.kind === "plugin" ? " own" : o.kind === "id3" ? " id3" : o.kind === "unknown" ? " unk" : "";
  const what = o.kind === "id3" ? "ID3-Version" : "Herkunft";
  const tip = `<div class="tip-h"><span class="src-b${cls}" style="--h:${own ? o.hue : srcHue(sid)}">${esc(short)}</span>${o.name !== short ? " " + esc(o.name) : ""}</div><div class="tip-l">${esc(what)} – ${esc(o.desc)}</div>`;
  return `<span class="src-b${cls}" data-sid="${esc(sid)}" style="--h:${own ? o.hue : srcHue(sid)}" aria-label="${what}: ${esc(o.name)}" data-tip-html="${esc(tip)}">${esc(short)}</span>`;
}
/** #74: ID3-Version (offizielle Felder) + Herkunft */
function srcBadges(ver, src) { return srcBadge(ver) + srcBadge(src); }

// ====================================================================== Hover-Infos (#72)
/* Eigene Tooltips statt der Browser-Tooltips: im Design der App (hell/dunkel), mit Überschrift (erste Zeile),
   „Feld: Wert“-Zeilen als Tabelle und farbigen Hervorhebungen (Herkunft, Tonart, BPM, Abweichungen).
   Quelle bleibt das title-Attribut (bzw. data-tip-html für reichere Inhalte) – es wird nur während des Hoverns
   beiseitegelegt, damit kein doppelter Browser-Tooltip erscheint. */
const TIP = { el: null, target: null, timer: 0 };
function tipHtml(el) {
  if (el.dataset.tipHtml) return el.dataset.tipHtml;
  const text = el.dataset.tipTitle || "";
  if (!text.trim()) return "";
  const lines = text.split("\n").filter((l, k, all) => l.trim() || (k && k < all.length - 1));
  const head = lines.length > 1 ? `<div class="tip-h">${esc(lines.shift())}</div>` : "";
  const rows = lines.map((l) => {
    const m = l.match(/^\s*([^:]{1,32}):\s+(.+)$/);
    const val = (s) => esc(s).replace(/\b(0?([1-9]|1[0-2])[AB])\b/g, (k) => (typeof keyStyle === "function" ? `<b class="tip-key" style="${keyStyle(k.replace(/^0/, ""))}">${k}</b>` : k))
      .replace(/(\d+(?:[.,]\d+)?\s?BPM)/g, '<b class="tip-bpm">$1</b>').replace(/(unterscheidet sich[^·]*|geändert|fehlt|NICHT[^·]*)/g, '<span class="tip-warn">$1</span>');
    return m ? `<div class="tip-r"><span class="tip-k">${esc(m[1])}</span><span class="tip-v">${val(m[2])}</span></div>` : `<div class="tip-l">${val(l)}</div>`;
  }).join("");
  return head + rows;
}
function tipShow(el) {
  const html = tipHtml(el);
  if (!html) return;
  const t = TIP.el;
  t.innerHTML = html;
  t.hidden = false;
  const r = el.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight;
  let x = r.left + r.width / 2 - w / 2, y = r.bottom + 8;
  if (y + h > innerHeight - 8) y = r.top - h - 8;
  t.style.left = Math.max(8, Math.min(innerWidth - w - 8, x)) + "px";
  t.style.top = Math.max(8, y) + "px";
}
function tipHide() {
  clearTimeout(TIP.timer);
  if (TIP.el) TIP.el.hidden = true;
  const el = TIP.target;
  if (el && el.dataset.tipTitle !== undefined) { el.setAttribute("title", el.dataset.tipTitle); delete el.dataset.tipTitle; }
  TIP.target = null;
}
function initTips() {
  TIP.el = document.createElement("div");
  TIP.el.className = "tip"; TIP.el.hidden = true; TIP.el.setAttribute("role", "tooltip");
  document.body.appendChild(TIP.el);
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest && e.target.closest("[title],[data-tip-html]");
    if (el === TIP.target) return;
    tipHide();
    if (!el || el.closest(".tg-thumb") || el.matches("input,textarea,select,option") || el.closest("#tgThumbPop")) return;
    TIP.target = el;
    if (el.hasAttribute("title")) { el.dataset.tipTitle = el.getAttribute("title"); el.removeAttribute("title"); }
    TIP.timer = setTimeout(() => { if (TIP.target === el && el.isConnected) tipShow(el); }, 380);
  });
  ["mousedown", "keydown", "scroll", "blur"].forEach((ev) => window.addEventListener(ev, tipHide, true));
  document.addEventListener("mouseleave", tipHide);
}

// ====================================================================== Listen-Cache: Prüfung im Hintergrund (#70)
let verifyTimer = 0;
function verifyWatch(res, baseMsg) {
  clearTimeout(verifyTimer);
  if (!res || !res.cached) return;
  const tick = async () => {
    let v;
    try { v = await call("verify_status"); } catch (e) { return; }
    if (v.running) {
      status(`${baseMsg} · aus dem Cache – prüfe ${fmtN(v.i)} / ${fmtN(v.total)} …`);
      verifyTimer = setTimeout(tick, 600);
      return;
    }
    const n = v.n_changed || 0, gone = (v.removed || []).length;
    if (n || gone) {
      if (v.kind === "tagger" && typeof taggerRefresh === "function") await taggerRefresh();
      else if (S.pairs && S.pairs.length) await refreshAll(await call("state"));
      status(`${baseMsg} · ${n ? `${fmtN(n)} Titel ausserhalb geändert – neu gelesen` : ""}${n && gone ? ", " : ""}${gone ? `${gone} nicht mehr vorhanden` : ""}`, "warn");
      $("#statusText").title = [...(v.changed || []), ...(v.removed || []).map((x) => x + " (fehlt)")].join("\n");
    } else status(`${baseMsg} · geprüft, alles aktuell (aus dem Cache)`, "ok");
  };
  verifyTimer = setTimeout(tick, 300);
}

// Unbehandelte Fehler aus Aufrufen (z. B. Schreibschutz einer Snapshot-Seite) verständlich anzeigen
window.addEventListener("unhandledrejection", (e) => {
  const m = e.reason && (e.reason.message || String(e.reason));
  if (m && typeof toast === "function") toast(m);
});

// ====================================================================== Start
async function init() {
  const st = await call("settings");
  S.settings = st;
  S.opts = st.options;
  for (const k of Object.keys(LAYOUT)) if (st.ui && st.ui[k] !== undefined) LAYOUT[k] = st.ui[k];
  applyLayout();
  applyTheme();
  initTips();                       // #72
  $("#ver").textContent = "Version " + st.version + (st.native ? "" : " · Browser");
  $("#mode").innerHTML = st.modes.map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
  $("#mode").value = st.mode;
  $("#recursive").checked = !!st.recursive;
  fillHistory();
  // #84: beim Start die Standardordner (sonst wie bisher der letzte Pfad)
  const dd = st.defaults || {};
  $("#pathL").value = st.start_paths[0] ?? (dd.left || st.hist_left[0] || "");
  $("#pathR").value = st.start_paths[1] ?? (st.start_paths.length ? "" : dd.right || st.hist_right[0] || "");
  homeSync();
  $("#emptySet").innerHTML = st.empty_sets.map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
  $("#fOp").innerHTML = st.filter_ops.map((o) => `<option>${esc(o)}</option>`).join("");
  $("#fSide").innerHTML = st.filter_sides.map((o) => `<option>${esc(o)}</option>`).join("");
  bind();
  bindLayout();
  if (typeof initPlayer === "function") initPlayer();
  if (typeof initJobs === "function") initJobs();
  if (typeof initSnapshots === "function") setTimeout(initSnapshots, 1200);
  $("#updateBtn").addEventListener("click", runUpdate);
  setTimeout(checkUpdateQuietly, 1500);
  syncOptions();
  renderPairs();
  showView(null);
  if (st.start_paths.length) compare(true);
}

function fillHistory() {
  const st = S.settings;
  $("#histL").innerHTML = st.hist_left.map((h) => `<option value="${esc(h)}"></option>`).join("");
  $("#histR").innerHTML = st.hist_right.map((h) => `<option value="${esc(h)}"></option>`).join("");
}

function applyTheme() {
  const dark = S.opts.theme !== "light";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  $("#themeLbl").textContent = dark ? "Helles Design" : "Dunkles Design";
}

function syncOptions() {
  $$(".seg button[data-filter]").forEach((b) => b.classList.toggle("on", b.dataset.filter === S.opts.filter));
  $("#trivBtn").classList.toggle("on", !!S.opts.show_trivial);
  $("#coverBtn").classList.toggle("on", !!S.opts.show_covers);
  $("#emptySet").value = S.opts.empty_set;
}

// ====================================================================== Laden
async function confirmDiscard() {
  const n = S.meta.unsaved || (await call("unsaved"));
  if (!n) return true;
  const v = await dialog({
    title: "Ungespeicherte Änderungen",
    text: `${n} Datei(en) haben ungespeicherte Änderungen.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Verwerfen", value: "discard" }, { label: "Speichern", value: "save", primary: true }],
  });
  if (v === null) return false;
  if (v === "save") return await save(true);
  return true;
}

async function compare(skipConfirm = false, keep = false) {
  if (!skipConfirm && !(await confirmDiscard())) return;
  const lp = $("#pathL").value.trim(), rp = $("#pathR").value.trim();
  homeSync();
  const res = await runTask(call("start_load", lp, rp, $("#recursive").checked, $("#mode").value, keep), "Dateien einlesen");
  if (!res) return;
  if (res.cancelled) { status("Einlesen abgebrochen – bisherige Ansicht bleibt erhalten.", "warn"); return; }
  S.settings = await call("settings");
  fillHistory();
  await loadPairs();
  applyState(await call("state"));
  status(res.pairs ? `${fmtN(res.pairs)} Paar${res.pairs === 1 ? "" : "e"} eingelesen.` : "Keine MP3-Dateien gefunden.", res.pairs ? "ok" : "warn");
  verifyWatch(res, `${fmtN(res.pairs)} Paar${res.pairs === 1 ? "" : "e"} eingelesen`);
  if (typeof snDetect === "function") snDetect(lp).then(() => rp && snDetect(rp));    // #60
  if (res.errors && res.errors.length) {
    await info(`${res.errors.length} Datei(en) nicht lesbar`, res.errors.slice(0, 30).join("\n") + (res.errors.length > 30 ? "\n…" : ""));
  }
  if ($("#adv").hidden === false) refreshFieldChoices();
}

async function loadPairs() {
  const pr = await call("pair_rows");
  S.pairs = pr.rows;
  S.counts = pr.counts;
  S.advKeys = null;
  await applyPairFilter(false);
}

// ====================================================================== Paarliste
const CHIPS = [["all", "Alle", null], ["diff", "≠", "diff"], ["triv", "≈", "triv"], ["same", "=", "same"], ["single", "◧", "single"]];
const CHIP_TITLE = { all: "Alle Paare", diff: "Mit Unterschieden", triv: "Nur unwichtige Unterschiede", same: "Gleich", single: "Nur eine Seite vorhanden" };

async function applyPairFilter(serverSide = true) {
  const q = $("#pairQuery").value.trim();
  const advOn = !$("#adv").hidden && $("#fField").value;
  if (serverSide && (q || advOn)) {
    const key = advOn ? $("#fField").value : null;
    const idx = await call("filter_pairs", q, key, $("#fOp").value, $("#fVal").value, $("#fSide").value);
    S.advKeys = new Set(idx);
  } else if (!q && !advOn) {
    S.advKeys = null;
  }
  S.visible = S.pairs.filter((p) => (S.chip === "all" || p.tag === S.chip) && (!S.advKeys || S.advKeys.has(p.i))).map((p) => p.i);
  renderPairs();
}

function renderChips() {
  const c = S.counts || {};
  $("#pairChips").innerHTML = CHIPS.map(([k, sym, dot]) => {
    const n = k === "all" ? S.pairs.length : c[k] || 0;
    if (k !== "all" && !n) return "";
    return `<button class="chip${S.chip === k ? " on" : ""}" data-chip="${k}" title="${esc(CHIP_TITLE[k])}">${dot ? `<span class="d d-${dot}"></span>` : ""}${k === "all" ? "Alle" : sym} ${fmtN(n)}</button>`;
  }).join("");
}

const ROW_H = 52;
function renderPairs() {
  renderChips();
  const n = S.visible.length, total = S.pairs.length;
  $("#pairCount").textContent = total ? (n === total ? `${fmtN(total)} Paare` : `${fmtN(n)} von ${fmtN(total)}`) : "–";
  $("#pairsPane").hidden = total <= 1;
  $("#pairSplit").hidden = total <= 1;
  const inner = $("#pairsInner");
  inner.style.height = n * ROW_H + "px";
  drawPairWindow();
}

function drawPairWindow() {
  const sc = $("#pairsScroll"), inner = $("#pairsInner");
  const n = S.visible.length;
  if (!S.pairs.length) { inner.innerHTML = ""; return; }
  if (!n) { inner.innerHTML = '<div class="pairs-empty">Keine Paare passen zum Filter.</div>'; return; }
  const first = Math.max(0, Math.floor(sc.scrollTop / ROW_H) - 5);
  const last = Math.min(n, Math.ceil((sc.scrollTop + sc.clientHeight) / ROW_H) + 5);
  let html = "";
  for (let k = first; k < last; k++) {
    const p = S.pairs[S.visible[k]];
    const name = p.left || p.right;
    const other = p.left && p.right && p.left !== p.right ? ` · ↔ ${p.right}` : "";
    html += `<button class="pair${p.i === S.cur ? " cur" : ""}${S.pairSel.has(p.i) ? " msel" : ""}" style="top:${k * ROW_H}px" data-i="${p.i}" title="${esc(p.left)}${p.right && p.right !== p.left ? "\n↔ " + esc(p.right) : ""}">
      <span class="d d-${p.tag}"></span><span class="t"><span class="n">${esc(name)}</span><span class="s">${esc(p.info + other)}</span></span>${pairBpm(p)}${p.modified ? '<span class="m" title="ungespeichert"></span>' : ""}</button>`;
  }
  inner.innerHTML = html;
}

/** Tempo-Spalte der Paarliste (#35): ein Wert oder „links ≠ rechts“ hervorgehoben. */
function pairBpm(p) {
  const [l, r] = p.bpm || ["", ""];
  if (!l && !r) return '<span class="bpm" title="kein Tempo"></span>';
  const diff = l && r && l !== r;
  return `<span class="bpm${diff ? " diff" : ""}" title="Tempo (BPM)${diff ? ` links ${esc(l)}, rechts ${esc(r)}` : ""}">${esc(diff ? `${l}≠${r}` : l || r)}</span>`;
}

function scrollPairIntoView(i) {
  const k = S.visible.indexOf(i);
  if (k < 0) return;
  const sc = $("#pairsScroll");
  const top = k * ROW_H;
  if (top < sc.scrollTop) sc.scrollTop = top;
  else if (top + ROW_H > sc.scrollTop + sc.clientHeight) sc.scrollTop = top + ROW_H - sc.clientHeight;
  drawPairWindow();
}

async function selectPair(i) {
  if (i === S.cur) return;
  S.sel.clear();
  S.anchor = null;
  applyState(await call("select", i));
  scrollPairIntoView(i);
  if (typeof playerFollow === "function") playerFollow();
}

async function refreshFieldChoices() {
  const ch = await call("field_choices");
  const cur = $("#fField").value;
  $("#fField").innerHTML = ch.map(([lbl, key]) => `<option value="${esc(key ?? "")}">${esc(lbl)}</option>`).join("");
  $("#fField").value = cur;
}

// ====================================================================== Zustand anwenden
/** #84: Knopf „Standardordner eintragen“ nur zeigen, wenn ein Standard gesetzt ist und das Feld abweicht */
function homeSync() {
  const d = (S.settings && S.settings.defaults) || {};
  [["L", "#pathL", d.left], ["R", "#pathR", d.right], ["T", "#tgPath", d.tagger]].forEach(([k, sel, def]) => {
    const b = $(`[data-home="${k}"]`), inp = $(sel);
    if (b && inp) { b.hidden = !def || inp.value.trim() === def; if (def) b.title = `Standardordner wieder eintragen:\n${def}`; }
  });
}

/** #82: nur das aktuelle Paar neu von der Platte lesen */
async function reloadPair() {
  if (S.cur === null || S.cur === undefined) return toast("Erst ein Dateipaar wählen.");
  let st = await call("reload_pair", false);
  if (st && st.ask) {
    const ok = await dialog({ title: "Ungespeicherte Änderungen verwerfen?", text: `${st.ask.files.join(", ")} hat ungespeicherte Änderungen. Beim Neu-Einlesen gehen sie verloren.`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Neu einlesen", value: true, primary: true }] });
    if (!ok) return;
    st = await call("reload_pair", true);
  }
  applyState(st);
}

function applyState(st) {
  if (!st) return;
  if (st.ask) return st; // Rückfrage nötig
  S.meta = st.meta || S.meta;
  S.opts = st.options || S.opts;
  if (st.pair) {
    const k = S.pairs.findIndex((p) => p.i === st.pair.i);
    if (k >= 0) {
      const old = S.pairs[k];
      if (old.tag !== st.pair.tag) { S.counts[old.tag]--; S.counts[st.pair.tag] = (S.counts[st.pair.tag] || 0) + 1; }
      S.pairs[k] = st.pair;
    }
  }
  showView(st.view);
  syncOptions();
  renderMeta();
  renderChips();
  drawPairWindow();
  if (st.message) status(st.message, st.tone);
  return st;
}

function renderMeta() {
  const m = S.meta;
  $("#undoBtn").disabled = !m.can_undo;
  $("#redoBtn").disabled = !m.can_redo;
  $("#undoBtn").title = m.can_undo ? `Rückgängig: ${m.undo_label}` : "Rückgängig";
  $("#redoBtn").title = m.can_redo ? `Wiederholen: ${m.redo_label}` : "Wiederholen";
  $("#saveLbl").textContent = m.unsaved ? `Speichern (${m.unsaved})` : "Speichern";
  $("#saveBtn").disabled = !m.unsaved;
  $("#pendingDot").className = "dot" + (m.unsaved ? " pending" : "");
  if (!m.unsaved && /ungespeichert|noch nicht gespeichert/.test($("#statusText").textContent)) status("Keine ungespeicherten Änderungen.");
}

// ====================================================================== Vergleichsansicht
function showView(v) {
  S.view = v;
  S.cur = v ? v.index : null;
  const has = v && (v.left || v.right);
  $("#emptyState").hidden = !!has;
  $("#cmp").hidden = !has;
  if (!has) return;
  renderHead($("#headL"), v.left, "L");
  renderHead($("#headR"), v.right, "R");
  const c = v.counts;
  $("#summary").textContent = v.both ? `${c.diff} wichtig · ${c.only} nur eine Seite · ${c.triv} unwichtig` : "Nur eine Seite – Tags können bearbeitet werden";
  // #56: nie in Richtung einer Snapshot-Seite (schreibgeschützt)
  const roL = !!(v.left && v.left.readonly), roR = !!(v.right && v.right.readonly);
  $$("[data-copyall],[data-missing]").forEach((b) => { const d = b.dataset.copyall || b.dataset.missing; b.disabled = !v.both || (d === "rl" && roL) || (d === "lr" && roR); });
  renderRows();
}

function renderHead(el, h, side) {
  if (!h) { el.innerHTML = '<div class="head-missing">— keine Datei —</div>'; return; }
  const covers = h.covers.length
    ? `<div class="covers">${h.covers.slice(0, 2).map((c) => `<button class="cover${c.differs ? " diff" : ""}" data-cover="${side}|${esc(c.key)}" title="${esc(c.label + " · " + c.desc + (c.differs ? " · unterscheidet sich" : ""))}" aria-label="${esc(c.label)} anzeigen">${c.src ? `<img src="${c.src}" alt="">` : ICON.image}</button>`).join("")}</div>`
    : S.opts.show_covers ? `<div class="covers"><button class="cover add" data-addcover="${side}" title="Kein Cover – klicken zum Hinzufügen" aria-label="Cover hinzufügen">${ICON.note}</button></div>` : "";
  // Datum/Größe nur im Tooltip; als Etiketten: ID3-Version, Dauer, Bitrate, Abtastrate, Kanäle
  const parts = h.info.split(/\s{2,}/).filter(Boolean).slice(2);
  el.classList.toggle("ro", !!h.readonly);
  el.innerHTML = `${covers}<div class="head-t">${h.readonly ? `<div class="head-snap" title="Snapshot – schreibgeschützt; übernehmen nur in Richtung der echten Dateien">📸 ${esc(h.snapshot)} · schreibgeschützt</div>` : ""}<div class="head-n" title="${esc(h.path + "\n" + h.info.split(/\s{2,}/).join(" · "))}">${esc(h.name)}${h.modified ? '<span class="m" title="ungespeicherte Änderungen"></span>' : ""}</div>
    <div class="tags">${parts.map((p) => `<span>${esc(p)}</span>`).join("")}${h.bpm ? `<span class="bpm-chip${h.bpm_differs ? " diff" : ""}" title="Tempo${h.bpm_differs ? " – unterscheidet sich von der anderen Seite" : ""}">${esc(h.bpm)} BPM</span>` : ""}</div></div>`;
}

function valueHtml(cell, state) {
  if (!cell) return '<span class="empty"></span>';
  if (!cell.present) return state === "only" ? '<span class="miss">— fehlt —</span>' : '<span class="empty"></span>';
  const s = cell.text;
  if (!s) return (cell.mod ? '<span class="mod"></span>' : "") + '<span class="empty">(leer)</span>';
  const n = s.length, chg = new Uint8Array(n), url = new Array(n).fill(null);
  // Python zählt Zeichen (Codepoints), JS UTF-16-Einheiten – bei Emoji o. Ä. umrechnen
  let pos = null;
  if (/[\uD800-\uDBFF]/.test(s)) { pos = [0]; for (const ch of s) pos.push(pos[pos.length - 1] + ch.length); }
  const u16 = (i) => (pos ? pos[Math.min(i, pos.length - 1)] : i);
  for (const [a, b] of cell.spans || []) for (let i = u16(a); i < Math.min(u16(b), n); i++) chg[i] = 1;
  for (const [a, b, u] of cell.links || []) for (let i = u16(a); i < Math.min(u16(b), n); i++) url[i] = u;
  let out = cell.mod ? '<span class="mod" title="geändert, noch nicht gespeichert"></span>' : "";
  if (cell.xml) out += `<button class="xml-badge${cell.xml === "view" ? " view" : ""}" data-xml="1" title="${cell.xml === "view" ? "XML ansehen (Binärfeld)" : "Im XML-Editor bearbeiten"}">XML</button>`;
  let start = 0;
  const cls = state === "triv" ? "tv" : "hl";
  for (let i = 1; i <= n; i++) {
    if (i === n || chg[i] !== chg[start] || url[i] !== url[start]) {
      let piece = esc(s.slice(start, i));
      if (chg[start]) piece = `<span class="${cls}">${piece}</span>`;
      if (url[start]) piece = `<a data-url="${esc(url[start])}" title="${esc(url[start])} öffnen">${piece}</a>`;
      out += piece;
      start = i;
    }
  }
  return out;
}

/** #99: Filter nach Herkunft im Vergleich – Auswahl aus den Herkünften des aktuellen Paars */
function visRows() { const r = (S.view && S.view.rows) || []; return S.srcFilter ? r.filter((x) => cmpSrcOf(x).includes(S.srcFilter)) : r; }
function cmpSrcOf(r) { return [r.src || "", r.ver || ""].filter(Boolean); }
function cmpSrcSync(rows) {
  const n = {};
  rows.forEach((r) => cmpSrcOf(r).forEach((s) => { n[s] = (n[s] || 0) + 1; }));
  if (S.srcFilter && !(S.srcFilter in n)) n[S.srcFilter] = 0;          // gewählte Herkunft bleibt wählbar
  const keys = Object.keys(n).sort((x, y) => (srcInfo(x)?.kind === "id3") - (srcInfo(y)?.kind === "id3") || (srcInfo(x)?.name || x).localeCompare(srcInfo(y)?.name || y));
  const html = '<option value="">Alle Herkünfte</option>' + keys.map((k) => `<option value="${esc(k)}">${esc(srcInfo(k)?.name || k)} (${n[k]})</option>`).join("");
  const sel = $("#cmpSrc");
  if (sel.dataset.v !== html) { sel.innerHTML = html; sel.dataset.v = html; }
  sel.value = S.srcFilter || "";
  sel.classList.toggle("on", !!S.srcFilter);
}

function renderRows() {
  const v = S.view;
  const body = $("#tbody");
  cmpSrcSync(v.rows);
  const rows = visRows();
  if (!rows.length) {
    body.innerHTML = `<div class="table-empty">${S.srcFilter ? `Keine Felder mit Herkunft „${esc(srcInfo(S.srcFilter)?.name || S.srcFilter)}“.` : S.opts.filter === "diff" ? "Keine Unterschiede." : "Keine Felder."}</div>`;
    return;
  }
  body.innerHTML = rows.map((r, n) => {
    const canCopy = v.both && r.state !== "same" && r.state !== "empty";
    const roL = !!(v.left && v.left.readonly), roR = !!(v.right && v.right.readonly);
    const ed = (c) => (c && c.editable ? "" : " noedit");
    return `<div class="tr ${r.state}${S.sel.has(r.key) ? " sel" : ""}" data-n="${n}" data-key="${esc(r.key)}">
      <div class="f"><span class="f-n"><span title="${esc(r.label)}">${esc(r.label)}</span></span><span class="f-id"><span class="fid" title="${esc(r.key)}">${esc(r.fid)}</span>${srcBadges(r.ver, r.src)}${r.trivial && r.state !== "same" ? '<span class="triv-b" title="Gilt als unwichtig (Einstellungen › Unwichtige Felder)">unwichtig</span>' : ""}</span></div>
      <div class="v${ed(r.L)}" data-side="L">${valueHtml(r.L, r.state)}</div>
      <div class="acts">${canCopy ? `${roL ? "<span></span>" : `<button class="arrow" data-dir="rl" title="Rechten Wert nach links übernehmen" aria-label="${esc(r.label)} nach links übernehmen">${ICON.left}</button>`}${roR ? "<span></span>" : `<button class="arrow" data-dir="lr" title="Linken Wert nach rechts übernehmen" aria-label="${esc(r.label)} nach rechts übernehmen">${ICON.right}</button>`}` : ""}</div>
      <div class="v r${ed(r.R)}" data-side="R">${valueHtml(r.R, r.state)}</div>
    </div>`;
  }).join("");
}

function paintSelection() {
  $$("#tbody .tr").forEach((tr) => tr.classList.toggle("sel", S.sel.has(tr.dataset.key)));
}

function rowKeys() { return visRows().map((r) => r.key); }
function selectedKeys() { return rowKeys().filter((k) => S.sel.has(k)); }

// ====================================================================== Bearbeiten
function startEdit(tr, side) {
  const r = visRows()[+tr.dataset.n];
  const cell = r[side];
  if (cell && cell.xml) return openXml(side, r.key);
  if (!cell || !cell.editable) {
    if (r.key.startsWith("APIC") && cell && cell.present) return openCover(side, r.key);
    if (cell && cell.present) toast(`„${r.label}“ ist ein Binärfeld und kann nur kopiert oder entfernt werden.`);
    return;
  }
  if (cell.multiline) return editDialog(r, side, cell.edit);
  const box = tr.querySelector(`.v[data-side="${side}"]`);
  const input = document.createElement("input");
  input.className = "edit";
  input.value = cell.edit;
  input.setAttribute("aria-label", `${r.label} ${side === "L" ? "links" : "rechts"} bearbeiten`);
  box.innerHTML = "";
  box.appendChild(input);
  input.focus();
  input.select();
  let done = false;
  const finish = async (commit, next) => {
    if (done) return;
    done = true;
    if (commit && input.value !== cell.edit) applyState(await call("set_value", side, r.key, input.value));
    else box.innerHTML = valueHtml(cell, r.state);
    if (next) {
      const rows = $$("#tbody .tr");
      for (let k = +tr.dataset.n + next; k >= 0 && k < rows.length; k += next) {
        const c = visRows()[k][side];
        if (c && c.editable && !c.multiline) { startEdit(rows[k], side); break; }
      }
    } else $("#table").focus();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); finish(true); }
    else if (e.key === "Escape") { e.preventDefault(); finish(false); }
    else if (e.key === "Tab") { e.preventDefault(); finish(true, e.shiftKey ? -1 : 1); }
    e.stopPropagation();
  });
  input.addEventListener("blur", () => finish(true));
}

async function editDialog(r, side, text) {
  const v = await dialog({
    title: `${r.label} – ${side === "L" ? "links" : "rechts"}`, area: text,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
  });
  if (v !== null && v !== text) applyState(await call("set_value", side, r.key, v));
}

// ====================================================================== Kopieren & Co.
async function copyKeys(keys, dir) {
  if (!keys.length) { toast("Bitte zuerst Felder markieren (Klick, Shift/Strg-Klick)."); return; }
  applyState(await call("copy_keys", keys, dir));
}

async function copyAll(dir) {
  let st = await call("copy_all", dir, null);
  if (st && st.ask) {
    const a = st.ask;
    const v = await dialog({
      title: "Felder nur im Ziel",
      text: `${a.count} Feld(er) gibt es nur im Ziel:\n\n${a.labels.map((l) => "• " + l).join("\n")}${a.more ? `\n… und ${a.more} weitere` : ""}\n\nSollen diese im Ziel entfernt werden, damit beide Seiten gleich sind?`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Behalten", value: false }, { label: "Entfernen", value: true, primary: true }],
    });
    if (v === null) return;
    st = await call("copy_all", dir, v);
  }
  applyState(st);
}

async function save(fromConfirm = false) {
  if (!S.meta.unsaved && !fromConfirm) { status("Keine ungespeicherten Änderungen.", "ok"); return true; }
  // #55: Wurden Dateien inzwischen von einem anderen Programm geändert?
  let force = false;
  const cf = (await call("save_conflicts")).conflicts;
  if (cf.length) {
    const what = await saveConflictDialog(cf);
    if (!what) return false;
    if (what === "merge") { applyState(await call("save_merge_external")); if (typeof taggerRefresh === "function") await taggerRefresh(); }
    else force = true;
  }
  const res = await runTask(call("start_save", force), "Speichern");
  if (!res) return false;
  await loadPairs();
  applyState(await call("state"));
  if (typeof taggerRefresh === "function") await taggerRefresh();
  const b = res.backup ? ` · Sicherung: ${res.backup.split(/[\\/]/).pop()}` : "";
  if (res.errors.length) {
    status(`${res.saved} gespeichert, ${res.errors.length} Fehler.${b}`, "warn");
    await info("Fehler beim Speichern", res.errors.slice(0, 30).join("\n"));
  } else if (res.cancelled) {
    status(`Abgebrochen – ${res.saved} Datei(en) gespeichert.${b}`, "warn");
  } else {
    status(`${res.saved} Datei(en) gespeichert.${b}`, "ok");
  }
  return !res.errors.length && !res.cancelled;
}

/** Externe Änderungen vor dem Speichern (#55) */
async function saveConflictDialog(cf) {
  const anyClash = cf.some((c) => c.clash.length);
  const list = cf.slice(0, 40).map((c) => `<div class="cf-file"><b>${esc(c.name)}</b>
    ${c.fields.slice(0, 12).map((f) => `<div class="cf-row${f.mine ? " clash" : ""}"><span class="k">${esc(f.label)}</span><span class="o">${esc(f.old || "—")}</span><span class="arr">→</span><span class="n">${esc(f.new || "—")}</span>${f.mine ? '<span class="tag">auch von dir geändert</span>' : ""}</div>`).join("")}
    ${c.fields.length > 12 ? `<div class="muted sm">… ${c.fields.length - 12} weitere</div>` : ""}</div>`).join("");
  return modal({
    title: `${cf.length} Datei(en) wurden von einem anderen Programm geändert`, wide: true,
    html: `<p class="muted" style="margin:0 0 10px">Seit TagStudio die Dateien eingelesen hat, hat z. B. Mp3tag, Mixed In Key oder beaTunes diese Felder geändert. Beim Speichern würden diese Änderungen sonst überschrieben.</p>
      <div class="cf-list">${list}</div>
      <p class="muted sm" style="margin:10px 0 0"><b>Übernehmen und speichern</b> liest die Dateien neu ein, behält deine eigenen Änderungen${anyClash ? " (bei Feldern, die beide geändert haben, gewinnt deine Änderung)" : ""} und speichert danach.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Trotzdem überschreiben", value: "force" }, { label: "Übernehmen und speichern", value: "merge", primary: true }],
  });
}

function openCover(side, key) {
  const h = side === "L" ? S.view.left : S.view.right;
  const c = h && h.covers.find((x) => x.key === key);
  if (!c || !c.src) { toast("Für dieses Bild gibt es keine Vorschau."); return; }
  $("#coverImg").src = c.src;
  $("#coverCap").textContent = `${c.label} · ${c.desc} · ${h.name}`;
  $("#coverView").hidden = false;
}

// ====================================================================== Kontextmenü
function showMenu(x, y, items) {
  const m = $("#menu");
  m.innerHTML = "";
  items.forEach((it) => {
    if (it === "-") { m.appendChild(document.createElement("hr")); return; }
    const b = document.createElement("button");
    b.setAttribute("role", "menuitem");
    b.innerHTML = (it.icon || "") + esc(it.label);
    b.addEventListener("click", () => { hideMenu(); it.run(); });
    m.appendChild(b);
  });
  m.hidden = false;
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 8) + "px";
  m.style.top = Math.min(y, innerHeight - r.height - 8) + "px";
  m.querySelector("button")?.focus();
}
function hideMenu() { $("#menu").hidden = true; }

function rowMenu(e, tr) {
  const r = visRows()[+tr.dataset.n];
  if (!S.sel.has(r.key)) { S.sel = new Set([r.key]); S.anchor = r.key; paintSelection(); }
  const keys = selectedKeys();
  const sideEl = e.target.closest(".v");
  const side = sideEl ? sideEl.dataset.side : null;
  const items = [];
  if (S.view.both) {
    items.push({ label: `Markierte nach rechts (${keys.length})`, icon: ICON.right, run: () => copyKeys(keys, "lr") });
    items.push({ label: `Markierte nach links (${keys.length})`, icon: ICON.left, run: () => copyKeys(keys, "rl") });
    items.push("-");
  }
  for (const sd of side ? [side] : ["L", "R"]) {
    const cell = r[sd];
    const name = sd === "L" ? "links" : "rechts";
    if (cell && cell.xml) items.push({ label: `XML-Editor (${name})`, icon: ICON.edit, run: () => openXml(sd, r.key) });
    else if (cell && cell.editable) items.push({ label: `Bearbeiten (${name})`, icon: ICON.edit, run: () => startEdit(tr, sd) });
    if (cell && keys.some((k) => { const rr = S.view.rows.find((x) => x.key === k); return rr && rr[sd] && rr[sd].present; }))
      items.push({ label: `Markierte ${name} entfernen`, icon: ICON.trash, run: async () => applyState(await call("remove", sd, keys)) });
  }
  const cell = side ? r[side] : null;
  if (cell && cell.present) {
    items.push("-");
    items.push({ label: "Wert kopieren", icon: ICON.copy, run: () => navigator.clipboard?.writeText(cell.text).then(() => toast("Wert kopiert.")) });
    cell.links.forEach(([, , u]) => items.push({ label: `Link öffnen: ${u.length > 40 ? u.slice(0, 40) + "…" : u}`, icon: ICON.link, run: () => call("open_url", u) }));
    if (r.key.startsWith("APIC")) {
      items.push({ label: "Bild anzeigen", icon: ICON.image, run: () => openCover(side, r.key) });
      items.push({ label: "Bild ersetzen …", icon: ICON.edit, run: () => coverReplace(side, r.key) });
      items.push({ label: "Bild exportieren …", icon: ICON.copy, run: () => coverExport(side, r.key) });
    }
    const h = side === "L" ? S.view.left : S.view.right;
    if (h) items.push({ label: IS_MAC ? "Im Finder zeigen" : "Im Explorer zeigen", icon: ICON.folder, run: () => call("reveal", h.path) });
  }
  items.push("-");
  items.push({ label: "Feld hinzufügen …", icon: ICON.edit, run: () => addFieldCompare(side) });
  if (S.meta.unsaved && (S.view.left?.modified || S.view.right?.modified)) {
    items.push({ label: "Änderungen an diesem Paar verwerfen", icon: ICON.trash, run: async () => applyState(await call("revert_pair")) });
  }
  showMenu(e.clientX, e.clientY, items);
}

// ====================================================================== Ereignisse
let pairQueryTimer = null;
function bind() {
  $("#compareBtn").addEventListener("click", () => compare());
  ["#pathL", "#pathR"].forEach((s) => $(s).addEventListener("keydown", (e) => { if (e.key === "Enter") compare(); }));
  $$("[data-pick]").forEach((b) => b.addEventListener("click", async () => {
    const side = b.dataset.pick, inp = side === "L" ? $("#pathL") : $("#pathR");
    const p = await call("pick_path", side, b.dataset.folder === "1", inp.value.trim());
    if (p) {
      inp.value = p;
      homeSync();
      const other = side === "L" ? $("#pathR") : $("#pathL");
      if (other.value.trim()) compare();
    } else if (!S.settings.native) {
      toast("Pfad bitte direkt ins Feld eintippen oder einfügen.");
    }
  }));
  $("#swapBtn").addEventListener("click", async () => {
    if (!(await confirmDiscard())) return;
    const l = $("#pathL").value; $("#pathL").value = $("#pathR").value; $("#pathR").value = l; homeSync();
    if (S.pairs.length) compare(true, true);
  });
  $("#themeBtn").addEventListener("click", async () => {
    S.opts.theme = S.opts.theme === "light" ? "dark" : "light";
    applyTheme();
    await call("set_option", "theme", S.opts.theme);
  });
  $$(".nav[data-module]").forEach((b) => b.addEventListener("click", () => setModule(b.dataset.module)));

  // Paarliste
  $("#pairsScroll").addEventListener("scroll", () => requestAnimationFrame(drawPairWindow));
  $("#pairsInner").addEventListener("click", (e) => {
    const b = e.target.closest(".pair");
    if (!b) return;
    const i = +b.dataset.i;
    if (e.ctrlKey || e.metaKey) {           // Mehrfachauswahl für Sammelkopie / Tag-Fixer
      if (!S.pairSel.size && S.cur !== null) S.pairSel.add(S.cur);
      S.pairSel.has(i) ? S.pairSel.delete(i) : S.pairSel.add(i);
      S.pairAnchor = i;
    } else if (e.shiftKey && (S.pairAnchor ?? S.cur) !== null) {
      const a = S.visible.indexOf(S.pairAnchor ?? S.cur), z = S.visible.indexOf(i);
      S.pairSel = new Set(S.visible.slice(Math.min(a, z), Math.max(a, z) + 1));
    } else {
      S.pairSel.clear();
      S.pairAnchor = i;
      selectPair(i);
    }
    renderBulkBar();
    drawPairWindow();
  });
  $("#pairsScroll").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const k = S.visible.indexOf(S.cur);
    const nk = Math.max(0, Math.min(S.visible.length - 1, k + (e.key === "ArrowDown" ? 1 : -1)));
    if (S.visible[nk] !== undefined) selectPair(S.visible[nk]);
  });
  $("#pairChips").addEventListener("click", (e) => { const c = e.target.closest(".chip"); if (c) { S.chip = c.dataset.chip; applyPairFilter(false); } });
  $("#pairQuery").addEventListener("input", () => { clearTimeout(pairQueryTimer); pairQueryTimer = setTimeout(() => applyPairFilter(true), 250); });
  $("#advToggle").addEventListener("click", async () => {
    const adv = $("#adv");
    adv.hidden = !adv.hidden;
    $("#advToggle").setAttribute("aria-expanded", String(!adv.hidden));
    $("#advToggle").textContent = adv.hidden ? "Erweiterter Filter" : "Erweiterten Filter ausblenden";
    if (!adv.hidden) await refreshFieldChoices();
    applyPairFilter(true);
  });
  ["#fField", "#fOp", "#fSide"].forEach((s) => $(s).addEventListener("change", () => applyPairFilter(true)));
  $("#fVal").addEventListener("input", () => { clearTimeout(pairQueryTimer); pairQueryTimer = setTimeout(() => applyPairFilter(true), 300); });
  $("#fReset").addEventListener("click", () => { $("#fField").value = ""; $("#fVal").value = ""; $("#fOp").selectedIndex = 0; $("#fSide").selectedIndex = 0; applyPairFilter(true); });

  // Optionen
  $$(".seg button[data-filter]").forEach((b) => b.addEventListener("click", async () => applyState(await call("set_option", "filter", b.dataset.filter))));
  $("#trivBtn").addEventListener("click", async () => applyState(await call("set_option", "show_trivial", !S.opts.show_trivial)));
  $("#coverBtn").addEventListener("click", async () => applyState(await call("set_option", "show_covers", !S.opts.show_covers)));
  $("#emptySet").addEventListener("change", async (e) => applyState(await call("set_option", "empty_set", e.target.value)));
  let fq = null;
  $("#fieldQuery").addEventListener("input", (e) => { clearTimeout(fq); fq = setTimeout(async () => applyState(await call("set_option", "query", e.target.value)), 200); });
  $$("[data-copyall]").forEach((b) => b.addEventListener("click", () => copyAll(b.dataset.copyall)));
  $("#pairReloadBtn").addEventListener("click", reloadPair);
  $("#cmpSrc").addEventListener("change", (e) => { S.srcFilter = e.target.value; renderRows(); });      // #99
  $("#tbody").addEventListener("click", (e) => {
    const b = e.target.closest(".f-id .src-b"); if (!b) return;
    e.stopPropagation();
    const k = b.dataset.sid;
    S.srcFilter = S.srcFilter === k ? "" : k;
    renderRows();
    toast(S.srcFilter ? `Nur Felder mit Herkunft „${srcInfo(k)?.name || k}“ – erneut klicken zeigt alle.` : "Alle Herkünfte.");
  }, true);
  $$("[data-home]").forEach((b) => b.addEventListener("click", () => {     // #84
    const d = S.settings.defaults || {}, k = b.dataset.home;
    const inp = $(k === "L" ? "#pathL" : k === "R" ? "#pathR" : "#tgPath");
    inp.value = k === "L" ? d.left : k === "R" ? d.right : d.tagger;
    homeSync();
    toast("Standardordner eingetragen – „" + (k === "T" ? "Einlesen" : "Vergleichen") + "“ lädt ihn.");
  }));
  ["#pathL", "#pathR", "#tgPath"].forEach((s) => $(s).addEventListener("input", homeSync));
  $$("[data-missing]").forEach((b) => b.addEventListener("click", async () => applyState(await call("copy_missing", b.dataset.missing))));

  // Tabelle
  const tb = $("#tbody");
  tb.addEventListener("click", async (e) => {
    const a = e.target.closest("a[data-url]");
    if (a && !e.shiftKey && !e.ctrlKey && !e.metaKey) { e.preventDefault(); call("open_url", a.dataset.url); return; }
    const tr = e.target.closest(".tr");
    if (!tr) return;
    const xb = e.target.closest("[data-xml]");
    if (xb) { openXml(xb.closest(".v").dataset.side, tr.dataset.key); return; }
    const arrow = e.target.closest(".arrow");
    if (arrow) { copyKeys([tr.dataset.key], arrow.dataset.dir); return; }
    if (e.target.closest(".edit")) return;
    const key = tr.dataset.key, keys = rowKeys();
    if (e.shiftKey && S.anchor) {
      const a1 = keys.indexOf(S.anchor), b1 = keys.indexOf(key);
      S.sel = new Set(keys.slice(Math.min(a1, b1), Math.max(a1, b1) + 1));
    } else if (e.ctrlKey || e.metaKey) {
      S.sel.has(key) ? S.sel.delete(key) : S.sel.add(key);
      S.anchor = key;
    } else {
      S.sel = new Set([key]);
      S.anchor = key;
    }
    paintSelection();
  });
  tb.addEventListener("dblclick", (e) => {
    const v = e.target.closest(".v"), tr = e.target.closest(".tr");
    if (v && tr && !e.target.closest(".edit")) startEdit(tr, v.dataset.side);
  });
  tb.addEventListener("contextmenu", (e) => { const tr = e.target.closest(".tr"); if (tr) { e.preventDefault(); rowMenu(e, tr); } });
  $("#headL").addEventListener("click", (e) => { const c = e.target.closest("[data-cover]"); if (c) openCover(...c.dataset.cover.split("|")); });
  $("#headR").addEventListener("click", (e) => { const c = e.target.closest("[data-cover]"); if (c) openCover(...c.dataset.cover.split("|")); });
  $("#coverView").addEventListener("click", () => ($("#coverView").hidden = true));
  document.addEventListener("click", (e) => { if (!e.target.closest("#menu")) hideMenu(); });

  // Aktionsleiste
  $("#undoBtn").addEventListener("click", () => undoRedo(false));
  $("#redoBtn").addEventListener("click", () => undoRedo(true));
  $("#saveBtn").addEventListener("click", () => save());

  // Tastatur
  document.addEventListener("keydown", async (e) => {
    const mod = e.ctrlKey || e.metaKey;
    const inField = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "");
    if (e.key === "Escape") { hideMenu(); $("#coverView").hidden = true; }
    if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); save(); return; }
    if (inField) return;
    if (mod && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); undoRedo(false); }
    else if (mod && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); undoRedo(true); }
    else if (S.module !== "compare") { if (e.key === "F5") { e.preventDefault(); if (S.module === "tagger") taggerLoad(); } }
    else if (mod && e.key.toLowerCase() === "a" && S.view) { e.preventDefault(); S.sel = new Set(rowKeys()); paintSelection(); }
    else if (e.altKey && e.key === "ArrowRight") { e.preventDefault(); copyKeys(selectedKeys(), "lr"); }
    else if (e.altKey && e.key === "ArrowLeft") { e.preventDefault(); copyKeys(selectedKeys(), "rl"); }
    else if (e.key === "F5" && e.shiftKey) { e.preventDefault(); reloadPair(); }      // #82
    else if (e.key === "F5") { e.preventDefault(); compare(false, true); }
    else if ((e.key === "ArrowDown" || e.key === "ArrowUp") && S.view && document.activeElement === $("#table")) {
      e.preventDefault();
      const keys = rowKeys();
      let k = keys.indexOf(S.anchor) + (e.key === "ArrowDown" ? 1 : -1);
      k = Math.max(0, Math.min(keys.length - 1, k));
      S.sel = new Set([keys[k]]); S.anchor = keys[k]; paintSelection();
      $(`#tbody .tr[data-n="${k}"]`)?.scrollIntoView({ block: "nearest" });
    } else if ((e.key === "Enter" || e.key === "F2") && S.anchor && document.activeElement === $("#table")) {
      const tr = $(`#tbody .tr[data-key="${CSS.escape(S.anchor)}"]`);
      if (tr) { e.preventDefault(); startEdit(tr, "L"); }
    }
  });
  window.addEventListener("beforeunload", (e) => { if (S.meta.unsaved && !S.settings.native) { e.preventDefault(); e.returnValue = ""; } });
}

const MODULES = {
  db: ["Datenbank", "Das Datenbank-Modul ist geplant: die ganze Bibliothek durchsuchen, Statistiken, Duplikate finden."],
};
async function undoRedo(redo) {
  const st = await call(redo ? "redo" : "undo");
  if (S.pairs.length) await loadPairs();
  applyState(st);
  if (typeof taggerRefresh === "function") await taggerRefresh();
  if (S.module === "fixer") fixerPreview();
}

const MODULE_IDS = { compare: "moduleCompare", tagger: "moduleTagger", fixer: "moduleFixer", backups: "moduleBackups", plugins: "modulePlugins", settings: "moduleSettings", snapshots: "moduleSnapshots" };
function setModule(m, opts = {}) {
  S.module = m;
  $$(".nav[data-module]").forEach((b) => { b.classList.toggle("active", b.dataset.module === m); b.toggleAttribute("aria-current", b.dataset.module === m); });
  for (const [k, id] of Object.entries(MODULE_IDS)) $("#" + id).hidden = k !== m;
  $("#srcCompare").hidden = m !== "compare";
  $("#modulePlaceholder").hidden = m in MODULE_IDS;
  if (!(m in MODULE_IDS)) { $("#phTitle").textContent = MODULES[m][0]; $("#phText").textContent = MODULES[m][1]; }
  if (m === "fixer") fixerShow(opts.scope);
  if (m === "backups") backupsShow();
  if (m === "plugins" && typeof pluginsShow === "function") pluginsShow();
  if (m === "tagger" && typeof taggerShow === "function") taggerShow();
  if (m === "settings" && typeof settingsShow === "function") settingsShow();
  if (m === "snapshots" && typeof snapShow === "function") snapShow();
  if (typeof plRender === "function") plRender();
}

init().catch((e) => { console.error(e); info("Start fehlgeschlagen", String(e && e.message ? e.message : e)); });
