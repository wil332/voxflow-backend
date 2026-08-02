from datetime import datetime
from xml.sax.saxutils import escape
from app.database.models import PodcastHistory
from sqlalchemy.orm import Session


def generate_rss_feed(db: Session, base_url: str = "http://localhost:8000") -> str:
    episodes = db.query(PodcastHistory).order_by(PodcastHistory.created_at.desc()).all()

    items_xml = ""
    episode_number = 0

    for ep in episodes:
        # CATATAN PERBAIKAN #1:
        # Sebelumnya nama file audio DIREKONSTRUKSI dari keyword:
        #   f"podcast_{ep.keyword.replace(' ', '_')}.mp3"
        # Ini TIDAK PERNAH cocok dengan nama file asli yang benar-benar
        # tersimpan di disk. Nama file asli (lihat main.py/ai_pipeline.py)
        # dibuat lewat re.sub() untuk membersihkan karakter ilegal DAN
        # ditambah suffix "_{id}" -- rekonstruksi manual di atas selalu
        # menghasilkan URL yang 404. Sekarang pakai `merged_audio_filename`
        # yang SUDAH tersimpan di database (nama file yang sebenarnya ada).
        if not ep.merged_audio_filename:
            # Episode belum selesai di-merge -- skip dari RSS, bukan
            # menampilkan link yang pasti 404.
            continue

        episode_number += 1

        # CATATAN PERBAIKAN #2:
        # Sebelumnya kode ini mengasumsikan metadata_json berbentuk
        # {"spotify": {"episode_title": ..., "show_notes": ...}}. Tapi
        # metadata_agent.py menghasilkan struktur FLAT:
        # {"title": ..., "description": ..., "tags": [...], ...} -- tanpa
        # key "spotify" sama sekali. Akibatnya title/description selalu
        # jatuh ke fallback (keyword/research_summary), metadata asli hasil
        # AI tidak pernah kepakai di RSS. Sekarang baca langsung dari root.
        metadata = ep.metadata_json or {}
        title = escape(metadata.get("title", ep.keyword or "Untitled Episode"))
        description = escape(metadata.get("description", ep.research_summary or ""))

        pub_date = (
            ep.created_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
            if ep.created_at
            else datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        )

        audio_url = f"{base_url}/api/v1/podcast/download/{ep.merged_audio_filename}"

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
