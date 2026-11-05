# Reproducibility Guide: PHARMAKON Research Task 04
## Death in the Club — Sub-Sync Experimental Validation

This document provides exact, deterministic commands to reproduce the entire empirical evaluation, crossover analysis, automated test suite, and publication-quality figures.

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

All commands are executed from the repository root: `C:\Users\User\PHARMAKON`.

#### Step 1: Run the Automated Validation Tests
Executes the pytest test suite validating historical claim reproduction, crossover unity, boundary conditions, and prototype safety:

```powershell
py -3.14 -m pytest research/death_in_the_club/test_death_in_the_club.py -v
```

**Expected Result:**
```
12 passed in ~5.5s
```

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

#### Step 4: Generate Publication-Quality Figures (Phase 6)
Renders Figures 1 through 5 in both 300 DPI high-resolution PNG and scalable vector SVG formats:

```powershell
py -3.14 research/death_in_the_club/plot_figures.py
```

**Generated Figures:**
- `figures/fig1_phase_interference.png` & `.svg`
- `figures/fig2_static_delay_trap.png` & `.svg`
- `figures/fig3_crossover_failure.png` & `.svg`
- `figures/fig4_method_comparison.png` & `.svg`
- `figures/fig5_failure_cases.png` & `.svg`

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

All test signals use fixed random seeds (`seed=202611`) and explicit analytic formulas, ensuring bit-exact determinism across repeated executions.
