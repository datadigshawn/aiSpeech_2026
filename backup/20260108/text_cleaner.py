"""
文字清洗與修正模組（用途2：辨識後修正）
引用 vocabulary/correction_dict.py 進行同音異字修正

檔案位置: aiSpeech/utils/text_cleaner.py

功能：
1. 修正同音異字（用途2 - 引用 correction_dict.py）
2. 數字標準化（中文數字 → 阿拉伯數字）
3. 簡繁轉換
4. 移除標點符號（用於 CER 計算）
5. 移除多餘空白

使用方式:
    from utils.text_cleaner import clean_text_for_asr, fix_radio_jargon
    
    # 完整清洗（用於評測）
    cleaned = clean_text_for_asr(raw_text)
    
    # 僅修正術語（用於顯示）
    fixed = fix_radio_jargon(raw_text)
"""

import re
import sys
from pathlib import Path


# ==================== 動態載入修正字典 ====================

def load_correction_dict():
    """
    動態載入 vocabulary/correction_dict.py 中的修正字典
    用途2: 辨識後修正同音異字
    
    Returns:
        dict: 修正字典 {錯誤詞: 正確詞}
    """
    try:
        # 取得專案根目錄
        project_root = Path(__file__).parent.parent
        correction_file = project_root / 'vocabulary' / 'correction_dict.py'
        
        if not correction_file.exists():
            print("⚠️  警告: 找不到 correction_dict.py")
            print(f"   請先執行: python utils/vocabulary_generator.py")
            return {}
        
        # 動態載入 Python 檔案
        import importlib.util
        spec = importlib.util.spec_from_file_location("correction_dict", correction_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 取得字典
        correction_dict = getattr(module, 'CORRECTION_DICT', {})
        
        if correction_dict:
            print(f"✅ 已載入修正字典: {len(correction_dict)} 組規則")
        else:
            print("⚠️  警告: 修正字典為空")
        
        return correction_dict
    
    except Exception as e:
        print(f"⚠️  載入修正字典失敗: {e}")
        return {}


# 全域變數：快取修正字典
_correction_dict = None
_dict_loaded = False


def get_correction_dict():
    """取得修正字典（單例模式）"""
    global _correction_dict, _dict_loaded
    
    if not _dict_loaded:
        _correction_dict = load_correction_dict()
        _dict_loaded = True
    
    return _correction_dict


# ==================== 核心修正功能 ====================

def fix_radio_jargon(text):
    """
    修正無線電專業術語（用途2 - 同音異字修正）
    引用 vocabulary/correction_dict.py
    
    Args:
        text (str): 原始辨識文字
    
    Returns:
        str: 修正後的文字
    
    Examples:
        >>> fix_radio_jargon("歐西呼叫車組")
        'OCC呼叫車組'
        
        >>> fix_radio_jargon("請確認鬼島異物")
        '請確認軌道異物'
    """
    if not text:
        return ""
    
    # 取得修正字典
    correction_dict = get_correction_dict()
    
    if not correction_dict:
        return text
    
    # 執行字典替換
    for wrong, correct in correction_dict.items():
        text = text.replace(wrong, correct)
    
    return text


# ==================== 數字標準化 ====================

def normalize_chinese_numbers(text):
    """
    中文數字轉阿拉伯數字
    處理無線電特殊讀法和一般中文數字
    
    Args:
        text (str): 包含中文數字的文字
    
    Returns:
        str: 數字標準化後的文字
    
    Examples:
        >>> normalize_chinese_numbers("洞九車門")
        '09車門'
        
        >>> normalize_chinese_numbers("腰洞月台")
        '10月台'
        
        >>> normalize_chinese_numbers("兩百五十")
        '250'
    """
    if not text:
        return ""
    
    # 1. 處理無線電特殊讀法（優先處理，避免被拆分）
    radio_numbers = {
        '洞洞': '00', '洞一': '01', '洞二': '02', '洞三': '03', 
        '洞四': '04', '洞五': '05', '洞六': '06', '洞七': '07',
        '洞八': '08', '洞九': '09',
        '腰洞': '10', '腰腰': '11', '腰二': '12', '腰三': '13',
        '腰四': '14', '腰五': '15', '腰六': '16', '腰七': '17',
        '腰八': '18', '腰九': '19',
        '么洞': '10', '么么': '11',
    }
    
    for chinese, arabic in radio_numbers.items():
        text = text.replace(chinese, arabic)
    
    # 2. 處理單個無線電數字
    single_radio = {
        '洞': '0', '勾': '9', '鉤': '9',
        '腰': '1', '么': '1', '拐': '7'
    }
    
    for chinese, arabic in single_radio.items():
        text = text.replace(chinese, arabic)
    
    # 3. 處理一般中文數字（使用 cn2an 庫）
    try:
        import cn2an
        
        # 找出所有可能的中文數字片段
        # 支援：零一二三四五六七八九十百千萬億兩
        pattern = r'[零一二三四五六七八九十百千萬億兩]+'
        
        def convert_match(match):
            chinese_num = match.group(0)
            try:
                # 嘗試轉換為阿拉伯數字
                arabic = cn2an.cn2an(chinese_num, 'smart')
                return str(arabic)
            except:
                # 如果轉換失敗，保持原樣
                return chinese_num
        
        text = re.sub(pattern, convert_match, text)
        
    except ImportError:
        # 如果沒有安裝 cn2an，做基本轉換
        basic_numbers = {
            '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
            '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
            '十': '10'
        }
        for chinese, arabic in basic_numbers.items():
            text = text.replace(chinese, arabic)
    
    return text


# ==================== 簡繁轉換 ====================

def convert_to_traditional(text):
    """
    簡體中文轉繁體中文
    
    Args:
        text (str): 可能包含簡體字的文字
    
    Returns:
        str: 繁體中文文字
    """
    if not text:
        return ""
    
    try:
        from opencc import OpenCC
        cc = OpenCC('s2t')  # 簡體到繁體
        return cc.convert(text)
    except ImportError:
        print("⚠️  警告: 未安裝 opencc-python-reimplemented")
        print("   執行: pip install opencc-python-reimplemented")
        return text
    except Exception as e:
        print(f"⚠️  簡繁轉換失敗: {e}")
        return text


# ==================== 文字清洗 ====================

def remove_punctuation(text):
    """
    移除所有標點符號（用於 CER 計算）
    
    Args:
        text (str): 包含標點的文字
    
    Returns:
        str: 無標點符號的文字
    """
    if not text:
        return ""
    
    # 中文標點
    chinese_punct = '，。！？；：「」『』（）【】《》、'
    # 英文標點
    english_punct = ',.!?;:\'"()[]<>-'
    
    all_punct = chinese_punct + english_punct
    
    for punct in all_punct:
        text = text.replace(punct, '')
    
    return text


def remove_extra_spaces(text):
    """
    移除多餘的空白字元
    
    Args:
        text (str): 可能包含多餘空白的文字
    
    Returns:
        str: 清理後的文字
    """
    if not text:
        return ""
    
    # 移除前後空白
    text = text.strip()
    
    # 將多個連續空白替換為單一空白
    text = re.sub(r'\s+', ' ', text)
    
    return text


# ==================== 完整清洗流程 ====================

def clean_text_for_asr(
    text,
    fix_jargon=True,
    normalize_numbers=True,
    convert_traditional=True,
    remove_punct=True,
    remove_spaces=True
):
    """
    完整的文字清洗流程（用於 ASR 評測）
    
    執行順序：
    1. 修正專業術語（用途2）
    2. 數字標準化
    3. 簡繁轉換
    4. 移除標點符號
    5. 移除多餘空白
    
    Args:
        text (str): 原始辨識文字
        fix_jargon (bool): 是否修正專業術語
        normalize_numbers (bool): 是否標準化數字
        convert_traditional (bool): 是否轉繁體
        remove_punct (bool): 是否移除標點
        remove_spaces (bool): 是否移除多餘空白
    
    Returns:
        str: 清洗後的文字
    
    Examples:
        >>> text = "歐西，呼叫車組洞九。"
        >>> clean_text_for_asr(text)
        'OCC呼叫車組09'
    """
    if not text:
        return ""
    
    # 1. 修正專業術語（用途2 - 最重要）
    if fix_jargon:
        text = fix_radio_jargon(text)
    
    # 2. 數字標準化
    if normalize_numbers:
        text = normalize_chinese_numbers(text)
    
    # 3. 簡繁轉換
    if convert_traditional:
        text = convert_to_traditional(text)
    
    # 4. 移除標點符號（用於 CER 計算）
    if remove_punct:
        text = remove_punctuation(text)
    
    # 5. 移除多餘空白
    if remove_spaces:
        text = remove_extra_spaces(text)
    
    return text


def clean_text_for_display(text):
    """
    用於顯示的文字清洗（保留標點符號）
    
    Args:
        text (str): 原始辨識文字
    
    Returns:
        str: 清洗後的文字（保留可讀性）
    """
    return clean_text_for_asr(
        text,
        fix_jargon=True,
        normalize_numbers=True,
        convert_traditional=True,
        remove_punct=False,  # 保留標點
        remove_spaces=True
    )


# ==================== 批次處理 ====================

def clean_file(input_path, output_path, mode='asr'):
    """
    清洗單一文字檔案
    
    Args:
        input_path (str): 輸入檔案路徑
        output_path (str): 輸出檔案路徑
        mode (str): 清洗模式
            - 'asr': 用於評測（移除標點）
            - 'display': 用於顯示（保留標點）
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    if mode == 'asr':
        cleaned = clean_text_for_asr(text)
    else:
        cleaned = clean_text_for_display(text)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned)


def clean_folder(input_folder, output_folder, mode='asr'):
    """
    批次清洗資料夾中的所有文字檔
    
    Args:
        input_folder (str): 輸入資料夾
        output_folder (str): 輸出資料夾
        mode (str): 清洗模式
    """
    from pathlib import Path
    
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    txt_files = list(input_folder.glob('*.txt'))
    
    print(f"\n📂 開始批次清洗: {len(txt_files)} 個檔案")
    print(f"   模式: {mode}")
    print(f"   輸出: {output_folder}\n")
    
    for txt_file in txt_files:
        output_path = output_folder / txt_file.name
        clean_file(txt_file, output_path, mode)
        print(f"✅ {txt_file.name}")
    
    print(f"\n完成！")


# ==================== 測試程式 ====================

if __name__ == "__main__":
    """
    測試用主程式
    使用方式: python utils/text_cleaner.py
    """
    
    print("="*60)
    print("文字清洗模組測試（用途2：辨識後修正）")
    print("="*60)
    
    # 測試案例
    test_cases = [
        "歐西呼叫車組，請立即至一月台。",
        "鬼島發現異物，洞九車門滿檔。",
        "車組腰洞收到，百帕斯模式啟動。",
        "R洞三站回報，方行鑰匙已使用。",
        "一一九，求救！車輛出軌！",
    ]
    
    print("\n📋 測試案例:\n")
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"測試 {i}:")
        print(f"  原文: {test_text}")
        
        # 測試修正術語
        fixed = fix_radio_jargon(test_text)
        print(f"  修正: {fixed}")
        
        # 測試完整清洗
        cleaned = clean_text_for_asr(test_text)
        print(f"  清洗: {cleaned}")
        print()
    
    print("="*60)
    print("測試完成！")
    print("="*60)
    
    # 顯示載入的修正字典統計
    correction_dict = get_correction_dict()
    if correction_dict:
        print(f"\n📊 修正字典統計:")
        print(f"   總規則數: {len(correction_dict)}")
        print(f"\n   範例規則（前 10 組）:")
        for i, (wrong, correct) in enumerate(list(correction_dict.items())[:10], 1):
            print(f"      {i}. {wrong} → {correct}")