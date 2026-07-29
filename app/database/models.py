from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.ext.mutable import MutableDict
from datetime import datetime
from app.database.database import Base


def default_agent_status():
    # Pakai callable, bukan dict literal langsung di Column(default=...),
    # supaya tiap row baru dapat dict baru (bukan berbagi referensi dict
    # yang sama antar row).
    return {
        "research": "pending",
        "script": "pending",
        "audio": "pending",
        "metadata": "pending",   # SEO metadata agent (title/desc/tags/cta)
        "tiktok": "pending",     # upload/publish ke TikTok - terpisah dari metadata
    }


class PodcastHistory(Base):
    __tablename__ = "podcast_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    keyword = Column(String(255), index=True)
    research_summary = Column(Text, nullable=True)
    status = Column(String(50), default="processing")  # processing | completed | failed
    progress = Column(Integer, default=0)               # 0-100

    # MutableDict.as_mutable() membuat SQLAlchemy melacak mutasi in-place
    # (item.agent_status["key"] = value), bukan cuma reassignment penuh.
    # Tanpa ini, update in-place tidak pernah ter-commit ke database.
    agent_status = Column(MutableDict.as_mutable(JSON), default=default_agent_status)

    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    audio_segments = Column(JSON, nullable=True)        # daftar segmen mentah
    merged_audio_filename = Column(String(255), nullable=True)
    video_filename = Column(String(255), nullable=True)

    # === Status publish TikTok ===
    tiktok_status = Column(String(50), default="pending")  # pending | uploading | success | failed
    tiktok_url = Column(String(500), nullable=True)
    tiktok_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)