/* MarKusSXCH TagStudio – Plugins: Verwaltungsseite und Aktionen (z. B. im Tagger).
   Formulare werden aus den Optionen des Plugins erzeugt – Plugins brauchen kein eigenes JavaScript. */
"use strict";

const PL = { list: [], userDir: "", logDir: "", frozen: false, cat: (() => { try { return localStorage.getItem("ts_pl_cat") || ""; } catch (e) { return ""; } })() };
const PL_CAT_ORDER = ["online", "shop", "cloud", "local_api", "import", "audio", "other"];
/** #352: alle Kategorien eines Plugins (Hauptkategorie zuerst) */
const plCats = (p) => (p.categories && p.categories.length ? p.categories : [p.category || "other"]).map((c) => (PL_CAT_ICON[c] ? c : "other"));

const PL_STATE = {
  ready: ["Bereit", "st-ok"],
  missing: ["Pakete fehlen", "st-missing"],
  error: ["Fehler", "st-err"],
};

async function pluginsShow(rescan = false) {
  const r = await call("plugins_list", rescan);
  PL.list = r.plugins; PL.userDir = r.user_dir; PL.builtinDir = r.builtin_dir || ""; PL.logDir = r.log_dir; PL.frozen = r.frozen;
  $("#plDir").textContent = "Eigene Plugins: " + r.user_dir;
  renderPlugins();
}

// Feste Funktionsknöpfe je Karte (von links): Verbindung testen, Schlüssel/Anmelden, Einstellungen, Weitere Funktionen.
// Was ein Plugin nicht hat, bleibt ausgegraut sichtbar – so sehen alle Karten gleich aus.
const PL_ICON = {
  test: '<svg class="i" viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
  key: '<svg class="i" viewBox="0 0 24 24"><circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3M15 8l2 2"/></svg>',
  login: '<svg class="i" viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3"/></svg>',
  set: '<svg class="i" viewBox="0 0 24 24"><path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/></svg>',
  more: '<svg class="i" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/></svg>',
};
// Symbol je Kategorie (gleicher Linienstil wie die übrigen Symbole)
const PL_CAT_ICON = {
  online: '<svg class="i" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
  shop: '<svg class="i" viewBox="0 0 24 24"><path d="M5 7h14l-1.5 10.5a2 2 0 0 1-2 1.5h-7a2 2 0 0 1-2-1.5z"/><path d="M9 7V5a3 3 0 0 1 6 0v2"/></svg>',
  cloud: '<svg class="i" viewBox="0 0 24 24"><path d="M7 18h10.5a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.5 9.2 4.5 4.5 0 0 0 7 18Z"/><path d="M12 11v5M9.5 13.5 12 11l2.5 2.5"/></svg>',
  local_api: '<svg class="i" viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01M11 7.5h6M11 16.5h6"/></svg>',
  import: '<svg class="i" viewBox="0 0 24 24"><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-6"/><path d="M12 3v12M7 10l5 5 5-5"/></svg>',
  audio: '<svg class="i" viewBox="0 0 24 24"><path d="M3 12h2M7 8v8M11 4v16M15 7v10M19 10v4M21 12h0"/></svg>',
  other: '<svg class="i" viewBox="0 0 24 24"><path d="M9 3h6v3a2 2 0 1 0 4 0V3h2v6h-3a2 2 0 1 0 0 4h3v8h-6v-3a2 2 0 1 0-4 0v3H3v-8h3a2 2 0 1 0 0-4H3V3h6Z"/></svg>',
};
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
  if (p.store) acts.push(p.builtin_version
    ? { kind: "revert", label: `Zurück auf eingebaute Version ${p.builtin_version}`, desc: `Entfernt die nachgeladene Version ${p.version} aus dem Plugin-Ordner.` }
    : { kind: "revert", label: "Nachgeladenes Plugin entfernen", desc: "Entfernt das Plugin aus dem Plugin-Ordner." });
  (p.links || []).forEach((l) => acts.push({ kind: "link", label: l.label, desc: l.desc || l.url, url: l.url }));   // #249
  if (p.path) acts.push({ kind: "dir", label: "Ordner dieses Plugins öffnen", desc: p.path });
  acts.push({ kind: "logdir", label: "Log-Ordner öffnen", desc: `${PL.logDir || "Logs"} – Protokolle dieses Plugins (${p.id}.log)` },   // #293
    { kind: "logview", label: "Protokoll live anzeigen …", desc: "Eigenes Fenster, das das Protokoll laufend nachführt – auch während ein Vorgang läuft" });
  if (p.env && p.state === "ready" && p.install.length) p.install.forEach((v) => acts.push({ kind: "install", id: v.id, label: `Neu installieren: ${v.label.replace(/^Installieren\s*\(?|\)$/g, "") || v.label}`, desc: (v.hint || "") }));
  return acts;
}

