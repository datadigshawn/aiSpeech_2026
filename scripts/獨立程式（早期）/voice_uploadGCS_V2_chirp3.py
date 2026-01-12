# Google STT V2 批次處理 + 時間戳記 + 自動格式轉換
# 支援自動轉換 IMA ADPCM (format 17) 為標準 PCM 格式

import os
from google.cloud import storage
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions

# =========================參數設定區==========================   
# 1. 設定金鑰路徑（自動處理相對路徑）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
KEY_FILENAME = "google-speech-key.json"

# 嘗試從多個位置尋找金鑰檔案
possible_key_paths = [
    os.path.join(PROJECT_ROOT, "utils", KEY_FILENAME),
    os.path.join(SCRIPT_DIR, KEY_FILENAME),
    os.path.join(PROJECT_ROOT, KEY_FILENAME),
]

key_path = None
for path in possible_key_paths:
    if os.path.exists(path):
        key_path = path
        break

if key_path:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
    print(f"✅ 找到金鑰檔案: {key_path}")
else:
    print(f"❌ 找不到金鑰檔案 '{KEY_FILENAME}'")
    print(f"💡 請將金鑰檔案放在以下任一位置:")
    for path in possible_key_paths:
        print(f"   - {path}")
    exit(1)

# 2. 專案設定
PROJECT_ID = "dazzling-seat-315406"
BUCKET_NAME = "my-speech-auto-2025"
LOCATION = "asia-northeast1"

# 3. 批次處理設定
INPUT_FOLDER = os.path.join(SCRIPT_DIR, "audio_input")
OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "transcripts_output")
SUPPORTED_FORMATS = {'.wav', '.mp3', '.m4a', '.flac'}

# ==========================================================

