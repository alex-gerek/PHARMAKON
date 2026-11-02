"""
PHARMAKON HUNTER v1.0 // Test Bench Generator
Generates 7 standardized test signals for verification of Adaptive Resonance Auto-Tracking:
1. test_01_chirp_delay.wav: 3.5 -> 7.5 kHz chirp over 4s under pink noise (-20 dBFS)
2. test_02_suppression_depth.wav: 5.2 kHz resonance (-12 dBFS) under pink noise (-20 dBFS)
3. test_03_click_thd.wav: Rapid frequency modulation 4.0 <-> 6.5 kHz to test zipper noise
4. test_04_transparency_gaps.wav: Alternating tone bursts and silent gaps (release verification)
5. test_05_decoy_trap.wav: Loud static tone 4.0 kHz + moving anomaly 5.2 -> 6.8 kHz
6. test_06_step_legato.wav: Instant jump 3.5 kHz -> 7.5 kHz (A/R asymmetry and click-free capture)
7. test_07_null_clean.wav: Smooth acoustic signal with no narrow resonances (null test < -60 dB)
"""

import os
import json
import numpy as np
import scipy.signal
import soundfile as sf

FS = 48000
BENCH_DIR = os.path.dirname(os.path.abspath(__file__))

def generate_pink_noise(num_samples: int, target_rms_db: float = -20.0) -> np.ndarray:
    """Generate high-quality pink noise using 1/f spectral filtering."""
    white = np.random.normal(0.0, 1.0, num_samples).astype(np.float32)
    # Filter white noise with 1/sqrt(f) filter in frequency domain
    X = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(num_samples, d=1.0 / FS)
    freqs[0] = freqs[1]  # avoid division by zero at DC
    scale = 1.0 / np.sqrt(freqs)
    scale[0] = 0.0  # remove DC
    X_pink = X * scale
    pink = np.fft.irfft(X_pink, n=num_samples).astype(np.float32)
    
    # Normalize to target RMS dB
    current_rms = np.sqrt(np.mean(pink**2))
    target_rms = 10.0 ** (target_rms_db / 20.0)
    if current_rms > 1e-9:
        pink = pink * (target_rms / current_rms)
    return pink

def db_to_linear(db: float) -> float:
    return 10.0 ** (db / 20.0)

