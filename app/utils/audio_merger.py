# app/utils/audio_merger.py

import os
import re
from pydub import AudioSegment
from app.config import settings


def merge_podcast_segments(
    segment_filenames: list,
    output_filename: str = "full_podcast.mp3",
    cleanup_segments: bool = False
) -> str:
    """
    Menggabungkan seluruh segmen audio menjadi 1 file MP3 utuh.

    CATATAN PERBAIKAN:
    Versi sebelumnya memakai FFmpeg `-f concat` (concat demuxer) sebagai
    metode utama. Concat demuxer TIDAK mendekode lalu menggabungkan audio --
    dia cuma menyambung paket-paket mentah dari tiap file MP3 secara
    berurutan, baru di-encode ulang sekali di akhir. Ini menghasilkan
    klik/glitch/suara patah tepat di titik sambungan kalau file sumbernya
    pakai bitrate variabel (VBR) -- yang memang lazim untuk output TTS
    seperti ElevenLabs -- karena batas antar-frame audio tidak selalu
    sejajar persis di titik sambungan.

    Solusi: decode PENUH tiap segmen ke PCM lewat pydub, gabungkan di level
    PCM (bukan bitstream MP3 mentah), baru encode ulang sekali di akhir.
    Ini menghilangkan masalah penyambungan bitstream sepenuhnya.

    Sekaligus memakai field `pause_duration` asli per segmen (dari
    script_agent.py) untuk jeda antar dialog, bukan jeda seragam 300ms,
    supaya ritme bicara terasa lebih natural.
    """
    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    TARGET_SAMPLE_RATE = 44100
    TARGET_CHANNELS = 2
    DEFAULT_GAP_MS = 350
    MIN_GAP_MS = 150
    MAX_GAP_MS = 1200

    def extract_segment_number(item):
        str_item = str(item)
        match = re.search(r'segment_(\d+)', str_item)
        return int(match.group(1)) if match else 9999

    sorted_segments = sorted(segment_filenames, key=extract_segment_number)

    # ============================================================
    # KUMPULKAN FILE SEGMEN YANG VALID (+ pause_duration masing-masing)
    # ============================================================
    valid_segments = []  # list of (file_path, pause_duration_seconds)

    for item in sorted_segments:
        if isinstance(item, dict):
            raw_path = item.get("file_path") or item.get("filename") or item.get("path") or ""
            pause_duration = item.get("pause_duration", 0.3)
        else:
            raw_path = str(item)
            pause_duration = 0.3

        base_name = os.path.basename(str(raw_path).strip())
        if not base_name or base_name == "output_audio":
            continue

        file_path = os.path.join(output_dir, base_name)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            valid_segments.append((file_path, pause_duration))
            print(f"[MERGER] ✅ Found: {base_name}")
        else:
            print(f"[MERGER] ⚠️ Missing: {file_path}")

    if len(valid_segments) == 0:
        print("[MERGER] ❌ No valid segments found!")
        return ""

    # ============================================================
    # DECODE + CONCAT PENUH LEWAT PYDUB
    # ============================================================
    try:
        combined = AudioSegment.empty()

        for file_path, pause_duration in valid_segments:
            try:
                audio = AudioSegment.from_file(file_path, format="mp3")
                audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
                audio = audio.set_channels(TARGET_CHANNELS)
                combined += audio

                gap_ms = int((pause_duration or 0.3) * 1000)
                gap_ms = max(MIN_GAP_MS, min(gap_ms, MAX_GAP_MS))
                combined += AudioSegment.silent(duration=gap_ms, frame_rate=TARGET_SAMPLE_RATE)

                print(f"[MERGER] ✅ Added: {os.path.basename(file_path)} (gap {gap_ms}ms)")
            except Exception as e:
                print(f"[MERGER] ❌ Failed to decode: {os.path.basename(file_path)} - {e}")

        if len(combined) > 500:
            combined.export(output_path, format="mp3", bitrate="192k")
            print(f"[MERGER] ✅ Merge success (pydub decode+concat, no bitstream splice glitch): {output_path}")

            if cleanup_segments:
                for file_path, _ in valid_segments:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

            return output_filename
        else:
            print("[MERGER] ❌ Merge failed - combined audio too short (kemungkinan semua segmen gagal didekode)")
            return ""

    except Exception as e:
        print(f"[MERGER] ❌ pydub merge error: {e}")
        return ""