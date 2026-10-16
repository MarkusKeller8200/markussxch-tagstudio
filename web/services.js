/* MarKusSXCH TagStudio – Online-Dienste als Plugins (#204):
   Integrationsfenster je Dienst-Plugin (Endpunkte, Testabfrage ohne Track, API-Tester) und Gesamtübersicht. */
"use strict";

const SVC = { detail: null, tab: "ep", filter: "", lastEp: "" };
const SVC_ST = { full: ["vollständig", "svc-full"], partial: ["teilweise", "svc-part"], none: ["nicht implementiert", "svc-none"] };

function svcLink(url, label) {
  return url ? `<a href="#" class="pl-link" data-url="${esc(url)}" title="${esc(url)}">${esc(label)} ↗</a>` : "";
}
function svcBadge(st) { const [t, c] = SVC_ST[st] || SVC_ST.none; return `<span class="svc-st ${c}">${t}</span>`; }
function svcCounts(c) {
  return ["full", "partial", "none"].filter((k) => c[k]).map((k) => `<span class="svc-st ${SVC_ST[k][1]}">${c[k]} ${SVC_ST[k][0]}</span>`).join(" ");
}

/** Auftrag im Fenster laufen lassen (der Fortschritts-Dialog läge hinter dem Fenster): Text + Abbrechen. */
async function svcTask(startPromise, box) {
  const r = await startPromise;
  if (!r.ok) { box.innerHTML = `<div class="pl-box err">${esc(r.error)}</div>`; return null; }
  box.innerHTML = `<div class="svc-run"><span class="spin"></span> <span class="svc-run-t">läuft …</span>
    <button class="ghost sm" data-svccancel>Abbrechen</button></div>`;
  const cbtn = box.querySelector("[data-svccancel]");
  cbtn.onclick = () => { cbtn.disabled = true; box.querySelector(".svc-run-t").textContent = "Wird abgebrochen …"; call("cancel_task"); };
  for (;;) {
    const t = await call("task_status");
    if (t.done) {
      if (t.error) { box.innerHTML = `<div class="pl-box err">${esc(t.error)}</div>`; return null; }
      if (t.result && t.result.cancelled) { box.innerHTML = '<div class="muted">Abgebrochen.</div>'; return null; }
      return t.result;
    }
    const tt = box.querySelector(".svc-run-t");
    if (tt && t.text && !cbtn.disabled) tt.textContent = t.text;
    await new Promise((ok) => setTimeout(ok, 150));
  }
}

