========================================================================
   PHARMAKON 3.0 (v3.0.0) // Neural Audio Antidote & Stem Mastering Console
   Portable & Self-Contained Distribution for Windows x64
   Open-Source MIT License (c) 2026 Lex Gerek | Lazuli Pictures
========================================================================

TWO EASY WAYS TO USE:
------------------------------------------------------------------------
OPTION A: GRAPHICAL SETUP WIZARD (RECOMMENDED FOR PERMANENT USE)
1. Double-click "Install_PHARMAKON.bat".
2. Select your desired installation location (default: AppData\Programs).
3. Check "Create Desktop Shortcut" (with studio gold icon) and "Launch".
4. Click "INSTALL PHARMAKON". Everything is set up cleanly in 3 seconds!

OPTION B: 100% PORTABLE / IN-PLACE (RUN FROM ANY FOLDER OR USB DRIVE)
1. Keep this folder wherever you like (e.g. C:\PHARMAKON, D:\AudioTools, USB).
2. Double-click "Create_Desktop_Shortcut.bat" to place a 1-click icon on your Desktop.
3. Or simply launch "Start_Pharmakon.bat" directly!
4. The studio console opens automatically at:
   http://127.0.0.1:7860
5. To gracefully stop the engine, double-click "Stop_Pharmakon.bat".

WHAT'S NEW IN PHARMAKON 3.0 (v3.0.0):
------------------------------------------------------------------------
- LIMITER-AWARE TRANSIENT-GUARDED SUB-SYNC:
  Local Guard per-kick phase alignment with Virtual Micro-Limiter cost
  function and transient protection. Prevents destructive inter-sample
  clashing and restores punchy, phase-locked bass.
- TRUE-PEAK LIMITER GUARD (4x OVERSAMPLING):
  Dedicated ceiling protection (default -0.3 dBTP; -1.0 dBTP for EBU R128) preventing
  inter-sample peak overs on streaming transcoding (Spotify / Apple Music).
- PHARMAKON TRACK INTELLIGENCE MAP:
  Automatic 9-sector structural musical intelligence (Intro, Drop, Groove,
  Development, Dense Middle, Interlude, Breakdown, Buildup, Outro).
  Interactive enlarged section inspector with intra-section kick onset map.
- LOSSLESS MASTERING PIPELINE:
  Verified 24-bit PCM_24 WAV export across single-file, stem, and split chains.
- EXPANDED STEREO PANORAMA & 3D DEPTH:
  Tighter, cleaner low-end articulation and clearer separation of mid/high
  instrumental lines without fatigue or synthetic harshness.

NOTE ON CURRENT STATUS & FUTURE ROADMAP:
------------------------------------------------------------------------
Currently calibrated and deep-tested on peak-energy EDM / Techno (Vector Pulse
benchmark suite). The engine operates reliably in production, with ongoing
mathematical refinements actively extending dedicated multi-genre profiles
(Drum & Bass, Hip-Hop/Trap, Rock/Metal, and Ambient/Pop).

SYSTEM REQUIREMENTS:
------------------------------------------------------------------------
- Windows 10 or Windows 11 (64-bit).
- Zero external dependencies: no Python, no Git, no Visual Studio needed.
- Audio: 16 kHz to 96 kHz (WAV, FLAC, MP3, OGG).

INCLUDED GUIDES & DOCUMENTATION (see docs/ folder):
------------------------------------------------------------------------
- docs/PHARMAKON_3_ARCHITECTURAL_GUIDE.md
  Micro-transient phase alignment, Virtual Micro-Limiter, and 9-sector macro segmentation.
- docs/STEM_MASTERING_GUIDE.md
  The comprehensive guide to 4-stem separation, bass mono-locking, and mastering.
- docs/AI_AUDIO_RESTORATION_WORKFLOW.md
  The engineering blueprint for taming metallic AI whistle and MP3 phase dispersion.

LEGACY PHARMAKON 2.0 (FROZEN ARCHIVE POLICY):
------------------------------------------------------------------------
For producers and engineers who prefer the established sound and workflow
of PHARMAKON 2.0, the complete v2.0.3 release package remains permanently
available in our GitHub Releases archive. Please note that version 2.0 is
now a frozen archive and will receive no further patches or updates. All
ongoing DSP research, multi-genre profiles, and limiter refinements will
be developed exclusively in PHARMAKON 3.0+.

CREDITS & OPEN-SOURCE LICENSE:
------------------------------------------------------------------------
Architect: Lex Gerek | Lazuli Pictures
Technical Audit: Feasy Core Architecture
Repository: https://github.com/alex-gerek/PHARMAKON
Licensed under the open-source MIT License.
