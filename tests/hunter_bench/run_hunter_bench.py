"""
PHARMAKON HUNTER v1.0 // 7-Stress-Test Benchmark Runner
Executes the full test suite against resonance_hunter.py reference engine.
Measures:
1. Tracking Delay (ms) & RMSE on Chirp
2. Suppression Depth (dB) on steady resonance
3. Zipper Noise / THD+N Click Detection on rapid modulation
4. Release Transparency & Return-to-0dB time in gaps
5. Decoy Resistance (Prominence lock vs Loud Static Trap)
6. Step Response Time & Legato Click Immunity
7. Null Test Residual (dBFS) on clean acoustic audio
"""

import os
import json
import numpy as np
import scipy.signal
import soundfile as sf
import time
from resonance_hunter import ResonanceHunter

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))

def measure_rms_db(sig: np.ndarray) -> float:
    rms = np.sqrt(np.mean(sig**2))
    return float(20.0 * np.log10(max(rms, 1e-12)))

def run_suite():
    print("=" * 70)
    print("   PHARMAKON HUNTER v1.0 // 7 STRESS-TEST BENCHMARK SUITE")
    print("   Target: Adaptive Resonance Auto-Tracking Verification")
    print("=" * 70)
    
    results = {}
    total_passed = 0
    
    # -------------------------------------------------------------
    # TEST 1: Tracking Delay & Follow Error (Chirp 3.5 -> 7.5 kHz)
    # -------------------------------------------------------------
    p1 = os.path.join(BENCH_DIR, "test_01_chirp_delay.wav")
    audio1, fs1 = sf.read(p1)
    hunter1 = ResonanceHunter(fs=fs1, num_nodes=1)
    
    t0 = time.perf_counter()
    out1, telem1 = hunter1.process(audio1)
    proc_time1 = time.perf_counter() - t0
    
    t_mask = (telem1["time"] >= 1.0) & (telem1["time"] <= 4.0)
    eval_t = telem1["time"][t_mask]
    eval_f0 = telem1["f0"][t_mask]
    
    f_true = 3500.0 + (7500.0 - 3500.0) * (eval_t - 0.5) / 4.0
    freq_slope = (7500.0 - 3500.0) / 4.0 # 1000 Hz / sec
    
    lags_ms = (f_true - eval_f0) / freq_slope * 1000.0
    mean_lag_ms = float(np.mean(lags_ms))
    max_lag_ms = float(np.max(np.abs(lags_ms)))
    
    pass_1 = bool(0.0 <= mean_lag_ms <= 20.0)
    total_passed += int(pass_1)
    results["test_01_chirp_delay"] = {
        "mean_lag_ms": round(mean_lag_ms, 2),
        "max_lag_ms": round(max_lag_ms, 2),
        "rtf": round(len(audio1) / (fs1 * proc_time1), 1),
        "passed": pass_1,
        "criteria": "Mean causal tracking lag <= 20 ms"
    }
    print(f"\n[TEST 1] Chirp Tracking Delay: Mean Lag = {mean_lag_ms:.2f} ms | Max = {max_lag_ms:.2f} ms")
    print(f"         Status: {'PASSED' if pass_1 else 'FAILED'} (RTF: {results['test_01_chirp_delay']['rtf']}x)")
    
    # -------------------------------------------------------------
    # TEST 2: Suppression Depth on Steady 5.2 kHz Resonance
    # -------------------------------------------------------------
    p2 = os.path.join(BENCH_DIR, "test_02_suppression_depth.wav")
    audio2, fs2 = sf.read(p2)
    hunter2 = ResonanceHunter(fs=fs2, num_nodes=1)
    
    out2, telem2 = hunter2.process(audio2)
    steady_mask = (telem2["time"] >= 1.5) & (telem2["time"] <= 3.5)
    mean_gain_db = float(np.mean(telem2["gain_db"][steady_mask]))
    steady_f0 = float(np.mean(telem2["f0"][steady_mask]))
    
    pass_2 = bool((-12.0 <= mean_gain_db <= -6.0) and (abs(steady_f0 - 5200.0) < 5.0))
    total_passed += int(pass_2)
    results["test_02_suppression_depth"] = {
        "attenuation_db": round(mean_gain_db, 2),
        "steady_f0_hz": round(steady_f0, 2),
        "passed": pass_2,
        "criteria": "Attenuation between -6.0 and -12.0 dB, f0 error < 5 Hz"
    }
    print(f"\n[TEST 2] Suppression Depth: Gain = {mean_gain_db:.2f} dB at {steady_f0:.1f} Hz (Target: 5200 Hz)")
    print(f"         Status: {'PASSED' if pass_2 else 'FAILED'}")
    
    # -------------------------------------------------------------
    # TEST 3: Click / THD+N Zipper Noise Verification
    # -------------------------------------------------------------
    p3 = os.path.join(BENCH_DIR, "test_03_click_thd.wav")
    audio3, fs3 = sf.read(p3)
    hunter3 = ResonanceHunter(fs=fs3, num_nodes=1)
    
    out3, telem3 = hunter3.process(audio3)
    sos_hp = scipy.signal.butter(8, 14000.0, btype='highpass', fs=fs3, output='sos')
    hf_in = scipy.signal.sosfilt(sos_hp, audio3)
    hf_out = scipy.signal.sosfilt(sos_hp, out3)
    peak_in_db = 20.0 * np.log10(max(np.max(np.abs(hf_in)), 1e-12))
    peak_out_db = 20.0 * np.log10(max(np.max(np.abs(hf_out)), 1e-12))
    added_hf_db = float(peak_out_db - peak_in_db)
    
    pass_3 = bool(added_hf_db <= 0.1)
    total_passed += int(pass_3)
    results["test_03_click_thd"] = {
        "added_hf_distortion_db": round(added_hf_db, 3),
        "passed": pass_3,
        "criteria": "Added HF distortion <= 0.1 dB (zero zipper noise)"
    }
    print(f"\n[TEST 3] Zipper Noise / Click Test: Added HF Distortion (>14 kHz) = {added_hf_db:.3f} dB")
    print(f"         Status: {'PASSED' if pass_3 else 'FAILED'}")
    
    # -------------------------------------------------------------
    # TEST 4: Transparency & Gaps (Release Verification)
    # -------------------------------------------------------------
    p4 = os.path.join(BENCH_DIR, "test_04_transparency_gaps.wav")
    audio4, fs4 = sf.read(p4)
    hunter4 = ResonanceHunter(fs=fs4, num_nodes=1)
    
    out4, telem4 = hunter4.process(audio4)
    gap_mask = (telem4["time"] >= 2.6) & (telem4["time"] <= 3.3)
    gap_gains = telem4["gain_db"][gap_mask]
    min_gap_gain = float(np.min(gap_gains))
    
    pass_4 = bool(min_gap_gain >= -0.5)
    total_passed += int(pass_4)
    results["test_04_transparency_gaps"] = {
        "gap_residual_gain_db": round(min_gap_gain, 2),
        "passed": pass_4,
        "criteria": "Gain returns to >= -0.5 dB in silence gaps"
    }
    print(f"\n[TEST 4] Transparency in Gaps: Gain in silence interval = {min_gap_gain:.2f} dB")
    print(f"         Status: {'PASSED' if pass_4 else 'FAILED'}")
    
    # -------------------------------------------------------------
    # TEST 5: Decoy Trap (Loud Static 4.0 kHz vs Moving Anomaly)
    # -------------------------------------------------------------
    p5 = os.path.join(BENCH_DIR, "test_05_decoy_trap.wav")
    audio5, fs5 = sf.read(p5)
    hunter5 = ResonanceHunter(fs=fs5, num_nodes=1)
    
    out5, telem5 = hunter5.process(audio5)
    trap_mask = (telem5["time"] >= 1.5) & (telem5["time"] <= 3.5)
    trap_f0s = telem5["f0"][trap_mask]
    max_sweep_f0 = float(np.max(trap_f0s))
    
    # Pass criterion: Hunter rejects staying trapped on 4000 Hz decoy and captures moving anomaly (>6200 Hz)
    pass_5 = bool(max_sweep_f0 >= 6200.0)
    total_passed += int(pass_5)
    results["test_05_decoy_trap"] = {
        "max_tracked_f0_hz": round(max_sweep_f0, 2),
        "decoy_rejected": pass_5,
        "passed": pass_5,
        "criteria": "Captures moving anomaly up to > 6200 Hz (rejects static 4000 Hz trap)"
    }
    print(f"\n[TEST 5] Decoy Trap Test: Max Tracked Frequency = {max_sweep_f0:.1f} Hz (Decoy: 4000 Hz)")
    print(f"         Status: {'PASSED' if pass_5 else 'FAILED'}")
    
    # -------------------------------------------------------------
    # TEST 6: Step / Legato Transition (Instant jump 3.5 -> 7.5 kHz)
    # -------------------------------------------------------------
    p6 = os.path.join(BENCH_DIR, "test_06_step_legato.wav")
    audio6, fs6 = sf.read(p6)
    hunter6 = ResonanceHunter(fs=fs6, num_nodes=1)
    
    out6, telem6 = hunter6.process(audio6)
    post_jump_mask = telem6["time"] >= 1.5
    post_times = telem6["time"][post_jump_mask]
    post_f0 = telem6["f0"][post_jump_mask]
    
    reached_indices = np.where(post_f0 >= 7000.0)[0]
    if len(reached_indices) > 0:
        capture_time_ms = float((post_times[reached_indices[0]] - 1.5) * 1000.0)
    else:
        capture_time_ms = 999.0
        
    pass_6 = bool(0.0 <= capture_time_ms <= 40.0)
    total_passed += int(pass_6)
    results["test_06_step_legato"] = {
        "capture_time_ms": round(capture_time_ms, 2),
        "passed": pass_6,
        "criteria": "Capture time to new target < 40 ms"
    }
    print(f"\n[TEST 6] Step / Legato Transition: Target Capture Time = {capture_time_ms:.1f} ms")
    print(f"         Status: {'PASSED' if pass_6 else 'FAILED'}")
    
    # -------------------------------------------------------------
    # TEST 7: Null / False-Positive Benchmark on Clean Audio
    # -------------------------------------------------------------
    p7 = os.path.join(BENCH_DIR, "test_07_null_clean.wav")
    audio7, fs7 = sf.read(p7)
    hunter7 = ResonanceHunter(fs=fs7, num_nodes=1)
    
    out7, telem7 = hunter7.process(audio7)
    max_active_gain = float(np.min(telem7["gain_db"]))
    null_diff = audio7 - out7
    null_dbfs = measure_rms_db(null_diff)
    
    pass_7 = bool((max_active_gain >= -0.5) and (null_dbfs < -55.0))
    total_passed += int(pass_7)
    results["test_07_null_clean"] = {
        "max_gain_dip_db": round(max_active_gain, 2),
        "null_diff_rms_dbfs": round(null_dbfs, 2),
        "passed": pass_7,
        "criteria": "Gain stays at 0.0 dB (min >= -0.5 dB), Null RMS < -55 dBFS"
    }
    print(f"\n[TEST 7] Null / False-Positive Test: Max Gain Dip = {max_active_gain:.2f} dB | Null Diff = {null_dbfs:.2f} dBFS")
    print(f"         Status: {'PASSED' if pass_7 else 'FAILED'}")
    
    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"   BENCHMARK VERDICT: {total_passed}/7 TESTS PASSED ({total_passed*100//7}%)")
    print("=" * 70)
    
    results["summary"] = {
        "total_tests": 7,
        "total_passed": total_passed,
        "all_passed": bool(total_passed == 7)
    }
    
    summary_path = os.path.join(BENCH_DIR, "benchmark_results.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Results archived to: {summary_path}\n")
    return total_passed == 7

if __name__ == "__main__":
    run_suite()
