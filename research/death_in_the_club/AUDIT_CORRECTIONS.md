# Data Integrity Review & Audit Corrections
## PHARMAKON Research Task 04: Death in the Club — Sub-Sync Validation

**Document ID:** PHARMAKON-AUDIT-2026-04  
**Date:** November 2026  
**Auditor:** Research Engineer, PHARMAKON DSP Project  
**Scope:** `measurements.csv`, `experiment_config.json`, `EXPERIMENT_REPORT.md`, `methods.py`, `run_experiments.py`, `plot_figures.py`, Figures 1–5  
**Guiding Principle:** Scientific accuracy takes absolute priority over positive benchmark results. Never silently overwrite or obscure discrepancies.

---

### Executive Summary of Discrepancies & Corrections

| Item | Topic | Prior Reported State | Root Cause | Corrective Action & Verified Outcome |
|---|---|---|---|---|
| **1 & 2** | **Historical 30-Run Statistics** | Method B: $+0.20\text{ dB}$<br>Method C: $-0.443\text{ dB}$<br>Method D: $+0.571\text{ dB}$ | Intermediate run draft numbers were retained in prose before filter convergence. | Recomputed directly from `measurements.csv` to 4 decimal places:<br>**Method B: $+0.2020\text{ dB}$**<br>**Method C: $-0.4512\text{ dB}$**<br>**Method D: $+0.5812\text{ dB}$** |
| **3** | **Low-Energy Boundary (`EXP_BOUNDARY_LOW_ENERGY`)** | $+62.841\text{ dB}$, `safe_path_engaged = False` | Hardcoded threshold was $10^{-5}$ ($-100\text{ dBFS}$); $-60\text{ dBFS}$ input ($7.07\times 10^{-4}$) failed to trigger guard, and exact anti-phase baseline ($0.0$) caused relative gain explosion. | Added explicit `min_signal_rms_dbfs = -50.0`. Safe path now strictly engages: `safe_path_engaged = True`, `applied_lag_ms = 0.0`, `delta_sub_gain_db = 0.000 dB`. |
| **4** | **Near-Zero Baseline Singularity (`EXP_PHASE_180`)** | $+116.780\text{ dB}$ included in "All Tests" arithmetic mean | Division by near-zero baseline ($\Delta\phi = 180^\circ$, baseline sum $\approx 0$) creates mathematical asymptote, inflating aggregate mean by $>2\text{ dB}$. | Defined explicit measurement floor: `MEASUREMENT_FLOOR_DBFS = -80.0`. Flagged `baseline_is_near_zero` and `is_relative_gain_valid`. Excluded singularities from continuous means (`valid_tests_sub_gain_mean_db`). Reported absolute output levels in dBFS. |
| **5** | **Crossover Reconstruction Equations** | Ambiguity between single-pass and effective forward-backward transfer functions | Conflating single-pass Butterworth amplitude $|H(e^{j\omega})|$ with `filtfilt` zero-phase effective response $G(e^{j\omega}) = |H(e^{j\omega})|^2$. | Mathematically derived exact digital filter equations: single-pass has $|H(f_c)| = 1/\sqrt{2}$ ($-3.01\text{ dB}$); `filtfilt` effective transfer function is $G(f_c) = 0.5000$ ($-6.02\text{ dB}$). Proved $G_{\text{LP}} + G_{\text{HP}} \equiv 1.000000$ (error $< 1.15\times 10^{-12}$). |
| **6** | **Figure 1 Terminology at 90°** | "Incoherent Power Addition" | Incorrect psychoacoustic/physical terminology; two equal-frequency sinusoids at $90^\circ$ are coherent sinusoids in quadrature, not random noise. | Corrected to: **"Quadrature Coherent Vector Sum: $\sin\omega t + \cos\omega t = \sqrt{2}\sin(\omega t + 45^\circ)$ (+3.01 dB)"**, distinguishing it from uncorrelated noise. |
| **7** | **Figure 4 Clarity & Subsets** | Overlapping annotations, ambiguous subset descriptions | Visual congestion and lack of clear separation between 30-run melodic suite and 50 non-boundary tests. | Redesigned layout with wider dimensions ($14\times 6.2$), readable boxed annotations, exact recomputed statistics, and explicit subset descriptions. |
| **8** | **GW-FRA Safe-Path Audit** | Potential edge case failures on near-silent inputs, overlapping windows, and true-peak swell | Incomplete formal boundary assertions for the prototype. | Implemented $-50\text{ dBFS}$ energy guard, verified partition-of-unity window normalization on overlapping kicks ($< 10^{-6}$ error), verified $C^1$ boundary continuity, and audited true-peak headroom consumption. |
| **9** | **Independent Automated Tests** | 6 basic tests | Lack of independent assertions for each specific discrepancy. | Implemented 12 independent pytest tests in `test_death_in_the_club.py` (`12 passed in 5.39s`). |

