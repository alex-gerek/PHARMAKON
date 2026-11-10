"""Ground-truth section benchmark for the Track Intelligence Map.

Synthetic arrangements are rendered from a known plan (bars per section, which
layers play), so every boundary and label is known exactly. The tracks may start
with a pickup (silence or an anacrusis) so the bar grid does NOT start at t = 0.

Metrics (MIREX structural segmentation conventions):
  hr05 / hr3   boundary F-measure, hit window +-0.5 s / +-3 s (start and end excluded)
  bar_f        boundary F-measure, hit window +-1 bar
  label_acc    fraction of time whose map tag equals the true tag
  generic      fraction of time labelled with a non-informative tag ("SECTION")
Run:  python -m bench.validate_sections
"""
import json
import os
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SR = 44100

# Layers: kick, bass, hat, clap, pad, lead, riser, snare_roll
EDM_LAYERS = {
    "INTRO":     dict(kick=1, hat=1),
    "GROOVE":    dict(kick=1, bass=1, hat=1, clap=1),
    "BREAKDOWN": dict(pad=1, lead=1),
    "BUILDUP":   dict(pad=1, lead=1, riser=1, snare_roll=1),
    "DROP":      dict(kick=1, bass=1, hat=1, clap=1, lead=1, pad=1),
    "OUTRO":     dict(kick=1, hat=1),
}
SONG_PROG = {  # chord roots (semitones from A) per bar; one chord per bar
    "INTRO": [0, 0, 5, 5], "VERSE": [0, 8, 3, 10], "PRECHORUS": [5, 7, 5, 7],
    "CHORUS": [3, 10, 0, 8], "BRIDGE": [1, 6, 1, 6], "OUTRO": [0, 0, 0, 0],
}
SONG_LAYERS = {
    "INTRO":     dict(pad=1),
    "VERSE":     dict(kick=1, bass=1, hat=1, clap=0.6, pad=0.6),
    "PRECHORUS": dict(kick=1, bass=1, hat=1, clap=0.8, pad=1, riser=1),
    "CHORUS":    dict(kick=1, bass=1, hat=1, clap=1, pad=1, lead=1),
    "BRIDGE":    dict(bass=1, pad=1),
    "OUTRO":     dict(pad=0.7),
}

CASES = [
    # (name, kind, bpm, pickup_s, [(tag, bars), ...])
    ("edm_classic", "edm", 128, 0.0,
     [("INTRO", 16), ("GROOVE", 16), ("BREAKDOWN", 16), ("BUILDUP", 8), ("DROP", 32), ("OUTRO", 16)]),
    ("edm_pickup", "edm", 124, 0.73,
     [("INTRO", 16), ("GROOVE", 32), ("BREAKDOWN", 8), ("BUILDUP", 8), ("DROP", 16), ("BREAKDOWN", 8),
      ("BUILDUP", 8), ("DROP", 16), ("OUTRO", 16)]),
    ("edm_short_intro", "edm", 138, 1.9,
     [("INTRO", 8), ("GROOVE", 16), ("BUILDUP", 8), ("DROP", 16), ("BREAKDOWN", 16), ("BUILDUP", 8),
      ("DROP", 16), ("OUTRO", 8)]),
    ("techno_long", "edm", 132, 0.0,
     [("INTRO", 32), ("GROOVE", 32), ("BREAKDOWN", 16), ("DROP", 32), ("OUTRO", 32)]),
    ("pop_basic", "song", 100, 0.0,
     [("INTRO", 4), ("VERSE", 8), ("PRECHORUS", 4), ("CHORUS", 8), ("VERSE", 8), ("PRECHORUS", 4),
      ("CHORUS", 8), ("BRIDGE", 8), ("CHORUS", 8), ("OUTRO", 4)]),
    ("pop_pickup", "song", 92, 1.1,
     [("INTRO", 8), ("VERSE", 16), ("CHORUS", 8), ("VERSE", 8), ("CHORUS", 8), ("BRIDGE", 8),
      ("CHORUS", 16), ("OUTRO", 8)]),
    ("pop_fast", "song", 120, 0.4,
     [("INTRO", 4), ("VERSE", 8), ("CHORUS", 8), ("VERSE", 8), ("CHORUS", 8), ("BRIDGE", 4),
      ("CHORUS", 8), ("OUTRO", 4)]),
]


