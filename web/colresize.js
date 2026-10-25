/* MarKusSXCH TagStudio – Spaltenbreite in Tabellen per Ziehen (#337, #340).
   Gemeinsame Hilfe für alle Tabellen: Griff am rechten Rand jedes Spaltenkopfs, ziehen = Breite, Doppelklick =
   automatisch (passend zum Inhalt), Tastatur ←/→ (mit Umschalt grösser). Breiten je Tabelle in LAYOUT.col_widths
   gemerkt; Rechtsklick auf die Kopfzeile → „Spaltenbreiten zurücksetzen“.
   Aufruf nach jedem Zeichnen der Tabelle: colResize(tableEl, "tabellen-id"). Spalten werden über th[data-col]
   erkannt, sonst über ihre Nummer; th[data-nogrip] bekommt keinen Griff (z. B. Häkchen-Spalte). */

const COLW = { min: 36, max: 1200, step: 10 };

function colWidths(tid) {
  const all = LAYOUT.col_widths || {};
  return all[tid] || {};
}
function colWidthsSave(tid, w) {
  const all = { ...(LAYOUT.col_widths || {}) };
  if (w && Object.keys(w).length) all[tid] = w; else delete all[tid];
  LAYOUT.col_widths = all;
  saveUi("col_widths");
}
const colKey = (th, i) => th.dataset.col || String(i);

/** Gemerkte Breiten anwenden; ohne gemerkte Breiten bleibt die Tabelle im automatischen Layout. */
function colApply(table, tid) {
  const ths = [...table.querySelectorAll(":scope > thead > tr:first-child > th")];
  const w = colWidths(tid);
  const fixed = Object.keys(w).length > 0;
  table.classList.toggle("col-fixed", fixed);
  if (!fixed) {
    ths.forEach((th) => { th.style.width = ""; });
    table.style.width = "";
    return;
  }
  // Spalten ohne gemerkte Breite behalten ihre heutige Breite (einmal gemessen, nicht gespeichert)
  const cur = ths.map((th) => th.getBoundingClientRect().width);
  let sum = 0;
  ths.forEach((th, i) => {
    const px = Math.round(w[colKey(th, i)] || cur[i] || 80);
    th.style.width = px + "px";
    sum += px;
  });
  table.style.width = sum + "px";
}

/** Breite passend zum Inhalt einer Spalte messen (höchstens 600 px). */
function colAutoWidth(table, idx) {
  const cells = [...table.rows].map((r) => r.cells[idx]).filter(Boolean);
  let best = 0;
  const probe = document.createElement("span");
  probe.style.cssText = "position:absolute;visibility:hidden;white-space:nowrap;left:-9999px;top:0";
  document.body.appendChild(probe);
  for (const c of cells.slice(0, 400)) {
    const cs = getComputedStyle(c);
    probe.style.font = cs.font;
    probe.style.letterSpacing = cs.letterSpacing;
    probe.style.textTransform = cs.textTransform;
    probe.innerHTML = c.innerHTML;
    probe.querySelectorAll(".col-grip").forEach((g) => g.remove());
    const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    best = Math.max(best, probe.getBoundingClientRect().width + pad + 14);   // + Platz für Sortier-Pfeil/Griff
  }
  probe.remove();
  return clamp(Math.ceil(best), COLW.min, 600);
}

function colResize(table, tid) {
  if (!table || !tid) return;
  const ths = [...table.querySelectorAll(":scope > thead > tr:first-child > th")];
  if (!ths.length) return;
  table.dataset.colTid = tid;
  ths.forEach((th, i) => {
    if (th.dataset.nogrip !== undefined || th.querySelector(":scope > .col-grip")) return;
    const g = document.createElement("span");
    g.className = "col-grip";
    g.tabIndex = 0;
    g.setAttribute("role", "separator");
    g.setAttribute("aria-orientation", "vertical");
    g.setAttribute("aria-label", "Spaltenbreite");
    g.title = "Ziehen: Breite · Doppelklick: automatisch · ←/→";
    g.dataset.i = String(i);
    th.appendChild(g);
  });
  colApply(table, tid);
}

/** Alle Spalten einfrieren (heutige Breiten messen) und eine Spalte setzen. */
function colSet(table, tid, i, px) {
  const ths = [...table.querySelectorAll(":scope > thead > tr:first-child > th")];
  const w = { ...colWidths(tid) };
  ths.forEach((th, k) => { const key = colKey(th, k); if (!w[key]) w[key] = Math.round(th.getBoundingClientRect().width); });
  w[colKey(ths[i], i)] = clamp(Math.round(px), COLW.min, COLW.max);
  colWidthsSave(tid, w);
  colApply(table, tid);
}

function colReset(table, tid) {
  colWidthsSave(tid, null);
  colApply(table, tid);
  toast("Spaltenbreiten zurückgesetzt.");
}

// Ein gemeinsamer Satz Ereignisse für alle Tabellen (die Griffe werden bei jedem Zeichnen neu angelegt)
document.addEventListener("pointerdown", (e) => {
  const g = e.target.closest && e.target.closest(".col-grip");
  if (!g || e.button !== 0) return;
  const table = g.closest("table"), tid = table && table.dataset.colTid;
  if (!tid) return;
  e.preventDefault(); e.stopPropagation();
  const th = g.parentElement, i = +g.dataset.i, x0 = e.clientX, w0 = th.getBoundingClientRect().width;
  g.setPointerCapture(e.pointerId);
  document.body.classList.add("col-dragging");
  let last = w0;
  const move = (ev) => { last = clamp(w0 + ev.clientX - x0, COLW.min, COLW.max); colSet(table, tid, i, last); };
  const up = () => {
    g.removeEventListener("pointermove", move);
    document.body.classList.remove("col-dragging");
  };
  g.addEventListener("pointermove", move);
  g.addEventListener("pointerup", up, { once: true });
  g.addEventListener("pointercancel", up, { once: true });
}, true);
// Klick auf den Griff sortiert nicht (Spaltenköpfe sind oft Sortier-Knöpfe)
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest(".col-grip")) { e.preventDefault(); e.stopPropagation(); } }, true);
document.addEventListener("dblclick", (e) => {
  const g = e.target.closest && e.target.closest(".col-grip");
  if (!g) return;
  e.preventDefault(); e.stopPropagation();
  const table = g.closest("table"), tid = table.dataset.colTid;
  colSet(table, tid, +g.dataset.i, colAutoWidth(table, +g.dataset.i));
}, true);
document.addEventListener("keydown", (e) => {
  const g = e.target.closest && e.target.closest(".col-grip");
  if (!g || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
  e.preventDefault(); e.stopPropagation();
  const table = g.closest("table"), tid = table.dataset.colTid;
  const w = g.parentElement.getBoundingClientRect().width, d = (e.shiftKey ? 4 : 1) * COLW.step;
  colSet(table, tid, +g.dataset.i, w + (e.key === "ArrowRight" ? d : -d));
}, true);
document.addEventListener("contextmenu", (e) => {
  const head = e.target.closest && e.target.closest("thead");
  const table = head && head.closest("table[data-col-tid]");
  if (!table) return;
  e.preventDefault();
  const tid = table.dataset.colTid;
  showMenu(e.clientX, e.clientY, [{ label: "Spaltenbreiten zurücksetzen", run: () => colReset(table, tid) }]);
});
