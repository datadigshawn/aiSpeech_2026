#!/usr/bin/env python3
"""
Google STT Chirp 3 完整測試腳本
版本: 1.3 (修正金鑰選擇邏輯)

放置位置: aiSpeech/tools/test_google_stt_chirp3.py

改進:
- 優先選擇有效的服務帳戶金鑰
- 過濾掉配置檔案（非認證金鑰）
- 更準確的金鑰驗證
"""
import os
import sys
from pathlib import Path

# ============================================================================
# 路徑設定
# ============================================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

print(f"腳本目錄: {SCRIPT_DIR}")
print(f"專案根目錄: {PROJECT_ROOT}")

# ============================================================================
# 認證設定 (修正版)
# ============================================================================
def validate_service_account_key(key_path):
    """
    驗證是否為有效的服務帳戶金鑰
    
    Args:
        key_path: 金鑰檔案路徑
    
    Returns:
        dict or None: 金鑰資料（如果有效），否則返回 None
    """
    try:
        import json
        with open(key_path, 'r') as f:
            key_data = json.load(f)
        
        # 檢查必要欄位
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        
        # 必須有 type 欄位且為 service_account
        if key_data.get('type') != 'service_account':
            return None
        
        # 檢查所有必要欄位
        for field in required_fields:
            if field not in key_data or not key_data[field]:
                return None
        
        return key_data
    
    except Exception:
        return None


def find_google_credentials():
    """
    搜尋有效的 Google Cloud 服務帳戶金鑰
    
    Returns:
        tuple: (金鑰路徑, 金鑰資料) 或 (None, None)
    """
    # 可能的檔案名稱
    possible_names = [
        "google-speech-key.json",
        "google-cloud-key.json",
        "service-account-key.json",
        "credentials.json",
    ]
    
    # 可能的目錄（優先順序）
    possible_dirs = [
        PROJECT_ROOT / "utils",
        PROJECT_ROOT / "config",
        SCRIPT_DIR,
        PROJECT_ROOT,
    ]
    
    print("\n搜尋認證金鑰...")
    
    valid_keys = []
    
    for directory in possible_dirs:
        if not directory.exists():
            continue
        
        print(f"  檢查: {directory.relative_to(PROJECT_ROOT) if directory != PROJECT_ROOT else '專案根目錄'}")
        
        # 檢查指定名稱
        for name in possible_names:
            key_file = directory / name
            if key_file.exists():
                key_data = validate_service_account_key(key_file)
                if key_data:
                    valid_keys.append((key_file, key_data))
        
        # 也搜尋所有 JSON 檔案
        for json_file in directory.glob("*.json"):
            if json_file not in [k[0] for k in valid_keys]:
                key_data = validate_service_account_key(json_file)
                if key_data:
                    valid_keys.append((json_file, key_data))
    
    if valid_keys:
        print(f"\n找到 {len(valid_keys)} 個有效的服務帳戶金鑰:")
        for i, (key_file, key_data) in enumerate(valid_keys, 1):
            print(f"    {i}. {key_file.name}")
            print(f"       路徑: {key_file}")
            print(f"       專案: {key_data.get('project_id')}")
            print(f"       服務帳戶: {key_data.get('client_email')}")
            print(f"       ✅ 有效的服務帳戶金鑰")
        
        # 返回第一個有效的金鑰
        return valid_keys[0]
    
    return None, None


def setup_credentials():
    """設定 Google Cloud 認證（修正版）"""
    # 先檢查環境變數
    existing_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    if existing_creds:
        # 檢查路徑是否有效
        if Path(existing_creds).exists():
            # 驗證是否為有效的服務帳戶金鑰
            key_data = validate_service_account_key(existing_creds)
            if key_data:
                print(f"✅ 使用環境變數中的認證: {existing_creds}")
                print(f"   專案: {key_data.get('project_id')}")
                return True
            else:
                print(f"⚠️  環境變數指向的檔案不是有效的服務帳戶金鑰: {existing_creds}")
                print("    將嘗試自動搜尋金鑰...")
        else:
            print(f"⚠️  環境變數指向的金鑰不存在: {existing_creds}")
            print("    將嘗試自動搜尋金鑰...")
    
    # 自動搜尋金鑰
    key_path, key_data = find_google_credentials()
    
    if key_path:
        # 設定環境變數
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_path)
        os.environ['GOOGLE_CLOUD_PROJECT'] = key_data.get('project_id', 'dazzling-seat-315406')
        print(f"\n✅ 自動設定認證金鑰: {key_path}")
        print(f"✅ 專案 ID: {key_data.get('project_id')}")
        return True
    
    print("\n❌ 找不到有效的服務帳戶金鑰")
    print("\n請確認:")
    print("  1. 金鑰檔案存在於以下任一位置:")
    print(f"     - {PROJECT_ROOT}/utils/google-speech-key.json")
    print(f"     - {PROJECT_ROOT}/config/google-speech-key.json")
    print("  2. 金鑰檔案是從 Google Cloud Console 下載的服務帳戶金鑰")
    print("  3. 金鑰檔案包含 'type': 'service_account' 欄位")
    
    return False


