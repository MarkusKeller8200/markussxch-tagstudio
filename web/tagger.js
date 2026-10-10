/* MarKusSXCH TagStudio – Tagger: Dateien eines Ordners auflisten, einzeln oder gemeinsam bearbeiten,
   Tags aus Dateinamen, Umbenennen, Spurnummern, Cover. Nutzt Funktionen aus app.js / modules.js. */
"use strict";

const TG = { settings: null, loaded: false, rows: [], order: [], sel: new Set(), anchor: null,
  sort: { col: "name", dir: 1 }, detail: null, editing: false,
  view: [], open: new Set(), flat: false };     // view: angezeigte Zeilen inkl. aufgeklappter Stems (#31)
const TG_COLS = [["m", ""], ["name", "Datei"], ["TIT2", "Titel"], ["TPE1", "Künstler"], ["TALB", "Album"],
  ["TRCK", "Spur"], ["TDRC", "Jahr"], ["TCON", "Genre"], ["TBPM", "BPM"], ["camelot", "Tonart"]];
const TG_ROW = 40;

// ---------------------------------------------------------------------- Anzeigen / Laden
async function taggerShow() {
  if (!TG.settings) {
    TG.settings = await call("tagger_settings");
    $("#histTg").innerHTML = TG.settings.hist.map((h) => `<option value="${esc(h)}"></option>`).join("");
    $("#tgPath").value = TG.settings.default || TG.settings.hist[0] || "";      // #84: Standardordner
    if (typeof homeSync === "function") homeSync();
    $("#tgRec").checked = !!TG.settings.recursive;
    const td = TG.settings.defaults || {};                                    // #86: Vorgaben beim Start
    if (td.sort_col) TG.sort = { col: td.sort_col, dir: td.sort_dir === -1 ? -1 : 1 };
    if (td.src_filter) TG.srcFilter = td.src_filter;
    renderTgHead();
    renderTgEditor();
    if (td.autoload && $("#tgPath").value && !TG.loaded) { await taggerLoad(); return; }
  }
  if (!TG.loaded) drawTgList();
  else await taggerRefresh();
  $("#tgTable").focus();
}

async function taggerLoad() {
  if (!(await confirmDiscard())) return;
  const path = $("#tgPath").value.trim();
  if (typeof homeSync === "function") homeSync();
  const res = await runTask(call("start_tag_load", path, $("#tgRec").checked), "Dateien einlesen");
  if (!res) return;
  if (res.cancelled) { status("Einlesen abgebrochen.", "warn"); return; }
  TG.settings = await call("tagger_settings");
  $("#histTg").innerHTML = TG.settings.hist.map((h) => `<option value="${esc(h)}"></option>`).join("");
  TG.loaded = true;
  if (typeof plForget === "function") plForget("tag");     // Indizes gelten nur für die vorige Liste
  const tr = await call("tag_rows");
  TG.rows = tr.rows; TG.flat = !!tr.stems_flat; TG.open = new Set();
  TG.sel = new Set(TG.rows.length ? [0] : []);
  TG.anchor = TG.rows.length ? 0 : null;
  tgApplyOrder();
  await tgLoadDetail();
  if (S.pairs.length) await refreshAll();  // gemeinsames Register: Vergleich frisch halten
  status(`${fmtN(res.files)} Datei(en) im Tagger${res.stems ? ` · ${fmtN(res.stems)} mit Stems (▸ aufklappen)` : ""}.`, res.files ? "ok" : "warn");
  if (typeof verifyWatch === "function") verifyWatch(res, `${fmtN(res.files)} Datei(en) im Tagger`);
  if (res.errors.length) await info(`${res.errors.length} Datei(en) nicht lesbar`, res.errors.slice(0, 30).join("\n"));
  if (typeof snDetect === "function") snDetect(path);       // #60: mitgegebenen Snapshot-Speicher anbieten
}

/** Nach Änderungen anderswo (Vergleich, Undo, Speichern …) */
async function taggerRefresh() {
  if (!TG.loaded) return;
  const tr = await call("tag_rows");
  TG.rows = tr.rows; TG.flat = !!tr.stems_flat;
  TG.sel = new Set([...TG.sel].filter((i) => i < TG.rows.length));
  tgApplyOrder();
  await tgLoadDetail();
}

async function tgLoadDetail() {
  taggerApplyDetail(await call("tag_detail", tgSelected()));
}

function tgSelected() { return TG.order.filter((i) => TG.sel.has(i)); }  // in Anzeige-Reihenfolge

/** Antwort der Tagger-Befehle anwenden */
function taggerApplyDetail(d) {
  if (!d) return;
  if (d.ask) return d;
  for (const r of d.rows || []) TG.rows[r.i] = r;
  TG.detail = d;
  if (d.meta) { S.meta = d.meta; renderMeta(); }
  drawTgList();
  if (!TG.editing) renderTgEditor();
  if (d.message) status(d.message, "info");
  if (d.errors && d.errors.length) info("Fehler", d.errors.join("\n"));
  return d;
}

// ---------------------------------------------------------------------- Liste
function trackNum(v) { const m = String(v || "").match(/^\s*(\d+)/); return m ? +m[1] : Infinity; }

function tgApplyOrder() {
  const q = ($("#tgQuery").value || "").trim().toLowerCase();
  const { col, dir } = TG.sort;
  let idx = TG.rows.filter((r) => r.parent === undefined).map((r) => r.i);   // Stems hängen unter dem Original
  const bpmNum = (v) => { const n = parseFloat(String(v || "").replace(",", ".")); return isFinite(n) ? n : Infinity; };
  const { text, nums } = tgParseQuery(q);                                    // #11: Zahlenfilter wie energy>=70
  if (text) idx = idx.filter((i) => { const r = TG.rows[i]; return [r.rel, r.TIT2, r.TPE1, r.TALB, r.TCON, r.TPE2].some((v) => (v || "").toLowerCase().includes(text)); });
  if (nums.length) idx = idx.filter((i) => { const r = TG.rows[i];
    return nums.every((f) => { const v = f.field === "bpm" ? bpmNum(r.TBPM) : r.feat ? r.feat[f.field] : null;
      return v !== null && v !== undefined && v !== Infinity && f.test(v); }); });
  const key = (r) => (col === "name" ? r.rel : col === "camelot" ? keySortValue(r.camelot) : col === "TRCK" ? (r.TPOS ? trackNum(r.TPOS) : 0) * 10000 + trackNum(r.TRCK)
    : col === "TBPM" ? bpmNum(r.TBPM) : col.startsWith("f:") ? (r.feat && r.feat[col.slice(2)] !== null && r.feat[col.slice(2)] !== undefined ? r.feat[col.slice(2)] : Infinity) : (r[col] || ""));
  idx.sort((a, b) => {
    const x = key(TG.rows[a]), y = key(TG.rows[b]);
    const ex = x === "" || x === Infinity || x === 999, ey = y === "" || y === Infinity || y === 999;
    if (ex !== ey) return ex ? 1 : -1;                     // leere Werte immer ans Ende, auch absteigend
    if (ex) return a - b;
    const c = typeof x === "number" ? x - y : String(x).localeCompare(String(y), "de", { numeric: true, sensitivity: "base" });
    return c * dir || a - b;
  });
  const view = [];
  for (const i of idx) {
    view.push({ i });
    const st = TG.rows[i].stems;
    if (st && TG.open.has(i)) st.forEach((x) => view.push(x.i !== null && x.i !== undefined ? { i: x.i, child: i } : { stem: x, child: i }));
  }
  TG.view = view;
  TG.order = view.filter((v) => v.i !== undefined).map((v) => v.i);
  const total = TG.rows.filter((r) => r.parent === undefined).length, nStem = TG.rows.filter((r) => r.stems).length;
  $("#tgCount").textContent = TG.rows.length ? (idx.length === total ? `${fmtN(idx.length)} Dateien` : `${fmtN(idx.length)} von ${fmtN(total)}`) + (TG.sel.size > 1 ? ` · ${TG.sel.size} markiert` : "") : "";
  $("#tgStemBtns").hidden = !nStem;
  $("#tgInner").style.height = view.length * TG_ROW + "px";
  drawTgList();
}

// ---------------------------------------------------------------------- Audio-Merkmale als Spalten und Filter (#11)
function tgFeatCols() {
  const list = (TG.settings && TG.settings.features) || [];
  const want = new Set(LAYOUT.tg_feat_cols || []);
  return list.filter(([n]) => want.has(n));
}

const TG_FEAT_ALIAS = { energie: "ENERGY", tanz: "DANCEABILITY", dance: "DANCEABILITY", froh: "HAPPINESS", happy: "HAPPINESS",
  stimmung: "VALENCE", valenz: "VALENCE", akustik: "ACOUSTICNESS", acoustic: "ACOUSTICNESS", instrument: "INSTRUMENTALNESS",
  live: "LIVENESS", sprache: "SPEECHINESS", speech: "SPEECHINESS", hell: "BRIGHTNESS", bright: "BRIGHTNESS",
  aggress: "AGGRESSIVENESS", tempo: "bpm" };

/** Suchtext in Text und Zahlenfilter zerlegen: „energy>=70 bpm:120-128 house“ → {text: "house", nums: [...]} */
function tgParseQuery(q) {
  const names = ((TG.settings && TG.settings.features) || []).map(([n]) => n);
  const field = (w) => {
    w = w.toLowerCase();
    if (w === "bpm") return "bpm";
    const a = Object.keys(TG_FEAT_ALIAS).find((k) => w.startsWith(k) || (w.length >= 3 && k.startsWith(w)));
    if (a) return TG_FEAT_ALIAS[a];
    return names.find((n) => w.length >= 3 && n.toLowerCase().startsWith(w)) || null;
  };
  const norm = String(q || "").replace(/≥/g, ">=").replace(/≤/g, "<=").replace(/([a-zäöü])\s*(>=|<=|>|<|=|:)\s*(?=\d)/gi, "$1$2");
  const text = [], nums = [];
  for (const tok of norm.split(/\s+/).filter(Boolean)) {
    const m = tok.match(/^([a-zäöü]+)(>=|<=|>|<|=|:)(\d+(?:[.,]\d+)?)(?:-(\d+(?:[.,]\d+)?))?$/i);
    const f = m && field(m[1]);
    if (!f) { text.push(tok); continue; }
    const a = parseFloat(m[3].replace(",", ".")), b = m[4] !== undefined ? parseFloat(m[4].replace(",", ".")) : null;
    const op = m[2];
    const test = b !== null ? (v) => v >= Math.min(a, b) && v <= Math.max(a, b)
      : op === ">=" ? (v) => v >= a : op === "<=" ? (v) => v <= a : op === ">" ? (v) => v > a : op === "<" ? (v) => v < a
      : f === "bpm" ? (v) => Math.abs(v - a) < 0.5 : (v) => v === a;
    nums.push({ field: f, test });
  }
  return { text: text.join(" ").toLowerCase(), nums };
}

