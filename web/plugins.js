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

// Feste Funktionsknöpfe je Karte (von links): Verbindung testen, Schlüssel/Anmelden, Einstellungen, Weitere Funktionen.
// Was ein Plugin nicht hat, bleibt ausgegraut sichtbar – so sehen alle Karten gleich aus.
const PL_SLOT_TEST = ["test"], PL_SLOT_KEY = ["keys", "login"], PL_SLOT_SET = ["settings"];
const PL_AUTH_NOTE = {
  none: "Ohne Anmeldung – es wird nichts gespeichert.",
  key: "Eigener Schlüssel – verschlüsselt im Datenordner des Plugins gespeichert, nie exportiert.",
  token: "Eigener Token – verschlüsselt im Datenordner des Plugins gespeichert, nie exportiert.",
  oauth: "Anmeldung: gespeichert wird nur der Token (verschlüsselt), nie das Passwort.",
};

function plMore(p) {                                   // Funktionen für „Weitere Funktionen …“
  const fixed = [...PL_SLOT_TEST, ...PL_SLOT_KEY, ...PL_SLOT_SET];
  const acts = (p.actions || []).filter((a) => a.where === "page" && !fixed.includes(a.id))
    .map((a) => ({ kind: "action", id: a.id, label: a.label, desc: a.description }));
  if (p.service) acts.push({ kind: "svc", label: "Integration …", desc: "Endpunkte mit Umsetzungsstand, Testabfrage ohne Track und API-Tester (nur lesend)" });
  if (p.env && p.state === "ready" && p.install.length) p.install.forEach((v) => acts.push({ kind: "install", id: v.id, label: `Neu installieren: ${v.label.replace(/^Installieren\s*\(?|\)$/g, "") || v.label}`, desc: (v.hint || "") }));
  return acts;
}

