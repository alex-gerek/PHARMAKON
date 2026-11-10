# PHARMAKON Metrics Bench — 2026-11-09T11:19:02

Excerpt 60 s per track; all versions loudness-matched (attenuation only) before measuring.
Sharpness is an approximate Zwicker/Fastl model with DIN 45692 weighting (calibrated to 1 acum), not ISO 532-1 certified.

## Draft targets

| Metric | Rule | Meaning |
|---|---|---|
| `res_v2_max_db` | <= 3.0 | no persistent resonant colouring > 3 dB in 2-9 kHz (metallic / plastic); detector v2 |
| `d_sharpness_acum` | <= 0.0 | not sharper than the original (fatigue) |
| `d_band_presence_db` | range (-1.5, 0.5) | 2-5 kHz share: tame, but not dull |
| `d_band_brilliance_db` | range (-1.5, 1.0) | 5-10 kHz share |
| `d_tilt_db_per_oct` | range (-0.5, 0.5) | overall tonal tilt preserved |
| `d_presence_flux_db` | <= 0.0 | harsh bursts not increased |
| `plr_db` | >= 8.0 | dynamics not squashed |

## Pass rate per variant

| Variant | `res_v2_max_db` | `d_sharpness_acum` | `d_band_presence_db` | `d_band_brilliance_db` | `d_tilt_db_per_oct` | `d_presence_flux_db` | `plr_db` |
|---|---|---|---|---|---|---|---|
| P31_DEFAULT | 2/6 | 0/6 | 2/6 | 2/6 | 6/6 | 5/6 | 6/6 |
| V2_CAL_DEEMPH | 6/6 | 1/6 | 6/6 | 6/6 | 6/6 | 2/6 | 6/6 |
| V2_CAL_DEEMPH_PK12 | 6/6 | 1/6 | 6/6 | 6/6 | 6/6 | 2/6 | 6/6 |

## Bronze_Psalter_Demo.wav (matched to -11.98 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | V2_CAL_DEEMPH | V2_CAL_DEEMPH_PK12 |
|---|---|---|---|---|
| res_v2_max_db | +3.98 | +4.94 (+0.96) | +2.19 (-1.79) | +0.00 (-3.98) |
| res_v2_hz | 2047 | 2062 | 7909 | — |
| res_v2_q | +11.20 | +11.40 | +16.10 | — |
| resonance_max_db | +8.74 | +8.67 (-0.07) | +7.99 (-0.75) | +7.98 (-0.76) |
| resonance_hz | 2094 | 2094 | 2094 | 2094 |
| sharpness_acum | +1.51 | +1.57 (+0.06) | +1.51 (-0.01) | +1.51 (-0.01) |
| band_presence_db | -19.06 | -18.26 (+0.80) | -19.69 (-0.63) | -19.69 (-0.63) |
| band_brilliance_db | -24.27 | -23.23 (+1.04) | -24.40 (-0.13) | -24.41 (-0.14) |
| band_air_db | -26.76 | -24.92 (+1.84) | -26.41 (+0.35) | -26.53 (+0.23) |
| tilt_db_per_oct | -2.92 | -2.80 (+0.12) | -3.06 (-0.14) | -3.06 (-0.14) |
| presence_flux_db | +11.39 | +11.21 (-0.18) | +11.50 (+0.11) | +11.54 (+0.15) |
| crest_db | +12.21 | +10.80 (-1.41) | +10.62 (-1.59) | +12.38 (+0.17) |
| plr_db | +11.04 | +9.37 (-1.67) | +9.28 (-1.76) | +11.08 (+0.04) |
| side_ratio_db | -7.30 | -7.44 (-0.14) | -7.50 (-0.20) | -7.58 (-0.28) |

