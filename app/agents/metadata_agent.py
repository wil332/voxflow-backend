import json
import re
import requests
from app.config import settings

def run_metadata_agent(keyword: str, research_text: str) -> dict:
    """
    Agent 4: Metadata Agent untuk menghasilkan SEO Metadata otomatis dari podcast.
    """
    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "Anda adalah SEO & Content Marketing Specialist untuk PodFlow AI.\n"
        "TUGAS: Buat metadata podcast yang dioptimalkan untuk SEO berdasarkan keyword dan data riset.\n"
        "OUTPUT WAJIB BERUPA FORMAT JSON MURNI DENGAN STRUKTUR SBB:\n"
        "{\n"
        '  "title": "Judul Podcast Catchy & SEO Friendly",\n'
        '  "description": "Rangkuman deskripsi episode 2-3 kalimat",\n'
        '  "tags": ["tag1", "tag2", "tag3", "tag4"],\n'
        '  "target_audience": "Target pendengar (misal: Programmer/Marketer Indonesia)",\n'
        '  "cta": "Call to action untuk pendengar"\n'
        "}"
    )

    # ================================================================
    # PERBAIKAN: Model distandarisasi ke "qwen-max" (stabil & aman)
    # ================================================================
    payload = {
        "model": "qwen-max",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Keyword Utama: {keyword}\n\nData Riset:\n{research_text[:300]}"}
        ],
        "temperature": 0.5
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']

            # Clean JSON
            cleaned_content = re.sub(r'```(?:json)?', '', content).strip()
            match = re.search(r'\{.*\}', cleaned_content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
    except Exception as e:
        print(f"[METADATA AGENT ERROR] Gagal generate metadata: {e}")

    # Fallback Metadata
    return {
        "title": f"Episode Podcast: {keyword.title()}",
        "description": f"Pembahasan mendalam dan tutorial praktis seputar {keyword} untuk audiens Indonesia.",
        "tags": [keyword, "podcast ai", "otomatisasi", "podflow"],
        "target_audience": "Masyarakat umum dan praktisi teknologi Indonesia",
        "cta": "Jangan lupa subscribe dan bagikan episode ini jika bermanfaat!"
    }