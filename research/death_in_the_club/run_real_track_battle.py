"""
PHARMAKON Research: Limiter-Aware Alignment Battle on Real Track
Testing Candidate 1 (Virtual Micro-Limiter), Candidate 2 (Crest Factor), and Candidate 3 (All-Pass Phase)
against Baseline and Current Method D (GW-FRA).
Track: "I die of thirst" (Я умираю от жажды)
"""

import os
import sys
import numpy as np
import scipy.signal as signal
import soundfile as sf

# Path setup
PHARMAKON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PHARMAKON_ROOT not in sys.path:
    sys.path.insert(0, PHARMAKON_ROOT)

from research.death_in_the_club.methods import (
    bandpass_filter,
    lowpass_filter,
    compute_rms,
    compute_true_peak,
    method_d_guarded_per_kick,
    ensure_stereo,
)

STEMS_DIR = os.path.join(PHARMAKON_ROOT, "uploads", "I die of thirst_Stems")
OUT_DIR = os.path.join(os.path.dirname(__file__), "real_tracks_test")
os.makedirs(OUT_DIR, exist_ok=True)


def evaluate_window_candidates(
    d_win_sub: np.ndarray,
    b_win_sub: np.ndarray,
    raw_b_full: np.ndarray,
    raw_d_full: np.ndarray,
    sr: int,
    max_lag: int,
    mode: str = "method_d",  # "method_d", "micro_limiter", "crest_factor"
):
    """
    Evaluates candidate lags in the window according to the strategy:
    - method_d: peak cross-correlation
    - micro_limiter: maximizes (delta_sub_rms_db - max(0, delta_peak_db))
    - crest_factor: minimizes peak/rms while maintaining positive sub gain
    """
    lags = np.arange(-max_lag, max_lag + 1)
    raw_sub_sum = d_win_sub + b_win_sub
    raw_full_sum = raw_d_full + raw_b_full
    
    rms_raw_sub = compute_rms(raw_sub_sum)
    peak_raw_full = np.max(np.abs(raw_full_sum))
    crest_raw = peak_raw_full / (compute_rms(raw_full_sum) + 1e-12)

    best_lag = 0
    best_pol = 1.0
    best_score = -999.0

    if mode == "method_d":
        corr = signal.correlate(d_win_sub, b_win_sub, mode="full")
        corr_lags = signal.correlation_lags(len(d_win_sub), len(b_win_sub), mode="full")
        center = len(corr) // 2
        sl = slice(max(0, center - max_lag), min(len(corr), center + max_lag + 1))
        scorr = corr[sl]
        slags = corr_lags[sl]
        if len(scorr) > 0:
            max_i = int(np.argmax(scorr))
            min_i = int(np.argmin(scorr))
            if abs(scorr[min_i]) > scorr[max_i]:
                return int(slags[min_i]), -1.0
            else:
                return int(slags[max_i]), 1.0
        return 0, 1.0

    # Grid search across lags for Candidate 1 & Candidate 2
    for pol in [1.0, -1.0]:
        for lag in lags:
            cand_b_sub = np.roll(b_win_sub * pol, lag)
            cand_b_full = np.roll(raw_b_full * pol, lag)
            if lag > 0:
                cand_b_sub[:lag] = b_win_sub[:lag]
                cand_b_full[:lag] = raw_b_full[:lag]
            elif lag < 0:
                cand_b_sub[lag:] = b_win_sub[lag:]
                cand_b_full[lag:] = raw_b_full[lag:]

            cand_sub_sum = d_win_sub + cand_b_sub
            cand_full_sum = raw_d_full + cand_b_full

            rms_cand_sub = compute_rms(cand_sub_sum)
            sub_gain_db = 20.0 * np.log10(max(1e-12, rms_cand_sub) / max(1e-12, rms_raw_sub))

            peak_cand_full = np.max(np.abs(cand_full_sum))
            delta_peak_db = 20.0 * np.log10(max(1e-12, peak_cand_full) / max(1e-12, peak_raw_full))

            if mode == "micro_limiter":
                # Score = Gain of sub minus penalty for peak inflation
                # If peak rises by +1.5 dB, limiter would push down by 1.5 dB, canceling gain!
                score = sub_gain_db - 1.2 * max(0.0, delta_peak_db)
            elif mode == "crest_factor":
                cand_crest = peak_cand_full / (compute_rms(cand_full_sum) + 1e-12)
                # We want lower crest factor (more compact wave) and positive sub gain
                score = (crest_raw - cand_crest) + (0.5 * sub_gain_db if sub_gain_db > 0 else -10.0)
            else:
                score = sub_gain_db

            if score > best_score:
                best_score = score
                best_lag = int(lag)
                best_pol = pol

    return best_lag, best_pol