---

### Detailed Investigation & Mathematical Explanations

#### 1. Recomputation of Summary Statistics (Items 1 & 2)

Direct recomputation across all 30 rows of `signal_category == "historical_30_runs_seed202611"` in `measurements.csv` yields:

```python
Method A (Baseline):     mean =  0.0000 dB, min =  0.0000 dB, max = 0.0000 dB
Method B (Global Delay): mean = +0.2020 dB, min = -0.0070 dB, max = 0.7790 dB
Method C (Legacy Sub):   mean = -0.4512 dB, min = -1.1720 dB, max = 0.1250 dB
Method D (Guarded Prot): mean = +0.5812 dB, min =  0.0000 dB, max = 1.3790 dB
```

*Discrepancy Cause:* During initial exploratory harness development, an intermediate run using a 2nd-order direct-form filter was logged. When updating to the standardized 4th-order SOS filter (which converged to exact agreement with `test_dsp_core_audit.py` at $-1.172\text{ dB}$), certain paragraphs of `EXPERIMENT_REPORT.md` retained the earlier intermediate values ($-0.443\text{ dB}$ and $+0.571\text{ dB}$) rather than reading the finalized CSV output.  
*Action Taken:* All statistics in `measurements.csv`, `experiment_config.json`, and `EXPERIMENT_REPORT.md` have been updated and synchronized to 4 decimal places. The original pre-audit files are preserved under `original_pre_audit/`.

---

#### 2. The Low-Energy Boundary Fallback Failure (`EXP_BOUNDARY_LOW_ENERGY`) (Item 3)

*Observation:* In `EXP_BOUNDARY_LOW_ENERGY`, Method D previously reported $+62.841\text{ dB}$ with `safe_path_engaged = False`.  
*Root Cause Analysis:*
1. **Signal Construction:** In `generate_boundary_condition("low_energy")`:
   $$d_{\text{mono}}(t) = 10^{-3} \sin(2\pi \cdot 50 t)$$
   $$b_{\text{mono}}(t) = 10^{-3} \sin(2\pi \cdot 50 t + \pi) = -10^{-3} \sin(2\pi \cdot 50 t)$$
   The input amplitude is $10^{-3}$ ($-60.0\text{ dBFS}$), with RMS $= \frac{10^{-3}}{\sqrt{2}} \approx 7.07 \times 10^{-4}$ ($-63.0\text{ dBFS}$).
2. **Defective Guard Threshold:** `methods.py` previously contained:
   ```python
   if rms_d < 1e-5 or rms_b < 1e-5:
       # safe path
   ```
   A threshold of $10^{-5}$ corresponds to $-100.0\text{ dBFS}$. Because $-63.0\text{ dBFS} > -100.0\text{ dBFS}$, the check evaluated to `False`.
3. **Anti-Phase Cancellation Singularity:** Because $d(t) + b(t) \equiv 0.0$, the baseline sum fell to the numerical measurement floor ($-120.0\text{ dBFS}$). Method D detected the anti-phase condition, flipped polarity, and produced an aligned output of $-57.16\text{ dBFS}$. The nominal relative gain was computed as:
   $$\Delta E = -57.16 - (-120.0) = +62.84\text{ dB}$$
*Correction:*
- Parameterized `min_signal_rms_dbfs = -50.0` (linear threshold $\approx 3.16 \times 10^{-3}$).
- Any stem with sub-band energy below $-50.0\text{ dBFS}$ triggers `safe_path_engaged = True`, setting `applied_lag_ms = 0.0`, `applied_polarity = 1.0`, and returning the pristine bass stem with $\Delta E_{\text{sub}} = 0.000\text{ dB}$.
- Verified: Both Method B and Method D now engage the safe path on `EXP_BOUNDARY_LOW_ENERGY`.

---

#### 3. Near-Zero Baseline Cases & Measurement Floor (Item 4)

