/* MarKusSXCH TagStudio – einfacher XML-Editor (Baum + Quelltext). Nutzt call/dialog/applyState aus app.js. */
"use strict";

const XE = { side: null, key: null, editable: false, original: "", text: "", decl: "", doc: null,
  valid: true, err: null, tab: "tree", dirty: false, checkTimer: null, hlTimer: null };

const xmlDeclOf = (s) => (s.match(/^\s*(<\?xml\b[^>]*\?>)/) || [, ""])[1];

// ---------------------------------------------------------------------- öffnen / schließen
/** opts.tag: Index einer Tagger-Datei (sonst Seite L/R im Vergleich) */
async function openXml(side, key, opts = {}) {
  const tag = opts.tag ?? null;
  const r = tag !== null ? await call("tag_xml", tag, key) : await call("get_xml", side, key);
  if (!r.ok) { toast(r.error); return; }
  Object.assign(XE, { side, key, tag, editable: r.editable, original: r.text, text: r.text, decl: xmlDeclOf(r.text),
    dirty: false, err: null, valid: true });
  $("#xmlTitle").textContent = `XML-Editor – ${r.label}`;
  $("#xmlSub").textContent = `${r.file}${tag !== null ? "" : side === "L" ? " · links" : " · rechts"}${r.blob ? ` · Binärfeld (${r.blob}) – nur der XML-Teil wird ersetzt` : ""}${r.editable ? "" : " · nur ansehen"}`;
  $("#xmlOk").textContent = r.editable ? "Übernehmen" : "Schließen";
  $("#xmlCancel").hidden = !r.editable;
  $("#xmlFormat").disabled = $("#xmlCompact").disabled = !r.editable;
  $("#xmlText").readOnly = !r.editable;
  $("#xmlFind").value = "";
  $("#xmlEd").hidden = false;
  setXmlTab(XE.text.length > 400000 ? "src" : "tree");
  await xmlValidate();
  xmlInfo();
}

async function closeXml(commit) {
  if (commit && XE.editable && XE.text !== XE.original) {
    if (!XE.valid) {
      const go = await dialog({ title: "XML ist nicht gültig", text: `${xmlErrText()}\n\nTrotzdem übernehmen?`,
        buttons: [{ label: "Zurück", value: null, primary: true }, { label: "Trotzdem übernehmen", value: true }] });
      if (!go) return;
    }
    if (XE.tag !== null) taggerApplyDetail(await call("tag_set", [XE.tag], XE.key, XE.text));
    else applyState(await call("set_value", XE.side, XE.key, XE.text));
  } else if (!commit && XE.text !== XE.original) {
    const go = await dialog({ title: "Änderungen verwerfen?", text: "Die Änderungen im XML-Editor gehen verloren.",
      buttons: [{ label: "Weiter bearbeiten", value: null }, { label: "Verwerfen", value: true, primary: true }] });
    if (!go) return;
  }
  $("#xmlEd").hidden = true;
  (XE.tag !== null ? $("#tgTable") : $("#table")).focus();
}

function setXmlTab(tab) {
  if (tab === "tree" && XE.tab === "src") reparse();
  XE.tab = tab;
  $$("[data-xtab]").forEach((b) => { b.classList.toggle("on", b.dataset.xtab === tab); b.setAttribute("aria-selected", String(b.dataset.xtab === tab)); });
  $(".xml-dlg").classList.toggle("mode-src", tab === "src");
  $("#xmlTree").hidden = tab !== "tree";
  $("#xmlSrc").hidden = tab !== "src";
  if (tab === "tree") renderTree();
  else { const ta = $("#xmlText"); if (ta.value !== XE.text) ta.value = XE.text; highlight(); ta.focus(); }
}

// ---------------------------------------------------------------------- Prüfen
async function xmlValidate() {
  const r = await call("xml_tool", "check", XE.text);
  XE.valid = r.ok;
  XE.err = r.ok ? null : r;
  const st = $("#xmlStatus");
  st.className = "xml-status " + (r.ok ? "ok" : "bad");
  st.textContent = r.ok ? "✓ Gültiges XML" : "✗ " + xmlErrText();
  st.disabled = r.ok;
  if (XE.tab === "src") gutter();
}
const xmlErrText = () => (XE.err ? `Zeile ${XE.err.line}, Spalte ${XE.err.col}: ${XE.err.error}` : "");

