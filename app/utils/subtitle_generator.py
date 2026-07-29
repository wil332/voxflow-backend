import whisper
import os

def generate_ass_subtitles(audio_path: str, output_ass_path: str):
    """
    Mengubah MP3 menjadi file subtitle .ass dengan gaya teks modern TikTok
    """
    model = whisper.load_model("base")  # Menggunakan model ringan
    result = model.transcribe(audio_path, language="id")

    # Header format .ass dengan styling warna TikTok (#2563EB & #06B6D4)
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
        for segment in result["segments"]:
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip().replace("'", "")
            f.write(f"Dialogue: 0,{start},{end},TikTok,,0,0,0,,{text}\n")

def format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds % 1) * 100)
    return f"{hrs}:{mins:02d}:{secs:02d}.{msecs:02d}"