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
    y1, _ = _chain(x, classic_31=True)      # v1 (Classic 3.1 profile)
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
    assert applied == [{"hz": 3000.0, "cut_db": 6.0, "q": 8.0, "time_coverage": 1.0}]
    H = np.fft.rfft(out[:, 0])
    f = np.fft.rfftfreq(SR, 1 / SR)
    k = np.argmin(np.abs(f - 3000.0))
    assert abs(20 * np.log10(np.abs(H[k])) + 6.0) < 0.1      # total cut equals the target
    assert int(np.argmax(np.abs(out[:, 0]))) == SR // 2       # zero-phase: no delay


def test_local_correction_only_where_resonance_present():
    """Resonance injected in the middle 70 % of the song: corrected there, untouched elsewhere."""
    clean = VR.synth_music(4, seconds=30.0)
    f0, q = 5200.0, 10.0
    n = len(clean)
    a, b = int(0.15 * n), int(0.85 * n)
    x = clean.copy()
    x[a:b] = VR.inject(clean, SR, f0, 6.0, q)[a:b]
    y_loc, m_loc = _chain(x, antidote_v2=True)
    y_glob, m_glob = _chain(x, antidote_v2=True, antidote_v2_local=False)
    ref, _ = _chain(clean, antidote_v2=True)
    cor = [c for c in m_loc["antidote_v2_corrections"] if abs(c["hz"] - f0) <= 0.03 * f0]
    assert cor and 0.5 < cor[0]["time_coverage"] < 0.95
    edge = slice(int(0.02 * n), int(0.10 * n))      # resonance-free region
    mid = slice(int(0.30 * n), int(0.70 * n))       # resonance region
    d_edge_loc = _band_db(y_loc[edge], f0, q) - _band_db(ref[edge], f0, q)
    d_edge_glob = _band_db(y_glob[edge], f0, q) - _band_db(ref[edge], f0, q)
    d_mid_loc = _band_db(y_loc[mid], f0, q) - _band_db(ref[mid], f0, q)
    assert abs(d_edge_loc) < 0.5          # local: clean region untouched
    assert d_edge_glob < -1.0             # global: clean region would be cut (band-average)
    assert d_mid_loc < 2.5                # resonance still removed where present


def test_antidote_v2_runs_in_both_workflow_modes():
    clean = VR.synth_music(2, seconds=16.0)
    f0, q = 4500.0, 10.0
    x = VR.inject(clean, SR, f0, 6.0, q)
    for mode in ("pharmakon1", "pharmakon2"):
        _, m = _chain(x, mode=mode)
        assert m["sound_profile"] == "Clean Chain 3.2"
        assert any(abs(c["hz"] - f0) <= 0.03 * f0 for c in m["antidote_v2_corrections"]), mode
    # Classic 3.1 in Pro Rack mode keeps the old behaviour: no automatic detection at all
    _, m = _chain(x, mode="pharmakon2", classic_31=True)
    assert "antidote_v2_corrections" not in m and "detected_resonance_hz" not in m
