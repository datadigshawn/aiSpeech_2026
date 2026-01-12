# 檔案位置 aiSpeech/scripts/batch_inference.py
import os
import sys
import time
from tqdm import tqdm # 進度條套件 (建議 pip install tqdm)

# 設定路徑：將上層目錄加入 path 才能 import utils
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 匯入我們剛寫好的模組
from scripts.model_whisper_old import transcribe_with_whisper
from utils.text_cleaner_old import fix_radio_jargon

# ================= ⚙️ 設定區 =================
# 指定目前的測試案資料夾
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), '..')
TEST_CASE = "Test_01_TMRT"   # 後續要跑其他語音情境，改資料夾名

# 輸入與輸出路徑
INPUT_DIR = os.path.join(PROJECT_ROOT, "experiments", TEST_CASE, "dataset_chunks")
OUTPUT_DIR_WHISPER = os.path.join(PROJECT_ROOT, "experiments", TEST_CASE, "ASR_Evaluation", "whisper_output")

# 支援格式
SUPPORTED_EXT = ('.wav', '.mp3', '.m4a')

def main():
    # 1. 檢查輸入資料夾
    if not os.path.exists(INPUT_DIR):
        print(f"❌ 找不到輸入資料夾: {INPUT_DIR}")
        return

    # 2. 建立輸出資料夾
    os.makedirs(OUTPUT_DIR_WHISPER, exist_ok=True)

    # 3. 掃描檔案
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(SUPPORTED_EXT)]
    files.sort()
    
    print(f"🚀 開始批次辨識 (Whisper Large-V3)")
    print(f"📂 輸入: {INPUT_DIR}")
    print(f"📂 輸出: {OUTPUT_DIR_WHISPER}")
    print(f"📊 總檔案數: {len(files)}\n")

    # 4. 執行迴圈
    for filename in tqdm(files, desc="Processing"):
        audio_path = os.path.join(INPUT_DIR, filename)
        output_txt_path = os.path.join(OUTPUT_DIR_WHISPER, os.path.splitext(filename)[0] + ".txt")

        # 若檔案已存在，可選擇跳過 (Optional)
        # if os.path.exists(output_txt_path):
        #     continue

        try:
            # A. 呼叫 Whisper 模組進行辨識
            # 這裡可以改參數 model_size="turbo" 或 "large-v3"
            raw_text = transcribe_with_whisper(audio_path, model_size="large-v3")

            # B. 呼叫 utils 進行術語修正 (Post-processing)
            final_text = fix_radio_jargon(raw_text)

            # C. 存檔
            with open(output_txt_path, "w", encoding="utf-8") as f:
                f.write(final_text)

        except Exception as e:
            print(f"\n❌ 錯誤 ({filename}): {e}")

    print("\n🎉 全部完成！")

if __name__ == "__main__":
    main()