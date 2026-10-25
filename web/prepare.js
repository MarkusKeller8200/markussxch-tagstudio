/* MarKusSXCH TagStudio – Seite „Vorbereiten“ (#109–#116): Workflow-Schritte, Status je Titel, Ausführen,
   externe Programme, Schutzregel, Übernahme. Logik in prepare.py / session_prepare.py. */
"use strict";

const PREP = { d: null, sel: new Set() };
/** Kurzname eines Schritts für die Tabelle: Nummer aus der Bezeichnung („03 Platinum Notes“ → 03), Übernahme „Ü“ */
function prepShort(s, i) { const m = String(s.label || "").match(/^(\d+)\b/); return m ? m[1] : s.type === "import" ? "Ü" : String(i + 1); }
const PREP_ICON = { open: "·", blocked: "", waiting: "⏳", done: "✓", warn: "⚠", error: "✕", skipped: "–" };

async function prepShow() {
  try { prepApply(await call("prep_refresh", PREP.d ? PREP.d.workflow.id : null)); } catch (e) { toast(String(e.message || e)); }
}

function prepApply(d) {
  PREP.d = d;
  if (d.message) toast(d.message);
  const w = d.workflow;
  $("#prepWf").innerHTML = d.workflows.map((x) => `<option value="${esc(x.id)}" ${x.id === w.id ? "selected" : ""}>${esc(x.name)}</option>`).join("");
  const miss = (p) => (p ? `<span class="path-dir">${esc(p)}</span>` : '<span class="st-missing">nicht festgelegt</span>');   // #177: Ordner grün
  $("#prepPaths").innerHTML = `Eingang: ${miss(w.inbox)} · Arbeitsordner: ${miss(d.work)} · Bibliothek: ${miss(w.library)}`;
  const names = new Set(d.rows.map((r) => r.name));
  PREP.sel = new Set([...PREP.sel].filter((n) => names.has(n)));
  prepSideCount(d);
  const fb = $("#prepFetch"), qs = w.sources || [];
  if (fb) {
    const nNew = Object.values(d.sources_new || {}).reduce((a, b) => a + b, 0);
    fb.hidden = !qs.length;
    fb.textContent = nNew ? `Abholen (${fmtN(nNew)})` : "Abholen";
    fb.classList.toggle("primary", !!nNew); fb.classList.toggle("ghost", !nNew);
    fb.title = "Neue Downloads in den Eingangsordner kopieren – " + qs.map((q) => `${q.name}: ${(d.sources_new || {})[q.id] || 0} neu`).join(", ");
  }
  prepRenderSteps();
  prepRenderTable();
}

function prepSideCount(d) {
  const el = $("#prepCount"); if (!el || !d) return;
  const imp = d.workflow.steps.findIndex((s) => s.type === "import");
  const n = imp < 0 ? d.rows.length : d.rows.filter((r) => !["done", "warn"].includes(r.cells[imp].state)).length;
  el.textContent = n ? String(n) : "";
  el.classList.remove("new");
}

function prepRenderSteps() {
  const d = PREP.d, w = d.workflow;
  $("#prepSteps").innerHTML = w.steps.map((s, i) => {
    const c = d.counts[s.id] || {};
    const ready = (c.open || 0) + (s.type === "verify" ? c.error || 0 : 0), wait = c.waiting || 0, done = (c.done || 0) + (c.warn || 0) + (c.skipped || 0);
    const btn = s.type === "check" ? "" : s.type === "external"
      ? `<button class="ghost sm" data-run="${esc(s.id)}" ${ready ? "" : "disabled"} title="${s.copy ? "In den Stufen-Ordner kopieren und " : ""}Programm öffnen">Öffnen${ready ? ` (${ready})` : ""}</button>`
      : `<button class="${s.type === "import" ? "primary" : "ghost"} sm" data-run="${esc(s.id)}" ${ready ? "" : "disabled"}>${s.type === "import" ? "Übernehmen" : s.type === "verify" ? "Prüfen" : "Ausführen"}${ready ? ` (${ready})` : ""}</button>`;
    const det = s.detect ? `<span class="muted sm" title="Abschluss wird an der Herkunft erkannt">erkennt: ${esc((d.origins || {})[s.detect] || s.detect)}</span>` : "";
    return `<div class="prep-step t-${s.type}"><div class="h">${/^\d/.test(s.label) ? "" : `<span class="n">${prepShort(s, i)}</span>`}<b title="${esc(d.types[s.type])}">${esc(s.label)}</b>${s.protect ? ' <span class="prep-lock" title="Schutzregel „nur ergänzen“">🔒</span>' : ""}</div>
      <div class="c"><span title="erledigt">✓ ${done}</span>${wait ? ` <span title="wartet">⏳ ${wait}</span>` : ""}${c.error ? ` <span class="st-missing" title="Fehler">✕ ${c.error}</span>` : ""}${(c.warn || 0) ? ` <span title="Warnungen der Schutzregel">⚠ ${c.warn}</span>` : ""}</div>
      <div class="a">${btn}${s.folder ? `<button class="ghost sm" data-folder="${esc(s.folder)}" title="Stufen-Ordner öffnen">📁</button>` : ""}${det}</div></div>`;
  }).join("");
}

