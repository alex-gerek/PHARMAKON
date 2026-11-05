"""
PHARMAKON Research Task 04: Death in the Club
Module: headroom_analysis.py

Single source of truth for every statistic about the headroom experiment.

Pipeline (strictly one-directional):
    headroom_measurements.csv  ->  headroom_summary.json  ->  Figure 6 (PNG/SVG)
                                                          ->  HEADROOM_ANALYSIS.md

Rules enforced by this module:
- No numeric result is typed by hand. Every number in the report and figure is
  formatted from the summary dict, which is computed from the CSV only.
- Filter criteria are declared once (FILTER_CRITERIA) and exported verbatim.
- Values from the superseded report are kept ONLY in SUPERSEDED_REPORT_VALUES and
  are printed exclusively in the clearly labelled reconciliation appendix.

Usage:
    py -3.14 research/death_in_the_club/headroom_analysis.py
"""

import os
import csv
import json
import hashlib
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import scipy.stats as stats
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(CURRENT_DIR, "headroom_measurements.csv")
SUMMARY_PATH = os.path.join(CURRENT_DIR, "headroom_summary.json")
REPORT_PATH = os.path.join(CURRENT_DIR, "HEADROOM_ANALYSIS.md")
FIGURES_DIR = os.path.join(CURRENT_DIR, "figures")

ACTIVE_METHODS = ["B_GlobalDelay", "C_LegacySubOnly", "D_GuardedPerKick"]
ALL_METHODS = ["A_Baseline"] + ACTIVE_METHODS
METHOD_LABELS = {
    "A_Baseline": "A: Baseline (unmodified)",
    "B_GlobalDelay": "B: Single global delay",
    "C_LegacySubOnly": "C: Legacy sub-only (align_sub_phase)",
    "D_GuardedPerKick": "D: Guarded per-kick prototype (GW-FRA)",
}

MEASUREMENT_FLOOR_DB = -80.0
TP_UNCHANGED_TOL_DB = 0.01      # |dTP| <= 0.01 dB counted as "unchanged" (meter ripple ~0.0055 dB, see report)
EXTREME_ABS_SUB_GAIN_DB = 3.0   # sensitivity cut for extreme sub-gain observations
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 20261105

FILTER_CRITERIA = {
    "measurement_floor_db": MEASUREMENT_FLOOR_DB,
    "near_zero_definition": "baseline sub-band (<100 Hz, 4th-order Butterworth, zero-phase) RMS of drums+bass <= -80.0 dBFS",
    "relative_gain_valid": "is_relative_gain_valid == True  (i.e. NOT near-zero)",
    "tp_delta_valid": "is_tp_delta_valid == True  (baseline true peak > -80.0 dBTP)",
    "active_methods": "method in {B_GlobalDelay, C_LegacySubOnly, D_GuardedPerKick}; Method A is the identity reference (all deltas 0 by construction) and is not an observation",
    "subsets": {
        "primary_all_valid": "active method AND relative_gain_valid AND tp_delta_valid  [THIS IS EXACTLY THE SET PLOTTED IN FIGURE 6 AND USED FOR ALL HEADLINE CORRELATIONS]",
        "historical_30": "active method AND signal_category == 'historical_30_runs_seed202611'",
        "non_boundary_valid": "primary_all_valid AND signal_category != 'boundary_conditions'  [the undocumented filter used by the superseded Figure 6]",
        "excl_pure_phase_sweep": "primary_all_valid AND signal_category != 'pure_phase_sweep'",
        "excl_abs_sub_gain_gt_3db": "primary_all_valid AND |delta_sub_gain_db| <= 3.0",
    },
    "tp_change_classes": f"increase: dTP > +{TP_UNCHANGED_TOL_DB} dB; decrease: dTP < -{TP_UNCHANGED_TOL_DB} dB; unchanged: |dTP| <= {TP_UNCHANGED_TOL_DB} dB",
    "axis_clipping": "none: Figure 6 panel (a) shows every observation in primary_all_valid; panel (b) is a labelled zoom and states how many points fall outside it",
}

SUBSET_ORDER = ["primary_all_valid", "historical_30", "non_boundary_valid",
                "excl_pure_phase_sweep", "excl_abs_sub_gain_gt_3db"]

# Values printed by the superseded HEADROOM_ANALYSIS.md (hand-typed literals in the old
# report template; never computed from any data file). Kept ONLY for the reconciliation appendix.
SUPERSEDED_REPORT_VALUES = {
    "historical_30": {
        "B_GlobalDelay": {"mean_dtp": 0.2858, "max_dtp": 2.4344},
        "C_LegacySubOnly": {"mean_dtp": 0.1440, "max_dtp": 1.8601},
        "D_GuardedPerKick": {"mean_dtp": 0.6554, "max_dtp": 2.6514},
    },
    "valid_tests": {
        "B_GlobalDelay": {"mean_dtp": 0.6395, "max_dtp": 6.0206},
        "C_LegacySubOnly": {"mean_dtp": 0.3150, "max_dtp": 5.7289},
        "D_GuardedPerKick": {"mean_dtp": 0.5360, "max_dtp": 6.0206},
    },
    "claimed_valid_scenarios": 50,
    "claimed_plotted_observations": 150,
    "claimed_d_safe_path": 19,
    "claimed_c_degraded": 30,
}


# =============================================================================
# Loading
# =============================================================================

_BOOL_COLS = {"safe_path_engaged", "baseline_is_near_zero", "is_relative_gain_valid",
              "is_tp_delta_valid", "baseline_exceeds_0dbtp", "proc_exceeds_0dbtp"}
_STR_COLS = {"exp_id", "signal_category", "signal_description", "method", "lag_semantics"}
_OPT_INT_COLS = {"d_events_detected", "d_events_corrected", "d_events_polarity_inverted"}


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def load_rows(path: str = CSV_PATH) -> List[Dict[str, Any]]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            r: Dict[str, Any] = {}
            for k, v in raw.items():
                if k in _STR_COLS:
                    r[k] = v
                elif k in _BOOL_COLS:
                    if v not in ("True", "False"):
                        raise ValueError(f"Bad boolean in column {k}: {v!r}")
                    r[k] = (v == "True")
                elif k in _OPT_INT_COLS:
                    r[k] = int(v) if v != "" else None
                else:
                    r[k] = float(v)
            rows.append(r)
    return rows


