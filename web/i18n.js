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
  lang: "de-CH", langs: [], exact: new Map(), pats: [], memo: new Map(), obs: null,
  done: new WeakMap(),                  // Knoten → zuletzt gesetzte Übersetzung (nicht doppelt übersetzen)
  attrs: ["title", "data-tip-title", "placeholder", "aria-label", "alt"],
};
const I18N_NUM = /(?<![\w{])[-+]?\d+(?:['’.,]\d+)*(?![\w}])/g;
const I18N_QUOTE = /„[^„“”\n]*[“”]|"[^"\n]*"|«[^«»\n]*»|“[^“”\n]*”/g;
const I18N_SKIP = "script,style,textarea,code,pre,.cm-editor,[contenteditable=''],[contenteditable='true'],.no-i18n";

function i18nActive() { return I18N.lang !== "de-CH" && (I18N.exact.size > 0 || I18N.pats.length > 0); }

/** Katalog übernehmen: Einträge ohne {x} direkt (in Laufzeitform), mit {x} als Muster */
function i18nSetCatalog(lang, cat) {
  I18N.lang = lang || "de-CH";
  I18N.exact = new Map(); I18N.pats = []; I18N.memo = new Map();
  for (let [k0, v] of Object.entries(cat || {})) {
    const k = i18nSkel(k0).key.replace(/^·\s*|\s*·$/g, "");          // „· …“/„… ·“ wie ohne Punkt
    v = v.replace(/^·\s*|\s*·$/g, "");
    if (!k.includes("{x}")) { I18N.exact.set(k, v); continue; }
    const lits = k.split(/\{[nqx]\}/).map((s) => s.trim()).filter(Boolean).sort((a, b) => b.length - a.length);
    const re = new RegExp("^" + k.split(/(\{[nqx]\})/).map((p) =>
      p === "{n}" ? "([-+]?\\d+(?:['’.,]\\d+)*)" : p === "{q}" ? "(„[^„“”\\n]*[“”]|\"[^\"\\n]*\"|«[^«»\\n]*»|“[^“”\\n]*”)" : p === "{x}" ? "(.*?)"
        : p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("") + "$", "s");
    I18N.pats.push({ re, kinds: (k.match(/\{[nqx]\}/g) || []), v, lit: lits[0] || "" });
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
  if (kind === "x") return i18nLine(v.trim()) === v.trim() ? v : v.replace(v.trim(), i18nLine(v.trim()));
  return v;
}
function i18nFill(tpl, vals) {
  let k = 0;
  return tpl.replace(/\{[nqx]\}/g, (m) => (k < vals.length ? i18nVal(vals[k][0], vals[k++][1]) : m));
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
    const m = p.re.exec(s);
    if (m) return i18nFill(p.v, p.kinds.map((k, i) => [k.slice(1, 2), m[i + 1]]));
  }
  const pre = /^([^:\n]{2,80}:)\s+([\s\S]+)$/.exec(s);                // „Wiedergabe nicht möglich: …“
  if (pre && I18N.exact.has(pre[1])) return I18N.exact.get(pre[1]) + " " + i18nLine(pre[2]);
  const lead = /^([·•–—]\s+)([\s\S]+)$/.exec(s);                     // „· 3 markiert“
  if (lead) { const r = i18nLine(lead[2]); if (r !== lead[2]) return lead[1] + r; }
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
  if (typeof s !== "string" || !s || I18N.lang === "de-CH") return s;
  const hit = I18N.memo.get(s);
  if (hit !== undefined) return hit;
  // erst als Ganzes (Zeilenumbrüche aus dem Quelltext sind nur Leerraum), sonst zeilenweise (Tooltips mit \n)
  const w = /^(\s*)([\s\S]*?)(\s*)$/.exec(s), whole = w[2].replace(/\s+/g, " ");
  const tw = whole && /[A-Za-zÄÖÜäöü]/.test(whole) ? i18nLine(whole) : whole;
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
  I18N.langs = r.langs || [];
  i18nSetCatalog(r.lang, r.catalog);
  try { localStorage.setItem("ts_lang", I18N.lang); } catch (e) { /* egal */ }
  if (was !== "de-CH" && I18N.lang !== was) { location.reload(); return; }   // bereits übersetzte Texte zurückholen
  i18nApply();
  document.documentElement.classList.remove("i18n-wait");
}

/** Sprache beim Start: gespeichert; beim ersten Start aus der Systemsprache; sonst de-CH */
function i18nStartLang(ui, first) {
  if (ui && ui.lang) return ui.lang;
  if (!first) return "de-CH";                                   // bestehende Installation: wie bisher
  const nav = (navigator.languages && navigator.languages[0]) || navigator.language || "de-CH";
  const a = nav.toLowerCase();
  return a.startsWith("gsw") ? "gsw-u-sd-chzh" : a.startsWith("de") ? "de-CH" : "en";
}

/** Flaggen als SVG (Windows zeigt Flaggen-Emojis nur als Buchstaben) */
const I18N_FLAGS = {
  "de-CH": '<svg viewBox="0 0 32 32" class="flag" aria-hidden="true"><rect width="32" height="32" rx="3" fill="#D52B1E"/><path d="M13 6h6v7h7v6h-7v7h-6v-7H6v-6h7z" fill="#fff"/></svg>',
  en: '<svg viewBox="0 0 60 30" class="flag" aria-hidden="true"><clipPath id="i18nUk"><path d="M0 0v30h60V0z"/></clipPath><clipPath id="i18nUk2"><path d="M30 15h30v15zv15H0zH0V0zV0h30z"/></clipPath><g clip-path="url(#i18nUk)"><path d="M0 0v30h60V0z" fill="#012169"/><path d="M0 0l60 30m0-30L0 30" stroke="#fff" stroke-width="6"/><path d="M0 0l60 30m0-30L0 30" clip-path="url(#i18nUk2)" stroke="#C8102E" stroke-width="4"/><path d="M30 0v30M0 15h60" stroke="#fff" stroke-width="10"/><path d="M30 0v30M0 15h60" stroke="#C8102E" stroke-width="6"/></g></svg>',
  "gsw-u-sd-chzh": '<svg viewBox="0 0 32 32" class="flag" aria-hidden="true"><rect width="32" height="32" rx="3" fill="#fff" stroke="#c9d4e2"/><path d="M32 0v29a3 3 0 0 1-3 3H0z" fill="#0F5BA7"/></svg>',
};
function i18nFlag(code) { return I18N_FLAGS[code] || ""; }

/** Sprachwahl (Einstellungen › Darstellung): Knöpfe mit Flagge, Namen in der eigenen Sprache (nicht übersetzt) */
function i18nPickerHtml() {
  const list = I18N.langs.length ? I18N.langs : [{ code: "de-CH", name: "Deutsch (Schweiz)", de: "Hochdeutsch (Schweiz)" }];
  return `<div class="seg lang-seg" id="stLang" translate="no">${list.map((l) =>
    `<button data-lang="${l.code}"${l.code === I18N.lang ? ' class="on"' : ""} title="${l.de} (${l.code})">${i18nFlag(l.code)}${l.name}</button>`).join("")}</div>`;
}
async function i18nPick(code) {
  if (!code || code === I18N.lang) return;
  LAYOUT.lang = code;
  try { await call("set_ui", "lang", code); } catch (e) { /* trotzdem anwenden */ }
  if (code === "de-CH") { try { localStorage.setItem("ts_lang", code); } catch (e) { /* egal */ } location.reload(); return; }
  await i18nLoad(code);
  document.querySelectorAll("#stLang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === code));
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("#stLang [data-lang]");
  if (b) { e.preventDefault(); i18nPick(b.dataset.lang); }
});

// Browser-Dialoge ebenfalls übersetzen
(function i18nDialogs() {
  for (const k of ["alert", "confirm", "prompt"]) {
    const orig = window[k];
    if (typeof orig !== "function") continue;
    window[k] = function (msg, ...rest) { return orig.call(window, tr(String(msg ?? "")), ...rest); };
  }
  setTimeout(() => document.documentElement.classList.remove("i18n-wait"), 4000);   // Sicherheitsnetz
})();
