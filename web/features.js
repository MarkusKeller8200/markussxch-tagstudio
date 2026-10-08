/* MarKusSXCH TagStudio – Audio-Merkmale im Tagger (TXXX:ENERGY … 0–100).
   Schieberegler + Zahlenfeld je Merkmal; funktioniert auch für mehrere markierte Dateien. */
"use strict";

function featSection(d) {
  const list = (TG.settings && TG.settings.features) || [];
  if (!list.length || !d.features) return "";
  const set = list.filter(([n]) => d.features[n].value !== "" || d.features[n].mixed).length;
  const rows = list.map(([n, label, desc]) => {
    const v = d.features[n], num = v.num;
    const cls = v.mixed ? "mixed" : num === null ? (v.value ? "bad" : "empty") : "";
    const pos = num === null ? 50 : num;
    return `<div class="ft-row ${cls}" data-feat="${n}">
      <label for="tgx-${n}" title="${esc(desc)}">${esc(label)}</label>
      <input type="range" id="tgr-${n}" min="0" max="100" step="1" value="${pos}" data-frange="${n}" aria-label="${esc(label)}" style="--p:${pos}%">
      <input id="tgx-${n}" class="ft-num" data-fnum="${n}" inputmode="numeric" value="${esc(v.value)}"
        placeholder="${v.mixed ? "versch." : "–"}" spellcheck="false" aria-label="${esc(label)} Wert" ${v.value && num === null ? 'title="Ungültiger Wert – bitte 0–100 eintragen"' : ""}>
      <button class="ft-x" data-fclear="${n}" title="${esc(label)} entfernen" aria-label="${esc(label)} entfernen" ${v.value || v.mixed ? "" : "disabled"}><svg class="i" viewBox="0 0 24 24"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
    </div>`;
  }).join("");
  return `<details class="tg-feat" id="tgFeat" ${TG.settings.features_open ? "open" : ""}>
    <summary><span>Audio-Merkmale</span><span class="muted sm">${set ? `${set} von ${list.length} gesetzt` : "keine gesetzt"} · 0–100</span></summary>
    <div class="ft-grid">${rows}</div></details>`;
}

async function featCommit(name, value) {
  const d = await call("tag_feature_set", tgSelected(), name, value);
  if (d && d.error) { toast(d.error); }
  taggerApplyDetail(d);
}

(function bindFeatures() {
  const ed = $("#tgEdit");
  ed.addEventListener("input", (e) => {
    const r = e.target.closest("[data-frange]"); if (!r) return;
    const row = r.closest(".ft-row");
    row.classList.remove("empty", "mixed", "bad");
    row.querySelector("[data-fnum]").value = r.value;
    r.style.setProperty("--p", r.value + "%");
  });
  ed.addEventListener("change", (e) => {
    const r = e.target.closest("[data-frange]");
    if (r) featCommit(r.dataset.frange, r.value);
  });
  const numCommit = (inp) => {
    const n = inp.dataset.fnum, v = TG.detail.features[n];
    const val = inp.value.trim();
    if (val === v.value || (v.mixed && val === "")) return;
    featCommit(n, val);
  };
  ed.addEventListener("keydown", (e) => {
    const inp = e.target.closest("[data-fnum]"); if (!inp) return;
    if (e.key === "Enter") { e.preventDefault(); numCommit(inp); }
    if (e.key === "Escape") { e.preventDefault(); inp.value = TG.detail.features[inp.dataset.fnum].value; }
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      const cur = parseInt(inp.value, 10);
      const step = e.shiftKey ? 10 : 1;
      inp.value = String(clamp((isNaN(cur) ? 50 : cur) + (e.key === "ArrowUp" ? step : -step), 0, 100));
    }
  });
  ed.addEventListener("focusout", (e) => { const inp = e.target.closest("[data-fnum]"); if (inp) numCommit(inp); });
  ed.addEventListener("click", (e) => {
    const b = e.target.closest("[data-fclear]"); if (b) featCommit(b.dataset.fclear, "");
  });
  ed.addEventListener("toggle", (e) => {
    if (e.target.id !== "tgFeat") return;
    TG.settings.features_open = e.target.open;
    call("tag_features_open", e.target.open);
  }, true);
})();
