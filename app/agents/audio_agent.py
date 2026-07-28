import os
import requests
from app.config import settings

def run_audio_generation_agent(script_json: list) -> list:
    """Agent 3: ElevenLabs API untuk mengubah naskah JSON multi-host menjadi file audio."""
    output_dir = "output_audio"
    os.makedirs(output_dir, exist_ok=True)
    
    # Menggunakan Voice ID bawaan sistem yang aman untuk akun Free Tier
    voice_mapping = {
        "Budi": "ErXwobaYiN019PkySvjV",  #(Pria)
        "Richel": "EXAVITQu4vr4xnSDxMaL"   #(Wanita)
    }
    # pNInz6obpgDQGcFmaJgB
    
    audio_results = []

    for index, line in enumerate(script_json):
        if "error" in line:
            continue
            
        speaker_raw = line.get("speaker", "Budi")
        text = line.get("text", "")
        
        # Normalisasi penamaan speaker agar fleksibel
        speaker_normalized = speaker_raw.strip().lower()
        if "b" in speaker_normalized:
            speaker = "Host_B"
            voice_id = voice_mapping.get("Budi")
        else:
            speaker = "Host_A"
            voice_id = voice_mapping.get("Richel")
        
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
            print(f"[AUDIO] Menghasilkan suara untuk {speaker} (Bagian {index + 1})...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                file_path = os.path.join(output_dir, f"segment_{index}_{speaker}.mp3")
                with open(file_path, "wb") as f:
                    f.write(response.content)
                
                audio_results.append({
                    "segment": index + 1,
                    "speaker": speaker,
                    "status": "success",
                    "file_path": file_path
                })
            else:
                audio_results.append({
                    "segment": index + 1,
                    "speaker": speaker,
                    "status": "failed",
                    "error": response.text
                })
                
        except requests.exceptions.RequestException as e:
            audio_results.append({
                "segment": index + 1,
                "speaker": speaker,
                "status": "error",
                "error": str(e)
            })
            
    return audio_results