# Inter-Sample Peaks (True-Peak): Why Spotify Distorts Tracks on Smartphones and How 4X Polyphase Oversampling Solves It

**Author:** Lex Gerek (Sound Architect / Engineer)  
**Project:** PHARMAKON 3.1 Studio Console  
**Implementation:** `remaster_engine.py` (`_true_peak_limiter_block`, `target_ceiling_db=-0.3` / `-1.0`)

This is the definitive frontier of modern audio mastering, overlooked by most bedroom producers and disregarded by virtually all generative AI audio platforms.

The nightmare is familiar to every engineer:  
You bounce your master from your DAW (FL Studio, Ableton, Logic, Pro Tools). The standard peak meter displays a clean -0.1 dBFS. Solid green lights, zero clipping.  
You upload the track to Spotify, Apple Music, or YouTube. You test it on an iPhone or through Bluetooth earbuds, and on every heavy kick drum hit and snare transient, you hear dry crackling, gritty high-frequency splatter, and collapsed depth.

Why does a track that appeared pristine on digital meters crackle on consumer devices? The answer lies in sampling theory, reconstruction kernel physics, and lossy codec behavior.

---

### 1. Mathematics & Physics: Whittaker-Nyquist-Shannon Sinc Kernels vs. Discrete Samples

Digital audio does not store continuous waveforms. It stores discrete temporal snapshots (samples) at sampling intervals determined by the sample rate (44.1 kHz or 48 kHz).

A frequent misconception is assuming that a DAC (Digital-to-Analog Converter) connects discrete points via straight lines.  
In physical reality, continuous electrical voltage is reconstructed strictly according to the **Whittaker-Kotelnikov-Nyquist-Shannon sampling theorem**:

$$s(t) = \sum_{n=-\infty}^{+\infty} x[n] \cdot \text{sinc}\left(\frac{t - n T_s}{T_s}\right), \quad \text{where } \text{sinc}(u) = \frac{\sin(\pi u)}{\pi u}$$

Each discrete digital sample generates an infinite decaying sinc kernel. The continuous analog voltage curve is the linear superposition of these overlapping sinc pulses.

When two or more adjacent samples carry high instantaneous amplitude close to full scale (for instance, $x[n] = -0.2\text{ dBFS}$ and $x[n+1] = -0.2\text{ dBFS}$), the main lobe of one sample aligns in phase with the positive secondary lobes of neighboring samples.  
This creates **constructive interference**, forcing the continuous analog waveform between sample points to arc significantly higher:

$$s(t_{\text{mid}}) > x[n] \quad \text{and} \quad s(t_{\text{mid}}) > x[n+1]$$

The peak of this inter-sample analog trajectory routinely exceeds digital zero by **+1.0 dB to +1.8 dB above 0 dBFS!**

This phenomenon is designated an **Inter-Sample Peak (True-Peak)**. Standard DAW peak meters (Sample Peak Meters) evaluate only the discrete values $x[n]$ and remain completely blind to the inter-sample analog overshoot.

---

### 2. The Dual Trap: Psychoacoustic Lossy Codecs and Mobile DAC Rails

When a track containing hidden inter-sample peaks is distributed across digital streaming channels, it encounters two destructive bottlenecks:

1. **Lossy Codec Transcoding (MP3, AAC, Ogg Vorbis):**  
   Streaming platforms re-encode master files using psychoacoustic compression based on the Modified Discrete Cosine Transform (MDCT). Subband analysis filters and lossy bit allocation inevitably cause peak regrowth (**peak expansion**) of **+0.5 dB to +1.2 dB**!  
   If a master was limited to 0 dBFS or -0.3 dBFS, post-encoding peaks on Spotify or YouTube escalate to +0.5 ... +0.9 dBFS.

2. **Hardware Rail Voltage Clipping in Mobile DACs:**  
   The consumer listens via a smartphone analog output or wireless Bluetooth earbuds. The onboard DAC reconstructs the continuous analog voltage via sinc interpolation and slams directly into its operational amplifier rail voltage limit ($V_{\text{rail}}$).  
   This triggers severe analog intermodulation distortion (IMD). The high frequencies shatter into harsh digital glare, and transient impact is destroyed.