*Observation:* In `EXP_PHASE_180`, two equal-amplitude ($0.50\text{ FS}$) $50\text{ Hz}$ sine waves are summed in exact anti-phase ($\Delta\phi = 180^\circ$). The baseline sum cancels analytically to zero ($-\infty\text{ dBFS}$, measured at $-120.0\text{ dBFS}$ due to numerical floor). When Method D inverts polarity, the output is in-phase ($-3.01\text{ dBFS}$), yielding a nominal relative gain of:
$$\Delta E_{\text{sub}} = -3.01 - (-120.0) = +116.99\text{ dB}$$
*Statistical Contamination:* When $+116.99\text{ dB}$ is included in the unweighted arithmetic mean across all 50 non-boundary tests, it shifts the aggregate mean from $+0.46\text{ dB}$ to $+2.78\text{ dB}$, creating a misleading representation of general algorithm performance.  
*Correction:*
1. Defined an explicit measurement floor: $\text{FLOOR}_{\text{dBFS}} = -80.0\text{ dBFS}$.
2. Added columns to `measurements.csv`:
   - `baseline_is_near_zero`: boolean (`True` if `sub_sum_baseline_dbfs <= -80.0`).
   - `is_relative_gain_valid`: boolean (`False` if baseline is near zero).
3. In `experiment_config.json`, continuous aggregate statistics are computed across valid non-singular tests (`valid_tests_sub_gain_mean_db`), while singular cancellation recoveries are counted and reported separately:
   - Method B: Valid Mean = **$+0.6541\text{ dB}$** (Raw Mean = $+2.9802\text{ dB}$)
   - Method C: Valid Mean = **$+0.1222\text{ dB}$** (Raw Mean = $+2.4484\text{ dB}$)
   - Method D: Valid Mean = **$+0.4574\text{ dB}$** (Raw Mean = $+2.7839\text{ dB}$)

---

#### 4. Verification of Crossover Reconstruction Equations (Item 5)

We audited the exact digital filter equations implemented in `remaster_engine.align_sub_phase`.

##### Digital Butterworth Formulation
The 2nd-order analog Butterworth low-pass prototype has transfer function:
$$H_a(s) = \frac{\Omega_c^2}{s^2 + \sqrt{2}\Omega_c s + \Omega_c^2}$$
Applying the bilinear transform $s = \frac{2}{T} \frac{1 - z^{-1}}{1 + z^{-1}}$ with frequency pre-warping $\Omega_c = \frac{2}{T} \tan\left(\frac{\omega_c T}{2}\right)$ yields the digital biquad transfer functions:
$$H_{\text{LP}}(z) = \frac{b_{0} + b_{1} z^{-1} + b_{2} z^{-2}}{1 + a_{1} z^{-1} + a_{2} z^{-2}}, \quad H_{\text{HP}}(z) = \frac{b_{0,\text{HP}} + b_{1,\text{HP}} z^{-1} + b_{2,\text{HP}} z^{-2}}{1 + a_{1} z^{-1} + a_{2} z^{-2}}$$

At normalized frequency $\omega = 2\pi f / f_s$, the single-pass frequency response has amplitude:
$$|H_{\text{LP}}(e^{j\omega})| = \frac{1}{\sqrt{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4}}$$
$$|H_{\text{HP}}(e^{j\omega})| = \frac{\left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^2}{\sqrt{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4}}$$
At crossover $f = f_c$ ($\omega = \omega_c$):
$$|H_{\text{LP}}(e^{j\omega_c})| = \frac{1}{\sqrt{1 + 1}} = \frac{1}{\sqrt{2}} \approx 0.707107 \quad (-3.0103\text{ dB})$$
$$|H_{\text{HP}}(e^{j\omega_c})| = \frac{1}{\sqrt{1 + 1}} = \frac{1}{\sqrt{2}} \approx 0.707107 \quad (-3.0103\text{ dB})$$

##### Forward-Backward Filtering Behavior (`signal.filtfilt`)
When an input sequence $x[n]$ is filtered forward and backward:
1. Forward pass: $V(e^{j\omega}) = X(e^{j\omega}) H(e^{j\omega})$
2. Time reversal: $V_r(e^{j\omega}) = V^*(e^{j\omega}) = X^*(e^{j\omega}) H^*(e^{j\omega})$
3. Second pass: $W(e^{j\omega}) = V_r(e^{j\omega}) H(e^{j\omega}) = X^*(e^{j\omega}) |H(e^{j\omega})|^2$
4. Final time reversal: $Y(e^{j\omega}) = W^*(e^{j\omega}) = X(e^{j\omega}) |H(e^{j\omega})|^2$

