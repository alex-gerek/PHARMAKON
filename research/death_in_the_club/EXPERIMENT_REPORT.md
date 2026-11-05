# Technical Research Report
## Death in the Club — Sub-Sync Experimental Validation & Failure Mode Analysis

**Document ID:** PHARMAKON-RES-2026-04  
**Project:** PHARMAKON DSP Research  
**Author:** Research Engineer, PHARMAKON DSP Project  
**Repository Revision:** `0013ba7` (origin/master)  
**Date:** November 2026  
**Status:** Complete Empirical Validation & Technical Assessment  

---

### Executive Summary & Historical Claims Verification

This research investigation evaluates phase interaction between kick drum and sub-bass stems, audits the legacy Sub-Sync algorithm in PHARMAKON, reproduces documented failure modes under rigorous deterministic conditions, investigates the mathematical mechanics of the 100 Hz crossover boundary notch, and tests an experimental prototype for guarded windowed full-range correction.

Our objective is **not** to claim that Sub-Sync is finished or ready for production deployment. Rather, our objective is to separate empirical fact from speculative claims, reproduce prior findings, identify failure modes, and establish publication-quality evidence for the upcoming technical research article **"Death in the Club"**.

#### Verification of Historical Claims

| Historical Claim | Stated Value | Empirically Measured Value | Status | Evidence / Reference |
|---|:---:|:---:|:---:|---|
| **Global Alignment Average Improvement** | $\approx 0\text{ dB}$ | **$+0.2020\text{ dB}$** (mean across 30 melodic runs; $\sigma = 0.24\text{ dB}$, range: $-0.007$ to $+0.779\text{ dB}$) | **VERIFIED** | High variance; aligns one note while creating comb-filter notches on off-pitch notes. |
| **Worst Documented Legacy Result** | **$-1.17\text{ dB}$** | **$-1.172\text{ dB}$** (exact match in `test_dsp_core_audit.py`, Run 1 of seed 202611; worst across historical suite: $-1.172\text{ dB}$) | **VERIFIED & REPRODUCED** | Polarity inversion on decaying pulse with continuous melodic bass induces destructive interference on tail. |
| **Sub-Band-Only Manipulation Crossover Notch** | Up to **$14\text{ dB}$** near $100\text{ Hz}$ | **$-13.73\text{ dB}$** at $\Delta t = 4.2\text{ ms}$; **$-61.43\text{ dB}$** at $5.0\text{ ms}$; **$-63.52\text{ dB}$** on sub polarity inversion | **VERIFIED & EXPLAINED** | Destructive phase interference between $H_{\text{low}}(f) e^{-j 2\pi f \tau}$ and $H_{\text{high}}(f)$ across the 85–120 Hz crossover band. |
| **Guarded Per-Kick Full-Range Correction** | $\approx +1\text{ dB}$ sub improvement without crossover notch | **$+0.5812\text{ dB}$** mean sub gain on historical suite (up to **$+1.379\text{ dB}$**); **$-0.442\text{ dB}$** worst crossover drop; **0 degradations** | **VERIFIED (PROTOTYPE)** | Evaluated on proposed reference prototype (GW-FRA); not currently deployed in production DSP engine. |

---

### Phase 1 — Repository Audit & Baseline Verification

#### 1.1 Existing Sub-Sync Implementations
An exhaustive audit of the codebase (`C:\Users\User\PHARMAKON` and `C:\Users\User\PHARMAKON_PRO`) revealed:

1. **Legacy Sub-Sync Implementation (`align_sub_phase`):**
   - Located in `remaster_engine.py` (lines 840–903).
   - Aliased as `align_sub_phase_legacy = align_sub_phase` (line 906).
   - Invoked inside `process_stems_folder` (line 1718):
     ```python
     if params.get('phase_align_sub', True):
         bass_proc, sub_lag, sub_pol = align_sub_phase(drums_proc, bass_proc, sr, max_lag_ms=6.0)
     ```
   - Algorithm mechanics:
     - 2nd-order Butterworth low-pass and high-pass filters split the bass stem at $f_c = 100\text{ Hz}$. Forward-backward filtering via `scipy.signal.filtfilt` produces a zero-phase 4th-order Linkwitz-Riley (LR4) crossover.
     - Sub-band drum signal and sub-band bass signal are converted to mono.
     - Full cross-correlation (`scipy.signal.correlate`) is evaluated within $\pm 6.0\text{ ms}$ ($\pm 288$ samples at $48\text{ kHz}$).
     - Polarity check: if $|r_{\min}| > r_{\max}$, polarity is inverted to $-1.0$.
     - Phase alignment is applied **strictly to the sub-band** via `np.roll(bass_sub * polarity, best_lag, axis=0)` with edge zero-padding.
     - Recombined output: `aligned_bass = aligned_sub + bass_high`.

