# 檔名：long_5min_auto_gcs.py   ← 直接存成這個名字
import os
import time
from google.cloud import speech
from google.cloud import storage

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

# ===== 只要改這一行 =====
audio_file_path = "TMRT_5minVoice_20251125.wav"
# ========================

# 自動建立 bucket（名字固定，第一次會建立，以後重複用）
bucket_name = "my-speech-auto-2025shawn"
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)
if not bucket.exists():
    bucket = storage_client.create_bucket(bucket_name, location="asia-east1")
    print(f"已自動建立儲存桶：{bucket_name}")

# 上傳音檔
blob = bucket.blob(os.path.basename(audio_file_path))
print("正在上傳音檔到 Google Cloud Storage...")
blob.upload_from_filename(audio_file_path)
gcs_uri = f"gs://{bucket_name}/{os.path.basename(audio_file_path)}"
print(f"上傳完成：{gcs_uri}")

# 開始長音檔轉錄
client = speech.SpeechClient()
audio = speech.RecognitionAudio(uri=gcs_uri)
config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=8000,      # 你這支就是 8000
    language_code="zh-TW",
    enable_automatic_punctuation=True,
)

print("已送出轉錄請求，5 分鐘音檔大約等 30~60 秒...")
operation = client.long_running_recognize(config=config, audio=audio)
response = operation.result(timeout=300)

# 輸出結果
print("\n=== 完整轉錄結果 ===\n")
with open("轉錄結果.txt", "w", encoding="utf-8") as f:
    for result in response.results:
        text = result.alternatives[0].transcript.strip()
        print(text)
        f.write(text + "\n")

# 自動刪除雲端音檔（省空間）
blob.delete()
print("\n成功！轉錄完成，已自動清理雲端音檔")
print("結果已存成「轉錄結果.txt」")