/** Filter oben: Alle + je Kategorie (mit Symbol und Anzahl); die Wahl wird gemerkt */
function renderPluginFilter() {
  const box = $("#plFilter"); if (!box) return;
  const n = {}, label = {};
  PL.list.forEach((p) => plCats(p).forEach((c) => { n[c] = (n[c] || 0) + 1; label[c] = PL_CAT_LABEL[c] || "Sonstiges"; }));
  if (PL.cat && !n[PL.cat]) PL.cat = "";
  const cats = PL_CAT_ORDER.filter((c) => n[c]);
  box.innerHTML = `<button class="chip${PL.cat ? "" : " on"}" data-plcat="">Alle <span class="n">${PL.list.length}</span></button>`
    + cats.map((c) => `<button class="chip cat-${c}${PL.cat === c ? " on" : ""}" data-plcat="${c}">${PL_CAT_ICON[c] || PL_CAT_ICON.other}${esc(label[c])} <span class="n">${n[c]}</span></button>`).join("");
}

function renderPlugins() {
  const box = $("#plList");
  renderPluginFilter();
  if (!PL.list.length) { box.innerHTML = '<div class="empty">Keine Plugins gefunden.</div>'; return; }
  const shown = PL.list.filter((p) => !PL.cat || plCats(p).includes(PL.cat));
  box.innerHTML = shown.map((p) => {
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
    const tagActs = acts.filter((a) => a.where !== "page" && a.where !== "hidden");   // #387: „hidden“ = nur intern
    // #248: einzeilig – Kurzname (sonst Name ohne „…“), zu lange Namen mit „…“ gekürzt (ganzer Name im Tooltip),
    // höchstens vier Chips + „+n“; „Im Tagger:“ statt „· Tagger“ an jedem Chip, wenn alle im Tagger sind
    const allTagger = tagActs.length && tagActs.every((a) => a.where === "tagger");
    const shown = tagActs.slice(0, 4), moreActs = tagActs.slice(4);
    const chip = (a) => `<span class="pl-act" data-tip-title="${esc(a.label.replace(/\s*…$/, ""))}" title="${esc(a.description || a.label.replace(/\s*…$/, ""))}">${esc(a.short || a.label.replace(/\s*…$/, ""))}${!allTagger && a.where === "tagger" ? ' <span class="faint">· Tagger</span>' : ""}</span>`;
    const actsHtml = `<div class="pl-acts"><span class="muted sm">${allTagger ? "Im Tagger:" : "Aktionen:"}</span> ${tagActs.length ? shown.map(chip).join("")
      + (moreActs.length ? `<span class="pl-act pl-more-acts" title="${esc(moreActs.map((a) => a.label.replace(/\s*…$/, "")).join("\n"))}">+${moreActs.length}</span>` : "")
      : `<span class="muted sm">${p.enabled ? "keine" : "– (ausgeschaltet)"}</span>`}</div>`;
    // 4. API-Zeile
    const api = p.service ? `<div class="pl-svc sm">${p.service.docs ? `<a href="#" class="pl-link" data-url="${esc(p.service.docs)}" title="${esc(p.service.docs)}">API: ${esc(p.service.name)} ↗</a>` : `<span>API: ${esc(p.service.name)}</span>`}
        <span class="muted">· <span>${esc(p.service.auth_text)}</span> ·</span> <a href="#" class="pl-link" data-svcopen title="Endpunkte mit Umsetzungsstand${p.service.test_query ? ", Testabfrage ohne Track" : ""}${p.service.testable ? ", API-Tester" : ""}">${p.service.endpoints} Endpunkte</a></div>`
      : `<div class="pl-svc sm muted">API: keine – arbeitet lokal</div>`;
    // 5. Hinweise (Status, Speicherung von Schlüsseln, Umgebung)
    const notes = [];
    if (on && p.status_text) notes.push(`<span class="pl-stat">${esc(p.status_text)}</span>`);
    if (p.service && PL_AUTH_NOTE[p.service.auth]) notes.push(esc(PL_AUTH_NOTE[p.service.auth]));
    if (p.env && p.state === "ready") notes.push(`Umgebung: ${esc((p.env_variant || "installiert").replace(/^Installieren\s*\(?|\)$/g, ""))}`);
    const hints = `<div class="pl-hints sm">${plStoreBox(p)}${notes.map((n) => `<div>${n}</div>`).join("")}${p.enabled ? err + missing + ext : ""}</div>`;
    // 6. Funktionsknöpfe
    // vier gleich breite Knöpfe mit Symbol und kurzer Beschriftung; der volle Name steht im Tooltip
    const slot = (a, label, icon, dis) => a && on
      ? `<button class="ghost sm" data-paction="${esc(a.id)}" title="${esc(a.label.replace(/\s*…$/, ""))}${a.description ? "\n" + esc(a.description) : ""}">${PL_ICON[icon]}<span>${label}</span></button>`
      : `<button class="ghost sm" disabled title="${esc(dis)}">${PL_ICON[icon]}<span>${label}</span></button>`;
    const key = find(PL_SLOT_KEY), more = plMore(p);
    const login = key && key.id === "login";
    const btns = `<div class="pl-btns">
        ${slot(find(PL_SLOT_TEST), "Testen", "test", "Dieses Plugin hat keine Verbindung zum Testen")}
        ${slot(key, login ? "Anmelden" : "Schlüssel", login ? "login" : "key", "Kein Schlüssel und keine Anmeldung nötig")}
        ${slot(find(PL_SLOT_SET), "Optionen", "set", "Dieses Plugin hat keine eigenen Einstellungen")}
        <button class="ghost sm" data-plmore ${more.length ? "" : "disabled"} title="${more.length ? "Weitere Funktionen dieses Plugins" : "Keine weiteren Funktionen"}">${PL_ICON.more}<span>Mehr …</span></button></div>`;
    return `<section class="card pl-card${p.enabled ? "" : " off"}" data-pid="${esc(p.id)}">
      <div class="pl-head">
        <div class="pl-ico cat-${esc(p.category || "other")}" aria-hidden="true">${PL_CAT_ICON[p.category] || PL_CAT_ICON.other}</div>
        <div class="pl-t"><h3 title="${esc(p.name)}\n${esc(p.path)}"><span class="pl-name">${esc(p.name)}</span><span class="muted sm">${esc(p.version)}</span>${p.builtin ? '<span class="plg-tag">eingebaut</span>' : p.store ? `<span class="plg-tag store" title="Aus Release ${esc(p.store.tag)} nachgeladen">nachgeladen</span>` : '<span class="plg-tag own">eigenes</span>'}</h3>
          <div class="pl-cat">${plCats(p).map((c) => `<span class="plg-tag cat cat-${esc(c)}">${esc(PL_CAT_LABEL[c] || "Sonstiges")}</span>`).join(" ")}</div></div>
        <div class="pl-sw"><div class="sm ${stCls} pl-st">● ${stTxt}</div>
          <label class="switch" title="${p.enabled ? "Ausschalten" : "Einschalten"}"><input type="checkbox" data-enable ${p.enabled ? "checked" : ""} aria-label="${esc(p.name)} ein/aus"><span></span></label></div>
      </div>
      <div class="pl-desc"><span>${esc(p.description)}</span><button class="pl-dmore" data-dmore hidden>mehr</button></div>
      ${actsHtml}
      ${api}
      ${hints}
      ${btns}
    </section>`;
  }).join("");
  plDescFit();
}

