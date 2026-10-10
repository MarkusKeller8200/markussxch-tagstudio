/* MarKusSXCH TagStudio – Vorschau-Player (unten in der Aktionsleiste) und externe Player.
   Leertaste: markierten Titel abspielen/pausieren · Shift+←/→: ±10 s · Alt+Bild↑/↓: voriger/nächster Cue ·
   S/Shift+S: nächste/vorige Stem-Spur · Strg/Cmd+P: im externen Player öffnen. Wellenform: einmal per Web Audio berechnet, im Cache (waveform.py);
   Cue-Marken aus Serato/Mixed In Key (cues.py).
   Im Tagger spielt der Player beim Wechsel der Markierung (↑/↓, Klick) automatisch weiter („Durchhören“).
   Im Vergleich schaltet A/B zwischen linker und rechter Datei um und behält die Position.
   ↑/↓ wechseln den Titel, egal wo der Fokus ist (#64); bei Stems schaltet der Player zwischen Original und Spuren
   an derselben Stelle um (#66). */
"use strict";

const PLAYER = { audio: null, info: null, kind: null, ref: null, side: "L", loading: false, follow: true, startAt: "0",
  wave: true, waveBusy: null, loop: null, raf: 0, repeat: false, ab: null,
  vol: 0.8, spare: null, fade: null, xfade: 0, xfadeStart: "start", xfadeAfter: 0, playFrom: 0, target: "A" };
const WAVE_N = 800;               // Balken der Wellenform (im Cache gespeichert)
const WAVE_MAX_BYTES = 80e6;      // sehr lange Mixe nicht dekodieren (Speicher)

const ICON_PLAY = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4v16l13-8Z"/></svg>';
const ICON_PAUSE = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4h3v16H7zM14 4h3v16h-3z"/></svg>';

/** Player-Einstellung ändern und in den Einstellungen (~/.tagstudio.json, Gruppe „Player“) merken. */
let plVolTimer = null;
function plSetPref(k, v) {
  if (k === "start") { PLAYER.startAt = v; plStartSync(); }
  else if (k === "wave") { PLAYER.wave = !!v; if (PLAYER.wave && PLAYER.info && !PLAYER.info.wave) plWaveCompute(PLAYER.info); plRender(); }
  else if (k === "follow") PLAYER.follow = !!v;
  else if (k === "repeat") { PLAYER.repeat = !!v; plRender(); }
  else if (k === "live") { PLAYER.live = !!v; plRender(); }
  else if (k === "xfade") PLAYER.xfade = +v || 0;
  else if (k === "xfade_start") PLAYER.xfadeStart = v;
  else if (k === "xfade_after") PLAYER.xfadeAfter = +v || 0;
  else if (k === "xfade_sync") PLAYER.xfadeSync = !!v;
  else if (k === "xfade_return") PLAYER.xfadeReturn = +v || 0;
  else if (k === "layout" || k === "top_collapsed" || k === "deck2" || k === "deck_target" || k === "sink_b" || k === "vol_b" || k === "start_b" || k === "repeat_b") {
    if (typeof pl2Pref === "function") pl2Pref(k, v);
    if (k === "vol_b") { clearTimeout(plVolTimer); plVolTimer = setTimeout(() => call("set_player_pref", "vol_b", v).catch(() => {}), 400); return; }
  }
  else if (k === "vol") { clearTimeout(plVolTimer); plVolTimer = setTimeout(() => call("set_player_pref", "vol", v).catch(() => {}), 400); return; }
  call("set_player_pref", k, v).catch(() => {});
}

/** Startpunkt-Umschalter (#36) */
function plStartSync() {
  $$("#plStart button").forEach((b) => { const on = b.dataset.v === PLAYER.startAt; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); });
}

function plStore(k, v) {
  try { if (v === undefined) return localStorage.getItem("ts_pl_" + k); localStorage.setItem("ts_pl_" + k, String(v)); } catch (e) { /* egal */ }
  return null;
}
const fmtTime = (s) => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60), r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
};

/** Was soll gespielt werden? → {kind, ref} oder null */
function plTarget() {
  if (S.module === "tagger" && typeof tgSelected === "function") {
    const sel = tgSelected();
    const i = sel.length ? (TG.sel.has(TG.anchor) ? TG.anchor : sel[0]) : null;
    return i === null || i === undefined ? null : { kind: "tag", ref: i };
  }
  if (S.module === "compare" && S.cur !== null && S.cur !== undefined) return { kind: "side", ref: PLAYER.side };
  return null;
}

async function plLoad(target, autoplay = true, keepTime = null, startMode = null, fromFade = false) {
  if (PLAYER.fade && !fromFade && typeof plFadeStop === "function") plFadeStop();
  if (!fromFade && typeof plTempoStop === "function") plTempoStop();
  if (!target) { toast(S.module === "tagger" ? "Erst einen Titel markieren." : "Erst ein Dateipaar wählen."); return; }
  const seq = PLAYER.loadSeq = (PLAYER.loadSeq || 0) + 1;
  PLAYER.loading = true;
  // schnelle Folge (S S, ↓↓): vom gewünschten statt vom noch ladenden Titel aus weiter
  PLAYER.want = target; PLAYER.wantTime = keepTime; PLAYER.wantPlay = autoplay;
  let info;
  try { info = await call("media_url", target.kind, target.ref); } catch (e) { if (seq === PLAYER.loadSeq) PLAYER.loading = false; toast(String(e.message || e)); return; }
  if (seq !== PLAYER.loadSeq) return;       // inzwischen ein anderer Titel gewünscht
  PLAYER.info = info; PLAYER.kind = target.kind; PLAYER.ref = target.ref;
  const a = PLAYER.audio;
  const keepAB = keepTime !== null && PLAYER.ab && PLAYER.ab.b !== undefined && plInGroupOf(target) ;   // #79: bei Stems/A-B gleiche Stelle → Schleife behalten
  if (!keepAB) { PLAYER.ab = null; plLoopSet(null); }
  a.src = info.url;
  const dur = info.duration || 0;
  const firstCue = (info.cues || []).find((c) => c.pos > 0.05);
  const sm = startMode || PLAYER.startAt;
  const start = keepTime !== null ? keepTime : sm === "30" ? dur * 0.3 : sm === "60" ? Math.min(60, dur * 0.5)
    : sm === "cue" ? (firstCue ? firstCue.pos : 0) : 0;
  PLAYER.wantTime = start; PLAYER.playFrom = start;
  const seek = () => { try { if (start > 0) a.currentTime = Math.min(start, (a.duration || dur) - 1); } catch (e) { /* egal */ } };
  a.addEventListener("loadedmetadata", seek, { once: true });
  plCues();
  plRender();
  if (PLAYER.wave && !info.wave) plWaveCompute(info);
  if (autoplay) {
    try { await a.play(); } catch (e) {
      // AbortError: schneller Titelwechsel – der neue Titel lädt bereits, kein Fehler
      if (e.name !== "AbortError") toast("Wiedergabe nicht möglich: " + (e.message || e));
    }
  }
  if (seq === PLAYER.loadSeq) PLAYER.loading = false;
}

