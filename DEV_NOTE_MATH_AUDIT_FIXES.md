# Dev Note — DSP Math Audit Fixes (on top of 3.1 hardening, commit `19e6bf2`)

**Date:** 2026-11-09 · **Status:** uncommitted working tree, to be committed together with the metrics bench work
**Default audio output:** bit-identical to 3.1 in full-mix mode (baseline SHA-256 hashes in `test_dsp_core_audit.py` still pass)

## Summary

| # | Area | Problem | Fixed? | Changes sound? |
|---|---|---|---|---|
| 1 | LUFS meter | K-weighting not BS.1770 (-0.26 LU @ 1 kHz, -0.41 @ 2 kHz) | Yes + EBU Tech 3341 tests | No (measurement only) |
| 2 | Sub-Sync `align_sub_phase_limiter_aware` | Broken window blend: bass faded around every kick | Yes | Only `existing_guard` / fallback path |
| 3 | Local Guard `process_local_sub_sync` | Overlapping windows → click | Yes | Only kicks < 210 ms apart |
| 4 | Both Sub-Syncs | Acceptance check used wrap-around `np.roll` | Yes | Marginal |
| 5 | Track Map BPM | Integer-lag quantization + wrong hop at 44.1 kHz | Yes + test | No (map only) |
| 6 | De-harsher | Amplitude vs bandwidth ratio → constant ~5.5 dB cut | Option added, **default unchanged** | Only when enabled |
| 7 | True-Peak limiter | — (3.1 code verified correct; 2.0 was wrong) | Documented | No |
| 8 | Docs / UI | False "EBU R128 compliant at -0.3 dBTP", "Normalized to -14 LUFS", hidden +22 dB | Yes | No |
| 9 | Code comments | Wrong time constants, "equal-power", H2 claim | Yes | No |
| 10 | Stems: bass / drum `soft_clip` | Saturation at 1X → aliasing -31 / -33 dB | Yes, 4X oversampled (§13) | Yes — removes aliasing only (stems mode) |
| 11 | Resonance detection | v1 (product Auto Antidote) flags notes, misses real resonances | Detector v2 (§14) | — |
| 12 | Auto Antidote | v1 cuts notes by 8–10 dB and leaves real resonances | v2 behind flag `antidote_v2` (§15), default off | Only when enabled |
| 13 | Tape stage HF tilt | Pre-emphasis never de-emphasized → +1.3…+1.5 dB above 3.5 kHz, chain sharper | Matched de-emphasis behind flag `tape_deemphasis` (§16), default off | Only when enabled |
| 14 | Tape operating level | Distortion set by how hot the source was rendered (−30…−38 dB, guitar worst) | Peak-calibrated operating level `tape_ref_peak_dbfs` (§18), default off | Only when enabled |
| 15 | Default sound | — | **Clean Chain 3.2 is the default**; `classic_31` restores 3.1 bit-exactly (§19) | **Yes — default sound changes** |

---

## 1. LUFS meter — `remaster_engine.py::_get_k_weighting_biquads`

**Problem.** Stage 1 (high-shelf) used the RBJ "Audio EQ Cookbook" formula with f0 / gain / Q constants that belong to the bilinear `K = tan(pi*f0/fs)` formulation; stage 2 had a normalized numerator instead of ITU's `[1, -2, 1]`. Error vs ITU: -0.04 dB @ 100 Hz, -0.26 dB @ 1 kHz, -0.41 dB @ 2 kHz. EBU Tech 3341 case 1 read -23.25 LUFS (tolerance ±0.1).

**Fix.** Bilinear formulation (`Vh`, `Vb`, `K`). At 48 kHz coefficients equal the ITU-R BS.1770-4 table to ~1e-16; other sample rates (44.1 / 96 kHz) get the exact equivalent filter (the ITU table alone is 48 kHz-only).

**Effect.**
- Absolute LUFS readings ~0.25 LU higher than in ≤3.1 (e.g. Bronze Psalter -11.32 → ~-11.07).
- Match Input Loudness: orig and master use the same meter, so the old error mostly cancelled (~0.01 LU on demos); now exact.
- `baseline.json` `*_metrics.lufs_*` are old-meter snapshots, not asserted by tests; regenerate if wanted.

**Tests:** `tests/test_ebu_tech3341_compliance.py` (23): ITU coefficient table; Tech 3341 integrated cases 1–5 (incl. relative / absolute gate) at 44.1 + 48 kHz, ±0.1 LU; analytic True-Peak cases (fs/4 inter-sample sine, sines 1–18 kHz), tolerance +0.2/-0.4 dB. Old meter fails 11/23.

**True-Peak note (not a bug):** `resample_poly` sees silence outside the file, so an abrupt high-frequency start reads up to +0.4 dB at the very edge — that is real ringing of a step from silence. Steady-state accuracy ±0.05 dB. Tests use 10 ms edge fades.

## 2. `align_sub_phase_limiter_aware` — `remaster_engine.py`

**Problem.** Overlap-add divided by `max(1, weight_acc)`, so where one Tukey window covered a sample (weight < 1) the bass was multiplied by the taper → faded toward zero around **every** detected kick, even if all shifts were rejected (output ≠ input by up to 0.29, dips to -119 dB). Used by `sub_sync_mode='existing_guard'` and as exception fallback of `local_guard` / `limiter_aware`.

**Fix.** Output starts as the untouched bass; accepted shifts are crossfaded in: `y = y_prev*(1-w) + shifted*w`. Rejected events are bit-exact (diff 1.5e-8 = float32 rounding).

## 3. Local Guard — `track_map_engine.py::process_local_sub_sync`

**Problem.** Window 210 ms, kicks may be 120 ms apart. Each accepted window blended `raw*(1-w) + shifted*w`, overwriting the previous window's correction → step back to raw at the window start (click).

**Fix.** Blend onto the current output: `bass_corrected*(1-w) + shifted*w`.

**Verification (forced 2 ms shift on every kick, 130 ms spacing, steady 55 Hz bass):**

| | Max sample-to-sample step | HF residue > 2 kHz |
|---|---|---|
| Input | 0.0029 | -114 dBFS |
| Local Guard old → new | 0.271 → 0.003 | -53 → -93 dBFS |
| Limiter-aware old → new | 0.282 → 0.003 | -63 → -93 dBFS |

## 4. Sub-Sync acceptance consistency (both engines)

Acceptance metrics used `np.roll` with wrap-around while candidate scoring filled the shifted-out edge with the raw signal. Both now use the same edge fill.

## 5. Track Map BPM — `track_map_engine.py::detect_bpm_and_grid`