def main():
    print("=" * 65)
    print("  PHARMAKON HUNTER // STANDARDIZED TEST BENCH GENERATOR")
    print(f"  Sampling Rate: {FS} Hz | Destination: {BENCH_DIR}")
    print("=" * 65)
    
    np.random.seed(42) # Deterministic reproducibility
    
    manifest = {}
    
    # -----------------------------------------------------------------
    # Test 1: Chirp Delay Benchmark
    # 3.5 -> 7.5 kHz sweep over 4s under pink noise (-20 dBFS)
    # -----------------------------------------------------------------
    duration_1 = 5.0
    t1 = np.linspace(0.0, duration_1, int(FS * duration_1), endpoint=False, dtype=np.float32)
    pink_1 = generate_pink_noise(len(t1), target_rms_db=-20.0)
    
    # Chirp runs between 0.5s and 4.5s
    chirp_signal = np.zeros_like(t1)
    chirp_mask = (t1 >= 0.5) & (t1 <= 4.5)
    t_chirp = t1[chirp_mask] - 0.5
    f_start, f_end = 3500.0, 7500.0
    chirp_dur = 4.0
    # Linear instantaneous frequency
    phase = 2.0 * np.pi * (f_start * t_chirp + 0.5 * (f_end - f_start) / chirp_dur * (t_chirp**2))
    chirp_amp = db_to_linear(-12.0) # -12 dBFS peak
    # Apply 20ms Tukey taper at start and end of chirp
    window = scipy.signal.windows.tukey(len(t_chirp), alpha=0.01)
    chirp_signal[chirp_mask] = chirp_amp * np.sin(phase) * window
    
    sig_1 = np.clip(pink_1 + chirp_signal, -1.0, 1.0)
    p1 = os.path.join(BENCH_DIR, "test_01_chirp_delay.wav")
    sf.write(p1, sig_1, FS, subtype="PCM_24")
    manifest["test_01_chirp_delay"] = {
        "file": "test_01_chirp_delay.wav",
        "duration_sec": duration_1,
        "f_start_hz": f_start,
        "f_end_hz": f_end,
        "chirp_window_sec": [0.5, 4.5],
        "pass_criterion": "Tracker f0_current lag <= 12 ms relative to f_true(t)"
    }
    print("  [OK] Generated test_01_chirp_delay.wav (5.0s)")
    
    # -----------------------------------------------------------------
    # Test 2: Suppression Depth
    # Tone 5.2 kHz at -12 dBFS under pink noise (-20 dBFS)
    # -----------------------------------------------------------------
    duration_2 = 4.0
    t2 = np.linspace(0.0, duration_2, int(FS * duration_2), endpoint=False, dtype=np.float32)
    pink_2 = generate_pink_noise(len(t2), target_rms_db=-20.0)
    tone_2 = db_to_linear(-12.0) * np.sin(2.0 * np.pi * 5200.0 * t2)
    sig_2 = np.clip(pink_2 + tone_2, -1.0, 1.0)
    p2 = os.path.join(BENCH_DIR, "test_02_suppression_depth.wav")
    sf.write(p2, sig_2, FS, subtype="PCM_24")
    manifest["test_02_suppression_depth"] = {
        "file": "test_02_suppression_depth.wav",
        "duration_sec": duration_2,
        "target_f0_hz": 5200.0,
        "target_level_dbfs": -12.0,
        "pass_criterion": "Gain attenuation stable at -6 dB to -10 dB in steady state"
    }
    print("  [OK] Generated test_02_suppression_depth.wav (4.0s)")
    
    # -----------------------------------------------------------------
    # Test 3: Click / THD+N Zipper Noise
    # Fast frequency modulation 4.0 <-> 6.5 kHz at 5 Hz rate
    # -----------------------------------------------------------------
    duration_3 = 4.0
    t3 = np.linspace(0.0, duration_3, int(FS * duration_3), endpoint=False, dtype=np.float32)
    f_center = 5250.0
    f_dev = 1250.0
    f_mod = 5.0
    instant_freq = f_center + f_dev * np.sin(2.0 * np.pi * f_mod * t3)
    phase_3 = 2.0 * np.pi * np.cumsum(instant_freq) / FS
    sig_3 = db_to_linear(-12.0) * np.sin(phase_3).astype(np.float32)
    p3 = os.path.join(BENCH_DIR, "test_03_click_thd.wav")
    sf.write(p3, sig_3, FS, subtype="PCM_24")
    manifest["test_03_click_thd"] = {
        "file": "test_03_click_thd.wav",
        "duration_sec": duration_3,
        "modulation_rate_hz": f_mod,
        "pass_criterion": "Zero high-frequency zipper noise spikes > 10 kHz in residual"
    }
    print("  [OK] Generated test_03_click_thd.wav (4.0s)")
    
    # -----------------------------------------------------------------
    # Test 4: Transparency & Gaps (Release Verification)
    # Alternating tone bursts and silent gaps under pink noise
    # -----------------------------------------------------------------
    duration_4 = 6.0
    t4 = np.linspace(0.0, duration_4, int(FS * duration_4), endpoint=False, dtype=np.float32)
    pink_4 = generate_pink_noise(len(t4), target_rms_db=-24.0)
    burst_signal = np.zeros_like(t4)
    # Burst 1: 1.0s to 2.0s @ 5500 Hz
    b1_mask = (t4 >= 1.0) & (t4 <= 2.0)
    burst_signal[b1_mask] = db_to_linear(-12.0) * np.sin(2.0 * np.pi * 5500.0 * t4[b1_mask])
    # Burst 2: 3.5s to 4.5s @ 6200 Hz
    b2_mask = (t4 >= 3.5) & (t4 <= 4.5)
    burst_signal[b2_mask] = db_to_linear(-12.0) * np.sin(2.0 * np.pi * 6200.0 * t4[b2_mask])
    sig_4 = np.clip(pink_4 + burst_signal, -1.0, 1.0)
    p4 = os.path.join(BENCH_DIR, "test_04_transparency_gaps.wav")
    sf.write(p4, sig_4, FS, subtype="PCM_24")
    manifest["test_04_transparency_gaps"] = {
        "file": "test_04_transparency_gaps.wav",
        "duration_sec": duration_4,
        "burst_intervals_sec": [[1.0, 2.0], [3.5, 4.5]],
        "pass_criterion": "Filter gain returns to 0.0 dB within 150 ms of burst termination"
    }
    print("  [OK] Generated test_04_transparency_gaps.wav (6.0s)")
    
    # -----------------------------------------------------------------
    # Test 5: Decoy Trap (Prominence vs Absolute Max)
    # Loud static 4.0 kHz tone (-10 dBFS) + moving anomaly 5.2 -> 6.8 kHz (-18 dBFS)
    # -----------------------------------------------------------------
    duration_5 = 5.0
    t5 = np.linspace(0.0, duration_5, int(FS * duration_5), endpoint=False, dtype=np.float32)
    pink_5 = generate_pink_noise(len(t5), target_rms_db=-24.0)
    # Static Decoy: loud 4.0 kHz tone (-10 dBFS)
    decoy_tone = db_to_linear(-10.0) * np.sin(2.0 * np.pi * 4000.0 * t5)
    # Moving Anomaly: swept tone 5200 -> 6800 Hz (-18 dBFS)
    chirp_5_mask = (t5 >= 0.5) & (t5 <= 4.5)
    t_c5 = t5[chirp_5_mask] - 0.5
    f5_start, f5_end = 5200.0, 6800.0
    phase_5 = 2.0 * np.pi * (f5_start * t_c5 + 0.5 * (f5_end - f5_start) / 4.0 * (t_c5**2))
    anomaly_tone = np.zeros_like(t5)
    anomaly_tone[chirp_5_mask] = db_to_linear(-18.0) * np.sin(phase_5)
    sig_5 = np.clip(pink_5 + decoy_tone + anomaly_tone, -1.0, 1.0)
    p5 = os.path.join(BENCH_DIR, "test_05_decoy_trap.wav")
    sf.write(p5, sig_5, FS, subtype="PCM_24")
    manifest["test_05_decoy_trap"] = {
        "file": "test_05_decoy_trap.wav",
        "duration_sec": duration_5,
        "decoy_hz": 4000.0,
        "anomaly_range_hz": [5200.0, 6800.0],
        "pass_criterion": "Prominence logic locks moving anomaly or handles both nodes without sticking"
    }
    print("  [OK] Generated test_05_decoy_trap.wav (5.0s)")
    
    # -----------------------------------------------------------------
    # Test 6: Step / Legato Transition
    # Instant jump 3.5 kHz -> 7.5 kHz at t = 1.5s
    # -----------------------------------------------------------------
    duration_6 = 4.0
    t6 = np.linspace(0.0, duration_6, int(FS * duration_6), endpoint=False, dtype=np.float32)
    step_mask_a = (t6 < 1.5)
    step_mask_b = (t6 >= 1.5)
    phase_6 = np.zeros_like(t6)
    # Continuous phase across jump
    phase_6[step_mask_a] = 2.0 * np.pi * 3500.0 * t6[step_mask_a]
    phase_at_jump = 2.0 * np.pi * 3500.0 * 1.5
    phase_6[step_mask_b] = phase_at_jump + 2.0 * np.pi * 7500.0 * (t6[step_mask_b] - 1.5)
    sig_6 = db_to_linear(-12.0) * np.sin(phase_6).astype(np.float32)
    p6 = os.path.join(BENCH_DIR, "test_06_step_legato.wav")
    sf.write(p6, sig_6, FS, subtype="PCM_24")
    manifest["test_06_step_legato"] = {
        "file": "test_06_step_legato.wav",
        "duration_sec": duration_6,
        "step_time_sec": 1.5,
        "step_f0_jump": [3500.0, 7500.0],
        "pass_criterion": "Capture time < 25 ms, no transient click artifact during capture"
    }
    print("  [OK] Generated test_06_step_legato.wav (4.0s)")
    
    # -----------------------------------------------------------------
    # Test 7: Null / False-Positive Benchmark
    # Clean natural signal without narrow resonances (pink noise + wide harmonics)
    # -----------------------------------------------------------------
    duration_7 = 4.0
    t7 = np.linspace(0.0, duration_7, int(FS * duration_7), endpoint=False, dtype=np.float32)
    pink_7 = generate_pink_noise(len(t7), target_rms_db=-18.0)
    # Add gentle wide chord (warm pad: 220 Hz, 330 Hz, 440 Hz, 550 Hz, 660 Hz with soft decay)
    chord = np.zeros_like(t7)
    for harmonic_idx, freq in enumerate([220.0, 330.0, 440.0, 550.0, 660.0]):
        amp = db_to_linear(-24.0 - harmonic_idx * 2.0)
        chord += amp * np.sin(2.0 * np.pi * freq * t7)
    sig_7 = np.clip(pink_7 + chord, -1.0, 1.0)
    p7 = os.path.join(BENCH_DIR, "test_07_null_clean.wav")
    sf.write(p7, sig_7, FS, subtype="PCM_24")
    manifest["test_07_null_clean"] = {
        "file": "test_07_null_clean.wav",
        "duration_sec": duration_7,
        "pass_criterion": "Zero false triggers: Gain stays 0.0 dB throughout; Null residual < -60 dBFS"
    }
    print("  [OK] Generated test_07_null_clean.wav (4.0s)")
    
    # Write manifest JSON
    manifest_path = os.path.join(BENCH_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[SUCCESS] All 7 test signals generated and cataloged in:\n{manifest_path}")

if __name__ == "__main__":
    main()
