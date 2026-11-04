"""
PHARMAKON 2.0 — Smart Online Patch Sync & Live Overlay Updater
Checks GitHub repository for verified DSP/UI patches when online,
stages & syntax-validates updates atomically, and remains 100% functional offline.
"""

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

RAW_BASE_URL = "https://raw.githubusercontent.com/alex-gerek/PHARMAKON/master"
RELEASE_PAGE_URL = "https://github.com/alex-gerek/PHARMAKON/releases/tag/v2.0.3"
FALLBACK_VERSION = "2.0.3"

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
    Mounts verified live-patched modules & static UI assets ahead of frozen PYZ bundle.
    Safe rollback: if any patched file fails to load, restores default behavior cleanly.
    """
    if not has_newer_live_patch():
        return False

    patch_dir = resolve_live_patch_dir()
    patched_static = patch_dir / "gui" / "static"
    if (patched_static / "index.html").is_file():
        os.environ["PHARMAKON_STATIC_DIR"] = str(patched_static)

    saved_engine = sys.modules.get("remaster_engine")
    try:
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


def _validate_downloaded_file(rel_path: str, raw_bytes: bytes) -> bool:
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False

    if len(text) < 64:
        return False

    if rel_path.endswith(".py"):
        if "PHARMAKON" not in text:
            return False
        try:
            compile(text, rel_path, "exec")
        except SyntaxError:
            return False
    elif rel_path.endswith(".html"):
        if "PHARMAKON" not in text or "</html>" not in text.lower():
            return False
    elif rel_path.endswith(".js"):
        if "runPharmakonProcess" not in text:
            return False
    return True


def _fetch_bytes(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "PHARMAKON-Studio-AutoSync/2.0",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise urllib.error.URLError(f"HTTP {resp.status}")
        return resp.read()


def sync_online_patches(force_apply_in_git: bool = False, timeout: float = 2.5) -> dict:
    """
    Checks GitHub master VERSION.json. If a newer version exists:
    - Downloads and validates all patch files atomically into _live_patches/
    - Hot-reloads remaster_engine & static assets in memory
    - Gracefully returns 'offline' when no internet connection is available
    """
    global _LAST_UPDATE_STATUS
    project_dir, _ = get_paths()
    active_info = get_active_version_info()
    local_ver = active_info.get("version", FALLBACK_VERSION)
    ts = int(time.time())

    try:
        raw_manifest = _fetch_bytes(f"{RAW_BASE_URL}/VERSION.json?t={ts}", timeout=timeout)
        remote_info = json.loads(raw_manifest.decode("utf-8"))
    except Exception:
        status = {
            "state": "offline",
            "local_version": local_ver,
            "remote_version": None,
            "updated_just_now": _LAST_UPDATE_STATUS.get("updated_just_now", False),
            "notes": active_info.get("notes", ""),
            "release_url": active_info.get("release_url", RELEASE_PAGE_URL),
            "checked_at": ts,
        }
        _LAST_UPDATE_STATUS = status
        return status

    if not isinstance(remote_info, dict) or remote_info.get("app") != "PHARMAKON":
        status = {
            "state": "offline",
            "local_version": local_ver,
            "remote_version": None,
            "updated_just_now": False,
            "notes": active_info.get("notes", ""),
            "release_url": RELEASE_PAGE_URL,
            "checked_at": ts,
        }
        _LAST_UPDATE_STATUS = status
        return status

    remote_ver = str(remote_info.get("version", local_ver))
    notes = str(remote_info.get("notes", ""))
    rel_url = str(remote_info.get("release_url", RELEASE_PAGE_URL))

    if parse_version(remote_ver) <= parse_version(local_ver):
        status = {
            "state": "up_to_date",
            "local_version": local_ver,
            "remote_version": remote_ver,
            "updated_just_now": _LAST_UPDATE_STATUS.get("updated_just_now", False),
            "notes": notes,
            "release_url": rel_url,
            "checked_at": ts,
        }
        _LAST_UPDATE_STATUS = status
        return status

    # Developer git workspace protection: notify without overwriting unless explicitly clicked
    is_git_repo = (project_dir / ".git").exists() and not getattr(sys, "frozen", False)
    if is_git_repo and not force_apply_in_git:
        status = {
            "state": "update_available",
            "local_version": local_ver,
            "remote_version": remote_ver,
            "updated_just_now": False,
            "notes": notes,
            "release_url": rel_url,
            "checked_at": ts,
        }
        _LAST_UPDATE_STATUS = status
        return status

    # Download & validate all patch files into temporary staging directory
    patch_files = remote_info.get("patch_files") or [
        "remaster_engine.py",
        "gui/server.py",
        "gui/static/index.html",
        "gui/static/app.js",
        "gui/static/style.css",
    ]

    patch_dir = resolve_live_patch_dir()
    staging_dir = patch_dir.parent / "_live_patches_staging"
    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        for rel_file in patch_files:
            clean_rel = rel_file.strip("/").replace("\\", "/")
            if ".." in clean_rel:
                raise ValueError(f"Unsafe path in manifest: {clean_rel}")
            raw_data = _fetch_bytes(f"{RAW_BASE_URL}/{clean_rel}?t={ts}", timeout=max(timeout, 6.0))
            if not _validate_downloaded_file(clean_rel, raw_data):
                raise ValueError(f"Validation failed for {clean_rel}")
            dest_file = staging_dir / clean_rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            dest_file.write_bytes(raw_data)

        (staging_dir / "VERSION.json").write_text(
            json.dumps(remote_info, indent=2), encoding="utf-8"
        )

        # Ensure companion static assets (icons/SVGs) exist in live patch static dir
        _, base_dir = get_paths()
        orig_static = base_dir / "gui" / "static"
        patch_static = patch_dir / "gui" / "static"
        if orig_static.is_dir():
            patch_static.mkdir(parents=True, exist_ok=True)
            for asset in orig_static.iterdir():
                if asset.is_file() and not (patch_static / asset.name).exists():
                    shutil.copy2(asset, patch_static / asset.name)

        # Commit validated staging files into live patch overlay
        for item in staging_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(staging_dir)
                target = patch_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

        shutil.rmtree(staging_dir, ignore_errors=True)

        # Hot-activate updated DSP engine & static assets immediately
        activate_live_patches(load_server=False)

        status = {
            "state": "updated",
            "previous_version": local_ver,
            "local_version": remote_ver,
            "remote_version": remote_ver,
            "updated_just_now": True,
            "notes": notes,
            "release_url": rel_url,
            "checked_at": ts,
        }
        _LAST_UPDATE_STATUS = status
        return status
    except Exception as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        status = {
            "state": "update_available",
            "local_version": local_ver,
            "remote_version": remote_ver,
            "updated_just_now": False,
            "notes": notes,
            "release_url": rel_url,
            "error": str(exc),
            "checked_at": ts,
        }
        _LAST_UPDATE_STATUS = status
        return status


def get_cached_status() -> dict:
    info = get_active_version_info()
    st = dict(_LAST_UPDATE_STATUS)
    st["local_version"] = info.get("version", FALLBACK_VERSION)
    return st
