import os
import time
import google.generativeai as genai

#========================參數設定區==========================
# 1. 設定 API Key
genai.configure(api_key="AIzaSyC6qkLuKrlmzN6KC4I4WAV7uUhweD9LxH0") 

# 2. 資料夾設定
INPUT_FOLDER = "audio_input"   
OUTPUT_FOLDER = "transcripts_Gemini" 

# 【關鍵修改 1】建議改用 1.5-pro，它對「說話者分離」的指令執行力比 Flash 好很多
# 如果您一定要用 Flash，請改回 "models/gemini-2.0-flash"，但效果可能不如 Pro
MODEL_NAME = "models/gemini-1.5-pro" 

# 3. 支援的音檔格式
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# 【關鍵修改 2】設定生成參數，降低隨機性，強迫遵守格式
generation_config = {
    "temperature": 0.1,  # 越低越死板，越容易遵守格式
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

# ================= 強化版 Prompt (劇本模式) =================
SYSTEM_INSTRUCTION = """
你是一位嚴格的「法庭速記員」。你的任務是將捷運無線電錄音轉錄為「對話劇本格式」。

【極重要規則 - 違反將導致任務失敗】：
1. **絕對禁止**將對話合併為一個段落。每一句話都必須**換行**。
2. **必須**辨識不同的說話者。音訊中只有兩個人（通常是「行控」與「現場人員」）。
3. 根據語氣和內容判斷角色。下指令、確認位置、語氣較平穩者通常為 [行控]；回報狀況、語氣較急促或有背景音者通常為 [現場]。若無法判斷，請使用 [說話者A] 與 [說話者B]。

【專業術語修正表】:
- 「洞/動」-> 0, 「么/搖」-> 1, 「兩」-> 2, 「拐」-> 7, 「勾」-> 9
- 「巨三/居三」 -> 「G3」
- 「偷拜PASS/百帕斯」 -> 「Bypass」
- 「哦西」 -> 「OCC」

【強制輸出格式範例】：
[說話者A]: 呼叫車組，請確認位置。
[說話者B]: 收到，目前位置 G3。
[說話者A]: 了解，請繼續作業。
(請嚴格依照此格式，一句一行)
"""

PROMPT_TEXT = "請開始轉錄，嚴格區分說話者並換行。"
# ========================================================

def process_batch():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    all_files = os.listdir(INPUT_FOLDER)
    audio_files = [f for f in all_files if os.path.splitext(f)[1].lower() in SUPPORTED_EXT]
    audio_files.sort() 

    total_files = len(audio_files)
    print(f"📂 偵測到 {total_files} 個音檔，準備使用 {MODEL_NAME} 處理...\n")

    # 初始化模型時帶入 generation_config
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config=generation_config,
        system_instruction=SYSTEM_INSTRUCTION # 建議將 System Prompt 放在這裡
    )

    for index, filename in enumerate(audio_files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        print(f"▶️ [{index+1}/{total_files}] 正在處理：{filename}")

        try:
            print(f"   (1/3) 上傳中...", end="", flush=True)
            audio_file = genai.upload_file(path=file_path)
            
            print(f" -> 等待轉碼...", end="", flush=True)
            while audio_file.state.name == "PROCESSING":
                time.sleep(1)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name != "ACTIVE":
                print(f"\n❌ {filename} 處理失敗")
                continue

            print(f" -> (2/3) AI 辨識中...", end="", flush=True)
            
            # 發送請求 (System Prompt 已在模型初始化時設定，這裡只需傳送 User Prompt 和 音檔)
            response = model.generate_content([PROMPT_TEXT, audio_file])
            
            output_filename = os.path.splitext(filename)[0] + ".txt"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            print(f" -> (3/3) ✅ 完成！")
            audio_file.delete()

        except Exception as e:
            print(f"\n❌ 錯誤：{e}")
        
        time.sleep(2) 

    print(f"\n🎉 處理完成！")

if __name__ == "__main__":
    process_batch()