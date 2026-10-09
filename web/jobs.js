/* MarKusSXCH TagStudio – Hintergrund-Aufträge (#29): Anzeige in der Fußleiste, Liste mit Abbrechen/Ordner,
   Meldung bei Fertigstellung, Fortsetzen der Warteschlange nach einem Neustart. Logik in jobs.py. */
"use strict";

const JOBS = { st: null, polling: false, seen: {}, open: false, notified: false };

const JOB_STATUS = { waiting: "wartet", running: "läuft", done: "fertig", error: "Fehler", cancelled: "abgebrochen" };

function jobPct(j) {
  if (j.status === "done") return 100;
  if (!j.total) return 0;
  return Math.max(0, Math.min(100, Math.round((100 * (j.i + (j.frac || 0))) / j.total)));
}

function jobsRenderChip() {
  const st = JOBS.st, chip = $("#jobsChip");
  if (!st || !st.jobs.length) { chip.hidden = true; return; }
  chip.hidden = false;
  const run = st.running, waiting = st.jobs.filter((j) => j.status === "waiting").length;
  const done = st.jobs.filter((j) => j.status === "done").length, err = st.jobs.filter((j) => j.status === "error").length;
  chip.classList.toggle("idle", !run);
  chip.classList.toggle("done", !st.active && !err);
  chip.classList.toggle("err", !st.active && !!err);
  let text;
  if (run) {
    const name = run.label.split(":")[0];
    text = `${name}: ${Math.min(run.i + 1, run.total)} von ${run.total} · ${jobPct(run)} %${waiting ? ` · ${waiting} wartend` : ""}`;
    chip.style.setProperty("--p", jobPct(run));
  } else if (st.active) text = `${waiting} Auftrag/Aufträge wartend`;
  else text = err ? `${err} Auftrag/Aufträge mit Fehler` : `✓ ${done} Auftrag/Aufträge fertig`;
  $("#jcText").textContent = text;
  chip.title = `Hintergrund-Aufträge: ${text} – Klick zeigt die Liste`;
  if (JOBS.open) jobsRenderList();
}

function jobsRenderList() {
  const box = $("#jobList");
  if (!box || !JOBS.st) return;
  const jobs = [...JOBS.st.jobs].reverse();
  box.innerHTML = jobs.length ? jobs.map((j) => {
    const files = j.names.length > 3 ? `${j.names.slice(0, 3).join(", ")} … (+${j.names.length - 3})` : j.names.join(", ");
    const line = j.status === "running" ? `${JOB_STATUS[j.status]} · ${Math.min(j.i + 1, j.total)} von ${j.total} · ${jobPct(j)} % · ${j.text || ""}`
      : j.status === "error" ? `Fehler: ${j.error}` : j.status === "done" ? (j.message || "fertig") : JOB_STATUS[j.status];
    return `<div class="job" data-id="${esc(j.id)}">
      <div class="t">${esc(j.label)}</div>
      <div class="acts">
        ${j.status === "waiting" || j.status === "running" ? '<button class="ghost sm" data-jcancel="1">Abbrechen</button>' : ""}
        ${j.outputs && j.outputs.length ? `<button class="ghost sm" data-jopen="1" title="${esc(j.outputs[0])}">Ordner öffnen</button>` : ""}
        ${j.logfile ? '<button class="ghost sm" data-jlog="1">Protokoll</button>' : ""}
      </div>
      <div class="f" title="${esc(j.names.join("\n"))}">${esc(files)}</div>
      <div class="s ${j.status}">${esc(line)}</div>
      ${j.status === "running" || j.status === "waiting" ? `<div class="bar"><i style="--p:${jobPct(j)}%"></i></div>` : ""}
    </div>`;
  }).join("") : '<div class="muted">Keine Aufträge.</div>';
}

