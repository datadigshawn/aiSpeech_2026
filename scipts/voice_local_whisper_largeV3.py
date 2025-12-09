import os
import time
import whisper
from datetime import timedelta

# ================= ⚙️ 設定區 =================
INPUT_FOLDER = "audio_input"
OUTPUT_FOLDER = "transcripts_Whisper"
MODEL_TYPE = "large-v3"  # 建議先用 medium，準確度高且速度快
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 🔧 後處理字典 =================
REPLACEMENT_RULES = {
    "歐西": "OCC", "哦西": "OCC", "護照": "呼叫", 
    "立即致": "立即至", "洞溝": "09", "動勾": "09", 
    "洞": "0", "勾": "9", "腰動": "10", "么洞": "10", 
    "么": "1", "動五": "05", "動武": "05",
    "聚山": "G13", "巨山": "G13", "G3大慶": "G13大慶",
    "大清": "大慶", "舊車": "舊社", "舊設": "舊社",
    "百帕子": "Bypass", "偷拜PASS": "Bypass", "OCS百帕斯": "OCS Bypass",
    "通告要動": "09/10", "車主通告要動": "車組09/10",
    "通過要動": "09/10", "車主通過要動": "車組09/10",
    "聚山": "G13", "九張離站": "九張犁站",
    "山軌": "三軌", "布含": "不含",
}

def post_process_text(text):
    """後處理文字"""
    for wrong, correct in REPLACEMENT_RULES.items():
        text = text.replace(wrong, correct)
    return text.strip()

def remove_repetitions(text, max_repeat=2):
    """移除重複片段"""
    # 方法1：按句號分割
    sentences = [s.strip() for s in text.split('。') if s.strip()]
    
    result = []
    prev = ""
    count = 0
    
    for sent in sentences:
        if sent == prev:
            count += 1
            if count < max_repeat:
                result.append(sent)
        else:
            result.append(sent)
            count = 0
        prev = sent
    
    return '。'.join(result) + '。'

def run_local_pipeline():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ 找不到輸入資料夾：{INPUT_FOLDER}")
        return
    
    files = [f for f in os.listdir(INPUT_FOLDER) 
             if os.path.splitext(f)[1].lower() in SUPPORTED_EXT]
    files.sort()
    
    if not files:
        print("❌ 資料夾內沒有支援的音檔。")
        return
    
    print(f"🔄 載入 Whisper 模型 ({MODEL_TYPE})...")
    try:
        model = whisper.load_model(MODEL_TYPE, device="mps")
        print("⚡️ 成功啟用 M2 GPU 加速！")
    except Exception as e:
        print(f"⚠️ GPU 啟用失敗: {e}")
        model = whisper.load_model(MODEL_TYPE)
    
    print(f"✅ 開始處理 {len(files)} 個檔案...\n")
    
    for i, filename in enumerate(files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        output_filename = os.path.splitext(filename)[0] + "_fixed.txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        print(f"▶️ [{i+1}/{len(files)}] {filename}")
        start_time = time.time()
        
        try:
            # 🔥 針對 nightly 版本的最佳參數組合
            result = model.transcribe(
                file_path,
                
                # 基礎設定
                language="zh",
                task="transcribe",
                
                # 防重複核心參數
                condition_on_previous_text=False,  # 🔥 最關鍵
                temperature=0.0,
                compression_ratio_threshold=2.4,   # 稍微放寬
                
                # 靜音處理
                no_speech_threshold=0.6,
                logprob_threshold=-1.0,
                
                # Prompt（簡短精準）
                initial_prompt="OCC G13 09 10 05 Bypass",
                
                # 性能
                fp16=True,
                verbose=False
            )
            
            # 後處理
            text = result["text"]
            text = post_process_text(text)
            text = remove_repetitions(text)
            
            # 儲存
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            
            duration = time.time() - start_time
            print(f"   ✅ 完成 ({int(duration)}秒)")
            print(f"   📝 字數: {len(text)}")
            
        except Exception as e:
            print(f"   ❌ 失敗: {str(e)}")
    
    print(f"\n🎉 完成！結果在 {OUTPUT_FOLDER}")

if __name__ == "__main__":
    run_local_pipeline()