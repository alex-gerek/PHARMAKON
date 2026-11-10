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


# ---------------------------------------------------------------------------
# Tempo v2 (3.2): multi-band onset periodicity + metrical octave decision.
# Validated on ground-truth synthetic tracks (bench/validate_tempo.py): the
# previous sub-band-only detector (90-170 BPM) scored acc1 32 % / acc2 36 %
# (wrong on hip-hop, trap, DnB, rock, 3/4); this one scores acc1 86 % / acc2 100 %.
# ---------------------------------------------------------------------------
TEMPO_MIN_BPM = 50.0
TEMPO_MAX_BPM = 210.0
TEMPO_OFFBEAT_RATIO = 0.6   # a pulse level is "too slow" if its off-beats carry >= 60 % of the beat strength
_TEMPO_BANDS = ((20.0, 150.0), (150.0, 2000.0), (2000.0, 6000.0), (6000.0, 16000.0))


def _onset_bands(mono: np.ndarray, sr: int, hop: int = 256, n_fft: int = 2048):
    """Half-wave rectified log-spectral flux in 4 bands (kick / body / snare / hats), each unit-std."""
    f, _, Z = signal.stft(mono, sr, nperseg=n_fft, noverlap=n_fft - hop, boundary=None, padded=False)
    L = np.log1p(1000.0 * np.abs(Z))
    d = np.maximum(0.0, np.diff(L, axis=1))
    fps = sr / float(hop)
    w = max(3, int(round(0.4 * fps)))
    out = []
    for lo, hi in _TEMPO_BANDS:
        m = (f >= lo) & (f < min(hi, 0.5 * sr))
        e = d[m].sum(axis=0) if np.any(m) else np.zeros(d.shape[1])
        e = np.maximum(e - np.convolve(e, np.ones(w) / w, mode="same"), 0.0)
        out.append(e / (np.std(e) + 1e-12))
    return np.array(out), fps


def _acf(e: np.ndarray) -> np.ndarray:
    e = e - e.mean()
    n = len(e)
    F = np.fft.rfft(e, 2 * n)
    a = np.fft.irfft(np.abs(F) ** 2)[:n]
    return a / (a[0] + 1e-12)


def _interp(a: np.ndarray, x):
    x = np.asarray(x, dtype=float)
    i = np.clip(np.floor(x).astype(int), 0, len(a) - 2)
    fr = x - i
    return a[i] * (1.0 - fr) + a[i + 1] * fr


def _beat_offbeat(B: np.ndarray, tau: float):
    """Best phase (on kick+body+snare bands) and per-band off-beat/beat strength ratios."""
    n = B.shape[1]
    E = B[0] + B[1] + B[2]
    spread = lambda e: np.maximum(np.maximum(e, np.roll(e, 1)), np.roll(e, -1))  # +-1 frame tolerance
    Em = spread(E)
    best_b, best_ph = -1.0, 0.0
    for ph in np.arange(0.0, tau, 1.0):
        b = Em[np.round(np.arange(ph, n - 1, tau)).astype(int)].mean()
        if b > best_b:
            best_b, best_ph = b, ph
    pos = np.arange(best_ph, n - 1, tau)
    off = pos + tau / 2.0
    off = off[off < n - 1]
    ratios = []
    for k in range(3):
        em = spread(B[k])
        b = em[np.round(pos).astype(int)].mean()
        o = em[np.round(off).astype(int)].mean()
        ratios.append(float(o / (b + 1e-12)))
    return ratios, best_ph


