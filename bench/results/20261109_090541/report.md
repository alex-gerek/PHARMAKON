# PHARMAKON Metrics Bench — 2026-11-09T09:05:41

Excerpt 60 s per track; all versions loudness-matched (attenuation only) before measuring.
Sharpness is an approximate Zwicker/Fastl model with DIN 45692 weighting (calibrated to 1 acum), not ISO 532-1 certified.

## Draft targets

| Metric | Rule | Meaning |
|---|---|---|
| `resonance_max_db` | <= 3.0 | no narrow 2-8 kHz peak > 3 dB above surroundings (metallic / AI whistle) |
| `d_sharpness_acum` | <= 0.0 | not sharper than the original (fatigue) |
| `d_band_presence_db` | range (-1.5, 0.5) | 2-5 kHz share: tame, but not dull |
| `d_band_brilliance_db` | range (-1.5, 1.0) | 5-10 kHz share |
| `d_tilt_db_per_oct` | range (-0.5, 0.5) | overall tonal tilt preserved |
| `d_presence_flux_db` | <= 0.0 | harsh bursts not increased |
| `plr_db` | >= 8.0 | dynamics not squashed |

## Pass rate per variant

| Variant | `resonance_max_db` | `d_sharpness_acum` | `d_band_presence_db` | `d_band_brilliance_db` | `d_tilt_db_per_oct` | `d_presence_flux_db` | `plr_db` |
|---|---|---|---|---|---|---|---|
| P31_DEFAULT | 0/6 | 0/6 | 2/6 | 2/6 | 6/6 | 5/6 | 6/6 |
| DEHARSH_CAL | 0/6 | 0/6 | 2/6 | 0/6 | 6/6 | 6/6 | 6/6 |
| DEHARSH_CAL_NO_AIR | 0/6 | 0/6 | 2/6 | 0/6 | 6/6 | 6/6 | 6/6 |

## Bronze_Psalter_Demo.wav (matched to -11.85 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | DEHARSH_CAL | DEHARSH_CAL_NO_AIR |
|---|---|---|---|---|
| resonance_max_db | +8.74 | +8.67 (-0.07) | +8.67 (-0.07) | +8.67 (-0.07) |
| resonance_hz | 2094 | 2094 | 2094 | 2094 |
| sharpness_acum | +1.51 | +1.57 (+0.06) | +1.58 (+0.07) | +1.58 (+0.07) |
| band_presence_db | -19.06 | -18.26 (+0.80) | -18.24 (+0.82) | -18.24 (+0.82) |
| band_brilliance_db | -24.27 | -23.23 (+1.04) | -22.77 (+1.50) | -22.77 (+1.50) |
| band_air_db | -26.76 | -24.92 (+1.84) | -24.93 (+1.83) | -24.97 (+1.79) |
| tilt_db_per_oct | -2.92 | -2.80 (+0.12) | -2.80 (+0.12) | -2.80 (+0.12) |
| presence_flux_db | +11.39 | +11.21 (-0.18) | +11.21 (-0.18) | +11.21 (-0.18) |
| crest_db | +12.21 | +10.80 (-1.41) | +10.89 (-1.32) | +10.90 (-1.31) |
| plr_db | +11.04 | +9.37 (-1.67) | +9.46 (-1.58) | +9.47 (-1.57) |
| side_ratio_db | -7.30 | -7.44 (-0.14) | -7.44 (-0.14) | -7.44 (-0.14) |

