/* MarKusSXCH TagStudio – Vorbereiten › Entdecken (#120): neue Titel gefolgter Künstler, Labels und Genres mit
   Vorhören, Merkliste und Kauf-Link. Logik in discover.py / session_discover.py. Gekauft wird nie automatisch. */
"use strict";

const DISC = { d: null, filter: "new", playing: "" };
const DISC_FILTERS = [["new", "Neu"], ["saved", "Gemerkt"], ["all", "Alle"], ["bought", "Gekauft"], ["hidden", "Ausgeblendet"]];

function prepTab(tab) {
  $$("#prepTabs [data-ptab]").forEach((b) => { b.classList.toggle("on", b.dataset.ptab === tab); b.setAttribute("aria-selected", String(b.dataset.ptab === tab)); });
  $("#prepWfPane").hidden = tab !== "wf";
  $("#prepWfActs").style.visibility = tab === "wf" ? "" : "hidden";
  $("#discPane").hidden = tab !== "disc";
  if (tab === "disc") discShow(); else discStop();
}

async function discShow() {
  try { discApply(await call("disc_overview")); } catch (e) { toast(String(e.message || e)); }
}

function discApply(d) {
  DISC.d = d;
  const c = d.counts || {};
  $("#discCount").textContent = c.new ? String(c.new) : "";
  $("#discFilter").innerHTML = DISC_FILTERS.map(([k, t]) => `<button data-f="${k}" role="radio" aria-checked="${k === DISC.filter}" class="${k === DISC.filter ? "on" : ""}">${t}${k !== "all" && c[k] ? ` <span class="muted">${fmtN(c[k])}</span>` : ""}</button>`).join("");
  const f = d.follow, n = f.artists.length + f.labels.length + f.genres.length;
  discFolRender();
  $("#discInfo").textContent = n ? `${n} gefolgt · ${d.last ? "zuletzt gesucht " + d.last.replace("T", " ").slice(0, 16) : "noch nicht gesucht"}${d.library ? "" : " · keine Bibliothek (für „vorhanden“)"}` : "Noch nichts gefolgt – „Folgen …“";
  discRender();
}

function discRows() {
  const d = DISC.d, q = ($("#discSearch").value || "").toLowerCase().trim(), hide = $("#discHideOwned").checked;
  return d.items.filter((e) => (DISC.filter === "all" ? e.status !== "hidden"
      : DISC.filter === "bought" ? e.status === "bought" || (e.purchased && e.status !== "hidden") : e.status === DISC.filter)
    && !(hide && e.owned && DISC.filter !== "bought")
    && (!q || `${e.artist} ${e.title} ${e.mix} ${e.label} ${e.release}`.toLowerCase().includes(q)));
}

