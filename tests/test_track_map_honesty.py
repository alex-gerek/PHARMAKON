"""Track map must not report a kick-vs-bass correlation it cannot measure."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import track_map_engine as tm  # noqa: E402
from bench import validate_resonance as VR  # noqa: E402

SR = 48000


def test_full_mix_has_no_kick_bass_correlation():
    mix = VR.synth_music(1, seconds=20.0)
    m = tm.build_provisional_track_map(mix, sr=SR)
    assert m["sections"]
    assert all(s["sub_correlation_r"] is None for s in m["sections"])


def test_separate_drum_and_bass_give_measured_correlation():
    rng = np.random.default_rng(0)
    n = SR * 20
    t = np.arange(n) / SR
    drums = np.zeros(n)
    for k in np.arange(0.2, 19.5, 0.5):
        i = int(k * SR)
        L = int(0.12 * SR)
        drums[i:i + L] += 0.8 * np.sin(2 * np.pi * 55 * np.arange(L) / SR) * np.exp(-np.arange(L) / (0.04 * SR))
    bass = 0.3 * np.sin(2 * np.pi * 55 * t + 1.0) + 0.01 * rng.standard_normal(n)
    sd = tm.butter_lowpass(drums, 100.0, SR)
    sb = tm.butter_lowpass(bass, 100.0, SR)
    m = tm.build_provisional_track_map(np.column_stack([drums + bass, drums + bass]), sub_drums=sd, sub_bass=sb, sr=SR)
    vals = [s["sub_correlation_r"] for s in m["sections"]]
    assert all(isinstance(v, float) for v in vals)
    assert not all(abs(v - 1.0) < 1e-6 for v in vals)  # a real measurement, not the self-correlation constant
