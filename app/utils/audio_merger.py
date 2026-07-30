# app/utils/audio_merger.py

import os
import re
import subprocess
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
    """
    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    TARGET_SAMPLE_RATE = 44100
    TARGET_CHANNELS = 2

    def extract_segment_number(item):
        str_item = str(item)
        match = re.search(r'segment_(\d+)', str_item)
        return int(match.group(1)) if match else 9999

    # ============================================================
    # KUMPULKAN FILE SEGMEN YANG VALID
    # ============================================================
    valid_segments = []
    sorted_segments = sorted(segment_filenames, key=extract_segment_number)

    for item in sorted_segments:
        if isinstance(item, dict):
            raw_path = item.get("file_path") or item.get("filename") or item.get("path") or ""
        else:
            raw_path = str(item)

        base_name = os.path.basename(str(raw_path).strip())
        if not base_name or base_name == "output_audio":
            continue

        file_path = os.path.join(output_dir, base_name)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            valid_segments.append(file_path)
            print(f"[MERGER] ✅ Found: {base_name}")
        else:
            print(f"[MERGER] ⚠️ Missing: {file_path}")

    if len(valid_segments) == 0:
        print("[MERGER] ❌ No valid segments found!")
        return ""

    # ============================================================
    # OPSI 1: Merge dengan FFmpeg (LEBIH STABIL)
    # ============================================================
    try:
        print("[MERGER] Using FFmpeg for merging...")

        # Buat file list untuk FFmpeg
        list_path = output_path.replace(".mp3", "_list.txt")
        with open(list_path, "w") as f:
            for seg in valid_segments:
                f.write(f"file '{seg}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"[MERGER] ✅ FFmpeg merge success: {output_path}")
            os.remove(list_path)

            if cleanup_segments:
                for seg in valid_segments:
                    try:
                        os.remove(seg)
                    except:
                        pass

            return output_filename
        else:
            print(f"[MERGER] ❌ FFmpeg failed: {result.stderr}")
            os.remove(list_path)

    except Exception as e:
        print(f"[MERGER] ❌ FFmpeg error: {e}")

    # ============================================================
    # OPSI 2: Fallback ke pydub (Jika FFmpeg gagal)
    # ============================================================
    print("[MERGER] Falling back to pydub...")

    try:
        combined = AudioSegment.empty()
        for seg_path in valid_segments:
            try:
                audio = AudioSegment.from_file(seg_path, format="mp3")
                audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
                audio = audio.set_channels(TARGET_CHANNELS)
                combined += audio
                combined += AudioSegment.silent(duration=300, frame_rate=TARGET_SAMPLE_RATE)
                print(f"[MERGER] ✅ Added: {os.path.basename(seg_path)}")
            except Exception as e:
                print(f"[MERGER] ❌ Failed: {os.path.basename(seg_path)} - {e}")

        if len(combined) > 500:
            combined.export(output_path, format="mp3", bitrate="192k")
            print(f"[MERGER] ✅ pydub merge success: {output_path}")
            return output_filename
        else:
            print("[MERGER] ❌ pydub merge failed - audio too short")

    except Exception as e:
        print(f"[MERGER] ❌ pydub error: {e}")

    return ""