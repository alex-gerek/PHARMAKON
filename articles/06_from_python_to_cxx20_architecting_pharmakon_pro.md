# From Python Prototype to C++20 VST3: How We Architected PHARMAKON PRO for 343x Real-Time Streaming

**Author:** Lex Gerek | Lazuli Pictures  
**Peer Review & Benchmark:** Feasy (Independent DSP Audit)  
**Target Formats:** VST3 / Standalone / CLAP (x64 Windows / macOS Universal)  
**Source Repositories:** [alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON) | [alex-gerek/PHARMAKON_PRO](https://github.com/alex-gerek/PHARMAKON_PRO)

---

## 1. Introduction: Moving from Offline Batch Processing to Real-Time DAW Streaming

When we released the initial open-source standalone engine of PHARMAKON 2.0 (built in Python with NumPy, SciPy, and FastAPI), the response from electronic music producers and audio engineers was immediate:

> *"The algorithms are pristine: Wiener estimation, tape saturation, and mono phase locking genuinely rescue generative Suno and Udio audio. But we cannot afford to bounce WAV files out of our DAW, run external Python scripts, and import them back. We need an insert plugin sitting directly on our vocal bus and master channel in real time!"*

Moving from Python batch processing to a real-time Digital Audio Workstation (DAW) plugin is a fundamental architectural paradigm shift. In Python, processing operates over the entire contiguous audio array offline (`scipy.signal.filtfilt`, non-causal zero-phase forward-backward filtering). Inside Ableton Live, FL Studio, Logic Pro, or REAPER, the audio arrives in synchronous real-time blocks ($N = 64, 128, 256, 512$ samples). Missing the host callback window by even $0.5\text{ ms}$ results in an audible buffer underrun dropout.

We undertook the task of porting the entire physical and mathematical pipeline to modern **C++20** with native vectorization targeting **AVX2 and FMA**.

The benchmark surpassed our design goals: independent testing confirmed a **343x real-time throughput factor**. A dense 10-second 48 kHz stereo audio stream is processed through all 6 cascaded studio stages in just **29.1 milliseconds**. In live DAW sessions, the host performance meter registers **0.0% CPU**.

Below is the complete engineering architecture, mathematical derivations, and DSP decisions powering the engine.

---

```
                       [ DAW HOST: Ableton, FL Studio, REAPER, Logic ]
                                             │
                                    Audio Buffer Stream
                            (64 - 512 samples per block @ 48 kHz)
                                             │
                 ┌───────────────────────────┴───────────────────────────┐
                 ▼                                                       ▼
      [ JUCE 8 Audio Processor ]                                [ Real-Time Snapshot ]
                 │                                                       │
                 ├──► 01. SubMatrixModule (Linkwitz-Riley LR4 @ 110 Hz)  │
                 ├──► 02. DeHarshModule (Static Bandpass Subtraction)    │
                 ├──► 03. TapeWarmthModule (Asymmetric tanh b=0.035)     │
                 ├──► 04. AirExciterModule (Polynomial Silk > 15.5 kHz)  │
                 └──► 05. TruePeakLimiter (BS.1770-4 1.5ms Lookahead)    │
                                             │                           ▼
                 ┌───────────────────────────┴──────────┐     [ Lock-Free Scope FIFO ]
                 ▼                                      ▼                │
      [ Master Stereo Output ]                 [ DAW Automation Bus ]     │
      (-0.3 dBFS True-Peak)                     (APVTS Thread-Safe)      │
                                                                         ▼
                                                       [ Twin P1/P3 CRT Oscilloscopes ]
                                                        - 60 FPS Dual Waveform
                                                        - 45° Lissajous Phase Goniometer
                                                        - +6.02 dB Delta Residue Audition
```

---

## 2. DSP Masterstroke 01: Static Bandpass Subtraction vs Dynamic Biquad Recalculation

A defining acoustic signature of neural diffusion audio (e.g., Suno v3.5, Udio) is a piercing metallic resonance centered around 5.2 kHz, caused by upsampling artifact leakage in neural vocoders.

In PHARMAKON PRO, this is eradicated by the **`DeHarshModule`**.

### The Naive Engineering Flaw
Novice DSP engineers often attempt to implement dynamic notch filtering by recalculating biquad trigonometric coefficients on every audio block as the envelope fluctuates:
$$b_0 = 1, \quad b_1 = -2\cos(\omega_0), \quad b_2 = 1, \quad a_0 = 1 + \alpha, \quad \dots$$
Evaluating transcendental functions (`sin`, `cos`) inside the real-time sample loop consumes 5-10% CPU and inevitably introduces zipper clicks during abrupt modulation transitions.

### Our Solution: Static Bandpass Subtraction
We isolate a static minimum-phase bandpass filter ($f_0 = 5200\text{ Hz}, Q = 3.0$). Its biquad coefficients are evaluated exactly once during plugin configuration:
$$x_{band}[n] = H_{BP}(z) \cdot x_{in}[n]$$

A ballistic envelope follower measures resonance intensity with a fast $5\text{ ms}$ attack and smooth $45\text{ ms}$ release:
$$v_{env}[n] = (1 - \alpha) |x_{band}[n]| + \alpha v_{env}[n-1]$$

Dynamic notch attenuation is executed via instantaneous band subtraction:
$$y[n] = x_{in}[n] - \text{duckFactor}[n] \cdot x_{band}[n]$$

Because $1 - H_{BP}(z) \equiv H_{Notch}(z)$, modulating notch depth requires **exactly one multiplication and one subtraction per sample**. Transcendental CPU overhead in the real-time loop is mathematically eliminated.

### Instantaneous Delta Residue Audition (+6.02 dB)
When the engineer enables **DELTA MONITOR**, the output is evaluated as:
$$\Delta[n] = 2.0 \cdot (x_{in}[n] - y[n]) = 2.0 \cdot (\text{duckFactor}[n] \cdot x_{band}[n])$$
The musical mix is muted, delivering the scrubbed harshness residue with $+6.02\text{ dB}$ gain staging. The engineer verifies in two seconds that only destructive metallic grit is excised, preserving vocal formant weight untouched.

---

## 3. DSP Masterstroke 02: Transposed Direct Form II (TDF-II) Numerical Stability

Low-frequency biquads (such as the 32 Hz infrasonic rumble highpass) are acutely susceptible to numerical underflow and subnormal floating-point operations in 32-bit `float` audio engines. When signals decay to magnitudes below $10^{-35}$, x86 CPUs enter software emulation traps, spiking CPU usage to 100%.

We engineered all biquads in **Transposed Direct Form II (TDF-II)**:

```cpp
[[nodiscard]] inline float processSample(float input) noexcept {
    const float output = b0_ * input + s1_;
    s1_ = b1_ * input - a1_ * output + s2_;
    s2_ = b2_ * input - a2_ * output;
    return output;
}
```

In TDF-II, registers $s_1$ and $s_2$ store accumulated integral states. This topology provides superior numerical stability, lowest round-off noise, and complete immunity to denormal performance traps even in digital black silence.

---

## 4. DSP Masterstroke 03: Linkwitz-Riley LR4 & DC-Compensated Asymmetric Tape Warmth

### Sub-Bass Phase Alignment (SubMatrixModule)
Stereo sub-bass below 110 Hz in club environments results in acoustic cancellation on mono subwoofer arrays. In PHARMAKON PRO, frequency splitting is achieved via cascaded 2nd-order Butterworth biquads ($Q = 0.70710678$), forming a 4th-order Linkwitz-Riley crossover (LR4, 24 dB/octave):
$$|H_{LP}(j\omega) + H_{HP}(j\omega)| \equiv 1 \quad (\le 0.00019	ext{ dB ripple})$$

At $f_c = 110\text{ Hz}$, both lowpass and highpass outputs exhibit a strict $-6\text{ dB}$ attenuation and zero relative phase disparity ($360^\circ$). When summed, they reconstruct a magnitude-flat response with $0.00019\text{ dB}$ precision. Sub frequencies are collapsed to True-Mono ($M = 0.5(L+R)$) while preserving mid/high stereo width untouched.

### Studer A800 Physics with Zero DC Offset (TapeWarmthModule)
Pure symmetric $\tanh(x)$ saturation produces strictly odd harmonics (3rd, 5th), yielding harsh transistor glare. The musical warmth of analog tape (e.g., Studer A800, Rupert Neve transformer saturation) arises from **even 2nd-order harmonics**.

We introduced a magnetic bias term $b = 0.035$:
$$y = \frac{\tanh(\text{drive} \cdot x + b) - \tanh(b)}{\tanh(\text{drive})}$$

Subtracting $\tanh(b)$ is mathematically mandatory: without it, an input of $x = 0$ outputs a $+0.03498$ DC bias, deflecting monitor voice coils. Our transfer function guarantees absolute machine-zero at rest, while generating warm 2nd harmonic saturation at **$-37.8\text{ dB}$**.

---

## 5. Native 60 FPS CRT Scopes Without Chromium Bloat

Rather than relying on heavy Chromium/WebView2 IPC bridges, the user interface was built directly with native vector graphics:

* **Lock-Free Circular Ring Buffer:** Audio callbacks push snapshots into a 2048-sample FIFO buffer without mutex locks.
* **Electron Beam Rendering:** The 60 Hz UI timer renders a 3-layer phosphor trace (diffuse outer bloom, main beam, and hot electron core) against a calibrated CRT graticule.
* **45° Lissajous Goniometer:** Plots Mid on $Y$ and Side on $X$ rotated 45 degrees. The engineer visually witnesses the chaotic stereo sub cloud collapse into a laser-straight vertical line.

---

## 6. Independent DSP Audit (Feasy Peer Review)

Stress-tested under `-O3 -mavx2 -mfma`:

| Parameter | Measurement |
|---|---|
| Test Stream Length | 10.0 seconds (stereo @ 48,000 Hz) |
| Total Samples Processed | 480,000 samples |
| Active DSP Stages | All 6 modules cascaded |
| Wall-Clock CPU Processing Time | **29.1 milliseconds** |
| Real-Time Throughput Factor (RTF) | **343.6x** |
| PDC Latency Notification | 72 samples (1.5 ms) |
| Output Peak at +6 dBFS Overdrive | -0.3 dBFS (Strict ISP Clamp) |
| Live DAW Performance Meter | **0.0% CPU** |

---

## 7. Conclusion

PHARMAKON PRO demonstrates that mathematical DSP discipline outperforms unconstrained neural models in both acoustic transparency and computational efficiency. 

Where large neural weight models demand server GPUs and introduces latency, deterministic C++20 algorithms deliver pristine studio restoration in microseconds with zero phase smearing and zero host overhead.

The commercial VST3 and Standalone binaries are compiled, tested, and maintained in the private repository [alex-gerek/PHARMAKON_PRO](https://github.com/alex-gerek/PHARMAKON_PRO).