function xmlInfo() {
  const lines = XE.text.split("\n").length;
  const kb = (new Blob([XE.text]).size / 1024).toFixed(1).replace(".", ",");
  $("#xmlInfo").textContent = `${lines} Zeile${lines === 1 ? "" : "n"} · ${kb} KB` + (XE.text !== XE.original ? " · geändert" : "");
}

function changed(text, from) {
  XE.text = text;
  if (from !== "src") { const ta = $("#xmlText"); if (ta.value !== text) ta.value = text; }
  clearTimeout(XE.checkTimer);
  XE.checkTimer = setTimeout(xmlValidate, 250);
  xmlInfo();
}

async function xmlTool(action) {
  const r = await call("xml_tool", action, XE.text);
  if (!r.ok) { XE.err = r; XE.valid = false; await xmlValidate(); toast("Erst die Fehlerstelle korrigieren."); setXmlTab("src"); jumpToError(); return; }
  changed(r.text, "tool");
  if (XE.tab === "tree") { reparse(); renderTree(); } else { $("#xmlText").value = r.text; highlight(); }
}

function jumpToError() {
  if (!XE.err) return;
  setXmlTab("src");
  const ta = $("#xmlText"), lines = XE.text.split("\n");
  let pos = 0;
  for (let i = 0; i < XE.err.line - 1 && i < lines.length; i++) pos += lines[i].length + 1;
  pos += Math.max(0, XE.err.col - 1);
  ta.focus();
  ta.setSelectionRange(pos, Math.min(XE.text.length, pos + 1));
  const lh = 20;
  ta.scrollTop = Math.max(0, (XE.err.line - 5) * lh);
}

// ---------------------------------------------------------------------- Baum
function reparse() {
  const doc = new DOMParser().parseFromString(XE.text, "application/xml");
  XE.doc = doc.getElementsByTagName("parsererror").length ? null : doc;
}

