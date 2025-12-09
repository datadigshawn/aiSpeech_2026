import os
import time
import whisper
from datetime import timedelta

# ================= ⚙️ 設定區 =================
INPUT_FOLDER = "audio_input"
OUTPUT_FOLDER = "transcripts_Whisper"
MODEL_TYPE = "medium"  # medium 對無線電音檔表現最穩定
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 🔧 後處理字典 =================
REPLACEMENT_RULES = {
    "歐西": "OCC", "哦西": "OCC", 
    "護照": "呼叫", "立即致": "立即至",
    "洞溝": "09", "動勾": "09", "洞": "0", "勾": "9",
    "腰動": "10", "么洞": "10", "么": "1",
    "動五": "05", "動武": "05",
    "聚山": "G13", "巨山": "G13", 
    "大清": "大慶", "舊車": "舊社", "舊設": "舊社",
    "百帕子": "Bypass", "百帕斯": "Bypass", "偷拜PASS": "Bypass",
    "通告要動": "09/10", "車主通告要動": "車組09/10",
    "通過要動": "09/10", "車主通過要動": "車組09/10",
    "動軌要動": "09/10", "車主動軌要動": "車組09/10",
    "九張離站": "九張犁站", "山軌": "三軌", "布含": "不含",
    "附電": "復電", "華門": "滑門", "電器": "電氣",
}

def post_process_text(text):
    """後處理：修正專有名詞"""
    for wrong, correct in REPLACEMENT_RULES.items():
        text = text.replace(wrong, correct)
    return text.strip()

def remove_repetitions(text, max_repeat=1):
    """移除完全重複的句子（只保留 1 次）"""
    lines = text.split('。')
    result = []
    seen = set()
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 完全相同的句子只保留第一次
        if line not in seen:
            result.append(line)
            seen.add(line)
    
    return '。'.join(result) + '。' if result else ""

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
        print("⚡️ M2 GPU 加速已啟用")
    except Exception as e:
        print(f"⚠️ 使用 CPU: {e}")
        model = whisper.load_model(MODEL_TYPE)
    
    print(f"✅ 開始處理 {len(files)} 個檔案\n")
    
    for i, filename in enumerate(files):
        file_path = os.path.join(INPUT_FOLDER, filename)
        output_filename = os.path.splitext(filename)[0] + "_fixed.txt"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        print(f"▶️ [{i+1}/{len(files)}] {filename}")
        start_time = time.time()
        
        try:
            # 🔥 關鍵：完全不用 initial_prompt！
            # Whisper 對無線電音檔，不給 prompt 反而更好
            result = model.transcribe(
                file_path,
                language="zh",
                
                # 🔥 核心參數：防止重複
                condition_on_previous_text=False,
                temperature=0.0,
                
                # 🔥 更嚴格的壓縮率門檻
                compression_ratio_threshold=1.8,
                
                # 🔥 提高靜音門檻，避免辨識背景雜訊
                no_speech_threshold=0.6,
                logprob_threshold=-1.0,
                
                # 🔥 不用 initial_prompt！
                # initial_prompt=None,  # 預設就是 None
                
                fp16=True,
                verbose=False
            )
            
            # 後處理
            text = result["text"]
            
            # 1. 移除完全重複的句子
            text = remove_repetitions(text)
            
            # 2. 修正專有名詞
            text = post_process_text(text)
            
            # 儲存
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            
            duration = time.time() - start_time
            word_count = len(text)
            print(f"   ✅ 完成 ({int(duration)}秒，{word_count}字)")
            
        except Exception as e:
            print(f"   ❌ 失敗: {e}")
    
    print(f"\n🎉 完成！查看 {OUTPUT_FOLDER}")

if __name__ == "__main__":
    run_local_pipeline()