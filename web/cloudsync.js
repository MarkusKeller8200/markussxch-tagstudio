"use strict";
// Einstellungen › Speicherort und Ordner › „Abgleich über die Dienste“ (Cloud Weg 2, #317, docs/KONZEPT-CLOUD.md).
// Rollen Playlists/Export und Programmdaten-Teile mit OneDrive, Google Drive oder Dropbox (Plugins) abgleichen –
// beide Richtungen; Konflikte und gelöschte Dateien nur nach Rückfrage.

const CLOUD_MODES = { both: "beide Richtungen", up: "nur hochladen", down: "nur herunterladen" };

function cloudLastText(l) {
  if (!l || !l.at) return "noch nie abgeglichen";
  const d = l.at.replace("T", " ").slice(0, 16);
  return `zuletzt ${d} · ↑${l.up || 0} ↓${l.down || 0}${l.conflicts ? ` · ${l.conflicts} Konflikt(e)` : ""}${l.deleted ? ` · ${l.deleted} gelöscht (offen)` : ""}${l.errors ? ` · ${l.errors} Fehler` : ""}`;
}

/** Abschnitt in der Karte „Speicherort und Ordner“ zeichnen (Aufruf am Ende von stFoldersRender) */
async function stCloudSyncRender() {
  const box = $("#stCloudSync"); if (!box) return;
  let o;
  try { o = await call("cloud_sync_overview"); } catch (e) { box.innerHTML = `<span class="st-missing sm">${esc(String(e.message || e))}</span>`; return; }
  const provs = o.providers || [];
  const ready = provs.filter((p) => p.ready);
  const provSel = (r) => `<select class="inp sm" data-csprov aria-label="Dienst für ${esc(r.label)}"><option value="">aus</option>${provs.map((p) => `<option value="${esc(p.id)}" ${r.sync && r.sync.provider === p.id ? "selected" : ""} ${p.ready ? "" : "disabled"}>${esc(p.name)}${p.ready ? "" : " (nicht angemeldet)"}</option>`).join("")}</select>`;
  const modeSel = (r) => `<select class="inp sm" data-csmode aria-label="Richtung" ${r.sync ? "" : "disabled"}>${Object.entries(CLOUD_MODES).map(([k, v]) => `<option value="${k}" ${(r.sync ? r.sync.mode : "both") === k ? "selected" : ""}>${esc(v)}</option>`).join("")}</select>`;
  const row = (r) => `<tr data-cskind="${esc(r.kind)}" data-csid="${esc(r.id)}"><th scope="row">${r.kind === "role" ? "" : '<span class="muted sm">Programmdaten · </span>'}${esc(r.label)}</th>
      <td>${provSel(r)} ${modeSel(r)} <input class="inp sm cs-remote" data-csremote value="${esc(r.sync ? r.sync.remote : r.default_remote)}" ${r.sync ? "" : "disabled"} spellcheck="false" aria-label="Ordner im Dienst" title="Ordner im Dienst">
      <div class="muted sm">${r.sync ? esc(cloudLastText(r.last)) : r.kind === "role" ? esc(r.path || "Rolle ohne Ordner") : ""}</div></td></tr>`;
  const any = o.rows.some((r) => r.sync);
  box.innerHTML = `<div class="st-row"><span>Abgleich über die Dienste</span><div>
    ${provs.length ? "" : '<div class="muted sm">Kein Cloud-Plugin eingeschaltet – unter Plugins „OneDrive“, „Google Drive“ oder „Dropbox“ einschalten, eigene App eintragen und anmelden.</div>'}
    ${provs.length && !ready.length ? '<div class="muted sm">Cloud-Plugin eingeschaltet, aber nicht angemeldet (Plugins › … › „Anmelden …“).</div>' : ""}
    <div class="fx-table cs-table"><table><tbody>${o.rows.map(row).join("")}</tbody></table></div>
    <div class="fold-acts"><button class="primary sm" data-cssync ${any ? "" : "disabled"}>Jetzt abgleichen</button>
      ${o.conflicts || o.gone ? `<button class="ghost sm" data-cspending>Offen: ${o.conflicts} Konflikt(e), ${o.gone} gelöscht …</button>` : ""}</div>
    <div class="muted sm">Musik nur über den Sync-Ordner des Desktop-Clients (oben). Zugangsdaten, Snapshots, Arbeit und Cache werden nie abgeglichen. Ändert sich eine Datei hier und im Dienst, fragt TagStudio nach; gelöscht wird nur nach Rückfrage.</div></div></div>`;
}

function cloudRowSync(tr) {
  const prov = $("[data-csprov]", tr).value;
  if (!prov) return null;
  return { provider: prov, mode: $("[data-csmode]", tr).value, remote: $("[data-csremote]", tr).value.trim() };
}

