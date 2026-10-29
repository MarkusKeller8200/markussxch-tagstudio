/* MarKusSXCH TagStudio – Ideen (#186): Wunschlisten für Titel, die später gekauft werden sollen. Gemerkt wird in
   „Entdecken“ („Idee merken ▸“), von Hand oder aus Text; Status Idee → Kaufen → Gekauft → In Bibliothek. Wunschlisten
   sind Playlists (Ordner „Ideen“). Logik in ideas.py / session_ideas.py. Beatport wird nur auf Klick verändert. */
"use strict";

const IDEA = { d: null, filter: "open", playing: "", checked: new Set() };
const IDEA_FILTERS = [["open", "Offen"], ["buy", "Kaufen"], ["bought", "Gekauft"], ["lib", "In Bibliothek"], ["dropped", "Verworfen"], ["all", "Alle"]];
const IDEA_STATUS = { idea: "Idee", buy: "Kaufen", bought: "Gekauft", lib: "In Bibliothek", dropped: "Verworfen" };
const IDEA_SRC = { deezer: "Deezer", beatport: "Beatport", spotify: "Spotify", manual: "von Hand", text: "Text", discover: "Entdecken" };

async function ideasShow(sel) {
  try { ideasApply(await call("ideas_overview", sel || (IDEA.d && IDEA.d.sel) || "")); } catch (e) { toast(String(e.message || e)); }
}

function ideasApply(d) {
  if (IDEA.d && IDEA.d.sel !== d.sel) IDEA.checked.clear();
  IDEA.d = d;
  ideasBadge(d.buy);
  $("#ideaLists").innerHTML = `<div class="idea-lh"><b>Wunschlisten</b><button class="icon-btn" id="ideaNewList" title="Neue Wunschliste …" aria-label="Neue Wunschliste">＋</button></div>`
    + (d.lists.length ? d.lists.map((l) => `<button class="idea-l${l.id === d.sel ? " on" : ""}" data-l="${esc(l.id)}" aria-current="${l.id === d.sel}" title="${esc(`${l.name}: ${l.counts.idea} Idee · ${l.counts.buy} Kaufen · ${l.counts.bought} gekauft · ${l.counts.lib} in Bibliothek`)}">
        <span class="nm ellipsis" translate="no">${esc(l.name)}</span><span class="n">${fmtN(l.count)}</span>${l.counts.buy ? `<span class="b" title="Zum Kauf vorgemerkt">${fmtN(l.counts.buy)}</span>` : ""}</button>`).join("")
      : '<div class="muted sm" style="padding:8px">Noch keine Wunschliste. In „Entdecken“ „Idee merken ▸“ oder hier „＋“.</div>');
  const l = ideasCur(), c = l ? l.counts : {};
  const n = (k) => k === "open" ? (c.idea || 0) + (c.buy || 0) : k === "all" ? (l ? l.count : 0) : c[k] || 0;
  $("#ideaFilter").innerHTML = IDEA_FILTERS.map(([k, t]) => `<button data-f="${k}" role="radio" aria-checked="${k === IDEA.filter}" class="${k === IDEA.filter ? "on" : ""}">${t}${n(k) ? ` <span class="muted">${fmtN(n(k))}</span>` : ""}</button>`).join("");
  $("#ideaTitle").textContent = l ? l.name : "";
  const bp = d.beatport || {};
  $("#ideaBp").disabled = !l;
  $("#ideaBp").title = !bp.available ? "Beatport-Plugin aus oder nicht angemeldet" : !bp.write ? "Im Beatport-Plugin „Playlists in Beatport schreiben“ einschalten" : `Als Beatport-Playlist ${l ? l.bp : ""} anlegen bzw. ergänzen (nur Titel mit Beatport-ID)`;
  $("#ideaMatch").disabled = !l || !d.library;
  $("#ideaMatch").title = d.library ? "Einträge ohne Datei in der Bibliothek suchen und sichere Treffer verknüpfen" : "Keine Bibliothek festgelegt (Einstellungen › Speicherort und Ordner)";
  $("#ideaAdd").disabled = !l;
  $("#ideaInfo").textContent = l ? `${fmtN(l.count)} Einträge · ${fmtN(c.buy || 0)} zum Kauf vorgemerkt · ${fmtN(c.bought || 0)} gekauft · ${fmtN(c.lib || 0)} in der Bibliothek${l.pushed ? ` · in Beatport: ${l.bp}` : ""}` : "";
  ideasRender();
}

