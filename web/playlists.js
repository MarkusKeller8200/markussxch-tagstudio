/* MarKusSXCH TagStudio – Seite „Playlists“ (#267) und Anbindung an Tagger (#268) und DJ-Set (#269).
   Speicher, Archiv und Playlist-Ordner (M3U8) in playlists.py / session_playlists.py. */
"use strict";

const PLS = { play: null, st: null, sel: new Set(), anchor: null, drag: null, busy: false, open: new Set(), closed: new Set(), archOpen: false, q: "" };
const PLS_ICON = { manual: "♫", djset: "◎", smart: "⚡", import: "⇣", queue: "⏭", wish: "☆" };
const PLS_KIND = { manual: "Playlist", djset: "DJ-Set", smart: "Smartlist", import: "Import", queue: "Warteschlange", wish: "Wunschliste" };

async function playlistsShow() {
  try {
    if (!PLS.smart) await plsSmartInfo().catch(() => {});                  // Feldnamen für die Regel-Zusammenfassung (#272)
    call("pl_push_targets").then((r) => { PLS.push = r.targets || []; }).catch(() => {});   // #273: „Senden an ›“
    const st = await call("pl_state", PLS.st ? PLS.st.sel : ""); plsApply(st); plsSmartAuto(st);
  } catch (e) { toast(String(e.message || e)); }
}

function plsApply(st) {
  if (!st) return;
  if (PLS.st && PLS.st.sel !== st.sel) { PLS.sel = new Set(); PLS.anchor = null; }
  PLS.st = st;
  if (st.pl) PLS.sel = new Set([...PLS.sel].filter((k) => k < st.pl.items.length));
  if (st.message) toast(st.message);
  if (st.errors && st.errors.length) info("Hinweise", st.errors.join("\n"));
  plsSideCount(st);
  if (S.module !== "playlists") return;
  plsRenderTree();
  plsRenderHead();
  plsRenderList();
}

async function plsCall(name, ...args) {
  if (PLS.busy) return null;
  PLS.busy = true;
  try { const st = await call(name, ...args); plsApply(st); return st; }
  catch (e) { toast(String(e.message || e)); return null; }
  finally { PLS.busy = false; }
}

function plsSideCount(st) {
  const el = $("#plsCount"); if (!el || !st) return;
  el.textContent = st.playlists.length ? String(st.playlists.length) : "";
  el.title = st.external ? `${st.external} Änderung(en) im Playlist-Ordner` : `${st.playlists.length} Playlists`;
  el.classList.toggle("warn", !!st.external);
}

function plsCur() { return PLS.st && PLS.st.pl; }
/** Archivierte Playlists und Smartlists (#272) lassen sich nicht von Hand ändern */
function plsFixed(pl) { return !!pl && (!!pl.archived || pl.kind === "smart"); }
function plsMeta(id) { return PLS.st && (PLS.st.playlists.find((p) => p.id === id) || PLS.st.archived.find((p) => p.id === id)); }
function plsLabel(p) { return p.folder ? `${p.folder} / ${p.name}` : p.name; }

// ---------------------------------------------------------------- Baum
function plsRenderTree() {
  const st = PLS.st, box = $("#plsTree");
  const q = PLS.q.trim().toLowerCase();
  const match = (p) => !q || plsLabel(p).toLowerCase().includes(q);
  const row = (p, depth) => `<div class="pls-node pls-pl${p.id === st.sel ? " on" : ""}" role="treeitem" aria-selected="${p.id === st.sel}" data-pl="${esc(p.id)}" draggable="true" style="padding-left:${8 + 16 * depth}px" title="${esc(plsLabel(p))} · ${PLS_KIND[p.kind] || ""}">
      <span class="pls-ico" aria-hidden="true"${p.color ? ` style="color:${esc(p.color)}"` : ""}>${PLS_ICON[p.kind] || "♫"}</span><span class="pls-nm ellipsis" translate="no">${esc(p.name)}</span><span class="pls-n">${fmtN(p.count)}</span></div>`;
  let html = "";
  const rec = st.recent.map((id) => st.playlists.find((p) => p.id === id)).filter(Boolean).slice(0, 5);
  if (rec.length && !q) html += `<div class="pls-sec">Zuletzt benutzt</div>${rec.map((p) => row(p, 0)).join("")}<div class="pls-sec">Alle</div>`;
  const kids = (f) => st.folders.filter((x) => x.split("/").length === (f ? f.split("/").length + 1 : 1) && (!f || x.startsWith(f + "/")));
  const inFolder = (f) => st.playlists.filter((p) => p.folder === f && match(p));
  const hasMatch = (f) => st.playlists.some((p) => (p.folder === f || p.folder.startsWith(f + "/")) && match(p));
  const walk = (f, depth) => {
    let h = "";
    for (const sub of kids(f)) {
      if (q && !hasMatch(sub)) continue;
      const open = q || !PLS.closed.has(sub);
      const n = st.playlists.filter((p) => p.folder === sub || p.folder.startsWith(sub + "/")).length;
      h += `<div class="pls-node pls-fold" role="treeitem" aria-expanded="${!!open}" data-folder="${esc(sub)}" style="padding-left:${8 + 16 * depth}px">
        <span class="pls-car" aria-hidden="true">${open ? "▾" : "▸"}</span><span class="pls-ico" aria-hidden="true">📁</span><span class="pls-nm ellipsis" translate="no">${esc(sub.split("/").pop())}</span><span class="pls-n">${fmtN(n)}</span></div>`;
      if (open) h += walk(sub, depth + 1);
    }
    return h + inFolder(f).map((p) => row(p, depth)).join("");
  };
  html += walk("", 0);
  if (!st.playlists.length && !q) html += `<div class="tg-empty sm">Noch keine Playlists. „+ Playlist“ legt eine an – oder im Tagger Titel markieren und per Rechtsklick „Zur Playlist hinzufügen …“.</div>`;
  if (st.archived.length) {
    html += `<div class="pls-node pls-arch" role="treeitem" aria-expanded="${PLS.archOpen}" data-arch="1"><span class="pls-car" aria-hidden="true">${PLS.archOpen ? "▾" : "▸"}</span><span class="pls-ico" aria-hidden="true">🗄</span><span class="pls-nm">Archiv</span><span class="pls-n">${fmtN(st.archived.length)}</span></div>`;
    if (PLS.archOpen) html += st.archived.filter(match).map((p) => row(p, 1).replace("pls-node pls-pl", "pls-node pls-pl gone")).join("");
  }
  box.innerHTML = html;
  $("#plsUndo").disabled = !st.can_undo;
  $("#plsUndo").title = st.can_undo ? `Rückgängig: ${st.undo} (Strg+Z)` : "Rückgängig (Strg+Z)";
  $("#plsRedo").disabled = !st.can_redo;
  $("#plsRedo").title = st.can_redo ? `Wiederholen: ${st.redo} (Strg+Y)` : "Wiederholen (Strg+Y)";
  const ext = $("#plsExt");
  ext.hidden = !st.external;
  ext.textContent = `${st.external} Änderung(en) im Ordner …`;
  $("#plsFolderBtn").disabled = !st.mirror;
  $("#plsFolderBtn").title = st.mirror ? `Playlist-Ordner öffnen: ${st.mirror}` : "Kein Playlist-Ordner – Basisordner unter Einstellungen › Speicherort und Ordner festlegen";
}

// ---------------------------------------------------------------- Kopf
function plsRenderHead() {
  const pl = plsCur(), el = $("#plsHead");
  if (!pl) { el.innerHTML = `<div class="muted">Links eine Playlist wählen oder eine neue anlegen.</div>`; return; }
  const loaded = PLS.st.tagger;
  const info = [`${fmtN(pl.count)} Titel`, pl.duration ? djDur(pl.duration) : "", pl.missing ? `${fmtN(pl.missing)} fehlen` : "",
    pl.count && pl.loaded < pl.count - pl.missing ? `${fmtN(pl.loaded)} im Tagger geladen` : "",
    ...Object.entries(pl.pushed || {}).map(([k, v]) => `gesendet an ${((PLS.push || []).find((t) => t.id === k) || { name: k }).name} ${new Date(v.at * 1000).toLocaleDateString()}`)].filter(Boolean).join(" · ");
  if (pl.archived) {
    el.innerHTML = `<div class="pls-h"><div class="grow"><h3 translate="no">${esc(pl.name)}</h3><div class="muted sm">${esc(pl.folder || "")}${pl.folder ? " · " : ""}${info}</div></div></div>
      <div class="hint pls-archived"><div>Archiviert am ${esc(new Date(pl.archived * 1000).toLocaleString())}.</div>${pl.file ? `<div class="muted sm">Datei im Archiv:</div><div class="sm" translate="no">${esc(pl.file)}</div>` : ""}
      <div class="pls-acts"><button class="primary sm" data-plsa="restore">Zurückholen</button><button class="ghost sm" data-plsa="delete">Endgültig löschen …</button></div></div>`;
    return;
  }
  el.innerHTML = `<div class="pls-h"><div class="grow"><h3><span class="pls-ico"${pl.color ? ` style="color:${esc(pl.color)}"` : ""} aria-hidden="true">${PLS_ICON[pl.kind] || "♫"}</span> <span translate="no">${esc(pl.name)}</span>${pl.djset ? ' <span class="chip sm" title="Wird gerade im DJ-Set bearbeitet">im DJ-Set</span>' : ""}</h3>
      <div class="muted sm">${pl.folder ? `<span translate="no">${esc(pl.folder)}</span> · ` : ""}${esc(PLS_KIND[pl.kind] || "")} · ${info}${pl.note ? ` · <span translate="no">${esc(pl.note)}</span>` : ""}</div>
      ${pl.kind === "smart" ? `<div class="sm pls-rules" id="plsRules">${plsSmartSummary(pl.rules)}${pl.refreshed ? ` <span class="muted">· aktualisiert ${esc(new Date(pl.refreshed * 1000).toLocaleString())}</span>` : ""}</div>` : ""}</div>
    <div class="pls-acts">
      ${pl.kind === "smart" ? `<button class="ghost" data-plsa="smartrefresh" title="Smartlist jetzt neu bilden (#272)">↻ Aktualisieren</button><button class="ghost" data-plsa="smartedit" title="Datenbasis, Regeln, Sortierung und Höchstzahl ändern">Regeln …</button>` : ""}
      ${PLS.play && PLS.play.id === pl.id && plsPlayActive() ? '<span class="chip sm on" title="Der Player folgt dieser Playlist (⏭, Titelende)">▶ läuft</span>' : ""}
      <button class="primary" data-plsa="play" ${pl.count > pl.missing ? "" : "disabled"} title="Ab dem markierten Titel abspielen – der Player folgt der Playlist, auch auf anderen Seiten (#270)">▶ Abspielen</button>
      <button class="ghost" data-plsa="tagger" ${pl.count ? "" : "disabled"} title="Titel der Playlist in den Tagger laden">Im Tagger öffnen</button>
      <button class="ghost" data-plsa="djset" ${pl.count ? "" : "disabled"} title="Playlist ins DJ-Set laden und dort optimieren">Im DJ-Set öffnen</button>
      ${pl.kind === "smart" ? "" : `<button class="ghost" data-plsa="addtag" ${loaded ? "" : "disabled"} title="Im Tagger markierte Titel ans Ende">+ Markierte aus dem Tagger</button>`}
      <button class="ghost" data-plsa="more" aria-haspopup="menu">Mehr ▾</button></div></div>`;
}