// ---------------------------------------------------------------------- #235: Plugins aus den Releases nachladen
/** Hinweis auf der Karte, wenn der Katalog eine neuere Version hat */
function plStoreBox(p) {
  const r = PL.store && PL.store.rows.find((x) => x.id === p.id);
  if (!r) return "";
  if (r.state === "update") return `<div class="pl-box upd"><span><b>Update verfügbar:</b> Version ${esc(r.version)}</span><button class="sm" data-plupd>Aktualisieren</button></div>`;
  if (r.state === "too_new") return `<div class="pl-box warn">Neuere Version ${esc(r.version)} braucht TagStudio ${esc(r.min_app)} oder neuer.</div>`;
  return "";
}

/** „Verfügbare Plugins …“ (#235/#236): Katalog des neuesten Releases im gewählten Kanal laden und Updates/neue Plugins zeigen */
async function pluginStoreCheck() {
  const res = await runTask(call("start_plugin_catalog"), "Plugin-Katalog laden");
  if (!res || res.cancelled) return;
  if (!res.release) { await info("Verfügbare Plugins", "Im gewählten Update-Kanal gibt es noch keinen Plugin-Katalog. Er erscheint mit dem nächsten Release."); return; }
  PL.store = res;
  renderPlugins();
  pluginStoreList();
}

