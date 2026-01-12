# Gemini 批次語音辨識 + 音檔時長資訊
# pip install -U google-generativeai pydub

import os
import time
import google.generativeai as genai
from datetime import timedelta

#========================參數設定區==========================
# 1. 自動尋找 API Key
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# 嘗試從環境變數或檔案讀取 API Key
API_KEY = os.getenv("GEMINI_API_KEY") or "AIzaSyC6qkLuKrlmzN6KC4I4WAV7uUhweD9LxH0"
genai.configure(api_key=API_KEY)

# 2. 資料夾設定
INPUT_FOLDER = os.path.join(SCRIPT_DIR, "audio_input")
OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "transcripts_Gemini")
MODEL_NAME = "models/gemini-2.0-flash-exp"  # 使用最新實驗版

# 3. 支援的音檔格式
SUPPORTED_EXT = {'.wav', '.mp3', '.m4a', '.aac', '.flac', '.ogg'}

# ================= 捷運專業術語 Prompt =================
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
   - 請按照時間順序輸出對話。
"""

PROMPT_TEXT = "請依照上述規則，區分兩位說話者並轉錄為精確的逐字稿。"
# ========================================================

def get_audio_duration(file_path):
    """
    取得音檔時長（秒）
    需要安裝: pip install pydub
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        duration_seconds = len(audio) / 1000.0  # pydub 回傳毫秒
        return duration_seconds
    except ImportError:
        print("  ⚠️  未安裝 pydub，無法取得音檔時長")
        print("  💡 執行: pip install pydub")
        return None
    except Exception as e:
        print(f"  ⚠️  無法讀取音檔時長: {e}")
        return None


def format_duration(seconds):
    """將秒數轉為可讀格式"""
    if seconds is None:
        return "未知"
    return str(timedelta(seconds=int(seconds)))


def add_metadata_header(filename, duration_seconds, transcript):
    """在逐字稿前面加入音檔資訊標頭"""
    header = f"""# 語音辨識結果
# 檔案名稱: {filename}
# 音檔時長: {format_duration(duration_seconds)}
# 辨識模型: Gemini 2.0 Flash
# 辨識時間: {time.strftime("%Y-%m-%d %H:%M:%S")}
# ================================================================

"""
    return header + transcript


