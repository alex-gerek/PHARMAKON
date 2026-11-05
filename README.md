<p align="center">
  <img src="gui/static/studio_icon.png" width="130" height="130" alt="PHARMAKON Logo">
</p>

# PHARMAKON 2.0
## Studio-Grade Audio Antidote, AI De-Harshing & True-Peak Mastering Console
### Created by Lex Gerek // Abbey Road 1974 × Blade Runner 2049

<p align="center">
  <a href="https://github.com/alex-gerek/PHARMAKON/releases/download/v2.0.3/PHARMAKON_v2.0.3_Windows_Portable.zip">
    <img src="https://img.shields.io/badge/Download%20Windows%20Portable%20(.exe)-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Download Windows Portable">
  </a>
  &nbsp;
  <a href="https://x.com/LexGerek/status/2116217723654955252?a=MI6yI7pf75A6ecEz4HM&s=20" target="_blank">
    <img src="https://img.shields.io/badge/Watch%20Walkthrough%20on%20X-000000?style=for-the-badge&logo=x&logoColor=white" alt="Watch Studio Walkthrough">
  </a>
  &nbsp;
  <a href="https://github.com/alex-gerek/PHARMAKON/archive/refs/heads/master.zip">
    <img src="https://img.shields.io/badge/Source%20Code%20ZIP-238636?style=for-the-badge&logo=github&logoColor=white" alt="Download Source Code ZIP">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0.3-emerald.svg?style=flat-square&color=10b981" alt="Version 2.0.3">
  <img src="https://img.shields.io/badge/Export-24--Bit%20PCM__24-0d9488.svg?style=flat-square" alt="24-Bit PCM_24">
  <img src="https://img.shields.io/badge/Auto--Sync-Live%20Patch%20Engine-6366f1.svg?style=flat-square" alt="Auto-Sync">
  <img src="https://img.shields.io/badge/DSP-Dynamic%20Ducker%20%2B%20Exciter-blue.svg?style=flat-square" alt="DSP Core">
  <img src="https://img.shields.io/badge/Oscilloscope-60%20FPS%20CRT%20%2B%20Phase%20Scope-brightgreen.svg?style=flat-square" alt="CRT Scope">
  <img src="https://img.shields.io/badge/True--Peak%20Limiter-4x%20Oversampling-f59e0b.svg?style=flat-square" alt="True Peak">
  <img src="https://img.shields.io/badge/Monitoring-A%20%2F%20B%20%2F%20Delta-purple.svg?style=flat-square" alt="Monitoring">
  <img src="https://img.shields.io/badge/Loudness-ITU--R%20BS.1770--4%20LUFS-cyan.svg?style=flat-square" alt="LUFS">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078d7?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/Author-Lex%20Gerek-black.svg?style=flat-square&logo=x" alt="Lex Gerek">
  <img src="https://img.shields.io/badge/License-MIT-orange.svg?style=flat-square" alt="License">
</p>

---

## 📚 Engineering Guides & Knowledge Base

Deep architectural and operational documentation for producers, audio engineers, and AI creators:
- [📖 **The Definitive Guide to Stem Mastering AI Music** (STEM_MASTERING_GUIDE.md)](STEM_MASTERING_GUIDE.md)  
  *4-stem Wiener decomposition, sub-bass Linkwitz-Riley LR4 mono-locking, resolving kick-bass phase clashes, and streaming loudness targets.*
- [🔬 **Neural Audio Detox: AI Audio Restoration Workflow** (AI_AUDIO_RESTORATION_WORKFLOW.md)](AI_AUDIO_RESTORATION_WORKFLOW.md)  
  *Root cause analysis of Suno & Udio metallic whistle, ballistic resonance ducking @ 5.2 kHz, asymmetric Studer A800 tape saturation, and reading the Spectral Diagnosis Certificate.*

---

## 1. Why PHARMAKON: The Anatomy of "AI Poison"

