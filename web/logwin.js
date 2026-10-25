/* MarKusSXCH TagStudio – Live-Protokoll eines Plugins in eigenem Fenster (#293). Liest die Protokolldatei im Log-Ordner
   fortlaufend (nur neue Bytes) und zeigt zusätzlich die Zeilen laufender Vorgänge, bevor sie in die Datei geschrieben
   werden (markiert „läuft“). Nur lesen – am Protokoll wird nichts geändert. */
"use strict";

const LW_HASH = new URLSearchParams(location.hash.slice(1));
const TOKEN = LW_HASH.get("token") || "";
const pywebviewReady = new Promise((resolve) => {
  if (TOKEN) return resolve(false);
  if (window.pywebview && window.pywebview.api) return resolve(true);
  window.addEventListener("pywebviewready", () => resolve(true));
});
async function call(name, ...args) {
  if (await pywebviewReady) return window.pywebview.api[name](...args);
  const res = await fetch("/api/" + name, { method: "POST", headers: { "Content-Type": "application/json", "X-Token": TOKEN }, body: JSON.stringify(args) });
  const j = await res.json();
  if (!j.ok) throw new Error(j.error || "Fehler");
  return j.result;
}
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const LW = { pid: "", name: "", offset: -1, seq: 0, text: "", live: [], mtime: 0, timer: 0, busy: false, max: 2000000 };

function lwTime(t) { const d = new Date(t * 1000); return d.toLocaleTimeString(); }

function lwRender() {
  const q = ($("#lwFind").value || "").toLowerCase().trim();
  const keep = (ln) => !q || ln.toLowerCase().includes(q);
  const lines = LW.text.split("\n").filter(keep);
  const live = LW.live.filter((e) => keep(e[2]));
  const el = $("#lwLog"), atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
  el.innerHTML = esc(lines.join("\n")).replace(/^(=====.*=====)$/gm, '<b class="lw-head">$1</b>')
    + (live.length ? `\n<span class="lw-live">${live.map((e) => `<span class="lw-t">${esc(lwTime(e[1]))} läuft</span> ${esc(e[2])}`).join("\n")}</span>` : "");
  if ($("#lwFollow").checked && (atEnd || LW.first)) el.scrollTop = el.scrollHeight;
  LW.first = false;
}

async function lwTick() {
  if (LW.busy || !LW.pid || $("#lwPause").checked) return;
  LW.busy = true;
  try {
    const r = await call("plugin_log_read", LW.pid, LW.name, LW.offset, LW.seq);
    if (r.name !== LW.name || r.reset) { LW.text = ""; LW.first = true; }
    LW.name = r.name;
    if (r.text) LW.text += r.text;
    if (LW.text.length > LW.max) LW.text = LW.text.slice(LW.text.length - LW.max);
    LW.offset = r.size;
    LW.seq = r.seq;
    LW.mtime = r.mtime;
    LW.live = LW.live.concat(r.live).filter((e) => r.name !== `${LW.pid}.log` || e[1] > r.mtime);
    const sel = $("#lwFile"), files = r.files.length ? r.files : [`${LW.pid}.log`];
    if (sel.options.length !== files.length || [...sel.options].some((o, i) => o.value !== files[i])) {
      sel.innerHTML = files.map((f) => `<option value="${esc(f)}">${esc(f)}</option>`).join("");
    }
    sel.value = LW.name || files[0];
    document.title = `${r.title} – Protokoll`;
    $("#lwTitle").textContent = r.title;
    $("#lwInfo").textContent = r.name ? `${r.dir} · ${r.name} · ${(r.size / 1024).toFixed(1)} KB · aktualisiert ${new Date().toLocaleTimeString()}`
      : `${r.dir} · noch kein Protokoll – es erscheint hier, sobald das Plugin etwas schreibt.`;
    if (r.text || r.reset || r.live.length || LW.first) lwRender();
  } catch (e) {
    $("#lwInfo").textContent = "Protokoll nicht lesbar: " + (e.message || e);
  } finally { LW.busy = false; }
}

function lwStart(pid) {
  if (LW.pid === pid) return;
  Object.assign(LW, { pid, name: "", offset: -1, seq: 0, text: "", live: [], first: true });
  clearInterval(LW.timer);
  lwTick();
  LW.timer = setInterval(lwTick, 1000);
}

(function bindLog() {
  $("#lwFile").addEventListener("change", (e) => { LW.name = e.target.value; LW.offset = -1; LW.text = ""; LW.first = true; lwTick(); });
  $("#lwFind").addEventListener("input", lwRender);
  $("#lwPause").addEventListener("change", lwTick);
  $("#lwCopy").addEventListener("click", () => navigator.clipboard.writeText($("#lwLog").innerText).catch(() => {}));
  $("#lwFolder").addEventListener("click", () => call("plugin_log_folder", LW.pid).catch(() => {}));
  if (LW_HASH.get("pid")) lwStart(LW_HASH.get("pid"));
})();
