"""
PHARMAKON 2.0 — Comprehensive DSP Core Audit & Regression Suite (pytest)
Covers:
1. WAV Export & Format Verification (P0-4)
2. 4X True-Peak Limiter & Chunk Spike Isolation (P0-2, P0-3)
3. Sub-Sync Phase Alignment & Crossover Integrity (P0-1)
4. Asymmetric Tape Saturation Harmonics, Aliasing & DC-Blocker (P1-1, P1-2)
5. Public Interfaces, Parameters, Presets & Bit-Identical DSP Regression
6. Long-File (>2 min) Streaming Chunk Boundaries & Crossfade Continuity
"""

import hashlib
import inspect
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy.signal as signal
import soundfile as sf

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import remaster_engine as re_eng

BASELINE_PATH = ROOT_DIR / "baseline.json"


@pytest.fixture(scope="module")
def baseline():
    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _measure_4x_true_peak_db(audio: np.ndarray) -> float:
    up = signal.resample_poly(audio.astype(np.float64), up=4, down=1, axis=0)
    peak = float(np.max(np.abs(up)))
    return float(20.0 * np.log10(max(1e-12, peak)))


def _band_rms_db(audio: np.ndarray, sr: int, f_lo: float, f_hi: float) -> float:
    nyq = 0.5 * sr
    b, a = signal.butter(4, [f_lo / nyq, min(f_hi, nyq - 20.0) / nyq], btype="band")
    filt = signal.filtfilt(b, a, audio.astype(np.float64), axis=0)
    rms = float(np.sqrt(np.mean(filt ** 2)))
    return float(20.0 * np.log10(max(1e-12, rms)))


# =============================================================================
# 1. WAV EXPORT & SUBTYPE VERIFICATION (P0-4)
# =============================================================================

def test_single_file_export_is_pcm24(tmp_path):
    """Master WAV and DELTA_POISON WAV from process_single_file must both be 24-bit PCM_24."""
    sr = 48000
    t = np.arange(sr * 2, dtype=np.float64) / sr
    src = np.column_stack([
        0.4 * np.sin(2 * np.pi * 110 * t) + 0.1 * np.sin(2 * np.pi * 5200 * t),
        0.4 * np.sin(2 * np.pi * 110 * t) + 0.1 * np.sin(2 * np.pi * 5200 * t),
    ]).astype(np.float32)

    in_wav = tmp_path / "test_track.wav"
    sf.write(in_wav, src, sr, subtype="PCM_24")

    out_file, metrics = re_eng.process_single_file(str(in_wav), open_folder=False)
    assert out_file is not None and os.path.isfile(out_file)
    assert sf.info(out_file).subtype == "PCM_24"
    assert sf.info(metrics["delta_path"]).subtype == "PCM_24"


def test_stems_folder_all_exports_are_pcm24(tmp_path):
    """Master WAV, RAW_SUM, and all 4 cleaned stems from process_stems_folder must be PCM_24."""
    sr = 48000
    t = np.arange(sr * 2, dtype=np.float64) / sr
    stems_dir = tmp_path / "SongStems"
    stems_dir.mkdir()

    sf.write(stems_dir / "drums.wav", np.column_stack([0.4 * np.sin(2 * np.pi * 55 * t)] * 2).astype(np.float32), sr, subtype="PCM_24")
    sf.write(stems_dir / "bass.wav", np.column_stack([0.35 * np.sin(2 * np.pi * 55 * t + 0.8)] * 2).astype(np.float32), sr, subtype="PCM_24")
    sf.write(stems_dir / "vocals.wav", np.column_stack([0.25 * np.sin(2 * np.pi * 440 * t)] * 2).astype(np.float32), sr, subtype="PCM_24")
    sf.write(stems_dir / "other.wav", np.column_stack([0.2 * np.sin(2 * np.pi * 330 * t)] * 2).astype(np.float32), sr, subtype="PCM_24")

    master_path, metrics = re_eng.process_stems_folder(str(stems_dir), open_folder=False)
    assert master_path is not None and os.path.isfile(master_path)

    rem_dir = Path(master_path).parent
    expected_files = [
        Path(master_path),
        Path(metrics["raw_sum_path"]),
        Path(metrics["delta_path"]),
        rem_dir / "SongStems - vocals_cleaned.wav",
        rem_dir / "SongStems - drums_punched.wav",
        rem_dir / "SongStems - bass_monofied.wav",
        rem_dir / "SongStems - other_widened.wav",
    ]
    for wav_p in expected_files:
        assert wav_p.is_file(), f"Missing output file: {wav_p}"
        assert sf.info(str(wav_p)).subtype == "PCM_24", f"{wav_p.name} has subtype {sf.info(str(wav_p)).subtype}, expected PCM_24"


