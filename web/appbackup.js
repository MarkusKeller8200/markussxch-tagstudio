"use strict";
// Einstellungen › Cloud › „Sicherung der Programmdaten“ (#402): ZIP in einen Ordner (z. B. OneDrive privat), von Hand
// oder automatisch; Wiederherstellen mit Vorschau und vorheriger Sicherung; ältere Sicherungen nur nach Rückfrage löschen.

const AB_AUTO = { off: "nur von Hand", exit: "beim Beenden", daily: "täglich (beim Start, wenn älter als 24 h)" };

async function stAppBackupRender() {
  const box = $("#stAppBackup"); if (!box) return;
  let o;
  try { o = await call("appbackup_overview"); } catch (e) { box.innerHTML = `<span class="st-missing sm">${esc(String(e.message || e))}</span>`; return; }
  const c = o.cfg, l = o.last || {};
  box.innerHTML = `<h4 class="cs-h">Sicherung der Programmdaten</h4>
    <div class="muted sm">Einstellungen (ohne Zugangsdaten), Playlists, Ideen, Einkäufe, Entdecken, Vorbereiten und Mixe als ZIP-Datei – z. B. in den OneDrive-Ordner. Nie dabei: Zugangsdaten, Snapshots, Caches, Musik.</div>
    <div class="st-row"><span>Ordner</span><div><span class="pl-folder"><input id="abFolder" class="inp sm" value="${esc(c.folder)}" placeholder="${esc(o.suggest)}" spellcheck="false" aria-label="Ordner für die Sicherung" translate="no"><button class="ghost sm" data-abpick>Wählen …</button>${!c.folder && o.suggest ? '<button class="ghost sm" data-absuggest>Vorschlag übernehmen</button>' : ""}</span></div></div>
    <div class="st-row"><span>Automatisch</span><div><select id="abAuto" class="inp sm" aria-label="Automatisch sichern">${Object.entries(AB_AUTO).map(([k, v]) => `<option value="${k}" ${c.auto === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>
      <label class="sm">Behalten <input id="abKeep" class="inp sm" type="number" min="1" max="100" value="${c.keep}" style="width:5em" aria-label="Anzahl Sicherungen behalten"></label>
      <span class="muted sm">ältere werden nur nach Rückfrage gelöscht</span></div></div>
    <div class="fold-acts"><button class="primary sm" data-abrun ${c.folder ? "" : "disabled"}>Jetzt sichern</button>
      <button class="ghost sm" data-abrestore ${o.count ? "" : "disabled"}>Wiederherstellen …</button>
      ${o.surplus ? `<button class="ghost sm" data-absurplus>${fmtN(o.surplus)} ältere Sicherung(en) …</button>` : ""}
      <span class="muted sm" id="abLast">${l.at ? `zuletzt ${esc(l.at.replace("T", " ").slice(0, 16))} · ${fsize(l.size || 0)}` : "noch keine Sicherung"}${o.count ? ` · ${fmtN(o.count)} im Ordner` : ""}</span></div>`;
}

async function appBackupSave() {
  const keep = parseInt($("#abKeep").value, 10);
  try { await call("appbackup_set", { folder: $("#abFolder").value.trim(), auto: $("#abAuto").value, keep: Number.isFinite(keep) ? keep : 10 }); }
  catch (e) { toast(String(e.message || e)); }
  stAppBackupRender();
}

/** Ältere Sicherungen über „behalten“ – Auswahl, löschen nur nach Bestätigung */
async function appBackupSurplusDialog() {
  const s = await call("appbackup_surplus");
  if (!s.files.length) return stAppBackupRender();
  const sel = await modal({ title: "Ältere Sicherungen", wide: true,
    html: `<p style="margin:0 0 6px">Mehr als ${fmtN(s.keep)} Sicherungen im Ordner – diese älteren können weg:</p>
      ${s.files.map((f, i) => `<label class="check sm"><input type="checkbox" data-abx="${i}" checked> <code translate="no">${esc(f.name)}</code> <span class="muted">${fsize(f.size)}</span></label>`).join("")}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Markierte löschen …", value: true, primary: true }],
    collect: (b) => [...b.querySelectorAll("[data-abx]:checked")].map((el) => s.files[+el.dataset.abx].path) });
  if (!sel || !sel.length) return;
  const ok = await dialog({ title: "Sicherungen löschen?", text: `${sel.length} Sicherung(en) endgültig löschen?`,
    buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
  if (!ok) return;
  const r = await call("appbackup_delete", sel);
  toast(`${r.deleted} gelöscht${r.errors.length ? `, ${r.errors.length} Fehler` : ""}.`);
  stAppBackupRender();
}

/** Wiederherstellen: Sicherung wählen → Vorschau → Teile/Gruppen wählen → Auftrag (vorher Sicherung des jetzigen Stands) */
async function appBackupRestoreFlow() {
  const o = await call("appbackup_overview");
  const pick = await modal({ title: "Sicherung wählen", wide: true,
    html: `<div class="ab-list">${o.list.map((f, i) => `<label class="check sm"><input type="radio" name="abPick" value="${i}" ${i === 0 ? "checked" : ""}> <code translate="no">${esc(f.name)}</code> <span class="muted">${fsize(f.size)}${f.online_only ? " · nur online – wird beim Öffnen geladen" : ""}</span></label>`).join("")}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Weiter …", value: true, primary: true }],
    collect: (b) => { const r = $('input[name="abPick"]:checked', b); return r ? o.list[+r.value].path : false; } });
  if (!pick) return;
  let pv;
  try { pv = await call("appbackup_preview", pick); } catch (e) { return info("Wiederherstellen", String(e.message || e)); }
  const m = pv.manifest;
  const partRow = (p) => p.id === "settings"
    ? `<div class="ab-part"><label class="check sm"><input type="checkbox" data-abpart="settings" ${p.files ? "checked" : ""} ${p.files ? "" : "disabled"}> <b>${esc(p.label)}</b></label>
        ${p.settings ? `<div class="ab-groups">${p.settings.groups.map((g) => `<label class="check sm"><input type="checkbox" data-abgrp="${esc(g.id)}" ${g.default ? "checked" : ""}> ${esc(g.label)} <span class="muted">(${fmtN(g.changed)} geändert)</span></label>`).join("")}</div>` : ""}</div>`
    : `<div class="ab-part"><label class="check sm"><input type="checkbox" data-abpart="${esc(p.id)}" ${p.files ? "checked" : ""} ${p.files ? "" : "disabled"}> <b>${esc(p.label)}</b></label>
        <div class="muted sm">${p.files ? `${fmtN(p.files)} Datei(en): ${fmtN(p.changed)} ersetzt, ${fmtN(p.new)} neu, ${fmtN(p.same)} gleich` : "nicht in der Sicherung"}${p.only_here ? ` · ${fmtN(p.only_here)} nur hier (bleiben)` : ""}</div></div>`;
  const sel = await modal({ title: "Wiederherstellen – Vorschau", wide: true,
    html: `<p style="margin:0 0 6px">Sicherung vom ${esc(String(m.created || "").replace("T", " "))} · Rechner <b translate="no">${esc(m.host || "?")}</b> · TagStudio ${esc(m.app_version || "?")}${pv.foreign ? ' · <span class="fold-warn">anderer Rechner – Fenster-, Pfad- und Player-Einstellungen sind nicht vorgewählt</span>' : ""}</p>
      ${pv.parts.map(partRow).join("")}
      ${pv.remap.length ? `<p class="muted sm">Pfade auf Musik werden umgeschrieben: ${pv.remap.map((r) => `<code translate="no">${esc(r.from)}</code> → <code translate="no">${esc(r.to)}</code>`).join(", ")}</p>` : ""}
      <p class="muted sm">Vorher sichert TagStudio den jetzigen Stand („vor-Wiederherstellen“) in denselben Ordner. Danach lädt die Oberfläche neu.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Wiederherstellen", value: true, primary: true }],
    collect: (b) => ({ parts: [...b.querySelectorAll("[data-abpart]:checked")].map((x) => x.dataset.abpart),
                       groups: [...b.querySelectorAll("[data-abgrp]:checked")].map((x) => x.dataset.abgrp) }) });
  if (!sel) return;
  const r = await runTask(call("start_appbackup_restore", pick, sel.parts, sel.groups), "Programmdaten wiederherstellen");
  if (!r) return;
  await info("Wiederherstellen", r.message);
  if (r.reload) location.reload();
}

document.addEventListener("change", (e) => {
  if (e.target.closest("#stAppBackup") && e.target.matches("#abFolder,#abAuto,#abKeep")) appBackupSave();
});

document.addEventListener("click", async (e) => {
  if (!e.target.closest("#stAppBackup")) return;
  if (e.target.closest("[data-abpick]")) {
    const p = await call("pick_path", "", true, $("#abFolder").value.trim());
    if (p) { $("#abFolder").value = p; appBackupSave(); }
  } else if (e.target.closest("[data-absuggest]")) {
    $("#abFolder").value = $("#abFolder").placeholder; appBackupSave();
  } else if (e.target.closest("[data-abrun]")) {
    const r = await runTask(call("start_appbackup"), "Programmdaten sichern");
    stAppBackupRender();
    if (!r) return;
    status(r.message, "info");
    if (r.ab_surplus) await appBackupSurplusDialog();
  } else if (e.target.closest("[data-absurplus]")) {
    await appBackupSurplusDialog();
  } else if (e.target.closest("[data-abrestore]")) {
    await appBackupRestoreFlow();
  }
});
