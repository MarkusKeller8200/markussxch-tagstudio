/* MarKusSXCH TagStudio – Plugins: Verwaltungsseite und Aktionen (z. B. im Tagger).
   Formulare werden aus den Optionen des Plugins erzeugt – Plugins brauchen kein eigenes JavaScript. */
"use strict";

const PL = { list: [], userDir: "", logDir: "", frozen: false };

const PL_STATE = {
  ready: ["Bereit", "st-ok"],
  missing: ["Pakete fehlen", "st-missing"],
  error: ["Fehler", "st-err"],
};

async function pluginsShow(rescan = false) {
  const r = await call("plugins_list", rescan);
  PL.list = r.plugins; PL.userDir = r.user_dir; PL.logDir = r.log_dir; PL.frozen = r.frozen;
  $("#plDir").textContent = "Eigene Plugins: " + r.user_dir;
  renderPlugins();
}

function renderPlugins() {
  const box = $("#plList");
  if (!PL.list.length) { box.innerHTML = '<div class="empty">Keine Plugins gefunden.</div>'; return; }
  box.innerHTML = PL.list.map((p) => {
    const [stTxt, stCls] = p.enabled ? PL_STATE[p.state] : ["Ausgeschaltet", "st-same"];
    const missing = p.state === "missing" ? `<div class="pl-box warn">
        <div><b>${p.env ? "Noch nicht installiert:" : "Fehlende Python-Pakete:"}</b> ${p.missing.map((m) => esc(m.label)).join(", ")}</div>
        ${PL.frozen && !p.env ? '<div class="hint">In der gepackten App können keine Pakete nachinstalliert werden.</div>'
          : `<div class="pl-inst">${p.install.map((v) => `<button class="ghost sm" data-install="${esc(v.id)}" title="pip install ${esc(v.packages.join(" "))}">${esc(v.label)}</button>`).join("")}</div>
             ${p.install.map((v) => v.hint ? `<div class="hint">${esc(v.label.replace(/^Installieren\s*\(?|\)$/g, ""))}: ${esc(v.hint)}</div>` : "").join("")}`}
        ${p.notes ? `<div class="hint">${esc(p.notes)}</div>` : ""}</div>` : "";
    const ext = p.external.length ? `<div class="pl-box warn"><b>Zusätzlich nötig:</b> ${p.external.map((e) => `${esc(e.label)}${e.hint ? ` <span class="hint">– ${esc(e.hint)}</span>` : ""}`).join("<br>")}</div>` : "";
    const err = p.state === "error" ? `<div class="pl-box err">${esc(p.error)}</div>` : "";
    const envOk = p.env && p.state === "ready" && p.install.length ? `<div class="pl-env"><span class="muted sm">Umgebung: ${esc((p.env_variant || "installiert").replace(/^Installieren\s*\(?|\)$/g, ""))}</span>
        <details><summary class="sm">Neu installieren / andere Variante …</summary><div class="pl-inst">${p.install.map((v) => `<button class="ghost sm" data-install="${esc(v.id)}">${esc(v.label)}</button>`).join("")}</div></details></div>` : "";
    const acts = p.actions.length ? `<div class="pl-acts"><span class="muted sm">Aktionen:</span> ${p.actions.map((a) => `<span class="pl-act" title="${esc(a.description)}">${esc(a.label.replace(/\s*…$/, ""))}${a.where === "tagger" ? ' <span class="faint">· Tagger</span>' : ""}</span>`).join("")}</div>` : "";
    return `<section class="card pl-card${p.enabled ? "" : " off"}" data-pid="${esc(p.id)}">
      <div class="pl-head">
        <div class="pl-ico"><svg class="i" viewBox="0 0 24 24"><path d="M9 3h6v3a2 2 0 1 0 4 0V3h2v6h-3a2 2 0 1 0 0 4h3v8h-6v-3a2 2 0 1 0-4 0v3H3v-8h3a2 2 0 1 0 0-4H3V3h6Z"/></svg></div>
        <div class="pl-t"><h3>${esc(p.name)} <span class="muted sm">${esc(p.version)}</span>${p.builtin ? ' <span class="pl-tag">eingebaut</span>' : ' <span class="pl-tag own">eigenes</span>'}</h3>
          <div class="sm ${stCls}">● ${stTxt}</div></div>
        <label class="switch" title="${p.enabled ? "Ausschalten" : "Einschalten"}"><input type="checkbox" data-enable ${p.enabled ? "checked" : ""} aria-label="${esc(p.name)} ein/aus"><span></span></label>
      </div>
      <p class="pl-desc">${esc(p.description)}</p>
      ${p.enabled ? err + missing + ext + acts + envOk : ""}
      <div class="hint pl-path" title="${esc(p.path)}">${esc(p.path)}</div>
    </section>`;
  }).join("");
}

async function pluginInstall(pid, variant) {
  const p = PL.list.find((x) => x.id === pid), v = p.install.find((x) => x.id === variant);
  const ok = await dialog({ title: "Pakete installieren?",
    text: (p.env
      ? `Für „${p.name}“ wird eine eigene Python-Umgebung angelegt und darin installiert:\n${v.packages.join(" ")}`
      : `Es wird ausgeführt:\npip install ${v.packages.join(" ")}`)
      + `\n\n${p.notes ? p.notes + "\n\n" : ""}Das kann je nach Verbindung einige Minuten dauern. Abbrechen ist jederzeit möglich.`,
    buttons: [{ label: "Abbrechen", value: false }, { label: "Installieren", value: true, primary: true }] });
  if (!ok) return;
  const res = await runTask(call("start_plugin_install", pid, variant), `${p.name}: Pakete installieren`);
  if (!res) return;
  if (res.cancelled) { status("Installation abgebrochen.", "warn"); }
  else if (res.ok) {
    await info("Installation abgeschlossen", res.state === "ready"
      ? `${p.name} ist jetzt bereit.`
      : `pip war erfolgreich, das Paket wird aber noch nicht gefunden. Bitte TagStudio neu starten.`);
  } else {
    await info("Installation fehlgeschlagen", `${res.error}\n\n${(res.log || []).slice(-15).join("\n")}${res.logfile ? `\n\nVollständiges Protokoll: ${res.logfile}` : ""}`);
  }
  await pluginsShow(true);
  if (typeof renderTgEditor === "function") { PL.actionsCache = null; renderTgEditor(); }
}