def test_split_audio_to_stems_exports_pcm24(tmp_path):
    """Extracted stems in split_audio_to_stems must also be saved as 24-bit PCM_24."""
    sr = 48000
    t = np.arange(sr * 2, dtype=np.float64) / sr
    mix = np.column_stack([
        0.35 * np.sin(2 * np.pi * 60 * t) + 0.25 * np.sin(2 * np.pi * 660 * t),
        0.35 * np.sin(2 * np.pi * 60 * t) + 0.25 * np.sin(2 * np.pi * 660 * t + 0.3),
    ]).astype(np.float32)
    in_wav = tmp_path / "mix_src.wav"
    sf.write(in_wav, mix, sr, subtype="PCM_24")

    out_dir, info = re_eng.split_audio_to_stems(str(in_wav))
    for key in ("drums", "bass", "vocals", "other"):
        assert sf.info(info[key]).subtype == "PCM_24", f"Stem {key} subtype={sf.info(info[key]).subtype}"


# =============================================================================
# 2. LIMITER & 4X TRUE-PEAK COMPLIANCE + SPIKE ISOLATION (P0-2, P0-3)
# =============================================================================

def test_limiter_stress_noise_peak_1_5():
    """Stress signal: broadband noise with peak 1.5 -> 4X True-Peak <= ceiling + 0.05 dB."""
    sr = 48000
    rng = np.random.default_rng(42)
    noise = rng.standard_normal((sr * 3, 2))
    noise = (noise / np.max(np.abs(noise)) * 1.5).astype(np.float32)

    ceiling_db = -0.3
    out, reported_tp = re_eng.true_peak_limiter(noise, sr, target_ceiling_db=ceiling_db, oversample=4)
    measured_tp = _measure_4x_true_peak_db(out)
    assert measured_tp <= ceiling_db + 0.05, f"4X True-Peak {measured_tp:.3f} dBFS exceeded {ceiling_db + 0.05:.2f} dBFS"


def test_limiter_stress_multisine_peak_1_6():
    """Stress signal: sum of sines with peak 1.6 -> 4X True-Peak <= ceiling + 0.05 dB."""
    sr = 48000
    t = np.arange(sr * 3, dtype=np.float64) / sr
    s = (
        np.sin(2 * np.pi * 73 * t)
        + 0.8 * np.sin(2 * np.pi * 997 * t + 0.3)
        + 0.7 * np.sin(2 * np.pi * 4321 * t + 1.1)
        + 0.6 * np.sin(2 * np.pi * 11050 * t + 2.0)
    )
    s = s / np.max(np.abs(s)) * 1.6
    sig = np.column_stack([s, s]).astype(np.float32)

    ceiling_db = -0.3
    out, _ = re_eng.true_peak_limiter(sig, sr, target_ceiling_db=ceiling_db, oversample=4)
    measured_tp = _measure_4x_true_peak_db(out)
    assert measured_tp <= ceiling_db + 0.05, f"4X True-Peak {measured_tp:.3f} dBFS exceeded {ceiling_db + 0.05:.2f} dBFS"


def test_limiter_single_spike_does_not_distort_distant_sine_p0_2():
    """
    P0-2 Acceptance Test:
    10 s of 0.5 FS 1 kHz sine + one short spike above ceiling at t = 5.0 s
    (with steep HF burst triggering post-decimation safety guard).
    Residual error outside +-250 ms around the spike must remain below -80 dBFS.
    """
    sr = 48000
    n = sr * 10
    t = np.arange(n, dtype=np.float64) / sr
    clean_sine = 0.5 * np.sin(2 * np.pi * 1000.0 * t)
    sig = clean_sine.copy()

    # Short 2 ms high-amplitude transient burst at t = 5.0 s that triggers post-decimation overshoot
    spike_center = sr * 5
    burst_idx = np.arange(spike_center - 48, spike_center + 48)
    sig[burst_idx] += 1.6 * ((-1.0) ** np.arange(len(burst_idx)))

    stereo_in = np.column_stack([sig, sig]).astype(np.float32)
    stereo_ref = np.column_stack([clean_sine, clean_sine]).astype(np.float32)

    out, _ = re_eng.true_peak_limiter(stereo_in, sr, target_ceiling_db=-0.3, oversample=4)

    # Evaluate residual error outside +-250 ms around t=5.0s (exclude 50ms filter edges at 0s and 10s)
    guard = int(0.250 * sr)
    edge = int(0.050 * sr)
    far_mask = np.ones(n, dtype=bool)
    far_mask[:edge] = False
    far_mask[-edge:] = False
    far_mask[spike_center - guard : spike_center + guard] = False

    err = out[far_mask] - stereo_ref[far_mask]
    err_rms_db = float(20.0 * np.log10(max(1e-12, np.sqrt(np.mean(err.astype(np.float64) ** 2)))))
    assert err_rms_db < -80.0, (
        f"P0-2 defect confirmed: residual error outside +-250ms is {err_rms_db:.2f} dBFS "
        f"(>= -80 dBFS) due to global-chunk tanh safety guard"
    )


