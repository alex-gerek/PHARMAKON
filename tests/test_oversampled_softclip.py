"""Bass / drum soft-clip stages must not alias (4x oversampled tanh, same character as 1x)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402
from bench import metrics as M  # noqa: E402

SR = 48000


def test_softclip_oversampled_removes_aliasing():
    old = M.chain_metrics(lambda x, sr: re_eng.soft_clip(x * 1.2, 0.98), sr=SR)
    new = M.chain_metrics(lambda x, sr: re_eng.soft_clip_oversampled(x * 1.2, sr, 0.98), sr=SR)
    assert new["alias_db"] <= -55.0, new
    assert new["alias_db"] < old["alias_db"] - 25.0
    # saturation character unchanged (harmonics below Nyquist, intermodulation)
    assert abs(new["thd_1k_db"] - old["thd_1k_db"]) < 0.3
    assert abs(new["imd_smpte_db"] - old["imd_smpte_db"]) < 0.3


def test_softclip_oversampled_small_signal_flat():
    t = np.arange(SR * 2) / SR
    for f in (50.0, 1000.0, 10000.0, 18000.0):
        x = 1e-3 * np.sin(2 * np.pi * f * t)
        x = np.column_stack([x, x])
        y = re_eng.soft_clip_oversampled(x, SR, 0.98)
        mid = slice(SR // 2, -SR // 2)
        assert y.shape == x.shape
        assert abs(20 * np.log10(np.std(y[mid]) / np.std(x[mid]))) < 0.05


def test_softclip_oversampled_1d():
    x = 0.5 * np.sin(2 * np.pi * 440.0 * np.arange(SR) / SR)
    y = re_eng.soft_clip_oversampled(x, SR, 0.98)
    assert y.shape == x.shape
