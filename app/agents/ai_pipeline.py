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


def _auto_publish_to_tiktok(job_id: int, keyword: str, audio_segments: list, metadata_result: dict):
    """
    Tahap otomatis setelah pipeline utama (research/script/audio/metadata) selesai:
    1. Merge semua segmen audio jadi satu file MP3
    2. Render video TikTok (MP4 + subtitle) dari audio yang sudah digabung
    3. Upload/publish video tersebut ke TikTok lewat webhook

    Kalau ada satu step gagal, status tiktok di-set "failed" dengan pesan error,
    tapi TIDAK melempar exception ke atas -- kegagalan di tahap ini tidak boleh
    membuat status pipeline utama ("research/script/audio/metadata") ikut jadi
    "failed", karena konten podcast intinya sudah berhasil dibuat.
    """
    from app.utils.audio_merger import merge_podcast_segments
    from app.utils.video_generator import create_tiktok_video_with_subtitles

    update_tiktok_status(job_id, "uploading", progress=92)

    try:
        clean_keyword = re.sub(r'[\\/*?:"<>|]', '', keyword or "podcast")
        clean_keyword = clean_keyword.replace(' ', '_')[:50]
        merged_filename = f"podcast_{clean_keyword}_{job_id}.mp3"

        print(f"[AUTO PUBLISH] Merging audio for job {job_id}...")
        merged_audio_filename = merge_podcast_segments(
            audio_segments, merged_filename, cleanup_segments=False
        )
        _save_output_files(job_id, merged_audio_filename=merged_audio_filename)
        update_tiktok_status(job_id, "uploading", progress=95)

        print(f"[AUTO PUBLISH] Rendering video for job {job_id}...")
        video_filename = create_tiktok_video_with_subtitles(merged_audio_filename, metadata_result or {})
        if not video_filename:
            raise RuntimeError("Gagal merender video (create_tiktok_video_with_subtitles mengembalikan kosong)")
        _save_output_files(job_id, video_filename=video_filename)
        update_tiktok_status(job_id, "uploading", progress=98)

        print(f"[AUTO PUBLISH] Uploading to TikTok for job {job_id}...")
        result = publish_to_tiktok_webhook(video_filename, metadata_result or {})

        if result.get("status") == "success":
            tiktok_url = None
            data = result.get("data") or {}
            if isinstance(data, dict):
                tiktok_url = data.get("video_url") or data.get("url") or data.get("share_url")
            update_tiktok_status(job_id, "success", url=tiktok_url, progress=100)
            print(f"[AUTO PUBLISH] ✅ Job {job_id} published to TikTok")
        else:
            update_tiktok_status(job_id, "failed", error=result.get("error", "Unknown error"), progress=100)
            print(f"[AUTO PUBLISH] ❌ Job {job_id} failed to publish: {result.get('error')}")

    except Exception as e:
        print(f"[AUTO PUBLISH ERROR] Job {job_id}: {e}")
        update_tiktok_status(job_id, "failed", error=str(e), progress=100)


def run_ai_pipeline(
    keyword: str,
    job_id: int = None,
    language: str = "indonesian",
    tone: str = "professional",
    voice: str = "mixed",
):
    print(f"[PIPELINE] Memulai pipeline untuk keyword: {keyword} (language={language}, tone={tone}, voice={voice})")

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
        script_result = run_script_agent(research_result, language=language, tone=tone)
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
        audio_segments = run_audio_agent(script_result, voice=voice)
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

    # === UPDATE STATUS: Metadata Done ===
    if job_id:
        update_agent_status(job_id, "metadata", "done", 90)

    print(f"[PIPELINE SUCCESS] Pipeline utama selesai untuk keyword: {keyword}")

    # === TAHAP OTOMATIS BARU: Merge Audio -> Render Video -> Upload TikTok ===
    # Dijalankan otomatis di sini supaya user tidak perlu klik "Merge Audio"
    # dan "Render Video" manual lagi. Kegagalan di tahap ini tidak melempar
    # exception ke atas -- podcast intinya (audio segments) sudah berhasil dibuat.
    if job_id:
        _auto_publish_to_tiktok(job_id, keyword, audio_segments, metadata_result)

    return research_result, script_result, metadata_result, audio_segments