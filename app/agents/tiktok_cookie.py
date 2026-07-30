# app/agents/tiktok_cookie.py

import os
import requests
from app.config import settings

def upload_to_tiktok_with_cookie(video_path: str, metadata: dict) -> dict:
    """
    Upload video ke TikTok langsung menggunakan 3 cookie:
    - sessionid
    - sid_tt
    - tt_csrf_token
    """
    # Ambil 3 cookie dari environment (Railway)
    sessionid = settings.TIKTOK_SESSIONID
    sid_tt = settings.TIKTOK_SID_TT
    csrf_token = settings.TIKTOK_CSRF_TOKEN

    # Cek apakah 3 cookie lengkap
    if not sessionid or not sid_tt or not csrf_token:
        return {
            "status": "error",
            "error": "Cookie TikTok tidak lengkap. Set TIKTOK_SESSIONID, TIKTOK_SID_TT, dan TIKTOK_CSRF_TOKEN di Railway."
        }

    # Siapkan cookies (hanya 3)
    cookies = {
        "sessionid": sessionid,
        "sid_tt": sid_tt,
        "tt_csrf_token": csrf_token,
        # passport_csrf_token tidak wajib, skip
    }

    # Headers (harus mirip browser)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
        "Origin": "https://www.tiktok.com",
        "X-CSRFToken": csrf_token,  # tambahkan CSRF di header
    }

    # Endpoint upload
    upload_url = "https://www.tiktok.com/api/v1/upload/"

    # Format caption
    hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in metadata.get("tags", [])])
    caption = f"{metadata.get('title', 'Podcast Episode')}\n\n{metadata.get('description', '')[:200]}\n\n{hashtags}"

    # Siapkan file dan data
    files = {"video": open(video_path, "rb")}
    data = {
        "title": metadata.get("title", "Podcast Episode"),
        "description": caption,
        "visibility": "0",  # 0 = public, 1 = private
    }

    try:
        print(f"[TIKTOK COOKIE] 📤 Uploading: {os.path.basename(video_path)}")
        print(f"[TIKTOK COOKIE] SessionID: {sessionid[:10]}...")
        print(f"[TIKTOK COOKIE] SID_TT: {sid_tt[:10]}...")
        print(f"[TIKTOK COOKIE] CSRF: {csrf_token[:10]}...")

        response = requests.post(
            upload_url,
            files=files,
            data=data,
            cookies=cookies,
            headers=headers,
            timeout=60
        )

        print(f"[TIKTOK COOKIE] Response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"[TIKTOK COOKIE] Response JSON: {result}")

            if result.get("status_code") == 0:
                video_id = result.get("video_id")
                share_url = f"https://www.tiktok.com/@/video/{video_id}"
                print(f"[TIKTOK COOKIE] ✅ Success! {share_url}")
                return {
                    "status": "success",
                    "url": share_url,
                    "video_id": video_id,
                    "data": result
                }
            else:
                error = result.get("status_msg", "Unknown error")
                print(f"[TIKTOK COOKIE] ❌ Failed: {error}")
                return {"status": "error", "error": error, "data": result}
        else:
            print(f"[TIKTOK COOKIE] ❌ HTTP {response.status_code}")
            print(f"[TIKTOK COOKIE] Response text: {response.text[:500]}")
            return {"status": "error", "error": f"HTTP {response.status_code}: {response.text[:200]}"}

    except Exception as e:
        print(f"[TIKTOK COOKIE] ❌ Exception: {e}")
        return {"status": "error", "error": str(e)}