# app/agents/ai_pipeline.py

from app.agents.research_agent import run_research_agent
from app.agents.script_agent import run_script_agent
from app.agents.metadata_agent import run_metadata_agent
from app.agents.audio_agent import run_audio_generation_agent as run_audio_agent
from app.database.database import SessionLocal
from app.database.models import PodcastHistory

def update_agent_status(job_id: int, agent: str, status: str, progress: int):
    try:
        db = SessionLocal()
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item and item.agent_status:
            item.agent_status[agent] = status
            item.progress = progress
            db.commit()
        db.close()
    except Exception as e:
        print(f"[STATUS ERROR] {e}")

def run_ai_pipeline(
    keyword: str,
    job_id: int = None,
    language: str = "indonesian",
    tone: str = "professional",
    voice: str = "mixed",
    duration: str = "5-10",
    platforms: list = []
):
    print(f"[PIPELINE] Memulai pipeline: keyword={keyword}, language={language}, tone={tone}")

    # === 1. RESEARCH ===
    if job_id:
        update_agent_status(job_id, "research", "running", 10)
    research_result = run_research_agent(keyword, language=language)

    # === 2. SCRIPT ===
    if job_id:
        update_agent_status(job_id, "research", "done", 30)
        update_agent_status(job_id, "script", "running", 35)
    script_result = run_script_agent(research_result, language=language, tone=tone)

    # === 3. METADATA ===
    if job_id:
        update_agent_status(job_id, "script", "done", 50)
        update_agent_status(job_id, "metadata", "running", 55)
    metadata_result = run_metadata_agent(keyword, research_result, language=language)

    # === 4. AUDIO ===
    if job_id:
        update_agent_status(job_id, "metadata", "done", 70)
        update_agent_status(job_id, "audio", "running", 75)
    audio_segments = run_audio_agent(script_result, voice=voice)

    # === 5. TIKTOK (pending) ===
    if job_id:
        update_agent_status(job_id, "audio", "done", 95)
        update_agent_status(job_id, "tiktok", "pending", 98)

    print(f"[PIPELINE SUCCESS] Selesai untuk keyword: {keyword}")
    return research_result, script_result, metadata_result, audio_segments