"""Tape stage with matched de-emphasis: flat linear response, saturation character kept."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402

SR = 48000


def _gain_db(f, deemphasis):
    t = np.arange(SR * 2) / SR
    x = 1e-3 * np.sin(2 * np.pi * f * t)
    x = np.column_stack([x, x])
    y = re_eng.apply_tape_warmth_v2(x, SR, drive=1.04, bias=0.035, ceiling=0.98, deemphasis=deemphasis)
    mid = slice(SR // 2, -SR // 4)
    return 20 * np.log10(np.std(y[mid, 0]) / np.std(x[mid, 0]))


def test_deemphasis_flattens_linear_response():
    ref = _gain_db(1000.0, True)
    for f in (500.0, 3500.0, 6000.0, 10000.0, 16000.0):
        assert abs(_gain_db(f, True) - ref) < 0.1, f
    # legacy stage keeps its HF tilt (documented behaviour)
    assert _gain_db(10000.0, False) - _gain_db(1000.0, False) > 1.0


def _harm_dbc(level_db, deemphasis, k):
    t = np.arange(SR * 2) / SR
    x = 10 ** (level_db / 20) * np.sin(2 * np.pi * 1000 * t)
    y = re_eng.apply_tape_warmth_v2(x, SR, drive=1.05, bias=0.035, ceiling=0.98, deemphasis=deemphasis)[SR // 2:]
    S = np.abs(np.fft.rfft(y * np.blackman(len(y))))
    f = np.fft.rfftfreq(len(y), 1 / SR)
    h = lambda n: S[np.argmin(np.abs(f - 1000 * n))]
    return 20 * np.log10(h(k) / h(1))


def test_deemphasis_keeps_harmonic_character():
    for lvl in (0.0, -6.0, -18.0):
        for k in (2, 3):
            assert abs(_harm_dbc(lvl, True, k) - _harm_dbc(lvl, False, k)) < 1.0
