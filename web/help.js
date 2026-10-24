/* MarKusSXCH TagStudio – Hilfe (#158): Tag-Übersicht mit aufklappbaren Kapiteln, Herkunft und Zählern aus dem
   Bibliotheks-Scan (Klick filtert im Tagger), Handbuch (README), ID3-Felder und Plugins als Markdown. */
"use strict";

const HELP = { tab: "tags", data: null, docs: null, open: new Set(["ident", "custom"]), q: "", dj: false, groups: new Set(), sort: { k: "", dir: 1 } };

async function helpShow() {
  helpTab(HELP.tab);
}

// ---------------------------------------------------------------------- Tastenkombinationen (#159)
const MODK = /Mac|iPhone|iPad/.test(navigator.platform || "") ? "Cmd" : "Strg";
const HELP_KEYS = [
  ["Allgemein", "", [
    [`${MODK}+S`, "Speichern"], [`${MODK}+Z`, "Rückgängig"], [`${MODK}+Y · ${MODK}+Shift+Z`, "Wiederholen"],
    ["F11", "Vollbild ein/aus (App-Fenster)"], ["Esc", "Menü, Cover-Ansicht oder Dialog schliessen"],
    ["Enter", "Im Dialog: Hauptknopf (z. B. Speichern, Übernehmen)"], ["←/→ auf einem Trenngriff", "Splitter verschieben (Doppelklick setzt zurück)"],
    ["Alt+← / Alt+→ · Maustasten Zurück/Vorwärts", "Zur vorherigen / nächsten Ansicht (nicht im Vergleich, #274)"]]],
  ["Player", "Tagger, Vergleich und DJ-Set – nicht während der Eingabe in ein Feld", [
    ["Leertaste", "Abspielen / Pause"], ["↑ / ↓", "Vorheriger / nächster Titel (überall, ausser in Listen mit eigener Auswahl)"],
    ["← / →", "Einen Takt zurück / vor (vier Schläge, bei bekanntem BPM)"], ["Shift+← / Shift+→", "Vorheriger / nächster Cue-Punkt (zurück: 4-Takt-Toleranz)"],
    ["0–5", "Bewertung setzen (0 = keine)"], ["F", "Like ein/aus"], ["R", "Wiederholen ein/aus"], ["L", "A–B-Schleife setzen (dreimal: aufheben)"],
    ["Esc", "A–B-Schleife aufheben"], ["M", "Stumm ein/aus"], ["S / Shift+S", "Nächste / vorherige Stem-Spur"],
    ["B", "Tasten wirken auf Player A bzw. B (bei zwei Playern)"], ["Shift+P", "Player-Leiste oben ein-/ausklappen"],
    [`${MODK}+P`, "Im externen Player öffnen"], ["Doppelklick auf einen Titel", "Titel abspielen"]]],
  ["Tagger", "Titelliste", [
    ["↑ / ↓", "Markierung bewegen"], ["Shift+↑ / Shift+↓", "Markierung erweitern"], [`${MODK}+A`, "Alle Titel markieren"],
    ["→ / ←", "Stems auf- / zuklappen"], ["F5", "Ordner neu einlesen"], ["Enter (im Feld)", "Wert übernehmen"], ["Esc (im Feld)", "Eingabe verwerfen"],
    ["Enter oder , (Stimmung)", "Stimmung hinzufügen"], ["Rücktaste (leeres Stimmungsfeld)", "Letzte Stimmung entfernen"],
    [`${MODK}+Shift+P`, "Markierte Titel zur zuletzt benutzten Playlist"]]],
  ["Vergleich", "", [
    ["↑ / ↓", "Paar bzw. Feld wechseln"], ["Alt+→ / Alt+←", "Markierte Felder nach rechts / links kopieren"],
    [`${MODK}+A`, "Alle Felder markieren"], ["Enter oder F2", "Feld bearbeiten"], ["F5", "Neu vergleichen"], ["Shift+F5", "Aktuelles Paar neu einlesen"],
    ["Enter (in den Pfadfeldern)", "Vergleich starten"]]],
  ["DJ-Set", "", [
    ["↑ / ↓", "Titel wählen"], ["Alt+↑ / Alt+↓", "Titel nach oben / unten verschieben"], ["G", "Titel an seinem Platz fixieren / lösen"],
    ["Entf / Rücktaste", "Titel aus dem Set entfernen"], ["Enter", "Titel im Player laden und abspielen"]]],
  ["Text- und XML-Editor", "", [
    [`${MODK}+Enter · ${MODK}+S`, "Übernehmen und schliessen"], ["Esc", "Schliessen ohne Übernehmen"], ["Tab", "Einrücken (Text-Ansicht)"]]],
  ["Player-Fenster (separat)", "", [
    ["Leertaste", "Abspielen / Pause"], ["↑ / ↓", "Vorheriger / nächster Titel"],
    ["← / →", "Einen Takt zurück / vor"], ["Shift+← / Shift+→", "Vorheriger / nächster Cue-Punkt"],
    ["0–5 · F · R · L · M", "Bewertung, Like, Wiederholen, A–B, Stumm"], ["B", "Ziel Player A / B"]]],
];

