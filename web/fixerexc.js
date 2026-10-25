/* MarKusSXCH TagStudio – Tag-Fixer: Editor für Ausnahmen (#342, #343).
   Ausnahmen je Feld bzw. Feldgruppe (Künstler und Mitwirkende, Genre, Stimmung oder ein einzelnes Feld): Namen wie
   „Above & Beyond“ werden beim Trennen von Mehrfachwerten nicht zerlegt. Vorschläge kommen aus den geladenen Titeln
   (Vergleich und Tagger), die einen Suchtext enthalten; anhaken, gesammelt übernehmen, speichern. Bestehende
   Ausnahmen sind in den Vorschlägen ausgeblendet – „Bestehende anzeigen“ oder das Auge je Eintrag blendet sie
   markiert wieder ein. */

const FXE = { exc: {}, target: "@artists", rows: [], sel: new Set(), shown: new Set(), all: false, timer: null };
const fxeNorm = (s) => String(s || "").split(/\s+/).filter(Boolean).join(" ").toLocaleLowerCase();

/** Standard-Suchtext: & plus die aktiven Trennzeichen (ohne Null-Trenner und Leerzeichen) */
function fxeDefaultFind() {
  const seps = (typeof fixerOptions === "function" ? fixerOptions().seps : []) || [];
  const terms = ["&", ...seps.filter((s) => s && s !== "\u0000").map((s) => s.trim())].filter(Boolean);
  return [...new Set(terms)].join(" ");
}

