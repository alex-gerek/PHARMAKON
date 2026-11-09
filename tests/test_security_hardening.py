"""
PHARMAKON 3.1 Security Hardening Test Suite
Covers 18 security verification scenarios:
  1. Missing session token returns 401
  2. Invalid session token returns 401
  3. Valid session token in X-Session-Token header passes
  4. Valid session token in cookie passes
  5. Untrusted Origin returns 403
  6. Trusted loopback Origin passes
  7. Invalid Host header returns 403
  8. Cross-site Sec-Fetch-Site returns 403
  9. /api/stream on non-audio file returns 404
  10. /api/stream path traversal returns 404
  11. /api/stream on valid audio file returns 200
  12. /api/open-report on non-HTML (.exe) returns 403/rejected
  13. /api/open-report on non-existent file returns 404
  14. /api/upload-binary with non-audio/unauthorized extension returns 400
  15. /api/upload-binary exceeding 250MB returns 413
  16. Static file path traversal (/static/..%2f) returns 404
  17. /api/reveal on non-existent path returns 404
  18. Ed25519 cryptographic signature verification on release manifest
"""

import os
import json
import base64
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from gui.server import app, SESSION_TOKEN
import auto_updater
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

client = TestClient(app)
AUTH_HEADERS = {"X-Session-Token": SESSION_TOKEN}


def test_01_missing_session_token_returns_401():
    # Calling protected endpoint /api/presets or /api/split-and-master without token
    resp = client.post("/api/split-and-master", json={})
    assert resp.status_code == 401
    assert "Unauthorized" in resp.text


def test_02_invalid_session_token_returns_401():
    resp = client.post(
        "/api/split-and-master",
        json={},
        headers={"X-Session-Token": "invalid_fake_token_12345"}
    )
    assert resp.status_code == 401
    assert "Unauthorized" in resp.text


def test_03_valid_session_token_header_accepted():
    resp = client.get("/api/presets", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "club" in resp.json()


def test_04_valid_session_token_cookie_accepted():
    client.cookies.set("pharmakon_session_token", SESSION_TOKEN)
    resp = client.get("/api/presets")
    client.cookies.clear()
    assert resp.status_code == 200
    assert "club" in resp.json()


def test_05_untrusted_origin_returns_403():
    resp = client.get(
        "/api/presets",
        headers={**AUTH_HEADERS, "Origin": "http://malicious-website.com"}
    )
    assert resp.status_code == 403
    assert "untrusted Origin" in resp.text


def test_06_trusted_loopback_origin_passes():
    resp = client.get(
        "/api/presets",
        headers={**AUTH_HEADERS, "Origin": "http://127.0.0.1:7860"}
    )
    assert resp.status_code == 200


def test_07_invalid_host_header_returns_403():
    resp = client.get(
        "/api/presets",
        headers={**AUTH_HEADERS, "Host": "evil-phishing.org"}
    )
    assert resp.status_code == 403
    assert "invalid Host" in resp.text


def test_08_cross_site_sec_fetch_site_returns_403():
    resp = client.get(
        "/api/presets",
        headers={**AUTH_HEADERS, "Sec-Fetch-Site": "cross-site"}
    )
    assert resp.status_code == 403
    assert "cross-site requests blocked" in resp.text


def test_09_stream_non_audio_returns_404():
    # Trying to stream a python script or spec file
    resp = client.get("/api/stream?path=Pharmakon.spec", headers=AUTH_HEADERS)
    assert resp.status_code == 404
    assert "not a supported audio stream" in resp.text


def test_10_stream_path_traversal_returns_404():
    resp = client.get(
        "/api/stream?path=../../../../windows/system32/notepad.exe",
        headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


def test_11_stream_valid_audio_returns_200(tmp_path):
    # Create a small valid test audio dummy
    test_wav = tmp_path / "stream_test.wav"
    test_wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00")
    resp = client.get(f"/api/stream?path={test_wav}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "audio/wav" in resp.headers.get("content-type", "")


def test_12_open_report_rejects_executable_or_non_html():
    resp = client.post(
        "/api/open-report",
        json={"path": "C:/Windows/System32/cmd.exe"},
        headers=AUTH_HEADERS
    )
    assert resp.status_code == 403
    assert resp.json().get("success") is False
    assert "only HTML reports" in resp.json().get("error", "")


def test_13_open_report_nonexistent_returns_404():
    resp = client.post(
        "/api/open-report",
        json={"path": "nonexistent_custom_report.html"},
        headers=AUTH_HEADERS
    )
    assert resp.status_code == 404


def test_14_upload_binary_rejects_unauthorized_extensions():
    resp = client.post(
        "/api/upload-binary?filename=malware.exe",
        content=b"test malicious payload",
        headers=AUTH_HEADERS
    )
    assert resp.status_code == 400
    assert "Invalid file type" in resp.text


def test_15_upload_binary_rejects_oversized_payload():
    # Simulate Content-Length header exceeding 250MB
    headers = dict(AUTH_HEADERS)
    headers["content-length"] = str(300 * 1024 * 1024)
    resp = client.post(
        "/api/upload-binary?filename=large_mix.wav",
        headers=headers
    )
    assert resp.status_code == 413
    assert "File too large" in resp.text


def test_16_static_path_traversal_returns_404():
    resp = client.get("/static/..%2f..%2fPharmakon.spec")
    assert resp.status_code == 404


def test_17_reveal_nonexistent_path_returns_404():
    resp = client.post(
        "/api/reveal",
        json={"path": "Z:/NonExistent/Directory/File.wav"},
        headers=AUTH_HEADERS
    )
    assert resp.status_code == 404
    assert resp.json().get("success") is False


def test_18_ed25519_manifest_cryptographic_verification():
    # Generate ephemeral keypair
    privkey = ed25519.Ed25519PrivateKey.generate()
    pubkey = privkey.public_key()
    pubkey_b64 = base64.b64encode(
        pubkey.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    ).decode("ascii")

    manifest = {
        "version": "3.1.0",
        "channel": "stable",
        "files": {
            "auto_updater.py": "abc123hash",
            "gui/server.py": "def456hash"
        }
    }

    # 1. Sign canonical bytes
    canon_bytes = auto_updater.canonical_json_bytes(manifest)
    sig_bytes = privkey.sign(canon_bytes)
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    # 2. Verify valid signature with matching pubkey
    valid = auto_updater.verify_manifest_signature(manifest, sig_b64, pubkey_b64)
    assert valid is True

    # 3. Tamper manifest content -> verification MUST fail
    tampered_manifest = dict(manifest)
    tampered_manifest["version"] = "3.2.0_hacked"
    invalid_tampered = auto_updater.verify_manifest_signature(tampered_manifest, sig_b64, pubkey_b64)
    assert invalid_tampered is False

    # 4. Tamper signature bytes -> verification MUST fail
    invalid_sig = auto_updater.verify_manifest_signature(manifest, sig_b64[:-4] + "AAAA", pubkey_b64)
    assert invalid_sig is False
