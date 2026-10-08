/* MarKusSXCH TagStudio – Dialoge und Module: Feld hinzufügen, Sammelkopie, Bilder, Tag-Fixer, Sicherungen.
   Nutzt call/dialog/info/toast/applyState/S aus app.js. */
"use strict";

// ====================================================================== Formular-Dialog
/** Dialog mit eigenem Inhalt. buttons: [{label, value, primary}]; onMount(body) vor dem Anzeigen;
    collect(body, value) liefert das Ergebnis (oder false = Dialog bleibt offen). */
function modal({ title, html, buttons, wide = false, onMount, collect }) {
  return new Promise((resolve) => {
    const ov = $("#modal"), body = $("#mBody"), box = $("#mBtns");
    $("#mTitle").textContent = title;
    body.innerHTML = html;
    $(".modal-dlg").classList.toggle("wide", wide);
    box.innerHTML = "";
    const finish = async (v) => {
      let out = v;
      if (v !== null && collect) {
        out = await collect(body, v);
        if (out === false) return;
      }
      ov.hidden = true;
      document.removeEventListener("keydown", onKey, true);
      resolve(out);
    };
    buttons.forEach((b) => {
      const el = document.createElement("button");
      el.className = b.primary ? "primary" : "ghost";
      el.textContent = b.label;
      el.addEventListener("click", () => finish(b.value));
      box.appendChild(el);
    });
    const onKey = (e) => {
      if (!$("#dialog").hidden) return;
      if (e.key === "Escape") { e.preventDefault(); e.stopImmediatePropagation(); finish(null); }
      if (e.key === "Enter" && e.target.tagName === "INPUT") {
        e.preventDefault(); e.stopImmediatePropagation();
        const p = buttons.find((b) => b.primary); if (p) finish(p.value);
      }
    };
    document.addEventListener("keydown", onKey, true);
    if (onMount) onMount(body);
    ov.hidden = false;
    (body.querySelector("[autofocus]") || body.querySelector("input,select,textarea") || box.querySelector(".primary"))?.focus();
  });
}

/** Nach Änderungen außerhalb der Vergleichsansicht: Paarliste, Ansicht und Tagger auffrischen. */
async function refreshAll(stateFromCall) {
  if (S.pairs.length) await loadPairs();
  applyState(stateFromCall && stateFromCall.view ? stateFromCall : await call("state"));
  if (typeof taggerRefresh === "function") await taggerRefresh();
}

