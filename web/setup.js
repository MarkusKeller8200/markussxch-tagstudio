/* MarKusSXCH TagStudio – Einrichtung (#167–#170): Einrichtungsassistent, empfohlene/ausgeblendete Menüpunkte,
   „Erste Schritte“-Hinweise je Seite und „Neu in dieser Version“. Logik in session_setup.py. */
"use strict";

const SETUP = { st: null };
const NAV_NAMES = { purchases: "Käufe", prep: "Vorbereiten", tagger: "Tagger", fixer: "Tag-Fixer", compare: "Vergleich", djset: "DJ-Set", playlists: "Playlists",
  snapshots: "Snapshots", backups: "Sicherungen", plugins: "Plugins", settings: "Einstellungen", help: "Hilfe" };

const WIZ_GOALS = [
  ["tags", "Tags bearbeiten und vervollständigen", "Tagger, Tag-Fixer und Tag-Rezepte – Titel, Künstler, Cover, Tonart, BPM …", ["tagger", "fixer"]],
  ["prep", "Neue Tracks vorbereiten", "Vom Download über deine Programme bis in die Bibliothek – mit Schutz bestehender Tags", ["prep"]],
  ["compare", "Ordner oder Sicherungen vergleichen", "Zwei Stände nebeneinander, Unterschiede übernehmen", ["compare"]],
  ["djset", "DJ-Sets planen", "Reihenfolge nach Tonart, BPM und Energie, Export für Rekordbox & Co.", ["djset"]],
  ["track", "Änderungen nachverfolgen", "Snapshots der Bibliothek und Sicherungen vor jedem Speichern", ["snapshots", "backups"]],
];
// Programme → Plugin (an/aus) und Schritt im Vorbereiten-Workflow (Stichwort in der Bezeichnung)
const WIZ_PROGRAMS = [
  ["mik", "Mixed In Key", "mik", "mixed in key"], ["beatunes", "beaTunes", "beatunes", "beatunes"],
  ["lexicon", "Lexicon", "lexicon", "lexicon"], ["platinum", "Platinum Notes", "", "platinum"],
  ["picard", "MusicBrainz Picard", "", "picard"], ["audioranger", "AudioRanger", "", "audioranger"],
  ["onetagger", "OneTagger", "", "onetagger"], ["engine", "Engine DJ", "", "engine dj"], ["mixo", "Mixo", "", "mixo"],
  ["serato", "Serato", "", ""], ["rekordbox", "Rekordbox", "", ""],
];
const WIZ_ONLINE = [
  ["online", "Online-Metadaten", "MusicBrainz, Deezer, iTunes, Discogs … ergänzen fehlende Angaben (manche Dienste brauchen einen eigenen Schlüssel)"],
  ["beatport", "Beatport", "Metadaten, Käufe abgleichen und herunterladen – Anmeldung später unter Plugins"],
  ["loudness", "Lautheit messen", "LUFS, True Peak, Clipping (braucht FFmpeg, z. B. über das Stems-Plugin)"],
  ["stems", "Stems", "Gesang, Drums, Bass … trennen – grosse Installation (Umgebung und Modelle), unter Plugins installieren"],
];
const FIRST_STEPS = {
  prep: ["Unter „Workflow bearbeiten“ Eingangsordner, Arbeitsordner und Bibliothek wählen.", "Schritte der Reihe nach ausführen – jede Stufe arbeitet auf einer Kopie.", "Reiter „Entdecken“: Künstlern und Labels folgen, neue Titel vorhören."],
  tagger: ["Oben einen Ordner wählen und „Laden“ – alle MP3 erscheinen in der Liste.", "Titel markieren und rechts bearbeiten; Strg+S speichert (vorher wird gesichert).", "Leertaste spielt ab, 0–5 bewertet; alle Tasten unter Hilfe › Tastatur."],
  fixer: ["Bereich wählen: markierte Titel oder ganzer Ordner.", "Mehrfachwerte, Gross-/Kleinschreibung oder Suchen & Ersetzen einstellen.", "Vorschau prüfen, dann übernehmen – Rückgängig jederzeit."],
  compare: ["Links und rechts je einen Ordner (oder Snapshot/Sicherung) wählen.", "Paare links auswählen; Unterschiede sind markiert.", "Alt+→ / Alt+← kopiert markierte Felder auf die andere Seite."],
  djset: ["Titel im Tagger markieren und „Zum DJ-Set“ hinzufügen.", "„Optimieren“ ordnet nach Tonart, BPM und Energie; G fixiert einen Titel.", "Als M3U8, Rekordbox-XML oder CSV exportieren."],
  playlists: ["Im Tagger Titel markieren, Rechtsklick „Zur Playlist hinzufügen …“ (Strg+Shift+P: zur zuletzt benutzten).", "Hier ordnen, umbenennen und in Ordner ziehen; Doppelklick spielt ab.", "Jede Playlist liegt auch als M3U8 im Playlist-Ordner – Archivieren statt Löschen."],
  snapshots: ["Bibliothek hinzufügen – TagStudio merkt sich den Tag-Stand aller Titel.", "Snapshots täglich oder von Hand; das Journal zeigt jede Änderung.", "Einzelne Felder oder ganze Titel lassen sich zurücksetzen."],
  backups: ["Vor jedem Speichern sichert TagStudio die Tags der betroffenen Titel.", "Hier ansehen, vergleichen und wiederherstellen.", "Speicherort unter Einstellungen › Sicherungen."],
  plugins: ["Plugins erweitern TagStudio (Online-Metadaten, Beatport, Stems …).", "Mit dem Schalter ein-/ausschalten; manche brauchen eine Installation.", "Aktionen erscheinen danach im Tagger unter „Plugins“."],
  settings: ["Alles an einem Ort, Sprungmarken oben.", "Export/Import der Einstellungen, auch zwischen Profilen.", "Hier lässt sich der Einrichtungsassistent erneut starten."],
  help: ["Tag-Übersicht: Bedeutung jedes Tags, mit Zähler aus deiner Bibliothek.", "Handbuch und alle Tastenkombinationen.", "Einrichtungsassistent und „Erste Schritte“ jederzeit neu starten."],
};