# ============================================================================
# 導入模組
# ============================================================================
def import_modules():
    """導入必要模組"""
    print("\n檢查必要模組...")
    
    modules = {
        'google.cloud.speech_v2': 'Google Cloud Speech V2',
        'google.api_core': 'Google API Core',
    }
    
    missing = []
    for module_name, display_name in modules.items():
        try:
            __import__(module_name)
            print(f"  ✅ {display_name}")
        except ImportError:
            print(f"  ❌ {display_name} (未安裝)")
            missing.append(module_name.split('.')[0])
    
    if missing:
        print(f"\n請安裝缺少的套件:")
        print(f"pip install {' '.join(set(missing))}")
        return False
    
    return True


# ============================================================================
# 測試函數
# ============================================================================
def test_1_environment():
    """測試 1: 環境檢查"""
    print("\n" + "=" * 80)
    print("測試 1: 環境檢查")
    print("=" * 80)
    
    # 1. 路徑檢查
    print("\n1.0 路徑檢查:")
    print(f"  當前工作目錄: {Path.cwd()}")
    print(f"  腳本目錄: {SCRIPT_DIR}")
    print(f"  專案根目錄: {PROJECT_ROOT}")
    
    key_dirs = [
        PROJECT_ROOT / "scripts" / "models",
        PROJECT_ROOT / "utils",
        PROJECT_ROOT / "experiments"
    ]
    
    for dir_path in key_dirs:
        status = "✅" if dir_path.exists() else "❌"
        print(f"  {status} {dir_path.relative_to(PROJECT_ROOT)}")
    
    # 2. 認證檢查
    print("\n1.1 Google Cloud 認證:")
    if not setup_credentials():
        print("❌ 認證設定失敗")
        return False
    
    # 3. 驗證認證有效性
    print("\n1.2 驗證認證:")
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if creds_path and Path(creds_path).exists():
        print(f"  金鑰位置: {creds_path}")
        
        key_data = validate_service_account_key(creds_path)
        if key_data:
            print(f"  專案 ID: {key_data.get('project_id')}")
            print(f"  服務帳戶: {key_data.get('client_email')}")
            print(f"  類型: {key_data.get('type')}")
            print(f"  ✅ 有效的服務帳戶金鑰")
        else:
            print(f"  ⚠️  金鑰檔案格式可能有問題")
    
    # 4. 專案 ID 檢查
    print("\n1.3 專案設定:")
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    print(f"  GOOGLE_CLOUD_PROJECT: {project_id}")
    
    # 5. 模組檢查
    print("\n1.4 Python 套件:")
    if not import_modules():
        return False
    
    # 6. FFmpeg 檢查
    print("\n1.5 FFmpeg (音訊轉換工具):")
    try:
        import subprocess
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  ✅ {version}")
        else:
            print("  ❌ FFmpeg 執行失敗")
            return False
    except FileNotFoundError:
        print("  ❌ FFmpeg 未安裝")
        print("  請安裝: brew install ffmpeg")
        return False
    except Exception as e:
        print(f"  ⚠️  FFmpeg 檢查異常: {e}")
    
    print("\n✅ 環境檢查完成")
    return True


