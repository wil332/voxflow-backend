"""
app/utils/rss_generator.py

Generate RSS Feed XML standar podcast (format yang diterima Spotify, Apple Podcasts, dll)
dari data yang tersimpan di tabel PodcastHistory.

Cara pakai: panggil generate_rss_feed(db) untuk dapat string XML,
lalu serve lewat endpoint FastAPI (lihat contoh endpoint di bawah).
"""

from datetime import datetime
from xml.sax.saxutils import escape
from app.database.models import PodcastHistory
from sqlalchemy.orm import Session


def generate_rss_feed(db: Session, base_url: str = "http://localhost:8000") -> str:
    episodes = db.query(PodcastHistory).order_by(PodcastHistory.created_at.desc()).all()

    items_xml = ""
    for index, ep in enumerate(episodes):
        metadata = ep.metadata_json or {}
        spotify_meta = metadata.get("spotify", {})

        title = escape(spotify_meta.get("episode_title", ep.keyword))
        description = escape(spotify_meta.get("show_notes", ep.research_summary or ""))
        pub_date = ep.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000") if ep.created_at else datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

        # Nama file audio mengikuti pola yang dipakai endpoint /download
        audio_filename = f"podcast_{ep.keyword.replace(' ', '_')}.mp3"
        audio_url = f"{base_url}/api/v1/podcast/download/{audio_filename}"

        episode_number = len(episodes) - index  # episode terbaru = nomor tertinggi

        items_xml += f"""
    <item>
      <title>{title}</title>
      <description>{description}</description>
      <pubDate>{pub_date}</pubDate>
      <enclosure url="{audio_url}" type="audio/mpeg" />
      <guid isPermaLink="false">{ep.id}</guid>
      <itunes:episode>{episode_number}</itunes:episode>
      <itunes:season>1</itunes:season>
    </item>"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>VoxFlow AI Podcast</title>
    <link>{base_url}</link>
    <description>Podcast yang dibuat sepenuhnya otomatis oleh AI — riset, naskah, dan produksi audio otonom.</description>
    <language>id-ID</language>
    <itunes:author>VoxFlow AI</itunes:author>
    <itunes:category text="Technology" />
    {items_xml}
  </channel>
</rss>"""

    return rss_xml