// ---------------------------------------------------------------- Titelliste
function plsRenderList() {
  const pl = plsCur(), list = $("#plsList");
  if (!pl) { list.innerHTML = ""; return; }
  if (!pl.items.length) {
    list.innerHTML = pl.kind === "smart"
      ? `<div class="tg-empty">Keine Titel erfüllen die Regeln – „Regeln …“ anpassen oder „↻ Aktualisieren“.</div>`
      : `<div class="tg-empty">Noch keine Titel. Im Tagger Titel markieren und „+ Markierte aus dem Tagger“ wählen – oder dort per Rechtsklick „Zur Playlist hinzufügen …“.</div>`;
    return;
  }
  const head = `<div class="pls-row pls-hd" aria-hidden="true"><span></span><span class="n">#</span><span>Titel</span><span class="r">BPM</span><span>Tonart</span><span class="r">Länge</span><span>Bewertung</span><span>Ordner</span></div>`;
  list.innerHTML = head + pl.items.map((r) => {
    const t = r.artist && r.title ? `${r.artist} – ${r.title}` : (r.title || r.artist || r.name);
    const miss = r.ref ? ' <span class="chip sm" title="Nur Künstler und Titel, keine Datei – „Mit Bibliothek abgleichen …“ sucht sie">ohne Datei</span>'
      + (r.url ? ` <a href="#" class="pls-link" data-url="${esc(r.url)}" title="Bei der Quelle öffnen (${esc(r.url.replace(/^https:\/\/(www\.|open\.)?/, "").split("/")[0])})">↗</a>` : "")
      : r.missing ? ` <span class="muted sm">${r.in_archive ? "(im Archiv)" : "(fehlt)"}</span>` : "";
    const bpm = r.bpm ? (Math.round(r.bpm * 10) / 10).toString().replace(".", ",") : "–";
    return `<div class="pls-row${PLS.sel.has(r.k) ? " sel" : ""}${r.missing ? " missing" : ""}${r.lock ? " locked" : ""}" data-k="${r.k}" draggable="${!pl.archived}" role="option" aria-selected="${PLS.sel.has(r.k)}" title="${esc(r.in_archive || r.path)}">
      <span class="h" aria-hidden="true">${plsFixed(pl) ? "" : "⋮⋮"}</span><span class="n">${r.k + 1}</span>
      <span class="t ellipsis"><span translate="no">${esc(t)}</span>${r.dup ? ' <span class="chip sm" title="Titel kommt mehrmals vor">doppelt</span>' : ""}${r.lock ? ' <span title="Im DJ-Set gesperrt">🔒</span>' : ""}${miss}${r.note ? ` <span class="muted sm" translate="no" title="Notiz">· ${esc(r.note)}</span>` : ""}</span>
      <span class="bp">${bpm}</span><span class="kk">${r.key ? keyBadge(r.key) : '<span class="mx">–</span>'}</span>
      <span class="d muted sm">${r.dur ? fmtTime(r.dur) : ""}</span><span class="rt">${r.rating ? "★".repeat(r.rating) : ""}</span>
      <span class="dir muted sm ellipsis" translate="no">${esc(r.dir)}</span></div>`;
  }).join("");
  const sel = list.querySelector(".pls-row.sel"); if (sel) sel.scrollIntoView({ block: "nearest" });
}

function plsRow(k) { const pl = plsCur(); return pl && pl.items[k]; }
function plsSelList() { return [...PLS.sel].sort((a, b) => a - b); }

function plsSelect(k, e, src = "key") {
  const pl = plsCur(); if (!pl || !pl.items[k]) return;
  if (e && (e.ctrlKey || e.metaKey)) { PLS.sel.has(k) ? PLS.sel.delete(k) : PLS.sel.add(k); PLS.anchor = k; }
  else if (e && e.shiftKey && PLS.anchor !== null) {
    const [a, b] = [Math.min(PLS.anchor, k), Math.max(PLS.anchor, k)];
    PLS.sel = new Set(Array.from({ length: b - a + 1 }, (_, j) => a + j));
  } else { PLS.sel = new Set([k]); PLS.anchor = k; }
  $$("#plsList .pls-row[data-k]").forEach((el) => { const on = PLS.sel.has(+el.dataset.k); el.classList.toggle("sel", on); el.setAttribute("aria-selected", String(on)); });
  const el = $(`#plsList .pls-row[data-k="${k}"]`); if (el) el.scrollIntoView({ block: "nearest" });
  if (src && typeof playerFollow === "function") playerFollow(src);
}

/** Player-Ziel einer Zeile: im Tagger geladen → kind „tag“, sonst die Datei direkt (kind „file“, #270) */
function plsRowTarget(r) {
  if (!r || r.missing || !r.path) return null;
  return r.i !== null && r.i !== undefined ? { kind: "tag", ref: r.i } : { kind: "file", ref: r.path };
}
function plsSame(a, b) { return !!a && !!b && (a === b || a.toLowerCase() === b.toLowerCase()); }

/** „Playlist abspielen“ (#270): läuft gerade ein Titel der gestarteten Playlist? Dann folgt der Player ihr – auch auf
    anderen Seiten (⏭/⏮, Titelende, Überblenden bei im Tagger geladenen Titeln). */
function plsPlayActive() {
  return !!(PLS.play && PLAYER.info && PLS.play.items.some((r) => plsSame(r.path, PLAYER.info.path)));
}
function plsPlayIndex() { return PLS.play ? PLS.play.items.findIndex((r) => plsSame(r.path, PLAYER.info && PLAYER.info.path)) : -1; }

function plsPlayStart() {
  const pl = plsCur(); if (!pl) return;
  const items = pl.items.map((r) => ({ path: r.path, i: r.i, missing: r.missing || !r.path }));
  let k = PLS.anchor !== null && !items[PLS.anchor].missing ? PLS.anchor : items.findIndex((r) => !r.missing);
  if (k < 0) { toast("Keine abspielbaren Titel."); return; }
  PLS.play = { id: pl.id, name: pl.name, items };
  plsSelect(k, null, null);
  plLoad(plsRowTarget(pl.items[k]), true);
  setTimeout(plsRenderHead, 600);
}

/** Player-Ziel auf dieser Seite: markierter Titel */
function plsTarget() { return plsRowTarget(PLS.anchor !== null ? plsRow(PLS.anchor) : null); }

function plsNextTag() {
  if (plsPlayActive()) {
    const it = PLS.play.items;
    for (let j = plsPlayIndex() + 1; j < it.length; j++) if (it[j].i !== null && it[j].i !== undefined && !it[j].missing) return it[j].i;
    return null;
  }
  const pl = plsCur(); if (!pl) return null;
  let k = pl.items.findIndex((r) => r.i === PLAYER.ref);
  if (k < 0) k = PLS.anchor === null ? -1 : PLS.anchor;
  for (let j = k + 1; j < pl.items.length; j++) if (pl.items[j].i !== null && pl.items[j].i !== undefined) return pl.items[j].i;
  return null;
}
function plsSelectTag(i) { const pl = plsCur(); const k = pl ? pl.items.findIndex((r) => r.i === i) : -1; if (k >= 0) plsSelect(k); }

async function plsStep(dir, play = true) {
  if (plsPlayActive()) {                                       // gestartete Playlist, egal welche Seite offen ist
    const it = PLS.play.items;
    let k = plsPlayIndex();
    do { k += dir; } while (k >= 0 && k < it.length && it[k].missing);
    if (k < 0 || k >= it.length) return;
    const pl = plsCur();
    if (S.module === "playlists" && pl && pl.id === PLS.play.id && pl.items[k]) plsSelect(k, null, null);
    plLoad(plsRowTarget(it[k]), true);
    return;
  }
  const pl = plsCur(); if (!pl) return;
  let k = PLS.anchor === null ? -1 : PLS.anchor;
  for (let s = 0; s < pl.items.length; s++) {
    k = k < 0 ? (dir > 0 ? 0 : pl.items.length - 1) : k + dir;
    if (k < 0 || k >= pl.items.length) return;
    if (plsRowTarget(pl.items[k])) break;
  }
  const was = PLAYER.audio && !PLAYER.audio.paused;
  plsSelect(k);
  if (!was && play) { const t = plsTarget(); if (t) plLoad(t, true); }
}

function plsPlay(k) {
  const r = plsRow(k); if (!r) return;
  const t = plsRowTarget(r);
  if (!t) { toast(r.ref ? "Zu diesem Eintrag gibt es noch keine Datei." : "Die Datei fehlt."); return; }
  plLoad(t, true);
}

