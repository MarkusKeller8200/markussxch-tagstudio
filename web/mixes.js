/* MarKusSXCH TagStudio – Ergebnisse von „Mix analysieren“ (#261, #387): Tracklist eines Mixes ansehen, vorhören,
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
        <td class="mx-acts"><div class="mx-btns"><button class="ghost sm mx-play" data-mxplay="mix" data-t="${l.start}" title="Im Mix vorhören">▶ Mix</button></div></td></tr>`;
      const pos = l.track_start != null ? Math.max(0, l.at - l.track_start) : 0;
      return `<tr data-n="${l.n}" class="${l.sure ? "" : "mx-unsure"}">
        <td><input class="inp mx-time${l.edited ? " edited" : ""}" data-mxtime="${l.n}" value="${mixTime(l.at)}" title="Zeit in der Tracklist – Mitte des Übergangs (Titelanfang ${l.track_start != null ? mixTime(l.track_start) : "?"}, erkannt ab ${mixTime(l.start)}). Ändern und Enter; leer = wieder berechnen." spellcheck="false"></td>
        <td><span translate="no">${esc(l.artist ? `${l.artist} - ${l.title}` : l.title)}</span>${l.exists ? "" : ' <span class="mx-tag warn" title="Die Datei ist nicht mehr am gespeicherten Ort">fehlt</span>'}
          ${l.also.length ? `<div class="faint sm">auch: <span translate="no">${esc(l.also.join(", "))}</span></div>` : ""}
          <div class="faint sm" translate="no">${esc(l.path)}</div></td>
        <td>${(l.tempo >= 0 ? "+" : "") + l.tempo.toFixed(1)} %${l.keylock ? "" : '<div class="faint sm">ohne Keylock</div>'}</td>
        <td>${Math.round(l.conf * 100)} %${l.sure ? "" : ' <span class="mx-tag">unsicher</span>'}</td>
        <td class="mx-acts"><div class="mx-btns"><button class="ghost sm mx-play" data-mxplay="mix" data-t="${l.at}" title="Im Mix ab dieser Zeit vorhören">▶ Mix</button>
          <button class="ghost sm mx-play" data-mxplay="${l.n}" data-t="${pos}" ${l.exists ? "" : "disabled"} title="Den erkannten Titel an derselben Stelle vorhören">▶ Titel</button>
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
    <div class="hint">Die Zeit ist die Mitte des Übergangs – dort setzen Tracklisten meist den Wechsel. Unsichere Treffer prüfen (▶), falsche mit ✕ verwerfen. Erkannt werden nur Titel deiner Bibliothek; Lücken erscheinen als „ID – ID“.</div>
    <div id="mxRows">${mixRowsHtml(d)}</div>${dropped}`;
}

/** Ergebnisfenster */
async function mixOpen(id) {
  let d;
  try { d = await call("mix_get", id); } catch (e) { toast(String(e.message || e)); return; }
  MIX.id = id;
  const rerender = (b, nd) => { d = nd; b.innerHTML = mixBodyHtml(d); };
  const act = async (b, fn) => { try { rerender(b, await fn()); } catch (e) { toast(String(e.message || e)); } };
  const btns = [{ label: "Schliessen", value: null }];
  if (d.report) btns.push({ label: "Bericht zeigen", value: "report" });
  btns.push({ label: "Text kopieren", value: "copy" }, { label: "Text speichern …", value: "txt" }, { label: "CUE speichern …", value: "cue" });
  if (d.missing.length) btns.push({ label: `Fehlende als Ideen (${d.missing.length})`, value: "ideas" });
  btns.push({ label: d.playlist ? "Playlist nachführen" : "Als Playlist speichern", value: "pl", primary: true });
  await modal({
    title: "Mix analysieren – Ergebnis", wide: "xl", html: mixBodyHtml(d), buttons: btns,
    onMount: (b) => {
      b.addEventListener("click", async (e) => {
        const p = e.target.closest("[data-mxplay]");
        if (p) { const n = p.dataset.mxplay === "mix" ? null : +p.dataset.mxplay; mixPlay(id, n, +p.dataset.t, `${p.dataset.mxplay}@${p.dataset.t}`, p); return; }
        const x = e.target.closest("[data-mxdrop]");
        if (x) { await act(b, () => call("mix_drop", id, +x.dataset.mxdrop, true)); return; }
        const r = e.target.closest("[data-mxback]");
        if (r) { await act(b, () => call("mix_drop", id, +r.dataset.mxback, false)); return; }
        const l = e.target.closest("[data-mxpl]");
        if (l) { e.preventDefault(); const pid = l.dataset.mxpl; mixCloseThen(() => mixShowPlaylist(pid)); }
      });
      b.addEventListener("keydown", async (e) => {
        const t = e.target.closest("[data-mxtime]");
        if (t && e.key === "Enter") { e.preventDefault(); e.stopPropagation(); await act(b, () => call("mix_set_time", id, +t.dataset.mxtime, t.value)); }
      }, true);
      b.addEventListener("change", async (e) => {
        const t = e.target.closest("[data-mxtime]");
        if (t) await act(b, () => call("mix_set_time", id, +t.dataset.mxtime, t.value));
      });
    },
    collect: async (b, v) => {
      try {
        if (v === "report") { call("reveal", d.report); return false; }
        if (v === "copy") {
          try { await navigator.clipboard.writeText(d.text); toast("Tracklist kopiert."); } catch (e) { toast("Kopieren nicht möglich."); }
          return false;
        }
        if (v === "txt" || v === "cue") {
          let dest = "";
          const beside = v === "cue" && d.mix_exists ? await call("mix_cue_beside", id) : "";
          if (beside) {
            const w = await dialog({ title: "CUE-Datei speichern", text: `Neben dem Mix speichern?\n\n${beside}\n\nDort finden Player und DJ-Programme sie automatisch.`,
              buttons: [{ label: "Abbrechen", value: null }, { label: "Anderer Ort …", value: "pick" }, { label: "Neben dem Mix", value: "beside", primary: true }] });
            if (!w) return false;
            if (w === "beside") dest = beside;
          }
          if (!dest) dest = await call("save_dialog", await call("mix_export_name", id, v));
          if (!dest) return false;
          let r = await call("mix_export_write", id, v, dest, false);
          if (r.exists) {
            const ok = await dialog({ title: "Datei ersetzen?", text: `${r.path}\n\nDiese Datei gibt es schon. Ersetzen?`, buttons: [{ label: "Abbrechen", value: false }, { label: "Ersetzen", value: true, primary: true }] });
            if (!ok) return false;
            r = await call("mix_export_write", id, v, dest, true);
          }
          if (r.ok) { toast(r.message); status(`${r.message} (${r.path})`, "info"); }
          return false;
        }
        if (v === "ideas") {
          const r = await call("mix_missing_to_ideas", id, "", "");
          toast(r.added ? `${r.added} Titel als Ideen gemerkt in „${r.name}“${r.dupes ? ` (${r.dupes} schon vorhanden)` : ""}.` : `Schon alle in „${r.name}“.`);
          if (typeof ideasBadge === "function") ideasBadge();
          return false;
        }
        if (v === "pl") {
          const r = await call("mix_to_playlist", id, "");
          toast(r.message);
          rerender(b, await call("mix_get", id));
          const bt = [...$("#mBtns").querySelectorAll("button")].find((x) => x.classList.contains("primary"));
          if (bt) bt.textContent = "Playlist nachführen";
          return false;
        }
      } catch (e) { toast(String(e.message || e)); return false; }
      return v;
    },
  });
  mixStop();
  await mixRunNext();
}

