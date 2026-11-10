"""Track Map tempo against ground-truth synthetic tracks (bench/validate_tempo.py).

The 3.1 sub-band detector scored acc1 32 % / acc2 36 % on this set. Required now:
no non-octave errors, >= 80 % exact, and every octave error shown as the alt tempo.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bench import validate_tempo as V  # noqa: E402


def test_tempo_ground_truth():
    r = V.run(verbose=False)
    assert r["acc2"] == 1.0, [x for x in r["rows"] if not x["acc2"]]
    assert r["acc1"] >= 0.80
    assert r["shown"] == 1.0, [x for x in r["rows"] if not x["shown"]]
