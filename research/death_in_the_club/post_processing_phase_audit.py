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

    # 1. Generate 120 BPM Kick (50 Hz sub)
    kick_mono, _, _ = generate_synthetic_kick(
        duration=duration, sr=sr, bpm=120.0, f_start=140.0, f_end=48.0, amplitude=0.85
    )
    # 2. Generate 50 Hz Bass with deliberate 180° destructive phase conflict (murder scene)
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

    # Raw Sum (Damaged by phase cancellation)
    raw_mix = drums + bad_bass

    # 3. Process with PHARMAKON Method D (GW-FRA Phase Alignment)
    # We DO NOT modify method_d, we just call it as an external black-box tool!
    restored_bass, meta = method_d_guarded_per_kick(drums, bad_bass, sr)
    restored_mix = drums + restored_bass

    # 4. Measure Metrics
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

    # 5. Delta Poison (Difference signal)
    delta_poison = restored_mix - raw_mix
    delta_rms = compute_rms(delta_poison)
    delta_dbfs = 20.0 * np.log10(max(1e-12, delta_rms))

    # Normalize files cleanly for export (-0.5 dBFS ceiling to prevent any player clipping)
    max_peak = max(np.max(np.abs(raw_mix)), np.max(np.abs(restored_mix)))
    norm_factor = 0.94 / max_peak if max_peak > 0 else 1.0

    wav_damaged = os.path.join(AUDIT_DIR, "01_PHASE_DAMAGED_MIX.wav")
    wav_restored = os.path.join(AUDIT_DIR, "02_PHARMAKON_RESTORED_MIX.wav")
    wav_delta = os.path.join(AUDIT_DIR, "03_DELTA_POISON.wav")

    sf.write(wav_damaged, raw_mix * norm_factor, sr, subtype="PCM_24")
    sf.write(wav_restored, restored_mix * norm_factor, sr, subtype="PCM_24")
    sf.write(wav_delta, delta_poison * norm_factor, sr, subtype="PCM_24")

    # 6. Generate Interactive HTML A/B Player
    html_path = os.path.join(AUDIT_DIR, "PHARMAKON_AB_LISTENING_PLAYER.html")
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
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
  .badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 16px;
  }}
  .badge-danger {{ background: #da3633; color: white; }}
  .badge-success {{ background: #238636; color: white; }}
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
  <h1>🎧 PHARMAKON Studio · Сравнительное прослушивание A/B</h1>
  <p class="desc">
    Стресс-тест разрушительной интерференции 180°: бочка и бас бьют одновременно на 48–50 Гц.
    Включите оба трека по очереди в наушниках или мониторах, чтобы услышать разницу в панче и глубине низа.
  </p>

  <div class="track-box" style="border-left: 4px solid #da3633;">
    <div class="track-title">🔴 Вариант A: Повреждённый микс (Противофаза 180°)</div>
    <div class="desc">Бочка и бас вычитают друг друга. Низ «ватный», удар пустой, тело провалилось.</div>
    <audio controls src="01_PHASE_DAMAGED_MIX.wav"></audio>
  </div>

  <div class="track-box" style="border-left: 4px solid #238636;">
    <div class="track-title">🟢 Вариант B: PHARMAKON Restored (Фазовое согласование)</div>
    <div class="desc">Фаза скорректирована. Саб-бас вернулся (+{sub_gain_db:+.2f} dB), атака бочки плотная и монолитная.</div>
    <audio controls src="02_PHARMAKON_RESTORED_MIX.wav"></audio>
  </div>

  <div class="track-box" style="border-left: 4px solid #8957e5;">
    <div class="track-title">🟣 Вариант C: Delta Poison (Спектр разности)</div>
    <div class="desc">Что именно вернул алгоритм (вычитание B − A).</div>
    <audio controls src="03_DELTA_POISON.wav"></audio>
  </div>

  <div class="metrics">
    <div class="metric-item">
      <div class="metric-val">+{sub_gain_db:.2f} dB</div>
      <div class="metric-lbl">Возврат саб-баса</div>
    </div>
    <div class="metric-item">
      <div class="metric-val">{tp_gain_db:+.2f} dB</div>
      <div class="metric-lbl">Рост True Peak (0 = идеально)</div>
    </div>
    <div class="metric-item">
      <div class="metric-val">{crest_restored:.2f}</div>
      <div class="metric-lbl">Crest Factor (было {crest_raw:.2f})</div>
    </div>
  </div>
</div>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print("\n[OK] Аудит успешно завершён!")
    print(f"Аудиофайлы и интерактивный плеер созданы в папке:")
    print(f"  -> {AUDIT_DIR}")
    print(f"  -> 01_PHASE_DAMAGED_MIX.wav")
    print(f"  -> 02_PHARMAKON_RESTORED_MIX.wav")
    print(f"  -> 03_DELTA_POISON.wav")
    print(f"  -> PHARMAKON_AB_LISTENING_PLAYER.html")
    print("=" * 80)


if __name__ == "__main__":
    build_audit_session()
