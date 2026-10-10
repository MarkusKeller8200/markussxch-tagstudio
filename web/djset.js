/* MarKusSXCH TagStudio – Seite „DJ-Set“ (#3): Titel aus dem Tagger sammeln, Reihenfolge nach Tonart, BPM und
   Energie optimieren, Übergänge bewerten, per Ziehen umsortieren, Titel sperren. Logik in setplan.py und
   session_djset.py; Wiedergabe über den Player (kind „tag“). */
"use strict";

const DJ = { st: null, sel: null, drag: null, busy: false };
const DJ_KIND = { same: "ok", adjacent: "ok", parallel: "ok", boost: "mid", jump: "bad", unknown: "unk" };
const DJ_KIND_SHORT = { same: "gleich", adjacent: "±1", parallel: "parallel", boost: "Sprung +", jump: "Sprung", unknown: "?" };

async function djsetShow() {
  try { djApply(await call("dj_state")); } catch (e) { toast(String(e.message || e)); }
}

/** Anzahl Titel im Set in der Seitenleiste (Wunsch des Users) */
function djSideCount(st) {
  const el = $("#djCount"); if (!el || !st) return;
  const n = st.items.length, live = st.items.filter((r) => !r.missing).length;
  el.textContent = n ? String(n) : "";
  el.title = n ? `${n} Titel im DJ-Set${live < n ? ` (${n - live} nicht geladen)` : ""}` : "DJ-Set ist leer";
}

function djApply(st) {
  DJ.st = st;
  djSideCount(st);
  if (st.message) toast(st.message);
  if (DJ.sel && !st.items.some((r) => r.path === DJ.sel)) DJ.sel = null;
  djOpts();
  djRender();
  djCharts();
}

async function djCall(name, ...args) {
  if (DJ.busy) return;
  DJ.busy = true;
  try { djApply(await call(name, ...args)); } catch (e) { toast(String(e.message || e)); }
  finally { DJ.busy = false; }
}

// ---------------------------------------------------------------- Optionen
function djOpts() {
  const o = DJ.st.opts;
  $("#djProfile").innerHTML = Object.entries(DJ.st.profiles).map(([k, l]) =>
    `<button type="button" role="radio" data-prof="${k}" class="${o.profile === k ? "on" : ""}" aria-checked="${o.profile === k}">${esc(l)}</button>`).join("");
  for (const k of ["w_key", "w_bpm", "w_energy"]) {
    const el = $(`#dj_${k}`); if (document.activeElement !== el) el.value = String(Math.round(o[k] * 100));
    $(`#dj_${k}_v`).textContent = Math.round(o[k] * 100);
  }
  if (document.activeElement !== $("#djMaxJump")) $("#djMaxJump").value = String(o.max_jump);
  $("#djMissing").value = o.missing;
}

