"""
PHARMAKON // Portable Windows build in one step.

Builds Pharmakon.exe from the CURRENT source with PyInstaller, adds the portable launch
scripts, docs and the signed manifest, and zips the result. Everything comes from one
build, so the exe (which embeds the engine code) and the GUI files always match.

Usage (from the repository root, after committing):
    python tools/build_portable.py --version 3.2.0

Output: dist_<version>/PHARMAKON/  and  PHARMAKON_v<version>_Windows_Portable.zip
"""
import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTABLE = ROOT / "tools" / "portable"          # launch scripts for the built app (not the dev ones)
DOCS = ["AI_AUDIO_RESTORATION_WORKFLOW.md", "DEV_NOTE_MATH_AUDIT_FIXES.md", "PHARMAKON_3_ARCHITECTURAL_GUIDE.md",
        "README.md", "RELEASE_NOTES_3.2.0.md", "STEM_MASTERING_GUIDE.md"]


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    args = ap.parse_args()

    manifest = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))
    if manifest.get("version") != args.version:
        sys.exit(f"[ERROR] VERSION.json says {manifest.get('version')}, not {args.version}")
    if subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode != 0:
        sys.exit("[ERROR] Uncommitted changes: commit first so the build matches a commit.")

    dist = ROOT / f"dist_{args.version}"
    work = ROOT / f"build_{args.version}"
    for d in (dist, work):
        shutil.rmtree(d, ignore_errors=True)
    run([sys.executable, "-m", "PyInstaller", "Pharmakon.spec", "--noconfirm", "--clean",
         "--workpath", str(work), "--distpath", str(dist)])

    app = dist / "PHARMAKON"
    for f in sorted(PORTABLE.iterdir()):
        shutil.copy2(f, app / f.name)
    for f in ("Create_Desktop_Shortcut.bat", "install_wizard.ps1", "pharmakon_hd_256.ico",
              "VERSION.json", "VERSION.json.sig"):
        shutil.copy2(ROOT / f, app / f)
    (app / "docs").mkdir(exist_ok=True)
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split())
    for name in DOCS:
        src = ROOT / name if name in tracked else ROOT / "docs" / name
        if src.exists():
            shutil.copy2(src, app / "docs" / name)
        else:
            print(f"[WARN] doc not found: {name}")

    out = ROOT / f"PHARMAKON_v{args.version}_Windows_Portable.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(app.rglob("*")):
            if p.is_file():
                z.write(p, Path("PHARMAKON") / p.relative_to(app))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print(f"[DONE] {out.name}  ({out.stat().st_size / 1e6:.1f} MB) built from {commit}")


if __name__ == "__main__":
    main()