// ---------------------------------------------------------------------- Aktionen ausführen
async function pluginActions(where = "tagger") {
  if (!PL.actionsCache) PL.actionsCache = await call("plugin_actions", where);
  return PL.actionsCache;
}

function pluginOptionHtml(o, n) {
  const id = `plo-${n}`;
  const lab = `<label for="${id}">${esc(o.label || o.key)}</label>`;
  if (o.type === "info") return `<span></span><div class="hint">${esc(o.label)}</div>`;
  if (o.type === "check") return `<span></span><label class="check"><input type="checkbox" id="${id}" data-ok="${esc(o.key)}" ${o.value ? "checked" : ""}> ${esc(o.label || o.key)}</label>`;
  if (o.type === "select") return lab + `<select id="${id}" class="inp" data-ok="${esc(o.key)}">${(o.choices || []).map((c) => { const [v, l] = Array.isArray(c) ? c : [c, c]; return `<option value="${esc(v)}" ${String(v) === String(o.value) ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select>`;
  if (o.type === "folder") return lab + `<div class="pl-folder"><input id="${id}" data-ok="${esc(o.key)}" value="${esc(o.value)}" spellcheck="false" placeholder="Ordner …"><button class="ghost sm" data-plpick="${id}">Wählen …</button></div>`;
  return lab + `<input id="${id}" data-ok="${esc(o.key)}" ${o.type === "number" ? 'type="number" step="any"' : ""} value="${esc(o.value)}" spellcheck="false">`;
}

async function pluginRun(pid, aid) {
  const idx = typeof tgSelected === "function" ? tgSelected() : [];
  const f = await call("plugin_form", pid, aid);
  if (f.needs_selection && !idx.length) { toast("Bitte zuerst Dateien markieren."); return; }
  const values = await modal({
    title: `${f.label.replace(/\s*…$/, "")}${f.needs_selection ? ` (${idx.length} Datei(en))` : ""}`,
    wide: true,
    html: `${f.description ? `<p class="muted" style="margin:0">${esc(f.description)}</p>` : ""}
      <div class="frm">${f.options.map(pluginOptionHtml).join("")}</div>
      <div class="hint">Plugin: ${esc(f.plugin_name)}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: f.run_label, value: true, primary: true }],
    onMount: (b) => b.querySelectorAll("[data-plpick]").forEach((btn) => btn.addEventListener("click", async () => {
      const inp = $("#" + btn.dataset.plpick, b);
      const p = await call("pick_path", "", true, inp.value.trim());
      if (p) inp.value = p; else if (!S.settings.native) toast("Pfad bitte direkt ins Feld eintippen.");
    })),
    collect: (b) => Object.fromEntries([...b.querySelectorAll("[data-ok]")].map((el) => [el.dataset.ok, el.type === "checkbox" ? el.checked : el.value])),
  });
  if (!values) return;
  const res = await runTask(call("start_plugin_action", pid, aid, idx, values), f.label.replace(/\s*…$/, ""));
  if (!res) return;
  if (res.changed && typeof taggerRefresh === "function") await taggerRefresh();
  if (res.cancelled) { status("Abgebrochen.", "warn"); if (!res.log.length) return; }
  const log = (res.log || []).slice(-40).join("\n");
  const outs = res.outputs || [];
  const btns = [{ label: "OK", value: null, primary: !outs.length }];
  if (outs.length) btns.push({ label: IS_MAC ? "Im Finder zeigen" : "Im Explorer zeigen", value: "reveal", primary: true });
  const what = await modal({
    title: res.cancelled ? "Abgebrochen" : f.label.replace(/\s*…$/, ""),
    html: `<p style="margin:0">${esc(res.message || "")}</p>${log ? `<pre class="pl-log">${esc(log)}</pre>` : ""}`,
    buttons: btns,
  });
  if (what === "reveal") call("reveal", outs[0]);
  if (res.message) status(res.message, "info");
}

// ---------------------------------------------------------------------- Ereignisse
(function bindPlugins() {
  $("#plRescan").addEventListener("click", async () => { PL.actionsCache = null; await pluginsShow(true); toast("Plugins neu eingelesen."); if (typeof renderTgEditor === "function") renderTgEditor(); });
  $("#plLogs").addEventListener("click", async () => { if (!(await call("open_folder", PL.logDir))) toast("Ordner konnte nicht geöffnet werden."); });
  $("#plOpen").addEventListener("click", async () => { if (!(await call("open_folder", PL.userDir))) toast("Ordner konnte nicht geöffnet werden."); });
  $("#plList").addEventListener("change", async (e) => {
    const cb = e.target.closest("[data-enable]"); if (!cb) return;
    const pid = cb.closest("[data-pid]").dataset.pid;
    const r = await call("plugin_enable", pid, cb.checked);
    PL.list = r.plugins; PL.actionsCache = null; renderPlugins();
    if (typeof renderTgEditor === "function") renderTgEditor();
  });
  $("#plList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-install]"); if (!b) return;
    pluginInstall(b.closest("[data-pid]").dataset.pid, b.dataset.install);
  });
})();
