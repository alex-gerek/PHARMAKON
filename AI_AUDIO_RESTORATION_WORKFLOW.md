# Neural Audio Detox // AI Audio Restoration Workflow
## Fixing Metallic Whistle, Phase Dispersion & Sibilance in Suno & Udio Generative Audio

**Author:** Lex Gerek | Lazuli Pictures  
**Standard:** PHARMAKON 2.0 Studio Restoration Engine  
**Compatibility:** Suno (v3 / v3.5 / v4), Udio (v1 / v1.5 / Hi-Fi), ElevenLabs Speech  

---

## 1. Anatomy of AI Audio Defects

Generative neural audio does not originate from acoustic vibrating instruments or analog circuitry. It is synthesized by latent diffusion and transformer decoders (vocoders) reconstructing spectrogram slices into waveform frames. This generates 4 unmistakable acoustic defects:

```
+--------------------------+-------------------------------------------------------+
| Acoustic AI Defect       | Physics Root Cause                                    |
+--------------------------+-------------------------------------------------------+
| 1. Metallic Whistle      | Periodic interpolation ripples from neural upsampling |
|    (5.0 kHz - 5.5 kHz)   | vocoders (EnCodec / SoundStream artifact).            |
+--------------------------+-------------------------------------------------------+
| 2. Sub-Bass Stereo Phase | Non-coherent spatial diffusion: low frequencies      |
|    Dispersion (< 120 Hz) | cancel out in mono playback and club subwoofers.      |
+--------------------------+-------------------------------------------------------+
| 3. Cold Glassy Highs     | Absence of analog harmonic saturation and lack of     |
|    (Odd Harmonics Only)  | even-order physical tube/tape distortion.             |
+--------------------------+-------------------------------------------------------+
| 4. Missing Air (>16 kHz) | Brickwall cutoffs imposed by neural model training   |
|                          | at 32 kHz - 44.1 kHz internal sample rates.          |
+--------------------------+-------------------------------------------------------+
```

---

## 2. The 5-Stage Neural Detox Pipeline

PHARMAKON 2.0 addresses each acoustic defect with deterministic, causal, closed-form DSP:

### Stage 1: Infrasonic Clean & Sub-Bass Phase Lock (< 120 Hz)
- **Problem:** Low-frequency rumble under 32 Hz steals amplifier power and causes speaker intermodulation. Uncorrelated stereo sub creates phase mud.
- **DSP Action:**
  1. 4th-order Butterworth highpass at $32\text{ Hz}$ cleanly cuts DC offset and sub-audible flutter.
  2. 4th-order Linkwitz-Riley (LR4, 24 dB/oct) crossover at $110 - 120\text{ Hz}$ splits audio into Sub and Mid-High bands.
  3. The Sub band is summed to True-Mono ($M = \frac{L + R}{2}, S = 0$).
  4. Phase correlation jumps from typical raw values of $+0.35$ to $+0.99$, locking the kick and bass into a rock-solid center anchor.

### Stage 2: Dynamic Anti-AI De-Harshing (5.0 - 5.5 kHz)
- **Problem:** Static notch filters permanently kill presence and air even when the singer isn't hitting sibilant syllables.
- **DSP Action:**
  1. Biquad bandpass filter ($f_0 = 5200\text{ Hz}, Q = 3.0$) extracts the instantaneous neural resonance envelope.
  2. Ballistic envelope detector ($\tau_{attack} = 5\text{ ms}, \tau_{release} = 45\text{ ms}$) measures harshness spikes in real time.
  3. Dynamic subtraction removes only the harshness energy without touching surrounding guitar body or vocal fundamentals.
  4. The **Delta Residue ($\Delta$)** reveals the isolated metallic whistle cleanly removed from the audio.

### Stage 3: Studer A800 Asymmetric Tape Warmth
- **Problem:** Neural audio lacks analog body and contains sterile, sharp digital transitions.
- **DSP Action:**
  1. 4X polyphase oversampled asymmetric hyperbolic tangent curve with global asymptote scaling:
     $$y = \left(\tanh(\text{drive} \cdot x + b) - \tanh(b)\right) \cdot \frac{\text{ceiling}}{1 + \tanh(b)}$$
  2. Working bias $b = 0.035$ generates musical **even 2nd harmonics at -38.05 dBc**, paired with a $10\text{ Hz}$ recursive one-pole DC-blocker ($|\text{DC}| < 10^{-7}$ in `float32`), mimicking physical magnetic tape compression.
  3. Removes digital glare and provides vintage analog cohesion ("glue").

### Stage 4: High-Frequency Polynomial Silk Exciter (> 15.5 kHz)
- **Problem:** Most neural models drop off sharply above 16 kHz, leaving high-hats and vocal breath feeling "choked".
- **DSP Action:**
  1. 4th-order bandpass ($8.0 - 13.0\text{ kHz}$) isolates high-mid donor energy.
  2. Polynomial harmonic generation ($y = x + 0.65x^2 - 0.25x^3$) synthesizes natural overtones extending up to 22 kHz.
  3. 4th-order highpass ($15.5\text{ kHz}$) injects only pristine silk air into the master bus.

### Stage 5: 4X Oversampled True-Peak Limiter
- **Problem:** Inter-sample peaks (ISP) cause clipping distortion when tracks are converted to streaming MP3/AAC formats.
- **DSP Action:**
  1. 4X polyphase sinc interpolation detects continuous analog peaks between discrete samples.
  2. Strict ceiling set to $-0.3\text{ dBFS}$ with $1.5\text{ ms}$ lookahead.
  3. For EBU R128 broadcast delivery and the -1 dBTP recommendation of Spotify / Apple Music, set the ceiling to $-1.0\text{ dBTP}$.

---

## 3. Presets Quick-Reference

| Preset | Target Genre / Problem | Sub Cut | Crossover | De-Harsh Freq | Tape Drive |
|---|---|:---:|:---:|:---:|:---:|
| **Suno Detox** | Suno v3.5 & v4 Tracks | $35\text{ Hz}$ | $130\text{ Hz}$ | $5200\text{ Hz}$ | $1.05\text{x}$ |
| **Udio Polish** | Udio 1.5 & Hi-Fi Tracks | $30\text{ Hz}$ | $115\text{ Hz}$ | $6100\text{ Hz}$ | $1.06\text{x}$ |
| **Club Punch** | EDM, Hip-Hop, Techno | $28\text{ Hz}$ | $140\text{ Hz}$ | $4800\text{ Hz}$ | $1.08\text{x}$ |
| **Audiophile Master** | Acoustic, Jazz, Orchestral | $24\text{ Hz}$ | $95\text{ Hz}$ | $5500\text{ Hz}$ | $1.01\text{x}$ |

---

## 4. Reading the Mastering & Spectral Diagnosis Certificate

When mastering completes in PHARMAKON, click **`📜 MASTERING REPORT`**:

- **Red Line (Raw AI Input):** Original audio frequency response showing low-end clutter and resonance spikes.
- **Green Line (PHARMAKON Master):** Mastered output with smoothed frequency balance and controlled dynamics.
- **Amber Dashed Line (Delta Residue $\Delta$):** Direct mathematical proof of surgery. Shows the exact isolated noise and sibilant whistle removed from your track.
- **Sub-Bass Phase Correlation:** Look for values $> +0.95$ confirming phase-locked club-ready bass.
- **Dynamic Crest Factor:** Values around $10.0 - 12.0\text{ dB}$ prove that transients and drum punch were fully preserved without flat-lining.
