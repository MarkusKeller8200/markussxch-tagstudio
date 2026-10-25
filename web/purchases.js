/* MarKusSXCH TagStudio – Seite „Käufe“ (#285): gekaufte Titel aller Stores, Abgleich mit der Bibliothek, Download.
   Speicher und Abgleich in purchases.py / session_purchases.py, Stores als Plugins (store_purchases, store_download). */
"use strict";

const PUR = { st: null, q: "", store: "", status: "", sel: new Set(), sort: { k: "bought", desc: true } };
const PUR_STATUS = { library: "in Bibliothek", inbox: "im Eingang", unclear: "unklar", missing: "fehlt" };
const PUR_COLS = [["status", "Status"], ["title", "Titel"], ["artist", "Interpret"], ["mix", "Mix"], ["dur", "Länge"],
  ["key", "Tonart"], ["bpm", "BPM"], ["catalog", "Katalognr."], ["store", "Store"], ["bought", "Kaufdatum"], ["hint", "Hinweis"]];

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
  const ss = Object.entries(st.sessions || {}).filter(([, v]) => v && v.active);   // #295
  $("#purSess").innerHTML = ss.map(([id, v]) => `<span class="pur-sess-on" title="Anmeldung nur für diese Sitzung – wird nicht gespeichert">● ${esc(purStoreName(id))}: Sitzung ${esc(v.username || "")}</span> <button class="ghost sm" data-sesslogout="${esc(id)}">Abmelden</button>`).join(" ");
}

/** #295: Anmelden nur für diese Sitzung, wie auf der Webseite – Token bleibt im Speicher, Passwort wird nicht gespeichert */
async function purSessionLogin(store, name, why) {
  return modal({ title: `${name} – Anmelden für den Download`,
      html: `<p style="margin:0">${esc(why || `${name} lehnt den gespeicherten Zugang für den Download ab.`)}</p>
        <p class="muted sm" style="margin:6px 0 10px">Anmelden wie auf der Webseite. Die Anmeldung gilt nur, solange TagStudio läuft – Passwort und Token werden nicht gespeichert.</p>
        <div class="frm"><label for="purSU">Benutzername / E-Mail</label><input id="purSU" type="text" autocomplete="username" spellcheck="false">
        <label for="purSP">Passwort</label><input id="purSP" type="password" autocomplete="current-password" spellcheck="false"></div>
        <p class="st-missing sm" id="purSErr" style="margin:8px 0 0"></p>`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Anmelden und herunterladen", value: true, primary: true }],
      collect: async (b) => {
        const u = $("#purSU", b).value.trim(), p = $("#purSP", b).value;
        if (!u || !p) { $("#purSErr", b).textContent = "Benutzername und Passwort angeben."; return false; }
        $("#purSErr", b).textContent = "Anmelden …";
        try {
          const r = await call("purch_session_login", store, u, p);
          $("#purSP", b).value = "";
          if (PUR.st) PUR.st.sessions = r.sessions;
          return r;
        } catch (e) { $("#purSErr", b).textContent = String(e.message || e); $("#purSP", b).value = ""; return false; }
      } });
}

/** #290: sichtbarer Grund bzw. gefundene Datei */
function purHint(r) {
  if (r.status === "library" || r.status === "inbox") return r.file ? r.file.split(/[\\/]/).pop() : "";
  if (r.status === "unclear") return r.reason + (r.cands && r.cands.length > 1 ? ` · ${r.cands.length} Kandidaten` : "");
  return r.reason && r.reason !== "nicht gefunden" ? r.reason : "";
}