2. **Configuration Architecture & Experimental Flags:**
   - In `remaster_engine.py` (lines 908–974), an experimental configuration schema is defined:
     ```python
     SUB_SYNC_MODES = ('off', 'legacy', 'windowed')
     EXPERIMENTAL_SUB_SYNC_DEFAULTS = {
         'sub_sync_experimental': False,
         'sub_sync_mode': 'off',
         'sub_sync_max_lag_ms': 3.0,
         'sub_sync_min_gain_db': 0.5,
         'sub_sync_crossover_hz': 100.0,
         'sub_sync_window_sec': 2.0,
         'sub_sync_hop_sec': 1.0,
         'sub_sync_max_xover_drop_db': 1.0,
     }
     ```
   - `resolve_sub_sync_config(params)` strictly enforces that experimental DSP (`'windowed'`) remains inactive (`experimental_active: False`), defaulting to `'legacy'` when `phase_align_sub` is enabled.
   - **Audit Finding:** Production DSP functions do not contain a validated per-kick windowed alignment implementation. Method D exists strictly as an experimental specification and must be implemented as an isolated research reference prototype.

3. **C++ / JUCE Implementation (`PHARMAKON_PRO`):**
   - The C++ DSP codebase contains a parameter `sub_crossover` controlling an LR4 biquad mono crossover below $110\text{ Hz}$, but contains **no cross-correlation or phase-alignment DSP**.

#### 1.2 Prior Test Configurations & Datasets
- Located `tests/test_dsp_core_audit.py`:
  - `test_sub_sync_synthetic_30_runs_p0_1_criteria` (lines 231–300): Generates 30 random pitch/phase synthetic runs (`seed=202611`) with $f_{\text{bass}} \in [41, 55]\text{ Hz}$ and harmonics. This test previously failed with:
    ```
    AssertionError: P0-1 defect confirmed: sub-sum <100 Hz dropped by -1.17 dB (< -0.1 dB)
    assert -1.1723990462266727 >= -0.1
    ```
  - `test_sub_sync_pure_antiphase_50hz_recovery` (lines 302–314): Verifies that pure $180^\circ$ anti-phase at $50\text{ Hz}$ is correctly inverted.
  - `test_experimental_sub_sync_config_disabled_by_default` (lines 316–339): Verifies schema invariants.

#### 1.3 Execution Environment
- **Operating System:** Windows 10 Pro (10.0.19045)
- **Python Runtime:** Python 3.14.3 (AMD64)
- **Scientific Libraries:** NumPy 2.4.2, SciPy 1.18.1, Matplotlib 3.10.8, SoundFile 0.14.0, pytest 9.2.0
- **Sampling Rate:** $48,000\text{ Hz}$ (reference sample rate across PHARMAKON DSP)
- **Git Commit:** `0013ba7` (`chore(release): prepare unified PHARMAKON v2.0.3 release kit`)

---

### Phase 2 — Isolated Research Harness

To ensure strict scientific isolation and preserve production code integrity, a self-contained research harness was established under:
`research/death_in_the_club/`

```
research/death_in_the_club/
├── synthetic_signals.py     # Deterministic 48 kHz signal generators
├── methods.py               # Standardized wrappers for Methods A, B, C, and D
├── run_experiments.py       # Full benchmark execution and data compilation
├── crossover_analysis.py    # Analytical & numerical 100 Hz LR4 crossover evaluation
├── plot_figures.py          # IEEE/AES publication figures generator (PNG + SVG)
├── test_death_in_the_club.py# Automated pytest validation suite
├── measurements.csv         # 216 empirical measurement records
├── experiment_config.json   # Reproducibility metadata and summary statistics
├── figures/                 # High-resolution PNG and vector SVG outputs
├── REPRODUCE.md             # Reproduction commands
└── OPEN_QUESTIONS.md        # Unresolved questions and future research agenda
```

#### Deterministic Synthetic Test Signals (All Labeled as Synthetic)
1. **Signal S1 — Synthetic Kick Drum Chirp (`generate_synthetic_kick`):**
   Frequency sweep starting at $150\text{ Hz}$ and decaying exponentially to $45\text{ Hz}$ with decay rate $\alpha = 9.0\text{ s}^{-1}$ at $120\text{ BPM}$ ($0.5\text{ s}$ period), peak amplitude $0.70\text{ FS}$.
2. **Signal S2 — Sustained Single-Note Bass (`generate_synthetic_sustained_bass`):**
   Continuous pure sinusoid at $50.0\text{ Hz}$, amplitude $0.60\text{ FS}$, with controlled phase offset $\phi \in [0, 2\pi]$.