// ---------------------------------------------------------------------- Integrationsfenster je Plugin
async function svcOpen(pid, tab = "ep", eid = "") {
  let d;
  try { d = await call("service_detail", pid); } catch (e) { toast(String(e.message || e)); return; }
  SVC.detail = d; SVC.tab = tab; SVC.filter = ""; SVC.lastEp = eid || SVC.lastEp; SVC.tqOut = ""; SVC.apiOut = {};
  SVC.tqv = SVC.tqv || {}; SVC.apiVals = SVC.apiVals || {};
  await modal({
    title: `Integration – ${d.name}`, wide: true,
    html: `<div class="svc-head">
        <div><b>${esc(d.name)}</b> <span class="muted sm">· Plugin „${esc(d.plugin_name)}“ · ${esc(d.auth_text)}</span>
          ${d.ready ? "" : `<span class="svc-st svc-none">${d.enabled ? "nicht bereit" : "ausgeschaltet"}</span>`}</div>
        <div class="svc-links sm">${svcLink(d.docs, "API-Dokumentation")}${d.home ? " · " + svcLink(d.home, "Startseite") : ""}${d.terms ? " · " + svcLink(d.terms, "Nutzungsbedingungen") : ""}</div>
        ${d.limits ? `<div class="hint">Grenzen: ${esc(d.limits)}</div>` : ""}${d.auth_note ? `<div class="hint">${esc(d.auth_note)}</div>` : ""}
        ${d.note ? `<div class="hint">${esc(d.note)}</div>` : ""}
      </div>
      <div class="svc-tabs" role="tablist">
        <button role="tab" data-svctab="ep">Endpunkte (${d.endpoints.length})</button>
        <button role="tab" data-svctab="tq" ${d.test_query ? "" : "disabled"} title="${d.test_query ? "Suche wie mit einem Titel – ohne Track" : d.ready ? "Dieser Dienst bietet keine Testabfrage" : "Plugin zuerst einschalten"}">Testabfrage</button>
        <button role="tab" data-svctab="api" ${d.ready && d.endpoints.some((e) => e.test) ? "" : "disabled"} title="Einen Endpunkt direkt aufrufen (nur lesend)">API-Tester</button>
      </div>
      <div id="svcBody"></div>`,
    buttons: [{ label: "Schliessen", value: null, primary: true }],
    onMount: (b) => {
      b.addEventListener("click", (e) => {
        const l = e.target.closest(".pl-link[data-url]");
        if (l) { e.preventDefault(); call("open_url", l.dataset.url); return; }
        const t = e.target.closest("[data-svctab]");
        if (t && !t.disabled) { SVC.tab = t.dataset.svctab; svcRender(b); return; }
        const f = e.target.closest("[data-svcf]");
        if (f) { SVC.filter = SVC.filter === f.dataset.svcf ? "" : f.dataset.svcf; svcRender(b); return; }
        const te = e.target.closest("[data-svctest]");
        if (te) { SVC.tab = "api"; SVC.lastEp = te.dataset.svctest; svcRender(b); return; }
        if (e.target.closest("#svcTqRun")) svcTestQuery(b);
        if (e.target.closest("#svcTqClear")) { SVC.tqv[SVC.detail.id] = {}; SVC.tqOut = ""; svcRender(b); $("#svcTq-artist", b)?.focus(); }
        if (e.target.closest("#svcTqEx")) { delete SVC.tqv[SVC.detail.id]; svcRender(b); }
        const idl = e.target.closest("a.svc-id"); if (idl) { e.preventDefault(); svcIdPick(b, idl); return; }
        const idt = e.target.closest("[data-idto]"); if (idt) { svcIdUse(b, idt); return; }
        if (e.target.closest("#svcApiClear")) { svcApiClear(b, true); }
        if (e.target.closest("#svcApiEx")) { svcApiClear(b, false); }
        if (e.target.closest("#svcApiRun")) svcApiRun(b);
        if (e.target.closest("#svcApiCopy")) { const pre = $("#svcApiBody", b); if (pre) navigator.clipboard?.writeText(pre.textContent).then(() => toast("Antwort kopiert.")); }
      });
      b.addEventListener("change", (e) => { if (e.target.id === "svcApiEp") { SVC.lastEp = e.target.value; svcRender(b); } });
      b.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" || e.target.tagName !== "INPUT") return;
        e.preventDefault(); e.stopPropagation();
        if (e.target.closest("#svcTq")) svcTestQuery(b); else if (e.target.closest("#svcApi")) svcApiRun(b);
      });
      svcRender(b);
    },
  });
}

function svcRender(b) {
  const d = SVC.detail;
  b.querySelectorAll("[data-svctab]").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.svctab === SVC.tab)));
  const body = $("#svcBody", b);
  if (SVC.tab === "tq") { body.innerHTML = svcTqHtml(); return; }
  if (SVC.tab === "api") { body.innerHTML = svcApiHtml(d); return; }
  const eps = d.endpoints.filter((e) => !SVC.filter || e.status === SVC.filter);
  body.innerHTML = `<div class="svc-filter">${["full", "partial", "none"].filter((k) => d.counts[k]).map((k) =>
      `<button class="sn-chip${SVC.filter === k ? " on" : ""}" data-svcf="${k}">${SVC_ST[k][0]} ${d.counts[k]}</button>`).join("")}</div>
    <div class="fx-table svc-table"><table><thead><tr><th>Status</th><th>Methode</th><th>Pfad</th><th>Beschreibung</th><th>Genutzt für / Hinweis</th><th></th></tr></thead><tbody>
    ${eps.map((e) => `<tr><td>${svcBadge(e.status)}</td><td><code>${esc(e.method)}</code></td><td><code>${esc(e.path)}</code></td>
      <td>${esc(e.label)}</td><td>${esc(e.use)}${e.note ? `<div class="hint">${esc(e.note)}</div>` : ""}</td>
      <td>${e.test && d.ready ? `<button class="ghost sm" data-svctest="${esc(e.id)}" title="Im API-Tester öffnen">Testen</button>` : ""}</td></tr>`).join("")}
    </tbody></table></div>`;
}

