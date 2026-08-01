FROM python:3.12-slim

# ffmpeg dipakai video_generator.py & audio_merger.py (tidak terkait TikTok
# upload). chromium/chromium-driver versi apt SENGAJA tidak dipakai lagi --
# lihat catatan di bawah.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


RUN playwright install --with-deps chromium

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]