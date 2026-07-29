import requests
from app.config import settings
from app.database.database import SessionLocal
from app.database.models import PodcastHistory

def update_research_status(job_id: int, status: str, progress: int):
    """Update status research agent di database"""
    try:
        db = SessionLocal()
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.progress = progress
            if item.agent_status:
                item.agent_status["research"] = status
                db.commit()
                print(f"[RESEARCH] Job {job_id}: {status} at {progress}%")
        db.close()
    except Exception as e:
        print(f"[RESEARCH STATUS ERROR] {e}")

def run_research_agent(keyword: str, job_id: int = None) -> str:
    """
    Agent 1: Research Agent menggunakan Qwen API.
    job_id: untuk update progress ke database
    """
    print(f"[RESEARCH] Starting research for keyword: {keyword}")

    # === UPDATE PROGRESS: Research Started ===
    if job_id:
        update_research_status(job_id, "running", 20)

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
        # === UPDATE PROGRESS: Calling API ===
        if job_id:
            update_research_status(job_id, "running", 40)

        print(f"[RESEARCH] Calling Qwen API...")
        response = requests.post(url, headers=headers, json=payload, timeout=70)

        # === UPDATE PROGRESS: API Response Received ===
        if job_id:
            update_research_status(job_id, "running", 60)

        if response.status_code != 200:
            print(f"[RESEARCH] Error: Status {response.status_code}")
            if job_id:
                update_research_status(job_id, "failed", 0)
            return f"Gagal dari server Qwen (Status {response.status_code}): {response.text}"

        data = response.json()
        result = data['choices'][0]['message']['content']

        print(f"[RESEARCH] Success, response length: {len(result)}")

        # === UPDATE PROGRESS: Research Complete ===
        if job_id:
            update_research_status(job_id, "done", 100)

        return result

    except requests.exceptions.RequestException as e:
        print(f"[RESEARCH] Connection error: {e}")
        if job_id:
            update_research_status(job_id, "failed", 0)
        return f"Error koneksi ke Qwen API: {str(e)}"
    except Exception as e:
        print(f"[RESEARCH] Error: {e}")
        if job_id:
            update_research_status(job_id, "failed", 0)
        return f"Error: {str(e)}"