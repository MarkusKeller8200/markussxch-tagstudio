/* MarKusSXCH TagStudio – Seite „Snapshots“: überwachte Ordner, Snapshots, Änderungsjournal, Zurücksetzen
   (#53, #54, #61). Logik in snapshots.py / session.py; Konzept: docs/KONZEPT-SNAPSHOTS.md */
"use strict";

const SN = { ov: null, lid: null, list: null, a: null, b: "live", j: null, filter: new Set(), q: "", open: new Set(), prog: "*", fkey: "",
  sel: new Map(), done: new Set() };
const SN_STATUS = { changed: "geändert", rewrite: "umgeschrieben", renamed: "umbenannt", audio: "Audio", new: "neu", removed: "entfernt" };

const snMB = (b) => (b < 1048576 ? `${Math.max(0, Math.round(b / 1024))} KB` : b < 1073741824 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${(b / 1073741824).toFixed(2).replace(".", ",")} GB`);
const snTime = (c) => (c ? c.slice(8, 10) + "." + c.slice(5, 7) + "." + c.slice(0, 4) + " " + c.slice(11, 16) : "");

async function snSizeRefresh() { try { snSideSize((await call("snap_overview")).total); } catch (e) { /* egal */ } }
function snSideSize(total) { const el = $("#snapSize"); if (el) el.textContent = total ? snMB(total) : ""; }

async function snapShow() {
  SN.ov = await call("snap_overview");
  snSideSize(SN.ov.total);
  if (!SN.ov.libs.some((l) => l.id === SN.lid)) SN.lid = SN.ov.libs.length ? SN.ov.libs[0].id : null;
  $("#snInfo").textContent = `Speicher: ${SN.ov.dir} · gesamt ${snMB(SN.ov.total)}${SN.ov.readonly ? " · NUR LESEN (aus neuerer TagStudio-Version)" : ""}`;
  // #77: mehrere Ordner eindeutig – Farbe, Name (bei gleichen Namen mit übergeordnetem Ordner), Pfad, Zustand
  $("#snLibs").innerHTML = SN.ov.libs.length ? `<div class="muted sm">${SN.ov.libs.length} überwachte(r) Ordner</div>` + SN.ov.libs.map((l) => `<div class="sn-lib${l.id === SN.lid ? " cur" : ""}${l.exists ? "" : " missing"}" data-lib="${esc(l.id)}" role="button" tabindex="0" style="--lh:${l.hue}">
      <span class="n"><i class="sn-dot"></i>${esc(l.label || l.name)}</span><span class="z">${snMB(l.bytes)}</span>
      <span class="r" title="${esc(l.root)}">${l.exists ? esc(l.root) : "nicht erreichbar: " + esc(l.root)}</span>
      <span class="z acts"><button class="x" data-lren="${esc(l.id)}" title="Anzeigename ändern">✎</button><button class="x" data-lmove="${esc(l.id)}" title="Ordner ändern (z. B. nach Umzug auf ein anderes Laufwerk)">📁</button><button class="x" data-unwatch="${esc(l.id)}" title="Nicht mehr überwachen (Snapshots löschen)">✕</button></span>
      <span class="s">${l.count} Snapshot(s)${l.last ? " · zuletzt " + esc(l.last.age) : ""}</span>
      <label class="s auto" title="Täglicher automatischer Snapshot für diesen Ordner"><input type="checkbox" data-lauto="${esc(l.id)}" ${l.auto ? "checked" : ""}> täglich</label></div>`).join("")
    : '<div class="tg-empty">Noch kein Ordner überwacht. Oben „+ Ordner überwachen …“ wählen – z. B. deine MP3-Bibliothek.</div>';
  $("#snCreate").disabled = !SN.lid || SN.ov.readonly;
  await snLoadList();
}

async function snLoadList() {
  if (!SN.lid) { $("#snSnaps").innerHTML = ""; snFillSelects(); return; }
  SN.list = await call("snap_list", SN.lid);
  if (!SN.list.snapshots.some((s) => s.id === SN.a)) SN.a = SN.list.snapshots.length ? SN.list.snapshots[0].id : null;
  if (SN.b !== "live" && !SN.list.snapshots.some((s) => s.id === SN.b)) SN.b = "live";
  $("#snSnaps").innerHTML = SN.list.snapshots.length ? SN.list.snapshots.map((s) => `<div class="sn-snap${s.id === SN.a ? " a" : ""}" data-snap="${esc(s.id)}" title="Klick: als Basis für das Journal">
      <span class="t">${esc(s.label)}${s.pinned ? " 📌" : ""}</span>
      <span class="acts"><button data-pin="${esc(s.id)}" class="${s.pinned ? "on" : ""}" title="${s.pinned ? "Nicht mehr anheften" : "Anheften (wird nie aufgeräumt)"}">📌</button><button data-ren="${esc(s.id)}" title="Umbenennen">✎</button><button data-del="${esc(s.id)}" title="Löschen">✕</button></span>
      <span class="m">${snTime(s.created)} · ${s.count} Titel · ${snMB(s.bytes)}${s.auto ? " · automatisch" : ""}</span></div>`).join("")
    : '<div class="tg-empty">Noch kein Snapshot. „Snapshot erstellen“ hält den jetzigen Stand fest.</div>';
  snFillSelects();
}

function snFillSelects() {
  const snaps = (SN.list && SN.list.snapshots) || [];
  const opt = (s) => `<option value="${esc(s.id)}">${esc(snTime(s.created) + " · " + s.label)}</option>`;
  $("#snA").innerHTML = snaps.map(opt).join("") || "<option>–</option>";
  if (SN.a) $("#snA").value = SN.a;
  $("#snB").innerHTML = '<option value="live">Jetzt (aktueller Stand)</option>' + snaps.map(opt).join("");
  $("#snB").value = SN.b;
  $("#snRun").disabled = !snaps.length;
}

// ---------------------------------------------------------------------- Journal
async function snRun() {
  if (!SN.lid || !SN.a) return;
  const res = await runTask(call("start_snap_journal", SN.lid, SN.a, SN.b), "Änderungsjournal berechnen");
  if (!res) return;
  if (SN.b === "live") {                    // #58: gesehen → Hinweis in der Fußleiste zurücksetzen
    call("snap_watch_ack", SN.lid).catch(() => {});
    if (SNW.res) { SNW.res.libs = SNW.res.libs.filter((l) => l.id !== SN.lid); SNW.res.total = SNW.res.libs.reduce((n, l) => n + l.count, 0); snWatchChip(); }
  }
  SN.j = res; SN.sel = new Map(); SN.done = new Set(); SN.open = new Set(); SN.filter = new Set(); SN.prog = "*"; SN.fkey = "";
  const st = SN.j.counts;
  if (st.changed) SN.filter.add("changed");
  snRender();
  if (res.errors && res.errors.length) toast(`${res.errors.length} Datei(en) nicht lesbar.`);
}

function snVisible() {
  const q = SN.q.trim().toLowerCase();
  return SN.j.rows.filter((r) => (!SN.filter.size || SN.filter.has(r.status) || (SN.filter.has("audio") && r.audio))
    && (SN.prog === "*" || r.guess === SN.prog) && (!SN.fkey || r.fields.some((f) => f.key === SN.fkey))   // #57
    && (!q || r.p.toLowerCase().includes(q) || r.fields.some((f) => (f.label + " " + f.key + " " + f.old + " " + f.new).toLowerCase().includes(q))));
}

function snRender() {
  const j = SN.j;
  if (!j) return;
  const c = j.counts, keys = ["changed", "renamed", "audio", "new", "removed", "rewrite"];
  $("#snFilter").innerHTML = keys.filter((k) => c[k]).map((k) => `<button class="sn-chip${SN.filter.has(k) ? " on" : ""}" data-f="${k}">${SN_STATUS[k]} ${fmtN(c[k])}</button>`).join("")
    + snProgFieldSelects()
    + `<input id="snQ" placeholder="Titel, Feld oder Wert suchen …" value="${esc(SN.q)}" aria-label="Journal durchsuchen">`
    + `<button class="ghost sm" id="snSelVis" title="In allen sichtbaren Titeln die (gefilterten) Felder zum Zurücksetzen auswählen">Sichtbare auswählen</button>`;
  const rows = snVisible();
  const total = j.rows.length;
  $("#snJournal").innerHTML = !total ? `<div class="tg-empty">Keine Änderungen zwischen „${esc(j.a.label)}“ und „${esc(j.b.label)}“. 🎉</div>`
    : !rows.length ? '<div class="tg-empty">Nichts passt zum Filter.</div>'
    : rows.slice(0, 1500).map((r) => {
      const can = !!r.fields.length && r.status !== "removed" && r.status !== "new";
      const ks = SN.sel.get(r.p), all = ks && ks.size === r.fields.length;
      const dir = r.p.includes("/") ? r.p.slice(0, r.p.lastIndexOf("/") + 1) : "";
      const sum = r.fields.length ? r.fields.slice(0, 4).map((f) => f.label.replace(/^Benutzertext \((.+)\)$/, "$1")).join(", ") + (r.fields.length > 4 ? ` +${r.fields.length - 4}` : "")
        : r.status === "renamed" ? "von " + r.p_old : r.status === "rewrite" ? "nur anders gespeichert (gleiche Werte)" : "";
      const open = SN.open.has(r.p);
      return `<div class="sn-row${SN.done.has(r.p) ? " done" : ""}" data-p="${esc(r.p)}">
        <div class="h"><input type="checkbox" data-row ${can ? "" : "disabled"} ${all ? "checked" : ""} aria-label="${esc(r.p)} auswählen">
          <span class="sn-st ${r.status}">${SN_STATUS[r.status]}${r.audio && r.status !== "audio" ? " · Audio" : ""}</span>${snGuess(r)}
          <span class="p" title="${esc(r.p)}"><span class="d">${esc(dir)}</span>${esc(r.p.slice(dir.length))}</span>
          <span class="sum">${esc(sum)} ${r.fields.length ? (open ? "▾" : "▸") : ""}${r.status !== "removed" && r.status !== "new" ? '<button class="sn-cmp" data-cmp title="Im Vergleich öffnen (Snapshot ↔ jetzt)">⇄</button>' : ""}</span></div>
        ${open && r.fields.length ? `<div class="sn-fields">${r.fields.map((f) => `<div class="sn-f"><input type="checkbox" data-k="${esc(f.key)}" ${ks && ks.has(f.key) ? "checked" : ""} aria-label="${esc(f.label)} zurücksetzen">
          <span class="k">${srcBadge(f.src)}${esc(f.label)}</span><span class="o${f.state === "removed" ? "" : ""}" title="${esc(f.old)}">${f.state === "added" ? "<i>– fehlte –</i>" : esc(f.old)}</span><span class="muted">→</span><span class="n" title="${esc(f.new)}">${f.state === "removed" ? "<i>– entfernt –</i>" : esc(f.new)}</span></div>`).join("")}</div>` : ""}
      </div>`;
    }).join("") + (rows.length > 1500 ? `<div class="tg-empty">… ${fmtN(rows.length - 1500)} weitere – Filter benutzen.</div>` : "");
  snSelInfo();
}

/** #57: vermutliches Programm je Titel */
function snGuess(r) {
  if (r.guess === null || r.guess === undefined) return '<span class="sn-guess"></span>';
  const p = (SN.j.programs || {})[r.guess];
  return r.guess ? `<span class="sn-guess" title="vermutlich geändert von ${esc(p ? p.name : r.guess)} (aus der Herkunft der geänderten Felder)">${srcBadge(r.guess) || esc(p ? p.name : r.guess)}</span>`
    : '<span class="sn-guess unk" title="Programm nicht erkennbar – nur Standardfelder geändert">?</span>';
}

/** #57: Filter „vermutlich von …“ und „Feld …“ */
function snProgFieldSelects() {
  const progs = Object.entries(SN.j.programs || {}).sort((a, b) => (a[0] === "") - (b[0] === "") || b[1].rows - a[1].rows);
  const keys = new Map();
  SN.j.rows.forEach((r) => { if (SN.prog === "*" || r.guess === SN.prog) r.fields.forEach((f) => { const k = keys.get(f.key) || { label: f.label, n: 0 }; k.n++; keys.set(f.key, k); }); });
  if (SN.fkey && !keys.has(SN.fkey)) SN.fkey = "";
  const fk = [...keys.entries()].sort((a, b) => b[1].n - a[1].n);
  return `<select id="snProg" class="inp sm" aria-label="Vermutlich geändert von"><option value="*">Alle Programme</option>${progs.map(([k, v]) => `<option value="${esc(k)}" ${k === SN.prog ? "selected" : ""}>${esc(k ? "vermutlich " + v.name : "Programm unbekannt")} (${fmtN(v.rows)})</option>`).join("")}</select>`
    + `<select id="snFkey" class="inp sm" aria-label="Feld"><option value="">Alle Felder</option>${fk.map(([k, v]) => `<option value="${esc(k)}" ${k === SN.fkey ? "selected" : ""}>${esc(v.label)} (${fmtN(v.n)})</option>`).join("")}</select>`;
}

/** #57: „alle Änderungen von … an Feld … zurück“ – sichtbare Titel (und ggf. nur das gefilterte Feld) auswählen */
function snSelectVisible() {
  let n = 0;
  snVisible().forEach((r) => {
    if (!r.fields.length || r.status === "removed" || r.status === "new" || SN.done.has(r.p)) return;
    const ks = SN.fkey ? [SN.fkey] : r.fields.map((f) => f.key);
    SN.sel.set(r.p, new Set(ks)); n += ks.length;
  });
  snRender();
  toast(n ? `${fmtN(n)} Feld(er) ausgewählt – „Auswahl zurücksetzen“ übernimmt den Snapshot-Stand.` : "Nichts zum Auswählen.");
}

function snSelInfo() {
  let files = 0, fields = 0;
  SN.sel.forEach((ks) => { if (ks.size) { files++; fields += ks.size; } });
  $("#snSelInfo").textContent = files ? `${fields} Feld(er) in ${files} Titel(n) ausgewählt` : "Titel oder einzelne Felder ankreuzen, um sie auf den Snapshot-Stand zurückzusetzen.";
  $("#snRevert").disabled = !files;
  $("#snBytes").disabled = !files;
}

function snItems(whole) {
  const out = [];
  SN.sel.forEach((ks, p) => {
    if (!ks.size) return;
    const r = SN.j.rows.find((x) => x.p === p);
    out.push({ p, p_old: r ? r.p_old : "", keys: whole || (r && ks.size === r.fields.length) ? null : [...ks] });
  });
  return out;
}

async function snRevert(mode) {
  const whole = mode === "bytes";
  const items = snItems(whole);
  if (!items.length) return;
  if (whole) {
    const ok = await dialog({ title: "Byte-genau zurückschreiben?", text: `${items.length} Titel bekommen exakt die Tags aus dem Snapshot – auch Binärfelder (Serato, Cue-Punkte). Spätere Änderungen an diesen Titeln gehen verloren; vorher wird eine Sicherung angelegt. Titel mit geändertem Audio werden übersprungen.`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Zurückschreiben", value: true, primary: true }] });
    if (!ok) return;
  }
  const r = await call("snap_revert", items, mode, false);
  if (!r.ok) return info("Zurücksetzen nicht möglich", r.error);
  items.forEach((it) => { SN.done.add(it.p); SN.sel.delete(it.p); });
  const stt = await call("state");
  if (stt.meta) { S.meta = stt.meta; renderMeta(); }
  if (S.pairs && S.pairs.length) await refreshAll(stt);
  if (typeof taggerRefresh === "function") await taggerRefresh();
  snRender();
  status(r.message, r.errors.length ? "warn" : "ok");
  if (r.errors.length) info("Nicht alles zurückgesetzt", r.errors.slice(0, 30).join("\n"));
}

// ---------------------------------------------------------------------- Aktionen
/** #60: Speicherort ändern – ganzer Speicher wird kopiert, geprüft und erst dann am alten Ort entfernt. */
async function snMoveStore(toDefault = false) {
  let dest = "";
  if (!toDefault) {
    dest = await call("pick_path", "", true, "");
    if (!dest) {
      if (S.settings.native) return false;
      dest = await modal({ title: "Speicherort ändern", html: '<div class="frm"><label for="snDest">Neuer Ort</label><input id="snDest" placeholder="z. B. S:\\_MP3" autofocus></div>',
        buttons: [{ label: "Abbrechen", value: null }, { label: "Weiter", value: true, primary: true }], collect: (b) => $("#snDest", b).value.trim() });
      if (!dest) return false;
    }
  }
  const ok = await dialog({ title: "Snapshot-Speicher verschieben?", text: toDefault
      ? "Der Speicher wird zurück in den TagStudio-Ordner verschoben."
      : `Ziel: ${dest}\n\nIst der Ordner nicht leer (z. B. dein MP3-Ordner), legt TagStudio darin den Unterordner „.tagstudio-snapshots“ an. Der Speicher wird kopiert, geprüft und erst danach am alten Ort entfernt.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Verschieben", value: true, primary: true }] });
  if (!ok) return false;
  const r = await runTask(call("start_snap_move", dest), "Snapshot-Speicher verschieben");
  if (!r || r.cancelled) return false;
  toast(r.message);
  if (typeof snapShow === "function" && S.module === "snapshots") snapShow();
  snSizeRefresh();
  return true;
}

