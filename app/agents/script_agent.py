# app/agents/script_agent.py

import json
import re
import requests
from app.config import settings

def run_scriptwriter_agent(research_text: str, language: str = "indonesian", tone: str = "professional") -> list:
    print(f"[SCRIPT] Language: {language}, Tone: {tone}")

    url = "https://apihub.agnes-ai.com/v1/chat/completions"

    # === PROMPT BERDASARKAN BAHASA ===
    if language == "indonesian":
        system_prompt = (
            "Anda adalah Scriptwriter Podcast Profesional untuk VoxFlow AI.\n"
            f"TUGAS: Ubah data riset menjadi naskah percakapan podcast antara Budi dan Richel.\n"
            f"WAJIB: Gunakan BAHASA INDONESIA untuk semua dialog.\n"
            f"TONE: {tone}\n"
            "KARAKTER: Budi (antusias, humor lokal) dan Richel (edukatif, terstruktur).\n"
            "STRICT FORMAT: OUTPUT WAJIB BERUPA FORMAT JSON MURNI (Array of Objects)."
        )
    elif language == "english":
        system_prompt = (
            "You are a Professional Podcast Scriptwriter for VoxFlow AI.\n"
            f"TASK: Convert research data into a podcast conversation script between Budi and Richel.\n"
            f"MUST: Use ENGLISH for all dialogues.\n"
            f"TONE: {tone}\n"
            "CHARACTERS: Budi (enthusiastic, critical thinker) and Richel (initiative, educational).\n"
            "STRICT FORMAT: OUTPUT MUST BE PURE JSON FORMAT (Array of Objects)."
        )
    else:
        system_prompt = (
            "Anda adalah Scriptwriter Podcast Profesional untuk VoxFlow AI.\n"
            f"TUGAS: Ubah data riset menjadi naskah percakapan podcast antara Budi dan Richel.\n"
            f"WAJIB: Gunakan BAHASA INDONESIA untuk semua dialog.\n"
            f"TONE: {tone}\n"
            "STRICT FORMAT: OUTPUT WAJIB BERUPA FORMAT JSON MURNI (Array of Objects)."
        )

    headers = {
        "Authorization": f"Bearer {settings.AGNES_API_KEY}",
        "Content-Type": "application/json"
    }

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
            raise ValueError(f"Agnes API Error status {response.status_code}")

        data = response.json()
        raw_content = data['choices'][0]['message']['content']

        cleaned_content = re.sub(r'```(?:json)?', '', raw_content).strip()
        match = re.search(r'\[.*\]', cleaned_content, re.DOTALL)
        script_data = json.loads(match.group(0) if match else cleaned_content)

        if isinstance(script_data, list) and len(script_data) > 0:
            return script_data
        else:
            raise ValueError("Hasil parsing JSON bukan berupa list array valid.")

    except Exception as e:
        print(f"[SCRIPT FALLBACK] {e}")
        return [
            {"speaker": "Budi", "emotion": "excited", "pause_duration": 0.8, "text": f"Halo semuanya! Selamat datang di VoxFlow AI Podcast."},
            {"speaker": "Richel", "emotion": "curious", "pause_duration": 0.5, "text": f"Halo! Kali ini kita bahas topik menarik: {research_text[:60]}..."},
            {"speaker": "Budi", "emotion": "neutral", "pause_duration": 0.8, "text": "Yuk kita mulai pembahasannya!"},
        ]

run_script_agent = run_scriptwriter_agent