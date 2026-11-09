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
