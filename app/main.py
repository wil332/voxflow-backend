import os
import re
import logging
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import static_ffmpeg
from app.config import settings
from app.database.database import engine, Base, get_db
from app.database.models import PodcastHistory
from app.middlewares.error_handler import setup_exception_handlers

# ============================================================
# SETUP LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# SETUP FFMPEG
# ============================================================
try:
    static_ffmpeg.add_paths()
    logger.info("FFmpeg paths added successfully")
except Exception as e:
    logger.error(f"FFmpeg setup error: {e}")

# ============================================================
# DATABASE INITIALIZATION
# ============================================================
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
except Exception as e:
    logger.error(f"Database initialization error: {e}")

# ============================================================
# FASTAPI APP
# ============================================================
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API server untuk otomatisasi platform podcast otonom.",
    version=settings.VERSION
)

# ============================================================
# CORS MIDDLEWARE
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://*.railway.app",
        "https://*.vercel.app",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

setup_exception_handlers(app)

# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "PodFlow AI Backend is running and ready!",
        "cors": "enabled",
        "database": "connected"
    }

# ============================================================
# DEBUG ENDPOINT
# ============================================================
@app.get("/api/v1/debug")
def debug_info():
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "database": db_status,
        "storage_dir": settings.STORAGE_DIR,
        "api_keys": {
            "qwen": "set" if settings.QWEN_API_KEY else "MISSING",
            "agnes": "set" if settings.AGNES_API_KEY else "MISSING",
            "elevenlabs": "set" if settings.ELEVENLABS_API_KEY else "MISSING",
            "groq": "set" if settings.GROQ_API_KEY else "MISSING",
        }
    }

# ============================================================
# HISTORY ENDPOINT
# ============================================================
@app.get("/api/v1/podcast/history")
def get_podcast_history(db: Session = Depends(get_db)):
    try:
        logger.info("Fetching podcast history")
        history = db.query(PodcastHistory).all()
        return {
            "status": "success",
            "total": len(history),
            "data": history
        }
    except Exception as e:
        logger.error(f"History error: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "status": "error",
                "total": 0,
                "data": [],
                "message": str(e)
            }
        )

# ============================================================
# GENERATE ENDPOINT
# ============================================================
@app.post("/api/v1/podcast/generate")
def trigger_podcast_generation(
    keyword: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Generate request for keyword: {keyword}")

        # Cek API keys
        if not settings.QWEN_API_KEY:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "QWEN_API_KEY not configured"}
            )
        if not settings.AGNES_API_KEY:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "AGNES_API_KEY not configured"}
            )
        if not settings.ELEVENLABS_API_KEY:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "ELEVENLABS_API_KEY not configured"}
            )

        # Buat entri database
        db_item = PodcastHistory(
            keyword=keyword,
            status="processing",
            progress=0,
            agent_status={
                "research": "pending",
                "script": "pending",
                "audio": "pending",
                "metadata": "pending"
            }
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        logger.info(f"Created job {db_item.id} for keyword: {keyword}")

        from app.agents.ai_pipeline import run_ai_pipeline

        def run_pipeline():
    try:
        from app.database.database import SessionLocal
        from app.agents.ai_pipeline import run_ai_pipeline
        import re

        bg_db = SessionLocal()
        try:
            item = bg_db.query(PodcastHistory).filter(PodcastHistory.id == db_item.id).first()
            if item:
                # === SET STATUS AWAL ===
                item.status = "processing"
                item.progress = 5
                item.agent_status = {
                    "research": "pending",
                    "script": "pending",
                    "audio": "pending",
                    "metadata": "pending"
                }
                bg_db.commit()
                print(f"[MAIN] Job {db_item.id} initialized")

                # === JALANKAN PIPELINE DENGAN JOB_ID ===
                research_data, script_json, metadata, audio_segments = run_ai_pipeline(keyword, db_item.id)

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
                    "metadata": "done"
                }
                bg_db.commit()
                print(f"[MAIN] Job {db_item.id} completed successfully")

        except Exception as e:
            print(f"[MAIN] Pipeline error: {e}")
            import traceback
            traceback.print_exc()
            if bg_db:
                item = bg_db.query(PodcastHistory).filter(PodcastHistory.id == db_item.id).first()
                if item:
                    item.status = "failed"
                    item.error_message = str(e)
                    bg_db.commit()
        finally:
            bg_db.close()
    except Exception as e:
        print(f"[MAIN] Background task error: {e}")
        import traceback
        traceback.print_exc()


        background_tasks.add_task(run_pipeline)

        return {
            "job_id": db_item.id,
            "status": "processing",
            "message": "Pipeline started"
        }
    except Exception as e:
        logger.error(f"Generate error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "detail": "Internal server error"
            }
        )

