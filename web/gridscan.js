/* MarKusSXCH TagStudio – Beatgrid-Status in der Tagger-Bibliothek (#191).
   Spalte „Beatgrid“: Serato-Raster, eigene Analyse, nur BPM-Schätzung, ohne Ergebnis, keins. Der Status kommt aus
   Tags und Wellenform-Cache (kein Dekodieren) und wird im Hintergrund in Paketen geholt. „Beatgrid analysieren …“
   rechnet für markierte Titel dieselbe Analyse wie der Player und legt sie im Cache ab – nie im MP3.
   Nutzt call/esc/toast aus app.js, TG/drawTgList aus tagger.js, plWaveCompute aus player.js. */
"use strict";

const TGG = { scan: false, run: false, stop: false, busy: new Set() };
const TGG_ORDER = ["serato", "analyse", "bpm", "nobeat", "none"];
const TGG_INFO = {
  serato: ["Serato", "Raster aus Serato übernommen (GEOB „Serato BeatGrid“) – nicht automatisch musikalisch geprüft"],
  analyse: ["Analyse", "Eigene Audioanalyse: BPM und erster Schlag bei gleichbleibendem Tempo – Taktanfang und Tempowechsel werden nicht erkannt"],
  bpm: ["nur BPM", "Nur der BPM-Tag – daraus geschätzt, kein Beatgrid. Rechtsklick › „Beatgrid analysieren …“"],
  nobeat: ["ohne Ergebnis", "Audio wurde analysiert, aber kein gleichmässiger Schlag gefunden"],
  none: ["keins", "Weder Serato-Raster noch Analyse noch BPM-Tag. Rechtsklick › „Beatgrid analysieren …“"],
};

function tgGridText(r) {
  if (TGG.busy.has(r.i)) return "läuft";
  return r.grid ? TGG_INFO[r.grid]?.[0] || r.grid : "nicht geprüft";
}
function tgGridOrder(r) { const k = TGG_ORDER.indexOf(r.grid); return k < 0 ? Infinity : k; }
function tgGridCell(r) {
  if (TGG.busy.has(r.i)) return '<span class="tg-grid run" title="Beatgrid-Analyse läuft">läuft …</span>';
  if (!r.grid) return '<span class="tg-grid" title="Noch nicht geprüft">–</span>';
  const [l, t] = TGG_INFO[r.grid] || [r.grid, ""];
  return `<span class="tg-grid g-${esc(r.grid)}" title="${esc(t)}">${esc(l)}</span>`;
}

/** Spalte sichtbar und Titel ohne Status → im Hintergrund in Paketen nachholen (abbrechbar über den Chip). */
async function tgGridMaybeScan() {
  if (TGG.scan || !TG.loaded || !tgCols().includes("grid")) return;
  const todo = TG.rows.filter((r) => !r.grid).map((r) => r.i);
  if (!todo.length) return;
  TGG.scan = true; TGG.stop = false;
  const chip = $("#waveChip"), own = chip && chip.hidden;
  if (own) { chip.hidden = false; chip.onclick = () => { TGG.stop = true; }; }
  try {
    for (let k = 0; k < todo.length && !TGG.stop; k += 150) {
      if (own) { $("#wcText").textContent = `Beatgrid prüfen ${Math.min(k + 150, todo.length)} / ${todo.length}`; chip.title = "Beatgrid-Status aus Tags und Cache · Klick: abbrechen"; $(".jc-ring", chip).style.setProperty("--p", Math.round(k / todo.length * 100)); }
      const r = await call("tag_grid_status", todo.slice(k, k + 150), false);
      for (const [i, code] of Object.entries(r.status || {})) { const row = TG.rows[+i]; if (row) row.grid = code; }
      drawTgList();
    }
  } catch (e) { /* Status ist eine Zusatzinfo – Fehler nicht aufdrängen */ }
  finally { TGG.scan = false; if (own) chip.hidden = true; }
}

/** Markierte Titel ohne Raster analysieren (wie im Player) – fortlaufend, abbrechbar, nur Cache. */
async function tgGridAnalyse(idx) {
  if (TGG.run || (typeof WAVEBG !== "undefined" && WAVEBG.run)) { toast("Es läuft bereits eine Analyse."); return; }
  const list = (idx || []).filter((i) => TG.rows[i] && !["serato", "analyse"].includes(TG.rows[i].grid));
  if (!list.length) { toast("Die markierten Titel haben schon ein Serato-Raster oder eine Analyse."); return; }
  const chip = $("#waveChip");
  TGG.run = true; TGG.stop = false;
  chip.hidden = false; chip.onclick = () => { TGG.stop = true; chip.title = "wird abgebrochen …"; };
  let done = 0, found = 0;
  try {
    for (const i of list) {
      if (TGG.stop) break;
      const row = TG.rows[i];
      $("#wcText").textContent = `Beatgrid ${done + 1} / ${list.length}`;
      chip.title = `${row ? row.name : ""}\nKlick: abbrechen`;
      $(".jc-ring", chip).style.setProperty("--p", Math.round(done / list.length * 100));
      TGG.busy.add(i); drawTgList();
      try {
        const info = await call("media_url", "tag", i);
        if (!(info.grid && info.grid.exact)) await plWaveCompute(info);
        const st = await call("tag_grid_status", [i], true);
        const code = (st.status || {})[i];
        if (row && code) row.grid = code;
        if (code === "analyse" || code === "serato") found++;
      } catch (e) { /* Datei nicht lesbar – weiter mit der nächsten */ }
      TGG.busy.delete(i); done++;
      drawTgList();
    }
  } finally {
    TGG.busy.clear(); TGG.run = false; chip.hidden = true; drawTgList();
  }
  const msg = `Beatgrid-Analyse: ${found} von ${done} Titel(n) mit Ergebnis${TGG.stop ? " (abgebrochen)" : ""}. Gespeichert im Cache, nicht im MP3.`;
  status(msg, TGG.stop ? "warn" : "ok"); toast(msg);
}
