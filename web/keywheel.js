/* MarKusSXCH TagStudio – Camelot-Rad für die Tonart (Tagger).
   Aussen Dur (B), innen Moll (A). Klick setzt die Tonart der markierten Dateien; passende Tonarten
   (±1 und Paralleltonart) werden hervorgehoben. Nutzt Funktionen aus app.js / tagger.js. */
"use strict";

const KW = { open: false, anchor: null };

function keyInfo(code) {
  const w = (TG.settings && TG.settings.keys && TG.settings.keys.wheel) || [];
  const r = w.find((x) => x[0] === code);
  return r ? { code, musical: r[1], openkey: r[2] } : null;
}
function keyParts(code) { return code ? { n: parseInt(code, 10), minor: code.endsWith("A") } : null; }
function keyCompat(code) {
  const p = keyParts(code); if (!p) return [];
  const L = p.minor ? "A" : "B";
  return [code, (p.n % 12 + 1) + L, ((p.n + 10) % 12 + 1) + L, p.n + (p.minor ? "B" : "A")];
}
function keySortValue(code) { const p = keyParts(code); return p ? p.n * 2 - (p.minor ? 1 : 0) : 999; }
/* Farbe je Zahl: einmal rundherum durch den Farbkreis, Nachbarn haben ähnliche Farben. */
function keyHue(n) { return (180 - (n - 1) * 30 + 720) % 360; }
function keyColor(code) { const p = keyParts(code); return p ? `hsl(${keyHue(p.n)} ${p.minor ? "58% 56%" : "62% 46%"})` : ""; }
function keyText(code) { const p = keyParts(code); const h = p ? keyHue(p.n) : 0; return h >= 35 && h <= 195 ? "#15181F" : "#FFFFFF"; }
function keyStyle(code) { return `--kc:${keyColor(code)};--kt:${keyText(code)}`; }
function keyBadge(code, cls = "") {
  return code ? `<span class="kb ${cls}" style="${keyStyle(code)}">${code}</span>` : "";
}