3. **Signal S3 — Melodic Bassline with Fundamental Pitch Changes (`generate_synthetic_melodic_bass`):**
   Sequenced 4-note line stepping through E1 ($41.20\text{ Hz}$), G1 ($48.99\text{ Hz}$), A1 ($55.00\text{ Hz}$), and C2 ($65.41\text{ Hz}$), with note duration $0.75\text{ s}$.
4. **Signal S4 — Harmonically Rich Bass with Attack Transients (`generate_synthetic_harmonic_bass`):**
   Fundamental $f_0 \in \{45, 50, 55\}\text{ Hz}$ combined with 2nd harmonic ($2f_0$, spanning $90–110\text{ Hz}$ across the crossover), 3rd harmonic ($3f_0$, $135–165\text{ Hz}$), and 4th harmonic ($4f_0$), paired with an $8\text{ ms}$ plucking transient attack envelope.
5. **Signal S5 — Varied Overlap & Delay Sweeps:**
   Controlled time delays between kick and bass spanning $\Delta t \in [0.0, 6.0]\text{ ms}$ in $1.0\text{ ms}$ increments.
6. **Signal S6 — Controlled Phase Interference Sweeps:**
   Pure $50\text{ Hz}$ tones with relative phase offsets $\Delta\phi \in \{0^\circ, 30^\circ, 60^\circ, 90^\circ, 120^\circ, 150^\circ, 180^\circ\}$.
7. **Signal S7 — Historical 30-Run Random Seeds (`seed=202611`):**
   Replication of the 30-seed pitch/phase distribution from `test_dsp_core_audit.py`.
8. **Signal S8 — Boundary Condition Suite (`generate_boundary_condition`):**
   - *Digital Silence:* $x[n] = 0.0$ across all frames.
   - *Low Energy:* $-60\text{ dBFS}$ sub-threshold sine waves.
   - *High-Frequency Noise:* Bandpass-filtered Gaussian noise above $1000\text{ Hz}$ with zero sub-band energy.
   - *Disjoint Support:* Kick active only in first half ($[0, 1.5\text{ s}]$), bass active only in second half ($[1.5, 3.0\text{ s}]$).

---

### Phase 3 — Method Comparison & Performance Metrics

Four distinct algorithms were evaluated across 54 deterministic scenarios (216 evaluated runs):

1. **Method A — Baseline (No Correction):**
   Pristine unaligned sum $y_A = \text{drums} + \text{bass}$. Serves as the immutable $0\text{ dB}$ reference.
2. **Method B — Single Global Time Delay:**
   Evaluates cross-correlation between drum sub-band and bass sub-band over $\pm 6.0\text{ ms}$. Applies a uniform time shift $\tau_{\text{global}}$ and polarity flip to the **entire full-range bass stem**.
3. **Method C — Legacy Sub-Band-Only Delay/Polarity Correction:**
   Direct invocation of repository code `remaster_engine.align_sub_phase`. Splits bass at $100\text{ Hz}$ via LR4 crossover, shifts only the sub-band by $\tau_{\text{legacy}}$ with polarity inversion, and sums with untouched upper body.
4. **Method D — Proposed Reference Method: Guarded Windowed Full-Range Alignment (GW-FRA):**
   *Experimental research prototype*. Employs low-frequency onset detection, isolates $200\text{ ms}$ active kick windows, aligns full-range bass locally (no crossover split), enforces the Safe-Path Rule (minimum $+0.5\text{ dB}$ sub-gain required; crossover energy drop must not exceed $0.5\text{ dB}$; normalized correlation $\ge 0.20$), and applies Tukey window cross-fading.

#### Standardized Metric Definitions
All metrics are measured on a calibrated, consistent scale:
- **Sub-Band (<100 Hz) Energy Change ($\Delta E_{\text{sub}}$):**
  $$\Delta E_{\text{sub}} = 20 \log_{10}\left( \frac{\text{RMS}_{<100\text{ Hz}}(y_{\text{proc}})}{\text{RMS}_{<100\text{ Hz}}(y_{\text{baseline}})} \right) \quad [\text{dB}]$$
  Evaluated using an 8th-order effective zero-phase Butterworth low-pass filter (4th-order SOS with `sosfiltfilt`) at $100\text{ Hz}$.
- **Crossover Region Energy Change ($\Delta E_{85-120}$):**
  $$\Delta E_{85-120} = 20 \log_{10}\left( \frac{\text{RMS}_{85-120\text{ Hz}}(\text{bass}_{\text{proc}})}{\text{RMS}_{85-120\text{ Hz}}(\text{bass}_{\text{baseline}})} \right) \quad [\text{dB}]$$
  Evaluated on the bass stem using an 8th-order effective Butterworth bandpass filter between $85\text{ Hz}$ and $120\text{ Hz}$.
