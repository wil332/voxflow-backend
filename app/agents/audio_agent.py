import os
import requests
from app.config import settings

def run_audio_generation_agent(script_json: list) -> list:
    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Mapping eksplisit, case-insensitive
    voice_mapping = {
        "budi": {"voice_id": "ErXwobaYiN019PkySvjV", "display": "Host_B"},
        "host_b": {"voice_id": "ErXwobaYiN019PkySvjV", "display": "Host_B"},
        "richel": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "display": "Host_A"},
        "host_a": {"voice_id": "EXAVITQu4vr4xnSDxMaL", "display": "Host_A"},
    }

    audio_results = []

    for index, line in enumerate(script_json):
        if "error" in line:
            continue

        speaker_raw = line.get("speaker", "Richel")
        text = line.get("text", "")

        # Cari mapping
        key = speaker_raw.strip().lower()
        mapping = voice_mapping.get(key, voice_mapping["richel"])  # fallback ke Richel
        voice_id = mapping["voice_id"]
        speaker_display = mapping["display"]

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.ELEVENLABS_API_KEY
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }

        try:
            print(f"[AUDIO] Menghasilkan suara untuk {speaker_display} (Bagian {index+1})...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                file_path = os.path.join(output_dir, f"segment_{index}_{speaker_display}.mp3")
                with open(file_path, "wb") as f:
                    f.write(response.content)
                audio_results.append({
                    "segment": index+1,
                    "speaker": speaker_display,
                    "status": "success",
                    "file_path": file_path
                })
            else:
                audio_results.append({
                    "segment": index+1,
                    "speaker": speaker_display,
                    "status": "failed",
                    "error": response.text
                })
        except Exception as e:
            audio_results.append({
                "segment": index+1,
                "speaker": speaker_display,
                "status": "error",
                "error": str(e)
            })

    return audio_results