def estimate_timestamps(transcript, total_duration):
    """
    簡易時間戳記估算（基於句子數量均分）
    ⚠️ 注意：這只是粗略估算，不如 Google STT 精確
    """
    if total_duration is None:
        return transcript
    
    lines = [line.strip() for line in transcript.split('\n') if line.strip() and not line.startswith('#')]
    
    if not lines:
        return transcript
    
    # 計算每句話的平均時長
    avg_duration = total_duration / len(lines)
    
    timestamped_lines = []
    current_time = 0
    
    for line in lines:
        minutes = int(current_time // 60)
        seconds = current_time % 60
        timestamp = f"[{minutes:02d}:{seconds:05.2f}]"
        timestamped_lines.append(f"{timestamp} {line}")
        current_time += avg_duration
    
    return '\n'.join(timestamped_lines)


def process_batch():
    """批次處理主程式"""
    
    # 確保資料夾存在
    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ 找不到輸入資料夾: {INPUT_FOLDER}")
        print(f"💡 請建立資料夾並放入音檔")
        return
    
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # 取得所有音檔
    all_files = os.listdir(INPUT_FOLDER)
    audio_files = [f for f in all_files if os.path.splitext(f)[1].lower() in SUPPORTED_EXT]
    audio_files.sort()

    total_files = len(audio_files)
    
    if total_files == 0:
        print(f"❌ 在 '{INPUT_FOLDER}' 中找不到支援的音檔")
        print(f"💡 支援格式: {', '.join(SUPPORTED_EXT)}")
        return
    
    print(f"\n{'='*60}")
    print(f"🚀 Gemini 批次處理模式")
    print(f"{'='*60}")
    print(f"📂 輸入資料夾: {INPUT_FOLDER}")
    print(f"📂 輸出資料夾: {OUTPUT_FOLDER}")
    print(f"📊 找到 {total_files} 個音檔")
    print(f"🤖 使用模型: {MODEL_NAME}")
    print(f"{'='*60}\n")

    model = genai.GenerativeModel(MODEL_NAME)
    
    success_count = 0
    fail_count = 0

    for index, filename in enumerate(audio_files, 1):
        file_path = os.path.join(INPUT_FOLDER, filename)
        
        print(f"\n[{index}/{total_files}] 處理: {filename}")
        print(f"{'='*60}")
        
        # 取得音檔時長
        duration = get_audio_duration(file_path)
        if duration:
            print(f"🎵 音檔時長: {format_duration(duration)}")

        try:
            # 1. 上傳
            print(f"  ☁️  上傳至 Gemini API...", end="", flush=True)
            audio_file = genai.upload_file(path=file_path)
            print(f" ✅")
            
            # 2. 等待處理
            print(f"  ⏳ 等待音檔轉碼...", end="", flush=True)
            while audio_file.state.name == "PROCESSING":
                time.sleep(2)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name != "ACTIVE":
                print(f"\n  ❌ 音檔處理失敗 (狀態: {audio_file.state.name})")
                fail_count += 1
                continue
            
            print(f" ✅")

            # 3. AI 辨識
            print(f"  🤖 Gemini 辨識中...")
            response = model.generate_content(
                [SYSTEM_INSTRUCTION, PROMPT_TEXT, audio_file],
                request_options={"timeout": 600}  # 10分鐘超時
            )
            
            transcript = response.text
            
            # 4. 產生三種輸出格式
            base_name = os.path.splitext(filename)[0]
            
            # 格式 1: 完整逐字稿（含標頭）
            full_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_完整逐字稿.txt")
            with open(full_output, "w", encoding="utf-8") as f:
                content = add_metadata_header(filename, duration, transcript)
                f.write(content)
            
            # 格式 2: 簡易時間戳記版（估算）
            timestamp_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_時間估算.txt")
            with open(timestamp_output, "w", encoding="utf-8") as f:
                timestamped = estimate_timestamps(transcript, duration)
                f.write(add_metadata_header(filename, duration, timestamped))
            
            # 格式 3: 純文字（無標頭，方便後處理）
            plain_output = os.path.join(OUTPUT_FOLDER, f"{base_name}_純文字.txt")
            with open(plain_output, "w", encoding="utf-8") as f:
                f.write(transcript)
            
            # 5. 顯示預覽
            preview = transcript[:100].replace('\n', ' ')
            print(f"  📄 辨識結果預覽: {preview}...")
            
            print(f"  ✅ 轉錄完成！")
            print(f"     📄 {os.path.basename(full_output)}")
            print(f"     📄 {os.path.basename(timestamp_output)}")
            print(f"     📄 {os.path.basename(plain_output)}")

            # 6. 清理雲端暫存檔
            audio_file.delete()
            print(f"  🗑️  已清理 API 暫存檔")
            
            success_count += 1

        except Exception as e:
            print(f"  ❌ 處理失敗: {e}")
            fail_count += 1
        
        # 避免觸發 API 頻率限制
        if index < total_files:
            time.sleep(2)

    # 總結報告
    print(f"\n{'='*60}")
    print(f"📊 批次處理完成")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count} 個檔案")
    print(f"❌ 失敗: {fail_count} 個檔案")
    print(f"📂 結果已儲存至: {OUTPUT_FOLDER}")
    print(f"{'='*60}\n")
    
    print("⚠️  注意事項:")
    print("• Gemini 不支援精確的單字層級時間戳記")
    print("• 時間估算版僅供參考，基於句子數量均分時長")
    print("• 如需精確時間戳，建議使用 Google Speech-to-Text")


if __name__ == "__main__":
    process_batch()