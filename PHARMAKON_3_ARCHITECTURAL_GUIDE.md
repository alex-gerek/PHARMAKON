# PHARMAKON 3.0 Architectural Blueprint
## Limiter-Aware Transient-Guarded Sub-Sync, Track Intelligence Map & True-Peak Guard
### Engineering Whitepaper & Knowledge Base // Created by Lex Gerek (2026)

---

## 1. Executive Summary & The Evolution from v2.0 to v3.0

**PHARMAKON 2.0** established the studio baseline for treating synthetic AI audio:
- Dedicated **5.2 kHz resonance ducking** (AI whistle cure),
- **Harmonic Air Exciter** (>16 kHz silk resynthesis),
- **4x polyphase asymmetric tape saturation** (analog warmth), and
- Verified **24-bit PCM_24** lossless export.

However, deep-dive acoustic experiments across multi-stem AI audio revealed a critical vulnerability in traditional low-end treatment: **static global phase alignment often creates destructive trade-offs**. When a fixed time-shift is applied uniformly across an entire track, some kick events align with the bass while others clash, resulting in **True-Peak overshoot**, transient smearing, and inter-sample clipping on downstream limiters.

**PHARMAKON 3.0** fundamentally resolves this challenge through **micro-transient intelligence**:
1. **Limiter-Aware Transient-Guarded Sub-Sync (Local Guard)**: Operates at the individual kick onset level, evaluating phase coherence against a **Virtual Micro-Limiter Cost Function**.
2. **True-Peak Limiter Guard**: 4x polyphase oversampling ceiling (-0.3 dBFS) ensuring 100% broadcast compliance (EBU R128 / ITU-R BS.1770-5).
3. **PHARMAKON Track Intelligence Map**: 9-sector automated structural composition map with interactive section inspection and intra-section kick onset tracking.
4. **Preservation of v2.0**: The proven PHARMAKON 2.0 processing core remains fully intact, with v3.0 serving as an advanced intelligence layer.

### 1.1 Legacy PHARMAKON 2.0: Permanent Availability & Frozen Archive Policy
We recognize that many producers and sound engineers formed their sonic workflows around the specific analog character, saturation curve, and coloration of **PHARMAKON 2.0**.
- **Permanent Access**: The complete, self-contained **PHARMAKON v2.0.3 package remains permanently hosted and downloadable** in our releases archive.
- **Frozen Archive Status**: Version 2.0 is now officially closed to active development. **It will receive no further patches, DSP revisions, or feature updates.**
- **The Path Forward**: All subsequent research, multi-genre calibrations (Drum & Bass, Hip-Hop, Rock, Pop), dynamic limiter refinements, and architectural enhancements will be deployed exclusively on the PHARMAKON 3.0+ engine.

---

## 2. Limiter-Aware Sub-Sync: Mathematical Foundations

### 2.1 The Problem with Naive Phase Alignment
Generative stems (e.g. Drums and Bass separated via neural models) frequently exhibit micro-timing drift. If a naive cross-correlation algorithm applies a constant $+3.2\text{ ms}$ or $-4.5\text{ ms}$ delay across the entire bass track:
- In sparse sections (Intro, Interlude, Breakdown), bass fundamentals shift unnecessarily.
- In dense drops, constructive interference at certain frequencies causes instantaneous voltage spikes that trigger heavy digital limiting, squashing the punch of the kick drum.

### 2.2 Local Guard Architecture
In PHARMAKON 3.0, the Sub-Sync engine executes a 3-tier local pipeline:
1. **Percussive Event Detection**:
   Using sub-band spectral flux and low-frequency energy novelty ($<120\text{ Hz}$), every individual kick onset $t_k$ is identified with millisecond precision (e.g., 134 discrete events on our *Vector Pulse* benchmark).
2. **Local Bounded Correlation Window**:
   For each event $t_k$, an adaptive temporal window ($[-40\text{ ms}, +80\text{ ms}]$) is extracted from both drum and bass stems. Local cross-correlation $R_{db}(\tau)$ determines the candidate micro-shift $\tau^*$.
3. **Virtual Micro-Limiter Cost Function**:
   Before committing to any shift $\tau^*$, the algorithm simulates the resulting local waveform:
   $$\mathcal{L}(\tau) = \alpha \cdot (1 - r_{\text{sub}}(\tau)) + \beta \cdot \max(0, \text{Peak}(\tau) - \text{Peak}_0) + \gamma \cdot \text{ISP}(\tau)$$
   - If $\tau^*$ improves sub-correlation without increasing True-Peak or destroying transient punch, it is **ACCEPTED** and applied via windowed raised-cosine crossfades.
   - If $\tau^*$ would cause transient distortion or severe peak headroom loss, the engine executes an **Autonomous Acoustic Safe-Bypass** ($0\text{ ms}$ shift), guaranteeing absolute acoustic transparency.

