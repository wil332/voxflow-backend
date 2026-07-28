from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from datetime import datetime
from app.database.database import Base

class PodcastHistory(Base):
    __tablename__ = "podcast_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    keyword = Column(String(255), index=True)
    research_summary = Column(Text, nullable=True)
    status = Column(String(50), default="completed")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)