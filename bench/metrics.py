"""
PHARMAKON Objective Metrics Bench - metric definitions (pure NumPy / SciPy).

Every metric here maps a perceptual complaint ("metallic", "harsh", "fatiguing",
"dull", "squashed", "dirty") to a number, so DSP stages can be tuned against
measurable targets instead of by ear. Listening is the final blind validation.

Music metrics (computed on loudness-matched audio):
    resonance_*        narrow peaks in 2-8 kHz above the smoothed spectrum ("metallic / AI whistle")
    band_*_db          1/3-octave-group tonal balance relative to total ("dull" vs "harsh")
    tilt_db_per_oct    fitted spectral slope 100 Hz - 16 kHz
    presence_flux_db   how spiky the 2-5 kHz share is over time (transient harshness)
    sharpness_acum     Zwicker/Fastl sharpness with DIN 45692 weighting (APPROXIMATE,
                       not an ISO 532-1 certified loudness model; calibrated to 1 acum
                       at the DIN reference point)
    crest_db, plr_db   dynamics (crest factor, peak-to-loudness ratio)
    lufs, true_peak_db loudness (ITU-R BS.1770-4 meter of remaster_engine) / 4x true peak
    side_ratio_db, corr  stereo width / phase correlation

Chain metrics (test tones pushed through a processing function):
    thd_1k_db          total harmonic distortion of a 1 kHz tone
    imd_smpte_db       SMPTE intermodulation (60 Hz + 7 kHz, 4:1)
    alias_db           non-harmonic (aliased) energy for a 9 kHz tone
"""
import os
import sys

import numpy as np
import scipy.signal as signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from remaster_engine import calc_integrated_lufs, ensure_stereo  # noqa: E402

FULL_SCALE_DB_SPL = 100.0  # assumed playback calibration: 0 dBFS sine RMS-equivalent ~ 100 dB SPL


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------

def _mono(audio):
    a = np.asarray(audio, dtype=np.float64)
    return a.mean(axis=1) if a.ndim == 2 else a


def _welch_db(x, sr, nperseg=8192):
    nperseg = min(nperseg, len(x))
    f, p = signal.welch(x, fs=sr, nperseg=nperseg, scaling="spectrum")
    return f, p


def match_loudness(audio, sr, target_lufs):
    """Constant gain so that integrated loudness equals target_lufs."""
    cur = calc_integrated_lufs(audio, sr)
    return np.asarray(audio, dtype=np.float64) * 10.0 ** ((target_lufs - cur) / 20.0)


def true_peak_db(audio):
    st = ensure_stereo(np.asarray(audio, dtype=np.float64))
    up = signal.resample_poly(st, 4, 1, axis=0)
    return float(20.0 * np.log10(max(1e-12, np.max(np.abs(up)))))


# -----------------------------------------------------------------------------
# 1. Resonances ("metallic", AI whistle)
# -----------------------------------------------------------------------------

def resonance_metrics(audio, sr, f_lo=2000.0, f_hi=8000.0, min_prom_db=3.0):
    """
    Narrow spectral peaks standing above a median-smoothed baseline.
    Baseline: running median over ~1/3 octave in the log-frequency domain.
    Returns the strongest prominence (dB), its frequency, and the number of
    peaks >= min_prom_db.
    """
    x = _mono(audio)
    f, p = _welch_db(x, sr, nperseg=8192)
    m = (f >= f_lo * 0.7) & (f <= min(f_hi * 1.3, sr * 0.49))
    f, pdb = f[m], 10.0 * np.log10(np.maximum(p[m], 1e-20))
    # resample onto a log-frequency grid (1/96 octave) so the baseline window is
    # a constant fraction of an octave
    grid = np.geomspace(f[0], f[-1], int(np.log2(f[-1] / f[0]) * 96))
    g_db = np.interp(grid, f, pdb)
    win = 33  # 33/96 octave ~ 1/3 octave
    base = signal.medfilt(g_db, win)
    prom_curve = g_db - base
    inside = (grid >= f_lo) & (grid <= f_hi)
    peaks, props = signal.find_peaks(np.where(inside, prom_curve, -99.0), prominence=1.0)
    if len(peaks) == 0:
        return {"resonance_max_db": 0.0, "resonance_hz": None, "resonance_count": 0}
    heights = prom_curve[peaks]
    best = int(np.argmax(heights))
    return {
        "resonance_max_db": round(float(max(0.0, heights[best])), 2),
        "resonance_hz": round(float(grid[peaks[best]]), 1),
        "resonance_count": int(np.sum(heights >= min_prom_db)),
    }


