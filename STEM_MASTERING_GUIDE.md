# The Definitive Guide to Stem Mastering AI Music
## From Suno & Udio Stems to Commercial Studio Masters

**Architect:** Lex Gerek | Lazuli Pictures  
**Software:** PHARMAKON 2.0 Open-Source Studio Console  
**License:** MIT License // Free & Open Source  

---

## 1. Why 2-Track Mastering Fails on AI Audio

Generative AI music engines (such as Suno v3.5/v4 and Udio 1.5/Hi-Fi) generate incredible musical ideas, but their raw 2-track stereo renders suffer from fundamental physics limitations of neural audio synthesis:

1. **Phase Mud in the Low-End:** Sub-bass synthesizers and acoustic kicks are generated with uncorrelated stereo spread below 100 Hz, causing massive phase cancellation on club subwoofers and car audio systems.
2. **Spectral Masking:** Vocals, distorted electric guitars, and synth leads all compete for energy between 2.5 kHz and 6 kHz. In a baked stereo mix, cutting 5.2 kHz to remove AI sibilance dulls the entire song.
3. **Transient Squashing:** Neural diffusion vocoders compress dynamic range, smoothing out the natural impact and punch of drum hits.

**The Solution is Stem Mastering:**  
By separating the track into **4 isolated stems (Drums, Bass, Vocals, Other/Instruments)**, each element can undergo surgical restoration before being summed back into a pristine, broadcast-ready master bus.

---

```
                       [ RAW NEURAL AUDIO TARGET ]
                                    │
                                    ▼
                     [ 4-STEM SPECTRAL SEPARATION ]
                                    │
         ┌──────────────┬───────────┴───────────┬──────────────┐
         ▼              ▼                       ▼              ▼
     [ DRUMS ]       [ BASS ]              [ VOCALS ]       [ OTHER ]
         │              │                       │              │
    • Transient    • LR4 110Hz Mono        • 5.2 kHz Dynamic • Mid-Side 3D
      Punch Shaper   Anchor (< 120Hz)        Resonance Ducker  Width Spread
    • 32Hz Sub Cut • Phase Solidification  • Sibilant Tamer  • Studer Tape Glue
         │              │                       │              │
         └──────────────┴───────────┬───────────┴──────────────┘
                                    │
                                    ▼
                         [ MASTER STEREO SUMMING ]
                                    │
                         • Studer A800 Tape Warmth
                         • Polynomial Silk Exciter (>15.5 kHz)
                         • 4X Oversampled True-Peak Limiter (-0.3 dBFS)
                                    │
                                    ▼
                       [ BROADCAST STUDIO MASTER ]
```

---

## 2. The 4-Stage Stem Surgery Workflow

### Stage 1: Drum Stem // Restoring Transient Punch & Attack
- **The Problem:** Neural audio softens the attack edge of snare hits and kick transients.
- **The Treatment:**
  - Apply the **Transient Punch Shaper** to accentuate the initial 5–10 ms envelope.
  - High-pass drums below 32 Hz with a 4th-order Butterworth filter to eliminate sub-surface speaker cone wobble.
  - Keep the kick strictly mono in the center of the soundstage.

### Stage 2: Bass Stem // Sub-Bass Solidification (< 120 Hz)
- **The Problem:** Neural stereo bass has random phase offset between Left and Right, causing weak mono playback.
- **The Treatment:**
  - Apply a **4th-order Linkwitz-Riley (LR4) Crossover at 110–120 Hz**.
  - Sum everything below 120 Hz to 100% True-Mono ($M = 0.5 \cdot (L + R), S = 0$).
  - Measure phase correlation: ensure low-end correlation rises from $+0.38$ to $> +0.95$.