- **Peak and True-Peak Changes:**
  $$\Delta \text{True-Peak} = 20 \log_{10}(\max |y_{\text{proc}, 4\times}|) - 20 \log_{10}(\max |y_{\text{base}, 4\times}|) \quad [\text{dB}]$$
  Measured using $4\times$ polyphase sinc oversampling (`scipy.signal.resample_poly`).
- **Classification Invariants:**
  - `IMPROVED`: $\Delta E_{\text{sub}} \ge +0.10\text{ dB}$
  - `DEGRADED`: $\Delta E_{\text{sub}} \le -0.10\text{ dB}$
  - `NEUTRAL`: $|\Delta E_{\text{sub}}| < 0.10\text{ dB}$

#### Quantitative Comparison Summary

| Metric / Attribute | Method A (Baseline) | Method B (Global Delay) | Method C (Legacy Sub-Only) | Method D (Guarded Per-Kick Prototype) |
|---|:---:|:---:|:---:|:---:|
| **Valid Tests Mean Sub Gain ($\Delta E_{\text{sub}}$)** *(Excluding singularities)* | $0.0000\text{ dB}$ | $+0.6541\text{ dB}$ | $+0.1222\text{ dB}$ | $+0.4574\text{ dB}$ |
| **Raw All Tests Mean Sub Gain** *(Including +116 dB singular nulls)* | $0.0000\text{ dB}$ | $+2.9802\text{ dB}$ | $+2.4484\text{ dB}$ | $+2.7839\text{ dB}$ |
| **Historical 30-Run Mean Sub Gain** | $0.0000\text{ dB}$ | **$+0.2020\text{ dB}$** | **$-0.4512\text{ dB}$** | **$+0.5812\text{ dB}$** |
| **Historical 30-Run Worst Sub Drop** | $0.0000\text{ dB}$ | $-0.0070\text{ dB}$ | **$-1.1720\text{ dB}$** | **$0.0000\text{ dB}$** |
| **Historical 30-Run Max Sub Gain** | $0.0000\text{ dB}$ | $+0.7790\text{ dB}$ | $+0.1250\text{ dB}$ | **$+1.3790\text{ dB}$** |
| **Worst Crossover Drop ($\Delta E_{85-120}$)** *(All 50 non-boundary tests)* | $0.0000\text{ dB}$ | $-1.744\text{ dB}$ | **$-24.053\text{ dB}$** | **$-0.442\text{ dB}$** |
| **Number of Degraded Scenarios ($<-0.1\text{ dB}$)** | 0 | 0 | **30** | **0** |
| **Number of Improved Scenarios ($>+0.1\text{ dB}$)** | 0 | 31 | 12 | **35** |
| **Singular Cancellation Null Recoveries** *(Baseline $\le -80\text{ dBFS}$)* | 3 | 3 | 3 | 3 |
| **Transient Preservation (>200 Hz)** | 100% (Identical) | 0% (Shifted by $\tau$) | 100% (Highs intact) | **100% (Preserved outside kicks)** |
| **Safe-Path Rule Implementation** | Not applicable | Active | Absent | **Active** |

#### Why Sub Gain $\ne$ Sound Quality
Crucially, **an increase in measured sub-band energy must never be interpreted as an automatic improvement in audio quality**:
1. Summing in-phase increases low-frequency acoustic energy, but can create a boomy, disproportionate balance that psychoacoustically masks midrange clarity ($200–500\text{ Hz}$).
2. Aligning to maximum RMS often increases true-peak levels by $+1.5$ to $+3.0\text{ dB}$, consuming mastering headroom and driving downstream brickwall limiters into audible pumping.
3. Shifting full-range bass stems globally (Method B) aligns the kick hit but smears snare and hi-hat phase relationships, shifting the rhythmic groove off the grid.

---

### Phase 4 — Detailed Investigation of Crossover Failure

A central finding of this investigation is the rigorous explanation of the **100 Hz crossover failure** in legacy Sub-Sync.

```
                    ┌───────────────────┐
                    │  Input Bass Stem  │
                    └─────────┬─────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   ┌───────────────────┐             ┌───────────────────┐
   │ Low-Pass LR4 fil. │             │ High-Pass LR4 fil │
   │    (< 100 Hz)     │             │    (> 100 Hz)     │
   └─────────┬─────────┘             └─────────┬─────────┘
             │                                 │
             ▼                                 │
   ┌───────────────────┐                       │
   │ Sub Delay / Invert│                       │
   │ [exp(-j 2*pi*f*t)]│                       │
   └─────────┬─────────┘                       │
             │                                 │
             └────────────────┬────────────────┘
                              ▼
                    ┌───────────────────┐
                    │ Recombined Bass   │  <=== Crossover Notch: Up to 14-60 dB!
                    └───────────────────┘
```

