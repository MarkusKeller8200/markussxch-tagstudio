/* MarKusSXCH TagStudio – Tagger: Dateien eines Ordners auflisten, einzeln oder gemeinsam bearbeiten,
   Tags aus Dateinamen, Umbenennen, Spurnummern, Cover. Nutzt Funktionen aus app.js / modules.js. */
"use strict";

const TG = { settings: null, loaded: false, rows: [], order: [], sel: new Set(), anchor: null,
  sort: { col: "name", dir: 1 }, detail: null, editing: false };
const TG_COLS = [["m", ""], ["name", "Datei"], ["TIT2", "Titel"], ["TPE1", "Künstler"], ["TALB", "Album"],
  ["TRCK", "Spur"], ["TDRC", "Jahr"], ["TCON", "Genre"], ["camelot", "Tonart"]];
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
  if (d.errors && d.errors.length) info("Fehler", d.errors.join("\n"));
  return d;
}

// ---------------------------------------------------------------------- Liste
function trackNum(v) { const m = String(v || "").match(/^\s*(\d+)/); return m ? +m[1] : Infinity; }

function tgApplyOrder() {
  const q = ($("#tgQuery").value || "").trim().toLowerCase();
  const { col, dir } = TG.sort;
  let idx = TG.rows.map((r) => r.i);
  if (q) idx = idx.filter((i) => { const r = TG.rows[i]; return [r.rel, r.TIT2, r.TPE1, r.TALB, r.TCON, r.TPE2].some((v) => (v || "").toLowerCase().includes(q)); });
  const key = (r) => (col === "name" ? r.rel : col === "camelot" ? keySortValue(r.camelot) : col === "TRCK" ? trackNum(r.TPOS) * 10000 + trackNum(r.TRCK) : (r[col] || ""));
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
  const sel1 = TG.sel.size === 1 ? TG.rows[[...TG.sel][0]] : null;
  const fit = new Set(sel1 && sel1.camelot ? keyCompat(sel1.camelot) : []);
  for (let k = first; k < last; k++) {
    const r = TG.rows[TG.order[k]];
    h += `<div class="tg-row${TG.sel.has(r.i) ? " sel" : ""}" style="top:${k * TG_ROW}px" data-i="${r.i}" title="${esc(r.rel)}">
      <span>${r.modified ? '<span class="m" title="ungespeichert"></span>' : ""}</span>
      <span class="fn">${esc(r.rel)}</span><span>${esc(r.TIT2)}</span><span>${esc(r.TPE1)}</span><span>${esc(r.TALB)}</span>
      <span>${esc(r.TRCK)}</span><span>${esc(r.TDRC)}</span><span>${esc(r.TCON)}</span>
      <span title="${esc(r.TKEY)}">${r.camelot ? keyBadge(r.camelot, fit.size && !TG.sel.has(r.i) ? (fit.has(r.camelot) ? "fit" : "") : "") : `<span class="mx">${esc(r.TKEY)}</span>`}</span></div>`;
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
    const inp = `<input id="tgf-${k}" data-key="${k}" value="${esc(v.value)}" ${v.mixed ? 'placeholder="‹verschieden›"' : ""} spellcheck="false">`;
    if (k === "TKEY") return `<label for="tgf-${k}">${esc(label)}</label><div class="key-inp">${inp}<button class="key-btn${KW.open ? " on" : ""}" id="tgKeyBtn" title="Camelot-Rad öffnen" aria-label="Camelot-Rad öffnen">${v.camelot ? keyBadge(v.camelot) : '<svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4.5"/><path d="M12 3v4.5M12 16.5V21M3 12h4.5M16.5 12H21"/></svg>'}</button></div>`;
    const u = !v.mixed && firstUrl(v.value);
    if (u) return `<label for="tgf-${k}">${esc(label)}</label><div class="url-inp">${inp}<a class="url-btn" data-url="${esc(u)}" title="${esc(u)} öffnen" aria-label="Link öffnen"><svg class="i" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg></a></div>`;
    return `<label for="tgf-${k}">${esc(label)}</label>${inp}`;
  }).join("");
  const PEN = '<svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';
  const DEL = '<svg class="i" viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
  const more = one && d.fields.length ? `<h4 style="margin:4px 0 0">Weitere Felder <span class="muted sm" style="font-weight:400">${d.fields.length}</span></h4>
    <div class="tg-more">
      <div class="tg-more-head"><span class="k">Feld<span class="col-grip" id="tgMoreGrip" role="separator" aria-orientation="vertical" aria-label="Breite der Feldnamen" tabindex="0" title="Ziehen: Breite ändern · Doppelklick: Standardbreite"></span></span><span>Wert</span><span></span></div>
      ${d.fields.map((f) => {
        const full = f.edit || f.text, ml = f.multiline;
        const shown = ml ? full : (f.text.length > 160 ? f.text.slice(0, 160) + " …" : f.text);
        return `<div class="tg-f" data-key="${esc(f.key)}"><span class="k" title="${esc(f.label + "\n" + f.key)}">${f.mod ? '<span class="m" style="display:inline-block;width:7px;height:7px;border-radius:99px;background:var(--acc);margin-right:6px"></span>' : ""}${esc(f.label)}</span>
      <span class="v${f.editable ? "" : " noedit"}${ml ? " ml" : ""}" title="${f.editable ? "Doppelklick: bearbeiten" : ""}">${f.xml ? `<button class="xml-badge${f.xml === "view" ? " view" : ""}" data-txml="1">XML</button>` : ""}${linkify(shown)}</span>
      <span class="b">${f.editable || f.xml ? `<button class="x" data-tedit="1" title="Im Editor bearbeiten" aria-label="${esc(f.label)} bearbeiten">${PEN}</button>` : ""}<button class="x del" data-tdel="1" title="Feld entfernen" aria-label="${esc(f.label)} entfernen">${DEL}</button></span></div>`;
      }).join("")}</div>` : "";
  const act = document.activeElement && box.contains(document.activeElement) ? document.activeElement.id : null;
  box.innerHTML = `${head}
    <div class="tg-cover"><button class="cover" id="tgCoverBig" title="${esc(c.desc || (c.state === "mixed" ? "unterschiedliche Cover" : "kein Cover"))}">${coverImg}</button>
      <div class="tg-cover-btns"><button class="ghost sm" id="tgCoverSet">Cover wählen …</button><button class="ghost sm" id="tgCoverDel" ${c.state === "none" ? "disabled" : ""}>Cover entfernen</button>
      <span class="hint">${esc(c.desc || (c.state === "mixed" ? "unterschiedlich" : "kein Cover"))}</span></div></div>
    <div class="tg-form">${form}
      <label for="tgVer">ID3-Version</label><select id="tgVer" class="inp" style="height:36px"><option value="3">ID3v2.3 (verbreitet)</option><option value="4">ID3v2.4 (Mehrfachwerte)</option>${d.version ? "" : '<option value="" selected>verschieden</option>'}</select>
    </div>
    ${typeof featSection === "function" ? featSection(d) : ""}
    <div class="tg-tools">
      <button class="ghost" id="tgFromName">Tags aus Dateiname …</button>
      <button class="ghost" id="tgRename">Dateien umbenennen …</button>
      <button class="ghost" id="tgNumber" ${d.count > 1 ? "" : "disabled"}>Spurnummern …</button>
      <button class="ghost" id="tgAddField">Feld hinzufügen …</button>
      <button class="ghost" id="tgFixer">Tag-Fixer …</button>
      <button class="ghost" id="tgCase">Groß-/Kleinschreibung …</button>
      <button class="ghost" id="tgReplace">Suchen &amp; Ersetzen …</button>
      <button class="ghost" id="tgFolderCover">Cover aus Ordner …</button>
      <button class="ghost" id="tgExport">Liste exportieren …</button>
      ${one ? '<button class="ghost" id="tgReveal">' + (IS_MAC ? "Im Finder zeigen" : "Im Explorer zeigen") + "</button>" : ""}
    </div>
    <div class="tg-plugins" id="tgPlugins"></div>${more}`;
  if (d.version) $("#tgVer").value = String(d.version);
  if (act && $("#" + act)) { const el = $("#" + act); el.focus(); if (el.setSelectionRange && el.value && /^(text|search)$/.test(el.type)) el.setSelectionRange(el.value.length, el.value.length); }
  keyWheelSync();
  tgRenderPlugins();
  const grip = $("#tgMoreGrip");
  if (grip) {
    const setK = (w) => { LAYOUT.tg_more_k = clamp(Math.round(w), 70, Math.max(120, box.clientWidth - 160)); document.documentElement.style.setProperty("--tg-more-k", LAYOUT.tg_more_k + "px"); };
    draggable(grip, {
      onStart: () => ({ w: LAYOUT.tg_more_k }),
      onMove: (dx, st) => setK(st.w + dx),
      onEnd: () => saveUi("tg_more_k"),
      onDouble: () => { setK(130); saveUi("tg_more_k"); },
      onKey: (dd) => { setK(LAYOUT.tg_more_k + dd); saveUi("tg_more_k"); },
    });
  }
}