function serialize() {
  let s = new XMLSerializer().serializeToString(XE.doc);
  s = s.replace(/^<\?xml[^>]*\?>\s*/, "");
  return XE.decl ? XE.decl + (XE.text.startsWith(XE.decl + "\n") ? "\n" : "") + s : s;
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function input(value, cls, label, onChange) {
  const i = el("input", "xin " + cls);
  i.value = value;
  i.size = Math.max(3, Math.min(60, value.length + 1));
  i.readOnly = !XE.editable;
  i.setAttribute("aria-label", label);
  i.spellcheck = false;
  i.addEventListener("input", () => { i.size = Math.max(3, Math.min(60, i.value.length + 1)); onChange(i.value); changed(serialize(), "tree"); });
  return i;
}

let nodeCount = 0;
function renderTree() {
  const box = $("#xmlTree");
  box.innerHTML = "";
  if (!XE.doc) reparse();
  if (!XE.doc) {
    box.appendChild(el("div", "xml-msg", "Das XML ist nicht gültig und kann nicht als Baum angezeigt werden. Bitte im Quelltext korrigieren."));
    return;
  }
  nodeCount = 0;
  const frag = document.createDocumentFragment();
  if (XE.decl) frag.appendChild(el("div", "cm", XE.decl));
  for (const n of XE.doc.childNodes) { const v = renderNode(n, 0); if (v) { v.classList.add("root"); frag.appendChild(v); } }
  box.appendChild(frag);
}

function renderNode(n, depth) {
  if (n.nodeType === Node.COMMENT_NODE) return el("div", "cm", `<!--${n.data}-->`);
  if (n.nodeType === Node.PROCESSING_INSTRUCTION_NODE) return el("div", "cm", `<?${n.target} ${n.data}?>`);
  if (n.nodeType === Node.TEXT_NODE || n.nodeType === Node.CDATA_SECTION_NODE) {
    if (!n.data.trim()) return null;
    const row = el("div", "xtext");
    row.appendChild(el("span", "lbl", n.nodeType === Node.CDATA_SECTION_NODE ? "CDATA" : "Text"));
    row.appendChild(input(n.data, "tv", "Text", (v) => { n.data = v; }));
    return row;
  }
  if (n.nodeType !== Node.ELEMENT_NODE) return null;
  nodeCount++;
  const wrap = el("div", "xn");
  const row = el("div", "xr");
  const kids = [...n.childNodes].filter((c) => !(c.nodeType === Node.TEXT_NODE && !c.data.trim()));
  const textOnly = kids.length === 1 && kids[0].nodeType === Node.TEXT_NODE;
  const hasKids = kids.length && !textOnly;
  const tw = el("button", "tw" + (hasKids ? "" : " leaf"));
  tw.innerHTML = '<svg class="i" viewBox="0 0 24 24" style="width:14px;height:14px"><path d="m6 9 6 6 6-6"/></svg>';
  tw.setAttribute("aria-label", "auf-/zuklappen");
  tw.addEventListener("click", () => wrap.classList.toggle("closed"));
  row.appendChild(tw);
  row.appendChild(el("span", "tg", "<" + n.tagName));
  for (const a of [...n.attributes]) {
    row.appendChild(el("span", "an", a.name));
    row.appendChild(el("span", "eq", "="));
    row.appendChild(input(a.value, "av", `Attribut ${a.name}`, (v) => { a.value = v; }));
  }
  if (!kids.length) { row.appendChild(el("span", "tg", "/>")); wrap.appendChild(row); return wrap; }
  row.appendChild(el("span", "tg", ">"));
  if (textOnly) {
    row.appendChild(input(kids[0].data, "tv", `Text von ${n.tagName}`, (v) => { kids[0].data = v; }));
    row.appendChild(el("span", "tg", `</${n.tagName}>`));
    wrap.appendChild(row);
    return wrap;
  }
  const nEl = kids.filter((c) => c.nodeType === Node.ELEMENT_NODE).length;
  row.appendChild(el("span", "xc", `… ${nEl} Element${nEl === 1 ? "" : "e"}`));
  wrap.appendChild(row);
  const box = el("div", "xk");
  for (const c of kids) { const v = renderNode(c, depth + 1); if (v) box.appendChild(v); }
  box.appendChild(el("div", "xr", "")).appendChild(el("span", "tg", `</${n.tagName}>`));
  wrap.appendChild(box);
  if (depth >= 2 && nodeCount > 250) wrap.classList.add("closed");
  return wrap;
}

function findInTree(q) {
  const rows = $$("#xmlTree .xr, #xmlTree .xtext");
  rows.forEach((r) => r.classList.remove("hit"));
  q = q.trim().toLowerCase();
  if (!q) return;
  let first = null;
  for (const r of rows) {
    const txt = (r.textContent + " " + [...r.querySelectorAll("input")].map((i) => i.value).join(" ")).toLowerCase();
    if (txt.includes(q)) {
      r.classList.add("hit");
      for (let p = r.parentElement; p && p.id !== "xmlTree"; p = p.parentElement) if (p.classList.contains("xn")) p.classList.remove("closed");
      first = first || r;
    }
  }
  if (first) first.scrollIntoView({ block: "center" });
}

// ---------------------------------------------------------------------- Quelltext mit Hervorhebung
const XML_TOKEN = /(<!--[\s\S]*?(?:-->|$))|(<!\[CDATA\[[\s\S]*?(?:\]\]>|$))|(<\?[\s\S]*?(?:\?>|$))|(<\/?[A-Za-z_][\w:.\-]*)((?:\s+[^\s=>\/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?>)?|(&[#\w]+;)/g;

function hlAttrs(s) {
  let out = "", last = 0, m;
  const re = /([^\s=]+)(\s*=\s*)?("[^"]*"|'[^']*'|[^\s"']+)?/g;
  while ((m = re.exec(s))) {
    if (m.index === re.lastIndex) re.lastIndex++;
    out += esc(s.slice(last, m.index)) + `<span class="h-attr">${esc(m[1])}</span>` + esc(m[2] || "")
      + (m[3] ? `<span class="h-str">${esc(m[3])}</span>` : "");
    last = m.index + m[0].length;
  }
  return out + esc(s.slice(last));
}

function highlight() {
  const s = XE.text;
  if (s.length > 300000) { $("#xmlHl").textContent = s + "\n"; gutter(); return; } // sehr groß: ohne Farben
  let out = "", last = 0, m;
  XML_TOKEN.lastIndex = 0;
  while ((m = XML_TOKEN.exec(s))) {
    if (m.index === XML_TOKEN.lastIndex) XML_TOKEN.lastIndex++;
    out += esc(s.slice(last, m.index));
    if (m[1]) out += `<span class="h-com">${esc(m[1])}</span>`;
    else if (m[2]) out += `<span class="h-cdata">${esc(m[2])}</span>`;
    else if (m[3]) out += `<span class="h-pi">${esc(m[3])}</span>`;
    else if (m[4]) {
      out += `<span class="h-tag">${esc(m[4])}</span>${hlAttrs(m[5] || "")}`;
      const tail = m[0].slice(m[4].length + (m[5] || "").length);
      out += tail ? `<span class="h-tag">${esc(tail)}</span>` : "";
    } else if (m[7]) out += `<span class="h-ent">${esc(m[7])}</span>`;
    last = m.index + m[0].length;
  }
  out += esc(s.slice(last));
  $("#xmlHl").innerHTML = out + "\n";
  gutter();
  syncScroll();
}

function gutter() {
  const n = XE.text.split("\n").length, errLine = XE.err ? XE.err.line : -1;
  let h = "";
  for (let i = 1; i <= n; i++) h += i === errLine ? `<div class="err" title="${esc(XE.err.error)}">${i}</div>` : `<div>${i}</div>`;
  $("#xmlGutter").innerHTML = h;
  syncScroll();
}

function syncScroll() {
  const ta = $("#xmlText");
  $("#xmlHl").scrollTop = ta.scrollTop;
  $("#xmlHl").scrollLeft = ta.scrollLeft;
  $("#xmlGutter").scrollTop = ta.scrollTop;
}

// ---------------------------------------------------------------------- Ereignisse
(function bindXml() {
  $$("[data-xtab]").forEach((b) => b.addEventListener("click", () => setXmlTab(b.dataset.xtab)));
  $("#xmlFormat").addEventListener("click", () => xmlTool("format"));
  $("#xmlCompact").addEventListener("click", () => xmlTool("compact"));
  $("#xmlExpand").addEventListener("click", () => $$("#xmlTree .xn").forEach((n) => n.classList.remove("closed")));
  $("#xmlCollapse").addEventListener("click", () => $$("#xmlTree .xn .xn").forEach((n) => n.classList.add("closed")));
  let ft = null;
  $("#xmlFind").addEventListener("input", (e) => { clearTimeout(ft); ft = setTimeout(() => findInTree(e.target.value), 200); });
  $("#xmlStatus").addEventListener("click", jumpToError);
  $("#xmlOk").addEventListener("click", () => closeXml(true));
  $("#xmlCancel").addEventListener("click", () => closeXml(false));
  const ta = $("#xmlText");
  ta.addEventListener("input", () => {
    XE.text = ta.value;
    XE.doc = null;
    clearTimeout(XE.hlTimer);
    XE.hlTimer = setTimeout(highlight, XE.text.length > 50000 ? 120 : 0);
    changed(ta.value, "src");
  });
  ta.addEventListener("scroll", syncScroll);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Tab" && !e.shiftKey && !ta.readOnly) {
      e.preventDefault();
      const a = ta.selectionStart, b = ta.selectionEnd;
      ta.setRangeText("  ", a, b, "end");
      ta.dispatchEvent(new Event("input"));
    }
  });
  // Tastatur, solange der Editor offen ist (und keine Rückfrage darüber liegt)
  document.addEventListener("keydown", (e) => {
    if ($("#xmlEd").hidden || !$("#dialog").hidden) return;
    const mod = e.ctrlKey || e.metaKey;
    if (e.key === "Escape") { e.preventDefault(); closeXml(false); }
    else if (mod && (e.key === "Enter" || e.key.toLowerCase() === "s")) { e.preventDefault(); closeXml(true); }
    else return;
    e.stopImmediatePropagation();
  }, true);
  $("#xmlEd").addEventListener("keydown", (e) => e.stopPropagation());  // Tabellen-Kürzel nicht auslösen
})();
