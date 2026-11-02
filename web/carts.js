/* MarKusSXCH TagStudio – Warenkorb (#420–#424, #433–#437): Titel zum Kaufen in Warenkörben sammeln (Liste einfügen, aus
   Ideen, von Hand, per Link – jeweils mit Vorschau), Assistent Schritt für Schritt, auf bereits gekaufte prüfen, bei Beatport zuordnen und die Einkaufsliste als Playlist TagStudio_CART_…
   senden (nur auf Klick). Körbe bleiben als Historik „Offen“/„Gekauft“. Logik in carts.py / session_carts.py. */
"use strict";

const CART = { d: null, filter: "open", checked: new Set(), showArchived: false };
const CART_FILTERS = [["open", "Einkaufsliste"], ["bought", "Gekauft"], ["lib", "In Bibliothek"], ["removed", "Entfernt"], ["all", "Alle"]];
const CART_STATUS = { open: "offen", bought: "gekauft", lib: "in Bibliothek", removed: "entfernt" };
const CART_WHY = { hand: "von Hand", bought: "bereits gekauft", lib: "in Bibliothek" };
const CART_SRC = { text: "Liste", ideas: "Ideen", manual: "von Hand", url: "Link" };

async function cartsShow(sel) {
  try { cartsApply(await call("carts_overview", sel || (CART.d && CART.d.sel) || "", CART.showArchived)); } catch (e) { toast(String(e.message || e)); }
}

function cartsCur() { return CART.d ? CART.d.carts.find((c) => c.id === CART.d.sel) || null : null; }

function cartsDate(ts) { return ts ? new Date(ts * 1000).toLocaleDateString() : ""; }

function cartsListBtn(c) {
  const n = c.counts || {};
  const tip = c.status === "bought"
    ? `${c.name}: gekauft am ${cartsDate(c.closed)}${c.closed_by === "hand" ? " (von Hand abgeschlossen)" : ""}`
    : `${c.name}: ${n.open || 0} auf der Einkaufsliste · ${n.bought || 0} gekauft · ${n.removed || 0} entfernt`;
  return `<button class="idea-l cart-l${c.id === CART.d.sel ? " on" : ""}${c.archived ? " arch" : ""}" data-c="${esc(c.id)}" aria-current="${c.id === CART.d.sel}" title="${esc(tip)}">
    <span class="nm ellipsis" translate="no">${esc(c.name)}</span>${c.status === "bought" ? `<span class="n">${esc(cartsDate(c.closed))}</span>` : `<span class="n">${fmtN(c.count)}</span>${n.open ? `<span class="b" title="Auf der Einkaufsliste">${fmtN(n.open)}</span>` : ""}`}</button>`;
}

function cartsApply(d) {
  if (CART.d && CART.d.sel !== d.sel) CART.checked.clear();
  CART.d = d;
  cartsBadge(d.open);
  const active = d.carts.filter((c) => !c.archived), opened = active.filter((c) => c.status === "open"), done = active.filter((c) => c.status === "bought");
  const arch = d.carts.filter((c) => c.archived);
  $("#cartLists").innerHTML = `<div class="idea-lh"><b>Warenkörbe</b><button class="icon-btn" id="cartNew" title="Neuer Warenkorb …" aria-label="Neuer Warenkorb">＋</button></div>`
    + `<div class="cart-grp muted sm">Offen</div>` + (opened.length ? opened.map(cartsListBtn).join("") : '<div class="muted sm" style="padding:4px 8px">Kein offener Warenkorb – „＋“ legt einen an.</div>')
    + (done.length ? `<div class="cart-grp muted sm" title="Gekaufte Warenkörbe bleiben als Historik erhalten">Gekauft (Historik)</div>` + done.map(cartsListBtn).join("") : "")
    + (d.n_archived ? `<button class="ghost sm cart-arch" id="cartArchToggle">${CART.showArchived ? "Archiv ausblenden" : `Archiv (${fmtN(d.n_archived)})`}</button>` + (CART.showArchived ? arch.map(cartsListBtn).join("") : "") : "");
  const c = cartsCur(), n = c ? c.counts : {};
  const cnt = (k) => (k === "all" ? (c ? c.count : 0) : n[k] || 0);
  $("#cartFilter").innerHTML = CART_FILTERS.map(([k, t]) => `<button data-f="${k}" role="radio" aria-checked="${k === CART.filter}" class="${k === CART.filter ? "on" : ""}">${t}${cnt(k) ? ` <span class="muted">${fmtN(cnt(k))}</span>` : ""}</button>`).join("");
  $("#cartTitle").textContent = c ? c.name : "";
  const open = !!c && c.status === "open" && !c.archived, bp = d.beatport || {};
  ["#cartAddText", "#cartAddIdeas", "#cartAddManual", "#cartAddUrl", "#cartMatch", "#cartCheck", "#cartBp", "#cartWizard"].forEach((s) => ($(s).disabled = !open));
  $("#cartMatch").title = !bp.available ? "Beatport-Plugin aus oder nicht angemeldet" : "Titel ohne Beatport-ID über die Beatport-Suche zuordnen (nur lesend)";
  $("#cartBp").title = !bp.available ? "Beatport-Plugin aus oder nicht angemeldet" : !bp.write ? "Im Beatport-Plugin „Playlists in Beatport schreiben“ einschalten"
    : `Einkaufsliste als Beatport-Playlist ${c ? c.bp : ""} anlegen bzw. abgleichen – danach auf beatport.com „Alle in den Warenkorb“`;
  $("#cartCheck").title = "Einkäufe aktualisieren und die Titel mit „Einkäufe“ und der Bibliothek abgleichen";
  $("#cartInfo").textContent = !c ? "" : [
    c.status === "bought" ? `Gekauft am ${cartsDate(c.closed)}${c.closed_by === "hand" ? " (von Hand abgeschlossen)" : ""}` : `${fmtN(n.open || 0)} auf der Einkaufsliste`,
    `${fmtN(n.bought || 0)} gekauft`, `${fmtN(n.removed || 0)} entfernt`, `Shop: ${c.store_name}`,
    c.checked ? `geprüft am ${cartsDate(c.checked)}` : "noch nicht auf Käufe geprüft",
    c.pushed ? `an Beatport gesendet am ${cartsDate(c.pushed.at)} (${fmtN(c.pushed.count || 0)} Titel)` : "",
  ].filter(Boolean).join(" · ");
  cartsHint(c);
  cartsRender();
}

