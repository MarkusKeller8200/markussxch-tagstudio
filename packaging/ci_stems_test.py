"""Echter Ende-zu-Ende-Test des Stems-Plugins (läuft in GitHub Actions, Workflow „Stems-Test“).

    python packaging/ci_stems_test.py [variante] [modell]

1. Erzeugt einen synthetischen Test-Titel (Bass, Kick, Hi-Hat, „Gesang“-Melodie) als MP3 – keine echte Musik,
   damit keine urheberrechtlich geschützten Dateien nötig sind.
2. Installiert die Stems-Umgebung genau wie die App (Session.start_plugin_install → uv, Python 3.12, PyTorch …).
3. Trennt den Titel über den Tagger (Session.start_plugin_action) und zeichnet dabei den Fortschritt auf.
4. Prüft: Installation ok, Fortschritt bewegt sich innerhalb des Titels (frac > 0 vor dem Ende), Spuren vorhanden,
   MP3-Spuren mit übernommenen Tags.
Ergebnis in stems-test.txt (wird als Anmerkung im Workflow angezeigt). Exitcode 0 = bestanden.
"""
import math
import os
import random
import struct
import subprocess
import sys
import tempfile
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "stems-test.txt")
LINES = []


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LINES.append(line)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES) + "\n")


def make_track(path_mp3, seconds=90, sr=44100):
    """Synthetischer Titel mit klar getrennten Klangquellen (124 BPM)."""
    rnd = random.Random(1)
    beat = 60 / 124
    n = seconds * sr
    frames = bytearray()
    melody = [0, 3, 5, 7, 5, 3, 0, -2]
    for i in range(n):
        t = i / sr
        tb = t % beat
        kick = math.sin(2 * math.pi * (50 + 80 * math.exp(-tb * 30)) * tb) * math.exp(-tb * 8) * 0.8
        hat_t = (t + beat / 2) % beat
        hat = (rnd.random() * 2 - 1) * math.exp(-hat_t * 60) * 0.25
        bass = math.sin(2 * math.pi * 55 * t) * 0.35 * (0.6 + 0.4 * math.sin(2 * math.pi * t / beat))
        note = melody[int(t / (beat * 2)) % len(melody)]
        f = 440 * 2 ** (note / 12)
        vib = 1 + 0.01 * math.sin(2 * math.pi * 5.5 * t)
        voice = (math.sin(2 * math.pi * f * vib * t) + 0.4 * math.sin(4 * math.pi * f * vib * t)) * 0.25
        s = max(-1.0, min(1.0, kick + hat + bass + voice))
        v = int(s * 30000)
        frames += struct.pack("<hh", v, v)
    wav = path_mp3[:-4] + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", "-id3v2_version", "3",
                    "-metadata", "title=Stems Testtitel", "-metadata", "artist=TagStudio CI", path_mp3], check=True)
    os.remove(wav)