def align_per_kick_custom(
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int,
    mode: str = "micro_limiter",  # "micro_limiter", "crest_factor"
    max_lag_ms: float = 3.0,
    window_sec: float = 0.20,
    pre_trigger_sec: float = 0.010,
    crossover_hz: float = 100.0,
) -> np.ndarray:
    """Windowed alignment with custom optimization metric."""
    drums_stereo = ensure_stereo(drums)
    bass_stereo = ensure_stereo(bass)
    n_samples = len(bass_stereo)

    sub_drums = lowpass_filter(np.mean(drums_stereo, axis=1), sr, cutoff=crossover_hz)
    sub_bass = lowpass_filter(np.mean(bass_stereo, axis=1), sr, cutoff=crossover_hz)

    # Detect kick events
    sub_drums_env = np.abs(sub_drums)
    kernel_len = int(round(0.005 * sr))
    env_smooth = np.convolve(sub_drums_env, np.ones(kernel_len) / kernel_len, mode="same")
    env_max = np.max(env_smooth)
    if env_max < 1e-6:
        return bass_stereo.copy()

    thresh = max(0.01, float(env_max * 0.15))
    min_dist_samples = int(round(0.12 * sr))
    kick_peaks, _ = signal.find_peaks(env_smooth, height=thresh, distance=min_dist_samples)

    if len(kick_peaks) == 0:
        return bass_stereo.copy()

    win_samples = int(round(window_sec * sr))
    pre_samples = int(round(pre_trigger_sec * sr))
    max_lag = int(round(max_lag_ms * 1e-3 * sr))

    bass_out = np.zeros_like(bass_stereo, dtype=np.float64)
    weight_acc = np.zeros((n_samples, 1), dtype=np.float64)

    full_win_len = pre_samples + win_samples
    taper = signal.windows.tukey(full_win_len, alpha=0.30)[:, np.newaxis]

    for k_idx in kick_peaks:
        w_start = max(0, k_idx - pre_samples)
        w_end = min(n_samples, w_start + full_win_len)
        actual_len = w_end - w_start
        if actual_len < max_lag * 2 + 10:
            continue

        w_taper = taper[:actual_len]
        d_sub_win = sub_drums[w_start:w_end]
        b_sub_win = sub_bass[w_start:w_end]
        raw_b_segment = bass_stereo[w_start:w_end]
        raw_d_segment = drums_stereo[w_start:w_end]

        best_lag, best_pol = evaluate_window_candidates(
            d_sub_win, b_sub_win, raw_b_segment, raw_d_segment, sr, max_lag, mode=mode
        )

        shifted_b = np.roll(raw_b_segment * best_pol, best_lag, axis=0)
        if best_lag > 0:
            shifted_b[:best_lag] = raw_b_segment[:best_lag]
        elif best_lag < 0:
            shifted_b[best_lag:] = raw_b_segment[best_lag:]

        # Safe path check
        raw_sub_sum = d_sub_win + b_sub_win
        cand_b_sub = np.roll(b_sub_win * best_pol, best_lag)
        cand_sub_sum = d_sub_win + cand_b_sub
        rms_raw = compute_rms(raw_sub_sum)
        rms_cand = compute_rms(cand_sub_sum)
        gain_db = 20.0 * np.log10(max(1e-12, rms_cand) / max(1e-12, rms_raw))

        # Peak check on full window sum
        raw_peak = np.max(np.abs(raw_d_segment + raw_b_segment))
        cand_peak = np.max(np.abs(raw_d_segment + shifted_b))
        peak_diff_db = 20.0 * np.log10(max(1e-12, cand_peak) / max(1e-12, raw_peak))

        # Crossover integrity check
        b85_raw = compute_rms(bandpass_filter(raw_b_segment, sr, 85.0, 120.0))
        b85_cand = compute_rms(bandpass_filter(shifted_b, sr, 85.0, 120.0))
        xover_drop_db = 20.0 * np.log10(max(1e-12, b85_cand) / max(1e-12, b85_raw))

        # Safety policy
        if mode == "micro_limiter":
            effective_net_db = gain_db - max(0.0, peak_diff_db)
            accept = (effective_net_db >= 0.15) and (xover_drop_db >= -0.5)
        else: # crest_factor
            accept = (gain_db >= 0.10) and (peak_diff_db <= 0.20) and (xover_drop_db >= -0.5)

        effective_segment = shifted_b if accept else raw_b_segment

        bass_out[w_start:w_end] += effective_segment * w_taper
        weight_acc[w_start:w_end] += w_taper

    # Blend back
    unassigned = weight_acc < 1e-6
    bass_out[unassigned[:, 0]] = bass_stereo[unassigned[:, 0]]
    assigned = ~unassigned
    weight_div = np.maximum(1.0, weight_acc)
    bass_out[assigned[:, 0]] /= weight_div[assigned[:, 0]]
    
    return bass_out.astype(np.float32)


