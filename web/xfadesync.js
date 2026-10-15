/* #181: Übergänge im Takt halten und messen (Player A, automatisches Überblenden).
 *
 * Problem: Die Phase des Folgetitels wird einmal berechnet und per Seek (`currentTime = …`) gesetzt. Während der
 * Seek-/Decoder-Anlaufzeit läuft der alte Titel weiter – danach liegt der neue um genau diese Zeit zurück. Ein
 * zweiter Seek hätte dieselbe Verzögerung.
 *
 * Lösung (wie ein DJ am Jogwheel):
 *  1. Beide Medienuhren über die geglättete Uhr des Metronoms (plClockSample/plClockEstimate) zum SELBEN Zeitpunkt
 *     schätzen und daraus den Beat-Versatz in Millisekunden berechnen (beide Elemente spielen über dieselbe Ausgabe,
 *     ihre currentTime-Werte sind also vergleichbar).
 *  2. Den Rest-Versatz während des Überblendens mit einer kleinen Tempo-Korrektur des Folgetitels (höchstens ±4 %)
 *     wegregeln – ohne Seek, also ohne Aussetzer.
 *  3. Den beim Start gemessenen Versatz merken und beim nächsten Übergang schon beim Seek einrechnen
 *     (gelernte Startverzögerung, Einstellung „xfade_seek_ms“).
 *  4. Jeden Übergang mit Messwerten ins App-Protokoll schreiben (Einstellungen › Expert › app.log, „Übergang“).
 */
"use strict";

const PL_XSYNC = { deadMs: 4, closeSec: 1.0, maxNudge: 0.04, minStep: 0.0015, learn: 0.7, maxLog: 20 };

/** Beat-Versatz des neuen Titels gegenüber dem alten in Millisekunden (Wanduhr).
 * > 0: neuer Titel ist VORAUS (seine Schläge kommen früher), < 0: er liegt zurück. Gewickelt auf ±½ Schlag. */
function plXsyncError(gOld, tOld, gNew, tNew, rateNew) {
  if (!gOld || !gNew || !Number.isFinite(tOld) || !Number.isFinite(tNew)) return null;
  const d0 = gridBeatAt(gNew, tNew) - gridBeatAt(gOld, tOld);
  const d = d0 - Math.round(d0);
  const bpm = plXsyncLocalBpm(gNew, tNew), rate = rateNew > 0 ? rateNew : 1;
  return d * 60 / (bpm * rate) * 1000;
}
/** BPM des Rasters an der Stelle t (variable Marker) */
function plXsyncLocalBpm(g, t) {
  const m = g.markers;
  let k = 0;
  while (k < m.length - 1 && t >= m[k + 1].pos) k++;
  return m[k].bpm || g.bpm;
}
/** Tempo-Korrektur (relativ, z. B. -0.02) für einen Fehler e (ms, bezogen auf das Ziel).
 * Voraus → langsamer, zurück → schneller. Totband gegen Zittern, Begrenzung gegen hörbares Leiern. */
function plXsyncNudge(eMs) {
  if (!Number.isFinite(eMs) || Math.abs(eMs) <= PL_XSYNC.deadMs) return 0;
  const n = -(eMs / 1000) / PL_XSYNC.closeSec;
  return Math.max(-PL_XSYNC.maxNudge, Math.min(PL_XSYNC.maxNudge, n));
}
/** Gelernte Startverzögerung nachführen: neuer Wert für den Seek-Vorhalt (ms, Wanduhr). */
function plXsyncLearn(prevMs, startErrMs) {
  if (!Number.isFinite(startErrMs)) return prevMs || 0;
  const v = (prevMs || 0) - startErrMs * PL_XSYNC.learn;
  return Math.max(-500, Math.min(500, Math.round(v)));
}