# ============================================================
# STATUS ENDPOINT
# ============================================================
@app.get("/api/v1/podcast/status/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    try:
        item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
        if not item:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "message": "Job tidak ditemukan"}
            )

        response = {
            "id": item.id,
            "keyword": item.keyword,
            "status": item.status,
            "progress": item.progress,
            "agent_status": item.agent_status,
            "error_message": item.error_message,
        }

        if item.status == "completed":
            if item.merged_audio_filename:
                response["audio_url"] = f"/api/v1/podcast/download/{item.merged_audio_filename}"
            if item.video_filename:
                response["video_url"] = f"/api/v1/podcast/video/{item.video_filename}"
            if item.metadata_json:
                response["metadata"] = item.metadata_json

        return response
    except Exception as e:
        logger.error(f"Status error: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

# ============================================================
# DOWNLOAD & STREAM
# ============================================================
@app.get("/api/v1/podcast/download/{filename}")
def download_audio_file(filename: str):
    try:
        file_path = os.path.join(settings.OUTPUT_AUDIO_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(404, f"File '{filename}' tidak ditemukan.")
        return FileResponse(path=file_path, media_type="audio/mpeg", filename=filename)
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

@app.get("/api/v1/podcast/video/{video_filename}")
def get_video_stream(video_filename: str):
    try:
        video_path = os.path.join(settings.OUTPUT_VIDEO_DIR, video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(404, "File video tidak ditemukan")
        return FileResponse(video_path, media_type="video/mp4")
    except Exception as e:
        logger.error(f"Video stream error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

# ============================================================
# MERGE AUDIO
# ============================================================
@app.post("/api/v1/podcast/merge-audio/{database_id}")
def merge_podcast_audio(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.utils.audio_merger import merge_podcast_segments

        db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
        if not db_item:
            raise HTTPException(404, "Podcast tidak ditemukan.")
        if not db_item.audio_segments:
            raise HTTPException(400, "Belum ada segmen audio.")
        if db_item.status != "completed":
            raise HTTPException(400, "Podcast belum selesai diproses.")

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
    except Exception as e:
        logger.error(f"Merge audio error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

# ============================================================
# GENERATE VIDEO
# ============================================================
@app.post("/api/v1/podcast/generate-video/{database_id}")
def generate_podcast_video(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.utils.video_generator import create_tiktok_video_with_subtitles
        from app.utils.audio_merger import merge_podcast_segments

        db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
        if not db_item:
            raise HTTPException(404, "Podcast tidak ditemukan.")
        if not db_item.audio_segments:
            raise HTTPException(400, "Belum ada segmen audio.")
        if db_item.status != "completed":
            raise HTTPException(400, "Podcast belum selesai diproses.")

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
        db.commit()
        db.refresh(db_item)

        return {
            "status": "completed",
            "database_id": db_item.id,
            "video_filename": video_filename,
            "video_stream_url": f"/api/v1/podcast/video/{video_filename}"
        }
    except Exception as e:
        logger.error(f"Generate video error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")