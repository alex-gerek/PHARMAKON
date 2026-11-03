# Empirical Telemetry & Figure Generation Report
**Article:** Beyond tanh: Engineering Asymmetric Saturation for Digital Audio (v2.6)  
**Author:** Lex Gerek (Sound Architect / Audio Engineer)  
**Project:** PHARMAKON 2.0 Studio Console  
**Script:** `articles/generate_figures.py`  
**Reference Commit:** `0af338f`  

---

## 1. Mathematical Parameters & Calibration

* **Drive:** $1.05$
* **Bias:** $0.035$
* **Ceiling:** $0.98$
* **Oversampling Factor:** $4\times$ polyphase FIR (`scipy.signal.resample_poly`)
* **Pre-Emphasis:** 1st-order Butterworth High-Pass at $3500\text{ Hz}$, gain factor $+0.20$ ($+1.58\text{ dB}$ extreme HF shelf)
* **DC-Blocker:** 1-pole recursive high-pass ($10\text{ Hz}$, $R = 1 - 2\pi \cdot 10 / 48000 = 0.99869$)

---

## 2. Telemetry Results by Figure

### Figure 1 — Asymmetric Saturation Transfer Functions
* **Formula:**
  $$y(u) = [\tanh(u + b) - \tanh(b)] \cdot \left[\frac{\text{ceiling}}{1 + \tanh(b)}\right]$$
* **Calculated Upper Asymptote ($x \to +\infty$):** $+0.913745\text{ FS}$
* **Calculated Lower Asymptote ($x \to -\infty$):** $-0.980000\text{ FS}$ (Strict ceiling preserved)
* **Raw Unscaled Negative Overshoot ($x \to -\infty$):** $-1.034986\text{ FS}$ (Over 0 dBFS, successfully neutralized by global asymptote scaling)

### Figure 2 — Level-Dependent Harmonic Distortion
Measured using 64-bit double precision, 144,000-point FFT ($3.0\text{ s}$ @ $48\text{ kHz}$) with a 7-term Blackman-Harris window:

| Input Level | $H_2$ (Even Octave) | $H_3$ (Odd Compression) | $\Delta (H_3 - H_2)$ | Regime |
|---|:---:|:---:|:---:|---|
| **$0.0\text{ dBFS}$** | **$-38.05\text{ dBc}$** | $-22.85\text{ dBc}$ | $+15.20\text{ dB}$ | High-density soft tape limiting |
| **$-3.0\text{ dBFS}$** | **$-39.53\text{ dBc}$** | $-27.88\text{ dBc}$ | $+11.66\text{ dB}$ | Vintage console drive |
| **$-6.0\text{ dBFS}$** | **$-41.67\text{ dBc}$** | $-33.34\text{ dBc}$ | $+8.33\text{ dB}$ | Discrete Class-A warmth |
| **$-12.0\text{ dBFS}$** | **$-46.97\text{ dBc}$** | $-44.92\text{ dBc}$ | $+2.05\text{ dB}$ | Subtle transformer sheen |
| **$-18.0\text{ dBFS}$** | **$-52.78\text{ dBc}$** | $-56.81\text{ dBc}$ | **$-4.02\text{ dB}$** | **$H_2$ Dominates (Octave overtone)** |

* **Exact Harmonic Equivalence Crossover Point:**
  * **Production Model (drive = 1.05):** **$-14.01\text{ dBFS}$** (Numerical FFT, $H_2 = H_3 = -48.89\text{ dBc}$).
  * **Analytical Explanation of the $\approx -13.6\text{ dBFS}$ vs $-14.01\text{ dBFS}$ Delta:**
    * In theoretical derivations where gain is normalized to unity ($\text{drive} = 1.0$, as in Section 3 of the paper), the Taylor equivalence equation $A_{\text{cross}} = \frac{6\tanh(b)}{1 \cdot [1 - 3\tanh^2(b)]} = 0.21069$ yields **$-13.53\text{ dBFS} \approx -13.6\text{ dBFS}$**.
    * In the production engine and Table B of Section 8, the drive parameter is set to $\text{drive} = 1.05$ ($+0.424\text{ dB}$ additional gain). This shifts the crossover threshold downward by $0.42\text{ dB}$ to $-13.95\text{ dBFS}$ analytically.
    * The rigorous 64-bit numerical FFT simulation including higher-order odd terms ($x^5, x^7$) pinpoints the exact physical crossover at **$-14.01\text{ dBFS}$**.
  * Below $-14.01\text{ dBFS}$, even harmonic $H_2$ exceeds $H_3$, creating characteristic analog low-level warmth. Above this threshold, $H_3$ rises to provide progressive peak cushion.

### Figure 3 — Waveform Transformation
Measured on $1\text{ kHz}$ sine at $0\text{ dBFS}$ ($1.000\text{ FS}$) through the full `apply_tape_warmth_v2` pipeline:
* **Steady-State Window:** $t \in [50.0, 54.0]\text{ ms}$ ($4$ full cycles).
* **Positive Peak Output:** $+0.7370\text{ FS}$
* **Negative Peak Output:** $-0.7558\text{ FS}$
* **Asymmetry Difference:** $\Delta = 0.0188\text{ FS}$ (produces the $-38.05\text{ dBc}$ second harmonic).
* **DC Offset in Steady-State:** $< 10^{-15}$ (cleared by 1-pole recursive DC-blocker).

---

## 3. Artifact Files Generated

Each figure is exported in three standard formats:
* **SVG:** Vector graphic for web, responsive articles, and high-fidelity publication (`.svg`).
* **PNG:** Raster image at $300\text{ DPI}$ ($> 2800\times 1800\text{ px}$ resolution) (`.png`).
* **PDF:** High-resolution vector document for camera-ready IEEE / AES papers (`.pdf`).

Files are saved to both `articles/figures/` and `articles/img/`.