/** #60: Nach dem Einlesen: liegt im Ordner ein anderer Snapshot-Speicher? Anbieten, ihn zu verwenden. */
async function snDetect(path) {
  if (!path || path.startsWith("snapshot:")) return;
  let d = null;
  try { d = await call("snap_detect", path); } catch (e) { return; }
  if (!d) return;
  const libs = (d.libs || []).map((l) => `• ${l.name} – ${l.count} Snapshot(s)${l.exists ? "" : " (Ordner nicht gefunden)"}`).join("\n");
  const v = await dialog({ title: "Snapshot-Speicher gefunden",
    text: `In diesem Ordner liegt ein Snapshot-Speicher:\n${d.root}\n\n${libs || "(noch ohne überwachte Ordner)"}${d.error ? "\n\n" + d.error : ""}\n\nStatt des bisherigen verwenden? Der bisherige Speicher bleibt unverändert erhalten.`,
    buttons: [{ label: "Nicht mehr fragen", value: "ignore" }, { label: "Später", value: null }, { label: "Verwenden", value: "use", primary: true }] });
  if (v === "ignore") { await call("snap_ignore", d.root); return; }
  if (v !== "use") return;
  const r = await call("snap_use", d.root);
  if (!r.ok) return info("Nicht möglich", r.error);
  toast("Snapshot-Speicher gewechselt.");
  snSizeRefresh();
  if (S.module === "snapshots") snapShow();
}

