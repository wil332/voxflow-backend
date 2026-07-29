from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.ext.mutable import MutableDict
from datetime import datetime
from app.database.database import Base

def default_agent_status():
    # Pakai fungsi/callable, bukan dict literal langsung.
    # Column(default=dict_literal) berisiko dict yang sama dipakai
    # sebagai referensi untuk banyak row kalau tidak dibungkus callable.
    return {
        "research": "pending",
        "script": "pending",
        "audio": "pending",
        "metadata": "pending"
    }

class PodcastHistory(Base):
    __tablename__ = "podcast_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    keyword = Column(String(255), index=True)
    research_summary = Column(Text, nullable=True)
    status = Column(String(50), default="processing")
    progress = Column(Integer, default=0)

    # MutableDict.as_mutable() membuat SQLAlchemy melacak perubahan
    # item[key] = value di dalam dict JSON ini, bukan cuma reassignment penuh.
    agent_status = Column(MutableDict.as_mutable(JSON), default=default_agent_status)

    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    audio_segments = Column(JSON, nullable=True)
    merged_audio_filename = Column(String(255), nullable=True)
    video_filename = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)