# app/agents/tiktok_agent.py

import os
import requests
from app.config import settings
from app.agents.tiktok_cookie import upload_to_tiktok_with_cookie

def publish_to_tiktok_webhook(video_filename: str, metadata: dict) -> dict:
    """
    Upload ke TikTok: coba webhook dulu, jika gagal fallback ke cookie.
    """
    webhook_url = getattr(settings, "TIKTOK_WEBHOOK_URL", "")
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    video_url = f"{base_url}/api/v1/podcast/video/{video_filename}"

    # Format caption
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
    # 1. COBA WEBHOOK (jika ada)
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
    # 2. FALLBACK: UPLOAD LANGSUNG PAKAI 3 COOKIE
    # ============================================================
    print("[TIKTOK AGENT] 🔄 Fallback: mencoba upload dengan 3 cookie...")
    video_path = os.path.join(settings.OUTPUT_VIDEO_DIR, video_filename)

    if not os.path.exists(video_path):
        return {
            "status": "error",
            "error": f"File video tidak ditemukan: {video_path}"
        }

    cookie_result = upload_to_tiktok_with_cookie(video_path, metadata)
    return cookie_result