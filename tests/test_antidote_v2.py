"""Auto Antidote v2 in the full-mix chain: removes an injected resonance, leaves clean music alone."""
import os
import sys

import numpy as np
import scipy.signal as signal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402
from bench import validate_resonance as VR  # noqa: E402

SR = 48000


def _band_db(y, f, q):
    fr, p = signal.welch(y.mean(axis=1), SR, nperseg=8192)
    m = (fr >= f - f / (2 * q)) & (fr <= f + f / (2 * q))
    return 10 * np.log10(np.mean(p[m]))


def _chain(x, **kw):
    return re_eng.process_audio_array(x.astype(np.float32), SR, {**re_eng.DEFAULT_PARAMS, **kw})


def test_antidote_v2_removes_injected_resonance():
    clean = VR.synth_music(2, seconds=16.0)
    f0, q = 4500.0, 10.0
    x = VR.inject(clean, SR, f0, 6.0, q)
    ref, m_ref = _chain(clean, antidote_v2=True)
    assert not m_ref["antidote_v2_corrections"]  # nothing to correct on clean music
    y1, _ = _chain(x)                       # v1 (default)
    y2, m2 = _chain(x, antidote_v2=True)
    res_v1 = _band_db(y1, f0, q) - _band_db(ref, f0, q)
    res_v2 = _band_db(y2, f0, q) - _band_db(ref, f0, q)
    assert res_v1 > 4.0                     # v1 leaves the resonance in place
    assert res_v2 < 2.5                     # v2 removes most of it
    assert any(abs(c["hz"] - f0) <= 0.03 * f0 for c in m2["antidote_v2_corrections"])


def test_resonance_correction_zero_phase_and_exact_depth():
    imp = np.zeros((SR, 2))
    imp[SR // 2] = 1.0
    out, applied = re_eng.apply_resonance_correction(imp, SR, [{"hz": 3000.0, "prominence_db": 6.0, "q_est": 8.0}])
    assert applied == [{"hz": 3000.0, "cut_db": 6.0, "q": 8.0}]
    H = np.fft.rfft(out[:, 0])
    f = np.fft.rfftfreq(SR, 1 / SR)
    k = np.argmin(np.abs(f - 3000.0))
    assert abs(20 * np.log10(np.abs(H[k])) + 6.0) < 0.1      # total cut equals the target
    assert int(np.argmax(np.abs(out[:, 0]))) == SR // 2       # zero-phase: no delay