/** #56: Snapshot als Quelle im Vergleich wählen → Pfadfeld bekommt „snapshot:<Ordner>/<Snapshot>“. */
async function snPickSpec(side) {
  const ov = await call("snap_overview");
  if (!ov.libs.length) return info("Keine Snapshots", "Noch kein Ordner überwacht – auf der Seite „Snapshots“ einen Ordner hinzufügen und einen Snapshot erstellen.");
  const lists = await Promise.all(ov.libs.map((l) => call("snap_list", l.id)));
  const html = '<div class="sn-pick">' + ov.libs.map((l, k) => `<div class="lib">${esc(l.label || l.name)} <span class="muted sm">${esc(l.root)}</span></div>`
    + (lists[k].snapshots.map((s) => `<button data-spec="snapshot:${esc(l.id)}/${esc(s.id)}"><span>${esc(s.label)}${s.pinned ? " 📌" : ""}</span><span class="muted">${snTime(s.created)} · ${s.count} Titel</span></button>`).join("") || '<div class="muted sm">noch kein Snapshot</div>')).join("") + "</div>";
  let picked = null;
  await modal({ title: `Snapshot ${side === "L" ? "links" : "rechts"}`, wide: true,
    html: `<p class="muted sm" style="margin:0 0 8px">Die Snapshot-Seite ist schreibgeschützt: Werte lassen sich nur in Richtung der echten Dateien übernehmen. Tipp: Zuordnung „Audio-Inhalt“ findet auch umbenannte Titel.</p>${html}`,
    buttons: [{ label: "Abbrechen", value: null }],
    onMount: (b) => b.addEventListener("click", (e) => { const t = e.target.closest("[data-spec]"); if (t) { picked = t.dataset.spec; $("#mBtns button")?.click(); } }) });
  if (!picked) return;
  $(side === "L" ? "#pathL" : "#pathR").value = picked;
  if (typeof homeSync === "function") homeSync();
  const other = $(side === "L" ? "#pathR" : "#pathL");
  if (!other.value.trim()) {
    const lib = ov.libs.find((l) => picked.startsWith(`snapshot:${l.id}/`));
    if (lib && lib.exists) other.value = lib.root;           // Standard: Snapshot ↔ Jetzt
  }
  toast("Snapshot gewählt – „Vergleichen“ startet.");
}

