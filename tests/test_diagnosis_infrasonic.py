"""The infrasonic check counts only energy below the cut-off.

A strong 45 Hz sub-bass with a weak 20 Hz rumble 50 dB below it: the old measure (4th-order
low-pass, zero-phase) let the 45 Hz tone through and reported about -22 dB of 'infrasonic'
energy, a warning on almost every bass-heavy track and on PHARMAKON's own masters.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402

SR = 48000


def _tones(rumble_db, seconds=12.0):
    t = np.arange(int(SR * seconds)) / SR
    sub = np.sin(2 * np.pi * 45.0 * t)
    rumble = 10 ** (rumble_db / 20) * np.sin(2 * np.pi * 20.0 * t)
    return sub + rumble


def test_sub_bass_is_not_counted_as_infrasound():
    x = _tones(-50.0)                       # rumble power 50 dB below the sub tone
    got = re_eng._energy_below_db(x, SR, 32.0)
    assert -53.0 < got < -47.0, f"measured {got:.1f} dB, expected about -50 dB"


def test_real_rumble_is_still_found():
    x = _tones(-10.0)
    got = re_eng._energy_below_db(x, SR, 32.0)
    assert -12.0 < got < -9.0, f"measured {got:.1f} dB, expected about -10.4 dB"


def test_diagnosis_calls_a_clean_sub_bass_ok():
    x = _tones(-60.0)
    audio = np.column_stack([x, x]) * 0.3
    m = re_eng.calc_audio_metrics(audio, audio, SR)
    d = re_eng.build_spectral_diagnosis(audio, audio, SR, m)
    item = {i["key"]: i for i in d["source"]}["infrasonic"]
    assert item["status"] == "ok", item
