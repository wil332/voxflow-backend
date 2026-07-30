import os
from dotenv import load_dotenv

# Memuat file .env dari root direktori proyek
load_dotenv()

class Settings:
    PROJECT_NAME: str = "VoxFlow Ai"
    VERSION: str = "1.0.0"

    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "").strip()
    AGNES_API_KEY: str = os.getenv("AGNES_API_KEY", "").strip()
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "").strip()
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "").strip()
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    TIKTOK_WEBHOOK_URL: str = os.getenv("TIKTOK_WEBHOOK_URL", "").strip()
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000").strip()

    # Batas jumlah thread FFmpeg saat render video (lihat video_generator.py).
    # Default 2 -- aman untuk container kecil (mencegah OOM kill akibat
    # auto-detect thread berlebihan). Kalau container di-upgrade ke tier
    # dengan lebih banyak RAM/CPU, naikkan nilai ini lewat environment
    # variable FFMPEG_THREADS, tidak perlu redeploy kode.
    FFMPEG_THREADS: int = int(os.getenv("FFMPEG_THREADS", "2"))

    STORAGE_DIR: str = os.getenv("STORAGE_DIR", ".")

    @property
    def OUTPUT_AUDIO_DIR(self) -> str:
        return os.path.join(self.STORAGE_DIR, "output_audio")

    @property
    def OUTPUT_VIDEO_DIR(self) -> str:
        return os.path.join(self.STORAGE_DIR, "output_video")

    @property
    def ASSETS_DIR(self) -> str:
        return os.path.join(self.STORAGE_DIR, "assets")


settings = Settings()