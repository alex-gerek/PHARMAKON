"""
PHARMAKON Research Task 04: Death in the Club
Module: synthetic_signals.py

Deterministic synthetic test signal generation at 48 kHz for low-end
kick and bass phase interaction experiments.

All generated signals are explicitly labeled as synthetic.
"""

import numpy as np
import scipy.signal as signal
from typing import Dict, Tuple, Any

SAMPLE_RATE = 48000


def generate_synthetic_kick(
    duration: float = 3.0,
    sr: int = SAMPLE_RATE,
    bpm: float = 120.0,
    f_start: float = 150.0,
    f_end: float = 45.0,
    decay_rate: float = 9.0,
    amplitude: float = 0.70,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Generates a synthetic kick drum signal consisting of a frequency sweep (chirp)
    from f_start down to f_end with exponential decay, repeating at the specified BPM.

    Returns:
        (kick_stereo, t, metadata)
    """
    n_samples = int(round(duration * sr))
    t = np.arange(n_samples, dtype=np.float64) / sr
    beat_interval = 60.0 / bpm
    t_beat = np.mod(t, beat_interval)

    # Exponential frequency sweep from f_start down to f_end
    # instantaneous frequency f(tau) = f_end + (f_start - f_end) * exp(-decay_rate * 2.5 * tau)
    tau = t_beat
    sweep_rate = decay_rate * 3.0
    phase = 2.0 * np.pi * (f_end * tau + (f_start - f_end) * (1.0 - np.exp(-sweep_rate * tau)) / sweep_rate)
    envelope = np.exp(-decay_rate * tau)
    kick_mono = amplitude * np.sin(phase) * envelope

    kick_stereo = np.column_stack([kick_mono, kick_mono]).astype(np.float32)
    meta = {
        "signal_type": "synthetic_kick_chirp",
        "bpm": bpm,
        "f_start_hz": f_start,
        "f_end_hz": f_end,
        "decay_rate": decay_rate,
        "amplitude": amplitude,
        "duration_sec": duration,
        "sr": sr,
    }
    return kick_stereo, t, meta


def generate_synthetic_sustained_bass(
    duration: float = 3.0,
    sr: int = SAMPLE_RATE,
    freq: float = 50.0,
    phase_offset_rad: float = 0.0,
    amplitude: float = 0.60,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Generates a synthetic sustained single-note sinusoidal sub-bass.
    """
    n_samples = int(round(duration * sr))
    t = np.arange(n_samples, dtype=np.float64) / sr
    bass_mono = amplitude * np.sin(2.0 * np.pi * freq * t + phase_offset_rad)
    bass_stereo = np.column_stack([bass_mono, bass_mono]).astype(np.float32)
    meta = {
        "signal_type": "synthetic_sustained_sine_bass",
        "freq_hz": freq,
        "phase_offset_rad": phase_offset_rad,
        "amplitude": amplitude,
        "duration_sec": duration,
        "sr": sr,
    }
    return bass_stereo, t, meta


def generate_synthetic_melodic_bass(
    duration: float = 3.0,
    sr: int = SAMPLE_RATE,
    notes: Tuple[float, ...] = (41.20, 48.99, 55.00, 65.41),  # E1, G1, A1, C2
    note_duration: float = 0.75,
    amplitude: float = 0.60,
    initial_phase: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Generates a synthetic melodic bassline that switches through different
    fundamental frequencies (e.g. E1 -> G1 -> A1 -> C2).
    """
    n_samples = int(round(duration * sr))
    t = np.arange(n_samples, dtype=np.float64) / sr
    bass_mono = np.zeros(n_samples, dtype=np.float64)

    curr_phase = initial_phase
    n_notes = len(notes)
    for i in range(n_samples):
        note_idx = int(t[i] / note_duration) % n_notes
        f = notes[note_idx]
        bass_mono[i] = amplitude * np.sin(curr_phase)
        curr_phase += 2.0 * np.pi * f / sr

    bass_stereo = np.column_stack([bass_mono, bass_mono]).astype(np.float32)
    meta = {
        "signal_type": "synthetic_melodic_bassline",
        "notes_hz": list(notes),
        "note_duration_sec": note_duration,
        "amplitude": amplitude,
        "duration_sec": duration,
        "sr": sr,
    }
    return bass_stereo, t, meta


def generate_synthetic_harmonic_bass(
    duration: float = 3.0,
    sr: int = SAMPLE_RATE,
    f0: float = 50.0,
    harmonics: Tuple[float, ...] = (1.0, 0.60, 0.35, 0.15),  # fundamental, 2nd, 3rd, 4th
    phases: Tuple[float, ...] = (0.0, 0.5, 1.2, 2.0),
    amplitude: float = 0.55,
    attack_ms: float = 10.0,
    repeat_interval: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Generates a synthetic bass signal with fundamental plus 2nd, 3rd, and 4th harmonics
    (crossing the 100 Hz boundary into 100, 150, 200 Hz) with realistic attack transients.
    """
    n_samples = int(round(duration * sr))
    t = np.arange(n_samples, dtype=np.float64) / sr
    bass_mono = np.zeros(n_samples, dtype=np.float64)

    for h_idx, (weight, phi) in enumerate(zip(harmonics, phases), start=1):
        f_h = f0 * h_idx
        bass_mono += weight * np.sin(2.0 * np.pi * f_h * t + phi)

    # Normalize harmonic combination to requested amplitude
    max_val = np.max(np.abs(bass_mono))
    if max_val > 1e-12:
        bass_mono = (bass_mono / max_val) * amplitude

    # Apply per-beat transient plucking envelope if repeat_interval > 0
    if repeat_interval > 0.0:
        t_cycle = np.mod(t, repeat_interval)
        att_sec = attack_ms * 1e-3
        # Fast attack, slight decay to sustain
        env = np.where(
            t_cycle < att_sec,
            t_cycle / att_sec,
            0.65 + 0.35 * np.exp(-8.0 * (t_cycle - att_sec)),
        )
        bass_mono *= env

    bass_stereo = np.column_stack([bass_mono, bass_mono]).astype(np.float32)
    meta = {
        "signal_type": "synthetic_harmonic_bass_with_transients",
        "f0_hz": f0,
        "harmonics_weights": list(harmonics),
        "phases_rad": list(phases),
        "attack_ms": attack_ms,
        "repeat_interval_sec": repeat_interval,
        "duration_sec": duration,
        "sr": sr,
    }
    return bass_stereo, t, meta


def generate_boundary_condition(
    condition_name: str,
    duration: float = 3.0,
    sr: int = SAMPLE_RATE,
    seed: int = 202611,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Generates boundary condition test signals:
    - 'silence': Complete digital zero array.
    - 'low_energy': Sub-threshold sine at -60 dBFS.
    - 'high_freq_noise': Out-of-band highpass noise (>1000 Hz, sub-band correlation ~0).
    - 'non_overlapping': Kick only in first half [0, 1.5s], Bass only in second half [1.5s, 3.0s].
    """
    n_samples = int(round(duration * sr))
    t = np.arange(n_samples, dtype=np.float64) / sr
    rng = np.random.default_rng(seed)

    if condition_name == "silence":
        drums = np.zeros((n_samples, 2), dtype=np.float32)
        bass = np.zeros((n_samples, 2), dtype=np.float32)
        meta = {"condition": "digital_silence", "drums_energy_dbfs": -np.inf, "bass_energy_dbfs": -np.inf}

    elif condition_name == "low_energy":
        # -60 dBFS sine waves (amplitude = 10^(-60/20) = 0.001)
        amp = 1e-3
        d_mono = amp * np.sin(2.0 * np.pi * 50.0 * t)
        b_mono = amp * np.sin(2.0 * np.pi * 50.0 * t + np.pi)
        drums = np.column_stack([d_mono, d_mono]).astype(np.float32)
        bass = np.column_stack([b_mono, b_mono]).astype(np.float32)
        meta = {"condition": "low_energy_sub_threshold", "amplitude_dbfs": -60.0}

    elif condition_name == "high_freq_noise":
        # Uncorrelated HF noise above 1000 Hz; no sub energy
        noise = rng.standard_normal(n_samples)
        b_hp, a_hp = signal.butter(4, 1000.0 / (0.5 * sr), btype="high")
        hf_noise = signal.filtfilt(b_hp, a_hp, noise)
        amp = 0.30
        hf_noise = (hf_noise / np.max(np.abs(hf_noise))) * amp
        drums = np.column_stack([hf_noise, hf_noise]).astype(np.float32)
        b_mono = 0.50 * np.sin(2.0 * np.pi * 50.0 * t)
        bass = np.column_stack([b_mono, b_mono]).astype(np.float32)
        meta = {"condition": "uncorrelated_out_of_band_noise", "noise_cutoff_hz": 1000.0}

    elif condition_name == "non_overlapping":
        # Kick in first half, Bass in second half
        half = n_samples // 2
        kick, _, _ = generate_synthetic_kick(duration=duration / 2.0, sr=sr)
        bass_sec, _, _ = generate_synthetic_sustained_bass(duration=duration / 2.0, sr=sr)
        drums = np.zeros((n_samples, 2), dtype=np.float32)
        bass = np.zeros((n_samples, 2), dtype=np.float32)
        drums[:half] = kick[:half]
        bass[half:] = bass_sec[: n_samples - half]
        meta = {"condition": "disjoint_temporal_support", "overlap_fraction": 0.0}

    else:
        raise ValueError(f"Unknown boundary condition: {condition_name}")

    meta["signal_type"] = f"synthetic_boundary_{condition_name}"
    meta["duration_sec"] = duration
    meta["sr"] = sr
    return drums, bass, meta