function discRender() {
  const rows = discRows().slice(0, 1000);
  if (!rows.length) {
    const msg = !DISC.d.items.length ? "Noch keine Vorschläge. Unter „Folgen …“ Künstler, Labels oder Genres festlegen und „Suchen“."
      : DISC.filter === "new" ? "Keine neuen Vorschläge." : "Nichts in dieser Ansicht.";
    $("#discList").innerHTML = `<div class="tg-empty">${msg}</div>`;
    return;
  }
  const src = { deezer: "Deezer", beatport: "Beatport", sonovault: "SonoVault" };
  $("#discList").innerHTML = `<table class="disc-t"><thead><tr><th></th><th></th><th>Künstler</th><th>Titel</th><th>Label</th><th>Datum</th><th>BPM · Tonart</th><th>Quelle</th><th></th></tr></thead><tbody>
    ${rows.map((e) => `<tr data-k="${esc(e.key)}" class="st-${e.status}${e.owned ? " owned" : ""}${e.purchased ? " bought-p" : ""}">
      <td><button class="icon-btn play ${DISC.playing === e.key ? "on" : ""}" data-a="play" ${e.preview ? "" : "disabled"} title="${e.preview ? "Vorhören (Ausschnitt)" : "kein Vorhör-Ausschnitt"}" aria-label="Vorhören">${DISC.playing === e.key ? "❚❚" : "▶"}</button></td>
      <td class="cv">${e.cover ? `<img src="${esc(e.cover)}" alt="" loading="lazy" referrerpolicy="no-referrer"><img class="big" src="${esc(e.cover)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}</td>
      <td class="ell" title="${esc(e.artist)}">${esc(e.artist)}</td>
      <td class="ell nm" title="${esc(e.title + (e.mix ? ` (${e.mix})` : ""))}"><b>${esc(e.title)}</b>${e.mix ? ` <span class="muted">(${esc(e.mix)})</span>` : ""}${e.status === "new" && DISC.filter !== "new" ? '<span class="disc-badge">neu</span>' : ""}${e.owned ? '<span class="disc-badge" title="Gleicher Künstler und Titel ist schon in der Bibliothek">vorhanden</span>' : ""}${e.purchased ? `<span class="disc-badge buy" title="${e.purchased === "ja" ? "Steht unter „Käufe“" : "Laut „Käufe“ gekauft am " + esc(e.purchased)}">gekauft</span>` : ""}</td>
      <td class="ell sm" title="${esc([e.label, e.release].filter(Boolean).join(" – "))}">${esc(e.label || "")}</td>
      <td class="sm nw">${esc((e.date || "").slice(0, 10))}</td>
      <td class="sm nw muted">${esc([e.bpm ? e.bpm : "", e.key_name].filter(Boolean).join(" · "))}</td>
      <td class="sm nw" title="${esc([e.seed, e.genre].filter(Boolean).join(" · "))}">${esc(src[e.src] || e.src)}</td>
      <td class="d-acts"><div class="d-row"><button class="ghost sm" data-a="open" ${e.url ? "" : "disabled"} title="${esc(e.url ? `Auf ${src[e.src] || e.src} öffnen (Kauf nur dort)` : "Kein Link (SonoVault: nur Anzeige, Eintrag verschwindet nach 30 Tagen)")}">Öffnen</button>
        ${e.status !== "saved" ? '<button class="icon-btn" data-a="saved" title="Merken">☆</button>' : '<button class="icon-btn" data-a="new" title="Nicht mehr merken">★</button>'}
        ${e.status !== "bought" ? '<button class="icon-btn" data-a="bought" title="Als gekauft markieren">✓</button>' : ""}
        ${e.status !== "hidden" ? '<button class="icon-btn" data-a="hidden" title="Ausblenden">✕</button>' : '<button class="icon-btn" data-a="new" title="Wieder anzeigen">↺</button>'}</div></td></tr>`).join("")}
    </tbody></table>${discRows().length > 1000 ? '<div class="muted sm" style="padding:8px">Die ersten 1000 Einträge – Suche oder Filter einschränken.</div>' : ""}`;
}

function discStop() {
  const a = $("#discAudio");
  if (a) { a.pause(); a.removeAttribute("src"); }
  if (DISC.playing) { DISC.playing = ""; if (DISC.d) discRender(); }
}

function discPlay(e) {
  const a = $("#discAudio");
  if (DISC.playing === e.key) { discStop(); return; }
  try { if (typeof PLAYER !== "undefined" && PLAYER.audio && !PLAYER.audio.paused) PLAYER.audio.pause(); } catch (x) { /* Player nicht aktiv */ }
  a.src = e.preview;
  a.play().catch((x) => toast("Vorhören nicht möglich: " + (x.message || x)));
  DISC.playing = e.key;
  discRender();
}

async function discRun() {
  discStop();
  const r = await runTask(call("start_disc_run"), "Entdecken – neue Titel suchen");
  if (!r) { discShow(); return; }
  status(`${fmtN(r.new)} neue(r) Vorschlag/Vorschläge (${fmtN(r.found)} gefunden).`, r.log.length ? "warn" : "info");
  DISC.filter = "new";
  await discShow();
  if (r.log.length && !r.new) await info("Hinweise zur Suche", r.log.join("\n"));
}

async function discFollowDialog() {
  const f = JSON.parse(JSON.stringify(DISC.d.follow));
  let genres = null;
  const genreBox = (b) => {
    const box = $("#dfGenres", b);
    if (!genres) { box.innerHTML = '<span class="muted sm">Genre-Charts (Top 100) kommen von Beatport. </span><button class="ghost sm" id="dfLoadG">Genres laden</button>'; return; }
    const on = new Set(f.genres.map((g) => String(g.id)));
    box.innerHTML = genres.map((g) => `<label class="check"><input type="checkbox" data-g="${esc(String(g.id))}" data-n="${esc(g.name)}" ${on.has(String(g.id)) ? "checked" : ""}> ${esc(g.name)}</label>`).join("");
  };
  const res = await modal({
    title: "Folgen – Künstler, Labels, Genres", wide: true,
    html: `<div class="disc-f"><p class="muted sm" style="margin:0 0 8px">„Suchen“ fragt für alles hier neue Veröffentlichungen ab. Deezer braucht keine Anmeldung; Beatport nutzt die Anmeldung des Beatport-Plugins. Es wird nie etwas gekauft – nur gemerkt und verlinkt.</p>
      <div class="cols"><div><label for="dfArt"><b>Künstler</b> <span class="muted sm">(einer pro Zeile)</span></label><textarea id="dfArt" class="fe-val" spellcheck="false">${esc(f.artists.join("\n"))}</textarea></div>
      <div><label for="dfLab"><b>Labels</b> <span class="muted sm">(eines pro Zeile)</span></label><textarea id="dfLab" class="fe-val" spellcheck="false">${esc(f.labels.join("\n"))}</textarea></div></div>
      <div style="margin:8px 0"><button class="ghost sm" id="dfSuggest" ${DISC.d.library ? "" : "disabled title=\"Zuerst unter Einstellungen › Speicherort und Ordner eine Bibliothek festlegen\""}>Aus der Bibliothek vorschlagen …</button><span class="muted sm" id="dfSugInfo"></span><div class="disc-sug" id="dfSug"></div></div>
      <label><b>Genres</b></label><div class="disc-genres" id="dfGenres"></div>
      <div class="frm" style="margin-top:10px"><label for="dfDays">Zeitraum</label><span><input id="dfDays" type="number" min="1" max="3650" value="${f.days || 60}" style="width:80px"> Tage zurück</span>
        <span></span><label class="check"><input type="checkbox" id="dfAuto" ${f.auto ? "checked" : ""}> Täglich beim Start automatisch suchen (im Hintergrund)</label>
        <label>Quellen</label><span><label class="check"><input type="checkbox" id="dfDz" ${f.sources.includes("deezer") ? "checked" : ""}> Deezer</label> <label class="check"><input type="checkbox" id="dfBp" ${f.sources.includes("beatport") ? "checked" : ""}> Beatport${DISC.d.beatport ? "" : ' <span class="muted sm">(Plugin aus oder nicht bereit)</span>'}</label>
          <label class="check" title="Je Künstler bzw. Label 1–2 Anfragen pro Suche (Suche nach dem Namen 30 Tage zwischengespeichert). Nur bei „Suchen“, nie bei der täglichen Suche. Einträge ohne Link, nach 30 Tagen entfernt."><input type="checkbox" id="dfSv" ${f.sources.includes("sonovault") ? "checked" : ""} ${(DISC.d.sonovault || {}).ready ? "" : "disabled"}> <span>SonoVault</span>${(DISC.d.sonovault || {}).ready ? ` <span class="muted sm">(kostet Kredite · ${esc(DISC.d.sonovault.text)})</span>` : ' <span class="muted sm">(Plugin aus oder kein Schlüssel)</span>'}</label></span></div></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }],
    onMount: (b) => {
      genreBox(b);
      b.addEventListener("click", async (e) => {
        const t = e.target.closest("button"); if (!t) return;
        if (t.id === "dfLoadG") {
          t.disabled = true; t.textContent = "Lade …";
          const r = await call("disc_genres");
          if (!r.ok) { $("#dfGenres", b).innerHTML = `<span class="st-missing sm">${esc(r.error)}</span>`; return; }
          genres = r.genres; genreBox(b);
        } else if (t.id === "dfSuggest") {
          t.disabled = true; $("#dfSugInfo", b).textContent = " Lese die Bibliothek …";
          const st = await call("start_disc_suggest");
          if (!st.ok) { $("#dfSugInfo", b).textContent = " " + st.error; t.disabled = false; return; }
          let s;
          for (;;) { s = await call("task_status"); if (s.done) break; await new Promise((ok) => setTimeout(ok, 200)); }
          t.disabled = false;
          if (s.error) { $("#dfSugInfo", b).textContent = " " + s.error; return; }
          $("#dfSugInfo", b).textContent = " Klick übernimmt in die Liste:";
          const have = (id) => new Set($(id, b).value.split("\n").map((x) => x.trim().toLowerCase()));
          const ha = have("#dfArt"), hl = have("#dfLab");
          $("#dfSug", b).innerHTML = s.result.artists.filter((x) => !ha.has(x.name.toLowerCase())).slice(0, 20).map((x) => `<button class="ghost sm" data-add="dfArt" data-v="${esc(x.name)}" title="${x.count} Titel">+ ${esc(x.name)}</button>`).join("")
            + s.result.labels.filter((x) => !hl.has(x.name.toLowerCase())).slice(0, 12).map((x) => `<button class="ghost sm" data-add="dfLab" data-v="${esc(x.name)}" title="Label · ${x.count} Titel">+ ${esc(x.name)} <span class="muted">Label</span></button>`).join("");
        } else if (t.dataset.add) {
          const ta = $("#" + t.dataset.add, b);
          ta.value = (ta.value.trim() ? ta.value.trim() + "\n" : "") + t.dataset.v;
          t.remove();
        }
      });
    },
    collect: (b) => {
      const lines = (id) => $(id, b).value.split("\n").map((x) => x.trim()).filter(Boolean);
      const g = genres ? [...b.querySelectorAll("#dfGenres [data-g]:checked")].map((x) => ({ id: +x.dataset.g || x.dataset.g, name: x.dataset.n })) : f.genres;
      return { artists: lines("#dfArt"), labels: lines("#dfLab"), genres: g, days: +$("#dfDays", b).value || 60, auto: $("#dfAuto", b).checked,
        sources: [$("#dfDz", b).checked ? "deezer" : "", $("#dfBp", b).checked ? "beatport" : "", $("#dfSv", b).checked ? "sonovault" : ""].filter(Boolean) };
    },
  });
  if (!res) return;
  try { discApply(await call("disc_follow_save", res)); toast("Gespeichert – „Suchen“ holt die neuen Titel."); } catch (e) { toast(String(e.message || e)); }
}