def wait(s, what, timeout, on_tick=None):
    t0 = time.time()
    while True:
        st = s.task_status()
        if on_tick:
            on_tick(st)
        if st.get("done"):
            return st
        if time.time() - t0 > timeout:
            raise SystemExit(f"Zeitüberschreitung bei {what}")
        time.sleep(0.5)


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "cpu"
    model = sys.argv[2] if len(sys.argv) > 2 else "htdemucs.yaml"
    home = tempfile.mkdtemp(prefix="ts_home_")
    os.environ["HOME"] = os.environ["USERPROFILE"] = home     # eigene Einstellungen/Plugin-Daten
    music = os.path.join(home, "Musik")
    os.makedirs(music)
    mp3 = os.path.join(music, "01 Stems Test.mp3")
    make_track(mp3)
    log(f"Testtitel erzeugt: {os.path.getsize(mp3)} Bytes · Variante {variant} · Modell {model} · {sys.platform}")

    # Nachbau eines Benutzer-PCs mit einem fremden, abgespeckten „ffmpeg“ im PATH (ohne MP3-Encoder):
    # Stems muss trotzdem das eigene, vollständige FFmpeg verwenden.
    bad = os.path.join(home, "fremdes-ffmpeg")
    os.makedirs(bad)
    if os.name == "nt":
        with open(os.path.join(bad, "ffmpeg.bat"), "w") as fh:
            fh.write("@echo Encoder not found (fremdes ffmpeg) 1>&2\r\n@exit /b 3\r\n")
    else:
        fp = os.path.join(bad, "ffmpeg")
        with open(fp, "w") as fh:
            fh.write("#!/bin/sh\necho 'Encoder not found (fremdes ffmpeg)' >&2\nexit 3\n")
        os.chmod(fp, 0o755)
    os.environ["PATH"] = bad + os.pathsep + os.environ.get("PATH", "")
    import shutil
    log(f"Fremdes ffmpeg im PATH: {shutil.which('ffmpeg')}")

    from session import Session
    s = Session()
    info = {p["id"]: p for p in s.plugins_list(True)["plugins"]}
    log(f"Stems vor Installation: {info['stems']['state']}")

    t0 = time.time()
    r = s.start_plugin_install("stems", variant)
    if not r.get("ok"):
        raise SystemExit(f"Installation nicht gestartet: {r}")
    texts = []
    st = wait(s, "Installation", 3600, lambda x: texts.append(x.get("text", "")) if x.get("text") and (not texts or texts[-1] != x.get("text")) else None)
    res = st.get("result") or {}
    log(f"Installation fertig nach {time.time() - t0:.0f} s · ok: {res.get('ok')} · {res.get('message') or st.get('error') or ''}")
    for t in texts[-8:]:
        log(f"  Installation: {t[:160]}")
    if st.get("error") or not res.get("ok"):
        for line in (res.get("log") or [])[-25:]:
            log(f"  {str(line)[:200]}")
        raise SystemExit("Installation fehlgeschlagen")
    info = {p["id"]: p for p in s.plugins_list(True)["plugins"]}
    log(f"Stems nach Installation: {info['stems']['state']} ({info['stems'].get('env_variant')})")
    if info["stems"]["state"] != "ready":
        raise SystemExit("Stems nicht bereit")

    s.start_tag_load(music, False)
    wait(s, "Einlesen", 120)
    samples = []

    def tick(x):
        samples.append((round(time.time() - t1, 1), x.get("i"), x.get("total"), round(x.get("frac") or 0, 3), x.get("text", "")))

    t1 = time.time()
    r = s.start_plugin_action("stems", "separate", [0], {"model": model, "format": "MP3", "overwrite": True})
    if not r.get("ok"):
        raise SystemExit(f"Trennung nicht gestartet: {r}")
    st = wait(s, "Trennung", 3600, tick)
    log(f"Trennung fertig nach {time.time() - t1:.0f} s · Fehler: {st.get('error')}")
    if st.get("error"):
        log(st["error"][-1500:])
        raise SystemExit("Trennung fehlgeschlagen")

    # Fortschritt auswerten
    fr = [x[3] for x in samples if x[1] == 0 and x[2] == 1]
    moving = sorted(set(f for f in fr if 0 < f < 1))
    texts = []
    for x in samples:
        if x[4] and (not texts or texts[-1] != x[4]):
            texts.append(x[4])
    log(f"Fortschritt: {len(samples)} Messpunkte, {len(moving)} verschiedene Zwischenstände, max {max(fr or [0]):.2f}")
    for t in (texts if len(texts) <= 14 else texts[:7] + ["…"] + texts[-7:]):
        log(f"  Anzeige: {t[:120]}")

    res = st.get("result") or {}
    log(f"Ergebnis: {res.get('message')}")
    outs = res.get("outputs") or []
    files = sorted(os.listdir(outs[0])) if outs else []
    log(f"Spuren: {files}")
    from id3tags import MP3File
    tagged = [f for f in files if f.endswith(".mp3") and MP3File(os.path.join(outs[0], f)).text("TPE1") == "TagStudio CI"]

    ok = True
    for cond, label in ((len(files) >= 4, "mindestens 4 Spuren"), (len(tagged) == len(files), "Tags übernommen"),
                        (len(moving) >= 3, "Fortschritt bewegt sich innerhalb des Titels")):
        log(("OK     " if cond else "FEHLER ") + label)
        ok &= cond
    log("STEMS-TEST " + ("BESTANDEN" if ok else "NICHT BESTANDEN"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as ex:
        if not isinstance(ex.code, int):
            log(f"FEHLER: {ex.code}")
            log("STEMS-TEST NICHT BESTANDEN")
            sys.exit(1)
        raise
