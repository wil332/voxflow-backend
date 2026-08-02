import os
import requests
import shutil
import tempfile
from app.config import settings

def run_audio_generation_agent(script_json: list, voice: str = "mixed") -> list:
    """
    Agent 3: ElevenLabs API untuk mengubah naskah JSON multi-host menjadi file audio.
    """
    print(f"[AUDIO] Voice: {voice}")
    print(f"[AUDIO] Received {len(script_json)} segments")

    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)

    # ============================================================
    # CEK API KEY
    # ============================================================
    if not settings.ELEVENLABS_API_KEY:
        print("[AUDIO] ❌ ELEVENLABS_API_KEY is missing!")
        return []

    # ============================================================
    # VOICE MAPPING
    # ============================================================
    voice_mapping = {
        "male": {"Budi": "ErXwobaYiN019PkySvjV", "Richel": "ErXwobaYiN019PkySvjV"},
        "female": {"Budi": "EXAVITQu4vr4xnSDxMaL", "Richel": "EXAVITQu4vr4xnSDxMaL"},
        "mixed": {"Budi": "ErXwobaYiN019PkySvjV", "Richel": "EXAVITQu4vr4xnSDxMaL"}
    }

    voice_map = voice_mapping.get(voice, voice_mapping["mixed"])

    # ============================================================
    # FILTER SEGMEN KOSONG
    # ============================================================
    valid_segments = []
    for i, seg in enumerate(script_json):
        if not isinstance(seg, dict):
            print(f"[AUDIO] ⚠️ Segment {i} is not a dict: {type(seg)}")
            continue
        text = seg.get("text", "").strip()
        if not text:
            print(f"[AUDIO] ⚠️ Segment {i} has empty text")
            continue
        speaker = seg.get("speaker", "Richel")
        valid_segments.append(seg)
        print(f"[AUDIO] ✅ Segment {i}: {speaker} - {text[:30]}...")

    if len(valid_segments) == 0:
        print("[AUDIO] ❌ No valid segments to process!")
        return []

    script_json = valid_segments
    print(f"[AUDIO] 🎤 Processing {len(script_json)} valid segments")

    audio_results = []

    for index, line in enumerate(script_json):
        if "error" in line:
            continue

        speaker_raw = line.get("speaker", "Budi")
        text = line.get("text", "")

        if not text or len(text.strip()) < 3:
            print(f"[AUDIO] ⚠️ Skip empty text at segment {index+1}")
            continue

        # Pilih voice ID berdasarkan speaker dan pilihan voice
        speaker_lower = speaker_raw.strip().lower()
        if "bud" in speaker_lower:
            voice_id = voice_map.get("Budi")
            speaker_display = "Host_B"
        else:
            voice_id = voice_map.get("Richel")
            speaker_display = "Host_A"

        if not voice_id:
            print(f"[AUDIO] ❌ Voice ID not found for {speaker_raw}")
            continue

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.ELEVENLABS_API_KEY
        }

        payload = {
            "text": text[:1000],
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.3,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

        try:
            print(f"[AUDIO] 🎤 Generating {speaker_display} (Segment {index+1}/{len(script_json)})...")
            response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                # ============================================================
                # SIMPAN LANGSUNG KE FILE (tanpa temp/rename untuk hindari cross-device)
                # ============================================================
                file_path = os.path.join(output_dir, f"segment_{index}_{speaker_display}.mp3")

                # Tulis langsung
                with open(file_path, "wb") as f:
                    f.write(response.content)

                # Cek apakah file berhasil dibuat
                if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                    audio_results.append({
                        "segment": index + 1,
                        "speaker": speaker_display,
                        "status": "success",
                        "file_path": file_path,
                        "size_bytes": os.path.getsize(file_path)
                    })
                    print(f"[AUDIO] ✅ Segment {index+1} saved ({os.path.getsize(file_path)} bytes)")
                else:
                    print(f"[AUDIO] ❌ Segment {index+1} file invalid")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    audio_results.append({
                        "segment": index + 1,
                        "speaker": speaker_display,
                        "status": "failed",
                        "error": "File invalid or empty"
                    })

            else:
                print(f"[AUDIO] ❌ ElevenLabs error: {response.status_code}")
                print(f"[AUDIO] Response: {response.text[:200]}")
                audio_results.append({
                    "segment": index + 1,
                    "speaker": speaker_display,
                    "status": "failed",
                    "error": response.text[:200]
                })

        except requests.exceptions.Timeout:
            print(f"[AUDIO] ❌ Timeout for segment {index+1}")
            audio_results.append({
                "segment": index + 1,
                "speaker": speaker_display,
                "status": "error",
                "error": "Timeout"
            })
        except Exception as e:
            print(f"[AUDIO] ❌ Error: {e}")
            audio_results.append({
                "segment": index + 1,
                "speaker": speaker_display,
                "status": "error",
                "error": str(e)
            })

    # ============================================================
    # CEK HASIL: audio_results berisi campuran status "success" DAN
    # "failed"/"error" -- jangan anggap semua "generated" begitu saja,
    # karena kalau ElevenLabs down/blocked (mis. 401 unusual_activity),
    # SEMUA segmen bisa masuk sini dengan status gagal, tapi jumlahnya
    # tetap kelihatan seperti "berhasil" kalau cuma dihitung panjangnya.
    # ============================================================
    success_results = [r for r in audio_results if r.get("status") == "success"]
    failed_count = len(audio_results) - len(success_results)

    if len(success_results) == 0:
        error_samples = {r.get("error") for r in audio_results if r.get("error")}
        raise Exception(
            f"Semua {len(audio_results)} segmen audio gagal digenerate. "
            f"Contoh error: {next(iter(error_samples), 'unknown')}"
        )

    if failed_count > 0:
        print(f"[AUDIO] ⚠️ {failed_count}/{len(audio_results)} segmen gagal, lanjut dengan {len(success_results)} yang berhasil")

    print(f"[AUDIO] ✅ Finished: {len(success_results)} segments generated")
    return success_result