function prepRenderTable() {
  const d = PREP.d, w = d.workflow;
  if (!d.rows.length) {
    $("#prepTable").innerHTML = `<div class="tg-empty">${w.inbox ? "Keine MP3 im Eingangsordner." : "Zuerst „Workflow bearbeiten“: Eingangsordner, Arbeitsordner und Bibliothek festlegen."}</div>`;
    return;
  }
  const all = d.rows.every((r) => PREP.sel.has(r.name));
  $("#prepTable").innerHTML = `<table class="prep-t"><thead><tr><th><input type="checkbox" id="prepAll" ${all ? "checked" : ""} aria-label="Alle wählen"></th><th>Titel</th>
    ${w.steps.map((s, i) => `<th title="${esc(s.label)}">${esc(prepShort(s, i))}</th>`).join("")}</tr></thead><tbody>
    ${d.rows.map((r) => `<tr data-name="${esc(r.name)}" class="${r.exists ? "" : "gone"}"><td><input type="checkbox" data-sel ${PREP.sel.has(r.name) ? "checked" : ""}></td>
      <td class="nm" title="${esc(r.path)}${r.source ? `\nQuelle: ${esc(r.source)}${r.origin_file ? " – " + esc(r.origin_file) : ""}` : ""}">${esc(r.name)}${r.source ? ` <span class="prep-src">${esc(r.source)}</span>` : ""}${r.exists ? "" : ' <span class="st-missing sm">fehlt</span>'}</td>
      ${r.cells.map((c, i) => `<td class="pc s-${c.state}" data-step="${i}" title="${esc(w.steps[i].label)}: ${esc(d.states[c.state] || (c.state === "blocked" ? "vorherige Schritte zuerst" : c.state))}${c.note ? " – " + esc(c.note) : ""}${c.viol.length ? ` – ${c.viol.length} geänderte(s) Feld(er)` : ""}">${PREP_ICON[c.state] || ""}</td>`).join("")}</tr>`).join("")}
    </tbody></table>`;
}

function prepNames() { return PREP.sel.size ? [...PREP.sel] : null; }

async function prepFetch() {
  const r = await runTask(call("start_prep_fetch", PREP.d.workflow.id, null), "Quellen abholen");
  if (!r || r.cancelled) { prepShow(); return; }
  status(`${fmtN(r.got.length)} neue(r) Titel abgeholt${r.same ? `, ${fmtN(r.same)} schon im Eingang` : ""}${r.per.length > 1 ? " (" + r.per.join(", ") + ")" : ""}.`, r.errors.length ? "warn" : "info");
  if (r.errors.length) await info("Hinweise", r.errors.join("\n"));
  prepShow();
}

async function prepRun(sid, names = null, force = false) {
  const s = PREP.d.workflow.steps.find((x) => x.id === sid);
  const r = await runTask(call("start_prep_run", PREP.d.workflow.id, sid, names || prepNames(), force), s.label);
  if (!r || r.cancelled) { prepShow(); return; }
  const msg = [`${s.label}: ${fmtN(r.done)} Titel`];
  if (s.type === "external") msg.push(r.launched ? "Programm geöffnet – danach „Aktualisieren“ bzw. erledigt markieren" : s.program ? "" : "kein Programm hinterlegt – bitte selbst öffnen (Ordner: 📁)");
  if (r.snapshot) msg.push(`Snapshot der Bibliothek „${r.snapshot}“ wird erstellt`);
  if (r.playlist) msg.push(`in Playlist „${r.playlist}“`);                                     // #270
  if (r.linked) msg.push(`${fmtN(r.linked)} Einträge in Playlists verknüpft`);                 // #271
  status(msg.filter(Boolean).join(" · "), r.errors.length ? "warn" : "info");
  if (r.errors.length) await info("Hinweise", r.errors.join("\n"));
  prepShow();
}

