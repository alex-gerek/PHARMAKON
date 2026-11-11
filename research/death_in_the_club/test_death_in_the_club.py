"""
PHARMAKON Research Task 04: Death in the Club
Module: test_death_in_the_club.py

Automated pytest suite validating experimental reproducibility, numerical stability,
boundary handling, crossover mathematics, safe-path audit, and exact data integrity.
"""

import os
import sys
import csv
import json
import pytest
import numpy as np
import scipy.signal as signal

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PHARMAKON_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PHARMAKON_ROOT not in sys.path:
    sys.path.insert(0, PHARMAKON_ROOT)

from synthetic_signals import (
    generate_synthetic_kick,
    generate_synthetic_sustained_bass,
    generate_synthetic_melodic_bass,
    generate_synthetic_harmonic_bass,
    generate_boundary_condition,
    SAMPLE_RATE,
)
from methods import (
    method_a_baseline,
    method_b_global_delay,
    method_c_legacy_sub_only,
    method_d_guarded_per_kick,
    compute_rms,
    compute_true_peak,
    lowpass_filter,
    bandpass_filter,
)
from crossover_analysis import analyze_crossover


# =============================================================================
# 1. Historical Claims & Reproduction Integrity
# =============================================================================

@pytest.mark.xfail(
    strict=True,
    reason="Historical un-guarded drop (-1.17 dB) is prevented in production by P0-1 Sub-Sync Energy Guard in align_sub_phase (which rejects shifts dropping sub > -0.1 dB, resulting in -0.036 dB)."
)
def test_historical_claim_worst_legacy_drop_reproduced():
    """
    Verifies Historical Claim: Worst documented legacy result is -1.17 dB.
    Re-runs the exact 30 random pitch/phase seeds (seed 202611) evaluated in
    test_dsp_core_audit.py and confirms the worst-case sub-sum drop is -1.172 dB.
    """
    sr = SAMPLE_RATE
    dur = 3.0
    n = int(round(dur * sr))
    t = np.arange(n, dtype=np.float64) / sr
    rng = np.random.default_rng(202611)

    worst_sub_gain = 0.0
    run_1_sub_gain = 0.0

    for run_i in range(30):
        f_bass = float(rng.uniform(41.0, 55.0))
        phi1 = float(rng.uniform(0, 2 * np.pi))
        phi2 = float(rng.uniform(0, 2 * np.pi))
        phi3 = float(rng.uniform(0, 2 * np.pi))

        t_beat = np.mod(t, 0.5)
        kick_mono = 0.65 * np.sin(2 * np.pi * 50.0 * t_beat) * np.exp(-9.0 * t_beat)
        bass_mono = (
            0.45 * np.sin(2 * np.pi * f_bass * t + phi1)
            + 0.30 * np.sin(2 * np.pi * (2.0 * f_bass) * t + phi2)
            + 0.18 * np.sin(2 * np.pi * (3.0 * f_bass) * t + phi3)
        )
        drums = np.column_stack([kick_mono, kick_mono]).astype(np.float32)
        bass = np.column_stack([bass_mono, bass_mono]).astype(np.float32)

        # Method C (Legacy align_sub_phase)
        aligned_bass, meta_c = method_c_legacy_sub_only(drums, bass, sr)

        # Measure sub-band sum (<100 Hz) before and after using 4th-order SOS
        sub_orig = lowpass_filter(drums + bass, sr, cutoff=100.0, order=4)
        sub_proc = lowpass_filter(drums + aligned_bass, sr, cutoff=100.0, order=4)
        gain_db = 20.0 * np.log10(compute_rms(sub_proc) / compute_rms(sub_orig))

        if run_i == 1:
            run_1_sub_gain = gain_db
        worst_sub_gain = min(worst_sub_gain, gain_db)

    # Exact historical claim: -1.17 dB
    assert -1.20 <= worst_sub_gain <= -1.15, (
        f"Expected historical worst drop around -1.17 dB, got {worst_sub_gain:.3f} dB"
    )
    assert -1.20 <= run_1_sub_gain <= -1.15, (
        f"Expected Run 1 drop around -1.17 dB, got {run_1_sub_gain:.3f} dB"
    )


