import os
import subprocess
from PIL import Image
from app.config import settings
from app.utils.subtitle_generator import generate_ass_subtitles

def ensure_background_exists(bg_path: str):
    """Membuat gambar background default jika file tiktok_bg.png belum ada."""
    if not os.path.exists(bg_path):
        print(f"[ASSETS] Background tidak ditemukan. Membuat gambar default di: {bg_path}")
        img = Image.new("RGB", (1080, 1920), color=(15, 23, 42))
        img.save(bg_path, "PNG")

def create_tiktok_video_with_subtitles(audio_filename: str, metadata: dict) -> str:
    """
    Membuat video MP4 dengan:
    - Background image 1080x1920
    - Audio dari file MP3
    - Waveform
    - Subtitle otomatis dari Whisper
    """
    audio_dir = settings.OUTPUT_AUDIO_DIR
    output_dir = settings.OUTPUT_VIDEO_DIR
    assets_dir = settings.ASSETS_DIR

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    audio_path = os.path.join(audio_dir, audio_filename)

    # ============================================================
    # CEK: APAKAH FILE AUDIO ADA?
    # ============================================================
    if not os.path.exists(audio_path):
        print(f"[VIDEO ENGINE] ❌ Audio file not found: {audio_path}")
        return ""

    # ============================================================
    # CEK: APAKAH FILE AUDIO BISA DIBACA (UKURAN > 0)?
    # ============================================================
    if os.path.getsize(audio_path) == 0:
        print(f"[VIDEO ENGINE] ❌ Audio file is empty: {audio_path}")
        return ""

    video_filename = audio_filename.replace(".mp3", ".mp4")
    output_video_path = os.path.join(output_dir, video_filename)

    # 1. Pastikan Background Gambar Tersedia
    background_image = os.path.join(assets_dir, "tiktok_bg.png")
    ensure_background_exists(background_image)

    # 2. Generate Subtitle .ass dari File Audio
    ass_path = os.path.join(output_dir, f"temp_{audio_filename.replace('.mp3', '')}.ass")
    try:
        generate_ass_subtitles(audio_path, ass_path)
        print(f"[VIDEO ENGINE] ✅ Subtitle generated: {ass_path}")
    except Exception as e:
        print(f"[VIDEO ENGINE] ❌ Subtitle generation failed: {e}")
        return ""

    # FFmpeg dari PATH
    ffmpeg_bin = "ffmpeg"

    # Escape path untuk filter subtitles
    clean_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")

    # 3. Perintah FFmpeg
    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1", "-i", background_image,
        "-i", audio_path,
        "-filter_complex",
        (
            "[1:a]showwaves=s=800x150:mode=line:colors=#2563EB[wave];"
            "[0:v][wave]overlay=(W-w)/2:1200[v_wave];"
            f"[v_wave]subtitles='{clean_ass_path}'[v_out]"
        ),
        "-map", "[v_out]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output_video_path
    ]

    try:
        print(f"[VIDEO ENGINE] 🎬 Rendering video: {video_filename}")
        print(f"[VIDEO ENGINE] Command: {' '.join(cmd)}")

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"[VIDEO ENGINE] ✅ FFmpeg output: {result.stdout}")

        # 4. Cek apakah file video berhasil dibuat
        if os.path.exists(output_video_path) and os.path.getsize(output_video_path) > 0:
            print(f"[VIDEO ENGINE] ✅ Video created: {output_video_path} ({os.path.getsize(output_video_path)} bytes)")

            # Cleanup subtitle temp
            if os.path.exists(ass_path):
                os.remove(ass_path)

            return video_filename
        else:
            print(f"[VIDEO ENGINE] ❌ Video file not created or empty")
            return ""

    except subprocess.CalledProcessError as e:
        print(f"[VIDEO ENGINE] ❌ FFmpeg error: {e.stderr}")
        if os.path.exists(ass_path):
            os.remove(ass_path)
        return ""
    except Exception as e:
        print(f"[VIDEO ENGINE] ❌ Error: {e}")
        if os.path.exists(ass_path):
            os.remove(ass_path)
        return ""