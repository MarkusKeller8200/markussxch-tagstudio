/* MarKusSXCH TagStudio – Mehrsprachigkeit der Oberfläche (#157).
   Ausgangssprache ist Schweizer Hochdeutsch (de-CH) und steht direkt im Code. Für andere Sprachen übersetzt diese
   Schicht die Oberfläche beim Anzeigen: Textknoten und die Attribute title / data-tip-title / placeholder / aria-label /
   alt werden über den Katalog (deutscher Text → Übersetzung) ersetzt – auch alles, was später dazukommt
   (MutationObserver). Platzhalter im Katalog: {n} Zahl, {q} Text in „…“ (Inhalt wird mitübersetzt), {x} beliebiger
   Text (wird seinerseits übersetzt). Nicht übersetzt wird, was in [translate="no"] steht (Dateinamen, Tag-Werte),
   in Eingabefeldern, Code und Editoren. Fehlt eine Übersetzung, bleibt der deutsche Text stehen.
   Muss vor app.js geladen werden; tr()/t() stehen allen Modulen zur Verfügung. */
"use strict";

const I18N = {
  lang: "de-CH", pref: "de-CH", langs: [], exact: new Map(), pats: [], memo: new Map(), obs: null,
  miss: (() => { try { return localStorage.getItem("ts_i18n_miss") ? new Set() : null; } catch (e) { return null; } })(),
  done: new WeakMap(),                  // Knoten → zuletzt gesetzte Übersetzung (nicht doppelt übersetzen)
  attrs: ["title", "data-tip-title", "placeholder", "aria-label", "alt"],
};
const I18N_NUM = /(?<![\w{])[-+]?\d+(?:['’.,]\d+)*(?![\w}])/g;
const I18N_QUOTE = /„[^„“”\n]*[“”]|"[^"\n]*"|«[^«»\n]*»|“[^“”\n]*”/g;
const I18N_SKIP = "script,style,textarea,code,pre,.cm-editor,[contenteditable=''],[contenteditable='true'],.no-i18n";

function i18nActive() { return I18N.exact.size > 0 || I18N.pats.length > 0; }   // auch de-CH mit eigenen Texten

/** Katalog übernehmen: Einträge ohne {x} direkt (in Laufzeitform), mit {x} als Muster */
function i18nSetCatalog(lang, cat) {
  I18N.lang = lang || "de-CH";
  I18N.exact = new Map(); I18N.pats = []; I18N.memo = new Map();
  // „· …“/„… ·“ wie ohne Punkt – aber ein eigener Eintrag ohne Punkt hat Vorrang („· Tagger“ ≠ „Tagger“)
  const ents = Object.entries(cat || {}).map(([k0, v]) => [i18nSkel(k0).key, v]);
  const dot = /^·\s*|\s*·$/g, plain = new Set(ents.filter(([k]) => !k.match(dot)).map(([k]) => k));
  for (let [k, v] of ents) {
    if (k.match(dot)) { const kk = k.replace(dot, ""); if (plain.has(kk)) continue; k = kk; v = v.replace(dot, ""); }
    if (!k.includes("{x}")) { I18N.exact.set(k, v); continue; }
    const lits = k.split(/\{[nqx]\}/).map((s) => s.trim()).filter(Boolean).sort((a, b) => b.length - a.length);
    const re = new RegExp("^" + k.split(/(\{[nqx]\})/).map((p, i, arr) =>
      p === "{n}" ? "([-+]?\\d+(?:['’.,]\\d+)*)" : p === "{q}" ? "(„[^„“”\\n]*[“”]|\"[^\"\\n]*\"|«[^«»\\n]*»|“[^“”\\n]*”)" : p === "{x}" ? "(.*?)"
        : p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
            .replace(/\s+$/, arr[i + 1] === "{x}" ? "\\s*" : "\\s+").replace(/^\s+/, arr[i - 1] === "{x}" ? "\\s*" : "\\s+")
            .replace(/(?<!\\s)\s+(?![*+])/g, "\\s+")).join("") + "$", "s");
    const litLen = lits.reduce((n, x) => n + x.length, 0);
    I18N.pats.push({ re, kinds: (k.match(/\{[nqx]\}/g) || []), v, lit: lits[0] || "", litLen, segs: lits.length });
  }
  I18N.pats.sort((a, b) => b.lit.length - a.lit.length);   // spezifischere Muster zuerst
  document.documentElement.lang = I18N.lang;
}

/** Laufzeitform eines Textes: Zahlen → {n}, Anführungszeichen → {q}; Werte in Reihenfolge */
function i18nSkel(s) {
  const vals = [];
  const key = s.replace(/\{n\}|\{q\}|\{x\}/g, "\u0000$&\u0000")         // Platzhalter im Katalog schützen
    .replace(I18N_QUOTE, (m) => { vals.push(["q", m]); return "\u0001"; })
    .replace(I18N_NUM, (m) => { vals.push(["n", m]); return "\u0002"; });
  // Reihenfolge der Werte nach Position im Text
  const order = [];
  key.replace(/[\u0001\u0002]/g, (m, pos) => { order.push(m === "\u0001" ? "q" : "n"); return m; });
  const qs = vals.filter((v) => v[0] === "q").map((v) => v[1]), ns = vals.filter((v) => v[0] === "n").map((v) => v[1]);
  const ordered = order.map((k) => [k, k === "q" ? qs.shift() : ns.shift()]);
  return { key: key.replace(/\u0001/g, "{q}").replace(/\u0002/g, "{n}").replace(/\u0000/g, "").replace(/\s+/g, " ").trim(), vals: ordered };
}

/** Wert eines Platzhalters einsetzen: Zahlen unverändert, Zitate und {x} mitübersetzen */
function i18nVal(kind, v) {
  if (kind === "q") {
    const inner = v.slice(1, -1), open = v[0], close = v[v.length - 1];
    const tt = i18nLine(inner);
    if (I18N.lang === "en" && open === "„") return `“${tt}”`;
    return open + tt + close;
  }
  if (kind === "x") return i18nX(v);
  if (I18N.lang === "en" && /^\d{1,3}(['’]\d{3})+$/.test(v)) return v.replace(/['’]/g, ",");   // 641'243 → 641,243
  return v;
}
/** eingesetzter Teil: als Ganzes, sonst Zusätze „, …“ einzeln („, Testabfrage ohne Track, API-Tester“) */
function i18nX(v) {
  const t = v.trim(), r = i18nLine(t);
  if (r !== t) return v.replace(t, r);
  const parts = t.split(/(?=, )/);
  if (parts.length < 2) return v;
  const out = parts.map((p) => i18nLine(p));
  return out.some((x, k) => x !== parts[k]) ? v.replace(t, out.join("")) : v;
}
function i18nFill(tpl, vals) {
  let k = 0;
  return tpl.replace(/\{[nqx]\}/g, (m) => (k < vals.length ? i18nVal(vals[k][0], vals[k++][1]) : m));
}

/** nur exakte Treffer (auch in Laufzeitform) – für mehrzeilige Texte als Ganzes */
function i18nExact(s) {
  const hit = I18N.exact.get(s);
  if (hit !== undefined) return hit;
  const sk = i18nSkel(s), v = I18N.exact.get(sk.key);
  return v !== undefined ? i18nFill(v, sk.vals) : s;
}

/** eine Zeile übersetzen (ohne Rand-Leerraum); unbekannt → unverändert */
function i18nLine(s) {
  if (!s) return s;
  const hit = I18N.exact.get(s);
  if (hit !== undefined) return hit;
  const sk = i18nSkel(s);
  const v = I18N.exact.get(sk.key);
  if (v !== undefined) return i18nFill(v, sk.vals);
  for (const p of I18N.pats) {
    if (p.lit && !s.includes(p.lit)) continue;
    // Muster mit nur einem festen Teil (z. B. „Künstler {x}“): nicht, wenn {x} unübersetzten deutschen Fliesstext
    // fängt – sonst würde „Künstler des ganzen Albums …“ fälschlich zu „Artist des ganzen Albums …“
    const m = p.re.exec(s);
    if (m && p.segs < 2 && p.kinds.some((k, i) => k === "{x}" && /(^|[\s(])[a-zäöüß]{3,}(?=[\s.,;:)…]|$)/.test(m[i + 1] || "")
        && i18nX(m[i + 1] || "") === (m[i + 1] || ""))) continue;
    if (m) return i18nFill(p.v, p.kinds.map((k, i) => [k.slice(1, 2), m[i + 1]])).replace(/\s+$/, "").replace(/\s+([.,;:])$/, "$1");
  }
  const pre = /^([^:\n]{2,80}:)\s+([\s\S]+)$/.exec(s);                // „Wiedergabe nicht möglich: …“
  if (pre && I18N.exact.has(pre[1])) return I18N.exact.get(pre[1]) + " " + i18nLine(pre[2]);
  const sort = /^([\s\S]*\S)(\s*[▴▾▸▲▼↑↓][¹²³⁴⁵⁶⁷⁸⁹]*)$/.exec(s);       // Spaltenkopf mit Sortierzeichen
  if (sort) { const r = i18nLine(sort[1]); if (r !== sort[1]) return r + sort[2]; }
  const lead = /^([·•–—]\s+)([\s\S]+)$/.exec(s);                     // „· 3 markiert“
  if (lead) { const r = i18nLine(lead[2]); if (r !== lead[2]) return lead[1] + r; }
  if (!/…$/.test(s)) {                                                // Aktionsname ohne „ …“ (Plugin-Menüs)
    const ell = I18N.exact.get(s + " …");
    if (ell !== undefined) return ell.replace(/\s*…$/, "");
  }
  // zusammengesetzte Texte: Teile zwischen „ · “ einzeln übersetzen
  if (s.includes(" · ")) {
    const parts = s.split(" · ");
    const out = parts.map((x) => i18nLine(x.trim()));
    if (out.some((x, k) => x !== parts[k].trim())) return out.join(" · ");
  }
  return s;
}

/** Text übersetzen (mehrzeilig, Rand-Leerraum bleibt) – Zwischenspeicher je Text */
function tr(s) {
  if (typeof s !== "string" || !s || (!I18N.exact.size && !I18N.pats.length)) return s;
  const hit = I18N.memo.get(s);
  if (hit !== undefined) return hit;
  // erst als Ganzes (Zeilenumbrüche aus dem Quelltext sind nur Leerraum), sonst zeilenweise (Tooltips mit \n)
  const w = /^(\s*)([\s\S]*?)(\s*)$/.exec(s), whole = w[2].replace(/\s+/g, " ");
  const tw = whole && /[A-Za-zÄÖÜäöü]/.test(whole) ? (s.includes("\n") ? i18nExact(whole) : i18nLine(whole)) : whole;
  if (I18N.miss && tw === whole && !s.includes("\n") && /[A-Za-zÄÖÜäöü]{2}/.test(whole)) I18N.miss.add(whole);   // Prüfhilfe (Tests)
  if (tw !== whole || !s.includes("\n")) {
    const res = tw !== whole ? w[1] + tw + w[3] : s;
    if (I18N.memo.size > 30000) I18N.memo.clear();
    I18N.memo.set(s, res);
    return res;
  }
  const out = s.split("\n").map((line) => {
    const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(line);
    if (!m[2] || !/[A-Za-zÄÖÜäöü]/.test(m[2])) return line;
    const norm = m[2].replace(/\s+/g, " ");
    const t = i18nLine(norm);
    if (I18N.miss && t === norm) I18N.miss.add(norm);
    return t === norm ? line : m[1] + t + m[3];
  }).join("\n");
  if (I18N.memo.size > 30000) I18N.memo.clear();
  I18N.memo.set(s, out);
  return out;
}
/** Text mit Platzhaltern {name} übersetzen und füllen: t("{n} Datei(en)", {n: 3}) */
function t(s, params) {
  let out = tr(s);
  if (params) out = out.replace(/\{(\w+)\}/g, (m, k) => (params[k] !== undefined ? String(params[k]) : m));
  return out;
}

function i18nSkip(el) {
  return !el || (el.closest && (el.closest(I18N_SKIP) || el.closest('[translate="no"]')));
}
function i18nText(node) {
  const v = node.nodeValue;
  if (!v || I18N.done.get(node) === v || !/[A-Za-zÄÖÜäöü]/.test(v)) return;
  const p = node.parentElement;
  if (!p || i18nSkip(p)) return;
  const tt = tr(v);
  if (tt !== v) { I18N.done.set(node, tt); node.nodeValue = tt; }
}
function i18nAttrs(el) {
  if (el.nodeType !== 1 || i18nSkip(el)) return;
  let rec = I18N.done.get(el);
  for (const a of I18N.attrs) {
    const v = el.getAttribute(a);
    if (!v || (rec && rec[a] === v)) continue;
    const tt = tr(v);
    if (tt !== v) { rec = rec || {}; rec[a] = tt; I18N.done.set(el, rec); el.setAttribute(a, tt); }
  }
  if (el.tagName === "INPUT" && /^(button|submit|reset)$/i.test(el.type) && el.value) {
    const tt = tr(el.value); if (tt !== el.value) el.value = tt;
  }
}
function i18nTree(root) {
  if (!root) return;
  if (root.nodeType === 3) { i18nText(root); return; }
  if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
  if (root.nodeType === 1) { if (i18nSkip(root)) return; i18nAttrs(root); }
  const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.nodeType === 1 && (n.matches(I18N_SKIP) || n.getAttribute("translate") === "no") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  for (let n = w.nextNode(); n; n = w.nextNode()) { if (n.nodeType === 3) i18nText(n); else i18nAttrs(n); }
}

/** Übersetzung einschalten (bzw. bei de-CH ausschalten); ganze Seite + alles Neue */
function i18nApply() {
  if (I18N.obs) { I18N.obs.disconnect(); I18N.obs = null; }
  document.title = tr(document.title);
  if (!i18nActive()) return;
  i18nTree(document.body);
  I18N.obs = new MutationObserver((recs) => {
    for (const r of recs) {
      if (r.type === "childList") for (const n of r.addedNodes) i18nTree(n);
      else if (r.type === "characterData") i18nText(r.target);
      else if (r.type === "attributes") i18nAttrs(r.target);
    }
  });
  I18N.obs.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: I18N.attrs.concat(["value"]) });
}

/** Sprache laden und anwenden (beim Start bzw. beim Wechsel). Ein Wechsel zurück auf de-CH lädt die Seite neu. */
async function i18nLoad(lang) {
  let r;
  try { r = await call("i18n_catalog", lang); } catch (e) { r = { lang: "de-CH", langs: [], catalog: {} }; }
  const was = I18N.lang;
  try { localStorage.setItem("ts_lang", r.lang || "de-CH"); } catch (e) { /* egal */ }
  if (was !== "de-CH" && r.lang !== was) { location.reload(); return; }   // bereits übersetzte Texte zurückholen
  I18N.langs = r.langs || [];
  i18nSetCatalog(r.lang, r.catalog);
  i18nApply();
  i18nSideRefresh();
  document.documentElement.classList.remove("i18n-wait");
}

/** Sprache des Betriebssystems (bzw. des Browsers): Deutsch – ob Deutschland oder Schweiz – wird de-CH */
function i18nSysLang() {
  const nav = (navigator.languages && navigator.languages[0]) || navigator.language || "de-CH";
  const a = nav.toLowerCase();
  return a.startsWith("gsw") ? "gsw-u-sd-chzh" : a.startsWith("de") ? "de-CH" : "en";
}

/** Gespeicherte Wahl: Sprachcode oder "auto" (Betriebssystem); beim allerersten Start "auto", sonst wie bisher Deutsch */
function i18nPref(ui, first) { return (ui && ui.lang) || (first ? "auto" : "de-CH"); }

/** Sprache beim Start (aufgelöst) */
function i18nStartLang(ui, first) {
  const p = i18nPref(ui, first);
  return p === "auto" ? i18nSysLang() : p;
}

/** Flaggen als SVG (Windows zeigt Flaggen-Emojis nur als Buchstaben) */
const I18N_FLAGS = {
  // Deutsch: Deutschland und Schweiz diagonal geteilt (oben links Deutschland, unten rechts Schweiz)
  "de-CH": '<svg viewBox="0 0 30 20" class="flag" aria-hidden="true"><path d="M0 0h30L20 6.67H0z" fill="#000"/><path d="M0 6.67h20l-10 6.66H0z" fill="#DD0000"/><path d="M0 13.33h10L0 20z" fill="#FFCE00"/><path d="M30 0v20H0z" fill="#D52B1E"/><path d="M19.8 9h2.4v3.1h3v2.4h-3v3.1h-2.4v-3.1h-3v-2.4h3z" fill="#fff"/></svg>',
  en: '<svg viewBox="0 0 60 30" class="flag" aria-hidden="true"><clipPath id="i18nUk"><path d="M0 0v30h60V0z"/></clipPath><clipPath id="i18nUk2"><path d="M30 15h30v15zv15H0zH0V0zV0h30z"/></clipPath><g clip-path="url(#i18nUk)"><path d="M0 0v30h60V0z" fill="#012169"/><path d="M0 0l60 30m0-30L0 30" stroke="#fff" stroke-width="6"/><path d="M0 0l60 30m0-30L0 30" clip-path="url(#i18nUk2)" stroke="#C8102E" stroke-width="4"/><path d="M30 0v30M0 15h60" stroke="#fff" stroke-width="10"/><path d="M30 0v30M0 15h60" stroke="#C8102E" stroke-width="6"/></g></svg>',
  "gsw-u-sd-chzh": '<svg viewBox="0 0 32 32" class="flag" aria-hidden="true"><rect width="32" height="32" rx="3" fill="#fff" stroke="#c9d4e2"/><path d="M32 0v29a3 3 0 0 1-3 3H0z" fill="#0F5BA7"/></svg>',
};
function i18nFlag(code) { return I18N_FLAGS[code] || ""; }

/** Sprachwahl (Einstellungen › Darstellung, Einrichtungsassistent): Knöpfe mit Flagge, Namen in der eigenen Sprache
 *  (nicht übersetzt), darunter die Option „Sprache des Betriebssystems verwenden“ (beim ersten Start aktiv) */
function i18nLangList() {
  return I18N.langs.length ? I18N.langs : [{ code: "de-CH", name: "Deutsch", de: "Deutsch" }];
}
function i18nPickerHtml() {
  const auto = I18N.pref === "auto";
  return `<div class="seg lang-seg" id="stLang" translate="no">${i18nLangList().map((l) =>
    `<button data-lang="${l.code}"${l.code === I18N.lang ? ' class="on"' : ""} title="${l.de} (${l.code})">${i18nFlag(l.code)}${l.name}</button>`).join("")}</div>
    <label class="check lang-sys"><input type="checkbox" data-lang-sys${auto ? " checked" : ""}> Sprache des Betriebssystems verwenden</label>`;
}
/** Sprachwahl unten in der Seitenleiste (unter „Einklappen“): Flagge + Auswahlliste; eingeklappt nur die Flagge */
function i18nSideRefresh() {
  const box = document.getElementById("sideLang");
  if (!box) return;
  const sel = box.querySelector("select"), flag = box.querySelector(".side-flag");
  const opts = [`<option value="auto">${esc0(tr("Betriebssystem"))} (${esc0((i18nLangList().find((l) => l.code === i18nSysLang()) || {}).name || "")})</option>`]
    .concat(i18nLangList().map((l) => `<option value="${l.code}">${esc0(l.name)}</option>`));
  sel.innerHTML = opts.join("");
  sel.value = I18N.pref === "auto" ? "auto" : I18N.lang;
  if (flag) flag.innerHTML = i18nFlag(I18N.lang);
  box.title = tr("Sprache der Oberfläche");
}
function esc0(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
/** #219: eigene Texte exportieren/importieren – überlagern die mitgelieferten, nur für diesen Benutzer bzw. dieses Profil */
function i18nToolsHtml() {
  return `<div class="st-path lang-tools" id="stLangTools">
      <button class="ghost sm" data-i18n-x="csv" title="Alle Texte mit den mitgelieferten Übersetzungen als CSV (für Excel) – in der letzten Spalte eigene Texte eintragen">Texte exportieren (CSV) …</button>
      <button class="ghost sm" data-i18n-x="json" title="Texte der gewählten Sprache als JSON">JSON …</button>
      <button class="ghost sm" data-i18n-imp title="Bearbeitete CSV- oder JSON-Datei einlesen – mit Prüfung und Vorschau">Texte importieren …</button>
      <button class="ghost sm" data-i18n-reset disabled title="Eigene Texte der gewählten Sprache entfernen – es gelten wieder die mitgelieferten">Eigene Texte zurücksetzen …</button></div>
    <div class="muted sm" id="stLangInfo"></div>`;
}
async function i18nToolsRefresh() {
  const el = document.getElementById("stLangInfo");
  if (!el) return;
  let r;
  try { r = await call("i18n_overlay_info", I18N.lang); } catch (e) { return; }
  const n = (r.counts || {})[I18N.lang] || 0;
  const name = (I18N.langs.find((l) => l.code === I18N.lang) || {}).name || I18N.lang;
  el.textContent = n ? t("Eigene Texte für {name}: {n} – gespeichert in {dir}", { name, n, dir: r.dir }) : t("Keine eigenen Texte für {name}.", { name });
  const b = document.querySelector("[data-i18n-reset]"); if (b) b.disabled = !n;
}
async function i18nExport(fmt) {
  if (S.settings && S.settings.native) {
    const r = await call("i18n_export", I18N.lang, fmt);
    if (r.ok) toast(t("Texte exportiert: {p}", { p: r.path })); else if (!r.cancelled) info(t("Export fehlgeschlagen"), r.error);
    return;
  }
  const r = await call("i18n_export_text", I18N.lang, fmt);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([r.text], { type: fmt === "json" ? "application/json" : "text/csv" }));
  a.download = r.name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast(t("Texte als Download gespeichert."));
}
async function i18nImport() {
  let text = "", name = "";
  if (S.settings && S.settings.native) {
    const r = await call("i18n_import_pick");
    if (!r) return;
    if (r.error) return info(t("Import nicht möglich"), r.error);
    text = r.text; name = r.name;
  } else {
    const inp = document.createElement("input");
    inp.type = "file"; inp.accept = ".csv,.json,text/csv,application/json";
    const f = await new Promise((ok) => { inp.onchange = () => ok(inp.files[0]); inp.click(); });
    if (!f) return;
    text = await f.text(); name = f.name;
  }
  let pv;
  try { pv = await call("i18n_import_preview", I18N.lang, text); } catch (e) { return info(t("Import nicht möglich"), String(e.message || e)); }
  const st = { ok: "✓", warn: "⚠", error: "✕" };
  const rows = pv.rows.slice(0, 300).map((r) => `<tr class="i18n-${r.status}"><td>${st[r.status] || ""}</td><td translate="no">${esc(r.key)}</td>
      <td translate="no">${esc(r.old || "")}</td><td translate="no"><b>${esc(r.new)}</b></td><td>${esc(r.note || "")}</td></tr>`).join("");
  const go = await modal({
    title: t("Texte importieren ({name})", { name }),
    html: `<div class="hint">${esc(t("{n} Text(e) werden übernommen · {w} mit Hinweis · {e} abgelehnt · {u} unverändert. Eigene Texte überlagern die mitgelieferten nur für dich; Updates überschreiben sie nicht.",
      { n: pv.count, w: pv.warnings, e: pv.errors, u: pv.unchanged }))}</div>
      <div class="i18n-imp"><table class="tbl"><thead><tr><th></th><th>${esc(t("Original"))}</th><th>${esc(t("Bisher"))}</th><th>${esc(t("Neu"))}</th><th>${esc(t("Hinweis"))}</th></tr></thead><tbody>${rows}</tbody></table></div>`,
    buttons: [{ label: t("Abbrechen"), value: null }, { label: t("Übernehmen"), value: true, primary: true, disabled: !pv.count }],
  });
  if (!go || !pv.count) return;
  const r = await call("i18n_import_apply", I18N.lang, text);
  toast(t("{n} eigene Text(e) gespeichert – die Oberfläche lädt neu.", { n: r.count }));
  setTimeout(() => location.reload(), 700);
}
async function i18nResetOwn() {
  const name = (I18N.langs.find((l) => l.code === I18N.lang) || {}).name || I18N.lang;
  const go = await modal({
    title: t("Eigene Texte zurücksetzen"),
    html: `<div class="hint">${esc(t("Alle eigenen Texte für {name} werden entfernt – danach gelten wieder die mitgelieferten Übersetzungen.", { name }))}</div>`,
    buttons: [{ label: t("Abbrechen"), value: null }, { label: t("Zurücksetzen"), value: true, primary: true }],
  });
  if (!go) return;
  await call("i18n_overlay_reset", I18N.lang);
  toast(t("Eigene Texte entfernt – die Oberfläche lädt neu."));
  setTimeout(() => location.reload(), 700);
}
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-i18n-x],[data-i18n-imp],[data-i18n-reset]");
  if (!b) return;
  e.preventDefault();
  if (b.dataset.i18nX) i18nExport(b.dataset.i18nX);
  else if (b.hasAttribute("data-i18n-imp")) i18nImport();
  else i18nResetOwn();
});

