/* MarKusSXCH TagStudio – Seite „Käufe“ (#285): gekaufte Titel aller Stores, Abgleich mit der Bibliothek, Download.
   Speicher und Abgleich in purchases.py / session_purchases.py, Stores als Plugins (store_purchases, store_download). */
"use strict";

const PUR = { st: null, q: "", store: "", status: "", sel: new Set(), sort: { k: "bought", desc: true } };
const PUR_STATUS = { library: "in Bibliothek", inbox: "im Eingang", unclear: "unklar", missing: "fehlt" };
const PUR_COLS = [["status", "Status"], ["title", "Titel"], ["artist", "Interpret"], ["mix", "Mix"], ["dur", "Länge"],
  ["key", "Tonart"], ["bpm", "BPM"], ["catalog", "Katalognr."], ["store", "Store"], ["bought", "Kaufdatum"]];

async function purchasesShow() {
  try { purApply(await call("purch_state")); } catch (e) { toast(String(e.message || e)); }
}

function purApply(st) {
  if (!st) return;
  PUR.st = st;
  const keys = new Set(st.rows.map((r) => r.k));
  PUR.sel = new Set([...PUR.sel].filter((k) => keys.has(k)));
  purSideCount();
  if (S.module !== "purchases") return;
  purRenderBar();
  purRenderTable();
}

function purSideCount() {
  const el = $("#purCount"); if (!el || !PUR.st) return;
  const n = PUR.st.count.missing || 0;
  el.textContent = n ? String(n) : "";
  el.title = n ? `${n} gekaufte Titel fehlen in der Bibliothek` : "";
}

function purStoreName(id) {
  const s = PUR.st.stores[id] || PUR.st.sources.find((x) => x.id === id);
  return s ? s.name : id;
}

function purRenderBar() {
  const st = PUR.st;
  const ids = [...new Set([...Object.keys(st.stores), ...st.sources.map((s) => s.id)])];
  $("#purStore").innerHTML = `<option value="">Alle Stores</option>` + ids.map((id) => `<option value="${esc(id)}"${id === PUR.store ? " selected" : ""}>${esc(purStoreName(id))}</option>`).join("");
  const all = st.rows.length;
  $("#purStatus").innerHTML = [["", `Alle (${fmtN(all)})`], ...Object.entries(PUR_STATUS).map(([k, l]) => [k, `${l} (${fmtN(st.count[k] || 0)})`])]
    .map(([k, l]) => `<button data-purst="${k}" class="${PUR.status === k ? "on" : ""}">${esc(l)}</button>`).join("");
  $("#purDest").innerHTML = st.dest ? `Ziel: <span translate="no" title="${esc(st.dest_from)}">${esc(st.dest)}</span>${st.dest_ok ? "" : " (wird angelegt)"}` : "Kein Eingangsordner";
  const sel = PUR.sel.size, miss = st.rows.filter((r) => r.status === "missing" && !r.preorder).length;
  const b = $("#purDl");
  b.textContent = sel ? `Markierte herunterladen (${fmtN(sel)})` : `Fehlende herunterladen (${fmtN(miss)})`;
  b.disabled = !(sel || miss) || !st.dest;
}

function purVisible() {
  const q = PUR.q.trim().toLowerCase();
  const rows = PUR.st.rows.filter((r) => (!PUR.store || r.store === PUR.store) && (!PUR.status || r.status === PUR.status)
    && (!q || [r.title, r.artist, r.mix, r.catalog, r.label, r.release, r.isrc].join(" ").toLowerCase().includes(q)));
  const { k, desc } = PUR.sort;
  const val = (r) => k === "key" ? (r.key ? (parseInt(r.key, 10) * 2 - (r.key.endsWith("A") ? 1 : 0)) : null)
    : k === "bought" ? (r.bought || (r.seen ? new Date(r.seen * 1000).toISOString() : ""))
    : k === "status" ? Object.keys(PUR_STATUS).indexOf(r.status) : r[k];
  rows.sort((a, b) => {
    const x = val(a), y = val(b);
    const ex = x === null || x === undefined || x === "", ey = y === null || y === undefined || y === "";
    if (ex || ey) return ex - ey;                                       // fehlende Werte immer ans Ende
    const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: "base" });
    return desc ? -c : c;
  });
  return rows;
}