// ---------------------------------------------------------------- Auswahl- und Namensdialoge
/** Playlist wählen oder neu anlegen → {id} | {name, folder} | null */
async function plsPick({ title, ok = "OK", allowNew = true, exclude = "" } = {}) {
  const st = await call("pl_list");
  const pls = st.playlists.filter((p) => p.id !== exclude && p.kind !== "smart" && p.kind !== "wish");   // #186: Wunschlisten über „Ideen“
  const order = [...st.recent.map((id) => pls.find((p) => p.id === id)).filter(Boolean), ...pls.filter((p) => !st.recent.includes(p.id))];
  const folders = st.folders;
  const html = `<input class="inp" id="plsPickFind" placeholder="Suchen …" style="width:100%" autocomplete="off">
    <div class="pls-pick" id="plsPickList" role="listbox">${order.map((p, k) => `<label class="pls-pick-row" data-name="${esc(plsLabel(p).toLowerCase())}">
      <input type="radio" name="plsPick" value="${esc(p.id)}"${k === 0 ? " checked" : ""}> <span class="pls-ico" aria-hidden="true">${PLS_ICON[p.kind] || "♫"}</span>
      <span class="ellipsis" translate="no">${esc(plsLabel(p))}</span><span class="muted sm">${fmtN(p.count)}</span>${st.recent.includes(p.id) ? ' <span class="chip sm">zuletzt</span>' : ""}</label>`).join("") || '<div class="muted sm">Noch keine Playlists.</div>'}</div>
    ${allowNew ? `<label class="pls-pick-row pls-pick-new"><input type="radio" name="plsPick" value="__new" data-plsnew${order.length ? "" : " checked"}> Neue Playlist:</label>
      <div class="pls-newrow"><input class="inp" id="plsPickName" placeholder="Name" maxlength="120"><input class="inp" id="plsPickFolder" list="plsPickFolders" placeholder="Ordner (optional, z. B. Sets/2026)"><datalist id="plsPickFolders">${folders.map((f) => `<option value="${esc(f)}">`).join("")}</datalist></div>` : ""}`;
  return modal({ title, html, buttons: [{ label: "Abbrechen", value: null }, { label: ok, value: true, primary: true }],
    onMount: (b) => {
      const find = $("#plsPickFind", b);
      find.focus();
      find.addEventListener("input", () => { const q = find.value.trim().toLowerCase(); b.querySelectorAll(".pls-pick-row[data-name]").forEach((r) => { r.hidden = !!q && !r.dataset.name.includes(q); }); });
      const nm = $("#plsPickName", b);
      const pickNew = () => { const r = b.querySelector("[data-plsnew]"); if (r) r.checked = true; };
      if (nm) nm.addEventListener("focus", pickNew);
      const fd = $("#plsPickFolder", b);
      if (fd) fd.addEventListener("focus", pickNew);
      b.addEventListener("dblclick", (e) => { if (e.target.closest(".pls-pick-row[data-name]")) $("#mBtns .primary").click(); });
    },
    collect: (b) => {
      const v = (b.querySelector('input[name="plsPick"]:checked') || {}).value;
      if (!v) { toast("Bitte eine Playlist wählen."); return false; }
      if (v !== "__new") return { id: v };
      const name = $("#plsPickName", b).value.trim();
      if (!name) { toast("Bitte einen Namen eingeben."); $("#plsPickName", b).focus(); return false; }
      return { name, folder: $("#plsPickFolder", b).value.trim() };
    } });
}

async function plsAsk(title, label, value = "", extra = "") {
  return modal({ title, html: `<label class="muted sm" for="plsNameIn">${esc(label)}</label><input class="inp" id="plsNameIn" maxlength="120" style="width:100%" value="${esc(value)}" autofocus>${extra}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "OK", value: true, primary: true }],
    onMount: (b) => { const i = $("#plsNameIn", b); i.focus(); i.select(); },
    collect: (b) => { const v = $("#plsNameIn", b).value.trim(); if (!v) { toast("Bitte einen Namen eingeben."); return false; } return v; } });
}

async function plsFolderPick(title, value = "") {
  const st = await call("pl_list");
  return modal({ title, html: `<label class="muted sm" for="plsFolderIn">Ordner (leer = oberste Ebene, Unterordner mit „/“)</label>
      <input class="inp" id="plsFolderIn" list="plsFolderList" style="width:100%" value="${esc(value)}"><datalist id="plsFolderList">${st.folders.map((f) => `<option value="${esc(f)}">`).join("")}</datalist>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Verschieben", value: true, primary: true }],
    onMount: (b) => $("#plsFolderIn", b).focus(), collect: (b) => $("#plsFolderIn", b).value.trim() });
}

/** Doppelte Titel: nachfragen (E5 – erlaubt, aber mit Hinweis) */
async function plsDupes(r) {
  return modal({ title: "Doppelte Titel", html: `<p style="margin:0">Schon in „${esc(r.name)}“: ${fmtN(r.dupes)} Titel. Neu: ${fmtN(r.new)} Titel.</p><p style="margin:8px 0 0">Die schon enthaltenen trotzdem nochmals hinzufügen?</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Überspringen", value: "skip" }, { label: "Trotzdem hinzufügen", value: "add", primary: true }] });
}

/** Titel einer Playlist hinzufügen – mit Rückfrage bei Doppelten. kind: "tag" (Tagger-Indizes) oder "paths". */
async function plsAddTo(id, kind, list) {
  const fn = kind === "tag" ? "pl_add_tag" : "pl_add_paths";
  try {
    let r = await call(fn, id, list, "ask");
    if (r.ask) { const how = await plsDupes(r); if (!how) return null; r = await call(fn, id, list, how); }
    toast(r.message); status(r.message, "ok");
    if (S.module === "playlists") playlistsShow(); else call("pl_state", id).then(plsApply).catch(() => {});
    if (typeof TG !== "undefined" && TG.plFilter && TG.plFilter.id === id) tgSetPlFilter(id);
    plsRecentRefresh();
    return r;
  } catch (e) { toast(String(e.message || e)); return null; }
}

/** „Zur Playlist hinzufügen …“ – aus Tagger (Indizes) oder Pfaden (DJ-Set, Playlist) */
async function plsAddDialog(kind, list, exclude = "") {
  if (!list || !list.length) { toast("Zuerst Titel markieren."); return; }
  const n = list.length;
  const pick = await plsPick({ title: `Zur Playlist hinzufügen (${fmtN(n)} Titel)`, ok: "Hinzufügen", exclude });
  if (!pick) return;
  if (pick.id) { await plsAddTo(pick.id, kind, list); return; }
  try {
    const st = kind === "tag" ? await call("pl_create", pick.name, pick.folder, list) : await call("pl_create", pick.name, pick.folder, null);
    if (kind !== "tag") await call("pl_add_paths", st.sel, list, "add");
    toast(st.message);
    if (S.module === "playlists") playlistsShow(); else plsApply(st);
    plsRecentRefresh();
  } catch (e) { toast(String(e.message || e)); }
}

/** Strg+Shift+P: zur zuletzt benutzten Playlist (#268) */
async function plsQuickAdd(idx) {
  if (!idx || !idx.length) { toast("Zuerst Titel markieren."); return; }
  const st = await call("pl_list");
  if (!st.recent.length) { plsAddDialog("tag", idx); return; }
  plsAddTo(st.recent[0], "tag", idx);
}

/** Einträge für Kontextmenüs (Tagger, Player) */
function plsMenuItems(idx) {
  const n = idx.length, rec = PLS.recentName;
  const items = [{ label: `Zur Playlist hinzufügen …${n > 1 ? ` (${n})` : ""}`, run: () => plsAddDialog("tag", idx) }];
  if (rec) items.push({ label: `Zu „${rec}“ hinzufügen (Strg+Shift+P)`, run: () => plsQuickAdd(idx) });
  return items;
}
function plsRecentRefresh() {
  call("pl_list").then((st) => { const p = st.playlists.find((x) => x.id === st.recent[0]); PLS.recentName = p ? p.name : ""; }).catch(() => {});
}

// ---------------------------------------------------------------- Aktionen
async function plsNew(folder = "") {
  const name = await plsAsk("Neue Playlist", "Name der Playlist"); if (!name) return;
  plsCall("pl_create", name, folder, null);
}
async function plsNewFolder(parent = "") {
  const name = await plsAsk("Neuer Ordner", parent ? `Unterordner in „${parent}“` : "Name des Ordners (Unterordner mit „/“)"); if (!name) return;
  plsCall("pl_folder_create", parent ? `${parent}/${name}` : name);
}

async function plsOpenTagger(id) {
  const r = await call("pl_files", id);
  if (!r.files.length) { toast("Keine der Dateien ist auf diesem Rechner vorhanden."); return; }
  const t = await runTask(call("start_tag_load_files", r.files, r.name), "Dateien einlesen");
  if (!t || t.cancelled) return;
  setModule("tagger");
  if (typeof tgAfterLoad === "function") await tgAfterLoad(t, "", false);
  if (r.missing) toast(`${r.missing} Titel fehlen auf diesem Rechner.`);
}

async function plsOpenDjset(id) {
  if (typeof djUnsavedOk === "function" && !(await djUnsavedOk("Playlist im DJ-Set öffnen"))) return;
  try {
    const st = await call("dj_load", id);
    setModule("djset");
    if (typeof djApply === "function") djApply(st);
  } catch (e) { toast(String(e.message || e)); }
}

async function plsMerge(id) {
  const st = await call("pl_list");
  const cur = st.playlists.find((p) => p.id === id);
  const res = await modal({ title: "Playlists zusammenführen", wide: true,
    html: `<div class="hint">Legt eine neue Playlist mit den Titeln aller gewählten an (in dieser Reihenfolge). Die bisherigen bleiben unverändert.</div>
      <div class="pls-pick">${st.playlists.map((p) => `<label class="pls-pick-row"><input type="checkbox" data-plsm="${esc(p.id)}"${p.id === id ? " checked" : ""}> <span class="ellipsis" translate="no">${esc(plsLabel(p))}</span><span class="muted sm">${fmtN(p.count)}</span></label>`).join("")}</div>
      <label class="muted sm" for="plsMergeName">Name der neuen Playlist</label><input class="inp" id="plsMergeName" style="width:100%" value="${esc(cur ? cur.name + " + …" : "")}">`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Zusammenführen", value: true, primary: true }],
    collect: (b) => {
      const ids = [...b.querySelectorAll("[data-plsm]:checked")].map((c) => c.dataset.plsm);
      const name = $("#plsMergeName", b).value.trim();
      if (ids.length < 2) { toast("Bitte mindestens zwei Playlists wählen."); return false; }
      if (!name) { toast("Bitte einen Namen eingeben."); return false; }
      return { ids, name };
    } });
  if (res) plsCall("pl_merge", res.ids, res.name, cur ? cur.folder : "");
}

async function plsColorNote(id) {
  const p = plsMeta(id); if (!p) return;
  const cols = ["", "#e5484d", "#f76b15", "#ffc53d", "#46a758", "#12a594", "#0090ff", "#8e4ec6", "#d6409f"];
  const res = await modal({ title: "Farbe und Notiz",
    html: `<div class="pls-colors" role="radiogroup" aria-label="Farbe">${cols.map((c) => `<label class="pls-col"><input type="radio" name="plsCol" value="${c}"${(p.color || "") === c ? " checked" : ""}><span style="${c ? `background:${c}` : ""}" title="${c ? c : "keine Farbe"}">${c ? "" : "–"}</span></label>`).join("")}</div>
      <label class="muted sm" for="plsNote">Notiz</label><textarea class="inp" id="plsNote" rows="3" style="width:100%" maxlength="2000">${esc(p.note || "")}</textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    collect: (b) => ({ color: (b.querySelector('input[name="plsCol"]:checked') || {}).value || "", note: $("#plsNote", b).value }) });
  if (res) plsCall("pl_meta", id, res.color, res.note);
}

