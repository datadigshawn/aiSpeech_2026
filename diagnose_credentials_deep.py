#!/usr/bin/env python3
"""
Google Cloud Speech-to-Text 深度診斷工具
檢查認證檔案、專案設定、API 狀態
"""

import os
import sys
import json
from pathlib import Path

def check_credential_file():
    """檢查認證檔案內容"""
    print("\n" + "="*70)
    print("步驟 1: 檢查認證檔案")
    print("="*70)
    
    key_path = Path("utils/google-speech-key.json")
    
    if not key_path.exists():
        print(f"❌ 認證檔案不存在: {key_path}")
        return None
    
    print(f"✅ 認證檔案存在: {key_path}")
    
    try:
        with open(key_path, 'r', encoding='utf-8') as f:
            key_data = json.load(f)
        
        # 檢查必要欄位
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = []
        
        for field in required_fields:
            if field not in key_data:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ 認證檔案缺少必要欄位: {missing_fields}")
            return None
        
        # 檢查類型
        if key_data['type'] != 'service_account':
            print(f"❌ 錯誤的認證類型: {key_data['type']} (應該是 service_account)")
            return None
        
        print(f"✅ 認證類型正確: service_account")
        print(f"✅ 專案 ID: {key_data['project_id']}")
        print(f"✅ 服務帳號: {key_data['client_email']}")
        
        # 檢查 private_key 格式
        if not key_data['private_key'].startswith('-----BEGIN PRIVATE KEY-----'):
            print(f"⚠️  private_key 格式可能有問題")
        else:
            print(f"✅ private_key 格式正確")
        
        return key_data['project_id']
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤: {e}")
        return None
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return None

def check_api_keys_json():
    """檢查 api_keys.json 設定"""
    print("\n" + "="*70)
    print("步驟 2: 檢查 api_keys.json 設定")
    print("="*70)
    
    config_path = Path("utils/api_keys.json")
    
    if not config_path.exists():
        print(f"⚠️  api_keys.json 不存在")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        project_id = config.get('GOOGLE_CLOUD_PROJECT')
        
        if project_id:
            print(f"✅ GOOGLE_CLOUD_PROJECT: {project_id}")
            return project_id
        else:
            print(f"⚠️  未設定 GOOGLE_CLOUD_PROJECT")
            return None
            
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return None

def test_authentication():
    """測試認證是否有效"""
    print("\n" + "="*70)
    print("步驟 3: 測試認證")
    print("="*70)
    
    # 設定認證
    key_path = Path("utils/google-speech-key.json")
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_path)
    
    print(f"設定認證路徑: {key_path}")
    
    try:
        from google.cloud import speech_v2
        from google.cloud.speech_v2 import SpeechClient
        from google.api_core.client_options import ClientOptions
        
        print("✅ Google Cloud Speech 套件已安裝")
        
        # 嘗試建立客戶端
        try:
            # 使用 global 區域測試
            client_options = ClientOptions(api_endpoint="global-speech.googleapis.com")
            client = SpeechClient(client_options=client_options)
            print("✅ 成功建立 Speech Client (global)")
            
            # 嘗試 us 區域
            client_options_us = ClientOptions(api_endpoint="us-speech.googleapis.com")
            client_us = SpeechClient(client_options=client_options_us)
            print("✅ 成功建立 Speech Client (us)")
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 建立客戶端失敗: {error_msg}")
            
            if "403" in error_msg or "Permission denied" in error_msg:
                print("\n可能原因：")
                print("  1. 服務帳號權限不足")
                print("  2. Speech-to-Text API 未啟用")
            elif "401" in error_msg or "Unauthorized" in error_msg:
                print("\n可能原因：")
                print("  1. 認證檔案內容錯誤")
                print("  2. 服務帳號已被刪除或停用")
            elif "404" in error_msg:
                print("\n可能原因：")
                print("  1. API 未啟用")
                print("  2. 專案 ID 錯誤")
            
            return False
            
    except ImportError:
        print("❌ 找不到 google-cloud-speech 套件")
        print("請執行：pip install google-cloud-speech")
        return False

