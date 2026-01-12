# 語音上傳GCS+STT V2+Chirp 3模式 + 時間戳記輸出
# 執行前需確定虛擬環境升級到最新版 pip install --upgrade google-cloud-speech

import os
from google.cloud import storage
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions

# =========================參數設定區==========================   
# 1. 設定金鑰路徑（自動處理相對路徑）
# 取得當前程式所在的目錄
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 專案根目錄（scripts 的上一層）
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# 金鑰檔案名稱
KEY_FILENAME = "google-speech-key.json"

# 嘗試從多個位置尋找金鑰檔案
possible_key_paths = [
    os.path.join(PROJECT_ROOT, "utils", KEY_FILENAME),  # aiSpeech/utils/google-speech-key.json
    os.path.join(SCRIPT_DIR, KEY_FILENAME),  # aiSpeech/scripts/google-speech-key.json
    os.path.join(PROJECT_ROOT, KEY_FILENAME),  # aiSpeech/google-speech-key.json
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
LOCATION = "asia-northeast1"  # 使用支援 Chirp 模型的區域(東京)

# 3. 批次處理設定
INPUT_FOLDER = os.path.join(SCRIPT_DIR, "audio_input")  # 使用絕對路徑
OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "transcripts_output")  # 使用絕對路徑
SUPPORTED_FORMATS = {'.wav', '.mp3', '.m4a', '.flac'}  # 支援的音檔格式

# ==========================================================

def format_timestamp(seconds):
    """將秒數轉換為 [mm:ss.ms] 格式"""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"[{minutes:02d}:{secs:06.3f}]"