# =============================================================================
# 3. SUB-SYNC PHASE ALIGNMENT & CROSSOVER INTEGRITY (P0-1)
# =============================================================================

def test_sub_sync_synthetic_30_runs_p0_1_criteria():
    """
    P0-1 / P2 Synthetic Sub-Sync Audit (30 random phase/pitch seeds):
    - Kick: 50 Hz decaying pulse train (every 0.5 s)
    - Bass: fundamental 41-55 Hz + 2nd & 3rd harmonics (reaching 82-165 Hz across 100 Hz crossover)
    Criteria:
    - Sub-band sum (<100 Hz) energy change >= -0.1 dB on all 30 runs
    - Bass energy in 85-120 Hz change >= -1.0 dB on all 30 runs
    - Applied shift <= 3.0 ms
    """
    sr = 48000
    dur = 3.0
    n = int(sr * dur)
    t = np.arange(n, dtype=np.float64) / sr
    rng = np.random.default_rng(202611)

    nyq = 0.5 * sr
    b_sub100, a_sub100 = signal.butter(4, 100.0 / nyq, btype="low")

    worst_bass_85_120_drop = 0.0
    worst_subsum_drop = 0.0
    max_shift_ms = 0.0

    for _ in range(30):
        f_bass = float(rng.uniform(41.0, 55.0))
        phi1 = float(rng.uniform(0, 2 * np.pi))
        phi2 = float(rng.uniform(0, 2 * np.pi))
        phi3 = float(rng.uniform(0, 2 * np.pi))

        t_beat = np.mod(t, 0.5)
        kick_mono = 0.65 * np.sin(2 * np.pi * 50.0 * t_beat) * np.exp(-9.0 * t_beat)
        bass_mono = (
            0.45 * np.sin(2 * np.pi * f_bass * t + phi1)
            + 0.30 * np.sin(2 * np.pi * (2.0 * f_bass) * t + phi2)
            + 0.18 * np.sin(2 * np.pi * (3.0 * f_bass) * t + phi3)
        )

        drums = np.column_stack([kick_mono, kick_mono]).astype(np.float32)
        bass = np.column_stack([bass_mono, bass_mono]).astype(np.float32)

        aligned_bass, lag_samples, _ = re_eng.align_sub_phase(drums, bass, sr)
        shift_ms = abs(lag_samples) * 1000.0 / sr
        max_shift_ms = max(max_shift_ms, shift_ms)

        # Bass 85-120 Hz energy before vs after
        b85_orig = _band_rms_db(bass, sr, 85.0, 120.0)
        b85_proc = _band_rms_db(aligned_bass, sr, 85.0, 120.0)
        worst_bass_85_120_drop = min(worst_bass_85_120_drop, b85_proc - b85_orig)

        # Sub-sum (<100 Hz) kick + bass before vs after
        sum_orig_sub = signal.filtfilt(b_sub100, a_sub100, (drums + bass).astype(np.float64), axis=0)
        sum_proc_sub = signal.filtfilt(b_sub100, a_sub100, (drums + aligned_bass).astype(np.float64), axis=0)
        sub_gain_db = float(
            20.0 * np.log10(
                max(1e-12, np.sqrt(np.mean(sum_proc_sub ** 2)))
                / max(1e-12, np.sqrt(np.mean(sum_orig_sub ** 2)))
            )
        )
        worst_subsum_drop = min(worst_subsum_drop, sub_gain_db)

    assert worst_bass_85_120_drop >= -1.0, (
        f"P0-1 defect confirmed: bass 85-120 Hz dropped by {worst_bass_85_120_drop:.2f} dB (< -1.0 dB)"
    )
    assert worst_subsum_drop >= -0.1, (
        f"P0-1 defect confirmed: sub-sum <100 Hz dropped by {worst_subsum_drop:.2f} dB (< -0.1 dB)"
    )
    assert max_shift_ms <= 3.0, (
        f"P0-1 defect confirmed: max lag shift {max_shift_ms:.2f} ms exceeded 3.0 ms"
    )


