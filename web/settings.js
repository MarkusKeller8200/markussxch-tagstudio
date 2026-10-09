/* MarKusSXCH TagStudio – Seite „Einstellungen“ (#21): alle Optionen an einem Ort, Export/Import, Zurücksetzen.
   Gespeichert wird sofort über die jeweiligen Sitzungs-Aufrufe; Export/Import/Zurücksetzen über appsettings.py. */
"use strict";

const ST = { data: null };

const stSel = (id, opts, cur) => `<select class="inp" id="${id}">${opts.map(([v, l]) => `<option value="${esc(String(v))}"${String(v) === String(cur) ? " selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
const stCheck = (id, on, label) => `<label class="check"><input type="checkbox" id="${id}"${on ? " checked" : ""}> ${esc(label)}</label>`;

async function settingsShow() {
  const d = ST.data = await call("settings_page");
  const f = d.file;
  $("#stFile").textContent = `Datei: ${f.path}${f.exists ? "" : " (noch nicht angelegt)"} · Sicherungen vor Import/Zurücksetzen: ${f.backup_dir}`;
  const p = d.player;
  $("#stGrid").innerHTML = `
    <section class="card"><h3>Darstellung</h3>
      <div class="st-row"><span>Design</span>
        <div class="seg" id="stTheme"><button data-v="dark"${d.theme !== "light" ? ' class="on"' : ""}>Dunkel</button><button data-v="light"${d.theme === "light" ? ' class="on"' : ""}>Hell</button></div>
        <label for="stNotation">Tonart-Schreibweise</label>${stSel("stNotation", d.notations, d.key_notation)}
        <span>Tagger</span>${stCheck("stStemsFlat", d.stems_flat, "Stems als eigene Titel anzeigen (statt aufklappbar unter dem Original)")}
      </div></section>
    <section class="card"><h3>Speichern und Sicherungen</h3>
      <div class="st-row">
        <label for="stSaveVer">ID3-Version beim Speichern</label>${stSel("stSaveVer", [[0, "beibehalten (wie die Datei)"], [3, "immer ID3v2.3 (am verträglichsten)"], [4, "immer ID3v2.4"]], d.save_version)}
        <span>Sicherung</span>${stCheck("stBackup", d.backup_enabled, "Vor dem Speichern die bisherigen Tags sichern")}
        <span>Sicherungsordner</span><div class="st-path"><code title="${esc(d.backup_dir)}">${esc(d.backup_dir)}</code><button class="ghost sm" id="stBkFolder">Ändern …</button><button class="ghost sm" id="stBkOpen">Öffnen</button></div>
      </div></section>
    <section class="card"><h3>Player</h3>
      <div class="st-row">
        <label for="stPlStart">Startpunkt</label>${stSel("stPlStart", [["0", "ab Anfang"], ["30", "ab 30 %"], ["60", "ab 1:00"], ["cue", "ab 1. Cue"]], p.start)}
        <span>Anzeige</span>${stCheck("stPlWave", p.wave, "Wellenform anzeigen (einmal berechnet, im Cache)")}
        <span>Durchhören</span>${stCheck("stPlFollow", p.follow, "Beim Wechsel der Markierung weiterspielen, am Titelende nächster Titel")}
        <span>Externe Player</span><div class="st-path"><span>${d.players ? `${d.players} eingerichtet` : "keiner – Standardprogramm des Systems"}</span><button class="ghost sm" id="stPlayers">Einrichten …</button></div>
      </div></section>
    <section class="card" id="stOriginCard" hidden></section>
    <section class="card"><h3>Unwichtige Felder</h3>
      <p class="muted sm" style="margin:0">Felder, die sich zwischen Dateien fast immer unterscheiden (Analyse-Daten, Kodierer …). Im Vergleich lassen sie sich ausblenden und zählen nicht als Unterschied. Muster mit <code>*</code>, z. B. <code>TXXX:MusicBrainz*</code> oder <code>GEOB:*</code>.</p>
      <div class="st-chips" id="stTriv"></div>
      <div class="st-add"><input class="inp" id="stTrivIn" placeholder="Muster hinzufügen, z. B. TXXX:Serato*" spellcheck="false"><button class="ghost sm" id="stTrivAdd">Hinzufügen</button><button class="ghost sm" id="stTrivDef" title="Standardliste wiederherstellen">Standard</button></div>
    </section>
    <section class="card" id="stCache"><h3>Cache</h3><div class="st-row" id="stCacheRows"><span class="muted sm">…</span></div></section>
    <section class="card"><h3>Plugins</h3>
      <p class="muted sm" style="margin:0">Plugins ein-/ausschalten, Pakete installieren und Optionen festlegen – auf der Seite „Plugins“.</p>
      <div><button class="ghost sm" id="stPlugins" style="width:auto">Zur Plugin-Seite</button></div>
    </section>`;
  stTrivRender();
  stCacheRender();
  if (typeof originSettingsRender === "function") originSettingsRender($("#stOriginCard"));
}

async function stCacheRender(info) {
  const c = info || await call("cache_info");
  const mb = (b) => (b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1).replace(".", ",")} MB`);
  const row = (k, label) => `<span>${label}</span><div class="st-path"><span>${fmtN(c[k].count)} Datei(en) · ${mb(c[k].bytes)}</span>
    <button class="ghost sm" data-cclear="${k}" ${c[k].count ? "" : "disabled"}>Leeren</button><button class="ghost sm" data-copen="${esc(c[k].dir)}">Ordner</button></div>`;
  $("#stCacheRows").innerHTML = row("wave", "Wellenformen") + row("covers", "Cover-Vorschauen");
}

function stTrivRender() {
  const d = ST.data, def = new Set(d.trivial_default);
  $("#stTriv").innerHTML = d.trivial.length
    ? d.trivial.map((t, k) => `<span class="st-chip${def.has(t) ? " def" : ""}" title="${def.has(t) ? "Standard" : "eigenes Muster"}">${esc(t)}<button data-k="${k}" aria-label="${esc(t)} entfernen">✕</button></span>`).join("")
    : '<span class="muted sm">Keine – alle Felder zählen.</span>';
}

async function stTrivSet(list) {
  ST.data.trivial = await call("set_trivial", list);
  stTrivRender();
  if (S.pairs && S.pairs.length) refreshAll(await call("state"));
}

async function stTransfer(kind) {
  if (kind === "export") {
    if (S.settings.native) {
      const r = await call("settings_export");
      if (r.ok) toast("Einstellungen exportiert: " + r.path); else if (!r.cancelled) info("Export fehlgeschlagen", r.error);
    } else {
      const text = await call("settings_export_text");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
      a.download = `TagStudio-Einstellungen-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast("Einstellungen als Download gespeichert.");
    }
    return;
  }
  if (S.settings.native) {
    const r = await call("settings_import_pick");
    if (r && r.error) return info("Import nicht möglich", r.error);
    if (r) stImportText(r.text, r.name);
  } else {
    const inp = $("#stFileIn");
    inp.value = "";
    inp.onchange = async () => { const f = inp.files[0]; if (f) stImportText(await f.text(), f.name); };
    inp.click();
  }
}

