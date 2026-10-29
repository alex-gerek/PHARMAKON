import sys
import os
import io
import glob
import numpy as np
import soundfile as sf
import scipy.signal as signal

# Force UTF-8 stdout and stderr on Windows to prevent UnicodeEncodeError in console
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

SUPPORTED_EXTS = ('.wav', '.mp3', '.flac', '.ogg', '.aiff', '.aif')

DEFAULT_PARAMS = {
    'sub_cutoff': 32.0,          # Sub infrasonic highpass cut (Hz)
    'mono_crossover': 120.0,     # Mono crossover frequency (Hz)
    'deharsh_freq': 5000.0,      # Anti-AI harshness notch frequency (Hz)
    'deharsh_q': 2.8,            # Notch Q factor
    'deharsh_depth': 1.0,        # 1.0 = full notch, 0.5 = blend
    'tape_drive': 1.04,          # Analog tape saturation drive
    'tape_ceiling': 0.98,        # Saturation ceiling
    'side_stereo_boost': 1.20,   # Highs Mid-Side side gain (+20%)
    'target_ceiling_db': -0.3,   # True-Peak ceiling (dBFS)
    'drum_punch': 1.0,           # Transient attack punch multiplier (for stems)
    'mode': 'pharmakon1'         # 'pharmakon1' (Auto) or 'pharmakon2' (Pro)
}

def butter_highpass(data, cutoff, fs, order=4):
    nyq = 0.5 * fs
    normal_cutoff = max(10.0, min(cutoff, nyq - 50.0)) / nyq
    b, a = signal.butter(order, normal_cutoff, btype='high', analog=False)
    return signal.filtfilt(b, a, data, axis=0)

def butter_lowpass(data, cutoff, fs, order=4):
    nyq = 0.5 * fs
    normal_cutoff = max(20.0, min(cutoff, nyq - 50.0)) / nyq
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    return signal.filtfilt(b, a, data, axis=0)

def soft_clip(x, threshold=0.95):
    return np.tanh(x / threshold) * threshold

def ensure_stereo(arr):
    if arr.ndim == 1:
        return np.column_stack([arr, arr])
    elif arr.shape[1] > 2:
        return arr[:, :2]
    return arr

def find_stem(files, keyword):
    for f in files:
        base = os.path.basename(f).lower()
        if keyword in base and base.endswith(SUPPORTED_EXTS):
            return f
    return None