/** Liste neu eingelesen: der Player darf nicht mehr auf alte Indizes zeigen. */
function plForget(kind) {
  if (typeof DECKB !== "undefined" && DECKB.kind === kind) dbForget();
  if (!PLAYER.audio || PLAYER.kind !== kind) return;
  if (PLAYER.fade) plFadeStop();
  PLAYER.audio.pause();
  PLAYER.audio.removeAttribute("src"); PLAYER.audio.load();
  plLoopSet(null);
  PLAYER.info = null; PLAYER.kind = null; PLAYER.ref = null;
  plCues(); plRender();
}

/** gleiche Aufnahme (Stems-Gruppe oder L/R im Vergleich)? */
function plInGroupOf(t) { return plInGroup(t) || (t && t.kind === "side" && PLAYER.kind === "side"); }

/** #79: A–B-Schleife – 1. Aufruf A setzen, 2. B setzen und spielen, 3. aufheben */
function plABStep() {
  const a = PLAYER.audio;
  if (!a.src) return;
  if (!PLAYER.ab) { PLAYER.ab = { a: a.currentTime }; toast(`A gesetzt bei ${fmtTime(a.currentTime)} – nochmals für B.`); }
  else if (PLAYER.ab.b === undefined) {
    const t = a.currentTime;
    if (t <= PLAYER.ab.a + 0.2) { toast("B muss nach A liegen."); return; }
    PLAYER.ab.b = t;
    plLoopSet({ pos: PLAYER.ab.a, end: t, k: -1 });
    toast(`Schleife ${fmtTime(PLAYER.ab.a)}–${fmtTime(t)} – nochmals (L) oder Esc zum Aufheben.`);
  } else { plABClear(); toast("Schleife aufgehoben."); }
  plABDraw(); plRender();
}
function plABClear() { PLAYER.ab = null; if (PLAYER.loop && PLAYER.loop.k === -1) plLoopSet(null); plABDraw(); plRender(); }
function plABDraw() {
  const box = $("#plCues"); if (!box) return;
  $("#plABMark")?.remove();
  const ab = PLAYER.ab, dur = (PLAYER.audio && PLAYER.audio.duration) || (PLAYER.info && PLAYER.info.duration) || 0;
  if (!ab || !dur) return;
  const l = (ab.a / dur) * 100, w = ab.b !== undefined ? ((ab.b - ab.a) / dur) * 100 : 0;
  box.insertAdjacentHTML("beforeend", `<button class="pl-abmark${ab.b === undefined ? " open" : ""}" id="plABMark" style="left:${l}%;width:${Math.max(0.4, w)}%" title="A–B-Schleife ${fmtTime(ab.a)}${ab.b !== undefined ? "–" + fmtTime(ab.b) : " (B fehlt)"} · Klick: aufheben"></button>`);
}

function plSame(t) { return t && PLAYER.info && t.kind === PLAYER.kind && t.ref === PLAYER.ref; }
/** Gehört das Ziel zur selben Stems-Gruppe wie der laufende Titel (Original oder eine Spur)? (#66) */
function plInGroup(t) { return !!(t && PLAYER.info && (PLAYER.info.stems || []).some((g) => g.kind === t.kind && g.ref === t.ref)); }

async function plToggle() {
  if (PLAYER.target === "B" && typeof dbToggle === "function") return dbToggle();
  const t = plTarget();
  if (!PLAYER.audio.src || (t && !plSame(t) && !plInGroup(t) && !(t.kind === "side" && PLAYER.kind === "side"))) return plLoad(t);
  if (t && t.kind === "side" && PLAYER.kind === "side" && PLAYER.info && PLAYER.info.ref !== PLAYER.side) return plLoad(t, true);
  if (PLAYER.audio.paused) { try { await PLAYER.audio.play(); } catch (e) { toast(String(e.message || e)); } } else PLAYER.audio.pause();
}

/** Markierung hat sich geändert (Tagger/Vergleich). src: „key“ (↑/↓, Programm), „click“ (Einfachklick), „multi“.
    Live-Vorschau (#91): Klick spielt sofort. Ohne Live-Vorschau (#92) wechselt ein Klick den laufenden Titel nicht –
    dafür Doppelklick; ↑/↓ und „Folgen“ wechseln beim Abspielen weiter. */
function playerFollow(src = "key") {
  if (PLAYER.noFollow) { plRender(); return; }          // Rechtsklick-Menü: nur markieren
  if (PLAYER.target === "B" && typeof dbFollow === "function") return dbFollow(src);   // #67: Player B folgt der Markierung
  if (!PLAYER.audio || PLAYER.loading || src === "multi") { plRender(); return; }
  const t = plTarget();
  if (src === "click" && PLAYER.live) {
    if (t && (!plSame(t) || PLAYER.audio.paused)) plLoad(t, true, plInGroup(t) ? PLAYER.audio.currentTime : null);
    return;
  }
  if (src === "click" || PLAYER.audio.paused || !PLAYER.follow) { plRender(); return; }
  if (t && !plSame(t)) plLoad(t, true, plInGroup(t) ? PLAYER.audio.currentTime : null);   // Spur derselben Gruppe: Stelle halten
}