function tgFeatMenu(btn) {
  const list = (TG.settings && TG.settings.features) || [];
  const on = new Set(LAYOUT.tg_feat_cols || []);
  const toggle = (n) => {
    const s = new Set(LAYOUT.tg_feat_cols || []);
    s.has(n) ? s.delete(n) : s.add(n);
    LAYOUT.tg_feat_cols = list.map(([x]) => x).filter((x) => s.has(x));
    saveUi("tg_feat_cols"); renderTgHead(); drawTgList();
  };
  const r = btn.getBoundingClientRect();
  showMenu(r.left, r.bottom + 6, [
    ...list.map(([n, label, desc]) => ({ label: `${on.has(n) ? "✓ " : "    "}${label} – ${desc}`, run: () => toggle(n) })),
    "-",
    { label: "Alle Merkmal-Spalten ausblenden", run: () => { LAYOUT.tg_feat_cols = []; saveUi("tg_feat_cols"); renderTgHead(); drawTgList(); } },
    { label: "Filter-Beispiel einsetzen: energy>=70", run: () => { $("#tgQuery").value = "energy>=70"; tgApplyOrder(); $("#tgQuery").focus(); } },
  ]);
}

function renderTgHead() {
  $("#tgTable").classList.toggle("covers", !!LAYOUT.tg_cover_col);       // #73
  const cb = $("#tgCoverCol"); if (cb) cb.classList.toggle("on", !!LAYOUT.tg_cover_col);
  const fcols = tgFeatCols();
  const fb = $("#tgFeatCols"); if (fb) { fb.classList.toggle("on", fcols.length > 0); fb.textContent = fcols.length ? `Merkmale (${fcols.length}) ▾` : "Merkmale ▾"; }
  $("#tgTable").style.setProperty("--tg-feat", fcols.length ? `repeat(${fcols.length}, 52px)` : " ");
  $("#tgTable").classList.toggle("feat", fcols.length > 0);
  $("#tgTable").classList.toggle("feat-many", fcols.length >= 4);
  $("#tgHead").innerHTML = TG_COLS.map(([k, l]) => {
    if (k === "m") return "<span></span>";
    const b = `<button data-sort="${k}" class="${TG.sort.col === k ? "on" : ""}">${esc(l)}${TG.sort.col === k ? (TG.sort.dir > 0 ? " ▴" : " ▾") : ""}</button>`;
    return k === "name" ? `<span class="th-name">${b}<span class="col-grip" id="tgNameGrip" role="separator" aria-orientation="vertical" aria-label="Breite der Spalte Datei" tabindex="0" title="Ziehen: Breite ändern · Doppelklick: automatisch"></span></span>` : b;
  }).join("") + fcols.map(([n, label, desc]) => { const k = "f:" + n, on = TG.sort.col === k;
    return `<button data-sort="${k}" class="ft-h${on ? " on" : ""}" title="${esc(label)} – ${esc(desc)} (0–100)">${esc(label.slice(0, 7))}${on ? (TG.sort.dir > 0 ? " ▴" : " ▾") : ""}</button>`; }).join("");
  const grip = $("#tgNameGrip");     // #41: Breite der Datei-Spalte
  const setW = (w) => { LAYOUT.tg_col_name = w ? clamp(Math.round(w), 110, 900) : 0; applyLayout(); };
  draggable(grip, {
    onStart: () => ({ w: grip.parentElement.getBoundingClientRect().width }),
    onMove: (dx, st) => setW(st.w + dx),
    onEnd: () => saveUi("tg_col_name"),
    onDouble: () => { setW(0); saveUi("tg_col_name"); },
    onKey: (d) => { setW((LAYOUT.tg_col_name || grip.parentElement.getBoundingClientRect().width) + d); saveUi("tg_col_name"); },
  });
}

function drawTgList() {
  const sc = $("#tgScroll"), inner = $("#tgInner");
  if (!TG.loaded) { inner.innerHTML = '<div class="tg-empty">Oben einen Ordner oder eine MP3-Datei wählen und auf <b>Einlesen</b> klicken.</div>'; inner.style.height = ""; return; }
  if (!TG.view.length) { inner.innerHTML = `<div class="tg-empty">${TG.rows.length ? "Keine Datei passt zum Filter." : "Keine MP3-Dateien gefunden."}</div>`; return; }
  const first = Math.max(0, Math.floor(sc.scrollTop / TG_ROW) - 6);
  const last = Math.min(TG.view.length, Math.ceil((sc.scrollTop + sc.clientHeight) / TG_ROW) + 6);
  let h = "";
  const sel1 = TG.sel.size === 1 ? TG.rows[[...TG.sel][0]] : null;
  const fit = new Set(sel1 && sel1.camelot ? keyCompat(sel1.camelot) : []);
  const mb = (b) => (b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1).replace(".", ",")} MB`);
  const fcols = tgFeatCols();
  for (let k = first; k < last; k++) {
    const v = TG.view[k];
    if (v.stem) {         // FLAC/WAV-Spur: nur anhören / zeigen
      const x = v.stem;
      h += `<div class="tg-row stem-x child" style="top:${k * TG_ROW}px" data-stem="${esc(x.path)}" title="${esc(x.path)}">
        <span></span><span class="fn"><span class="tw-ind">└</span><span class="nm"><b>${esc(x.name)}</b></span><span class="sx">${esc(x.ext)} · ${mb(x.size)}</span></span>
        <span class="stem-acts"><button class="ghost sm" data-splay="1" title="Spur anhören">▶ Anhören</button><button class="ghost sm" data-sreveal="1">${IS_MAC ? "Im Finder" : "Im Explorer"}</button></span></div>`;
      continue;
    }
    const r = TG.rows[v.i];
    const tw = r.stems ? `<button class="tw" data-tw="${r.i}" aria-expanded="${TG.open.has(r.i)}" title="Stems ${TG.open.has(r.i) ? "zuklappen" : "aufklappen"}">${TG.open.has(r.i) ? "▾" : "▸"}</button>` : "";
    const name = v.child !== undefined ? `<span class="tw-ind">└</span><span class="nm"><b>${esc(r.stem || r.name)}</b></span><span class="sx">MP3</span>`
      : `${tw}<span class="nm">${esc(r.rel)}</span>${r.stems ? `<span class="stem-b" title="${esc(r.stems.map((x) => x.name + " (" + x.ext + ")").join(", "))}">${r.stems.length} Stems</span>` : ""}`;
    h += `<div class="tg-row${TG.sel.has(r.i) ? " sel" : ""}${v.child !== undefined ? " child" : ""}" style="top:${k * TG_ROW}px" data-i="${r.i}" title="${esc(r.rel)}">
      <span>${r.modified ? '<span class="m" title="ungespeichert"></span>' : ""}</span>
      <span class="fn">${LAYOUT.tg_cover_col && v.child === undefined ? `<span class="tg-thumb${r.ch ? "" : " none"}"${r.ch ? ` data-ch="${r.ch}"` : ""}>${r.ch && TG_THUMBS.get(r.ch) ? `<img src="${TG_THUMBS.get(r.ch)}" alt="">` : ""}</span>` : ""}${name}${rateMini(r.rating, r.like)}</span><span>${esc(r.TIT2)}</span><span>${esc(r.TPE1)}</span><span>${esc(r.TALB)}</span>
      <span>${esc(r.TRCK)}</span><span>${esc(r.TDRC)}</span><span>${esc(r.TCON)}</span><span class="num">${esc(r.TBPM)}</span>
      <span title="${esc(r.TKEY)}">${r.camelot ? keyBadge(r.camelot, fit.size && !TG.sel.has(r.i) ? (fit.has(r.camelot) ? "fit" : "") : "") : `<span class="mx">${esc(r.TKEY)}</span>`}</span>${fcols.map(([n]) => { const v = r.feat ? r.feat[n] : null;
        return v === null || v === undefined ? "<span></span>" : `<span class="ft-c"><i style="width:${v}%"></i>${v}</span>`; }).join("")}</div>`;
  }
  inner.innerHTML = h;
  if (LAYOUT.tg_cover_col) tgThumbsLoad();
}

// ---------------------------------------------------------------------- Cover-Spalte (#73)
const TG_THUMBS = new Map();     // Hash → Bild (gleiche Cover eines Albums nur einmal)
const TG_THUMB_WAIT = new Set();
async function tgThumbsLoad() {
  const need = [...new Set($$("#tgInner .tg-thumb[data-ch]").map((e) => e.dataset.ch))].filter((h) => !TG_THUMBS.has(h) && !TG_THUMB_WAIT.has(h));
  for (const h of need) {
    TG_THUMB_WAIT.add(h);
    try { const r = await call("tag_cover_thumb", h); TG_THUMBS.set(h, r.ok ? r.src : ""); } catch (e) { TG_THUMBS.set(h, ""); }
    TG_THUMB_WAIT.delete(h);
    const src = TG_THUMBS.get(h);
    $$(`#tgInner .tg-thumb[data-ch="${h}"]`).forEach((el) => { el.innerHTML = src ? `<img src="${src}" alt="">` : ""; });
  }
}
function tgCoverPop(e) {
  const th = e.target.closest && e.target.closest(".tg-thumb[data-ch]"), pop = $("#tgThumbPop");
  if (!th || e.type === "mouseout") { if (pop) pop.hidden = true; return; }
  const src = TG_THUMBS.get(th.dataset.ch); if (!src) return;
  const r = th.getBoundingClientRect();
  pop.innerHTML = `<img src="${src}" alt="">`;
  pop.hidden = false;
  pop.style.left = (r.right + 8) + "px";
  pop.style.top = Math.max(8, Math.min(innerHeight - 228, r.top - 90)) + "px";
}

