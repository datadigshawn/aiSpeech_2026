#!/usr/bin/env python3
"""
環境變數設定檢查工具
檢查 .env 檔案是否正確設定
"""

import os
import sys
from pathlib import Path

# 載入 .env 檔案
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ 已載入 .env 檔案\n")
except ImportError:
    print("⚠️  未安裝 python-dotenv，請執行: pip install python-dotenv\n")


def check_required_settings():
    """檢查必要設定"""
    print("=" * 70)
    print("環境變數設定檢查")
    print("=" * 70)
    
    # 定義檢查項目
    checks = {
        "基本設定": [
            ("LOG_LEVEL", False, "日誌級別"),
            ("DEFAULT_TEST_CASE", False, "預設測試案"),
        ],
        "Whisper 設定（本地執行）": [
            ("WHISPER_MODEL", False, "Whisper 模型大小"),
            ("USE_FASTER_WHISPER", False, "使用優化版本"),
        ],
        "VAD 設定": [
            ("VAD_ENGINE", False, "VAD 引擎"),
            ("VAD_THRESHOLD", False, "VAD 閾值"),
        ],
        "Google Cloud（使用 Google STT 時需要）": [
            ("GOOGLE_CLOUD_PROJECT", False, "Google Cloud 專案 ID"),
            ("GOOGLE_APPLICATION_CREDENTIALS", True, "服務帳號金鑰路徑"),
            ("GOOGLE_STT_LOCATION", False, "STT 區域"),
            ("GOOGLE_STT_MODEL", False, "STT 模型"),
        ],
        "Google Gemini（使用 Gemini 時需要）": [
            ("GEMINI_API_KEY", True, "Gemini API 金鑰"),
            ("GEMINI_MODEL", False, "Gemini 模型"),
        ],
        "資料庫設定（選用）": [
            ("DB_HOST", False, "資料庫主機"),
            ("DB_PORT", False, "資料庫埠號"),
            ("DB_NAME", False, "資料庫名稱"),
        ],
    }
    
    results = {}
    
    for category, items in checks.items():
        print(f"\n【{category}】")
        category_results = []
        
        for var_name, check_file, description in items:
            value = os.getenv(var_name)
            
            if value:
                # 檢查是否為預設值（未修改）
                is_default = value in [
                    "your_gemini_api_key_here",
                    "/path/to/your-service-account-key.json",
                    "your-email@gmail.com",
                    "your-app-password",
                    "your_database_password"
                ]
                
                if is_default:
                    print(f"  ⚠️  {var_name}: 尚未修改（仍為預設值）")
                    print(f"      → {description}")
                    category_results.append((var_name, "default", value))
                elif check_file:
                    # 檢查檔案是否存在
                    if Path(value).exists():
                        print(f"  ✅ {var_name}: 已設定")
                        print(f"      → {value}")
                        category_results.append((var_name, "ok", value))
                    else:
                        print(f"  ❌ {var_name}: 檔案不存在")
                        print(f"      → {value}")
                        category_results.append((var_name, "file_not_found", value))
                else:
                    print(f"  ✅ {var_name}: 已設定")
                    # 對於敏感資訊，只顯示部分內容
                    if "KEY" in var_name or "PASSWORD" in var_name:
                        display_value = value[:10] + "..." if len(value) > 10 else value
                    else:
                        display_value = value
                    print(f"      → {display_value}")
                    category_results.append((var_name, "ok", value))
            else:
                print(f"  ⚪ {var_name}: 未設定")
                print(f"      → {description}")
                category_results.append((var_name, "not_set", None))
        
        results[category] = category_results
    
    return results


def provide_recommendations(results):
    """提供設定建議"""
    print("\n" + "=" * 70)
    print("設定建議")
    print("=" * 70)
    
    # 檢查是否可以使用 Whisper（最基本功能）
    whisper_ready = all(
        status in ["ok", "default"] 
        for cat, items in results.items() 
        if "Whisper" in cat or "VAD" in cat or "基本" in cat
        for _, status, _ in items
    )
    
    google_stt_ready = all(
        status == "ok"
        for cat, items in results.items()
        if "Google Cloud" in cat
        for _, status, _ in items
    )
    
    gemini_ready = any(
        var == "GEMINI_API_KEY" and status == "ok"
        for cat, items in results.items()
        if "Gemini" in cat
        for var, status, _ in items
    )
    
    print("\n✨ 您可以使用的功能：\n")
    
    if whisper_ready:
        print("✅ Whisper 本地辨識（推薦新手先使用）")
        print("   執行: python scripts/batch_inference.py --model whisper ...")
        print()
    
    if google_stt_ready:
        print("✅ Google STT 辨識（雲端服務，需要憑證）")
        print("   執行: python scripts/batch_inference.py --model google_stt ...")
        print()
    else:
        print("⚠️  Google STT 辨識（需要設定）")
        print("   請設定 GOOGLE_APPLICATION_CREDENTIALS 指向金鑰檔案")
        print()
    
    if gemini_ready:
        print("✅ Gemini 辨識（雲端服務，需要 API 金鑰）")
        print("   執行: python scripts/batch_inference.py --model gemini ...")
        print()
    else:
        print("⚠️  Gemini 辨識（需要設定）")
        print("   請到 https://makersuite.google.com/app/apikey 取得 API 金鑰")
        print("   並設定 GEMINI_API_KEY")
        print()
    
    # 提供下一步建議
    print("=" * 70)
    print("建議的下一步：")
    print("=" * 70)
    
    if whisper_ready:
        print("\n✨ 您可以立即開始使用 Whisper！\n")
        print("1️⃣  生成詞彙表：")
        print("   python vocabulary/generate_vocabulary_files.py")
        print()
        print("2️⃣  執行完整流程：")
        print("   python run_speech_recognition.py")
        print()
        print("3️⃣  或手動執行切分：")
        print("   python scripts/audio_splitter.py \\")
        print("     experiments/Test_02_TMRT/source_audio/your_audio.wav \\")
        print("     --output-dir experiments/Test_02_TMRT/dataset_chunks")
        print()
    else:
        print("\n⚠️  請先完成 .env 設定\n")
        print("必須設定的項目：")
        
        for cat, items in results.items():
            for var, status, _ in items:
                if status in ["not_set", "default", "file_not_found"]:
                    if "Whisper" in cat or "VAD" in cat or "基本" in cat:
                        print(f"  - {var}")
        print()


def main():
    """主函數"""
    print("\n")
    
    # 檢查 .env 檔案是否存在
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ 找不到 .env 檔案")
        print("\n請執行以下命令建立：")
        print("  cp .env.example .env")
        print("\n然後編輯 .env 填入您的設定")
        return
    
    # 執行檢查
    results = check_required_settings()
    
    # 提供建議
    provide_recommendations(results)
    
    print("\n")


if __name__ == "__main__":
    main()