// ====================================================================== Feld hinzufügen
let FIELD_CHOICES = null;
async function addFieldForm(sides, preset = {}) {
  FIELD_CHOICES = FIELD_CHOICES || (await call("add_field_choices"));
  const sideHtml = sides
    ? `<label>Seite</label><div class="radios">${sides.map(([v, l, en], k) => `<label><input type="radio" name="af-side" value="${v}" ${en ? "" : "disabled"} ${k === sides.findIndex((s) => s[2]) ? "checked" : ""}> ${l}</label>`).join("")}</div>`
    : "";
  return modal({
    title: "Feld hinzufügen",
    html: `<div class="frm">${sideHtml}
      <label for="afField">Feld</label><select id="afField">${FIELD_CHOICES.map(([l, fid, d]) => `<option value="${fid}" data-desc="${d ? 1 : 0}">${esc(l)}</option>`).join("")}</select>
      <label for="afDesc">Beschreibung</label><input id="afDesc" placeholder="z. B. Acoustid Id, Quelle …">
      <label for="afVal">Wert</label><input id="afVal" autofocus placeholder="Mehrere Werte mit ¦ trennen">
      </div><div class="hint">Die Beschreibung gilt nur für Benutzertext, Kommentar, Benutzer-URL und Liedtext.</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Hinzufügen", value: true, primary: true }],
    onMount: (b) => {
      const sel = $("#afField", b), desc = $("#afDesc", b);
      sel.value = preset.fid || "TXXX";
      const upd = () => { const d = sel.selectedOptions[0].dataset.desc === "1"; desc.disabled = !d; desc.parentElement && (desc.style.opacity = d ? 1 : 0.4); };
      sel.addEventListener("change", upd);
      upd();
    },
    collect: (b) => {
      const val = $("#afVal", b).value;
      if (!val.trim()) { $("#afVal", b).focus(); toast("Bitte einen Wert eingeben."); return false; }
      return { side: sides ? (b.querySelector('input[name="af-side"]:checked') || {}).value : null,
               fid: $("#afField", b).value, desc: $("#afDesc", b).value, value: val };
    },
  });
}

async function addFieldCompare(sidePreset) {
  const v = S.view;
  if (!v || !(v.left || v.right)) return;
  const sides = [["L", "Links", !!v.left], ["R", "Rechts", !!v.right]];
  if (sidePreset) sides.sort((a) => (a[0] === sidePreset ? -1 : 1));
  const r = await addFieldForm(sides);
  if (!r) return;
  let st = await call("add_field", r.side, r.fid, r.desc, r.value, false);
  if (st.ask) {
    const go = await dialog({ title: "Feld existiert schon", text: `„${st.ask.label}“ ist schon vorhanden. Ersetzen?`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Ersetzen", value: true, primary: true }] });
    if (!go) return;
    st = await call("add_field", r.side, r.fid, r.desc, r.value, true);
  }
  if (st.error) { toast(st.error); return; }
  applyState(st);
  if (st.added) { S.sel = new Set([st.added]); S.anchor = st.added; paintSelection(); $(`#tbody .tr[data-key="${CSS.escape(st.added)}"]`)?.scrollIntoView({ block: "nearest" }); }
}

// ====================================================================== Sammelkopie
async function bulkCopy(direction) {
  const idx = [...S.pairSel];
  const info_ = await call("bulk_keys", idx, direction);
  if (!info_.pairs) { toast("Bitte Paare markieren, bei denen beide Seiten vorhanden sind."); return; }
  const keys = info_.keys;
  const res = await modal({
    title: `Sammelkopie ${direction === "lr" ? "links → rechts" : "rechts → links"} · ${info_.pairs} Paar(e)`,
    wide: true,
    html: `<p class="muted" style="margin:0">Welche Felder sollen in allen markierten Paaren übernommen werden?</p>
      <div class="quick"><button class="ghost sm" data-q="all">Alle</button><button class="ghost sm" data-q="none">Keine</button>
      <button class="ghost sm" data-q="std">Standardfelder</button><button class="ghost sm" data-q="imp">Wichtige</button></div>
      <div class="checklist">${keys.map((k, n) => `<label><input type="checkbox" data-n="${n}" ${k.trivial ? "" : "checked"}> ${esc(k.label)}</label>`).join("")}</div>
      <label class="check"><input type="checkbox" id="bulkDel"> Felder, die in der Quelle fehlen, im Ziel entfernen</label>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => b.querySelector(".quick").addEventListener("click", (e) => {
      const q = e.target.dataset.q; if (!q) return;
      $$("input[data-n]", b).forEach((c) => { const k = keys[+c.dataset.n]; c.checked = q === "all" || (q === "std" && k.standard) || (q === "imp" && !k.trivial); });
    }),
    collect: (b) => ({ keys: $$("input[data-n]:checked", b).map((c) => keys[+c.dataset.n].key), del: $("#bulkDel", b).checked }),
  });
  if (!res) return;
  if (!res.keys.length) { toast("Keine Felder gewählt."); return; }
  await refreshAll(await call("bulk_apply", idx, direction, res.keys, res.del));
}

function renderBulkBar() {
  const n = S.pairSel ? S.pairSel.size : 0;
  $("#bulkBar").hidden = n < 2;
  $("#bulkInfo").textContent = `${n} Paare markiert`;
}

// ====================================================================== Bilder im Vergleich
function coverMenu(e, side, key, exists) {
  e.preventDefault();
  const items = [];
  if (exists) {
    items.push({ label: "Bild anzeigen", icon: ICON.image, run: () => openCover(side, key) });
    items.push({ label: "Bild ersetzen …", icon: ICON.edit, run: () => coverReplace(side, key) });
    items.push({ label: "Bild exportieren …", icon: ICON.copy, run: () => coverExport(side, key) });
    items.push({ label: "Bild entfernen", icon: ICON.trash, run: async () => applyState(await call("cover_remove", side, key)) });
  } else {
    items.push({ label: "Cover hinzufügen …", icon: ICON.image, run: () => coverReplace(side, "APIC:3") });
  }
  showMenu(e.clientX, e.clientY, items);
}

async function coverReplace(side, key) {
  const st = await call("cover_replace", side, key, "");
  if (st) applyState(st);
  else if (!S.settings.native) toast("Im Browser-Modus ist kein Dateidialog verfügbar – bitte das App-Fenster verwenden.");
}

async function coverExport(side, key) {
  const r = await call("cover_export", side, key);
  if (r.ok) status(`Bild gespeichert: ${r.path}`, "ok");
  else if (r.error) toast(r.error);
}

// ====================================================================== Tag-Fixer
const FX = { settings: null, timer: null };

async function fixerShow(scopePreset) {
  FX.settings = await call("fixer_settings");
  const st = FX.settings, sv = st.saved, c = st.counts;
  const nSel = S.pairSel ? S.pairSel.size : 0;
  const tg = typeof TG !== "undefined" ? TG : { sel: new Set(), rows: [] };
  const scopes = [
    ["pair", `Aktuelles Paar (beide Seiten)`, c.pair > 0],
    ["L", "Aktuelles Paar – nur links", !!(S.view && S.view.left)],
    ["R", "Aktuelles Paar – nur rechts", !!(S.view && S.view.right)],
    ["sel", `Markierte Paare (${nSel})`, nSel > 0],
    ["all", `Alle Dateien im Vergleich (${fmtN(c.all)})`, c.all > 0],
    ["tag_sel", `Tagger: markierte Dateien (${tg.sel.size})`, tg.sel.size > 0],
    ["tag_all", `Tagger: alle Dateien (${fmtN(c.tag_all)})`, c.tag_all > 0],
  ];
  const def = scopePreset || (scopes.find((x) => x[0] === FX.scope && x[2]) || scopes.find((x) => x[2]) || scopes[0])[0];
  $("#fxOpts").innerHTML = `
    <h4>Dateien</h4>${scopes.map(([v, l, en]) => `<label class="opt${en ? "" : " dim"}"><input type="radio" name="fx-scope" value="${v}" ${en ? "" : "disabled"} ${v === def ? "checked" : ""}> ${esc(l)}</label>`).join("")}
    <h4>Felder</h4><div class="fx-fields">${st.fields.map(([k, l]) => `<label class="opt"><input type="checkbox" data-field="${k}" ${sv.fields.includes(k) ? "checked" : ""}> ${esc(l)}</label>`).join("")}</div>
    <label class="opt"><input type="checkbox" id="fxAllText" ${sv.all_text ? "checked" : ""}> Alle Textfelder (inkl. Benutzertexte)</label>
    <h4>Als Trenner erkennen</h4>${st.separators.map(([l, sep], n) => `<label class="opt"><input type="checkbox" data-sep="${n}" ${sv.seps.includes(sep) ? "checked" : ""}> ${esc(l)}</label>`).join("")}
    <h4>Ausgabe</h4>
    <label class="opt"><input type="radio" name="fx-mode" value="sep" ${sv.mode !== "v24" ? "checked" : ""}> Trennzeichen <input class="sep-in" id="fxSep" value="${esc(sv.sep)}" aria-label="Trennzeichen"></label>
    <label class="opt"><input type="radio" name="fx-mode" value="v24" ${sv.mode === "v24" ? "checked" : ""}> ID3v2.4-Standard (echte Mehrfachwerte)</label>
    <label class="opt" style="padding-left:24px"><input type="checkbox" id="fxUpgrade" ${sv.upgrade ? "checked" : ""}> v2.3-Dateien dafür auf v2.4 umstellen</label>
    <label class="opt"><input type="checkbox" id="fxDedupe" ${sv.dedupe ? "checked" : ""}> Doppelte Werte entfernen</label>`;
  $("#fxOpts").oninput = () => { clearTimeout(FX.timer); FX.timer = setTimeout(fixerPreview, 200); };
  await fixerPreview();
}

function fixerOptions() {
  const o = $("#fxOpts");
  return {
    scope: (o.querySelector('input[name="fx-scope"]:checked') || {}).value || "pair",
    pairs: [...(S.pairSel || [])], tag_idx: typeof TG !== "undefined" ? [...TG.sel] : [],
    fields: $$("input[data-field]:checked", o).map((c) => c.dataset.field),
    all_text: $("#fxAllText").checked,
    seps: $$("input[data-sep]:checked", o).map((c) => FX.settings.separators[+c.dataset.sep][1]),
    mode: (o.querySelector('input[name="fx-mode"]:checked') || {}).value || "sep",
    sep: $("#fxSep").value, upgrade: $("#fxUpgrade").checked, dedupe: $("#fxDedupe").checked,
  };
}

async function fixerPreview() {
  const o = fixerOptions();
  FX.scope = o.scope;
  $("#fxUpgrade").disabled = o.mode !== "v24";
  const r = await call("fixer_preview", o);
  $("#fxCount").textContent = `${fmtN(r.count)} Änderung(en) in ${fmtN(r.files)} von ${fmtN(r.scope_files)} Datei(en)`;
  $("#fxApply").textContent = r.count ? `Anwenden (${fmtN(r.count)})` : "Anwenden";
  $("#fxApply").disabled = !r.count;
  $("#fxTable").innerHTML = r.rows.length
    ? `<table><thead><tr><th>Datei</th><th>Feld</th><th>Vorher</th><th>Nachher</th></tr></thead><tbody>${r.rows.map((x) => `<tr><td>${esc(x.file)}</td><td>${esc(x.label)}</td><td class="old">${esc(x.old)}</td><td class="new">${esc(x.new)}</td></tr>`).join("")}</tbody></table>${r.count > r.rows.length ? `<div class="empty">… und ${fmtN(r.count - r.rows.length)} weitere</div>` : ""}`
    : `<div class="empty">${r.scope_files ? "Nichts zu ändern – alles schon einheitlich." : "Keine Dateien im gewählten Bereich. Erst im Vergleich oder Tagger Dateien laden."}</div>`;
}

async function fixerApply() {
  const st = await call("fixer_apply", fixerOptions());
  await refreshAll(st);
  if (st.message) status(st.message, st.tone);
  await fixerPreview();
}

// ====================================================================== Sicherungen
const BK = { data: null, cur: null, files: [], sel: new Set() };

async function backupsShow() {
  BK.data = await call("backups");
  const d = BK.data;
  $("#bkEnabled").checked = d.enabled;
  const mb = (b) => (b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1).replace(".", ",")} MB`);
  $("#bkPath").textContent = `Ordner: ${d.folder} · ${d.list.length} Sicherung(en), ${mb(d.total)}`;
  $("#bkList").innerHTML = d.list.length
    ? d.list.map((b, n) => `<button class="bk-item${BK.cur && BK.cur.path === b.path ? " cur" : ""}" data-n="${n}"><span class="t">${esc(b.created)}</span><span class="s">${esc(b.label)} · ${b.count} Datei(en) · ${mb(b.bytes)}</span></button>`).join("")
    : '<div class="tg-empty">Noch keine Sicherungen. Sie entstehen automatisch beim Speichern.</div>';
  if (BK.cur && !d.list.some((b) => b.path === BK.cur.path)) BK.cur = null;
  if (!BK.cur) { $("#bkFiles").innerHTML = '<div class="tg-empty">Links eine Sicherung wählen.</div>'; $("#bkTitle").textContent = "Dateien"; $("#bkInfo").textContent = ""; }
  backupButtons();
}

function backupButtons() {
  $("#bkDelete").disabled = !BK.cur;
  $("#bkRestoreAll").disabled = !BK.cur || !BK.files.some((f) => f.code === "ok" || f.code === "audio");
  $("#bkRestoreSel").disabled = !BK.cur || !BK.sel.size;
  $("#bkRestoreSel").textContent = BK.sel.size ? `Markierte wiederherstellen (${BK.sel.size})` : "Markierte wiederherstellen";
}

async function backupSelect(n) {
  BK.cur = BK.data.list[n];
  BK.files = [];
  BK.sel.clear();
  $$("#bkList .bk-item").forEach((b) => b.classList.toggle("cur", +b.dataset.n === n));
  $("#bkTitle").textContent = `Dateien · ${BK.cur.created}`;
  $("#bkFiles").innerHTML = '<div class="tg-empty">Prüfe Dateien …</div>';
  const res = await runTask(call("start_backup_check", BK.cur.path), "Sicherung prüfen");
  if (!res || res.cancelled) return;
  BK.files = res.files;
  renderBackupFiles();
}

function renderBackupFiles() {
  const f = BK.files;
  const counts = f.reduce((a, x) => ((a[x.code] = (a[x.code] || 0) + 1), a), {});
  $("#bkInfo").textContent = `${f.length} Datei(en) · ${counts.ok || 0} wiederherstellbar · ${counts.same || 0} gleich` + (counts.missing ? ` · ${counts.missing} fehlen` : "") + (counts.audio ? ` · ${counts.audio} Audio geändert` : "");
  const chg = (x) => x.changes === null || x.changes === undefined ? '<span class="muted">–</span>'
    : !x.changes ? '<span class="muted">keine</span>'
    : `<button class="bk-diff" data-diff="${x.id}" title="Änderungen ansehen"><b>${x.changes}</b> <span>${esc(x.fields.join(", "))}${x.more ? ` +${x.more}` : ""}</span></button>`;
  $("#bkFiles").innerHTML = `<div class="fx-table"><table><thead><tr><th></th><th>Datei</th><th>Geänderte Felder</th><th>Status</th><th>Ordner</th></tr></thead><tbody>${f.map((x) => `<tr class="click${BK.sel.has(x.id) ? " sel" : ""}" data-id="${x.id}"><td><input type="checkbox" ${BK.sel.has(x.id) ? "checked" : ""} ${x.code === "ok" || x.code === "audio" ? "" : "disabled"} aria-label="${esc(x.name)} markieren"></td><td>${esc(x.name)}${x.loaded_modified ? ' <span class="muted sm">(ungespeicherte Änderungen im Programm)</span>' : ""}</td><td class="bk-chg">${chg(x)}</td><td class="st-${x.code}">${esc(x.text)}</td><td class="old" title="${esc(x.dir)}">…/${esc(x.dir.split(/[\\/]/).slice(-2).join("/"))}</td></tr>`).join("")}</tbody></table></div>`;
  backupButtons();
}

// Änderungs-Viewer: gesicherte Tags (vorher) ↔ heutige Datei (jetzt)
async function backupDiff(id) {
  const withChanges = BK.files.filter((x) => x.changes);
  for (;;) {
    const d = await call("backup_diff", BK.cur.path, id);
    const pos = withChanges.findIndex((x) => x.id === id);
    const stLabel = { changed: "geändert", added: "neu", removed: "entfernt" };
    const cell = (text, spans) => valueHtml({ present: true, text, spans, links: [] }, "diff");
    const verChanged = d.version[0] !== d.version[1] && d.version[1];
    const html = `<div class="bk-dhead"><div><b>${esc(d.name)}</b><div class="muted sm" title="${esc(d.path)}">${esc(d.path)}</div></div>
        <div class="muted sm">Sicherung ${esc(d.created)}${d.label ? ` · ${esc(d.label)}` : ""}</div></div>
      ${d.unsaved ? '<div class="hint st-missing">Diese Datei hat zusätzlich ungespeicherte Änderungen im Programm – verglichen wird mit dem gespeicherten Stand.</div>' : ""}
      ${verChanged ? `<div class="hint">ID3-Version: ${esc(d.version[0])} → ${esc(d.version[1])}</div>` : ""}
      ${d.missing ? '<div class="empty">Die Datei gibt es nicht mehr.</div>' : !d.rows.length ? '<div class="empty">Keine Unterschiede – die Tags entsprechen der Sicherung.</div>' : `
      <div class="fx-table bk-dtable"><table><thead><tr><th>Feld</th><th>Vorher (Sicherung)</th><th>Jetzt</th></tr></thead><tbody>
      ${d.rows.map((r) => `<tr class="bk-${r.state}"><td><span class="bk-st">${stLabel[r.state]}</span> ${esc(r.label)}<div class="faint sm">${esc(r.key)}</div></td>
        <td class="v">${r.state === "added" ? '<span class="muted">— fehlte —</span>' : cell(r.old, r.spans_old)}</td>
        <td class="v">${r.state === "removed" ? '<span class="muted">— entfernt —</span>' : cell(r.new, r.spans_new)}</td></tr>`).join("")}
      </tbody></table></div>`}
      <div class="muted sm">${d.rows.length} Feld(er) unterschiedlich${pos >= 0 ? ` · Datei ${pos + 1} von ${withChanges.length} mit Änderungen` : ""}</div>`;
    const canRestore = !d.missing && d.rows.length;
    const btns = [{ label: "‹", value: "prev" }, { label: "›", value: "next" }, { label: "Schliessen", value: null }];
    if (canRestore) btns.push({ label: "Diese Datei wiederherstellen", value: "restore", primary: true });
    const v = await modal({ title: "Änderungen seit der Sicherung", wide: true, html, buttons: btns,
      onMount: () => {
        const bs = $$("#mBtns button");
        bs[0].disabled = pos <= 0; bs[1].disabled = pos < 0 || pos >= withChanges.length - 1;
        bs[0].title = "Vorherige Datei mit Änderungen"; bs[1].title = "Nächste Datei mit Änderungen";
        bs[0].classList.add("bk-nav"); bs[1].classList.add("bk-nav");
      } });
    if (v === "prev" && pos > 0) { id = withChanges[pos - 1].id; continue; }
    if (v === "next" && pos >= 0 && pos < withChanges.length - 1) { id = withChanges[pos + 1].id; continue; }
    if (v === "restore") await backupRestore([id]);
    return;
  }
}

async function backupRestore(ids) {
  const b = BK.cur;
  const entries = BK.files.filter((x) => (ids ? ids.includes(x.id) : x.code === "ok" || x.code === "audio"));
  if (!entries.length) return;
  const dirty = entries.filter((x) => x.loaded_modified).length;
  const ok = await dialog({
    title: "Wiederherstellen",
    text: `${entries.length} Datei(en) auf den Stand vom ${b.created} zurücksetzen?\n\nDer aktuelle Zustand wird vorher selbst gesichert – das lässt sich also wieder rückgängig machen.` +
      (dirty ? `\n\nAchtung: ${dirty} dieser Datei(en) haben ungespeicherte Änderungen im Programm, die dabei verworfen werden.` : ""),
    buttons: [{ label: "Abbrechen", value: null }, { label: "Wiederherstellen", value: true, primary: true }],
  });
  if (!ok) return;
  let force = false;
  const audio = entries.filter((x) => x.code === "audio").length;
  if (audio) {
    force = !!(await dialog({ title: "Audiodaten verändert", text: `Bei ${audio} Datei(en) haben sich die Audiodaten verändert (evtl. eine andere Datei mit gleichem Namen).\n\nTrotzdem die alten Tags dort einsetzen?`,
      buttons: [{ label: "Nein, überspringen", value: null, primary: true }, { label: "Ja, trotzdem", value: true }] }));
  }
  const res = await runTask(call("start_restore", b.path, entries.map((x) => x.id), force), "Wiederherstellen");
  if (!res) return;
  await refreshAll();
  let text = `${res.restored} Datei(en) wiederhergestellt.`;
  if (res.skipped.length) text += `\n\n${res.skipped.length} übersprungen:\n` + res.skipped.slice(0, 15).map((x) => `• ${x.name} – ${x.text}`).join("\n");
  status(`${res.restored} Datei(en) aus Sicherung wiederhergestellt.`, "ok");
  await info("Wiederherstellen", text);
  await backupsShow();
  const n = BK.data.list.findIndex((x) => x.path === b.path);
  if (n >= 0) await backupSelect(n);
}

async function backupDelete() {
  const b = BK.cur;
  const ok = await dialog({ title: "Sicherung löschen", text: `Sicherung vom ${b.created} (${b.count} Datei(en)) endgültig löschen?\n\nDie MP3-Dateien selbst bleiben unverändert.`,
    buttons: [{ label: "Abbrechen", value: null, primary: true }, { label: "Löschen", value: true }] });
  if (!ok) return;
  const r = await call("delete_backup", b.path);
  if (!r.ok) { await info("Löschen fehlgeschlagen", r.error); return; }
  BK.cur = null; BK.files = []; BK.sel.clear();
  await backupsShow();
}

// ====================================================================== Ereignisse
(function bindModules() {
  $("#addFieldBtn").addEventListener("click", () => addFieldCompare());
  $$("[data-bulk]").forEach((b) => b.addEventListener("click", () => bulkCopy(b.dataset.bulk)));
  $("#bulkClear").addEventListener("click", () => { S.pairSel.clear(); renderBulkBar(); drawPairWindow(); });
  const coverHandler = (e) => {
    const c = e.target.closest("[data-cover]");
    if (c) { const [side, key] = c.dataset.cover.split("|"); coverMenu(e, side, key, true); return; }
    const add = e.target.closest("[data-addcover]");
    if (add) coverMenu(e, add.dataset.addcover, "APIC:3", false);
  };
  $("#headL").addEventListener("contextmenu", coverHandler);
  $("#headR").addEventListener("contextmenu", coverHandler);
  ["#headL", "#headR"].forEach((s) => $(s).addEventListener("click", (e) => { const add = e.target.closest("[data-addcover]"); if (add) coverReplace(add.dataset.addcover, "APIC:3"); }));
  $("#fxApply").addEventListener("click", fixerApply);
  $("#bkEnabled").addEventListener("change", async (e) => { BK.data = await call("set_backup", e.target.checked, null); toast(e.target.checked ? "Automatische Sicherung ist an." : "Achtung: Vor dem Speichern wird nicht mehr gesichert."); });
  $("#bkFolder").addEventListener("click", async () => { const d = await call("backup_pick_folder"); if (d) { BK.cur = null; await backupsShow(); } else if (!S.settings.native) toast("Im Browser-Modus ist kein Ordnerdialog verfügbar."); });
  $("#bkOpen").addEventListener("click", () => call("open_folder", BK.data && BK.data.folder));
  $("#bkList").addEventListener("click", (e) => { const b = e.target.closest(".bk-item"); if (b) backupSelect(+b.dataset.n); });
  $("#bkFiles").addEventListener("click", (e) => {
    const dv = e.target.closest("[data-diff]");
    if (dv) { backupDiff(+dv.dataset.diff); return; }
    const tr = e.target.closest("tr[data-id]"); if (!tr) return;
    const id = +tr.dataset.id, f = BK.files.find((x) => x.id === id);
    if (!f || !(f.code === "ok" || f.code === "audio")) return;
    BK.sel.has(id) ? BK.sel.delete(id) : BK.sel.add(id);
    renderBackupFiles();
  });
  $("#bkRestoreAll").addEventListener("click", () => backupRestore(null));
  $("#bkRestoreSel").addEventListener("click", () => backupRestore([...BK.sel]));
  $("#bkDelete").addEventListener("click", backupDelete);
})();