# -----------------------------------------------------------------------------
# 2. Tonal balance
# -----------------------------------------------------------------------------

BANDS = [
    ("sub", 20.0, 60.0),
    ("bass", 60.0, 250.0),
    ("low_mid", 250.0, 500.0),
    ("mid", 500.0, 2000.0),
    ("presence", 2000.0, 5000.0),
    ("brilliance", 5000.0, 10000.0),
    ("air", 10000.0, 20000.0),
]


def tonal_balance(audio, sr):
    """Band energy relative to total (dB) and fitted 1/3-octave spectral tilt (dB/oct)."""
    x = _mono(audio)
    f, p = _welch_db(x, sr, nperseg=8192)
    total = np.sum(p[(f >= 20.0) & (f <= min(20000.0, sr * 0.49))])
    out = {}
    for name, lo, hi in BANDS:
        hi = min(hi, sr * 0.49)
        e = np.sum(p[(f >= lo) & (f < hi)])
        out[f"band_{name}_db"] = round(float(10.0 * np.log10(max(e, 1e-20) / max(total, 1e-20))), 2)
    centers = 1000.0 * 2.0 ** (np.arange(-10, 5) / 3.0)  # ~100 Hz .. ~16 kHz
    centers = centers[centers < sr * 0.45]
    lv = []
    for c in centers:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        lv.append(10.0 * np.log10(max(np.sum(p[(f >= lo) & (f < hi)]), 1e-20)))
    slope = np.polyfit(np.log2(centers), np.array(lv), 1)[0]
    out["tilt_db_per_oct"] = round(float(slope), 2)
    return out


# -----------------------------------------------------------------------------
# 3. Transient harshness (presence flux)
# -----------------------------------------------------------------------------

def presence_flux(audio, sr, frame_s=0.05):
    """
    Spikiness of the 2-5 kHz share over time: 95th percentile minus median of the
    per-frame presence/full-band ratio (dB). High values = harsh bursts.
    """
    x = _mono(audio)
    sos = signal.butter(4, [2000.0, min(5000.0, sr * 0.45)], btype="band", fs=sr, output="sos")
    pres = signal.sosfiltfilt(sos, x)
    n = int(frame_s * sr)
    k = len(x) // n
    if k < 10:
        return {"presence_flux_db": 0.0}
    e_full = np.mean(x[: k * n].reshape(k, n) ** 2, axis=1)
    e_pres = np.mean(pres[: k * n].reshape(k, n) ** 2, axis=1)
    loud = e_full > np.max(e_full) * 1e-4  # ignore near-silent frames
    r = 10.0 * np.log10(np.maximum(e_pres[loud], 1e-20) / np.maximum(e_full[loud], 1e-20))
    return {"presence_flux_db": round(float(np.percentile(r, 95) - np.median(r)), 2)}


# -----------------------------------------------------------------------------
# 4. Sharpness (approximate Zwicker / Fastl, DIN 45692 weighting)
# -----------------------------------------------------------------------------

def _bark(f):
    return 13.0 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


def _threshold_quiet_db(f):
    f = np.maximum(f, 20.0) / 1000.0
    return 3.64 * f ** -0.8 - 6.5 * np.exp(-0.6 * (f - 3.3) ** 2) + 1e-3 * f ** 4  # Terhardt