/** Gefolgt (#291): Künstler, Labels und Genres als Chips – Beatport-Herkunft markiert, × entfernt */
function discFolRender() {
  const f = DISC.d.follow, bp = f.bp || { artists: [], labels: [] };
  const low = (xs) => new Set((xs || []).map((x) => x.toLowerCase()));
  const chips = (kind, xs, from) => xs.map((x) => `<span class="disc-chip" data-kind="${kind}" data-n="${esc(String(kind === "genres" ? x.id : x))}">${esc(kind === "genres" ? x.name : x)}${from && from.has(x.toLowerCase()) ? '<span class="bp" title="Auf Beatport gefolgt">BP</span>' : ""}<button data-x title="Nicht mehr folgen" aria-label="Nicht mehr folgen">×</button></span>`).join("");
  const grp = (t, kind, xs, from) => xs.length ? `<div class="disc-fol-grp"><span class="lbl">${t} (${fmtN(xs.length)})</span>${chips(kind, xs, from)}</div>` : "";
  $("#discFolList").innerHTML = (grp("Künstler", "artists", f.artists, low(bp.artists)) + grp("Labels", "labels", f.labels, low(bp.labels)) + grp("Genres", "genres", f.genres, null))
    || '<div class="muted sm">Noch nichts gefolgt – Namen eingeben oder „Von Beatport übernehmen“.</div>';
  $("#discFolSum").textContent = `${fmtN(f.artists.length)} Künstler · ${fmtN(f.labels.length)} Labels · ${fmtN(f.genres.length)} Genres`;
  $("#discFolBp").disabled = !DISC.d.beatport;
}