## Il Fuoco del Cuore.wav (matched to -15.05 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | V2_CAL_DEEMPH | V2_CAL_DEEMPH_PK12 |
|---|---|---|---|---|
| res_v2_max_db | +6.41 | +6.53 (+0.12) | +0.00 (-6.41) | +0.00 (-6.41) |
| res_v2_hz | 2435 | 2435 | — | — |
| res_v2_q | +12.50 | +13.60 | — | — |
| resonance_max_db | +6.93 | +6.98 (+0.05) | +6.91 (-0.02) | +6.93 (+0.00) |
| resonance_hz | 2118 | 2118 | 4224 | 4224 |
| sharpness_acum | +1.71 | +1.76 (+0.06) | +1.71 (+0.00) | +1.71 (+0.00) |
| band_presence_db | -7.11 | -6.76 (+0.35) | -7.78 (-0.67) | -7.77 (-0.66) |
| band_brilliance_db | -16.82 | -15.63 (+1.19) | -16.65 (+0.17) | -16.67 (+0.15) |
| band_air_db | -23.04 | -21.64 (+1.40) | -22.79 (+0.25) | -22.81 (+0.23) |
| tilt_db_per_oct | +1.05 | +1.16 (+0.11) | +0.89 (-0.16) | +0.90 (-0.15) |
| presence_flux_db | +5.97 | +5.90 (-0.07) | +6.51 (+0.54) | +6.50 (+0.53) |
| crest_db | +13.80 | +13.20 (-0.60) | +13.38 (-0.42) | +13.96 (+0.16) |
| plr_db | +10.25 | +9.44 (-0.81) | +9.88 (-0.37) | +10.46 (+0.21) |
| side_ratio_db | -6.94 | -6.41 (+0.53) | -6.41 (+0.53) | -6.41 (+0.53) |

## Miami Summer.wav (matched to -15.4 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | V2_CAL_DEEMPH | V2_CAL_DEEMPH_PK12 |
|---|---|---|---|---|
| res_v2_max_db | +3.98 | +3.81 (-0.17) | +0.00 (-3.98) | +2.30 (-1.68) |
| res_v2_hz | 2435 | 3181 | — | 7967 |
| res_v2_q | +11.80 | +11.30 | — | +14.80 |
| resonance_max_db | +7.11 | +7.11 (+0.00) | +7.35 (+0.24) | +7.33 (+0.22) |
| resonance_hz | 2792 | 2792 | 2792 | 2792 |
| sharpness_acum | +2.00 | +2.08 (+0.07) | +2.01 (+0.01) | +2.01 (+0.01) |
| band_presence_db | -8.72 | -8.80 (-0.08) | -9.58 (-0.86) | -9.58 (-0.86) |
| band_brilliance_db | -12.53 | -11.27 (+1.26) | -12.38 (+0.15) | -12.38 (+0.15) |
| band_air_db | -16.66 | -15.19 (+1.47) | -16.39 (+0.27) | -16.41 (+0.25) |
| tilt_db_per_oct | +0.14 | +0.26 (+0.12) | +0.02 (-0.12) | +0.01 (-0.13) |
| presence_flux_db | +5.26 | +5.37 (+0.11) | +5.51 (+0.25) | +5.49 (+0.23) |
| crest_db | +13.44 | +12.92 (-0.52) | +12.83 (-0.61) | +13.33 (-0.11) |
| plr_db | +10.31 | +9.61 (-0.70) | +9.77 (-0.54) | +10.28 (-0.03) |
| side_ratio_db | -12.21 | -11.11 (+1.10) | -11.36 (+0.85) | -11.37 (+0.84) |

## Cobalt Lullaby.wav (matched to -14.11 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | V2_CAL_DEEMPH | V2_CAL_DEEMPH_PK12 |
|---|---|---|---|---|
| res_v2_max_db | +0.00 | +0.00 (+0.00) | +0.00 (+0.00) | +0.00 (+0.00) |
| res_v2_hz | — | — | — | — |
| res_v2_q | — | — | — | — |
| resonance_max_db | +6.69 | +6.65 (-0.04) | +6.65 (-0.04) | +6.68 (-0.01) |
| resonance_hz | 2088 | 2088 | 2088 | 2088 |
| sharpness_acum | +1.55 | +1.60 (+0.05) | +1.56 (+0.01) | +1.56 (+0.01) |
| band_presence_db | -20.84 | -19.95 (+0.89) | -20.67 (+0.17) | -20.63 (+0.21) |
| band_brilliance_db | -24.47 | -23.87 (+0.60) | -24.26 (+0.21) | -24.24 (+0.23) |
| band_air_db | -27.28 | -25.45 (+1.83) | -26.95 (+0.33) | -26.99 (+0.29) |
| tilt_db_per_oct | -3.65 | -3.55 (+0.10) | -3.65 (+0.00) | -3.64 (+0.01) |
| presence_flux_db | +16.93 | +16.81 (-0.12) | +16.81 (-0.12) | +16.85 (-0.08) |
| crest_db | +9.35 | +9.59 (+0.24) | +9.21 (-0.14) | +9.70 (+0.35) |
| plr_db | +8.90 | +8.97 (+0.07) | +8.66 (-0.24) | +9.18 (+0.28) |
| side_ratio_db | -13.13 | -12.14 (+0.99) | -12.20 (+0.93) | -12.19 (+0.94) |

