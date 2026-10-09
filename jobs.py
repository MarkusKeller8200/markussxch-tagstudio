"""MarKusSXCH TagStudio – Hintergrund-Aufträge (Warteschlange für lange Plugin-Aktionen wie Stems).

Aufträge laufen nacheinander (immer nur einer gleichzeitig – Rechenlast) in einem eigenen Thread, während die
Oberfläche benutzbar bleibt. Jeder Auftrag hat Status wartet/läuft/fertig/Fehler/abgebrochen, Fortschritt und
Ergebnis. Offene Aufträge (wartend oder laufend) werden in ~/TagStudio/Auftraege.json vermerkt, damit sie nach
einem Neustart fortgesetzt werden können. Die eigentliche Arbeit macht `runner(job, cancel, progress)`.
Nur Standardbibliothek.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

STATE_FILE = None          # Standard: ~/TagStudio/Auftraege.json (zur Laufzeit bestimmt; Tests setzen einen Pfad)
KEEP_DONE = 50
ACTIVE = ("waiting", "running")


class JobManager:
    def __init__(self, runner, state_file: str | None = None):
        self.runner = runner
        self.state_file = state_file or STATE_FILE or os.path.join(os.path.expanduser("~"), "TagStudio", "Auftraege.json")
        self.jobs: list[dict] = []
        self.cancels: dict[str, threading.Event] = {}
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.thread: threading.Thread | None = None
        self.seq = 0          # steigt bei jeder Änderung – die Oberfläche erkennt Neues
        self.resumable = self._read_state()

    # ------------------------------------------------------------------ Anlegen / Steuern
    def add(self, plugin: str, action: str, label: str, paths: list[str], opts: dict, names=None) -> dict:
        job = {"id": uuid.uuid4().hex[:12], "plugin": plugin, "action": action, "label": label,
               "paths": list(paths), "names": list(names or [os.path.basename(p) for p in paths]), "opts": dict(opts),
               "status": "waiting", "i": 0, "total": len(paths), "frac": 0.0, "text": "wartet …",
               "created": time.time(), "started": None, "finished": None, "message": "", "error": "",
               "outputs": [], "logfile": "", "log": []}
        with self.lock:
            self.jobs.append(job)
            self.cancels[job["id"]] = threading.Event()
            self._changed()
        self._ensure_thread()
        self.wake.set()
        return dict(job)

    def cancel(self, jid: str) -> bool:
        with self.lock:
            job = self._get(jid)
            if job is None or job["status"] not in ACTIVE:
                return False
            self.cancels[jid].set()
            if job["status"] == "waiting":
                job.update(status="cancelled", text="abgebrochen", finished=time.time())
            self._changed()
            return True

    def cancel_all(self) -> int:
        with self.lock:
            ids = [j["id"] for j in self.jobs if j["status"] in ACTIVE]
        return sum(self.cancel(j) for j in ids)

    def clear_finished(self) -> int:
        with self.lock:
            before = len(self.jobs)
            self.jobs = [j for j in self.jobs if j["status"] in ACTIVE]
            for jid in [k for k in self.cancels if not self._get(k)]:
                del self.cancels[jid]
            self._changed()
            return before - len(self.jobs)

    def shutdown(self, keep_queue=True, wait=3.0):
        """Beim Beenden: laufenden Auftrag abbrechen. keep_queue=True: offene Aufträge bleiben für den nächsten
        Start vermerkt; sonst wird die Warteschlange verworfen."""
        with self.lock:
            pending = [self._persist(j) for j in self.jobs if j["status"] in ACTIVE]
            running = [j for j in self.jobs if j["status"] == "running"]
            for j in running:
                self.cancels[j["id"]].set()
            for j in self.jobs:
                if j["status"] == "waiting":
                    j["status"] = "cancelled"
        t0 = time.time()
        while running and time.time() - t0 < wait and any(j["status"] == "running" for j in running):
            time.sleep(0.1)
        self._write_state(pending if keep_queue else [])

    # ------------------------------------------------------------------ Fortsetzen nach Neustart
    def resume(self, accept: bool) -> int:
        items, self.resumable = self.resumable, []
        n = 0
        if accept:
            for it in items:
                paths = [p for p in it.get("paths", []) if os.path.isfile(p)]
                if paths:
                    self.add(it["plugin"], it["action"], it.get("label", it["action"]), paths, it.get("opts", {}))
                    n += 1
        if not n:
            self._write_state([])
        return n

    # ------------------------------------------------------------------ Status
    def status(self) -> dict:
        with self.lock:
            jobs = [{k: v for k, v in j.items() if k not in ("paths", "opts")} for j in self.jobs]
            active = [j for j in jobs if j["status"] in ACTIVE]
            run = next((j for j in jobs if j["status"] == "running"), None)
            return {"seq": self.seq, "jobs": jobs, "active": len(active), "running": run,
                    "resumable": [{"label": r.get("label", ""), "count": len(r.get("paths", []))} for r in self.resumable]}

    # ------------------------------------------------------------------ intern
    def _get(self, jid):
        return next((j for j in self.jobs if j["id"] == jid), None)

    def _changed(self):
        self.seq += 1
        done = [j for j in self.jobs if j["status"] not in ACTIVE]
        if len(done) > KEEP_DONE:
            drop = {j["id"] for j in done[:len(done) - KEEP_DONE]}
            self.jobs = [j for j in self.jobs if j["id"] not in drop]
        self._write_state([self._persist(j) for j in self.jobs if j["status"] in ACTIVE])

    @staticmethod
    def _persist(j):
        return {"plugin": j["plugin"], "action": j["action"], "label": j["label"], "paths": j["paths"], "opts": j["opts"]}

    def _read_state(self) -> list:
        try:
            with open(self.state_file, encoding="utf-8") as fh:
                data = json.load(fh)
            return [d for d in data.get("pending", []) if isinstance(d, dict) and d.get("plugin") and d.get("paths")]
        except (OSError, ValueError, AttributeError):
            return []

    def _write_state(self, pending):
        try:
            if not pending and not os.path.exists(self.state_file):
                return
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            pending = pending + [r for r in self.resumable if r not in pending]
            with open(self.state_file, "w", encoding="utf-8") as fh:
                json.dump({"pending": pending}, fh, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def _ensure_thread(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, daemon=True, name="TagStudio-Auftraege")
                self.thread.start()

    def _loop(self):
        while True:
            with self.lock:
                job = next((j for j in self.jobs if j["status"] == "waiting"), None)
                if job is not None:
                    job.update(status="running", started=time.time(), text="startet …")
                    self._changed()
            if job is None:
                self.wake.clear()
                if not self.wake.wait(30):
                    with self.lock:
                        if not any(j["status"] == "waiting" for j in self.jobs):
                            self.thread = None
                            return
                continue
            self._run(job)

    def _run(self, job):
        cancel = self.cancels[job["id"]]

        def progress(m):
            with self.lock:
                if m[0] == "progress":
                    job["i"], job["total"] = m[1], m[2]
                    job["text"] = os.path.basename(str(m[3])) if m[3] else job["text"]
                    job["frac"] = max(0.0, min(1.0, float(m[4]))) if len(m) > 4 and m[4] is not None else 0.0
                elif m[0] == "text":
                    job["text"] = str(m[1])
                elif m[0] == "total":
                    job["total"] = m[1]
                self.seq += 1
        try:
            res = self.runner(job, cancel, progress) or {}
            with self.lock:
                if res.get("cancelled") or cancel.is_set():
                    job.update(status="cancelled", text="abgebrochen")
                else:
                    job.update(status="done", text="fertig", i=job["total"], frac=0.0)
                job.update(message=str(res.get("message") or ""), outputs=list(res.get("outputs") or []),
                           logfile=str(res.get("logfile") or ""), log=[str(x) for x in (res.get("log") or [])][-60:])
        except Exception as ex:  # noqa: BLE001 – ein Auftrag darf die Warteschlange nicht anhalten
            with self.lock:
                if cancel.is_set():
                    job.update(status="cancelled", text="abgebrochen")
                else:
                    job.update(status="error", error=str(ex) or type(ex).__name__, text="Fehler")
        finally:
            with self.lock:
                job["finished"] = time.time()
                self._changed()
