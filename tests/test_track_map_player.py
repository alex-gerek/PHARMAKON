"""
Unit tests for integrated Track Intelligence Map audition player in mastering reports.
Verifies player bar markup, audio elements, source switching, and dynamic seeking.
"""
import os
import tempfile
import pytest
from remaster_engine import generate_track_map_html, generate_mastering_report_html

def _sample_track_map():
    return {
        "estimated_bpm": 128.0,
        "total_duration_s": 120.0,
        "total_kick_events": 64,
        "sections": [
            {
                "section_index": 1,
                "name": "Intro",
                "tag": "INTRO",
                "time_start_s": 0.0,
                "time_end_s": 15.0,
                "duration_s": 15.0,
                "time_str": "0:00 - 0:15",
                "color": "#f59e0b",
                "kicks_count": 8,
                "sub_phase_locked_count": 8,
                "crest_factor_db": 12.0,
                "rms_mix_dbfs": -18.0,
                "peak_mix_dbfs": -3.0,
                "sub_phase_correlation": 0.95,
                "policy_summary": "Acoustic transparency"
            },
            {
                "section_index": 2,
                "name": "Drop 1",
                "tag": "DROP",
                "time_start_s": 15.0,
                "time_end_s": 45.0,
                "duration_s": 30.0,
                "time_str": "0:15 - 0:45",
                "color": "#f43f5e",
                "kicks_count": 32,
                "sub_phase_locked_count": 30,
                "crest_factor_db": 9.5,
                "rms_mix_dbfs": -12.0,
                "peak_mix_dbfs": -0.5,
                "sub_phase_correlation": 0.88,
                "policy_summary": "Sub-bass headroom preserved"
            }
        ]
    }

def test_generate_track_map_html_player_elements():
    tm = _sample_track_map()
    sources = {
        'master': './TEST_TRACK - STUDIO_REMASTER.wav',
        'delta': './TEST_TRACK - DELTA_POISON.wav',
        'raw': '../TEST_TRACK.wav',
        'master_abs': '/path/to/master.wav',
        'delta_abs': '/path/to/delta.wav',
        'raw_abs': '/path/to/raw.wav'
    }
    html = generate_track_map_html(tm, target_path="/tmp", audio_sources=sources)
    
    assert "tm-player-bar" in html
    assert "tmMainPlayBtn" in html
    assert "toggleReportAudioPlay" in html
    assert "switchReportAudioSource" in html
    assert "tmPlayheadLine" in html
    assert "tmPlayhead-bead" in html or "tm-playhead-bead" in html
    assert 'id="tmAudioMaster"' in html
    assert 'src="./TEST_TRACK - STUDIO_REMASTER.wav"' in html
    assert 'id="tmAudioRaw"' in html
    assert 'src="../TEST_TRACK.wav"' in html
    assert 'id="tmAudioDelta"' in html
    assert 'src="./TEST_TRACK - DELTA_POISON.wav"' in html
    assert "btnSrcB" in html
    assert "btnSrcA" in html
    assert "btnSrcC" in html
    assert "playCurrentSection" in html
    assert "onTimelineBarClicked" in html

def test_generate_track_map_html_fallback_sources():
    tm = _sample_track_map()
    # Call without audio_sources parameter
    html = generate_track_map_html(tm)
    assert "tm-player-bar" in html
    assert 'id="tmAudioMaster"' in html
    assert 'id="tmAudioRaw"' in html
    assert 'id="tmAudioDelta"' in html

def test_mastering_report_html_contains_player():
    with tempfile.TemporaryDirectory() as tmpdir:
        track_name = "AuditionTestTrack"
        metrics = {
            'track_map': _sample_track_map(),
            'true_peak_orig_db': -0.2,
            'true_peak_proc_db': -1.0,
            'lufs_orig': -14.0,
            'lufs_proc': -14.0,
            'master_path': os.path.join(tmpdir, f"{track_name} - STUDIO_REMASTER.wav"),
            'delta_path': os.path.join(tmpdir, f"{track_name} - DELTA_POISON.wav"),
            'raw_path': os.path.join(tmpdir, f"{track_name}.wav"),
            'diagnosis': {
                'source': [{'status': 'ok', 'label': 'Phase', 'text': 'Original signal intact'}],
                'treatment': [{'status': 'ok', 'label': 'Linear', 'text': 'Applied linear phase correction'}],
                'seal': ['Bit-exact audit verified']
            }
        }
        
        report_path = generate_mastering_report_html(track_name, metrics, tmpdir)
        assert os.path.exists(report_path)
        
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        assert "tm-player-bar" in content
        assert "tm-playhead-line" in content
        assert "tmAudioMaster" in content
        assert "tmAudioRaw" in content
        assert "tmAudioDelta" in content
        assert "PLAY FROM HERE" in content
        assert "switchReportAudioSource" in content


