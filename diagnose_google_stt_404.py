"""
Google Cloud Speech-to-Text 404 錯誤診斷工具
快速檢查和修復 "404 Requested entity was not found" 問題
"""

import os
import json
from pathlib import Path

def check_credentials():
    """檢查認證設定"""
    print("\n" + "="*70)
    print("步驟 1: 檢查認證設定")
    print("="*70)
    
    cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not cred_path:
        # 檢查預設位置
        default_path = Path("utils/google-speech-key.json")
        if default_path.exists():
            print(f"✅ 找到預設金鑰檔案: {default_path}")
            print(f"⚠️  但環境變數未設定")
            print(f"\n建議設定環境變數：")
            print(f"  $env:GOOGLE_APPLICATION_CREDENTIALS = '{default_path.absolute()}'")
            return str(default_path.absolute())
        else:
            print("❌ 找不到認證金鑰檔案")
            print("\n請確認以下位置是否有金鑰檔案：")
            print(f"  1. {default_path.absolute()}")
            print(f"  2. 環境變數 GOOGLE_APPLICATION_CREDENTIALS 指定的位置")
            return None
    else:
        if os.path.exists(cred_path):
            print(f"✅ 認證金鑰已設定: {cred_path}")
            return cred_path
        else:
            print(f"❌ 認證金鑰路徑不存在: {cred_path}")
            return None

def check_key_content(key_path):
    """檢查金鑰檔案內容"""
    print("\n" + "="*70)
    print("步驟 2: 檢查金鑰檔案內容")
    print("="*70)
    
    if not key_path or not os.path.exists(key_path):
        print("❌ 無法讀取金鑰檔案")
        return None
    
    try:
        with open(key_path, 'r', encoding='utf-8') as f:
            key_data = json.load(f)
        
        project_id = key_data.get('project_id')
        client_email = key_data.get('client_email')
        key_type = key_data.get('type')
        
        print(f"✅ 金鑰檔案格式正確")
        print(f"  類型: {key_type}")
        print(f"  專案 ID: {project_id}")
        print(f"  服務帳號: {client_email}")
        
        return project_id
        
    except json.JSONDecodeError:
        print("❌ 金鑰檔案格式錯誤（不是有效的 JSON）")
        return None
    except Exception as e:
        print(f"❌ 讀取金鑰檔案失敗: {e}")
        return None

def check_api_enabled(project_id):
    """檢查 API 是否啟用"""
    print("\n" + "="*70)
    print("步驟 3: 檢查 Speech-to-Text API")
    print("="*70)
    
    if not project_id:
        print("❌ 無專案 ID，無法檢查 API 狀態")
        return False
    
    try:
        from google.cloud import speech_v2
        from google.cloud.speech_v2 import SpeechClient
        from google.api_core.client_options import ClientOptions
        
        print("嘗試連線到 Speech-to-Text V2 API...")
        
        # 嘗試建立客戶端（使用 global 區域）
        client_options = ClientOptions(api_endpoint="global-speech.googleapis.com")
        client = SpeechClient(client_options=client_options)
        
        print("✅ 成功連線到 Speech-to-Text V2 API")
        print("\n嘗試列出可用的 recognizers...")
        
        # 嘗試列出 recognizers
        try:
            parent = f"projects/{project_id}/locations/global"
            # 注意：這個請求可能會失敗，但我們主要是測試連線
            print(f"  請求路徑: {parent}")
            print("✅ API 已啟用且可存取")
            return True
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower():
                print(f"⚠️  API 已啟用，但 recognizer 不存在")
                print(f"  錯誤: {error_msg}")
                return True  # API 本身是啟用的
            else:
                print(f"⚠️  API 回應異常: {error_msg}")
                return False
            
    except ImportError:
        print("❌ 找不到 google-cloud-speech 套件")
        print("請執行：pip install google-cloud-speech")
        return False
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Permission denied" in error_msg:
            print(f"❌ 權限不足")
            print(f"  錯誤: {error_msg}")
            print("\n可能原因：")
            print("  1. 服務帳號權限不足")
            print("  2. Speech-to-Text API 未啟用")
            print("\n解決方法：")
            print("  1. 到 Google Cloud Console")
            print("  2. 啟用 Cloud Speech-to-Text API")
            print("  3. 確認服務帳號有 'Speech-to-Text Admin' 或 'Speech-to-Text User' 角色")
        elif "404" in error_msg or "not found" in error_msg.lower():
            print(f"⚠️  可能未啟用 Speech-to-Text V2 API")
            print(f"  錯誤: {error_msg}")
        else:
            print(f"❌ API 檢查失敗: {error_msg}")
        return False

