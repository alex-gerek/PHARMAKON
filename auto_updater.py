"""
PHARMAKON 3.1 — Hardened Cryptographic Online Patch Sync & Live Overlay Updater
Features:
- Ed25519 signature verification + SHA-256 manifest validation
- Tag-based releases (v{version}) instead of rolling master
- Non-destructive update check (check notifies, user explicitly clicks install)
- Dynamic re-verification of cached live patches on every startup
"""

import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import types
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519

# Ed25519 Public Key for PHARMAKON official updates
UPDATE_PUBLIC_KEY_B64 = "xGVv4GtJMLb5ozFQabRgKGbGQ+4f6GXjmgMXMcKbV4Q="

RAW_BASE_URL = "https://raw.githubusercontent.com/alex-gerek/PHARMAKON/master"
TAG_BASE_URL = "https://raw.githubusercontent.com/alex-gerek/PHARMAKON/v{version}"
RELEASE_PAGE_URL = "https://github.com/alex-gerek/PHARMAKON/releases/tag/v3.2.0"
FALLBACK_VERSION = "3.2.0"

_LAST_UPDATE_STATUS = {
    "state": "idle",
    "local_version": FALLBACK_VERSION,
    "remote_version": None,
    "signature_verified": False,
    "update_available": False,
    "updated_just_now": False,
    "notes": "",
    "release_url": RELEASE_PAGE_URL,
    "checked_at": None,
    "error": None,
}


def get_paths():
    if getattr(sys, "frozen", False):
        project_dir = Path(sys.executable).resolve().parent
        base_dir = Path(getattr(sys, "_MEIPASS", project_dir))
    else:
        project_dir = Path(__file__).resolve().parent
        base_dir = project_dir
    return project_dir, base_dir


