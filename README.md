<p align="center">
  <img src="gui/static/studio_icon.png" width="130" height="130" alt="PHARMAKON Logo">
</p>

# PHARMAKON 2.0 PRO
## Studio-Grade Audio Antidote, AI De-Harshing & True-Peak Mastering Console
### Created by Lex Gerek // Abbey Road 1974 × Blade Runner 2049

<p align="center">
  <a href="https://github.com/alex-gerek/PHARMAKON/releases/download/v2.0/PHARMAKON_v2.0_Windows_Portable.zip">
    <img src="https://img.shields.io/badge/Download%20Windows%20Portable%20(.exe)-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Download Windows Portable">
  </a>
  &nbsp;
  <a href="https://youtu.be/GyJ8nCmqhMc" target="_blank">
    <img src="https://img.shields.io/badge/Watch%20Studio%20Walkthrough-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="Watch Studio Walkthrough">
  </a>
  &nbsp;
  <a href="https://github.com/alex-gerek/PHARMAKON/archive/refs/heads/master.zip">
    <img src="https://img.shields.io/badge/Source%20Code%20ZIP-238636?style=for-the-badge&logo=github&logoColor=white" alt="Download Source Code ZIP">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0%20PRO-emerald.svg?style=flat-square&color=10b981" alt="Version 2.0 PRO">
  <img src="https://img.shields.io/badge/DSP-Dynamic%20Ducker%20%2B%20Exciter-blue.svg?style=flat-square" alt="DSP Core">
  <img src="https://img.shields.io/badge/Oscilloscope-60%20FPS%20CRT%20%2B%20Phase%20Scope-brightgreen.svg?style=flat-square" alt="CRT Scope">
  <img src="https://img.shields.io/badge/True--Peak%20Limiter-4x%20Oversampling-f59e0b.svg?style=flat-square" alt="True Peak">
  <img src="https://img.shields.io/badge/Monitoring-A%20%2F%20B%20%2F%20Delta-purple.svg?style=flat-square" alt="Monitoring">
  <img src="https://img.shields.io/badge/Loudness-ITU--R%20BS.1770--4%20LUFS-cyan.svg?style=flat-square" alt="LUFS">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078d7?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/Author-Lex%20Gerek-black.svg?style=flat-square&logo=youtube" alt="Lex Gerek">
  <img src="https://img.shields.io/badge/License-MIT-orange.svg?style=flat-square" alt="License">
</p>

---

## 1. Why PHARMAKON: The Anatomy of "AI Poison"