function ideasCur() { return IDEA.d ? IDEA.d.lists.find((l) => l.id === IDEA.d.sel) || null : null; }

function ideasRows() {
  const q = ($("#ideaSearch").value || "").toLowerCase().trim(), f = IDEA.filter;
  return IDEA.d.items.filter((e) => (f === "all" || (f === "open" ? e.status === "idea" || e.status === "buy" : e.status === f))
    && (!q || `${e.artist} ${e.title} ${e.mix} ${e.label} ${e.note}`.toLowerCase().includes(q)));
}

function ideasRender() {
  const box = $("#ideaList");
  if (!ideasCur()) { box.innerHTML = '<div class="tg-empty">Links eine Wunschliste wählen oder mit „＋“ eine neue anlegen.</div>'; ideasSelInfo(); return; }
  const rows = ideasRows();
  if (!rows.length) {
    box.innerHTML = `<div class="tg-empty">${IDEA.d.items.length ? "Nichts in dieser Ansicht." : "Diese Wunschliste ist leer – „+ Hinzufügen ▾“ oder in „Entdecken“ „Idee merken ▸“."}</div>`;
    ideasSelInfo();
    return;
  }
  const all = rows.every((e) => IDEA.checked.has(e.k));
  box.innerHTML = `<table class="disc-t idea-t"><thead><tr><th><input type="checkbox" id="ideaAll" aria-label="Alle markieren" ${all ? "checked" : ""}></th><th></th><th></th><th>Künstler</th><th>Titel</th><th>Label</th><th>Datum</th><th>Quelle</th><th>Status</th><th>Notiz</th><th></th></tr></thead><tbody>
    ${rows.map((e) => `<tr data-k="${e.k}" class="ist-${e.status}">
      <td><input type="checkbox" data-c ${IDEA.checked.has(e.k) ? "checked" : ""} aria-label="Markieren"></td>
      <td><button class="icon-btn play ${IDEA.playing === String(e.k) ? "on" : ""}" data-a="play" ${e.preview || e.store === "deezer" ? "" : "disabled"} title="${e.preview || e.store === "deezer" ? "Vorhören (Ausschnitt)" : "kein Vorhör-Ausschnitt"}" aria-label="Vorhören">${IDEA.playing === String(e.k) ? "❚❚" : "▶"}</button></td>
      <td class="cv">${e.cover ? `<img src="${esc(e.cover)}" alt="" loading="lazy" referrerpolicy="no-referrer"><img class="big" src="${esc(e.cover)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}</td>
      <td class="ell" title="${esc(e.artist)}">${esc(e.artist)}</td>
      <td class="ell nm" title="${esc(e.title + (e.mix ? ` (${e.mix})` : ""))}"><b>${esc(e.title)}</b>${e.mix ? ` <span class="muted">(${esc(e.mix)})</span>` : ""}</td>
      <td class="ell sm" title="${esc([e.label, e.release].filter(Boolean).join(" – "))}">${esc(e.label || "")}</td>
      <td class="sm nw">${esc((e.date || "").slice(0, 10))}</td>
      <td class="sm nw">${esc(IDEA_SRC[e.src] || e.src || "")}</td>
      <td class="sm nw"><span class="idea-st st-${e.status}" title="${e.status === "bought" ? (e.bought === "ja" ? "Steht unter „Einkäufe“" : "Laut „Einkäufe“ gekauft am " + esc(e.bought)) : e.status === "lib" ? esc(e.path) : ""}">${IDEA_STATUS[e.status] || e.status}</span></td>
      <td class="ell sm idea-note" data-a="note" title="${esc(e.note || "Notiz bearbeiten")}">${e.note ? esc(e.note) : '<span class="muted">＋</span>'}</td>
      <td class="d-acts"><div class="d-row"><button class="ghost sm" data-a="open" ${e.url ? "" : "disabled"} title="${esc(!e.url ? "Kein Link" : IDEA_SRC[e.src] ? `Auf ${IDEA_SRC[e.src]} öffnen (Kauf nur dort)` : "Bei der Quelle öffnen (Kauf nur dort)")}">Öffnen</button>
        ${e.set !== "buy" ? '<button class="icon-btn" data-a="buy" title="Zum Kauf vormerken">🛒</button>' : '<button class="icon-btn on" data-a="idea" title="Nicht mehr zum Kauf vormerken">🛒</button>'}
        ${e.set !== "dropped" ? '<button class="icon-btn" data-a="dropped" title="Verwerfen (bleibt unter „Verworfen“)">✕</button>' : '<button class="icon-btn" data-a="idea" title="Wieder als Idee">↺</button>'}
        <button class="icon-btn" data-a="menu" title="Weitere Aktionen" aria-haspopup="menu">⋯</button></div></td></tr>`).join("")}
    </tbody></table>`;
  ideasSelInfo();
}

function ideasSelInfo() {
  const n = IDEA.checked.size;
  $("#ideaSel").hidden = !n;
  $("#ideaSelN").textContent = n ? `${fmtN(n)} markiert` : "";
}

function ideasStop() {
  const a = $("#ideaAudio");
  if (a) { a.pause(); a.removeAttribute("src"); }
  if (IDEA.playing) { IDEA.playing = ""; if (IDEA.d) ideasRender(); }
}

async function ideasPlay(e) {
  if (IDEA.playing === String(e.k)) { ideasStop(); return; }
  const url = await call("ideas_preview", IDEA.d.sel, e.k);
  if (!url) { toast("Kein Vorhör-Ausschnitt – „Öffnen“ zeigt den Titel bei der Quelle."); return; }
  try { if (typeof PLAYER !== "undefined" && PLAYER.audio && !PLAYER.audio.paused) PLAYER.audio.pause(); } catch (x) { /* Player nicht aktiv */ }
  if (typeof discStop === "function") discStop();
  const a = $("#ideaAudio");
  a.src = url;
  a.play().catch((x) => toast("Vorhören nicht möglich: " + (x.message || x)));
  IDEA.playing = String(e.k);
  ideasRender();
}

async function ideasDo(fn, ...args) {
  try { const d = await call(fn, ...args); ideasApply(d); return d; } catch (e) { toast(String(e.message || e)); return null; }
}

async function ideasNameDialog(title, value = "", label = "Speichern") {
  return modal({
    title, html: `<label for="ideaNm">Name</label><input id="ideaNm" class="inp" type="text" value="${esc(value)}" maxlength="120" style="width:100%" autofocus>`,
    buttons: [{ label: "Abbrechen", value: null }, { label, value: true, primary: true }],
    collect: (b) => { const v = $("#ideaNm", b).value.trim(); if (!v) { $("#ideaNm", b).focus(); return false; } return v; },
  });
}

async function ideasNewList() {
  const n = await ideasNameDialog("Neue Wunschliste", "", "Anlegen");
  if (n) await ideasDo("ideas_list_create", n);
}

function ideasListMenu(ev, id) {
  const l = IDEA.d.lists.find((x) => x.id === id); if (!l) return;
  ev.preventDefault();
  showMenu(ev.clientX, ev.clientY, [
    { label: "Umbenennen …", run: async () => { const n = await ideasNameDialog("Wunschliste umbenennen", l.name); if (n && n !== l.name) await ideasDo("ideas_list_rename", id, n); } },
    { label: "Als Playlist übernehmen …", run: () => ideasToPlaylist(id) },
    { label: "Als Excel exportieren", run: () => ideasExport("xlsx", id) },
    "-",
    { label: "Archivieren …", run: () => ideasArchive(l) },
  ]);
}

async function ideasArchive(l) {
  const others = IDEA.d.lists.filter((x) => x.id !== l.id);
  const res = await modal({
    title: "Wunschliste archivieren",
    html: `<p style="margin:0 0 8px">„${esc(l.name)}“ (${fmtN(l.count)} Einträge) wird archiviert – unter Playlists › Archiv lässt sie sich zurückholen.</p>
      ${others.length && l.count ? `<label class="check"><input type="checkbox" id="ideaMv"> Einträge vorher verschieben nach</label> <select id="ideaMvTo">${others.map((o) => `<option value="${esc(o.id)}">${esc(o.name)}</option>`).join("")}</select>` : ""}`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Archivieren", value: true, primary: true }],
    collect: (b) => ({ to: $("#ideaMv", b) && $("#ideaMv", b).checked ? $("#ideaMvTo", b).value : "" }),
  });
  if (!res) return;
  await ideasDo("ideas_list_archive", l.id, res.to);
  status(`Wunschliste „${l.name}“ archiviert.`, "info");
}

function ideasAddMenu() {
  const b = $("#ideaAdd").getBoundingClientRect();
  showMenu(b.left, b.bottom + 6, [
    { label: "Titel von Hand …", run: ideasManual },
    { label: "Liste aus Text einfügen …", run: ideasText },
    { label: "Aus Entdecken …", run: () => setModule("discover") }, "-",
    { label: "Läuft gerade in Spotify merken", run: ideasSpotifyNow },          // #384 SP2
    { label: "Zuletzt gehört in Spotify …", run: ideasSpotifyRecent },
  ]);
}

/** #384: Spotify bereit? Sonst erklären (Plugin aus, nicht angemeldet, Berechtigung fehlt) → false */
async function ideasSpotifyReady(need) {
  const sp = (IDEA.d && IDEA.d.spotify) || {};
  if (!sp.available) { await info("Spotify", `Spotify ist nicht bereit: ${sp.why || "Plugin aus"}. Unter Plugins › Spotify einschalten und „Anmelden …“.`); return false; }
  if (need && (sp.missing || []).includes(need)) {
    await info("Spotify", "Für diese Funktion fehlt eine neue Berechtigung – bitte unter Plugins › Spotify einmal „Anmelden …“ (die Anmeldung fragt die zusätzlichen Berechtigungen ab).");
    return false;
  }
  return true;
}

async function ideasSpotifyNow() {
  if (!(await ideasSpotifyReady("user-read-currently-playing"))) return;
  let r;
  try { r = await call("ideas_spotify_now"); } catch (e) { return toast(String(e.message || e)); }
  if (!r.track) { await info("Läuft gerade", r.playing ? "In Spotify läuft gerade kein Musiktitel (z. B. Podcast oder Werbung)." : "In Spotify läuft gerade nichts."); return; }
  const t = r.track;
  const ok = await dialog({ title: "Läuft gerade in Spotify", text: `${t.artist} – ${t.title}${t.mix ? ` (${t.mix})` : ""}\n\nAls Idee in „${(ideasCur() || {}).name || "Ideen"}“ merken?`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Merken", value: true, primary: true }] });
  if (!ok) return;
  try {
    const a = await call("ideas_add_spotify", IDEA.d.sel, [t], "");
    toast(a.added ? "Als Idee gemerkt." : "Steht schon in der Wunschliste.");
    await ideasShow(a.pid);
  } catch (e) { toast(String(e.message || e)); }
}

async function ideasSpotifyRecent() {
  if (!(await ideasSpotifyReady())) return;
  let r;
  try { r = await call("ideas_spotify_recent", 50); } catch (e) { return toast(String(e.message || e)); }
  if (!r.tracks.length) { await info("Zuletzt gehört", "Spotify meldet keine zuletzt gehörten Titel."); return; }
  const when = (s) => (s ? s.replace("T", " ").slice(0, 16) : "");
  const pick = await modal({ title: "Zuletzt gehört in Spotify", wide: true,
    html: `<p class="muted sm" style="margin:0 0 6px">Neueste zuerst (Spotify liefert höchstens 50). Markierte kommen als Ideen in „${esc((ideasCur() || {}).name || "Ideen")}“.</p>
      <div class="ab-list">${r.tracks.map((t, i) => `<label class="check sm"><input type="checkbox" data-spr="${i}"> <span translate="no">${esc(t.artist)} – ${esc(t.title)}${t.mix ? ` (${esc(t.mix)})` : ""}</span> <span class="muted">${esc(when(t.played_at))}</span></label>`).join("")}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Als Ideen merken", value: true, primary: true }],
    collect: (b) => [...b.querySelectorAll("[data-spr]:checked")].map((x) => r.tracks[+x.dataset.spr]) });
  if (!pick || !pick.length) return;
  try {
    const a = await call("ideas_add_spotify", IDEA.d.sel, pick, "");
    toast(`${fmtN(a.added)} gemerkt${a.dupes ? `, ${fmtN(a.dupes)} schon vorhanden` : ""}.`);
    await ideasShow(a.pid);
  } catch (e) { toast(String(e.message || e)); }
}

