import os
import re
import logging
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import static_ffmpeg
from datetime import datetime

from app.config import settings
from app.agents.ai_pipeline import run_ai_pipeline
from app.middlewares.error_handler import setup_exception_handlers
from app.database.database import engine, Base, get_db
from app.database.models import PodcastHistory
from app.agents.tiktok_agent import publish_to_tiktok_webhook
from app.utils.audio_merger import merge_podcast_segments
from app.utils.video_generator import create_tiktok_video_with_subtitles

# ============================================================
# SETUP
# ============================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

static_ffmpeg.add_paths()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API server untuk otomatisasi platform podcast otonom.",
    version=settings.VERSION
)

# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_exception_handlers(app)

# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/")
def read_root():
    return {"status": "success", "message": "PodFlow AI Backend is running and ready!"}

# ============================================================
# GENERATE PODCAST (ASYNC + PARAMETER LENGKAP)
# ============================================================
@app.post("/api/v1/podcast/generate")
def trigger_podcast_generation(
    keyword: str,
    language: str = "indonesian",
    tone: str = "professional",
    voice: str = "mixed",
    duration: str = "5-10",
    platforms: list[str] = [],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Generate: keyword={keyword}, language={language}, tone={tone}, voice={voice}")

        # === CEK API KEYS ===
        if not settings.QWEN_API_KEY:
            return JSONResponse(500, {"status": "error", "message": "QWEN_API_KEY not configured"})
        if not settings.AGNES_API_KEY:
            return JSONResponse(500, {"status": "error", "message": "AGNES_API_KEY not configured"})
        if not settings.ELEVENLABS_API_KEY:
            return JSONResponse(500, {"status": "error", "message": "ELEVENLABS_API_KEY not configured"})

        # === BUAT DATABASE ENTRY ===
        db_item = PodcastHistory(
            keyword=keyword,
            status="processing",
            progress=0,
            agent_status={
                "research": "pending",
                "script": "pending",
                "audio": "pending",
                "metadata": "pending",
                "tiktok": "pending"
            },
            language=language,
            tone=tone,
            voice=voice,
            duration=duration,
            platforms=platforms
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        logger.info(f"Created job {db_item.id} for keyword: {keyword}")

        # ============================================================
        # BACKGROUND TASK
        # ============================================================
        def run_pipeline():
            try:
                from app.database.database import SessionLocal
                bg_db = SessionLocal()
                try:
                    item = bg_db.query(PodcastHistory).filter(PodcastHistory.id == db_item.id).first()
                    if not item:
                        return

                    item.status = "processing"
                    item.progress = 5
                    item.agent_status = {
                        "research": "running",
                        "script": "pending",
                        "audio": "pending",
                        "metadata": "pending",
                        "tiktok": "pending"
                    }
                    bg_db.commit()

                    # === JALANKAN PIPELINE DENGAN PARAMETER ===
                    research_data, script_json, metadata, audio_segments = run_ai_pipeline(
                        keyword=keyword,
                        job_id=db_item.id,
                        language=language,
                        tone=tone,
                        voice=voice,
                        duration=duration,
                        platforms=platforms
                    )

                    # === UPDATE HASIL ===
                    item.research_summary = str(research_data)
                    item.metadata_json = metadata
                    item.audio_segments = audio_segments
                    item.status = "completed"
                    item.progress = 100
                    item.agent_status = {
                        "research": "done",
                        "script": "done",
                        "audio": "done",
                        "metadata": "done",
                        "tiktok": "pending"
                    }
                    bg_db.commit()
                    logger.info(f"Pipeline completed for job {db_item.id}")

                    # === AUTO-UPLOAD TIKTOK (jika video sudah ada) ===
                    if item.video_filename:
                        try:
                            result = publish_to_tiktok_webhook(item.video_filename, metadata)
                            if result.get("status") in ["success", "test_success"]:
                                item.tiktok_status = "success"
                                item.tiktok_url = result.get("data", {}).get("url") or "Uploaded"
                            else:
                                item.tiktok_status = "failed"
                                item.tiktok_error = result.get("error", "Unknown error")
                            bg_db.commit()
                        except Exception as e:
                            item.tiktok_status = "failed"
                            item.tiktok_error = str(e)
                            bg_db.commit()

                except Exception as e:
                    logger.error(f"Pipeline error: {e}")
                    if bg_db:
                        item = bg_db.query(PodcastHistory).filter(PodcastHistory.id == db_item.id).first()
                        if item:
                            item.status = "failed"
                            item.error_message = str(e)
                            bg_db.commit()
                finally:
                    bg_db.close()
            except Exception as e:
                logger.error(f"Background task error: {e}")

        background_tasks.add_task(run_pipeline)

        return {
            "job_id": db_item.id,
            "status": "processing",
            "message": "Pipeline started"
        }

    except Exception as e:
        logger.error(f"Generate error: {e}")
        return JSONResponse(500, {"status": "error", "message": str(e)})

# ============================================================
# STATUS ENDPOINT
# ============================================================
@app.get("/api/v1/podcast/status/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
    if not item:
        return JSONResponse(404, {"status": "not_found", "message": "Job tidak ditemukan"})

    response = {
        "id": item.id,
        "keyword": item.keyword,
        "status": item.status,
        "progress": item.progress,
        "agent_status": item.agent_status,
        "error_message": item.error_message,
        "tiktok_status": getattr(item, "tiktok_status", None),
        "tiktok_url": getattr(item, "tiktok_url", None),
        "tiktok_error": getattr(item, "tiktok_error", None),
    }

    if item.status == "completed":
        if item.merged_audio_filename:
            response["audio_url"] = f"/api/v1/podcast/download/{item.merged_audio_filename}"
        if item.video_filename:
            response["video_url"] = f"/api/v1/podcast/video/{item.video_filename}"
        if item.metadata_json:
            response["metadata"] = item.metadata_json

    return response

# ============================================================
# HISTORY
# ============================================================
@app.get("/api/v1/podcast/history")
def get_podcast_history(db: Session = Depends(get_db)):
    history = db.query(PodcastHistory).all()
    return {"status": "success", "total": len(history), "data": history}

# ============================================================
# MERGE AUDIO
# ============================================================
@app.post("/api/v1/podcast/merge-audio/{database_id}")
def merge_podcast_audio(database_id: int, db: Session = Depends(get_db)):
    db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
    if not db_item:
        raise HTTPException(404, "Podcast tidak ditemukan.")
    if not db_item.audio_segments:
        raise HTTPException(400, "Belum ada segmen audio.")

    clean_keyword = re.sub(r'[\\/*?:"<>|]', '', db_item.keyword or "podcast")
    clean_keyword = clean_keyword.replace(' ', '_')[:50]
    merged_filename = f"podcast_{clean_keyword}_{database_id}.mp3"

    merged_audio_filename = merge_podcast_segments(db_item.audio_segments, merged_filename, cleanup_segments=False)

    db_item.merged_audio_filename = merged_audio_filename
    db.commit()
    db.refresh(db_item)

    return {
        "status": "completed",
        "database_id": db_item.id,
        "merged_audio_filename": merged_audio_filename,
        "download_url": f"/api/v1/podcast/download/{merged_audio_filename}"
    }

# ============================================================
# GENERATE VIDEO
# ============================================================
@app.post("/api/v1/podcast/generate-video/{database_id}")
def generate_podcast_video(database_id: int, db: Session = Depends(get_db)):
    db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
    if not db_item:
        raise HTTPException(404, "Podcast tidak ditemukan.")
    if not db_item.audio_segments:
        raise HTTPException(400, "Belum ada segmen audio.")

    # Merge audio dulu jika belum
    if not db_item.merged_audio_filename:
        clean_keyword = re.sub(r'[\\/*?:"<>|]', '', db_item.keyword or "podcast")
        clean_keyword = clean_keyword.replace(' ', '_')[:50]
        merged_filename = f"podcast_{clean_keyword}_{database_id}.mp3"
        merged_audio_filename = merge_podcast_segments(db_item.audio_segments, merged_filename, cleanup_segments=False)
        db_item.merged_audio_filename = merged_audio_filename
        db.commit()
        db.refresh(db_item)

    metadata = db_item.metadata_json or {}
    video_filename = create_tiktok_video_with_subtitles(db_item.merged_audio_filename, metadata)

    if not video_filename:
        raise HTTPException(500, "Gagal merender video.")

    db_item.video_filename = video_filename
    db_item.tiktok_status = "uploading"
    db.commit()
    db.refresh(db_item)

    # === AUTO-UPLOAD TIKTOK ===
    try:
        result = publish_to_tiktok_webhook(video_filename, metadata)
        if result.get("status") in ["success", "test_success"]:
            db_item.tiktok_status = "success"
            db_item.tiktok_url = result.get("data", {}).get("url") or "Uploaded"
            db_item.tiktok_uploaded_at = datetime.utcnow()
        else:
            db_item.tiktok_status = "failed"
            db_item.tiktok_error = result.get("error", "Unknown error")
        db.commit()
    except Exception as e:
        db_item.tiktok_status = "failed"
        db_item.tiktok_error = str(e)
        db.commit()

    return {
        "status": "completed",
        "database_id": db_item.id,
        "video_filename": video_filename,
        "video_stream_url": f"/api/v1/podcast/video/{video_filename}",
        "tiktok_status": db_item.tiktok_status,
        "tiktok_url": db_item.tiktok_url
    }

# ============================================================
# DOWNLOAD & STREAM
# ============================================================
@app.get("/api/v1/podcast/download/{filename}")
def download_audio_file(filename: str):
    file_path = os.path.join(settings.OUTPUT_AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File '{filename}' tidak ditemukan.")
    return FileResponse(path=file_path, media_type="audio/mpeg", filename=filename)

@app.get("/api/v1/podcast/video/{video_filename}")
def get_video_stream(video_filename: str):
    video_path = os.path.join(settings.OUTPUT_VIDEO_DIR, video_filename)
    if not os.path.exists(video_path):
        raise HTTPException(404, "File video tidak ditemukan")
    return FileResponse(video_path, media_type="video/mp4")

# ============================================================
# PUBLISH TIKTOK (RETRY)
# ============================================================
@app.post("/api/v1/podcast/publish-tiktok/{database_id}")
def publish_tiktok_retry(database_id: int, db: Session = Depends(get_db)):
    db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
    if not db_item:
        raise HTTPException(404, "Podcast tidak ditemukan.")
    if not db_item.video_filename:
        raise HTTPException(400, "Belum ada video untuk dipublish.")

    metadata = db_item.metadata_json or {}
    result = publish_to_tiktok_webhook(db_item.video_filename, metadata)

    if result.get("status") in ["success", "test_success"]:
        db_item.tiktok_status = "success"
        db_item.tiktok_url = result.get("data", {}).get("url") or "Uploaded"
        db_item.tiktok_uploaded_at = datetime.utcnow()
        db.commit()
        return {"status": "success", "tiktok_url": db_item.tiktok_url}
    else:
        db_item.tiktok_status = "failed"
        db_item.tiktok_error = result.get("error", "Unknown error")
        db.commit()
        raise HTTPException(500, f"Gagal publish: {db_item.tiktok_error}")