def _specific_loudness(x, sr, dz=0.1):
    f, p = _welch_db(x, sr, nperseg=8192)
    keep = (f >= 20.0) & (f <= min(15500.0, sr * 0.49))
    f, p = f[keep], p[keep]
    # power spectrum -> dB SPL with 0 dBFS full-scale sine = FULL_SCALE_DB_SPL
    spl = 10.0 * np.log10(np.maximum(p / 0.5, 1e-20)) + FULL_SCALE_DB_SPL
    z_edges = np.arange(0.0, 24.0 + dz, dz)
    z_c = 0.5 * (z_edges[:-1] + z_edges[1:])
    zf = _bark(f)
    e_band = np.zeros(len(z_c))
    idx = np.clip(np.digitize(zf, z_edges) - 1, 0, len(z_c) - 1)
    np.add.at(e_band, idx, 10.0 ** (spl / 10.0))
    # excitation spreading (Terhardt slopes): lower side +27 dB/Bark,
    # upper side -(24 + 230/f - 0.2 L) dB/Bark
    f_c = np.interp(z_c, zf, f) if len(f) > 1 else np.full(len(z_c), 1000.0)
    lvl = 10.0 * np.log10(np.maximum(e_band, 1e-20))
    exc = np.zeros(len(z_c))
    for i in np.nonzero(e_band > 0)[0]:
        dzv = z_c - z_c[i]
        up = -(24.0 + 230.0 / max(f_c[i], 20.0) - 0.2 * lvl[i])
        att = np.where(dzv < 0, 27.0 * dzv, up * dzv)
        exc += 10.0 ** ((lvl[i] + np.minimum(att, 0.0)) / 10.0)
    e_tq = 10.0 ** (_threshold_quiet_db(f_c) / 10.0)
    n_spec = 0.08 * (e_tq / 1.0) ** 0.23 * ((0.5 + 0.5 * exc / e_tq) ** 0.23 - 1.0)
    return z_c, np.maximum(n_spec, 0.0), dz


def _sharpness_raw(x, sr):
    z, n, dz = _specific_loudness(x, sr)
    total = np.sum(n) * dz
    if total <= 1e-9:
        return 0.0
    g = np.where(z <= 15.8, 1.0, 0.15 * np.exp(0.42 * (z - 15.8)) + 0.85)
    return 0.11 * np.sum(n * g * z) * dz / total


_SHARPNESS_CAL = None


def _sharpness_calibration(sr=48000):
    """DIN 45692 reference: critical-band noise (920-1080 Hz) at 60 dB SPL = 1 acum."""
    global _SHARPNESS_CAL
    if _SHARPNESS_CAL is None:
        rng = np.random.default_rng(12345)
        noise = rng.standard_normal(sr * 4)
        sos = signal.butter(8, [920.0, 1080.0], btype="band", fs=sr, output="sos")
        ref = signal.sosfiltfilt(sos, noise)
        rms_target = 10.0 ** ((60.0 - FULL_SCALE_DB_SPL) / 20.0) / np.sqrt(2.0)
        ref *= rms_target / np.sqrt(np.mean(ref ** 2))
        _SHARPNESS_CAL = 1.0 / _sharpness_raw(ref, sr)
    return _SHARPNESS_CAL


def sharpness_acum(audio, sr):
    """Approximate sharpness in acum (see module docstring for the caveat)."""
    return round(float(_sharpness_raw(_mono(audio), sr) * _sharpness_calibration()), 3)


# -----------------------------------------------------------------------------
# 5. Dynamics, loudness, stereo
# -----------------------------------------------------------------------------

def dynamics_and_stereo(audio, sr):
    st = ensure_stereo(np.asarray(audio, dtype=np.float64))
    peak = float(np.max(np.abs(st)))
    rms = float(np.sqrt(np.mean(st ** 2)))
    lufs = calc_integrated_lufs(st, sr)
    tp = true_peak_db(st)
    mid = 0.5 * (st[:, 0] + st[:, 1])
    side = 0.5 * (st[:, 0] - st[:, 1])
    corr = float(np.sum(st[:, 0] * st[:, 1]) / max(1e-12, np.sqrt(np.sum(st[:, 0] ** 2) * np.sum(st[:, 1] ** 2))))
    return {
        "lufs": round(float(lufs), 2),
        "true_peak_db": round(tp, 2),
        "crest_db": round(float(20.0 * np.log10(max(peak, 1e-12) / max(rms, 1e-12))), 2),
        "plr_db": round(float(tp - lufs), 2),
        "side_ratio_db": round(float(10.0 * np.log10(max(np.mean(side ** 2), 1e-20) / max(np.mean(mid ** 2), 1e-20))), 2),
        "corr": round(corr, 3),
    }


