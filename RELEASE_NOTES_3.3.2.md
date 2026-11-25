# PHARMAKON 3.3.2 — Bass Notes Stay in Bass

**Release date:** 2026-11-25

A small update on top of 3.3.1. Engineering record: [DEV_NOTE_MATH_AUDIT_FIXES.md](DEV_NOTE_MATH_AUDIT_FIXES.md), note 46.

## Stems

- **Split-and-master: bass notes that start on a kick stay in the Bass stem.** The kick gate of 3.3.1 also took a bass note's harmonics when the note started on a hit. The bass pitch is now tracked on the Bass stem and the note is protected inside the gate, but only where it behaves like a bass note: an 808 or a tom (pitched, fast decay, falling pitch) still goes to Drums. Measured against Suno stems (SI-SDR, change vs 3.3.1): drums +0.24 dB and bass +0.41 dB on 10 tracks (better on every track), +0.18 / +0.39 dB on 6 more (all 6); on 2 held-out tracks drums +0.5 / +0.0 dB and bass +1.2 / +0.2 dB. Vocals and Other unchanged. (note 46)
- **Known limit:** spoken or whispered words (no pitch) can still land in Drums.

## Upgrade

Installed 3.x copies update through the built-in updater (signed manifest, Ed25519). Portable: download `PHARMAKON_v3.3.2_Windows_Portable.zip` from the release page and unzip.
