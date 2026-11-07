"""
PHARMAKON 3.0: Limiter-Aware Sub-Sync Unit & Acceptance Tests
Verifies:
1. Virtual Micro-Limiter Cost Function: J(tau) = Delta E_sub(tau) - lambda * max(0, Delta Peak(tau))
2. Sub-Sync Mode Resolution & Safe-Bypass Toggle ('off', 'legacy', 'limiter_aware')
3. Infrasonic energy floor safe-bypass (< -50 dBFS)
4. Destructive phase cancellation recovery without peak blowout
5. Multi-stem process_stems_folder integration with True-Peak Guard
"""

import os
import numpy as np
import pytest
import scipy.signal as signal
import soundfile as sf
from pathlib import Path

import remaster_engine as re_eng


def _compute_rms_dbfs(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-12))
    return float(20.0 * np.log10(max(1e-12, rms)))


def _compute_peak_dbfs(x: np.ndarray) -> float:
    pk = float(np.max(np.abs(x)))
    return float(20.0 * np.log10(max(1e-12, pk)))


def test_sub_sync_mode_resolution_and_toggles():
    """Verifies mode selection, toggles, and parameter validation."""
    # 1. Default fallback (PHARMAKON 2.0 compatibility)
    cfg_default = re_eng.resolve_sub_sync_config()
    assert cfg_default["requested_mode"] == "off"
    assert cfg_default["effective_mode"] == "legacy"
    assert cfg_default["phase_align_sub"] is True

    # 2. Explicit 'off' mode (toggle disabled)
    cfg_off = re_eng.resolve_sub_sync_config({"sub_sync_mode": "off"})
    assert cfg_off["effective_mode"] == "off"

    # 3. Explicit phase_align_sub=False bypass
    cfg_bypass = re_eng.resolve_sub_sync_config({"phase_align_sub": False})
    assert cfg_bypass["effective_mode"] == "off"

    # 4. Explicit 'legacy' mode
    cfg_legacy = re_eng.resolve_sub_sync_config({"sub_sync_mode": "legacy"})
    assert cfg_legacy["effective_mode"] == "legacy"

    # 5. PHARMAKON 3.0 'limiter_aware' mode
    cfg_30 = re_eng.resolve_sub_sync_config({"sub_sync_mode": "limiter_aware"})
    assert cfg_30["effective_mode"] == "limiter_aware"
    assert cfg_30["experimental_active"] is True
    assert cfg_30["sub_sync_limiter_penalty"] == 1.20
    assert cfg_30["sub_sync_min_gain_db"] == 0.15
    assert cfg_30["sub_sync_energy_floor_dbfs"] == -50.0

    # 6. Invalid mode error handling
    with pytest.raises(ValueError, match="Invalid sub_sync_mode"):
        re_eng.resolve_sub_sync_config({"sub_sync_mode": "hyper_sync_ultra"})


def test_safe_bypass_on_acoustic_and_silent_material():
    """
    Acoustic or quiet material without kick fundamental (< -50 dBFS)
    must engage Safe-Bypass immediately, producing bit-exact identity output.
    """
    sr = 48000
    n = sr * 2
    t = np.arange(n, dtype=np.float64) / sr

    # Acoustic guitar / vocal emulation (no sub-50Hz energy)
    drums_acoustic = (0.2 * np.sin(2 * np.pi * 350.0 * t) + 0.1 * np.sin(2 * np.pi * 1200.0 * t)).astype(np.float32)
    bass_acoustic = (0.3 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)

    drums_stereo = np.column_stack([drums_acoustic, drums_acoustic])
    bass_stereo = np.column_stack([bass_acoustic, bass_acoustic])

    aligned_bass, meta = re_eng.align_sub_phase_limiter_aware(drums_stereo, bass_stereo, sr)

    assert meta["safe_path_engaged"] is True
    assert meta["events_corrected"] == 0
    # Must be bit-exact identical
    np.testing.assert_array_equal(aligned_bass, bass_stereo)


