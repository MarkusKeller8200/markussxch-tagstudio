/* MarKusSXCH TagStudio – Zurück/Vorwärts zwischen Ansichten (#274).
   Aufgezeichnet werden nur Sprünge aus dem Inhalt (z. B. Playlist › „Im Tagger öffnen“), nicht die Klicks in der
   Seitenleiste. Zurück stellt Seite und Stelle wieder her (Auswahl, Filter, Scrollposition), macht aber keine Aktion
   rückgängig und lädt keinen Tagger-Ordner neu. Der Verlauf gilt nur für die laufende Sitzung. */
"use strict";

const NAV = { back: [], fwd: [], MAX: 30, busy: false };

function navName(m) { return (typeof NAV_NAMES !== "undefined" && NAV_NAMES[m]) || m; }

/** Stelle auf der aktuellen Seite festhalten */
function navCapture() {
  const m = S.module, e = { module: m, detail: "" };
  try {
    if (m === "playlists" && typeof PLS !== "undefined" && PLS.st) {
      const p = typeof plsCur === "function" ? plsCur() : null;
      Object.assign(e, { pl: PLS.st.sel, rows: [...PLS.sel], anchor: PLS.anchor, scroll: $("#plsList").scrollTop, detail: p ? p.name : "" });
    } else if (m === "tagger" && typeof TG !== "undefined" && TG.loaded) {
      const r = TG.rows[TG.anchor];
      Object.assign(e, { root: TG.root, rel: r ? r.rel : "", selRel: [...TG.sel].map((i) => TG.rows[i] && TG.rows[i].rel).filter(Boolean),
        query: $("#tgQuery").value, plf: TG.plFilter ? TG.plFilter.id : "", scroll: $("#tgScroll").scrollTop, detail: r ? r.name : "" });
    } else if (m === "djset" && typeof DJ !== "undefined" && DJ.st) {
      Object.assign(e, { sel: DJ.sel, scroll: $("#djList").scrollTop, detail: DJ.st.name || "" });
    } else if (m === "compare") {
      e.cur = S.cur;
    } else if (m === "help" && typeof HELP !== "undefined") {
      e.tab = HELP.tab;
    }
  } catch (x) { /* Stelle unbekannt: nur die Seite */ }
  return e;
}

function navLabel(e) { return navName(e.module) + (e.detail ? ` › ${e.detail}` : ""); }

/** Vor einem Sprung aus dem Inhalt aufrufen (setModule macht das selbst, ausser für die Seitenleiste) */
function navPush() {
  if (NAV.busy || !S.module) return;
  const e = navCapture(), last = NAV.back[NAV.back.length - 1];
  if (last && last.module === e.module && last.detail === e.detail) NAV.back[NAV.back.length - 1] = e;
  else NAV.back.push(e);
  NAV.back = NAV.back.slice(-NAV.MAX);
  NAV.fwd = [];
  navRender();
}

/** dir -1 = zurück, +1 = vorwärts; steps > 1 springt mehrere Stationen (Rechtsklick-Liste) */
async function navGo(dir, steps = 1) {
  const from = dir < 0 ? NAV.back : NAV.fwd, to = dir < 0 ? NAV.fwd : NAV.back;
  if (!from.length || NAV.busy) return;
  let e = null;
  for (let k = 0; k < steps && from.length; k++) {
    to.push(k === 0 ? navCapture() : e);
    e = from.pop();
  }
  await navRestore(e);
}

