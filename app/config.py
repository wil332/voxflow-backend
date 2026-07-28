import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "PodFlow AI Backend"
    VERSION: str = "1.0.0"
    
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    AGNES_API_KEY: str = os.getenv("AGNES_API_KEY", "")
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")

settings = Settings()