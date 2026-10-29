"use strict";
// Einstellungen › Cloud › „Spiegel der Bibliothek“ (#403, docs/KONZEPT-CLOUD.md §4c): Einweg-Kopie der Musik in einen
// Cloud-Ordner (z. B. OneDrive privat, #405). Im Spiegel wird nie bearbeitet; überzählige Dateien nur nach Rückfrage.

/** Abschnitt in der Karte „Cloud“ zeichnen (Aufruf aus stCloudCardRender) */
async function stMirrorRender() {
  const box = $("#stMirror"); if (!box) return;
  let o;
  try { o = await call("mirror_overview"); } catch (e) { box.innerHTML = `<span class="st-missing sm">${esc(String(e.message || e))}</span>`; return; }
  const c = o.cfg, l = o.last || {};
  const libs = o.libraries.map((x) => `<label class="check sm" title="${esc(x.path)}"><input type="checkbox" data-mrlib="${esc(x.id)}" ${x.on ? "checked" : ""}> <span translate="no">${esc(x.name)}</span></label>`).join(" ");
  const last = l.at ? `zuletzt ${esc(l.at.replace("T", " ").slice(0, 16))} · ${fmtN(l.copied || 0)} kopiert · ${fmtN(l.files || 0)} Titel${l.extra ? ` · ${fmtN(l.extra)} überzählig` : ""}${l.errors ? ` · ${fmtN(l.errors)} Fehler` : ""}` : "noch nie nachgeführt";
  box.innerHTML = `<h4 class="cs-h">Spiegel der Bibliothek</h4>
    <div class="muted sm">Einweg-Kopie der Musik in einen Cloud-Ordner (z. B. OneDrive privat) – TagStudio bearbeitet weiter nur die Bibliothek, im Spiegel wird nie etwas geändert. Abo und Speichergrösse bestimmst du; „Platz schätzen“ zeigt, wie viel nötig ist.</div>
    <div class="st-row"><span>Ziel-Ordner</span><div><span class="pl-folder"><input id="mrFolder" class="inp sm" value="${esc(c.folder)}" placeholder="${esc(o.suggest || "z. B. OneDrive")}" spellcheck="false" aria-label="Ziel-Ordner des Spiegels" translate="no"><button class="ghost sm" data-mrpick>Wählen …</button>${!c.folder && o.suggest ? '<button class="ghost sm" data-mrsuggest>Vorschlag übernehmen</button>' : ""}</span>
      ${o.cloud_folders.length ? `<div class="muted sm">Cloud-Ordner aus Plugins: ${o.cloud_folders.map((x) => `<span title="${esc(x.path)}">☁ ${esc(x.name)}</span>`).join(" · ")}</div>` : '<div class="muted sm">Tipp: Plugins › OneDrive › „Kontoart …“ › „Privat“ – dann wird der OneDrive-Ordner vorgeschlagen.</div>'}</div></div>
    <div class="st-row"><span>Aufbau</span><div><select id="mrLayout" class="inp sm" aria-label="Aufbau im Ziel-Ordner">
        <option value="path" ${c.layout === "path" ? "selected" : ""}>Pfad der Bibliothek ohne Laufwerk (z. B. D: › Musik › DJ → Ziel › Musik › DJ)</option>
        <option value="name" ${c.layout === "name" ? "selected" : ""}>Je Bibliothek ein Ordner mit ihrem Namen</option></select>
      ${(o.dests || []).length ? `<div class="muted sm mr-dests">${o.dests.map((d) => `<div title="${esc(d.path)}"><span translate="no">${esc(d.name)}</span> → <code translate="no">${esc(d.dest)}</code></div>`).join("")}</div>` : ""}</div></div>
    <div class="st-row"><span>Bibliotheken</span><div>${libs || '<span class="muted sm">Keine erreichbare Bibliothek.</span>'}</div></div>
    <div class="st-row"><span>Optionen</span><div>
      <label class="check sm"><input type="checkbox" data-mropt="auto" ${c.auto ? "checked" : ""}> Automatisch nachführen (nach dem Speichern und nach „Vorbereiten › Übernehmen“)</label>
      <label class="check sm"><input type="checkbox" data-mropt="playlists" ${c.playlists ? "checked" : ""}> Playlists als M3U8 mit relativen Pfaden mitschreiben</label>
      <label class="check sm"><input type="checkbox" data-mropt="online_only" ${c.online_only ? "checked" : ""}> Kopien „nur online“ stellen (Platz auf diesem Rechner sparen${o.windows ? "" : " – unter macOS im Finder „Speicherplatz freigeben“"})</label></div></div>
    <div class="fold-acts"><button class="ghost sm" data-mrest ${c.folder ? "" : "disabled"}>Platz schätzen …</button>
      <button class="primary sm" data-mrrun ${c.folder ? "" : "disabled"}>Spiegel nachführen</button>
      ${o.extra ? `<button class="ghost sm" data-mrextra>${fmtN(o.extra)} überzählige Datei(en) …</button>` : ""}
      <span class="muted sm" id="mrLast">${last}</span></div>`;
}

function mirrorCollect() {
  const box = $("#stMirror");
  const all = [...box.querySelectorAll("[data-mrlib]")];
  const on = all.filter((x) => x.checked).map((x) => x.dataset.mrlib);
  const opt = (k) => { const el = box.querySelector(`[data-mropt="${k}"]`); return !!(el && el.checked); };
  return { folder: $("#mrFolder").value.trim(), layout: $("#mrLayout").value, libraries: on.length === all.length ? [] : on,
           auto: opt("auto"), playlists: opt("playlists"), online_only: opt("online_only") };
}

