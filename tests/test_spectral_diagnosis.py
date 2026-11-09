"""Measured Spectral Diagnosis: a defect is reported only when it is measured in THIS track."""
import io
import os
import sys
import contextlib
import tempfile

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402
from bench import validate_resonance as VR  # noqa: E402

SR = 48000


def _run(x, **kw):
    with contextlib.redirect_stdout(io.StringIO()):
        y, m = re_eng.process_audio_array(x.astype(np.float32), SR, {**re_eng.DEFAULT_PARAMS, **kw})
    d = m["diagnosis"]
    return y, m, {i["key"]: i for i in d["source"]}, {i["key"]: i for i in d["treatment"]}, d


def test_clean_music_reports_no_resonance_and_no_clipping():
    x = VR.synth_music(1, seconds=16.0)
    x = x / np.max(np.abs(x)) * 0.5            # -6 dBFS peaks, no clipping
    _, m, src, trt, d = _run(x)
    assert src["peak"]["status"] == "ok"
    assert src["resonance"]["status"] == "ok"
    assert "No correction needed" in trt["antidote"]["text"]
    assert trt["true_peak"]["status"] == "ok"


def test_injected_resonance_is_reported_and_shown_as_corrected():
    clean = VR.synth_music(3, seconds=16.0)
    f0 = 5000.0
    x = VR.inject(clean, SR, f0, 6.0, 10.0)
    _, m, src, trt, d = _run(x)
    assert src["resonance"]["status"] in ("issue", "warn")
    assert any(abs(r["hz"] - f0) <= 0.03 * f0 for r in src["resonance"]["value"])
    cors = trt["antidote"]["value"]["corrections"]
    assert any(abs(c["hz"] - f0) <= 0.03 * f0 for c in cors)
    assert trt["antidote"]["value"]["after_max_db"] < re_eng.DIAG_RES_ISSUE_DB


def test_clipping_reported_only_when_present():
    x = VR.synth_music(2, seconds=10.0)
    x = np.clip(x / np.max(np.abs(x)) * 1.6, -1.0, 1.0)   # hard-clipped source
    _, m, src, trt, d = _run(x)
    assert src["peak"]["status"] == "issue" and "clipped" in src["peak"]["text"]


def test_antiphase_low_end_reported():
    x = VR.synth_music(5, seconds=10.0)
    lo = re_eng.butter_lowpass(x, 120.0, SR)
    x2 = x - lo
    x2[:, 0] += lo[:, 0]
    x2[:, 1] -= lo[:, 1]                       # low band in anti-phase between channels
    _, m, src, trt, d = _run(x2)
    assert src["sub_phase"]["status"] == "issue"
    # mono below the 120 Hz crossover removes the anti-phase there; the anti-phase content
    # that leaks above 120 Hz stays stereo, and the diagnosis must say so (warn, not ok)
    assert trt["sub_phase"]["value"] > src["sub_phase"]["value"] + 0.3
    assert trt["sub_phase"]["status"] == ("ok" if trt["sub_phase"]["value"] >= re_eng.DIAG_SUBCORR_WARN else "warn")


def test_certificate_contains_only_measured_statements():
    x = VR.synth_music(1, seconds=10.0)
    x = x / np.max(np.abs(x)) * 0.5
    _, m, _, _, _ = _run(x)
    out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()):
        f = re_eng.generate_mastering_report_html("t", m, out, dict(re_eng.DEFAULT_PARAMS))
    h = open(f, encoding="utf-8").read()
    for canned in ("Healthy Punch", "VERIFIED STREAMING", "ZERO INTER-SAMPLE", "Harmonic Silk",
                   "De-Harsh Notch Cut", "Tape Warmth (tanh)", "24-bit Lossless"):
        assert canned not in h, canned
    assert "SOURCE DIAGNOSIS (MEASURED ON THE ORIGINAL)" in h
    assert f"{m['true_peak_proc_db']:+.2f} dBTP" in h
