/* MarKusSXCH TagStudio – JSON-Baum: Schlüssel/Wert-Paare wie im XML-Editor anzeigen und nur die Werte bearbeiten.
   Das Format (Einrückung, Reihenfolge, Leerzeichen, Escapes) bleibt erhalten: geändert werden nur die Zeichen
   der bearbeiteten Werte im Originaltext. */
"use strict";

/** JSON mit Positionen parsen → Knoten {type, start, end, raw, kids:[{key, node}]} oder Fehler. */
function jsonScan(text) {
  let i = 0;
  const n = text.length;
  const fail = (msg) => { const e = new Error(msg); e.pos = i; throw e; };
  const ws = () => { while (i < n && " \t\r\n".includes(text[i])) i++; };
  const str = () => {
    const s = i++;
    while (i < n && text[i] !== '"') { if (text[i] === "\\") i++; i++; }
    if (i >= n) fail("Zeichenkette nicht abgeschlossen");
    i++;
    return { type: "string", start: s, end: i, raw: text.slice(s, i) };
  };
  const val = () => {
    ws();
    const c = text[i];
    if (c === "{") {
      const s = i++; const kids = [];
      ws();
      if (text[i] === "}") { i++; return { type: "object", start: s, end: i, kids }; }
      for (;;) {
        ws();
        if (text[i] !== '"') fail("Schlüssel erwartet");
        const k = str();
        ws();
        if (text[i] !== ":") fail("„:“ erwartet");
        i++;
        kids.push({ key: JSON.parse(k.raw), node: val() });
        ws();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === "}") { i++; return { type: "object", start: s, end: i, kids }; }
        fail("„,“ oder „}“ erwartet");
      }
    }
    if (c === "[") {
      const s = i++; const kids = [];
      ws();
      if (text[i] === "]") { i++; return { type: "array", start: s, end: i, kids }; }
      for (;;) {
        kids.push({ key: kids.length, node: val() });
        ws();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === "]") { i++; return { type: "array", start: s, end: i, kids }; }
        fail("„,“ oder „]“ erwartet");
      }
    }
    if (c === '"') return str();
    const m = /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(text.slice(i, i + 64));
    if (!m) fail("Wert erwartet");
    const s = i; i += m[0].length;
    const raw = m[0];
    return { type: raw === "null" ? "null" : raw === "true" || raw === "false" ? "bool" : "number", start: s, end: i, raw };
  };
  try {
    const root = val();
    ws();
    if (i < n) fail("Text nach dem Ende");
    return { ok: true, root };
  } catch (e) {
    const before = text.slice(0, e.pos ?? i);
    const line = before.split("\n").length, col = before.length - before.lastIndexOf("\n");
    return { ok: false, error: `Zeile ${line}, Spalte ${col}: ${e.message}` };
  }
}

/** Ist der Text ein JSON-Objekt bzw. -Array? */
function isJsonDoc(text) {
  const s = (text || "").trim();
  return (s.startsWith("{") || s.startsWith("[")) && jsonScan(s).ok;
}

