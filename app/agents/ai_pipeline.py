from app.agents.research_agent import run_research_agent
from app.agents.script_agent import run_script_agent
from app.agents.metadata_agent import run_metadata_agent
from app.agents.audio_agent import run_audio_generation_agent as run_audio_agent
from app.database.database import SessionLocal
from app.database.models import PodcastHistory

def update_agent_status(job_id: int, agent: str, status: str, progress: int):
    """Update status agent di database"""
    try:
        db = SessionLocal()
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.progress = progress
            if item.agent_status:
                # Update status agent tertentu
                item.agent_status[agent] = status
                db.commit()
                print(f"[STATUS] Job {job_id}: {agent} → {status} ({progress}%)")
            else:
                print(f"[STATUS] WARNING: agent_status is None for job {job_id}")
        db.close()
    except Exception as e:
        print(f"[UPDATE STATUS ERROR] {e}")

def run_ai_pipeline(keyword: str, job_id: int = None):
    print(f"[PIPELINE] Memulai pipeline untuk keyword: {keyword}")

    # === UPDATE STATUS: Research Running ===
    if job_id:
        update_agent_status(job_id, "research", "running", 10)

    # 1. Research Agent (Qwen)
    try:
        research_result = run_research_agent(keyword, job_id)
        print(f"[PIPELINE] Research completed, length: {len(str(research_result))}")
    except Exception as e:
        print(f"[PIPELINE] Research failed: {e}")
        if job_id:
            update_agent_status(job_id, "research", "failed", 0)
        raise

    # === UPDATE STATUS: Research Done, Script Running ===
    if job_id:
        update_agent_status(job_id, "research", "done", 30)
        update_agent_status(job_id, "script", "running", 35)

    # 2. Script Agent (Agnes)
    try:
        script_result = run_script_agent(research_result)
        print(f"[PIPELINE] Script completed, {len(script_result)} segments")
    except Exception as e:
        print(f"[PIPELINE] Script failed: {e}")
        if job_id:
            update_agent_status(job_id, "script", "failed", 0)
        raise

    # === UPDATE STATUS: Script Done, Audio Running ===
    if job_id:
        update_agent_status(job_id, "script", "done", 50)
        update_agent_status(job_id, "audio", "running", 55)

    # 3. Audio Agent (ElevenLabs)
    try:
        audio_segments = run_audio_agent(script_result)
        print(f"[PIPELINE] Audio completed, {len(audio_segments)} segments")
    except Exception as e:
        print(f"[PIPELINE] Audio failed: {e}")
        if job_id:
            update_agent_status(job_id, "audio", "failed", 0)
        raise

    # === UPDATE STATUS: Audio Done, Metadata Running ===
    if job_id:
        update_agent_status(job_id, "audio", "done", 80)
        update_agent_status(job_id, "metadata", "running", 85)

    # 4. Metadata Agent (Qwen)
    try:
        metadata_result = run_metadata_agent(keyword, research_result)
        print(f"[PIPELINE] Metadata completed")
    except Exception as e:
        print(f"[PIPELINE] Metadata failed: {e}")
        if job_id:
            update_agent_status(job_id, "metadata", "failed", 0)
        raise

    # === UPDATE STATUS: All Done ===
    if job_id:
        update_agent_status(job_id, "metadata", "done", 100)

    print(f"[PIPELINE SUCCESS] Pipeline selesai untuk keyword: {keyword}")
    return research_result, script_result, metadata_result, audio_segments