## Bronze Psalter (1).wav (matched to -12.68 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | V2_CAL_DEEMPH | V2_CAL_DEEMPH_PK12 |
|---|---|---|---|---|
| res_v2_max_db | +4.32 | +4.31 (-0.01) | +0.00 (-4.32) | +0.00 (-4.32) |
| res_v2_hz | 2047 | 2047 | — | — |
| res_v2_q | +10.80 | +11.30 | — | — |
| resonance_max_db | +8.33 | +8.32 (-0.01) | +7.15 (-1.18) | +7.10 (-1.23) |
| resonance_hz | 2094 | 2094 | 2621 | 2621 |
| sharpness_acum | +1.47 | +1.53 (+0.06) | +1.48 (+0.01) | +1.48 (+0.00) |
| band_presence_db | -19.28 | -18.48 (+0.80) | -19.60 (-0.32) | -19.60 (-0.32) |
| band_brilliance_db | -24.73 | -23.77 (+0.96) | -24.55 (+0.18) | -24.56 (+0.17) |
| band_air_db | -27.21 | -25.38 (+1.83) | -26.86 (+0.35) | -26.98 (+0.23) |
| tilt_db_per_oct | -2.98 | -2.86 (+0.12) | -3.12 (-0.14) | -3.13 (-0.15) |
| presence_flux_db | +10.83 | +10.78 (-0.05) | +11.08 (+0.25) | +11.13 (+0.30) |
| crest_db | +13.42 | +12.12 (-1.30) | +11.76 (-1.66) | +13.21 (-0.21) |
| plr_db | +12.10 | +10.59 (-1.51) | +10.30 (-1.80) | +11.78 (-0.32) |
| side_ratio_db | -8.00 | -7.39 (+0.61) | -7.45 (+0.55) | -7.58 (+0.42) |

## !!!Round and Round.wav (matched to -14.33 LUFS)

| Metric | ORIGINAL | P31_DEFAULT | V2_CAL_DEEMPH | V2_CAL_DEEMPH_PK12 |
|---|---|---|---|---|
| res_v2_max_db | +0.00 | +0.00 (+0.00) | +0.00 (+0.00) | +0.00 (+0.00) |
| res_v2_hz | — | — | — | — |
| res_v2_q | — | — | — | — |
| resonance_max_db | +3.69 | +3.75 (+0.06) | +3.69 (+0.00) | +3.69 (+0.00) |
| resonance_hz | 7718 | 7718 | 7718 | 7718 |
| sharpness_acum | +1.81 | +1.88 (+0.07) | +1.82 (+0.01) | +1.82 (+0.01) |
| band_presence_db | -17.99 | -16.94 (+1.05) | -17.66 (+0.33) | -17.73 (+0.26) |
| band_brilliance_db | -18.83 | -17.82 (+1.01) | -18.50 (+0.33) | -18.58 (+0.25) |
| band_air_db | -22.87 | -20.99 (+1.88) | -22.46 (+0.41) | -22.56 (+0.31) |
| tilt_db_per_oct | -3.48 | -3.35 (+0.13) | -3.45 (+0.03) | -3.47 (+0.01) |
| presence_flux_db | +11.71 | +11.26 (-0.45) | +11.66 (-0.05) | +11.63 (-0.08) |
| crest_db | +10.48 | +10.42 (-0.06) | +10.05 (-0.43) | +10.60 (+0.12) |
| plr_db | +9.64 | +9.34 (-0.30) | +9.09 (-0.55) | +9.64 (+0.00) |
| side_ratio_db | -17.44 | -16.21 (+1.23) | -16.30 (+1.14) | -16.40 (+1.04) |

## Chain distortion (test tones, -6 dBFS)

| Chain / stage | THD 1 kHz | SMPTE IMD | Aliasing (9 kHz) |
|---|---|---|---|
| P31_DEFAULT | -32.6 dB | -24.2 dB | -58.9 dB |
| V2_CAL_DEEMPH | -33.2 dB | -24.2 dB | -59.4 dB |
| V2_CAL_DEEMPH_PK12 | -43.2 dB | -33.3 dB | -66.8 dB |
| stage_tape_v2 | -32.6 dB | -24.2 dB | -61.0 dB |
| stage_air_exciter | -158.7 dB | -163.2 dB | -72.7 dB |
| stage_vocal_sat_4x | -32.8 dB | -23.9 dB | -63.0 dB |
| stage_bass_softclip_4x | -33.0 dB | -24.0 dB | -63.2 dB |
| stage_drum_softclip_4x | -30.8 dB | -21.8 dB | -61.0 dB |
| ref_softclip_1x_pre_fix | -30.8 dB | -21.8 dB | -30.8 dB |
