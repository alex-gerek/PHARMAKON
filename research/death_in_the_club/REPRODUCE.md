# Reproducibility Guide: PHARMAKON Research Task 04
## Death in the Club — Sub-Sync Experimental Validation

This document provides exact, deterministic commands to reproduce the entire empirical evaluation, crossover analysis, automated test suite, and publication-quality figures (Figures 1 through 6).

---

### 1. Environment & Dependencies

The experiment suite requires Python 3.10+ (validated on Python 3.14.3 win32) with standard scientific dependencies:

```bash
numpy >= 1.24.0
scipy >= 1.10.0
matplotlib >= 3.7.0
pytest >= 7.0.0
```

Verify your Python environment:
```powershell
py -3.14 -c "import numpy, scipy, matplotlib, pytest; print('Environment OK!')"
```

---

### 2. Execution Commands

All commands are executed from the repository root (`.` or root directory).

#### Step 1: Run the Automated Validation Suites
Executes the comprehensive test suites validating historical claim reproduction, crossover unity, boundary conditions, prototype safety, and headroom data integrity:

```powershell
py -3.14 -m pytest research/death_in_the_club -v
```

Or run each test suite individually:
```powershell
# Core claims, crossover filter equations, boundary behaviors (12 tests)
py -3.14 -m pytest research/death_in_the_club/test_death_in_the_club.py -v

# Headroom experiment reconciliation, statistics verification, Figure 6 checks (14 tests)
py -3.14 -m pytest research/death_in_the_club/test_headroom_reconciliation.py -v
```

**Expected Result:**
- `test_death_in_the_club.py`: `12 passed in ~5.5s`
- `test_headroom_reconciliation.py`: `13 passed, 1 xfailed in ~2.0s` (the single `xfail` is the documented boundary step transient on unwindowed 12 kHz sine)
- Combined: `25 passed, 1 xfailed`

#### Step 2: Execute Crossover Transfer Function Analysis (Phase 4)
Computes the exact mathematical filter response of the 100 Hz LR4 crossover, verifying unity reconstruction and quantifying the notch created by sub-band delay and polarity inversion:

```powershell
py -3.14 research/death_in_the_club/crossover_analysis.py
```

**Expected Key Outputs:**
- Unity reconstruction max error: `7.73e-13` (bit-exact unity)
- Polarity inversion notch at 100 Hz: `-63.52 dB`
- Delay of 4.2 ms notch in 85–120 Hz band: `-13.73 dB` (~14 dB verified notch)
- Delay of 5.0 ms notch at 100 Hz: `-61.43 dB`

#### Step 3: Run Full Experimental Suite Across All 54 Scenarios (Phase 3)
Generates deterministic synthetic signals, evaluates Methods A, B, C, and D, and exports `measurements.csv` and `experiment_config.json`:

```powershell
py -3.14 research/death_in_the_club/run_experiments.py
```

**Generated Artifacts:**
- `research/death_in_the_club/measurements.csv` (216 metric rows with explicit floor and validity flags)
- `research/death_in_the_club/experiment_config.json` (metadata, summary statistics, and valid means)

#### Step 4: Generate Publication-Quality Figures 1–5 (Phase 6)
Renders Figures 1 through 5 in both 300 DPI high-resolution PNG and scalable vector SVG formats:

```powershell
py -3.14 research/death_in_the_club/plot_figures.py
```

**Generated Figures:**
- `figures/fig1_phase_interference.png` & `.svg`
- `figures/fig2_static_delay_trap.png` & `.svg`
- `figures/fig3_crossover_failure.png` & `.svg`
- `figures/fig4_method_comparison.png` & `.svg` (with separated panel headings and clean typography)
- `figures/fig5_failure_cases.png` & `.svg`

#### Step 5: Execute Headroom Cost Analysis & Generate Figure 6 (The Price of Alignment)
Generates **Figure 6** along with the reconciled data artifacts and report.

Depending on reproduction requirements, there are two deterministic execution paths:

**Option A — Render Figure 6 and Statistical Report from Existing Measurements:**
```powershell
py -3.14 research/death_in_the_club/headroom_analysis.py
```
This is the single source of truth for the headroom experiment: it parses `headroom_measurements.csv`, evaluates statistical correlations and bootstrap confidence intervals, and produces:
- `figures/fig6_price_of_alignment.png` (300 DPI high-resolution scatter plot with panel A full view and panel B zoom)
- `figures/fig6_price_of_alignment.svg` (vector format)
- `headroom_summary.json` (machine-readable statistical dictionary)
- `HEADROOM_ANALYSIS.md` (fully reconciled publication report)

**Option B — Full End-to-End Recomputation Across All 54 Scenarios:**
```powershell
py -3.14 research/death_in_the_club/headroom_experiment.py
```
Regenerates all synthetic waveforms, computes 4× polyphase oversampled true-peak levels without brickwall limiting or normalization, rewrites `headroom_measurements.csv` (216 rows), and automatically invokes `headroom_analysis.py` to regenerate Figure 6.