function purVisible() {
  const q = PUR.q.trim().toLowerCase();
  const rows = PUR.st.rows.filter((r) => (!PUR.store || r.store === PUR.store) && (!PUR.status || r.status === PUR.status)
    && (!q || [r.title, r.artist, r.mix, r.catalog, r.label, r.release, r.isrc].join(" ").toLowerCase().includes(q)));
  const { k, desc } = PUR.sort;
  const val = (r) => k === "key" ? (r.key ? (parseInt(r.key, 10) * 2 - (r.key.endsWith("A") ? 1 : 0)) : null)
    : k === "bought" ? (r.bought || (r.seen ? new Date(r.seen * 1000).toISOString() : ""))
    : k === "status" ? Object.keys(PUR_STATUS).indexOf(r.status) : k === "hint" ? purHint(r) : r[k];
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
  const dg = st.last || {};
  const diag = `<div class="muted sm pur-diag">Verglichen mit: ${libNamesHtml(dg.roots || st.roots || [], st.libs, st.libs_skipped)}${dg.files ? ` · ${fmtN(dg.files)} Dateien` : ""}${dg.dupes ? ` · <span title="${esc((dg.examples || []).map((x) => x.path + "\n= " + x.same).join("\n\n"))}">${fmtN(dg.dupes)} doppelt (gleiche Datei unter anderem Pfad) zusammengefasst</span>` : ""}</div>`;
  const head = PUR_COLS.map(([k, l]) => `<th data-pursort="${k}" class="${["dur", "bpm"].includes(k) ? "r" : ""}" aria-sort="${PUR.sort.k === k ? (PUR.sort.desc ? "descending" : "ascending") : "none"}">${esc(l)}${PUR.sort.k === k ? (PUR.sort.desc ? " ▾" : " ▴") : ""}</th>`).join("");
  box.innerHTML = diag + `<table class="pur-t"><thead><tr><th><input type="checkbox" id="purAll" ${all ? "checked" : ""} aria-label="Alle wählen"></th>${head}<th></th></tr></thead><tbody>
    ${rows.map((r) => {
      const stc = r.preorder ? `<span class="pur-st pre">Vorbestellung</span>` : `<span class="pur-st ${r.status}" title="${esc([r.file || r.reason || "", r.received ? `Bei ${purStoreName(r.store)} schon heruntergeladen` : ""].filter(Boolean).join(" · "))}">${esc(PUR_STATUS[r.status] || r.status)}</span>`;
      const date = r.bought ? esc(r.bought.slice(0, 10)) : (r.seen ? `<span class="muted" title="Kein Kaufdatum vom Store – zuerst gesehen">${esc(new Date(r.seen * 1000).toLocaleDateString())}</span>` : "");
      const bpm = r.bpm ? (Math.round(r.bpm * 10) / 10).toString() : "";
      return `<tr data-k="${esc(r.k)}" class="${PUR.sel.has(r.k) ? "sel" : ""}"><td><input type="checkbox" data-pursel ${PUR.sel.has(r.k) ? "checked" : ""}></td>
        <td>${stc}</td><td class="nm" translate="no" title="${esc(r.title)}">${esc(r.title)}</td><td class="nm" translate="no" title="${esc(r.artist)}">${esc(r.artist)}</td>
        <td class="nm muted" translate="no">${esc(r.mix)}</td><td class="r muted">${r.dur ? fmtTime(r.dur) : ""}</td>
        <td>${r.key ? keyBadge(r.key) : ""}</td><td class="r">${bpm}</td><td translate="no">${esc(r.catalog)}</td>
        <td translate="no">${esc(purStoreName(r.store))}</td><td>${date}</td>
        <td class="nm sm ${r.status === "unclear" ? "pur-why" : "muted"}" title="${esc([r.file, ...(r.cands || [])].filter(Boolean).join("\n"))}"${r.status === "library" || r.status === "inbox" ? ' translate="no"' : ""}>${r.linked ? "✓ " : ""}${esc(purHint(r))}</td>
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
  await purDoDownload(keys, 0);
}

async function purDoDownload(keys, round) {
  const r = await runTask(call("start_purch_download", keys), "Käufe herunterladen");
  if (!r || r.cancelled) return;
  PUR.sel = new Set();
  await purchasesShow();
  toast(`${fmtN(r.downloaded || 0)} Titel geladen.`);
  if (r.need_login && r.need_login.length && round === 0) {        // #295: Sitzungs-Anmeldung, dann gleich erneut
    const n = r.need_login[0];
    if (await purSessionLogin(n.store, n.name)) { await purDoDownload(n.keys, 1); return; }
  }
  if (r.manual && r.manual.length) { await purManual(r); return; }
  if (r.failed && r.failed.length) info("Nicht geladen", r.failed.slice(0, 30).join("\n") + (r.failed.length > 30 ? "\n…" : ""));
}