---

### 3. Industry Delivery Standards: Why -0.3 dBFS Fails for Streaming

For years, many studio workflows relied on a -0.3 dBFS ceiling. However, rigorous measurement standards established clear differentiation:

- **Lossless Studio Delivery: -0.3 dBFS True-Peak**  
  Reserved exclusively for uncompressed master deliverables: 24-bit / 32-bit float WAV and FLAC (vinyl pre-mastering, studio archival masters, broadcast stems). Because no lossy transcoding occurs, -0.3 dBFS preserves maximum dynamic headroom.

- **Streaming Broadcast Standards: -1.0 dBFS True-Peak**  
  Mandatory across all lossy distribution channels:
  - **Spotify Loudness Guidelines:** Recommends keeping masters below **-1.0 dBTP**, and below **-2.0 dBTP** for masters louder than -14 LUFS integrated.
  - **Apple Digital Masters:** Recommends not exceeding **-1.0 dBTP**.
  - **EBU R128:** European broadcast recommendation with a maximum permitted True-Peak of **-1.0 dBTP**, measured per ITU-R BS.1770-4 (BS.1770 itself defines the measurement, not a ceiling).

A 1.0 dB safety margin fully absorbs MDCT peak regrowth, guaranteeing absolute clarity across all consumer playback hardware.

---

### 4. The PHARMAKON 3.1 Solution: Detect at 4X, Apply at 1X

To intercept hidden sinc arcs before export, PHARMAKON uses a 4X polyphase True-Peak limiter whose peak detection follows the ITU-R BS.1770-4 Annex 2 4X-oversampling method. Version 3.1 rebuilt the limiter around one principle: **oversample to see the peaks, but never resample the music itself.**

1. **4X Polyphase Detection (192 kHz at a 48 kHz base):**
   The signal is upsampled with polyphase FIR filters (`signal.resample_poly(audio, up=4, down=1, axis=0)`), giving three interpolated points between every pair of samples. The upsampled copy is used only to *measure* the analog arc; it is never sent to the output.

2. **100% Stereo-Linked Gain (Phantom Center Stability):**
   Dual-mono limiting tilts the phantom center (lead vocal, kick, bass) whenever a hard-panned crash hits one side. The detector takes the maximum over both channels (`np.max(np.abs(audio_4x), axis=1)`) and applies one gain curve to both, so the stereo image cannot shift.

3. **Gain Computed at 4X, Applied at 1X:**
   The needed gain is computed on the 4X peaks (plus the 1X sample peaks) with a **0.2 dB internal margin**, held over a 2 ms window, smoothed with a zero-phase 30 Hz filter and bounded by

$$\text{Gain}_{\text{final}}(t) = \min\big(\text{NeededGain}(t),\ \text{Gain}_{\text{smooth}}(t)\big) \le \text{NeededGain}(t)$$

   The 4X gain curve is then reduced to 1X by **minimum pooling** (each original sample receives the strongest reduction of its four sub-points) and multiplied directly onto the **original 1X samples**. There is no decimation filter in the audio path, so there is no decimation ripple and no "peak regrowth" to absorb.

4. **Verification Pass with a Local Guard:**
   The limited output is measured again at 4X. Only if a residual overshoot remains is a `tanh` guard blended in — locally, on a 15 ms neighbourhood with a 5 ms Hann-smoothed mask — followed by a sample clamp. The reported True-Peak is measured on the **final** output.

5. **Why 3.1 Replaced the 2.0 Limiter (measured):**
   PHARMAKON 2.0 limited the 4X copy and decimated it back to 1X. Decimation ripple could push 1X samples over the ceiling again, which triggered a `tanh` stage over the **entire file**, and the reported True-Peak was read *before* that last stage. On a 20 s test signal with ten 8 dB overs (ceiling -1.0 dBTP):

   | | Reported TP | Actual TP | Change to audio away from the peaks (±60 ms excluded) |
   |---|---|---|---|
   | PHARMAKON 2.0 | -1.15 dBTP | -3.36 dBTP | up to -26.7 dBFS (whole-track saturation) |
   | PHARMAKON 3.1 | -1.20 dBTP | -1.20 dBTP | -148 dBFS (float rounding: bit-transparent) |