def allpass_biquad(audio: np.ndarray, sr: int, f0: float = 60.0, Q: float = 1.0) -> np.ndarray:
    """Second order allpass filter to rotate phase around f0 with 0 dB amplitude change."""
    w0 = 2 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2 * Q)
    b0 = 1 - alpha
    b1 = -2 * np.cos(w0)
    b2 = 1 + alpha
    a0 = 1 + alpha
    a1 = -2 * np.cos(w0)
    a2 = 1 - alpha

    b = np.array([b0, b1, b2]) / a0
    a = np.array([a0, a1, a2]) / a0
    return signal.lfilter(b, a, audio, axis=0).astype(np.float32)


def align_allpass_sub(
    drums: np.ndarray,
    bass: np.ndarray,
    sr: int,
    crossover_hz: float = 100.0,
) -> np.ndarray:
    """Candidate 3: All-Pass Phase Rotation on sub frequencies without shifting time/transients."""
    drums_stereo = ensure_stereo(drums)
    bass_stereo = ensure_stereo(bass)

    # Split sub and mid/high with Linkwitz-Riley crossover
    nyq = 0.5 * sr
    f_c = crossover_hz / nyq
    sos_lp = signal.butter(4, f_c, btype='low', output='sos')
    sos_hp = signal.butter(4, f_c, btype='high', output='sos')

    sub_b = signal.sosfiltfilt(sos_lp, bass_stereo, axis=0)
    high_b = signal.sosfiltfilt(sos_hp, bass_stereo, axis=0)

    sub_d = signal.sosfiltfilt(sos_lp, drums_stereo, axis=0)

    # Test phase rotation center frequencies around dominant bass fundamental [40, 50, 60, 70, 80 Hz]
    best_rotated_sub = sub_b
    best_score = -999.0

    raw_sum = sub_d + sub_b
    rms_raw = compute_rms(raw_sum)
    peak_raw = np.max(np.abs(drums_stereo + bass_stereo))

    for f_rot in [40.0, 50.0, 60.0, 70.0, 80.0, 95.0]:
        for q_val in [0.707, 1.0, 1.414]:
            cand_sub = allpass_biquad(sub_b, sr, f0=f_rot, Q=q_val)
            cand_sum = sub_d + cand_sub
            rms_cand = compute_rms(cand_sum)
            gain_db = 20.0 * np.log10(max(1e-12, rms_cand) / max(1e-12, rms_raw))

            cand_full_sum = drums_stereo + (cand_sub + high_b)
            cand_peak = np.max(np.abs(cand_full_sum))
            delta_peak_db = 20.0 * np.log10(max(1e-12, cand_peak) / max(1e-12, peak_raw))

            # Effective gain after limiter
            score = gain_db - max(0.0, delta_peak_db)
            if score > best_score and score > 0.10:
                best_score = score
                best_rotated_sub = cand_sub

    # Recombine with high band
    recombined_bass = best_rotated_sub + high_b
    return recombined_bass.astype(np.float32)