/** Stems eines Originals auf-/zuklappen (open: true/false/undefined = umschalten) */
function tgToggleStems(i, open) {
  const want = open === undefined ? !TG.open.has(i) : open;
  if (want) TG.open.add(i); else {
    TG.open.delete(i);
    (TG.rows[i].stems || []).forEach((x) => { if (x.i !== null && x.i !== undefined) TG.sel.delete(x.i); });
    if (!TG.sel.size) TG.sel.add(i);
  }
  tgApplyOrder();
}

function tgScrollTo(i) {
  const k = TG.view.findIndex((v) => v.i === i), sc = $("#tgScroll");
  if (k < 0) return;
  const top = k * TG_ROW;
  if (top < sc.scrollTop) sc.scrollTop = top;
  else if (top + TG_ROW > sc.scrollTop + sc.clientHeight) sc.scrollTop = top + TG_ROW - sc.clientHeight;
}

async function tgSelect(i, e = {}) {
  if (e.ctrlKey || e.metaKey) { TG.sel.has(i) ? TG.sel.delete(i) : TG.sel.add(i); TG.anchor = i; }
  else if (e.shiftKey && TG.anchor !== null) {
    const a = TG.order.indexOf(TG.anchor), z = TG.order.indexOf(i);
    TG.sel = new Set(TG.order.slice(Math.min(a, z), Math.max(a, z) + 1));
  } else { TG.sel = new Set([i]); TG.anchor = i; }
  tgApplyOrder();
  await tgLoadDetail();
  if (typeof playerFollow === "function") playerFollow(e && e.type === "click" ? (e.shiftKey || e.ctrlKey || e.metaKey ? "multi" : "click") : "key");
}

/** #97: Bewertung/Like für alle markierten Dateien (Sterne neben dem Cover, Tasten 0–5/F). */
async function tgMark(stars, like) {
  const idx = tgSelected();
  if (!idx.length) return;
  const r = TG.detail && TG.detail.rating;
  if (stars !== null && stars !== undefined && r && !r.mixed && r.value === stars) stars = 0;   // gleicher Stern: löschen
  if (like === "toggle") like = !(r && r.like);
  const d = await call("tag_set_rating", idx, stars ?? null, like ?? null);
  taggerApplyDetail(d);
  if (PLAYER.info && PLAYER.kind === "tag" && idx.includes(PLAYER.ref)) {
    const row = TG.rows[PLAYER.ref];
    if (row) { PLAYER.info.rating = row.rating; PLAYER.info.like = row.like; plRender(); }
  }
  if (d.message) toast(d.message);
}

/** Länge neben dem Cover (#34): ein Titel bzw. Gesamtlänge der markierten Titel. */
function tgLength(d) {
  const L = d.length;
  if (!L || !L.total) return "";
  const t = Math.round(L.total), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  const txt = h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
  return `<span class="tg-len" title="${L.count > 1 ? "Gesamtlänge der markierten Titel" : "Länge"}"><svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2"/><path d="M10 2h4"/></svg>${L.count > 1 ? `${txt} <span class="muted">gesamt · ${L.count} Titel</span>` : txt}</span>`;
}

// ---------------------------------------------------------------------- Bearbeiten
function renderTgEditor() {
  const box = $("#tgEdit"), d = TG.detail;
  if (!TG.loaded || !d || !d.count) {
    box.innerHTML = `<div class="tg-empty">${TG.loaded ? "Links eine oder mehrere Dateien markieren (Klick, Shift, Strg/Cmd)." : "Noch keine Dateien geladen."}</div>`;
    return;
  }
  const one = d.count === 1;
  const head = one
    ? `<div><h3>${esc(d.file.name)}</h3><div class="tags">${d.file.info.split(/\s{2,}/).filter(Boolean).slice(1).map((p) => `<span>${esc(p)}</span>`).join("")}</div></div>`
    : `<div><h3>${d.count} Dateien gewählt</h3><div class="hint">Felder mit „verschieden“ bleiben unverändert, solange du nichts einträgst.</div></div>`;
  const c = d.cover;
  const coverImg = c.state === "same" && c.src ? `<img src="${c.src}" alt="">` : c.state === "mixed" ? '<span class="hint">verschieden</span>' : ICON.note;
  const form = TG.settings.fields.map(([k, label]) => {
    const v = d.common[k];
    const inp = `<input id="tgf-${k}" data-key="${k}" value="${esc(v.value)}" ${v.mixed ? 'placeholder="‹verschieden›"' : ""} spellcheck="false">`;
    if (k === "TKEY") return `<label for="tgf-${k}">${esc(label)}</label><div class="key-inp">${inp}<button class="key-btn${KW.open ? " on" : ""}" id="tgKeyBtn" title="Camelot-Rad öffnen" aria-label="Camelot-Rad öffnen">${v.camelot ? keyBadge(v.camelot) : '<svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 3v4.5M12 16.5V21M3 12h4.5M16.5 12H21"/></svg>'}</button></div>`;
    const u = !v.mixed && firstUrl(v.value);
    if (u) return `<label for="tgf-${k}">${esc(label)}</label><div class="url-inp">${inp}<a class="url-btn" data-url="${esc(u)}" title="${esc(u)} öffnen" aria-label="Link öffnen"><svg class="i" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg></a></div>`;
    return `<label for="tgf-${k}">${esc(label)}</label>${inp}`;
  }).join("");
  const PEN = '<svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';
  const DEL = '<svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
  const srcs = {};
  (one ? d.fields : []).forEach((f) => { const k = f.src || ""; srcs[k] = (srcs[k] || 0) + 1; });
  if (TG.srcFilter && !(TG.srcFilter in srcs)) TG.srcFilter = "";
  const shownFields = one ? d.fields.filter((f) => !TG.srcFilter || (f.src || "") === (TG.srcFilter === "-" ? "" : TG.srcFilter)) : [];
  const srcOpts = Object.keys(srcs).filter(Boolean).sort((a, b) => (srcInfo(a)?.name || a).localeCompare(srcInfo(b)?.name || b));
  const srcSel = srcOpts.length ? `<select id="tgSrcF" class="inp" title="Weitere Felder nach Herkunft filtern" aria-label="Nach Herkunft filtern">
      <option value="">Alle Herkünfte</option>${srcOpts.map((k) => `<option value="${esc(k)}"${TG.srcFilter === k ? " selected" : ""}>${esc(srcInfo(k)?.name || k)} (${srcs[k]})</option>`).join("")}
      ${srcs[""] ? `<option value="-"${TG.srcFilter === "-" ? " selected" : ""}>ohne bekannte Herkunft (${srcs[""]})</option>` : ""}</select>
      ${TG.srcFilter && TG.srcFilter !== "-" && srcInfo(TG.srcFilter)?.kind !== "id3" ? `<button class="ghost sm" id="tgSrcDel" data-src="${esc(TG.srcFilter)}">Alle entfernen …</button>` : ""}` : "";
  const more = one && d.fields.length ? `<div class="tg-more-tools"><h4>Weitere Felder <span class="muted sm" style="font-weight:400">${shownFields.length === d.fields.length ? d.fields.length : `${shownFields.length} von ${d.fields.length}`}</span></h4>${srcSel}</div>
    <div class="tg-more">
      <div class="tg-more-head"><span class="k">Feld<span class="col-grip" id="tgMoreGrip" role="separator" aria-orientation="vertical" aria-label="Breite der Feldnamen" tabindex="0" title="Ziehen: Breite ändern · Doppelklick: Standardbreite"></span></span><span>Wert</span><span></span></div>
      ${shownFields.map((f) => {
        const full = f.edit || f.text, ml = f.multiline;
        const shown = ml ? full : (f.text.length > 160 ? f.text.slice(0, 160) + " …" : f.text);
        return `<div class="tg-f" data-key="${esc(f.key)}"><span class="k" title="${esc(f.label + "\n" + f.key)}">${srcBadge(f.ver)}${f.src ? `<span class="src-click" data-srcf="${esc(f.src)}" title="Klick: nur Felder dieser Herkunft zeigen (erneut: alle)">${srcBadge(f.src)}</span>` : ""}${f.mod ? '<span class="m" style="display:inline-block;width:7px;height:7px;border-radius:99px;background:var(--acc);margin-right:6px"></span>' : ""}${esc(f.label)}</span>
      <span class="v${f.editable ? "" : " noedit"}${ml ? " ml" : ""}" title="${f.editable ? "Doppelklick: bearbeiten" : ""}">${f.xml ? `<button class="xml-badge${f.xml === "view" ? " view" : ""}" data-txml="1">XML</button>` : ""}${COLOR_KEY_RE.test(f.key) ? colorSwatch(full) : ""}${linkify(shown)}</span>
      <span class="b">${f.editable || f.xml || f.blob ? `<button class="x" data-tedit="1" title="${f.blob ? "Binärfeld ansehen/bearbeiten" : "Im Editor bearbeiten"}" aria-label="${esc(f.label)} bearbeiten">${PEN}</button>` : ""}<button class="x del" data-tdel="1" title="Feld entfernen" aria-label="${esc(f.label)} entfernen">${DEL}</button></span></div>`;
      }).join("")}</div>` : "";
  const act = document.activeElement && box.contains(document.activeElement) ? document.activeElement.id : null;
  box.innerHTML = `${head}
    <div class="tg-cover"><button class="cover" id="tgCoverBig" title="${esc(c.desc || (c.state === "mixed" ? "unterschiedliche Cover" : "kein Cover"))}">${coverImg}</button>
      <div class="tg-cover-btns"><div class="row"><button class="ghost sm" id="tgCoverSet">Cover wählen …</button><button class="ghost sm" id="tgCoverDel" ${c.state === "none" ? "disabled" : ""}>Cover entfernen</button></div>
      <span class="hint" title="${esc(c.desc || "")}">${esc(c.desc || (c.state === "mixed" ? "unterschiedlich" : "kein Cover"))}</span><div class="tg-lenrate">${tgLength(d)}${d.rating ? rateHtml(d.rating.value, d.rating.like, { cls: "tg-rate", keys: true }) : ""}</div></div></div>
    <div class="tg-form">${form}
      <label for="tgVer">ID3-Version</label><select id="tgVer" class="inp" style="height:36px"><option value="3">ID3v2.3 (verbreitet)</option><option value="4">ID3v2.4 (Mehrfachwerte)</option>${d.version ? "" : '<option value="" selected>verschieden</option>'}</select>
    </div>
    ${typeof featSection === "function" ? featSection(d) : ""}
    <div class="tg-tools">
      <button class="ghost" id="tgFromName">Tags aus Dateiname …</button>
      <button class="ghost" id="tgRename">Dateien umbenennen …</button>
      <button class="ghost" id="tgNumber" ${d.count > 1 ? "" : "disabled"}>Spurnummern …</button>
      <button class="ghost" id="tgAddField">Feld hinzufügen …</button>
      <button class="ghost" id="tgFixer">Tag-Fixer …</button>
      <button class="ghost" id="tgCase">Groß-/Kleinschreibung …</button>
      <button class="ghost" id="tgReplace">Suchen &amp; Ersetzen …</button>
      <button class="ghost" id="tgFolderCover">Cover aus Ordner …</button>
      <button class="ghost" id="tgExport">Liste exportieren …</button>
      <button class="ghost" id="tgOrigin">Felder nach Herkunft …</button>
      ${tgSelected().some((i) => TG.rows[i] && (TG.rows[i].stems || TG.rows[i].parent !== undefined)) ? '<button class="ghost" id="tgStemTags" title="Tags der Originale auf ihre MP3-Stems übertragen">Stems: Tags vom Original …</button>' : ""}
      ${one ? '<button class="ghost" id="tgReveal">' + (IS_MAC ? "Im Finder zeigen" : "Im Explorer zeigen") + "</button>" : ""}
    </div>
    <div class="tg-plugins" id="tgPlugins"></div>${more}`;
  if (d.version) $("#tgVer").value = String(d.version);
  if (act && $("#" + act)) { const el = $("#" + act); el.focus(); if (el.setSelectionRange && el.value && /^(text|search)$/.test(el.type)) el.setSelectionRange(el.value.length, el.value.length); }
  keyWheelSync();
  tgRenderPlugins();
  const grip = $("#tgMoreGrip");
  if (grip) {
    const setK = (w) => { LAYOUT.tg_more_k = clamp(Math.round(w), 70, Math.max(120, box.clientWidth - 160)); document.documentElement.style.setProperty("--tg-more-k", LAYOUT.tg_more_k + "px"); };
    draggable(grip, {
      onStart: () => ({ w: LAYOUT.tg_more_k }),
      onMove: (dx, st) => setK(st.w + dx),
      onEnd: () => saveUi("tg_more_k"),
      onDouble: () => { setK(130); saveUi("tg_more_k"); },
      onKey: (dd) => { setK(LAYOUT.tg_more_k + dd); saveUi("tg_more_k"); },
    });
  }
}