def calc_audio_metrics(orig, proc, sr, params=None):
    """Calculates detailed comparative metrics and FFT curves for visualization."""
    if params is None:
        params = DEFAULT_PARAMS

    p_orig = float(np.max(np.abs(orig)))
    p_proc = float(np.max(np.abs(proc)))
    rms_orig = float(np.sqrt(np.mean(orig**2)))
    rms_proc = float(np.sqrt(np.mean(proc**2)))

    # Infrasonic reduction (< 32Hz)
    sub_cut = float(params.get('sub_cutoff', 32.0))
    b_sub, a_sub = signal.butter(4, min(sub_cut, sr*0.45) / (sr * 0.5), btype='low')
    sub_orig = signal.filtfilt(b_sub, a_sub, orig, axis=0)
    sub_proc = signal.filtfilt(b_sub, a_sub, proc, axis=0)
    sub_orig_rms = float(np.sqrt(np.mean(sub_orig**2)))
    sub_proc_rms = float(np.sqrt(np.mean(sub_proc**2)))
    sub_reduction = float(20 * np.log10(max(1e-9, sub_orig_rms) / max(1e-9, sub_proc_rms)))

    # Low-end side reduction (mono solidification < 120Hz)
    mono_cross = float(params.get('mono_crossover', 120.0))
    b_low, a_low = signal.butter(4, min(mono_cross, sr*0.45) / (sr * 0.5), btype='low')
    low_orig = signal.filtfilt(b_low, a_low, orig, axis=0)
    low_proc = signal.filtfilt(b_low, a_low, proc, axis=0)
    low_side_orig = (low_orig[:, 0] - low_orig[:, 1]) * 0.5
    low_side_proc = (low_proc[:, 0] - low_proc[:, 1]) * 0.5
    low_side_orig_rms = float(np.sqrt(np.mean(low_side_orig**2)))
    low_side_proc_rms = float(np.sqrt(np.mean(low_side_proc**2)))
    mono_side_reduction = float(20 * np.log10(max(1e-9, low_side_orig_rms) / max(1e-9, low_side_proc_rms)))

    # Highs stereo expansion
    b_high, a_high = signal.butter(4, min(mono_cross * 2.0, sr*0.45) / (sr * 0.5), btype='high')
    high_orig = signal.filtfilt(b_high, a_high, orig, axis=0)
    high_proc = signal.filtfilt(b_high, a_high, proc, axis=0)
    high_side_orig = (high_orig[:, 0] - high_orig[:, 1]) * 0.5
    high_side_proc = (high_proc[:, 0] - high_proc[:, 1]) * 0.5
    high_side_orig_rms = float(np.sqrt(np.mean(high_side_orig**2)))
    high_side_proc_rms = float(np.sqrt(np.mean(high_side_proc**2)))
    stereo_expansion = float(20 * np.log10(max(1e-9, high_side_proc_rms) / max(1e-9, high_side_orig_rms)))

    # 5kHz harsh notch reduction
    deharsh_f = float(params.get('deharsh_freq', 5000.0))
    f_low = max(500.0, deharsh_f * 0.95) / (sr * 0.5)
    f_high = min(sr * 0.49, deharsh_f * 1.05) / (sr * 0.5)
    b_harsh, a_harsh = signal.butter(2, [f_low, f_high], btype='band')
    harsh_orig = signal.filtfilt(b_harsh, a_harsh, orig, axis=0)
    harsh_proc = signal.filtfilt(b_harsh, a_harsh, proc, axis=0)
    harsh_orig_rms = float(np.sqrt(np.mean(harsh_orig**2)))
    harsh_proc_rms = float(np.sqrt(np.mean(harsh_proc**2)))
    harsh_reduction = float(20 * np.log10(max(1e-9, harsh_orig_rms) / max(1e-9, harsh_proc_rms)))

    # Compute Welch spectral curves (approx 100 log points 20Hz - 20kHz)
    analysis_len = min(len(orig), sr * 15)  # analyze up to 15s around loudest part
    mid_start = max(0, len(orig) // 2 - analysis_len // 2)
    sample_o = np.mean(orig[mid_start:mid_start + analysis_len], axis=1)
    sample_p = np.mean(proc[mid_start:mid_start + analysis_len], axis=1)

    f, pxx_o = signal.welch(sample_o, fs=sr, nperseg=min(4096, len(sample_o)))
    _, pxx_p = signal.welch(sample_p, fs=sr, nperseg=min(4096, len(sample_p)))

    freq_pts = np.geomspace(20.0, min(20000.0, sr * 0.49), 120)
    curve_o = np.interp(freq_pts, f, 10.0 * np.log10(np.maximum(pxx_o, 1e-12)))
    curve_p = np.interp(freq_pts, f, 10.0 * np.log10(np.maximum(pxx_p, 1e-12)))

    # Compute mini-waveform envelope for UI display (300 points)
    n_points = 300
    chunk = len(orig) // n_points
    if chunk > 0:
        wave_o = np.max(np.abs(orig[:chunk * n_points].reshape(n_points, chunk, -1)), axis=(1, 2))
        wave_p = np.max(np.abs(proc[:chunk * n_points].reshape(n_points, chunk, -1)), axis=(1, 2))
    else:
        wave_o = np.max(np.abs(orig), axis=1)
        wave_p = np.max(np.abs(proc), axis=1)

    # 2048-point oscilloscope snapshot from the loudest peak section for instant CRT display
    scope_len = 2048
    if len(orig) >= scope_len:
        loudest_idx = int(np.argmax(np.abs(sample_o)))
        start_idx = max(0, min(len(orig) - scope_len, mid_start + loudest_idx - scope_len // 2))
        s_o = orig[start_idx:start_idx + scope_len, 0] if orig.ndim > 1 else orig[start_idx:start_idx + scope_len]
        s_p = proc[start_idx:start_idx + scope_len, 0] if proc.ndim > 1 else proc[start_idx:start_idx + scope_len]
        byte_o = [int(np.clip(round(128.0 + float(x) * 127.0), 0, 255)) for x in s_o]
        byte_p = [int(np.clip(round(128.0 + float(x) * 127.0), 0, 255)) for x in s_p]
    else:
        byte_o = [128] * scope_len
        byte_p = [128] * scope_len

    return {
        'peak_orig_db': round(float(20 * np.log10(max(1e-9, p_orig))), 2),
        'peak_proc_db': round(float(20 * np.log10(max(1e-9, p_proc))), 2),
        'rms_orig_db': round(float(20 * np.log10(max(1e-9, rms_orig))), 2),
        'rms_proc_db': round(float(20 * np.log10(max(1e-9, rms_proc))), 2),
        'sub_reduction_db': round(max(0.0, sub_reduction), 2),
        'mono_side_reduction_db': round(max(0.0, mono_side_reduction), 2),
        'stereo_expansion_db': round(max(0.0, stereo_expansion), 2),
        'harsh_reduction_db': round(max(0.0, harsh_reduction), 2),
        'duration_sec': round(len(orig) / float(sr), 2),
        'sample_rate': int(sr),
        'fft_freqs': [round(float(x), 1) for x in freq_pts],
        'fft_orig_db': [round(float(x), 1) for x in curve_o],
        'fft_proc_db': [round(float(x), 1) for x in curve_p],
        'waveform_orig': [round(float(x), 3) for x in wave_o],
        'waveform_proc': [round(float(x), 3) for x in wave_p],
        'scope_sample_orig': byte_o,
        'scope_sample_proc': byte_p
    }

def process_audio_array(audio, sr, params=None):
    """Processes stereo audio in-memory with given parameters and returns (processed_audio, metrics)."""
    if params is None:
        params = DEFAULT_PARAMS

    audio = ensure_stereo(audio)
    nyq = 0.5 * sr

    sub_cutoff = float(params.get('sub_cutoff', 32.0))
    mono_crossover = float(params.get('mono_crossover', 120.0))
    deharsh_freq = float(params.get('deharsh_freq', 5000.0))
    deharsh_q = float(params.get('deharsh_q', 2.8))
    deharsh_depth = float(params.get('deharsh_depth', 1.0))
    tape_drive = float(params.get('tape_drive', 1.04))
    tape_ceiling = float(params.get('tape_ceiling', 0.98))
    side_stereo_boost = float(params.get('side_stereo_boost', 1.20))
    target_ceiling_db = float(params.get('target_ceiling_db', -0.3))

    # 1. Infrasonic highpass cut
    audio_sub = butter_highpass(audio, sub_cutoff, sr, order=4)

    # 2. Crossover at mono_crossover
    low_band = butter_lowpass(audio_sub, mono_crossover, sr, order=4)
    high_band = butter_highpass(audio_sub, mono_crossover, sr, order=4)

    # 3. Lows to 100% True Mono
    mono_low = np.mean(low_band, axis=1, keepdims=True)
    mono_low_stereo = np.repeat(mono_low, 2, axis=1)

    # 4. Anti-AI De-Harshing Notch Filter
    f_harsh = min(deharsh_freq, nyq - 50.0) / nyq
    b_notch, a_notch = signal.iirnotch(f_harsh, deharsh_q)
    high_notched = signal.filtfilt(b_notch, a_notch, high_band, axis=0)

    if deharsh_depth < 0.99:
        # Blend notch with original highs if depth < 1.0
        high_deharsh = high_notched * deharsh_depth + high_band * (1.0 - deharsh_depth)
    else:
        high_deharsh = high_notched

    # 5. Mid-Side stereo widening on highs only
    mid = 0.5 * (high_deharsh[:, 0] + high_deharsh[:, 1])
    side = 0.5 * (high_deharsh[:, 0] - high_deharsh[:, 1])
    side_widened = side * side_stereo_boost
    high_proc = np.column_stack([mid + side_widened, mid - side_widened])

    # 6. Summing
    full_mix = mono_low_stereo + high_proc

    # 7. Analog tape saturation warmth
    full_mix = np.tanh(full_mix * tape_drive) * tape_ceiling

    # 8. True-Peak Limiter
    peak = np.max(np.abs(full_mix))
    target_ceiling = 10.0 ** (target_ceiling_db / 20.0)
    if peak > 0:
        full_mix = (full_mix / peak) * target_ceiling

    # 9. SURGICAL TIME-RANGE / REGION PUNCH-IN BLENDING
    region_mode = params.get('region_mode', 'full')
    range_start = float(params.get('range_start', 0.0))
    range_end = float(params.get('range_end', 0.0))

    if region_mode == 'region' and range_end > range_start:
        total_len = len(audio)
        start_samp = int(np.clip(range_start * sr, 0, total_len))
        end_samp = int(np.clip(range_end * sr, start_samp, total_len))

        # 35ms equal-power cosine crossfade to prevent any click/transient at splice boundary
        fade_len = int(min(sr * 0.035, (end_samp - start_samp) // 4))

        final_out = np.copy(audio)

        if fade_len > 0:
            fade_in = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_len)))[:, np.newaxis]
            fade_out = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_len)))[:, np.newaxis]

            # Crossfade-in into processed
            final_out[start_samp:start_samp + fade_len] = (
                audio[start_samp:start_samp + fade_len] * (1.0 - fade_in) +
                full_mix[start_samp:start_samp + fade_len] * fade_in
            )
            # Fully processed region
            final_out[start_samp + fade_len:end_samp - fade_len] = full_mix[start_samp + fade_len:end_samp - fade_len]

            # Crossfade-out back to original
            final_out[end_samp - fade_len:end_samp] = (
                full_mix[end_samp - fade_len:end_samp] * fade_out +
                audio[end_samp - fade_len:end_samp] * (1.0 - fade_out)
            )
        else:
            final_out[start_samp:end_samp] = full_mix[start_samp:end_samp]

        full_mix = final_out

    metrics = calc_audio_metrics(audio, full_mix, sr, params)
    return full_mix, metrics