/** Variante 2: Der Store lässt das Herunterladen über die Schnittstelle nicht zu → auf seiner Seite selbst laden */
async function purManual(r) {
  const m = r.manual[0];
  const a = await modal({ title: "Selbst herunterladen", wide: true,
    html: `<p style="margin:0">${fmtN(r.failed.length)} Titel konnte TagStudio nicht laden: ${esc(m.name)} gibt dafür keine Download-Adresse heraus.</p>
      <p style="margin:8px 0 0">So geht es weiter (Variante 2):</p>
      <ol style="margin:4px 0 0;padding-left:20px"><li>Die Download-Seite bei ${esc(m.name)} öffnen und dort anmelden.</li>
        <li>Die fehlenden Titel in deinen Download-Ordner laden (z. B. 90_Download).</li>
        <li>In „Vorbereiten“ mit „Abholen“ übernehmen.</li><li>Hier „Abgleichen“ – die Titel stehen dann auf „im Eingang“ bzw. „in Bibliothek“.</li></ol>
      <details style="margin-top:8px"><summary class="muted sm">Nicht geladene Titel (${fmtN(r.failed.length)})</summary><div class="sm" translate="no" style="max-height:180px;overflow:auto">${r.failed.slice(0, 100).map(esc).join("<br>")}</div></details>`,
    buttons: [{ label: "Schliessen", value: null }, { label: `Downloads bei ${m.name} öffnen`, value: "open", primary: true }] });
  if (a === "open") call("open_url", m.url);
}

/** #290: Kauf von Hand einer Datei zuordnen – Kandidaten aus dem Abgleich oder eigene Datei */
async function purLinkDialog(r) {
  const cands = r.cands || [];
  const pick = await modal({ title: "Zuordnen", wide: true,
    html: `<p style="margin:0" translate="no">${esc(r.artist)} – ${esc(r.title)}${r.mix ? ` (${esc(r.mix)})` : ""}</p>
      ${r.reason ? `<p class="muted sm" style="margin:4px 0 8px">Grund: ${esc(r.reason)}</p>` : ""}
      ${cands.length ? cands.map((p, k) => `<label class="pls-pick-row"><input type="radio" name="purLink" value="${k}"${k === 0 ? " checked" : ""}> <span class="ellipsis" translate="no" title="${esc(p)}">${esc(p)}</span></label>`).join("") : '<div class="muted sm">Keine Kandidaten aus dem Abgleich.</div>'}
      <label class="pls-pick-row"><input type="radio" name="purLink" value="pick"${cands.length ? "" : " checked"}> Andere Datei wählen …</label>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Zuordnen", value: true, primary: true }],
    collect: (b) => (b.querySelector('input[name="purLink"]:checked') || {}).value });
  if (pick === null || pick === undefined) return;
  let path = pick === "pick" ? await call("pick_file", "mp3", r.file || (PUR.st.roots || [])[0] || "") : cands[+pick];
  if (!path) return;
  try { purApply(await call("purch_link", r.k, path)); toast("Zugeordnet – bleibt bei weiteren Abgleichen."); }
  catch (e) { toast(String(e.message || e)); }
}

async function purPickDest() {
  const p = await pickFolder($("#purDestBtn"), PUR.st ? PUR.st.dest : "", { role: "downloads" });   // #314
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
  if (r.status !== "library" || r.linked) items.push({ label: "Zuordnen …", run: () => purLinkDialog(r) });
  if (r.linked) items.push({ label: "Zuordnung aufheben", run: async () => purApply(await call("purch_link", r.k, "")) });
  if (r.status !== "library" && !r.preorder) items.push({ label: "Herunterladen …", run: () => { PUR.sel = new Set([k]); purRenderBar(); purDownload(); } });
  if (items.length) showMenu(e.clientX, e.clientY, items);
}

function purInit() {
  $("#purRefresh").addEventListener("click", () => purRefresh(false));
  $("#purMatch").addEventListener("click", () => purRefresh(true));
  $("#purFull").addEventListener("click", () => purRefresh(false, true));
  $("#purDl").addEventListener("click", purDownload);
  $("#purDestBtn").addEventListener("click", purPickDest);
  $("#purSess").addEventListener("click", async (e) => {
    const b = e.target.closest("[data-sesslogout]"); if (!b) return;
    const r = await call("purch_session_logout", b.dataset.sesslogout);
    PUR.st.sessions = r.sessions; purRenderBar(); toast("Sitzung abgemeldet.");
  });
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