## Il Fuoco del Cuore.wav (matched to -14.64 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | DEHARSH_CAL | DEHARSH_CAL_NO_AIR |
|---|---|---|---|---|
| resonance_max_db | +6.93 | +6.98 (+0.05) | +6.98 (+0.05) | +6.98 (+0.05) |
| resonance_hz | 2118 | 2118 | 2118 | 2118 |
| sharpness_acum | +1.71 | +1.76 (+0.06) | +1.77 (+0.06) | +1.76 (+0.06) |
| band_presence_db | -7.11 | -6.76 (+0.35) | -6.67 (+0.44) | -6.67 (+0.44) |
| band_brilliance_db | -16.82 | -15.63 (+1.19) | -15.65 (+1.17) | -15.65 (+1.17) |
| band_air_db | -23.04 | -21.64 (+1.40) | -21.67 (+1.37) | -21.71 (+1.33) |
| tilt_db_per_oct | +1.05 | +1.16 (+0.11) | +1.16 (+0.11) | +1.16 (+0.11) |
| presence_flux_db | +5.97 | +5.90 (-0.07) | +5.73 (-0.24) | +5.73 (-0.24) |
| crest_db | +13.80 | +13.20 (-0.60) | +13.24 (-0.56) | +13.24 (-0.56) |
| plr_db | +10.25 | +9.44 (-0.81) | +9.45 (-0.80) | +9.45 (-0.80) |
| side_ratio_db | -6.94 | -6.41 (+0.53) | -6.39 (+0.55) | -6.39 (+0.55) |

## Miami Summer.wav (matched to -14.9 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | DEHARSH_CAL | DEHARSH_CAL_NO_AIR |
|---|---|---|---|---|
| resonance_max_db | +7.11 | +7.11 (+0.00) | +7.09 (-0.02) | +7.09 (-0.02) |
| resonance_hz | 2792 | 2792 | 2792 | 2792 |
| sharpness_acum | +2.00 | +2.08 (+0.07) | +2.08 (+0.07) | +2.08 (+0.07) |
| band_presence_db | -8.72 | -8.80 (-0.08) | -8.31 (+0.41) | -8.31 (+0.41) |
| band_brilliance_db | -12.53 | -11.27 (+1.26) | -11.35 (+1.18) | -11.35 (+1.18) |
| band_air_db | -16.66 | -15.19 (+1.47) | -15.27 (+1.39) | -15.31 (+1.35) |
| tilt_db_per_oct | +0.14 | +0.26 (+0.12) | +0.26 (+0.12) | +0.26 (+0.12) |
| presence_flux_db | +5.26 | +5.37 (+0.11) | +5.01 (-0.25) | +5.01 (-0.25) |
| crest_db | +13.44 | +12.92 (-0.52) | +12.91 (-0.53) | +12.92 (-0.52) |
| plr_db | +10.31 | +9.61 (-0.70) | +9.53 (-0.78) | +9.53 (-0.78) |
| side_ratio_db | -12.21 | -11.11 (+1.10) | -11.10 (+1.11) | -11.10 (+1.11) |

## Cobalt Lullaby.wav (matched to -14.04 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | DEHARSH_CAL | DEHARSH_CAL_NO_AIR |
|---|---|---|---|---|
| resonance_max_db | +6.69 | +6.65 (-0.04) | +6.65 (-0.04) | +6.65 (-0.04) |
| resonance_hz | 2088 | 2088 | 2088 | 2088 |
| sharpness_acum | +1.55 | +1.60 (+0.05) | +1.62 (+0.07) | +1.62 (+0.07) |
| band_presence_db | -20.84 | -19.95 (+0.89) | -19.96 (+0.88) | -19.96 (+0.88) |
| band_brilliance_db | -24.47 | -23.87 (+0.60) | -23.00 (+1.47) | -23.00 (+1.47) |
| band_air_db | -27.28 | -25.45 (+1.83) | -25.45 (+1.83) | -25.49 (+1.79) |
| tilt_db_per_oct | -3.65 | -3.55 (+0.10) | -3.55 (+0.10) | -3.55 (+0.10) |
| presence_flux_db | +16.93 | +16.81 (-0.12) | +16.79 (-0.14) | +16.79 (-0.14) |
| crest_db | +9.35 | +9.59 (+0.24) | +9.60 (+0.25) | +9.60 (+0.25) |
| plr_db | +8.90 | +8.97 (+0.07) | +8.98 (+0.08) | +8.98 (+0.08) |
| side_ratio_db | -13.13 | -12.14 (+0.99) | -12.13 (+1.00) | -12.13 (+1.00) |