async function tgRenderPlugins() {
  if (!$("#tgPlugins") || typeof pluginActions !== "function") return;
  const acts = await pluginActions("tagger");
  const box = $("#tgPlugins");
  if (!box) return;
  box.innerHTML = acts.length
    ? `<h4>Plugins</h4><div class="tg-tools">${acts.map((a) => `<button class="ghost" data-plugin="${esc(a.plugin)}" data-action="${esc(a.id)}" title="${esc(a.description || a.plugin_name)}">${esc(a.label)}</button>`).join("")}</div>`
    : "";
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
  if (f.multiline || mvDetect(f.edit, key)) return tgFieldEditor(key);    // mehrzeilig oder Mehrfachwerte → Editor
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

/** URLs in einem Text als anklickbare Links (wie im Vergleich). */
const TG_URL_RE = /(?:https?:\/\/|www\.)[^\s|¦<>"]+/gi;
function linkify(text) {
  let out = "", last = 0;
  for (const m of text.matchAll(TG_URL_RE)) {
    const u = m[0].replace(/[.,;)]+$/, "");
    out += esc(text.slice(last, m.index)) + `<a data-url="${esc(/^www\./i.test(u) ? "https://" + u : u)}" title="${esc(u)} öffnen">${esc(u)}</a>`;
    last = m.index + u.length;
  }
  return out + esc(text.slice(last));
}
function firstUrl(text) {
  const m = (text || "").match(TG_URL_RE);
  if (!m) return null;
  const u = m[0].replace(/[.,;)]+$/, "");
  return /^www\./i.test(u) ? "https://" + u : u;
}

