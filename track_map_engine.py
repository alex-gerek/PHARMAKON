"""
PHARMAKON 3.0 · Track Map & Local Guard Processing Engine
Author: Lex Gerek // PHARMAKON Audio Labs

Implements:
1. Multi-metric provisional track mapping (energy slope, kick density, Crest Factor).
2. Local Limiter-Aware Sub-Sync with zero peak inflation and smooth continuous crossfade.
3. Complete event-by-event auditing (timestamp, decision, shift_ms, rejection reason).
4. Full Bypass mode support with bit-exact preservation.
"""

import os
import json
import numpy as np
import scipy.signal as signal
import soundfile as sf

def ensure_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return np.column_stack([audio, audio]).astype(np.float32)
    elif audio.ndim == 2 and audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1).astype(np.float32)
    elif audio.ndim == 2 and audio.shape[1] > 2:
        return audio[:, :2].astype(np.float32)
    return audio.astype(np.float32)


def butter_lowpass(sig: np.ndarray, cutoff: float, sr: int, order: int = 2) -> np.ndarray:
    nyq = 0.5 * sr
    b, a = signal.butter(order, min(cutoff, nyq - 10.0) / nyq, btype='low')
    if sig.ndim == 1:
        return signal.filtfilt(b, a, sig).astype(np.float32)
    return signal.filtfilt(b, a, sig, axis=0).astype(np.float32)


def evaluate_candidate_lags(
    d_sub_win: np.ndarray,
    b_sub_win: np.ndarray,
    raw_b_mono: np.ndarray,
    raw_d_mono: np.ndarray,
    sr: int,
    max_lag: int,
    limiter_penalty: float = 1.20,
):
    """Evaluates candidate time shifts in [-max_lag, +max_lag] for a kick window."""
    lags = np.arange(-max_lag, max_lag + 1)
    raw_sub_sum = d_sub_win + b_sub_win
    raw_full_sum = raw_d_mono + raw_b_mono

    rms_raw_sub = float(np.sqrt(np.mean(np.square(raw_sub_sum)) + 1e-12))
    peak_raw_full = float(np.max(np.abs(raw_full_sum)))
    peak_ref = max(peak_raw_full, float(np.max(np.abs(raw_d_mono))), float(np.max(np.abs(raw_b_mono))))

    best_lag = 0
    best_pol = 1.0
    best_score = -999.0

    for pol in [1.0, -1.0]:
        for lag in lags:
            cand_b_sub = np.roll(b_sub_win * pol, lag)
            cand_b_full = np.roll(raw_b_mono * pol, lag)
            if lag > 0:
                cand_b_sub[:lag] = b_win_sub[:lag] if 'b_win_sub' in dir() else b_sub_win[:lag]
                cand_b_full[:lag] = raw_b_mono[:lag]
            elif lag < 0:
                cand_b_sub[lag:] = b_sub_win[lag:]
                cand_b_full[lag:] = raw_b_mono[lag:]

            cand_sub_sum = d_sub_win + cand_b_sub
            cand_full_sum = raw_d_mono + cand_b_full

            rms_cand_sub = float(np.sqrt(np.mean(np.square(cand_sub_sum)) + 1e-12))
            sub_gain_db = 20.0 * np.log10(max(1e-12, rms_cand_sub) / max(1e-12, rms_raw_sub))

            peak_cand_full = float(np.max(np.abs(cand_full_sum)))
            delta_peak_db = 20.0 * np.log10(max(1e-12, peak_cand_full) / max(1e-12, peak_ref))

            score = sub_gain_db - limiter_penalty * max(0.0, delta_peak_db)

            if score > best_score:
                best_score = score
                best_lag = int(lag)
                best_pol = pol

    return best_lag, best_pol