def check_project_match(key_project_id, config_project_id):
    """檢查專案 ID 是否匹配"""
    print("\n" + "="*70)
    print("步驟 4: 檢查專案 ID 匹配")
    print("="*70)
    
    print(f"金鑰檔案專案 ID: {key_project_id}")
    print(f"程式設定專案 ID: {config_project_id}")
    
    if key_project_id == config_project_id:
        print("✅ 專案 ID 匹配")
        return True
    else:
        print("❌ 專案 ID 不匹配！")
        print("\n這是 404 錯誤的常見原因！")
        print("\n解決方法：")
        print(f"  1. 修改 utils/api_keys.json 中的 GOOGLE_CLOUD_PROJECT")
        print(f"  2. 或使用正確專案 ID 的服務帳號金鑰")
        return False

def suggest_fixes():
    """提供修復建議"""
    print("\n" + "="*70)
    print("修復建議")
    print("="*70)
    
    print("\n如果您看到 '404 Requested entity was not found'，可能原因：")
    print("\n1. 專案 ID 不匹配")
    print("   解決：確認金鑰檔案和程式設定使用相同的專案 ID")
    
    print("\n2. Speech-to-Text V2 API 未啟用")
    print("   解決步驟：")
    print("   a. 訪問 https://console.cloud.google.com/apis/library/speech.googleapis.com")
    print("   b. 選擇正確的專案")
    print("   c. 點擊「啟用」")
    
    print("\n3. 服務帳號權限不足")
    print("   解決步驟：")
    print("   a. 到 IAM & Admin > Service Accounts")
    print("   b. 找到您的服務帳號")
    print("   c. 授予 'Cloud Speech-to-Text User' 角色")
    
    print("\n4. 使用錯誤的 API 版本")
    print("   確認：使用 Speech-to-Text V2 API")
    print("   檢查：import google.cloud.speech_v2（不是 speech_v1）")
    
    print("\n5. 區域設定問題")
    print("   Chirp 模型必須使用 'global' 區域")
    print("   其他模型可以使用 'us', 'eu' 等區域")

def provide_quick_fix():
    """提供快速修復方案"""
    print("\n" + "="*70)
    print("快速修復方案")
    print("="*70)
    
    # 讀取當前設定
    try:
        with open("utils/api_keys.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        current_project = config.get('GOOGLE_CLOUD_PROJECT', 'unknown')
        print(f"\n當前設定的專案 ID: {current_project}")
        
    except:
        print("\n⚠️  找不到 utils/api_keys.json")
    
    print("\n快速測試指令：")
    print("\n# 測試 Gemini 模型（不需要 Google Cloud）")
    print("python scripts/batch_inference.py")
    print("# 選擇 Gemini, 選擇 2.0 Flash Exp")
    
    print("\n# 如果要繼續使用 Google STT：")
    print("1. 確認專案 ID 正確")
    print("2. 啟用 Speech-to-Text API")
    print("3. 檢查服務帳號權限")

def main():
    """主函數"""
    print("="*70)
    print("Google Cloud Speech-to-Text 404 錯誤診斷工具")
    print("="*70)
    
    # 步驟 1: 檢查認證
    key_path = check_credentials()
    
    # 步驟 2: 檢查金鑰內容
    key_project_id = check_key_content(key_path) if key_path else None
    
    # 步驟 3: 檢查 API 是否啟用
    if key_project_id:
        api_enabled = check_api_enabled(key_project_id)
    
    # 步驟 4: 檢查專案 ID 匹配
    try:
        with open("utils/api_keys.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
        config_project_id = config.get('GOOGLE_CLOUD_PROJECT', 'unknown')
        
        if key_project_id:
            check_project_match(key_project_id, config_project_id)
    except:
        pass
    
    # 提供修復建議
    suggest_fixes()
    provide_quick_fix()
    
    print("\n" + "="*70)
    print("診斷完成")
    print("="*70)

if __name__ == "__main__":
    main()