The **effective transfer function** of the forward-backward filter is:
$$G(e^{j\omega}) = \frac{Y(e^{j\omega})}{X(e^{j\omega})} = |H(e^{j\omega})|^2$$
Crucially:
- $G(e^{j\omega})$ is strictly real and non-negative, meaning the effective phase distortion is **identically zero** ($\angle G \equiv 0$).
- The magnitude is the **squared magnitude** of the single-pass filter:
  $$G_{\text{LP}}(e^{j\omega_c}) = |H_{\text{LP}}(e^{j\omega_c})|^2 = \left(\frac{1}{\sqrt{2}}\right)^2 = 0.500000 \quad (-6.0206\text{ dB})$$
  $$G_{\text{HP}}(e^{j\omega_c}) = |H_{\text{HP}}(e^{j\omega_c})|^2 = \left(\frac{1}{\sqrt{2}}\right)^2 = 0.500000 \quad (-6.0206\text{ dB})$$

##### Perfect Unity Recombination
Summing the low-pass and high-pass effective transfer functions yields:
$$G_{\text{sum}}(e^{j\omega}) = G_{\text{LP}}(e^{j\omega}) + G_{\text{HP}}(e^{j\omega}) = \frac{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4}{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4} \equiv 1.0000000000$$
Numerical verification confirms:
$$\max_{\omega} |G_{\text{sum}}(e^{j\omega}) - 1.0| = 7.73 \times 10^{-13} \quad (< -242\text{ dBFS})$$
This proves that the unmodified crossover is a true Linkwitz-Riley 4th-order (LR4) zero-phase filter with bit-exact unity reconstruction.

##### The Differential Sub-Band Transformation Defect
When `align_sub_phase` shifts or inverts only the low band:
$$G_{\text{recomb}}(e^{j\omega}) = G_{\text{LP}}(e^{j\omega}) \cdot T(e^{j\omega}) + G_{\text{HP}}(e^{j\omega})$$
- For sub polarity flip ($T = -1.0$):
  $$G_{\text{recomb}}(e^{j\omega_c}) = -0.5000 + 0.5000 = 0.0000 \implies -\infty\text{ dB (measured } -63.52\text{ dB)}$$
- For sub delay $\tau = 5.0\text{ ms}$ ($T = e^{-j\pi} = -1.0$):
  $$G_{\text{recomb}}(e^{j\omega_c}) = -0.5000 + 0.5000 = 0.0000 \implies -61.43\text{ dB notch}$$
- For sub delay $\tau = 4.2\text{ ms}$ ($T = e^{-j 151.2^\circ}$):
  $$|G_{\text{recomb}}(e^{j\omega_c})| = |0.5 e^{-j 151.2^\circ} + 0.5| = 0.2486 \implies -12.10\text{ dB (worst notch in 85–120 Hz: } -13.73\text{ dB)}$$

---

#### 5. Correction of Figure 1 Terminology (Item 6)

*Discrepancy:* Figure 1 previously labeled the $90^\circ$ phase case as `"+3.01 dB Summation (Incoherent Power Addition)"`.  
*Physical Correction:*  
Two sinusoids of the exact same frequency $f_0$ with relative phase $\Delta\phi = 90^\circ$ are **coherent orthogonal waveforms in quadrature**. Their acoustic sum is:
$$\sin(\omega t) + \sin(\omega t + \pi/2) = \sin(\omega t) + \cos(\omega t) = \sqrt{2} \sin(\omega t + \pi/4)$$
The resulting pressure wave has peak amplitude $\sqrt{2} \approx 1.414214$. In decibels:
$$20 \log_{10}(\sqrt{2}) = +3.0103\text{ dB}$$
This is an **orthogonal coherent vector sum**, completely distinct from the statistical power doubling ($10 \log_{10}(2) = +3.01\text{ dB}$) of uncorrelated random noise processes.  
*Action Taken:* Figure 1 was re-rendered with the mathematically rigorous title:  
**"+3.01 dB Summation (Quadrature Coherent Vector Sum: $\sin\omega t + \cos\omega t = \sqrt{2}\sin(\omega t + 45^\circ)$)"**.

---

#### 6. Layout & Annotation Overhaul of Figure 4 (Item 7)

