"""
PHARMAKON — Signed Patch Updater

Security model (fail closed):
  * An update is described by `release_manifest.json` (version, git tag, per-file SHA-256) and a
    detached Ed25519 signature `release_manifest.json.sig`. The matching PUBLIC key is embedded below.
  * Nothing is downloaded-and-run unless the signature verifies AND every file hash matches.
  * Updates are never applied silently: the app only reports "update_available"; files are
    downloaded and installed only after an explicit user action (apply=True).
  * Files are fetched from the immutable release tag named in the signed manifest, never from `master`.
  * Only the files in ALLOWED_PATCH_FILES can ever be installed.
  * Installed patches are re-verified (signature + hashes) every time they are loaded.
  * If no public key is configured or `cryptography` is missing, updates are notify-only.
Release tooling: tools/release_tool.py (keygen / build / sign / verify).
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

RAW_HOST = "https://raw.githubusercontent.com/alex-gerek/PHARMAKON"
MANIFEST_REF = "master"          # only the SIGNED manifest is read from here; code comes from a pinned tag
MANIFEST_NAME = "release_manifest.json"
SIGNATURE_NAME = "release_manifest.json.sig"

# Base64 of the 32-byte Ed25519 PUBLIC key (generate with `python tools/release_tool.py keygen`).
# Empty = signature verification impossible = updates are notify-only.
UPDATE_PUBLIC_KEY_B64 = ""

ALLOWED_PATCH_FILES = frozenset({
    "remaster_engine.py",
    "track_map_engine.py",
    "gui/server.py",
    "gui/security.py",
    "gui/static/index.html",
    "gui/static/app.js",
    "gui/static/style.css",
})
MAX_PATCH_FILE_BYTES = 8 * 1024 * 1024
_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
RELEASE_PAGE_URL = "https://github.com/alex-gerek/PHARMAKON/releases/tag/v3.0.0"
FALLBACK_VERSION = "3.0.0"

_LAST_UPDATE_STATUS = {
    "state": "idle",
    "local_version": FALLBACK_VERSION,
    "remote_version": None,
    "updated_just_now": False,
    "notes": "",
    "release_url": RELEASE_PAGE_URL,
    "checked_at": None,
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
        fallback = appdata / "PHARMAKON_2" / "_live_patches"
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


def _read_json_safe(p: Path):
    try:
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("app") == "PHARMAKON":
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


# ----------------------------------------------------------------------------- verification

def verify_manifest_signature(manifest_bytes: bytes, sig_b64: bytes, pubkey_b64: str = None) -> bool:
    """True only if `sig_b64` is a valid Ed25519 signature of `manifest_bytes`. Fails closed."""
    key_b64 = UPDATE_PUBLIC_KEY_B64 if pubkey_b64 is None else pubkey_b64
    if not key_b64:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64, validate=True))
        pub.verify(base64.b64decode(bytes(sig_b64).strip(), validate=True), manifest_bytes)
        return True
    except Exception:
        return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_files(manifest: dict):
    """Validated {path: sha256} map from a manifest, or None if anything is out of policy."""
    files = manifest.get("files")
    if manifest.get("app") != "PHARMAKON" or not isinstance(files, dict) or not files:
        return None
    if not _TAG_RE.match(str(manifest.get("ref", ""))):
        return None
    out = {}
    for rel, meta in files.items():
        if rel not in ALLOWED_PATCH_FILES or not isinstance(meta, dict):
            return None
        digest = str(meta.get("sha256", "")).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            return None
        out[rel] = digest
    return out


_VERIFY_CACHE = {}


def _verified_installed_files(patch_dir: Path):
    """Re-verify the installed overlay: signature of the stored manifest + hash of every file.
    Returns the set of verified relative paths, or None if the overlay must not be used."""
    try:
        mf = patch_dir / MANIFEST_NAME
        sg = patch_dir / SIGNATURE_NAME
        if not mf.is_file() or not sg.is_file():
            return None
        # cache key covers the manifest, signature AND every installed patch file (mtime/size/inode),
        # so editing any installed file invalidates the cached verdict
        stat_key = tuple(
            (str(p.relative_to(patch_dir)), st.st_mtime_ns, st.st_size, st.st_ino)
            for p in sorted(q for q in patch_dir.rglob("*") if q.is_file())
            for st in (p.stat(),)
        )
        key = (str(patch_dir), stat_key, UPDATE_PUBLIC_KEY_B64)
        if key in _VERIFY_CACHE:
            return _VERIFY_CACHE[key]
        result = None
        raw = mf.read_bytes()
        if verify_manifest_signature(raw, sg.read_bytes()):
            files = _manifest_files(json.loads(raw.decode("utf-8")))
            if files is not None:
                ok = True
                for rel, digest in files.items():
                    fp = patch_dir / rel
                    if not fp.is_file() or _sha256(fp.read_bytes()) != digest:
                        ok = False
                        break
                if ok:
                    result = frozenset(files)
        _VERIFY_CACHE.clear()
        _VERIFY_CACHE[key] = result
        return result
    except Exception:
        return None


def is_verified_overlay_file(rel_path: str) -> bool:
    verified = _verified_installed_files(resolve_live_patch_dir())
    return bool(verified) and rel_path in verified


def get_active_version_info() -> dict:
    bundled = get_bundled_version_info()
    patch_dir = resolve_live_patch_dir()
    patched = _read_json_safe(patch_dir / "VERSION.json")
    if (patched and parse_version(patched.get("version", "")) > parse_version(bundled.get("version", ""))
            and _verified_installed_files(patch_dir) is not None):
        return patched
    return bundled


def has_newer_live_patch() -> bool:
    bundled = get_bundled_version_info()
    patch_dir = resolve_live_patch_dir()
    patched = _read_json_safe(patch_dir / "VERSION.json")
    if not patched:
        return False
    if not parse_version(patched.get("version", "")) > parse_version(bundled.get("version", "")):
        return False
    return _verified_installed_files(patch_dir) is not None


def get_effective_static_dir(default_static_dir: Path) -> Path:
    env_dir = os.environ.get("PHARMAKON_STATIC_DIR")
    if env_dir and (Path(env_dir) / "index.html").is_file():
        return Path(env_dir)
    if has_newer_live_patch():
        patched_static = resolve_live_patch_dir() / "gui" / "static"
        if (patched_static / "index.html").is_file() and is_verified_overlay_file("gui/static/index.html"):
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
    Mounts live-patched modules & static UI assets ahead of the bundled copies, but ONLY if the
    installed overlay passes signature + hash verification. Any failure -> bundled code is used.
    """
    if not has_newer_live_patch():
        return False
    patch_dir = resolve_live_patch_dir()
    verified = _verified_installed_files(patch_dir) or frozenset()

    patched_static = patch_dir / "gui" / "static"
    if (patched_static / "index.html").is_file() and "gui/static/index.html" in verified:
        os.environ["PHARMAKON_STATIC_DIR"] = str(patched_static)

    saved_engine = sys.modules.get("remaster_engine")
    try:
        if "track_map_engine.py" in verified:
            new_tm = _load_module_from_file("track_map_engine", patch_dir / "track_map_engine.py")
            for mod_key in ("gui.server", "remaster_engine", "__main__"):
                m = sys.modules.get(mod_key)
                if m is not None and hasattr(m, "track_map_engine"):
                    setattr(m, "track_map_engine", new_tm)

        if "remaster_engine.py" in verified:
            new_eng = _load_module_from_file("remaster_engine", patch_dir / "remaster_engine.py")
            for mod_key in ("gui.server", "__main__"):
                m = sys.modules.get(mod_key)
                if m is not None and hasattr(m, "remaster_engine"):
                    setattr(m, "remaster_engine", new_eng)

        if load_server and "gui/server.py" in verified:
            if "gui" not in sys.modules:
                pkg = types.ModuleType("gui")
                pkg.__path__ = [str(patch_dir / "gui")]
                sys.modules["gui"] = pkg
            _load_module_from_file("gui.server", patch_dir / "gui" / "server.py")
        return True
    except Exception as exc:
        if saved_engine is not None:
            sys.modules["remaster_engine"] = saved_engine
        else:
            sys.modules.pop("remaster_engine", None)
        os.environ.pop("PHARMAKON_STATIC_DIR", None)
        print(f"[AUTO-UPDATE] Fallback to built-in bundle ({exc})")
        return False


