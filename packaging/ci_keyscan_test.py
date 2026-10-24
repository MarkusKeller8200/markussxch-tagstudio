"""Echter Ende-zu-Ende-Test des Plugins „Tonart (OpenKeyScan)“ (#245, Workflow „Tonart-Test“ in GitHub Actions).

    python packaging/ci_keyscan_test.py [variante]

1. Erzeugt synthetische Titel in bekannter Tonart (a-Moll: Am–Dm–Em–Am, C-Dur: C–F–G–C; Bass, Akkorde, Kick) –
   keine echte Musik.
2. Installiert die Umgebung genau wie die App (Session.start_plugin_install → uv, Python 3.12, PyTorch, librosa, PyAV)
   und lädt Netz und Modell von festem Commit mit Prüfsumme (env.files).
3. Erkennt die Tonart über den Tagger (Session.start_plugin_action „scan“) und prüft die Vorschau.
Bestanden, wenn Installation und Analyse klappen und jede Datei einen Camelot-Vorschlag hat. Ob die erkannte Tonart
zur erzeugten passt (gleich/verwandt), steht im Ergebnis – bei synthetischen Klängen nur als Hinweis.
Ergebnis in keyscan-test.txt. Exitcode 0 = bestanden.
"""
import math
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "keyscan-test.txt")
LINES = []
# MIDI-Grundtöne der Akkorde, Moll/Dur je Akkord
TRACKS = {"01 a-Moll.mp3": ("8A", [(57, True), (62, True), (64, True), (57, True)]),
          "02 C-Dur.mp3": ("8B", [(60, False), (65, False), (67, False), (60, False)])}


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LINES.append(line)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(LINES) + "\n")


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def make_track(path_mp3, chords, seconds=48, sr=44100):
    beat = 60 / 124
    bar = beat * 4
    frames = bytearray()
    for i in range(seconds * sr):
        t = i / sr
        root, minor = chords[int(t / (bar * 2)) % len(chords)]
        triad = [root, root + (3 if minor else 4), root + 7]
        tb = t % beat
        kick = math.sin(2 * math.pi * (50 + 80 * math.exp(-tb * 30)) * tb) * math.exp(-tb * 8) * 0.5
        bass = math.sin(2 * math.pi * hz(root - 24) * t) * 0.3
        pad = sum(math.sin(2 * math.pi * hz(n) * t) + 0.3 * math.sin(4 * math.pi * hz(n) * t) for n in triad) * 0.12
        s = max(-1.0, min(1.0, kick + bass + pad))
        v = int(s * 30000)
        frames += struct.pack("<hh", v, v)
    wav = path_mp3[:-4] + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    import imageio_ffmpeg
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k",
                    "-id3v2_version", "3", "-metadata", "title=Tonart-Test", path_mp3], check=True)
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
    home = tempfile.mkdtemp(prefix="ts_home_")
    os.environ["HOME"] = os.environ["USERPROFILE"] = home
    music = os.path.join(home, "Musik")
    os.makedirs(music)
    for name, (_want, chords) in TRACKS.items():
        make_track(os.path.join(music, name), chords)
    log(f"{len(TRACKS)} Testtitel erzeugt · Variante {variant} · {sys.platform}")

    from session import Session
    s = Session()
    t0 = time.time()
    r = s.start_plugin_install("keyscan", variant)
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
    log(f"Plugin nach Installation: {info['keyscan']['state']} ({info['keyscan'].get('env_variant')})")
    if info["keyscan"]["state"] != "ready":
        raise SystemExit("Plugin nicht bereit")

    s.start_tag_load(music, False)
    wait(s, "Einlesen", 120)
    t1 = time.time()
    r = s.start_plugin_action("keyscan", "scan", list(range(len(s.tag_files))), {"tkey": True, "cache": False})
    if not r.get("ok"):
        raise SystemExit(f"Analyse nicht gestartet: {r}")
    st = wait(s, "Analyse", 1800)
    res = st.get("result") or {}
    log(f"Analyse fertig nach {time.time() - t1:.0f} s · {res.get('message') or st.get('error')}")
    if st.get("error"):
        log(str(st["error"])[-1500:])
        raise SystemExit("Analyse fehlgeschlagen")
    for line in (res.get("log") or [])[-10:]:
        log(f"  Protokoll: {str(line)[:200]}")
    import keys
    import keyscan
    got = {p["name"]: p for p in res.get("proposals", []) if p["label"] == "Tonart (OpenKeyScan)"}
    ok = len(got) == len(TRACKS)
    log(("OK     " if ok else "FEHLER ") + f"Vorschlag OPENKEYSCAN_KEY für alle {len(TRACKS)} Titel")
    for name, (want, _c) in TRACKS.items():
        p = got.get(name)
        if not p:
            continue
        code = keys.parse_key(p["new"])
        rel = keyscan.relation(want, code) if code else "-"
        log(f"  {name}: erkannt {p['new']} · erwartet {keys.format_key(want)} · {keyscan.REL_TEXT.get(rel, rel)} · {p['note']}")
    log("TONART-TEST " + ("BESTANDEN" if ok else "NICHT BESTANDEN"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as ex:
        if not isinstance(ex.code, int):
            log(f"FEHLER: {ex.code}")
            log("TONART-TEST NICHT BESTANDEN")
            sys.exit(1)
