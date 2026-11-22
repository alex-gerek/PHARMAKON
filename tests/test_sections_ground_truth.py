"""Track Map sections against ground-truth arrangements (bench/validate_sections.py).

3.1 (fixed 8/16-bar grid from t = 0, positional labels) scored boundary F 0.22 (+-0.5 s)
and 27 % correct labels on this set. Required now on a pickup EDM track and two songs:
boundaries within half a second and correct labels.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import track_map_engine as tm  # noqa: E402
from bench import validate_sections as V  # noqa: E402


def _case(name):
    i = [c[0] for c in V.CASES].index(name)
    _, kind, bpm, pickup, plan = V.CASES[i]
    x, truth, bar_s = V.render(kind, bpm, pickup, plan, seed=i)
    m = tm.build_provisional_track_map(x, sr=V.SR)
    return m, V.evaluate(m, truth, bar_s, len(x) / V.SR)


def test_edm_with_pickup():
    m, r = _case("edm_pickup")
    assert r["hr05"] >= 0.9 and r["label_acc"] >= 0.95, r
    assert abs(m["first_downbeat_s"] - 0.73) < 0.1      # grid anchored to the music, not t = 0


def test_song_with_prechorus():
    m, r = _case("pop_basic")
    assert r["hr05"] >= 0.9 and r["label_acc"] >= 0.9, r
    assert m["genre"]["structure_vocabulary"] == "song"


def test_no_generic_section_labels():
    m, _ = _case("pop_fast")
    assert all(s["tag"] != "SECTION" for s in m["sections"])
    assert all(0.0 <= s["boundary_strength"] <= 1.0 and "evidence" in s for s in m["sections"])


def test_buildup_boundary_on_its_own_bar():
    # A riser ramps up, so 4-bar novelty peaked one bar late (114.9 s vs 113.2 s); the
    # boundary is now refined to the sharpest single-bar change (DEV note 36).
    m, r = _case("edm_short_intro")
    assert r["hr05"] == 1.0 and r["bar_f"] == 1.0, r
    starts = [s["start_s"] for s in m["sections"]]
    assert min(abs(t - 113.2) for t in starts) < 0.1, starts