async function tgRenderPlugins() {
  if (!$("#tgPlugins") || typeof pluginActions !== "function") return;
  const acts = await pluginActions("tagger");
  const box = $("#tgPlugins");
  if (!box) return;
  box.innerHTML = acts.length
    ? `<h4>Plugins</h4><div class="tg-tools">${acts.map((a) => `<button class="ghost" data-plugin="${esc(a.plugin)}" data-action="${esc(a.id)}" title="${esc(a.description || a.plugin_name)}">${esc(a.label)}</button>`).join("")}</div>`
    : "";
}

async function tgCommit(input) {
  const key = input.dataset.key, v = TG.detail.common[key];
  const val = input.value;
  if (val === v.value || (v.mixed && val === "")) return;
  taggerApplyDetail(await call("tag_set", tgSelected(), key, val));
}

// ---------------------------------------------------------------------- Werkzeuge
const PH = ["%track%", "%artist%", "%title%", "%album%", "%albumartist%", "%year%", "%disc%", "%genre%", "%composer%", "%dummy%"];

async function tgPatternDialog(kind) {
  const idx = tgSelected();
  const isRename = kind === "rename";
  const pat = (TG.settings.patterns || {})[isRename ? "rename" : "from"] || "%track% - %artist% - %title%";
  let last = null, timer = null;
  const preview = async (b) => {
    const p = $("#patIn", b).value;
    const r = await call(isRename ? "tag_rename" : "tag_from_filename", idx, p, false);
    last = r;
    const rows = isRename
      ? r.rows.map((x) => `<tr><td class="old">${esc(x.old)}</td><td class="${x.problem ? "st-missing" : x.new === x.old ? "old" : "new"}">${esc(x.new)}${x.problem ? `<br><small>${esc(x.problem)}</small>` : ""}</td></tr>`)
      : r.rows.map((x) => `<tr><td class="${x.match ? "" : "st-missing"}">${esc(x.name)}</td><td>${x.match ? (x.changes.length ? x.changes.map(([l, o, n]) => `${esc(l)}: <span class="old">${esc(o) || "–"}</span> → <span class="new">${esc(n)}</span>`).join("<br>") : '<span class="old">keine Änderung</span>') : '<span class="st-missing">Muster passt nicht</span>'}</td></tr>`);
    $("#patPrev", b).innerHTML = `<table><thead><tr><th>${isRename ? "Bisher" : "Datei"}</th><th>${isRename ? "Neu" : "Änderungen"}</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
    $("#patSum", b).textContent = isRename ? `${r.ok} Datei(en) werden umbenannt${r.problems ? `, ${r.problems} mit Problem (bleiben unverändert)` : ""}.`
      : `${r.matched} von ${r.rows.length} passen · ${r.changes} Feldänderung(en).`;
  };
  const res = await modal({
    title: isRename ? `Dateien umbenennen (${idx.length})` : `Tags aus Dateiname (${idx.length})`,
    wide: true,
    html: `<div class="frm"><label for="patIn">Muster</label><input id="patIn" value="${esc(pat)}" spellcheck="false" style="font-family:var(--mono)"></div>
      <div class="chips-ph">${PH.filter((p) => isRename ? p !== "%dummy%" : true).map((p) => `<button data-ph="${p}">${p}</button>`).join("")}</div>
      <div class="hint">${isRename ? "Ungültige Zeichen (\\ / : * ? \" < > |) werden durch _ ersetzt, Spurnummern zweistellig. Die Endung bleibt. Umbenennen geschieht sofort (nicht über „Speichern“)." : "Der Dateiname ohne Endung wird nach dem Muster zerlegt. %dummy% überspringt einen Teil. Änderungen werden erst mit „Speichern“ geschrieben."}</div>
      <div class="fx-table" id="patPrev" style="max-height:46vh"></div><div class="muted sm" id="patSum"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: isRename ? "Umbenennen" : "Übernehmen", value: true, primary: true }],
    onMount: (b) => {
      const inp = $("#patIn", b);
      inp.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => preview(b), 200); });
      b.querySelector(".chips-ph").addEventListener("click", (e) => {
        const p = e.target.dataset.ph; if (!p) return;
        const a = inp.selectionStart ?? inp.value.length;
        inp.setRangeText(p, a, inp.selectionEnd ?? a, "end"); inp.focus(); inp.dispatchEvent(new Event("input"));
      });
      preview(b);
    },
    collect: (b) => $("#patIn", b).value,
  });
  if (res === null) return;
  const d = await call(isRename ? "tag_rename" : "tag_from_filename", idx, res, true);
  TG.settings = await call("tagger_settings");
  if (isRename) { TG.rows = (await call("tag_rows")).rows; tgApplyOrder(); if (S.pairs.length) await refreshAll(); }
  taggerApplyDetail(d);
}

async function tgNumberDialog() {
  const idx = tgSelected();
  const prev = async (b) => {
    const r = await call("tag_number", idx, $("#numTot", b).checked, false);
    $("#numPrev", b).innerHTML = r.rows.length ? `<table><thead><tr><th>Datei</th><th>Bisher</th><th>Neu</th></tr></thead><tbody>${r.rows.map((x) => `<tr><td>${esc(x.name)}</td><td class="old">${esc(x.old) || "–"}</td><td class="new">${esc(x.new)}</td></tr>`).join("")}</tbody></table>` : '<div class="empty">Alle Spurnummern stimmen bereits.</div>';
  };
  const res = await modal({
    title: `Spurnummern vergeben (${idx.length} Dateien)`, wide: true,
    html: `<div class="hint">Nummeriert in der Reihenfolge der Liste (nach einer Spalte sortieren, um die Reihenfolge festzulegen).</div>
      <label class="check"><input type="checkbox" id="numTot" checked> Mit Gesamtzahl (z. B. 3/12)</label>
      <div class="fx-table" id="numPrev" style="max-height:50vh"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => { $("#numTot", b).addEventListener("change", () => prev(b)); prev(b); },
    collect: (b) => ({ tot: $("#numTot", b).checked }),
  });
  if (res) taggerApplyDetail(await call("tag_number", idx, res.tot, true));
}

async function tgAddField() {
  const r = await addFieldForm(null);
  if (!r) return;
  const idx = tgSelected();
  let d = await call("tag_add_field", idx, r.fid, r.desc, r.value, false);
  if (d.ask) {
    const go = await dialog({ title: "Feld existiert schon", text: `„${d.ask.label}“ ist in ${d.ask.count} Datei(en) schon vorhanden. Ersetzen?`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Ersetzen", value: true, primary: true }] });
    if (!go) return;
    d = await call("tag_add_field", idx, r.fid, r.desc, r.value, true);
  }
  if (d.error) { toast(d.error); return; }
  taggerApplyDetail(d);
}

function tgEditMore(row) {
  const key = row.dataset.key, f = TG.detail.fields.find((x) => x.key === key);
  if (!f) return;
  const i = tgSelected()[0];
  if (f.xml) return openXml(null, key, { tag: i });
  if (f.blob) return tgBlobEditor(key);
  if (!f.editable) { toast(key.startsWith("APIC") ? "Bilder über „Cover wählen …“ ändern." : "Dieses Feld kann nicht als Text bearbeitet werden."); return; }
  if (f.multiline || mvDetect(f.edit, key) || isJsonDoc(f.edit) || (COLOR_KEY_RE.test(key) && colorInfo(f.edit))) return tgFieldEditor(key);    // mehrzeilig oder Mehrfachwerte → Editor
  const v = row.querySelector(".v");
  const inp = document.createElement("input");
  inp.value = f.edit;
  v.innerHTML = ""; v.appendChild(inp); inp.focus(); inp.select();
  TG.editing = true;
  let done = false;
  const finish = async (commit) => {
    if (done) return; done = true; TG.editing = false;
    if (commit && inp.value !== f.edit) taggerApplyDetail(await call("tag_set", [i], key, inp.value));
    else renderTgEditor();
  };
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); finish(true); } if (e.key === "Escape") { e.preventDefault(); finish(false); } e.stopPropagation(); });
  inp.addEventListener("blur", () => finish(true));
}

/** URLs in einem Text als anklickbare Links (wie im Vergleich). */
const TG_URL_RE = /(?:https?:\/\/|www\.)[^\s|¦<>"]+/gi;
function linkify(text) {
  let out = "", last = 0;
  for (const m of text.matchAll(TG_URL_RE)) {
    const u = m[0].replace(/[.,;)]+$/, "");
    out += esc(text.slice(last, m.index)) + `<a data-url="${esc(/^www\./i.test(u) ? "https://" + u : u)}" title="${esc(u)} öffnen">${esc(u)}</a>`;
    last = m.index + u.length;
  }
  return out + esc(text.slice(last));
}
function firstUrl(text) {
  const m = (text || "").match(TG_URL_RE);
  if (!m) return null;
  const u = m[0].replace(/[.,;)]+$/, "");
  return /^www\./i.test(u) ? "https://" + u : u;
}