/** Menü zu einer Zelle (Titel × Schritt) */
function prepCellMenu(e, name, i) {
  const d = PREP.d, s = d.workflow.steps[i], row = d.rows.find((r) => r.name === name), c = row.cells[i];
  const names = PREP.sel.has(name) && PREP.sel.size > 1 ? [...PREP.sel] : [name];
  const n = names.length > 1 ? ` (${names.length})` : "";
  const items = [];
  if (c.viol.length) {
    items.push({ label: `Geänderte Felder ansehen (${c.viol.length}) …`, run: () => prepViolations(name, i) });
    items.push({ label: "Geänderte Felder zurücksetzen", run: async () => prepApply(await call("prep_revert", d.workflow.id, s.id, name)) }, "-");
  }
  if (s.type === "verify" && c.state === "error") items.push({ label: `Erneut prüfen${n}`, run: () => prepRun(s.id, names) });
  if (s.type !== "check" && c.state === "open") items.push({ label: s.type === "external" ? `Öffnen${n}` : `Ausführen${n}`, run: () => prepRun(s.id, names) });
  if (s.type === "import" && c.state === "error") items.push({ label: `Trotzdem übernehmen${n}`, run: () => prepRun(s.id, names, true) });
  items.push({ label: `Aussortieren${n} …`, run: () => archivePrepDialog(names) });                                  // #173
  if (["open", "waiting", "error", "blocked"].includes(c.state)) items.push({ label: `Als erledigt markieren${n}`, run: async () => prepApply(await call("prep_mark", d.workflow.id, s.id, names, "done")) });
  if (c.state !== "skipped") items.push({ label: `Überspringen${n}`, run: async () => prepApply(await call("prep_mark", d.workflow.id, s.id, names, "skipped")) });
  if (!["open", "blocked"].includes(c.state)) items.push({ label: `Zurück auf offen${n}`, run: async () => prepApply(await call("prep_mark", d.workflow.id, s.id, names, "open")) });
  items.push("-", { label: "Im Tagger öffnen", run: () => { setModule("tagger"); $("#tgPath").value = row.path; taggerLoad(); } });
  showMenu(e.clientX, e.clientY, items);
}

async function prepViolations(name, i) {
  const d = PREP.d, s = d.workflow.steps[i], c = d.rows.find((r) => r.name === name).cells[i];
  const r = await modal({ title: `${s.label}: geänderte Felder – ${name}`, wide: true,
    html: `<p class="muted sm" style="margin:0 0 8px">Die Schutzregel „nur ergänzen“ meldet Felder, die das Programm geändert oder entfernt hat. Neue Felder sind immer erlaubt.</p>
      <div class="fx-table"><table><thead><tr><th>Feld</th><th>Vorher</th><th>Nachher</th><th></th></tr></thead><tbody>
      ${c.viol.map((v) => `<tr><td><code>${esc(v.key)}</code></td><td class="old">${esc(v.old)}</td><td class="new">${v.state === "removed" ? "<i>entfernt</i>" : esc(v.new)}</td><td><button class="ghost sm" data-allow="${esc(v.key)}" title="Dieses Feld für „${esc(s.label)}“ künftig erlauben">künftig erlauben</button></td></tr>`).join("")}</tbody></table></div>`,
    buttons: [{ label: "Schliessen", value: null }, { label: "Zurücksetzen", value: "revert", primary: true }],
    onMount: (b) => b.addEventListener("click", async (e) => { const a = e.target.closest("[data-allow]"); if (!a) return; await call("prep_allow", d.workflow.id, s.id, a.dataset.allow); a.disabled = true; a.textContent = "erlaubt"; }) });
  if (r === "revert") prepApply(await call("prep_revert", d.workflow.id, s.id, name));
  else prepShow();
}

