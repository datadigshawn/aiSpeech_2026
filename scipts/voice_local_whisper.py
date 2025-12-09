#  安裝 openai-whisper.  , pip install openai-whisper | 或是為Apple Silicon優化的 mix-whisper
# 還需要安裝 ffmpeg (用 brew install ffmpeg)

import os
import time
import whisper
import re
from datetime import timedelta

# ================= ⚙️ 設定區 =================
INPUT_FOLDER = "audio_input"       # 放音檔的資料夾
OUTPUT_FOLDER = "transcripts_Whisper" # 存結果的資料夾
MODEL_TYPE = "turbo"               # M2 推薦用 turbo (速度快且準)，若要最高準度可用 large-v3

# 支援的檔案格式
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 🔧 模擬 Gemini 的術語修正邏輯 =================
# 這裡對應您原本 Prompt 中的 "Reference Glossary"
# 雖然 Whisper 聽力很好，但無線電雜訊多時仍建議強制修正
def post_process_transcript(text):
    # 1. 站名與代號修正 [參考您的 Gemini 規則]
    text = text.replace("巨三", " G3 ")
    text = text.replace("居三", " G3 ")
    text = text.replace("居十", " G10 ")
    text = text.replace("居一", " G1 ")
    
    # 2. 專業術語修正 
    text = text.replace("車主", "車組")
    text = text.replace("偷拜PASS", " Bypass ")
    text = text.replace("偷拜pass", " Bypass ")
    text = text.replace("百帕斯", " Bypass ")
    text = text.replace("哦西", " OCC ")
    text = text.replace("阿M", " RM ") # 或 AM，視情境
    
    # 3. 數字口呼修正 (Whisper 通常會直接轉成阿拉伯數字，這裡做防呆)
    #  0=洞, 1=么, 2=兩, 7=拐, 9=勾
    # 範例：若它打成國字，我們轉回數字，或根據需求保留
    text = text.replace("動勾", " 09 ")
    text = text.replace("洞勾", " 09 ")
    text = text.replace("么兩", " 12 ")
    
    # 移除多餘的空白
    return text.strip()

# ===============================================================

def run_local_pipeline():
    # 1. 建立輸出資料夾
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # 2. 掃描檔案
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ 找不到輸入資料夾：{INPUT_FOLDER}，請建立後放入音檔！")
        return
    
    files = [f for f in os.listdir(INPUT_FOLDER) if os.path.splitext(f)[1].lower() in SUPPORTED_EXT]
    files.sort()  # 排序，讓處理順序固定

    total_files = len(files)
    if total_files == 0:
        print(f"❌ 輸入資料夾中沒有支援的音檔格式：{SUPPORTED_EXT}，請放入音檔後再試！")
        return
    
    # 3. 載入模型
    print(f"🔄 載入 Whisper 模型 ({MODEL_TYPE})...(M2晶片加速中)")
    try:
        # ✅ 強制指定使用 mps (Mac 的 GPU 加速指令)
        model = whisper.load_model(MODEL_TYPE, device="mps") 
        print("⚡️ 成功啟用 M2 GPU 加速模式 (MPS)！")
    except Exception as e:
        print(f"⚠️ GPU 啟用失敗，切換回 CPU 模式 (錯誤: {e})")
        model = whisper.load_model(MODEL_TYPE) # 失敗時的回退方案
    
    print(f"✅ 模型載入成功！開始處理 {total_files} 個音檔...\n")

    # 4. 處理迴圈
    for i, filename in enumerate(files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        output_filename = os.path.splitext(filename)[0] + ".txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        print(f"▶️ [{i+1}/{total_files}] 正在處理：{filename}")
        start_time = time.time()

        try:
            # === 辨識核心===
            # initial_prompt：給模型暗示，讓他知道這是捷運無線電，提高專有名詞辨識率
            # 這裡加入提供的關鍵字
            result = model.transcribe(
                file_path,
                language="zh",
                initial_prompt="這是一段台灣捷運的無線電通訊錄音, 內容包含術語: OCC行控中心, G3舊社站, G10水安宮站, 車組, Bypass, RMF模式, ETS, 09/10, 么兩, 洞勾。"
            )

            # === 後處理（模擬Gemini的規則修正) ===
            original_text = result["text"]
            refined_text = post_process_transcript(original_text)

            # === 計算耗時 ===
            duration = time.time() - start_time
            duration_str = str(timedelta(seconds=int(duration)))

            # === 存檔 ===
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(refined_text)
            
            print(f"   ✅ 完成！耗時: {duration_str}，存檔為：{output_filename}\n")

            # (可選) 顯示前 50 個字預覽
            # print(f"      預覽: {refined_text[:50]}...")
        
        except Exception as e:
            print(f"   ❌ 處理失敗：{e}\n")

    print(f"// 全部處理完成！結果存放在資料夾：{OUTPUT_FOLDER} 資料夾")


if __name__ == "__main__":
    run_local_pipeline()