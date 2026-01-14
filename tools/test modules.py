#!/usr/bin/env python3
"""
模組測試腳本
檢查所有核心模組是否正確安裝和可導入
"""

import sys
from pathlib import Path

# 添加專案路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """測試所有模組導入"""
    print("=" * 60)
    print("開始測試 aiSpeech 模組...")
    print(str(project_root))    

    print("=" * 60)
    
    tests = []
    
    # 1. 測試基礎工具模組
    print("\n[1/5] 測試基礎工具模組...")
    try:
        from utils.logger import get_logger
        print("  ✅ logger.py")
        tests.append(("logger", True, None))
    except Exception as e:
        print(f"  ❌ logger.py: {e}")
        tests.append(("logger", False, str(e)))
    
    try:
        from utils.timestamp_manager import TimestampManager
        print("  ✅ timestamp_manager.py")
        tests.append(("timestamp_manager", True, None))
    except Exception as e:
        print(f"  ❌ timestamp_manager.py: {e}")
        tests.append(("timestamp_manager", False, str(e)))
    
    try:
        from utils.vad_processor import VADProcessor
        print("  ✅ vad_processor.py")
        tests.append(("vad_processor", True, None))
    except Exception as e:
        print(f"  ❌ vad_processor.py: {e}")
        tests.append(("vad_processor", False, str(e)))
    
    try:
        from utils.text_cleaner import clean_text
        print("  ✅ text_cleaner.py")
        tests.append(("text_cleaner", True, None))
    except Exception as e:
        print(f"  ❌ text_cleaner.py: {e}")
        tests.append(("text_cleaner", False, str(e)))
    
    try:
        from utils.config import get_config
        print("  ✅ config.py")
        tests.append(("config", True, None))
    except Exception as e:
        print(f"  ❌ config.py: {e}")
        tests.append(("config", False, str(e)))
    
    # 2. 測試 AI 模型模組
    print("\n[2/5] 測試 AI 模型模組...")
    try:
        from aiSpeech.scripts.models.model_google_stt_odd import GoogleSTTModel
        print("  ✅ model_google_stt.py")
        tests.append(("model_google_stt", True, None))
    except Exception as e:
        print(f"  ❌ model_google_stt.py: {e}")
        tests.append(("model_google_stt", False, str(e)))
    
    try:
        from scripts.models.model_gemini import GeminiModel
        print("  ✅ model_gemini.py")
        tests.append(("model_gemini", True, None))
    except Exception as e:
        print(f"  ❌ model_gemini.py: {e}")
        tests.append(("model_gemini", False, str(e)))
    
    # 3. 測試批次處理模組
    print("\n[3/5] 測試批次處理模組...")
    try:
        from scripts.audio_splitter import AudioSplitter
        print("  ✅ audio_splitter.py")
        tests.append(("audio_splitter", True, None))
    except Exception as e:
        print(f"  ❌ audio_splitter.py: {e}")
        tests.append(("audio_splitter", False, str(e)))
    
    try:
        from scripts.result_merger import ResultMerger
        print("  ✅ result_merger.py")
        tests.append(("result_merger", True, None))
    except Exception as e:
        print(f"  ❌ result_merger.py: {e}")
        tests.append(("result_merger", False, str(e)))
    
    try:
        from scripts.evaluator import Evaluator
        print("  ✅ evaluator.py")
        tests.append(("evaluator", True, None))
    except Exception as e:
        print(f"  ❌ evaluator.py: {e}")
        tests.append(("evaluator", False, str(e)))
    
    # 4. 測試關鍵依賴套件
    print("\n[4/5] 測試關鍵依賴套件...")
    dependencies = [
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("jiwer", "JiWER"),
        ("matplotlib", "Matplotlib"),
        ("torch", "PyTorch"),
        ("google.cloud.speech_v2", "Google Cloud Speech"),
        ("google.generativeai", "Google Generative AI"),
    ]
    
    for module_name, display_name in dependencies:
        try:
            __import__(module_name)
            print(f"  ✅ {display_name}")
            tests.append((display_name, True, None))
        except ImportError as e:
            print(f"  ❌ {display_name}: {e}")
            tests.append((display_name, False, str(e)))
    
    # 5. 測試可選依賴
    print("\n[5/5] 測試可選依賴...")
    optional_deps = [
        ("webrtcvad", "WebRTC VAD"),
        ("cn2an", "CN2AN"),
        ("opencc", "OpenCC"),
    ]
    
    for module_name, display_name in optional_deps:
        try:
            __import__(module_name)
            print(f"  ✅ {display_name}")
            tests.append((display_name, True, None))
        except ImportError:
            print(f"  ⚠️  {display_name} (可選，未安裝)")
            tests.append((display_name, None, "未安裝（可選）"))
    
    # 統計結果
    print("\n" + "=" * 60)
    print("測試結果摘要")
    print("=" * 60)
    
    passed = sum(1 for _, status, _ in tests if status is True)
    failed = sum(1 for _, status, _ in tests if status is False)
    optional = sum(1 for _, status, _ in tests if status is None)
    total = len(tests)
    
    print(f"\n總測試項目: {total}")
    print(f"  ✅ 通過: {passed}")
    print(f"  ❌ 失敗: {failed}")
    print(f"  ⚠️  可選: {optional}")
    
    if failed > 0:
        print("\n失敗的模組:")
        for name, status, error in tests:
            if status is False:
                print(f"  ❌ {name}")
                if error:
                    print(f"     錯誤: {error}")
    
    print("\n" + "=" * 60)
    
    if failed == 0:
        print("✨ 所有必要模組測試通過！系統已準備就緒。")
        print("\n下一步：")
        print("  1. 設定環境變數（.env 檔案）")
        print("  2. 準備測試音檔")
        print("  3. 執行音檔切分：python scripts/audio_splitter.py")
        return True
    else:
        print("⚠️  部分模組測試失敗，請先安裝缺失的依賴套件。")
        print("\n安裝指令:")
        print("  pip install -r requirements.txt")
        return False


def test_logger():
    """測試日誌系統"""
    print("\n" + "=" * 60)
    print("測試日誌系統功能...")
    print("=" * 60)
    
    try:
        from utils.logger import get_logger
        
        logger = get_logger('test_module')
        
        print("\n測試各級別日誌輸出：")
        logger.debug("這是 DEBUG 級別訊息")
        logger.info("這是 INFO 級別訊息")
        logger.warning("這是 WARNING 級別訊息")
        logger.error("這是 ERROR 級別訊息")
        
        print("\n✅ 日誌系統測試完成")
        print(f"📁 日誌檔案位置: logs/test_module.log")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 日誌系統測試失敗: {e}")
        return False


def main():
    """主函數"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "aiSpeech 系統檢查工具" + " " * 21 + "║")
    print("╚" + "=" * 58 + "╝")
    
    # 測試模組導入
    import_success = test_imports()
    
    # 如果導入成功，測試日誌系統
    if import_success:
        test_logger()
    
    print("\n")


if __name__ == "__main__":
    main()