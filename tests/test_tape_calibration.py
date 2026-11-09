"""Tape operating level calibrated by robust peak: distortion must not depend on input level."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402
from bench import validate_resonance as VR  # noqa: E402

SR = 48000
BASE = {**re_eng.DEFAULT_PARAMS, "air_exciter": 0.0, "dynamic_deharsh": True}


def _tape_residual_db(x, ref_peak):
    """Nonlinear residual of the calibrated tape stage alone (gain-staged as in the pipeline)."""
    g = 1.0
    if ref_peak is not None:
        p = np.percentile(np.max(np.abs(x), axis=1), 99.9)
        g = 10 ** ((ref_peak - 20 * np.log10(p)) / 20)
    t = lambda v: re_eng.apply_tape_warmth_v2(v * g, SR, drive=1.04, bias=0.035, ceiling=0.98,
                                              deemphasis=True).astype(np.float64) / g
    lin = t(x * 1e-4) / 1e-4
    y = t(x)
    k = np.sum(y * lin) / np.sum(lin * lin)
    return 10 * np.log10(np.sum((y - k * lin) ** 2) / np.sum(y ** 2))


def test_calibration_makes_distortion_level_independent():
    x = VR.synth_music(1, seconds=8.0)
    x = x / np.max(np.abs(x)) * 0.9
    loud, quiet = x, x * 10 ** (-9 / 20)
    # uncalibrated: 9 dB hotter input -> clearly more distortion
    assert _tape_residual_db(loud, None) - _tape_residual_db(quiet, None) > 8.0
    # calibrated: same distortion regardless of how hot the source was rendered
    assert abs(_tape_residual_db(loud, -12.0) - _tape_residual_db(quiet, -12.0)) < 0.5


def test_pipeline_param_off_is_bit_identical_and_on_changes_audio():
    x = VR.synth_music(2, seconds=6.0).astype(np.float32)
    a, _ = re_eng.process_audio_array(x, SR, dict(re_eng.DEFAULT_PARAMS))
    b, _ = re_eng.process_audio_array(x, SR, {**re_eng.DEFAULT_PARAMS, "tape_ref_peak_dbfs": None})
    c, _ = re_eng.process_audio_array(x, SR, {**re_eng.DEFAULT_PARAMS, "tape_ref_peak_dbfs": -12.0})
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    # output level is restored after the stage (gain applied before, removed after)
    assert abs(20 * np.log10(np.sqrt(np.mean(c ** 2)) / np.sqrt(np.mean(a ** 2)))) < 1.0