/** #92: Doppelklick auf eine Zeile – diesen Titel spielen (bzw. von vorn, wenn er schon läuft) */
function plPlayRow() {
  if (PLAYER.target === "B" && typeof dbPlayRow === "function") return dbPlayRow();
  const t = plTarget();
  if (!t) return;
  if (plSame(t) && !PLAYER.audio.paused) return;
  plLoad(t, true, plInGroup(t) ? PLAYER.audio.currentTime : null);
}

// ---------------------------------------------------------------------- Bewertung & Like (#95/#96/#97)
/** Sterne (0–5, null = verschieden) und ♥ als Knöpfe. Klick auf den aktuellen Stern löscht die Bewertung. */
function rateHtml(v, like, opt = {}) {
  const mixed = v === null || v === undefined;
  let h = `<span class="rate${mixed ? " mixed" : ""}${opt.cls ? " " + opt.cls : ""}" role="group" aria-label="Bewertung"${mixed ? ' title="Bewertung verschieden"' : ""}>`;
  for (let n = 1; n <= 5; n++) {
    h += `<button type="button" class="rs${!mixed && n <= v ? " on" : ""}" data-star="${n}" title="${n} Stern${n > 1 ? "e" : ""}${opt.keys ? ` (${n})` : ""}${!mixed && n === v ? " – nochmals: Bewertung entfernen" : ""}" aria-label="${n} Stern${n > 1 ? "e" : ""}" aria-pressed="${!mixed && n <= v}">★</button>`;
  }
  if (opt.like !== false) {
    const lm = like === null || like === undefined;
    h += `<button type="button" class="rl${like ? " on" : ""}${lm ? " mixed" : ""}" data-like="1" title="${like ? "Like entfernen" : "Like"}${opt.keys ? " (F)" : ""}${lm ? " – verschieden" : ""}" aria-label="Like" aria-pressed="${!!like}">♥</button>`;
  }
  return h + "</span>";
}

/** Kleine Anzeige in Listen: ★★★ und ♥ (nur wenn gesetzt) */
function rateMini(v, like) {
  if (!v && !like) return "";
  return `<span class="rate-mini" title="${v ? `${v} Stern${v > 1 ? "e" : ""}` : ""}${v && like ? " · " : ""}${like ? "Like" : ""}">${v ? "★".repeat(v) : ""}${like ? '<b>♥</b>' : ""}</span>`;
}

/** Tasten 0–5/F: den laufenden Titel bewerten – steht der Player, die Markierung (Tagger: alle markierten). */
async function plMark(stars, like) {
  if (PLAYER.target === "B" && typeof DECKB !== "undefined" && DECKB.info && DECKB.kind !== "stem") {   // #67: Player B bewerten
    return plMarkTarget({ kind: DECKB.kind, ref: DECKB.kind === "side" ? DECKB.info.ref : DECKB.ref }, stars, like);
  }
  const loaded = PLAYER.info && (PLAYER.kind === "tag" || PLAYER.kind === "side");
  const sel = plTarget();
  const useP = loaded && (!PLAYER.audio.paused || plSame(sel) || (sel && sel.kind === "side" && PLAYER.kind === "side"));
  const t = useP ? { kind: PLAYER.kind, ref: PLAYER.kind === "side" ? PLAYER.info.ref : PLAYER.ref } : null;
  if (!t) {
    if (S.module === "tagger" && typeof tgMark === "function" && tgSelected().length) return tgMark(stars, like);
    const p = plTarget();
    if (!p) { toast("Erst einen Titel markieren oder abspielen."); return; }
    return plMarkTarget(p, stars, like);
  }
  return plMarkTarget(t, stars, like);
}

async function plMarkTarget(t, stars, like) {
  const db = typeof DECKB !== "undefined" && DECKB.info && t.kind === DECKB.kind && (t.kind === "side" ? DECKB.info.ref === t.ref : DECKB.ref === t.ref) ? DECKB.info : null;
  const cur = PLAYER.info && plSame(t) ? PLAYER.info : db;
  if (stars !== null && stars !== undefined && cur && cur.rating === stars) stars = 0;   // gleicher Stern: löschen
  const r = await call("player_mark", t.kind, t.ref, stars ?? null, like ?? null);
  if (!r.ok) { toast(r.error); return; }
  if (PLAYER.info && (plSame(t) || (t.kind === "side" && PLAYER.kind === "side" && PLAYER.info.ref === t.ref))) { PLAYER.info.rating = r.rating; PLAYER.info.like = r.like; }
  if (db) { db.rating = r.rating; db.like = r.like; }
  if (r.meta) { S.meta = r.meta; renderMeta(); }
  if (r.row && typeof TG !== "undefined") {
    TG.rows[r.row.i] = r.row;
    if (TG.sel.has(r.row.i)) await tgLoadDetail(); else drawTgList();
  }
  if (t.kind === "side") applyState(await call("state"));
  plRender();
  if (typeof dbRender === "function") dbRender();
  if (r.message) toast(r.message);
}

/** #91: Live-Vorschau an/aus */
function plLiveSet(on) {
  plSetPref("live", !!on);
  toast(on ? "Live-Vorschau: Klick auf einen Titel spielt ihn sofort." : "Live-Vorschau aus – Doppelklick spielt einen Titel.");
}

/** #66: zwischen Original und Stem-Spuren umschalten – gleiche Stelle, Wiedergabe läuft weiter. */
function plStemSwitch(k) {
  const g = PLAYER.info && (PLAYER.info.stems || [])[k];
  if (!g || (plSame(g) && !PLAYER.loading)) return;
  const t = PLAYER.loading && PLAYER.wantTime != null ? PLAYER.wantTime : PLAYER.audio.currentTime;   // Titel lädt noch: dessen Ziel
  plLoad({ kind: g.kind, ref: g.ref }, PLAYER.loading ? PLAYER.wantPlay : !PLAYER.audio.paused, t);
}