function wheelSvg(cur) {
  const C = 160, R = [152, 108, 66];     // aussen, Grenze Dur/Moll, innen
  const ok = new Set(keyCompat(cur));
  const pt = (r, deg) => { const a = (deg - 90) * Math.PI / 180; return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
  const seg = (r1, r2, a1, a2) => {
    const [x1, y1] = pt(r2, a1), [x2, y2] = pt(r2, a2), [x3, y3] = pt(r1, a2), [x4, y4] = pt(r1, a1);
    return `M${x1.toFixed(2)} ${y1.toFixed(2)}A${r2} ${r2} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}L${x3.toFixed(2)} ${y3.toFixed(2)}A${r1} ${r1} 0 0 0 ${x4.toFixed(2)} ${y4.toFixed(2)}Z`;
  };
  let g = "";
  for (let n = 1; n <= 12; n++) {
    const mid = (n % 12) * 30, a1 = mid - 15 + 0.6, a2 = mid + 15 - 0.6;
    for (const minor of [false, true]) {
      const code = n + (minor ? "A" : "B"), info = keyInfo(code) || { musical: "" };
      const [r1, r2] = minor ? [R[2], R[1] - 1] : [R[1] + 1, R[0]];
      const [tx, ty] = pt((r1 + r2) / 2, mid);
      const st = !cur ? "" : code === cur ? " cur" : ok.has(code) ? " ok" : " dim";
      g += `<g class="kseg${st}" style="${keyStyle(code)}" data-code="${code}" tabindex="0" role="button" aria-label="${code} ${esc(info.musical)}">
        <path d="${seg(r1, r2, a1, a2)}"/>
        <text x="${tx.toFixed(1)}" y="${(ty - 3).toFixed(1)}" class="t1">${code}</text>
        <text x="${tx.toFixed(1)}" y="${(ty + 11).toFixed(1)}" class="t2">${esc(info.musical)}</text></g>`;
    }
  }
  const ci = cur && keyInfo(cur);
  const centre = ci
    ? `<text x="${C}" y="${C - 4}" class="cc">${cur}</text><text x="${C}" y="${C + 18}" class="cm">${esc(ci.musical)} · ${esc(ci.openkey)}</text>`
    : `<text x="${C}" y="${C + 5}" class="cm">${TG.detail && TG.detail.common.TKEY.mixed ? "verschieden" : "keine Tonart"}</text>`;
  return `<svg viewBox="0 0 320 320" class="kwheel" aria-label="Camelot-Rad">${g}
    <circle cx="${C}" cy="${C}" r="${R[2] - 4}" class="kcen"/>${centre}</svg>`;
}

function keyWheelRender() {
  const pop = $("#keyPop"); if (!pop || !KW.open || !TG.detail || !TG.detail.count) { keyWheelClose(); return; }
  const k = TG.detail.common.TKEY, cur = k.camelot || null, set = TG.settings.keys;
  const raw = !k.mixed && k.value && !cur ? `<div class="hint st-missing">„${esc(k.value)}“ ist keine erkannte Tonart.</div>` : "";
  const near = cur ? keyCompat(cur).slice(1).map((c) => `${keyBadge(c)} <span class="muted sm">${esc(keyInfo(c).musical)}</span>`).join(" ") : "";
  pop.innerHTML = `<div class="kp-head"><b>Tonart</b><span class="muted sm">${TG.detail.count > 1 ? TG.detail.count + " Dateien" : ""}</span>
      <button class="kp-x" data-kw="close" title="Schließen" aria-label="Schließen"><svg class="i" viewBox="0 0 24 24"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button></div>
    ${wheelSvg(cur)}${raw}
    <div class="kp-near">${cur ? `<span class="muted sm">Passt zu</span> ${near}` : '<span class="muted sm">Klick auf ein Feld setzt die Tonart. Aussen Dur, innen Moll.</span>'}</div>
    <div class="kp-row"><span class="muted sm">Schreiben als</span><div class="kn-seg">${set.notations.map(([v, l]) => `<button data-kn="${v}" class="${set.notation === v ? "on" : ""}" title="${esc(l)}">${esc(l.replace(/\s*\(.*/, ""))}</button>`).join("")}</div></div>
    <div class="kp-row"><button class="ghost sm" data-kw="convert">Schreibweise vereinheitlichen …</button><button class="ghost sm" data-kw="clear" ${!k.value && !k.mixed ? "disabled" : ""}>Tonart entfernen</button></div>`;
  keyWheelPlace();
}

function keyWheelPlace() {
  const pop = $("#keyPop"), a = $("#tgKeyBtn");
  if (!pop || pop.hidden) return;
  const r = (a || $("#tgEdit")).getBoundingClientRect(), ed = $("#tgEdit").getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let x = ed.left - w - 12, y = r.top + r.height / 2 - h / 2;   // links neben dem Bearbeitungsbereich
  if (x < 8) x = Math.min(innerWidth - w - 8, r.left);
  y = clamp(y, 8, innerHeight - h - 8);
  pop.style.left = x + "px"; pop.style.top = y + "px";
}

function keyWheelOpen() {
  let pop = $("#keyPop");
  if (!pop) { pop = document.createElement("div"); pop.id = "keyPop"; pop.className = "keypop"; document.body.appendChild(pop); keyWheelBind(pop); }
  if (KW.open) { keyWheelClose(); return; }
  KW.open = true; pop.hidden = false;
  keyWheelRender();
}
function keyWheelClose() { KW.open = false; const p = $("#keyPop"); if (p) p.hidden = true; }
function keyWheelSync() { if (KW.open) keyWheelRender(); }

async function keyWheelSet(code) {
  const d = taggerApplyDetail(await call("tag_key_set", tgSelected(), code));
  if (d) keyWheelRender();
}

async function keyConvertDialog() {
  const idx = tgSelected(), set = TG.settings.keys;
  await toolDialog({
    title: `Tonart-Schreibweise (${idx.length} Datei(en))`,
    form: `<div class="radios">${set.notations.map(([v, l]) => `<label><input type="radio" name="kn" value="${v}" ${set.notation === v ? "checked" : ""}> ${esc(l)}</label>`).join("")}</div>
      <div class="hint">Erkannt werden u. a. 8A, 1m, Am, A minor, F#m, D♭, a-Moll, Es-Dur.</div>`,
    columns: CHG_COLS,
    preview: async (b) => {
      const r = await call("tag_key_convert", idx, b.querySelector('input[name="kn"]:checked').value, false);
      r.summary = `${fmtN(r.count)} Datei(en) werden umgeschrieben.` + (r.unknown_count ? ` ${fmtN(r.unknown_count)} Wert(e) nicht erkannt: ${r.unknown.slice(0, 5).map((u) => "„" + u.value + "“").join(", ")}${r.unknown_count > 5 ? " …" : ""}` : "");
      return r;
    },
    apply: async (b) => {
      const n = b.querySelector('input[name="kn"]:checked').value;
      set.notation = await call("tag_key_notation", n);
      return call("tag_key_convert", idx, n, true);
    },
  });
  keyWheelSync();
}

function keyWheelBind(pop) {
  pop.addEventListener("click", async (e) => {
    const s = e.target.closest(".kseg"); if (s) { keyWheelSet(s.dataset.code); return; }
    const n = e.target.closest("[data-kn]");
    if (n) { TG.settings.keys.notation = await call("tag_key_notation", n.dataset.kn); keyWheelRender(); return; }
    const b = e.target.closest("[data-kw]"); if (!b) return;
    if (b.dataset.kw === "close") keyWheelClose();
    else if (b.dataset.kw === "clear") keyWheelSet("");
    else if (b.dataset.kw === "convert") { keyWheelClose(); keyConvertDialog(); }
  });
  pop.addEventListener("keydown", (e) => {
    const s = e.target.closest(".kseg");
    if (s && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); keyWheelSet(s.dataset.code); }
  });
  document.addEventListener("keydown", (e) => { if (KW.open && e.key === "Escape" && $("#modal").hidden) { e.stopPropagation(); keyWheelClose(); } }, true);
  document.addEventListener("mousedown", (e) => {
    if (KW.open && !pop.contains(e.target) && !e.target.closest(".tg-body") && $("#modal").hidden) keyWheelClose();
  });
  addEventListener("resize", keyWheelPlace);
}
