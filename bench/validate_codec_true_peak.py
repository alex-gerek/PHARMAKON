"""True-peak growth through lossy codecs on PHARMAKON-limited masters.

Measurement bench only: ffmpeg is called as an external encoder/decoder to
simulate distribution, it is not part of the product.

For every track: take 60 s around the loudest second, gain it to a target
integrated loudness (-14 and -8 LUFS), limit it with PHARMAKON's 4X true-peak
limiter at -0.3 / -1.0 / -2.0 dBTP, write 24-bit WAV, encode and decode with
MP3 320/128, AAC 256, Vorbis 160 and Opus 128, then measure the decoded true
peak (4X, 50 ms edges excluded) and the decoded sample peak.

Usage:
    python -m bench.validate_codec_true_peak track1.wav track2.wav ... [--out FILE]
Requires ffmpeg with libmp3lame, libvorbis and libopus on PATH.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import remaster_engine as R  # noqa: E402

CODECS = {
    "mp3_320": (["-c:a", "libmp3lame", "-b:a", "320k"], "mp3"),
    "mp3_128": (["-c:a", "libmp3lame", "-b:a", "128k"], "mp3"),
    "aac_256": (["-c:a", "aac", "-b:a", "256k"], "m4a"),
    "vorbis_160": (["-c:a", "libvorbis", "-b:a", "160k"], "ogg"),
    "opus_128": (["-c:a", "libopus", "-b:a", "128k"], "opus"),
}
LOUDNESS_TARGETS = (-14.0, -8.0)
CEILINGS = (-0.3, -1.0, -2.0)


def true_peak_db(x, sr, k=4, edge_s=0.05):
    e = int(edge_s * sr) * k
    up = signal.resample_poly(x, k, 1, axis=0)[e:-e]
    return float(20 * np.log10(np.max(np.abs(up)) + 1e-12))


def sample_peak_db(x):
    return float(20 * np.log10(np.max(np.abs(x)) + 1e-12))


def ffmpeg(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args, check=True)


def run(paths, workdir):
    out = {"sources": [], "masters": []}
    for ti, path in enumerate(paths):
        x, sr = sf.read(path, dtype="float64", always_2d=True)
        x = x[:, :2]
        out["sources"].append({"track": ti, "sample_peak_db": sample_peak_db(x),
                               "true_peak_db": true_peak_db(x, sr),
                               "lufs": float(R.calc_integrated_lufs(x, sr))})
        rms = np.sqrt(np.convolve((x ** 2).mean(1), np.ones(sr) / sr, mode="same"))
        c = int(np.argmax(rms))
        a = max(0, min(len(x) - 60 * sr, c - 30 * sr))
        seg = x[a:a + 60 * sr]
        for target in LOUDNESS_TARGETS:
            g = 10 ** ((target - R.calc_integrated_lufs(seg, sr)) / 20)
            for ceiling in CEILINGS:
                m, _ = R.true_peak_limiter(seg * g, sr, target_ceiling_db=ceiling)
                src = os.path.join(workdir, "master.wav")
                sf.write(src, m.astype(np.float64), sr, subtype="PCM_24")
                m24, _ = sf.read(src, dtype="float64", always_2d=True)
                row = {"track": ti, "lufs_target": target, "ceiling_db": ceiling,
                       "lufs_master": float(R.calc_integrated_lufs(m24, sr)),
                       "master_true_peak_db": true_peak_db(m24, sr)}
                for name, (args, ext) in CODECS.items():
                    enc = os.path.join(workdir, "enc." + ext)
                    dec = os.path.join(workdir, "dec.wav")
                    ffmpeg(["-i", src] + args + [enc])
                    ffmpeg(["-i", enc, "-c:a", "pcm_f32le", dec])
                    d, dsr = sf.read(dec, dtype="float64", always_2d=True)
                    row[name + "_true_peak_db"] = true_peak_db(d, dsr)
                    row[name + "_sample_peak_db"] = sample_peak_db(d)
                out["masters"].append(row)
                print(json.dumps(row), flush=True)
    return out


def summarize(res):
    lines = []
    for target in LOUDNESS_TARGETS:
        for ceiling in CEILINGS:
            rows = [r for r in res["masters"] if r["lufs_target"] == target and r["ceiling_db"] == ceiling]
            limited = [r for r in rows if r["master_true_peak_db"] > ceiling - 0.1]
            lines.append(f"{target:+.0f} LUFS, ceiling {ceiling:+.1f} dBTP: {len(limited)}/{len(rows)} masters reach the ceiling")
            for name in CODECS:
                if not limited:
                    continue
                growth = [r[name + "_true_peak_db"] - r["master_true_peak_db"] for r in limited]
                over = sum(r[name + "_sample_peak_db"] > 0 for r in rows)
                lines.append(f"   {name:11s} growth median {np.median(growth):+.2f} max {max(growth):+.2f} dB | "
                             f"decoded samples above 0 dBFS on {over}/{len(rows)}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="+")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results", "codec_true_peak.json"))
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as wd:
        res = run(a.tracks, wd)
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
    print(summarize(res))