function renderPlugins() {
  const box = $("#plList");
  if (!PL.list.length) { box.innerHTML = '<div class="empty">Keine Plugins gefunden.</div>'; return; }
  box.innerHTML = PL.list.map((p) => {
    const [stTxt, stCls] = p.enabled ? PL_STATE[p.state] : ["Ausgeschaltet", "st-same"];
    const on = p.enabled && p.state === "ready";
    const acts = p.actions || [];
    const find = (ids) => acts.find((a) => a.where === "page" && ids.includes(a.id));
    // fehlende Pakete: kurz mit einem Knopf – Varianten und Hinweise im Fenster „Installieren …“ (Karten bleiben gleich gross)
    const missing = p.state === "missing" ? `<div class="pl-box warn pl-miss">
        <div><b>${p.env ? "Noch nicht installiert:" : "Fehlende Python-Pakete:"}</b> ${p.missing.map((m) => esc(m.label)).join(", ")}</div>
        ${PL.frozen && !p.env ? '<div class="hint">In der gepackten App können keine Pakete nachinstalliert werden.</div>'
          : p.install.length ? `<div><button class="ghost sm" data-plinstall>Installieren …</button></div>` : ""}</div>` : "";
    const ext = p.external.length ? `<div class="pl-box warn"><b>Zusätzlich nötig:</b> ${p.external.map((e) => `${esc(e.label)}${e.hint ? ` <span class="hint">– ${esc(e.hint)}</span>` : ""}`).join("<br>")}</div>` : "";
    const err = p.state === "error" ? `<div class="pl-box err">${esc(p.error)}</div>` : "";
    // 3. Aktionen (erscheinen im Tagger)
    const tagActs = acts.filter((a) => a.where !== "page");
    const actsHtml = `<div class="pl-acts"><span class="muted sm">Aktionen:</span> ${tagActs.length ? tagActs.map((a) => `<span class="pl-act" title="${esc(a.description)}">${esc(a.label.replace(/\s*…$/, ""))}${a.where === "tagger" ? ' <span class="faint">· Tagger</span>' : ""}</span>`).join("") : `<span class="muted sm">${p.enabled ? "keine" : "– (ausgeschaltet)"}</span>`}</div>`;
    // 4. API-Zeile
    const api = p.service ? `<div class="pl-svc sm">${p.service.docs ? `<a href="#" class="pl-link" data-url="${esc(p.service.docs)}" title="${esc(p.service.docs)}">API: ${esc(p.service.name)} ↗</a>` : `<span>API: ${esc(p.service.name)}</span>`}
        <span class="muted">· ${esc(p.service.auth_text)} ·</span> <a href="#" class="pl-link" data-svcopen title="Endpunkte mit Umsetzungsstand${p.service.test_query ? ", Testabfrage ohne Track" : ""}${p.service.testable ? ", API-Tester" : ""}">${p.service.endpoints} Endpunkte</a></div>`
      : `<div class="pl-svc sm muted">API: keine – arbeitet lokal</div>`;
    // 5. Hinweise (Status, Speicherung von Schlüsseln, Umgebung)
    const notes = [];
    if (on && p.status_text) notes.push(`<span class="pl-stat">${esc(p.status_text)}</span>`);
    if (p.service && PL_AUTH_NOTE[p.service.auth]) notes.push(esc(PL_AUTH_NOTE[p.service.auth]));
    if (p.env && p.state === "ready") notes.push(`Umgebung: ${esc((p.env_variant || "installiert").replace(/^Installieren\s*\(?|\)$/g, ""))}`);
    const hints = `<div class="pl-hints sm">${notes.map((n) => `<div>${n}</div>`).join("")}${p.enabled ? err + missing + ext : ""}</div>`;
    // 6. Funktionsknöpfe
    const slot = (a, fallback, dis) => a && on
      ? `<button class="ghost sm" data-paction="${esc(a.id)}" title="${esc(a.description)}">${esc(a.label)}</button>`
      : `<button class="ghost sm" disabled title="${esc(dis)}">${esc(fallback)}</button>`;
    const key = find(PL_SLOT_KEY), more = plMore(p);
    const btns = `<div class="pl-btns">
        ${slot(find(PL_SLOT_TEST), "Verbindung testen", "Dieses Plugin hat keine Verbindung zum Testen")}
        ${slot(key, "Schlüssel …", "Kein Schlüssel und keine Anmeldung nötig")}
        ${slot(find(PL_SLOT_SET), "Einstellungen …", "Dieses Plugin hat keine eigenen Einstellungen")}
        <button class="ghost sm" data-plmore ${more.length && p.enabled ? "" : "disabled"} title="${more.length ? "Weitere Funktionen dieses Plugins" : "Keine weiteren Funktionen"}">Weitere Funktionen …</button></div>`;
    return `<section class="card pl-card${p.enabled ? "" : " off"}" data-pid="${esc(p.id)}">
      <div class="pl-head">
        <div class="pl-ico"><svg class="i" viewBox="0 0 24 24"><path d="M9 3h6v3a2 2 0 1 0 4 0V3h2v6h-3a2 2 0 1 0 0 4h3v8h-6v-3a2 2 0 1 0-4 0v3H3v-8h3a2 2 0 1 0 0-4H3V3h6Z"/></svg></div>
        <div class="pl-t"><h3 title="${esc(p.path)}"><span class="pl-name">${esc(p.name)}</span> <span class="muted sm">${esc(p.version)}</span>${p.builtin ? ' <span class="plg-tag">eingebaut</span>' : ' <span class="plg-tag own">eigenes</span>'}<span class="plg-tag cat cat-${esc(p.category || "other")}">${esc(p.category_label || "Sonstiges")}</span></h3>
          <div class="sm ${stCls}">● ${stTxt}</div></div>
        <label class="switch" title="${p.enabled ? "Ausschalten" : "Einschalten"}"><input type="checkbox" data-enable ${p.enabled ? "checked" : ""} aria-label="${esc(p.name)} ein/aus"><span></span></label>
      </div>
      <p class="pl-desc">${esc(p.description)}</p>
      ${actsHtml}
      ${api}
      ${hints}
      ${btns}
    </section>`;
  }).join("");
}

/** „Installieren …“: Varianten mit Hinweisen zur Auswahl (eine Variante → direkt) */
async function pluginInstallPick(pid) {
  const p = PL.list.find((x) => x.id === pid); if (!p) return;
  if (p.install.length === 1) { pluginInstall(pid, p.install[0].id); return; }
  let pick = null;
  await modal({
    title: `${p.name} – installieren`,
    html: `<div class="pl-more">${p.install.map((v, i) => `<div class="pl-more-row"><button class="ghost sm" data-more="${i}" title="pip install ${esc(v.packages.join(" "))}">${esc(v.label)}</button><span class="muted sm">${esc(v.hint || "")}</span></div>`).join("")}</div>
      ${p.notes ? `<div class="hint" style="margin-top:12px">${esc(p.notes)}</div>` : ""}`,
    buttons: [{ label: "Abbrechen", value: null }],
    onMount: (b) => b.addEventListener("click", (e) => {
      const m = e.target.closest("[data-more]"); if (!m) return;
      pick = p.install[+m.dataset.more];
      $("#mBtns button").click();
    }),
  });
  if (pick) pluginInstall(pid, pick.id);
}

