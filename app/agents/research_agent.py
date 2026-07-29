import requests
from app.config import settings

def run_research_agent(keyword: str) -> str:
    """
    Agent 1: Research Agent menggunakan Qwen API untuk mengumpulkan riset mendalam
    berdasarkan keyword utama (P0) dan kebutuhan SEO.
    """
    url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "Anda adalah AI Research Assistant untuk proyek VoxFlow AI.\n"
        "PANDUAN RISET KEYWORD & SEO HACKATHON:\n"
        "1. Educational Focus (Informational Intent): Jika keyword berfokus pada informasi/edukasi "
        "(seperti 'podcast AI' atau 'podcast automation'), sajikan materi edukatif yang mendalam, tren terbaru, dan konsep dasarnya.\n"
        "2. Tutorial & Guide Focus (Transactional/Commercial Intent): Jika keyword berfokus pada cara/solusi "
        "(seperti 'cara buat podcast otomatis dengan AI' atau 'AI podcast generator'), sajikan langkah-langkah praktis, panduan langkah demi langkah, dan perbandingannya.\n"
        "3. Market Localization: Wajib menyesuaikan topik, konteks, dan sudut pandang riset agar sangat relevan dengan pasar dan audiens Indonesia.\n"
        "4. Competitive Advantage: Tekankan selalu peran 'End-to-End Automation' sebagai solusi efisiensi utama.\n\n"
        "Sajikan hasil riset secara ringkas, padat, dan terstruktur agar mudah diolah menjadi naskah podcast."
    )

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
            print(f"[RESEARCH AGENT ERROR] Status: {response.status_code}, Body: {response.text}")
            return f"Gagal dari server Qwen (Status {response.status_code}): {response.text}"

        data = response.json()
        return data['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        print(f"[RESEARCH AGENT EXCEPTION] Error koneksi: {e}")
        return f"Error koneksi ke Qwen API: {str(e)}"
    except (ValueError, KeyError) as e:
        print(f"[RESEARCH AGENT EXCEPTION] Error parsing: {e}")
        return f"Format respons Qwen tidak valid. Respons mentah: {response.text}"