function helpKeysHtml() {
  return `<h2>Tastenkombinationen</h2><p class="muted">Die meisten Tasten wirken nicht, solange in ein Eingabefeld geschrieben wird.${MODK === "Cmd" ? "" : " Auf dem Mac gilt Cmd statt Strg."}</p>`
    + HELP_KEYS.map(([t, d, rows]) => `<h3>${esc(t)}</h3>${d ? `<p class="muted sm">${esc(d)}</p>` : ""}<table class="help-t help-keys"><tbody>${rows.map(([k, w]) => `<tr><td>${k.split(" · ").map((x) => x.split(" / ").map((y) => `<kbd>${esc(y)}</kbd>`).join(" / ")).join(" · ")}</td><td>${esc(w)}</td></tr>`).join("")}</tbody></table>`).join("");
}

/** #176: Lizenzen und Quellen aller fremden Bestandteile, gruppiert; #206: GitHub-Repository, Vertrauenssignale, eigene Durchsicht */
const LIC_MARKS = [["checked", "geprüft", "Code/Projekt angesehen und als vertrauenswürdig eingestuft"],
  ["followed", "gefolgt", "Dem Projekt bzw. Entwickler auf GitHub gefolgt (Stern/Folgen)"],
  ["thanked", "bedankt", "Mitteilung gesendet, dass TagStudio den Code verwendet"]];
