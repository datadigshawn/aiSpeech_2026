import os
import google.generativeai as genai

# 設定 API Key (去 Google AI Studio 申請)
# 登入Google AI Studio API key管理頁面, https://aistudio.google.com/app/apikey
genai.configure(api_key="AIzaSyC6qkLuKrlmzN6KC4I4WAV7uUhweD9LxH0") 

try:
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("你好，請用一句話解釋什麼是 Python？")
    print("\n✅ 測試成功！回應如下：")
    print(response.text)
except Exception as e:
    print(f"\n❌ 仍然發生錯誤：{e}")