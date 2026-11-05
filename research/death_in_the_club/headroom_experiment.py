"""
PHARMAKON Research Task 04: Death in the Club
Module: headroom_experiment.py

Final Publication Experiment: Investigating the true-peak and headroom cost
of increasing sub-band energy through kick/bass phase alignment.

Evaluates Methods A, B, C, and D across all 54 standardized scenarios without
post-processing normalization or limiting.

RECONCILIATION NOTE (2026-11-05):
This module now performs MEASUREMENT ONLY and writes headroom_measurements.csv.
All statistics, Figure 6 and HEADROOM_ANALYSIS.md are derived exclusively from
that CSV by headroom_analysis.py. The previous version of this file embedded
hand-typed statistics in the report template that were never computed from the
data (preserved in original_pre_reconciliation/ for comparison).

Outputs:
- headroom_measurements.csv  (then delegates to headroom_analysis.main())
"""

import sys
import os
import csv
import numpy as np
from typing import Dict, Any, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PHARMAKON_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PHARMAKON_ROOT not in sys.path:
    sys.path.insert(0, PHARMAKON_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from synthetic_signals import (
    generate_synthetic_kick,
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
)

CSV_OUTPUT_PATH = os.path.join(CURRENT_DIR, "headroom_measurements.csv")

MEASUREMENT_FLOOR_DBFS = -80.0
CEILING_DBTP = 0.0  # Fixed reference ceiling for headroom calculations


def to_db(linear_val: float) -> float:
    """Converts linear amplitude to dBFS/dBTP. Values <= 1e-12 are clamped to -120.0."""
    if linear_val <= 1e-12:
        return -120.0
    return float(20.0 * np.log10(linear_val))


def evaluate_headroom_scenario(
    exp_id: str,
    signal_cat: str,
    signal_desc: str,
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int = SAMPLE_RATE,
) -> List[Dict[str, Any]]:
    """Evaluates one scenario across Methods A, B, C, and D for headroom/true-peak."""
    results: List[Dict[str, Any]] = []

    # Method A Baseline
    bass_a, _ = method_a_baseline(drums, bass, sr)
    sum_a = drums + bass_a
    sub_sum_a = lowpass_filter(sum_a, sr, cutoff=100.0, order=4)
    rms_sub_a_db = to_db(compute_rms(sub_sum_a))
    baseline_is_near_zero = bool(rms_sub_a_db <= MEASUREMENT_FLOOR_DBFS)

    # Baseline True Peak (4x polyphase oversampling, scipy resample_poly default FIR)
    tp_a_linear = compute_true_peak(sum_a, oversample=4)
    tp_a_dbtp = to_db(tp_a_linear)
    headroom_a_db = CEILING_DBTP - tp_a_dbtp

    methods = [
        ("A_Baseline", lambda: method_a_baseline(drums, bass, sr)),
        ("B_GlobalDelay", lambda: method_b_global_delay(drums, bass, sr, max_lag_ms=6.0, min_signal_rms_dbfs=-50.0)),
        ("C_LegacySubOnly", lambda: method_c_legacy_sub_only(drums, bass, sr, max_lag_ms=6.0, crossover_freq=100.0)),
        ("D_GuardedPerKick", lambda: method_d_guarded_per_kick(drums, bass, sr, max_lag_ms=3.0, min_gain_db=0.5, min_signal_rms_dbfs=-50.0)),
    ]

    for m_name, m_func in methods:
        proc_bass, m_meta = m_func()
        proc_sum = drums + proc_bass

        proc_sub_sum = lowpass_filter(proc_sum, sr, cutoff=100.0, order=4)
        rms_sub_proc_db = to_db(compute_rms(proc_sub_sum))
        delta_sub_gain_db = rms_sub_proc_db - rms_sub_a_db

        tp_proc_linear = compute_true_peak(proc_sum, oversample=4)
        tp_proc_dbtp = to_db(tp_proc_linear)
        delta_tp_db = tp_proc_dbtp - tp_a_dbtp

        headroom_proc_db = CEILING_DBTP - tp_proc_dbtp
        delta_headroom_db = headroom_proc_db - headroom_a_db  # == -delta_tp_db

        lag_ms = m_meta.get("best_lag_ms", m_meta.get("average_shift_ms", 0.0))
        safe_path = m_meta.get("safe_path_engaged", False)
        if m_name == "D_GuardedPerKick":
            # Method D applies per-event shifts; it has no single global lag/polarity.
            # applied_lag_ms = mean |shift| over ALL detected events (rejected events count as 0 ms).
            pols = m_meta.get("applied_polarities", [])
            n_inv = int(m_meta.get("events_polarity_inverted", 0))
            pol = -1.0 if (pols and n_inv == len(pols)) else 1.0  # -1 only if every event inverted
            lag_semantics = "mean_abs_per_event_shift_ms"
            ev_det = int(m_meta.get("events_detected", 0))
            ev_cor = int(m_meta.get("events_corrected", 0))
        else:
            pol = m_meta.get("polarity", 1.0)
            n_inv = ""
            lag_semantics = "none" if m_name == "A_Baseline" else "single_global_lag_ms"
            ev_det = ""
            ev_cor = ""

        results.append({
            "exp_id": exp_id,
            "signal_category": signal_cat,
            "signal_description": signal_desc,
            "method": m_name,
            "applied_lag_ms": round(float(lag_ms), 3),
            "applied_polarity": float(pol),
            "safe_path_engaged": bool(safe_path),
            "baseline_is_near_zero": bool(baseline_is_near_zero),
            "is_relative_gain_valid": bool(not baseline_is_near_zero),
            "sub_rms_baseline_dbfs": round(rms_sub_a_db, 4),
            "sub_rms_proc_dbfs": round(rms_sub_proc_db, 4),
            "delta_sub_gain_db": round(delta_sub_gain_db, 4),
            "true_peak_baseline_dbtp": round(tp_a_dbtp, 4),
            "true_peak_proc_dbtp": round(tp_proc_dbtp, 4),
            "delta_true_peak_db": round(delta_tp_db, 4),
            "headroom_baseline_db": round(headroom_a_db, 4),
            "headroom_proc_db": round(headroom_proc_db, 4),
            "delta_headroom_db": round(delta_headroom_db, 4),
            # --- Reconciliation audit columns (appended; existing columns unchanged) ---
            "is_tp_delta_valid": bool(tp_a_dbtp > MEASUREMENT_FLOOR_DBFS),
            "true_peak_baseline_linear": round(float(tp_a_linear), 8),
            "true_peak_proc_linear": round(float(tp_proc_linear), 8),
            "baseline_exceeds_0dbtp": bool(tp_a_dbtp > CEILING_DBTP),
            "proc_exceeds_0dbtp": bool(tp_proc_dbtp > CEILING_DBTP),
            "lag_semantics": lag_semantics,
            "d_events_detected": ev_det,
            "d_events_corrected": ev_cor,
            "d_events_polarity_inverted": n_inv,
        })

    return results


def run_headroom_experiment() -> List[Dict[str, Any]]:
    """Runs all 54 test scenarios and logs headroom metrics."""
    all_rows: List[Dict[str, Any]] = []
    sr = SAMPLE_RATE
    dur = 3.0

    print(">>> Executing Headroom & True-Peak Cost Experiment...")

    # Suite 1: Pure Phase Sweep (0 to 180 deg)
    for p_deg in [0, 30, 60, 90, 120, 150, 180]:
        rad = np.deg2rad(p_deg)
        t = np.arange(int(round(dur * sr)), dtype=np.float64) / sr
        d = np.column_stack([0.50 * np.sin(2.0 * np.pi * 50.0 * t)] * 2).astype(np.float32)
        b = np.column_stack([0.50 * np.sin(2.0 * np.pi * 50.0 * t + rad)] * 2).astype(np.float32)
        all_rows.extend(evaluate_headroom_scenario(f"EXP_PHASE_{p_deg:03d}", "pure_phase_sweep", f"50Hz {p_deg} deg phase", d, b, sr))

    # Suite 2: Kick + Bass Delay Sweep (0 to 6 ms)
    for d_ms in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
        kick, t, _ = generate_synthetic_kick(duration=dur, sr=sr, bpm=120.0)
        delay_samples = int(round(d_ms * 1e-3 * sr))
        b_mono = 0.50 * np.sin(2.0 * np.pi * 50.0 * t)
        b_shifted = np.roll(b_mono, delay_samples)
        if delay_samples > 0:
            b_shifted[:delay_samples] = 0
        bass = np.column_stack([b_shifted, b_shifted]).astype(np.float32)
        all_rows.extend(evaluate_headroom_scenario(f"EXP_DELAY_{int(d_ms*10):02d}MS", "kick_bass_delay_sweep", f"Kick + 50Hz bass delay {d_ms:.1f}ms", kick, bass, sr))

    # Suite 3: Melodic Bassline (E1-G1-A1-C2) + Kick
    for init_p in [0, 90, 180]:
        kick, _, _ = generate_synthetic_kick(duration=dur, sr=sr, bpm=120.0)
        bass, _, _ = generate_synthetic_melodic_bass(duration=dur, sr=sr, notes=(41.20, 48.99, 55.00, 65.41), note_duration=0.75, initial_phase=np.deg2rad(init_p))
        all_rows.extend(evaluate_headroom_scenario(f"EXP_MELODIC_P{init_p:03d}", "melodic_bassline", f"Melodic bassline init phase {init_p} deg", kick, bass, sr))

    # Suite 4: Harmonic Bass with Attack Transients
    for f0_val in [45.0, 50.0, 55.0]:
        kick, _, _ = generate_synthetic_kick(duration=dur, sr=sr, bpm=120.0)
        bass, _, _ = generate_synthetic_harmonic_bass(duration=dur, sr=sr, f0=f0_val, harmonics=(1.0, 0.65, 0.35, 0.15), attack_ms=8.0, repeat_interval=0.5)
        all_rows.extend(evaluate_headroom_scenario(f"EXP_HARMONIC_{int(f0_val)}HZ", "harmonic_bass_transients", f"Harmonic bass f0={f0_val}Hz", kick, bass, sr))

    # Suite 5: Historical 30-Run Random Melodic/Harmonic Benchmark (Seed 202611)
    # NOTE: the kick here is a 50 Hz exponentially decaying sine (no frequency sweep).
    rng = np.random.default_rng(202611)
    n = int(sr * dur)
    t = np.arange(n, dtype=np.float64) / sr
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
        d = np.column_stack([kick_mono, kick_mono]).astype(np.float32)
        b = np.column_stack([bass_mono, bass_mono]).astype(np.float32)
        all_rows.extend(evaluate_headroom_scenario(f"EXP_HIST_RUN_{run_i:02d}", "historical_30_runs_seed202611", f"Historical run {run_i} (f_bass={f_bass:.2f}Hz)", d, b, sr))

    # Suite 6: Boundary Conditions
    for b_cond in ["silence", "low_energy", "high_freq_noise", "non_overlapping"]:
        drums_b, bass_b, _ = generate_boundary_condition(b_cond, duration=dur, sr=sr)
        all_rows.extend(evaluate_headroom_scenario(f"EXP_BOUNDARY_{b_cond.upper()}", "boundary_conditions", f"Boundary: {b_cond}", drums_b, bass_b, sr))

    fieldnames = list(all_rows[0].keys())
    with open(CSV_OUTPUT_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved {len(all_rows)} rows to {CSV_OUTPUT_PATH}")

    return all_rows


if __name__ == "__main__":
    run_headroom_experiment()
    # All statistics, Figure 6 and the report are derived from the CSV only.
    import headroom_analysis
    headroom_analysis.main()
