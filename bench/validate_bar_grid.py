"""Ground-truth beat-grid benchmark for the Track Intelligence Map.

Long synthetic drum + bass tracks are rendered with KNOWN beat times, then the bar
grid of track_map_engine.detect_bar_grid is compared with the truth. Three grid
methods are measured on the same audio:
  none       the 3.2 grid: phase + k * period from the BPM alone (no fit)
  lsq        least-squares line through the matched beat onsets
  theil_sen  robust line (median of pairwise slopes) through the same onsets

Stress cases (each alone, on top of a clean track):
  bpm_err      the grid is given a BPM 0.1 % off (0.13 BPM at 128): what a small
               tempo error does over 3 minutes
  loose_intro  the first 16 beats are played up to +-35 ms off the grid
  outliers     10 % extra drum hits at random off-grid times
  pickup       0.73 s of silence before the first beat
  hard         all four at once
  soft         every hit with a 10 ms attack ramp (later onset-function peak)

Metrics (ms unless noted):
  bias_ms           median SIGNED error (grid - truth); 3.2 grids were ~-40 ms (early)
  med_ms / p95_ms   median and 95th percentile |error| of every true beat to the grid
  end_ms            mean |error| over the last 16 beats (drift shows up here)
  down_ok           share of true downbeats that have a grid downbeat within 70 ms
Run:  python -m bench.validate_bar_grid
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bench.validate_tempo import STYLES, _hat, _kick, _snare  # noqa: E402

SR = 44100
SECONDS = 180.0
METHODS = ("none", "lsq", "theil_sen")
STRESS = ("clean", "bpm_err", "loose_intro", "outliers", "pickup", "hard", "soft")
CASES = [("four_on_floor", 128), ("four_on_floor", 100), ("hip_hop", 94),
         ("dnb", 174), ("rock_8ths", 110), ("half_time", 140)]
BPM_ERR = 0.001


def render(style, bpm, stress, seconds=SECONDS, sr=SR, seed=0):
    """Returns (mono, beat_times_s). Beat 0 is a downbeat."""
    rng = np.random.default_rng(seed)
    p = STYLES[style]
    on = lambda name: stress in (name, "hard")
    div = p.get("div", 4)
    pickup = 0.73 if on("pickup") else 0.0
    beat_s = 60.0 / bpm
    step_s = beat_s / div
    n = int(seconds * sr)
    x = np.zeros(n + sr)
    kick, snare = _kick(sr), _snare(sr, rng)
    if stress == "soft":
        a = int(0.010 * sr)
        ramp = np.linspace(0.0, 1.0, a) ** 2
        kick, snare = kick.copy(), snare.copy()
        kick[:a] *= ramp
        snare[:a] *= ramp
    n_steps = int((seconds - pickup - 0.5) / step_s)

    def put(sig, t):
        i = int(round(t * sr))
        if 0 <= i < len(x):
            x[i:i + len(sig)] += sig[: len(x) - i]

    loose = {}
    for k in range(n_steps):
        s = k % p["steps"]
        t = pickup + k * step_s
        beat = k // div
        if on("loose_intro") and beat < 16:
            t += loose.setdefault(beat, rng.uniform(-0.035, 0.035))
        t += rng.normal(0, 0.001)
        if s in p["kick"]:
            put(kick, t)
        if s in p["snare"]:
            put(snare, t)
        if s in p["hat"]:
            put(_hat(sr, rng) * (1.0 if s % 4 == 0 else 0.7), t)
    n_beats = n_steps // div
    if on("outliers"):
        for t in rng.uniform(pickup, seconds - 1.0, int(0.10 * n_beats)):
            put(kick if rng.random() < 0.5 else snare, t)
    x = x[:n]
    tt = np.arange(n) / sr
    bar_s = beat_s * 4
    roots = np.array([0, 5, 3, 7])
    idx = (np.maximum(tt - pickup, 0.0) // bar_s).astype(int) % 4
    f_bass = 41.2 * 2 ** (roots[idx] / 12)
    x += 0.25 * np.sin(2 * np.pi * np.cumsum(f_bass) / sr) * (tt >= pickup)
    x += 0.003 * rng.standard_normal(n)
    x = x / np.max(np.abs(x)) * 0.8
    return x, pickup + np.arange(n_beats) * beat_s


def evaluate(down, bar_s, truth):
    beat = bar_s / 4.0
    k0 = int(np.floor((0.0 - down[0]) / beat)) - 1
    k1 = int(np.ceil((truth[-1] + 1.0 - down[0]) / beat)) + 1
    grid = down[0] + np.arange(k0, k1) * beat
    near = np.abs(truth[:, None] - grid[None, :]).argmin(axis=1)
    signed = (grid[near] - truth) * 1000.0
    err = np.abs(signed)
    true_down = truth[::4]
    d_err = np.abs(true_down[:, None] - down[None, :]).min(axis=1)
    return dict(bias_ms=float(np.median(signed)), med_ms=float(np.median(err)), p95_ms=float(np.percentile(err, 95)),
                end_ms=float(np.mean(err[-16:])), down_ok=float(np.mean(d_err <= 0.070)))


def run(verbose=True, cases=CASES, stresses=STRESS):
    import track_map_engine as tm
    rows = []
    for ci, (style, bpm) in enumerate(cases):
        for si, stress in enumerate(stresses):
            x, truth = render(style, bpm, stress, seed=100 * ci + si)
            given = bpm * (1.0 + BPM_ERR) if stress in ("bpm_err", "hard") else float(bpm)
            for m in METHODS:
                down, bar_s, info = tm.detect_bar_grid(x, SR, given, fit=m, return_info=True)
                r = evaluate(np.asarray(down), bar_s, truth)
                r.update(style=style, bpm=bpm, stress=stress, method=m, fitted=info["fitted"])
                rows.append(r)
                if verbose:
                    print(f"{style:14s} {bpm:4d} {stress:12s} {m:10s} bias {r['bias_ms']:6.1f}  med {r['med_ms']:6.1f}  p95 {r['p95_ms']:6.1f}"
                          f"  end {r['end_ms']:6.1f}  down {r['down_ok']:.0%}  fit {info['fitted']}")
    summary = {}
    for m in METHODS:
        for stress in stresses:
            rr = [r for r in rows if r["method"] == m and r["stress"] == stress]
            summary[f"{m}/{stress}"] = {k: float(np.mean([r[k] for r in rr])) for k in ("bias_ms", "med_ms", "p95_ms", "end_ms", "down_ok")}
    if verbose:
        print("\nmean over cases")
        for k, v in summary.items():
            print(f"{k:24s} bias {v['bias_ms']:6.1f}  med {v['med_ms']:6.1f}  p95 {v['p95_ms']:6.1f}  end {v['end_ms']:6.1f}  down {v['down_ok']:.0%}")
    return dict(rows=rows, summary=summary)


if __name__ == "__main__":
    res = run()
    out = os.path.join(os.path.dirname(__file__), "results", "bar_grid.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("written", out)