def _env(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def render(kind, bpm, pickup_s, plan, seed=0, sr=SR, return_kicks=False):
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = 4 * beat
    total_bars = sum(b for _, b in plan)
    n = int((pickup_s + total_bars * bar + 0.5) * sr)
    x = np.zeros(n)
    kick_n = int(0.25 * sr)
    tk = np.arange(kick_n) / sr
    kick = 0.9 * np.sin(2 * np.pi * np.cumsum(50 + 100 * np.exp(-tk / 0.02)) / sr) * _env(kick_n, 0.08)
    b_hp, a_hp = signal.butter(2, 7000 / (sr / 2), "high")
    b_bp, a_bp = signal.butter(2, [1000 / (sr / 2), 6000 / (sr / 2)], "band")
    hat = 0.18 * signal.lfilter(b_hp, a_hp, rng.standard_normal(int(0.05 * sr))) * _env(int(0.05 * sr), 0.012)
    clap = 0.45 * signal.lfilter(b_bp, a_bp, rng.standard_normal(int(0.2 * sr))) * _env(int(0.2 * sr), 0.05)

    def add(i, s, g=1.0):
        if 0 <= i < n:
            m = min(len(s), n - i)
            x[i:i + m] += g * s[:m]

    layers_tab = EDM_LAYERS if kind == "edm" else SONG_LAYERS
    kick_times = []
    truth = []
    t_bar = pickup_s
    bar_idx = 0
    for tag, bars in plan:
        L = layers_tab[tag]
        t_start = t_bar
        prog = SONG_PROG.get(tag, [0, 5, 3, 7]) if kind == "song" else [0, 0, 5, 3]
        for b in range(bars):
            t0 = t_bar + b * bar
            i0 = int(t0 * sr)
            nb = int(bar * sr)
            root = 55.0 * 2 ** (prog[(bar_idx + b) % len(prog)] / 12.0)
            tt = np.arange(nb) / sr
            frac = (b + tt / bar) / bars                       # 0..1 position inside the section
            if L.get("bass"):
                add(i0, 0.35 * np.sin(2 * np.pi * root * tt) * (1 - 0.4 * ((tt % beat) / beat)))
            if L.get("pad"):
                g = 0.05 * L["pad"]
                pad = sum(np.sin(2 * np.pi * root * m * tt) for m in (4, 5, 6)) * g
                add(i0, pad)
            if L.get("lead"):
                for s8 in range(8):
                    f = root * 8 * 2 ** ([0, 3, 7, 10, 12, 10, 7, 3][s8] / 12.0)
                    ln = int(beat / 2 * sr)
                    tl = np.arange(ln) / sr
                    add(i0 + s8 * ln, 0.07 * np.sign(np.sin(2 * np.pi * f * tl)) * _env(ln, 0.15))
            if L.get("riser"):
                noise = rng.standard_normal(nb) * (0.02 + 0.12 * frac)
                add(i0, signal.lfilter(*signal.butter(2, min(0.95, (2000 + 8000 * frac[0]) / (sr / 2)), "high"), noise))
            for q in range(4):
                iq = i0 + int(q * beat * sr)
                if L.get("kick") and (kind == "edm" or q in (0, 2)):
                    add(iq, kick)
                    kick_times.append(iq / sr)
                if L.get("hat"):
                    add(iq + int(beat / 2 * sr), hat)
                if L.get("clap") and q in (1, 3):
                    add(iq, clap, L["clap"])
                if L.get("snare_roll"):
                    div = 2 if frac[0] < 0.5 else 4
                    for r in range(div):
                        add(iq + int(r * beat / div * sr), clap, 0.3 + 0.7 * frac[0])
        bar_idx += bars
        t_bar += bars * bar
        truth.append((round(t_start, 3), round(t_bar, 3), tag))
    if pickup_s > 0.3:      # an anacrusis: a short clap fill right before the first downbeat
        add(int((pickup_s - beat) * sr), clap, 0.5)
    x += 0.002 * rng.standard_normal(n)
    x = x / np.max(np.abs(x)) * 0.8
    if return_kicks:
        return np.column_stack([x, x]).astype(np.float32), truth, bar, np.array(kick_times)
    return np.column_stack([x, x]).astype(np.float32), truth, bar


def _f_measure(est, ref, win):
    est = np.asarray(est)
    ref = np.asarray(ref)
    if len(ref) == 0 and len(est) == 0:
        return 1.0
    if len(ref) == 0 or len(est) == 0:
        return 0.0
    used = set()
    hits = 0
    for r in ref:
        d = np.abs(est - r)
        for j in np.argsort(d):
            if d[j] > win:
                break
            if j not in used:
                used.add(j)
                hits += 1
                break
    p = hits / len(est)
    r_ = hits / len(ref)
    return 0.0 if hits == 0 else 2 * p * r_ / (p + r_)


def evaluate(tmap, truth, bar_s, duration):
    secs = tmap["sections"]
    est_b = [s["start_s"] for s in secs[1:]]
    ref_b = [t0 for t0, _, _ in truth[1:]]
    tt = np.arange(0.0, duration, 0.1)

    def tag_at(t, items):
        for a, b, tag in items:
            if a <= t < b:
                return tag
        return None
    est_items = [(s["start_s"], s["end_s"], s.get("sec_tag") or s.get("tag")) for s in secs]
    ref_items = [(a, b, t) for a, b, t in truth]
    valid = [t for t in tt if tag_at(t, ref_items) is not None]
    same = [tag_at(t, est_items) == tag_at(t, ref_items) for t in valid]
    generic = [tag_at(t, est_items) in ("SECTION", None) for t in valid]
    return dict(
        hr05=_f_measure(est_b, ref_b, 0.5),
        hr3=_f_measure(est_b, ref_b, 3.0),
        bar_f=_f_measure(est_b, ref_b, bar_s),
        label_acc=float(np.mean(same)) if same else 0.0,
        generic=float(np.mean(generic)) if generic else 0.0,
        n_est=len(secs), n_ref=len(truth),
    )


def run(builder=None, verbose=True):
    import track_map_engine as tm
    if builder is None:
        builder = lambda x, sr: tm.build_provisional_track_map(x, sr=sr)
    rows = []
    for i, (name, kind, bpm, pickup, plan) in enumerate(CASES):
        x, truth, bar_s = render(kind, bpm, pickup, plan, seed=i)
        m = builder(x, SR)
        r = evaluate(m, truth, bar_s, len(x) / SR)
        r.update(name=name, est_tags=[s.get("sec_tag") or s.get("tag") for s in m["sections"]],
                 est_starts=[round(s["start_s"], 1) for s in m["sections"]],
                 ref_tags=[t for _, _, t in truth], ref_starts=[round(a, 1) for a, _, _ in truth],
                 bpm_est=m.get("tempo_bpm"))
        rows.append(r)
        if verbose:
            print(f"{name:16s} hr0.5 {r['hr05']:.2f} hr3 {r['hr3']:.2f} bar {r['bar_f']:.2f} "
                  f"labels {r['label_acc']:.0%} generic {r['generic']:.0%} sections {r['n_est']}/{r['n_ref']} bpm {r['bpm_est']}")
    agg = {k: float(np.mean([r[k] for r in rows])) for k in ("hr05", "hr3", "bar_f", "label_acc", "generic")}
    if verbose:
        print("MEAN  " + "  ".join(f"{k} {v:.2f}" for k, v in agg.items()))
    return dict(mean=agg, rows=rows)


if __name__ == "__main__":
    res = run()
    out = os.path.join(os.path.dirname(__file__), "results", "sections_validation.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


def random_plan(rng, kind):
    """Held-out arrangements: random grammar, tempos, pickups (not used for tuning)."""
    if kind == "edm":
        plan = [("INTRO", int(rng.choice([8, 16, 32]))), ("GROOVE", int(rng.choice([16, 32])))]
        for _ in range(int(rng.integers(1, 3))):
            if rng.random() < 0.8:
                plan.append(("BREAKDOWN", int(rng.choice([8, 16]))))
            plan.append(("BUILDUP", int(rng.choice([4, 8]))))
            plan.append(("DROP", int(rng.choice([16, 32]))))
        plan.append(("OUTRO", int(rng.choice([8, 16, 32]))))
        bpm = float(np.round(rng.uniform(120, 145), 1))
    else:
        plan = [("INTRO", int(rng.choice([4, 8])))]
        pre = rng.random() < 0.5
        for _ in range(int(rng.integers(2, 4))):
            plan.append(("VERSE", int(rng.choice([8, 16]))))
            if pre:
                plan.append(("PRECHORUS", 4))
            plan.append(("CHORUS", int(rng.choice([8, 16]))))
        if rng.random() < 0.7:
            plan.insert(len(plan) - 1, ("BRIDGE", int(rng.choice([4, 8]))))
        plan.append(("CHORUS", 8))
        plan.append(("OUTRO", int(rng.choice([4, 8]))))
        bpm = float(np.round(rng.uniform(84, 128), 1))
    pickup = float(np.round(rng.choice([0.0, rng.uniform(0.2, 2.0)]), 2))
    return bpm, pickup, plan


def run_heldout(builder=None, n=20, seed=2027, verbose=True):
    import track_map_engine as tm
    if builder is None:
        builder = lambda x, sr: tm.build_provisional_track_map(x, sr=sr)
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        kind = "edm" if i % 2 == 0 else "song"
        bpm, pickup, plan = random_plan(rng, kind)
        x, truth, bar_s = render(kind, bpm, pickup, plan, seed=seed + i)
        m = builder(x, SR)
        r = evaluate(m, truth, bar_s, len(x) / SR)
        r.update(name=f"{kind}_{i}", bpm=bpm, pickup=pickup,
                 est=[(round(s["start_s"], 1), s.get("sec_tag") or s.get("tag")) for s in m["sections"]],
                 ref=[(round(a, 1), t) for a, _, t in truth])
        rows.append(r)
        if verbose:
            print(f"{r['name']:9s} bpm {bpm:6.1f} pickup {pickup:4.2f}  hr0.5 {r['hr05']:.2f} bar {r['bar_f']:.2f} labels {r['label_acc']:.0%}")
    agg = {k: float(np.mean([r[k] for r in rows])) for k in ("hr05", "hr3", "bar_f", "label_acc", "generic")}
    if verbose:
        print("HELD-OUT MEAN  " + "  ".join(f"{k} {v:.2f}" for k, v in agg.items()))
    return dict(mean=agg, rows=rows)