def test_sub_sync_pure_antiphase_50hz_recovery():
    """Regression check for current align_sub_phase: 180-deg out-of-phase 50 Hz sine flips polarity."""
    sr = 48000
    t = np.arange(sr * 2, dtype=np.float64) / sr
    d = np.column_stack([0.5 * np.sin(2 * np.pi * 50.0 * t)] * 2).astype(np.float32)
    b = np.column_stack([-0.5 * np.sin(2 * np.pi * 50.0 * t)] * 2).astype(np.float32)

    aligned_b, lag, pol = re_eng.align_sub_phase(d, b, sr)
    rms_before = float(np.sqrt(np.mean((d + b) ** 2)))
    rms_after = float(np.sqrt(np.mean((d + aligned_b) ** 2)))
    assert pol == -1.0
    assert rms_after > rms_before * 5.0


# =============================================================================
# 4. TAPE SATURATION STAGE: HARMONICS, ALIASING & DC-BLOCKER (P1-1, P1-2)
# =============================================================================

def test_tape_stage_harmonics_5_levels_match_baseline(baseline):
    """
    P1-1 / P2: 1 kHz sine, 48 kHz, 3.0 s, Blackman-Harris window, +-3 bin peak search.
    Verifies H2 and H3 across 0, -3, -6, -12, -18 dBFS within +-0.2 dB of baseline.json,
    and confirms H2 > H3 at -18 dBFS while H3 > H2 at 0 dBFS.
    """
    sr = 48000
    n = sr * 3
    t = np.arange(n, dtype=np.float64) / sr
    win = signal.windows.blackmanharris(n)
    bin_hz = sr / n
    b1, b2, b3 = int(round(1000 / bin_hz)), int(round(2000 / bin_hz)), int(round(3000 / bin_hz))

    ref_levels = baseline["tape_stage_telemetry"]["levels"]
    measured = {}
    for lvl_db in [0.0, -3.0, -6.0, -12.0, -18.0]:
        amp = 10.0 ** (lvl_db / 20.0)
        x = (amp * np.sin(2 * np.pi * 1000.0 * t)).astype(np.float32)
        y = re_eng.apply_tape_warmth_v2(x, sr=sr, drive=1.05, bias=0.035, ceiling=0.98, oversample=4)
        spec = np.abs(np.fft.rfft(y.astype(np.float64) * win))
        m1 = float(np.max(spec[b1 - 3 : b1 + 4]))
        m2 = float(np.max(spec[b2 - 3 : b2 + 4]))
        m3 = float(np.max(spec[b3 - 3 : b3 + 4]))
        h2 = float(20.0 * np.log10(m2 / m1))
        h3 = float(20.0 * np.log10(m3 / m1))
        measured[lvl_db] = (h2, h3)

        ref = ref_levels[str(lvl_db)]
        assert abs(h2 - ref["h2_dbc"]) <= 0.2, f"H2 mismatch at {lvl_db} dBFS"
        assert abs(h3 - ref["h3_dbc"]) <= 0.2, f"H3 mismatch at {lvl_db} dBFS"

    # At -18 dBFS, H2 dominates H3; at 0 dBFS, H3 exceeds H2 by ~15 dB
    assert measured[-18.0][0] > measured[-18.0][1]
    assert measured[0.0][1] - measured[0.0][0] > 14.0


