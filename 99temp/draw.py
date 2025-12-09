import matplotlib.pyplot as plt

def draw_structure():
    # 設定圖表大小與解析度
    fig, ax = plt.subplots(figsize=(10, 12), dpi=150)
    
    # 目錄結構文字內容
    structure_text = """
    aiSpeech/ (專案根目錄)
    │
    ├── requirements.txt
    ├── README.md
    │
    ├── scripts/ (核心程式碼)
    │   ├── audio_splitter.py   (切分音檔)
    │   ├── batch_inference.py  (批次推論: Gemini/STT/Whisper)
    │   ├── result_merger.py    (合併 CSV)
    │   └── evaluator.py        (計算 CER 與畫圖)
    │
    ├── utils/ (共用工具)
    │   ├── text_cleaner.py     (文字標準化: 轉數字/去標點)
    │   └── config.py           (API Key 設定)
    │
    └── experiments/ (多重測試案數據區)
        │
        ├── Test_01_TMRT/ (測試案 1)
        │   ├── source_audio/    (原始長檔)
        │   ├── dataset_chunks/  (切分短檔)
        │   └── ASR_Evaluation/
        │       ├── ground_truth/     (人工聽寫 .txt)
        │       ├── gemini_output/    (Gemini 輸出 .txt)
        │       ├── stt_output/       (Google STT 輸出 .txt)
        │       ├── whisper_output/   (Whisper 輸出 .txt)
        │       ├── asr_results.csv   (合併總表)
        │       └── report.csv        (評分結果)
        │
        ├── Test_02_Meeting/ (測試案 2)
        │   └── ...
        │
        └── Test_03_Interview/ (測試案 3)
            └── ...
    """

    # 繪製文字
    # 支援中文顯示需確保環境有字型，這裡使用預設字型繪製結構圖
    # 若需顯示中文註解，請確保系統有支援的中文字型 (如 Microsoft JhengHei 或 Arial Unicode MS)
    # 這裡為了通用性，使用等寬字體來保持縮排對齊
    ax.text(0.05, 0.95, structure_text, 
            transform=ax.transAxes, 
            fontsize=12, 
            family='monospace', 
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