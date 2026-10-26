/* MarKusSXCH TagStudio – Seite „Einkäufe“ (#285): gekaufte Titel aller Stores, Abgleich mit der Bibliothek, Download.
   Speicher und Abgleich in purchases.py / session_purchases.py, Stores als Plugins (store_purchases, store_download). */
"use strict";

const PUR = { st: null, q: "", store: "", status: "", sel: new Set(), sort: { k: "bought", desc: true } };
const PUR_STATUS = { library: "in Bibliothek", inbox: "im Eingang", unclear: "unklar", missing: "fehlt" };
const PUR_COLS = [["status", "Status"], ["title", "Titel"], ["artist", "Interpret"], ["mix", "Mix"], ["dur", "Länge"],
  ["key", "Tonart"], ["bpm", "BPM"], ["catalog", "Katalognr."], ["store", "Store"], ["bought", "Kaufdatum"], ["hint", "Hinweis"]];

async function purchasesShow() {
  try { purApply(await call("purch_state")); } catch (e) { toast(String(e.message || e)); }
  purUnzip();
}

/** #336: neue ZIPs in den Download-Ordnern entpacken (Einstellung „ZIP entpacken“, Standard ein) */
async function purUnzip() {
  let r;
  try { r = await call("purch_unzip"); } catch (e) { return; }
  if (!r || r.off || !r.zips.length) return;
  const msg = `${fmtN(r.files)} Titel aus ${fmtN(r.zips.length)} ZIP entpackt` + (r.skipped ? ` · ${fmtN(r.skipped)} übersprungen (gibt es schon)` : "");
  if (r.errors.length || r.skipped) {
    info("ZIP entpacken", [msg, ...r.errors, ...r.zips.flatMap((z) => z.skipped)].join("\n"));
  } else toast(msg + " – „Abgleichen“ übernimmt sie.");
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
  $("#purUnzip").checked = st.unzip !== false;
  $("#purStrict").checked = !!st.strict;                                            // #338
  const open = st.rows.filter((r) => (r.status === "unclear" || r.status === "missing") && !r.preorder).length;
  const selOpen = typeof purOpenList === "function" && PUR.sel.size ? purOpenList().length : 0;      // #345
  $("#purFix").textContent = PUR.sel.size ? `Markierte prüfen … (${fmtN(selOpen)})` : open ? `Unklare prüfen … (${fmtN(open)})` : "Unklare prüfen …";
  $("#purFix").disabled = PUR.sel.size ? !selOpen : !open;
  $("#purDest").innerHTML = st.dest ? `Ziel: <span translate="no" title="${esc(st.dest_from)}">${esc(st.dest)}</span>${st.dest_ok ? "" : " (wird angelegt)"}` : "Kein Eingangsordner";
  const sel = PUR.sel.size, miss = st.rows.filter((r) => r.status === "missing" && !r.preorder).length;
  const b = $("#purDl");
  b.textContent = sel ? `Markierte herunterladen (${fmtN(sel)})` : `Fehlende herunterladen (${fmtN(miss)})`;
  b.disabled = !(sel || miss) || !st.dest;
  const inb = (PUR.sel.size ? st.rows.filter((r) => PUR.sel.has(r.k)) : st.rows).filter((r) => r.status === "inbox" && r.file).length;   // #369
  const mv = $("#purMove"); mv.disabled = !inb; mv.textContent = inb ? `In Bibliothek verschieben … (${fmtN(inb)})` : "In Bibliothek verschieben …";
  const wt = st.rows.filter((r) => r.await).length;                                   // #368
  const wb = $("#purWait"); wb.hidden = !wt; wb.textContent = `Heruntergeladene übernehmen (${fmtN(wt)} warten)`;
  purWatch(wt);
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
  if (r.await) return "wartet auf Download – im Browser laden, TagStudio verlinkt die Datei selbst";   // #368
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
    box.innerHTML = `<div class="tg-empty">${st.sources.length && ready ? "Noch keine Einkäufe geholt – „↻ Aktualisieren“ liest die gekauften Titel."
      : "Zuerst unter Plugins › Beatport anmelden – dann holt „↻ Aktualisieren“ die gekauften Titel."}</div>`;
    return;
  }
  const rows = purVisible();
  const all = rows.length && rows.every((r) => PUR.sel.has(r.k));
  const dg = st.last || {};
  const diag = `<div class="muted sm pur-diag">Verglichen mit: ${libNamesHtml(dg.roots || st.roots || [], st.libs, st.libs_skipped)}${dg.files ? ` · ${fmtN(dg.files)} Dateien` : ""}${dg.dupes ? ` · <span title="${esc((dg.examples || []).map((x) => x.path + "\n= " + x.same).join("\n\n"))}">${fmtN(dg.dupes)} doppelt (gleiche Datei unter anderem Pfad) zusammengefasst</span>` : ""}</div>`;
  const head = PUR_COLS.map(([k, l]) => `<th data-col="${k}" data-pursort="${k}" class="${["dur", "bpm"].includes(k) ? "r" : ""}" aria-sort="${PUR.sort.k === k ? (PUR.sort.desc ? "descending" : "ascending") : "none"}">${esc(l)}${PUR.sort.k === k ? (PUR.sort.desc ? " ▾" : " ▴") : ""}</th>`).join("");
  box.innerHTML = diag + `<table class="pur-t"><thead><tr><th data-col="sel" data-nogrip><input type="checkbox" id="purAll" ${all ? "checked" : ""} aria-label="Alle wählen"></th>${head}<th data-col="link" data-nogrip></th></tr></thead><tbody>
    ${rows.map((r) => {
      const stc = r.preorder ? `<span class="pur-st pre">Vorbestellung</span>` : `<span class="pur-st ${r.status}" title="${esc([r.file || r.reason || "", r.received ? `Bei ${purStoreName(r.store)} schon heruntergeladen` : ""].filter(Boolean).join(" · "))}">${esc(PUR_STATUS[r.status] || r.status)}</span>`;
      const date = r.bought ? esc(r.bought.slice(0, 10)) : (r.seen ? `<span class="muted" title="Kein Kaufdatum vom Store – zuerst gesehen">${esc(new Date(r.seen * 1000).toLocaleDateString())}</span>` : "");
      const bpm = r.bpm ? (Math.round(r.bpm * 10) / 10).toString() : "";
      return `<tr data-k="${esc(r.k)}" class="${PUR.sel.has(r.k) ? "sel" : ""}${r.status === "unclear" && !r.preorder ? " pur-clickfix" : ""}"><td><input type="checkbox" data-pursel ${PUR.sel.has(r.k) ? "checked" : ""}></td>
        <td>${stc}</td><td class="nm" translate="no" title="${esc(r.title)}">${esc(r.title)}</td><td class="nm" translate="no" title="${esc(r.artist)}">${esc(r.artist)}</td>
        <td class="nm muted" translate="no">${esc(r.mix)}</td><td class="r muted">${r.dur ? fmtTime(r.dur) : ""}</td>
        <td>${r.key ? keyBadge(r.key) : ""}</td><td class="r">${bpm}</td><td translate="no">${esc(r.catalog)}</td>
        <td translate="no">${esc(purStoreName(r.store))}</td><td>${date}</td>
        <td class="nm sm ${r.status === "unclear" ? "pur-why" : "muted"}" title="${esc([r.status === "unclear" && !r.preorder ? "Klick: korrigieren · Rechtsklick: Menü" : "", r.file, ...(r.cands || [])].filter(Boolean).join("\n"))}"${r.status === "library" || r.status === "inbox" ? ' translate="no"' : ""}>${r.linked ? "✓ " : ""}${esc(purHint(r))}</td>
        <td>${r.url ? `<a href="#" class="pls-link" data-url="${esc(r.url)}" title="Bei ${esc(purStoreName(r.store))} öffnen">↗</a>` : ""}</td></tr>`;
    }).join("")}</tbody></table>${rows.length ? "" : '<div class="tg-empty">Keine Einkäufe für diesen Filter.</div>'}`;
  colResize(box.querySelector("table.pur-t"), "purchases");      // #337
}

