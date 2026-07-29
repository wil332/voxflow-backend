import os
from dotenv import load_dotenv

# Memuat file .env dari root direktori proyek
load_dotenv()

class Settings:
    PROJECT_NAME: str = "VoxFlow Ai"
    VERSION: str = "1.0.0"

    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    AGNES_API_KEY: str = os.getenv("AGNES_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # Cadangan / tidak wajib lagi kalau pakai Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")  # Dipakai khusus untuk Whisper (transkrip subtitle) via Groq
    TIKTOK_WEBHOOK_URL: str = os.getenv("TIKTOK_WEBHOOK_URL", "")
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

    # Folder penyimpanan file (audio/video/assets).
    # Di Railway: set STORAGE_DIR ke path Volume yang di-mount, misal "/data",
    # supaya file TIDAK hilang setiap kali service restart/redeploy.
    # Di lokal: dibiarkan default (folder di dalam project).
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

# Di app/config.py tambahkan
class Settings:
    # ... existing code ...

    def get_debug_info(self):
        return {
            "database_url": "set" if os.getenv("DATABASE_URL") else "MISSING",
            "qwen_key": "set" if self.QWEN_API_KEY else "MISSING",
            "agnes_key": "set" if self.AGNES_API_KEY else "MISSING",
            "elevenlabs_key": "set" if self.ELEVENLABS_API_KEY else "MISSING",
            "groq_key": "set" if self.GROQ_API_KEY else "MISSING",
        }

settings = Settings()