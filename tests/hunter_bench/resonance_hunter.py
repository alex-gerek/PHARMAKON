"""
PHARMAKON HUNTER v1.0 // Python Reference Implementation
Conforms to PHARMAKON HUNTER Technical Specification v1.0.

Core Features:
1. Dry Path Preservation: Audio filtered in time-domain via TDF-II Biquads.
2. Log2(f) One-Pole Smoother with exact block integration.
3. Temporal Leaky Spectrum Integrator (Bartlett/Welch frame smoothing) rejecting noise variance.
4. Spectral Whitening with configurable tilt (+6 dB/oct default), HF clamp (6.0), and 10 kHz roll-off.
5. Prominence Detection against 1/6-octave moving average with parabolic sub-bin peak interpolation (~1-2 Hz).
6. Dynamic Peaking Notch (RBJ peaking EQ) with double-precision TDF-II accumulator.
"""

import os
import json
import numpy as np
import scipy.signal
import soundfile as sf
import time

FS_DEFAULT = 48000

class TrackerNode:
    def __init__(self, search_min_hz=3000.0, search_max_hz=8000.0, fs=48000):
        self.fs = float(fs)
        self.search_min_hz = search_min_hz
        self.search_max_hz = search_max_hz
        
        # Initial frequency in log2 domain
        init_f0 = np.sqrt(search_min_hz * search_max_hz)
        self.logf_target = np.log2(init_f0)
        self.logf_current = np.log2(init_f0)
        
        self.gain_db_target = 0.0
        self.gain_db_current = 0.0
        self.gain_limit_db = -12.0
        self.q_factor = 10.0
        
        # Calibrated time constants for ballistics (in seconds)
        self.tau_freq_att = 0.003   # 3 ms (swift attack onto target)
        self.tau_freq_rel = 0.060   # 60 ms (smooth hold)
        self.tau_gain_att = 0.004   # 4 ms (fast clamp down)
        self.tau_gain_rel = 0.080   # 80 ms (musical decay)
        
        # Double-precision TDF-II biquad state
        self.s1 = 0.0
        self.s2 = 0.0
        
        # Biquad coefficients (normalized)
        self.b0 = 1.0
        self.b1 = 0.0
        self.b2 = 0.0
        self.a1 = 0.0
        self.a2 = 0.0
        
        self.locked = False
        self.update_coefficients(2.0 ** self.logf_current, self.gain_db_current, self.q_factor)

    def update_coefficients(self, f0: float, gain_db: float, Q: float):
        """Standard RBJ Peaking EQ coefficients."""
        f0 = np.clip(f0, 20.0, self.fs * 0.48)
        omega = 2.0 * np.pi * f0 / self.fs
        cos_w = np.cos(omega)
        sin_w = np.sin(omega)
        
        A = 10.0 ** (gain_db / 40.0) # amplitude factor
        alpha = sin_w / (2.0 * Q)
        
        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w
        a2 = 1.0 - alpha / A
        
        # Normalize
        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0


