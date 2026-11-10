"""
Track Map BPM precision: the detected tempo must be within 0.1 BPM of the true
tempo at 44.1 kHz and 48 kHz (integer-lag quantization used to read 128 BPM as
127.66 BPM, and the 5 ms hop was assumed exact although it is 4.989 ms at 44.1 kHz).
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import track_map_engine as tm  # noqa: E402


def _kick_track(bpm, sr, seconds=40.0, seed=1):
    rng = np.random.default_rng(seed)
    n_total = int(seconds * sr)
    x = 0.01 * rng.standard_normal(n_total)
    n = np.arange(int(0.12 * sr))
    for onset in np.arange(0.1, seconds - 0.2, 60.0 / bpm):
        n0 = int(onset * sr)
        idx = n[n0 + n < n_total]
        sweep = 2.0 * np.pi * (50.0 + 80.0 * np.exp(-idx / (0.01 * sr))) * idx / sr
        x[n0 + idx] += 0.8 * np.sin(sweep) * np.exp(-idx / (0.05 * sr))
    return x


@pytest.mark.parametrize("sr", [44100, 48000])
# Detector range is 50-210 BPM; octave chosen metrically (see bench/validate_tempo.py)
@pytest.mark.parametrize("bpm", [95.0, 124.0, 128.0, 140.0, 165.0])
def test_bpm_within_0p1(sr, bpm):
    est, bar_s = tm.detect_bpm_and_grid(_kick_track(bpm, sr), sr)
    assert abs(est - bpm) <= 0.1, f"{bpm} BPM @ {sr} Hz detected as {est}"
    assert abs(bar_s - 240.0 / est) < 1e-3  # est is rounded to 0.01 BPM