/** „Weitere Funktionen …“: alle übrigen Funktionen eines Plugins in einem Fenster */
async function pluginMore(pid) {
  const p = PL.list.find((x) => x.id === pid); if (!p) return;
  const items = plMore(p);
  let pick = null;
  await modal({
    title: `${p.name} – weitere Funktionen`,
    html: `<div class="pl-more">${items.map((it, i) => `<div class="pl-more-row"><button class="ghost sm" data-more="${i}">${esc(it.label)}</button><span class="muted sm">${esc(it.desc || "")}</span></div>`).join("")}</div>
      <div class="hint pl-path" title="${esc(p.path)}">Ordner: ${esc(p.path)}</div>`,
    buttons: [{ label: "Schliessen", value: null }],
    onMount: (b) => b.addEventListener("click", (e) => {
      const m = e.target.closest("[data-more]"); if (!m) return;
      pick = items[+m.dataset.more];
      $("#mBtns button").click();
    }),
  });
  if (!pick) return;
  if (pick.kind === "action") pluginRun(pid, pick.id);
  else if (pick.kind === "svc") svcOpen(pid);
  else if (pick.kind === "install") pluginInstall(pid, pick.id);
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
  if (o.type === "info") {
    // Hinweis, optional mit Links [[Text, https://…], …] – öffnen im Standard-Browser
    const links = (o.links || []).filter((l) => Array.isArray(l) && /^https:\/\//.test(l[1] || ""))
      .map((l) => `<a href="#" class="pl-link" data-url="${esc(l[1])}" title="${esc(l[1])}">${esc(l[0])} ↗</a>`).join(" · ");
    return `<span>${o.title ? `<b>${esc(o.title)}</b>` : ""}</span><div class="hint pl-info">${esc(o.label)}${links ? `<div class="pl-links">${links}</div>` : ""}</div>`;
  }
  if (o.type === "password") return lab + `<input id="${id}" type="password" data-ok="${esc(o.key)}" autocomplete="off" spellcheck="false">`;
  if (o.type === "textarea") return lab + `<textarea id="${id}" class="inp pl-ta" data-ok="${esc(o.key)}" spellcheck="false" rows="4">${esc(o.value)}</textarea>`;
  if (o.type === "check") return `<span></span><label class="check"><input type="checkbox" id="${id}" data-ok="${esc(o.key)}" ${o.value ? "checked" : ""}> ${esc(o.label || o.key)}</label>`;
  if (o.type === "select") return lab + `<select id="${id}" class="inp" data-ok="${esc(o.key)}">${(o.choices || []).map((c) => { const [v, l] = Array.isArray(c) ? c : [c, c]; return `<option value="${esc(v)}" ${String(v) === String(o.value) ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select>`;
  if (o.type === "folders") return lab + `<div class="pl-folders"><textarea id="${id}" class="inp pl-ta" data-ok="${esc(o.key)}" spellcheck="false" rows="3" placeholder="Je Zeile ein Ordner">${esc(o.value)}</textarea><button class="ghost sm" data-plpick="${id}" data-add="1" title="Ordner auswählen und als neue Zeile anfügen">+ Ordner …</button></div>`;
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
      <div class="hint">Plugin: ${esc(f.plugin_name)}${f.background ? " · läuft im Hintergrund – du kannst währenddessen weiterarbeiten (Fortschritt unten in der Fussleiste)" : ""}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: f.run_label, value: true, primary: true }],
    onMount: (b) => {
      b.addEventListener("click", (e) => {
        const l = e.target.closest(".pl-link[data-url]");
        if (l) { e.preventDefault(); call("open_url", l.dataset.url); }
      });
      b.querySelectorAll("[data-plpick]").forEach((btn) => btn.addEventListener("click", async () => {
        const inp = $("#" + btn.dataset.plpick, b);
        const add = !!btn.dataset.add, lines = inp.value.split("\n").map((x) => x.trim()).filter(Boolean);
        const p = await call("pick_path", "", true, add ? (lines[lines.length - 1] || "") : inp.value.trim());
        if (p) inp.value = add ? [...lines.filter((x) => x.toLowerCase() !== p.toLowerCase()), p].join("\n") : p;
        else if (!S.settings.native) toast("Pfad bitte direkt ins Feld eintippen.");
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
    if (!g) groups.push(g = { key, idx: groups.length, name: r.group, folder: r.folder || "", note: r.note, rows: [], links: new Map() });
    if (r.link && !g.links.has(r.link)) g.links.set(r.link, r.link_label || "Treffer");
    g.rows.push(r);
  }
  const dup = (g) => groups.some((x) => x !== g && x.name === g.name);
  const html = `<p style="margin:0">${esc(res.message || "")}</p>
    <div class="pl-prev-tools"><button class="ghost sm" data-pv="all">Alle wählen</button><button class="ghost sm" data-pv="none">Keine</button><button class="ghost sm" data-pv="empty" title="Nur Felder wählen, die in der Datei noch fehlen bzw. leer sind (#142)">Nur fehlende</button><button class="ghost sm" data-pv="default" title="Vorauswahl des Plugins wiederherstellen (z. B. ohne abgewählte Optionen und unsichere Treffer)">Vorauswahl</button>
      <span class="muted sm" id="pvCount"></span></div>
    <div class="fx-table pl-prev"><table><thead><tr><th style="width:28px"></th><th>Feld</th><th>Vorher</th><th>Nachher</th></tr></thead><tbody>
    ${groups.map((g) => `<tr class="pv-file"><td>${g.rows.some((r) => !r.same) ? `<input type="checkbox" data-pvg="${g.idx}" aria-label="${esc(g.name)} alle">` : ""}</td><td colspan="3"><b>${esc(g.name)}</b>${dup(g) && g.folder ? ` <span class="muted sm">(${esc(g.folder)})</span>` : ""} <span class="muted sm">${esc(g.note || "")}</span>${g.links.size ? `<div class="pv-links sm">Treffer ansehen: ${[...g.links].map(([u, l]) => `<a href="#" class="pl-link" data-url="${esc(u)}" title="${esc(u)}">${esc(l)} ↗</a>`).join(" · ")}</div>` : ""}</td></tr>
      ${g.rows.map((r) => `<tr class="${r.same ? "pv-same" : r.note.includes("unsicher") ? "pv-unsure" : ""}"><td>${r.same ? '<span class="pv-eq" title="Wert ist bereits gleich">=</span>' : `<input type="checkbox" data-pvi="${r.id}" data-pvgroup="${g.idx}" data-default="${r.checked ? 1 : 0}" data-empty="${r.old ? 0 : 1}" ${r.checked ? "checked" : ""}>`}</td>
        <td>${esc(r.label)}${r.link ? ` <a href="#" class="pl-link" data-url="${esc(r.link)}" title="Datensatz auf ${esc(r.link_label || "der Plattform")} ansehen">↗</a>` : ""}</td><td class="old"><div class="pv-val">${esc(r.old) || "–"}</div></td><td class="new"><div class="pv-val">${esc(r.new)}</div>${r.hint ? `<div class="hint">${esc(r.hint)}</div>` : ""}</td></tr>`).join("")}`).join("")}
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
        const l = e.target.closest(".pl-link[data-url]");
        if (l) { e.preventDefault(); call("open_url", l.dataset.url); return; }   // #144
        const t = e.target.closest("[data-pv]"); if (!t) return;
        const pv = t.dataset.pv;
        boxes().forEach((c) => { c.checked = pv === "all" ? true : pv === "none" ? false : pv === "empty" ? c.dataset.empty === "1" : c.dataset.default === "1"; });
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
  $("#plServices").addEventListener("click", () => svcOverview());     // #204
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
    const lk = e.target.closest(".pl-link[data-url]");                 // #204: API-Dokumentation
    if (lk) { e.preventDefault(); call("open_url", lk.dataset.url); return; }
    const so = e.target.closest("[data-svcopen]");
    if (so) { e.preventDefault(); svcOpen(so.closest("[data-pid]").dataset.pid); return; }
    const pi = e.target.closest("[data-plinstall]");
    if (pi) { pluginInstallPick(pi.closest("[data-pid]").dataset.pid); return; }
    const mo = e.target.closest("[data-plmore]");
    if (mo) { pluginMore(mo.closest("[data-pid]").dataset.pid); return; }
    const pa = e.target.closest("[data-paction]");
    if (pa) { pluginRun(pa.closest("[data-pid]").dataset.pid, pa.dataset.paction); return; }
    const b = e.target.closest("[data-install]"); if (!b) return;
    pluginInstall(b.closest("[data-pid]").dataset.pid, b.dataset.install);
  });
})();
