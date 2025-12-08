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
LOCATION = "asia-northeast1"  # 使用支援 Chirp 模型的區域(東京)；新加坡、ＥＵ、ＵＳ也支援


# 1. 設定區域
# 若使用Chirp模型，建議先查詢該模型支援的地區，https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3?utm_source=chatgpt.com，官方文件顯示US, EU, asia-northeast1, asia-southeast1皆支援
LOCATION = "asia-northeast1" # 原: "global"

# 2. 設定 API Endpoint（Chirp 模型使用特定區域端點）
API_ENDPOINT = f"{LOCATION}-speech.googleapis.com" 

# Recognizer 路徑：指向 global 的預設辨識器
RECOGNIZER_NAME = f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_"

gcs_uri = "gs://my-speech-auto-2025/TMRT_5minVoice_20251125.wav"


# 3. ⚠️ 修正：建立 Client 時傳入 Endpoint
# 這樣API請求才會正確送到asia-northeast1，而不是送到global導致400錯誤
# 原錯誤：ClientOptions = ClientOptions(...) <-這會覆蓋類別名稱且變數是大寫
# 修正為：使用小寫變數 my_client_options 或 options
my_client_options = ClientOptions(api_endpoint=API_ENDPOINT)

# 建立 Client時傳入正確定義的變數
client = speech_v2.SpeechClient(client_options=my_client_options)

config = cloud_speech.RecognitionConfig(
    auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
    # 建議使用標準的BCP-47語言代碼格式，cmn-Hant-TW 或 zh-TW皆可
    language_codes=["cmn-Hant-TW"],  # 保留 zh-TW 以優化中文辨識；若需自動偵測，可改為 ["auto"]

    
    # 4. 模型選擇 ⚠️ 主要變更：切換到 Chirp 3 模型，專為長中文語音優化
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
    print("雲端處理中 (Global 資源池，使用 Chirp 3)...")

    # 設定 timeout 為 900 秒（長音頻適用）
    response = operation.result(timeout=900)

    # 輸出結果
    output_filename = "【{LOCATION}_Chirp3】轉錄結果.txt"  # ⚠️ 更新檔名以區分
    with open(output_filename, "w", encoding="utf-8") as f:
        for file_result in response.results.values():
            # 檢查是否有錯誤
            if file_result.error.message:
                print(f"❌ 檔案處理發生錯誤: {file_result.error.message}")
                continue

            for result in file_result.transcript.results:
                if not result.alternatives:
                    continue  # 跳過沒有替代方案的結果
                best = result.alternatives[0]
                text = best.transcript.strip()
                confidence = best.confidence

                line = f"[{confidence:.1%}] {text}"
                f.write(line + "\n\n")
                print(line)

    print(f"\n✅ 轉錄成功！已產生 {output_filename}")

except Exception as e:
    print(f"\n❌ 發生錯誤: {e}")