# ----------------------------------------------------------------------------- network

def _fetch_bytes(url: str, timeout: float, max_bytes: int = MAX_PATCH_FILE_BYTES) -> bytes:
    if not url.startswith("https://"):
        raise urllib.error.URLError("HTTPS required")
    req = urllib.request.Request(
        url, headers={"User-Agent": "PHARMAKON-Studio-Updater/3.1", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise urllib.error.URLError(f"HTTP {resp.status}")
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Download exceeds size limit")
    return data


def _status(state, local_ver, remote_ver=None, notes="", rel_url=RELEASE_PAGE_URL, **extra):
    global _LAST_UPDATE_STATUS
    st = {"state": state, "local_version": local_ver, "remote_version": remote_ver,
          "updated_just_now": state == "updated", "notes": notes, "release_url": rel_url,
          "checked_at": int(time.time())}
    st.update(extra)
    _LAST_UPDATE_STATUS = st
    return st


def sync_online_patches(apply: bool = False, timeout: float = 2.5) -> dict:
    """
    Check for a signed release newer than the running version.
      apply=False (default, used at launch): only report 'update_available'; nothing is installed.
      apply=True  (explicit user click): download from the pinned tag, verify, install, hot-load.
    """
    active_info = get_active_version_info()
    local_ver = active_info.get("version", FALLBACK_VERSION)
    prev_notes = active_info.get("notes", "")

    try:
        manifest_bytes = _fetch_bytes(f"{RAW_HOST}/{MANIFEST_REF}/{MANIFEST_NAME}", timeout, 1024 * 1024)
        sig_bytes = _fetch_bytes(f"{RAW_HOST}/{MANIFEST_REF}/{SIGNATURE_NAME}", timeout, 4096)
    except Exception:
        return _status("offline", local_ver, notes=prev_notes,
                       rel_url=active_info.get("release_url", RELEASE_PAGE_URL))

    verified = verify_manifest_signature(manifest_bytes, sig_bytes)
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except Exception:
        manifest = None
    if not isinstance(manifest, dict) or manifest.get("app") != "PHARMAKON":
        return _status("offline", local_ver, notes=prev_notes)

    remote_ver = str(manifest.get("version", local_ver))
    notes = str(manifest.get("notes", ""))
    rel_url = str(manifest.get("release_url", RELEASE_PAGE_URL))
    if not rel_url.startswith("https://github.com/alex-gerek/PHARMAKON/"):
        rel_url = RELEASE_PAGE_URL

    if parse_version(remote_ver) <= parse_version(local_ver):
        return _status("up_to_date", local_ver, remote_ver, notes, rel_url)

    # Announce only. The remote notes are shown as untrusted text unless the signature verified.
    if not verified:
        return _status("update_available", local_ver, remote_ver, notes if verified else "", rel_url,
                       signature_verified=False,
                       error="Update signature could not be verified; install it manually from the release page.")
    if not apply:
        return _status("update_available", local_ver, remote_ver, notes, rel_url, signature_verified=True)

    files = _manifest_files(manifest)
    if files is None:
        return _status("update_available", local_ver, remote_ver, notes, rel_url,
                       signature_verified=True, error="Manifest violates update policy")

    project_dir, _ = get_paths()
    patch_dir = resolve_live_patch_dir()
    staging_dir = patch_dir.parent / "_live_patches_staging"
    ref = manifest["ref"]
    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        for rel, digest in files.items():
            data = _fetch_bytes(f"{RAW_HOST}/{ref}/{rel}", max(timeout, 8.0))
            if _sha256(data) != digest:
                raise ValueError(f"Hash mismatch for {rel}")
            if rel.endswith(".py"):
                compile(data.decode("utf-8"), rel, "exec")
            dest = staging_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        (staging_dir / MANIFEST_NAME).write_bytes(manifest_bytes)
        (staging_dir / SIGNATURE_NAME).write_bytes(sig_bytes)
        (staging_dir / "VERSION.json").write_text(json.dumps(
            {"app": "PHARMAKON", "version": remote_ver, "notes": notes, "release_url": rel_url,
             "channel": manifest.get("channel", "production")}, indent=2), encoding="utf-8")

        # Replace the overlay as a unit so a failure never leaves a half-updated mix.
        old_dir = patch_dir.parent / "_live_patches_old"
        shutil.rmtree(old_dir, ignore_errors=True)
        if patch_dir.exists():
            patch_dir.rename(old_dir)
        try:
            staging_dir.rename(patch_dir)
        except Exception:
            if old_dir.exists() and not patch_dir.exists():
                old_dir.rename(patch_dir)
            raise
        shutil.rmtree(old_dir, ignore_errors=True)

        activate_live_patches(load_server=False)
        return _status("updated", remote_ver, remote_ver, notes, rel_url,
                       previous_version=local_ver, signature_verified=True)
    except Exception as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        return _status("update_available", local_ver, remote_ver, notes, rel_url,
                       signature_verified=True, error=str(exc))


def get_cached_status() -> dict:
    info = get_active_version_info()
    st = dict(_LAST_UPDATE_STATUS)
    st["local_version"] = info.get("version", FALLBACK_VERSION)
    return st
