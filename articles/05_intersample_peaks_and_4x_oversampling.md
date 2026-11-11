# The Peak Your Meter Never Shows: Inter-Sample Overs, Lossy Codecs and a Limiter That Leaves the Music Alone

**Author:** Lex Gerek (Sound Architect / Engineer)  
**Project:** PHARMAKON 3.2 Studio Console  
**Implementation:** `remaster_engine.py` (`_true_peak_limiter_block`, `target_ceiling_db`), codec bench `bench/validate_codec_true_peak.py`

You bounce a master and the peak meter says −0.1 dBFS. No red lights. Then the track goes to a streaming service, gets converted to a lossy format, and plays through a chain of digital stages you don't control. Somewhere along that chain the waveform can go higher than anything your meter showed.

This article explains why that happens and measures how much headroom it actually takes. It also shows how PHARMAKON catches these peaks without touching the music between them.

---

### 1. Samples are not the waveform

Digital audio stores samples, not the curve between them. Playback rebuilds the continuous signal from those samples. In the ideal case, described by the Whittaker–Kotelnikov–Shannon sampling theorem, each sample contributes one sinc pulse:

```math
s(t) = \sum_{n=-\infty}^{+\infty} x[n]\,\mathrm{sinc}\!\left(\frac{t - nT_s}{T_s}\right), \qquad \mathrm{sinc}(u) = \frac{\sin(\pi u)}{\pi u}
```

The rebuilt curve passes through every sample, but between samples it can rise higher than any of them. A sample peak meter reads only $x[n]$, so it cannot see that rise. The peak of the rebuilt curve is called the **true peak**, and the part above the highest sample is an **inter-sample peak**.

The clearest example is a sine at a quarter of the sample rate (12 kHz at 48 kHz), shifted by 45°. Every sample lands at 0.707 of the real amplitude:

| | Level |
|---|---|
| Highest sample | −3.01 dBFS |
| True peak of the rebuilt curve | 0.00 dBFS |

That is a 3 dB over that a sample meter never shows. For contrived signals the gap can be even larger. In real music it depends on how hard the master was pushed: heavy limiting and clipping create the sharp, dense shapes where inter-sample peaks grow.

We checked how the raw files look before anyone masters them. On 6 AI-generated tracks in different styles, straight from the generator, the sample peak and the true peak differed by no more than 0.01 dB. The peaks sat 2.8 to 4.4 dB below full scale, at −13 to −15 LUFS. Raw generated files have room. Inter-sample overs appear when the track is made loud.

---

### 2. Where an over turns into distortion

An over by itself is just a number. It becomes audible distortion when a digital stage in the playback chain has no room above full scale and clips it. Typical candidates:

- **A decoder that writes fixed-point output.** A lossy file decodes to a waveform that can exceed 0 dBFS; written to 16- or 24-bit integers, the excess is cut off.
- **Sample-rate converters and the oversampling filter inside a DAC chip.** They compute the very inter-sample values a sample meter ignores. In fixed-point arithmetic, values above full scale overflow or clip.

Whether a particular phone, browser or Bluetooth headset clips depends on its implementation. We did not measure devices. What we can measure is how far the peaks travel before they reach the device.

---

### 3. Lossy codecs move the peaks

A lossy encoder does not store the waveform. It stores a frequency-domain approximation, drops what it considers inaudible, and the decoder rebuilds a slightly different waveform. Different waveform, different peaks, and they usually grow.

We measured this on the same 6 tracks:

- For each track we took 60 seconds around its loudest moment and mastered it to −14 and to −8 LUFS.
- PHARMAKON's limiter set the ceiling to −0.3, −1.0 or −2.0 dBTP.
- Each master was written as 24-bit WAV, then encoded and decoded through five formats with ffmpeg: MP3 320 and 128 kbps, AAC 256, Vorbis 160 and Opus 128. ffmpeg is used here only as a measuring instrument, not inside PHARMAKON.
- We then measured the decoded true peak.

**At −14 LUFS** none of the six masters needed limiting: their peaks stayed between −2.9 and −6.2 dBTP whatever ceiling was set. The codecs added up to +1.0 dB, and the loudest decoded peak was still −2.8 dBTP. At this loudness, for this material, the ceiling simply never came into play.

**At −8 LUFS**, a typical loud club master, the limiter was working on every track. Peak growth through the codec, decoded true peak minus master true peak:

| Codec | Median growth | Worst growth |
|---|---|---|
| MP3 320 kbps | +0.3 dB | +0.7 dB |
| AAC 256 kbps | +0.3 dB | +0.8 dB |
| MP3 128 kbps | +1.1 dB | +1.5 dB |
| Vorbis 160 kbps | +1.1 dB | +1.6 dB |
| Opus 128 kbps | +1.1 dB | +1.8 dB |

High bitrates move the peaks by a few tenths of a dB. The lower bitrates used for free tiers, mobile data and video add a full decibel or more.

What that means for the ceiling, counting the tracks whose decoded file had samples above 0 dBFS:

| Ceiling at −8 LUFS | MP3 128 | Vorbis 160 | Opus 128 | MP3 320 / AAC 256 |
|---|---|---|---|---|
| −0.3 dBTP | 6 of 6 | 6 of 6 | 6 of 6 | 0 / 1 of 6 |
| −1.0 dBTP | 2 of 6 | 4 of 6 | 4 of 6 | 0 of 6 |
| −2.0 dBTP | 0 of 6 | 0 of 6 | 0 of 6 | 0 of 6 |

A −1.0 dBTP ceiling is enough for high-bitrate formats, but not for a loud master in a low-bitrate format. At −2.0 dBTP no decoded file went above full scale in any format. The price is real but small: with the same input gain, the −2.0 masters came out 0.1 to 0.7 LU quieter than the −0.3 ones.

---

### 4. What the delivery specifications ask for

The measurements line up with what the platforms and broadcasters publish:

- **Spotify** recommends keeping masters below −1.0 dBTP, and below −2.0 dBTP for masters louder than −14 LUFS integrated.
- **Apple Digital Masters** recommends not exceeding −1.0 dBTP.
- **EBU R128** sets a maximum true peak of −1.0 dBTP for broadcast.
- **ITU-R BS.1770-4** defines how true peak and loudness are measured. It does not set a ceiling.

A −0.3 dBTP ceiling is a common habit for lossless delivery, such as WAV and FLAC for archives, vinyl pre-mastering or further processing. No standard requires it. It makes sense only when the file will not be lossy-encoded afterwards.

---

### 5. How PHARMAKON limits: detect at 4X, apply at 1X

PHARMAKON's true-peak limiter follows one principle: **oversample to see the peaks, never resample the music itself.**

1. **4X detection.** The signal is upsampled 4× with a polyphase filter (`signal.resample_poly`), giving three interpolated points between every pair of samples, the oversampling method of ITU-R BS.1770-4 Annex 2. This copy is used only to measure. It never reaches the output.
2. **Stereo-linked gain.** The detector takes the larger of the two channels at every point and applies one gain curve to both, so a hard-panned hit cannot pull the phantom centre (vocal, kick, bass) to one side.
3. **Gain computed at 4X, applied at 1X.** The needed gain is computed from the 4X peaks (and the 1X sample peaks) with a 0.2 dB internal margin, held over 2 ms and smoothed with a zero-phase 30 Hz filter. It is never allowed to rise above the needed gain:

```math
g_{\mathrm{final}}(t) = \min\bigl(g_{\mathrm{needed}}(t),\ g_{\mathrm{smooth}}(t)\bigr) \le g_{\mathrm{needed}}(t)
```

   The 4X gain curve is reduced to 1X by **minimum pooling**: each original sample gets the strongest reduction among its four sub-points. That gain multiplies the **original** samples. There is no decimation filter in the audio path, so no decimation ripple can push samples back over.
4. **Precise pass at 16X.** The output is measured again, this time at 16X, sixteen points per sample. A 4X check can read a peak up to 0.69 dB low when the energy sits close to the Nyquist frequency; at 16X the worst case is 0.04 dB, and the pass checks against exactly that bound. Where an over remains, it is removed the same way as in step 3, with smooth gain, and the check repeats until nothing is left. To keep it fast, the 16X measurement runs only where the 4X reading is within 0.75 dB of the ceiling, the only places an over can hide.
5. **Last-resort guard.** If anything were still over, a local `tanh` guard would blend in over a 15 ms neighbourhood, followed by a sample clamp. The reported true peak is measured on the final output.

**Why we added the precise pass.** Before it, step 5 was the only correction after the first gain stage, and our re-check at 32X showed what that cost:

- **The guard was firing on real music.** On 6 tracks mastered to −8 LUFS at three ceilings, the `tanh` guard fired in 17 of 18 masters. Where it fired, it squashed up to 15 ms of audio by about 2 dB. That is saturation, exactly what a transparent limiter should never add.
- **The clamp created new peaks.** The final sample clamp itself made new inter-sample peaks. Full-track masters ended up to 0.02 dB over the ceiling. White noise that fills the band to 24 kHz, a stress signal no music resembles, ended 0.3 dB over.

With the precise pass, at 32X:

| | Before | With the precise pass |
|---|---|---|
| 18 full-track masters at −8 LUFS | up to +0.02 dB over the ceiling | 0.04 dB under the ceiling, all 18 |
| `tanh` guard firing on those masters | 17 of 18 | 0 of 18 |
| White noise to 24 kHz | +0.3 dB over | 0.03 dB under the ceiling |
| Noise to 16 kHz | +0.1 dB over | 0.03 dB under the ceiling |

On a 97-second master, 99% of samples changed by less than 0.012 dB. The price is time: the limiter stage takes 1.3 to 2.3 times longer. Material that never comes near the ceiling comes out bit-identical to before. The Classic 3.1 sound profile keeps the 3.1 limiter bit-for-bit.

**Why it replaced the 2.0 limiter.** PHARMAKON 2.0 limited the 4X copy and decimated it back. Decimation ripple could push samples over the ceiling again, which triggered `tanh` saturation over the **entire file**, and the reported true peak was read before that last stage. Test: 20 s of noise with ten 8 dB overs, ceiling −1.0 dBTP:

| | Reported true peak | Actual true peak | Change to the audio away from the peaks (±60 ms excluded) |
|---|---|---|---|
| PHARMAKON 2.0 | −1.15 dBTP | −3.36 dBTP | up to −26.7 dBFS (whole-file saturation) |
| PHARMAKON 3.1 | −1.20 dBTP | −1.20 dBTP | −148 dBFS (float rounding: bit-transparent) |

Steps 1 to 3 and 5 have not changed since 3.1; the precise pass is new in the Clean Chain. Version 3.2 also corrected the loudness meter the limiter works with: K-weighting now matches ITU-R BS.1770-4 exactly and passes EBU Tech 3341 test cases 1–5 (±0.1 LU).

The listing below shows the base limiter, steps 1 to 3 and the guard; the precise pass lives in `_precise_gain_pass` in `remaster_engine.py`.

```python
import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d

def true_peak_limiter_block(audio, sr, target_ceiling_db=-1.0, oversample=4):
    """
    PHARMAKON base true-peak limiter (3.1, Classic profile; stereo, shape (N, 2)).
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

    # 6. Report the true peak of the FINAL output
    tp = np.max(np.abs(signal.resample_poly(out, oversample, 1, axis=0)))
    return out.astype(np.float32), round(20.0 * np.log10(max(tp, 1e-9)), 2)
```

---

### 6. Choosing the ceiling in PHARMAKON

The ceiling is a setting, and the right value depends on where the file goes next:

| Destination | Ceiling |
|---|---|
| Lossless master (WAV/FLAC) that will not be lossy-encoded | −0.3 dBTP, the PHARMAKON default |
| Streaming and broadcast at −14 LUFS or quieter | −1.0 dBTP |
| Streaming for masters louder than −14 LUFS (club, heavy genres) | −2.0 dBTP |

The default is −0.3 dBTP, and the Club preset goes to −0.1 dBTP. Both are lossless-delivery values. For a loud master headed to streaming, set the ceiling to −2.0 dBTP: in our measurements that was the level at which no format went over full scale. Making this choice automatic from the delivery target is on our list. Until then it is one setting in the console.

---

### 7. A last word

The numbers in this article are measurements: six generated tracks, two loudness levels, three ceilings, five formats. They come from ffmpeg's encoders, not from the exact encoders and players each platform uses, so treat them as a measured guide rather than a guarantee for every device. The judgement is mine: a master should carry its headroom with it, and the music between the peaks should come out exactly as it went in.

---
*Repository:* [https://github.com/alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON)  
*Codec measurement:* `bench/validate_codec_true_peak.py`, results in `bench/results/codec_true_peak.json`