function purRenderTable() {
  const st = PUR.st, box = $("#purTable");
  if (!st.rows.length) {
    const ready = st.sources.some((s) => s.ready);
    box.innerHTML = `<div class="tg-empty">${st.sources.length && ready ? "Noch keine Käufe geholt – „↻ Aktualisieren“ liest die gekauften Titel."
      : "Zuerst unter Plugins › Beatport anmelden – dann holt „↻ Aktualisieren“ die gekauften Titel."}</div>`;
    return;
  }
  const rows = purVisible();
  const all = rows.length && rows.every((r) => PUR.sel.has(r.k));
  const head = PUR_COLS.map(([k, l]) => `<th data-pursort="${k}" class="${["dur", "bpm"].includes(k) ? "r" : ""}" aria-sort="${PUR.sort.k === k ? (PUR.sort.desc ? "descending" : "ascending") : "none"}">${esc(l)}${PUR.sort.k === k ? (PUR.sort.desc ? " ▾" : " ▴") : ""}</th>`).join("");
  box.innerHTML = `<table class="pur-t"><thead><tr><th><input type="checkbox" id="purAll" ${all ? "checked" : ""} aria-label="Alle wählen"></th>${head}<th></th></tr></thead><tbody>
    ${rows.map((r) => {
      const stc = r.preorder ? `<span class="pur-st pre">Vorbestellung</span>` : `<span class="pur-st ${r.status}" title="${esc(r.file || r.reason || "")}">${esc(PUR_STATUS[r.status] || r.status)}</span>`;
      const date = r.bought ? esc(r.bought.slice(0, 10)) : (r.seen ? `<span class="muted" title="Kein Kaufdatum vom Store – zuerst gesehen">${esc(new Date(r.seen * 1000).toLocaleDateString())}</span>` : "");
      const bpm = r.bpm ? (Math.round(r.bpm * 10) / 10).toString() : "";
      return `<tr data-k="${esc(r.k)}" class="${PUR.sel.has(r.k) ? "sel" : ""}"><td><input type="checkbox" data-pursel ${PUR.sel.has(r.k) ? "checked" : ""}></td>
        <td>${stc}</td><td class="nm" translate="no" title="${esc(r.title)}">${esc(r.title)}</td><td class="nm" translate="no" title="${esc(r.artist)}">${esc(r.artist)}</td>
        <td class="nm muted" translate="no">${esc(r.mix)}</td><td class="r muted">${r.dur ? fmtTime(r.dur) : ""}</td>
        <td>${r.key ? keyBadge(r.key) : ""}</td><td class="r">${bpm}</td><td translate="no">${esc(r.catalog)}</td>
        <td translate="no">${esc(purStoreName(r.store))}</td><td>${date}</td>
        <td>${r.url ? `<a href="#" class="pls-link" data-url="${esc(r.url)}" title="Bei ${esc(purStoreName(r.store))} öffnen">↗</a>` : ""}</td></tr>`;
    }).join("")}</tbody></table>${rows.length ? "" : '<div class="tg-empty">Keine Käufe für diesen Filter.</div>'}`;
}

async function purRefresh(match = false, full = false) {
  const r = await runTask(match ? call("start_purch_match") : call("start_purch_refresh", null, full), match ? "Käufe abgleichen" : "Käufe aktualisieren");
  if (!r || r.cancelled) return;
  await purchasesShow();
  const c = r.count || {};
  toast((match ? "" : `${fmtN(r.new || 0)} neue Käufe · `) + `${fmtN(c.library || 0)} in Bibliothek · ${fmtN(c.inbox || 0)} im Eingang · ${fmtN(c.unclear || 0)} unklar · ${fmtN(c.missing || 0)} fehlen`);
  if (r.errors && r.errors.length) info("Hinweise", r.errors.join("\n"));
}