async function purRefresh(match = false, full = false) {
  const r = await runTask(match ? call("start_purch_match") : call("start_purch_refresh", null, full), match ? "Einkäufe abgleichen" : "Einkäufe aktualisieren");
  if (!r || r.cancelled) return;
  await purchasesShow();
  const c = r.count || {};
  toast((match ? "" : `${fmtN(r.new || 0)} neue Einkäufe · `) + `${fmtN(c.library || 0)} in Bibliothek · ${fmtN(c.inbox || 0)} im Eingang · ${fmtN(c.unclear || 0)} unklar · ${fmtN(c.missing || 0)} fehlen`);
  if (r.errors && r.errors.length) info("Hinweise", r.errors.join("\n"));
}

async function purDownload() {
  const st = PUR.st;
  const keys = PUR.sel.size ? [...PUR.sel] : null;
  const n = keys ? keys.length : st.rows.filter((r) => r.status === "missing" && !r.preorder).length;
  const ok = await modal({ title: "Einkäufe herunterladen",
    html: `<p style="margin:0">${fmtN(n)} Titel in den Eingangsordner laden?</p><p class="sm" translate="no" style="margin:6px 0 0">${esc(st.dest)}</p>
      <p class="muted sm" style="margin:8px 0 0">Die Dateien kommen unverändert vom Store; danach geht es wie gewohnt mit „Vorbereiten“ weiter. Vorbestellungen werden ausgelassen.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Herunterladen", value: true, primary: true }] });
  if (!ok) return;
  await purDoDownload(keys, 0);
}

async function purDoDownload(keys, round) {
  const r = await runTask(call("start_purch_download", keys), "Einkäufe herunterladen");
  if (!r || r.cancelled) return;
  PUR.sel = new Set();
  await purchasesShow();
  toast(`${fmtN(r.downloaded || 0)} Titel geladen.`);
  if (r.need_login && r.need_login.length && round === 0) {        // #295: Sitzungs-Anmeldung, dann gleich erneut
    const n = r.need_login[0];
    if (await purSessionLogin(n.store, n.name)) { await purDoDownload(n.keys, 1); return; }
    // #367: Anmeldung abgebrochen → trotzdem bei Beatport zum Download freigeben
    const rs = await runTask(call("start_purch_reset", n.keys), "Zum Download freigeben");
    if (rs && rs.ok) { await purchasesShow(); await purWaitDialog({ name: n.name, url: rs.url, dest: rs.dest, reset: (rs.reset || []).length,
      notes: [...(rs.failed || []), ...(rs.skipped || [])], notLoaded: n.keys.length }); return; }
  }
  if (r.manual && r.manual.length) { await purManual(r); return; }
  if (r.failed && r.failed.length) info("Nicht geladen", r.failed.slice(0, 30).join("\n") + (r.failed.length > 30 ? "\n…" : ""));
}

/** Variante 2: Der Store lässt das Herunterladen über die Schnittstelle nicht zu → auf seiner Seite selbst laden */
async function purManual(r) {
  const m = r.manual[0];
  if (m.dest || m.reset) {                                                     // #367: freigegeben + Speicherort
    return purWaitDialog({ name: m.name, url: m.url, dest: m.dest, reset: m.reset || 0, notes: m.reset_failed || [], notLoaded: r.failed.length, failed: r.failed });
  }
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

/** #367/#368: Titel wurden beim Store zum Download freigegeben – Speicherort zum Kopieren, Seite öffnen; die im Browser
    geladenen Dateien erkennt TagStudio selbst (purWatch) und verlinkt sie. */
async function purWaitDialog(o) {
  const a = await modal({ title: "Im Browser herunterladen", wide: true,
    html: `<p style="margin:0">${o.notLoaded ? `${fmtN(o.notLoaded)} Titel konnte TagStudio nicht direkt laden. ` : ""}<b>${fmtN(o.reset)}</b> ${o.notLoaded ? "davon stehen" : "Titel stehen"} jetzt in deiner Download-Warteliste bei ${esc(o.name)}.</p>
      <ol style="margin:8px 0 0;padding-left:20px"><li>„Downloads bei ${esc(o.name)} öffnen“ und die Titel dort herunterladen.</li>
        <li>Als Speicherort diesen Ordner einfügen (oder im Browser als Download-Ordner wählen):</li></ol>
      <div class="pur-dest-copy"><input class="inp mono" id="purDestCopy" readonly value="${esc(o.dest || "")}" translate="no"><button class="ghost sm" id="purDestCopyBtn">Kopieren</button></div>
      <p class="muted sm" style="margin:8px 0 0">Sobald die Dateien (auch als ZIP) dort liegen, erkennt TagStudio sie auf der Seite „Einkäufe“ selbst und verlinkt sie mit den Einkäufen – danach „In Bibliothek verschieben …“.</p>
      ${(o.notes || []).length ? `<details style="margin-top:8px"><summary class="muted sm">Hinweise (${fmtN(o.notes.length)})</summary><div class="sm" translate="no" style="max-height:160px;overflow:auto">${o.notes.slice(0, 100).map(esc).join("<br>")}</div></details>` : ""}`,
    buttons: [{ label: "Schliessen", value: null }, { label: `Downloads bei ${o.name} öffnen`, value: "open", primary: true }],
    onMount: (b) => {
      $("#purDestCopyBtn", b).addEventListener("click", async () => {
        const inp = $("#purDestCopy", b);
        try { await navigator.clipboard.writeText(inp.value); toast("Speicherort kopiert."); }
        catch { inp.select(); document.execCommand && document.execCommand("copy"); toast("Speicherort markiert – mit Strg+C kopieren."); }
      });
      $("#purDestCopy", b).addEventListener("focus", (e) => e.target.select());
    } });
  if (a === "open" && o.url) call("open_url", o.url);
}

/** #368: solange Einkäufe auf den Download warten und die Seite offen ist, alle 5 s die Download-Ordner prüfen */
let PUR_WATCH = { t: 0, sig: "", busy: false };
function purWatch(waiting) {
  if (!waiting) { clearInterval(PUR_WATCH.t); PUR_WATCH.t = 0; return; }
  if (PUR_WATCH.t) return;
  PUR_WATCH.t = setInterval(purWatchTick, 5000);
}
async function purWatchTick() {
  if (PUR_WATCH.busy || (typeof S !== "undefined" && S.module !== "purchases")) return;
  PUR_WATCH.busy = true;
  try {
    const s = await call("purch_dl_signature");
    if (!s.waiting) { purWatch(0); return; }
    if (s.sig === PUR_WATCH.sig) return;
    PUR_WATCH.sig = s.sig;
    await purPickup(false);
  } catch { /* nächster Versuch */ } finally { PUR_WATCH.busy = false; }
}
async function purPickup(loud) {
  const r = await call("purch_pickup");
  if (r.found.length || loud) {
    purApply(await call("purch_state"));
    toast(r.found.length ? `${fmtN(r.found.length)} heruntergeladene Titel verlinkt${r.waiting ? ` · ${fmtN(r.waiting)} warten noch` : ""}.`
      : `Noch keine passenden Dateien im Speicherort${r.waiting ? ` (${fmtN(r.waiting)} warten)` : ""}.`);
  }
}

/** #369: Einkäufe „im Eingang“ in die Bibliothek verschieben, danach im Tagger öffnen */
async function purMoveDialog(keys) {
  keys = keys || (PUR.sel.size ? [...PUR.sel] : null);
  const pv = await call("purch_move_preview", keys);
  if (!pv.count) return info("In Bibliothek verschieben", "Keine Einkäufe „im Eingang“ mit Datei.");
  const opts = pv.targets.map((t) => `<option value="${esc(t.path)}"${t.path === pv.target ? " selected" : ""}>${esc(t.name)} – ${esc(t.path)}</option>`).join("")
    + (pv.target && !pv.targets.some((t) => t.path === pv.target) ? `<option value="${esc(pv.target)}" selected>${esc(pv.target)}</option>` : "");
  const target = await modal({ title: "In Bibliothek verschieben", wide: true,
    html: `<p style="margin:0">${fmtN(pv.count)} Datei(en) aus dem Eingang in die Bibliothek verschieben?</p>
      <div class="frm" style="margin-top:10px"><label for="purMvTo">Ziel</label><div class="pur-dest-copy"><select id="purMvTo" class="inp">${opts || '<option value="">– kein Ordner –</option>'}</select><button class="ghost sm" id="purMvPick">Anderer Ordner …</button></div></div>
      <p class="muted sm" style="margin:8px 0 0">Gleichnamige Dateien im Ziel werden nie überschrieben (übersprungen und genannt). Danach stehen die Einkäufe auf „in Bibliothek“.</p>
      <details style="margin-top:8px"><summary class="muted sm">Dateien (${fmtN(pv.count)})</summary><div class="sm" translate="no" style="max-height:160px;overflow:auto">${pv.files.map((f) => esc(f.split(/[\\/]/).pop())).join("<br>")}</div></details>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Verschieben", value: true, primary: true }],
    onMount: (b) => $("#purMvPick", b).addEventListener("click", async (e) => {
      e.stopPropagation();                                                       // sonst schliesst der Klick das Menü
      const p = await pickFolder(e.currentTarget, $("#purMvTo", b).value || "", { role: "library" });
      if (p === FOLDER_FOLLOW) return;
      if (p) { const s = $("#purMvTo", b); s.insertAdjacentHTML("beforeend", `<option value="${esc(p)}">${esc(p)}</option>`); s.value = p; }
    }),
    collect: (b) => $("#purMvTo", b).value || false });
  if (!target) return;
  let r;
  try { r = await call("purch_move", keys, target); } catch (e) { return info("Nicht verschoben", String(e.message || e)); }
  purApply(r.state);
  const go = await dialog({ title: "In die Bibliothek verschoben",
    text: `${fmtN(r.moved.length)} Datei(en) nach ${r.target} verschoben.${r.skipped.length ? "\n\nNicht verschoben:\n" + r.skipped.join("\n") : ""}`,
    buttons: [{ label: "Schliessen", value: false }, ...(r.files.length ? [{ label: "Im Tagger öffnen", value: true, primary: true }] : [])] });
  if (!go || !r.files.length) return;
  const t = await runTask(call("start_tag_load_files", r.files, "Einkäufe"), "Dateien einlesen");
  if (!t || t.cancelled) return;
  setModule("tagger");
  if (typeof tgAfterLoad === "function") await tgAfterLoad(t, "", false);
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
  if ((r.status === "unclear" || r.status === "missing") && !r.preorder) items.unshift({ label: "Korrigieren …", run: () => purCorrect(k) });   // #338/#346: zuoberst
  if (r.status !== "library" || r.linked) items.push({ label: "Zuordnen …", run: () => purLinkDialog(r) });
  if (r.linked) items.push({ label: "Zuordnung aufheben", run: async () => purApply(await call("purch_link", r.k, "")) });
  if (r.status !== "library" && !r.preorder) items.push({ label: "Herunterladen …", run: () => { PUR.sel = new Set([k]); purRenderBar(); purDownload(); } });
  if (r.store === "beatport" && r.status !== "library" && !r.preorder) items.push({ label: "Erneut zum Download freigeben …", run: () => purBpReset([k]) });   // #362
  if (r.status === "inbox" && r.file) items.push({ label: "In Bibliothek verschieben …", run: () => purMoveDialog([k]) });   // #369
  if (items.length) showMenu(e.clientX, e.clientY, items);
}