/** Hinweise über der Tabelle: gekaufte auf der Liste (#422), unsichere/fehlende Beatport-Treffer (#423), abgeschlossen */
function cartsHint(c) {
  const box = $("#cartHint");
  const parts = [];
  if (c && c.archived) parts.push(`Archiviert. <button class="ghost sm" data-h="unarch">Zurückholen</button>`);
  else if (c && c.status === "bought") parts.push(`Dieser Warenkorb ist abgeschlossen (Historik). <button class="ghost sm" data-h="reopen">Wieder öffnen</button>`);
  else if (c) {
    const lib = (CART.d.items || []).filter((e) => e.status === "lib").length, b = (c.counts.bought || 0);
    if (b + lib) parts.push(`${fmtN(b + lib)} Titel ${b && lib ? "sind gekauft bzw. schon in der Bibliothek" : b ? "sind bereits gekauft" : "sind schon in der Bibliothek"} und würden doppelt gekauft. <button class="ghost sm" data-h="rmbought">Gekaufte entfernen (${fmtN(b + lib)}) …</button>`);
    if (c.unsure) parts.push(`${fmtN(c.unsure)} unsichere Beatport-Treffer – in der Spalte „Beatport“ wählen.`);
    else if (c.no_id && c.counts.open) parts.push(`${fmtN(c.no_id)} Titel ohne Beatport-Zuordnung – „Bei Beatport suchen …“.`);
  }
  box.innerHTML = parts.map((p) => `<div>${p}</div>`).join("");
  box.hidden = !parts.length;
}

function cartsRows() {
  const q = ($("#cartSearch").value || "").toLowerCase().trim(), f = CART.filter;
  return CART.d.items.filter((e) => (f === "all" || e.status === f) && (!q || `${e.artist} ${e.title} ${e.mix} ${e.note} ${e.source || ""}`.toLowerCase().includes(q)));
}

function cartsBpCell(e) {
  if (e.sid) return `<a href="#" data-a="open" class="cart-bp ok" title="${esc(e.url || "")}">✓ ${esc(e.sid)}</a>`;
  if (e.match === "unsure") return `<button class="ghost sm cart-bp warn" data-a="pick" title="Mehrere mögliche Treffer – wählen">unsicher – wählen …</button>`;
  if (e.match === "none") return `<span class="muted sm" title="Bei Beatport nicht gefunden">nicht gefunden</span>`;
  return '<span class="muted">—</span>';
}

function cartsRender() {
  const box = $("#cartList"), c = cartsCur();
  if (!c) { box.innerHTML = '<div class="tg-empty">Links einen Warenkorb wählen oder mit „＋“ einen neuen anlegen.</div>'; cartsSelInfo(); return; }
  const rows = cartsRows();
  if (!rows.length) {
    box.innerHTML = `<div class="tg-empty">${CART.d.items.length ? "Nichts in dieser Ansicht." : "Dieser Warenkorb ist leer – „Liste einfügen …“ (z. B. von 1001Tracklists), „Aus Ideen …“, „Von Hand …“, „Per Link …“ oder der „Assistent …“."}</div>`;
    cartsSelInfo();
    return;
  }
  const editable = c.status === "open" && !c.archived;
  const all = rows.every((e) => CART.checked.has(e.k));
  box.innerHTML = `<table class="disc-t idea-t cart-t"><thead><tr><th><input type="checkbox" id="cartAll" aria-label="Alle markieren" ${all ? "checked" : ""} ${editable ? "" : "disabled"}></th><th>Künstler</th><th>Titel</th><th>Beatport</th><th>Quelle</th><th>Status</th><th>Notiz</th><th></th></tr></thead><tbody>
    ${rows.map((e) => `<tr data-k="${e.k}" class="ist-${e.status === "removed" ? "dropped" : e.status}">
      <td><input type="checkbox" data-cc ${CART.checked.has(e.k) ? "checked" : ""} aria-label="Markieren" ${editable ? "" : "disabled"}></td>
      <td class="ell" title="${esc(e.artist)}">${esc(e.artist)}</td>
      <td class="ell nm" title="${esc(e.title + (e.mix ? ` (${e.mix})` : ""))}"><b>${esc(e.title)}</b>${e.mix ? ` <span class="muted">(${esc(e.mix)})</span>` : ""}</td>
      <td class="sm nw">${cartsBpCell(e)}</td>
      <td class="sm nw ell" title="${esc(e.source || "")}">${esc(CART_SRC[e.src] || e.src || "")}${e.via ? ` – <span translate="no">${esc(e.via)}</span>` : ""}</td>
      <td class="sm nw"><span class="idea-st st-${e.status === "open" ? "buy" : e.status}" title="${esc(e.status === "bought" ? (e.bought === "ja" ? "Steht unter „Einkäufe“" : "Laut „Einkäufe“ gekauft am " + e.bought) : e.status === "lib" ? e.lib : e.status === "removed" ? "Aus der Einkaufsliste genommen: " + (CART_WHY[e.removed] || "") : "")}">${CART_STATUS[e.status] || e.status}${e.status === "removed" && e.removed !== "hand" ? ` – ${CART_WHY[e.removed] || ""}` : ""}</span></td>
      <td class="ell sm idea-note" data-a="note" title="${esc(e.note || "Notiz bearbeiten")}">${e.note ? esc(e.note) : '<span class="muted">＋</span>'}</td>
      <td class="d-acts"><div class="d-row"><button class="ghost sm" data-a="open" ${e.url ? "" : "disabled"} title="${esc(e.url ? "Beim Shop bzw. bei der Quelle öffnen" : "Kein Link")}">Öffnen</button>
        ${!editable ? "" : e.status === "removed" ? '<button class="icon-btn" data-a="restore" title="Zurück auf die Einkaufsliste">↺</button>' : '<button class="icon-btn" data-a="remove" title="Aus der Einkaufsliste nehmen">✕</button>'}
        <button class="icon-btn" data-a="menu" title="Weitere Aktionen" aria-haspopup="menu">⋯</button></div></td></tr>`).join("")}
    </tbody></table>`;
  cartsSelInfo();
}

function cartsSelInfo() {
  const n = CART.checked.size;
  $("#cartSel").hidden = !n;
  $("#cartSelN").textContent = n ? `${fmtN(n)} markiert` : "";
}

async function cartsDo(fn, ...args) {
  try { const d = await call(fn, ...args); cartsApply(d); return d; } catch (e) { toast(String(e.message || e)); return null; }
}

async function cartsNameDialog(title, value = "", label = "Speichern") {
  return modal({
    title, html: `<label for="cartNm">Name</label><input id="cartNm" class="inp" type="text" value="${esc(value)}" maxlength="120" style="width:100%" autofocus>`,
    buttons: [{ label: "Abbrechen", value: null }, { label, value: true, primary: true }],
    collect: (b) => { const v = $("#cartNm", b).value.trim(); if (!v) { $("#cartNm", b).focus(); return false; } return v; },
  });
}

/** #433: Vorschlag für neue Körbe – Warenkorb_JJJJ_MM_TT (vom Kern, gleiche Schreibweise in allen Sprachen) */
function cartsDefaultName() {
  if (CART.d && CART.d.new_name) return CART.d.new_name;
  const t = new Date(), p = (n) => String(n).padStart(2, "0");
  return `Warenkorb_${t.getFullYear()}_${p(t.getMonth() + 1)}_${p(t.getDate())}`;
}

/** Neuer Warenkorb – danach startet der Assistent automatisch (#435, Entscheid 1) */
async function cartsNew() {
  const n = await cartsNameDialog("Neuer Warenkorb", cartsDefaultName(), "Anlegen");
  if (!n) return;
  const d = await cartsDo("carts_create", n);
  if (d) cartsWizard();
}