async function setupInit(st) {
  SETUP.st = await call("setup_state");
  setupNav();
  if (st.start_paths && st.start_paths.length) return false;
  if (SETUP.st.first) return wizardRun();
  setTimeout(whatsNew, 2500);
  setTimeout(() => { if (typeof foldersStartup === "function") foldersStartup(); }, 3500);   // #310
  return false;
}

/** Seitenleiste: empfohlene Menüpunkte markieren, ausgeblendete verstecken (#169) */
function setupNav() {
  const s = SETUP.st; if (!s) return;
  // #316: Reihenfolge – verschiebbare Menüpunkte vor „Einstellungen“ einreihen
  const anchor = $('.nav[data-module="settings"]');
  if (anchor && s.order) s.order.forEach((m) => { const b = $(`.nav[data-module="${m}"]`); if (b) anchor.parentNode.insertBefore(b, anchor); });
  $$(".nav[data-module]").forEach((b) => {
    const m = b.dataset.module;
    b.classList.toggle("rec", s.recommended.length > 0 && s.recommended.includes(m));
    if (s.modules.includes(m)) b.hidden = s.hidden.includes(m);
    let dot = b.querySelector(".rec-dot");
    if (b.classList.contains("rec") && !dot) { dot = document.createElement("span"); dot.className = "rec-dot nt"; dot.title = "Für dich empfohlen (Einrichtungsassistent)"; dot.textContent = "★"; b.appendChild(dot); }
    if (!b.classList.contains("rec") && dot) dot.remove();
  });
}

