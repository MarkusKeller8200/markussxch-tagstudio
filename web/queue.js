/* MarKusSXCH TagStudio – Warteschlange des Players (#138): „Als Nächstes spielen“ / „Zur Warteschlange hinzufügen“.
   Die Warteschlange hat Vorrang vor der Reihenfolge im Tagger bzw. DJ-Set: ⏭, Titelende und Überblenden nehmen den
   ersten geladenen Titel daraus; gespielte Titel fallen heraus. Gemerkt in der Konfiguration (session_djset.pq_*). */
"use strict";

const PQ = { items: [] };

function pqApply(st, quiet = false) {
  PQ.items = (st && st.items) || [];
  const n = PQ.items.length, b = $("#plQueue");
  if (b) {
    $("#plQueueN").textContent = n ? String(n) : "";
    b.classList.toggle("on", n > 0);
    b.title = n ? `Warteschlange: ${n} Titel – als Nächstes: ${pqLabel(PQ.items[0])}` : "Warteschlange ist leer (Rechtsklick auf einen Titel › „Als Nächstes spielen“)";
  }
  if (st && st.message && !quiet) toast(st.message);
  if ($("#pqList")) pqRenderList();
}

function pqLabel(r) { return r.title ? `${r.artist ? r.artist + " – " : ""}${r.title}` : r.name; }

async function pqCall(name, ...args) {
  try { pqApply(await call(name, ...args)); } catch (e) { toast(String(e.message || e)); }
}

/** Nächster spielbarer Titel (Tagger-Index) oder null */
function pqHead() {
  const r = PQ.items.find((x) => x.i !== null && x.i !== undefined && !(PLAYER.kind === "tag" && x.i === PLAYER.ref));
  return r ? r.i : null;
}

/** Titel i wird gespielt → aus der Warteschlange nehmen (aus plLoad) */
function pqTaken(i) {
  if (!PQ.items.some((x) => x.i === i)) return;
  call("pq_take", i).then((st) => pqApply(st, true)).catch(() => {});
}

/** ⏭ / Titelende: nächsten Titel der Warteschlange spielen. → true, wenn einer da war */
function pqPlayNext() {
  const i = pqHead();
  if (i === null) return false;
  if (S.module === "tagger" && typeof tgSelect === "function") {
    PLAYER.noFollow = true;
    tgSelect(i, {}).finally(() => { PLAYER.noFollow = false; TG.anchor = i; tgScrollTo(i); });
  } else if (S.module === "djset" && typeof djSelectTag === "function") djSelectTag(i);
  else if (S.module === "playlists" && typeof plsSelectTag === "function") plsSelectTag(i);   // #267
  plLoad({ kind: "tag", ref: i }, true);
  return true;
}

function pqAdd(idx, front) {
  if (!idx || !idx.length) { toast("Zuerst Titel markieren."); return; }
  pqCall("pq_add", idx, !!front);
}

function pqMenuItems(idx) {
  const n = idx.length;
  return [{ label: `Als Nächstes spielen${n > 1 ? ` (${n})` : ""}`, run: () => pqAdd(idx, true) },
    { label: `Zur Warteschlange hinzufügen${n > 1 ? ` (${n})` : ""}`, run: () => pqAdd(idx, false) }];
}

// ---------------------------------------------------------------- Liste (Dialog)
function pqRenderList() {
  const el = $("#pqList"); if (!el) return;
  el.innerHTML = PQ.items.length ? PQ.items.map((r, k) => `<div class="pq-row${r.i === null ? " missing" : ""}" data-k="${k}">
      <span class="pq-n">${k + 1}</span><span class="pq-t" title="${esc(r.path)}">${esc(pqLabel(r))}${r.i === null ? ' <span class="muted sm">(nicht geladen)</span>' : ""}</span>
      <button class="icon-btn" data-up="${k}" title="Nach oben" aria-label="Nach oben"${k ? "" : " disabled"}>↑</button>
      <button class="icon-btn" data-down="${k}" title="Nach unten" aria-label="Nach unten"${k < PQ.items.length - 1 ? "" : " disabled"}>↓</button>
      <button class="icon-btn" data-play="${k}" title="Jetzt spielen" aria-label="Jetzt spielen"${r.i === null ? " disabled" : ""}>▶</button>
      <button class="icon-btn" data-del="${k}" title="Aus der Warteschlange nehmen" aria-label="Entfernen">✕</button></div>`).join("")
    : '<div class="muted sm">Leer. Im Tagger oder DJ-Set per Rechtsklick „Als Nächstes spielen“ bzw. „Zur Warteschlange hinzufügen“.</div>';
}

async function pqDialog() {
  const r = await modal({ title: "Warteschlange", wide: true,
    html: '<p class="muted sm" style="margin:0 0 8px">Hat Vorrang vor der Reihenfolge im Tagger bzw. DJ-Set (⏭, Titelende, Überblenden). Gespielte Titel fallen heraus.</p><div id="pqList" class="pq-list"></div>',
    buttons: [{ label: "Leeren", value: "clear" }, { label: "Als DJ-Set übernehmen", value: "dj" }, { label: "Schliessen", value: null, primary: true }],
    onMount: (body) => {
      pqRenderList();
      body.addEventListener("click", (e) => {
        const b = e.target.closest("button[data-up],button[data-down],button[data-play],button[data-del]"); if (!b) return;
        const paths = PQ.items.map((x) => x.path);
        if (b.dataset.play !== undefined) { const it = PQ.items[+b.dataset.play]; if (it.i !== null) plLoad({ kind: "tag", ref: it.i }, true); return; }
        if (b.dataset.del !== undefined) paths.splice(+b.dataset.del, 1);
        else { const k = +(b.dataset.up ?? b.dataset.down), j = k + (b.dataset.up !== undefined ? -1 : 1); [paths[k], paths[j]] = [paths[j], paths[k]]; }
        pqCall("pq_set", paths);
      });
    } });
  if (r === "clear" && PQ.items.length) pqCall("pq_set", []);
  if (r === "dj") {
    if (!PQ.items.length) { toast("Die Warteschlange ist leer."); return; }
    try {
      const st = await call("pq_to_djset");
      if (typeof djApply === "function" && S.module === "djset") djApply(st); else { DJ.st = st; djSideCount(st); toast(st.message); }
    } catch (e) { toast(String(e.message || e)); }
  }
}

function pqInit() {
  const nx = $("#plNext"); if (!nx || $("#plQueue")) return;
  nx.insertAdjacentHTML("afterend", '<button class="icon-btn pl-tog pl-queue" id="plQueue" aria-label="Warteschlange"><svg class="i" viewBox="0 0 24 24"><path d="M4 6h12M4 12h12M4 18h8"/><path d="m16 15 5 3-5 3Z"/></svg><span class="pl-queue-n" id="plQueueN"></span></button>');
  $("#plQueue").addEventListener("click", pqDialog);
  call("pq_state").then((st) => pqApply(st, true)).catch(() => {});
}

/** Tagger neu geladen → Indizes neu auflösen */
function pqAfterTaggerLoad() { call("pq_state").then((st) => pqApply(st, true)).catch(() => {}); }