function cartsListMenu(ev, id) {
  const c = CART.d.carts.find((x) => x.id === id); if (!c) return;
  ev.preventDefault();
  showMenu(ev.clientX, ev.clientY, [
    { label: "Umbenennen …", run: async () => { const n = await cartsNameDialog("Warenkorb umbenennen", c.name); if (n && n !== c.name) await cartsDo("carts_rename", id, n); } },
    ...(c.archived ? [] : c.status === "open" ? [{ label: "Als gekauft abschliessen …", run: () => cartsClose(c) }] : [{ label: "Wieder öffnen", run: () => cartsDo("carts_reopen", id) }]),
    { label: "Als Excel exportieren", run: () => cartsExport("xlsx", id) },
    { label: "Als CSV exportieren", run: () => cartsExport("csv", id) }, "-",
    c.archived ? { label: "Zurückholen", run: () => cartsDo("carts_archive", id, false) } : { label: "Archivieren …", run: () => cartsArchive(c) },
  ]);
}

async function cartsClose(c) {
  const ok = await dialog({ title: "Als gekauft abschliessen", text: `„${c.name}“ als gekauft abschliessen? Er bleibt unter „Gekauft (Historik)“ und lässt sich wieder öffnen. Sobald alle Titel unter „Einkäufe“ stehen, geschieht das auch von selbst.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Abschliessen", value: true, primary: true }] });
  if (ok) await cartsDo("carts_close", c.id);
}

async function cartsArchive(c) {
  const ok = await dialog({ title: "Warenkorb archivieren", text: `„${c.name}“ (${fmtN(c.count)} Titel) archivieren? Er verschwindet aus der Liste und lässt sich unter „Archiv“ zurückholen – gelöscht wird nichts.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Archivieren", value: true, primary: true }] });
  if (ok) { await cartsDo("carts_archive", c.id, true); status(`Warenkorb „${c.name}“ archiviert.`, "info"); }
}

// ---------------------------------------------------------------------- Vorschau-Tabelle (#435, #436)
/** Liste mit Häkchen; rows: [{artist, title, mix, on, why, extra}] → Tabelle; liefert HTML */
function cartsPvTable(rows, extraHead = "") {
  return `<div class="cart-pv"><table><thead><tr><th><input type="checkbox" data-pvall checked aria-label="Alle"></th><th>Künstler</th><th>Titel</th>${extraHead ? `<th>${extraHead}</th>` : ""}</tr></thead><tbody>
    ${rows.map((r, i) => `<tr class="${r.on ? "" : "pv-head"}"><td><input type="checkbox" data-pv="${i}" ${r.on ? "checked" : ""} aria-label="Übernehmen"></td>
      <td translate="no">${esc(r.artist || "")}</td><td translate="no"><b>${esc(r.title || "")}</b>${r.mix ? ` <span class="muted">(${esc(r.mix)})</span>` : ""}${r.why ? `<div class="why">${esc(r.why)}</div>` : ""}</td>${extraHead ? `<td class="sm">${r.extra || ""}</td>` : ""}</tr>`).join("")}</tbody></table></div>`;
}

function cartsPvBind(b, rows, countEl) {
  const upd = () => {
    const n = b.querySelectorAll("[data-pv]:checked").length;
    if (countEl) countEl(n);
    const all = b.querySelector("[data-pvall]"); if (all) all.checked = n === rows.length;
  };
  b.addEventListener("change", (ev) => {
    if (ev.target.matches("[data-pvall]")) b.querySelectorAll("[data-pv]").forEach((x) => { x.checked = ev.target.checked; });
    upd();
  });
  upd();
}

const cartsPvPicked = (b) => [...b.querySelectorAll("[data-pv]:checked")].map((x) => +x.dataset.pv);

/** #436: Vorschau einer eingefügten Trackliste – Titelzeile des Mixes ausmarkiert. → skip (Positionen) oder null */
async function tracklistPickDialog(text, title = "Vorschau") {
  let pv;
  try { pv = await call("tracklist_preview", text); } catch (e) { toast(String(e.message || e)); return null; }
  if (!pv.items.length) { await info(title, "Keine Titel erkannt – je Zeile „Künstler - Titel“."); return null; }
  const rows = pv.items.map((x) => ({ ...x, on: !x.head, why: x.head ? "vermutlich Titel des Mixes – nicht übernommen" : "" }));
  const pick = await modal({ title, wide: true,
    html: `<p class="muted sm" style="margin:0 0 6px">${fmtN(pv.items.length)} Zeilen erkannt${pv.unknown ? `, ${fmtN(pv.unknown)} unbekannte (ID) ausgelassen` : ""}${pv.heads ? `. Ausmarkiert: vermutlich der Titel des Mixes – bei Bedarf anwählen` : ""}. Nur angewählte Titel werden übernommen.</p>${cartsPvTable(rows)}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => cartsPvBind(b, rows, (n) => { const p = $("#mBtns .primary"); if (p) { p.textContent = `Übernehmen (${n})`; p.disabled = !n; } }),
    collect: (b) => cartsPvPicked(b) });
  if (!pick) return null;
  const on = new Set(pick);
  return rows.map((_r, i) => i).filter((i) => !on.has(i));
}

// ---------------------------------------------------------------------- Titel hinzufügen (#421, #434, #437, #424)
/** → true, wenn etwas übernommen wurde */
async function cartsAddDone(r) {
  status(`${fmtN(r.added)} Titel in „${r.name}“${r.dupes ? `, ${fmtN(r.dupes)} schon vorhanden` : ""}${r.unknown ? `, ${fmtN(r.unknown)} unbekannte (ID) ausgelassen` : ""}.`, "info");
  await cartsShow(r.cid);
  return r.added > 0;
}

/** #437: Anleitung je Quelle mit Link (öffnet nur die Webseite im Browser – TagStudio liest dort nichts aus) */
const CART_TXT_GUIDE = {
  "1001tracklists": { name: "1001Tracklists", url: "https://www.1001tracklists.com/",
    steps: ["Tracklist auf 1001tracklists.com öffnen.", "Die Titelliste markieren und kopieren.", "Hier einfügen."] },
  mixid: { name: "MixID", url: "https://www.mixid.fm/",
    steps: ["Mix auf mixid.fm öffnen (angemeldet).", "Tracklist mit der Maus markieren (Zeit, Künstler — Titel) und kopieren (Strg+C bzw. Cmd+C).", "Hier einfügen."] },
};

async function cartsText() {
  const text = await modal({
    title: "Liste einfügen", wide: true,
    html: `<div class="row" style="gap:8px;margin:0 0 8px;align-items:center"><label for="ctSrc">Quelle</label><select id="ctSrc" class="inp"><option value="1001tracklists">1001Tracklists</option><option value="mixid">MixID</option><option value="text">andere Quelle</option></select></div>
      <div class="hint"><div id="ctGuide"></div>
      <div class="muted sm" style="margin-top:4px">Auch eine Beatport-Chart oder eigene Notizen gehen – je Zeile „Künstler - Titel (Mix)“. Nummern, Zeitmarken und Labels in [eckigen Klammern] fallen weg, „ID - ID“ wird ausgelassen. Vor dem Übernehmen zeigt eine Vorschau alle erkannten Titel. TagStudio ruft dafür keine Webseite ab.</div></div>
      <textarea id="ctTxt" class="fe-val" style="width:100%;min-height:220px;font-family:var(--mono, monospace)" spellcheck="false" translate="no" autofocus placeholder="[01:54] Künstler - Titel (Extended Mix) [Label]"></textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Weiter zur Vorschau", value: true, primary: true }],
    onMount: (b) => {
      const guide = () => {
        const g = CART_TXT_GUIDE[$("#ctSrc", b).value], box = $("#ctGuide", b);
        box.hidden = !g;
        if (g) box.innerHTML = `<b>${esc(g.name)}:</b> ${g.steps.map((x, k) => `<span>${k + 1}.</span> <span>${esc(x)}</span>`).join(" ")} <a href="#" data-u="${esc(g.url)}" title="${esc(g.url)}">${esc(g.name)} öffnen ↗</a>`;
      };
      $("#ctSrc", b).addEventListener("change", guide);
      b.addEventListener("click", (ev) => { const a = ev.target.closest("[data-u]"); if (a) { ev.preventDefault(); call("open_url", a.dataset.u); } });
      guide();
      $("#ctTxt", b).focus();
    },
    collect: (b) => ({ text: $("#ctTxt", b).value, via: $("#ctSrc", b).value }),     // #438: gewählte Quelle
  });
  if (!text || !text.text.trim()) return false;
  const skip = await tracklistPickDialog(text.text, "Liste einfügen – Vorschau");
  if (skip === null) return false;
  try { return await cartsAddDone(await call("carts_add_text", CART.d.sel, text.text, CART.d.sel ? "" : cartsDefaultName(), skip, text.via)); }
  catch (e) { toast(String(e.message || e)); return false; }
}

/** #434/#435: Titel aus einer Wunschliste wählen (Vorschau mit Häkchen; offene angewählt) */
async function cartsIdeasDialog() {
  let d;
  try { d = await call("ideas_overview", ""); } catch (e) { toast(String(e.message || e)); return false; }
  if (!d.lists.length) { await info("Aus Ideen", "Noch keine Wunschliste – in „Ideen“ bzw. „Entdecken“ Titel merken."); return false; }
  const ST = { idea: "Idee", buy: "Kaufen", bought: "gekauft", lib: "in Bibliothek", dropped: "verworfen" };
  let cur = d;
  const rowsOf = (dd) => dd.items.map((e) => ({ artist: e.artist, title: e.title, mix: e.mix, k: e.k, on: e.status === "idea" || e.status === "buy",
    extra: esc(ST[e.status] || e.status) + (e.store === "beatport" && e.sid ? " · Beatport ✓" : "") }));
  const body = (dd) => `<div class="row" style="gap:8px;margin:0 0 8px;align-items:center"><label for="ciList">Wunschliste</label><select id="ciList" class="inp">${dd.lists.map((l) => `<option value="${esc(l.id)}" ${l.id === dd.sel ? "selected" : ""}>${esc(l.name)} (${fmtN(l.count)})</option>`).join("")}</select></div>
    <p class="muted sm" style="margin:0 0 6px">Angewählt sind offene Ideen (Idee, Kaufen); gekaufte, vorhandene und verworfene nur auf Wunsch. Übernommene Ideen bekommen den Status „Kaufen“.</p>
    <div id="ciTbl">${dd.items.length ? cartsPvTable(rowsOf(dd), "Status") : '<div class="muted sm">Diese Wunschliste ist leer.</div>'}</div>`;
  let rows = rowsOf(cur);
  const setCount = (n) => { const p = $("#mBtns .primary"); if (p) { p.textContent = `In den Warenkorb (${n})`; p.disabled = !n; } };
  const pick = await modal({ title: "Aus Ideen", wide: true, html: body(cur),
    buttons: [{ label: "Abbrechen", value: null }, { label: "In den Warenkorb", value: true, primary: true }],
    onMount: (b) => {
      cartsPvBind(b, rows, setCount);
      b.addEventListener("change", async (ev) => {
        if (ev.target.id !== "ciList") return;
        try { cur = await call("ideas_overview", ev.target.value); } catch (e) { return; }
        rows = rowsOf(cur);
        $("#ciTbl", b).innerHTML = cur.items.length ? cartsPvTable(rows, "Status") : '<div class="muted sm">Diese Wunschliste ist leer.</div>';
        setCount(b.querySelectorAll("[data-pv]:checked").length);
      });
    },
    collect: (b) => ({ pid: cur.sel, ks: cartsPvPicked(b).map((i) => rows[i].k) }) });
  if (!pick || !pick.ks.length) return false;
  try { return await cartsAddDone(await call("carts_from_ideas", pick.pid, pick.ks, CART.d.sel, CART.d.sel ? "" : cartsDefaultName())); }
  catch (e) { toast(String(e.message || e)); return false; }
}

async function cartsManual() {
  const res = await modal({
    title: "Titel von Hand",
    html: `<div class="frm"><label for="cmA">Künstler</label><input id="cmA" class="inp" type="text" autofocus>
      <label for="cmT">Titel</label><input id="cmT" class="inp" type="text">
      <label for="cmM">Mix</label><input id="cmM" class="inp" type="text" placeholder="z. B. Extended Mix">
      <label for="cmU">Link</label><input id="cmU" class="inp" type="url" placeholder="https://www.beatport.com/track/…">
      <label for="cmN">Notiz</label><input id="cmN" class="inp" type="text"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Hinzufügen", value: true, primary: true }],
    collect: (b) => ({ artist: $("#cmA", b).value, title: $("#cmT", b).value, mix: $("#cmM", b).value, url: $("#cmU", b).value, note: $("#cmN", b).value }),
  });
  if (!res) return false;
  try {
    const r = await call("carts_add_manual", CART.d.sel, res);
    toast(r.added ? "Titel hinzugefügt." : "Steht schon im Warenkorb.");
    await cartsShow(r.cid);
    return r.added > 0;
  } catch (e) { toast(String(e.message || e)); return false; }
}

/** #424: Titel eines Links (Beatport, Spotify, SoundCloud) lesen, Vorschau, übernehmen */
async function cartsUrl() {
  const url = await modal({ title: "Per Link",
    html: `<p class="muted sm" style="margin:0 0 6px">Link einer Playlist, eines Albums bzw. Releases, einer Chart oder eines Titels einfügen – <b>Beatport</b>, <b>Spotify</b> oder <b>SoundCloud</b>. Gelesen wird über das jeweilige Plugin (angemeldet), nur lesend; vor dem Übernehmen zeigt eine Vorschau alle Titel.</p>
      <input id="cuUrl" class="inp" type="url" style="width:100%" placeholder="https://www.beatport.com/chart/…/123456" autofocus spellcheck="false">`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Titel lesen", value: true, primary: true }],
    collect: (b) => { const v = $("#cuUrl", b).value.trim(); if (!v) { $("#cuUrl", b).focus(); return false; } return v; } });
  if (!url) return false;
  const r = await runTask(call("start_carts_url", url), "Titel aus dem Link lesen");
  if (!r || r.cancelled) return false;
  if (!r.items.length) { await info("Per Link", `${r.plugin}: keine Titel gefunden.`); return false; }
  const rows = r.items.map((x) => ({ ...x, on: true, extra: x.sid ? "Beatport ✓" : "" }));
  const pick = await modal({ title: `Per Link – ${r.name || r.plugin}`, wide: true,
    html: `<p class="muted sm" style="margin:0 0 6px">${fmtN(rows.length)} Titel von ${esc(r.plugin)}. Nur angewählte werden übernommen.</p>${cartsPvTable(rows, "Beatport")}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => cartsPvBind(b, rows, (n) => { const p = $("#mBtns .primary"); if (p) { p.textContent = `Übernehmen (${n})`; p.disabled = !n; } }),
    collect: (b) => cartsPvPicked(b).map((i) => r.items[i]) });
  if (!pick || !pick.length) return false;
  try { return await cartsAddDone(await call("carts_add_refs", CART.d.sel, pick, CART.d.sel ? "" : cartsDefaultName(), r.plugin)); }
  catch (e) { toast(String(e.message || e)); return false; }
}

function cartsMoreMenu() {
  const b = $("#cartMore").getBoundingClientRect(), c = cartsCur(), open = c && c.status === "open" && !c.archived;
  showMenu(b.left, b.bottom + 6, [
    ...(open ? [{ label: "Unsichere und nicht gefundene neu suchen …", run: () => cartsMatch(true) },
      { label: "Gekaufte entfernen …", run: cartsRemoveBought },
      { label: "Als gekauft abschliessen …", run: () => cartsClose(c) }] : []),
    ...(c && !open && !c.archived ? [{ label: "Wieder öffnen", run: () => cartsDo("carts_reopen", c.id) }] : []),
    ...(c && c.pushed && c.pushed.url ? [{ label: "Playlist bei Beatport öffnen", run: () => call("open_url", c.pushed.url) }] : []),
    ...(c ? ["-", { label: "Diesen Warenkorb als Excel", run: () => cartsExport("xlsx", c.id) }, { label: "Diesen Warenkorb als CSV", run: () => cartsExport("csv", c.id) }] : []),
    { label: "Alle Warenkörbe als Excel", run: () => cartsExport("xlsx", "") }, "-",
    ...(CART.d.undo ? [{ label: "Rückgängig", run: async () => { const d = await cartsDo("carts_undo", CART.d.sel); if (d) status(d.message, "info"); } }] : []),
    ...(c ? [{ label: "Warenkorb umbenennen …", run: async () => { const n = await cartsNameDialog("Warenkorb umbenennen", c.name); if (n && n !== c.name) await cartsDo("carts_rename", c.id, n); } },
      c.archived ? { label: "Zurückholen", run: () => cartsDo("carts_archive", c.id, false) } : { label: "Warenkorb archivieren …", run: () => cartsArchive(c) }] : []),
  ]);
}

async function cartsExport(fmt, cid) {
  const r = await call("carts_export", fmt, cid);
  if (r && r.ok) status(r.message, "info"); else if (r && r.error) toast(r.error);
}

async function cartsRemove(ks) {
  const ok = await dialog({ title: "Aus der Einkaufsliste nehmen", text: `${fmtN(ks.length)} Titel aus der Einkaufsliste nehmen? Sie bleiben unter „Entfernt“ im Warenkorb und lassen sich zurückholen; Rückgängig ist möglich.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Herausnehmen", value: true, primary: true }] });
  if (!ok) return;
  CART.checked.clear();
  await cartsDo("carts_remove", CART.d.sel, ks);
}

/** #422/#435: gekaufte und vorhandene Titel – Vorschau mit Häkchen, dann aus der Einkaufsliste nehmen */
async function cartsRemoveBought() {
  const c = cartsCur(); if (!c) return false;
  const found = (CART.d.items || []).filter((e) => e.status === "bought" || e.status === "lib");
  if (!found.length) { await info("Gekaufte entfernen", c.checked ? "Auf der Einkaufsliste steht kein bereits gekaufter Titel." : "Kein gekaufter Titel bekannt – zuerst „Auf Käufe prüfen“."); return false; }
  const rows = found.map((e) => ({ artist: e.artist, title: e.title, mix: e.mix, on: true,
    extra: esc(e.status === "bought" ? (e.bought && e.bought !== "ja" ? `gekauft am ${e.bought}` : "gekauft") : "in Bibliothek") }));
  const pick = await modal({ title: "Gekaufte entfernen", wide: true,
    html: `<p class="muted sm" style="margin:0 0 6px">${fmtN(found.length)} Titel sind bereits gekauft bzw. schon in der Bibliothek und würden doppelt gekauft. Angewählte werden aus der Einkaufsliste genommen; sie bleiben unter „Entfernt“ sichtbar, Rückgängig ist möglich.</p>${cartsPvTable(rows, "Status")}`,
    buttons: [{ label: "Behalten", value: null }, { label: "Aus Einkaufsliste nehmen", value: true, primary: true }],
    onMount: (b) => cartsPvBind(b, rows, (n) => { const p = $("#mBtns .primary"); if (p) { p.textContent = `Aus Einkaufsliste nehmen (${n})`; p.disabled = !n; } }),
    collect: (b) => cartsPvPicked(b).map((i) => found[i].k) });
  if (!pick || !pick.length) return false;
  const d = await cartsDo("carts_remove_bought", c.id, pick);
  if (d) status(`${fmtN(d.removed_n)} bereits gekaufte Titel aus der Einkaufsliste genommen.`, "info");
  return !!d;
}

/** #422/#435: zuerst zeigen, was geprüft wird; dann Einkäufe aktualisieren und abgleichen; danach gekaufte zur Auswahl */
async function cartsCheck() {
  const c = cartsCur(); if (!c) return false;
  const n = (CART.d.items || []).filter((e) => e.status !== "removed").length;
  const bp = CART.d.beatport || {};
  const ok = await dialog({ title: "Auf Käufe prüfen",
    text: `${fmtN(n)} Titel dieses Warenkorbs werden geprüft:\n\n• ${bp.available ? "Einkäufe bei Beatport aktualisieren (nur neue Käufe, nur lesend)" : "Beatport ist nicht angemeldet – geprüft wird gegen die gespeicherten Einkäufe"}\n• mit „Einkäufe“ abgleichen (gleiche Beatport-ID bzw. Künstler + Titel + Mix)\n• ${CART.d.library ? "mit der Bibliothek abgleichen (sichere Treffer)" : "Bibliothek: keine festgelegt – wird ausgelassen"}\n\nEs wird nichts entfernt; danach kannst du gekaufte Titel aus der Einkaufsliste nehmen.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Prüfen", value: true, primary: true }] });
  if (!ok) return false;
  const r = await runTask(call("start_carts_check", CART.d.sel), "Warenkorb auf Käufe prüfen");
  if (!r) return false;
  await cartsShow();
  const parts = [`${fmtN(r.bought)} bereits gekauft`, r.library ? `${fmtN(r.lib)} in der Bibliothek` : "Bibliothek nicht geprüft (keine festgelegt)"];
  status(`Geprüft: ${parts.join(", ")}.${(r.errors || []).length ? " " + r.errors.join(" ") : ""}`, r.errors && r.errors.length ? "warn" : "info");
  if ((CART.d.items || []).some((e) => e.status === "bought" || e.status === "lib")) await cartsRemoveBought();
  return true;
}

/** #423/#435: zuerst zeigen, welche Titel gesucht werden; danach unsichere direkt wählen */
async function cartsMatch(again) {
  const c = cartsCur(); if (!c) return false;
  const bp = CART.d.beatport || {};
  if (!bp.available) { await info("Bei Beatport suchen", "Das Beatport-Plugin ist aus oder nicht angemeldet (Plugins › Beatport)."); return false; }
  const todo = (CART.d.items || []).filter((e) => e.status === "open" && !e.sid && !e.hand && (again || !e.match));
  if (!todo.length) { await info("Bei Beatport suchen", "Alle Titel der Einkaufsliste sind schon zugeordnet (bzw. als „nicht gefunden“ markiert – über „Weitere ▾“ neu suchen)."); return false; }
  const ok = await modal({ title: "Bei Beatport suchen", wide: true,
    html: `<p class="muted sm" style="margin:0 0 6px">${fmtN(todo.length)} Titel ohne Beatport-ID werden in der Beatport-Suche nachgeschlagen (nur lesend, dein Konto wird nicht verändert). Sichere Treffer werden zugeordnet, bei unsicheren wählst du danach selbst.</p>
      <div class="cart-pv"><table><tbody>${todo.map((e) => `<tr><td translate="no">${esc(e.artist)}</td><td translate="no"><b>${esc(e.title)}</b>${e.mix ? ` <span class="muted">(${esc(e.mix)})</span>` : ""}</td></tr>`).join("")}</tbody></table></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Suchen", value: true, primary: true }] });
  if (!ok) return false;
  const r = await runTask(call("start_carts_bp_match", CART.d.sel, !!again), "Warenkorb: bei Beatport suchen");
  if (!r) return false;
  await cartsShow();
  status(`${fmtN(r.searched)} gesucht: ${fmtN(r.sure)} sicher zugeordnet, ${fmtN(r.unsure)} unsicher (bitte wählen), ${fmtN(r.none)} nicht gefunden.`, "info");
  const unsure = (CART.d.items || []).filter((e) => e.match === "unsure" && (e.cands || []).length);
  if (unsure.length) await cartsPickMany(unsure, r);
  return true;
}

/** #435: alle unsicheren Treffer in einem Fenster wählen */
async function cartsPickMany(list, r) {
  const opt = (e) => `<select class="inp sm" data-pk="${e.k}">${e.cands.map((c, i) => `<option value="${i}">${esc(c.artist || "")} – ${esc(c.title || "")}${c.mix ? ` (${esc(c.mix)})` : ""} · ${Math.round((c.score || 0) * 100)} %</option>`).join("")}<option value="-1">Keiner davon – nicht bei Beatport</option></select>`;
  const pick = await modal({ title: "Beatport-Treffer wählen", wide: "xl",
    html: `<p class="muted sm" style="margin:0 0 6px">${r ? `${fmtN(r.sure)} sicher zugeordnet, ${fmtN(r.none)} nicht gefunden. ` : ""}Für ${fmtN(list.length)} Titel gibt es mehrere mögliche Treffer – bitte wählen (vorgewählt ist der beste).</p>
      <div class="cart-pv"><table><tbody>${list.map((e) => `<tr><td translate="no">${esc(e.artist)} – <b>${esc(e.title)}</b>${e.mix ? ` <span class="muted">(${esc(e.mix)})</span>` : ""}</td><td>${opt(e)}</td></tr>`).join("")}</tbody></table></div>`,
    buttons: [{ label: "Später", value: null }, { label: "Übernehmen", value: true, primary: true }],
    collect: (b) => Object.fromEntries([...b.querySelectorAll("[data-pk]")].map((s) => [s.dataset.pk, +s.value])) });
  if (!pick) return;
  await cartsDo("carts_pick_many", CART.d.sel, pick);
}

async function cartsPick(e) {
  const pick = await modal({ title: "Beatport-Treffer wählen", wide: true,
    html: `<p class="muted sm" style="margin:0 0 6px" translate="no">${esc(e.artist)} – ${esc(e.title)}${e.mix ? ` (${esc(e.mix)})` : ""}</p>
      <div class="ab-list">${(e.cands || []).map((c, i) => `<label class="check sm"><input type="radio" name="cpk" value="${i}" ${i === 0 ? "checked" : ""}> <span translate="no">${esc(c.artist || "")} – ${esc(c.title || "")}${c.mix ? ` (${esc(c.mix)})` : ""}</span> <span class="muted">${Math.round((c.score || 0) * 100)} %</span>${c.url ? ` <a href="#" data-u="${esc(c.url)}">ansehen ↗</a>` : ""}</label>`).join("")}
      <label class="check sm"><input type="radio" name="cpk" value="-1"> Keiner davon – nicht bei Beatport</label></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => b.addEventListener("click", (ev) => { const a = ev.target.closest("[data-u]"); if (a) { ev.preventDefault(); call("open_url", a.dataset.u); } }),
    collect: (b) => +((b.querySelector('input[name="cpk"]:checked') || {}).value ?? -1) });
  if (pick === null || pick === undefined) return;
  await cartsDo("carts_pick", CART.d.sel, e.k, pick);
}

/** #423/#435: Einkaufsliste als Beatport-Playlist TagStudio_CART_<Korb> – Vorschau mit allen Titeln, nur auf Klick */
async function cartsBeatport() {
  const pv = await call("carts_bp_preview", CART.d.sel);
  if (!pv.available || !pv.write) {
    await info("An Beatport senden", !pv.available ? "Das Beatport-Plugin ist aus oder nicht angemeldet (Plugins › Beatport)."
      : "Im Beatport-Plugin unter „Einstellungen …“ zuerst „Playlists in Beatport schreiben“ einschalten.");
    return false;
  }
  if (!pv.count) { await info("An Beatport senden", `Auf der Einkaufsliste steht kein Titel mit Beatport-ID${pv.without ? ` (${fmtN(pv.without)} ohne Zuordnung)` : ""} – zuerst „Bei Beatport suchen“.`); return false; }
  const send = (CART.d.items || []).filter((e) => e.status === "open" && e.sid), left = (CART.d.items || []).filter((e) => e.status === "open" && !e.sid);
  const ok = await modal({ title: "An Beatport senden", wide: true,
    html: `<p style="margin:0 0 6px">In deinem Beatport-Konto die Playlist <b translate="no">${esc(pv.name)}</b> ${pv.pushed && pv.pushed.id ? "abgleichen" : "anlegen"}: ${fmtN(pv.count)} Titel der Einkaufsliste.</p>
      <div class="cart-pv"><table><tbody>${send.map((e) => `<tr><td translate="no">${esc(e.artist)}</td><td translate="no"><b>${esc(e.title)}</b>${e.mix ? ` <span class="muted">(${esc(e.mix)})</span>` : ""}</td><td class="sm">✓ ${esc(e.sid)}</td></tr>`).join("")}</tbody></table></div>
      <p class="muted sm" style="margin:6px 0 0">${pv.without ? `${fmtN(pv.without)} Titel ohne Beatport-ID bleiben aussen vor${left.length ? `: ${left.slice(0, 5).map((e) => esc(`${e.artist} – ${e.title}`)).join("; ")}${left.length > 5 ? " …" : ""}` : ""}. ` : ""}${pv.bought ? `${fmtN(pv.bought)} bereits gekaufte werden nicht gesendet. ` : ""}Vorher werden die Einkäufe noch einmal geprüft. Die Playlist enthält danach genau die Einkaufsliste; andere Playlists bleiben unberührt. Es wird nichts gekauft – auf beatport.com „Alle in den Warenkorb“ und dort bezahlen.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "An Beatport senden", value: true, primary: true }] });
  if (!ok) return false;
  const r = await runTask(call("start_carts_bp", CART.d.sel), "Beatport – Warenkorb");
  if (!r) return false;
  await cartsShow();
  const go = await dialog({ title: "An Beatport gesendet",
    text: `${r.name}: ${fmtN(r.count)} Titel${r.created ? " (neu angelegt)" : ""}.${r.bought ? ` ${fmtN(r.bought)} bereits gekaufte ausgelassen.` : ""}${r.note ? " " + r.note : ""}\n\nAuf beatport.com die Playlist öffnen, „Alle in den Warenkorb“ wählen und dort bezahlen. Danach erkennt „Einkäufe“ die Käufe, und der Warenkorb wird als gekauft abgeschlossen.`,
    buttons: [{ label: "OK", value: null }, ...(r.url ? [{ label: "Playlist bei Beatport öffnen", value: true, primary: true }] : [])] });
  if (go && r.url) call("open_url", r.url);
  return true;
}

// ---------------------------------------------------------------------- #435 Assistent
const CART_WZ = [
  ["add", "Titel hinzufügen", "Titel für diesen Warenkorb sammeln. Jeder Weg zeigt vor dem Übernehmen eine Vorschau."],
  ["match", "Bei Beatport suchen", "Titel ohne Beatport-ID werden in der Beatport-Suche nachgeschlagen (nur lesend). Vorher siehst du die Liste, danach wählst du unsichere Treffer."],
  ["check", "Auf Käufe prüfen", "Einkäufe aktualisieren und mit „Einkäufe“ und der Bibliothek abgleichen. Danach kannst du bereits gekaufte Titel aus der Einkaufsliste nehmen."],
  ["send", "An Beatport senden", "Die Einkaufsliste wird als Playlist in deinem Beatport-Konto angelegt – erst nach der Vorschau und deinem Klick auf „An Beatport senden“."],
  ["buy", "Kaufen", "Auf beatport.com die Playlist öffnen, „Alle in den Warenkorb“ wählen und dort bezahlen. Danach erkennt „Einkäufe“ die Käufe und schliesst den Warenkorb ab."],
];

async function cartsWizard() {
  let i = 0;
  for (;;) {
    const c = cartsCur();
    if (!c || c.status !== "open" || c.archived) return;
    const [id, title, text] = CART_WZ[i], n = c.counts || {};
    const stat = `${fmtN(n.open || 0)} auf der Einkaufsliste · ${fmtN(c.no_id || 0)} ohne Beatport-ID · ${fmtN(c.unsure || 0)} unsicher · ${fmtN(n.bought || 0)} gekauft${c.pushed ? ` · gesendet am ${cartsDate(c.pushed.at)}` : ""}`;
    let choice = "";
    const acts = id === "add" ? `<div class="cart-wz-acts"><button class="ghost" data-wz="text">Liste einfügen …</button><button class="ghost" data-wz="ideas">Aus Ideen …</button><button class="ghost" data-wz="manual">Von Hand …</button><button class="ghost" data-wz="url">Per Link …</button></div>`
      : id === "buy" && c.pushed && c.pushed.url ? `<div class="cart-wz-acts"><button class="ghost" data-wz="openbp">Playlist bei Beatport öffnen ↗</button></div>` : "";
    const primary = { add: "Weiter", match: "Bei Beatport suchen …", check: "Auf Käufe prüfen …", send: "An Beatport senden …", buy: "Fertig" }[id];
    const v = await modal({ title: `Assistent – ${c.name}`, wide: true,
      html: `<div class="cart-wz-steps">${CART_WZ.map((s, k) => `<span class="${k === i ? "on" : k < i ? "done" : ""}">${k + 1}. ${esc(s[1])}</span>`).join("")}</div>
        <h3 style="margin:0 0 6px">Schritt ${i + 1} von ${CART_WZ.length}: ${esc(title)}</h3><p style="margin:0 0 6px">${esc(text)}</p>
        <div class="muted sm">${esc(stat)}</div>${acts}`,
      buttons: [{ label: "Abbrechen", value: null }, ...(i > 0 ? [{ label: "Zurück", value: "back" }] : []), ...(i < CART_WZ.length - 1 ? [{ label: "Überspringen", value: "skip" }] : []),
        { label: primary, value: "run", primary: true }],
      onMount: (b) => b.addEventListener("click", (ev) => {
        const a = ev.target.closest("[data-wz]"); if (!a) return;
        choice = a.dataset.wz;
        const p = $("#mBtns .primary"); if (p) p.click();
      }),
      collect: (_b, val) => choice || val });
    if (v === null || v === undefined) return;
    if (v === "back") { i = Math.max(0, i - 1); continue; }
    if (v === "skip") { i++; continue; }
    if (v === "openbp") { if (c.pushed && c.pushed.url) call("open_url", c.pushed.url); continue; }
    if (["text", "ideas", "manual", "url"].includes(v)) {
      await ({ text: cartsText, ideas: cartsIdeasDialog, manual: cartsManual, url: cartsUrl })[v]();
      continue;                                          // im Schritt bleiben – weitere Titel oder „Weiter“
    }
    if (id === "add") { i++; continue; }
    if (id === "buy") return;
    const done = await ({ match: () => cartsMatch(false), check: cartsCheck, send: cartsBeatport })[id]();
    if (done) i++;
  }
}

async function cartsNote(e) {
  const v = await modal({ title: "Notiz", html: `<div class="muted sm" style="margin-bottom:6px">${esc(e.artist)} – ${esc(e.title)}</div><textarea id="cnTxt" class="fe-val" style="width:100%;min-height:90px" maxlength="1000" autofocus>${esc(e.note || "")}</textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }], collect: (b) => $("#cnTxt", b).value });
  if (v === null || v === undefined) return;
  await cartsDo("carts_note", CART.d.sel, e.k, v);
}

function cartsRowMenu(ev, e) {
  ev.preventDefault();
  const c = cartsCur(), editable = c && c.status === "open" && !c.archived;
  const ks = CART.checked.has(e.k) && CART.checked.size > 1 ? [...CART.checked] : [e.k];
  const items = [];
  if (ks.length === 1) {
    if (e.url) items.push({ label: "Beim Shop bzw. bei der Quelle öffnen", run: () => call("open_url", e.url) });
    if (editable && (e.cands || []).length) items.push({ label: "Beatport-Treffer wählen …", run: () => cartsPick(e) });
    items.push({ label: "Notiz …", run: () => cartsNote(e) });
    const ws = typeof webSearchItem === "function" ? webSearchItem(ev, e.artist, e.title, e.mix) : null;
    if (ws) items.push(ws);
  }
  if (editable) {
    if (items.length) items.push("-");
    items.push(e.status === "removed" ? { label: "Zurück auf die Einkaufsliste", run: () => cartsDo("carts_restore", CART.d.sel, ks) }
      : { label: ks.length > 1 ? `${fmtN(ks.length)} aus der Einkaufsliste nehmen …` : "Aus der Einkaufsliste nehmen …", run: () => cartsRemove(ks) });
  }
  if (items.length) showMenu(ev.clientX, ev.clientY, items);
}

/** „In den Warenkorb ▸“ aus den Ideen (#421): offenen Korb wählen (zuletzt benutzter zuerst) oder neuen anlegen */
async function cartsFromIdeasMenu(ev, pid, ks, after) {
  if (!ks.length) { toast("Bitte zuerst Einträge markieren."); return; }
  let d;
  try { d = await call("carts_overview", "", false); } catch (e) { toast(String(e.message || e)); return; }
  const save = async (cid, name) => {
    try {
      const r = await call("carts_from_ideas", pid, ks, cid, name);
      toast(r.added ? `${fmtN(r.added)} Titel in „${r.name}“${r.dupes ? `, ${fmtN(r.dupes)} schon dort` : ""}.` : `Steht schon in „${r.name}“.`);
      cartsBadge();
      if (after) after(r);
    } catch (e) { toast(String(e.message || e)); }
  };
  const items = d.carts.filter((c) => c.status === "open" && !c.archived).map((c) => ({ label: `${c.name}${c.id === d.sel ? " ✓" : ""}`, run: () => save(c.id, "") }));
  if (items.length) items.push("-");
  items.push({ label: "Neuer Warenkorb …", run: async () => { const n = await cartsNameDialog("Neuer Warenkorb", d.new_name || cartsDefaultName(), "Anlegen und hinzufügen"); if (n) save("", n); } });
  const r = ev.target && ev.target.getBoundingClientRect ? ev.target.getBoundingClientRect() : { left: 0, bottom: 0 };
  setTimeout(() => showMenu(ev.clientX || r.left, ev.clientY || r.bottom, items), 0);
}

async function cartsBadge(n) {
  if (n === undefined) { try { n = await call("carts_count"); } catch (e) { return; } }
  const el = $("#cartCount"); if (el) el.textContent = n ? String(n) : "";
}

(function bindCarts() {
  setTimeout(() => cartsBadge(), 9500);
  $("#cartLists").addEventListener("click", (ev) => {
    if (ev.target.closest("#cartNew")) { cartsNew(); return; }
    if (ev.target.closest("#cartArchToggle")) { CART.showArchived = !CART.showArchived; cartsShow(); return; }
    const b = ev.target.closest("[data-c]"); if (!b) return;
    cartsShow(b.dataset.c);
  });
  $("#cartLists").addEventListener("contextmenu", (ev) => { const b = ev.target.closest("[data-c]"); if (b) cartsListMenu(ev, b.dataset.c); });
  $("#cartFilter").addEventListener("click", (e) => { const b = e.target.closest("[data-f]"); if (!b) return; CART.filter = b.dataset.f; cartsApply(CART.d); });
  $("#cartSearch").addEventListener("input", () => CART.d && cartsRender());
  $("#cartAddText").addEventListener("click", cartsText);                 // #434: einzelne Knöpfe
  $("#cartAddIdeas").addEventListener("click", cartsIdeasDialog);
  $("#cartAddManual").addEventListener("click", cartsManual);
  $("#cartAddUrl").addEventListener("click", cartsUrl);                   // #424
  $("#cartWizard").addEventListener("click", cartsWizard);                // #435
  $("#cartMore").addEventListener("click", (e) => { e.stopPropagation(); cartsMoreMenu(); });
  $("#cartMatch").addEventListener("click", () => cartsMatch(false));
  $("#cartCheck").addEventListener("click", cartsCheck);
  $("#cartBp").addEventListener("click", cartsBeatport);
  $("#cartHint").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-h]"); if (!b) return;
    const c = cartsCur(); if (!c) return;
    if (b.dataset.h === "rmbought") cartsRemoveBought();
    if (b.dataset.h === "reopen") cartsDo("carts_reopen", c.id);
    if (b.dataset.h === "unarch") cartsDo("carts_archive", c.id, false);
  });
  $("#cartSelRemove").addEventListener("click", () => cartsRemove([...CART.checked]));
  $("#cartSelRestore").addEventListener("click", async () => { const ks = [...CART.checked]; CART.checked.clear(); await cartsDo("carts_restore", CART.d.sel, ks); });
  $("#cartSelNone").addEventListener("click", () => { CART.checked.clear(); cartsRender(); });
  $("#cartList").addEventListener("change", (ev) => {
    if (ev.target.id === "cartAll") {
      cartsRows().forEach((e) => (ev.target.checked ? CART.checked.add(e.k) : CART.checked.delete(e.k)));
      cartsRender();
      return;
    }
    if (ev.target.matches("[data-cc]")) {
      const k = +ev.target.closest("tr").dataset.k;
      if (ev.target.checked) CART.checked.add(k); else CART.checked.delete(k);
      cartsSelInfo();
    }
  });
  $("#cartList").addEventListener("contextmenu", (ev) => {
    const tr = ev.target.closest("tr[data-k]"); if (!tr) return;
    const e = CART.d.items.find((x) => x.k === +tr.dataset.k); if (e) cartsRowMenu(ev, e);
  });
  $("#cartList").addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-a]"); if (!b) return;
    ev.preventDefault();
    const k = +b.closest("tr").dataset.k, e = CART.d.items.find((x) => x.k === k); if (!e) return;
    const a = b.dataset.a;
    if (a === "open") return e.url && call("open_url", e.url);
    if (a === "note") return cartsNote(e);
    if (a === "menu") return cartsRowMenu(ev, e);
    if (a === "pick") return cartsPick(e);
    if (a === "remove") return cartsRemove([k]);
    if (a === "restore") return cartsDo("carts_restore", CART.d.sel, [k]);
  });
})();
