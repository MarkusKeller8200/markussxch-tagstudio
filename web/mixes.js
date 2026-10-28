/* MarKusSXCH TagStudio – Seite „Mixe“ (#261, #387, #390): Ergebnisse von „Mix analysieren“ ansehen, vorhören,
   Treffer verwerfen, Zeiten korrigieren und als Playlist (Ordner „Mixe“), CUE-Datei, Text oder Ideen speichern.
   Die Analyse läuft im Plugin „mixscan“; Logik und Ablage in mixresult.py / session_mixes.py. */
"use strict";

const MIX = { id: "", audio: null, playing: "", next: null };

/** offenes Fenster schliessen (wie „Schliessen“) und danach next() ausführen */
function mixCloseThen(next) {
  MIX.next = next;
  const b = $("#mBtns button"); if (b) b.click();
}
async function mixRunNext() {
  const n = MIX.next; MIX.next = null;
  if (n) await n();
}

function mixTime(sec) {
  sec = Math.max(0, Math.round(Number(sec) || 0));
  const h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Vorhören im Ergebnisfenster: Mix ab Sekunde t bzw. Titel n ab seiner Stelle; nochmals klicken = Stopp */
async function mixPlay(id, n, t, key, btn) {
  if (!MIX.audio) MIX.audio = new Audio();
  const a = MIX.audio;
  document.querySelectorAll(".mx-play.on").forEach((b) => b.classList.remove("on"));
  if (MIX.playing === key && !a.paused) { a.pause(); MIX.playing = ""; return; }
  let info;
  try { info = await call("mix_audio", id, n === null ? null : n); } catch (e) { toast(String(e.message || e)); return; }
  if (a.src !== info.url) a.src = info.url;
  const go = () => { try { a.currentTime = Math.max(0, t || 0); } catch (e) { /* noch nicht bereit */ } a.play().catch(() => toast("Abspielen nicht möglich.")); };
  if (a.readyState >= 1 && a.src === info.url) go(); else a.addEventListener("loadedmetadata", go, { once: true });
  MIX.playing = key;
  if (btn) btn.classList.add("on");
}
function mixStop() {
  if (MIX.audio) MIX.audio.pause();
  MIX.playing = "";
}

function mixRowsHtml(d) {
  if (!d.lines.length) return '<div class="empty">Keine Titel erkannt – sind die Titel des Mixes im Index?</div>';
  return `<div class="fx-table mx-table"><table><thead><tr><th>Zeit</th><th>Titel</th><th>Tempo</th><th>Sicherheit</th><th></th></tr></thead><tbody>
    ${d.lines.map((l) => {
      if (l.gap) return `<tr class="mx-gap"><td>${mixTime(l.start)}</td><td colspan="3"><span class="muted">ID – ID</span> <span class="faint sm">· unbekannt ${mixTime(l.start)}–${mixTime(l.end)}</span></td>
        <td class="mx-acts"><div class="mx-btns"><button class="ghost sm mx-play" data-mxplay="mix" data-t="${l.start}" title="Im Mix vorhören">▶ Mix</button>
          <button class="ghost sm" data-mxgap="${l.start}" title="Diese Lücke über einen Erkennungsdienst erkennen (kostenpflichtig)">Erkennen …</button></div></td></tr>`;
      const pos = l.track_start != null ? Math.max(0, l.at - l.track_start) : 0;
      return `<tr data-n="${l.n}" class="${l.sure ? "" : "mx-unsure"}">
        <td><input class="inp mx-time${l.edited ? " edited" : ""}" data-mxtime="${l.n}" value="${mixTime(l.at)}" title="Zeit in der Tracklist – Mitte des Übergangs (Titelanfang ${l.track_start != null ? mixTime(l.track_start) : "?"}, erkannt ab ${mixTime(l.start)}). Ändern und Enter; leer = wieder berechnen." spellcheck="false"></td>
        <td><span translate="no">${esc(l.artist ? `${l.artist} - ${l.title}` : l.title)}</span>${l.online ? ` <span class="mx-tag online" title="Online erkannt – nicht in deiner Bibliothek">online · <span translate="no">${esc(l.online)}</span></span>`
          : l.tl ? ' <span class="mx-tag online" title="Aus der bekannten Tracklist – Zeitmarke in einer Lücke">aus Tracklist</span>'
          : l.exists ? "" : ' <span class="mx-tag warn" title="Die Datei ist nicht mehr am gespeicherten Ort">fehlt</span>'}
          ${l.linked ? ` <span class="faint sm" title="Zuerst ohne Datei erkannt, danach mit der Bibliothek verknüpft">verknüpft · <span translate="no">${esc(l.linked)}</span></span>` : ""}
          ${l.also.length ? `<div class="faint sm">auch: <span translate="no">${esc(l.also.join(", "))}</span></div>` : ""}
          ${l.online || l.tl ? '<div class="faint sm">nicht in der Bibliothek</div>' : `<div class="faint sm" translate="no">${esc(l.path)}</div>`}</td>
        <td>${l.online || l.tl || l.linked ? '<span class="faint">–</span>' : (l.tempo >= 0 ? "+" : "") + l.tempo.toFixed(1) + " %" + (l.keylock ? "" : '<div class="faint sm">ohne Keylock</div>')}</td>
        <td>${l.tl ? '<span class="faint">Tracklist</span>' : `${Math.round(l.conf * 100)} %${l.sure ? "" : ' <span class="mx-tag">unsicher</span>'}`}</td>
        <td class="mx-acts"><div class="mx-btns"><button class="ghost sm mx-play" data-mxplay="mix" data-t="${l.at}" title="Im Mix ab dieser Zeit vorhören">▶ Mix</button>
          ${l.online || l.tl ? "" : `<button class="ghost sm mx-play" data-mxplay="${l.n}" data-t="${pos}" ${l.exists ? "" : "disabled"} title="Den erkannten Titel an derselben Stelle vorhören">▶ Titel</button>`}
          <button class="ghost sm" data-mxdrop="${l.n}" title="Treffer verwerfen (falsch erkannt)">✕</button></div></td></tr>`;
    }).join("")}</tbody></table></div>`;
}

function mixBodyHtml(d) {
  const c = d.compare;
  const cmp = c && c.expected ? `<div class="mx-cmp">Bekannte Tracklist: <b>${c.hit.length} von ${c.expected}</b> erkannt (${Math.round(100 * c.hit.length / c.expected)} %)${c.unsure && c.unsure.length ? `, davon ${c.unsure.length} unsicher` : ""}.
      ${d.missing.length ? `<details><summary>Nicht im Index (${d.missing.length})</summary><div class="sm" translate="no">${d.missing.map(esc).join("<br>")}</div></details>` : ""}</div>` : "";
  const dropped = d.dropped.length ? `<details class="mx-dropped"><summary>Verworfen (${d.dropped.length})</summary>${d.dropped.map((x) => `<div class="row" style="gap:8px;align-items:center"><span translate="no">${esc(x.artist ? `${x.artist} - ${x.title}` : x.title)}</span> <span class="faint sm">${mixTime(x.start)}</span> <button class="ghost sm" data-mxback="${x.n}">Zurückholen</button></div>`).join("")}</details>` : "";
  return `<div class="mx-head"><div><b translate="no">${esc(d.name)}</b> <span class="muted sm">${mixTime(d.duration)} · analysiert ${esc(d.created)}${d.version ? ` · Plugin ${esc(d.version)}` : ""}</span></div>
      <div class="faint sm" translate="no">${esc(d.mix)}${d.mix_exists ? "" : " – Datei fehlt"}</div>
      ${d.index ? `<div class="faint sm">Index: ${esc(d.index)}</div>` : ""}
      ${d.playlist ? `<div class="sm">Gespeichert als Playlist – <a href="#" data-mxpl="${esc(d.playlist)}">in Playlists öffnen ›</a></div>` : ""}</div>
    ${cmp}
    <div class="hint">Die Zeit ist die Mitte des Übergangs – dort setzen Tracklisten meist den Wechsel. Unsichere Treffer prüfen (▶), falsche mit ✕ verwerfen. Erkannt werden nur Titel deiner Bibliothek; Lücken erscheinen als „ID – ID“ und lassen sich mit „Lücken online erkennen …“ über einen Erkennungsdienst füllen.</div>
    ${d.online ? '<div class="hint">Online erkannte Titel nur für den eigenen Gebrauch – eine Tracklist mit diesen Treffern nicht veröffentlichen (Nutzungsbedingungen des Dienstes).</div>' : ""}
    <div id="mxRows">${mixRowsHtml(d)}</div>${dropped}`;
}

// ====================================================================== Seite „Mixe“ (#390)
const MXP = { items: [], sel: "", d: null, plugin: null, ready: false };

function mixHead() {
  return `<div class="mx-bar">
      <button class="ghost sm" data-mxa="copy">Text kopieren</button><button class="ghost sm" data-mxa="txt">Text speichern …</button>
      <button class="ghost sm" data-mxa="cue">CUE speichern …</button>
      ${MXP.d.missing.length ? `<button class="ghost sm" data-mxa="ideas">Fehlende als Ideen (${MXP.d.missing.length})</button>` : ""}
      ${MXP.d.gaps ? `<button class="ghost sm" data-mxa="gaps" title="Ausschnitte der Lücken über einen Erkennungsdienst erkennen (kostenpflichtig)">Lücken online erkennen (${MXP.d.gaps}) …</button>` : ""}
      <button class="ghost sm" data-mxa="tracklist" title="Bekannte Tracklist (mit Zeitmarken) einfügen – füllt passende Lücken ohne Kosten">${MXP.d.tracklist ? "Tracklist ändern …" : "Tracklist einfügen …"}</button>
      ${MXP.d.nofile ? `<button class="ghost sm" data-mxa="link" title="Titel ohne Datei (online erkannt bzw. aus der Tracklist) in der Bibliothek suchen und verknüpfen">Mit Bibliothek abgleichen</button>
      <button class="ghost sm" data-mxa="online" title="Titel ohne Datei in einer Wunschliste merken">Ohne Datei als Ideen (${MXP.d.nofile})</button>` : ""}
      ${MXP.d.report ? '<button class="ghost sm" data-mxa="report">Bericht zeigen</button>' : ""}
      <button class="ghost sm" data-mxa="delete" title="Nur die Analyse löschen – Mix, Titel und gespeicherte Playlist bleiben">Löschen …</button>
      <button class="primary sm" data-mxa="pl" id="mxSavePl">${MXP.d.playlist ? "Playlist nachführen" : "Als Playlist speichern"}</button></div>`;
}

/** Seite zeigen; sel = Kennung einer Analyse (sonst die zuletzt gewählte bzw. neueste) */
async function mixesShow(sel) {
  let d;
  try { d = await call("mix_list"); } catch (e) { toast(String(e.message || e)); return; }
  MXP.items = d.items; MXP.plugin = d.plugin; MXP.ready = d.ready;
  if (sel !== undefined) MXP.sel = sel;
  if (!MXP.items.some((x) => x.id === MXP.sel)) MXP.sel = MXP.items.length ? MXP.items[0].id : "";
  mixBadge(MXP.items.length);
  const pl = MXP.plugin || {};
  $("#mxStatus").textContent = !pl.found ? "Plugin „Mix analysieren“ fehlt."
    : !pl.enabled ? "Plugin „Mix analysieren“ ist ausgeschaltet (Plugins)."
    : pl.state !== "ready" ? "Plugin „Mix analysieren“ ist noch nicht installiert – unter Plugins „Installieren …“ (etwa 100 MB)."
    : `Plugin ${pl.version} · ${pl.status || ""}`;
  ["#mxNew", "#mxIndex", "#mxOpts", "#mxFolder"].forEach((s) => { $(s).disabled = !MXP.ready; });
  $("#mxList").innerHTML = `<div class="idea-lh"><b>Analysen</b></div>` + (MXP.items.length ? MXP.items.map((x) => `<button class="idea-l mx-l${x.id === MXP.sel ? " on" : ""}" data-mx="${esc(x.id)}" aria-current="${x.id === MXP.sel}" title="${esc(x.mix)}">
      <span class="nm"><span class="ellipsis" translate="no">${esc(x.name)}</span><span class="faint sm">${esc(x.created)} · ${mixTime(x.duration)}${x.exists ? "" : " · Mix-Datei fehlt"}</span></span>
      <span class="n" title="Erkannte Titel${x.count > x.sure ? `, davon ${x.count - x.sure} unsicher` : ""}">${x.count}</span></button>`).join("")
    : `<div class="muted sm" style="padding:8px">Noch keine Analysen.${MXP.ready ? " „Mix analysieren …“ oben rechts." : ""}</div>`);
  if (MXP.sel) await mixesLoad(MXP.sel);
  else {
    MXP.d = null;
    $("#mxMain").innerHTML = `<div class="empty mx-empty">${MXP.ready
      ? "Mix-Datei wählen mit „Mix analysieren …“. Erkannt werden nur Titel, die im Index sind – einmal „Bibliothek indexieren …“, danach führt TagStudio den Index selbst nach."
      : `Für „Mixe“ braucht es das Plugin „Mix analysieren“ (eigene Umgebung, etwa 100 MB). <button class="ghost sm" data-mxa="plugins">Zu den Plugins</button>`}</div>`;
  }
}

async function mixesLoad(id) {
  try { MXP.d = await call("mix_get", id); } catch (e) { toast(String(e.message || e)); return; }
  MXP.sel = id;
  mixesRenderMain();
}
function mixesRenderMain() {
  if (!MXP.d) return;
  $("#mxMain").innerHTML = mixHead() + `<div class="card mx-card">${mixBodyHtml(MXP.d)}</div>`;
}

function mixBadge(n) {
  const el = $("#mixCount"); if (el) el.textContent = n ? String(n) : "";
}

/** Ergebnis öffnen = Seite „Mixe“ mit dieser Analyse */
async function mixOpen(id) {
  MXP.sel = id || MXP.sel;
  if (S.module === "mixes") await mixesShow(MXP.sel);
  else setModule("mixes");
}
/** frühere Aufrufe (Playlists › Importieren, Plugin „Frühere Analysen …“) führen auf die Seite */
async function mixListDialog() { await mixOpen(""); }

async function mixShowPlaylist(pid) {
  setModule("playlists");
  try { if (typeof plsApply === "function") { PLS.sel = new Set(); plsApply(await call("pl_state", pid)); } } catch (e) { /* Playlist weg */ }
}

async function mixAction(a) {
  const id = MXP.sel, d = MXP.d;
  if (a === "plugins") { setModule("plugins"); return; }
  if (!d) return;
  try {
    if (a === "report") call("reveal", d.report);
    else if (a === "copy") {
      try { await navigator.clipboard.writeText(d.text); toast("Tracklist kopiert."); } catch (e) { toast("Kopieren nicht möglich."); }
    } else if (a === "txt" || a === "cue") {
      let dest = "";
      const beside = a === "cue" && d.mix_exists ? await call("mix_cue_beside", id) : "";
      if (beside) {
        const w = await dialog({ title: "CUE-Datei speichern", text: `Neben dem Mix speichern?\n\n${beside}\n\nDort finden Player und DJ-Programme sie automatisch.`,
          buttons: [{ label: "Abbrechen", value: null }, { label: "Anderer Ort …", value: "pick" }, { label: "Neben dem Mix", value: "beside", primary: true }] });
        if (!w) return;
        if (w === "beside") dest = beside;
      }
      if (!dest) dest = await call("save_dialog", await call("mix_export_name", id, a));
      if (!dest) return;
      let r = await call("mix_export_write", id, a, dest, false);
      if (r.exists) {
        const ok = await dialog({ title: "Datei ersetzen?", text: `${r.path}\n\nDiese Datei gibt es schon. Ersetzen?`, buttons: [{ label: "Abbrechen", value: false }, { label: "Ersetzen", value: true, primary: true }] });
        if (!ok) return;
        r = await call("mix_export_write", id, a, dest, true);
      }
      if (r.ok) { toast(r.message); status(`${r.message} (${r.path})`, "info"); }
    } else if (a === "ideas") {
      const r = await call("mix_missing_to_ideas", id, "", "");
      toast(r.added ? `${r.added} Titel als Ideen gemerkt in „${r.name}“${r.dupes ? ` (${r.dupes} schon vorhanden)` : ""}.` : `Schon alle in „${r.name}“.`);
      if (typeof ideasBadge === "function") ideasBadge();
    } else if (a === "gaps") {
      await mixGaps(null);
    } else if (a === "tracklist") {
      await mixTracklist();
    } else if (a === "link") {
      const r = await runTask(call("start_mix_link", id), "Mixe mit der Bibliothek abgleichen");
      if (!r) return;
      toast(r.linked ? `${r.linked} Titel mit der Bibliothek verknüpft.` : "Keine sicheren Treffer in der Bibliothek.");
      await mixesLoad(id);
    } else if (a === "online") {
      const r = await call("mix_online_to_ideas", id, "", "");
      toast(r.added ? `${r.added} Titel als Ideen gemerkt in „${r.name}“${r.dupes ? ` (${r.dupes} schon vorhanden)` : ""}.` : `Schon alle in „${r.name}“.`);
      if (typeof ideasBadge === "function") ideasBadge();
    } else if (a === "pl") {
      const r = await call("mix_to_playlist", id, "");
      toast(r.message);
      await mixesLoad(id);
    } else if (a === "delete") {
      const ok = await dialog({ title: "Analyse löschen?", text: `${d.name}\n\nNur das gespeicherte Ergebnis wird gelöscht – der Mix, die Titel und eine gespeicherte Playlist bleiben.`,
        buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
      if (!ok) return;
      mixStop();
      await call("mix_delete", id);
      MXP.sel = "";
      await mixesShow();
    }
  } catch (e) { toast(String(e.message || e)); }
}

(function bindMixes() {
  if (!$("#moduleMixes")) return;
  setTimeout(() => call("mix_list").then((d) => mixBadge(d.items.length)).catch(() => {}), 9500);
  $("#mxNew").addEventListener("click", () => pluginRun("mixscan", "analyse"));
  $("#mxIndex").addEventListener("click", () => pluginRun("mixscan", "index"));
  $("#mxOpts").addEventListener("click", () => pluginRun("mixscan", "settings"));
  $("#mxFolder").addEventListener("click", () => pluginRun("mixscan", "analyse_folder"));
  $("#mxList").addEventListener("click", (e) => {
    const b = e.target.closest("[data-mx]"); if (!b) return;
    mixStop();
    mixesShow(b.dataset.mx);
  });
  const main = $("#mxMain");
  const act = async (fn) => { try { MXP.d = await fn(); mixesRenderMain(); } catch (e) { toast(String(e.message || e)); } };
  main.addEventListener("click", async (e) => {
    const a = e.target.closest("[data-mxa]");
    if (a) { mixAction(a.dataset.mxa); return; }
    const p = e.target.closest("[data-mxplay]");
    if (p) { const n = p.dataset.mxplay === "mix" ? null : +p.dataset.mxplay; mixPlay(MXP.sel, n, +p.dataset.t, `${p.dataset.mxplay}@${p.dataset.t}`, p); return; }
    const x = e.target.closest("[data-mxdrop]");
    if (x) { await act(() => call("mix_drop", MXP.sel, +x.dataset.mxdrop, true)); return; }
    const r = e.target.closest("[data-mxback]");
    if (r) { await act(() => call("mix_drop", MXP.sel, +r.dataset.mxback, false)); return; }
    const g = e.target.closest("[data-mxgap]");
    if (g) { await mixGaps(+g.dataset.mxgap); return; }
    const l = e.target.closest("[data-mxpl]");
    if (l) { e.preventDefault(); mixStop(); await mixShowPlaylist(l.dataset.mxpl); }
  });
  main.addEventListener("keydown", async (e) => {
    const t = e.target.closest("[data-mxtime]");
    if (t && e.key === "Enter") { e.preventDefault(); await act(() => call("mix_set_time", MXP.sel, +t.dataset.mxtime, t.value)); }
  });
  main.addEventListener("change", async (e) => {
    const t = e.target.closest("[data-mxtime]");
    if (t) await act(() => call("mix_set_time", MXP.sel, +t.dataset.mxtime, t.value));
  });
})();

// ====================================================================== #394 Tracklist nachträglich
async function mixTracklist() {
  const id = MXP.sel;
  const text = await modal({
    title: "Tracklist einfügen",
    html: `<div class="mx-gapdlg"><p>Je Zeile „Künstler - Titel“, mit Zeitmarke (z. B. von MixID oder 1001Tracklists kopiert). Einträge, deren Zeit in einer Lücke liegt (höchstens 60 s daneben), füllen sie als „aus Tracklist“ – ohne Hochladen, ohne Kosten.</p>
      <textarea id="mxTlText" class="inp" rows="14" spellcheck="false" translate="no" placeholder="[00:00] Künstler - Titel">${esc(MXP.d.tracklist || "")}</textarea></div>`,
    wide: true,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Übernehmen", value: "go", primary: true }],
    collect: (body) => $("#mxTlText", body).value,
  });
  if (text === null || text === undefined) return;
  try {
    MXP.d = await call("mix_set_tracklist", id, text);
    mixesRenderMain();
    toast(MXP.d.added ? `${MXP.d.added} Lücke(n) aus der Tracklist gefüllt.` : "Keine Lücke mit passender Zeitmarke.");
  } catch (e) { toast(String(e.message || e)); }
}

// ====================================================================== #393 „MixID light“: Lücken online erkennen
/** Dialog mit Dienst, Ausschnittlänge, Kostengrenze und Kostenvorschau; only = Beginn einer einzelnen Lücke */
async function mixGaps(only) {
  const id = MXP.sel;
  let g;
  try { g = await call("mix_gaps_info", id); } catch (e) { toast(String(e.message || e)); return; }
  if (!g.mix_exists) { await info("Lücken online erkennen", "Die Mix-Datei gibt es nicht mehr am gespeicherten Ort."); return; }
  const recs = g.recognizers || [];
  if (!recs.length) {
    await info("Lücken online erkennen", "Kein Erkennungsdienst eingeschaltet. Unter Plugins „SonoVault“ einschalten und den Schlüssel eintragen – die Audio-Erkennung braucht einen bezahlten Tarif bzw. Kredite.");
    return;
  }
  const rec = recs.find((r) => r.ready) || recs[0];
  if (!rec.ready) { await info("Lücken online erkennen", `${rec.name}: ${rec.why || "nicht bereit"}.`); return; }
  const secs = (rec.seconds || [30]).map((s) => `<option value="${s}"${s === (rec.default || 30) ? " selected" : ""}>${s} Sekunden</option>`).join("");
  const maxes = [5, 10, 20, 50].map((n) => `<option value="${n}"${n === 10 ? " selected" : ""}>${n}</option>`).join("");
  const html = `<div class="mx-gapdlg">
      <p><b>${only === null ? `${g.gaps.length} Lücke(n) ohne erkannten Titel.` : `Lücke ab ${mixTime(only)}.`}</b></p>
      <p>TagStudio schneidet daraus kurze Ausschnitte (ohne Tags, mono) und lässt sie erkennen – je angefangene 3 Minuten einer, in der Mitte des Abschnitts.</p>
      <label class="row" style="gap:8px;align-items:center">Dienst <select id="mgPid" class="inp">${recs.filter((r) => r.ready).map((r) => `<option value="${esc(r.id)}" translate="no">${esc(r.name)}</option>`).join("")}</select></label>
      <label class="row" style="gap:8px;align-items:center">Länge des Ausschnitts <select id="mgSec" class="inp">${secs}</select></label>
      <label class="row" style="gap:8px;align-items:center">Höchstens so viele Ausschnitte <select id="mgMax" class="inp">${maxes}</select></label>
      <div id="mgEst" class="mx-cmp">…</div>
      <div class="hint">Datenschutz: Die Ausschnitte werden zum Dienst hochgeladen. Nur Mixe, die du hochladen darfst (eigene Aufnahmen bzw. mit Rechten). Treffer bleiben im Mix-Ergebnis – nur für den eigenen Gebrauch, nicht veröffentlichen.</div>
      <label class="row" style="gap:8px;align-items:center"><input type="checkbox" id="mgOk"> Kosten und Hochladen bestätigen</label></div>`;
  const est = async (body) => {
    try {
      const p = await call("mix_gaps_plan", id, $("#mgPid", body).value, +$("#mgSec", body).value, +$("#mgMax", body).value, only);
      $("#mgEst", body).innerHTML = p.clips
        ? `<div><b>${p.clips} Ausschnitt(e)</b> aus ${p.gaps} Lücke(n) – geschätzt <b>${p.cost} ${esc(p.unit)}</b> (${p.each} je Ausschnitt).</div>${p.more ? `<div class="sm">${p.more} weitere Stelle(n) bei einem späteren Lauf.</div>` : ""}<div class="faint sm">${esc(p.quota)}</div>`
        : "Keine Stelle mehr zum Erkennen – alle schon geprüft.";
    } catch (e) { $("#mgEst", body).textContent = String(e.message || e); }
  };
  const opts = await modal({
    title: "Lücken online erkennen", html,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Erkennen", value: "go", primary: true }],
    onMount: (body) => { body.addEventListener("change", (e) => { if (e.target.id !== "mgOk") est(body); }); est(body); },
    collect: (body) => {
      if (!$("#mgOk", body).checked) { toast("Bitte zuerst „Kosten und Hochladen bestätigen“ anhaken."); return false; }
      return { pid: $("#mgPid", body).value, seconds: +$("#mgSec", body).value, max: +$("#mgMax", body).value, only, confirm: true };
    },
  });
  if (!opts) return;
  const r = await runTask(call("start_mix_gaps", id, opts), "Mix-Lücken erkennen");
  if (!r) return;
  const msg = `${r.name}: ${r.found} Titel erkannt aus ${r.clips} von ${r.planned} Ausschnitt(en).`;
  status(msg, "info");
  if (r.error) await info("Lücken online erkennen", `${msg}\n\nAbgebrochen: ${r.error}`);
  else toast(msg);
  await mixesLoad(id);
}

/** Playlists › Importieren ▾: Einträge, wenn das Plugin bereit ist bzw. Analysen vorhanden sind */
async function mixMenuEntries() {
  let d;
  try { d = await call("mix_list"); } catch (e) { return []; }
  const out = [];
  if (d.ready) out.push({ label: "Aus Mix erkennen (Mix analysieren) …", run: () => pluginRun("mixscan", "analyse") });
  if (d.items.length) out.push({ label: `Frühere Mix-Analysen (${d.items.length}) …`, run: () => mixOpen("") });
  return out;
}

/** #389: Mix im Hintergrund analysiert – sobald kein anderer Dialog offen ist, fragen, ob das Ergebnis aufgehen soll */
async function mixJobDone(j) {
  if (typeof modalIdle === "function") await modalIdle(600000);
  const v = await dialog({ title: "Mix analysiert", text: `${j.names[0] || ""}\n\n${j.message || ""}`,
    buttons: [{ label: "Später", value: false }, { label: "Ergebnis öffnen", value: true, primary: true }] });
  if (v) await mixOpen(j.mix_open);
}
