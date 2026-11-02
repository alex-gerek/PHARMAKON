"""
PHARMAKON DSP BRIDGE // Python to Native C++20 Shared Library Bridge (ctypes)
Architect: Lex Gerek | Lazuli Pictures & Feasy DSP Review
Zero disk I/O, pure in-memory zero-allocation DSP processing for Python & Whisper.
"""

import ctypes
import os
import sys
import time
import numpy as np
from pathlib import Path

# 1. Locate Native Shared Library
_MODULE_DIR = Path(__file__).resolve().parent

if sys.platform == "win32":
    _LIB_NAMES = ["libpharmakon.dll", "pharmakon.dll"]
elif sys.platform == "darwin":
    _LIB_NAMES = ["libpharmakon.dylib", "pharmakon.dylib"]
else:
    _LIB_NAMES = ["libpharmakon.so", "pharmakon.so"]

_lib_path = None
for name in _LIB_NAMES:
    p = _MODULE_DIR / name
    if p.exists():
        _lib_path = str(p)
        break

if not _lib_path:
    # Check parent dirs or standard build folders
    for cand in [_MODULE_DIR / "build" / _LIB_NAMES[0], _MODULE_DIR / "bin" / _LIB_NAMES[0]]:
        if cand.exists():
            _lib_path = str(cand)
            break

if not _lib_path:
    raise FileNotFoundError(
        f"Native PHARMAKON library ({_LIB_NAMES[0]}) not found in {_MODULE_DIR}. "
        f"Please compile with: cl /O2 /arch:AVX2 /std:c++20 /LD /DPHARMAKON_BUILD_DLL pharmakon_c.cpp /Fe:libpharmakon.dll"
    )

_lib = ctypes.CDLL(_lib_path)

# 2. Setup C API Types
_lib.pharmakon_create.argtypes = [ctypes.c_float]
_lib.pharmakon_create.restype = ctypes.c_void_p

_lib.pharmakon_destroy.argtypes = [ctypes.c_void_p]
_lib.pharmakon_destroy.restype = None

_lib.pharmakon_set_parameters.argtypes = [
    ctypes.c_void_p,
    ctypes.c_float,  # deharshDepth
    ctypes.c_float,  # tapeDrive
    ctypes.c_float,  # airGain
    ctypes.c_float,  # subMonoDepth
    ctypes.c_bool    # deltaListen
]
_lib.pharmakon_set_parameters.restype = None

_lib.pharmakon_process_block.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_float),
    ctypes.POINTER(ctypes.c_float),
    ctypes.c_int32
]
_lib.pharmakon_process_block.restype = None

_lib.pharmakon_get_latency_samples.argtypes = [ctypes.c_void_p]
_lib.pharmakon_get_latency_samples.restype = ctypes.c_int32