async function fixerExceptionsEdit() {
  const st = FX.settings || (FX.settings = await call("fixer_settings"));
  FXE.exc = JSON.parse(JSON.stringify(st.exceptions || {}));
  FXE.sel.clear(); FXE.shown.clear(); FXE.all = false;
  const targets = st.exc_targets || [];
  if (!targets.some((t) => t[0] === FXE.target)) FXE.target = (targets[0] || ["@artists"])[0];
  const opt = (t) => `<option value="${esc(t[0])}" ${t[0] === FXE.target ? "selected" : ""}>${esc(t[1])}${t[0].startsWith("@") ? "" : ` (${esc(t[0])})`}</option>`;
  const saved = await modal({
    title: "Ausnahmen beim Trennen", wide: true,
    html: `<p class="muted sm" style="margin:0 0 8px">Namen, die ein Trennzeichen enthalten (z. B. „Above &amp; Beyond“), werden im gewählten Feld nicht getrennt – gross/klein und Leerzeichen spielen keine Rolle.</p>
      <div class="fxe-top" data-keep-enter>
        <label>Feld <select class="inp" id="fxeTarget"><optgroup label="Gruppen">${targets.filter((t) => t[0].startsWith("@")).map(opt).join("")}</optgroup><optgroup label="Einzelne Felder">${targets.filter((t) => !t[0].startsWith("@")).map(opt).join("")}</optgroup></select></label>
        <label>Suchen <input class="inp" id="fxeFind" value="${esc(fxeDefaultFind())}" spellcheck="false" title="Mehrere Suchtexte mit Leerzeichen trennen"></label>
        <label class="check"><input type="checkbox" id="fxeAll"> Bestehende Ausnahmen anzeigen</label>
      </div>
      <div class="fxe-cols" data-keep-enter>
        <div class="fxe-left">
          <div class="muted sm" id="fxeInfo"></div>
          <div class="fx-table" id="fxeCand"></div>
          <div class="fxe-bar"><button class="ghost sm" id="fxeTake" disabled>Angehakte übernehmen</button></div>
        </div>
        <div class="fxe-right">
          <h4>Ausnahmen: <span id="fxeTName"></span></h4>
          <div id="fxeList" class="fxe-list"></div>
          <div class="fxe-add"><input class="inp" id="fxeNew" placeholder="Name hinzufügen …" spellcheck="false"><button class="ghost sm" id="fxeAdd">Hinzufügen</button></div>
        </div>
      </div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }],
    onMount: (b) => {
      $("#fxeTarget", b).onchange = (e) => { FXE.target = e.target.value; FXE.sel.clear(); FXE.shown.clear(); fxeLoad(); };
      $("#fxeFind", b).oninput = () => { clearTimeout(FXE.timer); FXE.timer = setTimeout(fxeLoad, 250); };
      $("#fxeAll", b).onchange = (e) => { FXE.all = e.target.checked; fxeRenderCand(); fxeRenderList(); };
      $("#fxeTake", b).onclick = fxeTake;
      $("#fxeAdd", b).onclick = fxeAddManual;
      $("#fxeNew", b).onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); fxeAddManual(); } };
      $("#fxeCand", b).addEventListener("change", (e) => {
        const t = e.target;
        if (t.id === "fxeCandAll") {
          fxeVisible().filter((r) => !fxeKnown(r.value)).forEach((r) => (t.checked ? FXE.sel.add(r.value) : FXE.sel.delete(r.value)));
          fxeRenderCand();
        } else if (t.dataset.fxev !== undefined) {
          const v = fxeVisible()[+t.dataset.fxev].value;
          if (t.checked) FXE.sel.add(v); else FXE.sel.delete(v);
          fxeTakeLabel();
        }
      });
      $("#fxeList", b).addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-fxeop]");
        if (!btn) return;
        const i = +btn.dataset.i, list = FXE.exc[FXE.target] || [], n = fxeNorm(list[i]);
        if (btn.dataset.fxeop === "del") { list.splice(i, 1); FXE.shown.delete(n); }
        else if (FXE.shown.has(n)) FXE.shown.delete(n); else FXE.shown.add(n);
        fxeRenderList(); fxeRenderCand();
      });
      $("#fxeList", b).addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.dataset.fxeedit !== undefined) e.target.blur(); });
      $("#fxeList", b).addEventListener("change", (e) => {
        const inp = e.target.closest("input[data-fxeedit]");
        if (!inp) return;
        const list = FXE.exc[FXE.target] || [], i = +inp.dataset.fxeedit, v = inp.value.trim();
        if (!v) list.splice(i, 1);
        else if (list.some((x, k) => k !== i && fxeNorm(x) === fxeNorm(v))) { list.splice(i, 1); toast("Diese Ausnahme gibt es schon."); }
        else list[i] = v;
        fxeRenderList(); fxeRenderCand();
      });
      fxeLoad();
    },
  });
  if (!saved) return;
  const clean = await call("set_fixer_exceptions", FXE.exc);
  FX.settings.exceptions = clean;
  fixerExcButton();
  toast("Ausnahmen gespeichert.");
  await fixerPreview();
}

const fxeList = () => FXE.exc[FXE.target] || [];
const fxeKnown = (v) => fxeList().some((x) => fxeNorm(x) === fxeNorm(v));
/** sichtbare Vorschläge: bestehende Ausnahmen nur mit „Bestehende anzeigen“ oder gezielt eingeblendet */
const fxeVisible = () => FXE.rows.filter((r) => !fxeKnown(r.value) || FXE.all || FXE.shown.has(fxeNorm(r.value)));

async function fxeLoad() {
  const find = ($("#fxeFind") || {}).value || "";
  const t = (FX.settings.exc_targets || []).find((x) => x[0] === FXE.target);
  $("#fxeTName").textContent = t ? t[1] : FXE.target;
  let r = { rows: [], files: 0 };
  try { r = await call("fixer_exception_candidates", FXE.target, find.split(/\s+/).filter(Boolean), fixerOptions().seps); } catch (e) { toast(String(e.message || e)); }
  FXE.rows = r.rows;
  FXE.files = r.files;
  fxeRenderCand(); fxeRenderList();
}

function fxeRenderCand() {
  const box = $("#fxeCand");
  if (!box) return;
  const rows = fxeVisible(), hidden = FXE.rows.length - rows.length;
  $("#fxeInfo").textContent = FXE.files
    ? `${fmtN(FXE.rows.length)} Wert(e) in ${fmtN(FXE.files)} geladenen Titeln${hidden ? ` · ${fmtN(hidden)} schon als Ausnahme ausgeblendet` : ""}`
    : "Keine Titel geladen – Vorschläge kommen aus den Titeln im Vergleich und im Tagger.";
  const free = rows.filter((r) => !fxeKnown(r.value));
  const all = free.length && free.every((r) => FXE.sel.has(r.value));
  box.innerHTML = rows.length
    ? `<table><thead><tr><th data-col="sel" data-nogrip><input type="checkbox" id="fxeCandAll" ${all ? "checked" : ""} aria-label="Alle anhaken"></th><th data-col="value">Wert</th><th data-col="count" class="r">Titel</th></tr></thead><tbody>${rows.map((r, i) => {
      const known = fxeKnown(r.value);
      return `<tr class="${known ? "fxe-known" : ""}"><td><input type="checkbox" data-fxev="${i}" ${known ? "checked disabled" : FXE.sel.has(r.value) ? "checked" : ""} aria-label="Als Ausnahme übernehmen"></td><td translate="no">${esc(r.value)}${known ? ' <span class="fxe-badge" translate="yes">Ausnahme</span>' : ""}</td><td class="r">${fmtN(r.count)}</td></tr>`;
    }).join("")}</tbody></table>`
    : `<div class="empty">${FXE.rows.length ? "Alle Treffer sind schon Ausnahmen." : "Kein Wert mit diesem Suchtext."}</div>`;
  colResize(box.querySelector("table"), "fixer-exc");
  fxeTakeLabel();
}

function fxeTakeLabel() {
  const n = [...FXE.sel].filter((v) => !fxeKnown(v)).length, b = $("#fxeTake");
  if (!b) return;
  b.textContent = n ? `Angehakte übernehmen (${fmtN(n)})` : "Angehakte übernehmen";
  b.disabled = !n;
}

function fxeTake() {
  const list = FXE.exc[FXE.target] || (FXE.exc[FXE.target] = []);
  let n = 0;
  for (const v of FXE.sel) if (!fxeKnown(v)) { list.push(v); n++; }
  FXE.sel.clear();
  fxeRenderList(); fxeRenderCand();
  if (n) toast(`${fmtN(n)} Ausnahme(n) übernommen – mit „Speichern“ sichern.`);
}

function fxeAddManual() {
  const inp = $("#fxeNew"), v = inp.value.trim();
  if (!v) return;
  if (fxeKnown(v)) { toast("Diese Ausnahme gibt es schon."); return; }
  (FXE.exc[FXE.target] || (FXE.exc[FXE.target] = [])).push(v);
  inp.value = "";
  fxeRenderList(); fxeRenderCand();
}

function fxeRenderList() {
  const box = $("#fxeList");
  if (!box) return;
  const list = fxeList();
  box.innerHTML = list.length ? list.map((x, i) => {
    const on = FXE.all || FXE.shown.has(fxeNorm(x));
    return `<div class="fxe-item${on ? " shown" : ""}"><button class="ghost sm icon" data-fxeop="eye" data-i="${i}" title="${on ? "In den Vorschlägen ausblenden" : "In den Vorschlägen einblenden"}" aria-pressed="${on}" ${FXE.all ? "disabled" : ""}>${on ? "◉" : "○"}</button><input class="inp" data-fxeedit="${i}" value="${esc(x)}" translate="no" spellcheck="false" aria-label="Ausnahme bearbeiten"><button class="ghost sm icon" data-fxeop="del" data-i="${i}" title="Ausnahme entfernen" aria-label="Ausnahme entfernen">✕</button></div>`;
  }).join("") : '<div class="muted sm">Noch keine Ausnahmen für dieses Feld.</div>';
}

/** Knopf im Tag-Fixer mit der Zahl aller Ausnahmen */
function fixerExcButton() {
  const n = Object.values((FX.settings || {}).exceptions || {}).reduce((a, l) => a + l.length, 0);
  $$("#fxExc, #fxExc2").forEach((b) => { b.textContent = n ? `Ausnahmen … (${fmtN(n)})` : "Ausnahmen …"; });
}
