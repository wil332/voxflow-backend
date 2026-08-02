import re
from app.celery_app import celery_app
from app.database.database import SessionLocal
from app.database.models import PodcastHistory


@celery_app.task(name="tasks.run_podcast_pipeline", bind=True, max_retries=0)
def run_podcast_pipeline_task(
    self,
    job_id: int,
    keyword: str,
    language: str = "indonesian",
    tone: str = "professional",
    voice: str = "mixed",
):
    """
    Pipeline utama: research -> script -> audio -> metadata, lalu otomatis
    lanjut merge audio -> render video -> publish TikTok (lihat
    ai_pipeline.py::_auto_publish_to_tiktok yang sudah dipanggil di dalam
    run_ai_pipeline itu sendiri).
    """
    from app.agents.ai_pipeline import run_ai_pipeline

    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.status = "processing"
            item.progress = 5
            item.agent_status = {
                "research": "pending",
                "script": "pending",
                "audio": "pending",
                "metadata": "pending",
                "tiktok": "pending",
            }
            db.commit()
        print(f"[TASK] Job {job_id} initialized, mulai pipeline...")

        research_data, script_json, metadata, audio_segments = run_ai_pipeline(
            keyword, job_id, language=language, tone=tone, voice=voice
        )

        # Refresh supaya dapat agent_status/tiktok_status TERBARU yang sudah
        # di-commit oleh session lain di dalam run_ai_pipeline (termasuk
        # hasil auto-publish TikTok).
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            db.refresh(item)
            item.research_summary = str(research_data)
            item.metadata_json = metadata
            item.audio_segments = audio_segments
            item.status = "completed"
            item.progress = 100

            merged_agent_status = dict(item.agent_status or {})
            merged_agent_status.update({
                "research": "done",
                "script": "done",
                "audio": "done",
                "metadata": "done",
            })
            item.agent_status = merged_agent_status

            db.commit()
            print(f"[TASK] Job {job_id} completed.")

        return {"job_id": job_id, "status": "completed"}

    except Exception as e:
        print(f"[TASK ERROR] Job {job_id}: {e}")
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.status = "failed"
            item.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()


@celery_app.task(name="tasks.merge_audio_task", bind=True)
def merge_audio_task(self, job_id: int):
    """Merge audio manual/retry -- dijalankan di background worker, tidak blocking request."""
    from app.utils.audio_merger import merge_podcast_segments

    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if not item:
            raise ValueError("Podcast tidak ditemukan.")
        if not item.audio_segments:
            raise ValueError("Belum ada segmen audio.")

        clean_keyword = re.sub(r'[\\/*?:"<>|]', '', item.keyword or "podcast")
        clean_keyword = clean_keyword.replace(' ', '_')[:50]
        merged_filename = f"podcast_{clean_keyword}_{job_id}.mp3"

        merged_audio_filename = merge_podcast_segments(
            item.audio_segments, merged_filename, cleanup_segments=False
        )
        if not merged_audio_filename:
            raise ValueError("Gagal menggabungkan audio.")

        item.merged_audio_filename = merged_audio_filename
        db.commit()
        print(f"[TASK] Merge audio job {job_id} selesai: {merged_audio_filename}")
        return {"merged_audio_filename": merged_audio_filename}

    except Exception as e:
        print(f"[TASK ERROR] Merge audio job {job_id}: {e}")
        raise

    finally:
        db.close()


@celery_app.task(name="tasks.generate_video_task", bind=True)
def generate_video_task(self, job_id: int):
    """Render video manual/retry -- dijalankan di background worker, tidak blocking request."""
    from app.utils.video_generator import create_tiktok_video_with_subtitles

    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if not item:
            raise ValueError("Podcast tidak ditemukan.")
        if not item.merged_audio_filename:
            raise ValueError("Audio belum di-merge. Merge audio dulu.")

        metadata = item.metadata_json or {}
        video_filename = create_tiktok_video_with_subtitles(item.merged_audio_filename, metadata)
        if not video_filename:
            raise ValueError("Gagal merender video.")

        item.video_filename = video_filename
        db.commit()
        print(f"[TASK] Render video job {job_id} selesai: {video_filename}")
        return {"video_filename": video_filename}

    except Exception as e:
        print(f"[TASK ERROR] Render video job {job_id}: {e}")
        raise

    finally:
        db.close()


@celery_app.task(name="tasks.publish_tiktok_task", bind=True)
def publish_tiktok_task(self, job_id: int):
    """Publish/retry publish TikTok manual -- dijalankan di background worker."""
    from app.agents.tiktok_agent import publish_to_tiktok_webhook

    db = SessionLocal()
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if not item:
            raise ValueError("Podcast tidak ditemukan.")
        if not item.video_filename:
            raise ValueError("Video belum tersedia. Render video dulu sebelum publish.")

        item.tiktok_status = "uploading"
        db.commit()

        metadata = item.metadata_json or {}
        result = publish_to_tiktok_webhook(item.video_filename, metadata)

        if result.get("status") == "success":
            data = result.get("data") or {}
            tiktok_url = (
                data.get("video_url") or data.get("url") or data.get("share_url")
                if isinstance(data, dict) else None
            )
            item.tiktok_status = "success"
            item.tiktok_url = tiktok_url
            item.tiktok_error = None
        else:
            item.tiktok_status = "failed"
            item.tiktok_error = result.get("error", "Unknown error")

        if item.agent_status is not None:
            updated = dict(item.agent_status)
            updated["tiktok"] = item.tiktok_status
            item.agent_status = updated

        db.commit()
        print(f"[TASK] Publish TikTok job {job_id}: {item.tiktok_status}")
        return {"tiktok_status": item.tiktok_status, "tiktok_url": item.tiktok_url}

    except Exception as e:
        print(f"[TASK ERROR] Publish TikTok job {job_id}: {e}")
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if item:
            item.tiktok_status = "failed"
            item.tiktok_error = str(e)
            db.commit()
        raise

    finally:
        db.close()
