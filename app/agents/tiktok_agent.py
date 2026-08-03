# app/agents/tiktok_agent.py

import os
import tempfile
import requests
from app.config import settings

try:
    from tiktok_uploader.upload import upload_video
except ImportError:
    upload_video = None


def _get_cookies_file_path() -> str:
    """
    Cookie diambil dari environment variable TIKTOK_COOKIES_CONTENT (Railway),
    ditulis ke file sementara di /tmp supaya tiktok-uploader bisa membacanya.
    """
    cookies_content = os.getenv("TIKTOK_COOKIES_CONTENT")
    if cookies_content:
        temp_path = os.path.join(tempfile.gettempdir(), "tiktok_cookies.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(cookies_content)
        return temp_path
    return getattr(settings, "TIKTOK_COOKIES_PATH", "tiktok_cookies.txt")


def publish_to_tiktok_webhook(video_filename: str, metadata: dict) -> dict:
    """
    Upload ke TikTok: coba webhook dulu, jika gagal fallback ke upload
    LANGSUNG via Selenium + cookie (TANPA lewat gateway/webhook pihak ketiga
    yang sebelumnya sering error 502 Bad Gateway - KRAKEND.BACKEND).
    """
    webhook_url = getattr(settings, "TIKTOK_WEBHOOK_URL", "")
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    video_url = f"{base_url}/api/v1/podcast/video/{video_filename}"

    hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in metadata.get("tags", [])])
    caption = f"{metadata.get('title', '')}\n\n{metadata.get('description', '')}\n\n{hashtags}"

    payload = {
        "video_url": video_url,
        "title": metadata.get("title", "Podcast Episode"),
        "caption": caption,
        "aspect_ratio": "9:16",
        "cta": metadata.get("cta", "Jangan lupa follow!")
    }

    # ============================================================
    # 1. COBA WEBHOOK RESMI DULU (kalau ada dan aktif)
    # ============================================================
    if webhook_url:
        try:
            print("[TIKTOK AGENT] 📤 Mencoba Webhook...")
            response = requests.post(webhook_url, json=payload, timeout=30)

            if response.status_code in [200, 201]:
                print("[TIKTOK AGENT] ✅ Webhook berhasil!")
                return {
                    "status": "success",
                    "message": "Video berhasil dipublikasikan ke TikTok via webhook!",
                    "data": response.json() if response.content else payload
                }
            else:
                print(f"[TIKTOK AGENT] ⚠️ Webhook gagal ({response.status_code})")
        except Exception as e:
            print(f"[TIKTOK AGENT] ⚠️ Webhook error: {e}")

    # ============================================================
    # 2. FALLBACK: Upload LANGSUNG via Selenium + cookie
    #    (bypass gateway pihak ketiga yang sebelumnya sering 502)
    # ============================================================
    print("[TIKTOK AGENT] 🔄 Fallback: upload langsung via Selenium + cookie (tanpa gateway)...")

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
                     f"Set environment variable TIKTOK_COOKIES_CONTENT di Railway."
        }

    try:
        upload_video(
            filename=video_path,
            description=caption,
            cookies=cookies_path,
            headless=True,
            browser="chrome",
        )

        print("[TIKTOK AGENT] ✅ Fallback Selenium berhasil, tanpa perlu gateway eksternal!")
        return {
            "status": "success",
            "message": "Video berhasil diupload langsung ke TikTok via cookie session (Selenium)!",
            "data": {"video_filename": video_filename, "caption": caption}
        }

    except Exception as e:
        print(f"[TIKTOK AGENT] ❌ Fallback Selenium juga gagal: {e}")
        return {"status": "error", "error": str(e)}