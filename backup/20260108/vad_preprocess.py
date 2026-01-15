"""
VAD (Voice Activity Detection) 處理器
支援兩種引擎:
1. Silero VAD (深度學習，推薦用於無線電)
2. WebRTC VAD (傳統訊號處理)
"""

import numpy as np
import wave
import torch
from pathlib import Path
from typing import List, Tuple, Optional
import warnings

from utils.logger import get_logger

logger = get_logger(__name__)


class VADProcessor:
    """語音活動檢測處理器"""
    
    def __init__(
        self,
        engine: str = "silero",
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 100,
        speech_pad_ms: int = 30
    ):
        """
        初始化 VAD 處理器
        
        Args:
            engine: VAD 引擎 ("silero" 或 "webrtc")
            threshold: 語音檢測閾值 (0.0-1.0)
            min_speech_duration_ms: 最小語音段長度 (毫秒)
            min_silence_duration_ms: 最小靜音段長度 (毫秒)
            speech_pad_ms: 語音段前後添加的緩衝 (毫秒)
        """
        self.engine = engine.lower()
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms
        
        # 初始化對應的 VAD 引擎
        if self.engine == "silero":
            self._init_silero_vad()
        elif self.engine == "webrtc":
            self._init_webrtc_vad()
        else:
            raise ValueError(f"不支援的 VAD 引擎: {engine}")
        
        logger.info(f"VAD 處理器初始化完成 (引擎: {self.engine})")
        logger.info(f"  閾值: {threshold}")
        logger.info(f"  最小語音段: {min_speech_duration_ms} ms")
    
    def _init_silero_vad(self):
        """初始化 Silero VAD"""
        try:
            # 載入 Silero VAD 模型
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            # 取得工具函數
            (self.get_speech_timestamps,
             self.save_audio,
             self.read_audio,
             self.VADIterator,
             self.collect_chunks) = utils
            
            logger.info("Silero VAD 模型載入成功")
            
        except Exception as e:
            logger.error(f"載入 Silero VAD 失敗: {e}")
            raise
    
    def _init_webrtc_vad(self):
        """初始化 WebRTC VAD"""
        try:
            import webrtcvad
            
            # WebRTC VAD 只支援 0, 1, 2, 3 四個級別
            # 將我們的 threshold 映射到這些級別
            if self.threshold <= 0.25:
                aggressiveness = 0  # 最不敏感
            elif self.threshold <= 0.50:
                aggressiveness = 1
            elif self.threshold <= 0.75:
                aggressiveness = 2
            else:
                aggressiveness = 3  # 最敏感
            
            self.vad = webrtcvad.Vad(aggressiveness)
            logger.info(f"WebRTC VAD 初始化成功 (aggressiveness: {aggressiveness})")
            
        except ImportError:
            logger.error("WebRTC VAD 未安裝，請執行: pip install webrtcvad")
            raise
        except Exception as e:
            logger.error(f"初始化 WebRTC VAD 失敗: {e}")
            raise
    
    def detect_speech_segments(
        self,
        audio_file: str,
        return_seconds: bool = False
    ) -> List[Dict]:
        """
        檢測音檔中的語音段
        
        Args:
            audio_file: 音檔路徑
            return_seconds: 是否以秒為單位回傳（否則為毫秒）
        
        Returns:
            語音段列表，每個元素包含:
            {
                'start': 開始時間,
                'end': 結束時間,
                'confidence': 信心分數 (僅 Silero)
            }
        """
        if self.engine == "silero":
            return self._detect_silero(audio_file, return_seconds)
        else:
            return self._detect_webrtc(audio_file, return_seconds)
    
    def _detect_silero(self, audio_file: str, return_seconds: bool) -> List[Dict]:
        """使用 Silero VAD 檢測"""
        # 讀取音檔
        wav = self.read_audio(audio_file, sampling_rate=16000)
        
        # 檢測語音時間戳
        speech_timestamps = self.get_speech_timestamps(
            wav,
            self.model,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            min_silence_duration_ms=self.min_silence_duration_ms,
            speech_pad_ms=self.speech_pad_ms,
            return_seconds=return_seconds
        )
        
        logger.info(f"Silero VAD 檢測到 {len(speech_timestamps)} 個語音段")
        
        return speech_timestamps
    
    def _detect_webrtc(self, audio_file: str, return_seconds: bool) -> List[Dict]:
        """使用 WebRTC VAD 檢測"""
        # 讀取音檔
        with wave.open(audio_file, 'rb') as wf:
            sample_rate = wf.getframerate()
            num_channels = wf.getnchannels()
            
            # WebRTC VAD 只支援特定的採樣率
            if sample_rate not in (8000, 16000, 32000, 48000):
                logger.warning(f"WebRTC VAD 不支援 {sample_rate} Hz，請使用 8k/16k/32k/48k")
                return []
            
            if num_channels != 1:
                logger.warning(f"WebRTC VAD 只支援單聲道，當前為 {num_channels} 聲道")
                return []
            
            audio_data = wf.readframes(wf.getnframes())
        
        # WebRTC VAD 需要固定長度的 frame (10ms, 20ms, 30ms)
        frame_duration_ms = 30  # 使用 30ms
        frame_length = int(sample_rate * frame_duration_ms / 1000) * 2  # 16-bit = 2 bytes
        
        # 逐 frame 檢測
        frames = []
        offset = 0
        while offset + frame_length <= len(audio_data):
            frame = audio_data[offset:offset + frame_length]
            is_speech = self.vad.is_speech(frame, sample_rate)
            frames.append(is_speech)
            offset += frame_length
        
        # 合併連續的語音 frame 成語音段
        segments = []
        in_speech = False
        speech_start = 0
        
        for i, is_speech in enumerate(frames):
            if is_speech and not in_speech:
                # 語音開始
                speech_start = i * frame_duration_ms
                in_speech = True
            elif not is_speech and in_speech:
                # 語音結束
                speech_end = i * frame_duration_ms
                
                # 只保留足夠長的語音段
                if speech_end - speech_start >= self.min_speech_duration_ms:
                    segment = {
                        'start': speech_start / 1000 if return_seconds else speech_start,
                        'end': speech_end / 1000 if return_seconds else speech_end
                    }
                    segments.append(segment)
                
                in_speech = False
        
        # 處理結尾仍在語音的情況
        if in_speech:
            speech_end = len(frames) * frame_duration_ms
            if speech_end - speech_start >= self.min_speech_duration_ms:
                segment = {
                    'start': speech_start / 1000 if return_seconds else speech_start,
                    'end': speech_end / 1000 if return_seconds else speech_end
                }
                segments.append(segment)
        
        logger.info(f"WebRTC VAD 檢測到 {len(segments)} 個語音段")
        
        return segments
    
    def is_speech_frame(
        self,
        audio_chunk: bytes,
        sample_rate: int = 16000
    ) -> bool:
        """
        即時判斷單一音訊 chunk 是否為語音（用於即時串流）
        
        Args:
            audio_chunk: 音訊資料 (bytes)
            sample_rate: 採樣率
        
        Returns:
            是否為語音
        """
        if self.engine == "silero":
            # 轉換為 tensor
            audio_int16 = np.frombuffer(audio_chunk, np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float32)
            
            # 重採樣到 16kHz (如果需要)
            if sample_rate != 16000:
                # 簡單的下採樣（生產環境應使用 librosa.resample）
                step = sample_rate // 16000
                audio_tensor = audio_tensor[::step]
            
            # 預測
            with torch.no_grad():
                speech_prob = self.model(audio_tensor, 16000).item()
            
            return speech_prob > self.threshold
            
        else:  # webrtc
            return self.vad.is_speech(audio_chunk, sample_rate)
    
    def calculate_metrics(
        self,
        detected_segments: List[Dict],
        ground_truth_segments: List[Dict]
    ) -> Dict:
        """
        計算 VAD 效能指標（誤觸率、漏接率）
        
        Args:
            detected_segments: VAD 檢測到的語音段
            ground_truth_segments: 標準答案語音段
        
        Returns:
            {
                'false_positive_rate': 誤觸率,
                'false_negative_rate': 漏接率,
                'precision': 精確度,
                'recall': 召回率
            }
        """
        # 簡化實作：計算總時長的重疊比例
        # 生產環境應使用更精確的 frame-level 比對
        
        def segments_to_set(segments):
            """將語音段轉換為毫秒集合"""
            ms_set = set()
            for seg in segments:
                start_ms = int(seg['start'] * 1000) if seg['start'] < 1000 else int(seg['start'])
                end_ms = int(seg['end'] * 1000) if seg['end'] < 1000 else int(seg['end'])
                ms_set.update(range(start_ms, end_ms))
            return ms_set
        
        detected_set = segments_to_set(detected_segments)
        truth_set = segments_to_set(ground_truth_segments)
        
        true_positive = len(detected_set & truth_set)
        false_positive = len(detected_set - truth_set)
        false_negative = len(truth_set - detected_set)
        
        # 計算指標
        precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0
        recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0
        
        fpr = false_positive / len(truth_set) if len(truth_set) > 0 else 0
        fnr = false_negative / len(truth_set) if len(truth_set) > 0 else 0
        
        metrics = {
            'false_positive_rate': round(fpr, 4),
            'false_negative_rate': round(fnr, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4)
        }
        
        logger.info(f"VAD 效能指標:")
        logger.info(f"  誤觸率 (FPR): {metrics['false_positive_rate']:.2%}")
        logger.info(f"  漏接率 (FNR): {metrics['false_negative_rate']:.2%}")
        logger.info(f"  精確度: {metrics['precision']:.2%}")
        logger.info(f"  召回率: {metrics['recall']:.2%}")
        
        return metrics


