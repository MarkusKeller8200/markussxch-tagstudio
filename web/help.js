/* MarKusSXCH TagStudio – Hilfe (#158): Tag-Übersicht mit aufklappbaren Kapiteln, Herkunft und Zählern aus dem
   Bibliotheks-Scan (Klick filtert im Tagger), Handbuch (README), ID3-Felder und Plugins als Markdown. */
"use strict";

const HELP = { tab: "tags", data: null, docs: null, open: new Set(["ident", "custom"]), q: "", dj: false };

async function helpShow() {
  helpTab(HELP.tab);
}

async function helpTab(tab) {
  HELP.tab = tab;
  $$("#helpTabs [data-htab]").forEach((b) => { b.classList.toggle("on", b.dataset.htab === tab); b.setAttribute("aria-selected", String(b.dataset.htab === tab)); });
  $("#helpTags").hidden = tab !== "tags";
  $("#helpDoc").hidden = tab === "tags";
  if (tab === "tags") return helpLoadTags();
  if (!HELP.docs) HELP.docs = await call("help_docs");
  const d = HELP.docs[tab];
  $("#helpDoc").innerHTML = d && d.text ? mdToHtml(d.text) : '<div class="tg-empty">Dokument nicht gefunden.</div>';
  $("#helpDoc").scrollTop = 0;
}

async function helpLoadTags(root) {
  try { HELP.data = await call("help_tags", root || $("#helpRoot").value || null); } catch (e) { toast(String(e.message || e)); return; }
  const d = HELP.data;
  $("#helpRoot").innerHTML = d.roots.length
    ? d.roots.map((r) => `<option value="${esc(r.path)}" ${r.path === d.root ? "selected" : ""}>${esc(r.path)} – ${esc(r.label)}${r.cached ? " ✓" : ""}</option>`).join("")
    : '<option value="">(kein Ordner – Standardordner des Taggers oder Snapshot-Bibliothek festlegen)</option>';
  const s = d.scan;
  $("#helpScanInfo").textContent = s ? `${fmtN(s.files)} Titel, ${fmtN(s.keys)} verschiedene Felder · gescannt ${s.scanned.replace("T", " ").slice(0, 16)}` : "noch nicht gescannt";
  helpRender();
}

function helpRowMatch(r) {
  if (HELP.dj && !r.dj) return false;
  const q = HELP.q.trim().toLowerCase();
  if (!q) return true;
  return [r.key, r.name, r.label, r.meaning, r.help, r.param, r.where].some((v) => (v || "").toLowerCase().includes(q))
    || (r.src && (srcInfo(r.src)?.name || r.src).toLowerCase().includes(q));
}

/** „Ohne“: Titel der gescannten Bibliothek, die das Feld nicht haben → Klick filtert im Tagger auf „fehlt“ */
function helpMissing(r) {
  const total = HELP.data && HELP.data.scan ? HELP.data.scan.files : 0;
  if (r.count === null || r.count === undefined || !total) return '<span class="muted">–</span>';
  const n = Math.max(0, total - r.count);
  if (!n) return '<span class="muted">0</span>';
  return `<button class="help-n miss" data-filter="${esc(r.key)}" data-mode="miss" data-label="${esc(r.name || r.key)}" title="Im Tagger die Titel ohne dieses Feld zeigen – zum Vervollständigen">${fmtN(n)}</button>`;
}

function helpCount(r) {
  if (r.count === null || r.count === undefined) return '<span class="muted">–</span>';
  if (!r.count) return '<span class="muted">0</span>';
  return `<button class="help-n" data-filter="${esc(r.key)}" data-label="${esc(r.name || r.key)}" title="Im Tagger die Titel mit diesem Feld zeigen">${fmtN(r.count)}</button>`;
}