// Mehrfachwerte: NULL-Zeichen (ID3v2.4, im Editor als ¦), Semikolon oder Komma
const MV_SEPS = [["nul", "NULL-Zeichen (ID3v2.4-Mehrfachwert)", " ¦ "], [";", "Semikolon ;", "; "], [",", "Komma ,", ", "]];
function mvDetect(text, key) {
  // mehrzeilige Texte, URL-Felder und Texte mit Links nicht automatisch zerlegen (Umschalten auf „Einzelwerte“ geht immer)
  if (!text || /\n/.test(text) || /^W/.test(key) || firstUrl(text)) return text && text.includes("¦") ? "nul" : null;
  if (text.includes("¦")) return "nul";
  if (text.includes(";")) return ";";
  if (text.includes(",")) return ",";
  return null;
}
function mvSplit(text, sep) {
  const re = sep === "nul" ? /\s*¦\s*/ : sep === ";" ? /\s*;\s*/ : /\s*,\s*/;
  return text.split(re).map((x) => x.trim()).filter((x, i, a) => x || a.length === 1);
}
function mvJoin(items, sep) {
  return items.map((x) => x.trim()).filter(Boolean).join(MV_SEPS.find((x) => x[0] === sep)[2]);
}

/** Editor für ein Feld aus „Weitere Felder“: Text oder Einzelwerte, Blättern zum vorigen/nächsten Feld. */
async function tgFieldEditor(key) {
  const i = tgSelected()[0];
  let f = TG.detail.fields.find((x) => x.key === key);
  if (!f) return;
  if (f.xml) return openXml(null, key, { tag: i });
  if (!f.editable) { toast("Dieses Feld kann nicht als Text bearbeitet werden."); return; }
  const st = { mode: "text", sep: "nul", items: [] };
  const list = () => TG.detail.fields.filter((x) => x.editable && !x.xml);
  const value = (b) => (st.mode === "list" ? mvJoin(st.items, st.sep) : $("#feVal", b).value);

  const renderList = (b, focus) => {
    const box = $("#feList", b);
    box.innerHTML = st.items.map((v, k) => `<div class="fe-item" data-k="${k}"><span class="fe-n">${k + 1}</span>
        <input value="${esc(v)}" data-fe="${k}" spellcheck="false" aria-label="Wert ${k + 1}">
        <button class="x" data-up="${k}" title="Nach oben" ${k ? "" : "disabled"}>↑</button>
        <button class="x" data-down="${k}" title="Nach unten" ${k < st.items.length - 1 ? "" : "disabled"}>↓</button>
        <button class="x del" data-rm="${k}" title="Wert entfernen">✕</button></div>`).join("");
    if (focus !== undefined) box.querySelector(`[data-fe="${focus}"]`)?.focus();
    upd(b);
  };
  const setMode = (b, mode) => {
    if (mode === st.mode) return;
    if (mode === "list") st.items = mvSplit($("#feVal", b).value, st.sep);
    else $("#feVal", b).value = mvJoin(st.items, st.sep);
    st.mode = mode;
    b.querySelectorAll("[data-fmode]").forEach((x) => x.classList.toggle("on", x.dataset.fmode === mode));
    $("#feTextBox", b).hidden = mode !== "text";
    $("#feListBox", b).hidden = mode !== "list";
    if (mode === "list") renderList(b, 0); else { $("#feVal", b).focus(); upd(b); }
  };
  const fill = (b) => {
    const l = list(), k = l.findIndex((x) => x.key === f.key);
    $("#feLabel", b).textContent = f.label;
    $("#feKey", b).textContent = f.key;
    const ta = $("#feVal", b);
    ta.value = f.edit;
    ta.rows = Math.min(18, Math.max(f.multiline ? 8 : 3, f.edit.split("\n").length + 1));
    $("#fePrev", b).disabled = k <= 0;
    $("#feNext", b).disabled = k < 0 || k >= l.length - 1;
    $("#fePos", b).textContent = k >= 0 ? `${k + 1} von ${l.length}` : "";
    const sep = mvDetect(f.edit, f.key);
    st.sep = sep || "nul";
    $("#feSep", b).value = st.sep;
    st.mode = "text";
    setMode(b, sep ? "list" : "text");
    if (!sep) { $("#feTextBox", b).hidden = false; $("#feListBox", b).hidden = true; b.querySelectorAll("[data-fmode]").forEach((x) => x.classList.toggle("on", x.dataset.fmode === "text")); ta.focus(); }
    upd(b);
  };
  const upd = (b) => {
    const v = value(b);
    const n = st.mode === "list" ? st.items.filter((x) => x.trim()).length : 0;
    $("#feInfo", b).textContent = st.mode === "list"
      ? `${n} Wert(e)${v !== f.edit ? " · geändert" : ""}`
      : `${v.length} Zeichen · ${v ? v.split("\n").length : 0} Zeile(n)${v !== f.edit ? " · geändert" : ""}`;
  };
  // Wert übernehmen, ohne den Dialog zu schliessen (beim Blättern)
  const save = async (b) => {
    const v = value(b);
    if (v !== f.edit) taggerApplyDetail(await call("tag_set", [i], f.key, v));
  };
  const go = async (b, dir) => {
    await save(b);
    const l = list(), k = l.findIndex((x) => x.key === f.key);
    const nx = l[k + dir] || l[k];
    if (!nx) return;
    f = nx;
    fill(b);
  };
  const res = await modal({
    title: "Feld bearbeiten", wide: true,
    html: `<div class="fe-head"><div><b id="feLabel"></b> <code id="feKey" class="muted sm"></code></div>
        <div class="fe-nav"><button class="ghost sm" id="fePrev" title="Voriges Feld (Alt+↑)">‹</button><span class="muted sm" id="fePos"></span><button class="ghost sm" id="feNext" title="Nächstes Feld (Alt+↓)">›</button></div></div>
      <div class="fe-modes"><div class="seg"><button data-fmode="text">Text</button><button data-fmode="list">Einzelwerte</button></div>
        <label class="muted sm">Trennung <select id="feSep" class="inp sm">${MV_SEPS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></label></div>
      <div id="feTextBox"><textarea id="feVal" class="fe-val" spellcheck="false"></textarea></div>
      <div id="feListBox" hidden><div id="feList" class="fe-list" data-keep-enter></div><button class="ghost sm" id="feAdd">+ Wert hinzufügen</button></div>
      <div class="fe-foot"><span class="hint">Leer = Feld entfernen. NULL-getrennte Mehrfachwerte gibt es nur in ID3v2.4 (beim Speichern als v2.3 werden sie mit „ / “ verbunden). <kbd>Strg</kbd>/<kbd>⌘</kbd>+<kbd>Enter</kbd> übernimmt.</span><span class="muted sm" id="feInfo"></span></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Feld entfernen", value: "del" }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => {
      const ta = $("#feVal", b);
      ta.addEventListener("input", () => upd(b));
      b.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); e.stopPropagation(); $("#mBtns .primary").click(); return; }
        if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); go(b, e.key === "ArrowUp" ? -1 : 1); return; }
        const inp = e.target.closest("[data-fe]");
        if (inp && e.key === "Enter") {            // Enter in einem Wert: neuer Wert darunter (statt Dialog schliessen)
          e.preventDefault(); e.stopPropagation();
          const k = +inp.dataset.fe;
          st.items.splice(k + 1, 0, "");
          renderList(b, k + 1);
        }
        if (inp && e.key === "Backspace" && !inp.value && st.items.length > 1) {
          e.preventDefault(); const k = +inp.dataset.fe; st.items.splice(k, 1); renderList(b, Math.max(0, k - 1));
        }
      }, true);
      b.addEventListener("input", (e) => { const inp = e.target.closest("[data-fe]"); if (inp) { st.items[+inp.dataset.fe] = inp.value; upd(b); } });
      b.addEventListener("click", (e) => {
        const t = e.target.closest("button"); if (!t) return;
        if (t.dataset.fmode) setMode(b, t.dataset.fmode);
        else if (t.id === "feAdd") { st.items.push(""); renderList(b, st.items.length - 1); }
        else if (t.dataset.rm !== undefined) { st.items.splice(+t.dataset.rm, 1); if (!st.items.length) st.items.push(""); renderList(b); }
        else if (t.dataset.up !== undefined) { const k = +t.dataset.up; [st.items[k - 1], st.items[k]] = [st.items[k], st.items[k - 1]]; renderList(b, k - 1); }
        else if (t.dataset.down !== undefined) { const k = +t.dataset.down; [st.items[k + 1], st.items[k]] = [st.items[k], st.items[k + 1]]; renderList(b, k + 1); }
      });
      $("#feSep", b).addEventListener("change", (e) => {
        if (st.mode === "text") { const items = mvSplit(ta.value, st.sep); st.sep = e.target.value; ta.value = mvJoin(items, st.sep); }
        else st.sep = e.target.value;
        upd(b);
      });
      $("#fePrev", b).onclick = () => go(b, -1);
      $("#feNext", b).onclick = () => go(b, 1);
      fill(b);
    },
    collect: (b, v) => ({ action: v, key: f.key, value: value(b), before: f.edit }),
  });
  if (!res) return;
  if (res.action === "del") taggerApplyDetail(await call("tag_remove", [i], [res.key]));
  else if (res.value !== res.before) taggerApplyDetail(await call("tag_set", [i], res.key, res.value));
}

// ---------------------------------------------------------------------- Werkzeuge mit Vorschau
/** Felder-Auswahl: „Alle Textfelder“ oder einzelne Standardfelder */
function fieldsPicker(defaults, allDefault = false) {
  return `<label class="check"><input type="checkbox" class="fp-all" ${allDefault ? "checked" : ""}> Alle Textfelder (auch Benutzertexte, Kommentare …)</label>
    <div class="checklist fp-list">${TG.settings.fields.map(([k, l]) => `<label><input type="checkbox" data-fk="${k}" ${defaults.includes(k) ? "checked" : ""}> ${esc(l)}</label>`).join("")}</div>`;
}
function pickedFields(b) {
  if ($(".fp-all", b).checked) return null;
  return $$("input[data-fk]:checked", b).map((c) => c.dataset.fk);
}
function bindFieldsPicker(b) {
  const sync = () => { const all = $(".fp-all", b).checked; $$("input[data-fk]", b).forEach((c) => (c.disabled = all)); $(".fp-list", b).style.opacity = all ? 0.45 : 1; };
  $(".fp-all", b).addEventListener("change", sync);
  sync();
}

/** Vorschau-Dialog: preview(body) liefert {rows, count, error}; Spalten [Titel, Feld]; apply(body) führt aus. */
async function toolDialog({ title, form, columns, preview, apply, applyLabel = "Übernehmen", onMount }) {
  let timer = null, last = null, open = true, body = null;
  const again = () => { clearTimeout(timer); timer = setTimeout(() => run(body), 220); };
  const run = async (b) => {
    if (!open || !$("#tdPrev", b)) return;
    const r = await preview(b);
    if (!open || !$("#tdPrev", b)) return;
    last = r;
    const err = r.error ? `<div class="empty st-missing">${esc(r.error)}</div>` : "";
    $("#tdPrev", b).innerHTML = err || (r.rows.length
      ? `<table><thead><tr>${columns.map(([t]) => `<th>${esc(t)}</th>`).join("")}</tr></thead><tbody>${r.rows.map((x) => `<tr>${columns.map(([, f, cls]) => `<td class="${typeof cls === "function" ? cls(x) : cls || ""}">${esc(x[f])}</td>`).join("")}</tr>`).join("")}</tbody></table>`
      : '<div class="empty">Keine Änderungen.</div>');
    $("#tdSum", b).textContent = r.error ? "" : r.summary || `${fmtN(r.count)} Änderung(en)${r.files !== undefined ? ` in ${fmtN(r.files)} Datei(en)` : ""}.`;
    const btn = $("#mBtns .primary");
    if (btn) { btn.disabled = !!r.error || !r.count; btn.textContent = r.count ? `${applyLabel} (${fmtN(r.count)})` : applyLabel; }
  };
  const res = await modal({
    title, wide: true,
    html: `${form}<div class="fx-table" id="tdPrev" style="max-height:42vh"></div><div class="muted sm" id="tdSum"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: applyLabel, value: true, primary: true }],
    onMount: (b) => {
      body = b;
      if (onMount) onMount(b);
      b.addEventListener("input", again);
      b.addEventListener("change", again);
      run(b);
    },
    collect: (b) => (last && last.count && !last.error ? b : false),
  });
  open = false; clearTimeout(timer);
  body.removeEventListener("input", again);
  body.removeEventListener("change", again);
  if (res) taggerApplyDetail(await apply(res));
}

