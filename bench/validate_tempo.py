"""Ground-truth tempo benchmark for the Track Intelligence Map.

Synthetic drum+bass+pad tracks are rendered at KNOWN tempos in rhythm styles that
are known to trip tempo detectors (half-time, hip-hop, trap hats, drum&bass, 3/4,
kick-less ballads). Metrics (MIREX convention):
  acc1 - estimate within 4 % of the true tempo        (what the map must show)
  acc2 - acc1 or within 4 % of x2, x1/2, x3, x1/3     (octave-tolerant)
  shown - acc1, or the octave the map shows as "alt" is the true one
Run:  python -m bench.validate_tempo
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SR = 44100


def _kick(sr, f0=55.0, dur=0.25):
    n = int(dur * sr)
    t = np.arange(n) / sr
    f = f0 + 90.0 * np.exp(-t / 0.02)
    return 0.9 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / 0.08)


def _snare(sr, rng, dur=0.18):
    n = int(dur * sr)
    t = np.arange(n) / sr
    noise = rng.standard_normal(n)
    from scipy import signal
    b, a = signal.butter(2, [1500 / (sr / 2), 8000 / (sr / 2)], btype="band")
    noise = signal.lfilter(b, a, noise)
    return (0.5 * noise + 0.3 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t / 0.05)


def _hat(sr, rng, dur=0.05):
    n = int(dur * sr)
    t = np.arange(n) / sr
    from scipy import signal
    b, a = signal.butter(2, 7000 / (sr / 2), btype="high")
    return 0.25 * signal.lfilter(b, a, rng.standard_normal(n)) * np.exp(-t / 0.012)


# Patterns on a 16-step grid per bar (4/4) or 12-step (3/4): (kick, snare, hat) steps
STYLES = {
    "four_on_floor": dict(steps=16, kick=[0, 4, 8, 12], snare=[4, 12], hat=[2, 6, 10, 14]),
    "half_time":     dict(steps=16, kick=[0, 10], snare=[8], hat=[0, 2, 4, 6, 8, 10, 12, 14]),
    "hip_hop":       dict(steps=16, kick=[0, 7, 10], snare=[4, 12], hat=[0, 2, 4, 6, 8, 10, 12, 14]),
    "trap":          dict(steps=16, kick=[0, 11], snare=[8], hat=list(range(16))),
    "dnb":           dict(steps=16, kick=[0, 10], snare=[4, 12], hat=[0, 2, 4, 6, 8, 10, 12, 14]),
    "waltz_3_4":     dict(steps=12, kick=[0], snare=[4, 8], hat=[0, 2, 4, 6, 8, 10]),
    "ballad_no_kick": dict(steps=16, kick=[], snare=[4, 12], hat=[0, 4, 8, 12]),
    "rock_8ths":     dict(steps=16, kick=[0, 6, 8], snare=[4, 12], hat=[0, 2, 4, 6, 8, 10, 12, 14]),
}

# (style, true tempo in BPM = quarter-note beats per minute)
CASES = [
    ("four_on_floor", 124), ("four_on_floor", 128), ("four_on_floor", 138), ("four_on_floor", 145),
    ("four_on_floor", 100), ("four_on_floor", 118),
    ("half_time", 140), ("half_time", 75),
    ("hip_hop", 88), ("hip_hop", 94), ("hip_hop", 72),
    ("trap", 70), ("trap", 140),
    ("dnb", 174), ("dnb", 170),
    ("waltz_3_4", 90), ("waltz_3_4", 150),
    ("ballad_no_kick", 66), ("ballad_no_kick", 80),
    ("rock_8ths", 110), ("rock_8ths", 160), ("rock_8ths", 96),
]


def render(style, bpm, seconds=40.0, sr=SR, seed=0):
    rng = np.random.default_rng(seed)
    p = STYLES[style]
    n = int(seconds * sr)
    x = np.zeros(n + sr)
    step_s = 60.0 / bpm / 4.0           # 16th note
    kick, snare = _kick(sr), _snare(sr, rng)
    total_steps = int(seconds / step_s)
    for k in range(total_steps):
        s = k % p["steps"]
        i = int(round(k * step_s * sr + rng.normal(0, 0.002) * sr))
        i = max(0, i)
        if s in p["kick"]:
            x[i:i + len(kick)] += kick[: len(x) - i]
        if s in p["snare"]:
            x[i:i + len(snare)] += snare[: len(x) - i]
        if s in p["hat"]:
            h = _hat(sr, rng) * (1.0 if s % 4 == 0 else 0.7)
            x[i:i + len(h)] += h[: len(x) - i]
    x = x[:n]
    # sustained bass + pad following a chord every bar (adds tonal, non-percussive energy)
    t = np.arange(n) / sr
    bar_s = step_s * p["steps"]
    roots = np.array([0, 5, 3, 7])
    idx = (t // bar_s).astype(int) % 4
    f_bass = 41.2 * 2 ** (roots[idx] / 12)
    x += 0.25 * np.sin(2 * np.pi * np.cumsum(f_bass) / sr)
    for mult in (4, 5, 6):
        x += 0.04 * np.sin(2 * np.pi * np.cumsum(f_bass * mult) / sr)
    x += 0.003 * rng.standard_normal(n)
    x = x / np.max(np.abs(x)) * 0.8
    return np.column_stack([x, x]).astype(np.float32)


def score(est, true):
    ok1 = abs(est - true) <= 0.04 * true
    ok2 = ok1 or any(abs(est - true * m) <= 0.04 * true * m for m in (2, 0.5, 3, 1 / 3))
    return ok1, ok2


def run(detector=None, verbose=True):
    import track_map_engine as tm
    if detector is None:
        detector = tm.detect_tempo
    rows = []
    for i, (style, bpm) in enumerate(CASES):
        x = render(style, bpm, seed=i)
        res = detector(np.mean(x, axis=1), SR)
        est, alt = (res["bpm"], res.get("alt_bpm")) if isinstance(res, dict) else (float(res), None)
        ok1, ok2 = score(est, bpm)
        shown = ok1 or (alt is not None and score(alt, bpm)[0])
        rows.append(dict(style=style, true=bpm, est=round(est, 2), alt=alt, acc1=ok1, acc2=ok2, shown=shown))
        if verbose:
            tag = 'OK ' if ok1 else ('ALT' if shown else ('OCT' if ok2 else 'BAD'))
            print(f"{style:16s} true {bpm:6.1f}  est {est:7.2f}  alt {alt}  {tag}")
    a1 = np.mean([r["acc1"] for r in rows])
    a2 = np.mean([r["acc2"] for r in rows])
    sh = np.mean([r["shown"] for r in rows])
    if verbose:
        print(f"acc1 {a1:.0%}  acc2 {a2:.0%}  shown(acc1 or alt) {sh:.0%}  (n={len(rows)})")
    return dict(acc1=float(a1), acc2=float(a2), shown=float(sh), rows=rows)


if __name__ == "__main__":
    res = run()
    out = os.path.join(os.path.dirname(__file__), "results", "tempo_validation.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
