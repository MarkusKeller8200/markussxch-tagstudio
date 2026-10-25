/* MarKusSXCH TagStudio – Tag-Fixer › Smart Fix (#339).
   Rezepte für wiederkehrende Fixes: mitgelieferte (nicht änderbar, nur kopierbar) und eigene (anlegen, bearbeiten,
   löschen nach Rückfrage, exportieren/importieren als JSON). Erstes Rezept „Mehrfachwerte mit Komma“. Der
   Ziel-Trenner ist je Rezept wählbar (Standard „, “). Vorschau, Auswahl (#341) und Anwenden teilt Smart Fix mit dem
   Mehrfachwerte-Fixer; Ausnahmen je Feld (#342) gelten auch hier. */

function fixerSetMode(mode) {
  FX.mode = mode === "smart" ? "smart" : "multi";
  LAYOUT.fx_mode = FX.mode;
  saveUi("fx_mode");
  FX.skip.clear();
  fixerModeUi();
  fixerPreview();
}

function fixerModeUi() {
  $$("#fxMode [data-fxmode]").forEach((b) => {
    const on = b.dataset.fxmode === FX.mode;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
  $("#fxMulti").hidden = FX.mode === "smart";
  $("#fxSmart").hidden = FX.mode !== "smart";
  if (FX.mode === "smart") smartRender();
}

const smartAll = () => [...FX.smart.builtin, ...FX.smart.own];
const smartCur = () => smartAll().find((r) => r.id === FX.smart.current) || FX.smart.builtin[0];
const smartTargetName = (id) => ((FX.smart.targets || []).find((t) => t[0] === id) || [id, id])[1];
const smartSepCodes = (sep) => {
  const s = (FX.settings.separators || []).find((x) => x[1] === sep);
  return s ? sepCode(s[3] || sep, s[0]) : sepCode(sep);
};

function smartRender() {
  const box = $("#fxSmart");
  if (!box || !FX.smart) return;
  const cur = smartCur();
  FX.smart.current = cur.id;
  const item = (r) => `<label class="opt fx-rcp${r.id === cur.id ? " on" : ""}"><input type="radio" name="fx-rcp" value="${esc(r.id)}" ${r.id === cur.id ? "checked" : ""}>
      <span><b>${esc(r.name)}</b> <span class="fx-rcp-tag">${r.builtin ? "mitgeliefert" : "eigen"}</span>${r.desc ? `<span class="muted sm fx-rcp-desc">${esc(r.desc)}</span>` : ""}</span></label>`;
  box.innerHTML = `
    <h4>Rezepte</h4>
    <div class="fx-rcps">${FX.smart.builtin.map(item).join("")}${FX.smart.own.map(item).join("")}</div>
    <div class="fx-rcp-detail">
      <span class="muted sm">Felder</span><div>${cur.fields.map((f) => `<span class="fx-chip">${esc(smartTargetName(f))}</span>`).join("")}</div>
      <span class="muted sm">Trennen bei</span><div class="sep-codes">${cur.seps.map(smartSepCodes).join(" ")}</div>
      <span class="muted sm">Ziel-Trenner</span><div><select class="inp sm" id="fxSmartOut" aria-label="Ziel-Trenner">${FX.smart.outputs.map(([v, l]) => `<option value="${esc(v)}" ${v === cur.out ? "selected" : ""}>${v === "v24" ? esc(l) : `${esc(l)} „${esc(v)}“`}</option>`).join("")}</select></div>
      <span class="muted sm">Doppelte</span><div>${cur.dedupe ? "werden entfernt" : "bleiben"}</div>
    </div>
    <div class="fx-rcp-btns">
      <button class="ghost sm" id="fxRcpNew">Neu …</button><button class="ghost sm" id="fxRcpCopy">Kopieren …</button>
      <button class="ghost sm" id="fxRcpEdit" ${cur.builtin ? "disabled title=\"Mitgelieferte Rezepte lassen sich nur kopieren\"" : ""}>Bearbeiten …</button>
      <button class="ghost sm" id="fxRcpDel" ${cur.builtin ? "disabled" : ""}>Löschen …</button>
      <button class="ghost sm" id="fxRcpExp" ${FX.smart.own.length ? "" : "disabled title=\"Noch keine eigenen Rezepte\""}>Exportieren …</button><button class="ghost sm" id="fxRcpImp">Importieren …</button>
    </div>
    <div class="fx-exc"><button class="ghost sm fx-exc-btn" id="fxExc2">Ausnahmen …</button></div>`;
  box.onchange = async (e) => {
    const t = e.target;
    if (t.name === "fx-rcp") { FX.smart.current = t.value; call("smart_select", t.value); FX.skip.clear(); smartRender(); fixerPreview(); }
    else if (t.id === "fxSmartOut") { FX.smart = await call("smart_set_out", cur.id, t.value); smartRender(); fixerPreview(); }
  };
  $("#fxRcpNew").onclick = () => smartEdit(null);
  $("#fxRcpCopy").onclick = () => smartEdit({ ...cur, id: "", builtin: false, name: `${cur.name} (Kopie)` });
  $("#fxRcpEdit").onclick = () => smartEdit(cur);
  $("#fxRcpDel").onclick = smartDelete;
  $("#fxRcpExp").onclick = smartExport;
  $("#fxRcpImp").onclick = smartImport;
  $("#fxExc2").onclick = fixerExceptionsEdit;
  fixerExcButton();
}

/** Rezept anlegen/bearbeiten: Name, Beschreibung, Felder/Gruppen, Trenner, Ziel-Trenner, Doppelte */
async function smartEdit(r) {
  const base = r || { id: "", name: "", desc: "", fields: ["@artists"], seps: [";"], out: ", ", dedupe: true };
  const seps = FX.settings.separators || [];
  const res = await modal({
    title: r && r.id ? "Rezept bearbeiten" : "Neues Rezept", wide: true,
    html: `<div class="fx-rcp-form">
        <label>Name</label><input class="inp" id="rcpName" value="${esc(base.name)}" spellcheck="false">
        <label>Beschreibung</label><input class="inp" id="rcpDesc" value="${esc(base.desc || "")}">
        <label>Felder</label><div class="fx-rcp-fields">${(FX.smart.targets || []).map((t) => `<label class="check"><input type="checkbox" data-rf="${esc(t[0])}" ${base.fields.includes(t[0]) ? "checked" : ""}> ${esc(t[1])}</label>`).join("")}</div>
        <label>Trennen bei</label><div class="fx-seps">${seps.map(([l, sep, , codes], n) => `<label class="opt"><input type="checkbox" data-rs="${n}" ${base.seps.includes(sep) ? "checked" : ""}> <span class="sep-codes">${sepCode(codes || sep, l)}</span> <span class="sep-name">${esc(l)}</span></label>`).join("")}</div>
        <label>Ziel-Trenner</label><select class="inp" id="rcpOut">${FX.smart.outputs.map(([v, l]) => `<option value="${esc(v)}" ${v === base.out ? "selected" : ""}>${v === "v24" ? esc(l) : `${esc(l)} „${esc(v)}“`}</option>`).join("")}</select>
        <span></span><label class="check"><input type="checkbox" id="rcpDedupe" ${base.dedupe !== false ? "checked" : ""}> Doppelte Werte entfernen</label>
      </div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }],
    collect: async (b) => {
      const rec = {
        id: base.builtin ? "" : base.id, name: $("#rcpName", b).value, desc: $("#rcpDesc", b).value,
        fields: $$("input[data-rf]:checked", b).map((x) => x.dataset.rf),
        seps: $$("input[data-rs]:checked", b).map((x) => seps[+x.dataset.rs][1]),
        out: $("#rcpOut", b).value, dedupe: $("#rcpDedupe", b).checked,
      };
      try { return await call("smart_save", rec); } catch (e) { toast(String(e.message || e)); return false; }
    },
  });
  if (!res) return;
  FX.smart = res;
  FX.smart.current = res.recipe.id;
  toast(`Rezept „${res.recipe.name}“ gespeichert.`);
  smartRender();
  fixerPreview();
}

async function smartDelete() {
  const cur = smartCur();
  if (cur.builtin) return;
  const ok = await dialog({ title: "Rezept löschen?", text: `„${cur.name}“ wird aus den eigenen Rezepten entfernt.`,
    buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
  if (!ok) return;
  FX.smart = await call("smart_delete", cur.id);
  toast("Rezept gelöscht.");
  smartRender();
  fixerPreview();
}

async function smartExport() {
  const r = await call("smart_export");
  if (r.ok) toast(`Exportiert: ${r.path}`);
  else if (r.error) info("Export nicht möglich", r.error);
}

async function smartImport() {
  const take = async (text) => {
    try {
      const r = await call("smart_import", text);
      FX.smart = r;
      toast(r.added ? `${fmtN(r.added)} Rezept(e) übernommen.` : "Keine Rezepte in der Datei.");
      smartRender();
    } catch (e) { info("Import nicht möglich", String(e.message || e)); }
  };
  if (S.settings && S.settings.native) {
    const r = await call("smart_import_pick");
    if (r && r.error) return info("Import nicht möglich", r.error);
    if (r) take(r.text);
    return;
  }
  const inp = document.createElement("input");
  inp.type = "file"; inp.accept = ".json,application/json";
  inp.onchange = async () => { const f = inp.files[0]; if (f) take(await f.text()); };
  inp.click();
}