const CHG_COLS = [["Datei", "name"], ["Feld", "label"], ["Vorher", "old", "old"], ["Nachher", "new", "new"]];

async function tgCaseDialog() {
  const idx = tgSelected();
  TG.caseModes = TG.caseModes || (await call("tag_case_modes"));
  await toolDialog({
    title: `Groß-/Kleinschreibung (${idx.length} Datei(en))`,
    form: `<div class="radios" style="flex-wrap:wrap">${TG.caseModes.map(([k, l], n) => `<label><input type="radio" name="cm" value="${k}" ${n === 0 ? "checked" : ""}> ${esc(l)}</label>`).join("")}</div>
      <div class="quick"><label class="check"><input type="checkbox" id="cmKeep" checked> Abkürzungen in GROSSBUCHSTABEN behalten (DJ, AC/DC, II)</label>
      <label class="check"><input type="checkbox" id="cmSmall"> Kleine Wörter klein (and, of, the, feat., und, von …)</label></div>
      ${fieldsPicker(["TIT2", "TPE1", "TALB", "TPE2"])}`,
    columns: CHG_COLS,
    onMount: bindFieldsPicker,
    preview: (b) => call("tag_case", idx, pickedFields(b), b.querySelector('input[name="cm"]:checked').value, $("#cmKeep", b).checked, $("#cmSmall", b).checked, false),
    apply: (b) => call("tag_case", idx, pickedFields(b), b.querySelector('input[name="cm"]:checked').value, $("#cmKeep", b).checked, $("#cmSmall", b).checked, true),
  });
}