def process_single_file(file_path, params=None, open_folder=True):
    file_path = file_path.strip().strip('"').strip("'")
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return None, None

    if params is None:
        params = DEFAULT_PARAMS

    base_dir = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    track_title, ext = os.path.splitext(filename)

    mode_label = "PHARMAKON 2 (PRO RACK)" if params.get('mode') == 'pharmakon2' else "PHARMAKON 1 (AUTO ANTIDOTE)"
    print(f"\n=======================================================")
    print(f"    PHARMAKON // {mode_label}")
    print(f"    Track: {track_title}")
    print(f"=======================================================\n")

    print(f"[1/4] Loading audio: {filename}...")
    try:
        audio, sr = sf.read(file_path, dtype='float32')
    except Exception as e:
        print(f"[ERROR] Could not read audio file: {e}")
        return None, None

    print(f"[2/4] DSP Processing: Infrasonic Cut (<{params.get('sub_cutoff', 32)}Hz) & Mono Crossover (<{params.get('mono_crossover', 120)}Hz)...")
    print(f"[3/4] Highs: Anti-AI De-Harshing ({params.get('deharsh_freq', 5000)}Hz Notch) & 3D Mid-Side (+{round((params.get('side_stereo_boost', 1.2)-1)*100)}% width)...")
    print(f"[4/4] Summing, Analog Tape Warmth & True-Peak Limiter ({params.get('target_ceiling_db', -0.3)} dBFS)...")

    full_mix, metrics = process_audio_array(audio, sr, params)

    out_dir = os.path.join(base_dir, "Remaster")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{track_title} - STUDIO_REMASTER.wav")

    sf.write(out_file, full_mix, sr)

    print(f"\n=======================================================")
    print(f"  SUCCESS! Remaster completed!")
    print(f"  Master file: {os.path.basename(out_file)}")
    print(f"  Location:    {out_dir}")
    print(f"  Peak In/Out: {metrics['peak_orig_db']} dBFS -> {metrics['peak_proc_db']} dBFS")
    print(f"  Analog Warmth: {metrics['rms_orig_db']} dBFS -> {metrics['rms_proc_db']} dBFS")
    print(f"=======================================================\n")

    if open_folder and sys.platform == 'win32':
        os.system(f'explorer "{out_dir}"')

    return out_file, metrics