**Headroom Experiment Methodology & Filter Criteria:**
- **54 Synthetic Scenarios**: 3 pure phase sweep (0°, 90°, 180°), 11 static delay sweeps (0.5 to 6.0 ms), 3 melodic progressions, 3 harmonic basslines with attack transients, 30 historical benchmark runs (`seed=202611`), and 4 boundary conditions (`silence`, `low_energy`, `high_freq_noise`, `non_overlapping`).
- **Near-Zero Exclusions (3 Scenarios)**: Scenarios where the baseline sub-band (<100 Hz) RMS is $\le -80.0\text{ dBFS}$ are mathematically undefined for relative decibel changes:
  1. `EXP_PHASE_180` (pure anti-phase baseline cancellation)
  2. `EXP_BOUNDARY_SILENCE` (all-zero baseline)
  3. `EXP_BOUNDARY_LOW_ENERGY` (sub-band energy below measurement floor)
  These 3 scenarios are excluded from all aggregate statistics and scatter plots, but are explicitly preserved and documented as special cases in Section 6.6 of `HEADROOM_ANALYSIS.md`.
- **Plotted Observations**: Exactly $51\text{ valid scenarios} \times 3\text{ active methods (B, C, D)} = \mathbf{153\text{ observations}}$. Method A (unmodified baseline) has $\Delta\text{E}_{\text{sub}} = 0\text{ dB}$, $\Delta\text{TP} = 0\text{ dB}$ by construction and is shown as the $(0, 0)$ reference origin.
- **Data Integrity & Reconciliation**:
  Unlike the superseded preliminary draft which contained hardcoded template text, every statistic and label in Figure 6 and `HEADROOM_ANALYSIS.md` is strictly computed from `headroom_measurements.csv`. The automated test `test_headroom_reconciliation.py` enforces that any divergence between the CSV, JSON summary, and Markdown tables immediately causes a test failure.

---

### 3. Verification Checklist

| Metric / Finding | Expected Value | Reproduction Command / Target |
|---|:---:|---|
| **Worst Legacy Sub Drop** | **$-1.172\text{ dB}$** | `test_death_in_the_club.py` / `EXP_HIST_RUN_01` in `measurements.csv` |
| **Historical 30-Run Global Delay Avg** | **$+0.2020\text{ dB}$** | `test_death_in_the_club.py` / `experiment_config.json` |
| **Historical 30-Run Legacy Avg** | **$-0.4512\text{ dB}$** | `test_death_in_the_club.py` / `experiment_config.json` |
| **Historical 30-Run Guarded Avg** | **$+0.5812\text{ dB}$** | `test_death_in_the_club.py` / `experiment_config.json` |
| **Valid Tests Guarded Avg Gain** | **$+0.4574\text{ dB}$** | `experiment_config.json` (`valid_tests_sub_gain_mean_db`) |
| **Crossover Notch at 4.2 ms** | **$-13.73\text{ dB}$** | `crossover_analysis.py` (`delay_ms = 4.2`) |
| **LR4 Unity Reconstruction Error** | **$< 10^{-11}$** | `crossover_analysis.py` (`max_unity_deviation`) |
| **Guarded Prototype Degradations** | **0** | `experiment_config.json` (`degradations_count = 0`) |
| **Guarded Worst Crossover Drop** | **$>-0.45\text{ dB}$** | `experiment_config.json` (`worst_crossover_drop_db = -0.442`) |
| **Low-Energy Boundary Safe Path** | **Engaged (`0.0 dB`)** | `EXP_BOUNDARY_LOW_ENERGY` in `measurements.csv` |
| **Historical 30-Run Global Delay True-Peak Avg** | **$+0.0508\text{ dB}$** | `test_headroom_reconciliation.py` / `headroom_summary.json` (supersedes old $+0.2858\text{ dB}$) |
| **Historical 30-Run Legacy Sub-Only True-Peak Avg** | **$-1.0642\text{ dB}$** | `test_headroom_reconciliation.py` / `headroom_summary.json` (supersedes old $+0.1440\text{ dB}$) |
| **Historical 30-Run Guarded Prototype True-Peak Avg** | **$-0.1526\text{ dB}$** | `test_headroom_reconciliation.py` / `headroom_summary.json` (supersedes old $+0.6554\text{ dB}$) |
| **Plotted Figure 6 Observations** | **$153$** ($51 \times 3$) | `test_headroom_reconciliation.py` / `headroom_summary.json` (`n_observations_plotted`) |
| **Near-Zero Baseline Exclusions** | **3 scenarios** | `headroom_analysis.py` (`EXP_PHASE_180`, `SILENCE`, `LOW_ENERGY`) |
| **Pooled Linear Correlation ($r_{\text{pooled}}$)** | **$+0.910$** | `headroom_summary.json` (falls to $+0.555$ without $>3\text{ dB}$ sub-gain outliers) |
| **Rank Correlation (Spearman $\rho$)** | **$+0.414$** | `headroom_summary.json` (`spearman_rho`) |

All test signals use fixed random seeds (`seed=202611`) and explicit analytic formulas, ensuring bit-exact determinism across repeated executions.