const PL_CAT_LABEL = { online: "Online-API", shop: "Shop-API", cloud: "Cloud-API", local_api: "Lokale API", import: "Übernahme aus Tags", audio: "Audio-Verarbeitung", other: "Sonstiges" };
// #236: Gruppen der Liste „Verfügbare Plugins“
const PL_ST_GROUPS = [["update", "Updates"], ["new", "Neu – noch nicht installiert"], ["current", "Installiert"], ["too_new", "Nicht verträglich"], ["own", "Eigenes Plugin mit gleicher ID"]];

function plStoreRow(r) {
  const btn = r.state === "update" ? `<button class="sm" data-stinst="${esc(r.id)}">Aktualisieren</button>`
    : r.state === "new" ? `<button class="sm" data-stinst="${esc(r.id)}">Installieren</button>`
    : `<button class="ghost sm" disabled>${r.state === "too_new" ? "Nicht verträglich" : r.state === "own" ? "Eigenes Plugin" : "Aktuell"}</button>`;
  const ver = r.installed && r.state === "update" ? `${esc(r.installed)} → ${esc(r.version)}` : esc(r.version);
  const note = r.state === "too_new" ? `Braucht TagStudio ${esc(r.min_app)} oder neuer.`
    : r.state === "own" ? "Im Plugin-Ordner liegt ein eigenes Plugin mit gleicher ID – es wird nicht überschrieben."
    : r.requires && PL.frozen ? "Braucht zusätzliche Python-Pakete – in der installierten App nicht nachinstallierbar." : "";
  return `<div class="pl-more-row st-row" data-strow="${esc(r.id)}"><span class="st-btn">${btn}</span><div><b>${esc(r.name)}</b> <span class="muted sm">${ver}</span>
    ${plCats({ category: r.category, categories: [r.category, ...(r.categories || [])] }).filter((x, i, a) => a.indexOf(x) === i).map((c) => `<span class="plg-tag cat cat-${c}">${esc(PL_CAT_LABEL[c])}</span>`).join(" ")}
    <div class="muted sm">${esc(r.description)}</div>${note ? `<div class="hint">${note}</div>` : ""}</div></div>`;
}