// ---------------------------------------------------------------------- Workflow bearbeiten
/** Eingabefeld mit Knopf für den Dateibrowser (#161). kind: "folder" oder "program" */
function prepPathInput(id, value, ph, kind = "folder", extra = "") {
  return `<div class="pl-folder"><input id="${id}"${kind === "program" ? "" : ' class="path-dir"'} value="${esc(value ?? "")}" placeholder="${esc(ph)}" spellcheck="false" ${extra}><button class="ghost sm" type="button" data-pick="${id}" data-kind="${kind}" title="${kind === "program" ? "Programm auswählen" : "Ordner auswählen"}">Wählen …</button></div>`;
}

/** Klick auf „Wählen …“ in einem Dialog: Dateibrowser öffnen, Pfad ins Feld übernehmen. */
async function prepPickClick(e, root) {
  const b = e.target.closest("[data-pick]");
  if (!b) return false;
  e.preventDefault(); e.stopPropagation();
  const inp = root.querySelector("#" + CSS.escape(b.dataset.pick)) || b.parentElement.querySelector("input");
  const prog = b.dataset.kind === "program";
  const p = await call("pick_path", "", !prog, inp.value.trim(), prog ? "program" : "mp3");
  if (p) { inp.value = p; inp.dispatchEvent(new Event("input", { bubbles: true })); }
  else if (!S.settings.native) toast("Pfad bitte direkt ins Feld eintippen.");
  return true;
}