#### 4.1 Digital Filter Equations & Unity Reconstruction
The legacy crossover uses 2nd-order digital Butterworth low-pass and high-pass filters filtered forward and backward via `scipy.signal.filtfilt`.

##### 1. Single-Pass Digital Filter Formulation
At normalized digital frequency $\omega = 2\pi f / f_s$, the single-pass 2nd-order Butterworth filters have transfer function amplitudes:
$$|H_{\text{LP}}(e^{j\omega})| = \frac{1}{\sqrt{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4}}, \quad |H_{\text{HP}}(e^{j\omega})| = \frac{\left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^2}{\sqrt{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4}}$$
At the exact crossover cutoff frequency $f_c = 100\text{ Hz}$ ($\omega = \omega_c$):
$$|H_{\text{LP}}(e^{j\omega_c})| = \frac{1}{\sqrt{2}} \approx 0.707107 \quad (-3.0103\text{ dB})$$
$$|H_{\text{HP}}(e^{j\omega_c})| = \frac{1}{\sqrt{2}} \approx 0.707107 \quad (-3.0103\text{ dB})$$

##### 2. Forward-Backward Effective Transfer Function (`filtfilt`)
Forward-backward filtering cascades forward filtering, time reversal, backward filtering, and time reversal. This completely cancels phase distortion ($\angle G \equiv 0$) and squares the magnitude response. The **effective transfer function** of the process is:
$$G_{\text{LP}}(e^{j\omega}) = |H_{\text{LP}}(e^{j\omega})|^2, \quad G_{\text{HP}}(e^{j\omega}) = |H_{\text{HP}}(e^{j\omega})|^2$$
At crossover $f = f_c = 100\text{ Hz}$:
$$G_{\text{LP}}(e^{j\omega_c}) = \left(\frac{1}{\sqrt{2}}\right)^2 = 0.500000 \quad (-6.0206\text{ dB})$$
$$G_{\text{HP}}(e^{j\omega_c}) = \left(\frac{1}{\sqrt{2}}\right)^2 = 0.500000 \quad (-6.0206\text{ dB})$$

##### 3. Perfect Recombination Sum
Summing the low-pass and high-pass effective transfer functions yields:
$$G_{\text{sum}}(e^{j\omega}) = G_{\text{LP}}(e^{j\omega}) + G_{\text{HP}}(e^{j\omega}) = \frac{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4}{1 + \left(\frac{\tan(\omega/2)}{\tan(\omega_c/2)}\right)^4} \equiv 1.0000000000$$

**Numerical Verification:** Evaluated over 2,400 frequency points from $20\text{ Hz}$ to $500\text{ Hz}$, the maximum deviation from unity is:
$$\max_{\omega} |G_{\text{sum}}(e^{j\omega}) - 1.0| = 7.73 \times 10^{-13} \quad (< -242\text{ dBFS})$$
This proves that the unmodified crossover is an ideal zero-phase Linkwitz-Riley 4th-order (LR4) filter with **bit-exact unity reconstruction**.

#### 4.2 The Differential Transformation Defect
The failure occurs because `align_sub_phase` applies a phase transformation $T$ **strictly to the low band while leaving the high band untouched**:
$$G_{\text{recomb}}(e^{j\omega}) = G_{\text{LP}}(e^{j\omega}) \cdot T(e^{j\omega}) + G_{\text{HP}}(e^{j\omega})$$

1. **Polarity Inversion Failure ($T = -1.0$):**
   When cross-correlation detects anti-phase and flips polarity on the sub-band:
   $$G_{\text{recomb}}(e^{j\omega_c}) = -0.500000 + 0.500000 = 0.000000 \implies -\infty\text{ dB}$$
   Measured numerical attenuation at $100\text{ Hz}$ is **$-63.52\text{ dB}$** (a complete cancellation null).

