# 不需要安裝google speech-to-text, 而是改安裝google-generativeai
# pip install -U google-generativeai

# 設計一回圈來處理複數檔案，在專案資料夾中，建立一個新資料夾叫做 audio_input。
# 將複數檔案（.wav, .mp3, .m4a 等）全部丟進去。
# 建立一個新資料夾叫做 transcripts (用來存結果)。

import os
import time
import glob
import google.generativeai as genai

#========================參數設定區==========================
# 1. 設定 API Key
# 設定 API Key (去 Google AI Studio 申請)
# 登入Google AI Studio API key管理頁面, https://aistudio.google.com/app/apikey
genai.configure(api_key="AIzaSyC6qkLuKrlmzN6KC4I4WAV7uUhweD9LxH0") 

# 2. 資料夾設定
INPUT_FOLDER = "audio_input"   # 放音檔的地方
OUTPUT_FOLDER = "transcripts_Germini"  # 存逐字稿的地方
MODEL_NAME = "models/gemini-2.0-flash" # 使用最快最便宜的模型

# 3. 支援的音檔格式
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 捷運專業術語 Prompt (含說話者辨識) =================
SYSTEM_INSTRUCTION = """
你是一位專業的「捷運無線電通訊」聽寫專家。請將音訊轉錄為繁體中文逐字稿。
這段錄音包含捷運操作術語、數字代碼與中英夾雜的指令，且**有兩位說話者**在對話。

請嚴格遵守以下辨識規則：

1. 【說話者辨識 (Speaker Diarization)】:
   - 錄音中有 2 位不同的說話者。
   - 請務必區分聲音特徵，並在每一句對話前標示 **[說話者 1]** 或 **[說話者 2]**。
   - 如果你能從對話內容明確判斷角色（例如：行控中心/OCC vs 司機員/車組），請直接用角色名稱標示。
   - 輸出格式範例：
     [行控中心]: 呼叫車組，請確認位置。
     [車組]: 收到，目前位置 G3。

2. 【數字唸法修正】:
   - 「洞/動」-> 0, 「么/搖」-> 1, 「兩」-> 2, 「拐」-> 7, 「勾」-> 9
   - 範例：「車組動勾搖動」 -> 「車組 0910」

3. 【站名與代號】:
   - 「巨三/居三」 -> 「G3」(舊社站)
   - 「居十」 -> 「G10」(水安宮站)
   - 「居十三」 -> 「G13」(大慶站)

4. 【專業術語】:
   - 「偷拜PASS/百帕斯」 -> 「Bypass」
   - 「哦西」 -> 「OCC」
   - 「阿M」 -> 「RM」或「AM」模式
   - 「車主」 -> 「車組」

5. 【格式要求】:
   - 請輸出完整對話，不要摘要。
   - 每一行都必須有說話者標籤。
"""

PROMPT_TEXT = "請依照上述規則，區分兩位說話者並轉錄為精確的逐字稿。"
# ========================================================

def process_batch():
    # 確保輸出資料夾存在
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    # 取得所有音檔
    all_files = os.listdir(INPUT_FOLDER)
    audio_files = [f for f in all_files if os.path.splitext(f)[1].lower() in SUPPORTED_EXT]
    audio_files.sort() # 排序，讓處理順序固定

    total_files = len(audio_files)
    print(f"📂 偵測到 {total_files} 個音檔，準備開始批次處理...\n")

    model = genai.GenerativeModel(MODEL_NAME)

    for index, filename in enumerate(audio_files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        print(f"▶️ [{index+1}/{total_files}] 正在處理：{filename}")

        try:
            # 1. 上傳
            print(f"   (1/3) 上傳中...", end="", flush=True)
            audio_file = genai.upload_file(path=file_path)
            
            # 2. 等待處理
            print(f" -> 等待轉碼...", end="", flush=True)
            while audio_file.state.name == "PROCESSING":
                time.sleep(1)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name != "ACTIVE":
                print(f"\n❌ {filename} 處理失敗 (狀態: {audio_file.state.name})")
                continue

            # 3. 辨識
            print(f" -> (2/3) AI 辨識中...", end="", flush=True)
            # 將 Prompt 組合送出
            response = model.generate_content([SYSTEM_INSTRUCTION, PROMPT_TEXT, audio_file])
            
            # 4. 存檔
            output_filename = os.path.splitext(filename)[0] + ".txt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            print(f" -> (3/3) ✅ 完成！存檔為：{output_filename}")

            # 5. 清理雲端暫存檔 (重要！避免免費額度爆掉或檔案堆積)
            audio_file.delete()

        except Exception as e:
            print(f"\n❌ 處理 {filename} 時發生錯誤：{e}")
        
        # 稍微休息一下，避免觸發 API 頻率限制 (雖然 Flash 限制很寬鬆)
        time.sleep(1)

    print(f"\n🎉 全部 {total_files} 個檔案處理完成！請查看 '{OUTPUT_FOLDER}' 資料夾。")

if __name__ == "__main__":
    process_batch()