function prepStepForm(s, recipesList, origins, pluginActs = []) {
  const inp = (id, label, v, ph = "") => `<label for="${id}">${esc(label)}</label><input id="${id}" value="${esc(v ?? "")}" placeholder="${esc(ph)}" spellcheck="false">`;
  const sel = (id, label, v, opts) => `<label for="${id}">${esc(label)}</label><select id="${id}" class="inp">${opts.map(([k, t]) => `<option value="${esc(k)}" ${k === v ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
  const chk = (id, label, v) => `<span></span><label class="check"><input type="checkbox" id="${id}" ${v ? "checked" : ""}> ${esc(label)}</label>`;
  const det = sel("psDetect", "Abschluss erkennen an", s.detect || "", [["", "nicht erkennen (von Hand bestätigen)"], ...Object.entries(origins).filter(([k]) => !["id3v3", "id3v4", "unknown"].includes(k)).map(([k, v]) => [k, `Herkunft ${v}`])]);
  let f = inp("psLabel", "Bezeichnung", s.label);
  if (s.type === "recipe") f += sel("psRecipe", "Tag-Rezept", s.recipe, recipesList.map((r) => [r.id, r.name])) + inp("psFolder", "Stufen-Ordner", s.folder, "_02_MP3Tag");
  if (s.type === "external") f += `<label for="psProgram">Programm (Pfad)</label>` + prepPathInput("psProgram", s.program, "z. B. C:\\Program Files\\Platinum Notes\\PlatinumNotes.exe", "program")
    + inp("psArgs", "Argumente", s.args, "{folder} oder {files}") + inp("psFolder", "Stufen-Ordner", s.folder, "leer = im bisherigen Ordner arbeiten")
    + chk("psCopy", "In den Stufen-Ordner kopieren (Programm ersetzt dort die Dateien)", s.copy) + det
    + chk("psProtect", "Schutzregel „nur ergänzen“", s.protect) + inp("psAllow", "Erlaubte Felder", (s.allow || []).join(", "), "z. B. TKEY, TBPM, GEOB:*");
  if (s.type === "plugin") {
    const cur = `${s.plugin || ""}|${s.action || ""}`;
    const acts = pluginActs.map((a) => [`${a.plugin}|${a.id}`, `${a.plugin_name}: ${a.label.replace(/\s*…$/, "")}`]);
    if (s.plugin && !acts.some(([k]) => k === cur)) acts.unshift([cur, `${s.plugin}: ${s.action} (nicht verfügbar)`]);
    f += sel("psPlugin", "Plugin-Aktion", cur, acts.length ? acts : [["|", "kein Plugin bereit"]])
      + `<span></span><span class="muted sm">Es gelten die zuletzt im Tagger gewählten Optionen der Aktion.</span>`
      + sel("psMode", "Vorschläge", s.mode || "fill", Object.entries(PREP.d.plugin_modes || {}))
      + inp("psFolder", "Stufen-Ordner", s.folder, "_04_Lautheit")
      + chk("psProtect", "Schutzregel „nur ergänzen“", s.protect) + inp("psAllow", "Erlaubte Felder", (s.allow || []).join(", "), "z. B. TBPM, TKEY");
  }
  if (s.type === "verify") f += inp("psFields", "Pflichtfelder", (s.fields || []).join(", "), "z. B. TIT2, TPE1, TKEY, TBPM, APIC*, TXXX:ENERGY")
    + `<span></span><span class="muted sm">Fehlt ein Feld oder ist es leer, wird der Titel als Fehler markiert. Nach dem Ergänzen erneut prüfen.</span>`;
  if (s.type === "import") f += chk("psDup", "Auf Duplikate prüfen (Dateiname, Künstler + Titel, Audio)", s.dup !== false)
    + inp("psPlaylist", "In Playlist aufnehmen", s.playlist || "", "leer = keine; z. B. Neu/{Jahr}-{Monat}")
    + `<span></span><span class="muted sm">Übernommene Titel kommen in diese Playlist (wird angelegt). Platzhalter {Jahr}, {Monat}, {Tag}, {Workflow}; Ordner mit „/“ (#270).</span>`;
  if (s.type === "check") f += det + chk("psProtect", "Schutzregel „nur ergänzen“ (Vergleich mit dem Stand bei der Übernahme)", s.protect) + inp("psAllow", "Erlaubte Felder", (s.allow || []).join(", "));
  return f;
}

function prepReadStep(b, s) {
  const v = (id) => ($("#" + id, b) ? $("#" + id, b).value : undefined), c = (id) => !!($("#" + id, b) && $("#" + id, b).checked);
  const out = { ...s, label: v("psLabel") || s.label };
  if (s.type === "recipe") Object.assign(out, { recipe: v("psRecipe"), folder: v("psFolder") });
  if (s.type === "external") Object.assign(out, { program: v("psProgram"), args: v("psArgs"), folder: v("psFolder"), copy: c("psCopy"), detect: v("psDetect"), protect: c("psProtect"), allow: (v("psAllow") || "").split(/\s*,\s*/).filter(Boolean) });
  if (s.type === "import") Object.assign(out, { dup: c("psDup"), playlist: v("psPlaylist") || "" });
  if (s.type === "verify") Object.assign(out, { fields: (v("psFields") || "").split(/\s*,\s*/).filter(Boolean) });
  if (s.type === "plugin") { const [plugin, action] = (v("psPlugin") || "|").split("|"); Object.assign(out, { plugin, action, mode: v("psMode"), folder: v("psFolder"), protect: c("psProtect"), allow: (v("psAllow") || "").split(/\s*,\s*/).filter(Boolean) }); }
  if (s.type === "check") Object.assign(out, { detect: v("psDetect"), protect: c("psProtect"), allow: (v("psAllow") || "").split(/\s*,\s*/).filter(Boolean) });
  return out;
}

async function prepEditWorkflow() {
  const w = JSON.parse(JSON.stringify(PREP.d.workflow));
  const recipesList = (await call("recipes")).recipes;
  let pluginActs = [];
  try { pluginActs = await call("plugin_actions", "tagger"); } catch (e) { pluginActs = []; }
  const origins = PREP.d.origins || {};
  const render = (b) => {
    $("#pwSteps", b).innerHTML = w.steps.map((s, i) => `<div class="rc-act" data-k="${i}"><span class="rc-n">${i + 1}</span><span class="rc-t"><b>${esc(s.label)}</b> <span class="muted sm">${esc(PREP.d.types[s.type])}${s.folder ? ` · <span class="path-dir">${esc(s.folder)}</span>` : ""}${s.protect ? " · 🔒" : ""}${s.type === "external" && !s.program ? " · kein Programm" : ""}${s.type === "verify" ? " · " + esc((s.fields || []).join(", ")) : ""}${s.type === "plugin" ? " · " + esc(s.plugin ? `${s.plugin}/${s.action}` : "kein Plugin") : ""}</span></span>
      <button class="icon-btn" data-ps="edit" title="Bearbeiten">✎</button><button class="icon-btn" data-ps="up" ${i ? "" : "disabled"}>↑</button><button class="icon-btn" data-ps="down" ${i < w.steps.length - 1 ? "" : "disabled"}>↓</button><button class="icon-btn" data-ps="del" title="Entfernen">✕</button></div>`).join("");
  };
  const edit = (b, i) => {
    const s = w.steps[i];
    const box = $("#pwEdit", b);
    box.hidden = false;
    box.innerHTML = `<div class="frm">${prepStepForm(s, recipesList, origins, pluginActs)}</div><div class="rc-edit-b"><button class="ghost sm" data-pse="cancel">Abbrechen</button><button class="ghost sm" data-pse="ok"><b>Übernehmen</b></button></div>`;
    box.onclick = (e) => { if (e.target.closest("[data-pick]")) return; const t = e.target.closest("[data-pse]"); if (!t) return; e.stopPropagation(); if (t.dataset.pse === "ok") w.steps[i] = prepReadStep(box, s); box.hidden = true; box.innerHTML = ""; render(b); };
  };
  w.sources = w.sources || [];
  const srcRow = (q, k) => `<div class="prep-src-row" data-q="${k}"><input data-f="name" value="${esc(q.name || "")}" placeholder="Name, z. B. Bandcamp" aria-label="Name der Quelle">
    ${prepPathInput("pwSrcF" + k, q.folder || "", "Download-Ordner, z. B. C:\\Users\\…\\Downloads", "folder", 'data-f="folder" aria-label="Ordner"')}
    <input data-f="pattern" value="${esc(q.pattern || "")}" placeholder="Filter, z. B. *Beatport*;*.mp3" aria-label="Dateifilter" spellcheck="false">
    <input data-f="sub" value="${esc(q.sub || "")}" placeholder="Unterordner im Eingang (optional)" aria-label="Unterordner">
    <label class="check sm" title="MP3 aus ZIP-Archiven entpacken"><input type="checkbox" data-f="zip" ${q.zip !== false ? "checked" : ""}> ZIP</label>
    <button class="icon-btn" data-qdel title="Quelle entfernen">✕</button></div>`;
  const readSrc = (b) => [...b.querySelectorAll(".prep-src-row")].map((el) => { const q = w.sources[+el.dataset.q] || {}; const g = (f) => el.querySelector(`[data-f="${f}"]`); return { ...q, name: g("name").value.trim(), folder: g("folder").value.trim(), pattern: g("pattern").value.trim(), sub: g("sub").value.trim(), zip: g("zip").checked }; });
  const renderSrc = (b) => { $("#pwSrc", b).innerHTML = w.sources.map(srcRow).join("") || '<p class="muted sm" style="margin:0 0 6px">Keine Quellen.</p>'; };
  const p = w.protect;
  const res = await modal({
    title: "Workflow bearbeiten", wide: true,
    html: `<div class="frm"><label for="pwName">Name</label><input id="pwName" value="${esc(w.name)}">
        <label for="pwInbox">Eingangsordner</label>${prepPathInput("pwInbox", w.inbox, "z. B. S:\\_MP3\\00_Neu\\_01_Original")}
        <label for="pwWork">Arbeitsordner</label>${prepPathInput("pwWork", w.work, "leer = Ordner über dem Eingang (Stufen-Ordner kommen dorthin)")}
        <label for="pwLib">Bibliothek</label>${prepPathInput("pwLib", w.library, "z. B. S:\\_MP3\\01_Library")}</div>
      <h4 class="st-sub">Quellen (Download-Ordner)</h4>
      <p class="muted sm" style="margin:0 0 6px">„Abholen“ kopiert neue MP3 – auch aus ZIP-Archiven (z. B. Bandcamp) – in den Eingangsordner und merkt sich die Quelle. Die Downloads bleiben unverändert und werden nicht doppelt geholt.</p>
      <div id="pwSrc"></div><button class="ghost sm" id="pwSrcAdd">+ Quelle</button>
      <h4 class="st-sub">Schritte</h4><div class="rc-acts" id="pwSteps"></div><div class="rc-edit" id="pwEdit" hidden data-keep-enter></div>
      <div class="rc-add"><select id="pwType" class="inp">${Object.entries(PREP.d.types).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select><button class="ghost sm" id="pwAdd">+ Schritt</button></div>
      <h4 class="st-sub">Schutzregel „nur ergänzen“</h4>
      <div class="frm"><label for="pwVar">Geschützte Felder</label><select id="pwVar" class="inp"><option value="A" ${p.variant === "A" ? "selected" : ""}>A – alle Felder</option><option value="B" ${p.variant === "B" ? "selected" : ""}>B – nur die Liste</option><option value="C" ${p.variant === "C" ? "selected" : ""}>C – alle ausser freie Felder</option></select>
        <label for="pwFields">Liste (für B)</label><input id="pwFields" value="${esc(p.fields.join(", "))}">
        <label for="pwFree">Freie Felder (für C)</label><input id="pwFree" value="${esc(p.free.join(", "))}">
        <label for="pwOn">Bei Verstoss</label><select id="pwOn" class="inp"><option value="report" ${p.on_violation === "report" ? "selected" : ""}>nur melden</option><option value="revert" ${p.on_violation === "revert" ? "selected" : ""}>automatisch zurücksetzen</option></select></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }],
    onMount: (b) => {
      render(b); renderSrc(b);
      b.addEventListener("click", (e) => {
        if (e.target.closest("[data-pick]")) { prepPickClick(e, b); return; }
        const t = e.target.closest("button"); if (!t || t.closest("#pwEdit")) return;
        if (t.id === "pwSrcAdd") { w.sources = readSrc(b); w.sources.push({ name: "", folder: "", pattern: "", sub: "", zip: true }); renderSrc(b); const rows = b.querySelectorAll(".prep-src-row"); rows[rows.length - 1].querySelector("input").focus(); return; }
        if (t.hasAttribute("data-qdel")) { w.sources = readSrc(b); w.sources.splice(+t.closest(".prep-src-row").dataset.q, 1); renderSrc(b); return; }
        if (t.id === "pwAdd") { const type = $("#pwType", b).value; w.steps.push({ id: "", type, label: PREP.d.types[type], folder: ["recipe", "plugin"].includes(type) ? "_neu" : "", mode: "fill", ...(type === "verify" ? { fields: ["TIT2", "TPE1", "TKEY", "TBPM", "APIC*"] } : {}) }); render(b); edit(b, w.steps.length - 1); return; }
        const k = t.closest(".rc-act") ? +t.closest(".rc-act").dataset.k : -1;
        if (k < 0) return;
        if (t.dataset.ps === "edit") return edit(b, k);
        if (t.dataset.ps === "del") w.steps.splice(k, 1);
        else if (t.dataset.ps) { const j = k + (t.dataset.ps === "up" ? -1 : 1); [w.steps[k], w.steps[j]] = [w.steps[j], w.steps[k]]; }
        render(b);
      });
    },
    collect: (b) => {
      const v = (id) => $("#" + id, b).value;
      const list = (x) => x.split(/\s*,\s*/).filter(Boolean);
      return { ...w, sources: readSrc(b), name: v("pwName"), inbox: v("pwInbox").trim(), work: v("pwWork").trim(), library: v("pwLib").trim(),
        protect: { variant: v("pwVar"), fields: list(v("pwFields")), free: list(v("pwFree")), on_violation: v("pwOn") } };
    },
  });
  if (!res) return;
  try { prepApply(await call("prep_workflow_save", res)); toast("Workflow gespeichert."); } catch (e) { toast(String(e.message || e)); }
}

async function prepMoreMenu() {
  const d = PREP.d, b = $("#prepMore").getBoundingClientRect();
  showMenu(b.left, b.bottom + 6, [
    { label: "Neuer Workflow aus Vorlage", run: async () => prepApply(await call("prep_workflow_new", null)) },
    { label: "Workflow kopieren", run: async () => prepApply(await call("prep_workflow_new", d.workflow.id)) },
    { label: "Workflow exportieren …", run: async () => { const t = await call("prep_export", d.workflow.id); await modal({ title: "Workflow exportieren", html: `<p class="muted sm">Ohne Ordner und Programmpfade – zum Weitergeben kopieren.</p><textarea class="fe-val" rows="16" readonly>${esc(t)}</textarea>`, buttons: [...(S.settings.native ? [{ label: "Als Datei speichern …", value: "file" }] : []), { label: "Schliessen", value: null, primary: true }], onMount: (bd) => { const ta = bd.querySelector("textarea"); ta.focus(); ta.select(); } }).then(async (v) => { if (v !== "file") return; const r = await call("prep_export_file", d.workflow.id); if (r.ok) toast("Workflow gespeichert: " + r.path); else if (!r.cancelled) info("Export fehlgeschlagen", r.error); }); } },
    { label: "Workflow importieren …", run: async () => { const t = await modal({ title: "Workflow importieren", html: '<textarea class="fe-val" id="pwImp" rows="14" placeholder="Exportierten Workflow (JSON) hier einfügen" spellcheck="false"></textarea>', buttons: [{ label: "Abbrechen", value: null }, { label: "Importieren", value: true, primary: true }], collect: (bd) => bd.querySelector("#pwImp").value }); if (!t) return; try { prepApply(await call("prep_import", t)); toast("Workflow importiert – Ordner und Programme festlegen."); } catch (e) { toast(String(e.message || e)); } } },
    "-",
    { label: "Stufen-Kopien übernommener Titel löschen …", run: prepCleanup },
    { label: "Workflow löschen …", run: async () => { if (await dialog({ title: "Workflow löschen", text: `Workflow „${d.workflow.name}“ löschen? Dateien bleiben unverändert.`, buttons: [{ label: "Abbrechen", value: null }, { label: "Löschen", value: true, primary: true }] })) prepApply(await call("prep_workflow_delete", d.workflow.id)); } },
  ]);
}

async function prepCleanup() {
  const d = PREP.d;
  const r = await call("prep_cleanup", d.workflow.id, prepNames(), false);
  if (!r.count) { toast("Keine Stufen-Kopien übernommener Titel vorhanden."); return; }
  const ok = await modal({ title: "Stufen-Kopien löschen", html: `<p style="margin:0 0 8px">${fmtN(r.count)} Datei(en) in den Stufen-Ordnern gehören zu Titeln, die schon in der Bibliothek sind. Endgültig löschen? Eingangsordner und Bibliothek bleiben unverändert.</p><div class="fx-table" style="max-height:30vh"><table><tbody>${r.files.slice(0, 300).map((p) => `<tr><td>${esc(p)}</td></tr>`).join("")}</tbody></table></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: `${fmtN(r.count)} Datei(en) löschen`, value: true, primary: true }] });
  if (!ok) return;
  const x = await call("prep_cleanup", d.workflow.id, prepNames(), true);
  status(`${fmtN(x.removed)} Stufen-Kopie(n) gelöscht.`, "info");
  prepShow();
}