function licAge(d) {
  if (!d) return "";
  const days = Math.round((Date.now() - new Date(d + "T00:00:00").getTime()) / 864e5);
  return days < 0 ? d : days < 60 ? `vor ${days} Tagen` : days < 730 ? `vor ${Math.round(days / 30)} Monaten` : `vor ${Math.round(days / 365)} Jahren`;
}
function licStars(n) { return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(".", ",") + " k" : String(n); }
function licRepoCell(it, review) {
  if (!it.repo) return '<span class="muted">–</span>';
  const [owner] = it.repo.split("/"), ri = it.repo_info || {}, rv = review[it.id] || {};
  const warn = ri.archived ? '<span class="lic-warn" title="Das Repository ist archiviert und wird nicht mehr gepflegt">archiviert</span>'
    : ri.pushed && (Date.now() - new Date(ri.pushed).getTime()) > 730 * 864e5 ? '<span class="lic-warn" title="Seit über zwei Jahren keine Änderungen">still</span>' : "";
  const sig = ri.pushed ? `<div class="muted sm">★ ${licStars(ri.stars || 0)} · zuletzt ${esc(licAge(ri.pushed))}${ri.owner_type === "Organization" ? " · Organisation" : ""} ${warn}</div>`
    : '<div class="faint sm">Signale nach der nächsten Prüfung</div>';
  return `<a href="#" data-url="https://github.com/${esc(it.repo)}">${esc(it.repo)} ↗</a>${sig}
    <div class="lic-acts sm"><a href="#" data-url="https://github.com/${esc(owner)}" title="Profil von ${esc(owner)} – dort „Follow“">Entwickler ↗</a>
      · <a href="#" data-licthanks="${esc(it.id)}" title="Vorbereitete Mitteilung, dass TagStudio diesen Code verwendet">Danke …</a></div>
    <div class="lic-marks">${LIC_MARKS.map(([k, l, t]) => `<label title="${esc(t)}${rv[k] ? " – " + esc(rv[k]) : ""}"><input type="checkbox" data-licmark="${esc(it.id)}" data-key="${k}" ${rv[k] ? "checked" : ""}> ${l}</label>`).join("")}</div>`;
}
function helpLicensesHtml(d) {
  if (!d.found) return '<div class="tg-empty">Liste der Fremdkomponenten nicht gefunden (docs/third-party.json).</div>';
  HELP.lic = d;
  const link = (url, txt) => (url && /^https?:/.test(url) ? `<a href="#" data-url="${esc(url)}">${esc(txt)} ↗</a>` : esc(txt));
  const groups = Object.keys(d.groups).filter((g) => d.items.some((it) => it.group === g));
  const review = d.review || {}, repos = d.items.filter((it) => it.repo && it.group !== "app");
  const done = (k) => repos.filter((it) => (review[it.id] || {})[k]).length;
  return `<h2>Lizenzen und Quellen</h2>
    <p class="muted">TagStudio ist freie Software unter der GNU General Public License v3 (oder neuer). Hier stehen alle fremden
    Bibliotheken, Werkzeuge, Online-Dienste und Vorlagen mit Lizenz und Quelle. Die Liste wird monatlich automatisch auf neue
    Versionen und geänderte Lizenzen geprüft; „Geprüft“ zeigt den zuletzt durchgesehenen Stand.</p>
    <p class="muted sm">GitHub: ${repos.length} Projekte · von dir geprüft ${done("checked")}, gefolgt ${done("followed")}, bedankt ${done("thanked")}.
    Sterne und letzte Änderung helfen bei der Einschätzung – archivierte oder lange stille Projekte sind markiert. Deine Häkchen bleiben nur auf diesem Gerät.</p>`
    + groups.map((g) => `<h3>${esc(d.groups[g])}</h3><table class="help-t help-lic"><colgroup><col class="c-name"><col class="c-use"><col class="c-lic"><col class="c-gh"><col class="c-chk"></colgroup><thead><tr><th>Komponente</th><th>Verwendung</th><th>Lizenz</th><th>GitHub</th><th>Geprüft</th></tr></thead><tbody>${
      d.items.filter((it) => it.group === g).map((it) => `<tr><td>${link(it.url, it.name)}</td><td>${esc(it.use || "")}</td><td>${link(it.license_url, it.license || "–")}</td><td class="lic-gh">${it.group === "app" ? (it.repo ? link("https://github.com/" + it.repo, it.repo) : "–") : licRepoCell(it, review)}</td><td class="muted sm">${
        it.checked ? esc(`${it.checked.version || ""}${it.checked.date ? " · " + it.checked.date : ""}`) : it.check ? "ausstehend" : "–"}</td></tr>`).join("")}</tbody></table>`).join("");
}