async function stImportText(text, name) {
  const pv = await call("settings_import_preview", text);
  if (!pv.ok) return info("Import nicht möglich", pv.error);
  if (!pv.groups.length) return info("Nichts zu importieren", "Die Datei enthält keine bekannten Einstellungen.");
  const from = [pv.app_version && `TagStudio ${pv.app_version}`, pv.platform && { win32: "Windows", darwin: "macOS", linux: "Linux" }[pv.platform] || pv.platform, pv.exported && pv.exported.replace("T", " ")].filter(Boolean).join(" · ");
  const groups = await modal({
    title: "Einstellungen importieren",
    html: `<div class="hint">${esc(name || "Datei")}${from ? " – " + esc(from) : ""}</div>
      ${pv.foreign ? '<div class="hint" style="margin-top:6px">Von einem anderen System: Pfade (Verlauf, Sicherungsordner, Player) sind nicht vorgewählt.</div>' : ""}
      <div class="st-groups">${pv.groups.map((g) => `<label class="check"><input type="checkbox" value="${esc(g.id)}"${g.default ? " checked" : ""}> ${esc(g.label)}<span class="n">${g.changed ? `${g.changed} geändert` : "gleich"}</span></label>`).join("")}</div>
      <div class="muted sm" style="margin-top:10px">Die bisherige Einstellungsdatei wird vorher gesichert. Danach lädt die Oberfläche neu.</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Importieren", value: true, primary: true }],
    collect: (b) => $$(".st-groups input:checked", b).map((x) => x.value),
  });
  if (!groups) return;
  if (!groups.length) return toast("Nichts gewählt.");
  if (!(await confirmDiscard())) return;
  const r = await call("settings_import", text, groups);
  if (!r.ok) return info("Import fehlgeschlagen", r.error);
  toast(`${r.keys} Einstellung(en) übernommen.`);
  setTimeout(() => location.reload(), 600);
}

async function stReset() {
  const groups = await modal({
    title: "Einstellungen zurücksetzen",
    html: `<div class="hint">Gewählte Bereiche gehen auf den Auslieferungszustand zurück. Die bisherige Datei wird vorher gesichert.</div>
      <div class="st-groups">${ST.data.groups.map(([id, label]) => `<label class="check"><input type="checkbox" value="${esc(id)}"${id === "layout" ? " checked" : ""}> ${esc(label)}</label>`).join("")}
      <label class="check" style="margin-top:6px"><input type="checkbox" value="all" id="stAll"> <b>Alles zurücksetzen</b></label></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Zurücksetzen", value: true, primary: true }],
    onMount: (b) => $("#stAll", b).addEventListener("change", (e) => $$(".st-groups input:not(#stAll)", b).forEach((x) => { x.disabled = e.target.checked; })),
    collect: (b) => ($("#stAll", b).checked ? "all" : $$(".st-groups input:checked", b).map((x) => x.value)),
  });
  if (!groups || (Array.isArray(groups) && !groups.length)) return;
  if (!(await confirmDiscard())) return;
  const r = await call("settings_reset", groups);
  if (!r.ok) return info("Zurücksetzen fehlgeschlagen", r.error);
  if (groups === "all" || groups.includes("player") || groups.includes("layout")) { try { Object.keys(localStorage).filter((k) => k.startsWith("ts_")).forEach((k) => localStorage.removeItem(k)); } catch (e) { /* egal */ } }
  toast("Zurückgesetzt – die bisherige Datei liegt im Sicherungsordner.");
  setTimeout(() => location.reload(), 600);
}

