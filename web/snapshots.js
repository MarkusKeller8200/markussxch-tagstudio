/* MarKusSXCH TagStudio – Seite „Snapshots“: überwachte Ordner, Snapshots, Änderungsjournal, Zurücksetzen
   (#53, #54, #61). Logik in snapshots.py / session.py; Konzept: docs/KONZEPT-SNAPSHOTS.md */
"use strict";

const SN = { ov: null, lid: null, list: null, a: null, b: "live", j: null, filter: new Set(), q: "", open: new Set(),
  sel: new Map(), done: new Set() };
const SN_STATUS = { changed: "geändert", rewrite: "umgeschrieben", renamed: "umbenannt", audio: "Audio", new: "neu", removed: "entfernt" };

const snMB = (b) => (b < 1048576 ? `${Math.max(0, Math.round(b / 1024))} KB` : b < 1073741824 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${(b / 1073741824).toFixed(2).replace(".", ",")} GB`);
const snTime = (c) => (c ? c.slice(8, 10) + "." + c.slice(5, 7) + "." + c.slice(0, 4) + " " + c.slice(11, 16) : "");

function snSideSize(total) { const el = $("#snapSize"); if (el) el.textContent = total ? snMB(total) : ""; }

async function snapShow() {
  SN.ov = await call("snap_overview");
  snSideSize(SN.ov.total);
  if (!SN.ov.libs.some((l) => l.id === SN.lid)) SN.lid = SN.ov.libs.length ? SN.ov.libs[0].id : null;
  $("#snInfo").textContent = `Speicher: ${SN.ov.dir} · gesamt ${snMB(SN.ov.total)}${SN.ov.readonly ? " · NUR LESEN (aus neuerer TagStudio-Version)" : ""}`;
  $("#snLibs").innerHTML = SN.ov.libs.length ? SN.ov.libs.map((l) => `<div class="sn-lib${l.id === SN.lid ? " cur" : ""}${l.exists ? "" : " missing"}" data-lib="${esc(l.id)}" role="button" tabindex="0">
      <span class="n">${esc(l.name)}</span><span class="z">${snMB(l.bytes)}</span>
      <span class="r" title="${esc(l.root)}">${l.exists ? esc(l.root) : "nicht erreichbar: " + esc(l.root)}</span><span class="z"><button class="x" data-unwatch="${esc(l.id)}" title="Nicht mehr überwachen (Snapshots löschen)">✕</button></span>
      <span class="s">${l.count} Snapshot(s)${l.last ? " · zuletzt " + esc(l.last.age) : ""}</span></div>`).join("")
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
  SN.j = res; SN.sel = new Map(); SN.done = new Set(); SN.open = new Set(); SN.filter = new Set();
  const st = SN.j.counts;
  if (st.changed) SN.filter.add("changed");
  snRender();
  if (res.errors && res.errors.length) toast(`${res.errors.length} Datei(en) nicht lesbar.`);
}

function snVisible() {
  const q = SN.q.trim().toLowerCase();
  return SN.j.rows.filter((r) => (!SN.filter.size || SN.filter.has(r.status) || (SN.filter.has("audio") && r.audio))
    && (!q || r.p.toLowerCase().includes(q) || r.fields.some((f) => (f.label + " " + f.key + " " + f.old + " " + f.new).toLowerCase().includes(q))));
}

function snRender() {
  const j = SN.j;
  if (!j) return;
  const c = j.counts, keys = ["changed", "renamed", "audio", "new", "removed", "rewrite"];
  $("#snFilter").innerHTML = keys.filter((k) => c[k]).map((k) => `<button class="sn-chip${SN.filter.has(k) ? " on" : ""}" data-f="${k}">${SN_STATUS[k]} ${fmtN(c[k])}</button>`).join("")
    + `<input id="snQ" placeholder="Titel, Feld oder Wert suchen …" value="${esc(SN.q)}" aria-label="Journal durchsuchen">`;
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
          <span class="sn-st ${r.status}">${SN_STATUS[r.status]}${r.audio && r.status !== "audio" ? " · Audio" : ""}</span>
          <span class="p" title="${esc(r.p)}"><span class="d">${esc(dir)}</span>${esc(r.p.slice(dir.length))}</span>
          <span class="sum">${esc(sum)} ${r.fields.length ? (open ? "▾" : "▸") : ""}</span></div>
        ${open && r.fields.length ? `<div class="sn-fields">${r.fields.map((f) => `<div class="sn-f"><input type="checkbox" data-k="${esc(f.key)}" ${ks && ks.has(f.key) ? "checked" : ""} aria-label="${esc(f.label)} zurücksetzen">
          <span class="k">${srcBadge(f.src)}${esc(f.label)}</span><span class="o${f.state === "removed" ? "" : ""}" title="${esc(f.old)}">${f.state === "added" ? "<i>– fehlte –</i>" : esc(f.old)}</span><span class="muted">→</span><span class="n" title="${esc(f.new)}">${f.state === "removed" ? "<i>– entfernt –</i>" : esc(f.new)}</span></div>`).join("")}</div>` : ""}
      </div>`;
    }).join("") + (rows.length > 1500 ? `<div class="tg-empty">… ${fmtN(rows.length - 1500)} weitere – Filter benutzen.</div>` : "");
  snSelInfo();
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
async function initSnapshots() {
  let st;
  try { st = await call("snap_startup"); } catch (e) { return; }
  try { snSideSize((await call("snap_overview")).total); } catch (e) { /* egal */ }
  const libs = st.libs.filter((l) => !l.missing);
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
  $("#snLibs").addEventListener("click", async (e) => {
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
  $("#snFilter").addEventListener("input", (e) => { if (e.target.id === "snQ") { SN.q = e.target.value; const pos = e.target.selectionStart; snRender(); const q = $("#snQ"); q.focus(); q.setSelectionRange(pos, pos); } });
  $("#snJournal").addEventListener("click", (e) => {
    const row = e.target.closest(".sn-row"); if (!row) return;
    const p = row.dataset.p, r = SN.j.rows.find((x) => x.p === p);
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