// ---------------------------------------------------------------- Liste
function djDur(s) {
  s = Math.round(s || 0);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h}:${String(m).padStart(2, "0")} h` : `${m} min`;
}

function djTrans(t) {
  if (!t) return "";
  const cls = t.bpm_over ? "bad" : DJ_KIND[t.key];
  const bpm = t.bpm_pct === null ? "BPM ?" : `${t.bpm_pct.toFixed(1).replace(".", ",")} %${t.bpm_rel === "x2" ? " (×2)" : t.bpm_rel === "half" ? " (½)" : ""}`;
  const en = t.energy_delta === null ? "" : ` · Energie ${t.energy_delta > 0 ? "+" : ""}${t.energy_delta}`;
  const tip = `${DJ.st.key_kinds[t.key]} · BPM-Unterschied ${bpm}${t.bpm_over ? " – über dem Maximum" : ""}${en}`;
  return `<div class="dj-tr ${cls}" title="${esc(tip)}"><i class="dot"></i><span class="k">${esc(DJ_KIND_SHORT[t.key])}</span>
    <span class="b${t.bpm_over ? " over" : ""}">${esc(bpm)}</span><span class="grow"></span><span class="s">${t.score}</span></div>`;
}

function djRender() {
  const st = DJ.st, list = $("#djList");
  const live = st.items.filter((r) => !r.missing).length;
  const locks = st.items.some((r) => r.lock && !r.missing);
  $("#djOpt").textContent = locks ? "Rest optimieren" : "Optimieren";
  $("#djOpt").disabled = live < 2;
  $("#djRevert").disabled = !st.can_revert;
  $("#djClear").disabled = !st.items.length;
  $("#djExport").disabled = !st.items.length;
  $("#djFromTagger").disabled = !st.tagger;
  $("#djAllTagger").disabled = !st.tagger;
  const missing = st.items.length - live;
  $("#djScore").innerHTML = st.score === null ? '<span class="muted">Noch keine Note</span>'
    : `<span class="dj-note ${st.score >= 75 ? "ok" : st.score >= 50 ? "mid" : "bad"}">${st.score}</span>
       <span class="muted">${st.before !== null && st.before !== undefined ? `vorher ${st.before}` : "Note 0–100"}${st.energy_fit !== null && st.energy_fit !== undefined ? ` · Energieverlauf ${st.energy_fit}` : ""}</span>`;
  $("#djInfo").textContent = st.items.length
    ? `${live} Titel · ${djDur(st.duration)}${missing ? ` · ${missing} nicht geladen` : ""}${st.method ? ` · zuletzt ${st.method === "exact" ? "exakt" : "Näherung"} (${st.ms} ms)` : ""}`
    : "";
  if (!st.items.length) {
    list.innerHTML = `<div class="tg-empty">Noch keine Titel im Set. Im Tagger einen Ordner laden, Titel markieren und oben
      „+ Markierte aus dem Tagger“ wählen – oder im Tagger per Rechtsklick „Zum DJ-Set hinzufügen“.</div>`;
    return;
  }
  list.innerHTML = st.items.map((r, k) => {
    const e = r.energy === null ? "" : `<span class="dj-en${r.energy_est ? " est" : ""}" title="Energie ${r.energy}${r.energy_est ? " (aus dem BPM geschätzt)" : ""}${r.target !== undefined ? ` · Soll ${r.target}` : ""}">
        <i style="width:${r.energy}%"></i>${r.target !== undefined ? `<b style="left:${r.target}%"></b>` : ""}</span>`;
    const bpm = r.bpm ? (Math.round(r.bpm * 10) / 10).toString().replace(".", ",") : "–";
    return `<div class="dj-row${r.path === DJ.sel ? " sel" : ""}${r.missing ? " missing" : ""}${r.lock ? " locked" : ""}" data-k="${k}" draggable="true" role="option" aria-selected="${r.path === DJ.sel}" title="${esc(r.path)}">
        <span class="h" aria-hidden="true">⋮⋮</span>
        <span class="n">${r.missing ? "–" : r.pos + 1}</span>
        <button class="x lk${r.lock ? " on" : ""}" data-lock="${k}" title="${r.lock ? "Entsperren" : "Sperren: bleibt beim Optimieren an dieser Position"} (G)" aria-pressed="${r.lock}">${r.lock ? "🔒" : "🔓"}</button>
        <span class="kk">${r.key ? keyBadge(r.key) : '<span class="mx">–</span>'}</span>
        <span class="bp">${bpm}</span>
        <span class="en">${e}</span>
        <span class="t ellipsis">${esc(r.title || r.name)}${r.missing ? ' <span class="muted sm">(nicht im Tagger geladen)</span>' : ""}</span>
        <span class="d muted sm">${r.duration ? fmtTime(r.duration) : ""}</span>
        <button class="x" data-del="${k}" title="Aus dem Set entfernen (Entf)">✕</button>
      </div>${r.to_next ? djTrans(r.to_next) : ""}`;
  }).join("");
  const sel = list.querySelector(".dj-row.sel"); if (sel) sel.scrollIntoView({ block: "nearest" });
}

// ---------------------------------------------------------------- Grafiken
function djCharts() {
  const live = DJ.st.items.filter((r) => !r.missing);
  $("#djWheel").innerHTML = djWheelSvg(live);
  $("#djCurve").innerHTML = djCurveSvg(live);
}

function djWheelSvg(rows) {
  const C = 120, R = { B: 100, A: 66 };
  const pt = (code) => { const n = parseInt(code, 10), a = ((n % 12) * 30 - 90) * Math.PI / 180, r = R[code.slice(-1)];
    return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
  let g = `<circle cx="${C}" cy="${C}" r="${R.B}" class="ring"/><circle cx="${C}" cy="${C}" r="${R.A}" class="ring"/>`;
  const used = new Set(rows.map((r) => r.key).filter(Boolean));
  for (let n = 1; n <= 12; n++) for (const m of ["A", "B"]) {
    const code = n + m, [x, y] = pt(code), on = used.has(code);
    g += `<g class="wk${on ? " on" : ""}" style="${keyStyle(code)}"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${on ? 13 : 10}"/>
      <text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}">${code}</text></g>`;
  }
  const ks = rows.map((r) => r.key).filter(Boolean);
  let path = "";
  for (let i = 1; i < ks.length; i++) {
    if (ks[i] === ks[i - 1]) continue;
    const [x1, y1] = pt(ks[i - 1]), [x2, y2] = pt(ks[i]);
    path += `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" style="opacity:${(0.35 + 0.65 * i / ks.length).toFixed(2)}"/>`;
  }
  const start = ks.length ? (() => { const [x, y] = pt(ks[0]); return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="17" class="start"/>`; })() : "";
  return `<svg viewBox="0 0 240 240" class="dj-wheel" role="img" aria-label="Weg des Sets durch das Camelot-Rad"><g class="path">${path}</g>${g}${start}
    <text x="${C}" y="${C + 4}" class="c">${ks.length ? `${used.size} Tonarten` : "keine Tonart"}</text></svg>`;
}

function djCurveSvg(rows) {
  const W = 360, H = 150, L = 28, Rr = 34, T = 10, B = 22;
  if (rows.length < 2) return `<div class="muted sm c">Kurve ab zwei Titeln</div>`;
  const x = (i) => L + (W - L - Rr) * i / (rows.length - 1);
  const ye = (v) => T + (H - T - B) * (1 - v / 100);
  const bpms = rows.map((r) => r.bpm).filter(Boolean);
  const bLo = bpms.length ? Math.floor(Math.min(...bpms) - 2) : 100, bHi = bpms.length ? Math.ceil(Math.max(...bpms) + 2) : 140;
  const yb = (v) => T + (H - T - B) * (1 - (v - bLo) / Math.max(1, bHi - bLo));
  const line = (vals, f) => { let d = "", pen = false;
    vals.forEach((v, i) => { if (v === null || v === undefined) { pen = false; return; } d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${f(v).toFixed(1)}`; pen = true; });
    return d; };
  let grid = "";
  for (const v of [0, 50, 100]) grid += `<line x1="${L}" x2="${W - Rr}" y1="${ye(v)}" y2="${ye(v)}" class="gl"/><text x="${L - 4}" y="${ye(v) + 4}" class="ax e">${v}</text>`;
  grid += `<text x="${W - Rr + 4}" y="${yb(bHi) + 4}" class="ax b l">${bHi}</text><text x="${W - Rr + 4}" y="${yb(bLo) + 4}" class="ax b l">${bLo}</text>`;
  const tgt = rows.some((r) => r.target !== undefined) ? `<path d="${line(rows.map((r) => r.target), ye)}" class="tgt"/>` : "";
  const dots = rows.map((r, i) => r.energy === null ? "" : `<circle cx="${x(i).toFixed(1)}" cy="${ye(r.energy).toFixed(1)}" r="2.6" class="${r.energy_est ? "est" : ""}"><title>${i + 1}. Energie ${r.energy}${r.energy_est ? " (geschätzt)" : ""}${r.bpm ? ` · ${r.bpm} BPM` : ""}</title></circle>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" class="dj-curve" role="img" aria-label="Energie- und BPM-Verlauf">${grid}${tgt}
    <path d="${line(rows.map((r) => r.bpm || null), yb)}" class="bpm"/>
    <path d="${line(rows.map((r) => r.energy), ye)}" class="en"/><g class="dots">${dots}</g>
    <text x="${L}" y="${H - 6}" class="ax">1</text><text x="${W - Rr}" y="${H - 6}" class="ax" text-anchor="end">${rows.length}</text></svg>
    <div class="dj-legend sm muted"><span class="le en">Energie</span>${tgt ? '<span class="le tgt">Soll-Verlauf</span>' : ""}<span class="le bpm">BPM (rechte Achse)</span></div>`;
}

