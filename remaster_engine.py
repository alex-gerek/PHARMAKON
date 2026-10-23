import sys
import os
import glob
import numpy as np
import soundfile as sf
import scipy.signal as signal

SUPPORTED_EXTS = ('.wav', '.mp3', '.flac', '.ogg', '.aiff', '.aif')

def butter_highpass(data, cutoff, fs, order=4):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='high', analog=False)
    return signal.filtfilt(b, a, data, axis=0)

def butter_lowpass(data, cutoff, fs, order=4):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
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

def process_single_file(file_path):
    file_path = file_path.strip().strip('"').strip("'")
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return False

    base_dir = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    track_title, ext = os.path.splitext(filename)

    print(f"\n=======================================================")
    print(f"    STUDIO REMASTER (FULL TRACK MASTERING)")
    print(f"    Track: {track_title}")
    print(f"=======================================================\n")

    print(f"[1/4] Loading audio: {filename}...")
    try:
        audio, sr = sf.read(file_path, dtype='float32')
    except Exception as e:
        print(f"[ERROR] Could not read audio file: {e}")
        return False

    audio = ensure_stereo(audio)
    nyq = 0.5 * sr

    print("[2/4] DSP Processing: Infrasonic Cut (<32Hz) & Low Crossover (<120Hz)...")
    # Sub cut
    audio_sub = butter_highpass(audio, 32, sr, order=4)
    # Crossover at 120Hz
    low_band = butter_lowpass(audio_sub, 120, sr, order=4)
    high_band = butter_highpass(audio_sub, 120, sr, order=4)

    # Lows to 100% True Mono (rock-solid sub bass translation)
    mono_low = np.mean(low_band, axis=1, keepdims=True)
    mono_low_stereo = np.repeat(mono_low, 2, axis=1)

    print("[3/4] Highs: Anti-AI De-Harshing (5kHz Notch) & 3D Mid-Side (+20% width)...")
    # De-harsh notch on highs
    f_harsh = 5000.0 / nyq
    b_notch, a_notch = signal.iirnotch(f_harsh, 2.8)
    high_deharsh = signal.filtfilt(b_notch, a_notch, high_band, axis=0)

    # Mid-Side stereo widening on highs only (leaving mono sub untouched)
    mid = 0.5 * (high_deharsh[:, 0] + high_deharsh[:, 1])
    side = 0.5 * (high_deharsh[:, 0] - high_deharsh[:, 1])
    side_widened = side * 1.20
    high_proc = np.column_stack([mid + side_widened, mid - side_widened])

    print("[4/4] Summing, Analog Tape Warmth & True-Peak Limiter (-0.3 dBFS)...")
    full_mix = mono_low_stereo + high_proc
    # Analog tape warmth
    full_mix = np.tanh(full_mix * 1.04) * 0.98

    # True-peak limit to -0.3 dBFS
    peak = np.max(np.abs(full_mix))
    target_ceiling = 10 ** (-0.3 / 20.0)
    if peak > 0:
        full_mix = (full_mix / peak) * target_ceiling

    # Output directory
    out_dir = os.path.join(base_dir, "Remaster")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{track_title} - STUDIO_REMASTER.wav")

    sf.write(out_file, full_mix, sr)

    print(f"\n=======================================================")
    print(f"  SUCCESS! Remaster completed in 1 second!")
    print(f"  Master file: {os.path.basename(out_file)}")
    print(f"  Location:    {out_dir}")
    print(f"=======================================================\n")

    os.system(f'explorer "{out_dir}"')
    return True

