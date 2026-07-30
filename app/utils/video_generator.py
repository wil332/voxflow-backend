import os
import subprocess
from PIL import Image

from app.config import settings
from app.utils.subtitle_generator import generate_ass_subtitles


def ensure_background_exists(bg_path: str):
    """
    Membuat background default jika belum ada.
    """
    if not os.path.exists(bg_path):
        print(f"[ASSETS] Background tidak ditemukan. Membuat: {bg_path}")

        img = Image.new(
            "RGB",
            (1080, 1920),
            color=(15, 23, 42)
        )

        img.save(bg_path, "PNG")


def create_tiktok_video_with_subtitles(audio_filename: str, metadata: dict) -> str:

    audio_dir = settings.OUTPUT_AUDIO_DIR
    output_dir = settings.OUTPUT_VIDEO_DIR
    assets_dir = settings.ASSETS_DIR

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)

    audio_path = os.path.join(audio_dir, audio_filename)

    video_filename = audio_filename.replace(".mp3", ".mp4")

    output_video_path = os.path.join(
        output_dir,
        video_filename
    )

    background_image = os.path.join(
        assets_dir,
        "tiktok_bg.png"
    )

    ensure_background_exists(background_image)

    # -----------------------------
    # Validasi audio
    # -----------------------------

    if not os.path.exists(audio_path):
        print(f"[ERROR] Audio tidak ditemukan:")
        print(audio_path)
        return ""

    if os.path.getsize(audio_path) == 0:
        print("[ERROR] Audio kosong.")
        return ""

    # -----------------------------
    # Generate subtitle
    # -----------------------------

    ass_path = os.path.join(
        output_dir,
        f"temp_{audio_filename.replace('.mp3','')}.ass"
    )

    try:
        print("[VIDEO ENGINE] Generate subtitle...")

        generate_ass_subtitles(
            audio_path,
            ass_path
        )

    except Exception as e:

        print("\n========== WHISPER ERROR ==========")
        print(str(e))
        return ""

    # -----------------------------
    # Validasi subtitle
    # -----------------------------

    if not os.path.exists(ass_path):
        print("[ERROR] Subtitle gagal dibuat.")
        return ""

    if os.path.getsize(ass_path) == 0:
        print("[ERROR] Subtitle kosong.")
        return ""

    ffmpeg_bin = "ffmpeg"

    clean_ass_path = os.path.abspath(ass_path)
    clean_ass_path = clean_ass_path.replace("\\", "/")
    clean_ass_path = clean_ass_path.replace(":", "\\:")

    filter_complex = (
        "[1:a]"
        "showwaves=s=800x150:mode=line:colors=blue[wave];"
        "[0:v][wave]"
        "overlay=(W-w)/2:1200[v_wave];"
        f"[v_wave]subtitles='{clean_ass_path}'[v_out]"
    )

    # ============================================================
    # CATATAN PERBAIKAN -- kenapa render sebelumnya kena exit code -9:
    # ============================================================
    # Exit code -9 = proses menerima SIGKILL, hampir selalu berarti
    # OOM killer container yang membunuh proses karena kehabisan memori.
    # Di log sebelumnya, libx264 mendeteksi "threads=60" secara otomatis
    # (auto-detect dari jumlah core yang terlihat container, yang di
    # environment seperti Railway sering tidak merefleksikan RAM yang
    # SEBENARNYA dialokasikan). Makin banyak thread encoding paralel,
    # makin besar buffer memori yang dialokasikan libx264 -- gampang
    # sekali menabrak limit RAM container dan langsung di-kill.
    #
    # Fix: batasi "-threads" secara eksplisit (bukan auto-detect), dan
    # pakai preset yang lebih ringan memori ("veryfast" -- x264 preset
    # yang lebih berat seperti "medium"/"slow" butuh buffer lookahead
    # lebih besar). CRF dinaikkan sedikit (kualitas visual TikTok tidak
    # butuh bitrate setinggi film) supaya beban encoding lebih ringan.
    FFMPEG_THREADS = str(getattr(settings, "FFMPEG_THREADS", 2))

    cmd = [

        ffmpeg_bin,

        "-y",

        "-loop",
        "1",

        "-i",
        background_image,

        "-i",
        audio_path,

        "-filter_complex",
        filter_complex,

        "-map",
        "[v_out]",

        "-map",
        "1:a",

        "-c:v",
        "libx264",

        "-threads",
        FFMPEG_THREADS,

        "-preset",
        "veryfast",

        "-crf",
        "26",

        "-c:a",
        "aac",

        "-pix_fmt",
        "yuv420p",

        "-shortest",

        output_video_path

    ]

    print("\n========== FFMPEG COMMAND ==========")
    print(" ".join(cmd))

    try:

        print("\n[VIDEO ENGINE] Rendering video...\n")

        # Timeout ditambahkan supaya kalau proses macet (bukan OOM, tapi
        # misal filter graph nyangkut), job tidak menggantung tanpa batas
        # dan memblokir worker lain selamanya.
        result = subprocess.run(

            cmd,

            capture_output=True,

            text=True,

            timeout=600,  # 10 menit -- sesuaikan kalau durasi podcast biasanya lebih panjang

        )

        print("\n========== STDOUT ==========")
        print(result.stdout)

        print("\n========== STDERR ==========")
        print(result.stderr)

        print("\n========== EXIT CODE ==========")
        print(result.returncode)

        if result.returncode != 0:

            print("[VIDEO ENGINE ERROR] FFmpeg gagal.")
            if result.returncode < 0:
                print(f"[VIDEO ENGINE ERROR] Proses dibunuh oleh sinyal {-result.returncode} "
                      f"(sinyal 9 = SIGKILL, biasanya OOM killer container kehabisan memori).")

            if os.path.exists(ass_path):
                os.remove(ass_path)

            return ""

        if not os.path.exists(output_video_path):

            print("[ERROR] Output video tidak ditemukan.")

            if os.path.exists(ass_path):
                os.remove(ass_path)

            return ""

        if os.path.getsize(output_video_path) == 0:

            print("[ERROR] Output video kosong.")

            if os.path.exists(ass_path):
                os.remove(ass_path)

            return ""

        if os.path.exists(ass_path):
            os.remove(ass_path)

        print("\n====================================")
        print("[VIDEO ENGINE SUCCESS]")
        print(output_video_path)
        print("====================================\n")

        return video_filename

    except subprocess.TimeoutExpired:
        print("[VIDEO ENGINE ERROR] FFmpeg timeout -- proses dihentikan paksa setelah 600 detik.")
        if os.path.exists(ass_path):
            os.remove(ass_path)
        return ""

    except Exception as e:

        print("\n========== VIDEO ENGINE EXCEPTION ==========")
        print(str(e))

        if os.path.exists(ass_path):
            os.remove(ass_path)

        return ""