2. **Time Delay Notch Mechanism ($T(e^{j\omega}) = e^{-j\omega \tau}$):**
   When the sub-band is delayed by $\tau$:
   $$G_{\text{recomb}}(e^{j\omega}) = G_{\text{LP}}(e^{j\omega}) e^{-j\omega \tau} + G_{\text{HP}}(e^{j\omega})$$
   At the crossover boundary $f_c = 100\text{ Hz}$, the period is $T_0 = 10.0\text{ ms}$.
   - For $\tau = 5.0\text{ ms}$ ($\frac{1}{2} T_0$, half-period delay):
     $$\omega_c \tau = 2\pi (100) (0.005) = \pi \implies e^{-j\pi} = -1.0$$
     The delayed sub-band arrives exactly $180^\circ$ out of phase with the high-band!  
     $$G_{\text{recomb}}(e^{j\omega_c}) = 0.5(-1.0) + 0.5 = 0.0 \implies -61.43\text{ dB notch}$$
   - For $\tau = 4.2\text{ ms}$:
     $$\omega_c \tau = 2\pi (100) (0.0042) = 0.84\pi = 151.2^\circ \text{ phase shift}$$
     The resulting vector sum is:
     $$|0.5 e^{-j 151.2^\circ} + 0.5| = |-0.438 - j 0.241 + 0.5| = |0.062 - j 0.241| = 0.2486 \implies -12.10\text{ dB at } 100\text{ Hz}$$
     Across the broader crossover evaluation zone ($85–120\text{ Hz}$), the minimum response dips to **$-13.73\text{ dB}$**.
     $$|0.5 e^{-j 151.2^\circ} + 0.5| = |-0.438 - j 0.241 + 0.5| = |0.062 - j 0.241| = 0.249 \implies -12.10\text{ dB at } 100\text{ Hz}$$
     Across the broader evaluation zone ($85–120\text{ Hz}$), the minimum response dips to **$-13.73\text{ dB}$**.

#### Measured Notch Depth vs Delay Table

| Sub-Band Delay ($\tau$) | Phase Shift at 100 Hz | Magnitude at 100 Hz (dB) | Worst Notch in 85–120 Hz (dB) | Average Attenuation in 85–120 Hz |
|:---:|:---:|:---:|:---:|:---:|
| **$0.0\text{ ms}$** | $0.0^\circ$ | $0.00\text{ dB}$ | $0.00\text{ dB}$ | $0.00\text{ dB}$ |
| **$1.0\text{ ms}$** | $36.0^\circ$ | $-0.44\text{ dB}$ | $-0.55\text{ dB}$ | $-0.32\text{ dB}$ |
| **$2.0\text{ ms}$** | $72.0^\circ$ | $-1.84\text{ dB}$ | $-2.30\text{ dB}$ | $-1.35\text{ dB}$ |
| **$2.5\text{ ms}$** | $90.0^\circ$ | $-3.01\text{ dB}$ | $-3.71\text{ dB}$ | $-2.20\text{ dB}$ |
| **$3.0\text{ ms}$** | $108.0^\circ$ | $-4.62\text{ dB}$ | $-5.58\text{ dB}$ | $-3.34\text{ dB}$ |
| **$3.5\text{ ms}$** | $126.0^\circ$ | $-6.87\text{ dB}$ | $-8.10\text{ dB}$ | $-4.94\text{ dB}$ |
| **$4.0\text{ ms}$** | $144.0^\circ$ | $-10.21\text{ dB}$ | $-11.73\text{ dB}$ | $-7.29\text{ dB}$ |
| **$4.2\text{ ms}$** | **$151.2^\circ$** | **$-12.10\text{ dB}$** | **$-13.73\text{ dB}$** | **$-8.57\text{ dB}$** |
| **$4.5\text{ ms}$** | $162.0^\circ$ | $-16.14\text{ dB}$ | $-17.92\text{ dB}$ | $-11.23\text{ dB}$ |
| **$5.0\text{ ms}$** | **$180.0^\circ$** | **$-61.43\text{ dB}$** | **$-61.43\text{ dB}$** | **$-17.89\text{ dB}$** |
| **$5.5\text{ ms}$** | $198.0^\circ$ | $-16.08\text{ dB}$ | $-18.46\text{ dB}$ | $-11.45\text{ dB}$ |
| **$6.0\text{ ms}$** | $216.0^\circ$ | $-10.18\text{ dB}$ | $-12.78\text{ dB}$ | $-7.71\text{ dB}$ |
| **Polarity Flip** | **$180.0^\circ$ (All $f$)** | **$-63.52\text{ dB}$** | **$-63.52\text{ dB}$** | **$-18.24\text{ dB}$** |

This confirms the historical claim of an **up to 14 dB crossover notch** near $100\text{ Hz}$ when delays between $4.0\text{ ms}$ and $4.5\text{ ms}$ are applied, and reveals that delays around $5.0\text{ ms}$ or polarity flips produce **total nulls exceeding 60 dB**.

---

### Phase 5 — Windowed Correction Hypothesis & Experimental Prototype

