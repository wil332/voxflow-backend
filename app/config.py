import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "VoxFlow Ai"
    VERSION: str = "1.0.0"

    # API Keys
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "").strip()
    AGNES_API_KEY: str = os.getenv("AGNES_API_KEY", "").strip()
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "").strip()
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()

    # Webhook TikTok
    TIKTOK_WEBHOOK_URL: str = os.getenv("TIKTOK_WEBHOOK_URL", "").strip()
    BASE_URL: str = os.getenv("BASE_URL", "https://voxflow-backend-production.up.railway.app").strip()

    # ============================================================
    # 3 COOKIE TIKTOK (untuk upload langsung)
    # ============================================================
    TIKTOK_SESSIONID: str = os.getenv("TIKTOK_SESSIONID", "").strip()
    TIKTOK_SID_TT: str = os.getenv("TIKTOK_SID_TT", "").strip()
    TIKTOK_CSRF_TOKEN: str = os.getenv("TIKTOK_CSRF_TOKEN", "").strip()

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