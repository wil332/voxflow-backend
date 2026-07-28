import os
import re
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agents.ai_pipeline import run_ai_pipeline
from app.middlewares.error_handler import setup_exception_handlers
from app.database.database import engine, Base, get_db
from app.database.models import PodcastHistory
from app.utils.audio_merger import merge_podcast_segments
from app.agents.metadata_agent import run_metadata_agent

# Membuat tabel otomatis saat aplikasi berjalan
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PodFlow AI Backend",
    description="API server untuk otomatisasi platform podcast otonom.",
    version="1.0.0"
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