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


ONSET_HOP, ONSET_NFFT = 256, 2048


def onset_latency_s(sr: int) -> float:
    """
    Onset-function frame m peaks about n_fft - hop samples BEFORE the hit it marks: the
    log flux rises as soon as the hit enters the far edge of the 2048-sample window, and
    diff() puts that rise one hop earlier. Measured (bench/validate_bar_grid.py, sharp
    drum hits): 1770-1800 samples at 44.1, 48 and 96 kHz; softer attacks peak later
    (10 ms attack ~1350-1530), quieter hits a little later (-40 dB ~1430-1590).
    Frame index -> time: m / fps + onset_latency_s(sr).
    """
    return (ONSET_NFFT - ONSET_HOP) / float(sr)


def _onset_bands(mono: np.ndarray, sr: int, hop: int = ONSET_HOP, n_fft: int = ONSET_NFFT):
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
            if not (TEMPO_MIN_BPM <= f <= TEMPO_MAX_BPM):
                continue
            r = f / slow
            if r >= 1.9 and abs(r - round(r)) < 0.03:
                return True
        return False

    rival_family = None
    bpm0 = bpm_sum
    tops = [float(bpms[int(np.argmax(ak))]) for ak in band_acf]
    for cand in tops:
        if _same_family(cand, bpm_sum) or _is_grouping(cand, bpm_sum):
            continue
        s_c, s_s = _family_score(cand), _family_score(bpm_sum)
        votes_c = sum(1 for t in tops if _same_family(t, cand))
        # override only when two or more drum bands agree: one band alone (a bass line,
        # a shaker) does not define the beat, but a close rival is still shown as alt
        if votes_c >= 2 and s_c > s_s + 0.05:
            bpm0, rival_family = cand, bpm_sum
            break
        if s_c > 0.85 * s_s and (rival_family is None or s_c > _family_score(rival_family)):
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
    if rival_family is not None:
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


# ---------------------------------------------------------------------------
# Sections v2 (3.2): downbeat-anchored bar grid, bar-feature novelty, measured labels.
# Validated on ground-truth arrangements (bench/validate_sections.py): the 3.1 grid
# (fixed 8/16-bar blocks from t = 0, positional labels) scored boundary F 0.22
# (+-0.5 s) and 27 % correct labels; held-out: 0.29 / 24 %. This: 0.97 / 99 %,
# held-out 0.91 / 92 %.
# ---------------------------------------------------------------------------
SEC_FEAT_BANDS = ((20.0, 100.0), (100.0, 300.0), (300.0, 2000.0), (2000.0, 6000.0), (6000.0, 16000.0))
SEC_NOVELTY_PROMINENCE = 0.12   # middle of the 0.08-0.12 plateau where boundary F is flat
SEC_MIN_BARS = 4
SEC_DENSITY_WEIGHT = 1.0        # weight of the onset-density features in the bar distance
SEC_MIN_TRACK_BARS = 8          # shorter audio is reported as one CLIP, not segmented
SEC_RUN_DB = 8.0                # breakdown run: low end this far below the track median ...
SEC_RUN_BARS = 4                # ... for at least this many bars
SEC_LOW_DROP_DB = 6.0           # section-level breakdown threshold (vs time-weighted median)
SEC_MERGE_NOVELTY = 0.5         # same-label neighbours are kept apart above this novelty
SEC_FOUR_ON_FLOOR = 0.65        # min/max beat-position kick ratio for the energy-role vocabulary

SECTION_COLORS = {
    "INTRO": "#f59e0b", "OUTRO": "#a855f7", "BREAKDOWN": "#10b981", "BUILDUP": "#f97316",
    "DROP": "#f43f5e", "GROOVE": "#0ea5e9", "VERSE": "#38bdf8", "PRECHORUS": "#fb923c",
    "CHORUS": "#e11d48", "BRIDGE": "#6366f1", "CLIP": "#64748b",
}
SECTION_NAMES = {
    "INTRO": "Intro", "OUTRO": "Outro", "BREAKDOWN": "Breakdown", "BUILDUP": "Buildup",
    "DROP": "Drop", "GROOVE": "Groove", "VERSE": "Verse", "PRECHORUS": "Pre-Chorus",
    "CHORUS": "Chorus", "BRIDGE": "Bridge", "CLIP": "Clip",
}


def _maxf(e: np.ndarray, r: int) -> np.ndarray:
    """Running max over +-r frames (+-17 ms at r = 3): low-band flux peaks lag the beat grid."""
    out = e.copy()
    for k in range(1, r + 1):
        out = np.maximum(out, np.maximum(np.roll(e, k), np.roll(e, -k)))
    return out