def format_timestamp(seconds):
    """將秒數轉換為 [mm:ss.ms] 格式"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"[{minutes:02d}:{secs:06.3f}]"


def convert_audio_with_pydub(input_path, output_path):
    """使用 pydub 轉換音檔"""
    try:
        from pydub import AudioSegment
        
        print(f"  🔄 使用 pydub 轉換中...")
        audio = AudioSegment.from_wav(input_path)
        
        # 轉換為標準格式
        audio = audio.set_frame_rate(16000)
        audio = audio.set_channels(1)
        audio = audio.set_sample_width(2)
        
        audio.export(output_path, format="wav", codec="pcm_s16le")
        print(f"  ✅ 轉換成功: 16kHz, 單聲道, 16-bit PCM")
        return True
        
    except ImportError:
        print(f"  ⚠️  未安裝 pydub，請執行: pip install pydub")
        return False
    except Exception as e:
        print(f"  ❌ pydub 轉換失敗: {e}")
        return False


def convert_audio_with_ffmpeg(input_path, output_path):
    """使用 ffmpeg 命令列工具轉換"""
    import subprocess
    
    try:
        print(f"  🔄 使用 ffmpeg 轉換中...")
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ar', '16000',  # 採樣率 16kHz
            '-ac', '1',       # 單聲道
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-y',  # 覆蓋輸出檔
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ 轉換成功: 16kHz, 單聲道, 16-bit PCM")
            return True
        else:
            print(f"  ❌ ffmpeg 錯誤: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print(f"  ⚠️  未安裝 ffmpeg，請執行: brew install ffmpeg")
        return False
    except Exception as e:
        print(f"  ❌ ffmpeg 轉換失敗: {e}")
        return False


def convert_to_standard_wav(input_path):
    """
    將非標準 WAV (如 IMA ADPCM) 轉換為標準 PCM 格式
    返回轉換後的檔案路徑，如果不需要轉換則返回原路徑
    """
    try:
        import wave
        with wave.open(input_path, 'rb') as wf:
            comp_type = wf.getcomptype()
            
            # 如果是標準 PCM 格式，不需轉換
            if comp_type == 'NONE':
                print(f"  ✅ 已是標準 PCM 格式")
                return input_path, False
    except Exception as e:
        # 讀取失敗通常表示需要轉換
        print(f"  ⚠️  偵測到非標準格式: {e}")
    
    # 需要轉換
    base_name = os.path.splitext(input_path)[0]
    converted_path = f"{base_name}_converted_pcm.wav"
    
    # 先嘗試 ffmpeg（較快且可靠）
    if convert_audio_with_ffmpeg(input_path, converted_path):
        return converted_path, True
    
    # 如果 ffmpeg 失敗，嘗試 pydub
    if convert_audio_with_pydub(input_path, converted_path):
        return converted_path, True
    
    # 兩者都失敗
    print(f"  ❌ 無法轉換音檔，請安裝 ffmpeg 或 pydub")
    print(f"  💡 執行: brew install ffmpeg")
    print(f"  💡 執行: pip install pydub")
    return None, False


def process_single_file(local_filename, client, recognizer_name, storage_client, bucket):
    """處理單一音檔的轉錄"""
    base_name = os.path.splitext(os.path.basename(local_filename))[0]
    print(f"\n{'='*60}")
    print(f"📝 正在處理: {os.path.basename(local_filename)}")
    print(f"{'='*60}")
    
    # 步驟1: 轉換格式
    converted_path, needs_cleanup = convert_to_standard_wav(local_filename)
    if converted_path is None:
        print(f"  ⚠️  無法轉換音檔格式，跳過此檔案")
        return False
    
    # 步驟2: 上傳到 GCS
    try:
        gcs_filename = f"batch_{os.path.basename(converted_path)}"
        blob = bucket.blob(gcs_filename)
        blob.upload_from_filename(converted_path)
        gcs_uri = f"gs://{BUCKET_NAME}/{gcs_filename}"
        print(f"  ☁️  已上傳至 Cloud Storage")
    except Exception as e:
        print(f"  ❌ 上傳失敗: {e}")
        if needs_cleanup and os.path.exists(converted_path):
            os.remove(converted_path)
        return False
    
    # 步驟3: 讀取音檔資訊
    try:
        import wave
        with wave.open(converted_path, 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / float(framerate)
            
            print(f"🎵 音檔資訊:")
            print(f"  聲道數: {channels}")
            print(f"  採樣率: {framerate} Hz")
            print(f"  位元深度: {sample_width * 8} bit")
            print(f"  時長: {duration:.2f} 秒")
    except Exception as e:
        print(f"  ⚠️  無法讀取音檔資訊: {e}")
        framerate = 16000
        channels = 1
    
    # 步驟4: 設定 Google STT 參數
    config = cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=framerate,
            audio_channel_count=channels,
        ),
        language_codes=["cmn-Hant-TW"],
        model="chirp_3",
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
        ),
    )
    
    file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)
    request = cloud_speech.BatchRecognizeRequest(
        recognizer=recognizer_name,
        config=config,
        files=[file_metadata],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )
    
    print(f"⏳ 呼叫 Google STT API 進行轉錄...")
    
    try:
        operation = client.batch_recognize(request=request)
        response = operation.result(timeout=1800)
        
        # 確保輸出資料夾存在
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)
        
        # 產生輸出檔案路徑
        full_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_完整逐字稿.txt")
        word_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_單字時間戳.txt")
        sentence_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_句子時間戳.txt")  # 新增
        csv_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_時間戳記.csv")
        
        with open(full_output, "w", encoding="utf-8") as f_full, \
             open(word_output, "w", encoding="utf-8") as f_word, \
             open(sentence_output, "w", encoding="utf-8") as f_sent, \
             open(csv_output, "w", encoding="utf-8") as f_csv:
            
            f_csv.write("開始時間(秒),結束時間(秒),時間標記,文字內容,信心分數\n")
            
            # 句子時間戳記檔案標頭
            f_sent.write("# 句子層級時間戳記\n")
            f_sent.write(f"# 檔案: {os.path.basename(local_filename)}\n")
            f_sent.write(f"# 模型: Chirp 3\n")
            f_sent.write("# " + "="*50 + "\n\n")
            
            has_content = False
            sentence_index = 1  # 句子編號
            
            for file_result in response.results.values():
                if file_result.error.message:
                    print(f"❌ 轉錄錯誤: {file_result.error.message}")
                    continue
                
                for result in file_result.transcript.results:
                    has_content = True
                    best = result.alternatives[0]
                    transcript = best.transcript.strip()
                    confidence = best.confidence
                    
                    if best.words:
                        start_time = best.words[0].start_offset.total_seconds()
                        end_time = best.words[-1].end_offset.total_seconds()
                        time_label = f"{format_timestamp(start_time)} - {format_timestamp(end_time)}"
                        duration = end_time - start_time
                        
                        # === 輸出 1: 完整逐字稿（句子層級） ===
                        f_full.write(f"{time_label}\n")
                        f_full.write(f"[信心度: {confidence:.1%}] {transcript}\n\n")
                        
                        # === 輸出 2: 句子時間戳記（新增格式） ===
                        f_sent.write(f"句子 {sentence_index}\n")
                        f_sent.write(f"時間: {time_label}\n")
                        f_sent.write(f"起始: {start_time:.3f} 秒\n")
                        f_sent.write(f"結束: {end_time:.3f} 秒\n")
                        f_sent.write(f"時長: {duration:.3f} 秒\n")
                        f_sent.write(f"信心度: {confidence:.1%}\n")
                        f_sent.write(f"內容: {transcript}\n")
                        f_sent.write("-" * 50 + "\n\n")
                        sentence_index += 1
                        
                        # === 輸出 3: 單字層級時間戳 ===
                        f_word.write(f"\n{time_label} - 完整句:\n{transcript}\n\n")
                        f_word.write("單字時間戳記:\n")
                        
                        for word_info in best.words:
                            word = word_info.word
                            w_start = word_info.start_offset.total_seconds()
                            w_time = format_timestamp(w_start)
                            f_word.write(f"  {w_time} {word}\n")
                        
                        f_word.write("-" * 50 + "\n")
                        
                        # === 輸出 4: CSV 格式（句子層級） ===
                        safe_transcript = transcript.replace(",", "；")
                        f_csv.write(f"{start_time:.3f},{end_time:.3f},{time_label},{safe_transcript},{confidence:.4f}\n")
                        
                        print(f"  {time_label} {transcript[:40]}...")
            
            if not has_content:
                print(f"  ⚠️  此音檔無法辨識出任何內容")
        
        print(f"✅ 轉錄完成！")
        print(f"  📄 {os.path.basename(full_output)}")
        print(f"  📄 {os.path.basename(sentence_output)}")
        print(f"  📄 {os.path.basename(word_output)}")
        print(f"  📊 {os.path.basename(csv_output)}")
        
        # 清理
        blob.delete()
        print(f"  🗑️  已清理 GCS 暫存檔")
        
        if needs_cleanup and os.path.exists(converted_path):
            os.remove(converted_path)
            print(f"  🗑️  已清理本地轉換檔")
        
        return has_content
        
    except Exception as e:
        print(f"❌ 轉錄失敗: {e}")
        
        try:
            blob.delete()
        except:
            pass
        
        if needs_cleanup and os.path.exists(converted_path):
            os.remove(converted_path)
        
        return False


def run_batch_pipeline():
    """批次處理資料夾內的所有音檔"""
    
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ 找不到輸入資料夾: {INPUT_FOLDER}")
        print(f"💡 請建立 '{INPUT_FOLDER}' 資料夾並放入音檔")
        return
    
    audio_files = [
        f for f in os.listdir(INPUT_FOLDER)
        if os.path.splitext(f)[1].lower() in SUPPORTED_FORMATS
    ]
    
    if not audio_files:
        print(f"❌ 在 '{INPUT_FOLDER}' 中找不到支援的音檔")
        print(f"💡 支援格式: {', '.join(SUPPORTED_FORMATS)}")
        return
    
    audio_files.sort()
    
    print(f"\n{'='*60}")
    print(f"🚀 批次處理模式")
    print(f"{'='*60}")
    print(f"📂 輸入資料夾: {INPUT_FOLDER}")
    print(f"📂 輸出資料夾: {OUTPUT_FOLDER}")
    print(f"📊 找到 {len(audio_files)} 個音檔")
    print(f"🌏 處理區域: {LOCATION}")
    print(f"🤖 使用模型: Chirp 3")
    print(f"{'='*60}\n")
    
    API_ENDPOINT = f"{LOCATION}-speech.googleapis.com"
    RECOGNIZER_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"
    client_options = ClientOptions(api_endpoint=API_ENDPOINT)
    client = speech_v2.SpeechClient(client_options=client_options)
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    
    success_count = 0
    fail_count = 0
    
    for idx, filename in enumerate(audio_files, 1):
        local_path = os.path.join(INPUT_FOLDER, filename)
        
        print(f"\n[{idx}/{len(audio_files)}] 處理: {filename}")
        
        if process_single_file(local_path, client, RECOGNIZER_NAME, storage_client, bucket):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n{'='*60}")
    print(f"📊 批次處理完成")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count} 個檔案")
    print(f"❌ 失敗: {fail_count} 個檔案")
    print(f"📂 結果已儲存至: {OUTPUT_FOLDER}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_batch_pipeline()