/** #56: aus dem Journal: nur diesen einen Titel im Vergleich öffnen (Snapshot ↔ jetzt bzw. zweiter Snapshot) */
async function snOpenCompare(p) {
  const lib = SN.ov.libs.find((l) => l.id === SN.lid);
  const r = SN.j.rows.find((x) => x.p === p);
  if (!lib || !r) return;
  const q = (rel) => "?p=" + encodeURIComponent(rel);
  const old = r.p_old || p;                       // umbenannt: im Snapshot unter dem alten Pfad
  $("#pathL").value = `snapshot:${SN.lid}/${SN.a}${q(old)}`;
  $("#pathR").value = SN.b === "live" ? lib.root.replace(/[\\/]+$/, "") + (lib.root.includes("\\") ? "\\" : "/") + p.split("/").join(lib.root.includes("\\") ? "\\" : "/") : `snapshot:${SN.lid}/${SN.b}${q(p)}`;
  setModule("compare");
  await compare(false);
  if (S.opts.filter !== "diff") applyState(await call("set_option", "filter", "diff"));   // #81: nur die Änderungen
  if (!S.opts.show_trivial) applyState(await call("set_option", "show_trivial", true));  // … auch die unwichtigen
}

async function snAddLibrary() {
  let p = await call("pick_path", "", true, "");
  if (!p) {
    if (S.settings.native) return;
    p = await modal({ title: "Ordner überwachen", html: '<div class="frm"><label for="snPath">Ordner</label><input id="snPath" placeholder="z. B. S:\\_MP3\\01_Library" autofocus></div>',
      buttons: [{ label: "Abbrechen", value: null }, { label: "Überwachen", value: true, primary: true }], collect: (b) => $("#snPath", b).value.trim() });
    if (!p) return;
  }
  const r = await call("snap_add_library", p, null);
  if (!r.ok) return info("Ordner nicht möglich", r.error);
  SN.lid = r.library.id;
  await snapShow();
  if (!SN.list.snapshots.length && await dialog({ title: "Ersten Snapshot erstellen?", text: `„${r.library.name}“ wird überwacht. Soll der jetzige Stand gleich festgehalten werden? (läuft im Hintergrund)`,
    buttons: [{ label: "Später", value: null }, { label: "Snapshot erstellen", value: true, primary: true }] })) snCreate("Erster Snapshot");
}