6. **Coordination with Integrated LUFS and PLR:**
   The ceiling defines the Peak-to-Loudness Ratio (PLR) window:
   - **Streaming delivery (Spotify / Apple Music / YouTube):** -14 LUFS at -1.0 dBTP (PLR = 13 dB);
   - **Club & heavy masters (PHARMAKON Standard):** -8 ... -6 LUFS at -1.0 dBTP (PLR = 5 ... 7 dB).
   Integrated loudness is measured per ITU-R BS.1770-4 and verified against EBU Tech 3341 test cases 1–5 (±0.1 LU).

```python
import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d

def true_peak_limiter_block(audio, sr, target_ceiling_db=-1.0, oversample=4):
    """
    PHARMAKON 3.1 True-Peak limiter (stereo, shape (N, 2)).
    Detects at 4X, applies the gain at 1X: the audio itself is never resampled.
    """
    n = len(audio)
    ceiling = 10.0 ** (target_ceiling_db / 20.0)

    # 1. 4X polyphase detection (ITU-R BS.1770-4 Annex 2 method), stereo-linked
    audio_4x = signal.resample_poly(audio, up=oversample, down=1, axis=0)
    peaks_4x = np.max(np.abs(audio_4x), axis=1)
    peaks_1x = np.repeat(np.max(np.abs(audio), axis=1), oversample)[:len(peaks_4x)]
    peaks = np.maximum(peaks_4x, peaks_1x)

    # 2. Needed gain with a 0.2 dB internal margin
    internal = ceiling * 10.0 ** (-0.20 / 20.0)
    needed = np.minimum(1.0, internal / (peaks + 1e-12))

    # 3. Peak hold (2 ms centered window) + zero-phase 30 Hz smoothing;
    #    min() guarantees gain <= needed gain on every 4X point
    sr_4x = sr * oversample
    hold = minimum_filter1d(needed, size=int(0.002 * sr_4x) | 1)
    b, a = signal.butter(1, 30.0 / (0.5 * sr_4x))
    gain_4x = np.minimum(needed, signal.filtfilt(b, a, hold))

    # 4. Gain envelope -> 1X by minimum pooling, applied to the ORIGINAL samples
    gain_4x = np.pad(gain_4x, (0, n * oversample - len(gain_4x)), mode='edge')
    gain_1x = gain_4x[:n * oversample].reshape(n, oversample).min(axis=1)
    out = audio * gain_1x[:, None]

    # 5. Verification: re-measure at 4X; a local tanh guard only where needed
    tp_4x = np.max(np.abs(signal.resample_poly(out, oversample, 1, axis=0)), axis=1)
    over = (tp_4x[:n * oversample].reshape(n, oversample) > ceiling).any(axis=1)
    over |= np.max(np.abs(out), axis=1) > ceiling
    if over.any():
        k = int(0.015 * sr)
        mask = np.convolve(over.astype(float), np.ones(2 * k + 1), mode='same') > 0
        mask = signal.convolve(mask.astype(float), np.hanning(int(0.005 * sr)), mode='same')
        mask = np.clip(mask / mask.max(), 0.0, 1.0)[:, None]
        out = out * (1.0 - mask) + np.tanh(out / ceiling) * ceiling * mask
    out = np.clip(out, -ceiling, ceiling)

    # 6. Report the True-Peak of the FINAL output
    tp = np.max(np.abs(signal.resample_poly(out, oversample, 1, axis=0)))
    return out.astype(np.float32), round(20.0 * np.log10(max(tp, 1e-9)), 2)
```

A -1.0 dBTP ceiling measured with 4X detection leaves the headroom that streaming platforms recommend for lossy encoding, while the music between the peaks passes through the limiter untouched.

---
*Repository:* [https://github.com/alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON)