async function plsArchive(id) {
  const p = plsMeta(id); if (!p) return;
  const mirror = PLS.st.mirror;
  const ok = await modal({ title: "Playlist archivieren",
    html: `<p style="margin:0">„${esc(p.name)}“ ins Archiv legen? Die Playlist bleibt erhalten und lässt sich jederzeit zurückholen. Die Musikdateien bleiben unverändert.</p>${mirror ? '<p style="margin:8px 0 0">Ihre M3U8 wandert aus dem Playlist-Ordner ins Archiv.</p>' : ""}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Archivieren", value: true, primary: true }] });
  if (ok) plsCall("pl_archive", id);
}

async function plsDelete(id) {
  const p = plsMeta(id); if (!p) return;
  const ok = await modal({ title: "Endgültig löschen",
    html: `<p style="margin:0">„${esc(p.name)}“ endgültig löschen? Das lässt sich nicht rückgängig machen. Die Musikdateien bleiben unverändert.</p>${p.file ? '<p style="margin:8px 0 0">Auch die M3U8 im Archiv wird entfernt.</p>' : ""}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Endgültig löschen", value: true, primary: true }] });
  if (ok) plsCall("pl_delete", id);
}

function plsPlMenu(x, y, id) {
  const p = plsMeta(id); if (!p) return;
  if (p.archived) {
    showMenu(x, y, [{ label: "Zurückholen", run: () => plsCall("pl_restore", id) }, { label: "Datei zeigen", icon: ICON.folder, run: () => call("pl_reveal", id) }, "-",
      { label: "Endgültig löschen …", run: () => plsDelete(id) }]);
    return;
  }
  showMenu(x, y, [
    { label: "Im Tagger öffnen", run: () => plsOpenTagger(id) },
    { label: "Im DJ-Set öffnen", run: () => plsOpenDjset(id) }, "-",
    { label: "Umbenennen … (F2)", run: () => plsRename(id) },
    { label: "Duplizieren", run: () => plsCall("pl_duplicate", id) },
    ...(p.kind === "smart" ? [{ label: "Regeln …", run: () => plsSmartDialog(p) }, { label: "Aktualisieren", run: () => plsSmartRefresh(id) },
      { label: "Einfrieren (normale Playlist daraus machen)", run: () => plsSmartFreeze(id) }] : []),
    { label: "In Ordner verschieben …", run: () => plsMove(id) },
    { label: "Farbe und Notiz …", run: () => plsColorNote(id) },
    { label: "Mit anderen zusammenführen …", run: () => plsMerge(id) },
    ...(PLS.st.mirror ? [{ label: "M3U8 im Playlist-Ordner zeigen", icon: ICON.folder, run: () => call("pl_reveal", id).then((ok) => { if (!ok) toast("Datei nicht gefunden."); }) }] : []),
    "-", ...plsListItems(id),
    ...(PLS.push && PLS.push.length ? ["-", ...PLS.push.map((t) => ({ label: `An ${t.name} senden …`, run: () => plsPush(id, t) }))] : []),
    "-", { label: "Archivieren …", run: () => plsArchive(id) },
  ]);
}

/** #270/#271: Export, Warteschlange, Abgleich, Fehlende, Einkaufsliste */
function plsListItems(id) {
  const cur = plsCur(), here = cur && cur.id === id ? cur : null;
  const refs = here ? here.refs : 0, gone = here ? here.missing - here.refs : 0;
  return [
    { label: "Exportieren: M3U8 (absolute Pfade) …", run: () => plsExport("m3u8", { ids: [id] }, { relative: false }) },
    { label: "Exportieren: M3U8 (relative Pfade) …", run: () => plsExport("m3u8", { ids: [id] }, { relative: true }) },
    { label: "Exportieren: Rekordbox-XML …", run: () => plsExport("xml", { ids: [id] }, {}) },
    { label: "Exportieren: CSV für Excel …", run: () => plsExport("csv", { ids: [id] }, {}) },
    { label: "In die Warteschlange (im Tagger geladene Titel)", run: () => plsToQueue(id) },
    ...(here && refs ? [{ label: `Mit Bibliothek abgleichen … (${refs} ohne Datei)`, run: () => plsMatch(id) }] : []),
    { label: "Alle Playlists mit Bibliothek abgleichen …", run: () => plsMatch({ folder: "" }) },
    ...(here && gone > 0 ? [{ label: `Fehlende suchen … (${gone})`, run: () => plsFindMissing(id) }] : []),
    ...(here && (refs || gone > 0) ? [{ label: "Einkaufsliste exportieren …", run: () => plsShopping({ ids: [id] }) }] : []),
  ];
}

async function plsExport(fmt, sel, opts) {
  try {
    const r = await call("pl_export", fmt, sel.ids || null, sel.folder ?? null, opts);
    if (r && r.ok) { toast(r.message); status(`${r.message} (${r.path})`, "info"); }
  } catch (e) { toast(String(e.message || e)); }
}
async function plsShopping(sel) {
  try {
    const r = await call("pl_shopping", sel.ids || null, sel.folder ?? null);
    if (r && r.ok) { toast(r.message); status(`${r.message} (${r.path})`, "info"); }
  } catch (e) { toast(String(e.message || e)); }
}
async function plsToQueue(id) {
  try { const st = await call("pl_to_queue", id); if (typeof pqApply === "function") pqApply(st); else toast(st.message); }
  catch (e) { toast(String(e.message || e)); }
}

/** Import: Datei oder Plugin-Quelle (#271) */
async function plsImportMenu(btn) {
  let src = [];
  try { src = (await call("dj_sources")).sources || []; } catch (e) { /* keine */ }
  const mix = typeof mixMenuEntries === "function" ? await mixMenuEntries() : [];      // #387
  const r = btn.getBoundingClientRect();
  showMenu(r.left, r.bottom + 6, [
    { label: "Datei (M3U, M3U8, Rekordbox-XML, CSV, Spotify-Export) …", run: () => plsImportFile() },
    { label: "Trackliste einfügen (1001Tracklists, MixID, Beatport …) …", run: () => plsImportText() },
    ...(mix.length ? ["-", ...mix] : []),
    "-",
    { label: "Aus Serato …", run: () => plsImportApp("serato") },
    { label: "Aus Engine DJ …", run: () => plsImportApp("engine") },
    { label: "Aus VirtualDJ …", run: () => plsImportApp("vdj") },
    ...src.map((x) => ({ label: `Aus ${x.name} …`, run: () => plsImportSource(x) })),
  ]);
}

/** #278: Playlists aus Serato, Engine DJ oder VirtualDJ – die Bibliothek des Programms wird nur gelesen */
async function plsImportApp(app) {
  let lib;
  try { lib = await call("pl_dj_libraries", app); } catch (e) { toast(String(e.message || e)); return; }
  let path = lib.found[0] || "";
  if (lib.found.length !== 1) {
    const where = await modal({ title: `Playlists aus ${lib.name}`,
      html: lib.found.length
        ? `<p style="margin:0 0 8px">Welche Bibliothek?</p><select class="inp" id="plsDjLib" translate="no">${lib.found.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join("")}</select>`
        : `<p style="margin:0">Keine Bibliothek von ${esc(lib.name)} am üblichen Ort gefunden. Bitte den Ordner wählen (${esc(PLS_DJ_HINT[app])}).</p>`,
      buttons: [{ label: "Abbrechen", value: null }, { label: "Anderer Ordner …", value: "pick" }, ...(lib.found.length ? [{ label: "Weiter", value: "ok", primary: true }] : [])],
      collect: (b, v) => v === "ok" ? b.querySelector("#plsDjLib").value : v });
    if (!where) return;
    path = where;
  }
  if (path === "pick") {
    const r = await call("pl_dj_pick", app);
    if (!r || r.cancelled) return;
    path = r.path;
  }
  const res = await runTask(call("start_pl_dj_scan", app, path), `${lib.name}: Playlists lesen`);
  if (!res || res.cancelled) return;
  if (res.ok === false) { info(lib.name, res.error); return; }
  if (!res.lists.length) { info(lib.name, "In dieser Bibliothek gibt es keine Playlists."); return; }
  const keys = await modal({ title: `Playlists aus ${lib.name} übernehmen`, wide: true,
    html: `<div class="hint">Häkchen setzen und „Übernehmen“ – die Playlists kommen in den Ordner „${esc(lib.name)}“ (schon übernommene werden aktualisiert). ${esc(lib.name)} selbst bleibt unverändert.</div>
      <div class="muted sm" translate="no" style="margin:0 0 6px">${esc(res.path)}</div>
      <label class="djs-row"><input type="checkbox" id="plsDjAll"> <b>Alle</b></label>
      <div class="djs-list">${res.lists.map((p, k) => `<label class="djs-row" style="padding-left:${8 + 18 * (p.folder ? p.folder.split("/").length : 0)}px"><input type="checkbox" data-plsdj="${k}"> <span translate="no">${esc(p.name)}</span>
        <span class="muted sm">${p.missing ? `${fmtN(p.count)} Titel, davon ${fmtN(p.missing)} nicht auf diesem Rechner` : `${fmtN(p.count)} Titel`}</span>${p.known ? ' <span class="chip">schon übernommen</span>' : ""}${p.folder ? ` <span class="muted sm" translate="no">${esc(p.folder)}</span>` : ""}</label>`).join("")}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => b.querySelector("#plsDjAll").addEventListener("change", (e) => b.querySelectorAll("[data-plsdj]").forEach((c) => { c.checked = e.target.checked; })),
    collect: (b) => [...b.querySelectorAll("[data-plsdj]:checked")].map((c) => res.lists[+c.dataset.plsdj].key) });
  if (!keys || !keys.length) return;
  const r = await runTask(call("start_pl_dj_import", app, res.path, keys), `${lib.name}: Playlists übernehmen`);
  if (!r || r.cancelled) return;
  if (r.ok === false) { toast(r.error); return; }
  toast(r.missing ? `${r.lists.length} Playlist(s) übernommen. ${r.missing} Titel sind nicht auf diesem Rechner – „Fehlende suchen …“ hilft.`
    : `${r.lists.length} Playlist(s) übernommen.`);
  PLS.sel = new Set();
  plsApply(await call("pl_state", r.lists[0] ? r.lists[0].id : ""));
}
const PLS_DJ_HINT = { serato: "den Ordner „_Serato_“", engine: "den Ordner „Engine Library“", vdj: "den Ordner „VirtualDJ“" };

/** #279: kopierte Trackliste einfügen → Einträge ohne Datei, danach „Mit Bibliothek abgleichen …“ */
async function plsImportText() {
  const r = await modal({ title: "Trackliste einfügen", wide: true,
    html: `<div class="hint">Trackliste von 1001Tracklists, MixID, einer Beatport-Chart oder aus eigenen Notizen kopieren und hier einfügen – je Zeile „Künstler - Titel (Mix)“. Nummern, Zeitmarken und Labels in eckigen Klammern fallen weg; unbekannte Titel („ID - ID“) werden ausgelassen. TagStudio ruft dafür keine Webseite ab.</div>
      <div class="row" style="gap:8px;margin:0 0 8px"><input class="inp" id="plsTxtName" placeholder="Name der Playlist" style="flex:1">
      <select class="inp" id="plsTxtSrc"><option value="1001tracklists">1001Tracklists</option><option value="mixid">MixID</option><option value="beatport">Beatport</option><option value="spotify">Spotify</option><option value="text" selected>andere Quelle</option></select></div>
      <textarea class="inp" id="plsTxt" rows="14" style="width:100%;font-family:var(--mono, monospace)" translate="no" placeholder="01. Künstler - Titel (Extended Mix) [Label]"></textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    onMount: (b) => b.querySelector("#plsTxt").focus(),
    collect: (b) => ({ text: b.querySelector("#plsTxt").value, name: b.querySelector("#plsTxtName").value.trim(), src: b.querySelector("#plsTxtSrc").value,
      label: b.querySelector("#plsTxtSrc").selectedOptions[0].textContent }) });
  if (!r || !r.text.trim()) return;
  const folder = r.src === "text" ? "Tracklisten" : r.label;
  try { PLS.sel = new Set(); plsApply(await call("pl_import_text", r.text, r.name, folder, r.src)); }
  catch (e) { toast(String(e.message || e)); }
}
async function plsImportFile() {
  try { const st = await call("pl_import", ""); if (st && !st.cancelled) { PLS.sel = new Set(); plsApply(st); } }
  catch (e) { toast(String(e.message || e)); }
}
async function plsImportSource(src) {
  const res = await runTask(call("start_dj_source_list", src.id), `${src.name}: Playlists holen`);
  if (!res || res.cancelled) return;
  const pls = res.playlists || [];
  if (!pls.length) { info(src.name, "Keine Playlists gefunden."); return; }
  const ids = await modal({ title: `Playlists aus ${src.name} übernehmen`, wide: true,
    html: `<div class="hint">Häkchen setzen und „Übernehmen“ – jede Playlist kommt in den Ordner „${esc(src.name)}“ (schon geholte werden aktualisiert).</div>
      <div class="djs-list">${pls.map((p, k) => `<label class="djs-row" style="padding-left:${8 + 18 * Math.max(0, p.depth)}px"><input type="checkbox" data-plsi="${k}"> <span translate="no">${esc(p.name)}</span></label>`).join("")}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    collect: (b) => [...b.querySelectorAll("[data-plsi]:checked")].map((c) => pls[+c.dataset.plsi].id) });
  if (!ids || !ids.length) return;
  const r = await runTask(call("start_pl_source_import", src.id, ids), `${src.name}: Playlists übernehmen`);
  if (!r || r.cancelled) return;
  toast(`${r.lists.length} Playlist(s) übernommen` + (r.missing ? ` · ${r.missing} Titel nicht auf diesem Rechner` : "") + ".");
  if (r.kept || r.linked) toast(`Verknüpfungen: ${fmtN(r.kept || 0)} behalten, ${fmtN(r.linked || 0)} neu gefunden.`);
  const first = r.lists[0];
  plsApply(await call("pl_state", first ? first.id : ""));
}

/** Treffer-Dialog für Abgleich und Fehlende suchen: je Zeile Status und Auswahl → picks [{k, path}] */
async function plsPickRows(title, hint, rows, labelOf, suggest = true) {
  const st = { sure: "gefunden", unclear: "unklar", missing: "fehlt" };
  const unclear = rows.filter((r) => r.status === "unclear" && r.path).length;
  // #281: unklare Zeilen bringen einen Vorschlag mit – vorgewählt nur, wenn „Vorschläge vorwählen“ an ist
  const opt = (r) => r.candidates.length
    ? `<select class="inp" data-plsk="${r.k}"${r.pid ? ` data-pid="${esc(r.pid)}"` : ""} data-sug="${esc(r.status === "unclear" ? r.path || "" : "")}">${r.status === "sure" ? "" : '<option value="">– nicht verknüpfen –</option>'}${r.candidates.map((c) => `<option value="${esc(c)}"${c === r.path && (r.status !== "unclear" || suggest) ? " selected" : ""}>${c === r.path && r.status === "unclear" ? "★ " : ""}${esc(c)}</option>`).join("")}</select>`
    : '<span class="muted sm">kein Treffer</span>';
  return modal({ title, wide: true,
    html: `<div class="hint">${esc(hint)}</div>${unclear ? `<label class="check" style="margin:0 0 6px"><input type="checkbox" id="plsSug"${suggest ? " checked" : ""}> Vorschläge (★) für unklare Einträge vorwählen (${fmtN(unclear)})</label>` : ""}
      <div class="fx-table" style="max-height:55vh"><table><thead><tr><th>Eintrag</th><th>Status</th><th>Datei</th></tr></thead><tbody>${rows.map((r) => `<tr>
      <td translate="no">${esc(labelOf(r))}</td><td><span class="pls-st ${r.status}">${st[r.status]}</span>${r.reason ? `<div class="muted sm">${esc(r.reason)}</div>` : ""}</td><td translate="no">${opt(r)}</td></tr>`).join("")}</tbody></table></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Verknüpfen", value: true, primary: true }],
    onMount: (b) => b.querySelector("#plsSug")?.addEventListener("change", (e) => b.querySelectorAll("select[data-sug]").forEach((el) => {
      if (el.dataset.sug) el.value = e.target.checked ? el.dataset.sug : ""; })),
    collect: (b) => [...b.querySelectorAll("[data-plsk]")].map((el) => ({ k: +el.dataset.plsk, pid: el.dataset.pid || undefined, path: el.value })).filter((x) => x.path) });
}

/** Abgleich: id = eine Playlist, sonst {folder} (#282: ganzer Ordner, "" = alle Playlists) */
async function plsMatch(id) {
  const m = (PLS.st && PLS.st.match) || { any_mix: false, roots: [] };
  const what = typeof id === "string" ? "" : (id.folder ? `Abgeglichen werden alle Playlists in „${esc(id.folder)}“.` : "Abgeglichen werden alle Playlists.");
  const how = await modal({ title: "Mit der Bibliothek abgleichen",
    html: `${what ? `<p style="margin:0 0 8px">${what}</p>` : ""}<p style="margin:0 0 6px">Suchen in:</p>
      ${m.roots.length ? `<div class="djs-list" style="margin:0 0 8px">${m.roots.map((r, k) => { const l = (m.libs || []).find((x) => x.path.toLowerCase() === r.toLowerCase()); return `<label class="djs-row"><input type="checkbox" data-plsroot="${k}" checked> ${l ? `<b translate="no">${esc(l.name)}</b> ` : ""}<span class="muted sm" translate="no">${esc(r)}</span></label>`; }).join("")}</div>${(m.libs_skipped || []).length ? `<p class="muted sm">Übersprungen: ${m.libs_skipped.map((x) => `${esc(x.name)} (${esc(x.why)})`).join(", ")}</p>` : ""}`
        : '<p class="muted sm">Keine Bibliothek festgelegt – nur die im Tagger geladenen Titel.</p>'}
      <p class="muted sm" style="margin:0 0 8px">Dazu die im Tagger geladenen Titel. „Anderer Ordner …“ sucht zusätzlich in einem Ordner deiner Wahl.</p>
      <label class="check"><input type="checkbox" id="plsAnyMix"${m.any_mix ? " checked" : ""}> Anderer Mix gilt als gefunden (z. B. Extended Mix statt Radio Edit; Extended wird bevorzugt)</label>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Anderer Ordner …", value: "pick" }, { label: "Abgleichen", value: "lib", primary: true }],
    collect: (b, v) => ({ v, any: b.querySelector("#plsAnyMix").checked,
      roots: [...b.querySelectorAll("[data-plsroot]:checked")].map((c) => m.roots[+c.dataset.plsroot]) }) });
  if (!how) return;
  let folder = "";
  if (how.v === "pick") { folder = await call("pick_path", "", true, ""); if (!folder) return; }
  if (PLS.st && PLS.st.match) PLS.st.match.any_mix = how.any;
  const r = await runTask(call("start_pl_match", id, folder, how.any, how.roots), "Mit der Bibliothek abgleichen");
  if (!r || r.cancelled) return;
  if (r.ok === false) { toast(r.error); return; }
  const picks = await plsPickRows("Mit der Bibliothek abgleichen",
    r.playlists > 1 ? `${fmtN(r.playlists)} Playlists mit ${fmtN(r.library)} Titeln abgeglichen: ${fmtN(r.sure)} gefunden, ${fmtN(r.unclear)} unklar, ${fmtN(r.missing)} fehlen. Gefundene und Vorschläge (★) sind vorgewählt; bei unklaren steht der Grund.`
      : `${fmtN(r.library)} Titel geprüft: ${fmtN(r.sure)} gefunden, ${fmtN(r.unclear)} unklar, ${fmtN(r.missing)} fehlen. Gefundene und Vorschläge (★) sind vorgewählt; bei unklaren steht der Grund.`,
    r.rows, (x) => (x.playlist ? x.playlist + " · " : "") + x.label);
  if (picks && picks.length) plsCall("pl_relink_many", picks.map((p) => ({ ...p, pid: p.pid || id })), PLS.st ? PLS.st.sel : "");
}

async function plsFindMissing(id) {
  let folder = "";
  const how = await modal({ title: "Fehlende suchen", html: '<p style="margin:0">Wo soll TagStudio nach den fehlenden Dateien suchen (gleicher Dateiname)?</p>',
    buttons: [{ label: "Abbrechen", value: null }, { label: "Anderer Ordner …", value: "pick" }, { label: "In der Bibliothek", value: "lib", primary: true }] });
  if (!how) return;
  if (how === "pick") { folder = await call("pick_path", "", true, ""); if (!folder) return; }
  const r = await runTask(call("start_pl_find_missing", id, folder), "Fehlende Dateien suchen");
  if (!r || r.cancelled) return;
  if (r.ok === false) { toast(r.error); return; }
  const picks = await plsPickRows("Fehlende suchen", "Neuer Ort je fehlender Datei – eindeutige Treffer (gleiche Grösse) sind vorgewählt.",
    r.rows, (x) => x.old.split(/[\\/]/).pop());
  if (picks && picks.length) plsCall("pl_relink", id, picks);
}


async function plsRename(id) {
  const p = plsMeta(id); if (!p || p.archived) return;
  const name = await plsAsk("Playlist umbenennen", "Neuer Name", p.name);
  if (name && name !== p.name) plsCall("pl_rename", id, name);
}
async function plsMove(id) {
  const p = plsMeta(id); if (!p) return;
  const f = await plsFolderPick(`„${p.name}“ verschieben`, p.folder);
  if (f !== null && f !== undefined && f !== p.folder) plsCall("pl_move", id, f);
}

function plsFolderMenu(x, y, f) {
  showMenu(x, y, [
    { label: "Neue Playlist hier …", run: () => plsNew(f) },
    { label: "Neue Smartlist hier …", run: () => plsSmartDialog(null, f) },
    { label: "Neuer Unterordner …", run: () => plsNewFolder(f) }, "-",
    { label: "Ordner umbenennen …", run: async () => { const n = await plsAsk("Ordner umbenennen", "Neuer Name bzw. Pfad (mit „/“)", f); if (n && n !== f) plsCall("pl_folder_rename", f, n); } },
    { label: "Leeren Ordner entfernen", run: () => plsCall("pl_folder_remove", f) }, "-",
    { label: "Ordner als Rekordbox-XML exportieren …", run: () => plsExport("xml", { folder: f }, {}) },
    { label: "Einkaufsliste des Ordners …", run: () => plsShopping({ folder: f }) },
    { label: "Ordner mit Bibliothek abgleichen …", run: () => plsMatch({ folder: f }) }, "-",
    { label: "Ganzen Ordner archivieren …", run: async () => {
      const n = PLS.st.playlists.filter((p) => p.folder === f || p.folder.startsWith(f + "/")).length;
      const ok = await modal({ title: "Ordner archivieren", html: `<p style="margin:0">Alle ${fmtN(n)} Playlists in „${esc(f)}“ archivieren? Sie lassen sich einzeln zurückholen.</p>`,
        buttons: [{ label: "Abbrechen", value: null }, { label: "Archivieren", value: true, primary: true }] });
      if (ok) plsCall("pl_folder_archive", f);
    } },
  ]);
}

function plsRowMenu(e, k) {
  const pl = plsCur(), r = plsRow(k); if (!pl || !r) return;
  if (!PLS.sel.has(k)) plsSelect(k);
  const ks = plsSelList(), n = ks.length;
  const items = [];
  if (r.i !== null && r.i !== undefined) {
    items.push({ label: "In Player A abspielen", run: () => plLoad({ kind: "tag", ref: r.i }, true) });
    if (typeof PL2 !== "undefined" && PL2.layout === "top") items.push({ label: "In Player B laden", run: () => dbLoad({ kind: "tag", ref: r.i }, true) });
    items.push({ label: "Im Tagger zeigen", run: () => djShowInTagger(r.i) });
  }
  if (!r.missing) items.push({ label: "Dateiordner öffnen", icon: ICON.folder, run: () => call("reveal", r.path) });
  const ws = typeof webSearchItem === "function" ? webSearchItem(e, r.artist, r.title) : null;      // #283
  if (ws) items.push(ws);
  if (items.length) items.push("-");
  items.push({ label: `Zu anderer Playlist …${n > 1 ? ` (${n})` : ""}`, run: () => plsAddDialog("paths", ks.map((j) => pl.items[j].path).filter(Boolean), pl.id) });
  if (!plsFixed(pl)) items.push({ label: "Nach oben", run: () => plsMove1(k, -1) }, { label: "Nach unten", run: () => plsMove1(k, 1) }, "-",
    { label: `Aus der Playlist entfernen${n > 1 ? ` (${n})` : ""}`, run: () => plsCall("pl_remove", pl.id, ks) });
  showMenu(e.clientX, e.clientY, items);
}

function plsMove1(k, dir) {
  const pl = plsCur(); const j = k + dir;
  if (!pl || j < 0 || j >= pl.items.length) return;
  const perm = pl.items.map((_, i) => i);
  [perm[k], perm[j]] = [perm[j], perm[k]];
  PLS.sel = new Set([j]); PLS.anchor = j;
  plsCall("pl_order", pl.id, perm);
}

async function plsExternal() {
  const r = await call("pl_external");
  if (!r.changes.length) { toast("Keine Änderungen im Playlist-Ordner."); playlistsShow(); return; }
  const what = { changed: "geändert", removed: "entfernt", new: "neu" };
  const opts = {
    changed: [["take", "Änderung übernehmen"], ["keep", "TagStudio-Fassung behalten"]],
    removed: [["keep", "Neu schreiben"], ["archive", "Playlist archivieren"]],
    new: [["take", "Als Playlist übernehmen"], ["keep", "Ignorieren"]] };
  const res = await modal({ title: "Änderungen im Playlist-Ordner", wide: true,
    html: `<div class="hint">Ein anderes Programm hat Dateien im Playlist-Ordner geändert. TagStudio überschreibt solche Dateien nicht ungefragt.<div class="muted sm" translate="no">${esc(r.mirror)}</div></div>
      <div class="fx-table"><table><thead><tr><th>Datei</th><th>Was</th><th>Entscheid</th></tr></thead><tbody>${r.changes.map((c, k) => `<tr>
        <td translate="no">${esc(c.rel)}</td><td>${what[c.kind]}</td><td>${opts[c.kind].map(([v, l], j) => `<label class="check"><input type="radio" name="plsx${k}" value="${v}"${j === 0 ? " checked" : ""}> ${esc(l)}</label>`).join(" ")}</td></tr>`).join("")}</tbody></table></div>`,
    buttons: [{ label: "Später", value: null }, { label: "Ausführen", value: true, primary: true }],
    collect: (b) => r.changes.map((c, k) => ({ rel: c.rel, action: (b.querySelector(`input[name="plsx${k}"]:checked`) || {}).value || "keep" })) });
  if (res) plsCall("pl_external_apply", res);
}

// ---------------------------------------------------------------- Tasten und Ereignisse
function plsKey(e) {
  if (S.module !== "playlists" || e.target.closest("input,select,textarea") || !$("#modal").hidden || !$("#dialog").hidden) return;
  const pl = plsCur();
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.shiftKey && (e.key === "z" || e.key === "Z")) { e.preventDefault(); e.stopImmediatePropagation(); if (PLS.st.can_undo) plsCall("pl_undo", PLS.st.sel); return; }
  if (mod && (e.key === "y" || e.key === "Y" || (e.shiftKey && (e.key === "z" || e.key === "Z")))) { e.preventDefault(); e.stopImmediatePropagation(); if (PLS.st.can_redo) plsCall("pl_redo", PLS.st.sel); return; }
  if (e.key === "F2" && pl && !pl.archived) { e.preventDefault(); plsRename(pl.id); return; }
  if (!pl || !pl.items.length) return;
  const k = PLS.anchor === null ? -1 : PLS.anchor, n = pl.items.length;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault(); e.stopPropagation();
    const dir = e.key === "ArrowDown" ? 1 : -1;
    if (e.altKey && k >= 0 && !plsFixed(pl)) { plsMove1(k, dir); return; }
    plsSelect(k < 0 ? 0 : Math.max(0, Math.min(n - 1, k + dir)), e.shiftKey ? { shiftKey: true } : null);
  } else if ((e.key === "Delete" || e.key === "Backspace") && PLS.sel.size && !plsFixed(pl)) {
    e.preventDefault(); plsCall("pl_remove", pl.id, plsSelList());
  } else if (e.key === "Enter" && k >= 0) {
    e.preventDefault(); plsPlay(k);
  } else if (mod && (e.key === "a" || e.key === "A")) {
    e.preventDefault(); PLS.sel = new Set(pl.items.map((r) => r.k)); plsRenderList();
  }
}

function plsInit() {
  $("#plsNew").addEventListener("click", () => plsNew(""));
  $("#plsNewFolder").addEventListener("click", () => plsNewFolder(""));
  $("#plsNewSmart").addEventListener("click", () => plsSmartDialog(null, ""));                 // #272
  $("#plsImport").addEventListener("click", (e) => { e.stopPropagation(); plsImportMenu(e.currentTarget); });   // #271
  $("#plsUndo").addEventListener("click", () => plsCall("pl_undo", PLS.st ? PLS.st.sel : ""));
  $("#plsRedo").addEventListener("click", () => plsCall("pl_redo", PLS.st ? PLS.st.sel : ""));
  $("#plsExt").addEventListener("click", plsExternal);
  $("#plsFolderBtn").addEventListener("click", () => { if (PLS.st && PLS.st.mirror) call("open_folder", PLS.st.mirror); });
  let qt = 0;
  $("#plsFind").addEventListener("input", (e) => { clearTimeout(qt); qt = setTimeout(() => { PLS.q = e.target.value; plsRenderTree(); }, 120); });
  const tree = $("#plsTree");
  tree.addEventListener("click", (e) => {
    const f = e.target.closest("[data-folder]"), p = e.target.closest("[data-pl]"), a = e.target.closest("[data-arch]");
    if (a) { PLS.archOpen = !PLS.archOpen; plsRenderTree(); return; }
    if (f) { const k = f.dataset.folder; PLS.closed.has(k) ? PLS.closed.delete(k) : PLS.closed.add(k); plsRenderTree(); return; }
    if (p) { if (isDoubleClick(e, "pls:" + p.dataset.pl)) { plsRename(p.dataset.pl); return; } plsCall("pl_state", p.dataset.pl).then(plsSmartAuto); }
  });
  tree.addEventListener("contextmenu", (e) => {
    const f = e.target.closest("[data-folder]"), p = e.target.closest("[data-pl]");
    if (!f && !p) { e.preventDefault(); showMenu(e.clientX, e.clientY, [{ label: "Neue Playlist …", run: () => plsNew("") }, { label: "Neue Smartlist …", run: () => plsSmartDialog(null, "") }, { label: "Neuer Ordner …", run: () => plsNewFolder("") }]); return; }
    e.preventDefault();
    if (p) plsPlMenu(e.clientX, e.clientY, p.dataset.pl); else plsFolderMenu(e.clientX, e.clientY, f.dataset.folder);
  });
  // Playlist auf einen Ordner ziehen = verschieben
  tree.addEventListener("dragstart", (e) => { const p = e.target.closest("[data-pl]"); if (!p || p.classList.contains("gone")) { e.preventDefault(); return; } PLS.dragPl = p.dataset.pl; e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", p.dataset.pl); } catch (x) { /* egal */ } });
  tree.addEventListener("dragover", (e) => { if (!PLS.dragPl && PLS.drag === null) return; const t = e.target.closest("[data-folder],[data-pl]:not(.gone)"); if (!t) return; e.preventDefault(); $$("#plsTree .drop").forEach((x) => x.classList.remove("drop")); t.classList.add("drop"); });
  tree.addEventListener("dragleave", (e) => { const t = e.target.closest(".drop"); if (t) t.classList.remove("drop"); });
  tree.addEventListener("drop", (e) => {
    const t = e.target.closest("[data-folder],[data-pl]"); $$("#plsTree .drop").forEach((x) => x.classList.remove("drop"));
    if (!t) return;
    e.preventDefault();
    if (PLS.dragPl) {                                              // Playlist → Ordner bzw. Ordner der Ziel-Playlist
      const id = PLS.dragPl; PLS.dragPl = null;
      const f = t.dataset.folder !== undefined ? t.dataset.folder : (plsMeta(t.dataset.pl) || {}).folder || "";
      const p = plsMeta(id); if (p && p.folder !== f) plsCall("pl_move", id, f);
    } else if (PLS.drag !== null && t.dataset.pl && t.dataset.pl !== PLS.st.sel && (plsMeta(t.dataset.pl) || {}).kind === "smart") {
      PLS.drag = null; toast("Smartlists füllen sich über ihre Regeln – zuerst „Einfrieren“, um sie von Hand zu ändern.");
    } else if (PLS.drag !== null && t.dataset.pl && t.dataset.pl !== PLS.st.sel) {   // Titel → andere Playlist (kopieren)
      const pl = plsCur(), ks = PLS.sel.has(PLS.drag) ? plsSelList() : [PLS.drag];
      PLS.drag = null;
      plsAddTo(t.dataset.pl, "paths", ks.map((j) => pl.items[j].path).filter(Boolean));
    }
  });
  tree.addEventListener("dragend", () => { PLS.dragPl = null; });
  $("#plsHead").addEventListener("click", (e) => {
    const b = e.target.closest("[data-plsa]"); const pl = plsCur(); if (!b || !pl) return;
    const a = b.dataset.plsa;
    if (a === "tagger") plsOpenTagger(pl.id);
    else if (a === "djset") plsOpenDjset(pl.id);
    else if (a === "addtag") { const idx = typeof tgSelected === "function" ? tgSelected() : []; if (!idx.length) toast("Im Tagger zuerst Titel markieren."); else plsAddTo(pl.id, "tag", idx); }
    else if (a === "play") plsPlayStart();                                       // #270
    else if (a === "smartrefresh") plsSmartRefresh(pl.id);                       // #272
    else if (a === "smartedit") plsSmartDialog(pl);
    else if (a === "more") { e.stopPropagation(); const r = b.getBoundingClientRect(); plsPlMenu(r.left, r.bottom + 6, pl.id); }
    else if (a === "restore") plsCall("pl_restore", pl.id);
    else if (a === "delete") plsDelete(pl.id);
  });
  const list = $("#plsList");
  list.addEventListener("click", (e) => {
    const lk = e.target.closest(".pls-link[data-url]");                       // #280: Spotify/SoundCloud-Link
    if (lk) { e.preventDefault(); e.stopPropagation(); call("open_url", lk.dataset.url); return; }
    const row = e.target.closest(".pls-row[data-k]"); if (!row) return;
    list.focus({ preventScroll: true });
    const k = +row.dataset.k;
    if (isDoubleClick(e, "pls-row:" + k)) { plsSelect(k); plsPlay(k); return; }
    plsSelect(k, e, "click");
  });
  list.addEventListener("contextmenu", (e) => { const row = e.target.closest(".pls-row[data-k]"); if (!row) return; e.preventDefault(); plsRowMenu(e, +row.dataset.k); });
  list.addEventListener("dragstart", (e) => {
    const row = e.target.closest(".pls-row[data-k]"); if (!row) return;
    PLS.drag = +row.dataset.k;
    row.classList.add("dragging");
    e.dataTransfer.effectAllowed = "copyMove";
    try { e.dataTransfer.setData("text/plain", plsRow(PLS.drag).path); } catch (x) { /* egal */ }
    const r = plsRow(PLS.drag);
    if (r.i !== null && r.i !== undefined && typeof plDragStart === "function") plDragStart(e, { kind: "tag", ref: r.i });
  });
  list.addEventListener("dragover", (e) => {
    if (PLS.drag === null) return;
    const row = e.target.closest(".pls-row[data-k]"); if (!row) return;
    e.preventDefault();
    const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
    $$("#plsList .drop-a,#plsList .drop-b").forEach((el) => el.classList.remove("drop-a", "drop-b"));
    row.classList.add(after ? "drop-b" : "drop-a");
  });
  list.addEventListener("dragend", () => { PLS.drag = null; $$("#plsList .dragging,#plsList .drop-a,#plsList .drop-b").forEach((el) => el.classList.remove("dragging", "drop-a", "drop-b")); });
  list.addEventListener("drop", (e) => {
    const row = e.target.closest(".pls-row[data-k]"), pl = plsCur(); if (PLS.drag === null || !row || !pl) return;
    e.preventDefault();
    if (plsFixed(pl)) { PLS.drag = null; return; }
    const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
    const perm = pl.items.map((_, i) => i), from = PLS.drag;
    let to = +row.dataset.k + (after ? 1 : 0);
    perm.splice(from, 1);
    if (from < to) to--;
    perm.splice(to, 0, from);
    PLS.drag = null; PLS.sel = new Set([to]); PLS.anchor = to;
    plsCall("pl_order", pl.id, perm);
  });
  document.addEventListener("keydown", plsKey, true);
  document.addEventListener("keydown", (e) => {                   // #268: Strg+Shift+P im Tagger
    if (S.module !== "tagger" || !(e.ctrlKey || e.metaKey) || !e.shiftKey || (e.key !== "p" && e.key !== "P")) return;
    if (e.target.closest("input,select,textarea") || !$("#modal").hidden) return;
    e.preventDefault(); e.stopImmediatePropagation();
    plsQuickAdd(typeof tgSelected === "function" ? tgSelected() : []);
  }, true);
}

// ---------------------------------------------------------------- Senden an DJ-Programme (#273)
async function plsPush(id, t) {
  const p = plsMeta(id); if (!p) return;
  if (!t.ready) { info(t.name, t.why || "Senden ist im Moment nicht möglich."); return; }
  const again = p.pushed && p.pushed[t.id];
  const ok = await modal({ title: `An ${t.name} senden`,
    html: `<p style="margin:0">„${esc(p.name)}“ (${fmtN(p.count)} Titel) an ${esc(t.name)} senden?</p>
      <p class="muted sm" style="margin:8px 0 0">${again ? "Die Playlist wurde schon gesendet – fehlende Titel werden dort an ihrer Stelle eingefügt." : "Dort wird eine neue Playlist mit diesem Namen angelegt."}
      Einträge ohne Datei und Titel, die dort fehlen, werden ausgelassen und gemeldet. TagStudio entfernt und löscht dort nichts.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Senden", value: true, primary: true }] });
  if (!ok) return;
  const r = await runTask(call("start_pl_push", id, t.id, {}), `An ${t.name} senden`);
  if (!r || r.cancelled) return;
  try { plsApply(await call("pl_state", PLS.st ? PLS.st.sel : id)); } catch (e) { /* egal */ }
  const miss = (r.missing || []).length;
  if (r.ok && !miss) { toast(r.message); return; }
  const btns = [{ label: "OK", value: null }];
  if (r.logfile) btns.unshift({ label: "Protokoll öffnen", value: "log" });
  const a = await modal({ title: t.name, html: `<p style="margin:0">${esc(r.message || "")}</p>${miss ? `<div class="muted sm" style="margin-top:8px">Nicht in ${esc(t.name)}:</div><div class="sm" translate="no" style="max-height:200px;overflow:auto">${r.missing.slice(0, 50).map((x) => esc(x.split(/[\\/]/).pop())).join("<br>")}${miss > 50 ? "<br>…" : ""}</div>` : ""}`, buttons: btns });
  if (a === "log") call("open_log", r.logfile).catch(() => {});
}

// ---------------------------------------------------------------- Smartlists (#272)
async function plsSmartInfo(force = false) {
  if (!PLS.smart || force) PLS.smart = await call("pl_smart_info");
  return PLS.smart;
}
const PLS_SM_SORT = { "": "keine (Reihenfolge der Datenbasis)", random: "Zufall", artist: "Künstler", title: "Titel", album: "Album", genre: "Genre",
  year: "Jahr", bpm: "BPM", key: "Tonart", rating: "Bewertung", energy: "Energie", added: "Aufgenommen", edited: "Bearbeitet", path: "Dateipfad" };

function plsSmFieldLabel(id) {
  const f = PLS.smart && PLS.smart.fields.find((x) => x.id === id);
  return f ? f.label : id;
}
function plsSmNum(x) { return x === null || x === undefined ? "" : String(Math.round(x * 100) / 100).replace(".", ","); }

/** Kurzfassung der Regeln im Kopf – jeder Teil ein eigener Textknoten (Übersetzung) */
function plsSmartSummary(r) {
  if (!r) return "";
  const sp = (t) => `<span>${esc(t)}</span>`, val = (t) => `<span translate="no">${esc(t)}</span>`;
  const one = (x) => {
    const lab = sp(plsSmFieldLabel(x.f)), op = PLS.smart ? PLS.smart.op_labels[x.op] : x.op;
    if (x.op === "empty" || x.op === "not_empty") return `${lab} ${sp(op)}`;
    if (x.op === "yes" || x.op === "no") return `${lab}: ${sp(op)}`;
    if (x.op === "between") return `${lab} ${val(`${plsSmNum(x.a) || "…"}–${plsSmNum(x.b) || "…"}`)}`;
    if (x.op === "gte" || x.op === "lte" || x.op === "eq") return `${lab} ${val(`${{ gte: "≥", lte: "≤", eq: "=" }[x.op]} ${plsSmNum(x.a)}`)}`;
    if (x.op === "days") return `${lab}: ${sp(`letzte ${x.a} Tage`)}`;
    if (x.f === "origin") { const o = PLS.smart && PLS.smart.origins.find((y) => y.id === x.a); return `${lab} ${sp(op)} ${val(o ? o.name : x.a)}`; }
    const a = Array.isArray(x.a) ? x.a.join(", ") : x.a;
    return `${lab} ${sp(op)} ${val(x.f === "key" ? a : `„${a}“`)}`;
  };
  const base = r.base.kind === "tagger" ? "Im Tagger geladene Titel" : r.base.kind === "playlist" ? "Aus Playlist" : "Bibliothek";
  const bp = r.base.kind === "playlist" ? (plsMeta(r.base.pid) || {}).name || "?" : "";
  const parts = [`⚡ ${sp(base)}${bp ? ` ${val(`„${bp}“`)}` : ""}`];
  if (r.rules.length) parts.push((r.match === "any" && r.rules.length > 1 ? `${sp("Eine Regel erfüllt")}: ` : "") + r.rules.map(one).join(" · "));
  else parts.push(sp("ohne Regeln (alle Titel)"));
  if (r.sort) parts.push(`${sp("sortiert nach")} ${sp(PLS_SM_SORT[r.sort] || r.sort)}${r.desc && r.sort !== "random" ? " ↓" : ""}`);
  if (r.limit) parts.push(`${sp("höchstens")} ${val(fmtN(r.limit))}`);
  return parts.join(" · ");
}

/** Beim Öffnen neu bilden, wenn noch nie oder vor mehr als 15 Minuten gebildet (S3) */
function plsSmartAuto(st) {
  const pl = st && st.pl;
  if (!pl || pl.kind !== "smart" || pl.archived || PLS.busy) return;
  PLS.smartTried = PLS.smartTried || new Set();
  if (Date.now() / 1000 - (pl.refreshed || 0) < 900 || PLS.smartTried.has(pl.id)) return;
  PLS.smartTried.add(pl.id);
  plsSmartRefresh(pl.id, true);
}

async function plsSmartRefresh(id, quiet = false) {
  const r = await runTask(call("start_pl_smart_refresh", id), "Smartlist aktualisieren");
  if (!r || r.cancelled) return;
  try { plsApply(await call("pl_state", id)); } catch (e) { toast(String(e.message || e)); return; }
  if (!quiet || r.changed) toast(`${fmtN(r.count)} von ${fmtN(r.scanned)} Titeln erfüllen die Regeln.`);
}

async function plsSmartFreeze(id) {
  const p = plsMeta(id); if (!p) return;
  const ok = await modal({ title: "Smartlist einfrieren", html: `<p style="margin:0">„${esc(p.name)}“ wird zu einer normalen Playlist mit den ${fmtN(p.count)} aktuellen Titeln. Die Regeln fallen weg (Rückgängig mit Strg+Z).</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Einfrieren", value: true, primary: true }] });
  if (ok) plsCall("pl_smart_freeze", id);
}

/** Regel-Dialog: Datenbasis, alle/eine Regel, Regeln, Sortierung, Höchstzahl. pl = null → neue Smartlist */
async function plsSmartDialog(pl, folder = "") {
  let info;
  try { info = await plsSmartInfo(true); } catch (e) { toast(String(e.message || e)); return; }
  const r0 = JSON.parse(JSON.stringify(pl && pl.rules ? pl.rules : info.default));
  const rules = r0.rules.map((x) => ({ ...x }));
  const ftype = (f) => (info.fields.find((x) => x.id === f) || {}).type || "text";
  const opSel = (x) => `<select class="inp sm" data-smop>${info.ops[ftype(x.f)].map((o) => `<option value="${o}"${o === x.op ? " selected" : ""}>${esc(info.op_labels[o])}</option>`).join("")}</select>`;
  const valIn = (x) => {
    const t = ftype(x.f), a = x.a ?? "", b = x.b ?? "";
    if (["empty", "not_empty", "yes", "no"].includes(x.op)) return "";
    if (t === "num" && x.op === "between") return `<input class="inp sm" type="number" step="any" data-sma value="${esc(a)}" placeholder="von" style="width:80px"> – <input class="inp sm" type="number" step="any" data-smb value="${esc(b)}" placeholder="bis" style="width:80px">`;
    if (t === "num") return `<input class="inp sm" type="number" step="any" data-sma value="${esc(a)}" style="width:90px"${x.f === "rating" ? ' min="0" max="5"' : ""}>`;
    if (t === "date" && x.op === "days") return `<input class="inp sm" type="number" min="1" data-sma value="${esc(a)}" style="width:80px"> <span class="muted sm">Tage</span>`;
    if (t === "date") return `<input class="inp sm" type="date" data-sma value="${esc(a)}">`;
    if (t === "origin") return `<select class="inp sm" data-sma>${info.origins.map((o) => `<option value="${esc(o.id)}"${o.id === a ? " selected" : ""} translate="no">${esc(o.name)}</option>`).join("")}</select>`;
    if (t === "key") return `<input class="inp sm" data-sma value="${esc(Array.isArray(a) ? a.join(", ") : a)}" placeholder="${x.op === "fits" ? "z. B. 8A" : "z. B. 8A, 9A"}" style="width:120px">`;
    return `<input class="inp sm" data-sma value="${esc(a)}" style="width:180px">`;
  };
  const rowHtml = (x, k) => `<div class="pls-sm-rule" data-smk="${k}"><select class="inp sm" data-smf>${info.fields.map((f) => `<option value="${f.id}"${f.id === x.f ? " selected" : ""}>${esc(f.label)}</option>`).join("")}</select>
    ${opSel(x)} <span class="pls-sm-val">${valIn(x)}</span><button class="ghost sm" data-smdel title="Regel entfernen" aria-label="Regel entfernen">✕</button></div>`;
  const base = r0.base || { kind: "library", pid: "" };
  const html = `${pl ? "" : `<div class="pls-newrow"><input class="inp" id="plsSmName" placeholder="Name" maxlength="120" value=""><input class="inp" id="plsSmFolder" list="plsSmFolders" placeholder="Ordner (optional)" value="${esc(folder)}"><datalist id="plsSmFolders">${(PLS.st ? PLS.st.folders : []).map((f) => `<option value="${esc(f)}">`).join("")}</datalist></div>`}
    <div class="pls-sm-sec"><b>Datenbasis</b>
      <label class="check"><input type="radio" name="plsSmBase" value="library"${base.kind === "library" ? " checked" : ""}> Bibliothek</label>
      <label class="check"><input type="radio" name="plsSmBase" value="tagger"${base.kind === "tagger" ? " checked" : ""}> Im Tagger geladene Titel (${fmtN(info.tagger)})</label>
      <label class="check"><input type="radio" name="plsSmBase" value="playlist"${base.kind === "playlist" ? " checked" : ""}${info.playlists.length ? "" : " disabled"}> Aus Playlist:</label>
      <select class="inp sm" id="plsSmPl"${info.playlists.length ? "" : " hidden"}>${info.playlists.filter((p) => !pl || p.id !== pl.id).map((p) => `<option value="${esc(p.id)}"${p.id === base.pid ? " selected" : ""} translate="no">${esc(p.label)}</option>`).join("")}</select>
      <div class="muted sm">${libNamesHtml(info.roots, info.libs, info.libs_skipped)}</div></div>
    <div class="pls-sm-sec"><b>Regeln</b>
      <label class="check"><input type="radio" name="plsSmMatch" value="all"${r0.match !== "any" ? " checked" : ""}> alle erfüllt</label>
      <label class="check"><input type="radio" name="plsSmMatch" value="any"${r0.match === "any" ? " checked" : ""}> mindestens eine erfüllt</label>
      <div id="plsSmRules"></div><button class="ghost sm" id="plsSmAdd">+ Regel</button></div>
    <div class="pls-sm-sec"><b>Sortierung</b> <select class="inp sm" id="plsSmSort">${info.sorts.map((k) => `<option value="${k}"${k === (r0.sort || "") ? " selected" : ""}>${esc(PLS_SM_SORT[k] || k)}</option>`).join("")}</select>
      <label class="check"><input type="checkbox" id="plsSmDesc"${r0.desc ? " checked" : ""}> absteigend</label>
      <label class="check">Höchstens <input class="inp sm" type="number" min="0" id="plsSmLimit" value="${r0.limit || ""}" placeholder="alle" style="width:80px"> Titel</label></div>`;
  const read = (b) => {                      // Werte der Zeilen in rules übernehmen
    b.querySelectorAll("[data-smk]").forEach((row) => {
      const x = rules[+row.dataset.smk]; if (!x) return;
      const a = row.querySelector("[data-sma]"), bb = row.querySelector("[data-smb]");
      x.a = a ? a.value : undefined; x.b = bb ? bb.value : undefined;
    });
  };
  const draw = (b) => { $("#plsSmRules", b).innerHTML = rules.map(rowHtml).join("") || '<div class="muted sm">Keine Regel – alle Titel der Datenbasis.</div>'; };
  const res = await modal({ title: pl ? `Regeln: ${pl.name}` : "Neue Smartlist", wide: true, html,
    buttons: [{ label: "Abbrechen", value: null }, { label: pl ? "Speichern und aktualisieren" : "Anlegen", value: true, primary: true }],
    onMount: (b) => {
      draw(b);
      const nm = $("#plsSmName", b); if (nm) nm.focus();
      $("#plsSmAdd", b).addEventListener("click", () => { read(b); rules.push({ f: "genre", op: "contains", a: "" }); draw(b); });
      $("#plsSmPl", b).addEventListener("change", () => { b.querySelector('input[name="plsSmBase"][value="playlist"]').checked = true; });
      b.addEventListener("click", (e) => { const d = e.target.closest("[data-smdel]"); if (!d) return; read(b); rules.splice(+d.closest("[data-smk]").dataset.smk, 1); draw(b); });
      b.addEventListener("change", (e) => {
        const row = e.target.closest("[data-smk]"); if (!row) return;
        const x = rules[+row.dataset.smk];
        if (e.target.matches("[data-smf]")) { x.f = e.target.value; x.op = info.ops[ftype(x.f)][0]; x.a = ""; x.b = ""; draw(b); }
        else if (e.target.matches("[data-smop]")) { read(b); x.op = e.target.value; draw(b); }
      });
    },
    collect: (b) => {
      read(b);
      const name = pl ? pl.name : $("#plsSmName", b).value.trim();
      if (!name) { toast("Bitte einen Namen eingeben."); $("#plsSmName", b).focus(); return false; }
      const kind = (b.querySelector('input[name="plsSmBase"]:checked') || {}).value || "library";
      return { name, folder: pl ? pl.folder : $("#plsSmFolder", b).value.trim(),
        rules: { base: { kind, pid: kind === "playlist" ? $("#plsSmPl", b).value : "" }, match: (b.querySelector('input[name="plsSmMatch"]:checked') || {}).value || "all",
          rules, sort: $("#plsSmSort", b).value, desc: $("#plsSmDesc", b).checked, limit: +$("#plsSmLimit", b).value || 0 } };
    } });
  if (!res) return;
  const st = await plsCall("pl_smart_save", pl ? pl.id : "", res.name, res.folder, res.rules);
  if (st && st.sel) plsSmartRefresh(st.sel, true);
}

/** Tagger wurde neu geladen → Indizes der Playlist-Titel neu auflösen */
function plsAfterTaggerLoad() {
  if (S.module === "playlists") playlistsShow();
  plsRecentRefresh();
}

plsInit();
plsRecentRefresh();
if (typeof S !== "undefined" && S.module === "playlists" && !PLS.st) playlistsShow();
else setTimeout(() => { if (!PLS.st) call("pl_state", "").then((st) => { PLS.st = st; plsSideCount(st); }).catch(() => {}); }, 900);