// ---------------------------------------------------------------------- Herkunft der Tags (#22)
async function originSettingsRender(card) {
  const o = await call("tag_origins");
  S.settings.origins = o.catalog;
  ST.origins = o.custom.length ? o.custom.map((r) => ({ ...r })) : [];
  const cat = o.catalog, ids = Object.keys(cat).filter((k) => cat[k].kind !== "id3").sort((a, b) => cat[a].name.localeCompare(cat[b].name));
  const triv = new Set(ST.data.trivial.map((t) => t.toLowerCase()));
  card.hidden = false;
  card.innerHTML = `<h3>Herkunft der Tags</h3>
    <p class="muted sm" style="margin:0">TagStudio zeigt bei „Weitere Felder“ und im Vergleich, welche Anwendung ein Feld geschrieben hat. Eigene Zuordnungen gehen vor der eingebauten Liste.</p>
    ${stCheck("orStd", o.std_badge, "v2.3/v2.4-Kennzeichen auch bei Standardfeldern (Titel, Künstler, BPM …)")}
    <div class="or-list" id="orList"></div>
    <div><button class="ghost sm" id="orAdd" style="width:auto">+ Zuordnung</button> <button class="primary sm" id="orSave" style="width:auto" hidden>Zuordnungen speichern</button></div>
    <details class="or-all"><summary>Bekannte Herkünfte (${ids.length})</summary>
      ${ids.map((k) => { const v = cat[k], all = v.patterns.length && v.patterns.every((p) => triv.has(p.toLowerCase()));
        return `<div class="or-src">${srcBadge(k)}<div class="d"><b>${esc(v.name)}</b> – ${esc(v.desc)}<br><code>${esc(v.patterns.join("  ·  "))}</code></div>
        ${v.patterns.length ? `<button class="ghost sm" data-triv="${esc(k)}" ${all ? "disabled" : ""} title="Muster dieser Herkunft zu den unwichtigen Feldern hinzufügen">${all ? "unwichtig ✓" : "als unwichtig"}</button>` : ""}</div>`; }).join("")}
    </details>`;
  orRender();
}