# =============================================================================
# Subsets
# =============================================================================

def _is_valid(r):
    return r["is_relative_gain_valid"] and r["is_tp_delta_valid"]


SUBSET_PREDICATES: Dict[str, Callable[[Dict[str, Any]], bool]] = {
    "primary_all_valid": lambda r: r["method"] in ACTIVE_METHODS and _is_valid(r),
    "historical_30": lambda r: r["method"] in ACTIVE_METHODS and r["signal_category"] == "historical_30_runs_seed202611",
    "non_boundary_valid": lambda r: r["method"] in ACTIVE_METHODS and _is_valid(r) and r["signal_category"] != "boundary_conditions",
    "excl_pure_phase_sweep": lambda r: r["method"] in ACTIVE_METHODS and _is_valid(r) and r["signal_category"] != "pure_phase_sweep",
    "excl_abs_sub_gain_gt_3db": lambda r: r["method"] in ACTIVE_METHODS and _is_valid(r) and abs(r["delta_sub_gain_db"]) <= EXTREME_ABS_SUB_GAIN_DB,
}


def subset(rows, name):
    return [r for r in rows if SUBSET_PREDICATES[name](r)]


# =============================================================================
# Statistics
# =============================================================================

def _r6(x):
    return None if x is None else float(round(float(x), 6))


def describe(vals: List[float]) -> Dict[str, Any]:
    a = np.asarray(vals, dtype=np.float64)
    if a.size == 0:
        return {"n": 0, "mean": None, "std": None, "median": None, "min": None, "max": None}
    return {"n": int(a.size), "mean": _r6(a.mean()), "std": _r6(a.std(ddof=1)) if a.size > 1 else None,
            "median": _r6(np.median(a)), "min": _r6(a.min()), "max": _r6(a.max())}


def method_stats(rs: List[Dict[str, Any]]) -> Dict[str, Any]:
    dtp = [r["delta_true_peak_db"] for r in rs]
    return {
        "n": len(rs),
        "n_scenarios": len({r["exp_id"] for r in rs}),
        "delta_sub_gain_db": describe([r["delta_sub_gain_db"] for r in rs]),
        "delta_true_peak_db": describe(dtp),
        "delta_headroom_db": describe([r["delta_headroom_db"] for r in rs]),
        "tp_increase_count": int(sum(1 for v in dtp if v > TP_UNCHANGED_TOL_DB)),
        "tp_decrease_count": int(sum(1 for v in dtp if v < -TP_UNCHANGED_TOL_DB)),
        "tp_unchanged_count": int(sum(1 for v in dtp if abs(v) <= TP_UNCHANGED_TOL_DB)),
        "tp_exactly_zero_count": int(sum(1 for v in dtp if v == 0.0)),
        "sub_gain_degraded_count_lt_minus_0p1db": int(sum(1 for r in rs if r["delta_sub_gain_db"] < -0.1)),
        "safe_path_engaged_count": int(sum(1 for r in rs if r["safe_path_engaged"])),
        "baseline_exceeds_0dbtp_count": int(sum(1 for r in rs if r["baseline_exceeds_0dbtp"])),
        "proc_exceeds_0dbtp_count": int(sum(1 for r in rs if r["proc_exceeds_0dbtp"])),
    }


def corr(x: List[float], y: List[float]) -> Dict[str, Any]:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    out = {"n": int(x.size), "pearson_r": None, "pearson_p": None, "spearman_rho": None, "spearman_p": None}
    if x.size < 3 or np.std(x) == 0 or np.std(y) == 0:
        out["note"] = "undefined (n<3 or zero variance)"
        return out
    pr = stats.pearsonr(x, y)
    sr = stats.spearmanr(x, y)
    out.update({"pearson_r": _r6(pr[0]), "pearson_p": float(pr[1]),
                "spearman_rho": _r6(sr[0]), "spearman_p": float(sr[1])})
    return out


def corr_block(rs) -> Dict[str, Any]:
    block = {"pooled_BCD": corr([r["delta_sub_gain_db"] for r in rs], [r["delta_true_peak_db"] for r in rs])}
    for m in ACTIVE_METHODS:
        mr = [r for r in rs if r["method"] == m]
        block[m] = corr([r["delta_sub_gain_db"] for r in mr], [r["delta_true_peak_db"] for r in mr])
    return block


def cluster_bootstrap(rs) -> Dict[str, Any]:
    """Resamples whole scenarios (3 dependent observations each) with replacement."""
    by_scen: Dict[str, List[Dict[str, Any]]] = {}
    for r in rs:
        by_scen.setdefault(r["exp_id"], []).append(r)
    keys = sorted(by_scen)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    pear, spear = [], []
    for _ in range(BOOTSTRAP_N):
        pick = rng.integers(0, len(keys), len(keys))
        x, y = [], []
        for i in pick:
            for r in by_scen[keys[i]]:
                x.append(r["delta_sub_gain_db"])
                y.append(r["delta_true_peak_db"])
        if np.std(x) == 0 or np.std(y) == 0:
            continue
        pear.append(stats.pearsonr(x, y)[0])
        spear.append(stats.spearmanr(x, y)[0])
    return {
        "resamples": BOOTSTRAP_N, "seed": BOOTSTRAP_SEED, "unit": "scenario (exp_id)",
        "pearson_ci95": [_r6(np.percentile(pear, 2.5)), _r6(np.percentile(pear, 97.5))],
        "spearman_ci95": [_r6(np.percentile(spear, 2.5)), _r6(np.percentile(spear, 97.5))],
    }


def leave_one_scenario_out(rs) -> Dict[str, Any]:
    scen = sorted({r["exp_id"] for r in rs})
    res = []
    for s in scen:
        k = [r for r in rs if r["exp_id"] != s]
        c = corr([r["delta_sub_gain_db"] for r in k], [r["delta_true_peak_db"] for r in k])
        res.append((s, c["pearson_r"], c["spearman_rho"]))
    pmin = min(res, key=lambda t: t[1])
    pmax = max(res, key=lambda t: t[1])
    smin = min(res, key=lambda t: t[2])
    smax = max(res, key=lambda t: t[2])
    return {
        "pearson_min": {"value": pmin[1], "dropped": pmin[0]},
        "pearson_max": {"value": pmax[1], "dropped": pmax[0]},
        "spearman_min": {"value": smin[2], "dropped": smin[0]},
        "spearman_max": {"value": smax[2], "dropped": smax[0]},
    }


