import json
import re
import requests
from app.config import settings

def run_metadata_agent(keyword: str, research_text: str) -> dict:
    """
    Agent 4: Metadata Agent untuk menghasilkan SEO Metadata multi-platform (TikTok & Spotify).
    """
    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "Anda adalah SEO & Content Marketing Specialist untuk VoxFlow AI.\n"
        "TUGAS: Buat metadata podcast multi-platform (TikTok dan Spotify) berdasarkan keyword dan data riset.\n"
        "OUTPUT WAJIB BERUPA FORMAT JSON MURNI DENGAN STRUKTUR SBB:\n"
        "{\n"
        '  "tiktok": {\n'
        '    "title": "Judul video TikTok yang catchy & pendek",\n'
        '    "description": "Deskripsi singkat dengan hashtag TikTok",\n'
        '    "tags": ["tag1", "tag2", "tag3"],\n'
        '    "cta": "Call to action untuk TikTok"\n'
        '  },\n'
        '  "spotify": {\n'
        '    "episode_title": "Judul Episode Podcast Profesional untuk Spotify",\n'
        '    "show_notes": "Show notes lengkap, ringkasan pembahasan, dan poin-poin utama untuk Spotify",\n'
        '    "season_number": 1,\n'
        '    "episode_number": 1,\n'
        '    "tags": ["tag1", "tag2"]\n'
        '  },\n'
        '  "general": {\n'
        '    "target_audience": "Target pendengar (misal: Programmer/Marketer Indonesia)"\n'
        '  }\n'
        "}"
    )

    payload = {
        "model": "qwen3.7-max",
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

    # Fallback Metadata (Multi-Platform)
    return {
        "tiktok": {
            "title": f"Fakta menarik seputar {keyword.title()}",
            "description": f"Pembahasan singkat mengenai {keyword} #voxflow #podcastai",
            "tags": [keyword, "podcastai", "faktaunik"],
            "cta": "Jangan lupa follow untuk info menarik lainnya!"
        },
        "spotify": {
            "episode_title": f"Deep Dive: Mengupas Tuntas {keyword.title()}",
            "show_notes": f"Dalam episode kali ini, kita membahas secara mendalam mengenai {keyword} dan implikasinya di era modern.",
            "season_number": 1,
            "episode_number": 1,
            "tags": [keyword, "tech", "podcast"]
        },
        "general": {
            "target_audience": "Masyarakat umum dan praktisi teknologi Indonesia"
        }
    }