> 📺 **Official Studio Walkthrough (A/B & Delta Tests):**  
> [**Watch Video on X: Treating Generative Audio: Pure Mathematical DSP | PHARMAKON 2.0**](https://x.com/LexGerek/status/2116217723654955252?a=MI6yI7pf75A6ecEz4HM&s=20)

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

**PHARMAKON 2.0 is a dedicated analog-digital resuscitation console.**  
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
When mastering stems (Drums + Bass + Vocals + Other), cross-correlation in the <100 Hz band estimates low-end phase offset and polarity within a bounded lag window to reduce destructive sub-bass cancellation. See research article: [Death in the Club](articles/04_death_in_the_club_sub_phase_cancellation.md) ([Original publication on X](https://x.com/LexGerek/status/2118355503122182427)).

### 🛡 5. 4x Polyphase True-Peak Limiter & OOM Streaming Chunking
A 4x polyphase oversampled lookahead limiter (`scipy.signal.resample_poly`) enforces zero inter-sample clipping across the master bus. Streaming chunking with raised-cosine crossfading prevents memory exhaustion (OOM) on long tracks and DJ sets.
- Default True-Peak Ceiling: -0.3 dBFS (Compliant with ITU-R BS.1770-5 and streaming broadcast targets).

### 📊 6. ITU-R BS.1770-4 / EBU R128 Loudness Metering
True integrated LUFS calculation featuring dual-stage K-weighting filtering and gated energy integration (-70 LKFS absolute / -10 dB relative gate).

### 📼 7. 4x Polyphase Asymmetric Tape Saturation & 10 Hz DC-Blocker
Calibrated to Technical Whitepaper v2.6: combines 3.5 kHz HF pre-emphasis, 4x polyphase oversampling, global-asymptote scaled asymmetric `tanh` waveshaping (-38.05 dBc even 2nd-harmonic warmth, aliasing <= -48 dBc), and a 10 Hz recursive one-pole DC-blocker (`|DC| < 1e-7` steady-state in `float32`).

### 🔒 8. Verified 24-Bit PCM_24 Export & Diagnostic Telemetry
Every rendered studio master, `RAW_SUM`, `DELTA_POISON`, and stem WAV is explicitly written as 24-bit `PCM_24` and verified post-export (`verify_wav_export`) for frame count, sample rate, channel layout, and subtype, backed by non-intrusive `pharmakon.dsp` diagnostic logging.

---

## 3. Monitoring Bay: A / B / Δ (Delta Residue)

Three click-free, phase-aligned auditioning modes:

| Button | Key | Mode | Function |
|---|:---:|---|---|
| **[A] RAW** | `A` | Untreated Track | Original AI file with harsh digital sibilance and ISP clipping (Ruby CRT beam). |
| **[B] MASTER** | `B` | PHARMAKON Master | Full analog-modeled master: cohesive sub-bass, warm tape glue, silky air (Emerald CRT beam). |
| **[Δ] DELTA** | `D` | Subtraction Bay | **Audition the raw null difference** ($\text{Raw} - \text{Master}$; note: `DELTA_POISON.wav` is exported without loudness gain-matching so overall level/saturation/width shifts are audible alongside extracted resonances, whereas spectral delta metrics apply RMS gain-matching). |

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
| **🟡 SUNO v3.5/v4** | Neural vocoder detox, high-frequency air synthesis | Notch: 5200 Hz, Exciter: 18%, Sub: 35 Hz |
| **🟣 UDIO 1.5** | Glassy harshness smoothing, 3D Mid/Side widening | Notch: 6100 Hz, Exciter: 14%, Tape: 1.06x |
| **🔴 CLUB PUNCH** | High-energy kick/bass density, EDM transient puncher | Mono < 140 Hz, Drum Punch: +35%, -0.1 dBFS |
| **⚪ AUDIOPHILE** | Transparent analog correction for acoustic & jazz | Subtle saturation, True-Peak: -0.5 dBFS |

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
3. **⬇ DOWNLOAD MASTER (.WAV):** Exports header-verified 24-bit `PCM_24` studio master WAV files with custom destination folder selection.
4. **⚡ DELTA POISON (.WAV):** Exports the isolated null-difference artifact residue (`Raw - Master`) in verified 24-bit `PCM_24` WAV format.
5. **📦 DOWNLOAD STEMS (.ZIP):** Packages all 4 separated or processed 24-bit `PCM_24` stems into a lossless studio archive.

---

## 9. 🚀 Installation & Quick Start

### Option 1: Zero-Install Windows Package (Recommended for Producers & Creators)
> **No Python, no command-line, no compilers, no external libraries required.**

1. **Download & Extract:**  
   Download **[PHARMAKON_v2.0.3_Windows_Portable.zip](https://github.com/alex-gerek/PHARMAKON/releases/download/v2.0.3/PHARMAKON_v2.0.3_Windows_Portable.zip)** (169 MB).  
   > *Important:* Right-click the downloaded `.zip` file and select **"Extract All..."** into a folder of your choice (e.g. `Downloads`, `Desktop`, or `C:\PHARMAKON`). Running directly from inside an unextracted zip runs in a temporary cache.

2. **Choose your installation method:**

   * **Method A: Graphical Setup Wizard (`Install_PHARMAKON.bat`)**  
     Double-click **`Install_PHARMAKON.bat`**.  
     - A dark-themed graphical installer opens.
     - **Destination Folder:** Select where to install (default: `%LOCALAPPDATA%\Programs\PHARMAKON 2.0`, or browse to any custom folder on `C:`, `D:`, etc.).
     - **Desktop Shortcut:** Automatically creates a high-resolution Desktop shortcut with the custom studio gold icon.
     - **Start Menu:** Adds PHARMAKON 2.0 to your Windows Start Menu.
     - Click **INSTALL PHARMAKON** - setup completes in under 3 seconds with zero admin prompts.

   * **Method B: Instant Desktop Shortcut (`Create_Desktop_Shortcut.bat`)**  
     If you prefer keeping the extracted folder right where it is (or on an external SSD/USB drive):  
     - Double-click **`Create_Desktop_Shortcut.bat`**.  
     - Instantly generates the `PHARMAKON 2.0` shortcut on your Windows Desktop pointing directly to this directory.

   * **Method C: Direct Standalone Launch**  
     - Double-click **`Start_Pharmakon.bat`** (or `Pharmakon.exe`).  
     - To cleanly stop the background engine when finished, double-click **`Stop_Pharmakon.bat`**.

3. **🔄 Smart Online Auto-Update (`AUTO-SYNC`):**  
   - On launch (or when clicking the header **`AUTO-SYNC v2.0.3`** status pill), PHARMAKON checks GitHub `VERSION.json` for verified DSP & UI patches, syntax-validates them atomically into `_live_patches/`, and hot-mounts updates on the fly.  
   - **100% Offline Ready:** Remains completely standalone and functional with zero internet connection.

---

### Step-by-Step Studio Workflow:
1. **Launch Console:** Launch via the Desktop shortcut or `Start_Pharmakon.bat`. Your browser or desktop window will open to `http://127.0.0.1:7860`.
2. **Load Audio:** Drag and drop any Suno, Udio, or vocal track (WAV, MP3, FLAC, OGG) onto the drop zone, or click **Browse**.
3. **Select Processing Mode:**
   - **Commence Re-Mastering:** Runs full-mix de-harshing, dynamic resonance notch, tape saturation, stereo widening, and 4x True-Peak limiting.
   - **Split & Stem Master:** Separates the track into 4 stems (Vocals, Drums, Bass, Other), locks sub-bass mono phase, and masters each stem with custom dynamics.
4. **Inspect & Compare:**
   - Press `A` to listen to the raw track, `B` for the mastered result, or `D` (Delta) to audition solely the extracted digital artifacts and harshness.
   - Switch visualizers with keys `1` to `6` (Dual CRT, RTA Spectrum, Lissajous Phase Scope).
5. **Export Master:** Click **Download Master (.WAV)** to save your pristine 24-bit studio master, and export the official **Mastering Certificate** as an interactive HTML report or high-resolution PNG card.

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

#### 4. Run DSP regression & benchmark suites
```bash
pytest -v
python tests/hunter_bench/run_hunter_bench.py
```

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
* [03. Beyond tanh: Engineering Asymmetric Saturation for Digital Audio](articles/03_magnetic_tape_physics_and_tanh_saturation.md) ([PDF Whitepaper](PHARMAKON_Saturation_Whitepaper.pdf))
* [04. Death in the Club: A Kick, a Bassline, and a Phase Problem That Refuses to Die](articles/04_death_in_the_club_sub_phase_cancellation.md) ([Original publication on X](https://x.com/LexGerek/status/2118355503122182427))
* [05. Inter-Sample Peaks (True-Peak): Why Streaming Distorts and How 4X Polyphase Oversampling Solves It](articles/05_intersample_peaks_and_4x_oversampling.md)
* [06. From Python to C++20: Architecting the Real-Time DSP Engine of PHARMAKON PRO](articles/06_from_python_to_cxx20_architecting_pharmakon_pro.md)

---

## 11. Real-Time DAW Plugin: PHARMAKON PRO
Looking for zero-latency, sample-accurate DAW integration?

**PHARMAKON PRO** is the commercial real-time C++20 DAW plugin (VST3, AU, CLAP, Standalone) built on JUCE 8 with dual 60 FPS vector CRT displays, 45-degree Lissajous phase goniometer, and AVX2-accelerated DSP for Ableton Live, Cockos REAPER, FL Studio, Logic Pro, and Cubase.
* Architecture white paper: [Article 06: From Python to C++20](articles/06_from_python_to_cxx20_architecting_pharmakon_pro.md)

---

## 12. Author & License
Conceived and engineered by **Lex Gerek**  
* X / Twitter: [@LexGerek](https://x.com/LexGerek)

* GitHub: [@alex-gerek](https://github.com/alex-gerek)  

Released under the **MIT License**. Free for personal, commercial, and studio use.
