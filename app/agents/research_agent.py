import time
import requests
from app.config import settings

def run_research_agent(keyword: str, language: str = "indonesian") -> str:
    print(f"[RESEARCH] Keyword: {keyword}, Language: {language}")

    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    # === SYSTEM PROMPT BERDASARKAN BAHASA ===
    prompts = {
        "indonesian": (
            "Anda adalah AI Research Assistant untuk VoxFlow AI.\n"
            "TUGAS: Lakukan riset mendalam tentang topik yang diberikan.\n"
            "WAJIB: Gunakan BAHASA INDONESIA untuk semua output.\n"
            "Sajikan hasil riset secara ringkas, padat, dan terstruktur."
        ),
        "english": (
            "You are an AI Research Assistant for VoxFlow AI.\n"
            "TASK: Conduct in-depth research on the given topic.\n"
            "MUST: Use ENGLISH for all output.\n"
            "Present research results concisely and structured."
        ),
        "sunda": (
            "Anjeun asisten panaliti AI pikeun VoxFlow AI.\n"
            "TUGAS: Laksanakeun panaliti anu jero ngeunaan topik anu dipasihkeun.\n"
            "WAJIB: Anggo BASA SUNDA pikeun sadaya kaluaran.\n"
            "Kintunkeun hasil panaliti sacara ringkes sareng terstruktur."
        ),
        "jawa": (
            "Sampeyan asisten peneliti AI kanggo VoxFlow AI.\n"
            "TUGAS: Nindakake riset jero babagan topik sing diwenehake.\n"
            "WAJIB: Gunakake BASA JAWA kanggo kabeh output.\n"
            "Aturaken asil riset kanthi ringkes lan terstruktur."
        )
    }

    system_prompt = prompts.get(language, prompts["indonesian"])

    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "qwen-max",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Lakukan riset mendalam terkait topik/keyword: {keyword}"}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=70)
        if response.status_code != 200:
            return f"Gagal dari server Qwen (Status {response.status_code})"
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"