/** Baum-Editor in box. onChange() bei jeder Änderung. Rückgabe: {text(), valid(), expandAll(open)}. */
function jsonTreeEditor(box, text, onChange) {
  const scan = jsonScan(text);
  const edits = new Map();          // Knoten → neuer Rohtext
  const bad = new Set();
  box.innerHTML = "";
  box.classList.add("json-tree");
  if (!scan.ok) {
    box.appendChild(jel("div", "xml-msg", "Kein gültiges JSON – bitte in der Textansicht korrigieren. " + scan.error));
    return { text: () => text, valid: () => false, expandAll: () => {} };
  }
  const asciiOnly = /\\u00[89a-f][0-9a-f]|\\u0[1-9a-f][0-9a-f]{2}|\\u[1-9a-f][0-9a-f]{3}/i.test(text);
  const encStr = (s) => {
    let j = JSON.stringify(s);
    if (asciiOnly) j = j.replace(/[\u007f-￿]/g, (ch) => "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0"));
    return j;
  };

  const leaf = (node, label) => {
    if (node.type === "string") {
      const inp = jin(JSON.parse(node.raw), "av", label);
      inp.addEventListener("input", () => { set(node, encStr(inp.value)); jgrow(inp); });
      return inp;
    }
    if (node.type === "number") {
      const inp = jin(node.raw, "num", label);
      inp.inputMode = "decimal";
      inp.addEventListener("input", () => {
        const v = inp.value.trim().replace(",", ".");
        const ok = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(v);
        inp.classList.toggle("bad", !ok);
        if (ok) { bad.delete(node); set(node, v); } else { bad.add(node); onChange(); }
        jgrow(inp);
      });
      return inp;
    }
    if (node.type === "bool") {
      const lab = jel("label", "jbool");
      const cb = document.createElement("input");
      cb.type = "checkbox"; cb.checked = node.raw === "true"; cb.setAttribute("aria-label", label);
      const t = jel("span", "", node.raw);
      cb.addEventListener("change", () => { t.textContent = String(cb.checked); set(node, String(cb.checked)); });
      lab.append(cb, t);
      return lab;
    }
    return jel("span", "jnull", "null");
  };

  const set = (node, raw) => {
    if (raw === node.raw) edits.delete(node); else edits.set(node, raw);
    onChange();
  };

  const render = (key, node, depth) => {
    const wrap = jel("div", "xn" + (depth ? "" : " root"));
    const row = jel("div", "xr");
    const branch = node.type === "object" || node.type === "array";
    const tw = jel("button", "tw" + (branch && node.kids.length ? "" : " leaf"));
    tw.type = "button";
    tw.innerHTML = '<svg class="i" viewBox="0 0 24 24" style="width:14px;height:14px"><path d="m6 9 6 6 6-6"/></svg>';
    tw.setAttribute("aria-label", "auf-/zuklappen");
    tw.addEventListener("click", () => wrap.classList.toggle("closed"));
    row.appendChild(tw);
    if (key !== null) {
      row.appendChild(jel("span", typeof key === "number" ? "jidx" : "an", typeof key === "number" ? `[${key}]` : key));
      row.appendChild(jel("span", "eq", ":"));
    }
    if (branch) {
      row.appendChild(jel("span", "tg", node.type === "object" ? "{" : "["));
      row.appendChild(jel("span", "xc", `${node.kids.length} ${node.type === "object" ? "Einträge" : "Elemente"} …`));
      wrap.appendChild(row);
      const kids = jel("div", "xk");
      for (const k of node.kids) kids.appendChild(render(k.key, k.node, depth + 1));
      wrap.appendChild(kids);
      const close = jel("div", "xr jclose");
      close.appendChild(jel("span", "tg", node.type === "object" ? "}" : "]"));
      wrap.appendChild(close);
    } else {
      row.appendChild(leaf(node, String(key ?? "Wert")));
      wrap.appendChild(row);
    }
    return wrap;
  };

  box.appendChild(render(null, scan.root, 0));
  return {
    text: () => {
      let out = text;
      [...edits.entries()].sort((a, b) => b[0].start - a[0].start).forEach(([nd, raw]) => {
        out = out.slice(0, nd.start) + raw + out.slice(nd.end);
      });
      return out;
    },
    valid: () => bad.size === 0,
    changed: () => edits.size > 0,
    expandAll: (open) => box.querySelectorAll(".xn").forEach((x) => x.classList.toggle("closed", !open)),
  };
}

function jel(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function jin(value, cls, label) {
  const i = jel("input", "xin " + cls);
  i.value = value; i.spellcheck = false; i.setAttribute("aria-label", label);
  jgrow(i);
  return i;
}
function jgrow(i) { i.size = Math.max(3, Math.min(60, i.value.length + 1)); }