/** Voriger/nächster Titel. play=false: nur die Markierung bewegen (läuft der Player, folgt er ohnehin). */
async function plStep(dir, play = true) {
  if (S.module === "tagger" && TG.order.length) {
    const k = Math.max(0, Math.min(TG.order.length - 1, TG.order.indexOf(TG.anchor) + dir));
    const i = TG.order[k];
    const wasPlaying = !PLAYER.audio.paused;
    await tgSelect(i, {});          // beim Abspielen übernimmt playerFollow() den neuen Titel
    TG.anchor = i;
    tgScrollTo(i);
    if (!wasPlaying && play) plLoad(plTarget(), true);
  } else if (S.module === "compare" && S.visible && S.visible.length) {
    const k = Math.max(0, Math.min(S.visible.length - 1, S.visible.indexOf(S.cur) + dir));
    const wasPlaying = !PLAYER.audio.paused;
    await selectPair(S.visible[k]);
    if (!wasPlaying && play) plLoad(plTarget(), true);
  }
}

/** #64: ↑/↓ wechseln den Titel, egal wo der Fokus ist. Ausgenommen: mehrzeilige Felder, Auswahllisten, Zahlenfelder,
    Felder mit Vorschlagsliste, offene Dialoge/Menüs und die Feldtabelle im Vergleich (dort wandern ↑/↓ durch die Felder).
    Die Listen im Tagger und Vergleich behandeln ↑/↓ (auch mit Shift) selbst. */
function plArrowKey(e) {
  if ((e.key !== "ArrowUp" && e.key !== "ArrowDown") || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented) return;
  if (S.module !== "tagger" && S.module !== "compare") return;
  if (!$("#modal").hidden || !$("#dialog").hidden || !$("#xmlEd").hidden || !$("#menu").hidden || (typeof KW !== "undefined" && KW.open)) return;
  const el = document.activeElement || document.body;
  if (el.closest("#tgTable, #pairsScroll, #table")) return;
  if (/TEXTAREA|SELECT/.test(el.tagName) || el.isContentEditable) return;
  if (el.tagName === "INPUT" && (el.type === "number" || el.hasAttribute("list") || el.dataset.fnum !== undefined)) return;
  e.preventDefault();
  e.stopPropagation();
  if (el.tagName === "INPUT" && el.type !== "range") el.blur();   // Eingabe übernehmen (focusout), dann wechseln
  plStep(e.key === "ArrowDown" ? 1 : -1, false);
}

function plSide(side) {
  PLAYER.side = side;
  if (PLAYER.kind === "side" && PLAYER.audio.src) plLoad({ kind: "side", ref: side }, !PLAYER.audio.paused, PLAYER.audio.currentTime);
  else plRender();
}

function plRender() {
  const a = PLAYER.audio;
  if (!a) return;
  const bar = $("#player");
  bar.classList.toggle("on", !!a.src);
  $("#plPlay").innerHTML = a.paused ? ICON_PLAY : ICON_PAUSE;
  $("#plPlay").title = a.paused ? "Abspielen (Leertaste)" : "Pause (Leertaste)";
  const i = PLAYER.info;
  $("#plTitle").textContent = i ? (i.title ? `${i.artist ? i.artist + " – " : ""}${i.title}` : i.name) : "Vorhören: Titel markieren, Leertaste";
  $("#plTitle").title = i ? i.path : "";
  bar.classList.toggle("playing", !a.paused);
  // #46/#63: Tonart (mit den anderen Schreibweisen) und Tempo des laufenden Titels
  const rate = a.playbackRate || 1, bpmN = parseFloat(String((i && i.bpm) || "").replace(",", ".")) || 0;
  const bpm = !i || !i.bpm ? "" : Math.abs(rate - 1) > 0.0005 && bpmN ? `${(bpmN * rate).toFixed(1)}` : String(Math.round(bpmN) || i.bpm);
  const alt = i && i.key_alt ? [i.key_alt.musical, i.key_alt.openkey].filter(Boolean) : [];
  const meta = i ? `${i.key && typeof keyBadge === "function" ? keyBadge(i.key) : ""}${alt.length ? `<span class="pl-key-alt" title="Musikalisch · Open Key">${esc(alt.join(" · "))}</span>` : ""}${bpm ? `<span class="pl-bpm${Math.abs(rate - 1) > 0.0005 ? " synced" : ""}" title="${Math.abs(rate - 1) > 0.0005 ? `Tempo angeglichen (${rate > 1 ? "+" : ""}${((rate - 1) * 100).toFixed(1)} %, Original ${Math.round(bpmN)} BPM)` : "Tempo"}">${esc(bpm)} BPM</span>` : ""}` : "";
  if ($("#plMeta").dataset.v !== meta) { $("#plMeta").innerHTML = meta; $("#plMeta").dataset.v = meta; }
  plStemsRender();
  const rh = i && i.markable !== false && i.rating !== undefined ? rateHtml(i.rating, i.like, { keys: true }) : "";
  if ($("#plRate").dataset.v !== rh) { $("#plRate").innerHTML = rh; $("#plRate").dataset.v = rh; }
  $("#plVol").classList.toggle("muted", a.muted);
  $("#plVol").title = a.muted ? "Stumm (M)" : "Lautstärke (M: stumm)";
  const dur = a.duration || (i && i.duration) || 0;
  plTimes(i ? a.currentTime : 0, i ? dur : 0);
  const seek = $("#plSeek");
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(a.currentTime * 10)); }
  seek.disabled = !i;
  plDrawWave();
  $("#plAB").hidden = S.module !== "compare";
  $("#plLive").classList.toggle("on", !!PLAYER.live); $("#plLive").setAttribute("aria-pressed", String(!!PLAYER.live));
  $("#plRepeat").classList.toggle("on", PLAYER.repeat); $("#plRepeat").setAttribute("aria-pressed", String(PLAYER.repeat));
  $("#plAB2").classList.toggle("on", !!PLAYER.ab); $("#plAB2").classList.toggle("half", !!PLAYER.ab && PLAYER.ab.b === undefined);
  const hasCues = !!(i && i.cues && i.cues.length);
  $("#plCuePrev").hidden = $("#plCueNext").hidden = !hasCues;      // Cue-Sprünge (#37)
  $$("#plAB button").forEach((b) => b.classList.toggle("on", b.dataset.side === PLAYER.side));
}

