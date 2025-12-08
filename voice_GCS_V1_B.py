# voice_GCS_V1_STABLE.py
import os
from google.cloud import speech

# 設定金鑰路徑
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

gcs_uri = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"

def transcribe_gcs_v1(gcs_uri):
    # 1. 使用 V1 Client (不再是 speech_v2)
    client = speech.SpeechClient()

    # 2. 設定音訊來源
    audio = speech.RecognitionAudio(uri=gcs_uri)

    # 3. 設定參數
    # V1 對於 WAV 檔案，通常可以不指定 encoding 與 sample_rate，它會自動讀檔頭
    config = speech.RecognitionConfig(
        language_code="zh-TW",          # 繁體中文
        enable_automatic_punctuation=True, # 自動標點
        enable_word_time_offsets=True,     # 時間戳記
        # model="default",              # V1 使用預設模型即可，最穩
    )

    print("正在送出給 Google Speech V1 API (LongRunning)...")
    print(f"檔案: {gcs_uri}")

    # 4. 發送長語音辨識請求 (非同步)
    operation = client.long_running_recognize(config=config, audio=audio)

    print("雲端處理中 (V1 API)...")
    
    # 5. 等待結果 (timeout 900秒)
    response = operation.result(timeout=900)

    # 6. 輸出結果
    output_filename = "【V1_Stable】轉錄結果.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        for result in response.results:
            # V1 的結構稍微不同，直接取 alternatives[0]
            best = result.alternatives[0]
            text = best.transcript.strip()
            confidence = best.confidence
            
            line = f"[{confidence:.1%}] {text}"
            f.write(line + "\n\n")
            print(line)

    print(f"\n✅ V1 轉錄成功！已產生 {output_filename}")

if __name__ == "__main__":
    try:
        transcribe_gcs_v1(gcs_uri)
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")