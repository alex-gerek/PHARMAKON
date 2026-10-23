import sys
import os
import glob
import numpy as np
import soundfile as sf
import scipy.signal as signal

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

def find_stem(files, keyword):
    for f in files:
        base = os.path.basename(f).lower()
        if keyword in base and base.endswith('.wav'):
            return f
    return None

def process_folder(target_folder):
    target_folder = target_folder.strip().strip('"').strip("'")
    if not os.path.isdir(target_folder):
        # Maybe user dropped a file inside the folder
        if os.path.isfile(target_folder):
            target_folder = os.path.dirname(target_folder)
        else:
            print(f"[ERROR] Folder not found: {target_folder}")
            return False

    wav_files = glob.glob(os.path.join(target_folder, "*.wav"))
    if not wav_files:
        print(f"[ERROR] No .wav stem files found in: {target_folder}")
        return False

    v_path = find_stem(wav_files, "vocal")
    d_path = find_stem(wav_files, "drum")
    b_path = find_stem(wav_files, "bass")
    o_path = find_stem(wav_files, "other")

    if not all([v_path, d_path, b_path, o_path]):
        print("[ERROR] Could not find all 4 stems (vocals, drums, bass, other) in folder.")
        print(f"Found: vocals={bool(v_path)}, drums={bool(d_path)}, bass={bool(b_path)}, other={bool(o_path)}")
        return False

    track_name = os.path.basename(target_folder)
    print(f"\n=======================================================")
    print(f"    STUDIO REMASTER DSP ENGINE: {track_name}")
    print(f"=======================================================\n")

    print("[1/5] Loading lossless stems...")
    vocals, sr = sf.read(v_path, dtype='float32')
    drums, _ = sf.read(d_path, dtype='float32')
    bass, _ = sf.read(b_path, dtype='float32')
    other, _ = sf.read(o_path, dtype='float32')

    # Ensure 2 channels
    def ensure_stereo(arr):
        if arr.ndim == 1:
            return np.column_stack([arr, arr])
        return arr

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

    # Save
    sf.write(os.path.join(remaster_dir, f"{track_name} - vocals_cleaned.wav"), vocals_proc, sr)
    sf.write(os.path.join(remaster_dir, f"{track_name} - drums_punched.wav"), drums_proc, sr)
    sf.write(os.path.join(remaster_dir, f"{track_name} - bass_monofied.wav"), bass_proc, sr)
    sf.write(os.path.join(remaster_dir, f"{track_name} - other_widened.wav"), other_proc, sr)

    master_path = os.path.join(remaster_dir, f"{track_name} - STUDIO_REMASTER.wav")
    sf.write(master_path, master_mix, sr)

    print(f"\n=======================================================")
    print(f"  SUCCESS! Remaster completed!")
    print(f"  Master file: {os.path.basename(master_path)}")
    print(f"=======================================================\n")
    
    # Open folder in Explorer
    os.system(f'explorer "{remaster_dir}"')
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = input("Enter or drag Stems folder here: ")
    process_folder(folder)