/** #384 SP5: Wunschliste als private Spotify-Playlist – nur auf Klick, es wird nichts entfernt */
async function ideasSpotifyPush() {
  if (!(await ideasSpotifyReady("playlist-modify-private"))) return;
  const pv = await call("ideas_sp_preview", IDEA.d.sel);
  if (!pv.count) { await info("Als Spotify-Playlist", "Kein offener Eintrag mit Spotify-Link bzw. -ID. Titel aus „Läuft gerade“, „Zuletzt gehört“ oder mit einem open.spotify.com-Link haben eine."); return; }
  const ok = await dialog({ title: "Als Spotify-Playlist",
    text: `In deinem Spotify-Konto die private Playlist „${pv.name}“ ${pv.pushed && pv.pushed.id ? "ergänzen" : "anlegen bzw. ergänzen"}: ${fmtN(pv.count)} Titel.${pv.without ? ` ${fmtN(pv.without)} Einträge ohne Spotify-ID bleiben aussen vor.` : ""} Vorhandene Titel der Playlist bleiben, es wird nichts entfernt.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "In Spotify anlegen", value: true, primary: true }] });
  if (!ok) return;
  const r = await runTask(call("start_ideas_sp", IDEA.d.sel), "Spotify – Wunschliste");
  if (!r) return;
  const go = await dialog({ title: "Als Spotify-Playlist", text: r.message || "Fertig.",
    buttons: [{ label: "OK", value: null }, ...(r.url ? [{ label: "In Spotify öffnen", value: true, primary: true }] : [])] });
  if (go && r.url) call("open_url", r.url);
  ideasShow();
}

async function ideasManual() {
  const res = await modal({
    title: "Idee von Hand",
    html: `<div class="frm"><label for="imA">Künstler</label><input id="imA" class="inp" type="text" autofocus>
      <label for="imT">Titel</label><input id="imT" class="inp" type="text">
      <label for="imM">Mix</label><input id="imM" class="inp" type="text" placeholder="z. B. Extended Mix">
      <label for="imU">Link</label><input id="imU" class="inp" type="url" placeholder="https://…">
      <label for="imN">Notiz</label><input id="imN" class="inp" type="text"></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Hinzufügen", value: true, primary: true }],
    collect: (b) => ({ artist: $("#imA", b).value, title: $("#imT", b).value, mix: $("#imM", b).value, url: $("#imU", b).value, note: $("#imN", b).value }),
  });
  if (!res) return;
  try {
    const r = await call("ideas_add_manual", IDEA.d.sel, res);
    toast(r.added ? "Idee hinzugefügt." : "Steht schon in der Wunschliste.");
    await ideasShow(r.pid);
  } catch (e) { toast(String(e.message || e)); }
}