async function jobsDialog() {
  JOBS.open = true;
  jobsPoll();
  const p = modal({
    title: "Hintergrund-Aufträge", wide: true,
    html: `<p class="muted sm" style="margin:0 0 10px">Lange Plugin-Aktionen (z. B. Stems) laufen hier nacheinander, während du weiterarbeitest. Ergebnis-Dateien entstehen in eigenen Ordnern; die Originale bleiben unverändert.</p>
      <div class="job-list" id="jobList"></div>
      <div style="display:flex;gap:8px;margin-top:10px"><button class="ghost sm" id="jobClear" style="width:auto">Erledigte entfernen</button><button class="ghost sm" id="jobCancelAll" style="width:auto">Alle abbrechen</button></div>`,
    buttons: [{ label: "Schliessen", value: null, primary: true }],
    onMount: (b) => {
      jobsRenderList();
      b.addEventListener("click", async (e) => {
        const t = e.target.closest("button"); if (!t) return;
        const id = t.closest(".job")?.dataset.id, job = id && JOBS.st.jobs.find((j) => j.id === id);
        if (t.id === "jobClear") JOBS.st = await call("jobs_clear");
        else if (t.id === "jobCancelAll") JOBS.st = await call("jobs_cancel_all");
        else if (t.dataset.jcancel) JOBS.st = await call("job_cancel", id);
        else if (t.dataset.jopen && job) call("reveal", job.outputs[0]);
        else if (t.dataset.jlog && job) call("reveal", job.logfile);
        jobsRenderChip(); jobsRenderList();
      });
    },
  });
  await p;
  JOBS.open = false;
}

function jobsNotify(j) {
  const ok = j.status === "done";
  const msg = ok ? `${j.label.split(":")[0]} fertig: ${j.names.length === 1 ? j.names[0] : j.names.length + " Titel"}` : `${j.label}: ${JOB_STATUS[j.status]}${j.error ? " – " + j.error.split("\n")[0] : ""}`;
  toast(msg);
  status(msg, ok ? "ok" : "warn");
  try {
    if (document.hidden && window.Notification && Notification.permission === "granted") new Notification("TagStudio", { body: msg });
  } catch (e) { /* Systemmeldung ist optional */ }
  if (ok && typeof jobFinishedHook === "function") jobFinishedHook(j);
  if (typeof jobFinishedSnapshot === "function") jobFinishedSnapshot(j);
}

async function jobsPoll() {
  if (JOBS.polling) return;
  JOBS.polling = true;
  try {
    for (;;) {
      const st = await call("jobs_status");
      for (const j of st.jobs) {
        const before = JOBS.seen[j.id];
        if (before !== j.status && ["done", "error"].includes(j.status)) jobsNotify(j);   // auch sehr schnelle Aufträge
        JOBS.seen[j.id] = j.status;
      }
      JOBS.st = st;
      jobsRenderChip();
      if (!st.active && !JOBS.open) break;
      await new Promise((r) => setTimeout(r, st.active ? 1000 : 1500));
    }
  } catch (e) { /* nächster Anstoss startet neu */ }
  finally { JOBS.polling = false; }
}

/** Nach „Stems erzeugen …“ usw.: Auftrag wurde angelegt. */
function jobsQueued(res) {
  toast(res.waiting > 1 ? `Auftrag angelegt – ${res.waiting} warten. Du kannst weiterarbeiten.` : "Läuft im Hintergrund – du kannst weiterarbeiten.");
  if (!JOBS.notified && window.Notification && Notification.permission === "default") {
    JOBS.notified = true;
    try { Notification.requestPermission().catch(() => {}); } catch (e) { /* egal */ }
  }
  jobsPoll();
}

async function initJobs() {
  $("#jobsChip").addEventListener("click", jobsDialog);
  let st;
  try { st = await call("jobs_status"); } catch (e) { return; }
  JOBS.st = st;
  st.jobs.forEach((j) => { JOBS.seen[j.id] = j.status; });
  jobsRenderChip();
  if (st.active) jobsPoll();
  if (st.resumable && st.resumable.length) {
    const n = st.resumable.reduce((a, r) => a + r.count, 0);
    const v = await dialog({
      title: "Offene Aufträge fortsetzen?",
      text: `Beim letzten Beenden waren noch ${st.resumable.length} Hintergrund-Auftrag/-Aufträge offen (${n} Titel):\n${st.resumable.map((r) => "• " + r.label).join("\n")}`,
      buttons: [{ label: "Verwerfen", value: false }, { label: "Fortsetzen", value: true, primary: true }],
    });
    const r = await call("jobs_resume", !!v);
    JOBS.st = r; jobsRenderChip();
    if (r.resumed) { toast(`${r.resumed} Auftrag/Aufträge fortgesetzt.`); jobsPoll(); }
  }
}

