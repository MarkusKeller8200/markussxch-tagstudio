/* MarKusSXCH TagStudio – Hilfe (#158): Tag-Übersicht mit aufklappbaren Kapiteln, Herkunft und Zählern aus dem
   Bibliotheks-Scan (Klick filtert im Tagger), Handbuch (README), ID3-Felder und Plugins als Markdown. */
"use strict";

const HELP = { tab: "tags", data: null, docs: null, open: new Set(["ident", "custom"]), q: "", dj: false, groups: new Set(), sort: { k: "", dir: 1 } };

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

/** Kurzname einer Gruppe für die Filter-Chips („1. Titel, Album …“ → „1. Titel, Album …“ gekürzt) */
function helpGroupShort(t) { return t.length > 34 ? t.slice(0, 32).replace(/[\s,]+\S*$/, "") + " …" : t; }

/** Einheitliche Zeile für alle Gruppen (Analysewerte: Ablage als Tag, Parameter als Name). */
function helpRowNorm(ch, r) {
  if (ch.kind !== "analysis") return r;
  return { ...r, key: r.key || "", tagShow: r.where, name: r.param,
    meaning: `Eigener Frame: ${r.own}${r.tagstudio ? " · In TagStudio: " + r.tagstudio : ""}`, dj: true, analysis: true };
}

function helpSortVal(r, k) {
  const total = HELP.data && HELP.data.scan ? HELP.data.scan.files : 0;
  if (k === "mit") return r.count ?? -1;
  if (k === "ohne") return r.count === null || r.count === undefined ? -1 : total - r.count;
  if (k === "name") return (r.name || "").toLowerCase();
  return (r.tagShow || r.key || "").toLowerCase();
}

