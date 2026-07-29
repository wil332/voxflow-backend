# app/agents/tiktok_agent.py
import requests
from app.config import settings

def publish_to_tiktok_webhook(video_filename: str, metadata: dict) -> dict:
    webhook_url = getattr(settings, "TIKTOK_WEBHOOK_URL", "")
    
    # 🔗 URL video publik yang bisa diakses (Sesuaikan domain jika sudah dipublish)
    # Jika masih di local/dev, gunakan IP/Host lokal kamu
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    video_url = f"{base_url}/api/v1/podcast/video/{video_filename}"
    
    # Format Hashtags
    hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in metadata.get("tags", [])])
    caption = f"🎙️ {metadata.get('title', '')}\n\n{metadata.get('description', '')}\n\n{hashtags}"

    # Payload asli yang dikirim ke TikTok Webhook
    payload = {
        "video_url": video_url,
        "title": metadata.get("title", ""),
        "caption": caption,
        "aspect_ratio": "9:16",
        "cta": metadata.get("cta", "Jangan lupa follow!")
    }

    # 🚀 UBAH MODE TEST MENJADI LIVE POST REQUEST
    if not webhook_url or "maxy-api.com" in webhook_url:
        print("[TIKTOK AGENT] Memulai pengiriman LIVE ke Webhook...")

    try:
        # Kirim data ke Webhook TikTok MAXY
        response = requests.post(webhook_url, json=payload, timeout=30)
        
        if response.status_code in [200, 201]:
            print("[TIKTOK AGENT SUCCESS] Berhasil terkirim ke Webhook MAXY!")
            return {
                "status": "success",
                "message": "Video berhasil dipublikasikan ke TikTok!",
                "data": response.json() if response.content else payload
            }
        else:
            print(f"[TIKTOK AGENT ERROR] Webhook menolak request: {response.status_code}")
            return {
                "status": "error",
                "error": f"HTTP {response.status_code}: {response.text}"
            }

    except Exception as e:
        print(f"[TIKTOK AGENT EXCEPTION] Gagal koneksi ke Webhook: {e}")
        return {
            "status": "error",
            "error": str(e)
        }