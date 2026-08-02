import os
import re
from pydub import AudioSegment
from app.config import settings


def _default_bgm_path() -> str:
    """
    Path BGM default kalau BGM_PATH env var tidak di-set: cari file
    'default.mp3' di dalam assets/bgm/. Kalau tidak ada juga, ducking
    di-skip otomatis (podcast tetap jadi, cuma tanpa musik latar).
    """
    if settings.BGM_PATH:
        return settings.BGM_PATH
    return os.path.join(settings.ASSETS_DIR, "bgm", "default.mp3")


def _build_ducked_bgm(bgm_path: str, timeline: list) -> AudioSegment:
    """
    Membangun trek BGM yang sudah di-"duck" (volume otomatis naik-turun)
    mengikuti timeline vokal.

    timeline: list of tuple (kind, duration_ms) berurutan sesuai urutan
    audio final, dengan kind "vocal" atau "gap".

    Prinsip ducking: BGM lebih PELAN saat ada vokal (supaya suara host
    jelas terdengar), dan lebih KERAS saat jeda/tidak ada vokal (supaya
    musik latar tetap terasa "hidup", bukan diam total).
    """
    DUCK_DB = -16     # volume BGM saat vokal aktif (lebih pelan)
    RAISE_DB = -7      # volume BGM saat jeda (lebih terdengar)
    FADE_MS = 150       # transisi halus antar level volume, hindari klik/pop

    total_duration_ms = sum(dur for _, dur in timeline)
    if total_duration_ms <= 0:
        raise ValueError("Timeline kosong, tidak ada durasi untuk di-duck.")

    bgm = AudioSegment.from_file(bgm_path)

    # Loop BGM kalau lebih pendek dari total durasi podcast
    while len(bgm) < total_duration_ms:
        bgm += bgm
    bgm = bgm[:total_duration_ms]

    pieces = []
    cursor = 0
    for kind, duration_ms in timeline:
        if duration_ms <= 0:
            continue
        chunk = bgm[cursor:cursor + duration_ms]
        gain_db = DUCK_DB if kind == "vocal" else RAISE_DB
        pieces.append(chunk + gain_db)
        cursor += duration_ms

    if not pieces:
        return bgm + DUCK_DB

    ducked = pieces[0]
    for piece in pieces[1:]:
        ducked = ducked.append(piece, crossfade=min(FADE_MS, len(piece) // 2, len(ducked) // 2))

    return ducked


def merge_podcast_segments(
    segment_filenames: list,
    output_filename: str = "full_podcast.mp3",
    cleanup_segments: bool = False
) -> str:
    """
    Menggabungkan seluruh segmen audio menjadi 1 file MP3 utuh, dengan
    opsional audio ducking otomatis kalau ada file BGM tersedia.

    CATATAN PERBAIKAN (merge method):
    Versi sebelumnya memakai FFmpeg `-f concat` (concat demuxer) sebagai
    metode utama. Concat demuxer TIDAK mendekode lalu menggabungkan audio --
    dia cuma menyambung paket-paket mentah dari tiap file MP3 secara
    berurutan. Ini menghasilkan klik/glitch/suara patah tepat di titik
    sambungan kalau file sumbernya pakai bitrate variabel (VBR) -- yang
    memang lazim untuk output TTS seperti ElevenLabs.

    Solusi: decode PENUH tiap segmen ke PCM lewat pydub, gabungkan di level
    PCM (bukan bitstream MP3 mentah), baru encode ulang sekali di akhir.

    CATATAN FITUR BARU (audio ducking):
    Kalau file BGM ditemukan (lihat _default_bgm_path / BGM_PATH env var),
    dibangun trek BGM yang otomatis mengecil volumenya persis di rentang
    waktu vokal aktif, dan naik lagi di rentang jeda -- meniru teknik
    "ducking" produksi audio profesional -- lalu di-overlay di bawah trek
    vokal. Kalau BGM tidak ditemukan, proses ini di-skip sepenuhnya dan
    podcast tetap dihasilkan (vokal saja), TIDAK menggagalkan proses.
    """
    output_dir = settings.OUTPUT_AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    TARGET_SAMPLE_RATE = 44100
    TARGET_CHANNELS = 2
    MIN_GAP_MS = 150
    MAX_GAP_MS = 1200

    def extract_segment_number(item):
        str_item = str(item)
        match = re.search(r'segment_(\d+)', str_item)
        return int(match.group(1)) if match else 9999

    sorted_segments = sorted(segment_filenames, key=extract_segment_number)

    # ============================================================
    # KUMPULKAN FILE SEGMEN YANG VALID (+ pause_duration masing-masing)
    # ============================================================
    valid_segments = []  # list of (file_path, pause_duration_seconds)

    for item in sorted_segments:
        if isinstance(item, dict):
            raw_path = item.get("file_path") or item.get("filename") or item.get("path") or ""
            pause_duration = item.get("pause_duration", 0.3)
        else:
            raw_path = str(item)
            pause_duration = 0.3

        base_name = os.path.basename(str(raw_path).strip())
        if not base_name or base_name == "output_audio":
            continue

        file_path = os.path.join(output_dir, base_name)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
            valid_segments.append((file_path, pause_duration))
            print(f"[MERGER] ✅ Found: {base_name}")
        else:
            print(f"[MERGER] ⚠️ Missing: {file_path}")

    if len(valid_segments) == 0:
        print("[MERGER] ❌ No valid segments found!")
        return ""

    # ============================================================
    # DECODE + CONCAT PENUH LEWAT PYDUB -- sambil catat timeline
    # (kind, duration_ms) untuk keperluan ducking BGM nanti.
    # ============================================================
    try:
        combined = AudioSegment.empty()
        timeline = []  # [(kind, duration_ms), ...] -- "vocal" atau "gap"

        for file_path, pause_duration in valid_segments:
            try:
                audio = AudioSegment.from_file(file_path, format="mp3")
                audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
                audio = audio.set_channels(TARGET_CHANNELS)
                combined += audio
                timeline.append(("vocal", len(audio)))

                gap_ms = int((pause_duration or 0.3) * 1000)
                gap_ms = max(MIN_GAP_MS, min(gap_ms, MAX_GAP_MS))
                combined += AudioSegment.silent(duration=gap_ms, frame_rate=TARGET_SAMPLE_RATE)
                timeline.append(("gap", gap_ms))

                print(f"[MERGER] ✅ Added: {os.path.basename(file_path)} (gap {gap_ms}ms)")
            except Exception as e:
                print(f"[MERGER] ❌ Failed to decode: {os.path.basename(file_path)} - {e}")

        if len(combined) <= 500:
            print("[MERGER] ❌ Merge failed - combined audio too short (kemungkinan semua segmen gagal didekode)")
            return ""

        # ============================================================
        # AUDIO DUCKING -- overlay BGM yang sudah di-duck, kalau ada.
        # ============================================================
        bgm_path = _default_bgm_path()
        final_audio = combined

        if bgm_path and os.path.exists(bgm_path):
            try:
                print(f"[MERGER] 🎵 BGM ditemukan di {bgm_path}, menerapkan audio ducking...")
                ducked_bgm = _build_ducked_bgm(bgm_path, timeline)
                # overlay() menumpuk ducked_bgm DI BAWAH vokal (posisi 0),
                # tanpa memotong panjang trek utama.
                final_audio = combined.overlay(ducked_bgm)
                print("[MERGER] ✅ Audio ducking berhasil diterapkan.")
            except Exception as e:
                print(f"[MERGER] ⚠️ Ducking gagal ({e}), lanjut tanpa BGM.")
                final_audio = combined
        else:
            print(f"[MERGER] ℹ️ BGM tidak ditemukan di {bgm_path}, lanjut tanpa musik latar.")

        final_audio.export(output_path, format="mp3", bitrate="192k")
        print(f"[MERGER] ✅ Merge success (pydub decode+concat, no bitstream splice glitch): {output_path}")

        if cleanup_segments:
            for file_path, _ in valid_segments:
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        return output_filename

    except Exception as e:
        print(f"[MERGER] ❌ pydub merge error: {e}")
        return ""