// Mehrfachwerte: NULL-Zeichen (ID3v2.4, im Editor als ¦), Semikolon oder Komma
const MV_SEPS = [["nul", "NULL-Zeichen (ID3v2.4-Mehrfachwert)", " ¦ "], [";", "Semikolon ;", "; "], [",", "Komma ,", ", "]];
function mvDetect(text, key) {
  // mehrzeilige Texte, URL-Felder und Texte mit Links nicht automatisch zerlegen (Umschalten auf „Einzelwerte“ geht immer)
  if (!text || /\n/.test(text) || /^W/.test(key) || firstUrl(text)) return text && text.includes("¦") ? "nul" : null;
  if (text.includes("¦")) return "nul";
  if (text.includes(";")) return ";";
  if (text.includes(",")) return ",";
  return null;
}
function mvSplit(text, sep) {
  const re = sep === "nul" ? /\s*¦\s*/ : sep === ";" ? /\s*;\s*/ : /\s*,\s*/;
  return text.split(re).map((x) => x.trim()).filter((x, i, a) => x || a.length === 1);
}
function mvJoin(items, sep) {
  return items.map((x) => x.trim()).filter(Boolean).join(MV_SEPS.find((x) => x[0] === sep)[2]);
}

/** Editor für ein Feld aus „Weitere Felder“: Text oder Einzelwerte, Blättern zum vorigen/nächsten Feld. */
async function tgFieldEditor(key) {
  const i = tgSelected()[0];
  let f = TG.detail.fields.find((x) => x.key === key);
  if (!f) return;
  if (f.xml) return openXml(null, key, { tag: i });
  if (!f.editable) { toast("Dieses Feld kann nicht als Text bearbeitet werden."); return; }
  const st = { mode: "text", sep: "nul", items: [] };
  const list = () => TG.detail.fields.filter((x) => x.editable && !x.xml);
  const value = (b) => (st.mode === "list" ? mvJoin(st.items, st.sep) : st.mode === "tree" && st.tree ? st.tree.text() : $("#feVal", b).value);

  const renderList = (b, focus) => {
    const box = $("#feList", b);
    box.innerHTML = st.items.map((v, k) => `<div class="fe-item" data-k="${k}"><span class="fe-n">${k + 1}</span>
        <input value="${esc(v)}" data-fe="${k}" spellcheck="false" aria-label="Wert ${k + 1}">
        <button class="x" data-up="${k}" title="Nach oben" ${k ? "" : "disabled"}>↑</button>
        <button class="x" data-down="${k}" title="Nach unten" ${k < st.items.length - 1 ? "" : "disabled"}>↓</button>
        <button class="x del" data-rm="${k}" title="Wert entfernen">✕</button></div>`).join("");
    if (focus !== undefined) box.querySelector(`[data-fe="${focus}"]`)?.focus();
    upd(b);
  };
  const setMode = (b, mode, force) => {
    if (mode === st.mode && !force) return;
    const cur = value(b);                       // aktuellen Stand aus der bisherigen Ansicht holen
    if (st.mode === "tree" && st.tree && !st.tree.valid() && !force) { toast("Erst die rot markierten Zahlen korrigieren."); return; }
    $("#feVal", b).value = cur;
    st.mode = mode;
    if (mode === "list") st.items = mvSplit(cur, st.sep);
    if (mode === "tree") st.tree = jsonTreeEditor($("#feTree", b), cur, () => upd(b), { expert: jsonExpert() });
    $(".jexp", b).hidden = mode !== "tree";
    b.querySelectorAll("[data-fmode]").forEach((x) => x.classList.toggle("on", x.dataset.fmode === mode));
    $("#feTextBox", b).hidden = mode !== "text";
    $("#feListBox", b).hidden = mode !== "list";
    $("#feTreeBox", b).hidden = mode !== "tree";
    $("#feSepWrap", b).hidden = mode === "tree";
    if (mode === "list") renderList(b, 0);
    else { if (mode === "text") $("#feVal", b).focus(); upd(b); }
  };
  const fill = (b) => {
    const l = list(), k = l.findIndex((x) => x.key === f.key);
    $("#feLabel", b).textContent = f.label;
    $("#feKey", b).textContent = f.key;
    const ta = $("#feVal", b);
    ta.value = f.edit;
    ta.rows = Math.min(18, Math.max(f.multiline ? 8 : 3, f.edit.split("\n").length + 1));
    $("#fePrev", b).disabled = k <= 0;
    $("#feNext", b).disabled = k < 0 || k >= l.length - 1;
    $("#fePos", b).textContent = k >= 0 ? `${k + 1} von ${l.length}` : "";
    const json = isJsonDoc(f.edit);
    const sep = json ? null : mvDetect(f.edit, f.key);
    st.sep = sep || "nul";
    $("#feSep", b).value = st.sep;
    $('[data-fmode="tree"]', b).hidden = !json;
    st.mode = "text"; st.tree = null;
    setMode(b, json ? "tree" : sep ? "list" : "text", true);
    upd(b);
  };
  const syncFeColor = (b) => {
    const c = COLOR_KEY_RE.test(f.key) && st.mode === "text" ? colorInfo($("#feVal", b).value) : null;
    $("#feColor", b).hidden = !c;
    if (c) { $("#feColorPick", b).value = c.hex; $("#feColorTxt", b).textContent = `Farbe ${c.hex.toUpperCase()} – Schreibweise bleibt (${c.raw})`; }
  };
  const upd = (b) => {
    syncFeColor(b);
    const v = value(b);
    const n = st.mode === "list" ? st.items.filter((x) => x.trim()).length : 0;
    $("#feInfo", b).textContent = st.mode === "tree"
      ? `JSON · nur Werte bearbeitbar${st.tree && !st.tree.valid() ? " · ungültige Zahl" : ""}${v !== f.edit ? " · geändert" : ""}`
      : st.mode === "list"
      ? `${n} Wert(e)${v !== f.edit ? " · geändert" : ""}`
      : `${v.length} Zeichen · ${v ? v.split("\n").length : 0} Zeile(n)${v !== f.edit ? " · geändert" : ""}`;
  };
  // Wert übernehmen, ohne den Dialog zu schliessen (beim Blättern)
  const save = async (b) => {
    const v = value(b);
    if (v !== f.edit) taggerApplyDetail(await call("tag_set", [i], f.key, v));
  };
  const go = async (b, dir) => {
    await save(b);
    const l = list(), k = l.findIndex((x) => x.key === f.key);
    const nx = l[k + dir] || l[k];
    if (!nx) return;
    f = nx;
    fill(b);
  };
  const res = await modal({
    title: "Feld bearbeiten", wide: true,
    html: `<div class="fe-head"><div><b id="feLabel"></b> <code id="feKey" class="muted sm"></code></div>
        <div class="fe-nav"><button class="ghost sm" id="fePrev" title="Voriges Feld (Alt+↑)">‹</button><span class="muted sm" id="fePos"></span><button class="ghost sm" id="feNext" title="Nächstes Feld (Alt+↓)">›</button></div></div>
      <div class="fe-modes"><div class="seg"><button data-fmode="tree" hidden>Baum</button><button data-fmode="text">Text</button><button data-fmode="list">Einzelwerte</button></div>
        ${EXPERT_HTML}<label class="muted sm" id="feSepWrap">Trennung <select id="feSep" class="inp sm">${MV_SEPS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></label></div>
      <div id="feTreeBox" hidden><div id="feTree" class="xml-tree fe-tree"></div></div>
      <div id="feTextBox"><div class="fe-color" id="feColor" hidden><input type="color" id="feColorPick" title="Farbe wählen"><span class="muted sm" id="feColorTxt"></span></div>
        <textarea id="feVal" class="fe-val" spellcheck="false"></textarea></div>
      <div id="feListBox" hidden><div id="feList" class="fe-list" data-keep-enter></div><button class="ghost sm" id="feAdd">+ Wert hinzufügen</button></div>
      <div class="fe-foot"><span class="hint">Leer = Feld entfernen. NULL-getrennte Mehrfachwerte gibt es nur in ID3v2.4 (beim Speichern als v2.3 werden sie mit „ / “ verbunden). <kbd>Strg</kbd>/<kbd>⌘</kbd>+<kbd>Enter</kbd> übernimmt.</span><span class="muted sm" id="feInfo"></span></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Feld entfernen", value: "del" }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => {
      const ta = $("#feVal", b);
      ta.addEventListener("input", () => upd(b));
      $("#feColorPick", b).addEventListener("input", (e) => {
        const c = colorInfo(ta.value);
        if (c) { ta.value = colorFormat(c, e.target.value); upd(b); }
      });
      const ecb = $(".jexp-cb", b);
      ecb.checked = jsonExpert();
      ecb.addEventListener("change", () => {
        if (st.tree && !st.tree.setExpert(ecb.checked)) { ecb.checked = !ecb.checked; toast("Erst die rot markierten Zahlen korrigieren."); return; }
        jsonExpert(ecb.checked);
      });
      b.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); e.stopPropagation(); $("#mBtns .primary").click(); return; }
        if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); go(b, e.key === "ArrowUp" ? -1 : 1); return; }
        const inp = e.target.closest("[data-fe]");
        if (inp && e.key === "Enter") {            // Enter in einem Wert: neuer Wert darunter (statt Dialog schliessen)
          e.preventDefault(); e.stopPropagation();
          const k = +inp.dataset.fe;
          st.items.splice(k + 1, 0, "");
          renderList(b, k + 1);
        }
        if (inp && e.key === "Backspace" && !inp.value && st.items.length > 1) {
          e.preventDefault(); const k = +inp.dataset.fe; st.items.splice(k, 1); renderList(b, Math.max(0, k - 1));
        }
      }, true);
      b.addEventListener("input", (e) => { const inp = e.target.closest("[data-fe]"); if (inp) { st.items[+inp.dataset.fe] = inp.value; upd(b); } });
      b.addEventListener("click", (e) => {
        const t = e.target.closest("button"); if (!t) return;
        if (t.dataset.fmode) setMode(b, t.dataset.fmode);
        else if (t.id === "feAdd") { st.items.push(""); renderList(b, st.items.length - 1); }
        else if (t.dataset.rm !== undefined) { st.items.splice(+t.dataset.rm, 1); if (!st.items.length) st.items.push(""); renderList(b); }
        else if (t.dataset.up !== undefined) { const k = +t.dataset.up; [st.items[k - 1], st.items[k]] = [st.items[k], st.items[k - 1]]; renderList(b, k - 1); }
        else if (t.dataset.down !== undefined) { const k = +t.dataset.down; [st.items[k + 1], st.items[k]] = [st.items[k], st.items[k + 1]]; renderList(b, k + 1); }
      });
      $("#feSep", b).addEventListener("change", (e) => {
        if (st.mode === "text") { const items = mvSplit(ta.value, st.sep); st.sep = e.target.value; ta.value = mvJoin(items, st.sep); }
        else st.sep = e.target.value;
        upd(b);
      });
      $("#fePrev", b).onclick = () => go(b, -1);
      $("#feNext", b).onclick = () => go(b, 1);
      fill(b);
    },
    collect: (b, v) => ({ action: v, key: f.key, value: value(b), before: f.edit }),
  });
  if (!res) return;
  if (res.action === "del") taggerApplyDetail(await call("tag_remove", [i], [res.key]));
  else if (res.value !== res.before) taggerApplyDetail(await call("tag_set", [i], res.key, res.value));
}

/** Expertenmodus für den JSON-Baum (pro Browser gemerkt). */
function jsonExpert(v) {
  try { if (v !== undefined) localStorage.setItem("ts_json_expert", v ? "1" : ""); return !!localStorage.getItem("ts_json_expert"); }
  catch (e) { if (v !== undefined) jsonExpert._v = !!v; return !!jsonExpert._v; }
}
const EXPERT_HTML = `<label class="check jexp" title="Expertenmodus: Einträge hinzufügen, duplizieren und entfernen (z. B. neue Cue-Punkte)"><input type="checkbox" class="jexp-cb"> Expertenmodus</label>`;

/** Binärfeld-Editor (GEOB/PRIV): Kopf (MIME, Dateiname) und – wenn lesbar – Inhalt als Text; sonst Hex-Ansicht. */
async function tgBlobEditor(key) {
  const i = tgSelected()[0];
  const r = await call("tag_blob", i, key);
  if (!r.ok) { toast(r.error); return; }
  const geob = r.fid === "GEOB";
  const head = geob
    ? `<label>Beschreibung</label><div class="ro">${esc(r.desc) || '<span class="muted">(leer)</span>'}</div>
       <label for="bfMime">MIME-Typ</label><input id="bfMime" value="${esc(r.mime)}" spellcheck="false">
       <label for="bfName">Dateiname</label><input id="bfName" value="${esc(r.filename)}" spellcheck="false">`
    : `<label>Besitzer</label><div class="ro">${esc(r.owner) || '<span class="muted">(leer)</span>'}</div>`;
  const json = r.editable && r.inner === "json" && isJsonDoc(r.text);
  const body = r.editable
    ? `${json ? `<div class="fe-modes"><div class="seg"><button data-bmode="tree" class="on">Baum</button><button data-bmode="text">Text</button></div>
        <span class="bf-tools">${EXPERT_HTML}<button class="ghost sm" id="bfOpenAll">Alle aufklappen</button><button class="ghost sm" id="bfCloseAll">Alle zuklappen</button></span></div>
        <div id="bfTree" class="xml-tree fe-tree"></div>` : ""}
      <textarea id="bfText" class="fe-val bf-text" spellcheck="false" rows="14" ${json ? "hidden" : ""}>${esc(r.text)}</textarea>`
    : `<pre class="bf-hex">${esc(r.hex)}</pre>`;
  const tools = [
    r.kind === "xml" ? '<button class="ghost sm" id="bfXml">Im XML-Editor öffnen</button>' : "",
    r.editable && r.inner === "json" ? `<button class="ghost sm" id="bfJson" ${json ? "hidden" : ""}>JSON formatieren</button>` : "",
  ].join("");
  const res = await modal({
    title: `${r.label} – ${r.file}`, wide: true,
    html: `<div class="frm bf-head">${head}</div>
      <div class="bf-info"><span class="chip">${esc(r.fid)}</span><span>${esc(r.kind_label)}${r.codec ? " · " + esc(r.codec) : ""} · ${fmtN(r.size)} Bytes</span>
        <span class="bf-tools">${tools}</span></div>
      ${r.note ? `<div class="hint">${esc(r.note)}</div>` : ""}
      ${body}
      <div class="hint">${r.editable
        ? (r.kind === "base64" ? "Bearbeitet wird der entschlüsselte Text; beim Übernehmen wird er wieder Base64-kodiert." : "Beim Übernehmen wird nur dieser Inhalt ersetzt, alle übrigen Bytes bleiben erhalten.")
        : "Unbekanntes Binärformat – nur ansehen. MIME-Typ und Dateiname lassen sich trotzdem ändern."}
        Programme, die das Feld geschrieben haben (z. B. Serato, Mixed In Key), erwarten ihr eigenes Format – Änderungen auf eigene Gefahr.</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Feld entfernen", value: "del" }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => {
      const bs = { mode: json ? "tree" : "text", tree: null };
      const text = () => (bs.mode === "tree" && bs.tree ? bs.tree.text() : $("#bfText", b).value);
      b._bfText = text; b._bfState = bs;
      if (json) bs.tree = jsonTreeEditor($("#bfTree", b), r.text, () => {}, { expert: jsonExpert() });
      const ecb = $(".jexp-cb", b);
      if (ecb) {
        ecb.checked = jsonExpert();
        ecb.addEventListener("change", () => { if (bs.tree && !bs.tree.setExpert(ecb.checked)) { ecb.checked = !ecb.checked; toast("Erst die rot markierten Zahlen korrigieren."); return; } jsonExpert(ecb.checked); });
      }
      b.querySelectorAll("[data-bmode]").forEach((btn) => btn.addEventListener("click", () => {
        const m = btn.dataset.bmode;
        if (m === bs.mode) return;
        if (bs.mode === "tree" && !bs.tree.valid()) { toast("Erst die rot markierten Zahlen korrigieren."); return; }
        const cur = text();
        bs.mode = m;
        $("#bfText", b).value = cur;
        if (m === "tree") bs.tree = jsonTreeEditor($("#bfTree", b), cur, () => {}, { expert: jsonExpert() });
        b.querySelectorAll("[data-bmode]").forEach((x) => x.classList.toggle("on", x.dataset.bmode === m));
        $("#bfTree", b).hidden = m !== "tree";
        $("#bfText", b).hidden = m !== "text";
        $("#bfJson", b).hidden = m !== "text";
        $("#bfOpenAll", b).hidden = $("#bfCloseAll", b).hidden = m !== "tree";
        $(".jexp", b).hidden = m !== "tree";
      }));
      $("#bfOpenAll", b)?.addEventListener("click", () => bs.tree && bs.tree.expandAll(true));
      $("#bfCloseAll", b)?.addEventListener("click", () => bs.tree && bs.tree.expandAll(false));
      $("#bfXml", b)?.addEventListener("click", () => { $("#mBtns .ghost").click(); setTimeout(() => openXml(null, key, { tag: i }), 50); });
      $("#bfJson", b)?.addEventListener("click", async () => {
        const p = await call("blob_pretty", $("#bfText", b).value, "json");
        if (p.ok) $("#bfText", b).value = p.text; else toast(p.error);
      });
    },
    collect: (b, v) => {
      if (v === true && b._bfState.mode === "tree" && b._bfState.tree && !b._bfState.tree.valid()) { toast("Erst die rot markierten Zahlen korrigieren."); return false; }
      return { action: v, text: r.editable ? b._bfText() : null,
      mime: geob ? $("#bfMime", b).value : null, filename: geob ? $("#bfName", b).value : null };
    },
  });
  if (!res) return;
  if (res.action === "del") { taggerApplyDetail(await call("tag_remove", [i], [key])); return; }
  try {
    taggerApplyDetail(await call("tag_blob_set", i, key, res.text, res.mime, res.filename));
  } catch (e) { await info("Nicht übernommen", String(e.message || e)); }
}

