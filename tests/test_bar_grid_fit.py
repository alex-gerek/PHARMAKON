"""Track Map beat grid fit (3.3), see bench/validate_bar_grid.py.

The 3.2 grid was phase + k * period from the BPM alone, so a tempo error grew along
the track. The grid is now a Theil-Sen line through the matched beat onsets.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import track_map_engine as tm  # noqa: E402
from bench import validate_bar_grid as V  # noqa: E402


def test_theil_sen_exact_line():
    x = np.arange(50.0)
    s, c = tm.theil_sen(x, 3.5 * x - 7.0)
    assert abs(s - 3.5) < 1e-12 and abs(c + 7.0) < 1e-12


def test_theil_sen_ignores_a_quarter_of_outliers():
    rng = np.random.default_rng(0)
    x = np.arange(200.0)
    y = 2.0 * x + 1.0 + rng.normal(0, 0.01, 200)
    bad = rng.choice(200, 50, replace=False)
    y[bad[:25]] += rng.uniform(5, 50, 25)        # one-sided outliers, as a loose intro is
    y[bad[25:]] += rng.uniform(-50, 50, 25)
    s, c = tm.theil_sen(x, y)
    ls, lc = np.polyfit(x, y, 1)
    assert abs(s - 2.0) < 0.005 and abs(c - 1.0) < 0.5
    assert abs(ls - 2.0) > abs(s - 2.0)          # least squares is pulled, Theil-Sen is not


def test_theil_sen_even_count_is_true_median():
    # two points: the only pairwise slope; intercept = mean of the two middle residuals
    s, c = tm.theil_sen([0.0, 1.0], [0.0, 2.0])
    assert s == 2.0 and c == 0.0


def test_grid_does_not_drift_with_a_tempo_error():
    # 0.1 % BPM error + loose intro + outlier hits + pickup, 120 s at 128 BPM
    x, truth = V.render("four_on_floor", 128, "hard", seconds=120.0, seed=7)
    given = 128.0 * (1.0 + V.BPM_ERR)
    res, bars = {}, {}
    for m in ("none", "theil_sen"):
        down, bars[m] = tm.detect_bar_grid(x, V.SR, given, fit=m)
        res[m] = V.evaluate(np.asarray(down), bars[m], truth)
    fit, old = res["theil_sen"], res["none"]
    # error over the last 16 beats (the onset latency is corrected, so drift shows directly)
    assert fit["end_ms"] < 5.0, fit
    assert old["end_ms"] > 15.0, old   # the unfitted grid did drift
    # the fitted bar length is the TRUE one, not the one implied by the wrong BPM
    assert abs(bars["theil_sen"] / (240.0 / 128.0) - 1.0) < 2e-4


import pytest  # noqa: E402


@pytest.mark.parametrize("sr", [44100, 48000])
def test_grid_is_on_the_beat_not_40_ms_early(sr):
    # 3.2 grids were 36-40 ms early: onset-function latency (n_fft - hop samples)
    x, truth = V.render("four_on_floor", 128, "clean", seconds=40.0, sr=sr, seed=11)
    down, bar_s = tm.detect_bar_grid(x, sr, 128.0)
    r = V.evaluate(np.asarray(down), bar_s, truth)
    assert abs(r["bias_ms"]) < 3.0, r
    assert r["p95_ms"] < 5.0, r


def test_latency_is_the_stft_geometry():
    assert tm.onset_latency_s(44100) == (tm.ONSET_NFFT - tm.ONSET_HOP) / 44100.0


@pytest.mark.parametrize("style,bpm,seed", [("four_on_floor", 128, 0), ("dnb", 174, 300)])
def test_downbeat_is_not_on_the_backbeat(style, bpm, seed):
    # the 3.2 rule put the one on the snare (beat 2 or 4) on these two tracks
    x, truth = V.render(style, bpm, "clean", seconds=60.0, seed=seed)
    down, bar_s, info = tm.detect_bar_grid(x, V.SR, float(bpm), return_info=True)
    r = V.evaluate(np.asarray(down), bar_s, truth)
    assert info["backbeat"] is not None
    assert r["down_ok"] == 1.0, r


def test_half_time_snare_is_not_taken_for_a_backbeat():
    # snare on 3 only: one strong beat, not a pair -> no backbeat constraint
    x, truth = V.render("half_time", 140, "clean", seconds=60.0, seed=5)
    down, bar_s, info = tm.detect_bar_grid(x, V.SR, 140.0, return_info=True)
    assert info["backbeat"] is None
    assert V.evaluate(np.asarray(down), bar_s, truth)["down_ok"] == 1.0
