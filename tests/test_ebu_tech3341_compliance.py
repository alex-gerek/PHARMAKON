"""
Loudness meter compliance suite.

1. K-weighting coefficients vs. the ITU-R BS.1770-4 published 48 kHz table.
2. EBU Tech 3341 integrated-loudness test cases 1-5 (stereo 1 kHz tone
   sequences, tolerance +/-0.1 LU), synthesized per the specification and
   run at 44.1 kHz and 48 kHz.
3. Analytic true-peak cases (signals whose true peak is known in closed form),
   checked against the Tech 3341 true-peak tolerance (+0.2 / -0.4 dB).
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402

LU_TOL = 0.1
TP_TOL_UP = 0.2
TP_TOL_DOWN = 0.4
SAMPLE_RATES = (44100, 48000)

# ITU-R BS.1770-4, Table 1 (pre-filter) and Table 2 (RLB filter), fs = 48 kHz
ITU_STAGE1_B = [1.53512485958697, -2.69169618940638, 1.19839281085285]
ITU_STAGE1_A = [1.0, -1.69065929318241, 0.73248077421585]
ITU_STAGE2_B = [1.0, -2.0, 1.0]
ITU_STAGE2_A = [1.0, -1.99004745483398, 0.99007225036621]


def _tone_sequence(sr, segments, freq=1000.0):
    """Stereo (L = R) 1 kHz sine, piecewise level: [(dbfs, seconds), ...]."""
    parts = []
    for level_dbfs, seconds in segments:
        n = int(round(seconds * sr))
        amp = 10.0 ** (level_dbfs / 20.0)
        parts.append(amp * np.ones(n))
    env = np.concatenate(parts)
    tone = np.sin(2.0 * np.pi * freq * np.arange(len(env)) / sr) * env
    return np.column_stack([tone, tone])


def test_k_weighting_matches_itu_table_at_48k():
    (b1, a1), (b2, a2) = re_eng._get_k_weighting_biquads(48000)
    np.testing.assert_allclose(b1, ITU_STAGE1_B, atol=1e-9)
    np.testing.assert_allclose(a1, ITU_STAGE1_A, atol=1e-9)
    np.testing.assert_allclose(b2, ITU_STAGE2_B, atol=1e-9)
    np.testing.assert_allclose(a2, ITU_STAGE2_A, atol=1e-9)


# EBU Tech 3341, integrated loudness test cases 1-5
EBU_3341_CASES = [
    ("case1_-23dBFS", [(-23.0, 20.0)], -23.0),
    ("case2_-33dBFS", [(-33.0, 20.0)], -33.0),
    ("case3_relative_gate", [(-36.0, 10.0), (-23.0, 60.0), (-36.0, 10.0)], -23.0),
    ("case4_absolute_gate", [(-72.0, 10.0), (-36.0, 10.0), (-23.0, 60.0), (-36.0, 10.0), (-72.0, 10.0)], -23.0),
    ("case5_level_steps", [(-26.0, 20.0), (-20.0, 20.1), (-26.0, 20.0)], -23.0),
]


@pytest.mark.parametrize("sr", SAMPLE_RATES)
@pytest.mark.parametrize("name,segments,expected", EBU_3341_CASES, ids=[c[0] for c in EBU_3341_CASES])
def test_ebu_tech3341_integrated_loudness(sr, name, segments, expected):
    audio = _tone_sequence(sr, segments)
    measured = re_eng.calc_integrated_lufs(audio, sr)
    assert abs(measured - expected) <= LU_TOL, f"{name} @ {sr} Hz: {measured} LUFS, expected {expected} +/- {LU_TOL}"


def _assert_tp(measured_db, expected_db, label):
    assert expected_db - TP_TOL_DOWN <= measured_db <= expected_db + TP_TOL_UP, (
        f"{label}: measured {measured_db} dBTP, expected {expected_db} (+{TP_TOL_UP} / -{TP_TOL_DOWN})"
    )


@pytest.mark.parametrize("sr", SAMPLE_RATES)
def test_true_peak_intersample_fs4_sine(sr):
    # fs/4 sine with 45 deg phase: every sample sits at 0.707 * A, true peak is A.
    amp_db = -6.0
    n = np.arange(sr * 2)
    x = 10.0 ** (amp_db / 20.0) * np.sin(2.0 * np.pi * 0.25 * n + np.pi / 4.0)
    sample_peak_db = 20.0 * np.log10(np.max(np.abs(x)))
    assert sample_peak_db < amp_db - 2.9  # the case really is an inter-sample peak
    _, _, tp = re_eng.measure_true_peak_per_channel(np.column_stack([x, x]))
    _assert_tp(tp, amp_db, f"fs/4 ISP sine @ {sr}")


def _edge_fade(x, sr, fade_sec=0.01):
    # An abrupt start/stop is a real step that rings on reconstruction (the true
    # peak genuinely exceeds the sine amplitude there), so faded edges are used
    # to isolate the steady-state true-peak accuracy.
    n = int(fade_sec * sr)
    ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, n)))
    x = x.copy()
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


@pytest.mark.parametrize("sr", SAMPLE_RATES)
@pytest.mark.parametrize("freq", [997.0, 5000.0, 12000.0, 15000.0, 18000.0])
def test_true_peak_sine_amplitude(sr, freq):
    amp_db = -3.0
    n = np.arange(sr * 2)
    x = _edge_fade(10.0 ** (amp_db / 20.0) * np.sin(2.0 * np.pi * freq * n / sr + 0.3), sr)
    _, _, tp = re_eng.measure_true_peak_per_channel(np.column_stack([x, x]))
    _assert_tp(tp, amp_db, f"{freq} Hz sine @ {sr}")
