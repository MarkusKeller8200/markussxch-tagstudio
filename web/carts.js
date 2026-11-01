/* MarKusSXCH TagStudio – Warenkorb (#420–#423): Titel zum Kaufen in Warenkörben sammeln (Liste einfügen, aus Ideen,
   von Hand), auf bereits gekaufte prüfen, bei Beatport zuordnen und die Einkaufsliste als Playlist TagStudio_CART_…
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
  ["#cartAdd", "#cartMatch", "#cartCheck", "#cartBp"].forEach((s) => ($(s).disabled = !open));
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
    else if (c.no_id && c.counts.open) parts.push(`${fmtN(c.no_id)} Titel ohne Beatport-Zuordnung – „Bei Beatport suchen“.`);
  }
  box.innerHTML = parts.map((p) => `<div>${p}</div>`).join("");
  box.hidden = !parts.length;
}

function cartsRows() {
  const q = ($("#cartSearch").value || "").toLowerCase().trim(), f = CART.filter;
  return CART.d.items.filter((e) => (f === "all" || e.status === f) && (!q || `${e.artist} ${e.title} ${e.mix} ${e.note}`.toLowerCase().includes(q)));
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
    box.innerHTML = `<div class="tg-empty">${CART.d.items.length ? "Nichts in dieser Ansicht." : "Dieser Warenkorb ist leer – „+ Hinzufügen ▾“ (z. B. eine Trackliste einfügen) oder in „Ideen“ „In den Warenkorb ▸“."}</div>`;
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
      <td class="sm nw">${esc(CART_SRC[e.src] || e.src || "")}</td>
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

function cartsDefaultName() { return `Warenkorb ${new Date().toLocaleDateString()}`; }

async function cartsNew() {
  const n = await cartsNameDialog("Neuer Warenkorb", cartsDefaultName(), "Anlegen");
  if (n) await cartsDo("carts_create", n);
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

function cartsAddMenu() {
  const b = $("#cartAdd").getBoundingClientRect();
  showMenu(b.left, b.bottom + 6, [
    { label: "Liste einfügen (z. B. 1001Tracklists) …", run: cartsText },
    { label: "Titel von Hand …", run: cartsManual },
    { label: "Aus Ideen …", run: () => setModule("ideas") },
  ]);
}

async function cartsText() {
  const text = await modal({
    title: "Liste einfügen",
    html: `<p class="muted sm" style="margin:0 0 6px">Je Zeile „Künstler - Titel (Mix)“ – z. B. die kopierte Trackliste von 1001Tracklists, MixID oder eigene Notizen. Nummern, Zeitmarken und Labels in [eckigen Klammern] fallen weg; „ID - ID“ wird ausgelassen.</p><textarea id="ctTxt" class="fe-val" style="width:100%;min-height:220px" spellcheck="false" autofocus></textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    collect: (b) => $("#ctTxt", b).value,
  });
  if (!text || !text.trim()) return;
  try {
    const r = await call("carts_add_text", CART.d.sel, text, CART.d.sel ? "" : cartsDefaultName());
    status(`${fmtN(r.added)} Titel in „${r.name}“${r.dupes ? `, ${fmtN(r.dupes)} schon vorhanden` : ""}${r.unknown ? `, ${fmtN(r.unknown)} unbekannte (ID) ausgelassen` : ""}.`, "info");
    await cartsShow(r.cid);
  } catch (e) { toast(String(e.message || e)); }
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
  if (!res) return;
  try {
    const r = await call("carts_add_manual", CART.d.sel, res);
    toast(r.added ? "Titel hinzugefügt." : "Steht schon im Warenkorb.");
    await cartsShow(r.cid);
  } catch (e) { toast(String(e.message || e)); }
}

function cartsMoreMenu() {
  const b = $("#cartMore").getBoundingClientRect(), c = cartsCur(), open = c && c.status === "open" && !c.archived;
  showMenu(b.left, b.bottom + 6, [
    ...(open ? [{ label: "Unsichere und nicht gefundene neu suchen", run: () => cartsMatch(true) },
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

/** #422: gekaufte und in der Bibliothek vorhandene Titel aus der Einkaufsliste nehmen – nach Rückfrage */
async function cartsRemoveBought() {
  const c = cartsCur(); if (!c) return;
  const n = (CART.d.items || []).filter((e) => e.status === "bought" || e.status === "lib").length;
  if (!n) { await info("Gekaufte entfernen", c.checked ? "Auf der Einkaufsliste steht kein bereits gekaufter Titel." : "Kein gekaufter Titel bekannt – zuerst „Auf Käufe prüfen“."); return; }
  const ok = await dialog({ title: "Gekaufte entfernen", text: `${fmtN(n)} Titel sind bereits gekauft bzw. schon in der Bibliothek. Aus der Einkaufsliste nehmen? Sie bleiben unter „Entfernt“ sichtbar; Rückgängig ist möglich.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Entfernen", value: true, primary: true }] });
  if (!ok) return;
  const d = await cartsDo("carts_remove_bought", c.id);
  if (d) status(`${fmtN(d.removed_n)} bereits gekaufte Titel aus der Einkaufsliste genommen.`, "info");
}

/** #422: Einkäufe aktualisieren, dann mit „Einkäufe“ und der Bibliothek abgleichen */
async function cartsCheck() {
  const r = await runTask(call("start_carts_check", CART.d.sel), "Warenkorb auf Käufe prüfen");
  if (!r) return;
  await cartsShow();
  const parts = [`${fmtN(r.bought)} bereits gekauft`, r.library ? `${fmtN(r.lib)} in der Bibliothek` : "Bibliothek nicht geprüft (keine festgelegt)"];
  status(`Geprüft: ${parts.join(", ")}.${(r.errors || []).length ? " " + r.errors.join(" ") : ""}`, r.errors && r.errors.length ? "warn" : "info");
  if (r.bought + r.lib) cartsRemoveBought();
}

/** #423: Titel ohne Beatport-ID zuordnen (nur lesend) */
async function cartsMatch(again) {
  const r = await runTask(call("start_carts_bp_match", CART.d.sel, !!again), "Warenkorb: bei Beatport suchen");
  if (!r) return;
  status(`${fmtN(r.searched)} gesucht: ${fmtN(r.sure)} sicher zugeordnet, ${fmtN(r.unsure)} unsicher (bitte wählen), ${fmtN(r.none)} nicht gefunden.`, "info");
  cartsShow();
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

/** #423: Einkaufsliste als Beatport-Playlist TagStudio_CART_<Korb> – nur auf Klick (W2) */
async function cartsBeatport() {
  const pv = await call("carts_bp_preview", CART.d.sel);
  if (!pv.available || !pv.write) {
    await info("An Beatport senden", !pv.available ? "Das Beatport-Plugin ist aus oder nicht angemeldet (Plugins › Beatport)."
      : "Im Beatport-Plugin unter „Einstellungen …“ zuerst „Playlists in Beatport schreiben“ einschalten.");
    return;
  }
  if (!pv.count) { await info("An Beatport senden", `Auf der Einkaufsliste steht kein Titel mit Beatport-ID${pv.without ? ` (${fmtN(pv.without)} ohne Zuordnung)` : ""} – zuerst „Bei Beatport suchen“.`); return; }
  const ok = await dialog({ title: "An Beatport senden",
    text: `In deinem Beatport-Konto die Playlist „${pv.name}“ ${pv.pushed && pv.pushed.id ? "abgleichen" : "anlegen"}: ${fmtN(pv.count)} Titel der Einkaufsliste.`
      + `${pv.without ? ` ${fmtN(pv.without)} Titel ohne Beatport-ID bleiben aussen vor.` : ""}${pv.bought ? ` ${fmtN(pv.bought)} bereits gekaufte werden nicht gesendet.` : ""}`
      + ` Vorher werden die Einkäufe noch einmal geprüft. Die Playlist enthält danach genau die Einkaufsliste; andere Playlists bleiben unberührt. Es wird nichts gekauft – auf beatport.com „Alle in den Warenkorb“ und dort bezahlen.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "An Beatport senden", value: true, primary: true }] });
  if (!ok) return;
  const r = await runTask(call("start_carts_bp", CART.d.sel), "Beatport – Warenkorb");
  if (!r) return;
  await cartsShow();
  const go = await dialog({ title: "An Beatport gesendet",
    text: `${r.name}: ${fmtN(r.count)} Titel${r.created ? " (neu angelegt)" : ""}.${r.bought ? ` ${fmtN(r.bought)} bereits gekaufte ausgelassen.` : ""}${r.note ? " " + r.note : ""}\n\nAuf beatport.com die Playlist öffnen, „Alle in den Warenkorb“ wählen und dort bezahlen. Danach erkennt „Einkäufe“ die Käufe, und der Warenkorb wird als gekauft abgeschlossen.`,
    buttons: [{ label: "OK", value: null }, ...(r.url ? [{ label: "Playlist bei Beatport öffnen", value: true, primary: true }] : [])] });
  if (go && r.url) call("open_url", r.url);
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
  items.push({ label: "Neuer Warenkorb …", run: async () => { const n = await cartsNameDialog("Neuer Warenkorb", cartsDefaultName(), "Anlegen und hinzufügen"); if (n) save("", n); } });
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
  $("#cartAdd").addEventListener("click", (e) => { e.stopPropagation(); cartsAddMenu(); });
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