/** Liste nach Gruppen (Updates, Neu, Installiert, …), optional nach Kategorie gefiltert */
function plStoreListHtml(rows, cat) {
  const shown = rows.filter((r) => !cat || plCats({ categories: [r.category, ...(r.categories || [])] }).includes(cat));
  if (!shown.length) return '<div class="empty">Keine Plugins in dieser Kategorie.</div>';
  return PL_ST_GROUPS.map(([g, label]) => {
    const rs = shown.filter((r) => r.state === g).sort((a, b) => a.name.localeCompare(b.name));
    return rs.length ? `<div class="st-group"><h4>${esc(label)} <span class="muted sm">${rs.length}</span></h4>${rs.map(plStoreRow).join("")}</div>` : "";
  }).join("");
}

/** #236: alle Plugins des Katalogs – Updates und neue zuerst, dann installierte und nicht verträgliche */
async function pluginStoreList() {
  const st = PL.store; if (!st) return;
  const n = (s) => st.rows.filter((r) => r.state === s).length;
  const cats = PL_CAT_ORDER.filter((c) => st.rows.some((r) => plCats({ categories: [r.category, ...(r.categories || [])] }).includes(c)));
  let pick = null, cat = "";
  const chips = () => `<button class="chip${cat ? "" : " on"}" data-stcat="">Alle <span class="n">${st.rows.length}</span></button>`
    + cats.map((c) => `<button class="chip cat-${c}${cat === c ? " on" : ""}" data-stcat="${c}">${PL_CAT_ICON[c]}${esc(PL_CAT_LABEL[c])}</button>`).join("");
  await modal({
    title: "Verfügbare Plugins", wide: true,
    html: `<div class="muted sm">Katalog aus Release ${esc(st.release.version)}${st.release.beta ? " (Beta)" : ""} · ${st.rows.length} Plugins · ${n("update")} Update(s) · ${n("new")} neu</div>
      <div class="pl-filter st-filter" role="toolbar" aria-label="Plugins nach Art filtern">${chips()}</div>
      <div class="pl-more st-list">${plStoreListHtml(st.rows, cat)}</div>
      <div class="hint" style="margin-top:12px">Plugins sind Python-Code. TagStudio lädt sie nur aus den offiziellen Releases und prüft die Prüfsumme. Nachgeladene Plugins liegen im Ordner „Eigene Plugins“ und ersetzen die eingebaute Version; unter „Mehr …“ geht es zurück.</div>`,
    buttons: [{ label: "Schliessen", value: null }],
    onMount: (b) => b.addEventListener("click", (e) => {
      const ch = e.target.closest("[data-stcat]");
      if (ch) { cat = ch.dataset.stcat; $(".st-filter", b).innerHTML = chips(); $(".st-list", b).innerHTML = plStoreListHtml(st.rows, cat); return; }
      const m = e.target.closest("[data-stinst]"); if (!m) return;
      pick = m.dataset.stinst;
      $("#mBtns button").click();
    }),
  });
  if (pick) pluginStoreInstall(pick);
}

async function pluginStoreInstall(pid) {
  const r = PL.store && PL.store.rows.find((x) => x.id === pid); if (!r) return;
  const res = await runTask(call("start_plugin_store_install", pid), `${r.name}: Plugin laden`);
  if (!res || res.cancelled) return;
  r.state = "current"; r.installed = r.version;
  PL.actionsCache = null;
  await pluginsShow(true);
  if (typeof renderTgEditor === "function") renderTgEditor();
  const p = PL.list.find((x) => x.id === pid);
  toast(p && p.state !== "ready" ? `${r.name} ${r.version} installiert – noch nicht bereit, siehe Karte.` : `${r.name} ${r.version} installiert.`);
}