/** Laufzeit, Restlaufzeit (#63) und Länge; in den letzten 30 Sekunden rot (#65, blinkt beim Abspielen). */
function plTimes(t, dur) {
  const rest = Math.max(0, dur - t);
  $("#plElapsed").textContent = fmtTime(t);
  $("#plRemain").textContent = "−" + fmtTime(Math.ceil(rest - 0.001));
  $("#plLen").textContent = fmtTime(dur);
  $("#plRemain").classList.toggle("end", !!PLAYER.info && dur > 0 && rest <= 30);
}

/** #66: Umschalter Original/Spuren, nur bei Titeln mit Stems (Knopf mit Menü; S/Shift+S: nächste/vorige Spur) */
function plStemsRender() {
  const box = $("#plStems"), g = (PLAYER.info && PLAYER.info.stems) || [];
  const cur = g.find((x) => plSame(x));
  box.hidden = !g.length;
  const label = cur ? cur.label : "Stems";
  if (box.textContent !== label) box.textContent = label;
}

function plStemsMenu(btn) {
  const g = (PLAYER.info && PLAYER.info.stems) || [];
  const r = btn.getBoundingClientRect();
  const top = typeof PL2 !== "undefined" && PL2.layout === "top";
  showMenu(r.left, top ? r.bottom + 6 : r.top - 8 - (g.length + 1) * 34, g.map((x, k) => ({
    label: (plSame(x) ? "✓ " : "    ") + x.label, run: () => plStemSwitch(k) })));
}

function plStemCycle(dir) {
  const g = (PLAYER.info && PLAYER.info.stems) || [];
  if (!g.length) return false;
  const w = PLAYER.loading && PLAYER.want;
  const k = g.findIndex((x) => (w ? x.kind === w.kind && x.ref === w.ref : plSame(x)));
  plStemSwitch((k + dir + g.length) % g.length);
  toast(g[(k + dir + g.length) % g.length].label);
  return true;
}

function plSeekBy(sec) {
  if (!PLAYER.audio.src) return;
  PLAYER.audio.currentTime = Math.max(0, Math.min((PLAYER.audio.duration || 0) - 0.5, PLAYER.audio.currentTime + sec));
  plRender();
}

// ---------------------------------------------------------------------- Wellenform & Cue-Marken
/** Wellenform einmal berechnen (Web Audio, niedrige Abtastrate spart Speicher) und im Cache ablegen. */
async function plWaveCompute(info) {
  if (!info.wave_key || PLAYER.waveBusy === info.wave_key) return;
  PLAYER.waveBusy = info.wave_key;
  try {
    const res = await fetch(info.url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    if (+(res.headers.get("Content-Length") || 0) > WAVE_MAX_BYTES) return;
    const buf = await res.arrayBuffer();
    const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    let audio = null;
    for (const rate of [8000, 22050, 44100]) {
      try { audio = await new OAC(1, 1, rate).decodeAudioData(buf.slice(0)); break; } catch (e) { audio = null; }
    }
    if (!audio) return;
    const ch = [...Array(audio.numberOfChannels).keys()].map((c) => audio.getChannelData(c));
    const len = ch[0].length, step = len / WAVE_N, peaks = [], rms = [];
    for (let b = 0; b < WAVE_N; b++) {
      const from = Math.floor(b * step), to = Math.max(from + 1, Math.floor((b + 1) * step));
      let pk = 0, sq = 0, n = 0;
      for (const d of ch) for (let k = from; k < to && k < len; k++) { const v = Math.abs(d[k]); if (v > pk) pk = v; sq += v * v; n++; }
      peaks.push(Math.min(255, Math.round(pk * 255)));
      rms.push(Math.min(255, Math.round(Math.sqrt(sq / Math.max(1, n)) * 255)));
    }
    const wave = { peaks, rms };
    call("wave_save", info.wave_key, peaks, rms).catch(() => {});
    if (PLAYER.info && PLAYER.info.wave_key === info.wave_key) { PLAYER.info.wave = wave; plRender(); }
    if (typeof DECKB !== "undefined" && DECKB.info && DECKB.info.wave_key === info.wave_key) { DECKB.info.wave = wave; dbRender(); }
  } catch (e) { /* ohne Wellenform weiter – Wiedergabe ist wichtiger */ }
  finally { if (PLAYER.waveBusy === info.wave_key) PLAYER.waveBusy = null; }
}

function plDrawWave() {
  const box = $("#plWave"), cv = $("#plCanvas");
  const w = PLAYER.wave && PLAYER.info && PLAYER.info.wave;
  box.classList.toggle("wave", !!w);
  if (!w) return;
  const dpr = window.devicePixelRatio || 1, W = Math.max(1, Math.round(cv.clientWidth * dpr)), H = Math.max(1, Math.round(cv.clientHeight * dpr));
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  const g = cv.getContext("2d"), st = getComputedStyle(document.documentElement);
  const acc = st.getPropertyValue("--acc").trim() || "#7c5cff", dim = st.getPropertyValue("--faint").trim() || "#888";
  const a = PLAYER.audio, dur = a.duration || PLAYER.info.duration || 0, played = dur ? a.currentTime / dur : 0;
  const n = w.peaks.length, top = Math.max(1, ...w.peaks), bw = W / n, mid = H / 2;
  g.clearRect(0, 0, W, H);
  for (let k = 0; k < n; k++) {
    const x = k * bw, ph = Math.max(1, (w.peaks[k] / top) * (H - 2) / 2), rh = Math.max(0.5, (w.rms[k] / top) * (H - 2) / 2);
    const on = k / n < played;
    g.globalAlpha = on ? 0.45 : 0.3; g.fillStyle = on ? acc : dim;
    g.fillRect(x, mid - ph, Math.max(1, bw - 0.4), ph * 2);
    g.globalAlpha = on ? 1 : 0.75;
    g.fillRect(x, mid - rh, Math.max(1, bw - 0.4), rh * 2);
  }
  g.globalAlpha = 1; g.fillStyle = acc;
  g.fillRect(Math.round(played * W), 0, Math.max(1, Math.round(dpr)), H);
}

function plCues() {
  const box = $("#plCues"), i = PLAYER.info, cues = (i && i.cues) || [];
  const dur = (PLAYER.audio && PLAYER.audio.duration) || (i && i.duration) || 0;
  box.innerHTML = dur ? cues.map((c, k) => {
    const left = Math.max(0, Math.min(100, (c.pos / dur) * 100));
    const w = c.kind === "loop" && c.end ? `--w:${Math.max(2, ((c.end - c.pos) / dur) * box.clientWidth)}px;` : "";
    const label = `${c.kind === "loop" ? "Loop" : "Cue"} ${c.index + 1}${c.name ? " · " + c.name : ""} · ${fmtTime(c.pos)}${c.kind === "loop" && c.end ? `–${fmtTime(c.end)} · Klick: Schleife an/aus` : ""} (${c.source})`;
    return `<button class="pl-cue${c.kind === "loop" ? " loop" : ""}${PLAYER.loop && PLAYER.loop.k === k ? " on" : ""}" data-k="${k}" style="left:${left}%;${c.color ? `--cue:${esc(c.color)};` : ""}${w}" title="${esc(label)}" aria-label="${esc(label)}"></button>`;
  }).join("") : "";
  plABDraw();
}

/** #47: Serato-Loop als Schleife abspielen (null = aus) */
function plLoopSet(c) {
  PLAYER.loop = c && c.end > c.pos ? { pos: c.pos, end: c.end, k: c.k } : null;
  if (c && c.k !== -1 && PLAYER.ab) { PLAYER.ab = null; plABDraw(); }     // Serato-Loop ersetzt A–B
  cancelAnimationFrame(PLAYER.raf);
  $$("#plCues .pl-cue.loop").forEach((b) => b.classList.toggle("on", !!PLAYER.loop && +b.dataset.k === PLAYER.loop.k));
  if (!PLAYER.loop) return;
  const tick = () => {
    const L = PLAYER.loop, a = PLAYER.audio;
    if (!L) return;
    if (a.currentTime >= L.end || a.currentTime < L.pos - 0.5) a.currentTime = L.pos;
    PLAYER.raf = requestAnimationFrame(tick);
  };
  PLAYER.raf = requestAnimationFrame(tick);
}

/** #48: Zeit (und nahen Cue) beim Überfahren der Leiste zeigen */
function plHover(e) {
  const box = $("#plWave"), tip = $("#plHover"), i = PLAYER.info;
  const dur = (PLAYER.audio && PLAYER.audio.duration) || (i && i.duration) || 0;
  if (!i || !dur || e.type === "mouseleave") { tip.hidden = true; return; }
  const r = box.getBoundingClientRect(), f = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), t = f * dur;
  const near = (i.cues || []).find((c) => Math.abs(c.pos - t) / dur < 0.012);
  tip.textContent = fmtTime(t) + (near ? ` · ${near.kind === "loop" ? "Loop" : "Cue"} ${near.index + 1}${near.name ? " " + near.name : ""}` : "");
  tip.hidden = false;
  tip.style.left = Math.max(0, Math.min(r.width - tip.offsetWidth, f * r.width - tip.offsetWidth / 2)) + "px";
}

