"""
Release tooling for the signed PHARMAKON updater (run by the maintainer, never shipped to users).

  python tools/release_tool.py keygen --out ~/pharmakon_update_private.key
      -> prints the PUBLIC key: paste it into UPDATE_PUBLIC_KEY_B64 in auto_updater.py.
         Keep the private key OFFLINE and OUT of the repository (a password manager or hardware token).

  python tools/release_tool.py build --version 3.1.0 --notes "what changed"
      -> writes release_manifest.json with the SHA-256 of every patch file (ref = tag v3.1.0).

  python tools/release_tool.py sign --key ~/pharmakon_update_private.key
      -> writes release_manifest.json.sig (Ed25519 over the exact manifest bytes).

  python tools/release_tool.py verify --pub <base64 public key>

Release order: commit code -> build -> sign -> commit manifest+sig -> create tag vX.Y.Z on the SAME
commit as the code the manifest hashes -> push tag, then push the manifest to master.
"""
import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import auto_updater  # noqa: E402

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    sys.exit("pip install cryptography")

MANIFEST = ROOT / auto_updater.MANIFEST_NAME
SIG = ROOT / auto_updater.SIGNATURE_NAME


def cmd_keygen(a):
    out = Path(a.out).expanduser()
    if out.exists():
        sys.exit(f"refusing to overwrite {out}")
    priv = Ed25519PrivateKey.generate()
    raw = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                             serialization.NoEncryption())
    out.write_text(base64.b64encode(raw).decode())
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print("Private key written to", out, "(keep it secret, never commit it)")
    print("UPDATE_PUBLIC_KEY_B64 =", repr(base64.b64encode(pub).decode()))


def cmd_build(a):
    files = {}
    for rel in sorted(auto_updater.ALLOWED_PATCH_FILES):
        p = ROOT / rel
        if p.is_file():
            files[rel] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "size": p.stat().st_size}
    manifest = {
        "app": "PHARMAKON", "version": a.version, "ref": f"v{a.version}", "channel": "production",
        "release_url": f"https://github.com/alex-gerek/PHARMAKON/releases/tag/v{a.version}",
        "notes": a.notes, "files": files,
    }
    MANIFEST.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    print(f"wrote {MANIFEST} ({len(files)} files)")


def cmd_sign(a):
    raw = base64.b64decode(Path(a.key).expanduser().read_text().strip())
    priv = Ed25519PrivateKey.from_private_bytes(raw)
    SIG.write_bytes(base64.b64encode(priv.sign(MANIFEST.read_bytes())))
    print(f"wrote {SIG}")


def cmd_verify(a):
    pub = a.pub or auto_updater.UPDATE_PUBLIC_KEY_B64
    ok = auto_updater.verify_manifest_signature(MANIFEST.read_bytes(), SIG.read_bytes(), pub)
    files = auto_updater._manifest_files(json.loads(MANIFEST.read_text()))
    hashes_ok = files is not None and all(
        hashlib.sha256((ROOT / r).read_bytes()).hexdigest() == d for r, d in files.items())
    print("signature:", "OK" if ok else "INVALID", "| hashes:", "OK" if hashes_ok else "MISMATCH")
    sys.exit(0 if ok and hashes_ok else 1)


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
k = sub.add_parser("keygen"); k.add_argument("--out", required=True); k.set_defaults(f=cmd_keygen)
b = sub.add_parser("build"); b.add_argument("--version", required=True); b.add_argument("--notes", default=""); b.set_defaults(f=cmd_build)
s = sub.add_parser("sign"); s.add_argument("--key", required=True); s.set_defaults(f=cmd_sign)
v = sub.add_parser("verify"); v.add_argument("--pub", default=""); v.set_defaults(f=cmd_verify)
args = ap.parse_args()
args.f(args)
