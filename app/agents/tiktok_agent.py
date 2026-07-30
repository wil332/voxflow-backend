# app/agents/tiktok_agent.py
"""
Upload otomatis ke TikTok pakai cookie session.
Cookie dibaca dari environment variable TIKTOK_COOKIES_CONTENT (bukan file
fisik), supaya aman di-deploy ke Railway tanpa perlu commit file sensitif
ke Git.
"""

import os
import tempfile
from app.config import settings

try:
    from tiktok_uploader.upload import upload_video
except ImportError:
    upload_video = None


def _get_cookies_file_path() -> str:
    """
    Kalau ada env var TIKTOK_COOKIES_CONTENT, tulis isinya ke file sementara
    di server (Railway punya /tmp yang writable), lalu balikin path-nya.
    Kalau tidak ada, fallback ke file fisik biasa (buat development lokal).
    """
    cookies_content = os.getenv("TIKTOK_COOKIES_CONTENT")

    if cookies_content:
        # Tulis ke file sementara di /tmp (writable di Railway)
        temp_path = os.path.join(tempfile.gettempdir(), "tiktok_cookies.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(cookies_content)
        return temp_path

    # Fallback: file fisik lokal (buat development di laptop)
    return getattr(settings, "TIKTOK_COOKIES_PATH", "tiktok_cookies.txt")


def publish_to_tiktok_webhook(video_filename: str, metadata: dict) -> dict:
    if upload_video is None:
        return {
            "status": "error",
            "error": "Library 'tiktok-uploader' belum terinstall. Jalankan: pip install tiktok-uploader"
        }

    video_path = os.path.join(settings.OUTPUT_VIDEO_DIR, video_filename)
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"File video tidak ditemukan: {video_path}"}

    cookies_path = _get_cookies_file_path()
    if not os.path.exists(cookies_path):
        return {
            "status": "error",
            "error": f"File cookie TikTok tidak ditemukan di: {cookies_path}. "
                     f"Pastikan environment variable TIKTOK_COOKIES_CONTENT sudah diset di Railway."
        }

    hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in metadata.get("tags", [])])
    caption = f"{metadata.get('title', '')}\n\n{metadata.get('description', '')}\n\n{hashtags}"

    try:
        print(f"[TIKTOK AGENT] Mulai upload otomatis via cookie: {video_filename}")

        upload_video(
            filename=video_path,
            description=caption,
            cookies=cookies_path,
            headless=True,
        )

        print("[TIKTOK AGENT SUCCESS] Video berhasil di-upload otomatis via cookie!")
        return {
            "status": "success",
            "message": "Video berhasil diupload otomatis ke TikTok via cookie session!",
            "data": {"video_filename": video_filename, "caption": caption}
        }

    except Exception as e:
        print(f"[TIKTOK AGENT ERROR] Gagal upload via cookie: {e}")
        return {"status": "error", "error": str(e)}