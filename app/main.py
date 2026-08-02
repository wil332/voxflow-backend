import os
import re
import logging
from fastapi import FastAPI, Depends, HTTPException
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
        "https://voxflow-frontend.vercel.app",  # ← TAMBAHKAN INI
        "https://voxflow-frontend-k3p2yo679-voxflow-podcast-ai.vercel.app",
    ],
    # "https://*.vercel.app" dan "https://*.railway.app" TIDAK bisa taruh di
    # allow_origins -- Starlette cocokkan itu secara exact-string-match, bukan
    # glob/wildcard, jadi tidak pernah match origin asli seperti
    # "https://voxflow-frontend.vercel.app". Wildcard subdomain yang benar
    # harus lewat allow_origin_regex (regex asli).
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.railway\.app",
    # allow_credentials=False karena tidak ada fetch di frontend yang pakai
    # `credentials: "include"` (tidak ada cookie/session cross-origin).
    # Kombinasi allow_origins=["*"] + allow_credentials=True juga TIDAK valid
    # secara spesifikasi CORS -- browser akan menolak response semacam itu.
    allow_credentials=False,
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
            "openai": "set" if settings.OPENAI_API_KEY else "MISSING (subtitle akan di-skip)",
            "openrouter": "set" if settings.OPENROUTER_API_KEY else "MISSING",
        }
    }

# ============================================================
# RSS FEED (untuk hosting podcast: Spotify, Apple Podcasts, dll)
# ============================================================
from fastapi.responses import Response

@app.get("/api/v1/podcast/rss")
def get_podcast_rss_feed(db: Session = Depends(get_db)):
    try:
        from app.utils.rss_generator import generate_rss_feed
        xml_content = generate_rss_feed(db, base_url=settings.BASE_URL)
        return Response(content=xml_content, media_type="application/rss+xml")
    except Exception as e:
        logger.error(f"RSS feed error: {e}")
        raise HTTPException(500, f"Gagal generate RSS feed: {str(e)}")

# ============================================================
# MAINTENANCE: Bersihkan file corrupt sisa bug lama di volume
# ============================================================
@app.post("/api/v1/debug/cleanup-corrupt-files")
def cleanup_corrupt_files(min_bytes: int = 1000):
    """
    Hapus file .mp4/.mp3 yang ukurannya di bawah `min_bytes` -- sisa dari
    bug lama di video_generator.py (FFmpeg gagal/OOM-kill di tengah render,
    file setengah jadi tertinggal di disk). Aman dipanggil kapan saja --
    file yang masih dipakai/valid (di atas threshold) tidak disentuh.
    """
    removed = []
    errors = []

    for directory in [settings.OUTPUT_VIDEO_DIR, settings.OUTPUT_AUDIO_DIR]:
        if not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if not os.path.isfile(file_path):
                continue
            try:
                size = os.path.getsize(file_path)
                if size < min_bytes:
                    os.remove(file_path)
                    removed.append({"file": filename, "size_bytes": size})
            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

    return {
        "status": "success",
        "removed_count": len(removed),
        "removed_files": removed,
        "errors": errors,
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

        # ============================================================
        # ENQUEUE KE CELERY -- BUKAN BackgroundTasks lagi.
        # ============================================================
        # BackgroundTasks bawaan FastAPI MASIH jalan di proses/event loop
        # yang sama dengan web server -- kalau ada beberapa job generate
        # bersamaan, proses TTS/render FFmpeg yang berat bisa saling rebutan
        # resource dengan request HTTP lain yang sedang dilayani. Celery task
        # dijalankan di WORKER PROCESS TERPISAH (lihat Procfile), jadi web
        # server tetap responsif walau ada job berat sedang diproses.
        from app.tasks import run_podcast_pipeline_task
        run_podcast_pipeline_task.delay(
            db_item.id, keyword, language=language, tone=tone, voice=voice
        )

        return {
            "job_id": db_item.id,
            "status": "processing",
            "message": "Pipeline started (queued via Celery)"
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
# MERGE AUDIO (manual / retry) -- ASYNC via Celery
# ============================================================
@app.post("/api/v1/podcast/merge-audio/{database_id}", status_code=202)
def merge_podcast_audio(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.tasks import merge_audio_task

        db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
        if not db_item:
            raise HTTPException(404, "Podcast tidak ditemukan.")
        if not db_item.audio_segments:
            raise HTTPException(400, "Belum ada segmen audio.")
        if db_item.status != "completed":
            raise HTTPException(400, "Podcast belum selesai diproses.")

        task = merge_audio_task.delay(database_id)

        # Status 202 Accepted -- permintaan diterima dan diantre, BELUM
        # selesai. Frontend polling /status/{id} atau /history untuk tahu
        # kapan merged_audio_filename benar-benar terisi.
        return {
            "status": "queued",
            "database_id": database_id,
            "task_id": task.id,
            "message": "Merge audio sedang diproses di background."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Merge audio error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

# ============================================================
# GENERATE VIDEO (manual / retry) -- ASYNC via Celery
# ============================================================
@app.post("/api/v1/podcast/generate-video/{database_id}", status_code=202)
def generate_podcast_video(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.tasks import generate_video_task, merge_audio_task

        db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
        if not db_item:
            raise HTTPException(404, "Podcast tidak ditemukan.")
        if not db_item.audio_segments:
            raise HTTPException(400, "Belum ada segmen audio.")
        if db_item.status != "completed":
            raise HTTPException(400, "Podcast belum selesai diproses.")

        if not db_item.merged_audio_filename:
            # Merge dulu (juga async), baru render video -- dirantai lewat
            # Celery chain supaya render video otomatis jalan begitu merge
            # selesai, tanpa perlu request terpisah dari frontend.
            # .si() (immutable signature) dipakai untuk generate_video_task
            # supaya dia TIDAK menerima return value merge_audio_task (dict)
            # sebagai argumen tambahan -- generate_video_task cuma butuh
            # database_id yang sudah kita tahu, bukan hasil task sebelumnya.
            chain = merge_audio_task.s(database_id) | generate_video_task.si(database_id)
            task = chain.apply_async()
        else:
            task = generate_video_task.delay(database_id)

        return {
            "status": "queued",
            "database_id": database_id,
            "task_id": task.id,
            "message": "Render video sedang diproses di background."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate video error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

# ============================================================
# PUBLISH / RETRY PUBLISH KE TIKTOK (manual)
# ============================================================
# Upload TikTok sekarang otomatis jalan sebagai bagian dari pipeline utama
# (lihat ai_pipeline.py -> _auto_publish_to_tiktok). Endpoint ini disediakan
# sebagai jalur MANUAL untuk retry kalau auto-publish gagal (misal webhook
# TikTok down saat itu), tanpa perlu menjalankan ulang seluruh pipeline riset.
@app.post("/api/v1/podcast/publish-tiktok/{database_id}", status_code=202)
def publish_podcast_to_tiktok(database_id: int, db: Session = Depends(get_db)):
    try:
        from app.tasks import publish_tiktok_task

        db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
        if not db_item:
            raise HTTPException(404, "Podcast tidak ditemukan.")
        if not db_item.video_filename:
            raise HTTPException(400, "Video belum tersedia. Render video dulu sebelum publish.")

        db_item.tiktok_status = "uploading"
        db.commit()

        task = publish_tiktok_task.delay(database_id)

        return {
            "status": "queued",
            "database_id": database_id,
            "task_id": task.id,
            "message": "Publish TikTok sedang diproses di background."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish TikTok error: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

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