// ---------------------------------------------------------------- Aktionen
async function djAddFromTagger(all = false) {
  const idx = all ? null : (typeof tgSelected === "function" ? tgSelected() : []);
  if (!all && !idx.length) { toast("Im Tagger zuerst Titel markieren."); return; }
  try {
    const st = await call("dj_add", idx);
    if (S.module === "djset") djApply(st); else { DJ.st = st; djSideCount(st); toast(st.message); }
  } catch (e) { toast(String(e.message || e)); }
}

function djRowAt(k) { return DJ.st && DJ.st.items[k]; }

function djSelect(k, src = "key") {
  const r = djRowAt(k); if (!r) return;
  DJ.sel = r.path;
  $$("#djList .dj-row").forEach((el) => { const on = +el.dataset.k === k; el.classList.toggle("sel", on); el.setAttribute("aria-selected", String(on)); });
  const el = $(`#djList .dj-row[data-k="${k}"]`); if (el) el.scrollIntoView({ block: "nearest" });
  if (typeof playerFollow === "function") playerFollow(src);
}

/** Nächster geladener Titel nach dem laufenden (für Überblenden) als Tagger-Index oder null */
function djNextTag() {
  if (!DJ.st) return null;
  const items = DJ.st.items;
  let k = items.findIndex((r) => !r.missing && r.i === PLAYER.ref);
  if (k < 0) k = djSelIndex();
  for (let j = k + 1; j < items.length; j++) if (!items[j].missing) return items[j].i;
  return null;
}
function djSelectTag(i) {
  const k = DJ.st ? DJ.st.items.findIndex((r) => !r.missing && r.i === i) : -1;
  if (k >= 0) djSelect(k);
}

