
# voice_GCS_V2_LONG.py
import os
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions

# 設定金鑰路徑
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

PROJECT_ID = "dazzling-seat-315406"

# 我們維持使用 us-central1，因為這是 Google 資源最多的機房
LOCATION = "us-central1"
API_ENDPOINT = f"{LOCATION}-speech.googleapis.com"

# Recognizer 路徑
RECOGNIZER_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"

gcs_uri = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"

# 初始化 Client
client = speech_v2.SpeechClient(
    client_options=ClientOptions(api_endpoint=API_ENDPOINT)
)

config = cloud_speech.RecognitionConfig(
    auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
    language_codes=["zh-TW"],
    
    # ⚠️ 修正：改用 "long" 模型
    # "long" 是 V2 API 中針對長語音辨識的標準模型
    # 它 100% 支援 zh-TW，且效果穩定
    model="long", 
    
    features=cloud_speech.RecognitionFeatures(
        enable_automatic_punctuation=True, # 自動標點
        enable_word_time_offsets=True,     # 時間戳記
    ),
)

file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)

request = cloud_speech.BatchRecognizeRequest(
    recognizer=RECOGNIZER_NAME,
    config=config,
    files=[file_metadata],
    recognition_output_config=cloud_speech.RecognitionOutputConfig(
        inline_response_config=cloud_speech.InlineOutputConfig(),
    ),
)

print(f"正在送出給 Google Speech V2 API（區域：{LOCATION}），請稍等...")
print(f"連線 Endpoint: {API_ENDPOINT}")
print("使用模型: long (標準長語音模型)")

try:
    operation = client.batch_recognize(request=request)
    print("雲端處理中...")
    
    # 設定 timeout 為 900 秒 (15分鐘)
    response = operation.result(timeout=900)

    # 輸出結果
    output_filename = "【Standard_Long】轉錄結果.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        for file_result in response.results.values():
            for result in file_result.transcript.results:
                best = result.alternatives[0]
                text = best.transcript.strip()
                confidence = best.confidence
                
                # 寫入檔案與螢幕輸出
                line = f"[{confidence:.1%}] {text}"
                f.write(line + "\n\n")
                print(line)

    print(f"\n✅ 轉錄成功！已產生 {output_filename}")

except Exception as e:
    print(f"\n❌ 發生錯誤: {e}")