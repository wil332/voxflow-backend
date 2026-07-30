# app/agents/audio_agent.py

import os
import requests
import tempfile
from pydub import AudioSegment
from app.config import settings

def run_audio_generation_agent(script_json: list, voice: str = "mixed") -> list:
    print(f"[AUDIO] Voice: {voice}")

    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)

    voice_mapping = {
        "male": {"Budi": "ErXwobaYiN019PkySvjV", "Richel": "ErXwobaYiN019PkySvjV"},
        "female": {"Budi": "EXAVITQu4vr4xnSDxMaL", "Richel": "EXAVITQu4vr4xnSDxMaL"},
        "mixed": {"Budi": "ErXwobaYiN019PkySvjV", "Richel": "EXAVITQu4vr4xnSDxMaL"}
    }

    voice_map = voice_mapping.get(voice, voice_mapping["mixed"])
    audio_results = []

    for index, line in enumerate(script_json):
        if "error" in line:
            continue

        speaker_raw = line.get("speaker", "Budi")
        text = line.get("text", "")

        if not text or len(text.strip()) < 3:
            print(f"[AUDIO] ⚠️ Skip empty text at segment {index+1}")
            continue

        # Pilih voice ID
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
            "text": text[:1000],  # Batasi panjang teks
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.3,      # <-- Turunkan stability untuk lebih natural
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

        try:
            print(f"[AUDIO] Generating {speaker_display} (Segment {index+1})...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                # ============================================================
                # SIMPAN AUDIO DENGAN VALIDASI
                # ============================================================
                file_path = os.path.join(output_dir, f"segment_{index}_{speaker_display}.mp3")

                # Simpan dulu ke temp untuk validasi
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                    tmp.write(response.content)
                    tmp_path = tmp.name

                # ============================================================
                # VALIDASI: Coba load dengan pydub
                # ============================================================
                try:
                    test_audio = AudioSegment.from_file(tmp_path, format="mp3")
                    if len(test_audio) < 500:  # Kurang dari 0.5 detik
                        raise ValueError("Audio terlalu pendek")

                    # Pindahkan ke folder output
                    os.rename(tmp_path, file_path)

                    audio_results.append({
                        "segment": index + 1,
                        "speaker": speaker_display,
                        "status": "success",
                        "file_path": file_path,
                        "duration_ms": len(test_audio)
                    })
                    print(f"[AUDIO] ✅ Segment {index+1} saved ({len(test_audio)}ms)")

                except Exception as e:
                    print(f"[AUDIO] ❌ Invalid audio: {e}")
                    os.remove(tmp_path)
                    audio_results.append({
                        "segment": index + 1,
                        "speaker": speaker_display,
                        "status": "failed",
                        "error": f"Invalid audio: {str(e)}"
                    })

            else:
                print(f"[AUDIO] ❌ ElevenLabs error: {response.status_code}")
                audio_results.append({
                    "segment": index + 1,
                    "speaker": speaker_display,
                    "status": "failed",
                    "error": response.text[:200]
                })

        except Exception as e:
            print(f"[AUDIO] ❌ Error: {e}")
            audio_results.append({
                "segment": index + 1,
                "speaker": speaker_display,
                "status": "error",
                "error": str(e)
            })

    return audio_results