async function snCreate(label = null) {
  if (!SN.lid) return toast("Erst einen Ordner überwachen.");
  if (label === null) {
    const v = await modal({ title: "Snapshot erstellen", html: `<div class="frm"><label for="snLabel">Bezeichnung</label><input id="snLabel" placeholder="z. B. Vor Mixed In Key" autofocus>
      <label></label><label class="check"><input type="checkbox" id="snPin" checked> anheften (wird beim Aufräumen nie gelöscht)</label></div>`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Erstellen", value: true, primary: true }],
      collect: (b) => ({ label: $("#snLabel", b).value.trim(), pin: $("#snPin", b).checked }) });
    if (!v) return;
    label = v.label; var pin = v.pin;
  }
  const r = await call("snap_create", SN.lid, label || "", false, label ? pin !== false : false);
  if (!r.ok) return info("Snapshot nicht möglich", r.error);
  jobsQueued(r);
}

function jobFinishedSnapshot(j) { if (j.plugin === "tagstudio:snapshot" && S.module === "snapshots") snapShow(); else if (j.plugin === "tagstudio:snapshot") call("snap_overview").then((o) => snSideSize(o.total)); }

// ---------------------------------------------------------------------- Start (#54)
// ---------------------------------------------------------------------- Überwachung zur Laufzeit (#58)
const SNW = { timer: 0, last: 0, busy: false, res: null };
function snWatchStart() {
  clearInterval(SNW.timer);
  SNW.last = Date.now();
  SNW.timer = setInterval(snWatchTick, 30000);
  snWatchTick(true);                        // Ausgangslage aufnehmen
}
async function snWatchTick(first = false) {
  const min = (SN.ov && SN.ov.settings && SN.ov.settings.snap_watch !== undefined) ? SN.ov.settings.snap_watch : (SNW.res ? SNW.res.interval : 5);
  if (SNW.busy || (!first && (!min || Date.now() - SNW.last < min * 60000))) return;
  SNW.busy = true; SNW.last = Date.now();
  try { SNW.res = await call("snap_watch"); } catch (e) { SNW.res = null; } finally { SNW.busy = false; }
  snWatchChip();
}
function snWatchChip() {
  const c = $("#snWatchChip"), r = SNW.res;
  if (!c) return;
  c.hidden = !(r && r.total);
  if (c.hidden) return;
  $("#snwText").textContent = `${fmtN(r.total)} Titel extern geändert`;
  c.title = r.libs.map((l) => `${l.name}: ${l.count} Titel\n` + l.files.slice(0, 8).map((f) => "  " + f).join("\n") + (l.count > 8 ? "\n  …" : "")).join("\n") + "\n\nKlick: Journal letzter Snapshot ↔ jetzt";
}
async function snWatchOpen() {
  const r = SNW.res;
  if (!r || !r.libs.length) return;
  const l = r.libs[0];
  await call("snap_watch_ack", l.id);
  r.total -= l.count; r.libs.shift();
  snWatchChip();
  SN.lid = l.id; SN.a = null; SN.b = "live";
  setModule("snapshots");
  setTimeout(async () => { await snLoadList(); if (SN.a) snRun(); else toast("Noch kein Snapshot – erst einen erstellen."); }, 300);
}