async function ideasText() {
  const text = await modal({
    title: "Liste aus Text einfügen",
    html: `<p class="muted sm" style="margin:0 0 6px">Je Zeile „Künstler - Titel (Mix)“ – z. B. aus einer Trackliste, einem Chat oder Notizen. Nummern und Zeitmarken fallen weg.</p><textarea id="itTxt" class="fe-val" style="width:100%;min-height:200px" spellcheck="false" autofocus></textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: true, primary: true }],
    collect: (b) => $("#itTxt", b).value,
  });
  if (!text || !text.trim()) return;
  try {
    const r = await call("ideas_add_text", IDEA.d.sel, text);
    status(`${fmtN(r.added)} Idee(n) übernommen${r.dupes ? `, ${fmtN(r.dupes)} schon vorhanden` : ""}${r.unknown ? `, ${fmtN(r.unknown)} unbekannte (ID) ausgelassen` : ""}.`, "info");
    await ideasShow(r.pid);
  } catch (e) { toast(String(e.message || e)); }
}

function ideasMoreMenu() {
  const b = $("#ideaMore").getBoundingClientRect(), l = ideasCur();
  showMenu(b.left, b.bottom + 6, [
    ...(l ? [{ label: "Als Playlist übernehmen …", run: () => ideasToPlaylist(l.id) },
      { label: "Als Spotify-Playlist …", run: ideasSpotifyPush },                // #384 SP5
      { label: "Diese Wunschliste als Excel", run: () => ideasExport("xlsx", l.id) },
      { label: "Diese Wunschliste als CSV", run: () => ideasExport("csv", l.id) }] : []),
    { label: "Alle Wunschlisten als Excel", run: () => ideasExport("xlsx", "") }, "-",
    ...(IDEA.d.undo ? [{ label: "Rückgängig", run: async () => { const d = await ideasDo("ideas_undo", IDEA.d.sel); if (d) status(d.message, "info"); } }] : []),
    ...(l ? ["-", { label: "Wunschliste umbenennen …", run: async () => { const n = await ideasNameDialog("Wunschliste umbenennen", l.name); if (n && n !== l.name) await ideasDo("ideas_list_rename", l.id, n); } },
      { label: "Wunschliste archivieren …", run: () => ideasArchive(l) }] : []),
  ]);
}

async function ideasExport(fmt, pid) {
  const r = await call("ideas_export", fmt, pid);
  if (r && r.ok) status(r.message, "info"); else if (r && r.error) toast(r.error);
}

async function ideasToPlaylist(pid) {
  const l = IDEA.d.lists.find((x) => x.id === pid); if (!l) return;
  const n = await ideasNameDialog("Als Playlist übernehmen", l.name, "Übernehmen");
  if (!n) return;
  try {
    const r = await call("ideas_to_playlist", pid, n, "");
    const go = await dialog({ title: "Playlist angelegt", text: `„${r.name}“ mit ${fmtN(r.count)} Einträgen. Titel ohne Datei stehen dort als Einkaufsliste.`,
      buttons: [{ label: "Hier bleiben", value: null }, { label: "Zur Playlist", value: true, primary: true }] });
    if (go) { if (typeof PLS !== "undefined") PLS.st = Object.assign(PLS.st || {}, { sel: r.pid }); setModule("playlists"); }
  } catch (e) { toast(String(e.message || e)); }
}

async function ideasMatch() {
  const r = await runTask(call("start_ideas_match", IDEA.d.sel), "Wunschliste mit der Bibliothek abgleichen");
  if (!r) return;
  status(r.linked ? `${fmtN(r.linked)} Titel in der Bibliothek gefunden und verknüpft.` : "Keine sicheren Treffer in der Bibliothek.", "info");
  ideasShow();
}

async function ideasBeatport() {
  const pv = await call("ideas_bp_preview", IDEA.d.sel);
  if (!pv.available || !pv.write) {
    await info("Als Beatport-Playlist", !pv.available ? "Das Beatport-Plugin ist aus oder nicht angemeldet (Plugins › Beatport)."
      : "Im Beatport-Plugin unter „Einstellungen“ zuerst „Playlists in Beatport schreiben“ einschalten.");
    return;
  }
  if (!pv.count) { await info("Als Beatport-Playlist", "Kein offener Eintrag mit Beatport-ID. Nur Vorschläge von Beatport (Entdecken) haben eine."); return; }
  const ok = await dialog({ title: "Als Beatport-Playlist",
    text: `In deinem Beatport-Konto die Playlist „${pv.name}“ anlegen bzw. ergänzen: ${fmtN(pv.count)} Titel.${pv.without ? ` ${fmtN(pv.without)} Einträge ohne Beatport-ID bleiben aussen vor.` : ""} Es wird nichts gekauft; vorhandene Titel der Playlist bleiben.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "In Beatport anlegen", value: true, primary: true }] });
  if (!ok) return;
  const r = await runTask(call("start_ideas_bp", IDEA.d.sel), "Beatport – Wunschliste");
  if (!r) return;
  status(`${r.name}: ${fmtN(r.added || 0)} Titel ergänzt${r.created ? " (neu angelegt)" : ""}.${r.note ? " " + r.note : ""}`, "info");
  ideasShow();
}