/** Sprache wählen: Code oder "auto" (Sprache des Betriebssystems) */
async function i18nPick(choice) {
  if (!choice || choice === I18N.pref) return;
  const code = choice === "auto" ? i18nSysLang() : choice;
  I18N.pref = choice;
  LAYOUT.lang = choice;
  try { await call("set_ui", "lang", choice); } catch (e) { /* trotzdem anwenden */ }
  if (code === I18N.lang) { i18nPickRefresh(); return; }
  if (code === "de-CH") { try { localStorage.setItem("ts_lang", code); } catch (e) { /* egal */ } location.reload(); return; }
  await i18nLoad(code);
  i18nPickRefresh();
}
function i18nPickRefresh() {
  document.querySelectorAll(".lang-seg [data-lang]").forEach((b) => b.classList.toggle("on", b.dataset.lang === I18N.lang));
  document.querySelectorAll("[data-lang-sys]").forEach((c) => { c.checked = I18N.pref === "auto"; });
  i18nSideRefresh();
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest(".lang-seg [data-lang]");
  if (b) { e.preventDefault(); i18nPick(b.dataset.lang); }
});
document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.matches && t.matches("[data-lang-sys]")) { e.stopPropagation(); i18nPick(t.checked ? "auto" : I18N.lang); }
  else if (t.id === "sideLangSel") i18nPick(t.value);
}, true);

// Browser-Dialoge ebenfalls übersetzen
(function i18nDialogs() {
  for (const k of ["alert", "confirm", "prompt"]) {
    const orig = window[k];
    if (typeof orig !== "function") continue;
    window[k] = function (msg, ...rest) { return orig.call(window, tr(String(msg ?? "")), ...rest); };
  }
  setTimeout(() => document.documentElement.classList.remove("i18n-wait"), 4000);   // Sicherheitsnetz
})();
