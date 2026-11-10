# Who Put Plastic in My Music? Hunting Down the Math Behind a Cleaner Sound

**Author:** Lex Gerek (Sound Architect / Engineer)  
**Project:** PHARMAKON 3.2 Studio Console (Clean Chain, Track Intelligence Map)  
**Implementation:** `remaster_engine.py`, `track_map_engine.py`, measurement bench in `bench/`

---

### 1. Why we audited the math

PHARMAKON exists for one reason: AI-generated music should sound cleaner and easier to listen to, and still sound like itself. Version 3.2 is the result of a full mathematical audit of the engine. Every formula was tested on signals with a known correct answer, and every statement in the report now comes from a measurement of the actual file.

The audit left us with a simple working principle. Everything the processing touches falls into one of two classes:

- **Defects.** These were never part of the music: the metallic resonances a generator leaves behind, intermodulation dirt, digital aliasing, clicks. Our goal is to bring them down, and in our bench a change is accepted only if no measured defect grows.
- **Taste.** Brightness, tonal balance, density. That is the artist's decision, so it stays within a tight tolerance of the original.

Measurements tell us exactly what happened to the signal. Listening tells us whether the result is right. We use both, and we don't confuse one with the other.

---

### 2. What we found

The audit found two kinds of problems: errors in the math, and report numbers that measured nothing.

| Module | What was wrong | Consequence |
|---|---|---|
| LUFS meter | K-weighting filter built with the wrong formula | Filter off by up to 0.41 dB; the EBU reference test read 0.25 LU off, outside its ±0.1 LU tolerance |
| Resonance detector | Looked for the sharpest peak in the spectrum | Mistook notes for artifacts: cut notes by 8–10 dB, missed real resonances, and flagged clean music every time |
| De-harsher | Compared amplitude with bandwidth instead of its square root | A constant ~5.5 dB cut even on clean material |
| Saturation | HF pre-emphasis never compensated; distortion set by the source level | Harsher top end; up to 3% distortion on acoustic guitar |
| Sub-Sync | Broken window blending around kicks | Bass dips and clicks |
| Stems saturation | Bass and drums saturated without oversampling | Aliasing at −31…−33 dB: digital grit on the kick |
| Track Map | Tempo from the sub band only; sections on a fixed grid counted from 0:00; bass notes counted as kicks | Wrong tempo on most non-four-on-the-floor music, sections in the wrong places, kick counts up to 2× too high |

The reports had their own problems. The "clipping, 5 kHz resonance, phase issue" diagnosis appeared on every track. The "Verified Streaming Compliant" seal was stamped regardless of the file. The kick-to-bass correlation always read 1.00, because the signal was being compared with itself.

---

### 3. What we fixed, and the math behind it

Every fix rests on standard signal-processing math and is locked in by an automated test.

**Loudness.** The K-weighting filter is now derived through the bilinear transform of the ITU-R BS.1770-4 analog prototype. At 48 kHz the coefficients match the ITU table to machine precision; at any other sample rate they are computed exactly. The meter passes the EBU Tech 3341 tests (±0.1 LU).

**Resonances: line versus bump.** A note is a narrow line in the spectrum. Generator colouring is a broad bump in the spectral envelope, about f/Q wide. Detector v2 first removes the lines with a running median, then looks for bumps that hold the same frequency over time. The correction is a zero-phase peaking cut, applied only where the bump was found:

```math
y(t) = x(t) + w(t)\,\bigl[(H_{\mathrm{cut}} * x)(t) - x(t)\bigr], \qquad w(t) \in [0, 1]
```

Where $w(t) = 0$, the audio stays bit-identical to the original.

**De-harsher.** The amplitude of a broadband signal grows with the square root of its bandwidth, so the expected band ratio is now √(B₁/B₂). On pink noise the unwanted cut dropped from −5.5 dB to −0.2 dB.

**Saturation.** An exact inverse filter now follows the HF pre-emphasis. The original filter is minimum-phase, so its inverse is stable and cancels both magnitude and phase. The operating level is calibrated to a robust peak, the 99.9th percentile of amplitude, the way a tape machine is aligned to 0 VU. We also tested calibrating to average loudness and rejected it on the numbers: it widened the distortion spread between tracks.

**Sub-Sync and stems.** Windows around kicks now blend smoothly into the current output. Bass and drum saturation runs at 4× the sample rate, which pushes aliasing down to −63 dB.

**Track Intelligence Map.** We rebuilt it and checked it against ground truth: arrangements where every beat, kick and section boundary is known exactly.