async function initSnapshots() {
  let st;
  snWatchStart();
  try { st = await call("snap_startup"); } catch (e) { return; }
  try { snSideSize((await call("snap_overview")).total); } catch (e) { /* egal */ }
  const libs = st.libs.filter((l) => !l.missing);
  if (!st.libs.length && st.hint) {                // #78: noch kein Ordner überwacht
    const v = await modal({ title: "Snapshots einrichten?",
      html: `<p style="margin:0 0 8px">Es wird noch kein Ordner überwacht. Mit einem überwachten Ordner hält TagStudio den Tag-Zustand deiner Bibliothek fest und zeigt später, was andere Programme (Mixed In Key, beaTunes, Mp3tag …) geändert haben – einzeln rückgängig machbar.</p>
        <label class="check"><input type="checkbox" id="snNoHint"> Nicht mehr fragen (in den Einstellungen wieder einschaltbar)</label>`,
      buttons: [{ label: "Später", value: "later" }, { label: "Ordner wählen …", value: "pick", primary: true }],
      collect: (b, v) => ({ v, no: $("#snNoHint", b).checked }) });
    if (v && v.no) await call("snap_set", "snap_hint", false);
    if (v && v.v === "pick") { setModule("snapshots"); setTimeout(snAddLibrary, 300); }
    return;
  }
  if (!libs.length) return;
  let created = false;
  if (st.ask) {
    const lines = libs.map((l) => {
      const ch = l.changed + l.new + l.removed;
      const parts = [[l.changed, "geändert"], [l.new, "neu"], [l.removed, "entfernt"]].filter(([n]) => n).map(([n, w]) => `${fmtN(n)} ${w}`).join(", ");
      return `<div class="sn-start"><b>${esc(l.name)}</b>: ${l.last ? (ch ? `<span class="warn">${parts}</span> seit „${esc(l.last.label)}“ (${esc(l.last.age)})` : `unverändert seit „${esc(l.last.label)}“ (${esc(l.last.age)})`) : "noch kein Snapshot"}</div>`;
    }).join("");
    const anyCh = libs.some((l) => l.last && l.changed + l.new + l.removed);
    const res = await modal({
      title: "Snapshots", html: `${lines}<p class="muted sm" style="margin:10px 0 0">Änderungen stammen von anderen Programmen oder Speichern ausserhalb von TagStudio.${st.daily ? " Der tägliche automatische Snapshot läuft unabhängig davon im Hintergrund." : ""}</p>
        <label class="check" style="margin-top:8px"><input type="checkbox" id="snNoAsk"> Beim Start nicht mehr fragen (in den Einstellungen wieder einschaltbar)</label>`,
      buttons: [{ label: "Später", value: "later" }, ...(anyCh ? [{ label: "Journal ansehen", value: "journal" }] : []), { label: "Snapshot erstellen", value: "create", primary: !anyCh }],
      collect: (b, v) => ({ v, noask: $("#snNoAsk", b).checked }),
    });
    if (res && res.noask) await call("snap_set", "snap_ask", false);
    if (res && res.v === "journal") {
      const l = libs.find((x) => x.last && x.changed + x.new + x.removed);
      SN.lid = l.id; SN.a = l.last.id; SN.b = "live";
      setModule("snapshots");
      setTimeout(snRun, 300);
    } else if (res && res.v === "create") {
      for (const l of libs) await call("snap_create", l.id, "Beim Start", false, false);
      created = true;
      jobsPoll();
    }
  }
  if (st.daily && !created) {
    const due = libs.filter((l) => l.due);
    for (const l of due) await call("snap_create", l.id, "", true, false);
    if (due.length) jobsPoll();
  }
}

