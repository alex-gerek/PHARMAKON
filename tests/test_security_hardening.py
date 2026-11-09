"""Security regression tests: local-server guard and signed updater (no FastAPI / network needed)."""
import base64
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gui"))

import auto_updater  # noqa: E402
import security  # noqa: E402

pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402


# ------------------------------------------------------------------ server guard
@pytest.fixture()
def client():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    async def index(request):
        return JSONResponse({"page": "ui"})

    async def secret(request):
        return JSONResponse({"secret": 1})

    async def ping(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/", index), Route("/api/secret", secret, methods=["GET", "POST"]),
                            Route("/api/ping", ping)])
    app.add_middleware(security.LocalGuardMiddleware, token="T" * 43, port=7860)
    return TestClient(app, base_url="http://127.0.0.1:7860")


def test_api_requires_token(client):
    assert client.get("/api/secret").status_code == 401
    assert client.post("/api/secret").status_code == 401


def test_ping_is_public_and_leaks_nothing(client):
    r = client.get("/api/ping")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_ui_load_sets_strict_httponly_cookie_then_api_works(client):
    r = client.get("/")
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert client.get("/api/secret").status_code == 200


def test_token_header_works_for_tools(client):
    assert client.get("/api/secret", headers={"X-Pharmakon-Token": "T" * 43}).status_code == 200
    assert client.get("/api/secret", headers={"X-Pharmakon-Token": "wrong"}).status_code == 401


def test_dns_rebinding_host_blocked(client):
    r = client.get("/api/secret", headers={"Host": "evil.example:7860", "X-Pharmakon-Token": "T" * 43})
    assert r.status_code == 403


def test_foreign_origin_blocked_even_with_token(client):
    r = client.post("/api/secret", headers={"Origin": "https://evil.example", "X-Pharmakon-Token": "T" * 43})
    assert r.status_code == 403


def test_cross_site_fetch_blocked(client):
    r = client.get("/api/secret", headers={"Sec-Fetch-Site": "cross-site", "X-Pharmakon-Token": "T" * 43})
    assert r.status_code == 403


def test_no_cors_headers_emitted(client):
    r = client.get("/api/ping", headers={"Origin": "http://127.0.0.1:7860"})
    assert not any(h.lower().startswith("access-control-") for h in r.headers)


def test_path_helpers():
    assert security.is_audio_path("C:/m/track.WAV") and not security.is_audio_path("C:/Users/x/.ssh/id_rsa")
    assert not security.is_audio_path("run.bat") and not security.is_audio_path("evil.exe")
    assert security.is_report_path("x - MASTERING_REPORT.html") and not security.is_report_path("calc.exe")
    assert security.is_inside("/tmp/a/b.wav", "/tmp/a") and not security.is_inside("/tmp/a/../b.wav", "/tmp/a")


def test_token_file_roundtrip(tmp_path):
    p = security.write_token_file("abc", tmp_path / "t")
    assert security.read_token_file(p) == "abc"


# ------------------------------------------------------------------ signed updater
def _keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return priv, base64.b64encode(pub).decode()


def _release(version="9.9.9", files=None, ref=None):
    files = files or {"remaster_engine.py": b"# PHARMAKON engine\n" * 10,
                      "gui/static/index.html": b"<html>PHARMAKON</html>" * 5}
    manifest = {"app": "PHARMAKON", "version": version, "ref": ref or f"v{version}", "notes": "n",
                "release_url": f"https://github.com/alex-gerek/PHARMAKON/releases/tag/v{version}",
                "files": {k: {"sha256": hashlib.sha256(v).hexdigest()} for k, v in files.items()}}
    return files, (json.dumps(manifest, sort_keys=True)).encode()


@pytest.fixture()
def updater(tmp_path, monkeypatch):
    priv, pub = _keypair()
    monkeypatch.setattr(auto_updater, "UPDATE_PUBLIC_KEY_B64", pub)
    patch_dir = tmp_path / "_live_patches"
    patch_dir.mkdir()
    monkeypatch.setattr(auto_updater, "resolve_live_patch_dir", lambda: patch_dir)
    monkeypatch.setattr(auto_updater, "get_bundled_version_info",
                        lambda: {"app": "PHARMAKON", "version": "3.0.0"})
    monkeypatch.setattr(auto_updater, "_VERIFY_CACHE", {})
    return priv, patch_dir


