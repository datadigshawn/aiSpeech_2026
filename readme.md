# aiSpeech - 捷運緊急通訊語音辨識結果

## 專案說明
基於Google Cloud Speech-to-Text與Gemini AI的無線電語音轉文字系統

## 安裝步驟

### 1. Clone 專案
'''bash
git clone https://github.com/datadigshawn/aiSpeech_2026.git
cd aiSpeech
'''

### 2. 安裝相依套件
'''bash
pip install -r requirements.txt
'''

### 3. 設定API金鑰
複製 'config/google_stt_conig.json.template'並填入專案資訊
'''bash
cp config/google_stt_config.json.template config/google_stt_config.json
'''

將Google cloud金鑰檔案放置於：
- 'utils/google-speech-key.json'
- 'utils/google-gemini-key.rtf'

### 4. 同步音檔資料
從Google Drive 下載 'aiSpeech_Data' 資料夾，並按步驟4建立符號連結

## 使用方法
'''bash
# 執行streamlit 介面
steamlit run app_webInferface.py

# 批次處理測試
bash run_test02_google_stt.sh
'''
