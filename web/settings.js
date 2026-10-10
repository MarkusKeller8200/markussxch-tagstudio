/* MarKusSXCH TagStudio – Seite „Einstellungen“ (#21): alle Optionen an einem Ort, Export/Import, Zurücksetzen.
   Gespeichert wird sofort über die jeweiligen Sitzungs-Aufrufe; Export/Import/Zurücksetzen über appsettings.py. */
"use strict";

const ST = { data: null };

const stSel = (id, opts, cur) => `<select class="inp" id="${id}">${opts.map(([v, l]) => `<option value="${esc(String(v))}"${String(v) === String(cur) ? " selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
const stCheck = (id, on, label) => `<label class="check"><input type="checkbox" id="${id}"${on ? " checked" : ""}${id === "stPlDeck2" && ST.data && ST.data.player.layout !== "top" ? " disabled" : ""}> ${esc(label)}</label>`;

async function settingsShow() {
  const d = ST.data = await call("settings_page");
  const f = d.file;
  $("#stFile").textContent = `Datei: ${f.path}${f.exists ? "" : " (noch nicht angelegt)"} · Sicherungen vor Import/Zurücksetzen: ${f.backup_dir}`;
  const p = d.player;
  const vd = d.view_defaults || { compare: {}, tagger: {} }, cd = vd.compare, td = vd.tagger;
  $("#stGrid").innerHTML = `
    <section class="card" id="stLookCard"><h3>Darstellung</h3>
      <div class="st-row"><span>Design</span>
        <div class="seg" id="stTheme"><button data-v="dark"${d.theme !== "light" ? ' class="on"' : ""}>Dunkel</button><button data-v="light"${d.theme === "light" ? ' class="on"' : ""}>Hell</button></div>
        <label for="stNotation">Tonart-Schreibweise</label>${stSel("stNotation", d.notations, d.key_notation)}
      </div></section>
    <section class="card" id="stTaggerCard"><h3>Tagger</h3>
      <div class="st-row">${stDefRow("tagger", "Standardordner")}
        <span>Stems</span>${stCheck("stStemsFlat", d.stems_flat, "Stems als eigene Titel anzeigen (statt aufklappbar unter dem Original)")}
        <label for="stFeatScale">Audio-Merkmale in den Dateien</label>${stSel("stFeatScale", d.feat_scales || [[100, "0–100"]], d.feat_scale || 100)}
        <span></span><span class="muted sm">Angezeigt und bearbeitet wird immer 0–100. Bei 0–10 (z. B. Lexicon) rechnet TagStudio beim Lesen ×10 und beim Schreiben ÷10 um.</span>
      </div>
      <h4 class="st-sub">Beim Start</h4>
      <div class="st-row">
        ${stVd("tagger", "start", "Beim Start laden", [["last", "zuletzt geladenen Ordner (mit Markierung, Sortierung, Filter)"], ["default", "Standardordner"], ["none", "nichts"]], td, "zuletzt geladenen Ordner (Standard)")}
        ${stVd("tagger", "recursive", "Unterordner", [[true, "einbeziehen"], [false, "nicht einbeziehen"]], td)}
        ${stVd("tagger", "sort", "Sortierung", (d.tg_sort_cols || []).flatMap(([c, l]) => [[c + ":1", l + " ↑"], [c + ":-1", l + " ↓"]]), td.sort_col ? { sort: td.sort_col + ":" + (td.sort_dir || 1) } : {})}
        ${stVd("tagger", "cover_col", "Cover-Spalte", [[true, "anzeigen"], [false, "ausblenden"]], td)}
        ${stVd("tagger", "src_filter", "Herkunfts-Filter", [["-", "ohne Herkunft"], ...Object.entries(S.settings.origins || {}).filter(([, v]) => v.kind !== "plugin").map(([k, v]) => [k, v.name])], td, "alle Herkünfte")}
      </div></section>
    <section class="card" id="stFixerCard"><h3>Tag-Fixer</h3>
      <p class="muted sm" style="margin:0">Mehrfachwerte, Gross-/Kleinschreibung, Suchen &amp; Ersetzen – die zuletzt benutzten Einstellungen merkt der Tag-Fixer selbst.</p>
      <div><button class="ghost sm" id="stFixerGo" style="width:auto">Zum Tag-Fixer</button></div>
    </section>
    <section class="card" id="stCompareCard"><h3>Vergleich</h3>
      <p class="muted sm" style="margin:0">Standardordner stehen beim Start in den Pfadfeldern; weicht ein Feld ab (z. B. nach einem Snapshot-Vergleich), trägt ⌂ den Standard wieder ein.</p>
      <div class="st-row">${stDefRow("left", "Standard links")}${stDefRow("right", "Standard rechts")}</div>
      <h4 class="st-sub">Beim Start</h4>
      <div class="st-row">
        ${stVd("compare", "recursive", "Unterordner", [[true, "einbeziehen"], [false, "nicht einbeziehen"]], cd)}
        ${stVd("compare", "mode", "Zuordnen nach", d.modes || [], cd)}
        ${stVd("compare", "filter", "Anzeige", [["all", "Alle"], ["diff", "Unterschiede"], ["same", "Gleiche"]], cd)}
        ${stVd("compare", "show_trivial", "Unwichtige", [[true, "anzeigen"], [false, "ausblenden"]], cd)}
        ${stVd("compare", "empty_set", "Leere Felder", d.empty_sets || [], cd)}
        ${stVd("compare", "show_covers", "Cover", [[true, "anzeigen"], [false, "ausblenden"]], cd)}
        <span></span><span class="muted sm">Weicht der Vergleich von den Vorgaben ab, setzt ihn der Knopf ⌂ „Standard“ in der Werkzeugleiste zurück.</span>
      </div></section>
    <section class="card" id="stSnapCard"><h3>Snapshots</h3><div class="st-row" id="stSnapRows"><span class="muted sm">…</span></div></section>
    <section class="card" id="stSaveCard"><h3>Sicherungen und Speichern</h3>
      <div class="st-row">
        <label for="stSaveVer">ID3-Version beim Speichern</label>${stSel("stSaveVer", [[0, "beibehalten (wie die Datei)"], [3, "immer ID3v2.3 (am verträglichsten)"], [4, "immer ID3v2.4"]], d.save_version)}
        <span>Sicherung</span>${stCheck("stBackup", d.backup_enabled, "Vor dem Speichern die bisherigen Tags sichern")}
        <span>Sicherungsordner</span><div class="st-path"><code title="${esc(d.backup_dir)}">${esc(d.backup_dir)}</code><button class="ghost sm" id="stBkFolder">Ändern …</button><button class="ghost sm" id="stBkOpen">Öffnen</button></div>
      </div></section>
    <section class="card" id="stPlayerCard"><h3>Player</h3>
      <div class="st-row">
        <label for="stPlStart">Startpunkt</label>${stSel("stPlStart", [["0", "ab Anfang"], ["30", "ab 30 %"], ["60", "ab 1:00"], ["cue", "ab 1. Cue"]], p.start)}
        <span>Anzeige</span>${stCheck("stPlWave", p.wave, "Wellenform anzeigen (einmal berechnet, im Cache)")}
        <span>Durchhören</span>${stCheck("stPlFollow", p.follow, "Beim Wechsel der Markierung weiterspielen, am Titelende nächster Titel")}
        <span>Wiederholen</span>${stCheck("stPlRepeat", p.repeat, "Titel wiederholen (R)")}
        <span>Live-Vorschau</span>${stCheck("stPlLive", p.live, "Klick auf einen Titel spielt ihn sofort (aus: Doppelklick spielt)")}
        <label for="stPlVol">Lautstärke</label><div class="st-path"><input type="range" id="stPlVol" min="0" max="100" value="${Math.round(p.vol * 100)}" style="width:160px"><span class="muted sm" id="stPlVolV">${Math.round(p.vol * 100)} %</span></div>
        <label for="stPlXf">Überblenden</label><div class="st-path">${stSel("stPlXf", [[0, "aus"], [2, "2 s"], [4, "4 s"], [6, "6 s"], [8, "8 s"], [10, "10 s"], [12, "12 s"]], p.xfade)}
          ${stSel("stPlXfStart", [["start", "nächster Titel ab Startpunkt"], ["0", "nächster Titel ab Anfang"], ["cue", "nächster Titel ab 1. Cue"]], p.xfade_start)}</div>
        <label for="stPlXfAfter">Überblenden wann</label>${stSel("stPlXfAfter", [[0, "am Titelende"], [15, "nach 15 s (Durchhören)"], [30, "nach 30 s"], [45, "nach 45 s"], [60, "nach 1 Minute"], [90, "nach 1:30"], [120, "nach 2 Minuten"]], p.xfade_after)}
        <span>Tempo angleichen</span><div class="st-path">${stCheck("stPlXfSync", p.xfade_sync, "Nächsten Titel beim Überblenden im BPM des laufenden spielen (Tonhöhe bleibt, max. ±10 %)")}</div>
        <label for="stPlXfRet">Zurück auf eigenes BPM</label>${stSel("stPlXfRet", [[0, "sofort nach dem Überblenden"], [4, "in 4 s"], [8, "in 8 s"], [16, "in 16 s"], [30, "in 30 s"], [60, "in 1 Minute"]], p.xfade_return)}
        <span></span><span class="muted sm">Überblenden wirkt im Tagger mit „Durchhören“, nicht bei „Titel wiederholen“ oder einer Schleife.</span>
        <label for="stPlLayout">Position</label>${stSel("stPlLayout", [["bottom", "unten in der Aktionsleiste"], ["top", "oben als eigene Leiste (einklappbar, Shift+P)"]], p.layout)}
        <span>Player B</span><div>${stCheck("stPlDeck2", p.deck2 && p.layout === "top", "Zweiten Player unter Player A anzeigen (Vorhören, eigenes Ausgabegerät)")}${p.layout === "top" ? "" : '<div class="muted sm">Nur mit Position „oben“ verfügbar.</div>'}</div>
        <span>Fortsetzen</span>${stCheck("stPlResume", p.resume !== false, "Beim Start den zuletzt geladenen Titel an derselben Stelle laden")}
        <label for="stPlResumePlay">Nach dem Neustart</label>${stSel("stPlResumePlay", [["pause", "in Pause laden"], ["play", "sofort abspielen (Autoplay)"], ["was", "abspielen, wenn er beim Schliessen lief"]], p.resume_play || "pause")}
        <label for="stPlStartmode">Nach dem Start</label>${stSel("stPlStartmode", [["last", "zuletzt benutzte Einstellungen"], ["default", "immer die Standard-Einstellungen"]], p.startmode)}
        <span>Standard</span><div class="st-path"><button class="ghost sm" id="stPlDefSave" title="Die Einstellungen oben als Standard für den Start merken">Aktuelle als Standard speichern</button><button class="ghost sm" id="stPlDefApply" ${p.has_defaults ? "" : "disabled"} title="Player jetzt auf den gespeicherten Standard setzen">Auf Standard zurücksetzen</button><button class="ghost sm" id="stPlDefDel" ${p.has_defaults ? "" : "disabled"}>Standard löschen</button></div>
        <span></span><span class="muted sm">${p.has_defaults ? "Ein Standard ist gespeichert." : "Noch kein Standard gespeichert – „Aktuelle als Standard speichern“ merkt die Einstellungen oben."}</span>
        <span>Externe Player</span><div class="st-path"><span>${d.players ? `${d.players} eingerichtet` : "keiner – Standardprogramm des Systems"}</span><button class="ghost sm" id="stPlayers">Einrichten …</button></div>
      </div></section>
    <section class="card" id="stPluginCard"><h3>Plugins</h3>
      <p class="muted sm" style="margin:0">Plugins ein-/ausschalten, Pakete installieren und Optionen festlegen – auf der Seite „Plugins“.</p>
      <div><button class="ghost sm" id="stPlugins" style="width:auto">Zur Plugin-Seite</button></div>
    </section>
    <section class="card" id="stOriginCard" hidden></section>
    <section class="card" id="stTrivCard"><h3>Unwichtige Felder</h3>
      <p class="muted sm" style="margin:0">Felder, die sich zwischen Dateien fast immer unterscheiden (Analyse-Daten, Kodierer …). Im Vergleich lassen sie sich ausblenden und zählen nicht als Unterschied. Muster mit <code>*</code>, z. B. <code>TXXX:MusicBrainz*</code> oder <code>GEOB:*</code>.</p>
      <div class="st-chips" id="stTriv"></div>
      <div class="st-add"><input class="inp" id="stTrivIn" placeholder="Muster hinzufügen, z. B. TXXX:Serato*" spellcheck="false"><button class="ghost sm" id="stTrivAdd">Hinzufügen</button><button class="ghost sm" id="stTrivDef" title="Standardliste wiederherstellen">Standard</button></div>
    </section>
    <section class="card" id="stCache"><h3>Cache</h3><div class="st-row" id="stCacheRows"><span class="muted sm">…</span></div></section>
    <section class="card" id="stUpdateCard"><h3>Updates</h3>
      <div class="st-row">
        <span>Installiert</span><span>Version ${esc(d.version)}${/-/.test(d.version) ? ' <span class="beta-b">Beta</span>' : ""}</span>
        <label for="stUpdCh">Updates anbieten</label>${stSel("stUpdCh", [["stable", "nur offizielle Versionen"], ["beta", "auch Beta-Versionen (zum Testen)"]], d.update_channel)}
        <span></span><span class="muted sm">${d.update_channel === "stable" && /-/.test(d.version) ? "Du verwendest eine Beta – die nächste offizielle Version wird angeboten, sobald sie erscheint." : "Beta-Versionen erscheinen nur, solange eine neue Version in Arbeit ist."}</span>
        <span></span><div class="st-path"><button class="ghost sm" id="stUpdCheck">Jetzt nach Updates suchen</button><button class="ghost sm" id="stUpdNotes">Versionshinweise</button></div>
      </div></section>`;
  stToc();
  stTrivRender();
  stCacheRender();
  stSnapRender();
  if (typeof originSettingsRender === "function") await originSettingsRender($("#stOriginCard"));
  stToc();
}

/** #84: Zeile „Standardordner“ */
/** #85/#86: Vorgabe beim Start – erste Option „wie zuletzt benutzt“ (keine Vorgabe) */
function stVd(area, key, label, options, cur, none = "wie zuletzt benutzt") {
  const has = Object.prototype.hasOwnProperty.call(cur, key), v = has ? JSON.stringify(cur[key]) : "";
  const id = `stVd_${area}_${key}`;
  return `<label for="${id}">${esc(label)}</label><select class="inp" id="${id}" data-vd="${area}:${key}">
    <option value=""${has ? "" : " selected"}>${esc(none)}</option>
    ${options.map(([val, l]) => { const j = JSON.stringify(val); return `<option value="${esc(j)}"${j === v ? " selected" : ""}>${esc(l)}</option>`; }).join("")}</select>`;
}

async function stVdSet(sel) {
  const [area, key] = sel.dataset.vd.split(":"), raw = sel.value;
  let r;
  if (key === "sort") {
    const [col, dir] = raw ? JSON.parse(raw).split(":") : [null, null];
    await call("set_view_default", area, "sort_col", col);
    r = await call("set_view_default", area, "sort_dir", dir === null ? null : +dir);
  } else r = await call("set_view_default", area, key, raw ? JSON.parse(raw) : null);
  S.settings.view_defaults = r;
  if (typeof TG !== "undefined" && TG.settings) TG.settings.defaults = r.tagger;
  if (typeof cmpHomeSync === "function") cmpHomeSync();
  toast(raw ? "Vorgabe gespeichert – gilt ab dem nächsten Start." : "Keine Vorgabe – wie zuletzt benutzt.");
}

/** #87: Sprungmarken zu den Karten */
function stToc() {
  const box = $("#stToc");
  if (!box) return;
  box.innerHTML = $$("#stGrid > .card").filter((c) => !c.hidden && $("h3", c)).map((c) => `<button class="chip" data-goto="${c.id}">${esc($("h3", c).textContent)}</button>`).join("");
}

function stDefRow(k, label) {
  const v = (S.settings.defaults || {})[k] || "";
  return `<label for="stDef_${k}">${esc(label)}</label><div class="st-path"><input class="inp" id="stDef_${k}" data-defdir="${k}" value="${esc(v)}" placeholder="kein Standard – letzter Pfad wird verwendet" spellcheck="false">
    <button class="ghost sm" data-defpick="${k}" title="Ordner wählen">…</button><button class="ghost sm" data-defclear="${k}" ${v ? "" : "disabled"} title="Kein Standardordner">✕</button></div>`;
}
async function stDefSet(k, v) {
  const r = await call("set_default_dir", k, v);
  if (!r.ok) { info("Nicht möglich", r.error); return; }
  S.settings.defaults = r.defaults;
  if (typeof homeSync === "function") homeSync();
  toast(v ? "Standardordner gespeichert." : "Kein Standardordner mehr.");
  settingsShow();
}

async function stSnapRender() {
  const o = await call("snap_overview"), s = o.settings;
  $("#stSnapRows").innerHTML = `<span>Automatik</span>${stCheck("snDaily", s.snap_daily, "Täglich einen Snapshot je überwachtem Ordner (beim ersten Start des Tages)")}
    <span>Beim Start</span>${stCheck("snAsk", s.snap_ask, "Fragen, ob ein weiterer Snapshot erstellt bzw. das Journal angezeigt werden soll")}
    <span></span>${stCheck("snHint", s.snap_hint, "Hinweis, solange noch kein Ordner überwacht wird")}
    <label for="snKeep">Aufbewahrung</label><div class="st-path"><input class="inp" type="number" min="1" max="500" id="snKeep" value="${s.snap_keep}" style="width:80px"><span>automatische behalten, danach je einer pro Woche für</span><input class="inp" type="number" min="0" max="520" id="snWeeks" value="${s.snap_weeks}" style="width:80px"><span>Wochen</span></div>
    <label for="snWatch">Überwachung</label><div class="st-path"><span>Während TagStudio läuft alle</span><input class="inp" type="number" min="0" max="240" id="snWatch" value="${s.snap_watch}" style="width:70px"><span>Minuten auf fremde Änderungen prüfen (0 = aus)</span></div>
    <span>Gründlich</span>${stCheck("snThorough", s.snap_thorough, "Alle Dateien lesen (auch wenn Grösse und Änderungszeit gleich sind) – langsamer")}
    <span>Speicherort</span><div class="st-path"><code title="${esc(o.dir)}">${esc(o.dir)}</code><button class="ghost sm" data-copen="${esc(o.dir)}">Öffnen</button><button class="ghost sm" id="snMove" title="Ganzen Speicher an einen anderen Ort verschieben (z. B. in den MP3-Ordner, um ihn weiterzugeben)">Ändern …</button>${o.default ? "" : '<button class="ghost sm" id="snMoveDefault" title="Zurück in den TagStudio-Ordner verschieben">Standard</button>'}</div>
    ${o.readonly ? '<span></span><div class="hint warn">Dieser Speicher stammt aus einer neueren TagStudio-Version und wird nur gelesen – bitte TagStudio aktualisieren.</div>' : ""}
    <span>Belegt</span><div class="st-path"><span>${snMB(o.total)} · ${o.libs.length} überwachte(r) Ordner</span><button class="ghost sm" id="stSnapGo">Zur Seite „Snapshots“</button></div>`;
}

/** #80: Cache für alle geladenen Titel (neu) erstellen – jetzt (mit Fortschritt) oder im Hintergrund */
async function stCacheBuild(k) {
  const what = { lists: "Listen-Cache", wave: "Wellenformen", covers: "Cover-Vorschauen" }[k];
  const how = await dialog({ title: `${what} erstellen`,
    text: "Erstellt wird für alle im Tagger und Vergleich geladenen Titel. Das kann bei grossen Bibliotheken dauern – im Hintergrund kannst du derweil weiterarbeiten.",
    buttons: [{ label: "Abbrechen", value: null }, { label: "Jetzt", value: "now" }, { label: "Im Hintergrund", value: "bg", primary: true }] });
  if (!how) return;
  if (k === "wave") return waveBuildAll(how === "bg");
  if (how === "bg") {
    const r = await call("start_cache_build", k, true);
    if (!r.ok) return info("Nicht möglich", r.error);
    toast(`${what}: läuft als Hintergrund-Auftrag (Fortschritt unten links).`);
    if (typeof jobsPoll === "function") jobsPoll();
    return;
  }
  const r = await runTask(call("start_cache_build", k, false), `${what} erstellen`);
  if (r && !r.cancelled) status(r.message, r.tone || "ok");
}

/** Wellenformen im Browser berechnen (Web Audio). bg: ohne Fenster – Fortschritt in der Fußleiste, Klick bricht ab. */
const WAVEBG = { run: false, stop: false };
async function waveBuildAll(bg = false) {
  if (WAVEBG.run) { toast("Wellenformen werden bereits erstellt."); return; }
  const list = await call("wave_missing");
  if (!list.length) { toast("Alle geladenen Titel haben schon eine Wellenform (oder es ist nichts geladen)."); return; }
  const ov = $("#progress"), bar = $("#progBar"), cancelBtn = $("#progCancel"), chip = $("#waveChip");
  WAVEBG.run = true; WAVEBG.stop = false;
  if (bg) {
    chip.hidden = false;
    chip.onclick = () => { WAVEBG.stop = true; chip.title = "wird abgebrochen …"; };
  } else {
    $("#progTitle").textContent = "Wellenformen erstellen";
    bar.classList.remove("indet");
    cancelBtn.hidden = false;
    cancelBtn.onclick = () => { WAVEBG.stop = true; };
    ov.hidden = false;
  }
  let done = 0;
  for (const x of list) {
    if (WAVEBG.stop) break;
    if (bg) { $("#wcText").textContent = `Wellenformen ${done + 1} / ${list.length}`; chip.title = `${x.name}\nKlick: abbrechen`; $(".jc-ring", chip).style.setProperty("--p", Math.round(done / list.length * 100)); }
    else { $("#progText").textContent = `${done + 1} / ${list.length} · ${x.name}`; bar.style.width = (done / list.length * 100) + "%"; }
    await plWaveCompute({ wave_key: x.key, url: x.url });
    done++;
  }
  if (bg) chip.hidden = true; else { ov.hidden = true; cancelBtn.onclick = null; }
  WAVEBG.run = false;
  const msg = WAVEBG.stop ? `Wellenformen: ${done} von ${list.length} erstellt (abgebrochen).` : `Wellenformen erstellt: ${done} Titel.`;
  status(msg, WAVEBG.stop ? "warn" : "ok");
  if (bg) toast(msg);
  if (S.module === "settings") stCacheRender();
}

async function stCacheRender(info) {
  const c = info || await call("cache_info");
  const mb = (b) => (b < 1048576 ? `${Math.round(b / 1024)} KB` : `${(b / 1048576).toFixed(1).replace(".", ",")} MB`);
  const row = (k, label) => `<span>${label}</span><div class="st-path"><span>${fmtN(c[k].count)} Datei(en) · ${mb(c[k].bytes)}</span>
    <button class="ghost sm" data-cbuild="${k}" title="Für alle geladenen Titel (Tagger und Vergleich) neu erstellen">Erstellen</button><button class="ghost sm" data-cclear="${k}" ${c[k].count ? "" : "disabled"}>Leeren</button><button class="ghost sm" data-copen="${esc(c[k].dir)}">Ordner</button></div>`;
  $("#stCacheRows").innerHTML = `<span>Listen-Cache</span>${stCheck("stListCache", c.lists.on, "Tagger und Vergleich sofort aus dem Cache anzeigen, danach im Hintergrund über einen Hash je Titel auf Änderungen prüfen")}`
    + row("lists", "Listen") + row("wave", "Wellenformen") + row("covers", "Cover-Vorschauen");
}

function stTrivRender() {
  const d = ST.data, def = new Set(d.trivial_default);
  $("#stTriv").innerHTML = d.trivial.length
    ? d.trivial.map((t, k) => `<span class="st-chip${def.has(t) ? " def" : ""}" title="${def.has(t) ? "Standard" : "eigenes Muster"}">${esc(t)}<button data-k="${k}" aria-label="${esc(t)} entfernen">✕</button></span>`).join("")
    : '<span class="muted sm">Keine – alle Felder zählen.</span>';
}

async function stTrivSet(list) {
  ST.data.trivial = await call("set_trivial", list);
  stTrivRender();
  if (S.pairs && S.pairs.length) refreshAll(await call("state"));
}

async function stTransfer(kind) {
  if (kind === "export") {
    if (S.settings.native) {
      const r = await call("settings_export");
      if (r.ok) toast("Einstellungen exportiert: " + r.path); else if (!r.cancelled) info("Export fehlgeschlagen", r.error);
    } else {
      const text = await call("settings_export_text");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
      a.download = `TagStudio-Einstellungen-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast("Einstellungen als Download gespeichert.");
    }
    return;
  }
  if (S.settings.native) {
    const r = await call("settings_import_pick");
    if (r && r.error) return info("Import nicht möglich", r.error);
    if (r) stImportText(r.text, r.name);
  } else {
    const inp = $("#stFileIn");
    inp.value = "";
    inp.onchange = async () => { const f = inp.files[0]; if (f) stImportText(await f.text(), f.name); };
    inp.click();
  }
}

async function stImportText(text, name) {
  const pv = await call("settings_import_preview", text);
  if (!pv.ok) return info("Import nicht möglich", pv.error);
  if (!pv.groups.length) return info("Nichts zu importieren", "Die Datei enthält keine bekannten Einstellungen.");
  const from = [pv.app_version && `TagStudio ${pv.app_version}`, pv.platform && { win32: "Windows", darwin: "macOS", linux: "Linux" }[pv.platform] || pv.platform, pv.exported && pv.exported.replace("T", " ")].filter(Boolean).join(" · ");
  const groups = await modal({
    title: "Einstellungen importieren",
    html: `<div class="hint">${esc(name || "Datei")}${from ? " – " + esc(from) : ""}</div>
      ${pv.foreign ? '<div class="hint" style="margin-top:6px">Von einem anderen System: Pfade (Verlauf, Sicherungsordner, Player) sind nicht vorgewählt.</div>' : ""}
      <div class="st-groups">${pv.groups.map((g) => `<label class="check"><input type="checkbox" value="${esc(g.id)}"${g.default ? " checked" : ""}> ${esc(g.label)}<span class="n">${g.changed ? `${g.changed} geändert` : "gleich"}</span></label>`).join("")}</div>
      <div class="muted sm" style="margin-top:10px">Die bisherige Einstellungsdatei wird vorher gesichert. Danach lädt die Oberfläche neu.</div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Importieren", value: true, primary: true }],
    collect: (b) => $$(".st-groups input:checked", b).map((x) => x.value),
  });
  if (!groups) return;
  if (!groups.length) return toast("Nichts gewählt.");
  if (!(await confirmDiscard())) return;
  const r = await call("settings_import", text, groups);
  if (!r.ok) return info("Import fehlgeschlagen", r.error);
  toast(`${r.keys} Einstellung(en) übernommen.`);
  setTimeout(() => location.reload(), 600);
}

async function stReset() {
  const groups = await modal({
    title: "Einstellungen zurücksetzen",
    html: `<div class="hint">Gewählte Bereiche gehen auf den Auslieferungszustand zurück. Die bisherige Datei wird vorher gesichert.</div>
      <div class="st-groups">${ST.data.groups.map(([id, label]) => `<label class="check"><input type="checkbox" value="${esc(id)}"${id === "layout" ? " checked" : ""}> ${esc(label)}</label>`).join("")}
      <label class="check" style="margin-top:6px"><input type="checkbox" value="all" id="stAll"> <b>Alles zurücksetzen</b></label></div>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Zurücksetzen", value: true, primary: true }],
    onMount: (b) => $("#stAll", b).addEventListener("change", (e) => $$(".st-groups input:not(#stAll)", b).forEach((x) => { x.disabled = e.target.checked; })),
    collect: (b) => ($("#stAll", b).checked ? "all" : $$(".st-groups input:checked", b).map((x) => x.value)),
  });
  if (!groups || (Array.isArray(groups) && !groups.length)) return;
  if (!(await confirmDiscard())) return;
  const r = await call("settings_reset", groups);
  if (!r.ok) return info("Zurücksetzen fehlgeschlagen", r.error);
  if (groups === "all" || groups.includes("player") || groups.includes("layout")) { try { Object.keys(localStorage).filter((k) => k.startsWith("ts_")).forEach((k) => localStorage.removeItem(k)); } catch (e) { /* egal */ } }
  toast("Zurückgesetzt – die bisherige Datei liegt im Sicherungsordner.");
  setTimeout(() => location.reload(), 600);
}

// ---------------------------------------------------------------------- Herkunft der Tags (#22)
async function originSettingsRender(card) {
  const o = await call("tag_origins");
  S.settings.origins = o.catalog;
  ST.origins = o.custom.length ? o.custom.map((r) => ({ ...r })) : [];
  const cat = o.catalog, rank = (k) => (cat[k].kind === "id3" ? 0 : cat[k].kind === "unknown" ? 1 : 2);
  const ids = Object.keys(cat).sort((a, b) => rank(a) - rank(b) || cat[a].name.localeCompare(cat[b].name));
  const nOwn = ids.filter((k) => cat[k].custom_label).length;
  const triv = new Set(ST.data.trivial.map((t) => t.toLowerCase()));
  card.hidden = false;
  card.innerHTML = `<h3>Herkunft der Tags</h3>
    <p class="muted sm" style="margin:0">TagStudio zeigt bei „Weitere Felder“ und im Vergleich, welche Anwendung ein Feld geschrieben hat. Eigene Zuordnungen gehen vor der eingebauten Liste.</p>
    ${stCheck("orVer", o.ver_badge, "ID3-Version (v2.3/v2.4) bei offiziellen Feldern zeigen – zusammen mit der Herkunft; benutzerdefinierte Felder (TXXX, GEOB, PRIV …) ohne bekannte Herkunft heissen „unbekannt“")}
    <div class="or-list" id="orList"></div>
    <div><button class="ghost sm" id="orAdd" style="width:auto">+ Zuordnung</button> <button class="primary sm" id="orSave" style="width:auto" hidden>Zuordnungen speichern</button></div>
    <details class="or-all" ${ST.orOpen ? "open" : ""}><summary>Kennzeichen und bekannte Herkünfte (${ids.length})${nOwn ? ` · ${nOwn} eigene` : ""}</summary>
      <p class="muted sm" style="margin:6px 0">Text und Farbe jedes Kennzeichens lassen sich anpassen (#75); ↺ setzt auf den Standard zurück.
        ${nOwn ? '<button class="ghost sm" id="orLabReset" style="width:auto">Alle Kennzeichen zurücksetzen</button>' : ""}</p>
      ${ids.map((k) => { const v = cat[k], all = v.patterns.length && v.patterns.every((p) => triv.has(p.toLowerCase()));
        return `<div class="or-src" data-sid="${esc(k)}"><span class="prev">${srcBadge(k)}</span><div class="d"><b>${esc(v.name)}</b> – ${esc(v.desc)}${v.patterns.length ? `<br><code>${esc(v.patterns.join("  ·  "))}</code>` : ""}</div>
        <span class="lab"><input type="text" class="or-short" maxlength="16" value="${esc(v.custom_label ? v.short : "")}" placeholder="${esc(v.short_default)}" aria-label="Kennzeichen für ${esc(v.name)}" title="Eigener Text des Kennzeichens">
          <input type="color" class="or-hue" value="${hueHex(v.hue ?? srcHue(k))}" aria-label="Farbe für ${esc(v.name)}" title="Farbe des Kennzeichens">
          <button class="ghost sm" data-orreset="${esc(k)}" ${v.custom_label ? "" : "disabled"} title="Auf Standard zurücksetzen">↺</button></span>
        ${v.patterns.length ? `<button class="ghost sm" data-triv="${esc(k)}" ${all ? "disabled" : ""} title="Muster dieser Herkunft zu den unwichtigen Feldern hinzufügen">${all ? "unwichtig ✓" : "als unwichtig"}</button>` : ""}</div>`; }).join("")}
    </details>`;
  $("details.or-all", card).addEventListener("toggle", (e) => { ST.orOpen = e.target.open; });
  orRender();
}

/** Farbton ↔ Farbe für die Farbwahl (#75) */
function hueHex(h) {
  const f = (n) => { const k = (n + h / 30) % 12, a = 0.6 * Math.min(0.5, 1 - 0.5); const c = 0.5 - a * Math.max(-1, Math.min(k - 3, 9 - k, 1)); return Math.round(c * 255).toString(16).padStart(2, "0"); };
  return `#${f(0)}${f(8)}${f(4)}`;
}
function hexHue(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255, g = parseInt(hex.slice(3, 5), 16) / 255, b = parseInt(hex.slice(5, 7), 16) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  if (!d) return 0;
  const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return Math.round((h * 60 + 360) % 360);
}

/** #75: eigenes Kennzeichen speichern und überall neu zeichnen */
async function orLabelSet(sid, short, hue) {
  const o = await call("set_origin_label", sid, short, hue);
  S.settings.origins = o.catalog;
  originSettingsRender($("#stOriginCard"));
  if (S.pairs && S.pairs.length) refreshAll(await call("state"));
  if (typeof TG !== "undefined" && TG.detail && typeof renderTgEditor === "function") renderTgEditor();
}

function orRender() {
  $("#orList").innerHTML = ST.origins.length
    ? `<div class="or-row or-head"><span class="muted sm">Feld-Muster</span><span class="muted sm">Herkunft</span><span></span></div>` + ST.origins.map((r, k) => `<div class="or-row" data-k="${k}">
        <input class="pat" value="${esc(r.pattern)}" placeholder="z. B. TXXX:VDJ*" spellcheck="false" aria-label="Feld-Muster">
        <input class="src" value="${esc(r.source)}" placeholder="z. B. VirtualDJ" aria-label="Herkunft" list="orNames">
        <button class="x" data-ordel="${k}" title="Entfernen" aria-label="Entfernen">✕</button></div>`).join("")
      + `<datalist id="orNames">${Object.values(S.settings.origins || {}).filter((v) => v.kind !== "plugin").map((v) => `<option value="${esc(v.name)}">`).join("")}</datalist>`
    : '<span class="muted sm">Keine eigenen Zuordnungen.</span>';
}

function orRead() {
  return $$("#orList .or-row[data-k]").map((r) => ({ pattern: $(".pat", r).value.trim(), source: $(".src", r).value.trim() }));
}

function initSettings() {
  $("#stExport").addEventListener("click", () => stTransfer("export"));
  $("#stImport").addEventListener("click", () => stTransfer("import"));
  $("#stReset").addEventListener("click", () => stReset());
  $("#stToc").addEventListener("click", (e) => {                         // #87: Sprungmarken
    const b = e.target.closest("[data-goto]"); if (b) $("#" + b.dataset.goto)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  const grid = $("#stGrid");
  grid.addEventListener("click", async (e) => {
    const t = e.target.closest("button"); if (!t) return;
    if (t.closest("#stTheme")) {
      S.opts.theme = t.dataset.v; applyTheme(); await call("set_option", "theme", S.opts.theme);
      $$("#stTheme button").forEach((b) => b.classList.toggle("on", b === t));
    } else if (t.id === "stBkFolder") { const d = await call("backup_pick_folder"); if (d) settingsShow(); else if (!S.settings.native) toast("Im Browser-Modus ist kein Ordnerdialog verfügbar."); }
    else if (t.id === "stBkOpen") call("open_folder", ST.data.backup_dir);
    else if (t.id === "stPlayers") { await plSetup(); settingsShow(); }
    else if (t.id === "stPlDefSave") { await call("player_defaults", "save"); toast("Player-Einstellungen als Standard gespeichert."); settingsShow(); }
    else if (t.id === "stPlDefApply") { const pp = await call("player_defaults", "apply"); plApplyPrefs(pp); toast("Player auf Standard zurückgesetzt."); settingsShow(); }
    else if (t.id === "stPlDefDel") { await call("player_defaults", "reset"); toast("Standard gelöscht."); settingsShow(); }
    else if (t.id === "stPlugins") setModule("plugins");
    else if (t.id === "stFixerGo") setModule("fixer");
    else if (t.id === "stUpdCheck") runUpdate();
    else if (t.id === "stUpdNotes") showReleaseNotes();
    else if (t.id === "stSnapGo") setModule("snapshots");
    else if (t.dataset.cclear) {
      const what = t.dataset.cclear === "wave" ? "Wellenformen" : t.dataset.cclear === "lists" ? "Listen-Cache" : "Cover-Vorschauen";
      if (await dialog({ title: `${what} leeren?`, text: "Sie werden bei Bedarf neu berechnet.", buttons: [{ label: "Abbrechen", value: null }, { label: "Leeren", value: true, primary: true }] })) {
        const r = await call("cache_clear", t.dataset.cclear); stCacheRender(r); toast(`${r.removed} Datei(en) entfernt.`);
        if (t.dataset.cclear === "wave" && PLAYER.info) PLAYER.info.wave = null;
      }
    }
    else if (t.dataset.cbuild) { await stCacheBuild(t.dataset.cbuild); stCacheRender(); }
    else if (t.dataset.defpick) { const v = await call("pick_path", "", true, (S.settings.defaults || {})[t.dataset.defpick] || ""); if (v) stDefSet(t.dataset.defpick, v); else if (!S.settings.native) toast("Im Browser-Modus den Pfad eintragen."); }
    else if (t.dataset.defclear) stDefSet(t.dataset.defclear, "");
    else if (t.dataset.copen) call("open_folder", t.dataset.copen);
    else if (t.id === "stTrivAdd") { const v = $("#stTrivIn").value.trim(); if (v) { await stTrivSet([...ST.data.trivial, v]); $("#stTrivIn").value = ""; } }
    else if (t.id === "stTrivDef") { if (await dialog({ title: "Standardliste wiederherstellen?", text: "Eigene Muster gehen verloren.", buttons: [{ label: "Abbrechen", value: null }, { label: "Wiederherstellen", value: true, primary: true }] })) stTrivSet(ST.data.trivial_default); }
    else if (t.dataset.k !== undefined && t.closest("#stTriv")) { const l = [...ST.data.trivial]; l.splice(+t.dataset.k, 1); stTrivSet(l); }
    else if (t.dataset.orreset) { await orLabelSet(t.dataset.orreset, "", null); toast("Kennzeichen zurückgesetzt."); }
    else if (t.id === "orLabReset") {
      if (await dialog({ title: "Alle Kennzeichen zurücksetzen?", text: "Eigene Texte und Farben der Herkunfts-Kennzeichen gehen verloren.", buttons: [{ label: "Abbrechen", value: null }, { label: "Zurücksetzen", value: true, primary: true }] })) { await orLabelSet(null); toast("Alle Kennzeichen auf Standard."); }
    }
    else if (t.id === "orAdd") { ST.origins = orRead(); ST.origins.push({ pattern: "", source: "" }); orRender(); $("#orSave").hidden = false; $$("#orList .pat").pop()?.focus(); }
    else if (t.dataset.ordel !== undefined) { ST.origins = orRead(); ST.origins.splice(+t.dataset.ordel, 1); orRender(); $("#orSave").hidden = false; }
    else if (t.id === "orSave") {
      const rules = orRead().filter((r) => r.pattern || r.source);
      if (rules.some((r) => !r.pattern || !r.source)) return toast("Bitte Muster und Herkunft ausfüllen.");
      const o = await call("set_tag_origins", rules);
      S.settings.origins = o.catalog;
      toast(`${o.custom.length} eigene Zuordnung(en) gespeichert.`);
      originSettingsRender($("#stOriginCard"));
      if (S.module === "settings" && TG.detail) renderTgEditor();
    }
    else if (t.dataset.triv) {
      const pats = (S.settings.origins[t.dataset.triv] || {}).patterns || [];
      const have = new Set(ST.data.trivial.map((x) => x.toLowerCase()));
      await stTrivSet([...ST.data.trivial, ...pats.filter((p) => !have.has(p.toLowerCase()))]);
      toast(`${S.settings.origins[t.dataset.triv].name}: Felder gelten jetzt als unwichtig.`);
      originSettingsRender($("#stOriginCard"));
    }
  });
  grid.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.id === "stTrivIn") { e.preventDefault(); $("#stTrivAdd").click(); } });
  grid.addEventListener("input", (e) => { if (e.target.closest("#orList")) $("#orSave").hidden = false; });
  grid.addEventListener("change", async (e) => {
    const t = e.target;
    if (t.id === "stNotation") {
      await call("tag_key_notation", t.value);
      if (typeof TG !== "undefined" && TG.settings && TG.settings.keys) { TG.settings.keys.notation = t.value; }
      toast("Tonart-Schreibweise gespeichert.");
    } else if (t.id === "stSaveVer") { await call("set_save_version", +t.value); toast(+t.value ? `Beim Speichern immer ID3v2.${t.value}.` : "ID3-Version bleibt wie in der Datei."); }
    else if (t.id === "stBackup") { await call("set_backup", t.checked, null); if (!t.checked) toast("Achtung: Vor dem Speichern wird nicht mehr gesichert."); }
    else if (t.id === "stStemsFlat") { await call("set_stems_flat", t.checked); if (TG.loaded) { TG.open = new Set(); await taggerRefresh(); } toast(t.checked ? "Stems erscheinen als eigene Titel." : "Stems erscheinen aufklappbar unter dem Original."); }
    else if (t.id === "stFeatScale") {                                           // #11
      await call("set_feat_scale", +t.value);
      if (typeof TG !== "undefined" && TG.loaded) { await taggerRefresh(); }
      toast(+t.value === 10 ? "Audio-Merkmale: Dateien in 0–10, Anzeige 0–100." : "Audio-Merkmale: 0–100.");
    }
    else if (t.dataset.defdir) stDefSet(t.dataset.defdir, t.value.trim());
    else if (t.id === "stListCache") { await call("set_list_cache", t.checked); toast(t.checked ? "Listen-Cache an." : "Listen-Cache aus – es wird immer von der Platte gelesen."); }
    else if (t.id === "orVer") {
      await call("set_origin_ver_badge", t.checked);
      if (S.pairs && S.pairs.length) refreshAll(await call("state"));
      if (typeof TG !== "undefined" && TG.loaded) await tgLoadDetail();
      toast(t.checked ? "Offizielle Felder zeigen ihre ID3-Version." : "Offizielle Felder ohne Versions-Kennzeichen.");
    }
    else if (t.classList.contains("or-short") || t.classList.contains("or-hue")) {
      const row = t.closest("[data-sid]"), sid = row.dataset.sid, v = S.settings.origins[sid] || {};
      const short = $(".or-short", row).value.trim();
      const hue = t.classList.contains("or-hue") ? hexHue(t.value) : (v.custom_label ? v.hue : null);
      await orLabelSet(sid, short, hue ?? null);
      toast("Kennzeichen gespeichert.");
    }
    else if (t.id === "snMove" || t.id === "snMoveDefault") { if (await snMoveStore(t.id === "snMoveDefault")) stSnapRender(); }
    else if (t.id === "snDaily") await call("snap_set", "snap_daily", t.checked);
    else if (t.id === "snAsk") await call("snap_set", "snap_ask", t.checked);
    else if (t.id === "snHint") await call("snap_set", "snap_hint", t.checked);
    else if (t.id === "snThorough") await call("snap_set", "snap_thorough", t.checked);
    else if (t.id === "snKeep") { await call("snap_set", "snap_keep", Math.max(1, +t.value || 20)); toast("Aufbewahrung gespeichert."); }
    else if (t.id === "snWatch") { await call("snap_set", "snap_watch", Math.max(0, +t.value || 0)); if (typeof SN !== "undefined" && SN.ov) SN.ov.settings.snap_watch = Math.max(0, +t.value || 0); toast("Überwachung gespeichert."); }
    else if (t.id === "snWeeks") { await call("snap_set", "snap_weeks", Math.max(0, +t.value || 0)); toast("Aufbewahrung gespeichert."); }
    else if (t.id === "stPlStart") plSetPref("start", t.value);
    else if (t.id === "stPlWave") plSetPref("wave", t.checked);
    else if (t.id === "stPlFollow") plSetPref("follow", t.checked);
    else if (t.id === "stPlRepeat") plSetPref("repeat", t.checked);
    else if (t.id === "stPlLive") plSetPref("live", t.checked);
    else if (t.id === "stPlVol") { PLAYER.vol = (+t.value) / 100; if (!PLAYER.fade) PLAYER.audio.volume = PLAYER.vol; $("#plVol").value = t.value; plSetPref("vol", PLAYER.vol); }
    else if (t.id === "stPlXf") plSetPref("xfade", +t.value);
    else if (t.id === "stPlXfStart") plSetPref("xfade_start", t.value);
    else if (t.id === "stPlXfAfter") plSetPref("xfade_after", +t.value);
    else if (t.id === "stPlXfSync") plSetPref("xfade_sync", t.checked);
    else if (t.id === "stPlXfRet") plSetPref("xfade_return", +t.value);
    else if (t.dataset.vd) await stVdSet(t);
    else if (t.id === "stUpdCh") { await call("set_update_channel", t.value); toast(t.value === "beta" ? "Updates: auch Beta-Versionen." : "Updates: nur offizielle Versionen."); settingsShow(); checkUpdateQuietly(); }
    else if (t.id === "stPlLayout") { pl2Pref("layout", t.value); await call("set_player_pref", "layout", t.value); settingsShow(); }
    else if (t.id === "stPlDeck2") plSetPref("deck2", t.checked);
    else if (t.id === "stPlResume") { await call("set_player_pref", "resume", t.checked); toast(t.checked ? "Wiedergabe wird beim Start fortgesetzt." : "Player startet leer."); }
    else if (t.id === "stPlResumePlay") { await call("set_player_pref", "resume_play", t.value); toast(t.value === "pause" ? "Titel wird in Pause geladen." : "Titel wird nach dem Start abgespielt."); }
    else if (t.id === "stPlStartmode") plSetPref("startmode", t.value);
  });
  grid.addEventListener("input", (e) => { if (e.target.id === "stPlVol") $("#stPlVolV").textContent = e.target.value + " %"; });
}

initSettings();