def test_tape_stage_9khz_aliasing_below_minus_48dbc():
    """9 kHz 0 dBFS sine through apply_tape_warmth_v2 (4x oversampled): alias at 21 kHz & 3 kHz <= -48 dBc."""
    sr = 48000
    n = sr * 3
    t = np.arange(n, dtype=np.float64) / sr
    win = signal.windows.blackmanharris(n)
    x9 = np.sin(2 * np.pi * 9000.0 * t).astype(np.float32)
    y9 = re_eng.apply_tape_warmth_v2(x9, sr=sr, drive=1.05, bias=0.035, ceiling=0.98, oversample=4)

    spec = np.abs(np.fft.rfft(y9.astype(np.float64) * win))
    bin_hz = sr / n
    b_fund = int(round(9000.0 / bin_hz))
    b_21k = int(round(21000.0 / bin_hz))
    b_3k = int(round(3000.0 / bin_hz))

    m_fund = float(np.max(spec[b_fund - 3 : b_fund + 4]))
    alias_21k = float(20.0 * np.log10(max(np.max(spec[b_21k - 3 : b_21k + 4]), 1e-18) / m_fund))
    alias_3k = float(20.0 * np.log10(max(np.max(spec[b_3k - 3 : b_3k + 4]), 1e-18) / m_fund))

    assert alias_21k <= -48.0, f"21 kHz alias {alias_21k:.2f} dBc > -48 dBc"
    assert alias_3k <= -48.0, f"3 kHz alias {alias_3k:.2f} dBc > -48 dBc"


def test_stems_mode_unoversampled_vocal_saturation_aliasing_p1_2():
    """
    P1-2 Acceptance Check:
    In process_stems_folder, vocals currently use 1x un-oversampled `np.tanh(x * 1.08) * 0.96`.
    On a 9 kHz 0 dBFS tone, 3rd harmonic at 27 kHz folds back to 21 kHz above -48 dBc (~-22 dBc).
    """
    sr = 48000
    n = sr * 3
    t = np.arange(n, dtype=np.float64) / sr
    win = signal.windows.blackmanharris(n)
    x9 = np.sin(2 * np.pi * 9000.0 * t).astype(np.float32)

    # Exact expression from process_stems_folder vocal chain
    y_voc = (np.tanh(x9 * 1.08) * 0.96).astype(np.float32)
    spec = np.abs(np.fft.rfft(y_voc.astype(np.float64) * win))
    bin_hz = sr / n
    m_fund = float(np.max(spec[int(round(9000 / bin_hz)) - 3 : int(round(9000 / bin_hz)) + 4]))
    m_21k = float(np.max(spec[int(round(21000 / bin_hz)) - 3 : int(round(21000 / bin_hz)) + 4]))
    alias_21k_dbc = float(20.0 * np.log10(max(m_21k, 1e-18) / m_fund))

    assert alias_21k_dbc <= -48.0, (
        f"P1-2 defect confirmed: 1x vocal saturation alias at 21 kHz is {alias_21k_dbc:.2f} dBc (> -48 dBc)"
    )


def test_tape_stage_dc_blocker_steady_state():
    """Verifies 10 Hz DC blocker suppresses steady-state DC offset from -0.0117 down to < 1e-6 in float32."""
    sr = 48000
    t = np.arange(sr * 3, dtype=np.float64) / sr
    x = np.sin(2 * np.pi * 1000.0 * t).astype(np.float32)
    y = re_eng.apply_tape_warmth_v2(x, sr=sr, drive=1.05, bias=0.035, ceiling=0.98, oversample=4)
    steady_dc = abs(float(np.mean(y[sr:])))
    assert steady_dc < 1e-6, f"Steady-state DC {steady_dc:.3e} >= 1e-6"


# =============================================================================
# 5. PUBLIC INTERFACES, PARAMETERS & BIT-IDENTICAL DSP REGRESSION
# =============================================================================

def test_public_interfaces_and_default_params_preserved(baseline):
    """All baseline DEFAULT_PARAMS keys/values, PRESETS, and public signatures must remain intact."""
    for k, v in baseline["default_params"].items():
        assert k in re_eng.DEFAULT_PARAMS, f"Missing DEFAULT_PARAMS key: {k}"
        assert re_eng.DEFAULT_PARAMS[k] == v, f"Changed DEFAULT_PARAMS[{k}]: {re_eng.DEFAULT_PARAMS[k]} != {v}"

    assert re_eng.PRESETS == baseline["presets"], "PRESETS dictionary changed unexpectedly"

    for fn_name, orig_sig in baseline["public_signatures"].items():
        fn = getattr(re_eng, fn_name, None)
        assert callable(fn), f"Public function {fn_name} missing"
        cur_params = list(inspect.signature(fn).parameters.keys())
        orig_param_count = len([p for p in orig_sig.strip("()").split(",") if p.strip()])
        assert len(cur_params) >= orig_param_count, f"Signature shrunk on {fn_name}"

    # Verify Whitepaper permalink lines #L130-L180 of apply_tape_warmth_v2 remain anchored at line 130
    lines = (ROOT_DIR / "remaster_engine.py").read_text(encoding="utf-8").splitlines()
    assert lines[129].startswith("def apply_tape_warmth_v2("), (
        f"apply_tape_warmth_v2 shifted away from line 130! Line 130 is: {lines[129]}"
    )


