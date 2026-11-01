# Why EQ Fails on Generative Audio: The Physics of Dead Air Above 16 kHz

**Author:** Lex Gerek (Sound Architect / Engineer)  
**Project:** PHARMAKON 2.0 Studio Console  
**Proof Graphic:** `Spectral_Proof_EQ_vs_Exciter.png`  
**Implementation:** `remaster_engine.py` (`harmonic_air_exciter`)

The most common advice given to producers trying to fix Suno or Udio tracks is:
> *"Just slap an EQ on the master bus, boost a high shelf at 16 kHz by +8 dB, and your mix will instantly breathe."*

It seems intuitive: the track sounds dull and claustrophobic, so boosting the high frequencies should open it up.  
In practice, it sounds terrible: instead of silky air and open vocal shimmer, you get harsh metallic screech, digital grain, and abrasive hiss.

Why does an equalizer fail on generative audio? The answer lies in signal mathematics.

---

### 1. The Fundamental Principle: An Equalizer Only Multiplies

An equalizer is a **frequency-selective multiplier**. It multiplies the amplitude of energy already present at frequency $f$ by a gain factor $K$:

$$Output(f) = Input(f) \cdot K(f)$$

* A $+8\text{ dB}$ shelf represents an amplification multiplier $K \approx 2.51$.
* If the acoustic signal at frequency $f$ is physically zero ($Input = 0$), the equation yields zero:
  $$0 \times 2.51 = 0$$

An equalizer cannot synthesize a single missing harmonic. It can only increase the level of information that already exists in the recording.

---

### 2. The 15.5 kHz Brickwall Cliff

To optimize latency and model checkpoint size, generative vocoders (Suno, Udio) render audio using low sampling rates (often 32 kHz with a 16 kHz Nyquist ceiling) or apply steep anti-aliasing cutoffs at **15.5 kHz**.

Viewing raw generative audio in a spectral FFT analyzer reveals an unnatural **vertical cliff**:
* Full acoustic energy below 15 kHz.
* At exactly 15.5 kHz, energy plunges off a precipice with a slope exceeding **~1400 dB / Octave**, dropping into a $-85\text{ dBFS}$ digital void.

Above 15.5 kHz, there is **zero acoustic signal**: no cymbal overtones, no vocal breath, and no room reverberation decay. Only low-level quantization noise and diffusion phase jitter remain.

Boosting a high shelf at 16 kHz simply pulls that $-85\text{ dBFS}$ noise floor up to $-77\text{ dBFS}$, converting dullness into ear fatigue.

---

### 3. The PHARMAKON 2.0 Solution: 4X Polyphase Harmonic Synthesis

Instead of equalizing dead air, PHARMAKON 2.0 physically synthesizes replacement harmonics from intact donor bands:

1. **Donor Band Selection (8 - 13 kHz):**  
   We isolate the upper-mid acoustic band using a zero-phase 4th-order equivalent bandpass filter where musical information remains untouched by the vocoder cutoff.

2. **4X Polyphase Upsampling (192 kHz):**  
   Generating 3rd-order harmonics on a 12.5 kHz donor yields frequencies up to $37.5\text{ kHz}$. At standard 48 kHz, this creates severe foldover aliasing at **10.5 kHz** ($|48 - 37.5| = 10.5\text{ kHz}$), and down to **6.6 kHz** on 44.1 kHz ($|44.1 - 37.5| = 6.6\text{ kHz}$). Running in a 192 kHz polyphase domain extends the Nyquist limit to 96 kHz, mathematically eliminating aliasing.

3. **Asymmetric Taylor Polynomial:**  
   Signal is routed through:
   $$y = x + 0.65 x^2 - 0.25 x^3$$
   The quadratic term generates musical even 2nd harmonics ($2f$), while the cubic term produces odd 3rd harmonics ($3f$), reconstructing a continuous dense air taper across 16 - 22 kHz. Soft pre-filtering $\tanh(2.2y) \cdot 0.45$ tames high-frequency crest spikes.

4. **8th-Order Equivalent Zero-Phase Isolation (`filtfilt`):**  
   A 4th-order Butterworth highpass filter processed forward and backward via `filtfilt` yields an **8th-order equivalent response (-48 dB/Octave)** with **zero phase rotation ($\theta(f) = 0$)**, preventing comb-filtering cancellations when blended into the master bus.

5. **Headroom Notice:**  
   Harmonic air injection introduces a minor peak energy rise (+0.2 to +0.5 dB). In the PHARMAKON pipeline, this is naturally handed off to our 4X True-Peak Limiter stage (Article 05) to ensure absolute broadcast ceiling compliance.

```python
import numpy as np
from scipy import signal

def harmonic_air_exciter(audio, sr, drive=0.15, cutoff=15500.0, donor_band=(8000.0, 13000.0), oversample=4):
    """
    4X Polyphase Harmonic Air Synthesizer.
    Reconstructs lost 16-22 kHz frequencies via polynomial harmonic synthesis.
    Output peak energy increases slightly (+0.2 to +0.5 dB); follow with a True-Peak Limiter stage.
    """
    orig_len = len(audio)
    nyquist = 0.5 * sr
    
    # 1. Isolate intact donor band (Zero-phase 4th-order equivalent bandpass)
    b_band, a_band = signal.butter(2, [donor_band[0] / nyquist, donor_band[1] / nyquist], btype='band')
    donor = signal.filtfilt(b_band, a_band, audio, axis=0)

    # 2. 4X polyphase upsampling (anti-aliasing protection up to 96 kHz Nyquist)
    donor_4x = signal.resample_poly(donor, up=oversample, down=1, axis=0)
    
    # 3. Asymmetric non-linear 2nd & 3rd harmonic generation
    harmonics_4x = donor_4x + 0.65 * (donor_4x ** 2) - 0.25 * (donor_4x ** 3)
    harmonics_4x = np.tanh(2.2 * harmonics_4x) * 0.45

    # 4. Zero-phase isolation strictly above vocoder cutoff (8th-order equivalent response, -48 dB/Oct)
    sr_4x = sr * oversample
    b_hp, a_hp = signal.butter(4, cutoff / (0.5 * sr_4x), btype='high')
    air_4x = signal.filtfilt(b_hp, a_hp, harmonics_4x, axis=0)

    # 5. Polyphase downsample to 1X and pristine bus injection
    air_1x = signal.resample_poly(air_4x, up=1, down=oversample, axis=0)[:orig_len]
    return (audio + air_1x * drive).astype(np.float32)
```

The resulting audio exhibits a seamless, organic spectral extension up to 22 kHz without harsh digital artifacts.

---
*Repository:* [https://github.com/alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON)
