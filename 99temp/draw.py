import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import platform
import os

def draw_structure():
    # 1. 設定中文字體路徑 (核心解決方案)
    system_name = platform.system()
    
    if system_name == "Darwin":  # macOS
        # Mac 常用的繁體中文字體：蘋方-繁 (PingFang TC)
        font_path = '/System/Library/Fonts/PingFang.ttc'
        # 如果找不到 PingFang，嘗試用黑體
        if not os.path.exists(font_path):
            font_path = '/System/Library/Fonts/STHeiti Light.ttc'
            
    elif system_name == "Windows":  # Windows
        # Windows 常用的微軟正黑體
        font_path = r'C:\Windows\Fonts\msjh.ttc'
        
    elif system_name == "Linux":  # Linux (例如 Colab 或 Ubuntu)
        # 嘗試尋找常見的開源中文字體
        font_path = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
    else:
        font_path = None

    # 載入字體屬性
    if font_path and os.path.exists(font_path):
        my_font = FontProperties(fname=font_path)
        print(f"使用字體: {font_path}")
    else:
        # 如果真的找不到，回退到預設(可能還是會亂碼，但至少不會報錯)
        my_font = FontProperties()
        print("警告：未找到合適的中文字體，中文可能會顯示為方格。")

    # 設定圖表大小與解析度
    fig, ax = plt.subplots(figsize=(12, 14), dpi=150) # 稍微加大寬度以免文字折行
    
    # 目錄結構文字內容
    structure_text = """
aiSpeech/
├── 📄 requirements.txt          # 專案依賴庫 (pandas, jiwer, cn2an, opencc等)
├── 📄 README.md                 # 專案說明文件
│
├── 📂 scripts/                  # 【核心程式碼區】所有Python腳本放這裡
│   ├── 📄 audio_splitter.py     # 1. 切分音檔與靜音偵測腳本 
│   ├── 📄 batch_inference.py    # 2. 呼叫三種模型(Gemini, STT, Whisper)的批次推論腳本
│   ├── 📄 result_merger.py      # 3. 合併結果腳本 (原 asr_results.py) 
│   └── 📄 evaluator.py          # 4. 評分與繪圖腳本 (原 asr_evaluation.py) 
│
├── 📂 utils/                    # 【工具區】共用模組
│   ├── 📄 text_cleaner.py       # 定義 clean_text 函數 (轉數字、去標點)
│   └── 📄 config.py             # 設定 API Key 或全域參數
│
└── 📂 experiments/              # 【實驗數據區】每個測試案獨立一個資料夾
    │
    ├── 📂 Test_01_TMRT/         # 測試案1：捷運無線電 (本次範例)
    │   ├── 📂 source_audio/     # 原始長音檔 (如 TMRT_5min.wav)
    │   ├── 📂 dataset_chunks/   # 切分後的短音檔 (chunk_001.wav...) 
    │   │
    │   ├── 📂 ASR_Evaluation/   # 評測核心資料夾
    │   │   ├── 📂 ground_truth/      # 人工聽寫的正確文字檔 (chunk_001.txt)
    │   │   ├── 📂 gemini_output/     # Gemini 辨識結果
    │   │   ├── 📂 stt_output/        # Google STT 辨識結果
    │   │   ├── 📂 whisper_output/    # Whisper 辨識結果
    │   │   │
    │   │   ├── 📄 asr_results.csv    # 合併後的總表
    │   │   └── 📄 evaluation_report.csv # 最終 CER 評分報表
    │
    ├── 📂 Test_02_Meeting/      # 測試案2：(預留) 會議記錄
    │   └── ... (結構同上)
    │
    └── 📂 Test_03_Interview/    # 測試案3：(預留) 訪談
        └── ... (結構同上)
    """

    # 繪製文字
    # 關鍵修改：加入 fontproperties=my_font 參數
    ax.text(0.05, 0.95, structure_text, 
            transform=ax.transAxes, 
            fontsize=11, # 稍微調小字體以容納更多內容
            fontproperties=my_font, # 這裡指定中文字體
            verticalalignment='top')

    # 隱藏座標軸
    ax.axis('off')
    
    # 儲存檔案
    output_filename = 'aiSpeech_structure.jpg'
    plt.savefig(output_filename, bbox_inches='tight', pad_inches=0.5)
    print(f"成功產生圖片：{output_filename}")
    plt.close()

if __name__ == "__main__":
    draw_structure()