// ---------------------------------------------------------------------- Werkzeuge mit Vorschau
/** Felder-Auswahl: „Alle Textfelder“ oder einzelne Standardfelder */
function fieldsPicker(defaults, allDefault = false) {
  return `<label class="check"><input type="checkbox" class="fp-all" ${allDefault ? "checked" : ""}> Alle Textfelder (auch Benutzertexte, Kommentare …)</label>
    <div class="checklist fp-list">${TG.settings.fields.map(([k, l]) => `<label><input type="checkbox" data-fk="${k}" ${defaults.includes(k) ? "checked" : ""}> ${esc(l)}</label>`).join("")}</div>`;
}
function pickedFields(b) {
  if ($(".fp-all", b).checked) return null;
  return $$("input[data-fk]:checked", b).map((c) => c.dataset.fk);
}
function bindFieldsPicker(b) {
  const sync = () => { const all = $(".fp-all", b).checked; $$("input[data-fk]", b).forEach((c) => (c.disabled = all)); $(".fp-list", b).style.opacity = all ? 0.45 : 1; };
  $(".fp-all", b).addEventListener("change", sync);
  sync();
}

/** Vorschau-Dialog: preview(body) liefert {rows, count, error}; Spalten [Titel, Feld]; apply(body) führt aus. */
async function toolDialog({ title, form, columns, preview, apply, applyLabel = "Übernehmen", onMount }) {
  let timer = null, last = null, open = true, body = null;
  const again = () => { clearTimeout(timer); timer = setTimeout(() => run(body), 220); };
  const run = async (b) => {
    if (!open || !$("#tdPrev", b)) return;
    const r = await preview(b);
    if (!open || !$("#tdPrev", b)) return;
    last = r;
    const err = r.error ? `<div class="empty st-missing">${esc(r.error)}</div>` : "";
    $("#tdPrev", b).innerHTML = err || (r.rows.length
      ? `<table><thead><tr>${columns.map(([t]) => `<th>${esc(t)}</th>`).join("")}</tr></thead><tbody>${r.rows.map((x) => `<tr>${columns.map(([, f, cls]) => `<td class="${typeof cls === "function" ? cls(x) : cls || ""}">${esc(x[f])}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      : '<div class="empty">Keine Änderungen.</div>');
    $("#tdSum", b).textContent = r.error ? "" : r.summary || `${fmtN(r.count)} Änderung(en)${r.files !== undefined ? ` in ${fmtN(r.files)} Datei(en)` : ""}.`;
    const btn = $("#mBtns .primary");
    if (btn) { btn.disabled = !!r.error || !r.count; btn.textContent = r.count ? `${applyLabel} (${fmtN(r.count)})` : applyLabel; }
  };
  const res = await modal({
    title, wide: true,
    html: `${form}<div class="fx-table" id="tdPrev" style="max-height:42vh"></div><div class="muted sm" id="tdSum"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: applyLabel, value: true, primary: true }],
    onMount: (b) => {
      body = b;
      if (onMount) onMount(b);
      b.addEventListener("input", again);
      b.addEventListener("change", again);
      run(b);
    },
    collect: (b) => (last && last.count && !last.error ? b : false),
  });
  open = false; clearTimeout(timer);
  body.removeEventListener("input", again);
  body.removeEventListener("change", again);
  if (res) taggerApplyDetail(await apply(res));
}