function ideasPickList(ev, ks, copyOnly) {
  const others = IDEA.d.lists.filter((x) => x.id !== IDEA.d.sel);
  if (!others.length) { toast("Zuerst eine zweite Wunschliste anlegen („＋“)."); return; }
  setTimeout(() => showMenu(ev.clientX, ev.clientY, others.map((o) => ({ label: o.name, run: async () => {
    const d = await ideasDo("ideas_move", IDEA.d.sel, ks, o.id, !!copyOnly);
    if (d) { IDEA.checked.clear(); ideasRender(); status(`${fmtN(d.moved)} Eintrag/Einträge ${copyOnly ? "kopiert" : "verschoben"} nach „${o.name}“${d.dupes ? ` (${fmtN(d.dupes)} schon dort)` : ""}.`, "info"); }
  } }))), 0);
}

async function ideasRemove(ks) {
  const ok = await dialog({ title: "Aus der Wunschliste entfernen", text: `${fmtN(ks.length)} Eintrag/Einträge entfernen? „Verwerfen“ behält sie unter „Verworfen“. Rückgängig ist möglich.`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Entfernen", value: true, primary: true }] });
  if (!ok) return;
  IDEA.checked.clear();
  await ideasDo("ideas_remove", IDEA.d.sel, ks);
}

async function ideasNote(e) {
  const v = await modal({ title: "Notiz", html: `<div class="muted sm" style="margin-bottom:6px">${esc(e.artist)} – ${esc(e.title)}</div><textarea id="inTxt" class="fe-val" style="width:100%;min-height:90px" maxlength="1000" autofocus>${esc(e.note || "")}</textarea>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }], collect: (b) => $("#inTxt", b).value });
  if (v === null || v === undefined) return;
  await ideasDo("ideas_set", IDEA.d.sel, [e.k], null, v);
}

function ideasRowMenu(ev, e) {
  ev.preventDefault();
  const ks = IDEA.checked.has(e.k) && IDEA.checked.size > 1 ? [...IDEA.checked] : [e.k];
  const items = [
    { label: "Zum Kauf vormerken", run: () => ideasDo("ideas_set", IDEA.d.sel, ks, "buy") },
    { label: "Als Idee", run: () => ideasDo("ideas_set", IDEA.d.sel, ks, "idea") },
    { label: "Verwerfen", run: () => ideasDo("ideas_set", IDEA.d.sel, ks, "dropped") }, "-",
    ...(ks.length === 1 ? [{ label: "Notiz …", run: () => ideasNote(e) }] : []),
    { label: "Verschieben nach ›", run: () => ideasPickList(ev, ks, false) },
    { label: "Kopieren nach ›", run: () => ideasPickList(ev, ks, true) },
  ];
  if (ks.length === 1) {
    if (e.url) items.push({ label: "Bei der Quelle öffnen", run: () => call("open_url", e.url) });
    const ws = typeof webSearchItem === "function" ? webSearchItem(ev, e.artist, e.title, e.mix) : null;
    if (ws) items.push(ws);
  }
  items.push("-", { label: ks.length > 1 ? `${fmtN(ks.length)} entfernen …` : "Entfernen …", run: () => ideasRemove(ks) });
  showMenu(ev.clientX, ev.clientY, items);
}

/** „Idee merken ▸“ in Entdecken: Auswahl der Wunschliste (zuletzt benutzte zuerst), oder neue */
async function ideasRememberMenu(ev, keys, after) {
  let d;
  try { d = await call("ideas_overview", ""); } catch (e) { toast(String(e.message || e)); return; }
  const save = async (pid, name) => {
    try {
      const r = await call("ideas_from_disc", keys, pid, name);
      toast(r.added ? `In „${r.name}“ gemerkt.` : `Steht schon in „${r.name}“.`);
      ideasBadge();
      if (after) after(r);
    } catch (e) { toast(String(e.message || e)); }
  };
  const items = d.lists.map((l) => ({ label: `${l.name}${l.id === d.sel ? " ✓" : ""}`, run: () => save(l.id, "") }));
  if (items.length) items.push("-");
  items.push({ label: "Neue Wunschliste …", run: async () => { const n = await ideasNameDialog("Neue Wunschliste", "", "Anlegen und merken"); if (n) save("", n); } });
  const x = ev.clientX || (ev.target.getBoundingClientRect().left), y = ev.clientY || (ev.target.getBoundingClientRect().bottom);
  showMenu(x, y, items);
}

async function ideasBadge(n) {
  if (n === undefined) { try { n = await call("ideas_count"); } catch (e) { return; } }
  const el = $("#ideaCount"); if (el) el.textContent = n ? String(n) : "";
}

(function bindIdeas() {
  setTimeout(() => ideasBadge(), 9000);
  $("#ideaLists").addEventListener("click", (ev) => {
    if (ev.target.closest("#ideaNewList")) { ideasNewList(); return; }
    const b = ev.target.closest("[data-l]"); if (!b) return;
    ideasStop();
    ideasShow(b.dataset.l);
  });
  $("#ideaLists").addEventListener("contextmenu", (ev) => { const b = ev.target.closest("[data-l]"); if (b) ideasListMenu(ev, b.dataset.l); });
  $("#ideaFilter").addEventListener("click", (e) => { const b = e.target.closest("[data-f]"); if (!b) return; IDEA.filter = b.dataset.f; ideasApply(IDEA.d); });
  $("#ideaSearch").addEventListener("input", () => IDEA.d && ideasRender());
  $("#ideaAdd").addEventListener("click", (e) => { e.stopPropagation(); ideasAddMenu(); });
  $("#ideaMore").addEventListener("click", (e) => { e.stopPropagation(); ideasMoreMenu(); });
  $("#ideaMatch").addEventListener("click", ideasMatch);
  $("#ideaBp").addEventListener("click", ideasBeatport);
  $("#ideaAudio").addEventListener("ended", ideasStop);
  $("#ideaSelStatus").addEventListener("change", async (e) => {
    const v = e.target.value; e.target.value = "";
    if (v) { await ideasDo("ideas_set", IDEA.d.sel, [...IDEA.checked], v); }
  });
  $("#ideaSelMove").addEventListener("click", (ev) => ideasPickList(ev, [...IDEA.checked], false));
  $("#ideaSelRemove").addEventListener("click", () => ideasRemove([...IDEA.checked]));
  $("#ideaSelNone").addEventListener("click", () => { IDEA.checked.clear(); ideasRender(); });
  $("#ideaList").addEventListener("change", (ev) => {
    if (ev.target.id === "ideaAll") {
      ideasRows().forEach((e) => (ev.target.checked ? IDEA.checked.add(e.k) : IDEA.checked.delete(e.k)));
      ideasRender();
      return;
    }
    if (ev.target.matches("[data-c]")) {
      const k = +ev.target.closest("tr").dataset.k;
      if (ev.target.checked) IDEA.checked.add(k); else IDEA.checked.delete(k);
      ideasSelInfo();
    }
  });
  $("#ideaList").addEventListener("contextmenu", (ev) => {
    const tr = ev.target.closest("tr[data-k]"); if (!tr) return;
    const e = IDEA.d.items.find((x) => x.k === +tr.dataset.k); if (e) ideasRowMenu(ev, e);
  });
  $("#ideaList").addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-a]"); if (!b) return;
    const k = +b.closest("tr").dataset.k, e = IDEA.d.items.find((x) => x.k === k); if (!e) return;
    const a = b.dataset.a;
    if (a === "play") return ideasPlay(e);
    if (a === "open") return call("open_url", e.url);
    if (a === "note") return ideasNote(e);
    if (a === "menu") return ideasRowMenu(ev, e);
    if (IDEA.playing === String(k) && a === "dropped") ideasStop();
    await ideasDo("ideas_set", IDEA.d.sel, [k], a);
  });
})();