/** ⏮/⏭ im Player: nächster geladener Titel im Set */
async function djStep(dir, play = true) {
  if (!DJ.st) return;
  const n = DJ.st.items.length;
  let k = djSelIndex();
  for (let s = 0; s < n; s++) {
    k = k < 0 ? (dir > 0 ? 0 : n - 1) : k + dir;
    if (k < 0 || k >= n) return;
    if (!DJ.st.items[k].missing) break;
  }
  const wasPlaying = PLAYER.audio && !PLAYER.audio.paused;
  djSelect(k);
  if (!wasPlaying && play) { const t = djTarget(); if (t) plLoad(t, true); }
}
function djSelIndex() { return DJ.st ? DJ.st.items.findIndex((r) => r.path === DJ.sel) : -1; }

/** Player-Ziel auf dieser Seite: markierter Titel (nur wenn im Tagger geladen). */
function djTarget() {
  const r = DJ.st && DJ.st.items.find((x) => x.path === DJ.sel);
  return r && !r.missing ? { kind: "tag", ref: r.i } : null;
}

function djMove(k, dir) {
  const items = DJ.st.items.map((r) => r.path), j = k + dir;
  if (j < 0 || j >= items.length) return;
  [items[k], items[j]] = [items[j], items[k]];
  DJ.sel = items[j];
  djCall("dj_order", items);
}

function djKey(e) {
  if (S.module !== "djset" || e.target.closest("input,select,textarea") || !$("#modal").hidden) return;
  const k = djSelIndex(), n = DJ.st ? DJ.st.items.length : 0;
  if ((e.key === "ArrowDown" || e.key === "ArrowUp") && n) {
    e.preventDefault(); e.stopPropagation();
    const dir = e.key === "ArrowDown" ? 1 : -1;
    if (e.altKey && k >= 0) { djMove(k, dir); return; }
    djSelect(k < 0 ? 0 : Math.max(0, Math.min(n - 1, k + dir)));
  } else if ((e.key === "Delete" || e.key === "Backspace") && k >= 0) {
    e.preventDefault(); djCall("dj_remove", [DJ.st.items[k].path]);
  } else if ((e.key === "g" || e.key === "G") && !e.ctrlKey && !e.metaKey && !e.altKey && k >= 0) {
    e.preventDefault(); e.stopPropagation(); djCall("dj_lock", DJ.st.items[k].path, !DJ.st.items[k].lock);
  } else if (e.key === "Enter" && k >= 0) {
    e.preventDefault(); const t = djTarget(); if (t) plLoad(t, true);
  }
}

let djOptTimer = 0;
function djSetOpt(k, v, delay = 0) {
  clearTimeout(djOptTimer);
  djOptTimer = setTimeout(() => djCall("dj_set_opt", k, v), delay);
}

