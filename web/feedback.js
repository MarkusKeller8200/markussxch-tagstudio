/* MarKusSXCH TagStudio – Fehler melden / Funktion vorschlagen (#187).
   Sicherer Start: TagStudio füllt das GitHub-Formular vor und öffnet es im Browser. Abgeschickt wird erst dort mit der
   eigenen GitHub-Anmeldung – TagStudio speichert und sendet keine Zugangsdaten. Neue Meldungen erhalten „triage“
   und werden erst nach Freigabe durch den Projektverantwortlichen umgesetzt. Nutzt call/modal/esc/toast aus app.js. */
"use strict";

const FB = { info: null, kind: "bug", vals: {}, step: "form", prep: null, dup: null, dupQ: "" };
const FB_HELP = {
  what: "Was hast du erwartet, was ist stattdessen passiert? Fehlermeldung wörtlich.",
  steps: "1. Ordner … im Tagger einlesen\n2. Titel markieren, Feld … ändern\n3. Speichern → Fehler …",
  extra: "Betroffene Feldnamen (z. B. TXXX:…), Herkunft der Dateien (Beatport, Serato …)",
  problem: "Welches Problem soll gelöst werden bzw. was möchtest du erreichen?",
  solution: "Wo in der Oberfläche, welche Felder, welches Verhalten?",
  alternatives: "Andere Programme, die das schon können (Mp3tag, Rekordbox …)",
};

/** Dialog öffnen. kind: "bug" | "feature"; area: vorgewählter Bereich (z. B. „Tagger“). */
async function fbOpen(kind = "bug", area = "") {
  try { FB.info = FB.info || await call("feedback_info", !!window.pywebview); } catch (e) { toast(String(e.message || e)); return; }
  FB.kind = kind; FB.step = "form"; FB.prep = null; FB.dup = null; FB.dupQ = "";
  FB.vals = { area: area || "", sendEnv: true };
  await modal({
    title: "Fehler melden / Funktion vorschlagen", wide: true,
    html: '<div id="fbBody"></div>',
    buttons: [{ label: "Schliessen", value: null }],
    onMount: (b) => {
      b.addEventListener("click", (e) => {
        const a = e.target.closest("a[data-url]"); if (a) { e.preventDefault(); call("open_url", a.dataset.url); return; }
        const k = e.target.closest("[data-fbkind]"); if (k) { fbCollect(b); FB.kind = k.dataset.fbkind; fbRender(b); return; }
        if (e.target.closest("#fbPreview")) fbPreview(b);
        if (e.target.closest("#fbBack")) { FB.step = "form"; fbRender(b); }
        if (e.target.closest("#fbSearch")) fbSearch(b, true);
        if (e.target.closest("#fbGo")) fbGo(b);
      });
      b.addEventListener("change", (e) => { if (e.target.id === "fbConsent") $("#fbGo", b).disabled = !e.target.checked; });
      b.addEventListener("focusout", (e) => { if (e.target.id === "fbTitle") { fbCollect(b); fbSearch(b, false); } });
      fbRender(b);
    },
  });
}

function fbCollect(b) {
  b.querySelectorAll("[data-fb]").forEach((i) => { FB.vals[i.dataset.fb] = i.type === "checkbox" ? i.checked : i.value; });
}

function fbRender(b) {
  const box = $("#fbBody", b), d = FB.info, k = FB.kind, v = FB.vals;
  if (FB.step === "preview") return fbRenderPreview(box);
  if (FB.step === "done") return fbRenderDone(box);
  const req = new Set(d.required[k]);
  const fields = d.fields[k].filter(([id]) => !["version", "os", "variant", "area"].includes(id));
  box.innerHTML = `
    <div class="fb-kind" role="radiogroup" aria-label="Art der Meldung">
      <button class="sn-chip${k === "bug" ? " on" : ""}" data-fbkind="bug" role="radio" aria-checked="${k === "bug"}">Fehler melden</button>
      <button class="sn-chip${k === "feature" ? " on" : ""}" data-fbkind="feature" role="radio" aria-checked="${k === "feature"}">Funktion vorschlagen</button>
    </div>
    <p class="hint">Die Meldung erscheint <b>öffentlich</b> auf GitHub. Bitte keine MP3s, Liedtexte, Zugangsdaten oder persönlichen
      Angaben eintragen – Benutzerordner, E-Mail-Adressen und lange Schlüssel werden vor dem Öffnen automatisch geschwärzt.
      Sicherheitslücken bitte <a href="#" data-url="https://github.com/MarkusKeller8200/markussxch-tagstudio/security/advisories/new">privat melden</a>.</p>
    <div class="frm fb-frm">
      <label for="fbTitle">Titel *</label>
      <div><input id="fbTitle" data-fb="title" value="${esc(v.title || "")}" placeholder="${k === "bug" ? "z. B. Speichern bricht bei Cover über 5 MB ab" : "z. B. Liedtexte im Player anzeigen"}" spellcheck="true">
        <div class="sm"><button class="ghost sm" id="fbSearch" title="Vorhandene Meldungen mit ähnlichem Titel suchen">Ähnliche Meldungen suchen</button></div>
        <div id="fbDup" class="sm">${fbDupHtml()}</div></div>
      <label for="fbArea">Bereich</label>
      <select id="fbArea" data-fb="area" class="inp"><option value="">(bitte wählen)</option>${d.areas[k].map((a) =>
        `<option ${a === v.area ? "selected" : ""}>${esc(a)}</option>`).join("")}</select>
      ${fields.map(([id, label]) => `<label for="fb-${id}">${esc(label)}${req.has(id) ? " *" : ""}</label>
        <textarea id="fb-${id}" data-fb="${id}" class="inp" rows="${id === "extra" || id === "alternatives" ? 3 : 4}" placeholder="${esc(FB_HELP[id] || "")}">${esc(v[id] || "")}</textarea>`).join("")}
      ${k === "bug" ? `<span></span><label class="fb-env"><input type="checkbox" data-fb="sendEnv" ${v.sendEnv !== false ? "checked" : ""}>
        Version und System mitsenden: <b>${esc(d.env.version)}</b> · ${esc(d.env.os)} · ${esc(d.env.variant)}</label>` : ""}
      <span></span><div class="svc-btns"><button class="primary sm" id="fbPreview">Vorschau …</button></div>
    </div>`;
}

