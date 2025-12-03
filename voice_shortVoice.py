import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

from google.cloud import speech
import wave
import contextlib

# 改這一行
audio_file_path = "TMRT_5minVoice_20251125.wav"

# 自動偵測取樣率
def get_sample_rate(filepath):
    if filepath.lower().endswith('.wav'):
        with contextlib.closing(wave.open(filepath, 'r')) as f:
            return f.getframerate()
    return 0

sample_rate = get_sample_rate(audio_file_path)
print(f"偵測到取樣率：{sample_rate} Hz")

# 自動判斷編碼
ext = os.path.splitext(audio_file_path)[1].lower()
if ext == ".mp3":
    encoding = speech.RecognitionConfig.AudioEncoding.MP3
elif ext == ".flac":
    encoding = speech.RecognitionConfig.AudioEncoding.FLAC
else:
    encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16

# 讀檔
with open(audio_file_path, "rb") as f:
    content = f.read()

# 檢查檔案大小（超過 10MB 會失敗）
file_size_mb = len(content) / (1024 * 1024)
print(f"檔案大小：{file_size_mb:.2f} MB")
if file_size_mb > 10:
    raise ValueError("檔案超過 10MB，請改用 Cloud Storage 的 long_running_recognize")

audio = speech.RecognitionAudio(content=content)

config = speech.RecognitionConfig(
    encoding=encoding,
    sample_rate_hertz=sample_rate,
    language_code="zh-TW",
    enable_automatic_punctuation=True,
    audio_channel_count=1,
)

client = speech.SpeechClient()
print("正在使用 LongRunningRecognize 處理約 5 分鐘音檔（會等 10~40 秒）...")

# 這就是關鍵：用 long_running_recognize
operation = client.long_running_recognize(config=config, audio=audio)
response = operation.result(timeout=300)   # 最多等 5 分鐘

print("\n=== 轉錄結果 ===\n")
with open("轉錄結果.txt", "w", encoding="utf-8") as f:
    for result in response.results:
        text = result.alternatives[0].transcript
        print(text)
        f.write(text.strip() + "\n")

print("\n成功！5 分鐘語音已完整轉錄，結果存成「轉錄結果.txt」")