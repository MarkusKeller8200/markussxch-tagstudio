/* MarKusSXCH TagStudio – Einkäufe: Korrekturfenster für unklare und fehlende Zuweisungen (#338).
   Je nach Grund: mehrere Treffer → Kandidaten mit Tags vergleichen und den richtigen zuordnen; anderer Mix → Titel,
   Untertitel und Dateinamen der Datei anpassen (mit Sicherung) und erneut prüfen; anderer Künstler → Ähnlichkeit der
   Künstler je Kandidat; nicht gefunden → Datei von Hand wählen. „Weiter ›“ springt zum nächsten unklaren Kauf. */

const PUR_KIND = {
  multi: ["Mehrere Treffer", "Den richtigen Titel aus der Liste wählen und zuordnen."],
  dur: ["Länge weicht ab", "Die Länge passt nicht genau – Kandidaten vergleichen und den richtigen zuordnen."],
  mix: ["Anderer Mix", "Die Datei hat einen anderen Mix. Stimmt die Datei, Titel, Untertitel bzw. Dateinamen anpassen und erneut prüfen."],
  similar: ["Titel ähnlich", "Nur ein ähnlicher Titel gefunden – vergleichen, anpassen oder zuordnen."],
  artist: ["Anderer Künstler", "Gleicher Titel, aber anderer Künstler – die Ähnlichkeit hilft beim Entscheiden."],
  missing: ["Nicht gefunden", "Kein passender Titel in der Bibliothek – Datei von Hand wählen oder herunterladen."],
};

/** Unklare und fehlende Einkäufe in der Reihenfolge der Tabelle (ohne Vorbestellungen) */
const purOpenList = () => purVisible().filter((r) => (r.status === "unclear" || r.status === "missing") && !r.preorder
  && (!PUR.sel.size || PUR.sel.has(r.k)));                                       // #345: nur markierte, wenn welche markiert sind

async function purCorrect(k) {
  let key = k || (purOpenList()[0] || {}).k;
  while (key) {
    const next = await purCorrectOne(key);
    if (next !== "next") break;
    const list = purOpenList(), i = list.findIndex((r) => r.k === key);
    key = (list[i + 1] || (i < 0 ? list[0] : null) || {}).k;
    if (!key) toast("Keine weiteren unklaren Einkäufe.");
  }
}

