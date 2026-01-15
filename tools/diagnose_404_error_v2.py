#!/usr/bin/env python3
"""
Google STT 404 錯誤診斷腳本 (修正版)
自動搜尋並設定認證金鑰

使用方式:
    cd /Users/apple/Projects/aiSpeech
    python diagnose_404_error.py
"""
import os
import sys
import json
from pathlib import Path

# 設定路徑
PROJECT_ROOT = Path('/Users/apple/Projects/aiSpeech')
sys.path.insert(0, str(PROJECT_ROOT))

print("=" * 80)
print("Google STT 404 錯誤診斷 (修正版)")
print("=" * 80)

# ============================================================================
# 步驟 0: 自動搜尋並設定認證金鑰
# ============================================================================
print("\n【步驟 0】自動搜尋認證金鑰")
print("-" * 80)

def find_service_account_key():
    """搜尋有效的服務帳戶金鑰"""
    possible_paths = [
        PROJECT_ROOT / "utils" / "google-speech-key.json",
        PROJECT_ROOT / "config" / "google-speech-key.json",
        PROJECT_ROOT / "google-speech-key.json",
    ]
    
    print("搜尋金鑰檔案...")
    for key_path in possible_paths:
        print(f"  檢查: {key_path.relative_to(PROJECT_ROOT)}")
        
        if not key_path.exists():
            print(f"    ❌ 不存在")
            continue
        
        try:
            with open(key_path, 'r') as f:
                key_data = json.load(f)
            
            # 驗證是否為服務帳戶金鑰
            if key_data.get('type') != 'service_account':
                print(f"    ⚠️  不是服務帳戶金鑰 (type={key_data.get('type')})")
                continue
            
            # 檢查必要欄位
            required_fields = ['project_id', 'private_key', 'client_email']
            missing = [f for f in required_fields if f not in key_data]
            
            if missing:
                print(f"    ⚠️  缺少欄位: {missing}")
                continue
            
            print(f"    ✅ 找到有效的服務帳戶金鑰")
            print(f"    專案: {key_data.get('project_id')}")
            print(f"    服務帳戶: {key_data.get('client_email')}")
            
            return key_path, key_data
        
        except Exception as e:
            print(f"    ❌ 讀取失敗: {e}")
            continue
    
    return None, None

# 搜尋金鑰
key_path, key_data = find_service_account_key()

if not key_path:
    print("\n❌ 錯誤: 找不到有效的服務帳戶金鑰")
    print("\n請確認以下位置有金鑰檔案:")
    print(f"  - {PROJECT_ROOT}/utils/google-speech-key.json")
    print(f"  - {PROJECT_ROOT}/config/google-speech-key.json")
    print("\n金鑰檔案必須:")
    print("  1. 是從 Google Cloud Console 下載的 JSON 格式")
    print("  2. 包含 'type': 'service_account'")
    print("  3. 包含 project_id, private_key, client_email 欄位")
    sys.exit(1)

# 設定環境變數
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_path)
os.environ['GOOGLE_CLOUD_PROJECT'] = key_data['project_id']

print(f"\n✅ 已自動設定環境變數:")
print(f"  GOOGLE_APPLICATION_CREDENTIALS: {key_path}")
print(f"  GOOGLE_CLOUD_PROJECT: {key_data['project_id']}")

# ============================================================================
# 步驟 1: 驗證認證設定
# ============================================================================
print("\n【步驟 1】驗證認證設定")
print("-" * 80)

creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
project_id = os.getenv('GOOGLE_CLOUD_PROJECT')