// ---------------------------------------------------------------------- Testabfrage ohne Track
function svcTqHtml() {
  const d = SVC.detail, ex = d.example || {};
  const v = SVC.tqv[d.id] || ex;                      // #205: ohne eigene Eingaben das Beispiel des Dienstes
  const f = (k, l, ph, w = "") => `<label for="svcTq-${k}">${l}</label><input id="svcTq-${k}" data-tq="${k}" value="${esc(v[k] || "")}" placeholder="${esc(ph)}" spellcheck="false" ${w}>`;
  return `<div id="svcTq"><div class="hint">Sucht wie mit einem Titel aus der Liste – mit denselben Stufen und derselben Bewertung –, aber ohne Track und ohne Tags zu ändern.</div>
    <div class="frm svc-tq">${f("artist", "Künstler", "z. B. Mara Lind")}${f("title", "Titel", "z. B. Nordlicht (Extended Mix)")}${f("mix", "Mix", "leer = aus dem Titel")}
      ${f("album", "Album", "optional")}${f("isrc", "ISRC", "optional")}${f("duration", "Dauer", "z. B. 6:12 oder 372")}
      <span></span><div class="svc-btns"><button class="primary sm" id="svcTqRun">Suchen</button>
        <button class="ghost sm" id="svcTqClear" title="Alle Eingaben leeren">Felder löschen</button>
        ${Object.keys(ex).length ? `<button class="ghost sm" id="svcTqEx" title="Beispiel, das bei ${esc(d.name)} einen Treffer liefert">Beispiel einsetzen</button>` : ""}</div></div>
    <div id="svcTqOut">${SVC.tqOut || ""}</div></div>`;
}