async function purCorrectOne(key) {
  let c;
  try { c = await call("purch_candidates", key); } catch (e) { toast(String(e.message || e)); return null; }
  const r = c.row, kind = PUR_KIND[c.kind] ? c.kind : (r.status === "missing" ? "missing" : "multi");
  const [head, help] = PUR_KIND[kind];
  const editable = ["mix", "similar", "dur"].includes(kind);
  const fmtD = (s) => (s ? fmtTime(s) : "");
  const sug = { title: r.title, sub: r.mix && !/^original( mix)?$/i.test(r.mix) ? r.mix : "",
    name: `${r.artist} - ${r.title}${r.mix ? ` (${r.mix})` : ""}` };
  const more = purOpenList().length;
  const res = await modal({
    title: `Korrigieren – ${head}`, wide: "xl",
    html: `<div class="pc-buy"><span class="muted sm">Kauf</span><b translate="no">${esc(r.artist)} – ${esc(r.title)}${r.mix ? ` (${esc(r.mix)})` : ""}</b>
        <span class="muted sm">${[fmtD(r.dur), r.key || "", r.bpm ? `${Math.round(r.bpm)} BPM` : "", r.catalog].filter(Boolean).map(esc).join(" · ")}</span></div>
      <p class="muted sm" style="margin:6px 0 8px">${esc(help)}${r.reason ? ` <span class="pc-why">(${esc(r.reason)})</span>` : ""}${c.strict ? ' · <span class="pc-strict">Abgleich streng</span>' : ""}</p>
      ${c.cands.length ? `<div class="fx-table pc-table"><table><thead><tr><th data-col="sel" data-nogrip></th><th data-col="file">Datei</th><th data-col="artist">Künstler</th><th data-col="title">Titel</th><th data-col="mix">Mix</th><th data-col="dur" class="r">Länge</th><th data-col="bpm" class="r">BPM</th><th data-col="key">Tonart</th></tr></thead><tbody>
        ${c.cands.map((x, i) => `<tr data-i="${i}" class="click${i === 0 ? " sel" : ""}"><td><input type="radio" name="pcPick" value="${i}" ${i === 0 ? "checked" : ""} aria-label="Kandidat wählen"></td>
          <td translate="no" title="${esc(x.path)}">${esc(x.name)}${x.ok ? "" : ' <span class="pc-why">fehlt</span>'}</td>
          <td translate="no">${esc(x.artist)}${kind === "artist" || x.artist_sim < 100 ? ` <span class="pc-sim${x.artist_sim >= 80 ? " hi" : ""}" translate="yes" title="Ähnlichkeit der Künstler">${x.artist_sim} %</span>` : ""}</td>
          <td translate="no">${esc(x.title)}${x.subtitle ? ` <span class="muted sm">· ${esc(x.subtitle)}</span>` : ""}</td>
          <td translate="no">${esc(x.mix || "–")}</td><td class="r">${fmtD(x.dur)}</td><td class="r">${esc(x.bpm)}</td><td>${x.key ? keyBadge(x.key) : ""}</td></tr>`).join("")}
        </tbody></table></div>` : '<div class="muted sm">Keine Kandidaten aus dem Abgleich.</div>'}
      ${editable && c.cands.length ? `<div class="pc-edit">
        <h4>Gewählte Datei anpassen</h4>
        <label>Dateiname</label><input class="inp" id="pcName" spellcheck="false" translate="no">
        <label>Titel</label><input class="inp" id="pcTitle" spellcheck="false" translate="no">
        <label>Untertitel</label><input class="inp" id="pcSub" spellcheck="false" translate="no" placeholder="z. B. Extended Mix">
        <span></span><div class="pc-edit-btns"><button class="ghost sm" id="pcSuggest" title="Werte des Kaufs einsetzen">Wie der Kauf</button><button class="ghost sm" id="pcFix">Ändern und prüfen</button><span class="muted sm" id="pcMsg"></span></div>
      </div>` : ""}`,
    buttons: [{ label: "Schliessen", value: null }, { label: "Datei wählen …", value: "pick" },
      ...(c.cands.length ? [{ label: "Zuordnen", value: "link" }] : []),
      { label: more > 1 || r.status === "library" ? "Weiter ›" : "Fertig", value: "next", primary: true }],
    onMount: (b) => {
      const pickIdx = () => +((b.querySelector('input[name="pcPick"]:checked') || {}).value || 0);
      const fill = () => {
        const x = c.cands[pickIdx()];
        if (!x || !$("#pcName", b)) return;
        $("#pcName", b).value = x.name.replace(/\.mp3$/i, "");
        $("#pcTitle", b).value = x.title;
        $("#pcSub", b).value = x.subtitle;
      };
      const tb = $(".pc-table", b);
      if (tb) {
        colResize(tb.querySelector("table"), "purch-correct");
        tb.addEventListener("click", (e) => {
          const tr = e.target.closest("tr[data-i]");
          if (!tr) return;
          tr.querySelector("input").checked = true;
          $$("tr.sel", tb).forEach((x) => x.classList.remove("sel"));
          tr.classList.add("sel");
          fill();
        });
      }
      fill();
      if ($("#pcSuggest", b)) $("#pcSuggest", b).onclick = () => { $("#pcName", b).value = sug.name; $("#pcTitle", b).value = sug.title; $("#pcSub", b).value = sug.sub; };
      if ($("#pcFix", b)) $("#pcFix", b).onclick = async () => {
        const x = c.cands[pickIdx()];
        $("#pcMsg", b).textContent = "…";
        try {
          const f = await call("purch_fix_file", key, x.path, $("#pcTitle", b).value, $("#pcSub", b).value, $("#pcName", b).value);
          if (!f.ok) { $("#pcMsg", b).textContent = f.error; return; }
          x.path = f.path; x.name = f.path.split(/[\\/]/).pop();
          purApply(f.state);
          $("#pcMsg", b).textContent = f.sure ? "✓ Passt jetzt – zugeordnet." : `Geändert, passt noch nicht (${f.reason || "kein sicherer Treffer"}).`;
          $("#pcMsg", b).className = f.sure ? "sm pc-ok" : "sm pc-why";
        } catch (e) { $("#pcMsg", b).textContent = String(e.message || e); }
      };
    },
    collect: (b, v) => (v === "link" ? { link: c.cands[+((b.querySelector('input[name="pcPick"]:checked') || {}).value || 0)].path } : v),
  });
  if (res && res.link) {
    try { purApply(await call("purch_link", key, res.link)); toast("Zugeordnet – bleibt bei weiteren Abgleichen."); }
    catch (e) { toast(String(e.message || e)); }
    return "next";
  }
  if (res === "pick") {
    const p = await call("pick_file", "mp3", r.file || (PUR.st.roots || [])[0] || "");
    if (!p) return null;
    try { purApply(await call("purch_link", key, p)); toast("Zugeordnet – bleibt bei weiteren Abgleichen."); }
    catch (e) { toast(String(e.message || e)); }
    return "next";
  }
  return res;
}
