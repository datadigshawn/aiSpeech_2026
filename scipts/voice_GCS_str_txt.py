import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

from google.cloud import speech

gcs_uri = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"

client = speech.SpeechClient()

audio = speech.RecognitionAudio(uri=gcs_uri)

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=0,                    # 讓 Google 自動偵測
    language_code="zh-TW",
    enable_automatic_punctuation=True,
    enable_word_time_offsets=True,
    # ───────────────────────────────
    # 這兩行是新版正確寫法（講者分離）
    diarization_config=speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        # min_speaker_count=1,    # 這兩行可選，Google 會自動判斷人數
        # max_speaker_count=5,
    ),
    # ───────────────────────────────
)

print("正在送出 5 分鐘音檔到 Google 雲端轉錄（約 30~90 秒）...")
operation = client.long_running_recognize(config=config, audio=audio)
print("請稍等，雲端處理中...")
response = operation.result(timeout=600)

# 輸出 .txt + .srt（含講者標記）
with open("轉錄結果.txt", "w", encoding="utf-8") as txt, \
     open("轉錄結果.srt", "w", encoding="utf-8") as srt:

    count = 1
    for result in response.results:
        transcript = result.alternatives[0].transcript.strip()
        words = result.alternatives[0].words

        speaker_tag = words[0].speaker_tag
        speaker = f"講者{speaker_tag}" if speaker_tag > 0 else "未知講者"

        def fmt(sec):
            if not sec:
                return "00:00:00,000"
            s = int(sec)
            ms = int((sec - s) * 1000)
            return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d},{ms:03d}"

        start = words[0].start_time.total_seconds()
        end = words[-1].end_time.total_seconds()

        txt.write(f"{speaker}: {transcript}\n\n")
        srt.write(f"{count}\n")
        srt.write(f"{fmt(start)} --> {fmt(end)}\n")
        srt.write(f"{transcript}\n\n")
        count += 1

print("成功！已產生：")
print("   轉錄結果.txt")
print("   轉錄結果.srt（含講者標記與時間軸）")