/* MarKusSXCH TagStudio – Vorschau-Player (unten in der Aktionsleiste) und externe Player.
   Leertaste: markierten Titel abspielen/pausieren · Shift+←/→: ±10 s · Strg/Cmd+P: im externen Player öffnen.
   Im Tagger spielt der Player beim Wechsel der Markierung (↑/↓, Klick) automatisch weiter („Durchhören“).
   Im Vergleich schaltet A/B zwischen linker und rechter Datei um und behält die Position. */
"use strict";

const PLAYER = { audio: null, info: null, kind: null, ref: null, side: "L", loading: false, follow: true, startAt: "0" };

const ICON_PLAY = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4v16l13-8Z"/></svg>';
const ICON_PAUSE = '<svg class="i" viewBox="0 0 24 24"><path d="M7 4h3v16H7zM14 4h3v16h-3z"/></svg>';

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

async function plLoad(target, autoplay = true, keepTime = null) {
  if (!target) { toast(S.module === "tagger" ? "Erst einen Titel markieren." : "Erst ein Dateipaar wählen."); return; }
  PLAYER.loading = true;
  let info;
  try { info = await call("media_url", target.kind, target.ref); } catch (e) { PLAYER.loading = false; toast(String(e.message || e)); return; }
  PLAYER.info = info; PLAYER.kind = target.kind; PLAYER.ref = target.ref;
  const a = PLAYER.audio;
  a.src = info.url;
  const dur = info.duration || 0;
  const start = keepTime !== null ? keepTime : PLAYER.startAt === "30" ? dur * 0.3 : PLAYER.startAt === "60" ? Math.min(60, dur * 0.5) : 0;
  const seek = () => { try { if (start > 0) a.currentTime = Math.min(start, (a.duration || dur) - 1); } catch (e) { /* egal */ } };
  a.addEventListener("loadedmetadata", seek, { once: true });
  plRender();
  if (autoplay) {
    try { await a.play(); } catch (e) {
      // AbortError: schneller Titelwechsel – der neue Titel lädt bereits, kein Fehler
      if (e.name !== "AbortError") toast("Wiedergabe nicht möglich: " + (e.message || e));
    }
  }
  PLAYER.loading = false;
}

function plSame(t) { return t && PLAYER.info && t.kind === PLAYER.kind && t.ref === PLAYER.ref; }

async function plToggle() {
  const t = plTarget();
  if (!PLAYER.audio.src || (t && !plSame(t) && !(t.kind === "side" && PLAYER.kind === "side"))) return plLoad(t);
  if (t && t.kind === "side" && PLAYER.kind === "side" && PLAYER.info && PLAYER.info.ref !== PLAYER.side) return plLoad(t, true);
  if (PLAYER.audio.paused) { try { await PLAYER.audio.play(); } catch (e) { toast(String(e.message || e)); } } else PLAYER.audio.pause();
}

/** Markierung hat sich geändert (Tagger/Vergleich): beim Abspielen gleich weiter mit dem neuen Titel. */
function playerFollow() {
  if (!PLAYER.audio || PLAYER.audio.paused || !PLAYER.follow || PLAYER.loading) { plRender(); return; }
  const t = plTarget();
  if (t && !plSame(t)) plLoad(t, true);
}

async function plStep(dir) {
  if (S.module === "tagger" && TG.order.length) {
    const k = Math.max(0, Math.min(TG.order.length - 1, TG.order.indexOf(TG.anchor) + dir));
    const i = TG.order[k];
    const wasPlaying = !PLAYER.audio.paused;
    await tgSelect(i, {});          // beim Abspielen übernimmt playerFollow() den neuen Titel
    tgScrollTo(i);
    if (!wasPlaying) plLoad(plTarget(), true);
  } else if (S.module === "compare" && S.visible && S.visible.length) {
    const k = Math.max(0, Math.min(S.visible.length - 1, S.visible.indexOf(S.cur) + dir));
    const wasPlaying = !PLAYER.audio.paused;
    await selectPair(S.visible[k]);
    if (!wasPlaying) plLoad(plTarget(), true);
  }
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
  const dur = a.duration || (i && i.duration) || 0;
  $("#plTime").textContent = i ? `${fmtTime(a.currentTime)} / ${fmtTime(dur)}` : "";
  const seek = $("#plSeek");
  if (!seek.matches(":active")) { seek.max = String(Math.max(1, Math.round(dur * 10))); seek.value = String(Math.round(a.currentTime * 10)); }
  seek.disabled = !i;
  $("#plAB").hidden = S.module !== "compare";
  $$("#plAB button").forEach((b) => b.classList.toggle("on", b.dataset.side === PLAYER.side));
}

