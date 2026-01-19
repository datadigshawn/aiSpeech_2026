#!/usr/bin/env python3
"""
文字清洗與標準化模組
用於 ASR 評測前的文字預處理
"""

import re
from typing import Optional

try:
    import cn2an
    CN2AN_AVAILABLE = True
except ImportError:
    CN2AN_AVAILABLE = False

try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False


# 無線電術語修正字典 (用途2: 辨識後修正)
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
    "威威威福": "VVVF",
    "雞皮": "KP",
}


def clean_text(text: str, keep_punctuation: bool = False) -> str:
    """
    文字清洗與標準化 (用於 CER/TER 計算前處理)
    
    Args:
        text: 待清洗的文字
        keep_punctuation: 是否保留標點符號
    
    Returns:
        清洗後的文字
    """
    if not text:
        return ""
    
    # 1. 移除標點符號 (除非特別要求保留)
    if not keep_punctuation:
        text = re.sub(r'[，。！？、；：「」『』（）《》\[\],.!?;:\'\"\(\)<>]', '', text)
    
    # 2. 移除多餘空白
    text = re.sub(r'\s+', '', text)
    
    # 3. 簡繁轉換 (統一為繁體)
    if OPENCC_AVAILABLE:
        cc = OpenCC('s2t')  # Simplified to Traditional
        text = cc.convert(text)
    
    # 4. 中文數字轉阿拉伯數字
    if CN2AN_AVAILABLE:
        try:
            # cn2an 可能會對某些非數字文字報錯，需要 try-catch
            text = cn2an.transform(text, "cn2an")
        except Exception:
            pass  # 如果轉換失敗，保持原文
    
    return text.strip()


def fix_radio_jargon(text: str) -> str:
    """
    修正無線電術語的同音異字 (用途2: Python 後處理)
    
    這是辨識「後」的修正步驟，處理 AI 聽對音但寫錯字的情況
    
    Args:
        text: 辨識結果文字
    
    Returns:
        修正後的文字
    """
    if not text:
        return ""
    
    # 執行字典替換
    for wrong, correct in RADIO_REPLACEMENT_RULES.items():
        text = text.replace(wrong, correct)
    
    # 額外格式整理
    text = text.replace("G 3", "G3").replace("G 10", "G10")
    text = text.replace("R 0", "R0").replace("R 1", "R1")
    
    return text.strip()


def normalize_for_evaluation(
    reference: str,
    hypothesis: str
) -> tuple[str, str]:
    """
    評測前的標準化 (用於 CER/TER 計算)
    
    同時處理參考答案和辨識結果，確保比較基準一致
    
    Args:
        reference: 參考答案 (Ground Truth)
        hypothesis: 辨識結果 (ASR Output)
    
    Returns:
        標準化後的 (reference, hypothesis) 元組
    """
    ref_cleaned = clean_text(reference)
    hyp_cleaned = clean_text(hypothesis)
    
    return ref_cleaned, hyp_cleaned


def extract_key_terms(text: str, term_list: list[str]) -> list[str]:
    """
    從文字中提取關鍵術語 (用於 TER 計算)
    
    Args:
        text: 待分析的文字
        term_list: 關鍵術語列表
    
    Returns:
        在文字中出現的關鍵術語列表
    """
    found_terms = []
    for term in term_list:
        if term in text:
            found_terms.append(term)
    return found_terms


def test_text_cleaner():
    """測試文字清洗功能"""
    print("測試文字清洗模組...")
    
    # 測試 1: 標點符號移除
    text1 = "請確認，G3站狀況。"
    cleaned1 = clean_text(text1)
    print(f"\n測試 1 - 標點符號移除:")
    print(f"  原文: {text1}")
    print(f"  清洗後: {cleaned1}")
    
    # 測試 2: 同音異字修正
    text2 = "歐西呼叫，立即致月台"
    fixed2 = fix_radio_jargon(text2)
    print(f"\n測試 2 - 同音異字修正:")
    print(f"  原文: {text2}")
    print(f"  修正後: {fixed2}")
    
    # 測試 3: 中文數字轉換
    if CN2AN_AVAILABLE:
        text3 = "一一九車站"
        cleaned3 = clean_text(text3)
        print(f"\n測試 3 - 中文數字轉換:")
        print(f"  原文: {text3}")
        print(f"  轉換後: {cleaned3}")
    else:
        print(f"\n⚠️  CN2AN 不可用，跳過中文數字轉換測試")
    
    # 測試 4: 簡繁轉換
    if OPENCC_AVAILABLE:
        text4 = "请确认轨道状况"  # 簡體
        cleaned4 = clean_text(text4)
        print(f"\n測試 4 - 簡繁轉換:")
        print(f"  原文: {text4}")
        print(f"  轉換後: {cleaned4}")
    else:
        print(f"\n⚠️  OpenCC 不可用，跳過簡繁轉換測試")
    
    print("\n✅ 文字清洗模組測試完成")


if __name__ == "__main__":
    test_text_cleaner()
