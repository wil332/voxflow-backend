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
        history = db.query(PodcastHistory).order_by(PodcastHistory.id.asc()).all()
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
    language: str = "indonesian",
    tone: str = "professional",
    voice: str = "mixed",
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Generate request for keyword: {keyword} (language={language}, tone={tone}, voice={voice})")

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
        # CATATAN: key "tiktok" ditambahkan di sini supaya konsisten dengan
        # yang dipakai ai_pipeline.py untuk melacak status upload TikTok
        # secara terpisah dari "metadata" (SEO metadata generation).
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
            }
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        logger.info(f"Created job {db_item.id} for keyword: {keyword}")

        def run_pipeline():
            try:
                from app.database.database import SessionLocal
                from app.agents.ai_pipeline import run_ai_pipeline

                bg_db = SessionLocal()
                try:
                    item = bg_db.query(PodcastHistory).filter(PodcastHistory.id == db_item.id).first()
                    if item:
                        item.status = "processing"
                        item.progress = 5
                        item.agent_status = {
                            "research": "pending",
                            "script": "pending",
                            "audio": "pending",
                            "metadata": "pending",
                            "tiktok": "pending"
                        }
                        bg_db.commit()
                        print(f"[MAIN] Job {db_item.id} initialized")

                        # Jalankan pipeline dengan job_id.
                        # CATATAN: run_ai_pipeline sekarang JUGA menjalankan
                        # merge audio -> render video -> upload TikTok secara
                        # otomatis di dalamnya sebelum return, jadi baris ini
                        # baru selesai setelah semua tahap itu (termasuk
                        # publish TikTok) sudah dicoba.
                        research_data, script_json, metadata, audio_segments = run_ai_pipeline(
                            keyword, db_item.id, language=language, tone=tone, voice=voice
                        )

                        # PENTING: refresh dulu supaya kita dapat agent_status
                        # dan tiktok_status TERBARU yang sudah di-commit oleh
                        # sesi database lain di dalam run_ai_pipeline (termasuk
                        # hasil auto-publish TikTok). Tanpa refresh, "item" di
                        # sini masih memegang data lama dari sebelum pipeline jalan.
                        bg_db.refresh(item)

                        item.research_summary = str(research_data)
                        item.metadata_json = metadata
                        item.audio_segments = audio_segments
                        item.status = "completed"
                        item.progress = 100

                        # Merge, JANGAN overwrite penuh -- supaya key "tiktok"
                        # yang sudah di-set oleh auto-publish tidak hilang
                        # tertimpa dict baru yang tidak punya key itu.
                        merged_agent_status = dict(item.agent_status or {})
                        merged_agent_status.update({
                            "research": "done",
                            "script": "done",
                            "audio": "done",
                            "metadata": "done",
                        })
                        item.agent_status = merged_agent_status

                        bg_db.commit()
                        logger.info(f"Pipeline completed for job {db_item.id}")

                except Exception as e:
                    logger.error(f"Pipeline error: {e}", exc_info=True)
                    if bg_db:
                        item = bg_db.query(PodcastHistory).filter(PodcastHistory.id == db_item.id).first()
                        if item:
                            item.status = "failed"
                            item.error_message = str(e)
                            bg_db.commit()
                finally:
                    bg_db.close()
            except Exception as e:
                logger.error(f"Background task error: {e}", exc_info=True)

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
            # Status publish TikTok dikirim selalu (bukan hanya saat completed)
            # supaya frontend bisa menampilkan progres "uploading..." secara
            # real-time lewat polling, sama seperti agent lain.
            "tiktok_status": item.tiktok_status,
            "tiktok_url": item.tiktok_url,
            "tiktok_error": item.tiktok_error,
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
# MERGE AUDIO (manual / retry)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merge audio error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

