# voice_local_whisper_optimized.py
import os
import time
import whisper
from datetime import timedelta

# ================= ⚙️ 設定區 =================
INPUT_FOLDER = "audio_input"           # 放音檔的資料夾
OUTPUT_FOLDER = "transcripts_Whisper"  # 存結果的資料夾
MODEL_TYPE = "medium"                # turbo 不擅長處理無線電的噪音 |large-v3太容易腦補且很慢 ｜先改用medium

# 支援的檔案格式
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 🔧 優化策略：後處理字典 =================
REPLACEMENT_RULES = {
    "歐西": "OCC", "哦西": "OCC", "護照": "呼叫", "立即致": "立即至",
    "洞溝": "09", "動勾": "09", "洞": "0", "勾": "9", "腰動": "10",
    "么洞": "10", "么": "1", "義務": "異物","方行鑰匙": "方形鑰匙",
    "動物車門": "05車門", "動五": "05","偷拜PASS": "Bypass",
    "百帕斯": "Bypass", "巨山": "G3", "大清": "大慶"
}

# === 後處理文字，修正常見錯誤 ===
def post_process_text(text):
    for wrong, correct in REPLACEMENT_RULES.items():
        text = text.replace(wrong, correct)
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

    # 2. 載入模型
    print(f"🔄 載入 Whisper 模型 ({MODEL_TYPE})...")
    try:
        # 強制使用 MPS (Mac GPU)
        model = whisper.load_model(MODEL_TYPE, device="mps")
        print("⚡️ 成功啟用 M2 GPU 加速模式 (MPS)！")
    except Exception as e:
        print(f"⚠️ GPU 啟用失敗，切換回 CPU 模式: {e}")
        model = whisper.load_model(MODEL_TYPE)

    print(f"✅ 開始處理 {len(files)} 個檔案 (Large-v3 高準度模式)...\n")

    # 3. 執行辨識
    for i, filename in enumerate(files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        output_filename = os.path.splitext(filename)[0] + ".txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        print(f"▶️ [{i+1}/{len(files)}] 正在處理：{filename}")
        start_time = time.time()

        try:
            # === Whisper 辨識 (針對 M2 效能優化版) ===
            result = model.transcribe(
                file_path,
                language="zh",
                # 縮短提示詞來降低干擾
                initial_prompt="無線電通訊：OCC, G13大慶, 09/10, 05車門, Bypass",

                # ✅ 避免模型在靜音處鬼打牆 (重要！), 不依賴前文，每段獨立辨識
                condition_on_previous_text=False,
                
                # ✅ 降低隨機性
                temperature=0,
                
                # （核心關鍵）壓縮率門檻
                # 當模型開始鬼打牆重複一句話時，gzip壓縮率會變高，設定更嚴格(1.5)，一旦發現重複就強制斷開，不會讓他持續跑, 稍微放寬
                compression_ratio_threshold=2.0,

                # ✅ 靜音過濾：提高門檻(防止把雜訊當成話來辨識), 原0.6可能太低而致漏字，下調至0.5
                no_speech_threshold=0.5,

                # ✅ 對數機率門檻：過濾不確定的結果, 從-1調整到-0.8，讓模型更嚴格篩選
                logprob_threshold=-0.8,

                # ✅ VAD(語音活動檢測)參數
                vad_filter=True, # 開啟VAD過濾
                vad_parameters={
                    "threshold": 0.3,  # 靜音門檻，降低到0.3以捕捉較輕微的語音
                    "min_speech_duration_ms": 100,  #最短語音長度
                },


                # ✅ 設定 beam search 來增加搜索寬度提高準確度｜若是運算過重導致卡死再棄用
                beam_size=5,  # 默認是5，可試8或10看效果
                best_of=5,   # 取最佳結果

                # ✅ M2 加速設定
                fp16=True,

                # ✅ 顯示即時進度 (讓你知道程式有在跑)
                verbose=False
            )

            # === 後處理修正 ===
            raw_text = result["text"]
            refined_text = post_process_text(raw_text)

            # 簡單檢查：如果字數爆炸多（超過5000字），通常壞掉了
            if len(refined_text) > 5000:
                print("⚠️ 警告：產出的文字過長，可能發生重複迴圈，請檢查檔案。")

            # === 存檔 ===
            duration = time.time() - start_time
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(refined_text)
            
            print(f"   ✅ 完成！耗時: {str(timedelta(seconds=int(duration)))}")

        except Exception as e:
            print(f"   ❌ 處理失敗：{e}")

    print(f"\n🎉 全部完成！結果請查看：{OUTPUT_FOLDER}")

def remove_repetitions(text, max_repeat=3):
    """移除明顯的重複句子"""
    sentences = text.split('。')
    result = []
    prev_sentence = ""
    repeat_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # 檢查是否與前一句相同或高度相似
        if sentence == prev_sentence:
            repeat_count += 1
            if repeat_count >= max_repeat:
                continue  # 跳過重複
        else:
            repeat_count = 0
            
        result.append(sentence)
        prev_sentence = sentence
    
    return '。'.join(result) + '。' if result else ""

if __name__ == "__main__":
    run_local_pipeline()