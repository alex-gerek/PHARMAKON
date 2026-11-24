"""The split takes the kick out of the bass bus.

Synthetic mix with a known answer: a held 55 Hz bass note (sine with slow notes) and a kick
(a 120 ms sine sweep 110 -> 45 Hz with a fast decay) every 0.5 s. Before this step the low-band
HPSS kept most of the kick body in Bass.wav.
"""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import remaster_engine as re_eng  # noqa: E402

SR = 44100


def _parts(seconds=6.0):
    n = int(SR * seconds)
    t = np.arange(n) / SR
    f_bass = np.where((t % 2.0) < 1.0, 55.0, 49.0)                    # two held notes
    bass = 0.25 * np.sin(2 * np.pi * np.cumsum(f_bass) / SR)
    kick = np.zeros(n)
    L = int(0.12 * SR); tt = np.arange(L) / SR
    sweep = np.sin(2 * np.pi * np.cumsum(45.0 + 65.0 * np.exp(-tt / 0.02)) / SR) * np.exp(-tt / 0.04)
    for s in np.arange(0.25, seconds - 0.2, 0.5):
        i = int(s * SR); kick[i:i + L] += 0.9 * sweep
    return bass, kick


def _share(est, parts, k):
    """Share of source k's energy that the least-squares fit finds in est."""
    A = np.stack(parts, 1)
    c, *_ = np.linalg.lstsq(A, est, rcond=None)
    return float(c[k] ** 2)


def _si_sdr(ref, est):
    ref = ref - ref.mean(); est = est - est.mean()
    a = np.dot(est, ref) / np.dot(ref, ref); t = a * ref; e = est - t
    return 10 * np.log10(np.dot(t, t) / (np.dot(e, e) + 1e-12))


def _split(tmp_path, tag, bass, kick):
    mix = np.column_stack([bass + kick, bass + kick]).astype(np.float32)
    p = tmp_path / f"kb_{tag}.wav"
    sf.write(p, mix, SR, subtype="FLOAT")
    _, info = re_eng.split_audio_to_stems(str(p), str(tmp_path / f"out_{tag}"), subtype="FLOAT")
    d = sf.read(info["drums"])[0].mean(1)
    b = sf.read(info["bass"])[0].mean(1)
    n = min(len(d), len(b), len(kick))
    return d[:n], b[:n], n


def test_kick_goes_to_drums_and_both_buses_get_closer_to_the_truth(tmp_path, monkeypatch):
    bass, kick = _parts()
    d1, b1, n = _split(tmp_path, "new", bass, kick)
    parts = [bass[:n], kick[:n]]
    assert _share(d1, parts, 1) > 0.6, "most of the kick must be in Drums"
    assert _share(b1, parts, 1) < 0.05, "almost no kick may stay in Bass"
    assert _share(b1, parts, 0) > 0.65, "the held note stays in Bass"
    # the same mix without the step (split 3.3 as it was)
    monkeypatch.setattr(re_eng, "_move_kick_to_drums", lambda d, b, a, sr: (d, b))
    d0, b0, _ = _split(tmp_path, "old", bass, kick)
    assert _si_sdr(kick[:n], d1) > _si_sdr(kick[:n], d0) + 3.0, "Drums must get clearly closer to the kick"
    assert _si_sdr(bass[:n], b1) > _si_sdr(bass[:n], b0), "Bass must get closer to the bass note"


def test_moving_the_kick_keeps_drums_plus_bass():
    bass, kick = _parts(4.0)
    audio = np.column_stack([bass + kick, bass + kick])
    drums = np.zeros_like(audio)
    bass_stem = audio.copy()
    d2, b2 = re_eng._move_kick_to_drums(drums, bass_stem, audio, SR)
    assert np.allclose(d2 + b2, drums + bass_stem, atol=1e-5)
    assert np.mean(d2 ** 2) > 0.1 * np.mean(kick ** 2)          # something was moved


def test_no_kick_no_change():
    t = np.arange(int(3 * SR)) / SR
    tone = 0.3 * np.sin(2 * np.pi * 55 * t)
    audio = np.column_stack([tone, tone])
    drums = np.zeros_like(audio)
    d2, b2 = re_eng._move_kick_to_drums(drums, audio.copy(), audio, SR)
    assert np.array_equal(d2, drums) and np.array_equal(b2, audio)