def resolve_live_patch_dir() -> Path:
    project_dir, _ = get_paths()
    preferred = project_dir / "_live_patches"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except Exception:
        appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        fallback = appdata / "PHARMAKON" / "_live_patches"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def parse_version(v_str: str) -> tuple:
    if not v_str or not isinstance(v_str, str):
        return (0, 0, 0)
    nums = re.findall(r"\d+", v_str)
    parts = [int(x) for x in nums[:4]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def canonical_json_bytes(obj: dict) -> bytes:
    """Returns deterministic canonical UTF-8 JSON bytes for cryptographic verification."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')


def hash_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest_signature(manifest_dict: dict, sig_b64: str, pubkey_b64: str = UPDATE_PUBLIC_KEY_B64) -> bool:
    """Verifies that the manifest dictionary was signed by the official PHARMAKON Ed25519 private key."""
    try:
        sig_bytes = base64.b64decode(sig_b64.strip())
        pub_bytes = base64.b64decode(pubkey_b64.strip())
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        canon_bytes = canonical_json_bytes(manifest_dict)
        pub_key.verify(sig_bytes, canon_bytes)
        return True
    except Exception:
        return False


def _read_json_safe(p: Path):
    try:
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def get_bundled_version_info() -> dict:
    project_dir, base_dir = get_paths()
    for candidate in (base_dir / "VERSION.json", project_dir / "VERSION.json"):
        data = _read_json_safe(candidate)
        if data:
            return data
    return {"app": "PHARMAKON", "version": FALLBACK_VERSION, "release_url": RELEASE_PAGE_URL}


def get_active_version_info() -> dict:
    bundled = get_bundled_version_info()
    patch_dir = resolve_live_patch_dir()
    patched = _read_json_safe(patch_dir / "VERSION.json")
    if patched and parse_version(patched.get("version", "")) > parse_version(bundled.get("version", "")):
        return patched
    return bundled


def has_newer_live_patch() -> bool:
    bundled = get_bundled_version_info()
    patch_dir = resolve_live_patch_dir()
    patched = _read_json_safe(patch_dir / "VERSION.json")
    if not patched:
        return False
    return parse_version(patched.get("version", "")) > parse_version(bundled.get("version", ""))


def get_effective_static_dir(default_static_dir: Path) -> Path:
    env_dir = os.environ.get("PHARMAKON_STATIC_DIR")
    if env_dir and (Path(env_dir) / "index.html").is_file():
        return Path(env_dir)
    if has_newer_live_patch():
        patched_static = resolve_live_patch_dir() / "gui" / "static"
        if (patched_static / "index.html").is_file():
            return patched_static
    return default_static_dir


def _load_module_from_file(mod_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not create spec for {mod_name} at {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def activate_live_patches(load_server: bool = False) -> bool:
    """
    Mounts verified live-patched modules & static UI assets.
    Security Guard: Re-verifies file SHA-256 against VERSION.json before loading.
    Rolls back safely to built-in bundle if any file fails integrity check.
    """
    if not has_newer_live_patch():
        return False

    patch_dir = resolve_live_patch_dir()
    manifest = _read_json_safe(patch_dir / "VERSION.json")
    if not manifest:
        return False

    # Verify integrity of each patched file
    expected_files = manifest.get("files", {})
    for rel_path, expected_hash in expected_files.items():
        fpath = patch_dir / rel_path
        if not fpath.exists():
            print(f"[SECURITY] Live patch missing expected file {rel_path}. Fallback to bundle.")
            return False
        actual_hash = hash_file_sha256(fpath)
        if actual_hash != expected_hash:
            print(f"[SECURITY] Live patch hash mismatch on {rel_path}. Tampering detected. Fallback.")
            return False

    patched_static = patch_dir / "gui" / "static"
    if (patched_static / "index.html").is_file():
        os.environ["PHARMAKON_STATIC_DIR"] = str(patched_static)

    saved_engine = sys.modules.get("remaster_engine")
    try:
        tm_file = patch_dir / "track_map_engine.py"
        if tm_file.is_file():
            new_tm = _load_module_from_file("track_map_engine", tm_file)
            for mod_key in ("gui.server", "remaster_engine", "__main__"):
                m = sys.modules.get(mod_key)
                if m is not None and hasattr(m, "track_map_engine"):
                    setattr(m, "track_map_engine", new_tm)

        eng_file = patch_dir / "remaster_engine.py"
        if eng_file.is_file():
            new_eng = _load_module_from_file("remaster_engine", eng_file)
            for mod_key in ("gui.server", "__main__"):
                m = sys.modules.get(mod_key)
                if m is not None and hasattr(m, "remaster_engine"):
                    setattr(m, "remaster_engine", new_eng)

        if load_server:
            srv_file = patch_dir / "gui" / "server.py"
            if srv_file.is_file():
                if "gui" not in sys.modules:
                    pkg = types.ModuleType("gui")
                    pkg.__path__ = [str(patch_dir / "gui")]
                    sys.modules["gui"] = pkg
                _load_module_from_file("gui.server", srv_file)
        return True
    except Exception as exc:
        if saved_engine is not None:
            sys.modules["remaster_engine"] = saved_engine
        else:
            sys.modules.pop("remaster_engine", None)
        os.environ.pop("PHARMAKON_STATIC_DIR", None)
        print(f"[AUTO-UPDATE] Fallback to built-in bundle ({exc})")
        return False


def _fetch_bytes(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PHARMAKON-Studio-AutoSync/3.1",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise urllib.error.URLError(f"HTTP {resp.status}")
        return resp.read()


def check_online_updates(timeout: float = 3.0) -> dict:
    """
    Checks GitHub for new signed updates.
    Verifies Ed25519 signature before notifying the user.
    NEVER installs automatically — sets state for user confirmation.
    """
    global _LAST_UPDATE_STATUS
    active_info = get_active_version_info()
    local_ver = active_info.get("version", FALLBACK_VERSION)
    ts = int(time.time())

    try:
        raw_manifest = _fetch_bytes(f"{RAW_BASE_URL}/VERSION.json?t={ts}", timeout=timeout)
        remote_info = json.loads(raw_manifest.decode("utf-8"))
        raw_sig = _fetch_bytes(f"{RAW_BASE_URL}/VERSION.json.sig?t={ts}", timeout=timeout).decode("utf-8").strip()
    except Exception:
        status = {
            "state": "offline",
            "local_version": local_ver,
            "remote_version": None,
            "signature_verified": False,
            "update_available": False,
            "updated_just_now": _LAST_UPDATE_STATUS.get("updated_just_now", False),
            "notes": active_info.get("notes", ""),
            "release_url": active_info.get("release_url", RELEASE_PAGE_URL),
            "checked_at": ts,
            "error": None,
        }
        _LAST_UPDATE_STATUS = status
        return status

    # Verify Ed25519 signature
    sig_valid = verify_manifest_signature(remote_info, raw_sig, UPDATE_PUBLIC_KEY_B64)
    remote_ver = str(remote_info.get("version", local_ver))
    notes = str(remote_info.get("notes", ""))
    rel_url = str(remote_info.get("release_url", f"https://github.com/alex-gerek/PHARMAKON/releases/tag/v{remote_ver}"))

    if not sig_valid:
        status = {
            "state": "signature_invalid",
            "local_version": local_ver,
            "remote_version": remote_ver,
            "signature_verified": False,
            "update_available": False,
            "updated_just_now": False,
            "notes": notes,
            "release_url": rel_url,
            "checked_at": ts,
            "error": "Cryptographic signature verification failed! Untrusted release.",
        }
        _LAST_UPDATE_STATUS = status
        return status

    if parse_version(remote_ver) <= parse_version(local_ver):
        status = {
            "state": "up_to_date",
            "local_version": local_ver,
            "remote_version": remote_ver,
            "signature_verified": True,
            "update_available": False,
            "updated_just_now": _LAST_UPDATE_STATUS.get("updated_just_now", False),
            "notes": notes,
            "release_url": rel_url,
            "checked_at": ts,
            "error": None,
        }
    else:
        status = {
            "state": "update_available",
            "local_version": local_ver,
            "remote_version": remote_ver,
            "signature_verified": True,
            "update_available": True,
            "updated_just_now": False,
            "notes": notes,
            "release_url": rel_url,
            "checked_at": ts,
            "error": None,
        }

    _LAST_UPDATE_STATUS = status
    return status


def install_verified_update(timeout: float = 10.0) -> dict:
    """
    Downloads and installs files from the verified release tag v{version}.
    Validates SHA-256 hash of each file before staging.
    """
    global _LAST_UPDATE_STATUS
    active_info = get_active_version_info()
    local_ver = active_info.get("version", FALLBACK_VERSION)
    ts = int(time.time())

    # Pre-check update status
    chk = check_online_updates(timeout=timeout)
    if not chk.get("signature_verified") or not chk.get("update_available"):
        return chk

    remote_ver = chk["remote_version"]
    tag_url = TAG_BASE_URL.format(version=remote_ver)

    # Re-fetch manifest from tag
    try:
        raw_manifest = _fetch_bytes(f"{tag_url}/VERSION.json", timeout=timeout)
        manifest = json.loads(raw_manifest.decode("utf-8"))
        raw_sig = _fetch_bytes(f"{tag_url}/VERSION.json.sig", timeout=timeout).decode("utf-8").strip()
    except Exception as exc:
        chk["error"] = f"Failed to download release manifest: {exc}"
        return chk

    if not verify_manifest_signature(manifest, raw_sig, UPDATE_PUBLIC_KEY_B64):
        chk["signature_verified"] = False
        chk["error"] = "Signature verification failed on release tag."
        return chk

    files_to_download = manifest.get("files", {})
    if not files_to_download:
        chk["error"] = "No files declared in manifest."
        return chk

    patch_dir = resolve_live_patch_dir()
    staging_dir = patch_dir.parent / "_live_patches_staging"

    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        for rel_name, expected_hash in files_to_download.items():
            clean_rel = rel_name.strip("/").replace("\\", "/")
            if ".." in clean_rel:
                raise ValueError(f"Unsafe path in manifest: {clean_rel}")

            raw_bytes = _fetch_bytes(f"{tag_url}/{clean_rel}", timeout=timeout)
            calc_hash = hashlib.sha256(raw_bytes).hexdigest()
            if calc_hash != expected_hash:
                raise ValueError(f"Hash mismatch on {clean_rel}: expected {expected_hash}, got {calc_hash}")

            dest = staging_dir / clean_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw_bytes)

        # Write manifest and signature to staging
        (staging_dir / "VERSION.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (staging_dir / "VERSION.json.sig").write_text(raw_sig, encoding="utf-8")

        # Copy to live patch directory
        for item in staging_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(staging_dir)
                target = patch_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

        shutil.rmtree(staging_dir, ignore_errors=True)
        activate_live_patches(load_server=False)

        res = {
            "state": "updated",
            "previous_version": local_ver,
            "local_version": remote_ver,
            "remote_version": remote_ver,
            "signature_verified": True,
            "update_available": False,
            "updated_just_now": True,
            "notes": manifest.get("notes", ""),
            "release_url": chk["release_url"],
            "checked_at": ts,
            "error": None,
        }
        _LAST_UPDATE_STATUS = res
        return res
    except Exception as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        chk["error"] = str(exc)
        _LAST_UPDATE_STATUS = chk
        return chk


def get_cached_status() -> dict:
    info = get_active_version_info()
    st = dict(_LAST_UPDATE_STATUS)
    st["local_version"] = info.get("version", FALLBACK_VERSION)
    return st