if __name__ == "__main__":
    # 測試 VAD 處理器
    
    # 測試 Silero VAD
    print("=== 測試 Silero VAD ===")
    silero_vad = VADProcessor(engine="silero", threshold=0.5)
    
    test_audio = "experiments/Test_01_TMRT/batch_processing/source_audio/test.wav"
    if Path(test_audio).exists():
        segments = silero_vad.detect_speech_segments(test_audio, return_seconds=True)
        print(f"\n檢測到 {len(segments)} 個語音段:")
        for i, seg in enumerate(segments[:5]):  # 只顯示前5個
            print(f"  段落 {i+1}: {seg['start']:.2f}s - {seg['end']:.2f}s")
    else:
        print(f"測試檔案不存在: {test_audio}")
    
    # 測試 WebRTC VAD (如果已安裝)
    try:
        print("\n=== 測試 WebRTC VAD ===")
        webrtc_vad = VADProcessor(engine="webrtc", threshold=0.5)
        
        if Path(test_audio).exists():
            segments = webrtc_vad.detect_speech_segments(test_audio, return_seconds=True)
            print(f"\n檢測到 {len(segments)} 個語音段:")
            for i, seg in enumerate(segments[:5]):
                print(f"  段落 {i+1}: {seg['start']:.2f}s - {seg['end']:.2f}s")
    except Exception as e:
        print(f"WebRTC VAD 測試失敗: {e}")