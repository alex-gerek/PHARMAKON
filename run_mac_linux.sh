#!/usr/bin/env bash
# Studio Remaster - Lex Gerek DSP Audio Engine (Mac & Linux)

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "========================================================"
echo "        STUDIO REMASTER (DSP CLEANING & MASTERING)"
echo "   Audio De-Harshing, Mono Sub-Bass, Punch & 3D Width"
echo "========================================================"
echo ""

# Check python3
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3.9+ from python.org or via brew."
    exit 1
fi

# Auto-install dependencies if missing
python3 -c "import numpy, scipy, soundfile" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[SETUP] First run: Installing required DSP libraries (numpy, scipy, soundfile)..."
    python3 -m pip install -r "$DIR/requirements.txt"
    echo ""
fi

TARGET="$1"
if [ -z "$TARGET" ]; then
    read -p "Enter stems folder path: " TARGET
fi

if [ -z "$TARGET" ]; then
    echo "No folder provided. Exiting."
    exit 0
fi

python3 "$DIR/remaster_engine.py" "$TARGET"