**Problems.** (a) Integer autocorrelation lag → 128 BPM read as 127.66 (bar grid drifts ~0.6 s over 128 bars). (b) Hop is `int(0.005*sr)` = 220 samples = 4.989 ms at 44.1 kHz, but the formula assumed exactly 5 ms.

**Fix.** Real hop duration; parabolic interpolation of the autocorrelation peak refined on the 4-beat (bar) peak; `signal.correlate` (FFT) instead of `np.correlate`. Worst error on synthetic kicks 90–170 BPM: 0.51 → 0.05 BPM.

**Test:** `tests/test_bpm_precision.py` (±0.1 BPM at 44.1 / 48 kHz). Known limitation unchanged: search range is 90–170 BPM (174 BPM DnB is out of range).

## 6. De-harsher — `remaster_engine.py::dynamic_deharsh`

**Problem.** `expected_ratio = bw / (1.35*f)` compares a bandwidth ratio with an amplitude ratio (amplitudes of broadband material scale with `sqrt(bandwidth)`), so the band is ducked ~5.5 dB even on flat white / pink noise without any resonance.

**Change.** New argument `calibrated` and param `deharsh_calibrated` (default **False** = legacy sound). Calibrated mode uses `sqrt(bw_harsh / bw_ref)` from the real band edges.

| Signal | Legacy | Calibrated |
|---|---|---|
| White noise | -5.6 dB | -0.2 dB |
| Pink noise | -5.5 dB | -0.2 dB |
| White + 5 kHz resonance | -9.5 dB | -3.9 dB |

**Why the default stays legacy (for now).** On 4 real tracks (equal-LUFS renders in `_ab_listening/deharsh/`, not for commit), the resonance band vs original is -1.0…-1.9 dB with legacy, but -0.0…**+1.3 dB** with calibrated. The rest of the chain adds HF (tape pre-emphasis +1.3 dB above ~3.5 kHz, never de-emphasized; air exciter), and the legacy "error" was compensating for it. Two errors cancelling is not a design — this will be resolved with the objective metrics bench (next step), tuning each stage to a measurable target instead of by ear.

## 7. True-Peak limiter (no code change in this round)

The 3.1 P0-2 limiter (gain computed at 4X, min-pooled to 1X, applied to original samples, local tanh guard only where needed) was verified correct. Measured on 20 s noise with ten 8 dB overs, ceiling -1.0 dBTP:

| | Reported TP | Actual TP | Change to audio away from peaks (±60 ms excluded) |
|---|---|---|---|
| 2.0 limiter (`legacy_limiter=True`) | -1.15 dBTP | -3.36 dBTP | up to -26.7 dBFS (whole-file tanh) |
| 3.1 limiter | -1.20 dBTP | -1.20 dBTP | -148 dBFS (bit-transparent) |

So 2.0 misreported True-Peak (measured before its final stage) and saturated the whole track; 3.1 fixed both.

## 8. Documentation / UI

- **EBU R128 = max -1 dBTP.** Removed claims that the default -0.3 dBTP ceiling is "EBU R128 compliant": `README.md`, `README.txt`, `PHARMAKON_3_ARCHITECTURAL_GUIDE.md`, `AI_AUDIO_RESTORATION_WORKFLOW.md`, `articles_ru/README_RU.md` (it also wrongly stated -1.0 as the default).
- Meter scope stated precisely: "Integrated loudness per ITU-R BS.1770-4, verified against EBU Tech 3341 cases 1–5". Momentary / short-term / LRA (Tech 3342) not implemented → not called an "EBU R128 meter".
- **Article 05** (EN + RU, unpublished): BS.1770 described as measurement method, R128 as -1 dBTP, Spotify/Apple "recommend" not "mandate"; section 4 rewritten for the 3.1 limiter with the table above and a code listing that produces output identical to the engine (diff = 0); project header 2.0 → 3.1. Articles 01–04 (published) untouched.
- **GUI:** certificate footer (`app.js`); LUFS card subtitle; "Normalized to -14.0 LUFS" → "Measured at …"; static "-0.30 dBFS" → live `txtTruePeak` from `true_peak_proc_db`.
- **Delta spectrum:** legend now says "+22 dB display offset" (report + GUI); metrics expose `fft_delta_display_offset_db: 22.0`.
- `dist/PHARMAKON/docs/*` still old — regenerated by the release build.

## 9. Code comments corrected

Equal-gain (not equal-power) crossfades; real envelope time constants (drum transient 0.64 / 6.4 ms; de-harsh symmetric 35 Hz zero-phase); de-harsh max reduction ~16.5 dB; tape docstring: H2/H3 per level from `baseline.json` (H3 dominates at high level, H2 below ~-15 dBFS) and the un-de-emphasized HF tilt.

## 10. Tests

- Before: 42/42 in `tests/`.
- Now: **99 passed, 1 xfailed** across `tests/` + `research/death_in_the_club`.
- 1 failure, **pre-existing** (fails on `19e6bf2` too): `test_death_in_the_club.py::test_historical_claim_worst_legacy_drop_reproduced`.
- Fragile test to be aware of: `test_public_interfaces_and_default_params_preserved` asserts `apply_tape_warmth_v2` is on **line 130** — any line added above it fails the suite.

## 11. Open items (not changed)

1. **J(τ) vs Research Note 05:** code uses `peak_ref = max(peak_sum, |drums|, |bass|)` instead of `P_sum(0)` and λ = 1.0 in acceptance (paper: 1.2). Local Guard remains safe (hard `peak_diff <= 0.02 dB`). Proposal: update Note 05 to describe the code.
2. Mono files measured as dual-mono (+3 dB vs BS.1770 mono).
3. ~~Bass / drums `soft_clip` at 1X~~ — fixed, see §13.
4. De-harsh default + tape pre-emphasis + exciter → to be tuned with the metrics bench.

## 12. Objective metrics bench (new, v1) — `bench/`

- `bench/metrics.py` (pure NumPy/SciPy): resonance prominence 2–8 kHz, 7-band tonal balance + 1/3-octave tilt, presence flux (transient harshness), approximate Zwicker/Fastl sharpness with DIN 45692 weighting (self-calibrates to 1.013 at the 1 acum reference point; **not** ISO 532-1 certified), crest / PLR / LUFS / TP / stereo; chain metrics THD 1 kHz, SMPTE IMD, aliasing (9 kHz).
- `bench/run_bench.py`: renders chain variants per track, loudness-matches all versions (attenuation only), computes metrics + deltas vs original, checks DRAFT targets, writes `bench/results/<ts>/results.json` + `report.md`.
- `tests/test_bench_metrics.py`: white/pink tilt (+3 / 0 dB/oct), sharpness reference + monotonicity, resonance detection, chain identity vs clipping.

