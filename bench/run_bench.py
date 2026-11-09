"""
PHARMAKON Objective Metrics Bench - runner.

For every track in the corpus:
  1. take an excerpt (default 60 s starting at 30 % of the track),
  2. render each chain VARIANT with remaster_engine.process_audio_array,
  3. loudness-match ORIGINAL + all variants to one common LUFS (attenuation only),
  4. compute bench.metrics.music_metrics and deltas vs ORIGINAL,
  5. check the DRAFT targets.
Chain distortion metrics (THD / IMD / aliasing) are measured once per variant
with test tones, plus per individual nonlinear stage.

Usage:
    python bench/run_bench.py                      # default corpus
    python bench/run_bench.py track1.wav track2.wav --excerpt 45
Results: bench/results/<timestamp>/results.json and report.md
"""
import argparse
import datetime as dt
import json
import os
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import remaster_engine as re_eng  # noqa: E402
from bench import metrics as M  # noqa: E402

DEFAULT_CORPUS = [
    "demo_audio/bronze_psalter/Bronze_Psalter_Demo.wav",
    "uploads/Il Fuoco del Cuore.wav",
    "uploads/Miami Summer.wav",
    "uploads/Cobalt Lullaby.wav",
    "uploads/Bronze Psalter (1).wav",
    "uploads/!!!Round and Round.wav",
]

VARIANTS = {
    "P31_DEFAULT": {},
    "V2_CAL_DEEMPH": {"antidote_v2": True, "deharsh_calibrated": True, "tape_deemphasis": True},
    "V2_CAL_DEEMPH_PK12": {"antidote_v2": True, "deharsh_calibrated": True, "tape_deemphasis": True,
                           "tape_ref_peak_dbfs": -12.0},
}

# DRAFT targets - to be agreed; every one maps to a listening complaint.
TARGETS = {
    "res_v2_max_db": ("<=", 3.0, "no persistent resonant colouring > 3 dB in 2-9 kHz (metallic / plastic); detector v2"),
    "d_sharpness_acum": ("<=", 0.0, "not sharper than the original (fatigue)"),
    "d_band_presence_db": ("range", (-1.5, 0.5), "2-5 kHz share: tame, but not dull"),
    "d_band_brilliance_db": ("range", (-1.5, 1.0), "5-10 kHz share"),
    "d_tilt_db_per_oct": ("range", (-0.5, 0.5), "overall tonal tilt preserved"),
    "d_presence_flux_db": ("<=", 0.0, "harsh bursts not increased"),
    "plr_db": (">=", 8.0, "dynamics not squashed"),
}
CHAIN_TARGETS = {
    "alias_db": ("<=", -60.0, "aliasing (digital grit)"),
    "imd_smpte_db": ("<=", -40.0, "intermodulation (muddy / dirty)"),
}


def _check(value, rule):
    op, ref, _ = rule
    if value is None:
        return None
    if op == "<=":
        return value <= ref
    if op == ">=":
        return value >= ref
    lo, hi = ref
    return lo <= value <= hi


def _excerpt(audio, sr, seconds):
    n = int(seconds * sr)
    if len(audio) <= n:
        return audio
    start = max(0, min(len(audio) - n, int(len(audio) * 0.30)))
    return audio[start:start + n]


def _chain(params):
    def run(x, sr):
        y, _ = re_eng.process_audio_array(x.astype(np.float32), sr, {**re_eng.DEFAULT_PARAMS, **params})
        return y
    return run


STAGES = {
    "stage_tape_v2": lambda x, sr: re_eng.apply_tape_warmth_v2(x, sr, drive=1.04, bias=0.035, ceiling=0.98),
    "stage_air_exciter": lambda x, sr: re_eng.harmonic_air_exciter(x, sr, drive=0.12),
    "stage_vocal_sat_4x": lambda x, sr: re_eng.saturate_vocal_oversampled(x, sr),
    "stage_bass_softclip_4x": lambda x, sr: re_eng.soft_clip_oversampled(x * 1.05, sr, 0.98),
    "stage_drum_softclip_4x": lambda x, sr: re_eng.soft_clip_oversampled(x * 1.2, sr, 0.98),
    "ref_softclip_1x_pre_fix": lambda x, sr: re_eng.soft_clip(x * 1.2, 0.98),
}


