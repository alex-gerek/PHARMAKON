# PHARMAKON 3.3.1 — Kick in Drums, Honest Diagnosis

**Release date:** 2026-11-24

A small update on top of 3.3.0. Engineering record: [DEV_NOTE_MATH_AUDIT_FIXES.md](DEV_NOTE_MATH_AUDIT_FIXES.md), notes 44–45.

## Stems

- **Split-and-master: the kick leaves the Bass stem.** The own split kept most of the kick body (and 808 tails) in Bass.wav, so Drums scored worse than the unseparated mix. A kick gate on the detected hits and a second, finer hit / held-note pass now move it to Drums; Drums + Bass keep their sum, Vocals and Other are unchanged. Measured against Suno stems (SI-SDR): drums −2.85 → +3.49 dB and bass −2.33 → +0.86 dB on 10 tracks (both better on every track), −0.74 → +3.14 and −0.60 → +1.04 dB on 6 more, and +5.6 / +6.7 dB (drums), +3.6 / +1.9 dB (bass) on 2 held-out tracks. (note 44)
- **Known limit:** a whispered backing vocal can still land in Drums (noise without pitch).

## Diagnosis

- **No false "Infrasonic Energy" warning on bass-heavy tracks.** The check counted the 32-60 Hz sub-bass as infrasound. It now measures energy strictly below the cut-off; a PHARMAKON master that read −25.8 dB (warning) reads −39 dB (OK). (note 45)
- **No stale results during a run.** The previous track's SOURCE / TREATMENT lines and true-peak labels are cleared when processing starts. (note 45)

## Upgrade

Installed 3.x copies update through the built-in updater (signed manifest, Ed25519). Portable: download `PHARMAKON_v3.3.1_Windows_Portable.zip` from the release page and unzip.
