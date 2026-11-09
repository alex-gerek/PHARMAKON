"""
Ground-truth validation of resonance detectors (v1 vs v2).

Why synthetic + injected: on real AI tracks nobody knows which peaks are artifacts.
So we build cases where the answer is known:

  A. Synthetic music, NO resonance   - chord progression with harmonic tones (incl. long
                                        high notes such as C7 = 2093 Hz), bass, hi-hats,
                                        noise floor. Any detection = FALSE POSITIVE.
  B. Synthetic music + injected EQ resonance (peaking filter, known f / gain / Q) -
     detection within +-3 % of f = HIT.
  C. Real tracks + injected resonance - HIT if a new detection appears at f
     (real tracks may contain their own resonances; only the injected one is scored).

v1 = remaster_engine.detect_harsh_resonances (product Auto Antidote: acts if prominence >= 3 dB)
v2 = bench.resonance_v2.analyze
"""
import json
import os
import sys

import numpy as np
import scipy.signal as signal
import soundfile as sf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import remaster_engine as re_eng  # noqa: E402
from bench import resonance_v2 as V2  # noqa: E402

SR = 48000
FREQ_TOL = 0.03
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def synth_music(seed, seconds=40.0, sr=SR):
    """Chord progression + melody (reaching C7) + bass + hi-hats + noise floor, stereo."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    key = int(rng.integers(0, 12))
    progression = [[0, 4, 7], [9, 0, 4], [5, 9, 0], [7, 11, 2]]  # I vi IV V
    chord_s = 2.0
    for ci, start in enumerate(np.arange(0.0, seconds, chord_s)):
        chord = progression[ci % 4]
        a, b = int(start * sr), int(min(seconds, start + chord_s) * sr)
        tt = t[a:b] - start
        env = np.minimum(1.0, tt / 0.02) * np.exp(-tt / 3.0)
        for pc in chord:
            for octave in (4, 5):
                f0 = midi_hz(12 * (octave + 1) + (key + pc) % 12)
                for h in range(1, 40):
                    if f0 * h > 15000:
                        break
                    out[a:b] += 0.05 / h * env * np.sin(2 * np.pi * f0 * h * tt + rng.uniform(0, 6.28))
        # bass
        fb = midi_hz(36 + (key + chord[0]) % 12)
        for h in range(1, 12):
            out[a:b] += 0.12 / h * env * np.sin(2 * np.pi * fb * h * tt)
        # melody: one long note per chord, sometimes very high (C7 region)
        mel = midi_hz(int(rng.choice([84, 88, 91, 96, 79])) + (key + chord[int(rng.integers(0, 3))]) % 12 - key % 12)
        for h in range(1, 8):
            if mel * h < 16000:
                out[a:b] += 0.06 / h * env * np.sin(2 * np.pi * mel * h * tt)
    # hi-hats (broadband, where a colouring resonance becomes visible)
    hat = signal.sosfilt(signal.butter(4, 6000, "high", fs=sr, output="sos"), rng.standard_normal(n))
    gate = np.zeros(n)
    for k in np.arange(0.0, seconds, 0.25):
        i = int(k * sr)
        L = min(int(0.05 * sr), n - i)
        gate[i:i + L] = np.exp(-np.arange(L) / (0.012 * sr))
    out += 0.08 * hat * gate
    # pink-ish noise floor (reverb / room / breath)
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / sr)
    X[1:] /= np.sqrt(f[1:])
    pink = np.fft.irfft(X, n)
    out += 0.01 * pink / np.std(pink)
    out *= 0.3 / np.max(np.abs(out))
    return np.column_stack([out, out])


def inject(audio, sr, f, gain_db, q):
    b, a = _peaking(f, gain_db, q, sr)
    return signal.lfilter(b, a, audio, axis=0)


def _peaking(f0, gain_db, q, sr):
    A = 10 ** (gain_db / 40)
    w = 2 * np.pi * f0 / sr
    al = np.sin(w) / (2 * q)
    b = np.array([1 + al * A, -2 * np.cos(w), 1 - al * A])
    a = np.array([1 + al / A, -2 * np.cos(w), 1 - al / A])
    return b / a[0], a / a[0]


def v1_detect(audio, sr):
    f, q, prom = re_eng.detect_harsh_resonances(audio, sr)
    return [f] if prom >= 3.0 else []


def v2_detect(audio, sr):
    return [r["hz"] for r in V2.analyze(audio, sr)["resonances"]]


def _hit(dets, f):
    return any(abs(d - f) <= FREQ_TOL * f for d in dets)


def run(n_synth=12, gains=(3.0, 4.0, 6.0, 9.0), qs=(5.0, 10.0, 20.0), real_tracks=None, inj_per_track=2):
    """Returns a summary dict; see module docstring for case definitions."""
    rng = np.random.default_rng(7)
    fp = {"v1": 0, "v2": 0, "n": 0}
    rec = {}
    f_err, q_ratio = [], []

    def score(kind, g, q, hit1, hit2, f, x_sr):
        key = f"{kind}|gain={g:g}|Q={q:g}"
        r = rec.setdefault(key, {"v1": 0, "v2": 0, "n": 0})
        r["n"] += 1
        r["v1"] += int(hit1)
        r["v2"] += int(hit2)

    def v2_full(x, sr):
        return V2.analyze(x, sr)["resonances"]

    for seed in range(n_synth):
        clean = synth_music(seed)
        fp["n"] += 1
        fp["v1"] += int(len(v1_detect(clean, SR)) > 0)
        fp["v2"] += int(len(v2_detect(clean, SR)) > 0)
        for g in gains:
            for q in qs:
                f = float(rng.uniform(2500.0, 8000.0))
                x = inject(clean, SR, f, g, q)
                r2 = v2_full(x, SR)
                d2 = [d["hz"] for d in r2]
                hit2 = _hit(d2, f)
                if hit2:
                    best = min(r2, key=lambda d: abs(d["hz"] - f))
                    f_err.append(abs(best["hz"] - f) / f)
                    if best["q_est"]:
                        q_ratio.append(best["q_est"] / q)
                score("synth", g, q, _hit(v1_detect(x, SR), f), hit2, f, SR)

    real_found = {}
    for path in real_tracks or []:
        a, sr = sf.read(path, dtype="float64")
        a = re_eng.ensure_stereo(a)
        s = int(len(a) * 0.3)
        a = a[s:s + 40 * sr]
        base1, base2 = v1_detect(a, sr), v2_detect(a, sr)
        real_found[os.path.basename(path)] = {"v1": base1, "v2": V2.analyze(a, sr)["resonances"][:3]}
        for g in gains:
            for q in qs:
                for _ in range(inj_per_track):
                    f = float(rng.uniform(2500.0, 8000.0))
                    x = inject(a, sr, f, g, q)
                    score("real", g, q, _hit(v1_detect(x, sr), f) and not _hit(base1, f),
                          _hit(v2_detect(x, sr), f) and not _hit(base2, f), f, sr)

    def agg(kind, g):
        n = sum(v["n"] for k, v in rec.items() if k.startswith(f"{kind}|gain={g:g}|"))
        a1 = sum(v["v1"] for k, v in rec.items() if k.startswith(f"{kind}|gain={g:g}|"))
        a2 = sum(v["v2"] for k, v in rec.items() if k.startswith(f"{kind}|gain={g:g}|"))
        return {"v1": f"{a1}/{n}", "v2": f"{a2}/{n}"}

    return {
        "false_positives_clean_synth": fp,
        "recall_by_gain": {kind: {f"{g:g} dB": agg(kind, g) for g in gains} for kind in ("synth", "real")},
        "recall_detail": rec,
        "v2_freq_error_median_pct": round(100 * float(np.median(f_err)), 2) if f_err else None,
        "v2_freq_error_max_pct": round(100 * float(np.max(f_err)), 2) if f_err else None,
        "v2_q_est_over_true_median": round(float(np.median(q_ratio)), 2) if q_ratio else None,
        "real_tracks_original_detections": real_found,
    }


if __name__ == "__main__":
    tracks = [os.path.join(ROOT, p) for p in (
        "uploads/Il Fuoco del Cuore.wav", "uploads/Miami Summer.wav", "uploads/Cobalt Lullaby.wav",
        "uploads/Bronze Psalter (1).wav", "uploads/!!!Round and Round.wav")]
    print(json.dumps(run(real_tracks=[t for t in tracks if os.path.isfile(t)]), indent=1, default=str))
