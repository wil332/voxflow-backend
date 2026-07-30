from openai import OpenAI
from app.config import settings


client = None
if settings.OPENROUTER_API_KEY:
    # Mengarahkan klien OpenAI SDK ke endpoint OpenRouter
    client = OpenAI(
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )
else:
    print("[SUBTITLE WARNING] OPENROUTER_API_KEY belum di-set. Subtitle akan di-skip (video tetap dibuat tanpa subtitle).")


def generate_ass_subtitles(audio_path: str, output_ass_path: str):
    """
    Mengubah MP3 menjadi file subtitle .ass menggunakan Whisper via OpenRouter API.

    Kalau OPENROUTER_API_KEY tidak tersedia atau transkripsi gagal, tetap menulis
    file .ass minimal (cuma header, tanpa dialog) supaya proses render video
    di video_generator.py tidak ikut gagal gara-gara file subtitle tidak ada.
    """
    segments = []

    if client is None:
        print("[SUBTITLE] Skip transkripsi -- OPENROUTER_API_KEY tidak tersedia.")
    else:
        try:
            with open(audio_path, "rb") as audio_file:
                response = client.audio.transcriptions.create(
                    model="openai/whisper-1", # Format model openrouter untuk whisper
                    file=audio_file,
                    language="id",
                    response_format="verbose_json"
                )

            if hasattr(response, 'segments') and response.segments:
                segments = response.segments
            elif isinstance(response, dict) and response.get('segments'):
                segments = response.get('segments')
            else:
                print("[SUBTITLE WARNING] Whisper tidak mengembalikan data segments.")
                segments = []

        except Exception as err:
            print(f"[SUBTITLE ERROR] Gagal transkripsi audio: {err}")
            segments = []

    # Header format .ass dengan styling warna TikTok
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TikTok,Arial,55,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,100,100,960,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header)
        for segment in segments:
            start_time = segment.start if hasattr(segment, 'start') else segment.get("start", 0)
            end_time = segment.end if hasattr(segment, 'end') else segment.get("end", 0)
            text_content = segment.text if hasattr(segment, 'text') else segment.get("text", "")

            start = format_timestamp(start_time)
            end = format_timestamp(end_time)
            text = str(text_content).strip().replace("'", "")
            f.write(f"Dialogue: 0,{start},{end},TikTok,,0,0,0,,{text}\n")


def format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds % 1) * 100)
    return f"{hrs}:{mins:02d}:{secs:02d}.{msecs:02d}"