class ResonanceHunter:
    def __init__(self, fs=48000, num_nodes=1):
        self.fs = int(fs)
        self.fft_size = 1024
        self.hop_size = 128
        self.sub_block = 16
        self.spec_bins = self.fft_size // 2 + 1
        
        # Whitening parameters
        self.tilt_exp = 1.0         # +6 dB/octave
        self.whitening_wmax = 6.0   # +15.6 dB clamp
        self.prominence_threshold_db = 9.5 # Highly selective against noise fluctuations
        
        # Precompute Hann window
        self.window = np.hanning(self.fft_size).astype(np.float32)
        
        # Precompute Whitening Curve
        freqs = np.linspace(0.0, self.fs / 2.0, self.spec_bins, dtype=np.float32)
        f_ref = 1000.0
        ratio = np.maximum(freqs / f_ref, 1e-4)
        weights = ratio ** self.tilt_exp
        weights = np.minimum(weights, self.whitening_wmax)
        hf_mask = freqs > 10000.0
        if np.any(hf_mask):
            weights[hf_mask] *= np.exp(-(freqs[hf_mask] - 10000.0) / 4000.0)
        self.whitening_weights = weights.astype(np.float32)
        
        # Temporal leaky integrator for spectrum
        self.smoothed_mag = np.zeros(self.spec_bins, dtype=np.float32)
        self.alpha_spec = 0.50 # Balanced temporal smoothing
        
        # Active tracker nodes
        self.nodes = [TrackerNode(search_min_hz=3000.0, search_max_hz=8000.0, fs=self.fs)]
        if num_nodes == 3:
            self.nodes = [
                TrackerNode(search_min_hz=40.0, search_max_hz=140.0, fs=self.fs),    # Low Mud
                TrackerNode(search_min_hz=600.0, search_max_hz=1400.0, fs=self.fs),  # Boxy Harsh
                TrackerNode(search_min_hz=3000.0, search_max_hz=8000.0, fs=self.fs), # Neural Whistle
            ]

    def _analyze_spectrum(self, frame_audio: np.ndarray):
        """Computes temporally smoothed, whitened magnitude spectrum and extracts prominent resonance."""
        windowed = frame_audio * self.window
        X_complex = np.fft.rfft(windowed, n=self.fft_size)
        mag = np.abs(X_complex).astype(np.float32)
        
        # Temporal spectrum smoothing across frames
        self.smoothed_mag = self.alpha_spec * self.smoothed_mag + (1.0 - self.alpha_spec) * mag
        
        # 1. Spectral Whitening
        mag_white = self.smoothed_mag * self.whitening_weights
        
        # 2. Moving Average Envelope (~1/6 octave, 17 bins)
        kernel_size = 17
        kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
        env = np.convolve(mag_white, kernel, mode='same')
        env = np.maximum(env, 1e-7)
        
        # 3. Prominence in dB
        prominence_db = 20.0 * np.log10(np.maximum(mag_white, 1e-7) / env)
        
        freq_bins = np.linspace(0.0, self.fs / 2.0, self.spec_bins)
        
        # 4. Search and Update per Node
        for node in self.nodes:
            gate_mask = (freq_bins >= node.search_min_hz) & (freq_bins <= node.search_max_hz)
            gate_indices = np.where(gate_mask)[0]
            
            if len(gate_indices) == 0:
                continue
                
            prom_gate = prominence_db[gate_indices]
            max_rel_idx = np.argmax(prom_gate)
            max_bin_idx = gate_indices[max_rel_idx]
            max_prom = prom_gate[max_rel_idx]
            
            if max_prom >= self.prominence_threshold_db:
                node.locked = True
                
                # Parabolic sub-bin interpolation
                k = max_bin_idx
                if 1 <= k < (self.spec_bins - 1):
                    alpha_val = mag_white[k - 1]
                    beta_val = mag_white[k]
                    gamma_val = mag_white[k + 1]
                    denom = alpha_val - 2.0 * beta_val + gamma_val
                    delta = 0.5 * (alpha_val - gamma_val) / denom if np.abs(denom) > 1e-9 else 0.0
                    delta = np.clip(delta, -0.5, 0.5)
                else:
                    delta = 0.0
                    
                bin_res = self.fs / float(self.fft_size)
                f_peak = (k + delta) * bin_res
                f_peak = np.clip(f_peak, node.search_min_hz, node.search_max_hz)
                
                node.logf_target = np.log2(f_peak)
                excess = max_prom - self.prominence_threshold_db
                target_gain = -np.clip(excess * 1.2, 0.0, abs(node.gain_limit_db))
                node.gain_db_target = target_gain
            else:
                node.locked = False
                node.gain_db_target = 0.0

    def process(self, audio_in: np.ndarray):
        """
        Processes audio block by block.
        Returns:
            audio_out: filtered audio (dry x wet biquad)
            telemetry: dict with tracked frequencies, gains, and timestamps.
        """
        N = len(audio_in)
        audio_out = np.zeros(N, dtype=np.float32)
        
        time_stamps = []
        tracked_f0 = []
        tracked_gain = []
        
        hop_step = self.hop_size
        sub_step = self.sub_block
        hop_accum = 0
        
        ring = np.zeros(self.fft_size, dtype=np.float32)
        
        for i in range(0, N, sub_step):
            sub_end = min(i + sub_step, N)
            chunk_len = sub_end - i
            chunk = audio_in[i:sub_end]
            
            # Push to ring buffer
            ring = np.roll(ring, -chunk_len)
            ring[-chunk_len:] = chunk
            
            hop_accum += chunk_len
            if hop_accum >= hop_step:
                hop_accum -= hop_step
                self._analyze_spectrum(ring)
            
            # Sub-block coefficient & smoother update with exact discrete integration
            for node in self.nodes:
                diff_logf = node.logf_target - node.logf_current
                tau_f = node.tau_freq_att if node.locked else node.tau_freq_rel
                alpha_f = 1.0 - np.exp(-chunk_len / (tau_f * self.fs))
                node.logf_current += alpha_f * diff_logf
                current_f0 = 2.0 ** node.logf_current
                
                diff_gain = node.gain_db_target - node.gain_db_current
                tau_g = node.tau_gain_att if diff_gain < 0.0 else node.tau_gain_rel
                alpha_g = 1.0 - np.exp(-chunk_len / (tau_g * self.fs))
                node.gain_db_current += alpha_g * diff_gain
                
                node.update_coefficients(current_f0, node.gain_db_current, node.q_factor)
                
                if i % 128 == 0:
                    time_stamps.append(i / float(self.fs))
                    tracked_f0.append(current_f0)
                    tracked_gain.append(node.gain_db_current)
            
            # Filter chunk sample by sample using TDF-II
            processed_chunk = chunk.astype(np.float64)
            for node in self.nodes:
                b0, b1, b2 = node.b0, node.b1, node.b2
                a1, a2 = node.a1, node.a2
                s1, s2 = node.s1, node.s2
                
                filtered = np.zeros(chunk_len, dtype=np.float64)
                for s in range(chunk_len):
                    x = processed_chunk[s]
                    y = b0 * x + s1
                    s1 = b1 * x - a1 * y + s2
                    s2 = b2 * x - a2 * y
                    filtered[s] = y
                    
                node.s1, node.s2 = s1, s2
                processed_chunk = filtered
                
            audio_out[i:sub_end] = processed_chunk.astype(np.float32)
            
        telemetry = {
            "time": np.array(time_stamps),
            "f0": np.array(tracked_f0),
            "gain_db": np.array(tracked_gain)
        }
        return audio_out, telemetry
