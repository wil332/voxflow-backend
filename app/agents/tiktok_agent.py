# app/agents/tiktok_agent.py
"""
Upload otomatis ke TikTok pakai cookie session, menggantikan webhook eksternal.

SETUP YANG DIBUTUHKAN:
1. Install library: pip install tiktok-uploader
2. Install browser driver Chrome/Chromium (tiktok-uploader butuh Selenium)
3. Export cookie login TikTok kamu ke file "tiktok_cookies.txt" format Netscape,
   pakai extension browser seperti "Get cookies.txt LOCALLY"
4. Taruh file cookie itu di root project, atau set path-nya lewat env var TIKTOK_COOKIES_PATH
"""

import os
from app.config import settings

try:
    from tiktok_uploader.upload import upload_video
except ImportError:
    upload_video = None


def publish_to_tiktok_webhook(video_filename: str, metadata: dict) -> dict:
    """
    Nama fungsi dipertahankan sama (publish_to_tiktok_webhook) supaya main.py
    tidak perlu diubah — tapi sekarang isinya upload via cookie, bukan webhook.
    """
    if upload_video is None:
        return {
            "status": "error",
            "error": "Library 'tiktok-uploader' belum terinstall. Jalankan: pip install tiktok-uploader"
        }

    video_path = os.path.join(settings.OUTPUT_VIDEO_DIR, video_filename)
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"File video tidak ditemukan: {video_path}"}

    cookies_path = getattr(settings, "TIKTOK_COOKIES_PATH", "tiktok_cookies.txt")
    if not os.path.exists(cookies_path):
        return {"status": "error", "error": f"File cookie TikTok tidak ditemukan di: {cookies_path}"}

    hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in metadata.get("tags", [])])
    caption = f"{metadata.get('title', '')}\n\n{metadata.get('description', '')}\n\n{hashtags}"

    try:
        print(f"[TIKTOK AGENT] Mulai upload otomatis via cookie: {video_filename}")

        upload_video(
            filename=video_path,
            description=caption,
            cookies=cookies_path,
            headless=True,  # jalan tanpa buka jendela browser (cocok buat server)
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