def run(corpus, excerpt_s, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    results = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "excerpt_s": excerpt_s,
               "variants": VARIANTS, "targets": {k: [v[0], v[1], v[2]] for k, v in TARGETS.items()},
               "tracks": [], "chain": {}}

    for name, params in VARIANTS.items():
        results["chain"][name] = M.chain_metrics(_chain(params))
    for name, fn in STAGES.items():
        results["chain"][name] = M.chain_metrics(fn)

    for rel in corpus:
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            print(f"[skip] not found: {rel}")
            continue
        audio, sr = sf.read(path, dtype="float32")
        x = _excerpt(re_eng.ensure_stereo(audio), sr, excerpt_s)
        versions = {"ORIGINAL": x}
        for name, params in VARIANTS.items():
            versions[name], _ = re_eng.process_audio_array(x, sr, {**re_eng.DEFAULT_PARAMS, **params})
        lufs = {k: re_eng.calc_integrated_lufs(v, sr) for k, v in versions.items()}
        target = min(lufs.values())
        mets = {k: M.music_metrics(M.match_loudness(v, sr, target), sr) for k, v in versions.items()}
        mets_raw_lufs = {k: round(float(v), 2) for k, v in lufs.items()}
        orig = mets["ORIGINAL"]
        row = {"track": os.path.basename(path), "sr": sr, "matched_lufs": round(float(target), 2),
               "raw_lufs": mets_raw_lufs, "metrics": mets, "deltas": {}, "checks": {}}
        for name in VARIANTS:
            m = mets[name]
            d = {f"d_{k}": round(float(m[k] - orig[k]), 3) for k in m
                 if isinstance(m[k], (int, float)) and isinstance(orig.get(k), (int, float))}
            row["deltas"][name] = d
            merged = {**m, **d}
            row["checks"][name] = {k: _check(merged.get(k), rule) for k, rule in TARGETS.items()}
        results["tracks"].append(row)
        print(f"[ok] {row['track']}")

    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(render_report(results))
    return results


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "PASS" if v else "**FAIL**"
    if isinstance(v, float):
        return f"{v:+.2f}" if abs(v) < 100 else f"{v:.0f}"
    return str(v)


def render_report(res):
    L = [f"# PHARMAKON Metrics Bench — {res['generated']}", "",
         f"Excerpt {res['excerpt_s']:.0f} s per track; all versions loudness-matched (attenuation only) before measuring.",
         "Sharpness is an approximate Zwicker/Fastl model with DIN 45692 weighting (calibrated to 1 acum), not ISO 532-1 certified.", ""]
    L += ["## Draft targets", "", "| Metric | Rule | Meaning |", "|---|---|---|"]
    for k, (op, ref, why) in TARGETS.items():
        L.append(f"| `{k}` | {op} {ref} | {why} |")
    L += ["", "## Pass rate per variant", "", "| Variant | " + " | ".join(f"`{k}`" for k in TARGETS) + " |",
          "|---|" + "---|" * len(TARGETS)]
    for v in res["variants"]:
        cells = []
        for k in TARGETS:
            vals = [t["checks"][v][k] for t in res["tracks"] if t["checks"][v][k] is not None]
            cells.append(f"{sum(vals)}/{len(vals)}" if vals else "—")
        L.append(f"| {v} | " + " | ".join(cells) + " |")
    keys = ["res_v2_max_db", "res_v2_hz", "res_v2_q", "resonance_max_db", "resonance_hz", "sharpness_acum", "band_presence_db", "band_brilliance_db",
            "band_air_db", "tilt_db_per_oct", "presence_flux_db", "crest_db", "plr_db", "side_ratio_db"]
    for t in res["tracks"]:
        L += ["", f"## {t['track']} (matched to {t['matched_lufs']} LUFS)", "",
              "| Metric | ORIGINAL | " + " | ".join(res["variants"]) + " |", "|---|---|" + "---|" * len(res["variants"])]
        for k in keys:
            row = [_fmt(t["metrics"]["ORIGINAL"].get(k))]
            for v in res["variants"]:
                val = t["metrics"][v].get(k)
                d = t["deltas"][v].get(f"d_{k}")
                row.append(f"{_fmt(val)}" + (f" ({d:+.2f})" if isinstance(d, float) and k not in ("resonance_hz", "res_v2_hz", "res_v2_q") else ""))
            L.append(f"| {k} | " + " | ".join(row) + " |")
    L += ["", "## Chain distortion (test tones, -6 dBFS)", "", "| Chain / stage | THD 1 kHz | SMPTE IMD | Aliasing (9 kHz) |", "|---|---|---|---|"]
    for name, c in res["chain"].items():
        L.append(f"| {name} | {c['thd_1k_db']:.1f} dB | {c['imd_smpte_db']:.1f} dB | {c['alias_db']:.1f} dB |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="*")
    ap.add_argument("--excerpt", type=float, default=60.0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, "bench", "results", dt.datetime.now().strftime("%Y%m%d_%H%M%S"))
    run(a.tracks or DEFAULT_CORPUS, a.excerpt, out)
    print("report:", os.path.join(out, "report.md"))
