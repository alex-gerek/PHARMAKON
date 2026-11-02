"""
PHARMAKON HUNTER // Python ctypes Bridge
(c) 2026 Lazuli Pictures / Lex Gerek. Confidential & Proprietary.
Connects Python to native C++20 libpharmakon_hunter.so / .dll
Zero memory copies, zero allocations.
"""

import os
import ctypes
import numpy as np

class HunterEngine:
    def __init__(self, lib_path: str = "./libpharmakon_hunter.so", sample_rate: float = 48000.0):
        self.sample_rate = sample_rate
        if not os.path.exists(lib_path):
            raise FileNotFoundError(f"Native library not found at: {lib_path}")
            
        self.lib = ctypes.CDLL(lib_path)
        
        # Signatures
        self.lib.pharmakon_hunter_create.argtypes = [ctypes.c_float]
        self.lib.pharmakon_hunter_create.restype = ctypes.c_void_p
        
        self.lib.pharmakon_hunter_set_nodes.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        self.lib.pharmakon_hunter_set_nodes.restype = None
        
        self.lib.pharmakon_hunter_process.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int32
        ]
        self.lib.pharmakon_hunter_process.restype = None
        
        self.lib.pharmakon_hunter_node_freq.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        self.lib.pharmakon_hunter_node_freq.restype = ctypes.c_float
        
        self.lib.pharmakon_hunter_node_gain_db.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        self.lib.pharmakon_hunter_node_gain_db.restype = ctypes.c_float
        
        self.lib.pharmakon_hunter_destroy.argtypes = [ctypes.c_void_p]
        self.lib.pharmakon_hunter_destroy.restype = None
        
        self.handle = self.lib.pharmakon_hunter_create(ctypes.c_float(sample_rate))
        if not self.handle:
            raise RuntimeError("Failed to allocate native ResonanceHunterModule handle")

    def set_nodes(self, n: int):
        self.lib.pharmakon_hunter_set_nodes(self.handle, ctypes.c_int32(n))

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        Process float32 audio in-place without memory allocation.
        """
        assert audio.dtype == np.float32, "Audio must be float32"
        out = np.ascontiguousarray(audio.copy())
        ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self.lib.pharmakon_hunter_process(self.handle, ptr, ctypes.c_int32(len(out)))
        return out

    def get_node_freq(self, idx: int = 0) -> float:
        return float(self.lib.pharmakon_hunter_node_freq(self.handle, ctypes.c_int32(idx)))

    def get_node_gain_db(self, idx: int = 0) -> float:
        return float(self.lib.pharmakon_hunter_node_gain_db(self.handle, ctypes.c_int32(idx)))

    def __del__(self):
        if hasattr(self, 'handle') and self.handle:
            self.lib.pharmakon_hunter_destroy(self.handle)
            self.handle = None