def music_metrics(audio, sr):
    """All music metrics for one (already loudness-matched) signal."""
    out = {}
    out.update(dynamics_and_stereo(audio, sr))
    out.update(resonance_metrics(audio, sr))  # v1 (long-term peaks; also flags notes)
    from bench import resonance_v2  # v2: persistent envelope colouring, ignores notes
    r2 = resonance_v2.analyze(audio, sr)["resonances"]
    out["res_v2_max_db"] = r2[0]["prominence_db"] if r2 else 0.0
    out["res_v2_hz"] = r2[0]["hz"] if r2 else None
    out["res_v2_q"] = r2[0]["q_est"] if r2 else None
    out["res_v2_count"] = len(r2)
    out.update(tonal_balance(audio, sr))
    out.update(presence_flux(audio, sr))
    out["sharpness_acum"] = sharpness_acum(audio, sr)
    return out


# -----------------------------------------------------------------------------
# 6. Chain distortion metrics (test tones through a processing function)
# -----------------------------------------------------------------------------

def _tone(sr, freqs_amps, seconds=2.0):
    t = np.arange(int(seconds * sr)) / sr
    x = sum(a * np.sin(2.0 * np.pi * f * t) for f, a in freqs_amps)
    fade = int(0.02 * sr)
    ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, fade)))
    x[:fade] *= ramp
    x[-fade:] *= ramp[::-1]
    return np.column_stack([x, x])


def _spectrum(y, sr):
    y = _mono(y)
    y = y[len(y) // 4: -len(y) // 4]
    w = signal.windows.blackmanharris(len(y))
    s = np.abs(np.fft.rfft(y * w)) ** 2
    f = np.fft.rfftfreq(len(y), 1.0 / sr)
    return f, s


def _band_power(f, s, f0, half_bw=6.0):
    m = (f >= f0 - half_bw) & (f <= f0 + half_bw)
    return float(np.sum(s[m]))


def chain_metrics(process, sr=48000, level_dbfs=-6.0):
    """
    process: callable(stereo_float_array, sr) -> stereo array (the DSP chain or a stage).
    THD (1 kHz), SMPTE IMD (60 Hz + 7 kHz, 4:1), aliasing (9 kHz tone: energy not on
    harmonics of 9 kHz).
    """
    a = 10.0 ** (level_dbfs / 20.0)
    # THD
    y = process(_tone(sr, [(1000.0, a)]), sr)
    f, s = _spectrum(y, sr)
    fund = _band_power(f, s, 1000.0)
    harm = sum(_band_power(f, s, 1000.0 * k) for k in range(2, 10) if 1000.0 * k < sr * 0.49)
    thd = 10.0 * np.log10(max(harm, 1e-30) / max(fund, 1e-30))
    # SMPTE IMD
    y = process(_tone(sr, [(60.0, a * 0.8), (7000.0, a * 0.2)]), sr)
    f, s = _spectrum(y, sr)
    carrier = _band_power(f, s, 7000.0)
    side = sum(_band_power(f, s, 7000.0 + k * 60.0, 4.0) for k in (-3, -2, -1, 1, 2, 3))
    imd = 10.0 * np.log10(max(side, 1e-30) / max(carrier, 1e-30))
    # aliasing
    f0 = 9000.0
    y = process(_tone(sr, [(f0, a)]), sr)
    f, s = _spectrum(y, sr)
    fund = _band_power(f, s, f0)
    mask = (f > 200.0) & (f < sr * 0.49)
    for k in range(1, 10):
        if f0 * k < sr * 0.49:
            mask &= np.abs(f - f0 * k) > 12.0
    alias = 10.0 * np.log10(max(np.sum(s[mask]), 1e-30) / max(fund, 1e-30))
    return {"thd_1k_db": round(float(thd), 2), "imd_smpte_db": round(float(imd), 2), "alias_db": round(float(alias), 2)}
