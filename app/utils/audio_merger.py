# app/utils/audio_merger.py

import os
import re
from pydub import AudioSegment
from pydub.effects import normalize
from app.config import settings

def merge_podcast_segments(
    segment_filenames: list,
    output_filename: str = "full_podcast.mp3",
    cleanup_segments: bool = False
) -> str:
    """
    Menggabungkan seluruh segmen audio menjadi 1 file MP3 utuh.
    DENGAN NORMALISASI VOLUME + SAMPLE RATE UNIFORM.
    """
    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    combined_audio = AudioSegment.empty()
    loaded_count = 0
    processed_files = []

    # ============================================================
    # TARGET: SAMPLE RATE UNIFORM (44100 Hz, Stereo)
    # ============================================================
    TARGET_SAMPLE_RATE = 44100
    TARGET_CHANNELS = 2  # Stereo

    def extract_segment_number(item):
        str_item = str(item)
        match = re.search(r'segment_(\d+)', str_item)
        return int(match.group(1)) if match else 9999

    sorted_segments = sorted(segment_filenames, key=extract_segment_number)
    print(f"\n[MERGER] Ditemukan {len(sorted_segments)} segmen. Memulai penggabungan...")

    for item in sorted_segments:
        if isinstance(item, dict):
            raw_path = item.get("file_path") or item.get("filename") or item.get("path") or ""
        else:
            raw_path = str(item)

        base_name = os.path.basename(str(raw_path).strip())

        if not base_name or base_name == "output_audio":
            continue

        file_path = os.path.join(output_dir, base_name)

        if os.path.exists(file_path):
            try:
                # ============================================================
                # 1. LOAD AUDIO DENGAN FORMAT YANG BENAR
                # ============================================================
                segment = AudioSegment.from_file(file_path, format="mp3")

                # ============================================================
                # 2. UNIFORM SAMPLE RATE & CHANNELS
                # ============================================================
                if segment.frame_rate != TARGET_SAMPLE_RATE:
                    segment = segment.set_frame_rate(TARGET_SAMPLE_RATE)
                    print(f"[MERGER] 🔄 Resample {base_name} → {TARGET_SAMPLE_RATE}Hz")

                if segment.channels != TARGET_CHANNELS:
                    segment = segment.set_channels(TARGET_CHANNELS)
                    print(f"[MERGER] 🔄 Convert {base_name} → Stereo")

                # ============================================================
                # 3. NORMALISASI VOLUME (SUPAYA TIDAK PECAH)
                # ============================================================
                # Normalisasi ke -3dB (agar tidak clipping)
                normalized_segment = normalize(segment, headroom=3.0)

                # ============================================================
                # 4. GABUNG DENGAN JEDA 0.3 DETIK
                # ============================================================
                combined_audio += normalized_segment
                combined_audio += AudioSegment.silent(duration=300, frame_rate=TARGET_SAMPLE_RATE)
                loaded_count += 1
                processed_files.append(file_path)
                print(f"[MERGER] ✅ {base_name} (volume normalized)")

            except Exception as e:
                print(f"[MERGER] ❌ Gagal membaca {base_name}: {e}")
        else:
            print(f"[MERGER] ⚠️ File tidak ditemukan: {file_path}")

    # ============================================================
    # 5. EKSPOR DENGAN BITRATE TINGGI
    # ============================================================
    if loaded_count > 0:
        try:
            # Normalisasi final (keseluruhan audio)
            final_audio = normalize(combined_audio, headroom=2.0)

            final_audio.export(
                output_path,
                format="mp3",
                bitrate="256k",  # <-- Bitrate tinggi untuk kualitas baik
                parameters=["-ac", "2", "-ar", "44100"]  # Stereo, 44.1kHz
            )
            print(f"\n[MERGER] ✅ {loaded_count} segmen digabung ke: {output_path}")
            print(f"[MERGER] 📊 Sample Rate: {TARGET_SAMPLE_RATE}Hz, Bitrate: 256kbps")

            if cleanup_segments:
                print("[MERGER] 🧹 Menghapus file segmen...")
                for temp_file in processed_files:
                    try:
                        if os.path.exists(temp_file) and temp_file != output_path:
                            os.remove(temp_file)
                    except Exception as e:
                        print(f"[MERGER] ⚠️ Gagal hapus {temp_file}: {e}")

        except Exception as e:
            print(f"\n[MERGER] ❌ Gagal ekspor MP3: {e}")
    else:
        print("\n[MERGER] ❌ Tidak ada segmen yang digabung!")

    return output_filename