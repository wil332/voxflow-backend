import json
import re
import requests
from app.config import settings

def run_scriptwriter_agent(research_text: str) -> list:
    """
    Agent 2: Agnes AI Scriptwriter dengan instruksi dialog mendalam.
    """
    url = "https://apihub.agnes-ai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.AGNES_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "Anda adalah Scriptwriter Podcast Profesional untuk VoxFlow AI.\n"
        "TUGAS: Ubah data riset menjadi naskah percakapan podcast antara Budi dan Richel.\n\n"
        "KARAKTER:\n"
        "- Budi: Antusias, suka humor lokal, pemikir kritis.\n"
        "- Richel: Inisiatif, edukatif, dan lebih terstruktur.\n\n"
        "ATURAN PENULISAN NASKAH:\n"
        "1. Durasi & Segmen: Buat percakapan interaktif (MINIMAL 8 hingga 14 dialog bergantian).\n"
        "2. SEO & Content Alignment: Bahas konsep edukasi, tutorial praktis, dan otomatisasi.\n"
        "3. STRICT FORMAT: OUTPUT WAJIB BERUPA FORMAT JSON MURNI (Array of Objects).\n\n"
        "Struktur JSON yang valid (Gunakan nama Budi dan Richel):\n"
        "[\n"
        '  {"speaker": "Budi", "emotion": "excited", "pause_duration": 0.8, "text": "..."},\n'
        '  {"speaker": "Richel", "emotion": "curious", "pause_duration": 0.5, "text": "..."}\n'
        "]"
    )

    payload = {
        "model": "agnes-2.0-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Data Riset:\n{research_text}"}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        data = response.json()
        raw_content = data['choices'][0]['message']['content']

        # === PERBAIKAN: Handle berbagai format Agnes ===
        # Bersihkan markdown
        cleaned_content = re.sub(r'```(?:json)?', '', raw_content).strip()

        # Coba parse JSON
        script_data = json.loads(cleaned_content)

        # Jika Agnes mengembalikan object dengan key "podcast_naskah"
        if isinstance(script_data, dict) and "podcast_naskah" in script_data:
            script_data = script_data["podcast_naskah"]

        # Jika masih dict, coba ambil array pertama
        if isinstance(script_data, dict):
            # Cari key yang berisi array
            for key, value in script_data.items():
                if isinstance(value, list):
                    script_data = value
                    break

        if isinstance(script_data, list) and len(script_data) > 0:
            return script_data
        else:
            raise ValueError("Data bukan array yang valid")

    except Exception as e:
        print(f"[SCRIPT AGENT FALLBACK TRIGGERED] Terjadi kesalahan: {e}")
        # FALLBACK: menggunakan nama Budi dan Richel (cocok dengan audio_agent)
        return [
            {"speaker": "Budi", "emotion": "excited", "pause_duration": 0.8, "text": "Halo semuanya! Selamat datang kembali di PodFlow AI Podcast."},
            {"speaker": "Richel", "emotion": "curious", "pause_duration": 0.5, "text": "Halo! Kali ini kita bakal bahas topik yang menarik banget nih seputar teknologi."},
            {"speaker": "Budi", "emotion": "neutral", "pause_duration": 0.8, "text": f"Betul banget, kita bakal ngobrolin hasil riset terbaru: {research_text[:60]}..."},
            {"speaker": "Richel", "emotion": "excited", "pause_duration": 0.5, "text": "Wah keren banget! Yuk langsung aja kita masuk ke pembahasan lengkapnya."}
        ]

# --- ALIAS: biarkan nama run_script_agent bisa dipanggil dari ai_pipeline ---
run_script_agent = run_scriptwriter_agent