/** Seitenleiste: offene Titel im Eingang, auch ohne die Seite zu öffnen (alle 2 Minuten, liest keine Tags) */
async function prepPendingTick() {
  if (typeof S !== "undefined" && S.module === "prep") return;
  try {
    const r = await call("prep_pending");
    const el = $("#prepCount"); if (!el) return;
    el.textContent = r.count ? String(r.count) : r.sources ? `↓${r.sources}` : "";
    el.title = "Titel im Eingang, die noch nicht übernommen sind" + (r.new ? ` – davon ${r.new} neu` : "");
    el.classList.toggle("new", !!(r.new || r.sources));
    if (r.sources) el.title += ` – ${r.sources} neue(r) Download(s) zum Abholen`;
  } catch (e) { /* noch nicht bereit */ }
}

(function bindPrep() {
  setTimeout(prepPendingTick, 4000);
  setInterval(prepPendingTick, 120000);
  $("#prepRefresh").addEventListener("click", prepShow);
  $("#prepFetch").addEventListener("click", prepFetch);
  $("#prepEdit").addEventListener("click", prepEditWorkflow);
  $("#prepMore").addEventListener("click", (e) => { e.stopPropagation(); prepMoreMenu(); });
  $("#prepWf").addEventListener("change", async (e) => { PREP.sel.clear(); prepApply(await call("prep_refresh", e.target.value)); });
  $("#prepSteps").addEventListener("click", (e) => {
    const r = e.target.closest("[data-run]"); if (r) { prepRun(r.dataset.run); return; }
    const f = e.target.closest("[data-folder]"); if (f) call("open_folder", (PREP.d.work || "") + (PREP.d.work.includes("\\") ? "\\" : "/") + f.dataset.folder);
  });
  $("#prepTable").addEventListener("change", (e) => {
    if (e.target.id === "prepAll") { PREP.sel = e.target.checked ? new Set(PREP.d.rows.map((r) => r.name)) : new Set(); prepRenderTable(); return; }
    const tr = e.target.closest("tr[data-name]"); if (!tr || !e.target.matches("[data-sel]")) return;
    if (e.target.checked) PREP.sel.add(tr.dataset.name); else PREP.sel.delete(tr.dataset.name);
  });
  $("#prepTable").addEventListener("click", (e) => {
    const td = e.target.closest("td.pc"); if (!td) return;
    e.stopPropagation();
    prepCellMenu(e, td.closest("tr").dataset.name, +td.dataset.step);
  });
})();
