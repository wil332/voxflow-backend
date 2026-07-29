import os
import re
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from app.agents.ai_pipeline import run_ai_pipeline
from app.middlewares.error_handler import setup_exception_handlers
from app.database.database import engine, Base, get_db
from app.database.models import PodcastHistory
from app.utils.audio_merger import merge_podcast_segments
from app.agents.metadata_agent import run_metadata_agent
from app.utils.video_generator import create_tiktok_video_with_subtitles
from app.agents.tiktok_agent import publish_to_tiktok_webhook
from pydantic import BaseModel
from app.database import engine, Base
import static_ffmpeg

# Membuat tabel otomatis saat aplikasi berjalan
static_ffmpeg.add_paths()
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=" VoxFlow Ai",
    description="API server untuk otomatisasi platform podcast otonom.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Mengizinkan semua domain/localhost frontend
    allow_credentials=True,
    allow_methods=["*"],  # Mengizinkan semua method (GET, POST, dll)
    allow_headers=["*"],
)

setup_exception_handlers(app)

@app.get("/")
def read_root():
    return {
        "status": "success",
        "message": "PodFlow AI Backend is running and ready!"
    }

@app.post("/api/v1/podcast/generate")
def trigger_podcast_generation(keyword: str, db: Session = Depends(get_db)):
    # 1. Jalankan AI Pipeline
    research_data, script_json, audio_output = run_ai_pipeline(keyword)
    metadata = run_metadata_agent(keyword, research_data)
    
    print(f"\n[DEBUG MAIN] Isi asli audio_output: {audio_output} (Tipe: {type(audio_output)})")
    
    # 2. Ekstrak list segmen audio secara fleksibel
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

    # ==============================================================================
    # 3. PEMBERSIHAN NAMA FILE (SANITIZATION)
    # Menghapus karakter terlarang Windows (\ / : * ? " < > |) dari keyword
    # ==============================================================================
    clean_keyword = re.sub(r'[\\/*?:"<>|]', '', keyword)  # Hapus karakter ilegal
    clean_keyword = clean_keyword.replace(' ', '_')      # Ganti spasi dengan underscore
    clean_keyword = clean_keyword[:50]                   # Batasi maksimal 50 karakter
    
    output_name = f"podcast_{clean_keyword}.mp3"
    # ==============================================================================

    # 4. Jalankan Penggabungan Audio
    final_audio_filename = merge_podcast_segments(segments_list, output_filename=output_name)
    video_filename = create_tiktok_video_with_subtitles(final_audio_filename, metadata)
    # tiktok_status = publish_to_tiktok_webhook(video_filename, metadata)
    
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
        "video_output" : {
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
    """
    Endpoint yang dipanggil oleh Frontend saat tombol 'Upload ke TikTok' diklik.
    """
    metadata = {
        "title": payload.title,
        "description": payload.description,
        "tags": payload.tags,
        "cta": payload.cta
    }
    
    # Panggil fungsi agent TikTok
    result = publish_to_tiktok_webhook(payload.video_filename, metadata)
    
    if result.get("status") in ["success", "test_success"]:
        return {
            "status": "success",
            "message": "Video berhasil dipublikasikan ke TikTok MAXY!",
            "data": result
        }
    else:
        raise HTTPException(
            status_code=500, 
            detail=f"Gagal upload ke TikTok: {result.get('error')}"
        )
@app.get("/api/v1/podcast/video/{video_filename}")
def get_video_stream(video_filename: str):
    """
    Endpoint untuk menyajikan (stream/download) file MP4 ke Frontend.
    """
    video_path = os.path.join("output_video", video_filename)
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="File video tidak ditemukan")
        
    return FileResponse(video_path, media_type="video/mp4")