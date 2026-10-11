/* MarKusSXCH TagStudio – Profile (#164, #165): Auswahl beim Start, Verwaltung in den Einstellungen.
   Ein Profil hat eigene Einstellungen und Daten; Plugins und grosse Plugin-Daten werden geteilt. Logik in paths.py. */
"use strict";

/** Profilwahl beim Start. → true, wenn TagStudio mit einem anderen Profil neu startet */
async function profilePick(p) {
  const r = await modal({
    title: "Profil wählen",
    html: `<p class="muted sm" style="margin:0 0 10px">Jedes Profil hat eigene Einstellungen und Daten (Sicherungen, Snapshots, Vorbereiten, Entdecken). Plugins werden gemeinsam genutzt.</p>
      <div class="prof-list">${p.list.map((n) => `<label class="check prof-it"><input type="radio" name="profPick" value="${esc(n)}" ${n === p.name ? "checked" : ""}> <b>${esc(n)}</b>${n === p.name ? ' <span class="muted sm">(aktuell)</span>' : ""}</label>`).join("")}</div>
      <label class="check" style="margin-top:12px"><input type="checkbox" id="profNoAsk"> Künftig nicht mehr fragen (umstellbar unter Einstellungen › Profile)</label>`,
    buttons: [{ label: "Starten", value: true, primary: true }],
    collect: (b) => ({ name: (b.querySelector('input[name="profPick"]:checked') || {}).value || p.name, ask: !$("#profNoAsk", b).checked }),
  });
  const ch = r || { name: p.name, ask: true };
  const res = await call("profile_choose", ch.name, ch.ask);
  if (res && res.restart) { status(`Starte mit Profil „${ch.name}“ …`, "info"); return true; }
  return false;
}

async function stProfilesRender() {
  const box = $("#stProfiles"); if (!box) return;
  const p = await call("profile_info");
  box.innerHTML = `<div class="st-row">
      <span>Aktuelles Profil</span><div><b>${esc(p.name)}</b> <span class="muted sm">${esc(p.dir)}</span></div>
      <span>Profile</span><div class="prof-rows">${p.list.map((n) => `<div class="prof-row"><span>${esc(n)}${n === p.name ? ' <span class="muted sm">(aktuell)</span>' : ""}</span>
        <span class="prof-acts">${n !== p.name ? `<button class="ghost sm" data-prof-switch="${esc(n)}">Wechseln</button>` : ""}<button class="ghost sm" data-prof-link="${esc(n)}" title="Verknüpfung „TagStudio (${esc(n)})“ auf dem Desktop anlegen">Verknüpfung</button></span></div>`).join("")}</div>
      <span>Neues Profil</span><div class="st-path"><input id="profNew" class="inp" placeholder="Name, z. B. Test" spellcheck="false" style="max-width:220px">
        <label class="check sm"><input type="checkbox" id="profCopy"> Einstellungen von „${esc(p.name)}“ übernehmen</label><button class="ghost sm" id="profAdd">Anlegen</button></div>
      <span></span><span class="muted sm">Ein neues, leeres Profil startet wie eine frische Installation – mit Einrichtungsassistent. Plugins, die Stems-Umgebung und Modelle werden mitbenutzt; Einstellungen, Anmeldungen und Protokolle sind je Profil getrennt.</span>
      <span>Beim Start</span>${stCheck("profAsk", p.ask_setting, "Profil beim Start auswählen (wenn es mehrere gibt)")}
    </div>`;
}

(function bindProfiles() {
  document.addEventListener("click", async (e) => {
    const sw = e.target.closest("[data-prof-switch]"), ln = e.target.closest("[data-prof-link]");
    if (e.target.id === "profAdd") {
      const name = $("#profNew").value.trim();
      try {
        const r = await call("profile_create", name, $("#profCopy").checked);
        toast(`Profil „${r.created}“ angelegt.`);
        stProfilesRender();
      } catch (x) { toast(String(x.message || x)); }
    } else if (sw) {
      if (S.meta && S.meta.unsaved && !(await dialog({ title: "Profil wechseln", text: "Es gibt ungespeicherte Änderungen. Trotzdem wechseln? Sie gehen verloren.", buttons: [{ label: "Abbrechen", value: null }, { label: "Wechseln", value: true, primary: true }] }))) return;
      const r = await call("profile_choose", sw.dataset.profSwitch, (await call("profile_info")).ask_setting);
      if (r.restart) status(`Starte mit Profil „${sw.dataset.profSwitch}“ …`, "info");
    } else if (ln) {
      try { const r = await call("profile_shortcut", ln.dataset.profLink); toast(`Verknüpfung angelegt: ${r.path}`); } catch (x) { toast(String(x.message || x)); }
    }
  });
  document.addEventListener("change", async (e) => { if (e.target.id === "profAsk") await call("profile_set_ask", e.target.checked); });
})();
