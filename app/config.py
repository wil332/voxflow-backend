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
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    TIKTOK_WEBHOOK_URL: str = os.getenv("TIKTOK_WEBHOOK_URL", "")
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

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

    # === HAPUS DUPLIKAT DI BAWAH INI ===
    # def get_debug_info(self):  # <-- HAPUS BAGIAN INI
    #     return { ... }

# === PASTIKAN settings = Settings() HANYA SATU ===
settings = Settings()