function plSeekBy(sec) {
  if (!PLAYER.audio.src) return;
  PLAYER.audio.currentTime = Math.max(0, Math.min((PLAYER.audio.duration || 0) - 0.5, PLAYER.audio.currentTime + sec));
  plRender();
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
  showMenu(r.left, r.top - 8 - (list.length + 3) * 34, [
    ...list.map((p, k) => ({ label: `Öffnen mit ${p.name}` + (k === 0 ? "  (Strg/Cmd+P)" : ""), run: () => plExternal(k) })),
    { label: "Öffnen mit Standardprogramm" + (list.length ? "" : "  (Strg/Cmd+P)"), run: () => plExternal(null) },
    "-",
    { label: "Player einrichten …", run: () => plSetup() },
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
function initPlayer() {
  const a = new Audio();
  a.preload = "metadata";
  PLAYER.audio = a;
  const vol = parseFloat(plStore("vol") ?? "0.8");
  a.volume = isFinite(vol) ? Math.max(0, Math.min(1, vol)) : 0.8;
  PLAYER.startAt = plStore("start") || "0";
  PLAYER.follow = plStore("follow") !== "0";
  ["play", "pause", "ended", "loadedmetadata", "emptied"].forEach((ev) => a.addEventListener(ev, plRender));
  a.addEventListener("timeupdate", () => { const s = $("#plSeek"); if (!s.matches(":active")) plRender(); });
  a.addEventListener("ended", () => { if (PLAYER.follow && S.module === "tagger") plStep(1); });
  a.addEventListener("error", () => { if (a.src) toast("Datei kann nicht abgespielt werden."); });

  $("#plPlay").addEventListener("click", () => plToggle());
  $("#plPrev").addEventListener("click", () => plStep(-1));
  $("#plNext").addEventListener("click", () => plStep(1));
  $("#plSeek").addEventListener("input", (e) => { a.currentTime = (+e.target.value) / 10; $("#plTime").textContent = `${fmtTime(a.currentTime)} / ${fmtTime(a.duration)}`; });
  $("#plVol").value = String(Math.round(a.volume * 100));
  $("#plVol").addEventListener("input", (e) => { a.volume = (+e.target.value) / 100; plStore("vol", a.volume); });
  $("#plStart").value = PLAYER.startAt;
  $("#plStart").addEventListener("change", (e) => { PLAYER.startAt = e.target.value; plStore("start", PLAYER.startAt); });
  $("#plAB").addEventListener("click", (e) => { const b = e.target.closest("[data-side]"); if (b) plSide(b.dataset.side); });
  $("#plMore").addEventListener("click", (e) => plMenu(e.currentTarget));

  document.addEventListener("keydown", (e) => {
    const inField = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName || "") && document.activeElement?.type !== "range";
    if (inField || !$("#modal").hidden || !$("#dialog").hidden || !$("#xmlEd").hidden) return;
    if (S.module !== "tagger" && S.module !== "compare") return;
    if (e.key === " " && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); plToggle(); }
    else if (e.shiftKey && (e.key === "ArrowRight" || e.key === "ArrowLeft") && PLAYER.audio.src) { e.preventDefault(); plSeekBy(e.key === "ArrowRight" ? 10 : -10); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") { e.preventDefault(); call("players").then((l) => plExternal(l.length ? 0 : null)); }
  });
  plRender();
}