## Bronze Psalter (1).wav (matched to -12.57 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | DEHARSH_CAL | DEHARSH_CAL_NO_AIR |
|---|---|---|---|---|
| resonance_max_db | +8.33 | +8.32 (-0.01) | +8.32 (-0.01) | +8.32 (-0.01) |
| resonance_hz | 2094 | 2094 | 2094 | 2094 |
| sharpness_acum | +1.47 | +1.53 (+0.06) | +1.54 (+0.06) | +1.54 (+0.06) |
| band_presence_db | -19.28 | -18.48 (+0.80) | -18.46 (+0.82) | -18.46 (+0.82) |
| band_brilliance_db | -24.73 | -23.77 (+0.96) | -23.25 (+1.48) | -23.25 (+1.48) |
| band_air_db | -27.21 | -25.38 (+1.83) | -25.38 (+1.83) | -25.42 (+1.79) |
| tilt_db_per_oct | -2.98 | -2.86 (+0.12) | -2.86 (+0.12) | -2.86 (+0.12) |
| presence_flux_db | +10.83 | +10.78 (-0.05) | +10.78 (-0.05) | +10.78 (-0.05) |
| crest_db | +13.42 | +12.12 (-1.30) | +12.05 (-1.37) | +12.06 (-1.36) |
| plr_db | +12.10 | +10.59 (-1.51) | +10.53 (-1.57) | +10.53 (-1.57) |
| side_ratio_db | -8.00 | -7.39 (+0.61) | -7.39 (+0.61) | -7.39 (+0.61) |

## !!!Round and Round.wav (matched to -14.2 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | DEHARSH_CAL | DEHARSH_CAL_NO_AIR |
|---|---|---|---|---|
| resonance_max_db | +3.69 | +3.75 (+0.06) | +3.73 (+0.04) | +3.73 (+0.04) |
| resonance_hz | 7718 | 7718 | 7718 | 7718 |
| sharpness_acum | +1.81 | +1.88 (+0.07) | +1.90 (+0.09) | +1.90 (+0.08) |
| band_presence_db | -17.99 | -16.94 (+1.05) | -16.95 (+1.04) | -16.95 (+1.04) |
| band_brilliance_db | -18.83 | -17.82 (+1.01) | -17.24 (+1.59) | -17.24 (+1.59) |
| band_air_db | -22.87 | -20.99 (+1.88) | -21.00 (+1.87) | -21.04 (+1.83) |
| tilt_db_per_oct | -3.48 | -3.35 (+0.13) | -3.35 (+0.13) | -3.35 (+0.13) |
| presence_flux_db | +11.71 | +11.26 (-0.45) | +11.16 (-0.55) | +11.16 (-0.55) |
| crest_db | +10.48 | +10.42 (-0.06) | +10.49 (+0.01) | +10.50 (+0.02) |
| plr_db | +9.64 | +9.34 (-0.30) | +9.38 (-0.26) | +9.38 (-0.26) |
| side_ratio_db | -17.44 | -16.21 (+1.23) | -16.21 (+1.23) | -16.21 (+1.23) |

## Chain distortion (test tones, -6 dBFS)

| Chain / stage | THD 1 kHz | SMPTE IMD | Aliasing (9 kHz) |
|---|---|---|---|
| P31_DEFAULT | -32.6 dB | -24.2 dB | -58.9 dB |
| DEHARSH_CAL | -32.6 dB | -24.2 dB | -58.9 dB |
| DEHARSH_CAL_NO_AIR | -32.6 dB | -24.2 dB | -61.0 dB |
| stage_tape_v2 | -32.6 dB | -24.2 dB | -61.0 dB |
| stage_air_exciter | -158.7 dB | -163.2 dB | -72.7 dB |
| stage_vocal_sat_4x | -32.8 dB | -23.9 dB | -63.0 dB |
| stage_bass_softclip_4x | -33.0 dB | -24.0 dB | -63.2 dB |
| stage_drum_softclip_4x | -30.8 dB | -21.8 dB | -61.0 dB |
| ref_softclip_1x_pre_fix | -30.8 dB | -21.8 dB | -30.8 dB |
