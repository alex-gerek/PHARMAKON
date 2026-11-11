# PHARMAKON 3.2.0 — Clean Chain

**Release date:** 2026-11-10

## The idea

PHARMAKON exists to make AI-generated music sound cleaner and easier to listen to, while it still sounds like itself. Version 3.2 is the result of a full mathematical audit of the engine. Every formula was tested on signals with a known correct answer, and every statement in the report now comes from a measurement of the actual file.

Everything the processing touches falls into one of two classes:

- **Defects:** things that were never part of the music, such as the metallic resonances a generator leaves behind, intermodulation dirt, digital aliasing and clicks. Our goal is to bring them down, and on our measurement bench a change is accepted only if no measured defect grows.
- **Taste:** brightness, tonal balance and density. That is the artist's decision, so it stays within a tight tolerance of the original.

Measurements tell us exactly what happened to the signal. Listening tells us whether the result is right.

Full story of the audit: [Who Put Plastic in My Music?](articles/07_who_put_plastic_in_my_music.md) ([on X](https://x.com/LexGerek/status/2120167917488676895)).

## What changed in sound: Clean Chain vs Classic 3.1

Measured on 12 tracks across different styles (techno, trance, pop, classical, acoustic guitar and more), all versions loudness-matched. Full-chain metrics come from 6 tracks; saturation was measured on 8 (2 tracks are in both sets).

| Measure | Classic 3.1 | Clean Chain 3.2 |
|---|---|---|
| Persistent AI resonances (6 tracks) | left in place on 4 of 6, +3.8…+6.5 dB | below the 3 dB threshold on all 6; fully gone on 5 |
| Added sharpness (acum) | +0.05…+0.07 on every track | −0.01…+0.01 |
| "Air" 10–20 kHz | +1.4…+1.9 dB | +0.2…+0.3 dB |
| Saturation distortion on music (8 tracks) | −30…−38 dB, set by the source | −43…−45 dB on every track |
| Chain intermodulation (SMPTE test signal) | −24 dB | −33 dB |
| Dynamics: crest factor vs. original | −1.4…+0.2 dB (median −0.6) | −0.2…+0.4 dB (median +0.1) |

- **The top end stops stinging.** 3.1 added about +1.5 dB of air to every track; 3.2 keeps the top close to the original.
- **Metallic AI resonances are removed only where they occur.** Auto Antidote v2 finds resonant colouring that persists through the track and cuts it only in the passages where it is present. Musical notes are left alone; the 3.1 detector could cut a note by 8–10 dB. It works in both modes, PHARMAKON 1 (Auto) and PHARMAKON 2 (Studio Pro Rack).
- **Cleaner dense passages and natural dynamics.** Saturation is calibrated to the track's own peak level, so its distortion no longer depends on how loud the source was rendered.
- Loudness targets, the true-peak ceiling, mono low end and Sub-Sync behave as before.

## Classic 3.1 switch

Prefer the previous, brighter sound? Console → **SOUND PROFILE → CLASSIC 3.1** (or `classic_31: true`). It reproduces 3.1 processing bit-for-bit.

## Track Intelligence Map, rebuilt

Every part of the map was checked against ground truth: arrangements where every beat, kick and section boundary is known exactly.

- **Tempo.** The beat is read from kick, body and snare onsets across several bands, and the octave is chosen by where the off-beats fall. Exact tempo went from 28 % to 88 % on a reference set of 25 known-tempo tracks in 9 styles. Where a tempo is genuinely ambiguous (half-time, triplet feel), the map shows the second reading, for example "93.4 BPM (or 70)". Precision is within 0.1 BPM.
- **Sections.** The bar grid is anchored to the first downbeat, so a pickup no longer shifts every boundary. Boundaries sit where the music measurably changes, and each section is named from what was measured; the generic "SECTION" label is gone. Boundary accuracy (within half a second) went from 0.22 to 0.97 and correct labels from 27 % to 99 %. On arrangements the method never saw during tuning: 0.91 and 92 %.
- **Kicks.** A kick is now a sharp low-end attack, not any low-end peak. On ground truth the F-score went from 0.16 to 0.98. In a dense full mix the count is labelled as an estimate; with a drum stem it comes from the stem.
- **Evidence for every section.** Cards in the report and in the PNG certificate show the boundary strength and the measured low end and level of each section.

## Honest reports

- The Spectral Diagnosis and the certificate are built only from measurements of the specific file. A defect is shown only if it was measured, and "fixed" only if the measurement after processing confirms it. Canned statements such as "Verified Streaming Compliant" are gone.
- The kick-to-bass correlation is reported only when separate drum and bass signals exist; it used to read 1.00 because the signal was compared with itself.

## Accuracy fixes

- **Loudness meter.** The K-weighting filter now matches ITU-R BS.1770-4 exactly and passes EBU Tech 3341 test cases 1–5 (±0.1 LU) at 44.1 and 48 kHz. The old filter was off by up to 0.41 dB and read the EBU reference 0.25 LU off. Reported LUFS values now read about 0.25 LU higher than in 3.0/3.1; A/B loudness matching was already consistent and is now exact.
- **De-harsher.** It compared amplitude with bandwidth instead of its square root and cut about 5.5 dB even on clean material; on pink noise the unwanted cut is now −0.2 dB.
- **Sub-Sync.** Fixed bass level dips around kicks in the Existing-Guard / fallback path and clicks on very dense kick patterns in Local Guard.
- **Stems mode.** Bass and drum saturation is now 4× oversampled: aliasing −31 dB → −61 dB.
- **Documentation.** The default −0.3 dBTP ceiling is no longer described as "EBU R128 compliant" (R128 requires −1.0 dBTP; choose −1.0 for broadcast and streaming delivery).

## Download, build and updates

- **Smaller download.** The portable build is about 79 MB instead of about 930 MB; it ships only the two demos the console offers.
- **Bundled demos work again.** In earlier portable builds both demos failed with "Target path not found".
- **Signed updates.** The update manifest is signed with Ed25519, and the hash of every file is checked against the exact bytes clients download from the release tag.
- **3.0 clients that update themselves** no longer get an error on "Check update", and they load the new Track Map engine.

## For developers

- Full engineering record with measurements and tests: `DEV_NOTE_MATH_AUDIT_FIXES.md`.
- Objective metrics bench and ground-truth validators: `bench/` (tempo, sections, kicks, resonance, Antidote).
- One-step portable build from a committed tree: `python tools/build_portable.py --version 3.2.0`.
- Release signing and the client-side check: `python tools/release_tool.py verify --pubkey <key> --remote`.