async function discFolEdit(kind, name, add) {
  if (kind === "genres") {
    const f = JSON.parse(JSON.stringify(DISC.d.follow));
    f.genres = f.genres.filter((g) => String(g.id) !== String(name));
    discApply(await call("disc_follow_save", f));
    return;
  }
  discApply(await call("disc_follow_edit", kind, name, add));
}

async function discFolAdd() {
  const inp = $("#discFolName"), v = inp.value.trim();
  if (!v) { inp.focus(); return; }
  const kind = $("#discFolKind").value;
  const had = DISC.d.follow[kind].length;
  await discFolEdit(kind, v, true);
  if (DISC.d.follow[kind].length === had) toast(`„${v}“ ist schon in der Liste.`);
  inp.value = "";
}

async function discFolBeatport() {
  const r = await runTask(call("start_disc_bp_follow"), "Beatport – gefolgte Künstler und Labels");
  if (!r) return;
  await discShow();
  status(`Beatport: ${fmtN(r.artists)} Künstler und ${fmtN(r.labels)} Labels gelesen, ${fmtN(r.new_artists)} Künstler und ${fmtN(r.new_labels)} Labels neu.`, "info");
}

async function discRelated() {
  const r = await runTask(call("start_disc_related"), "Ähnliche Künstler suchen");
  if (!r) return;
  if (!r.artists.length) { await info("Ähnliche Künstler", "Keine weiteren ähnlichen Künstler gefunden."); return; }
  const pick = await modal({
    title: "Ähnliche Künstler", html: `<p class="muted sm" style="margin:0 0 8px">Zu deinen gefolgten Künstlern ähnliche (Deezer). Gewählte werden gefolgt.</p>
      <div class="disc-rel">${r.artists.map((a) => `<label class="check"><input type="checkbox" data-n="${esc(a.name)}"> ${esc(a.name)} <span class="muted sm">· ähnlich wie ${esc(a.because.slice(0, 3).join(", "))}${a.because.length > 3 ? " …" : ""}</span></label>`).join("")}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Folgen", value: true, primary: true }],
    collect: (b) => [...b.querySelectorAll("[data-n]:checked")].map((x) => x.dataset.n),
  });
  if (!pick || !pick.length) return;
  for (const n of pick) DISC.d = await call("disc_follow_edit", "artists", n, true);
  discApply(DISC.d);
  toast(`${fmtN(pick.length)} Künstler gefolgt – „Suchen“ holt ihre neuen Titel.`);
}

async function discClear() {
  const v = await dialog({ title: "Vorschläge leeren", text: "Neue und ausgeblendete Vorschläge entfernen? Gemerkte und gekaufte bleiben erhalten.",
    buttons: [{ label: "Abbrechen", value: null }, { label: "Leeren", value: "clear" }, { label: "Leeren und neu suchen", value: "run", primary: true }] });
  if (!v) return;
  discStop();
  const d = await call("disc_clear");
  discApply(d);
  status(`${fmtN(d.removed)} Vorschlag/Vorschläge entfernt.`, "info");
  if (v === "run") await discRun();
}

function discRowMenu(ev, e) {
  const f = DISC.d.follow, has = (kind, n) => f[kind].some((x) => x.toLowerCase() === n.toLowerCase());
  const items = [];
  e.artist.split(/\s*(?:,|&)\s*/).filter(Boolean).forEach((a) => {
    items.push(has("artists", a) ? { label: `Künstler nicht mehr folgen: ${a}`, run: () => discFolEdit("artists", a, false) }
      : { label: `Künstler folgen: ${a}`, run: () => discFolEdit("artists", a, true) });
  });
  if (e.label) items.push(has("labels", e.label) ? { label: `Label nicht mehr folgen: ${e.label}`, run: () => discFolEdit("labels", e.label, false) }
    : { label: `Label folgen: ${e.label}`, run: () => discFolEdit("labels", e.label, true) });
  if (!items.length) return;
  ev.preventDefault();
  showMenu(ev.clientX, ev.clientY, items);
}

/** Merkliste exportieren (#162) */
function discExportMenu() {
  const b = $("#discExport").getBoundingClientRect(), c = (DISC.d && DISC.d.counts) || {};
  const run = async (fmt, which) => {
    const r = await call("disc_export", fmt, which);
    if (r && r.ok) status(r.message, "info"); else if (r && r.error) toast(r.error);
  };
  showMenu(b.left, b.bottom + 6, [
    { label: `Merkliste als Excel (${fmtN(c.saved || 0)})`, run: () => run("xlsx", "saved") },
    { label: "Merkliste als CSV", run: () => run("csv", "saved") }, "-",
    { label: `Gekaufte als Excel (${fmtN(c.bought || 0)})`, run: () => run("xlsx", "bought") },
    { label: "Neu + gemerkt + gekauft als Excel", run: () => run("xlsx", "all") },
  ]);
}

/** Tägliche Suche beim Start (#162): im Hintergrund, danach Anzahl neuer Vorschläge melden */
async function discAutoStart() {
  let r;
  try { r = await call("disc_auto"); } catch (e) { return; }
  if (!r || !r.started) { discBadge(); return; }
  for (let i = 0; i < 180; i++) {
    await new Promise((ok) => setTimeout(ok, 5000));
    let st; try { st = await call("disc_auto_status"); } catch (e) { return; }
    if (!st.running) {
      discBadge(st.count_new);
      if (st.auto_new) toast(`Entdecken: ${fmtN(st.auto_new)} neue(r) Vorschlag/Vorschläge.`);
      if (S.module === "prep" && !$("#discPane").hidden) discShow();
      return;
    }
  }
}

async function discBadge(n) {
  if (n === undefined) { try { n = (await call("disc_auto_status")).count_new; } catch (e) { return; } }
  const el = $("#discCount"); if (el) el.textContent = n ? String(n) : "";
}

(function bindDiscover() {
  setTimeout(discAutoStart, 8000);
  $("#discExport").addEventListener("click", (e) => { e.stopPropagation(); discExportMenu(); });
  $("#prepTabs").addEventListener("click", (e) => { const b = e.target.closest("[data-ptab]"); if (b) prepTab(b.dataset.ptab); });
  $("#discFilter").addEventListener("click", (e) => { const b = e.target.closest("[data-f]"); if (!b) return; DISC.filter = b.dataset.f; discApply(DISC.d); });
  $("#discSearch").addEventListener("input", () => DISC.d && discRender());
  $("#discHideOwned").addEventListener("change", () => DISC.d && discRender());
  $("#discRun").addEventListener("click", discRun);
  $("#discFollow").addEventListener("click", discFollowDialog);
  $("#discClear").addEventListener("click", discClear);
  $("#discFolAdd").addEventListener("click", discFolAdd);
  $("#discFolName").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); discFolAdd(); } });
  $("#discFolBp").addEventListener("click", discFolBeatport);
  $("#discFolRel").addEventListener("click", discRelated);
  $("#discFolList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-x]"); if (!b) return;
    const c = b.closest(".disc-chip");
    discFolEdit(c.dataset.kind, c.dataset.n, false);
  });
  $("#discList").addEventListener("contextmenu", (ev) => {
    const tr = ev.target.closest("tr[data-k]"); if (!tr) return;
    const e = DISC.d.items.find((x) => x.key === tr.dataset.k); if (e) discRowMenu(ev, e);
  });
  $("#discAudio").addEventListener("ended", discStop);
  $("#discList").addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-a]"); if (!b) return;
    const k = b.closest("tr").dataset.k, e = DISC.d.items.find((x) => x.key === k); if (!e) return;
    if (b.dataset.a === "play") return discPlay(e);
    if (b.dataset.a === "open") return call("open_url", e.url);
    if (DISC.playing === k && b.dataset.a === "hidden") discStop();
    discApply(await call("disc_set", [k], b.dataset.a));
  });
})();
