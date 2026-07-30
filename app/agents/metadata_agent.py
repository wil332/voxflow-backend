# app/agents/metadata_agent.py

import json
import re
import requests
from app.config import settings

def run_metadata_agent(keyword: str, research_text: str, language: str = "indonesian") -> dict:
    print(f"[METADATA] Language: {language}")

    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    # === PROMPT BERDASARKAN BAHASA ===
    if language == "indonesian":
        system_prompt = (
            "Anda adalah SEO & Content Marketing Specialist untuk VoxFlow AI.\n"
            "TUGAS: Buat metadata podcast yang dioptimalkan untuk SEO.\n"
            "WAJIB: Gunakan BAHASA INDONESIA untuk semua output.\n"
            "OUTPUT WAJIB BERUPA FORMAT JSON MURNI DENGAN STRUKTUR SBB:\n"
            '{"title": "...", "description": "...", "tags": ["tag1", "tag2"], "target_audience": "...", "cta": "..."}'
        )
    elif language == "english":
        system_prompt = (
            "You are an SEO & Content Marketing Specialist for VoxFlow AI.\n"
            "TASK: Create SEO-optimized podcast metadata.\n"
            "MUST: Use ENGLISH for all output.\n"
            "OUTPUT MUST BE PURE JSON FORMAT:\n"
            '{"title": "...", "description": "...", "tags": ["tag1", "tag2"], "target_audience": "...", "cta": "..."}'
        )
    else:
        system_prompt = (
            "Anda adalah SEO & Content Marketing Specialist untuk VoxFlow AI.\n"
            "TUGAS: Buat metadata podcast yang dioptimalkan untuk SEO.\n"
            "WAJIB: Gunakan BAHASA INDONESIA untuk semua output.\n"
            "OUTPUT WAJIB BERUPA FORMAT JSON MURNI."
        )

    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

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
            cleaned_content = re.sub(r'```(?:json)?', '', content).strip()
            match = re.search(r'\{.*\}', cleaned_content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
    except Exception as e:
        print(f"[METADATA ERROR] {e}")

    # === FALLBACK ===
    lang_label = "Indonesia" if language == "indonesian" else "English"
    return {
        "title": f"Episode Podcast: {keyword.title()}",
        "description": f"Pembahasan mendalam tentang {keyword} untuk audiens {lang_label}.",
        "tags": [keyword, "podcast", "ai"],
        "target_audience": f"Masyarakat {lang_label}",
        "cta": "Subscribe dan bagikan!"
    }