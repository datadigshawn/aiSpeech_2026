import torch
import torch.nn as nn
import torch.optim as optim
import time

# 1. 匯入我們自己寫的模組
from config import device       # 抓取 Mac M2 (MPS) 或 Windows (CUDA)
from model import SimpleAudioNet

def train_process():
    print(f"🚀 開始訓練程序，使用裝置: {device}")
    
    # --- A. 準備模型 ---
    # input_size=1000 模擬音訊特徵, num_classes=2 (例如: 是/否)
    model = SimpleAudioNet(input_size=1000, num_classes=2)
    model.to(device) # <--- 關鍵！把模型搬到 GPU/MPS 上
    
    # --- B. 定義訓練工具 ---
    criterion = nn.CrossEntropyLoss()  # 損失函數 (衡量錯得多離譜)
    optimizer = optim.Adam(model.parameters(), lr=0.001) # 優化器 (負責修正參數)

    # --- C. 產生假數據 (模擬 64 筆音訊資料) ---
    print("📦 正在生成模擬音訊數據...")
    # 隨機產生 64 筆資料，每筆有 1000 個特徵
    dummy_inputs = torch.randn(64, 1000).to(device) 
    # 隨機產生 64 個答案 (0 或 1)
    dummy_labels = torch.randint(0, 2, (64,)).to(device)

    # --- D. 開始訓練迴圈 (Training Loop) ---
    model.train() # 開啟訓練模式
    
    start_time = time.time()
    epochs = 10 # 訓練 10 輪
    
    print("\n💪 開始健身 (Training)...")
    for epoch in range(epochs):
        # 1. 歸零 (清空上一步的梯度)
        optimizer.zero_grad()
        
        # 2. 前向傳播 (模型預測)
        outputs = model(dummy_inputs)
        
        # 3. 計算誤差 (Loss)
        loss = criterion(outputs, dummy_labels)
        
        # 4. 反向傳播 (學習)
        loss.backward()
        
        # 5. 更新參數
        optimizer.step()
        
        print(f"Epoch [{epoch+1}/{epochs}] | Loss: {loss.item():.4f}")

    end_time = time.time()
    print(f"\n✅ 訓練完成！總耗時: {end_time - start_time:.4f} 秒")
    print(f"🎉 恭喜！您的 {device} 成功跑完了一次完整的 AI 訓練流程。")

if __name__ == "__main__":
    train_process()
