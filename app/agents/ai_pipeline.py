import time
import re
from app.agents.research_agent import run_research_agent
from app.agents.script_agent import run_script_agent
from app.agents.metadata_agent import run_metadata_agent
from app.agents.audio_agent import run_audio_generation_agent as run_audio_agent
from app.agents.tiktok_agent import publish_to_tiktok_webhook
from app.database.database import SessionLocal
from app.database.models import PodcastHistory


def update_agent_status(job_id: int, agent: str, status: str, progress: int):
    """Update status agent tertentu (dan progress global) di database."""
    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.progress = progress
            if item.agent_status is not None:
                updated = dict(item.agent_status)
                updated[agent] = status
                item.agent_status = updated
                db.commit()
                print(f"[STATUS] Job {job_id}: {agent} -> {status} ({progress}%)")
            else:
                print(f"[STATUS] WARNING: agent_status is None for job {job_id}")
    except Exception as e:
        print(f"[UPDATE STATUS ERROR] {e}")
        db.rollback()
    finally:
        db.close()


def update_tiktok_status(job_id: int, status: str, url: str = None, error: str = None, progress: int = None):
    """Update status publish TikTok secara terpisah dari agent_status['metadata']."""
    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.tiktok_status = status
            if url is not None:
                item.tiktok_url = url
            if error is not None:
                item.tiktok_error = error
            if progress is not None:
                item.progress = progress
            if item.agent_status is not None:
                updated = dict(item.agent_status)
                updated["tiktok"] = status
                item.agent_status = updated
            db.commit()
            print(f"[TIKTOK STATUS] Job {job_id}: tiktok -> {status}")
    except Exception as e:
        print(f"[UPDATE TIKTOK STATUS ERROR] {e}")
        db.rollback()
    finally:
        db.close()


def _save_output_files(job_id: int, merged_audio_filename: str = None, video_filename: str = None):
    """Simpan nama file hasil merge/render ke row job."""
    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            if merged_audio_filename:
                item.merged_audio_filename = merged_audio_filename
            if video_filename:
                item.video_filename = video_filename
            db.commit()
    except Exception as e:
        print(f"[SAVE OUTPUT FILES ERROR] {e}")
        db.rollback()
    finally:
        db.close()


