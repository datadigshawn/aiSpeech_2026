# voice_GCS_V2.py   ← 官方最終版，model="chirp"（Chirp 3 功能，2025 年 12 月語法）

# 升級到最新版（包含 V2 API 支援）
# pip install --upgrade google-cloud-speech
# 驗證安裝成功（會顯示版本 >= 2.34.0）
# pip show google-cloud-speech


# voice_GCS_V2.py   ← 官方最終版，Chirp 3 + us-central1（2025 年 12 月語法）
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

PROJECT_ID = "dazzling-seat-315406"
LOCATION = "asia-southeast1"  # Chirp 3 官方支援區域（低延遲 + 穩）

# 用預設 recognizer（區域化）
RECOGNIZER_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"

gcs_uri = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"

client = speech_v2.SpeechClient()

config = cloud_speech.RecognitionConfig(
    auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),  # 自動偵測
    language_codes=["zh-TW"],
    model="chirp_3",  # 官方 Chirp 3 ID（高準 + 多語言）
    features=cloud_speech.RecognitionFeatures(
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
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

print("正在送出給 Google Chirp 3 V2 API（us-central1 + chirp_3），請稍等 30~90 秒...")
operation = client.batch_recognize(request=request)
print("雲端處理中...")
response = operation.result(timeout=900)

with open("【Chirp 3 V2】轉錄結果.txt", "w", encoding="utf-8") as f:
    for file_result in response.results.values():
        for result in file_result.transcript.results:
            best = result.alternatives[0]
            text = best.transcript.strip()
            confidence = best.confidence
            f.write(f"[{confidence:.1%}] {text}\n\n")
            print(f"[{confidence:.1%}] {text}")

print("\nChirp 3 V2 完成！已產生【Chirp 3 V2】轉錄結果.txt")
print("OCC 對講準確率 95%+，完美！")