/** #206: Danke-Text auf Deutsch oder Englisch – mit der Bitte um Rückmeldung, falls die Nutzung nicht passt */
function licThanksText(it, lang) {
  const who = it.repo.split("/")[0], proj = "https://github.com/MarkusKeller8200/markussxch-tagstudio";
  const lic = it.license ? (lang === "en" ? ` (${it.license})` : ` (${it.license})`) : "";
  if (lang === "en") {
    return `Hi ${who},\n\nI'd like to say thank you: my open-source project MarKusSXCH TagStudio (MP3 tagger and DJ tool, GPL-3.0) `
      + `uses ${it.name}${lic}${it.use ? ` – ${it.use}` : ""}.\n\nProject: ${proj}\n`
      + `License and source are credited in the app under Help › Licenses (docs/third-party.json).\n\n`
      + `If this use conflicts with your license or your wishes, or if you would like your code removed from this project, `
      + `please let me know so that I can comply accordingly.\n\nThank you very much for your work!`;
  }
  // Du-Form für Einzelpersonen, Ihr-Form für Organisationen (Teams) – nie „Sie“
  const org = (it.repo_info || {}).owner_type === "Organization";
  const [dich, deiner, deinen, deine] = org ? ["euch", "eurer", "euren", "eure"] : ["dich", "deiner", "deinen", "deine"];
  return `Hallo ${who},\n\nich möchte mich bei ${dich} bedanken: Mein Open-Source-Projekt MarKusSXCH TagStudio (MP3-Tagger und DJ-Werkzeug, GPL-3.0) `
    + `verwendet ${it.name}${lic}${it.use ? ` – ${it.use}` : ""}.\n\nProjekt: ${proj}\n`
    + `Lizenzangabe und Quelle stehen in der Hilfe unter „Lizenzen“ (docs/third-party.json).\n\n`
    + `Sollte die Nutzung des Codes ${deiner} Lizenz oder ${deinen} Wünschen widersprechen oder soll er aus diesem Projekt entfernt werden, `
    + `bitte ich ${dich} um eine entsprechende Rückmeldung, damit ich dem Folge leisten kann.\n\nVielen Dank für ${deine} Arbeit!`;
}
async function licThanks(id) {
  const it = (HELP.lic?.items || []).find((x) => x.id === id);
  if (!it || !it.repo) return;
  const ri = it.repo_info || {}, base = `https://github.com/${it.repo}`;
  const title = `Danke – ${it.name} wird in TagStudio verwendet`;
  const where = ri.discussions ? `${base}/discussions/new?category=show-and-tell&title=${encodeURIComponent(title)}`
    : `${base}/issues/new?title=${encodeURIComponent(title)}`;
  const r = await modal({
    title: `Danke an ${it.repo}`,
    html: `<p class="muted sm">Text anpassen, kopieren und auf GitHub einfügen. TagStudio sendet nichts selbst.
      ${ri.discussions ? "Das Projekt hat Diskussionen – dort ist ein Danke am besten aufgehoben (Kategorie „Show and tell“, falls vorhanden)."
        : "Das Projekt hat keine Diskussionen – du kannst ein Issue eröffnen oder dem Entwickler über sein Profil schreiben (manche nennen dort E-Mail oder Mastodon)."}</p>
      <div class="lic-lang" role="radiogroup" aria-label="Sprache">
        <label><input type="radio" name="licLang" value="en" checked> Englisch</label>
        <label><input type="radio" name="licLang" value="de"> Deutsch</label></div>
      <textarea id="licThanksTxt" class="inp" rows="12" style="width:100%">${esc(licThanksText(it, "en"))}</textarea>`,
    onMount: (b) => b.addEventListener("change", (e) => {
      if (e.target.name === "licLang") $("#licThanksTxt", b).value = licThanksText(it, e.target.value);
    }),
    buttons: [{ label: "Abbrechen", value: null }, { label: "Kopieren", value: "copy" },
      { label: ri.discussions ? "Kopieren + Diskussion öffnen" : "Kopieren + Issue öffnen", value: "open", primary: true }],
    collect: async (b, v) => {                       // kopieren noch im Klick (Zwischenablage braucht die Benutzeraktion)
      const text = $("#licThanksTxt", b).value;
      try { await navigator.clipboard.writeText(text); toast("Text kopiert."); } catch { toast("Kopieren nicht möglich – Text bitte markieren."); return false; }
      return v;
    },
  });
  if (r === "open") call("open_url", where);
}