def test_dsp_bit_identical_regression(baseline):
    """Audio samples returned by process_audio_array must match Stage 1 baseline SHA-256 bit-for-bit."""
    rng = np.random.default_rng(20261104)
    sr = 48000
    t = np.arange(sr * 4, dtype=np.float64) / sr
    sig_l = 0.45 * np.sin(2 * np.pi * 55 * t) + 0.25 * np.sin(2 * np.pi * 440 * t) + 0.18 * np.sin(2 * np.pi * 5200 * t) + 0.02 * rng.standard_normal(len(t))
    sig_r = 0.45 * np.sin(2 * np.pi * 55 * t + 0.4) + 0.25 * np.sin(2 * np.pi * 440 * t - 0.2) + 0.18 * np.sin(2 * np.pi * 5200 * t) + 0.02 * rng.standard_normal(len(t))
    synth_stereo = np.column_stack([sig_l, sig_r]).astype(np.float32)

    out_auto, _ = re_eng.process_audio_array(synth_stereo, sr)
    assert hashlib.sha256(out_auto.tobytes()).hexdigest() == baseline["dsp_output_hashes"]["synth_pharmakon1_sha256"]

    for p_key in ("suno", "udio", "club", "audiophile"):
        out_p, _ = re_eng.process_audio_array(synth_stereo, sr, {"mode": "pharmakon2", "preset": p_key})
        assert hashlib.sha256(out_p.tobytes()).hexdigest() == baseline["dsp_output_hashes"][f"synth_preset_{p_key}_sha256"]


# =============================================================================
# 6. LONG FILES (>2 MIN) & CHUNK CROSSFADE BOUNDARIES
# =============================================================================

def test_long_file_130s_chunk_boundary_continuity_and_true_peak():
    """
    Tests >2 min file (130 s @ 24 kHz -> crosses 120 s chunk boundary with 1.0 s crossfade at 119-120 s):
    - Output length matches input length exactly
    - Zero NaN/Inf and zero click discontinuity at chunk crossfade start (119.0 s) and end (120.0 s)
    - True-Peak across boundary window <= ceiling + 0.05 dB
    """
    sr = 24000  # 130s * 24kHz = 3.12M stereo samples -> exercises exact 120*sr chunking path fast
    dur_sec = 130
    n = sr * dur_sec
    t = np.arange(n, dtype=np.float64) / sr

    # Continuous stereo signal exceeding ceiling (1.25 peak) right across 119s..120s crossfade
    tone_l = 0.85 * np.sin(2 * np.pi * 220.0 * t) + 0.40 * np.sin(2 * np.pi * 55.0 * t)
    tone_r = 0.85 * np.sin(2 * np.pi * 220.0 * t + 0.3) + 0.40 * np.sin(2 * np.pi * 55.0 * t)
    long_audio = np.column_stack([tone_l, tone_r]).astype(np.float32)

    ceiling_db = -0.3
    out, reported_tp = re_eng.true_peak_limiter(long_audio, sr, target_ceiling_db=ceiling_db, oversample=4)

    assert out.shape == long_audio.shape
    assert out.dtype == np.float32
    assert np.all(np.isfinite(out))

    # Inspect 118.5s .. 120.5s window around the 119.0s - 120.0s crossfade seam
    w_start = int(118.5 * sr)
    w_end = int(120.5 * sr)
    seam_slice = out[w_start:w_end]

    # Sample-to-sample first difference at seams vs interior steady wave (detect any step/click)
    interior_diff_max = float(np.max(np.abs(np.diff(out[int(60 * sr) : int(62 * sr)], axis=0))))
    seam_diff_max = float(np.max(np.abs(np.diff(seam_slice, axis=0))))
    assert seam_diff_max <= interior_diff_max * 1.15, (
        f"Discontinuity/click detected at 120s chunk boundary: seam_diff={seam_diff_max:.5f} vs interior={interior_diff_max:.5f}"
    )

    seam_tp_db = _measure_4x_true_peak_db(seam_slice)
    assert seam_tp_db <= ceiling_db + 0.05, f"Chunk seam 4X True-Peak {seam_tp_db:.3f} dBFS exceeded ceiling"