def _serve(monkeypatch, files, manifest, sig):
    def fake(url, timeout, max_bytes=0):
        name = url.split("/PHARMAKON/", 1)[1]
        if name == f"master/{auto_updater.MANIFEST_NAME}":
            return manifest
        if name == f"master/{auto_updater.SIGNATURE_NAME}":
            return sig
        rel = name.split("/", 1)[1]
        if rel in files:
            return files[rel]
        raise OSError("404")
    monkeypatch.setattr(auto_updater, "_fetch_bytes", fake)


def test_signature_valid_and_tamper_detected(updater):
    priv, _ = updater
    _, manifest = _release()
    sig = base64.b64encode(priv.sign(manifest))
    assert auto_updater.verify_manifest_signature(manifest, sig)
    assert not auto_updater.verify_manifest_signature(manifest + b" ", sig)
    other, _ = _keypair()
    assert not auto_updater.verify_manifest_signature(manifest, base64.b64encode(other.sign(manifest)))


def test_no_public_key_fails_closed(monkeypatch):
    monkeypatch.setattr(auto_updater, "UPDATE_PUBLIC_KEY_B64", "")
    assert not auto_updater.verify_manifest_signature(b"x", base64.b64encode(b"\0" * 64))


def test_manifest_policy_rejects_unlisted_paths_and_branch_refs():
    _, m = _release(files={"../evil.py": b"x" * 100})
    assert auto_updater._manifest_files(json.loads(m)) is None
    _, m = _release(files={"launcher.pyw": b"x" * 100})
    assert auto_updater._manifest_files(json.loads(m)) is None
    _, m = _release(ref="master")
    assert auto_updater._manifest_files(json.loads(m)) is None


def test_launch_check_never_installs(updater, monkeypatch):
    priv, patch_dir = updater
    files, manifest = _release()
    _serve(monkeypatch, files, manifest, base64.b64encode(priv.sign(manifest)))
    st = auto_updater.sync_online_patches(apply=False)
    assert st["state"] == "update_available" and st["signature_verified"] is True
    assert not (patch_dir / "remaster_engine.py").exists()


def test_signed_update_installs_and_reverifies(updater, monkeypatch):
    priv, patch_dir = updater
    files, manifest = _release()
    _serve(monkeypatch, files, manifest, base64.b64encode(priv.sign(manifest)))
    st = auto_updater.sync_online_patches(apply=True)
    assert st["state"] == "updated", st
    assert auto_updater.has_newer_live_patch()
    assert auto_updater.is_verified_overlay_file("remaster_engine.py")
    # post-install tampering disables the whole overlay
    (patch_dir / "remaster_engine.py").write_text("import os; os.system('calc')  # PHARMAKON")
    assert not auto_updater.has_newer_live_patch()
    assert not auto_updater.is_verified_overlay_file("remaster_engine.py")
    assert auto_updater.get_active_version_info()["version"] == "3.0.0"


def test_hash_mismatch_blocks_install(updater, monkeypatch):
    priv, patch_dir = updater
    files, manifest = _release()
    bad = dict(files)
    bad["remaster_engine.py"] = b"# PHARMAKON backdoor\n" * 10
    _serve(monkeypatch, bad, manifest, base64.b64encode(priv.sign(manifest)))
    st = auto_updater.sync_online_patches(apply=True)
    assert st["state"] == "update_available" and "Hash mismatch" in st["error"]
    assert not (patch_dir / "remaster_engine.py").exists()


def test_unsigned_or_wrongly_signed_is_notify_only(updater, monkeypatch):
    _, patch_dir = updater
    files, manifest = _release()
    attacker, _ = _keypair()
    _serve(monkeypatch, files, manifest, base64.b64encode(attacker.sign(manifest)))
    st = auto_updater.sync_online_patches(apply=True)
    assert st["state"] == "update_available" and st["signature_verified"] is False
    assert st["notes"] == "" and not (patch_dir / "remaster_engine.py").exists()


def test_older_signed_release_is_not_a_downgrade(updater, monkeypatch):
    priv, _ = updater
    files, manifest = _release(version="2.0.0")
    _serve(monkeypatch, files, manifest, base64.b64encode(priv.sign(manifest)))
    assert auto_updater.sync_online_patches(apply=True)["state"] == "up_to_date"