function helpRender() {
  const d = HELP.data;
  if (!d) return;
  const total = d.scan ? d.scan.files : 0;
  const groups = d.chapters.map((ch) => ({ ch, rows: ch.rows.map((r) => helpRowNorm(ch, r)).filter(helpRowMatch) }));
  // Filter-Chips je Gruppe (Mehrfachauswahl; keine Auswahl = alle)
  $("#helpGroups").innerHTML = `<button data-grp="" class="${HELP.groups.size ? "" : "on"}">Alle</button>` + groups.map(({ ch, rows }) =>
    `<button data-grp="${esc(ch.id)}" class="${HELP.groups.has(ch.id) ? "on" : ""}" title="${esc(ch.title)}" ${rows.length ? "" : "disabled"}>${esc(helpGroupShort(ch.title))} <span class="muted">${rows.length}</span></button>`).join("");
  const { k, dir } = HELP.sort;
  const cmp = (a, b) => { const x = helpSortVal(a, k), y = helpSortVal(b, k); return (x < y ? -1 : x > y ? 1 : 0) * dir; };
  const filtering = !!(HELP.q || HELP.dj);
  const th = (key, label, cls = "", title = "") => `<th class="${cls}${k === key ? " sorted" : ""}" data-sort="${key}" title="${esc(title || "Sortieren")}">${label}${k === key ? (dir > 0 ? " ▴" : " ▾") : ""}</th>`;
  let body = "";
  for (const { ch, rows } of groups) {
    if (HELP.groups.size && !HELP.groups.has(ch.id)) continue;
    if (filtering && !rows.length) continue;
    const open = HELP.open.has(ch.id) || filtering;
    const withCount = rows.filter((r) => r.count).length;
    body += `<tr class="help-grp" data-ch="${esc(ch.id)}"><td colspan="8"><button class="tw" aria-expanded="${open}" title="${open ? "Zuklappen" : "Aufklappen"}">${open ? "▾" : "▸"}</button><b>${esc(ch.title)}</b> <span class="muted sm">${rows.length} Tags${total && withCount ? ` · ${withCount} in der Bibliothek` : ""}</span>${ch.desc && open ? `<div class="muted sm help-grp-d">${esc(ch.desc)}</div>` : ""}</td></tr>`;
    if (!open) continue;
    if (!rows.length) { body += `<tr class="help-sub"><td></td><td colspan="7" class="muted sm">${ch.id === "custom" && !d.scan ? "Erst nach „Bibliothek scannen“." : "Keine Einträge."}</td></tr>`; continue; }
    const list = k ? [...rows].sort(cmp) : rows;
    body += list.map((r) => `<tr class="help-sub" data-ch="${esc(ch.id)}"><td></td>
      <td><code>${esc(r.tagShow || r.key)}</code>${r.ver ? ` <span class="muted sm">${esc(r.ver)}</span>` : ""}</td><td>${esc(r.name || "")}</td>
      <td>${esc(r.meaning || r.label || "")}${r.help && r.help !== r.meaning ? `<div class="muted sm">${esc(r.help)}</div>` : ""}</td>
      <td>${r.dj ? "✓" : ""}</td><td>${r.src ? srcBadge(r.src) : ""}</td>
      <td class="n">${r.key ? helpCount(r) : ""}${total && r.count ? `<div class="help-bar-n" style="width:${Math.max(2, Math.round(100 * r.count / total))}%"></div>` : ""}</td>
      <td class="n">${r.key ? helpMissing(r) : ""}</td></tr>`).join("");
  }
  const sw = `<details class="help-ch" data-ch="software" ${HELP.open.has("software") ? "open" : ""}><summary><b>DJ-Software im Vergleich</b> <span class="muted sm">– wer schreibt was in die MP3?</span></summary>
    <div class="help-body"><table class="help-t"><thead><tr><th>Software</th><th>ID3-Tags direkt in MP3</th><th>Cue-Punkte direkt in MP3</th><th>Eigene Datenbank</th></tr></thead>
    <tbody>${d.software.map((s) => `<tr><td><b>${esc(s.name)}</b></td><td>${esc(s.id3)}</td><td>${esc(s.cues)}</td><td>${esc(s.db)}</td></tr>`).join("")}</tbody></table>
    <p class="muted sm">„Teilweise“: nicht alle angezeigten oder analysierten Werte werden in die Datei zurückgeschrieben. Cue-Punkte, Beatgrid und Loops haben keinen ID3-Standard – sie liegen in den Formaten der jeweiligen Programme (z. B. GEOB:Serato …).</p></div></details>`;
  $("#helpChapters").innerHTML = `<div class="help-grid card"><table class="help-t"><thead><tr><th class="tw-c"></th>${th("key", "Frame / Tag")}${th("name", "Mp3tag")}<th>Bedeutung</th><th title="für DJs wichtig">DJ</th><th>Herkunft</th>${th("mit", "Mit", "n", "Titel der gescannten Bibliothek mit diesem Feld – Klick auf die Zahl filtert im Tagger")}${th("ohne", "Ohne", "n", "Titel der gescannten Bibliothek ohne dieses Feld – Klick auf die Zahl filtert im Tagger auf „fehlt“")}</tr></thead>
    <tbody>${body || '<tr><td colspan="8" class="muted">Keine Tags passen zur Suche.</td></tr>'}</tbody></table></div>${HELP.q || HELP.dj ? "" : sw}`;
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
  $("#helpOpenAll").addEventListener("click", () => { (HELP.data ? HELP.data.chapters : []).forEach((c) => HELP.open.add(c.id)); helpRender(); });
  $("#helpCloseAll").addEventListener("click", () => { HELP.open.clear(); helpRender(); });
  $("#helpGroups").addEventListener("click", (e) => {
    const b = e.target.closest("[data-grp]"); if (!b) return;
    const id = b.dataset.grp;
    if (!id) HELP.groups.clear();
    else { if (HELP.groups.has(id)) HELP.groups.delete(id); else { HELP.groups.add(id); HELP.open.add(id); } }
    helpRender();
  });
  $("#helpChapters").addEventListener("toggle", (e) => { const d = e.target; if (d.dataset && d.dataset.ch && !HELP.q) { if (d.open) HELP.open.add(d.dataset.ch); else HELP.open.delete(d.dataset.ch); } }, true);
  $("#helpChapters").addEventListener("click", (e) => {
    const b = e.target.closest("[data-filter]"); if (b) { helpFilter(b.dataset.filter, b.dataset.label, b.dataset.mode || "has"); return; }
    const so = e.target.closest("th[data-sort]");
    if (so) { const k = so.dataset.sort; HELP.sort = HELP.sort.k === k ? (HELP.sort.dir > 0 ? { k, dir: -1 } : { k: "", dir: 1 }) : { k, dir: k === "mit" || k === "ohne" ? -1 : 1 }; helpRender(); return; }
    const g = e.target.closest("tr.help-grp");
    if (g && !e.target.closest("a,button:not(.tw)")) { const id = g.dataset.ch; if (HELP.open.has(id)) HELP.open.delete(id); else HELP.open.add(id); helpRender(); }
  });
  $("#helpDoc").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-url]"); if (a) { e.preventDefault(); call("open_url", a.dataset.url); return; }
    const t = e.target.closest("a[data-htab-link]"); if (t) { e.preventDefault(); helpTab(t.dataset.htabLink); }
  });
})();
