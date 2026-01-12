#!/usr/bin/env python3
"""
VAD (Voice Activity Detection) 處理器
支援 WebRTC VAD 和 Silero VAD
"""

from typing import Dict, List, Tuple, Optional  # 修復：明確導入 Dict
import numpy as np
from pathlib import Path

try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    
try:
    import torch
    SILERO_AVAILABLE = True
except ImportError:
    SILERO_AVAILABLE = False


class VADProcessor:
    """語音活動檢測處理器"""
    
    def __init__(
        self,
        vad_type: str = "webrtc",  # "webrtc" or "silero"
        aggressiveness: int = 3,    # WebRTC 靈敏度 (0-3)
        sample_rate: int = 16000
    ):
        """
        初始化 VAD 處理器
        
        Args:
            vad_type: VAD 類型 ("webrtc" 或 "silero")
            aggressiveness: WebRTC VAD 靈敏度 (0=寬鬆, 3=嚴格)
            sample_rate: 採樣率 (WebRTC 僅支援 8000, 16000, 32000, 48000)
        """
        self.vad_type = vad_type.lower()
        self.sample_rate = sample_rate
        
        # 初始化對應的 VAD
        if self.vad_type == "webrtc":
            if not WEBRTC_AVAILABLE:
                raise ImportError("WebRTC VAD 未安裝，請執行: pip install webrtcvad")
            self.vad = webrtcvad.Vad(aggressiveness)
        elif self.vad_type == "silero":
            if not SILERO_AVAILABLE:
                raise ImportError("Silero VAD 需要 PyTorch，請執行: pip install torch")
            self._init_silero()
        else:
            raise ValueError(f"不支援的 VAD 類型: {vad_type}")
    
    def _init_silero(self):
        """初始化 Silero VAD 模型"""
        # Silero VAD 模型載入
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        self.vad = model
        self.get_speech_timestamps = utils[0]
    
    def is_speech(
        self,
        audio_chunk: bytes,
        frame_duration_ms: int = 30
    ) -> bool:
        """
        判斷音訊片段是否包含語音
        
        Args:
            audio_chunk: 音訊數據 (bytes, 16-bit PCM)
            frame_duration_ms: 片段長度 (毫秒)，WebRTC 僅支援 10/20/30
        
        Returns:
            True 如果檢測到語音，否則 False
        """
        if self.vad_type == "webrtc":
            return self.vad.is_speech(audio_chunk, self.sample_rate)
        elif self.vad_type == "silero":
            # 將 bytes 轉換為 Tensor
            audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float32)
            
            # Silero 模型推論
            speech_prob = self.vad(audio_tensor, self.sample_rate).item()
            return speech_prob > 0.5  # 閾值可調整
    
    def process_audio_file(
        self,
        audio_path: Path,
        frame_duration_ms: int = 30
    ) -> Dict[str, any]:
        """
        處理完整音訊檔案，回傳語音片段資訊
        
        Args:
            audio_path: 音訊檔案路徑
            frame_duration_ms: 檢測窗口長度 (毫秒)
        
        Returns:
            包含語音片段時間戳的字典
        """
        # 這裡需要實作完整的音訊檔案處理邏輯
        # 目前先回傳基本結構
        return {
            "speech_segments": [],
            "total_speech_duration": 0.0,
            "vad_type": self.vad_type
        }
    
    def get_statistics(self) -> Dict[str, float]:
        """
        回傳 VAD 統計資訊 (用於 KPI 監控)
        
        Returns:
            包含誤觸率、漏接率等指標的字典
        """
        return {
            "false_positive_rate": 0.0,  # 誤觸率
            "false_negative_rate": 0.0,  # 漏接率
            "total_frames_processed": 0
        }


def test_vad():
    """測試 VAD 處理器"""
    print("測試 VAD 處理器...")
    
    # 測試 WebRTC VAD
    if WEBRTC_AVAILABLE:
        print("\n✅ WebRTC VAD 可用")
        vad_webrtc = VADProcessor(vad_type="webrtc", sample_rate=16000)
        print(f"   VAD 類型: {vad_webrtc.vad_type}")
    else:
        print("\n⚠️  WebRTC VAD 不可用")
    
    # 測試 Silero VAD
    if SILERO_AVAILABLE:
        print("\n✅ Silero VAD 可用")
        # vad_silero = VADProcessor(vad_type="silero", sample_rate=16000)
        # print(f"   VAD 類型: {vad_silero.vad_type}")
    else:
        print("\n⚠️  Silero VAD 不可用 (需要 PyTorch)")


if __name__ == "__main__":
    test_vad()
