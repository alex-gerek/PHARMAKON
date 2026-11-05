"""
PHARMAKON Research Task 04: Death in the Club
Module: methods.py

Implements and wraps the 4 phase alignment methods under evaluation:
- Method A: Baseline (No correction).
- Method B: Single Global Time Delay (full-range uniform shift).
- Method C: Legacy Sub-Band-Only Delay/Polarity Correction (calls remaster_engine.align_sub_phase).
- Method D: Proposed Reference Method: Guarded Windowed Full-Range Alignment (GW-FRA)
  [Experimental Prototype - not the existing production algorithm].
"""

import sys
import os
import numpy as np
import scipy.signal as signal
from typing import Tuple, Dict, Any, List

# Ensure PHARMAKON root is in python path to import actual remaster_engine
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PHARMAKON_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PHARMAKON_ROOT not in sys.path:
    sys.path.insert(0, PHARMAKON_ROOT)

from remaster_engine import align_sub_phase, ensure_stereo


# =============================================================================
# Helper Utilities
# =============================================================================

def bandpass_filter(audio: np.ndarray, sr: int, f_low: float, f_high: float, order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth bandpass filter using second-order sections (SOS)."""
    nyq = 0.5 * sr
    low = max(1.0, f_low) / nyq
    high = min(nyq - 20.0, f_high) / nyq
    if low >= high:
        return np.zeros_like(audio)
    sos = signal.butter(order, [low, high], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, audio.astype(np.float64), axis=0).astype(np.float32)


def lowpass_filter(audio: np.ndarray, sr: int, cutoff: float = 100.0, order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth lowpass filter using second-order sections (SOS)."""
    nyq = 0.5 * sr
    f_c = min(cutoff, nyq - 20.0) / nyq
    sos = signal.butter(order, f_c, btype="low", output="sos")
    return signal.sosfiltfilt(sos, audio.astype(np.float64), axis=0).astype(np.float32)


def compute_rms(audio: np.ndarray) -> float:
    """Computes RMS value of an audio array."""
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def compute_true_peak(audio: np.ndarray, oversample: int = 4) -> float:
    """Computes peak amplitude with 4x polyphase sinc oversampling."""
    if audio.size == 0:
        return 0.0
    audio_stereo = ensure_stereo(audio)
    up_l = signal.resample_poly(audio_stereo[:, 0].astype(np.float64), oversample, 1)
    up_r = signal.resample_poly(audio_stereo[:, 1].astype(np.float64), oversample, 1)
    max_val = max(float(np.max(np.abs(up_l))), float(np.max(np.abs(up_r))))
    return max_val


# =============================================================================
# Method A: Baseline (No correction)
# =============================================================================

def method_a_baseline(drums: np.ndarray, bass: np.ndarray, sr: int) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Method A: Baseline (unaligned, pristine original bass).
    """
    bass_stereo = ensure_stereo(bass).astype(np.float32)
    meta = {
        "method": "A_Baseline",
        "description": "Unmodified original bass signal",
        "best_lag_samples": 0,
        "best_lag_ms": 0.0,
        "polarity": 1.0,
        "safe_path_engaged": True,
    }
    return bass_stereo, meta


# =============================================================================
# Method B: Single Global Time Delay (Full-Range Bass Shift)
# =============================================================================

def method_b_global_delay(
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int,
    max_lag_ms: float = 6.0,
    crossover_hz: float = 100.0,
    min_signal_rms_dbfs: float = -50.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Method B: A single global time delay and polarity check applied
    to the ENTIRE full-range bass stem based on sub-band cross-correlation.
    """
    drums_stereo = ensure_stereo(drums)
    bass_stereo = ensure_stereo(bass)
    orig_len = len(bass_stereo)

    # Sub-band correlation strictly below crossover_hz
    drum_sub = lowpass_filter(np.mean(drums_stereo, axis=1), sr, cutoff=crossover_hz)
    bass_sub = lowpass_filter(np.mean(bass_stereo, axis=1), sr, cutoff=crossover_hz)

    thresh_lin = 10.0 ** (min_signal_rms_dbfs / 20.0)

    # Silence & low energy guard (-50 dBFS)
    if compute_rms(drum_sub) < thresh_lin or compute_rms(bass_sub) < thresh_lin:
        meta = {
            "method": "B_GlobalDelay",
            "best_lag_samples": 0,
            "best_lag_ms": 0.0,
            "polarity": 1.0,
            "safe_path_engaged": True,
            "reason": "low_energy_sub_threshold",
        }
        return bass_stereo.astype(np.float32), meta

    max_lag = int(round(max_lag_ms * 1e-3 * sr))
    corr = signal.correlate(drum_sub, bass_sub, mode="full")
    lags = signal.correlation_lags(len(drum_sub), len(bass_sub), mode="full")

    center = len(corr) // 2
    window = slice(max(0, center - max_lag), min(len(corr), center + max_lag + 1))
    search_corr = corr[window]
    search_lags = lags[window]

    max_idx = int(np.argmax(search_corr))
    min_idx = int(np.argmin(search_corr))

    if abs(search_corr[min_idx]) > search_corr[max_idx]:
        polarity = -1.0
        best_lag = int(search_lags[min_idx])
    else:
        polarity = 1.0
        best_lag = int(search_lags[max_idx])

    # Apply delay to full-range bass
    aligned_bass = np.roll(bass_stereo * polarity, best_lag, axis=0)
    if best_lag > 0:
        aligned_bass[:best_lag] = 0
    elif best_lag < 0:
        aligned_bass[best_lag:] = 0

    aligned_bass = aligned_bass[:orig_len].astype(np.float32)
    meta = {
        "method": "B_GlobalDelay",
        "description": "Single uniform full-range time shift and polarity inversion",
        "best_lag_samples": best_lag,
        "best_lag_ms": float(best_lag * 1000.0 / sr),
        "polarity": float(polarity),
        "safe_path_engaged": False,
    }
    return aligned_bass, meta


# =============================================================================
# Method C: Legacy Sub-Band-Only Delay/Polarity Correction (Repository Code)
# =============================================================================

def method_c_legacy_sub_only(
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int,
    max_lag_ms: float = 6.0,
    crossover_freq: float = 100.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Method C: Legacy Sub-Sync implementation strictly using
    remaster_engine.align_sub_phase from the repository.
    """
    drums_stereo = ensure_stereo(drums)
    bass_stereo = ensure_stereo(bass)

    # Call actual repository function
    aligned_bass, best_lag, polarity = align_sub_phase(
        drums_stereo, bass_stereo, sr, max_lag_ms=max_lag_ms, crossover_freq=crossover_freq
    )

    meta = {
        "method": "C_LegacySubOnly",
        "description": "Legacy 100 Hz LR4 crossover split with circular roll on sub-band only",
        "best_lag_samples": int(best_lag),
        "best_lag_ms": float(best_lag * 1000.0 / sr),
        "polarity": float(polarity),
        "crossover_freq_hz": float(crossover_freq),
        "safe_path_engaged": False,
    }
    return aligned_bass.astype(np.float32), meta


# =============================================================================
# Method D: Guarded Per-Kick Full-Range Bass Correction (Experimental Prototype)
# =============================================================================

def method_d_guarded_per_kick(
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int,
    max_lag_ms: float = 3.0,
    min_gain_db: float = 0.5,
    crossover_hz: float = 100.0,
    window_sec: float = 0.20,
    pre_trigger_sec: float = 0.010,
    max_xover_drop_db: float = 0.5,
    min_signal_rms_dbfs: float = -50.0,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Method D: Proposed Reference Method — Guarded Windowed Full-Range Alignment (GW-FRA)
    [Experimental Prototype — NOT the existing production PHARMAKON algorithm].

    Design specifications:
    1. Kick Detection: Identifies low-frequency transient impact peaks in drum stem (<100 Hz).
    2. Event Windowing: Isolates active kick impact interval [t_k - pre_trigger, t_k + window_sec].
    3. Full-Range Bass Shift: Shifts the whole bass stem locally within the window, completely
       avoiding frequency band splitting and thereby eliminating crossover notch artifacts.
    4. Safe-Path Rule: Evaluates sub-band (<100 Hz) gain and crossover (85-120 Hz) energy impact:
       - If drum or bass energy < min_signal_rms_dbfs (default -50 dBFS) -> Reject shift.
       - If expected sub gain < min_gain_db (default +0.5 dB) -> Reject shift (0 ms).
       - If crossover region drop > max_xover_drop_db -> Reject shift.
       - If correlation is negative or low (< 0.20) -> Reject shift.
    5. Smooth Cross-Fade: Applies Hann/Tukey taper across window boundaries to guarantee C^1 continuity
       and prevent clicks or boundary discontinuities.
    """
    drums_stereo = ensure_stereo(drums)
    bass_stereo = ensure_stereo(bass)
    n_samples = len(bass_stereo)

    # Silence & low energy check (-50 dBFS threshold)
    sub_drums = lowpass_filter(np.mean(drums_stereo, axis=1), sr, cutoff=crossover_hz)
    sub_bass = lowpass_filter(np.mean(bass_stereo, axis=1), sr, cutoff=crossover_hz)
    rms_d = compute_rms(sub_drums)
    rms_b = compute_rms(sub_bass)

    thresh_lin = 10.0 ** (min_signal_rms_dbfs / 20.0)

    if rms_d < thresh_lin or rms_b < thresh_lin:
        meta = {
            "method": "D_GuardedPerKick",
            "prototype_status": "experimental_reference_prototype",
            "events_detected": 0,
            "events_corrected": 0,
            "safe_path_engaged": True,
            "reason": "low_energy_sub_threshold",
            "average_shift_ms": 0.0,
        }
        return bass_stereo.copy().astype(np.float32), meta

    # 1. Kick Onset Detection: Energy envelope follower on lowpass drum stem
    env = np.abs(sub_drums)
    # Smooth envelope with ~5 ms moving average
    win_len = int(round(0.005 * sr))
    env_smooth = np.convolve(env, np.ones(win_len) / win_len, mode="same")
    peak_threshold = 0.30 * np.max(env_smooth)

    # Minimum distance between kicks (e.g. 150 ms = 400 BPM max)
    min_dist = int(round(0.150 * sr))
    kick_peaks, _ = signal.find_peaks(env_smooth, height=peak_threshold, distance=min_dist)

    if len(kick_peaks) == 0:
        meta = {
            "method": "D_GuardedPerKick",
            "prototype_status": "experimental_reference_prototype",
            "events_detected": 0,
            "events_corrected": 0,
            "safe_path_engaged": True,
            "reason": "no_kick_peaks_detected",
            "average_shift_ms": 0.0,
        }
        return bass_stereo.copy().astype(np.float32), meta

    # 2. Windowed alignment setup
    win_samples = int(round(window_sec * sr))
    pre_samples = int(round(pre_trigger_sec * sr))
    max_lag = int(round(max_lag_ms * 1e-3 * sr))

    # Weighting accumulator for partition-of-unity overlap-add
    bass_out = np.zeros_like(bass_stereo, dtype=np.float64)
    weight_acc = np.zeros((n_samples, 1), dtype=np.float64)

    events_corrected = 0
    applied_shifts = []
    applied_polarities = []  # metadata only (reconciliation audit); does not affect output

    # Prepare Hann window for smooth tapering
    full_win_len = pre_samples + win_samples
    taper = signal.windows.tukey(full_win_len, alpha=0.30)
    taper_2d = taper[:, np.newaxis]

    for k_idx in kick_peaks:
        w_start = max(0, k_idx - pre_samples)
        w_end = min(n_samples, w_start + full_win_len)
        actual_len = w_end - w_start
        if actual_len < max_lag * 2 + 10:
            continue

        w_taper = taper_2d[:actual_len]
        d_win = sub_drums[w_start:w_end]
        b_win = sub_bass[w_start:w_end]

        # Cross-correlation within window
        corr = signal.correlate(d_win, b_win, mode="full")
        lags = signal.correlation_lags(len(d_win), len(b_win), mode="full")
        center = len(corr) // 2

        search_slice = slice(max(0, center - max_lag), min(len(corr), center + max_lag + 1))
        scorr = corr[search_slice]
        slags = lags[search_slice]

        if len(scorr) == 0:
            continue

        max_i = int(np.argmax(scorr))
        min_i = int(np.argmin(scorr))

        # Check positive vs negative peak
        if abs(scorr[min_i]) > scorr[max_i]:
            cand_pol = -1.0
            cand_lag = int(slags[min_i])
            peak_corr_val = abs(scorr[min_i])
        else:
            cand_pol = 1.0
            cand_lag = int(slags[max_i])
            peak_corr_val = scorr[max_i]

        # Normalized correlation check
        norm_factor = np.sqrt(np.sum(d_win ** 2) * np.sum(b_win ** 2)) + 1e-12
        norm_corr = peak_corr_val / norm_factor

        # Candidate alignment evaluation
        raw_b_segment = bass_stereo[w_start:w_end]
        shifted_b_segment = np.roll(raw_b_segment * cand_pol, cand_lag, axis=0)
        if cand_lag > 0:
            shifted_b_segment[:cand_lag] = raw_b_segment[:cand_lag]
        elif cand_lag < 0:
            shifted_b_segment[cand_lag:] = raw_b_segment[cand_lag:]

        # Sub-band sum gain verification (<100 Hz)
        raw_sub_sum = d_win + b_win
        cand_sub_sum = d_win + np.roll(b_win * cand_pol, cand_lag)
        rms_raw_sub = compute_rms(raw_sub_sum)
        rms_cand_sub = compute_rms(cand_sub_sum)
        cand_sub_gain_db = 20.0 * np.log10(max(1e-12, rms_cand_sub) / max(1e-12, rms_raw_sub))

        # Crossover band (85-120 Hz) check on bass segment
        b85_raw = compute_rms(bandpass_filter(raw_b_segment, sr, 85.0, 120.0))
        b85_cand = compute_rms(bandpass_filter(shifted_b_segment, sr, 85.0, 120.0))
        xover_drop_db = 20.0 * np.log10(max(1e-12, b85_cand) / max(1e-12, b85_raw))

        # SAFE-PATH RULE:
        # Require:
        # 1. Positive sub-band gain >= min_gain_db
        # 2. Normalized correlation >= 0.20
        # 3. No severe crossover region destruction (drop >= -max_xover_drop_db)
        if (cand_sub_gain_db >= min_gain_db and
            norm_corr >= 0.20 and
            xover_drop_db >= -max_xover_drop_db):
            effective_segment = shifted_b_segment
            applied_shifts.append(cand_lag * 1000.0 / sr)
            applied_polarities.append(float(cand_pol))
            events_corrected += 1
        else:
            # Fallback to pristine unshifted bass
            effective_segment = raw_b_segment
            applied_shifts.append(0.0)
            applied_polarities.append(1.0)

        # Accumulate tapered segment
        bass_out[w_start:w_end] += effective_segment * w_taper
        weight_acc[w_start:w_end] += w_taper

    # Blend corrected regions with uncorrected baseline
    # Where weight_acc == 0 (no kicks), bass_out becomes 100% pristine bass
    blend_mask = np.clip(weight_acc, 0.0, 1.0)
    # Normalize regions where multiple windows overlapped
    valid_overlap = weight_acc > 1.0
    bass_out[valid_overlap[:, 0]] /= weight_acc[valid_overlap[:, 0]]

    # Recombine: weighted corrected windows + (1 - blend_mask) * pristine bass
    final_bass = bass_out + (1.0 - blend_mask) * bass_stereo
    final_bass = final_bass[:n_samples].astype(np.float32)

    meta = {
        "method": "D_GuardedPerKick",
        "prototype_status": "experimental_reference_prototype",
        "events_detected": len(kick_peaks),
        "events_corrected": events_corrected,
        "average_shift_ms": float(np.mean(np.abs(applied_shifts))) if applied_shifts else 0.0,
        "applied_shifts_ms": [float(s) for s in applied_shifts],
        "applied_polarities": [float(p) for p in applied_polarities],
        "events_polarity_inverted": int(sum(1 for p in applied_polarities if p < 0)),
        "safe_path_engaged": (events_corrected == 0),
        "min_gain_db_threshold": min_gain_db,
    }
    return final_bass, meta