- **Tempo.** The beat is read from kick, body and snare onsets across several bands, and the octave is chosen by where the off-beats fall. Exact tempo went from 28% to 88% on the reference set. Where the tempo is genuinely ambiguous (half-time, triplet feels), the map shows the second reading, and between the two the right answer was always shown.
- **Sections.** The bar grid is anchored to the first downbeat, so a pickup no longer shifts every boundary. Boundaries sit where the music measurably changes, and each section is named from what was measured. Boundary accuracy (within half a second) went from 0.22 to 0.97, correct labels from 27% to 99%. On arrangements the method never saw during tuning, it holds at 0.91 and 92%.
- **Kicks.** A kick is now a sharp low-end attack, not any low-end peak. On ground truth the F-score went from 0.16 to 0.98. In a dense full mix, kick detection stays hard, so the map labels the count as an estimate; with a drum stem the count comes from the stem.

---

### 4. What changed in sound

The new Clean Chain 3.2 is built to remove defects while keeping the artist's tone. We measured it on 12 tracks across different styles: techno, trance, pop, classical, acoustic guitar and more. All versions were loudness-matched before measuring. Full-chain metrics come from 6 tracks; saturation was measured on 8 (2 tracks are in both sets).

Beyond these tracks, every module was checked separately on material with a known answer: synthetic signals and arrangements where every beat, kick and boundary is known, resonances injected at a known frequency and strength into real music, and isolated drum stems used as a kick reference.

| Measure | Classic 3.1 | Clean Chain 3.2 |
|---|---|---|
| Persistent AI resonances (6 tracks) | left in place on 4 of 6, +3.8…+6.5 dB | below the 3 dB threshold on all 6; fully gone on 5 |
| Added sharpness (acum) | +0.05…+0.07 on every track | −0.01…+0.01 |
| "Air" 10–20 kHz | +1.4…+1.9 dB | +0.2…+0.3 dB |
| Saturation distortion on music (8 tracks) | −30…−38 dB, set by the source | −43…−45 dB on every track |
| Chain intermodulation (SMPTE test signal) | −24 dB | −33 dB |
| Dynamics: crest factor vs. original | −1.4…+0.2 dB (median −0.6) | −0.2…+0.4 dB (median +0.1) |

What I hear: the nagging metallic ring is gone, the top end stops stinging, dense passages get cleaner, and kicks and plucked strings breathe again. On material with no measured defect, Antidote makes no correction at all: nothing to treat means nothing gets touched. The previous sound remains available bit-for-bit through the Classic 3.1 switch.

---

### 5. Why you can trust the numbers

Every claim above is checked automatically: 105 tests run on every code change.

- **Standard references.** Loudness is tested against EBU Tech 3341, and true-peak against signals whose real peak is known analytically.
- **Signals with a known answer.** We inject resonances of known frequency and strength into music. Detector v2 made 0 false detections out of 12 (the old one: 12 out of 12), with a median frequency error of 0.5%. It finds a 9 dB resonance in 35 of 36 synthetic cases and in 24 of 30 cases on real tracks.
- **Data the method never saw.** The Track Map benchmarks include held-out arrangements that were never used for tuning. The saturation calibration was chosen on one set of tracks and confirmed on the full-chain bench.
- **The no-regression rule.** A change is accepted only if no measured defect grows. The saturation calibration, for example, reduced both distortion and dynamic squashing on every one of the 8 tracks.
- **An honest certificate.** The diagnosis and the seal are built only from measurements of the specific file. A defect is shown only if it was measured, and "fixed" only if the measurement after processing confirms it.

---

### 6. What comes next

The foundation is now measurable, so every next step follows the same rule: the goal is a number, and no defect is allowed to grow.

1. **Loudness for the venue.** Hit a club-ready level without crushing the groove, with the certificate showing exactly how far it went and why it stopped.
2. **Resonances that live in one part of a track.** Catching colouring that appears only in the chorus or only in the drop. Every step in sensitivity will be measured for false alarms on clean music, with the goal of keeping them as low as they are today.
3. **Antidote for stems.** Finding which stem carries the colouring and treating the source instead of the whole mix.
4. **Processing that follows the arrangement.** Protecting dynamics in breakdowns and intros, allowing more density in the drop, guided by the Track Map.
5. **Kick and bass that lock tighter.** More precise low-end alignment, verified against errors we inject ourselves.
6. **A player inside the map.** Click a section, loop it, compare raw and master, see where each defect lives on the timeline, and export cue points for DJ software.
7. **Certified psychoacoustics.** Standard loudness and sharpness models in place of today's approximation.
8. **PHARMAKON PRO.** The same engine as a real-time plugin inside your DAW.

The measurement bench is already in place to check each of these with the same metrics as today's fixes.

---

### 7. A last word

The numbers in this article are measurements. The judgement of the sound is mine: it is how I hear PHARMAKON 3.2 and why I built it this way. Load a track, open the certificate, and listen.

---
*Repository:* [https://github.com/alex-gerek/PHARMAKON](https://github.com/alex-gerek/PHARMAKON)