async function pluginStoreRevert(pid) {
  const p = PL.list.find((x) => x.id === pid); if (!p) return;
  const ok = await dialog({ title: p.builtin_version ? "Zurück auf eingebaute Version?" : "Plugin entfernen?",
    text: p.builtin_version
      ? `Die nachgeladene Version ${p.version} von „${p.name}“ wird aus dem Plugin-Ordner gelöscht. Danach gilt wieder die eingebaute Version ${p.builtin_version}.`
      : `„${p.name}“ ${p.version} wird aus dem Plugin-Ordner gelöscht. Einstellungen und Anmeldungen des Plugins bleiben erhalten.`,
    buttons: [{ label: "Abbrechen", value: false }, { label: p.builtin_version ? "Zurücksetzen" : "Entfernen", value: true, primary: true }] });
  if (!ok) return;
  const r = await call("plugin_store_revert", pid);
  if (!r.ok) { info("Hinweis", r.error); return; }
  PL.list = r.plugins; PL.actionsCache = null;
  if (PL.store) PL.store = null;                       // Vergleich ist veraltet → bei Bedarf neu suchen
  renderPlugins();
  if (typeof renderTgEditor === "function") renderTgEditor();
  toast(p.builtin_version ? `${p.name}: eingebaute Version ${p.builtin_version} aktiv.` : `${p.name} entfernt.`);
}

/** Beschreibung mit fester Höhe: „mehr“ nur, wenn der Text nicht hineinpasst; aufgeklappt liegt er über der Karte */
function plDescFit() {
  $$("#plList .pl-desc").forEach((d) => {
    const t = d.querySelector("span"), b = d.querySelector("[data-dmore]");
    d.classList.remove("open");
    b.hidden = t.scrollHeight <= d.clientHeight + 1;
    b.textContent = "mehr";
  });
}

function plDescClose(d) {
  const b = d.querySelector("[data-dmore]");
  d.classList.remove("open"); d.appendChild(b); b.textContent = "mehr";
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
`,
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
  else if (pick.kind === "revert") pluginStoreRevert(pid);
  else if (pick.kind === "link") call("open_url", pick.url);
  else if (pick.kind === "dir" && !(await call("open_folder", p.path))) toast("Ordner konnte nicht geöffnet werden.");
  else if (pick.kind === "logdir" && !(await call("plugin_log_folder", pid))) toast("Ordner konnte nicht geöffnet werden.");
  else if (pick.kind === "logview") pluginLogWindow(pid);
}

/** #293: Live-Protokoll abgedockt – im App-Fenster ein eigenes Fenster, im Browser ein Popup */
async function pluginLogWindow(pid) {
  let r;
  try { r = await call("log_window_open", pid); } catch (e) { r = { ok: false, error: String(e.message || e) }; }
  if (r.ok) return;
  if (!r.browser) { toast(r.error || "Fenster konnte nicht geöffnet werden."); return; }
  const w = window.open(`log-window.html#pid=${encodeURIComponent(pid)}&token=${encodeURIComponent(TOKEN)}`, `tsLog_${pid}`, "width=900,height=560,resizable=yes");
  if (!w) toast("Das Protokoll-Fenster wurde vom Browser blockiert – bitte Popups für diese Seite erlauben.");
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
  if (o.type === "file") return lab + `<div class="pl-folder"><input id="${id}" data-ok="${esc(o.key)}" value="${esc(o.value)}" spellcheck="false" placeholder="Datei …"><button class="ghost sm" data-plpick="${id}" data-file="${esc(o.kind || "mp3")}">Wählen …</button></div>`;   // #387
  if (o.type === "folder") return lab + `<div class="pl-folder"><input id="${id}" data-ok="${esc(o.key)}" value="${esc(o.value)}" spellcheck="false" placeholder="Ordner …"><button class="ghost sm" data-plpick="${id}">Wählen …</button></div>`;
  return lab + `<input id="${id}" data-ok="${esc(o.key)}" ${o.type === "number" ? 'type="number" step="any"' : ""} value="${esc(o.value)}" spellcheck="false">`;
}