function fbDupHtml() {
  if (!FB.dup) return "";
  if (FB.dup.error) return `<span class="muted">${esc(FB.dup.error)}</span>`;
  if (!FB.dup.items.length) return '<span class="muted">Keine ähnlichen Meldungen gefunden.</span>';
  return `<div class="fb-dup"><span class="muted">Ähnliche Meldungen – vielleicht gibt es deine schon (dann dort ergänzen):</span><ul>${FB.dup.items.map((x) =>
    `<li><a href="#" data-url="${esc(x.url)}">#${x.number} ${esc(x.title)}</a> <span class="muted">(${x.state === "open" ? "offen" : "erledigt"})</span></li>`).join("")}</ul></div>`;
}

async function fbSearch(b, force) {
  const q = (FB.vals.title || "").trim();
  if (q.length < 4 || (!force && q === FB.dupQ)) return;
  FB.dupQ = q;
  const box = $("#fbDup", b);
  if (box) box.innerHTML = '<span class="muted">suche …</span>';
  try { FB.dup = await call("feedback_search", q); } catch (e) { FB.dup = { items: [], error: String(e.message || e) }; }
  const el = $("#fbDup", b); if (el) el.innerHTML = fbDupHtml();
}

async function fbPreview(b) {
  fbCollect(b);
  const v = FB.vals, f = { ...v };
  if (FB.kind === "bug" && v.sendEnv !== false) Object.assign(f, FB.info.env);
  delete f.sendEnv;
  try { FB.prep = await call("feedback_prepare", FB.kind, f); } catch (e) { toast(String(e.message || e)); return; }
  FB.step = "preview";
  if (!FB.dup) fbSearch(b, true);
  fbRender(b);
}

function fbRenderPreview(box) {
  const p = FB.prep;
  box.innerHTML = `<p class="hint">So wird das GitHub-Formular vorausgefüllt. Abgeschickt wird erst im Browser – dort meldest du dich
      mit deinem GitHub-Konto an und klickst „Submit new issue“. Die Meldung erhält die Labels ${p.labels.map((l) => `<code>${esc(l)}</code>`).join(" ")}
      und wartet auf die Prüfung durch den Projektverantwortlichen.</p>
    ${p.redacted.length ? `<div class="fb-warn">Geschwärzt: ${p.redacted.map(esc).join(", ")}. Bitte die Vorschau prüfen.</div>` : ""}
    ${p.truncated ? '<div class="fb-warn">Der Text ist sehr lang und wurde gekürzt – den Rest bitte im Formular ergänzen.</div>' : ""}
    <table class="help-t fb-prev"><tbody>${p.preview.map(([k, v]) => `<tr><th>${esc(k)}</th><td><pre>${esc(v)}</pre></td></tr>`).join("")}</tbody></table>
    <div id="fbDup" class="sm">${fbDupHtml()}</div>
    <label class="fb-consent"><input type="checkbox" id="fbConsent"> Ich bin einverstanden, dass diese Meldung <b>öffentlich</b> auf GitHub erscheint.</label>
    <div class="svc-btns"><button class="ghost sm" id="fbBack">Zurück</button><button class="primary sm" id="fbGo" disabled>Auf GitHub öffnen</button></div>`;
}

function fbGo(b) {
  if (!$("#fbConsent", b)?.checked || !FB.prep) return;
  call("open_url", FB.prep.url);
  FB.step = "done";
  fbRender(b);
}

function fbRenderDone(box) {
  box.innerHTML = `<p><b>Das Formular ist im Browser geöffnet.</b> Dort anmelden und „Submit new issue“ klicken.</p>
    <p class="muted">Status danach: <b>Eingereicht – wartet auf Prüfung</b> (Label <code>triage</code>). Ohne GitHub-Konto lässt sich dort
      kostenlos eines anlegen. Wenn nichts geöffnet wurde (offline?), später nochmals versuchen – die Eingaben bleiben bis zum Schliessen erhalten.</p>
    <p><a href="#" data-url="${esc(FB.prep.mine)}">Meine Meldungen auf GitHub ansehen ↗</a></p>
    <div class="svc-btns"><button class="ghost sm" id="fbBack">Zurück zum Formular</button></div>`;
}
