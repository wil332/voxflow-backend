import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import static_ffmpeg

from app.agents.ai_pipeline import run_ai_pipeline
from app.middlewares.error_handler import setup_exception_handlers
from app.database.database import engine, Base, get_db
from app.database.models import PodcastHistory
from app.utils.audio_merger import merge_podcast_segments
from app.agents.metadata_agent import run_metadata_agent
from app.utils.video_generator import create_tiktok_video_with_subtitles
from app.agents.tiktok_agent import publish_to_tiktok_webhook

# Memastikan direktori penyimpanan selalu tersedia
os.makedirs("output_audio", exist_ok=True)
os.makedirs("output_video", exist_ok=True)


# Managing Startup & Shutdown Events secara aman (Mencegah Timeout 502)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dijalankan saat aplikasi mulai menyala
    try:
        static_ffmpeg.add_paths()
        Base.metadata.create_all(bind=engine)
        print("[STARTUP] Database tables created & static_ffmpeg initialized.")
    except Exception as e:
        print(f"[STARTUP ERROR] Gagal menginisialisasi dependensi: {e}")
    yield
    # Cleanup (jika ada) saat aplikasi dimatikan
    print("[SHUTDOWN] Server VoxFlow dimatikan.")


# 2. Inisialisasi Aplikasi FastAPI
app = FastAPI(
    title="VoxFlow AI",
    description="API server untuk otomatisasi platform podcast otonom.",
    version="1.0.0",
    lifespan=lifespan
)

# 3. Konfigurasi CORS (Mendukung All-Origin & Localhost Frontend)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,  # Set False jika allow_origins=["*"] agar tidak kena CORS blocking di browser
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_exception_handlers(app)


# 4. Route Endpoints
@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "VoxFlow AI Backend is running and ready!"
    }


@app.post("/api/v1/podcast/generate")
def trigger_podcast_generation(keyword: str, db: Session = Depends(get_db)):
    # 1. Jalankan AI Pipeline
    research_data, script_json, audio_output = run_ai_pipeline(keyword)
    metadata = run_metadata_agent(keyword, research_data)

    print(f"\n[DEBUG MAIN] Isi asli audio_output: {audio_output} (Tipe: {type(audio_output)})")

    # 2. Ekstrak list segmen audio
    segments_list = []

    if isinstance(audio_output, dict):
        extracted = (
            audio_output.get("files")
            or audio_output.get("audio_files")
            or audio_output.get("segments")
            or audio_output.get("audio_segments")
        )
        if extracted is not None:
            segments_list = extracted
        else:
            segments_list = list(audio_output.values())
    elif isinstance(audio_output, list):
        segments_list = audio_output
    else:
        segments_list = [str(audio_output)] if audio_output else []

    if len(segments_list) > 0 and isinstance(segments_list[0], list):
        segments_list = [item for sublist in segments_list for item in sublist]

    print(f"[MAIN] Segmen yang siap dikirim ke merger: {segments_list}\n")

    # 3. Sanitasi Nama File
    clean_keyword = re.sub(r'[\\/*?:"<>|]', '', keyword)
    clean_keyword = clean_keyword.replace(' ', '_')
    clean_keyword = clean_keyword[:50]

    output_name = f"podcast_{clean_keyword}.mp3"

    # 4. Penggabungan Audio & Pembuatan Video
    final_audio_filename = merge_podcast_segments(segments_list, output_filename=output_name)
    video_filename = create_tiktok_video_with_subtitles(final_audio_filename, metadata)

    # 5. Simpan ke Database
    db_item = PodcastHistory(
        keyword=keyword,
        research_summary=str(research_data),
        metadata_json=metadata,
        status="completed"
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return {
        "status": "completed",
        "database_id": db_item.id,
        "keyword_received": keyword,
        "research_summary": research_data,
        "generated_script": script_json,
        "full_audio_file": final_audio_filename,
        "video_output": {
            "file": video_filename,
            "download_url": f"/api/v1/podcast/video/{video_filename}"
        },
        "metadata": metadata,
        "message": "Pipeline podcast berhasil diselesaikan dan digabung!"
    }


@app.get("/api/v1/podcast/history")
def get_podcast_history(db: Session = Depends(get_db)):
    history = db.query(PodcastHistory).all()
    return {
        "status": "success",
        "total": len(history),
        "data": history
    }


@app.get("/api/v1/podcast/download/{filename}")
def download_audio_file(filename: str):
    output_dir = "output_audio"
    file_path = os.path.join(output_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"File audio dengan nama '{filename}' tidak ditemukan."
        )

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename
    )


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
        return {
            "status": "success",
            "message": "Video berhasil dipublikasikan ke TikTok!",
            "data": result
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal upload ke TikTok: {result.get('error')}"
        )


@app.get("/api/v1/podcast/video/{video_filename}")
def get_video_stream(video_filename: str):
    video_path = os.path.join("output_video", video_filename)

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="File video tidak ditemukan")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=video_filename
    )


# Entrypoint untuk Railway/Local execution
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    # Gunakan "main:app" jika main.py berada di root direktori
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)