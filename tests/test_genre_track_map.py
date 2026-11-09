import numpy as np
import pytest
from track_map_engine import build_provisional_track_map, analyze_track_style

def test_techno_edm_structure_preserved():
    """Verify that a 4-on-the-floor beat is classified as electronic and retains 9-sector EDM mapping."""
    sr = 44100
    bpm = 135.0
    bar_s = (60.0 / bpm) * 4.0
    dur_s = 180.0 # 3 minutes
    n_samples = int(dur_s * sr)
    t = np.arange(n_samples) / sr
    
    # Generate techno track with heavy sub-bass and 4-on-the-floor kicks
    mix = 0.3 * np.sin(2 * np.pi * 50.0 * t) # continuous sub
    # Add regular kicks every quarter beat (0.444s)
    beat_step = int((60.0 / bpm) * sr)
    for kick_pos in range(0, n_samples - int(0.1 * sr), beat_step):
        k_t = np.arange(int(0.1 * sr)) / sr
        kick_burst = np.sin(2 * np.pi * 70.0 * np.exp(-30.0 * k_t) * k_t) * np.exp(-15.0 * k_t)
        mix[kick_pos : kick_pos + len(kick_burst)] += 0.8 * kick_burst

    # Fade out last 8 bars for a realistic outro
    outro_len = int(8.0 * bar_s * sr)
    mix[-outro_len:] *= np.linspace(1.0, 0.2, outro_len)
        
    tmap = build_provisional_track_map(mix, sr=sr)
    
    assert "genre" in tmap
    assert tmap["genre"]["category"] == "electronic"
    assert "Techno" in tmap["genre"]["label"] or "Electronic" in tmap["genre"]["label"]
    assert tmap["num_sections"] > 3
    # Check that EDM tags exist
    tags = [s["tag"] for s in tmap["sections"]]
    assert "INTRO" in tags
    assert "OUTRO" in tags
    assert any(tag in ("DROP", "GROOVE", "BREAKDOWN", "BUILDUP") for tag in tags)

def test_pop_song_ssm_structure():
    """Verify that a Pop/Song harmonic progression with verse/chorus is mapped into song roles."""
    sr = 44100
    bpm = 120.0
    beat_s = 60.0 / bpm
    bar_s = beat_s * 4.0
    
    # 4 bars intro, 8 bars verse, 4 bars pre, 8 bars chorus, 8 bars verse, 8 bars chorus, 4 bars outro
    structure_plan = [
        ("intro", 4, 0.4),
        ("verse", 8, 0.5),
        ("pre", 4, 0.8),
        ("chorus", 8, 1.4),
        ("verse", 8, 0.5),
        ("chorus", 8, 1.4),
        ("outro", 4, 0.3),
    ]
    
    total_bars = sum(b for _, b, _ in structure_plan)
    audio = np.zeros(int(total_bars * bar_s * sr), dtype=np.float32)
    curr_s = 0
    
    for sec_type, bars, gain in structure_plan:
        n_sec = int(bars * bar_s * sr)
        sec_t = np.arange(n_sec) / sr
        sig = np.zeros(n_sec, dtype=np.float32)
        if sec_type in ("intro", "verse", "outro"):
            sig += 0.2 * np.sin(2 * np.pi * 261.6 * sec_t) # C chord
        elif sec_type == "pre":
            sig += 0.2 * np.sin(2 * np.pi * 220.0 * sec_t) # Am chord
        elif sec_type == "chorus":
            sig += 0.3 * np.sin(2 * np.pi * 174.6 * sec_t) # F chord
            sig += 0.2 * np.sin(2 * np.pi * 329.6 * sec_t)
            sig += 0.2 * np.sin(2 * np.pi * 523.2 * sec_t)
        sig *= gain
        
        # Syncopated pop kick on beat 1 and 3 only (NOT 4-on-the-floor)
        for b in range(bars):
            b_off = int(b * bar_s * sr)
            k_len = int(0.1 * sr)
            k_t = np.arange(k_len) / sr
            kick = np.sin(2 * np.pi * 90.0 * np.exp(-20.0 * k_t) * k_t) * np.exp(-15.0 * k_t)
            if b_off + k_len < n_sec:
                sig[b_off : b_off + k_len] += 0.4 * kick
            b3_off = b_off + int(2.0 * beat_s * sr)
            if b3_off + k_len < n_sec:
                sig[b3_off : b3_off + k_len] += 0.3 * kick
                
        audio[curr_s : curr_s + n_sec] = sig
        curr_s += n_sec
        
    tmap = build_provisional_track_map(audio, sr=sr)
    
    assert "genre" in tmap
    assert tmap["genre"]["category"] == "pop_rock"
    tags = [s["tag"] for s in tmap["sections"]]
    assert "CHORUS" in tags
    assert "VERSE" in tags
    assert "INTRO" in tags
    assert "OUTRO" in tags