async function navRestore(e) {
  NAV.busy = true;
  try {
    if (e.module === "playlists" && typeof PLS !== "undefined" && e.pl) {
      if (PLS.st) PLS.st.sel = e.pl;
      setModule("playlists");
      if (typeof playlistsShow === "function") await playlistsShow();
      const pl = typeof plsCur === "function" ? plsCur() : null;
      if (pl && pl.id === e.pl) {
        PLS.sel = new Set((e.rows || []).filter((k) => k < pl.items.length));
        PLS.anchor = e.anchor !== undefined && e.anchor < pl.items.length ? e.anchor : null;
        plsRenderList();
        $("#plsList").scrollTop = e.scroll || 0;
      }
    } else if (e.module === "tagger") {
      setModule("tagger");
      if (TG.loaded && e.root && TG.root === e.root) {            // gleicher Ordner: Stelle wiederherstellen
        $("#tgQuery").value = e.query || "";
        if ((e.plf || "") !== (TG.plFilter ? TG.plFilter.id : "")) await tgSetPlFilter(e.plf || null);
        const byRel = new Map(TG.rows.map((r) => [r.rel, r.i]));
        const sel = (e.selRel || []).map((r) => byRel.get(r)).filter((i) => i !== undefined);
        const a = byRel.get(e.rel);
        if (sel.length) TG.sel = new Set(sel);
        if (a !== undefined) TG.anchor = a;
        tgApplyOrder();
        await tgLoadDetail();
        $("#tgScroll").scrollTop = e.scroll || 0;
      }
    } else if (e.module === "djset") {
      setModule("djset");
      if (typeof djsetShow === "function") await djsetShow();
      if (e.sel && DJ.st) { const k = DJ.st.items.findIndex((r) => r.path === e.sel); if (k >= 0) djSelect(k); }
      if (e.scroll) $("#djList").scrollTop = e.scroll;
    } else if (e.module === "compare") {
      setModule("compare");
      if (e.cur !== null && e.cur !== undefined && e.cur !== S.cur && S.pairs.some((p) => p.i === e.cur)) await selectPair(e.cur);
    } else if (e.module === "help") {
      setModule("help");
      if (e.tab && typeof helpTab === "function") helpTab(e.tab);
    } else {
      setModule(e.module);
    }
  } catch (x) { console.error(x); }
  finally { NAV.busy = false; navRender(); }
}

function navRender() {
  const box = $("#navHist"); if (!box) return;
  const b = NAV.back[NAV.back.length - 1], f = NAV.fwd[NAV.fwd.length - 1];
  box.hidden = !b && !f;
  const back = $("#navBack"), fwd = $("#navFwd");
  back.disabled = !b;
  $("#navBackLbl").innerHTML = b ? `<span>${esc(navName(b.module))}</span>${b.detail ? `<small translate="no">${esc(b.detail)}</small>` : ""}` : "<span>Zurück</span>";
  back.title = b ? `Zurück zu ${navLabel(b)} (Alt+←, Rechtsklick: Verlauf)` : "Zurück";
  fwd.hidden = !f;
  fwd.title = f ? `Vorwärts zu ${navLabel(f)} (Alt+→)` : "Vorwärts";
}

function navMenu(e) {
  e.preventDefault();
  if (!NAV.back.length) return;
  const list = [...NAV.back].reverse().slice(0, 12);
  showMenu(e.clientX, e.clientY, list.map((x, k) => ({ label: navLabel(x), run: () => navGo(-1, k + 1) })));
}

(function navInit() {
  $("#navBack").addEventListener("click", () => navGo(-1));
  $("#navFwd").addEventListener("click", () => navGo(1));
  $("#navBack").addEventListener("contextmenu", navMenu);
  document.addEventListener("keydown", (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
    if (S.module === "compare") return;                              // dort kopiert Alt+←/→ Felder
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") || !$("#modal").hidden) return;
    e.preventDefault();
    navGo(e.key === "ArrowLeft" ? -1 : 1);
  });
  // Maustasten Zurück/Vorwärts (Taste 4/5) – auch die Navigation des Browsers verhindern
  document.addEventListener("mousedown", (e) => { if (e.button === 3 || e.button === 4) e.preventDefault(); });
  document.addEventListener("mouseup", (e) => {
    if (e.button !== 3 && e.button !== 4) return;
    e.preventDefault();
    if (!$("#modal").hidden) return;
    navGo(e.button === 3 ? -1 : 1);
  });
  navRender();
})();
