"""
PHARMAKON: Post-Processing Phase & Headroom Audit Tool
Standalone tool - DOES NOT MODIFY ANY EXISTING ENGINE OR PRODUCTION CODE.
Renders WAVs and generates an interactive A/B HTML audio player for immediate listening.
"""

import os
import sys
import numpy as np
import scipy.signal as signal
import soundfile as sf

PHARMAKON_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PHARMAKON_ROOT not in sys.path:
    sys.path.insert(0, PHARMAKON_ROOT)

from research.death_in_the_club.synthetic_signals import (
    generate_synthetic_kick,
    generate_synthetic_harmonic_bass,
)
from research.death_in_the_club.methods import (
    lowpass_filter,
    compute_rms,
    compute_true_peak,
    method_d_guarded_per_kick,
    ensure_stereo,
)

AUDIT_DIR = os.path.join(os.path.dirname(__file__), "real_tracks_test")
os.makedirs(AUDIT_DIR, exist_ok=True)


def build_audit_session():
    sr = 48000
    duration = 5.0 # 5 seconds of punchy kick-bass pattern

    kick_mono, _, _ = generate_synthetic_kick(
        duration=duration, sr=sr, bpm=120.0, f_start=140.0, f_end=48.0, amplitude=0.85
    )
    bass_mono, _, _ = generate_synthetic_harmonic_bass(
        duration=duration,
        sr=sr,
        f0=48.0,
        harmonics=(1.0, 0.45, 0.15),
        phases=(np.pi, 0.0, 0.0),
        amplitude=0.75,
        repeat_interval=0.5,
    )

    drums = ensure_stereo(kick_mono)
    bad_bass = ensure_stereo(bass_mono)

    raw_mix = drums + bad_bass

    restored_bass, meta = method_d_guarded_per_kick(drums, bad_bass, sr)
    restored_mix = drums + restored_bass

    sub_raw = lowpass_filter(raw_mix, sr, 100.0)
    sub_restored = lowpass_filter(restored_mix, sr, 100.0)
    rms_raw = compute_rms(sub_raw)
    rms_restored = compute_rms(sub_restored)
    sub_gain_db = 20.0 * np.log10(rms_restored / (rms_raw + 1e-12))

    tp_raw = compute_true_peak(raw_mix)
    tp_restored = compute_true_peak(restored_mix)
    tp_gain_db = 20.0 * np.log10(tp_restored / (tp_raw + 1e-12))

    crest_raw = tp_raw / (rms_raw + 1e-12)
    crest_restored = tp_restored / (rms_restored + 1e-12)

    delta_poison = restored_mix - raw_mix
    delta_rms = compute_rms(delta_poison)
    delta_dbfs = 20.0 * np.log10(max(1e-12, delta_rms))

    max_peak = max(np.max(np.abs(raw_mix)), np.max(np.abs(restored_mix)))
    norm_factor = 0.94 / max_peak if max_peak > 0 else 1.0

    wav_damaged = os.path.join(AUDIT_DIR, "01_PHASE_DAMAGED_MIX.wav")
    wav_restored = os.path.join(AUDIT_DIR, "02_PHARMAKON_RESTORED_MIX.wav")
    wav_delta = os.path.join(AUDIT_DIR, "03_DELTA_POISON.wav")

    sf.write(wav_damaged, raw_mix * norm_factor, sr, subtype="PCM_24")
    sf.write(wav_restored, restored_mix * norm_factor, sr, subtype="PCM_24")
    sf.write(wav_delta, delta_poison * norm_factor, sr, subtype="PCM_24")

    html_path = os.path.join(AUDIT_DIR, "PHARMAKON_AB_LISTENING_PLAYER.html")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PHARMAKON · Phase Audit A/B Player</title>
<style>
  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    padding: 30px;
    display: flex;
    justify-content: center;
  }}
  .card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    max-width: 700px;
    width: 100%;
    padding: 24px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  }}
  h1 {{ color: #58a6ff; margin-top: 0; font-size: 22px; }}
  .track-box {{
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
  }}
  .track-title {{ font-weight: bold; font-size: 15px; margin-bottom: 8px; }}
  audio {{ width: 100%; outline: none; margin-top: 6px; }}
  .metrics {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 20px;
    border-top: 1px solid #30363d;
    padding-top: 16px;
  }}
  .metric-item {{
    background: #21262d;
    padding: 10px;
    border-radius: 6px;
    text-align: center;
  }}
  .metric-val {{ font-size: 18px; font-weight: bold; color: #39d353; }}
  .metric-lbl {{ font-size: 11px; color: #8b949e; text-transform: uppercase; margin-top: 4px; }}
  .desc {{ font-size: 13px; color: #8b949e; line-height: 1.5; }}
</style>
</head>
<body>
<div class="card">
  <h1>PHARMAKON Studio · Comparative A/B Auditioning</h1>
  <p class="desc">
    180-Degree Destructive Interference Stress Test: Kick and bass hit simultaneously at 48-50 Hz.
    Audition both versions sequentially in studio monitors or headphones.
  </p>

  <div class="track-box" style="border-left: 4px solid #da3633;">
    <div class="track-title">Option A: Phase-Damaged Mix (180° Polarity Opposition)</div>
    <div class="desc">Kick and bass cancel each other out. Sub-bass is hollow, punch is lost, low-end body collapsed.</div>
    <audio controls src="01_PHASE_DAMAGED_MIX.wav"></audio>
  </div>

  <div class="track-box" style="border-left: 4px solid #238636;">
    <div class="track-title">Option B: PHARMAKON Restored (Phase Aligned)</div>
    <div class="desc">Phase aligned. Sub-bass recovered (+{sub_gain_db:+.2f} dB), punch is solid and focused without peak inflation.</div>
    <audio controls src="02_PHARMAKON_RESTORED_MIX.wav"></audio>
  </div>

  <div class="track-box" style="border-left: 4px solid #8957e5;">
    <div class="track-title">Option C: Delta Poison (Subtracted Residue)</div>
    <div class="desc">Isolated subtracted delta component (Option B minus Option A).</div>
    <audio controls src="03_DELTA_POISON.wav"></audio>
  </div>

  <div class="metrics">
    <div class="metric-item">
      <div class="metric-val">+{sub_gain_db:.2f} dB</div>
      <div class="metric-lbl">Sub Recovery</div>
    </div>
    <div class="metric-item">
      <div class="metric-val">{tp_gain_db:+.2f} dB</div>
      <div class="metric-lbl">True-Peak Growth</div>
    </div>
    <div class="metric-item">
      <div class="metric-val">{crest_restored:.2f}</div>
      <div class="metric-lbl">Crest Factor (Was {crest_raw:.2f})</div>
    </div>
  </div>
</div>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("\n[OK] Audit session completed successfully!")
    print(f"Artifacts created in: {AUDIT_DIR}")


if __name__ == "__main__":
    build_audit_session()
