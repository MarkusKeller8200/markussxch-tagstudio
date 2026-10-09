/* MarKusSXCH TagStudio – JSON-Baum: Schlüssel/Wert-Paare wie im XML-Editor anzeigen und die Werte bearbeiten.
   Normalmodus: nur Werte; das Format (Einrückung, Reihenfolge, Leerzeichen, Escapes) bleibt erhalten, weil nur die
   Zeichen der geänderten Werte im Originaltext ersetzt werden.
   Expertenmodus: zusätzlich Einträge hinzufügen (z. B. neue Cue-Punkte), duplizieren und entfernen. Neue Einträge
   übernehmen Einrückung und Trennzeichen ihrer Nachbarn.
   Farben: Werte unter Schlüsseln wie „color“ werden – wenn sie ein Hex-Wert sind – als Farbe angezeigt und lassen
   sich per Farbwähler ändern (Schreibweise wie vorher, z. B. #CC0000, 0xFFCC0000, cc0000). */
"use strict";

// ====================================================================== Farben
const COLOR_KEY_RE = /colou?r|farbe/i;
/** Hex-Farbe erkennen: #RGB, #RRGGBB, #AARRGGBB/#RRGGBBAA, 0x…, ohne Präfix (nur 6/8 Stellen). */
function colorInfo(value) {
  const s = String(value ?? "").trim();
  const m = /^(#|0x|0X)?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.exec(s);
  if (!m || (!m[1] && m[2].length === 3)) return null;
  let h = m[2];
  const upper = h === h.toUpperCase() && /[A-F]/.test(h);
  let alpha = "", alphaPos = "";
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (h.length === 8) {            // 0xAARRGGBB (Serato, Windows) bzw. #RRGGBBAA (CSS)
    if (m[1] === "#") { alpha = h.slice(6); alphaPos = "end"; h = h.slice(0, 6); } else { alpha = h.slice(0, 2); alphaPos = "start"; h = h.slice(2); }
  }
  return { hex: "#" + h.toLowerCase(), prefix: m[1] || "", upper, short: m[2].length === 3, alpha, alphaPos, raw: s };
}
/** Neue Farbe (#rrggbb) in der Schreibweise des alten Werts. */
function colorFormat(info, hex) {
  let h = hex.replace("#", "");
  if (info.short && h[0] === h[1] && h[2] === h[3] && h[4] === h[5]) h = h[0] + h[2] + h[4];
  if (info.alphaPos === "start") h = info.alpha + h;
  if (info.alphaPos === "end") h = h + info.alpha;
  return info.prefix + (info.upper ? h.toUpperCase() : h.toLowerCase());
}
/** Farbfeld-HTML (für Listen). */
function colorSwatch(value) {
  const c = colorInfo(value);
  return c ? `<span class="swatch" style="background:${c.hex}" title="${c.hex}"></span>` : "";
}

// ====================================================================== Parser mit Positionen
/** JSON parsen → Knoten {type, start, end, raw, kids:[{key, node, s, e}]} (s/e: Eintrag inkl. Schlüssel). */
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
    if (c === "{" || c === "[") {
      const obj = c === "{", close = obj ? "}" : "]";
      const s = i++; const kids = [];
      ws();
      if (text[i] === close) { i++; return { type: obj ? "object" : "array", start: s, end: i, kids }; }
      for (;;) {
        ws();
        let key = kids.length, ks = i;
        if (obj) {
          if (text[i] !== '"') fail("Schlüssel erwartet");
          key = JSON.parse(str().raw);
          ws();
          if (text[i] !== ":") fail("„:“ erwartet");
          i++;
        }
        const node = val();
        kids.push({ key, node, s: ks, e: node.end });
        ws();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === close) { i++; return { type: obj ? "object" : "array", start: s, end: i, kids }; }
        fail(`„,“ oder „${close}“ erwartet`);
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

// ====================================================================== Strukturänderungen (Expertenmodus)
/** Leerraum/Trenner zwischen zwei Geschwistern bzw. nach der öffnenden Klammer. */
function _sep(text, parent) {
  const k = parent.kids;
  if (k.length >= 2) return text.slice(k[k.length - 2].e, k[k.length - 1].s);          // z. B. ",\n    "
  if (k.length === 1) return "," + text.slice(parent.start + 1, k[0].s);                // gleiche Einrückung
  return "";
}
function _colon(text, parent) {
  for (const k of parent.kids) {
    const seg = text.slice(k.s, k.node.start);
    const m = /"\s*(:\s*)$/.exec(seg);
    if (m) return m[1];
  }
  return ": ";
}
/** Neuen Eintrag (Rohtext) am Ende von parent einfügen. */
function jsonAppend(text, parent, entryRaw) {
  const k = parent.kids;
  if (!k.length) {
    const inner = text.slice(parent.start + 1, parent.end - 1);
    return text.slice(0, parent.start + 1) + (inner.trim() ? inner : "") + entryRaw + text.slice(parent.end - 1);
  }
  const last = k[k.length - 1];
  return text.slice(0, last.e) + _sep(text, parent) + entryRaw + text.slice(last.e);
}
/** Eintrag direkt nach kid einfügen (Duplizieren). */
function jsonInsertAfter(text, parent, kid, entryRaw) {
  const sep = _sep(text, parent) || ", ";
  return text.slice(0, kid.e) + sep + entryRaw + text.slice(kid.e);
}
/** Eintrag entfernen (samt Trenner). */
function jsonRemove(text, parent, idx) {
  const k = parent.kids;
  if (k.length === 1) return text.slice(0, parent.start + 1) + text.slice(parent.end - 1).replace(/^\s*/, "") ;
  if (idx < k.length - 1) return text.slice(0, k[idx].s) + text.slice(k[idx + 1].s);
  return text.slice(0, k[idx - 1].e) + text.slice(k[idx].e);
}
/** Kopie eines Werts mit Einrückung an neuer Stelle (gleiche Ebene → Rohtext unverändert). */
function _cloneRaw(text, kid) { return text.slice(kid.s, kid.e); }

/** Leerer Wert eines Typs. */
const JSON_NEW = { string: '""', number: "0", bool: "false", null: "null", object: "{}", array: "[]" };

// ====================================================================== Baum-Editor
/** Baum-Editor in box. onChange() bei jeder Änderung. opts.expert: Struktur änderbar.
    Rückgabe: {text(), valid(), changed(), expandAll(open), setExpert(on)}. */
function jsonTreeEditor(box, text, onChange, opts = {}) {
  let base = text;                 // Text, auf den sich die Positionen beziehen
  let expert = !!opts.expert;
  let scan, edits, bad, asciiOnly;
  const closed = new Set();        // zugeklappte Pfade (bleiben beim Neuzeichnen erhalten)

  const current = () => {
    let out = base;
    [...edits.entries()].sort((a, b) => b[0].start - a[0].start).forEach(([nd, raw]) => {
      out = out.slice(0, nd.start) + raw + out.slice(nd.end);
    });
    return out;
  };
  const encStr = (s) => {
    let j = JSON.stringify(s);
    if (asciiOnly) j = j.replace(/[\u007f-￿]/g, (ch) => "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0"));
    return j;
  };
  const set = (node, raw) => {
    if (raw === node.raw) edits.delete(node); else edits.set(node, raw);
    onChange();
  };
  // Strukturänderung: aktuelle Werte übernehmen, Text umbauen, neu zeichnen
  const restructure = (fn) => {
    if (bad.size) { if (typeof toast === "function") toast("Erst die rot markierten Zahlen korrigieren."); return; }
    const t = current();
    const sc = jsonScan(t);
    if (!sc.ok) return;
    const out = fn(t, sc.root);
    if (out == null) return;
    build(out);
    onChange();
  };
  const findByPath = (root, path) => {
    let nd = root;
    for (const p of path) { const k = nd.kids.find((x) => x.key === p); if (!k) return null; nd = k.node; }
    return nd;
  };

  const leaf = (node, key, path) => {
    const label = String(key ?? "Wert");
    const wrap = jel("span", "jleaf");
    if (node.type === "string") {
      const inp = jin(JSON.parse(node.raw), "av", label);
      wrap.appendChild(inp);
      if (COLOR_KEY_RE.test(String(key ?? ""))) addColor(wrap, inp, (v) => set(node, encStr(v)));
      inp.addEventListener("input", () => { set(node, encStr(inp.value)); jgrow(inp); syncColor(wrap, inp.value); });
      return wrap;
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
      wrap.appendChild(inp);
      return wrap;
    }
    if (node.type === "bool") {
      const lab = jel("label", "jbool");
      const cb = document.createElement("input");
      cb.type = "checkbox"; cb.checked = node.raw === "true"; cb.setAttribute("aria-label", label);
      const t = jel("span", "", node.raw);
      cb.addEventListener("change", () => { t.textContent = String(cb.checked); set(node, String(cb.checked)); });
      lab.append(cb, t);
      wrap.appendChild(lab);
      return wrap;
    }
    wrap.appendChild(jel("span", "jnull", "null"));
    return wrap;
  };

  const xbtn = (cls, title, sym, fn) => {
    const b = jel("button", "jx " + cls, sym);
    b.type = "button"; b.title = title; b.setAttribute("aria-label", title);
    b.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
    return b;
  };

  const render = (key, node, depth, path, parentPath, idx) => {
    const pkey = JSON.stringify(path);
    const wrap = jel("div", "xn" + (depth ? "" : " root") + (closed.has(pkey) ? " closed" : ""));
    const row = jel("div", "xr");
    const branch = node.type === "object" || node.type === "array";
    const tw = jel("button", "tw" + (branch && node.kids.length ? "" : " leaf"));
    tw.type = "button";
    tw.innerHTML = '<svg class="i" viewBox="0 0 24 24" style="width:14px;height:14px"><path d="m6 9 6 6 6-6"/></svg>';
    tw.setAttribute("aria-label", "auf-/zuklappen");
    tw.addEventListener("click", () => { wrap.classList.toggle("closed"); wrap.classList.contains("closed") ? closed.add(pkey) : closed.delete(pkey); });
    row.appendChild(tw);
    if (key !== null) {
      row.appendChild(jel("span", typeof key === "number" ? "jidx" : "an", typeof key === "number" ? `[${key}]` : key));
      row.appendChild(jel("span", "eq", ":"));
    }
    if (branch) {
      row.appendChild(jel("span", "tg", node.type === "object" ? "{" : "["));
      row.appendChild(jel("span", "xc", `${node.kids.length} ${node.type === "object" ? "Einträge" : "Elemente"} …`));
    } else {
      row.appendChild(leaf(node, key, path));
    }
    if (expert && parentPath) {     // Eintrag duplizieren / entfernen
      const tools = jel("span", "jtools");
      tools.appendChild(xbtn("dup", "Duplizieren (Kopie direkt darunter)", "⧉", () => restructure((t, root) => {
        const par = findByPath(root, parentPath);
        return jsonInsertAfter(t, par, par.kids[idx], _cloneRaw(t, par.kids[idx]).replace(/^"(?:[^"\\]|\\.)*"(\s*:)/, (m0, c) => (typeof key === "string" ? encStr(uniqueKey(par, key)) + c : m0)));
      })));
      tools.appendChild(xbtn("del", "Entfernen", "✕", () => restructure((t, root) => jsonRemove(t, findByPath(root, parentPath), idx))));
      row.appendChild(tools);
    }
    wrap.appendChild(row);
    if (branch) {
      const kids = jel("div", "xk");
      node.kids.forEach((k, j) => kids.appendChild(render(k.key, k.node, depth + 1, [...path, k.key], path, j)));
      if (expert) kids.appendChild(addRow(node, path));
      wrap.appendChild(kids);
      const close = jel("div", "xr jclose");
      close.appendChild(jel("span", "tg", node.type === "object" ? "}" : "]"));
      wrap.appendChild(close);
    }
    return wrap;
  };

  const uniqueKey = (obj, k) => {
    const names = new Set(obj.kids.map((x) => x.key));
    if (!names.has(k)) return k;
    let n = 2; while (names.has(`${k}_${n}`)) n++;
    return `${k}_${n}`;
  };

  // „+“-Zeile: Liste → neues Element (Kopie des letzten oder leerer Wert); Objekt → neuer Schlüssel mit Typ
  const addRow = (node, path) => {
    const row = jel("div", "xr jadd");
    if (node.type === "array") {
      if (node.kids.length) {
        row.appendChild(xbtn("add", "Neues Element als Kopie des letzten (z. B. neuer Cue-Punkt)", "+ Element (Kopie des letzten)", () => restructure((t, root) => {
          const par = findByPath(root, path);
          return jsonAppend(t, par, _cloneRaw(t, par.kids[par.kids.length - 1]));
        })));
      }
      const sel = typeSelect();
      row.appendChild(sel);
      row.appendChild(xbtn("add", "Neues leeres Element dieses Typs", "+ leeres Element", () => restructure((t, root) =>
        jsonAppend(t, findByPath(root, path), JSON_NEW[sel.value]))));
    } else {
      const name = jel("input", "xin jkey");
      name.placeholder = "neuer Schlüssel"; name.size = 14; name.spellcheck = false;
      const sel = typeSelect();
      row.append(name, sel, xbtn("add", "Schlüssel hinzufügen", "+ Schlüssel", () => {
        const k = name.value.trim();
        if (!k) { name.focus(); return; }
        restructure((t, root) => {
          const par = findByPath(root, path);
          if (par.kids.some((x) => x.key === k)) { if (typeof toast === "function") toast(`„${k}“ gibt es schon.`); return null; }
          return jsonAppend(t, par, encStr(k) + _colon(t, par) + JSON_NEW[sel.value]);
        });
      }));
    }
    return row;
  };
  const typeSelect = () => {
    const sel = jel("select", "jtype");
    [["string", "Text"], ["number", "Zahl"], ["bool", "Ja/Nein"], ["object", "Objekt { }"], ["array", "Liste [ ]"], ["null", "null"]]
      .forEach(([v, l]) => { const o = jel("option", "", l); o.value = v; sel.appendChild(o); });
    sel.setAttribute("aria-label", "Typ");
    return sel;
  };

  const build = (t) => {
    base = t;
    scan = jsonScan(t);
    edits = new Map();
    bad = new Set();
    asciiOnly = /\\u00[89a-f][0-9a-f]|\\u0[1-9a-f][0-9a-f]{2}|\\u[1-9a-f][0-9a-f]{3}/i.test(t);
    box.innerHTML = "";
    box.classList.add("json-tree");
    box.classList.toggle("expert", expert);
    if (!scan.ok) {
      box.appendChild(jel("div", "xml-msg", "Kein gültiges JSON – bitte in der Textansicht korrigieren. " + scan.error));
      return;
    }
    box.appendChild(render(null, scan.root, 0, [], null, 0));
  };
  build(text);

  return {
    text: () => (scan.ok ? current() : base),
    valid: () => scan.ok && bad.size === 0,
    changed: () => current() !== text,
    expandAll: (open) => box.querySelectorAll(".xn").forEach((x) => x.classList.toggle("closed", !open)),
    setExpert: (on) => { if (bad.size) return false; expert = !!on; build(current()); return true; },
  };
}

// ---------------------------------------------------------------------- Farbwähler neben einem Eingabefeld
function addColor(wrap, inp, onPick) {
  const c = colorInfo(inp.value);
  const pick = document.createElement("input");
  pick.type = "color"; pick.className = "jcolor"; pick.title = "Farbe wählen";
  pick.hidden = !c;
  if (c) pick.value = c.hex;
  pick.addEventListener("input", () => {
    const cur = colorInfo(inp.value);
    if (!cur) return;
    inp.value = colorFormat(cur, pick.value);
    jgrow(inp);
    onPick(inp.value);
  });
  wrap.insertBefore(pick, inp);
}
function syncColor(wrap, value) {
  const pick = wrap.querySelector(".jcolor");
  if (!pick) return;
  const c = colorInfo(value);
  pick.hidden = !c;
  if (c) pick.value = c.hex;
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
