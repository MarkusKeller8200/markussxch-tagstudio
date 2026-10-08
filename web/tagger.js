/* MarKusSXCH TagStudio – Tagger: Dateien eines Ordners auflisten, einzeln oder gemeinsam bearbeiten,
   Tags aus Dateinamen, Umbenennen, Spurnummern, Cover. Nutzt Funktionen aus app.js / modules.js. */
"use strict";

const TG = { settings: null, loaded: false, rows: [], order: [], sel: new Set(), anchor: null,
  sort: { col: "name", dir: 1 }, detail: null, editing: false };
const TG_COLS = [["m", ""], ["name", "Datei"], ["TIT2", "Titel"], ["TPE1", "Künstler"], ["TALB", "Album"],
  ["TRCK", "Spur"], ["TDRC", "Jahr"], ["TCON", "Genre"]];
const TG_ROW = 40;

// ---------------------------------------------------------------------- Anzeigen / Laden
async function taggerShow() {
  if (!TG.settings) {
    TG.settings = await call("tagger_settings");
    $("#histTg").innerHTML = TG.settings.hist.map((h) => `<option value="${esc(h)}"></option>`).join("");
    $("#tgPath").value = TG.settings.hist[0] || "";
    $("#tgRec").checked = !!TG.settings.recursive;
    renderTgHead();
    renderTgEditor();
  }
  if (!TG.loaded) drawTgList();
  else await taggerRefresh();
  $("#tgTable").focus();
}

async function taggerLoad() {
  if (!(await confirmDiscard())) return;
  const path = $("#tgPath").value.trim();
  const res = await runTask(call("start_tag_load", path, $("#tgRec").checked), "Dateien einlesen");
  if (!res) return;
  if (res.cancelled) { status("Einlesen abgebrochen.", "warn"); return; }
  TG.settings = await call("tagger_settings");
  $("#histTg").innerHTML = TG.settings.hist.map((h) => `<option value="${esc(h)}"></option>`).join("");
  TG.loaded = true;
  TG.rows = (await call("tag_rows")).rows;
  TG.sel = new Set(TG.rows.length ? [0] : []);
  TG.anchor = TG.rows.length ? 0 : null;
  tgApplyOrder();
  await tgLoadDetail();
  if (S.pairs.length) await refreshAll();  // gemeinsames Register: Vergleich frisch halten
  status(`${fmtN(res.files)} Datei(en) im Tagger.`, res.files ? "ok" : "warn");
  if (res.errors.length) await info(`${res.errors.length} Datei(en) nicht lesbar`, res.errors.slice(0, 30).join("\n"));
}

/** Nach Änderungen anderswo (Vergleich, Undo, Speichern …) */
async function taggerRefresh() {
  if (!TG.loaded) return;
  TG.rows = (await call("tag_rows")).rows;
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
  if (d.errors && d.errors.length) info("Fehler beim Umbenennen", d.errors.join("\n"));
  return d;
}

// ---------------------------------------------------------------------- Liste
function trackNum(v) { const m = String(v || "").match(/^\s*(\d+)/); return m ? +m[1] : Infinity; }

function tgApplyOrder() {
  const q = ($("#tgQuery").value || "").trim().toLowerCase();
  const { col, dir } = TG.sort;
  let idx = TG.rows.map((r) => r.i);
  if (q) idx = idx.filter((i) => { const r = TG.rows[i]; return [r.rel, r.TIT2, r.TPE1, r.TALB, r.TCON, r.TPE2].some((v) => (v || "").toLowerCase().includes(q)); });
  const key = (r) => (col === "name" ? r.rel : col === "TRCK" ? trackNum(r.TPOS) * 10000 + trackNum(r.TRCK) : (r[col] || ""));
  idx.sort((a, b) => {
    const x = key(TG.rows[a]), y = key(TG.rows[b]);
    const c = typeof x === "number" ? x - y : String(x).localeCompare(String(y), "de", { numeric: true, sensitivity: "base" });
    return c * dir || a - b;
  });
  TG.order = idx;
  $("#tgCount").textContent = TG.rows.length ? (idx.length === TG.rows.length ? `${fmtN(idx.length)} Dateien` : `${fmtN(idx.length)} von ${fmtN(TG.rows.length)}`) + (TG.sel.size > 1 ? ` · ${TG.sel.size} markiert` : "") : "";
  $("#tgInner").style.height = idx.length * TG_ROW + "px";
  drawTgList();
}

function renderTgHead() {
  $("#tgHead").innerHTML = TG_COLS.map(([k, l]) => k === "m" ? "<span></span>"
    : `<button data-sort="${k}" class="${TG.sort.col === k ? "on" : ""}">${esc(l)}${TG.sort.col === k ? (TG.sort.dir > 0 ? " ▴" : " ▾") : ""}</button>`).join("");
}

