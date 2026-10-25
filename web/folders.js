"use strict";
// Einstellungen › Speicherort und Ordner – Ordner-Rollen (#310, docs/KONZEPT-ORDNER.md).
// Jede Rolle wird hier genau einmal festgelegt: Modus „Basis“ (Basisordner + Unterordner), „Eigener Ordner“ oder
// (Sicherung/Snapshots) „Programmdaten“. Ändern betrifft nur die Einstellung – Dateien bleiben, wo sie sind.

const FOLDER_MODES = { base: "Basis", custom: "Eigener Ordner", app: "Programmdaten" };

function folderHints(hints) {
  return (hints || []).map((h) => h === "fehlt – anlegen?"
    ? `<button class="link-btn st-missing" data-fcreate>fehlt – anlegen?</button>`
    : `<span class="fold-hint ${/erreichbar|Basisordner|festgelegt/.test(h) ? "st-missing" : "muted"}">${esc(h)}</span>`).join(" ");
}

function folderPathCell(path, exists) {
  return `<code class="fold-path ${path && !exists ? "st-missing" : ""}" title="${esc(path || "")}">${esc(path || "–")}</code>`;
}

/** Ganze Karte „Speicherort und Ordner“ zeichnen (Aufruf aus settings.js) */
async function stFoldersRender() {
  const box = $("#stFolders"); if (!box) return;
  let f;
  try { f = await call("folders_get"); } catch (e) { box.innerHTML = `<span class="st-missing">${esc(String(e.message || e))}</span>`; return; }
  FOLDERS.data = f;
  const modeTxt = (x) => `${esc(FOLDER_MODES[x.mode] || x.mode)}${x.mode === "base" && x.sub !== (x.default_sub || "01_Library") ? ` (${esc(x.sub)})` : ""}`;
  const roleRow = (r) => `<tr data-frole="${esc(r.id)}"><th scope="row" title="${esc(r.desc)}">${esc(r.label)}</th>
      <td>${folderPathCell(r.path, r.exists)} ${folderHints(r.hints)}<div class="muted sm">${esc(r.desc)}</div>
      <div class="fold-acts"><span class="fold-mode">${modeTxt(r)}</span><button class="ghost sm" data-fchange>Ändern …</button><button class="ghost sm" data-fopen ${r.path ? "" : "disabled"}>Öffnen</button>${r.id === "archive" ? '<button class="ghost sm" data-farchlist>Aussortierte …</button>' : ""}</div></td></tr>`;
  const libRow = (l, i) => `<tr data-flib="${esc(l.id)}">${i === 0 ? `<th scope="row" rowspan="${f.libraries.length + 1}">Bibliotheken</th>` : ""}
      <td><label class="check fold-lib"><input type="checkbox" data-factive ${l.active ? "checked" : ""} ${l.main ? "disabled" : ""} title="Aktiv: wird in Abgleichen berücksichtigt"> <b>${esc(l.name)}</b></label>${l.main ? ' <span class="plg-tag">Hauptbibliothek</span>' : `<button class="link-btn sm" data-fmain>als Hauptbibliothek</button>`}
        <div>${folderPathCell(l.path, l.exists)} ${folderHints(l.hints)}</div>
        <div class="fold-acts"><span class="fold-mode">${modeTxt(l)}</span><button class="ghost sm" data-flibchange>Ändern …</button><button class="ghost sm" data-fopen ${l.path ? "" : "disabled"}>Öffnen</button><button class="ghost sm" data-flibremove ${l.main && f.libraries.length > 1 ? "disabled" : ""}>Entfernen</button></div></td></tr>`;
  const roles = f.roles;
  const inbox = roles.filter((r) => r.id === "inbox"), rest = roles.filter((r) => r.id !== "inbox");
  box.innerHTML = `${f.review.length ? `<div class="fold-review"><span>Wir haben ${fmtN(f.review.length)} verschiedene Bibliotheks-Ordner gefunden – bitte festlegen, welche bleiben und welche die Hauptbibliothek ist.</span><button class="primary sm" data-freview>Übersicht …</button></div>` : ""}
    <div class="st-row"><span>Basisordner</span><div><div class="pl-folder">${folderPathCell(f.base, f.base_exists)}<button class="ghost sm" data-fbase>Ändern …</button><button class="ghost sm" data-fopenbase ${f.base ? "" : "disabled"}>Öffnen</button><button class="ghost sm" data-fstruct ${f.base ? "" : "disabled"}>Struktur anlegen …</button></div>
      <div class="muted sm">${f.base ? "Rollen im Modus „Basis“ liegen hier; jede Ordnerauswahl beginnt hier." : "Kein Basisordner – alle Rollen sind eigene Ordner. Leere Rollen fragen beim ersten Gebrauch nach."}</div></div></div>
    <div class="fx-table fold-table"><table><thead><tr><th>Rolle</th><th>Ordner</th></tr></thead><tbody>
      ${inbox.map(roleRow).join("")}
      ${f.libraries.map(libRow).join("")}
      <tr class="fold-add">${f.libraries.length ? "" : '<th scope="row">Bibliotheken</th>'}<td><button class="ghost sm" data-flibadd>+ Bibliothek hinzufügen …</button></td></tr>
      ${rest.map(roleRow).join("")}
    </tbody></table></div>
    <p class="muted sm">„Ändern …“ stellt nur die Einstellung um – vorhandene Dateien bleiben, wo sie sind. Fremde DJ-Programme werden nie verändert.</p>`;
}

