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
    const pageActs = p.actions.filter((a) => a.where === "page");
    const page = p.enabled && p.state === "ready" && (pageActs.length || p.status_text) ? `<div class="pl-page">${p.status_text ? `<span class="sm pl-stat">${esc(p.status_text)}</span>` : ""}
      ${pageActs.map((a) => `<button class="ghost sm" data-paction="${esc(a.id)}" title="${esc(a.description)}">${esc(a.label)}</button>`).join("")}</div>` : "";
    const acts = p.actions.filter((a) => a.where !== "page").length ? `<div class="pl-acts"><span class="muted sm">Aktionen:</span> ${p.actions.filter((a) => a.where !== "page").map((a) => `<span class="pl-act" title="${esc(a.description)}">${esc(a.label.replace(/\s*…$/, ""))}${a.where === "tagger" ? ' <span class="faint">· Tagger</span>' : ""}</span>`).join("")}</div>` : "";
    return `<section class="card pl-card${p.enabled ? "" : " off"}" data-pid="${esc(p.id)}">
      <div class="pl-head">
        <div class="pl-ico"><svg class="i" viewBox="0 0 24 24"><path d="M9 3h6v3a2 2 0 1 0 4 0V3h2v6h-3a2 2 0 1 0 0 4h3v8h-6v-3a2 2 0 1 0-4 0v3H3v-8h3a2 2 0 1 0 0-4H3V3h6Z"/></svg></div>
        <div class="pl-t"><h3>${esc(p.name)} <span class="muted sm">${esc(p.version)}</span>${p.builtin ? ' <span class="pl-tag">eingebaut</span>' : ' <span class="pl-tag own">eigenes</span>'}</h3>
          <div class="sm ${stCls}">● ${stTxt}</div></div>
        <label class="switch" title="${p.enabled ? "Ausschalten" : "Einschalten"}"><input type="checkbox" data-enable ${p.enabled ? "checked" : ""} aria-label="${esc(p.name)} ein/aus"><span></span></label>
      </div>
      <p class="pl-desc">${esc(p.description)}</p>
      ${p.enabled ? err + missing + ext + page + acts + envOk : ""}
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
  const cond = o.show_if ? ` data-showif='${esc(JSON.stringify(o.show_if))}'` : "";
  const wrap = (h) => `<div class="pl-opt"${cond}>${h}</div>`;
  return wrap(pluginOptionInner(o, id));
}

function pluginOptionInner(o, id) {
  const lab = `<label for="${id}">${esc(o.label || o.key)}</label>`;
  if (o.type === "info") return `<span></span><div class="hint">${esc(o.label)}</div>`;
  if (o.type === "password") return lab + `<input id="${id}" type="password" data-ok="${esc(o.key)}" autocomplete="off" spellcheck="false">`;
  if (o.type === "textarea") return lab + `<textarea id="${id}" class="inp pl-ta" data-ok="${esc(o.key)}" spellcheck="false" rows="4">${esc(o.value)}</textarea>`;
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
      <div class="hint">Plugin: ${esc(f.plugin_name)}${f.background ? " · läuft im Hintergrund – du kannst währenddessen weiterarbeiten (Fortschritt unten in der Fußleiste)" : ""}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: f.run_label, value: true, primary: true }],
    onMount: (b) => {
      b.querySelectorAll("[data-plpick]").forEach((btn) => btn.addEventListener("click", async () => {
        const inp = $("#" + btn.dataset.plpick, b);
        const p = await call("pick_path", "", true, inp.value.trim());
        if (p) inp.value = p; else if (!S.settings.native) toast("Pfad bitte direkt ins Feld eintippen.");
      }));
      const sync = () => b.querySelectorAll("[data-showif]").forEach((el) => {
        const cond = JSON.parse(el.dataset.showif);
        el.hidden = !Object.entries(cond).every(([k, want]) => {
          const ctl = b.querySelector(`[data-ok="${k}"]`);
          if (!ctl) return true;
          return ctl.type === "checkbox" ? ctl.checked === !!want : ctl.value === String(want);
        });
      });
      b.addEventListener("change", sync);
      sync();
      const first = b.querySelector(".pl-opt:not([hidden]) input:not([type=checkbox]), .pl-opt:not([hidden]) textarea");
      if (first && !first.value) first.focus();
    },
    collect: (b) => Object.fromEntries([...b.querySelectorAll("[data-ok]")].map((el) => [el.dataset.ok, el.type === "checkbox" ? el.checked : el.value])),
  });
  if (!values) return;
  const started = await call("start_plugin_action", pid, aid, f.needs_selection ? idx : [], values);
  if (started.ok && started.background) { jobsQueued(started); return; }
  const res = await runTask(Promise.resolve(started), f.label.replace(/\s*…$/, ""));
  if (S.module === "plugins") pluginsShow();
  if (!res) return;
  if (res.proposals && res.proposals.length) { await pluginPreview(f, res); return; }
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

// ---------------------------------------------------------------------- Vorschläge bestätigen
async function pluginPreview(f, res) {
  const rows = res.proposals;
  const groups = [];
  // nach Datei (Pfad) gruppieren – gleich benannte Dateien aus verschiedenen Ordnern bleiben getrennt
  for (const r of rows) {
    const key = r.gkey || r.group;
    let g = groups.find((x) => x.key === key);
    if (!g) groups.push(g = { key, idx: groups.length, name: r.group, folder: r.folder || "", note: r.note, rows: [] });
    g.rows.push(r);
  }
  const dup = (g) => groups.some((x) => x !== g && x.name === g.name);
  const html = `<p style="margin:0">${esc(res.message || "")}</p>
    <div class="pl-prev-tools"><button class="ghost sm" data-pv="all">Alle wählen</button><button class="ghost sm" data-pv="none">Keine</button><button class="ghost sm" data-pv="default">Vorschlag</button>
      <span class="muted sm" id="pvCount"></span></div>
    <div class="fx-table pl-prev"><table><thead><tr><th style="width:28px"></th><th>Feld</th><th>Vorher</th><th>Nachher</th></tr></thead><tbody>
    ${groups.map((g) => `<tr class="pv-file"><td>${g.rows.some((r) => !r.same) ? `<input type="checkbox" data-pvg="${g.idx}" aria-label="${esc(g.name)} alle">` : ""}</td><td colspan="3"><b>${esc(g.name)}</b>${dup(g) && g.folder ? ` <span class="muted sm">(${esc(g.folder)})</span>` : ""} <span class="muted sm">${esc(g.note || "")}</span></td></tr>
      ${g.rows.map((r) => `<tr class="${r.same ? "pv-same" : r.note.includes("unsicher") ? "pv-unsure" : ""}"><td>${r.same ? '<span class="pv-eq" title="Wert ist bereits gleich">=</span>' : `<input type="checkbox" data-pvi="${r.id}" data-pvgroup="${g.idx}" data-default="${r.checked ? 1 : 0}" ${r.checked ? "checked" : ""}>`}</td>
        <td>${esc(r.label)}</td><td class="old">${esc(r.old) || "–"}</td><td class="new">${esc(r.new)}${r.hint ? `<div class="hint">${esc(r.hint)}</div>` : ""}</td></tr>`).join("")}`).join("")}
    </tbody></table></div>
    ${(res.log || []).length ? `<details class="sm"><summary class="muted">Protokoll (${res.log.length})</summary><pre class="pl-log">${esc(res.log.slice(-60).join("\n"))}</pre></details>` : ""}`;
  const ids = await modal({
    title: `${f.label.replace(/\s*…$/, "")} – Vorschau`, wide: true, html,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => {
      const boxes = () => [...b.querySelectorAll("[data-pvi]")];
      const upd = () => {
        const n = boxes().filter((c) => c.checked).length;
        $("#pvCount", b).textContent = `${n} von ${boxes().length} gewählt`;
        b.querySelectorAll("[data-pvg]").forEach((g) => {
          const mine = boxes().filter((c) => c.dataset.pvgroup === g.dataset.pvg);
          const on = mine.filter((c) => c.checked).length;
          g.checked = on === mine.length; g.indeterminate = on > 0 && on < mine.length;
        });
        const btn = $("#mBtns .primary"); if (btn) { btn.disabled = !n; btn.textContent = n ? `Übernehmen (${n})` : "Übernehmen"; }
      };
      b.addEventListener("change", (e) => {
        const g = e.target.closest("[data-pvg]");
        if (g) boxes().filter((c) => c.dataset.pvgroup === g.dataset.pvg).forEach((c) => (c.checked = g.checked));
        upd();
      });
      b.addEventListener("click", (e) => {
        const t = e.target.closest("[data-pv]"); if (!t) return;
        boxes().forEach((c) => { c.checked = t.dataset.pv === "all" ? true : t.dataset.pv === "none" ? false : c.dataset.default === "1"; });
        upd();
      });
      upd();
    },
    collect: (b) => [...b.querySelectorAll("[data-pvi]:checked")].map((c) => +c.dataset.pvi),
  });
  if (!ids) { status("Keine Änderungen übernommen.", "info"); return; }
  const r = await call("plugin_apply", res.proposals_token, ids);
  if (!r.ok) { info("Hinweis", r.error); return; }
  if (typeof taggerRefresh === "function") await taggerRefresh();
  status(r.message, "info");
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
    const pa = e.target.closest("[data-paction]");
    if (pa) { pluginRun(pa.closest("[data-pid]").dataset.pid, pa.dataset.paction); return; }
    const b = e.target.closest("[data-install]"); if (!b) return;
    pluginInstall(b.closest("[data-pid]").dataset.pid, b.dataset.install);
  });
})();
