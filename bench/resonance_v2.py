"""
Resonance detector v2 - bench wrapper.

The implementation lives in remaster_engine.detect_resonances_v2 (the product module),
so the bench and Auto Antidote v2 always measure with exactly the same code and live
patches of remaster_engine.py stay self-contained. See the block comment
"2b. AUTO ANTIDOTE v2" in remaster_engine.py for the algorithm, and
bench/validate_resonance.py for the ground-truth validation.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from remaster_engine import detect_resonances_v2 as analyze  # noqa: E402,F401


def strongest(audio, sr, **kw):
    """(hz, prominence_db, q_est) of the top resonance, or (None, 0.0, None)."""
    res = analyze(audio, sr, **kw)["resonances"]
    if not res:
        return None, 0.0, None
    return res[0]["hz"], res[0]["prominence_db"], res[0]["q_est"]
