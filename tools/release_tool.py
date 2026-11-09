"""
PHARMAKON 3.1 // Release & Manifest Signing Tool
Implements Ed25519 asymmetric cryptography and SHA-256 manifest generation/verification.
Author: PHARMAKON Security Team
"""

import os
import sys
import json
import base64
import hashlib
import argparse
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def canonical_json_bytes(obj: dict) -> bytes:
    """Returns deterministic, canonical UTF-8 JSON bytes for cryptographic signing."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')

def hash_file_sha256(path: str) -> str:
    """Calculates hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def cmd_keygen(args):
    """Generates an Ed25519 keypair, saving private key outside repository."""
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pem_bytes = priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(out_path, 'wb') as f:
        f.write(pem_bytes)
        
    pub_bytes = priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_bytes).decode('ascii')
    
    print("=======================================================")
    print("  PHARMAKON Ed25519 Keypair Generated Successfully")
    print("=======================================================")
    print(f"Private Key saved to: {out_path}")
    print(f"Public Key (Base64):  {pub_b64}")
    print("\nCopy this Public Key to auto_updater.py (UPDATE_PUBLIC_KEY_B64).")
    print("KEEP YOUR PRIVATE KEY SAFE AND OFFLINE. DO NOT COMMIT TO GIT!")
    print("=======================================================")
    return pub_b64

def cmd_sign(args):
    """Generates a signed VERSION.json manifest from release files."""
    priv_path = Path(args.key).resolve()
    if not priv_path.exists():
        print(f"[ERROR] Private key not found at {priv_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(priv_path, 'rb') as f:
        priv_key = serialization.load_pem_private_key(f.read(), password=None)
        
    files_dict = {}
    for fpath in args.files:
        p = Path(fpath)
        if p.exists() and p.is_file():
            # Use relative name or basename
            rel_name = p.name
            files_dict[rel_name] = hash_file_sha256(str(p))
            
    manifest = {
        "version": args.version,
        "release_tag": f"v{args.version}",
        "notes": args.notes or f"PHARMAKON v{args.version} Release",
        "files": files_dict
    }
    
    canon_bytes = canonical_json_bytes(manifest)
    signature = priv_key.sign(canon_bytes)
    sig_b64 = base64.b64encode(signature).decode('ascii')
    
    # Write manifest and signature
    manifest_out = Path(args.manifest_out).resolve()
    with open(manifest_out, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        
    sig_out = Path(f"{manifest_out}.sig")
    with open(sig_out, 'w', encoding='utf-8') as f:
        f.write(sig_b64)
        
    print(f"[SUCCESS] Signed manifest created: {manifest_out}")
    print(f"[SUCCESS] Signature written to:    {sig_out}")
    print(f"Signature (Base64): {sig_b64[:32]}...")

def cmd_verify(args):
    """Verifies manifest signature and optionally checks files on disk."""
    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"[ERROR] Manifest file not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
        
    sig_path = Path(args.sig).resolve() if args.sig else Path(f"{manifest_path}.sig")
    if not sig_path.exists():
        print(f"[ERROR] Signature file not found: {sig_path}", file=sys.stderr)
        sys.exit(1)
        
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    with open(sig_path, 'r', encoding='utf-8') as f:
        sig_b64 = f.read().strip()
        
    sig_bytes = base64.b64decode(sig_b64)
    pub_bytes = base64.b64decode(args.pubkey.strip())
    pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
    
    canon_bytes = canonical_json_bytes(manifest)
    try:
        pub_key.verify(sig_bytes, canon_bytes)
        print("[VERIFIED] Ed25519 signature is VALID!")
    except Exception as e:
        print(f"[FAILED] Signature verification failed: {e}", file=sys.stderr)
        sys.exit(2)
        
    # Check file hashes if files directory specified
    if args.check_files_dir:
        base_dir = Path(args.check_files_dir).resolve()
        for fname, expected_hash in manifest.get("files", {}).items():
            f_on_disk = base_dir / fname
            if not f_on_disk.exists():
                print(f"[WARN] File missing on disk: {fname}")
                continue
            actual_hash = hash_file_sha256(str(f_on_disk))
            if actual_hash != expected_hash:
                print(f"[MISMATCH] Hash mismatch for {fname}: expected {expected_hash}, got {actual_hash}", file=sys.stderr)
                sys.exit(3)
            else:
                print(f"[OK] {fname}: SHA-256 matches")
                
    print("[SUCCESS] All manifest verifications passed.")

def main():
    parser = argparse.ArgumentParser(description="PHARMAKON Ed25519 Release Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # keygen
    p_kg = subparsers.add_parser("keygen", help="Generate Ed25519 keypair")
    p_kg.add_argument("--out", required=True, help="Path to save private key (PEM)")
    
    # sign
    p_sn = subparsers.add_parser("sign", help="Sign release manifest")
    p_sn.add_argument("--version", required=True, help="Release version (e.g. 3.1.0)")
    p_sn.add_argument("--key", required=True, help="Path to Ed25519 private key PEM")
    p_sn.add_argument("--files", nargs="+", required=True, help="Files to include in manifest")
    p_sn.add_argument("--manifest-out", default="VERSION.json", help="Output manifest path")
    p_sn.add_argument("--notes", default="", help="Release notes")
    
    # verify
    p_vf = subparsers.add_parser("verify", help="Verify release manifest signature")
    p_vf.add_argument("--manifest", default="VERSION.json", help="Path to manifest JSON")
    p_vf.add_argument("--sig", default="", help="Path to signature file (defaults to <manifest>.sig)")
    p_vf.add_argument("--pubkey", required=True, help="Base64 encoded public key")
    p_vf.add_argument("--check-files-dir", default="", help="Directory to verify file SHA-256 hashes")
    
    args = parser.parse_args()
    if args.command == "keygen":
        cmd_keygen(args)
    elif args.command == "sign":
        cmd_sign(args)
    elif args.command == "verify":
        cmd_verify(args)

if __name__ == "__main__":
    main()