// ---------------------------------------------------------------------- Assistent (#167, #168)
async function wizardRun() {
  const pg = await call("settings_page").catch(() => ({}));
  const prep = await call("prep_overview", null).catch(() => null);
  const plist = await call("plugins_list").catch(() => ({ plugins: [] }));
  const pl = Object.fromEntries((plist.plugins || []).map((p) => [p.id, p]));
  const fo = await call("folders_overview").catch(() => ({ drives: [], structure: [], suggest: "", base: "" }));
  const W = {
    base: fo.base || fo.suggest || "", mode: "struct", names: Object.fromEntries((fo.structure || []).map((x) => [x.id, x.name])),
    step: 0, goals: new Set(["tags"]), lib: (S.settings.defaults && S.settings.defaults.tagger) || "", inbox: prep ? prep.workflow.inbox : "",
    backup: true, backupDir: "", snap: true, programs: new Set(), adapt: true,
    online: new Set(Object.keys(pl).filter((k) => pl[k].enabled && WIZ_ONLINE.some(([id]) => id === k))),
    theme: S.opts.theme || "dark", notation: pg.key_notation || "", notations: pg.notations || [], layout: (pg.player && pg.player.layout) || "bottom", firstSteps: true,
  };
  const steps = ["Willkommen", "Speicherort", "Deine Musik", "Sicherheit", "Deine Programme", "Online-Dienste", "Darstellung", "Fertig"];
  const gb = (n) => (n >= 1e12 ? (n / 1e12).toFixed(1) + " TB" : Math.round(n / 1e9) + " GB");
  const baseFor = (root) => (/^[A-Za-z]:\\$/.test(root) && !/^C:/i.test(root) ? root + "TagStudio" : /^C:/i.test(root) ? fo.home_base : root.replace(/[\\/]$/, "") + (root.includes("\\") ? "\\" : "/") + "TagStudio");
  const ov = $("#wizard");
  const pathIn = (id, v, ph) => `<div class="pl-folder"><input id="${id}" value="${esc(v)}" placeholder="${esc(ph)}" spellcheck="false"><button class="ghost sm" data-wpick="${id}">Wählen …</button></div>`;
  const chk = (name, val, on, title, sub = "") => `<label class="wiz-opt"><input type="checkbox" data-w="${name}" value="${esc(val)}" ${on ? "checked" : ""}><span><b>${esc(title)}</b>${sub ? `<span class="muted sm">${esc(sub)}</span>` : ""}</span></label>`;
  const read = () => {
    const v = (id) => ($("#" + id, ov) ? $("#" + id, ov).value.trim() : null);
    const set = (name) => new Set([...ov.querySelectorAll(`[data-w="${name}"]:checked`)].map((x) => x.value));
    if (W.step === 0) W.goals = set("goal");
    if (W.step === 1) { W.base = v("wBase") ?? W.base; W.mode = (ov.querySelector('input[name="wMode"]:checked') || {}).value || W.mode; }
    if (W.step === 2 && W.mode === "struct") ov.querySelectorAll("[data-wname]").forEach((x) => { W.names[x.dataset.wname] = x.value.trim() || W.names[x.dataset.wname]; });
    if (W.step === 2 && W.mode !== "struct") { W.lib = v("wLib") ?? W.lib; W.inbox = v("wInbox") ?? W.inbox; }
    if (W.step === 3) { W.backup = !!$("#wBackup", ov).checked; W.backupDir = v("wBackupDir") ?? ""; W.snap = !!($("#wSnap", ov) || {}).checked; }
    if (W.step === 4) { W.programs = set("prog"); W.adapt = !!($("#wAdapt", ov) || {}).checked; }
    if (W.step === 5) W.online = set("online");
    if (W.step === 6) { W.theme = ($(".wiz-theme .on", ov) || {}).dataset?.v || W.theme; W.notation = v("wNot") || W.notation; W.layout = v("wLayout") || W.layout; }
    if (W.step === 7) W.firstSteps = !!$("#wFirst", ov).checked;
  };
  const body = () => {
    switch (W.step) {
      case 0: return `<h2>Willkommen bei TagStudio</h2>${typeof i18nPickerHtml === "function" ? `<div class="wiz-lang">${i18nDropHtml("wiz")}</div>` : ""}<p class="muted">In ein paar Schritten richtest du TagStudio für deine Arbeit ein. Alles lässt sich später unter Einstellungen ändern – jeder Schritt kann übersprungen werden.</p>
        <h4>Was willst du vor allem tun?</h4><div class="wiz-opts">${WIZ_GOALS.map(([id, t, sub]) => chk("goal", id, W.goals.has(id), t, sub)).join("")}</div>
        <p class="muted sm">Die passenden Menüpunkte werden als <span class="rec-dot">★</span> empfohlen markiert – die anderen bleiben erreichbar.</p>`;
      case 1: return `<h2>Speicherort</h2><p class="muted">Auf welchem Laufwerk soll deine Musik liegen? Der <b>Basisordner</b> wird gemerkt: Jede Ordnerauswahl in TagStudio beginnt dort, damit du dich nicht jedes Mal durchklicken musst.</p>
        <div class="wiz-drives">${(fo.drives || []).map((d) => `<button class="wiz-drive ${W.base.toLowerCase().startsWith(d.root.toLowerCase()) ? "on" : ""}" data-wdrive="${esc(d.root)}"><b>${esc(d.root)}</b><span>${esc(d.label || d.kind || "")}</span><span class="muted sm">${gb(d.free)} frei von ${gb(d.total)}</span></button>`).join("")}</div>
        <div class="frm"><label for="wBase">Basisordner</label>${pathIn("wBase", W.base, fo.suggest || "")}</div>
        <h4>Wie möchtest du starten?</h4><div class="wiz-opts">
          <label class="wiz-opt"><input type="radio" name="wMode" value="struct" ${W.mode === "struct" ? "checked" : ""}><span><b>Empfohlene Ordnerstruktur anlegen</b><span class="muted sm">Neue Musik, Bibliothek, Archiv, Downloads, Arbeitsordner und Sicherung als Unterordner – TagStudio stellt alles passend ein. Vorhandene Ordner bleiben, es wird nichts verschoben.</span></span></label>
          <label class="wiz-opt"><input type="radio" name="wMode" value="own" ${W.mode !== "struct" ? "checked" : ""}><span><b>Bestehende Ordner wählen</b><span class="muted sm">Deine Musik liegt schon irgendwo – du wählst Bibliothek und Eingangsordner selbst (Auswahl beginnt im Basisordner).</span></span></label></div>`;
      case 2: return W.mode === "struct"
        ? `<h2>Ordnerstruktur</h2><p class="muted">Unter <b>${esc(W.base)}</b> werden diese Ordner angelegt (Namen änderbar):</p>
          <div class="wiz-struct">${(fo.structure || []).map((x) => `<input data-wname="${esc(x.id)}" value="${esc(W.names[x.id] || x.name)}" spellcheck="false" aria-label="${esc(x.desc)}"><span class="muted sm">${esc(x.desc)}</span>`).join("")}</div>
          <p class="muted sm">TagStudio sichert nur die Tags (wenige MB). Gegen den Verlust des Laufwerks sichere die Musik zusätzlich auf ein anderes Laufwerk oder in die Cloud.</p>`
        : `<h2>Deine Musik</h2><p class="muted">Der <b>Bibliotheksordner</b> öffnet sich beim Start im Tagger. Der <b>Eingangsordner</b> ist der Ordner, in dem neue Musik landet (für „Vorbereiten“).</p>
        <div class="frm"><label for="wLib">Bibliothek</label>${pathIn("wLib", W.lib, "z. B. " + (W.base || "S:\\Musik") + "\\01_Library")}
        <label for="wInbox">Eingangsordner (optional)</label>${pathIn("wInbox", W.inbox, "z. B. " + (W.base || "S:\\Musik") + "\\00_New")}</div>`;
      case 3: return `<h2>Sicherheit</h2><p class="muted">TagStudio verändert nur Tags, nie das Audio. Trotzdem lohnt sich ein Netz:</p>
        <div class="wiz-opts"><label class="wiz-opt"><input type="checkbox" id="wBackup" ${W.backup ? "checked" : ""}><span><b>Vor jedem Speichern sichern</b><span class="muted sm">Die Tags der betroffenen Titel werden vorher abgelegt und lassen sich wiederherstellen.</span></span></label>
        ${W.lib || W.mode === "struct" ? `<label class="wiz-opt"><input type="checkbox" id="wSnap" ${W.snap ? "checked" : ""}><span><b>Bibliothek mit Snapshots überwachen</b><span class="muted sm">Merkt sich den Tag-Stand aller Titel; das Journal zeigt später jede Änderung – auch von anderen Programmen.</span></span></label>` : ""}</div>
        ${W.mode === "struct" ? `<p class="muted sm">Sicherungen und Snapshots kommen in ${esc(W.base)}\\${esc(W.names.backup || "99_Sicherung")}.</p>` : `<div class="frm"><label for="wBackupDir">Ordner für Sicherungen</label>${pathIn("wBackupDir", W.backupDir, pg.backup_dir ? `leer = wie bisher (${pg.backup_dir})` : "leer = Standard")}</div>`}`;
      case 4: return `<h2>Deine Programme</h2><p class="muted">Welche Programme nutzt du? TagStudio erkennt deren Tags (Herkunft), schaltet passende Plugins ein und stellt den Vorbereiten-Ablauf darauf ein.</p>
        <div class="wiz-opts cols">${WIZ_PROGRAMS.map(([id, t, plug]) => chk("prog", id, W.programs.has(id), t, plug ? "Plugin zum Übernehmen der Analysewerte" : "")).join("")}</div>
        ${W.goals.has("prep") && prep ? `<label class="check"><input type="checkbox" id="wAdapt" ${W.adapt ? "checked" : ""}> Vorbereiten-Workflow anpassen: Schritte für nicht genutzte Programme entfernen</label>` : ""}`;
      case 5: return `<h2>Online-Dienste <span class="muted sm">(optional)</span></h2><p class="muted">Plugins, die Daten aus dem Internet holen oder mehr Speicher brauchen. Anmeldungen und Schlüssel gibst du später selbst unter Plugins ein.</p>
        <div class="wiz-opts">${WIZ_ONLINE.filter(([id]) => pl[id]).map(([id, t, sub]) => chk("online", id, W.online.has(id), t, sub)).join("")}</div>`;
      case 6: return `<h2>Darstellung</h2><div class="frm"><span>Design</span><div class="seg wiz-theme"><button data-v="dark" class="${W.theme !== "light" ? "on" : ""}">Dunkel</button><button data-v="light" class="${W.theme === "light" ? "on" : ""}">Hell</button></div>
        ${W.notations.length ? `<label for="wNot">Tonart-Schreibweise</label><select id="wNot" class="inp">${W.notations.map(([k, v]) => `<option value="${esc(k)}" ${k === W.notation ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>` : ""}
        <label for="wLayout">Player</label><select id="wLayout" class="inp"><option value="bottom" ${W.layout !== "top" ? "selected" : ""}>unten in der Aktionsleiste</option><option value="top" ${W.layout === "top" ? "selected" : ""}>oben als eigene Leiste</option></select></div>`;
      default: {
        const rec = [...new Set(WIZ_GOALS.filter(([id]) => W.goals.has(id)).flatMap((g) => g[3]))].map((m) => NAV_NAMES[m]);
        return `<h2>Fertig</h2><p class="muted">Das wird eingestellt:</p><ul class="wiz-sum">
          <li>Empfohlen: ${esc(rec.join(", ") || "—")}</li>${W.base ? `<li>Basisordner: ${esc(W.base)}</li>` : ""}
          ${W.mode === "struct" ? `<li>Ordnerstruktur: ${esc(Object.values(W.names).join(", "))}</li>` : ""}
          ${W.mode !== "struct" && W.lib ? `<li>Bibliothek: ${esc(W.lib)}</li>` : ""}${W.mode !== "struct" && W.inbox ? `<li>Eingangsordner: ${esc(W.inbox)}</li>` : ""}
          <li>Sicherungen vor dem Speichern: ${W.backup ? "ja" : "nein"}${(W.lib || W.mode === "struct") && W.snap ? " · Snapshots der Bibliothek" : ""}</li>
          ${W.programs.size ? `<li>Programme: ${esc(WIZ_PROGRAMS.filter(([id]) => W.programs.has(id)).map((p) => p[1]).join(", "))}</li>` : ""}
          ${W.online.size ? `<li>Plugins: ${esc(WIZ_ONLINE.filter(([id]) => W.online.has(id)).map((p) => p[1]).join(", "))}</li>` : ""}</ul>
          <label class="check"><input type="checkbox" id="wFirst" ${W.firstSteps ? "checked" : ""}> „Erste Schritte“-Hinweise auf jeder Seite zeigen</label>
          <p class="muted sm">Assistent und „Erste Schritte“ lassen sich jederzeit neu starten: Hilfe oder Einstellungen › Darstellung.</p>`;
      }
    }
  };
  const render = () => {
    ov.innerHTML = `<div class="wiz-box" role="dialog" aria-modal="true" aria-label="Einrichtungsassistent">
      <div class="wiz-steps">${steps.map((t, i) => `<span class="${i === W.step ? "on" : i < W.step ? "done" : ""}">${i + 1}. ${esc(t)}</span>`).join("")}</div>
      <div class="wiz-body">${body()}</div>
      <div class="wiz-foot"><button class="ghost" data-wiz="skip">${W.step === steps.length - 1 ? "Abbrechen" : "Assistent überspringen"}</button><span class="grow"></span>
        ${W.step ? '<button class="ghost" data-wiz="back">Zurück</button>' : ""}<button class="primary" data-wiz="next">${W.step === steps.length - 1 ? "Einrichten" : "Weiter"}</button></div></div>`;
    (ov.querySelector(".wiz-body input:not([type=checkbox]), .wiz-body button.primary") || ov.querySelector("[data-wiz=next]"))?.focus();
  };
  return new Promise((resolve) => {
    ov.hidden = false;
    render();
    const done = async (apply) => {
      ov.onclick = null;
      if (apply) { try { await wizardApply(W, prep, pl); } catch (e) { toast(String(e.message || e)); } }
      else SETUP.st = await call("setup_finish", SETUP.st.recommended, SETUP.st.first_steps);
      ov.hidden = true; ov.innerHTML = "";
      setupNav();
      if (S.module) firstStepsShow(S.module);
      resolve(apply);
    };
    ov.onclick = async (e) => {
      const pk = e.target.closest("[data-wpick]");
      if (pk) { const inp = $("#" + pk.dataset.wpick, ov); const p = await call("pick_path", "", true, inp.value.trim()); if (p) inp.value = p; return; }
      const dv = e.target.closest("[data-wdrive]");
      if (dv) { W.base = baseFor(dv.dataset.wdrive); $("#wBase", ov).value = W.base; $$(".wiz-drive", ov).forEach((x) => x.classList.toggle("on", x === dv)); return; }
      const th = e.target.closest(".wiz-theme button");
      if (th) { $$(".wiz-theme button", ov).forEach((b) => b.classList.toggle("on", b === th)); S.opts.theme = th.dataset.v; applyTheme(); return; }
      const b = e.target.closest("[data-wiz]"); if (!b) return;
      read();
      if (b.dataset.wiz === "skip") return done(false);
      if (b.dataset.wiz === "back") { W.step--; return render(); }
      if (W.step === steps.length - 1) return done(true);
      if (W.step === 1 && W.mode === "struct" && !W.base) { toast("Bitte einen Basisordner wählen."); return; }
      W.step++; render();
    };
  });
}

async function wizardApply(W, prep, pl) {  // eslint-disable-line no-param-reassign
  const rec = [...new Set(WIZ_GOALS.filter(([id]) => W.goals.has(id)).flatMap((g) => g[3]))];
  if (W.mode === "struct" && W.base) {                               // #171: Struktur anlegen, alles darauf einstellen
    const r = await call("setup_structure", W.base, W.names);
    W.lib = r.paths.library; W.inbox = "";
    prep = await call("prep_overview", null).catch(() => prep);
  } else if (W.base) await call("set_base_dir", W.base, true);
  if (W.lib) await call("set_default_dir", "tagger", W.lib);
  await call("set_backup", W.backup, W.mode === "struct" ? null : (W.backupDir || null), true);
  if (W.lib && W.snap) await call("snap_add_library", W.lib).catch(() => {});
  for (const [id, , plug] of WIZ_PROGRAMS) if (plug && pl[plug]) await call("plugin_enable", plug, W.programs.has(id)).catch(() => {});
  for (const [id] of WIZ_ONLINE) if (pl[id]) await call("plugin_enable", id, W.online.has(id)).catch(() => {});
  if (prep && (W.inbox || W.lib || (W.goals.has("prep") && W.adapt))) {
    const w = JSON.parse(JSON.stringify(prep.workflow));
    if (W.inbox) w.inbox = W.inbox;
    if (W.lib && !w.library) w.library = W.lib;
    if (W.goals.has("prep") && W.adapt) {
      const drop = WIZ_PROGRAMS.filter(([id, , , kw]) => kw && !W.programs.has(id)).map((p) => p[3]);
      w.steps = w.steps.filter((s) => !(["external", "check"].includes(s.type) && drop.some((kw) => s.label.toLowerCase().includes(kw))));
    }
    await call("prep_workflow_save", w);
  }
  S.opts.theme = W.theme; applyTheme(); await call("set_option", "theme", W.theme);
  if (W.notation) await call("tag_key_notation", W.notation).catch(() => {});
  await call("set_player_pref", "layout", W.layout).catch(() => {});
  if (typeof pl2Pref === "function") pl2Pref("layout", W.layout);
  if (W.mode !== "struct") await call("folders_adopt").catch(() => {});   // #310: gewählte Ordner als Rollen
  SETUP.st = await call("setup_finish", rec, W.firstSteps);
  toast("Eingerichtet – viel Spass mit TagStudio!");
  const start = rec[0] || "tagger";
  setModule(start, { side: true });
  if (start === "tagger" && W.lib && typeof taggerAutoStart === "function") taggerAutoStart().catch(() => {});
}

// ---------------------------------------------------------------------- Erste Schritte (#170)
function firstStepsShow(m) {
  const box = $("#firstSteps"), s = SETUP.st;
  if (!box) return;
  const tips = FIRST_STEPS[m];
  if (!s || !s.first_steps || !tips || s.first_steps_seen.includes(m) || !$("#wizard").hidden) { box.hidden = true; return; }
  box.innerHTML = `<div class="fs-h"><b>Erste Schritte – ${esc(NAV_NAMES[m] || m)}</b><button class="icon-btn" data-fs="close" title="Ausblenden" aria-label="Ausblenden">✕</button></div>
    <ol>${tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ol>
    <div class="fs-b"><button class="ghost sm" data-fs="off">Alle Hinweise aus</button><button class="primary sm" data-fs="ok">Verstanden</button></div>`;
  box.dataset.m = m;
  box.hidden = false;
}

async function whatsNew() {
  let r;
  try { r = await call("whats_new"); } catch (e) { return; }
  if (!r || !r.show) return;
  await modal({ title: `Neu in TagStudio ${esc(S.settings.version)}`, wide: true,
    html: `<div class="md wn">${r.parts.map((p) => `<h3>${esc(p.version)}</h3>${mdLite(p.notes)}`).join("")}</div>`,
    buttons: [{ label: "Alle Versionshinweise …", value: "all" }, { label: "OK", value: true, primary: true }] }).then((v) => { if (v === "all") showReleaseNotes(); });
  call("whats_new_seen").catch(() => {});
}

(function bindSetup() {
  document.addEventListener("click", async (e) => {
    const f = e.target.closest("#firstSteps [data-fs]");
    if (f) {
      const box = $("#firstSteps"), m = box.dataset.m;
      if (f.dataset.fs === "off") SETUP.st = await call("set_first_steps", false);
      else SETUP.st = await call("first_steps_seen", m);
      box.hidden = true;
      return;
    }
    if (e.target.closest("[data-setup=wizard]")) { await wizardRun(); if (S.module === "settings") settingsShow(); return; }
    const mv = e.target.closest("[data-navmove]");
    if (mv) {
      const [m, d] = mv.dataset.navmove.split("|");
      const order = [...SETUP.st.order], i = order.indexOf(m), j = i + +d;
      if (i < 0 || j < 0 || j >= order.length) return;
      [order[i], order[j]] = [order[j], order[i]];
      SETUP.st = await call("set_nav_order", order);
      setupNav(); stNavOrderRefresh();
      return;
    }
    if (e.target.closest("[data-navorder=reset]")) { SETUP.st = await call("set_nav_order", []); setupNav(); stNavOrderRefresh(); return; }
    if (e.target.closest("[data-setup=firststeps]")) { SETUP.st = await call("first_steps_restart"); toast("„Erste Schritte“ werden wieder auf jeder Seite gezeigt."); firstStepsShow(S.module); return; }
  });
  document.addEventListener("change", async (e) => {
    const h = e.target.closest("[data-navshow]");
    if (h) {
      const hidden = [...document.querySelectorAll("[data-navshow]")].filter((x) => !x.checked).map((x) => x.dataset.navshow);
      SETUP.st = await call("set_nav_hidden", hidden);
      setupNav();
    }
  });
})();

/** Liste „Menüpunkte“ nach einer Änderung der Reihenfolge neu zeichnen (ohne die ganze Seite) */
function stNavOrderRefresh() {
  const box = $("#stNavOrder"); if (!box) return;
  const tmp = document.createElement("div");
  tmp.innerHTML = setupSettingsHtml();
  const fresh = tmp.querySelector("#stNavOrder");
  if (fresh) box.replaceWith(fresh);
}

/** Einstellungen › Darstellung: Seitenleiste und Einrichtung (#169) */
function setupSettingsHtml() {
  const s = SETUP.st; if (!s) return "";
  const order = s.order || s.modules.filter((m) => !["settings", "help"].includes(m));
  return `<h4 class="st-sub">Seitenleiste</h4><div class="st-row"><span>Menüpunkte</span><div><div class="nav-pick nav-order" id="stNavOrder">${order.map((m, i) => `<div class="nav-ord-row"><label class="check"><input type="checkbox" data-navshow="${m}" ${s.hidden.includes(m) ? "" : "checked"}> ${esc(NAV_NAMES[m])}${s.recommended.includes(m) ? ' <span class="rec-dot" title="empfohlen">★</span>' : ""}</label><span class="nav-ord-btns"><button class="icon-btn sm" data-navmove="${m}|-1" title="Nach oben" aria-label="Nach oben" ${i ? "" : "disabled"}>↑</button><button class="icon-btn sm" data-navmove="${m}|1" title="Nach unten" aria-label="Nach unten" ${i < order.length - 1 ? "" : "disabled"}>↓</button></span></div>`).join("")}</div>
    <button class="ghost sm" data-navorder="reset">Standard-Reihenfolge</button></div>
    <span>Einrichtung</span><div class="st-path"><button class="ghost sm" data-setup="wizard">Einrichtungsassistent starten</button><button class="ghost sm" data-setup="firststeps">„Erste Schritte“ neu starten</button></div></div>`;
}

// Einstellungen › Speicherort und Ordner: web/folders.js (#310)

// ---------------------------------------------------------------------- Aussortieren (#173)
const archRows = (rows) => `<div class="fx-table" style="max-height:38vh"><table><thead><tr><th>Titel</th><th>Ziel im Archiv</th></tr></thead><tbody>${rows.map((r) => `<tr class="${r.problem ? "gone" : ""}"><td title="${esc(r.src)}">${esc(r.src.split(/[\\/]/).pop())}${r.stems ? ' <span class="muted sm">+ Stems</span>' : ""}</td><td>${r.problem ? `<span class="st-missing">${esc(r.problem)}</span>` : `<span class="muted sm" title="${esc(r.dst)}">${esc(r.dst)}</span>`}</td></tr>`).join("")}</tbody></table></div>`;

async function archiveTaggerDialog(idx) {
  if (!idx.length) { toast("Bitte zuerst Titel markieren."); return; }
  let p;
  try { p = await call("tag_archive", idx, false); } catch (e) { toast(String(e.message || e)); return; }
  const ok = await modal({ title: `Aussortieren (${idx.length})`, wide: true,
    html: `<p style="margin:0 0 8px">Die Titel werden nach <b>${esc(p.archive)}</b> verschoben – Unterordner bleiben erhalten, ein Stems-Ordner wandert mit. Jede Bewegung steht im Vermerk <code>_aussortiert.csv</code>; zurückholen unter Einstellungen › Speicherort und Ordner.</p>${archRows(p.rows)}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: `${fmtN(p.ok)} Titel aussortieren`, value: true, primary: true }] });
  if (!ok || !p.ok) return;
  const r = await call("tag_archive", idx, true);
  status(r.message, r.errors.length ? "warn" : "info");
  if (r.errors.length) await info("Hinweise", r.errors.join("\n"));
  if (typeof taggerLoad === "function") taggerLoad();
}