def test_2_model_initialization():
    """測試 2: 模型初始化"""
    print("\n" + "=" * 80)
    print("測試 2: 模型初始化")
    print("=" * 80)
    
    try:
        from scripts.models.model_google_stt import GoogleSTTModel
        print("✅ 模組導入成功")
        
        print("\n初始化 Google STT 模型...")
        print("  這可能需要幾秒鐘時間...")
        
        model = GoogleSTTModel(
            project_id="dazzling-seat-315406",
            model="chirp_3",
            location="us",
            auto_config=True,
            auto_convert_audio=True
        )
        
        print("\n模型配置:")
        model.print_config_info()
        
        print("\n✅ 模型初始化成功")
        return model
    
    except ImportError as e:
        print(f"\n❌ 模組導入失敗: {e}")
        return None
    
    except Exception as e:
        print(f"\n❌ 模型初始化失敗: {e}")
        
        error_str = str(e)
        if "does not have a valid type" in error_str:
            print("\n診斷: 使用了錯誤的金鑰檔案")
            print(f"  當前金鑰: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
            print("  這個檔案不是服務帳戶金鑰")
            print("  請確認使用的是從 Google Cloud Console 下載的金鑰")
        
        import traceback
        print("\n詳細錯誤:")
        traceback.print_exc()
        return None


def test_3_audio_conversion(model):
    """測試 3: 音訊格式檢查與轉換"""
    if not model:
        print("\n⚠️  跳過音訊轉換測試（模型未初始化）")
        return None
    
    print("\n" + "=" * 80)
    print("測試 3: 音訊格式檢查與轉換")
    print("=" * 80)
    
    test_dirs = [
        PROJECT_ROOT / "experiments" / "Test_02_TMRT" / "source_audio",
        PROJECT_ROOT / "experiments" / "Test_01_TMRT" / "source_audio",
    ]
    
    test_file = None
    for test_dir in test_dirs:
        if test_dir.exists():
            audio_files = list(test_dir.glob("*.wav"))
            if audio_files:
                test_file = str(audio_files[0])
                break
    
    if not test_file:
        print("\n⚠️  找不到測試音檔")
        return None
    
    print(f"\n使用測試檔案: {Path(test_file).name}")
    
    try:
        from scripts.models.model_google_stt import AudioConverter
        
        print("\n3.1 音訊檔案資訊:")
        info = AudioConverter.get_wav_info(test_file)
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        print("\n3.2 轉換需求檢查:")
        needs_convert, detailed_info = AudioConverter.needs_conversion(test_file)
        print(f"  需要轉換: {needs_convert}")
        
        if needs_convert:
            print(f"  轉換原因:")
            for reason in detailed_info.get('conversion_reasons', []):
                print(f"    - {reason}")
        
        print("\n✅ 音訊轉換測試完成")
        return test_file
    
    except Exception as e:
        print(f"\n❌ 音訊轉換測試失敗: {e}")
        return None


def test_4_transcription(model, test_file):
    """測試 4: 語音辨識"""
    if not model or not test_file:
        print("\n⚠️  跳過語音辨識測試（前置條件未滿足）")
        return False
    
    print("\n" + "=" * 80)
    print("測試 4: 語音辨識")
    print("=" * 80)
    
    print(f"\n開始辨識音檔: {Path(test_file).name}")
    print("這可能需要幾秒鐘到一分鐘...")
    
    try:
        result = model.transcribe_file(
            test_file,
            phrases=None,
            enable_word_time_offsets=True
        )
        
        print("\n辨識結果:")
        print("-" * 80)
        
        if 'error' in result:
            print(f"❌ 辨識失敗: {result['error']}")
            return False
        
        transcript = result.get('transcript', '')
        confidence = result.get('confidence', 0)
        
        print(f"文字內容:\n{transcript}")
        print(f"\n信心度: {confidence:.2%}")
        
        if transcript:
            print("\n✅ 語音辨識成功")
            return True
        else:
            print("\n⚠️  辨識結果為空")
            return False
    
    except Exception as e:
        print(f"\n❌ 語音辨識失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_batch_processing():
    """測試 5: 批次處理建議"""
    print("\n" + "=" * 80)
    print("測試 5: 批次處理建議")
    print("=" * 80)
    
    print("\n如果上述測試都通過，您可以執行批次處理:")
    print("\n從專案根目錄執行:")
    print("  cd " + str(PROJECT_ROOT))
    print("  python scripts/batch_inference.py \\")
    print("      --test-case Test_02_TMRT \\")
    print("      --model google_stt \\")
    print("      --stt-model chirp_3 \\")
    print("      --stt-region us")


def main():
    """主測試流程"""
    print("=" * 80)
    print("Google STT Chirp 3 完整測試程式 (v1.3 - 修正版)")
    print("=" * 80)
    
    # 測試 1: 環境檢查
    if not test_1_environment():
        print("\n" + "=" * 80)
        print("測試中斷：環境檢查失敗")
        print("=" * 80)
        return 1
    
    # 測試 2: 模型初始化
    model = test_2_model_initialization()
    if not model:
        print("\n" + "=" * 80)
        print("測試中斷：模型初始化失敗")
        print("=" * 80)
        return 1
    
    # 測試 3: 音訊轉換
    test_file = test_3_audio_conversion(model)
    
    # 測試 4: 語音辨識
    transcription_success = test_4_transcription(model, test_file)
    
    # 測試 5: 批次處理建議
    test_5_batch_processing()
    
    # 總結
    print("\n" + "=" * 80)
    print("測試完成總結")
    print("=" * 80)
    
    print("\n測試結果:")
    print("  ✅ 環境檢查: 通過")
    print(f"  {'✅' if model else '❌'} 模型初始化: {'通過' if model else '失敗'}")
    print(f"  {'✅' if test_file else '⚠️ '} 音訊轉換: {'通過' if test_file else '未測試'}")
    print(f"  {'✅' if transcription_success else '❌'} 語音辨識: {'通過' if transcription_success else '失敗或未測試'}")
    
    if model and transcription_success:
        print("\n🎉 所有測試通過！您的系統已準備好使用 Google STT Chirp 3 模式")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查錯誤訊息並修正")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)