---

## 3. Real-Time 4x Oversampling True-Peak Limiter Guard

Post-reconstruction inter-sample peaks (ISPs) are the primary cause of distortion when tracks are transcoded by streaming platforms (Spotify Vorbis/AAC, Apple Music AAC, YouTube Opus).

PHARMAKON 3.0 integrates a dedicated **True-Peak Limiter Guard**:
- **4x Polyphase Oversampling**: Signal is upsampled via high-order Kaiser-windowed sinc filters to expose inter-sample peaks.
- **Lookahead Gain Reduction**: A smooth 3-stage gain envelope (1.5 ms lookahead, fast attack, program-dependent release) clamps voltage excursions.
- **Streaming Ceiling**: Hard-capped at **-0.3 dBFS True-Peak**, preventing any DAC clipping during playback.

---

## 4. Track Intelligence Map (9-Sector Macro Segmentation)

To master music intelligently, processing must adapt to song structure. PHARMAKON 3.0 automatically parses the audio into 9 musical sectors:

| Sector | Musical Role | Typical Dynamic Crest | Mastering Policy |
|:---|:---|:---:|:---|
| **01. INTRO** | Atmospheric opening | 11.0 – 13.0 dB | True-Peak guard protected |
| **02. DROP** | Primary rhythmic impact | 9.5 – 10.5 dB | Sub-bass headroom preserved |
| **03. DEVELOPMENT** | Energy expansion | 10.0 – 10.5 dB | Sub-bass headroom preserved |
| **04. DENSE MIDDLE** | Maximum spectral density | 10.0 – 10.5 dB | Phase optimal (0-lag reference) |
| **05. INTERLUDE** | Harmonic transition | 10.0 – 10.5 dB | Phase optimal (0-lag reference) |
| **06. BREAKDOWN** | Percussion drop-out / vocal space | 14.0 – 15.0 dB | Acoustic transparency (safe path) |
| **07. BUILDUP** | Tension crescendo | 10.5 – 11.0 dB | Phase optimal (0-lag reference) |
| **08. CLIMAX / DROP** | Climax groove | 8.5 – 9.5 dB | Phase optimal (0-lag reference) |
| **09. OUTRO** | Energy resolution | 11.0 – 12.0 dB | Phase optimal (0-lag reference) |

### Interactive Section Inspector:
Clicking any card in the GUI opens the high-resolution inspector showing:
- Dynamic Crest, Peak / RMS levels, Sub-bass energy (<100 Hz),
- Active phase-lock statistics and sub-correlation $r$,
- An intra-section kick onset map displaying the precise timing and decision for every percussive transient.

---

## 5. Subjective Psychoacoustic Listening Impressions

Across critical studio monitoring (Genelec 8351B / Neumann KH 120 + KH 750 DSP Sub):
1. **3D Depth & Stereo Panorama**: The acoustic stage expands naturally. Mono-locked sub-bass anchors the center, allowing stereophonic synths, vocals, and cymbals to spread wider without phase smear.
2. **Low-End Articulation**: Kick drums gain punch and tactile chest impact. The "one-note muddy drone" characteristic of generative AI tracks is replaced by discrete, articulate basslines.
3. **Instrumental Clarity**: Vocal formants and acoustic guitar / synth plucks remain bright, silk-like, and clearly separated without inducing ear fatigue.

---

## 6. Engineering Transparency & Multi-Genre Research Roadmap

### 6.1 Honest Engineering Assessment
PHARMAKON 3.0 represents a major evolutionary leap, but we adhere to strict engineering honesty:
- **Current Mathematical Tuning**: The algorithm is currently optimized and rigorously audited on high-density club music (**Techno / Peak-Energy EDM** benchmarked on *Vector Pulse*).
- **Ongoing Calibration**: On tracks with complex polyrhythms or dynamic rubato tempo (jazz, acoustic classical, indie folk), manual audit remains recommended.
- **Continuous Research**: We are actively gathering multi-genre datasets to expand automatic parameter heuristics.

### 6.2 Next Development Phases
1. **Genre Profiles Extension**: Implementing dedicated DSP heuristics for:
   - *Drum & Bass / Jungle* (fast 174 BPM transients),
   - *Hip-Hop / Trap* (heavy 808 sub pitch-slides),
   - *Rock & Metal* (distorted bass guitars and rapid double-kick drums),
   - *Synthwave & Ambient Pop* (dense analog synth textures).
2. **Dynamic Processing Curves**: Linking Sector Intelligence directly to compressor and exciter thresholds, enabling automated macro-dynamics.
3. **Multi-Platform Native Binaries**: Expanding portable standalone packages across macOS (Apple Silicon / Intel) and Linux.

---
*PHARMAKON is an open-source studio audio research project by Lex Gerek under the MIT License.*