def process_stems_folder(target_folder, params=None, open_folder=True):
    target_folder = target_folder.strip().strip('"').strip("'")
    if not os.path.isdir(target_folder):
        print(f"[ERROR] Folder not found: {target_folder}")
        return None, None

    if params is None:
        params = DEFAULT_PARAMS

    audio_files = []
    for ext in SUPPORTED_EXTS:
        audio_files.extend(glob.glob(os.path.join(target_folder, f"*{ext}")))

    if not audio_files:
        print(f"[ERROR] No audio files found in: {target_folder}")
        return None, None

    v_path = find_stem(audio_files, "vocal")
    d_path = find_stem(audio_files, "drum")
    b_path = find_stem(audio_files, "bass")
    o_path = find_stem(audio_files, "other")

    if not all([v_path, d_path, b_path, o_path]):
        if len(audio_files) == 1:
            print(f"[INFO] Folder contains a single track. Running Full Track Mastering...")
            return process_single_file(audio_files[0], params=params, open_folder=open_folder)
        else:
            print("[INFO] Could not find all 4 stems (vocals, drums, bass, other).")
            print(f"Found {len(audio_files)} files. Running Full Track Mastering on: {os.path.basename(audio_files[0])}")
            return process_single_file(audio_files[0], params=params, open_folder=open_folder)

    track_name = os.path.basename(target_folder)
    mode_label = "PHARMAKON 2 (PRO STEM RACK)" if params.get('mode') == 'pharmakon2' else "PHARMAKON 1 (AUTO STEM ANTIDOTE)"
    print(f"\n=======================================================")
    print(f"    PHARMAKON // {mode_label}")
    print(f"    Track: {track_name}")
    print(f"=======================================================\n")

    vocals, sr = sf.read(v_path, dtype='float32')
    drums, _ = sf.read(d_path, dtype='float32')
    bass, _ = sf.read(b_path, dtype='float32')
    other, _ = sf.read(o_path, dtype='float32')

    vocals = ensure_stereo(vocals)
    drums = ensure_stereo(drums)
    bass = ensure_stereo(bass)
    other = ensure_stereo(other)

    min_len = min(len(vocals), len(drums), len(bass), len(other))
    vocals = vocals[:min_len]
    drums = drums[:min_len]
    bass = bass[:min_len]
    other = other[:min_len]

    raw_sum = vocals + drums + bass + other

    # Sub & Mono params
    sub_cut = float(params.get('sub_cutoff', 32.0))
    mono_cross = float(params.get('mono_crossover', 120.0))
    deharsh_f = float(params.get('deharsh_freq', 5000.0))
    deharsh_q = float(params.get('deharsh_q', 2.5))
    deharsh_depth = float(params.get('deharsh_depth', 1.0))
    side_boost = float(params.get('side_stereo_boost', 1.25))
    punch_factor = float(params.get('drum_punch', 1.0))
    target_ceiling_db = float(params.get('target_ceiling_db', -0.3))

    # --- BASS ---
    print(f"[1/4] BASS: Sub-cut {sub_cut}Hz, Mono below {mono_cross}Hz, Warmth saturation...")
    bass_clean = butter_highpass(bass, sub_cut, sr, order=4)
    bass_low = butter_lowpass(bass_clean, mono_cross, sr, order=4)
    bass_high = butter_highpass(bass_clean, mono_cross, sr, order=4)
    mono_low = np.mean(bass_low, axis=1, keepdims=True)
    mono_low_stereo = np.repeat(mono_low, 2, axis=1)
    bass_proc = mono_low_stereo + bass_high
    bass_proc = soft_clip(bass_proc * 1.05, 0.98)

    # --- DRUMS ---
    print(f"[2/4] DRUMS: Sub-cut 28Hz, Transient kick punch enhancement (x{punch_factor})...")
    drums_clean = butter_highpass(drums, 28, sr, order=4)
    diff = np.diff(np.abs(drums_clean), axis=0, prepend=0)
    attack_mask = np.clip(diff * (4.0 * punch_factor), 0.0, 0.35)
    drums_proc = drums_clean * (1.0 + attack_mask)
    drums_proc = soft_clip(drums_proc, 0.98)

    # --- VOCALS ---
    print(f"[3/4] VOCALS: De-essing AI harshness ({deharsh_f}Hz notch), Tape warmth...")
    vocals_clean = butter_highpass(vocals, 85, sr, order=3)
    nyq = 0.5 * sr
    f_harsh = min(deharsh_f, nyq - 50.0) / nyq
    b_notch, a_notch = signal.iirnotch(f_harsh, deharsh_q)
    vocals_notched = signal.filtfilt(b_notch, a_notch, vocals_clean, axis=0)
    if deharsh_depth < 0.99:
        vocals_deharsh = vocals_notched * deharsh_depth + vocals_clean * (1.0 - deharsh_depth)
    else:
        vocals_deharsh = vocals_notched
    vocals_proc = np.tanh(vocals_deharsh * 1.1) * 0.95

    # --- OTHER / SYNTHS ---
    print(f"[4/4] SYNTHS: Highpass 115Hz, 3D Mid-Side (+{round((side_boost-1)*100)}% stereo)...")
    other_clean = butter_highpass(other, 115, sr, order=3)
    mid = 0.5 * (other_clean[:, 0] + other_clean[:, 1])
    side = 0.5 * (other_clean[:, 0] - other_clean[:, 1])
    side_widened = side * side_boost
    other_proc = np.column_stack([mid + side_widened, mid - side_widened])

    # --- MASTER SUM & LIMITER ---
    print(f"\n>>> Summing to Master Mix and True-Peak Limiting ({target_ceiling_db} dBFS)...")
    master_mix = drums_proc + bass_proc * 0.98 + vocals_proc * 1.05 + other_proc * 0.92
    peak = np.max(np.abs(master_mix))
    target_ceiling = 10.0 ** (target_ceiling_db / 20.0)
    if peak > 0:
        master_mix = (master_mix / peak) * target_ceiling

    remaster_dir = os.path.join(target_folder, "Remaster")
    os.makedirs(remaster_dir, exist_ok=True)

    # Save cleaned stems
    v_out = os.path.join(remaster_dir, f"{track_name} - vocals_cleaned.wav")
    d_out = os.path.join(remaster_dir, f"{track_name} - drums_punched.wav")
    b_out = os.path.join(remaster_dir, f"{track_name} - bass_monofied.wav")
    o_out = os.path.join(remaster_dir, f"{track_name} - other_widened.wav")
    master_path = os.path.join(remaster_dir, f"{track_name} - STUDIO_REMASTER.wav")

    sf.write(v_out, vocals_proc, sr)
    sf.write(d_out, drums_proc, sr)
    sf.write(b_out, bass_proc, sr)
    sf.write(o_out, other_proc, sr)
    sf.write(master_path, master_mix, sr)

    metrics = calc_audio_metrics(raw_sum, master_mix, sr, params)

    print(f"\n=======================================================")
    print(f"  SUCCESS! Remaster completed!")
    print(f"  Master file: {os.path.basename(master_path)}")
    print(f"  Location:    {remaster_dir}")
    print(f"=======================================================\n")

    if open_folder and sys.platform == 'win32':
        os.system(f'explorer "{remaster_dir}"')

    return master_path, metrics

def main():
    if len(sys.argv) > 1:
        target = sys.argv[1].strip().strip('"').strip("'")
    else:
        target = input("Drag & drop audio file or stems folder here (or paste path): ").strip().strip('"').strip("'")

    if not target:
        print("[ERROR] No target path provided.")
        return

    if os.path.isfile(target):
        process_single_file(target)
    elif os.path.isdir(target):
        process_stems_folder(target)
    else:
        print(f"[ERROR] Target not found: {target}")

if __name__ == "__main__":
    main()