def test_recognizer_path():
    """測試 recognizer 路徑"""
    print("\n" + "="*70)
    print("步驟 4: 測試 Recognizer 路徑")
    print("="*70)
    
    key_path = Path("utils/google-speech-key.json")
    
    try:
        with open(key_path, 'r') as f:
            key_data = json.load(f)
        project_id = key_data['project_id']
    except:
        print("❌ 無法讀取專案 ID")
        return
    
    # 測試不同的 recognizer 路徑格式
    test_paths = [
        f"projects/{project_id}/locations/global/recognizers/_",
        f"projects/{project_id}/locations/us/recognizers/_",
        f"projects/{project_id}/locations/global/recognizers/chirp_3",
        f"projects/{project_id}/locations/us/recognizers/chirp_3",
    ]
    
    print(f"\n測試的 Recognizer 路徑：")
    for path in test_paths:
        print(f"  - {path}")
    
    print("\n正確的路徑格式應該是：")
    print(f"  projects/{project_id}/locations/{{LOCATION}}/recognizers/_")
    print("  其中 LOCATION 可以是 global, us, eu 等")

def provide_solutions():
    """提供解決方案"""
    print("\n" + "="*70)
    print("解決方案")
    print("="*70)
    
    print("\n如果還是 404 錯誤，請檢查：")
    
    print("\n1. 啟用 Speech-to-Text API")
    print("   訪問：https://console.cloud.google.com/apis/library/speech.googleapis.com")
    print("   - 選擇正確的專案")
    print("   - 點擊「啟用」")
    print("   - 等待 2-3 分鐘生效")
    
    print("\n2. 確認服務帳號權限")
    print("   訪問：https://console.cloud.google.com/iam-admin/iam")
    print("   - 找到服務帳號")
    print("   - 確認有以下任一角色：")
    print("     • Cloud Speech-to-Text User")
    print("     • Cloud Speech Administrator")
    print("     • Owner / Editor")
    
    print("\n3. 檢查專案 ID 是否正確")
    print("   訪問：https://console.cloud.google.com/home/dashboard")
    print("   - 確認當前專案 ID")
    print("   - 確認與認證檔案中的 project_id 一致")
    
    print("\n4. 嘗試重新建立服務帳號金鑰")
    print("   訪問：https://console.cloud.google.com/iam-admin/serviceaccounts")
    print("   - 選擇服務帳號")
    print("   - 「金鑰」→「新增金鑰」→「JSON」")
    print("   - 下載並替換 utils/google-speech-key.json")
    
    print("\n5. 確認 API 區域可用性")
    print("   Chirp 3 模型：")
    print("   - 主要區域：us, eu")
    print("   - 全域：global（建議使用）")

def main():
    """主函數"""
    print("="*70)
    print("Google Cloud Speech-to-Text 深度診斷工具")
    print("="*70)
    
    # 步驟 1: 檢查認證檔案
    key_project_id = check_credential_file()
    
    # 步驟 2: 檢查 api_keys.json
    config_project_id = check_api_keys_json()
    
    # 比較專案 ID
    if key_project_id and config_project_id:
        print("\n" + "="*70)
        print("專案 ID 比較")
        print("="*70)
        
        if key_project_id == config_project_id:
            print(f"✅ 專案 ID 一致: {key_project_id}")
        else:
            print(f"⚠️  專案 ID 不一致！")
            print(f"   認證檔案: {key_project_id}")
            print(f"   api_keys.json: {config_project_id}")
            print(f"\n建議：修改 api_keys.json 使其與認證檔案一致")
    
    # 步驟 3: 測試認證
    auth_ok = test_authentication()
    
    # 步驟 4: 測試 recognizer 路徑
    test_recognizer_path()
    
    # 提供解決方案
    provide_solutions()
    
    print("\n" + "="*70)
    print("診斷完成")
    print("="*70)
    
    # 最終建議
    if not auth_ok:
        print("\n⚠️  認證測試失敗！")
        print("請先解決認證問題，再嘗試執行語音辨識。")
    else:
        print("\n✅ 認證測試通過！")
        print("如果還是 404 錯誤，可能是 API 未啟用或權限問題。")

if __name__ == "__main__":
    main()
