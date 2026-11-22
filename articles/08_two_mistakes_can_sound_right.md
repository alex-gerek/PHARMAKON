# Two mistakes can sound right

**Author:** Lex Gerek (Sound Architect / Engineer)  
**Project:** PHARMAKON 3.2 Studio Console  
**Engineering record:** [DEV_NOTE_MATH_AUDIT_FIXES.md](../DEV_NOTE_MATH_AUDIT_FIXES.md), notes 6, 16, 19 (tone) and 33, 35, 36 (beat grid and sections)

![A hand lifts a blue glass off a concert photo: under the glass the colours look right, outside it the same photo is yellow](img/08_two_mistakes_cover.jpg)

---

PHARMAKON cleans up AI-generated music. Along the way we learned something about how sound gets fixed.

Imagine a photo that looks too yellow. Instead of fixing the light, you add a blue filter until it looks right. Now remove the filter, and the photo looks worse. The filter wasn't fixing anything. It was hiding the problem.

We found the same thing inside PHARMAKON. One part made the high sounds too bright. Another turned them down too much. Together they sounded balanced, so nobody noticed. We fixed both, and that is now PHARMAKON's default sound.

It happened again with our beat finder. Its timing was slightly off, and the song-section detector had been set up around that mistake. When we fixed the timing, the sections got worse. Once we found the second mistake too, the sections ended up more accurate than before.

So we no longer judge one part at a time, and we don't trust "it sounds fine." We measure the whole chain against a known right answer.

If an honest fix makes things worse, don't roll it back yet. You may have found the second mistake.

## Try PHARMAKON

PHARMAKON is free and open source (MIT license). It runs on an ordinary laptop: no GPU, no AI models, just measured math.

Download for Windows (portable, no install): <https://github.com/alex-gerek/PHARMAKON/releases/latest>

Source code, macOS / Linux and all engineering notes: <https://github.com/alex-gerek/PHARMAKON>

---

### The numbers behind the two cases

- **Tone.** The de-harsher compared a bandwidth ratio with an amplitude ratio, so it cut about 5.5 dB even on flat noise. The tape stage lifted everything above about 3.5 kHz by 1.3–1.5 dB and never took it back. Each error hid the other. Clean Chain 3.2 fixes both (calibrated de-harsher, matched tape de-emphasis); Classic 3.1 keeps the old sound bit-for-bit.
- **Beat grid and sections.** The beat grid sat about 40 ms early: the onset detector marks a hit 1792 samples (one analysis window minus one hop) before it happens. Correcting it moved the bar windows the section thresholds had been set on, and correct section labels on 20 held-out test tracks fell from 0.918 to 0.894. Section features were put back on their original clock, then build-up boundaries were moved to the bar where the change starts: held-out boundary accuracy (±0.5 s) 0.913 → 0.938, labels 0.918 → 0.921, no track worse than before.

*Original publication on X:* [https://x.com/LexGerek/status/2124566669762683097](https://x.com/LexGerek/status/2124566669762683097)