To overcome the fatal crossover failure of legacy Sub-Sync, we evaluated the feasibility of **guarded per-kick full-range processing** (Method D):

#### 5.1 Architecture of Guarded Windowed Full-Range Alignment (GW-FRA)
1. **Kick Transient Onset Detection:**
   Evaluates a smoothed energy envelope follower on the drum stem lowpass band ($<100\text{ Hz}$). Peak detection with dynamic thresholding ($30\%$ of maximum envelope) and a refractory lockout period ($150\text{ ms}$) accurately pinpoints kick attack onsets $\{t_k\}$.
2. **Analysis & Correction Windowing:**
   For each detected kick event $k$, an event window is defined spanning $[t_k - 10\text{ ms}, t_k + 200\text{ ms}]$. The $10\text{ ms}$ pre-trigger captures the initial pressure wave, while the $200\text{ ms}$ post-trigger covers the resonant decay.
3. **Full-Range Bass Shift:**
   Crucially, **no frequency band splitting is performed**. Within the active window, the entire bass waveform is shifted by candidate lag $\tau_k \in [-3.0, +3.0]\text{ ms}$. Because the entire spectrum is shifted by the identical delay, the internal phase relationship between fundamental ($f_0$) and higher harmonics ($2f_0, 3f_0$) is strictly preserved ($100\%$ harmonic coherence), and the crossover notch is mathematically eliminated ($0.00\text{ dB}$ drop).
4. **The Safe-Path Rule:**
   Before applying any correction, the prototype evaluates three objective criteria:
   - *Gain Check:* Expected sub-band sum energy gain must satisfy $\Delta E_{\text{sub}} \ge +0.50\text{ dB}$.
   - *Coherence Check:* Normalized cross-correlation must satisfy $\rho \ge 0.20$ (rejects noise and uncorrelated content).
   - *Crossover Protection:* Mid-band energy change ($85–120\text{ Hz}$) must not drop by more than $-0.50\text{ dB}$.
   - **Safe-Path Fallback:** If any check fails, $\tau_k$ is set to $0.0\text{ ms}$ and polarity is $+1.0$. The unmodified baseline is returned with zero distortion.
5. **Smooth Cross-Fading:**
   Corrected segments are tapered with a Tukey window ($\alpha = 0.30$) and accumulated using partition-of-unity normalization, preventing edge clicks and discontinuities.

#### 5.2 Performance Results of Prototype
- **Mean Sub-Band Gain on Historical Suite:** **$+0.5812\text{ dB}$** (peak gain $+1.3790\text{ dB}$).
- **Degradations:** **0 out of 54 scenarios** (compared to 30 degradations for legacy Sub-Sync).
- **Crossover Integrity:** Worst-case drop was only $-0.442\text{ dB}$ (well within the $-0.50\text{ dB}$ safe bound, completely avoiding the $-24.05\text{ dB}$ legacy drop).
- **Transient Preservation:** High-frequency transients ($>200\text{ Hz}$) outside kick hits remain bit-exact to original.

---

### Phase 6 — Publication Figures Catalog

Five figures were generated in camera-ready high-resolution PNG ($300\text{ DPI}$) and vector SVG formats under `research/death_in_the_club/figures/`:

```
research/death_in_the_club/figures/
├── fig1_phase_interference.png  & .svg  (Figure 1: Phase Interference)
├── fig2_static_delay_trap.png   & .svg  (Figure 2: The Static Delay Trap)
├── fig3_crossover_failure.png   & .svg  (Figure 3: Crossover Failure)
├── fig4_method_comparison.png   & .svg  (Figure 4: Method Comparison)
└── fig5_failure_cases.png       & .svg  (Figure 5: Measured Failure Cases)
```

#### Detailed Figure Descriptions
- **Figure 1 — Phase Interference (Analytical Illustration):**
  Three-panel time-domain waveform display comparing two $50\text{ Hz}$ sine waves (Kick and Bass) and their acoustic sum at $0^\circ$ ($+6.02\text{ dB}$ constructive summation), $90^\circ$ ($+3.01\text{ dB}$ quadrature coherent vector addition: $\sin\omega t + \cos\omega t = \sqrt{2}\sin(\omega t + 45^\circ)$), and $180^\circ$ ($-\infty\text{ dB}$ destructive cancellation). Explicitly notes that two equal-frequency sinusoids at $90^\circ$ are coherent orthogonal signals, distinct from statistically uncorrelated random noise.
