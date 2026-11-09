"""Sanity tests for the objective metrics bench (signals with analytically known answers)."""
import os
import sys

import numpy as np
import scipy.signal as signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bench import metrics as M  # noqa: E402

SR = 48000


def _pink(rng, n):
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X[1:] /= np.sqrt(f[1:])
    x = np.fft.irfft(X, n)
    return x / np.std(x) * 0.05


def _narrowband(rng, fc, spl_db=60.0):
    sos = signal.butter(8, [fc * 0.92, fc * 1.08], btype="band", fs=SR, output="sos")
    x = signal.sosfiltfilt(sos, rng.standard_normal(SR * 4))
    return x * (10 ** ((spl_db - M.FULL_SCALE_DB_SPL) / 20) / np.sqrt(2)) / np.sqrt(np.mean(x ** 2))


def test_tilt_white_and_pink():
    rng = np.random.default_rng(0)
    assert abs(M.tonal_balance(rng.standard_normal(SR * 6) * 0.05, SR)["tilt_db_per_oct"] - 3.0) < 0.2
    assert abs(M.tonal_balance(_pink(rng, SR * 6), SR)["tilt_db_per_oct"]) < 0.2


def test_sharpness_reference_and_monotonic():
    rng = np.random.default_rng(1)
    assert abs(M.sharpness_acum(_narrowband(rng, 1000.0), SR) - 1.0) < 0.05  # DIN 45692 reference point
    vals = [M.sharpness_acum(_narrowband(rng, fc), SR) for fc in (500.0, 1000.0, 2000.0, 4000.0, 8000.0)]
    assert all(b > a for a, b in zip(vals, vals[1:]))


def test_resonance_detects_added_peak():
    rng = np.random.default_rng(2)
    pink = _pink(rng, SR * 6)
    b, a = signal.iirpeak(5000.0 / (SR / 2), 15)
    with_peak = pink + 1.5 * signal.lfilter(b, a, pink)  # ~+8 dB narrow peak at 5 kHz
    assert M.resonance_metrics(pink, SR)["resonance_count"] == 0
    r = M.resonance_metrics(with_peak, SR)
    assert r["resonance_count"] >= 1 and abs(r["resonance_hz"] - 5000.0) < 150.0


def test_chain_metrics_identity_and_clip():
    clean = M.chain_metrics(lambda x, sr: x)
    assert clean["thd_1k_db"] < -120 and clean["imd_smpte_db"] < -120 and clean["alias_db"] < -120
    dirty = M.chain_metrics(lambda x, sr: np.tanh(2 * x) / 2)
    assert dirty["thd_1k_db"] > -40 and dirty["alias_db"] > -40
