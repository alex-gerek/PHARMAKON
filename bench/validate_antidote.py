"""
Ground-truth check of Auto Antidote v1 vs v2 inside the full-mix chain.

For clean synthetic music C and a resonance-injected copy X = EQ(C; f, gain, Q):
  residual(f) = band level of chain(X) - band level of chain_ref(C)   (band = f +- f/(2Q))
where chain_ref is the same chain with the antidote unable to act on anything
(v2 finds nothing on clean music, verified 0/12 false positives).
Ideal antidote: residual -> 0 dB (injected colouring removed). No antidote: residual = gain.

Also reports 'note damage' of v1: on CLEAN music v1 still retargets the de-harsher to a
note; the level change of that note's band versus the v2 chain is measured.
"""
import json
import os
import sys

import numpy as np
import scipy.signal as signal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import remaster_engine as re_eng  # noqa: E402
from bench import validate_resonance as VR  # noqa: E402

SR = 48000


def chain(x, v2):
    p = {**re_eng.DEFAULT_PARAMS, "antidote_v2": v2}
    y, m = re_eng.process_audio_array(x.astype(np.float32), SR, p)
    return y, m


def band_db(y, f, q):
    f_, p = signal.welch(y.mean(axis=1), SR, nperseg=8192)
    bw = f / q
    m = (f_ >= f - bw / 2) & (f_ <= f + bw / 2)
    return 10 * np.log10(np.mean(p[m]))


def run(seeds=range(6), gains=(4.0, 6.0, 9.0), q=10.0):
    rng = np.random.default_rng(11)
    rows = []
    note_damage = []
    for seed in seeds:
        clean = VR.synth_music(seed, seconds=24.0)
        ref, m_ref = chain(clean, True)
        assert not m_ref.get("antidote_v2_corrections"), "v2 acted on clean music"
        y1c, m1c = chain(clean, False)
        if m1c.get("detected_prominence_db", 0) >= 3.0:
            fn = m1c["detected_resonance_hz"]
            note_damage.append(band_db(y1c, fn, 20.0) - band_db(ref, fn, 20.0))
        for g in gains:
            f = float(rng.uniform(2500.0, 7500.0))
            x = VR.inject(clean, SR, f, g, q)
            y1, _ = chain(x, False)
            y2, m2 = chain(x, True)
            rows.append({"seed": seed, "f": round(f, 1), "gain": g,
                         "residual_v1_db": round(band_db(y1, f, q) - band_db(ref, f, q), 2),
                         "residual_v2_db": round(band_db(y2, f, q) - band_db(ref, f, q), 2),
                         "v2_corrections": m2.get("antidote_v2_corrections")})
    summ = {}
    for g in gains:
        r = [x for x in rows if x["gain"] == g]
        summ[f"{g:g} dB injected"] = {
            "v1_residual_median_db": round(float(np.median([x["residual_v1_db"] for x in r])), 2),
            "v2_residual_median_db": round(float(np.median([x["residual_v2_db"] for x in r])), 2),
            "v2_residual_worst_db": round(float(max(x["residual_v2_db"] for x in r)), 2),
        }
    return {"summary": summ,
            "v1_note_damage_db_on_clean_music": [round(float(d), 2) for d in note_damage],
            "rows": rows}


if __name__ == "__main__":
    print(json.dumps(run(), indent=1, default=str))