/** Regler für einen Übergang anlegen (in plCrossfade, nachdem der neue Titel spielt). */
function plXsyncStart(f, ctx) {
  f.sync = {
    gOld: ctx.gOld, gNew: ctx.gNew, ratio: ctx.ratio, lock: !!ctx.lock, targetMs: -(ctx.manualMs || 0),
    clkOld: { samples: [] }, clkNew: { samples: [] }, t0: null, lastRate: ctx.ratio,
    startErr: null, startAt: null, err: null, maxNudge: 0, trace: [], lastTrace: -1e9, settledN: 0,
    info: ctx.info
  };
}
/** Ein Regelschritt (aus dem Überblend-Takt, alle 40 ms). */
function plXsyncTick(f, oldEl, newEl, now = performance.now()) {
  const s = f && f.sync;
  if (!s || !oldEl || !newEl) return;
  if (s.t0 === null) s.t0 = now;
  const rOld = oldEl.playbackRate || 1, rNew = newEl.playbackRate || 1;
  plClockSample(s.clkOld, now, oldEl.currentTime, rOld);
  if (plClockSample(s.clkNew, now, newEl.currentTime, rNew)) s.settledN = 0;
  const tOld = plClockEstimate(s.clkOld, now, rOld), tNew = plClockEstimate(s.clkNew, now, rNew);
  if (tOld === null || tNew === null) return;
  const err = plXsyncError(s.gOld, tOld, s.gNew, tNew, rNew);
  if (err === null) return;
  const e = err - s.targetMs;
  s.err = e; s.settledN++;
  if (s.startErr === null) { s.startErr = e; s.startAt = Math.round(now - s.t0); }
  if (now - s.lastTrace >= 500) { s.trace.push([Math.round(now - s.t0), Math.round(e)]); s.lastTrace = now; }
  if (!s.lock) return;
  const n = plXsyncNudge(e), rate = s.ratio * (1 + n);
  s.maxNudge = Math.max(s.maxNudge, Math.abs(n));
  if (Math.abs(rate - s.lastRate) >= s.ratio * PL_XSYNC.minStep || (n === 0 && rate !== s.lastRate)) {
    newEl.playbackRate = rate;
    s.lastRate = rate;
    plClockReset(s.clkNew);              // Steigung ändert sich → neu einschwingen, sonst falsche Schätzung
  }
}
/** Übergang beenden: Korrektur zurücknehmen, Messwerte protokollieren, Startverzögerung lernen. */
function plXsyncStop(f, newEl, reason = "fertig") {
  const s = f && f.sync;
  if (!s) return null;
  f.sync = null;
  if (newEl && s.lock && s.lastRate !== s.ratio) newEl.playbackRate = s.ratio;
  const entry = {
    reason, from: s.info.from, to: s.info.to, bpm_old: s.info.bpmOld, bpm_new: s.info.bpmNew,
    grid_old: s.info.srcOld, grid_new: s.info.srcNew, ratio: +s.ratio.toFixed(4), bar: s.info.bar,
    manual_ms: s.info.manualMs, pre_ms: s.info.preMs, lock: s.lock,
    start_err_ms: s.startErr === null ? null : Math.round(s.startErr), settled_after_ms: s.startAt,
    end_err_ms: s.err === null ? null : Math.round(s.err), max_nudge_pct: +(s.maxNudge * 100).toFixed(2),
    trace: s.trace
  };
  if (s.lock && s.startErr !== null && reason === "fertig") {
    const nv = plXsyncLearn(s.info.preMs, s.startErr);
    if (nv !== (PLAYER.xfadeSeekMs || 0)) {
      PLAYER.xfadeSeekMs = nv;
      if (typeof call === "function") call("set_player_pref", "xfade_seek_ms", nv).catch(() => {});
    }
    entry.learned_pre_ms = nv;
  }
  PLAYER.xfadeLog = (PLAYER.xfadeLog || []).concat([entry]).slice(-PL_XSYNC.maxLog);
  if (typeof call === "function") call("player_log", entry).catch(() => {});
  return entry;
}
/** Kurzbeschreibung eines Grids für das Protokoll */
function plXsyncSrc(info) {
  const g = info && info.grid;
  if (!g) return "keins";
  return g.source || (g.exact ? "Serato" : g.analysed ? "Analyse" : "BPM");
}
/** Dateiname ohne Pfad (Protokoll) */
function plXsyncName(info) {
  const p = String((info && (info.path || info.name || info.title)) || "");
  return p.split(/[\\/]/).pop();
}

/** Messwerte der letzten Übergänge (dieser Sitzung) anzeigen */
function plXsyncLogDialog() {
  const rows = (PLAYER.xfadeLog || []).slice().reverse();
  const ms = (v) => v === null || v === undefined ? "–" : (v > 0 ? "+" : "") + v + " ms";
  const body = rows.length ? `<table class="help-t"><thead><tr><th>Von → Nach</th><th>Raster</th><th>Start</th><th>Ende</th>
      <th>Korrektur max.</th><th>Vorhalt</th></tr></thead><tbody>${rows.map((r) => `<tr>
      <td>${esc(r.from)}<br>→ ${esc(r.to)}${r.reason !== "fertig" ? ` <span class="muted">(${esc(r.reason)})</span>` : ""}</td>
      <td>${esc(r.grid_old)} / ${esc(r.grid_new)}<br><span class="muted">${r.bpm_old} → ${r.bpm_new} BPM${r.bar > 1 ? ` · ${r.bar} Schläge` : ""}</span></td>
      <td>${ms(r.start_err_ms)}</td><td>${ms(r.end_err_ms)}</td><td>${r.lock ? r.max_nudge_pct + " %" : "aus"}</td>
      <td>${ms(r.pre_ms)}${r.learned_pre_ms !== undefined ? `<br><span class="muted">neu ${ms(r.learned_pre_ms)}</span>` : ""}</td></tr>`).join("")}
      </tbody></table>`
    : `<p class="muted">Noch keine gemessenen Übergänge in dieser Sitzung. Gemessen wird beim automatischen Überblenden
       in Player A mit „Im Takt“ und Beatgrid bei beiden Titeln.</p>`;
  return modal({
    title: "Übergänge – Messwerte", wide: true,
    html: `<p class="muted sm">Versatz des Folgetitels zum laufenden Titel: + = zu früh, − = zu spät (Ziel: 0 bzw. die
      Folgetrack-Korrektur). „Start“ = kurz nach dem Einsetzen, „Ende“ = beim Abschluss des Überblendens.
      Alle Übergänge stehen auch im App-Protokoll (Einstellungen › Expert, Zeilen „Übergang“).</p>${body}`,
    buttons: [{ label: "Schliessen", value: null, primary: true }]
  });
}