/** Zum nächsten/vorigen Cue springen (Shift+↑/↓ bzw. Alt+←/→ im Player). */
function plCueJump(dir) {
  const cues = (PLAYER.info && PLAYER.info.cues) || [], t = PLAYER.audio.currentTime;
  if (!cues.length || !PLAYER.audio.src) return false;
  const c = dir > 0 ? cues.find((x) => x.pos > t + 0.3) : [...cues].reverse().find((x) => x.pos < t - 1);
  PLAYER.audio.currentTime = c ? c.pos : dir > 0 ? t : 0;
  plRender();
  return true;
}

// ---------------------------------------------------------------------- Externe Player
function plRefs() {
  if (S.module === "tagger") { const sel = tgSelected(); return sel.length ? { kind: "tag", refs: sel } : null; }
  if (S.module === "compare" && S.cur !== null) return { kind: "side", refs: [PLAYER.side] };
  return null;
}

async function plExternal(index = null) {
  const r = plRefs();
  if (!r) { toast("Erst Titel markieren."); return; }
  const res = await call("play_external", r.kind, r.refs, index);
  if (!res.ok) await info("Player konnte nicht gestartet werden", res.error);
  else toast(`${res.count} Titel in ${res.player} geöffnet.`);
}

async function plMenu(btn) {
  const list = await call("players");
  const r = btn.getBoundingClientRect();
  const top = PL2.layout === "top" && !DET.on;
  showMenu(r.left, top ? r.bottom + 6 : r.top - 8 - (list.length + 8) * 34, [
    ...list.map((p, k) => ({ label: `Öffnen mit ${p.name}` + (k === 0 ? "  (Strg/Cmd+P)" : ""), run: () => plExternal(k) })),
    { label: "Öffnen mit Standardprogramm" + (list.length ? "" : "  (Strg/Cmd+P)"), run: () => plExternal(null) },
    "-",
    { label: "Player einrichten …", run: () => plSetup() },
    { label: (PLAYER.wave ? "✓ " : "    ") + "Wellenform anzeigen", run: () => plSetPref("wave", !PLAYER.wave) },
    ...(PL2.layout === "top" ? [{ label: (PL2.deck2 ? "✓ " : "    ") + "Player B anzeigen", run: () => plSetPref("deck2", !PL2.deck2) }] : []),
    { label: (PL2.layout === "top" ? "✓ " : "    ") + "Player oben anordnen", run: () => plSetPref("layout", PL2.layout === "top" ? "bottom" : "top") },
    { label: (PLAYER.xfade ? `✓ Überblenden (${PLAYER.xfade} s)` : "    Überblenden"), run: () => plSetPref("xfade", PLAYER.xfade ? 0 : 6) },
    { label: "Player abdocken (eigenes Fenster)", run: () => plDetach() },
    "-",
    { label: "Alle Player-Einstellungen …", run: () => setModule("settings") },
  ]);
}