function purInit() {
  $("#purRefresh").addEventListener("click", () => purRefresh(false));
  $("#purMatch").addEventListener("click", () => purRefresh(true));
  $("#purFull").addEventListener("click", () => purRefresh(false, true));
  $("#purDl").addEventListener("click", purDownload);
  $("#purMove").addEventListener("click", () => purMoveDialog());                // #369
  $("#purWait").addEventListener("click", () => purPickup(true));                // #368
  $("#purDestBtn").addEventListener("click", purPickDest);
  $("#purFix").addEventListener("click", () => purCorrect());                   // #338
  $("#purBpl").addEventListener("click", (e) => purBpMenu(e));                  // #334/#335
  $("#purStrict").addEventListener("change", async (e) => {
    await call("set_purch_strict", e.target.checked);
    toast(e.target.checked ? "Abgleich streng: auch der Mix muss passen." : "Abgleich wie bisher.");
    purRefresh(true);
  });
  $("#purUnzip").addEventListener("change", async (e) => {                          // #336
    await call("set_unzip_auto", e.target.checked);
    toast(e.target.checked ? "Neue ZIP-Downloads werden entpackt." : "ZIP-Downloads werden nicht mehr entpackt.");
    if (e.target.checked) purUnzip();
  });
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
    if (cb) { const k = cb.closest("tr").dataset.k; if (cb.checked) PUR.sel.add(k); else PUR.sel.delete(k); cb.closest("tr").classList.toggle("sel", cb.checked); purRenderBar(); return; }
    // #353: Linksklick auf einen unklaren Einkauf öffnet die Korrektur (Häkchen, Links und Spaltengriffe ausgenommen)
    const tr = e.target.closest("tbody tr[data-k]");
    if (!tr || e.target.closest("input, a, button, .col-grip") || e.shiftKey || e.ctrlKey || e.metaKey) return;
    const r = PUR.st.rows.find((x) => x.k === tr.dataset.k);
    if (r && r.status === "unclear" && !r.preorder) purCorrect(r.k);
  });
  box.addEventListener("contextmenu", (e) => {
    const tr = e.target.closest("tr[data-k]"); if (!tr) return;
    e.preventDefault();
    purRowMenu(e, tr.dataset.k);                                                // #353: Rechtsklick immer das Kontextmenü
  });
  box.addEventListener("dblclick", (e) => {                                    // #349: gefundene Titel abspielen
    const tr = e.target.closest("tr[data-k]");
    if (!tr || e.target.closest("input, a, .col-grip")) return;
    const r = PUR.st.rows.find((x) => x.k === tr.dataset.k);
    if (r && r.file && (r.status === "library" || r.status === "inbox")) plLoad({ kind: "file", ref: r.file }, true);
    else if (r) toast("Keine Datei zugeordnet – nichts abzuspielen.");
  });
}

purInit();
setTimeout(() => { if (!PUR.st) call("purch_state").then((st) => { PUR.st = st; purSideCount(); }).catch(() => {}); }, 1200);
if (typeof S !== "undefined" && S.module === "purchases") purchasesShow();