def process_single_file(local_filename, gcs_uri, client, recognizer_name):
    """處理單一音檔的轉錄"""
    base_name = os.path.splitext(os.path.basename(local_filename))[0]
    print(f"\n{'='*60}")
    print(f"📝 正在處理: {os.path.basename(local_filename)}")
    print(f"{'='*60}")
    
    # 先檢查音檔資訊
    try:
        import wave
        with wave.open(local_filename, 'rb') as wf:
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
            
            # 檢查是否符合 Google STT 建議規格
            if framerate not in [8000, 16000, 32000, 44100, 48000]:
                print(f"  ⚠️  警告: 採樣率 {framerate} Hz 可能不是最佳選擇")
                print(f"  💡 建議: 8000Hz (電話品質) 或 16000Hz (一般語音)")
    except Exception as e:
        print(f"  ⚠️  無法讀取 WAV 資訊: {e}")
        channels, framerate, sample_width = None, None, None

    # 根據檢測到的格式設定編碼
    if channels and framerate and sample_width:
        if sample_width == 2:  # 16-bit
            encoding = cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16
        elif sample_width == 1:  # 8-bit
            encoding = cloud_speech.ExplicitDecodingConfig.AudioEncoding.MULAW
        else:
            encoding = cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16
        
        # 使用明確的解碼設定取代 auto_decoding_config
        decoding_config = cloud_speech.ExplicitDecodingConfig(
            encoding=encoding,
            sample_rate_hertz=framerate,
            audio_channel_count=channels,
        )
        print(f"  🔧 使用編碼: {encoding.name}, {framerate}Hz, {channels}聲道")
    else:
        # 無法檢測時使用自動偵測
        decoding_config = cloud_speech.AutoDetectDecodingConfig()
        print(f"  🔧 使用自動偵測編碼")

    config = cloud_speech.RecognitionConfig(
        explicit_decoding_config=decoding_config if isinstance(decoding_config, cloud_speech.ExplicitDecodingConfig) else None,
        auto_decoding_config=decoding_config if isinstance(decoding_config, cloud_speech.AutoDetectDecodingConfig) else None,
        language_codes=["cmn-Hant-TW"],
        model="chirp_3", 
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,  # ⭐ 關鍵：啟用單字時間戳記
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
        csv_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_時間戳記.csv")
        
        with open(full_output, "w", encoding="utf-8") as f_full, \
             open(word_output, "w", encoding="utf-8") as f_word, \
             open(csv_output, "w", encoding="utf-8") as f_csv:
            
            # CSV 標題
            f_csv.write("開始時間(秒),結束時間(秒),時間標記,文字內容,信心分數\n")
            
            for file_result in response.results.values():
                if file_result.error.message:
                    print(f"❌ 轉錄錯誤: {file_result.error.message}")
                    continue
                
                for result in file_result.transcript.results:
                    best = result.alternatives[0]
                    transcript = best.transcript.strip()
                    confidence = best.confidence
                    
                    # 取得整段的時間範圍（若有 words 就用第一個和最後一個字的時間）
                    if best.words:
                        start_time = best.words[0].start_offset.total_seconds()
                        end_time = best.words[-1].end_offset.total_seconds()
                        time_label = f"{format_timestamp(start_time)} - {format_timestamp(end_time)}"
                        
                        # === 輸出 1: 完整逐字稿 ===
                        f_full.write(f"{time_label}\n")
                        f_full.write(f"[信心度: {confidence:.1%}] {transcript}\n\n")
                        
                        # === 輸出 2: 單字層級時間戳 ===
                        f_word.write(f"\n{time_label} - 完整句:\n{transcript}\n\n")
                        f_word.write("單字時間戳記:\n")
                        
                        for word_info in best.words:
                            word = word_info.word
                            w_start = word_info.start_offset.total_seconds()
                            w_end = word_info.end_offset.total_seconds()
                            w_time = format_timestamp(w_start)
                            
                            f_word.write(f"  {w_time} {word}\n")
                        
                        f_word.write("-" * 50 + "\n")
                        
                        # === 輸出 3: CSV 結構化資料 ===
                        # 將標點符號中的逗號替換為分號，避免破壞CSV格式
                        safe_transcript = transcript.replace(",", "；")
                        f_csv.write(f"{start_time:.3f},{end_time:.3f},{time_label},{safe_transcript},{confidence:.4f}\n")
                        
                        # 終端預覽
                        print(f"  {time_label} {transcript[:40]}...")
                    
                    else:
                        # 若無單字時間資訊（極少見），使用基本格式
                        f_full.write(f"[無時間戳] [{confidence:.1%}] {transcript}\n\n")

        print(f"✅ 轉錄完成！")
        print(f"  📄 {os.path.basename(full_output)}")
        print(f"  📄 {os.path.basename(word_output)}")
        print(f"  📊 {os.path.basename(csv_output)}")
        
        return True

    except Exception as e:
        print(f"❌ 轉錄失敗: {e}")
        return False


def run_batch_pipeline():
    """批次處理資料夾內的所有音檔"""
    
    # 1. 檢查輸入資料夾
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ 找不到輸入資料夾: {INPUT_FOLDER}")
        print(f"💡 請建立 '{INPUT_FOLDER}' 資料夾並放入音檔")
        return
    
    # 2. 掃描所有支援的音檔
    audio_files = [
        f for f in os.listdir(INPUT_FOLDER)
        if os.path.splitext(f)[1].lower() in SUPPORTED_FORMATS
    ]
    
    if not audio_files:
        print(f"❌ 在 '{INPUT_FOLDER}' 中找不到支援的音檔")
        print(f"💡 支援格式: {', '.join(SUPPORTED_FORMATS)}")
        return
    
    audio_files.sort()  # 按檔名排序
    
    print(f"\n{'='*60}")
    print(f"🚀 批次處理模式")
    print(f"{'='*60}")
    print(f"📂 輸入資料夾: {INPUT_FOLDER}")
    print(f"📂 輸出資料夾: {OUTPUT_FOLDER}")
    print(f"📊 找到 {len(audio_files)} 個音檔")
    print(f"🌏 處理區域: {LOCATION}")
    print(f"🤖 使用模型: Chirp 3")
    print(f"{'='*60}\n")
    
    # 3. 設定 Google Cloud 連線（只需建立一次）
    API_ENDPOINT = f"{LOCATION}-speech.googleapis.com"
    RECOGNIZER_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"
    client_options = ClientOptions(api_endpoint=API_ENDPOINT)
    client = speech_v2.SpeechClient(client_options=client_options)
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    
    # 4. 批次處理每個檔案
    success_count = 0
    fail_count = 0
    
    for idx, filename in enumerate(audio_files, 1):
        local_path = os.path.join(INPUT_FOLDER, filename)
        gcs_filename = f"batch_{idx}_{filename}"
        gcs_uri = f"gs://{BUCKET_NAME}/{gcs_filename}"
        
        print(f"\n[{idx}/{len(audio_files)}] 處理: {filename}")
        
        # 上傳到 GCS
        try:
            print(f"  ☁️  上傳至 Cloud Storage...")
            blob = bucket.blob(gcs_filename)
            blob.upload_from_filename(local_path)
            print(f"  ✅ 上傳完成")
        except Exception as e:
            print(f"  ❌ 上傳失敗: {e}")
            fail_count += 1
            continue
        
        # 轉錄處理
        if process_single_file(local_path, gcs_uri, client, RECOGNIZER_NAME):
            success_count += 1
        else:
            fail_count += 1
        
        # 清理 GCS 上的暫存檔（可選）
        try:
            blob.delete()
            print(f"  🗑️  已清理 GCS 暫存檔")
        except:
            pass
    
    # 5. 輸出總結報告
    print(f"\n{'='*60}")
    print(f"📊 批次處理完成")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count} 個檔案")
    print(f"❌ 失敗: {fail_count} 個檔案")
    print(f"📂 結果已儲存至: {OUTPUT_FOLDER}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    run_batch_pipeline()