def main():
    print("=" * 80)
    print("PHARMAKON BATTLE: Testing Alignment Strategies on Real Track")
    print(f"Loading Stems from: {STEMS_DIR}")
    print("=" * 80)

    drums_path = os.path.join(STEMS_DIR, "Drums.wav")
    bass_path = os.path.join(STEMS_DIR, "Bass.wav")
    vox_path = os.path.join(STEMS_DIR, "Vocals.wav")
    oth_path = os.path.join(STEMS_DIR, "Other.wav")

    drums, sr = sf.read(drums_path)
    bass, _ = sf.read(bass_path)
    vox, _ = sf.read(vox_path)
    oth, _ = sf.read(oth_path)

    # Convert to stereo
    drums = ensure_stereo(drums)
    bass = ensure_stereo(bass)
    vox = ensure_stereo(vox)
    oth = ensure_stereo(oth)

    # 1. Baseline: Raw Sum
    baseline_kb = drums + bass
    baseline_full = drums + bass + vox + oth

    # Sub-band filter for measurement (<100 Hz)
    sub_kb_base = lowpass_filter(baseline_kb, sr, cutoff=100.0)
    rms_sub_base = compute_rms(sub_kb_base)
    tp_base = compute_true_peak(baseline_kb)
    tp_full_base = compute_true_peak(baseline_full)
    crest_base = tp_base / (compute_rms(baseline_kb) + 1e-12)

    results = []
    results.append({
        "Name": "0. Baseline (Оригинал без вмешательств)",
        "Delta_Sub_dB": 0.0,
        "Delta_TP_KB_dB": 0.0,
        "Effective_Sub_dB": 0.0,
        "Crest_Factor": crest_base,
        "Full_Mix_TP_dBTP": 20.0 * np.log10(tp_full_base),
        "aligned_bass": bass
    })

    # 2. Method D: Current GW-FRA (Max sub blind)
    print("\n[1/3] Running Current Method D (GW-FRA)...")
    bass_d, meta_d = method_d_guarded_per_kick(drums, bass, sr)
    sum_d = drums + bass_d
    sub_d = lowpass_filter(sum_d, sr, cutoff=100.0)
    rms_d = compute_rms(sub_d)
    tp_d = compute_true_peak(sum_d)
    delta_sub_d = 20.0 * np.log10(rms_d / rms_sub_base)
    delta_tp_d = 20.0 * np.log10(tp_d / tp_base)
    results.append({
        "Name": "1. Метод D (GW-FRA: слепой максимум)",
        "Delta_Sub_dB": delta_sub_d,
        "Delta_TP_KB_dB": delta_tp_d,
        "Effective_Sub_dB": delta_sub_d - max(0.0, delta_tp_d),
        "Crest_Factor": tp_d / (compute_rms(sum_d) + 1e-12),
        "Full_Mix_TP_dBTP": 20.0 * np.log10(compute_true_peak(drums + bass_d + vox + oth)),
        "aligned_bass": bass_d
    })

    # 3. Candidate 1: Micro-Limiter Aware GW-FRA
    print("\n[2/3] Running Candidate 1: Virtual Micro-Limiter...")
    bass_c1 = align_per_kick_custom(drums, bass, sr, mode="micro_limiter")
    sum_c1 = drums + bass_c1
    sub_c1 = lowpass_filter(sum_c1, sr, cutoff=100.0)
    rms_c1 = compute_rms(sub_c1)
    tp_c1 = compute_true_peak(sum_c1)
    delta_sub_c1 = 20.0 * np.log10(rms_c1 / rms_sub_base)
    delta_tp_c1 = 20.0 * np.log10(tp_c1 / tp_base)
    results.append({
        "Name": "2. Кандидат 1 (Виртуальный микро-лимитер)",
        "Delta_Sub_dB": delta_sub_c1,
        "Delta_TP_KB_dB": delta_tp_c1,
        "Effective_Sub_dB": delta_sub_c1 - max(0.0, delta_tp_c1),
        "Crest_Factor": tp_c1 / (compute_rms(sum_c1) + 1e-12),
        "Full_Mix_TP_dBTP": 20.0 * np.log10(compute_true_peak(drums + bass_c1 + vox + oth)),
        "aligned_bass": bass_c1
    })

    # 4. Candidate 2: Crest Factor Optimization
    print("\n[3/3] Running Candidate 2: Crest Factor Optimization...")
    bass_c2 = align_per_kick_custom(drums, bass, sr, mode="crest_factor")
    sum_c2 = drums + bass_c2
    sub_c2 = lowpass_filter(sum_c2, sr, cutoff=100.0)
    rms_c2 = compute_rms(sub_c2)
    tp_c2 = compute_true_peak(sum_c2)
    delta_sub_c2 = 20.0 * np.log10(rms_c2 / rms_sub_base)
    delta_tp_c2 = 20.0 * np.log10(tp_c2 / tp_base)
    results.append({
        "Name": "3. Кандидат 2 (Оптимизация Crest Factor)",
        "Delta_Sub_dB": delta_sub_c2,
        "Delta_TP_KB_dB": delta_tp_c2,
        "Effective_Sub_dB": delta_sub_c2 - max(0.0, delta_tp_c2),
        "Crest_Factor": tp_c2 / (compute_rms(sum_c2) + 1e-12),
        "Full_Mix_TP_dBTP": 20.0 * np.log10(compute_true_peak(drums + bass_c2 + vox + oth)),
        "aligned_bass": bass_c2
    })

    # 5. Candidate 3: All-Pass Phase Rotation
    print("\n[4/3] Running Candidate 3: All-Pass Phase Rotation...")
    bass_c3 = align_allpass_sub(drums, bass, sr)
    sum_c3 = drums + bass_c3
    sub_c3 = lowpass_filter(sum_c3, sr, cutoff=100.0)
    rms_c3 = compute_rms(sub_c3)
    tp_c3 = compute_true_peak(sum_c3)
    delta_sub_c3 = 20.0 * np.log10(rms_c3 / rms_sub_base)
    delta_tp_c3 = 20.0 * np.log10(tp_c3 / tp_base)
    results.append({
        "Name": "4. Кандидат 3 (All-Pass фазовращатель)",
        "Delta_Sub_dB": delta_sub_c3,
        "Delta_TP_KB_dB": delta_tp_c3,
        "Effective_Sub_dB": delta_sub_c3 - max(0.0, delta_tp_c3),
        "Crest_Factor": tp_c3 / (compute_rms(sum_c3) + 1e-12),
        "Full_Mix_TP_dBTP": 20.0 * np.log10(compute_true_peak(drums + bass_c3 + vox + oth)),
        "aligned_bass": bass_c3
    })

    # Print Report Table
    print("\n" + "=" * 95)
    print("РЕЗУЛЬТАТЫ СРАВНИТЕЛЬНОГО БАТТЛА (ТРЕК: Я УМИРАЮ ОТ ЖАЖДЫ)")
    print("=" * 95)
    header = f"{'Метод':<38} | {'Δ Саб (дБ)':<11} | {'Δ Peak (дБ)':<11} | {'Эффект. Саб':<12} | {'Crest Factor':<12}"
    print(header)
    print("-" * 95)
    for r in results:
        print(f"{r['Name']:<38} | {r['Delta_Sub_dB']:>+10.4f}  | {r['Delta_TP_KB_dB']:>+10.4f}  | {r['Effective_Sub_dB']:>+10.4f}  | {r['Crest_Factor']:>10.4f}")
    print("=" * 95)

    # Save audio files for listening (both isolated Kick+Bass and Full Mix)
    print("\nСохранение аудиофайлов для прослушивания в:", OUT_DIR)
    for idx, r in enumerate(results):
        prefix = f"{idx:02d}_{r['Name'].split()[1] if len(r['Name'].split()) > 1 else 'Base'}"
        clean_prefix = "".join(c for c in prefix if c.isalnum() or c in ('_', '-'))
        
        # Isolated Kick + Bass
        kb_audio = drums + r["aligned_bass"]
        # Normalize to prevent any digital overs in preview (safe ceiling -0.5 dBFS)
        kb_peak = np.max(np.abs(kb_audio))
        if kb_peak > 0:
            scale = min(1.0, 0.94 / kb_peak)
            kb_audio_norm = kb_audio * scale
        else:
            kb_audio_norm = kb_audio
        kb_out = os.path.join(OUT_DIR, f"{clean_prefix}_KickBass.wav")
        sf.write(kb_out, kb_audio_norm, sr, subtype="PCM_24")

        # Full Mix (Kick + Bass + Vox + Other)
        full_audio = drums + r["aligned_bass"] + vox + oth
        f_peak = np.max(np.abs(full_audio))
        if f_peak > 0:
            scale = min(1.0, 0.94 / f_peak)
            full_audio_norm = full_audio * scale
        else:
            full_audio_norm = full_audio
        full_out = os.path.join(OUT_DIR, f"{clean_prefix}_FullMix.wav")
        sf.write(full_out, full_audio_norm, sr, subtype="PCM_24")

        print(f"  -> Сохранены: {os.path.basename(kb_out)} и {os.path.basename(full_out)}")

    print("\n[OK] Эксперимент успешно завершён!")


if __name__ == "__main__":
    main()