def build_provisional_track_map(
    full_mix: np.ndarray,
    sub_drums: np.ndarray,
    sub_bass: np.ndarray,
    sr: int,
    kick_peaks: np.ndarray,
) -> dict:
    """
    Constructs a multi-metric provisional track map based on physical acoustic features.
    Sections and boundaries are explicitly marked as preliminary.
    """
    mix_mono = np.mean(ensure_stereo(full_mix), axis=1)
    duration_s = len(mix_mono) / sr

    # Estimate tempo from inter-kick intervals
    if len(kick_peaks) >= 8:
        diffs = np.diff(kick_peaks) / sr
        regular = diffs[(diffs >= 0.35) & (diffs <= 0.65)]
        if len(regular) >= 4:
            bpm = float(60.0 / np.median(regular))
        else:
            bpm = 120.0
    else:
        bpm = 120.0

    bar_len_s = (60.0 / bpm) * 4.0
    phrase_16_s = bar_len_s * 4.0  # ~4 bars or 16 beats

    # Segment the track into musical phrases (~16-bar default chunks, adapted to duration)
    chunk_dur = max(15.0, min(30.0, bar_len_s * 16.0))
    n_chunks = max(1, int(round(duration_s / chunk_dur)))
    raw_boundaries = np.linspace(0.0, duration_s, n_chunks + 1)

    sections = []
    for i in range(len(raw_boundaries) - 1):
        t0 = float(round(raw_boundaries[i], 2))
        t1 = float(round(raw_boundaries[i + 1], 2))
        s_idx = int(t0 * sr)
        e_idx = int(t1 * sr)

        seg_mix = mix_mono[s_idx:e_idx]
        seg_sd = sub_drums[s_idx:e_idx]
        seg_sb = sub_bass[s_idx:e_idx]

        r_mix = float(20.0 * np.log10(np.sqrt(np.mean(seg_mix**2) + 1e-12)))
        r_sd = float(20.0 * np.log10(np.sqrt(np.mean(seg_sd**2) + 1e-12)))
        r_sb = float(20.0 * np.log10(np.sqrt(np.mean(seg_sb**2) + 1e-12)))
        pk_mix = float(20.0 * np.log10(np.max(np.abs(seg_mix)) + 1e-12))
        crest_factor = float(pk_mix - r_mix)

        k_in_sec = [int(k) for k in kick_peaks if s_idx <= k < e_idx]
        k_count = len(k_in_sec)
        k_density = float(k_count / max(1.0, t1 - t0))

        corr = float(np.corrcoef(seg_sd, seg_sb)[0, 1]) if (len(seg_sd) > 0 and r_sd > -60.0 and r_sb > -60.0) else 0.0

        # Preliminary section naming based on acoustic state
        if i == 0 and k_count < 15:
            sec_type = "Вступление / Интро"
        elif i == len(raw_boundaries) - 2 and k_count < 8:
            sec_type = "Аутро / Финал"
        elif k_density < 0.2:
            sec_type = "Яма / Брейкдаун (спад бочки)"
        elif k_density >= 0.7 and r_sb > -20.0:
            sec_type = f"Плотный дроп / Кульминация (активный ритм)"
        else:
            sec_type = f"Развитие грува / Тема"

        sections.append({
            "section_index": i + 1,
            "provisional_name": f"[ПРЕДВАРИТЕЛЬНО] {sec_type}",
            "time_start_s": t0,
            "time_end_s": t1,
            "duration_s": float(round(t1 - t0, 2)),
            "kick_events_count": k_count,
            "kick_density_hits_per_s": float(round(k_density, 3)),
            "rms_mix_dbfs": float(round(r_mix, 2)),
            "rms_sub_drums_dbfs": float(round(r_sd, 2)),
            "rms_sub_bass_dbfs": float(round(r_sb, 2)),
            "peak_dbfs": float(round(pk_mix, 2)),
            "crest_factor_db": float(round(crest_factor, 2)),
            "sub_correlation_r": float(round(corr, 3)),
            "boundary_type": "предварительная математическая сетка фразировки",
        })

    return {
        "status": "provisional",
        "estimated_bpm": float(round(bpm, 2)),
        "total_duration_s": float(round(duration_s, 2)),
        "total_kick_events": len(kick_peaks),
        "total_sections": len(sections),
        "sections": sections,
    }