*Discrepancy:* Panel titles and annotations in Figure 4 were congested, with legacy drop annotations overlapping other elements, and did not clearly delineate the evaluation subsets.  
*Action Taken:*
- Expanded figure dimensions to $14.0 \times 6.2\text{ inches}$ at $300\text{ DPI}$.
- Panel A clearly specifies: **"Historical 30-Run Random Melodic/Harmonic Bass Benchmark (Seed 202611)"** with box plots, mean diamonds, and boxed annotations showing:
  - Legacy worst drop: **$-1.172\text{ dB}$**, legacy mean: **$-0.4512\text{ dB}$**.
  - Guarded prototype mean: **$+0.5812\text{ dB}$** (100% non-negative, $0.000$ to $+1.379\text{ dB}$).
  - Global delay mean: **$+0.2020\text{ dB}$** (high variance).
- Panel B clearly specifies: **"Mean vs Worst Observed Crossover Notch (All 50 Non-Boundary Tests)"**, documenting:
  - Legacy worst crossover drop: **$-24.05\text{ dB}$**.
  - Guarded prototype crossover notch: **$> -0.45\text{ dB}$** (zero crossover destruction).
- Both PNG and SVG vector files were regenerated.

---

#### 7. Audit of GW-FRA Prototype Conditions (Item 8)

| Condition | Mechanism Audited | Verification Result |
|---|---|---|
| **Near-Silent Inputs** | Evaluates $\text{RMS} < 10^{-50/20}$ ($-50.0\text{ dBFS}$) on sub-band drum and bass signals before processing. | Safe-path rule reliably engages; returns unmodified input with $0.000\text{ dB}$ delta. |
| **Overlapping Windows** | Partition-of-unity normalization: accumulates weights $W[n] = \sum_k w_k[n]$; divides accumulated corrected segments by $W[n]$ where $W[n] > 0$. | Tested with rapid $80\text{ ms}$ kick bursts. Reconstruction error when shifts are zero is $< 10^{-6}$, confirming zero amplitude distortion. |
| **Boundary Continuity** | Evaluates Tukey window ($\alpha = 0.30$) tapering on $200\text{ ms}$ event windows. | Continuous $C^1$ smoothness verified; no step discontinuities or edge clicks. |
| **True-Peak Changes** | Measures $4\times$ polyphase sinc interpolated true-peak across all runs. | In-phase alignment increases true-peak by $+3.0$ to $+6.0\text{ dB}$. Confirms that low-end phase alignment consumes mastering headroom. |

---

### Verification: Automated Independent Test Suite (Item 9)

An automated suite of 12 independent tests was executed via `pytest`:

```powershell
py -3.14 -m pytest research/death_in_the_club/test_death_in_the_club.py -v
```

```
test_historical_claim_worst_legacy_drop_reproduced  PASSED [  8%]
test_measurements_csv_summary_statistics_exact_match PASSED [ 16%]
test_crossover_digital_butterworth_exact_equations PASSED [ 25%]
test_historical_claim_crossover_notch_up_to_14db    PASSED [ 33%]
test_quadrature_vector_addition_exact_3db           PASSED [ 41%]
test_true_peak_headroom_increase                    PASSED [ 50%]
test_low_energy_boundary_engages_safe_path          PASSED [ 58%]
test_near_zero_baseline_relative_gain_exclusion     PASSED [ 66%]
test_overlapping_windows_unity_reconstruction       PASSED [ 75%]
test_boundary_handling_silence_and_low_energy       PASSED [ 83%]
test_reconstructed_signal_length_and_channel_pres   PASSED [ 91%]
test_guarded_prototype_preserves_crossover_and_prev PASSED [100%]

======================== 12 passed in 5.39s =========================
```

---

### Remaining Limitations & Open Research Questions

1. **Psychoacoustic Masking vs Low-End Impact:** While GW-FRA guarantees non-negative acoustic pressure gain ($+0.58\text{ dB}$ average), an unadjusted low-end boost can psychoacoustically mask lower-mid clarity ($150–400\text{ Hz}$). A formal double-blind MUSHRA test is required before commercial deployment.
2. **Dynamic 808 Pitch Glides:** Continuous pitch glides violate the quasi-stationary assumption within the $200\text{ ms}$ analysis window, potentially causing time-varying correlation smearing.
3. **Cross-Fade Comb Filtering:** Blending a shifted segment with an unshifted segment during window transitions can induce subtle comb filtering during the cross-fade duration if the shift is large.
4. **Real-Time DSP Constraints:** Implementing GW-FRA in JUCE / C++20 VST3 requires sidechain buffering and approximately $10\text{ ms}$ (480 samples) lookahead latency.
