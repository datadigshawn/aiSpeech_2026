# 檔案位置 aiSpeech/scripts/model_whisper.py
import whisper
import torch

# 全域變數，用來暫存載入好的模型，避免重複載入
_loaded_model = None
_curerent_model_size = None

def load_model_once(model_size = "large-v3"):
    """
    確保模型只被載入一次的單例模式（Singleton Pattern）
    並保留原本的M2 GPU加速判斷邏輯
    """
    global _loaded_model, _curerent_model_size

    # 如果模型已經載入且大小一樣，直接回傳
    if _loaded_model is not None and _curerent_model_size == model_size:
        return _loaded_model
    print(f"🔄 正在載入 Whisper模型 ({model_size})...")

    # 偵測 M2/M3 Mac的MPS加速
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    
    try:
        _loaded_model = whisper.load_model(model_size, device=device)
        print(f"✅ Whisper模型 ({model_size}) 載入完成，使用裝置: {device.upper()}")
    except Exception as e:
        print(f"❌ {device}啟用失敗，切回CPU模式：{e}")
        _loaded_model = whisper.load_model(model_size, device="cpu")
        
    _curerent_model_size = model_size
    return _loaded_model

def transcribe_with_whisper(audio_path, model_size = "large-v3"):
    """
    當一檔案辨識函數
    """
    # 1. 取得模型實體
    model = load_model_once(model_size)
    
    # 2. 設定提示詞(prompt)-保留核心promt
    prompt_text = "這是一段捷運無線電通訊,術語包含:OCC行控中心, 呼叫, 立即至一月台, 09, 10, 異物, 方形鑰匙, 05車門, Bypass。"

    # 3. 進行辨識
    # initial_prompt是關鍵
    result = model.transcribe(
        audio_path,
        language="zh",
        initial_prompt=prompt_text,
    )
    return result['text']