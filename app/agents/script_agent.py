# app/agents/script_agent.py

import json
import re
import requests
from app.config import settings

def run_scriptwriter_agent(research_text: str, language: str = "indonesian", tone: str = "professional") -> list:
    print(f"[SCRIPT] Language: {language}, Tone: {tone}")
    print(f"[SCRIPT] Research text length: {len(research_text)}")

    url = "https://apihub.agnes-ai.com/v1/chat/completions"

    # ... prompt system (sesuai bahasa) ...

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=90)

        if response.status_code != 200:
            print(f"[SCRIPT] ❌ Agnes API error: {response.status_code}")
            print(f"[SCRIPT] Response: {response.text[:200]}")
            raise ValueError(f"Agnes API Error: {response.status_code}")

        data = response.json()
        raw_content = data['choices'][0]['message']['content']
        print(f"[SCRIPT] Raw content (first 200 chars): {raw_content[:200]}")

        # ============================================================
        # 1. BERSIHKAN MARKDOWN
        # ============================================================
        cleaned_content = re.sub(r'```(?:json)?', '', raw_content).strip()

        # ============================================================
        # 2. COBA PARSE JSON
        # ============================================================
        try:
            script_data = json.loads(cleaned_content)
        except json.JSONDecodeError:
            # Cari array JSON di dalam teks
            match = re.search(r'\[.*\]', cleaned_content, re.DOTALL)
            if match:
                script_data = json.loads(match.group(0))
            else:
                raise ValueError("No valid JSON array found in response")

        # ============================================================
        # 3. NORMALISASI FORMAT
        # ============================================================
        # Jika response berbentuk {"podcast_naskah": [...]}
        if isinstance(script_data, dict):
            for key in ["podcast_naskah", "script", "dialog", "conversation"]:
                if key in script_data and isinstance(script_data[key], list):
                    script_data = script_data[key]
                    break
            # Jika masih dict, coba ambil nilai pertama yang berupa list
            if isinstance(script_data, dict):
                for value in script_data.values():
                    if isinstance(value, list):
                        script_data = value
                        break

        # ============================================================
        # 4. VALIDASI & FILTER SEGMEN KOSONG
        # ============================================================
        if not isinstance(script_data, list):
            raise ValueError(f"Script data is not a list: {type(script_data)}")

        valid_segments = []
        for i, seg in enumerate(script_data):
            if not isinstance(seg, dict):
                print(f"[SCRIPT] ⚠️ Segment {i} is not a dict: {type(seg)}")
                continue
            # Pastikan ada field 'text' dengan isi
            text = seg.get("text", "").strip()
            if not text:
                print(f"[SCRIPT] ⚠️ Segment {i} has empty text")
                continue
            # Pastikan ada field 'speaker'
            speaker = seg.get("speaker", "Richel").strip()
            if not speaker:
                seg["speaker"] = "Richel"
            valid_segments.append(seg)

        if len(valid_segments) == 0:
            print("[SCRIPT] ❌ No valid segments found! Using fallback.")
            return get_fallback_script(research_text, language)

        print(f"[SCRIPT] ✅ Valid segments: {len(valid_segments)}")
        return valid_segments

    except Exception as e:
        print(f"[SCRIPT] ❌ Error: {e}")
        return get_fallback_script(research_text, language)


def get_fallback_script(research_text: str, language: str = "indonesian") -> list:
    """Fallback script ketika Agnes gagal"""
    print("[SCRIPT] Using fallback script")

    if language == "indonesian":
        return [
            {"speaker": "Budi", "text": f"Halo semuanya! Selamat datang di podcast kita. Kali ini kita akan membahas tentang {research_text[:50]}...", "emotion": "excited"},
            {"speaker": "Richel", "text": f"Hai Budi! Wah topiknya menarik banget nih. {research_text[:80]}... Yuk kita mulai pembahasannya!", "emotion": "curious"},
            {"speaker": "Budi", "text": "Saya setuju! Mari kita bahas secara mendalam.", "emotion": "neutral"},
            {"speaker": "Richel", "text": "Oke, kita mulai dari konsep dasarnya dulu ya.", "emotion": "educational"},
        ]
    else:
        return [
            {"speaker": "Budi", "text": f"Hello everyone! Welcome to our podcast. Today we'll discuss about {research_text[:50]}...", "emotion": "excited"},
            {"speaker": "Richel", "text": f"Hi Budi! That's a very interesting topic. {research_text[:80]}... Let's start the discussion!", "emotion": "curious"},
            {"speaker": "Budi", "text": "I agree! Let's dive deep into it.", "emotion": "neutral"},
            {"speaker": "Richel", "text": "Okay, let's start with the basics first.", "emotion": "educational"},
        ]


run_script_agent = run_scriptwriter_agent