import os
import re
import threading
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import static_ffmpeg
from fastapi.responses import Response

from app.config import settings
from app.agents.ai_pipeline import run_ai_pipeline
from app.middlewares.error_handler import setup_exception_handlers
from app.database.database import engine, Base, get_db
from app.database.models import PodcastHistory
from app.agents.tiktok_agent import publish_to_tiktok_webhook
from app.utils.audio_merger import merge_podcast_segments
from app.utils.video_generator import create_tiktok_video_with_subtitles

static_ffmpeg.add_paths()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API server untuk otomatisasi platform podcast otonom.",
    version=settings.VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_exception_handlers(app)

# --------------------------------------------------------------------
# 1. HEALTH CHECK
# --------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"status": "success", "message": "PodFlow AI Backend is running!"}

# --------------------------------------------------------------------
# 2. PIPELINE GENERATE (ASYNCHRONOUS)
# --------------------------------------------------------------------
def run_pipeline_background(db_id: int, keyword: str):
    """Background task: jalankan pipeline dan update database."""
    from app.database.database import SessionLocal
    db = SessionLocal()

    try:
        # Update status awal
        item = db.query(PodcastHistory).filter(PodcastHistory.id == db_id).first()
        if not item:
            return
        item.status = "processing"
        item.progress = 0
        item.agent_status = {"research": "running", "script": "pending", "audio": "pending", "metadata": "pending"}
        db.commit()

        # Jalankan pipeline (synchronous di background)
        research_data, script_json, metadata, audio_segments = run_ai_pipeline(keyword)

        # Update database dengan hasil
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
        db.commit()

        print(f"[BACKGROUND] Pipeline selesai untuk job {db_id}")

    except Exception as e:
        print(f"[BACKGROUND ERROR] Job {db_id} gagal: {e}")
        item = db.query(PodcastHistory).filter(PodcastHistory.id == db_id).first()
        if item:
            item.status = "failed"
            item.error_message = str(e)
            db.commit()
    finally:
        db.close()


