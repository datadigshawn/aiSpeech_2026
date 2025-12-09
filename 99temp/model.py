import torch
import torch.nn as nn

class SimpleAudioNet(nn.Module):
    def __init__(self, input_size=1000, num_classes=10):
        super().__init__()
        # 這是網路的結構定義
        self.layer1 = nn.Linear(input_size, 128) # 第一層：輸入 -> 128個神經元
        self.relu = nn.ReLU()                    # 激活函數：過濾負值
        self.layer2 = nn.Linear(128, num_classes)# 輸出層：128 -> 分類數量(例如10個指令)
        
    def forward(self, x):
        # 這是資料流動的方向
        x = self.layer1(x)
        x = self.relu(x)
        x = self.layer2(x)
        return x

print("✅ 模型架構 (model.py) 定義完成")