async function purDownload() {
  const st = PUR.st;
  const keys = PUR.sel.size ? [...PUR.sel] : null;
  const n = keys ? keys.length : st.rows.filter((r) => r.status === "missing" && !r.preorder).length;
  const ok = await modal({ title: "Käufe herunterladen",
    html: `<p style="margin:0">${fmtN(n)} Titel in den Eingangsordner laden?</p><p class="sm" translate="no" style="margin:6px 0 0">${esc(st.dest)}</p>
      <p class="muted sm" style="margin:8px 0 0">Die Dateien kommen unverändert vom Store; danach geht es wie gewohnt mit „Vorbereiten“ weiter. Vorbestellungen werden ausgelassen.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Herunterladen", value: true, primary: true }] });
  if (!ok) return;
  const r = await runTask(call("start_purch_download", keys), "Käufe herunterladen");
  if (!r || r.cancelled) return;
  PUR.sel = new Set();
  await purchasesShow();
  toast(`${fmtN(r.downloaded || 0)} Titel geladen.`);
  if (r.failed && r.failed.length) info("Nicht geladen", r.failed.slice(0, 30).join("\n") + (r.failed.length > 30 ? "\n…" : ""));
}

async function purPickDest() {
  const p = await call("pick_path", "", true, PUR.st ? PUR.st.dest : "");
  if (p) purApply(await call("purch_set_dest", p));
  else if (!S.settings.native) toast("Im Browser-Modus ist kein Ordnerdialog verfügbar.");
}

function purRowMenu(e, k) {
  const r = PUR.st.rows.find((x) => x.k === k); if (!r) return;
  const items = [];
  if (r.url) items.push({ label: `Bei ${purStoreName(r.store)} öffnen`, run: () => call("open_url", r.url) });
  if (r.file) items.push({ label: "Dateiordner öffnen", icon: ICON.folder, run: () => call("reveal", r.file) });
  const ws = typeof webSearchItem === "function" ? webSearchItem(e, r.artist, r.title + (r.mix ? ` (${r.mix})` : "")) : null;
  if (ws) items.push(ws);
  if (r.status !== "library" && !r.preorder) items.push({ label: "Herunterladen …", run: () => { PUR.sel = new Set([k]); purRenderBar(); purDownload(); } });
  if (items.length) showMenu(e.clientX, e.clientY, items);
}

function purInit() {
  $("#purRefresh").addEventListener("click", () => purRefresh(false));
  $("#purMatch").addEventListener("click", () => purRefresh(true));
  $("#purFull").addEventListener("click", () => purRefresh(false, true));
  $("#purDl").addEventListener("click", purDownload);
  $("#purDestBtn").addEventListener("click", purPickDest);
  let qt = 0;
  $("#purFind").addEventListener("input", (e) => { clearTimeout(qt); qt = setTimeout(() => { PUR.q = e.target.value; purRenderTable(); }, 120); });
  $("#purStore").addEventListener("change", (e) => { PUR.store = e.target.value; purRenderTable(); });
  $("#purStatus").addEventListener("click", (e) => { const b = e.target.closest("[data-purst]"); if (!b) return; PUR.status = b.dataset.purst; purRenderBar(); purRenderTable(); });
  const box = $("#purTable");
  box.addEventListener("click", (e) => {
    const lk = e.target.closest(".pls-link[data-url]");
    if (lk) { e.preventDefault(); call("open_url", lk.dataset.url); return; }
    const th = e.target.closest("[data-pursort]");
    if (th) { const k = th.dataset.pursort; PUR.sort = PUR.sort.k === k ? { k, desc: !PUR.sort.desc } : { k, desc: k === "bought" }; purRenderTable(); return; }
    if (e.target.id === "purAll") { const rows = purVisible(); if (e.target.checked) rows.forEach((r) => PUR.sel.add(r.k)); else rows.forEach((r) => PUR.sel.delete(r.k)); purRenderTable(); purRenderBar(); return; }
    const cb = e.target.closest("[data-pursel]");
    if (cb) { const k = cb.closest("tr").dataset.k; if (cb.checked) PUR.sel.add(k); else PUR.sel.delete(k); cb.closest("tr").classList.toggle("sel", cb.checked); purRenderBar(); }
  });
  box.addEventListener("contextmenu", (e) => { const tr = e.target.closest("tr[data-k]"); if (!tr) return; e.preventDefault(); purRowMenu(e, tr.dataset.k); });
}

purInit();
setTimeout(() => { if (!PUR.st) call("purch_state").then((st) => { PUR.st = st; purSideCount(); }).catch(() => {}); }, 1200);
if (typeof S !== "undefined" && S.module === "purchases") purchasesShow();