const FOLDERS = { data: null };

/** Dialog: Rolle oder Bibliothek umstellen (Basis / eigener Ordner / Programmdaten) */
async function folderChangeDialog({ title, mode, sub, path, base, app, defaultSub, note = "", name = null }) {
  const modeIn = (v, label, extra) => `<label class="wiz-opt"><input type="radio" name="fMode" value="${v}" ${mode === v ? "checked" : ""}><span><b>${esc(label)}</b>${extra}</span></label>`;
  return modal({ title, wide: true,
    html: `${name !== null ? `<div class="frm"><label for="fName">Name</label><input id="fName" class="inp" value="${esc(name)}" maxlength="60"></div>` : ""}
      <div class="wiz-opts">
      ${modeIn("base", "Im Basisordner", `<span class="muted sm">${base ? esc(base) + "\\" : "Kein Basisordner festgelegt – "}</span><input id="fSub" class="inp" value="${esc(sub || defaultSub)}" spellcheck="false" aria-label="Unterordner">`)}
      ${modeIn("custom", "Eigener Ordner", `<span class="pl-folder"><input id="fPath" class="inp" value="${esc(path || "")}" spellcheck="false" aria-label="Eigener Ordner" placeholder="z. B. E:\\Musik"><button class="ghost sm" data-fpick>Wählen …</button></span>`)}
      ${app ? modeIn("app", "Programmdaten von TagStudio", '<span class="muted sm">Wie vor Version 4.10 – im Benutzerordner unter TagStudio.</span>') : ""}
      </div><p class="muted sm">Nur die Einstellung ändert sich – Dateien bleiben, wo sie sind.${note ? " " + esc(note) : ""}</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (body) => {
      body.addEventListener("click", async (e) => {
        if (!e.target.closest("[data-fpick]")) return;
        const inp = $("#fPath", body);
        const p = await call("pick_path", "", true, inp.value.trim());
        if (p) { inp.value = p; $('input[name="fMode"][value="custom"]', body).checked = true; }
      });
      body.addEventListener("focusin", (e) => {
        const r = e.target.id === "fSub" ? "base" : e.target.id === "fPath" ? "custom" : null;
        if (r) $(`input[name="fMode"][value="${r}"]`, body).checked = true;
      });
    },
    collect: (body) => {
      const m = ($('input[name="fMode"]:checked', body) || {}).value || mode;
      const value = m === "base" ? $("#fSub", body).value.trim() : m === "custom" ? $("#fPath", body).value.trim() : "";
      if (m === "custom" && !value) { toast("Bitte einen Ordner wählen."); return false; }
      return { mode: m, value, name: name !== null ? $("#fName", body).value.trim() : null };
    } });
}

/** Übersicht „Diese Ordner haben wir gefunden“ (einmalig nach dem Update, #310) */
async function foldersReviewDialog() {
  const f = FOLDERS.data && FOLDERS.data.review.length ? FOLDERS.data : await call("folders_get");
  if (!f.review.length) return false;
  const libs = Object.fromEntries(f.libraries.map((l) => [l.id, l]));
  const main = (f.libraries.find((l) => l.main) || {}).id;
  const res = await modal({ title: "Diese Ordner haben wir gefunden", wide: true,
    html: `<p style="margin:0 0 8px">Bisher war die Bibliothek an mehreren Stellen eingetragen. Ab jetzt gibt es eine Liste der Bibliotheken – bitte festlegen, welche bleiben, welche aktiv sind (werden in Käufe, Playlists und Entdecken abgeglichen) und welche die <b>Hauptbibliothek</b> ist (Startordner des Taggers, Ziel von Vorbereiten). Es wird nichts verschoben oder gelöscht.</p>
      <div class="fx-table"><table><thead><tr><th>Behalten</th><th>Aktiv</th><th>Haupt</th><th>Ordner</th><th>Eingetragen bei</th></tr></thead><tbody>
      ${f.review.map((c) => { const l = libs[c.id] || {}; return `<tr data-rid="${esc(c.id)}"><td><input type="checkbox" data-rkeep checked aria-label="Behalten"></td><td><input type="checkbox" data-ractive ${l.active !== false ? "checked" : ""} aria-label="Aktiv"></td><td><input type="radio" name="rMain" value="${esc(c.id)}" ${c.id === main ? "checked" : ""} aria-label="Hauptbibliothek"></td>
        <td>${folderPathCell(c.path, true)}</td><td class="muted sm">${esc(c.found.join(", "))}</td></tr>`; }).join("")}
      </tbody></table></div>`,
    buttons: [{ label: "Später", value: null }, { label: "Übernehmen", value: true, primary: true }],
    collect: (body) => {
      const items = $$("tr[data-rid]", body).map((tr) => ({ id: tr.dataset.rid, keep: $("[data-rkeep]", tr).checked, active: $("[data-ractive]", tr).checked }));
      const m = ($('input[name="rMain"]:checked', body) || {}).value || "";
      if (!items.some((x) => x.keep)) { toast("Mindestens eine Bibliothek behalten."); return false; }
      if (items.some((x) => x.id === m && !x.keep)) { toast("Die Hauptbibliothek muss behalten werden."); return false; }
      return { items, main: m };
    } });
  if (!res) return false;
  try { FOLDERS.data = await call("folders_review_apply", res); toast("Bibliotheken festgelegt."); } catch (e) { toast(String(e.message || e)); }
  stFoldersRender();
  return true;
}

/** Beim Start: offene Übersicht einmal zeigen */
async function foldersStartup() {
  try { FOLDERS.data = await call("folders_get"); } catch (e) { return; }
  if (FOLDERS.data.review.length) foldersReviewDialog();
}

(function bindFolderRoles() {
  const err = (e) => toast(String(e.message || e));
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-fchange],[data-fopen],[data-fopenbase],[data-fbase],[data-fstruct],[data-flibadd],[data-flibchange],[data-flibremove],[data-fmain],[data-fcreate],[data-freview],[data-farchlist]");
    if (!t || !t.closest("#stFolders")) return;
    const f = FOLDERS.data || await call("folders_get");
    const row = t.closest("tr");
    const role = row && row.dataset.frole ? f.roles.find((r) => r.id === row.dataset.frole) : null;
    const lib = row && row.dataset.flib ? f.libraries.find((l) => l.id === row.dataset.flib) : null;
    try {
      if (t.dataset.freview !== undefined) return void foldersReviewDialog();
      if (t.dataset.farchlist !== undefined) return void archiveRestoreDialog();
      if (t.dataset.fopenbase !== undefined) return void call("open_folder", f.base);
      if (t.dataset.fopen !== undefined) return void call("open_folder", (role || lib).path);
      if (t.dataset.fcreate !== undefined) {
        await call("folders_create", [role ? role.id : "lib:" + lib.id]);
        toast("Ordner angelegt."); return void stFoldersRender();
      }
      if (t.dataset.fbase !== undefined) {
        let p = await call("pick_path", "", true, f.base || "");
        if (!p) return;
        const follow = f.roles.filter((r) => r.mode === "base").map((r) => r.label);
        if (f.libraries.some((l) => l.mode === "base")) follow.push("Bibliotheken im Basisordner");
        if (f.base && !(await dialog({ title: "Basisordner ändern", text: `Neuer Basisordner: ${p}\n\nDiese Rollen folgen: ${follow.join(", ") || "keine"}.\nNur die Einstellung ändert sich – die Dateien im bisherigen Basisordner bleiben, wo sie sind. Weiter?`,
          buttons: [{ label: "Abbrechen", value: null }, { label: "Ändern", value: true, primary: true }] }))) return;
        await call("folders_set_base", p, false);
        toast("Basisordner geändert."); return void stFoldersRender();
      }
      if (t.dataset.fstruct !== undefined) {
        const subs = f.structure.map((x) => x.sub.replace(/\//g, "\\"));
        if (!(await dialog({ title: "Ordnerstruktur anlegen", text: `In ${f.base} werden die fehlenden Ordner angelegt: ${subs.join(", ")}. Vorhandene bleiben, es wird nichts verschoben. Weiter?`,
          buttons: [{ label: "Abbrechen", value: null }, { label: "Anlegen", value: true, primary: true }] }))) return;
        const r = await call("folders_create");
        toast(r.created.length ? `${fmtN(r.created.length)} Ordner angelegt.` : "Alle Ordner sind schon vorhanden.");
        if (r.errors.length) info("Nicht angelegt", r.errors.join("\n"));
        return void stFoldersRender();
      }
      if (t.dataset.fchange !== undefined && role) {
        const note = role.id === "snapshots" ? "Der bisherige Snapshot-Speicher bleibt am alten Ort; am neuen Ort beginnt ein leerer Speicher (oder ein dort vorhandener wird benutzt). Mitnehmen: Snapshots › Speicherort › Verschieben."
          : role.id === "playlists" ? "Alle Playlists werden im neuen Ordner neu geschrieben." : "";
        const r = await folderChangeDialog({ title: `Ordner „${role.label}“`, mode: role.mode, sub: role.sub, path: role.mode === "custom" ? role.path : "", base: f.base, app: role.app, defaultSub: role.default_sub, note });
        if (!r) return;
        await call("folders_set_role", role.id, r.mode, r.value);
        toast(`Ordner „${role.label}“ geändert.`); return void stFoldersRender();
      }
      if (t.dataset.flibadd !== undefined) {
        const r = await folderChangeDialog({ title: "Bibliothek hinzufügen", mode: "custom", sub: "01_Library", path: "", base: f.base, app: false, defaultSub: "01_Library", name: f.libraries.length ? "" : "Haupt" });
        if (!r) return;
        await call("folders_lib_add", r.name || "", r.mode, r.value, true);
        toast("Bibliothek hinzugefügt."); return void stFoldersRender();
      }
      if (t.dataset.flibchange !== undefined && lib) {
        const r = await folderChangeDialog({ title: `Bibliothek „${lib.name}“`, mode: lib.mode, sub: lib.sub, path: lib.mode === "custom" ? lib.path : "", base: f.base, app: false, defaultSub: "01_Library", name: lib.name,
          note: lib.main ? "Engine DJ, Lexicon, Rekordbox, Serato und VirtualDJ merken sich Pfade – zeigt die Hauptbibliothek auf andere Dateien, dort „Fehlende Dateien suchen“ bzw. „Relocate“ verwenden." : "" });
        if (!r) return;
        await call("folders_lib_update", lib.id, { name: r.name, mode: r.mode, value: r.value });
        toast("Bibliothek geändert."); return void stFoldersRender();
      }
      if (t.dataset.fmain !== undefined && lib) {
        await call("folders_lib_update", lib.id, { main: true });
        toast(`„${lib.name}“ ist jetzt die Hauptbibliothek.`); return void stFoldersRender();
      }
      if (t.dataset.flibremove !== undefined && lib) {
        if (!(await dialog({ title: "Bibliothek entfernen", text: `„${lib.name}“ (${lib.path}) aus der Liste der Bibliotheken entfernen? Die Dateien bleiben unverändert.`,
          buttons: [{ label: "Abbrechen", value: null }, { label: "Entfernen", value: true, primary: true }] }))) return;
        await call("folders_lib_remove", lib.id);
        toast("Bibliothek entfernt."); return void stFoldersRender();
      }
    } catch (x) { err(x); stFoldersRender(); }
  });
  document.addEventListener("change", async (e) => {
    const c = e.target.closest("#stFolders [data-factive]"); if (!c) return;
    try { await call("folders_lib_update", c.closest("tr").dataset.flib, { active: c.checked }); } catch (x) { err(x); }
    stFoldersRender();
  });
})();