async function plSetup() {
  let list = await call("players");
  const row = (p, k) => `<div class="pl-row" data-k="${k}">
      <input class="pl-name" value="${esc(p.name || "")}" placeholder="Name, z. B. foobar2000" aria-label="Name">
      <div class="pl-cmd"><input class="pl-path" value="${esc(p.cmd || "")}" placeholder="Programm, z. B. C:\\Program Files\\foobar2000\\foobar2000.exe" spellcheck="false" aria-label="Programm">
        <button class="ghost sm" data-browse="${k}" title="Programm wählen">…</button></div>
      <input class="pl-args" value="${esc(p.args || "{files}")}" spellcheck="false" aria-label="Argumente" title="Platzhalter: {files} alle Dateien · {file} erste Datei · {folder} Ordner · {m3u} Playlist">
      <button class="x del" data-del="${k}" title="Entfernen">✕</button></div>`;
  const draw = (b) => {
    $("#plList", b).innerHTML = list.length
      ? `<div class="pl-row pl-head"><span>Name</span><span>Programm</span><span>Argumente</span><span></span></div>${list.map(row).join("")}`
      : '<div class="muted">Noch kein Player eingerichtet – ohne Eintrag öffnet TagStudio das Standardprogramm des Systems.</div>';
  };
  const read = (b) => $$(".pl-row[data-k]", b).map((r) => ({
    name: $(".pl-name", r).value, cmd: $(".pl-path", r).value, args: $(".pl-args", r).value }));
  const res = await modal({
    title: "Externe Player", wide: true,
    html: `<div class="hint" style="margin-bottom:10px">Markierte Titel mit einem anderen Programm öffnen (Knopf ⋯ im Player oder Strg/Cmd+P für den ersten Eintrag).
      Argumente: <code>{files}</code> alle Dateien · <code>{file}</code> erste Datei · <code>{folder}</code> Ordner · <code>{m3u}</code> temporäre Playlist.
      Beispiele: foobar2000 <code>/add {files}</code> · VLC <code>--playlist-enqueue {files}</code> · macOS: Programm als <code>/Applications/VLC.app</code>.</div>
      <div id="plList" class="pl-list"></div><button class="ghost sm" id="plAdd" style="width:auto">+ Player hinzufügen</button>`,
    buttons: [{ label: "Abbrechen", value: null }, { label: "Speichern", value: true, primary: true }],
    onMount: (b) => {
      draw(b);
      b.addEventListener("click", async (e) => {
        const t = e.target.closest("button"); if (!t) return;
        if (t.id === "plAdd") { list = read(b); list.push({ name: "", cmd: "", args: "{files}" }); draw(b); $$(".pl-name", b).pop()?.focus(); }
        else if (t.dataset.del !== undefined) { list = read(b); list.splice(+t.dataset.del, 1); draw(b); }
        else if (t.dataset.browse !== undefined) {
          const p = await call("pick_file", "program", "");
          if (p) { list = read(b); list[+t.dataset.browse].cmd = p; if (!list[+t.dataset.browse].name) list[+t.dataset.browse].name = p.split(/[\\/]/).pop().replace(/\.(exe|app|bat|cmd)$/i, ""); draw(b); }
          else if (!S.settings.native) toast("Im Browser-Modus bitte den Pfad eintragen.");
        }
      });
    },
    collect: (b) => read(b),
  });
  if (res === null) return;
  const saved = await call("set_players", res);
  toast(`${saved.length} Player gespeichert.`);
}

// ---------------------------------------------------------------------- Einrichten
/** Einstellungen auf den Player anwenden (Start, „Standard übernehmen“ #93) */
function plApplyPrefs(pp) {
  PLAYER.vol = pp.vol; if (!PLAYER.fade) PLAYER.audio.volume = pp.vol;
  if ($("#plVol")) $("#plVol").value = String(Math.round(pp.vol * 100));
  PLAYER.startAt = pp.start;
  PLAYER.follow = pp.follow;
  PLAYER.wave = pp.wave;
  PLAYER.repeat = !!pp.repeat;
  PLAYER.live = !!pp.live;
  PLAYER.xfade = +pp.xfade || 0; PLAYER.xfadeStart = pp.xfade_start || "start"; PLAYER.xfadeAfter = +pp.xfade_after || 0;
  PLAYER.xfadeSync = pp.xfade_sync !== false; PLAYER.xfadeReturn = pp.xfade_return ?? 8;
  if (typeof pl2Apply === "function") pl2Apply(pp);
  if ($("#plStart")) plStartSync();
  plRender();
}

/** beide Audio-Elemente (zweites für das Überblenden #94): Ereignisse nur vom aktiven auswerten */
function plBindAudio(el) {
  el.preload = "metadata";
  const act = (fn) => (e) => { if (e.target === PLAYER.audio) fn(e); };
  ["play", "pause", "ended", "loadedmetadata", "emptied"].forEach((ev) => el.addEventListener(ev, plRender));
  el.addEventListener("loadedmetadata", act(() => { plCues(); plABDraw(); }));
  el.addEventListener("timeupdate", act(() => { const s = $("#plSeek"); if (!s.matches(":active")) plRender(); if (typeof plXfadeCheck === "function") plXfadeCheck(); }));
  el.addEventListener("ended", act(() => {
    const a = PLAYER.audio;
    if (PLAYER.repeat) { a.currentTime = 0; a.play().catch(() => {}); return; }      // #79
    if (PLAYER.follow && S.module === "tagger") plStep(1);
  }));
  el.addEventListener("error", act(() => { if (PLAYER.audio.src) toast("Datei kann nicht abgespielt werden."); }));
}