(function bindSnapshots() {
  $("#snAddLib").addEventListener("click", snAddLibrary);
  $$("[data-snappick]").forEach((b) => b.addEventListener("click", () => snPickSpec(b.dataset.snappick)));
  $("#snWatchChip").addEventListener("click", snWatchOpen);
  $("#snCreate").addEventListener("click", () => snCreate());
  $("#snRun").addEventListener("click", snRun);
  $("#snRevert").addEventListener("click", () => snRevert("undo"));
  $("#snBytes").addEventListener("click", () => snRevert("bytes"));
  $("#snPrune").addEventListener("click", async () => {
    const r = await call("snap_prune", SN.lid || null);
    toast(r.removed ? `${r.removed} automatische(r) Snapshot(s) entfernt – ${snMB(r.freed)} frei.` : "Nichts aufzuräumen.");
    snapShow();
  });
  $("#snA").addEventListener("change", (e) => { SN.a = e.target.value; snLoadList(); });
  $("#snB").addEventListener("change", (e) => { SN.b = e.target.value; });
  $("#snLibs").addEventListener("change", async (e) => {
    const a = e.target.closest("[data-lauto]"); if (!a) return;
    const r = await call("snap_update_library", a.dataset.lauto, null, null, a.checked);
    if (!r.ok) return info("Nicht möglich", r.error);
    toast(a.checked ? "Täglicher Snapshot an." : "Für diesen Ordner kein täglicher Snapshot.");
  });
  $("#snLibs").addEventListener("click", async (e) => {
    if (e.target.closest("label.auto")) { e.stopPropagation(); return; }
    const ren = e.target.closest("[data-lren]"), mv = e.target.closest("[data-lmove]");
    if (ren || mv) {
      e.stopPropagation();
      const l = SN.ov.libs.find((x) => x.id === (ren || mv).dataset[ren ? "lren" : "lmove"]);
      let v = null;
      if (ren) {
        v = await modal({ title: "Anzeigename", html: `<div class="frm"><label for="snLname">Name</label><input id="snLname" value="${esc(l.name)}" autofocus></div>`,
          buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }], collect: (b) => $("#snLname", b).value.trim() });
        if (!v) return;
      } else {
        v = await call("pick_path", l.root, true, "");
        if (!v && !S.settings.native) v = await modal({ title: "Ordner ändern", html: `<div class="frm"><label for="snLroot">Neuer Ordner</label><input id="snLroot" value="${esc(l.root)}" autofocus></div><p class="muted sm">Die Snapshots bleiben erhalten; Pfade sind relativ zum Ordner gespeichert.</p>`,
          buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }], collect: (b) => $("#snLroot", b).value.trim() });
        if (!v) return;
      }
      const r = await call("snap_update_library", l.id, ren ? v : null, mv ? v : null, null);
      if (!r.ok) return info("Nicht möglich", r.error);
      snapShow();
      return;
    }
    const un = e.target.closest("[data-unwatch]");
    if (un) {
      e.stopPropagation();
      const l = SN.ov.libs.find((x) => x.id === un.dataset.unwatch);
      if (await dialog({ title: `„${l.name}“ nicht mehr überwachen?`, text: `Alle ${l.count} Snapshot(s) dieses Ordners werden gelöscht (${snMB(l.bytes)}). Die MP3-Dateien bleiben unverändert.`,
        buttons: [{ label: "Abbrechen", value: null }, { label: "Löschen", value: true, primary: true }] })) { await call("snap_remove_library", l.id); SN.lid = null; SN.j = null; snapShow(); }
      return;
    }
    const b = e.target.closest("[data-lib]"); if (!b) return;
    SN.lid = b.dataset.lib; SN.a = null; SN.j = null; $("#snJournal").innerHTML = '<div class="tg-empty">Snapshot wählen und „Journal berechnen“.</div>'; $("#snFilter").innerHTML = "";
    snapShow();
  });
  $("#snSnaps").addEventListener("click", async (e) => {
    const t = e.target.closest("button");
    if (t && t.dataset.pin) { const s = SN.list.snapshots.find((x) => x.id === t.dataset.pin); await call("snap_update", SN.lid, s.id, null, !s.pinned); return snLoadList(); }
    if (t && t.dataset.ren) {
      const s = SN.list.snapshots.find((x) => x.id === t.dataset.ren);
      const v = await modal({ title: "Snapshot umbenennen", html: `<div class="frm"><label for="snRen">Bezeichnung</label><input id="snRen" value="${esc(s.label)}" autofocus></div>`,
        buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }], collect: (b) => $("#snRen", b).value.trim() });
      if (v) { await call("snap_update", SN.lid, s.id, v, null); snLoadList(); }
      return;
    }
    if (t && t.dataset.del) {
      const s = SN.list.snapshots.find((x) => x.id === t.dataset.del);
      if (!(await dialog({ title: "Snapshot löschen?", text: `„${s.label}“ vom ${snTime(s.created)} wird gelöscht.`, buttons: [{ label: "Abbrechen", value: null }, { label: "Löschen", value: true, primary: true }] }))) return;
      const r = await call("snap_delete", SN.lid, s.id);
      toast(`Gelöscht – ${snMB(r.freed)} frei.`);
      return snapShow();
    }
    const row = e.target.closest("[data-snap]");
    if (row) { SN.a = row.dataset.snap; snLoadList(); }
  });
  $("#snFilter").addEventListener("click", (e) => {
    const c = e.target.closest("[data-f]"); if (!c) return;
    SN.filter.has(c.dataset.f) ? SN.filter.delete(c.dataset.f) : SN.filter.add(c.dataset.f);
    snRender();
  });
  $("#snFilter").addEventListener("change", (e) => {
    if (e.target.id === "snProg") { SN.prog = e.target.value; snRender(); }
    else if (e.target.id === "snFkey") { SN.fkey = e.target.value; snRender(); }
  });
  $("#snFilter").addEventListener("click", (e) => { if (e.target.id === "snSelVis") snSelectVisible(); });
  $("#snFilter").addEventListener("input", (e) => { if (e.target.id === "snQ") { SN.q = e.target.value; const pos = e.target.selectionStart; snRender(); const q = $("#snQ"); q.focus(); q.setSelectionRange(pos, pos); } });
  $("#snJournal").addEventListener("click", (e) => {
    const row = e.target.closest(".sn-row"); if (!row) return;
    const p = row.dataset.p, r = SN.j.rows.find((x) => x.p === p);
    if (e.target.closest("[data-cmp]")) { snOpenCompare(p); return; }
    if (e.target.matches("[data-row]")) {
      SN.sel.set(p, e.target.checked ? new Set(r.fields.map((f) => f.key)) : new Set());
      return snRender();
    }
    if (e.target.matches("[data-k]")) {
      const ks = SN.sel.get(p) || new Set();
      e.target.checked ? ks.add(e.target.dataset.k) : ks.delete(e.target.dataset.k);
      SN.sel.set(p, ks);
      return snRender();
    }
    if (e.target.closest(".h") && r.fields.length) { SN.open.has(p) ? SN.open.delete(p) : SN.open.add(p); snRender(); }
  });
})();
