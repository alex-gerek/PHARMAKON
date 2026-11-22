"""Stems mode takes every stem of a folder (DEV note 37).

Suno exports 7-12 numbered stems. The 3.2 rule took ONE file per keyword (vocal, drum,
bass, other), so backing vocals, keys, synths, percussion, guitar ... were left out of the
master, and an extra "(Drum Kit).wav" render in the folder could replace the drum stem.
"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402

SUNO = ["0 Lead Vocals", "1 Backing Vocals", "2 Drums", "3 Bass", "4 Keyboard",
        "5 Percussion", "6 Synth", "7 Other", "8 Brass"]


def _tone(sr, f, amp, seconds=2.0):
    t = np.arange(int(sr * seconds)) / sr
    return np.column_stack([amp * np.sin(2 * np.pi * f * t)] * 2).astype(np.float32)


def _suno_folder(path, sr=48000, extra=()):
    path.mkdir()
    for i, name in enumerate(SUNO):
        sf.write(path / f"{name}.wav", _tone(sr, 110.0 * (i + 1), 0.05), sr, subtype="PCM_24")
    for name in extra:
        sf.write(path / f"{name}.wav", _tone(sr, 3000.0, 0.3), sr, subtype="PCM_24")
    return path


def _files(d):
    return [str(d / f) for f in os.listdir(d)]


def test_every_suno_stem_lands_in_a_bus(tmp_path):
    d = _suno_folder(tmp_path / "Song")
    g = re_eng.group_stem_files(_files(d))
    names = {k: sorted(os.path.basename(p)[:-4] for p in v) for k, v in g.items()}
    assert names["vocals"] == ["0 Lead Vocals", "1 Backing Vocals"]
    assert names["drums"] == ["2 Drums", "5 Percussion"]
    assert names["bass"] == ["3 Bass"]
    assert names["other"] == ["4 Keyboard", "6 Synth", "7 Other", "8 Brass"]
    assert sum(len(v) for v in g.values()) == len(SUNO)


def test_bus_sum_is_the_sum_of_all_stems(tmp_path):
    d = _suno_folder(tmp_path / "Song")
    buses, sr = re_eng.load_stem_buses(re_eng.group_stem_files(_files(d)))
    total = sum(sf.read(p, dtype="float32")[0] for p in _files(d))
    assert sr == 48000
    assert np.max(np.abs(sum(buses.values()) - total)) < 1e-6


def test_extra_renders_and_pharmakon_outputs_are_not_stems(tmp_path):
    # a "(Drum Kit)" extract next to the numbered set used to replace "2 Drums"
    d = _suno_folder(tmp_path / "Song", extra=["Song (Drum Kit)", "Song (Synth Bass)", "Song - STUDIO_REMASTER"])
    g = re_eng.group_stem_files(_files(d))
    used = [os.path.basename(p) for v in g.values() for p in v]
    assert not any("Drum Kit" in u or "Synth Bass" in u or "REMASTER" in u for u in used)
    assert len(used) == len(SUNO)


def test_four_stem_folder_is_unchanged(tmp_path):
    d = tmp_path / "Four"
    d.mkdir()
    for n in ("Vocals", "Drums", "Bass", "Other"):
        sf.write(d / f"{n}.wav", _tone(44100, 220.0, 0.1), 44100)
    g = re_eng.group_stem_files(_files(d))
    assert {k: [os.path.basename(p) for p in v] for k, v in g.items()} == {
        "vocals": ["Vocals.wav"], "drums": ["Drums.wav"], "bass": ["Bass.wav"], "other": ["Other.wav"]}


def test_stems_mode_runs_on_a_suno_folder(tmp_path):
    d = _suno_folder(tmp_path / "SunoSong")
    master_path, metrics = re_eng.process_stems_folder(str(d), open_folder=False)
    assert master_path and os.path.isfile(master_path)
    raw, _ = sf.read(metrics["raw_sum_path"], dtype="float32")
    total = sum(sf.read(p, dtype="float32")[0] for p in _files(d) if p.endswith(".wav"))
    n = min(len(raw), len(total))
    # RAW_SUM holds all 9 stems (PCM_24 export rounding only)
    assert np.max(np.abs(raw[:n] - total[:n])) < 1e-4