# ============================================================
# GENERATE VIDEO (manual / retry)
# ============================================================
@app.post("/api/v1/podcast/generate-video/{database_id}")
def generate_podcast_video(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.utils.video_generator import create_tiktok_video_with_subtitles
        from app.utils.audio_merger import merge_podcast_segments
        from app.agents.tiktok_agent import publish_to_tiktok_webhook

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

        # ============================================================
        # BARU: Otomatis lanjut upload ke TikTok, tanpa klik manual terpisah
        # ============================================================
        tiktok_metadata = metadata.get("tiktok", metadata)  # fallback kalau metadata belum multi-platform
        tiktok_result = publish_to_tiktok_webhook(video_filename, tiktok_metadata)

        db_item.tiktok_status = tiktok_result.get("status")
        if tiktok_result.get("status") == "success":
            db_item.tiktok_url = tiktok_result.get("data", {}).get("url") or None
        else:
            db_item.tiktok_error = tiktok_result.get("error")
        db.commit()
        db.refresh(db_item)

        return {
            "status": "completed",
            "database_id": db_item.id,
            "video_filename": video_filename,
            "video_stream_url": f"/api/v1/podcast/video/{video_filename}",
            "tiktok_upload": tiktok_result,
            "message": (
                "Video berhasil dibuat DAN otomatis diupload ke TikTok!"
                if tiktok_result.get("status") == "success"
                else "Video berhasil dibuat, tapi upload TikTok gagal (cek field tiktok_upload)."
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate video error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")



@app.post("/api/v1/podcast/publish-tiktok/{database_id}")
def publish_podcast_to_tiktok(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.agents.tiktok_agent import publish_to_tiktok_webhook

        db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
        if not db_item:
            raise HTTPException(404, "Podcast tidak ditemukan.")
        if not db_item.video_filename:
            raise HTTPException(400, "Video belum tersedia. Render video dulu sebelum publish.")

        db_item.tiktok_status = "uploading"
        db.commit()

        metadata = db_item.metadata_json or {}
        result = publish_to_tiktok_webhook(db_item.video_filename, metadata)

        if result.get("status") == "success":
            data = result.get("data") or {}
            tiktok_url = data.get("video_url") or data.get("url") or data.get("share_url") if isinstance(data, dict) else None
            db_item.tiktok_status = "success"
            db_item.tiktok_url = tiktok_url
            db_item.tiktok_error = None
        else:
            db_item.tiktok_status = "failed"
            db_item.tiktok_error = result.get("error", "Unknown error")

        if db_item.agent_status is not None:
            updated = dict(db_item.agent_status)
            updated["tiktok"] = db_item.tiktok_status
            db_item.agent_status = updated

        db.commit()
        db.refresh(db_item)

        return {
            "status": db_item.tiktok_status,
            "tiktok_url": db_item.tiktok_url,
            "error": db_item.tiktok_error,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish TikTok error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

# DELETE

@app.delete("/api/v1/podcast/episode/{database_id}")
def delete_podcast_episode(database_id: int, db: Session = Depends(get_db)):
    """
    Menghapus 1 episode podcast dari database, sekaligus file audio/video
    terkait di server (kalau ada) supaya tidak jadi sampah storage.
    """
    db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail=f"Episode dengan ID {database_id} tidak ditemukan.")

    # Hapus file fisik terkait, kalau ada (tidak fatal kalau gagal/tidak ketemu)
    files_to_delete = []
    if db_item.merged_audio_filename:
        files_to_delete.append(os.path.join(settings.OUTPUT_AUDIO_DIR, db_item.merged_audio_filename))
    if db_item.video_filename:
        files_to_delete.append(os.path.join(settings.OUTPUT_VIDEO_DIR, db_item.video_filename))

    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"[DELETE WARNING] Gagal hapus file {file_path}: {e}")

    keyword = db_item.keyword
    db.delete(db_item)
    db.commit()

    return {
        "status": "success",
        "message": f"Episode '{keyword}' (ID {database_id}) berhasil dihapus.",
        "database_id": database_id
    }

# DELETE All

@app.delete("/api/v1/podcast/episodes/all")
def delete_all_podcast_episodes(db: Session = Depends(get_db)):
    """
    Menghapus SEMUA episode podcast dari database, sekaligus semua file
    audio/video terkait. Aksi ini tidak bisa dibatalkan.
    """
    all_items = db.query(PodcastHistory).all()
    deleted_count = len(all_items)

    for db_item in all_items:
        files_to_delete = []
        if db_item.merged_audio_filename:
            files_to_delete.append(os.path.join(settings.OUTPUT_AUDIO_DIR, db_item.merged_audio_filename))
        if db_item.video_filename:
            files_to_delete.append(os.path.join(settings.OUTPUT_VIDEO_DIR, db_item.video_filename))

        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"[DELETE ALL WARNING] Gagal hapus file {file_path}: {e}")

        db.delete(db_item)

    db.commit()

    return {
        "status": "success",
        "message": f"{deleted_count} episode berhasil dihapus.",
        "deleted_count": deleted_count
    }