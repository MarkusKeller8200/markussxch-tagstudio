/* MarKusSXCH TagStudio – Tag-Rezepte (#111): Aktionslisten wie in Mp3tag zusammenstellen, Vorschau, anwenden.
   Server: recipes.py, Session.recipes/recipes_save/tag_recipe. Auch Schritt „Rezept“ im Vorbereiten-Workflow. */
"use strict";

const RC = { data: null, cur: 0, list: [] };

function rcFields(a) { return a.fields === "all" || !a.fields ? "all" : a.fields.join(", "); }
function rcParseFields(v) { v = String(v || "").trim(); return !v || v.toLowerCase() === "all" || v === "alle" ? "all" : v.split(/\s*,\s*/).filter(Boolean); }

/** Formular-Felder je Aktionstyp */
function rcForm(a) {
  const f = (id, label, val, ph = "") => `<label for="${id}">${esc(label)}</label><input id="${id}" value="${esc(val ?? "")}" placeholder="${esc(ph)}" spellcheck="false">`;
  const fl = () => f("raF", "Felder", rcFields(a), "all = alle Textfelder, sonst z. B. TIT2, TPE1, TXXX:*");
  switch (a.type) {
    case "replace": return f("raFind", "Suchen", a.find) + f("raRepl", "Ersetzen durch", a.repl, "leer = entfernen") + fl()
      + `<span></span><div class="quick"><label class="check"><input type="checkbox" id="raCase" ${a.case ? "checked" : ""}> Gross-/Kleinschreibung</label><label class="check"><input type="checkbox" id="raWord" ${a.word ? "checked" : ""}> ganze Wörter</label><label class="check"><input type="checkbox" id="raRegex" ${a.regex ? "checked" : ""}> regulärer Ausdruck</label></div>`;
    case "words": return f("raWords", "Wörter (Schreibweise)", (a.words || []).join(", "), "z. B. DJ, feat., MC, vs.") + fl();
    case "case": return `<label for="raMode">Schreibweise</label><select id="raMode" class="inp">${Object.entries(RC.data.case_modes).map(([k, v]) => `<option value="${k}" ${a.mode === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>` + fl();
    case "first_value": case "remove": case "trim": return f("raF", a.type === "remove" ? "Felder (Muster)" : "Felder", a.type === "trim" ? rcFields(a) : (a.fields === "all" ? "" : (a.fields || []).join(", ")), a.type === "remove" ? "z. B. COMM*, TXXX:COMMENT" : "z. B. TXXX:FILETYPE");
    case "set": return f("raField", "Feld", a.field, "z. B. TXXX:QUELLE") + f("raValue", "Wert", a.value, "leer = entfernen; %TIT2% setzt einen Feldwert ein");
    case "version": return `<label for="raV2">ID3v2</label><select id="raV2" class="inp"><option value="0" ${!a.v2 ? "selected" : ""}>beibehalten</option><option value="3" ${a.v2 === 3 ? "selected" : ""}>ID3v2.3</option><option value="4" ${a.v2 === 4 ? "selected" : ""}>ID3v2.4</option></select>
      <label for="raV1">ID3v1</label><select id="raV1" class="inp"><option value="keep" ${!a.v1 || a.v1 === "keep" ? "selected" : ""}>wie vorhanden</option><option value="write" ${a.v1 === "write" ? "selected" : ""}>mitschreiben</option><option value="remove" ${a.v1 === "remove" ? "selected" : ""}>entfernen</option></select>`;
    default: return '<span class="muted">Keine Einstellungen.</span>';
  }
}

function rcReadForm(b, a) {
  const v = (id) => { const el = $("#" + id, b); return el ? el.value : undefined; };
  const c = (id) => !!($("#" + id, b) && $("#" + id, b).checked);
  const out = { type: a.type };
  if (a.type === "replace") Object.assign(out, { find: v("raFind"), repl: v("raRepl"), fields: rcParseFields(v("raF")), case: c("raCase"), word: c("raWord"), regex: c("raRegex") });
  else if (a.type === "words") Object.assign(out, { words: (v("raWords") || "").split(/\s*,\s*/).filter(Boolean), fields: rcParseFields(v("raF")) });
  else if (a.type === "case") Object.assign(out, { mode: v("raMode"), fields: rcParseFields(v("raF")) });
  else if (a.type === "trim") Object.assign(out, { fields: rcParseFields(v("raF")) });
  else if (a.type === "first_value" || a.type === "remove") Object.assign(out, { fields: (v("raF") || "").split(/\s*,\s*/).filter(Boolean) });
  else if (a.type === "set") Object.assign(out, { field: (v("raField") || "").trim(), value: v("raValue") });
  else if (a.type === "version") Object.assign(out, { v2: +v("raV2") || 0, v1: v("raV1") });
  return out;
}

/** Aktion im Dialog selbst bearbeiten (kein zweiter Dialog – der würde den Rezept-Dialog ersetzen). */
function rcEditAction(b, a, done) {
  const box = $("#rcEdit", b);
  box.hidden = false;
  box.innerHTML = `<div class="rc-edit-h"><b>${esc(RC.data.types[a.type])}</b></div><div class="frm">${rcForm(a)}</div>
    <div class="rc-edit-b"><button class="ghost sm" data-rce="cancel">Abbrechen</button><button class="ghost sm" data-rce="ok"><b>Übernehmen</b></button></div>`;
  box.onclick = (e) => {
    const t = e.target.closest("[data-rce]"); if (!t) return;
    e.stopPropagation();
    const out = t.dataset.rce === "ok" ? rcReadForm(box, a) : null;
    box.hidden = true; box.innerHTML = ""; box.onclick = null;
    if (out) done(out);
  };
  box.querySelector("input,select")?.focus();
}

function rcLine(a) {
  const f = rcFields(a) === "all" ? "alle Textfelder" : rcFields(a);
  switch (a.type) {
    case "replace": return `„${a.find || ""}“ → „${a.repl || ""}“ in ${f}`;
    case "words": return `Wörter so schreiben: ${(a.words || []).join(", ")} (${f})`;
    case "case": return `${RC.data.case_modes[a.mode] || a.mode} in ${f}`;
    case "dedupe": return "Doppelte Werte und gleiche Doppel-Felder entfernen";
    case "first_value": return `Nur den ersten Wert behalten: ${(a.fields || []).join(", ")}`;
    case "remove": return `Entfernen: ${(a.fields || []).join(", ")}`;
    case "set": return `${a.field} = „${a.value || ""}“`;
    case "trim": return `Leerzeichen bereinigen in ${f}`;
    case "version": return `Speichern als ${a.v2 ? "ID3v2." + a.v2 : "bisherige ID3-Version"}, ${{ write: "mit ID3v1", remove: "ohne ID3v1" }[a.v1] || "ID3v1 wie vorhanden"}`;
    default: return a.type;
  }
}

function rcRender(b) {
  const r = RC.list[RC.cur];
  $("#rcSel", b).innerHTML = RC.list.map((x, k) => `<option value="${k}" ${k === RC.cur ? "selected" : ""}>${esc(x.name)}</option>`).join("");
  $("#rcName", b).value = r ? r.name : "";
  $("#rcActs", b).innerHTML = r && r.actions.length ? r.actions.map((a, k) => `<div class="rc-act" data-k="${k}"><span class="rc-n">${k + 1}</span><span class="rc-t" title="${esc(RC.data.types[a.type])}">${esc(rcLine(a))}</span>
      <button class="icon-btn" data-rc="edit" title="Bearbeiten">✎</button><button class="icon-btn" data-rc="up" ${k ? "" : "disabled"} title="Nach oben">↑</button><button class="icon-btn" data-rc="down" ${k < r.actions.length - 1 ? "" : "disabled"} title="Nach unten">↓</button><button class="icon-btn" data-rc="del" title="Entfernen">✕</button></div>`).join("")
    : '<div class="muted sm">Noch keine Aktionen.</div>';
}

async function tgRecipeDialog() {
  const idx = tgSelected();
  RC.data = await call("recipes");
  RC.list = JSON.parse(JSON.stringify(RC.data.recipes));
  RC.cur = Math.min(RC.cur, Math.max(0, RC.list.length - 1));
  const touch = (b) => b.dispatchEvent(new Event("change"));
  await toolDialog({
    title: `Tag-Rezepte (${idx.length} Datei(en))`,
    form: `<div class="rc-head"><select id="rcSel" class="inp" aria-label="Rezept"></select>
        <button class="ghost sm" id="rcNew">Neu</button><button class="ghost sm" id="rcCopy">Kopie</button><button class="ghost sm" id="rcDel">Löschen …</button>
        <button class="ghost sm" id="rcSave" title="Rezepte dauerhaft speichern (auch für den Vorbereiten-Workflow)">Rezepte speichern</button><button class="ghost sm" id="rcReset" title="Mitgelieferte Vorlage wiederherstellen">Vorlage</button></div>
      <div class="frm"><label for="rcName">Name</label><input id="rcName" spellcheck="false"></div>
      <div class="rc-acts" id="rcActs"></div>
      <div class="rc-edit" id="rcEdit" hidden data-keep-enter></div>
      <div class="rc-add"><select id="rcType" class="inp">${Object.entries(RC.data.types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select><button class="ghost sm" id="rcAdd">+ Aktion</button>
        <span class="muted sm">Die Aktionen laufen der Reihe nach; die Vorschau zeigt das Ergebnis für die markierten Titel.</span></div>`,
    columns: CHG_COLS,
    applyLabel: "Anwenden",
    onMount: (b) => {
      rcRender(b);
      b.addEventListener("click", async (e) => {
        const t = e.target.closest("button"); if (!t || t.closest("#rcEdit")) return;
        const r = RC.list[RC.cur];
        if (t.id === "rcNew") { RC.list.push({ id: "", name: "Neues Rezept", actions: [] }); RC.cur = RC.list.length - 1; }
        else if (t.id === "rcCopy" && r) { RC.list.push({ ...JSON.parse(JSON.stringify(r)), id: "", builtin: false, name: r.name + " (Kopie)" }); RC.cur = RC.list.length - 1; }
        else if (t.id === "rcDel" && r) { if (!(await dialog({ title: "Rezept löschen", text: `Rezept „${r.name}“ löschen? (wirksam mit „Rezepte speichern“)`, buttons: [{ label: "Abbrechen", value: null }, { label: "Löschen", value: true, primary: true }] }))) return; RC.list.splice(RC.cur, 1); RC.cur = 0; }
        else if (t.id === "rcSave") { RC.data = await call("recipes_save", RC.list); RC.list = JSON.parse(JSON.stringify(RC.data.recipes)); toast("Rezepte gespeichert."); }
        else if (t.id === "rcReset") { RC.data = await call("recipes_reset"); RC.list = JSON.parse(JSON.stringify(RC.data.recipes)); RC.cur = 0; toast("Vorlage wiederhergestellt."); }
        else if (t.id === "rcAdd" && r) { rcEditAction(b, { type: $("#rcType", b).value, fields: "all" }, (a) => { r.actions.push(a); rcRender(b); touch(b); }); return; }
        else if (t.dataset.rc && r) {
          const k = +t.closest(".rc-act").dataset.k;
          if (t.dataset.rc === "del") r.actions.splice(k, 1);
          else if (t.dataset.rc === "edit") { rcEditAction(b, r.actions[k], (a) => { r.actions[k] = a; rcRender(b); touch(b); }); return; }
          else { const j = k + (t.dataset.rc === "up" ? -1 : 1); [r.actions[k], r.actions[j]] = [r.actions[j], r.actions[k]]; }
        } else return;
        rcRender(b); touch(b);
      });
      $("#rcSel", b).addEventListener("change", (e) => { RC.cur = +e.target.value; rcRender(b); });
      $("#rcName", b).addEventListener("input", (e) => { if (RC.list[RC.cur]) RC.list[RC.cur].name = e.target.value; });
    },
    preview: (b) => {
      const r = RC.list[RC.cur];
      return r && r.actions.length ? call("tag_recipe", idx, r, false) : Promise.resolve({ rows: [], count: 0, summary: "Rezept wählen oder Aktionen hinzufügen." });
    },
    apply: () => call("tag_recipe", idx, RC.list[RC.cur], true),
  });
}
