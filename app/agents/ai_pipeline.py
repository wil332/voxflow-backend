from app.agents.research_agent import run_research_agent
from app.agents.script_agent import run_script_agent
from app.agents.metadata_agent import run_metadata_agent
from app.agents.audio_agent import run_audio_generation_agent as run_audio_agent
from app.database.database import SessionLocal
from app.database.models import PodcastHistory

def run_ai_pipeline(keyword: str, job_id: int = None):
    print(f"[PIPELINE] Memulai pipeline untuk keyword: {keyword}")

    # === UPDATE STATUS: Research Running ===
    if job_id:
        update_agent_status(job_id, "research", "running", 10)

    # === PANGGIL RESEARCH AGENT DENGAN JOB_ID ===
    research_result = run_research_agent(keyword, job_id)  # <-- Kirim job_id

    # === UPDATE STATUS: Research Done, Script Running ===
    if job_id:
        update_agent_status(job_id, "research", "done", 30)
        update_agent_status(job_id, "script", "running", 35)

    script_result = run_script_agent(research_result)

    # === UPDATE STATUS: Script Done, Audio Running ===
    if job_id:
        update_agent_status(job_id, "script", "done", 50)
        update_agent_status(job_id, "audio", "running", 55)

    audio_segments = run_audio_agent(script_result)

    # === UPDATE STATUS: Audio Done, Metadata Running ===
    if job_id:
        update_agent_status(job_id, "audio", "done", 80)
        update_agent_status(job_id, "metadata", "running", 85)

    metadata_result = run_metadata_agent(keyword, research_result)

    # === UPDATE STATUS: All Done ===
    if job_id:
        update_agent_status(job_id, "metadata", "done", 100)

    print(f"[PIPELINE SUCCESS] Pipeline selesai untuk keyword: {keyword}")
    return research_result, script_result, metadata_result, audio_segments

def update_agent_status(job_id: int, agent: str, status: str, progress: int):
    """Update status agent di database"""
    try:
        db = SessionLocal()
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.progress = progress
            if item.agent_status:
                item.agent_status[agent] = status
            db.commit()
            print(f"[STATUS] Job {job_id}: {agent} → {status} ({progress}%)")
        db.close()
    except Exception as e:
        print(f"[UPDATE STATUS ERROR] {e}")