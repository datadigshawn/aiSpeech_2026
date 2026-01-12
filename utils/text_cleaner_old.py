# 檔案位置：aiSpeech/utils/text_cleaner.py

# 無線電術語修正字典
RADIO_REPLACEMENT_RULES = {
    "歐西": "OCC",
    "哦西": "OCC",
    "護照": "呼叫",
    "立即致": "立即至",
    "洞溝": "09",
    "動勾": "09",
    "洞": "0",
    "勾": "9",
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

def fix_radio_jargon(text):
    """
    針對無線電術語進行強制替換 (Post-processing)
    """
    if not text:
        return ""
        
    # 1. 執行字典替換
    for wrong, correct in RADIO_REPLACEMENT_RULES.items():
        text = text.replace(wrong, correct)
    
    # 2. 額外的格式整理
    # 例如把 "G 3" 的空白拿掉變成 "G3"
    text = text.replace("G 3", "G3").replace("G 10", "G10")
    
    return text.strip()

# 保留您原本可能存在的 clean_text 函數 (用於評分前處理)，這裡不衝突