async function pluginRun(pid, aid) {
  const idx = typeof tgSelected === "function" ? tgSelected() : [];
  const f = await call("plugin_form", pid, aid);
  if (f.needs_selection && !idx.length) { toast("Bitte zuerst Dateien markieren."); return; }
  const values = f.direct && !f.options.length ? {} : await modal({
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
        const p = await call("pick_path", "", !btn.dataset.file, add ? (lines[lines.length - 1] || "") : inp.value.trim(), btn.dataset.file || "mp3");
        if (p) inp.value = add ? [...lines.filter((x) => x.toLowerCase() !== p.toLowerCase()), p].join("\n") : p;
        else if (!S.settings.native) toast("Pfad bitte direkt ins Feld eintippen.");
      }));
      const sync = () => b.querySelectorAll("[data-showif]").forEach((el) => {
        const cond = JSON.parse(el.dataset.showif);
        el.hidden = !Object.entries(cond).every(([k, want]) => {
          const ctl = b.querySelector(`[data-ok="${k}"]`);
          if (!ctl) return true;
          if (Array.isArray(want)) return want.map(String).includes(ctl.value);       // mehrere erlaubte Werte
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
  if (res.open && res.open.files && res.open.files.length) { await pluginOpenFiles(res.open, res); return; }   // #238
  if (res.mix_open && typeof mixOpen === "function") { status(res.message || "", "info"); await mixOpen(res.mix_open); return; }   // #387
  if (res.mix_list && typeof mixListDialog === "function") { await mixListDialog(); return; }
  if (res.changed && typeof taggerRefresh === "function") await taggerRefresh();
  if (res.cancelled) { status("Abgebrochen.", "warn"); if (!res.log.length) return; }
  const log = (res.log || []).slice(-40).join("\n");
  const outs = res.outputs || [];
  const btns = [{ label: "OK", value: null, primary: !outs.length }];
  if (outs.length) btns.push({ label: IS_MAC ? "Im Finder zeigen" : "Im Explorer zeigen", value: "reveal", primary: true });
  const what = await modal({
    title: res.cancelled ? "Abgebrochen" : f.label.replace(/\s*…$/, ""),
    html: `<p style="margin:0">${esc(res.message || "")}</p>${pluginResultTable(res.table)}${log ? `<pre class="pl-log">${esc(log)}</pre>` : ""}`,
    wide: !!(res.table && res.table.rows && res.table.rows.length),
    buttons: btns,
  });
  if (what === "reveal") call("reveal", outs[0]);
  if (res.message) status(res.message, "info");
}

/** #255: Tabelle im Ergebnis eines Plugins – nur Anzeige (nicht im Protokoll, nicht gespeichert) */
function pluginResultTable(t) {
  if (!t || !Array.isArray(t.cols) || !Array.isArray(t.rows) || !t.rows.length) return "";
  return `<div class="fx-table pl-res-table"><table><thead><tr>${t.cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>
    ${t.rows.map((r) => `<tr>${r.map((v, i) => `<td${i === 0 ? ' translate="no"' : ""}>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

/** #238: Ergebnis „öffnen“ eines Plugins – Dateien in den Tagger laden, auf Wunsch ins DJ-Set (Reihenfolge bleibt) */
async function pluginOpenFiles(o, res) {
  if (typeof confirmDiscard === "function" && !(await confirmDiscard())) return;
  const r = await runTask(call("start_tag_load_files", o.files, o.label || ""), "Dateien einlesen");
  if (!r || r.cancelled) return;
  if (o.target === "djset" || o.target === "djadd") {
    const st = await call("dj_add_paths", o.files, o.target === "djset", o.label || "");
    setModule("djset");
    if (typeof djApply === "function") djApply(st);
    if (typeof tgAfterLoad === "function") await tgAfterLoad(r, "", false);
  } else {
    setModule("tagger");
    if (typeof tgAfterLoad === "function") await tgAfterLoad(r, "", false);
  }
  status(res.message || "", "info");
  if ((res.log || []).length) toast(`${res.log.length} Hinweis(e) – siehe Plugin-Protokoll.`);
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
  if ((r.errors || []).length) info("Hinweis", `${r.message}\n\n${r.errors.slice(0, 20).join("\n")}`);   // #239: z. B. Lexicon
}

// ---------------------------------------------------------------------- Ereignisse
(function bindPlugins() {
  $("#plFilter").addEventListener("click", (e) => {
    const b = e.target.closest("[data-plcat]"); if (!b) return;
    PL.cat = b.dataset.plcat;
    try { localStorage.setItem("ts_pl_cat", PL.cat); } catch (err) { /* egal */ }
    renderPlugins();
  });
  $("#plServices").addEventListener("click", () => svcOverview());     // #204
  $("#plStore").addEventListener("click", () => pluginStoreCheck());   // #235
  $("#plRescan").addEventListener("click", async () => { PL.actionsCache = null; await pluginsShow(true); toast("Plugins neu eingelesen."); if (typeof renderTgEditor === "function") renderTgEditor(); });
  $("#plLogs").addEventListener("click", async () => { if (!(await call("open_folder", PL.logDir))) toast("Ordner konnte nicht geöffnet werden."); });
  // „Plugin-Ordner öffnen“: eigene Plugins (Benutzerordner) oder eingebaute (Programmordner) – Wunsch User 17.10.2026
  const openDir = async (d) => { if (!(await call("open_folder", d))) toast("Ordner konnte nicht geöffnet werden."); };
  $("#plOpen").addEventListener("click", (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    showMenu(r.left, r.bottom + 4, [
      { label: `Eigene Plugins – ${PL.userDir}`, run: () => openDir(PL.userDir) },
      ...(PL.builtinDir ? [{ label: `Eingebaute Plugins (Programmordner) – ${PL.builtinDir}`, run: () => openDir(PL.builtinDir) }] : []),
    ]);
  });
  $("#plList").addEventListener("change", async (e) => {
    const cb = e.target.closest("[data-enable]"); if (!cb) return;
    const pid = cb.closest("[data-pid]").dataset.pid;
    const r = await call("plugin_enable", pid, cb.checked);
    PL.list = r.plugins; PL.actionsCache = null; renderPlugins();
    if (typeof renderTgEditor === "function") renderTgEditor();
    if (r.folders_note) toast(r.folders_note);                                  // #314: Unterordner je Quelle
  });
  $("#plList").addEventListener("click", (e) => {
    const lk = e.target.closest(".pl-link[data-url]");                 // #204: API-Dokumentation
    if (lk) { e.preventDefault(); call("open_url", lk.dataset.url); return; }
    const so = e.target.closest("[data-svcopen]");
    if (so) { e.preventDefault(); svcOpen(so.closest("[data-pid]").dataset.pid); return; }
    const up = e.target.closest("[data-plupd]");                       // #235
    if (up) { pluginStoreInstall(up.closest("[data-pid]").dataset.pid); return; }
    const pi = e.target.closest("[data-plinstall]");
    if (pi) { pluginInstallPick(pi.closest("[data-pid]").dataset.pid); return; }
    if (!e.target.closest(".pl-desc.open")) $$("#plList .pl-desc.open").forEach(plDescClose);   // Klick daneben schliesst
    const dm = e.target.closest("[data-dmore]");
    if (dm) {
      const d = dm.closest(".pl-desc"), open = !d.classList.contains("open");
      $$("#plList .pl-desc.open").forEach(plDescClose);
      if (open) { d.classList.add("open"); d.querySelector("span").appendChild(dm); dm.textContent = "weniger"; }
      return;
    }
    const mo = e.target.closest("[data-plmore]");
    if (mo) { pluginMore(mo.closest("[data-pid]").dataset.pid); return; }
    const pa = e.target.closest("[data-paction]");
    if (pa) { pluginRun(pa.closest("[data-pid]").dataset.pid, pa.dataset.paction); return; }
    const b = e.target.closest("[data-install]"); if (!b) return;
    pluginInstall(b.closest("[data-pid]").dataset.pid, b.dataset.install);
  });
})();

/** #387: einmal nach dem Start – Plugins führen z. B. ihren Index im Hintergrund nach (Ereignis „app_started“) */
async function pluginsStartup() {
  try { await call("plugins_startup"); } catch (e) { /* egal */ }
}
