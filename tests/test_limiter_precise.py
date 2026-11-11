"""Precise true-peak verification (Clean Chain 3.2).

The 3.1 limiter checks its output at 4X and, if anything is still over, blends in
a local tanh guard followed by a hard sample clamp. On signals with a lot of
energy near Nyquist the clamp itself creates new inter-sample peaks, and 4X
reads dense high-frequency content slightly low. Measured at 32X:
full-band white noise ended about 0.3 dB over the ceiling, noise low-passed at
16 kHz about 0.1 dB over. The precise pass re-measures at 8X and corrects with
smooth gain instead of saturation; Classic 3.1 keeps the old path bit-for-bit.
"""
import os
import sys

import numpy as np
import pytest
import scipy.signal as signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import remaster_engine as re_eng  # noqa: E402

SR = 48000


def tp32_db(x):
    edge = int(0.05 * SR) * 32
    up = signal.resample_poly(np.asarray(x, np.float64), 32, 1, axis=0)[edge:-edge]
    return float(20 * np.log10(np.max(np.abs(up))))


def noise(lowpass_hz=None, seconds=4, seed=1, peak=1.5):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((SR * seconds, 2))
    if lowpass_hz:
        x = signal.lfilter(*signal.butter(4, lowpass_hz / (SR / 2)), x, axis=0)
    return (x / np.max(np.abs(x)) * peak).astype(np.float32)


@pytest.mark.parametrize("ceiling", [-0.3, -1.0, -2.0])
@pytest.mark.parametrize("lowpass_hz", [None, 16000])
def test_precise_limiter_holds_ceiling_at_32x(ceiling, lowpass_hz):
    out, reported = re_eng.true_peak_limiter(noise(lowpass_hz), SR, target_ceiling_db=ceiling, precise=True)
    assert tp32_db(out) <= ceiling + 0.02
    assert reported <= ceiling + 0.02


def test_old_limiter_gap_is_real():
    """Documents the defect the precise pass removes (Classic 3.1 keeps it on purpose)."""
    out, _ = re_eng.true_peak_limiter(noise(None), SR, target_ceiling_db=-1.0, precise=False)
    assert tp32_db(out) > -1.0 + 0.1


def test_precise_pass_does_not_touch_clean_material():
    """Nothing over the ceiling at 8X -> output identical to the 3.1 path."""
    t = np.arange(SR * 3) / SR
    s = 0.5 * np.sin(2 * np.pi * 1000 * t) + 0.3 * np.sin(2 * np.pi * 7000 * t)
    x = np.column_stack([s, s]).astype(np.float32)
    a, _ = re_eng.true_peak_limiter(x, SR, target_ceiling_db=-1.0, precise=False)
    b, _ = re_eng.true_peak_limiter(x, SR, target_ceiling_db=-1.0, precise=True)
    assert np.array_equal(a, b)


def test_precise_pass_stays_local():
    """A single HF burst: audio 250 ms away from it is untouched (below -80 dBFS)."""
    n = SR * 10
    t = np.arange(n) / SR
    clean = 0.5 * np.sin(2 * np.pi * 1000 * t)
    sig = clean.copy()
    idx = np.arange(SR * 5 - 48, SR * 5 + 48)
    sig[idx] += 1.6 * ((-1.0) ** np.arange(len(idx)))
    out, _ = re_eng.true_peak_limiter(np.column_stack([sig, sig]).astype(np.float32), SR,
                                      target_ceiling_db=-0.3, precise=True)
    far = np.ones(n, bool)
    far[: int(0.05 * SR)] = False
    far[-int(0.05 * SR):] = False
    far[SR * 5 - int(0.25 * SR): SR * 5 + int(0.25 * SR)] = False
    err = np.max(np.abs(out[far, 0] - clean[far]))
    assert 20 * np.log10(err + 1e-12) < -80
    assert tp32_db(out) <= -0.3 + 0.02


def test_precise_pass_works_in_chunked_path():
    x = noise(16000, seconds=130, seed=3)
    out, reported = re_eng.true_peak_limiter(x, SR, target_ceiling_db=-1.0, precise=True)
    # 32X over 130 s is heavy; check the chunk seam region and a random window
    for a in (SR * 118, SR * 60):
        seg = out[a: a + SR * 4]
        assert tp32_db(seg) <= -1.0 + 0.02


def test_profiles_select_limiter():
    assert re_eng.resolve_sound_profile({})[1]['limiter_precise'] is True
    assert re_eng.resolve_sound_profile({'classic_31': True})[1]['limiter_precise'] is False