async function mixShowPlaylist(pid) {
  if (typeof setModule === "function") setModule("playlists");
  try { if (typeof plsApply === "function") { PLS.sel = new Set(); plsApply(await call("pl_state", pid)); } } catch (e) { /* Playlist weg */ }
}

/** Frühere Analysen (Programmdaten › Mixe) */
async function mixListDialog() {
  let d;
  try { d = await call("mix_list"); } catch (e) { toast(String(e.message || e)); return; }
  const body = () => d.items.length
    ? `<div class="fx-table mx-table"><table><thead><tr><th>Mix</th><th>Analysiert</th><th>Titel</th><th></th></tr></thead><tbody>${d.items.map((x) => `<tr>
        <td><span translate="no">${esc(x.name)}</span> <span class="faint sm">${mixTime(x.duration)}</span>${x.exists ? "" : ' <span class="mx-tag warn">Mix-Datei fehlt</span>'}<div class="faint sm" translate="no">${esc(x.mix)}</div></td>
        <td>${esc(x.created)}</td><td>${x.count}${x.count > x.sure ? ` <span class="faint sm">(${x.count - x.sure} unsicher)</span>` : ""}</td>
        <td class="mx-acts"><div class="mx-btns"><button class="ghost sm" data-mxopen="${esc(x.id)}">Öffnen</button><button class="ghost sm" data-mxdel="${esc(x.id)}" title="Nur die Analyse löschen – Mix, Titel und gespeicherte Playlist bleiben">Löschen …</button></div></td></tr>`).join("")}</tbody></table></div>`
    : '<div class="empty">Noch keine Analysen.</div>';
  const btns = [{ label: "Schliessen", value: null }];
  if (d.ready) btns.push({ label: "Mix analysieren …", value: "new", primary: true });
  const v = await modal({
    title: "Mix-Analysen", wide: true, buttons: btns,
    html: `<div class="hint">Gespeicherte Ergebnisse von „Mix analysieren“ – öffnen ohne neue Analyse.${d.ready ? "" : " Für neue Analysen das Plugin „Mix analysieren“ installieren und einschalten (Plugins)."}</div><div id="mxList">${body()}</div>`,
    onMount: (b) => b.addEventListener("click", async (e) => {
      const o = e.target.closest("[data-mxopen]");
      if (o) { const rid = o.dataset.mxopen; mixCloseThen(() => mixOpen(rid)); return; }
      const x = e.target.closest("[data-mxdel]");
      if (x) {
        const it = d.items.find((i) => i.id === x.dataset.mxdel);
        const ok = await dialog({ title: "Analyse löschen?", text: `${it ? it.name : ""}\n\nNur das gespeicherte Ergebnis wird gelöscht – der Mix, die Titel und eine gespeicherte Playlist bleiben.`,
          buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
        if (!ok) return;
        try { d = await call("mix_delete", x.dataset.mxdel); $("#mxList", b).innerHTML = body(); } catch (err) { toast(String(err.message || err)); }
      }
    }),
  });
  if (v === "new" && typeof pluginRun === "function") await pluginRun("mixscan", "analyse");
  else await mixRunNext();
}

/** Playlists › Importieren ▾: Einträge, wenn das Plugin bereit ist bzw. Analysen vorhanden sind */
async function mixMenuEntries() {
  let d;
  try { d = await call("mix_list"); } catch (e) { return []; }
  const out = [];
  if (d.ready) out.push({ label: "Aus Mix erkennen (Mix analysieren) …", run: () => pluginRun("mixscan", "analyse") });
  if (d.items.length) out.push({ label: `Frühere Mix-Analysen (${d.items.length}) …`, run: () => mixListDialog() });
  return out;
}

/** #389: Mix im Hintergrund analysiert – sobald kein anderer Dialog offen ist, fragen, ob das Ergebnis aufgehen soll */
async function mixJobDone(j) {
  if (typeof modalIdle === "function") await modalIdle(600000);
  const v = await dialog({ title: "Mix analysiert", text: `${j.names[0] || ""}\n\n${j.message || ""}`,
    buttons: [{ label: "Später", value: false }, { label: "Ergebnis öffnen", value: true, primary: true }] });
  if (v) await mixOpen(j.mix_open);
}
