/* Einheitliche TagStudio-Hover-Infos (#72, #192): Hauptfenster und abgedockter Player.
 * Es gibt nur EINE sichtbare Art von Tooltip – die von TagStudio. Ein title-Attribut (auch dynamisch gesetzt)
 * wird sofort in data-tip-title verschoben, SVG-<title>-Elemente ebenso; der Browser zeigt keinen eigenen Tooltip.
 * Für Screenreader bleibt bei Symbol-Knöpfen nur ein unsichtbares aria-label (kein zweiter Tooltip).
 */
"use strict";
const TIP = {el:null, target:null, timer:0, observer:null};

function tipHtml(el) {
  if (el.dataset.tipHtml) return el.dataset.tipHtml;
  const text = el.dataset.tipTitle || "";
  if (!text.trim()) return "";
  const lines = text.split("\n").filter((l,k,all)=>l.trim() || (k && k<all.length-1));
  const head = lines.length > 1 ? `<div class="tip-h">${esc(lines.shift())}</div>` : "";
  const rows = lines.map((l)=>{
    const m = l.match(/^\s*([^:]{1,32}):\s+(.+)$/);
    const val = (s) => esc(s)
      .replace(/\b(0?([1-9]|1[0-2])[AB])\b/g, (k)=>
        typeof keyStyle === "function" ? `<b class="tip-key" style="${keyStyle(k.replace(/^0/,""))}">${k}</b>` : k)
      .replace(/(\d+(?:[.,]\d+)?\s?BPM)/g,'<b class="tip-bpm">$1</b>')
      .replace(/(unterscheidet sich[^·]*|geändert|fehlt|NICHT[^·]*)/g,'<span class="tip-warn">$1</span>');
    return m ? `<div class="tip-r"><span class="tip-k">${esc(m[1])}</span><span class="tip-v">${val(m[2])}</span></div>`
      : `<div class="tip-l">${val(l)}</div>`;
  }).join("");
  return head + rows;
}

/** Native title in zugängliche, kontrollierte Tooltip-Daten migrieren. */
function tipNormalize(el) {
  if (!el || el.nodeType !== 1 || !el.hasAttribute("title")) return;
  const text = el.getAttribute("title");
  if (text && el.matches("button") && !el.hasAttribute("aria-label") && !el.textContent.trim()) {
    el.setAttribute("aria-label", text); // Icon-Button für Screenreader erhalten
  }
  if (text) el.dataset.tipTitle = text;       // neu gesetzte Titel überschreiben alte Inhalte
  else delete el.dataset.tipTitle;
  el.removeAttribute("title");                // Browser-Tooltip auch nach mehreren Sekunden verhindern
  if (TIP.target === el && TIP.el && !TIP.el.hidden) tipShow(el);
}
/** SVG-<title> erzeugt ebenfalls einen Browser-Tooltip → in data-tip-title des Elternelements übernehmen. */
function tipSvgTitle(el) {
  const host = el.parentNode;
  if (host && host.nodeType === 1 && !host.dataset.tipTitle && el.textContent.trim()) host.dataset.tipTitle = el.textContent.trim();
  el.remove();
}
function tipNormalizeTree(node) {
  if (!node || node.nodeType !== 1) return;
  if (node.namespaceURI === "http://www.w3.org/2000/svg" && node.localName === "title") { tipSvgTitle(node); return; }
  tipNormalize(node);
  if (node.querySelectorAll) {
    node.querySelectorAll("[title]").forEach(tipNormalize);
    node.querySelectorAll("svg title").forEach(tipSvgTitle);
  }
}
function tipShow(el) {
  if (!TIP.el || !el || !el.isConnected) return;
  const html = tipHtml(el);
  if (!html) { TIP.el.hidden = true; return; }
  const t = TIP.el;
  t.innerHTML = html; t.hidden = false;
  const r = el.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight;
  let x = r.left + r.width / 2 - w / 2, y = r.bottom + 8;
  if (y + h > innerHeight - 8) y = r.top - h - 8;
  t.style.left = Math.max(8, Math.min(innerWidth - w - 8, x)) + "px";
  t.style.top = Math.max(8, Math.min(innerHeight - h - 8, y)) + "px";
}
function tipHide() {
  clearTimeout(TIP.timer);
  if (TIP.el) TIP.el.hidden = true;
  TIP.target = null;
}
function tipActivate(el) {
  if (el) tipNormalize(el);
  if (el === TIP.target) return;
  tipHide();
  if (!el || !tipHtml(el)) return;
  TIP.target = el;
  TIP.timer = setTimeout(() => {
    if (TIP.target === el && el.isConnected) tipShow(el);
  }, 380);
}
function initTips() {
  if (TIP.el) return;                           // idempotent bei erneutem Initialisieren
  TIP.el = document.createElement("div");
  TIP.el.className = "tip"; TIP.el.hidden = true; TIP.el.setAttribute("role","tooltip");
  document.body.appendChild(TIP.el);
  tipNormalizeTree(document.body);
  TIP.observer = new MutationObserver((records) => {
    for (const rec of records) {
      if (rec.type === "attributes") tipNormalize(rec.target);
      else for (const node of rec.addedNodes) tipNormalizeTree(node);
    }
    if (TIP.target && !TIP.target.isConnected) tipHide();
  });
  TIP.observer.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:["title"]});
  const fromEvent = (event) => event.target.closest &&
    event.target.closest("[data-tip-title],[data-tip-html],[title]");
  document.addEventListener("mouseover", (event) => tipActivate(fromEvent(event)));
  document.addEventListener("mouseout", (event) => {
    const t = TIP.target;
    if (t && (event.target === t || t.contains(event.target)) &&
        (!event.relatedTarget || !t.contains(event.relatedTarget))) tipHide();
  });
  document.addEventListener("focusin", (event) => tipActivate(fromEvent(event)));
  document.addEventListener("focusout", (event) => {
    if (TIP.target && (event.target === TIP.target || TIP.target.contains(event.target))) tipHide();
  });
  ["mousedown","keydown","scroll","blur"].forEach(event =>
    window.addEventListener(event,tipHide,true));
  document.addEventListener("mouseleave",tipHide);
}
