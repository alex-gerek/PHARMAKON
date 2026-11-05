# Open Questions & Future Research Agenda
## Death in the Club — Sub-Sync Experimental Validation

This document outlines unresolved theoretical, algorithmic, and psychoacoustic questions identified during Task 04 validation. These items define the research roadmap before any guarded windowed Sub-Sync algorithm can be considered for production DSP deployment in PHARMAKON.

---

### 1. Psychoacoustic Perception & Masking (The "Gain != Quality" Question)

* **Open Question 1.1: Does coherent sub-summation improve mix clarity or induce low-end muddiness?**  
  * *Observation:* Re-aligning kick and bass to coherent summation increases sub-band energy by $+1$ to $+6\text{ dB}$.  
  * *Hypothesis:* While physical pressure at 50 Hz increases, this acoustic swell may psychoacoustically mask lower-mid fundamentals ($150–400\text{ Hz}$), clouding vocal presence and snare punch.  
  * *Required Test:* Formal double-blind MUSHRA (ITU-R BS.1534) listening tests comparing:
    1. Unaligned mix
    2. Aligned mix with unadjusted faders (+1 to +3 dB sub swell)
    3. Aligned mix with bass fader attenuated by $-1.5\text{ dB}$ (headroom-neutral test).

* **Open Question 1.2: Subjective perception of transient pitch glides vs static basslines**  
  * *Observation:* Electronic kicks sweep rapidly from $150\text{ Hz}$ to $40\text{ Hz}$ in the first $30–50\text{ ms}$.  
  * *Open Problem:* The human ear perceives instantaneous pitch along an integration window ($20–50\text{ ms}$). Phase alignment that maximizes correlation across a $200\text{ ms}$ window may lock the tail at $45\text{ Hz}$ while slightly misaligning the $80\text{ Hz}$ initial punch. Which interval dominates perceived low-end impact?

---

### 2. Algorithmic Windowing & Temporal Boundary Dynamics

* **Open Question 2.1: Window duration dependence on kick envelope vs bass note duration**  
  * *Current Prototype:* Uses fixed $200\text{ ms}$ post-trigger analysis windows.  
  * *Failure Mode:* On sustained 808 sub notes lasting $1.5\text{ s}$, tapering back to the unaligned baseline after $200\text{ ms}$ creates a slow phase modulation or subtle amplitude dip during the sustain phase.  
  * *Proposed Investigation:* Adaptive envelope-tracking windowing where the correction window duration $\tau_{win}$ matches the instantaneous decay time of the kick drum:
    $$\tau_{win} = \arg\min_t \left( E_{\text{kick}}(t) < -24\text{ dB relative to peak} \right)$$

* **Open Question 2.2: Fast tempos and overlapping kick windows (>150 BPM)**  
  * *Edge Case:* In drum & bass, hardcore techno, or metal blast beats ($160–200\text{ BPM}$), kick hits occur every $150–180\text{ ms}$.  
  * *Open Problem:* When window duration exceeds the inter-onset interval, adjacent window shifts can conflict (e.g. Kick 1 asks for $+2.0\text{ ms}$, Kick 2 asks for $-1.5\text{ ms}$).  
  * *Proposed Investigation:* Spline-interpolated time-warp trajectory $\tau(t)$ constrained by a maximum slew rate $|\frac{d\tau}{dt}| < \delta_{pitch\_shift}$ to avoid perceptible pitch-wobble / flutter.

* **Open Question 2.3: Boundary cross-fade artifacts & phase cancellation during transitions**  
  * *Mechanism:* Blending a shifted segment $x(t - \tau)$ with an unshifted segment $x(t)$ via a cross-fade window $w(t)$:
    $$y(t) = w(t) x(t - \tau) + [1 - w(t)] x(t)$$
    creates an internal comb filter during the cross-fade transition whenever $\tau \ne 0$!  
  * *Severity:* For $\tau = 4\text{ ms}$ at $125\text{ Hz}$, the crossfade midpoint $w=0.5$ produces $0.5 x(t) - 0.5 x(t) = 0$ (a brief transient cancellation during the cross-fade itself).  
  * *Research Need:* Measure whether time-domain granular cross-fading or continuous time-varying allpass filtering avoids transition comb filtering.

---

### 3. Complex Musical Stems & Non-Ideal Signals

* **Open Question 3.1: Pitch-bending 808s and portamento glide basslines**  
  * *Challenge:* When an 808 glides in pitch during a sustained kick decay, cross-correlation produces multiple local maxima or broad, ambiguous correlation plateaus.  
  * *Research Need:* Test guarded per-kick alignment against continuous pitch-tracking signals.

* **Open Question 3.2: Stereo sub-bass and decorrelated low end**  
  * *Challenge:* Modern bass sound designs often incorporate stereo chorus, unison detune, or Haas delay on bass stems.  
  * *Investigation:* Does Sub-Sync apply independent per-channel delays (risking stereo image destabilization) or mono-referenced delay applied equally to left and right channels?

* **Open Question 3.3: Pre-existing sub-bass distortion & saturation harmonics**  
  * *Challenge:* When bass stems contain heavy saturation (fuzz, tube drive), higher harmonics ($200–2000\text{ Hz}$) have significant energy. Shifting the full-range bass preserves internal harmonic alignment, but does shifting the high attack interfere with snare or vocal transients?

---

### 4. Real-Time C++20 / JUCE Plugin Architecture Constraints

* **Open Question 4.1: Latency & Lookahead in VST3/AU Environments**  
  * *Constraint:* Detecting a kick onset requires at least $5–10\text{ ms}$ lookahead to align the bass before the transient strikes.  
  * *Production Impact:* Introducing a $10\text{ ms}$ lookahead adds 480 samples of plugin latency. How does this integrate into the zero-latency live processing architecture of PHARMAKON PRO?

* **Open Question 4.2: Sidechain Bus Architecture**  
  * *Requirement:* Sub-Sync in a DAW requires the drum or kick stem routed via a sidechain input bus into the bass channel plugin (or master console).  
  * *Implementation:* Evaluating cross-track phase coherence across distinct audio thread buffers with varying buffer sizes ($64$ to $1024$ samples).