async function svcTestQuery(b) {
  const raw = {};
  b.querySelectorAll("[data-tq]").forEach((i) => { raw[i.dataset.tq] = i.value.trim(); });
  SVC.tqv[SVC.detail.id] = raw;
  const out = $("#svcTqOut", b);
  const r = await svcTask(call("start_service_test", SVC.detail.id, raw), out);
  if (!r) return;
  const pct = (x) => `<span class="svc-pct ${x.sure ? "sure" : x.maybe ? "maybe" : "low"}" title="${x.sure ? "sicher" : x.maybe ? "unsicher" : "zu schwach – würde nicht vorgeschlagen"}">${x.score} %</span>`;
  const cols = [["Treffer", (x) => pct(x)], ["Künstler", (x) => esc(x.artist)], ["Titel", (x) => esc(x.title) + (x.mix ? ` <span class="muted">(${esc(x.mix)})</span>` : "")],
    ["Album", (x) => esc(x.album)], ["Label", (x) => esc(x.label)], ["Datum", (x) => esc(x.date)], ["Länge", (x) => esc(x.length)],
    ["ISRC", (x) => esc(x.isrc)], ["Info", (x) => esc(x.extra)], ["", (x) => (x.url ? svcLink(x.url, "ansehen") : "")]]
    .filter(([h, fn]) => !h || h === "Treffer" || r.rows.some((x) => fn(x)));
  SVC.tqOut = `<div class="sm svc-sum">${r.rows.length ? `${r.rows.length} Kandidat(en) – oben der beste. Ab 80 % „sicher“ (vorausgewählt), ab 62 % „unsicher“.` : "Keine Kandidaten."}</div>
    ${r.rows.length ? `<div class="fx-table svc-table"><table><thead><tr>${cols.map(([h]) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>
      ${r.rows.map((x) => `<tr>${cols.map(([, fn]) => `<td>${fn(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : ""}
    ${r.log && r.log.length ? `<details class="sm" open><summary class="muted">Protokoll (${r.log.length})</summary><pre class="pl-log">${esc(r.log.join("\n"))}</pre></details>` : ""}`;
  out.innerHTML = SVC.tqOut;
}

// ---------------------------------------------------------------------- API-Tester (Rohabfrage)
function svcApiHtml(d) {
  const eps = d.endpoints.filter((e) => e.test);
  if (!eps.length) return '<div class="muted">Dieser Dienst hat keine lesenden Endpunkte zum Testen.</div>';
  const ep = eps.find((e) => e.id === SVC.lastEp) || eps[0];
  SVC.lastEp = ep.id;
  const vals = SVC.apiVals[d.id + "/" + ep.id] || {};
  const hasEx = ep.params.some((p) => p.example);
  return `<div id="svcApi"><div class="hint">Ruft den Endpunkt direkt auf (nur lesend). Schlüssel und Token setzt das Plugin ein – sie werden nie angezeigt.</div>
    <div class="frm svc-api">
      <label for="svcApiEp">Endpunkt</label><select id="svcApiEp" class="inp">${["full", "partial", "none"].map((st) => {
        const g = eps.filter((e) => e.status === st); if (!g.length) return "";
        return `<optgroup label="${SVC_ST[st][0]}">${g.map((e) => `<option value="${esc(e.id)}" ${e.id === ep.id ? "selected" : ""}>${esc(e.method)} ${esc(e.path)} – ${esc(e.label)}</option>`).join("")}</optgroup>`; }).join("")}</select>
      ${ep.params.map((p) => `<label for="svcP-${esc(p.name)}">${esc(p.label)}${p.required ? " *" : ""}${p.in === "path" ? ' <span class="faint">(Pfad)</span>' : ""}</label>
        <input id="svcP-${esc(p.name)}" data-ap="${esc(p.name)}" value="${esc(vals[p.name] ?? (p.example || p.default))}" placeholder="${esc(p.example || "")}" spellcheck="false">`).join("")}
      <span></span><div class="svc-btns"><button class="primary sm" id="svcApiRun">Senden</button>
        ${ep.params.length ? '<button class="ghost sm" id="svcApiClear" title="Eingaben leeren – feste Vorgaben wie fmt=json bleiben">Felder löschen</button>' : ""}
        ${hasEx ? '<button class="ghost sm" id="svcApiEx" title="Beispielwerte, die ein Resultat liefern">Beispiel einsetzen</button>' : ""}</div></div>
    <div id="svcApiOut">${(SVC.apiOut || {})[ep.id] || ""}</div></div>`;
}

async function svcApiRun(b) {
  const eid = $("#svcApiEp", b).value, params = {};
  b.querySelectorAll("[data-ap]").forEach((i) => { params[i.dataset.ap] = i.value; });
  SVC.apiVals[SVC.detail.id + "/" + eid] = params;
  const out = $("#svcApiOut", b);
  const r = await svcTask(call("start_service_api", SVC.detail.id, eid, params), out);
  if (!r) return;
  const hd = Object.entries(r.headers || {}).map(([k, v]) => `${k}: ${v}`).join("\n");
  const html = `<div class="svc-resp"><span class="svc-http ${r.ok ? "ok" : "bad"}">HTTP ${r.status}</span>
      <span class="muted sm">${fmtN(r.ms)} ms · ${fmtN(r.bytes)} Bytes${r.content_type ? " · " + esc(r.content_type) : ""}${r.retries ? ` · ${r.retries} Wiederholung${r.retries > 1 ? "en" : ""} (Dienst ausgelastet)` : ""}</span>
      <button class="ghost sm" id="svcApiCopy">Antwort kopieren</button></div>
    <div class="sm svc-url"><code>${esc(r.url)}</code></div>
    ${hd ? `<details class="sm"><summary class="muted">Kopfzeilen</summary><pre class="pl-log">${esc(hd)}</pre></details>` : ""}
    <div id="svcIdBar" class="svc-idbar sm" hidden></div>
    <pre class="svc-body" id="svcApiBody">${svcBodyHtml(r.body)}</pre>`;
  SVC.apiOut = { ...(SVC.apiOut || {}), [eid]: html };
  out.innerHTML = html;
}

// #213: IDs in der Antwort anklickbar – damit den nächsten Endpunkt füllen
const SVC_IDKEY = /^(id|mbid|.*_id|isrc|upc|discid|code)$/i;
function svcIdOk(k, v) {
  if (!SVC_IDKEY.test(k)) return false;
  if (typeof v === "number") return Number.isInteger(v) && v > 0;
  return typeof v === "string" && /^[A-Za-z0-9._-]{2,64}$/.test(v) && v !== "•••";
}
/** JSON hübsch ausgeben; IDs als Links mit dem Namen des umgebenden Objekts als Hinweis (release, artist …) */
function svcJsonHtml(v, ind, parent) {
  const pad = "  ".repeat(ind);
  if (Array.isArray(v)) {
    if (!v.length) return "[]";
    return "[\n" + v.map((x) => pad + "  " + svcJsonHtml(x, ind + 1, parent)).join(",\n") + "\n" + pad + "]";
  }
  if (v && typeof v === "object") {
    const ks = Object.keys(v);
    if (!ks.length) return "{}";
    return "{\n" + ks.map((k) => {
      const x = v[k];
      const val = svcIdOk(k, x)
        ? `<a href="#" class="svc-id" data-idv="${esc(String(x))}" data-idk="${esc(k)}" data-idp="${esc(parent || "")}" title="Diese ID in einen anderen Endpunkt einsetzen">${esc(JSON.stringify(x))}</a>`
        : svcJsonHtml(x, ind + 1, x && typeof x === "object" ? k : parent);
      return `${pad}  ${esc(JSON.stringify(k))}: ${val}`;
    }).join(",\n") + "\n" + pad + "}";
  }
  return esc(JSON.stringify(v));
}
function svcBodyHtml(body) {
  if (!body) return "(leer)";
  try { return svcJsonHtml(JSON.parse(body), 0, ""); } catch { return esc(body); }
}
/** Endpunkte mit ID-Feld, passendster zuerst (Objektname bzw. Schlüssel im Pfad oder in der ID des Endpunkts) */
function svcIdTargets(key, parent) {
  const d = SVC.detail, words = [parent, key.replace(/_?id$/i, "")].filter(Boolean).map((w) => w.toLowerCase().replace(/s$/, ""));
  const out = [];
  d.endpoints.filter((e) => e.test).forEach((e) => {
    const p = e.params.find((x) => (x.in === "path" && SVC_IDKEY.test(x.name)) || (x.in === "query" && x.name.toLowerCase() === key.toLowerCase()));
    if (!p) return;
    const hay = (e.id + " " + e.path).toLowerCase();
    const score = words.reduce((n, w) => n + (w && hay.includes(w) ? 2 : 0), 0) + (p.name.toLowerCase() === key.toLowerCase() ? 1 : 0);
    out.push({ e, p, score });
  });
  return out.sort((a, b) => b.score - a.score);
}
function svcIdPick(b, a) {
  const bar = $("#svcIdBar", b), v = a.dataset.idv, t = svcIdTargets(a.dataset.idk, a.dataset.idp);
  bar.hidden = false;
  bar.innerHTML = t.length
    ? `ID <code>${esc(v)}</code>${a.dataset.idp ? ` <span class="muted">(${esc(a.dataset.idp)})</span>` : ""} einsetzen in: ${t.slice(0, 8).map(({ e, p }) =>
        `<button class="ghost sm" data-idto="${esc(e.id)}" data-idparam="${esc(p.name)}" data-idv="${esc(v)}">${esc(e.label)}</button>`).join(" ")}`
    : `Kein Endpunkt mit passendem ID-Feld für <code>${esc(v)}</code>.`;
}
function svcIdUse(b, btn) {
  const d = SVC.detail, ep = d.endpoints.find((e) => e.id === btn.dataset.idto);
  if (!ep) return;
  const key = d.id + "/" + ep.id;
  SVC.apiVals[key] = { ...Object.fromEntries(ep.params.map((p) => [p.name, p.example || p.default])), [btn.dataset.idparam]: btn.dataset.idv };
  SVC.lastEp = ep.id;
  svcRender(b);
  $("#svcApiRun", b)?.focus();
}

function svcApiClear(b, clear) {
  const d = SVC.detail, ep = d.endpoints.find((e) => e.id === $("#svcApiEp", b).value);
  if (!ep) return;
  const key = d.id + "/" + ep.id;
  if (clear) SVC.apiVals[key] = Object.fromEntries(ep.params.map((p) => [p.name, p.default]));
  else delete SVC.apiVals[key];
  if (SVC.apiOut) delete SVC.apiOut[ep.id];
  svcRender(b);
}

// ---------------------------------------------------------------------- Gesamtübersicht
async function svcOverview() {
  const r = await call("services_overview");
  const list = r.services;
  const all = list.reduce((a, s) => { ["full", "partial", "none"].forEach((k) => (a[k] += s.counts[k])); return a; }, { full: 0, partial: 0, none: 0 });
  let filter = "";
  const rows = () => list.map((s) => {
    const eps = s.endpoints.filter((e) => !filter || e.status === filter);
    if (!eps.length) return "";
    const state = s.plugin ? (s.ready ? '<span class="svc-st svc-full">bereit</span>' : `<span class="svc-st svc-none">${s.enabled ? "nicht bereit" : "aus"}</span>`) : '<span class="svc-st svc-part">Kern</span>';
    return `<tr class="svc-grp"><td colspan="5"><b>${esc(s.name)}</b> <span class="muted sm">· ${esc(s.plugin_name)} · ${esc(s.auth_text)}${s.kind === "local" ? " · lokal" : ""}</span> ${state}
        <span class="svc-links sm">${svcLink(s.docs, "API")}</span>
        ${s.plugin ? `<button class="ghost sm" data-svcopen="${esc(s.plugin)}">Integration …</button>` : ""}</td></tr>
      ${eps.map((e) => `<tr><td>${svcBadge(e.status)}</td><td><code>${esc(e.method)}</code></td><td><code>${esc(e.path)}</code></td><td>${esc(e.label)}</td>
        <td>${esc(e.use)}${e.note ? `<div class="hint">${esc(e.note)}</div>` : ""}</td></tr>`).join("")}`;
  }).join("");
  await modal({
    title: "Integrationen – alle Online-Dienste", wide: true,
    html: `<div class="hint">Jeder Online-Dienst ist ein eigenes Plugin (Updates bleiben im Kern). „Vollständig“: genutzt, wie TagStudio es braucht · „teilweise“: nur ein Teil der Möglichkeiten · „nicht implementiert“: zur Übersicht aufgeführt.</div>
      <div class="svc-filter" id="svcOvF">${["full", "partial", "none"].map((k) => `<button class="sn-chip" data-ovf="${k}">${SVC_ST[k][0]} ${all[k]}</button>`).join("")}
        <span class="muted sm">${list.length} Dienste · ${all.full + all.partial + all.none} Endpunkte</span></div>
      <div class="fx-table svc-table svc-ov"><table><thead><tr><th>Status</th><th>Methode</th><th>Pfad</th><th>Beschreibung</th><th>Genutzt für / Hinweis</th></tr></thead><tbody id="svcOvBody">${rows()}</tbody></table></div>`,
    buttons: [{ label: "Schliessen", value: null, primary: true }],
    onMount: (b) => b.addEventListener("click", (e) => {
      const l = e.target.closest(".pl-link[data-url]");
      if (l) { e.preventDefault(); call("open_url", l.dataset.url); return; }
      const f = e.target.closest("[data-ovf]");
      if (f) {
        filter = filter === f.dataset.ovf ? "" : f.dataset.ovf;
        b.querySelectorAll("[data-ovf]").forEach((x) => x.classList.toggle("on", x.dataset.ovf === filter));
        $("#svcOvBody", b).innerHTML = rows(); return;
      }
      const o = e.target.closest("[data-svcopen]");
      if (o) { hideModalThen(() => svcOpen(o.dataset.svcopen)); }
    }),
  });
}

/** Offenes Fenster schliessen und danach ein anderes öffnen */
function hideModalThen(fn) {
  const btn = $("#mBtns .primary");
  if (btn) btn.click();
  setTimeout(fn, 60);
}