function drawTgList() {
  const sc = $("#tgScroll"), inner = $("#tgInner");
  if (!TG.loaded) { inner.innerHTML = '<div class="tg-empty">Oben einen Ordner oder eine MP3-Datei wählen und auf <b>Einlesen</b> klicken.</div>'; inner.style.height = ""; return; }
  if (!TG.order.length) { inner.innerHTML = `<div class="tg-empty">${TG.rows.length ? "Keine Datei passt zum Filter." : "Keine MP3-Dateien gefunden."}</div>`; return; }
  const first = Math.max(0, Math.floor(sc.scrollTop / TG_ROW) - 6);
  const last = Math.min(TG.order.length, Math.ceil((sc.scrollTop + sc.clientHeight) / TG_ROW) + 6);
  let h = "";
  for (let k = first; k < last; k++) {
    const r = TG.rows[TG.order[k]];
    h += `<div class="tg-row${TG.sel.has(r.i) ? " sel" : ""}" style="top:${k * TG_ROW}px" data-i="${r.i}" title="${esc(r.rel)}">
      <span>${r.modified ? '<span class="m" title="ungespeichert"></span>' : ""}</span>
      <span class="fn">${esc(r.rel)}</span><span>${esc(r.TIT2)}</span><span>${esc(r.TPE1)}</span><span>${esc(r.TALB)}</span>
      <span>${esc(r.TRCK)}</span><span>${esc(r.TDRC)}</span><span>${esc(r.TCON)}</span></div>`;
  }
  inner.innerHTML = h;
}

function tgScrollTo(i) {
  const k = TG.order.indexOf(i), sc = $("#tgScroll");
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
    return `<label for="tgf-${k}">${esc(label)}</label><input id="tgf-${k}" data-key="${k}" value="${esc(v.value)}" ${v.mixed ? 'placeholder="‹verschieden›"' : ""} spellcheck="false">`;
  }).join("");
  const more = one && d.fields.length ? `<h4 style="margin:4px 0 0">Weitere Felder</h4><div class="tg-more">${d.fields.map((f) => `
      <div class="tg-f" data-key="${esc(f.key)}"><span class="k" title="${esc(f.key)}">${f.mod ? '<span class="m" style="display:inline-block;width:7px;height:7px;border-radius:99px;background:var(--acc);margin-right:6px"></span>' : ""}${esc(f.label)}</span>
      <span class="v${f.editable ? "" : " noedit"}">${f.xml ? `<button class="xml-badge${f.xml === "view" ? " view" : ""}" data-txml="1">XML</button>` : ""}${esc(f.text.length > 160 ? f.text.slice(0, 160) + " …" : f.text)}</span>
      <button class="x" data-tdel="1" title="Feld entfernen" aria-label="${esc(f.label)} entfernen"><svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div>`).join("")}</div>` : "";
  const act = document.activeElement && box.contains(document.activeElement) ? document.activeElement.id : null;
  box.innerHTML = `${head}
    <div class="tg-cover"><button class="cover" id="tgCoverBig" title="${esc(c.desc || (c.state === "mixed" ? "unterschiedliche Cover" : "kein Cover"))}">${coverImg}</button>
      <div class="tg-cover-btns"><button class="ghost sm" id="tgCoverSet">Cover wählen …</button><button class="ghost sm" id="tgCoverDel" ${c.state === "none" ? "disabled" : ""}>Cover entfernen</button>
      <span class="hint">${esc(c.desc || (c.state === "mixed" ? "unterschiedlich" : "kein Cover"))}</span></div></div>
    <div class="tg-form">${form}
      <label for="tgVer">ID3-Version</label><select id="tgVer" class="inp" style="height:36px"><option value="3">ID3v2.3 (verbreitet)</option><option value="4">ID3v2.4 (Mehrfachwerte)</option>${d.version ? "" : '<option value="" selected>verschieden</option>'}</select>
    </div>
    <div class="tg-tools">
      <button class="ghost" id="tgFromName">Tags aus Dateiname …</button>
      <button class="ghost" id="tgRename">Dateien umbenennen …</button>
      <button class="ghost" id="tgNumber" ${d.count > 1 ? "" : "disabled"}>Spurnummern …</button>
      <button class="ghost" id="tgAddField">Feld hinzufügen …</button>
      <button class="ghost" id="tgFixer">Tag-Fixer …</button>
      ${one ? '<button class="ghost" id="tgReveal">' + (IS_MAC ? "Im Finder zeigen" : "Im Explorer zeigen") + "</button>" : ""}
    </div>${more}`;
  if (d.version) $("#tgVer").value = String(d.version);
  if (act && $("#" + act)) { const el = $("#" + act); el.focus(); if (el.setSelectionRange && el.value) el.setSelectionRange(el.value.length, el.value.length); }
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
  if (!f.editable) { toast(key.startsWith("APIC") ? "Bilder über „Cover wählen …“ ändern." : "Dieses Feld kann nicht als Text bearbeitet werden."); return; }
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
  $("#tgInner").addEventListener("click", (e) => { const r = e.target.closest(".tg-row"); if (r) tgSelect(+r.dataset.i, e); });
  $("#tgTable").addEventListener("keydown", (e) => {
    if (!TG.order.length) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") { e.preventDefault(); e.stopPropagation(); TG.sel = new Set(TG.order); tgApplyOrder(); tgLoadDetail(); return; }
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
  });
  ed.addEventListener("click", async (e) => {
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
    const row = e.target.closest(".tg-f");
    if (row && e.target.closest("[data-tdel]")) taggerApplyDetail(await call("tag_remove", [idx[0]], [row.dataset.key]));
    else if (row && e.target.closest("[data-txml]")) openXml(null, row.dataset.key, { tag: idx[0] });
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