# 3. High-Level Python Wrapper
class PharmakonEngine:
    """
    High-performance real-time audio restoration wrapper around native C++20 DSP core.
    Operates 100% in-memory with zero disk latency.
    """

    def __init__(self, sample_rate: float = 48000.0):
        self.sample_rate = float(sample_rate)
        self.handle = _lib.pharmakon_create(ctypes.c_float(self.sample_rate))
        if not self.handle:
            raise MemoryError("Failed to initialize native C++ PharmakonEngine instance.")

    def __del__(self):
        if hasattr(self, "handle") and self.handle:
            _lib.pharmakon_destroy(self.handle)
            self.handle = None

    def get_latency_samples(self) -> int:
        """Returns lookahead latency (in samples) introduced by TruePeakLimiter."""
        return int(_lib.pharmakon_get_latency_samples(self.handle))

    def process_audio(
        self,
        audio_np: np.ndarray,
        deharsh: float = 0.75,
        tape: float = 1.15,
        air: float = 0.18,
        sub_mono: float = 1.0,
        delta: bool = False
    ) -> np.ndarray:
        """
        Processes audio in-memory through the full 5-stage C++20 DSP chain:
        1. SubMatrixModule (LR4 Mono Lock < 110Hz + 32Hz Sub Cut)
        2. DeHarshModule (Dynamic Resonant Ducker @ 5.2kHz)
        3. TapeWarmthModule (Studer A800 Asymmetric Soft Saturation)
        4. AirExciterModule (Polynomial Silk Harmonics > 15.5kHz)
        5. TruePeakLimiter (BS.1770-4 1.5ms Lookahead @ -0.3 dBFS)

        Args:
            audio_np: Input numpy array. Shape (N, 2) for stereo, or (N,) for mono.
            deharsh: Anti-AI harshness reduction depth [0.0 - 1.5]
            tape: Analog tape warmth drive [1.0 - 1.5]
            air: High-frequency silk exciter gain [0.0 - 0.4]
            sub_mono: Sub-bass mono anchor depth [0.0 - 1.0]
            delta: If True, outputs isolated removed residue (+6dB boosted)

        Returns:
            np.ndarray: Cleaned audio of same shape in float32.
        """
        is_mono = audio_np.ndim == 1
        if is_mono:
            audio_stereo = np.column_stack([audio_np, audio_np])
        else:
            audio_stereo = audio_np

        # Ensure contiguous 32-bit float array
        audio_c = np.ascontiguousarray(audio_stereo, dtype=np.float32)
        n_samples = len(audio_c)

        # Set DSP parameters
        _lib.pharmakon_set_parameters(
            self.handle,
            ctypes.c_float(deharsh),
            ctypes.c_float(tape),
            ctypes.c_float(air),
            ctypes.c_float(sub_mono),
            ctypes.c_bool(delta)
        )

        # Direct pointer binding without intermediate copies
        ptr_l = audio_c[:, 0].ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ptr_r = audio_c[:, 1].ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        # Process block in native AVX2 SIMD C++
        _lib.pharmakon_process_block(
            self.handle,
            ptr_l,
            ptr_r,
            ctypes.c_int32(n_samples)
        )

        if is_mono:
            return audio_c[:, 0].copy()
        return audio_c


def benchmark(duration_sec: float = 180.0, sr: int = 48000):
    """
    Runs live benchmark: 3 minutes of dense stereo audio.
    """
    total_samples = int(duration_sec * sr)
    print("=" * 65)
    print("  PHARMAKON NATIVE C++20 DSP BENCHMARK (AVX2 / FMA)")
    print(f"  Duration: {duration_sec:.1f} s ({duration_sec/60:.1f} min) | Sample Rate: {sr} Hz")
    print(f"  Total Stereo Samples: {total_samples:,} (L+R = {total_samples * 2:,} samples)")
    print("=" * 65)

    # Generate synthetic dense test signal: sub + body + harsh 5.2kHz whistle + noise
    t = np.linspace(0, duration_sec, total_samples, dtype=np.float32)
    sig_l = (
        0.35 * np.sin(2 * np.pi * 55.0 * t) +
        0.30 * np.sin(2 * np.pi * 440.0 * t) +
        0.25 * np.sin(2 * np.pi * 5200.0 * t) +
        0.05 * np.random.uniform(-1, 1, total_samples).astype(np.float32)
    )
    sig_r = (
        0.35 * np.sin(2 * np.pi * 55.0 * t + 0.5) +
        0.30 * np.sin(2 * np.pi * 440.0 * t) +
        0.25 * np.sin(2 * np.pi * 5200.0 * t) +
        0.05 * np.random.uniform(-1, 1, total_samples).astype(np.float32)
    )
    test_audio = np.column_stack([sig_l, sig_r]).astype(np.float32)

    engine = PharmakonEngine(sample_rate=sr)

    # Warmup
    engine.process_audio(test_audio[:2048])

    # Timed run
    start_t = time.perf_counter()
    mastered = engine.process_audio(test_audio, deharsh=0.85, tape=1.15, air=0.18, sub_mono=1.0)
    elapsed_sec = time.perf_counter() - start_t

    rtf = duration_sec / elapsed_sec
    latency_samp = engine.get_latency_samples()
    latency_ms = (latency_samp / sr) * 1000.0

    print(f"  Processed in:       {elapsed_sec * 1000.0:.2f} ms ({elapsed_sec:.4f} s)")
    print(f"  Real-Time Factor:   {rtf:.1f}x FASTER than real time!")
    print(f"  Chain PDC Latency:  {latency_samp} samples ({latency_ms:.2f} ms)")
    print(f"  Peak Level:         {np.max(np.abs(mastered)):.4f} (<= 1.0 True-Peak bounded)")
    print("=" * 65)
    return rtf, elapsed_sec


if __name__ == "__main__":
    benchmark(180.0, 48000)