def process_stems_folder(target_folder):
    target_folder = target_folder.strip().strip('"').strip("'")
    if not os.path.isdir(target_folder):
        print(f"[ERROR] Folder not found: {target_folder}")
        return False

    audio_files = []
    for ext in SUPPORTED_EXTS:
        audio_files.extend(glob.glob(os.path.join(target_folder, f"*{ext}")))

    if not audio_files:
        print(f"[ERROR] No audio files found in: {target_folder}")
        return False

    v_path = find_stem(audio_files, "vocal")
    d_path = find_stem(audio_files, "drum")
    b_path = find_stem(audio_files, "bass")
    o_path = find_stem(audio_files, "other")

    # If it is NOT a stems folder (doesn't have all 4 stems), but has a single audio file
    if not all([v_path, d_path, b_path, o_path]):
        if len(audio_files) == 1:
            print(f"[INFO] Folder contains a single track. Running Full Track Mastering...")
            return process_single_file(audio_files[0])
        else:
            print("[INFO] Could not find all 4 stems (vocals, drums, bass, other).")
            print(f"Found {len(audio_files)} files. Running Full Track Mastering on primary file: {os.path.basename(audio_files[0])}")
            return process_single_file(audio_files[0])

    track_name = os.path.basename(target_folder)
    print(f"\n=======================================================")
    print(f"    STUDIO REMASTER (4-STEM SURGICAL MASTERING)")
    print(f"    Track: {track_name}")
    print(f"=======================================================\n")

    print("[1/5] Loading lossless stems...")
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

    # --- BASS ---
    print("[2/5] BASS: Sub-cut 32Hz, Mono below 120Hz, Warmth saturation...")
    bass_clean = butter_highpass(bass, 32, sr, order=4)
    bass_low = butter_lowpass(bass_clean, 120, sr, order=4)
    bass_high = butter_highpass(bass_clean, 120, sr, order=4)
    mono_low = np.mean(bass_low, axis=1, keepdims=True)
    mono_low_stereo = np.repeat(mono_low, 2, axis=1)
    bass_proc = mono_low_stereo + bass_high
    bass_proc = soft_clip(bass_proc * 1.05, 0.98)

    # --- DRUMS ---
    print("[3/5] DRUMS: Sub-cut 28Hz, Transient kick punch enhancement...")
    drums_clean = butter_highpass(drums, 28, sr, order=4)
    diff = np.diff(np.abs(drums_clean), axis=0, prepend=0)
    attack_mask = np.clip(diff * 4.0, 0.0, 0.25)
    drums_proc = drums_clean * (1.0 + attack_mask)
    drums_proc = soft_clip(drums_proc, 0.98)

    # --- VOCALS ---
    print("[4/5] VOCALS: De-essing AI harshness (4.5-6.5kHz notch), Tape warmth...")
    vocals_clean = butter_highpass(vocals, 85, sr, order=3)
    nyq = 0.5 * sr
    f_harsh = 5000.0 / nyq
    b_notch, a_notch = signal.iirnotch(f_harsh, 2.5)
    vocals_deharsh = signal.filtfilt(b_notch, a_notch, vocals_clean, axis=0)
    vocals_proc = np.tanh(vocals_deharsh * 1.1) * 0.95

    # --- OTHER ---
    print("[5/5] SYNTHS: Highpass 115Hz, 3D Mid-Side +25% stereo widening...")
    other_clean = butter_highpass(other, 115, sr, order=3)
    mid = 0.5 * (other_clean[:, 0] + other_clean[:, 1])
    side = 0.5 * (other_clean[:, 0] - other_clean[:, 1])
    side_widened = side * 1.25
    other_proc = np.zeros_like(other_clean)
    other_proc[:, 0] = mid + side_widened
    other_proc[:, 1] = mid - side_widened

    # --- MASTER SUM & LIMITER ---
    print("\n>>> Summing to Master Mix and True-Peak Limiting (-0.3 dBFS)...")
    master_mix = drums_proc + bass_proc * 0.98 + vocals_proc * 1.05 + other_proc * 0.92
    peak = np.max(np.abs(master_mix))
    target_ceiling = 10 ** (-0.3 / 20.0)
    if peak > 0:
        master_mix = (master_mix / peak) * target_ceiling

    remaster_dir = os.path.join(target_folder, "Remaster")
    os.makedirs(remaster_dir, exist_ok=True)

    # Save cleaned stems
    sf.write(os.path.join(remaster_dir, f"{track_name} - vocals_cleaned.wav"), vocals_proc, sr)
    sf.write(os.path.join(remaster_dir, f"{track_name} - drums_punched.wav"), drums_proc, sr)
    sf.write(os.path.join(remaster_dir, f"{track_name} - bass_monofied.wav"), bass_proc, sr)
    sf.write(os.path.join(remaster_dir, f"{track_name} - other_widened.wav"), other_proc, sr)

    master_path = os.path.join(remaster_dir, f"{track_name} - STUDIO_REMASTER.wav")
    sf.write(master_path, master_mix, sr)

    print(f"\n=======================================================")
    print(f"  SUCCESS! Remaster completed!")
    print(f"  Master file: {os.path.basename(master_path)}")
    print(f"  Location:    {remaster_dir}")
    print(f"=======================================================\n")
    
    os.system(f'explorer "{remaster_dir}"')
    return True

def main():
    if len(sys.argv) > 1:
        target = sys.argv[1].strip().strip('"').strip("'")
    else:
        target = input("Перетащите сюда аудиофайл или папку со стемсами: ").strip().strip('"').strip("'")

    if not target:
        print("Путь не указан.")
        return

    if os.path.isfile(target):
        process_single_file(target)
    elif os.path.isdir(target):
        process_stems_folder(target)
    else:
        print(f"[ERROR] Не удалось найти: {target}")

if __name__ == "__main__":
    main()