function initPlayer() {
  const a = new Audio();
  PLAYER.audio = a;
  PLAYER.spare = new Audio();
  plBindAudio(a); plBindAudio(PLAYER.spare);
  const pp = (S.settings && S.settings.player) || { vol: 0.8, start: "0", follow: true, wave: true, saved: true };
  if (!pp.saved) {          // bis 3.2.0-beta.1 im Browser-Speicher → einmalig in die Einstellungen übernehmen
    const v = parseFloat(plStore("vol")), st = plStore("start");
    if (isFinite(v)) { pp.vol = Math.max(0, Math.min(1, v)); call("set_player_pref", "vol", pp.vol).catch(() => {}); }
    if (st && ["0", "30", "60", "cue"].includes(st)) { pp.start = st; call("set_player_pref", "start", st).catch(() => {}); }
    if (plStore("wave") === "0") { pp.wave = false; call("set_player_pref", "wave", false).catch(() => {}); }
    if (plStore("follow") === "0") { pp.follow = false; call("set_player_pref", "follow", false).catch(() => {}); }
  }
  plApplyPrefs(pp);
  $("#plWave").insertAdjacentHTML("beforeend", '<div class="pl-hover" id="plHover" hidden></div>');
  $("#plWave").addEventListener("mousemove", plHover);
  $("#plWave").addEventListener("mouseleave", plHover);
  window.addEventListener("resize", () => { plCues(); plDrawWave(); });
  $("#plCues").addEventListener("click", (e) => {
    if (e.target.closest("#plABMark")) { plABClear(); toast("Schleife aufgehoben."); return; }
    const b = e.target.closest(".pl-cue"); if (!b || !PLAYER.info) return;
    const c = PLAYER.info.cues[+b.dataset.k];
    if (c.kind === "loop" && c.end) {            // #47: Loop an/aus
      if (PLAYER.loop && PLAYER.loop.k === +b.dataset.k) { plLoopSet(null); toast("Schleife aus."); return; }
      plLoopSet({ pos: c.pos, end: c.end, k: +b.dataset.k });
      toast(`Schleife ${fmtTime(c.pos)}–${fmtTime(c.end)} – erneut klicken zum Beenden.`);
    }
    PLAYER.audio.currentTime = c.pos;
    if (PLAYER.audio.paused) PLAYER.audio.play().catch(() => {});
    plRender();
  });

  $("#plPlay").addEventListener("click", () => plToggle());
  $("#plPrev").addEventListener("click", () => plStep(-1));
  $("#plNext").addEventListener("click", () => plStep(1));
  $("#plSeek").addEventListener("input", (e) => { const x = PLAYER.audio; x.currentTime = (+e.target.value) / 10; plTimes(x.currentTime, x.duration || 0); });
  $("#plStems").addEventListener("click", (e) => { e.stopPropagation(); plStemsMenu(e.currentTarget); });
  document.addEventListener("keydown", plArrowKey, true);     // #64: vor den Handlern der Eingabefelder
  $("#plVol").value = String(Math.round(PLAYER.vol * 100));
  $("#plVol").addEventListener("input", (e) => { PLAYER.vol = (+e.target.value) / 100; if (!PLAYER.fade) PLAYER.audio.volume = PLAYER.vol; plSetPref("vol", PLAYER.vol); });
  plStartSync();
  $("#plStart").addEventListener("click", (e) => { const b = e.target.closest("[data-v]"); if (b) plSetPref("start", b.dataset.v); });
  $("#plCuePrev").addEventListener("click", () => plCueJump(-1));
  $("#plCueNext").addEventListener("click", () => plCueJump(1));
  $("#plAB").addEventListener("click", (e) => { const b = e.target.closest("[data-side]"); if (b) plSide(b.dataset.side); });
  $("#plMore").addEventListener("click", (e) => plMenu(e.currentTarget));
  $("#plRepeat").addEventListener("click", () => { plSetPref("repeat", !PLAYER.repeat); toast(PLAYER.repeat ? "Titel wird wiederholt." : "Titel nicht mehr wiederholen."); });
  $("#plAB2").addEventListener("click", plABStep);
  $("#plLive").addEventListener("click", () => plLiveSet(!PLAYER.live));
  $("#plRate").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (!PLAYER.info) return;
    const t = { kind: PLAYER.kind, ref: PLAYER.kind === "side" ? PLAYER.info.ref : PLAYER.ref };
    if (b.dataset.star) plMarkTarget(t, +b.dataset.star, null); else if (b.dataset.like) plMarkTarget(t, null, "toggle");
  });

  document.addEventListener("keydown", plKeydown);
  if (typeof initPlayer2 === "function") initPlayer2(pp);
  plRender();
}

function plKeydown(e) {
    const ae = document.activeElement;
    const inField = /INPUT|TEXTAREA|SELECT/.test(ae?.tagName || "") && ae?.type !== "range";
    if (inField || !$("#modal").hidden || !$("#dialog").hidden || !$("#xmlEd").hidden) return;
    if (S.module !== "tagger" && S.module !== "compare") return;
    if (typeof dbKey === "function" && dbKey(e)) return;          // #67: Ziel Player B
    if (e.key === " " && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); plToggle(); }
    else if (e.shiftKey && (e.key === "ArrowRight" || e.key === "ArrowLeft") && PLAYER.audio.src) { e.preventDefault(); plSeekBy(e.key === "ArrowRight" ? 10 : -10); }
    else if ((e.key === "s" || e.key === "S") && !e.ctrlKey && !e.metaKey && !e.altKey && PLAYER.audio.src && plStemCycle(e.shiftKey ? -1 : 1)) e.preventDefault();   // #66
    else if ((e.key === "l" || e.key === "L") && !e.ctrlKey && !e.metaKey && !e.altKey && PLAYER.audio.src) { e.preventDefault(); plABStep(); }   // #79
    else if ((e.key === "r" || e.key === "R") && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); $("#plRepeat").click(); }
    else if (e.key === "Escape" && PLAYER.ab) { plABClear(); }
    else if (/^[0-5]$/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); plMark(+e.key, null); }   // #96
    else if ((e.key === "f" || e.key === "F") && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); plMark(null, "toggle"); }   // #95
    else if ((e.key === "m" || e.key === "M") && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); PLAYER.audio.muted = !PLAYER.audio.muted; if (PLAYER.fade) PLAYER.fade.old.muted = PLAYER.audio.muted; plRender(); toast(PLAYER.audio.muted ? "Stumm (M)" : "Ton an"); }   // #49
    else if (e.altKey && (e.key === "PageDown" || e.key === "PageUp") && PLAYER.audio.src) { e.preventDefault(); plCueJump(e.key === "PageDown" ? 1 : -1); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") { e.preventDefault(); call("players").then((l) => plExternal(l.length ? 0 : null)); }
    else if (typeof pl2Key === "function") pl2Key(e);
}
