# PHARMAKON 3.2.0 — Clean Chain

**Release date:** 2026-11-09

## The idea

Music should be pleasant to listen to for hours — in a club, in headphones, on a long drive. PHARMAKON 3.2 removes the *measurable* defects that make long listening tiring and leaves the author's sound alone.

Every change in this release follows one rule:

- **Defects** — things that were never part of the music (AI "metallic" resonances, intermodulation distortion, digital aliasing, clicks) — are only ever reduced, never increased. Less of every defect is better for every listener, whatever their personal sensitivity.
- **Taste** — brightness, tonal balance, density — stays within a small tolerance of the original.

## What you will hear (Clean Chain vs 3.1, measured on 14 AI tracks)

- **No more "glassy" top end.** 3.1 added +1.5…2 dB of "air" and up to +1.7 dB of brilliance to every track. 3.2 keeps the top end close to the original: cymbals, hi-hats and "s" sounds stop stinging.
- **"Metallic" AI resonances removed — only where they occur.** The new Auto Antidote v2 finds resonant colouring that persists through the track and cuts it only in the passages where it is present. It never touches musical notes (the 3.1 detector could cut a note by 8–10 dB).
- **Cleaner dense passages.** Saturation distortion on music drops from −30…−38 dB (it used to depend on how loud the source was rendered) to −44 dB on every track.
- **More natural dynamics.** Crest factor +1.3 dB on average: kicks and plucked strings breathe more.
- Loudness, the True-Peak ceiling, mono low end and Sub-Sync are unchanged.

## Classic 3.1 switch

Prefer the previous, brighter sound? Console → **SOUND PROFILE → CLASSIC 3.1** (or `classic_31: true`). It reproduces 3.1 processing bit-for-bit.

## Accuracy fixes

- **Loudness meter** now matches ITU-R BS.1770-4 exactly and is verified against EBU Tech 3341 test cases 1–5 (±0.1 LU) at 44.1 and 48 kHz. Reported LUFS values read ~0.25 LU higher than in 3.0/3.1; A/B loudness matching was already consistent and is now exact.
- **Sub-Sync:** fixed bass level dips around kicks in the Existing-Guard / fallback path and clicks on very dense kick patterns in Local Guard.
- **Track Intelligence Map:** tempo detection accurate to ~0.05 BPM (was up to 0.5 BPM; at 44.1 kHz all tempos read 0.23 % low).
- **Stems mode:** bass and drum saturation is now 4× oversampled (aliasing −31 dB → −61 dB).
- **Documentation:** the default −0.3 dBTP ceiling is no longer described as "EBU R128 compliant" (R128 requires −1.0 dBTP — choose −1.0 for broadcast and streaming delivery).

## For developers

Full engineering record with measurements and tests: `DEV_NOTE_MATH_AUDIT_FIXES.md`. Objective metrics bench and ground-truth validators: `bench/`.