function helpRender() {
  const d = HELP.data;
  if (!d) return;
  const total = d.scan ? d.scan.files : 0;
  const sw = `<details class="help-ch" data-ch="software" ${HELP.open.has("software") || HELP.q ? "open" : ""}><summary><b>DJ-Software im Vergleich</b> <span class="muted sm">– wer schreibt was in die MP3?</span></summary>
    <div class="help-body"><table class="help-t"><thead><tr><th>Software</th><th>ID3-Tags direkt in MP3</th><th>Cue-Punkte direkt in MP3</th><th>Eigene Datenbank</th></tr></thead>
    <tbody>${d.software.map((s) => `<tr><td><b>${esc(s.name)}</b></td><td>${esc(s.id3)}</td><td>${esc(s.cues)}</td><td>${esc(s.db)}</td></tr>`).join("")}</tbody></table>
    <p class="muted sm">„Teilweise“: nicht alle angezeigten oder analysierten Werte werden in die Datei zurückgeschrieben. Cue-Punkte, Beatgrid und Loops haben keinen ID3-Standard – sie liegen in den Formaten der jeweiligen Programme (z. B. GEOB:Serato …).</p></div></details>`;
  const chapters = d.chapters.map((ch) => {
    const rows = ch.rows.filter(helpRowMatch);
    if ((HELP.q || HELP.dj) && !rows.length) return "";
    const open = HELP.open.has(ch.id) || !!HELP.q;
    let body;
    if (ch.kind === "analysis") {
      body = `<table class="help-t"><thead><tr><th>DJ-Parameter</th><th>Eigener ID3v2.4-Frame?</th><th>Empfohlene Ablage</th><th>In TagStudio</th><th>Herkunft</th><th class="n" title="Titel mit diesem Feld">Mit</th><th class="n" title="Titel ohne dieses Feld">Ohne</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td>${esc(r.param)}</td><td>${esc(r.own)}</td><td><code>${esc(r.where)}</code></td><td>${esc(r.tagstudio)}</td><td>${r.src ? srcBadge(r.src) : ""}</td><td class="n">${r.key ? helpCount(r) : ""}</td><td class="n">${r.key ? helpMissing(r) : ""}</td></tr>`).join("")}</tbody></table>`;
    } else {
      body = rows.length ? `<table class="help-t"><thead><tr><th>Frame / Tag</th><th>Mp3tag</th><th>Bedeutung</th><th title="für DJs wichtig">DJ</th><th>Herkunft</th><th class="n" title="Titel der gescannten Bibliothek mit diesem Feld">Mit</th><th class="n" title="Titel der gescannten Bibliothek ohne dieses Feld">Ohne</th></tr></thead><tbody>
        ${rows.map((r) => `<tr><td><code>${esc(r.key)}</code>${r.ver ? ` <span class="muted sm">${esc(r.ver)}</span>` : ""}</td><td>${esc(r.name || "")}</td>
          <td>${esc(r.meaning || r.label || "")}${r.help && r.help !== r.meaning ? `<div class="muted sm">${esc(r.help)}</div>` : ""}</td>
          <td>${r.dj ? "✓" : ""}</td><td>${r.src ? srcBadge(r.src) : ""}</td><td class="n">${helpCount(r)}${total && r.count ? `<div class="help-bar-n" style="width:${Math.max(2, Math.round(100 * r.count / total))}%"></div>` : ""}</td><td class="n">${helpMissing(r)}</td></tr>`).join("")}</tbody></table>`
        : ch.id === "custom" && !d.scan ? "" : '<div class="muted sm">Keine Einträge.</div>';
    }
    return `<details class="help-ch" data-ch="${esc(ch.id)}" ${open ? "open" : ""}><summary><b>${esc(ch.title)}</b> <span class="muted sm">${rows.length}</span></summary>
      <div class="help-body">${ch.desc ? `<p class="muted sm">${esc(ch.desc)}</p>` : ""}${body}</div></details>`;
  }).join("");
  $("#helpChapters").innerHTML = (HELP.q || HELP.dj ? "" : sw) + chapters;
}

async function helpScan() {
  const root = $("#helpRoot").value;
  if (!root) { toast("Bitte zuerst einen Ordner wählen (Standardordner des Taggers oder Snapshot-Bibliothek)."); return; }
  const r = await runTask(call("start_tag_scan", root), "Bibliothek scannen");
  if (!r || r.cancelled) return;
  status(`${fmtN(r.files)} Titel gescannt, ${fmtN(r.keys)} verschiedene Felder (${r.seconds} s).`, "info");
  HELP.open.add("custom");
  helpLoadTags(root);
}

/** Klick auf eine Anzahl: Tagger mit der Bibliothek öffnen und nach dem Feld filtern. */
async function helpFilter(key, label, mode = "has") {
  const root = HELP.data && HELP.data.root;
  setModule("tagger");
  const loaded = TG.loaded && TG.root && root && TG.root.replace(/[\\/]+$/, "").toLowerCase() === root.replace(/[\\/]+$/, "").toLowerCase();
  if (!loaded && root) {
    $("#tgPath").value = root;
    $("#tgRec").checked = true;
    await taggerLoad();
  }
  await tgSetFieldFilter(key, mode, label);
  const f = TG.fieldFilter, total = TG.rows.filter((r) => r.parent === undefined).length;
  toast(mode === "miss" ? `Filter „${label}“ fehlt: ${fmtN(f ? Math.max(0, total - f.n) : 0)} Titel ohne dieses Feld.`
    : `Filter „${label}“: ${fmtN(f ? f.n : 0)} Titel – oben auf „fehlt“ umschalten, um zu vervollständigen.`);
}

// ---------------------------------------------------------------------- Markdown (einfach, für README & Co.)
function mdInline(s) {
  let t = esc(s);
  t = t.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`);
  t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");
  t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, txt, url) => /^https?:/.test(url)
    ? `<a href="#" data-url="${url}">${txt} ↗</a>` : /ID3-FELDER\.md$/.test(url) ? `<a href="#" data-htab-link="id3">${txt}</a>`
    : /PLUGINS\.md$/.test(url) ? `<a href="#" data-htab-link="plugins">${txt}</a>` : txt);
  return t;
}

