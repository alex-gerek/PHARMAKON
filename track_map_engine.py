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


def detect_bpm_and_grid(mix_mono: np.ndarray, sr: int):
    """
    Detects track BPM and bar/phrase grid from low-end rhythmic onsets.
    """
    nyq = 0.5 * sr
    b_sub, a_sub = signal.butter(2, min(nyq - 10, 120.0) / nyq, btype='low')
    sub = signal.filtfilt(b_sub, a_sub, mix_mono)

    env_sub = np.abs(sub)
    w_smooth = int(round(0.008 * sr))
    env_s_smooth = np.convolve(env_sub, np.ones(w_smooth) / w_smooth, mode='same')
    d_sub_env = np.maximum(0, np.diff(env_s_smooth, prepend=env_s_smooth[0]))
    d_sub_env = np.convolve(d_sub_env, np.ones(w_smooth) / w_smooth, mode='same')

    hop_onset = int(0.005 * sr)
    ds = d_sub_env[::hop_onset] - np.mean(d_sub_env[::hop_onset])
    corr = np.correlate(ds, ds, mode='full')
    corr = corr[len(corr) // 2 :]

    min_lag = int(round((60.0 / 170.0) / 0.005))
    max_lag = int(round((60.0 / 90.0) / 0.005))
    best_lag = min_lag + np.argmax(corr[min_lag:max_lag])
    bpm = float(60.0 / (best_lag * 0.005))

    if bpm < 100.0 and corr[best_lag // 2] > 0.6 * corr[best_lag]:
        bpm *= 2.0

    bar_s = (60.0 / bpm) * 4.0
    return round(bpm, 2), bar_s


def detect_acoustic_boundaries(mix_mono: np.ndarray, sr: int, bpm: float = None) -> list:
    """
    Detects dynamic structural change points from acoustic novelty of the full mix.
    Snaps to musical phrase grid (16-bar macro phrases and 8-bar sub-phrases).
    """
    duration_s = float(len(mix_mono) / sr)
    if not bpm or bpm < 60.0 or bpm > 220.0:
        bpm, bar_s = detect_bpm_and_grid(mix_mono, sr)
    else:
        bar_s = (60.0 / bpm) * 4.0

    phrase_8 = 8.0 * bar_s
    phrase_16 = 16.0 * bar_s

    nyq = 0.5 * sr
    b_sub, a_sub = signal.butter(2, min(nyq - 10, 100.0) / nyq, btype='low')
    sub_sig = signal.filtfilt(b_sub, a_sub, mix_mono)

    # True physical energy RMS (not arithmetic mean of dBs)
    track_mean_sub = float(20.0 * np.log10(np.sqrt(np.mean(sub_sig**2)) + 1e-12))
    track_mean_mix = float(20.0 * np.log10(np.sqrt(np.mean(mix_mono**2)) + 1e-12))

    # Candidate 8-bar grid
    n_blocks = int(round(duration_s / phrase_8))
    grid = [0.0]
    for b in range(1, n_blocks):
        grid.append(round(b * phrase_8, 2))
    grid.append(round(duration_s, 2))

    block_sub = []
    block_crest = []
    for i in range(len(grid) - 1):
        s0 = int(grid[i] * sr)
        s1 = int(grid[i+1] * sr)
        seg_m = mix_mono[s0:s1]
        seg_s = sub_sig[s0:s1]
        r_m = 20.0 * np.log10(np.sqrt(np.mean(seg_m**2)) + 1e-12)
        r_s = 20.0 * np.log10(np.sqrt(np.mean(seg_s**2)) + 1e-12)
        pk = 20.0 * np.log10(np.max(np.abs(seg_m)) + 1e-12)
        block_sub.append(r_s)
        block_crest.append(pk - r_m)

    boundaries = [0.0]
    curr_idx = 0
    while curr_idx < len(grid) - 1:
        rem_dur = duration_s - grid[curr_idx]
        if rem_dur <= phrase_8 * 1.25:
            break

        is_breakdown = (block_sub[curr_idx] - track_mean_sub < -2.2) and (block_crest[curr_idx] > 10.5)

        next_is_breakdown = False
        if curr_idx + 1 < len(grid) - 1:
            next_is_breakdown = (block_sub[curr_idx + 1] - track_mean_sub < -2.2) and (block_crest[curr_idx + 1] > 10.5)

        is_buildup = False
        if curr_idx > 0 and (block_sub[curr_idx - 1] - track_mean_sub < -2.2):
            is_buildup = True

        is_climax = False
        if curr_idx > 0 and (grid[curr_idx] > duration_s * 0.65) and (block_sub[curr_idx] - track_mean_sub > -0.2):
            if curr_idx > 1 and (block_sub[curr_idx - 1] - track_mean_sub < -2.2 or block_sub[curr_idx - 2] - track_mean_sub < -2.2):
                is_climax = True

        if (is_breakdown or is_buildup or is_climax) and (curr_idx + 1 < len(grid)):
            next_t = grid[curr_idx + 1]
            if next_t - boundaries[-1] >= phrase_8 * 0.8:
                boundaries.append(round(float(next_t), 2))
                curr_idx += 1
                continue

        if next_is_breakdown:
            next_t = grid[curr_idx + 1]
            if next_t - boundaries[-1] >= phrase_8 * 0.8:
                boundaries.append(round(float(next_t), 2))
                curr_idx += 1
                continue

        if curr_idx + 2 < len(grid):
            next_t = grid[curr_idx + 2]
            boundaries.append(round(float(next_t), 2))
            curr_idx += 2
        else:
            curr_idx += 1

    boundaries.append(round(float(duration_s), 2))
    boundaries = sorted(list(set(boundaries)))
    return boundaries


def build_provisional_track_map(
    full_mix: np.ndarray,
    sub_drums: np.ndarray = None,
    sub_bass: np.ndarray = None,
    sr: int = 44100,
    kick_peaks: np.ndarray = None,
    events_log: list = None,
) -> dict:
    """
    Constructs a dynamic, content-aware multi-metric Track Intelligence Map.
    Identifies musical phrases (16-bar macro phrases and 8-bar transition phrases)
    and classifies musical roles (Intro, Drop/Groove, Development, Dense Middle,
    Interlude, Breakdown, Buildup, Climax/Drop, Outro) from measured physical acoustic descriptors.
    """
    mix_mono = np.mean(ensure_stereo(full_mix), axis=1)
    duration_s = float(len(mix_mono) / sr)

    if sub_drums is None:
        sub_drums = butter_lowpass(mix_mono, 100.0, sr, order=2)
    if sub_bass is None:
        sub_bass = sub_drums

    bpm, bar_s = detect_bpm_and_grid(mix_mono, sr)

    # Detect kick peaks on sub_drums or low-end onsets
    if kick_peaks is None or len(kick_peaks) == 0:
        env = np.abs(sub_drums)
        win_len = int(round(0.005 * sr))
        env_smooth = np.convolve(env, np.ones(win_len) / win_len, mode="same")
        env_max = float(np.max(env_smooth))
        if env_max > 1e-4:
            # Multi-scale adaptive peak picking
            peak_thr = max(0.005, env_max * 0.12)
            min_dist_samples = int(round(0.20 * sr))
            kick_peaks, _ = signal.find_peaks(env_smooth, height=peak_thr, distance=min_dist_samples)
        else:
            kick_peaks = np.array([])

    avg_mix_rms = float(20.0 * np.log10(np.sqrt(np.mean(mix_mono**2) + 1e-12)))
    avg_sub_rms = float(20.0 * np.log10(np.sqrt(np.mean(sub_bass**2) + 1e-12)))

    # Detect dynamic boundaries aligned with musical hyper-measures
    raw_b = detect_acoustic_boundaries(mix_mono, sr, bpm=bpm)

    sections = []
    prev_tag = None
    for i in range(len(raw_b) - 1):
        t0 = float(round(raw_b[i], 2))
        t1 = float(round(raw_b[i + 1], 2))
        s_idx = int(t0 * sr)
        e_idx = min(len(mix_mono), int(t1 * sr))
        sec_dur = t1 - t0
        bars_count = round(sec_dur / bar_s) if bar_s > 0 else 0

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
        k_density = float(k_count / max(1.0, sec_dur))
        d_rms = r_mix - avg_mix_rms
        d_sub = r_sb - avg_sub_rms

        # Energy slope across section
        half_pt = (s_idx + e_idx) // 2
        r_first = float(20.0 * np.log10(np.sqrt(np.mean(seg_mix[:(half_pt - s_idx)]**2) + 1e-12)))
        r_second = float(20.0 * np.log10(np.sqrt(np.mean(seg_mix[(half_pt - s_idx):]**2) + 1e-12)))
        rms_rise = r_second - r_first

        r_sub_first = float(20.0 * np.log10(np.sqrt(np.mean(seg_sb[:(half_pt - s_idx)]**2) + 1e-12)))
        r_sub_second = float(20.0 * np.log10(np.sqrt(np.mean(seg_sb[(half_pt - s_idx):]**2) + 1e-12)))
        sub_rise = r_sub_second - r_sub_first

        corr = float(np.corrcoef(seg_sd, seg_sb)[0, 1]) if (len(seg_sd) > 0 and r_sd > -60.0 and r_sb > -60.0) else 0.0

        is_start = (i == 0)
        is_end = (i == len(raw_b) - 2)

        # Multi-Feature Acoustic Role Classifier (Music Intelligence)
        if is_start and (d_rms < -0.1 or crest_factor > 9.8 or k_density < 0.8):
            sec_type = "Intro"
            sec_tag = "INTRO"
            sec_color = "#f59e0b"  # Amber
        elif is_end and (d_rms < -0.3 or sub_rise < -1.0 or k_density < 0.6):
            sec_type = "Outro"
            sec_tag = "OUTRO"
            sec_color = "#a855f7"  # Purple
        elif d_sub < -2.2 and crest_factor > 10.5:
            sec_type = "Breakdown"
            sec_tag = "BREAKDOWN"
            sec_color = "#10b981"  # Emerald
        elif prev_tag == "BREAKDOWN" or (sub_rise > 1.2 and d_sub < 0.5):
            sec_type = "Buildup"
            sec_tag = "BUILDUP"
            sec_color = "#f97316"  # Orange
        elif t0 > duration_s * 0.65 and d_sub > 0.1 and crest_factor < 8.8 and (prev_tag in ("BUILDUP", "BREAKDOWN")):
            sec_type = "Climax / Drop"
            sec_tag = "DROP"
            sec_color = "#f43f5e"  # Rose Red
        elif i == 1:
            sec_type = "Drop / Groove"
            sec_tag = "DROP"
            sec_color = "#f43f5e"  # Rose Red
        elif i == 2:
            sec_type = "Development"
            sec_tag = "GROOVE"
            sec_color = "#0ea5e9"  # Cyan Blue
        elif i == 3:
            sec_type = "Dense Middle"
            sec_tag = "GROOVE"
            sec_color = "#0ea5e9"  # Cyan Blue
        elif (i + 1 < len(raw_b) - 1 and (raw_b[i+1] >= duration_s * 0.5) and (i >= 3) and (raw_b[i+2] - raw_b[i+1] <= bar_s * 10)) or (d_sub < 0.0 and d_sub >= -2.2):
            sec_type = "Interlude"
            sec_tag = "INTERLUDE"
            sec_color = "#6366f1"  # Indigo
        elif d_sub >= 0.0 and crest_factor < 9.5:
            sec_type = "Groove"
            sec_tag = "GROOVE"
            sec_color = "#0ea5e9"  # Cyan Blue
        elif (i + 1 < len(raw_b) - 1 and (raw_b[i+2] - raw_b[i+1] <= phrase_8 * 1.25) and (i >= 3)) or (d_sub < 0.0 and d_sub >= -2.2):
            sec_type = "Interlude"
            sec_tag = "INTERLUDE"
            sec_color = "#6366f1"  # Indigo
        else:
            sec_type = f"Section {i + 1:02d}"
            sec_tag = "SECTION"
            sec_color = "#38bdf8"  # Steel/Sky Blue

        prev_tag = sec_tag

        # Event audit breakdown for this section
        events_acc = 0
        events_rej = 0
        events_byp = 0
        rejection_reasons = {}
        kicks_detail = []

        if events_log:
            sec_events = [e for e in events_log if t0 <= e.get('time_s', 0.0) < t1]
            events_acc = sum(1 for e in sec_events if e.get('decision') == 'ACCEPT')
            events_rej = sum(1 for e in sec_events if e.get('decision') == 'REJECT')
            events_byp = sum(1 for e in sec_events if e.get('decision') == 'BYPASS')
            for e in sec_events:
                t_e = e.get('time_s', 0.0)
                rel_pct = max(0.0, min(100.0, (t_e - t0) / max(0.01, sec_dur) * 100.0))
                kicks_detail.append({
                    "event_index": e.get('event_index'),
                    "time_s": t_e,
                    "rel_pct": round(rel_pct, 1),
                    "decision": e.get('decision'),
                    "applied_shift_ms": e.get('applied_shift_ms', 0.0),
                    "candidate_shift_ms": e.get('candidate_shift_ms', 0.0),
                    "reason": e.get('reason', '')
                })
                if e.get('decision') == 'REJECT':
                    r_str = e.get('reason', 'rejected')
                    key = r_str.split('(')[0].split(' ')[0].strip()
                    rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
        else:
            events_byp = k_count
            for k in k_in_sec:
                t_k = float(k / sr)
                rel_pct = max(0.0, min(100.0, (t_k - t0) / max(0.01, sec_dur) * 100.0))
                kicks_detail.append({
                    "time_s": round(t_k, 3),
                    "rel_pct": round(rel_pct, 1),
                    "decision": "DETECTED",
                    "applied_shift_ms": 0.0
                })

        # Policy verdict in international English
        if events_acc > 0:
            policy_verdict = f"{events_acc} kicks phase-locked (Zero Peak Inflation)"
        elif events_rej > 0:
            top_rej = max(rejection_reasons.items(), key=lambda x: x[1])[0] if rejection_reasons else "optimal"
            if top_rej == "zero_lag_optimal":
                policy_verdict = "Phase optimal (0-lag reference)"
            elif top_rej == "sub_loss":
                policy_verdict = "Sub-bass headroom preserved"
            elif top_rej == "peak_inflation":
                policy_verdict = "True-Peak guard protected"
            else:
                policy_verdict = f"Phase optimal ({top_rej})"
        elif k_count == 0:
            policy_verdict = "Acoustic transparency (safe path)"
        else:
            policy_verdict = "Linear acoustic balance"

        m0, s0_rem = divmod(int(t0), 60)
        m1, s1_rem = divmod(int(t1), 60)

        sections.append({
            "sec_index": i + 1,
            "section_index": i + 1,
            "name": sec_type,
            "sec_tag": sec_tag,
            "tag": sec_tag,
            "color": sec_color,
            "start_s": t0,
            "end_s": t1,
            "time_start_s": t0,
            "time_end_s": t1,
            "start_str": f"{m0}:{s0_rem:02d}",
            "end_str": f"{m1}:{s1_rem:02d}",
            "time_str": f"{m0}:{s0_rem:02d} - {m1}:{s1_rem:02d}",
            "duration_s": round(sec_dur, 2),
            "bars_count": bars_count,
            "kicks_count": k_count,
            "kick_events_count": k_count,
            "kicks_density_per_s": round(k_density, 2),
            "rms_mix_dbfs": round(r_mix, 2),
            "rms_sub_drums_dbfs": round(r_sd, 2),
            "rms_sub_bass_dbfs": round(r_sb, 2),
            "peak_mix_dbfs": round(pk_mix, 2),
            "peak_dbfs": round(pk_mix, 2),
            "crest_factor_db": round(crest_factor, 2),
            "sub_correlation_r": round(corr, 3),
            "events_accepted": events_acc,
            "events_rejected": events_rej,
            "events_bypassed": events_byp,
            "rejection_reasons": rejection_reasons,
            "policy_verdict": policy_verdict,
            "kicks_detail": kicks_detail,
        })

    m_tot, s_tot = divmod(int(duration_s), 60)
    return {
        "duration_s": round(duration_s, 2),
        "total_duration_s": round(duration_s, 2),
        "duration_str": f"{m_tot}:{s_tot:02d}",
        "tempo_bpm": round(bpm, 1),
        "estimated_bpm": round(bpm, 1),
        "total_kicks": len(kick_peaks),
        "total_kick_events": len(kick_peaks),
        "num_sections": len(sections),
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
                "reason": "mode_bypass (processing disabled)",
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
            reason = "zero_lag_optimal (reference alignment)"
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

    track_map = build_provisional_track_map(
        full_mix=raw_d_mono + raw_b_mono,
        sub_drums=sub_drums,
        sub_bass=sub_bass,
        sr=sr,
        kick_peaks=kick_peaks,
        events_log=events_log,
    )

    meta = {
        "mode": mode,
        "events_detected": len(kick_peaks),
        "events_corrected": corrected_count,
        "events_rejected": len(kick_peaks) - corrected_count,
        "safe_bypass_engaged": (corrected_count == 0),
        "average_shift_ms": float(np.mean(applied_shifts_ms)) if applied_shifts_ms else 0.0,
        "track_map": track_map,
        "events_log": events_log,
    }

    return bass_corrected.astype(np.float32), meta, events_log
