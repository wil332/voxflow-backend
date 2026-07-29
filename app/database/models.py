from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from datetime import datetime
from app.database.database import Base

class PodcastHistory(Base):
    __tablename__ = "podcast_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    keyword = Column(String(255), index=True)
    research_summary = Column(Text, nullable=True)
    status = Column(String(50), default="processing")  # processing | completed | failed
    progress = Column(Integer, default=0)              # 0-100
    agent_status = Column(JSON, default={
        "research": "pending",
        "script": "pending",
        "audio": "pending",
        "metadata": "pending"
    })
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    audio_segments = Column(JSON, nullable=True)       # daftar segmen mentah
    merged_audio_filename = Column(String(255), nullable=True)
    video_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)