async function mirrorSave() {
  try { await call("mirror_set", mirrorCollect()); } catch (e) { toast(String(e.message || e)); }
  stMirrorRender();
}

const mrSize = (n) => (n ? fsize(n) : "0");

/** Platzschätzung – Musik gesamt, schon im Spiegel, noch zu kopieren, Sicherungen, freier Platz */
async function mirrorEstimateDialog() {
  let e;
  try { e = await call("mirror_estimate"); } catch (err) { return toast(String(err.message || err)); }
  const row = (k, v) => `<tr><th scope="row">${esc(k)}</th><td>${v}</td></tr>`;
  const libs = (e.libs || []).map((x) => row(x.name, `${fmtN(x.files)} Titel · ${fsize(x.bytes)}${x.copy ? ` · ${fmtN(x.copy)} zu kopieren (${fsize(x.copy_bytes)})` : " · aktuell"}`)).join("");
  await modal({ title: "Spiegel – benötigter Platz", wide: true,
    html: `<div class="fx-table"><table><tbody>
      ${row("Ziel", `<code translate="no">${esc(e.folder)}</code>`)}
      ${libs}
      ${row("Musik gesamt", `<b>${fsize(e.music)}</b> (${fmtN(e.files)} Titel)`)}
      ${row("Davon schon im Spiegel", mrSize(e.present))}
      ${row("Noch zu kopieren", mrSize(e.to_copy))}
      ${e.other ? row("Sicherungen der Programmdaten", fsize(e.other)) : ""}
      ${row("Benötigt in der Cloud (ca.)", `<b>${fsize(e.total)}</b>`)}
      ${row("Frei auf diesem Laufwerk", e.free == null ? "unbekannt" : fsize(e.free) + (e.free < e.to_copy ? ' · <span class="st-missing">zu wenig für die Kopien</span>' : ""))}
      ${e.extra ? row("Überzählig im Spiegel", `${fmtN(e.extra)} Datei(en), ${fsize(e.extra_bytes)} – werden nur nach Rückfrage gelöscht`) : ""}
    </tbody></table></div>
    <p class="muted sm">Den freien Platz in deinem Cloud-Abo kennt TagStudio ohne Anmeldung nicht – vergleiche „Benötigt in der Cloud“ mit deinem Speicher (z. B. onedrive.live.com › Speicher). Jede Tag-Änderung lädt die ganze Datei neu hoch.</p>`,
    buttons: [{ label: "OK", value: null, primary: true }] });
}

/** Überzählige Dateien im Spiegel – Auswahl, löschen nur nach Bestätigung */
async function mirrorExtraDialog() {
  const x = await call("mirror_extra");
  if (!x.files.length) { toast("Keine überzähligen Dateien."); return stMirrorRender(); }
  const sel = await modal({ title: "Überzählige Dateien im Spiegel", wide: true,
    html: `<p style="margin:0 0 6px">Diese Dateien liegen im Spiegel, aber nicht mehr in der Bibliothek (gelöscht, verschoben oder umbenannt).</p>
      <div class="mr-extra">${x.files.map((f, i) => `<label class="check sm"><input type="checkbox" data-mrx="${i}" checked> <code translate="no">${esc(f.rel)}</code></label>`).join("")}</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Markierte löschen …", value: true, primary: true }],
    collect: (b) => [...b.querySelectorAll("[data-mrx]:checked")].map((el) => x.files[+el.dataset.mrx].path) });
  if (!sel || !sel.length) return;
  const ok = await dialog({ title: "Im Spiegel löschen?", text: `${sel.length} Datei(en) im Spiegel löschen? Die Bibliothek bleibt unverändert; die Cloud legt gelöschte Dateien meist in ihren Papierkorb.`,
    buttons: [{ label: "Abbrechen", value: false }, { label: "Löschen", value: true, primary: true }] });
  if (!ok) return;
  const r = await call("mirror_delete_extra", sel);
  toast(`${r.deleted} gelöscht${r.errors.length ? `, ${r.errors.length} Fehler` : ""}.`);
  stMirrorRender();
}

document.addEventListener("change", (e) => {
  if (e.target.closest("#stMirror") && e.target.matches("#mrFolder,#mrLayout,[data-mrlib],[data-mropt]")) mirrorSave();
});

document.addEventListener("click", async (e) => {
  if (!e.target.closest("#stMirror")) return;
  if (e.target.closest("[data-mrpick]")) {
    const p = await call("pick_path", "", true, $("#mrFolder").value.trim());
    if (p) { $("#mrFolder").value = p; mirrorSave(); }
  } else if (e.target.closest("[data-mrsuggest]")) {
    $("#mrFolder").value = $("#mrFolder").placeholder; mirrorSave();
  } else if (e.target.closest("[data-mrest]")) {
    await mirrorEstimateDialog();
  } else if (e.target.closest("[data-mrrun]")) {
    const r = await runTask(call("start_mirror"), "Spiegel nachführen");
    stMirrorRender();
    if (!r || r.cancelled) return;
    status(r.message, "info");
    if (r.mirror_extra) await mirrorExtraDialog();
  } else if (e.target.closest("[data-mrextra]")) {
    await mirrorExtraDialog();
  }
});
