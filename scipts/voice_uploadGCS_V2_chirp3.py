# 語音上傳GCS+STT V2+Chirp 3模式(限定特定區域)，進行語音辨識
# 執行前需確定虛擬環境升級到最新版（包含 V2 API 支援） pip install --upgrade google-cloud-speech
# 驗證安裝成功（會顯示版本 >= 2.34.0） pip show google-cloud-speech

import os
from google.cloud import storage
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions  # ⚠️ 必須匯入這個來指定 Endpoint

# =========================參數設定區==========================   
# 1. 設定金鑰路徑
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-speech-key.json"

# 2. 專案設定
PROJECT_ID = "dazzling-seat-315406"
BUCKET_NAME = "my-speech-auto-2025"
# 若使用Chirp模型，建議先查詢該模型支援的地區，https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3?utm_source=chatgpt.com，官方文件顯示US, EU, asia-northeast1, asia-southeast1皆支援
LOCATION = "asia-northeast1"  # 使用支援 Chirp 模型的區域(東京)

# 3. 檔案上傳（確認語音檔案跟程式放在同一層資料夾）
LOCAL_FILENAME = "TMRT_5minVoice_20251125.wav"


# ==========================================================

def run_pipeline():
    # 1. 先定義GCS路徑
    gcs_uri = f"gs://{BUCKET_NAME}/{LOCAL_FILENAME}"

    print(f"🚀 步驟一：正在將本地檔案 '{LOCAL_FILENAME}' 上傳到 Cloud Storage...")
    
    # 檢查本地檔案是否存在
    if not os.path.exists(LOCAL_FILENAME):
        print(f"❌ 找不到本地檔案：{LOCAL_FILENAME}")
        print("💡 請將 wav 檔複製到這個程式碼所在的資料夾中！")
        return

    # 2. 執行上傳
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(LOCAL_FILENAME)
        blob.upload_from_filename(LOCAL_FILENAME)
        print(f"✅ 上傳成功！檔案位置: {gcs_uri}")
    except Exception as e:
        print(f"❌ 上傳失敗 (請檢查權限或網路): {e}")
        return
    
    # 3. 開始轉錄
    print(f"\n🚀 步驟二：呼叫 Speech V2 Chirp 模型進行轉錄...")
    
    # 設定 API Endpoint（Chirp 模型使用特定區域端點）
    API_ENDPOINT = f"{LOCATION}-speech.googleapis.com"
    # Recognizer 路徑：指向 global 的預設辨識器
    RECOGNIZER_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"
    
    # 建立 Client 時傳入 Endpoint
    # 這樣API請求才會正確送到asia-northeast1，而不是送到global導致400錯誤
    # 原錯誤：ClientOptions = ClientOptions(...) <-這會覆蓋類別名稱且變數是大寫
    client_options = ClientOptions(api_endpoint=API_ENDPOINT)
    # 建立 Client時傳入正確定義的變數
    client = speech_v2.SpeechClient(client_options=client_options)

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        # 建議使用標準的BCP-47語言代碼格式，cmn-Hant-TW 或 zh-TW皆可
        language_codes=["cmn-Hant-TW"],  # 保留 zh-TW 以優化中文辨識；若需自動偵測，可改為 ["auto"]
        model="chirp_3", 
        features=cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
            # 可選：若需說話者區分，新增 enable_speaker_diarization=True
        ),
    )

    file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)
    request = cloud_speech.BatchRecognizeRequest(
        recognizer=RECOGNIZER_NAME,
        config=config,
        files=[file_metadata],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )

    # ⚠️ 更新提示：反映 Chirp 3 模型
    print(f"正在送出給 Google Speech V2 API（區域：{LOCATION}），請稍等...")
    print("連線 Endpoint: {API_ENDPINT}")  # 確認連線網址正確
    print("使用模型: chirp_3 (繁體中文長語音優化)")


    try:
        operation = client.batch_recognize(request=request)
        print("⏳ 雲端運算中 (約需 3~5 分鐘)...")
        response = operation.result(timeout=1800)
        
        # 輸出結果
        output_filename = "Chirp_轉錄結果.txt"
        with open(output_filename, "w", encoding="utf-8") as f:
            for file_result in response.results.values():
                if file_result.error.message:
                    print(f"❌ 轉錄錯誤: {file_result.error.message}")
                    continue
                for result in file_result.transcript.results:
                    best = result.alternatives[0]
                    line = f"[{best.confidence:.1%}] {best.transcript.strip()}"
                    f.write(line + "\n\n")
                    print(line[:50] + "...") # 預覽前50字

        print(f"\n✅ 全部完成！請查看檔案: {output_filename}")

    except Exception as e:
        print(f"❌ 轉錄過程發生錯誤: {e}")

if __name__ == "__main__":
    run_pipeline()