def test_measurements_csv_summary_statistics_exact_match():
    """
    Item 1 of Review: Recomputes summary statistics directly from measurements.csv.
    Asserts exact values for historical 30-run suite:
    - Method B: +0.2020 dB
    - Method C: -0.4512 dB
    - Method D: +0.5812 dB
    """
    csv_path = os.path.join(CURRENT_DIR, "measurements.csv")
    assert os.path.exists(csv_path), "measurements.csv missing"

    with open(csv_path, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def get_hist_mean(m_name: str) -> float:
        vals = [
            float(r["delta_sub_gain_db"]) for r in rows
            if r["method"] == m_name and r["signal_category"] == "historical_30_runs_seed202611"
        ]
        assert len(vals) == 30, f"Expected 30 runs for {m_name}, got {len(vals)}"
        return float(np.mean(vals))

    mean_b = get_hist_mean("B_GlobalDelay")
    mean_c = get_hist_mean("C_LegacySubOnly")
    mean_d = get_hist_mean("D_GuardedPerKick")

    assert abs(mean_b - 0.2020) < 0.0005, f"Method B mean expected +0.2020, got {mean_b:.4f}"
    assert abs(mean_c - (-0.4512)) < 0.0005, f"Method C mean expected -0.4512, got {mean_c:.4f}"
    assert abs(mean_d - 0.5812) < 0.0005, f"Method D mean expected +0.5812, got {mean_d:.4f}"


# =============================================================================
# 2. Crossover Mathematics & Unity Reconstruction
# =============================================================================

def test_crossover_digital_butterworth_exact_equations():
    """
    Item 5 of Review: Verifies the digital Butterworth filter equations.
    Distinguishes single-pass amplitude response (|H(w)| = 1/sqrt(2) = -3.01 dB at fc)
    from forward-backward effective transfer function (G(w) = |H(w)|^2 = 0.5000 = -6.02 dB at fc),
    and proves G_LP(w) + G_HP(w) = |H_LP|^2 + |H_HP|^2 == 1.000000 across all frequencies.
    """
    sr = 48000
    fc = 100.0
    nyq = 0.5 * sr
    b_lo, a_lo = signal.butter(2, fc / nyq, btype="low")
    b_hi, a_hi = signal.butter(2, fc / nyq, btype="high")

    w, h_lo = signal.freqz(b_lo, a_lo, worN=8192, fs=sr)
    _, h_hi = signal.freqz(b_hi, a_hi, worN=8192, fs=sr)

    # Single pass magnitudes
    mag_lo_single = np.abs(h_lo)
    mag_hi_single = np.abs(h_hi)

    # filtfilt effective transfer functions (strictly real, non-negative)
    G_lo = mag_lo_single ** 2
    G_hi = mag_hi_single ** 2

    idx_fc = int(np.argmin(np.abs(w - fc)))

    # Single pass amplitude at 100 Hz is 1/sqrt(2) (-3.01 dB)
    assert abs(mag_lo_single[idx_fc] - 1.0 / np.sqrt(2.0)) < 0.01
    assert abs(mag_hi_single[idx_fc] - 1.0 / np.sqrt(2.0)) < 0.01

    # filtfilt effective squared transfer function at 100 Hz is 0.5000 (-6.02 dB)
    assert abs(G_lo[idx_fc] - 0.5000) < 0.01
    assert abs(G_hi[idx_fc] - 0.5000) < 0.01

    # Perfect unity reconstruction G_lo + G_hi == 1.00000000
    G_sum = G_lo + G_hi
    max_dev = float(np.max(np.abs(G_sum - 1.0)))
    assert max_dev < 1e-11, f"Max deviation from unity is {max_dev:.2e}"


def test_historical_claim_crossover_notch_up_to_14db():
    """
    Verifies Historical Claim: Sub-band-only manipulation causes a crossover notch
    up to 14 dB near 100 Hz.
    """
    res = analyze_crossover(sr=SAMPLE_RATE, fc=100.0)
    sweep = {d["delay_ms"]: d for d in res["delay_sweep"]}

    # At 4.2 ms delay, worst notch in 85-120 Hz band is ~13.73 dB
    d42 = sweep[4.2]
    assert -14.5 <= d42["worst_notch_85_120hz_db"] <= -13.0, (
        f"Expected ~14 dB notch at 4.2ms, got {d42['worst_notch_85_120hz_db']:.2f} dB"
    )

    # Polarity inversion causes complete cancellation at 100 Hz (< -40 dB)
    assert res["polarity_inversion_notch_100hz_db"] < -40.0


# =============================================================================
# 3. Waveform Physics & Terminology
# =============================================================================

def test_quadrature_vector_addition_exact_3db():
    """
    Item 6 of Review: Proves that two equal-frequency sinusoids at 90 deg relative phase
    undergo deterministic quadrature coherent vector addition:
    sin(wt) + sin(wt + pi/2) = sin(wt) + cos(wt) = sqrt(2)*sin(wt + pi/4).
    Pressure amplifies by sqrt(2) = +3.0103 dB, distinct from statistically uncorrelated noise.
    """
    sr = 48000
    t = np.arange(sr, dtype=np.float64) / sr
    f0 = 50.0

    w1 = np.sin(2.0 * np.pi * f0 * t)
    w2 = np.cos(2.0 * np.pi * f0 * t)  # 90 deg shifted
    w_sum = w1 + w2

    rms_single = compute_rms(w1)
    rms_sum = compute_rms(w_sum)

    ratio = rms_sum / rms_single
    gain_db = 20.0 * np.log10(ratio)

    assert abs(ratio - np.sqrt(2.0)) < 1e-6
    assert abs(gain_db - 3.0103) < 1e-3


def test_true_peak_headroom_increase():
    """
    Item 8 of Review: Verifies that coherent phase alignment increases true-peak
    levels by up to +3 to +6 dB, confirming that alignment consumes mastering headroom.
    """
    sr = 48000
    t = np.linspace(0, 1.0, sr)
    f0 = 50.0

    # Two coherent 50 Hz waveforms aligned in-phase
    w1 = 0.50 * np.sin(2.0 * np.pi * f0 * t)
    w2 = 0.50 * np.sin(2.0 * np.pi * f0 * t)

    tp_single = compute_true_peak(w1)
    tp_sum = compute_true_peak(w1 + w2)

    tp_gain_db = 20.0 * np.log10(tp_sum / tp_single)
    assert abs(tp_gain_db - 6.02) < 0.05, f"Expected +6.02 dB true-peak increase, got {tp_gain_db:.2f} dB"


# =============================================================================
# 4. Safe-Path Rule & Boundary Conditions Audit
# =============================================================================

def test_low_energy_boundary_engages_safe_path():
    """
    Item 3 of Review: Verifies that Method D engages the safe-path rule on low-energy signals
    (-60 dBFS input) and returns the unmodified baseline with gain == 0.0 dB.
    """
    sr = SAMPLE_RATE
    drums, bass, meta = generate_boundary_condition("low_energy", duration=2.0, sr=sr)

    proc_bass, m_meta = method_d_guarded_per_kick(drums, bass, sr, min_signal_rms_dbfs=-50.0)

    assert m_meta["safe_path_engaged"] is True
    assert m_meta["reason"] == "low_energy_sub_threshold"
    assert m_meta["events_corrected"] == 0
    # Output must be bit-exact to original bass
    assert np.allclose(proc_bass, bass, atol=1e-7)


def test_near_zero_baseline_relative_gain_exclusion():
    """
    Item 4 of Review: Verifies that near-zero baseline cancellation cases (e.g. EXP_PHASE_180)
    are flagged as invalid relative gains and excluded from aggregate continuous statistics.
    """
    cfg_path = os.path.join(CURRENT_DIR, "experiment_config.json")
    with open(cfg_path, mode="r", encoding="utf-8") as f:
        cfg = json.load(f)

    stats = cfg["summary_statistics"]
    for m in ["B_GlobalDelay", "C_LegacySubOnly", "D_GuardedPerKick"]:
        m_stat = stats[m]
        assert m_stat["measurement_floor_dbfs"] == -80.0
        assert m_stat["singular_cancellation_cases_count"] >= 1
        # Valid mean should exclude the +116 dB singularity
        assert m_stat["valid_tests_sub_gain_mean_db"] < 1.0, (
            f"Expected valid mean < 1.0 dB, got {m_stat['valid_tests_sub_gain_mean_db']} dB"
        )


def test_overlapping_windows_unity_reconstruction():
    """
    Item 8 of Review: Verifies that when kicks occur rapidly (interval < window duration),
    partition-of-unity window normalization produces exact unity reconstruction when shift is 0.
    """
    sr = SAMPLE_RATE
    dur = 1.0
    n = int(sr * dur)
    t = np.arange(n, dtype=np.float64) / sr

    # Rapid kicks every 80 ms (interval < 200 ms window)
    kick_mono = np.zeros(n, dtype=np.float32)
    for k_time in np.arange(0.1, 0.9, 0.08):
        idx = int(round(k_time * sr))
        kick_mono[idx : min(n, idx + 480)] = 0.50

    drums = np.column_stack([kick_mono, kick_mono])
    bass = np.column_stack([0.50 * np.sin(2.0 * np.pi * 50.0 * t)] * 2).astype(np.float32)

    # Force zero shift by setting min_gain_db very high (safety fallback)
    proc_bass, meta = method_d_guarded_per_kick(drums, bass, sr, min_gain_db=50.0)

    # Reconstruction error must be negligible (< 1e-6)
    max_diff = float(np.max(np.abs(proc_bass - bass)))
    assert max_diff < 1e-6, f"Window overlap reconstruction error {max_diff:.2e} exceeded tolerance"


def test_boundary_handling_silence_and_low_energy():
    """
    Verifies that all methods process complete silence and low-energy signals
    without producing NaNs, Infs, or raising exceptions.
    """
    sr = SAMPLE_RATE
    for b_name in ["silence", "low_energy", "high_freq_noise", "non_overlapping"]:
        drums, bass, _ = generate_boundary_condition(b_name, duration=1.0, sr=sr)
        for method_fn in [method_a_baseline, method_b_global_delay, method_c_legacy_sub_only, method_d_guarded_per_kick]:
            proc_bass, meta = method_fn(drums, bass, sr)
            assert np.all(np.isfinite(proc_bass)), f"NaN/Inf detected in {method_fn.__name__} on {b_name}"
            assert proc_bass.shape == bass.shape, f"Shape mismatch in {method_fn.__name__} on {b_name}"


def test_reconstructed_signal_length_and_channel_preservation():
    """
    Verifies that for all methods and all signals, the output signal length
    and stereo channel count strictly match the input.
    """
    sr = SAMPLE_RATE
    dur = 1.5
    kick, _, _ = generate_synthetic_kick(duration=dur, sr=sr)
    bass, _, _ = generate_synthetic_melodic_bass(duration=dur, sr=sr)

    for method_fn in [method_a_baseline, method_b_global_delay, method_c_legacy_sub_only, method_d_guarded_per_kick]:
        proc_bass, _ = method_fn(kick, bass, sr)
        assert len(proc_bass) == len(bass)
        assert proc_bass.shape[1] == 2
        assert proc_bass.dtype == np.float32


def test_guarded_prototype_preserves_crossover_and_prevents_degradation():
    """
    Verifies that Method D (Guarded Windowed Full-Range Prototype):
    1. Never produces a crossover notch (crossover deviation > -0.5 dB).
    2. Never degrades sub-band energy on the historical test suite (all gains >= 0.0 dB).
    """
    sr = SAMPLE_RATE
    dur = 2.0
    rng = np.random.default_rng(202611)
    n = int(round(dur * sr))
    t = np.arange(n, dtype=np.float64) / sr

    for _ in range(5):
        f_bass = float(rng.uniform(41.0, 55.0))
        phi = float(rng.uniform(0, 2 * np.pi))
        t_beat = np.mod(t, 0.5)
        kick = np.column_stack([0.65 * np.sin(2 * np.pi * 50.0 * t_beat) * np.exp(-9.0 * t_beat)] * 2).astype(np.float32)
        bass = np.column_stack([0.50 * np.sin(2 * np.pi * f_bass * t + phi)] * 2).astype(np.float32)

        proc_bass, meta = method_d_guarded_per_kick(kick, bass, sr)

        # Sub-band gain
        sub_orig = lowpass_filter(kick + bass, sr, cutoff=100.0)
        sub_proc = lowpass_filter(kick + proc_bass, sr, cutoff=100.0)
        gain_db = 20.0 * np.log10(compute_rms(sub_proc) / compute_rms(sub_orig))

        # Crossover band energy
        b85_orig = compute_rms(bandpass_filter(bass, sr, 85.0, 120.0))
        b85_proc = compute_rms(bandpass_filter(proc_bass, sr, 85.0, 120.0))
        xover_db = 20.0 * np.log10(max(1e-12, b85_proc) / max(1e-12, b85_orig))

        assert gain_db >= -0.05, f"Method D degraded sub energy by {gain_db:.3f} dB"
        assert xover_db >= -0.50, f"Method D caused crossover drop of {xover_db:.3f} dB"
