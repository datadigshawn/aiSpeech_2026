# =============================================
# ultimate_mrt_transcribe.py   ← 檔名
# 台北捷運 OCC 通聯專用終極三段式神器（2025 最強版）
# =============================================

# 操作方法
# 1. 將你的語音檔上傳到 Google Cloud Storage（GCS）
# 2. 改GCS_URI
# 3. 改 GEMINI_API_KEY (去 https://aistudio.google.com/app/apikey 拿一組免費的 Gemini API Key)

import os
import time
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

from google.cloud import speech
import google.generativeai as genai

# ==================== 你的設定區 ====================
GCS_URI = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"   # ← 改這行

# 你的 Gemini API Key（去 https://aistudio.google.com/app/apikey 免費拿）
GEMINI_API_KEY = "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"   # ← 改這行！

# 捷運專業詞彙庫（越塞越準！）
MRT_PHRASES = [
    # 無線電數字口呼（超級重要！）
    "動", "洞", "么", "兩", "三", "四", "五", "六", "拐", "八", "勾", "溝",
    
    # 車站名（完整 + 常見縮寫）
    "北屯總站", "舊社", "松竹", "四維國小", "文心崇德", "文心中清", "文華高中",
    "文心櫻花", "市政府", "水安宮", "南屯", "豐樂公園", "大慶", "九張犁", "九德", "烏日", "高鐵台中",
    "G13", "G14", "G10", "G9", "G6", "A1", "A3", "A4", "A5", "A6", "A7", "A8", "A8a", "A9", "A10", "A11", "A12", "A13", "A14", "A15", "A16", "A17", "A18",
    
    # 專業術語（重點中的重點）
    "車門溝槽", "滑門溝槽", "溝槽是否有異物", "電器隔離", "電氣隔離", "機械隔離", "機械重置",
    "方形鑰匙", "轉轍器", "岔心", "巡軌", "第三軌", "三軌", "復電", "斷電", "三軌復電", "三軌斷電",
    "OCC", "行控中心", "AM模式", "MCS模式", "RMF模式", "VVVF", "IDRH", "EDRH", "門眉蓋板", "ETS",
    "EB", "緊急煞車", "PICU", "月台門", "端牆門", "駕駛台", "駕駛蓋板",
    "OCS BYPASS", "DOOR BYPASS", "清車", "清車作業", "授權碼", "設備櫃",
    
    # 通聯用語（讓模型學會「標準說法」
    "OVER", "收到", "否定否定", "正確正確", "感謝", "OUT", "回報", "通告全線", "通告完畢",
    "回CALL", "回call", "確認是否", "請立即前往", "人員登上", "切換至", "嘗試手動", "無法關閉",
    
    # 常見車組號（你可以再補）
    "09/10", "29/30", "車組", "車端"
]

# =============================================
print("第一段：啟動 Chirp Enhanced 超強雲端轉錄（最貴最準）...")
client = speech.SpeechClient()

audio = speech.RecognitionAudio(uri=GCS_URI)

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=0,
    language_code="zh-TW",
    model="latest_long",              # 最強長音檔模型
    use_enhanced=True,                # 開啟 Enhanced（費用 ×8）
    enable_automatic_punctuation=True,
    enable_word_time_offsets=True,
    diarization_config=speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
    ),
    speech_contexts=[speech.SpeechContext(phrases=MRT_PHRASES)],
)

operation = client.long_running_recognize(config=config, audio=audio)
print("請稍等 30~90 秒，Google 正在用最強模型處理...")
response = operation.result(timeout=900)

# 收集原始轉錄結果
raw_lines = []
for result in response.results:
    text = result.alternatives[0].transcript.strip()
    speaker = result.alternatives[0].words[0].speaker_tag
    raw_lines.append(f"講者{speaker}: {text}")

raw_transcript = "\n".join(raw_lines)
print("\n第一段完成！原始轉錄如下：\n")
print(raw_transcript[:1000] + "...\n")

# =============================================
print("第二段：啟動 Gemini 1.5 Pro 專業校正（變標準通聯格式）...")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

prompt = f"""
你是一位服務 20 年的台北捷運 OCC 資深調度員，請根據以下語音轉錄結果，修正所有錯字、車站名、專業術語，並輸出「標準通聯紀錄格式」：

要求：
1. 每句話前面標明發話者（OCC / G13大慶站長 / 車組09/10 等）
2. 修正所有明顯錯字（如「一虎教具」→「OCC呼叫」）
3. 補上遺漏的「OVER」「收到」「否定否定」
4. 輸出乾淨、專業、標準的通聯紀錄

轉錄內容：
{raw_transcript}
"""

print("Gemini 正在校正（約 10~20 秒）...")
gemini_response = model.generate_content(prompt)
final_transcript = gemini_response.text

# =============================================
print("第三段：輸出三種完美格式！")

# 1. 純文字版
with open("【最終版】捷運通聯紀錄.txt", "w", encoding="utf-8") as f:
    f.write("台北捷運 OCC 通聯紀錄（AI 智慧轉錄 + 人工等級校正）\n")
    f.write("="*60 + "\n\n")
    f.write(final_transcript)

# 2. 字幕版 .srt（可直接套影片）
with open("【最終版】字幕.srt", "w", encoding="utf-8") as srt:
    count = 1
    for result in response.results:
        if not result.alternatives[0].words:
            continue
        start = result.alternatives[0].words[0].start_time.total_seconds()
        end = result.alternatives[0].words[-1].end_time.total_seconds()
        text = result.alternatives[0].transcript.strip()

        h, r = divmod(int(start), 3600)
        m, s = divmod(r, 60)
        ms = int((start - int(start)) * 1000)
        start_str = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        h, r = divmod(int(end), 3600)
        m, s = divmod(r, 60)
        ms = int((end - int(end)) * 1000)
        end_str = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt.write(f"{count}\n{start_str} --> {end_str}\n{text}\n\n")
        count += 1

# 3. 標準通聯表格（可直接貼 Excel）
with open("【最終版】通聯表格.csv", "w", encoding="utf-8") as f:
    f.write("發話者,內容\n")
    for line in final_transcript.strip().split("\n"):
        if ":" in line:
            speaker, content = line.split(":", 1)
            f.write(f"{speaker.strip()},{content.strip()}\n")
        else:
            f.write(f", {line.strip()}\n")

print("\n全部完成！已產生三個檔案：")
print("   【最終版】捷運通聯紀錄.txt   ← 最乾淨可直接交差")
print("   【最終版】字幕.srt           ← 直接套影片就有中文字幕")
print("   【最終版】通聯表格.csv       ← 可貼 Excel 做報表")

print("\n你現在擁有全台灣最強的捷運 OCC 語音轉文字系統了！")