### Stage 3: Vocal Stem // Surgical De-Harshing without Dulling
- **The Problem:** Neural vocoders leave a piercing metallic whistle between 5.0 kHz and 5.5 kHz that hurts human ears at high volume.
- **The Treatment:**
  - Engage **Dynamic Resonant Ducker** targeting the detected resonance peak (typically 5200 Hz, $Q = 2.8 - 3.2$).
  - Because surgery is applied only to the vocal stem, instruments retain their natural presence and clarity.
  - Audit the **Delta Monitor ($\Delta$)** to verify that only isolated noise is cut, leaving vocal chest body intact.

### Stage 4: Other / Synths / Guitars // 3D Mid-Side Air Spread
- **The Problem:** AI instruments often sound clustered in the center or exhibit narrow stereo imaging.
- **The Treatment:**
  - Apply Mid-Side high-frequency expansion ($+1.5\text{ dB}$ on Side channels above 1 kHz).
  - Add Studer A800 asymmetric tape saturation ($\text{drive} = 1.05$) to glue synthetic synths with analog warmth.

---

## 3. Master Bus Polish & Streaming Compliance

Once all 4 stems are surgically treated, they are summed into the PHARMAKON Master Bus:

1. **Analog Tape Density:** Inject even 2nd harmonics at $-38.05\text{ dBc}$ via 4X oversampled global-asymptote scaled $\tanh$ saturation and a $10\text{ Hz}$ DC-blocker to remove digital coldness.
2. **Silk Exciter (> 15.5 kHz):** Synthesize high-frequency air harmonics lost during 44.1 kHz neural model sampling.
3. **4X Oversampled True-Peak Limiter:**
   - Ceiling: $-0.3\text{ dBFS}$ (Spotify / Apple Music / YouTube compliant).
   - Zero Inter-Sample Peaks (ISP): guarantees clean reproduction after AAC/MP3 lossy encoding.
   - Target Loudness: $-14.0\text{ LUFS}$ (streaming standard) to $-11.5\text{ LUFS}$ (club/electronic density).

---

## 4. How to Execute in PHARMAKON 2.0 (Step-by-Step)

1. **Launch Studio Console:** Run `Start_Pharmakon.bat` or open `http://127.0.0.1:7860`.
2. **Load Target Audio:** Drag and drop your raw WAV/MP3 file into the upload zone.
3. **Click `🧬 SPLIT & STEM MASTER`:**
   - The engine automatically extracts Drums, Bass, Vocals, and Instruments via Wiener HPSS decomposition.
   - Applies frequency-specific restorative DSP to each stem in memory.
   - Sums and masters through the analog warmth and 4x True-Peak limiter chain.
4. **Inspect Spectral Diagnosis Certificate:**
   - Verify that Sub-Bass Phase Correlation reads $> +0.95$.
   - Confirm that the amber **Delta Residue ($\Delta$)** curve shows the eliminated 5.2 kHz resonance hump.
   - Check Dynamic Crest Factor ($> 10.0\text{ dB}$) confirming healthy punch.
5. **Export:** Click `📦 DOWNLOAD STEMS (.ZIP)` for the isolated 24-bit `PCM_24` stems or `⬇ DOWNLOAD MASTER (.WAV)` for the header-verified 24-bit `PCM_24` studio master.

---

## 5. Technical Specifications Reference

| Target Platform | Target Integrated LUFS | True-Peak Ceiling | Sub-Bass Crossover | Phase Correlation |
|---|:---:|:---:|:---:|:---:|
| **Spotify / Apple Music** | $-14.0\text{ LUFS}$ | $-0.3\text{ dBFS}$ | $110 - 120\text{ Hz}$ | $> +0.90$ |
| **Club / DJ / EDM** | $-11.5\text{ LUFS}$ | $-0.1\text{ dBFS}$ | $130 - 140\text{ Hz}$ | $> +0.98$ |
| **Audiophile / Acoustic** | $-16.0\text{ LUFS}$ | $-0.5\text{ dBFS}$ | $95\text{ Hz}$ | $> +0.95$ |
| **YouTube Music** | $-14.0\text{ LUFS}$ | $-0.3\text{ dBFS}$ | $115\text{ Hz}$ | $> +0.92$ |
