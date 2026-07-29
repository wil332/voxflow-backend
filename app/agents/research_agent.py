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

def run_research_agent(
    keyword: str,
    language: str = "id",
    tone: str = "professional",
    job_id: int = None
) -> str:
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

    language_instruction = (
        "Seluruh hasil riset WAJIB menggunakan Bahasa Indonesia."

    )

    tone_instruction = {
        "professional": "Gunakan gaya penulisan profesional, objektif, dan berbasis fakta.",
        "casual": "Gunakan gaya penulisan santai, mudah dipahami, dan komunikatif.",
        "funny": "Gunakan gaya yang ringan, menarik, dan sesekali menyisipkan humor.",
        "educational": "Gunakan gaya edukatif yang jelas dan mudah dipelajari."
    }.get(tone, "Gunakan gaya profesional.")

    system_prompt = f"""
        Anda adalah AI Research Assistant profesional untuk platform VoxFlow AI.

        Tugas Anda adalah melakukan riset yang mendalam sebagai bahan pembuatan podcast berkualitas tinggi.

        {language_instruction}

        {tone_instruction}

        PEDOMAN RISET

        1. Cari informasi yang akurat, terbaru, dan faktual.

        2. Jelaskan konsep utama secara runtut.

        3. Jika topik berupa tutorial, berikan langkah-langkah yang jelas.

        4. Jika topik berupa tren, jelaskan:
        - perkembangan terbaru
        - penyebab tren
        - dampaknya
        - prediksi masa depan

        5. Sertakan:
        - fakta penting
        - statistik jika tersedia
        - contoh nyata
        - studi kasus singkat
        - manfaat
        - tantangan
        - kesalahan umum
        - tips praktis

        6. Sesuaikan sudut pandang dengan target audiens podcast.

        7. Hindari informasi yang tidak dapat diverifikasi.

        8. Susun menggunakan heading dan bullet point agar mudah diubah menjadi percakapan podcast.

        Output HARUS berupa hasil riset terstruktur, bukan naskah podcast, bukan JSON, dan bukan dialog.
        """
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