import json
import re
import requests
from app.config import settings

def run_scriptwriter_agent(
    research_text: str,
    language: str = "id",
    tone: str = "professional",
    voice: str = "mixed",
    duration: str = "5-10",
    host_count: int = 2,
) -> list:
    """
    Agent 2: Agnes AI Scriptwriter dengan instruksi dialog mendalam.
    """
    url = "https://apihub.agnes-ai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.AGNES_API_KEY}",
        "Content-Type": "application/json"
    }

    language_instruction = (
        "Seluruh dialog WAJIB menggunakan Bahasa Indonesia."

    )

    tone_instruction = {
        "professional": "Gunakan gaya profesional, objektif, dan berbobot.",
        "casual": "Gunakan gaya santai seperti percakapan sehari-hari.",
        "funny": "Gunakan gaya ringan dengan humor seperlunya.",
        "educational": "Gunakan gaya edukatif yang jelas dan mudah dipahami."
    }.get(tone, "Gunakan gaya profesional.")

    voice_presets = {
        "mixed": ("Budi", "Richel"),
        "male": ("Budi", "Andi"),
        "female": ("Richel", "Alya")
    }

    host1, host2 = voice_presets.get(voice, ("Budi", "Richel"))

    duration_instruction = {
        "1-3": "6-8 dialog.",
        "5-10": "12-18 dialog.",
        "10-15": "20-28 dialog.",
        "15-20": "30-40 dialog."
    }.get(duration, "12-18 dialog.")

    host_instruction = (
        f"Gunakan SATU pembicara saja yaitu {host1}."
        if host_count == 1
        else f"Gunakan dua pembicara yaitu {host1} dan {host2}."
    )

    system_prompt = f"""
        Anda adalah Scriptwriter Podcast Profesional untuk VoxFlow AI.

        TUGAS
        Ubah hasil riset menjadi naskah podcast yang terdengar alami, menarik, dan informatif.

        {language_instruction}

        {tone_instruction}

        {host_instruction}

        DURASI
        {duration_instruction}

        ATURAN

        1. Percakapan harus terdengar natural seperti podcast sungguhan.

        2. Jangan membaca hasil riset secara verbatim.

        3. Tambahkan transisi antar topik.

        4. Gunakan pertanyaan dan tanggapan yang natural.

        5. Berikan contoh nyata bila memungkinkan.

        6. Hindari pengulangan kalimat.

        7. Tutup podcast dengan kesimpulan singkat.

        OUTPUT

        WAJIB berupa JSON VALID.

        Contoh:

        [
        {{
            "speaker":"{host1}",
            "emotion":"excited",
            "pause_duration":0.6,
            "text":"..."
        }},
        {{
            "speaker":"{host2}",
            "emotion":"curious",
            "pause_duration":0.5,
            "text":"..."
        }}
        ]

        Jangan menambahkan markdown.
        Jangan menggunakan ```json.
        Jangan menambahkan penjelasan.
        Output HARUS hanya berupa JSON Array.
    """
    payload = {
        "model": "agnes-2.0-flash",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"""
        Berikut hasil riset:

        {research_text}

        Buat naskah podcast sesuai seluruh instruksi di atas.
        """
            }
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