function mdToHtml(md) {
  const lines = md.replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0, para = [];
  const flush = () => { if (para.length) { out.push(`<p>${mdInline(para.join(" "))}</p>`); para = []; } };
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) {
      flush();
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`);
      continue;
    }
    const h = l.match(/^(#{1,4})\s+(.*)$/);
    if (h) { flush(); out.push(`<h${h[1].length + 1}>${mdInline(h[2])}</h${h[1].length + 1}>`); i++; continue; }
    if (/^\s*(---|\*\*\*)\s*$/.test(l)) { flush(); out.push("<hr>"); i++; continue; }
    if (/^\|/.test(l) && i + 1 < lines.length && /^\|[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
      flush();
      const cells = (x) => x.replace(/^\||\|\s*$/g, "").split("|").map((c) => c.trim());
      const head = cells(l);
      i += 2;
      const body = [];
      while (i < lines.length && /^\|/.test(lines[i])) body.push(cells(lines[i++]));
      out.push(`<table class="help-t"><thead><tr>${head.map((c) => `<th>${mdInline(c)}</th>`).join("")}</tr></thead><tbody>${body.map((r) => `<tr>${r.map((c) => `<td>${mdInline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      flush();
      const ordered = /^\s*\d+\./.test(l);
      const items = [];
      while (i < lines.length && (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
        const m = lines[i].match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
        if (m) items.push({ d: m[1].length, t: m[3] });
        else items[items.length - 1].t += " " + lines[i].trim();
        i++;
      }
      let html = "", depth = -1;
      const stack = [];
      for (const it of items) {
        const lvl = Math.min(3, Math.floor(it.d / 2));
        while (depth < lvl) { html += ordered && depth < 0 ? "<ol>" : "<ul>"; stack.push(ordered && depth < 0 ? "</ol>" : "</ul>"); depth++; }
        while (depth > lvl) { html += stack.pop(); depth--; }
        html += `<li>${mdInline(it.t)}</li>`;
      }
      while (stack.length) html += stack.pop();
      out.push(html);
      continue;
    }
    if (/^>\s?/.test(l)) {
      flush();
      const q = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, ""));
      out.push(`<blockquote>${mdInline(q.join(" "))}</blockquote>`);
      continue;
    }
    if (!l.trim()) { flush(); i++; continue; }
    para.push(l.trim());
    i++;
  }
  flush();
  return out.join("\n");
}

(function bindHelp() {
  $("#helpTabs").addEventListener("click", (e) => { const b = e.target.closest("[data-htab]"); if (b) helpTab(b.dataset.htab); });
  $("#helpScan").addEventListener("click", helpScan);
  $("#helpRoot").addEventListener("change", (e) => helpLoadTags(e.target.value));
  $("#helpQ").addEventListener("input", (e) => { HELP.q = e.target.value; helpRender(); });
  $("#helpDj").addEventListener("change", (e) => { HELP.dj = e.target.checked; helpRender(); });
  $("#helpOpenAll").addEventListener("click", () => { $$("#helpChapters details").forEach((d) => { d.open = true; HELP.open.add(d.dataset.ch); }); });
  $("#helpCloseAll").addEventListener("click", () => { $$("#helpChapters details").forEach((d) => { d.open = false; }); HELP.open.clear(); });
  $("#helpChapters").addEventListener("toggle", (e) => { const d = e.target; if (d.dataset && d.dataset.ch && !HELP.q) { if (d.open) HELP.open.add(d.dataset.ch); else HELP.open.delete(d.dataset.ch); } }, true);
  $("#helpChapters").addEventListener("click", (e) => { const b = e.target.closest("[data-filter]"); if (b) helpFilter(b.dataset.filter, b.dataset.label, b.dataset.mode || "has"); });
  $("#helpDoc").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-url]"); if (a) { e.preventDefault(); call("open_url", a.dataset.url); return; }
    const t = e.target.closest("a[data-htab-link]"); if (t) { e.preventDefault(); helpTab(t.dataset.htabLink); }
  });
})();