document.addEventListener("change", async (e) => {
  const tr = e.target.closest("#stCloudSync tr[data-csid]"); if (!tr) return;
  if (!e.target.matches("[data-csprov],[data-csmode],[data-csremote]")) return;
  try {
    await call("cloud_sync_set", tr.dataset.cskind, tr.dataset.csid, cloudRowSync(tr));
    toast(cloudRowSync(tr) ? "Abgleich eingerichtet – „Jetzt abgleichen“ startet ihn." : "Abgleich ausgeschaltet.");
  } catch (err) { toast(String(err.message || err)); }
  stCloudSyncRender();
});

document.addEventListener("click", async (e) => {
  if (e.target.closest("#stCloudSync [data-cssync]")) {
    const st = await call("start_cloud_sync");
    if (!st.ok) return toast(st.error);
    const r = await runTask(Promise.resolve(st), "Abgleich über die Dienste");
    stCloudSyncRender();
    if (!r) return;
    const errs = (r.rows || []).filter((x) => x.error || (x.errors || []).length);
    if (errs.length) await info("Abgleich über die Dienste", [r.message, ...errs.map((x) => `${x.label}: ${x.error || x.errors.join("\n")}`)].join("\n\n"));
    else status(r.message, "info");
    if (r.conflicts || r.gone) await cloudPendingDialog();
  } else if (e.target.closest("#stCloudSync [data-cspending]")) {
    await cloudPendingDialog();
  }
});

/** Konflikte (beide Fassungen) und gelöschte Dateien – nichts geschieht ohne Entscheid */
async function cloudPendingDialog() {
  for (;;) {
    const p = await call("cloud_pending");
    if (!p.conflicts.length && !p.gone.length) { stCloudSyncRender(); return; }
    const conf = p.conflicts.map((c) => `<div class="cs-conf" data-cid="${esc(c.id)}"><b>${esc(c.label)}</b> · <code>${esc(c.rel)}</code> <span class="muted sm">– hier und im Dienst geändert</span>
      <div class="cs-two"><div><div class="muted sm">Hier (${fmtN(c.local_size)} Bytes)</div><pre class="pl-log" translate="no">${esc(c.local)}</pre></div>
        <div><div class="muted sm">Im Dienst (${fmtN(c.remote_size)} Bytes)</div><pre class="pl-log" translate="no">${esc(c.remote)}</pre></div></div>
      <div class="fold-acts"><button class="ghost sm" data-csres="here">Hier behalten</button><button class="ghost sm" data-csres="there">Aus dem Dienst übernehmen</button>${c.part === "settings" ? "" : '<button class="ghost sm" data-csres="both">Beide behalten</button>'}</div></div>`).join("");
    const gone = p.gone.map((g) => `<div class="cs-gone" data-gid="${esc(g.id)}"><b>${esc(g.label)}</b> · <code>${esc(g.rel)}</code> <span class="muted sm">– ${esc(g.why)}</span>
      <div class="fold-acts"><button class="ghost sm" data-csgone="delete">${g.where === "local" ? "Auch hier löschen …" : "Auch im Dienst löschen …"}</button><button class="ghost sm" data-csgone="keep">Nicht löschen (wieder abgleichen)</button></div></div>`).join("");
    let act = null;
    const done = await modal({ title: "Abgleich – bitte entscheiden", wide: true,
      html: `${conf}${gone}<p class="muted sm">Jede Entscheidung gilt sofort. „Schliessen“ lässt die übrigen offen – sie erscheinen beim nächsten Abgleich wieder.</p>`,
      buttons: [{ label: "Schliessen", value: null }],
      onMount: (b) => b.addEventListener("click", (ev) => {
        const r = ev.target.closest("[data-csres]"), g = ev.target.closest("[data-csgone]");
        if (r) act = { kind: "res", id: r.closest("[data-cid]").dataset.cid, v: r.dataset.csres };
        else if (g) act = { kind: "gone", id: g.closest("[data-gid]").dataset.gid, v: g.dataset.csgone };
        else return;
        $("#mBtns button", document).click();
      }) });
    if (!act) { stCloudSyncRender(); return done; }
    try {
      if (act.kind === "res") await call("cloud_resolve", act.id, act.v);
      else if (act.v === "keep") await call("cloud_gone", act.id, "keep");
      else {
        const g = p.gone.find((x) => x.id === act.id);
        const ok = await dialog({ title: "Datei löschen?", text: `${g.label}: ${g.rel}\n\n${g.where === "local" ? "Die Datei wurde im Dienst gelöscht. Auch hier löschen?" : "Die Datei wurde hier gelöscht. Auch im Dienst löschen?"}`,
          buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
        if (ok) await call("cloud_gone", act.id, "delete");
      }
    } catch (err) { toast(String(err.message || err)); }
  }
}
