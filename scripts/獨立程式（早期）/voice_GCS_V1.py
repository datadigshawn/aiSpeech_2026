import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"
from google.cloud import speech

gcs_uri = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"

# ================== 捷運專業詞彙庫（獨立定義） ==================
MRT_PHRASES = [
    # 無線電數字口呼
    "動", "洞", "么", "兩", "三", "四", "五", "六", "拐", "八", "勾", "溝",
    # 車站名
    "北屯總站", "舊社", "松竹", "四維國小", "文心崇德", "文心中清", "文華高中",
    "文心櫻花", "市政府", "水安宮", "南屯", "豐樂公園", "大慶", "九張犁", "九德", "烏日", "高鐵台中",
    "G13", "G14", "G10", "G9", "G6", "A1", "A3", "A4", "A5", "A6", "A7", "A8", "A8a", "A9", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18",
    # 專業術語
    "車門溝槽", "滑門溝槽", "溝槽是否有異物", "電器隔離", "電氣隔離", "機械隔離", "機械重置",
    "方形鑰匙", "轉轍器", "岔心", "巡軌", "第三軌", "三軌", "復電", "斷電", "三軌復電", "三軌斷電",
    "OCC", "行控中心", "AM模式", "MCS模式", "RMF模式", "VVVF", "IDRH", "EDRH", "門眉蓋板", "ETS",
    "EB", "緊急煞車", "PICU", "月台門", "端牆門", "駕駛台", "駕駛蓋板",
    "OCS BYPASS", "DOOR BYPASS", "清車", "清車作業", "授權碼", "設備櫃",
    # 通聯用語
    "OVER", "收到", "否定否定", "正確正確", "感謝", "OUT", "回報", "通告全線", "通告完畢",
    "回CALL", "回call", "確認是否", "請立即前往", "人員登上", "切換至", "嘗試手動", "無法關閉",
    # 車組
    "09/10", "29/30", "車組", "車端"
]

client = speech.SpeechClient()
audio = speech.RecognitionAudio(uri=gcs_uri)

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=0,
    language_code="zh-TW",
    model="latest_long",  # V1 最強長音檔模型（Chirp-like 準確率，支援詞庫）
    # use_enhanced=True,  # 可選：開啟增強（費用 ×8，準到 99%）
    enable_automatic_punctuation=True,
    enable_word_time_offsets=True,
    diarization_config=speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        # min_speaker_count=1,  # 可選
        # max_speaker_count=5,
    ),
    # 關鍵：詞庫正確寫法（boost=18 讓模型「硬猜」這些詞）
    speech_contexts=[
        speech.SpeechContext(
            phrases=MRT_PHRASES,
            boost=18.0  # 超強加權（官方上限 20）
        )
    ],
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
        if not words:  # 防空
            continue
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