import os
import re
from pydub import AudioSegment

FFMPEG_PATH = r"D:\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
FFPROBE_PATH = r"D:\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"

AudioSegment.converter = FFMPEG_PATH
AudioSegment.ffprobe = FFPROBE_PATH

def merge_podcast_segments(segment_filenames: list, output_filename: str = "full_podcast.mp3") -> str:
    """
    Menggabungkan seluruh segmen audio menjadi 1 file MP3 utuh,
    kemudian menghapus seluruh file segmen sementara sehingga hanya file gabungan
    yang tersimpan di dalam folder output_audio.
    """
    output_dir = "output_audio"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)
    
    combined_audio = AudioSegment.empty()
    loaded_count = 0
    processed_files = []  # Menyimpan daftar path file segmen yang berhasil dibaca
    
    # Fungsi pengurutan segmen berdasarkan angka
    def extract_segment_number(item):
        str_item = str(item)
        match = re.search(r'segment_(\d+)', str_item)
        return int(match.group(1)) if match else 9999

    sorted_segments = sorted(segment_filenames, key=extract_segment_number)
    print(f"\n[MERGER] Ditemukan {len(sorted_segments)} segmen dinamis. Memulai penggabungan...")
    
    # 1. Proses Penempelan Audio
    for item in sorted_segments:
        if isinstance(item, dict):
            raw_path = item.get("file_path") or item.get("filename") or item.get("path") or ""
        else:
            raw_path = str(item)
            
        base_name = os.path.basename(str(raw_path).strip())
        
        if not base_name or base_name == "output_audio":
            continue
            
        file_path = os.path.join(output_dir, base_name)
        
        if os.path.exists(file_path):
            try:
                segment = AudioSegment.from_file(file_path, format="mp3")
                combined_audio += segment
                combined_audio += AudioSegment.silent(duration=400) # Jeda 0.4 detik
                loaded_count += 1
                processed_files.append(file_path) # Catat file segmen untuk dihapus nanti
                print(f"[MERGER SUCCESS] Berhasil menempel: {base_name}")
            except Exception as e:
                print(f"[MERGER ERROR] Gagal membaca file {base_name}: {e}")
        else:
            print(f"[MERGER WARNING] File tidak ditemukan di: {file_path}")
            
    # 2. Ekspor File Audio Gabungan Utama
    if loaded_count > 0:
        try:
            combined_audio.export(output_path, format="mp3", bitrate="192k")
            print(f"\n[MERGER SUKSES] Total {loaded_count} segmen berhasil digabung ke: {output_path}")
            
            # 3. PEMBERSIHAN SEGMEN SEMENTARA (CLEANUP)
            # Menghapus semua file segmen setelah ekspor MP3 gabungan berhasil
            print("[CLEANUP] Menghapus file segmen sementara...")
            for temp_file in processed_files:
                try:
                    if os.path.exists(temp_file) and temp_file != output_path:
                        os.remove(temp_file)
                except Exception as cleanup_err:
                    print(f"[CLEANUP WARNING] Gagal menghapus {temp_file}: {cleanup_err}")
                    
            print("[CLEANUP SUKSES] Hanya file audio gabungan utama yang tersimpan!\n")
            
        except Exception as e:
            print(f"\n[MERGER CRITICAL ERROR] Gagal mengekspor MP3: {e}\n")
    else:
        print("\n[MERGER ERROR] Tidak ada segmen audio yang berhasil digabung!\n")
        
    return output_filename