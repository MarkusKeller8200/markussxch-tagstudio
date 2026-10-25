/* MarKusSXCH TagStudio – Einkäufe: Playlists in Beatport (#334, #335).
   „Download Tracks …“ trägt die Einkäufe ohne lokale Datei in TagStudio_DOWNLOAD_<Datum>_<n> ein (je 100 – mehr lädt
   Beatport nicht auf einmal); „Playlists je Kaufdatum …“ legt PRÄFIX_JJJJ_MM_TT an bzw. ergänzt sie. Beides ändert
   das Beatport-Konto – nur mit eingeschalteter Plugin-Einstellung und nur auf Klick; verändert werden ausschliesslich
   Playlists, deren Name mit „TagStudio_“ beginnt. */

function purBpMenu(e) {
  e.stopPropagation();                                  // sonst schliesst derselbe Klick das Menü gleich wieder
  const b = e.currentTarget.getBoundingClientRect();
  showMenu(b.left, b.bottom + 4, [
    { label: "Download Tracks …", run: purBpDownload },
    { label: "Playlists je Kaufdatum …", run: purBpByDate },
    "-",
    { label: "Download-Playlists aufräumen …", run: purBpCleanup },
    { label: "Schreibzugriff prüfen", run: purBpCheck },
  ]);
}

/** Einstellung des Plugins prüfen – aus: Hinweis, wo man sie einschaltet */
async function purBpReady(s) {
  if (!s.available) { await info("Beatport nicht bereit", s.why || "Das Plugin „Beatport“ ist aus oder nicht angemeldet."); return false; }
  if (!s.playlists_write) {
    await info("Playlists in Beatport sind ausgeschaltet",
      "TagStudio legt nur Playlists in deinem Beatport-Konto an, wenn du es erlaubst: Plugins › Beatport › „Einstellungen …“ › „Playlists in Beatport anlegen und befüllen“.");
    return false;
  }
  return true;
}

function purBpResult(title, r) {
  const pls = r.playlists || [];
  return modal({
    title, wide: true,
    html: `<div class="fx-table pc-table"><table><thead><tr><th data-col="name">Playlist</th><th data-col="add" class="r">Neu</th><th data-col="del" class="r">Entfernt</th><th data-col="tot" class="r">Titel</th><th data-col="open" data-nogrip></th></tr></thead><tbody>
      ${pls.map((p) => `<tr><td translate="no">${esc(p.name)}${p.created ? ' <span class="fx-rcp-tag">neu</span>' : ""}</td><td class="r">${fmtN(p.added || 0)}</td><td class="r">${fmtN(p.removed || 0)}</td><td class="r">${fmtN(p.total || 0)}</td>
        <td><a href="#" class="pls-link" data-url="${esc(p.url)}">In Beatport öffnen ↗</a></td></tr>`).join("")}</tbody></table></div>
      ${(r.notes || []).map((n) => `<p class="pc-why sm">${esc(n)}</p>`).join("")}`,
    buttons: [{ label: "Schliessen", value: null, primary: true }],
    onMount: (b) => b.addEventListener("click", (e) => { const a = e.target.closest("[data-url]"); if (a) { e.preventDefault(); call("open_url", a.dataset.url); } }),
  });
}