def detect_tempo(mix_mono: np.ndarray, sr: int) -> dict:
    """
    Tempo with evidence. Returns bpm (quarter-note level), alt_bpm (the octave a
    listener might also tap, or None), octave_confident, pulse_clarity (0..1),
    and the per-level off-beat ratios used for the decision.
    """
    mono = np.asarray(mix_mono, dtype=float)
    B, fps = _onset_bands(mono, sr)
    # the beat is carried by kick / body / snare; hats (> 6 kHz) often play subdivisions or
    # triplets (e.g. 94 BPM with triplet hats reads as 140 when hats vote)
    full = B[0] + B[1] + B[2]
    full = np.convolve(full, np.array([0.25, 0.5, 0.25]), mode="same")
    A = _acf(full)

    # 1) periodicity: comb over beat multiples (finds the right tempo FAMILY, octave-agnostic)
    bpms = np.arange(40.0, 240.0, 0.25)
    taus = 60.0 * fps / bpms
    valid = 4.0 * taus < len(A) - 2

    def _comb(acf_):
        c = sum(_interp(acf_, k * taus) / k for k in (1, 2, 3, 4))
        return np.where(valid, c, -np.inf)

    def _same_family(a, b):
        r = np.log2(a / b)
        return abs(r - round(r)) < 0.03

    comb = _comb(A)
    bpm_sum = float(bpms[int(np.argmax(comb))])
    # Meter conflict check (e.g. a 2.56 s bar split in 4 = 94 BPM or in 3 = 70/140).
    # The summed comb can prefer the 3-division because shakers / triplet hats feed it.
    # Kick, body and snare bands each score both families (best octave member, plain
    # beat-lag autocorrelation, normalised per band); the drum bands decide. A rival
    # whose period is an integer multiple of a summed-family beat is only a grouping
    # (a 3/4 bar, a half-note) and never overrides.
    band_acf = []
    for k in range(3):
        ak = _interp(_acf(np.convolve(B[k], np.array([0.25, 0.5, 0.25]), mode="same")), taus)
        ak = np.where(valid & (bpms >= TEMPO_MIN_BPM) & (bpms <= TEMPO_MAX_BPM), ak, -np.inf)
        band_acf.append(ak)

    def _family_score(fb):
        tot = 0.0
        for ak in band_acf:
            top = float(np.max(ak))
            if top <= 0:
                continue
            best = -np.inf
            for e in range(-3, 4):
                c = fb * 2.0 ** e
                if TEMPO_MIN_BPM <= c <= TEMPO_MAX_BPM:
                    best = max(best, float(ak[int(np.argmin(np.abs(bpms - c)))]))
            tot += max(0.0, best) / top
        return tot

    def _is_grouping(slow, fast_family):
        for e in range(-3, 4):
            f = fast_family * 2.0 ** e
            r = f / slow
            if r >= 1.9 and abs(r - round(r)) < 0.03:
                return True
        return False

    rival_family = None
    bpm0 = bpm_sum
    for ak in band_acf:
        cand = float(bpms[int(np.argmax(ak))])
        if _same_family(cand, bpm_sum) or _is_grouping(cand, bpm_sum):
            continue
        s_c, s_s = _family_score(cand), _family_score(bpm_sum)
        if s_c > s_s + 0.05:
            bpm0, rival_family = cand, bpm_sum
            break
        if s_c > 0.85 * s_s:
            rival_family = cand

    # 2) octave: climb from the slowest level until off-beats stop carrying kick/snare hits
    cands = sorted({bpm0 * 2.0 ** k for k in range(-3, 4) if TEMPO_MIN_BPM <= bpm0 * 2.0 ** k <= TEMPO_MAX_BPM})
    if not cands:
        cands = [float(np.clip(bpm0, TEMPO_MIN_BPM, TEMPO_MAX_BPM))]
    levels = []
    chosen = None
    for c in cands:
        r, _ = _beat_offbeat(B, 60.0 * fps / c)
        levels.append({"bpm": round(float(c), 2), "offbeat_ratio": [round(v, 3) for v in r]})
        if chosen is None and max(r) < TEMPO_OFFBEAT_RATIO:
            chosen = c
    decided = chosen is not None
    if chosen is None:
        # no level has clean off-beats (dense mix): take the level closest to 120 BPM
        chosen = min(cands, key=lambda c: abs(np.log2(c / 120.0)))

    # 3) precision: fit the period over 16 beat multiples (error / 16 vs one lag)
    tau0 = 60.0 * fps / chosen
    kmax = int(max(1, min(16, (len(A) - 3) // max(1.0, tau0))))
    grid = tau0 * (1.0 + np.linspace(-0.012, 0.012, 2401))
    ks = np.arange(1, kmax + 1)
    score = _interp(A, grid[:, None] * ks[None, :]).sum(axis=1)
    tau = float(grid[int(np.argmax(score))])
    bpm = 60.0 * fps / tau

    # 4) honesty: margin of the octave decision
    idx = [i for i, L in enumerate(levels) if abs(L["bpm"] - round(chosen, 2)) < 0.02]
    i = idx[0] if idx else 0
    r_here = max(levels[i]["offbeat_ratio"])
    r_below = max(levels[i - 1]["offbeat_ratio"]) if i > 0 else None
    margin_up = TEMPO_OFFBEAT_RATIO - r_here
    margin_down = (r_below - TEMPO_OFFBEAT_RATIO) if r_below is not None else 1.0
    octave_confident = bool(decided and margin_up >= 0.15 and margin_down >= 0.15)
    alt = None
    if not octave_confident:
        dbl, half = bpm * 2.0, bpm / 2.0
        if margin_up < 0.15 and dbl <= TEMPO_MAX_BPM + 30.0:
            alt = dbl
        elif half >= 40.0:
            alt = half
    if alt is None and bpm < 80.0:
        # half-time grooves (trap, dubstep, half-time DnB) are the same pattern as a slow
        # groove with a backbeat; the genre convention often counts them double.
        alt = bpm * 2.0
        octave_confident = False
    if alt is not None and not (70.0 <= alt <= 180.0):
        alt = None   # outside the range people count in (e.g. "134 or 67"): not a useful alternative
    if alt is None and rival_family is not None:
        # a strong non-octave rival (3:2 etc.): show it in the counted range
        r = rival_family
        while r < 70.0:
            r *= 2.0
        while r > 180.0:
            r /= 2.0
        if 70.0 <= r <= 180.0:
            alt = r
            octave_confident = False
    pulse = float(np.clip(_interp(A, np.array([tau]))[0], 0.0, 1.0))
    return {
        "bpm": round(float(bpm), 2),
        "alt_bpm": round(float(alt), 1) if alt else None,
        "octave_confident": octave_confident,
        "pulse_clarity": round(pulse, 3),
        "levels": levels,
    }


def detect_bpm_and_grid(mix_mono: np.ndarray, sr: int):
    """Track BPM and bar length (4/4 assumed for the bar grid)."""
    t = detect_tempo(mix_mono, sr)
    bpm = t["bpm"]
    return bpm, (60.0 / bpm) * 4.0


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


def analyze_track_style(
    mix_mono: np.ndarray,
    sr: int,
    kick_peaks: np.ndarray = None,
    sub_bass: np.ndarray = None,
) -> tuple:
    dur_s = float(len(mix_mono) / sr)
    if sub_bass is None:
        sub_bass = butter_lowpass(mix_mono, 100.0, sr, order=2)
        
    rms_full = float(np.sqrt(np.mean(mix_mono**2) + 1e-12))
    rms_sub = float(np.sqrt(np.mean(sub_bass**2) + 1e-12))
    sub_ratio_db = float(20.0 * np.log10(rms_sub / max(1e-12, rms_full)))

    if kick_peaks is None or len(kick_peaks) == 0:
        env = np.abs(sub_bass)
        win_len = int(round(0.005 * sr))
        env_smooth = np.convolve(env, np.ones(win_len) / win_len, mode="same")
        env_max = float(np.max(env_smooth))
        if env_max > 1e-4:
            peak_thr = max(0.005, env_max * 0.12)
            min_dist = int(round(0.20 * sr))
            kick_peaks, _ = signal.find_peaks(env_smooth, height=peak_thr, distance=min_dist)
        else:
            kick_peaks = np.array([], dtype=int)

    k_count = len(kick_peaks)
    k_density = float(k_count / max(1.0, dur_s))

    four_on_floor_score = 0.0
    if k_count >= 8:
        intervals = np.diff(kick_peaks) / float(sr)
        median_iv = float(np.median(intervals))
        valid_ivs = intervals[np.abs(intervals - median_iv) < median_iv * 0.5]
        if len(valid_ivs) >= 4:
            std_iv = float(np.std(valid_ivs))
            cv = std_iv / max(1e-4, median_iv)
            regularity = float(np.clip(1.0 - (cv / 0.18), 0.0, 1.0))
            density_weight = float(np.clip((k_density - 1.0) / 1.0, 0.0, 1.0))
            four_on_floor_score = regularity * density_weight

    descriptors = {
        "four_on_floor_score": round(four_on_floor_score, 3),
        "sub_ratio_db": round(sub_ratio_db, 2),
        "kick_density_per_s": round(k_density, 2),
    }

    if four_on_floor_score >= 0.40 or (k_density >= 1.6 and sub_ratio_db > -8.0):
        confidence = float(np.clip(0.70 + four_on_floor_score * 0.30, 0.70, 0.99))
        return "electronic", "Electronic / Techno / Club", confidence, descriptors
    elif k_density < 0.25 and sub_ratio_db < -12.0:
        return "ambient", "Acoustic / Ambient / Freeform", 0.85, descriptors
    else:
        conf = float(np.clip(0.75 + (1.0 - four_on_floor_score) * 0.20, 0.70, 0.95))
        return "pop_rock", "Pop / Rock / Song", conf, descriptors

def compute_section_chroma(mix_mono: np.ndarray, sr: int, boundaries: list) -> np.ndarray:
    n_fft = 4096
    w = np.hanning(n_fft)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    valid_mask = (freqs >= 65.0) & (freqs <= 2000.0)
    valid_freqs = freqs[valid_mask]
    midi_pitches = 12.0 * np.log2(np.maximum(1.0, valid_freqs) / 440.0) + 69.0
    pitch_classes = (np.round(midi_pitches).astype(int)) % 12

    chromas = []
    for i in range(len(boundaries) - 1):
        s0 = int(boundaries[i] * sr)
        s1 = int(boundaries[i+1] * sr)
        seg = mix_mono[s0:s1]
        c_sec = np.zeros(12, dtype=np.float32)
        hop = n_fft // 2
        for pos in range(0, max(1, len(seg) - n_fft), hop):
            frame = seg[pos:pos+n_fft] * w
            mag = np.abs(np.fft.rfft(frame))[valid_mask] ** 2
            np.add.at(c_sec, pitch_classes, mag)
        norm = float(np.linalg.norm(c_sec)) + 1e-9
        chromas.append(c_sec / norm)
    return np.array(chromas)


def build_provisional_track_map(
    full_mix: np.ndarray,
    sub_drums: np.ndarray = None,
    sub_bass: np.ndarray = None,
    sr: int = 44100,
    kick_peaks: np.ndarray = None,
    events_log: list = None,
    genre_mode: str = "auto",  # "auto", "electronic", "pop_song", "ambient"
) -> dict:
    mix_mono = np.mean(ensure_stereo(full_mix), axis=1)
    duration_s = float(len(mix_mono) / sr)

    # Kick-vs-bass sub correlation only exists when separate drum and bass signals are
    # given (stems mode). For a full mix both defaults are the SAME signal, which would
    # make the correlation a meaningless constant 1.00 - report None instead.
    kick_bass_separate = (sub_drums is not None) and (sub_bass is not None) and (sub_bass is not sub_drums)

    if sub_drums is None:
        sub_drums = butter_lowpass(mix_mono, 100.0, sr, order=2)
    if sub_bass is None:
        sub_bass = sub_drums

    tempo_info = detect_tempo(mix_mono, sr)
    bpm = tempo_info["bpm"]
    # Phrase grid resolution: a slow reading (< 80 BPM) is often the half-time of the
    # counted tempo; its double is on the SAME grid (every other line), so use the finer
    # one for section boundaries. The displayed tempo stays the measured one (+ alt).
    grid_bpm = bpm * 2.0 if bpm < 80.0 else bpm
    bar_s = (60.0 / grid_bpm) * 4.0

    # Detect kick peaks on sub_drums or low-end onsets
    if kick_peaks is None or len(kick_peaks) == 0:
        env = np.abs(sub_drums)
        win_len = int(round(0.005 * sr))
        env_smooth = np.convolve(env, np.ones(win_len) / win_len, mode="same")
        env_max = float(np.max(env_smooth))
        if env_max > 1e-4:
            peak_thr = max(0.005, env_max * 0.12)
            min_dist_samples = int(round(0.20 * sr))
            kick_peaks, _ = signal.find_peaks(env_smooth, height=peak_thr, distance=min_dist_samples)
        else:
            kick_peaks = np.array([])

    avg_mix_rms = float(20.0 * np.log10(np.sqrt(np.mean(mix_mono**2) + 1e-12)))
    avg_sub_rms = float(20.0 * np.log10(np.sqrt(np.mean(sub_bass**2) + 1e-12)))

    # Style Analysis & Genre Routing
    cat, genre_label, conf, desc = analyze_track_style(mix_mono, sr, kick_peaks=kick_peaks, sub_bass=sub_bass)
    
    if genre_mode == "auto":
        target_mode = cat
    elif genre_mode in ("electronic", "pop_rock", "ambient"):
        target_mode = genre_mode
    elif genre_mode == "pop_song":
        target_mode = "pop_rock"
    else:
        target_mode = "electronic"

    sections = []
    
    if target_mode == "electronic":
        # === 100% PRESERVED EXACT EDM / TECHNO ALGORITHM ===
        raw_b = detect_acoustic_boundaries(mix_mono, sr, bpm=grid_bpm)
        phrase_8 = 8.0 * bar_s
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

            half_pt = (s_idx + e_idx) // 2
            r_first = float(20.0 * np.log10(np.sqrt(np.mean(seg_mix[:(half_pt - s_idx)]**2) + 1e-12)))
            r_second = float(20.0 * np.log10(np.sqrt(np.mean(seg_mix[(half_pt - s_idx):]**2) + 1e-12)))
            rms_rise = r_second - r_first

            r_sub_first = float(20.0 * np.log10(np.sqrt(np.mean(seg_sb[:(half_pt - s_idx)]**2) + 1e-12)))
            r_sub_second = float(20.0 * np.log10(np.sqrt(np.mean(seg_sb[(half_pt - s_idx):]**2) + 1e-12)))
            sub_rise = r_sub_second - r_sub_first

            corr = (float(np.corrcoef(seg_sd, seg_sb)[0, 1]) if (len(seg_sd) > 0 and r_sd > -60.0 and r_sb > -60.0) else 0.0) if kick_bass_separate else None

            is_start = (i == 0)
            is_end = (i == len(raw_b) - 2)

            if is_start and (d_rms < -0.1 or crest_factor > 9.8 or k_density < 0.8):
                sec_type = "Intro"
                sec_tag = "INTRO"
                sec_color = "#f59e0b"
            elif is_end and (d_rms < -0.3 or sub_rise < -1.0 or k_density < 0.6):
                sec_type = "Outro"
                sec_tag = "OUTRO"
                sec_color = "#a855f7"
            elif d_sub < -2.2 and crest_factor > 10.5:
                sec_type = "Breakdown"
                sec_tag = "BREAKDOWN"
                sec_color = "#10b981"
            elif prev_tag == "BREAKDOWN" or (sub_rise > 1.2 and d_sub < 0.5):
                sec_type = "Buildup"
                sec_tag = "BUILDUP"
                sec_color = "#f97316"
            elif t0 > duration_s * 0.65 and d_sub > 0.1 and crest_factor < 8.8 and (prev_tag in ("BUILDUP", "BREAKDOWN")):
                sec_type = "Climax / Drop"
                sec_tag = "DROP"
                sec_color = "#f43f5e"
            elif i == 1:
                sec_type = "Drop / Groove"
                sec_tag = "DROP"
                sec_color = "#f43f5e"
            elif i == 2:
                sec_type = "Development"
                sec_tag = "GROOVE"
                sec_color = "#0ea5e9"
            elif i == 3:
                sec_type = "Dense Middle"
                sec_tag = "GROOVE"
                sec_color = "#0ea5e9"
            elif (i + 1 < len(raw_b) - 1 and (raw_b[i+1] >= duration_s * 0.5) and (i >= 3) and (raw_b[i+2] - raw_b[i+1] <= bar_s * 10)) or (d_sub < 0.0 and d_sub >= -2.2):
                sec_type = "Interlude"
                sec_tag = "INTERLUDE"
                sec_color = "#6366f1"
            elif d_sub >= 0.0 and crest_factor < 9.5:
                sec_type = "Groove"
                sec_tag = "GROOVE"
                sec_color = "#0ea5e9"
            elif (i + 1 < len(raw_b) - 1 and (raw_b[i+2] - raw_b[i+1] <= phrase_8 * 1.25) and (i >= 3)) or (d_sub < 0.0 and d_sub >= -2.2):
                sec_type = "Interlude"
                sec_tag = "INTERLUDE"
                sec_color = "#6366f1"
            else:
                sec_type = f"Section {i + 1:02d}"
                sec_tag = "SECTION"
                sec_color = "#38bdf8"

            prev_tag = sec_tag
            sections.append({
                "sec_type": sec_type, "sec_tag": sec_tag, "sec_color": sec_color,
                "t0": t0, "t1": t1, "sec_dur": sec_dur, "bars_count": bars_count,
                "s_idx": s_idx, "e_idx": e_idx, "r_mix": r_mix, "r_sd": r_sd, "r_sb": r_sb,
                "pk_mix": pk_mix, "crest_factor": crest_factor, "corr": corr,
                "k_in_sec": k_in_sec, "k_count": k_count, "k_density": k_density
            })
    else:
        # === SONG / POP / ROCK / AMBIENT SSM ARCHITECTURE ===
        phrase_4 = 4.0 * bar_s
        n_4bars = int(round(duration_s / phrase_4))
        raw_grid = [0.0]
        for b in range(1, n_4bars):
            raw_grid.append(round(b * phrase_4, 2))
        raw_grid.append(round(duration_s, 2))
        raw_grid = sorted(list(set(raw_grid)))

        rms_blocks = []
        rise_blocks = []
        for i in range(len(raw_grid) - 1):
            s0 = int(raw_grid[i] * sr)
            s1 = int(raw_grid[i+1] * sr)
            seg = mix_mono[s0:s1]
            r = 20.0 * np.log10(np.sqrt(np.mean(seg**2)) + 1e-12)
            half = len(seg) // 2
            r1 = 20.0 * np.log10(np.sqrt(np.mean(seg[:half]**2)) + 1e-12)
            r2 = 20.0 * np.log10(np.sqrt(np.mean(seg[half:]**2)) + 1e-12)
            rms_blocks.append(r)
            rise_blocks.append(r2 - r1)

        chromas = compute_section_chroma(mix_mono, sr, raw_grid)
        ssm = np.dot(chromas, chromas.T)

        avg_rms = float(np.mean(rms_blocks))
        max_rms = float(np.max(rms_blocks))

        chorus_scores = []
        for i in range(len(raw_grid) - 1):
            loudness_factor = max(0.0, (rms_blocks[i] - avg_rms) / max(1.0, max_rms - avg_rms))
            loud_sims = [ssm[i, j] for j in range(len(raw_grid) - 1) if j != i and rms_blocks[j] >= avg_rms - 0.5]
            rep_factor = float(np.mean(loud_sims)) if loud_sims else 0.0
            chorus_scores.append(loudness_factor * 0.5 + rep_factor * 0.5)

        is_chorus_block = [s >= 0.55 for s in chorus_scores]

        i = 0
        verse_count = 0
        chorus_count = 0
        while i < len(raw_grid) - 1:
            t0 = raw_grid[i]
            if i == 0:
                sec_tag = "INTRO"
                sec_type = "Intro"
                sec_color = "#f59e0b"
                step = 1
            elif i >= len(raw_grid) - 2 and (rms_blocks[i] < avg_rms or rise_blocks[i] < -1.0):
                sec_tag = "OUTRO"
                sec_type = "Outro"
                sec_color = "#64748b"
                step = len(raw_grid) - 1 - i
            elif is_chorus_block[i]:
                chorus_count += 1
                sec_tag = "CHORUS"
                sec_type = f"Chorus {chorus_count}"
                sec_color = "#e11d48"
                step = 1
                while i + step < len(raw_grid) - 1 and is_chorus_block[i + step]:
                    step += 1
            elif rise_blocks[i] > 1.0 or (i + 1 < len(raw_grid) - 1 and is_chorus_block[i + 1] and rms_blocks[i] < rms_blocks[i+1] - 1.0):
                sec_tag = "PRECHORUS"
                sec_type = "Pre-Chorus"
                sec_color = "#fb923c"
                step = 1
            elif t0 >= duration_s * 0.60 and t0 <= duration_s * 0.85 and chorus_count >= 1:
                chorus_sim = np.mean([ssm[i, c_idx] for c_idx in range(len(raw_grid) - 1) if is_chorus_block[c_idx]]) if any(is_chorus_block) else 0.0
                if chorus_sim < 0.85:
                    sec_tag = "BRIDGE"
                    sec_type = "Bridge"
                    sec_color = "#a855f7"
                    step = 1
                    while i + step < len(raw_grid) - 1 and not is_chorus_block[i + step] and step < 2:
                        step += 1
                else:
                    verse_count += 1
                    sec_tag = "VERSE"
                    sec_type = f"Verse {verse_count}"
                    sec_color = "#38bdf8"
                    step = 1
            else:
                verse_count += 1
                sec_tag = "VERSE"
                sec_type = f"Verse {verse_count}"
                sec_color = "#38bdf8"
                step = 1
                while i + step < len(raw_grid) - 1 and not is_chorus_block[i + step] and not (rise_blocks[i+step] > 1.0) and step < 2:
                    step += 1

            t1 = raw_grid[min(len(raw_grid) - 1, i + step)]
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
            corr = (float(np.corrcoef(seg_sd, seg_sb)[0, 1]) if (len(seg_sd) > 0 and r_sd > -60.0 and r_sb > -60.0) else 0.0) if kick_bass_separate else None

            sections.append({
                "sec_type": sec_type, "sec_tag": sec_tag, "sec_color": sec_color,
                "t0": t0, "t1": t1, "sec_dur": sec_dur, "bars_count": bars_count,
                "s_idx": s_idx, "e_idx": e_idx, "r_mix": r_mix, "r_sd": r_sd, "r_sb": r_sb,
                "pk_mix": pk_mix, "crest_factor": crest_factor, "corr": corr,
                "k_in_sec": k_in_sec, "k_count": k_count, "k_density": k_density
            })
            i += step

    # Build final standardized JSON structure for each section
    out_sections = []
    for idx, s in enumerate(sections):
        t0 = s["t0"]
        t1 = s["t1"]
        sec_dur = s["sec_dur"]
        bars_count = s["bars_count"]
        r_mix = s["r_mix"]
        r_sd = s["r_sd"]
        r_sb = s["r_sb"]
        pk_mix = s["pk_mix"]
        crest_factor = s["crest_factor"]
        corr = s["corr"]
        k_in_sec = s["k_in_sec"]
        k_count = s["k_count"]
        k_density = s["k_density"]

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

        out_sections.append({
            "sec_index": idx + 1,
            "section_index": idx + 1,
            "name": s["sec_type"],
            "sec_tag": s["sec_tag"],
            "tag": s["sec_tag"],
            "color": s["sec_color"],
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
            "sub_correlation_r": round(corr, 3) if corr is not None else None,
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
        "tempo_alt_bpm": tempo_info["alt_bpm"],
        "tempo_octave_confident": tempo_info["octave_confident"],
        "tempo_pulse_clarity": tempo_info["pulse_clarity"],
        "total_kicks": len(kick_peaks),
        "total_kick_events": len(kick_peaks),
        "num_sections": len(out_sections),
        "genre": {
            "category": cat,
            "label": genre_label,
            "confidence": conf,
            "mode_applied": target_mode,
            "descriptors": desc
        },
        "sections": out_sections,
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
        if best_lag > 0:
            cand_b_sub[:best_lag] = b_sub_win[:best_lag]
        elif best_lag < 0:
            cand_b_sub[best_lag:] = b_sub_win[best_lag:]
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
            # Seamless crossfade onto the current output (not the raw segment), so a
            # window overlapping a previously corrected kick does not jump back to raw.
            bass_corrected[w_start:w_end] = bass_corrected[w_start:w_end] * (1.0 - w_taper) + shifted_b * w_taper
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