> 📺 **Official Studio Walkthrough (A/B & Delta Tests):**  
> [**Watch on YouTube: Treating Generative Audio: Pure Mathematical DSP | PHARMAKON 2.0**](https://youtu.be/GyJ8nCmqhMc)

> **Pharmakon** *(Ancient Greek: φάρμακον)* — an ancient philosophical paradox denoting simultaneously **poison**, **remedy**, and **antidote**.

Generative audio models (**Suno v3/v3.5/v4**, **Udio 1.5**, Stable Audio) have revolutionized music creation. Yet producers, composers, and audio engineers face an inescapable reality: **raw AI audio suffers from severe systemic sonic defects**.

### Common AI Audio Pathologies:
1. **Metallic AI Harshness (4.5–7 kHz):**  
   Neural vocoders generate artificial resonant spikes on vocal sibilants ("s", "sh"), cymbals, and upper mids. This synthetic harshness causes immediate listener ear fatigue ("glass sand").
2. **High-Frequency Spectral Cutoff (>15.5 kHz):**  
   Most generative models operate with compressed bandwidth (cutoff above 15–16 kHz). Static high-shelf equalizers fail because there is **no acoustic information above the brickwall** - boosting merely amplifies quantization hiss.
3. **Phase-Smudged Sub-Bass (Sub Mud):**  
   Low frequencies (20–120 Hz) are often rendered out-of-phase across the stereo panorama. On mono systems (smartphones, club subwoofers), the kick and bass experience devastating phase cancellation.
4. **Transient Smearing & Kick-Bass Phase Clashes:**  
   Drum attacks lose punch, and low-end waveforms cancel each other out when overlaid without phase alignment.
5. **Inter-Sample Peak (ISP) True-Peak Clipping:**  
   AI services normalize audio directly to 0 dBFS. During digital-to-analog conversion (DAC) and lossy streaming transcoding (Spotify, Apple Music, YouTube), severe inter-sample overshoots (+1.5 dBFS or higher) destroy fidelity.

**PHARMAKON 2.0 PRO is a dedicated analog-digital resuscitation console.**  
Fusing **Abbey Road 1974** analog tape warmth with **Blade Runner 2049** telemetry, it surgically extracts digital venom, resynthesizes lost acoustic silk, and bonds the master using pure mathematical DSP.

---

## 2. DSP Core Innovations

### 🔬 1. Auto Spectral Antidote (Resonance Peak Detection)
Performs Welch Power Spectral Density FFT analysis and algorithmically isolates resonant whistling peaks via `scipy.signal.find_peaks` (e.g. 5307.9 Hz at +9.1 dB excess), automatically tuning notch center frequency and Q-factor.

### ⚡ 2. Dynamic De-Harshing Ducker (Anti-AI)
Unlike crude static EQ cuts that dull the entire performance, **PHARMAKON uses an envelope-following dynamic ducker** (5ms attack, 45ms release). It ducks the harsh band only in the precise milliseconds when resonant energy exceeds psychoacoustic comfort.

### 💨 3. Harmonic Air Exciter (>16 kHz Silk Synthesizer)
An authentic harmonic synthesizer that extracts program material from the 8–13 kHz donor band, creates polyphonic even and odd harmonics via asymmetric non-linear saturation, high-passes above 15.5 kHz, and injects pure silky air (16–22 kHz) into the mix.

### 🎯 4. Low-End Phase Alignment (Sub Sync for Stems)
When mastering stems (Drums + Bass + Vocals + Other), cross-correlation in the 30–100 Hz band calculates microsecond time-alignment, guaranteeing that kick transients and bass waveforms strike in perfect phase coherence.

### 🛡 5. 4x Polyphase True-Peak Limiter & OOM Streaming Chunking
A 4x polyphase oversampled lookahead limiter (`scipy.signal.resample_poly`) enforces an AES/EBU compliant **-1.0 dBFS True-Peak ceiling** with zero inter-sample clipping. Streaming chunking with raised-cosine crossfading prevents memory exhaustion (OOM) on long tracks and DJ sets.

### 📊 6. ITU-R BS.1770-4 / EBU R128 Loudness Metering
True integrated LUFS calculation featuring dual-stage K-weighting filtering and gated energy integration (-70 LKFS absolute / -10 dB relative gate).

---

## 3. Monitoring Bay: A / B / Δ (Delta Residue)

Three click-free, phase-aligned auditioning modes:

| Button | Key | Mode | Function |
|---|:---:|---|---|
| **[A] RAW** | `A` | Untreated Track | Original AI file with harsh digital sibilance and ISP clipping (Ruby CRT beam). |
| **[B] MASTER** | `B` | PHARMAKON Master | Full analog-modeled master: cohesive sub-bass, warm tape glue, silky air (Emerald CRT beam). |
| **[Δ] DELTA** | `D` | Subtraction Bay | **Audition exclusively the extracted AI poison** ($\text{Raw} - \text{Master}$ with phase inversion and $+6\text{ dB}$ boost). |

> **Pro Mastering Tip:**  
> Switch to **`[Δ] DELTA`** during playback. If you hear only the metallic whistle, harsh clicks, and muddy rumble - with no vocal fundamentals or harmonic body leaking through - **your master calibration is acoustically transparent**!

---

## 4. Visualizers & CRT Oscilloscopes

- **⚡ DUAL BEAMS (Key `1`):** Twin 60 FPS P1 green phosphor CRT oscilloscopes displaying RAW and MASTER simultaneously.
- **📺 SINGLE SCOPE (Key `2`):** Focused single-channel cathode-ray tube view.
- **📊 RTA SPECTRUM (Key `3`):** Real-time spectrum analyzer with 20 Hz – 20 kHz log grid and dB calibration.
- **🎯 DSP CURVES (Key `4`):** Interactive frequency response curves of dynamic filters and exciter.
- **🌊 WAVEFORM (Key `5`):** Full overview waveform with timeline scrubbers.
- **🧭 PHASE SCOPE (Key `6`):** **Lissajous Vector Goniometer** ($X = \text{Side}$, $Y = -\text{Mid}$) with 45° radar reticle and phase correlation meter ranging from **-1.0 (out of phase)** to **+1.0 (mono coherent)**.

---

## 5. Surgical Punch-In Caliper

Repair isolated defects (such as a screeched AI vocal note at 0:45) without altering the rest of your song:
1. Drag calipers directly on the waveform to select the damaged segment.
2. Adjust `IN` and `OUT` points (or click `+3s`, `+5s`).
3. Render applies a seamless **35ms raised-cosine equal-power crossfade**.
4. **100% of the audio outside the calipers remains byte-for-byte untouched!**

---

## 6. Studio AI Presets

| Profile | Description | Factory Settings |
|---|---|---|
| **⚡ AUTO SCAN** | Automatic Welch PSD FFT resonance scanner | Dynamic peak search, adaptive Q-factor |
| **🟡 SUNO v3.5/v4** | Neural vocoder detox, high-frequency air synthesis | Notch: 5200 Hz, Exciter: 18%, Sub: 34 Hz |
| **🟣 UDIO 1.5** | Glassy harshness smoothing, 3D Mid/Side widening | Notch: 6100 Hz, Exciter: 14%, Tape: 1.06x |
| **🔴 CLUB PUNCH** | High-energy kick/bass density, EDM transient puncher | Mono < 140 Hz, Drum Punch: +35%, -0.1 dBFS |
| **⚪ AUDIOPHILE** | Transparent analog correction for acoustic & jazz | Subtle saturation, True-Peak: -1.0 dBFS |

---

## 7. Stem Separation: Built-In Fast DSP vs Dedicated AI Splitters (Demucs / UVR5)

PHARMAKON 2.0 provides two streamlined workflows for stem mastering:

### 1. Autonomous Built-In Splitter (`🧬 SPLIT & STEM MASTER` button):
* **Technology:** Proprietary lightweight pure SciPy mathematical DSP (STFT Harmonic-Percussive Source Separation with Wiener soft masks and stereo coherence filtering).
* **Advantages:** Zero downloads, 0 MB disk footprint, no PyTorch or GPU required, runs in seconds on any laptop CPU. Instantly isolates Drums transients, True-Mono Bass, Center Vocals, and Stereo Other.
* **Acoustic Limitation:** Pure spectral math cannot distinguish human vocal formants from heavily distorted lead guitars centered in the exact same mid-range.

### 2. High-Precision Studio Vocal Extraction (Recommended Open-Source AI Tools):
If your production demands surgically isolated acapellas free of centered guitar solos:
* 🔗 **[Meta AI Demucs](https://github.com/facebookresearch/demucs)** (by Alexandre Défossez, MIT License) — state-of-the-art deep neural separation distinguishing vocal timbres from instrument overtones.
* 🔗 **[Ultimate Vocal Remover GUI (UVR5)](https://github.com/Anjok07/ultimatevocalremovergui)** — the gold standard free open-source desktop application housing top MDX-Net, Demucs, and VR-Arch separation engines.

> **Studio Workflow:**  
> Separate your song in UVR5 or Demucs into 4 stems (`vocals.wav`, `drums.wav`, `bass.wav`, `other.wav`), place them in a folder, and click **`📁 BROWSE STEMS...`** in Section 01.  
> PHARMAKON will lock low-end kick/bass phase (**Sub Sync Alignment**), tame AI vocoder harshness, punch drum transients, and master through the analog console and 4x True-Peak limiter!

---

## 8. Studio Mastering Certificate & Export

1. **📄 OPEN FULL REPORT:** Opens an interactive HTML diagnostic report in your default browser with SVG spectrograms, LUFS/True-Peak metrics, and unique mastering serial number.
2. **📸 EXPORT PNG CARD:** Generates a studio quality certificate card via native Windows "Save As..." dialog.
3. **⬇ DOWNLOAD MASTER (.WAV):** Exports lossless 24-bit studio master WAV files with custom destination folder selection.

---

## 9. 🚀 Quick Start

### Option 1: Standalone Portable (Zero-Install for Windows)
> **Recommended for musicians & producers. No Python, pip, or command-line required.**

1. Download **[PHARMAKON_v2.0_Windows_Portable.zip](https://github.com/alex-gerek/PHARMAKON/releases/download/v2.0/PHARMAKON_v2.0_Windows_Portable.zip)** (139 MB).
2. Extract the `PHARMAKON` folder anywhere on your computer.
3. Double-click **`Pharmakon.exe`** (or `Start_Pharmakon.bat`).
4. The studio console will instantly launch in dedicated studio window mode.

---

### Option 2: For Developers & Source Build (Python 3.9+)

<details>
<summary><b>Expand source installation instructions</b></summary>

#### 1. Clone the repository
```bash
git clone https://github.com/alex-gerek/PHARMAKON.git
cd PHARMAKON
```

#### 2. Install dependencies
```bash
pip install -r requirements.txt
```

#### 3. Launch console
Double-click:
```text
Pharmakon_GUI.bat
```
*(Or run in terminal: `python gui/server.py`)*

Open your browser at: 👉 **`http://127.0.0.1:7860`**

</details>

### Studio Hotkeys:
* `Space` — Play / Pause
* `A` — Monitor RAW
* `B` — Monitor MASTER
* `D` — Monitor DELTA (Isolated poison)
* `1` ... `6` — Switch Scopes (Dual, Single, RTA, DSP, Wave, Phase Scope)
* `L` — Loop 5-second region
* `Escape` — Clear surgical calipers

---

## 10. Engineering Monographs & White Papers
Mathematical proofs, transfer functions, and AES/IEEE calibrations are documented in [`articles/`](articles/):
* [01. Why Equalizers Cannot Cure AI Audio: The Physics of Dead Air Above 16 kHz](articles/01_why_equalizers_cannot_cure_ai_audio.md)
* [02. Spectral Geometry vs Gigabyte Weights: Fast Deterministic DSP for Vocal Isolation](articles/02_neural_weights_vs_wiener_estimation.md)
* [03. The Physics of Analog Tape Saturation: Soft Clipping and Asymmetric Tanh Compression](articles/03_magnetic_tape_physics_and_tanh_saturation.md)
* [04. Death in the Club: The Low-End Phase War Between Kick and Sub-Bass (Sub-Sync)](articles/04_death_in_the_club_sub_phase_cancellation.md)
* [05. Inter-Sample Peaks (True-Peak): Why Streaming Distorts and How 4X Polyphase Oversampling Solves It](articles/05_intersample_peaks_and_4x_oversampling.md)

---

## 11. Author & License
Conceived and engineered by **Lex Gerek**  
* YouTube / Portfolio: [Lex Gerek](https://www.youtube.com/@alex-gerek)  
* GitHub: [@alex-gerek](https://github.com/alex-gerek)  

Released under the **MIT License**. Free for personal, commercial, and studio use.