function djInit() {
  $("#djFromTagger").addEventListener("click", () => djAddFromTagger(false));
  $("#djAllTagger").addEventListener("click", () => djAddFromTagger(true));
  $("#djOpt").addEventListener("click", async () => {
    const b = $("#djOpt"), n = DJ.st ? DJ.st.items.filter((r) => !r.missing).length : 0;
    b.disabled = true; b.textContent = "Optimiere …";
    if (n > 15) status(`Optimiere ${n} Titel – das dauert einige Sekunden …`, "info");
    try { await djCall("dj_optimize"); } finally { if (DJ.st) djRender(); }
  });
  $("#djExport").addEventListener("click", (e) => { e.stopPropagation(); djExportMenu(); });
  $("#djRevert").addEventListener("click", () => djCall("dj_revert"));
  $("#djClear").addEventListener("click", async () => {
    const missing = DJ.st.items.some((r) => r.missing);
    const r = await modal({ title: "DJ-Set leeren", html: '<p style="margin:0">Alle Titel aus dem Set entfernen? Die Dateien bleiben unverändert.</p>',
      buttons: [...(missing ? [{ label: "Nur nicht geladene", value: "missing" }] : []), { label: "Abbrechen", value: null }, { label: "Leeren", value: "all", primary: true }] });
    if (r) djCall("dj_clear", r === "missing");
  });
  $("#djProfile").addEventListener("click", (e) => { const b = e.target.closest("[data-prof]"); if (b) djSetOpt("profile", b.dataset.prof); });
  for (const k of ["w_key", "w_bpm", "w_energy"]) {
    $(`#dj_${k}`).addEventListener("input", (e) => { $(`#dj_${k}_v`).textContent = e.target.value; djSetOpt(k, +e.target.value / 100, 350); });
  }
  $("#djMaxJump").addEventListener("change", (e) => djSetOpt("max_jump", +e.target.value || 8));
  $("#djMissing").addEventListener("change", (e) => djSetOpt("missing", e.target.value));
  const list = $("#djList");
  list.addEventListener("click", (e) => {
    const lk = e.target.closest("[data-lock]"), del = e.target.closest("[data-del]");
    if (lk) { const r = djRowAt(+lk.dataset.lock); djCall("dj_lock", r.path, !r.lock); return; }
    if (del) { djCall("dj_remove", [djRowAt(+del.dataset.del).path]); return; }
    const row = e.target.closest(".dj-row"); if (!row) return;
    list.focus({ preventScroll: true });
    if (e.detail === 2) { djSelect(+row.dataset.k); const t = djTarget(); if (t) plLoad(t, true); else toast("Titel ist im Tagger nicht geladen."); return; }
    djSelect(+row.dataset.k, "click");
  });
  list.addEventListener("contextmenu", (e) => {
    const row = e.target.closest(".dj-row"); if (!row) return;
    e.preventDefault();
    const k = +row.dataset.k, r = djRowAt(k);
    djSelect(k);
    const items = [];
    if (!r.missing) {
      items.push({ label: "In Player A abspielen", run: () => plLoad({ kind: "tag", ref: r.i }, true) });
      if (typeof PL2 !== "undefined" && PL2.layout === "top") items.push({ label: "In Player B laden", run: () => dbLoad({ kind: "tag", ref: r.i }, true) });
      items.push({ label: "Im Tagger zeigen", run: () => djShowInTagger(r.i) }, "-");
    }
    items.push({ label: r.lock ? "Entsperren" : "Sperren (Position halten)", run: () => djCall("dj_lock", r.path, !r.lock) },
      { label: "Nach oben", run: () => djMove(k, -1) }, { label: "Nach unten", run: () => djMove(k, 1) }, "-",
      { label: "Aus dem Set entfernen", run: () => djCall("dj_remove", [r.path]) });
    showMenu(e.clientX, e.clientY, items);
  });
  // Ziehen zum Umsortieren
  list.addEventListener("dragstart", (e) => {
    const row = e.target.closest(".dj-row"); if (!row) return;
    DJ.drag = +row.dataset.k;
    row.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", DJ.st.items[DJ.drag].path); } catch (err) { /* egal */ }
    const it = DJ.st.items[DJ.drag];                 // #105: auch auf Player A/B ziehbar
    if (!it.missing && typeof plDragStart === "function") plDragStart(e, { kind: "tag", ref: it.i });
  });
  list.addEventListener("dragover", (e) => {
    if (DJ.drag === null) return;
    const row = e.target.closest(".dj-row"); if (!row) return;
    e.preventDefault();
    const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
    $$("#djList .drop-a,#djList .drop-b").forEach((el) => el.classList.remove("drop-a", "drop-b"));
    row.classList.add(after ? "drop-b" : "drop-a");
  });
  list.addEventListener("dragend", () => { DJ.drag = null; $$("#djList .dragging,#djList .drop-a,#djList .drop-b").forEach((el) => el.classList.remove("dragging", "drop-a", "drop-b")); });
  list.addEventListener("drop", (e) => {
    const row = e.target.closest(".dj-row"); if (DJ.drag === null || !row) return;
    e.preventDefault();
    const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
    const items = DJ.st.items.map((x) => x.path), from = DJ.drag;
    let to = +row.dataset.k + (after ? 1 : 0);
    const [moved] = items.splice(from, 1);
    if (from < to) to--;
    items.splice(to, 0, moved);
    DJ.drag = null; DJ.sel = moved;
    djCall("dj_order", items);
  });
  document.addEventListener("keydown", djKey, true);
}

