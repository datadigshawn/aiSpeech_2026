import torch
from config import device
import time

def run_test():
    print("🚀 開始測試 GitHub 同步流程...")
    
    # 模擬一個簡單運算
    a = torch.randn(1000, 1000).to(device)
    b = torch.randn(1000, 1000).to(device)
    
    start = time.time()
    result = torch.matmul(a, b)
    end = time.time()
    
    print(f"✅ 運算成功！耗時: {end - start:.4f} 秒")
    print("🎉 如果您在 GitHub 上看到這段程式碼，代表同步測試成功！")

if __name__ == "__main__":
    run_test()k