
# 要在網頁增加錄音功能，要安裝錄音元件及處理音訊格式工具 pydub

import streamlit as st
import os
from google.cloud import speech

# --- 設定區 ---
# 請將此路徑改為你實際 key.json 的位置
# 建議：為了資安，正式專案通常會使用 st.secrets，但本機測試這樣最快
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google-gemini-key.json"

def transcribe_audio(content):
    """呼叫 Google Cloud STT API 進行辨識"""
    client = speech.SpeechClient()
    
    audio = speech.RecognitionAudio(content=content)
    
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, # 假設是 WAV
        language_code="zh-TW", # 繁體中文
        # enable_automatic_punctuation=True, # 是否開啟自動標點符號(選填)
    )

    response = client.recognize(config=config, audio=audio)
    return response

# --- 介面 (UI) 建置 ---

st.set_page_config(page_title="語音轉文字助手", page_icon="🎙️")

st.title("🎙️ Google Cloud Speech-to-Text 轉錄工具")
st.write("這是一個使用 **Streamlit** 與 **Google Cloud** 搭建的本機測試工具。")

# 1. 檔案上傳元件
uploaded_file = st.file_uploader("請上傳 WAV 音訊檔案", type=["wav"])

if uploaded_file is not None:
    # 2. 在介面上播放音訊，確認檔案沒問題
    st.audio(uploaded_file, format='audio/wav')
    
    # 3. 建立按鈕
    if st.button("開始辨識"):
        with st.spinner('正在傳送至 Google Cloud 進行分析...'):
            try:
                # 讀取上傳檔案的 Bytes 資料
                content = uploaded_file.read()
                
                # 呼叫辨識函式
                response = transcribe_audio(content)
                
                # 4. 顯示結果
                if not response.results:
                    st.warning("未能辨識出任何文字，請確認音檔清晰度。")
                else:
                    st.success("辨識完成！")
                    
                    # 將所有片段組合成完整文章
                    full_transcript = ""
                    for result in response.results:
                        text = result.alternatives[0].transcript
                        confidence = result.alternatives[0].confidence
                        full_transcript += text + " "
                        
                        # 顯示詳細資訊 (可摺疊)
                        with st.expander(f"片段詳情 (信心分數: {confidence:.2f})"):
                            st.write(text)
                    
                    st.markdown("### 📝 完整逐字稿：")
                    st.text_area("結果內容", value=full_transcript, height=200)
                    
            except Exception as e:
                st.error(f"發生錯誤: {e}")
                st.info("請檢查 key.json 是否存在，或是音檔格式是否正確。")