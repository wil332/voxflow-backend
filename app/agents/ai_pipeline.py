from app.agents.research_agent import run_research_agent
from app.agents.script_agent import run_script_agent          # ← alias dari run_scriptwriter_agent
from app.agents.metadata_agent import run_metadata_agent
from app.agents.audio_agent import run_audio_generation_agent as run_audio_agent

def run_ai_pipeline(keyword: str):
    """
    Pipeline utama: Research → Script → Metadata → Audio.
    Mengembalikan 4 nilai: (research_text, script_json, metadata_dict, audio_segments_list)
    """
    print(f"[PIPELINE] Memulai riset untuk keyword: {keyword}")

    # 1. Riset
    research_result = run_research_agent(keyword)

    # 2. Naskah (fallback otomatis jika Agnes error)
    script_result = run_script_agent(research_result)

    # 3. Metadata SEO
    metadata_result = run_metadata_agent(keyword, research_result)

    # 4. Audio per segmen (ElevenLabs)
    audio_segments = run_audio_agent(script_result)

    print(f"[PIPELINE SUCCESS] Pipeline selesai untuk keyword: {keyword}")
    return research_result, script_result, metadata_result, audio_segments