async function tgReplaceDialog() {
  const idx = tgSelected();
  const args = (b, apply) => [idx, pickedFields(b), $("#rpFind", b).value, $("#rpRepl", b).value, $("#rpCase", b).checked, $("#rpRegex", b).checked, $("#rpWord", b).checked, apply];
  await toolDialog({
    title: `Suchen & Ersetzen (${idx.length} Datei(en))`,
    form: `<div class="frm"><label for="rpFind">Suchen</label><input id="rpFind" autofocus spellcheck="false">
      <label for="rpRepl">Ersetzen durch</label><input id="rpRepl" spellcheck="false" placeholder="leer = entfernen"></div>
      <div class="quick"><label class="check"><input type="checkbox" id="rpCase"> Groß-/Kleinschreibung beachten</label>
      <label class="check"><input type="checkbox" id="rpWord"> Nur ganze Wörter</label>
      <label class="check"><input type="checkbox" id="rpRegex"> Regulärer Ausdruck (\\1 im Ersatz)</label></div>
      ${fieldsPicker(["TIT2", "TPE1", "TALB", "TPE2", "TCON", "TCOM"], true)}`,
    columns: CHG_COLS,
    applyLabel: "Ersetzen",
    onMount: bindFieldsPicker,
    preview: (b) => (b.querySelector("#rpFind").value ? call("tag_replace", ...args(b, false)) : Promise.resolve({ rows: [], count: 0, summary: "Suchbegriff eingeben." })),
    apply: (b) => call("tag_replace", ...args(b, true)),
  });
}

