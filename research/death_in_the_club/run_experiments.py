"""
PHARMAKON Research Task 04: Death in the Club
Module: run_experiments.py

Orchestrates the experimental validation suite across all signal classes and
evaluates Methods A, B, C, and D. Outputs measurements.csv and experiment_config.json.
"""

import sys
import os
import json
import csv
import platform
import scipy
import numpy as np
import scipy.signal as signal
from typing import Dict, Any, List, Tuple

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

CSV_OUTPUT_PATH = os.path.join(CURRENT_DIR, "measurements.csv")
CONFIG_OUTPUT_PATH = os.path.join(CURRENT_DIR, "experiment_config.json")
MEASUREMENT_FLOOR_DBFS = -80.0  # Explicit floor for baseline energy validity


def to_db(linear_val: float) -> float:
    """Converts linear amplitude to dBFS, safe against zero."""
    if linear_val <= 1e-12:
        return -120.0
    return float(20.0 * np.log10(linear_val))


def evaluate_run(
    exp_id: str,
    signal_cat: str,
    signal_desc: str,
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int = SAMPLE_RATE,
) -> List[Dict[str, Any]]:
    """
    Evaluates one test case through Methods A, B, C, and D and computes
    all standardized physical and spectral metrics.
    """
    results: List[Dict[str, Any]] = []

    # 1. Evaluate baseline sum (Method A)
    bass_a, meta_a = method_a_baseline(drums, bass, sr)
    sum_a = drums + bass_a
    sub_sum_a = lowpass_filter(sum_a, sr, cutoff=100.0)
    rms_sub_a = compute_rms(sub_sum_a)
    rms_sub_a_db = to_db(rms_sub_a)
    baseline_is_near_zero = bool(rms_sub_a_db <= MEASUREMENT_FLOOR_DBFS)

    # Crossover band (85-120 Hz) bass energy
    b85_a = bandpass_filter(bass_a, sr, 85.0, 120.0)
    rms_b85_a = compute_rms(b85_a)
    rms_b85_a_db = to_db(rms_b85_a)

    # Peak & True-Peak
    peak_a = np.max(np.abs(sum_a))
    tp_a = compute_true_peak(sum_a)

    methods = [
        ("A_Baseline", lambda: method_a_baseline(drums, bass, sr)),
        ("B_GlobalDelay", lambda: method_b_global_delay(drums, bass, sr, max_lag_ms=6.0)),
        ("C_LegacySubOnly", lambda: method_c_legacy_sub_only(drums, bass, sr, max_lag_ms=6.0, crossover_freq=100.0)),
        ("D_GuardedPerKick", lambda: method_d_guarded_per_kick(drums, bass, sr, max_lag_ms=3.0, min_gain_db=0.5)),
    ]

    for m_name, m_func in methods:
        proc_bass, m_meta = m_func()
        proc_sum = drums + proc_bass

        # Sub-band sum (<100 Hz)
        proc_sub_sum = lowpass_filter(proc_sum, sr, cutoff=100.0)
        rms_sub_proc = compute_rms(proc_sub_sum)
        rms_sub_proc_db = to_db(rms_sub_proc)

        # Gain relative to Method A baseline (explicitly defined)
        sub_gain_db = rms_sub_proc_db - rms_sub_a_db

        # Crossover region (85-120 Hz) bass energy
        b85_proc = bandpass_filter(proc_bass, sr, 85.0, 120.0)
        rms_b85_proc = compute_rms(b85_proc)
        rms_b85_proc_db = to_db(rms_b85_proc)
        xover_delta_db = rms_b85_proc_db - rms_b85_a_db

        # Peak & True-Peak
        peak_proc = np.max(np.abs(proc_sum))
        tp_proc = compute_true_peak(proc_sum)
        delta_peak_db = to_db(peak_proc) - to_db(peak_a)
        delta_tp_db = to_db(tp_proc) - to_db(tp_a)

        # High-frequency transient displacement (>200 Hz)
        hi_bass_a = bandpass_filter(bass_a, sr, 200.0, 8000.0)
        hi_bass_proc = bandpass_filter(proc_bass, sr, 200.0, 8000.0)
        hi_diff_rms = compute_rms(hi_bass_proc - hi_bass_a)
        transient_preserved = bool(hi_diff_rms < 1e-4)

        # Classification
        if sub_gain_db >= 0.10:
            status = "IMPROVED"
        elif sub_gain_db <= -0.10:
            status = "DEGRADED"
        else:
            status = "NEUTRAL"

        lag_ms = m_meta.get("best_lag_ms", m_meta.get("average_shift_ms", 0.0))
        pol = m_meta.get("polarity", 1.0)
        safe_path = m_meta.get("safe_path_engaged", False)

        row = {
            "exp_id": exp_id,
            "signal_category": signal_cat,
            "signal_description": signal_desc,
            "method": m_name,
            "applied_lag_ms": round(float(lag_ms), 3),
            "applied_polarity": float(pol),
            "safe_path_engaged": bool(safe_path),
            "baseline_is_near_zero": bool(baseline_is_near_zero),
            "is_relative_gain_valid": bool(not baseline_is_near_zero),
            "sub_sum_baseline_dbfs": round(rms_sub_a_db, 3),
            "sub_sum_proc_dbfs": round(rms_sub_proc_db, 3),
            "delta_sub_gain_db": round(sub_gain_db, 3),
            "bass_85_120hz_baseline_dbfs": round(rms_b85_a_db, 3),
            "bass_85_120hz_proc_dbfs": round(rms_b85_proc_db, 3),
            "delta_bass_85_120hz_db": round(xover_delta_db, 3),
            "sum_peak_baseline_dbfs": round(to_db(peak_a), 3),
            "sum_peak_proc_dbfs": round(to_db(peak_proc), 3),
            "delta_peak_db": round(delta_peak_db, 3),
            "true_peak_baseline_dbfs": round(to_db(tp_a), 3),
            "true_peak_proc_dbfs": round(to_db(tp_proc), 3),
            "delta_true_peak_db": round(delta_tp_db, 3),
            "transient_preserved": transient_preserved,
            "status": status,
        }
        results.append(row)

    return results