const CHG_COLS = [["Datei", "name"], ["Feld", "label"], ["Vorher", "old", "old"], ["Nachher", "new", "new"]];

async function tgCaseDialog() {
  const idx = tgSelected();
  TG.caseModes = TG.caseModes || (await call("tag_case_modes"));
  await toolDialog({
    title: `Groß-/Kleinschreibung (${idx.length} Datei(en))`,
    form: `<div class="radios" style="flex-wrap:wrap">${TG.caseModes.map(([k, l], n) => `<label><input type="radio" name="cm" value="${k}" ${n === 0 ? "checked" : ""}> ${esc(l)}</label>`).join("")}</div>
      <div class="quick"><label class="check"><input type="checkbox" id="cmKeep" checked> Abkürzungen in GROSSBUCHSTABEN behalten (DJ, AC/DC, II)</label>
      <label class="check"><input type="checkbox" id="cmSmall"> Kleine Wörter klein (and, of, the, feat., und, von …)</label></div>
      ${fieldsPicker(["TIT2", "TPE1", "TALB", "TPE2"])}`,
    columns: CHG_COLS,
    onMount: bindFieldsPicker,
    preview: (b) => call("tag_case", idx, pickedFields(b), b.querySelector('input[name="cm"]:checked').value, $("#cmKeep", b).checked, $("#cmSmall", b).checked, false),
    apply: (b) => call("tag_case", idx, pickedFields(b), b.querySelector('input[name="cm"]:checked').value, $("#cmKeep", b).checked, $("#cmSmall", b).checked, true),
  });
}

async function tgReplaceDialog() {
  const idx = tgSelected();
  const args = (b, apply) => [idx, pickedFields(b), $("#rpFind", b).value, $("#rpRepl", b).value, $("#rpCase", b).checked, $("#rpRegex", b).checked, $("#rpWord", b).checked, apply];
  await toolDialog({
    title: `Suchen & Ersetzen (${idx.length} Datei(en))`,
    form: `<div class="frm"><label for="rpFind">Suchen</label><input id="rpFind" autofocus spellcheck="false">
      <label for="rpRepl">Ersetzen durch</label><input id="rpRepl" spellcheck="false" placeholder="leer = entfernen"></div>
      <div class="quick"><label class="check"><input type="checkbox" id="rpCase"> Groß-/Kleinschreibung beachten</label>
      <label class="check"><input type="checkbox" id="rpWord"> Nur ganze Wörter</label>
      <label class="check"><input type="checkbox" id="rpRegex"> Regulärer Ausdruck (\\1 im Ersatz)</label></div>
      ${fieldsPicker(["TIT2", "TPE1", "TALB", "TPE2", "TCON", "TCOM"], true)}`,
    columns: CHG_COLS,
    applyLabel: "Ersetzen",
    onMount: bindFieldsPicker,
    preview: (b) => (b.querySelector("#rpFind").value ? call("tag_replace", ...args(b, false)) : Promise.resolve({ rows: [], count: 0, summary: "Suchbegriff eingeben." })),
    apply: (b) => call("tag_replace", ...args(b, true)),
  });
}

async function tgFolderCoverDialog() {
  const idx = tgSelected();
  await toolDialog({
    title: `Cover aus Bild im Ordner (${idx.length} Datei(en))`,
    form: `<div class="hint">Gesucht wird pro Ordner nach cover / folder / front / album (.jpg, .png, .gif), sonst wird das größte Bild genommen.</div>
      <label class="check"><input type="checkbox" id="fcMissing" checked> Nur Dateien ohne Cover</label>`,
    columns: [["Datei", "name"], ["Bild", "image"], ["Aktion", "reason", (x) => (x.action === "set" ? "new" : "old")]],
    preview: async (b) => { const r = await call("tag_folder_cover", idx, $("#fcMissing", b).checked, false); r.summary = `${fmtN(r.count)} von ${fmtN(r.rows.length)} Datei(en) bekommen ein Cover.`; return r; },
    apply: (b) => call("tag_folder_cover", idx, $("#fcMissing", b).checked, true),
  });
}

async function tgExportDialog() {
  const idx = tgSelected();
  const res = await modal({
    title: "Liste exportieren",
    html: `<div class="frm"><label>Dateien</label><div class="radios"><label><input type="radio" name="ex-s" value="sel" ${idx.length > 1 ? "checked" : ""}> Markierte (${idx.length})</label><label><input type="radio" name="ex-s" value="all" ${idx.length > 1 ? "" : "checked"}> Alle (${fmtN(TG.rows.length)})</label></div>
      <label>Format</label><div class="radios"><label><input type="radio" name="ex-f" value="xlsx" checked> Excel (.xlsx)</label><label><input type="radio" name="ex-f" value="csv"> CSV (Semikolon, für Excel)</label></div></div>
      <div class="hint">Spalten: Datei, Ordner, alle Standardfelder, Dauer, Bitrate, ID3-Version, Cover ja/nein, Größe.</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern unter …", value: true, primary: true }],
    collect: (b) => ({ sel: b.querySelector('input[name="ex-s"]:checked').value === "sel", fmt: b.querySelector('input[name="ex-f"]:checked').value }),
  });
  if (!res) return;
  const r = await call("tag_export", res.sel ? idx : [], res.fmt);
  if (r.ok) status(`${fmtN(r.count)} Datei(en) exportiert: ${r.path}`, "ok");
  else if (!r.cancelled) toast(r.error || "Export fehlgeschlagen.");
  else if (!S.settings.native) toast("Im Browser-Modus ist kein Speichern-Dialog verfügbar – bitte das App-Fenster verwenden.");
}

async function tgStemTagsDialog() {
  const idx = tgSelected();
  const pv = await call("tag_stem_tags", idx, false);
  if (!pv.stems) return toast("Keine MP3-Stems zu den markierten Titeln (FLAC/WAV haben keine ID3-Tags).");
  const ok = await dialog({
    title: "Tags vom Original übernehmen",
    text: `Alle Felder (ausser DJ-Analysen wie Serato-/Traktor-Daten) von ${pv.originals} Original(en) auf ${pv.stems} MP3-Stem(s) übertragen; der Titel bekommt die Spur in Klammern, z. B. „Titel (Vocals)“. Rückgängig ist möglich.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übertragen", value: true, primary: true }],
  });
  if (!ok) return;
  const d = await call("tag_stem_tags", idx, true);
  taggerApplyDetail(d);
}

/** Nach einem fertigen Stems-Auftrag: neue Spuren ohne neues Einlesen anhängen und aufklappen. */
async function jobFinishedHook(j) {
  if (j.plugin !== "stems" || !TG.loaded) return;
  const r = await call("tag_attach_stems");
  TG.rows = r.rows;
  r.new.forEach((i) => TG.open.add(i));
  tgApplyOrder();
  if (r.new.length) status(`${r.new.length} Titel mit neuen Stems – unter dem Original aufgeklappt.`, "ok");
}

