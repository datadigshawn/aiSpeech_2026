# voice_local_whisper_optimized.py
import os
import time
import whisper
from datetime import timedelta

# ================= ⚙️ 設定區 =================
INPUT_FOLDER = "audio_input"           # 放音檔的資料夾
OUTPUT_FOLDER = "transcripts_Whisper"  # 存結果的資料夾
MODEL_TYPE = "large-v3"                   # M2 推薦用 turbo｜假如辨識度能不滿意，可以改用 large-v3

# 支援的檔案格式
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 🔧 優化策略：後處理字典 =================
# 這是您的核心需求：把聽錯的無線電術語強制修正回來
REPLACEMENT_RULES = {
    "歐西": "OCC",
    "哦西": "OCC",
    "護照": "呼叫",
    "立即致": "立即至",
    "洞溝": "09",   # 無線電特殊讀音
    "動勾": "09",
    "洞": "0",      # 單獨出現時
    "勾": "9",      # 單獨出現時
    "腰動": "10",
    "么洞": "10",
    "么": "1",
    "義務": "異物",
    "方行鑰匙": "方形鑰匙",
    "動物車門": "05車門",
    "動五": "05",
    "偷拜PASS": "Bypass",
    "百帕斯": "Bypass",
}

def post_process_text(text):
    """
    執行文字替換，將常見錯誤修正回來
    """
    # 1. 先執行字典替換
    for wrong, correct in REPLACEMENT_RULES.items():
        text = text.replace(wrong, correct)
    
    # 2. 額外的格式整理 (可選)
    # 比如把 "G 3" 的空白拿掉變成 "G3"
    text = text.replace("G 3", "G3").replace("G 10", "G10")
    
    return text.strip()

# =======================================================

def run_local_pipeline():
    # 1. 準備資料夾
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ 找不到輸入資料夾：{INPUT_FOLDER}")
        return
    
    files = [f for f in os.listdir(INPUT_FOLDER) if os.path.splitext(f)[1].lower() in SUPPORTED_EXT]
    files.sort()

    if not files:
        print("❌ 資料夾內沒有支援的音檔。")
        return

    # 2. 載入模型 (嘗試啟用 M2 GPU)
    print(f"🔄 載入 Whisper 模型 ({MODEL_TYPE})...")
    try:
        model = whisper.load_model(MODEL_TYPE, device="mps")
        print("⚡️ 成功啟用 M2 GPU 加速模式 (MPS)！")
    except Exception as e:
        print(f"⚠️ GPU 啟用失敗，切換回 CPU 模式: {e}")
        model = whisper.load_model(MODEL_TYPE)

    print(f"✅ 開始處理 {len(files)} 個檔案...\n")

    # 3. 執行辨識
    for i, filename in enumerate(files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        output_filename = os.path.splitext(filename)[0] + ".txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        print(f"▶️ [{i+1}/{len(files)}] 正在處理：{filename}")
        start_time = time.time()

        try:
            # === Whisper 辨識 ===
            # initial_prompt 是 Whisper 唯一能接受的「提示」
            # 我們把重要的關鍵字放在這裡，暗示模型
            result = model.transcribe(
                file_path,
                language="zh",
                initial_prompt="這是一段台灣捷運無線電通訊。術語包含：OCC行控中心, 呼叫, 立即至一月台, 09, 10, 異物, 方形鑰匙, 05車門, Bypass。"
            )

            # === 後處理修正 (Python 強制替換) ===
            raw_text = result["text"]
            refined_text = post_process_text(raw_text)

            # === 存檔 ===
            duration = time.time() - start_time
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(refined_text)
            
            print(f"   ✅ 完成！耗時: {str(timedelta(seconds=int(duration)))}")

        except Exception as e:
            print(f"   ❌ 處理失敗：{e}")

    print(f"\n🎉 全部完成！結果請查看：{OUTPUT_FOLDER}")

if __name__ == "__main__":
    run_local_pipeline()