function orRender() {
  $("#orList").innerHTML = ST.origins.length
    ? `<div class="or-row or-head"><span class="muted sm">Feld-Muster</span><span class="muted sm">Herkunft</span><span></span></div>` + ST.origins.map((r, k) => `<div class="or-row" data-k="${k}">
        <input class="pat" value="${esc(r.pattern)}" placeholder="z. B. TXXX:VDJ*" spellcheck="false" aria-label="Feld-Muster">
        <input class="src" value="${esc(r.source)}" placeholder="z. B. VirtualDJ" aria-label="Herkunft" list="orNames">
        <button class="x" data-ordel="${k}" title="Entfernen" aria-label="Entfernen">✕</button></div>`).join("")
      + `<datalist id="orNames">${Object.values(S.settings.origins || {}).filter((v) => v.kind !== "plugin").map((v) => `<option value="${esc(v.name)}">`).join("")}</datalist>`
    : '<span class="muted sm">Keine eigenen Zuordnungen.</span>';
}

function orRead() {
  return $$("#orList .or-row[data-k]").map((r) => ({ pattern: $(".pat", r).value.trim(), source: $(".src", r).value.trim() }));
}

function initSettings() {
  $("#stExport").addEventListener("click", () => stTransfer("export"));
  $("#stImport").addEventListener("click", () => stTransfer("import"));
  $("#stReset").addEventListener("click", () => stReset());
  const grid = $("#stGrid");
  grid.addEventListener("click", async (e) => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.closest("#stTheme")) {
      S.opts.theme = t.dataset.v; applyTheme(); await call("set_option", "theme", S.opts.theme);
      $$("#stTheme button").forEach((b) => b.classList.toggle("on", b === t));
    } else if (t.id === "stBkFolder") { const d = await call("backup_pick_folder"); if (d) settingsShow(); else if (!S.settings.native) toast("Im Browser-Modus ist kein Ordnerdialog verfügbar."); }
    else if (t.id === "stBkOpen") call("open_folder", ST.data.backup_dir);
    else if (t.id === "stPlayers") { await plSetup(); settingsShow(); }
    else if (t.id === "stPlugins") setModule("plugins");
    else if (t.dataset.cclear) {
      const what = t.dataset.cclear === "wave" ? "Wellenformen" : "Cover-Vorschauen";
      if (await dialog({ title: `${what} leeren?`, text: "Sie werden bei Bedarf neu berechnet.", buttons: [{ label: "Abbrechen", value: null }, { label: "Leeren", value: true, primary: true }] })) {
        const r = await call("cache_clear", t.dataset.cclear); stCacheRender(r); toast(`${r.removed} Datei(en) entfernt.`);
        if (t.dataset.cclear === "wave" && PLAYER.info) PLAYER.info.wave = null;
      }
    }
    else if (t.dataset.copen) call("open_folder", t.dataset.copen);
    else if (t.id === "stTrivAdd") { const v = $("#stTrivIn").value.trim(); if (v) { await stTrivSet([...ST.data.trivial, v]); $("#stTrivIn").value = ""; } }
    else if (t.id === "stTrivDef") { if (await dialog({ title: "Standardliste wiederherstellen?", text: "Eigene Muster gehen verloren.", buttons: [{ label: "Abbrechen", value: null }, { label: "Wiederherstellen", value: true, primary: true }] })) stTrivSet(ST.data.trivial_default); }
    else if (t.dataset.k !== undefined && t.closest("#stTriv")) { const l = [...ST.data.trivial]; l.splice(+t.dataset.k, 1); stTrivSet(l); }
    else if (t.id === "orAdd") { ST.origins = orRead(); ST.origins.push({ pattern: "", source: "" }); orRender(); $("#orSave").hidden = false; $$("#orList .pat").pop()?.focus(); }
    else if (t.dataset.ordel !== undefined) { ST.origins = orRead(); ST.origins.splice(+t.dataset.ordel, 1); orRender(); $("#orSave").hidden = false; }
    else if (t.id === "orSave") {
      const rules = orRead().filter((r) => r.pattern || r.source);
      if (rules.some((r) => !r.pattern || !r.source)) return toast("Bitte Muster und Herkunft ausfüllen.");
      const o = await call("set_tag_origins", rules);
      S.settings.origins = o.catalog;
      toast(`${o.custom.length} eigene Zuordnung(en) gespeichert.`);
      originSettingsRender($("#stOriginCard"));
      if (S.module === "settings" && TG.detail) renderTgEditor();
    }
    else if (t.dataset.triv) {
      const pats = (S.settings.origins[t.dataset.triv] || {}).patterns || [];
      const have = new Set(ST.data.trivial.map((x) => x.toLowerCase()));
      await stTrivSet([...ST.data.trivial, ...pats.filter((p) => !have.has(p.toLowerCase()))]);
      toast(`${S.settings.origins[t.dataset.triv].name}: Felder gelten jetzt als unwichtig.`);
      originSettingsRender($("#stOriginCard"));
    }
  });
  grid.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "stTrivIn") { e.preventDefault(); $("#stTrivAdd").click(); } });
  grid.addEventListener("input", (e) => { if (e.target.closest("#orList")) $("#orSave").hidden = false; });
  grid.addEventListener("change", async (e) => {
    const t = e.target;
    if (t.id === "stNotation") {
      await call("tag_key_notation", t.value);
      if (typeof TG !== "undefined" && TG.settings && TG.settings.keys) { TG.settings.keys.notation = t.value; }
      toast("Tonart-Schreibweise gespeichert.");
    } else if (t.id === "stSaveVer") { await call("set_save_version", +t.value); toast(+t.value ? `Beim Speichern immer ID3v2.${t.value}.` : "ID3-Version bleibt wie in der Datei."); }
    else if (t.id === "stBackup") { await call("set_backup", t.checked, null); if (!t.checked) toast("Achtung: Vor dem Speichern wird nicht mehr gesichert."); }
    else if (t.id === "stStemsFlat") { await call("set_stems_flat", t.checked); if (TG.loaded) { TG.open = new Set(); await taggerRefresh(); } toast(t.checked ? "Stems erscheinen als eigene Titel." : "Stems erscheinen aufklappbar unter dem Original."); }
    else if (t.id === "orStd") {
      await call("set_origin_std_badge", t.checked);
      if (S.pairs && S.pairs.length) refreshAll(await call("state"));
      toast(t.checked ? "Auch Standardfelder zeigen ihre ID3-Version." : "Standardfelder ohne Kennzeichen.");
    }
    else if (t.id === "stPlStart") plSetPref("start", t.value);
    else if (t.id === "stPlWave") plSetPref("wave", t.checked);
    else if (t.id === "stPlFollow") plSetPref("follow", t.checked);
  });
}

initSettings();