/** Alle Felder einer Herkunft (z. B. Serato, iTunes) aus den markierten Dateien entfernen – mit Vorschau. */
async function tgOriginDialog(preset = "") {
  const idx = tgSelected();
  if (!idx.length) return toast("Erst Dateien markieren.");
  const cat = S.settings.origins || {};
  const ids = Object.keys(cat).filter((k) => cat[k].kind !== "id3").sort((a, b) => cat[a].name.localeCompare(cat[b].name));
  const res = await modal({
    title: "Felder nach Herkunft entfernen", wide: true,
    html: `<div class="frm"><label for="orSrc">Herkunft</label><select id="orSrc" class="inp">${ids.map((k) => `<option value="${esc(k)}"${k === preset ? " selected" : ""}>${esc(cat[k].name)}</option>`).join("")}</select></div>
      <div class="hint" id="orDesc" style="margin:6px 0 10px"></div><div id="orPrev"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Entfernen", value: true, primary: true }],
    onMount: (b) => {
      const upd = async () => {
        const sid = $("#orSrc", b).value;
        $("#orDesc", b).textContent = cat[sid] ? cat[sid].desc + " – " + idx.length + " markierte Datei(en)." : "";
        const p = await call("tag_origin_remove", idx, sid, false);
        $("#orPrev", b).innerHTML = p.count
          ? `<div class="fx-table pl-prev"><table><thead><tr><th>Feld</th><th>Schlüssel</th><th style="text-align:right">Dateien</th></tr></thead><tbody>${p.keys.map(([k, l, n]) => `<tr><td>${esc(l)}</td><td><code>${esc(k)}</code></td><td style="text-align:right">${n}</td></tr>`).join("")}</tbody></table></div><div class="muted sm" style="margin-top:6px">${p.count} Feld(er) in ${p.files} Datei(en) – Rückgängig ist möglich, gespeichert wird erst mit „Speichern“.</div>`
          : '<div class="muted">Keine Felder dieser Herkunft in den markierten Dateien.</div>';
        b.dataset.count = p.count;
      };
      $("#orSrc", b).addEventListener("change", upd); upd();
    },
    collect: (b) => (+b.dataset.count ? $("#orSrc", b).value : (toast("Nichts zu entfernen."), false)),
  });
  if (!res) return;
  const d = await call("tag_origin_remove", idx, res, true);
  taggerApplyDetail(d);
  if (typeof taggerRefresh === "function") await taggerRefresh();
  status(d.message, "ok");
}

// ---------------------------------------------------------------------- Ereignisse
(function bindTagger() {
  $("#tgLoad").addEventListener("click", taggerLoad);
  $("#tgPath").addEventListener("keydown", (e) => { if (e.key === "Enter") taggerLoad(); });
  $$("[data-tgpick]").forEach((b) => b.addEventListener("click", async () => {
    const p = await call("pick_path", "T", b.dataset.tgpick === "1", $("#tgPath").value.trim());
    if (p) { $("#tgPath").value = p; taggerLoad(); } else if (!S.settings.native) toast("Pfad bitte direkt ins Feld eintippen oder einfügen.");
  }));
  let qt = null;
  $("#tgQuery").addEventListener("input", () => { clearTimeout(qt); qt = setTimeout(tgApplyOrder, 150); });
  $("#tgHead").addEventListener("click", (e) => {
    const b = e.target.closest("[data-sort]"); if (!b) return;
    TG.sort = { col: b.dataset.sort, dir: TG.sort.col === b.dataset.sort ? -TG.sort.dir : 1 };
    renderTgHead(); tgApplyOrder();
  });
  $("#tgScroll").addEventListener("scroll", () => requestAnimationFrame(drawTgList));
  $("#tgInner").addEventListener("click", (e) => {
    const tw = e.target.closest("[data-tw]");
    if (tw) { e.stopPropagation(); tgToggleStems(+tw.dataset.tw); return; }
    const sx = e.target.closest(".stem-x");
    if (sx) {
      if (e.target.closest("[data-splay]")) plLoad({ kind: "stem", ref: sx.dataset.stem });
      else if (e.target.closest("[data-sreveal]")) call("reveal", sx.dataset.stem);
      return;
    }
    const r = e.target.closest(".tg-row");
    if (!r) return;
    // #92: Doppelklick spielt den Titel (über e.detail – die Zeile wird beim ersten Klick neu gezeichnet)
    const dbl = e.detail === 2 && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.target.closest("button");
    tgSelect(+r.dataset.i, e).then(() => { if (dbl && typeof plPlayRow === "function") plPlayRow(); });
  });
  $("#tgCoverCol").addEventListener("click", () => { LAYOUT.tg_cover_col = !LAYOUT.tg_cover_col; saveUi("tg_cover_col"); renderTgHead(); drawTgList(); });
  $("#tgFeatCols").addEventListener("click", (e) => { e.stopPropagation(); tgFeatMenu(e.currentTarget); });
  $("#tgInner").addEventListener("mouseover", tgCoverPop);
  $("#tgInner").addEventListener("mouseout", tgCoverPop);
  $("#tgStemOpen").addEventListener("click", () => { TG.rows.forEach((r) => { if (r.stems) TG.open.add(r.i); }); tgApplyOrder(); });
  $("#tgStemClose").addEventListener("click", () => { [...TG.open].forEach((i) => tgToggleStems(i, false)); });
  $("#tgTable").addEventListener("keydown", (e) => {
    if (!TG.order.length) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") { e.preventDefault(); e.stopPropagation(); TG.sel = new Set(TG.order); tgApplyOrder(); tgLoadDetail(); return; }
    if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && !e.shiftKey && TG.anchor !== null) {   // Stems auf-/zuklappen
      const r = TG.rows[TG.anchor], p = r && (r.stems ? r.i : r.parent);
      if (p !== undefined && TG.rows[p].stems) {
        e.preventDefault();
        if (e.key === "ArrowLeft" && r.parent !== undefined) { tgSelect(p, {}); tgToggleStems(p, false); tgScrollTo(p); }
        else tgToggleStems(p, e.key === "ArrowRight");
      }
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const k = Math.max(0, Math.min(TG.order.length - 1, TG.order.indexOf(TG.anchor) + (e.key === "ArrowDown" ? 1 : -1)));
    const i = TG.order[k];
    tgSelect(i, { shiftKey: e.shiftKey });
    if (!e.shiftKey) TG.anchor = i;
    tgScrollTo(i);
  });
  const ed = $("#tgEdit");
  ed.addEventListener("keydown", (e) => {
    const inp = e.target.closest(".tg-form input[data-key]");
    if (!inp) return;
    if (e.key === "Enter") { e.preventDefault(); tgCommit(inp); }
    if (e.key === "Escape") { e.preventDefault(); const v = TG.detail.common[inp.dataset.key]; inp.value = v.value; }
  });
  ed.addEventListener("focusout", (e) => { const inp = e.target.closest(".tg-form input[data-key]"); if (inp) tgCommit(inp); });
  ed.addEventListener("change", async (e) => {
    if (e.target.id === "tgVer" && e.target.value) taggerApplyDetail(await call("tag_version", tgSelected(), +e.target.value));
    else if (e.target.id === "tgSrcF") { TG.srcFilter = e.target.value; renderTgEditor(); }
  });
  ed.addEventListener("click", async (e) => {
    const rb = e.target.closest(".tg-rate button");
    if (rb) { if (rb.dataset.star) tgMark(+rb.dataset.star, null); else tgMark(null, "toggle"); return; }
    const a = e.target.closest("a[data-url]");
    if (a) { e.preventDefault(); call("open_url", a.dataset.url); return; }
    const id = e.target.closest("button")?.id;
    const idx = tgSelected();
    if (id === "tgCoverSet") { const d = await call("tag_cover_file", idx, ""); if (d) taggerApplyDetail(d); else if (!S.settings.native) toast("Im Browser-Modus ist kein Dateidialog verfügbar – bitte das App-Fenster verwenden."); }
    else if (id === "tgCoverDel") taggerApplyDetail(await call("tag_cover", idx, null, true));
    else if (id === "tgCoverBig") {
      const c = TG.detail.cover;
      if (c.state === "same" && c.src) { $("#coverImg").src = c.src; $("#coverCap").textContent = c.desc; $("#coverView").hidden = false; }
    }
    else if (id === "tgFromName") tgPatternDialog("from");
    else if (id === "tgRename") tgPatternDialog("rename");
    else if (id === "tgNumber") tgNumberDialog();
    else if (id === "tgAddField") tgAddField();
    else if (id === "tgFixer") setModule("fixer", { scope: "tag_sel" });
    else if (id === "tgReveal") call("reveal", TG.detail.file.path);
    else if (id === "tgCase") tgCaseDialog();
    else if (id === "tgReplace") tgReplaceDialog();
    else if (id === "tgFolderCover") tgFolderCoverDialog();
    else if (id === "tgExport") tgExportDialog();
    else if (id === "tgOrigin") tgOriginDialog();
    else if (id === "tgStemTags") tgStemTagsDialog();
    else if (id === "tgSrcDel") tgOriginDialog(e.target.closest("button").dataset.src);
    else if (id === "tgKeyBtn") keyWheelOpen();
    const pb = e.target.closest("[data-plugin]");
    if (pb) pluginRun(pb.dataset.plugin, pb.dataset.action);
    const sf = e.target.closest("[data-srcf]");                 // #50: Klick auf Kennzeichen filtert
    if (sf) { TG.srcFilter = TG.srcFilter === sf.dataset.srcf ? "" : sf.dataset.srcf; renderTgEditor(); return; }
    const row = e.target.closest(".tg-f");
    if (row && e.target.closest("[data-tdel]")) taggerApplyDetail(await call("tag_remove", [idx[0]], [row.dataset.key]));
    else if (row && e.target.closest("[data-txml]")) openXml(null, row.dataset.key, { tag: idx[0] });
    else if (row && e.target.closest("[data-tedit]")) {
      const fd = TG.detail.fields.find((x) => x.key === row.dataset.key);
      if (fd && fd.blob) tgBlobEditor(row.dataset.key); else tgFieldEditor(row.dataset.key);
    }
  });
  ed.addEventListener("dblclick", (e) => { const row = e.target.closest(".tg-f"); if (row && !e.target.closest("button")) tgEditMore(row); });
  // Splitter zwischen Liste und Bearbeitungsbereich
  const setW = (w) => { LAYOUT.tg_edit_w = clamp(Math.round(w), 340, Math.max(360, innerWidth * 0.6)); document.documentElement.style.setProperty("--tg-edit-w", LAYOUT.tg_edit_w + "px"); };
  draggable($("#tgSplit"), {
    onStart: () => ({ w: $("#tgEdit").getBoundingClientRect().width }),
    onMove: (dx, st) => setW(st.w - dx),
    onEnd: () => saveUi("tg_edit_w"),
    onDouble: () => { setW(430); saveUi("tg_edit_w"); },
    onKey: (d) => { setW((LAYOUT.tg_edit_w || 430) - d); saveUi("tg_edit_w"); },
  });
})();
