"""Release manifest hashes must be computed on the bytes clients download (the git blob
served by raw.githubusercontent.com), never on Windows working-tree files with CRLF."""
import hashlib
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import release_tool as R  # noqa: E402


def test_release_hash_is_the_git_blob_hash():
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        for rel in ("track_map_engine.py", "gui/server.py"):
            dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel]).returncode
            if dirty:
                continue  # an uncommitted file is refused by design; nothing to compare
            blob = subprocess.run(["git", "show", f"HEAD:{rel}"], capture_output=True).stdout
            assert b"\r\n" not in blob
            assert R.release_sha256(rel) == hashlib.sha256(blob).hexdigest()
    finally:
        os.chdir(cwd)
