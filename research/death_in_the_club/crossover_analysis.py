"""
PHARMAKON Research Task 04: Death in the Club
Module: crossover_analysis.py

Phase 4: Comprehensive mathematical and numerical investigation of the legacy
100 Hz Linkwitz-Riley (LR4 via filtfilt) crossover failure.
"""

import numpy as np
import scipy.signal as signal
from typing import Dict, Any, List

SAMPLE_RATE = 48000
CROSSOVER_FREQ = 100.0


def analyze_crossover(sr: int = SAMPLE_RATE, fc: float = CROSSOVER_FREQ) -> Dict[str, Any]:
    """
    Computes exact frequency response and recombination characteristics of
    the 2nd-order Butterworth low-pass and high-pass filters implemented in
    remaster_engine.align_sub_phase (which use signal.filtfilt, producing
    an effective zero-phase 4th-order Linkwitz-Riley LR4 response).

    Evaluates:
    1. Low-pass magnitude squared |H_LP(f)|^2 and high-pass |H_HP(f)|^2.
    2. Unmodified sum |H_LP|^2 + |H_HP|^2 (verifies unity reconstruction).
    3. Recombination with polarity inversion (-H_LP_sq + H_HP_sq).
    4. Recombination with various sub-band delays (0.5 ms to 6.0 ms).
    5. Exact notch depths and crossover band (85-120 Hz) energy losses.
    """
    nyq = 0.5 * sr
    f_cross = min(fc, nyq - 20.0) / nyq
    b_low, a_low = signal.butter(2, f_cross, btype="low")
    b_hi, a_hi = signal.butter(2, f_cross, btype="high")

    # Evaluate frequency response over dense grid 20 Hz to 500 Hz
    freqs = np.linspace(20.0, 500.0, 2400)
    w = 2.0 * np.pi * freqs / sr

    _, h_low = signal.freqz(b_low, a_low, worN=freqs, fs=sr)
    _, h_hi = signal.freqz(b_hi, a_hi, worN=freqs, fs=sr)

    # filtfilt produces squared magnitude with zero phase
    h_low_sq = np.abs(h_low) ** 2
    h_hi_sq = np.abs(h_hi) ** 2

    # 1. Unmodified Recombination
    h_unmodified = h_low_sq + h_hi_sq
    max_dev_unmodified = float(np.max(np.abs(h_unmodified - 1.0)))

    # 2. Polarity Inversion (-1.0 on sub-band)
    h_polarity_inv = -h_low_sq + h_hi_sq
    mag_polarity_inv = np.abs(h_polarity_inv)
    idx_fc = int(np.argmin(np.abs(freqs - fc)))
    notch_depth_inv_db = float(20.0 * np.log10(max(1e-12, mag_polarity_inv[idx_fc])))

    # 3. Delay sweep from 0 to 6 ms
    delays_ms = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.2, 4.5, 5.0, 5.5, 6.0]
    delay_results: List[Dict[str, Any]] = []

    crossover_band_mask = (freqs >= 85.0) & (freqs <= 120.0)

    for d_ms in delays_ms:
        tau_sec = d_ms * 1e-3
        # Sub-band delayed by tau: exp(-j * 2 * pi * f * tau)
        phase_sub = -2.0 * np.pi * freqs * tau_sec
        h_delay_recomb = h_low_sq * np.exp(1j * phase_sub) + h_hi_sq
        mag_delay = np.abs(h_delay_recomb)
        mag_delay_db = 20.0 * np.log10(np.maximum(1e-12, mag_delay))

        fc_db = float(mag_delay_db[idx_fc])
        min_band_db = float(np.min(mag_delay_db[crossover_band_mask]))
        avg_band_db = float(np.mean(mag_delay_db[crossover_band_mask]))

        delay_results.append({
            "delay_ms": d_ms,
            "response_at_100hz_db": fc_db,
            "worst_notch_85_120hz_db": min_band_db,
            "mean_deviation_85_120hz_db": avg_band_db,
            "phase_at_100hz_deg": float(np.angle(h_delay_recomb[idx_fc], deg=True)),
        })

    results = {
        "sr": sr,
        "fc_hz": fc,
        "max_unity_deviation": max_dev_unmodified,
        "unity_reconstruction_verified": bool(max_dev_unmodified < 1e-10),
        "polarity_inversion_notch_100hz_db": notch_depth_inv_db,
        "delay_sweep": delay_results,
        "freqs": freqs.tolist(),
        "h_low_sq": h_low_sq.tolist(),
        "h_hi_sq": h_hi_sq.tolist(),
        "h_unmodified": h_unmodified.tolist(),
        "h_polarity_inv_mag": mag_polarity_inv.tolist(),
    }
    return results


if __name__ == "__main__":
    res = analyze_crossover()
    print("=== CROSSOVER ANALYSIS ===")
    print(f"Unity reconstruction max error: {res['max_unity_deviation']:.2e}")
    print(f"Polarity inversion notch at 100 Hz: {res['polarity_inversion_notch_100hz_db']:.2f} dB")
    print("\nDelay Sweep:")
    print("Delay (ms) | 100 Hz (dB) | Worst in 85-120 Hz (dB)")
    for d in res["delay_sweep"]:
        print(f"{d['delay_ms']:10.1f} | {d['response_at_100hz_db']:11.2f} | {d['worst_notch_85_120hz_db']:21.2f}")
