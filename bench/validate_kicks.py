"""Ground-truth kick counting for the Track Map (full mix, no stems).

Uses the section benchmark arrangements (bench/validate_sections.py), which know the
exact sample of every kick. Bass in these tracks is a sustained line that changes note
every bar and pumps on the beat, the case that inflated the 3.1 counter.
Metrics: precision, recall, F (hit window +-30 ms), and count ratio est/true.
Run:  python -m bench.validate_kicks
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bench import validate_sections as VS  # noqa: E402

WIN = 0.030


def match(est_s, ref_s, win=WIN):
    est_s = np.sort(np.asarray(est_s, dtype=float))
    used = np.zeros(len(est_s), bool)
    hits = 0
    for r in ref_s:
        j = np.searchsorted(est_s, r)
        best = None
        for k in (j - 1, j):
            if 0 <= k < len(est_s) and not used[k] and abs(est_s[k] - r) <= win:
                if best is None or abs(est_s[k] - r) < abs(est_s[best] - r):
                    best = k
        if best is not None:
            used[best] = True
            hits += 1
    p = hits / max(1, len(est_s))
    rc = hits / max(1, len(ref_s))
    f = 0.0 if hits == 0 else 2 * p * rc / (p + rc)
    return p, rc, f


def run(detector=None, verbose=True):
    import track_map_engine as tm
    if detector is None:
        detector = lambda x, sr: np.array([k for s in tm.build_provisional_track_map(x, sr=sr)["sections"]
                                           for k in [kd["time_s"] for kd in s["kicks_detail"]]])
    rows = []
    for i, (name, kind, bpm, pickup, plan) in enumerate(VS.CASES):
        x, truth, bar, kicks = VS.render(kind, bpm, pickup, plan, seed=i, return_kicks=True)
        est = np.asarray(detector(x, VS.SR), dtype=float)
        p, r, f = match(est, kicks)
        rows.append(dict(name=name, true=len(kicks), est=int(len(est)), precision=p, recall=r, f=f))
        if verbose:
            print(f"{name:16s} true {len(kicks):4d}  est {len(est):4d}  P {p:.2f} R {r:.2f} F {f:.2f}")
    agg = {k: float(np.mean([r[k] for r in rows])) for k in ("precision", "recall", "f")}
    agg["count_ratio"] = float(np.sum([r["est"] for r in rows]) / np.sum([r["true"] for r in rows]))
    if verbose:
        print("MEAN  " + "  ".join(f"{k} {v:.2f}" for k, v in agg.items()))
    return dict(mean=agg, rows=rows)


if __name__ == "__main__":
    res = run()
    out = os.path.join(os.path.dirname(__file__), "results", "kicks_validation.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


def run_heldout(detector, n=20, seed=2027, verbose=True):
    """Same random arrangements as bench.validate_sections.run_heldout (never used for tuning)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        kind = "edm" if i % 2 == 0 else "song"
        bpm, pickup, plan = VS.random_plan(rng, kind)
        x, truth, bar, kicks = VS.render(kind, bpm, pickup, plan, seed=seed + i, return_kicks=True)
        est = np.asarray(detector(x, VS.SR), dtype=float)
        p, r, f = match(est, kicks)
        rows.append(dict(name=f"{kind}_{i}", true=len(kicks), est=int(len(est)), precision=p, recall=r, f=f))
    agg = {k: float(np.mean([r[k] for r in rows])) for k in ("precision", "recall", "f")}
    agg["count_ratio"] = float(np.sum([r["est"] for r in rows]) / np.sum([r["true"] for r in rows]))
    if verbose:
        print("HELD-OUT  " + "  ".join(f"{k} {v:.2f}" for k, v in agg.items()))
    return dict(mean=agg, rows=rows)