def _auto_publish_to_tiktok(job_id: int, keyword: str, audio_segments: list, metadata: dict):
    """Auto merge audio → render video → upload TikTok"""
    print(f"[DEBUG AUTO-PUBLISH] 🔄 Starting auto-publish for job {job_id}")

    if not audio_segments or len(audio_segments) == 0:
        print("[DEBUG AUTO-PUBLISH] ❌ No audio segments to process")
        return

    try:
        from app.utils.audio_merger import merge_podcast_segments
        from app.utils.video_generator import create_tiktok_video_with_subtitles
        from app.agents.tiktok_agent import publish_to_tiktok_webhook
        import re

        print(f"[DEBUG AUTO-PUBLISH] 📊 Audio segments count: {len(audio_segments)}")

        # ============================================================
        # 1. MERGE AUDIO
        # ============================================================
        print(f"[DEBUG AUTO-PUBLISH] 🎵 Step 1: Merging audio...")

        clean_keyword = re.sub(r'[\\/*?:"<>|]', '', keyword or "podcast")
        clean_keyword = clean_keyword.replace(' ', '_')[:50]
        merged_filename = f"podcast_{clean_keyword}_{job_id}.mp3"

        merged_audio = merge_podcast_segments(audio_segments, merged_filename, cleanup_segments=False)
        print(f"[DEBUG AUTO-PUBLISH] ✅ Audio merged: {merged_audio}")

        # Update database
        db = SessionLocal()
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.merged_audio_filename = merged_audio
            db.commit()
            print(f"[DEBUG AUTO-PUBLISH] ✅ Database updated with merged audio")
        db.close()

        # ============================================================
        # 2. RENDER VIDEO
        # ============================================================
        print(f"[DEBUG AUTO-PUBLISH] 🎬 Step 2: Rendering video...")
        video_filename = create_tiktok_video_with_subtitles(merged_audio, metadata or {})

        if video_filename:
            print(f"[DEBUG AUTO-PUBLISH] ✅ Video rendered: {video_filename}")
            db = SessionLocal()
            item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
            if item:
                item.video_filename = video_filename
                db.commit()
                print(f"[DEBUG AUTO-PUBLISH] ✅ Database updated with video filename")
            db.close()
        else:
            print(f"[DEBUG AUTO-PUBLISH] ❌ Video render failed")
            return

        # ============================================================
        # 3. UPLOAD TIKTOK
        # ============================================================
        print(f"[DEBUG AUTO-PUBLISH] 📱 Step 3: Uploading to TikTok...")
        result = publish_to_tiktok_webhook(video_filename, metadata or {})

        db = SessionLocal()
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.tiktok_status = result.get("status", "failed")
            if result.get("status") in ["success", "test_success"]:
                item.tiktok_url = result.get("data", {}).get("url") or "Uploaded"
            else:
                item.tiktok_error = result.get("error", "Unknown error")
            db.commit()
        db.close()

        print(f"[DEBUG AUTO-PUBLISH] ✅ TikTok upload result: {result.get('status')}")

    except Exception as e:
        print(f"[DEBUG AUTO-PUBLISH] ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def run_ai_pipeline(
    keyword: str,
    job_id: int = None,
    language: str = "indonesian",
    tone: str = "professional",
    voice: str = "mixed",
):
    print(f"\n{'='*60}")
    print(f"[DEBUG PIPELINE] 🚀 STARTING PIPELINE")
    print(f"[DEBUG PIPELINE] Keyword: {keyword}")
    print(f"[DEBUG PIPELINE] Job ID: {job_id}")
    print(f"[DEBUG PIPELINE] Language: {language}, Tone: {tone}, Voice: {voice}")
    print(f"{'='*60}\n")

    # === UPDATE STATUS: Research Running ===
    if job_id:
        update_agent_status(job_id, "research", "running", 10)

    # ============================================================
    # 1. RESEARCH AGENT (Qwen)
    # ============================================================
    print(f"[DEBUG PIPELINE] 📚 Step 1/4: Research Agent starting...")
    start_time = time.time()
    try:
        research_result = run_research_agent(keyword, job_id)
        print(f"[DEBUG PIPELINE] ✅ Research completed in {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Research result length: {len(str(research_result))}")
    except Exception as e:
        print(f"[DEBUG PIPELINE] ❌ Research failed after {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Error: {e}")
        traceback.print_exc()
        if job_id:
            update_agent_status(job_id, "research", "failed", 0)
        raise

    # === UPDATE STATUS: Research Done, Script Running ===
    if job_id:
        update_agent_status(job_id, "research", "done", 30)
        update_agent_status(job_id, "script", "running", 35)

    # ============================================================
    # 2. SCRIPT AGENT (Agnes)
    # ============================================================
    print(f"[DEBUG PIPELINE] 📝 Step 2/4: Script Agent starting...")
    start_time = time.time()
    try:
        script_result = run_script_agent(research_result, language=language, tone=tone)
        print(f"[DEBUG PIPELINE] ✅ Script completed in {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Script segments: {len(script_result)}")
    except Exception as e:
        print(f"[DEBUG PIPELINE] ❌ Script failed after {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Error: {e}")
        traceback.print_exc()
        if job_id:
            update_agent_status(job_id, "script", "failed", 0)
        raise

    # === UPDATE STATUS: Script Done, Audio Running ===
    if job_id:
        update_agent_status(job_id, "script", "done", 50)
        update_agent_status(job_id, "audio", "running", 55)

    # ============================================================
    # 3. AUDIO AGENT (ElevenLabs)
    # ============================================================
    print(f"[DEBUG PIPELINE] 🎵 Step 3/4: Audio Agent starting...")
    start_time = time.time()
    try:
        audio_segments = run_audio_agent(script_result, voice=voice)
        print(f"[DEBUG PIPELINE] ✅ Audio completed in {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Audio segments: {len(audio_segments)}")
    except Exception as e:
        print(f"[DEBUG PIPELINE] ❌ Audio failed after {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Error: {e}")
        traceback.print_exc()
        if job_id:
            update_agent_status(job_id, "audio", "failed", 0)
        raise

    # === UPDATE STATUS: Audio Done, Metadata Running ===
    if job_id:
        update_agent_status(job_id, "audio", "done", 80)
        update_agent_status(job_id, "metadata", "running", 85)

    # ============================================================
    # 4. METADATA AGENT (Qwen)
    # ============================================================
    print(f"[DEBUG PIPELINE] 🏷️ Step 4/4: Metadata Agent starting...")
    start_time = time.time()
    try:
        metadata_result = run_metadata_agent(keyword, research_result)
        print(f"[DEBUG PIPELINE] ✅ Metadata completed in {time.time() - start_time:.2f}s")
    except Exception as e:
        print(f"[DEBUG PIPELINE] ❌ Metadata failed after {time.time() - start_time:.2f}s")
        print(f"[DEBUG PIPELINE] Error: {e}")
        traceback.print_exc()
        if job_id:
            update_agent_status(job_id, "metadata", "failed", 0)
        raise

    # === UPDATE STATUS: Metadata Done ===
    if job_id:
        update_agent_status(job_id, "metadata", "done", 90)

    print(f"\n{'='*60}")
    print(f"[DEBUG PIPELINE] ✅ PIPELINE COMPLETED!")
    print(f"[DEBUG PIPELINE] Total time: {time.time() - start_time:.2f}s")
    print(f"{'='*60}\n")

    # ============================================================
    # AUTO-PUBLISH (Merge Audio → Render Video → TikTok)
    # ============================================================
    if job_id:
        print(f"[DEBUG PIPELINE] 📤 Starting auto-publish...")
        _auto_publish_to_tiktok(job_id, keyword, audio_segments, metadata_result)

    return research_result, script_result, metadata_result, audio_segments