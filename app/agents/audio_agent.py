# app/agents/audio_agent.py

import os
import requests
from app.config import settings

def run_audio_generation_agent(script_json: list, voice: str = "mixed") -> list:
    print(f"[AUDIO] Voice: {voice}")

    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)

    # === VOICE MAPPING ===
    voice_mapping = {
        "male": {"Budi": "ErXwobaYiN019PkySvjV", "Richel": "ErXwobaYiN019PkySvjV"},
        "female": {"Budi": "EXAVITQu4vr4xnSDxMaL", "Richel": "EXAVITQu4vr4xnSDxMaL"},
        "mixed": {"Budi": "ErXwobaYiN019PkySvjV", "Richel": "EXAVITQu4vr4xnSDxMaL"}
    }

    # Pilih mapping berdasarkan voice
    voice_map = voice_mapping.get(voice, voice_mapping["mixed"])

    audio_results = []

    for index, line in enumerate(script_json):
        if "error" in line:
            continue

        speaker_raw = line.get("speaker", "Budi")
        text = line.get("text", "")

        # Pilih voice ID berdasarkan speaker dan pilihan voice
        if "bud" in speaker_raw.lower():
            voice_id = voice_map.get("Budi")
            speaker_display = "Host_B"
        else:
            voice_id = voice_map.get("Richel")
            speaker_display = "Host_A"

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.ELEVENLABS_API_KEY
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        try:
            print(f"[AUDIO] Generating {speaker_display} (Segment {index+1})...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                file_path = os.path.join(output_dir, f"segment_{index}_{speaker_display}.mp3")
                with open(file_path, "wb") as f:
                    f.write(response.content)

                audio_results.append({
                    "segment": index + 1,
                    "speaker": speaker_display,
                    "status": "success",
                    "file_path": file_path
                })
            else:
                audio_results.append({
                    "segment": index + 1,
                    "speaker": speaker_display,
                    "status": "failed",
                    "error": response.text
                })

        except Exception as e:
            audio_results.append({
                "segment": index + 1,
                "speaker": speaker_display,
                "status": "error",
                "error": str(e)
            })

    return audio_results