// ---------------------------------------------------------------- Exporte (#4)
function djExportMenu() {
  const b = $("#djExport").getBoundingClientRect();
  showMenu(b.left, b.bottom + 6, [
    { label: "M3U8-Playlist (absolute Pfade) …", run: () => djExport("m3u8", { relative: false }) },
    { label: "M3U8-Playlist (Pfade relativ zur Playlist) …", run: () => djExport("m3u8", { relative: true }) },
    { label: "Rekordbox-XML …", run: () => djExport("xml", { notation: "musical" }) },
    { label: "CSV für Excel (mit Übergangsbewertung) …", run: () => djExport("csv", {}) },
    "-",
    { label: "Spurnummern in Set-Reihenfolge schreiben …", run: djNumberDialog },
  ]);
}

async function djExport(fmt, opts) {
  if (!DJ.st || !DJ.st.items.length) { toast("Das Set ist leer."); return; }
  try {
    const r = await call("dj_export", fmt, opts);
    if (r && r.ok) { status(`${r.message} (${r.path})`, "info"); toast(r.message); }
  } catch (e) { toast(String(e.message || e)); }
}

async function djNumberDialog() {
  const idx = await call("dj_tag_indices");
  if (!idx.length) { toast("Keine geladenen Titel im Set."); return; }
  const prev = async (b) => {
    const r = await call("tag_number", idx, $("#djNumTot", b).checked, false);
    $("#djNumPrev", b).innerHTML = r.rows.length ? `<table><thead><tr><th>Datei</th><th>Bisher</th><th>Neu</th></tr></thead><tbody>${r.rows.map((x) => `<tr><td>${esc(x.name)}</td><td class="old">${esc(x.old) || "–"}</td><td class="new">${esc(x.new)}</td></tr>`).join("")}</tbody></table>` : '<div class="empty">Alle Spurnummern stimmen bereits.</div>';
  };
  const res = await modal({
    title: `Spurnummern in Set-Reihenfolge (${idx.length} Titel)`, wide: true,
    html: `<div class="hint">Schreibt das Feld „Spurnummer“ (TRCK) in der Reihenfolge des Sets. Nicht geladene Titel werden übersprungen. Rückgängig mit Strg+Z; gespeichert wird wie gewohnt mit „Speichern“.</div>
      <label class="check"><input type="checkbox" id="djNumTot" checked> Mit Gesamtzahl (z. B. 3/12)</label>
      <div class="fx-table" id="djNumPrev" style="max-height:50vh"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => { $("#djNumTot", b).addEventListener("change", () => prev(b)); prev(b); },
    collect: (b) => ({ tot: $("#djNumTot", b).checked }),
  });
  if (!res) return;
  const d = await call("tag_number", idx, res.tot, true);
  if (d.meta) { S.meta = d.meta; renderMeta(); }
  if (typeof taggerRefresh === "function" && TG.loaded) await taggerRefresh();
  toast(d.message || "Spurnummern gesetzt.");
}

async function djShowInTagger(i) {
  setModule("tagger");
  if (typeof tgSelect === "function") { try { await tgSelect(i, {}); } catch (e) { /* egal */ } }
}

djInit();
// Startseite DJ-Set: init() kann die Seite setzen, bevor dieses Skript geladen ist
if (typeof S !== "undefined" && S.module === "djset" && !DJ.st) djsetShow();
else setTimeout(() => { if (!DJ.st) call("dj_state").then(djSideCount).catch(() => {}); }, 800);   // Anzahl in der Seitenleiste
