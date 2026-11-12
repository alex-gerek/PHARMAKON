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
    # drift = error at the end of the track beyond the constant onset latency
    assert fit["end_ms"] - fit["med_ms"] < 3.0, fit
    assert old["end_ms"] - old["med_ms"] > 15.0, old   # the 3.2 grid did drift (~27 ms here)
    # the fitted bar length is the TRUE one, not the one implied by the wrong BPM
    assert abs(bars["theil_sen"] / (240.0 / 128.0) - 1.0) < 2e-4