async function archivePrepDialog(names) {
  const wid = PREP.d.workflow.id;
  let p;
  try { p = await call("prep_archive", wid, names, false, true); } catch (e) { toast(String(e.message || e)); return; }
  const res = await modal({ title: `Aussortieren (${names.length})`, wide: true,
    html: `<p style="margin:0 0 8px">Das Original aus dem Eingang kommt nach <b>${esc(p.archive)}</b> (Unterordner bleiben), der Titel verschwindet aus dem Workflow.</p>${archRows(p.rows)}
      ${p.copies.length ? `<label class="check" style="margin-top:8px"><input type="checkbox" id="arCopies" checked> ${fmtN(p.copies.length)} Stufen-Kopie(n) in den Arbeitsordnern löschen</label>` : ""}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: `${fmtN(p.ok)} Titel aussortieren`, value: true, primary: true }],
    collect: (b) => ({ copies: !!(b.querySelector("#arCopies") || {}).checked }) });
  if (!res || !p.ok) return;
  const d = await call("prep_archive", wid, names, true, res.copies);
  if (d.errors && d.errors.length) await info("Hinweise", d.errors.join("\n"));
  PREP.sel.clear();
  prepApply(d);
  status(d.message, "info");
}

async function archiveRestoreDialog() {
  const a = await call("archive_list");
  const can = (e) => !e.restored && e.in_archive && e.src_free && !/Stems/.test(e.area);
  const ids = await modal({ title: "Aussortierte Titel", wide: true,
    html: a.entries.length ? `<p class="muted sm" style="margin:0 0 8px">Archiv: ${esc(a.archive)} · zurückholen geht, wenn der Titel noch im Archiv liegt und der alte Platz frei ist.</p>
      <div class="fx-table" style="max-height:50vh"><table><thead><tr><th></th><th>Datum</th><th>Titel</th><th>Von</th><th>Bereich</th></tr></thead><tbody>${a.entries.map((e) => `<tr class="${can(e) ? "" : "gone"}"><td>${can(e) ? `<input type="checkbox" data-arid="${e.id}">` : ""}</td><td class="sm">${esc(e.at)}</td><td title="${esc(e.dst)}">${esc(e.dst.split(/[\\/]/).pop())}</td><td class="sm muted" title="${esc(e.src)}">${esc(e.src)}</td><td class="sm">${esc(e.area)}${e.restored ? " · zurückgeholt" : !e.in_archive ? " · nicht mehr im Archiv" : ""}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="muted">Noch nichts aussortiert${a.archive ? "" : " – kein Archiv-Ordner festgelegt"}.</p>`,
    buttons: [{ label: "Schliessen", value: null }, ...(a.entries.some(can) ? [{ label: "Ausgewählte zurückholen", value: true, primary: true }] : [])],
    collect: (b) => [...b.querySelectorAll("[data-arid]:checked")].map((x) => +x.dataset.arid) });
  if (!ids || !ids.length) return;
  const r = await call("archive_restore", ids);
  status(r.message, r.errors.length ? "warn" : "info");
  if (r.errors.length) await info("Hinweise", r.errors.join("\n"));
}