print(f"環境變數:")
print(f"  GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
print(f"  GOOGLE_CLOUD_PROJECT: {project_id}")
print(f"  ✅ 認證設定完成")

# ============================================================================
# 步驟 2: 測試 API 連接
# ============================================================================
print("\n【步驟 2】測試 Google Cloud API 連接")
print("-" * 80)

try:
    from google.cloud.speech_v2 import SpeechClient
    from google.api_core.client_options import ClientOptions
    
    # 測試不同的區域端點
    regions_to_test = [
        ("us", "us-speech.googleapis.com"),
        ("us-central1", "us-central1-speech.googleapis.com"),
        ("eu", "eu-speech.googleapis.com"),
    ]
    
    successful_regions = []
    
    for location, endpoint in regions_to_test:
        try:
            print(f"\n測試區域: {location}")
            print(f"  端點: {endpoint}")
            
            client_options = ClientOptions(api_endpoint=endpoint)
            client = SpeechClient(client_options=client_options)
            
            print(f"  ✅ 連接成功")
            successful_regions.append((location, endpoint))
        except Exception as e:
            error_msg = str(e)[:100]
            print(f"  ❌ 連接失敗: {error_msg}")
    
    if successful_regions:
        print(f"\n✅ 成功連接 {len(successful_regions)} 個區域")
    else:
        print(f"\n❌ 警告: 所有區域連接失敗")

except ImportError as e:
    print(f"  ❌ 無法導入 Google Cloud Speech 模組: {e}")
    print(f"  請安裝: pip install google-cloud-speech")
    sys.exit(1)

# ============================================================================
# 步驟 3: 測試模型初始化
# ============================================================================
print("\n【步驟 3】測試模型初始化")
print("-" * 80)

try:
    from scripts.models.model_google_stt import GoogleSTTModel
    
    test_configs = [
        {"model": "chirp_3", "location": "us"},
        {"model": "chirp_3", "location": "us-central1"},
        {"model": "chirp_2", "location": "us-central1"},
        {"model": "latest_long", "location": "us-central1"},
    ]
    
    successful_configs = []
    
    for config in test_configs:
        print(f"\n測試配置: {config['model']} @ {config['location']}")
        
        try:
            model = GoogleSTTModel(
                project_id=project_id,
                model=config['model'],
                location=config['location'],
                auto_config=True,
                auto_convert_audio=True
            )
            
            print(f"  ✅ 初始化成功")
            print(f"  Recognizer: projects/{project_id}/locations/{config['location']}/recognizers/_")
            print(f"  端點: {model.api_endpoint}")
            
            successful_configs.append(config)
            
        except Exception as e:
            error_msg = str(e)[:150]
            print(f"  ❌ 初始化失敗: {error_msg}")
    
    if successful_configs:
        print(f"\n✅ 成功初始化 {len(successful_configs)} 個配置")
    else:
        print(f"\n❌ 警告: 所有配置初始化失敗")

except ImportError as e:
    print(f"  ❌ 無法導入 GoogleSTTModel: {e}")
    print(f"  請檢查 scripts/models/model_google_stt.py 是否存在")
    sys.exit(1)

# ============================================================================
# 步驟 4: 測試實際辨識
# ============================================================================
print("\n【步驟 4】測試實際辨識")
print("-" * 80)

# 找測試音檔
test_dir = PROJECT_ROOT / "experiments" / "Test_02_TMRT" / "source_audio"

if not test_dir.exists():
    print(f"  ⚠️  測試目錄不存在: {test_dir}")
    print(f"  跳過辨識測試")
else:
    audio_files = list(test_dir.glob('*.wav'))
    
    if not audio_files:
        print(f"  ⚠️  找不到 WAV 檔案")
        print(f"  跳過辨識測試")
    else:
        # 選擇第一個檔案進行測試
        test_file = str(audio_files[0])
        print(f"\n使用測試音檔: {Path(test_file).name}")
        print(f"檔案大小: {Path(test_file).stat().st_size / 1024:.1f} KB")
        
        # 只測試成功初始化的前兩個配置
        configs_to_test = successful_configs[:2] if successful_configs else test_configs[:2]
        
        test_results = []
        
        for config in configs_to_test:
            print(f"\n  測試: {config['model']} @ {config['location']}")
            
            try:
                model = GoogleSTTModel(
                    project_id=project_id,
                    model=config['model'],
                    location=config['location'],
                    auto_config=True,
                    auto_convert_audio=True
                )
                
                result = model.transcribe_file(
                    test_file,
                    phrases=None,
                    enable_word_time_offsets=True
                )
                
                if 'error' in result:
                    print(f"    ❌ 辨識錯誤: {result['error']}")
                    test_results.append({
                        'config': config,
                        'status': 'error',
                        'message': result['error']
                    })
                    
                elif result.get('transcript'):
                    transcript = result['transcript']
                    confidence = result.get('confidence', 0)
                    
                    print(f"    ✅ 辨識成功")
                    print(f"    文字: {transcript[:80]}{'...' if len(transcript) > 80 else ''}")
                    print(f"    信心度: {confidence:.2%}")
                    
                    test_results.append({
                        'config': config,
                        'status': 'success',
                        'transcript': transcript,
                        'confidence': confidence
                    })
                else:
                    print(f"    ⚠️  辨識結果為空")
                    test_results.append({
                        'config': config,
                        'status': 'empty',
                        'message': '辨識結果為空'
                    })
                    
            except Exception as e:
                error_msg = str(e)[:200]
                print(f"    ❌ 執行失敗: {error_msg}")
                test_results.append({
                    'config': config,
                    'status': 'exception',
                    'message': error_msg
                })

# ============================================================================
# 步驟 5: 診斷總結和建議
# ============================================================================
print("\n" + "=" * 80)
print("【診斷總結】")
print("=" * 80)

# 分析結果
if 'test_results' in locals() and test_results:
    success_count = sum(1 for r in test_results if r['status'] == 'success')
    error_count = sum(1 for r in test_results if r['status'] == 'error')
    
    print(f"\n辨識測試結果:")
    print(f"  成功: {success_count}/{len(test_results)}")
    print(f"  失敗: {error_count}/{len(test_results)}")
    
    # 找出所有成功的配置
    working_configs = [r['config'] for r in test_results if r['status'] == 'success']
    
    if working_configs:
        print(f"\n✅ 找到 {len(working_configs)} 個可用配置:")
        for config in working_configs:
            print(f"  - {config['model']} @ {config['location']}")
        
        # 推薦使用的配置
        best_config = working_configs[0]
        print(f"\n【推薦配置】")
        print(f"  模型: {best_config['model']}")
        print(f"  區域: {best_config['location']}")
        
        print(f"\n【執行批次處理】")
        print(f"  cd /Users/apple/Projects/aiSpeech")
        print(f"  python scripts/batch_inference.py \\")
        print(f"      --test-case Test_02_TMRT \\")
        print(f"      --model google_stt \\")
        print(f"      --stt-model {best_config['model']} \\")
        print(f"      --stt-region {best_config['location']}")
    
    else:
        print(f"\n❌ 所有配置都失敗了")
        
        # 分析錯誤類型
        error_messages = [r['message'] for r in test_results if 'message' in r]
        
        if error_messages:
            print(f"\n常見錯誤:")
            unique_errors = list(set(error_messages))
            for i, error in enumerate(unique_errors[:3], 1):
                print(f"  {i}. {error[:100]}")
        
        print(f"\n【可能的問題】")
        
        if any('404' in r.get('message', '') for r in test_results):
            print(f"  ❌ 404 錯誤: Recognizer 未找到")
            print(f"     - 可能原因: 區域或專案 ID 錯誤")
            print(f"     - 解決方案: 嘗試不同的區域配置")
        
        if any('encoding' in r.get('message', '').lower() for r in test_results):
            print(f"  ❌ 音訊編碼錯誤")
            print(f"     - 可能原因: 音訊格式不支援")
            print(f"     - 解決方案: 確認 auto_convert_audio=True")
        
        if any('60 seconds' in r.get('message', '') for r in test_results):
            print(f"  ❌ 音檔過長")
            print(f"     - 可能原因: 音檔超過 60 秒")
            print(f"     - 解決方案: 使用 VAD 切分或 latest_long 模型")
        
        print(f"\n【建議行動】")
        print(f"  1. 檢查 Google Cloud Console:")
        print(f"     - Speech-to-Text API 是否已啟用")
        print(f"     - 服務帳戶權限是否正確 (roles/speech.client)")
        print(f"  2. 嘗試不同的區域:")
        print(f"     - us")
        print(f"     - us-central1")
        print(f"     - eu")
        print(f"  3. 嘗試不同的模型:")
        print(f"     - chirp_2 (較舊但穩定)")
        print(f"     - latest_long (支援長音檔)")

else:
    print(f"\n⚠️  未執行辨識測試")
    print(f"  請確認測試音檔目錄存在:")
    print(f"  {test_dir}")

print("\n" + "=" * 80)
print("診斷完成")
print("=" * 80)

# 儲存診斷結果
output_file = PROJECT_ROOT / "diagnosis_output.txt"
print(f"\n💾 診斷結果已保存到: {output_file}")