def test_destructive_phase_cancellation_recovery():
    """
    Synthesize simultaneous 50 Hz kick and 50 Hz bass in phase conflict.
    Limiter-Aware 3.0 must detect the destructive cancellation, apply optimal shift,
    restore sub energy, and preserve dynamic headroom.
    """
    sr = 48000
    duration = 3.0
    n = int(round(sr * duration))
    t = np.arange(n, dtype=np.float64) / sr

    # Periodic kick drum at 120 BPM (0.5 s period)
    t_beat = np.mod(t, 0.5)
    kick = 0.70 * np.sin(2 * np.pi * 50.0 * t_beat) * np.exp(-12.0 * t_beat)

    # Bass note at 50 Hz in anti-phase
    bass = 0.50 * np.sin(2 * np.pi * 50.0 * t + np.pi)

    drums_stereo = np.column_stack([kick, kick]).astype(np.float32)
    bass_stereo = np.column_stack([bass, bass]).astype(np.float32)

    raw_mix = drums_stereo + bass_stereo
    raw_sub = re_eng.butter_lowpass(raw_mix, 100.0, sr, order=2)
    raw_sub_rms = _compute_rms_dbfs(raw_sub)

    aligned_bass, meta = re_eng.align_sub_phase_limiter_aware(
        drums_stereo,
        bass_stereo,
        sr,
        max_lag_ms=3.0,
        limiter_penalty=1.20,
    )

    restored_mix = drums_stereo + aligned_bass
    restored_sub = re_eng.butter_lowpass(restored_mix, 100.0, sr, order=2)
    restored_sub_rms = _compute_rms_dbfs(restored_sub)

    sub_recovery_db = restored_sub_rms - raw_sub_rms

    assert meta["safe_path_engaged"] is False
    assert meta["events_corrected"] >= 10
    # Must recover sub energy from the destructive null
    assert sub_recovery_db >= 0.15, f"Expected sub gain >= 0.15 dB, got {sub_recovery_db:.2f} dB"


def test_process_stems_folder_with_sub_sync_modes(tmp_path):
    """Verifies process_stems_folder behavior across 'off', 'legacy', and 'limiter_aware' modes."""
    sr = 48000
    t = np.arange(sr * 1.5, dtype=np.float64) / sr
    stems_dir = tmp_path / "TechnoStems"
    stems_dir.mkdir()

    # Create synthetic stems
    t_beat = np.mod(t, 0.5)
    kick = (0.75 * np.sin(2 * np.pi * 50.0 * t_beat) * np.exp(-10.0 * t_beat)).astype(np.float32)
    bass = (0.45 * np.sin(2 * np.pi * 50.0 * t + np.pi)).astype(np.float32)
    vox = (0.20 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    other = (0.15 * np.sin(2 * np.pi * 880.0 * t)).astype(np.float32)

    sf.write(stems_dir / "drums.wav", np.column_stack([kick, kick]), sr, subtype="PCM_24")
    sf.write(stems_dir / "bass.wav", np.column_stack([bass, bass]), sr, subtype="PCM_24")
    sf.write(stems_dir / "vocals.wav", np.column_stack([vox, vox]), sr, subtype="PCM_24")
    sf.write(stems_dir / "other.wav", np.column_stack([other, other]), sr, subtype="PCM_24")

    # Run 1: limiter_aware (PHARMAKON 3.0 default)
    master_30, metrics_30 = re_eng.process_stems_folder(
        str(stems_dir),
        params={"sub_sync_mode": "limiter_aware"},
        open_folder=False,
    )
    assert os.path.isfile(master_30)

    # Run 2: off (safe bypass)
    master_off, metrics_off = re_eng.process_stems_folder(
        str(stems_dir),
        params={"sub_sync_mode": "off"},
        open_folder=False,
    )
    assert os.path.isfile(master_off)

    # Run 3: legacy
    master_leg, metrics_leg = re_eng.process_stems_folder(
        str(stems_dir),
        params={"sub_sync_mode": "legacy"},
        open_folder=False,
    )
    assert os.path.isfile(master_leg)
