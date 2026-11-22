# PHARMAKON 3.3.0 — Measured Map, Honest Stems

**Release date:** 2026-11-22

Everything since 3.2.0 (2026-11-10). As in 3.2, every change was accepted on a measurement with a known right answer; the engineering record is in [DEV_NOTE_MATH_AUDIT_FIXES.md](DEV_NOTE_MATH_AUDIT_FIXES.md), notes 29–42. Short story of what we learned: [Two Mistakes Can Sound Right](articles/08_two_mistakes_can_sound_right.md) ([on X](https://x.com/LexGerek/status/2124566669762683097)).

## Sound

- **Precise true-peak pass (Clean Chain).** The limited output is re-measured at 16X and residual overs are corrected with smooth gain. On 18 loud masters the output stays 0.04 dB under the ceiling at 32X (3.1 limiter: up to +0.019 dB over, with a tanh guard firing on 17 of 18). Classic 3.1 keeps the 3.1 limiter bit-for-bit. (note 30)
- **Limiter memory.** The Clean Chain limiter needs about 1 GB for a 3.5 min track (was 2.3 GB; 4 min of loud noise 5.1 GB → 1.0 GB), same speed, output within 1–2 float32 LSB. (note 40)

## Stems

- **Suno stem folders work.** Stems mode used one file per keyword and silently dropped most of a Suno export (backing vocals, keys, synth, percussion, guitar). Every stem now goes to one of the 4 buses; a numbered Suno set is used as a whole; 4-stem folders behave as before. (note 37)
- **Split-and-master: the kick goes to Drums.** The own split sent everything below 130 Hz to Bass, kick included. Measured against Suno stems of 7 tracks (SI-SDR): drums −11.5 → −4.4 dB, bass −3.8 → −3.1 dB, better on 7 of 7; vocals and the rest about unchanged. (note 38)
- **Known limit, measured:** the own split's vocal stem is still mostly not voice (19 % of its energy) and the voice leaks into Other (16 %). The fix in research is a pitch-contour voice model. (notes 38, 41)

## Track Intelligence Map

- **Beat grid fitted to the beats** (Theil–Sen): no drift along the track; with a 0.1 % tempo error the 95th-percentile beat error falls from 102 ms to 1.5 ms. (note 31)
- **Grid on the beat, not 40 ms early** (onset-detector latency, derived from the analysis window). (note 33)
- **Downbeat not on the snare** (backbeat rule): right on 42 of 42 benchmark runs. (note 34)
- **Build-up boundaries on their own bar.** Held-out sections (20 tracks): boundary accuracy ±0.5 s 0.913 → 0.938, labels 0.918 → 0.921, no track worse than 3.2. (notes 35, 36)
- **Section player** in the Mastering Report and the GUI: play, pause, loop a section, A/B/C (master / original / removed delta). (note 32)

## Privacy and reliability

- Reports no longer contain local file paths; audio and the edited map are resolved next to the report on the server. (notes 32, 42)
- The report audio route serves the file of the report that asked for it, not the first file with that name anywhere in the project. (note 32)
- Live-patched 3.0 clients get the patched Track Map engine. (note 29)
- The test suite runs outside the author's machine (bit-exact hashes on the reference environment, measured fingerprints elsewhere; `pythonpath = .`; `requirements-dev.txt`). (note 39)
- One-step portable build: `python tools/build_portable.py --version 3.3.0`.

## Upgrade

Portable: download `PHARMAKON_v3.3.0_Windows_Portable.zip` from the release page and unzip. Installed 3.x copies update through the built-in updater (signed manifest, Ed25519).
