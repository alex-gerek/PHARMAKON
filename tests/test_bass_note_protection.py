"""The kick gate keeps a bass note that sounds through the hit, but not an 808.

The kick step moves low-end energy above the bass floor into Drums during each hit; when a bass
note sounds through the hit, its harmonics went to Drums too. Now the pitch of the bass bus is
tracked and the note's harmonics are protected, but only where the pitch behaves like a bass note
(steady level, no fast downward slide); the pitched 808 / tom tones of the drums are not protected.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402

SR = 44100


def _808(seconds=4.0, every=0.5):
    n = int(SR * seconds)
    out = np.zeros(n)
    L = int(0.45 * SR); tt = np.arange(L) / SR
    sweep = np.sin(2 * np.pi * np.cumsum(50.0 + 60.0 * np.exp(-tt / 0.03)) / SR) * np.exp(-tt / 0.08)
    for s in np.arange(0.1, seconds - 0.5, every):
        i = int(s * SR); out[i:i + L] += sweep[:n - i]
    return out


def _held_bass(seconds=4.0, f=55.0):
    t = np.arange(int(SR * seconds)) / SR
    x = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) + 0.2 * np.sin(2 * np.pi * 3 * f * t)
    return 0.3 * x


def test_steady_bass_note_is_kept_and_808_is_not():
    held = _held_bass()
    tt, f0 = re_eng._bass_pitch_track(held, SR)
    kept = re_eng._bass_notes_only(held, SR, tt, f0)
    assert np.mean(kept > 0) > 0.6, "a steady bass note must count as a bass note"
    b808 = _808()
    tt, f0 = re_eng._bass_pitch_track(b808, SR)
    kept = re_eng._bass_notes_only(b808, SR, tt, f0)
    assert np.mean(kept[f0 > 0] > 0) < 0.25 if np.any(f0 > 0) else True, "a decaying, sliding 808 must not count"


def _kick_hits(seconds=4.0, every=0.5):
    n = int(SR * seconds)
    kick = np.zeros(n)
    L = int(0.12 * SR); tt = np.arange(L) / SR
    sweep = np.sin(2 * np.pi * np.cumsum(45.0 + 65.0 * np.exp(-tt / 0.02)) / SR) * np.exp(-tt / 0.04)
    for s in np.arange(0.25, seconds - 0.2, every):
        i = int(s * SR); kick[i:i + L] += 0.9 * sweep
    return kick


def _notes_on_the_hits(seconds=4.0, every=0.5):
    """A new bass note starts on every hit (55 / 73 / 62 / 82 Hz in turn) and holds until the next:
    the case the gate got wrong, because the new note is not yet in the floor around the hit."""
    t = np.arange(int(SR * seconds)) / SR
    notes = np.array([55.0, 73.4, 61.7, 82.4])
    k = np.clip(((t - 0.25) // every).astype(int), 0, None) % len(notes)
    f = notes[k]
    ph = 2 * np.pi * np.cumsum(f) / SR
    return 0.3 * (np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph))


def test_held_note_stays_in_bass_through_the_hits(monkeypatch):
    bass = _notes_on_the_hits()
    kick = _kick_hits()
    mix_mono = bass + kick
    onsets = re_eng._track_map_module().detect_kick_onsets(mix_mono, SR)
    assert len(onsets) > 3
    k_new = re_eng._kick_part_of_bass(mix_mono, SR, onsets)
    monkeypatch.setattr(re_eng, "_bass_notes_only", lambda b, sr, tt, f0: np.zeros_like(f0))
    k_old = re_eng._kick_part_of_bass(mix_mono, SR, onsets)

    def si_sdr(ref, est):
        ref = ref - ref.mean(); est = est - est.mean()
        a = est @ ref / (ref @ ref); t = a * ref; e = est - t
        return 10 * np.log10((t @ t) / (e @ e))
    # the bass bus gets closer to the bass, the kick part does not get worse
    assert si_sdr(bass, mix_mono - k_new) > si_sdr(bass, mix_mono - k_old) + 0.03
    assert si_sdr(kick, k_new) > si_sdr(kick, k_old) - 0.05