**First baseline (6 AI tracks, 60 s excerpts, `bench/results/20261109_075708/`):**
- The chain makes every track **sharper** (+0.05…+0.09 acum) and brighter: air +1.4…+1.9 dB, brilliance +0.6…+1.6 dB. Removing the air exciter changes air by only -0.04 dB → the main HF brightener is the **tape pre-emphasis**, not the exciter.
- Chain distortion at -6 dBFS: THD -32.6 dB, **SMPTE IMD -24.2 dB (≈6 %)** — all from the tape stage.
- **Bass / drum `soft_clip` at 1X alias at -33 / -31 dB** (vocals 4X: -63 dB) → audible grit on drums; P1-2 oversampling should be extended to them.
- PLR drops 0.3–1.7 dB, stays ≥ 8.9 dB; stereo side +0.5…+1.2 dB (intended widening).
- **Resonance metric v1 is not discriminative:** its strongest "resonances" are musical notes (2093 Hz = C7, 1661 Hz = G#6) — a 60 s average spectrum cannot tell a sustained note from an AI artifact. Same blind spot exists in the product's `detect_harsh_resonances` (Auto Antidote can notch a note). v2 needs time-resolved persistence + harmonic-structure tests.
- Reference corpus of human-made masters still missing (needed to define target tonal balance / sharpness).

Tests now: **103 passed, 1 xfailed**, 1 pre-existing failure (see §10).

## 13. Bass / drum saturation oversampled — `remaster_engine.py`

**Problem.** In stems mode the bass stage (`soft_clip(bass*1.05, 0.98)`) and the end of `enhance_drum_transients` (`soft_clip(drums, 0.98)`) ran `tanh` at 1X. `tanh` produces odd harmonics without bound; at 1X everything above Nyquist folds back as inharmonic aliasing ("digital grit"). P1-2 fixed this for vocals only.

**Fix.** New `soft_clip_oversampled(x, sr, threshold, oversample=4)` (placed after `saturate_vocal_oversampled`, so `apply_tape_warmth_v2` stays on line 130). Used for bass and drum stages. Note: the drum clip only runs when `drum_punch > 1.01` (presets suno / udio / club); the default `drum_punch = 1.0` returns the drums unprocessed.

**Measured (test tones):**

| Stage | Level | Aliasing 1X → 4X | THD | SMPTE IMD |
|---|---|---|---|---|
| Bass (×1.05) | -6 dBFS | -33.0 → **-63.2 dB** | -33.0 → -33.0 | -24.0 → -24.0 |
| Bass (×1.05) | -1 dBFS | -24.1 → **-54.4 dB** | unchanged | unchanged |
| Drums (×1.2) | -6 dBFS | -30.8 → **-61.0 dB** | -30.8 → -30.8 | -21.8 → -21.8 |
| Drums (×1.2) | -1 dBFS | -22.3 → **-52.5 dB** | unchanged | unchanged |

Small-signal response identical within ±0.03 dB up to 20 kHz. Saturation character (in-band harmonics, IMD) unchanged — only the aliased component is removed.

**On real drum stems** (punch 1.35): the removed component is -54…-56 dB re drum RMS, 56–98 % of it above 10 kHz — a real but modest improvement on typical material; it matters most on hot stems and the club preset.

**Tests:** `tests/test_oversampled_softclip.py` (aliasing ≤ -55 dB and ≥ 25 dB better than 1X; THD/IMD unchanged ±0.3 dB; flat small-signal response; 1-D input). Bench: `bench/results/20261109_090541/` — every nonlinear stage now aliases at ≤ -58.9 dB (full chain -58.9 dB with the air exciter, -61.0 dB without).

Full-mix mode does not use these stages: its audio and SHA-256 hashes are unchanged. Tests: **106 passed, 1 xfailed**, 1 pre-existing failure.

## 14. Resonance detector v2 — `remaster_engine.detect_resonances_v2` (wrapper `bench/resonance_v2.py`)

**Problem with v1** (`remaster_engine.detect_harsh_resonances`, used by Auto Antidote in `pharmakon1` mode): it takes the strongest narrow peak of one long-term spectrum in 3.2–7.8 kHz. A sustained note is such a peak, so v1 targets notes and misses real resonances.

**v2 principle.** A note partial is a spectral *line* (1–3 FFT bins); resonant colouring is a *bump of the envelope* (width ≈ f/Q, lifts noise, cymbals, breath and partials alike). Per 2 s segment (hop 1 s): Welch 8192 → remove lines with a ~200 Hz running median → envelope on a 1/96-octave grid → bump = envelope − 1-octave running median → bumps ≥ 1.5 dB and ≥ 1/24 octave wide in 2–9 kHz → persistence across segments ≥ 0.6, median height ≥ 2 dB. Outputs frequency, height, width → Q estimate, persistence.

**Ground-truth validation — `bench/validate_resonance.py`, results `bench/results/resonance_validation.json`:**
- Clean synthetic music (chords with 40 harmonics, melody up to C7, bass, hi-hats, noise floor) → any detection is a false positive.
- Same + injected peaking-EQ resonance (f 2.5–8 kHz, gain 3/4/6/9 dB, Q 5/10/20) → hit if detected within ±3 %.
- 5 real tracks + injected resonance (2 per gain/Q) → hit only if new vs the original.

| | v1 | v2 |
|---|---|---|
| False positives, clean synthetic | **12/12** | **0/12** |
| Synthetic recall 3 / 4 / 6 / 9 dB | 0 / 2 / 4 / 3 of 36 | 16 / 28 / 32 / 35 of 36 |
| Real-track recall 3 / 4 / 6 / 9 dB | 0 / 1 / 0 / 1 of 30 | 10 / 14 / 22 / 24 of 30 |
| Frequency error (median / max) | — | 0.52 % / 2.15 % |
| Q estimate / true Q (median) | — | 1.06 (±50 %; very narrow Q is underestimated) |

Weak spot: wide resonances (Q ≈ 5) on real tracks (≈ 40 % recall even at 9 dB) — the 1-octave baseline absorbs part of a wide bump.

**Bench with v2** (`bench/results/20261109_092922/`): 4 of 6 AI tracks show persistent colouring at **~2.05 kHz** (both Bronze Psalter versions, +4.0…+4.3 dB) or **~2.43 kHz** (Il Fuoco del Cuore +6.4 dB, Miami Summer +4.0 dB). The current chain does **not** reduce them (Δ −0.2…+1.0 dB): they lie below the 3.2 kHz lower limit of the product's detector, and v1 locks onto notes anyway. The same ~2.43 kHz in two different songs is a candidate generator signature — needs more tracks to confirm.

**Tests:** `tests/test_resonance_v2.py` (no detection on clean music with high notes; injected 6 dB / Q 10 at 5 kHz found with Q in 5–20; documents that v1 misses it). Bench target `res_v2_max_db ≤ 3 dB` replaces the v1 resonance target.

**Next:** Auto Antidote on v2 behind a flag (search 1.5–9 kHz, freq + Q from v2, de-harsh band from Q), then bench: `res_v2_max_db` must drop with no sharpness / dullness penalty.

## 15. Auto Antidote v2 in the full-mix chain — flag `antidote_v2` (default **False**)

**Where the code lives.** `detect_resonances_v2` and `apply_resonance_correction` are inside `remaster_engine.py` (block "2b. AUTO ANTIDOTE v2"), not a separate module: `auto_updater.py` live-patches only `remaster_engine.py` / `track_map_engine.py`, so a new module would break patched old bundles. `bench/resonance_v2.py` re-exports the engine function → bench and product measure with identical code. `apply_tape_warmth_v2` is still on line 130.

**Chain (`process_audio_array`, `mode == 'pharmakon1'` and `antidote_v2=True`):**
1. `detect_resonances_v2(audio)` on the input (2–9 kHz, persistent envelope bumps); v1 detection is skipped.
2. After the mono crossover, on the high band only: `apply_resonance_correction` — up to 3 zero-phase peaking cuts, cut = `antidote_v2_depth` (1.0) × measured height, capped at `antidote_v2_max_cut_db` (8 dB), Q = measured Q clipped to 2…16. Zero-phase via `sosfiltfilt` with half the gain per pass (total cut = target; verified: −6.00 dB ± 0.1 at f0, impulse not delayed).
3. The dynamic de-harsher keeps its preset frequency (transient harshness), legacy or calibrated per `deharsh_calibrated`.
4. Metrics: `antidote_version`, `antidote_v2_resonances`, `antidote_v2_corrections`.
Stems mode is not wired yet (needs a decision which stem gets the correction).

**Ground truth — `bench/validate_antidote.py` → `bench/results/antidote_validation.json`** (6 synthetic songs × 3 injected resonances, Q 10; residual = band level of chain(injected) − chain(clean)):

| Injected | Residual after v1 (default) | Residual after v2 (median / worst) |
|---|---|---|
| 4 dB | 3.79 dB | 1.32 / 2.97 dB |
| 6 dB | 6.14 dB | 1.17 / 1.51 dB |
| 9 dB | 8.77 dB | 1.24 / 1.60 dB |

**On clean music v1 cuts a note by 8.2–10.3 dB** (6/6 songs): it retargets the de-harsher onto the strongest note. v2 makes no correction on clean music (asserted).
The ~1.2 dB systematic residual: the detector's envelope smoothing underestimates the true bump height (~70–85 % of it). A depth > 1 could compensate but would over-cut wide bumps; left at 1.0 deliberately.

**Bench on 6 AI tracks — `bench/results/20261109_094647/`:**

| Variant | `res_v2_max_db ≤ 3` | Presence 2–5 kHz Δ | Brilliance 5–10 kHz Δ | Sharpness Δ |
|---|---|---|---|---|
| P31_DEFAULT (v1) | 2/6 | −0.1…+1.1 dB | +0.6…+1.3 dB | +0.05…+0.07 |
| ANTIDOTE_V2 | 6/6 | −0.9…+0.6 dB | +0.8…+1.2 dB | +0.05…+0.07 |
| ANTIDOTE_V2 + calibrated de-harsh | **6/6, 5 of 6 at 0 dB** | −0.5…+1.0 dB | +1.1…+1.6 dB | +0.06…+0.09 |

- The persistent 2.0–2.4 kHz colouring is removed (Il Fuoco del Cuore 6.4 → 0 dB, Bronze Psalter 4.3 → 0 dB, Miami Summer 4.0 → 0 dB with calibrated de-harsh).
- With the **legacy** de-harsher, new bumps appear after processing at 6.6–7.9 kHz that were not in the originals: its constant ~5.5 dB cut at 5 kHz plus the tape HF shelf make the region above look like a resonance. With the calibrated de-harsher they are gone → ANTIDOTE_V2 + calibrated is the first configuration where no stage creates colouring for another to fight.
- **Sharpness still rises on every variant** and brilliance/air stay +1.1…+1.9 dB: the remaining brightener is the tape pre-emphasis (§12). That is the next target.

**Tests:** `tests/test_antidote_v2.py` (injected 6 dB resonance: v1 residual > 4 dB, v2 < 2.5 dB and corrected within ±3 %; clean music → no correction; correction filter: exact −6 dB, zero phase). Totals: see §10 / final run.

## 16. Tape stage matched de-emphasis — flag `tape_deemphasis` (default **False**)

**Problem.** `apply_tape_warmth_v2` adds `0.2 × HP1(3.5 kHz)` before the saturator and never removes it: small-signal response +0.74 dB @ 3.5 kHz, +1.34 @ 10 kHz, +1.46 @ 19 kHz. The bench identified it as the main reason the chain makes every track sharper (air +1.8 dB; removing the air exciter changed air by only 0.04 dB).

**Fix.** New argument `deemphasis` (signature still starts on line 130). After decimation the exact inverse filter is applied: with HP = (b0 + b1 z⁻¹)/(1 + a1 z⁻¹), H = 1 + 0.2·HP and 1/H = (1 + a1 z⁻¹)/((1 + 0.2 b0) + (a1 + 0.2 b1) z⁻¹). H is minimum-phase, so the inverse is stable and cancels magnitude and phase. HF still drives the saturator harder (tape-style), but the linear response is flat. `process_audio_array` passes `params['tape_deemphasis']`.

**Verified:** small-signal response −0.11…−0.13 dB from 1 kHz to 19 kHz (flat within ±0.03 dB; constant −0.13 dB is the stage's own small-signal gain); H2/H3 change ≤ 0.6 dB at 0 / −6 / −18 dBFS; THD 1 kHz −32.6 → −33.2 dB; aliasing unchanged (−61 dB). SMPTE IMD stays −24.2 dB — it comes from the drive itself, not from the tilt (open item).

**Bench (6 AI tracks, `bench/results/20261109_deemph/`), median Δ vs original [range]:**

| Metric | P31_DEFAULT | V2 + cal. de-harsh | **V2 + cal. de-harsh + de-emphasis** | V2 + legacy de-harsh + de-emphasis |
|---|---|---|---|---|
| `res_v2_max_db` (absolute) | 4.06 [0…6.53] | 0 [0…2.27] | **0 [0…2.19]** | 0 [0…2.78] |
| Sharpness (acum) | +0.06 | +0.07 | **+0.01 [−0.01…+0.01]** | −0.01 |
| Presence 2–5 kHz | +0.80 | +0.14 | **−0.55** | −0.74 |
| Brilliance 5–10 kHz | +1.02 | +1.43 | **+0.20** | −0.30 |
| Air 10–20 kHz | +1.83 | +1.83 | **+0.34** (air exciter, intended) | +0.35 |
| Tilt (dB/oct) | +0.12 | −0.04 | −0.15 | −0.15 |
| Presence flux | −0.10 | −0.02 | +0.12 | +0.08 |
| PLR (absolute) | 9.40 | 9.48 | 9.50 | 9.58 |

Pass rate on DRAFT targets: V2 + cal. + de-emphasis passes resonance, presence, brilliance, tilt, PLR on 6/6; sharpness 1/6 (median +0.01 acum vs the strict "≤ 0" rule) and presence flux 2/6 (+0.12 dB median). The legacy-de-harsh variant passes sharpness 6/6 only because the legacy ~5.5 dB fixed cut at 5 kHz acts as a hidden presence/brilliance EQ.

**Decision needed (owner):** default chain. Proposed: `antidote_v2 + deharsh_calibrated + tape_deemphasis` — every stage mathematically correct, no stage creating colouring another one fights, sharpness neutral instead of +0.06. If a net "softer than original" result is wanted, it should be an explicit, documented tilt / presence parameter measured by the bench, not the legacy de-harsh bug. Targets "≤ 0" for sharpness and presence flux need a tolerance agreed against measurement repeatability.

**Tests:** `tests/test_tape_deemphasis.py` (flat response with flag within 0.1 dB, legacy tilt > 1 dB documented, H2/H3 within 1 dB).

## 17. Auto Antidote v2 is local in time — `antidote_v2_local` (default **True** inside v2)

**Why.** Processing should act only where a defect is present. The v2 detector already knows, per 2 s segment (hop 1 s), whether each resonance is present (`_presence`), so a static whole-track cut also attenuated healthy audio in segments without the resonance.

**How.** `detect_resonances_v2` now also returns `_seg_starts`, `_seg_n` and, per resonance, `_presence` (private keys, stripped from report metrics). `apply_resonance_correction(..., timeline=...)` computes the zero-phase cut `cut(x)` and blends `y = x + w(t)·(cut(x) − x)`, where `w = 1` in segments with the resonance, 0 elsewhere, 0.5 s raised-cosine transitions. Because `cut(x)` is zero-phase, the blend is a smooth time-varying cut depth (no comb filtering); where `w = 0` the audio is untouched. Each correction reports `time_coverage`. `antidote_v2_local=False` restores the static whole-track cut.

**Ground truth (6 dB / Q 10 resonance at 5.2 kHz injected into part of a synthetic song):**

| Resonance present in | Residual where present (local / global) | Clean part of the song (local / global) | Coverage |
|---|---|---|---|
| 70 % of song | +1.15 / +1.15 dB | **−0.08** / −1.25 dB | 0.87 |
| 100 % of song | +1.29 / +1.11 dB | — | 0.96 |
| 50 % of song | not detected | untouched | — |

**Known limitation.** Detection still requires persistence ≥ 0.6 over the whole track, so a resonance present in < 60 % of it (e.g. only in the chorus) is not detected. Regional detection (e.g. ≥ N consecutive segments) is the next improvement and must be re-validated for false positives on clean music (currently 0/12).

**Tests:** `tests/test_antidote_v2.py::test_local_correction_only_where_resonance_present` (coverage 0.5–0.95; clean region within ±0.5 dB locally vs < −1 dB globally; resonance region residual < 2.5 dB). The correction-filter test now also checks `time_coverage`.

## 18. Tape stage calibrated operating level — `tape_ref_peak_dbfs` (default **None** = legacy)

**Problem (measured on 8 real tracks).** The tape stage's nonlinear residual on music (= tape(x) − its linear small-signal response, i.e. intermodulation + harmonics; measured with `tape(εx)/ε` as the linear reference) is −30…−38 dB (1.3–3 %) and is set by the source level, not by any PHARMAKON setting: each −6 dB of input → ≈ −10 dB residual. The worst case is the acoustic guitar track (Neon waltz, peak 0.1 dBFS: −30 dB, 3 %) — exactly the material where dirt is most audible.

**First attempt rejected by measurement.** Aligning the mix to a reference *loudness* before the saturator (`tape_ref_lufs`, kept as an option) widened the track-to-track spread of distortion from 7.8 to ~11 dB: the saturator reacts to instantaneous amplitude, and high-crest material gets its peaks pushed further into saturation.

**Fix.** Align a robust *peak* — the 99.9th percentile of `max(|L|,|R|)` — to `tape_ref_peak_dbfs` before the saturator and restore the gain after it (like aligning a tape machine to 0 VU). Gain clipped to −24…+12 dB. With the parameter absent the stage is bit-identical to before (asserted).

**Sweep (8 tracks, `bench/results/tape_ref_peak_sweep.json`; LUFS sweep: `tape_ref_sweep.json`):**

| Reference peak | Residual median [range] | Track-to-track spread | PLR median |
|---|---|---|---|
| none (current) | −35.5 [−37.8…−30.0] dB | 7.8 dB | 9.67 |
| −3 dBFS | −28.8 dB | 1.3 dB | 8.67 |
| −6 dBFS | −34.0 dB | 1.5 dB | 9.43 |
| −9 dBFS | −39.2 dB | 1.6 dB | 9.89 |
| **−12 dBFS** | **−44.2 [−44.5…−43.1] dB** | **1.4 dB** | **10.16** |

At −12 dBFS **every** track has less distortion than the best track today (worst −43.1 vs best −37.8 dB) **and** more dynamics (PLR higher on 8/8) — strict improvement on both defects (Pareto). The amount of saturation is now controlled by `tape_drive`, not by the source.

**Full bench (`bench/results/20261109_tape_pk12/`), V2_CAL_DEEMPH vs + `tape_ref_peak_dbfs=-12`:** chain THD −33.2 → −43.2 dB, SMPTE IMD −24.2 → −33.3 dB, aliasing −59.4 → −66.8 dB, PLR median 9.52 → 10.37, crest 11.19 → 12.80 dB; resonances, sharpness (+0.01), presence/brilliance/air unchanged (air +0.34 → +0.24 dB).

**Tests:** `tests/test_tape_calibration.py` (uncalibrated: +9 dB input → > 8 dB more distortion; calibrated: < 0.5 dB difference; parameter off → bit-identical; on → output level restored within 1 dB).

**Proposed default chain (owner decision):** `antidote_v2`, `deharsh_calibrated`, `tape_deemphasis`, `tape_ref_peak_dbfs = -12`.

## 19. Clean Chain 3.2 is the default sound; Classic 3.1 switch

**Owner decision (2026-11-09):** enable the new chain by default and keep a switch back to the previous sound.

**Engine.** `resolve_sound_profile(params)` (placed before `resolve_sub_sync_config`, so `apply_tape_warmth_v2` is still on line 130) returns `('Clean Chain 3.2', CLEAN_CHAIN_DEFAULTS)` or, with `classic_31: True`, `('Classic 3.1', CLASSIC_31_DEFAULTS)`:

| Setting | Clean Chain 3.2 | Classic 3.1 |
|---|---|---|
| `antidote_v2` / `antidote_v2_local` | True / True | False |
| `deharsh_calibrated` | True | False |
| `tape_deemphasis` | True | False |
| `tape_ref_peak_dbfs` | −12.0 | None |

Any parameter given explicitly overrides the profile. `process_audio_array` and the stems vocal de-harsher read the profile instead of raw `params.get(...)`. Metrics: `sound_profile`, `sound_profile_settings` (full mix), `sound_profile` (stems). Presets (`suno`, `udio`, `club`, `audiophile`) get the Clean Chain too unless `classic_31` is set.

**GUI.** New strip under "Match Input Loudness": `SOUND PROFILE // CLEAN CHAIN` with `CLEAN 3.2` / `CLASSIC 3.1` buttons (`setClassicSound`, state `classicSound`), sent as `classic_31` with both processing requests. Server passes params through unchanged. Checked in a browser: toggle switches state, badge, LED and description; no console errors.

**Tests.** The Stage-1 SHA-256 regression tests (`test_dsp_bit_identical_regression`, `test_diagnostic_logging_emits_telemetry_without_changing_audio`) now run with `classic_31: True`: they guarantee that **Classic 3.1 is bit-identical to the 3.1 baseline** — the hashes in `baseline.json` are unchanged. New: `test_sound_profile_defaults_and_override`, `test_default_equals_explicit_clean_chain`. Tests that compared against "the default = v1" now ask for `classic_31` explicitly. Bench variants: `CLASSIC_31` vs `CLEAN_32_DEFAULT`.

**Docs.** README (EN) and `articles_ru/README_RU.md` have a new section "Clean Chain — the default sound profile": goal (no fatigue from measurable defects, taste kept), the defects-vs-taste rule (Pareto), measured comparison on 14 AI tracks, the Classic switch. Wording deliberately makes no medical claims.

**Not done (release process, owner decision):** `VERSION.json`, the README title ("PHARMAKON 3.0"), auto-updater release metadata and the portable build still say 3.0/3.1; the profile is labelled "3.2". Bumping the version and building/publishing a release is a separate step.

## 20. Antidote v2 runs in both workflow modes

In 3.1 the automatic resonance detection ran only in `pharmakon1` (Auto Antidote), because in `pharmakon2` (Studio Pro Rack) the user sets the de-harsh frequency manually. Antidote v2 is not a tonal control but a defect remover (persistent resonant colouring, applied only where present, never on notes), so it now runs in **both** modes whenever the profile enables it. The manual de-harsh knobs in Pro Rack keep working on top of it. Classic 3.1 is unchanged: no automatic detection in `pharmakon2`, v1 detection in `pharmakon1`.

GUI note: in `pharmakon1` the whole Pro Rack section (including the Sound Profile and Match Input Loudness strips) is hidden; the request still carries `classic_31: false`, so the Auto mode always uses the full Clean Chain.

Test: `tests/test_antidote_v2.py::test_antidote_v2_runs_in_both_workflow_modes`.

## 21. Measured Spectral Diagnosis — console panels and Mastering Certificate show only measured facts

**Problem.** The console's "SOURCE DEFECT DIAGNOSIS" panel was static HTML (clipping at 0.00 dBFS, 5 kHz resonance, sub-bass phase cancellation, infrasonic mud — shown for every track). The treatment panel mixed the Antidote v2 frequency with an unrelated de-harsh band number. HUD tags ("CLIPPING RISK: HIGH", "TRUE-PEAK: -0.3 dBFS"), evaluative captions ("Healthy Punch", "Mono Lock", "Warm Density Boost") and invented fallback numbers (PLR 11.2, crest 10.8/12.0, correlation +0.84/+0.99, 5000 Hz) appeared in the console, the in-app certificate modal, the PNG export and the HTML certificate. The HTML certificate always printed "VERIFIED STREAMING COMPLIANT • ZERO INTER-SAMPLE PEAKS". The modal also added a second hidden +22 dB to parts of the delta curve.

**Fix.** `build_spectral_diagnosis(orig, proc, sr, metrics, params, extra)` (engine, after `calc_audio_metrics`) is the single source of truth, stored as `metrics['diagnosis']` for full-mix and stems modes:
- **Source (measured on the original):** true-peak + clipped plateaus (≥ 3 consecutive full-scale samples); persistent resonances (detector v2: frequency, height, share of track); low-band L/R correlation; energy below the sub cutoff; dynamics (info).
- **Treatment (before → after):** true-peak vs ceiling; loudness; Antidote v2 corrections (frequency, cut, Q, time coverage) **plus the strongest resonance remaining after processing**; de-harsh band change relative to overall level (signed); low-end correlation; infrasonic energy after; tape operating-level gain; tonal balance per band relative to overall level; dynamics.
- **Seal:** only statements true for this file (ceiling held/exceeded with the measured value; −1 dBTP streaming recommendation met or not; meter verification).
- Status per line: issue / warn / ok / info, with thresholds as named constants (`DIAG_*`) and their rationale in the code.

Console (`renderDiagnosis`, HUD tags), in-app certificate modal (new diagnosis block, Antidote v2 tile), PNG export tiles and the HTML certificate (diagnosis block, Antidote v2 tile, band summary relative to overall level, real export format, measured seal) all render from it. No invented fallbacks: missing values show "—".

**Tests:** `tests/test_spectral_diagnosis.py` — clean music → no resonance / clipping reported, "no correction needed"; injected resonance → reported at its frequency, corrected, nothing ≥ 3 dB remains; hard-clipped source → "clipped"; anti-phase low end → issue, and after processing the honest status (anti-phase content above the 120 Hz crossover stays stereo → warn, not ok); certificate contains none of the canned phrases and does contain the measured true-peak. Browser check: real Bronze Psalter diagnosis renders in the console lists and HUD with no console errors.

## 22. Metric tiles: removed from the main page, kept in the Mastering Report

The main console page duplicated the measured diagnosis with 8 metric tiles and a "4-band master profile" row that used different definitions (absolute band change incl. the overall level change vs relative in the diagnosis; de-harsh number at ~5 kHz shown next to the Antidote v2 frequency). The main page now shows only the diagnosis under the oscilloscopes (JS updates of the old tile ids are null-guarded).

The Mastering Report keeps compact tiles, made consistent with the diagnosis:
- "4X TRUE-PEAK CEILING … dBFS" → "4X TRUE-PEAK (MEASURED) … dBTP", raw value in dBTP (HTML certificate, in-app modal, PNG card).
- Band row → "BAND BALANCE (VS OVERALL LEVEL)": sub 20-120, body 120-2k, presence 2-5k, brilliance 5-10k, air 10-20k — the same numbers as the diagnosis (`tonal_balance_rel_db`).
- Stereo width caption → "Side level of highs vs raw (measured)"; "24-bit Lossless WAV" → actual container info.
Browser check: modal opens without errors; no canned captions remain.

## 23. Mastering Report usability: button state, full PNG certificate, band row

- **Button looked unresponsive.** After a page reload (or while a track is processing, ~9 s) `openMasteringReportModal()` had no result to show and only wrote a status line at the top of the page, so clicks looked lost. Measured in a browser: with a result the modal opens in 1–4 ms on every click and nothing covers the button. Fix: `setReportButtonState('none' | 'busy' | 'ready')` — dimmed/dashed and labelled "process a track first" / "REPORT: PROCESSING…" until a result exists, a nudge animation on click, normal once ready.
- **PNG card was the 2.0 design:** "PHARMAKON 2.0 PRO", fixed serial "PH-2026-CERT", fixed seal "VERIFIED STREAMING COMPLIANT • ZERO INTER-SAMPLE PEAKS (-0.3 dBFS)", six tiles only with truncated text. Now a full measured certificate (1400 px wide, height fits content): 3.2 header, serial derived from track + date with local timestamp, tiles in 2 × 3 with wrapped captions, the measured diagnosis in two columns, band balance relative to overall level, spectrum, and the seal lines from `diagnosis.seal`. Verified by rendering the real Bronze Psalter result to a PNG.
- **Modal band row overlapped** ("-0.4BRILLIANCE"): flex-wrap with gaps, title on its own line; verified no overlaps.
- Incident note: one patch script truncated `app.js` (file opened for writing before an encoding error); restored from the last commit, nothing lost. Patch scripts now encode before writing.

## 24. Main page shows one-line summaries; PNG certificate includes the Track Intelligence Map; honest kick-bass correlation

- **Main page:** the full diagnosis lists moved to the Mastering Report. Under each oscilloscope there is now one clickable line (`diagSourceSummary`: number of defects/warnings and their names; `diagTreatSummary`: profile, output true-peak, Antidote v2 result) that opens the report.
- **PNG certificate:** adds the Track Intelligence Map (proportional sections bar + one card per section: crest, peak/RMS, kicks/phase, kick-bass correlation, policy verdict), between the diagnosis and the band balance; canvas height grows with the number of sections. Verified on a 12-section render (Il Fuoco del Cuore).
- **Kick-bass "SUB-CORRELATION" was a constant 1.00 for every full-mix track:** without stems `build_provisional_track_map` used the same signal for "drums" and "bass" and correlated it with itself. Now it is `None` unless separate drum and bass signals are given (stems mode: real values, e.g. 0.26 / 0.27 on Bronze Psalter stems). Console modal, inspector, PNG and HTML certificate show "— (stems only)". Tests: `tests/test_track_map_honesty.py`.

## 25. Track Map tempo v2: multi-band onsets + metrical octave decision (ground-truth validated)

- **Problem (measured):** `detect_bpm_and_grid` looked only at the sub band (< 120 Hz) and searched 90–170 BPM. On 22 synthetic tracks with known tempo (`bench/validate_tempo.py`: four-on-floor, half-time, hip-hop, trap, DnB, 3/4, kick-less ballad, rock 8ths) it scored **acc1 32 % / acc2 36 %**. Errors were not only octaves but 4:3 / 3:2 ones (hip-hop 88 → 117, DnB 174 → 117, rock 110 → 165). The bass line drove the estimate (real example: "Oblomki" 100.5 BPM; its drums in three bands agree on 150/75).
- **Fix (`detect_tempo`):** log-spectral flux in 4 bands (kick / body / snare / hats), comb over beat multiples to find the tempo family, then the octave: climb from the slowest level until the off-beats stop carrying kick/body/snare hits (off-beat/beat ratio < 0.6 in every band; hats excluded). Period refined over 16 beat multiples (±0.1 BPM test still passes). Range 50–210 BPM.
- **Result:** acc1 **86 %**, acc2 **100 %**, and every octave miss is shown as the alternative tempo (`tempo_alt_bpm`, UI: "70.0 BPM (or 140.0)"). Remaining misses are half-time styles (trap / half-time at 140 read as 70), where people also count either. Held-out run (32 random tempos): acc1 75 %, acc2 100 %.
- **Grid:** a reading below 80 BPM uses the doubled tempo for the phrase grid (same grid lines, finer). The displayed tempo stays the measured one.
- **Real tracks** (no labels, consistency only): Stromae "Alors On Danse" 119.99 (known 120); the club tracks agree with 3.1 (134.0 / 131.1 / 150.1).
- New fields in the map: `tempo_alt_bpm`, `tempo_octave_confident`, `tempo_pulse_clarity`. Test: `tests/test_tempo_ground_truth.py`.

## 26. Updater: live-patched 3.0 clients no longer get HTTP 500 on "Check update"

3.0.x frozen builds keep their own `auto_updater` (it is not a patch file) and load the 3.2 `server.py` from `_live_patches`. The 3.2 server called `check_online_updates` / `install_verified_update`, which 3.0 does not have, so the button returned 500. Verified on a copy of the 3.0.0 build: it auto-updated to 3.2 from master and processed a track correctly; only the manual check failed. Now it falls back to the cached status, and install asks for the full 3.2 download. **Note:** the 3.0 updater applies patches without a signature check; only the full 3.2 build closes that. `gui/server.py` changed, so VERSION.json patch hashes and the signature must be re-done at release.

### 25b. Meter conflict (4-division vs 3-division of the same bar)

- **Real case:** "Move! Move! Move!" (user's track). The 3.2.0 detector read **187 BPM**, and the first tempo v2 read **140**. Kick, body and snare bands put the beat at **93.75**. The bar (2.56 s) splits into 4 (94) or 3/6 (70/140), and triplet hats and shakers fed the summed signal toward 70/140.
- **Fix:** the beat family comes from the summed signal (hats excluded). Each drum band (kick / body / snare) then scores the competing families by plain beat-lag autocorrelation, normalised per band. A rival family overrides only when ≥ 2 drum bands pick it and it scores higher. A rival that is an integer grouping of the beat (a 3/4 bar, a half-note) never overrides. A close rival (≥ 85 % of the score) is shown as the alternative tempo. "Move" → **93.4 BPM (or 70)**.
- **Benchmark:** a triplet-shuffle style was added (3 tempos). Main set: acc1 **88 %**, acc2 **100 %**, shown **100 %** (n = 25). Held-out (36 random tempos): acc1 72 %, acc2 94 %, shown 97 %. Known miss: a shuffle at 88.3 reads as 132.5 with alt 106. Not tuned further, to avoid fitting the synthetic set.

## 27. Track Map sections v2: downbeat grid, measured boundaries, measured labels

- **Problem (measured):** sections came from a fixed 8/16-bar grid counted from t = 0, and the labels came from the section's position ("the 2nd section is a DROP"). On a ground-truth set (`bench/validate_sections.py`: 4 EDM and 3 song arrangements, some with a pickup before the first downbeat), 3.1 scored boundary F **0.22** (±0.5 s), 0.43 (±1 bar) and **27 %** correct labels. Held-out random arrangements: 0.29 / 24 %. Any pickup shifted every boundary.
- **Fix (`detect_sections`):**
  1. Bar grid anchored to the music: beat phase from the drum onsets; downbeat = the beat where spectral change and low-end onsets concentrate.
  2. Per-bar features: 5 band levels, 4 onset densities, chroma.
  3. Boundary novelty = max(Foote checkerboard on the bar self-similarity matrix, 4-bar block-mean change), peaks with prominence ≥ 0.12 (middle of a flat 0.08–0.12 plateau), ≥ 4 bars apart.
  4. Absolute gate: a band changes ≥ 1.5 dB, or onset density ≥ 25 %, or 4-bar chroma cosine < 0.9. Without it a static track gets noise boundaries.
  5. Breakdown edges measured directly: ≥ 4 bars with the 20–100 Hz level 8 dB below the track median.
- **Labels from measurements:**
  - *Energy vocabulary* (four-on-the-floor ratio ≥ 0.65). It uses the low end vs the time-weighted median, sustained bass between kicks (20th-percentile sub level), level vs the loudest section, and level rise. The roles are INTRO / GROOVE / BREAKDOWN / BUILDUP / DROP / OUTRO.
  - *Song vocabulary.* Repetition clusters need the same chroma (cos ≥ 0.97) and the same band levels (≤ 2.5 dB RMS). A pre-chorus is a cluster sandwiched verse → P → chorus. The chorus is the end of the repeated chain.
  - If no repeated chorus is measured, the map falls back to energy roles and says so (`structure_note`); it does not guess verse/chorus. The generic "SECTION" label is gone.
- **Result:** main set boundary F **0.97** (±0.5 s), 0.99 (±1 bar), labels **99 %**. Held-out (20 random arrangements, never used for tuning): **0.91** / 0.94 / **92 %**.
  - Known limits: a 4-bar pre-chorus right after a 16-bar verse can merge into it. Song-mode thresholds were tuned on synthetic songs only. On real songs, chroma similarity of true repeats is ~0.9, so repetition is often not found; the map then falls back to energy roles. Real hand-labelled songs are needed before relaxing it, because relaxing it on synthetic data dropped labels to 72 %.
- **Edge behaviour (measured, kept as is):**
  - The block novelty near the end compares a 4-bar window with a shorter one. Its rise towards the last bar line raises the right-hand peak base, which suppresses false boundaries inside long outros.
  - It also hides a real change 4 bars before the end in a short song (`test_pop_song_ssm_structure`, now a strict xfail with the reason).
  - Three edge treatments were tried: zeroing the last line, full windows only, and merging a partial last bar. All three lowered the benchmark (main 0.97 → 0.86–0.92 boundary F; held-out labels 92 % → 81–84 %), so none was kept.
  - The trailing-bar onset density is now computed from the real partial bar (it used to be 0.0 by accident). Tracks shorter than 8 bars are one "CLIP" (this removed 20 empty-slice warnings).
- **Each section now carries** `boundary_strength` (the novelty at its start) and `evidence` (level vs loudest, low end vs median, bass present, level rise, repeat group). The UI shows them on the cards and in the PNG.
- **UI:** narrow blocks show 3-letter tags (INT/GRV/BRK/BLD/DRP/OUT/VRS/PRE/CHR/BRG) with the full name in the tooltip. The legend lists only the tags present. Time labels are dropped instead of cut mid-word. The title is 3.2.
- **Tests:** `tests/test_sections_ground_truth.py`. `tests/test_genre_track_map.py` was updated:
  - the techno test signal is one 3-minute groove, so the map must NOT invent an INTRO / DROP / BREAKDOWN (3.1 reported 9 sectors);
  - the pop test now checks that the choruses are where the map says CHORUS.

## 28. Kick counting in the Track Map (full mix)

- **Problem (measured):** per-section "kicks" were peaks of the |< 100 Hz| envelope at least 0.2 s apart, so bass notes counted as kicks and the time was the envelope peak, not the attack. Real example: "Groove 4" of Club Impact showed 326 kicks in 83 s at 131 BPM (≈ 180 beats). On ground truth (`bench/validate_kicks.py`, every kick sample known) 3.1 scored **F 0.16** (±30 ms) and counted **2.25×** the true number.
- **Fix (`detect_kick_onsets`):**
  - A kick is an ≥ 8 dB rise of the 40–200 Hz level within 20 ms that reaches within 15 dB of the track's loud low end.
  - One kick can show two rises (its pitch sweep beats against the bass note), so rises within 150 ms are one kick.
  - The onset is where the level first reaches peak − 10 dB. Zero-phase filtering pre-rings, so "first rise above the floor" came 35–90 ms early.
- **Result:** synthetic **F 0.98**, count ×1.03; held-out F 0.99, ×1.01.
- **Real music**, against the kicks of the isolated drum stem (Gravity / Bronze Psalter / Vector Pulse, ±60 ms): **0.70 / 0.54 / 0.36**; 3.1 scored 0.04 / 0.38 / 0.36.
  - A lower rise threshold helps dense real mixes and hurts clean ones; the real-music mean is flat (0.53–0.55 for 4–8 dB), so 8 dB is kept.
  - In a dense full mix the count stays an **estimate**: the map sets `kicks_source = "mix_estimate"` and the UI, PNG and HTML label it "KICKS (EST.)". With a drum stem the count comes from the stem.
- **Tried and rejected:** a pitch-sweep test (zero-crossing frequency of the first 20 ms vs 40–80 ms; kicks 1.6–2.5×, bass ≈ 1.1×). On real mixes it removed true kicks: recall 0.68 / 0.13 / 0.16.
- **Genre family** now comes from the same measurement as the section vocabulary: low-end onset evenness over the 4 beat positions (≥ 0.65 = four-on-the-floor). The 3.1 rule used the kick count, which a sustained bass under the kick can hide (the static-techno test).