@app.post("/api/v1/podcast/generate")
def trigger_podcast_generation(
    keyword: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Buat entri database dengan status processing
    db_item = PodcastHistory(
        keyword=keyword,
        status="processing",
        progress=0,
        agent_status={"research": "pending", "script": "pending", "audio": "pending", "metadata": "pending"}
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    # Jalankan pipeline di background
    background_tasks.add_task(run_pipeline_background, db_item.id, keyword)

    return {
        "job_id": db_item.id,
        "status": "processing",
        "message": "Pipeline started. Poll /api/v1/podcast/status/{job_id} for progress."
    }

# --------------------------------------------------------------------
# 3. ENDPOINT STATUS (POLLING)
# --------------------------------------------------------------------
@app.get("/api/v1/podcast/status/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    item = db.query(PodcastHistory).filter(PodcastHistory.id == job_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "id": item.id,
        "keyword": item.keyword,
        "status": item.status,
        "progress": item.progress,
        "agent_status": item.agent_status,
        "error_message": item.error_message,
    }

    if item.status == "completed":
        response["metadata"] = item.metadata_json
        if item.merged_audio_filename:
            response["audio_url"] = f"/api/v1/podcast/download/{item.merged_audio_filename}"
        if item.video_filename:
            response["video_url"] = f"/api/v1/podcast/video/{item.video_filename}"

    return response

# --------------------------------------------------------------------
# 4. MERGE AUDIO (JIKA INGIN MANUAL)
# --------------------------------------------------------------------
@app.post("/api/v1/podcast/merge-audio/{database_id}")
def merge_podcast_audio(database_id: int, db: Session = Depends(get_db)):
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
    merged_audio_path = os.path.join(settings.OUTPUT_AUDIO_DIR, merged_audio_filename)

    if not os.path.exists(merged_audio_path):
        raise HTTPException(500, "Gagal menggabungkan audio.")

    db_item.merged_audio_filename = merged_audio_filename
    db.commit()
    db.refresh(db_item)

    return {
        "status": "completed",
        "database_id": db_item.id,
        "merged_audio_filename": merged_audio_filename,
        "download_url": f"/api/v1/podcast/download/{merged_audio_filename}"
    }

# --------------------------------------------------------------------
# 5. GENERATE VIDEO (RENDER MP4)
# --------------------------------------------------------------------
@app.post("/api/v1/podcast/generate-video/{database_id}")
def generate_podcast_video(database_id: int, db: Session = Depends(get_db)):
    db_item = db.query(PodcastHistory).filter(PodcastHistory.id == database_id).first()
    if not db_item:
        raise HTTPException(404, "Podcast tidak ditemukan.")
    if not db_item.audio_segments:
        raise HTTPException(400, "Belum ada segmen audio.")
    if db_item.status != "completed":
        raise HTTPException(400, "Podcast belum selesai diproses.")

    # Cek apakah merged_audio sudah ada, kalau belum, buat dulu
    if not db_item.merged_audio_filename:
        clean_keyword = re.sub(r'[\\/*?:"<>|]', '', db_item.keyword or "podcast")
        clean_keyword = clean_keyword.replace(' ', '_')[:50]
        merged_filename = f"podcast_{clean_keyword}_{database_id}.mp3"
        merged_audio_filename = merge_podcast_segments(db_item.audio_segments, merged_filename, cleanup_segments=False)
        db_item.merged_audio_filename = merged_audio_filename
        db.commit()
        db.refresh(db_item)

    # Render video
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

# --------------------------------------------------------------------
# 6. DOWNLOAD & STREAM (TIDAK BERUBAH, TETAP ADA)
# --------------------------------------------------------------------
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

# --------------------------------------------------------------------
# 7. TIKTOK UPLOAD (MANUAL)
# --------------------------------------------------------------------
class TikTokUploadRequest(BaseModel):
    video_filename: str
    title: str
    description: str
    tags: list[str] = []
    cta: str = "Jangan lupa follow!"

@app.post("/api/v1/podcast/upload-tiktok")
def upload_to_tiktok_manual(payload: TikTokUploadRequest):
    metadata = {
        "title": payload.title,
        "description": payload.description,
        "tags": payload.tags,
        "cta": payload.cta
    }
    result = publish_to_tiktok_webhook(payload.video_filename, metadata)
    if result.get("status") in ["success", "test_success"]:
        return {"status": "success", "message": "Video berhasil dipublikasikan ke TikTok MAXY!", "data": result}
    else:
        raise HTTPException(500, f"Gagal upload ke TikTok: {result.get('error')}")

# --------------------------------------------------------------------
# 8. HISTORY (TETAP ADA)
# --------------------------------------------------------------------
@app.get("/api/v1/podcast/history")
def get_podcast_history(db: Session = Depends(get_db)):
    history = db.query(PodcastHistory).all()
    return {"status": "success", "total": len(history), "data": history}

# di app/main.py, tambahkan setelah endpoint history

@app.get("/api/v1/podcast/rss")
def get_rss_feed(db: Session = Depends(get_db)):
    """
    Generate RSS feed XML dari history podcast.
    """
    history = db.query(PodcastHistory).order_by(PodcastHistory.created_at.desc()).limit(20).all()

    # Bangun XML RSS
    rss_items = []
    for item in history:
        # Ambil metadata
        meta = item.metadata_json or {}
        title = meta.get("title", f"Episode {item.id}")
        description = meta.get("description", item.research_summary or "")
        pub_date = item.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000") if item.created_at else ""
        # URL audio (jika ada)
        audio_url = f"{settings.BASE_URL}/api/v1/podcast/download/{item.merged_audio_filename}" if item.merged_audio_filename else ""

        rss_items.append(f"""
        <item>
            <title>{title}</title>
            <description>{description}</description>
            <pubDate>{pub_date}</pubDate>
            <guid>{item.id}</guid>
            <enclosure url="{audio_url}" type="audio/mpeg" length="0"/>
        </item>
        """)

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
    <channel>
        <title>VoxFlow AI Podcast</title>
        <description>Podcast otomatis oleh VoxFlow AI</description>
        <link>{settings.BASE_URL}</link>
        {''.join(rss_items)}
    </channel>
    </rss>
    """

    return Response(content=rss_xml, media_type="application/xml")