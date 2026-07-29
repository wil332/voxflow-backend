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
    
    # Prompt dipertegas agar menghasilkan minimal 8-12 percakapan bergantian
    system_prompt = (
    "Anda adalah Scriptwriter Podcast Profesional untuk VoxFlow  AI.\n"
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
        
        if response.status_code != 200:
            print(f"[SCRIPT AGENT ERROR] Status API: {response.status_code} - {response.text}")
            raise ValueError(f"Agnes API Error status {response.status_code}")
            
        data = response.json()
        raw_content = data['choices'][0]['message']['content']
        
        # Log untuk memantau respons asli dari AI
        print(f"\n[SCRIPT AGENT LOG] Respons mentah dari Agnes AI:\n{raw_content[:200]}...\n")
        
        # 1. Bersihkan formatting markdown jika ada
        cleaned_content = re.sub(r'```(?:json)?', '', raw_content).strip()
        
        # 2. Ambil blok array JSON [...]
        match = re.search(r'\[.*\]', cleaned_content, re.DOTALL)
        if match:
            json_string = match.group(0)
        else:
            json_string = cleaned_content
            
        # 3. Parse JSON
        script_data = json.loads(json_string)
        
        if isinstance(script_data, list) and len(script_data) > 0:
            print(f"[SCRIPT AGENT SUCCESS] Berhasil membuat {len(script_data)} segmen naskah.")
            return script_data
        else:
            raise ValueError("Hasil parsing JSON bukan berupa list array valid.")
            
    except Exception as e:
        print(f"[SCRIPT AGENT FALLBACK TRIGGERED] Terjadi kesalahan: {e}")
        # Jika API Agnes error, fallback ini membuat 4 segmen percakapan agar tetap berjalan
        return [
            {"speaker": "Host_A", "emotion": "excited", "pause_duration": 0.8, "text": "Halo semuanya! Selamat datang kembali di PodFlow AI Podcast."},
            {"speaker": "Host_B", "emotion": "curious", "pause_duration": 0.5, "text": "Halo! Kali ini kita bakal bahas topik yang menarik banget nih seputar teknologi."},
            {"speaker": "Host_A", "emotion": "neutral", "pause_duration": 0.8, "text": f"Betul banget, kita bakal ngobrolin hasil riset terbaru: {research_text[:60]}..."},
            {"speaker": "Host_B", "emotion": "excited", "pause_duration": 0.5, "text": "Wah keren banget! Yuk langsung aja kita masuk ke pembahasan lengkapnya."}
        ]