"""Tonart-Worker (#245): läuft im Python der Plugin-Umgebung (nicht in TagStudio).

Aufruf: python worker.py auftrag.json
Auftrag: {"files": [...], "engine": Ordner mit model.py, "model": Pfad zu openkeyscan3.pt, "device": "auto"|"cpu"}
Meldungen an TagStudio als Zeilen „@@{json}“; alles andere ist Protokoll.

Die Analyse folgt der OpenKeyScan-Engine (https://github.com/rekordcloud/openkeyscan-analyzer, MIT-Lizenz):
Audio mono 44,1 kHz → CQT (105 Bänder, 24 je Oktave, ab 65 Hz, Sprung 8820) → log1p → KeyNet (24 Klassen).
Klasse 0–11 = 1A–12A (Moll), 12–23 = 1B–12B (Dur). Das Netz (model.py) und die Gewichte lädt TagStudio beim
Installieren von einem festen Stand des Repositorys und prüft beide mit SHA-256.
"""
import importlib.util
import json
import os
import sys
import traceback

SR, N_BINS, HOP = 44100, 105, 8820


def emit(**kw):
    sys.stderr.flush()
    print("\n@@" + json.dumps(kw, ensure_ascii=False), flush=True)


def camelot(cls: int) -> str:
    return f"{cls % 12 + 1}{'A' if cls < 12 else 'B'}"


def load_net(engine_dir, model_path, device):
    import torch
    spec = importlib.util.spec_from_file_location("openkeyscan_model", os.path.join(engine_dir, "model.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    net = mod.KeyNet(num_classes=24, in_channels=1, Nf=64, p=0.3).to(device)
    try:
        state = torch.load(model_path, map_location=device, weights_only=True)
    except TypeError:            # ältere PyTorch-Versionen kennen weights_only nicht
        state = torch.load(model_path, map_location=device)
    net.load_state_dict(state)
    net.eval()
    return net


def load_audio(path):
    """Mono-Signal (float32, 44,1 kHz). Zuerst PyAV (bringt FFmpeg mit, liest MP3/M4A/AAC zuverlässig), sonst librosa."""
    import numpy as np
    try:
        import av
        frames = []
        with av.open(path) as container:
            stream = container.streams.audio[0]
            rs = av.AudioResampler(format="flt", layout="mono", rate=SR)
            for frame in container.decode(stream):
                for r in rs.resample(frame) or []:
                    frames.append(r.to_ndarray())
            for r in rs.resample(None) or []:
                frames.append(r.to_ndarray())
        if not frames:
            raise ValueError("keine Audiodaten")
        wave = np.concatenate(frames, axis=1)[0]
        wave = np.ascontiguousarray(wave, dtype=np.float32)
        peak = float(np.abs(wave).max()) if wave.size else 0.0
        return wave / peak * 0.95 if peak > 0 else wave
    except ImportError:
        pass
    import librosa
    wave, _sr = librosa.load(path, sr=SR, mono=True)
    return wave.astype("float32")


def spectrogram(wave):
    import librosa
    import numpy as np
    import torch
    cqt = librosa.cqt(wave, sr=SR, hop_length=HOP, n_bins=N_BINS, bins_per_octave=24, fmin=65)
    spec = np.log1p(np.abs(cqt))[:, 0:-2]
    return torch.tensor(spec, dtype=torch.float32).unsqueeze(0).unsqueeze(0)      # (1, 1, Bänder, Zeit)


def pick_device(want):
    import torch
    if want and want != "auto":
        return torch.device(want)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def main(job_path):
    with open(job_path, encoding="utf-8") as fh:
        job = json.load(fh)
    emit(event="status", msg="Lade PyTorch und das Tonart-Modell …")
    import torch
    device = pick_device(job.get("device"))
    net = load_net(job["engine"], job["model"], device)
    try:
        spectrogram(__import__("numpy").zeros(SR * 2, dtype="float32"))   # erster CQT-Aufruf ist langsam
    except Exception:  # noqa: BLE001
        pass
    emit(event="loaded", device=str(device))
    for i, path in enumerate(job["files"]):
        emit(event="start", i=i, path=path)
        try:
            x = spectrogram(load_audio(path)).to(device)
            with torch.no_grad():
                prob = torch.softmax(net(x), dim=1)[0]
            cls = int(torch.argmax(prob).item())
            emit(event="done", i=i, path=path, camelot=camelot(cls), class_id=cls, conf=round(float(prob[cls]), 4))
        except Exception as ex:  # noqa: BLE001 – nächste Datei versuchen
            traceback.print_exc()
            emit(event="fail", i=i, path=path, msg=f"{type(ex).__name__}: {ex}")
    emit(event="end")


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as ex:  # noqa: BLE001
        traceback.print_exc()
        emit(event="fatal", msg=f"{type(ex).__name__}: {ex}")
        sys.exit(2)