# --- 3.3 fixes: no local paths in reports, escaped names, report-relative audio ---

def _report_with_audio(tmpdir, track_name):
    metrics = {
        'track_map': _sample_track_map(),
        'master_path': os.path.join(tmpdir, f"{track_name} - STUDIO_REMASTER.wav"),
        'delta_path': os.path.join(tmpdir, f"{track_name} - DELTA_POISON.wav"),
        'raw_path': os.path.join(os.path.dirname(tmpdir), f"{track_name}.wav"),
    }
    return generate_mastering_report_html(track_name, metrics, tmpdir)


def test_report_has_no_absolute_local_paths():
    with tempfile.TemporaryDirectory() as root:
        out = os.path.join(root, "Remaster")
        os.makedirs(out)
        with open(_report_with_audio(out, "PathLeak"), encoding="utf-8") as f:
            content = f.read()
        import re
        tags = " ".join(re.findall(r"<audio[^>]*>", content))
        for p in (root, root.replace("\\", "/")):
            assert p not in tags
        # NOTE: the hidden "tm-target-path" field (used by "save track map") still holds the
        # output folder; tracked as a follow-up in DEV note 32.
        assert "data-abs-path" not in content
        assert 'src="../PathLeak.wav"' in content


def test_report_escapes_track_names_in_audio_tags():
    tm = _sample_track_map()
    sources = {'master': './A "quoted" & name.wav', 'delta': './d.wav', 'raw': '../r.wav'}
    html = generate_track_map_html(tm, audio_sources=sources)
    assert 'src="./A &quot;quoted&quot; &amp; name.wav"' in html
    assert 'A "quoted"' not in html


def _write_wav(path):
    import numpy as np
    import soundfile as sf
    sf.write(path, np.zeros(441, dtype="float32"), 44100)


def test_server_serves_audio_from_the_requesting_reports_folder():
    from fastapi.testclient import TestClient
    from gui.server import app, SESSION_TOKEN
    client = TestClient(app)
    h = {"X-Session-Token": SESSION_TOKEN}
    with tempfile.TemporaryDirectory() as root:
        a, b = os.path.join(root, "A", "Remaster"), os.path.join(root, "B", "Remaster")
        for d in (a, b):
            os.makedirs(d)
        # same file name in two folders: each report must get its own file
        for d, n in ((a, 441), (b, 882)):
            import numpy as np
            import soundfile as sf
            sf.write(os.path.join(d, "Song - STUDIO_REMASTER.wav"), np.zeros(n, dtype="float32"), 44100)
        sf.write(os.path.join(root, "B", "Song.wav"), np.zeros(1323, dtype="float32"), 44100)
        rep_b = _report_with_audio(b, "Song")
        ref = "http://127.0.0.1:8000/api/report?path=" + rep_b
        r = client.get("/api/Song%20-%20STUDIO_REMASTER.wav", headers={**h, "Referer": ref})
        assert r.status_code == 200
        assert r.content == open(os.path.join(b, "Song - STUDIO_REMASTER.wav"), "rb").read()
        r = client.get("/api/report-audio", params={"rel": "../Song.wav"}, headers={**h, "Referer": ref})
        assert r.status_code == 200
        assert r.content == open(os.path.join(root, "B", "Song.wav"), "rb").read()
        # non-audio and absolute paths are refused
        assert client.get("/api/report-audio", params={"rel": "../../x.html"}, headers={**h, "Referer": ref}).status_code == 404
        assert client.get("/api/report-audio", params={"rel": os.path.join(a, "Song - STUDIO_REMASTER.wav")},
                          headers={**h, "Referer": ref}).status_code == 404
        assert client.get("/api/sub/Song.wav", headers={**h, "Referer": ref}).status_code == 403