def verdict(summary_corr: Dict[str, Any], boot: Dict[str, Any], loo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decision rule (declared in the report):
      MONOTONIC     : pooled Spearman >= 0.8 AND every per-method Spearman >= 0.8.
      INCONCLUSIVE  : pooled Spearman cluster-bootstrap 95% CI contains 0, OR the sign of
                      pooled Spearman flips under leave-one-scenario-out.
      VARIABLE      : otherwise (a dependence exists but it is not monotonic and/or differs by method).
    """
    pooled = summary_corr["pooled_BCD"]["spearman_rho"]
    per = {m: summary_corr[m]["spearman_rho"] for m in ACTIVE_METHODS}
    lo, hi = boot["spearman_ci95"]
    flips = (np.sign(loo["spearman_min"]["value"]) != np.sign(loo["spearman_max"]["value"]))
    if pooled is not None and pooled >= 0.8 and all(v is not None and v >= 0.8 for v in per.values()):
        v = "MONOTONIC"
    elif lo <= 0.0 <= hi or flips:
        v = "INCONCLUSIVE"
    else:
        v = "VARIABLE"
    signs = {m: (None if per[m] is None else ("positive" if per[m] > 0 else "negative" if per[m] < 0 else "zero"))
             for m in ACTIVE_METHODS}
    return {"pooled": v, "per_method_spearman_sign": signs,
            "method_signs_disagree": len({s for s in signs.values() if s}) > 1}


# =============================================================================
# Summary
# =============================================================================

def build_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    scen_first: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        scen_first.setdefault(r["exp_id"], r)

    # Identity / integrity checks computed from the CSV
    max_hr_identity_err = max(abs(r["delta_headroom_db"] + r["delta_true_peak_db"]) for r in rows)
    max_tp_identity_err = max(abs(r["true_peak_proc_dbtp"] - r["true_peak_baseline_dbtp"] - r["delta_true_peak_db"]) for r in rows)
    a_nonzero = [r["exp_id"] for r in rows if r["method"] == "A_Baseline" and
                 (r["delta_true_peak_db"] != 0 or r["delta_sub_gain_db"] != 0)]

    primary = subset(rows, "primary_all_valid")
    primary_ids = {r["exp_id"] for r in primary}
    non_boundary_ids = {r["exp_id"] for r in subset(rows, "non_boundary_valid")}

    excluded = []
    for sid, r in scen_first.items():
        if sid not in primary_ids:
            reasons = []
            if not r["is_relative_gain_valid"]:
                reasons.append(f"near-zero baseline sub RMS ({r['sub_rms_baseline_dbfs']:.4f} dBFS <= {MEASUREMENT_FLOOR_DB} dBFS)")
            if not r["is_tp_delta_valid"]:
                reasons.append(f"baseline true peak at/below floor ({r['true_peak_baseline_dbtp']:.4f} dBTP)")
            excluded.append({"exp_id": sid, "signal_category": r["signal_category"], "reasons": reasons})

    previously_dropped = sorted(primary_ids - non_boundary_ids)

    # Points that the superseded figure's fixed axis limits (x in [-2,7], y in [-3,7]) hid
    hidden_old_axes = [{"exp_id": r["exp_id"], "method": r["method"], "delta_sub_gain_db": r["delta_sub_gain_db"],
                        "delta_true_peak_db": r["delta_true_peak_db"]}
                       for r in subset(rows, "non_boundary_valid")
                       if not (-2.0 <= r["delta_sub_gain_db"] <= 7.0 and -3.0 <= r["delta_true_peak_db"] <= 7.0)]

    special_cases = []
    for r in rows:
        if not _is_valid(r):
            special_cases.append({k: r[k] for k in (
                "exp_id", "method", "safe_path_engaged", "applied_lag_ms", "applied_polarity",
                "sub_rms_baseline_dbfs", "sub_rms_proc_dbfs", "true_peak_baseline_dbtp", "true_peak_proc_dbtp",
                "true_peak_baseline_linear", "true_peak_proc_linear")})

    subsets_out = {}
    for name in SUBSET_ORDER:
        rs = subset(rows, name)
        subsets_out[name] = {
            "criterion": FILTER_CRITERIA["subsets"][name],
            "n_observations": len(rs),
            "n_scenarios": len({r["exp_id"] for r in rs}),
            "per_method": {m: method_stats([r for r in rs if r["method"] == m]) for m in ACTIVE_METHODS},
            "correlations": corr_block(rs),
        }

    boot = cluster_bootstrap(primary)
    loo = leave_one_scenario_out(primary)
    v = verdict(subsets_out["primary_all_valid"]["correlations"], boot, loo)

    # Data-derived example cases
    def pick(rs, key, n=3, reverse=True):
        return [{"exp_id": r["exp_id"], "method": r["method"], "delta_sub_gain_db": r["delta_sub_gain_db"],
                 "delta_true_peak_db": r["delta_true_peak_db"]}
                for r in sorted(rs, key=key, reverse=reverse)[:n]]

    gain_without_tp_cost = [r for r in primary if r["delta_sub_gain_db"] >= 0.5 and r["delta_true_peak_db"] <= TP_UNCHANGED_TOL_DB]
    tp_cost_small_gain = [r for r in primary if r["delta_true_peak_db"] > 0.5 and 0.0 <= r["delta_sub_gain_db"] < 0.5]
    loss_both = [r for r in primary if r["delta_sub_gain_db"] < -0.1 and r["delta_true_peak_db"] < -TP_UNCHANGED_TOL_DB]

    exp00 = next(r for r in rows if r["exp_id"] == "EXP_PHASE_000" and r["method"] == "A_Baseline")

    return {
        "schema_version": 1,
        "source_csv": os.path.basename(CSV_PATH),
        "source_csv_sha256": sha256_of(CSV_PATH),
        "n_rows": len(rows),
        "n_scenarios": len(scen_first),
        "n_scenarios_relative_valid": int(sum(1 for r in scen_first.values() if r["is_relative_gain_valid"])),
        "n_scenarios_near_zero": int(sum(1 for r in scen_first.values() if r["baseline_is_near_zero"])),
        "filter_criteria": FILTER_CRITERIA,
        "integrity_checks": {
            "max_abs_headroom_identity_error_db": _r6(max_hr_identity_err),
            "max_abs_tp_delta_identity_error_db": _r6(max_tp_identity_err),
            "method_a_nonzero_delta_scenarios": a_nonzero,
            "clipping_applied_in_pipeline": False,
            "clipping_note": "No np.clip / limiter in synthetic_signals, methods, remaster_engine.align_sub_phase or harness; float samples above 1.0 FS are preserved, so dBTP > 0 values are real over-ceiling measurements, not clipped values.",
            "phase000_baseline_tp_dbtp": exp00["true_peak_baseline_dbtp"],
            "phase000_expected_tp_dbtp": 0.0,
            "meter_note": "EXP_PHASE_000 is 0.5 sin + 0.5 sin = 1.0 FS peak (0.000 dBTP analytically); the 4x resample_poly meter reads the stored value, i.e. its overshoot ripple on a stationary 50 Hz sine.",
        },
        "figure6": {
            "subset": "primary_all_valid",
            "n_observations_plotted": len(primary),
            "n_scenarios_plotted": len(primary_ids),
            "methods_plotted": ACTIVE_METHODS,
        },
        "excluded_scenarios": sorted(excluded, key=lambda e: e["exp_id"]),
        "previously_dropped_by_undocumented_boundary_filter": previously_dropped,
        "points_hidden_by_superseded_axis_limits": hidden_old_axes,
        "near_zero_special_cases": special_cases,
        "subsets": subsets_out,
        "primary_bootstrap": boot,
        "primary_leave_one_scenario_out": loo,
        "verdict": v,
        "examples": {
            "largest_tp_increase": pick(primary, lambda r: r["delta_true_peak_db"]),
            "largest_tp_decrease": pick(primary, lambda r: r["delta_true_peak_db"], reverse=False),
            "sub_gain_ge_0p5db_without_tp_increase_count": len(gain_without_tp_cost),
            "sub_gain_ge_0p5db_without_tp_increase_by_method": {m: sum(1 for r in gain_without_tp_cost if r["method"] == m) for m in ACTIVE_METHODS},
            "tp_increase_gt_0p5db_with_sub_gain_lt_0p5db_count": len(tp_cost_small_gain),
            "tp_increase_gt_0p5db_with_sub_gain_lt_0p5db": pick(tp_cost_small_gain, lambda r: r["delta_true_peak_db"], n=5),
            "sub_loss_and_tp_decrease_count": len(loss_both),
            "sub_loss_and_tp_decrease_by_method": {m: sum(1 for r in loss_both if r["method"] == m) for m in ACTIVE_METHODS},
        },
        "superseded_report_values": SUPERSEDED_REPORT_VALUES,
        "all_rows_counts": {
            "d_safe_path_all": int(sum(1 for r in rows if r["method"] == "D_GuardedPerKick" and r["safe_path_engaged"])),
            "c_degraded_all": int(sum(1 for r in rows if r["method"] == "C_LegacySubOnly" and r["delta_sub_gain_db"] < -0.1)),
            "d_rows_with_any_polarity_inverted_event": int(sum(1 for r in rows if r["method"] == "D_GuardedPerKick" and (r["d_events_polarity_inverted"] or 0) > 0)),
        },
        "cross_check_measurements_csv": cross_check_measurements_csv(),
    }


# =============================================================================
# Figure 6
# =============================================================================

MARKERS = {
    "B_GlobalDelay": ("#2563EB", "s", 42),
    "C_LegacySubOnly": ("#C0392B", "^", 48),
    "D_GuardedPerKick": ("#0E6251", "D", 40),
}


def render_figure6(rows, summary):
    primary = subset(rows, "primary_all_valid")
    corrs = summary["subsets"]["primary_all_valid"]["correlations"]
    n_obs = summary["figure6"]["n_observations_plotted"]
    n_scen = summary["figure6"]["n_scenarios_plotted"]

    fig, axes = plt.subplots(1, 2, figsize=(15.0, 7.2), dpi=300)
    xs = np.array([r["delta_sub_gain_db"] for r in primary])
    ys = np.array([r["delta_true_peak_db"] for r in primary])

    # Zoom window from data (central 90% of each axis, padded), never used for statistics
    zx = (min(-0.5, np.percentile(xs, 2) - 0.3), max(0.5, np.percentile(xs, 95) + 0.3))
    zy = (min(-0.5, np.percentile(ys, 2) - 0.3), max(0.5, np.percentile(ys, 95) + 0.3))
    outside = int(np.sum((xs < zx[0]) | (xs > zx[1]) | (ys < zy[0]) | (ys > zy[1])))

    for ax, title, lims in [
        (axes[0], f"(a) All {n_obs} plotted observations (full range, no points hidden)", None),
        (axes[1], f"(b) Zoom on central region ({outside} of {n_obs} points lie outside this view)", (zx, zy)),
    ]:
        for m in ACTIVE_METHODS:
            col, mk, sz = MARKERS[m]
            mr = [r for r in primary if r["method"] == m]
            c = corrs[m]
            rho = "n/a" if c["spearman_rho"] is None else f"{c['spearman_rho']:+.3f}"
            ax.scatter([r["delta_sub_gain_db"] for r in mr], [r["delta_true_peak_db"] for r in mr],
                       color=col, marker=mk, s=sz, alpha=0.70, edgecolors="white", linewidths=0.4,
                       label=f"{METHOD_LABELS[m]}  (n={len(mr)}, Spearman ρ={rho})")
        ax.axhline(0.0, color="#475569", linestyle="--", linewidth=1.0, label="Zero reference (ΔTP = 0 dB / ΔE = 0 dB)")
        ax.axvline(0.0, color="#475569", linestyle="--", linewidth=1.0)
        if lims is None:
            lo = min(xs.min(), ys.min()) - 0.5
            hi = max(xs.max(), ys.max()) + 0.5
            ax.set_xlim(lo, hi)
            ax.set_ylim(lo, hi)
        else:
            ax.set_xlim(*lims[0])
            ax.set_ylim(*lims[1])
        x0, x1 = ax.get_xlim()
        ax.plot([x0, x1], [x0, x1], linestyle=":", color="#B45309", linewidth=1.1,
                label="Reference ΔTP = ΔE_sub (not a fitted model)")
        ax.set_xlabel("Sub-band (<100 Hz) RMS change ΔE_sub (dB re. Method A)", fontsize=10.5)
        ax.set_ylabel("True-peak change ΔTP (dB re. Method A)\n[headroom change to 0 dBTP = −ΔTP]", fontsize=10.5)
        ax.set_title(title, fontsize=10.5, loc="left")
        ax.grid(True, alpha=0.35)

    pc = corrs["pooled_BCD"]
    boot = summary["primary_bootstrap"]
    axes[0].text(0.02, 0.98,
                 f"Pooled B+C+D (n={pc['n']}):\n"
                 f"Pearson r = {pc['pearson_r']:+.3f}  [95% CI {boot['pearson_ci95'][0]:+.2f}, {boot['pearson_ci95'][1]:+.2f}]\n"
                 f"Spearman ρ = {pc['spearman_rho']:+.3f}  [95% CI {boot['spearman_ci95'][0]:+.2f}, {boot['spearman_ci95'][1]:+.2f}]\n"
                 f"(scenario-cluster bootstrap, {boot['resamples']} resamples)\n"
                 f"Verdict: {summary['verdict']['pooled']}",
                 transform=axes[0].transAxes, va="top", fontsize=8.6, family="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#F8FAFC", ec="#CBD5E1"))
    axes[1].legend(loc="lower right", fontsize=7.8, framealpha=0.95)

    fig.suptitle(f"Figure 6 — The Price of Alignment: sub-band energy change vs true-peak change\n"
                 f"Experiment EXP_HEADROOM · {n_scen} valid synthetic scenarios × 3 active methods (B, C, D) = {n_obs} observations",
                 fontsize=12, fontweight="bold", x=0.01, ha="left")
    fig.text(0.01, 0.005,
             "SYNTHETIC TEST SIGNALS ONLY (48 kHz, deterministic). No normalization or limiting. True peak: 4× polyphase oversampling (scipy resample_poly), not a certified BS.1770 meter.\n"
             f"Excluded: {len(summary['excluded_scenarios'])} near-zero-reference scenarios (sub RMS ≤ {MEASUREMENT_FLOOR_DB:.0f} dBFS), reported separately as special cases. "
             "Method A is the reference (0,0). Observations within a scenario share a baseline and are not independent.\n"
             "Higher sub-band energy is NOT evidence of better sound; this figure measures level and peak only. Generated by headroom_analysis.py from headroom_measurements.csv.",
             fontsize=7.8, style="italic", color="#475569", va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))

    os.makedirs(FIGURES_DIR, exist_ok=True)
    png = os.path.join(FIGURES_DIR, "fig6_price_of_alignment.png")
    svg = os.path.join(FIGURES_DIR, "fig6_price_of_alignment.svg")
    plt.rcParams["svg.hashsalt"] = "pharmakon-fig6"
    fig.savefig(png, dpi=300, facecolor="white", metadata={"Software": None})
    fig.savefig(svg, format="svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)
    summary["figure6"]["zoom_x_db"] = [_r6(zx[0]), _r6(zx[1])]
    summary["figure6"]["zoom_y_db"] = [_r6(zy[0]), _r6(zy[1])]
    summary["figure6"]["points_outside_zoom"] = outside
    return png, svg


# =============================================================================
# Report
# =============================================================================

def _f(x, nd=4, sign=True):
    if x is None:
        return "n/a"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def stats_table(summary) -> str:
    lines = ["<!-- STATS_TABLE:BEGIN -->",
             "| Subset | Method | n | mean ΔE_sub (dB) | mean ΔTP (dB) | median ΔTP (dB) | min ΔTP (dB) | max ΔTP (dB) | mean Δheadroom (dB) | TP ↑ | TP ↓ | TP = | safe-path |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in SUBSET_ORDER:
        for m in ACTIVE_METHODS:
            ms = summary["subsets"][s]["per_method"][m]
            e, t, h = ms["delta_sub_gain_db"], ms["delta_true_peak_db"], ms["delta_headroom_db"]
            lines.append(f"| `{s}` | `{m}` | {ms['n']} | {_f(e['mean'])} | {_f(t['mean'])} | {_f(t['median'])} | "
                         f"{_f(t['min'])} | {_f(t['max'])} | {_f(h['mean'])} | {ms['tp_increase_count']} | "
                         f"{ms['tp_decrease_count']} | {ms['tp_unchanged_count']} | {ms['safe_path_engaged_count']} |")
    lines.append("<!-- STATS_TABLE:END -->")
    return "\n".join(lines)


def corr_table(summary) -> str:
    lines = ["<!-- CORR_TABLE:BEGIN -->",
             "| Subset | Group | n | Pearson r | Spearman ρ |",
             "|---|---|---:|---:|---:|"]
    for s in SUBSET_ORDER:
        for g in ["pooled_BCD"] + ACTIVE_METHODS:
            c = summary["subsets"][s]["correlations"][g]
            lines.append(f"| `{s}` | `{g}` | {c['n']} | {_f(c['pearson_r'], 3)} | {_f(c['spearman_rho'], 3)} |")
    lines.append("<!-- CORR_TABLE:END -->")
    return "\n".join(lines)


def reconciliation_table(summary) -> str:
    old = summary["superseded_report_values"]
    hist = summary["subsets"]["historical_30"]["per_method"]
    nb = summary["subsets"]["non_boundary_valid"]["per_method"]
    lines = ["| Statistic | Method | Superseded report (hand-typed) | Recomputed from CSV | Difference |",
             "|---|---|---:|---:|---:|"]
    for label, src, key in [("Historical 30-run mean ΔTP", hist, ("historical_30", "mean_dtp", "mean")),
                            ("Historical 30-run max ΔTP", hist, ("historical_30", "max_dtp", "max")),
                            ("'Valid tests' mean ΔTP (non-boundary filter)", nb, ("valid_tests", "mean_dtp", "mean")),
                            ("'Valid tests' max ΔTP (non-boundary filter)", nb, ("valid_tests", "max_dtp", "max"))]:
        for m in ACTIVE_METHODS:
            ov = old[key[0]][m][key[1]]
            nv = src[m]["delta_true_peak_db"][key[2]]
            lines.append(f"| {label} | `{m}` | {ov:+.4f} | {nv:+.4f} | {nv - ov:+.4f} |")
    d_sp_valid = summary["subsets"]["primary_all_valid"]["per_method"]["D_GuardedPerKick"]["safe_path_engaged_count"]
    c_deg_hist = hist["C_LegacySubOnly"]["sub_gain_degraded_count_lt_minus_0p1db"]
    c_deg_valid = summary["subsets"]["primary_all_valid"]["per_method"]["C_LegacySubOnly"]["sub_gain_degraded_count_lt_minus_0p1db"]
    allc = summary["all_rows_counts"]
    lines += [
        f"| Valid scenarios in Figure 6 | all | {old['claimed_valid_scenarios']} | {summary['figure6']['n_scenarios_plotted']} | — |",
        f"| Plotted active observations | all | {old['claimed_plotted_observations']} | {summary['figure6']['n_observations_plotted']} | — |",
        f"| Method D safe-path engagements (subset unstated) | `D_GuardedPerKick` | {old['claimed_d_safe_path']} | all 54: {allc['d_safe_path_all']}; valid: {d_sp_valid} | — |",
        f"| Method C degraded, ΔE_sub < −0.1 dB (subset unstated) | `C_LegacySubOnly` | {old['claimed_c_degraded']} | all 54: {allc['c_degraded_all']}; valid: {c_deg_valid}; historical: {c_deg_hist} | — |",
    ]
    return "\n".join(lines)


def cross_check_measurements_csv() -> Optional[Dict[str, Any]]:
    """Independent pipeline check: run_experiments.py logged the same historical suite in measurements.csv."""
    path = os.path.join(CURRENT_DIR, "measurements.csv")
    if not os.path.exists(path):
        return None
    out: Dict[str, Any] = {"source": "measurements.csv", "source_sha256": sha256_of(path), "historical_30": {}}
    with open(path, newline="", encoding="utf-8") as f:
        rs = [r for r in csv.DictReader(f) if r["signal_category"] == "historical_30_runs_seed202611"]
    for m in ACTIVE_METHODS:
        mr = [r for r in rs if r["method"] == m]
        out["historical_30"][m] = {
            "n": len(mr),
            "mean_delta_sub_gain_db": _r6(np.mean([float(r["delta_sub_gain_db"]) for r in mr])),
            "mean_delta_true_peak_db": _r6(np.mean([float(r["delta_true_peak_db"]) for r in mr])),
        }
    return out


def cross_check_table(summary) -> str:
    cc = summary.get("cross_check_measurements_csv")
    if not cc:
        return "_measurements.csv not found; cross-check skipped._"
    hist = summary["subsets"]["historical_30"]["per_method"]
    lines = ["| Method | mean ΔE_sub: headroom CSV | mean ΔE_sub: measurements.csv | mean ΔTP: headroom CSV | mean ΔTP: measurements.csv |",
             "|---|---:|---:|---:|---:|"]
    for m in ACTIVE_METHODS:
        c = cc["historical_30"][m]
        lines.append(f"| `{m}` | {_f(hist[m]['delta_sub_gain_db']['mean'])} | {_f(c['mean_delta_sub_gain_db'])} | "
                     f"{_f(hist[m]['delta_true_peak_db']['mean'])} | {_f(c['mean_delta_true_peak_db'])} |")
    return "\n".join(lines)


def write_report(summary) -> str:
    p = summary["subsets"]["primary_all_valid"]
    h = summary["subsets"]["historical_30"]
    pc = p["correlations"]["pooled_BCD"]
    boot = summary["primary_bootstrap"]
    loo = summary["primary_leave_one_scenario_out"]
    v = summary["verdict"]
    ex = summary["examples"]
    ic = summary["integrity_checks"]
    hd = h["per_method"]

    excl_lines = "\n".join(f"| `{e['exp_id']}` | {e['signal_category']} | {'; '.join(e['reasons'])} |"
                           for e in summary["excluded_scenarios"])
    special_lines = "\n".join(
        f"| `{s['exp_id']}` | `{s['method']}` | {s['safe_path_engaged']} | {s['applied_lag_ms']:.3f} | {s['applied_polarity']:+.0f} | "
        f"{s['sub_rms_baseline_dbfs']:.2f} | {s['sub_rms_proc_dbfs']:.2f} | {s['true_peak_baseline_dbtp']:.2f} | "
        f"{s['true_peak_proc_dbtp']:.2f} | {s['true_peak_proc_linear']:.6f} |"
        for s in summary["near_zero_special_cases"])
    hidden = ", ".join(f"`{x['exp_id']}`/{x['method']} ({x['delta_sub_gain_db']:+.2f}, {x['delta_true_peak_db']:+.2f})"
                       for x in summary["points_hidden_by_superseded_axis_limits"]) or "none"
    big_up = ", ".join(f"`{x['exp_id']}`/{x['method']} (ΔE {x['delta_sub_gain_db']:+.2f}, ΔTP {x['delta_true_peak_db']:+.2f})"
                       for x in ex["largest_tp_increase"])
    big_down = ", ".join(f"`{x['exp_id']}`/{x['method']} (ΔE {x['delta_sub_gain_db']:+.2f}, ΔTP {x['delta_true_peak_db']:+.2f})"
                         for x in ex["largest_tp_decrease"])
    cost_small = ", ".join(f"`{x['exp_id']}`/{x['method']} (ΔE {x['delta_sub_gain_db']:+.2f}, ΔTP {x['delta_true_peak_db']:+.2f})"
                           for x in ex["tp_increase_gt_0p5db_with_sub_gain_lt_0p5db"]) or "none"
    per_sign = ", ".join(f"{m}: {s}" for m, s in v["per_method_spearman_sign"].items())

    sens_rows = []
    for s in SUBSET_ORDER:
        c = summary["subsets"][s]["correlations"]["pooled_BCD"]
        sens_rows.append(f"| `{s}` | {c['n']} | {_f(c['pearson_r'], 3)} | {_f(c['spearman_rho'], 3)} |")
    sens = "\n".join(sens_rows)

    n_base_over = sum(summary["subsets"]["primary_all_valid"]["per_method"][m]["baseline_exceeds_0dbtp_count"] for m in ACTIVE_METHODS) // 3

    report = f"""# The Price of Alignment — True-Peak & Headroom Cost of Kick/Bass Phase Alignment

**Document ID:** PHARMAKON-HEADROOM-2026-04 (reconciled revision)
**Status:** Research draft for *Death in the Club*. Synthetic signals only. Not a product claim.
**Generated by:** `headroom_analysis.py` — every number below is formatted from `headroom_summary.json`, which is computed only from `headroom_measurements.csv`.
**Source CSV SHA-256:** `{summary['source_csv_sha256']}`
**Rows / scenarios:** {summary['n_rows']} rows, {summary['n_scenarios']} scenarios × 4 methods.
**Guard test:** `test_headroom_reconciliation.py` fails if any statistic in this file differs from an independent recomputation from the CSV.

> [!IMPORTANT]
> This revision replaces a report whose true-peak statistics were hand-typed into the generator template and never computed from the data. See **Appendix A — Reconciliation**. The superseded files are preserved in `original_pre_reconciliation/`.

---

## 1. Research question and answer

**Question:** What is the true-peak and headroom cost of increasing sub-band energy through kick/bass phase alignment?

**Answer from this dataset:** the pooled relationship between sub-band RMS change (ΔE_sub) and true-peak change (ΔTP) is classified **{v['pooled']}** under the decision rule in §4. Per-method Spearman signs: {per_sign}{' — the methods disagree in sign, so there is no single method-independent “price”.' if v['method_signs_disagree'] else '.'}

- Pooled Figure 6 set (n = {pc['n']}): Pearson r = {_f(pc['pearson_r'], 3)} (95% CI {_f(boot['pearson_ci95'][0], 2)} to {_f(boot['pearson_ci95'][1], 2)}), Spearman ρ = {_f(pc['spearman_rho'], 3)} (95% CI {_f(boot['spearman_ci95'][0], 2)} to {_f(boot['spearman_ci95'][1], 2)}); scenario-cluster bootstrap, {boot['resamples']} resamples, seed {boot['seed']}.
- The large gap between Pearson and Spearman indicates that the linear coefficient is dominated by a few large-magnitude observations (see §4 sensitivity).
- On the historical 30-run subset, mean ΔTP is {_f(hd['B_GlobalDelay']['delta_true_peak_db']['mean'])} dB (B), {_f(hd['C_LegacySubOnly']['delta_true_peak_db']['mean'])} dB (C) and {_f(hd['D_GuardedPerKick']['delta_true_peak_db']['mean'])} dB (D), with mean ΔE_sub {_f(hd['B_GlobalDelay']['delta_sub_gain_db']['mean'])} / {_f(hd['C_LegacySubOnly']['delta_sub_gain_db']['mean'])} / {_f(hd['D_GuardedPerKick']['delta_sub_gain_db']['mean'])} dB.
- {ex['sub_gain_ge_0p5db_without_tp_increase_count']} observations gained ≥ 0.5 dB sub-band RMS with no true-peak increase (by method: {ex['sub_gain_ge_0p5db_without_tp_increase_by_method']}); {ex['tp_increase_gt_0p5db_with_sub_gain_lt_0p5db_count']} observations raised true peak by > 0.5 dB while gaining < 0.5 dB sub RMS.

Higher sub-band energy is **not** evidence of better sound. This experiment measures level and peak only; it contains no perceptual evaluation.

---

## 2. Definitions

- **ΔE_sub (dB)** = 20·log10(RMS_proc / RMS_base) of the drums + bass sum after a 4th-order Butterworth low-pass at 100 Hz applied forward-backward (`sosfiltfilt`), whole 3 s signal, both channels.
- **True peak (dBTP)** = 20·log10 of the maximum absolute sample after 4× `scipy.signal.resample_poly` oversampling of each channel. This is an approximation; it is **not** a certified ITU-R BS.1770-4 meter (an earlier claim of compliance is withdrawn).
- **ΔTP (dB)** = TP_proc − TP_base. **Headroom** = 0 dBTP − TP. **Δheadroom** = −ΔTP (identity verified: max error {ic['max_abs_headroom_identity_error_db']} dB).
- **TP class:** increase if ΔTP > +{TP_UNCHANGED_TOL_DB} dB, decrease if ΔTP < −{TP_UNCHANGED_TOL_DB} dB, otherwise unchanged.
- **Applied lag:** B and C report one global lag. **D reports the mean absolute per-event shift over all detected kick events (rejected events count as 0 ms)**; it has no single lag. D's polarity column is −1 only if every event was inverted; per-event inversions are counted in `d_events_polarity_inverted` (this metadata was not recorded in the superseded CSV, whose D polarity was a default of +1).

---

## 3. Filter criteria and exclusions

| Criterion | Definition |
|---|---|
| Near-zero reference | {FILTER_CRITERIA['near_zero_definition']} |
| Relative-gain valid | {FILTER_CRITERIA['relative_gain_valid']} |
| ΔTP valid | {FILTER_CRITERIA['tp_delta_valid']} |
| Observations | {FILTER_CRITERIA['active_methods']} |
| **Figure 6 / headline set** | {FILTER_CRITERIA['subsets']['primary_all_valid']} |
| Axis clipping | {FILTER_CRITERIA['axis_clipping']} |

**Result:** {summary['n_scenarios_relative_valid']} of {summary['n_scenarios']} scenarios are valid → **{summary['figure6']['n_scenarios_plotted']} scenarios × 3 active methods = {summary['figure6']['n_observations_plotted']} plotted observations.** No further filter is applied to Figure 6 or to the headline correlations.

Excluded scenarios (all four methods preserved in the CSV and listed in §6):

| exp_id | Category | Reason |
|---|---|---|
{excl_lines}

---

## 4. Correlation, sensitivity and verdict

**Decision rule** (applied to the Figure 6 set): MONOTONIC if pooled Spearman ≥ 0.8 and every per-method Spearman ≥ 0.8; INCONCLUSIVE if the pooled Spearman bootstrap 95% CI contains 0 or its sign flips under leave-one-scenario-out; otherwise VARIABLE.

Leave-one-scenario-out on the Figure 6 set: Pearson ranges {_f(loo['pearson_min']['value'], 3)} (dropping `{loo['pearson_min']['dropped']}`) to {_f(loo['pearson_max']['value'], 3)} (dropping `{loo['pearson_max']['dropped']}`); Spearman ranges {_f(loo['spearman_min']['value'], 3)} (dropping `{loo['spearman_min']['dropped']}`) to {_f(loo['spearman_max']['value'], 3)} (dropping `{loo['spearman_max']['dropped']}`).

Pooled B+C+D correlation by subset (sensitivity to extreme values and to the subset definition):

| Subset | n | Pearson r | Spearman ρ |
|---|---:|---:|---:|
{sens}

Full correlation table (pooled and per method):

{corr_table(summary)}

Interpretation constraints: the three observations from one scenario share a baseline and are not independent, so nominal p-values are not reported as evidence; the scenario-cluster bootstrap is the uncertainty estimate used. The suite composition (e.g. idealised pure-sine phase sweeps) is a design choice, not a population sample, so pooled coefficients describe this test set only.

---

## 5. Headroom statistics (all subsets, all computed from the CSV)

{stats_table(summary)}

Data-derived extremes in the Figure 6 set:
- Largest true-peak increases: {big_up}.
- Largest true-peak decreases: {big_down}.
- True-peak increase > 0.5 dB with sub gain < 0.5 dB: {cost_small}.
- Sub-band loss (< −0.1 dB) together with a true-peak decrease: {ex['sub_loss_and_tp_decrease_count']} observations (by method: {ex['sub_loss_and_tp_decrease_by_method']}). A lower true peak here reflects lost signal, not a benefit.

---

## 6. True-peak measurement checks

1. **Identities:** Δheadroom = −ΔTP (max error {ic['max_abs_headroom_identity_error_db']} dB); ΔTP = TP_proc − TP_base (max rounding error {ic['max_abs_tp_delta_identity_error_db']} dB); Method A has zero deltas in every scenario (violations: {ic['method_a_nonzero_delta_scenarios'] or 'none'}).
2. **Unchanged peaks:** ΔTP is a global maximum over 3 s. A method that alters only part of the signal (D modifies kick windows only) leaves ΔTP = 0 whenever the global peak lies outside the modified region. ΔTP = 0 therefore does **not** mean local peaks inside corrected windows are unchanged; this experiment does not measure local window peaks.
3. **Negative deltas** are reported as measured and are included in all means. They arise both from destructive changes (C's band-split recombination) and from realignments that reduce crest coincidence.
4. **Clipping:** {ic['clipping_note']} In the Figure 6 set, {n_base_over} of {summary['figure6']['n_scenarios_plotted']} baselines already exceed 0 dBTP (all historical, delay-sweep and melodic scenarios). Their headroom is negative before any processing; if exported to fixed-point these signals would clip. The test signals were not level-normalised, which limits the absolute headroom interpretation; ΔTP remains a valid relative measurement because no clipping occurs in the float pipeline.
5. **Meter ripple:** EXP_PHASE_000 sums to an analytic 1.0 FS peak (0.0000 dBTP) but reads {ic['phase000_baseline_tp_dbtp']:+.4f} dBTP. The ±{TP_UNCHANGED_TOL_DB} dB "unchanged" tolerance is set just above this observed meter ripple.
6. **Near-zero references:** relative ΔE_sub and ΔTP are undefined when the baseline is at the floor (dB values are clamped at −120). These rows are excluded from every aggregate and reported in absolute terms:

| exp_id | Method | safe-path | lag (ms) | pol | sub RMS base (dBFS) | sub RMS proc (dBFS) | TP base (dBTP) | TP proc (dBTP) | TP proc (linear FS) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
{special_lines}

---

## 7. Limitations

- Synthetic, deterministic signals only; no real multitracks; no listening tests.
- True-peak meter is a 4× `resample_poly` approximation, not a certified BS.1770 implementation.
- Test signals are not level-normalised; many baselines exceed 0 dBTP.
- Global ΔTP cannot detect local peak changes inside D's corrected windows.
- Observations within a scenario are dependent; pooled correlations depend on suite composition.
- Method D is an experimental research prototype, not the existing PHARMAKON algorithm.
- No mechanism claims (e.g. transient-collision explanations or fader-compensation rules) are made here; the superseded report's mechanism narrative and "−2 dB fader rule" were not supported by any measurement in this dataset and have been removed.

---

## Appendix A — Reconciliation with the superseded report

**Root cause.** In the superseded `headroom_experiment.py`, `write_headroom_analysis_report()` computed a `stats_by_method` dictionary from the rows but never used it: the report's statistics table and executive summary were hand-typed numeric literals inside the f-string template. The Figure 6 annotation text ("150 Valid Runs") and title ("50 valid synthetic scenarios") were also hard-coded strings. The mean ΔE_sub literals happened to match the data; the true-peak literals did not originate from any computation or file (a search of every CSV, JSON, Markdown and Python file in the research directory finds them only in the old template and the report it produced). The CSV values were correct; the report was wrong.

**Count reconciliation.** {summary['n_scenarios_relative_valid']} scenarios are relative-gain valid ({summary['n_scenarios_relative_valid'] * 3} active observations). The superseded figure additionally dropped every `boundary_conditions` scenario without documentation, removing the valid {', '.join('`' + x + '`' for x in summary['previously_dropped_by_undocumented_boundary_filter'])}, which left {summary['subsets']['non_boundary_valid']['n_scenarios']} scenarios / {summary['subsets']['non_boundary_valid']['n_observations']} observations — matching neither the claimed 50/150 nor the 51/153 valid set. Its fixed axis limits (x −2…7 dB, y −3…7 dB) further hid: {hidden}. Its correlation annotation was computed on the {summary['subsets']['non_boundary_valid']['n_observations']}-point set while being labelled as 150. This revision plots all {summary['figure6']['n_observations_plotted']} valid observations and states the subset in the figure.

{reconciliation_table(summary)}

**Independent pipeline cross-check.** `run_experiments.py` (Phases 3–7) logged the same seed-202611 historical suite in `measurements.csv` using its own measurement code:

{cross_check_table(summary)}

Other corrections: the superseded report listed `EXP_MELODIC_P180` as a near-zero case (its baseline is not near zero) and omitted `EXP_BOUNDARY_SILENCE` and `EXP_BOUNDARY_LOW_ENERGY`; the annotation format forced a "+" sign in front of correlation coefficients regardless of sign; Method D's per-event polarity inversions were not recorded (now: {summary['all_rows_counts']['d_rows_with_any_polarity_inverted_event']} D rows contain at least one inverted event).
"""
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    return REPORT_PATH


def main():
    rows = load_rows()
    summary = build_summary(rows)
    png, svg = render_figure6(rows, summary)
    with open(SUMMARY_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    write_report(summary)
    print(f"Wrote {SUMMARY_PATH}\nWrote {REPORT_PATH}\nWrote {png}\nWrote {svg}")
    print(f"Verdict: {summary['verdict']['pooled']}; plotted n = {summary['figure6']['n_observations_plotted']}")
    return summary


if __name__ == "__main__":
    main()