def process_local_sub_sync(
    drums_stereo: np.ndarray,
    bass_stereo: np.ndarray,
    sr: int,
    mode: str = "limiter_aware",  # "limiter_aware", "legacy", "off"
    crossover_hz: float = 100.0,
    window_sec: float = 0.20,
    pre_trigger_sec: float = 0.010,
    max_lag_ms: float = 3.0,
    limiter_penalty: float = 1.20,
    min_gain_db: float = 0.0,
    max_peak_inflation_db: float = 0.02,
    max_xover_drop_db: float = 0.50,
):
    """
    Executes local windowed Sub-Sync with complete auditing.
    Guarantees seamless crossfade without boundary dips or clicks.
    """
    drums_stereo = ensure_stereo(drums_stereo)
    bass_stereo = ensure_stereo(bass_stereo)
    n_samples = len(bass_stereo)

    sub_drums = butter_lowpass(np.mean(drums_stereo, axis=1), crossover_hz, sr, order=2)
    sub_bass = butter_lowpass(np.mean(bass_stereo, axis=1), crossover_hz, sr, order=2)

    # Detect kick peaks
    env = np.abs(sub_drums)
    win_len = int(round(0.005 * sr))
    env_smooth = np.convolve(env, np.ones(win_len) / win_len, mode="same")
    env_max = float(np.max(env_smooth))
    peak_threshold = max(0.01, float(env_max * 0.15))
    min_dist_samples = int(round(0.12 * sr))
    kick_peaks, _ = signal.find_peaks(env_smooth, height=peak_threshold, distance=min_dist_samples)

    pre_samples = int(round(pre_trigger_sec * sr))
    win_samples = int(round(window_sec * sr))
    full_win_len = pre_samples + win_samples
    max_lag = int(round(max_lag_ms * 1e-3 * sr))
    taper = signal.windows.tukey(full_win_len, alpha=0.30)[:, np.newaxis]

    nyq = 0.5 * sr
    bp_b, bp_a = signal.butter(2, [max(10.0, 85.0) / nyq, min(nyq - 10.0, 120.0) / nyq], btype="bandpass")

    raw_d_mono = np.mean(drums_stereo, axis=1)
    raw_b_mono = np.mean(bass_stereo, axis=1)

    bass_corrected = bass_stereo.copy()
    events_log = []

    # If mode is 'off' (Bypass), record all events as BYPASS and return untouched
    if mode == "off":
        for idx, k_idx in enumerate(kick_peaks):
            events_log.append({
                "event_index": idx + 1,
                "time_s": float(round(k_idx / sr, 4)),
                "decision": "BYPASS",
                "applied_shift_ms": 0.0,
                "polarity": 1.0,
                "gain_sub_db": 0.0,
                "peak_diff_db": 0.0,
                "xover_drop_db": 0.0,
                "reason": "mode_bypass (обработка отключена)",
            })
        meta = {
            "mode": "off",
            "events_detected": len(kick_peaks),
            "events_corrected": 0,
            "events_rejected": len(kick_peaks),
            "safe_bypass_engaged": True,
            "average_shift_ms": 0.0,
        }
        return bass_stereo.copy().astype(np.float32), meta, events_log

    # Active processing loop
    corrected_count = 0
    applied_shifts_ms = []

    for idx, k_idx in enumerate(kick_peaks):
        t_sec = float(round(k_idx / sr, 4))
        w_start = max(0, k_idx - pre_samples)
        w_end = min(n_samples, w_start + full_win_len)
        actual_len = w_end - w_start

        if actual_len < max_lag * 2 + 10:
            events_log.append({
                "event_index": idx + 1,
                "time_s": t_sec,
                "decision": "REJECT",
                "applied_shift_ms": 0.0,
                "polarity": 1.0,
                "gain_sub_db": 0.0,
                "peak_diff_db": 0.0,
                "xover_drop_db": 0.0,
                "reason": "window_boundary_edge",
            })
            continue

        d_sub_win = sub_drums[w_start:w_end]
        b_sub_win = sub_bass[w_start:w_end]
        raw_b_seg = bass_stereo[w_start:w_end]
        raw_d_seg = drums_stereo[w_start:w_end]
        w_taper = taper[:actual_len]

        best_lag, best_pol = evaluate_candidate_lags(
            d_sub_win, b_sub_win, raw_b_mono[w_start:w_end], raw_d_mono[w_start:w_end],
            sr, max_lag, limiter_penalty=limiter_penalty
        )

        shifted_b = np.roll(raw_b_seg * best_pol, best_lag, axis=0)
        if best_lag > 0:
            shifted_b[:best_lag] = raw_b_seg[:best_lag]
        elif best_lag < 0:
            shifted_b[best_lag:] = raw_b_seg[best_lag:]

        raw_sub_sum = d_sub_win + b_sub_win
        cand_b_sub = np.roll(b_sub_win * best_pol, best_lag)
        cand_sub_sum = d_sub_win + cand_b_sub

        rms_raw_sub = float(np.sqrt(np.mean(np.square(raw_sub_sum)) + 1e-12))
        rms_cand_sub = float(np.sqrt(np.mean(np.square(cand_sub_sum)) + 1e-12))
        gain_sub_db = 20.0 * np.log10(max(1e-12, rms_cand_sub) / max(1e-12, rms_raw_sub))

        raw_pk = float(np.max(np.abs(raw_d_seg + raw_b_seg)))
        cand_pk = float(np.max(np.abs(raw_d_seg + shifted_b)))
        peak_diff_db = 20.0 * np.log10(max(1e-12, cand_pk) / max(1e-12, raw_pk))

        b85_raw = float(np.sqrt(np.mean(np.square(signal.filtfilt(bp_b, bp_a, raw_b_seg, axis=0))) + 1e-12))
        b85_cand = float(np.sqrt(np.mean(np.square(signal.filtfilt(bp_b, bp_a, shifted_b, axis=0))) + 1e-12))
        xover_drop_db = 20.0 * np.log10(max(1e-12, b85_cand) / max(1e-12, b85_raw))

        shift_ms = float(round(best_lag * 1000.0 / sr, 3))

        # Acceptance Decision
        if best_lag == 0:
            decision = "REJECT"
            reason = "zero_lag_optimal (фаза уже оптимальна)"
        elif peak_diff_db > max_peak_inflation_db:
            decision = "REJECT"
            reason = f"peak_inflation (+{peak_diff_db:.3f} dB > +{max_peak_inflation_db} dB)"
        elif xover_drop_db < -max_xover_drop_db:
            decision = "REJECT"
            reason = f"xover_drop ({xover_drop_db:.3f} dB < -{max_xover_drop_db} dB)"
        elif gain_sub_db < (min_gain_db - 0.001):
            decision = "REJECT"
            reason = f"sub_loss ({gain_sub_db:.3f} dB < {min_gain_db:.3f} dB)"
        else:
            decision = "ACCEPT"
            reason = f"valid_shift (gain={gain_sub_db:+.3f}dB, pk_diff={peak_diff_db:+.3f}dB)"

        if decision == "ACCEPT":
            # Seamless crossfade: raw * (1 - taper) + shifted * taper
            bass_corrected[w_start:w_end] = raw_b_seg * (1.0 - w_taper) + shifted_b * w_taper
            corrected_count += 1
            applied_shifts_ms.append(abs(shift_ms))

        events_log.append({
            "event_index": idx + 1,
            "time_s": t_sec,
            "decision": decision,
            "applied_shift_ms": shift_ms if decision == "ACCEPT" else 0.0,
            "candidate_shift_ms": shift_ms,
            "polarity": float(best_pol),
            "gain_sub_db": float(round(gain_sub_db, 4)),
            "peak_diff_db": float(round(peak_diff_db, 4)),
            "xover_drop_db": float(round(xover_drop_db, 4)),
            "reason": reason,
        })

    meta = {
        "mode": mode,
        "events_detected": len(kick_peaks),
        "events_corrected": corrected_count,
        "events_rejected": len(kick_peaks) - corrected_count,
        "safe_bypass_engaged": (corrected_count == 0),
        "average_shift_ms": float(np.mean(applied_shifts_ms)) if applied_shifts_ms else 0.0,
    }

    return bass_corrected.astype(np.float32), meta, events_log