async function tgFolderCoverDialog() {
  const idx = tgSelected();
  await toolDialog({
    title: `Cover aus Bild im Ordner (${idx.length} Datei(en))`,
    form: `<div class="hint">Gesucht wird pro Ordner nach cover / folder / front / album (.jpg, .png, .gif), sonst wird das größte Bild genommen.</div>
      <label class="check"><input type="checkbox" id="fcMissing" checked> Nur Dateien ohne Cover</label>`,
    columns: [["Datei", "name"], ["Bild", "image"], ["Aktion", "reason", (x) => (x.action === "set" ? "new" : "old")]],
    preview: async (b) => { const r = await call("tag_folder_cover", idx, $("#fcMissing", b).checked, false); r.summary = `${fmtN(r.count)} von ${fmtN(r.rows.length)} Datei(en) bekommen ein Cover.`; return r; },
    apply: (b) => call("tag_folder_cover", idx, $("#fcMissing", b).checked, true),
  });
}

async function tgExportDialog() {
  const idx = tgSelected();
  const res = await modal({
    title: "Liste exportieren",
    html: `<div class="frm"><label>Dateien</label><div class="radios"><label><input type="radio" name="ex-s" value="sel" ${idx.length > 1 ? "checked" : ""}> Markierte (${idx.length})</label><label><input type="radio" name="ex-s" value="all" ${idx.length > 1 ? "" : "checked"}> Alle (${fmtN(TG.rows.length)})</label></div>
      <label>Format</label><div class="radios"><label><input type="radio" name="ex-f" value="xlsx" checked> Excel (.xlsx)</label><label><input type="radio" name="ex-f" value="csv"> CSV (Semikolon, für Excel)</label></div></div>
      <div class="hint">Spalten: Datei, Ordner, alle Standardfelder, Dauer, Bitrate, ID3-Version, Cover ja/nein, Größe.</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern unter …", value: true, primary: true }],
    collect: (b) => ({ sel: b.querySelector('input[name="ex-s"]:checked').value === "sel", fmt: b.querySelector('input[name="ex-f"]:checked').value }),
  });
  if (!res) return;
  const r = await call("tag_export", res.sel ? idx : [], res.fmt);
  if (r.ok) status(`${fmtN(r.count)} Datei(en) exportiert: ${r.path}`, "ok");
  else if (!r.cancelled) toast(r.error || "Export fehlgeschlagen.");
  else if (!S.settings.native) toast("Im Browser-Modus ist kein Speichern-Dialog verfügbar – bitte das App-Fenster verwenden.");
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
    const a = e.target.closest("a[data-url]");
    if (a) { e.preventDefault(); call("open_url", a.dataset.url); return; }
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
    else if (id === "tgCase") tgCaseDialog();
    else if (id === "tgReplace") tgReplaceDialog();
    else if (id === "tgFolderCover") tgFolderCoverDialog();
    else if (id === "tgExport") tgExportDialog();
    else if (id === "tgKeyBtn") keyWheelOpen();
    const pb = e.target.closest("[data-plugin]");
    if (pb) pluginRun(pb.dataset.plugin, pb.dataset.action);
    const row = e.target.closest(".tg-f");
    if (row && e.target.closest("[data-tdel]")) taggerApplyDetail(await call("tag_remove", [idx[0]], [row.dataset.key]));
    else if (row && e.target.closest("[data-txml]")) openXml(null, row.dataset.key, { tag: idx[0] });
    else if (row && e.target.closest("[data-tedit]")) tgFieldEditor(row.dataset.key);
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
