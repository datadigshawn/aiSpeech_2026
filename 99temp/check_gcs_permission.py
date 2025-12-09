import os
from google.cloud import storage

# 設定金鑰路徑 (必須與您跑 STT 的是同一個 key)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

# 您的 Bucket 名稱 (不含 gs://)
BUCKET_NAME = "my-speech-auto-2025"
# 您的檔案名稱
TARGET_FILE = "TMRT_5minVoice_20251125.wav"

print(f"🕵️‍♂️ 正在檢查 Bucket: {BUCKET_NAME}")

try:
    storage_client = storage.Client()
    
    # 1. 嘗試存取 Bucket
    try:
        bucket = storage_client.get_bucket(BUCKET_NAME)
        print("✅ 成功連線到 Bucket！(金鑰有效)")
    except Exception as e:
        print(f"❌ 無法存取 Bucket。原因：{e}")
        print("💡 請檢查：Service Account 是否有 'Storage Object Viewer' 權限？")
        exit()

    # 2. 列出裡面所有檔案 (這可以確認程式到底看得到什麼)
    print(f"\n📂 Bucket 內的檔案清單：")
    blobs = list(bucket.list_blobs())
    
    found = False
    for blob in blobs:
        print(f" - {blob.name}")
        if blob.name == TARGET_FILE:
            found = True

    # 3. 最終判定
    print("-" * 30)
    if found:
        print(f"✅ 找到了！檔案 {TARGET_FILE} 確實存在且可讀取。")
        print("🤔 如果 STT 還是報錯，可能是 API 跨區域讀取延遲，請稍後再試。")
    else:
        print(f"❌ 找不到檔案：{TARGET_FILE}")
        print("💡 可能原因：")
        print("   1. 檔名真的有錯字 (例如大小寫、空格)。")
        print("   2. 檔案放在資料夾內 (例如 'data/file.wav')，路徑要補全。")
        print("   3. 上傳尚未完成。")

except Exception as e:
    print(f"❌ 發生未預期的錯誤: {e}")