async function purBpDownload() {
  const keys = PUR.sel.size ? [...PUR.sel] : null;
  const pv = await call("purch_dl_playlist_preview", keys);
  if (!(await purBpReady(pv))) return;
  if (!pv.count) return info("Download Tracks", "Keine Beatport-Einkäufe ohne lokale Datei.");
  const ok = await modal({
    title: "Download Tracks", wide: true,
    html: `<p style="margin:0">${fmtN(pv.count)} ${keys ? "markierte" : "fehlende bzw. unklare"} Beatport-Titel → ${fmtN(pv.chunks.length)} Playlist(s) in deinem Beatport-Konto (Beatport lädt höchstens 100 Titel auf einmal):</p>
      <ul class="pc-list">${pv.chunks.map((c) => `<li><span translate="no">${esc(c.name)}</span> – ${fmtN(c.count)} Titel</li>`).join("")}</ul>
      <p class="muted sm">Eine Playlist gleichen Namens wird ersetzt, überzählige vom selben Tag geleert – es häuft sich nichts an. In Beatport die Playlist öffnen und alle Titel in den Download übernehmen.</p>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "In Beatport anlegen", value: true, primary: true }],
  });
  if (!ok) return;
  const r = await runTask(call("start_purch_dl_playlist", keys), "Download-Playlists in Beatport");
  if (r && r.ok) purBpResult("Download Tracks", r);
}

async function purBpByDate() {
  const pv0 = await call("purch_buy_playlists_preview", null, "", "");
  if (!(await purBpReady(pv0))) return;
  let pv = pv0;
  const table = () => (pv.rows.length
    ? `<table><thead><tr><th data-col="date">Kaufdatum</th><th data-col="name">Playlist</th><th data-col="n" class="r">Titel</th></tr></thead><tbody>${pv.rows.map((r) => `<tr><td>${esc(r.date)}</td><td translate="no">${esc(r.name)}</td><td class="r">${fmtN(r.count)}</td></tr>`).join("")}</tbody></table>`
    : '<div class="empty">Keine Einkäufe mit Kaufdatum im Zeitraum.</div>');
  const res = await modal({
    title: "Playlists je Kaufdatum", wide: true,
    html: `<div class="pc-edit" data-keep-enter>
        <label>Präfix</label><input class="inp" id="pbPrefix" value="${esc(pv.prefix)}" spellcheck="false" translate="no">
        <label>Von</label><input class="inp" id="pbSince" type="date">
        <label>Bis</label><input class="inp" id="pbUntil" type="date">
      </div>
      <p class="muted sm" style="margin:8px 0">Je Kaufdatum eine Playlist PRÄFIX_JJJJ_MM_TT; vorhandene werden nur ergänzt (keine Doppelten), andere Playlists bleiben unberührt. Das Präfix beginnt immer mit „TagStudio_“.</p>
      <div class="fx-table pc-table" id="pbTable">${table()}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "In Beatport anlegen", value: true, primary: true }],
    onMount: (b) => {
      let t = 0;
      const upd = () => { clearTimeout(t); t = setTimeout(async () => {
        pv = await call("purch_buy_playlists_preview", $("#pbPrefix", b).value.trim() || null, $("#pbSince", b).value, $("#pbUntil", b).value);
        $("#pbTable", b).innerHTML = table();
      }, 250); };
      b.addEventListener("input", upd);
    },
    collect: (b) => ({ prefix: $("#pbPrefix", b).value.trim(), since: $("#pbSince", b).value, until: $("#pbUntil", b).value }),
  });
  if (!res) return;
  const r = await runTask(call("start_purch_buy_playlists", res.prefix || null, res.since, res.until), "Playlists je Kaufdatum in Beatport");
  if (r && r.ok) purBpResult("Playlists je Kaufdatum", r);
}

async function purBpCleanup() {
  const s = await call("purch_bp_settings");
  if (!(await purBpReady(s))) return;
  const ok = await dialog({ title: "Download-Playlists aufräumen?",
    text: "Alle Playlists in deinem Beatport-Konto, deren Name mit „TagStudio_DOWNLOAD_“ beginnt, werden gelöscht. Andere Playlists bleiben unberührt.",
    buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
  if (!ok) return;
  const r = await runTask(call("start_purch_dl_cleanup"), "Download-Playlists aufräumen");
  if (!r) return;
  if (r.failed && r.failed.length) info("Nicht alles gelöscht", [`${fmtN(r.deleted.length)} gelöscht.`, ...r.failed].join("\n"));
  else toast(`${fmtN((r.deleted || []).length)} Download-Playlist(s) gelöscht.`);
}

async function purBpCheck() {
  const s = await call("purch_bp_settings");
  if (!s.available) return info("Beatport nicht bereit", s.why || "");
  try {
    const r = await call("purch_bp_check");
    info("Schreibzugriff Beatport", r.text);
  } catch (e) { info("Schreibzugriff Beatport", String(e.message || e)); }
}
