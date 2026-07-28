from app.agents.research_agent import run_research_agent
from app.agents.script_agent import run_scriptwriter_agent
from app.agents.audio_agent import run_audio_generation_agent

def run_ai_pipeline(keyword: str):
    """
    Menjalankan pipeline lengkap: Qwen (Research) -> Agnes (Script) -> ElevenLabs (Audio).
    """
    print(f"\n[PIPELINE] Memulai proses podcast otonom untuk keyword: '{keyword}'...")
    
    # Tahap 1: Riset oleh Qwen AI
    research_data = run_research_agent(keyword)
    if isinstance(research_data, str) and (research_data.startswith("Gagal") or research_data.startswith("Error")):
        return research_data, [{"error": "Pipeline terhenti pada tahap Qwen AI."}], []
    
    # Tahap 2: Pembuatan Naskah oleh Agnes AI
    script_json = run_scriptwriter_agent(research_data)
    if isinstance(script_json, list) and len(script_json) > 0 and "error" in script_json[0]:
        return research_data, script_json, []
        
    # Tahap 3: Pembuatan Audio oleh ElevenLabs
    print("[PIPELINE] [3/3] Menghubungkan ke ElevenLabs untuk sintesis suara...")
    audio_output = run_audio_generation_agent(script_json)
    
    print("[PIPELINE] Seluruh rangkaian proses PodFlow AI selesai!\n")
    return research_data, script_json, audio_output