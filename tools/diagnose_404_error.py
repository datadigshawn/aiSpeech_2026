#!/usr/bin/env python3
"""
Google STT 404 錯誤診斷腳本
專門診斷 "404 Requested entity was not found" 錯誤

使用方式:
    cd /Users/apple/Projects/aiSpeech
    python diagnose_404_error.py
"""
import os
import sys
from pathlib import Path

# 設定路徑
sys.path.insert(0, '/Users/apple/Projects/aiSpeech')

print("=" * 80)
print("Google STT 404 錯誤診斷")
print("=" * 80)

# ============================================================================
# 步驟 1: 檢查認證
# ============================================================================
print("\n【步驟 1】檢查認證設定")
print("-" * 80)

creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
project_id = os.getenv('GOOGLE_CLOUD_PROJECT')

print(f"環境變數:")
print(f"  GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
print(f"  GOOGLE_CLOUD_PROJECT: {project_id}")

if creds_path and Path(creds_path).exists():
    print(f"  ✅ 金鑰檔案存在")
    
    import json
    with open(creds_path) as f:
        key_data = json.load(f)
    
    print(f"  金鑰類型: {key_data.get('type')}")
    print(f"  金鑰專案: {key_data.get('project_id')}")
    
    if key_data.get('project_id') != 'dazzling-seat-315406':
        print(f"  ⚠️  警告: 金鑰專案與預期不符！")
    
    if not project_id:
        print(f"  ⚠️  警告: GOOGLE_CLOUD_PROJECT 未設定")
        print(f"  將使用金鑰中的專案: {key_data.get('project_id')}")
        os.environ['GOOGLE_CLOUD_PROJECT'] = key_data.get('project_id')
        project_id = key_data.get('project_id')
else:
    print(f"  ❌ 金鑰檔案不存在或路徑錯誤")
    sys.exit(1)

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
    
    for location, endpoint in regions_to_test:
        try:
            print(f"\n測試區域: {location} (端點: {endpoint})")
            client_options = ClientOptions(api_endpoint=endpoint)
            client = SpeechClient(client_options=client_options)
            print(f"  ✅ 連接成功")
        except Exception as e:
            print(f"  ❌ 連接失敗: {e}")

except ImportError as e:
    print(f"  ❌ 無法導入 Google Cloud Speech 模組: {e}")
    sys.exit(1)

# ============================================================================
# 步驟 3: 測試 Recognizer 路徑
# ============================================================================
print("\n【步驟 3】測試 Recognizer 路徑")
print("-" * 80)

from scripts.models.model_google_stt import GoogleSTTModel

test_configs = [
    {"model": "chirp_3", "location": "us"},
    {"model": "chirp_3", "location": "us-central1"},
    {"model": "chirp_2", "location": "us-central1"},
    {"model": "latest_long", "location": "us-central1"},
]

for config in test_configs:
    print(f"\n測試配置: {config}")
    try:
        model = GoogleSTTModel(
            project_id=project_id or 'dazzling-seat-315406',
            model=config['model'],
            location=config['location'],
            auto_config=True,
            auto_convert_audio=True
        )
        print(f"  ✅ 初始化成功")
        print(f"  Recognizer: projects/{project_id}/locations/{config['location']}/recognizers/_")
        print(f"  端點: {model.api_endpoint}")
        
    except Exception as e:
        print(f"  ❌ 初始化失敗: {e}")

# ============================================================================
# 步驟 4: 測試實際辨識
# ============================================================================
print("\n【步驟 4】測試實際辨識")
print("-" * 80)

# 找測試音檔
test_dir = Path('experiments/Test_02_TMRT/source_audio')
if not test_dir.exists():
    print(f"  ⚠️  測試目錄不存在: {test_dir}")
else:
    audio_files = list(test_dir.glob('*.wav'))
    
    if not audio_files:
        print(f"  ⚠️  找不到 WAV 檔案")
    else:
        test_file = str(audio_files[0])
        print(f"\n使用測試音檔: {Path(test_file).name}")
        
        # 測試不同配置
        for config in test_configs[:2]:  # 只測試前兩個配置
            print(f"\n  測試: {config['model']} @ {config['location']}")
            
            try:
                model = GoogleSTTModel(
                    project_id=project_id or 'dazzling-seat-315406',
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
                elif result.get('transcript'):
                    print(f"    ✅ 辨識成功")
                    print(f"    文字: {result['transcript'][:100]}...")
                    print(f"    信心度: {result.get('confidence', 0):.2%}")
                else:
                    print(f"    ⚠️  辨識結果為空")
                    
            except Exception as e:
                print(f"    ❌ 執行失敗: {str(e)[:200]}")

# ============================================================================
# 步驟 5: 診斷建議
# ============================================================================
print("\n" + "=" * 80)
print("【診斷建議】")
print("=" * 80)

print("""
基於上述測試結果，請檢查：

1. 如果所有配置都顯示 404 錯誤：
   - 可能是專案 ID 錯誤
   - 可能是 API 權限未啟用
   - 建議在 Google Cloud Console 確認：
     * Speech-to-Text API 已啟用
     * 服務帳戶有正確的權限（roles/speech.client）

2. 如果某些區域成功，某些失敗：
   - 使用成功的區域配置
   - 更新預設區域設定

3. 如果顯示 "Audio encoding" 錯誤：
   - 音訊格式不支援
   - 確認 auto_convert_audio=True

4. 如果顯示 "Audio can be of a maximum of 60 seconds"：
   - 音檔太長
   - 使用 VAD 預處理或改用 latest_long 模型

執行建議:
  # 使用測試通過的配置
  python scripts/batch_inference.py \\
      --test-case Test_02_TMRT \\
      --model google_stt \\
      --stt-model [成功的模型] \\
      --stt-region [成功的區域]
""")

print("=" * 80)
print("診斷完成")
print("=" * 80)