def theil_sen(x, y):
    """
    Theil-Sen line fit: slope = median of all pairwise slopes, intercept = median of
    y - slope * x. Breakdown point 29 %: up to that share of points can be anywhere
    without moving the line (a least-squares fit follows them).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2:
        raise ValueError("theil_sen needs at least 2 points")
    if len(x) > GRID_FIT_MAX_POINTS:          # O(n^2) pairs: thin evenly, deterministic
        keep = np.unique(np.round(np.linspace(0, len(x) - 1, GRID_FIT_MAX_POINTS)).astype(int))
        x, y = x[keep], y[keep]
    i, j = np.triu_indices(len(x), 1)
    dx = x[j] - x[i]
    ok = dx != 0
    slope = float(np.median((y[j] - y[i])[ok] / dx[ok]))
    return slope, float(np.median(y - slope * x))


# Beat grid fit (3.3): the grid used to be ph + k * tau from the detected BPM alone, so a
# BPM error grew along the track (0.1 BPM at 128 BPM is ~0.2 s after 5 min). The grid is
# now fitted to the beat onsets themselves. Validated in bench/validate_bar_grid.py.
GRID_FIT_WINDOWS = (0.30, 0.20, 0.12)   # onset search half-window around the grid, in beats
GRID_FIT_MIN_BEATS = 8                  # fewer matched onsets: keep the unfitted grid
GRID_FIT_MAX_DEV = 0.02                 # a fitted period more than 2 % from the tempo is rejected
GRID_FIT_REL_STRENGTH = 0.3             # an onset counts if >= 30 % of the median strong onset
GRID_FIT_MAX_POINTS = 1500
DOWNBEAT_BACKBEAT_RATIO = 1.5           # snare on both beats of a pair >= 1.5x the other pair = backbeat


def _fit_beat_grid(E: np.ndarray, ph: float, tau: float, method: str = "theil_sen"):
    """
    Beat grid (frames) as offset + k * period. method "none" = the old fixed grid,
    "lsq" = least squares, "theil_sen" = robust fit. Returns (beats, period, info).
    """
    n = len(E)
    info = {"method": method, "fitted": False, "matched": 0}
    if method == "none":
        return np.arange(ph, n - 1, tau), tau, info
    offset, period = ph, tau
    for win in GRID_FIT_WINDOWS:
        k0 = int(np.ceil(-offset / period))
        ks = np.arange(k0, int(np.floor((n - 2 - offset) / period)) + 1)
        pred = offset + ks * period
        hw = max(1, int(round(win * period)))
        idx, t, val = [], [], []
        for k, p in zip(ks, pred):
            c = int(round(p))
            a, b = max(1, c - hw), min(n - 1, c + hw + 1)
            if b - a < 3:
                continue
            m = a + int(np.argmax(E[a:b]))
            if m <= a or m >= b - 1:          # edge of the window: not a peak of its own
                continue
            y0, y1, y2 = E[m - 1], E[m], E[m + 1]
            den = y0 - 2.0 * y1 + y2
            frac = 0.5 * (y0 - y2) / den if den < 0 else 0.0   # parabolic sub-frame peak
            idx.append(k)
            t.append(m + float(np.clip(frac, -0.5, 0.5)))
            val.append(y1)
        if len(val) < GRID_FIT_MIN_BEATS:
            return np.arange(ph, n - 1, tau), tau, info
        val = np.asarray(val)
        strong = val >= GRID_FIT_REL_STRENGTH * np.median(val[val >= np.median(val)])
        if strong.sum() < GRID_FIT_MIN_BEATS:
            return np.arange(ph, n - 1, tau), tau, info
        kx, ty = np.asarray(idx, float)[strong], np.asarray(t)[strong]
        if method == "lsq":
            s, c = np.polyfit(kx, ty, 1)
        else:
            s, c = theil_sen(kx, ty)
        if abs(s / tau - 1.0) > GRID_FIT_MAX_DEV:
            return np.arange(ph, n - 1, tau), tau, info
        period, offset = float(s), float(c)
        info["matched"] = int(strong.sum())
    info["fitted"] = True
    k0 = int(np.ceil(-offset / period))
    ks = np.arange(k0, int(np.floor((n - 2 - offset) / period)) + 1)
    return offset + ks * period, period, info


def detect_bar_grid(mono: np.ndarray, sr: int, bpm: float, fit: str = "theil_sen", return_info: bool = False):
    """
    Downbeat times (s). Beat phase from drum onsets; downbeat = the beat of the 4 where
    spectral change and low-end onsets concentrate (sections and chords change on the one).
    The grid is anchored to the music, not to t = 0 (a pickup no longer shifts every boundary),
    and fitted to the beat onsets (fit="theil_sen"; "lsq" and "none" are kept for the bench).
    """
    B, fps = _onset_bands(mono, sr)
    tau = 60.0 * fps / bpm
    _, ph = _beat_offbeat(B, tau)
    n = B.shape[1]
    E = B[0] + B[1] + B[2]
    beats, period, info = _fit_beat_grid(E, ph, tau, fit)
    f, _, Z = signal.stft(mono, sr, nperseg=4096, noverlap=4096 - 256, boundary=None, padded=False)
    M = np.log1p(100.0 * np.abs(Z))
    bi = np.clip(np.round(beats).astype(int), 0, M.shape[1] - 1)
    w = max(1, int(tau // 2))
    ch = np.zeros(len(bi))
    for j, c in enumerate(bi):
        a = M[:, max(0, c - w):c].mean(axis=1) if c > 0 else M[:, 0]
        b = M[:, c:min(M.shape[1], c + w)].mean(axis=1)
        ch[j] = np.linalg.norm(b - a)
    low = B[0] + 0.5 * B[1]
    lowb = low[np.clip(np.round(beats).astype(int), 0, n - 1)]
    sc = [ch[o::4].mean() / (ch.mean() + 1e-9) + 0.5 * lowb[o::4].mean() / (lowb.mean() + 1e-9) for o in range(4)]
    # Backbeat (3.3, DEV note 34): a snare on 2 and 4 is a broadband change too, so the
    # score above often put the one on the snare. When both beats of one pair (o, o+2)
    # carry clearly more snare-band onset than the other pair, that pair is the backbeat
    # and the one is chosen from the other pair only. One strong snare beat (half-time:
    # snare on 3) is not a backbeat pair and leaves the choice open.
    sn = _maxf(B[2], 2)[np.clip(np.round(beats).astype(int), 0, n - 1)]
    s4 = np.array([sn[o::4].mean() if len(sn[o::4]) else 0.0 for o in range(4)])
    pair = [min(s4[0], s4[2]), min(s4[1], s4[3])]
    other = [max(s4[1], s4[3]), max(s4[0], s4[2])]
    cand = [0, 1, 2, 3]
    info["backbeat"] = None
    for pb in (0, 1):
        if pair[pb] >= DOWNBEAT_BACKBEAT_RATIO * other[pb] and pair[pb] > 0:
            cand = [1 - pb, 3 - pb]
            info["backbeat"] = [pb, pb + 2]            # grid offsets of the snare pair
    best = max(cand, key=lambda o: sc[o])
    lat = onset_latency_s(sr)                  # 3.2 grids were ~40 ms early (DEV note 33)
    down = beats[best::4] / fps + lat
    bar_s = 4.0 * period / fps
    while len(down) and down[0] > 0.05 and down[0] - bar_s > -0.5 * bar_s:
        down = np.concatenate([[down[0] - bar_s], down])
    if return_info:
        info["beat_period_s"] = period / fps
        return down, bar_s, info
    return down, bar_s


def _bar_features(mono: np.ndarray, sr: int, down: np.ndarray) -> list:
    f, _, Z = signal.stft(mono, sr, nperseg=4096, noverlap=4096 - 1024, boundary=None, padded=False)
    P = np.abs(Z) ** 2
    hop_t = 1024.0 / sr
    B, fps = _onset_bands(mono, sr)
    valid = (f >= 65.0) & (f <= 2000.0)
    pc = (np.round(12.0 * np.log2(np.maximum(f[valid], 1.0) / 440.0) + 69.0).astype(int)) % 12
    sub_m = (f >= 20.0) & (f < 100.0)
    # Bar features stay on the onset-frame clock the section thresholds were set on (3.2):
    # down is in real time (DEV note 33), so step back by the onset latency here. Measuring
    # band energies 40 ms later lost boundaries on the held-out section set (DEV note 35).
    lat = onset_latency_s(sr)
    edges = [max(0.0, t - lat) for t in down] + [len(mono) / sr]
    feats = []
    for i in range(len(edges) - 1):
        a, b = max(0.0, edges[i]), edges[i + 1]
        fa = min(int(a / hop_t), P.shape[1] - 1)
        fb = min(max(fa + 1, int(b / hop_t)), P.shape[1])
        Pb = P[:, fa:fb].mean(axis=1)
        band_e = [10.0 * np.log10(Pb[(f >= lo) & (f < hi)].sum() + 1e-12) for lo, hi in SEC_FEAT_BANDS]
        oa = min(int(a * fps), B.shape[1] - 1)
        ob = min(max(oa + 1, int(b * fps)), B.shape[1])
        dens = [float(B[k, oa:ob].mean()) for k in range(4)]
        ch = np.zeros(12)
        np.add.at(ch, pc, Pb[valid])
        ch = ch / (np.linalg.norm(ch) + 1e-12)
        sub_frames = P[sub_m, fa:fb].sum(axis=0)
        sub_floor = 10.0 * np.log10(np.percentile(sub_frames, 20) + 1e-12) if sub_frames.size else -120.0
        feats.append(dict(band=np.array(band_e), dens=np.array(dens), chroma=ch,
                          rms=10.0 * np.log10(Pb.sum() + 1e-12), sub_floor=float(sub_floor)))
    return feats


def _bar_novelty(feats: list, half: int = 4) -> np.ndarray:
    """Max of (a) Foote checkerboard novelty on the bar self-similarity matrix and (b) block
    novelty: mean features of the 4 bars before vs after each bar line (a chord loop averages
    out inside a section, so only a change of section remains). Both symmetric: no time shift."""
    z = lambda X: (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-6)
    X = np.hstack([z(np.array([f["band"] for f in feats])),
                   SEC_DENSITY_WEIGHT * z(np.array([f["dens"] for f in feats])),
                   np.array([f["chroma"] for f in feats]) * np.sqrt(12.0)])
    n = len(X)
    d = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    S = np.exp(-(d / (np.median(d) + 1e-9)) ** 2)
    k = half
    g = np.exp(-0.5 * ((np.arange(-k, k) + 0.5) / (k / 2.0)) ** 2)
    sg = np.sign(np.arange(-k, k) + 0.5)
    K = np.outer(g, g) * np.outer(sg, sg)
    Sp = np.pad(S, k, mode="edge")
    nov = np.zeros(n + 1)
    blk = np.zeros(n + 1)
    for i in range(1, n):
        nov[i] = (Sp[i:i + 2 * k, i:i + 2 * k] * K).sum()
        blk[i] = np.linalg.norm(X[i:min(n, i + 4)].mean(axis=0) - X[max(0, i - 4):i].mean(axis=0))
    # Normalise on interior bar lines only. The last bar is usually partial (the file ends
    # mid-bar) and the edges are padding: neither is a section change and neither may set
    # the scale of the curve.
    nov = np.maximum(nov, 0.0)
    nov = nov / (nov.max() + 1e-12)
    blk = blk / (blk.max() + 1e-12)
    return np.maximum(nov, blk)


SEC_MIN_CHANGE_DB = 1.5         # absolute gate: some band must change by this much ...
SEC_MIN_DENSITY_CHANGE = 0.25   # ... or the onset density by 25 % ...
SEC_MIN_CHROMA_COS = 0.90       # ... or the harmony (4-bar chroma cosine below this)


def _real_change(feats: list, i: int, w: int = 4) -> bool:
    """The novelty curve is normalised to its own maximum, so in a static track noise looks
    like structure. Keep a boundary only if the music measurably changes across it."""
    a = feats[max(0, i - w):i]
    b = feats[i:i + w]
    if not a or not b:
        return False
    pw = lambda fs: 10.0 * np.log10(np.mean([10 ** (f["band"] / 10.0) for f in fs], axis=0))
    if np.max(np.abs(pw(b) - pw(a))) >= SEC_MIN_CHANGE_DB:
        return True
    da = np.mean([f["dens"] for f in a], axis=0)
    db = np.mean([f["dens"] for f in b], axis=0)
    if np.max(np.abs(db - da) / (np.maximum(da, db) + 1e-9)) >= SEC_MIN_DENSITY_CHANGE:
        return True
    ca = np.mean([f["chroma"] for f in a], axis=0)
    cb = np.mean([f["chroma"] for f in b], axis=0)
    return float(np.dot(ca, cb) / (np.linalg.norm(ca) * np.linalg.norm(cb) + 1e-12)) < SEC_MIN_CHROMA_COS


def _pick_boundaries(nov: np.ndarray, feats: list) -> list:
    n = len(nov) - 1
    pk, _ = signal.find_peaks(nov[:n], prominence=SEC_NOVELTY_PROMINENCE)
    chosen = []
    for i in sorted(pk, key=lambda i: -nov[i]):
        if 2 <= i <= n - 2 and all(abs(i - c) >= SEC_MIN_BARS for c in chosen) and _real_change(feats, i):
            chosen.append(int(i))
    # breakdown edges measured directly: >= SEC_RUN_BARS bars with the low end SEC_RUN_DB
    # below the track median (replaces a novelty boundary within 2 bars)
    low = np.array([f["band"][0] for f in feats])
    dip = low < float(np.median(low)) - SEC_RUN_DB
    edges = []
    i = 0
    while i < len(dip):
        if dip[i]:
            j = i
            while j < len(dip) and dip[j]:
                j += 1
            if j - i >= SEC_RUN_BARS:
                edges += [e for e in (i, j) if 0 < e < len(dip)]
            i = j
        else:
            i += 1
    out = [b for b in chosen if all(abs(b - e) > 2 for e in edges)] + edges
    return sorted(set(out))



def _section_evidence(feats: list, starts_idx: list) -> list:
    rms = np.array([f["rms"] for f in feats])
    bounds = list(starts_idx) + [len(feats)]
    ev = []
    for s in range(len(bounds) - 1):
        a, b = bounds[s], bounds[s + 1]
        r = rms[a:b]
        k = len(r)
        ev.append(dict(
            bars=(a, b),
            level=float(10 * np.log10(np.mean(10 ** (r / 10)))),
            sub=float(10 * np.log10(np.mean([10 ** (feats[j]["sub_floor"] / 10) for j in range(a, b)]))),
            low=float(10 * np.log10(np.mean([10 ** (feats[j]["band"][0] / 10) for j in range(a, b)]))),
            rise=float(np.polyfit(np.arange(k), r, 1)[0] * (k - 1)) if k >= 3 else 0.0,
            chroma=np.mean([feats[j]["chroma"] for j in range(a, b)], axis=0),
            band=np.mean([feats[j]["band"] for j in range(a, b)], axis=0),
        ))
    top = max(e["level"] for e in ev)
    top_sub = max(e["sub"] for e in ev)
    wts = np.array([e["bars"][1] - e["bars"][0] for e in ev], dtype=float)
    lows = np.array([e["low"] for e in ev])
    o = np.argsort(lows)
    cw = np.cumsum(wts[o])
    low_med = float(lows[o][min(len(o) - 1, int(np.searchsorted(cw, 0.5 * cw[-1])))])
    for e in ev:
        e["level_vs_top"] = e["level"] - top
        e["sub_vs_top"] = e["sub"] - top_sub          # sustained low end between kicks = bass
        e["low_vs_median"] = e["low"] - low_med       # whole low end (kick + bass), 20-100 Hz
        e["has_bass"] = e["sub_vs_top"] >= -12.0
    return ev


def _label_energy_roles(ev: list) -> list:
    tags = []
    n = len(ev)
    for i, e in enumerate(ev):
        nxt = ev[i + 1] if i + 1 < n else None
        prev_tag = tags[-1] if tags else None
        rising = e["rise"] >= 3.0 and (nxt is None or nxt["level"] > e["level"])
        no_low = e["low_vs_median"] < -SEC_LOW_DROP_DB
        weak = (not e["has_bass"]) or e["level_vs_top"] < -4.0
        if i == 0 and (no_low or weak):
            t = "INTRO"
        elif i == n - 1 and (no_low or weak or e["rise"] <= -3.0):
            t = "OUTRO"
        elif no_low:
            t = "BUILDUP" if rising else "BREAKDOWN"
        elif rising and nxt is not None and nxt["level"] - e["level"] >= 2.0:
            t = "BUILDUP"
        elif e["has_bass"] and e["level_vs_top"] >= -2.0 and prev_tag in ("BREAKDOWN", "BUILDUP"):
            t = "DROP"
        elif e["has_bass"] and e["level_vs_top"] >= -1.0 and prev_tag == "DROP":
            t = "DROP"
        else:
            t = "GROOVE"
        tags.append(t)
    return tags


def _section_similarity(a: dict, b: dict):
    c = float(np.dot(a["chroma"], b["chroma"]) / (np.linalg.norm(a["chroma"]) * np.linalg.norm(b["chroma"]) + 1e-12))
    d = float(np.sqrt(np.mean((a["band"] - b["band"]) ** 2)))
    return c, d


def _label_song(ev: list):
    """Repetition-based song roles. Returns (tags, cluster ids); tags is None when no
    repeated chorus is measured (then verse/chorus names would be guesses)."""
    from collections import Counter
    n = len(ev)
    cl = [-1] * n
    c_id = 0
    for i in range(n):
        if cl[i] >= 0:
            continue
        cl[i] = c_id
        for j in range(i + 1, n):
            if cl[j] < 0:
                c, d = _section_similarity(ev[i], ev[j])
                if c >= 0.97 and d <= 2.5:     # same harmony AND same instrumentation
                    cl[j] = c_id
        c_id += 1
    groups = {}
    for i, c in enumerate(cl):
        groups.setdefault(c, []).append(i)
    rep = {c: m for c, m in groups.items() if len(m) >= 2}
    if not rep:
        return None, cl
    nbars = lambda i: ev[i]["bars"][1] - ev[i]["bars"][0]
    R = set(rep)
    pre, chorus, verse = [], None, None
    # pre-chorus: a repeated cluster mostly sandwiched V -> P -> Q, not longer than Q
    for c in rep:
        nq = Counter(cl[i + 1] if i + 1 < n else None for i in rep[c]).most_common(1)[0]
        pv = Counter(cl[i - 1] if i > 0 else None for i in rep[c]).most_common(1)[0]
        need = max(2, int(np.ceil(0.6 * len(rep[c]))))
        if nq[1] >= need and pv[1] >= need:
            q, v = nq[0], pv[0]
            if q in rep and v in rep and len({q, v, c}) == 3 and \
                    np.mean([nbars(i) for i in rep[c]]) <= np.mean([nbars(i) for i in rep[q]]):
                pre, chorus = [c], q
                break
    if chorus is None:
        # chorus = end of the repeated chain: more often preceded than followed by other
        # repeated sections; ties -> louder
        def score(c):
            p = sum(1 for i in rep[c] if i > 0 and cl[i - 1] in R and cl[i - 1] != c)
            f_ = sum(1 for i in rep[c] if i + 1 < n and cl[i + 1] in R and cl[i + 1] != c)
            return (p - f_, np.mean([ev[i]["level"] for i in rep[c]]))
        chorus = max(rep, key=score)
    others = [c for c in rep if c != chorus and c not in pre]
    if others:
        verse = max(others, key=lambda c: sum(nbars(i) for i in rep[c]))
    tags = [None] * n
    for i in range(n):
        tags[i] = "PRECHORUS" if cl[i] in pre else "CHORUS" if cl[i] == chorus else "VERSE" if cl[i] == verse else None
    for i in range(n):
        if tags[i]:
            continue
        if i == 0:
            tags[i] = "INTRO"
        elif i == n - 1:
            tags[i] = "OUTRO"
        elif i + 1 < n and tags[i + 1] == "CHORUS" and nbars(i) <= 8 and tags[i - 1] in ("VERSE", "INTRO"):
            tags[i] = "PRECHORUS"
        elif i >= n / 2:
            tags[i] = "BRIDGE"      # a non-repeated section in the second half
        else:
            tags[i] = "VERSE"
    return tags, cl


def _four_on_floor(mono: np.ndarray, sr: int, bpm: float, down: np.ndarray, ev: list) -> float:
    """min/max of the mean low-band onset over the 4 beat positions (outside breakdowns)."""
    B, fps = _onset_bands(mono, sr)
    tau = 60.0 * fps / bpm
    n = B.shape[1]
    lowm = _maxf(B[0], 3)
    q = np.zeros(4)
    for e in ev:
        if e["low_vs_median"] < -SEC_LOW_DROP_DB:
            continue
        for i in range(*e["bars"]):
            for k in range(4):
                p = (down[i] - onset_latency_s(sr)) * fps + k * tau
                if p < n - 1:
                    q[k] += lowm[int(round(p))]
    return float(q.min() / q.max()) if q.max() > 0 else 0.0


def detect_sections(mono: np.ndarray, sr: int, bpm: float, vocabulary: str = "auto") -> dict:
    """
    Section boundaries (s) and labels with the evidence behind them.
    vocabulary: "auto" | "energy" (intro/groove/breakdown/buildup/drop/outro) | "song".
    """
    dur = len(mono) / sr
    bar_s = 4.0 * 60.0 / bpm
    if dur < SEC_MIN_TRACK_BARS * bar_s:
        return {"sections": [{"t0": 0.0, "t1": round(dur, 3), "tag": "CLIP", "bars": int(round(dur / bar_s)),
                              "boundary_strength": 1.0, "evidence": {}}],
                "vocabulary": "none", "vocabulary_note": f"shorter than {SEC_MIN_TRACK_BARS} bars: not segmented",
                "four_on_floor": 0.0, "first_downbeat_s": 0.0, "bar_s": bar_s}
    down, bar_s = detect_bar_grid(mono, sr, bpm)
    feats = _bar_features(mono, sr, down)
    nov = _bar_novelty(feats)
    bidx = _pick_boundaries(nov, feats)
    sidx = [0] + bidx
    ev = _section_evidence(feats, sidx)
    fotf = _four_on_floor(mono, sr, bpm, down, ev)
    song_tags, cl = _label_song(ev)
    if vocabulary == "auto":
        vocab = "energy" if fotf >= SEC_FOUR_ON_FLOOR else "song"
    else:
        vocab = vocabulary
    note = None
    if vocab == "song" and (song_tags is None or "CHORUS" not in song_tags):
        vocab = "energy"
        note = "no repeated chorus measured: energy roles instead of verse/chorus names"
    tags = song_tags if vocab == "song" else _label_energy_roles(ev)
    keep = [0]
    for i in range(1, len(tags)):
        strong = nov[sidx[i]] >= SEC_MERGE_NOVELTY
        same = (not strong) and tags[i] == tags[keep[-1]] and (vocab != "song" or cl[i] == cl[keep[-1]])
        if not same:
            keep.append(i)
    dur = len(mono) / sr
    out = []
    for k_i, k in enumerate(keep):
        a = sidx[k]
        b = sidx[keep[k_i + 1]] if k_i + 1 < len(keep) else len(feats)
        e_list = ev[k:(keep[k_i + 1] if k_i + 1 < len(keep) else len(ev))]
        t0 = 0.0 if k == 0 else float(down[a])
        t1 = float(down[b]) if b < len(down) else dur
        strength = 1.0 if k == 0 else float(nov[a])
        lvl = float(10 * np.log10(np.mean([10 ** (e["level"] / 10) for e in e_list])))
        out.append({
            "t0": round(t0, 3), "t1": round(min(t1, dur), 3), "tag": tags[k], "bars": int(b - a),
            "boundary_strength": round(min(1.0, strength), 2),
            "evidence": {
                "level_vs_loudest_db": round(lvl - max(e["level"] for e in ev), 1),
                "low_end_vs_median_db": round(float(np.mean([e["low_vs_median"] for e in e_list])), 1),
                "bass_present": bool(any(e["has_bass"] for e in e_list)),
                "level_rise_db": round(float(sum(e["rise"] for e in e_list)), 1),
                "repeat_group": (int(cl[k]) if vocab == "song" else None),
            },
        })
    return {"sections": out, "vocabulary": vocab, "vocabulary_note": note,
            "four_on_floor": round(fotf, 3), "first_downbeat_s": round(float(down[0]) if len(down) else 0.0, 3),
            "bar_s": bar_s}


# ---------------------------------------------------------------------------
# Kick onsets (3.2). The 3.1 counter took peaks of the |<100 Hz| envelope 0.2 s apart:
# bass notes counted as kicks and the time was the envelope peak, not the attack.
# Ground truth (bench/validate_kicks.py): 3.1 F 0.16 with 2.25x the true count;
# this F 0.98 (count x1.03), held-out F 0.99. Real music, against kicks of the isolated
# drum stem (3 stem sets): F 0.70 / 0.54 / 0.36 vs 3.1 0.04 / 0.38 / 0.36 (+-60 ms).
# In a dense full mix the count is an estimate; the UI says so.
# ---------------------------------------------------------------------------
KICK_BAND_HZ = (40.0, 200.0)
KICK_RISE_DB = 8.0          # level rise within 20 ms
KICK_LEVEL_FLOOR_DB = 15.0  # the rise must reach within this of the loud low end (95th pct)
KICK_CLUSTER_S = 0.15       # one kick can show two rises (sweep beating with the bass note)


def detect_kick_onsets(mono: np.ndarray, sr: int) -> np.ndarray:
    """Kick attack times (samples) from the 40-200 Hz level: an 8 dB rise within 20 ms that
    reaches the loud part of the low end; the onset is where the level first gets within
    10 dB of the attack peak (zero-phase filtering pre-rings, so 'first rise' is too early)."""
    mono = np.asarray(mono, dtype=float)
    if len(mono) < int(0.5 * sr):
        return np.array([], dtype=int)
    sos = signal.butter(4, [KICK_BAND_HZ[0] / (sr / 2), KICK_BAND_HZ[1] / (sr / 2)], btype="band", output="sos")
    y = signal.sosfiltfilt(sos, mono)
    hop = max(1, int(round(0.002 * sr)))
    win = max(1, int(round(0.010 * sr)))
    L = 10.0 * np.log10(np.convolve(y * y, np.ones(win) / win, mode="same")[::hop] + 1e-12)
    fps = sr / hop
    k = max(1, int(round(0.020 * fps)))
    rise = np.zeros_like(L)
    rise[k:] = L[k:] - L[:-k]
    loud = float(np.percentile(L, 95))
    pk, _ = signal.find_peaks(rise, height=KICK_RISE_DB)
    pk = [p for p in pk if L[min(len(L) - 1, p + int(0.02 * fps))] >= loud - KICK_LEVEL_FLOOR_DB]
    out = []
    start = None
    for p in pk:
        if start is not None and p - start <= int(KICK_CLUSTER_S * fps):
            continue
        start = p
        top = p + int(np.argmax(L[p:p + int(0.04 * fps)])) if p + 2 < len(L) else p
        s0 = max(0, p - k)
        seg = L[s0:top + 1]
        on = s0 + int(np.argmax(seg >= L[top] - 10.0))
        out.append(int(round(on * hop)))
    return np.array(out, dtype=int)


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

    # Kick onsets. Given by the caller (stems mode) -> "drum_stem"; else measured on the
    # separate drum signal if there is one, otherwise estimated from the full mix.
    if kick_peaks is not None and len(kick_peaks) > 0:
        kicks_source = "drum_stem"
    else:
        kicks_source = "drum_stem" if kick_bass_separate else "mix_estimate"
        kick_peaks = detect_kick_onsets(sub_drums if kick_bass_separate else mix_mono, sr)

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

    vocab_req = {"electronic": "energy", "ambient": "energy", "pop_rock": "song"}.get(target_mode, "auto")         if genre_mode != "auto" else "auto"
    seg = detect_sections(mix_mono, sr, grid_bpm, vocabulary=vocab_req)
    if genre_mode == "auto" and seg["vocabulary"] != "none":
        # One measurement decides both the genre family and the section vocabulary: the
        # low-end onset evenness over the 4 beat positions (four-on-the-floor). The 3.1 rule
        # used the kick COUNT, which a sustained bass under the kick can hide.
        fotf = seg["four_on_floor"]
        if fotf >= SEC_FOUR_ON_FLOOR and cat != "electronic":
            cat, genre_label = "electronic", "Electronic / Techno / Club"
            conf = float(np.clip(0.70 + 0.30 * fotf, 0.70, 0.99))
        elif fotf < SEC_FOUR_ON_FLOOR and cat == "electronic":
            cat, genre_label = "pop_rock", "Pop / Rock / Song"
            conf = float(np.clip(0.75 + 0.20 * (1.0 - fotf), 0.70, 0.95))
        desc = dict(desc, four_on_floor_beat_evenness=round(fotf, 3))
        target_mode = cat
    sections = []
    counters = {}
    for sd in seg["sections"]:
        t0, t1 = sd["t0"], sd["t1"]
        tag = sd["tag"]
        counters[tag] = counters.get(tag, 0) + 1
        s_idx = int(t0 * sr)
        e_idx = min(len(mix_mono), int(t1 * sr))
        sec_dur = t1 - t0
        seg_mix = mix_mono[s_idx:e_idx]
        seg_sd = sub_drums[s_idx:e_idx]
        seg_sb = sub_bass[s_idx:e_idx]
        r_mix = float(20.0 * np.log10(np.sqrt(np.mean(seg_mix**2) + 1e-12)))
        r_sd = float(20.0 * np.log10(np.sqrt(np.mean(seg_sd**2) + 1e-12)))
        r_sb = float(20.0 * np.log10(np.sqrt(np.mean(seg_sb**2) + 1e-12)))
        pk_mix = float(20.0 * np.log10(np.max(np.abs(seg_mix)) + 1e-12)) if len(seg_mix) else -120.0
        k_in_sec = [int(k) for k in kick_peaks if s_idx <= k < e_idx]
        corr = (float(np.corrcoef(seg_sd, seg_sb)[0, 1]) if (len(seg_sd) > 0 and r_sd > -60.0 and r_sb > -60.0) else 0.0) if kick_bass_separate else None
        sections.append({
            "sec_type": f"{SECTION_NAMES.get(tag, tag.title())} {counters[tag]}", "sec_tag": tag,
            "sec_color": SECTION_COLORS.get(tag, "#38bdf8"),
            "t0": t0, "t1": t1, "sec_dur": sec_dur, "bars_count": sd["bars"],
            "s_idx": s_idx, "e_idx": e_idx, "r_mix": r_mix, "r_sd": r_sd, "r_sb": r_sb,
            "pk_mix": pk_mix, "crest_factor": float(pk_mix - r_mix), "corr": corr,
            "k_in_sec": k_in_sec, "k_count": len(k_in_sec), "k_density": float(len(k_in_sec) / max(1.0, sec_dur)),
            "boundary_strength": sd["boundary_strength"], "evidence": sd["evidence"],
        })
    # a single tag occurring once reads better without a number ("Intro", not "Intro 1")
    for sx in sections:
        if counters.get(sx["sec_tag"], 0) == 1:
            sx["sec_type"] = SECTION_NAMES.get(sx["sec_tag"], sx["sec_tag"].title())

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
            "boundary_strength": s["boundary_strength"],
            "evidence": s["evidence"],
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
        "kicks_source": kicks_source,
        "total_kick_events": len(kick_peaks),
        "num_sections": len(out_sections),
        "first_downbeat_s": seg["first_downbeat_s"],
        "genre": {
            "category": cat,
            "label": genre_label,
            "confidence": conf,
            "mode_applied": target_mode,
            "structure_vocabulary": seg["vocabulary"],
            "structure_note": seg["vocabulary_note"],
            "four_on_floor": seg["four_on_floor"],
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
