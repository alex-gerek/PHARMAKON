"""Resonance detector v2: ignores notes, finds envelope colouring (ground truth by construction)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402
from bench import resonance_v2 as V2  # noqa: E402
from bench import validate_resonance as VR  # noqa: E402

SR = 48000


def test_clean_music_with_high_notes_has_no_resonance():
    for seed in (0, 1):
        clean = VR.synth_music(seed, seconds=20.0)
        assert V2.analyze(clean, SR)["resonances"] == [], f"seed {seed}"


def test_injected_resonance_found_with_frequency_and_q():
    clean = VR.synth_music(3, seconds=20.0)
    f0 = 5000.0
    x = VR.inject(clean, SR, f0, 6.0, 10.0)
    res = V2.analyze(x, SR)["resonances"]
    hits = [r for r in res if abs(r["hz"] - f0) <= 0.03 * f0]
    assert hits, res
    assert 5.0 <= hits[0]["q_est"] <= 20.0
    assert hits[0]["prominence_db"] >= 2.0


def test_v1_picks_a_note_not_the_resonance():
    """Documents the v1 blind spot that v2 fixes."""
    clean = VR.synth_music(3, seconds=20.0)
    x = VR.inject(clean, SR, 5000.0, 6.0, 10.0)
    f_v1, _, prom = re_eng.detect_harsh_resonances(x, SR)
    assert not (prom >= 3.0 and abs(f_v1 - 5000.0) <= 150.0)