- **Figure 2 — The Static Delay Trap:**
  Top panel plots the phase-delay equation $\Delta\phi(f) = 2\pi f \Delta t$ under a fixed $\Delta t = 4.0\text{ ms}$ delay, annotating E1 ($41.2\text{ Hz}$, $59.3^\circ$), $62.5\text{ Hz}$ ($90^\circ$), and B1 ($125\text{ Hz}$, $180^\circ$ anti-phase null). Bottom panel illustrates the resulting acoustic comb-filtering, showing deep notches across the low end.
- **Figure 3 — Crossover Failure:**
  Plots measured frequency response from $30\text{ Hz}$ to $300\text{ Hz}$ comparing unmodified recombination (unity reconstruction $0.00\text{ dB}$) against legacy sub-band delays ($2.5\text{ ms}$, $4.2\text{ ms}$, $5.0\text{ ms}$) and polarity inversion. Highlights the critical $85–120\text{ Hz}$ zone and annotates the verified $-13.7\text{ dB}$ notch and $-63.5\text{ dB}$ polarity null.
- **Figure 4 — Method Comparison (Audited Layout):**
  Two-panel quantitative comparison across clearly separated evaluation subsets. Panel A displays box-plot distributions of sub-band gain ($\Delta E_{\text{sub}}$) on the historical 30-run suite (seed 202611), annotating legacy degradations down to $-1.172\text{ dB}$ (mean: $-0.4512\text{ dB}$) versus guarded prototype gains up to $+1.379\text{ dB}$ (mean: $+0.5812\text{ dB}$, 100% non-negative). Panel B compares mean and worst-case crossover integrity across all 50 valid non-boundary tests, highlighting the $-24.05\text{ dB}$ legacy destruction versus the guarded prototype's safe response ($> -0.45\text{ dB}$).
- **Figure 5 — Failure Cases:**
  Presents two empirically measured failure cases:
  1. *Time-domain waveform degradation* (Run 1 of historical suite): Legacy polarity flip creates destructive cancellation on the bass note tail, dropping sub-sum energy by $-1.17\text{ dB}$.
  2. *Spectral harmonic destruction:* Fast Fourier Transform spectrum demonstrating that legacy sub-sync severely attenuates the 2nd harmonic at $106.7\text{ Hz}$ due to crossover phase destruction.

---

### Phase 7 — Tests, Boundaries & Scientific Reproducibility

An expanded automated pytest test suite containing 12 independent verification checks was implemented in `research/death_in_the_club/test_death_in_the_club.py`. Execution commands and test verification:

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

#### Boundary Handling & Stability Audit
- **Digital Silence:** Handled cleanly with zero division guards; outputs identical silence with zero NaNs or Infs.
- **Sub-Threshold Energy (-60 dBFS):** Safe-path rule prevents spurious amplification.
- **High-Frequency Uncorrelated Noise:** Method D engages safe-path fallback ($\tau = 0.0\text{ ms}$), avoiding the $-0.46\text{ dB}$ degradation created by legacy circular roll.
- **Non-Overlapping Stems:** Safe-path fallback correctly leaves disjoint stems unmodified.
- **Signal Length & Format:** All methods strictly preserve frame count, stereo channel count, and float32 data types.

---

### Scientific Integrity & Methodological Boundaries

In compliance with strict scientific research guidelines:
1. **No Invented Numbers:** All numerical values in this report were measured directly using 64-bit numerical computation in NumPy/SciPy from deterministic signal formulas or actual repository code.
2. **Clear Signal Labeling:** Every generated test signal is synthetic. No simulated data is described as commercial multitrack recordings.
3. **No Unwarranted Quality Claims:** We explicitly emphasize that acoustic pressure gain ($\text{dB}$) does not equate to perceptual quality. Headroom consumption and potential midrange masking require formal MUSHRA listening tests.
4. **No Premature Feature Completion Claims:** Sub-Sync is **not** complete or production-ready. Method D is an experimental reference prototype demonstrating proof of concept; it has not been validated across diverse multitrack genres.
5. **Production Code Immutability:** No production DSP algorithms in `remaster_engine.py` or `PHARMAKON_PRO` were modified or bypassed. All research was conducted in the isolated `research/death_in_the_club/` workspace.

---

### Deliverables Checklist

- [x] `EXPERIMENT_REPORT.md` — Comprehensive research report, failure mode analysis, and verified claims.
- [x] `measurements.csv` — Full tabular record of 216 benchmark runs across 54 scenarios.
- [x] `experiment_config.json` — Environment metadata, seeds, filter parameters, and summary statistics.
- [x] `figures/` — High-resolution PNG (300 DPI) and SVG figures (Figs 1, 2, 3, 4, 5).
- [x] `REPRODUCE.md` — Step-by-step reproduction instructions and execution commands.
- [x] `OPEN_QUESTIONS.md` — Unresolved research questions, psychoacoustic considerations, and roadmap.