def run_all_experiments() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Runs all systematic experiment suites and compiles full dataset."""
    all_rows: List[Dict[str, Any]] = []
    sr = SAMPLE_RATE
    dur = 3.0

    print(">>> PHARMAKON RESEARCH TASK 04: Running Experimental Validation Suite...")

    # Suite 1: Pure Phase Sweep (50 Hz Sines: In-Phase to Anti-Phase)
    print("  [Suite 1/6] Evaluating Pure 50 Hz Phase Sweep (0 to 180 deg)...")
    phase_degs = [0, 30, 60, 90, 120, 150, 180]
    for p_deg in phase_degs:
        p_rad = np.deg2rad(p_deg)
        t = np.arange(int(round(dur * sr)), dtype=np.float64) / sr
        d_mono = 0.50 * np.sin(2.0 * np.pi * 50.0 * t)
        b_mono = 0.50 * np.sin(2.0 * np.pi * 50.0 * t + p_rad)
        drums = np.column_stack([d_mono, d_mono]).astype(np.float32)
        bass = np.column_stack([b_mono, b_mono]).astype(np.float32)
        rows = evaluate_run(
            exp_id=f"EXP_PHASE_{p_deg:03d}",
            signal_cat="pure_phase_sweep",
            signal_desc=f"Pure 50Hz sine sum with {p_deg} deg relative phase",
            drums=drums,
            bass=bass,
            sr=sr,
        )
        all_rows.extend(rows)

    # Suite 2: Synthetic Kick Chirp + Sustained 50 Hz Bass with Time Delay Sweep
    print("  [Suite 2/6] Evaluating Synthetic Kick + Bass Delay Sweep (0 to 6 ms)...")
    delays_ms = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    for d_ms in delays_ms:
        kick, t, _ = generate_synthetic_kick(duration=dur, sr=sr, bpm=120.0)
        delay_samples = int(round(d_ms * 1e-3 * sr))
        b_mono = 0.50 * np.sin(2.0 * np.pi * 50.0 * t)
        # Shift bass by delay_samples
        b_shifted = np.roll(b_mono, delay_samples)
        if delay_samples > 0:
            b_shifted[:delay_samples] = 0
        bass = np.column_stack([b_shifted, b_shifted]).astype(np.float32)
        rows = evaluate_run(
            exp_id=f"EXP_DELAY_{int(d_ms*10):02d}MS",
            signal_cat="kick_bass_delay_sweep",
            signal_desc=f"Synthetic kick + 50Hz bass delayed by {d_ms:.1f}ms",
            drums=kick,
            bass=bass,
            sr=sr,
        )
        all_rows.extend(rows)

    # Suite 3: Melodic Bassline (E1, G1, A1, C2) + Synthetic Kick
    print("  [Suite 3/6] Evaluating Melodic Bassline (E1-G1-A1-C2) with Kick...")
    for init_p_deg in [0, 90, 180]:
        kick, _, _ = generate_synthetic_kick(duration=dur, sr=sr, bpm=120.0)
        bass, _, _ = generate_synthetic_melodic_bass(
            duration=dur, sr=sr, notes=(41.20, 48.99, 55.00, 65.41),
            note_duration=0.75, initial_phase=np.deg2rad(init_p_deg)
        )
        rows = evaluate_run(
            exp_id=f"EXP_MELODIC_P{init_p_deg:03d}",
            signal_cat="melodic_bassline",
            signal_desc=f"4-note bassline (41-65Hz) with kick at init phase {init_p_deg} deg",
            drums=kick,
            bass=bass,
            sr=sr,
        )
        all_rows.extend(rows)

    # Suite 4: Harmonic Bass with 2nd, 3rd, 4th Harmonics & Fast Attack Transients
    print("  [Suite 4/6] Evaluating Harmonic Bass with Attack Transients...")
    for f0_val in [45.0, 50.0, 55.0]:
        kick, _, _ = generate_synthetic_kick(duration=dur, sr=sr, bpm=120.0)
        bass, _, _ = generate_synthetic_harmonic_bass(
            duration=dur, sr=sr, f0=f0_val,
            harmonics=(1.0, 0.65, 0.35, 0.15),
            attack_ms=8.0, repeat_interval=0.5
        )
        rows = evaluate_run(
            exp_id=f"EXP_HARMONIC_{int(f0_val)}HZ",
            signal_cat="harmonic_bass_transients",
            signal_desc=f"Bass f0={f0_val}Hz with harmonics crossing 100Hz and 8ms attack",
            drums=kick,
            bass=bass,
            sr=sr,
        )
        all_rows.extend(rows)

    # Suite 5: Exact Historical 30-Run Test Replication (Seed 202611 from test_dsp_core_audit.py)
    print("  [Suite 5/6] Replicating Historical 30-Run Random Pitch/Phase Test (Seed 202611)...")
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
        drums = np.column_stack([kick_mono, kick_mono]).astype(np.float32)
        bass = np.column_stack([bass_mono, bass_mono]).astype(np.float32)
        rows = evaluate_run(
            exp_id=f"EXP_HIST_RUN_{run_i:02d}",
            signal_cat="historical_30_runs_seed202611",
            signal_desc=f"Historical test run {run_i} (f_bass={f_bass:.2f}Hz)",
            drums=drums,
            bass=bass,
            sr=sr,
        )
        all_rows.extend(rows)

    # Suite 6: Boundary Conditions (Silence, Low Energy, HF Noise, Disjoint)
    print("  [Suite 6/6] Evaluating Boundary Conditions...")
    for b_cond in ["silence", "low_energy", "high_freq_noise", "non_overlapping"]:
        drums_b, bass_b, b_meta = generate_boundary_condition(b_cond, duration=dur, sr=sr)
        rows = evaluate_run(
            exp_id=f"EXP_BOUNDARY_{b_cond.upper()}",
            signal_cat="boundary_conditions",
            signal_desc=f"Boundary condition: {b_cond}",
            drums=drums_b,
            bass=bass_b,
            sr=sr,
        )
        all_rows.extend(rows)

    # Write measurements.csv
    fieldnames = list(all_rows[0].keys())
    with open(CSV_OUTPUT_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved {len(all_rows)} measurement records to {CSV_OUTPUT_PATH}")

    # Compile reproducibility metadata & config
    config_metadata = {
        "project": "PHARMAKON Research Task 04: Death in the Club",
        "reference_paper": "Death in the Club: The Low-End Phase War Between Kick and Sub-Bass",
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
            "sample_rate_hz": SAMPLE_RATE,
            "git_commit": "0013ba7",
        },
        "seeds": {
            "historical_30_runs_seed": 202611,
            "boundary_conditions_seed": 202611,
        },
        "methods_evaluated": {
            "A_Baseline": "No correction (unaligned sum reference)",
            "B_GlobalDelay": "Single global time delay and polarity inversion across full bass stem (max_lag=6.0ms)",
            "C_LegacySubOnly": "remaster_engine.align_sub_phase (100 Hz LR4 crossover, circular roll sub-band only, max_lag=6.0ms)",
            "D_GuardedPerKick": "Proposed Reference Prototype: Guarded Windowed Full-Range Alignment (GW-FRA, max_lag=3.0ms, min_gain=0.5dB, tukey taper)",
        },
        "filters": {
            "crossover_freq_hz": 100.0,
            "crossover_evaluation_band_hz": [85.0, 120.0],
            "sub_band_evaluation_cutoff_hz": 100.0,
        },
        "summary_statistics": compute_suite_summaries(all_rows),
    }

    with open(CONFIG_OUTPUT_PATH, mode="w", encoding="utf-8") as f:
        json.dump(config_metadata, f, indent=2)
    print(f"Saved experiment configuration and metadata to {CONFIG_OUTPUT_PATH}")

    return all_rows, config_metadata


def compute_suite_summaries(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes summary statistics for each method across the suite with floor-aware rigor."""
    summaries = {}
    for m in ["A_Baseline", "B_GlobalDelay", "C_LegacySubOnly", "D_GuardedPerKick"]:
        m_rows = [r for r in rows if r["method"] == m]
        sub_gains_all = [r["delta_sub_gain_db"] for r in m_rows if r["signal_category"] != "boundary_conditions"]
        
        # Valid non-singular subset (baseline strictly above measurement floor)
        sub_gains_valid = [
            r["delta_sub_gain_db"] for r in m_rows 
            if r["signal_category"] != "boundary_conditions" and r.get("is_relative_gain_valid", True)
        ]
        singular_count = sum(1 for r in m_rows if r.get("baseline_is_near_zero", False))

        xover_drops = [r["delta_bass_85_120hz_db"] for r in m_rows if r["signal_category"] != "boundary_conditions"]

        # Historical 30-run specific metrics
        hist_rows = [r for r in rows if r["method"] == m and r["signal_category"] == "historical_30_runs_seed202611"]
        hist_gains = [r["delta_sub_gain_db"] for r in hist_rows]

        summaries[m] = {
            "total_runs": len(m_rows),
            "measurement_floor_dbfs": MEASUREMENT_FLOOR_DBFS,
            "singular_cancellation_cases_count": singular_count,
            "valid_tests_sub_gain_mean_db": round(float(np.mean(sub_gains_valid)), 4) if sub_gains_valid else 0.0,
            "valid_tests_sub_gain_min_db": round(float(np.min(sub_gains_valid)), 4) if sub_gains_valid else 0.0,
            "valid_tests_sub_gain_max_db": round(float(np.max(sub_gains_valid)), 4) if sub_gains_valid else 0.0,
            "raw_all_tests_sub_gain_mean_db": round(float(np.mean(sub_gains_all)), 4) if sub_gains_all else 0.0,
            "raw_all_tests_sub_gain_max_db": round(float(np.max(sub_gains_all)), 4) if sub_gains_all else 0.0,
            "hist_30_runs_mean_db": round(float(np.mean(hist_gains)), 4) if hist_gains else 0.0,
            "hist_30_runs_min_db": round(float(np.min(hist_gains)), 4) if hist_gains else 0.0,
            "hist_30_runs_max_db": round(float(np.max(hist_gains)), 4) if hist_gains else 0.0,
            "worst_crossover_drop_db": round(float(np.min(xover_drops)), 4) if xover_drops else 0.0,
            "improvements_count": sum(1 for r in m_rows if r["status"] == "IMPROVED"),
            "degradations_count": sum(1 for r in m_rows if r["status"] == "DEGRADED"),
            "neutral_count": sum(1 for r in m_rows if r["status"] == "NEUTRAL"),
        }
    return summaries


if __name__ == "__main__":
    run_all_experiments()