async function helpTab(tab) {
  HELP.tab = tab;
  $$("#helpTabs [data-htab]").forEach((b) => { b.classList.toggle("on", b.dataset.htab === tab); b.setAttribute("aria-selected", String(b.dataset.htab === tab)); });
  $("#helpTags").hidden = tab !== "tags";
  $("#helpDoc").hidden = tab === "tags";
  $("#helpDoc").removeAttribute("translate");                       // #219: nur Dokumente bleiben unübersetzt
  if (tab === "tags") return helpLoadTags();
  if (tab === "keys") { $("#helpDoc").innerHTML = helpKeysHtml(); $("#helpDoc").scrollTop = 0; return; }
  $("#helpDoc").classList.toggle("wide", tab === "licenses");          // #206: Tabelle nutzt die ganze Breite
  if (tab === "report") {                                            // #187
    $("#helpDoc").innerHTML = `<h2>Fehler melden, Verbesserung oder neue Funktion vorschlagen</h2>
      <p class="muted">Meldungen landen als Issue im öffentlichen GitHub-Projekt. TagStudio füllt das Formular vor (Version, System,
      Bereich), sucht nach ähnlichen Meldungen und schwärzt private Angaben; abgeschickt wird im Browser mit deinem GitHub-Konto.
      TagStudio speichert keine Zugangsdaten.</p>
      <p class="muted">Jede neue Meldung bekommt das Label <code>triage</code> und wird vom Projektverantwortlichen geprüft. Erst seine
      ausdrückliche Freigabe macht daraus einen Entwicklungsauftrag – eine Meldung allein ist keine Zusage.</p>
      <p class="muted">Je nach Art kommt die Meldung in einen eigenen Meilenstein: Fehler → Fehler, Verbesserung
      (bestehende Funktion besser machen) → Verbesserungen, neue Funktion → Funktionen. Eigene Übersetzungen (Einstellungen ›
      Darstellung › Sprache) lassen sich als Vorschlag einreichen – sie kommen nach Prüfung in die mitgelieferten Texte.</p>
      <div class="svc-btns"><button class="primary" data-fbopen="bug">Fehler melden …</button><button class="ghost" data-fbopen="improvement">Verbesserung vorschlagen …</button><button class="ghost" data-fbopen="feature">Neue Funktion vorschlagen …</button><button class="ghost" data-fbopen="translation">Übersetzung einreichen …</button>
      <a href="#" data-url="https://github.com/MarkusKeller8200/markussxch-tagstudio/issues">Alle Meldungen ansehen ↗</a></div>`;
    $("#helpDoc").scrollTop = 0; return;
  }
  if (tab === "licenses") { $("#helpDoc").innerHTML = helpLicensesHtml(await call("help_licenses")); $("#helpDoc").scrollTop = 0; return; }
  const lang = (typeof I18N !== "undefined" && I18N.lang) || "de-CH";
  if (!HELP.docs || HELP.docsLang !== lang) { HELP.docs = await call("help_docs", lang); HELP.docsLang = lang; }
  const d = HELP.docs[tab];
  // Dokumente sind ganze Texte in ihrer Sprache (englische Fassung oder Deutsch) – nicht Wort für Wort übersetzen
  if (d && d.text) $("#helpDoc").setAttribute("translate", "no");
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
function helpGroupShort(t) { t = typeof tr === "function" ? tr(t) : t; return t.length > 34 ? t.slice(0, 32).replace(/[\s,]+\S*$/, "") + " …" : t; }   // #157: erst übersetzen, dann kürzen

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
  $("#helpDoc").addEventListener("change", async (e) => {
    const c = e.target.closest("[data-licmark]"); if (!c) return;
    try {
      const r = await call("help_lic_mark", c.dataset.licmark, c.dataset.key, c.checked);
      HELP.lic.review = r.review; const top = $("#helpDoc").scrollTop;
      $("#helpDoc").innerHTML = helpLicensesHtml(HELP.lic); $("#helpDoc").scrollTop = top;
    } catch (ex) { c.checked = !c.checked; toast(String(ex.message || ex)); }
  });
  $("#helpDoc").addEventListener("click", (e) => {
    const a = e.target.closest("a[data-url]"); if (a) { e.preventDefault(); call("open_url", a.dataset.url); return; }
    const fo = e.target.closest("[data-fbopen]"); if (fo) { fbOpen(fo.dataset.fbopen); return; }
    const th = e.target.closest("a[data-licthanks]"); if (th) { e.preventDefault(); licThanks(th.dataset.licthanks); return; }
    const t = e.target.closest("a[data-htab-link]"); if (t) { e.preventDefault(); helpTab(t.dataset.htabLink); }
  });
})();
